from __future__ import annotations
from typing import ClassVar, Optional
from pydantic import Field
from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.authorize import AUTHENTICATED, ROLE
from n3tx_core.widgets import TextareaField


class Source(ActorModel):
    __tablename__: ClassVar[str] = 'sources'
    __storable__: ClassVar[bool] = True
    __access__: ClassVar[dict] = {
        'read': AUTHENTICATED,
        'create': AUTHENTICATED,
        'update': AUTHENTICATED,
        'delete': ROLE('admin'),
    }
    __ui__: ClassVar[dict] = {
        'icon': '📰',
        'field_order': [
            'name', 'url', 'description', 'language',
            'scraping_notes', 'agent_discovered', 'active',
        ],
    }

    name: str = Field(min_length=1, max_length=300,
                      json_schema_extra={'ui': {'placeholder': 'Source name...'}})
    url: str = Field(min_length=1,
                     json_schema_extra={'ui': {'placeholder': 'https://...'}})
    description: TextareaField = Field(default='')
    language: str = Field(default='en')
    scraping_notes: TextareaField = Field(default='',
                                          json_schema_extra={'ui': {'placeholder': 'Hints for the scraping agent...'}})
    agent_discovered: bool = Field(default=False)
    active: bool = Field(default=True)
    last_scraped: Optional[str] = Field(default=None)
