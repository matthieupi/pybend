# AgentActor: stored native configuration

AgentActor is a storable ActorModel at `agents`. AgentTool is a storable tool
reference at `agent_tools`. Register both normally; only TTX stores history.

| Field | Contract |
| --- | --- |
| system_key | Stable provisioning identity, default empty string |
| name | Required display name, 1–200 characters |
| prompt | Stored system prompt |
| tools | Ordered local list of AgentTool records |
| llm | Provider/model selection, default ollama:llama3.1 |
| constraints | max_iterations and server-selected SDK retry bounds |

`tool_addrs()` extracts ordered unique targets. `run_config(task, **kwargs)`
combines stored settings with trusted Python overrides for model, tools, prompt,
result type, caller, scope and constraints. Configuration edits use ordinary
native CRUD; provisioning is configuration, never provider execution.

## Execution boundary

Stored agents inherit the same `agentic(..., ttx=None)` and Matrix AGENTIC path
as model agents. Applications must explicitly declare AGENTIC policy and supply
fresh guarded run behavior. Stock configuration does **not** enable execution.

The former unrestricted `/agents/{id}/agentic` and streaming endpoints are
removed; schema metadata no longer advertises agentic_endpoint. Applications
may publish deliberate bounded domain actions with native named caller injection.
There are no numeric history arguments, JSON-string response wrappers or private
tool-address compatibility aliases.

Trusted Python results are native dictionaries with canonical ttx_ref and
structured SDK evidence. Browser clients consume application-owned bounded
actions, not a guessed stock execution endpoint. Native event DTOs retain text,
thinking, tool calls/results and done; DoneChunk includes canonical ttx_ref.

See [model policy](mixin.md), [history](ttx-history.md) and
[tool boundaries](tool-discovery.md). Source changes do not migrate databases or
authorize provider calls, deployment or generic TTX collection access.

## Changelog

- 2026-11-11: Retire stock HTTP execution and numeric/JSON-string adapters; use
  the inherited native Matrix execution seam and canonical TTX state.
- 2026-11-04: Document the historical stored-agent integration and route caveats.
