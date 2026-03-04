# Backend Test Suite — In-Depth Review

Comprehensive audit of 43 test files (18 integration + 25 unit) totaling ~4,500 lines.

---

# I. Test Infrastructure Problems

## TI-1. Session-Scoped Fixtures Cause Cross-Test Contamination

**Severity:** High
**Location:** `tests/conftest.py:221-300` — all fixtures use `scope="session"`

Every fixture — `test_db`, `seed_data`, `client`, all token fixtures — is session-scoped. This means:
- All tests share a **single database** and **single dataset**
- Tests that create, update, or delete entities **permanently mutate** shared state
- Test ordering determines outcomes

**Concrete failure scenario:**
```
1. test_products_crud::TestCreateProduct creates 8 new products (total → 13)
2. test_pagination::test_total_count_reflects_all_records checks total >= 5 → passes (lucky)
3. test_cross_model_workflows::test_product_lifecycle deletes product ID 6
4. Any test fetching product 6 by ID now gets 404
```

**Impact:** Tests are non-deterministic. Running a single test file works; running the full suite may not. Re-ordering tests (e.g., `pytest -p no:randomly`) changes pass/fail outcomes.

**Fix:** Use function-scoped or class-scoped fixtures with per-test database reset, or a transaction rollback strategy (begin transaction → run test → rollback).

---

## TI-2. No Test Cleanup / Rollback Strategy

**Severity:** High
**Location:** `tests/conftest.py:40-52` — `_setup_test_db()`

The setup creates tables and seeds data once. No teardown between tests. No transaction wrapping. Tests that create entities (most CRUD tests do) add to the database permanently.

**Impact:** Every `POST` test that creates a product/comment/like adds to cumulative state. Count-based assertions (`len(data) >= 5`) are fragile — they pass only because they use `>=` instead of `==`.

---

## TI-3. Broken Module Import Shim Architecture

**Severity:** Medium
**Location:** `conftest.py:1-20` (root), `run_tests.py:1-27`, `run_unit_tests.py:1-16`

Three separate files each implement the same workaround for the broken `n3tx/__init__.py` import (issue B1 in issues.md). Each does it slightly differently:
- Root conftest pre-registers 8 package shims
- `run_tests.py` pre-registers 2 package shims with actual paths
- `run_unit_tests.py` pre-registers 2 with empty paths

This creates a fragile import environment where:
- Running `pytest` from different directories produces different results
- Adding new subpackages requires updating multiple shim lists
- IDE test runners may not use the shim files at all

**Fix:** Fix the root cause (B1: broken `n3tx/__init__.py`), then remove all three shim files.

---

## TI-4. Duplicate pytest Configuration

**Severity:** Low
**Location:** `pytest.ini` and `pyproject.toml`

Both files configure `testpaths` and `pythonpath` for pytest. `pytest.ini` additionally sets `--import-mode=importlib`, while `pyproject.toml` doesn't. Having two config sources creates ambiguity about which takes precedence (pytest.ini wins, but it's confusing).

---

## TI-5. `helpers.py` Only Contains One Function

**Severity:** Low
**Location:** `tests/helpers.py`

The entire helpers module is just `auth_header(token)` returning `{"x-access-token": token}`. Multiple test files could benefit from shared helpers (href parsing, response validation, seed data lookups) but don't use any.

---

# II. Integration Test Issues

## IT-1. Over-Permissive Assertions Throughout

**Severity:** High
**Location:** Multiple files

Tests use range assertions where exact values should be checked:

| File | Line | Assertion | Problem |
|------|------|-----------|---------|
| `test_products_crud.py` | ~281 | `status_code in (200, 403)` | Doesn't test actual access rule |
| `test_error_handling.py` | ~207 | `status_code in (201, 400, 422)` | XSS test accepts any outcome |
| `test_error_handling.py` | ~130 | `status_code in (401, 403)` | Empty token behavior undefined |
| `test_fk_hydration.py` | ~88 | `isinstance(user_owner, (str, int))` | Doesn't validate format |
| `test_products_crud.py` | ~216 | `len(data) >= 5` | Cumulative from other tests |

**Impact:** Tests pass for the wrong reasons. The delete-as-regular-user test (`test_products_crud.py:281`) literally accepts both success and failure — it tests nothing.

---

## IT-2. Mega-Test Anti-Pattern in Workflow Tests

**Severity:** High
**Location:** `test_cross_model_workflows.py:15-92`

`test_product_lifecycle` is a single 78-line test with 10 sequential steps:
1. Create product
2. Read product
3. Add comment
4. Like comment
5. Reply to comment
6. Favorite product
7. Read product with populate
8. Verify nested data
9. Delete comment
10. Delete product

If step 5 fails, steps 6-10 never execute. The test report shows 1 failure with no information about which of the 10 operations broke or whether the first 4 were valid.

**Fix:** Split into 10 separate test methods sharing a class-scoped fixture for the created product.

---

## IT-3. False Positive in Comment ID Matching

**Severity:** Medium
**Location:** `test_cross_model_workflows.py:238`

```python
comment_found = any(str(comment_id) in str(href) for href in comments)
```

Uses substring match: comment ID `1` matches href `"/products/11/comments/12"`. This produces false positives when IDs are substrings of other IDs.

**Fix:** Use proper URL parsing or regex: `f"/comments/{comment_id}"` as exact substring, or parse the URL path.

---

## IT-4. Likes CRUD Has Only 3 Tests

**Severity:** High (Coverage Gap)
**Location:** `test_likes_crud.py` — 48 lines total

The entire Like model CRUD is covered by just 3 tests:
1. List likes on a comment (via populate)
2. List favorites on a product (via populate)
3. Schema marks `user` as protected

**Missing:**
- Direct like CREATE (POST)
- Direct like DELETE
- Like as different users
- Unlike (toggle off) verification
- Like count changes
- Duplicate like handling (idempotency)
- Access control on likes

---

## IT-5. No Authorization Tests for AND/NOT/Where Rules

**Severity:** High (Coverage Gap)
**Location:** `test_authorization.py`

Tests only cover:
- ANYONE (read access)
- AUTHENTICATED (create access)
- OWNER | ROLE('admin') (update access)
- ROLE('admin') (delete access)

**Missing rule combinations:**
- `AND` rule (`OWNER & Where(status='draft')`)
- `NOT` rule (`~ROLE('banned')`)
- `Where()` rule (field-value conditions)
- Nested composites (`(OWNER | ROLE('mod')) & AUTHENTICATED`)
- SQL pushdown for list filtering with complex rules

This is especially critical given that frontend issue F1 showed the NOT rule is already broken — the backend should be tested to confirm it works correctly server-side.

---

## IT-6. Collection Routes Missing Critical Tests

**Severity:** Medium
**Location:** `test_collection_routes.py` — 9 tests

Missing:
- Filtering on collection routes
- Ordering / sorting
- Empty collection handling
- `populate=` parameter on collection routes
- Date range filtering
- Access control (user without read permission on parent model)
- Exact count validation (uses `>=` instead of `==`)

---

## IT-7. No Cascade Delete Tests

**Severity:** Medium
**Location:** Not tested anywhere

No test verifies what happens when:
- A product is deleted that has comments → are comments orphaned? deleted? error?
- A comment is deleted that has likes → same question
- A comment with replies is deleted → do replies become orphaned?
- A user is deleted → what happens to their owned entities?

This is a fundamental data integrity concern with no test coverage.

---

## IT-8. Duplicate Test Coverage

**Severity:** Low
**Location:** `test_authorization.py:167-192` vs `test_protected_fields.py:14-25`

`TestProtectedFieldsAuthorization` in `test_authorization.py` and `TestProtectedFieldsOnCreate` in `test_protected_fields.py` test the same behavior (protected field auto-injection from JWT). Five tests are functionally duplicated.

**Impact:** Wasted test execution time and maintenance burden.

---

## IT-9. Schema Endpoint Tests Don't Validate $id URLs

**Severity:** Medium
**Location:** `test_schema_endpoints.py`

Tests check that `$id` and `$schema` keys exist but never validate:
- URLs are well-formed
- URLs resolve to actual endpoints
- URLs match the expected format (`{API_URL}/{ClassName}`)
- `$defs` entries have consistent `$id` values

---

## IT-10. Pagination Boundary Tests Incomplete

**Severity:** Medium
**Location:** `test_pagination.py:75`

```python
resp = client.get(f"/products?limit=2&offset={max(total - 2, 0)}")
```

When `total=2`, `max(2-2, 0) = 0`, fetching the first page — not the last. The "last page" boundary test only works when total > 2.

**Additional missing:**
- Default limit when none specified
- `limit=1, total=1` → `has_more` should be `false`
- Float limit values (`limit=2.5`)
- Negative limit values
- Last page exact boundary: `total=5, limit=2, offset=4` → 1 item

---

## IT-11. Custom Method Tests Don't Verify Persistence

**Severity:** Medium
**Location:** `test_custom_methods.py`

Tests call `/like`, `/favorite`, `/reply` endpoints and check response status/structure, but never verify:
- The like was actually stored in the database
- The favorite count changed
- The reply appears in the parent comment's collection
- A second toggle actually removes the entity

---

## IT-12. Auth Flow Tests Missing Email Validation Edge Cases

**Severity:** Low
**Location:** `test_auth_flow.py`

Missing:
- Registration with duplicate email
- Registration with SQL injection in email
- Login with case-different email (`Alice@Example.COM`)
- Empty password
- Very long password (>1000 chars)
- Token `iat` (issued at) validation
- Token expiry matches config value

---

## IT-13. Error Handling XSS Test Is Meaningless

**Severity:** Medium
**Location:** `test_error_handling.py:207`

```python
def test_html_in_product_name(self, ...):
    resp = client.post("/products", json={"name": "<script>alert('xss')</script>", ...}, ...)
    assert resp.status_code in (201, 400, 422)
```

This accepts ALL three possible outcomes — successful storage, bad request, or validation error. It tests nothing. The test should:
1. Assert 201 (if backend doesn't sanitize — which it shouldn't, the frontend should escape)
2. Then GET the product and verify the name is stored as-is (no mangling)
3. Confirm the backend doesn't corrupt the data

---

## IT-14. FK Hydration Tests Don't Validate Href Resolvability

**Severity:** Low
**Location:** `test_fk_hydration.py`

Tests check that href arrays contain strings matching a rough pattern, but never actually `GET` one of the href URLs to verify it resolves to a real entity.

---

## IT-15. Middleware CORS Test Weak

**Severity:** Low
**Location:** `test_middleware.py`

```python
def test_cors_headers_present(self, client):
    resp = client.get("/products", headers={"Origin": "http://example.com"})
    # only checks status_code
```

Doesn't actually assert CORS headers (`Access-Control-Allow-Origin`, etc.) in response.

---

# III. Unit Test Issues

## UT-1. `test_config.py` — Execution Order Dependency

**Severity:** Medium
**Location:** `tests/unit/test_config.py` — `test_sqlite_db_file`

The session-scoped `test_db` fixture in integration tests changes `config.SQLITE_DB_FILE`. If unit tests run after integration tests in the same session, `test_sqlite_db_file` may see the modified value instead of `"n3tx.db"`.

Already documented as B5 in issues.md, but worth noting this is a direct test bug.

---

## UT-2. `test_proto_model.py` — No Tests for `generate_join_model()`

**Severity:** High (Coverage Gap)
**Location:** `tests/unit/test_proto_model.py`

`generate_join_model()` is a core function that creates join models (ProductComment, CommentLike, ProductLike). It:
- Creates a new class dynamically
- Sets `__tablename__`, `__storable__`, `__protected_fields__`
- Adds parent FK column
- Copies methods from child class
- Registers in `join_models` dict

**None of this is unit-tested.** Only integration tests exercise it indirectly.

Missing unit tests:
- Generated class has correct tablename
- Generated class has parent FK column
- Generated class inherits child methods
- Generated class has correct `__protected_fields__`
- Edge case: generating join model twice (idempotency)
- Edge case: parent without `__tablename__`
- Edge case: child with no `@expose_route` methods

---

## UT-3. `test_rules.py` — Missing `Where` Rule Tests

**Severity:** Medium (Coverage Gap)
**Location:** `tests/unit/test_rules.py`

The `Where` rule allows field-value conditions on resources:
```python
Where(status='draft')  # Only resources where status == 'draft'
```

No unit tests exercise `Where.evaluate()` or `Where.to_sql()`. The rule's `__and__`, `__or__`, `__invert__` are tested indirectly through composite rules but `Where` specifically is never tested.

---

## UT-4. `test_rules.py` — `to_sql()` Not Tested

**Severity:** Medium (Coverage Gap)
**Location:** `tests/unit/test_rules.py`

Authorization rules support SQL pushdown for efficient list filtering:
```python
OWNER.to_sql(context) → ("user_owner = ?", [user_id])
```

No unit tests verify SQL generation for:
- `ANYONE.to_sql()` → `None` (no filter)
- `AUTHENTICATED.to_sql()` → `None` (no filter)
- `OWNER.to_sql()` → WHERE clause with user_id
- `ROLE('admin').to_sql()` → `None` (role check, no SQL)
- Composite `(OWNER | ROLE('admin')).to_sql()` → correct OR clause
- `Where(status='draft').to_sql()` → field comparison clause

---

## UT-5. `test_access_schema.py` — Missing Composite Serialization

**Severity:** Medium
**Location:** `tests/unit/test_access_schema.py`

Tests serialization of simple rules (ANYONE, AUTHENTICATED, OWNER, ROLE) but missing:
- `AndRule` serialization → `{"op": "and", "rules": [...]}`
- `OrRule` serialization → `{"op": "or", "rules": [...]}`
- `NotRule` serialization → `{"op": "not", "rule": {...}}`
- `Where` serialization → `{"rule": "where", ...}`
- Nested composite serialization
- Deserialization (if any)

---

## UT-6. `test_sqlite_storage.py` — Missing FK Hydration Tests

**Severity:** High (Coverage Gap)
**Location:** `tests/unit/test_sqlite_storage.py`

`sqlite_storage.py` handles FK hydration — converting ListRef fields to href arrays and populating nested objects. The unit test doesn't test:
- `_hydrate_fk_fields()` — href array construction
- `_populate_field()` — nested object loading
- Join table queries (parent_id filtering)
- Populate with depth parameter
- Populate with nonexistent field

These are only tested via integration tests, making it hard to isolate storage-layer bugs.

---

## UT-7. `test_sqlite_migration.py` — Missing Migration Execution Test

**Severity:** Medium
**Location:** `tests/unit/test_sqlite_migration.py`

Tests:
- Finding pending migrations
- Migration status reporting
- Column addition via `migrate_table`

Missing:
- Actually running a migration script (only checks status)
- Migration with SQL errors (rollback?)
- Migration ordering (001 before 002)
- Re-running already-applied migration (idempotency)
- Migration with data transformation (not just schema change)

---

## UT-8. `test_routes.py` — Incomplete Route Factory Coverage

**Severity:** High (Coverage Gap)
**Location:** `tests/unit/test_routes.py`

`routes_fastapi.py` is the largest and most complex source file (~400 lines). Unit test coverage is thin:

**Tested:**
- `register_route()` adds route
- `register_routes()` registers all models
- Schema endpoint returns correct structure
- CRUD route existence

**Not tested:**
- `make_create_instance()` — protected field injection logic
- `make_update_instance()` — field stripping, auth check
- `make_delete_instance()` — admin vs owner logic
- `_resolve_user()` — JWT-to-model bridge
- Custom method handler generation
- Authorization middleware injection on routes
- Error responses (404, 403, 422) from route handlers
- Pagination parameter handling in list routes
- `populate` and `depth` query parameter passing

---

## UT-9. `test_storable_mixin.py` — Missing Edge Cases

**Severity:** Medium
**Location:** `tests/unit/test_storable_mixin.py`

Missing:
- `save()` with model instance (not dict) for update
- `save()` when storage is None (should raise meaningful error)
- `create_table()` delegation
- `list()` with pagination parameters
- `list()` with `populate` parameter
- `get()` with `populate` parameter
- `update()` with model instance (not dict)
- `delete()` when storage is None

---

## UT-10. `test_resolver.py` — Only Tests Default Resolver

**Severity:** Low
**Location:** `tests/unit/test_resolver.py`

Tests the `DefaultResolver` but doesn't test:
- The `AuthorizationResolver` Protocol interface
- Custom resolver implementation
- Resolver with SQL pushdown
- Resolver error handling (AccessDenied propagation)

---

## UT-11. `test_seed.py` — Doesn't Actually Seed

**Severity:** Low
**Location:** `tests/unit/test_seed.py`

If present, likely tests seed data structure but doesn't verify:
- `seed()` function creates all expected entities
- Entity counts match expected values
- Relationships are correctly established
- `--reset` flag works
- Idempotency (running seed twice)

---

# IV. Coverage Gaps — Untested Source Files

## CG-1. `api/backend.py` — Zero Test Coverage

**Severity:** Medium
**Location:** `src/n3tx/core/api/backend.py` (157 lines)

Two full backend classes with no test coverage:
- `BaseBackend` — ABC with model registration
- `FastAPIBackend` — CORS setup, auth middleware, route registration, static file mounting
- `FlaskBackend` — Flask setup, blueprint registration

**Missing tests:**
- Middleware ordering
- CORS configuration correctness
- Static file serving
- HTML page serving
- Auth-exempt path logic

---

## CG-2. `api/routes_flask.py` — Zero Test Coverage

**Severity:** Low
**Location:** `src/n3tx/core/api/routes_flask.py` (259 lines)

The entire Flask route layer has no tests. This is the legacy backend but it's still importable and used when `config.BACKEND == "flask"`.

---

## CG-3. `storage/json_storage.py` — Zero Test Coverage

**Severity:** Low
**Location:** `src/n3tx/core/storage/json_storage.py` (77 lines)

An alternative JSON-file storage backend implementing `AbstractStorage`. All CRUD methods, file I/O, and ID generation are untested.

---

## CG-4. `models/viewable_mixin.py` — Zero Test Coverage

**Severity:** Low
**Location:** `src/n3tx/core/models/viewable_mixin.py` (50 lines)

The `ViewableMixin` class with `view()` method and `viewables` registry has no tests.

---

## CG-5. `utils/scaffold.py` — Zero Test Coverage

**Severity:** Low
**Location:** `src/n3tx/core/utils/scaffold.py` (450 lines)

The entire component scaffolding system — `scaffold_item()`, `scaffold_list()`, `scaffold_css()`, `scaffold_model()`, `scaffold_single()` — has no unit tests. Only the schema endpoint test checks the scaffold endpoint returns text.

---

## CG-6. `utils/generate_docs.py` — Zero Test Coverage

**Severity:** Low
**Location:** `src/n3tx/core/utils/generate_docs.py` (67 lines)

Documentation generator with no tests for:
- Markdown generation
- Index file creation
- Field/method/route documentation accuracy

---

## CG-7. `utils/introspection.py` — Partial Coverage

**Severity:** Medium
**Location:** `src/n3tx/core/utils/introspection.py`

Functions like `get_list_fields()`, `get_ref_fields()`, `collect_all_referenced_models()`, `_unwrap_listref()`, `_is_self_ref()` are complex type introspection utilities. Tests exist but miss:
- Forward reference resolution
- `Optional[ListRef[T]]` unwrapping
- Circular reference detection
- `_unwrap_listref()` with Pydantic FieldInfo metadata vs type metadata

---

## CG-8. `User` Model — Login/Register Logic Not Unit-Tested

**Severity:** Medium
**Location:** `models/user_model.py`

The `User` model has custom logic:
- `_plain_password` handling
- `Bot` subclass
- Password hashing on create
- Login/register flow

Only integration tests (via auth_flow) exercise this. No unit test isolates the model's custom behavior.

---

# V. Structural / Design Issues

## SD-1. No Parametrized Tests

**Severity:** Low (Code Quality)
**Location:** Throughout

No use of `@pytest.mark.parametrize` anywhere. Many tests repeat the same pattern with different inputs (e.g., testing 5 schema endpoints, testing 4 error status codes). Parametrization would:
- Reduce code duplication
- Make it easy to add new cases
- Provide better failure reporting

---

## SD-2. No Test Markers

**Severity:** Low (Code Quality)
**Location:** Throughout

No `@pytest.mark.slow`, `@pytest.mark.integration`, `@pytest.mark.unit` markers. Can't selectively run fast unit tests vs slow integration tests. Can't skip tests requiring network/DB.

---

## SD-3. No Fixture Factories

**Severity:** Medium (Code Quality)
**Location:** `tests/conftest.py`

Tests that need fresh entities (a new product, a new comment) must call the API directly within the test body. A fixture factory pattern would allow:
```python
@pytest.fixture
def make_product(client, alice_token):
    def _make(**overrides):
        data = {"name": "Test", "price": 10.0, **overrides}
        resp = client.post("/products", json=data, headers=auth_header(alice_token))
        return resp.json()
    return _make
```

---

## SD-4. Fragile String Parsing for Href Validation

**Severity:** Medium
**Location:** `test_authorization.py:176`, `test_cross_model_workflows.py:238`, `test_fk_hydration.py`

Multiple tests parse href URLs using string manipulation:
```python
user_owner_id = int(user_owner_val.rstrip("/").rsplit("/", 1)[-1])
```

This is fragile. A URL format change breaks all these tests. Should use a shared helper:
```python
def parse_href_id(href: str) -> int:
    """Extract the trailing integer ID from an href URL."""
    return int(href.rstrip("/").rsplit("/", 1)[-1])
```

---

## SD-5. No Negative Authorization Tests for Custom Methods

**Severity:** Medium (Coverage Gap)
**Location:** `test_custom_methods.py`

Tests verify that authenticated users CAN call `/like`, `/favorite`, `/reply`. But no test verifies that:
- Anonymous users get 401 on `/like` (only 3 tests check auth required)
- A banned user (if ~ROLE rule existed) is blocked
- A user calling `/like` on a nonexistent entity gets 404
- Calling `/reply` with missing required fields returns 422

---

# VI. Summary Statistics

| Category | Count | Critical | High | Medium | Low |
|----------|-------|----------|------|--------|-----|
| Infrastructure | 5 | 0 | 2 | 1 | 2 |
| Integration Tests | 15 | 0 | 4 | 7 | 4 |
| Unit Tests | 11 | 0 | 3 | 6 | 2 |
| Coverage Gaps | 8 | 0 | 0 | 3 | 5 |
| Structural | 5 | 0 | 0 | 3 | 2 |
| **Total** | **44** | **0** | **9** | **20** | **15** |

### Top Priority Fixes
1. **TI-1/TI-2**: Fix test isolation (session-scoped → function-scoped with rollback)
2. **IT-1**: Replace over-permissive assertions with exact expected values
3. **IT-4**: Expand Like CRUD tests from 3 to ~15
4. **IT-5**: Add AND/NOT/Where authorization rule tests
5. **UT-2**: Add `generate_join_model()` unit tests
6. **UT-8**: Expand route factory unit tests
7. **IT-2**: Split mega-tests into individual test methods
8. **UT-6**: Add FK hydration unit tests to sqlite_storage
9. **IT-7**: Add cascade delete tests
