# PyBend Agentic System — Implementation Plan

## Context

We're jumping from v0.8 directly to v0.10 Wave 1 to build a **Grant Watch Tool** — a financing watch that scrapes government websites and uses LLM agents to surface structured grant opportunities. This is PyBend's first product use case for the agentic system.

### Design Decisions (Confirmed)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| LLM internals | **Pydantic AI** | Handles agentic loop, provider abstraction, structured output, tool calling. PyBend models ARE Pydantic models — `output_type=Grant` works natively. |
| Orchestration | **Actor-based self-organization** | Each agent actor does its job and forwards TX to the next. No Pipeline class — the actor system IS the orchestration. |
| Scheduling | **SchedulerActor** | A static Actor whose only job is waking agents via TX. Agents register via `__schedule__` ClassVar or dynamic TX. |
| Agent identity | **ActorModel + AgentMixin** | "The model is the agent." `__agent__ = True` injects AgentMixin, same pattern as `__storable__`. |

---

## Architecture: How It Works

### The Core Loop

Each agent actor wraps a **Pydantic AI `Agent`** internally. The Pydantic AI agent handles the LLM loop (tool calling, structured output, retries). The ActorModel handles routing, persistence, lifecycle, and schema.

```
                    ┌─────────────────────────────┐
                    │     ActorModel (PyBend)      │
                    │  - Routing (Matrix TX)       │
                    │  - Persistence (StorableMixin)│
                    │  - Schema (proto_schema)     │
                    │  - Auth (two-tier ABAC)      │
                    │  - Lifecycle events          │
                    │                              │
                    │  ┌───────────────────────┐   │
                    │  │  Pydantic AI Agent     │   │
                    │  │  - LLM loop           │   │
                    │  │  - Tool calling       │   │
                    │  │  - Structured output   │   │
                    │  │  - Usage tracking     │   │
                    │  └───────────────────────┘   │
                    └─────────────────────────────┘
```

### Tool Bridge: Pydantic AI ↔ Matrix TX

Pydantic AI tools are functions decorated with `@agent.tool`. PyBend internal tools are actors in the Matrix. The bridge: **for each tool in `__tools__`, create a wrapper function that sends a TX and awaits the response**.

```python
# AgentMixin creates this wrapper for each tool in __tools__
async def grants_create(ctx: RunContext[AgentDeps], **kwargs) -> dict:
    """Create a new grant. (docstring from schema)"""
    tx = TX(name='create', source=agent_addr, target='grants', data=kwargs)
    response = await ctx.deps.request(tx)  # NetworkAdapter.request() pattern
    return response.data
```

The tool's input schema comes from the model's JSON Schema (already generated). The tool's docstring comes from the schema description. The LLM sees standard MCP-format tools. When it calls one, the wrapper sends a TX through the Matrix — identical to what NetworkMCP does for external MCP clients.

### Actor-Based Orchestration (Grant Watch Flow)

No Pipeline class. Each agent is an actor that processes and forwards:

```
SchedulerActor ──TX(WAKE)──► ScraperAgent
                                 │
                    For each source URL:
                    scrape HTML (external tool)
                                 │
                     ──TX(ANALYZE)──► AnalyzerAgent
                                         │
                          Pydantic AI extracts grants
                          (output_type=Grant)
                                         │
                          ──TX(CREATE)──► Grant (ActorModel)
                                              │
                                    StorableMixin.create()
                                    _publish_lifecycle()
                                              │
                              ┌───────────────┴───────────────┐
                              ▼                               ▼
                      NetworkWebSocket              NotifierActor
                      (real-time UI)               (email/webhook)
```

Each agent knows its downstream target. The "pipeline" emerges from the actor graph.

### SchedulerActor

A static Actor (not a model — no storage needed) whose only job is waking agents on schedule:

```python
class SchedulerActor(Actor, auto_register=False):
    __addr__ = 'scheduler'

    async def REGISTER(self, data, tx):
        """Agent registers its schedule: {'addr': 'scraper', 'schedule': {'cron': '0 6 * * *'}}"""
        self._add_job(data['addr'], data['schedule'])

    async def SET_SCHEDULE(self, data, tx):
        """Agent dynamically changes its schedule via TX."""
        self._update_job(tx.source, data['schedule'])

    async def _wake(self, addr):
        """Fire-and-forget WAKE TX to agent's inbox."""
        await self.send(TX(name='WAKE', source=self.addr, target=addr, data={
            'triggered_at': datetime.now().isoformat()
        }))
```

**Registration flow**: When a model class with `__schedule__` is loaded, `AgentMixin.__init_subclass__()` queues a deferred registration. During app bootstrap (after Matrix is ready), queued schedules are sent as REGISTER TX to the SchedulerActor.

### Dependency Injection: AgentDeps

Pydantic AI's `RunContext[DepsType]` maps to a PyBend-specific deps dataclass:

```python
@dataclass
class AgentDeps:
    request: Callable   # NetworkAdapter.request() — for Matrix TX tool calls
    user: dict          # Current user (from TX meta, for auth context)
    agent_addr: str     # Agent's actor address
    run_id: str         # Current run UUID (for audit trail)
```

Tools receive `ctx.deps.request` to route TX through the Matrix. This keeps the Pydantic AI agent decoupled from Actor internals.

### Schema & Dump Integration

**Schema extension** (additive, zero modification to existing stages):
```python
@schema_extension(after='methods')
def agent(cls, schema: dict) -> dict:
    if not getattr(cls, '__agent__', False):
        return schema
    schema['agent'] = {
        'model': cls.__prompt__.get('model', ''),
        'tools': getattr(cls, '__tools__', []),
        'schedule': getattr(cls, '__schedule__', None),
        'status_field': 'status',
    }
    return schema
```

**Dump extension** (agent state in API responses):
```python
@dump_extension(after='instance_url')
def agent_status(instance, d: dict) -> dict:
    if getattr(instance.__class__, '__agent__', False):
        # Include latest run summary if available
        ...
    return d
```

---

## What Already Exists (No Code Needed)

Before designing anything, here's what the codebase already provides:

| Capability | How It Helps Agents | File |
|-----------|-------------------|------|
| **Actor/Matrix/TX** | Agents ARE actors. Tool calls ARE TX messages. | `actors/actor.py`, `matrix.py`, `tx.py` |
| **NetworkAdapter.request()** | Future-based req/resp over fire-and-forget messaging — agents use this for tool calls | `api/network_adapter.py` |
| **NetworkMCP._schema_to_mcp_tools()** | Schema → MCP tool definitions. Agents reuse this to discover tools | `api/network_mcp.py` |
| **Interceptors (use())** | Cost guards, rate limits, audit — composable TX middleware | `actors/actor.py` |
| **Mixin injection** | `__storable__ = True` injects StorableMixin. Same pattern for `__agent__ = True` | `models/proto_model.py` |
| **Schema pipeline** | `@schema_extension` adds agent metadata to JSON Schema | `models/proto_schema.py` |
| **Dump pipeline** | `@dump_extension` adds agent state to API responses | `models/proto_dump.py` |
| **Lifecycle events** | ActorModel publishes create/update/delete to subscribers (WS, AP) | `models/actor_model.py` |
| **Discovery** | `/.well-known/agent.json` already serves A2A Agent Cards | `api/discovery.py` |
| **Two-tier auth** | Boundary gate + resource-level OWNER check | `api/auth_interceptor.py` |

---

## Package Structure

```
src/pybend/core/agents/
├── __init__.py            # Re-exports: AgentMixin, AgentDeps, AgentRun, tool, SchedulerActor
├── agent_mixin.py         # AgentMixin — injected when __agent__ = True
│                          #   Wraps pydantic_ai.Agent
│                          #   Builds Matrix TX tool wrappers
│                          #   Manages AgentRun lifecycle
│                          #   Handles WAKE/RUN TX
├── deps.py                # AgentDeps dataclass (deps for Pydantic AI RunContext)
├── tools.py               # @tool decorator for external tools, ToolRegistry
├── scheduler.py           # SchedulerActor (APScheduler integration)
├── interceptors.py        # cost_guard, rate_limiter, circuit_breaker
├── schema_ext.py          # @schema_extension for agent metadata in JSON Schema
├── dump_ext.py            # @dump_extension for agent state in API responses
└── models/
    └── agent_run.py       # AgentRun model (run history, cost, tokens)
```

**Dependencies** (added to `pyproject.toml`):
- `pydantic-ai` — agent internals
- `apscheduler` — async scheduling for SchedulerActor

---

## Key Files Modified

| File | Change |
|------|--------|
| `src/pybend/core/models/proto_model.py` | Add `__agent__` detection in `__init_subclass__()`, inject `AgentMixin` |
| `src/pybend/core/app.py` | Wire SchedulerActor in `create_app()`, process deferred schedules |
| `src/pybend/__init__.py` | Re-export agent system public API |
| `pyproject.toml` | Add `pydantic-ai` and `apscheduler` to `[agents]` extras |

---

## Key Files Created

| File | Purpose |
|------|---------|
| `src/pybend/core/agents/agent_mixin.py` | Core mixin: wraps Pydantic AI Agent, tool bridge, run lifecycle |
| `src/pybend/core/agents/deps.py` | AgentDeps dataclass for Pydantic AI dependency injection |
| `src/pybend/core/agents/tools.py` | `@tool` decorator for external tools, ToolRegistry |
| `src/pybend/core/agents/scheduler.py` | SchedulerActor with APScheduler |
| `src/pybend/core/agents/interceptors.py` | Safety interceptors (cost, rate, circuit breaker) |
| `src/pybend/core/agents/schema_ext.py` | Schema pipeline extension for agent metadata |
| `src/pybend/core/agents/dump_ext.py` | Dump pipeline extension for agent state |
| `src/pybend/core/agents/models/agent_run.py` | AgentRun storable model |
| `src/pybend/core/agents/__init__.py` | Package re-exports |

---

## Implementation Phases

### Phase 1: Core Agent Primitives (~3-5 days)

1. **AgentMixin** (`agent_mixin.py`)
   - `__init_subclass__` hook in `proto_model.py` — detect `__agent__ = True`, inject mixin
   - Wrap `pydantic_ai.Agent` internally
   - Build Matrix TX tool wrappers from `__tools__` list (reuse `NetworkMCP._schema_to_mcp_tools()` for tool discovery)
   - Handle `WAKE` and `RUN` TX in actor inbox
   - Create/update `AgentRun` on each execution
   - Return structured results via `pydantic_ai.Agent.run()` with `output_type`

2. **AgentDeps** (`deps.py`)
   - Dataclass with `request` callable, `user` dict, `agent_addr`, `run_id`
   - Passed to `pydantic_ai.Agent.run(deps=...)` on each execution

3. **External tools** (`tools.py`)
   - `@tool` decorator that attaches `__tool__` metadata to functions
   - `ToolRegistry` for collecting external tools
   - AgentMixin registers both Matrix tools AND external tools on the Pydantic AI agent

4. **AgentRun model** (`models/agent_run.py`)
   - Storable model: `agent_id`, `task`, `status`, `started_at`, `completed_at`, `tokens_used`, `cost`, `result`

5. **Schema extension** (`schema_ext.py`)
   - `@schema_extension(after='methods')` adds `agent` block to JSON Schema

6. **Dump extension** (`dump_ext.py`)
   - `@dump_extension(after='instance_url')` adds agent status to API responses

7. **Tests**
   - AgentMixin with mock Pydantic AI agent
   - Tool bridge: Matrix TX tools, external tools
   - Schema extension output validation
   - AgentRun lifecycle

### Phase 2: SchedulerActor (~2-3 days)

1. **SchedulerActor** (`scheduler.py`)
   - Static Actor (not a model) with APScheduler
   - `REGISTER` handler — add cron job
   - `SET_SCHEDULE` handler — update/remove job
   - `_wake(addr)` — send WAKE TX
   - Graceful shutdown (cancel all jobs)

2. **`__schedule__` ClassVar** support
   - In `AgentMixin.__init_subclass__()`, queue deferred schedule registration
   - In `create_app()` or app startup, flush deferred schedules as REGISTER TX to SchedulerActor
   - Dynamic schedule: agents can send SET_SCHEDULE TX at any time

3. **Tests**
   - SchedulerActor REGISTER/SET_SCHEDULE handlers
   - WAKE TX delivery
   - `__schedule__` deferred registration flow
   - Multiple agents with different schedules

### Phase 3: Safety & Observability (~2-3 days)

1. **Interceptors** (`interceptors.py`)
   - `cost_guard` — per-run token/cost budget (uses Pydantic AI's `UsageLimits`)
   - `rate_limiter` — sliding window on LLM API calls
   - `circuit_breaker` — stop after N consecutive errors

2. **Lifecycle events**
   - `_publish_lifecycle('after_agent_run', ...)` — broadcast run results
   - WebSocket subscribers see real-time agent status
   - AgentRun records persisted for audit

3. **Tests**
   - Cost guard blocks over-budget runs
   - Rate limiter throttles rapid calls
   - Circuit breaker opens/closes
   - Lifecycle events received by subscribers

### Phase 4: Grant Watch Tool (~3-5 days)

1. **Models**
   - `Grant` — storable ActorModel (title, source_url, amount, deadline, eligibility, fingerprint)
   - `GrantSource` — storable ActorModel (url, name, scan_frequency)
   - `GrantScanner` — storable + agent ActorModel (ScraperAgent)
   - `GrantAnalyzer` — storable + agent ActorModel (AnalyzerAgent)

2. **External tools**
   - `web_scrape(url)` — httpx GET, return HTML
   - `web_search(query)` — search API wrapper (optional)

3. **Agent flow**
   - SchedulerActor WAKE → GrantScanner
   - GrantScanner scrapes all GrantSources, sends TX(ANALYZE) → GrantAnalyzer
   - GrantAnalyzer uses Pydantic AI with `output_type=list[Grant]` to extract grants
   - GrantAnalyzer deduplicates (fingerprint check via Grant.list)
   - New grants created via TX(CREATE) → Grant model
   - Grant LIFECYCLE events → WebSocket (real-time UI) + NotifierActor

4. **App bootstrap**
   ```python
   app = create_app(
       models=[Grant, GrantSource, GrantScanner, GrantAnalyzer, AgentRun],
       join_models=[(GrantScanner, AgentRun), (GrantAnalyzer, AgentRun)],
       storage='sqlite:///grants.db',
       routing='actor', ws=True,
       name='Grant Watch',
   )
   ```

5. **Tests**
   - End-to-end: WAKE → scrape → analyze → store → lifecycle
   - Mock LLM responses (Pydantic AI supports test mode)
   - Deduplication logic
   - Auth: only admin can trigger scans

---

## What the Developer Writes (End Goal)

```python
class Grant(ActorModel):
    __tablename__ = 'grants'
    __storable__ = True
    __access__ = {'read': ANYONE, 'create': AUTHENTICATED, 'update': ROLE('admin'), 'delete': ROLE('admin')}

    title: str
    source_url: str
    amount_min: Optional[float] = None
    amount_max: Optional[float] = None
    deadline: Optional[str] = None
    eligibility: str = ''
    description: str = ''
    status: str = 'new'
    fingerprint: str = ''

class GrantScanner(ActorModel):
    __tablename__ = 'scanners'
    __storable__ = True
    __agent__ = True
    __prompt__ = {
        'system': 'You scrape government websites for grant opportunities.',
        'model': 'anthropic:claude-sonnet-4-5-20250929',
    }
    __tools__ = ['grant_sources_list', 'web_scrape']
    __schedule__ = {'cron': '0 6 * * *'}  # Daily at 6 AM

    name: str
    status: str = Field(default='idle')

    @expose_route('/run', methods=['POST'], access=ROLE('admin'))
    async def run(self, task: str = 'Scan for new grants') -> str: ...
```

From these two model definitions: database tables, CRUD API, JSON Schema, frontend rendering, access control, MCP tool exposure, agent execution, scheduled scanning, run history, real-time status updates.

---

## Verification

1. **Unit tests**: `cd /workspace/src/pybend/core && pytest tests/unit/test_agent_*.py`
2. **Actor tests**: `cd /workspace/src/pybend/core && pytest actors/tests/`
3. **Integration**: Start server, trigger scan via `POST /scanners/1/run`, verify grants created
4. **Regression**: All existing 1,704 tests still pass
5. **MCP**: Verify agent tools appear in `GET /mcp/tools`
6. **WebSocket**: Verify agent status updates push to connected clients
