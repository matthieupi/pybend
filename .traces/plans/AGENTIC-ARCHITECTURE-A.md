# PyBend Agentic System — Architecture Plan A

> **Status:** In progress
> **Date:** 2026-03-03
> **Branch:** `v0.10` (from `v0.8`)
> **Target:** v0.10 Wave 1 — Schema Agentic System
> **First use case:** Grant-watching tool (government grant discovery via web scraping + LLM analysis)

---

## Context

**Why:** Build a grant-watching tool (first client product) that scrapes government websites and uses LLM agents to discover open grants. This is the first product built on PyBend's agentic feature, so the system must be generic, composable, and schema-driven.

**What it delivers:** "Define a model, get an agent." A model with `__agent__` configuration gets an LLM-powered reasoning loop that calls tools — where tools are just `@expose_route` methods on other models, already carrying I/O validation and `__access__` auth.

---

## Core Insight #1: @expose_route = Tool

**No new `@tool` decorator.** The existing `@expose_route` decorator already provides everything a tool needs:

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

## Core Insight #2: Pydantic AI Is the Engine

**We don't build an LLM client, agent loop, or context manager.** Pydantic AI already provides:

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

**PyBend's job is purely the binding layer:**
1. Discover `@expose_route` methods → register as Pydantic AI tools
2. Route tool calls through Matrix as TX messages (preserving auth + interceptors)
3. Make agents schema-driven via `__agent__` ClassVar
4. Persist agent state via StorableMixin
5. Publish lifecycle events to subscribers

---

## Decided Architecture

### Design Decisions (Resolved)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **LLM engine** | Pydantic AI | Handles LLM, loop, tools, retries, streaming. We only build the binding. |
| **Base class** | Hybrid: AgentMixin + AgentModel | AgentMixin for existing models; AgentModel(ActorModel) for agent-first models |
| **Tool access** | Explicit whitelist + progressive discovery | `__agent__['tools']` restricts; glob patterns (`'grants_*'`); default = own model only |
| **Custom tools** | `@expose_route` on models | No new decorator. Tools = model methods. Auth, validation, routing already work |
| **LLM provider** | Ollama first (via Pydantic AI) | `'ollama:llama3.1'` — local, free. Switch to any provider by changing the string |
| **Config format** | `__agent__` dict ClassVar | Consistent with `__ui__`, `__access__`. Parsed into AgentConfig internally |

### The Stack

```
Pydantic AI Agent (LLM calls, tool loop, retries, structured output)
    ↕  lives inside the AgentModel/AgentMixin
    ↕
AgentMixin.agent_run() — the binding layer
    ├── Discovers @expose_route methods from whitelisted models
    ├── Creates Pydantic AI tool wrappers that route through Matrix
    ├── Passes PyBend context (Matrix, user, agent) as Pydantic AI deps
    └── Returns result + usage
    ↕
ToolRegistry — discovers tools from model schemas, creates TX-routing wrappers
    ↕  (TX messages through Matrix)
Matrix (existing message routing)
    ↕
ActorModel targets (Grant, WebTools, etc. — @expose_route methods = tools)
```

### Components

| Component | Location | What It Does | New? |
|-----------|----------|-------------|------|
| **AgentMixin** | `agents/agent_mixin.py` | Provides `agent_run()`. Creates Pydantic AI Agent, wires tools, runs it. | Yes |
| **AgentModel** | `agents/agent_model.py` | `AgentModel(AgentMixin, ActorModel)` — agent-first base class | Yes |
| **AgentConfig** | `agents/config.py` | Validated config parsed from `__agent__` dict | Yes |
| **ToolRegistry** | `agents/tool_registry.py` | Discovers `@expose_route` methods, creates Pydantic AI tool wrappers | Yes |
| **tool_utils.py** | `agents/tool_utils.py` | Shared schema→tool conversion (extracted from NetworkMCP) | Yes (refactor) |
| **AgentTrace** | `agents/trace.py` | Records execution steps as storable model (Phase 2) | Yes |
| **Pydantic AI** | `pydantic-ai` package | LLM client, agent loop, tool dispatch, retries, streaming | External dep |
| **@expose_route** | `utils/decorators.py` | Existing — this IS the tool system | Existing |
| **NetworkAdapter** | `api/network_adapter.py` | Existing — request() correlation for tool TX routing | Existing |

### How the Binding Works

```python
class AgentMixin:
    """Injected into models with __agent__. Creates and manages a Pydantic AI Agent."""

    async def agent_run(self, task: str, user: dict = None) -> dict:
        config = AgentConfig.from_dict(self.__agent__)

        # 1. Create Pydantic AI agent with provider string
        ai_agent = Agent(
            f"{config.provider}:{config.model}",    # e.g. 'ollama:llama3.1'
            system_prompt=config.system,
            deps_type=AgentDeps,
            retries=config.retries,
        )

        # 2. Discover @expose_route methods from whitelisted models
        registry = ToolRegistry(matrix)
        tool_specs = await registry.discover(whitelist=config.tools)

        # 3. Register each as a Pydantic AI tool (routes through Matrix)
        for spec in tool_specs:
            wrapper = registry.make_pydantic_ai_tool(spec)
            ai_agent.tool(wrapper)

        # 4. Run with PyBend context as dependencies
        deps = AgentDeps(matrix=matrix, user=user, agent=self)
        result = await ai_agent.run(task, deps=deps)

        # 5. Return structured result
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

### Tool Wrapper Pattern

For each `@expose_route` method discovered from model schemas, create a Pydantic AI tool that routes through Matrix:

```python
@dataclass
class AgentDeps:
    """PyBend context passed to every tool via Pydantic AI's deps system."""
    matrix: Matrix
    user: dict          # JWT user context for auth
    agent: 'AgentMixin' # The agent instance

class ToolRegistry:
    def make_pydantic_ai_tool(self, spec: ToolSpec) -> Tool:
        """Create a Pydantic AI Tool that routes calls through Matrix as TX."""
        target_addr = spec.model_addr   # e.g. 'web_tools'
        action = spec.method_name       # e.g. 'scrape'
        adapter = self._adapter         # NetworkAdapter for request() correlation

        async def tool_fn(ctx: RunContext[AgentDeps], **kwargs) -> dict:
            tx = TX(
                name=action,
                source=f'agent/{ctx.deps.agent.addr}',
                target=target_addr,
                data=kwargs,
                meta={'user': ctx.deps.user},
            )
            response = await adapter.request(tx)
            if response.is_error:
                raise ModelRetry(response.data.get('message', 'Tool call failed'))
            return response.data

        return Tool(
            function=tool_fn,
            name=spec.tool_name,          # e.g. 'web_tools_scrape'
            description=spec.description,
            takes_ctx=True,
        )
```

When the LLM calls a tool:
1. Pydantic AI validates arguments against the tool schema
2. The wrapper creates a TX and sends it through Matrix
3. Matrix routes to the target ActorModel
4. The model's handler dispatches to the `@expose_route` method
5. Auth interceptors run (the tool call goes through the same path as HTTP requests)
6. Response TX returns via `NetworkAdapter.request()` correlation
7. Result flows back to Pydantic AI → LLM

### Dual Integration Pattern

**Path A — Mixin injection (add agency to existing models):**
```python
class Product(ActorModel):
    __tablename__ = 'products'
    __storable__ = True
    __agent__ = {  # AgentMixin auto-injected by __init_subclass__
        'system': 'You manage product inventory...',
        'tools': ['orders_list', 'suppliers_*'],
    }
```

**Path B — AgentModel subclass (agent-first models):**
```python
class GrantScanner(AgentModel):
    __tablename__ = 'grant_scanners'
    __storable__ = True
    __agent__ = {
        'system': 'You find government grants...',
        'tools': ['grants_create', 'web_tools_scrape'],
    }
```

Both paths produce identical agent capabilities.

---

## Message Flow

### Complete tool call lifecycle

```
1. POST /grant_scanners/1/scan {"url": "https://grants.gov"}
       ↓
2. GrantScanner.scan() calls self.agent_run(task)
       ↓
3. AgentMixin.agent_run():
   a. Creates pydantic_ai.Agent('ollama:llama3.1', system_prompt=..., deps_type=AgentDeps)
   b. ToolRegistry.discover(whitelist=['grants_create', 'web_tools_scrape'])
      → Requests schemas from Matrix children
      → Creates Pydantic AI Tool wrappers that route through Matrix
   c. Registers tools on the Pydantic AI agent
   d. Calls ai_agent.run(task, deps=AgentDeps(matrix, user, self))
       ↓
4. Pydantic AI loop (internal):
   a. Sends messages + tool specs to Ollama
   b. Ollama responds: tool_use("web_tools_scrape", {url: "https://grants.gov"})
   c. Pydantic AI validates args, calls our wrapper
   d. Wrapper creates TX(name='scrape', target='web_tools', data={url: ...})
      → Routes through Matrix → WebTools.handler() → scrape() method
      → Response TX returns via NetworkAdapter.request() correlation
   e. Pydantic AI sends tool result back to Ollama
   f. Loop continues — Ollama calls grants_create for each grant
   g. Ollama produces final answer → Pydantic AI validates output
       ↓
5. agent_run() returns {answer, usage, messages}
6. scan() returns result to HTTP response
```

### Tool call routing (TX path)

```
Pydantic AI tool wrapper
    → TX(name='scrape', source='agent/grant_scanners', target='web_tools')
    → NetworkAdapter.request(tx)  [Future-based correlation]
    → Matrix.inbox(tx)
    → Matrix routes to 'web_tools' child
    → WebTools.inbox(tx)
    → WebTools.handler(tx)  [runs interceptors first]
    → getattr(WebTools, 'scrape')(**tx.data)
    → response = {'url': ..., 'html': ...}
    → WebTools.send(tx.reply(data=response))
    → Matrix routes reply back to adapter
    → NetworkAdapter.inbox(tx) matches in_reply_to → resolves Future
    → wrapper receives response.data
    → returns to Pydantic AI → sent to LLM
```

---

## Grant-Watching App (Concrete Example)

### Models

```python
# models/grant.py
class Grant(ActorModel):
    __tablename__ = 'grants'
    __storable__ = True
    __access__ = {
        'read': ANYONE,
        'create': AUTHENTICATED,
        'update': OWNER | ROLE('admin'),
        'delete': ROLE('admin'),
    }

    title: str
    agency: str
    deadline: Optional[str] = None
    amount_min: Optional[float] = None
    amount_max: Optional[float] = None
    url: str
    description: str = ''
    eligibility: str = ''
    status: str = 'discovered'      # discovered, reviewed, expired
    confidence: float = 0.0         # LLM confidence score

# models/web_tools.py — "custom tools" as a model with methods
class WebTools(ActorModel):
    __tablename__ = 'web_tools'
    __storable__ = False             # No storage, methods only

    @expose_route('/scrape', methods=['POST'], access=AUTHENTICATED)
    async def scrape(self, url: str) -> dict:
        """Fetch a URL and return its HTML content."""
        import httpx
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

# models/grant_scanner.py — the agent
class GrantScanner(AgentModel):
    __tablename__ = 'grant_scanners'
    __storable__ = True
    __agent__ = {
        'provider': 'ollama',
        'model': 'llama3.1',
        'system': '''You are a government grant discovery agent.
Your job: scan web pages for open grants, extract structured data, create Grant records.
For each grant found, extract: title, agency, deadline, amount range, eligibility, URL.
Set confidence score based on data completeness (0.0-1.0).
Be thorough but cost-efficient.''',
        'tools': ['grants_create', 'grants_list', 'web_tools_scrape', 'web_tools_extract'],
        'max_iterations': 50,
    }

    name: str
    focus_areas: str = ''
    last_run: Optional[str] = None

    @expose_route('/scan', methods=['POST'], access=AUTHENTICATED)
    async def scan(self, url: str, user: User = None) -> str:
        result = await self.agent_run(f"Scan {url} for government grants about: {self.focus_areas}")
        return json.dumps(result)
```

### App Setup

```python
app = create_app(
    models=[User, Grant, WebTools, GrantScanner],
    storage="sqlite:///grants.db",
    routing='actor',
)
```

### User Flow

1. `POST /grant_scanners` → create scanner: `{name: "NSF Scanner", focus_areas: "renewable energy"}`
2. `POST /grant_scanners/1/scan` → `{url: "https://grants.gov/search-grants"}`
3. Agent runs: Pydantic AI loop calls scrape → extract → grants_create via Matrix
4. `GET /grants` → browse all discovered grants
5. `GET /agent_traces?agent_id=1` → inspect what the agent did

---

## Phased Delivery

### Phase 0: Primitives (~3-5 days)

**Delivers:** ToolRegistry + tool_utils extraction. The plumbing that discovers `@expose_route` methods and creates Pydantic AI tool wrappers.

**New files:**
| File | Purpose |
|------|---------|
| `src/pybend/core/agents/__init__.py` | Package init, re-exports |
| `src/pybend/core/agents/tool_registry.py` | Discovers tools from model schemas, creates Pydantic AI tool wrappers |
| `src/pybend/core/agents/tool_utils.py` | Shared schema→tool conversion (extracted from NetworkMCP) |

**Refactor:**
- Extract `NetworkMCP._schema_to_mcp_tools()` and `_crud_tool_specs()` → `tool_utils.py`
- NetworkMCP imports from `tool_utils` (no behavior change, just shared code)

**Tests:** Mock Matrix for tool discovery, verify tool wrappers route TX correctly.

### Phase 1: Agent Binding (~1 week)

**Delivers:** AgentMixin, AgentModel, AgentConfig. "Define a model, get a working agent."

**New files:**
| File | Purpose |
|------|---------|
| `src/pybend/core/agents/agent_mixin.py` | AgentMixin: creates Pydantic AI Agent, wires tools, provides `agent_run()` |
| `src/pybend/core/agents/agent_model.py` | `AgentModel(AgentMixin, ActorModel)` — agent-first base class |
| `src/pybend/core/agents/config.py` | AgentConfig dataclass (parsed from `__agent__` dict) |

**Modified files:**
| File | Change |
|------|--------|
| `src/pybend/core/models/proto_model.py` | `__init_subclass__`: detect `__agent__`, inject AgentMixin |
| `src/pybend/core/models/proto_schema.py` | Register `agent` schema extension stage |
| `src/pybend/__init__.py` | Export AgentModel, AgentMixin |
| `pyproject.toml` | Add `pydantic-ai` dependency |

**Tests:** End-to-end with mock LLM: agent discovers tools, Pydantic AI calls them via TX, creates records in DB.

**Grant-watching app is buildable after this phase.**

### Phase 2: Observability (~3-5 days)

**New files:**
| File | Purpose |
|------|---------|
| `src/pybend/core/agents/trace.py` | `AgentTrace(ProtoModel)` — records steps, usage, cost |

Uses Pydantic AI's `result.all_messages()` and `result.usage()` to populate traces.

### Phase 3+: Demand-gated

- **Structured output**: Use Pydantic AI's `output_type=` with Pydantic models
- **Streaming**: Use Pydantic AI's `run_stream()` for real-time output
- **Multi-agent**: Agents as Pydantic AI tools of other agents (via TX routing)
- **Memory**: Persist `result.all_messages_json()` via StorableMixin, pass as `message_history=`
- **Deferred tools**: Use Pydantic AI's `DeferredToolRequests` for long-running tools

---

## Key Files Reference

**Reuse (read before implementing):**
- `src/pybend/core/api/network_mcp.py` — `_schema_to_mcp_tools()`, `_crud_tool_specs()` to extract
- `src/pybend/core/api/network_adapter.py` — `request()` correlation pattern for tool TX routing
- `src/pybend/core/models/actor_model.py` — `handler_crud()`, `_publish_lifecycle()` patterns
- `src/pybend/core/models/proto_model.py` — `__init_subclass__` mixin injection pattern (line 68-89)
- `src/pybend/core/models/proto_schema.py` — `@schema_extension`, `register_stage()` for agent stage
- `src/pybend/core/utils/decorators.py` — `@expose_route` (this IS the tool system)

**No changes needed to:**
- `routes_fastapi.py` — agent tools route through Matrix, not HTTP routes
- `authorize/` — auth flows through existing interceptors + @expose_route access=
- Frontend — agents are backend-only (no UI changes)

## Verification

1. **Unit tests** — mock LLM via `agent.override()`, mock Matrix
2. **Integration test** — AgentModel with mock LLM creates Grant records via TX routing through Matrix
3. **Manual test** — run Ollama locally, create GrantScanner, trigger /scan, verify grants in DB
4. **Regression** — all existing tests pass (`pytest tests/unit/`, `pytest actors/tests/`, `pytest ../example/tests/`)
