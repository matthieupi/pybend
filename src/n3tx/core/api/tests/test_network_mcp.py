"""
Test plan for network_mcp
==========================

UNIT TESTS — behavior validation
  - test_init_default_addr_is_mcp
  - test_init_custom_addr
  - test_init_auto_register_false
  - test_invalidate_cache_clears_tools_cache
  - test_schema_to_mcp_tools_returns_list
  - test_schema_to_mcp_tools_includes_crud_tools
  - test_schema_to_mcp_tools_includes_custom_method_tools
  - test_schema_to_mcp_tools_empty_for_missing_tablename
  - test_crud_tool_specs_list_action
  - test_crud_tool_specs_get_action
  - test_crud_tool_specs_create_action
  - test_crud_tool_specs_update_action
  - test_crud_tool_specs_delete_action
  - test_crud_tool_specs_filters_read_only_fields
  - test_crud_tool_specs_filters_protected_fields
  - test_crud_tool_specs_filters_display_false_fields
  - test_crud_tool_specs_writable_required_subset
  - test_parse_tool_name_standard_format
  - test_parse_tool_name_underscore_in_tablename
  - test_parse_tool_name_single_part_defaults_to_list
  - test_custom_method_tool_filters_user_param

INTEGRATION TESTS (partial) — adjacent pairs
  - test_handle_tools_list_discovers_registered_models
  - test_handle_tools_list_uses_cache_on_second_call
  - test_handle_tools_list_skips_non_type_children
  - test_handle_tools_list_skips_children_without_schema
  - test_handle_tools_list_continues_on_schema_error
  - test_handle_tools_list_continues_on_schema_timeout
  - test_handle_tools_call_routes_to_correct_model
  - test_handle_tools_call_routes_crud_action
  - test_handle_tools_call_routes_custom_method
  - test_handle_tools_call_returns_success_content
  - test_handle_tools_call_returns_error_content
  - test_handle_tools_call_timeout_response
  - test_handle_jsonrpc_initialize
  - test_handle_jsonrpc_ping
  - test_handle_jsonrpc_tools_list
  - test_handle_jsonrpc_tools_call
  - test_handle_jsonrpc_unknown_method
  - test_handle_jsonrpc_exception_handling

INTEGRATION TESTS (full pipeline) — end-to-end chains
  - test_jsonrpc_to_tools_list_to_schema_requests
  - test_jsonrpc_to_tools_call_to_crud_tx
  - test_jsonrpc_error_response_format

OUTPUT SHAPE — serialization contracts
  - test_mcp_tool_shape_has_required_keys
  - test_mcp_tool_inputschema_is_valid_json_schema
  - test_jsonrpc_response_has_jsonrpc_field
  - test_jsonrpc_response_has_id_field
  - test_jsonrpc_response_has_result_or_error
  - test_jsonrpc_error_code_for_method_not_found
  - test_jsonrpc_error_code_for_parse_error
  - test_jsonrpc_error_code_for_internal_error
  - test_tools_call_content_array_structure

FASTAPI ROUTES
  - test_create_mcp_routes_post_endpoint
  - test_create_mcp_routes_get_tools_endpoint
  - test_mcp_jsonrpc_route_parse_error
  - test_mcp_jsonrpc_route_success
  - test_list_tools_route_returns_count
"""

import asyncio
import pytest
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from typing import ClassVar

from pydantic import Field

from n3tx.core.api.network_mcp import NetworkMCP, create_mcp_routes
from n3tx.core.actors.tx import TX
from n3tx.core.actors.actor import Actor
from n3tx.core.actors.matrix import Matrix
from n3tx.core.models.actor_model import ActorModel

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


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture(autouse=True)
def reset_actor_state():
    """Save and restore Actor/Matrix class-level state between tests."""
    saved_matrix = Actor.__matrix__
    saved_children = Actor.__children__.copy()
    saved_matrix_children = Matrix.__children__.copy()

    yield

    Actor.__matrix__ = saved_matrix
    Actor.__children__ = saved_children
    Matrix.__children__ = saved_matrix_children


@pytest.fixture
def matrix():
    """Create a fresh Matrix instance for each test."""
    Actor.__matrix__ = None
    return Matrix()


@pytest.fixture
def mcp_adapter(matrix):
    """Create a NetworkMCP adapter registered with the test Matrix."""
    adapter = NetworkMCP()
    matrix.register(adapter)
    return adapter


@pytest.fixture
def mock_model():
    """Create a mock ActorModel class for testing."""
    class TestModel(ActorModel, auto_register=False):
        __tablename__: ClassVar[str] = 'test_models'
        __storable__: ClassVar[bool] = True
        name: str = Field(min_length=1, max_length=100)
        value: int = Field(ge=0, default=0)
        internal: str = Field(default='', json_schema_extra={'ui': {'display': False}})
        protected: str = Field(default='', json_schema_extra={'ui': {'protected': True}})

        def custom_method(self, arg1: str, arg2: int = 10) -> str:
            """Custom method exposed via schema."""
            return f"{arg1}_{arg2}"

    # Inject a minimal schema method
    @classmethod
    def schema_method(cls):
        return {
            '__name__': 'TestModel',
            '__tablename__': 'test_models',
            'properties': {
                'id': {'type': 'integer'},
                'name': {'type': 'string', 'minLength': 1, 'maxLength': 100},
                'value': {'type': 'integer', 'minimum': 0, 'default': 0},
                'internal': {'type': 'string', 'default': '', 'ui': {'display': False}},
                'protected': {'type': 'string', 'default': '', 'ui': {'protected': True}},
            },
            'required': ['name'],
            'methods': {
                'custom_method': {
                    'description': 'Custom method',
                    'parameters': {
                        'arg1': {'type': 'string'},
                        'arg2': {'type': 'integer', 'default': 10},
                        'user': {'type': 'object'},  # Should be filtered
                    },
                    'returns': {'type': 'string'},
                },
            },
        }

    TestModel.schema = schema_method
    return TestModel


# ===================================================================
# TestNetworkMCPInit
# ===================================================================

class TestNetworkMCPInit:
    """NetworkMCP initialization and configuration."""

    def test_init_default_addr_is_mcp(self, matrix):
        adapter = NetworkMCP()
        assert adapter.addr == 'mcp'

    def test_init_custom_addr(self, matrix):
        adapter = NetworkMCP(addr='custom_mcp')
        assert adapter.addr == 'custom_mcp'

    def test_init_auto_register_false(self):
        """NetworkMCP has auto_register=False, requires manual registration."""
        Actor.__matrix__ = None
        m = Matrix()
        # Creating without registering should not appear in Matrix children
        adapter = NetworkMCP(addr='test_mcp')
        assert 'test_mcp' not in m.children

    def test_invalidate_cache_clears_tools_cache(self, mcp_adapter):
        # Set a fake cache using the internal attribute directly
        mcp_adapter._tools_cache = [{'name': 'fake_tool'}]
        assert mcp_adapter._tools_cache is not None

        mcp_adapter.invalidate_cache()
        assert mcp_adapter._tools_cache is None


# ===================================================================
# TestSchemaToMCPTools
# ===================================================================

class TestSchemaToMCPTools:
    """_schema_to_mcp_tools() converts model schemas to MCP tool definitions."""

    def test_schema_to_mcp_tools_returns_list(self, mcp_adapter):
        schema = {
            '__tablename__': 'products',
            '__name__': 'Product',
            'properties': {'name': {'type': 'string'}},
            'required': ['name'],
        }
        tools = mcp_adapter._schema_to_mcp_tools(schema)
        assert isinstance(tools, list)

    def test_schema_to_mcp_tools_includes_crud_tools(self, mcp_adapter):
        schema = {
            '__tablename__': 'products',
            '__name__': 'Product',
            'properties': {'name': {'type': 'string'}},
            'required': [],
        }
        tools = mcp_adapter._schema_to_mcp_tools(schema)
        tool_names = [t['name'] for t in tools]

        assert 'products_list' in tool_names
        assert 'products_get' in tool_names
        assert 'products_create' in tool_names
        assert 'products_update' in tool_names
        assert 'products_delete' in tool_names

    def test_schema_to_mcp_tools_includes_custom_method_tools(self, mcp_adapter):
        schema = {
            '__tablename__': 'products',
            '__name__': 'Product',
            'properties': {'name': {'type': 'string'}},
            'required': [],
            'methods': {
                'favorite': {
                    'description': 'Mark as favorite',
                    'parameters': {'user_id': {'type': 'integer'}},
                },
            },
        }
        tools = mcp_adapter._schema_to_mcp_tools(schema)
        tool_names = [t['name'] for t in tools]

        assert 'products_favorite' in tool_names

    def test_schema_to_mcp_tools_empty_for_missing_tablename(self, mcp_adapter):
        schema = {'__name__': 'NoTable', 'properties': {}}
        tools = mcp_adapter._schema_to_mcp_tools(schema)
        assert tools == []

    def test_custom_method_tool_filters_user_param(self, mcp_adapter):
        """User parameter should be filtered from MCP tool schema."""
        schema = {
            '__tablename__': 'products',
            '__name__': 'Product',
            'properties': {},
            'methods': {
                'comment': {
                    'description': 'Add comment',
                    'parameters': {
                        'text': {'type': 'string'},
                        'user': {'type': 'object'},  # Should be filtered
                    },
                },
            },
        }
        tools = mcp_adapter._schema_to_mcp_tools(schema)
        comment_tool = next(t for t in tools if t['name'] == 'products_comment')

        assert 'text' in comment_tool['inputSchema']['properties']
        assert 'user' not in comment_tool['inputSchema']['properties']


# ===================================================================
# TestCrudToolSpecs
# ===================================================================

class TestCrudToolSpecs:
    """_crud_tool_specs() generates correct CRUD operation tool definitions."""

    def test_crud_tool_specs_list_action(self, mcp_adapter):
        schema = {
            '__tablename__': 'products',
            '__name__': 'Product',
            'properties': {'name': {'type': 'string'}},
            'required': [],
        }
        specs = list(mcp_adapter._crud_tool_specs(schema, 'products', 'Product'))
        list_spec = next(s for s in specs if s[0] == 'list')

        assert list_spec[1] == 'List Product records'
        assert 'limit' in list_spec[2]['properties']
        assert 'offset' in list_spec[2]['properties']

    def test_crud_tool_specs_get_action(self, mcp_adapter):
        schema = {
            '__tablename__': 'products',
            'properties': {},
            'required': [],
        }
        specs = list(mcp_adapter._crud_tool_specs(schema, 'products', 'Product'))
        get_spec = next(s for s in specs if s[0] == 'get')

        assert 'id' in get_spec[2]['properties']
        assert 'id' in get_spec[2]['required']

    def test_crud_tool_specs_create_action(self, mcp_adapter):
        schema = {
            '__tablename__': 'products',
            'properties': {
                'name': {'type': 'string'},
                'price': {'type': 'number'},
            },
            'required': ['name'],
        }
        specs = list(mcp_adapter._crud_tool_specs(schema, 'products', 'Product'))
        create_spec = next(s for s in specs if s[0] == 'create')

        assert 'name' in create_spec[2]['properties']
        assert 'price' in create_spec[2]['properties']
        assert 'name' in create_spec[2]['required']

    def test_crud_tool_specs_update_action(self, mcp_adapter):
        schema = {
            '__tablename__': 'products',
            'properties': {'name': {'type': 'string'}},
            'required': ['name'],
        }
        specs = list(mcp_adapter._crud_tool_specs(schema, 'products', 'Product'))
        update_spec = next(s for s in specs if s[0] == 'update')

        assert 'id' in update_spec[2]['properties']
        assert 'name' in update_spec[2]['properties']
        assert 'id' in update_spec[2]['required']
        assert 'name' not in update_spec[2]['required']  # Not required for update

    def test_crud_tool_specs_delete_action(self, mcp_adapter):
        schema = {
            '__tablename__': 'products',
            'properties': {},
            'required': [],
        }
        specs = list(mcp_adapter._crud_tool_specs(schema, 'products', 'Product'))
        delete_spec = next(s for s in specs if s[0] == 'delete')

        assert 'id' in delete_spec[2]['properties']
        assert 'id' in delete_spec[2]['required']

    def test_crud_tool_specs_filters_read_only_fields(self, mcp_adapter):
        """ID field should be excluded from create/update writable fields."""
        schema = {
            '__tablename__': 'products',
            'properties': {
                'id': {'type': 'integer'},
                'name': {'type': 'string'},
            },
            'required': [],
        }
        specs = list(mcp_adapter._crud_tool_specs(schema, 'products', 'Product'))
        create_spec = next(s for s in specs if s[0] == 'create')

        assert 'id' not in create_spec[2]['properties']
        assert 'name' in create_spec[2]['properties']

    def test_crud_tool_specs_filters_protected_fields(self, mcp_adapter):
        """Protected fields should be excluded from create/update."""
        schema = {
            '__tablename__': 'products',
            'properties': {
                'name': {'type': 'string'},
                'secret': {'type': 'string', 'ui': {'protected': True}},
            },
            'required': [],
        }
        specs = list(mcp_adapter._crud_tool_specs(schema, 'products', 'Product'))
        create_spec = next(s for s in specs if s[0] == 'create')

        assert 'name' in create_spec[2]['properties']
        assert 'secret' not in create_spec[2]['properties']

    def test_crud_tool_specs_filters_display_false_fields(self, mcp_adapter):
        """Fields with display=False should be excluded from create/update."""
        schema = {
            '__tablename__': 'products',
            'properties': {
                'name': {'type': 'string'},
                'internal': {'type': 'string', 'ui': {'display': False}},
            },
            'required': [],
        }
        specs = list(mcp_adapter._crud_tool_specs(schema, 'products', 'Product'))
        create_spec = next(s for s in specs if s[0] == 'create')

        assert 'name' in create_spec[2]['properties']
        assert 'internal' not in create_spec[2]['properties']

    def test_crud_tool_specs_writable_required_subset(self, mcp_adapter):
        """Required fields should only include writable required fields."""
        schema = {
            '__tablename__': 'products',
            'properties': {
                'id': {'type': 'integer'},
                'name': {'type': 'string'},
                'secret': {'type': 'string', 'ui': {'protected': True}},
            },
            'required': ['id', 'name', 'secret'],
        }
        specs = list(mcp_adapter._crud_tool_specs(schema, 'products', 'Product'))
        create_spec = next(s for s in specs if s[0] == 'create')

        assert create_spec[2]['required'] == ['name']


# ===================================================================
# TestParseToolName
# ===================================================================

class TestParseToolName:
    """_parse_tool_name() splits tool names into (model_addr, action)."""

    def test_parse_tool_name_standard_format(self, mcp_adapter):
        model_addr, action = mcp_adapter._parse_tool_name('products_create')
        assert model_addr == 'products'
        assert action == 'create'

    def test_parse_tool_name_underscore_in_tablename(self, mcp_adapter):
        """Only the last underscore should split model from action."""
        model_addr, action = mcp_adapter._parse_tool_name('user_profiles_update')
        assert model_addr == 'user_profiles'
        assert action == 'update'

    def test_parse_tool_name_single_part_defaults_to_list(self, mcp_adapter):
        """Single-part name with no underscore defaults to list action."""
        model_addr, action = mcp_adapter._parse_tool_name('products')
        assert model_addr == 'products'
        assert action == 'list'


# ===================================================================
# TestHandleToolsList
# ===================================================================

class TestHandleToolsList:
    """handle_tools_list() discovers registered models and builds MCP tools."""

    @pytest.mark.asyncio
    async def test_handle_tools_list_discovers_registered_models(self, matrix, mcp_adapter, mock_model):
        """Should request schema from each registered model."""
        matrix.register(mock_model)

        # Mock request to return schema
        async def mock_request(tx, timeout=30.0):
            if tx.name == 'schema' and tx.target == 'test_models':
                return tx.reply(data=mock_model.schema())
            return tx.error('Not found')

        with mock_method(mcp_adapter, 'request', mock_request):
            tools = await mcp_adapter.handle_tools_list()

        tool_names = [t['name'] for t in tools]
        assert 'test_models_list' in tool_names
        assert 'test_models_create' in tool_names
        assert 'test_models_custom_method' in tool_names

    @pytest.mark.asyncio
    async def test_handle_tools_list_uses_cache_on_second_call(self, matrix, mcp_adapter, mock_model):
        """Second call should use cached tools without making new requests."""
        matrix.register(mock_model)

        call_count = 0

        async def mock_request(tx, timeout=30.0):
            nonlocal call_count
            call_count += 1
            if tx.name == 'schema':
                return tx.reply(data=mock_model.schema())
            return tx.error('Not found')

        with mock_method(mcp_adapter, 'request', mock_request):
            tools1 = await mcp_adapter.handle_tools_list()
            tools2 = await mcp_adapter.handle_tools_list()

        assert call_count == 1  # Only called once
        assert tools1 == tools2

    @pytest.mark.asyncio
    async def test_handle_tools_list_skips_non_type_children(self, matrix, mcp_adapter):
        """Should only process class children, not instances."""
        instance = Actor(addr='instance')
        matrix.register(instance)

        async def mock_request(tx, timeout=30.0):
            pytest.fail("Should not make requests for non-type children")

        with mock_method(mcp_adapter, 'request', mock_request):
            tools = await mcp_adapter.handle_tools_list()

        assert tools == []

    @pytest.mark.asyncio
    async def test_handle_tools_list_skips_children_without_schema(self, matrix, mcp_adapter):
        """Should skip children whose schema lacks __tablename__."""
        class NoTableName(Actor, auto_register=False):
            pass

        matrix.register(NoTableName)

        async def mock_request(tx, timeout=30.0):
            # Return a schema without __tablename__
            return tx.reply(data={'__name__': 'NoTableName', 'properties': {}})

        with mock_method(mcp_adapter, 'request', mock_request):
            tools = await mcp_adapter.handle_tools_list()

        assert tools == []

    @pytest.mark.asyncio
    async def test_handle_tools_list_continues_on_schema_error(self, matrix, mcp_adapter, mock_model):
        """Should log warning and continue when schema request returns error."""
        matrix.register(mock_model)

        async def mock_request(tx, timeout=30.0):
            return tx.error('Schema generation failed', code=500)

        with mock_method(mcp_adapter, 'request', mock_request):
            tools = await mcp_adapter.handle_tools_list()

        assert tools == []  # No tools added, but no exception raised

    @pytest.mark.asyncio
    async def test_handle_tools_list_continues_on_schema_timeout(self, matrix, mcp_adapter, mock_model):
        """Should continue when schema request raises exception."""
        matrix.register(mock_model)

        async def mock_request(tx, timeout=30.0):
            raise TimeoutError("Schema request timed out")

        with mock_method(mcp_adapter, 'request', mock_request):
            tools = await mcp_adapter.handle_tools_list()

        assert tools == []  # No tools added, but no exception raised


# ===================================================================
# TestHandleToolsCall
# ===================================================================

class TestHandleToolsCall:
    """handle_tools_call() routes tool calls to the correct model/action."""

    @pytest.mark.asyncio
    async def test_handle_tools_call_routes_to_correct_model(self, mcp_adapter):
        """Should parse tool name and route to target model."""
        async def mock_request(tx, timeout=30.0):
            assert tx.target == 'products'
            assert tx.name == 'list'
            return tx.reply(data={'items': []})

        with mock_method(mcp_adapter, 'request', mock_request):
            result = await mcp_adapter.handle_tools_call('products_list', {})

        assert 'content' in result
        assert result['content'][0]['type'] == 'text'

    @pytest.mark.asyncio
    async def test_handle_tools_call_routes_crud_action(self, mcp_adapter):
        """Should route CRUD actions correctly."""
        async def mock_request(tx, timeout=30.0):
            assert tx.name == 'create'
            assert tx.data == {'name': 'Widget', 'price': 9.99}
            return tx.reply(data={'id': 1, 'name': 'Widget', 'price': 9.99})

        with mock_method(mcp_adapter, 'request', mock_request):
            result = await mcp_adapter.handle_tools_call(
                'products_create',
                {'name': 'Widget', 'price': 9.99}
            )

        assert 'content' in result
        assert '"id": 1' in result['content'][0]['text']

    @pytest.mark.asyncio
    async def test_handle_tools_call_routes_custom_method(self, mcp_adapter):
        """Should route custom method calls correctly."""
        async def mock_request(tx, timeout=30.0):
            assert tx.name == 'favorite'
            assert tx.data == {'product_id': 5}
            return tx.reply(data={'success': True})

        with mock_method(mcp_adapter, 'request', mock_request):
            result = await mcp_adapter.handle_tools_call(
                'products_favorite',
                {'product_id': 5}
            )

        assert 'content' in result
        assert 'success' in result['content'][0]['text']

    @pytest.mark.asyncio
    async def test_handle_tools_call_returns_success_content(self, mcp_adapter):
        """Successful calls return content array with text."""
        async def mock_request(tx, timeout=30.0):
            return tx.reply(data={'result': 'ok'})

        with mock_method(mcp_adapter, 'request', mock_request):
            result = await mcp_adapter.handle_tools_call('products_list', {})

        assert 'content' in result
        assert isinstance(result['content'], list)
        assert len(result['content']) == 1
        assert result['content'][0]['type'] == 'text'
        assert 'result' in result['content'][0]['text']
        assert 'isError' not in result

    @pytest.mark.asyncio
    async def test_handle_tools_call_returns_error_content(self, mcp_adapter):
        """Error responses should include isError flag."""
        async def mock_request(tx, timeout=30.0):
            return tx.error('Product not found', code=404)

        with mock_method(mcp_adapter, 'request', mock_request):
            result = await mcp_adapter.handle_tools_call('products_get', {'id': 999})

        assert result['isError'] is True
        assert 'content' in result
        assert 'not found' in result['content'][0]['text'].lower()

    @pytest.mark.asyncio
    async def test_handle_tools_call_timeout_response(self, mcp_adapter):
        """Timeout errors should be returned as error content."""
        async def mock_request(tx, timeout=30.0):
            raise asyncio.TimeoutError()

        with mock_method(mcp_adapter, 'request', mock_request):
            # This should not raise, but return timeout error
            with pytest.raises(asyncio.TimeoutError):
                await mcp_adapter.handle_tools_call('products_list', {})


# ===================================================================
# TestHandleJSONRPC
# ===================================================================

class TestHandleJSONRPC:
    """handle_jsonrpc() dispatches JSON-RPC 2.0 requests to handlers."""

    @pytest.mark.asyncio
    async def test_handle_jsonrpc_initialize(self, mcp_adapter):
        """Initialize should return protocol version and capabilities."""
        request = {'jsonrpc': '2.0', 'method': 'initialize', 'id': 1}
        response = await mcp_adapter.handle_jsonrpc(request)

        assert response['jsonrpc'] == '2.0'
        assert response['id'] == 1
        assert 'result' in response
        assert response['result']['protocolVersion'] == '2024-11-05'
        assert 'tools' in response['result']['capabilities']
        assert response['result']['serverInfo']['name'] == 'n3tx'

    @pytest.mark.asyncio
    async def test_handle_jsonrpc_ping(self, mcp_adapter):
        """Ping should return empty result."""
        request = {'jsonrpc': '2.0', 'method': 'ping', 'id': 2}
        response = await mcp_adapter.handle_jsonrpc(request)

        assert response['jsonrpc'] == '2.0'
        assert response['id'] == 2
        assert response['result'] == {}

    @pytest.mark.asyncio
    async def test_handle_jsonrpc_tools_list(self, mcp_adapter):
        """tools/list should call handle_tools_list()."""
        async def mock_handle_tools_list():
            return [{'name': 'test_tool', 'description': 'Test', 'inputSchema': {}}]

        with mock_method(mcp_adapter, 'handle_tools_list', mock_handle_tools_list):
            request = {'jsonrpc': '2.0', 'method': 'tools/list', 'id': 3}
            response = await mcp_adapter.handle_jsonrpc(request)

        assert response['jsonrpc'] == '2.0'
        assert response['id'] == 3
        assert 'tools' in response['result']
        assert len(response['result']['tools']) == 1

    @pytest.mark.asyncio
    async def test_handle_jsonrpc_tools_call(self, mcp_adapter):
        """tools/call should call handle_tools_call()."""
        async def mock_handle_tools_call(tool_name, arguments):
            assert tool_name == 'products_list'
            assert arguments == {'limit': 10}
            return {'content': [{'type': 'text', 'text': '[]'}]}

        with mock_method(mcp_adapter, 'handle_tools_call', mock_handle_tools_call):
            request = {
                'jsonrpc': '2.0',
                'method': 'tools/call',
                'params': {'name': 'products_list', 'arguments': {'limit': 10}},
                'id': 4,
            }
            response = await mcp_adapter.handle_jsonrpc(request)

        assert response['jsonrpc'] == '2.0'
        assert response['id'] == 4
        assert 'content' in response['result']

    @pytest.mark.asyncio
    async def test_handle_jsonrpc_unknown_method(self, mcp_adapter):
        """Unknown method should return method not found error."""
        request = {'jsonrpc': '2.0', 'method': 'unknown/method', 'id': 5}
        response = await mcp_adapter.handle_jsonrpc(request)

        assert response['jsonrpc'] == '2.0'
        assert response['id'] == 5
        assert 'error' in response
        assert response['error']['code'] == -32601
        assert 'not found' in response['error']['message'].lower()

    @pytest.mark.asyncio
    async def test_handle_jsonrpc_exception_handling(self, mcp_adapter):
        """Exceptions during handling should return internal error."""
        async def mock_handle_tools_list():
            raise ValueError("Something went wrong")

        with mock_method(mcp_adapter, 'handle_tools_list', mock_handle_tools_list):
            request = {'jsonrpc': '2.0', 'method': 'tools/list', 'id': 6}
            response = await mcp_adapter.handle_jsonrpc(request)

        assert response['jsonrpc'] == '2.0'
        assert response['id'] == 6
        assert 'error' in response
        assert response['error']['code'] == -32603
        assert 'Something went wrong' in response['error']['message']


# ===================================================================
# TestJSONRPCToToolsListToSchemaRequests
# ===================================================================

class TestJSONRPCToToolsListToSchemaRequests:
    """Full pipeline: JSON-RPC request → tools/list → schema requests → tool specs."""

    @pytest.mark.asyncio
    async def test_jsonrpc_to_tools_list_to_schema_requests(self, matrix, mcp_adapter, mock_model):
        """Complete flow from JSON-RPC to discovered tools."""
        matrix.register(mock_model)

        # Mock request to return schema
        async def mock_request(tx, timeout=30.0):
            if tx.name == 'schema' and tx.target == 'test_models':
                return tx.reply(data=mock_model.schema())
            return tx.error('Not found')

        with mock_method(mcp_adapter, 'request', mock_request):
            request = {'jsonrpc': '2.0', 'method': 'tools/list', 'id': 1}
            response = await mcp_adapter.handle_jsonrpc(request)

        assert response['jsonrpc'] == '2.0'
        assert 'result' in response
        assert 'tools' in response['result']
        tools = response['result']['tools']

        tool_names = [t['name'] for t in tools]
        assert 'test_models_list' in tool_names
        assert 'test_models_create' in tool_names
        assert 'test_models_custom_method' in tool_names


# ===================================================================
# TestJSONRPCToToolsCallToCrudTX
# ===================================================================

class TestJSONRPCToToolsCallToCrudTX:
    """Full pipeline: JSON-RPC tools/call → parse → route → CRUD TX → response."""

    @pytest.mark.asyncio
    async def test_jsonrpc_to_tools_call_to_crud_tx(self, mcp_adapter):
        """Complete flow from JSON-RPC call to CRUD TX message."""
        async def mock_request(tx, timeout=30.0):
            # Verify TX is correctly formed
            assert tx.name == 'create'
            assert tx.target == 'products'
            assert tx.source == 'mcp'
            assert tx.data == {'name': 'Widget', 'price': 19.99}
            return tx.reply(data={'id': 1, 'name': 'Widget', 'price': 19.99})

        with mock_method(mcp_adapter, 'request', mock_request):
            request = {
                'jsonrpc': '2.0',
                'method': 'tools/call',
                'params': {
                    'name': 'products_create',
                    'arguments': {'name': 'Widget', 'price': 19.99},
                },
                'id': 10,
            }
            response = await mcp_adapter.handle_jsonrpc(request)

        assert response['jsonrpc'] == '2.0'
        assert response['id'] == 10
        assert 'result' in response
        assert 'content' in response['result']
        assert response['result']['content'][0]['type'] == 'text'
        assert 'Widget' in response['result']['content'][0]['text']


# ===================================================================
# TestJSONRPCErrorResponseFormat
# ===================================================================

class TestJSONRPCErrorResponseFormat:
    """Error responses follow JSON-RPC 2.0 spec."""

    @pytest.mark.asyncio
    async def test_jsonrpc_error_response_format(self, mcp_adapter):
        """Error response should have correct structure."""
        async def mock_request(tx, timeout=30.0):
            return tx.error('Resource not found', code=404)

        with mock_method(mcp_adapter, 'request', mock_request):
            request = {
                'jsonrpc': '2.0',
                'method': 'tools/call',
                'params': {'name': 'products_get', 'arguments': {'id': 999}},
                'id': 20,
            }
            response = await mcp_adapter.handle_jsonrpc(request)

        # Response should still be success at JSON-RPC level,
        # error is in the content
        assert response['jsonrpc'] == '2.0'
        assert response['id'] == 20
        assert 'result' in response
        assert response['result']['isError'] is True


# ===================================================================
# TestMCPToolShape
# ===================================================================

class TestMCPToolShape:
    """MCP tool definitions have required shape."""

    def test_mcp_tool_shape_has_required_keys(self, mcp_adapter):
        """Each tool must have name, description, inputSchema."""
        schema = {
            '__tablename__': 'products',
            '__name__': 'Product',
            'properties': {'name': {'type': 'string'}},
            'required': [],
        }
        tools = mcp_adapter._schema_to_mcp_tools(schema)

        for tool in tools:
            assert 'name' in tool
            assert 'description' in tool
            assert 'inputSchema' in tool
            assert isinstance(tool['name'], str)
            assert isinstance(tool['description'], str)
            assert isinstance(tool['inputSchema'], dict)

    def test_mcp_tool_inputschema_is_valid_json_schema(self, mcp_adapter):
        """inputSchema should be a valid JSON Schema object."""
        schema = {
            '__tablename__': 'products',
            '__name__': 'Product',
            'properties': {
                'name': {'type': 'string', 'minLength': 1},
                'price': {'type': 'number', 'minimum': 0},
            },
            'required': ['name'],
        }
        tools = mcp_adapter._schema_to_mcp_tools(schema)
        create_tool = next(t for t in tools if t['name'] == 'products_create')

        input_schema = create_tool['inputSchema']
        assert input_schema['type'] == 'object'
        assert 'properties' in input_schema
        assert isinstance(input_schema['properties'], dict)
        # Note: ui and access should be stripped from properties
        for prop_name, prop_schema in input_schema['properties'].items():
            assert 'ui' not in prop_schema
            assert 'access' not in prop_schema


# ===================================================================
# TestJSONRPCResponseShape
# ===================================================================

class TestJSONRPCResponseShape:
    """JSON-RPC responses follow spec."""

    @pytest.mark.asyncio
    async def test_jsonrpc_response_has_jsonrpc_field(self, mcp_adapter):
        """All responses must have jsonrpc: '2.0'."""
        request = {'jsonrpc': '2.0', 'method': 'ping', 'id': 1}
        response = await mcp_adapter.handle_jsonrpc(request)
        assert response['jsonrpc'] == '2.0'

    @pytest.mark.asyncio
    async def test_jsonrpc_response_has_id_field(self, mcp_adapter):
        """Response id must match request id."""
        request = {'jsonrpc': '2.0', 'method': 'ping', 'id': 42}
        response = await mcp_adapter.handle_jsonrpc(request)
        assert response['id'] == 42

    @pytest.mark.asyncio
    async def test_jsonrpc_response_has_result_or_error(self, mcp_adapter):
        """Response must have either result or error, not both."""
        # Success case
        request = {'jsonrpc': '2.0', 'method': 'ping', 'id': 1}
        response = await mcp_adapter.handle_jsonrpc(request)
        assert 'result' in response
        assert 'error' not in response

        # Error case
        request = {'jsonrpc': '2.0', 'method': 'invalid', 'id': 2}
        response = await mcp_adapter.handle_jsonrpc(request)
        assert 'error' in response
        assert 'result' not in response

    @pytest.mark.asyncio
    async def test_jsonrpc_error_code_for_method_not_found(self, mcp_adapter):
        """Method not found should use code -32601."""
        request = {'jsonrpc': '2.0', 'method': 'unknown', 'id': 1}
        response = await mcp_adapter.handle_jsonrpc(request)
        assert response['error']['code'] == -32601

    @pytest.mark.asyncio
    async def test_jsonrpc_error_code_for_internal_error(self, mcp_adapter):
        """Internal errors should use code -32603."""
        async def mock_handle_tools_list():
            raise RuntimeError("Internal error")

        with mock_method(mcp_adapter, 'handle_tools_list', mock_handle_tools_list):
            request = {'jsonrpc': '2.0', 'method': 'tools/list', 'id': 1}
            response = await mcp_adapter.handle_jsonrpc(request)

        assert response['error']['code'] == -32603


# ===================================================================
# TestToolsCallContentArrayStructure
# ===================================================================

class TestToolsCallContentArrayStructure:
    """tools/call result content follows MCP format."""

    @pytest.mark.asyncio
    async def test_tools_call_content_array_structure(self, mcp_adapter):
        """Content must be array of objects with type and text."""
        async def mock_request(tx, timeout=30.0):
            return tx.reply(data={'items': [1, 2, 3]})

        with mock_method(mcp_adapter, 'request', mock_request):
            result = await mcp_adapter.handle_tools_call('products_list', {})

        assert 'content' in result
        assert isinstance(result['content'], list)
        assert len(result['content']) >= 1
        for item in result['content']:
            assert 'type' in item
            assert item['type'] == 'text'
            assert 'text' in item
            assert isinstance(item['text'], str)


# ===================================================================
# TestCreateMCPRoutes
# ===================================================================

class TestCreateMCPRoutes:
    """create_mcp_routes() generates FastAPI routes."""

    def test_create_mcp_routes_post_endpoint(self, mcp_adapter):
        """Should create POST /mcp endpoint."""
        router = create_mcp_routes(mcp_adapter)
        routes = [r.path for r in router.routes]
        assert '/mcp' in routes

    def test_create_mcp_routes_get_tools_endpoint(self, mcp_adapter):
        """Should create GET /mcp/tools endpoint."""
        router = create_mcp_routes(mcp_adapter)
        routes = [(r.path, r.methods) for r in router.routes]
        assert ('/mcp/tools', {'GET'}) in routes

    @pytest.mark.asyncio
    async def test_mcp_jsonrpc_route_parse_error(self, mcp_adapter):
        """POST /mcp should return parse error for invalid JSON."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(create_mcp_routes(mcp_adapter))
        client = TestClient(app)

        # Send invalid JSON (plain text)
        response = client.post('/mcp', content='not json', headers={'content-type': 'application/json'})

        assert response.status_code == 400
        data = response.json()
        assert data['jsonrpc'] == '2.0'
        assert data['error']['code'] == -32700
        assert 'parse' in data['error']['message'].lower()

    @pytest.mark.asyncio
    async def test_mcp_jsonrpc_route_success(self, mcp_adapter):
        """POST /mcp should route valid requests to handle_jsonrpc."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(create_mcp_routes(mcp_adapter))
        client = TestClient(app)

        response = client.post('/mcp', json={'jsonrpc': '2.0', 'method': 'ping', 'id': 1})

        assert response.status_code == 200
        data = response.json()
        assert data['jsonrpc'] == '2.0'
        assert data['id'] == 1
        assert data['result'] == {}

    @pytest.mark.asyncio
    async def test_list_tools_route_returns_count(self, matrix, mcp_adapter, mock_model):
        """GET /mcp/tools should return tools and count."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(create_mcp_routes(mcp_adapter))
        client = TestClient(app)

        matrix.register(mock_model)

        # Mock request to return schema
        async def mock_request(tx, timeout=30.0):
            if tx.name == 'schema':
                return tx.reply(data=mock_model.schema())
            return tx.error('Not found')

        with mock_method(mcp_adapter, 'request', mock_request):
            response = client.get('/mcp/tools')

        assert response.status_code == 200
        data = response.json()
        assert 'tools' in data
        assert 'count' in data
        assert data['count'] == len(data['tools'])
        assert data['count'] > 0  # Should have CRUD + custom method tools
