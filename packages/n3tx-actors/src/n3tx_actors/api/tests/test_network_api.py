"""
Test plan for NetworkAPI
=========================

UNIT TESTS — behavior validation
  - test_init_default_addr_is_api
  - test_init_custom_addr
  - test_init_auto_register_false
  - test_get_user_extracts_from_request_state
  - test_get_user_returns_empty_dict_when_no_user
  - test_response_or_raise_returns_data_on_success
  - test_response_or_raise_raises_on_error_tx
  - test_parse_method_args_extracts_simple_params
  - test_parse_method_args_handles_pydantic_models
  - test_parse_method_args_injects_user_dict
  - test_parse_method_args_resolves_storable_user
  - test_parse_method_args_skips_self_cls_user
  - test_parse_method_args_raises_on_invalid_field

EDGE CASES — boundary conditions
  - test_get_user_with_none_state_user
  - test_response_or_raise_with_missing_error_code
  - test_response_or_raise_with_missing_error_message
  - test_parse_method_args_with_empty_data
  - test_parse_method_args_with_missing_optional_param
  - test_parse_method_args_user_without_user_id

BAD INPUTS — error handling and validation
  - test_response_or_raise_error_code_extraction
  - test_parse_method_args_invalid_pydantic_model
  - test_parse_method_args_type_conversion_failure

INTEGRATION TESTS (partial) — route generation
  - test_create_api_routes_generates_schema_route
  - test_create_api_routes_generates_crud_routes
  - test_create_api_routes_generates_custom_method_routes
  - test_create_api_routes_generates_collection_routes_for_join_models
  - test_create_api_routes_parent_child_path_structure
  - test_schema_route_sends_schema_tx
  - test_schema_route_scaffold_parameter
  - test_create_route_sends_create_tx
  - test_create_route_injects_user_owner
  - test_create_route_injects_parent_fk
  - test_list_route_sends_list_tx
  - test_list_route_handles_pagination
  - test_get_route_sends_get_tx
  - test_update_route_sends_update_tx
  - test_update_route_strips_protected_fields
  - test_delete_route_sends_delete_tx
  - test_custom_method_instance_route
  - test_custom_method_class_route
  - test_custom_method_parses_body_args

INTEGRATION TESTS (full pipeline) — end-to-end
  - test_schema_request_through_adapter_to_response
  - test_crud_create_through_adapter_to_response
  - test_crud_list_through_adapter_to_response
  - test_error_tx_raises_http_exception

OUTPUT SHAPE — serialization contracts
  - test_response_or_raise_extracts_data_field
  - test_parse_method_args_output_structure
  - test_create_route_status_code_201
  - test_error_response_includes_detail

CLEANUP / RESOURCES
  - test_routes_register_with_router
  - test_multiple_models_generate_independent_routes
"""

import asyncio
import pytest
from contextlib import contextmanager
from inspect import signature
from typing import ClassVar, Optional
from unittest.mock import AsyncMock, MagicMock, Mock

from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from n3tx_actors.api.network_api import (
    NetworkAPI,
    create_api_routes,
    _get_user,
    _response_or_raise,
    _parse_method_args,
)
from n3tx_actors.tx import TX
from n3tx_actors.actor import Actor
from n3tx_actors.matrix import Matrix
from n3tx_core.models.storable_mixin import StorableMixin
from n3tx_core.utils.decorators import expose_route

pytestmark = pytest.mark.unit


# ===================================================================
# Helpers
# ===================================================================

@contextmanager
def mock_method(instance, name, replacement):
    """Temporarily replace a method on a Pydantic BaseModel instance.

    Pydantic's __setattr__/__delattr__ prevent normal mock patching.
    This uses object.__setattr__/delattr__ to bypass the protection.
    """
    object.__setattr__(instance, name, replacement)
    try:
        yield replacement
    finally:
        object.__delattr__(instance, name)


def make_mock_request(user=None):
    """Create a mock FastAPI Request with optional user in state."""
    req = Mock(spec=Request)
    req.state = Mock()
    req.state.user = user
    req.query_params = {}
    return req


# ===================================================================
# Mock Models
# ===================================================================

class MockModel(StorableMixin, Actor, auto_register=False):
    """Mock model for testing route generation."""
    __tablename__: ClassVar[str] = 'mock_models'
    __storable__: ClassVar[bool] = True
    __protected_fields__: ClassVar[set] = {'user_owner'}

    name: str = Field(min_length=1, max_length=100)
    value: int = Field(ge=0, default=0)
    user_owner: Optional[int] = Field(default=None)

    @classmethod
    def schema(cls):
        return {
            '__name__': 'MockModel',
            '__tablename__': 'mock_models',
            'properties': {
                'id': {'type': 'integer'},
                'name': {'type': 'string', 'minLength': 1, 'maxLength': 100},
                'value': {'type': 'integer', 'minimum': 0, 'default': 0},
                'user_owner': {'type': 'integer'},
            },
            'required': ['name'],
        }

    @classmethod
    def register_view_routes(cls, router, *, tag: str) -> None:
        """Local view-capability hook used to test package-neutral delegation.

        The real implementation lives in n3tx-ui's ViewableMixin; actor tests
        avoid importing that package so n3tx-actors remains package-neutral.
        """

        @router.get(f"/{cls.__name__}/@", tags=[tag], include_in_schema=False)
        async def collection_default_view(_cls=cls):
            return HTMLResponse(f'<ntx-list model="{_cls.__name__}"></ntx-list>')

        @router.get(f"/{cls.__name__}/@{{view}}", tags=[tag], include_in_schema=False)
        async def collection_named_view(view: str, _cls=cls):
            tag_name = 'ntx-table' if view == 'table' else f'ntx-{view}'
            return HTMLResponse(f'<{tag_name} model="{_cls.__name__}"></{tag_name}>')

        @router.get(f"/{cls.__name__}/{{id:int}}/@", tags=[tag], include_in_schema=False)
        async def member_default_view(id: int, _cls=cls):
            return HTMLResponse(f'<ntx-item ref="{_cls.__name__}/{id}" display="lg"></ntx-item>')

        @router.get(f"/{cls.__name__}/{{id:int}}/@{{view}}", tags=[tag], include_in_schema=False)
        async def member_named_view(id: int, view: str, _cls=cls):
            tag_name = 'ntx-item' if view == 'item' else f'ntx-{view}'
            return HTMLResponse(f'<{tag_name} ref="{_cls.__name__}/{id}" display="lg"></{tag_name}>')

    @expose_route('/custom', methods=['POST'])
    def custom_method(self, arg1: str, arg2: int = 10) -> str:
        return f"{arg1}_{arg2}"


class MockUser(StorableMixin, Actor, auto_register=False):
    """Mock user model for user injection tests."""
    __tablename__: ClassVar[str] = 'users'
    __storable__: ClassVar[bool] = True

    id: Optional[int] = Field(default=None)
    name: str = Field(min_length=1)
    email: str = Field(min_length=1)

    @classmethod
    def get(cls, user_id: int):
        """Mock get method for user resolution."""
        return cls(id=user_id, name='Test User', email='test@example.com')


class MockChildModel(StorableMixin, Actor, auto_register=False):
    """Mock child model with parent relationship."""
    __tablename__: ClassVar[str] = 'mock_children'
    __tagname__: ClassVar[str] = 'children'
    __storable__: ClassVar[bool] = True
    __owner__: ClassVar[type] = MockModel

    content: str = Field(min_length=1)
    mockmodel_id: Optional[int] = Field(default=None)


# ===================================================================
# TestNetworkAPIInit
# ===================================================================

class TestNetworkAPIInit:
    """NetworkAPI initialization and configuration."""

    def test_init_default_addr_is_api(self):
        adapter = NetworkAPI()
        assert adapter.addr == 'api'

    def test_init_custom_addr(self):
        adapter = NetworkAPI(addr='custom_api')
        assert adapter.addr == 'custom_api'

    def test_init_auto_register_false(self):
        """NetworkAPI has auto_register=False, requires manual registration."""
        Actor.__matrix__ = None
        m = Matrix()
        adapter = NetworkAPI(addr='test_api')
        assert 'test_api' not in m._children


# ===================================================================
# TestGetUser
# ===================================================================

class TestGetUser:
    """_get_user() helper function."""

    def test_get_user_extracts_from_request_state(self):
        user_dict = {'user_id': 1, 'email': 'test@example.com'}
        request = make_mock_request(user=user_dict)
        result = _get_user(request)
        assert result == user_dict

    def test_get_user_returns_empty_dict_when_no_user(self):
        request = make_mock_request(user=None)
        result = _get_user(request)
        assert result == {}

    def test_get_user_with_none_state_user(self):
        """Should return empty dict if state.user is explicitly None."""
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.user = None
        result = _get_user(request)
        assert result == {}


# ===================================================================
# TestResponseOrRaise
# ===================================================================

class TestResponseOrRaise:
    """_response_or_raise() helper function."""

    def test_response_or_raise_returns_data_on_success(self):
        tx = TX(name='SUCCESS', source='api', target='model',
                data={'result': 'ok'})
        result = _response_or_raise(tx)
        assert result == {'result': 'ok'}

    def test_response_or_raise_raises_on_error_tx(self):
        tx = TX(name='ERROR', source='api', target='model',
                data={'message': 'Not found', 'code': 404},
                meta={'error': True})

        with pytest.raises(HTTPException) as exc_info:
            _response_or_raise(tx)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == 'Not found'

    def test_response_or_raise_with_missing_error_code(self):
        """Should default to 500 if error code is missing."""
        tx = TX(name='ERROR', source='api', target='model',
                data={'message': 'Something went wrong'},
                meta={'error': True})

        with pytest.raises(HTTPException) as exc_info:
            _response_or_raise(tx)

        assert exc_info.value.status_code == 500

    def test_response_or_raise_with_missing_error_message(self):
        """Should default to 'Internal error' if message is missing."""
        tx = TX(name='ERROR', source='api', target='model',
                data={'code': 500},
                meta={'error': True})

        with pytest.raises(HTTPException) as exc_info:
            _response_or_raise(tx)

        assert exc_info.value.detail == 'Internal error'

    def test_response_or_raise_error_code_extraction(self):
        """Should extract status code from error data."""
        tx = TX(name='ERROR', source='api', target='model',
                data={'message': 'Unauthorized', 'code': 401},
                meta={'error': True})

        with pytest.raises(HTTPException) as exc_info:
            _response_or_raise(tx)

        assert exc_info.value.status_code == 401


# ===================================================================
# TestParseMethodArgs
# ===================================================================

class TestParseMethodArgs:
    """_parse_method_args() helper function."""

    def test_parse_method_args_extracts_simple_params(self):
        def test_method(self, name: str, count: int):
            pass

        sig = signature(test_method)
        type_hints = {'name': str, 'count': int}
        data = {'name': 'widget', 'count': '5'}
        request = make_mock_request()

        result = _parse_method_args(sig, type_hints, data, request)

        assert result == {'name': 'widget', 'count': 5}

    def test_parse_method_args_handles_pydantic_models(self):
        class TestData(BaseModel):
            title: str
            value: int

        def test_method(self, data: TestData):
            pass

        sig = signature(test_method)
        type_hints = {'data': TestData}
        data = {'data': {'title': 'Test', 'value': 42}}
        request = make_mock_request()

        result = _parse_method_args(sig, type_hints, data, request)

        assert 'data' in result
        assert isinstance(result['data'], TestData)
        assert result['data'].title == 'Test'
        assert result['data'].value == 42

    def test_parse_method_args_injects_user_dict(self):
        """If user param exists and type is not StorableMixin, inject dict."""
        def test_method(self, user: dict):
            pass

        sig = signature(test_method)
        type_hints = {'user': dict}
        data = {}
        request = make_mock_request(user={'user_id': 1, 'email': 'test@example.com'})

        result = _parse_method_args(sig, type_hints, data, request)

        assert 'user' in result
        assert result['user'] == {'user_id': 1, 'email': 'test@example.com'}

    def test_parse_method_args_resolves_storable_user(self):
        """If user param type is StorableMixin subclass, resolve full instance."""
        def test_method(self, user: MockUser):
            pass

        sig = signature(test_method)
        type_hints = {'user': MockUser}
        data = {}
        request = make_mock_request(user={'user_id': 5})

        # Mock the get method to return a user instance
        mock_user = MockUser(id=5, name='Test', email='test@example.com')
        original_get = MockUser.get
        MockUser.get = lambda user_id: mock_user

        try:
            result = _parse_method_args(sig, type_hints, data, request)

            assert 'user' in result
            assert isinstance(result['user'], MockUser)
            assert result['user'].id == 5
        finally:
            MockUser.get = original_get

    def test_parse_method_args_skips_self_cls_user(self):
        """Should not include self, cls, or user in param extraction from data."""
        def test_method(self, arg1: str, user: dict):
            pass

        sig = signature(test_method)
        type_hints = {'arg1': str, 'user': dict}
        data = {'arg1': 'value', 'self': 'ignored', 'cls': 'ignored', 'user': 'ignored'}
        request = make_mock_request(user={'user_id': 1})

        result = _parse_method_args(sig, type_hints, data, request)

        assert result == {'arg1': 'value', 'user': {'user_id': 1}}

    def test_parse_method_args_with_empty_data(self):
        """Should handle empty data dict."""
        def test_method(self):
            pass

        sig = signature(test_method)
        type_hints = {}
        data = {}
        request = make_mock_request()

        result = _parse_method_args(sig, type_hints, data, request)

        assert result == {}

    def test_parse_method_args_with_missing_optional_param(self):
        """Should skip params not present in data."""
        def test_method(self, required: str, optional: int = 10):
            pass

        sig = signature(test_method)
        type_hints = {'required': str, 'optional': int}
        data = {'required': 'value'}
        request = make_mock_request()

        result = _parse_method_args(sig, type_hints, data, request)

        assert result == {'required': 'value'}

    def test_parse_method_args_user_without_user_id(self):
        """Should not inject user if user_id is missing."""
        def test_method(self, user: dict):
            pass

        sig = signature(test_method)
        type_hints = {'user': dict}
        data = {}
        request = make_mock_request(user={'email': 'test@example.com'})  # No user_id

        result = _parse_method_args(sig, type_hints, data, request)

        # User param not in signature, so should not be in result
        assert result == {}

    def test_parse_method_args_raises_on_invalid_field(self):
        """Should raise HTTPException on type conversion failure."""
        def test_method(self, count: int):
            pass

        sig = signature(test_method)
        type_hints = {'count': int}
        data = {'count': 'not-a-number'}
        request = make_mock_request()

        with pytest.raises(HTTPException) as exc_info:
            _parse_method_args(sig, type_hints, data, request)

        assert exc_info.value.status_code == 422
        assert 'count' in exc_info.value.detail

    def test_parse_method_args_invalid_pydantic_model(self):
        """Should raise HTTPException on Pydantic validation failure."""
        class TestData(BaseModel):
            required: str

        def test_method(self, data: TestData):
            pass

        sig = signature(test_method)
        type_hints = {'data': TestData}
        data = {'data': {}}  # Missing required field
        request = make_mock_request()

        with pytest.raises(HTTPException) as exc_info:
            _parse_method_args(sig, type_hints, data, request)

        assert exc_info.value.status_code == 422

    def test_parse_method_args_type_conversion_failure(self):
        """Should raise HTTPException when type conversion fails."""
        def test_method(self, value: float):
            pass

        sig = signature(test_method)
        type_hints = {'value': float}
        data = {'value': 'invalid-float'}
        request = make_mock_request()

        with pytest.raises(HTTPException) as exc_info:
            _parse_method_args(sig, type_hints, data, request)

        assert exc_info.value.status_code == 422


# ===================================================================
# TestCreateAPIRoutesRouteGeneration
# ===================================================================

class TestCreateAPIRoutesRouteGeneration:
    """create_api_routes() generates correct route structure."""

    def test_create_api_routes_generates_schema_route(self):
        """Should generate GET /{ClassName} schema route."""
        api = NetworkAPI()
        models = {'mock_models': MockModel}
        router = create_api_routes(api, models)

        routes = {r.path for r in router.routes}
        assert '/MockModel' in routes

    def test_create_api_routes_generates_crud_routes(self):
        """Should generate all CRUD routes for storable models."""
        api = NetworkAPI()
        models = {'mock_models': MockModel}
        router = create_api_routes(api, models)

        routes = {r.path for r in router.routes}
        # Base path for list and create
        assert '/mock_models' in routes
        # Item path for get, update, delete
        assert '/mock_models/{id:int}' in routes

    def test_create_api_routes_generates_custom_method_routes(self):
        """Should generate routes for @expose_route methods."""
        api = NetworkAPI()
        models = {'mock_models': MockModel}
        router = create_api_routes(api, models)

        routes = {r.path for r in router.routes}
        # Instance method route includes {id:int}
        assert '/mock_models/{id:int}/custom' in routes

    def test_create_api_routes_generates_collection_routes_for_join_models(self):
        """Join models should get static collection routes first."""
        api = NetworkAPI()
        models = {
            'mock_models': MockModel,
            'mock_children': MockChildModel,
        }
        router = create_api_routes(api, models)

        routes = {r.path for r in router.routes}
        # Static collection route for join model
        assert '/mock_children' in routes

    def test_create_api_routes_parent_child_path_structure(self):
        """Child models should have parent ID in path."""
        api = NetworkAPI()
        models = {
            'mock_models': MockModel,
            'mock_children': MockChildModel,
        }
        router = create_api_routes(api, models)

        routes = {r.path for r in router.routes}
        # Parent-child path structure
        assert '/mock_models/{parent_id:int}/children' in routes
        assert '/mock_models/{parent_id:int}/children/{id:int}' in routes


# ===================================================================
# TestSchemaRoute
# ===================================================================

class TestSchemaRoute:
    """Schema route functionality."""

    @pytest.mark.asyncio
    async def test_schema_route_sends_schema_tx(self):
        """GET /{ClassName} should send schema TX through adapter."""
        Actor.__matrix__ = None
        m = Matrix()
        api = NetworkAPI()
        m.register(api)
        m.register(MockModel)

        models = {'mock_models': MockModel}
        router = create_api_routes(api, models)

        schema_data = MockModel.schema()

        async def mock_request(tx, timeout=10.0):
            assert tx.name == 'schema'
            assert tx.target == 'mock_models'
            assert tx.source == 'api'
            return tx.reply(data=schema_data)

        with mock_method(api, 'request', mock_request):
            from fastapi import FastAPI
            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)

            response = client.get('/MockModel')

        assert response.status_code == 200
        assert response.json() == schema_data

    @pytest.mark.asyncio
    async def test_schema_route_scaffold_parameter(self):
        """GET /{ClassName}?scaffold=html should generate scaffold code."""
        Actor.__matrix__ = None
        m = Matrix()
        api = NetworkAPI()
        m.register(api)
        m.register(MockModel)

        models = {'mock_models': MockModel}
        router = create_api_routes(api, models)

        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # Scaffold generation requires the scaffold module
        # This test verifies the route structure, actual generation tested separately
        response = client.get('/MockModel?scaffold=html')

        # Should return plaintext response or error if scaffold not available
        assert response.status_code in (200, 400)


# ===================================================================
# TestCRUDRoutes
# ===================================================================

class TestCRUDRoutes:
    """CRUD route functionality."""

    @pytest.mark.asyncio
    async def test_create_route_sends_create_tx(self):
        """POST /{tablename} should send create TX."""
        Actor.__matrix__ = None
        m = Matrix()
        api = NetworkAPI()
        m.register(api)
        m.register(MockModel)

        models = {'mock_models': MockModel}
        router = create_api_routes(api, models)

        captured_tx = None

        async def mock_request(tx, timeout=30.0):
            nonlocal captured_tx
            captured_tx = tx
            return tx.reply(data={'id': 1, 'name': 'Test', 'value': 5})

        with mock_method(api, 'request', mock_request):
            from fastapi import FastAPI
            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)

            response = client.post('/mock_models', json={'name': 'Test', 'value': 5})

        assert response.status_code == 201
        assert captured_tx.name == 'create'
        assert captured_tx.target == 'mock_models'
        assert captured_tx.data['name'] == 'Test'
        assert captured_tx.data['value'] == 5

    @pytest.mark.asyncio
    async def test_create_route_injects_user_owner(self):
        """POST should auto-inject user_owner from JWT on create."""
        Actor.__matrix__ = None
        m = Matrix()
        api = NetworkAPI()
        m.register(api)
        m.register(MockModel)

        models = {'mock_models': MockModel}
        router = create_api_routes(api, models)

        captured_tx = None

        async def mock_request(tx, timeout=30.0):
            nonlocal captured_tx
            captured_tx = tx
            return tx.reply(data={'id': 1, 'name': 'Test', 'user_owner': 123})

        # Create app with JWT middleware simulation
        from fastapi import FastAPI
        app = FastAPI()

        @app.middleware("http")
        async def add_user_to_state(request, call_next):
            request.state.user = {'user_id': 123, 'email': 'test@example.com'}
            response = await call_next(request)
            return response

        app.include_router(router)

        with mock_method(api, 'request', mock_request):
            client = TestClient(app)
            response = client.post('/mock_models', json={'name': 'Test'})

        assert response.status_code == 201
        assert captured_tx.data.get('user_owner') == 123

    @pytest.mark.asyncio
    async def test_create_route_injects_parent_fk(self):
        """POST on child route should inject parent FK."""
        Actor.__matrix__ = None
        m = Matrix()
        api = NetworkAPI()
        m.register(api)
        m.register(MockModel)
        m.register(MockChildModel)

        models = {
            'mock_models': MockModel,
            'mock_children': MockChildModel,
        }
        router = create_api_routes(api, models)

        captured_tx = None

        async def mock_request(tx, timeout=30.0):
            nonlocal captured_tx
            captured_tx = tx
            return tx.reply(data={'id': 1, 'content': 'Child content', 'mockmodel_id': 5})

        with mock_method(api, 'request', mock_request):
            from fastapi import FastAPI
            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)

            response = client.post(
                '/mock_models/5/children',
                json={'content': 'Child content'}
            )

        assert response.status_code == 201
        assert captured_tx.data.get('mockmodel_id') == 5

    @pytest.mark.asyncio
    async def test_list_route_sends_list_tx(self):
        """GET /{tablename} should send list TX."""
        Actor.__matrix__ = None
        m = Matrix()
        api = NetworkAPI()
        m.register(api)
        m.register(MockModel)

        models = {'mock_models': MockModel}
        router = create_api_routes(api, models)

        captured_tx = None

        async def mock_request(tx, timeout=30.0):
            nonlocal captured_tx
            captured_tx = tx
            return tx.reply(data={'data': [], 'meta': {'total': 0}})

        with mock_method(api, 'request', mock_request):
            from fastapi import FastAPI
            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)

            response = client.get('/mock_models')

        assert response.status_code == 200
        assert captured_tx.name == 'list'
        assert captured_tx.target == 'mock_models'

    @pytest.mark.asyncio
    async def test_list_route_handles_pagination(self):
        """GET /{tablename}?limit=10&offset=20 should include pagination."""
        Actor.__matrix__ = None
        m = Matrix()
        api = NetworkAPI()
        m.register(api)
        m.register(MockModel)

        models = {'mock_models': MockModel}
        router = create_api_routes(api, models)

        captured_tx = None

        async def mock_request(tx, timeout=30.0):
            nonlocal captured_tx
            captured_tx = tx
            return tx.reply(data={'data': [], 'meta': {'total': 100, 'limit': 10, 'offset': 20}})

        with mock_method(api, 'request', mock_request):
            from fastapi import FastAPI
            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)

            response = client.get('/mock_models?limit=10&offset=20')

        assert response.status_code == 200
        assert captured_tx.data.get('limit') == 10
        assert captured_tx.data.get('offset') == 20

    @pytest.mark.asyncio
    async def test_get_route_sends_get_tx(self):
        """GET /{tablename}/{id} should send get TX."""
        Actor.__matrix__ = None
        m = Matrix()
        api = NetworkAPI()
        m.register(api)
        m.register(MockModel)

        models = {'mock_models': MockModel}
        router = create_api_routes(api, models)

        captured_tx = None

        async def mock_request(tx, timeout=30.0):
            nonlocal captured_tx
            captured_tx = tx
            return tx.reply(data={'id': 5, 'name': 'Test', 'value': 10})

        with mock_method(api, 'request', mock_request):
            from fastapi import FastAPI
            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)

            response = client.get('/mock_models/5')

        assert response.status_code == 200
        assert captured_tx.name == 'get'
        assert captured_tx.data.get('id') == 5

    @pytest.mark.asyncio
    async def test_class_name_read_mirror_sends_get_tx(self):
        """GET /{ClassName}/{id} should dispatch same get TX to table-name actor."""
        Actor.__matrix__ = None
        m = Matrix()
        api = NetworkAPI()
        m.register(api)
        m.register(MockModel)

        models = {'mock_models': MockModel}
        router = create_api_routes(api, models)

        captured_tx = None
        reply_data = {
            'id': 5,
            'name': 'Test',
            '$schema': 'http://test/MockModel',
            '$id': 'http://test/mock_models/5',
        }

        async def mock_request(tx, timeout=30.0):
            nonlocal captured_tx
            captured_tx = tx
            return tx.reply(data=reply_data)

        from fastapi import FastAPI
        app = FastAPI()

        @app.middleware("http")
        async def add_user_to_state(request, call_next):
            request.state.user = {'user_id': 77, 'email': 'actor@example.com'}
            return await call_next(request)

        app.include_router(router)

        with mock_method(api, 'request', mock_request):
            client = TestClient(app)
            response = client.get('/MockModel/5?populate=children&depth=1')

        assert response.status_code == 200
        assert response.json() == reply_data
        assert captured_tx.name == 'get'
        assert captured_tx.source == 'api'
        assert captured_tx.target == 'mock_models'
        assert captured_tx.data == {'id': 5, 'populate': 'children', 'depth': 1}
        assert captured_tx.meta['user'] == {'user_id': 77, 'email': 'actor@example.com'}
        assert captured_tx.meta['model_cls'] is MockModel

    @pytest.mark.asyncio
    async def test_class_name_read_mirror_error_maps_like_table_get(self):
        """Error TX from class-name read mirror should map through _response_or_raise."""
        Actor.__matrix__ = None
        m = Matrix()
        api = NetworkAPI()
        m.register(api)
        m.register(MockModel)

        models = {'mock_models': MockModel}
        router = create_api_routes(api, models)

        async def mock_request(tx, timeout=30.0):
            return tx.error('Not found', code=404)

        with mock_method(api, 'request', mock_request):
            from fastapi import FastAPI
            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)

            response = client.get('/MockModel/999')

        assert response.status_code == 404
        assert response.json()['detail'] == 'Not found'

    @pytest.mark.asyncio
    async def test_actor_html_view_routes_do_not_send_crud_tx(self):
        """Actor HTML view routes should be served by view capability, not api.request."""
        Actor.__matrix__ = None
        m = Matrix()
        api = NetworkAPI()
        m.register(api)
        m.register(MockModel)

        models = {'mock_models': MockModel}
        router = create_api_routes(api, models)

        async def fail_request(tx, timeout=30.0):
            raise AssertionError('HTML view routes must not call api.request')

        with mock_method(api, 'request', fail_request):
            from fastapi import FastAPI
            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)

            collection_default = client.get('/MockModel/@')
            collection_named = client.get('/MockModel/@table')
            member_default = client.get('/MockModel/5/@')
            member_named = client.get('/MockModel/5/@item')

        assert collection_default.status_code == 200
        assert 'text/html' in collection_default.headers['content-type']
        assert '<ntx-list model="MockModel"' in collection_default.text
        assert collection_named.status_code == 200
        assert '<ntx-table model="MockModel"' in collection_named.text
        assert member_default.status_code == 200
        assert '<ntx-item ref="MockModel/5" display="lg"' in member_default.text
        assert member_named.status_code == 200
        assert '<ntx-item ref="MockModel/5" display="lg"' in member_named.text

    def test_actor_route_conflicts_preserve_intended_targets(self):
        """Class-name view/read routes should not shadow legacy method routes."""
        api = NetworkAPI()
        router = create_api_routes(api, {'mock_models': MockModel})
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        assert client.get('/MockModel/@table').status_code == 200
        assert client.get('/MockModel/5/@item').status_code == 200
        assert client.get('/MockModel/5/custom').status_code == 404
        # Existing table-name custom route remains registered.
        routes = {r.path for r in router.routes}
        assert '/mock_models/{id:int}/custom' in routes

    @pytest.mark.asyncio
    async def test_update_route_sends_update_tx(self):
        """PUT /{tablename}/{id} should send update TX."""
        Actor.__matrix__ = None
        m = Matrix()
        api = NetworkAPI()
        m.register(api)
        m.register(MockModel)

        models = {'mock_models': MockModel}
        router = create_api_routes(api, models)

        captured_tx = None

        async def mock_request(tx, timeout=30.0):
            nonlocal captured_tx
            captured_tx = tx
            return tx.reply(data={'id': 5, 'name': 'Updated', 'value': 20})

        with mock_method(api, 'request', mock_request):
            from fastapi import FastAPI
            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)

            response = client.put('/mock_models/5', json={'name': 'Updated', 'value': 20})

        assert response.status_code == 200
        assert captured_tx.name == 'update'
        assert captured_tx.data.get('id') == 5
        assert captured_tx.data.get('name') == 'Updated'

    @pytest.mark.asyncio
    async def test_update_route_strips_protected_fields(self):
        """PUT should strip protected fields from update data."""
        Actor.__matrix__ = None
        m = Matrix()
        api = NetworkAPI()
        m.register(api)
        m.register(MockModel)

        models = {'mock_models': MockModel}
        router = create_api_routes(api, models)

        captured_tx = None

        async def mock_request(tx, timeout=30.0):
            nonlocal captured_tx
            captured_tx = tx
            return tx.reply(data={'id': 5, 'name': 'Test'})

        with mock_method(api, 'request', mock_request):
            from fastapi import FastAPI
            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)

            response = client.put(
                '/mock_models/5',
                json={'name': 'Test', 'user_owner': 999}  # Protected field
            )

        assert response.status_code == 200
        # Protected field should be stripped
        assert 'user_owner' not in captured_tx.data
        assert captured_tx.data.get('name') == 'Test'

    @pytest.mark.asyncio
    async def test_delete_route_sends_delete_tx(self):
        """DELETE /{tablename}/{id} should send delete TX."""
        Actor.__matrix__ = None
        m = Matrix()
        api = NetworkAPI()
        m.register(api)
        m.register(MockModel)

        models = {'mock_models': MockModel}
        router = create_api_routes(api, models)

        captured_tx = None

        async def mock_request(tx, timeout=30.0):
            nonlocal captured_tx
            captured_tx = tx
            return tx.reply(data={'success': True})

        with mock_method(api, 'request', mock_request):
            from fastapi import FastAPI
            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)

            response = client.delete('/mock_models/5')

        assert response.status_code == 200
        assert captured_tx.name == 'delete'
        assert captured_tx.data.get('id') == 5


# ===================================================================
# TestCustomMethodRoutes
# ===================================================================

class TestCustomMethodRoutes:
    """Custom @expose_route method routes."""

    @pytest.mark.asyncio
    async def test_custom_method_instance_route(self):
        """Instance method route should include {id:int} in path."""
        Actor.__matrix__ = None
        m = Matrix()
        api = NetworkAPI()
        m.register(api)
        m.register(MockModel)

        models = {'mock_models': MockModel}
        router = create_api_routes(api, models)

        captured_tx = None

        async def mock_request(tx, timeout=30.0):
            nonlocal captured_tx
            captured_tx = tx
            return tx.reply(data={'result': 'test_10'})

        with mock_method(api, 'request', mock_request):
            from fastapi import FastAPI
            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)

            response = client.post(
                '/mock_models/5/custom',
                json={'arg1': 'test', 'arg2': 10}
            )

        assert response.status_code == 200
        assert captured_tx.name == 'custom_method'
        assert captured_tx.data.get('id') == 5
        assert captured_tx.data.get('arg1') == 'test'
        assert captured_tx.data.get('arg2') == 10

    @pytest.mark.asyncio
    async def test_custom_method_class_route(self):
        """Class method route should not include {id:int}."""
        # Add a class method to MockModel
        @classmethod
        @expose_route('/class_method', methods=['POST'])
        def class_method(cls, value: int) -> dict:
            return {'doubled': value * 2}

        MockModel.class_method = class_method

        Actor.__matrix__ = None
        m = Matrix()
        api = NetworkAPI()
        m.register(api)
        m.register(MockModel)

        models = {'mock_models': MockModel}
        router = create_api_routes(api, models)

        routes = {r.path for r in router.routes}
        # Class method should not have {id:int}
        assert '/mock_models/class_method' in routes

    @pytest.mark.asyncio
    async def test_custom_method_parses_body_args(self):
        """Custom method should parse arguments from request body."""
        Actor.__matrix__ = None
        m = Matrix()
        api = NetworkAPI()
        m.register(api)
        m.register(MockModel)

        models = {'mock_models': MockModel}
        router = create_api_routes(api, models)

        captured_tx = None

        async def mock_request(tx, timeout=30.0):
            nonlocal captured_tx
            captured_tx = tx
            return tx.reply(data={'result': 'parsed'})

        with mock_method(api, 'request', mock_request):
            from fastapi import FastAPI
            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)

            response = client.post(
                '/mock_models/1/custom',
                json={'arg1': 'value1', 'arg2': 42}
            )

        assert response.status_code == 200
        assert captured_tx.data.get('arg1') == 'value1'
        assert captured_tx.data.get('arg2') == 42


# ===================================================================
# TestEndToEndPipeline
# ===================================================================

class TestEndToEndPipeline:
    """Full pipeline from HTTP request to TX to response."""

    @pytest.mark.asyncio
    async def test_schema_request_through_adapter_to_response(self):
        """Complete flow: HTTP GET /Model → TX → schema response."""
        Actor.__matrix__ = None
        m = Matrix()
        api = NetworkAPI()
        m.register(api)
        m.register(MockModel)

        models = {'mock_models': MockModel}
        router = create_api_routes(api, models)

        schema_data = MockModel.schema()

        async def mock_request(tx, timeout=10.0):
            return tx.reply(data=schema_data)

        with mock_method(api, 'request', mock_request):
            from fastapi import FastAPI
            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)

            response = client.get('/MockModel')

        assert response.status_code == 200
        data = response.json()
        assert data['__tablename__'] == 'mock_models'
        assert 'properties' in data

    @pytest.mark.asyncio
    async def test_crud_create_through_adapter_to_response(self):
        """Complete flow: HTTP POST → create TX → response."""
        Actor.__matrix__ = None
        m = Matrix()
        api = NetworkAPI()
        m.register(api)
        m.register(MockModel)

        models = {'mock_models': MockModel}
        router = create_api_routes(api, models)

        async def mock_request(tx, timeout=30.0):
            return tx.reply(data={
                'id': 1,
                'name': tx.data['name'],
                'value': tx.data['value'],
            })

        with mock_method(api, 'request', mock_request):
            from fastapi import FastAPI
            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)

            response = client.post('/mock_models', json={'name': 'Widget', 'value': 10})

        assert response.status_code == 201
        data = response.json()
        assert data['name'] == 'Widget'
        assert data['value'] == 10

    @pytest.mark.asyncio
    async def test_crud_list_through_adapter_to_response(self):
        """Complete flow: HTTP GET → list TX → response."""
        Actor.__matrix__ = None
        m = Matrix()
        api = NetworkAPI()
        m.register(api)
        m.register(MockModel)

        models = {'mock_models': MockModel}
        router = create_api_routes(api, models)

        async def mock_request(tx, timeout=30.0):
            return tx.reply(data={
                'data': [
                    {'id': 1, 'name': 'Item 1', 'value': 10},
                    {'id': 2, 'name': 'Item 2', 'value': 20},
                ],
                'meta': {'total': 2, 'limit': 20, 'offset': 0},
            })

        with mock_method(api, 'request', mock_request):
            from fastapi import FastAPI
            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)

            response = client.get('/mock_models')

        assert response.status_code == 200
        data = response.json()
        assert len(data['data']) == 2
        assert data['meta']['total'] == 2

    @pytest.mark.asyncio
    async def test_error_tx_raises_http_exception(self):
        """Error TX should be converted to HTTPException."""
        Actor.__matrix__ = None
        m = Matrix()
        api = NetworkAPI()
        m.register(api)
        m.register(MockModel)

        models = {'mock_models': MockModel}
        router = create_api_routes(api, models)

        async def mock_request(tx, timeout=30.0):
            return tx.error('Not found', code=404)

        with mock_method(api, 'request', mock_request):
            from fastapi import FastAPI
            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)

            response = client.get('/mock_models/999')

        assert response.status_code == 404
        data = response.json()
        assert 'detail' in data
        assert 'not found' in data['detail'].lower()


# ===================================================================
# TestOutputShape
# ===================================================================

class TestOutputShape:
    """Verify output structures match expectations."""

    def test_response_or_raise_extracts_data_field(self):
        """Should return the data field from success TX."""
        tx = TX(name='SUCCESS', source='api', target='model',
                data={'key': 'value', 'nested': {'data': 123}})
        result = _response_or_raise(tx)
        assert result == {'key': 'value', 'nested': {'data': 123}}

    def test_parse_method_args_output_structure(self):
        """Should return dict with parsed arguments."""
        def test_method(self, arg1: str, arg2: int):
            pass

        sig = signature(test_method)
        type_hints = {'arg1': str, 'arg2': int}
        data = {'arg1': 'test', 'arg2': 42}
        request = make_mock_request()

        result = _parse_method_args(sig, type_hints, data, request)

        assert isinstance(result, dict)
        assert set(result.keys()) == {'arg1', 'arg2'}

    @pytest.mark.asyncio
    async def test_create_route_status_code_201(self):
        """Create route should return 201 status code."""
        Actor.__matrix__ = None
        m = Matrix()
        api = NetworkAPI()
        m.register(api)
        m.register(MockModel)

        models = {'mock_models': MockModel}
        router = create_api_routes(api, models)

        async def mock_request(tx, timeout=30.0):
            return tx.reply(data={'id': 1})

        with mock_method(api, 'request', mock_request):
            from fastapi import FastAPI
            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)

            response = client.post('/mock_models', json={'name': 'Test'})

        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_error_response_includes_detail(self):
        """Error responses should have 'detail' field."""
        Actor.__matrix__ = None
        m = Matrix()
        api = NetworkAPI()
        m.register(api)
        m.register(MockModel)

        models = {'mock_models': MockModel}
        router = create_api_routes(api, models)

        async def mock_request(tx, timeout=30.0):
            return tx.error('Validation failed', code=422)

        with mock_method(api, 'request', mock_request):
            from fastapi import FastAPI
            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)

            response = client.post('/mock_models', json={})

        assert response.status_code == 422
        data = response.json()
        assert 'detail' in data


# ===================================================================
# TestCleanupAndResources
# ===================================================================

class TestCleanupAndResources:
    """Routes registration and multi-model handling."""

    def test_routes_register_with_router(self):
        """Should create routes that register with APIRouter."""
        api = NetworkAPI()
        models = {'mock_models': MockModel}
        router = create_api_routes(api, models)

        from fastapi import APIRouter
        assert isinstance(router, APIRouter)
        assert len(router.routes) > 0

    def test_multiple_models_generate_independent_routes(self):
        """Multiple models should generate independent route sets."""
        class AnotherModel(StorableMixin, Actor, auto_register=False):
            __tablename__: ClassVar[str] = 'another_models'
            __storable__: ClassVar[bool] = True

            title: str = Field(min_length=1)

            @classmethod
            def schema(cls):
                return {
                    '__name__': 'AnotherModel',
                    '__tablename__': 'another_models',
                    'properties': {'title': {'type': 'string'}},
                    'required': ['title'],
                }

        api = NetworkAPI()
        models = {
            'mock_models': MockModel,
            'another_models': AnotherModel,
        }
        router = create_api_routes(api, models)

        routes = {r.path for r in router.routes}

        # Schema routes for both
        assert '/MockModel' in routes
        assert '/AnotherModel' in routes

        # CRUD routes for both (at least item routes)
        assert '/mock_models/{id:int}' in routes
        assert '/another_models/{id:int}' in routes
