from __future__ import annotations
from typing import ClassVar, Literal, Optional
from pydantic import Field

from n3tx.core.models.actor_model import ActorModel
from n3tx.core.authorize import ANYONE, AUTHENTICATED, OWNER, ROLE
from n3tx.core.widgets import UrlField, DateField, CurrencyField, TextareaField
from models.user import User


class Grant(ActorModel):
    """A government grant discovered by an agent."""

    __tablename__: ClassVar[str] = 'grants'
    __storable__: ClassVar[bool] = True
    __protected_fields__: ClassVar[set] = {'user_owner'}
    __access__: ClassVar[dict] = {
        'read': ANYONE,
        'create': AUTHENTICATED,
        'update': AUTHENTICATED | ROLE('admin'),
        'delete': OWNER | ROLE('admin'),
    }

    title: str = Field(min_length=1, max_length=500)
    agency: str = Field(min_length=1, max_length=200)
    deadline: Optional[DateField] = Field(default=None, description="Application deadline")
    amount_min: Optional[CurrencyField] = Field(default=None, description="Minimum award amount")
    amount_max: Optional[CurrencyField] = Field(default=None, description="Maximum award amount")
    url: UrlField = Field(description="URL to the grant listing")
    description: TextareaField = Field(default='')
    status: Literal['discovered', 'reviewed', 'applied', 'expired'] = Field(default='discovered', description="Grant processing status")
    user_owner: User = Field(default=None, description="User who created this grant",
                             json_schema_extra={'access': {'view': 'authenticated', 'edit': 'owner'}})
