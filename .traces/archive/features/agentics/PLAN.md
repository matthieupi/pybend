# Agent Components, Memory & Pygentic — Consolidated Plan

## Context

After the module split (v0.10), the `n3tx-agents` package needs three things: (1) frontend visibility into agent reasoning, (2) persistent agent memory, and (3) a kitchen-sink example app to prototype and evaluate these features. Currently `run_stream()` only yields text deltas (TODO at mixin.py:536), `ntx-chat.js` renders nothing for tool calls or thinking, and agents have no memory between runs.

**Detailed sub-plans**: `agent-components.md` and `agent-memory.md` (in this directory)

---

## Phase 1: Rich Agent Streaming (Backend)

**Goal**: `run_stream()` yields typed events — tool_call, tool_result, thinking, text, done.

**File**: `packages/n3tx-agents/src/n3tx_agents/mixin.py` (lines 453-581)

Replace `stream_text(delta=True)` with pydantic-ai's `agent.iter()` graph API:

```python
async with ai_agent.iter(task, **run_kwargs) as agent_run:
    async for node in agent_run:
        if Agent.is_model_request_node(node):
            async with node.stream(agent_run.ctx) as stream:
                async for event in stream:
                    # yield typed chunks: tool_call, thinking, text
        elif Agent.is_call_tools_node(node):
            # yield tool_result chunks
```

Event format (backward-compatible — existing frontends ignore unknown names):
- `{'name': 'tool_call', 'data': {'tool': '...', 'args': {...}, 'call_id': '...'}, 'meta': {stream, seq}}`
- `{'name': 'tool_result', 'data': {'tool': '...', 'result': '...', 'call_id': '...'}, 'meta': {stream, seq}}`
- `{'name': 'thinking', 'data': {'text': '...'}, 'meta': {stream, seq}}`
- `{'name': 'text', ...}` and `{'name': 'done', ...}` unchanged

Also add `agentic_stream()` override to `AgentActor` in `packages/n3tx-agents/src/n3tx_agents/actor.py` (matching existing `agentic()` override pattern at line 103).

**No SSE/transport changes needed** — `routes_fastapi.py` and `HTTP.stream()` pass through any JSON dict.

---

## Phase 2: Agent Memory Mechanism

**Goal**: External actor-managed memory with TX-based store/recall and LLM tool access.

### New Files

| File | What |
|------|------|
| `packages/n3tx-agents/src/n3tx_agents/memory_model.py` | `Memory(ActorModel)` — content, category, agent_id, tags, relevance, timestamps |
| `packages/n3tx-agents/src/n3tx_agents/memory_manager.py` | `MemoryManager(Actor)` — TX handlers: store, recall, search, forget, decay |
| `packages/n3tx-agents/src/n3tx_agents/memory_tools.py` | `make_memory_tools(agent_id)` — closured Pydantic AI Tool objects |

### Modified Files

| File | Change |
|------|--------|
| `packages/n3tx-agents/src/n3tx_agents/mixin.py` | Memory config in `agentic()`, `extra_tools` param in `run()`/`run_stream()`, pre-run recall, post-run store |
| `packages/n3tx-core/src/n3tx_core/config.py` | `'memory': False` in AGENT_DEFAULTS |
| `packages/n3tx-agents/src/n3tx_agents/__init__.py` | Export Memory, MemoryManager, setup_memory |
| `packages/n3tx-agents/src/n3tx_agents/schema_ext.py` | Add `memory` to safe_keys |

### TX Protocol

| Message | Request | Response |
|---------|---------|----------|
| `store` | `{content, category?, agent_id?, tags?}` | Memory model_response |
| `recall` | `{query, agent_id?, category?, limit?}` | `{memories: [...], count}` |
| `forget` | `{id?}` or `{agent_id, category?}` | `{deleted: id}` or `{deleted_count}` |
| `decay` | `{agent_id?, decay_rate?}` | `{updated_count}` |

### Integration Flow

1. `agentic()` resolves `memory` config (3-tier cascade: AGENT_DEFAULTS < `__agent__` < kwargs)
2. If enabled: pre-run `recall` TX → inject memories into prompt
3. `make_memory_tools(agent_id)` added as `extra_tools` → agent can store/recall during reasoning
4. Optional post-run `store` TX with summary (off by default)

### Config

```python
__agent__ = {'memory': True}                              # boolean
__agent__ = {'memory': {'preload': True, 'tools': True}}  # fine-grained
await product.agentic(task='...', memory=True)             # call-time override
```

---

## Phase 3: Frontend Agent Components

**Goal**: Three components in `packages/n3tx-agents/src/n3tx_agents/static/components/`

### `ntx-agent-live.js` — Real-Time Agent Activity View

Extends `Component`. Attributes: `model`, `ref`, `method`. Uses `HTTP.stream()` for SSE.

Dispatches on `chunk.name`:
- `thinking` → collapsible italic section
- `tool_call` → collapsible card with tool name + args JSON
- `tool_result` → result appended under matching tool_call (by `call_id`)
- `text` → progressive text output
- `done` → usage summary

### `ntx-agent-edit.js` — Agent Configuration Editor

Extends `NTTElement`. Specialized sections:
- System prompt (large textarea)
- Tool picker (checkboxes, auto-creates AgentTool join records)
- LLM selector dropdown
- Constraints key-value editor
- Test button (quick `agentic()` call)

### `ntx-chat.js` Enhancement

Modify `_sendStream()` (lines 130-171) to dispatch on `chunk.name`:
- `tool_call` → compact collapsible card in chat flow
- `tool_result` → result under tool_call card
- `thinking` → subtle animated indicator
- `text`/`done` → unchanged

---

## Phase 4: Pygentic Example App

**Goal**: Kitchen-sink app at `examples/pygentic/` showcasing all features.

### Structure

```
examples/pygentic/
├── config.py               # DB: pygentic.db, routing='actor', ws=True
├── main.py                 # create_app with all models
├── seed.py                 # 3 users, 2 agents, 5 tasks, tool wiring
├── models/
│   ├── user.py             # BaseUser + ActorModel
│   ├── task.py             # Task with __agent__=True, @expose_route('/analyze', stream=True)
│   └── memory.py           # Memory model (from n3tx_agents)
├── static/
│   └── index.html          # Agent dashboard: ntx-agent-live + ntx-chat + ntx-agent-edit
└── tests/
    ├── conftest.py          # Standard fixtures
    ├── test_task_crud.py
    ├── test_agent_crud.py
    ├── test_agent_run.py    # TestModel
    ├── test_agent_stream.py # Typed events
    └── test_memory.py       # Memory CRUD + recall
```

### Models

- `User` — standard (BaseUser + ActorModel)
- `Task` — domain model with `__agent__ = True`, `__agent__ = {'memory': True}`, streaming `/analyze` method
- `Memory` — from n3tx_agents package
- `AgentActor` + `AgentTool` — from n3tx_agents

---

## Execution Order

```
Phase 1 (streaming)  ──┐
                       ├──→ Phase 3 (frontend components)  ──→ Phase 4 (Pygentic)
Phase 2 (memory)     ──┘
```

Phases 1 and 2 are independent — can be built in parallel. Phase 3 needs Phase 1 (typed events). Phase 4 needs all three.

---

## Verification

1. **Streaming**: Run grants example, trigger `agentic_stream` with a real LLM — verify `tool_call`/`tool_result` events appear in SSE output. Test with `TestModel` for unit tests.
2. **Memory**: Unit tests for Memory CRUD, MemoryManager TX handlers, memory tools routing. Integration test: `agentic()` with `memory=True` — verify pre-run recall injects into prompt.
3. **Components**: Manual browser testing in Pygentic app — trigger an agent run, observe live view rendering tool calls/thinking/text. Edit an agent via ntx-agent-edit, verify save persists.
4. **Pygentic E2E**: `python3 -m pytest examples/pygentic/tests/ -v` — all CRUD, agent run, streaming, memory tests pass. Browser: open dashboard, run agent, observe live activity, check memory persistence across runs.
