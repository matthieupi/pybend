"""
Tests for agent tool call auth in the Veille app.

Bug: Run.execute() calls agentic_stream() without passing user context,
so all agent tool calls to @expose_route(access=AUTHENTICATED) methods
(like WebTools.scrape) get "Access denied".

Fix: Propagate the originating user through the agent pipeline so every
tool call carries real identity for auth and future usage tracking.
"""

import sys
import os
import json
import pytest
from typing import ClassVar

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pydantic import Field

from n3tx_actors.actor import Actor
from n3tx_actors.matrix import Matrix
from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.utils.decorators import expose_route
from n3tx_core.authorize import AUTHENTICATED
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_core.utils.registrar import register_model, registered_models
from n3tx_agents.tools import _route_tool_call
from n3tx_agents.deps import AgentDeps


@pytest.fixture(autouse=True)
def reset_state():
    saved_matrix = Actor.__matrix__
    saved_children = Actor.__children__.copy()
    saved_matrix_children = Matrix.__children__.copy()
    saved_models = dict(registered_models)

    Actor.__matrix__ = None
    Actor.__children__ = {}
    Matrix.__children__ = {}
    registered_models.clear()

    yield

    Actor.__matrix__ = saved_matrix
    Actor.__children__ = saved_children
    Matrix.__children__ = saved_matrix_children
    registered_models.clear()
    registered_models.update(saved_models)


@pytest.fixture
def fresh_matrix():
    return Matrix()


class MockCtx:
    def __init__(self, user=None):
        self.deps = AgentDeps(user=user, agent_addr='runs')


class TestVeilleScraperAuth:
    """Reproduce the Veille bug: agent scraper gets Access denied on all sources."""

    @pytest.mark.asyncio
    async def test_scraper_tool_call_without_user_gets_access_denied(self, fresh_matrix):
        """Reproduce the exact bug: WebTools.scrape with access=AUTHENTICATED
        called via internal TX (no user) returns Access denied.

        This mirrors Run.execute() → agentic_stream() → _route_tool_call()
        with no user propagated.
        """
        class WebTools(ActorModel):
            __tablename__: ClassVar[str] = 'web_tools'
            __storable__: ClassVar[bool] = False

            @expose_route('/scrape', methods=['POST'], access=AUTHENTICATED)
            def scrape(url: str) -> dict:
                return {'url': url, 'status': 200, 'text': 'scraped content'}

        ctx = MockCtx(user=None)
        result = await _route_tool_call(ctx, 'web_tools', 'scrape', {'url': 'https://grants.example.com'})

        data = json.loads(result)
        assert 'url' in data, f"Expected scrape result but got: {data}"
        assert data['url'] == 'https://grants.example.com'

    @pytest.mark.asyncio
    async def test_scraper_tool_call_with_user_succeeds(self, fresh_matrix):
        """When the user IS propagated, the scrape tool call works.

        This is the post-fix scenario: execute(user=X) → agentic_stream(user=X)
        → AgentDeps(user=X) → _route_tool_call(meta={'user': X}).
        """
        class WebTools(ActorModel):
            __tablename__: ClassVar[str] = 'web_tools'
            __storable__: ClassVar[bool] = False

            @expose_route('/scrape', methods=['POST'], access=AUTHENTICATED)
            def scrape(url: str) -> dict:
                return {'url': url, 'status': 200, 'text': 'scraped content'}

        ctx = MockCtx(user={'user_id': 1, 'role': 'user', 'email': 'alice@example.com'})
        result = await _route_tool_call(ctx, 'web_tools', 'scrape', {'url': 'https://grants.example.com'})

        data = json.loads(result)
        assert data['url'] == 'https://grants.example.com'
        assert data['text'] == 'scraped content'

    @pytest.mark.asyncio
    async def test_check_duplicate_with_user_succeeds(self, fresh_matrix, tmp_path):
        """WebTools.check_duplicate also needs user context to pass auth."""
        storage = SQLiteStorage(str(tmp_path / 'test.db'))

        class Grant(ActorModel):
            __tablename__: ClassVar[str] = 'grants'
            __storable__: ClassVar[bool] = True
            __access__: ClassVar[dict] = {'read': AUTHENTICATED, 'create': AUTHENTICATED}
            title: str = Field(default='')
            url: str = Field(default='')

        register_model(Grant, storage=storage)

        class WebTools(ActorModel):
            __tablename__: ClassVar[str] = 'web_tools'
            __storable__: ClassVar[bool] = False

            @expose_route('/check_duplicate', methods=['POST'], access=AUTHENTICATED)
            def check_duplicate(url: str, title: str = '') -> dict:
                return {'duplicate': False}

        ctx = MockCtx(user={'user_id': 1, 'role': 'user'})
        result = await _route_tool_call(ctx, 'web_tools', 'check_duplicate', {
            'url': 'https://example.com/grant', 'title': 'Test',
        })

        data = json.loads(result)
        assert 'duplicate' in data, f"Expected check_duplicate result but got: {data}"

    @pytest.mark.asyncio
    async def test_grants_crud_with_user_succeeds(self, fresh_matrix, tmp_path):
        """CRUD operations with user context work correctly."""
        storage = SQLiteStorage(str(tmp_path / 'test.db'))

        class Grant(ActorModel):
            __tablename__: ClassVar[str] = 'grants'
            __storable__: ClassVar[bool] = True
            __access__: ClassVar[dict] = {
                'read': AUTHENTICATED,
                'create': AUTHENTICATED,
                'update': AUTHENTICATED,
            }
            title: str = Field(min_length=1, max_length=500)
            funder: str = Field(default='')
            url: str = Field(default='')

        register_model(Grant, storage=storage)

        ctx = MockCtx(user={'user_id': 1, 'role': 'user'})
        result = await _route_tool_call(ctx, 'grants', 'create', {
            'title': 'Test Grant', 'funder': 'Test Funder',
            'url': 'https://example.com/grant',
        })

        data = json.loads(result)
        assert data.get('title') == 'Test Grant'
