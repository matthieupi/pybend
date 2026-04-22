# Agent Components & Pygentic App — Feature Plan

## Context

After the module split (v0.10), the `n3tx-agents` package needs frontend components that give visibility into agent reasoning. Currently, `ntx-chat.js` is a basic floating chat panel that only renders text deltas — tool calls, thinking tokens, and intermediate results are invisible to the user. This plan covers three tightly coupled deliverables: rich agent streaming (backend), agent-specific frontend components, and a new "Pygentic" kitchen-sink example app.

---

## Deliverable 1: Rich Agent Streaming (Backend Enhancement)

### Problem

`run_stream()` in `mixin.py` (line 532-541) only uses `stream_text(delta=True)`:

```python
async with ai_agent.run_stream(task, **run_kwargs) as result:
    async for text in result.stream_text(delta=True):
        yield {'name': 'text', 'data': {'text': text}, 'meta': {'stream': True, 'seq': seq}}
```

Source has explicit TODOs at lines 536 and 551-553 acknowledging this gap.

### Target Event Spectrum

```python
# Tool call started
{'name': 'tool_call', 'data': {'tool': 'grants_list', 'args': {...}, 'call_id': '...'}, 'meta': {'stream': True, 'seq': N}}

# Tool result returned
{'name': 'tool_result', 'data': {'tool': 'grants_list', 'result': '...', 'call_id': '...'}, 'meta': {'stream': True, 'seq': N}}

# Text delta (unchanged)
{'name': 'text', 'data': {'text': '...'}, 'meta': {'stream': True, 'seq': N}}

# Thinking token (if model supports it)
{'name': 'thinking', 'data': {'text': '...'}, 'meta': {'stream': True, 'seq': N}}

# Done (unchanged, but enriched)
{'name': 'done', 'data': {'answer': '...', 'usage': {...}, 'tool_calls': N}, 'meta': {'stream': True, 'stream_end': True, 'seq': N}}
```

### Approach: Use pydantic-ai's Stream Events

Pydantic-ai v1.66+ provides typed stream events via the raw stream response:

| Event Type | Fields | Meaning |
|---|---|---|
| `PartStartEvent` | `index, part` | New message part started |
| `PartDeltaEvent` | `index, delta` | Part content delta (text, tool call args, thinking) |
| `FunctionToolCallEvent` | `part: ToolCallPart` | LLM decided to call a tool |
| `FunctionToolResultEvent` | `result, content` | Tool returned |
| `ThinkingPart` / `ThinkingPartDelta` | `content` | Reasoning tokens |

Replace `stream_text(delta=True)` with iteration over `result._raw_stream_response` or use `agent.iter()` graph API which yields `UserPromptNode`, `ModelRequestNode`, `CallToolsNode`, etc.

**Preferred approach**: `agent.iter()` — it's the public API for full visibility into each step. Restructure `run_stream()` to iterate graph nodes:

```python
async with ai_agent.iter(task, **run_kwargs) as agent_run:
    async for node in agent_run:
        if Agent.is_model_request_node(node):
            # Iterate streaming events within this node
            async with node.stream(agent_run.ctx) as request_stream:
                async for event in request_stream:
                    if isinstance(event, PartStartEvent):
                        if isinstance(event.part, ToolCallPart):
                            yield {'name': 'tool_call', 'data': {...}}
                        elif isinstance(event.part, ThinkingPart):
                            yield {'name': 'thinking', 'data': {...}}
                    elif isinstance(event, PartDeltaEvent):
                        if isinstance(event.delta, TextPartDelta):
                            yield {'name': 'text', 'data': {'text': event.delta.content_delta}}
                        elif isinstance(event.delta, ThinkingPartDelta):
                            yield {'name': 'thinking', 'data': {'text': event.delta.content_delta}}
        elif Agent.is_call_tools_node(node):
            # Tool execution happens here
            for tool_result in node.tool_results:
                yield {'name': 'tool_result', 'data': {...}}
```

### Files to Modify

- `packages/n3tx-agents/src/n3tx_agents/mixin.py` — `run_stream()` rewrite (lines 453-581)
- `packages/n3tx-agents/src/n3tx_agents/actor.py` — Add `agentic_stream()` override on AgentActor (matching existing `agentic()` override pattern at lines 103-135)
- SSE handlers are already generic — `routes_fastapi.py` and `network_api.py` pass through whatever dict the generator yields, no changes needed there
- `HTTP.stream()` in the frontend already parses any JSON chunk — no changes needed

### Backward Compatibility

The SSE wire format is stable: `event: chunk|done|error` with `data: {json}`. Existing frontends that only handle `name: 'text'` will simply ignore `tool_call`/`tool_result`/`thinking` events. The `done` chunk is unchanged. Zero breaking changes.

---

## Deliverable 2: Agent-Specific Frontend Components

### Component 1: `ntx-agent-live.js` — Real-Time Agent Activity View

The "window into the agent's mind." Shows what an agent is currently doing: thinking, tool calls in progress, results flowing back, text generation.

**Placement**: `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js`

**Design**:
- Extends `Component` (not NTTStream) — needs custom rendering for each event type, not the stream-text append pattern
- Attributes: `model`, `ref` (entity address), `method` (default: `"agentic_stream"`)
- Uses `HTTP.stream()` directly (same approach as `ntx-chat.js`) for SSE
- Receives typed events from Deliverable 1 and renders each differently:

| Event | Rendering |
|---|---|
| `thinking` | Collapsible "Thinking..." section, italic text, subtle background |
| `tool_call` | Collapsible card: tool name as header, args as JSON tree (starts "running...") |
| `tool_result` | Result appended under its matching `tool_call` card (matched by `call_id`) |
| `text` | Progressive text output (like current ntx-stream) |
| `done` | Final summary with usage stats (tokens, tool calls count) |

- Auto-scrolls to bottom as new events arrive
- Collapsible sections default open during streaming, can be collapsed after
- CSS in component shadow DOM (self-contained)

**Interaction with schema**: Reads `schema.agent.enabled` and `schema.agent.methods` to discover streaming capability. If `agentic_stream` is in methods, enables the live view. Falls back gracefully if agent section is absent.

### Component 2: `ntx-agent-edit.js` — Agent Configuration Editor

A specialized editor for `AgentActor` instances that goes beyond standard `ntx-item` edit mode.

**Placement**: `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-edit.js`

**Design**:
- Extends `NTTElement` — participates in the entity lifecycle (value, schema, ref, save)
- Specialized sections rendered in `render()`:
  - **System prompt** — large textarea with monospace font
  - **Tool picker** — checkbox list of available tools (from schema discovery via `GET /{model}` for all registered models). Toggle on/off, auto-creates/removes `AgentTool` join records
  - **LLM selector** — dropdown (populated from a config endpoint or hardcoded list)
  - **Constraints** — key-value editor for `max_iterations`, `temperature`, etc.
  - **Test button** — runs a quick `agentic()` call to validate config, shows result inline
- Save delegates to standard CRUD (PUT on the entity)

### Component 3: Enhance `ntx-chat.js`

Modify the existing chat component to handle new typed events:

**File**: `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js`

Changes to `_sendStream()` (lines 130-171):
- Dispatch on `chunk.name` instead of treating everything as text:
  - `tool_call` → render as a compact collapsible card within the chat flow: `🔧 Calling grants_list...`
  - `tool_result` → append result summary under the tool_call card
  - `thinking` → subtle "thinking..." indicator (animated dots or italic text)
  - `text` → unchanged (progressive text append)
  - `done` → unchanged (cleanup + show answer if no text was streamed)
- Add CSS for tool call cards and thinking indicators

---

## Deliverable 3: Pygentic Example App

A kitchen-sink app at `/workspace/examples/pygentic/` showcasing all agent features.

### Models

```python
# User — standard (copy from examples/chat/models/user.py)
class User(BaseUser, ActorModel):
    __tablename__ = 'users'
    __abstract__ = False
    __ui__ = {'renderer': {'item': 'ntx-user'}}
    image: str = Field(default='...')

# Task — domain model with agent capabilities
class Task(ActorModel):
    __tablename__ = 'tasks'
    __storable__ = True
    __agent__ = True  # Demonstrates AgentMixin on domain models
    __access__ = {'read': ANYONE, 'create': AUTHENTICATED, 'update': OWNER, 'delete': ROLE('admin')}
    __ui__ = {'field_order': ['title', 'status', 'priority', 'description', 'assignee']}

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default='', json_schema_extra={'ui': {'widget': 'textarea'}})
    status: str = Field(default='open')  # open, in_progress, done
    priority: str = Field(default='medium')  # low, medium, high, critical
    assignee: str = Field(default='')

    @expose_route('/analyze', methods=['POST'], stream=True, access=AUTHENTICATED)
    async def analyze(self, user: User = None):
        """Uses agentic_stream to analyze the task."""
        async for chunk in self.agentic_stream(task=f'Analyze this task: {self.title}. {self.description}'):
            yield chunk

# Memory — placeholder (full implementation in memory plan)
class Memory(ActorModel):
    __tablename__ = 'memories'
    __storable__ = True
    content: str = Field(min_length=1)
    category: str = Field(default='fact')
    agent_id: str = Field(default='')
    tags: list = Field(default=[])
    relevance: float = Field(default=1.0, ge=0.0, le=1.0)

# AgentActor + AgentTool from n3tx_agents (used directly)
```

### Directory Structure

```
examples/pygentic/
├── __init__.py
├── config.py                # Copy from examples/chat/config.py, DB: pygentic.db
├── main.py                  # create_app with routing='actor', ws=True
├── seed.py                  # 3 users, 2 agents, 5 tasks, tool assignments
├── models/
│   ├── __init__.py          # re-exports
│   ├── user.py              # BaseUser + ActorModel
│   ├── task.py              # Task with __agent__ = True
│   └── memory.py            # Memory placeholder model
├── static/
│   ├── index.html           # Agent-focused dashboard layout
│   └── components/          # App-specific overrides (if any)
└── tests/
    ├── __init__.py
    ├── conftest.py           # Standard pattern (test_db, seed_data, client, tokens)
    ├── helpers.py            # auth_header()
    ├── test_boot.py          # Smoke tests
    ├── test_schema_endpoints.py
    ├── test_task_crud.py     # CRUD for Task
    ├── test_agent_crud.py    # CRUD for AgentActor
    ├── test_agent_run.py     # agentic() with TestModel
    └── test_agent_stream.py  # agentic_stream() with typed events
```

### main.py

```python
import config
from n3tx_core.app import create_app
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_agents import AgentActor, AgentTool
from models import User, Task, Memory

storage = SQLiteStorage(config.DB_PATH)
app = create_app(
    models=[User, Task, Memory, AgentTool, AgentActor],
    join_models=[(AgentActor, AgentTool)],
    storage=storage,
    routing='actor',
    ws=True,
    static_dir=os.path.join(_HERE, 'static'),
    jwt_secret=config.JWT_SECRET,
    name="Pygentic",
    version="0.10.0",
    description="Agent management, live view, and memory showcase",
)
```

### Seed Data

- 3 users (alice, bob, charlie)
- 2 agents: "General Assistant" (tools: tasks, memories), "Task Analyzer" (tools: tasks)
- 5 tasks with varied status/priority
- AgentTool records linking agents to their tools

### Frontend (index.html)

Agent-focused dashboard with:
- Left sidebar: model navigation (standard `ntx-sidebar`)
- Main area: `ntx-list` for Tasks (with `ntx-stream` for the `/analyze` method)
- Right panel: `ntx-agent-live` bound to selected agent — shows real-time activity
- Bottom panel: `ntx-chat` for quick agent interaction
- Agent management via `ntx-agent-edit` (accessible from agent list view)

---

## Implementation Order

### Phase 1: Rich Streaming Backend (Deliverable 1)
1. Research pydantic-ai `agent.iter()` API — confirm event types and async iteration pattern
2. Rewrite `run_stream()` in `mixin.py` to use `agent.iter()` with typed event yielding
3. Add `agentic_stream()` override to `AgentActor` (matching existing `agentic()` pattern)
4. Test with existing `ntx-stream.js` — verify backward compat (text events still work)
5. Write unit tests for new event types using `pydantic_ai.models.test.TestModel`

### Phase 2: Frontend Components (Deliverable 2)
6. Create `ntx-agent-live.js` — event-dispatching streaming view
7. Enhance `ntx-chat.js` — add tool_call/tool_result/thinking rendering
8. Create `ntx-agent-edit.js` — specialized agent editor
9. Test components manually with grants example app

### Phase 3: Pygentic App (Deliverable 3)
10. Create app skeleton: config.py, main.py, models/, tests/
11. Define Task model with `__agent__ = True` and `/analyze` streaming method
12. Create seed.py with agents, tasks, tool assignments
13. Build custom index.html with agent dashboard layout
14. Write test suite (conftest, CRUD, agent run, streaming)
15. Verify all components work end-to-end

### Dependencies

```
Phase 1 (streaming) → Phase 2 (components need typed events)
Phase 1 + Phase 2 → Phase 3 (Pygentic uses both)
Memory plan (parallel) → Phase 3 (Memory model integrated into Pygentic)
```

---

## Key Design Decisions

1. **`agent.iter()` over raw stream events** — public API, future-proof, gives graph-level visibility (tool execution nodes, not just stream deltas)
2. **`ntx-agent-live` extends Component, not NTTStream** — NTTStream's append-text pattern doesn't fit multi-event-type rendering. New component needs its own rendering logic per event type.
3. **`ntx-agent-edit` extends NTTElement** — participates in entity lifecycle (value/schema/ref/save), just overrides render() for specialized layout
4. **`ntx-chat` enhanced, not replaced** — it already works for basic interaction. Adding typed event rendering is additive.
5. **Pygentic uses `routing='actor'` + `ws=True`** — full Level 3 with WebSocket push for live updates
6. **Memory model is a placeholder in Pygentic** — full memory architecture is designed in the parallel memory plan
