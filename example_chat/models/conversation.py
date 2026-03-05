"""Conversation model — an AgentActor that manages multi-turn chat.

The Conversation extends AgentActor, inheriting agent capabilities (name,
prompt, llm, tools, constraints) and adding chat-specific fields (messages,
user_owner). Messages are stored as Message records (via join table) that
mirror pydantic-ai's format.

Frontend sends via WebSocket:
    {name: 'send_message', target: 'conversations/1', data: {content: 'hello'}}

The actor handler dispatches to send_message(data, tx) which:
    1. Loads the conversation instance
    2. Loads message history from the join table
    3. Converts to pydantic-ai ModelMessage objects
    4. Runs pydantic-ai Agent with message_history
    5. Stores new messages (user + assistant) via join table
    6. Returns {response, usage, message_id}
"""

import logging
from typing import ClassVar, Optional

from pydantic import Field

from n3tx.core.agents.actor import AgentActor
from n3tx.core.models.ref import ListRef
from n3tx.core.authorize import ANYONE, AUTHENTICATED, OWNER, ROLE

from .message import Message

logger = logging.getLogger('n3tx.chat')


# Known provider prefixes that pydantic-ai resolves natively
_KNOWN_PROVIDERS = ('openai:', 'anthropic:', 'google:', 'groq:', 'mistral:', 'cohere:')


def _resolve_llm(llm_str: str):
    """Resolve an LLM string to a pydantic-ai model, configuring providers.

    Strings with a known provider prefix (anthropic:, openai:, etc.) pass
    through to pydantic-ai. Everything else (bare model names like 'qwen3.5:9b'
    or 'ollama:model') routes through Ollama with the configured base URL.
    """
    import config
    if not llm_str:
        llm_str = config.DEFAULT_LLM

    # Strip explicit 'ollama:' prefix if present
    if llm_str.startswith('ollama:'):
        llm_str = llm_str[len('ollama:'):]

    # Known providers pass through directly
    if any(llm_str.startswith(p) for p in _KNOWN_PROVIDERS):
        return llm_str, None

    # Everything else goes through Ollama
    from pydantic_ai.models.openai import OpenAIModel
    from pydantic_ai.providers.ollama import OllamaProvider
    base_url = config.OLLAMA_BASE_URL.rstrip('/')
    provider = OllamaProvider(base_url=f'{base_url}/v1')
    model = OpenAIModel(llm_str, provider=provider)
    return model, None


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
    }

    # Override AgentActor defaults for chat context
    name: str = Field(default='New Conversation', min_length=1, max_length=200)
    prompt: str = Field(default='You are a helpful assistant.')
    llm: str = Field(default='', description='LLM model string (empty = default)')

    # Chat-specific fields
    messages: Optional[ListRef[Message]] = Field(default=[])
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

    @classmethod
    async def send_message(cls, data: dict, tx):
        """Handle a chat message via the actor system.

        This is a non-exposed handler method — dispatched by ActorModel.handler
        for non-CRUD messages. The method signature (data, tx) follows the
        standard actor handler pattern.

        Args:
            data: {id: int, content: str} — conversation ID and user message.
            tx: TX message envelope (carries meta.user for auth).

        Returns:
            dict with {response, usage, message_id} or TX error.
        """
        from pydantic_ai import Agent

        conv_id = data.get('id')
        content = data.get('content', '').strip()
        user = (tx.meta or {}).get('user', {})
        user_id = user.get('user_id')

        if not conv_id:
            return tx.error("'id' required", code=400)
        if not content:
            return tx.error("'content' required", code=400)

        # Load conversation
        conv = cls.get(conv_id)
        if not conv:
            return tx.error(f"Conversation {conv_id} not found", code=404)

        # Ownership check
        if conv.user_owner and user_id and conv.user_owner != user_id:
            return tx.error("Access denied", code=403)

        # Resolve join model and LLM
        msg_cls = conv._get_message_model()
        llm_str = data.get('llm') or conv.llm or ''

        # Load existing history
        history = conv._load_history()

        # Create pydantic-ai agent and run
        # data.get('llm') can be a TestModel instance in tests — pass through directly
        if llm_str and not isinstance(llm_str, str):
            model = llm_str
        else:
            model, _ = _resolve_llm(llm_str)
        ai_agent = Agent(model, system_prompt=conv.prompt)
        result = await ai_agent.run(content, message_history=history)

        # Store new messages from this run
        new_messages = result.new_messages()
        stored_ids = []
        for msg in new_messages:
            record = Message.from_model_message(msg, user_owner=user_id)
            # Set the FK field for the join table
            setattr(record, 'conversation_id', conv_id)
            created = msg_cls.create(record)
            if created:
                stored_ids.append(created.id)

        # Extract assistant response text
        assistant_text = result.output

        # Usage
        usage = result.usage()

        return {
            'response': assistant_text,
            'usage': {
                'input_tokens': usage.input_tokens,
                'output_tokens': usage.output_tokens,
            },
            'message_ids': stored_ids,
        }
