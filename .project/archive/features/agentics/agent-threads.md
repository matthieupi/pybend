# Agent Threads — Conversation History Persistence

## Context

Agents need per-conversation history that persists across requests and isolates between frontends/sessions. Currently, `message_history` is an ephemeral list passed by the caller — nothing is persisted, and concurrent sessions on different frontends can leak into each other.

**Two orthogonal modules** (separate concerns):
- **Thread** — per-conversation history, session-scoped, request/response pairs
- **Memory** — long-term agent knowledge, cross-session (separate future work)

This plan covers **Thread only**.

**Design principle**: Thread is a "mostly static" ActorModel — standard CRUD IS the API. Agents TX `{name: 'get', target: 'threads', data: {id: N}}` to read history. No ThreadManager, no custom handlers. The model is the manager.

---

## Thread Model

**New file**: `packages/n3tx-agents/src/n3tx_agents/thread.py`

```python
class Thread(ActorModel):
    __tablename__ = 'threads'
    __storable__ = True
    __protected_fields__ = {'user_owner'}
    __access__ = {
        'read':   OWNER | ROLE('admin'),
        'create': AUTHENTICATED,
        'update': OWNER | ROLE('admin'),
        'delete': OWNER | ROLE('admin'),
    }

    agent_addr: str = Field(default='')    # Actor address of the agent
    messages: list  = Field(default=[])    # pydantic-ai messages (JSON auto-serialized)
    user_owner: int = Field(default=0)     # Protected — auto-injected from JWT
```

**Key decisions**:
- `messages: list` — framework auto-serializes to JSON TEXT in SQLite (v0.9+), no manual handling
- `agent_addr` is a string (not FK) — decoupled from agent model, works for any actor address
- OWNER-scoped access — users can only read/update their own threads (session isolation)
- No `__agent__ = True` — Thread is passive storage, not an agent
- No title/status fields — keep minimal, add later if needed

**Messages format**: Each message is a TX-shaped dict (JSONified TX envelope):
```python
{'name': 'request', 'source': 'user', 'target': 'agents/1',
 'data': {... pydantic-ai message ...}, 'meta': {}, 'timestamp': 1234567890.0}
```

**Conversion utilities** (`@staticmethod` on Thread class):

```python
@staticmethod
def to_history(tx_messages: list) -> list[ModelMessage]:
    """Stored TX dicts → pydantic-ai ModelMessage list for agent.run()."""
    if not tx_messages: return []
    raw = [msg['data'] for msg in tx_messages]
    return ModelMessagesTypeAdapter.validate_python(raw)

@staticmethod
def from_history(model_messages: list, source='', target='') -> list[dict]:
    """pydantic-ai ModelMessage list → TX-shaped dicts for storage."""
    if not model_messages: return []
    serialized = ModelMessagesTypeAdapter.dump_python(model_messages, mode='json')
    return [
        {'name': msg.get('kind', 'message'), 'source': source, 'target': target,
         'data': msg, 'meta': {}, 'timestamp': time.time()}
        for msg in serialized
    ]
```

Static methods on Thread (not module-level) — they belong to the Thread class conceptually and are accessible via `Thread.to_history()` / `Thread.from_history()`.

---

## Mixin Integration

**`thread_id` replaces `message_history`** in the public API. They are mutually exclusive — if `thread_id` is provided, `message_history` is ignored (thread IS the history).

### `run()` — Engine (lines 276-391 in mixin.py)

Add `thread_id: int = None` parameter. Thread logic lives here (not in `agentic()`) because AgentActor.agentic() also calls `run()` directly — avoids duplication.

**Pre-run** (after adapter setup, before LLM loop):
```python
if thread_id is not None:
    message_history = None  # thread_id takes precedence
    thread_tx = TX(name='get', source=adapter.addr, target='threads',
                   data={'id': thread_id}, meta={'user': user} if user else {})
    resp = await adapter.request(thread_tx)
    if resp.is_error:
        raise RuntimeError(f"Thread {thread_id} not found: {resp.data.get('message')}")
    message_history = to_history(resp.data.get('messages', []))
```

**Post-run** (after `result = await ai_agent.run(task, **run_kwargs)`):
```python
all_messages = result.all_messages()
if thread_id is not None:
    update_tx = TX(name='update', source=adapter.addr, target='threads',
                   data={'id': thread_id, 'messages': from_history(all_messages)},
                   meta={'user': user} if user else {})
    resp = await adapter.request(update_tx)
    if resp.is_error:
        logger.warning("Failed to update thread %s: %s", thread_id, resp.data.get('message'))
```

Return dict adds `'thread_id': thread_id` when present.

### `run_stream()` — Streaming Engine (lines 453-580)

Same `thread_id` parameter and pre-run read. Post-run update happens after stream completes but inside the `async with` block (adapter still alive):

```python
async with ai_agent.call_stream(task, **run_kwargs) as result:
    async for text in result.stream_text(delta=True):
        yield {name: 'text', ...}

    # Stream complete — capture messages and update thread
    all_messages = result.all_messages()
    if thread_id is not None:
    # TX update (same as run())

    yield {name: 'done', data: {answer, usage, thread_id}, ...}
```

### `agentic()` and `agentic_stream()` — Policy Layer

Pass-through only — extract `thread_id` from kwargs and forward to `run()`/`run_stream()`:

```python
thread_id = kwargs.get('thread_id')
# ... in the run() call:
return await instance.call(..., thread_id=thread_id, ...)
```

### `AgentActor.agentic()` — Override (actor.py lines 103-135)

One-line addition — forward `thread_id` from kwargs:

```python
result = await run_fn(self, ..., thread_id=kwargs.get('thread_id'), ...)
```

---

## Files Summary

### New (1)

| File | What |
|------|------|
| `packages/n3tx-agents/src/n3tx_agents/thread.py` | Thread(ActorModel) + `to_history()` / `from_history()` utilities |

### Modified (3)

| File | Change |
|------|--------|
| `packages/n3tx-agents/src/n3tx_agents/mixin.py` | `thread_id` param on `run()`, `run_stream()`, `agentic()`, `agentic_stream()`. Pre-run TX read, post-run TX update. |
| `packages/n3tx-agents/src/n3tx_agents/actor.py` | Forward `thread_id` from kwargs in `AgentActor.agentic()` |
| `packages/n3tx-agents/src/n3tx_agents/__init__.py` | Export `Thread`, `to_history`, `from_history` |

### Test (1)

| File | What |
|------|------|
| `packages/n3tx-agents/src/n3tx_agents/tests/test_thread.py` | Thread CRUD, conversion round-trip, run() integration, stream integration |

---

## Implementation Sequence

1. Create `thread.py` — Thread model + conversion utilities
2. Update `__init__.py` — exports
3. Modify `run()` in `mixin.py` — thread_id param, pre-run read, post-run update
4. Modify `run_stream()` — same + capture `all_messages()` after stream
5. Modify `agentic()` and `agentic_stream()` — pass thread_id through
6. Modify `AgentActor.agentic()` — pass thread_id through
7. Write `test_thread.py` — model tests, CRUD, conversion, integration with run/stream
8. Run full test suite

---

## Test Plan

**Model tests**: Thread fields, access rules, protected_fields, storable flag.

**CRUD tests** (file-based SQLite via `tmp_path`): create thread, get thread, update messages, delete thread.

**Conversion tests**: `to_history([])` → `[]`, `from_history([])` → `[]`, round-trip with real pydantic-ai messages.

**Integration with `run()`**:
- `run(thread_id=N)` reads thread, uses history, updates thread after run
- Second `run(thread_id=N)` continues conversation (message count grows)
- `thread_id` overrides `message_history` when both provided
- Invalid `thread_id` raises `RuntimeError`

**Integration with `run_stream()`**:
- Stream with `thread_id` updates thread after stream completes
- Done chunk includes `thread_id`

**Integration with `agentic()` and `AgentActor.agentic()`**:
- `thread_id` forwards correctly through the policy layer

---

## Verification

```bash
# Unit + integration tests
cd /workspace && python3 -m pytest packages/n3tx-agents/src/n3tx_agents/tests/test_thread.py -v

# Full agent test suite (no regressions)
cd /workspace && python3 -m pytest packages/n3tx-agents/src/n3tx_agents/tests/ -v

# Grants example tests (no regressions)
cd /workspace && python3 -m pytest examples/grants/tests/ -v
```
