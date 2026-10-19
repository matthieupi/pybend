# n3tx-agents

Optional model reasoning and stored agent configuration, using Pydantic AI for
execution and N3TX actors for tools and conversation storage.

Install `n3tx-agents` in your application environment (Python 3.10+). It depends
on `n3tx-core`, `n3tx-actors`, and `pydantic-ai`; see
[package metadata](pyproject.toml) for version constraints. Browser components
also import `n3tx-ui` assets; the Python dependency graph alone does not provide
their browser prerequisites.

## Start here

Use the complete [provider-free example](../../docs/AGENTS.md#provider-free-how-to)
before configuring a live provider. Import this package before declaring models
with `__agent__`. Register storage and Matrix targets, including Thread when
using raw registration. App bootstrap registers Thread for agent-enabled models.

| Interface | Purpose | Reference |
|---|---|---|
| `AgentMixin` | Model-context reasoning through `agentic()` | [Mixin](docs/mixin.md) |
| `AgentActor`, `AgentTool` | Agents and tool references as stored models | [AgentActor](docs/agent-actor.md) |
| `Thread` | Stored conversation messages | [Thread lifecycle](docs/mixin.md#thread-lifecycle) |
| `AgentDeps` | Runtime caller context and agent address | [Tools](docs/tool-discovery.md) |
| `ToolSpec`, `discover_tools`, `make_tool` | Schema-derived tools | [Discovery](docs/tool-discovery.md) |
| `provision_app_agent` | Bootstrap a configured application agent | [Source](src/n3tx_agents/app_agent.py) |

```text
model policy / stored agent -> shared runtime -> Pydantic AI
                                      |
                               Matrix tools + Thread
```

## Limits

- Tool discovery is not authorization. Matrix tools do not inherit every HTTP
  boundary check; `user=None` is trusted internal execution.
- The stock AgentActor HTTP signature does not explicitly request caller
  injection. Audit caller propagation before exposing private tools or history.
- Every prepared call loads or creates a thread. This requires storage even
  with `tools=[]` and a test model.
- `constraints.max_iterations` limits model requests only. No built-in scheduler,
  durable task queue, general spend ceiling, or tool-effect rollback is implied.

Implementation owners: [mixin.py](src/n3tx_agents/mixin.py) resolves model policy;
[actor.py](src/n3tx_agents/actor.py) adapts stored fields;
[agent.py](src/n3tx_agents/agent.py) owns preparation/execution;
[tools.py](src/n3tx_agents/tools.py) owns discovery and TX calls.
