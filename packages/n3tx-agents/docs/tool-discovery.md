# Tool discovery and execution boundaries

[Package](../README.md) · [Actor authorization](../../n3tx-actors/docs/actor-model.md)

Tool schemas describe available operations. They do not prove that the caller
may perform them. Use trusted model schemas and deliberately selected addresses.

```text
supplied addresses -> Matrix child lookup -> schema() -> ToolSpec
                                                       |
                                            generated typed function
                                                       |
Pydantic AI -> function(ctx, args) -> TX -> Matrix.request/stream
                                             |
                                         ActorModel
```

## Discovery reference

| API | Contract |
|---|---|
| `discover_tools(actor_addrs: list, root, caller_addr: str = None)` | Returns `list[ToolSpec]` from exact child-address lookups |
| `ToolSpec` | `actor_addr`, `method_name`, `tool_name`, `description`, `parameters`, `stream=False` |
| `create_tool_function(spec)` | Generates an async callable using trusted schema metadata |
| `make_tool(spec)` | Wraps it as a Pydantic AI Tool with `takes_ctx=True` |
| `AgentDeps` | `user`, `agent_addr`, mandatory canonical `ttx` |

Missing children and classes without `schema()` are warned about and skipped.
StorableMixin subclasses contribute `list/get/create/update/delete`; exposed
schema methods contribute method tools, including streaming methods. Names use
`{tablename}_{method}`.

The caller is excluded only when its address exactly matches a supplied address.
An instance address such as `agents/1` does not exclude `agents`. Reasoning
methods agentic/agentic_stream/run/run_stream are excluded on agent-enabled
models. Discovery is not a general recursion or permission guard.

| Input generation | Behavior |
|---|---|
| CRUD fields | Omits `id` from writable fields and fields with `ui.protected` or `ui.display=False` |
| Update | Requires only `id`; supplied fields are a patch, collections replace whole values |
| Instance action | `scope == 'instancemethod'` adds required `id` |
| Caller argument | Removes `user` from model-generated tool parameters |
| Required arguments | Uses schema required list; empty/missing list falls back to all parameters |
| Types | Maps string/integer/number/boolean/array/object to Python builtins; not full JSON Schema fidelity |
| Optional `None` | Omitted before TX dispatch; required `None` retained |

Generated identifiers normalize hyphens (and tool-name dots); invalid parameter
identifiers are skipped. Generated code uses `exec()` over schema-derived text:
schemas are trusted code inputs, not user-supplied tool definitions.

## Execution and security limits

`_route_tool_call` obtains `Actor.root()`, requires the active canonical TTX as
TX source, and carries `meta={'user': ctx.deps.user}`.
It calls Matrix directly, not NetworkAPI. Error TXs become `ModelRetry`; a retry
does not make a denied operation authorized or undo an earlier side effect.

| Path | What is enforced / missing |
|---|---|
| CRUD get/create/update/delete | ActorModel checks declared model policy when `meta.user` is not `None`; absent model policy passes |
| List | ActorModel consumes `meta.sql_filter`; tool routing does not compute it and list does not call `_authorize` |
| Exposed action | ActorModel evaluates explicit decorator `access=` when caller is not `None`; no HTTP default-auth gate here |
| Method argument `user` | Removed from discovery; named exposed parameters receive trusted native metadata |
| Explicit raw `user=None` | Native trusted-internal bypass; the restored runtime preserves `None`, so authenticated entrypoints must supply their caller |
| Protected fields | Discovery filtering is not equivalent to HTTP protected-field stripping/injection |

Do not expose private collections to stock list tools on the assumption that
passing a caller enforces row filtering. Do not accept identity from request
bodies or treat tool-address selection as permission. Test denial and caller
propagation on each real entrypoint. The existing
[tool auth tests](../src/n3tx_agents/tests/test_tool_call_auth.py) explicitly
exercise the internal bypass; they are not proof of external-user isolation.

Conversation history uses canonical TTX and private agent-root owner/admin
policy. Nullable scope does not grant business access. The same table also holds
User DMs, which never enter agent-admin policy. Do not expose raw collection
tools; use authorized history actions. Notes compose explicit
`n3tx_threads.NoteMixin`, whose host/ingress owns action authorization. Never
trust body identity or presentation filtering. See [history](ttx-history.md).

## Streaming tools

Streaming specs route through `Matrix.stream()`. The tool consumes the stream
server-side, returning one JSON string to the LLM: prefer a nested application
`done.data`, otherwise concatenate text, otherwise return the collected events.
An error TX or application `error` event raises ModelRetry. This can accumulate
events in memory; it is not a bounded streaming-output interface for the LLM.

## Schema context

The registered `agent` schema stage publishes enabled status, safe config keys
(`self_tools`, `neighbors`, `neighbor_depth`) and Python method names, not stock
HTTP execution endpoints. The `llm` pipeline strips UI/identity noise, `$defs`,
hidden/protected schema properties and selected method metadata. It is schema
cleanup, not caller-aware redaction of model instance values.

Evidence: [tools.py](../src/n3tx_agents/tools.py),
[schema_ext.py](../src/n3tx_agents/schema_ext.py),
[stream specs tests](../src/n3tx_agents/tests/test_streaming_tool_specs.py).

## Changelog

- 2026-11-11: Document mandatory active-TTX tool sources, native caller injection,
  canonical history policy and retirement of stock execution endpoints.
