# Sprint 1: Production Safety + Observability

**Sprint Duration:** ~5 days
**Branch:** `v0.9` (current)
**Wave Tag:** `[0.10]`

---

## Sprint Goal

Every agent run is persistently recorded with cost, tool traces, and full message history. The web scraping path is hardened against SSRF. SQLite is tuned for concurrent agent workloads. Tool call errors are classified for intelligent retry behavior.

---

## Dependency Graph

```
Phase A: Safety (independent, can all start Day 1)
  A1: SSRF prevention          ─── no dependencies
  A2: SQLite pragma improvements ── no dependencies
  A3: Error classification      ─── no dependencies

Phase B: AgentRun Model (starts Day 1-2, independent of Phase A)
  B1: AgentRun model definition  ── no dependencies
  B2: Join model registration    ── depends on B1

Phase C: Tracing + Cost (starts Day 2-3, depends on B1)
  C1: Cost estimation module     ── no dependencies
  C2: Trace interceptor          ── no dependencies (uses existing use() API)
  C3: Instrument agent_run()     ── depends on B1, C1, C2

Phase D: Integration + Tests (starts Day 3-5, depends on everything)
  D1: Unit tests                 ── depends on A1, A2, A3, B1, C1, C2
  D2: Integration tests          ── depends on B2, C3
  D3: Documentation updates      ── depends on all above
```

---

## Phase A: Safety (Day 1, ~4 hours)

Three independent tasks with no cross-dependencies. Can be done in parallel or in any order.

### Task A1: SSRF Prevention in WebTools.scrape()

**Estimated time:** 1.5 hours
**Risk:** Low (pure Python, no framework changes)
**Category:** Security hardening (application code)

**Problem:** `WebTools.scrape()` accepts any URL and follows redirects. An LLM agent could be tricked into requesting `http://169.254.169.254/latest/meta-data/` (cloud metadata endpoint) or internal network addresses.

**Files created:**
- `/workspace/example_grants/utils/__init__.py` (empty)
- `/workspace/example_grants/utils/security.py`

**Files modified:**
- `/workspace/example_grants/models/web_tools.py`

#### A1.1: Create `example_grants/utils/security.py`

This is **application code**, not framework code. SSRF prevention is specific to apps that do server-side HTTP requests. Other N3TX apps (e.g., a blog) have no scraping and need no SSRF guard.

```python
# example_grants/utils/security.py

import ipaddress
import socket
from urllib.parse import urlparse

_BLOCKED_RANGES = [
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
    ipaddress.ip_network('127.0.0.0/8'),
    ipaddress.ip_network('169.254.0.0/16'),   # Link-local / cloud metadata
    ipaddress.ip_network('0.0.0.0/8'),
    ipaddress.ip_network('::1/128'),
    ipaddress.ip_network('fc00::/7'),          # IPv6 private
]

_ALLOWED_SCHEMES = {'http', 'https'}


def validate_url(url: str) -> str:
    """Validate a URL is safe for server-side requests.

    Raises ValueError if the URL targets internal infrastructure,
    uses a disallowed scheme, or cannot be resolved.
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

**Design decisions:**
- Lives in `example_grants/utils/`, not in `src/n3tx/core/`. SSRF is an application concern, not a framework concern. A different N3TX app might have different blocked ranges or no scraping at all.
- DNS resolution happens at validation time, not at request time. This prevents DNS rebinding attacks where a hostname resolves to a safe IP during validation but a blocked IP during the actual request. For full protection, `httpx` would need a custom `AsyncResolver` that re-validates on redirect -- but that is a Phase 2 enhancement, not Sprint 1 scope.
- The function raises `ValueError`, which the existing `exception_to_tx_error()` in `tx.py` maps to HTTP 400. The agent sees a clear error message and can try a different URL.

#### A1.2: Modify `example_grants/models/web_tools.py`

Add a single import and a single line at the top of `scrape()`:

```python
# At the top of scrape(), before the httpx call:
from utils.security import validate_url
url = validate_url(url)  # Raises ValueError on blocked URLs
```

**Exact change location:** Line 17 of `web_tools.py`, before the `import httpx` line inside `scrape()`.

The modified `scrape()` method:
```python
@expose_route('/scrape', methods=['POST'], access=AUTHENTICATED)
async def scrape(self, url: str) -> dict:
    """Fetch a URL and return its HTML content."""
    from utils.security import validate_url
    url = validate_url(url)
    import httpx
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        resp = await client.get(url)
    return {'url': url, 'status': resp.status_code, 'html': resp.text[:50000]}
```

---

### Task A2: SQLite Pragma Improvements

**Estimated time:** 0.5 hours
**Risk:** Low (config changes only, proven SQLite best practices)
**Category:** Framework enhancement (minimal, additive)

**Problem:** Current pragmas use `busy_timeout=5000` and default `synchronous=FULL`. Agent runs can hold connections longer than 5 seconds, and WAL mode is safe with `synchronous=NORMAL` for a 2-3x write performance improvement.

**Files modified:**
- `/workspace/src/n3tx/core/storage/sqlite_storage.py`

#### A2.1: Update `__init__()` pragmas

**Exact change location:** Lines 68-69 of `sqlite_storage.py`. After the existing `PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=5000` lines.

Replace:
```python
init_conn.execute("PRAGMA journal_mode=WAL")
init_conn.execute("PRAGMA busy_timeout=5000")
```

With:
```python
init_conn.execute("PRAGMA journal_mode=WAL")
init_conn.execute("PRAGMA busy_timeout=10000")
init_conn.execute("PRAGMA synchronous=NORMAL")
init_conn.execute("PRAGMA cache_size=-64000")
```

**Rationale:**
- `busy_timeout=10000`: Agent runs can hold DB connections for several seconds. 10s timeout prevents `SQLITE_BUSY` errors during concurrent agent activity without excessive waiting.
- `synchronous=NORMAL`: With WAL mode, `NORMAL` is safe (WAL journal provides crash recovery). Eliminates unnecessary fsync per transaction. Proven best practice per SQLite docs and production deployment guides.
- `cache_size=-64000`: 64MB page cache (negative value = kilobytes). Reduces disk I/O for repeated queries on the same tables. Default is ~2MB which is too small for agent workloads that scan multiple tables per run.

#### A2.2: Update `_get_conn()` pragmas

**Exact change location:** Line 78 of `sqlite_storage.py`. The `_get_conn()` method creates new connections when the pool is empty and only sets `busy_timeout`.

Replace:
```python
conn.execute("PRAGMA busy_timeout=5000")
```

With:
```python
conn.execute("PRAGMA busy_timeout=10000")
conn.execute("PRAGMA synchronous=NORMAL")
conn.execute("PRAGMA cache_size=-64000")
```

New connections created outside the init path must also get the same pragmas. WAL mode is set at the file level so it persists, but `busy_timeout`, `synchronous`, and `cache_size` are per-connection.

---

### Task A3: Error Classification in tools.py

**Estimated time:** 2 hours
**Risk:** Low (additive, existing code path enhanced)
**Category:** Framework enhancement (agents package)

**Problem:** `_route_tool_call()` in `tools.py` raises `ModelRetry` with a generic message for all error TXs (line 196). The LLM cannot distinguish between a transient timeout (retry) and a permanent 404 (stop trying). This wastes tokens on futile retries and misses recoverable errors.

**Files created:**
- `/workspace/src/n3tx/core/agents/errors.py`

**Files modified:**
- `/workspace/src/n3tx/core/agents/tools.py` (lines 194-196)

#### A3.1: Create `src/n3tx/core/agents/errors.py`

```python
"""Error classification for agent tool calls.

Classifies TX error responses into transient/permanent/resource categories
to inform retry decisions. The LLM receives category-aware error messages
that help it decide whether to retry, try a different approach, or give up.
"""

from n3tx.core.actors.tx import TX


class AgentError(Exception):
    """Base for agent-specific errors with retry semantics."""
    retryable: bool = False
    category: str = 'unknown'

    def __init__(self, message: str, code: int = 500):
        super().__init__(message)
        self.code = code


class TransientError(AgentError):
    """Network timeout, temporary unavailability, server error."""
    retryable = True
    category = 'transient'


class PermanentError(AgentError):
    """Invalid data, not found, validation failure, auth failure."""
    retryable = False
    category = 'permanent'


class ResourceError(AgentError):
    """Rate limit, quota exceeded, service overloaded."""
    retryable = True  # After backoff
    category = 'resource'


def classify_tx_error(tx: TX) -> AgentError:
    """Classify a TX error response for retry decisions.

    Maps HTTP-style status codes from TX.data['code'] to error categories.
    The TX error protocol (tx.error(message, code)) already carries these.
    """
    data = tx.data if isinstance(tx.data, dict) else {}
    code = data.get('code', 500)
    message = data.get('message', str(tx.data))

    if code == 429:
        return ResourceError(message, code)
    if code in (408, 502, 503, 504):
        return TransientError(message, code)
    if code in (400, 401, 403, 404, 409, 422):
        return PermanentError(message, code)
    # Default: assume transient (better to retry once too many than miss a recovery)
    return TransientError(message, code)
```

**Design decisions:**
- Three concrete subclasses, not an enum. This allows `isinstance` checks and can carry additional context in the future (e.g., `retry_after` on `ResourceError`).
- `classify_tx_error()` takes a TX, not raw args. This keeps the interface aligned with the TX protocol -- callers already have the error TX.
- Default to transient. Rationale: Pydantic AI's `retries` parameter limits the total retry count anyway. It's better to give a transient error a second chance than to prematurely declare it permanent.

#### A3.2: Modify `_route_tool_call()` in `tools.py`

**Exact change location:** Lines 194-196 of `tools.py`.

Replace:
```python
    if response.is_error:
        from pydantic_ai import ModelRetry
        raise ModelRetry(response.data.get('message', 'Tool call failed'))
```

With:
```python
    if response.is_error:
        from pydantic_ai import ModelRetry
        from n3tx.core.agents.errors import classify_tx_error
        error = classify_tx_error(response)
        if error.retryable:
            raise ModelRetry(
                f"[{error.category}] {error}. "
                f"This may be temporary — try again or use a different approach."
            )
        else:
            raise ModelRetry(
                f"[permanent] {error}. "
                f"Do NOT retry this exact operation — the error will not resolve."
            )
```

**Why still `ModelRetry` for permanent errors?** Pydantic AI uses `ModelRetry` to communicate tool errors back to the LLM. Even for permanent errors, the LLM needs to know what happened so it can adjust strategy. The `[permanent]` prefix and explicit instruction not to retry guides the LLM's behavior. The actual retry count is controlled by Pydantic AI's `retries` parameter on the `Tool` object.

---

## Phase B: AgentRun Model (Day 1-2, ~3 hours)

### Task B1: AgentRun Model Definition

**Estimated time:** 2 hours
**Risk:** Low (follows exact pattern of AgentActor model)
**Category:** Application code (example_grants/)

**Files created:**
- `/workspace/example_grants/models/agent_run.py`

**Files modified:**
- `/workspace/example_grants/models/__init__.py`

#### B1.1: Create `example_grants/models/agent_run.py`

This model follows the **exact same patterns** as:
- `AgentActor` in `/workspace/src/n3tx/core/agents/actor.py` for JSON field serialization (`_JSON_FIELDS`, `_storage_dict`, `@model_validator`)
- `Grant` in `/workspace/example_grants/models/grant.py` for field declarations with Widget types
- `ActorModel` base class for actor capabilities

```python
"""AgentRun -- Persistent record of a single agent execution.

Every time an agent runs (POST /agents/{id}/run), an AgentRun record captures
the full context: what was asked, what tools were called, what it cost,
and what the answer was. This provides audit trail, cost tracking, and
debugging data without any UI code -- the schema-driven frontend renders
it automatically.
"""
from __future__ import annotations

import json
from typing import ClassVar, Optional

from pydantic import Field, model_validator

from n3tx.core.models.actor_model import ActorModel
from n3tx.core.authorize import AUTHENTICATED, ROLE
from n3tx.core.widgets import DateTimeField, TextareaField, CurrencyField

_JSON_FIELDS = ('tool_calls', 'messages')


class AgentRun(ActorModel):
    """Persistent record of a single agent execution."""

    __tablename__: ClassVar[str] = 'agent_runs'
    __storable__: ClassVar[bool] = True
    __access__: ClassVar[dict] = {
        'read': AUTHENTICATED,
        'create': AUTHENTICATED,
        'update': ROLE('admin'),
        'delete': ROLE('admin'),
    }
    __ui__: ClassVar[dict] = {
        'field_order': [
            'agent_id', 'task', 'status', 'model_used',
            'duration_ms', 'estimated_cost', 'total_tokens',
        ],
        'groups': {
            'Overview': ['agent_id', 'task', 'status', 'model_used'],
            'Timing': ['started_at', 'completed_at', 'duration_ms'],
            'Cost': [
                'input_tokens', 'output_tokens', 'total_tokens',
                'requests', 'estimated_cost',
            ],
            'Result': ['answer', 'error'],
            'Trace': ['tool_calls', 'messages'],
        },
    }

    agent_id: int = Field(description="FK to the agent that ran")
    task: str = Field(default='', description="User prompt / task")
    status: str = Field(
        default='running',
        description="running | completed | failed | cancelled",
    )
    started_at: Optional[DateTimeField] = Field(default=None)
    completed_at: Optional[DateTimeField] = Field(default=None)
    duration_ms: int = Field(default=0, description="Wall-clock duration in milliseconds")
    answer: TextareaField = Field(default='')
    error: str = Field(default='')
    model_used: str = Field(default='')
    input_tokens: int = Field(default=0)
    output_tokens: int = Field(default=0)
    total_tokens: int = Field(default=0)
    estimated_cost: CurrencyField = Field(default=0.0)
    requests: int = Field(default=0, description="Number of LLM API requests")
    tool_calls: list = Field(default=[],
                             json_schema_extra={'ui': {'display': False}})
    messages: list = Field(default=[],
                           json_schema_extra={'ui': {'display': False}})
    user_id: int = Field(default=0)

    @model_validator(mode='before')
    @classmethod
    def _deserialize_json_fields(cls, data):
        """Deserialize JSON TEXT strings from SQLite back to Python objects."""
        if isinstance(data, dict):
            for field in _JSON_FIELDS:
                val = data.get(field)
                if isinstance(val, str):
                    try:
                        data[field] = json.loads(val)
                    except (json.JSONDecodeError, TypeError):
                        pass
        return data

    def _storage_dict(self, exclude_unset: bool = True) -> dict:
        """Serialize list fields to JSON strings for SQLite storage."""
        d = super()._storage_dict(exclude_unset=exclude_unset)
        for field in _JSON_FIELDS:
            if field in d and not isinstance(d[field], str):
                d[field] = json.dumps(d[field], default=str)
        return d

    @classmethod
    def update(cls, id, data):
        """Serialize JSON fields before storage update."""
        from pydantic import BaseModel
        if isinstance(data, BaseModel):
            data_dict = data.model_dump(exclude_unset=True)
        elif isinstance(data, dict):
            data_dict = dict(data)
        else:
            data_dict = data
        for field in _JSON_FIELDS:
            if field in data_dict and not isinstance(data_dict[field], str):
                data_dict[field] = json.dumps(data_dict[field], default=str)
        return super().update(id, data_dict)
```

**Design decisions:**
- `tool_calls` and `messages` have `ui.display: False`. These are large JSON blobs useful for debugging/API consumers but not for the default list view. They are still accessible in the detail view and via API.
- `user_id` is a plain `int`, not a `User` FK. Agent runs can be triggered by the system (scheduler, webhook) without a user context. A `Ref[User]` would require a valid FK, which is not always available.
- `agent_id` is a plain `int`, not a `Ref[AgentActor]`. The join model (`AgentActorAgentRun`) handles the relationship. The field is for querying ("which agent produced this run?"), not for FK hydration.
- The `update()` override follows the exact same pattern as `AgentActor.update()` (lines 90-102 of actor.py). This is necessary because `StorableMixin.update()` receives a raw dict, not a model instance, so the `_storage_dict()` hook is not invoked.

#### B1.2: Update `example_grants/models/__init__.py`

Add `AgentRun` to the package exports:

```python
from .user import User
from .grant import Grant
from .source import Source
from .web_tools import WebTools
from .agent_run import AgentRun

__all__ = ["User", "Grant", "Source", "WebTools", "AgentRun"]
```

---

### Task B2: Join Model Registration

**Estimated time:** 1 hour
**Risk:** Low (follows exact existing pattern)
**Category:** Application code (example_grants/)

**Files modified:**
- `/workspace/example_grants/main.py`
- `/workspace/example_grants/tests/conftest.py`

#### B2.1: Update `example_grants/main.py`

**Exact change location:** Lines 27 and 35-37.

Add import:
```python
from models import User, Grant, Source, WebTools
```
becomes:
```python
from models import User, Grant, Source, WebTools, AgentRun
```

Update `create_app()` call:
```python
app = create_app(
    models=[User, Grant, Source, WebTools, AgentTool, AgentActor, AgentRun],
    join_models=[(AgentActor, AgentTool), (AgentActor, AgentRun)],
    # ... rest unchanged
)
```

This generates:
- `AgentActorAgentRun` join model with `agentactor_id` FK column
- `GET /AgentRun` -- schema endpoint
- `GET /agent_runs` -- list all runs (paginated)
- `GET /agent_runs/{id}` -- single run detail
- `GET /agents/{agent_id}/agent_runs` -- runs for a specific agent (nested route via join)
- Frontend: `<ntx-list model="AgentRun">` renders browsable run history automatically

#### B2.2: Update test conftest.py

**Exact change location:** Line 51 of `conftest.py`.

Add import:
```python
from models import User, Grant, Source, WebTools
```
becomes:
```python
from models import User, Grant, Source, WebTools, AgentRun
```

No other conftest changes needed -- the model is registered via `main.py` import, and tests create AgentRun records directly in the test functions.

---

## Phase C: Tracing + Cost (Day 2-3, ~6 hours)

### Task C1: Cost Estimation Module

**Estimated time:** 1 hour
**Risk:** Low (pure function, static data, no dependencies)
**Category:** Application code (example_grants/)

**Files created:**
- `/workspace/example_grants/agents/__init__.py` (empty)
- `/workspace/example_grants/agents/pricing.py`

#### C1.1: Create `example_grants/agents/pricing.py`

```python
"""Cost estimation for LLM API usage.

Static pricing table + pure function. Update PRICING when providers change rates.
Costs are estimates -- actual billing may differ due to caching, batching, etc.
"""

# Per-million-token rates (USD). Source: provider pricing pages, March 2026.
PRICING = {
    'anthropic:claude-sonnet-4-5-20250929': {'input': 3.00, 'output': 15.00},
    'anthropic:claude-opus-4-6':            {'input': 5.00, 'output': 25.00},
    'anthropic:claude-haiku-3-5':           {'input': 0.25, 'output': 1.25},
    'openai:gpt-5.2':                       {'input': 1.75, 'output': 14.00},
    'openai:gpt-4o-mini':                   {'input': 0.15, 'output': 0.60},
    'google:gemini-2.5-pro':                {'input': 1.25, 'output': 10.00},
    'google:gemini-2.5-flash-lite':         {'input': 0.10, 'output': 0.40},
}

# Conservative default for unknown models
_DEFAULT = {'input': 3.00, 'output': 15.00}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD for a given model and token count.

    Returns 0.0 for local models (ollama:*) and test models.
    Returns a conservative estimate for unknown cloud models.
    """
    if not model or model.startswith('ollama:') or model == 'test':
        return 0.0

    rates = PRICING.get(model, _DEFAULT)
    cost = (
        (input_tokens * rates['input'] / 1_000_000) +
        (output_tokens * rates['output'] / 1_000_000)
    )
    return round(cost, 6)
```

**Design decisions:**
- Application code, not framework code. Different apps use different models. The pricing table is specific to Grant Watcher's likely model selection.
- Returns `float`, not `Decimal`. We are estimating, not accounting. Six decimal places is more than sufficient for dollar amounts.
- `model == 'test'` returns 0.0: Pydantic AI's `TestModel` is used in tests. Charging zero for test runs avoids polluting cost aggregates.

---

### Task C2: Trace Interceptor

**Estimated time:** 1.5 hours
**Risk:** Low (uses existing `use()` API, passive interceptor)
**Category:** Application code (example_grants/)

**Architectural decision:** Where does the trace interceptor live?

**Options:**
1. `src/n3tx/core/agents/tracing.py` (framework code)
2. `example_grants/agents/tracing.py` (application code)

**Recommendation: Option 2 (application code).** Tracing into an AgentRun record is specific to apps that have an AgentRun model. The framework provides the hook (`use()` on NetworkAdapter); the app provides the implementation. If a second app needs tracing, we can extract a generic tracing hook into the framework later. Per N3TX philosophy: "premature abstraction adds indirection without value."

**Files created:**
- `/workspace/example_grants/agents/tracing.py`

#### C2.1: Create `example_grants/agents/tracing.py`

```python
"""Tool call trace interceptor for agent runs.

Creates paired request/inbox interceptors that capture the full lifecycle
of every tool call during an agent run. The interceptors are registered on
the transient NetworkAdapter via adapter.use().

Usage:
    on_req, on_inbox, traces = create_trace_interceptor()
    adapter.use(on_req, on='request')
    adapter.use(on_inbox, on='inbox')
    # ... run agent ...
    # traces now contains [{tool, args, result, duration_ms, success}, ...]
"""

import time
from n3tx.core.actors.tx import TX


def create_trace_interceptor():
    """Factory: creates paired interceptors + shared trace accumulator.

    Returns:
        (on_request, on_inbox, traces)
        - on_request: async interceptor for adapter.use(fn, on='request')
        - on_inbox: async interceptor for adapter.use(fn, on='inbox')
        - traces: list that accumulates tool call records during the run
    """
    traces = []
    pending = {}  # tx.uuid -> {tool, args, start_time}

    async def on_request(tx: TX) -> TX:
        """Record tool call start time and arguments."""
        pending[tx.uuid] = {
            'tool': f'{tx.target}_{tx.name}',
            'args': _safe_serialize(tx.data),
            'start_time': time.monotonic(),
        }
        return tx  # Pass through unchanged -- tracing is passive

    async def on_inbox(tx: TX) -> TX:
        """Match reply to original request, record result and duration."""
        reply_to = tx.meta.get('in_reply_to')
        if reply_to and reply_to in pending:
            start_info = pending.pop(reply_to)
            elapsed_ms = int((time.monotonic() - start_info['start_time']) * 1000)
            traces.append({
                'tool': start_info['tool'],
                'args': start_info['args'],
                'result': _safe_serialize(
                    tx.data if not tx.is_error else {'error': tx.data}
                ),
                'duration_ms': elapsed_ms,
                'success': not tx.is_error,
            })
        return tx  # Pass through unchanged

    return on_request, on_inbox, traces


def _safe_serialize(data) -> dict | list | str:
    """Ensure data is JSON-serializable. Truncate large values."""
    if data is None:
        return {}
    if isinstance(data, (dict, list)):
        # Truncate large string values to avoid bloating the trace
        import json
        serialized = json.dumps(data, default=str)
        if len(serialized) > 10000:
            return {'_truncated': True, '_size': len(serialized),
                    '_preview': serialized[:500]}
        return data
    return str(data)
```

**Design decisions:**
- **Closure pattern.** The `traces` list and `pending` dict are scoped to the run via the closure. No global state. Multiple concurrent agent runs each get their own interceptor + trace list. This is critical for correctness.
- **Passive interceptors.** Both `on_request` and `on_inbox` always return the TX unchanged. They never modify data or return error TXs. The tracing system is invisible to the tool call path.
- **`_safe_serialize()` truncation.** Web scraping results can be 50KB+. Storing full HTML in the trace would bloat the DB. Truncate to 10KB per value with a preview. The full result is still in the `messages` field (Pydantic AI's message history).
- **`time.monotonic()`** for duration measurement. Unlike `time.time()`, monotonic clocks are not affected by NTP adjustments. Correct for measuring elapsed time within a process.

---

### Task C3: Instrument agent_run() — Wire Tracing and Recording

**Estimated time:** 3.5 hours
**Risk:** Medium (touches the critical execution path)
**Category:** Split between framework (minimal) and application (substantial)

This is the most complex task. It requires:
1. A small framework-level change to `mixin.py` to expose trace hooks and richer return data
2. An application-level wrapper in `AgentActor.run()` to create/update AgentRun records

**Files modified:**
- `/workspace/src/n3tx/core/agents/mixin.py` (framework — minimal change)
- `/workspace/src/n3tx/core/agents/actor.py` (application pattern — override `run()`)

**Architectural decision: Where does the instrumentation logic live?**

**Options:**
1. Modify `agent_run()` in `mixin.py` to accept optional tracing hooks and return richer data
2. Override `AgentActor.run()` in the Grant Watcher app to wrap the call with recording

**Recommendation: Both, minimally.**
- `mixin.py` gets a **callback hook** for trace interceptor registration (2 lines) and returns `all_messages()` in the result dict.
- `AgentActor.run()` in `/workspace/src/n3tx/core/agents/actor.py` gets the instrumentation wrapper that creates/updates AgentRun records.

Since `AgentActor` is currently framework code (lives in `src/n3tx/core/agents/`), and the instrumentation is tightly coupled to the agent execution flow, the recording logic lives in the `run()` method override. If `AgentActor` is eventually moved to example_grants, the instrumentation moves with it.

#### C3.1: Modify `mixin.py` — Add trace hook and richer return

**Exact changes to `/workspace/src/n3tx/core/agents/mixin.py`:**

1. Add `on_adapter_created` callback parameter to `agent_run()`:

   **Line 39** — change the signature:
   ```python
   async def agent_run(self, prompt: str, tools: list, task: str,
                       user: dict = None, **kwargs) -> dict:
   ```
   becomes:
   ```python
   async def agent_run(self, prompt: str, tools: list, task: str,
                       user: dict = None, on_adapter_created=None,
                       **kwargs) -> dict:
   ```

2. After `root.register(adapter)` (line 95), add the callback invocation:

   ```python
   root.register(adapter)

   # Hook for tracing: caller can register interceptors on the adapter
   if on_adapter_created:
       on_adapter_created(adapter)
   ```

3. Enrich the return dict (lines 132-140) to include `all_messages()` serialized:

   Replace:
   ```python
   usage = result.usage()
   return {
       'answer': result.output,
       'usage': {
           'input_tokens': usage.input_tokens,
           'output_tokens': usage.output_tokens,
           'requests': usage.requests,
       },
       'messages': len(result.all_messages()),
   }
   ```

   With:
   ```python
   usage = result.usage()
   return {
       'answer': result.output,
       'usage': {
           'input_tokens': usage.input_tokens,
           'output_tokens': usage.output_tokens,
           'requests': usage.requests,
       },
       'messages': len(result.all_messages()),
       'message_history': _serialize_messages(result.all_messages()),
   }
   ```

4. Add the `_serialize_messages()` helper at module level (after the class):

   ```python
   def _serialize_messages(messages) -> list:
       """Serialize Pydantic AI message objects to plain dicts.

       Handles ModelRequest, ModelResponse, and their part types
       (TextPart, ToolCallPart, ToolReturnPart, ThinkingPart).
       Degrades gracefully for unknown types.
       """
       result = []
       for msg in messages:
           try:
               # Pydantic AI messages are Pydantic models — model_dump() works
               if hasattr(msg, 'model_dump'):
                   result.append(msg.model_dump(mode='json'))
               elif hasattr(msg, '__dict__'):
                   result.append({k: str(v) for k, v in msg.__dict__.items()})
               else:
                   result.append(str(msg))
           except Exception:
               result.append({'_error': 'serialization_failed', '_type': type(msg).__name__})
       return result
   ```

**Why `on_adapter_created` callback instead of always registering tracing?** Because tracing is opt-in. Not every `agent_run()` call needs tracing overhead. The callback pattern lets the caller decide what interceptors to register, preserving the "primitives, not opinions" principle.

#### C3.2: Modify `AgentActor.run()` — Add instrumented recording

**Exact changes to `/workspace/src/n3tx/core/agents/actor.py`:**

The existing `run()` method (lines 138-156) currently calls `agent_run()` and returns the raw JSON result. We wrap it with AgentRun record creation.

Replace lines 138-156:

```python
@expose_route('/run', methods=['POST'])
async def run(self, task: str, **kwargs) -> str:
    """Execute the agent's reasoning loop.

    Args:
        task: The user task / query to execute.
        **kwargs: Passed to agent_run() (e.g., llm, constraints overrides).

    Returns:
        JSON string with {answer, usage, messages}.
    """
    tool_addrs = self.tool_addrs()
    result = await self.agent_run(
        prompt=self.prompt,
        tools=tool_addrs,
        task=task,
        **kwargs,
    )
    return json.dumps(result, default=str)
```

With:

```python
@expose_route('/run', methods=['POST'])
async def run(self, task: str, **kwargs) -> str:
    """Execute the agent's reasoning loop with persistent recording.

    Creates an AgentRun record before execution, captures tool call
    traces via interceptor, and updates the record with results.

    Args:
        task: The user task / query to execute.
        **kwargs: Passed to agent_run() (e.g., llm, constraints overrides).

    Returns:
        JSON string with {answer, usage, messages, run_id}.
    """
    import time as _time
    from datetime import datetime, timezone

    tool_addrs = self.tool_addrs()
    model_used = kwargs.get('llm') or self.llm

    # ── Create run record (optional: only if AgentRun is registered) ──
    run_record = None
    tool_traces = None
    try:
        from n3tx.core.utils.registrar import registered_models
        agent_run_cls = registered_models.get('agent_runs')
        if agent_run_cls:
            run_record = agent_run_cls(
                agent_id=self.id,
                task=task[:5000],  # Truncate very long tasks
                status='running',
                started_at=datetime.now(timezone.utc).isoformat(),
                model_used=str(model_used),
                user_id=(kwargs.get('user') or {}).get('user_id', 0)
                if isinstance(kwargs.get('user'), dict) else 0,
            )
            run_record = agent_run_cls.create(run_record)
    except Exception as e:
        logger.warning("Failed to create AgentRun record: %s", e)
        run_record = None

    start_time = _time.monotonic()

    # ── Set up tracing callback ──
    def _wire_tracing(adapter):
        nonlocal tool_traces
        try:
            from agents.tracing import create_trace_interceptor
        except ImportError:
            return  # Tracing module not available — skip silently
        on_req, on_inbox, traces = create_trace_interceptor()
        adapter.use(on_req, on='request')
        adapter.use(on_inbox, on='inbox')
        tool_traces = traces

    try:
        result = await self.agent_run(
            prompt=self.prompt,
            tools=tool_addrs,
            task=task,
            on_adapter_created=_wire_tracing,
            **kwargs,
        )

        # ── Update run record with results ──
        if run_record and agent_run_cls:
            elapsed_ms = int((_time.monotonic() - start_time) * 1000)
            usage = result.get('usage', {})
            in_tok = usage.get('input_tokens', 0)
            out_tok = usage.get('output_tokens', 0)
            try:
                from agents.pricing import estimate_cost
                cost = estimate_cost(
                    model=str(model_used),
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                )
            except ImportError:
                cost = 0.0

            update_data = {
                'status': 'completed',
                'completed_at': datetime.now(timezone.utc).isoformat(),
                'duration_ms': elapsed_ms,
                'answer': str(result.get('answer', ''))[:50000],
                'input_tokens': in_tok,
                'output_tokens': out_tok,
                'total_tokens': in_tok + out_tok,
                'requests': usage.get('requests', 0),
                'estimated_cost': cost,
                'tool_calls': tool_traces or [],
                'messages': result.get('message_history', []),
            }
            try:
                agent_run_cls.update(run_record.id, update_data)
            except Exception as e:
                logger.warning("Failed to update AgentRun %s: %s",
                               run_record.id, e)

        result['run_id'] = run_record.id if run_record else None
        return json.dumps(result, default=str)

    except Exception as e:
        # ── Record failure ──
        if run_record and agent_run_cls:
            elapsed_ms = int((_time.monotonic() - start_time) * 1000)
            try:
                agent_run_cls.update(run_record.id, {
                    'status': 'failed',
                    'completed_at': datetime.now(timezone.utc).isoformat(),
                    'duration_ms': elapsed_ms,
                    'error': str(e)[:5000],
                    'tool_calls': tool_traces or [],
                })
            except Exception as update_err:
                logger.warning("Failed to record AgentRun failure: %s",
                               update_err)
        raise
```

**Design decisions:**
- **Graceful degradation.** If `AgentRun` is not registered (model not in `registered_models`), the run proceeds without recording. If the tracing module is not importable, the run proceeds without tracing. If the AgentRun create/update fails, the agent run still completes. Recording is best-effort; it must never break the primary execution path.
- **Lookup via `registered_models`** instead of direct import. This avoids a hard dependency on the `AgentRun` class existing. Framework code (`actor.py`) should not import application code (`example_grants/models/agent_run.py`). The `registered_models` dict is the standard way to discover models at runtime.
- **Import `agents.tracing` inside the closure.** This is an application-level module that lives in `example_grants/agents/`. It is importable because `example_grants/` is on `sys.path` when running the Grant Watcher app. Other N3TX apps that don't have an `agents/tracing.py` get a graceful `ImportError` skip.
- **`run_id` in response.** The response now includes the AgentRun record ID so the caller can immediately fetch the full record via `GET /agent_runs/{run_id}`.
- **Truncation.** `task` truncated to 5000 chars, `answer` to 50000, `error` to 5000. Prevents unbounded storage from adversarial inputs.

---

## Phase D: Integration + Tests (Day 3-5, ~6 hours)

### Task D1: Unit Tests

**Estimated time:** 3 hours
**Risk:** Low
**Category:** Tests

**Files created:**
- `/workspace/example_grants/tests/test_ssrf.py`
- `/workspace/example_grants/tests/test_pricing.py`
- `/workspace/example_grants/tests/test_error_classification.py`
- `/workspace/example_grants/tests/test_tracing.py`

#### D1.1: SSRF Prevention Tests — `test_ssrf.py`

```
Tests:
  - test_blocked_localhost: validate_url('http://127.0.0.1/secret') raises ValueError
  - test_blocked_metadata: validate_url('http://169.254.169.254/...') raises ValueError
  - test_blocked_private_10: validate_url('http://10.0.0.1/') raises ValueError
  - test_blocked_private_172: validate_url('http://172.16.0.1/') raises ValueError
  - test_blocked_private_192: validate_url('http://192.168.1.1/') raises ValueError
  - test_blocked_scheme_ftp: validate_url('ftp://example.com') raises ValueError
  - test_blocked_scheme_file: validate_url('file:///etc/passwd') raises ValueError
  - test_blocked_no_hostname: validate_url('http://') raises ValueError
  - test_allowed_public_url: validate_url('https://nsf.gov/grants') returns the URL
  - test_unresolvable_host: validate_url('http://nonexistent.invalid/') raises ValueError
```

Location: `/workspace/example_grants/tests/test_ssrf.py`

These are pure unit tests (no server needed). Import `validate_url` directly.

#### D1.2: Pricing Tests — `test_pricing.py`

```
Tests:
  - test_known_model_cost: estimate_cost('anthropic:claude-sonnet-4-5-20250929', 1_000_000, 1_000_000) == 18.0
  - test_unknown_model_uses_default: estimate_cost('unknown:model', 1_000_000, 0) == 3.0
  - test_ollama_free: estimate_cost('ollama:llama3.1', 999999, 999999) == 0.0
  - test_test_model_free: estimate_cost('test', 100, 100) == 0.0
  - test_zero_tokens: estimate_cost('anthropic:claude-sonnet-4-5-20250929', 0, 0) == 0.0
  - test_rounding: result has at most 6 decimal places
  - test_empty_model_string: estimate_cost('', 1000, 1000) == 0.0
```

Location: `/workspace/example_grants/tests/test_pricing.py`

Pure unit tests. Import `estimate_cost` from `agents.pricing`.

#### D1.3: Error Classification Tests — `test_error_classification.py`

```
Tests:
  - test_429_is_resource: classify returns ResourceError for code 429
  - test_404_is_permanent: classify returns PermanentError for code 404
  - test_503_is_transient: classify returns TransientError for code 503
  - test_500_is_transient: classify returns TransientError for code 500 (default)
  - test_400_is_permanent: classify returns PermanentError for code 400
  - test_resource_is_retryable: ResourceError.retryable is True
  - test_permanent_not_retryable: PermanentError.retryable is False
  - test_transient_is_retryable: TransientError.retryable is True
  - test_classify_preserves_message: error message from TX.data['message'] is preserved
```

Location: `/workspace/example_grants/tests/test_error_classification.py`

Pure unit tests. Create TX objects with `tx.error(msg, code)` and pass to `classify_tx_error()`.

#### D1.4: Trace Interceptor Tests — `test_tracing.py`

```
Tests:
  - test_request_records_pending: on_request populates pending dict
  - test_inbox_matches_reply: on_inbox matches in_reply_to, creates trace record
  - test_unmatched_inbox_passes_through: on_inbox with no matching pending returns TX unchanged
  - test_trace_captures_duration: duration_ms is positive integer
  - test_trace_captures_error: is_error TX records success=False
  - test_trace_captures_tool_name: tool field is '{target}_{name}'
  - test_multiple_tool_calls: multiple request/reply pairs accumulate in traces list
  - test_safe_serialize_truncation: large data is truncated with preview
```

Location: `/workspace/example_grants/tests/test_tracing.py`

Async unit tests. Create TX objects, call interceptors directly.

---

### Task D2: Integration Tests

**Estimated time:** 2.5 hours
**Risk:** Medium (requires full app stack running)
**Category:** Tests

**Files created:**
- `/workspace/example_grants/tests/test_agent_run_observability.py`

#### D2.1: AgentRun Integration Tests — `test_agent_run_observability.py`

These extend the existing `test_agent_run.py` pattern. They use the full app stack (TestClient, real DB, real Matrix routing) with `TestModel` for the LLM.

```
Tests:
  - test_agent_run_creates_record: POST /agents/{id}/run creates AgentRun record
    Verify: GET /agent_runs returns at least one record
    Verify: record has status='completed', agent_id matches, task matches

  - test_agent_run_records_usage: After run, AgentRun has input_tokens > 0
    Verify: total_tokens == input_tokens + output_tokens
    Verify: requests >= 1

  - test_agent_run_records_cost: After run, estimated_cost >= 0.0
    (With TestModel, cost should be 0.0 since model='test')

  - test_agent_run_records_timing: duration_ms > 0, started_at and completed_at are set

  - test_agent_run_records_tool_calls: When agent calls a tool,
    tool_calls field contains at least one entry with
    {tool, args, duration_ms, success} keys

  - test_agent_run_failure_records_error: When agent_run raises,
    AgentRun record has status='failed' and error field is populated

  - test_agent_run_nested_route: GET /agents/{id}/agent_runs returns runs
    for that specific agent (via join model)

  - test_agent_run_schema_endpoint: GET /AgentRun returns valid JSON Schema
    with expected properties (agent_id, status, tool_calls, etc.)

  - test_run_response_includes_run_id: POST /agents/{id}/run response
    JSON includes 'run_id' key
```

Location: `/workspace/example_grants/tests/test_agent_run_observability.py`

These tests use the same fixtures as existing tests (`test_db`, `seed_data`, `alice_token`). The conftest already sets up a test DB with the full app.

**Test approach for failure recording:**
Create a test agent with a known-bad tool address. When the LLM tries to call the tool, the error is captured. Alternatively, mock the adapter to raise during `agent_run()`.

#### D2.2: SQLite Pragma Verification

Add a simple test to verify the pragma changes are effective:

```
Tests:
  - test_sqlite_busy_timeout: New connection has busy_timeout=10000
  - test_sqlite_synchronous: New connection has synchronous=1 (NORMAL)
  - test_sqlite_cache_size: New connection has cache_size=-64000
```

These can be added to an existing test file or a new `test_sqlite_pragmas.py`. They query `PRAGMA busy_timeout`, `PRAGMA synchronous`, `PRAGMA cache_size` on a fresh connection from the storage pool.

---

### Task D3: Documentation Updates

**Estimated time:** 0.5 hours
**Risk:** None
**Category:** Documentation

**Files modified:**
- `/workspace/CLAUDE.md` — update Key Files section with new files, update Architecture Overview with AgentRun

**Changes to CLAUDE.md:**

1. Add to "Key Files by Area" under a new "### Agents" subsection (or update the existing Agents entries):
   ```
   - `example_grants/models/agent_run.py` - AgentRun model: persistent agent execution records
   - `example_grants/agents/pricing.py` - Cost estimation: static pricing table + estimate_cost()
   - `example_grants/agents/tracing.py` - Tool call trace interceptor factory
   - `example_grants/utils/security.py` - SSRF prevention: URL validation for server-side requests
   - `src/n3tx/core/agents/errors.py` - Error classification: transient/permanent/resource
   ```

2. Add to "Key Patterns" section:
   ```
   ### AgentRun Pattern
   Agent runs are persisted via AgentRun model. The run() method creates a record
   before execution, registers trace interceptors, and updates with results after.
   If AgentRun is not registered, the agent runs without recording (graceful degradation).
   ```

---

## Summary of All Changes

### New Files (8)

| File | Category | Purpose |
|------|----------|---------|
| `example_grants/utils/__init__.py` | App | Package init |
| `example_grants/utils/security.py` | App | SSRF URL validation |
| `example_grants/agents/__init__.py` | App | Package init |
| `example_grants/agents/pricing.py` | App | Cost estimation |
| `example_grants/agents/tracing.py` | App | Trace interceptor factory |
| `example_grants/models/agent_run.py` | App | AgentRun model |
| `src/n3tx/core/agents/errors.py` | Framework | Error classification |
| `example_grants/tests/test_agent_run_observability.py` | Tests | Integration tests |

### Modified Files (7)

| File | Category | Scope of Change |
|------|----------|----------------|
| `example_grants/models/web_tools.py` | App | +2 lines (import + validate_url call) |
| `example_grants/models/__init__.py` | App | +2 lines (import + export AgentRun) |
| `example_grants/main.py` | App | +2 lines (import AgentRun, add join model) |
| `example_grants/tests/conftest.py` | Tests | +1 line (import AgentRun) |
| `src/n3tx/core/storage/sqlite_storage.py` | Framework | +4 lines (pragma changes in 2 locations) |
| `src/n3tx/core/agents/tools.py` | Framework | ~8 lines (error classification in _route_tool_call) |
| `src/n3tx/core/agents/mixin.py` | Framework | ~20 lines (on_adapter_created hook, message_history, _serialize_messages) |
| `src/n3tx/core/agents/actor.py` | Framework | ~60 lines (instrumented run() method) |

### Framework vs. Application Split

| Area | Framework (src/n3tx/core/) | Application (example_grants/) |
|------|------------------------------|-------------------------------|
| SSRF prevention | 0 files | 1 file (security.py) |
| SQLite pragmas | 1 file (sqlite_storage.py, 4 lines) | 0 files |
| Error classification | 1 file (errors.py, ~60 LOC) | 0 files |
| AgentRun model | 0 files | 1 file (agent_run.py) |
| Cost estimation | 0 files | 1 file (pricing.py) |
| Tracing | 0 files | 1 file (tracing.py) |
| Instrumentation | 2 files (mixin.py ~20 LOC, actor.py ~60 LOC) | 0 files |
| **Total new LOC** | **~140 LOC** | **~350 LOC** |

This split is consistent with N3TX's philosophy: the framework provides primitives (hooks, error types, richer return data), the application provides implementation (what to record, how to trace, what counts as safe).

---

## Time Budget

| Phase | Task | Hours | Day |
|-------|------|-------|-----|
| A | A1: SSRF prevention | 1.5 | 1 |
| A | A2: SQLite pragmas | 0.5 | 1 |
| A | A3: Error classification | 2.0 | 1 |
| B | B1: AgentRun model | 2.0 | 1-2 |
| B | B2: Join model registration | 1.0 | 2 |
| C | C1: Cost estimation | 1.0 | 2 |
| C | C2: Trace interceptor | 1.5 | 2-3 |
| C | C3: Instrument agent_run() | 3.5 | 3 |
| D | D1: Unit tests | 3.0 | 3-4 |
| D | D2: Integration tests | 2.5 | 4-5 |
| D | D3: Documentation | 0.5 | 5 |
| | **Total** | **~19 hours** | **~5 days** |

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `_serialize_messages()` breaks on new Pydantic AI message types | Medium | Low | Defensive serialization with fallback to `str()`. Pin Pydantic AI version in requirements. |
| AgentRun.create() fails during agent run (DB issue) | Low | Low | Graceful degradation: run proceeds without recording. `try/except` around all recording calls. |
| Trace interceptor interferes with auth interceptor on adapter | Very Low | Medium | Trace interceptors are registered AFTER auth interceptor (on the transient adapter, auth is not registered). They are passive (always return TX unchanged). No interference possible. |
| Large message histories bloat SQLite | Medium (at scale) | Low | `messages` field is hidden from UI by default (`ui.display: False`). Future: truncation, compression, or separate table. Not Sprint 1. |
| DNS resolution in SSRF check is slow for some domains | Low | Low | `socket.getaddrinfo` uses system resolver with caching. Timeout inherits from system DNS config. For production, consider caching resolved IPs. |

---

## Acceptance Criteria

Sprint 1 is complete when:

1. `POST /agents/1/run {"task": "..."}` creates an `AgentRun` record in the DB
2. `GET /agent_runs` returns a paginated list of run records with status, cost, duration
3. `GET /agents/1/agent_runs` returns runs for agent 1 (nested route via join model)
4. `GET /AgentRun` returns a valid JSON Schema with all fields and UI groups
5. The `tool_calls` field on completed runs contains entries with `{tool, args, duration_ms, success}`
6. Failed runs have `status='failed'` and a populated `error` field
7. `validate_url('http://169.254.169.254/')` raises `ValueError`
8. `validate_url('https://nsf.gov/')` succeeds
9. `PRAGMA busy_timeout` returns `10000` on DB connections
10. Error TX responses to tool calls include `[transient]` or `[permanent]` category prefix
11. All existing tests pass (no regressions)
12. All new tests pass

---

## Not In Scope (deferred to later sprints)

| Item | Why deferred | When |
|------|-------------|------|
| Live progress streaming (SSE/WebSocket) | Nice-to-have, not blocking | Sprint 2 |
| External observability (Langfuse/Logfire) | Requires evaluation after Phase 1 is in production | Sprint 3+ |
| Circuit breakers for external services | Requires tenacity dependency decision | Sprint 2 |
| Rate limiting (API + LLM) | Requires SlowAPI dependency decision | Sprint 2 |
| Structured logging (structlog) | Incremental migration, large surface area | Sprint 2 |
| Graceful shutdown for agent runs | Requires FastAPI lifespan integration | Sprint 2 |
| Retry logic (tenacity on WebTools.scrape) | Couples with circuit breaker design | Sprint 2 |
| Idempotent grant creation | Requires domain-specific dedup logic | Sprint 2 |
| Budget alerts and anomaly detection | Requires AgentRun data to be in production first | Sprint 3+ |
