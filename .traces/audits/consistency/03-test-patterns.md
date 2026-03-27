# Test Patterns Audit

**Date**: 2026-03-26
**Scope**: All test files across packages/, examples/, and apps/
**Focus**: Fixture patterns, database strategy, auth handling, mocking, naming, isolation

---

## Executive Summary

~170 test files, ~21,400 lines of test code. Framework unit tests are well-structured with proper isolation. Integration and E2E tests show **significant drift**: session-scoped shared databases, global config mutation, duplicated utilities, and missing test markers block parallel execution and selective filtering.

---

## Test Distribution

| Location | Files | Lines | Avg/File |
|----------|-------|-------|----------|
| n3tx-core/unit | 47 | ~8,500 | 180 |
| n3tx-actors | 20 | ~4,000 | 200 |
| n3tx-agents | 5 | ~1,200 | 240 |
| n3tx-trace | 6 | ~1,000 | 167 |
| examples/core | 20 | ~1,800 | 90 |
| examples/actors | 20 | ~1,700 | 85 |
| examples/grants | 16 | ~1,400 | 88 |
| examples/chat | 7 | ~800 | 114 |
| examples/pygentic | 5 | ~400 | 80 |
| apps/veille | 4 | ~400 | 100 |

---

## Fixture Patterns

### Pattern A: Unit Test Fixtures (packages/)

```python
# n3tx-core/tests/unit/conftest.py
@pytest.fixture(autouse=True)
def _ensure_debug_off():
    original = config.DEBUG
    config.DEBUG = False
    yield
    config.DEBUG = original

@pytest.fixture
def jwt_secret():
    return 'test-secret-key-for-unit-tests'

@pytest.fixture
def test_token(configure_auth, jwt_secret):
    return create_token(user_id=1, ...)

@pytest.fixture
def mock_storage():
    return MagicMock()
```

**Scope**: `function` (default) -- tests fully isolated.
**Status**: EXEMPLARY

### Pattern B: Integration Fixtures (examples/)

```python
# examples/*/tests/conftest.py (IDENTICAL across all examples)
@pytest.fixture(scope="session")
def test_db():
    db_fd, db_path = tempfile.mkstemp(suffix='_test_n3tx.db')
    config.SQLITE_DB_FILE = db_path  # Global config mutation!
    _setup_test_db(db_path)
    yield db_path
    os.unlink(db_path)

@pytest.fixture(scope="session")
def seed_data(test_db):
    users = _seed_users()
    products = _seed_products()
    return {...}

@pytest.fixture(scope="session")
def client(test_db, seed_data):
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
```

**Scope**: `session` -- one app + DB for all tests.
**Status**: FUNCTIONAL but fragile.

### Pattern C: E2E Fixtures (examples/*/tests/e2e/)

```python
@pytest.fixture(scope="session", autouse=True)
def e2e_server(request):
    port = find_free_port()
    tmp_dir = tempfile.mkdtemp(prefix="e2e_core_")
    db_path = os.path.join(tmp_dir, "test_e2e.db")
    run_seed(_APP_DIR, db_path)
    proc = start_server(_APP_DIR, port, db_path, extra_env={...})
    # Patch BASE on collected test modules
    for item in request.session.items:
        if hasattr(item.module, 'BASE'):
            item.module.BASE = base_url
    yield base_url
    stop_server(proc)
    shutil.rmtree(tmp_dir, ignore_errors=True)
```

**Status**: GOOD -- subprocess isolation, dynamic ports, clean temp DB.

### Pattern D: Actor State Reset

```python
# n3tx-actors, n3tx-agents conftest files (DUPLICATED)
@pytest.fixture(autouse=True)
def reset_actor_state():
    saved_matrix = Actor.__matrix__
    saved_children = Actor.__children__.copy()
    saved_matrix_children = Matrix.__children__.copy()
    Actor.__matrix__ = None
    Actor.__children__ = {}
    Matrix.__children__ = {}
    yield
    Actor.__matrix__ = saved_matrix
    Actor.__children__ = saved_children
    Matrix.__children__ = saved_matrix_children
```

**Status**: Essential for isolation, but duplicated across 3+ conftest files.

---

## Database Strategy

| Context | Strategy | Isolation | Parallel Safe |
|---------|----------|-----------|---------------|
| Unit tests | Mock or `:memory:` SQLite | Per-test | Yes |
| Integration tests | Session-scoped temp file | Per-session | No |
| E2E tests | Subprocess temp DB | Per-session | Yes (separate processes) |

### Anti-Pattern: `:memory:` SQLite Connection Isolation

```python
# ANTI-PATTERN (from some tests):
storage = SQLiteStorage(':memory:')  # Connection 1
storage.create_table(Model)          # May open Connection 2 = DIFFERENT DB
```

Multiple statements opening separate connections get different in-memory databases.

### Anti-Pattern: Global Config Mutation

```python
config.SQLITE_DB_FILE = db_path  # Mutates global state
```

All integration tests rely on this. Not thread-safe. If one test crashes, config stays in bad state.

### Anti-Pattern: No Per-Test Cleanup

```python
def test_create_product(self, client, alice_token):
    resp = client.post("/products", json={"name": "Test", "price": 10})
    # Data stays in DB until session end

def test_list_products(self, client):
    resp = client.get("/products")
    # Sees "Test" product from previous test -- unexpected state
```

---

## Authentication Patterns

### Unit Tests (packages/)
- Tokens generated fresh per test via `create_token()`
- `configure_auth()` fixture sets/restores JWT settings
- Allows per-test variation

### Integration Tests (examples/)
- Session-scoped tokens for seed users (`alice_token`, `bob_token`)
- Consistent `auth_header(token)` helper across all examples

### E2E Tests
- Auth via Playwright `page.evaluate()` -- JavaScript fetch + localStorage

**Consistency**: Auth patterns are reasonable and consistent within each layer.

---

## Mocking Patterns

### Standard unittest.mock (packages/)
```python
from unittest.mock import MagicMock, AsyncMock, patch
```
Used consistently across all unit tests.

### Pydantic BaseModel Patching Workaround
```python
@contextmanager
def mock_method(instance, name, replacement):
    """Pydantic's __setattr__/__delattr__ prevent normal mock patching."""
    object.__setattr__(instance, name, replacement)
    try:
        yield replacement
    finally:
        object.__delattr__(instance, name)
```

**DUPLICATED** identically in:
- `packages/n3tx-actors/tests/conftest.py`
- `packages/n3tx-actors/api/tests/conftest.py`
- `packages/n3tx-agents/tests/conftest.py`
- Partial duplication in `apps/veille/tests/`

---

## Test Markers

| Location | `pytest.mark.unit` | `pytest.mark.integration` | `pytest.mark.e2e` |
|----------|-------------------|--------------------------|-------------------|
| n3tx-core | Yes (47 files) | N/A | N/A |
| n3tx-actors | Yes | Implicit | N/A |
| n3tx-agents | Yes | N/A | N/A |
| n3tx-trace | Partial | N/A | N/A |
| examples/ | N/A | Yes | **MISSING** |
| apps/veille | **NONE** | **NONE** | N/A |

**Impact**: `pytest -m e2e` won't work. `pytest -m integration` misses veille tests.

---

## Naming Conventions

### Unit Tests (packages/)
```python
class TestFullmethod:
    def test_class_access_binds_class(self): ...
    def test_instance_access_binds_instance(self): ...
```
Convention: `test_<descriptive_name>` with class grouping.

### Integration Tests (examples/)
```python
class TestCreateProduct:
    def test_create_product_authenticated_returns_201(self): ...
    def test_create_product_unauthenticated_returns_403(self): ...
```
Convention: `test_<action>_<scenario>_<expected_result>` (verbose).

### App Tests (veille/)
Convention: `test_<feature_description>` with long docstrings.

**Inconsistency**: Three different naming approaches across the codebase.

---

## Async Patterns

| Location | Pattern | Configuration |
|----------|---------|---------------|
| n3tx-agents | `@pytest.mark.asyncio` | Implicit (no pytest.ini) |
| n3tx-actors | Manual `asyncio.iscoroutinefunction()` checks | N/A |
| apps/veille | Manual | N/A |

**No explicit `asyncio_mode` in any pytest configuration file.**

---

## Import Patterns

### Unit Tests
```python
from n3tx_core.models.proto_model import ProtoModel  # Absolute
from .conftest import mock_method  # Relative to conftest
```

### Integration Tests
```python
from helpers import auth_header  # Local file
from models import Product, Comment  # Local app models
```

### E2E Tests
```python
sys.path.insert(0, os.path.join(_WORKSPACE, 'tests'))
from e2e_helpers import find_free_port, wait_for_server, start_server
```

**Fragile**: Hardcoded relative paths for directory traversal.

---

## Anti-Pattern Summary

| # | Anti-Pattern | Severity | Locations |
|---|-------------|----------|-----------|
| 1 | Global config mutation | HIGH | All integration conftest files |
| 2 | Session-scoped shared DB (no test isolation) | HIGH | All examples/*/tests/conftest.py |
| 3 | No per-test cleanup | MEDIUM-HIGH | All integration tests |
| 4 | Missing test markers | MEDIUM | E2E tests, apps/veille |
| 5 | `mock_method()` duplicated 3+ times | LOW | actors, api, agents conftest |
| 6 | No pytest async configuration | LOW | All packages |
| 7 | Fragile path manipulation in E2E | LOW | All e2e conftest files |
| 8 | Stale/unmaintained test files | LOW | test_error_drop_guard.py, test_shutdown_with_sse.py |

---

## Recommendations

### 1. Standardize Test Markers
Add to all test files:
- Unit: `pytestmark = pytest.mark.unit`
- Integration: `pytestmark = pytest.mark.integration`
- E2E: `pytestmark = pytest.mark.e2e`

### 2. Improve Test Isolation
Move integration fixtures from session-scoped to module-scoped, or implement transaction rollback:
```python
@pytest.fixture(scope="module")
def test_db():
    # Fresh DB per test module
```

### 3. Centralize Shared Utilities
Create `packages/n3tx-core/src/n3tx_core/tests/conftest_utils.py`:
```python
from contextlib import contextmanager

@contextmanager
def mock_method(instance, name, replacement):
    object.__setattr__(instance, name, replacement)
    try:
        yield replacement
    finally:
        object.__delattr__(instance, name)
```

### 4. Add Explicit pytest Configuration
Create `/workspace/pytest.ini`:
```ini
[pytest]
markers =
    unit: Unit tests (fast, isolated)
    integration: Integration tests (real DB)
    e2e: End-to-end tests (browser)
asyncio_mode = auto
```

### 5. Standardize Naming
- Unit: `test_<feature>` (what's tested)
- Integration: `test_<action>_<happy_or_sad>` (what happens)
- E2E: `test_user_<flow>` (user story)

### 6. Clean Up Stale Tests
Review and either update or remove: `test_error_drop_guard.py`, `test_streaming_shutdown.py`
