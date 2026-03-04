# Codebase Concerns

**Analysis Date:** 2026-03-04

## Tech Debt

**Coupled model reference collection in introspection:**
- Issue: `collect_all_referenced_models()` calls `__n3tx_methods_json_signature__()` as a side effect to populate `cls._referenced_models`. The TODO at line 79 acknowledges the coupling.
- Files: `src/n3tx/core/utils/introspection.py:79-83`
- Impact: The function both discovers and mutates state. Called again in `proto_model.schema()`, leading to redundant work and potential bugs if the set is modified between calls.
- Fix approach: Return referenced models as a return value instead of mutating `cls._referenced_models`. Make `__n3tx_methods_json_signature__()` a pure function that returns `(methods_dict, referenced_models_set)`.

**Unused method signature utility:**
- Issue: `pydantic_method_signature()` is declared but marked as "Currently unused" (TODO at line 100).
- Files: `src/n3tx/core/utils/introspection.py:97-119`
- Impact: Dead code that could mislead developers into thinking it is active.
- Fix approach: Either integrate it into `__n3tx_methods_json_signature__()` as intended or remove it.

**Join model FK differentiation TODO:**
- Issue: `ProtoModel.__init_subclass__()` has a TODO at line 83 about differentiating between join models and foreign keys for programmatic model generation.
- Files: `src/n3tx/core/models/proto_model.py:83`
- Impact: The current approach rewrites FK annotations in `__init_subclass__` but cannot distinguish between a simple FK reference and a relationship that needs a join table. Developers must manually call `generate_join_model()`.
- Fix approach: Add a `__joins__` ClassVar or use `ListRef` type annotation to auto-detect join-table relationships during `__init_subclass__`.

**Legacy actor module:**
- Issue: `src/n3tx/core/actors/legacy/actor_legacy.py` exists alongside the current actor system.
- Files: `src/n3tx/core/actors/legacy/actor_legacy.py`
- Impact: Confusion about which actor implementation is canonical. No imports reference it, but it ships with the package.
- Fix approach: Remove the legacy module or gate it behind a compatibility flag.

**Deprecated backward-compat alias in TX:**
- Issue: `exception_to_tx_error = TX.from_exception` is a deprecated alias at line 83.
- Files: `src/n3tx/core/actors/tx.py:83`
- Impact: Minor. Could be referenced by old code or tests.
- Fix approach: Grep for usage. If none, remove.

**BaseUser.login does full table scan:**
- Issue: `BaseUser.login()` calls `cls.list()` (full table scan) then filters with `next()` to find a user by email. Same pattern in `register_user()` for uniqueness check.
- Files: `src/n3tx/core/models/base_user.py:101-102`, `src/n3tx/core/models/base_user.py:140-141`
- Impact: O(n) login and registration. Acceptable for small user bases but will not scale. With 10k+ users, every login loads all users into memory.
- Fix approach: Add `find_by(field, value)` or `sql_filter` support to `StorableMixin` so `login()` can issue `WHERE email = ?` directly.

**Print statement in Actor.inbox:**
- Issue: `Actor.inbox()` has a bare `print(tx)` at line 311 that prints every incoming TX to stdout.
- Files: `src/n3tx/core/actors/actor.py:311`
- Impact: Pollutes stdout in production. Not a logger call, so it bypasses log-level filtering.
- Fix approach: Replace with `logger.debug(tx)` or remove.

## Architecture Risks

**SQLite as sole production storage backend:**
- Issue: `SQLiteStorage` is the only `AbstractStorage` implementation. The connection pool is fixed at 4 connections with `check_same_thread=False`.
- Files: `src/n3tx/core/storage/sqlite_storage.py:58-70`
- Impact: SQLite WAL mode allows concurrent readers but only one writer at a time. Under concurrent agent runs (each triggering CRUD tool calls), writer contention causes `SQLITE_BUSY` errors. The `busy_timeout=5000` pragma mitigates short bursts but not sustained load. For the grant-watch pipeline with multiple agents scanning simultaneously, this is a bottleneck.
- Fix approach: For near-term, increase `busy_timeout` and add retry logic on `SQLITE_BUSY`. For production, implement a PostgreSQL `AbstractStorage` backend.

**Single-process actor system with no task queue:**
- Issue: The actor system is entirely in-process. `asyncio.create_task()` in `_publish_lifecycle()` creates fire-and-forget tasks with no persistence, retry, or dead-letter handling. If the process crashes, in-flight agent runs and lifecycle events are lost.
- Files: `src/n3tx/core/models/actor_model.py:286-293`
- Impact: Agent runs (which may take 30+ seconds and make external API calls) have no crash recovery. Lifecycle events that trigger downstream processing (e.g., Grant.after_create -> Analyzer) silently fail on process restart.
- Fix approach: For v1, this is acceptable for single-user/dev use. For production, introduce a persistent task queue (e.g., Redis-backed) and make `_publish_lifecycle()` enqueue rather than fire-and-forget.

**Actor routing is synchronous-async hybrid:**
- Issue: `handler_crud()` in `ActorModel` is a synchronous classmethod that calls synchronous `StorableMixin` methods (`.create()`, `.get()`, `.list()`, `.update()`, `.delete()`). These block the event loop during SQLite I/O.
- Files: `src/n3tx/core/models/actor_model.py:183-275`
- Impact: Under concurrent load, a slow SQLite query blocks all other async operations in the same event loop. This is masked in light usage but becomes visible with multiple simultaneous agent tool calls.
- Fix approach: Wrap synchronous storage calls with `asyncio.to_thread()` or make the storage layer async.

**Lifecycle subscribers are a ClassVar list -- not isolated per deployment:**
- Issue: `ActorModel._subscribers` is `ClassVar[list] = []`. Each model class shares one subscriber list across all instances. Subscribers are appended at app startup (e.g., `model._subscribers.append('ws')` in `app.py:247`).
- Files: `src/n3tx/core/models/actor_model.py:54`, `src/n3tx/core/app.py:246-247`
- Impact: If multiple test suites or app configurations share the same process (common in pytest), subscriber lists leak between tests. The lifecycle test suite (`test_actor_model_lifecycle.py`) works around this by creating fresh subclasses.
- Fix approach: Reset subscribers in test teardown, or use a per-Matrix subscriber registry instead of per-class.

**No request-scoped context for agent runs:**
- Issue: `agent_run()` creates a transient `NetworkAdapter` per run for correlation, but there is no request-scoped context carrying auth, rate limits, or cost budget across tool calls within a single run.
- Files: `src/n3tx/core/agents/mixin.py:84-95`
- Impact: Each tool call within an agent run is independently authenticated via `tx.meta['user']`, but there is no aggregate cost tracking, no per-run rate limiting, and no ability to cancel a run in progress.
- Fix approach: Extend `AgentDeps` to include a run-scoped context object with budget counters, cancellation token, and accumulated usage.

## Security Concerns

**WebTools.scrape has no SSRF protection:**
- Issue: The `WebTools.scrape()` method fetches arbitrary URLs using `httpx.AsyncClient` with no validation. The SSRF protection utility exists at `example_grants/utils/url_validator.py` but is NOT imported or called by `WebTools.scrape()`.
- Files: `example_grants/models/web_tools.py:16-21`, `example_grants/utils/url_validator.py`
- Impact: Critical. An LLM agent (or any authenticated user) can instruct `WebTools.scrape()` to fetch internal URLs (`http://127.0.0.1:5000/...`, `http://169.254.169.254/metadata`, etc.), enabling SSRF attacks against the internal network and cloud metadata services.
- Fix approach: Import and call `validate_url(url)` at the top of `WebTools.scrape()` before making the HTTP request. This is a one-line fix with the existing utility.

**Agent tool calls inherit user auth but have no tool-level authorization:**
- Issue: When an agent runs, tool calls carry `tx.meta['user']` from the invoking user. However, there is no mechanism to restrict WHICH tools an agent can call beyond the `tools` list in its configuration. An agent configured with `tools=['grants']` gets full CRUD access to grants (create, update, delete) -- there is no read-only or action-scoped tool permission.
- Files: `src/n3tx/core/agents/tools.py:43-88` (discover_tools gives all CRUD ops for storable models)
- Impact: An agent meant only to scan/read grants can also create, update, and delete them. The LLM decides which tools to call, and the only guard is the model-level `__access__` rule (which the invoking user may satisfy).
- Fix approach: Add a `permissions` field to `AgentTool` (e.g., `permissions: list = ['list', 'get']`) and filter `_crud_tool_specs()` output to only include permitted operations.

**Source model has no access control:**
- Issue: The `Source` model defines no `__access__` rules. With no `__access__`, the default behavior depends on routing level -- Level 3 (actor routing) defaults to AUTHENTICATED for non-schema operations, but this is implicit.
- Files: `example_grants/models/source.py`
- Impact: Any authenticated user can create, update, or delete grant sources. For a grant-watch system where sources drive agent scanning, this is a data integrity risk.
- Fix approach: Add explicit `__access__` rules to `Source`, e.g., `'create': ROLE('admin'), 'update': ROLE('admin'), 'delete': ROLE('admin')`.

**Default JWT secret in production config:**
- Issue: `example_grants/config.py` uses `JWT_SECRET = os.environ.get("N3TX_JWT_SECRET", "ntx-dev-secret-change-in-production")`. The fallback is a known insecure secret listed in `INSECURE_SECRETS` in `src/n3tx/core/authorize/auth.py:16-19`. The `configure()` function emits a warning but does not prevent startup.
- Files: `example_grants/config.py:12`, `src/n3tx/core/authorize/auth.py:16-34`
- Impact: If deployed without setting `N3TX_JWT_SECRET`, any attacker can forge valid JWT tokens. The warning is logged but easily missed.
- Fix approach: In production mode (`DEBUG=false`), raise an error instead of a warning when an insecure secret is detected.

**No rate limiting on login/register endpoints:**
- Issue: `BaseUser.login()` and `BaseUser.register_user()` have `access=ANYONE` with no rate limiting.
- Files: `src/n3tx/core/models/base_user.py:75`, `src/n3tx/core/models/base_user.py:111`
- Impact: Brute-force password attacks and registration spam are unmitigated.
- Fix approach: Add a rate-limiting interceptor on the NetworkAPI adapter for auth endpoints.

**Agent `exec()` for tool functions:**
- Issue: `create_tool_function()` uses `exec()` to generate dynamic Python functions from `ToolSpec` parameters.
- Files: `src/n3tx/core/agents/tools.py:250-264`
- Impact: The docstring notes inputs come from trusted model schemas (our own code). This is true for N3TX-generated schemas, but if external schemas are ever ingested (e.g., federated models, user-provided tool specs), this becomes a code injection vector. Currently low risk because all tool specs come from `discover_tools()` which reads from registered Matrix children.
- Fix approach: No immediate fix needed. Document the trust boundary clearly. If external tool specs are ever supported, switch to `types.FunctionType` construction or parameter validation.

## Performance Bottlenecks

**Full table scan for user login:**
- Problem: `BaseUser.login()` calls `cls.list()` which loads ALL users, then iterates to find a match.
- Files: `src/n3tx/core/models/base_user.py:101-102`
- Cause: `StorableMixin.list()` has no `find_by()` or `WHERE` clause support (outside of `sql_filter` which requires an `AccessContext`).
- Improvement path: Add a `find_by(field, value)` classmethod to `StorableMixin` that issues `SELECT * FROM {table} WHERE {field} = ? LIMIT 1`.

**Schema generation runs full pipeline on each miss:**
- Problem: `ProtoModel.schema()` caches per class, but cache misses trigger the full `proto_schema.run_pipeline()` which calls `collect_all_referenced_models()`, `__n3tx_methods_json_signature__()`, and all pipeline stages.
- Files: `src/n3tx/core/models/proto_model.py:186-200`
- Cause: Cache is per-process, so first request after startup pays the full cost. `copy.deepcopy()` runs on every access even for cache hits.
- Improvement path: For grant-watch where schemas are static, consider returning frozen dicts or using `__slots__`-based immutable schema objects to avoid deepcopy overhead.

**N+1 query risk in agent tool calls:**
- Problem: When an agent calls `grants_list` followed by `grants_get` for each result, it creates N+1 queries. The agent has no way to request populated/eager-loaded data.
- Files: `src/n3tx/core/agents/tools.py:108-145` (CRUD tool specs have no `populate` parameter)
- Cause: Tool specs expose basic CRUD without `?populate=` support.
- Improvement path: Add optional `populate` parameter to list/get tool specs so agents can request eager-loaded data in a single call.

## Fragile Areas

**ActorModel handler with JSON string parsing:**
- Files: `src/n3tx/core/models/actor_model.py:134-141`
- Why fragile: The non-CRUD handler path (lines 130-145) has special-case logic for string results: it tries `json.loads()` and falls back to wrapping in `{'result': str}`. This creates ambiguity -- a custom method returning a literal string that happens to be valid JSON gets parsed differently than one returning plain text.
- Safe modification: Always wrap non-TX results consistently. If JSON parsing is needed, make it opt-in via a decorator or return type annotation.
- Test coverage: `example_grants/tests/test_agent_run.py` covers the happy path but not edge cases of the JSON-string parsing logic.

**Mixin injection via `__bases__` rewriting:**
- Files: `src/n3tx/core/models/proto_model.py:73-94`
- Why fragile: `StorableMixin` and `AgentMixin` are injected by directly mutating `cls.__bases__`. This works but bypasses Python's normal MRO construction. If a class already has a complex inheritance hierarchy (e.g., `User(BaseUser, ActorModel)` where both paths inject mixins), the MRO can become unpredictable.
- Safe modification: Test any new mixin injection with the full `User(BaseUser, ActorModel)` hierarchy. Verify MRO with `cls.__mro__`.
- Test coverage: `src/n3tx/core/agents/tests/test_mixin.py` covers AgentMixin injection including dual mixin case.

**Transient adapter cleanup in agent_run:**
- Files: `src/n3tx/core/agents/mixin.py:142-144`
- Why fragile: Cleanup directly accesses `root._children.pop(adapter_addr, None)` -- reaching into Matrix's private state. If Matrix's child management changes (e.g., adds an `unregister()` method), this breaks silently.
- Safe modification: Add `Actor.unregister(addr)` method and use it instead of direct `_children.pop()`.
- Test coverage: `test_mixin.py` has explicit tests for cleanup on success and failure paths.

## Missing Infrastructure

**No scheduling mechanism:**
- Problem: The grant-watch pipeline requires periodic scanning (e.g., "scan all sources every 6 hours"). There is no scheduler, cron trigger, or timer actor in the framework.
- Blocks: SchedulerActor implementation, automated grant discovery pipeline.
- Current workaround: Manual triggering via `POST /agents/1/run`.
- Implementation path: Create a `SchedulerActor` that uses `asyncio` timers or `APScheduler` to send TX messages on a schedule. Register it with Matrix. Configure via model fields (cron expression, target actor, task payload).

**No agent run persistence:**
- Problem: `agent_run()` returns results directly but does not persist them. There is no `AgentRun` or `AgentStep` model to record run history, tool calls, LLM token usage, or error traces.
- Blocks: Run history UI, cost tracking, debugging failed agent runs, audit trail.
- Files: `src/n3tx/core/agents/mixin.py:130-140` (result dict is returned, not stored)
- Implementation path: Create `AgentRun(ActorModel)` with fields: agent_id, task, status, answer, usage_json, started_at, completed_at. Create `AgentStep(ActorModel)` with fields: run_id, tool_name, input_json, output_json, timestamp. Persist before/after each tool call in `_route_tool_call()`.

**No file reader capability:**
- Problem: The grant-watch pipeline needs to read organization documents (eligibility criteria, org profile) to match against grant requirements. There is no file reader actor or document ingestion tool.
- Blocks: Eligibility analysis, org-specific grant matching.
- Implementation path: Create a `FileReader` tool actor (like `WebTools`) with methods for reading local files, PDFs, and structured documents. Register as a Matrix child so agents can call `file_reader_read` as a tool.

**No lifecycle event wiring for grant pipeline:**
- Problem: The `_publish_lifecycle()` mechanism exists and is tested, but `Grant._subscribers` is empty. No actor is wired to receive `after_create` events from grants.
- Files: `src/n3tx/core/models/actor_model.py:280-293`, `example_grants/models/grant.py` (no subscribers)
- Blocks: Automatic eligibility analysis when new grants are discovered.
- Implementation path: Create an `AnalyzerAgent` and wire it: `Grant._subscribers.append('agents/{analyzer_id}')`. The analyzer receives `LIFECYCLE` TX with `event='after_create'` and triggers analysis.

**Frontend has no agent-specific UI components:**
- Problem: The frontend renders agents using generic `ntx-item` and `ntx-method` components. There is no dedicated agent UI for: run status/progress, streaming output, run history, tool call visualization, or cost display.
- Files: `src/n3tx/static/components/ntx-method.js` (generic method button, fire-and-forget)
- Blocks: User-facing agent interaction beyond clicking "Run" and seeing a JSON response.
- Implementation path: Create `ntx-agent` web component that extends `NTTElement`. Show run status (pending/running/complete/error), stream partial results via WebSocket, display tool call timeline, show token usage.

**No WebSocket integration in example_grants:**
- Problem: `example_grants/main.py` uses `routing='actor'` but does not enable WebSocket (`ws=False` by default in `create_app`). Lifecycle events publish via `_publish_lifecycle` but no WebSocket adapter receives them.
- Files: `example_grants/main.py:35-45`
- Impact: The frontend cannot receive real-time updates when agents create new grants. Users must manually refresh.
- Fix approach: Add `ws=True` to the `create_app()` call and wire subscribers.

## Integration Gaps

**Missing models for full grant-watch pipeline:**

| Model | Purpose | Status | Needed For |
|-------|---------|--------|------------|
| `Grant` | Grant records | Exists | -- |
| `Source` | Scan sources | Exists | -- |
| `AgentActor` | Agent instances | Exists (framework) | -- |
| `AgentTool` | Tool references | Exists (framework) | -- |
| `AgentRun` | Run history/audit | Missing | Run persistence, cost tracking |
| `AgentStep` | Tool call log | Missing | Debugging, audit trail |
| `Criterion` | Eligibility criteria | Missing | Eligibility matching |
| `GrantCriterion` | Grant-to-criterion mapping | Missing | Scoring/ranking |
| `Report` | Analysis reports | Missing | User-facing output |
| `Organization` | Org profile/docs | Missing | Org-specific matching |

**Missing actors for full pipeline:**

| Actor | Purpose | Status | Dependency |
|-------|---------|--------|------------|
| `SchedulerActor` | Periodic scanning | Missing | `asyncio` timer or APScheduler |
| `AnalyzerAgent` | Grant eligibility analysis | Missing | Criterion model, file reader |
| `FileReader` | Document ingestion | Missing | PDF/text parsing library |
| `NotificationActor` | Alert on new matches | Missing | Email/webhook integration |

**Missing wiring between existing components:**
- `Grant._subscribers` is empty -- no actor receives lifecycle events from grants.
- `Source._subscribers` is empty -- no actor is notified when sources change.
- `WebTools.scrape()` lacks SSRF protection despite the validator existing in the same project.
- Agent tool discovery gives full CRUD access with no action-level scoping.
- No `populate` support in agent tool specs, forcing N+1 patterns.
- Frontend has no streaming/progress UI for long-running agent operations.

## Test Coverage Gaps

**WebTools.scrape SSRF integration test missing:**
- What's not tested: Whether `WebTools.scrape()` blocks internal URLs. The SSRF tests in `example_grants/tests/test_ssrf.py` test the `url_validator` utility in isolation but NOT the `WebTools.scrape()` endpoint.
- Files: `example_grants/tests/test_ssrf.py` (unit tests only), `example_grants/models/web_tools.py` (no SSRF call)
- Risk: The validator exists and is tested, but since it is not wired into `scrape()`, the protection is illusory.
- Priority: High -- this is a security gap, not just missing coverage.

**No end-to-end agent run test via HTTP:**
- What's not tested: Triggering an agent run via `POST /agents/{id}/run` through the HTTP API (TestClient). The existing `test_agent_run.py` tests call `agent.run()` directly on the Python object, bypassing the HTTP layer, auth interceptor, and TX routing.
- Files: `example_grants/tests/test_agent_run.py`
- Risk: Auth bypass, TX routing errors, or response serialization bugs in the HTTP-to-agent path would not be caught.
- Priority: Medium -- the unit tests cover the core logic, but the HTTP integration path is untested.

**No concurrent agent run test:**
- What's not tested: Multiple simultaneous `agent_run()` calls sharing the same Matrix and SQLite storage. Race conditions in transient adapter registration/cleanup and SQLite writer contention are untested.
- Files: `src/n3tx/core/agents/mixin.py:84-95`
- Risk: Transient adapter address collision (unlikely due to UUID, but untested), SQLite `SQLITE_BUSY` under concurrent writes.
- Priority: Medium -- becomes high when the scheduler triggers multiple agents simultaneously.

**Source model authorization not tested:**
- What's not tested: Whether unauthenticated or unauthorized users can create/update/delete sources. Since `Source` has no `__access__` rules, the behavior is implicitly "AUTHENTICATED for everything" under actor routing.
- Files: `example_grants/models/source.py`, `example_grants/tests/` (no source auth tests)
- Risk: Any authenticated user can modify the scan source list.
- Priority: Medium.

**Lifecycle event subscriber wiring not tested in grants app:**
- What's not tested: Whether `_publish_lifecycle()` correctly delivers events when `_subscribers` is populated in the grants app context. Framework-level tests exist in `test_actor_model_lifecycle.py` but grants-specific wiring is absent.
- Files: `src/n3tx/core/tests/unit/test_actor_model_lifecycle.py` (framework tests), `example_grants/tests/` (no lifecycle tests)
- Risk: When lifecycle wiring is added (Grant.after_create -> Analyzer), integration bugs may surface.
- Priority: Low (no subscribers currently wired, but becomes high when wiring is added).

## Dependencies at Risk

**pydantic-ai version coupling:**
- Risk: The agent system depends on `pydantic-ai` for LLM integration. The `Tool` class, `RunContext`, `UsageLimits`, and `TestModel` APIs are used directly. Pydantic AI is pre-1.0 and its API surface may change.
- Impact: Breaking changes in pydantic-ai could break `agent_run()`, tool generation, and all agent tests.
- Migration plan: Pin the pydantic-ai version. Abstract the LLM interface behind a thin adapter if the API proves unstable.

**httpx in WebTools:**
- Risk: `WebTools.scrape()` imports `httpx` inline. It is not declared as a project dependency in a visible `requirements.txt` or `pyproject.toml` at the `example_grants` level.
- Impact: Missing dependency on fresh deployment.
- Migration plan: Add `httpx` and `beautifulsoup4` to example_grants dependencies.

---

*Concerns audit: 2026-03-04*
