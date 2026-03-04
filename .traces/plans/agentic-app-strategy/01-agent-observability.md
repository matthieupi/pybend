# Agent Observability for Grant Watcher

**Research Date:** 2026-03-04
**Scope:** Persistent run tracking, tool call tracing, cost accounting, live progress, and external observability integration for the N3TX agent system.
**Audience:** Technical CEO + Engineering Leadership

---

## 1. Executive Summary

Today, when an agent runs in the Grant Watcher app, the entire execution is a black box. `POST /agents/1/run` returns `{answer, usage, messages}` and then the data evaporates -- there is no persistent record, no audit trail, no cost ledger, no way to answer "what did the agent do last Tuesday?" or "how much have we spent on LLM calls this month?" For a grant-discovery product where agents spend real money scanning government websites, this is a **liability gap**, not just a missing feature.

The good news: the existing architecture is almost purpose-built for observability. Every tool call already flows through the actor system as a `TX` message with a UUID, source, target, and timestamp. The `NetworkAdapter` already correlates requests with responses via `_pending` futures. Pydantic AI's `RunResult` already surfaces `all_messages()` with `ToolCallPart`/`ToolReturnPart` objects and `RunUsage` with token counts. **The data exists in flight; it just needs to land somewhere.**

This report lays out a concrete plan: an `AgentRun` model that records every execution, an interceptor-based tracing system for tool calls, a cost-tracking pipeline with per-model pricing, and a phased path to live progress streaming. The total implementation scope is **3-5 days for the core** (Phase 1), with optional external integrations adding 1-2 days each. The ROI is immediate: cost visibility alone pays for the engineering investment within weeks of production use.

---

## 2. The What -- Concrete Deliverables

### 2.1 AgentRun Model (Persistent Run Records)

A new `AgentRun` model that captures every agent execution as a storable, schema-driven entity. Because it extends `ActorModel`, the frontend gets browse/search/detail views for free -- no UI code required.

**Fields:**

| Field | Type | Purpose |
|-------|------|---------|
| `agent_id` | `int` | FK to the AgentActor that ran |
| `task` | `str` | The user's input prompt |
| `status` | `str` | `running` / `completed` / `failed` / `cancelled` |
| `started_at` | `DateTimeField` | UTC timestamp of run start |
| `completed_at` | `DateTimeField` | UTC timestamp of run end |
| `duration_ms` | `int` | Wall-clock duration in milliseconds |
| `answer` | `TextareaField` | The LLM's final output |
| `error` | `str` | Error message if failed |
| `model_used` | `str` | Actual LLM model string (e.g., `anthropic:claude-sonnet-4-5-20250929`) |
| `input_tokens` | `int` | Total input tokens consumed |
| `output_tokens` | `int` | Total output tokens consumed |
| `total_tokens` | `int` | Computed sum |
| `estimated_cost` | `CurrencyField` | Dollar cost estimate |
| `requests` | `int` | Number of LLM API requests |
| `tool_calls` | `list` | JSON array of `{tool, args, result, duration_ms, success}` |
| `messages` | `list` | Full Pydantic AI message history (serialized) |
| `user_id` | `int` | Who triggered the run (nullable for system-triggered) |

> **Key Insight:** Every field above is already available in the current `agent_run()` return path. `result.usage()` gives tokens. `result.all_messages()` gives the full conversation including `ToolCallPart` and `ToolReturnPart`. The only missing data is tool call durations, which require the interceptor (Section 2.2).

### 2.2 Tool Call Tracing (Interceptor-Based)

Every tool call in `agent_run()` already flows as a `TX` message through a transient `NetworkAdapter`. This adapter supports `use()` interceptors. By registering a tracing interceptor on both `request` and `inbox`, we capture the full lifecycle of every tool call -- without touching a single line of the tool or agent code.

```
[LLM decides to call grants_list]
        |
        v
[_route_tool_call] --> TX(name='list', target='grants')
        |
        v
[adapter.request(tx)]
    |--- use(trace_interceptor, on='request')  --> record: {tool, args, start_time}
    |
    v
[Matrix routes to Grant.handler_crud()]
    |
    v
[Reply TX arrives at adapter.inbox()]
    |--- use(trace_interceptor, on='inbox')    --> record: {result, end_time, success}
    |
    v
[_route_tool_call returns JSON to LLM]
```

The trace interceptor is a **closure** that accumulates records into a list scoped to the run. After the run completes, the list is serialized into `AgentRun.tool_calls`.

### 2.3 Cost Tracking Pipeline

A static pricing table mapping model identifiers to per-token costs, combined with the token counts from Pydantic AI's `RunUsage`.

**Pricing snapshot (2026 rates):**

| Model | Input ($/1M tokens) | Output ($/1M tokens) | Source |
|-------|---------------------|----------------------|--------|
| `anthropic:claude-sonnet-4-5-20250929` | $3.00 | $15.00 | [Anthropic pricing](https://www.anthropic.com/pricing) |
| `anthropic:claude-opus-4-6` | $5.00 | $25.00 | [Anthropic pricing](https://www.anthropic.com/pricing) |
| `openai:gpt-5.2` | $1.75 | $14.00 | [OpenAI pricing](https://openai.com/pricing) |
| `openai:gpt-4o-mini` | $0.15 | $0.60 | [OpenAI pricing](https://openai.com/pricing) |
| `google:gemini-2.5-pro` | $1.25 | $10.00 | [Google Cloud pricing](https://cloud.google.com/vertex-ai/pricing) |
| `google:gemini-2.5-flash-lite` | $0.10 | $0.40 | [Google Cloud pricing](https://cloud.google.com/vertex-ai/pricing) |
| `ollama:*` | $0.00 | $0.00 | Local inference |

([Full 2026 pricing comparison](https://www.tldl.io/resources/llm-api-pricing-2026))

Cost calculation is trivial once you have the tokens:

```python
cost = (input_tokens * input_price / 1_000_000) + (output_tokens * output_price / 1_000_000)
```

### 2.4 Live Progress Streaming (Phase 2)

Real-time visibility into running agents via SSE or WebSocket. Two architectural options:

```
Option A: SSE (Simpler)                    Option B: WebSocket (Already exists)

[Agent Run]                                [Agent Run]
    |                                          |
    v                                          v
[SSE endpoint]                             [NetworkWebSocket._connections]
    |                                          |
    v                                          v
[EventSourceResponse]                      [broadcast to all clients]
    |                                          |
    v                                          v
[Browser EventSource API]                  [Frontend Matrix receives TX]
```

### 2.5 External Observability Integration (Phase 3)

Optional integration with Langfuse, Logfire, or Arize Phoenix via OpenTelemetry.

---

## 3. The Why -- Business Value

### 3.1 Cost Control

Without observability, LLM spend is invisible until the invoice arrives. A single runaway agent with no `UsageLimits` and a complex prompt can burn through hundreds of dollars of tokens in minutes. The Grant Scanner agent, configured with `tools=['grants', 'sources', 'web_tools']`, can chain `web_tools_scrape` calls across dozens of government sites per run. At $3/$15 per million tokens with Claude Sonnet, a single scan of 50 pages could cost **$2-10 depending on page sizes and reasoning depth**.

> **Key Insight:** Cost tracking turns "we think agents cost about X" into "Agent #1 spent $47.23 across 156 runs this month, averaging $0.30/run, with 3 outlier runs above $2." This is the difference between a budget line item and a controlled expense.

### 3.2 Debugging and Root Cause Analysis

When the Grant Scanner creates a malformed grant record (wrong deadline, missing URL, garbled description), the current system provides no way to understand why. The LLM conversation is gone. The tool call sequence is gone. Was it a bad prompt? A scraping failure? An LLM hallucination? With persistent run records and tool call traces, you can:

- Replay the exact sequence: "The LLM called `web_tools_scrape` on nsf.gov, got a 403, retried via `ModelRetry`, got HTML, called `web_tools_extract`, got empty text, then hallucinated the grant details"
- Correlate failures: "60% of failed runs involve the NIH source -- their site blocks automated requests"
- Optimize prompts: Compare token counts and quality across prompt variations

### 3.3 Audit Trail

For a grant-discovery platform, accountability matters. When a user asks "who found this grant?" or "when was this grant last verified?", the run history provides a complete provenance chain: **Agent X ran at time T, called tools A/B/C, produced result R, which created Grant record G.**

### 3.4 Operational Confidence

Right now, `POST /agents/1/run` is fire-and-hope. The operator has no idea if the agent is working, stalled, or burning money on a loop. Even basic status tracking (`running` / `completed` / `failed`) transforms operations from reactive ("users are complaining") to proactive ("3 of 5 scheduled runs failed last night, all on the same source").

---

## 4. The How -- Implementation Architecture

### 4.1 AgentRun Model Definition

This follows the standard N3TX model pattern. It lives in the Grant Watcher example app (not the framework), since run tracking is application-level, not framework-level.

```python
# example_grants/models/agent_run.py

from __future__ import annotations
import json
from typing import ClassVar, Optional
from pydantic import Field, model_validator

from n3tx.core.models.actor_model import ActorModel
from n3tx.core.authorize import ANYONE, AUTHENTICATED, ROLE
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
        'field_order': ['agent_id', 'task', 'status', 'duration_ms',
                        'answer', 'estimated_cost', 'total_tokens'],
        'groups': {
            'Overview': ['agent_id', 'task', 'status', 'model_used'],
            'Timing': ['started_at', 'completed_at', 'duration_ms'],
            'Cost': ['input_tokens', 'output_tokens', 'total_tokens',
                     'requests', 'estimated_cost'],
            'Result': ['answer', 'error'],
            'Trace': ['tool_calls', 'messages'],
        },
    }

    agent_id: int = Field(description="FK to the agent that ran")
    task: str = Field(default='', description="User prompt / task")
    status: str = Field(default='running',
                        description="running | completed | failed | cancelled")
    started_at: Optional[DateTimeField] = Field(default=None)
    completed_at: Optional[DateTimeField] = Field(default=None)
    duration_ms: int = Field(default=0)
    answer: TextareaField = Field(default='')
    error: str = Field(default='')
    model_used: str = Field(default='')
    input_tokens: int = Field(default=0)
    output_tokens: int = Field(default=0)
    total_tokens: int = Field(default=0)
    estimated_cost: CurrencyField = Field(default=0.0)
    requests: int = Field(default=0)
    tool_calls: list = Field(default=[])
    messages: list = Field(default=[])
    user_id: int = Field(default=0)

    @model_validator(mode='before')
    @classmethod
    def _deserialize_json_fields(cls, data):
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
        d = super()._storage_dict(exclude_unset=exclude_unset)
        for field in _JSON_FIELDS:
            if field in d and not isinstance(d[field], str):
                d[field] = json.dumps(d[field], default=str)
        return d
```

> **Key Insight:** This model follows the exact same JSON-field serialization pattern as `AgentActor` (see `/workspace/src/n3tx/core/agents/actor.py` lines 67-87). The `_JSON_FIELDS` / `_storage_dict` / `@model_validator` trio is a proven pattern for SQLite storage of complex types.

### 4.2 Registration and Join Model

```python
# In example_grants/main.py, add to the models list:

from models.agent_run import AgentRun

app = create_app(
    models=[User, Grant, Source, WebTools, AgentTool, AgentActor, AgentRun],
    join_models=[(AgentActor, AgentTool), (AgentActor, AgentRun)],
    # ... rest unchanged
)
```

This gives us:
- `GET /AgentRun` -- schema (auto-generated, includes all fields and UI hints)
- `GET /agent_runs` -- list all runs (paginated, auth-gated)
- `GET /agent_runs/{id}` -- single run detail
- `GET /agents/{agent_id}/agent_runs` -- runs for a specific agent (via join model)
- Frontend: `<ntx-list model="AgentRun">` renders a browsable run history

The join model `AgentActorAgentRun` is generated automatically by `generate_join_model()` with an `agentactor_id` FK column, following the exact pattern used for `AgentActorAgentTool` already in the codebase.

### 4.3 Modified agent_run() Flow

The core change is wrapping the existing `agent_run()` method to capture data before, during, and after execution.

```
                       BEFORE                   DURING                    AFTER
                    +-----------+          +----------------+         +-----------+
                    | Create    |          | Run Pydantic   |         | Update    |
                    | AgentRun  |          | AI agent with  |         | AgentRun  |
    POST            | record    |          | trace          |         | with      |
    /agents/1/run   | status=   |          | interceptor    |         | results   |
    -------->       | 'running' |  ------> | on adapter     | ------> | status=   |
                    |           |          |                |         | completed |
                    +-----------+          +----------------+         +-----------+
                         |                       |                         |
                         v                       v                         v
                    [AgentRun.create()]    [tool_calls list             [AgentRun.update()]
                                           accumulates]
```

The implementation wraps `agent_run()` at the `AgentActor.run()` level (in the Grant Watcher app, not in framework code). This preserves the framework's simplicity while adding application-level instrumentation:

```python
# Modified AgentActor.run() or a wrapper in the grant app

import time
from datetime import datetime, timezone

async def instrumented_run(self, task: str, user=None, **kwargs) -> str:
    from models.agent_run import AgentRun
    from agents.pricing import estimate_cost

    # Phase 1: Create run record
    run_record = AgentRun(
        agent_id=self.id,
        task=task,
        status='running',
        started_at=datetime.now(timezone.utc).isoformat(),
        model_used=kwargs.get('llm') or self.llm,
        user_id=user.get('user_id', 0) if user else 0,
    )
    run_record = AgentRun.create(run_record)
    start_time = time.monotonic()

    try:
        # Phase 2: Execute with tracing
        tool_addrs = self._resolve_tool_addrs()
        result = await self.agent_run(
            prompt=self.prompt,
            tools=tool_addrs,
            task=task,
            **kwargs,
        )

        # Phase 3: Record results
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        parsed = json.loads(result) if isinstance(result, str) else result
        usage = parsed.get('usage', {})

        AgentRun.update(run_record.id, {
            'status': 'completed',
            'completed_at': datetime.now(timezone.utc).isoformat(),
            'duration_ms': elapsed_ms,
            'answer': parsed.get('answer', ''),
            'input_tokens': usage.get('input_tokens', 0),
            'output_tokens': usage.get('output_tokens', 0),
            'total_tokens': usage.get('input_tokens', 0) + usage.get('output_tokens', 0),
            'requests': usage.get('requests', 0),
            'estimated_cost': estimate_cost(
                model=kwargs.get('llm') or self.llm,
                input_tokens=usage.get('input_tokens', 0),
                output_tokens=usage.get('output_tokens', 0),
            ),
        })
        return result

    except Exception as e:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        AgentRun.update(run_record.id, {
            'status': 'failed',
            'completed_at': datetime.now(timezone.utc).isoformat(),
            'duration_ms': elapsed_ms,
            'error': str(e),
        })
        raise
```

### 4.4 Tool Call Trace Interceptor

The tracing interceptor hooks into the transient `NetworkAdapter` that `agent_run()` creates for each run (see `/workspace/src/n3tx/core/agents/mixin.py` line 89). The key insight: `adapter.use()` already exists and supports both `request` and `inbox` hooks.

```python
# agents/tracing.py

import time
from n3tx.core.actors.tx import TX


def create_trace_interceptor():
    """Factory: creates a paired request/inbox interceptor that captures tool calls.

    Returns (request_interceptor, inbox_interceptor, trace_list).
    The trace_list accumulates records during the run.
    """
    traces = []
    pending_starts = {}  # uuid -> {tool, args, start_time}

    async def on_request(tx: TX) -> TX:
        """Record tool call start time and arguments."""
        pending_starts[tx.uuid] = {
            'tool': f'{tx.target}_{tx.name}',
            'args': tx.data,
            'start_time': time.monotonic(),
            'tx_uuid': tx.uuid,
        }
        return tx  # Pass through unchanged

    async def on_inbox(tx: TX) -> TX:
        """Match reply to original request, record result and duration."""
        reply_to = tx.meta.get('in_reply_to')
        if reply_to and reply_to in pending_starts:
            start_info = pending_starts.pop(reply_to)
            elapsed_ms = int((time.monotonic() - start_info['start_time']) * 1000)
            traces.append({
                'tool': start_info['tool'],
                'args': start_info['args'],
                'result': tx.data if not tx.is_error else {'error': tx.data},
                'duration_ms': elapsed_ms,
                'success': not tx.is_error,
            })
        return tx  # Pass through unchanged

    return on_request, on_inbox, traces
```

To wire this into `agent_run()`, the change is minimal -- 4 lines added to `mixin.py`:

```python
# In agent_run(), after creating the adapter (line 89):

adapter = NetworkAdapter(addr=adapter_addr)

# ADD: Wire trace interceptor
from n3tx.core.agents.tracing import create_trace_interceptor
on_req, on_inbox, tool_traces = create_trace_interceptor()
adapter.use(on_req, on='request')
adapter.use(on_inbox, on='inbox')

# ... existing code continues ...

# After result = await ai_agent.run(...):
# tool_traces now contains all tool call records
```

This design is notable for what it does **not** touch: it modifies zero lines of `tools.py`, `_route_tool_call`, `actor_model.py`, or any handler. The interceptor pattern (`use()`) was designed exactly for this kind of cross-cutting concern.

### 4.5 Cost Estimation Module

```python
# agents/pricing.py

# Per-million-token rates. Update when providers change pricing.
PRICING = {
    'anthropic:claude-sonnet-4-5-20250929': {'input': 3.00, 'output': 15.00},
    'anthropic:claude-opus-4-6':            {'input': 5.00, 'output': 25.00},
    'anthropic:claude-haiku-3-5':           {'input': 0.25, 'output': 1.25},
    'openai:gpt-5.2':                      {'input': 1.75, 'output': 14.00},
    'openai:gpt-4o-mini':                  {'input': 0.15, 'output': 0.60},
    'google:gemini-2.5-pro':               {'input': 1.25, 'output': 10.00},
    'google:gemini-2.5-flash-lite':        {'input': 0.10, 'output': 0.40},
}

# Default for unknown models (conservative estimate)
_DEFAULT = {'input': 3.00, 'output': 15.00}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD for a given model and token count.

    Returns 0.0 for local models (ollama:*) and unknown-but-free models.
    """
    if model.startswith('ollama:') or model == 'test':
        return 0.0

    rates = PRICING.get(model, _DEFAULT)
    cost = (
        (input_tokens * rates['input'] / 1_000_000) +
        (output_tokens * rates['output'] / 1_000_000)
    )
    return round(cost, 6)


def daily_spend(runs: list) -> float:
    """Sum estimated_cost across a list of AgentRun records."""
    return sum(getattr(r, 'estimated_cost', 0) or 0 for r in runs)
```

### 4.6 Enriching agent_run() with Full Message History

Pydantic AI's `result.all_messages()` returns a list of `ModelRequest` and `ModelResponse` objects. Each `ModelResponse` contains:
- `parts`: list of `TextPart`, `ToolCallPart`, `ThinkingPart`
- `usage`: `RequestUsage` with per-request token counts
- `model_name`: which model handled this specific request
- `timestamp`: when the response was generated

Each `ToolCallPart` contains:
- `tool_name`: e.g., `grants_list`
- `args`: the arguments passed
- `tool_call_id`: correlation ID

Each `ToolReturnPart` (in the subsequent `ModelRequest`) contains:
- `tool_name`: matching the call
- `content`: the tool's return value
- `timestamp`: when the tool completed

([Pydantic AI messages API](https://ai.pydantic.dev/api/messages/))

The current `agent_run()` returns only `len(result.all_messages())`. To capture the full history, we serialize the message list:

```python
# In agent_run() return:
return {
    'answer': result.output,
    'usage': { ... },
    'messages': len(result.all_messages()),
    'message_history': [msg_to_dict(m) for m in result.all_messages()],
    'tool_traces': tool_traces,  # From interceptor
}
```

The `msg_to_dict` serializer handles Pydantic AI's message types, extracting the fields documented above into plain dicts suitable for JSON storage.

### 4.7 Architecture Diagram -- Full Data Flow

```
 User: POST /agents/1/run {"task": "Find new NSF grants"}
                |
                v
 [NetworkAPI] --> TX(name='run', target='agents', data={task, id=1})
                |
                v
 [AgentActor.handler()] --> run() method
                |
                v
 [instrumented_run()]
    |
    +-- 1. AgentRun.create(status='running')  -----> [SQLite: agent_runs table]
    |
    +-- 2. agent_run(prompt, tools, task)
    |       |
    |       +-- NetworkAdapter(addr='_agent_abc123')
    |       |       |
    |       |       +-- use(trace_on_request, on='request')
    |       |       +-- use(trace_on_inbox, on='inbox')
    |       |
    |       +-- discover_tools(['grants','sources','web_tools'], matrix)
    |       |       |
    |       |       +-- ToolSpec: grants_list, grants_create, ...
    |       |       +-- ToolSpec: sources_list, sources_get, ...
    |       |       +-- ToolSpec: web_tools_scrape, web_tools_extract
    |       |
    |       +-- Agent(llm, tools=ai_tools).run(task, deps=AgentDeps)
    |               |
    |               |  LLM Loop:
    |               |  +-- LLM: "I should list sources first"
    |               |  +-- ToolCall: sources_list {}
    |               |  |     +-- TX(list, _agent_abc123 -> sources)  [traced]
    |               |  |     +-- Reply TX(sources data)               [traced]
    |               |  |
    |               |  +-- LLM: "Now scrape nsf.gov"
    |               |  +-- ToolCall: web_tools_scrape {url: nsf.gov}
    |               |  |     +-- TX(scrape, _agent_abc123 -> web_tools)  [traced]
    |               |  |     +-- Reply TX(html content)                   [traced]
    |               |  |
    |               |  +-- LLM: "Found a grant, creating record"
    |               |  +-- ToolCall: grants_create {title, url, ...}
    |               |  |     +-- TX(create, _agent_abc123 -> grants)  [traced]
    |               |  |     +-- Reply TX(created grant)               [traced]
    |               |  |
    |               |  +-- LLM: "Done. Found 1 new grant."
    |               |
    |               +-- returns RunResult
    |
    +-- 3. AgentRun.update(status='completed', tool_calls=[...], ...)
    |                                                      |
    |                                                      +---> [SQLite]
    +-- 4. Return {answer, usage, messages, run_id}
                |
                v
 [HTTP 200 JSON response to user]
```

---

## 5. Feasibility Assessment

### 5.1 Complexity Analysis

| Component | Effort | Risk | Dependencies |
|-----------|--------|------|--------------|
| AgentRun model | 0.5 days | Low | Standard ActorModel pattern, identical to Grant/Source |
| Join model + registration | 0.25 days | Low | Same as existing AgentTool join |
| Instrumented run wrapper | 1 day | Medium | Touches agent_run() flow; needs careful error handling |
| Trace interceptor | 0.5 days | Low | Uses existing `use()` API; zero changes to framework |
| Cost estimation module | 0.25 days | Low | Static pricing table, pure function |
| Message history serialization | 0.5 days | Medium | Pydantic AI message types need careful serialization |
| Tests | 1 day | Low | Extend existing test_agent_run.py patterns |
| **Total Phase 1** | **~4 days** | **Medium** | |

### 5.2 What Changes in Framework vs. App Code

This is critical. The vast majority of the work happens in **application code** (the Grant Watcher app), not in the N3TX framework:

| Change | Where | Impact |
|--------|-------|--------|
| AgentRun model | `example_grants/models/agent_run.py` | **New file** (app code) |
| Pricing module | `example_grants/agents/pricing.py` | **New file** (app code) |
| Trace interceptor | `example_grants/agents/tracing.py` or `src/n3tx/core/agents/tracing.py` | **New file** (could live in either) |
| Instrumented run | `example_grants/models/agent_run.py` or override | **New code** (app code) |
| agent_run() changes | `src/n3tx/core/agents/mixin.py` | **Minimal** -- expose `tool_traces` + `message_history` in return dict |
| main.py registration | `example_grants/main.py` | **2 lines** (add model + join) |

The only framework-level change is enhancing `agent_run()` to return the raw data. The interpretation, storage, and presentation are all application-level. This is consistent with N3TX's principle: **"primitives, not opinions."**

### 5.3 Risk Factors

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| SQLite JSON storage performance for large message histories | Medium | Low | Messages field could be large (50KB+ for complex runs). Truncation or separate table if needed. |
| Pydantic AI message serialization brittleness | Medium | Medium | Pin Pydantic AI version; write a defensive serializer that degrades gracefully. |
| Run record creation fails (DB issue) during agent run | Low | Medium | Wrap in try/except; agent run proceeds even if recording fails. |
| Tool trace interceptor interferes with auth interceptor | Low | High | Trace interceptor is passive (always returns tx unchanged). Test with auth enabled. |
| Cost estimates drift from actual pricing | Certain | Low | Pricing table is a best-effort estimate. Include "estimated" disclaimer. Update quarterly. |

### 5.4 SQLite Considerations

The `tool_calls` and `messages` fields store JSON TEXT. For a typical agent run:
- **tool_calls**: 3-10 entries, ~500 bytes each = **1.5-5 KB**
- **messages**: 5-20 message objects, ~1-5 KB each = **5-100 KB**

SQLite handles TEXT fields up to 1 GB. For 1,000 runs at 50 KB average, that is 50 MB of data -- well within SQLite's comfort zone. If message histories grow large (e.g., extended multi-turn agent sessions), the messages field can be:
1. Truncated to the last N messages
2. Stored in a separate `agent_run_messages` table with its own pagination
3. Compressed before storage (gzip typically achieves 80%+ compression on JSON)

---

## 6. ROI Analysis

### 6.1 Investment

| Cost | Estimate |
|------|----------|
| Engineering time (Phase 1) | 4 days = ~$4,000 (at $1,000/day loaded cost) |
| Ongoing maintenance | ~2 hours/quarter (pricing table updates, Pydantic AI version bumps) |
| Infrastructure cost | $0 (SQLite, no new services) |

### 6.2 Returns

| Benefit | Value | Timeline |
|---------|-------|----------|
| **Cost visibility** | Prevents $X00/month surprise LLM bills. Even 10% cost optimization from identifying wasteful runs pays back in 1-2 months. | Immediate |
| **Debugging time saved** | Each agent failure investigation drops from 30-60 min (reproduce, guess, add logging, re-run) to 5 min (read the trace). At 2 failures/week, saves 1-2 hours/week. | Immediate |
| **Prompt optimization** | Compare token consumption across prompt variants. A 20% token reduction on a frequently-run agent saves money proportionally. | Within 2 weeks |
| **Audit compliance** | Grant-related applications may require demonstrating due diligence in data sourcing. Run history provides evidence chain. | When needed |
| **Operational dashboards** | Status field enables "agent health" monitoring without custom tooling. The schema-driven UI renders it automatically. | Immediate |

### 6.3 Payback Period

For a system running 50 agent invocations per day at an average of $0.30 each:
- Monthly LLM spend: ~$450
- A 15% cost optimization (common from just having visibility): saves **~$67/month**
- Debug time savings: ~6 hours/month at $125/hour = **~$750/month**
- **Total monthly savings: ~$817**
- **Payback period: < 1 week**

Even at 10 runs/day, the debug time savings alone justify the investment within the first month.

---

## 7. Trade-offs & Alternatives

### 7.1 Build vs. Buy: External Observability Platforms

| Approach | Pros | Cons |
|----------|------|------|
| **Built-in (AgentRun model)** | Zero dependencies, works offline, schema-driven UI for free, full data ownership, fits N3TX philosophy | No waterfall visualization, no advanced analytics, no alert system |
| **Langfuse (self-hosted)** | Beautiful UI, span waterfalls, cost tracking, evals, collaborative | Docker dependency, separate data store (Postgres), learning curve, network dependency |
| **Pydantic Logfire** | First-party Pydantic AI integration (2 lines of code), OTel-native, purpose-built LLM panels | SaaS (data leaves your infra), pricing scales with usage, vendor lock-in |
| **Arize Phoenix (self-hosted)** | Open source, no feature gates, OTel-native, evals built in | Docker dependency, separate data store, Python-heavy |

([Langfuse overview](https://langfuse.com/docs/observability/overview)) | ([Logfire integration](https://ai.pydantic.dev/logfire/)) | ([Phoenix overview](https://arize.com/docs/phoenix))

> **Key Insight:** These are not mutually exclusive. The **built-in AgentRun model provides the data capture layer** (persistence, cost tracking, tool traces). An external platform provides the **visualization and analysis layer**. You can start with built-in and add Langfuse/Logfire later by exporting AgentRun records or by adding OTel spans alongside.

### 7.2 Comparison Table: Implementation Approaches

| Criterion | Built-in Only | Built-in + Logfire | Built-in + Langfuse | External Only |
|-----------|--------------|--------------------|--------------------|--------------|
| Setup time | 4 days | 4.5 days | 5 days | 1 day |
| Ongoing cost | $0 | ~$25-100/mo | $0 (self-hosted) | $0-100/mo |
| Data ownership | Full | Partial (SaaS) | Full (self-hosted) | Depends |
| Offline operation | Yes | No | Yes (self-hosted) | No |
| Visualization | Basic (schema UI) | Excellent | Excellent | Excellent |
| Alerting | Manual | Built-in | Built-in | Built-in |
| N3TX integration | Native | OTel bridge | OTel bridge | OTel bridge |
| Persistence | SQLite | External DB | Postgres | External DB |

### 7.3 What You Give Up

**With built-in only:**
- No span waterfall visualization (you get JSON arrays, not interactive timelines)
- No anomaly detection or automated alerting
- No cross-agent comparison dashboards (unless you build them)
- No collaborative annotation (team members can't tag/comment on runs)

**With external platform:**
- Additional infrastructure (Docker containers, Postgres)
- Network dependency for observability (if SaaS)
- Two sources of truth for run data (unless you make one primary)
- Learning curve for another platform

### 7.4 Alternative: Framework-Level Hook

Instead of modifying `agent_run()` directly, an alternative is a **lifecycle hook pattern** on `AgentMixin`:

```python
class AgentMixin:
    async def on_run_start(self, task, tools, **kwargs): pass
    async def on_run_complete(self, result, **kwargs): pass
    async def on_run_error(self, error, **kwargs): pass
    async def on_tool_call(self, tool_name, args, result, duration_ms): pass
```

Applications would override these hooks. This is more elegant but adds framework complexity for a feature that may only be needed in some apps. **Recommendation: start with the simpler wrapped approach. If a second app needs run tracking, extract the hooks into the framework.**

### 7.5 Alternative: Event Sourcing with TX Log

Every `TX` in the actor system already has a UUID, timestamp, source, target, and data. An event-sourced approach would persist **every TX** and derive run views from the event log:

```
[TX Log Table]
uuid | timestamp | name | source | target | data | meta
-----+-----------+------+--------+--------+------+------
a1   | 10:00:01  | run  | api    | agents | {task: "..."} | {user: {...}}
a2   | 10:00:02  | list | _agent | sources | {} | {run_id: "a1"}
a3   | 10:00:02  | list_RESPONSE | sources | _agent | [{...}] | {in_reply_to: "a2"}
...
```

This is architecturally pure but operationally heavy: it produces far more data than needed (every CRUD operation, every internal message), requires complex queries to reconstruct run views, and conflates framework debugging with application observability.

([Event sourcing for agentic AI](https://akka.io/blog/event-sourcing-the-backbone-of-agentic-ai))

**Recommendation: Reject for now.** The AgentRun model captures the right level of abstraction. Event sourcing is valuable if you need perfect auditability of the entire actor system, but that is a different feature.

---

## 8. Phased Implementation Plan

### Phase 1: Core Observability (3-5 days)

**Goal:** Every agent run is persistently recorded with full context.

| Task | Deliverable | Effort |
|------|-------------|--------|
| Define AgentRun model | `example_grants/models/agent_run.py` | 0.5d |
| Register model + join | `example_grants/main.py` changes | 0.25d |
| Implement trace interceptor | `agents/tracing.py` | 0.5d |
| Implement cost estimator | `agents/pricing.py` | 0.25d |
| Modify `agent_run()` to return rich data | `mixin.py` -- return message_history + tool_traces | 0.5d |
| Wire instrumented_run into AgentActor | Override or wrapper in grant app | 0.5d |
| Message serialization utility | Handle Pydantic AI types -> JSON | 0.5d |
| Tests | Extend test_agent_run.py | 1d |

**Definition of done:** `POST /agents/1/run` creates an AgentRun record. `GET /agent_runs` shows run history with status, cost, duration. `GET /agents/1/agent_runs` shows runs for a specific agent. Tool call traces are captured in the tool_calls field.

### Phase 2: Live Progress (2-3 days, optional)

**Goal:** Users see real-time tool calls as they happen during a run.

| Task | Deliverable | Effort |
|------|-------------|--------|
| SSE endpoint for run progress | `GET /agents/{id}/run/{run_id}/stream` | 1d |
| Emit progress events from trace interceptor | Extend on_request/on_inbox to push events | 0.5d |
| Frontend EventSource consumer | Listen to SSE, render live tool calls | 1d |

**Alternative:** Use the existing `NetworkWebSocket` to broadcast tool call events. The infrastructure exists (`_connections`, `LIFECYCLE` handler, `create_ws_routes`). Tool call events would be a new event type alongside CREATE/UPDATE/DELETE lifecycle events.

### Phase 3: External Integration (1-2 days per platform, optional)

**Goal:** Rich visualization and alerting via Langfuse or Logfire.

| Platform | Integration Path | Effort |
|----------|-----------------|--------|
| **Pydantic Logfire** | `logfire.configure(); logfire.instrument_pydantic_ai()` -- literally 2 lines in `main.py`. Automatic span capture for all agent runs. ([Logfire docs](https://ai.pydantic.dev/logfire/)) | 0.5d |
| **Langfuse** | Use OTEL-native SDK v3. Export spans alongside AgentRun records. Self-hosted with Docker. ([Langfuse OTEL integration](https://langfuse.com/integrations/native/opentelemetry)) | 1.5d |
| **Arize Phoenix** | Self-hosted via Docker. OTel exporter config. ([Phoenix GitHub](https://github.com/Arize-ai/phoenix)) | 1.5d |

> **Key Insight:** Logfire is the path of least resistance. Two lines of code. But it is SaaS -- your data goes to Pydantic's servers. For a grant-discovery platform that may handle sensitive government URLs and application data, self-hosted Langfuse or Phoenix may be more appropriate. The built-in AgentRun model works regardless.

### Phase 4: Advanced Analytics (future)

- Budget alerts: `if daily_spend(runs) > threshold: notify()`
- Anomaly detection: runs with >2x average cost or duration
- Prompt A/B testing: compare AgentRun metrics across prompt variants
- Agent leaderboard: which agent finds the most grants per dollar

---

## 9. Integration with Existing Architecture

### 9.1 How AgentRun Fits the N3TX Pattern

| N3TX Pattern | AgentRun Implementation |
|----------------|------------------------|
| Model is the app | AgentRun model definition carries all schema, UI, access rules |
| Zero to working | Register model, get CRUD API + browsable UI instantly |
| Backend is authoritative | Run records are created server-side; frontend just reads schema |
| Schema-driven UI | `__ui__.groups` organizes fields into Overview/Timing/Cost/Result/Trace sections |
| ListRef joins | `(AgentActor, AgentRun)` join gives nested browsing via `/agents/1/agent_runs` |
| Widget types | `DateTimeField`, `TextareaField`, `CurrencyField` render correctly without frontend code |
| Access control | `AUTHENTICATED` for read, `ROLE('admin')` for modify -- operators can browse but not tamper |

### 9.2 How Tracing Fits the Actor Pattern

The trace interceptor uses `adapter.use()`, which is the canonical cross-cutting concern mechanism in the actor system. It follows the exact same pattern as `auth_interceptor` in `/workspace/src/n3tx/core/api/auth_interceptor.py`:

```python
# Auth interceptor (existing):
adapter.use(auth_interceptor, on='request')

# Trace interceptor (new):
adapter.use(trace_on_request, on='request')
adapter.use(trace_on_inbox, on='inbox')
```

Both are async functions with signature `async (TX) -> TX`. Both return the TX unchanged (pass-through). The auth interceptor may return an error TX to short-circuit; the trace interceptor never does. They compose cleanly.

### 9.3 How Cost Tracking Fits the Data Model

Cost is stored as `CurrencyField` on AgentRun -- the same widget type used for `Grant.amount_min` and `Grant.amount_max`. The frontend already knows how to render currency values with the `$` prefix. No new widget code needed.

Aggregate cost queries use the existing `StorableMixin.list()` with `sql_filter`:

```python
# Daily cost for a specific agent
runs = AgentRun.list(sql_filter=f"agent_id = {agent_id} AND started_at >= '{today}'")
total = sum(r.estimated_cost for r in runs['data'])
```

---

## 10. Comparison: Before and After

| Dimension | Before (Current) | After (Phase 1) |
|-----------|------------------|------------------|
| Run persistence | None -- data lost after HTTP response | Every run stored in SQLite with full context |
| Cost visibility | Unknown -- check provider dashboard | Per-run cost estimate, aggregate queries |
| Debugging | Reproduce, guess, add logging, re-run (30-60 min) | Read tool_calls + messages from AgentRun (5 min) |
| Audit trail | None | Full provenance: who ran what, when, what tools called, what was created |
| Status monitoring | Fire and hope | `status` field: running/completed/failed with duration |
| Tool call details | Lost after run | `tool_calls` JSON: tool name, args, result, duration, success |
| Message history | Only count returned | Full serialized conversation (ModelRequest/ModelResponse sequence) |
| Run history | None | `GET /agent_runs` with pagination, `GET /agents/{id}/agent_runs` per agent |
| Frontend UI | Nothing | Schema-driven list + detail views, grouped by Overview/Timing/Cost/Result/Trace |

---

## 11. Recommendation

**Go.** Priority: **High**. Implement Phase 1 immediately.

**Rationale:**

1. **The architecture supports it natively.** The interceptor pattern, ActorModel pattern, join model pattern, and widget system are all in place. This is not a shoehorn -- it is the next logical use of existing primitives.

2. **The data already exists in flight.** Pydantic AI's `RunResult` surfaces tokens, messages, and tool call details. The transient `NetworkAdapter` carries every tool call as a TX. We are literally discarding this data after each run. Persisting it is a minimal change.

3. **The cost of not doing it is real.** Invisible LLM spend, blind debugging, and no audit trail are liabilities that grow with every agent added. The Grant Scanner is agent #1. Agents #2-5 are coming. Build the observability infrastructure now, while the surface area is small.

4. **The investment is modest.** 4 days for Phase 1 with immediate payback from debugging time savings alone. Zero new infrastructure (SQLite). Zero new dependencies for Phase 1.

5. **It compounds.** AgentRun data enables prompt optimization, cost optimization, anomaly detection, and agent comparison -- all without additional infrastructure. The data becomes an asset.

**Specific guidance:**

- **Phase 1:** Do it this week. The AgentRun model, trace interceptor, and cost estimator are straightforward.
- **Phase 2 (live progress):** Queue for next sprint. Nice-to-have, not blocking.
- **Phase 3 (external integration):** Evaluate after Phase 1 is in production. If the schema-driven UI is sufficient for the team's needs, defer. If waterfall traces and alerts become important, add Logfire (2 lines) or Langfuse (self-hosted).
- **Framework-level hooks:** Defer until a second app needs run tracking. Premature abstraction.

---

## 12. Sources

- [Pydantic AI Agent API](https://ai.pydantic.dev/api/agent/) -- RunResult, usage, message history
- [Pydantic AI Messages API](https://ai.pydantic.dev/api/messages/) -- ToolCallPart, ToolReturnPart, ModelRequest, ModelResponse
- [Pydantic AI Usage API](https://ai.pydantic.dev/api/usage/) -- RunUsage, UsageLimits class definitions
- [Pydantic AI Message History](https://ai.pydantic.dev/message-history/) -- all_messages(), new_messages() usage
- [Pydantic AI Logfire Integration](https://ai.pydantic.dev/logfire/) -- 2-line setup, automatic span capture
- [Pydantic AI Streaming](https://deepwiki.com/pydantic/pydantic-ai/4.1-streaming-and-real-time-processing) -- run_stream, AgentStreamEvents
- [Langfuse Observability Overview](https://langfuse.com/docs/observability/overview) -- @observe decorator, OTEL-native SDK
- [Langfuse Pydantic AI Integration](https://langfuse.com/integrations/frameworks/pydantic-ai) -- framework-specific integration guide
- [Langfuse Token & Cost Tracking](https://langfuse.com/docs/observability/features/token-and-cost-tracking) -- per-model pricing, cost attribution
- [OpenTelemetry AI Agent Observability](https://opentelemetry.io/blog/2025/ai-agent-observability/) -- GenAI SIG, semantic conventions
- [OpenTelemetry GenAI Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/) -- standard span schema for LLM tracing
- [SigNoz Pydantic AI Observability](https://signoz.io/docs/pydantic-ai-observability/) -- OTel integration guide
- [Arize Phoenix](https://github.com/Arize-ai/phoenix) -- open-source, self-hosted LLM observability
- [Arize AX Pydantic AI Tracing](https://arize.com/docs/ax/integrations/python-agent-frameworks/pydantic/pydantic-ai-tracing) -- Phoenix integration for Pydantic AI
- [LLM API Pricing 2026](https://www.tldl.io/resources/llm-api-pricing-2026) -- comprehensive pricing comparison
- [LLM Cost Per Token Guide 2026](https://www.silicondata.com/blog/llm-cost-per-token) -- pricing tiers, reasoning tokens
- [Traceloop: LLM Cost Per User](https://www.traceloop.com/blog/from-bills-to-budgets-how-to-track-llm-token-usage-and-cost-per-user) -- metadata tagging strategy
- [Event Sourcing for Agentic AI](https://akka.io/blog/event-sourcing-the-backbone-of-agentic-ai) -- event-driven agent architectures
- [Schema Design for Agent Memory](https://medium.com/@pranavprakash4777/schema-design-for-agent-memory-and-llm-history-38f5cbc126fb) -- conversations/messages/tool_calls tables
- [FastAPI Server-Sent Events](https://fastapi.tiangolo.com/tutorial/server-sent-events/) -- native SSE support
- [SSE for AI Agent Streaming](https://akanuragkumar.medium.com/streaming-ai-agents-responses-with-server-sent-events-sse-a-technical-case-study-f3ac855d0755) -- practical SSE implementation for agents

---

*Report generated for the Grant Watcher observability evaluation. All code sketches reference the N3TX codebase at `/workspace/src/n3tx/` and the Grant Watcher app at `/workspace/example_grants/`.*
