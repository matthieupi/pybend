# n3tx-agents

Optional model reasoning and stored agent configuration, using Pydantic AI for
execution, N3TX actors for tools, and native Thread/TXRecord history.

Install `n3tx-agents` in your application environment (Python 3.10+). Its
declared runtime dependencies are `n3tx-core`, `n3tx-actors`, and `pydantic-ai`;
see [package metadata](pyproject.toml) for version constraints. Browser components
also import `n3tx-ui` assets; the Python dependency graph alone does not provide
their browser prerequisites.

## Start here

Import this package before declaring models with `__agent__`. Register `Thread`
and `TXRecord` storage and Matrix targets; do not register TTX as a substitute.
`scope` is optional creation metadata: omitted scope stays `None`, including for
saved instances. Native resume checks the requested Thread's access, not equality
with a supplied scope. Application-specific context binding is a separate check.
Use `llm='test'` and `tools=[]` for provider-free calls; storage and native Thread
access checks are still required. See
[scope examples](docs/mixin.md#scope-examples).

| Interface | Purpose | Reference |
|---|---|---|
| `AgentMixin` | Model-context reasoning through `agentic()` | [Mixin](docs/mixin.md) |
| `AgentActor`, `AgentTool` | Agents and tool references as stored models | [AgentActor](docs/agent-actor.md) |
| `Thread.append`, `Thread.history` | Append caller-attributed TX snapshots and decode SDK history | [Thread guide](docs/thread.md) |
| `AgentDeps` | Runtime caller context and agent address for tool routing | [Tools](docs/tool-discovery.md) |
| `ToolSpec`, `discover_tools`, `make_tool` | Schema-derived tools | [Discovery](docs/tool-discovery.md) |
| `provision_app_agent` | Bootstrap a configured application agent | [Source](src/n3tx_agents/app_agent.py) |

```text
model policy / stored agent -> shared runtime -> Pydantic AI
                                      |
                                Matrix tools + Thread/TXRecord history
```

## Limits

- Tool discovery is not authorization. Matrix tools do not inherit every HTTP
  boundary check; caller propagation and Thread owner/admin checks are distinct
  concerns. Trusted internal `user=None` calls bypass Thread policy by design.
- Verify authenticated caller propagation on the actual HTTP/Matrix path; neither
  a body-supplied identity nor a trusted internal call substitutes for it.
- Every prepared call loads or creates a thread. This requires storage even
  with `tools=[]` and a test model.
- Thread and TXRecord are separate registered storable models. Read their
  current API, time/cursor, attribution and Notes projection in the
  [Thread guide](docs/thread.md). Older TTX guides are historical, not current
  API authority.
- Thread itself enforces native owner/admin policy independently of its `scope`
  metadata. Application parent/action checks are separate and do not grant native
  Thread access. Notes applies its own host/action checks and then uses Thread.
  TXRecord's deny-all policy is enforced at configured HTTP boundaries. Raw
  Matrix LIST does not derive that filter; do not offer it as a collection tool.
  See [tool boundaries](docs/tool-discovery.md) and
  [Thread storage](docs/thread.md).
- Stock AgentActor HTTP default/variadic parsing and kwargs-only caller limits
  remain; this persistence change does not make arbitrary external execution
  safe. Collagen stock execution remains separately denied. See
  [route cautions](docs/agent-actor.md#response-boundary).
- `constraints.max_iterations` limits model requests only. No built-in scheduler,
  durable task queue, general spend ceiling, or tool-effect rollback is implied.

Implementation owners: [mixin.py](src/n3tx_agents/mixin.py) resolves model policy;
[actor.py](src/n3tx_agents/actor.py) adapts stored fields;
[agent.py](src/n3tx_agents/agent.py) owns preparation/execution;
[tools.py](src/n3tx_agents/tools.py) owns discovery and TX calls.

Thread, TXRecord, NotesMixin, and ThreadedMixin are in `n3tx_agents`. No TTX
compatibility alias is provided.

## Changelog

- 2026-11-06: Restore Thread/TXRecord history navigation and correct current API.

- 2026-11-04 (historical): Document TTX-only registration, semantic conversation roots,
  saved-parent authorization and SDK decoding without codecs or capture.
