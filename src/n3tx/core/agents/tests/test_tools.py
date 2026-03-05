"""Tests for tool discovery and function generation."""

import inspect
import pytest
from pydantic import Field

from n3tx.core.actors.actor import Actor
from n3tx.core.actors.matrix import Matrix
from n3tx.core.models.actor_model import ActorModel
from n3tx.core.storage.sqlite_storage import SQLiteStorage
from n3tx.core.utils.decorators import expose_route
from n3tx.core.utils.registrar import register_model
from n3tx.core.agents.tools import (
    ToolSpec, discover_tools, create_tool_function, make_tool,
    _crud_tool_specs, _method_tool_specs,
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
