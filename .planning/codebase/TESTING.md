# Testing Patterns

**Analysis Date:** 2026-03-04

## Test Framework

**Runner:**
- pytest >= 8.2
- Config: `pyproject.toml` (no `pytest.ini` or `tox.ini`)
- `pytest-asyncio` for async test support (`@pytest.mark.asyncio`)

**Assertion Library:**
- Native `assert` statements (no third-party assertion library)
- `pytest.raises()` for exception testing

**Additional Dependencies:**
- `httpx >= 0.27` (FastAPI TestClient backend)
- `pydantic-ai >= 1.0` (agent testing with `TestModel`)
- `playwright` (e2e tests, not in `dev` extras -- installed separately)

**Run Commands:**
```bash
# Framework unit tests
cd /workspace && python3 -m pytest src/pybend/core/tests/unit/

# Agent unit tests
cd /workspace && python3 -m pytest src/pybend/core/agents/tests/

# Integration tests (Level 1/2 direct routes)
cd /workspace && python3 -m pytest example_api/tests/

# Integration tests (Level 3 actor routing)
cd /workspace && python3 -m pytest example_actor/tests/

# Grant-watching app tests (actor routing + agents)
cd /workspace && python3 -m pytest example_grants/tests/

# E2E tests (requires running server)
cd /workspace && python3 -m pytest example_grants/tests/e2e/

# All tests
cd /workspace && python3 -m pytest

# Single test file
cd /workspace && python3 -m pytest src/pybend/core/tests/unit/test_actor_system.py

# Single test class or function
cd /workspace && python3 -m pytest src/pybend/core/tests/unit/test_actor_system.py::TestTX::test_reply_swaps_source_target
```

## Test File Organization

**Location:** Tests are organized by scope in dedicated directories:

```
src/pybend/core/tests/
    conftest.py              # Shared fixtures (imports example_api app)
    helpers.py               # auth_header(), parse_href_id(), extract_items()
    unit/
        conftest.py          # Unit-specific fixtures (mock storage, auth, requests)
        test_actor_system.py # Actor, Matrix, TX, interceptors (85 tests)
        test_actor_model.py  # ActorModel class structure (46 tests)
        test_actor_model_crud.py  # handler_crud() (49 tests)
        test_actor_model_handler.py  # handler() dispatch (8 tests)
        test_actor_model_authorize.py  # Tier 2 auth (20 tests)
        test_actor_model_lifecycle.py  # Lifecycle events (16 tests)
        test_actor_model_integration.py  # Full TX routing (58 tests)
        test_proto_model.py  # ProtoModel base class (58 tests)
        test_proto_schema.py # Schema pipeline (52 tests)
        test_proto_dump.py   # Dump pipeline (43 tests)
        test_proto_dump_stages.py  # Dump pipeline stages (42 tests)
        test_auth.py         # Auth token create/verify (28 tests)
        test_auth_edge_cases.py  # Auth edge cases (19 tests)
        test_auth_interceptor.py  # Interceptor auth (51 tests)
        test_access_algebra.py  # Rule algebra ANYONE|OWNER|ROLE (54 tests)
        test_access_context.py  # AccessContext evaluation (15 tests)
        test_access_denied.py  # Access denied responses (9 tests)
        test_access_schema.py  # Schema access injection (10 tests)
        test_rules.py        # Authorization rules (68 tests)
        test_resolver.py     # Rule resolver (18 tests)
        test_routes.py       # Route registration (20 tests)
        test_sqlite_storage.py  # SQLite storage (26 tests)
        test_sqlite_migration.py  # Migration system (29 tests)
        test_sqlite_helpers.py  # SQL helpers (4 tests)
        test_json_storage.py  # JSON storage (24 tests)
        test_storable_mixin.py  # StorableMixin injection (23 tests)
        test_storage_adjunction.py  # Storage adjunction (13 tests)
        test_registrar.py    # Model registry (17 tests)
        test_decorators.py   # @expose_route (14 tests)
        test_introspection.py  # Type introspection (38 tests)
        test_typer.py        # Ref/ListRef types (20 tests)
        test_ref.py          # FK references (7 tests)
        test_populate.py     # Field population (25 tests)
        test_config.py       # Config module (11 tests)
        test_base_user.py    # BaseUser model (14 tests)
        test_backend.py      # Backend abstraction (16 tests)
        test_ssr.py          # SSR modes (63 tests)
        test_erroring.py     # MethodError (4 tests)
        test_viewable_mixin.py  # ViewableMixin (10 tests)
        test_schema_ext.py   # Schema extensions (36 tests)
        test_discovery.py    # Route discovery (18 tests)
        test_abstract_storage.py  # Abstract storage (3 tests)
        widgets/
            test_widget.py   # Widget types (39 tests)
            test_schema_ext.py  # Widget schema extension (20 tests)

src/pybend/core/agents/tests/
    conftest.py              # Agent fixtures (reset_actor_state, fresh_matrix, memory_storage)
    test_agent_actor.py      # AgentActor CRUD + run (29 tests)
    test_mixin.py            # AgentMixin injection (12 tests)
    test_tools.py            # Tool discovery + generation (12 tests)

example_grants/tests/
    conftest.py              # Grants app fixtures (test_db, seed_data, client, tokens)
    helpers.py               # auth_header()
    test_grants_crud.py      # Grant CRUD (7 tests)
    test_sources_crud.py     # Source CRUD (3 tests)
    test_agent_crud.py       # Agent CRUD via API (6 tests)
    test_agent_run.py        # Agent LLM run (4 tests)
    test_auth_flow.py        # Login, register, token refresh (18 tests)
    test_authorization.py    # ABAC rules enforcement (23 tests)
    test_error_handling.py   # Error response format (22 tests)
    test_pagination.py       # Pagination (14 tests)
    test_schema_endpoints.py # Schema endpoints (4 tests)
    test_security_config.py  # Security settings (11 tests)
    test_ssrf.py             # SSRF protection (17 tests)
    test_boot.py             # App bootstrap (9 tests)
    e2e/
        test_navigation.py   # Playwright: list/detail nav (4 tests)
        test_create_validation.py  # Playwright: create form validation (3 tests)

example_api/tests/           # ~399 tests (Level 1/2 direct routes)
    conftest.py, helpers.py
    test_products_crud.py    # (33 tests)
    test_comments_crud.py    # (21 tests)
    test_likes_crud.py       # (10 tests)
    test_schema_endpoints.py # (42 tests)
    test_auth_flow.py        # (17 tests)
    test_authorization.py    # (18 tests)
    test_custom_methods.py   # (25 tests)
    test_error_handling.py   # (31 tests)
    test_pagination.py       # (20 tests)
    test_fk_hydration.py     # (13 tests)
    test_protected_fields.py # (7 tests)
    test_product_model.py    # (20 tests)
    test_user_model.py       # (27 tests)
    test_comment_model.py    # (17 tests)
    test_like_model.py       # (6 tests)
    test_cross_model_workflows.py  # (18 tests)
    test_jwt_tokens.py       # (15 tests)
    test_middleware.py        # (13 tests)
    test_seed.py             # (12 tests)
    test_collection_routes.py  # (11 tests)
    e2e/
        test_comment.py      # (1 test)
        test_like_favorite.py  # (1 test)

example_actor/tests/         # ~399 tests (Level 3 actor routing, mirrors example_api)
    # Same file structure as example_api/tests/
```

**Naming:**
- Test files: `test_{subject}.py`
- Test classes: `Test{Subject}` (e.g., `TestGrantModelAuthorization`, `TestHandlerCrudCreate`)
- Test methods: `test_{behavior_description}` (e.g., `test_create_grant_authenticated`)

## Test Structure

**Suite Organization (unit tests):**
```python
"""Module docstring describing what these tests cover."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from pybend.core.actors.tx import TX
from pybend.core.actors.actor import Actor

pytestmark = pytest.mark.unit


# ===================================================================
# Test model (module-level, reused across test classes)
# ===================================================================

class _TestModel(ActorModel, auto_register=False):
    __tablename__: ClassVar[str] = 'test'
    __storable__: ClassVar[bool] = True
    name: str = Field(default='')


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture(autouse=True)
def mock_storage():
    storage = MagicMock()
    _TestModel.storage = storage
    yield storage
    _TestModel.storage = None


@pytest.fixture
def make_tx():
    def _make(name, data=None):
        return TX(name=name, source='test', target='test', data=data or {})
    return _make


# ===================================================================
# TestClassName
# ===================================================================

class TestClassName:
    """One-line description of what this class tests."""

    def test_specific_behavior(self, make_tx):
        tx = make_tx('create', {'name': 'Widget'})
        result = _TestModel.handler_crud(tx)
        assert isinstance(result, dict)
```

**Suite Organization (integration tests):**
```python
"""Tests for Grant CRUD operations via the API."""
import pytest
from helpers import auth_header


class TestGrantCreate:
    def test_create_grant_authenticated(self, client, alice_token):
        resp = client.post("/grants", json={
            "title": "New Energy Grant",
            "agency": "DOE",
            "url": "https://energy.gov/new-grant",
        }, headers=auth_header(alice_token))
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "New Energy Grant"

    def test_create_grant_unauthenticated(self, client):
        resp = client.post("/grants", json={...})
        assert resp.status_code in (401, 403)
```

**Key patterns:**
- `pytestmark = pytest.mark.unit` at module level for all unit test files
- Comment separator blocks (`# ====`) between test classes for visual organization
- Test classes group related assertions; test methods test one behavior each
- Inner test model classes use `auto_register=False` to avoid polluting the global actor registry

## Mocking

**Framework: `unittest.mock`**

**Patterns:**

**1. Mock storage for unit tests (inject directly on class):**
```python
@pytest.fixture(autouse=True)
def mock_storage():
    storage = MagicMock()
    _CrudModel.storage = storage
    yield storage
    _CrudModel.storage = None
```
File: `src/pybend/core/tests/unit/test_actor_model_crud.py`

**2. mock_method for Pydantic BaseModel instances:**
```python
from contextlib import contextmanager

@contextmanager
def mock_method(instance, name, replacement):
    """Pydantic's __setattr__/__delattr__ prevent normal mock patching.
    Use object.__setattr__/delattr__ to bypass."""
    object.__setattr__(instance, name, replacement)
    try:
        yield replacement
    finally:
        object.__delattr__(instance, name)

# Usage:
mock_handler = AsyncMock()
with mock_method(actor_instance, 'handler', mock_handler):
    await actor_instance.inbox(tx)
mock_handler.assert_awaited_once_with(tx)
```
File: `src/pybend/core/tests/unit/test_actor_system.py`

**3. Capture sent messages via mock inbox:**
```python
sent = []
async def capture_inbox(tx):
    sent.append(tx)

with mock_method(matrix, 'inbox', capture_inbox):
    await worker.handler(tx)

assert len(sent) == 1
assert sent[0].name == 'GREET_RESPONSE'
```

**4. MagicMock for FastAPI Request objects:**
```python
@pytest.fixture
def mock_request():
    request = MagicMock()
    request.state = MagicMock()
    request.state.user = {'user_id': 1, 'email': 'test@example.com', 'role': 'user'}
    return request
```
File: `src/pybend/core/tests/unit/conftest.py`

**5. Module-level mocking with `patch()`:**
```python
with patch('pybend.core.actors.matrix.logger') as mock_logger:
    await m.inbox(tx)
    mock_logger.warning.assert_called_once()
```

**What to Mock:**
- Storage backends (unit tests should not touch real DB)
- Actor inbox/handler/send for routing tests
- Matrix instance for parent routing verification
- Logger for warning/error assertion
- LLM via `pydantic_ai.models.test.TestModel`

**What NOT to Mock:**
- Schema generation (test the full pipeline)
- Model validation (test real Pydantic behavior)
- Auth rule evaluation (test real rule algebra)
- Integration tests hit real HTTP endpoints via TestClient

## Fixtures and Factories

**Session-scoped fixtures (conftest.py pattern across all example apps):**

```python
@pytest.fixture(scope="session")
def test_db():
    """Create temporary DB, re-register all models, clean up after session."""
    db_fd, db_path = tempfile.mkstemp(suffix='_test_grants.db')
    original_db = config.SQLITE_DB_FILE
    config.SQLITE_DB_FILE = db_path
    _setup_test_db(db_path)
    yield db_path
    config.SQLITE_DB_FILE = original_db
    try:
        os.close(db_fd)
    except OSError:
        pass
    if os.path.exists(db_path):
        os.unlink(db_path)

@pytest.fixture(scope="session")
def seed_data(test_db):
    """Seed test DB with users, entities. Returns dict of created objects."""
    users = _seed_users()
    grants = _seed_grants(users)
    agent = _seed_agent()
    return {"users": users, "grants": grants, "agent": agent}

@pytest.fixture(scope="session")
def client(test_db, seed_data):
    """FastAPI TestClient wrapping the app."""
    from fastapi.testclient import TestClient
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

@pytest.fixture(scope="session")
def alice_token(seed_data):
    alice = seed_data["users"]["alice"]
    return create_token(alice.id, alice.email, alice.role)
```

**Factory fixtures (SD-3 pattern):**
```python
@pytest.fixture(scope="session")
def make_product(client, alice_token):
    def _factory(name="Factory Product", price=19.99, token=None, **overrides):
        return _make_product(client, token or alice_token, name=name,
                             price=price, **overrides)
    return _factory
```

**TX factory fixture:**
```python
@pytest.fixture
def make_tx():
    def _make(name, data=None):
        return TX(name=name, source='test', target='crud_test', data=data or {})
    return _make
```

**Agent test fixtures (`src/pybend/core/agents/tests/conftest.py`):**
```python
@pytest.fixture(autouse=True)
def reset_actor_state():
    """Isolate actor/matrix state between tests."""
    saved_matrix = Actor.__matrix__
    saved_children = Actor.__children__.copy()
    Actor.__matrix__ = None
    Actor.__children__ = {}
    yield
    Actor.__matrix__ = saved_matrix
    Actor.__children__ = saved_children

@pytest.fixture
def fresh_matrix():
    return Matrix()

@pytest.fixture
def memory_storage():
    return SQLiteStorage(':memory:')
```

**Location:**
- `src/pybend/core/tests/conftest.py` -- shared integration fixtures (imports `example_api` app)
- `src/pybend/core/tests/unit/conftest.py` -- unit test fixtures (mocks, auth helpers)
- `src/pybend/core/agents/tests/conftest.py` -- agent test fixtures (actor state reset)
- `example_grants/tests/conftest.py` -- grants app fixtures (DB, seed, tokens)
- `example_api/tests/conftest.py` -- API example fixtures
- `example_actor/tests/conftest.py` -- Actor example fixtures
- `*/tests/helpers.py` -- utility functions (`auth_header()`, `parse_href_id()`)

## Coverage

**Requirements:** None enforced (no `--cov-fail-under` in config)

**View Coverage:**
```bash
cd /workspace && python3 -m pytest --cov=src/pybend/core src/pybend/core/tests/unit/
```

## Test Types

**Unit Tests (~1100 tests in `src/pybend/core/tests/unit/` + agents/tests/):**
- Test individual classes and methods in isolation
- Mock storage, external dependencies
- Mark: `pytestmark = pytest.mark.unit`
- Focus: model behavior, schema pipeline, auth rules, actor messaging, storage operations

**Integration Tests (~800+ tests across example_api + example_actor + example_grants):**
- Test full HTTP request/response cycle via FastAPI `TestClient`
- Real database (temp SQLite file), real model registration, real auth
- Focus: CRUD endpoints, auth flow, pagination, FK hydration, error handling, authorization
- `example_api/tests/` and `example_actor/tests/` are structurally identical (same tests, different routing mode)

**E2E Tests (~7 tests in example_grants/tests/e2e/):**
- Playwright browser automation (Chromium headless)
- Require a running server (`cd example_grants && python main.py`)
- Focus: navigation, form validation, UI feedback
- NOT run as part of regular test suite (manual or CI with server)

**Agent Tests:**
- Unit: `src/pybend/core/agents/tests/` -- mixin injection, tool discovery, function generation, LLM execution with TestModel
- Integration: `example_grants/tests/test_agent_crud.py` -- agent CRUD via API
- Integration: `example_grants/tests/test_agent_run.py` -- agent LLM run with real DB

## Common Patterns

**Async Testing:**
```python
@pytest.mark.asyncio
async def test_inbox_calls_handler(self):
    a = Actor(addr='test')
    mock_handler = AsyncMock()
    tx = TX(name='X', source='a', target='test')
    with mock_method(a, 'handler', mock_handler):
        await a.inbox(tx)
    mock_handler.assert_awaited_once_with(tx)
```

**Error Testing:**
```python
def test_get_nonexistent_returns_404_error(self, mock_storage, make_tx):
    mock_storage.get.return_value = None
    tx = make_tx('get', {'id': 999})
    result = _CrudModel.handler_crud(tx)
    assert isinstance(result, TX)
    assert result.is_error
    assert result.data['code'] == 404
```

**Auth Testing (integration):**
```python
def test_create_grant_authenticated(self, client, alice_token):
    resp = client.post("/grants", json={...},
                       headers=auth_header(alice_token))
    assert resp.status_code == 201

def test_create_grant_unauthenticated(self, client):
    resp = client.post("/grants", json={...})
    assert resp.status_code in (401, 403)
```

**Paginated Response Testing:**
```python
def test_list_grants_public(self, client, seed_data):
    resp = client.get("/grants")
    body = resp.json()
    data = body["data"] if isinstance(body, dict) else body
    assert len(data) >= 1
```

**Schema Metadata Testing:**
```python
def test_list_grants_has_schema_metadata(self, client, seed_data):
    resp = client.get("/grants")
    body = resp.json()
    data = body["data"] if isinstance(body, dict) else body
    for item in data:
        assert "$schema" in item
        assert "$id" in item
```

**Agent LLM Testing (TestModel):**
```python
@pytest.mark.asyncio
async def test_agent_run_with_tools(self, fresh_matrix, tmp_path):
    from pydantic_ai.models.test import TestModel

    storage = SQLiteStorage(str(tmp_path / 'agents.db'))

    class Grant(ActorModel):
        __tablename__ = 'grants'
        __storable__ = True
        title: str = Field(default='')

    register_model(Grant, storage=storage)

    # TestModel calls grants_list, which does a real DB query
    result = await Scanner.agent_run(
        Scanner,
        prompt='List available grants.',
        tools=['grants'],
        task='List all grants',
        llm=TestModel(call_tools=['grants_list']),
    )
    assert 'answer' in result
    assert result['usage']['requests'] >= 1
```

**File-based SQLite for tests needing real DB:**
```python
def test_crud(self, fresh_matrix, tmp_path):
    storage = SQLiteStorage(str(tmp_path / 'test.db'))
    register_model(MyModel, storage=storage)
    # `:memory:` creates separate DB per connection -- use tmp_path instead
```

**E2E Test Pattern (Playwright):**
```python
def test_main_list_click_navigates():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(BASE)
        _wait_for_items(page)
        # Interact via page.evaluate() for Shadow DOM
        page.evaluate("""() => {
            const table = document.querySelector('ntt-table');
            const row = table.shadowRoot.querySelector('.table-body ntt-row');
            row.shadowRoot.querySelector('.row').click();
        }""")
        page.wait_for_timeout(1500)
        # Assert state
        after = page.evaluate("""() => ({
            hash: location.hash,
            hasBackBtn: !!document.querySelector('ntt-router')
                ?.shadowRoot?.querySelector('.back-btn'),
        })""")
        assert after["hash"].startswith("#Grant/")
        browser.close()
```

## Auth Helper Pattern

All integration test suites use the same helper:
```python
# tests/helpers.py
def auth_header(token):
    return {"x-access-token": token}
```

Fixtures provide tokens for different roles:
```python
alice_token   # regular user
bob_token     # regular user (different user for cross-user tests)
charlie_token # regular user (third user)
admin_token   # admin role
```

## Test Documentation Pattern

Authorization test files include a test plan docstring at the top:
```python
"""
Test plan for authorization (ABAC rules)
========================================

GRANT MODEL AUTHORIZATION
  - test_anyone_can_read_grants_no_auth_required
  - test_authenticated_users_can_create_grants
  ...
"""
```
See `example_grants/tests/test_authorization.py`, `example_grants/tests/test_ssrf.py`.

## Coverage Gaps

**Not tested:**
- WebSocket communication (no WebSocket tests found)
- Federation protocol (mentioned as future -- `federation` in ROADMAP)
- Frontend JavaScript (no JS unit test framework detected -- only Playwright e2e)
- Performance under load (profiling tools exist at `src/pybend/core/tests/profiling/` but no automated perf tests)
- Database concurrency (tests use single-threaded TestClient)
- Custom migration scripts (migration framework tested, but app-specific migrations in `example_grants/migrations/` not tested)
- Widget rendering (backend widget types tested, but frontend Widget JS classes not unit-tested)
- Error recovery in actor message routing (e.g., retry, dead letter)
- Agent tool execution errors (tool calls that fail mid-LLM-run)

**Partially tested:**
- SSRF protection: unit-tested in `test_ssrf.py` but not integration-tested via the actual `scrape` endpoint
- Security config: some tests are documentation-only (`pass` body, e.g., `test_debug_can_be_enabled_via_env`)
- E2E: only covers grants app navigation and create validation; no e2e for edit, delete, auth UI flow

---

*Testing analysis: 2026-03-04*
