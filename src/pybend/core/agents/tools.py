"""Tool discovery and Pydantic AI tool wrapper generation.

Discovers @expose_route methods and CRUD operations from actor schemas,
creates properly-typed async functions that route calls through Matrix as TX,
and wraps them as Pydantic AI Tool objects.

The generated functions use exec() for dynamic signatures — same approach
as dataclasses, namedtuple, and attrs. All input comes from trusted model
schemas (our own code), not user input.
"""

import json
import logging
from dataclasses import dataclass

from pybend.core.actors.tx import TX

logger = logging.getLogger('pybend.agents')

# JSON Schema type → Python type name (for exec'd function signatures)
_JSON_TYPE_MAP = {
    'string': 'str',
    'integer': 'int',
    'number': 'float',
    'boolean': 'bool',
    'array': 'list',
    'object': 'dict',
}


@dataclass
class ToolSpec:
    """Specification for a single tool derived from a model schema."""
    actor_addr: str     # Target actor address (e.g., 'products', 'web_tools')
    method_name: str    # Method/action name (e.g., 'create', 'scrape')
    tool_name: str      # LLM-facing name (e.g., 'products_create')
    description: str    # Human-readable description
    parameters: dict    # JSON Schema for parameters


# ── Discovery ─────────────────────────────────────────────────────

def discover_tools(actor_addrs: list, root) -> list[ToolSpec]:
    """Discover all tools from a list of actor addresses.

    Reads schemas from Matrix children. Includes CRUD operations for
    storable models and @expose_route methods for all models.

    Args:
        actor_addrs: List of actor addresses (e.g., ['grants', 'web_tools'])
        root: Matrix root instance

    Returns:
        List of ToolSpec objects for all discovered tools.
    """
    from pybend.core.models.storable_mixin import StorableMixin

    specs = []
    children = root._children if not isinstance(root, type) else root.__children__

    for addr in actor_addrs:
        child = children.get(addr)
        if child is None:
            logger.warning("Tool discovery: actor '%s' not found in Matrix", addr)
            continue

        # Get the class (works for both class actors and instance actors)
        cls = child if isinstance(child, type) else child.__class__
        if not hasattr(cls, 'schema'):
            logger.warning("Tool discovery: actor '%s' has no schema() method", addr)
            continue

        schema = cls.schema()
        tablename = schema.get('__tablename__', addr)
        model_name = schema.get('__name__', tablename)

        # CRUD tools for storable models
        is_storable = (
            issubclass(cls, StorableMixin)
            if isinstance(cls, type) else False
        )
        if is_storable:
            specs.extend(_crud_tool_specs(addr, tablename, model_name, schema))

        # Custom method tools from @expose_route
        specs.extend(_method_tool_specs(addr, tablename, model_name, schema))

    return specs


def _crud_tool_specs(addr, tablename, model_name, schema):
    """Generate ToolSpecs for CRUD operations from a model schema."""
    properties = schema.get('properties', {})
    required = schema.get('required', [])

    # Filter to writable fields (same logic as NetworkMCP._crud_tool_specs)
    writable = {}
    for name, prop in properties.items():
        if name == 'id':
            continue
        ui = prop.get('ui', {})
        if ui.get('protected') or ui.get('display') is False:
            continue
        writable[name] = {k: v for k, v in prop.items() if k not in ('ui', 'access')}

    writable_required = [r for r in required if r in writable]

    crud_ops = [
        ('list', f'List {model_name} records', {
            'type': 'object',
            'properties': {
                'limit': {'type': 'integer', 'description': 'Max records to return'},
                'offset': {'type': 'integer', 'description': 'Records to skip'},
            },
        }),
        ('get', f'Get a {model_name} by ID', {
            'type': 'object',
            'properties': {'id': {'type': 'integer', 'description': f'{model_name} ID'}},
            'required': ['id'],
        }),
        ('create', f'Create a new {model_name}', {
            'type': 'object',
            'properties': writable,
            'required': writable_required,
        }),
        ('update', f'Update an existing {model_name}', {
            'type': 'object',
            'properties': {'id': {'type': 'integer', 'description': f'{model_name} ID'}, **writable},
            'required': ['id'],
        }),
        ('delete', f'Delete a {model_name} by ID', {
            'type': 'object',
            'properties': {'id': {'type': 'integer', 'description': f'{model_name} ID'}},
            'required': ['id'],
        }),
    ]

    return [
        ToolSpec(
            actor_addr=addr, method_name=action,
            tool_name=f'{tablename}_{action}',
            description=desc, parameters=params,
        )
        for action, desc, params in crud_ops
    ]


def _method_tool_specs(addr, tablename, model_name, schema):
    """Generate ToolSpecs for @expose_route custom methods."""
    specs = []
    for method_name, method_info in schema.get('methods', {}).items():
        params = dict(method_info.get('parameters', {}))
        # Filter out 'user' (injected server-side, not a tool parameter)
        filtered = {k: v for k, v in params.items() if k != 'user'}
        required = list(filtered.keys())

        # Instance methods need 'id' to resolve the entity
        if method_info.get('scope') == 'instancemethod':
            filtered = {
                'id': {'type': 'integer', 'description': f'{model_name} ID'},
                **filtered,
            }
            required = ['id'] + required

        specs.append(ToolSpec(
            actor_addr=addr,
            method_name=method_name,
            tool_name=f'{tablename}_{method_name}',
            description=method_info.get('description', f'{model_name}.{method_name}()'),
            parameters={'type': 'object', 'properties': filtered, 'required': required},
        ))

    return specs


# ── Tool function generation ──────────────────────────────────────

async def _route_tool_call(ctx, target_addr: str, method_name: str, data: dict) -> str:
    """Route a tool call through Matrix as TX. Used by generated tool functions.

    Creates a TX, sends via adapter.request() for correlation, returns
    the response as a JSON string (tool results are always text for the LLM).
    """
    adapter = ctx.deps.adapter
    meta = {'user': ctx.deps.user} if ctx.deps.user else {}
    tx = TX(
        name=method_name,
        source=adapter.addr,
        target=target_addr,
        data=data,
        meta=meta,
    )
    response = await adapter.request(tx)
    if response.is_error:
        from pydantic_ai import ModelRetry
        raise ModelRetry(response.data.get('message', 'Tool call failed'))
    return json.dumps(response.data, default=str)


def create_tool_function(spec: ToolSpec):
    """Create an async function with typed parameters from a ToolSpec.

    The function has a proper Python signature that Pydantic AI introspects
    for JSON Schema generation. Tool calls route through Matrix via TX.

    Returns:
        An async function suitable for wrapping in pydantic_ai.Tool.
    """
    properties = spec.parameters.get('properties', {})
    required_set = set(spec.parameters.get('required', []))

    # Sanitize function name (must be valid Python identifier)
    func_name = spec.tool_name.replace('-', '_').replace('.', '_')
    if not func_name.isidentifier():
        func_name = f'tool_{abs(hash(spec.tool_name)) & 0xFFFFFF:x}'

    # Build parameter list: required first, then optional with defaults
    required_params = []
    optional_params = []
    param_names = []

    for pname, prop in properties.items():
        safe_name = pname.replace('-', '_')
        if not safe_name.isidentifier():
            logger.warning("Skipping parameter '%s' (not a valid identifier)", pname)
            continue

        param_names.append(safe_name)
        type_str = _JSON_TYPE_MAP.get(prop.get('type', 'string'), 'str')

        if safe_name in required_set or pname in required_set:
            required_params.append(f'{safe_name}: {type_str}')
        else:
            optional_params.append(f'{safe_name}: {type_str} = None')

    # ctx first (RunContext, handled by takes_ctx=True), then typed params
    all_params = ['ctx'] + required_params + optional_params
    params_str = ', '.join(all_params)

    # Build dict from local variables (filter out None for optional params)
    if param_names:
        kvs = ', '.join(f'"{n}": {n}' for n in param_names)
        collect = f'_d = {{{kvs}}}\n    _d = {{k: v for k, v in _d.items() if v is not None}}'
    else:
        collect = '_d = {}'

    # Escape description for docstring
    desc = (spec.description or spec.tool_name).replace('\\', '\\\\').replace('"""', "'''")

    code = (
        f'async def {func_name}({params_str}) -> str:\n'
        f'    """{desc}"""\n'
        f'    {collect}\n'
        f'    return await _route(ctx, _target, _method, _d)\n'
    )

    # Namespace: route function + closured target/method values
    ns = {
        '_route': _route_tool_call,
        '_target': spec.actor_addr,
        '_method': spec.method_name,
    }

    exec(code, ns)  # noqa: S102
    fn = ns[func_name]
    fn.__module__ = 'pybend.core.agents.tools'
    return fn


def make_tool(spec: ToolSpec):
    """Create a Pydantic AI Tool from a ToolSpec.

    Returns a Tool object with a properly-typed function, ready to
    register on a Pydantic AI Agent.
    """
    from pydantic_ai.tools import Tool

    fn = create_tool_function(spec)
    return Tool(
        function=fn,
        takes_ctx=True,
        name=spec.tool_name,
        description=spec.description,
    )
