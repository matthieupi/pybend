# N3TX Agents

LLM-powered reasoning via the actor system.

**A Model is an Agent, an Agent is an Actor, and an Actor is a Tool collection.**

Every Actor with `@expose_route` methods is a set of callable tools.
An Agent is an Actor that reasons — it has a prompt, an LLM, and a list
of other actors it can talk to. The union of all `@expose_route` methods
on those actors forms the agent's available tool set.

Agents are **data, not code**. The primary pattern is dynamic
instantiation — create agents via API, store them in DB, load them at
runtime. Subclasses are supported but not the primary path.

---

## Quick Start

### Path A: Dynamic Agents (primary)

Agents are instances of `AgentActor`. Configuration lives in fields.

```python
from n3tx import AgentActor, create_app

# Define tool-providing models (these are NOT agents — they are tools)
class Grant(ActorModel):
    __tablename__ = 'grants'
    __storable__ = True
    title: str
    url: str

class WebTools(ActorModel):
    __tablename__ = 'web_tools'
    __storable__ = False

    @expose_route('/scrape', methods=['POST'])
    async def scrape(self, url: str) -> dict:
        """Fetch a URL and return its content."""
        ...

# Create an agent — in code, via API, or from DB
scanner = AgentActor(
    name="Grant Scanner",
    prompt="You find government grants. List sources, scrape each URL, "
           "create Grant records for new ones.",
    tools=["grants", "web_tools"],
    llm="anthropic:claude-sonnet-4-5-20250929",
    constraints={"max_iterations": 30},
)

# Trigger the agent
result = await scanner.run(task="Find grants about renewable energy")
# result is JSON: {"answer": "...", "usage": {...}, "messages": 5}
```

Via API:

```
POST /agents
{"name": "Grant Scanner", "prompt": "...", "tools": ["grants", "web_tools"]}

POST /agents/1/run
{"task": "Find grants about renewable energy"}
```

From DB:

```python
scanner = AgentActor.get(1)
result = await scanner.run(task="Find new grants")
```

### Path B: Agentic Model Methods (secondary)

Any `ActorModel` with `__agent__ = True` gets `AgentMixin` injected.
Its methods can call `self.agent_run()` internally — the caller doesn't
know or care that an LLM is involved.

```python
class Product(ActorModel):
    __tablename__ = 'products'
    __storable__ = True
    __agent__ = True          # injects AgentMixin

    name: str
    price: float

    @expose_route('/create_from_text', methods=['POST'])
    async def create_from_text(self, text: str, tools: list = []) -> str:
        """LLM parses freeform text into a Product."""
        result = await self.agent_run(
            prompt="Parse the text into a Product with name and price. "
                   "Use products_create to save it.",
            tools=["products"] + tools,
            task=text,
        )
        return result['answer']
```

Both paths use the same underlying machinery: `AgentMixin.agent_run()`.

---

## Core Insights

### @expose_route = Tool

No new `@tool` decorator. The existing `@expose_route` already provides
everything a tool needs:

- **I/O validation** — parameter types from function signatures
- **Auth** — inherits `__access__` from model + per-method `access=`
- **Schema exposure** — appears in `schema.methods`, auto-discovered
- **TX routing** — calls route through Matrix with full interceptor chain
- **Tool spec generation** — schemas carry method signatures with types

A "custom tool" like web scraping is just an `@expose_route` method
on a non-storable model:

```python
class WebTools(ActorModel):
    __tablename__ = 'web_tools'
    __storable__ = False

    @expose_route('/scrape', methods=['POST'], access=AUTHENTICATED)
    async def scrape(self, url: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
        return {'url': url, 'html': resp.text[:50000]}
```

### Pydantic AI Is the Engine

N3TX does not build an LLM client, agent loop, or context manager.
[Pydantic AI](https://ai.pydantic.dev/) provides all of that:

| Concern | Pydantic AI provides |
|---------|---------------------|
| LLM calls | Multi-provider (Ollama, Anthropic, OpenAI, Google, etc.) |
| Agent loop | ReAct-style tool calling with automatic retries |
| Tool calling | Argument validation + result serialization |
| Structured output | `output_type=` with Pydantic model validation |
| Conversation history | `result.all_messages()` for continuation |
| Usage tracking | `result.usage()` (tokens, requests) |
| Error handling | `ModelRetry`, `UsageLimitExceeded`, retries |
| Safety limits | `UsageLimits(request_limit=, token_limit=)` |

N3TX's job is purely the **binding layer**: discover tools from actors,
route tool calls through Matrix as TX, persist agent state, publish
lifecycle events.

### Actors ARE Tools, Agents ARE Actors

```
Actor
  |-- Has @expose_route methods     --> these ARE tools
  |-- Registered with Matrix        --> addressable via TX
  |-- Any actor can be in another agent's tools list

ActorModel (Actor + ProtoModel)
  |-- Same as Actor, plus: storage, schema, CRUD
  |-- CRUD operations are themselves tools (list, get, create, update, delete)

AgentMixin (injected when __agent__ = True)
  |-- Provides: agent_run(prompt, tools, task)
  |-- Provides: tool discovery from actor addresses
  |-- Makes any ActorModel capable of LLM-powered methods

AgentActor (ActorModel + __agent__ = True)
  |-- prompt, tools, llm, constraints are FIELDS (data, not code)
  |-- Instances ARE agents -- created from DB, API, or code
  |-- /run endpoint calls self.agent_run(self.prompt, self.tools, task)
```

---

## Package Structure

```
src/n3tx/core/agents/
  __init__.py        Re-exports: AgentMixin, AgentActor, AgentDeps, ToolSpec
  mixin.py           AgentMixin: agentic(), run(), Matrix request-response, Pydantic AI binding
  actor.py           AgentActor(ActorModel): the dynamic agent class
  deps.py            AgentDeps dataclass (Pydantic AI RunContext deps)
  tools.py           ToolSpec, discover_tools(), create_tool_function(), make_tool()
  schema_ext.py      @schema_extension for agent metadata in JSON Schema
  tests/
    conftest.py      Fixtures: fresh_matrix, memory_storage, reset_actor_state
    test_mixin.py    12 tests: injection, agent_run, cleanup, tool calling
    test_tools.py    12 tests: discovery, function generation, Pydantic AI wrapper
    test_agent_actor.py  21 tests: class, instances, CRUD, run, schema
```

---

## Module Reference

### AgentMixin (`mixin.py`)

Injected into any model with `__agent__ = True` via `ProtoModel`'s mixin registry.
Same injection pattern as `StorableMixin`:

```python
__storable__ = True  -->  injects StorableMixin  (special-cased in core)
__agent__    = True  -->  injects AgentMixin     (registered by n3tx_agents.__init__)
__ui__       = {...} -->  injects ViewableMixin  (registered by n3tx_ui.__init__)
```

**Import ordering requirement**: `n3tx_agents` (or just `import n3tx_agents`) must
be imported **before** any model with `__agent__ = True` is defined. The mixin
registry is populated at `n3tx_agents` import time. Applications must put
`import n3tx_agents` before their model imports in `main.py`.

```python
# main.py — correct order
import n3tx_agents   # registers AgentMixin in proto_model._mixin_registry
from models import Product  # __agent__ = True fires → AgentMixin injected

# main.py — wrong order (AgentMixin silently not injected)
from models import Product  # __agent__ = True fires with empty registry
import n3tx_agents          # too late
```

Provides one method:

#### `agent_run(prompt, tools, task, user=None, **kwargs) -> dict`

Execute an LLM reasoning loop with Matrix-routed tools.

**Args:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `prompt` | `str` | System prompt for the LLM |
| `tools` | `list[str]` | Actor addresses whose methods become tools |
| `task` | `str` | The user task / query to execute |
| `user` | `dict` | JWT user dict for auth context (optional) |
| `llm` | `str \| Model` | Override LLM model (kwarg) |
| `constraints` | `dict` | Override constraints (kwarg) |

**Returns:**

```python
{
    "answer": "The LLM's final text output",
    "usage": {
        "input_tokens": 1500,
        "output_tokens": 320,
        "requests": 3
    },
    "messages": 7
}
```

**Internals:**

Each call to `run()`:

1. Resolves LLM from 3-tier cascade (kwargs > model config > AGENT_DEFAULTS)
2. Reads thread history via `Actor.root().request()` (if `thread_id` provided)
3. Calls `discover_tools(tools, root)` to build `ToolSpec` list
4. Creates a `pydantic_ai.Agent` with the discovered tools
5. Runs the Pydantic AI agent loop (`ai_agent.run(task, deps=...)`)
6. Updates thread with conversation messages (if `thread_id` provided)

Tool calls and thread operations route through `Actor.root().request()`
(Matrix request-response) — no transient adapters needed. Matrix uses
asyncio Futures keyed by TX uuid for concurrent correlation.

---

### AgentActor (`actor.py`)

A concrete `ActorModel` whose instances ARE agents. Extends `ActorModel`
with `__agent__ = True`, so `AgentMixin` is injected automatically.

#### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | (required) | Human-readable agent name |
| `prompt` | `str` | `''` | System prompt for the LLM |
| `tools` | `list` | `[]` | Actor addresses for tool discovery |
| `llm` | `str` | `'ollama:llama3.1'` | Pydantic AI `provider:model` string |
| `constraints` | `dict` | `{}` | Budget/safety limits |

#### LLM Provider Strings

The `llm` field accepts any [Pydantic AI model string](https://ai.pydantic.dev/models/):

```
ollama:llama3.1                       # Local Ollama
anthropic:claude-sonnet-4-5-20250929           # Anthropic
openai:gpt-4o                         # OpenAI
google-gla:gemini-2.0-flash           # Google
```

#### Constraints

The `constraints` dict controls safety limits:

```python
{
    "max_iterations": 30,    # Max LLM round-trips (maps to UsageLimits.request_limit)
}
```

#### Storage

`tools` (list) and `constraints` (dict) are stored as JSON TEXT in SQLite.
Serialization is handled automatically:

- `_storage_dict()` serializes `list`/`dict` fields to JSON strings on write
- `@model_validator(mode='before')` deserializes JSON strings back on read

#### Endpoint

`POST /{tablename}/{id}/run`

```json
{"task": "Find grants about renewable energy"}
```

Returns JSON:

```json
{
    "answer": "I found 3 new grants...",
    "usage": {"input_tokens": 2100, "output_tokens": 450, "requests": 5},
    "messages": 11
}
```

---

### Tool Discovery (`tools.py`)

Discovers tools from actor addresses by reading their schemas.

#### `discover_tools(actor_addrs, root) -> list[ToolSpec]`

For each address in `actor_addrs`:

1. Looks up the actor in Matrix children
2. Gets the model class and calls `cls.schema()`
3. If the model is **storable**: generates CRUD tool specs (`list`, `get`, `create`, `update`, `delete`)
4. For all `@expose_route` methods in `schema.methods`: generates method tool specs

**Tool naming convention:** `{tablename}_{method}` (e.g., `grants_create`, `web_tools_scrape`).

**CRUD tools** for storable models:

| Tool | Description | Required params |
|------|-------------|-----------------|
| `{t}_list` | List records | (none, optional `limit`/`offset`) |
| `{t}_get` | Get by ID | `id` |
| `{t}_create` | Create record | writable fields |
| `{t}_update` | Update record | `id` + writable fields |
| `{t}_delete` | Delete by ID | `id` |

**Method tools** from `@expose_route`:

- Parameters come from `schema.methods[name].parameters`
- The `user` parameter is filtered out (injected server-side)
- Instance methods automatically get an `id` parameter prepended

#### `ToolSpec`

```python
@dataclass
class ToolSpec:
    actor_addr: str     # Target actor address (e.g., 'grants')
    method_name: str    # Method/action name (e.g., 'create')
    tool_name: str      # LLM-facing name (e.g., 'grants_create')
    description: str    # Human-readable description
    parameters: dict    # JSON Schema for parameters
```

#### `create_tool_function(spec) -> async function`

Creates an async function with a proper Python signature from a `ToolSpec`.
Uses `exec()` for dynamic signature generation — same approach as
`dataclasses`, `namedtuple`, and `attrs`. All input comes from trusted
model schemas.

The generated function:

1. Collects parameters into a dict
2. Calls `_route_tool_call(ctx, target, method, data)`
3. Which creates a TX and sends it through `adapter.request()` for correlation
4. Returns the response as a JSON string (tool results are text for the LLM)
5. Raises `pydantic_ai.ModelRetry` on error TXs (lets the LLM retry)

#### `make_tool(spec) -> pydantic_ai.Tool`

Wraps `create_tool_function()` output in a `pydantic_ai.tools.Tool`
with `takes_ctx=True`.

---

### AgentDeps (`deps.py`)

Dependency context passed to every Pydantic AI tool function via
`RunContext[AgentDeps]`.

```python
@dataclass
class AgentDeps:
    adapter: NetworkAdapter   # For request/response correlation
    user: Optional[dict]      # JWT user dict for auth context
    agent_addr: str           # Agent's actor address (TX.source)
```

---

### Schema Extension (`schema_ext.py`)

Registered via `@schema_extension(after='methods')`. Adds an `agent`
section to JSON Schema for models with `__agent__ = True`.

**For `AgentActor` subclasses:**

```json
{
    "agent": {
        "enabled": true,
        "run_endpoint": "/agents/{id}/run"
    }
}
```

**For other `__agent__ = True` models:**

```json
{
    "agent": {
        "enabled": true
    }
}
```

**For non-agent models:** No `agent` key in schema.

---

## Streaming

Agent reasoning can stream progressive results to the frontend via SSE.

### Stream Event Models

Streaming methods declare their event vocabulary using non-storable `ProtoModel` subclasses. These serve as the schema contract between backend and frontend — the frontend knows exactly what shape each event carries.

```python
# Defined in n3tx_agents/actor.py (shipped with the package)
class TextChunk(ProtoModel):
    text: str = Field(default='')

class ToolCallEvent(ProtoModel):
    tool: str = Field(default='')
    args: dict = Field(default={})
    call_id: str = Field(default='')

class ToolResultEvent(ProtoModel):
    tool: str = Field(default='')
    result: str = Field(default='')
    call_id: str = Field(default='')

class ThinkingChunk(ProtoModel):
    text: str = Field(default='')

class DoneChunk(ProtoModel):
    answer: str = Field(default='')
    usage: dict = Field(default={})
    tool_calls: int = Field(default=0)
```

These models are not storable — they exist purely for validation and JSON Schema generation. The schema pipeline serializes them into the method schema so the frontend can validate and type-check events at runtime.

### `events=` Parameter on `@expose_route`

Streaming methods declare their event types via the `events=` parameter:

```python
@expose_route('/agentic_stream', methods=['POST'], stream=True,
              events={
                  'text': TextChunk, 'tool_call': ToolCallEvent,
                  'tool_result': ToolResultEvent, 'thinking': ThinkingChunk,
                  'done': DoneChunk,
              })
async def agentic_stream(self, task: str, **kwargs):
    ...
```

The schema pipeline (`methods` stage in `proto_model.py`) serializes this into:

```json
{
  "methods": {
    "agentic_stream": {
      "route": "/agentic_stream",
      "stream": true,
      "events": {
        "text": {"type": "object", "properties": {"text": {"type": "string"}}},
        "tool_call": {"type": "object", "properties": {"tool": {...}, "args": {...}, "call_id": {...}}},
        ...
      }
    }
  }
}
```

### Frontend: NTTStreamAgent

**File**: `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js`

`NTTStreamAgent` extends `NTTStream` with rich agent output rendering — typed entries (thinking, tool calls, text), markdown rendering, and tool result cards. All agent-style streaming components extend `NTTStreamAgent` (or `NTTStream` directly for simpler cases).

**Component hierarchy:**

```
Component → NTTMethod → NTTStream → NTTStreamAgent → (app subclasses)
```

```javascript
import { NTTStreamAgent } from './ntx-stream-agent.js';

class MyComponent extends NTTStreamAgent {
    // UPPERCASE methods = TX inbox handlers (actor convention)
    TEXT(data, meta)       { /* data.text */ }
    TOOL_CALL(data, meta)  { /* data.tool, data.args, data.call_id */ }
    TOOL_RESULT(data, meta){ /* data.tool, data.result */ }
    THINKING(data, meta)   { /* data.text */ }
    DONE(data, meta)       { /* data.answer, data.usage */ }

    // Lifecycle hooks
    STREAM_END(data)       { /* stream completed */ }
    STREAM_ERROR(err)      { /* stream failed */ }
}
```

**Key methods:**

| Method | Purpose |
|--------|---------|
| `prerender()` | Structural DOM created before schema loads. Never wiped by render(). |
| `callMethod()` | Start stream via TX with `meta: {stream: true, req: reqId}`. |
| `cancel()` | Client-side cancel: sets `#cancelled` flag, sends `STREAM_CANCEL` TX. |

**How dispatch works:**

1. `callMethod()` sends TX with `meta: {stream: true}` via the Actor system.
2. Backend sends stream chunks as TX messages.
3. `NTTStream.STREAM()` handler receives chunks, skips if `#cancelled`.
4. Dispatches to UPPERCASE handlers: `THINKING()`, `TOOL_CALL()`, `TEXT()`, `DONE()`, etc.

**UPPERCASE convention**: All methods that handle TX messages are UPPERCASE. This mirrors the backend actor handler pattern and visually separates inbox handlers from internal component logic (lowercase/camelCase).

### Concrete Streaming Components

`<ntx-agent-live>` and `<ntx-chat>` extend `NTTStream` directly:

- **`<ntx-agent-live>`** — Real-time agent activity view. Shows structured event log (thinking → tool calls → text → done) with collapsible entries and JSON rendering.
- **`<ntx-chat>`** — Agent chat panel. Floating chat widget for conversational agent interaction.

Both use `prerender()` for structural UI and auto-cancel streams in `disconnectedCallback()`.

---

## Message Flow

Complete lifecycle of an agent tool call:

```
1. POST /agents/1/run {"task": "Scan grants.gov for new grants"}
        |
2. AgentActor(id=1).run(task)
   --> calls self.agent_run(self.prompt, self.tools, task)
        |
3. AgentMixin.run():
   a. Resolves LLM from config cascade
   b. discover_tools(["grants", "web_tools"], matrix)
      --> Gets schema.methods from each actor
      --> Builds ToolSpec list: grants_create, grants_list, ...,
                                web_tools_scrape, web_tools_extract
   c. Creates pydantic_ai.Agent(llm, system_prompt, tools=[...])
   d. Runs ai_agent.run(task, deps=AgentDeps(user, agent_addr))
        |
4. Pydantic AI loop (internal):
   a. Sends messages + tool specs to LLM
   b. LLM responds: tool_use("web_tools_scrape", {url: "https://..."})
   c. Pydantic AI validates args, calls generated tool function
   d. Tool function creates TX(name='scrape', target='web_tools', data={...})
   e. adapter.request(tx) --> Matrix routes --> WebTools.handler()
      --> scrape() method executes
      --> Response TX returns via Future correlation
   f. Tool result (JSON string) sent back to LLM
   g. LLM calls more tools or produces final answer
        |
5. agent_run() returns {answer, usage, messages}
6. Transient adapter cleaned up (finally block)
7. run() returns JSON to HTTP response
```

---

## Dynamic Tool Extension

Any agentic method can accept extra tool addresses at call time:

```python
class Product(ActorModel):
    __agent__ = True

    @expose_route('/create_from_text', methods=['POST'])
    async def create_from_text(self, text: str, tools: list = []) -> str:
        result = await self.agent_run(
            prompt="Parse freeform text into a Product.",
            tools=["products"] + tools,    # own model + caller-provided
            task=text,
        )
        return result['answer']
```

The caller can extend the agent's capabilities at call time:

```python
# Via TX
TX(name="create_from_text", target="products",
   data={"text": "Red sneakers, $89", "tools": ["suppliers", "pricing"]})

# Via API
POST /products/1/create_from_text
{"text": "Red sneakers, $89", "tools": ["suppliers", "pricing"]}
```

---

## Triggering Agents

Agents wake up on messages. No special scheduling infrastructure needed:

```python
# Via HTTP endpoint
POST /agents/1/run {"task": "Scan all sources"}

# Via code
result = await scanner.run(task="Scan all sources")

# Via TX message (from another actor or agent)
await matrix.send(TX(
    name='run', source='scheduler', target='agents',
    data={'id': 1, 'task': 'Scan all sources'}
))

# Via lifecycle event (reactive)
Grant._subscribers.append('agents/1')
# When a Grant is created, the agent receives a LIFECYCLE TX
```

---

## Testing

Use Pydantic AI's `TestModel` for mock LLM responses:

```python
from pydantic_ai.models.test import TestModel

# No tool calls — LLM returns immediately
result = await agent.run(
    task="Hello",
    llm=TestModel(call_tools=[]),
)

# LLM calls a specific tool, then returns
result = await agent.run(
    task="List all grants",
    llm=TestModel(call_tools=['grants_list']),
)
```

**Important:** Tests that use real SQLite storage must use file-based
databases (e.g., `tmp_path / 'test.db'`), not `:memory:`. The SQLite
migration system opens its own connection, which for `:memory:` creates
a separate, empty database.

---

## Files Modified (outside this package)

| File | Change |
|------|--------|
| `proto_model.py` | Added `register_mixin()` API + `_mixin_registry`. `n3tx_agents.__init__` calls `register_mixin('__agent__', AgentMixin)` to register the mixin before model classes are defined. |
| `n3tx_agents/__init__.py` | Calls `register_mixin('__agent__', AgentMixin)` before importing `AgentActor` so the registry is populated when `AgentActor.__init_subclass__` fires. |
| `pyproject.toml` | `pydantic-ai>=1.0` in `agents` and `dev` extras |
