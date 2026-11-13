# n3tx-agents

Native model reasoning and stored configuration over **one canonical TTX store,
native Matrix dispatch and one Pydantic AI execution loop**. There is no legacy
Thread/TXRecord model, numeric history handle, fallback journal or dual write.

Import `n3tx_agents` before declaring `__agent__` models. Register only
`n3tx_threads.TTX` for history. Native app bootstrap selects it automatically
for agent-enabled models, execution capture and explicit NoteMixin hosts.
Notes compose `n3tx_threads.NoteMixin`; `__notes__` injection is retired.

## Interfaces and ownership

| Interface | Responsibility |
| --- | --- |
| `AgentMixin` | Model context/policy, explicit Matrix AGENTIC admission and guarded run seam |
| `AgentActor`, `AgentTool` | Stored agent configuration and selected tool addresses |
| `Agent.create_history/get_history/authorize_history` | Canonical root creation and private owner/admin history policy |
| `Agent.invoke/invoke_stream` | Native Matrix invocation preserving trusted CallConfig |
| `Agent.prepare/run/run_stream` | Mandatory TTX preparation, one SDK loop and finalized checkpoints |
| `Agent.chat_history` | Trusted full SDK decoding after authorization |
| `ThreadedMixin` | Declared root/participating child capture with one TTX context |
| `ToolSpec`, `discover_tools`, `make_tool` | Schema-derived native Matrix tools |
| `provision_app_agent` | Configuration provisioning, never provider execution |

```text
policy / bounded backend -> Agent.invoke -> Matrix AGENTIC
                                             |
                                      guarded target.run
                                             |
                                      prepare -> SDK loop
                                                   |
                          active TTX <- ATTACH <- finalized SDK messages
                              |
                              +-> native Matrix tools -> child TTX -> RETURN
```

## Policy and limits

- Agent roots explicitly declare `meta.agent_history=True` and nullable
  `data.scope`. Fresh native `OWNER | ROLE('admin')` policy governs their history.
  User DM roots lack this declaration and receive no agent-admin grant.
- Scope is immutable compatibility metadata, not permission. History reads do
  not load the business record or require business update permission; retained
  audits remain readable after source deletion. Execution separately requires
  deliberate `__access__['AGENTIC']` and fresh application business guards.
- `user=None` remains trusted native Python semantics, not anonymous ingress.
  Transport metadata supplies callers; a body identity is never authority.
- `CallConfig` contains trusted server-selected prompt/model/tools/output/retry
  controls. Matrix command bodies cannot override them. Runtime configuration
  stays in task-local Python state and is never captured or serialized.
- Results are dictionaries containing canonical `ttx_ref`. SDK evidence remains
  structured; stored agents no longer publish unrestricted HTTP execution routes.
- Checkpoints append each finalized full SDK dictionary once through ATTACH and
  stop after uncertain persistence. They do not replay providers or tool effects.
- Native collection tool selection is not authorization. Raw Matrix LIST does
  not derive all HTTP row filters; never offer generic TTX collection tools.
- No scheduler, spend ceiling, same-owner concurrency control, transactional
  effect/history coupling or supported explicit early SDK stream close is added.

## Guides

- [Canonical history and capture](docs/ttx-history.md)
- [Model mixin](docs/mixin.md)
- [Stored configuration](docs/agent-actor.md)
- [Tool discovery and execution](docs/tool-discovery.md)

Dependencies remain declared in [pyproject.toml](pyproject.toml). Source changes
do not convert existing databases; migration/admission belongs to the consuming
application's approved offline cutover.

## Changelog

- 2026-11-11: Cut over to mandatory TTX-only history, native Matrix invocation,
  private owner/admin roots and explicit Notes composition; retire legacy APIs.
- 2026-11-11: Add explicit TTX history decoding/preparation as an intermediate
  opt-in snapshot, superseded by the canonical cutover above.
- 2026-11-06: Restore Thread/TXRecord history navigation and correct its then API.
- 2026-11-04 (historical): Document the earlier TTX-only integration.
