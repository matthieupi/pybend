# P0+P1: Security Fixes + Exhaustive Test Coverage

## P0: Security Fixes (6 items)

### Fix 1: Debug Default OFF
**Files**: `example_grants/config.py`, `src/pybend/core/config.py`
- `DEBUG = os.getenv("PYBEND_DEBUG", "false").lower() in ("true", "1")`
- Both config files default to `False`
- Still all the current example apps should have DEBUG = True

### Fix 2: CORS Wildcard + Credentials
**File**: `src/pybend/core/api/backend.py`
- When `origins=["*"]`, set `allow_credentials=False`
- Only allow credentials with explicit origin lists

### Fix 3: API Docs Disabled in Production
**File**: `src/pybend/core/api/backend.py`
- `docs_url = "/docs" if DEBUG else None`
- `redoc_url = "/redoc" if DEBUG else None`

### Fix 4: Status Literal Type
**File**: `example_grants/models/grant.py`
- `status: Literal['discovered', 'reviewed', 'applied', 'expired']`
- Pydantic rejects invalid status values at validation time
- Make sure the frontend has the proper widget for rendering Literals 
  (Should be a dropdown, in edit mode, stylized pill for display)
---

## P1: Exhaustive Test Coverage (~230 tests, 13 new files)

### Core Framework Tests

#### `src/pybend/core/tests/unit/test_auth_interceptor.py` (~45 tests, ~350 lines)
Tier 1 auth gate — currently ZERO test coverage.
- Schema requests pass through without auth
- Unauthenticated requests rejected (401)
- Valid token accepted, user injected into meta
- Expired token rejected
- Malformed token rejected
- List requests get `sql_filter` injected for OWNER rules
- Create requests checked against model `__access__`
- Read/Update/Delete identity-gated (user_id in meta)
- Multiple user roles tested (user, admin, none)
- Edge cases: missing model_cls in meta, empty token, bearer prefix

#### `src/pybend/core/tests/unit/test_actor_model_authorize.py` (~20 tests, ~180 lines)
Tier 2 ABAC with resource instance.
- OWNER rule: owner can update, non-owner denied
- ROLE rule: admin can delete, user cannot
- Compound rules: OWNER | ROLE('admin')
- ANYONE rule: read allowed without auth
- AUTHENTICATED rule: requires valid user
- No `__access__` defaults to AUTHENTICATED
- Method-level access via `@expose_route(access=...)`

#### `src/pybend/core/tests/unit/test_auth_edge_cases.py` (~15 tests, ~120 lines)
JWT edge cases.
- Token with wrong algorithm rejected
- Token with missing claims rejected
- Token decode with wrong secret fails
- Password hash roundtrip (hash then verify)
- Empty password rejected
- Unicode password handling
- Token expiration boundary (just expired vs just valid)

#### `src/pybend/core/tests/unit/test_base_user.py` (~12 tests, ~100 lines)
Login/register logic.
- `login()` with correct credentials returns token
- `login()` with wrong password returns error
- `login()` with non-existent email returns error
- `register_user()` creates user with hashed password
- `register_user()` with duplicate email returns error
- `register_user()` with missing required fields returns 422
- Password is never returned in responses

### Example Grants Integration Tests

#### `example_grants/tests/test_auth_flow.py` (~18 tests)
- Register new user → login → use token → access protected endpoints
- Register with invalid email format → 422
- Login with wrong password → 401
- Access protected endpoint without token → 401
- Access protected endpoint with expired token → 401
- Token refresh flow

#### `example_grants/tests/test_authorization.py` (~25 tests)
Per-model ABAC with multiple users.
- Alice (owner) can update her grant, Bob cannot
- Admin can update any grant
- Anyone can read grants (no auth required for list)
- Only authenticated users can create grants
- Only admin can delete grants
- Source CRUD with OWNER checks
- Cross-user isolation (Alice's grants vs Bob's grants)
- Agent CRUD requires authenticated user

#### `example_grants/tests/test_error_handling.py` (~20 tests)
HTTP error responses.
- 401 for unauthenticated access to protected endpoints
- 403 for unauthorized actions (wrong role)
- 404 for non-existent resources
- 422 for validation errors (bad input types, missing required fields)
- 400 for malformed requests
- Method errors return proper HTTP status codes
- Error response format: `{"detail": "..."}`

#### `example_grants/tests/test_pagination.py` (~10 tests)
- Default pagination (limit=20, offset=0)
- Custom limit and offset
- `has_more` flag accuracy
- `total` count accuracy
- Empty result set
- Offset beyond total returns empty data
- Limit=0 edge case
- Large offset values

#### `example_grants/tests/test_boot.py` (~8 tests)
Boot verification.
- App starts without errors
- All models registered
- All routes accessible
- Schema endpoints return valid JSON Schema
- Static files served
- Health check (if applicable)

#### `example_grants/tests/test_ssrf.py` (~12 tests)
SSRF validation.
- Public URL allowed
- Private IP (10.x, 172.16-31.x, 192.168.x) blocked
- Loopback (127.0.0.1, ::1) blocked
- Link-local (169.254.x) blocked
- DNS rebinding (hostname resolving to private IP) blocked
- URL with port to internal service blocked
- Redirect to private IP handled
- Valid external URLs pass through

#### `example_grants/tests/test_security_config.py` (~8 tests)
P0 fix verification.
- Debug mode off by default
- CORS credentials disabled with wildcard origin
- API docs not exposed in production mode
- JWT secret validation at startup
- Status field rejects invalid values

---

## Execution Order

```
Phase 1: P0 security fixes (parallel, ~1 day)
  Fix 1-6 are independent, can be implemented in any order

Phase 2: Core framework tests (after P0, ~1 day)
  test_auth_interceptor.py
  test_actor_model_authorize.py
  test_auth_edge_cases.py
  test_base_user.py

Phase 3: Integration tests (after P0, ~1.5 days)
  test_auth_flow.py
  test_authorization.py
  test_error_handling.py
  test_pagination.py
  test_boot.py
  test_ssrf.py
  test_security_config.py

Phase 4: Verify all tests pass, fix any regressions
```

## Files Summary

**New files (14):**
- `example_grants/utils/url_validator.py`
- `src/pybend/core/tests/unit/test_auth_interceptor.py`
- `src/pybend/core/tests/unit/test_actor_model_authorize.py`
- `src/pybend/core/tests/unit/test_auth_edge_cases.py`
- `src/pybend/core/tests/unit/test_base_user.py`
- `example_grants/tests/test_auth_flow.py`
- `example_grants/tests/test_authorization.py`
- `example_grants/tests/test_error_handling.py`
- `example_grants/tests/test_pagination.py`
- `example_grants/tests/test_boot.py`
- `example_grants/tests/test_ssrf.py`
- `example_grants/tests/test_security_config.py`
- `example_grants/utils/__init__.py`

**Modified files (5):**
- `example_grants/config.py`
- `example_grants/models/grant.py`
- `src/pybend/core/config.py`
- `src/pybend/core/api/backend.py`
- `src/pybend/core/authorize/auth.py`
