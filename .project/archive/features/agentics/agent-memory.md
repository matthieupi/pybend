# Agent Memory Mechanism — Feature Plan

## Context

Agents in N3TX need persistent memory — the ability to recall knowledge from previous interactions and store new insights during reasoning. Currently, every agent run starts from scratch with only the system prompt and task. Memory is managed by an external actor, uses TX for data exchange/retrieval, and integrates into the agent run loop via both prompt injection and LLM-callable tools.

---

## Architecture Overview

```
Agent (AgentMixin.run)
  │
  ├─ (1) agentic() resolves memory config from __agent__ dict
  ├─ (2) Pre-run: TX(name='recall', target='memory') → MemoryManager
  │      → receives relevant memories → prepends to prompt
  ├─ (3) During run: memory_store/memory_recall available as LLM tools
  │      → route through Matrix to MemoryManager via standard tool routing
  └─ (4) Post-run: optional TX(name='store', target='memory')
         → auto-store run summary

Matrix (root)
├── products (ActorModel)
├── agents (AgentActor)
├── memory (MemoryManager)     ← New service actor
│   ├── store()                ← Create a memory
│   ├── recall()               ← Search memories by query/filters
│   ├── search()               ← Structured search with pagination
│   ├── forget()               ← Delete memories by criteria
│   └── decay()                ← Run relevance decay
└── _agent_xxx (transient adapter)
```

### Design Decisions

1. **Memory is an external actor** — not a field on AgentActor. Agents communicate with it via TX messages. This keeps agents decoupled from memory implementation.

2. **`Memory` model is an `ActorModel`** — storable and routable. It IS the memory actor (registered in Matrix as `'memories'`). Its `@expose_route` methods are the TX interface.

3. **MemoryManager is a separate service `Actor`** — registered as `'memory'` in the Matrix with `auto_register=False`. Handles the orchestration logic (search, decay, bulk operations) while Memory model handles CRUD.

4. **Dual integration**: Both prompt injection (pre-run recall) AND tool access (during-run memory_store/memory_recall). Option C from design space.

5. **SQLite LIKE-based search** to start — simple keyword matching against content and tags. Upgrade path to FTS5 or vector embeddings without changing the TX protocol.

6. **`agent_id` is a string** (actor address), not an FK — decoupled from any specific agent model. Works for both class-level (`Product` with `__agent__=True`, addr `'products'`) and instance-level (`AgentActor.get(1)`, addr `'agents'`).

---

## Memory Model

**New file**: `packages/n3tx-agents/src/n3tx_agents/memory_model.py`

```python
class Memory(ActorModel):
    __tablename__ = 'memories'
    __storable__ = True
    __access__ = {
        'read': AUTHENTICATED,
        'create': AUTHENTICATED,
        'update': AUTHENTICATED,
        'delete': AUTHENTICATED,
    }

    content: str       # The memory text (min_length=1, max_length=10000)
    category: str      # 'episodic' | 'semantic' | 'procedural' | 'preference'
    agent_id: str      # Actor address of owning agent ('' = shared)
    tags: list         # Keyword tags for retrieval (JSON list, auto-serialized)
    relevance: float   # 0.0-1.0, decays over time (default 1.0)
    run_id: str        # Correlation to agent run that created this
    source: str        # 'auto' | 'tool' | 'system'
    created_at: float  # Unix timestamp
    accessed_at: float # Unix timestamp, updated on recall
```

**Key properties**:
- `tags` is a `list` field — framework auto-serializes to JSON TEXT in SQLite
- `agent_id` is a plain string, not FK — decoupled from agent model
- `category` is a string enum, not Python Enum — simple and extensible
- `relevance` starts at 1.0, decays via `decay()` handler
- `accessed_at` updated on each recall for recency tracking

---

## MemoryManager Actor

**New file**: `packages/n3tx-agents/src/n3tx_agents/memory_manager.py`

A service `Actor` (not `ActorModel` — it doesn't need storage itself) registered at `'memory'` in the Matrix. Handles TX messages and delegates to the `Memory` model for persistence.

### TX Protocol

| TX Name | Direction | Request Data | Response Data |
|---------|-----------|-------------|---------------|
| `store` | Agent → Memory | `{content, category?, agent_id?, tags?, relevance?, run_id?, source?}` | Memory model_response |
| `recall` | Agent → Memory | `{query, agent_id?, category?, limit?, min_relevance?}` | `{memories: [...], count: int}` |
| `search` | Agent → Memory | `{agent_id?, category?, tags?, min_relevance?, limit?, offset?}` | `{memories: [...], meta: {total, limit, offset, has_more}}` |
| `forget` | Agent → Memory | `{id?}` or `{agent_id, category?, older_than?}` | `{deleted: id}` or `{deleted_count: int}` |
| `decay` | System → Memory | `{agent_id?, decay_rate?, min_relevance?}` | `{updated_count: int}` |

### Handler Implementations

**`store(data, tx)`**: Validates `content` is present, creates `Memory(**data)`, returns `tx.reply(data=created.model_response())`.

**`recall(data, tx)`**: Builds SQL filter from `agent_id`, `category`, `min_relevance`. If `query` is provided, splits into keywords and adds `LIKE` clauses against both `content` and `tags` columns. Returns memories sorted by relevance. Updates `accessed_at` on retrieved records.

**`search(data, tx)`**: Full structured search with pagination. Same filter building but with `limit`/`offset` support via `Memory.list(sql_filter=..., limit=..., offset=...)`.

**`forget(data, tx)`**: If `id` provided, deletes single record. Otherwise bulk deletes by `agent_id` + `category` + `older_than` criteria.

**`decay(data, tx)`**: Iterates all memories for an agent, applies `new_relevance = relevance * (decay_rate ^ days_since_access)`. Default decay_rate=0.95 per day. Floor at `min_relevance` (default 0.01).

---

## Memory Tools (LLM-Callable)

**New file**: `packages/n3tx-agents/src/n3tx_agents/memory_tools.py`

Creates Pydantic AI `Tool` objects with `agent_id` closured in — the LLM never needs to know the agent's identity, it's injected automatically.

```python
def make_memory_tools(agent_id: str) -> list[Tool]:
    """Create memory tools with agent_id closured in."""

    async def memory_store(ctx, content: str, category: str = 'episodic', tags: list = None) -> str:
        """Store a new memory for future reference."""
        data = {'content': content, 'category': category, 'agent_id': agent_id}
        if tags: data['tags'] = tags
        return await _route_tool_call(ctx, 'memory', 'store', data)

    async def memory_recall(ctx, query: str, category: str = None, limit: int = 5) -> str:
        """Recall memories relevant to a query."""
        data = {'query': query, 'agent_id': agent_id, 'limit': limit}
        if category: data['category'] = category
        return await _route_tool_call(ctx, 'memory', 'recall', data)

    async def memory_forget(ctx, id: int) -> str:
        """Delete a specific memory."""
        return await _route_tool_call(ctx, 'memory', 'forget', {'id': id})

    return [
        Tool(function=memory_store, takes_ctx=True, name='memory_store', ...),
        Tool(function=memory_recall, takes_ctx=True, name='memory_recall', ...),
        Tool(function=memory_forget, takes_ctx=True, name='memory_forget', ...),
    ]
```

This closure-based approach matches how `create_tool_function()` works in `tools.py` (closured target/method), keeps `ToolSpec` unchanged, and naturally scopes the `agent_id`.

---

## Integration with AgentMixin

### Changes to `agentic()` (policy layer)

Memory config is resolved through the standard 3-tier cascade:

```python
# 1. config.AGENT_DEFAULTS['memory'] — global default (False)
# 2. __agent__['memory'] — model-level override
# 3. agentic(memory={...}) — call-time override
```

When memory is enabled:

**Pre-run** (between config resolution and `run()` call):
1. Send `TX(name='recall', target='memory', data={query: task, agent_id, limit})` via adapter
2. Parse response — list of relevant memories
3. Append formatted memories to system prompt:
   ```
   Relevant memories from previous interactions:
   - [episodic] User asked about NSF deadlines last time
   - [fact] NSF CISE grants deadline is June 15, 2026
   ```

**During run** (via tools):
1. Add memory tools to the tools list: `make_memory_tools(agent_id)`
2. These are pre-built `Tool` objects, passed via new `extra_tools` kwarg on `run()`
3. Agent can explicitly call `memory_store()` and `memory_recall()` during reasoning

**Post-run** (optional, `auto_store=False` by default):
1. Send `TX(name='store', target='memory', data={content: summary, category: 'episodic', agent_id})`
2. Fire-and-forget — don't block on memory storage

### Changes to `run()` (engine)

Add `extra_tools: list = None` parameter. After discovering tools from actor addresses, merge:

```python
ai_tools = [make_tool(spec) for spec in tool_specs]
if extra_tools:
    ai_tools.extend(extra_tools)  # Pre-built Tool objects from agentic()
```

Same change applies to `run_stream()`.

---

## Configuration

### Global Default

```python
# config.py — AGENT_DEFAULTS
AGENT_DEFAULTS = {
    'self_tools': True,
    'neighbors': True,
    'neighbor_depth': 1,
    'llm': 'ollama:llama3.1',
    'memory': False,  # NEW — disabled by default for backward compat
}
```

### Per-Model Configuration

```python
# Boolean — enable with all defaults
class Product(ActorModel):
    __agent__ = {'memory': True}

# Dict — fine-grained control
class Product(ActorModel):
    __agent__ = {
        'memory': {
            'preload': True,        # recall before each run
            'preload_limit': 5,     # max memories to preload
            'tools': True,          # expose memory_store/recall as LLM tools
            'auto_store': False,    # auto-store run summaries
        }
    }

# Call-time override
result = await product.agentic(task='...', memory={'preload': True, 'tools': True})
```

---

## Registration and Lifecycle

### Setup Helper

```python
# In n3tx_agents/__init__.py
def setup_memory(storage, matrix=None):
    """Register Memory model and MemoryManager actor."""
    from n3tx_agents.memory_model import Memory
    from n3tx_agents.memory_manager import MemoryManager
    from n3tx_core.utils.registrar import register_model
    from n3tx_actors.actor import Actor

    register_model(Memory, storage=storage)
    root = matrix or Actor.root()
    if root and not root.has('memory'):
        manager = MemoryManager()
        root.register(manager)
```

Called during app bootstrap — either explicitly or auto-detected when any registered model has memory enabled.

### Memory Lifecycle

| Event | When | How |
|-------|------|-----|
| **Created** | LLM calls `memory_store` tool | Explicit, during reasoning |
| **Created** | `auto_store=True` after run | Automatic post-run summary |
| **Created** | App code sends `store` TX | Programmatic |
| **Retrieved** | `preload=True` before run | Automatic pre-run |
| **Retrieved** | LLM calls `memory_recall` tool | Explicit, during reasoning |
| **Decayed** | Periodic `decay` TX | Scheduled or on-demand |
| **Deleted** | LLM calls `memory_forget` | Explicit |
| **Deleted** | Bulk `forget` by criteria | Maintenance |

---

## Schema Extension

Add `memory` sub-key to the `agent` schema section:

```json
{
  "agent": {
    "enabled": true,
    "config": {"self_tools": true, "neighbors": true, "memory": true},
    "methods": ["agentic", "agentic_stream", "ctx", "tools"]
  }
}
```

---

## File-by-File Summary

### New Files (4)

| File | Purpose | ~Lines |
|------|---------|--------|
| `packages/n3tx-agents/src/n3tx_agents/memory_model.py` | Memory ActorModel (content, category, agent_id, tags, relevance, timestamps) | 50 |
| `packages/n3tx-agents/src/n3tx_agents/memory_manager.py` | MemoryManager Actor (store, recall, search, forget, decay handlers) | 200 |
| `packages/n3tx-agents/src/n3tx_agents/memory_tools.py` | `make_memory_tools(agent_id)` — closured Pydantic AI Tools | 60 |
| `packages/n3tx-agents/src/n3tx_agents/tests/test_memory.py` | Full test suite for model, manager, tools, integration | 300 |

### Modified Files (4)

| File | Change | ~Lines Added |
|------|--------|-------------|
| `packages/n3tx-agents/src/n3tx_agents/mixin.py` | Memory config in `agentic()`, `extra_tools` in `run()`/`run_stream()` | 50 |
| `packages/n3tx-core/src/n3tx_core/config.py` | `'memory': False` in AGENT_DEFAULTS | 1 |
| `packages/n3tx-agents/src/n3tx_agents/__init__.py` | Export Memory, MemoryManager, setup_memory | 10 |
| `packages/n3tx-agents/src/n3tx_agents/schema_ext.py` | Add `memory` to safe_keys in agent schema | 5 |

---

## Implementation Sequence

### Phase 1: Foundation
1. Create `memory_model.py` — Memory ActorModel
2. Create `memory_manager.py` — MemoryManager with all TX handlers
3. Tests for Memory CRUD and MemoryManager handlers
4. Update `__init__.py` exports

### Phase 2: Tool Integration
5. Create `memory_tools.py` — `make_memory_tools()`
6. Tests for memory tools routing through Matrix

### Phase 3: Mixin Integration
7. Add `extra_tools` to `run()` / `run_stream()`
8. Add memory config resolution to `agentic()` / `agentic_stream()`
9. Update `config.py` with memory default
10. Integration tests for full flow

### Phase 4: Polish
11. Update `schema_ext.py` — memory in agent schema
12. Add `setup_memory()` helper
13. Documentation updates

---

## Backward Compatibility

- `memory` defaults to `False` — existing agents unchanged
- `agentic()`/`run()` signatures unchanged (new kwargs are optional)
- No new external dependencies
- Enabling memory is one line: `__agent__ = {'memory': True}`

## Future Enhancements

- **FTS5 full-text search**: Add `__fts_fields__ = ['content']` to Memory, auto-create FTS5 virtual table + sync triggers in migration. Replace LIKE with FTS5 MATCH + BM25 ranking.
- **Vector embeddings**: Add `embedding` field, use sqlite-vec or external vector store. TX protocol unchanged — only MemoryManager internals change.
- **Memory summarization**: Periodic background task that summarizes old episodic memories into semantic ones, reducing noise.
- **Cross-agent memory sharing**: `agent_id=''` for shared memories accessible by all agents.
