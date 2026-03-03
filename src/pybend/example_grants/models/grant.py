from __future__ import annotations
from typing import ClassVar, Optional
from pydantic import Field

from pybend.core.models.actor_model import ActorModel
from pybend.core.authorize import ANYONE, AUTHENTICATED, OWNER, ROLE


class Grant(ActorModel):
    """A government grant discovered by an agent."""

    __tablename__: ClassVar[str] = 'grants'
    __storable__: ClassVar[bool] = True
    __access__: ClassVar[dict] = {
        'read': ANYONE,
        'create': AUTHENTICATED,
        'update': OWNER | ROLE('admin'),
        'delete': ROLE('admin'),
    }

    title: str = Field(min_length=1, max_length=500)
    agency: str = Field(min_length=1, max_length=200)
    deadline: Optional[str] = Field(default=None, description="Application deadline")
    amount_min: Optional[float] = Field(default=None, description="Minimum award amount")
    amount_max: Optional[float] = Field(default=None, description="Maximum award amount")
    url: str = Field(min_length=1, description="URL to the grant listing")
    description: str = Field(default='', json_schema_extra={'ui': {'widget': 'textarea'}})
    status: str = Field(default='discovered', description="discovered | reviewed | applied | expired")
