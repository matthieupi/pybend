"""Tests for api/routes_fastapi.py — Route helpers and factories."""

import pytest
import asyncio
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
from n3tx_core.utils.decorators import expose_route
from n3tx_core.utils.erroring import MethodError
from n3tx_core.utils.registrar import registered_models, join_models


def _route_methods(app, path):
    methods = set()
    for route in app.routes:
        if getattr(route, 'path', None) == path:
            methods.update(getattr(route, 'methods', set()) or set())
    return methods

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


class TestClassNameCrudMirrors:

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
            assert class_response.json()['$id'].endswith(f'/MirrorProduct/{created.id}')
            assert '$href' not in class_response.json()
            assert 'links' not in class_response.json()
        finally:
            registered_models.clear()
            registered_models.update(saved)

    def test_class_name_collection_marker_matches_table_name_list(self, tmp_path):
        saved = dict(registered_models)
        registered_models.clear()
        try:
            class MirrorListProduct(ProtoModel):
                __tablename__: ClassVar[str] = 'mirror_list_products'
                __storable__: ClassVar[bool] = True
                __access__: ClassVar[dict] = {'read': ANYONE}
                name: str = Field(default='')

            app = create_app(
                models=[MirrorListProduct],
                storage=SQLiteStorage(str(tmp_path / 'mirror_list.db')),
                static_dir=None,
            )
            MirrorListProduct.create(MirrorListProduct(name='A'))
            MirrorListProduct.create(MirrorListProduct(name='B'))
            client = TestClient(app)

            table_response = client.get('/mirror_list_products')
            class_response = client.get('/MirrorListProduct/_')
            assert table_response.status_code == 200
            assert class_response.status_code == 200
            assert class_response.json() == table_response.json()
            assert class_response.json()[0]['$schema'].endswith('/MirrorListProduct')
            assert class_response.json()[0]['$id'].endswith('/MirrorListProduct/1')

            table_page = client.get('/mirror_list_products?limit=1&offset=0')
            class_page = client.get('/MirrorListProduct/_?limit=1&offset=0')
            assert class_page.status_code == 200
            assert class_page.json() == table_page.json()
            assert 'data' in class_page.json()
            assert class_page.json()['meta']['limit'] == 1
        finally:
            registered_models.clear()
            registered_models.update(saved)

    def test_class_name_create_update_delete_mirrors_table_routes(self, tmp_path):
        saved = dict(registered_models)
        registered_models.clear()
        try:
            class MirrorWriteProduct(ProtoModel):
                __tablename__: ClassVar[str] = 'mirror_write_products'
                __storable__: ClassVar[bool] = True
                __access__: ClassVar[dict] = {
                    'create': ANYONE,
                    'read': ANYONE,
                    'update': ANYONE,
                    'delete': ANYONE,
                }
                name: str = Field(default='')

            app = create_app(
                models=[MirrorWriteProduct],
                storage=SQLiteStorage(str(tmp_path / 'mirror_write.db')),
                static_dir=None,
            )
            client = TestClient(app)

            create_response = client.post('/MirrorWriteProduct', json={'name': 'Created'})
            assert create_response.status_code == 201
            created = create_response.json()
            assert created['name'] == 'Created'
            assert created['$schema'].endswith('/MirrorWriteProduct')
            assert created['$id'].endswith(f"/MirrorWriteProduct/{created['id']}")

            table_read = client.get(f"/mirror_write_products/{created['id']}")
            assert table_read.status_code == 200
            assert table_read.json() == created

            update_response = client.put(
                f"/MirrorWriteProduct/{created['id']}",
                json={'name': 'Updated'},
            )
            assert update_response.status_code == 200
            updated = update_response.json()
            assert updated['name'] == 'Updated'
            assert updated['$id'].endswith(f"/MirrorWriteProduct/{created['id']}")
            assert client.get(f"/mirror_write_products/{created['id']}").json()['name'] == 'Updated'

            delete_response = client.delete(f"/MirrorWriteProduct/{created['id']}")
            assert delete_response.status_code == 200
            assert delete_response.json() == {'message': 'Deleted successfully'}
            assert client.get(f"/mirror_write_products/{created['id']}").status_code == 404
        finally:
            registered_models.clear()
            registered_models.update(saved)

    def test_class_name_method_mirror_matches_table_name_method(self, tmp_path):
        saved = dict(registered_models)
        registered_models.clear()
        try:
            class MirrorMethodProduct(ProtoModel):
                __tablename__: ClassVar[str] = 'mirror_method_products'
                __storable__: ClassVar[bool] = True
                __access__: ClassVar[dict] = {
                    'create': ANYONE,
                    'read': ANYONE,
                    'update': ANYONE,
                    'delete': ANYONE,
                }
                name: str = Field(default='')

                @expose_route('/rename', methods=['POST'], access=ANYONE)
                def rename(self, name: str) -> dict:
                    return {'id': self.id, 'name': name}

            app = create_app(
                models=[MirrorMethodProduct],
                storage=SQLiteStorage(str(tmp_path / 'mirror_method.db')),
                static_dir=None,
            )
            created = MirrorMethodProduct.create(MirrorMethodProduct(name='Old'))
            client = TestClient(app)

            table_response = client.post(
                f'/mirror_method_products/{created.id}/rename',
                json={'name': 'New'},
            )
            class_response = client.post(
                f'/MirrorMethodProduct/{created.id}/rename',
                json={'name': 'New'},
            )
            assert table_response.status_code == 200
            assert class_response.status_code == 200
            assert class_response.json() == table_response.json()
        finally:
            registered_models.clear()
            registered_models.update(saved)

    def test_class_name_method_mirror_preserves_validation_and_method_errors(self, tmp_path):
        saved = dict(registered_models)
        registered_models.clear()
        try:
            class MirrorMethodErrorProduct(ProtoModel):
                __tablename__: ClassVar[str] = 'mirror_method_error_products'
                __storable__: ClassVar[bool] = True
                __access__: ClassVar[dict] = {
                    'create': ANYONE,
                    'read': ANYONE,
                    'update': ANYONE,
                    'delete': ANYONE,
                }
                name: str = Field(default='')

                @expose_route('/rename', methods=['POST'], access=ANYONE)
                def rename(self, name: str) -> dict:
                    return {'id': self.id, 'name': name}

                @expose_route('/fail', methods=['POST'], access=ANYONE)
                def fail(self) -> dict:
                    raise MethodError('method failed', 409)

            app = create_app(
                models=[MirrorMethodErrorProduct],
                storage=SQLiteStorage(str(tmp_path / 'mirror_method_errors.db')),
                static_dir=None,
            )
            created = MirrorMethodErrorProduct.create(MirrorMethodErrorProduct(name='Old'))
            client = TestClient(app)

            table_missing = client.post(f'/mirror_method_error_products/{created.id}/rename', json={})
            class_missing = client.post(f'/MirrorMethodErrorProduct/{created.id}/rename', json={})
            assert class_missing.status_code == table_missing.status_code == 400
            assert class_missing.json() == table_missing.json()

            table_not_found = client.post('/mirror_method_error_products/999999/rename', json={'name': 'Nope'})
            class_not_found = client.post('/MirrorMethodErrorProduct/999999/rename', json={'name': 'Nope'})
            assert class_not_found.status_code == table_not_found.status_code == 404
            assert class_not_found.json() == table_not_found.json()

            table_error = client.post(f'/mirror_method_error_products/{created.id}/fail', json={})
            class_error = client.post(f'/MirrorMethodErrorProduct/{created.id}/fail', json={})
            assert class_error.status_code == table_error.status_code == 409
            assert class_error.json() == table_error.json() == {'detail': 'method failed'}
        finally:
            registered_models.clear()
            registered_models.update(saved)

    def test_class_name_method_mirror_supports_async_and_streaming_methods(self, tmp_path):
        saved = dict(registered_models)
        registered_models.clear()
        try:
            class MirrorAsyncMethodProduct(ProtoModel):
                __tablename__: ClassVar[str] = 'mirror_async_method_products'
                __storable__: ClassVar[bool] = True
                __access__: ClassVar[dict] = {
                    'create': ANYONE,
                    'read': ANYONE,
                    'update': ANYONE,
                    'delete': ANYONE,
                }
                name: str = Field(default='')

                @expose_route('/async_echo', methods=['POST'], access=ANYONE)
                async def async_echo(self, text: str) -> dict:
                    await asyncio.sleep(0)
                    return {'id': self.id, 'text': text}

                @expose_route('/stream_echo', methods=['POST'], access=ANYONE, stream=True)
                async def stream_echo(self, text: str):
                    yield {'chunk': text}

            app = create_app(
                models=[MirrorAsyncMethodProduct],
                storage=SQLiteStorage(str(tmp_path / 'mirror_async_methods.db')),
                static_dir=None,
            )
            created = MirrorAsyncMethodProduct.create(MirrorAsyncMethodProduct(name='Async'))
            client = TestClient(app)

            table_async = client.post(
                f'/mirror_async_method_products/{created.id}/async_echo',
                json={'text': 'hello'},
            )
            class_async = client.post(
                f'/MirrorAsyncMethodProduct/{created.id}/async_echo',
                json={'text': 'hello'},
            )
            assert class_async.status_code == table_async.status_code == 200
            assert class_async.json() == table_async.json() == {'id': created.id, 'text': 'hello'}

            class_stream = client.post(
                f'/MirrorAsyncMethodProduct/{created.id}/stream_echo',
                json={'text': 'streamed'},
            )
            assert class_stream.status_code == 200
            assert 'text/event-stream' in class_stream.headers['content-type']
            assert 'event: chunk' in class_stream.text
            assert '"chunk": "streamed"' in class_stream.text
            assert 'event: done' in class_stream.text
        finally:
            registered_models.clear()
            registered_models.update(saved)

    def test_class_name_method_mirror_supports_static_like_methods(self, tmp_path):
        saved = dict(registered_models)
        registered_models.clear()
        try:
            class MirrorStaticMethodProduct(ProtoModel):
                __tablename__: ClassVar[str] = 'mirror_static_method_products'
                __storable__: ClassVar[bool] = True
                __access__: ClassVar[dict] = {
                    'create': ANYONE,
                    'read': ANYONE,
                    'update': ANYONE,
                    'delete': ANYONE,
                }
                name: str = Field(default='')

                @staticmethod
                @expose_route('/summarize', methods=['POST'], access=ANYONE)
                def summarize(value: int) -> dict:
                    return {'value': value, 'doubled': value * 2}

            app = create_app(
                models=[MirrorStaticMethodProduct],
                storage=SQLiteStorage(str(tmp_path / 'mirror_static_methods.db')),
                static_dir=None,
            )
            client = TestClient(app)

            table_response = client.post('/mirror_static_method_products/summarize', json={'value': 7})
            class_response = client.post('/MirrorStaticMethodProduct/summarize', json={'value': 7})
            assert class_response.status_code == table_response.status_code == 200
            assert class_response.json() == table_response.json() == {'value': 7, 'doubled': 14}
        finally:
            registered_models.clear()
            registered_models.update(saved)

    def test_static_exposed_method_schema_reports_static_scope(self):
        class MirrorStaticScopeProduct(ProtoModel):
            __tablename__: ClassVar[str] = 'mirror_static_scope_products'

            @staticmethod
            @expose_route('/summarize', methods=['POST'], access=ANYONE, stream=True)
            async def summarize(value: int):
                yield {'value': value}

        method = MirrorStaticScopeProduct.schema()['methods']['summarize']

        assert method['route'] == '/summarize'
        assert method['scope'] == 'staticmethod'
        assert method['stream'] is True

    def test_class_exposed_method_schema_and_routes_are_collection_scoped(self, tmp_path):
        saved = dict(registered_models)
        registered_models.clear()
        try:
            class MirrorClassMethodProduct(ProtoModel):
                __tablename__: ClassVar[str] = 'mirror_class_method_products'
                __storable__: ClassVar[bool] = True
                __access__: ClassVar[dict] = {
                    'create': ANYONE,
                    'read': ANYONE,
                    'update': ANYONE,
                    'delete': ANYONE,
                }
                name: str = Field(default='')

                @classmethod
                @expose_route('/summarize', methods=['POST'], access=ANYONE)
                def summarize(cls, value: int) -> dict:
                    return {'model': cls.__name__, 'value': value}

            method = MirrorClassMethodProduct.schema()['methods']['summarize']
            assert method['route'] == '/summarize'
            assert method['scope'] == 'classmethod'

            app = create_app(
                models=[MirrorClassMethodProduct],
                storage=SQLiteStorage(str(tmp_path / 'mirror_class_methods.db')),
                static_dir=None,
            )
            client = TestClient(app)

            table_response = client.post('/mirror_class_method_products/summarize', json={'value': 3})
            class_response = client.post('/MirrorClassMethodProduct/summarize', json={'value': 3})

            assert table_response.status_code == 200
            assert class_response.status_code == 200
            assert class_response.json() == table_response.json() == {
                'model': 'MirrorClassMethodProduct',
                'value': 3,
            }
            assert client.post('/MirrorClassMethodProduct/1/summarize', json={'value': 3}).status_code == 405
        finally:
            registered_models.clear()
            registered_models.update(saved)

    def test_actor_style_exposed_method_without_self_is_collection_scoped(self, tmp_path):
        saved = dict(registered_models)
        registered_models.clear()
        try:
            class MirrorActorMethodProduct(ProtoModel):
                __tablename__: ClassVar[str] = 'mirror_actor_method_products'
                __storable__: ClassVar[bool] = False
                __access__: ClassVar[dict] = {'run': ANYONE}

                @expose_route('/run-task', methods=['POST'], access=ANYONE)
                def run_task(value: int) -> dict:
                    return {'value': value, 'doubled': value * 2}

            method = MirrorActorMethodProduct.schema()['methods']['run_task']
            assert method['route'] == '/run-task'
            assert method['scope'] == 'actormethod'
            assert method['requires_instance'] is False

            app = create_app(
                models=[MirrorActorMethodProduct],
                storage=SQLiteStorage(str(tmp_path / 'mirror_actor_methods.db')),
                static_dir=None,
            )
            client = TestClient(app)

            table_response = client.post('/mirror_actor_method_products/run-task', json={'value': 4})
            class_response = client.post('/MirrorActorMethodProduct/run-task', json={'value': 4})

            assert table_response.status_code == 200
            assert class_response.status_code == 200
            assert class_response.json() == table_response.json() == {'value': 4, 'doubled': 8}
        finally:
            registered_models.clear()
            registered_models.update(saved)

    def test_class_name_method_mirror_does_not_capture_member_view_routes(self, tmp_path):
        import n3tx_ui  # noqa: F401 - registers ViewableMixin before model definition

        saved = dict(registered_models)
        registered_models.clear()
        try:
            class MirrorViewMethodProduct(ProtoModel):
                __tablename__: ClassVar[str] = 'mirror_view_method_products'
                __storable__: ClassVar[bool] = True
                __ui__: ClassVar[dict] = {'renderer': {'run': 'ntx-item', 'item': 'ntx-item'}}
                __access__: ClassVar[dict] = {
                    'create': ANYONE,
                    'read': ANYONE,
                    'update': ANYONE,
                    'delete': ANYONE,
                }
                calls: ClassVar[int] = 0
                name: str = Field(default='')

                @expose_route('/run', methods=['POST'], access=ANYONE)
                def run(self) -> dict:
                    type(self).calls += 1
                    return {'ran': True, 'calls': type(self).calls}

            app = create_app(
                models=[MirrorViewMethodProduct],
                storage=SQLiteStorage(str(tmp_path / 'mirror_view_methods.db')),
                static_dir=None,
            )
            created = MirrorViewMethodProduct.create(MirrorViewMethodProduct(name='View'))
            client = TestClient(app)

            method_response = client.post(f'/MirrorViewMethodProduct/{created.id}/run', json={})
            assert method_response.status_code == 200
            assert method_response.json() == {'ran': True, 'calls': 1}

            view_response = client.get(f'/MirrorViewMethodProduct/{created.id}/@run')
            assert view_response.status_code == 200
            assert 'text/html' in view_response.headers['content-type']
            assert '<ntx-item' in view_response.text
            assert MirrorViewMethodProduct.calls == 1
        finally:
            registered_models.clear()
            registered_models.update(saved)

    def test_nested_class_name_routes_generated_for_join_models(self, tmp_path):
        saved_models = dict(registered_models)
        saved_joins = dict(join_models)
        registered_models.clear()
        join_models.clear()
        try:
            class NestedRouteParent(ProtoModel):
                __tablename__: ClassVar[str] = 'nested_route_parents'
                __storable__: ClassVar[bool] = True
                __access__: ClassVar[dict] = {
                    'create': ANYONE,
                    'read': ANYONE,
                    'update': ANYONE,
                    'delete': ANYONE,
                }
                name: str = Field(default='')

            class NestedRouteChild(ProtoModel):
                __tablename__: ClassVar[str] = 'nested_route_children'
                __storable__: ClassVar[bool] = True
                __access__: ClassVar[dict] = {
                    'create': ANYONE,
                    'read': ANYONE,
                    'update': ANYONE,
                    'delete': ANYONE,
                }
                name: str = Field(default='')

            app = create_app(
                models=[NestedRouteParent],
                join_models=[(NestedRouteParent, NestedRouteChild)],
                storage=SQLiteStorage(str(tmp_path / 'nested_route_generation.db')),
                static_dir=None,
            )

            collection_methods = _route_methods(app, '/NestedRouteParent/{parent_id:int}/NestedRouteChild')
            member_methods = _route_methods(app, '/NestedRouteParent/{parent_id:int}/NestedRouteChild/{id:int}')

            assert {'GET', 'POST'} <= collection_methods
            assert {'GET', 'PUT', 'DELETE'} <= member_methods
            assert {'GET', 'POST'} <= _route_methods(app, '/nested_route_parents/{parent_id:int}/nested_route_children')
            assert {'GET', 'PUT', 'DELETE'} <= _route_methods(app, '/nested_route_parents/{parent_id:int}/nested_route_children/{id:int}')
        finally:
            registered_models.clear()
            registered_models.update(saved_models)
            join_models.clear()
            join_models.update(saved_joins)

    def test_nested_class_name_routes_mirror_legacy_join_behavior(self, tmp_path):
        saved_models = dict(registered_models)
        saved_joins = dict(join_models)
        registered_models.clear()
        join_models.clear()
        try:
            class NestedMirrorParent(ProtoModel):
                __tablename__: ClassVar[str] = 'nested_mirror_parents'
                __storable__: ClassVar[bool] = True
                __access__: ClassVar[dict] = {
                    'create': ANYONE,
                    'read': ANYONE,
                    'update': ANYONE,
                    'delete': ANYONE,
                }
                name: str = Field(default='')

            class NestedMirrorChild(ProtoModel):
                __tablename__: ClassVar[str] = 'nested_mirror_children'
                __storable__: ClassVar[bool] = True
                __access__: ClassVar[dict] = {
                    'create': ANYONE,
                    'read': ANYONE,
                    'update': ANYONE,
                    'delete': ANYONE,
                }
                name: str = Field(default='')

            app = create_app(
                models=[NestedMirrorParent],
                join_models=[(NestedMirrorParent, NestedMirrorChild)],
                storage=SQLiteStorage(str(tmp_path / 'nested_mirror_behavior.db')),
                static_dir=None,
            )
            client = TestClient(app)
            parent = NestedMirrorParent.create(NestedMirrorParent(name='Parent'))

            class_create = client.post(f'/NestedMirrorParent/{parent.id}/NestedMirrorChild', json={'name': 'Child'})
            assert class_create.status_code == 201
            created = class_create.json()
            assert created['nestedmirrorparent_id'] == parent.id
            assert created['$id'].endswith(f'/NestedMirrorParent/{parent.id}/NestedMirrorChild/{created["id"]}')

            legacy_read = client.get(f'/nested_mirror_parents/{parent.id}/nested_mirror_children/{created["id"]}')
            class_read = client.get(f'/NestedMirrorParent/{parent.id}/NestedMirrorChild/{created["id"]}')
            assert class_read.status_code == legacy_read.status_code == 200
            assert class_read.json() == legacy_read.json()

            legacy_list = client.get(f'/nested_mirror_parents/{parent.id}/nested_mirror_children')
            class_list = client.get(f'/NestedMirrorParent/{parent.id}/NestedMirrorChild')
            assert class_list.status_code == legacy_list.status_code == 200
            assert class_list.json() == legacy_list.json()

            class_update = client.put(
                f'/NestedMirrorParent/{parent.id}/NestedMirrorChild/{created["id"]}',
                json={'name': 'Updated'},
            )
            legacy_update = client.put(
                f'/nested_mirror_parents/{parent.id}/nested_mirror_children/{created["id"]}',
                json={'name': 'Updated Again'},
            )
            assert class_update.status_code == legacy_update.status_code == 200
            assert class_update.json()['nestedmirrorparent_id'] == parent.id
            assert legacy_update.json()['nestedmirrorparent_id'] == parent.id

            class_delete = client.delete(f'/NestedMirrorParent/{parent.id}/NestedMirrorChild/{created["id"]}')
            assert class_delete.status_code == 200
            assert client.get(f'/NestedMirrorParent/{parent.id}/NestedMirrorChild/{created["id"]}').status_code == 404
        finally:
            registered_models.clear()
            registered_models.update(saved_models)
            join_models.clear()
            join_models.update(saved_joins)

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

            assert client.put('/MirrorNotFoundProduct/999999', json={'name': 'Nope'}).status_code == 404
            assert client.delete('/MirrorNotFoundProduct/999999').status_code == 404
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
            assert client.get('/NonStorableMirror/_').status_code == 404
            assert client.post('/NonStorableMirror', json={'name': 'Nope'}).status_code == 405
            assert client.put('/NonStorableMirror/1', json={'name': 'Nope'}).status_code == 404
            assert client.delete('/NonStorableMirror/1').status_code == 404
        finally:
            registered_models.clear()
            registered_models.update(saved)

    def test_nested_class_name_routes_mirror_legacy_join_routes(self, tmp_path):
        saved = dict(registered_models)
        registered_models.clear()
        try:
            class DirectNestedParent(ProtoModel):
                __tablename__: ClassVar[str] = 'direct_nested_parents'
                __storable__: ClassVar[bool] = True
                __access__: ClassVar[dict] = {
                    'create': ANYONE,
                    'read': ANYONE,
                    'update': ANYONE,
                    'delete': ANYONE,
                    'list': ANYONE,
                }
                name: str = Field(default='')

            class DirectNestedChild(ProtoModel):
                __tablename__: ClassVar[str] = 'direct_nested_children'
                __storable__: ClassVar[bool] = True
                __access__: ClassVar[dict] = {
                    'create': ANYONE,
                    'read': ANYONE,
                    'update': ANYONE,
                    'delete': ANYONE,
                    'list': ANYONE,
                }
                name: str = Field(default='')

                @expose_route('/mark', methods=['POST'], access=ANYONE)
                def mark(self, value: str) -> dict:
                    return {'id': self.id, 'value': value}

            class DirectNestedParentChild(DirectNestedChild):
                __tablename__: ClassVar[str] = 'direct_nested_parent_children'
                __tagname__: ClassVar[str] = 'children'
                __storable__: ClassVar[bool] = True
                __owner__ = DirectNestedParent
                __parent__ = DirectNestedChild
                directnestedparent_id: int = Field(...)

            app = create_app(
                models=[DirectNestedParent, DirectNestedParentChild],
                storage=SQLiteStorage(str(tmp_path / 'direct_nested.db')),
                static_dir=None,
            )
            client = TestClient(app)
            parent = DirectNestedParent.create(DirectNestedParent(name='Parent'))

            legacy_create = client.post(
                f'/direct_nested_parents/{parent.id}/children',
                json={'name': 'Child'},
            )
            assert legacy_create.status_code == 201
            child_id = legacy_create.json()['id']

            class_list = client.get(f'/DirectNestedParent/{parent.id}/DirectNestedChild')
            legacy_list = client.get(f'/direct_nested_parents/{parent.id}/children')
            assert class_list.status_code == legacy_list.status_code == 200
            assert class_list.json() == legacy_list.json()

            class_read = client.get(f'/DirectNestedParent/{parent.id}/DirectNestedChild/{child_id}')
            legacy_read = client.get(f'/direct_nested_parents/{parent.id}/children/{child_id}')
            assert class_read.status_code == legacy_read.status_code == 200
            assert class_read.json() == legacy_read.json()
            assert class_read.json()['$id'].endswith(
                f'/DirectNestedParent/{parent.id}/DirectNestedChild/{child_id}'
            )

            class_update = client.put(
                f'/DirectNestedParent/{parent.id}/DirectNestedChild/{child_id}',
                json={'name': 'Updated'},
            )
            legacy_after_update = client.get(f'/direct_nested_parents/{parent.id}/children/{child_id}')
            assert class_update.status_code == 200
            assert legacy_after_update.json()['name'] == 'Updated'

            class_method = client.post(
                f'/DirectNestedParent/{parent.id}/DirectNestedChild/{child_id}/mark',
                json={'value': 'ok'},
            )
            legacy_method = client.post(
                f'/direct_nested_parents/{parent.id}/children/{child_id}/mark',
                json={'value': 'ok'},
            )
            assert class_method.status_code == legacy_method.status_code == 200
            assert class_method.json() == legacy_method.json() == {'id': child_id, 'value': 'ok'}

            class_delete = client.delete(f'/DirectNestedParent/{parent.id}/DirectNestedChild/{child_id}')
            assert class_delete.status_code == 200
            assert client.get(f'/direct_nested_parents/{parent.id}/children/{child_id}').status_code == 404
        finally:
            registered_models.clear()
            registered_models.update(saved)
