# AgentMixin Methods

> Part of [n3tx-agents](../README.md)

## What This Covers

The six `@fullmethod` methods injected by `AgentMixin` into any model
with `__agent__ = True`. Covers `ctx()`, `tools()`, `agentic()`, `run()`,
`agentic_stream()`, and `run_stream()`. Does not cover AgentActor's
`agentic()` override (see [agent-actor.md](agent-actor.md)).

## Architecture

All methods use `@fullmethod` from `n3tx_core.utils.descriptors` -- they
work identically on classes and instances. The first parameter `target`
receives either the class or the instance.

```
agentic(task)                    agentic_stream(task)
    |                                |
    | 3-tier config cascade          | same cascade
    |                                |
    v                                v
run(task, prompt, tools, ...)    run_stream(task, prompt, tools, ...)
    |                                |
    | discover_tools()               | discover_tools()
    | build pydantic-ai Agent        | build pydantic-ai Agent
    | agent.run(task)                | agent.run_stream(task)
    |                                |
    v                                v
{answer, usage, messages}        yields {name, data, meta} chunks
```

Tool calls and thread operations route through `Actor.root().request()`
(Matrix request-response) — no transient adapters needed.

## Interface

### `ctx(target) -> str`

Builds LLM context string from the model schema.

- **Class call** (`Product.ctx()`): Returns schema text with fields, types,
  and methods. If `__agent__['prompt']` is set, it is prepended.
- **Instance call** (`product.ctx()`): Same as class, plus appends current
  instance data (field values, truncated at 200 chars each).

### `tools(target) -> list[str]`

Returns actor addresses for tool discovery. Same result for class and instance.

- `self_tools` (default `True`): includes own `__tablename__`
- `neighbors` (default `True`): includes `ListRef` relationship tablenames
- `__agent__['tools']`: appends extra addresses
- Deduplicates, preserves order

### `agentic(target, task: str, **kwargs) -> dict`

Policy layer. Resolves config, delegates to `run()`.

**kwargs accepted**: `prompt`, `tools`, `llm`, `constraints`, `user`,
`thread_id`, `create_thread`, `result_type`.

**Config cascade**: `config.AGENT_DEFAULTS` < `__agent__` dict < kwargs.
The `tools` kwarg uses `in` check (passing `tools=[]` is valid and means
"no tools", distinct from omitting it which triggers auto-discovery).

**Returns**: `{"answer": str|structured, "usage": {"input_tokens": int, "output_tokens": int, "requests": int}, "messages": list, "message_count": int}`

### `run(target, task, prompt, tools, ...) -> dict`

Engine. No config resolution. Receives fully resolved params.

**Parameters**:

| Param | Type | Purpose |
|-------|------|---------|
| `task` | str | User query |
| `prompt` | str | System prompt |
| `tools` | list[str] | Actor addresses |
| `user` | dict | JWT user context (injected into tool TX meta) |
| `constraints` | dict | `{"max_iterations": N}` maps to UsageLimits |
| `thread_id` | int | Thread ID for persistent conversation history |
| `create_thread` | bool | Create a new `Thread` automatically when no `thread_id` is provided |
| `result_type` | type | Pydantic model for structured output |
| `**kwargs` | | Override `llm` (LLM model string or pydantic-ai Model) |

**LLM resolution** (3-tier cascade inside run): `kwargs['llm']` >
`__agent__['llm']` > instance `llm` attr > `config.AGENT_DEFAULTS['llm']`.
Raises `ValueError` if nothing resolves. `ollama:model` strings are
converted to `OpenAIChatModel` with `OllamaProvider`.

### `agentic_stream(target, task, **kwargs)` -> async generator

Same config cascade as `agentic()`, delegates to `run_stream()`.
Yields the same chunk format.

### `run_stream(target, task, prompt, tools, ...)` -> async generator

Streaming engine. Same params as `run()`. Yields TX-aligned chunks:

| Chunk | `name` | `data` | `meta` |
|-------|--------|--------|--------|
| Text | `"text"` | `{"text": "..."}` | `{"stream": true, "seq": N}` |
| Tool Call | `"tool_call"` | `{"tool": "...", "args": {...}, "call_id": "..."}` | `{"stream": true, "seq": N}` |
| Tool Result | `"tool_result"` | `{"tool": "...", "result": "...", "call_id": "..."}` | `{"stream": true, "seq": N}` |
| Thinking | `"thinking"` | `{"text": "..."}` | `{"stream": true, "seq": N}` |
| Done | `"done"` | `{"answer": "...", "usage": {...}, "tool_calls": N, "thread_id": id?}` | `{"stream_end": true, "seq": N}` |
| Error | `"error"` | `{"message": "...", "code": 500}` | `{"error": true, "seq": N}` |

Errors are caught and yielded as error chunks rather than raised.

Event schemas can be declared via `events=` on `@expose_route` (see
[agent-actor.md](agent-actor.md) for the concrete event models). The
`methods` stage in `proto_model.py` serializes these into the method
schema as `events: {name: json_schema}`, enabling frontend validation
and handler discovery.

## Usage Patterns

### Multi-turn conversation (via Thread)

```python
from n3tx_agents import Thread

# Create a thread for this conversation
thread = Thread.create(Thread(agent_addr='products', user_owner=user_id))

# First turn
result1 = await product.agentic(task='What fields do I have?', thread_id=thread.id)

# Second turn — thread carries history automatically
result2 = await product.agentic(
    task='Tell me more about the price field',
    thread_id=thread.id,
)
```

### Auto-create a thread from chat UI

```python
result = await agent.run(
    task='Hello',
    prompt='You are helpful.',
    tools=[],
    create_thread=True,
    user={'user_id': 1, 'role': 'user'},
)

thread_id = result['thread_id']
```

When `create_thread=True`, `run()` / `run_stream()` create a new `Thread`,
validate later reuse against the current agent address, and return the
resulting `thread_id` so the frontend can continue the conversation.

### Structured output

```python
from pydantic import BaseModel

class Analysis(BaseModel):
    summary: str
    score: float

result = await product.agentic(
    task='Analyze this product',
    result_type=Analysis,
)
# result['answer'] is an Analysis instance
```

### Testing with TestModel

```python
from pydantic_ai.models.test import TestModel

result = await Product.agentic(
    task='Test',
    llm=TestModel(call_tools=[]),         # no tool calls
)
result = await Product.agentic(
    task='Test',
    llm=TestModel(call_tools=['grants_list']),  # calls grants_list tool
)
```

## Gotchas

- The `tools` kwarg on `agentic()` uses `'tools' in kwargs` (not truthiness).
  Passing `tools=[]` means "no tools". Omitting `tools` means "auto-discover".
- No LLM default — `run()` raises `ValueError` if no LLM resolves from
  the 3-tier cascade. In tests, always pass `llm=TestModel(call_tools=[])`.
- `RuntimeError("No Matrix root")` means no `Matrix()` was instantiated.
  Agent methods require a live Matrix for tool routing and request-response.
- Tool calls route through `Actor.root().request()` (Matrix). No adapter
  creation/teardown overhead.
