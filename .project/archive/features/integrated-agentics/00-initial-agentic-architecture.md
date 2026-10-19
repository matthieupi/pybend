# N3TX Agentic System — Unified Architecture Plan

> **Status:** Draft
> **Date:** 2026-03-03
> **Branch:** `v0.10` (from `v0.8`)
> **Target:** v0.10 Wave 1 — Schema Agentic System
> **First use case:** Grant-watching tool

---

## Vision

**A Model is an Agent, an Agent is an Actor, and an Actor is a Tool collection.**

Every Actor with `@expose_route` methods is a set of callable tools. An Agent
is an Actor that reasons — it has a prompt, an LLM, and a list of other actors
it can talk to. The union of all `@expose_route` methods on those actors forms
the agent's available tool set.

Agents are **data, not code**. The primary pattern is dynamic instantiation —
create agents via API, store them in DB, load them at runtime. Subclasses are
supported but not the primary path.

---

## Core Insights (Unchanged)

### Insight #1: @expose_route = Tool

No new `@tool` decorator. The existing `@expose_route` decorator already
provides everything a tool needs:

- **I/O validation** — parameter types from function signatures, validated by Pydantic
- **Auth** — inherits `__access__` from model + per-method `access=` parameter
- **Schema exposure** — appears in `schema.methods`, auto-discovered by MCP
- **TX routing** — calls route through Matrix with full interceptor chain
- **Tool spec generation** — NetworkMCP already converts `schema.methods` to MCP tool specs

A "custom tool" like web scraping is just an `@expose_route` method on a model:

```python
class WebTools(ActorModel):
    __tablename__ = 'web_tools'
    __storable__ = False  # No storage needed, methods-only

    @expose_route('/scrape', methods=['POST'], access=AUTHENTICATED)
    async def scrape(self, url: str) -> dict:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(url)
        return {'url': url, 'html': resp.text[:50000]}
```

### Insight #2: Pydantic AI Is the Engine

We don't build an LLM client, agent loop, or context manager. Pydantic AI provides:

| Concern | Pydantic AI provides | We DON'T build |
|---------|---------------------|----------------|
| LLM calls | Multi-provider (Ollama, Anthropic, OpenAI, Google, etc.) | ~~LLMClient~~ |
| Agent loop | ReAct-style tool calling with automatic retries | ~~AgentLoop~~ |
| Tool calling | `@agent.tool` + argument validation + result serialization | ~~tool call dispatch~~ |
| Structured output | `output_type=` with Pydantic model validation | ~~output parsing~~ |
| Conversation history | `result.all_messages()` + `message_history=` for continuation | ~~AgentContext~~ |
| Usage tracking | `result.usage()` → input_tokens, output_tokens, requests | ~~token counting~~ |
| Error handling | `ModelRetry`, `UsageLimitExceeded`, automatic retries | ~~retry logic~~ |
| Streaming | `run_stream()` → text chunks, structured output, events | ~~streaming~~ |
| Dependencies | `deps_type=` + `RunContext[Deps]` in tools | ~~context injection~~ |
| Safety limits | `UsageLimits(request_limit=, token_limit=)` | ~~budget guards~~ (for now) |

N3TX's job is purely the **binding layer**:
1. Discover `@expose_route` methods from target actors → register as Pydantic AI tools
2. Route tool calls through Matrix as TX messages (preserving auth + interceptors)
3. Persist agent state via StorableMixin
4. Publish lifecycle events to subscribers

### Insight #3: Actors ARE Tools, Agents ARE Actors

This is the composition chain that the earlier plans missed:

```
Actor
  └─ Has @expose_route methods → these ARE tools
  └─ Registered with Matrix → addressable via TX
  └─ Any actor can be in another agent's tools list

ActorModel (Actor + ProtoModel)
  └─ Same as Actor, plus: storage, schema, CRUD
  └─ CRUD operations are themselves tools (create, list, get, update, delete)

AgentMixin (injected when __agent__ = True)
  └─ Provides: agent_run(prompt, tools, task)
  └─ Provides: tool discovery from actor addresses
  └─ Makes any ActorModel capable of LLM-powered methods

AgentActor (ActorModel + __agent__ = True)
  └─ prompt, tools, llm, constraints are FIELDS (data, not code)
  └─ Instances ARE agents — created from DB, API, or code
  └─ RUN handler calls self.agent_run(self.prompt, self.tools, task)
```

---

## Architecture

### Two Paths, One Mechanism

**Path A — Dynamic agents (primary):**

Agents are instances of AgentActor. Configuration lives in fields (DB-storable).

```python
# In code
scanner = AgentActor(
    name="Grant Scanner",
    prompt="You find government grants. List sources, fetch each URL, "
           "analyze for grants, create Grant records for new ones.",
    tools=["grants", "sources", "web_tools"],
    llm="anthropic:claude-sonnet-4-5-20250929",
)

# Via API
# POST /agents {"name": "Grant Scanner", "prompt": "...", "tools": ["grants", "sources", "web_tools"]}

# From DB (loaded on startup or lazily)
scanner = AgentActor.get(1)  # same object, same capabilities
```

**Path B — Agentic model methods (secondary):**

Any ActorModel with `__agent__ = True` gets AgentMixin injected. Its methods
can use `self.agent_run()` internally.

```python
class Product(ActorModel):
    __tablename__ = 'products'
    __storable__ = True
    __agent__ = True  # injects AgentMixin

    name: str
    price: float

    @expose_route('/create_from_text', methods=['POST'], access=AUTHENTICATED)
    async def create_from_text(self, text: str, tools: list[str] = []) -> str:
        """LLM parses freeform text into a Product and creates it."""
        result = await self.agent_run(
            prompt="Parse the text into a Product with name and price. "
                   "Use products_create to save it.",
            tools=["products"] + tools,  # own model + any extras passed in
            task=text,
        )
        return result
```

Both paths use the same underlying machinery: `AgentMixin.agent_run()`.

### AgentActor — The Dynamic Agent Class

```python
class AgentActor(ActorModel):
    """A model whose instances ARE agents. Configuration is data, not code."""

    __tablename__ = 'agents'
    __storable__ = True
    __agent__ = True  # gets AgentMixin

    name: str
    prompt: str                       # system prompt
    tools: list[str] = []            # actor addresses this agent can talk to
    llm: str = 'ollama:llama3.1'     # pydantic-ai provider:model string
    constraints: dict = {}            # {max_iterations, max_cost_usd, timeout_seconds}

    @expose_route('/run', methods=['POST'], access=AUTHENTICATED)
    async def run(self, task: str, user: User = None) -> str:
        """Execute the agent's reasoning loop."""
        result = await self.agent_run(
            prompt=self.prompt,
            tools=self.tools,
            task=task,
        )
        return json.dumps(result)
```

That's it. The entire agent class. Everything else is inherited from
ActorModel + injected by AgentMixin.

### AgentMixin — The Binding Layer

Injected into any ActorModel with `__agent__ = True`. Provides the bridge
between N3TX's actor system and Pydantic AI.

```python
class AgentMixin:
    """Injected when __agent__ = True. Provides agent_run() and tool discovery."""

    async def agent_run(self, prompt: str, tools: list[str], task: str,
                        user: dict = None, **kwargs) -> dict:
        """
        Core agent execution method.

        Args:
            prompt: System prompt for the LLM
            tools: List of actor addresses whose @expose_route methods become tools
            task: The user/caller task to execute
            user: Auth context (from TX meta or HTTP request)

        Returns:
            {answer, usage: {input_tokens, output_tokens, requests}, messages}
        """
        llm_model = getattr(self, 'llm', None) or kwargs.get('llm',
                                                             'ollama:llama3.1')
        constraints = getattr(self, 'constraints', {}) | kwargs.get(
            'constraints', {})

        # 1. Discover tools from actor addresses
        tool_specs = await self._discover_tools(tools)

        # 2. Create Pydantic AI agent
        ai_agent = Agent(
            llm_model,
            system_prompt=prompt,
            deps_type=AgentDeps,
        )

        # 3. Register discovered tools as Pydantic AI tools
        for spec in tool_specs:
            wrapper = self._make_tool_wrapper(spec)
            ai_agent.tool(wrapper)

        # 4. Build deps
        deps = AgentDeps(
            matrix=self.__class__.__matrix__,
            user=user,
            agent_addr=self.addr if hasattr(self,
                                            '_addr') else self.__class__.__addr__,
        )

        # 5. Run with Pydantic AI's usage limits
        usage_limits = None
        if constraints:
            usage_limits = UsageLimits(
                request_limit=constraints.get('max_iterations'),
                response_tokens_limit=constraints.get('max_response_tokens'),
            )

        result = await ai_agent.call(task, deps=deps, usage_limits=usage_limits)

        # 6. Return structured result
        return {
            'answer': result.output,
            'usage': {
                'input_tokens': result.usage().input_tokens,
                'output_tokens': result.usage().output_tokens,
                'requests': result.usage().requests,
            },
            'messages': len(result.all_messages()),
        }
```

### Progressive Tool Discovery

The `tools` field contains actor addresses. Discovery is two-step:

```
Step 1: LIGHTWEIGHT — Get actor schemas (method names + descriptions)
  Agent knows: ["grants", "web_tools"]
  → TX(name='SCHEMA', target='grants') → {methods: {create: {...}, list: {...}, ...}}
  → TX(name='SCHEMA', target='web_tools') → {methods: {scrape: {...}, extract: {...}}}

  Agent now knows: grants_create, grants_list, grants_get, ...
                   web_tools_scrape, web_tools_extract

Step 2: ON-DEMAND — Full parameter schema available in the method spec
  Each method in schema.methods already carries its parameters, types,
  descriptions. This becomes the Pydantic AI tool's input schema.
```

In practice, Step 1 and Step 2 happen together since `schema.methods`
carries full parameter info. But the two-step model matters for:
- Large tool sets: an agent can present method names to the LLM first
- Dynamic extension: `tools` param on a method adds actors at call time

```python
async def _discover_tools(self, actor_addrs: list[str]) -> list[ToolSpec]:
    """Discover all @expose_route methods from a list of actor addresses."""
    specs = []
    for addr in actor_addrs:
        # Get the actor's schema (already has methods with full signatures)
        schema = await self._get_actor_schema(addr)
        for method_name, method_info in schema.get('methods', {}).items():
            specs.append(ToolSpec(
                actor_addr=addr,
                method_name=method_name,
                tool_name=f"{addr}_{method_name}",
                description=method_info.get('description', ''),
                parameters=method_info.get('parameters', {}),
            ))
        # Also include CRUD operations if the actor is storable
        if schema.get('__tablename__'):
            for crud_op in ['create', 'list', 'get', 'update', 'delete']:
                specs.append(ToolSpec(
                    actor_addr=addr,
                    method_name=crud_op,
                    tool_name=f"{addr}_{crud_op}",
                    description=f"{crud_op.title()} a {schema.get('__name__', addr)}",
                    parameters=_crud_params(crud_op, schema),
                ))
    return specs
```

### Tool Wrapper — TX Routing

Each discovered tool becomes a Pydantic AI tool function that routes through Matrix:

```python
def _make_tool_wrapper(self, spec: ToolSpec):
    """Create a Pydantic AI tool that routes calls through Matrix as TX."""
    target = spec.actor_addr
    action = spec.method_name

    async def tool_fn(ctx: RunContext[AgentDeps], **kwargs) -> dict:
        tx = TX(
            name=action,
            source=ctx.deps.agent_addr,
            target=target,
            data=kwargs,
            meta={'user': ctx.deps.user},
        )
        # Use NetworkAdapter.request() pattern for correlation
        response = await _matrix_request(ctx.deps.matrix, tx)
        if response.is_error:
            raise ModelRetry(response.data.get('message', 'Tool call failed'))
        return response.data

    return Tool(
        function=tool_fn,
        name=spec.tool_name,
        description=spec.description,
        takes_ctx=True,
    )
```

When the LLM calls a tool:
1. Pydantic AI validates arguments against the tool schema
2. The wrapper creates a TX and sends it through Matrix
3. Matrix routes to the target ActorModel
4. The model's handler dispatches to the `@expose_route` method
5. Auth interceptors run (same path as HTTP/MCP requests)
6. Response TX returns via request() correlation
7. Result flows back to Pydantic AI → LLM

### Dynamic Tool Extension via Method Parameters

Any agentic method can accept extra tool addresses at call time:

```python
class Product(ActorModel):
    __agent__ = True

    @expose_route('/create_from_text', methods=['POST'])
    async def create_from_text(self, text: str, tools: list[str] = []) -> str:
        result = await self.agent_run(
            prompt="Parse freeform text into a Product.",
            tools=["products"] + tools,  # own + caller-provided
            task=text,
        )
        return result['answer']
```

Called via TX:
```python
TX(
    name="CREATE_FROM_TEXT",
    target="products",
    data={
        "text": "Modern high heel shoe, $32",
        "tools": ["suppliers", "pricing_tools"]  # extend capabilities
    }
)
```

The calling agent doesn't know or care that `create_from_text` uses an LLM
internally. It's just another tool. And the method can leverage additional
actors the caller provides.

---

## Triggering: TX-Native (from Plan C)

Agents wake up on TX messages. No special scheduling infrastructure needed
in Phase 0:

```python
# Trigger via code
await scanner.send(TX(name='RUN', source='scheduler', target='agents/1',
                      data={'task': 'Scan all sources for new grants'}))

# Trigger via HTTP (Level 3 routing or @expose_route)
POST /agents/1/run  {"task": "Scan all sources"}

# Trigger via lifecycle event (reactive)
Grant._subscribers.append('agents/1')
# → When a Grant is created, scanner receives LIFECYCLE TX
# → Scanner's LIFECYCLE handler can trigger a RUN

# Trigger via another agent (multi-agent)
# Agent A's tool call targets Agent B's run endpoint
TX(name='RUN', target='agents/2', data={'task': 'Analyze this grant page'})
```

---

## Message Flow: Complete Tool Call Lifecycle

```
1. POST /agents/1/run {"task": "Scan grants.gov for grants"}
       ↓
2. AgentActor(id=1).run(task) calls self.agent_run(self.prompt, self.tools, task)
       ↓
3. AgentMixin.agent_run():
   a. _discover_tools(["grants", "web_tools"])
      → Gets schema.methods from each actor
      → Builds ToolSpec list: grants_create, grants_list, web_tools_scrape, ...
   b. Creates pydantic_ai.Agent(self.llm, system_prompt=self.prompt, deps_type=AgentDeps)
   c. Registers tool wrappers on the Pydantic AI agent
   d. Calls ai_agent.run(task, deps=AgentDeps(matrix, user, agent_addr))
       ↓
4. Pydantic AI loop (internal):
   a. Sends messages + tool specs to LLM
   b. LLM responds: tool_use("web_tools_scrape", {url: "https://grants.gov"})
   c. Pydantic AI validates args, calls our TX wrapper
   d. TX(name='scrape', target='web_tools', data={url: ...})
      → Matrix routes → WebTools.handler() → scrape() method
      → Response TX returns via request() correlation
   e. Pydantic AI sends tool result back to LLM
   f. LLM calls grants_create for each grant found
   g. LLM produces final answer → Pydantic AI returns
       ↓
5. agent_run() returns {answer, usage, messages}
6. run() returns JSON result to HTTP response
```

---

## Grant-Watching App (Concrete Example)

### Models (these are the tool providers)

```python
class Grant(ActorModel):
    __tablename__ = 'grants'
    __storable__ = True
    __access__ = {
        'read': ANYONE, 'create': AUTHENTICATED,
        'update': OWNER | ROLE('admin'), 'delete': ROLE('admin'),
    }
    title: str
    agency: str
    deadline: Optional[str] = None
    amount_min: Optional[float] = None
    amount_max: Optional[float] = None
    url: str
    description: str = ''
    status: str = 'discovered'

class Source(ActorModel):
    __tablename__ = 'sources'
    __storable__ = True
    name: str
    url: str
    category: str = 'government'

class WebTools(ActorModel):
    __tablename__ = 'web_tools'
    __storable__ = False

    @expose_route('/scrape', methods=['POST'], access=AUTHENTICATED)
    async def scrape(self, url: str) -> dict:
        """Fetch a URL and return its HTML content."""
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            resp = await client.get(url)
        return {'url': url, 'status': resp.status_code, 'html': resp.text[:50000]}

    @expose_route('/extract', methods=['POST'], access=AUTHENTICATED)
    def extract(self, html: str, selector: str = 'body') -> dict:
        """Extract text from HTML using CSS selectors."""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        elements = soup.select(selector)
        return {'count': len(elements), 'texts': [el.get_text(strip=True) for el in elements[:20]]}
```

### The Agent (an instance, not a subclass)

```python
# In code (or seed script)
grant_scanner = AgentActor(
    name="Grant Scanner",
    prompt="""You are a government grant discovery agent.
Your job: scan web pages for open grants, extract structured data, create Grant records.
Steps:
1. List all sources (sources_list)
2. For each source, scrape the URL (web_tools_scrape)
3. Extract relevant sections (web_tools_extract)
4. For each grant found, check existing grants (grants_list) to avoid duplicates
5. Create new Grant records (grants_create) with: title, agency, deadline, amounts, url, description
Be thorough but cost-efficient.""",
    tools=["grants", "sources", "web_tools"],
    llm="anthropic:claude-sonnet-4-5-20250929",
    constraints={"max_iterations": 50, "max_cost_usd": 1.00},
)

# Or via API (identical result):
# POST /agents {
#   "name": "Grant Scanner",
#   "prompt": "...",
#   "tools": ["grants", "sources", "web_tools"],
#   "llm": "anthropic:claude-sonnet-4-5-20250929"
# }
```

### App Setup

```python
app = create_app(
    models=[User, Grant, Source, WebTools, AgentActor],
    storage="sqlite:///grants.db",
    routing='actor',
)
```

### User Flow

1. Seed sources: `POST /sources {"name": "NSF", "url": "https://nsf.gov/grants"}`
2. Create agent: `POST /agents {"name": "Grant Scanner", "prompt": "...", "tools": ["grants", "sources", "web_tools"]}`
3. Trigger: `POST /agents/1/run {"task": "Scan all sources for new grants"}`
4. Agent runs its ReAct loop, creating Grant records via TX
5. Browse results: `GET /grants`
6. Inspect run: response includes answer, usage, message count

---

## Package Structure

```
src/n3tx/core/agents/
├── __init__.py            # Re-exports: AgentMixin, AgentActor, AgentDeps
├── mixin.py               # AgentMixin: agent_run(), _discover_tools(), _make_tool_wrapper()
├── actor.py               # AgentActor(ActorModel): the dynamic agent class
├── deps.py                # AgentDeps dataclass (Pydantic AI RunContext deps)
├── tools.py               # ToolSpec, tool discovery utilities, schema→tool conversion
└── schema_ext.py          # @schema_extension for agent metadata in JSON Schema
```

Minimal. No scheduler (TX-native for now), no custom interceptors (Pydantic AI
UsageLimits for now), no trace model (Phase 2). Just the binding layer.

---

## Files Modified

| File | Change |
|------|--------|
| `src/n3tx/core/models/proto_model.py` | `__init_subclass__()`: detect `__agent__ = True`, inject AgentMixin |
| `src/n3tx/core/app.py` | Register AgentActor in `create_app()` if agents are used |
| `src/n3tx/__init__.py` | Export AgentActor, AgentMixin |
| `pyproject.toml` | Add `pydantic-ai` dependency |

## Files Created

| File | Purpose |
|------|---------|
| `src/n3tx/core/agents/__init__.py` | Package exports |
| `src/n3tx/core/agents/mixin.py` | AgentMixin: `agent_run()`, tool discovery, tool wrappers |
| `src/n3tx/core/agents/actor.py` | AgentActor: dynamic agent class (prompt, tools, llm as fields) |
| `src/n3tx/core/agents/deps.py` | AgentDeps dataclass |
| `src/n3tx/core/agents/tools.py` | ToolSpec, `discover_tools()`, `make_tool_wrapper()`, schema→tool utilities |
| `src/n3tx/core/agents/schema_ext.py` | `@schema_extension(after='methods')` for agent metadata |

---

## Phased Delivery

### Phase 0: Core Binding (~3-5 days)

**Goal:** `agent_run(prompt, tools, task)` works end-to-end.

1. **AgentMixin** (`mixin.py`)
   - `agent_run(prompt, tools, task, user, **kwargs)`
   - `_discover_tools(actor_addrs)` — get schemas, build ToolSpecs
   - `_make_tool_wrapper(spec)` — create Pydantic AI tool that routes via TX
   - `__init_subclass__` hook in `proto_model.py` — detect `__agent__`, inject mixin

2. **AgentDeps** (`deps.py`)
   - Dataclass: matrix, user, agent_addr

3. **Tool utilities** (`tools.py`)
   - `ToolSpec` dataclass (actor_addr, method_name, tool_name, description, parameters)
   - Schema-to-tool conversion (extract from NetworkMCP, share)
   - CRUD tool spec generation

4. **Tests**
   - Mock LLM via Pydantic AI's `agent.override()`
   - Mock Matrix for tool routing
   - End-to-end: agent_run discovers tools, LLM calls them via TX, results return

**After Phase 0:** Any ActorModel with `__agent__ = True` can call `self.agent_run()`.

### Phase 1: AgentActor + Grant App (~1 week)

**Goal:** Dynamic agents work. Grant-watching app is buildable.

1. **AgentActor** (`actor.py`)
   - Concrete ActorModel with prompt, tools, llm, constraints fields
   - `/run` endpoint via `@expose_route`
   - RUN handler for TX-based triggering

2. **Schema extension** (`schema_ext.py`)
   - Agent metadata in JSON Schema output

3. **Grant-watching models**
   - Grant, Source, WebTools as example/demo models
   - AgentActor instance as the scanner

4. **Tests**
   - AgentActor CRUD (create agent via API, store in DB)
   - AgentActor.run() end-to-end with mock LLM
   - Dynamic tool extension via `tools` parameter
   - Grant app integration test

**After Phase 1:** The grant-watching app works end-to-end.

### Phase 2: Observability & Traces

- AgentRun model (run history, steps, cost, tokens)
- Dump extension for agent status in API responses
- Run audit trail

### Phase 3+: Demand-Gated

- Streaming (Pydantic AI `run_stream()` + SSE)
- Multi-agent (agents as tools for other agents — already works via TX!)
- Persistent memory (conversation history across runs)
- Custom interceptors (cost guard, rate limiter, circuit breaker)
- Scheduling (SchedulerActor or cron-to-TX bridge)
- Structured output (`output_type=` with Pydantic models)

---

## How This Follows N3TX's Philosophy

| Principle | How the agentic system embodies it |
|-----------|-----------------------------------|
| **Model is the app** | AgentActor fields define a complete agent. No config files, no wiring. |
| **Zero to working** | Instantiate AgentActor, get a working agent. Store in DB, trigger via API. |
| **Primitives, not opinions** | `agent_run(prompt, tools, task)` — developer controls everything. |
| **Backend is authoritative** | Agent tools = actor methods. Auth, validation, routing — all backend. |
| **Transparent, not magical** | Every tool call is a TX through Matrix. Traceable, interceptable. |
| **Modular** | AgentMixin is injected. Pydantic AI is external. Tools are actors. Clean boundaries. |

---

## Key Distinction from Earlier Plans

The earlier plans (A, B, C) treated agents as **special model subclasses** —
you write a class with `__agent__` config, and that class IS the agent.

This plan treats agents as **instances of a generic class** — AgentActor is
one class, and each instance is a different agent with different prompt, tools,
and LLM. The class provides the machinery; the data provides the identity.

This means:
- Agents can be created at runtime via API (no code deployment)
- Agents can be cloned, modified, versioned as data
- The same AgentActor class serves unlimited agent personalities
- Subclassing is still available when you need code-level customization
- Any model can have agentic methods via `__agent__ = True` + `self.agent_run()`

The `__agent__ = True` mixin injection still exists — it's what gives
AgentActor (and any other model) the `agent_run()` method. But the mixin
provides capability, not identity.

---

## Verification

1. **Unit tests** — mock LLM via `agent.override()`, mock Matrix for tool routing
2. **Integration test** — AgentActor instance discovers tools from real actors, calls them via TX, creates records in DB
3. **Dynamic creation test** — create agent via `POST /agents`, trigger via `POST /agents/1/run`, verify tools discovered and called
4. **Tool extension test** — method with `tools: list[str] = []` param receives extra actors at call time
5. **Grant-watcher E2E** — define models, seed sources, create scanner agent, trigger scan, verify grants in DB
6. **Regression** — all existing tests pass
