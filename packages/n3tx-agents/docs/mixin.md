# AgentMixin reference

Import `n3tx_agents` before declaring `__agent__`. ProtoModel injects the native
mixin at class construction. It creates no unrestricted HTTP execution endpoint.

## Policy and execution

`ctx()` projects the llm schema and optional current-instance data. `tools()`
selects self, local list neighbors and configured tool addresses, deduplicated in
order. Neither context projection nor discovery authorizes access or redacts all
instance data; review sensitive fields before provider disclosure.

`run_config(task, **kwargs)` resolves trusted Python configuration:

| Input | Resolution |
| --- | --- |
| Prompt | Truthy call prompt, otherwise ctx with optional model prefix |
| Tools | Explicit tools including [], otherwise model discovery |
| Constraints | Global defaults, model constraints, then call constraints |
| LLM | Explicit override, otherwise model/target/global configuration |
| Output | Truthy explicit result_type, otherwise model configuration |
| Caller/scope | Trusted call inputs; nullable scope is never inferred |

`agentic(task, *, ttx=None, **kwargs)` checks explicit callee AGENTIC policy,
creates or authorizes the root, resolves policy and calls Agent.invoke. Matrix
AGENTIC rechecks policy and owner, then invokes guarded target.run. Applications
retain fresh business checks and whole-save behavior in that seam.

`run(..., *, ttx, **kwargs)` prepares and executes the single SDK loop. It is
trusted internal execution, not an ingress access gate. CallConfig has no numeric
history ID; PreparedCall and AgentDeps require canonical TTX state.

```text
agentic -> run_config -> Agent.invoke -> Matrix AGENTIC -> guarded run
                                                            |
                                                     prepare -> SDK run
```

Results are `{answer, usage, messages, message_count, ttx_ref}`. The message list
contains raw loaded SDK objects followed by newly finalized objects; the SDK gets
a separately repaired copy. Structured output remains structured. Persistence
uses full codec-tagged JSON dictionaries, not stringified SDK objects.

`max_iterations` limits model requests. `tool_retries` and `output_retries`
preserve backend-selected SDK retry bounds, including zero. No spend ceiling,
execution replay or transactional rollback is added.

## Streaming

`agentic_stream(..., ttx=None)` performs the same admission and Matrix routing;
guarded `run_stream(..., *, ttx)` uses native SDK streaming. Class calls do not
construct an instance merely to stream. Events retain text/thinking/tool/done/
error semantics; done carries ttx_ref.

Explicit early SDK stream close is unsupported and may leave incomplete
history. Normal completion, cancellation and business-effect rollback are
distinct concerns. See [history and capture](ttx-history.md).

## Changelog

- 2026-11-11: Document mandatory TTX, Matrix invocation and guarded run ownership.
- 2026-11-06: Document the then-legacy optional creation scope and owner policy.
- 2026-11-04: Document the historical earlier TTX integration.
