# T02C capability documentation — attempt 1

## ✅ Outcome and scope

Rewrote 13 current actor, agent and File guides to separate orientation,
how-to examples and package reference. The docs distinguish native model
capabilities from application construction and transport routing, and describe
security limitations instead of implying transport parity.

Only the paths assessed below and this report are owned by this pass. Runtime
source, tests, dependency metadata, changelog history, inventory and review
ledgers were not changed. Other working-tree changes belong to parallel work.
No dependencies were installed, commits created, or paid/provider calls made.

### Method Signature Surface

No callable/interface signatures changed. Documentation examples and reference
declarations describe existing interfaces; they do not introduce runtime APIs.

## 📍 Per-file assessment

Paths are relative to the N3TX checkout. Assessments describe the rewritten
documents, not a claim that every old paragraph was independently audited.
All 13 current guides were reread in full during the closing review.

| Path | Value | Presentation | Correctness focus | Completeness / limit | Disposition |
|---|---|---|---|---|---|
| `docs/ACTORS.md` | Entry point for choosing actor capability | Decision table, flow, complete local example | Construction, model capability and routing are independent | Links to dispatch, adapters and trust boundaries | Rewritten; retain as overview |
| `docs/AGENTS.md` | Entry point for adding reasoning | Capability table, runtime flow, provider-free script | Import order, persistent threads, caller propagation and response boundaries | Example execution blocked by dependency; points to precise package contracts | Rewritten; retain as overview |
| `packages/n3tx-actors/README.md` | Package orientation and integration choice | Short selection and reference tables | ActorModel does not require actor HTTP; storage registration remains separate | Advanced setup delegated to bootstrap and adapter guides | Rewritten; retain |
| `packages/n3tx-actors/docs/actor-messaging.md` | TX, Actor, Matrix and proxy reference | Envelope/dispatch tables and flow | Mutable TX, reply correlation, global root, timeout semantics | No durable delivery guarantee; source and tests linked | Rewritten; retain |
| `packages/n3tx-actors/docs/actor-model.md` | Model dispatch and enforcement contract | CRUD and authorization boundary tables | Raw TX is not HTTP preprocessing; list and caller injection limits | Covers partial updates and non-durable lifecycle events | Rewritten; retain |
| `packages/n3tx-actors/docs/interceptors.md` | Policy registration and execution points | Chain diagram, point table, registration example | Class/instance ordering and Matrix overrides; model metadata required for auth | Example only registers policy, explicitly not an ingress demonstration | Rewritten; retain |
| `packages/n3tx-actors/docs/network-adapters.md` | Protocol-specific integration reference | Decision table and separate protocol sections | WS collection translation, MCP/AP caller gaps, remote URL/token risks | Remote wiring is a prerequisite-dependent excerpt, not a runnable local example | Rewritten; retain |
| `packages/n3tx-agents/README.md` | Dependency and capability orientation | Export/reference table and runtime diagram | Browser dependencies differ from Python dependencies; threads need storage | App-agent provisioning currently links to source rather than a full how-to | Rewritten; retain with follow-up noted |
| `packages/n3tx-agents/docs/mixin.md` | Policy, runtime and thread ownership | Signature reference, precedence table and lifecycle section | Per-key precedence, full instance context, no create_thread switch | Execution verification blocked; concurrent thread writes and preparation errors called out | Rewritten; retain |
| `packages/n3tx-agents/docs/agent-actor.md` | Stored agent fields, routes and browser integration | Field/response tables, continuation example, component hierarchy | Typed AgentTool records, JSON text vs actor objects, direct parser and caller gaps | Continuation depends on overview setup; not independently runnable | Rewritten; retain |
| `packages/n3tx-agents/docs/tool-discovery.md` | Discovery versus execution security reference | Discovery and enforcement tables | Discovery is not authorization; Matrix list filters and method user injection differ | Documents schema trust, recursion limitations and stream accumulation | Rewritten; retain |
| `packages/n3tx-files/README.md` | Optional capability and dependency orientation | Split-store diagram and export table | Public default read despite public=False; undeclared multipart prerequisite | Delegates complete usage and operations to File guide | Rewritten; retain |
| `packages/n3tx-files/docs/file.md` | Upload, range download, materialization and operations | Temporary-storage script, API/metadata/store/security tables | URL vs dict authorization, local-only ensure_local, separate metadata/blob lifecycle | End-to-end example blocked by multipart; no shipped remote projection claimed | Rewritten; retain |

## 🔎 Per-path evidence map

Source paths below are relative to `packages/`; tests are evidence of intended
contracts, not a blanket claim that their suite passed. The guides contain links
to these implementation owners.

| Document | Primary implementation / test evidence |
|---|---|
| `docs/ACTORS.md` | `n3tx-actors/src/n3tx_actors/{actor,matrix,tx}.py`; actor test suite; executed local example |
| `docs/AGENTS.md` | `n3tx-agents/src/n3tx_agents/{__init__,mixin,agent,thread}.py`; `n3tx-core/src/n3tx_core/app.py`; agent tests (collection blocked) |
| Actors README | `n3tx-actors/pyproject.toml`; actor exports; core `app.py` |
| `actor-messaging.md` | Actor package `{actor,matrix,tx,actor_proxy}.py`; `tests/test_streaming_shutdown.py` and actor suite |
| `actor-model.md` | Actor package `models/actor_model.py`, `api/auth_interceptor.py`; `tests/test_actormodel_auth.py`, `tests/unit/test_actor_model_lifecycle.py` |
| `interceptors.md` | Actor package `actor.py`, `api/network_adapter.py`, `api/auth_interceptor.py`; `tests/test_interceptors.py`; executed registration example |
| `network-adapters.md` | Actor package `api/network_{api,ws,mcp,ap}.py`, `api/remote_matrix.py`, `remote_proxy.py`; adapter suite and `tests/test_remote_matrix.py` |
| Agents README | `n3tx-agents/pyproject.toml`; agent package `__init__.py`, `app_agent.py`; core `app.py` |
| `mixin.md` | Agent package `{mixin,agent,utils,thread}.py`; `tests/test_mixin.py`, `tests/test_thread.py` |
| `agent-actor.md` | Agent package `{actor,tool_model}.py`, `static/components/ntx-{chat,agent-live,agent,agents}.js`; core `api/routes_fastapi.py`; `tests/test_agent_actor.py`; dependency-free route probe |
| `tool-discovery.md` | Agent package `{tools,schema_ext}.py`; `tests/test_tool_call_auth.py`, `tests/test_streaming_tool_specs.py`; actor model authorization implementation |
| Files README | `n3tx-files/pyproject.toml`; File package `{__init__,file,config}.py` |
| `file.md` | File package `{file,store,routes,materialize,address,config}.py`; File test suite, including test-only distributed gateway |

## 🧪 Verification

Runs used `/workspace/.venv-agents/bin/python` from the checkout root, with:

```sh
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=packages/n3tx-core/src:packages/n3tx-actors/src:packages/n3tx-agents/src:packages/n3tx-files/src:packages/n3tx-ui/src
/workspace/.venv-agents/bin/python -m pytest packages/n3tx-actors/src/n3tx_actors/tests/ packages/n3tx-actors/src/n3tx_actors/api/tests/ -q -p no:cacheprovider --tb=short
/workspace/.venv-agents/bin/python -m pytest packages/n3tx-files/src/n3tx_files/tests/ -q -p no:cacheprovider --tb=no
/workspace/.venv-agents/bin/python -m pytest packages/n3tx-agents/src/n3tx_agents/tests/ -q -p no:cacheprovider --tb=short
```

| Check | Result |
|---|---|
| Actor suites, closing rerun | **910 passed, 5 failed**, 4 warnings |
| File suite, closing rerun | **13 passed, 13 failed**, 1 warning; earlier detailed traces show missing `python-multipart` during route setup |
| Agent suite, closing rerun | Collection blocked: `ModuleNotFoundError: pydantic_ai` |
| Local actor script | Earlier execution passed; returned `{'value': 42}` |
| Interceptor registration script | Earlier execution passed |
| Agent and File examples | Attempted earlier; blocked by missing `pydantic_ai` and `python-multipart`, respectively |
| Python fence syntax | Earlier check parsed all 6 Python fences across the 13 guides; syntax is not runtime verification |
| Relative links/fragments | Earlier check passed across the 13 guides; parallel writers may still change target headings |
| Current-document reread | All 13 guides read in full in closing review |
| Scoped `git diff --check` | Passed for all 13 owned guides in closing review |
| New report permissions | Verified `0664`, owner/group `agent:agent`; nvim identity unavailable |

### Exact actor failures

Under `packages/n3tx-actors/src/n3tx_actors/api/tests/`:

- `test_network_ap.py::TestInboxHandler::test_handle_inbox_error_missing_type`
- `test_network_ap.py::TestInboxHandler::test_handle_inbox_error_missing_actor`
- `test_network_ap.py::TestFederationRoutes::test_inbox_route_400_for_invalid_json`
  — tests expect `error`, implementation returns `detail`.
- `test_network_ws.py::TestTranslateIncoming::test_translate_incoming_create`
- `test_network_ws.py::TestIntegrationWebSocket::test_ws_crud_create`
  — tests expect `create`, implementation translates collection target to `list`.

These failures were observed with documentation-only changes; runtime fixes are
outside this pass. A clean-baseline test run was not performed, so this report
does not certify their history. Warnings include unawaited Actor.send coroutines
and TestClient/httpx deprecations.

### Direct/actor route probe

A dependency-free analogous exposed method with signature
`agentic(self, task: str, thread_id: int = 0, **kwargs) -> str` confirmed:

- Direct task-only request: 400, `Missing field: thread_id`.
- Direct invocation supplied with the parser's required fields: JSON string,
  caller absent. This is diagnostic evidence, not a recommended dummy-kwargs API.
- Actor task-only request: object response after JSON parsing, caller absent.

This validates route-layer behavior without claiming an actual AgentActor run.

## ⚠️ Remaining acceptance gaps and follow-up

1. **Full historical/source inspection is not certified.** Earlier large reads
   were truncated. The final current guides were fully reread, but exhaustive
   original-document preservation and full source/test read coverage remain
   unproven. Do not mark that audit requirement complete based on this report.
2. **Agent and File end-to-end examples are not runtime-verified.** Rerun them
   and their suites in an approved environment with the missing dependencies.
   No dependency installation was performed in this pass.
3. **Review application-agent provisioning coverage.** The package README links
   to `app_agent.py`; check whether a dedicated workflow section is needed before
   accepting the reduction of older material.
4. **Security gaps are documented, not fixed.** In particular: agent caller
   propagation/list filtering; MCP/AP ingress; WS broadcasts; RemoteMatrix
   destination/token handling; File public reads and dict materialization.
5. **Integration check remains owner-level work.** Recheck cross-guide links
   after all parallel writers finish. Inventory/ledger updates are intentionally
   left to their owner. No changelog/history content was edited.
6. **Shared editor identity unavailable.** `id nvim` reported no such user;
   shared nvim access could not be verified through that identity.

The rewrite and evidence handoff are available for review; the broader audit is
not represented as fully accepted or green.
