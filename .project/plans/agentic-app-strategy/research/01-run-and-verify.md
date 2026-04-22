# Run the App & Verify: End-to-End Smoke Testing & Operational Readiness

**Grant Watcher on N3TX v0.10 -- Research Analysis**
**Date:** 2026-03-04
**Audience:** Technical CEO + Engineering Leadership
**Status:** Research Complete

---

## Executive Summary

Grant Watcher is a **schema-driven agentic application** -- a grant discovery platform where LLM agents scan government funding sources, scrape pages, extract grant data, and create structured records. It runs on N3TX v0.10 with Level 3 actor routing, ABAC authorization, widget types, and pydantic-ai for agent execution.

**The core question:** Can we prove this application works, and keep proving it as we evolve?

**The short answer:** The existing test suite covers roughly **40-50% of the operational surface**. CRUD operations, schema endpoints, agent tool resolution, and basic E2E navigation are tested. But critical paths -- auth flows, error handling, pagination, widget rendering, ABAC edge cases, and agent execution through the full HTTP stack -- remain **unverified by automation**.

> **Key Insight:** For a schema-driven app, the regression surface is *enormous* because a single model change cascades through schema generation, API routes, ABAC rules, frontend rendering, and agent tool discovery. The framework absorbs this complexity -- but only if we verify the absorption works.

**Estimated effort to reach "provably working":** 3-5 engineering days. The ROI is high because the test infrastructure (conftest, TestClient, seed data) already exists. We are filling gaps, not building from scratch.

---

## Table of Contents

1. [Current State Audit](#-current-state-audit)
2. [Verification Gap Analysis](#-verification-gap-analysis)
3. [Smoke Test Strategy](#-smoke-test-strategy)
4. [Operational Readiness Patterns](#-operational-readiness-patterns)
5. [Agent Testing Deep Dive](#-agent-testing-deep-dive)
6. [Feasibility & ROI](#-feasibility--roi)
7. [Trade-offs & Recommendations](#-trade-offs--recommendations)
8. [Implementation Roadmap](#-implementation-roadmap)
9. [Sources](#-sources)

---

## :mag: Current State Audit

### What Exists Today

The Grant Watcher application lives at `/workspace/example_grants/` and consists of:

| Component | File(s) | Status |
|-----------|---------|--------|
| **Models** | `models/grant.py`, `models/source.py`, `models/user.py`, `models/web_tools.py` | Complete -- 4 app models + AgentActor + AgentTool from framework |
| **Bootstrap** | `main.py` | Complete -- `create_app()` with Level 3 actor routing |
| **Seed Data** | `seed.py` | Complete -- 2 users, 4 sources, 2 grants, 1 agent with 3 tools |
| **Migrations** | `migrations/20260303_001_set_default_grant_owner.py` | 1 migration |
| **Config** | `config.py` | Environment-variable-driven, sensible defaults |
| **Static** | `static/index.html`, `login.html`, `register.html` | Minimal app-specific HTML |
| **Integration Tests** | `tests/test_*.py` (5 files) | Partial CRUD + schema + agent coverage |
| **E2E Tests** | `tests/e2e/test_navigation.py`, `test_create_validation.py` | Playwright-based browser tests |

### Application Architecture

```
[Browser] --HTTP--> [FastAPI + JWTAuthMiddleware]
                         |
                    [NetworkAPI adapter]  <-- auth_interceptor (Tier 1)
                         |
                    [Matrix (message router)]
                         |
              +----------+----------+---------+----------+
              |          |          |         |          |
          [Grant]   [Source]    [User]   [WebTools]  [AgentActor]
          (CRUD)    (CRUD)     (Auth)   (scrape/    (run -> LLM loop
                                        extract)    -> tool calls -> TX)
                                                         |
                                                    [pydantic-ai Agent]
                                                         |
                                                    [tools via Matrix TX]
```

### Existing Test Coverage Map

Here is every test currently written, mapped to the operational surface it covers:

| Test File | Tests | What It Covers | What It Misses |
|-----------|-------|----------------|----------------|
| `test_grants_crud.py` | 6 tests | List (public), create (auth), create (unauth), get by ID, get 404, update as admin | Delete, OWNER enforcement, pagination, $schema/$id validation, field validation (422), widget metadata in responses |
| `test_sources_crud.py` | 3 tests | List (auth), create (auth), get by ID | Delete, update, unauthenticated access, ABAC rules (Sources have no explicit `__access__` -- defaults to AUTHENTICATED) |
| `test_schema_endpoints.py` | 4 tests | Grant schema, Source schema, Agent schema (with `agent.enabled`), WebTools schema (with methods) | Widget metadata in schema (`ui.widget`), access rules in schema, `$defs` content, `$id`/`$schema` URLs, `required` array accuracy |
| `test_agent_crud.py` | 6 tests | List agents, get agent (with FK hydration check), tools as hrefs, create via API, update prompt, add tool via join route | Delete agent, ABAC for agents, agent constraints serialization, JSON field roundtrip |
| `test_agent_run.py` | 4 tests | Run with no tools, run with grants_list tool, run with sources_list tool, resolve tool hrefs | Run via HTTP endpoint (POST /agents/1/run), run with multiple tool calls, error handling during run, usage reporting accuracy |
| `test_navigation.py` | 4 tests | List click -> detail, back button, hash deep link, sidebar navigation | Multi-model navigation, search/filter, pagination UI, auth-gated UI elements |
| `test_create_validation.py` | 3 tests | Client-side validation on missing fields, detailed feedback analysis, error visibility | Server-side 422 assertion, successful create flow, edit flow, delete flow |

**Total: 30 tests across 7 files.**

### Test Infrastructure

The `conftest.py` provides solid session-scoped fixtures:

- **Isolated temp DB** per test session (file-based SQLite via `tempfile.mkstemp`)
- **Seed data** with users (alice, bob, admin), sources, grants, and one agent with tools
- **JWT tokens** pre-generated for alice, bob, admin
- **FastAPI TestClient** wrapping the actual `app` from `main.py`

This infrastructure is well-designed. The session scope means tests are fast (no per-test DB reset) but share state (order-dependent risk).

---

## :mag: Verification Gap Analysis

### The Full Request Lifecycle

Every request in Grant Watcher follows this path:

```
1. HTTP Request
   |
2. JWTAuthMiddleware (decode token, set request.state.user)
   |
3. FastAPI route handler (created by create_api_routes)
   |
4. Build TX message (name, source, target, data, meta with user)
   |
5. api_adapter.request(tx) -- runs interceptors
   |
6. auth_interceptor (Tier 1: gate, sql_filter, access check)
   |
7. Matrix.send() -- route to target actor
   |
8. ActorModel.handler_crud() -- CRUD dispatch
   |  |-- _authorize() (Tier 2: OWNER check with resource instance)
   |  |-- StorableMixin.create/get/list/update/delete
   |  |-- model_response() (inject $schema, $id)
   |
9. TX reply -> correlate -> HTTP response
```

**What is NOT tested in this path today:**

| Gap | Risk Level | Why It Matters |
|-----|-----------|----------------|
| **Auth flow (register/login/token)** | HIGH | No tests for user registration, login, or token validity. If auth breaks, everything behind AUTHENTICATED breaks. |
| **ABAC enforcement on Grants** | HIGH | Grant has `delete: OWNER \| ROLE('admin')` and `update: AUTHENTICATED \| ROLE('admin')`. No test verifies that Bob cannot delete Alice's grant. |
| **Pagination** | MEDIUM | No test verifies `?limit=N&offset=M` returns correct `{data, meta}` envelope with `has_more`. |
| **Delete operations** | MEDIUM | No delete test for grants, sources, or agents. |
| **Error responses (401/403/404/422)** | HIGH | Only 404 on get and 401/403 on create are tested. No validation error (422) tests, no ABAC denial (403) tests. |
| **Widget metadata in schema** | MEDIUM | Grant uses `UrlField`, `DateField`, `CurrencyField`, `TextareaField`. No test verifies the schema carries `ui.widget` annotations. |
| **$schema/$id on entity responses** | LOW | Tests check for presence on list items but do not validate URL format or correctness. |
| **Agent run via HTTP** | HIGH | `test_agent_run.py` calls `agent.run()` directly (bypassing HTTP stack). No test hits `POST /agents/{id}/run`. |
| **WebTools scrape/extract** | MEDIUM | No test invokes the scrape or extract endpoints (would need mocking of httpx and beautifulsoup). |
| **Protected field injection** | MEDIUM | Grant has `__protected_fields__ = {'user_owner'}`. No test verifies user_owner is auto-injected on create and stripped on update. |
| **Migration execution** | LOW | The migration exists but no test verifies it ran. |
| **Static file serving** | LOW | No test verifies index.html, login.html, register.html are served. |
| **Discovery endpoints** | LOW | No test hits `/_meta` or `/.well-known/agent.json`. |

### Risk Heat Map

```
                 HIGH IMPACT
                     |
   Auth Flow --------+-------- ABAC Enforcement
                     |
   Agent Run (HTTP) -+-------- Error Responses
                     |
                     |
   Pagination -------+-------- Delete Operations
                     |
   Protected Fields -+-------- Widget Metadata
                     |
   Discovery --------+-------- Static Files
                     |
                 LOW IMPACT
```

> **Key Insight:** The highest-risk gaps are all in the **auth/authz layer** and the **agent execution path via HTTP**. These are exactly the paths where silent failures cause the most damage -- a broken auth flow returns 200 with an error string (the infamous "200 OK error" pattern documented in CLAUDE.md), and a broken agent run silently returns no results.

---

## :bar_chart: Smoke Test Strategy

### What Makes Schema-Driven Smoke Testing Different

In a traditional app, smoke tests verify specific routes you manually wired. In a **schema-driven app like N3TX**, the framework generates routes from model definitions. This means:

1. **The schema IS the contract.** If the schema is correct, the frontend will render correctly. Test the schema, and you've implicitly tested the frontend.

2. **Model changes cascade everywhere.** Adding a field to Grant changes the schema, the API response shape, the form inputs, and the agent tool parameters. A single smoke test suite must verify this cascade.

3. **ABAC rules are data, not code.** Access rules are declared on models and serialized into schemas. Testing them requires hitting the actual routes with different auth contexts.

This aligns with the [Schema-Driven Development](https://blog.noclocks.dev/schema-driven-development-and-single-source-of-truth-essential-practices-for-modern-developers) philosophy: define once, validate the derivations.

### The Smoke Test Pyramid

```
          /\
         /  \     E2E (Playwright)        -- 4 tests (exist)
        / E2E\    Browser renders, navigates, validates
       /------\
      /        \  Integration (TestClient) -- 26 tests (exist, gaps)
     /  INTEG   \ API routes, auth, CRUD, agent run
    /------------\
   /              \ Boot & Schema          -- 0 tests (NEW)
  /  BOOT/SCHEMA   \ Server starts, models register, schemas resolve
 /------------------\
```

The **bottom layer is missing entirely**. Boot verification is the foundation -- if the app does not start correctly, nothing above it matters.

### Tier 1: Boot Verification (NEW -- 0 tests today)

**What to verify:**

| Check | How | Expected |
|-------|-----|----------|
| App starts without error | `TestClient(app)` constructor succeeds | No exception |
| All 6 models registered | `len(registered_models) >= 6` | User, Grant, Source, WebTools, AgentTool, AgentActor + join model |
| All models have tables | `model.list()` does not raise | Returns list (possibly empty) |
| Schema endpoints resolve | `GET /{ClassName}` for each model | 200 with `__name__` field |
| Discovery endpoints work | `GET /_meta` | 200 with `models` dict |
| Static files serve | `GET /` | 200 with HTML content |
| JWT is configured | `create_token(...)` does not raise | Returns string token |

**Example implementation:**

```python
class TestBootVerification:
    def test_app_starts(self, client):
        """TestClient creation implies app startup succeeded."""
        assert client is not None

    def test_all_models_registered(self, test_db):
        from n3tx.core.utils.registrar import registered_models
        expected = {'users', 'grants', 'sources', 'web_tools', 'agent_tools', 'agents'}
        actual = set(registered_models.keys())
        assert expected.issubset(actual), f"Missing models: {expected - actual}"

    def test_schemas_resolve(self, client, seed_data):
        for class_name in ['User', 'Grant', 'Source', 'WebTools', 'AgentActor']:
            resp = client.get(f"/{class_name}")
            assert resp.status_code == 200, f"Schema for {class_name} failed"
            assert resp.json()['__name__'] == class_name

    def test_meta_endpoint(self, client, seed_data):
        resp = client.get("/_meta")
        assert resp.status_code == 200
        meta = resp.json()
        assert 'models' in meta
        assert 'grants' in meta['models']

    def test_static_index(self, client, seed_data):
        resp = client.get("/")
        assert resp.status_code == 200
```

**LOE: ~1 hour.** These are trivial to write but catch catastrophic regressions.

### Tier 2: Auth Flow Verification (NEW -- 0 tests today)

**Critical path that touches every authenticated operation:**

```python
class TestAuthFlow:
    def test_register_new_user(self, client):
        resp = client.post("/users/register", json={
            "name": "Test User", "email": "test@example.com", "password": "test123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert "user" in data
        assert data["user"]["email"] == "test@example.com"

    def test_login_returns_token(self, client, seed_data):
        resp = client.post("/users/login", json={
            "email": "alice@example.com", "password": "alice123",
        })
        assert resp.status_code == 200
        assert "token" in resp.json()

    def test_login_wrong_password(self, client, seed_data):
        resp = client.post("/users/login", json={
            "email": "alice@example.com", "password": "wrong",
        })
        assert resp.status_code == 401

    def test_auth_me(self, client, alice_token):
        resp = client.get("/auth/me", headers=auth_header(alice_token))
        assert resp.status_code == 200
        assert resp.json()["email"] == "alice@example.com"

    def test_auth_me_no_token(self, client):
        resp = client.get("/auth/me")
        assert resp.status_code == 401

    def test_invalid_token(self, client):
        resp = client.get("/auth/me", headers=auth_header("invalid.jwt.garbage"))
        assert resp.status_code == 401
```

**LOE: ~2 hours.** The `example_actor/tests/test_auth_flow.py` has 18 tests that can be directly adapted.

### Tier 3: ABAC Enforcement (NEW -- 0 tests today)

Grant's access rules are the most complex in the app:

```python
__access__ = {
    'read':   ANYONE,              # Public listing
    'create': AUTHENTICATED,       # Any logged-in user
    'update': AUTHENTICATED | ROLE('admin'),   # Any auth user OR admin
    'delete': OWNER | ROLE('admin'),           # Only owner or admin
}
```

**Tests needed:**

```python
class TestGrantABAC:
    def test_list_grants_no_auth(self, client, seed_data):
        """ANYONE can read -- no token needed."""
        resp = client.get("/grants")
        assert resp.status_code == 200

    def test_create_grant_no_auth(self, client):
        """AUTHENTICATED required -- no token = 401."""
        resp = client.post("/grants", json={"title": "X", "agency": "Y", "url": "https://x.com"})
        assert resp.status_code in (401, 403)

    def test_delete_grant_non_owner(self, client, bob_token, seed_data):
        """Grant owned by alice. Bob is not owner or admin. Should be 403."""
        grant = seed_data["grants"][0]  # owned by alice
        resp = client.delete(f"/grants/{grant.id}", headers=auth_header(bob_token))
        assert resp.status_code == 403

    def test_delete_grant_as_owner(self, client, alice_token, seed_data):
        """Alice owns the grant. Should succeed."""
        # Create a new grant first (so we don't break other tests)
        create_resp = client.post("/grants", json={
            "title": "Deletable", "agency": "TEST", "url": "https://test.com",
        }, headers=auth_header(alice_token))
        grant_id = create_resp.json()["id"]
        resp = client.delete(f"/grants/{grant_id}", headers=auth_header(alice_token))
        assert resp.status_code == 200

    def test_delete_grant_as_admin(self, client, admin_token, seed_data):
        """Admin can delete any grant."""
        # (create then delete pattern)
```

**LOE: ~3 hours.** Requires careful test ordering or create-then-operate patterns.

### Tier 4: Schema Contract Verification (PARTIAL -- needs expansion)

The schema is the **universal contract** between backend and frontend. If the schema is wrong, the frontend silently breaks.

```python
class TestSchemaContract:
    def test_grant_schema_has_widget_metadata(self, client, seed_data):
        schema = client.get("/Grant").json()
        props = schema["properties"]
        # Widget types should be in schema
        assert props["url"]["ui"]["widget"] == "url"
        assert props["deadline"]["ui"]["widget"] == "date"
        assert props["amount_min"]["ui"]["widget"] == "currency"
        assert props["description"]["ui"]["widget"] == "textarea"

    def test_grant_schema_has_access_rules(self, client, seed_data):
        schema = client.get("/Grant").json()
        assert "access" in schema
        assert schema["access"]["read"]["rule"] == "anyone"
        assert schema["access"]["create"]["rule"] == "authenticated"

    def test_grant_schema_has_required_fields(self, client, seed_data):
        schema = client.get("/Grant").json()
        required = schema.get("required", [])
        assert "title" in required
        assert "agency" in required

    def test_grant_schema_has_protected_field_metadata(self, client, seed_data):
        schema = client.get("/Grant").json()
        user_owner = schema["properties"].get("user_owner", {})
        ui = user_owner.get("ui", {})
        assert ui.get("protected") is True

    def test_schema_urls_are_correct(self, client, seed_data):
        schema = client.get("/Grant").json()
        assert schema["$id"].endswith("/Grant")
        assert schema["$schema"].endswith("/Schema")
        assert schema["__tablename__"] == "grants"

    def test_agent_schema_has_run_method(self, client, seed_data):
        schema = client.get("/AgentActor").json()
        methods = schema.get("methods", {})
        assert "run" in methods
        assert methods["run"]["methods"] == ["POST"]
        # run() takes a 'task' parameter
        assert "task" in methods["run"]["parameters"]
```

**LOE: ~2 hours.** High ROI -- these tests catch frontend regressions before a browser is even opened.

### Tier 5: Full CRUD Lifecycle (PARTIAL -- needs delete + pagination)

```python
class TestGrantFullLifecycle:
    def test_create_read_update_delete(self, client, alice_token, admin_token):
        """Full CRUD lifecycle in one test."""
        # CREATE
        resp = client.post("/grants", json={
            "title": "Lifecycle Test", "agency": "DOE",
            "url": "https://energy.gov/test", "description": "Test grant",
        }, headers=auth_header(alice_token))
        assert resp.status_code == 201
        grant = resp.json()
        grant_id = grant["id"]
        assert grant["$schema"].endswith("/Grant")
        assert grant["$id"].endswith(f"/grants/{grant_id}")

        # READ
        resp = client.get(f"/grants/{grant_id}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Lifecycle Test"

        # UPDATE
        resp = client.put(f"/grants/{grant_id}", json={
            "title": "Updated Lifecycle", "agency": "DOE",
            "url": "https://energy.gov/test",
        }, headers=auth_header(alice_token))
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated Lifecycle"

        # DELETE (as admin since OWNER|ROLE('admin'))
        resp = client.delete(f"/grants/{grant_id}", headers=auth_header(admin_token))
        assert resp.status_code == 200

        # VERIFY GONE
        resp = client.get(f"/grants/{grant_id}")
        assert resp.status_code == 404

    def test_pagination(self, client, seed_data):
        resp = client.get("/grants?limit=1&offset=0")
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body
        assert "meta" in body
        assert body["meta"]["limit"] == 1
        assert len(body["data"]) <= 1
```

**LOE: ~2 hours.**

---

## :bar_chart: Operational Readiness Patterns

### Health Check Endpoints

Grant Watcher already has `/_meta` which serves as a basic health/discovery endpoint. A production-ready health check should go further, as recommended by [FastAPI health check best practices](https://www.index.dev/blog/how-to-implement-health-check-in-python):

```
GET /health          -> {"status": "healthy", "checks": {...}}
GET /health/live     -> 200 (process is alive, for k8s liveness)
GET /health/ready    -> 200 or 503 (can serve traffic, for k8s readiness)
```

**What a ready check should verify:**

| Check | What It Validates | Failure Mode |
|-------|------------------|--------------|
| DB connection | `SELECT 1` succeeds | SQLite file missing/locked |
| Model registration | `len(registered_models) >= expected` | Import error, missing model |
| Table existence | Each model's table exists | Migration failure |
| JWT config | Secret is configured, not default | Auth won't work |
| Matrix alive | `Actor.root()` is not None | Actor system failed to boot |

**Implementation cost: ~4 hours** for a proper health endpoint with sub-checks. Can be done as a N3TX framework feature (benefits all apps) or app-specific route.

### Startup Verification

The `create_app()` function in `/workspace/src/n3tx/core/app.py` does a lot of implicit setup:

1. Configures auth (`authorize.configure()`)
2. Prepares model registrations (pure)
3. Generates join models
4. Applies registrations (creates tables, runs auto-migration)
5. Creates FastAPI backend
6. Registers routes (direct or actor)
7. Mounts discovery endpoints

**What could fail silently:**

- A model with a bad field type registers but produces a broken schema
- Auto-migration adds a column but the migration file has conflicting logic
- Join model generation fails for a new parent-child pair
- The Matrix singleton is not initialized (actor routing silently fails)

**Current state:** No startup self-check exists. The first indication of failure is a runtime 500 error.

**Recommendation:** Add a `_verify_startup()` function called at the end of `create_app()` that runs the equivalent of the boot smoke tests. Log warnings for fixable issues, raise for fatal ones.

### Structured Logging

The app uses `logging.basicConfig()` with a simple format:

```python
logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')
```

For operational readiness, structured logging (JSON format) enables:
- Request tracing via correlation IDs
- Log aggregation in tools like Datadog, ELK, CloudWatch
- Performance monitoring (request duration)

**Current state:** Logging exists but is unstructured and inconsistent. The actor system logs TX routing, but there is no request-level trace ID.

**Recommendation for production:** Adopt `structlog` or JSON-formatted logging. Add a middleware that generates a request ID and propagates it through TX messages via `tx.meta['request_id']`. **LOE: ~1 day for framework-level implementation.**

### Configuration Validation

The `config.py` in Grant Watcher reads from environment variables with sensible defaults:

```python
JWT_SECRET = os.environ.get("N3TX_JWT_SECRET", "ntx-dev-secret-change-in-production")
```

> :warning: **Warning:** The default JWT secret is a well-known string. If deployed without setting `N3TX_JWT_SECRET`, any attacker can forge JWT tokens. This is the single highest-risk operational issue.

**Recommended validations at startup:**

```python
if JWT_SECRET == "ntx-dev-secret-change-in-production":
    if not DEBUG:
        raise RuntimeError("N3TX_JWT_SECRET must be set in production")
    logger.warning("Using default JWT secret -- DEVELOPMENT ONLY")
```

---

## :zap: Agent Testing Deep Dive

### The Agent Execution Path

The agent flow is the most complex path in the application:

```
POST /agents/1/run {"task": "Scan for grants"}
     |
     v
[NetworkAPI] -- TX(name='run', target='agents') --> [Matrix]
     |
     v
[AgentActor.handler_crud]  -- falls through to generic handler
     |
     v
[AgentActor.run(task)]     -- @expose_route method
     |
     +-- _resolve_tool_addrs()  -- href -> DB lookup -> actor addrs
     |
     +-- agent_run(prompt, tools, task)  -- from AgentMixin
           |
           +-- Create transient NetworkAdapter (for correlation)
           +-- discover_tools(addrs, matrix)  -- read schemas from actors
           +-- create_tool_function(spec)     -- exec() dynamic functions
           +-- Agent(llm, tools=...).run(task)  -- pydantic-ai loop
                 |
                 +-- LLM decides to call tool (e.g., grants_list)
                 +-- Tool function builds TX, sends via adapter.request()
                 +-- Matrix routes TX to Grant actor
                 +-- Grant.handler_crud('list') executes
                 +-- Response TX correlates back
                 +-- LLM receives tool result, continues reasoning
```

### What Is Tested vs What Is Not

| Step | Tested? | How |
|------|---------|-----|
| `_resolve_tool_addrs()` | Yes | `test_agent_resolves_tool_hrefs` verifies href -> addr resolution |
| `agent_run()` direct call | Yes | 3 tests call `agent.run()` with `TestModel` |
| Tool discovery from schemas | Implicitly | `test_agent_run_with_tool_call` exercises `discover_tools` |
| Tool routing through Matrix | Implicitly | TestModel calls `grants_list` which routes through Matrix |
| POST /agents/{id}/run via HTTP | **No** | All agent run tests bypass the HTTP layer |
| Auth on agent run endpoint | **No** | No test verifies that unauthenticated users cannot run agents |
| Error handling during agent run | **No** | No test for tool call failures, LLM errors, timeouts |
| Multiple sequential tool calls | **No** | TestModel calls one tool then stops |
| Transient adapter cleanup | **No** | No test verifies the adapter is removed from Matrix after run |

### Testing Strategy for Agents

Following [Pydantic AI's testing documentation](https://ai.pydantic.dev/testing/), the recommended approach uses `TestModel` for deterministic testing:

```python
from pydantic_ai.models.test import TestModel
```

**TestModel behavior:** It is "just plain old procedural Python code that tries to generate data that satisfies the JSON schema of a tool." It calls all registered tools by default, or specific tools via `call_tools=['tool_name']`.

**Three levels of agent testing:**

| Level | What It Tests | Determinism | Speed |
|-------|--------------|-------------|-------|
| **Unit** (TestModel, direct call) | Tool discovery, execution loop, result format | Fully deterministic | <1s |
| **Integration** (TestModel, via HTTP) | Full stack: HTTP -> auth -> actor -> agent -> tools -> response | Fully deterministic | 1-3s |
| **Evaluation** (FunctionModel, scripted) | Multi-turn conversations, specific tool sequences | Scripted deterministic | 1-5s |

**The critical gap is Level 2 -- integration via HTTP:**

```python
class TestAgentRunHTTP:
    def test_run_agent_via_api(self, client, seed_data, alice_token):
        """POST /agents/{id}/run should execute the agent and return results."""
        agent = seed_data["agent"]
        resp = client.post(
            f"/agents/{agent.id}/run",
            json={"task": "List all sources"},
            headers=auth_header(alice_token),
        )
        assert resp.status_code == 200
        result = resp.json()
        # The run() method returns JSON string, which the route returns as-is
        # (may need json.loads depending on how the route serializes)
        assert "answer" in result or isinstance(result, str)

    def test_run_agent_no_auth(self, client, seed_data):
        """Agent run should require authentication."""
        agent = seed_data["agent"]
        resp = client.post(
            f"/agents/{agent.id}/run",
            json={"task": "List grants"},
        )
        assert resp.status_code in (401, 403)
```

**Challenge:** The `test_agent_run.py` tests use `@pytest.mark.asyncio` and call `agent.run()` directly. This is because `TestModel` needs to be passed as a kwarg. The HTTP endpoint `POST /agents/{id}/run` uses the agent's configured `llm` field (which is `"test"` in test seed data, but `"test"` is not a valid pydantic-ai model string).

**Solution:** Either:
1. Use `Agent.override()` context manager to swap the model at the pydantic-ai level
2. Accept `llm` as a body parameter in the run endpoint (already supported via `**kwargs`)
3. Set the agent's `llm` field to `"test"` in the test DB and configure pydantic-ai to accept it

Option 2 is the most practical for testing. The `run()` method already accepts `**kwargs` which are forwarded to `agent_run()`, so passing `{"task": "...", "llm": TestModel()}` should work if the route passes through kwargs correctly.

**LOE: ~4 hours** to add HTTP-level agent tests with proper TestModel integration.

---

## :bar_chart: Feasibility & ROI

### Effort Estimate

| Work Item | LOE | Priority | Risk Reduced |
|-----------|-----|----------|-------------|
| Boot verification tests | 1 hour | P0 | Catastrophic regression |
| Auth flow tests (register, login, token) | 2 hours | P0 | Auth system breakage |
| ABAC enforcement tests (Grant access rules) | 3 hours | P0 | Security/permission bugs |
| Schema contract tests (widgets, access, required) | 2 hours | P1 | Frontend rendering bugs |
| Full CRUD lifecycle (create->read->update->delete) | 2 hours | P1 | Data integrity issues |
| Pagination tests | 1 hour | P1 | List endpoint regressions |
| Error response tests (401/403/404/422) | 2 hours | P1 | Silent failures |
| Agent run via HTTP tests | 4 hours | P1 | Agent system regressions |
| Protected field injection tests | 1 hour | P2 | user_owner bypass |
| Health check endpoint (framework feature) | 4 hours | P2 | Operational blind spots |
| **Total** | **~22 hours** | | |

That is **roughly 3 engineering days** for a comprehensive smoke test suite that covers the operational surface.

### What Breaks First When Someone Changes a Model?

This is the key question for understanding regression risk. Let's trace what happens when a developer adds a field to Grant:

```python
# Developer adds:
eligibility: str = Field(default='', description="Eligibility criteria")
```

**Cascade of effects:**

```
1. ProtoModel.schema() includes 'eligibility' in properties    [AUTO]
2. register_routes() includes it in POST/PUT body validation   [AUTO]
3. SQLiteStorage.create_table() runs auto-migration            [AUTO]
4. model_response() includes it in API responses               [AUTO]
5. Frontend form.js renders a new text input                   [AUTO]
6. Agent tool discovery includes it in grants_create params    [AUTO]
7. Existing tests pass (field has default)                     [OK]
8. BUT: no test verifies the field appears in schema           [GAP]
9. BUT: no test verifies the frontend renders it               [GAP]
10. BUT: no test verifies the agent can use it                 [GAP]
```

The framework handles steps 1-6 automatically. But **verification of the cascade** requires tests at levels 8-10. Without them, a developer adds a field, sees no test failures, ships it, and discovers days later that the frontend form is broken because the widget type was wrong.

### Cost of NOT Doing This

| Scenario | Without Smoke Tests | With Smoke Tests |
|----------|--------------------|--------------------|
| Developer adds a field with typo in widget name | Discovered by QA in staging, 2-4 hours of debugging | Test fails in CI, 5-minute fix |
| Auth interceptor refactor breaks OWNER check | Discovered in production when user deletes wrong record | Test fails immediately |
| Schema pipeline change breaks widget injection | Frontend shows raw inputs instead of currency/date pickers | Schema contract test catches it |
| Database migration corrupts agent tool hrefs | Agent silently discovers 0 tools, returns empty answers | Agent test catches missing tools |
| JWT secret defaults to dev value in production | Security breach | Config validation blocks deployment |

**Conservative estimate:** Each undetected regression costs **4-8 hours** of debugging time (the "three-layer wild goose chase" pattern documented in CLAUDE.md). The smoke test suite prevents **2-3 such incidents per month** during active development. At an engineering cost of $100/hour, the ROI breaks even in the **first month**.

### CI/CD Readiness Assessment

| Requirement | Current State | Needed |
|-------------|--------------|--------|
| Tests run without external dependencies | Yes (SQLite tempfile, TestModel for LLM) | Already CI-ready |
| Tests are deterministic | Mostly (session-scoped fixtures share state) | Add function-scoped option for isolation |
| Tests run fast (<5 min) | Yes (~10s for 30 tests) | Already fast enough |
| E2E tests require running server | Yes (Playwright needs live server) | Keep separate; run in CI with Docker |
| Coverage reporting | Not configured | Add `pytest-cov` |
| Linting/type checking | Not configured | Add `ruff` + `mypy` |

**The integration tests are already CI-ready.** The E2E (Playwright) tests need a separate CI step that starts the server. This is a standard pattern.

---

## :bulb: Trade-offs & Recommendations

### TestClient-Based vs Live Server Tests

| Approach | Pros | Cons |
|----------|------|------|
| **TestClient (recommended for smoke)** | Fast, deterministic, no server process, CI-friendly | Does not test actual HTTP transport, CORS, static file serving via Uvicorn |
| **Live server (Playwright E2E)** | Tests real user flows, catches frontend rendering bugs | Slow (3-5s per test), requires server process, flaky in CI |
| **Hybrid (recommended)** | Fast smoke + targeted E2E | Two test suites to maintain |

**Recommendation:** Use TestClient for all API-level smoke tests (Tiers 1-5 above). Keep Playwright E2E tests for critical user flows (navigation, form validation, auth UI). Run TestClient tests on every commit; run E2E tests on PR merge and nightly.

### Mocked LLM (TestModel) vs Real LLM

| Approach | When to Use | Cost |
|----------|------------|------|
| **TestModel** | CI, every commit, unit/integration tests | Free, deterministic |
| **FunctionModel** | Testing specific tool call sequences | Free, deterministic, requires scripting |
| **Real LLM (cached/VCR)** | Monthly eval runs, quality assessment | API costs, non-deterministic |
| **Real LLM (live)** | Pre-production validation | API costs, slow, non-deterministic |

As [Pydantic AI's testing docs](https://ai.pydantic.dev/testing/) note: "There's no ML or AI in TestModel, it's just plain old procedural Python code." This is a feature, not a limitation -- for smoke tests, determinism matters more than realism.

**Recommendation:** Use TestModel for all CI tests. Add a `pydantic_ai.models.test.TestModel(call_tools=['specific_tool'])` variant for tests that need to exercise specific tool paths. Reserve real LLM tests for a separate `tests/evals/` directory that runs weekly.

### Test Isolation vs Realistic Data

| Approach | Pros | Cons |
|----------|------|------|
| **Session-scoped fixtures (current)** | Fast, shared seed data, realistic interactions | Order-dependent, tests can pollute each other |
| **Function-scoped fixtures** | Perfect isolation, order-independent | Slow (DB setup per test), more boilerplate |
| **Hybrid: session + cleanup** | Fast + mostly isolated | Moderate complexity |

**Recommendation:** Keep session-scoped fixtures for the main seed data. For tests that mutate state (delete, update), use a **create-then-operate** pattern: create a fresh entity in the test, operate on it, and verify. This avoids polluting shared seed data without the overhead of per-test DB setup.

```python
def test_delete_grant(self, client, alice_token, admin_token):
    # Create a fresh grant (don't touch seed data)
    resp = client.post("/grants", json={...}, headers=auth_header(alice_token))
    grant_id = resp.json()["id"]
    # Delete it
    resp = client.delete(f"/grants/{grant_id}", headers=auth_header(admin_token))
    assert resp.status_code == 200
```

---

## :calendar: Implementation Roadmap

### Phase 1: Foundation (Day 1) -- P0

**Goal:** Boot verification + auth flow. If these pass, the app is fundamentally operational.

```
Files to create/modify:
  example_grants/tests/test_boot.py         [NEW] ~50 lines
  example_grants/tests/test_auth_flow.py    [NEW] ~80 lines

Tests added: ~12
Time: 3 hours
```

**Deliverables:**
- Boot verification: app starts, models register, schemas resolve, static files serve
- Auth: register, login, token decode, /auth/me, invalid tokens

### Phase 2: Security & Contracts (Day 2) -- P0/P1

**Goal:** ABAC enforcement + schema contracts. The app is both secure and rendering correctly.

```
Files to create/modify:
  example_grants/tests/test_abac.py         [NEW] ~100 lines
  example_grants/tests/test_schema_endpoints.py [EXTEND] +60 lines

Tests added: ~15
Time: 5 hours
```

**Deliverables:**
- ABAC: Grant access rules (ANYONE read, AUTHENTICATED create, OWNER|ADMIN delete)
- Schema: widget metadata, access rules, required fields, protected fields, $id/$schema

### Phase 3: Data Integrity (Day 3) -- P1

**Goal:** Full CRUD lifecycle, pagination, error responses. Data flows correctly in all directions.

```
Files to create/modify:
  example_grants/tests/test_grants_crud.py  [EXTEND] +80 lines
  example_grants/tests/test_error_handling.py [NEW] ~100 lines

Tests added: ~18
Time: 5 hours
```

**Deliverables:**
- Full lifecycle: create->read->update->delete with verification
- Pagination: limit, offset, meta envelope, has_more
- Errors: 401 (no auth), 403 (wrong role), 404 (missing entity), 422 (validation)

### Phase 4: Agent Verification (Day 4) -- P1

**Goal:** Agent execution via HTTP, tool discovery, error handling.

```
Files to create/modify:
  example_grants/tests/test_agent_run.py    [EXTEND] +60 lines
  example_grants/tests/test_agent_http.py   [NEW] ~80 lines

Tests added: ~10
Time: 4 hours
```

**Deliverables:**
- Agent run via HTTP POST endpoint
- Auth requirements for agent endpoints
- Tool discovery verification (correct tools from correct actors)
- Error handling (invalid task, missing tools)

### Phase 5: Operational Hardening (Day 5) -- P2

**Goal:** Health check, config validation, documentation.

```
Files to create/modify:
  example_grants/tests/test_discovery.py    [NEW] ~30 lines
  example_grants/tests/test_protected.py    [NEW] ~40 lines
  (Optional: framework-level health endpoint)

Tests added: ~8
Time: 3 hours
```

**Deliverables:**
- Discovery endpoint tests (/_meta, /.well-known/agent.json)
- Protected field tests (user_owner injection on create, stripping on update)
- Documentation of the test suite and how to run it

### Summary Timeline

```
Day 1 [P0]: Boot + Auth         ------> 12 tests, 3 hours
Day 2 [P0]: ABAC + Schema       ------> 15 tests, 5 hours
Day 3 [P1]: CRUD + Pagination   ------> 18 tests, 5 hours
Day 4 [P1]: Agent HTTP           ------> 10 tests, 4 hours
Day 5 [P2]: Ops Hardening        ------> 8 tests, 3 hours
                                         ─────────────────
                                 Total:  63 tests, 20 hours
                                 Current: 30 tests
                                 After:   93 tests (~3x coverage)
```

### Expected Test Execution Profile

```
Current:   30 tests in ~10 seconds
After:     93 tests in ~25 seconds (estimated)
CI target: < 60 seconds (well within 15-minute smoke test guideline)
```

Per [Microsoft's Engineering Playbook](https://microsoft.github.io/code-with-engineering-playbook/automated-testing/smoke-testing/), smoke tests should "keep execution time and complexity to minimum." The 25-second execution time is well within the recommended threshold.

---

## :bar_chart: Comparison: Grant Watcher vs example_actor Test Coverage

The `example_actor/` app has the most mature test suite in the codebase. Here is how Grant Watcher compares:

| Test Category | example_actor | Grant Watcher (current) | Grant Watcher (proposed) |
|--------------|--------------|------------------------|--------------------------|
| Auth flow (register, login, token) | 18 tests | 0 tests | 12 tests |
| CRUD operations | 20 tests | 15 tests | 25 tests |
| ABAC / authorization | 8 tests | 0 tests | 8 tests |
| Error handling (401/403/404/422) | 15 tests | 2 tests | 12 tests |
| Schema endpoints | 4 tests | 4 tests | 10 tests |
| Pagination | 4 tests | 0 tests | 4 tests |
| FK hydration | 3 tests | 2 tests | 3 tests |
| Custom methods | 6 tests | 0 tests | 4 tests |
| Agent execution | N/A | 4 tests | 10 tests |
| E2E (Playwright) | 0 tests | 7 tests | 7 tests |
| **Total** | **~78 tests** | **30 tests** | **~95 tests** |

The proposed suite brings Grant Watcher to **parity with example_actor** while adding the unique agent-specific coverage that no other example app has.

---

## :warning: Top 5 Risks If We Skip This

1. **Default JWT secret in production.** The config defaults to `"ntx-dev-secret-change-in-production"`. Without a startup check, this will eventually be deployed unmodified. Any attacker who reads the source code can forge admin tokens.

2. **ABAC rules silently fail open.** If the `auth_interceptor` or `handler_crud._authorize()` has a bug, requests that should be denied are allowed. Without ABAC tests, this is discovered when a user deletes data they should not have access to.

3. **Agent tool discovery returns empty.** If a model rename or schema pipeline change causes `discover_tools()` to find 0 tools, the agent runs but does nothing useful. The user sees "No grants found" -- which is a valid answer, not an error. Without agent integration tests, this is indistinguishable from correct behavior.

4. **Schema widget metadata breaks.** If the `widget` schema pipeline stage (`schema_ext.py`) fails to inject `ui.widget`, the frontend falls back to plain text inputs. Currency fields show as text, dates show as text, URLs show as text. The app "works" but the UX degrades silently.

5. **Protected field bypass.** If `user_owner` is not auto-injected on create, grants are created with `user_owner=None`. OWNER-based access rules then fail for everyone (no one is the owner). Without a protected-field test, this is only noticed when no user can delete their own grants.

---

## :link: Sources

- [Microsoft Engineering Playbook -- Smoke Testing](https://microsoft.github.io/code-with-engineering-playbook/automated-testing/smoke-testing/) -- smoke test principles and CI/CD integration
- [BrowserStack -- What is Smoke Testing](https://www.browserstack.com/guide/smoke-testing) -- comprehensive 2026 guide to smoke testing
- [CircleCI -- Smoke Testing in CI/CD Pipelines](https://circleci.com/blog/smoke-tests-in-cicd-pipelines/) -- integrating smoke tests as quality gates
- [FastAPI -- Testing](https://fastapi.tiangolo.com/tutorial/testing/) -- official TestClient documentation
- [Index.dev -- FastAPI Health Check Endpoint](https://www.index.dev/blog/how-to-implement-health-check-in-python) -- health check implementation patterns
- [Pydantic AI -- Testing](https://ai.pydantic.dev/testing/) -- TestModel, FunctionModel, and agent testing patterns
- [Pydantic AI -- TestModel API](https://ai.pydantic.dev/api/models/test/) -- TestModel class reference
- [Pydantic -- Building Agentic Applications](https://pydantic.dev/articles/building-agentic-application) -- production agentic app patterns
- [Schema-Driven Development -- Modern Approach](https://blog.noclocks.dev/schema-driven-development-and-single-source-of-truth-essential-practices-for-modern-developers) -- SDD philosophy
- [SDD -- Schema Driven Development (Medium)](https://medium.com/@hintology/sdd-schema-driven-development-f1d232d73ea6) -- schema as contract pattern
- [JSON Schema -- Validation, Contract Testing, Dynamic Forms](https://sohamnakhare.medium.com/exploring-json-schema-validation-contract-testing-and-dynamic-forms-c0472f4de2de) -- using JSON Schema for frontend-backend consistency
- [Mercari -- Production Readiness Checklist](https://github.com/mercari/production-readiness-checklist) -- microservice operational readiness
- [O'Reilly -- Production-Ready Microservices](https://www.oreilly.com/library/view/production-ready-microservices/9781491965962/app01.html) -- production readiness appendix
- [GoReplay -- Production Readiness Checklist 2025](https://goreplay.org/blog/production-readiness-checklist-20250808133113/) -- 7 key steps
- [SitePoint -- Testing AI Agents: Validating Non-Deterministic Behavior](https://www.sitepoint.com/testing-ai-agents-deterministic-evaluation-in-a-non-deterministic-world/) -- testing strategies for agentic systems
- [VirtusLab -- How to Test and Evaluate Agentic Systems](https://virtuslab.com/blog/ai/testing-evaluating-agentic-systems/) -- reliability testing for agents
- [EPAM -- Testing Pyramid 2.0 for GenAI Apps](https://www.epam.com/insights/ai/blogs/reimagining-testing-pyramid-for-genai-applications) -- adapted testing pyramid for LLM applications
- [MarkTechPost -- Bulletproof Agentic Workflows with PydanticAI](https://www.marktechpost.com/2026/02/19/a-coding-implementation-to-build-bulletproof-agentic-workflows-with-pydanticai-using-strict-schemas-tool-injection-and-model-agnostic-execution/) -- strict schemas and tool injection
- [Scenario -- Test Pydantic AI Agents](https://langwatch.ai/scenario/agent-integration/pydantic-ai/) -- VCR-style agent testing
- [UK Government Technology Blog -- Validating a Distributed Architecture with JSON Schema](https://technology.blog.gov.uk/2015/01/07/validating-a-distributed-architecture-with-json-schema/) -- schema validation at scale
