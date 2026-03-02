# example/models/user.py
from __future__ import annotations
from pybend.core.models.actor_model import ActorModel
from pybend.core.models.base_user import BaseUser
from typing import ClassVar, Optional
from pydantic import Field


class Bot(ActorModel):
    __storable__: ClassVar[bool] = True
    __tablename__: ClassVar[str] = 'bots'
    name: str
    description: str
    owner: str
    version: str
    status: str
    prompt: str


class User(BaseUser, ActorModel):
    __tablename__: ClassVar[str] = 'users'
    __abstract__: ClassVar[bool] = False

    __ui__: ClassVar[dict] = {
        'renderer': {
            'item': 'ntt-user',
        },
    }

    # App-specific fields (auth fields inherited from BaseUser)
    image: str = Field(default='https://ui-avatars.com/api/?name=User&background=94a3b8&color=fff&size=128&rounded=true')
    age: Optional[int] = None
