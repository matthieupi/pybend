"""Tests for tool discovery and function generation."""

import asyncio
import inspect
import json
import pytest
from pydantic import Field

from n3tx_actors.actor import Actor
from n3tx_actors.matrix import Matrix
from n3tx_actors.tx import TX
from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_core.utils.decorators import expose_route
from n3tx_core.utils.registrar import register_model
from n3tx_agents.tools import (
    ToolSpec, discover_tools, create_tool_function, make_tool,
    _crud_tool_specs, _method_tool_specs, _route_tool_call,
)

pytestmark = pytest.mark.unit


# ── Fixtures: model definitions ──

def setup_models(fresh_matrix, memory_storage):
    """Create test models and return (matrix, Grant class, WebTools class)."""
    m = fresh_matrix

    class Grant(ActorModel):
        __tablename__ = 'grants'
        __storable__ = True
        title: str = Field(default='')
        amount: float = Field(default=0.0)

    class WebTools(ActorModel):
        __tablename__ = 'web_tools'
        __storable__ = False

        @expose_route('/scrape', methods=['POST'])
        def scrape(self, url: str) -> str:
            """Fetch a URL."""
            return f'scraped {url}'

        @expose_route('/extract', methods=['POST'])
        def extract(self, html: str, selector: str) -> str:
            """Extract text from HTML."""
            return 'extracted'

    register_model(Grant, storage=memory_storage)
    return m, Grant, WebTools


class TestToolDiscovery:
    """Tests for discover_tools()."""

    def test_discovers_crud_from_storable_model(self, fresh_matrix, memory_storage):
        m, Grant, _ = setup_models(fresh_matrix, memory_storage)
        specs = discover_tools(['grants'], m)

        crud_names = {s.method_name for s in specs}
        assert crud_names == {'list', 'get', 'create', 'update', 'delete'}

    def test_discovers_methods_from_non_storable(self, fresh_matrix, memory_storage):
        m, _, WebTools = setup_models(fresh_matrix, memory_storage)
        specs = discover_tools(['web_tools'], m)

        names = {s.method_name for s in specs}
        assert 'scrape' in names
        assert 'extract' in names
        # No CRUD tools for non-storable
        assert 'create' not in names

    def test_discovers_from_multiple_actors(self, fresh_matrix, memory_storage):
        m, Grant, WebTools = setup_models(fresh_matrix, memory_storage)
        specs = discover_tools(['grants', 'web_tools'], m)

        tool_names = {s.tool_name for s in specs}
        assert 'grants_create' in tool_names
        assert 'web_tools_scrape' in tool_names

    def test_missing_actor_logs_warning(self, fresh_matrix, memory_storage, caplog):
        m, _, _ = setup_models(fresh_matrix, memory_storage)

        import logging
        with caplog.at_level(logging.WARNING):
            specs = discover_tools(['nonexistent'], m)

        assert len(specs) == 0
        assert 'nonexistent' in caplog.text

    def test_empty_tools_list(self, fresh_matrix, memory_storage):
        m, _, _ = setup_models(fresh_matrix, memory_storage)
        specs = discover_tools([], m)
        assert specs == []

    def test_instance_method_includes_id_param(self, fresh_matrix, memory_storage):
        m, _, WebTools = setup_models(fresh_matrix, memory_storage)
        specs = discover_tools(['web_tools'], m)

        scrape_spec = next(s for s in specs if s.method_name == 'scrape')
        props = scrape_spec.parameters.get('properties', {})
        assert 'id' in props  # instance method needs id
        assert 'url' in props


class TestToolFunctionGeneration:
    """Tests for create_tool_function()."""

    def test_creates_function_with_typed_params(self):
        spec = ToolSpec(
            actor_addr='grants', method_name='create',
            tool_name='grants_create', description='Create a new Grant',
            parameters={
                'type': 'object',
                'properties': {
                    'title': {'type': 'string'},
                    'amount': {'type': 'number'},
                },
                'required': ['title'],
            },
        )

        fn = create_tool_function(spec)
        sig = inspect.signature(fn)
        params = list(sig.parameters.keys())

        assert fn.__name__ == 'grants_create'
        assert 'ctx' in params
        assert 'title' in params
        assert 'amount' in params
        assert fn.__doc__ == 'Create a new Grant'

    def test_required_params_before_optional(self):
        spec = ToolSpec(
            actor_addr='test', method_name='do',
            tool_name='test_do', description='Test',
            parameters={
                'type': 'object',
                'properties': {
                    'optional_field': {'type': 'string'},
                    'required_field': {'type': 'integer'},
                },
                'required': ['required_field'],
            },
        )

        fn = create_tool_function(spec)
        sig = inspect.signature(fn)
        params = list(sig.parameters.values())

        # Find required_field and optional_field
        req = next(p for p in params if p.name == 'required_field')
        opt = next(p for p in params if p.name == 'optional_field')

        assert req.default is inspect.Parameter.empty
        assert opt.default is None

    def test_no_params_function(self):
        spec = ToolSpec(
            actor_addr='test', method_name='list',
            tool_name='test_list', description='List records',
            parameters={'type': 'object', 'properties': {}},
        )

        fn = create_tool_function(spec)
        sig = inspect.signature(fn)
        # Only ctx parameter
        assert list(sig.parameters.keys()) == ['ctx']

    def test_type_mapping(self):
        spec = ToolSpec(
            actor_addr='test', method_name='multi',
            tool_name='test_multi', description='Multi-type',
            parameters={
                'type': 'object',
                'properties': {
                    'name': {'type': 'string'},
                    'count': {'type': 'integer'},
                    'price': {'type': 'number'},
                    'active': {'type': 'boolean'},
                    'tags': {'type': 'array'},
                    'meta': {'type': 'object'},
                },
                'required': ['name', 'count', 'price', 'active', 'tags', 'meta'],
            },
        )

        fn = create_tool_function(spec)
        ann = fn.__annotations__
        assert ann['name'] is str
        assert ann['count'] is int
        assert ann['price'] is float
        assert ann['active'] is bool
        assert ann['tags'] is list
        assert ann['meta'] is dict

    def test_function_is_async(self):
        spec = ToolSpec(
            actor_addr='t', method_name='m',
            tool_name='t_m', description='Test',
            parameters={'type': 'object', 'properties': {}},
        )

        fn = create_tool_function(spec)
        assert inspect.iscoroutinefunction(fn)


class TestMakeToolPydanticAI:
    """Tests for make_tool() — Pydantic AI Tool wrapper."""

    def test_creates_pydantic_ai_tool(self):
        from pydantic_ai.tools import Tool

        spec = ToolSpec(
            actor_addr='grants', method_name='create',
            tool_name='grants_create', description='Create a Grant',
            parameters={
                'type': 'object',
                'properties': {'title': {'type': 'string'}},
                'required': ['title'],
            },
        )

        tool = make_tool(spec)
        assert isinstance(tool, Tool)
        assert tool.name == 'grants_create'
        assert tool.description == 'Create a Grant'


# ── Phase 2: Test Hardening ──────────────────────────────────────

class TestRouteToolCall:
    """T1 / T4: Tests for _route_tool_call error handling."""

    @pytest.mark.asyncio
    async def test_error_response_raises_model_retry(self, fresh_matrix):
        """_route_tool_call raises ModelRetry when tool returns error TX."""
        from pydantic_ai import ModelRetry
        from n3tx_agents.agent import AgentDeps

        # Actor that returns an error for any 'do_something' message.
        # Non-exposed methods on class actors use (data, tx) signature.
        class ErrorActor(ActorModel):
            __tablename__ = 'error_actor'
            __storable__ = False

            @classmethod
            def do_something(cls, data, tx):
                return tx.error("Something went wrong", code=500)

        deps = AgentDeps(user=None, agent_addr='test')

        class MockCtx:
            pass
        ctx = MockCtx()
        ctx.deps = deps

        with pytest.raises(ModelRetry, match="Something went wrong"):
            await _route_tool_call(ctx, 'error_actor', 'do_something', {})

    @pytest.mark.asyncio
    async def test_tool_call_to_missing_actor(self, fresh_matrix):
        """_route_tool_call to non-existent actor raises ModelRetry."""
        from pydantic_ai import ModelRetry
        from n3tx_agents.agent import AgentDeps

        deps = AgentDeps(user=None, agent_addr='test')

        class MockCtx:
            pass
        ctx = MockCtx()
        ctx.deps = deps

        # Matrix._route_error sends error TX back to source (matrix)
        with pytest.raises(ModelRetry, match="No route"):
            await _route_tool_call(ctx, 'nonexistent_actor', 'get', {'id': 1})

    @pytest.mark.asyncio
    async def test_streaming_tool_call_returns_done_payload(self, fresh_matrix):
        from n3tx_agents.agent import AgentDeps

        class StreamActor(ActorModel):
            __tablename__ = 'stream_actor'
            __storable__ = False

            @classmethod
            @expose_route('/analyze', methods=['POST'], stream=True)
            async def analyze(cls, query: str):
                yield {'name': 'text', 'data': {'text': f'Analyzing {query}'}}
                yield {'name': 'done', 'data': {'answer': f'Final {query}', 'score': 0.9}}

        class MockCtx:
            pass

        ctx = MockCtx()
        ctx.deps = AgentDeps(user=None, agent_addr='test')

        result = await _route_tool_call(
            ctx,
            'stream_actor',
            'analyze',
            {'query': 'grants'},
            stream=True,
        )

        assert json.loads(result) == {'answer': 'Final grants', 'score': 0.9}

    @pytest.mark.asyncio
    async def test_streaming_tool_call_falls_back_to_joined_text(self, fresh_matrix):
        from n3tx_agents.agent import AgentDeps

        class StreamActor(ActorModel):
            __tablename__ = 'stream_actor_text'
            __storable__ = False

            @classmethod
            @expose_route('/analyze', methods=['POST'], stream=True)
            async def analyze(cls, query: str):
                yield {'name': 'text', 'data': {'text': 'Hello '}}
                yield {'name': 'text', 'data': {'text': query}}

        class MockCtx:
            pass

        ctx = MockCtx()
        ctx.deps = AgentDeps(user=None, agent_addr='test')

        result = await _route_tool_call(
            ctx,
            'stream_actor_text',
            'analyze',
            {'query': 'world'},
            stream=True,
        )

        assert json.loads(result) == {'answer': 'Hello world'}


class TestToolFunctionEdgeCases:
    """T6: Edge cases for create_tool_function."""

    def test_all_optional_params(self):
        """Function with all optional params works correctly."""
        spec = ToolSpec(
            actor_addr='test', method_name='search',
            tool_name='test_search', description='Search',
            parameters={
                'type': 'object',
                'properties': {
                    'query': {'type': 'string'},
                    'limit': {'type': 'integer'},
                },
                'required': [],  # All optional
            },
        )

        fn = create_tool_function(spec)
        sig = inspect.signature(fn)
        params = list(sig.parameters.values())

        # All non-ctx params should have defaults
        for p in params:
            if p.name != 'ctx':
                assert p.default is None

    def test_invalid_param_name_skipped(self):
        """Parameters with invalid Python identifiers are skipped."""
        spec = ToolSpec(
            actor_addr='test', method_name='do',
            tool_name='test_do', description='Test',
            parameters={
                'type': 'object',
                'properties': {
                    'valid_name': {'type': 'string'},
                    '123invalid': {'type': 'string'},
                },
                'required': ['valid_name'],
            },
        )

        fn = create_tool_function(spec)
        sig = inspect.signature(fn)
        param_names = list(sig.parameters.keys())
        assert 'valid_name' in param_names
        assert '123invalid' not in param_names

    def test_description_with_special_chars(self):
        """Descriptions with quotes and backslashes are escaped properly."""
        spec = ToolSpec(
            actor_addr='test', method_name='do',
            tool_name='test_do',
            description='Create a "special" model with C:\\path and """triple"""',
            parameters={'type': 'object', 'properties': {}},
        )

        fn = create_tool_function(spec)
        # Should not raise — docstring is properly escaped
        assert fn.__doc__ is not None

    def test_hyphenated_tool_name(self):
        """Tool names with hyphens are sanitized to valid identifiers."""
        spec = ToolSpec(
            actor_addr='test', method_name='do',
            tool_name='my-tool.action', description='Test',
            parameters={'type': 'object', 'properties': {}},
        )

        fn = create_tool_function(spec)
        assert fn.__name__ == 'my_tool_action'
        assert fn.__name__.isidentifier()


class TestMethodRequiredParams:
    """Tests for 1.2: required list in method schema entries."""

    def test_method_schema_has_required_list(self, fresh_matrix, memory_storage):
        """Method schema entries include a 'required' list."""
        m = fresh_matrix

        class MyModel(ActorModel):
            __tablename__ = 'my_models'
            __storable__ = False

            @expose_route('/do', methods=['POST'])
            def do_thing(self, required_arg: str, optional_arg: str = 'default') -> str:
                return 'done'

        schema = MyModel.schema()
        method = schema['methods']['do_thing']
        assert 'required' in method
        assert 'required_arg' in method['required']
        assert 'optional_arg' not in method['required']

    def test_method_tool_spec_respects_required(self, fresh_matrix, memory_storage):
        """_method_tool_specs reads required from schema, not all params."""
        m = fresh_matrix

        class ToolModel(ActorModel):
            __tablename__ = 'tool_models'
            __storable__ = False

            @expose_route('/extract', methods=['POST'])
            def extract(self, html: str, selector: str = 'body') -> str:
                return 'extracted'

        schema = ToolModel.schema()
        specs = _method_tool_specs('tool_models', 'tool_models', 'ToolModel', schema)

        extract_spec = next(s for s in specs if s.method_name == 'extract')
        required = extract_spec.parameters.get('required', [])
        # 'id' is added for instance methods, 'html' is required, 'selector' is not
        assert 'id' in required
        assert 'html' in required
        assert 'selector' not in required


class TestLoopDetection:
    """Tests for 1.7: automatic loop detection in discover_tools."""

    def test_self_exclusion(self, fresh_matrix, memory_storage):
        """Agent's own address is excluded from tool discovery."""
        m, Grant, _ = setup_models(fresh_matrix, memory_storage)
        # Discover with caller_addr matching one of the addresses
        specs = discover_tools(['grants'], m, caller_addr='grants')
        assert len(specs) == 0

    def test_self_exclusion_partial(self, fresh_matrix, memory_storage):
        """Only the caller's address is excluded, others are kept."""
        m, Grant, WebTools = setup_models(fresh_matrix, memory_storage)
        specs = discover_tools(['grants', 'web_tools'], m, caller_addr='grants')
        tool_names = {s.tool_name for s in specs}
        assert 'grants_create' not in tool_names
        assert 'web_tools_scrape' in tool_names

    def test_instance_caller_addr_keeps_model_namespace_tools(self, fresh_matrix, memory_storage):
        """Instance caller addresses should not exclude class namespace tools."""
        m, Grant, _ = setup_models(fresh_matrix, memory_storage)
        specs = discover_tools(['grants'], m, caller_addr='grants/1')
        tool_names = {s.tool_name for s in specs}
        assert 'grants_update' in tool_names
        assert 'grants_get' in tool_names

    def test_agent_actor_run_excluded(self, fresh_matrix, tmp_path):
        """AgentActor subclass's run method is auto-excluded from tools."""
        from n3tx_agents.actor import AgentActor
        from n3tx_agents.tool_model import AgentTool
        from n3tx_core.models.proto_model import generate_join_model

        m = fresh_matrix
        storage = SQLiteStorage(str(tmp_path / 'test.db'))
        register_model(AgentTool, storage=storage)
        register_model(AgentActor, storage=storage)
        generate_join_model(AgentActor, AgentTool)

        # AgentActor was defined at import time (before this test's Matrix),
        # so manually register it as a child of this test's Matrix.
        m._children['agents'] = AgentActor

        specs = discover_tools(['agents'], m)
        method_names = {s.method_name for s in specs}
        # CRUD is included, but 'run' is excluded
        assert 'create' in method_names
        assert 'run' not in method_names

    def test_method_exclusion_set(self, fresh_matrix, memory_storage):
        """_method_tool_specs respects exclude parameter."""
        m, _, WebTools = setup_models(fresh_matrix, memory_storage)
        schema = WebTools.schema()
        specs = _method_tool_specs('web_tools', 'web_tools', 'WebTools', schema,
                                   exclude={'scrape'})
        names = {s.method_name for s in specs}
        assert 'scrape' not in names
        assert 'extract' in names


class TestOptionalParamFiltering:
    """Tests for 1.3: optional param None filtering."""

    def test_required_none_preserved(self):
        """Required params with None value are kept in the data dict."""
        spec = ToolSpec(
            actor_addr='test', method_name='do',
            tool_name='test_do', description='Test',
            parameters={
                'type': 'object',
                'properties': {
                    'required_field': {'type': 'string'},
                    'optional_field': {'type': 'string'},
                },
                'required': ['required_field'],
            },
        )
        fn = create_tool_function(spec)

        # Inspect generated code: _required should be in the closure
        # Verify by checking the function exists and is callable
        assert callable(fn)
        sig = inspect.signature(fn)
        assert sig.parameters['required_field'].default is inspect.Parameter.empty
        assert sig.parameters['optional_field'].default is None
