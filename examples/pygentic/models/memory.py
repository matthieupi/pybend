from __future__ import annotations
from typing import ClassVar, Optional
from pydantic import Field

from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.authorize import AUTHENTICATED, OWNER, ROLE


class Memory(ActorModel):
    """Long-term memory store for agents — placeholder model."""

    __tablename__: ClassVar[str] = 'memories'
    __storable__: ClassVar[bool] = True
    __protected_fields__: ClassVar[set] = {'user_owner'}
    __access__: ClassVar[dict] = {
        'read': AUTHENTICATED,
        'create': AUTHENTICATED,
        'update': OWNER | ROLE('admin'),
        'delete': OWNER | ROLE('admin'),
    }

    content: str = Field(min_length=1)
    category: str = Field(default='fact')
    agent_id: str = Field(default='')
    tags: list = Field(default=[])
    relevance: float = Field(default=1.0, ge=0.0, le=1.0)
    user_owner: Optional[int] = Field(default=None)
