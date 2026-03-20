# AgentActor

> Part of [n3tx-agents](../README.md)

## What This Covers

`AgentActor` -- the concrete model whose instances ARE agents. Covers
field definitions, the `agentic()` override, tool resolution from DB
records, and CRUD lifecycle. Does not cover AgentMixin methods in general
(see [mixin.md](mixin.md)).

## Architecture

AgentActor is a standard storable ActorModel with `__agent__ = True`.
Its config lives in DB fields, not code. Agents are data.

```
AgentActor (DB record)
    |
    +-- name, prompt, llm, constraints  (DB fields)
    +-- tools: ListRef[AgentTool]       (join table)
    |
    +-- agentic(task)          @expose_route('/agentic', POST)
    |      |
    |      | _resolve_tool_addrs()  -- DB lookup
    |      v
    |   AgentMixin.run()  -- bypasses mixin's agentic() cascade
    |
    +-- agentic_stream(task)   @expose_route('/agentic_stream', POST, stream=True, events={...})
           |
           | _resolve_tool_addrs()  -- same DB lookup
           v
        AgentMixin.run_stream()  -- streaming engine
```

AgentActor's `agentic()` and `agentic_stream()` override the mixin's
versions. They read config from DB fields instead of using the 3-tier
cascade, then call `AgentMixin.run()` / `run_stream()` directly via the
descriptor's underlying function.

### Stream Event Models

`actor.py` defines five non-storable `ProtoModel` subclasses used by
`agentic_stream()` via the `events=` parameter:

| Model | Fields | Purpose |
|-------|--------|---------|
| `TextChunk` | `text` | Progressive text output from the LLM |
| `ToolCallEvent` | `tool`, `args`, `call_id` | Agent is calling a tool |
| `ToolResultEvent` | `tool`, `result`, `call_id` | Result from a tool call |
| `ThinkingChunk` | `text` | Agent is in a thinking/reasoning phase |
| `DoneChunk` | `answer`, `usage`, `tool_calls` | Terminal event — task complete |

These models exist purely for validation and JSON Schema generation. They
are not storable. The schema pipeline serializes them into
`schema.methods.agentic_stream.events` so the frontend knows the exact
shape of each event type.

## Interface

### Fields

| Field | Type | Default | Storage |
|-------|------|---------|---------|
| `name` | str | required | TEXT |
| `prompt` | str | `''` | TEXT |
| `llm` | str | `'ollama:llama3.1'` | TEXT |
| `constraints` | dict | `{}` | TEXT (JSON serialized) |
| `tools` | ListRef[AgentTool] | `[]` | FK join table |

### `AgentTool` (tool reference model)

```python
class AgentTool(ActorModel):
    __tablename__ = 'agent_tools'
    __storable__ = True
    target: str       # Actor address (e.g. 'grants', 'web_tools')
    description: str  # Human-readable description
```

Linked to AgentActor via `ListRef` + auto-generated join table.

### `agentic(self, task: str, **kwargs) -> str`

Exposed as `POST /agents/{id}/agentic`. Returns a JSON string (not dict)
containing `{answer, usage, messages, message_count}`.

**kwargs accepted**: `llm`, `constraints`, `user`, `thread_id`,
`result_type`.

**Tool resolution**: Calls `_resolve_tool_addrs()` which handles three
input formats for the `tools` field:
- `AgentTool` instances (in-memory construction)
- Plain strings (e.g. `'grants'`)
- Href strings from FK hydration (e.g. `http://localhost:5000/agents/1/agent_tools/3`)

### `_resolve_tool_addrs(self) -> list[str]`

Internal. Resolves tool addresses from the `tools` ListRef field.
Batch-fetches href-referenced tools in one query to avoid N+1.

## Usage Patterns

### Create agent via API

```bash
# Create agent
curl -X POST /agents -d '{"name": "Scanner", "prompt": "Find grants.", "llm": "anthropic:claude-sonnet-4-5-20250929"}'

# Add tools via join table
curl -X POST /agents/1/agent_tools -d '{"target": "grants", "description": "Grant CRUD"}'
curl -X POST /agents/1/agent_tools -d '{"target": "web_tools", "description": "Web scraping"}'

# Trigger reasoning
curl -X POST /agents/1/agentic -d '{"task": "Find new grants"}'
```

### Create agent in code

```python
from n3tx_agents import AgentActor, AgentTool

agent = AgentActor.create(AgentActor(
    name='Grant Scanner',
    prompt='You find government grants for nonprofits.',
    tools=[AgentTool(target='grants'), AgentTool(target='web_tools')],
    llm='anthropic:claude-sonnet-4-5-20250929',
    constraints={'max_iterations': 20},
))

result_str = await agent.agentic(task='Scan for new grants')
result = json.loads(result_str)
print(result['answer'])
```

### Join table setup

```python
from n3tx_core.models.proto_model import generate_join_model
from n3tx_core.utils.registrar import register_model

register_model(AgentTool, storage=storage)
register_model(AgentActor, storage=storage)
join_cls = generate_join_model(AgentActor, AgentTool)
register_model(join_cls, storage=storage)
```

## Gotchas

- `agentic()` returns a JSON **string**, not a dict. This is because it
  is decorated with `@expose_route` (HTTP endpoint returns text). Parse
  with `json.loads()` in code.
- AgentActor's `agentic()` bypasses the mixin's config cascade. It reads
  `self.prompt`, `self.llm`, `self.constraints` directly from DB fields.
  kwargs override DB values (`constraints` are merged, not replaced).
- Tool addresses must match actor addresses registered in the Matrix.
  If a tool address has no corresponding actor, `discover_tools()` logs
  a warning and skips it.
- `AgentActor.run` and `AgentActor.stream_run` are auto-excluded from
  tool discovery to prevent recursive agent invocation loops.
- When loaded from DB, `tools` is a list of href strings (FK hydration).
  `_resolve_tool_addrs()` handles this transparently via batch fetch.

## Schema Extension

The `agent` stage in the schema pipeline adds metadata to AgentActor schemas:

```json
{
  "agent": {
    "enabled": true,
    "agentic_endpoint": "/agents/{id}/agentic",
    "methods": ["agentic", "agentic_stream", "ctx", "tools"]
  }
}
```

Non-AgentActor models with `__agent__ = True` get `enabled: true` but
no `agentic_endpoint`.
