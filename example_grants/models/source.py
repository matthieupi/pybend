from __future__ import annotations
from typing import ClassVar
from pydantic import Field

from pybend.core.models.actor_model import ActorModel
from pybend.core.widgets import UrlField


class Source(ActorModel):
    """A grant listing source (website to scan)."""

    __tablename__: ClassVar[str] = 'sources'
    __storable__: ClassVar[bool] = True

    name: str = Field(min_length=1, max_length=200)
    url: UrlField = Field(description="URL to scan for grants")
    category: str = Field(default='government', description="government | foundation | corporate")
