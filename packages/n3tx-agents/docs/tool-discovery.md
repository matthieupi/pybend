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
| `AgentDeps` | `user`, `agent_addr`; no adapter field |

Missing children and classes without `schema()` are warned about and skipped.
StorableMixin subclasses contribute `list/get/create/update/delete`; exposed
schema methods contribute method tools, including streaming methods. Names use
`{tablename}_{method}`.

The caller is excluded only when its address exactly matches a supplied address.
An instance address such as `agents/1` does not exclude `agents`. AgentActor
subclasses exclude the historical names `run` and `stream_run`, **not** the
current exposed `agentic` and `agentic_stream`. This is not a recursion guard.

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

`_route_tool_call` obtains `Actor.root()`, sets TX source to the root address,
and carries `meta={'user': ctx.deps.user}`. `agent_addr` is not the TX source.
It calls Matrix directly, not NetworkAPI. Error TXs become `ModelRetry`; a retry
does not make a denied operation authorized or undo an earlier side effect.

| Path | What is enforced / missing |
|---|---|
| CRUD get/create/update/delete | ActorModel checks declared model policy when `meta.user` is not `None`; absent model policy passes |
| List | ActorModel consumes `meta.sql_filter`; tool routing does not compute it and list does not call `_authorize` |
| Exposed action | ActorModel evaluates explicit decorator `access=` when caller is not `None`; no HTTP default-auth gate here |
| Method argument `user` | Removed from discovery; raw ActorModel dispatch does not inject it from metadata |
| Explicit raw `user=None` | Native trusted-internal bypass; the restored runtime preserves `None`, so authenticated entrypoints must supply their caller |
| Protected fields | Discovery filtering is not equivalent to HTTP protected-field stripping/injection |

Do not expose private collections to stock list tools on the assumption that
passing a caller enforces row filtering. Do not accept identity from request
bodies or treat tool-address selection as permission. Test denial and caller
propagation on each real entrypoint. The existing
[tool auth tests](../src/n3tx_agents/tests/test_tool_call_auth.py) explicitly
exercise the internal bypass; they are not proof of external-user isolation.

Conversation history currently uses separate Thread and TXRecord models. See
the [Thread guide](thread.md). Thread enforces its own native owner/admin policy;
`scope` metadata does not grant Thread access. Application parent/action checks
are separate from native Thread authorization. Notes applies its host/action
checks independently before using Thread. Thread.user_owner governs owner
access; TXRecord.user_owner identifies the appender and grants no independent
access. TXRecord declares deny-all access for configured HTTP boundaries,
but raw Matrix LIST does not derive the corresponding filter. Do not offer raw
record collection tools to untrusted callers; use authorized history actions.

Notes uses trusted Matrix `tx.meta.user` or named HTTP `user` injection. Its
`NOTE` and `read_notes` actions perform the host/action checks for write/read.
These
specific capability guards do not establish caller injection for every exposed
actor method. Never trust body-supplied identity or presentation filtering.

## Streaming tools

Streaming specs route through `Matrix.stream()`. The tool consumes the stream
server-side, returning one JSON string to the LLM: prefer a nested application
`done.data`, otherwise concatenate text, otherwise return the collected events.
An error TX or application `error` event raises ModelRetry. This can accumulate
events in memory; it is not a bounded streaming-output interface for the LLM.

## Schema context

The registered `agent` schema stage publishes enabled status, safe config keys
(`self_tools`, `neighbors`, `neighbor_depth`), method names, and AgentActor's
`agentic_endpoint`. The separate `llm` pipeline strips UI/identity noise, `$defs`,
hidden/protected schema properties and selected method metadata. It is schema
cleanup, not caller-aware redaction of model instance values.

Evidence: [tools.py](../src/n3tx_agents/tools.py),
[schema_ext.py](../src/n3tx_agents/schema_ext.py),
[stream specs tests](../src/n3tx_agents/tests/test_streaming_tool_specs.py).
