"""Tests for api/routes_fastapi.py — Route helpers and factories."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from typing import ClassVar, Dict, Any

from pydantic import Field

from n3tx_core.api.routes_fastapi import import (
    _get_user, _build_context, _serialize, _resolve_user,
    register_route,
)
from n3tx_core.authorize.context import AccessContext
from n3tx_core.models.proto_model import ProtoModel
from n3tx_core.models.storable_mixin import StorableMixin

pytestmark = pytest.mark.unit



class TestGetUser:

    def test_extracts_user(self):
        request = MagicMock()
        request.state.user = {'user_id': 1, 'email': 'a@b.com', 'role': 'user'}
        result = _get_user(request)
        assert result['user_id'] == 1

    def test_no_user(self):
        request = MagicMock()
        request.state.user = None
        result = _get_user(request)
        assert result == {}

    def test_no_state(self):
        request = MagicMock()
        request.state = MagicMock()
        # getattr(request.state, 'user', {}) returns {} when user not set
        request.state.user = None
        result = _get_user(request)
        assert result == {}

    def test_empty_user(self):
        request = MagicMock()
        request.state.user = {}
        result = _get_user(request)
        assert result == {}


class TestBuildContext:

    def test_returns_access_context(self):
        request = MagicMock()
        request.state.user = {'user_id': 1, 'role': 'user'}
        model_class = MagicMock()
        ctx = _build_context(request, model_class, 'read')
        assert isinstance(ctx, AccessContext)

    def test_sets_action(self):
        request = MagicMock()
        request.state.user = {'user_id': 1}
        ctx = _build_context(request, MagicMock(), 'create')
        assert ctx.action == 'create'

    def test_sets_resource(self):
        request = MagicMock()
        request.state.user = {'user_id': 1}
        resource = MagicMock()
        ctx = _build_context(request, MagicMock(), 'read', resource=resource)
        assert ctx.resource is resource

    def test_sets_parent_id(self):
        request = MagicMock()
        request.state.user = {'user_id': 1}
        ctx = _build_context(request, MagicMock(), 'read', parent_id=42)
        assert ctx.parent_id == 42


class TestSerialize:

    def test_basic_serialize(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'ser_t1'
            name: str = Field(default='test')
        m = M(id=1, name='hello')
        data = _serialize(m)
        assert '$schema' in data
        assert '$id' in data
        assert data['name'] == 'hello'

    def test_with_populated(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'ser_t2'
            name: str = Field(default='')
        m = M(id=1, name='test')
        m.__dict__['_populated'] = {'comments': {'data': [], 'meta': {}}}
        data = _serialize(m)
        assert 'comments' in data
        assert data['comments']['data'] == []

    def test_no_populated(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'ser_t3'
            name: str = Field(default='')
        m = M(id=1, name='test')
        data = _serialize(m)
        assert 'comments' not in data


class TestResolveUser:

    def test_storable_type_fetches(self):
        class MockUser(ProtoModel):
            __tablename__: ClassVar[str] = 'resolve_users'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        MockUser.storage = MagicMock()
        MockUser.storage.get.return_value = MockUser(id=1, name='found')

        request = MagicMock()
        request.state.user = {'user_id': 1, 'role': 'user'}
        result = _resolve_user(MockUser, request)
        assert result.name == 'found'

    def test_dict_type_returns_raw(self):
        request = MagicMock()
        request.state.user = {'user_id': 1, 'role': 'user', 'email': 'a@b.com'}
        result = _resolve_user(dict, request)
        assert result['user_id'] == 1

    def test_no_user(self):
        request = MagicMock()
        request.state.user = {}
        result = _resolve_user(dict, request)
        assert result is None

    def test_none_user(self):
        request = MagicMock()
        request.state.user = None
        result = _resolve_user(dict, request)
        assert result is None


class TestRegisterRoute:

    def test_get(self):
        with patch('n3tx_core.api.routes_fastapi.router') as mock_router:
            def handler():
                pass
            register_route('/test', handler, method='GET')
            mock_router.get.assert_called_once_with('/test')

    def test_post(self):
        with patch('n3tx_core.api.routes_fastapi.router') as mock_router:
            def handler():
                pass
            register_route('/test', handler, method='POST')
            mock_router.post.assert_called_once_with('/test')

    def test_put(self):
        with patch('n3tx_core.api.routes_fastapi.router') as mock_router:
            def handler():
                pass
            register_route('/test', handler, method='PUT')
            mock_router.put.assert_called_once_with('/test')

    def test_delete(self):
        with patch('n3tx_core.api.routes_fastapi.router') as mock_router:
            def handler():
                pass
            register_route('/test', handler, method='DELETE')
            mock_router.delete.assert_called_once_with('/test')

    def test_unsupported_raises(self):
        with pytest.raises(ValueError, match="Unsupported HTTP method"):
            register_route('/test', lambda: None, method='PATCH')
