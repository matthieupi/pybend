"""
Tests for agent tool calls to @expose_route methods with access control.

Bug: When the agent makes tool calls via _route_tool_call with no user context
(deps.user=None), custom @expose_route methods with access=AUTHENTICATED
return "Access denied" via ModelRetry.

Fix: Two changes needed:
1. _route_tool_call should always set meta={'user': ctx.deps.user} so
   internal TX has user=None (not missing key), enabling consistent handling.
2. handler() Tier 2 auth should treat user=None as internal (matching _authorize()).
"""

import json
import pytest
from typing import ClassVar

from pydantic import Field

from n3tx_actors.actor import Actor
from n3tx_actors.matrix import Matrix
from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.utils.decorators import expose_route
from n3tx_core.authorize import AUTHENTICATED
from n3tx_core.utils.registrar import register_model
from n3tx_agents.tools import _route_tool_call
from n3tx_agents.agent import AgentDeps

pytestmark = pytest.mark.unit


class MockCtx:
    """Minimal RunContext mock for _route_tool_call."""
    def __init__(self, user=None):
        self.deps = AgentDeps(user=user, agent_addr='test_agent')


class TestToolCallToAuthenticatedMethod:
    """_route_tool_call to @expose_route(access=AUTHENTICATED) with and without user."""

    @pytest.mark.asyncio
    async def test_tool_call_no_user_to_authenticated_method_succeeds(self, fresh_matrix):
        """Agent tool call (no user) to an AUTHENTICATED method should succeed.

        This is the core bug: the agent's scrape tool call gets 'Access denied'
        because the handler treats empty/missing user as external unauthenticated.
        """

        class ToolActor(ActorModel):
            __tablename__ = 'tool_actor'
            __storable__ = False

            @expose_route('/fetch', methods=['POST'], access=AUTHENTICATED)
            def fetch(url: str) -> dict:
                """Class-level method with AUTHENTICATED access."""
                return {'url': url, 'content': 'fetched'}

        ctx = MockCtx(user=None)
        result = await _route_tool_call(ctx, 'tool_actor', 'fetch', {'url': 'https://example.com'})

        data = json.loads(result)
        assert 'url' in data
        assert data['url'] == 'https://example.com'

    @pytest.mark.asyncio
    async def test_tool_call_with_user_to_authenticated_method_succeeds(self, fresh_matrix):
        """Agent tool call WITH user to an AUTHENTICATED method should succeed."""

        class ToolActor(ActorModel):
            __tablename__ = 'tool_actor'
            __storable__ = False

            @expose_route('/fetch', methods=['POST'], access=AUTHENTICATED)
            def fetch(url: str) -> dict:
                return {'url': url, 'content': 'fetched'}

        ctx = MockCtx(user={'user_id': 1, 'role': 'user'})
        result = await _route_tool_call(ctx, 'tool_actor', 'fetch', {'url': 'https://example.com'})

        data = json.loads(result)
        assert data['url'] == 'https://example.com'

    @pytest.mark.asyncio
    async def test_tool_call_no_user_to_crud_succeeds(self, fresh_matrix, tmp_path):
        """Agent tool call (no user) to CRUD operations should succeed.

        CRUD uses _authorize() which correctly handles internal messages.
        """
        from n3tx_core.storage.sqlite_storage import SQLiteStorage
        storage = SQLiteStorage(str(tmp_path / 'test.db'))

        class CrudActor(ActorModel):
            __tablename__ = 'crud_actor'
            __storable__ = True
            __access__: ClassVar[dict] = {
                'read': AUTHENTICATED,
                'create': AUTHENTICATED,
            }
            name: str = Field(default='test')

        register_model(CrudActor, storage=storage)

        ctx = MockCtx(user=None)
        result = await _route_tool_call(ctx, 'crud_actor', 'list', {})

        data = json.loads(result)
        assert isinstance(data, (list, dict))
        if isinstance(data, dict):
            assert 'data' in data

    @pytest.mark.asyncio
    async def test_tool_call_always_includes_user_in_meta(self, fresh_matrix):
        """_route_tool_call should always include 'user' key in TX meta,
        even when user is None. This makes internal vs external distinction
        explicit and enables future per-user tracking."""
        from n3tx_actors.tx import TX
        from unittest.mock import AsyncMock, patch

        class ToolActor(ActorModel):
            __tablename__ = 'tool_actor'
            __storable__ = False

            @expose_route('/fetch', methods=['POST'], access=AUTHENTICATED)
            def fetch(url: str) -> dict:
                return {'url': url}

        ctx = MockCtx(user=None)

        # Capture the TX sent through root.request
        captured_tx = []
        original_request = Actor.root().request

        async def spy_request(tx, **kwargs):
            captured_tx.append(tx)
            return await original_request(tx, **kwargs)

        root = Actor.root()
        object.__setattr__(root, 'request', spy_request)
        try:
            await _route_tool_call(ctx, 'tool_actor', 'fetch', {'url': 'https://example.com'})
        except Exception:
            pass  # May fail due to auth — that's OK, we just want to inspect the TX
        finally:
            object.__delattr__(root, 'request')

        assert len(captured_tx) == 1
        # 'user' key should always be present in meta
        assert 'user' in captured_tx[0].meta, \
            f"Expected 'user' key in meta but got: {captured_tx[0].meta}"
