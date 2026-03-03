# Plan: PyBend Schema Agentic System — Architecture Design

## Context

**Priority shift**: Skip directly to v0.10 Wave 1 (Schema Agentic System). A client prospect needs a **grant/financing watch tool** — scrape government websites, analyze content via LLM agents, discover open grants. This becomes PyBend's first agentic product and trial run.

**Design constraint**: The system must be generic and schema-driven. The grant-watcher is the first app, but the architecture must support any agentic task.

**Key decisions** (from discussion):
- **Pydantic AI** is the internal agent engine (same Pydantic ecosystem)
- **Tool scoping**: Explicit allowlist + progressive discovery
- **LLM config**: Class-level default, per-instance override
- **Triggering**: Agents wake on TX message (actor-native)
- **Web fetching**: httpx default + optional Playwright tool

---

## Existing Infrastructure to Build On

| Pattern | Where | What It Gives Agents |
|---------|-------|---------------------|
| **Actor/Matrix/TX** | `actors/actor.py`, `matrix.py`, `tx.py` | Message routing, inbox/handler/send, transparent addressing |
| **Interceptors** | `actor.py` `use()` | Cost budgets, rate limits, tool scoping — same `async (TX)->TX` pattern |
| **Mixin injection** | `proto_model.py` `__init_subclass__` | `__agent__=True` triggers AgentMixin, like `__storable__=True` triggers StorableMixin |
| **Schema pipeline** | `proto_schema.py` `@schema_extension` | Agent metadata flows through schema |
| **MCP tools** | `network_mcp.py` `_schema_to_mcp_tools()` | Model CRUD + custom methods auto-generate as tool specs |
| **NetworkAdapter** | `network_adapter.py` | request/response correlation via Future |
| **ActorModel** | `actor_model.py` | Messaging + CRUD + lifecycle events + two-tier auth |
| **Lifecycle events** | `actor_model.py` `_publish_lifecycle` | Agents can subscribe to model changes |

---

## Architecture: Three Layers

### Layer 1: Agent Definition (developer-facing)

The developer writes an ActorModel with `__agent__ = True`:

```python
class GrantWatcher(ActorModel):
    __tablename__ = 'grant_watchers'
    __storable__ = True
    __agent__ = True
    __llm__ = 'anthropic:claude-sonnet-4-5-20250929'   # Class default, instance-overridable
    __prompt__ = {
        'system': 'You discover government grant opportunities.',
    }
    __tools__ = ['grants_create', 'grants_list', 'sources_list', 'web_fetch']
    __constraints__ = {
        'max_iterations': 20,
        'max_cost_usd': 0.50,
        'timeout_seconds': 300,
    }

    name: str
    status: str = 'idle'
    last_run: Optional[datetime] = None
```

**What `__agent__ = True` triggers** (via `__init_subclass__`):
- Injects `AgentMixin` (adds `RUN` handler, `_build_agent()`, `_execute_tool()`)
- Registers `agent` schema extension stage (agent metadata in JSON Schema)
- Agent responds to `TX(name='RUN')` messages

### Layer 2: Pydantic AI Bridge (framework internals)

**AgentMixin** bridges PyBend's actor system to Pydantic AI:

```
TX(name='RUN', target='grant_watchers', data={task: '...'})
    -> ActorModel.inbox() -> handler() -> AgentMixin.RUN()
        -> _build_agent() creates pydantic_ai.Agent:
            - model from __llm__
            - system_prompt from __prompt__
            - tools generated from __tools__ allowlist
            - deps carries Matrix ref + auth context
            - output_type from __result_type__ (default: str)
        -> agent.run(task, deps=AgentDeps(matrix, user, run))
            -> Pydantic AI manages ReAct loop internally
            -> Tool calls -> _execute_tool() -> TX through Matrix
            -> Results fed back to LLM automatically
        -> AgentRun record created with full trace
    -> TX.reply(data={result, run_id, cost})
```

**Tool generation** — the core bridge:

Pydantic AI needs Python tool functions. PyBend auto-generates them from the same schema specs that generate MCP tools:

```python
# AgentMixin._build_tools() generates tool functions from __tools__ allowlist:

# For 'grants_create' in __tools__:
#   1. Look up 'grants' model in registered_models
#   2. Read schema properties (name: str, amount: float, ...)
#   3. Generate a tool function:

@agent.tool_plain
async def grants_create(title: str, amount: float, source_url: str, ...) -> dict:
    """Create a new Grant record."""
    tx = TX(name='create', target='grants', data={...})
    result = await matrix_request(tx)  # Routes through Matrix
    return result.data

# For 'web_fetch' in __tools__ (built-in tool):
@agent.tool_plain
async def web_fetch(url: str) -> str:
    """Fetch and return the text content of a URL."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        return resp.text
```

**Key insight**: Tool calls route through Matrix as TX messages. This means:
- Auth interceptors apply (agents respect access rules)
- Lifecycle events fire (other systems can react)
- Same code path as HTTP/MCP requests (no special agent-only routes)
- Tracing/observability via interceptors

**AgentDeps** — dependency injection for Pydantic AI:

```python
@dataclass
class AgentDeps:
    matrix: Matrix          # For routing tool TXs
    user: dict              # Auth context (who triggered the agent)
    run: AgentRun           # Current run record (for tracing)
    constraints: dict       # Budget/iteration limits
```

### Layer 3: Agent Runs & Tracing

**AgentRun** — auto-generated model for run history:

```python
class AgentRun(ActorModel):
    __tablename__ = 'agent_runs'
    __storable__ = True

    agent_type: str              # 'GrantWatcher'
    agent_id: Optional[int]      # FK to agent instance
    task: str                    # What was requested
    status: str                  # 'running', 'completed', 'failed', 'budget_exceeded'
    steps: list[dict] = []       # [{role, content, tool_calls, tool_results}]
    result: Optional[str]        # Final output
    cost_usd: float = 0.0
    tokens_used: int = 0
    started_at: datetime
    completed_at: Optional[datetime] = None
```

Gives: run history via CRUD, queryable via CLI, schema-driven UI, lifecycle events on completion.

---

## Progressive Tool Discovery

`__tools__` is an explicit allowlist, but agents can discover available tools at runtime:

```python
__tools__ = [
    'grants_create',       # Specific tool
    'grants_list',         # Specific tool
    'sources_*',           # Wildcard: all Source tools
    'web_fetch',           # Built-in tool
]
```

**Discovery mechanism**: A built-in `discover_tools` meta-tool that returns the filtered list of available tools based on the allowlist + access rules:

```python
@agent.tool_plain
async def discover_tools() -> list[dict]:
    """List all tools available to this agent."""
    return [{'name': t.name, 'description': t.description, 'schema': t.input_schema}
            for t in resolved_tools]
```

---

## Triggering: TX-Native

Agents wake up on TX messages. No cron, no manual API — pure actor messaging:

```python
# Trigger via code:
await GrantWatcher.send(TX(name='RUN', source='scheduler', target='grant_watchers',
                           data={'task': 'Scan all sources for new grants'}))

# Trigger via HTTP (Level 3 routing):
POST /grant_watchers/run  {"task": "Scan all sources"}

# Trigger via lifecycle event (reactive):
Source._subscribers.append('grant_watchers')
# -> When a Source is created, GrantWatcher receives LIFECYCLE TX
# -> GrantWatcher.LIFECYCLE handler can trigger a RUN

# Trigger via another agent (multi-agent):
await self.send(TX(name='RUN', target='grant_watchers', data={...}))
```

The `RUN` handler is added by AgentMixin. Custom handlers can also trigger runs:

```python
class GrantWatcher(ActorModel):
    __agent__ = True

    async def LIFECYCLE(self, data, tx):
        """React to model changes — e.g., new source added."""
        if data['event'] == 'after_create' and 'sources' in tx.source:
            new_source = data['entity']
            await self.send(TX(name='RUN', target=self.addr,
                              data={'task': f"Scan new source: {new_source['url']}"}))
```

---

## Safety via Interceptors

Same `async (TX) -> TX` pattern as `auth_interceptor`:

```python
# Budget enforcement (registered on agent's send or on a per-run basis)
async def budget_guard(tx: TX) -> TX:
    run = tx.meta.get('agent_run')
    if run and run.cost_usd >= run.constraints.get('max_cost_usd', float('inf')):
        return tx.error("Budget exceeded", code=429)
    return tx

# Tool scope enforcement
async def scope_guard(tx: TX) -> TX:
    allowed = tx.meta.get('allowed_tools', [])
    tool_name = f"{tx.target}_{tx.name}"
    if allowed and not _matches_allowlist(tool_name, allowed):
        return tx.error(f"Tool '{tool_name}' not in agent scope", code=403)
    return tx
```

**Pydantic AI also provides** `UsageLimits(request_limit=N, response_tokens_limit=N)` — these compose with our interceptors for defense in depth.

---

## Grant-Watching App: Complete Example

```python
# models.py
from pybend import ActorModel, Field, create_app
from datetime import datetime
from typing import Optional

class Source(ActorModel):
    __tablename__ = 'sources'
    __storable__ = True
    name: str
    url: str
    category: str = 'government'
    last_scanned: Optional[datetime] = None

class Grant(ActorModel):
    __tablename__ = 'grants'
    __storable__ = True
    title: str
    amount: Optional[float] = None
    deadline: Optional[str] = None
    source_url: str
    eligibility: str = ''
    description: str = ''
    status: str = 'discovered'

class GrantWatcher(ActorModel):
    __tablename__ = 'grant_watchers'
    __storable__ = True
    __agent__ = True
    __llm__ = 'anthropic:claude-sonnet-4-5-20250929'
    __prompt__ = {
        'system': """You are a grant discovery agent. Your job:
1. List configured sources (sources_list)
2. Fetch each source URL (web_fetch)
3. Analyze the content for open grant opportunities
4. Create a Grant record for each new one (grants_create)
5. Check existing grants to avoid duplicates (grants_list)
Be thorough. Extract: title, amount, deadline, eligibility, description.""",
    }
    __tools__ = ['sources_list', 'grants_create', 'grants_list', 'web_fetch']
    __constraints__ = {'max_iterations': 30, 'max_cost_usd': 1.00}

    name: str
    status: str = 'idle'

# main.py
app = create_app(
    models=[Source, Grant, GrantWatcher],
    storage="sqlite:///grants.db",
)
```

**What happens:**
1. Developer seeds sources: `POST /sources {"name": "BPI France", "url": "https://..."}`
2. Trigger agent: `POST /grant_watchers/run {"task": "Scan all sources"}`
3. Agent wakes (TX -> inbox -> RUN handler)
4. Pydantic AI runs ReAct loop:
   - Calls `sources_list` -> TX -> Matrix -> Source.list() -> returns sources
   - Calls `web_fetch(url)` for each source -> httpx fetch -> returns HTML text
   - LLM analyzes content, identifies grants
   - Calls `grants_create(title=..., amount=..., ...)` -> TX -> Matrix -> Grant.create()
   - Calls `grants_list` to check duplicates before creating
5. Run completes -> AgentRun stored with full trace
6. Response: `{result: "Found 3 new grants", run_id: 42, cost_usd: 0.35}`

---

## New Files

| File | Purpose |
|------|---------|
| `src/pybend/core/agents/__init__.py` | Package exports: AgentMixin, AgentRun, AgentDeps |
| `src/pybend/core/agents/mixin.py` | AgentMixin: `RUN` handler, `_build_agent()`, `_build_tools()`, `_execute_tool()` |
| `src/pybend/core/agents/run.py` | AgentRun model: run history, steps, cost tracking |
| `src/pybend/core/agents/deps.py` | AgentDeps dataclass for Pydantic AI dependency injection |
| `src/pybend/core/agents/tools.py` | Tool function generator: schema -> Pydantic AI tool functions |
| `src/pybend/core/agents/builtins.py` | Built-in tools: `web_fetch`, `web_search` |
| `src/pybend/core/agents/schema_ext.py` | `@schema_extension`: agent metadata in JSON Schema |
| `src/pybend/core/agents/interceptors.py` | Budget guard, scope guard interceptors |

## Modified Files

| File | Change |
|------|--------|
| `src/pybend/core/models/proto_model.py` | `__init_subclass__()`: detect `__agent__=True`, inject AgentMixin |
| `src/pybend/core/app.py` | Register AgentRun model, wire agent tooling in `build()` |
| `src/pybend/__init__.py` | Re-export AgentMixin, AgentRun |
| `pyproject.toml` | Add `pydantic-ai` dependency (+ optional `[browser]` extra for Playwright) |

---

## Phased Implementation

### Phase 0: Core Agent Loop (~3-5 days)
- `AgentMixin` with `RUN` handler -> Pydantic AI agent
- Tool function generation from model schemas
- `AgentRun` model for tracing
- `__agent__=True` mixin injection in `__init_subclass__`
- `web_fetch` built-in tool (httpx)
- Budget interceptor via Pydantic AI's `UsageLimits`

**Ships**: A working agent that runs a ReAct loop, calls model CRUD tools via Matrix, and stores run traces. Enough to build a proof-of-concept grant-watcher.

### Phase 1: Production features (~1-2 weeks)
- `web_search` built-in tool
- `@schema_extension` for agent metadata in schema output
- Scope guard interceptor
- Streaming support (SSE for long-running agent runs)
- `web_fetch_js` (Playwright) as optional tool
- `__result_type__` for structured output validation

**Ships**: The grant-watching app is fully buildable and deployable.

### Phase 2: Multi-agent + advanced (~2-3 weeks)
- Agent-to-agent via TX messages (agents as tools for other agents)
- Orchestrator pattern (supervisor spawns/coordinates workers)
- Persistent memory (conversation history across runs)
- Context pruning strategies
- Progressive tool discovery (wildcard patterns, `discover_tools` meta-tool)

### Phase 3: Observability + ecosystem (~1-2 weeks)
- Agent dashboard (active agents, costs, completion rates)
- A2A Agent Card enhancements in `discovery.py`
- OpenTelemetry / Logfire integration (Pydantic AI native)
- Agent delegation protocol

---

## How This Follows PyBend's Philosophy

| Principle | How the agentic system embodies it |
|-----------|-----------------------------------|
| **Model is the app** | `__agent__=True` on a model = complete agent definition |
| **Zero to working** | Define model, get agent. No config files, no wiring, no boilerplate |
| **Primitives, not opinions** | Developer controls prompt, tools, constraints. Framework provides execution |
| **Backend is authoritative** | Agent tools, access rules, schemas — all from backend models |
| **Transparent, not magical** | Every tool call is a TX message, traceable through Matrix |
| **Modular** | Agent definition (model) is separate from execution (Pydantic AI) and tools (Matrix routing) |

---

## Verification Plan

1. **Unit tests**: AgentMixin.RUN() with mock Pydantic AI agent, tool routing, budget enforcement
2. **Integration test**: Full ReAct loop — agent creates records via tool calls, results in DB
3. **Grant-watcher E2E**: Define models, seed sources, trigger RUN, verify grants created
4. **Safety tests**: Budget exceeded -> stops, scope violation -> rejected, UsageLimits hit -> stops
5. **Schema test**: `GET /GrantWatcher` returns schema with agent metadata section
6. **Multi-trigger test**: TX trigger, HTTP trigger, lifecycle trigger all produce same behavior
