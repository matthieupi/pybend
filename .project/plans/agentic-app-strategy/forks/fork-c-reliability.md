# Fork C: Reliability Path -- Full Resilience Stack

**Scope:** Everything from doc 04 (production hardening) beyond the Sprint 1 critical safety items.
**Assumption:** Sprint 1 is complete: SSRF prevention (`security.py`), SQLite pragmas, error classification (`errors.py`), AgentRun model, trace interceptor.
**Duration:** ~2 weeks (10 working days)
**Branch:** `v0.10-reliability` (from `v0.9`)

---

## Table of Contents

1. [Prerequisites and Sprint 1 Inventory](#1-prerequisites-and-sprint-1-inventory)
2. [Task Breakdown](#2-task-breakdown)
3. [Dependency Graph](#3-dependency-graph)
4. [Detailed Task Specifications](#4-detailed-task-specifications)
5. [New Dependencies](#5-new-dependencies)
6. [Interceptor Chain Ordering](#6-interceptor-chain-ordering)
7. [Test Strategy](#7-test-strategy)
8. [Risk Register](#8-risk-register)

---

## 1. Prerequisites and Sprint 1 Inventory

These are assumed complete before starting Fork C:

| Sprint 1 Deliverable | File | Status |
|---|---|---|
| SSRF prevention | `src/n3tx/core/agents/security.py` | Done |
| Error classification | `src/n3tx/core/agents/errors.py` | Done |
| SQLite pragmas (NORMAL sync, 10s busy_timeout, cache_size) | `src/n3tx/core/storage/sqlite_storage.py` | Done |
| AgentRun model (run history) | `example_grants/models/agent_run.py` (or `src/n3tx/core/agents/`) | Done |
| Trace interceptor (agent run logging) | `src/n3tx/core/agents/` or `example_grants/` | Done |

**From Sprint 1, Fork C inherits:**
- `errors.py` with `classify_tx_error()`, `TransientError`, `PermanentError`, `ResourceError` -- used by Tasks 1 and 2.
- `security.py` with `validate_url()` -- used by Task 3 (circuit breaker integration alongside SSRF check).
- SQLite pragmas already applied -- no further storage work in this fork.

---

## 2. Task Breakdown

| # | Task | Type | Est. | Day | Depends On |
|---|------|------|------|-----|------------|
| **T1** | Retry logic -- tool level (Pydantic AI retries) | Framework | 0.5d | 1 | Sprint 1 (errors.py) |
| **T2** | Updated `_route_tool_call` with error classification | Framework | 0.5d | 1 | Sprint 1 (errors.py) |
| **T3** | Retry logic -- HTTP level (tenacity on scrape) | App | 1d | 2 | -- |
| **T4** | Circuit breaker implementation | Framework | 1d | 3 | -- |
| **T5** | Circuit breaker interceptor on WebTools | App | 0.5d | 4 | T4 |
| **T6** | Circuit breaker tests | Framework+App | 0.5d | 4 | T4, T5 |
| **T7** | Rate limiting -- API endpoints (SlowAPI) | Framework | 1d | 5 | -- |
| **T8** | Rate limiting -- web scraping (per-domain) | App | 0.5d | 6 | -- |
| **T9** | Rate limiting -- LLM tokens (UsageLimits) | Framework | 0.5d | 6 | -- |
| **T10** | Idempotent grant creation | App | 1d | 7 | -- |
| **T11** | Structured logging -- configuration | Framework | 1d | 8 | -- |
| **T12** | Structured logging -- agent run correlation IDs | Framework | 1d | 9 | T11 |
| **T13** | Graceful shutdown | Framework+App | 1d | 10 | -- |
| **T14** | Health check endpoints | Framework+App | 0.5d | 10 | -- |

**Total: ~10 days of work across 10 calendar days.**

---

## 3. Dependency Graph

```
Sprint 1: errors.py (classify_tx_error)
    |
    +--- T1 (tool retries) + T2 (_route_tool_call update)
    |
    |    T3 (tenacity on scrape) -- independent
    |
    T4 (circuit breaker implementation) -- independent
    |
    +--- T5 (circuit breaker interceptor on WebTools)
    |    |
    |    +--- T6 (circuit breaker tests)
    |
    T7 (SlowAPI rate limiting) -- independent
    T8 (scraping rate limit) -- independent
    T9 (LLM token limits) -- independent
    T10 (idempotent grant create) -- independent
    |
    T11 (structlog config) -- independent
    |
    +--- T12 (correlation IDs in agent_run)
    |
    T13 (graceful shutdown) -- independent
    T14 (health checks) -- independent
```

Parallelizable groups:
- **Group A (Day 1-2):** T1+T2 (tool retries), T3 (tenacity)
- **Group B (Day 3-4):** T4 (circuit breaker), T5+T6 (interceptor+tests)
- **Group C (Day 5-6):** T7 (SlowAPI), T8 (scrape rate limit), T9 (LLM tokens)
- **Group D (Day 7):** T10 (idempotent create)
- **Group E (Day 8-9):** T11+T12 (structured logging)
- **Group F (Day 10):** T13 (shutdown), T14 (health checks)

---

## 4. Detailed Task Specifications

### T1: Tool-Level Retry Configuration (0.5 days)

**Goal:** Wire Pydantic AI's built-in `retries` parameter into `make_tool()` so that per-tool retry count is configurable via agent constraints.

**Files modified:**
- `src/n3tx/core/agents/tools.py` -- `make_tool()` accepts `retries` parameter
- `src/n3tx/core/agents/mixin.py` -- `agent_run()` reads `constraints['tool_retries']` and passes to `make_tool()`

**Changes to `tools.py`:**

```python
# make_tool() signature change:
def make_tool(spec: ToolSpec, retries: int = 3):
    from pydantic_ai.tools import Tool
    fn = create_tool_function(spec)
    return Tool(
        function=fn,
        takes_ctx=True,
        name=spec.tool_name,
        description=spec.description,
        retries=retries,
    )
```

**Changes to `mixin.py`:**

```python
# In agent_run(), when building tools:
tool_retries = constraints.get('tool_retries', 3)
ai_tools = [make_tool(spec, retries=tool_retries) for spec in tool_specs]
```

**Why `retries=3` default:** Pydantic AI's default is 1. Three retries gives transient errors (network blips, rate limits with short backoff) a realistic chance to recover. The LLM sees the error message from `_route_tool_call` and can adjust its approach.

**Test:** `example_grants/tests/test_agent_run.py` -- add a test that verifies the Tool objects created by `make_tool()` have the expected `retries` value. Mock a transient failure and verify the tool is retried.

---

### T2: Updated `_route_tool_call` with Error Classification (0.5 days)

**Goal:** Replace the generic `ModelRetry("Tool call failed")` with classified error messages that guide the LLM's retry behavior.

**Files modified:**
- `src/n3tx/core/agents/tools.py` -- `_route_tool_call()` function

**Current code (line 194-196):**
```python
if response.is_error:
    from pydantic_ai import ModelRetry
    raise ModelRetry(response.data.get('message', 'Tool call failed'))
```

**Updated code:**
```python
if response.is_error:
    from pydantic_ai import ModelRetry
    from n3tx.core.agents.errors import classify_tx_error

    error = classify_tx_error(response)
    if error.retryable:
        raise ModelRetry(
            f"[{error.category}] {response.data.get('message', 'Tool call failed')}. "
            f"This is a temporary issue -- retry or use a different approach."
        )
    else:
        raise ModelRetry(
            f"[permanent] {response.data.get('message', 'Tool call failed')}. "
            f"Do NOT retry this exact operation -- the error will not resolve."
        )
```

**Key design choice:** Both branches raise `ModelRetry`. For permanent errors, the message instructs the LLM to stop retrying that specific call. Combined with T1's `retries=3`, permanent errors exhaust retries after one attempt with a clear "do not retry" signal, while transient errors get the full retry budget.

**The error classification from Sprint 1 provides:**
- `classify_tx_error(tx)` reads `tx.data['code']` and maps:
  - 429 -> `ResourceError` (retryable)
  - 408, 502, 503, 504 -> `TransientError` (retryable)
  - 400, 401, 403, 404, 422 -> `PermanentError` (not retryable)
  - Default -> `TransientError`

**Test:** Unit test in `src/n3tx/core/tests/unit/test_agent_tools.py` (new file) that creates mock error TXs with various codes and verifies the correct ModelRetry messages.

---

### T3: HTTP-Level Retry with Tenacity (1 day)

**Goal:** Add tenacity retry decorator to `WebTools.scrape()` for automatic retry on transient HTTP errors.

**Files modified:**
- `example_grants/models/web_tools.py` -- `scrape()` method
- `pyproject.toml` -- add `tenacity` to `agents` optional dependency

**Updated `web_tools.py`:**

```python
from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception_type, before_sleep_log,
)
import httpx
import logging

logger = logging.getLogger('n3tx.agents')

class WebTools(ActorModel):
    __tablename__ = 'web_tools'
    __storable__ = False

    @expose_route('/scrape', methods=['POST'], access=AUTHENTICATED)
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def scrape(self, url: str) -> dict:
        """Fetch a URL and return its HTML content."""
        from n3tx.core.agents.security import validate_url
        url = validate_url(url)  # SSRF prevention from Sprint 1
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=30,
            headers={'User-Agent': 'GrantWatcher/1.0 (+https://example.com/bot)'},
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
        return {'url': url, 'status': resp.status_code, 'html': resp.text[:50000]}
```

**Decorator stacking note:** The `@retry` decorator wraps `scrape()` before `@expose_route` processes it. `@expose_route` reads `__endpoint__` metadata which is set by the decorator factory -- it does not change the function's runtime behavior. The `retry` decorator wraps the actual function call, so it executes inside the route handler. Order: `expose_route` is outermost (metadata), `retry` wraps the function body.

**Important:** `tenacity` supports async functions natively since v8.0. The `@retry` decorator detects `async def` and wraps with `async for attempt in ...` internally.

**Configuration via constraints (future):** For now, hardcode `stop_after_attempt(3)` and `wait_exponential(min=2, max=30)`. These could later be read from a config dict, but YAGNI for the grants app.

**Test:** `example_grants/tests/test_web_tools_retry.py` -- mock `httpx.AsyncClient.get()` to raise `httpx.TimeoutException` twice, succeed on third attempt. Verify the function returns successfully. Also test that permanent errors (e.g., 404) are not retried (they raise `httpx.HTTPStatusError`, not in the retry filter).

---

### T4: Circuit Breaker Implementation (1 day)

**Goal:** In-process, per-domain circuit breaker for external service calls. Pure Python, no dependencies, ~80 lines.

**New file:** `src/n3tx/core/agents/circuit.py`

**This is a framework-level component** because circuit breakers are reusable across any agentic app, not specific to grants.

```python
"""In-process circuit breaker for external service calls.

Three states: CLOSED (normal) -> OPEN (failing, reject calls) -> HALF_OPEN (test recovery).

Usage:
    breaker = get_breaker("scrape:grants.gov")
    if not breaker.can_execute():
        return tx.error("Circuit open", code=503)
    try:
        result = await do_thing()
        breaker.record_success()
    except Exception:
        breaker.record_failure()

Or as a TX interceptor via actor.use() -- see circuit_interceptor().
"""

import time
import logging
from enum import Enum

logger = logging.getLogger('n3tx.circuit')


class CircuitState(Enum):
    CLOSED = 'closed'
    OPEN = 'open'
    HALF_OPEN = 'half_open'


class CircuitBreaker:
    """Per-target circuit breaker.

    Args:
        name: Identifier (e.g., "scrape:grants.gov").
        failure_threshold: Consecutive failures before opening. Default 5.
        recovery_timeout: Seconds before testing recovery. Default 60.
    """

    def __init__(self, name: str, failure_threshold: int = 5,
                 recovery_timeout: float = 60.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.success_count = 0

    def can_execute(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                logger.info("[%s] Circuit half-open, testing recovery", self.name)
                return True
            return False
        return True  # HALF_OPEN allows one test call

    def record_success(self):
        if self.state == CircuitState.HALF_OPEN:
            logger.info("[%s] Circuit closed (recovered)", self.name)
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count += 1

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            logger.warning(
                "[%s] Circuit re-opened from half-open after failure", self.name
            )
        elif self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(
                "[%s] Circuit OPEN after %d failures (retry in %ds)",
                self.name, self.failure_count, self.recovery_timeout,
            )

    def reset(self):
        """Manual reset (for admin/testing)."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0


# ── Global registry ──

_breakers: dict[str, CircuitBreaker] = {}

def get_breaker(name: str, **kwargs) -> CircuitBreaker:
    """Get or create a circuit breaker by name."""
    if name not in _breakers:
        _breakers[name] = CircuitBreaker(name, **kwargs)
    return _breakers[name]

def reset_all():
    """Reset all circuit breakers (for testing)."""
    _breakers.clear()
```

**Design decisions:**
- **In-memory, not Redis:** Single-instance deployment for grants app. Redis adds a dependency and operational complexity with no benefit at this scale.
- **Per-domain, not per-tool:** A domain going down affects all tools that call it. Circuit breaker keyed by `"scrape:{domain}"` catches this correctly.
- **HALF_OPEN allows exactly one test call:** If it succeeds, circuit closes. If it fails, circuit re-opens immediately (no threshold -- one failure in HALF_OPEN means the service is still down).
- **Thread safety:** Not needed. FastAPI runs in a single asyncio event loop. All circuit breaker state mutations happen in coroutines, which are cooperative (no preemption within a coroutine body). The `time.time()` reads are atomic. If uvicorn workers are added later, each worker gets its own circuit breaker state -- acceptable for this scale.

---

### T5: Circuit Breaker Interceptor on WebTools (0.5 days)

**Goal:** Wire the circuit breaker into WebTools as a TX interceptor using the `use()` pattern.

**Files modified:**
- `example_grants/models/web_tools.py` -- add interceptor registration
- `example_grants/main.py` -- register interceptor at app startup

**The interceptor function (in `web_tools.py` or a separate `interceptors.py`):**

```python
from n3tx.core.agents.circuit import get_breaker
from n3tx.core.actors.tx import TX

async def scrape_circuit_breaker(tx: TX) -> TX:
    """TX interceptor: check circuit breaker before scraping.

    Only applies to 'scrape' messages. Other messages pass through.
    After the handler responds, the circuit breaker is updated by the
    scrape method itself (or via a post-handler pattern).
    """
    if tx.name != 'scrape':
        return tx

    url = (tx.data or {}).get('url', '')
    from urllib.parse import urlparse
    domain = urlparse(url).netloc or 'unknown'

    breaker = get_breaker(f"scrape:{domain}")
    if not breaker.can_execute():
        return tx.error(
            f"Circuit open for {domain} -- service is unavailable, try again later",
            code=503,
        )
    return tx
```

**Registration in `main.py` (after `create_app`):**

```python
# Register circuit breaker interceptor on WebTools inbox
from models.web_tools import scrape_circuit_breaker
WebTools.use(scrape_circuit_breaker, on='inbox')
```

**Recording success/failure:** The interceptor only blocks requests when the circuit is open. Recording outcomes requires post-handler integration. Two approaches:

**Approach A (Recommended): Update circuit in `scrape()` itself:**
```python
async def scrape(self, url: str) -> dict:
    from urllib.parse import urlparse
    from n3tx.core.agents.circuit import get_breaker
    domain = urlparse(url).netloc
    breaker = get_breaker(f"scrape:{domain}")
    try:
        # ... httpx call ...
        breaker.record_success()
        return result
    except Exception:
        breaker.record_failure()
        raise
```

This is simpler and more explicit. The interceptor blocks when open; the method records outcomes. No new abstractions needed.

**Approach B: Send interceptor on WebTools that inspects replies.** More complex, requires correlating request/response TXs. Not worth the complexity for this use case.

**How this maps to N3TX primitives:**
- `WebTools.use(fn, on='inbox')` -- same pattern as `api.use(auth_interceptor, on='request')` in `app.py`
- Error TX returned from interceptor short-circuits the chain (line 314-317 in `actor.py`): `if tx.is_error: await target.send(tx); return`
- The error TX routes back through Matrix to the agent's adapter, where `_route_tool_call` classifies it as a `TransientError` (code 503) and raises `ModelRetry` with an appropriate message

---

### T6: Circuit Breaker Tests (0.5 days)

**New files:**
- `src/n3tx/core/tests/unit/test_circuit.py` -- unit tests for `CircuitBreaker` class
- `example_grants/tests/test_circuit_interceptor.py` -- integration test for the TX interceptor

**Unit tests (`test_circuit.py`):**
1. **CLOSED -> OPEN transition:** Record `failure_threshold` failures, verify `state == OPEN`, verify `can_execute()` returns `False`.
2. **OPEN -> HALF_OPEN transition:** Set `last_failure_time` to `time.time() - recovery_timeout - 1`, verify `can_execute()` returns `True` and `state == HALF_OPEN`.
3. **HALF_OPEN -> CLOSED on success:** From HALF_OPEN, call `record_success()`, verify `state == CLOSED` and `failure_count == 0`.
4. **HALF_OPEN -> OPEN on failure:** From HALF_OPEN, call `record_failure()`, verify `state == OPEN`.
5. **CLOSED stays CLOSED below threshold:** Record `failure_threshold - 1` failures, verify still CLOSED.
6. **`get_breaker()` reuses instances:** Call twice with same name, verify same object.
7. **`reset_all()` clears registry.**
8. **`reset()` resets individual breaker.**

**Integration test (`test_circuit_interceptor.py`):**
1. **Open circuit returns 503 TX:** Manually open the circuit for a domain, send a scrape TX through the interceptor, verify error TX with code 503.
2. **Closed circuit passes through:** Verify the interceptor returns the original TX unchanged when circuit is closed.
3. **Non-scrape TXs pass through:** Verify interceptor ignores TXs with `name != 'scrape'`.

---

### T7: Rate Limiting -- API Endpoints with SlowAPI (1 day)

**Goal:** Add HTTP-level rate limiting to FastAPI endpoints using SlowAPI middleware.

**Files modified:**
- `src/n3tx/core/api/backend.py` -- add SlowAPI limiter state and error handler
- `src/n3tx/core/app.py` -- pass rate limit config, apply to sensitive routes
- `pyproject.toml` -- add `slowapi` dependency

**Changes to `backend.py` (`FastAPIBackend.__init__`):**

```python
# After CORSMiddleware:
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded

    limiter = Limiter(key_func=get_remote_address)
    self.app.state.limiter = limiter
    self.app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    self._limiter = limiter
except ImportError:
    self._limiter = None
    logger.info("slowapi not installed -- rate limiting disabled")
```

**The `try/except ImportError` pattern** keeps SlowAPI optional. The framework should not hard-require it; apps that want rate limiting install it.

**Per-endpoint limits on agent run route:**

SlowAPI decorates individual route functions. For the `create_api_routes()` generated routes in `network_api.py`, we need a way to apply limits. Two options:

**Option A (Recommended): Apply in `create_api_routes()` conditionally:**
```python
# In network_api.py, for the agent run endpoint:
if hasattr(app_or_router, 'state') and hasattr(app_or_router.state, 'limiter'):
    limiter = app_or_router.state.limiter
    # Apply to specific routes
```

**Option B: Middleware-level global rate limit:**
```python
# In backend.py, as middleware — simpler but less granular:
from slowapi.middleware import SlowAPIMiddleware
self.app.add_middleware(SlowAPIMiddleware)
```

**Recommended configuration:**
| Endpoint Pattern | Limit | Rationale |
|---|---|---|
| `POST /agents/{id}/run` | 5/minute | Agent runs are expensive (LLM tokens) |
| All CRUD endpoints | 60/minute | Standard API rate limiting |
| `POST /login` | 10/minute | Brute force prevention |
| `GET /health`, `GET /ready` | No limit | Monitoring must always work |
| Schema endpoints (`GET /{ClassName}`) | No limit | Cached, lightweight |

**Important:** Rate limiting at this level is app-level configuration, not framework core. The `FastAPIBackend` provides the limiter instance; the app decides which routes to limit.

**Test:** `example_grants/tests/test_rate_limiting.py` -- send 6 requests to `/agents/1/run` in quick succession, verify the 6th returns 429. Use `TestClient` with `raise_server_exceptions=False`.

---

### T8: Rate Limiting -- Web Scraping Per-Domain (0.5 days)

**Goal:** Prevent hammering government websites by enforcing per-domain delays between scrape requests.

**Files modified:**
- `example_grants/models/web_tools.py` -- add domain rate limiting to `scrape()`

**Implementation (in `web_tools.py`):**

```python
import asyncio
import time
from collections import defaultdict
from urllib.parse import urlparse

_domain_semaphores: dict[str, asyncio.Semaphore] = defaultdict(lambda: asyncio.Semaphore(1))
_last_request_time: dict[str, float] = {}
_MIN_INTERVAL = 2.0  # seconds between requests to same domain


async def _rate_limit_domain(domain: str):
    """Enforce per-domain rate limit with semaphore + delay."""
    sem = _domain_semaphores[domain]
    async with sem:
        now = time.time()
        last = _last_request_time.get(domain, 0)
        wait = _MIN_INTERVAL - (now - last)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_request_time[domain] = time.time()
```

**Called at the top of `scrape()`:**
```python
async def scrape(self, url: str) -> dict:
    from n3tx.core.agents.security import validate_url
    url = validate_url(url)
    domain = urlparse(url).netloc
    await _rate_limit_domain(domain)
    # ... rest of scrape logic
```

**Why app-level, not framework-level:** Per-domain scrape rate limiting is specific to web scraping tools. Other tool actors (database, API) have different rate limiting needs. Putting this in `example_grants/models/web_tools.py` keeps the concern local.

**Why semaphore + delay, not token bucket:** Simpler. Government websites are not high-throughput targets. One request per 2 seconds per domain is generous and prevents any appearance of abuse. A token bucket would be needed for burst-then-throttle patterns, which is not the use case here.

**Test:** `example_grants/tests/test_web_tools_retry.py` (extend existing test file) -- mock `httpx` and verify that two scrape calls to the same domain take at least `_MIN_INTERVAL` seconds total.

---

### T9: Rate Limiting -- LLM Tokens via UsageLimits (0.5 days)

**Goal:** Extend `agent_run()` to read token limits from agent constraints and pass them to Pydantic AI's `UsageLimits`.

**Files modified:**
- `src/n3tx/core/agents/mixin.py` -- `agent_run()` method

**Current code (line 122-126):**
```python
usage_limits = None
if constraints.get('max_iterations'):
    usage_limits = UsageLimits(
        request_limit=constraints['max_iterations'],
    )
```

**Updated code:**
```python
usage_limits = None
if constraints:
    limits_kwargs = {}
    if constraints.get('max_iterations'):
        limits_kwargs['request_limit'] = constraints['max_iterations']
    if constraints.get('max_input_tokens'):
        limits_kwargs['request_tokens_limit'] = constraints['max_input_tokens']
    if constraints.get('max_output_tokens'):
        limits_kwargs['response_tokens_limit'] = constraints['max_output_tokens']
    if constraints.get('max_total_tokens'):
        limits_kwargs['total_tokens_limit'] = constraints['max_total_tokens']
    if limits_kwargs:
        usage_limits = UsageLimits(**limits_kwargs)
```

**Constraints schema documentation (for `AgentActor.constraints` field):**
```json
{
    "max_iterations": 25,
    "max_input_tokens": 100000,
    "max_output_tokens": 50000,
    "max_total_tokens": 150000,
    "tool_retries": 3
}
```

**Test:** `example_grants/tests/test_agent_run.py` -- add a test that creates an agent with `constraints={"max_iterations": 2}` and verifies the UsageLimits is set correctly. Use `TestModel` which respects usage limits.

---

### T10: Idempotent Grant Creation (1 day)

**Goal:** Prevent duplicate grants when an agent retries `grants_create`. Dedup by URL.

**Files modified:**
- `example_grants/models/grant.py` -- override `create()` classmethod

**Implementation:**

```python
class Grant(ActorModel):
    # ... existing fields ...

    @classmethod
    def create(cls, data):
        """Idempotent create: if a grant with the same URL exists, return it."""
        # Extract URL from the data (may be a Grant instance or a dict)
        from pydantic import BaseModel
        if isinstance(data, BaseModel):
            url_val = getattr(data, 'url', None)
        elif isinstance(data, dict):
            url_val = data.get('url')
        else:
            url_val = None

        if url_val:
            url_str = str(url_val)
            existing = cls.list(sql_filter=("url = ?", [url_str]))
            items = existing.get('data', existing) if isinstance(existing, dict) else existing
            if items:
                logger.info("Idempotent create: grant with URL %s already exists (id=%s)",
                            url_str, items[0].id)
                return items[0]

        return super().create(data)
```

**Why URL-based dedup:**
- Every grant has a unique URL (the listing page on grants.gov or similar).
- An agent retrying `grants_create` after a transient failure will send the same URL.
- Title-based dedup would be fragile (titles can vary slightly between runs).
- A composite key (URL + agency) adds complexity with no benefit -- URL is already unique.

**Edge case: same grant, different URL format:** `http://grants.gov/1234` vs `https://www.grants.gov/1234/`. The `validate_url()` from Sprint 1 normalizes scheme to HTTPS, but hostname variations are not normalized. This is acceptable -- false negatives (missing a dedup) create an extra record, which is less harmful than false positives (blocking a legitimate new grant).

**Test:** `example_grants/tests/test_idempotent_create.py` -- create a grant, then create another with the same URL. Verify only one record exists and the second `create()` returns the first record. Also test that different URLs create separate records.

---

### T11: Structured Logging -- Configuration (1 day)

**Goal:** Migrate from stdlib `logging` to `structlog` for JSON-structured output in production and human-readable output in development. Incremental -- existing `logging.getLogger()` calls continue to work.

**New file:** `src/n3tx/core/logging.py`

**Files modified:**
- `pyproject.toml` -- add `structlog` dependency
- `example_grants/main.py` -- call `configure_logging()` at startup

**Implementation (`logging.py`):**

```python
"""Structured logging configuration for N3TX.

Wraps stdlib logging with structlog processors. Existing
logging.getLogger() calls work unchanged -- structlog captures
them via ProcessorFormatter on the root handler.

Usage:
    from n3tx.core.logging import configure_logging
    configure_logging(json_output=False)  # dev mode

    # Then in any module:
    import structlog
    logger = structlog.get_logger('n3tx.agents')
    logger.info("agent_run.start", run_id="abc123", tools=["grants"])
"""

import logging
import structlog


def configure_logging(json_output: bool = True, level: int = logging.INFO):
    """Configure structlog for N3TX.

    Args:
        json_output: True for production (JSON lines), False for dev (colored console).
        level: Root log level.
    """
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if json_output:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
```

**Integration in `example_grants/main.py`:**

```python
# Replace: logging.basicConfig(level=logging.INFO, format='...')
# With:
from n3tx.core.logging import configure_logging
is_production = os.environ.get('N3TX_ENV') == 'production'
configure_logging(json_output=is_production)
```

**Incremental migration strategy:**
1. Install structlog, add `configure_logging()` call -- all existing `logging.getLogger()` output is now formatted by structlog (JSON in prod, colored in dev).
2. Over time, replace `logging.getLogger()` with `structlog.get_logger()` in specific modules to get structured key-value logging. This is additive and non-breaking.
3. Never remove stdlib logging support -- third-party libraries use it.

**Framework vs App:** `configure_logging()` lives in framework (`src/n3tx/core/logging.py`) because structured logging is a framework concern. The call site is the app (`main.py`) because logging configuration is a startup decision.

**Test:** `src/n3tx/core/tests/unit/test_logging_config.py` -- call `configure_logging(json_output=True)`, emit a log message via `logging.getLogger('test')`, capture output and verify it's valid JSON with expected keys (`timestamp`, `level`, `logger`).

---

### T12: Structured Logging -- Agent Run Correlation IDs (1 day)

**Goal:** Add correlation IDs to agent run logs so every log line from a single run can be traced.

**Files modified:**
- `src/n3tx/core/agents/mixin.py` -- use structlog context vars in `agent_run()`
- `src/n3tx/core/agents/tools.py` -- log tool calls with run context

**Changes to `mixin.py`:**

```python
import structlog

logger = structlog.get_logger('n3tx.agents')

async def agent_run(self, prompt, tools, task, user=None, **kwargs):
    # ... existing setup ...

    run_id = TX(name='', source='', target='').uuid  # already exists on line 87

    # Bind correlation context for all log lines in this run
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        run_id=run_id,
        agent_addr=agent_addr,
        user_id=user.get('user_id') if user else None,
    )

    logger.info("agent_run.start", task_length=len(task), tools=tools)

    try:
        result = await ai_agent.run(task, deps=deps, usage_limits=usage_limits)
        usage = result.usage()

        logger.info("agent_run.complete",
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            requests=usage.requests,
            messages=len(result.all_messages()),
        )

        return { ... }

    except Exception as e:
        logger.error("agent_run.failed",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise

    finally:
        root._children.pop(adapter_addr, None)
        logger.info("agent_run.cleanup", adapter=adapter_addr)
        structlog.contextvars.clear_contextvars()
```

**Changes to `tools.py` (`_route_tool_call`):**

```python
import structlog

logger = structlog.get_logger('n3tx.agents.tools')

async def _route_tool_call(ctx, target_addr, method_name, data):
    logger.info("tool_call.start", target=target_addr, method=method_name)
    # ... existing logic ...
    if response.is_error:
        logger.warning("tool_call.error",
            target=target_addr, method=method_name,
            code=response.data.get('code'),
            message=response.data.get('message'),
        )
        # ... error classification ...
    else:
        logger.info("tool_call.success", target=target_addr, method=method_name)
    return json.dumps(response.data, default=str)
```

**Why `contextvars`:** The `run_id` is bound at the start of `agent_run()` and automatically appears in every log line emitted during that coroutine's execution, including deep in tool calls and interceptors. No need to pass `run_id` through function parameters. `contextvars` are coroutine-scoped in asyncio, so concurrent agent runs get separate contexts.

**Important: `clear_contextvars()` in `finally`:** Prevents context leaking to subsequent requests on the same event loop task. The `finally` block ensures cleanup even if the run fails.

**Test:** Extend `example_grants/tests/test_agent_run.py` -- capture log output during an agent run and verify `run_id` appears in all log lines.

---

### T13: Graceful Shutdown (1 day)

**Goal:** Track active agent runs and drain them with a configurable timeout before the server stops.

**Files modified:**
- `src/n3tx/core/agents/mixin.py` -- register/deregister active runs
- `src/n3tx/core/app.py` -- add FastAPI lifespan with shutdown drain
- `src/n3tx/core/api/backend.py` -- pass lifespan to FastAPI constructor

**Active run tracking (in `mixin.py`):**

```python
import asyncio

# Module-level active run registry
_active_runs: dict[str, asyncio.Task] = {}

def get_active_runs() -> dict:
    """Get currently active agent runs (for shutdown + health check)."""
    return dict(_active_runs)
```

**In `agent_run()`, wrap the run in a task and register it:**

```python
async def agent_run(self, ...):
    run_id = TX(name='', source='', target='').uuid
    # ... setup ...

    # Register this run for graceful shutdown tracking
    current_task = asyncio.current_task()
    if current_task:
        _active_runs[run_id] = current_task

    try:
        # ... existing run logic ...
    finally:
        _active_runs.pop(run_id, None)
        root._children.pop(adapter_addr, None)
```

**Lifespan context manager (in `app.py`):**

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def _lifespan(app):
    # Startup (nothing needed)
    yield
    # Shutdown
    from n3tx.core.agents.mixin import get_active_runs
    active = get_active_runs()
    if active:
        import logging
        logger = logging.getLogger('n3tx.shutdown')
        logger.info("Shutdown: waiting for %d active agent runs", len(active))
        timeout = float(os.environ.get('N3TX_SHUTDOWN_TIMEOUT', '30'))
        done, pending = await asyncio.wait(
            active.values(),
            timeout=timeout,
        )
        if pending:
            logger.warning("Force-cancelling %d agent runs after %ds", len(pending), timeout)
            for task in pending:
                task.cancel()
            # Wait briefly for cancellation to propagate
            await asyncio.gather(*pending, return_exceptions=True)
```

**Changes to `backend.py`:**

```python
# In FastAPIBackend.__init__:
self.app = FastAPI(
    title=self.name,
    version=self.version,
    description=self.description,
    lifespan=lifespan,  # new parameter
)
```

The `lifespan` parameter needs to be threaded through from `create_app()` / `N3TXApp.build()` to `FastAPIBackend.__init__()`. Add it as an optional parameter to `FastAPIBackend`:

```python
def __init__(self, cors_origins=None, ssr_mode='off', lifespan=None, **data):
    # ... existing code ...
    self.app = FastAPI(
        title=self.name,
        version=self.version,
        description=self.description,
        lifespan=lifespan,
    )
```

**Test:** `src/n3tx/core/tests/unit/test_graceful_shutdown.py` -- create a mock async task registered in `_active_runs`, call `shutdown_agents()` with a 1-second timeout, verify the task is cancelled. Also test the happy path where the task completes before the timeout.

---

### T14: Health Check Endpoints (0.5 days)

**Goal:** Add `/health` (liveness) and `/ready` (readiness) endpoints.

**Files modified:**
- `src/n3tx/core/app.py` -- add health check routes in `N3TXApp.build()`

**Implementation (in `build()`, after route registration):**

```python
import time

_start_time = time.time()

@backend.app.get("/health", tags=["Operations"], include_in_schema=False)
async def health():
    """Liveness probe. Lightweight, no dependency checks."""
    return {
        "status": "healthy",
        "uptime_seconds": round(time.time() - _start_time, 1),
    }

@backend.app.get("/ready", tags=["Operations"], include_in_schema=False)
async def ready():
    """Readiness probe. Checks DB connectivity and actor system."""
    from fastapi.responses import JSONResponse
    checks = {}

    # Database check
    try:
        # Use the storage from the first registered model
        model_cls = next(iter(registered_models.values()), None)
        if model_cls and hasattr(model_cls, 'storage'):
            with model_cls.storage._connection() as conn:
                conn.execute("SELECT 1")
            checks['database'] = 'ok'
        else:
            checks['database'] = 'no models registered'
    except Exception as e:
        checks['database'] = f'error: {e}'

    # Matrix check
    from n3tx.core.actors.actor import Actor
    root = Actor.root()
    checks['matrix'] = 'ok' if root else 'error: no root actor'
    if root:
        checks['actor_count'] = len(root.children)

    # Active agent runs
    from n3tx.core.agents.mixin import get_active_runs
    checks['active_agent_runs'] = len(get_active_runs())

    all_ok = all(
        v == 'ok' or isinstance(v, int)
        for v in checks.values()
    )

    return JSONResponse(
        content={
            "status": "ready" if all_ok else "not_ready",
            "checks": checks,
        },
        status_code=200 if all_ok else 503,
    )
```

**Why `include_in_schema=False`:** Health check endpoints are operational, not part of the API contract. They should not appear in OpenAPI docs or be discoverable by N3TX schema resolution.

**Why framework-level:** Every N3TX app needs health checks for deployment. The `/health` endpoint is universal. The `/ready` endpoint checks N3TX-specific dependencies (Matrix, storage).

**Test:** `example_grants/tests/test_health.py` -- GET `/health` returns 200 with `status: healthy`. GET `/ready` returns 200 with `database: ok` and `matrix: ok`.

---

## 5. New Dependencies

| Package | Version | Size | Maturity | PyPI Downloads/month | Purpose | Required? |
|---------|---------|------|----------|---------------------|---------|-----------|
| `tenacity` | `>=8.0,<10` | ~30KB | 7+ years, 9K+ GitHub stars | 30M+ | Retry decorator for `WebTools.scrape()` | Optional (agents extra) |
| `slowapi` | `>=0.1.9,<1.0` | ~20KB | Mature (port of flask-limiter) | 500K+ | HTTP rate limiting middleware | Optional (new extra) |
| `structlog` | `>=24.0,<26.0` | ~100KB | 10+ years, 3.5K+ stars | 10M+ | JSON-structured logging | Optional (new extra) |

**Updates to `pyproject.toml`:**

```toml
[project.optional-dependencies]
agents = ["pydantic-ai>=1.0", "tenacity>=8.0,<10"]
ratelimit = ["slowapi>=0.1.9,<1.0"]
logging = ["structlog>=24.0,<26.0"]
production = ["tenacity>=8.0,<10", "slowapi>=0.1.9,<1.0", "structlog>=24.0,<26.0"]
dev = [
    "pytest>=8.2", "pytest-cov>=6.0", "httpx>=0.27",
    "pyinstrument>=4.6", "requests>=2.31", "pydantic-ai>=1.0",
    "tenacity>=8.0,<10", "slowapi>=0.1.9,<1.0", "structlog>=24.0,<26.0",
]
```

**Justification for each:**
- **tenacity:** The de facto Python retry library. Supports async natively, has exponential backoff, jitter, and conditional retry. Building our own would be 200+ lines to replicate what tenacity does in 3 lines of decorator config. Zero runtime overhead when not retrying.
- **slowapi:** FastAPI-native rate limiting. Wraps `limits` (the same library behind flask-limiter). Three lines to add, handles storage backends (in-memory by default), sliding windows, and per-endpoint configuration.
- **structlog:** The standard for structured logging in Python. Works with stdlib logging (incremental migration), supports contextvars (correlation IDs), JSON output for log aggregation, colored dev output. Building our own structured logger would be reimplementing structlog.

**Not added:**
- **pybreaker:** Custom 80-line implementation preferred (see T4 rationale). Avoids a dependency for a simple pattern. Our implementation integrates directly with TX/interceptors.

---

## 6. Interceptor Chain Ordering

When `routing='actor'` (Level 3), the `NetworkAPI` adapter can have multiple interceptors registered on the `request` method. The order matters because interceptors run FIFO (first-in, first-out) as implemented in `Actor._run_interceptors()` (line 289-299 of `actor.py`).

### Current Chain (Sprint 1 complete)

```
NetworkAPI.request(tx)
  |
  [request interceptors - FIFO order]
  |
  1. auth_interceptor      -- registered in app.py build()
  2. trace_interceptor      -- registered in app.py build() (Sprint 1)
  |
  [send to Matrix]
```

### After Fork C

```
NetworkAPI.request(tx)
  |
  [request interceptors - FIFO order]
  |
  1. auth_interceptor        -- MUST be first (rejects 401/403 before any processing)
  2. rate_limit_interceptor  -- AFTER auth (rate limit per authenticated user, not per anon request)
  3. trace_interceptor       -- AFTER rate limit (only trace requests that pass the gate)
  |
  [send to Matrix]
```

**Registration order in `app.py`:**

```python
api = NetworkAPI()
matrix.register(api)
api.use(auth_interceptor, on='request')       # 1st
api.use(rate_limit_interceptor, on='request')  # 2nd (if using TX-level rate limiting)
api.use(trace_interceptor, on='request')       # 3rd
```

**The circuit breaker is NOT on NetworkAPI.** It is on `WebTools.inbox`, which is a different interceptor chain:

```
WebTools.inbox(tx)
  |
  [inbox interceptors - FIFO order]
  |
  1. scrape_circuit_breaker  -- blocks if circuit is open for the target domain
  |
  [handler dispatch]
  |
  scrape() method runs:
    - SSRF check (validate_url)
    - domain rate limit (asyncio.Semaphore + delay)
    - tenacity retry wrapper
    - httpx request
    - circuit breaker record_success/record_failure
```

**Key insight:** The interceptor chains are actor-scoped, not global. `NetworkAPI` interceptors gate the API boundary. `WebTools` interceptors gate the scraping boundary. They never interfere because they run on different actors.

### Interaction Diagram

```
HTTP POST /agents/1/run {"task": "Find grants"}
  |
  v
NetworkAPI.request(tx)
  |-- auth_interceptor: verify JWT -> pass
  |-- rate_limit_interceptor: check 5/min -> pass
  |-- trace_interceptor: log request -> pass
  |
  v
Matrix routes to AgentActor (addr='agents')
  |
  v
AgentActor.handler_crud() -> dispatches to run()
  |
  v
agent_run() starts (mixin.py)
  |-- creates transient adapter
  |-- discovers tools
  |-- Pydantic AI loop calls grants_list, web_tools_scrape, etc.
  |
  v
Tool call: web_tools_scrape(url="https://nsf.gov/...")
  |
  v
_route_tool_call() creates TX(target='web_tools', name='scrape')
  |
  v
transient adapter.request(tx) -> Matrix -> WebTools.inbox(tx)
  |
  v
WebTools inbox interceptors:
  |-- scrape_circuit_breaker: check circuit for nsf.gov -> pass
  |
  v
WebTools.handler dispatches to scrape()
  |-- validate_url() -> SSRF check
  |-- _rate_limit_domain("nsf.gov") -> per-domain delay
  |-- @retry (tenacity) wraps httpx call
  |   |-- attempt 1: httpx.TimeoutException -> wait 2s
  |   |-- attempt 2: httpx.TimeoutException -> wait 4s
  |   |-- attempt 3: success!
  |-- circuit breaker.record_success()
  |
  v
Response TX routes back to transient adapter
  |
  v
_route_tool_call() returns JSON to Pydantic AI
  |
  v
LLM processes response, may call more tools...
  |
  v
agent_run() completes, returns result dict
```

---

## 7. Test Strategy

### Unit Tests (Framework)

| File | Tests | Covers |
|---|---|---|
| `src/n3tx/core/tests/unit/test_circuit.py` | 8 tests | CircuitBreaker state machine (T4, T6) |
| `src/n3tx/core/tests/unit/test_agent_tools.py` | 4 tests | `make_tool()` retries param, `_route_tool_call` error classification (T1, T2) |
| `src/n3tx/core/tests/unit/test_logging_config.py` | 3 tests | `configure_logging()` JSON/console modes (T11) |
| `src/n3tx/core/tests/unit/test_graceful_shutdown.py` | 3 tests | Active run tracking, shutdown drain (T13) |

### Integration Tests (App)

| File | Tests | Covers |
|---|---|---|
| `example_grants/tests/test_web_tools_retry.py` | 4 tests | Tenacity retry, domain rate limiting (T3, T8) |
| `example_grants/tests/test_circuit_interceptor.py` | 3 tests | TX interceptor with circuit breaker (T5) |
| `example_grants/tests/test_rate_limiting.py` | 3 tests | SlowAPI endpoint rate limiting (T7) |
| `example_grants/tests/test_idempotent_create.py` | 3 tests | Grant dedup by URL (T10) |
| `example_grants/tests/test_health.py` | 2 tests | Health and readiness endpoints (T14) |
| `example_grants/tests/test_agent_run.py` | 2 new tests | UsageLimits from constraints, correlation IDs in logs (T9, T12) |

### Testing Patterns

**Circuit breaker state transitions (T6):**
```python
def test_circuit_opens_after_threshold():
    breaker = CircuitBreaker("test", failure_threshold=3, recovery_timeout=1.0)
    for _ in range(3):
        breaker.record_failure()
    assert breaker.state == CircuitState.OPEN
    assert not breaker.can_execute()

def test_circuit_half_opens_after_timeout():
    breaker = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.1)
    breaker.record_failure()
    assert breaker.state == CircuitState.OPEN
    time.sleep(0.15)
    assert breaker.can_execute()
    assert breaker.state == CircuitState.HALF_OPEN
```

**Retry with mocked failures (T3):**
```python
@pytest.mark.asyncio
async def test_scrape_retries_on_timeout():
    """scrape() retries on TimeoutException, succeeds on 3rd attempt."""
    call_count = 0
    original_get = httpx.AsyncClient.get

    async def mock_get(self, url, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise httpx.TimeoutException("timeout")
        # Return a mock response
        return httpx.Response(200, text="<html>OK</html>")

    with patch.object(httpx.AsyncClient, 'get', mock_get):
        wt = WebTools()
        result = await wt.scrape("https://example.com/grants")
        assert result['status'] == 200
        assert call_count == 3
```

**Rate limiting (T7):**
```python
def test_agent_run_rate_limited(client, alice_token):
    """6th agent run request within 1 minute returns 429."""
    headers = {"x-access-token": alice_token}
    for i in range(5):
        resp = client.post("/agents/1/run", json={"task": "test"}, headers=headers)
        # May fail for other reasons, but should not be 429
        assert resp.status_code != 429

    resp = client.post("/agents/1/run", json={"task": "test"}, headers=headers)
    assert resp.status_code == 429
```

**Idempotent create (T10):**
```python
def test_duplicate_grant_url_returns_existing(test_db, seed_data, alice_token):
    """Creating a grant with an existing URL returns the existing grant."""
    existing = seed_data["grants"][0]
    duplicate = Grant(
        title="Different Title",
        agency="Different Agency",
        url=existing.url,
        user_owner=seed_data["users"]["alice"].id,
    )
    result = Grant.create(duplicate)
    assert result.id == existing.id
    assert result.title == existing.title  # Original, not duplicate
```

### Test Environment Notes

- **Tenacity tests:** Set `wait=wait_none()` in test overrides to avoid actual sleep delays. Or use `tenacity.stop_after_attempt(1)` to disable retries in tests that don't test retry behavior.
- **Circuit breaker tests:** Use short `recovery_timeout` (0.1s) so HALF_OPEN transitions are fast. Call `reset_all()` in test teardown to prevent cross-test contamination.
- **SlowAPI tests:** SlowAPI uses in-memory storage by default, which is per-process. TestClient runs in the same process as the app, so rate limits accumulate across test cases. Use `limiter.reset()` in fixtures.
- **structlog tests:** Capture log output by adding a `StringIO` handler before the test and reading it after. Or use structlog's `testing.capture_logs()` context manager.

---

## 8. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| tenacity `@retry` on async `scrape()` does not compose with `@expose_route` | Low | Medium | Test early (T3 day 2). Decorator stacking is well-defined; `@expose_route` only sets metadata. |
| Circuit breaker too aggressive (opens on transient blip) | Medium | Low | Conservative defaults (5 failures, 60s recovery). Can be tuned via `get_breaker()` kwargs. |
| SlowAPI rate limits break TestClient tests | Medium | Low | Use `limiter.reset()` in test fixtures. Or configure higher limits in test mode. |
| structlog breaks existing log parsers | Low | Medium | Incremental migration: stdlib loggers still work, just reformatted. JSON output only in production mode. |
| Graceful shutdown `asyncio.wait()` does not cancel Pydantic AI's internal event loop | Medium | Medium | Pydantic AI uses `asyncio.create_task()` internally. Cancelling the outer task propagates `CancelledError` through the task tree. Test with real Pydantic AI (not TestModel). |
| Per-domain rate limiting `asyncio.Semaphore` leaks on domain strings | Low | Low | `defaultdict` creates semaphores lazily. At grants scale (dozens of domains), memory is negligible. |
| Idempotent create `cls.list(sql_filter=...)` is slow without index on `url` | Medium | Low | Add a migration to create `CREATE INDEX idx_grants_url ON grants(url)` in `example_grants/migrations/`. |

---

## Appendix: File Change Summary

### New Files

| File | Type | Task |
|---|---|---|
| `src/n3tx/core/agents/circuit.py` | Framework | T4 |
| `src/n3tx/core/logging.py` | Framework | T11 |
| `src/n3tx/core/tests/unit/test_circuit.py` | Test | T6 |
| `src/n3tx/core/tests/unit/test_agent_tools.py` | Test | T1, T2 |
| `src/n3tx/core/tests/unit/test_logging_config.py` | Test | T11 |
| `src/n3tx/core/tests/unit/test_graceful_shutdown.py` | Test | T13 |
| `example_grants/tests/test_web_tools_retry.py` | Test | T3, T8 |
| `example_grants/tests/test_circuit_interceptor.py` | Test | T5 |
| `example_grants/tests/test_rate_limiting.py` | Test | T7 |
| `example_grants/tests/test_idempotent_create.py` | Test | T10 |
| `example_grants/tests/test_health.py` | Test | T14 |
| `example_grants/migrations/003_grant_url_index.sql` | Migration | T10 |

### Modified Files

| File | Tasks | Nature of Change |
|---|---|---|
| `src/n3tx/core/agents/tools.py` | T1, T2 | `make_tool()` retries param, `_route_tool_call()` error classification |
| `src/n3tx/core/agents/mixin.py` | T1, T9, T12, T13 | Tool retries, UsageLimits, correlation IDs, active run tracking |
| `src/n3tx/core/app.py` | T7, T13, T14 | Lifespan, health endpoints, rate limit wiring |
| `src/n3tx/core/api/backend.py` | T7, T13 | SlowAPI setup, lifespan parameter |
| `example_grants/models/web_tools.py` | T3, T5, T8 | Tenacity, circuit breaker record, domain rate limit |
| `example_grants/models/grant.py` | T10 | Idempotent create override |
| `example_grants/main.py` | T5, T11 | Circuit breaker interceptor registration, configure_logging() |
| `example_grants/tests/test_agent_run.py` | T9, T12 | New tests for UsageLimits and correlation IDs |
| `pyproject.toml` | T3, T7, T11 | New optional dependencies |

### Unchanged Files (no modifications needed)

| File | Reason |
|---|---|
| `src/n3tx/core/actors/actor.py` | `use()` and interceptor chain already support all patterns |
| `src/n3tx/core/actors/tx.py` | `error()` and `is_error` already provide the error channel |
| `src/n3tx/core/api/auth_interceptor.py` | Unchanged; auth remains the first interceptor |
| `src/n3tx/core/api/network_adapter.py` | `request()` already runs interceptors |
| `src/n3tx/core/storage/sqlite_storage.py` | Pragmas done in Sprint 1 |
| `src/n3tx/core/agents/errors.py` | Done in Sprint 1, consumed by T2 |
| `src/n3tx/core/agents/security.py` | Done in Sprint 1, consumed by T3 |

---

## Appendix: Commit Plan

Each task should be committed independently with its tests. Suggested commit messages:

```
feat(agents): Add tool-level retry configuration via constraints [0.10]
feat(agents): Classify TX errors in _route_tool_call for guided LLM retry [0.10]
feat(agents): Add tenacity retry to WebTools.scrape with exponential backoff [0.10]
feat(agents): Add in-process circuit breaker with three-state machine [0.10]
feat(agents): Wire circuit breaker as TX interceptor on WebTools.inbox [0.10]
test(agents): Add circuit breaker state transition and interceptor tests [0.10]
feat(api): Add SlowAPI rate limiting middleware to FastAPIBackend [0.10]
feat(agents): Add per-domain scrape rate limiting with asyncio.Semaphore [0.10]
feat(agents): Extend UsageLimits with token budget from constraints [0.10]
feat(grants): Add idempotent grant creation with URL-based dedup [0.10]
feat(core): Add structured logging configuration with structlog [0.10]
feat(agents): Add correlation IDs to agent_run structured logs [0.10]
feat(core): Add graceful shutdown with active agent run draining [0.10]
feat(core): Add /health and /ready operational endpoints [0.10]
```
