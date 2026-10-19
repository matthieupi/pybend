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

On the frontend, `AgentActor.__ui__.renderer` defaults both `item` and
`detail` to `ntx-agent`, so routed agent lists render custom agent cards and
agent detail routes mount the same rich component automatically once the shell
imports `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.js`.

Apps that need a broader agents surface can also opt into
`packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agents.js`. That
component extends `NTTList`, keeps the normal stored `AgentActor` collection
flow, and can merge those real DB rows with app-supplied built-in workflow
entries from `window.NTX_AGENT_CATALOGS[catalog]`. Those built-ins are launch
cards, not fake `AgentActor` records.

```
AgentActor (DB record)
    |
    +-- name, prompt, llm, constraints  (DB fields)
    +-- tools: list[AgentTool]          (ordered local id list)
    |
    +-- agentic(task)          @expose_route('/agentic', POST)
    |      |
    |      | tool_addrs()  -- hydrated AgentTool records to actor addresses
    |      v
    |   CallConfig  -- DB-backed adapter input (mixin.py)
    |      |
    |      v
    |   Agent.prepare(...) -> Agent.run(...)  (agent.py)
    |
    +-- agentic_stream(task)   @expose_route('/agentic_stream', POST, stream=True, events={...})
           |
           | tool_addrs()  -- same hydrated record handling
           v
        CallConfig -> Agent.prepare(...) -> Agent.run_stream(...)  (agent.py)
```

AgentActor's `agentic()` and `agentic_stream()` override the mixin's
versions. They read config from DB fields instead of using the 3-tier
cascade, then delegate into the shared internal runtime seam.

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
| `system_key` | str | `''` | TEXT |
| `name` | str | required | TEXT |
| `prompt` | str | `''` | TEXT |
| `llm` | str | `'ollama:llama3.1'` | TEXT |
| `constraints` | dict | `{}` | TEXT (JSON serialized) |
| `tools` | list[AgentTool] | `[]` | TEXT (ordered local ids, hydrated records) |

`system_key` is a stable machine identifier for framework-provisioned app
agents. It allows bootstrap code to create or update a static Assistant
idempotently across reloads and restarts without relying on the display name.

### `AgentTool` (tool reference model)

```python
class AgentTool(ActorModel):
    __tablename__ = 'agent_tools'
    __storable__ = True
    target: str       # Actor address (e.g. 'grants', 'web_tools')
    description: str  # Human-readable description
```

Linked to AgentActor through `tools: list[AgentTool]`.

### `agentic(self, task: str, **kwargs) -> str`

Exposed as `POST /agents/{id}/agentic`. Returns a JSON string (not dict)
containing `{answer, usage, messages, message_count}`.

Internally, `AgentActor.agentic()` delegates to the shared runtime and then
serializes the same sync result dict used by `AgentMixin.agentic()` with
`json.dumps(result, default=str)`. `message_count` therefore always matches
`len(messages)`, and `thread_id` is included when a thread is used or created.

**kwargs accepted**: `llm`, `constraints`, `user`, `thread_id`,
`result_type`.

**Tool resolution**: Calls `tool_addrs()` which handles hydrated `AgentTool`
records, dicts with `target`, and plain actor-address strings.

### `tool_addrs(self) -> list[str]`

Internal. Resolves actor addresses from the `tools: list[AgentTool]` field.

## Usage Patterns

### Create agent via API

```bash
# Create agent
curl -X POST /agents -d '{"name": "Scanner", "prompt": "Find grants.", "llm": "anthropic:claude-sonnet-4-5-20250929"}'

# Generated HTTP PUT accepts a partial writable AgentActor representation.
curl -X PUT /agents/1 -d '{
  "prompt": "Find current grants."
}'

# Trigger reasoning
curl -X POST /agents/1/agentic -d '{"task": "Find new grants"}'
```

By contrast, `AgentActor.update(id, {"tools": [1, 2]})` and generated agent
update tools are patch-oriented. Supplied `tools` replaces the complete ordered
relationship list; omission from a Python/TX patch leaves it unchanged.

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

### App setup

```python
from n3tx_core.utils.registrar import register_model

register_model(AgentTool, storage=storage)
register_model(AgentActor, storage=storage)
```

## Gotchas

- `agentic()` returns a JSON **string**, not a dict. This is because it
  is decorated with `@expose_route` (HTTP endpoint returns text). Parse
  with `json.loads()` in code. The decoded payload is the same sync result
  dict produced internally by the shared runtime.
- AgentActor's `agentic()` uses DB-backed configuration rather than the
  mixin's class-config cascade. It reads `self.prompt`, `self.llm`,
  `self.constraints`, and tool refs from stored fields, then delegates to
  the shared runtime. kwargs override DB values (`constraints` are merged,
  not replaced).
- Tool addresses must match actor addresses registered in the Matrix.
  If a tool address has no corresponding actor, `discover_tools()` logs
  a warning and skips it.
- `AgentActor.run` and `AgentActor.stream_run` are auto-excluded from
  tool discovery to prevent recursive agent invocation loops.
- When loaded from DB, `tools` is an ordered list of hydrated `AgentTool`
  records. The frontend renders `target` and `description` directly without a
  second fetch, while `tool_addrs()` extracts actor addresses for execution.

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
