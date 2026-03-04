from __future__ import annotations
from pybend.core.models.actor_model import ActorModel
from pybend.core.models.base_user import BaseUser
from typing import ClassVar, Optional
from pydantic import Field


class User(BaseUser, ActorModel):
    __tablename__: ClassVar[str] = 'users'
    __abstract__: ClassVar[bool] = False
    __ui__: ClassVar[dict] = {
        'renderer': {'item': 'ntt-user'},
    }

    image: str = Field(
        default='https://ui-avatars.com/api/?name=User&background=94a3b8&color=fff&size=128&rounded=true'
    )
    age: Optional[int] = None
