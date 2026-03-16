# example/models/user.py
from __future__ import annotations
from n3tx_core.models.proto_model import ProtoModel
from n3tx_core.models.base_user import BaseUser
from typing import ClassVar, Optional
from pydantic import Field


class Bot(ProtoModel):
    __storable__: ClassVar[bool] = True
    __tablename__: ClassVar[str] = 'bots'
    name: str
    description: str
    owner: str
    version: str
    status: str
    prompt: str


class User(BaseUser):
    __tablename__: ClassVar[str] = 'users'
    __abstract__: ClassVar[bool] = False

    __ui__: ClassVar[dict] = {
        'renderer': {
            'item': 'ntx-user',
        },
    }

    # App-specific fields (auth fields inherited from BaseUser)
    image: str = Field(default='https://ui-avatars.com/api/?name=User&background=94a3b8&color=fff&size=128&rounded=true')
    age: Optional[int] = None
