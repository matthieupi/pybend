"""Message model — mirrors pydantic-ai's ModelMessage format.

Each row stores one pydantic-ai message (ModelRequest or ModelResponse).
The `parts` field preserves the full pydantic-ai part structure (text,
tool calls, thinking, retries) as JSON. The `content` and `role` fields
are derived for display convenience.

Round-trip:
    pydantic-ai msg  -->  Message.from_model_message(msg)  -->  DB row
    DB row           -->  message.to_model_message()        -->  pydantic-ai msg
"""

import json
import logging
from typing import ClassVar, Literal, Optional

from pydantic import Field, TypeAdapter, model_validator

from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.authorize import ANYONE, AUTHENTICATED, ROLE

logger = logging.getLogger('n3tx.chat')

# JSON fields that need serialize/deserialize for SQLite TEXT columns
_JSON_FIELDS = ('parts', 'usage')


class Message(ActorModel):
    """A chat message that mirrors pydantic-ai's ModelMessage format.

    Stores the full pydantic-ai message structure (kind + parts) for
    lossless round-trip, plus derived content/role for display.
    """

    __tablename__: ClassVar[str] = 'messages'
    __storable__: ClassVar[bool] = True
    __access__: ClassVar[dict] = {
        'read': AUTHENTICATED,
        'create': AUTHENTICATED,
        'update': ROLE('admin'),
        'delete': ROLE('admin'),
    }

    # Core: mirrors pydantic-ai ModelMessage
    kind: Literal['request', 'response']
    parts: list = Field(default_factory=list)

    # Display fields (derived from parts)
    content: str = Field(default='')
    role: str = Field(default='user')

    # Metadata (varies by kind)
    model_name: Optional[str] = Field(default=None)
    usage: Optional[dict] = Field(default=None)
    instructions: Optional[str] = Field(default=None)
    timestamp_ms: Optional[str] = Field(default=None)

    # Ownership
    user_owner: Optional[int] = Field(default=None)

    @model_validator(mode='before')
    @classmethod
    def _deserialize_json_fields(cls, data):
        """Deserialize JSON TEXT strings from SQLite back to Python objects."""
        if isinstance(data, dict):
            for field in _JSON_FIELDS:
                val = data.get(field)
                if isinstance(val, str):
                    try:
                        data[field] = json.loads(val)
                    except (json.JSONDecodeError, TypeError):
                        pass
        return data

    def _storage_dict(self, exclude_unset: bool = True) -> dict:
        """Serialize list/dict fields to JSON strings for SQLite storage."""
        d = super()._storage_dict(exclude_unset=exclude_unset)
        for field in _JSON_FIELDS:
            if field in d and not isinstance(d[field], str):
                d[field] = json.dumps(d[field], default=str)
        return d

    @classmethod
    def from_model_message(cls, msg, user_owner: Optional[int] = None) -> 'Message':
        """Convert a pydantic-ai ModelMessage to our Message.

        Args:
            msg: A pydantic-ai ModelRequest or ModelResponse.
            user_owner: Owner user ID.

        Returns:
            A Message instance (not yet persisted).
        """
        from pydantic_ai.messages import ModelRequest, ModelResponse

        if isinstance(msg, ModelRequest):
            req_adapter = TypeAdapter(ModelRequest)
            data = json.loads(req_adapter.dump_json(msg))
            content, role = cls._extract_display(data)
            return cls(
                kind='request',
                parts=data['parts'],
                content=content,
                role=role,
                instructions=data.get('instructions'),
                timestamp_ms=data.get('timestamp'),
                user_owner=user_owner,
            )
        elif isinstance(msg, ModelResponse):
            resp_adapter = TypeAdapter(ModelResponse)
            data = json.loads(resp_adapter.dump_json(msg))
            content, role = cls._extract_display(data)
            return cls(
                kind='response',
                parts=data['parts'],
                content=content,
                role=role,
                model_name=data.get('model_name'),
                usage=data.get('usage'),
                timestamp_ms=data.get('timestamp'),
                user_owner=user_owner,
            )
        else:
            raise TypeError(f"Expected ModelRequest or ModelResponse, got {type(msg)}")

    def to_model_message(self):
        """Convert back to a pydantic-ai ModelRequest or ModelResponse.

        Returns:
            A pydantic-ai ModelRequest or ModelResponse instance.
        """
        from pydantic_ai.messages import ModelRequest, ModelResponse

        if self.kind == 'request':
            data = {
                'kind': 'request',
                'parts': self.parts,
                'timestamp': self.timestamp_ms,
                'instructions': self.instructions,
            }
            return TypeAdapter(ModelRequest).validate_python(data)
        else:
            data = {
                'kind': 'response',
                'parts': self.parts,
                'timestamp': self.timestamp_ms or '2026-01-01T00:00:00Z',
                'usage': self.usage or {
                    'input_tokens': 0, 'output_tokens': 0, 'details': {},
                },
                'model_name': self.model_name,
            }
            return TypeAdapter(ModelResponse).validate_python(data)

    @staticmethod
    def _extract_display(data: dict) -> tuple:
        """Extract display content and role from serialized message parts.

        Returns:
            (content, role) tuple for UI display.
        """
        kind = data.get('kind', 'request')
        parts = data.get('parts', [])

        if kind == 'request':
            # Prioritize user-prompt (may come after system-prompt in same message)
            fallback = None
            for p in parts:
                pk = p.get('part_kind', '')
                if pk == 'user-prompt':
                    content = p.get('content', '')
                    if isinstance(content, str):
                        return content, 'user'
                    return str(content), 'user'
                if pk == 'tool-return' and fallback is None:
                    fallback = (str(p.get('content', '')), 'tool')
                if pk == 'retry-prompt' and fallback is None:
                    fallback = (str(p.get('content', '')), 'system')
                if pk == 'system-prompt' and fallback is None:
                    fallback = (p.get('content', ''), 'system')
            return fallback or ('', 'user')
        else:
            for p in parts:
                pk = p.get('part_kind', '')
                if pk == 'text':
                    return p.get('content', ''), 'assistant'
                if pk == 'thinking':
                    return p.get('content', ''), 'assistant'
            # Tool call only (no text response yet)
            for p in parts:
                if p.get('part_kind') == 'tool-call':
                    return f"[tool: {p.get('tool_name', '?')}]", 'assistant'
            return '', 'assistant'
