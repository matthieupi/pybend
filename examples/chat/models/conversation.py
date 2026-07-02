"""Conversation model — an AgentActor that manages multi-turn chat.

The Conversation extends AgentActor, inheriting agent capabilities (name,
prompt, llm, tools, constraints) and adding chat-specific fields (messages,
user_owner). Messages are stored as Message records (via join table) that
mirror pydantic-ai's format.

Chat uses SSE streaming via @expose_route('/chat', stream=True):
    POST /conversations/{id}/chat  {content: "hello"}
    → SSE: event: chunk, data: {"text": "token"} ...
    → SSE: event: done,  data: {}

The AgentMixin.agentic_stream() handles LLM resolution, adapter lifecycle,
and pydantic-ai internally — zero pydantic-ai imports in app code.
"""

import logging
from typing import ClassVar, Optional

from pydantic import Field

from n3tx_agents.actor import AgentActor
from n3tx_core.authorize import ANYONE, AUTHENTICATED, OWNER, ROLE
from n3tx_core.utils.decorators import expose_route

from .message import Message
from .user import User

logger = logging.getLogger('n3tx.chat')


class Conversation(AgentActor):
    """A chat conversation that IS an agent.

    Extends AgentActor to inherit agent fields (name, prompt, llm, tools,
    constraints) and adds chat-specific fields (messages, user_owner).
    Messages are stored as Message records via a join table, preserving
    the full pydantic-ai message format for lossless multi-turn history.
    """

    __tablename__: ClassVar[str] = 'conversations'
    __protected_fields__: ClassVar[set] = {'user_owner'}
    __access__: ClassVar[dict] = {
        'read': OWNER | ROLE('admin'),
        'create': AUTHENTICATED,
        'update': OWNER | ROLE('admin'),
        'delete': OWNER | ROLE('admin'),
    }
    __ui__: ClassVar[dict] = {
        'field_order': ['name', 'prompt', 'llm', 'messages'],
        'renderer': {'item': 'ntx-chat-conv'},
    }
    __agent__: ClassVar = {'self_tools': False, 'neighbors': False}

    # Override AgentActor defaults for chat context
    name: str = Field(default='New Conversation', min_length=1, max_length=200)
    prompt: str = Field(default='You are a helpful assistant.')
    llm: str = Field(default='', description='LLM model string (empty = default)')
    # Override AgentActor's list[AgentTool] — chat doesn't use agent tools.
    # Must be defined on this class to prevent AgentMixin.tools fullmethod
    # descriptor from shadowing the Pydantic field default.
    tools: list = Field(default_factory=list)

    # Chat-specific fields
    messages: Optional[list[Message]] = Field(default=[])
    user_owner: Optional[int] = Field(default=None)

    def _get_message_model(self):
        """Get the join model class for messages (ConversationMessage)."""
        fk_models = getattr(self.__class__, '__fk_models__', {})
        return fk_models.get('messages', Message)

    def _load_messages(self):
        """Load all messages for this conversation, ordered by id."""
        msg_cls = self._get_message_model()
        result = msg_cls.list(
            sql_filter=(f"conversation_id = ?", [self.id]),
        )
        if isinstance(result, dict):
            return result.get('data', [])
        return result

    def _load_history(self):
        """Load messages and convert to pydantic-ai ModelMessage list."""
        messages = self._load_messages()
        history = []
        for msg in messages:
            try:
                history.append(msg.to_model_message())
            except Exception as e:
                logger.warning("Failed to convert message %s: %s", msg.id, e)
        return history

    @expose_route('/chat', methods=['POST'], stream=True, access=AUTHENTICATED)
    async def chat(self, content: str, user: Optional[User] = None):
        """Stream a chat response via SSE using the N3TX agent system."""
        conv = self.__class__.get(self.id)
        user_id = None
        if isinstance(user, dict):
            user_id = user.get('id')
        elif user is not None:
            user_id = user.id

        if conv.user_owner and user_id and conv.user_owner != user_id:
            raise Exception("Access denied")

        msg_cls = conv._get_message_model()

        # Always store the user message before streaming — it should persist
        # regardless of whether the LLM responds successfully.
        user_msg = Message(
            kind='request', content=content, role='user',
            parts=[{'part_kind': 'user-prompt', 'content': content}],
            user_owner=user_id,
        )
        setattr(user_msg, 'conversation_id', conv.id)
        msg_cls.create(user_msg)

        history = conv._load_history()
        streamed_text = ''

        async for chunk in conv.agentic_stream(
            task=content,
            prompt=conv.prompt,
            tools=[],
            message_history=history,
        ):
            name = chunk.get('name', '')
            if name == 'text':
                streamed_text += chunk['data']['text']
                yield {'text': chunk['data']['text']}
            elif name == 'done':
                # Prefer accumulated streamed text; fall back to done answer
                answer = streamed_text or chunk['data'].get('answer', '')

                # Assistant message
                asst_msg = Message(
                    kind='response', content=answer, role='assistant',
                    parts=[{'part_kind': 'text', 'content': answer}],
                    user_owner=user_id,
                )
                setattr(asst_msg, 'conversation_id', conv.id)
                msg_cls.create(asst_msg)
            elif name == 'error':
                error_msg = chunk['data'].get('message', 'Unknown error')
                raise Exception(error_msg)
