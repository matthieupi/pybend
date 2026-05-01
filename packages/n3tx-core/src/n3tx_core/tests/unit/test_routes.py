"""Tests for api/routes_fastapi.py — Route helpers and factories."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from typing import ClassVar, Dict, Any

from pydantic import Field
from fastapi import APIRouter
from fastapi.testclient import TestClient

import n3tx_core.api.routes_fastapi as routes_fastapi
from n3tx_core.app import create_app
from n3tx_core.api.routes_fastapi import (
    _get_user, _build_context, _serialize, _resolve_user,
    _resolve_custom_return_type, register_route,
)
from n3tx_core.authorize import ANYONE
from n3tx_core.authorize.context import AccessContext
from n3tx_core.models.proto_model import ProtoModel
from n3tx_core.models.storable_mixin import StorableMixin
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_core.utils.registrar import registered_models

pytestmark = pytest.mark.unit


class ReturnParent(ProtoModel):
    __tablename__: ClassVar[str] = 'return_parent'
    name: str = Field(default='')


class ReturnChild(ProtoModel):
    __tablename__: ClassVar[str] = 'return_child'
    name: str = Field(default='')


def custom_returns_child(self) -> 'ReturnChild':
    return ReturnChild(name='ok')


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


class TestResolveCustomReturnType:

    def test_resolves_future_annotation_to_different_model(self):
        assert _resolve_custom_return_type(custom_returns_child, ReturnParent) is ReturnChild


class TestRegisterRoutesViewDelegation:

    def test_register_routes_delegates_view_routes_without_ui_import(self, monkeypatch):
        calls = []

        class DelegatedViewModel(ProtoModel):
            __tablename__: ClassVar[str] = 'delegated_view_models'

            @classmethod
            def register_view_routes(cls, router, *, tag: str):
                calls.append((cls, tag))

        test_router = APIRouter()
        saved = dict(registered_models)
        registered_models.clear()
        registered_models['delegated_view_models'] = DelegatedViewModel
        monkeypatch.setattr(routes_fastapi, 'router', test_router)
        try:
            routes_fastapi.register_routes()
        finally:
            registered_models.clear()
            registered_models.update(saved)

        assert calls == [(DelegatedViewModel, 'delegated_view_models'.capitalize())]


class TestClassNameReadMirror:

    def test_class_name_read_mirror_matches_table_name_read(self, tmp_path):
        saved = dict(registered_models)
        registered_models.clear()
        try:
            class MirrorProduct(ProtoModel):
                __tablename__: ClassVar[str] = 'mirror_products'
                __storable__: ClassVar[bool] = True
                __access__: ClassVar[dict] = {'read': ANYONE}
                name: str = Field(default='')

            app = create_app(
                models=[MirrorProduct],
                storage=SQLiteStorage(str(tmp_path / 'mirror.db')),
                static_dir=None,
            )
            created = MirrorProduct.create(MirrorProduct(name='Widget'))
            client = TestClient(app)

            table_response = client.get(f'/mirror_products/{created.id}')
            class_response = client.get(f'/MirrorProduct/{created.id}')

            assert table_response.status_code == 200
            assert class_response.status_code == 200
            assert class_response.json() == table_response.json()
            assert class_response.json()['$schema'].endswith('/MirrorProduct')
            assert class_response.json()['$id'].endswith(f'/mirror_products/{created.id}')
        finally:
            registered_models.clear()
            registered_models.update(saved)

    def test_class_name_read_mirror_preserves_not_found_and_is_get_only(self, tmp_path):
        saved = dict(registered_models)
        registered_models.clear()
        try:
            class MirrorNotFoundProduct(ProtoModel):
                __tablename__: ClassVar[str] = 'mirror_not_found_products'
                __storable__: ClassVar[bool] = True
                name: str = Field(default='')

            app = create_app(
                models=[MirrorNotFoundProduct],
                storage=SQLiteStorage(str(tmp_path / 'mirror_not_found.db')),
                static_dir=None,
            )
            client = TestClient(app)

            table_response = client.get('/mirror_not_found_products/999999')
            class_response = client.get('/MirrorNotFoundProduct/999999')
            assert class_response.status_code == table_response.status_code == 404
            assert class_response.json() == table_response.json()

            assert client.post('/MirrorNotFoundProduct/1', json={'name': 'Nope'}).status_code == 405
            assert client.put('/MirrorNotFoundProduct/1', json={'name': 'Nope'}).status_code == 405
            assert client.delete('/MirrorNotFoundProduct/1').status_code == 405
        finally:
            registered_models.clear()
            registered_models.update(saved)

    def test_non_storable_model_does_not_get_class_name_read_mirror(self, tmp_path):
        saved = dict(registered_models)
        registered_models.clear()
        try:
            class NonStorableMirror(ProtoModel):
                __tablename__: ClassVar[str] = 'non_storable_mirrors'
                name: str = Field(default='')

            app = create_app(
                models=[NonStorableMirror],
                storage=SQLiteStorage(str(tmp_path / 'non_storable.db')),
                static_dir=None,
            )
            client = TestClient(app)

            assert client.get('/NonStorableMirror').status_code == 200
            assert client.get('/NonStorableMirror/1').status_code == 404
        finally:
            registered_models.clear()
            registered_models.update(saved)
