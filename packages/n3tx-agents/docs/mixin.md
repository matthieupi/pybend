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
    | create transient adapter       | create transient adapter
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

Policy layer. Resolves config, creates transient adapter, delegates to `run()`.

**kwargs accepted**: `prompt`, `tools`, `llm`, `constraints`, `user`,
`message_history`, `result_type`.

**Config cascade**: `config.AGENT_DEFAULTS` < `__agent__` dict < kwargs.
The `tools` kwarg uses `in` check (passing `tools=[]` is valid and means
"no tools", distinct from omitting it which triggers auto-discovery).

**Adapter lifecycle**: Creates `NetworkAdapter(addr='_agent_{uuid}')`,
registers with Matrix, cleans up in `finally` block (even on error).

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
| `llm` | str or Model | LLM identifier or pydantic-ai Model instance |
| `constraints` | dict | `{"max_iterations": N}` maps to UsageLimits |
| `adapter` | NetworkAdapter | Reuse existing (skips transient creation) |
| `message_history` | list | Previous messages for multi-turn |
| `result_type` | type | Pydantic model for structured output |

**LLM resolution**: `ollama:model` strings are converted to
`OpenAIChatModel` with `OllamaProvider`. All other strings pass through
to pydantic-ai's default resolution.

### `agentic_stream(target, task, **kwargs)` -> async generator

Same config cascade as `agentic()`, delegates to `run_stream()`.
Yields the same chunk format.

### `run_stream(target, task, prompt, tools, ...)` -> async generator

Streaming engine. Same params as `run()`. Yields TX-aligned chunks:

| Chunk | `name` | `data` | `meta` |
|-------|--------|--------|--------|
| Text | `"text"` | `{"text": "..."}` | `{"stream": true, "seq": N}` |
| Done | `"done"` | `{"answer": "...", "usage": {...}}` | `{"stream_end": true, "seq": N}` |
| Error | `"error"` | `{"message": "...", "code": 500}` | `{"error": true, "seq": N}` |

Errors are caught and yielded as error chunks rather than raised.

## Usage Patterns

### Multi-turn conversation

```python
result1 = await product.agentic(task='What fields do I have?')
result2 = await product.agentic(
    task='Tell me more about the price field',
    message_history=result1['messages'],
)
```

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

- `run()` creates a transient adapter if none is provided. If you call
  `run()` in a loop, pass a shared adapter to avoid creating/destroying
  one per iteration.
- The `tools` kwarg on `agentic()` uses `'tools' in kwargs` (not truthiness).
  Passing `tools=[]` means "no tools". Omitting `tools` means "auto-discover".
- `agentic_stream()` cleanup depends on the generator's `finally` block.
  Always fully consume the generator or call `await gen.aclose()`.
- LLM defaults to `ollama:llama3.1`. In tests, always pass
  `llm=TestModel(call_tools=[])` to avoid hitting a real LLM.
- `RuntimeError("No Matrix root")` means no `Matrix()` was instantiated.
  Agent methods require a live Matrix for tool routing.
