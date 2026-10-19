"""Thread — Per-conversation history persistence for agents.

Thread is a static ActorModel — standard CRUD IS the API. No custom
handlers, no ThreadManager. Agents read/update threads via TX:

    TX(name='get', target='threads', data={'id': thread_id})
    TX(name='update', target='threads', data={'id': thread_id, 'messages': [...]})

Messages are stored as TX-shaped dicts (JSONified TX envelopes), each
wrapping a pydantic-ai message in its `data` field:

    {'name': 'request', 'source': 'user', 'target': 'agents/1',
     'data': {kind: 'request', parts: [...]}, 'meta': {}, 'timestamp': ...}

Thread vs Memory (orthogonal modules):
    Thread — per-conversation, session-scoped, request/response pairs
    Memory — long-term, cross-session, facts/preferences (separate module)
"""

import logging
import time
from typing import ClassVar, Optional

from pydantic import Field

from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.authorize import AUTHENTICATED, OWNER, ROLE

logger = logging.getLogger('n3tx.agents.thread')


class Thread(ActorModel):
    """Per-conversation history. Standard CRUD — the model IS the manager.

    Fields:
        agent_addr: Actor address of the agent this thread belongs to.
        messages: Conversation history as TX-shaped dicts (JSON auto-serialized).
        user_owner: Protected field — auto-injected from JWT on create.
    """

    __tablename__: ClassVar[str] = 'threads'
    __storable__: ClassVar[bool] = True
    __protected_fields__: ClassVar[set] = {'user_owner'}
    __access__: ClassVar[dict] = {
        'read':   OWNER | ROLE('admin'),
        'create': AUTHENTICATED,
        'update': OWNER | ROLE('admin'),
        'delete': OWNER | ROLE('admin'),
    }

    agent_addr: str = Field(default='', description='Actor address of the agent')
    messages: list = Field(default=[], description='Conversation history (TX-shaped dicts)')
    user_owner: Optional[int] = Field(default=None, description='Owner user ID')

    @staticmethod
    def to_history(tx_messages: list) -> list:
        """Convert stored TX dicts → pydantic-ai ModelMessage list.

        Extracts the pydantic-ai message from each TX envelope's `data`
        field and validates it back into ModelMessage objects.

        Args:
            tx_messages: List of TX-shaped dicts from Thread.messages.

        Returns:
            List of pydantic-ai ModelMessage objects for the LLM's message_history.
        """
        if not tx_messages:
            return []
        from pydantic_ai.messages import ModelMessagesTypeAdapter
        raw = [msg['data'] for msg in tx_messages]
        return list(ModelMessagesTypeAdapter.validate_python(raw))

    @staticmethod
    def from_history(model_messages: list, source: str = '', target: str = '') -> list:
        """Convert pydantic-ai ModelMessage list → TX-shaped dicts for storage.

        Wraps each serialized pydantic-ai message in a TX envelope with
        name, source, target, data, meta, and timestamp fields.

        Args:
            model_messages: List of pydantic-ai ModelMessage from result.all_messages().
            source: TX source address (e.g., 'user' or adapter addr).
            target: TX target address (e.g., agent addr).

        Returns:
            List of TX-shaped dicts suitable for Thread.messages storage.
        """
        if not model_messages:
            return []
        from pydantic_ai.messages import ModelMessagesTypeAdapter
        serialized = ModelMessagesTypeAdapter.dump_python(model_messages, mode='json')
        return [
            {
                'name': msg.get('kind', 'message'),
                'source': source,
                'target': target,
                'data': msg,
                'meta': {},
                'timestamp': time.time(),
            }
            for msg in serialized
        ]
