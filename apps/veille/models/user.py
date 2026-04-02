from __future__ import annotations
from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.models.base_user import BaseUser
from typing import ClassVar
from pydantic import Field


class User(BaseUser, ActorModel):
    __tablename__: ClassVar[str] = 'users'
    __abstract__: ClassVar[bool] = False

    __ui__: ClassVar[dict] = {
        'icon': '👤',
        'renderer': {
            'item': 'ntx-item',
        },
    }

    image: str = Field(
        default='https://ui-avatars.com/api/?name=User&background=94a3b8&color=fff&size=128&rounded=true'
    )
