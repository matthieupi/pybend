# Production Hardening: Error Handling, Rate Limiting, Retry Logic & Operational Resilience

## Option 4 -- Grant Watcher Application

---

## 1. Executive Summary

The Grant Watcher is an agentic application where LLM agents scrape government websites, call external APIs, and create database records autonomously. Today, **every one of those external interactions is a single point of failure with no safety net**. A timeout from grants.gov, a rate limit from Anthropic's API, or a transient SQLite lock can silently kill an agent run -- and nobody finds out until a user notices missing grants.

This is not hypothetical. [Recent research on multi-agent LLM systems](https://galileo.ai/blog/multi-agent-llm-systems-fail) found that **rate limiting causes a 93.75% degradation** in agent task completion, while systems with proper retry logic handled transient timeouts at **98.75% success rates**. The difference between "works in demo" and "works in production" is exactly this category of work: error classification, retry policies, circuit breakers, and operational visibility.

The good news: **N3TX's architecture already has the right primitives**. The interceptor system (`use()` on any Actor), the TX error protocol (`tx.error()` / `tx.is_error`), and the NetworkAdapter request-correlation pattern provide natural extension points. Production hardening is not a rewrite -- it is **layering resilience onto an architecture that was designed to support it**.

---

## 2. The What -- Concrete Deliverables

### 2.1 Deliverable Map

| # | Deliverable | Touches | New Files | Estimated LOC |
|---|-------------|---------|-----------|---------------|
| 1 | Error classification + propagation | `mixin.py`, `tools.py`, `tx.py` | `errors.py` | ~150 |
| 2 | Retry logic (tool + agent level) | `mixin.py`, `tools.py`, `web_tools.py` | `retry.py` | ~200 |
| 3 | Circuit breakers for external services | `web_tools.py`, new interceptor | `circuit.py` | ~180 |
| 4 | Rate limiting (API + LLM + scraping) | `app.py`, `mixin.py` | `rate_limit.py` | ~250 |
| 5 | SQLite production hardening | `sqlite_storage.py` | -- | ~50 delta |
| 6 | Health check + readiness endpoints | `app.py`, `backend.py` | -- | ~60 |
| 7 | Structured logging | `mixin.py`, `tools.py`, across codebase | -- | ~100 delta |
| 8 | Graceful shutdown | `app.py`, `mixin.py` | -- | ~80 |
| 9 | Security hardening (SSRF, input validation) | `web_tools.py` | `security.py` | ~120 |
| **Total** | | | ~3 new files | **~1,200 LOC** |

### 2.2 Architecture After Hardening

```
                        +-----------------+
                        |  FastAPI App     |
                        |  /health /ready  |
                        +--------+--------+
                                 |
                    +------------+------------+
                    |                         |
             Rate Limiter              Structured Logger
             (SlowAPI/TX               (structlog JSON)
              interceptor)
                    |                         |
             +------+------+                  |
             | NetworkAPI  |                  |
             | + auth_int  |                  |
             | + rate_int  |                  |
             +------+------+                  |
                    |                         |
              +-----+-----+                  |
              |   Matrix   |                  |
              +-----+------+                  |
                    |                         |
     +-----------+-+---------+                |
     |           |           |                |
  +--+---+  +---+----+  +---+------+         |
  |Grant |  |Source   |  |WebTools  |         |
  |Agent |  |         |  |+ circuit |         |
  |+retry|  |         |  |  breaker |         |
  +------+  +--------+  +----------+         |
     |                        |               |
     +---agent_run()----------+               |
     |  + error classify      |               |
     |  + retry policy        |               |
     |  + usage tracking      |               |
     +------------------------+---------------+
              |
     +--------+--------+
     | External World   |
     | - LLM APIs       |
     | - grants.gov     |
     | - Web sources    |
     +------------------+
```

---

## 3. The Why -- Risk Reduction and Reliability

### 3.1 Current Failure Modes (Unmitigated)

| Failure Scenario | Current Behavior | Impact | Probability |
|-----------------|-----------------|--------|-------------|
| LLM API rate limit (429) | Pydantic AI may retry once, then crash | Agent run lost, tokens wasted | **High** (daily at scale) |
| Web scrape timeout | `httpx.TimeoutError` propagates up, agent_run crashes | Silent failure, no grants found | **High** |
| SQLite busy lock | `sqlite3.OperationalError` after 5s | CRUD fails mid-agent-run | **Medium** (concurrent agents) |
| grants.gov is down | Every scrape attempt fails, LLM keeps trying | Token burn, no useful output | **Medium** |
| Malicious URL in scrape task | Agent scrapes `http://169.254.169.254/` (SSRF) | Cloud metadata exposed | **Low** but catastrophic |
| Agent enters retry loop | No max retries configured | Unbounded token cost | **Medium** |

> :bulb: **Key Insight:** The most expensive failures are **silent**. The `agent_run()` in `mixin.py` has a bare `try/finally` that cleans up the transient adapter but **does not catch or classify the exception**. The caller (`AgentActor.run()`) returns `json.dumps(result)` -- but if `agent_run()` throws, the exception propagates to the route layer and becomes a generic 500. No error is recorded, no usage is logged, no retry is attempted.

### 3.2 What Production Hardening Prevents

| Category | Annual cost without hardening (estimate) | With hardening |
|----------|----------------------------------------|----------------|
| Wasted LLM tokens from failed runs | $200-500/month at moderate usage | ~$20-50 (90% reduction) |
| Silent data gaps (missed grants) | Unquantifiable -- discovered by users | Alerts within minutes |
| Debugging time per incident | 2-4 hours (no structured logs) | 15-30 min (correlation IDs) |
| Security incidents (SSRF) | 1 breach = existential risk | Eliminated by design |
| User trust erosion | Hard to measure, easy to feel | Consistent reliability |

---

## 4. The How -- Implementation Details

### 4.1 Error Classification and Propagation

**The problem:** `_route_tool_call()` in `tools.py` already uses Pydantic AI's `ModelRetry` for error TX responses (line 195-196), but it does not distinguish between transient errors (retry-worthy) and permanent errors (stop immediately). The LLM sees "Tool call failed" regardless of whether grants.gov is down vs. the grant title was too long.

**The solution: Classify errors at the TX level.**

```python
# src/n3tx/core/agents/errors.py (new file)

class AgentError(Exception):
    """Base for agent-specific errors with retry semantics."""
    retryable: bool = False
    category: str = 'unknown'

class TransientError(AgentError):
    """Network timeout, rate limit, temporary unavailability."""
    retryable = True
    category = 'transient'

class PermanentError(AgentError):
    """Invalid data, missing required fields, auth failure."""
    retryable = False
    category = 'permanent'

class ResourceError(AgentError):
    """Rate limit, quota exceeded, circuit open."""
    retryable = True  # After backoff
    category = 'resource'

# Map TX error codes to classifications
def classify_tx_error(tx: TX) -> AgentError:
    """Classify a TX error response for retry decisions."""
    code = tx.data.get('code', 500)
    message = tx.data.get('message', '')

    if code == 429:
        return ResourceError(message)
    if code in (408, 502, 503, 504):
        return TransientError(message)
    if code in (400, 401, 403, 404, 422):
        return PermanentError(message)
    return TransientError(message)  # Default: assume transient
```

**Updated `_route_tool_call` with classification:**

```python
# In tools.py -- updated error handling
async def _route_tool_call(ctx, target_addr, method_name, data):
    adapter = ctx.deps.adapter
    meta = {'user': ctx.deps.user} if ctx.deps.user else {}
    tx = TX(name=method_name, source=adapter.addr,
            target=target_addr, data=data, meta=meta)

    response = await adapter.request(tx)

    if response.is_error:
        from pydantic_ai import ModelRetry
        from n3tx.core.agents.errors import classify_tx_error

        error = classify_tx_error(response)
        if error.retryable:
            raise ModelRetry(
                f"[{error.category}] {response.data.get('message', 'Tool call failed')}. "
                f"Try again or use a different approach."
            )
        else:
            # Permanent errors: tell the LLM to stop trying this tool
            raise ModelRetry(
                f"[permanent] {response.data.get('message', 'Tool call failed')}. "
                f"Do NOT retry this operation -- the error is permanent."
            )
    return json.dumps(response.data, default=str)
```

> :bulb: **Key Insight:** For permanent errors, we still raise `ModelRetry` but with phrasing that instructs the LLM to stop. Pydantic AI's [tool retry mechanism](https://ai.pydantic.dev/api/tools/) respects `retries` per-tool, so setting `retries=1` on permanent-error-prone tools prevents infinite loops while still giving the LLM the error message.

**Error propagation through the agent run:**

```
Tool fails (e.g., web scrape timeout)
    |
    v
_route_tool_call() classifies error → raises ModelRetry
    |
    v
Pydantic AI retries tool call (up to tool.retries times)
    |
    v
All retries exhausted → Pydantic AI raises ModelRetry
    |
    v
agent_run() catches, wraps in result dict:
    {
      'answer': null,
      'error': {'category': 'transient', 'message': '...', 'retries_exhausted': true},
      'usage': {...},
      'messages': N
    }
    |
    v
AgentActor.run() returns JSON → HTTP 200 with error field
    (NOT a 500 -- the agent completed, just with errors)
```

### 4.2 Retry Logic

**Two levels of retry: tool-level and agent-level.**

#### Tool-Level Retries (Pydantic AI built-in)

Pydantic AI already supports per-tool `retries` configuration. The `make_tool()` function in `tools.py` should accept retry config from agent constraints.

```python
# Updated make_tool() in tools.py
def make_tool(spec: ToolSpec, retries: int = 3):
    from pydantic_ai.tools import Tool
    fn = create_tool_function(spec)
    return Tool(
        function=fn,
        takes_ctx=True,
        name=spec.tool_name,
        description=spec.description,
        retries=retries,  # Pydantic AI handles retry loop
    )
```

#### Agent-Level Retries (tenacity for external calls)

For `WebTools.scrape()`, which directly calls `httpx`, use tenacity with exponential backoff.

```python
# Updated web_tools.py with tenacity
from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception_type, before_sleep_log
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
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=30,
            headers={'User-Agent': 'GrantWatcher/1.0 (+https://example.com/bot)'}
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()  # Convert 4xx/5xx to exceptions
        return {'url': url, 'status': resp.status_code, 'html': resp.text[:50000]}
```

#### Idempotency for Grant Creation

When an agent retries `grants_create`, it should not create duplicates. The solution: **check-before-create at the model level**.

```python
# In Grant model or as a CRUD interceptor
@classmethod
def create(cls, data):
    """Idempotent create: skip if grant with same URL exists."""
    if hasattr(data, 'url') and data.url:
        existing = cls.list(sql_filter=(
            "url = ?", [str(data.url)]
        ))
        items = existing['data'] if isinstance(existing, dict) else existing
        if items:
            return items[0]  # Return existing instead of duplicate
    return super().create(data)
```

#### Retry Policy Configuration

Store retry policies in `AgentActor.constraints`, read by `agent_run()`:

```python
# Agent constraints schema
{
    "max_iterations": 10,
    "tool_retries": 3,           # per-tool retry count
    "agent_retries": 2,          # full-run retry count
    "backoff_base": 2,           # exponential backoff base (seconds)
    "max_backoff": 60,           # max backoff (seconds)
    "timeout": 300,              # total run timeout (seconds)
}
```

### 4.3 Circuit Breakers

**The pattern:** When grants.gov is down, every scrape attempt fails. Without a circuit breaker, the agent burns through LLM tokens asking the scrape tool to try again and again. A circuit breaker **stops calling a known-failing service** until it recovers.

```python
# src/n3tx/core/agents/circuit.py (new file)
import time
import logging
from enum import Enum

logger = logging.getLogger('n3tx.circuit')

class CircuitState(Enum):
    CLOSED = 'closed'       # Normal operation
    OPEN = 'open'           # Failing -- reject calls immediately
    HALF_OPEN = 'half_open' # Testing recovery -- allow one call

class CircuitBreaker:
    """Per-target circuit breaker for external services.

    Default: open after 5 consecutive failures, retry after 60 seconds.
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
        # HALF_OPEN: allow exactly one call
        return True

    def record_success(self):
        if self.state == CircuitState.HALF_OPEN:
            logger.info("[%s] Circuit closed (recovered)", self.name)
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count += 1

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(
                "[%s] Circuit OPEN after %d failures (retry in %ds)",
                self.name, self.failure_count, self.recovery_timeout
            )

# Global registry (per external service)
_breakers: dict[str, CircuitBreaker] = {}

def get_breaker(name: str, **kwargs) -> CircuitBreaker:
    if name not in _breakers:
        _breakers[name] = CircuitBreaker(name, **kwargs)
    return _breakers[name]
```

**Integration as a TX interceptor:**

```python
# Circuit breaker as an interceptor on WebTools
from n3tx.core.agents.circuit import get_breaker

async def scrape_circuit_breaker(tx: TX) -> TX:
    """Interceptor: check circuit breaker before scraping."""
    if tx.name != 'scrape':
        return tx

    url = (tx.data or {}).get('url', '')
    from urllib.parse import urlparse
    domain = urlparse(url).netloc

    breaker = get_breaker(f"scrape:{domain}")
    if not breaker.can_execute():
        return tx.error(
            f"Circuit open for {domain} -- service unavailable, try later",
            code=503
        )
    return tx

# Register in app setup
WebTools.use(scrape_circuit_breaker, on='inbox')
```

> :bulb: **Key Insight:** Circuit breakers map naturally to the interceptor pattern. `WebTools.use(circuit_breaker, on='inbox')` runs before the handler, and returning an error TX short-circuits the chain. This is the same pattern as `auth_interceptor` -- resilience is just another interceptor.

### 4.4 Rate Limiting

**Three distinct rate limiting concerns:**

| Concern | What | Why | Implementation |
|---------|------|-----|----------------|
| API endpoint rate limiting | `10 req/s` per IP | Prevent DoS, abuse | SlowAPI middleware |
| LLM API rate limiting | Token budgets per agent | Control costs | `UsageLimits` in Pydantic AI |
| Web scraping rate limiting | `1 req/2s` per domain | Don't hammer sources | Semaphore + delay in `WebTools` |

#### API Rate Limiting (SlowAPI)

[SlowAPI](https://github.com/laurentS/slowapi) provides FastAPI-native rate limiting with minimal overhead. According to [recent benchmarks](https://shiladityamajumder.medium.com/using-slowapi-in-fastapi-mastering-rate-limiting-like-a-pro-19044cb6062b), SlowAPI offers **30-50% lower overhead than traditional middleware approaches**.

```python
# In app.py or backend.py -- add rate limiting middleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)

# In create_app or FastAPIBackend.__init__:
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# On sensitive endpoints:
@app.post("/agents/{id}/run")
@limiter.limit("5/minute")  # Max 5 agent runs per minute per IP
async def run_agent(request: Request, id: int, ...):
    ...
```

#### LLM Token Budget Management

Pydantic AI's `UsageLimits` already handles this -- the existing code in `mixin.py` uses `request_limit` from `constraints.max_iterations`. Extend to include token limits:

```python
# In agent_run() -- extended usage limits
usage_limits = None
if constraints:
    usage_limits = UsageLimits(
        request_limit=constraints.get('max_iterations', 25),
        request_tokens_limit=constraints.get('max_input_tokens', 100_000),
        response_tokens_limit=constraints.get('max_output_tokens', 50_000),
        total_tokens_limit=constraints.get('max_total_tokens', 150_000),
    )
```

#### Web Scraping Rate Limiting

```python
# In WebTools -- domain-scoped rate limiting
import asyncio
from collections import defaultdict

_domain_locks: dict[str, asyncio.Semaphore] = defaultdict(lambda: asyncio.Semaphore(1))
_last_request: dict[str, float] = {}
_MIN_INTERVAL = 2.0  # seconds between requests to same domain

async def _rate_limit_domain(domain: str):
    """Enforce per-domain rate limit."""
    async with _domain_locks[domain]:
        now = time.time()
        last = _last_request.get(domain, 0)
        wait = _MIN_INTERVAL - (now - last)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_request[domain] = time.time()
```

#### Rate Limiting as a TX Interceptor

For a framework-level approach, rate limiting can be an interceptor on the NetworkAPI adapter, sitting alongside `auth_interceptor`:

```python
# Rate limit interceptor for NetworkAPI
import time
from collections import defaultdict

_request_counts: dict[str, list] = defaultdict(list)
_WINDOW = 60  # 1 minute
_MAX_REQUESTS = 60  # 60 req/min per user

async def rate_limit_interceptor(tx: TX) -> TX:
    user_id = tx.meta.get('user', {}).get('user_id', 'anon')
    key = f"{user_id}:{tx.target}"
    now = time.time()

    # Sliding window cleanup
    _request_counts[key] = [t for t in _request_counts[key] if now - t < _WINDOW]

    if len(_request_counts[key]) >= _MAX_REQUESTS:
        return tx.error("Rate limit exceeded", code=429)

    _request_counts[key].append(now)
    return tx

# Register alongside auth
api.use(rate_limit_interceptor, on='request')
```

### 4.5 SQLite Production Hardening

**Current state:** The codebase **already has WAL mode and connection pooling** in `sqlite_storage.py`. This is ahead of most Python/SQLite deployments. The existing implementation at lines 58-70 shows:

```python
# Already in sqlite_storage.py:
self._pool = queue.Queue(maxsize=pool_size)  # pool_size=4 default
init_conn = sqlite3.connect(database, check_same_thread=False)
init_conn.execute("PRAGMA journal_mode=WAL")
init_conn.execute("PRAGMA busy_timeout=5000")
```

**Remaining gaps and improvements:**

| Aspect | Current | Recommended | Why |
|--------|---------|-------------|-----|
| Pool size | 4 (hardcoded default) | Configurable, 1 writer + N readers | [SQLite concurrency is 1 writer + many readers](https://emschwartz.me/psa-your-sqlite-connection-pool-might-be-ruining-your-write-performance/) |
| Transaction type | DEFERRED (SQLite default) | BEGIN IMMEDIATE for writes | [Prevents upgrade deadlocks](https://berthub.eu/articles/posts/a-brief-post-on-sqlite3-database-locked-despite-timeout/) |
| Busy timeout | 5000ms | 10000ms for agent workloads | Agent runs can hold locks longer |
| `synchronous` pragma | FULL (default) | NORMAL in WAL mode | [Safe with WAL, 2-3x faster](https://oneuptime.com/blog/post/2026-02-02-sqlite-production-setup/view) |
| DB size management | None | Periodic `VACUUM`, old run cleanup | Prevents unbounded growth |
| Error recovery | Catch `sqlite3.Error` | Retry on `SQLITE_BUSY` with backoff | Resilience under concurrent load |

**Concrete changes to `sqlite_storage.py`:**

```python
# Additional pragmas in __init__:
init_conn.execute("PRAGMA journal_mode=WAL")
init_conn.execute("PRAGMA busy_timeout=10000")
init_conn.execute("PRAGMA synchronous=NORMAL")  # Safe with WAL, faster
init_conn.execute("PRAGMA cache_size=-64000")    # 64MB cache (negative = KB)

# Write operations should use BEGIN IMMEDIATE:
@contextlib.contextmanager
def _write_connection(self):
    """Context manager for write operations with IMMEDIATE transaction."""
    conn = self._get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        self._put_conn(conn)
```

### 4.6 Health Check and Readiness Endpoints

[Production FastAPI deployments](https://www.index.dev/blog/how-to-implement-health-check-in-python) should expose separate liveness and readiness endpoints for container orchestrators.

```python
# Health check endpoints -- add to app.py / create_app()
import time

_start_time = time.time()

@app.get("/health", tags=["Operations"], include_in_schema=False)
async def health():
    """Liveness probe. Lightweight -- no dependency checks."""
    return {
        "status": "healthy",
        "uptime_seconds": round(time.time() - _start_time, 1),
    }

@app.get("/ready", tags=["Operations"], include_in_schema=False)
async def ready():
    """Readiness probe. Checks all critical dependencies."""
    checks = {}

    # SQLite check
    try:
        from n3tx.core.storage.sqlite_storage import SQLiteStorage
        # Quick query to verify DB is accessible
        storage = list(registered_models.values())[0].storage
        with storage._connection() as conn:
            conn.execute("SELECT 1")
        checks['database'] = 'ok'
    except Exception as e:
        checks['database'] = f'error: {e}'

    # Matrix check
    from n3tx.core.actors.actor import Actor
    root = Actor.root()
    checks['matrix'] = 'ok' if root else 'error: no root'
    checks['actors'] = len(root._children) if root else 0

    all_ok = all(v == 'ok' or isinstance(v, int) for v in checks.values())
    status_code = 200 if all_ok else 503

    from fastapi.responses import JSONResponse
    return JSONResponse(
        content={"status": "ready" if all_ok else "not_ready", "checks": checks},
        status_code=status_code,
    )
```

### 4.7 Structured Logging

**Current state:** The codebase uses Python's standard `logging` module consistently (`logger = logging.getLogger('n3tx.xxx')`). There are also raw `print(tx)` calls (e.g., `actor.py` line 311). The logging produces unstructured text output.

**Recommendation: [structlog](https://signoz.io/guides/structlog/) for JSON-structured logs** in production, with human-readable output in development.

```python
# Structured logging configuration
import structlog
import logging

def configure_logging(json_output: bool = True):
    """Configure structlog for N3TX.

    Args:
        json_output: True for production (JSON), False for dev (pretty console).
    """
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
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
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[renderer],
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
```

**Agent-run specific logging with correlation IDs:**

```python
# In mixin.py -- structured logging for agent runs
import structlog

logger = structlog.get_logger('n3tx.agents')

async def agent_run(self, prompt, tools, task, user=None, **kwargs):
    run_id = TX(name='', source='', target='').uuid
    log = logger.bind(
        run_id=run_id,
        agent_addr=agent_addr,
        tools=tools,
        user_id=user.get('user_id') if user else None,
    )

    log.info("agent_run.start", task_length=len(task))

    try:
        result = await ai_agent.run(task, deps=deps, usage_limits=usage_limits)
        usage = result.usage()

        log.info("agent_run.complete",
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            requests=usage.requests,
            messages=len(result.all_messages()),
        )
        return { ... }

    except Exception as e:
        log.error("agent_run.failed",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise
    finally:
        root._children.pop(adapter_addr, None)
        log.info("agent_run.cleanup", adapter=adapter_addr)
```

> :bulb: **Key Insight:** The `run_id` correlation ID connects every log line from a single agent run -- tool calls, retries, circuit breaker trips, and the final result. In production, `grep run_id=abc123` instantly shows the complete execution trace. This is the difference between "something failed" and "here is exactly what happened."

### 4.8 Graceful Shutdown

**The problem:** If the server stops during an `agent_run()`, the transient adapter is orphaned in the Matrix, the LLM API call may be abandoned mid-stream, and partial results are lost.

**Solution: Use [FastAPI lifespan events](https://fastapi.tiangolo.com/advanced/events/) to track and drain active agent runs.**

```python
# Agent run tracking for graceful shutdown
import asyncio

_active_runs: dict[str, asyncio.Task] = {}

async def shutdown_agents(timeout: float = 30.0):
    """Wait for active agent runs to complete, with timeout."""
    if not _active_runs:
        return

    logger.info("Shutting down: %d active agent runs", len(_active_runs))

    # Give active runs time to finish
    done, pending = await asyncio.wait(
        _active_runs.values(),
        timeout=timeout,
    )

    if pending:
        logger.warning("Force-cancelling %d agent runs", len(pending))
        for task in pending:
            task.cancel()

# In create_app() -- lifespan context manager
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    # Startup
    yield
    # Shutdown
    await shutdown_agents(timeout=30)

# Pass to FastAPI:
app = FastAPI(lifespan=lifespan, ...)
```

### 4.9 Security Hardening

#### SSRF Prevention for Web Scraping

The current `WebTools.scrape()` accepts **any URL** and follows redirects. According to the [OWASP SSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html), this is a textbook SSRF vulnerability.

```python
# src/n3tx/core/agents/security.py (new file)
import ipaddress
import socket
from urllib.parse import urlparse

# Blocked IP ranges (RFC 1918, link-local, loopback, cloud metadata)
_BLOCKED_RANGES = [
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
    ipaddress.ip_network('127.0.0.0/8'),
    ipaddress.ip_network('169.254.0.0/16'),   # Link-local / cloud metadata
    ipaddress.ip_network('0.0.0.0/8'),
    ipaddress.ip_network('::1/128'),
    ipaddress.ip_network('fc00::/7'),
]

_ALLOWED_SCHEMES = {'http', 'https'}

def validate_url(url: str) -> str:
    """Validate a URL is safe for server-side requests.

    Raises ValueError if the URL targets internal infrastructure.
    """
    parsed = urlparse(url)

    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ValueError(f"Blocked scheme: {parsed.scheme}")

    if not parsed.hostname:
        raise ValueError("No hostname in URL")

    # Resolve DNS and check against blocked ranges
    try:
        resolved = socket.getaddrinfo(parsed.hostname, parsed.port or 443)
        for _, _, _, _, addr_info in resolved:
            ip = ipaddress.ip_address(addr_info[0])
            for blocked in _BLOCKED_RANGES:
                if ip in blocked:
                    raise ValueError(
                        f"URL resolves to blocked IP range: {ip}"
                    )
    except socket.gaierror:
        raise ValueError(f"Cannot resolve hostname: {parsed.hostname}")

    return url
```

**Updated `WebTools.scrape()`:**

```python
@expose_route('/scrape', methods=['POST'], access=AUTHENTICATED)
async def scrape(self, url: str) -> dict:
    from n3tx.core.agents.security import validate_url
    url = validate_url(url)  # Raises ValueError on blocked URLs
    # ... rest of scrape logic
```

#### Agent Task Input Validation

LLM prompts from user input should be length-limited and logged:

```python
@expose_route('/run', methods=['POST'])
async def run(self, task: str, **kwargs) -> str:
    # Input validation
    if len(task) > 10_000:
        raise MethodError("Task too long (max 10,000 chars)", 400)

    # Log the task for audit trail
    logger.info("Agent run requested",
                agent_id=self.id, task_length=len(task),
                user=kwargs.get('user', {}).get('user_id'))

    # ... proceed with agent_run
```

---

## 5. Feasibility Assessment

### 5.1 Complexity Matrix

| Component | Complexity | Risk | Dependencies | Can ship independently |
|-----------|-----------|------|--------------|----------------------|
| Error classification | Low | Low | None | Yes |
| Tool-level retries | Low | Low | Pydantic AI (already there) | Yes |
| Tenacity on WebTools | Low | Low | `tenacity` (pip install) | Yes |
| Circuit breaker | Medium | Low | None (pure Python) | Yes |
| SlowAPI rate limiting | Low | Low | `slowapi` (pip install) | Yes |
| TX-level rate limiting | Medium | Medium | Interceptor chain ordering | Yes |
| SQLite pragmas | Low | Low | None (config change) | Yes |
| Health endpoints | Low | Low | None | Yes |
| Structured logging | Medium | Medium | `structlog` (pip install) | Partial (incremental migration) |
| Graceful shutdown | Medium | Medium | FastAPI lifespan | Yes |
| SSRF prevention | Low | **Critical** | None (pure Python) | Yes |
| Idempotent creates | Medium | Medium | Model method override | Yes |

### 5.2 Dependency Impact

| New dependency | Size | Maturity | Maintenance |
|---------------|------|----------|-------------|
| `tenacity` | ~30KB | Very mature (7+ years, 9,000+ GitHub stars) | Active |
| `slowapi` | ~20KB | Mature (ported from flask-limiter) | Active |
| `structlog` | ~100KB | Very mature (10+ years, 3,500+ stars) | Active |
| `pybreaker` | ~15KB | Mature (5+ years) | Low activity (stable) |

> :warning: **Risk:** `pybreaker` has low maintenance activity. The custom `CircuitBreaker` implementation (~80 lines, shown above) is recommended instead -- it avoids a dependency for a straightforward pattern and integrates directly with the TX/interceptor model.

### 5.3 What Could Go Wrong

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Retry logic creates duplicate grants | Medium | Idempotency keys on create (URL-based dedup) |
| Circuit breaker too aggressive | Low | Conservative defaults (5 failures, 60s recovery) |
| Structured logging migration breaks existing log parsing | Low | Incremental: add structlog alongside, don't remove stdlib |
| Rate limiter blocks legitimate bulk operations | Medium | Per-user limits, admin bypass |
| Graceful shutdown timeout too short | Low | Configurable timeout, default 30s |

---

## 6. ROI Analysis

### 6.1 Investment vs Return

| Investment | Estimated effort | Return |
|-----------|-----------------|--------|
| Error classification + propagation | 2-3 hours | Every future debugging session is 3x faster |
| Retry logic (tool + agent) | 3-4 hours | 90% reduction in failed runs from transient errors |
| Circuit breakers | 3-4 hours | Prevents token burn when external services are down |
| Rate limiting | 3-4 hours | DoS protection + LLM cost control |
| SQLite hardening | 1-2 hours | Eliminates "database is locked" under concurrent load |
| Health endpoints | 1 hour | Container orchestrator compatibility |
| Structured logging | 4-6 hours | Operational visibility, incident response time halved |
| Graceful shutdown | 2-3 hours | No orphaned agent runs on deploy |
| SSRF prevention | 1-2 hours | Eliminates a class of security vulnerabilities |
| **Total** | **20-30 hours** | **Production-grade reliability** |

### 6.2 What You Get for 20-30 Hours

```
Before:                              After:

Agent fails silently      -->        Classified error in structured JSON log
Nobody knows for hours               Alert fires in minutes

Retry? Hope the LLM       -->        Tenacity retries with backoff
  does it on its own                 Circuit breaker stops beating dead horse

grants.gov down =         -->        Circuit opens after 5 failures
  burn $50 in tokens                 Agent told "service unavailable"

"database is locked"      -->        WAL + IMMEDIATE + 10s timeout
  kills agent run                    Concurrent reads/writes just work

Deploy = kill active      -->        Graceful shutdown drains runs
  agent runs                         30s grace period, then force-cancel

What happened? grep       -->        structlog JSON + correlation IDs
  through 10 files                   One query shows entire run trace
```

### 6.3 Comparison: Build vs Buy vs Defer

| Approach | Pros | Cons |
|----------|------|------|
| **Build now (recommended)** | Full control, fits architecture, ~25 hours | Engineering time |
| **Use managed service (e.g., Prefect)** | [Prefect + Pydantic AI integration](https://www.prefect.io/blog/prefect-pydantic-integration) exists | Added dependency, cost, complexity |
| **Defer to post-launch** | Ship faster | First outage burns trust; retrofitting is harder |

---

## 7. Trade-offs and Alternatives

### 7.1 Over-Engineering Risks

| Pattern | When it's over-engineering | When it's necessary |
|---------|--------------------------|-------------------|
| Distributed circuit breakers (Redis-backed) | Single instance deployment | Multi-instance with shared state |
| OpenTelemetry full stack | No observability platform | Datadog/Grafana stack in place |
| Saga pattern for agent runs | Simple sequential workflows | Multi-agent coordination with partial rollback |
| Redis rate limiting backend | Single server, < 100 req/s | Multi-server, > 1000 req/s |
| Prometheus metrics | No monitoring infrastructure | Grafana dashboard exists |

**For the Grant Watcher at launch scale**, the in-memory implementations (circuit breaker, rate limiter) are sufficient. Redis-backed versions are a future upgrade, not a launch requirement.

### 7.2 Framework Alignment

Every proposed pattern uses existing N3TX primitives:

| Pattern | N3TX primitive used |
|---------|--------------------|
| Circuit breaker | `actor.use(interceptor, on='inbox')` -- same as auth |
| Rate limiting | `api.use(interceptor, on='request')` -- same as auth |
| Error classification | `TX.error(message, code)` -- existing API |
| Retry (tool level) | Pydantic AI `Tool(retries=N)` -- existing |
| Health checks | FastAPI route -- standard |
| Graceful shutdown | FastAPI lifespan -- standard |
| Structured logging | Replace `logging.getLogger()` calls -- non-breaking |

> :bulb: **Key Insight:** None of these patterns require new N3TX abstractions. The interceptor system was designed for exactly this: layering cross-cutting concerns (auth, rate limiting, circuit breaking) without modifying handler code. This is framework alignment, not framework extension.

### 7.3 What NOT to Build

| Don't build | Why not |
|------------|---------|
| Custom retry library | Tenacity exists, is battle-tested |
| Custom rate limiter middleware | SlowAPI exists, integrates with FastAPI |
| Agent run persistence/replay | Prefect does this; only build if needed |
| Full observability stack | Ship logs first, add metrics later if needed |
| Database write queue | SQLite WAL + IMMEDIATE handles single-instance fine |

---

## 8. Implementation Priority and Phasing

### Phase 1: Critical Safety (Days 1-2, ~8 hours)

| Priority | What | Why first |
|----------|------|-----------|
| P0 | SSRF prevention in `WebTools.scrape()` | Security vulnerability, zero tolerance |
| P0 | Error classification in `tools.py` | Foundation for everything else |
| P0 | SQLite pragma improvements | One-line changes, immediate reliability gain |
| P1 | Tenacity on `WebTools.scrape()` | Most common failure path |
| P1 | Health check endpoints | Operational baseline |

### Phase 2: Resilience (Days 3-4, ~10 hours)

| Priority | What | Why second |
|----------|------|-----------|
| P1 | Circuit breaker for external services | Prevents token burn during outages |
| P1 | Rate limiting (API + agent runs) | DoS protection + cost control |
| P1 | Pydantic AI tool retries (configure `retries=` param) | Built-in, just needs wiring |
| P1 | Idempotent grant creation | Prevents duplicates from retries |

### Phase 3: Observability (Days 5-7, ~12 hours)

| Priority | What | Why third |
|----------|------|-----------|
| P2 | Structured logging migration | Long-term operational value |
| P2 | Graceful shutdown | Deploy safety |
| P2 | Agent run correlation IDs | Debugging at scale |
| P2 | Agent task input validation | Defense-in-depth |

---

## 9. Recommendation

**Go. Priority: High. Start with Phase 1 immediately.**

Production hardening is **not optional for an agentic application**. Unlike a CRUD app where a failed request returns a 500 and the user retries, a failed agent run wastes LLM tokens, misses grant deadlines, and erodes trust in the system's autonomous capabilities. The [AWS Prescriptive Guidance on Operationalizing Agentic AI](https://docs.aws.amazon.com/pdfs/prescriptive-guidance/latest/strategy-operationalizing-agentic-ai/strategy-operationalizing-agentic-ai.pdf) explicitly lists error handling, retry logic, and circuit breakers as **required** operational controls for agentic systems.

The total investment is **20-30 engineering hours** spread across three phases. Phase 1 (8 hours) addresses the most critical gaps -- security, error handling, and database reliability. This is the kind of work that costs 8 hours now or 80 hours later when debugging a production incident with no structured logs and no error classification.

The architecture is ready. The interceptor pattern supports resilience layers. The TX error protocol provides the error channel. The `constraints` field on `AgentActor` provides the configuration point. This is implementation work, not design work.

---

## :link: Sources

1. [FastAPI Error Handling Patterns -- Better Stack](https://betterstack.com/community/guides/scaling-python/error-handling-fastapi/)
2. [Production-Grade Logging for FastAPI Applications -- Medium, Feb 2026](https://medium.com/@laxsuryavanshi.dev/production-grade-logging-for-fastapi-applications-a-complete-guide-f384d4b8f43b)
3. [How to Build Production-Ready FastAPI Applications -- OneUptime, Jan 2026](https://oneuptime.com/blog/post/2026-01-26-fastapi-production-ready/view)
4. [PyBreaker -- Python Circuit Breaker (GitHub)](https://github.com/danielfm/pybreaker)
5. [Building Resilient Python Applications with Tenacity](https://www.amitavroy.com/articles/building-resilient-python-applications-with-tenacity-smart-retries-for-a-fail-proof-architecture)
6. [SlowAPI: Mastering Rate Limiting in FastAPI -- Medium, Jan 2026](https://shiladityamajumder.medium.com/using-slowapi-in-fastapi-mastering-rate-limiting-like-a-pro-19044cb6062b)
7. [Rate Limiting AI APIs with Async Middleware in FastAPI 2026](https://dasroot.net/posts/2026/02/rate-limiting-ai-apis-async-middleware-fastapi-redis/)
8. [Pydantic AI -- HTTP Request Retries](https://ai.pydantic.dev/retries/)
9. [Pydantic AI -- Tool Retries and ModelRetry](https://ai.pydantic.dev/api/tools/)
10. [Build AI Agents That Resume from Failure with Pydantic AI + Prefect](https://www.prefect.io/blog/prefect-pydantic-integration)
11. [SQLite Busy Timeout -- Bert Hubert](https://berthub.eu/articles/posts/a-brief-post-on-sqlite3-database-locked-despite-timeout/)
12. [Your SQLite Connection Pool Might Be Ruining Write Performance](https://emschwartz.me/psa-your-sqlite-connection-pool-might-be-ruining-your-write-performance/)
13. [How to Set Up SQLite for Production Use -- OneUptime, Feb 2026](https://oneuptime.com/blog/post/2026-02-02-sqlite-production-setup/view)
14. [Why Multi-Agent LLM Systems Fail -- Galileo](https://galileo.ai/blog/multi-agent-llm-systems-fail)
15. [Why Your AI Agent Works in Demo But Fails in Production -- DEV](https://dev.to/dingomanhammer/why-your-ai-agent-works-in-demo-but-fails-in-production-4e51)
16. [Operationalizing Agentic AI -- AWS Prescriptive Guidance](https://docs.aws.amazon.com/pdfs/prescriptive-guidance/latest/strategy-operationalizing-agentic-ai/strategy-operationalizing-agentic-ai.pdf)
17. [OWASP SSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)
18. [structlog -- Complete Guide (SigNoz)](https://signoz.io/guides/structlog/)
19. [Setting Up Structured Logging in FastAPI with structlog](https://ouassim.tech/notes/setting-up-structured-logging-in-fastapi-with-structlog/)
20. [FastAPI Health Check Endpoint -- Best Practices](https://www.index.dev/blog/how-to-implement-health-check-in-python)
21. [FastAPI Lifespan Events (Official Docs)](https://fastapi.tiangolo.com/advanced/events/)
22. [Prometheus FastAPI Instrumentator (GitHub)](https://github.com/trallnag/prometheus-fastapi-instrumentator)
23. [Python Retry Policies with Tenacity: Jitter, Backoff, and Idempotency -- Medium, Dec 2025](https://medium.com/@hadiyolworld007/python-retry-policies-with-tenacity-jitter-backoff-and-idempotency-that-survives-chaos-12bba4fc8d32)
24. [Handling Tool Errors and Agent Recovery -- APXML](https://apxml.com/courses/langchain-production-llm/chapter-2-sophisticated-agents-tools/agent-error-handling)
25. [ReliabilityBench: Evaluating LLM Agent Reliability -- arXiv 2601.06112](https://arxiv.org/pdf/2601.06112)
