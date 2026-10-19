# Tool Discovery

> Part of [n3tx-agents](../README.md)

## What This Covers

The pipeline from actor addresses to callable Pydantic AI tools:
`discover_tools()` -> `ToolSpec` -> `create_tool_function()` -> `make_tool()`.
Also covers the schema extension that provides the LLM-clean schema pipeline.

## Architecture

```
actor addresses        e.g. ['grants', 'web_tools']
    |
    v
discover_tools()       reads schema() from Matrix children
    |
    +-- _crud_tool_specs()     CRUD for storable models (list/get/create/update/delete)
    +-- _method_tool_specs()   @expose_route methods (scrape, extract, ...)
    |
    v
list[ToolSpec]         {actor_addr, method_name, tool_name, description, parameters}
    |
    v
make_tool(spec)        per spec:
    |
    +-- create_tool_function(spec)   exec()-generated async fn with typed params
    +-- pydantic_ai.Tool(fn, ...)    wraps in Pydantic AI Tool
    |
    v
list[Tool]             registered on pydantic_ai.Agent
```

Tool calls at runtime route through `_route_tool_call()`:

```
LLM calls tool  ->  generated fn(ctx, params)  ->  _route_tool_call()
    |
    +-- creates TX(name=method, target=actor_addr, data=params)
    +-- non-stream: Matrix.request(tx)  -- Future-based correlation
    +-- stream=True: Matrix.stream(tx)  -- Queue-based correlation
    +-- streamed routes are consumed server-side to completion
    +-- returns one final JSON string to the LLM
    +-- on error TX: raises ModelRetry (LLM retries)
```

## Interface

### `discover_tools(actor_addrs, root, caller_addr=None) -> list[ToolSpec]`

| Param | Type | Purpose |
|-------|------|---------|
| `actor_addrs` | list[str] | Actor addresses to discover tools from |
| `root` | Matrix | Matrix root for child lookup |
| `caller_addr` | str | Calling agent address (excluded to prevent self-loops) |

**Behavior**:
- Looks up each address in `root._children`
- Calls `cls.schema()` on found actors
- Storable models get 5 CRUD ToolSpecs (list, get, create, update, delete)
- All `@expose_route` methods get a ToolSpec each
- Streaming `@expose_route(..., stream=True)` methods stay in the tool set and
  are marked as streaming instead of being filtered out
- AgentActor subclasses auto-exclude `run` and `stream_run` methods
- Missing actors log a warning and are skipped

### `ToolSpec` (dataclass)

```python
@dataclass
class ToolSpec:
    actor_addr: str     # Target actor (e.g. 'products')
    method_name: str    # Action name (e.g. 'create', 'scrape')
    tool_name: str      # LLM-facing name (e.g. 'products_create')
    description: str    # Human-readable description
    parameters: dict    # JSON Schema for input parameters
    stream: bool = False
```

Tool names follow `{tablename}_{method}` convention.

### `create_tool_function(spec) -> async function`

Generates an async function via `exec()` with properly typed parameters
from the ToolSpec's JSON Schema. The function's signature is introspected
by Pydantic AI for JSON Schema generation.

Type mapping: `string->str`, `integer->int`, `number->float`,
`boolean->bool`, `array->list`, `object->dict`.

Required params have no default. Optional params default to `None`.
The `ctx` parameter (RunContext[AgentDeps]) is always first.

### `make_tool(spec) -> pydantic_ai.Tool`

Wraps `create_tool_function()` output in a `pydantic_ai.tools.Tool` with
`takes_ctx=True`.

### `_route_tool_call(ctx, target_addr, method_name, data, stream=False) -> str`

Internal. Creates a TX, sends via `Actor.root().request()` or
`Actor.root().stream()`, and returns response data as JSON string. On error
TX, raises `pydantic_ai.ModelRetry`.

For streaming tool methods, `_route_tool_call()` consumes the stream and
collapses it into a single result for the LLM:

- prefer a yielded `{'name': 'done', 'data': ...}` payload
- otherwise fall back to concatenated text chunks
- otherwise return collected event payloads

## Usage Patterns

### Manual tool discovery (for inspection)

```python
from n3tx_agents.tools import discover_tools
from n3tx_actors.actor import Actor

root = Actor.root()
specs = discover_tools(['products', 'comments'], root)
for spec in specs:
    print(f"{spec.tool_name}: {spec.description}")
    print(f"  params: {spec.parameters}")
```

### Custom tool filtering

```python
specs = discover_tools(['products'], root)
# Keep only read operations
read_specs = [s for s in specs if s.method_name in ('list', 'get')]
tools = [make_tool(s) for s in read_specs]
```

## LLM Schema Pipeline

The `schema_ext` module registers two pipelines:

**Default pipeline** -- `agent` stage (after `methods`): Adds `agent`
section to JSON Schema for `__agent__ = True` models. Contains `enabled`,
`config` (safe keys only -- no LLM credentials), `methods` list, and
`agentic_endpoint` (for AgentActor subclasses).

**LLM pipeline** -- `base` + `clean` stages: Produces a clean schema
for LLM context consumption. Strips frontend-only keys (`ui`, `$id`,
`$schema`, `additionalProperties`), removes `$defs`, filters hidden/
protected properties, strips routing metadata from methods, removes
`user` parameter from method signatures.

```python
from n3tx_core.models.proto_schema import run_pipeline
cleaned = run_pipeline(Product, pipeline='llm')
```

## Gotchas

- CRUD tool specs filter out `id`, protected, and hidden fields from
  writable properties. The `id` field is only included in get/update/delete
  where it is required.
- Instance methods (scope == `'instancemethod'`) auto-prepend an `id`
  parameter and add it to `required`. Class methods do not.
- The `user` parameter is always stripped from method tool specs -- it is
  injected server-side from JWT, never passed by the LLM.
- Parameter names with hyphens are converted to underscores. Invalid
  Python identifiers are skipped with a warning.
- Generated functions use `exec()` with a controlled namespace containing
  only `_route`, `_target`, `_method`, and `_required`. Input comes from
  trusted model schemas, not user data.
- Optional parameters set to `None` are stripped from the data dict before
  routing, but required parameters with `None` value are preserved. This
  prevents sending empty optional fields to CRUD operations.
