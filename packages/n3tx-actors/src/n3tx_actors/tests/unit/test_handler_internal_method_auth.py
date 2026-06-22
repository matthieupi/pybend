"""
Tests for Tier 2 auth on @expose_route methods in handler().

Bug: When an agent makes tool calls via internal TX, custom @expose_route
methods with access=AUTHENTICATED return "Access denied". The handler's
custom method auth path uses tx.meta.get('user', {}) which returns {}
(empty dict, not None) for internal TX, so AUTHENTICATED.evaluate({}) fails.

Two fixes needed:
1. Handler should treat user=None (internal message) the same way _authorize()
   does: pass through without auth check.
2. Agent callers should propagate the originating user's auth context through
   the pipeline so tool calls carry real identity for tracking/auditing.
"""

import pytest
import asyncio
from typing import ClassVar

from pydantic import Field

from n3tx_actors.models.actor_model import ActorModel
from n3tx_actors.tx import TX
from n3tx_actors.actor import Actor
from n3tx_actors.matrix import Matrix
from n3tx_core.utils.descriptors import fullmethod
from n3tx_core.utils.decorators import expose_route
from n3tx_core.authorize import AUTHENTICATED, OWNER, ROLE, Where

pytestmark = pytest.mark.unit


# ===================================================================
# Test model — @expose_route methods with access control
# ===================================================================

class _AuthMethodModel(ActorModel, auto_register=False):
    __tablename__: ClassVar[str] = 'auth_method_test'
    name: str = Field(default='')

    @expose_route('/scrape', methods=['POST'], access=AUTHENTICATED)
    def scrape(url: str) -> dict:
        """A class-level method requiring authentication (like WebTools.scrape)."""
        return {'url': url, 'text': 'scraped content'}

    @expose_route('/admin_op', methods=['POST'], access=ROLE('admin'))
    def admin_op(action: str) -> dict:
        """A class-level method requiring admin role."""
        return {'action': action, 'done': True}


class _OwnedMethodModel(ActorModel, auto_register=False):
    __tablename__: ClassVar[str] = 'owned_method_test'
    __owner_field__: ClassVar[str] = 'user_owner'
    __access__: ClassVar[dict] = {'read': OWNER | ROLE('admin')}

    name: str = Field(default='')
    secret: str = Field(default='')
    status: str = Field(default='draft')
    user_owner: int | None = None
    executed: ClassVar[bool] = False

    @expose_route('/reveal', methods=['GET'], access=OWNER | ROLE('admin'))
    def reveal(self) -> dict:
        """Instance method guarded by resource ownership."""
        type(self).executed = True
        return {'secret': self.secret}

    @expose_route('/draft-secret', methods=['GET'], access=OWNER & Where(status='draft'))
    def draft_secret(self) -> dict:
        """Instance method guarded by ownership and a resource attribute."""
        type(self).executed = True
        return {'secret': self.secret, 'status': self.status}


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture(autouse=True)
def reset_actor_state():
    saved_matrix = Actor.__matrix__
    saved_actor_children = Actor.__children__.copy()
    saved_matrix_children = Matrix.__children__.copy()
    saved_handler_children = _AuthMethodModel.__children__.copy()
    saved_owned_children = _OwnedMethodModel.__children__.copy()
    yield
    Actor.__matrix__ = saved_matrix
    Actor.__children__ = saved_actor_children
    Matrix.__children__ = saved_matrix_children
    _AuthMethodModel.__children__ = saved_handler_children
    _OwnedMethodModel.__children__ = saved_owned_children
    _OwnedMethodModel.executed = False


@pytest.fixture
def capture_send():
    """Replace send with a capturing mock, restore after test."""
    sent = []

    @fullmethod
    async def mock_send(target, tx):
        sent.append(tx)

    original = _AuthMethodModel.__dict__.get('send')
    type.__setattr__(_AuthMethodModel, 'send', mock_send)
    yield sent
    if original:
        type.__setattr__(_AuthMethodModel, 'send', original)
    else:
        type.__delattr__(_AuthMethodModel, 'send')


@pytest.fixture
def capture_owned_send():
    """Replace owned-model send with a capturing mock, restore after test."""
    sent = []

    @fullmethod
    async def mock_send(target, tx):
        sent.append(tx)

    original = _OwnedMethodModel.__dict__.get('send')
    type.__setattr__(_OwnedMethodModel, 'send', mock_send)
    yield sent
    if original:
        type.__setattr__(_OwnedMethodModel, 'send', original)
    else:
        type.__delattr__(_OwnedMethodModel, 'send')


# ===================================================================
# Test: Internal TX to @expose_route(access=AUTHENTICATED) should pass
# ===================================================================

class TestInternalTxCustomMethodAuth:
    """Internal TX (no user in meta) should bypass auth on custom methods,
    consistent with _authorize() for CRUD operations."""

    @pytest.mark.asyncio
    async def test_internal_tx_to_authenticated_method_passes(self, capture_send):
        """An internal TX (empty meta, no user key) calling an @expose_route
        method with access=AUTHENTICATED should succeed.

        This reproduces the agent tool call bug: when the agent calls
        web_tools_scrape via internal TX, it gets 'Access denied' because
        the handler treats missing user key as unauthenticated.
        """
        tx = TX(
            name='scrape',
            source='matrix',
            target='auth_method_test',
            data={'url': 'https://example.com'},
            meta={},  # Internal: no 'user' key
        )
        await _AuthMethodModel.handler(tx)

        assert len(capture_send) == 1
        reply = capture_send[0]
        assert not reply.is_error, f"Expected success but got error: {reply.data}"
        assert reply.data.get('url') == 'https://example.com'

    @pytest.mark.asyncio
    async def test_internal_tx_no_meta_to_authenticated_method_passes(self, capture_send):
        """TX with no meta at all (default empty dict) should also pass."""
        tx = TX(
            name='scrape',
            source='matrix',
            target='auth_method_test',
            data={'url': 'https://example.com'},
        )
        await _AuthMethodModel.handler(tx)

        assert len(capture_send) == 1
        reply = capture_send[0]
        assert not reply.is_error, f"Expected success but got error: {reply.data}"

    @pytest.mark.asyncio
    async def test_internal_tx_to_role_restricted_method_passes(self, capture_send):
        """Internal TX to a ROLE('admin') method should also pass through."""
        tx = TX(
            name='admin_op',
            source='internal_actor',
            target='auth_method_test',
            data={'action': 'rebuild'},
            meta={},
        )
        await _AuthMethodModel.handler(tx)

        assert len(capture_send) == 1
        reply = capture_send[0]
        assert not reply.is_error, f"Expected success but got error: {reply.data}"
        assert reply.data.get('action') == 'rebuild'

    @pytest.mark.asyncio
    async def test_external_tx_without_auth_still_denied(self, capture_send):
        """TX with explicit user={} (external unauthenticated) should still be denied.

        An external request has meta={'user': {}} (empty user dict, explicitly
        set by NetworkAPI). That's different from internal (no 'user' key).
        """
        tx = TX(
            name='scrape',
            source='api',
            target='auth_method_test',
            data={'url': 'https://example.com'},
            meta={'user': {}},  # External: explicit empty user
        )
        await _AuthMethodModel.handler(tx)

        assert len(capture_send) == 1
        reply = capture_send[0]
        assert reply.is_error
        assert reply.data.get('code') == 403

    @pytest.mark.asyncio
    async def test_authenticated_external_tx_passes(self, capture_send):
        """TX with valid user should pass auth as before."""
        tx = TX(
            name='scrape',
            source='api',
            target='auth_method_test',
            data={'url': 'https://example.com'},
            meta={'user': {'user_id': 1, 'role': 'user'}},
        )
        await _AuthMethodModel.handler(tx)

        assert len(capture_send) == 1
        reply = capture_send[0]
        assert not reply.is_error
        assert reply.data.get('url') == 'https://example.com'


class TestInstanceCustomMethodResourceAuth:
    """Instance @expose_route access must evaluate against the target resource."""

    @pytest.fixture
    def owned_doc(self):
        return _OwnedMethodModel(id=7, name='Plan', secret='classified', user_owner=10)

    @pytest.mark.asyncio
    async def test_owner_can_call_owner_guarded_instance_method(
        self, capture_owned_send, monkeypatch, owned_doc,
    ):
        monkeypatch.setattr(_OwnedMethodModel, 'get', classmethod(lambda cls, id: owned_doc), raising=False)

        tx = TX(
            name='reveal',
            source='api',
            target='owned_method_test',
            data={'id': owned_doc.id},
            meta={'user': {'user_id': 10, 'role': 'user'}},
        )
        await _OwnedMethodModel.handler(tx)

        assert len(capture_owned_send) == 1
        reply = capture_owned_send[0]
        assert not reply.is_error, reply.data
        assert reply.data == {'secret': 'classified'}
        assert _OwnedMethodModel.executed is True

    @pytest.mark.asyncio
    async def test_admin_can_call_owner_or_admin_guarded_instance_method(
        self, capture_owned_send, monkeypatch, owned_doc,
    ):
        monkeypatch.setattr(_OwnedMethodModel, 'get', classmethod(lambda cls, id: owned_doc), raising=False)

        tx = TX(
            name='reveal',
            source='api',
            target='owned_method_test',
            data={'id': owned_doc.id},
            meta={'user': {'user_id': 99, 'role': 'admin'}},
        )
        await _OwnedMethodModel.handler(tx)

        assert len(capture_owned_send) == 1
        reply = capture_owned_send[0]
        assert not reply.is_error, reply.data
        assert reply.data == {'secret': 'classified'}
        assert _OwnedMethodModel.executed is True

    @pytest.mark.asyncio
    async def test_authenticated_non_owner_is_denied_before_method_execution(
        self, capture_owned_send, monkeypatch, owned_doc,
    ):
        monkeypatch.setattr(_OwnedMethodModel, 'get', classmethod(lambda cls, id: owned_doc), raising=False)

        tx = TX(
            name='reveal',
            source='api',
            target='owned_method_test',
            data={'id': owned_doc.id},
            meta={'user': {'user_id': 20, 'role': 'user'}},
        )
        await _OwnedMethodModel.handler(tx)

        assert len(capture_owned_send) == 1
        reply = capture_owned_send[0]
        assert reply.is_error
        assert reply.data.get('code') == 403
        assert _OwnedMethodModel.executed is False

    @pytest.mark.asyncio
    async def test_missing_instance_returns_404_before_method_execution(
        self, capture_owned_send, monkeypatch,
    ):
        monkeypatch.setattr(_OwnedMethodModel, 'get', classmethod(lambda cls, id: None), raising=False)

        tx = TX(
            name='reveal',
            source='api',
            target='owned_method_test',
            data={'id': 999},
            meta={'user': {'user_id': 10, 'role': 'user'}},
        )
        await _OwnedMethodModel.handler(tx)

        assert len(capture_owned_send) == 1
        reply = capture_owned_send[0]
        assert reply.is_error
        assert reply.data.get('code') == 404
        assert _OwnedMethodModel.executed is False

    @pytest.mark.asyncio
    async def test_resource_where_rule_is_denied_before_method_execution(
        self, capture_owned_send, monkeypatch,
    ):
        published_doc = _OwnedMethodModel(
            id=8,
            name='Published',
            secret='not-a-draft',
            status='published',
            user_owner=10,
        )
        monkeypatch.setattr(_OwnedMethodModel, 'get', classmethod(lambda cls, id: published_doc), raising=False)

        tx = TX(
            name='draft_secret',
            source='api',
            target='owned_method_test',
            data={'id': published_doc.id},
            meta={'user': {'user_id': 10, 'role': 'user'}},
        )
        await _OwnedMethodModel.handler(tx)

        assert len(capture_owned_send) == 1
        reply = capture_owned_send[0]
        assert reply.is_error
        assert reply.data.get('code') == 403
        assert _OwnedMethodModel.executed is False
