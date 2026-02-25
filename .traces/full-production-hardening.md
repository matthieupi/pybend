# PyBend Production Hardening Roadmap

> Post-v0.7.0 roadmap for hardening PyBend for production deployments.
> Generated from security audit findings and architectural review of the actual codebase.

---

## Overview

### Current State Assessment

PyBend v0.7.0 is a schema-driven full-stack framework with a working backend (FastAPI + SQLite), authorization system (JWT + ABAC), and vanilla JS frontend (Web Components). The framework is functional for development and demo use but has several gaps that must be addressed before production deployment.

The security audit (`/workspace/.traces/issues.md`) identified 10 backend issues (B1-B10) and 13 frontend issues (F1-F13). This roadmap expands on those findings and adds operational, performance, and compliance concerns.

### Risk Summary

| Priority | Count | Category Examples |
|----------|-------|-------------------|
| Critical | 5 | JWT secrets, SQL injection vectors, CORS, error disclosure, rate limiting |
| High | 20 | Auth gaps, input validation, API security, storage, logging |
| Medium | 25 | Operational, performance, testing, frontend security, compliance |

### Recommended Implementation Order

1. Critical items first (items 1-5) -- blockers for any production deployment
2. High-priority authentication & authorization (items 6-10) -- user-facing security
3. High-priority input validation & API security (items 11-20) -- attack surface reduction
4. High-priority storage & logging (items 21-30) -- data integrity and observability
5. Medium-priority items by opportunity -- during regular feature development

---

## Critical Priority (Must-Fix Before Production)

### 1. JWT Secret Management

**Problem:** Two separate hardcoded default secrets exist in the codebase, and the application starts without complaint when neither is overridden.

**File:** `/workspace/src/pybend/core/config.py` (line 14)
```python
JWT_SECRET = os.getenv("JWT_SECRET", "pybend-dev-secret-change-in-production")
```

**File:** `/workspace/src/pybend/core/authorize/auth.py` (line 9)
```python
_jwt_secret: str = os.getenv("JWT_SECRET", "authorize-dev-secret-change-in-production")
```

Two different default values create confusion about which secret is in use. The `authorize` module has its own default (`"authorize-dev-secret-change-in-production"`) which is overridden by `main.py` calling `authorize.configure(jwt_secret=config.JWT_SECRET)` -- so the effective default at runtime is `"pybend-dev-secret-change-in-production"`. But if someone imports `authorize` directly without calling `configure()`, they get the other secret.

**Impact:** Any attacker who reads the public source code can forge valid JWT tokens. Total authentication bypass.

**Cross-reference:** Issue B8 in `/workspace/.traces/issues.md`.

**Implementation approach:**
```python
# config.py — refuse to start with default secret in production
import os
import secrets

_ENV = os.getenv("PYBEND_ENV", "development")
_default_secret = os.getenv("JWT_SECRET")

if _ENV != "development" and not _default_secret:
    raise RuntimeError(
        "JWT_SECRET environment variable must be set in non-development environments. "
        "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
    )

JWT_SECRET = _default_secret or f"dev-{secrets.token_urlsafe(32)}"
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))
```

```python
# authorize/auth.py — remove the hardcoded default, require configure() in production
_jwt_secret: str | None = None

def configure(*, jwt_secret: str = None, jwt_expiry_hours: int = None) -> None:
    global _jwt_secret, _jwt_expiry_hours
    if jwt_secret is not None:
        _jwt_secret = jwt_secret
    if jwt_expiry_hours is not None:
        _jwt_expiry_hours = jwt_expiry_hours

def _get_secret() -> str:
    if _jwt_secret is None:
        raise RuntimeError("authorize.configure(jwt_secret=...) must be called before using JWT functions")
    return _jwt_secret
```

**Effort estimate:** 1-2 hours (code change + test updates + documentation)

---

### 2. SQL Injection via Table/Column Names

**Problem:** Table names and column names derived from model class attributes (`__tablename__`, field names) are interpolated directly into SQL strings via f-strings throughout the storage layer. While the *values* use parameterized queries (safe), the *identifiers* are not escaped.

**File:** `/workspace/src/pybend/core/storage/sqlite_storage.py`

Multiple locations:
- Line 58: `f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"`
- Line 78: `f"SELECT * FROM {table_name}"`
- Line 145: `f"SELECT id FROM {child_table} WHERE {fk_col} = ?"`
- Line 182: `f"SELECT * FROM {table_name} WHERE id = ?"`
- Line 311: `f"SELECT * FROM {child_table} WHERE {fk_col} IN ({placeholders})"`
- Line 437: `f"SELECT * FROM {target_table} WHERE id IN ({placeholders})"`
- Line 492: `f"{field} = ?"` in SET clause construction
- Line 496: `f"UPDATE {table_name} SET {set_clause} WHERE id = ?"`
- Line 517: `f"DELETE FROM {table_name} WHERE id = ?"`

**File:** `/workspace/src/pybend/core/storage/sqlite_migration.py`
- Line 166-170: `CREATE TABLE IF NOT EXISTS {table_name}`
- Line 209: `ALTER TABLE {table_name} ADD COLUMN {field_name}`

**Mitigating factor:** Table names and column names come from Python class attributes (`__tablename__`, `model_fields`), not from user input. An attacker would need to control a model class definition to exploit this. However:
1. If PyBend ever supports user-defined models (the TODOs mention "DB-based compiled models"), this becomes a direct injection vector.
2. The `sql_filter` tuple from `_resolver.sql_filter_for()` inserts WHERE clauses -- if the resolver has a bug, it could inject arbitrary SQL.

**Impact:** Currently low risk (trusted model definitions). Becomes critical if/when user-defined models are supported.

**Implementation approach:**
```python
# sqlite_storage.py — add identifier quoting helper
import re

def _quote_identifier(name: str) -> str:
    """Quote a SQLite identifier, preventing injection via table/column names."""
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")
    return f'"{name}"'

# Then use throughout:
insert_sql = f"INSERT INTO {_quote_identifier(table_name)} ({', '.join(_quote_identifier(f) for f in fields)}) VALUES ({placeholders})"
```

Additionally, validate `__tablename__` values at model registration time in `register_model()`:
```python
# registrar.py
def register_model(model_class, storage=None):
    tablename = getattr(model_class, '__tablename__', '')
    if not re.match(r'^[a-z][a-z0-9_]*$', tablename):
        raise ValueError(f"Invalid __tablename__ '{tablename}' on {model_class.__name__}")
    # ...existing logic...
```

**Effort estimate:** 2-3 hours (create helper, apply across sqlite_storage.py, sqlite_migration.py, add validation in registrar)

---

### 3. CORS Wildcard in Production

**Problem:** The FastAPI backend is configured with fully permissive CORS.

**File:** `/workspace/src/pybend/core/api/backend.py` (lines 59-65)
```python
self.app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Per the CORS specification, `allow_origins=["*"]` with `allow_credentials=True` is technically invalid. Starlette works around this by reflecting the request's `Origin` header back as `Access-Control-Allow-Origin`, which effectively means *any origin* can make credentialed requests.

**Impact:** Any malicious website can make authenticated API calls on behalf of a logged-in PyBend user if they have a valid JWT token in localStorage (the frontend uses `x-access-token` header). This enables CSRF-like attacks.

**Cross-reference:** Issue B7 in `/workspace/.traces/issues.md`.

**Implementation approach:**
```python
# backend.py — make CORS configurable, default to restrictive in production
import os

class FastAPIBackend(BaseBackend):
    def __init__(self, **data):
        super().__init__(**data)
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware

        self.app = FastAPI(...)

        # CORS: restrictive by default, configurable via env
        cors_origins = os.getenv("CORS_ORIGINS", "").split(",")
        cors_origins = [o.strip() for o in cors_origins if o.strip()]

        if not cors_origins:
            # Development fallback
            env = os.getenv("PYBEND_ENV", "development")
            if env == "development":
                cors_origins = ["http://localhost:5000", "http://127.0.0.1:5000"]
            else:
                raise RuntimeError(
                    "CORS_ORIGINS must be set in production. "
                    "Example: CORS_ORIGINS=https://myapp.com,https://admin.myapp.com"
                )

        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["Content-Type", "x-access-token"],
        )
```

**Effort estimate:** 1 hour

---

### 4. Error Information Disclosure

**Problem:** The `get_traceback_info()` utility returns full Python traceback frames -- including file paths, line numbers, function names, and source code -- in HTTP 400 error responses to the client.

**File:** `/workspace/src/pybend/core/utils/erroring.py` (lines 4-23)
```python
def get_traceback_info(e: Exception):
    tb = traceback.extract_tb(e.__traceback__)
    last_frames = tb[-3:] if tb else []
    trace_info = [
        {
            "file": frame.filename,
            "line": frame.lineno,
            "function": frame.name,
            "code": frame.line
        }
        for frame in last_frames
    ]
    trace_info[-1]['error'] = str(e)
    return trace_info
```

**Called from:** `/workspace/src/pybend/core/api/routes_fastapi.py` (line 81)
```python
raise HTTPException(status_code=400, detail=get_traceback_info(e))
```

Additionally, several route handlers include verbose `print()` statements (lines 62, 184, 219, 223, 238) that log full request data to stdout.

**Impact:** Exposes internal server paths, code structure, and potentially sensitive variable values to any API caller. This is a classic information disclosure vulnerability that aids further attacks.

**Implementation approach:**
```python
# erroring.py — environment-aware error formatting
import os
import traceback
import logging

logger = logging.getLogger("pybend")

def get_traceback_info(e: Exception):
    """Format exception for API response. Full trace in dev, safe message in production."""
    env = os.getenv("PYBEND_ENV", "development")

    # Always log the full trace server-side
    logger.error("Request error: %s", e, exc_info=True)

    if env == "development":
        tb = traceback.extract_tb(e.__traceback__)
        last_frames = tb[-3:] if tb else []
        trace_info = [
            {"file": frame.filename, "line": frame.lineno,
             "function": frame.name, "code": frame.line}
            for frame in last_frames
        ]
        if trace_info:
            trace_info[-1]['error'] = str(e)
        return trace_info

    # Production: safe generic message
    return {"error": "Request processing failed", "type": type(e).__name__}
```

**Effort estimate:** 1-2 hours (modify erroring.py, replace print statements with logging, add PYBEND_ENV support)

---

### 5. No Rate Limiting

**Problem:** No rate limiting or throttling exists on any endpoint. The login endpoint (`/users/login`) is especially dangerous because it:
1. Accepts unlimited password attempts
2. Performs a `User.list()` (full table scan) on every login attempt (line 83 of `user_model.py`)
3. Uses bcrypt comparison which is intentionally slow -- an attacker can DOS the server with concurrent login requests

**File:** `/workspace/src/pybend/core/models/user_model.py` (lines 57-90)
```python
@staticmethod
@expose_route('/login', methods=['POST'], access=ANYONE)
def login(email: str, password: str) -> dict:
    users = User.list()  # Full table scan every login
    user = next((u for u in users if u.email == email), None)
    if not user or not user.password_hash:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    ...
```

The registration endpoint (`/users/register`, line 93) also does `User.list()` on every call.

**Impact:** Brute force password attacks, credential stuffing, denial of service via resource exhaustion.

**Implementation approach:**
```python
# middleware/rate_limit.py — simple in-memory rate limiter
import time
from collections import defaultdict
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Token-bucket rate limiter keyed by client IP."""

    def __init__(self, app, default_rpm: int = 60, auth_rpm: int = 10):
        super().__init__(app)
        self.default_rpm = default_rpm
        self.auth_rpm = auth_rpm
        self._buckets = defaultdict(lambda: {"tokens": 0, "last": 0})

    # Auth endpoints get stricter limits
    AUTH_PATHS = {"/users/login", "/users/register"}

    async def dispatch(self, request, call_next):
        client_ip = request.client.host
        path = request.url.path
        rpm = self.auth_rpm if path in self.AUTH_PATHS else self.default_rpm

        bucket = self._buckets[f"{client_ip}:{path}"]
        now = time.time()
        elapsed = now - bucket["last"]
        bucket["tokens"] = min(rpm, bucket["tokens"] + elapsed * (rpm / 60))
        bucket["last"] = now

        if bucket["tokens"] < 1:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests"},
                headers={"Retry-After": str(int(60 / rpm))},
            )
        bucket["tokens"] -= 1
        return await call_next(request)
```

For production, replace the in-memory store with Redis for multi-worker support.

Additionally, fix the `User.login()` and `User.register()` methods to use indexed email lookups instead of `User.list()`:
```python
# Future: add sql_filter support to login
# user = User.get_by_email(email)  # Uses WHERE email = ? instead of full scan
```

**Effort estimate:** 3-4 hours (middleware + tests + login query optimization)

---

## High Priority

### Authentication & Authorization

#### 6. Token Refresh Mechanism

**Problem:** JWTs have a fixed 24-hour expiry (`JWT_EXPIRY_HOURS` default in `/workspace/src/pybend/core/config.py` line 15). There is no refresh token mechanism. When a token expires, the user must re-authenticate with credentials.

**File:** `/workspace/src/pybend/core/authorize/auth.py` (line 30-38)
```python
def create_token(user_id: int, email: str, role: str = "user") -> str:
    payload = {
        "user_id": user_id, "email": email, "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=_jwt_expiry_hours),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, _jwt_secret, algorithm="HS256")
```

**Impact:** Poor UX (forced re-login every 24h). Encourages long-lived tokens. No way to rotate tokens without re-authentication.

**Implementation approach:**
- Add a `/users/refresh` endpoint that accepts a valid (non-expired) token and returns a new token with refreshed expiry
- Optionally introduce a separate refresh token with longer expiry stored server-side
- Add `"jti"` (JWT ID) claim for token tracking

**Effort estimate:** 3-4 hours

---

#### 7. Password Complexity Requirements

**Problem:** No password validation exists. The seed data uses passwords like `"alice123"`, `"bob123"`. The registration endpoint (`/workspace/src/pybend/core/models/user_model.py` line 94) accepts any string as a password.

**Impact:** Users can set single-character or empty passwords, making brute force trivial.

**Implementation approach:**
- Add a `validate_password(password: str)` function in `authorize/auth.py` enforcing minimum length (8+), complexity rules
- Call it in `User.register()` before hashing
- Return clear error messages about requirements

**Effort estimate:** 1 hour

---

#### 8. Account Lockout After Failed Attempts

**Problem:** No lockout mechanism exists. An attacker can attempt unlimited passwords against any account. The only protection would be rate limiting (item 5), but even with rate limits, slow brute force over days would succeed against weak passwords.

**Impact:** Combined with no password complexity (item 7), accounts with weak passwords are trivially compromised.

**Implementation approach:**
- Add a `failed_login_attempts` and `locked_until` column to the users table
- After N failures (configurable, default 5), lock the account for a configurable duration
- Return generic "Invalid credentials" regardless of lock state (avoid enumeration)
- Admin-only unlock mechanism

**Effort estimate:** 3-4 hours

---

#### 9. Session Invalidation / Token Revocation

**Problem:** JWTs are stateless -- once issued, a token is valid until expiry. There is no way to invalidate a specific token (e.g., on password change, account compromise, or explicit logout).

**File:** `/workspace/src/pybend/core/authorize/auth.py` -- `decode_token()` (line 41-42) performs no revocation check.

**Impact:** Compromised tokens remain valid for up to 24 hours. No server-side logout capability.

**Implementation approach:**
- Maintain a token denylist (in-memory set or database table) of revoked `jti` values
- Check the denylist in `decode_token()` or in the JWT middleware
- Add a `/users/logout` endpoint that adds the current token's `jti` to the denylist
- Automatically revoke all tokens on password change

**Effort estimate:** 4-5 hours

---

#### 10. CSRF Protection for State-Changing Operations

**Problem:** The frontend sends JWT tokens via the `x-access-token` header (not cookies), which provides natural CSRF protection for API calls made from JavaScript. However, if the architecture ever switches to cookie-based tokens (for SSR or third-party integrations), CSRF becomes a critical vulnerability.

**File:** `/workspace/src/pybend/core/api/backend.py` (line 88) -- tokens read from header only.

**Impact:** Currently low risk due to header-based auth. This is a defensive measure for architecture evolution.

**Implementation approach:**
- Document that `x-access-token` header-based auth is intentionally chosen for CSRF resistance
- If cookie-based auth is ever added, implement CSRF tokens (double-submit cookie pattern)
- Add `SameSite` cookie attributes if cookies are used

**Effort estimate:** 1 hour (documentation now; 4 hours if cookies are introduced later)

---

### Input Validation & Data Safety

#### 11. Request Body Size Limits

**Problem:** No maximum request body size is configured. An attacker can send arbitrarily large POST/PUT bodies to exhaust server memory.

**File:** `/workspace/src/pybend/core/api/backend.py` -- no body size limit in FastAPI config.

**Impact:** Denial of service via memory exhaustion.

**Implementation approach:**
- Add a `RequestSizeLimitMiddleware` that rejects bodies over a configurable limit (e.g., 1MB)
- Or use uvicorn's `--limit-concurrency` and `--limit-max-requests` flags

**Effort estimate:** 1 hour

---

#### 12. File Upload Validation

**Problem:** No explicit file upload endpoints exist, but the `image` field on `ProtoModel` (line 46 of `/workspace/src/pybend/core/models/proto_model.py`) accepts any string URL. If file uploads are added in the future, validation must be in place.

**Impact:** Currently N/A (URLs only). Becomes relevant if direct file upload is supported.

**Implementation approach:**
- Validate that `image` field values are well-formed URLs (not `javascript:`, `data:` with executable MIME types)
- If file upload is added: validate file type, size, content (magic bytes), and store outside the web root

**Effort estimate:** 1 hour for URL validation; 4-6 hours for file upload support

---

#### 13. Input Sanitization Beyond Pydantic

**Problem:** Pydantic validates types and constraints (e.g., `min_length`, `max_length`, `gt=0`) but does not sanitize content. String fields can contain HTML, JavaScript, SQL fragments, or control characters.

**File:** `/workspace/src/pybend/core/models/proto_model.py` -- no sanitization layer.

**Impact:** Stored XSS when values are rendered in the frontend (documented in issues F2-F5). Backend has no defense-in-depth for this.

**Implementation approach:**
- Add a Pydantic validator or field pre-processor that strips HTML tags from text fields by default
- Allow opt-out for fields that intentionally support rich text
- Use `bleach` or `markupsafe` for HTML sanitization

**Effort estimate:** 3-4 hours

---

#### 14. SQL Parameter Binding Audit

**Problem:** While most value queries use parameterized binding (`?` placeholders), the `sql_filter` tuple from the authorization resolver inserts WHERE clauses that could contain unsafe content if the resolver has bugs.

**File:** `/workspace/src/pybend/core/storage/sqlite_storage.py` (lines 80-84)
```python
if sql_filter is not None:
    clause, params = sql_filter
    if clause:
        select_sql += f" WHERE {clause}"
        filter_params = list(params) if params else []
```

The `clause` string is inserted directly. Its safety depends entirely on the `DefaultResolver.sql_filter_for()` implementation.

**Impact:** If a custom resolver is implemented with a bug, it could inject arbitrary SQL through the WHERE clause.

**Implementation approach:**
- Add assertion/validation that `clause` only contains expected SQL tokens (column names, operators, `?` placeholders)
- Document the security contract for custom `AuthorizationResolver` implementations
- Add integration tests that verify the resolver output is safe

**Effort estimate:** 2-3 hours

---

#### 15. XSS Prevention in Schema-Driven Rendering

**Problem:** The frontend renders entity data via `innerHTML` template literals without escaping. This is documented in issues F2-F5 (`/workspace/.traces/issues.md`).

**Key files:**
- `src/pybend/static/NTT0.6/components/ntt-profile.js` (lines 34-108) -- F2
- `src/pybend/static/NTT0.6/components/ntt-topbar.js` (lines 88-128) -- F3
- `src/pybend/static/NTT0.6/components/ntt-item.js` -- xs(), sm(), md() -- F4
- `src/pybend/static/NTT0.6/generators/form.js` -- getInput(), getHeader() -- F5

**Impact:** Stored XSS on every page load (topbar renders on every page).

**Implementation approach:**
- Create a shared `escapeHtml()` utility in the NTT frontend
- Apply it to all template literal interpolations of user data
- Consider a lint rule or code review checklist to prevent future regressions

**Effort estimate:** 3-4 hours (utility + apply across all affected components)

---

### API Security

#### 16. Rate Limiting Per Endpoint

**Problem:** Covered in critical item 5, but the full implementation should support per-endpoint rate limits (not just auth endpoints).

**Impact:** Resource-intensive endpoints (like `/users/login` which does `User.list()`) can be targeted individually.

**Implementation approach:**
- Extend the rate limiter from item 5 with configurable per-path limits
- Use decorator or middleware configuration

**Effort estimate:** Included in item 5

---

#### 17. Request Throttling

**Problem:** No concurrent request limits. A single client can open hundreds of simultaneous connections.

**Impact:** Server resource exhaustion.

**Implementation approach:**
- Configure uvicorn `--limit-concurrency` for connection limits
- Add per-IP concurrent request tracking in middleware

**Effort estimate:** 1-2 hours

---

#### 18. API Versioning Strategy

**Problem:** No API versioning. Routes are at the root (`/products`, `/users`). Breaking changes will affect all clients simultaneously.

**Impact:** No safe upgrade path for API consumers.

**Implementation approach:**
- Add `/api/v1/` prefix to all routes
- Maintain backward compatibility at root during transition
- Document versioning policy

**Effort estimate:** 2-3 hours

---

#### 19. Deprecation Headers

**Problem:** No mechanism to signal deprecated endpoints or fields to API consumers.

**Impact:** No advance warning for breaking changes.

**Implementation approach:**
- Add `Sunset` and `Deprecation` response headers for deprecated endpoints
- Document deprecation policy

**Effort estimate:** 1-2 hours

---

#### 20. Security Headers

**Problem:** No security headers are set on responses.

**File:** `/workspace/src/pybend/core/api/backend.py` -- no security header middleware.

Missing headers:
- `Strict-Transport-Security` (HSTS)
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 0` (modern recommendation)
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Content-Security-Policy` (see item 46)
- `Permissions-Policy`

**Impact:** Browser-level security features are not engaged.

**Implementation approach:**
```python
# Add SecurityHeadersMiddleware to backend.py
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "0"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # HSTS only in production with HTTPS
        if os.getenv("PYBEND_ENV") != "development":
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response
```

**Effort estimate:** 1-2 hours

---

### Storage & Data

#### 21. Database Connection Pooling

**Problem:** Every database operation creates a new `sqlite3.connect()` and closes it immediately after. There is no connection pooling or reuse.

**File:** `/workspace/src/pybend/core/storage/sqlite_storage.py` -- every method calls `sqlite3.connect(self.database)` and `conn.close()` individually.

For example, the `list()` method (lines 72-174) opens a connection, opens a second connection for count (lines 90-94), then opens a third for the main query (lines 105-106). The `_populate_fields()` method receives a connection but it was opened by the caller.

**Impact:** Connection overhead on every request. Not critical for SQLite (file-based) but becomes important if the storage layer is extended to PostgreSQL or MySQL.

**Implementation approach:**
- Use a connection pool (e.g., `sqlalchemy.pool` or a simple thread-local connection)
- For SQLite specifically, use WAL mode and a single shared connection with proper locking

**Effort estimate:** 3-4 hours

---

#### 22. Query Timeout Limits

**Problem:** No query execution timeout. A malformed authorization filter or large dataset could cause a query to run indefinitely.

**Impact:** Server thread blocked indefinitely, leading to resource exhaustion.

**Implementation approach:**
- Set `sqlite3.connect(database, timeout=5)` for SQLite
- For production databases, configure statement timeout at the DB level

**Effort estimate:** 30 minutes

---

#### 23. Migration Rollback Support

**Problem:** The auto-migration system (`migrate_table()` in `/workspace/src/pybend/core/storage/sqlite_migration.py` lines 182-295) has no rollback capability. It adds columns and *removes orphaned columns* (line 268-274), which is destructive and irreversible.

The manual migration system (Rails-style) does support rollback via `down()` methods, but the auto-migration has no undo.

**Impact:** Data loss from accidental column removal. No recovery path from failed migrations.

**Implementation approach:**
- Add a backup step before auto-migration (copy database file)
- Log all auto-migration changes to the `_migrations` table
- Implement a `--dry-run` flag that shows what would change without executing
- Consider making column removal opt-in rather than automatic

**Effort estimate:** 4-5 hours

---

#### 24. Data Backup Strategy

**Problem:** No backup mechanism. The SQLite database file (`pybend.db`) is the single copy of all data. The seed script's `--reset` flag (line 156-159 of `/workspace/src/pybend/core/seed.py`) deletes the database with `os.remove()` with no backup.

**Impact:** Data loss from any failure (disk, migration bug, accidental reset).

**Implementation approach:**
- Add a `backup` management command that copies the DB file with timestamp
- Implement automatic pre-migration backups
- Document backup/restore procedures
- For production: add scheduled backup to external storage

**Effort estimate:** 2-3 hours

---

#### 25. Sensitive Data Encryption at Rest

**Problem:** Password hashes are stored via bcrypt (good), but all other data is stored as plaintext in SQLite. No field-level encryption exists for sensitive data.

**File:** `/workspace/src/pybend/core/models/user_model.py` -- `password_hash` is properly hashed. But `email` is plaintext.

**Impact:** Database file compromise exposes all user data.

**Implementation approach:**
- Add a `__encrypted_fields__` class variable on models for fields requiring encryption
- Implement transparent encryption/decryption in the storage layer using `cryptography.fernet`
- Store encryption keys separately from the database

**Effort estimate:** 6-8 hours

---

### Logging & Monitoring

#### 26. Structured Logging Format

**Problem:** All logging uses `print()` statements scattered throughout the codebase. No structured format, no log levels, no correlation IDs.

**Files:**
- `/workspace/src/pybend/core/api/routes_fastapi.py` -- lines 62, 172, 184, 219, 223, 238
- `/workspace/src/pybend/core/storage/sqlite_storage.py` -- line 41
- `/workspace/src/pybend/core/models/storable_mixin.py` -- lines 39, 43, 85
- `/workspace/src/pybend/core/storage/sqlite_migration.py` -- multiple print statements

**Impact:** No ability to filter, search, or alert on log events. No request tracing in production.

**Implementation approach:**
- Replace all `print()` calls with `logging.getLogger("pybend").{level}()`
- Configure structured JSON logging for production (e.g., `python-json-logger`)
- Add request ID middleware for correlation
- Configure log levels via environment variable

**Effort estimate:** 4-5 hours (replacing prints + configuring structured logging)

---

#### 27. Audit Trail for Data Mutations

**Problem:** No audit trail for create/update/delete operations. The only record is stdout print statements.

**Impact:** No way to determine who changed what, or when. Required for compliance in many industries.

**Implementation approach:**
- Add an `_audit_log` table recording: timestamp, user_id, action (create/update/delete), model, record_id, changes (JSON diff)
- Hook into StorableMixin create/update/delete methods
- Add a read-only API for audit log access (admin only)

**Effort estimate:** 5-6 hours

---

#### 28. Health Check Endpoint

**Problem:** No health check endpoint. Load balancers and orchestrators have no way to verify the service is healthy.

**Impact:** No automated health monitoring. Unhealthy instances continue receiving traffic.

**Implementation approach:**
- Add `GET /health` returning `{"status": "ok", "version": "0.7.0", "db": "connected"}`
- Check database connectivity as part of the health check
- Add to `AUTH_EXEMPT_PATHS` in backend.py

**Effort estimate:** 30 minutes

---

#### 29. Metrics Endpoint (Prometheus-Compatible)

**Problem:** No application metrics. No visibility into request rates, latencies, error rates, or database performance.

**Impact:** No production monitoring capability.

**Implementation approach:**
- Add `prometheus-fastapi-instrumentator` for automatic HTTP metrics
- Add custom metrics for database query duration, auth failures, rate limit hits
- Expose at `GET /metrics`

**Effort estimate:** 2-3 hours

---

#### 30. Error Tracking Integration

**Problem:** Errors are printed to stdout and returned to the client (item 4). No error tracking service integration.

**Impact:** Errors in production go unnoticed until users report them.

**Implementation approach:**
- Add Sentry SDK integration (or similar) with environment-based DSN configuration
- Configure exception capture in middleware
- Add breadcrumbs for request context

**Effort estimate:** 1-2 hours

---

## Medium Priority

### Operational

#### 31. Graceful Shutdown Handling

**Problem:** No graceful shutdown handling. `uvicorn.run()` (line 59 of `main.py`) uses default signal handling. In-flight requests may be dropped on `SIGTERM`.

**Impact:** Data corruption if a write operation is interrupted mid-transaction.

**Implementation approach:**
- Use uvicorn's `--timeout-graceful-shutdown` flag
- Add FastAPI `on_event("shutdown")` handler to close database connections
- Ensure SQLite transactions complete before shutdown

**Effort estimate:** 1-2 hours

---

#### 32. Configuration Validation on Startup

**Problem:** No validation of configuration values at startup. Invalid `PORT`, `HOST`, or missing required config silently fails or produces cryptic errors later.

**File:** `/workspace/src/pybend/core/config.py` -- bare variable assignments with no validation.

**Impact:** Runtime errors instead of clear startup failures.

**Implementation approach:**
- Add a `validate_config()` function called from `main.py` before anything else
- Validate: PORT is int in valid range, HOST is valid, JWT_SECRET is set (non-dev), SQLITE_DB_FILE path is writable

**Effort estimate:** 1-2 hours

---

#### 33. Environment-Specific Defaults

**Problem:** The config module (`/workspace/src/pybend/core/config.py`) has a single set of defaults. `HOST = "0.0.0.0"` is appropriate for containerized deployment but exposes the server on all interfaces in development.

**Impact:** Development server unnecessarily exposed on network.

**Implementation approach:**
- Add `PYBEND_ENV` environment variable (development/staging/production)
- Different defaults per environment (e.g., HOST=127.0.0.1 in dev, 0.0.0.0 in production)
- Auto-detect environment from common signals (e.g., `KUBERNETES_SERVICE_HOST`)

**Effort estimate:** 2 hours

---

#### 34. Secret Rotation Support

**Problem:** Changing the JWT secret invalidates all existing tokens immediately. No support for key rotation with a grace period.

**Impact:** Token rotation causes mass logout of all users.

**Implementation approach:**
- Support multiple JWT secrets (current + previous)
- `decode_token()` tries current secret first, falls back to previous
- Remove old secret after a grace period (1x token expiry duration)

**Effort estimate:** 2-3 hours

---

#### 35. Deployment Documentation

**Problem:** No deployment guide. The only run instructions are `python3 main.py` with `uvicorn.run()`.

**Impact:** Inconsistent deployments. No guidance on production settings (workers, reverse proxy, TLS).

**Implementation approach:**
- Document: environment variables, reverse proxy setup (nginx), TLS termination, systemd/docker config
- Include production uvicorn settings: `--workers`, `--access-log`, `--proxy-headers`
- Provide Docker Compose and Kubernetes examples

**Effort estimate:** 3-4 hours

---

### Performance

#### 36. Response Caching Strategy

**Problem:** No caching at any level. Schema endpoints return the same JSON on every request. Entity lists are re-queried on every request.

**Impact:** Unnecessary database load for read-heavy workloads.

**Implementation approach:**
- Add `Cache-Control` headers to schema endpoints (long TTL, schemas rarely change)
- Add ETag support for entity responses
- Consider in-memory caching for `model.schema()` output (it's computed per-request but doesn't change until restart)

**Effort estimate:** 3-4 hours

---

#### 37. Database Query Optimization

**Problem:** Several inefficient query patterns:
1. `User.login()` does `User.list()` -- full table scan instead of `WHERE email = ?` (line 83 of `user_model.py`)
2. `User.register()` does `User.list()` to check email uniqueness (line 122 of `user_model.py`)
3. FK hydration in `list()` executes N+1 queries (one per parent per collection field)
4. No database indexes beyond the primary key

**Impact:** Performance degrades linearly with data volume. Login becomes slower as user count grows.

**Implementation approach:**
- Add `get_by_field(field, value)` to StorableMixin for indexed lookups
- Add SQL indexes on commonly queried fields (`email`, FK columns)
- Batch FK hydration queries (already partially done in `_populate_fields` but not in `list()`)
- Add UNIQUE constraint on `users.email`

**Effort estimate:** 4-5 hours

---

#### 38. Static Asset Caching Headers

**Problem:** Static files served via `StaticFiles(directory=str(static_dir))` use default headers (no caching).

**File:** `/workspace/src/pybend/core/api/backend.py` (line 130)

**Impact:** Browser re-downloads all JS/CSS on every page load.

**Implementation approach:**
- Configure `StaticFiles` with `Cache-Control: max-age=86400` for hashed assets
- Use fingerprinted filenames for cache busting

**Effort estimate:** 1-2 hours

---

#### 39. Gzip/Brotli Compression

**Problem:** No response compression. JSON responses and static files are sent uncompressed.

**Impact:** Higher bandwidth usage, slower page loads.

**Implementation approach:**
- Add `GZipMiddleware` from Starlette: `app.add_middleware(GZipMiddleware, minimum_size=500)`

**Effort estimate:** 15 minutes

---

#### 40. Connection Keep-Alive Tuning

**Problem:** Using default uvicorn keep-alive settings. No tuning for production load patterns.

**Impact:** Suboptimal connection reuse under load.

**Implementation approach:**
- Configure uvicorn `--timeout-keep-alive` based on expected client behavior
- Document recommended settings for different deployment scenarios

**Effort estimate:** 30 minutes

---

### Testing & Quality

#### 41. Security-Focused Test Suite

**Problem:** The existing test suite covers functionality but not security-specific scenarios (injection attempts, auth bypass, privilege escalation).

**Impact:** Security regressions go undetected.

**Implementation approach:**
- Add test cases for: SQL injection via input fields, XSS payloads in entity fields, JWT manipulation, auth bypass attempts, IDOR (accessing other users' resources), privilege escalation
- Include in CI pipeline

**Effort estimate:** 6-8 hours

---

#### 42. Fuzzing for Input Handlers

**Problem:** No fuzz testing for API input handlers.

**Impact:** Edge cases in input parsing may cause crashes or unexpected behavior.

**Implementation approach:**
- Use `hypothesis` for property-based testing of Pydantic models
- Use `schemathesis` for API fuzzing based on OpenAPI schema
- Add to CI as a nightly job

**Effort estimate:** 4-5 hours

---

#### 43. Dependency Vulnerability Scanning

**Problem:** No automated scanning for known vulnerabilities in Python or JS dependencies.

**Impact:** Vulnerable dependencies may ship to production.

**Implementation approach:**
- Add `pip-audit` or `safety` to CI for Python
- Add `npm audit` for frontend dependencies
- Configure GitHub Dependabot or Snyk

**Effort estimate:** 1-2 hours

---

#### 44. SAST/DAST Integration

**Problem:** No static or dynamic application security testing in the development workflow.

**Impact:** Code-level vulnerabilities not caught before merge.

**Implementation approach:**
- Add `bandit` for Python SAST
- Add `semgrep` with security-focused rulesets
- Consider OWASP ZAP for DAST in staging

**Effort estimate:** 2-3 hours

---

#### 45. Load Testing Benchmarks

**Problem:** No load testing. Unknown performance characteristics under concurrent load.

**Impact:** No baseline for performance regression detection. Unknown capacity limits.

**Implementation approach:**
- Create `locust` or `k6` load test scripts for common workflows (login, list, create, read)
- Establish baseline metrics (p50/p95/p99 latency, max throughput)
- Include in release checklist

**Effort estimate:** 3-4 hours

---

### Frontend Security

#### 46. Content Security Policy

**Problem:** No CSP headers. The frontend uses `innerHTML` extensively, so `unsafe-inline` would be needed initially, but a CSP can still prevent external script loading and other attacks.

**Impact:** No browser-level defense against injected scripts.

**Implementation approach:**
- Start with a report-only CSP to identify violations
- Gradually tighten: remove `unsafe-inline` by migrating to DOM APIs
- Set CSP header in the security headers middleware (item 20)

**Effort estimate:** 2-3 hours (initial), 10+ hours (full inline elimination)

---

#### 47. Subresource Integrity for Static Assets

**Problem:** Frontend JS files loaded via `<script src>` have no integrity attributes. If the static file server is compromised, modified scripts execute without detection.

**Impact:** Supply chain attack vector.

**Implementation approach:**
- Generate SRI hashes during build/deploy
- Add `integrity="sha384-..."` and `crossorigin="anonymous"` to script tags

**Effort estimate:** 2 hours

---

#### 48. Secure Cookie Configuration

**Problem:** Currently not using cookies (JWT in header), but if cookies are introduced (item 10), they need proper configuration.

**Impact:** N/A currently. Defensive documentation.

**Implementation approach:**
- Document: `Secure`, `HttpOnly`, `SameSite=Strict`, `Path=/`, short expiry
- Add to the auth system configuration

**Effort estimate:** 1 hour (if needed)

---

#### 49. Client-Side Input Validation Alignment

**Problem:** Frontend form validation is minimal. Pydantic validates on the backend, but rejected requests show as generic HTTP 422 errors without clear field-level feedback.

**Impact:** Poor UX. Users submit invalid data and get opaque errors.

**Implementation approach:**
- The schema already carries validation constraints (`minLength`, `maxLength`, `minimum`, `maximum`)
- Implement client-side validation in `form.js` that reads these constraints
- Display field-level error messages before submission

**Effort estimate:** 4-5 hours

---

#### 50. WebSocket Security

**Problem:** A WebSocket transport exists (`/workspace/src/pybend/static/NTT0.6/core/transport/Socket.js`) but has bugs (issue F10 -- `readystate` typo, missing `this.` prefix). If/when it is activated, it needs authentication and message validation.

**Impact:** Currently dead code. Becomes relevant if real-time features are enabled.

**Implementation approach:**
- Fix existing bugs (F10)
- Require JWT authentication on WebSocket connection (validate token on upgrade)
- Validate incoming message format and size
- Implement heartbeat/timeout for idle connections

**Effort estimate:** 3-4 hours

---

### Compliance & Documentation

#### 51. Security Policy (SECURITY.md)

**Problem:** No security policy or vulnerability reporting process.

**Impact:** Security researchers have no way to report vulnerabilities responsibly.

**Implementation approach:**
- Create `SECURITY.md` with: supported versions, reporting instructions, expected response timeline, PGP key (optional)

**Effort estimate:** 1 hour

---

#### 52. Responsible Disclosure Process

**Problem:** No vulnerability disclosure process defined.

**Impact:** Vulnerabilities may be disclosed publicly without prior notice.

**Implementation approach:**
- Set up a security@domain email
- Document the disclosure timeline (acknowledge within 48h, fix within 90 days)
- Consider a bug bounty program for critical findings

**Effort estimate:** 1 hour

---

#### 53. Dependency License Audit

**Problem:** No audit of dependency licenses. PyBend uses `pydantic`, `fastapi`, `uvicorn`, `bcrypt`, `PyJWT`, `sqlite3` (stdlib). Frontend has no npm dependencies currently but the test infrastructure adds `jest`, `jsdom`, etc.

**Impact:** License compliance risk for commercial users.

**Implementation approach:**
- Run `pip-licenses` to generate license report
- Verify all dependencies are compatible with PyBend's intended license
- Document in `LICENSE` or `THIRD_PARTY_LICENSES`

**Effort estimate:** 1-2 hours

---

#### 54. Privacy Considerations (GDPR)

**Problem:** No data export, data deletion, or consent management features. User data (name, email) is stored without explicit consent tracking.

**Impact:** Non-compliance with GDPR and similar regulations for European users.

**Implementation approach:**
- Add `GET /users/{id}/export` endpoint returning all user data as JSON/ZIP
- Add `DELETE /users/{id}` with cascading data deletion (related to issue B6)
- Add consent tracking fields to user model
- Document data retention policy

**Effort estimate:** 6-8 hours

---

#### 55. API Security Documentation

**Problem:** No documentation of the API's security model for consumers. The CLAUDE.md describes the architecture for developers, but API consumers need to know: how to authenticate, what permissions they need, how errors are returned.

**Impact:** API consumers may misuse the API or implement insecure client code.

**Implementation approach:**
- Document: authentication flow, token usage, error response format, rate limits, CORS policy
- Add to the auto-generated docs or as a separate security guide
- Include in OpenAPI schema descriptions

**Effort estimate:** 3-4 hours

---

## Implementation Order

The recommended implementation sequence accounts for dependencies between items and risk reduction per unit of effort.

### Phase 1: Critical Security (Week 1)
| # | Item | Depends On | Effort |
|---|------|-----------|--------|
| 1 | JWT Secret Management | -- | 1-2h |
| 4 | Error Information Disclosure | -- | 1-2h |
| 3 | CORS Wildcard in Production | -- | 1h |
| 20 | Security Headers | -- | 1-2h |
| 28 | Health Check Endpoint | -- | 30min |
| 39 | Gzip Compression | -- | 15min |

### Phase 2: Authentication Hardening (Week 1-2)
| # | Item | Depends On | Effort |
|---|------|-----------|--------|
| 5 | Rate Limiting | -- | 3-4h |
| 7 | Password Complexity | -- | 1h |
| 8 | Account Lockout | 5 | 3-4h |
| 15 | XSS Prevention (frontend) | -- | 3-4h |
| 37 | Database Query Optimization (login) | -- | 4-5h |

### Phase 3: Input Safety & Storage (Week 2-3)
| # | Item | Depends On | Effort |
|---|------|-----------|--------|
| 2 | SQL Identifier Quoting | -- | 2-3h |
| 11 | Request Body Size Limits | -- | 1h |
| 13 | Input Sanitization | -- | 3-4h |
| 22 | Query Timeout Limits | -- | 30min |
| 26 | Structured Logging | -- | 4-5h |

### Phase 4: Token Management (Week 3)
| # | Item | Depends On | Effort |
|---|------|-----------|--------|
| 6 | Token Refresh | 1 | 3-4h |
| 9 | Session Invalidation | 6 | 4-5h |
| 34 | Secret Rotation | 1 | 2-3h |

### Phase 5: Observability & Operations (Week 3-4)
| # | Item | Depends On | Effort |
|---|------|-----------|--------|
| 27 | Audit Trail | 26 | 5-6h |
| 29 | Metrics Endpoint | -- | 2-3h |
| 30 | Error Tracking | 26 | 1-2h |
| 31 | Graceful Shutdown | -- | 1-2h |
| 32 | Config Validation | -- | 1-2h |

### Phase 6: Testing & Quality (Week 4-5)
| # | Item | Depends On | Effort |
|---|------|-----------|--------|
| 41 | Security Test Suite | 1-5 | 6-8h |
| 43 | Dependency Scanning | -- | 1-2h |
| 44 | SAST/DAST Integration | -- | 2-3h |
| 45 | Load Testing | 28, 29 | 3-4h |

### Phase 7: Everything Else (Ongoing)
Remaining items from Medium Priority, implemented as needed alongside feature work.

---

## Quick Wins

Items that can be implemented in under 1 hour each:

| # | Item | Effort | Impact |
|---|------|--------|--------|
| 28 | Health Check Endpoint | 30min | Enables monitoring |
| 39 | Gzip Compression | 15min | 60-80% bandwidth reduction for JSON |
| 22 | Query Timeout Limits | 30min | Prevents runaway queries |
| 40 | Connection Keep-Alive Tuning | 30min | Better connection reuse |
| 3 | CORS Wildcard Fix | 1h | Eliminates cross-origin attack vector |
| 7 | Password Complexity | 1h | Eliminates trivial passwords |
| 11 | Request Body Size Limits | 1h | Prevents memory exhaustion |
| 20 | Security Headers | 1h | Enables browser security features |
| 51 | SECURITY.md | 1h | Enables responsible disclosure |
| 52 | Responsible Disclosure Process | 1h | Professional security posture |
| 10 | CSRF Documentation | 1h | Documents existing protection |

**Total quick-win effort:** ~8 hours for 11 improvements.

---

## Cross-References

### Issues Already Tracked in `/workspace/.traces/issues.md`

| Issue | Roadmap Item | Status |
|-------|-------------|--------|
| B7 (CORS wildcard) | Item 3 | This roadmap |
| B8 (JWT secret) | Item 1 | This roadmap |
| B9 (Email uniqueness) | Item 37 | This roadmap |
| B10 (Token decode errors) | Item 4 (related) | This roadmap |
| B6 (No cascade delete) | Item 54 (GDPR) | This roadmap |
| F1 (Permissions NOT rule) | Not in scope | Fix separately |
| F2-F5 (XSS) | Item 15 | This roadmap |
| F6 (NetworkAdapter callback) | Not in scope | Fix separately |
| F7 (Observable conflict) | Not in scope | Fix separately |
| F8 (registrar.js assertion) | Not in scope | Fix separately |
| F9 (Unvalidated URL) | Item 12 | This roadmap |
| F10 (Socket.js bugs) | Item 50 | This roadmap |

### Items Being Addressed in v0.7.0 (Phase 7)

The following critical items have partial fixes being implemented as part of the v0.7.0 release cycle:
- **Item 1 (JWT Secret):** The `authorize.configure()` pattern is in place; what remains is refusing to start with default secrets in production.
- **Item 3 (CORS):** No fix in v0.7.0; still `["*"]`. Needs explicit implementation.
- **Item 4 (Error Disclosure):** `get_traceback_info()` still returns full traces. Needs environment-aware toggling.
- **Item 5 (Rate Limiting):** No fix in v0.7.0. Needs full implementation.

The above items are the minimum set that must be resolved before any production deployment.
