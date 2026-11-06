# n3tx-agents

Optional model reasoning and stored agent configuration, using Pydantic AI for
execution, N3TX actors for tools, and native TTX conversation storage.

Install `n3tx-agents` in your application environment (Python 3.10+). It depends
on `n3tx-core`, `n3tx-actors`, `n3tx-threads`, and `pydantic-ai`; see
[package metadata](pyproject.toml) for version constraints. Browser components
also import `n3tx-ui` assets; the Python dependency graph alone does not provide
their browser prerequisites.

## Start here

Import this package before declaring models with `__agent__`. Register storage
and Matrix targets, including `TTX` from `n3tx_threads` when using raw
registration. Agent-aware app bootstrap registers TTX, not Thread. Use a saved
registered ActorModel instance or pass an actual saved local parent `scope` Ref
for class-level, non-storable or unsaved targets. There is no global fallback.
Use `llm='test'` and `tools=[]` for provider-free calls; storage and parent
authorization are still required. See [scope examples](docs/mixin.md#scope-examples).

| Interface | Purpose | Reference |
|---|---|---|
| `AgentMixin` | Model-context reasoning through `agentic()` | [Mixin](docs/mixin.md) |
| `AgentActor`, `AgentTool` | Agents and tool references as stored models | [AgentActor](docs/agent-actor.md) |
| `history.open_thread`, `history.read_history` | Open parent-bound conversations and decode SDK messages | [Thread lifecycle](docs/mixin.md#thread-lifecycle) |
| `AgentDeps` | Runtime caller context and agent address for tool routing | [Tools](docs/tool-discovery.md) |
| `ToolSpec`, `discover_tools`, `make_tool` | Schema-derived tools | [Discovery](docs/tool-discovery.md) |
| `provision_app_agent` | Bootstrap a configured application agent | [Source](src/n3tx_agents/app_agent.py) |

```text
model policy / stored agent -> shared runtime -> Pydantic AI
                                      |
                               Matrix tools + TTX conversation history
```

## Limits

- Tool discovery is not authorization. Matrix tools do not inherit every HTTP
  boundary check; their existing missing-caller internal paths are not repaired
  by history authorization. History treats a missing caller as anonymous `{}`.
- Verify authenticated caller propagation on the actual HTTP/Matrix path; neither
  a body-supplied identity nor a trusted internal call substitutes for it.
- Every prepared call loads or creates a thread. This requires storage even
  with `tools=[]` and a test model.
- `Thread(TTX, auto_register=False)` is an empty semantic subclass sharing TTX
  storage. Only TTX is registered; public identities use `/TTX/<id>`, never
  `/Thread/<id>`. `thread_id` remains the opaque conversation-root TTX ID.
- A `Conversation` root targets the owning scope, has the executing agent's
  address as source and a null payload. Its immediate `Message` children target
  that root and contain SDK JSON. `read_history` uses the SDK decoder directly:
  no codec registry, separate container or execution capture is involved.
- Parent `read` and `update` authorize execution/resume; parent `read` authorizes
  history. Checkpoints recheck parent update permission. Exact scope binding is
  required, but attribution and agent source are not private access grants.
  Shared-parent permissions therefore govern shared conversation access.
  TTX's deny-all policy is enforced at configured HTTP boundaries. Raw Matrix
  LIST does not derive that filter; do not offer it as a TTX collection tool.
  See [tool boundaries](docs/tool-discovery.md) and
  [Thread storage](../n3tx-threads/docs/thread.md).
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

Generic TTX storage and notes are imported from `n3tx_threads`.
The former `n3tx_agents.thread`, `tx_record`, `notes_mixin`, and `threaded_mixin`
modules and package-level exports are removed; no compatibility aliases exist.

## Changelog

- 2026-11-04: Document TTX-only registration, semantic conversation roots,
  saved-parent authorization and SDK decoding without codecs or capture.
