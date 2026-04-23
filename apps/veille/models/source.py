from __future__ import annotations
from typing import ClassVar, Optional

from pydantic import Field

from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.authorize import AUTHENTICATED, ROLE
from n3tx_core.utils.decorators import expose_route
from n3tx_core.widgets import TextareaField
from models.web_tools import _fetch_http_content, _fetch_js_content, _persist_source_scrape


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
        'icon': 'veille-source',
        'field_order': [
            'name', 'url', 'description', 'language',
            'scraping_notes', 'agent_discovered', 'active',
            'last_scraped', 'scrape_changed', 'content_updated_at',
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

    # Scrape tracking
    last_scraped: Optional[str] = Field(default=None)
    scraped_content: TextareaField = Field(default='',
                                           json_schema_extra={'ui': {'display': False}})
    scraped_content_hash: Optional[str] = Field(default=None,
                                                json_schema_extra={'ui': {'display': False}})
    previous_content_hash: Optional[str] = Field(default=None,
                                                 json_schema_extra={'ui': {'display': False}})
    scrape_status: Optional[int] = Field(default=None,
                                         json_schema_extra={'ui': {'display': False}})
    scrape_method: Optional[str] = Field(default=None,
                                         json_schema_extra={'ui': {'display': False}})
    scraped_final_url: Optional[str] = Field(default=None,
                                             json_schema_extra={'ui': {'display': False}})
    scrape_changed: bool = Field(default=False)
    content_updated_at: Optional[str] = Field(default=None)
    last_scrape_error: TextareaField = Field(default='',
                                             json_schema_extra={'ui': {'display': False}})

    @expose_route('/fetch', methods=['POST'], access=AUTHENTICATED)
    async def fetch(self, use_js: bool = False, user=None) -> dict:
        """Refresh this source and persist the latest scraped content."""

        scrape = await (_fetch_js_content(self.url) if use_js else _fetch_http_content(self.url))
        return _persist_source_scrape(self.id, scrape)
