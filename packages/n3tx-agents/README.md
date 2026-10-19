# 🧠 n3tx-agents: Give Your Models a Brain

> One flag. That's it. Set `__agent__ = True` and your model can reason, call tools, and stream answers — zero config, zero boilerplate.

---

## 🌐 Overview

n3tx-agents makes your N3TX models self-aware. Slap `__agent__ = True` on any
ActorModel and it gains the ability to reason about itself, call tools
on other actors, and stream progressive results -- all without you writing
a single line of agent plumbing. Tool discovery reads schemas from the actor
Matrix, so every `@expose_route` method and CRUD operation in your system is
automatically available as an LLM tool. Your models already know what they
can do — now they can *think* about it too.

---

## 📦 Installation

```bash
pip install n3tx-agents          # standalone
pip install n3tx[agents]         # via meta-package
pip install -e packages/n3tx-agents  # editable dev install
```

Requires `n3tx-core>=0.10.0`, `n3tx-actors>=0.10.0`, `pydantic-ai>=1.0`.

---

## 🚀 Quick Start

You're three lines away from a model that can talk about itself:

```python
from n3tx_actors.models.actor_model import ActorModel
from pydantic import Field

class Product(ActorModel):
    __tablename__ = 'products'
    __storable__ = True
    __agent__ = True                    # injects AgentMixin

    name: str = Field(min_length=1)
    price: float = Field(gt=0)

# Class-level: reasons about the schema
result = await Product.agentic(task='What fields does Product have?')
print(result['answer'])

# Instance-level: reasons about schema + this specific record
product = Product.get(1)
result = await product.agentic(task='Is this product priced competitively?')

# Streaming
async for chunk in product.agentic_stream(task='Describe this product'):
    print(chunk['data'], end='', flush=True)
```

That's the whole thing. No prompt engineering, no tool wiring, no adapter setup. Your model already knows its own schema and relationships — the agent just reads them.

---

## 🧩 Core Concepts

Here's how the pieces fit together.

### AgentMixin vs AgentActor

Two paths to agentic models, depending on what you're building:

**AgentMixin** is injected into any model with `__agent__ = True`. Config
derives from the model definition. Use this when an existing model needs
reasoning capabilities — you want your Product to answer questions, not become a whole new thing.

**AgentActor** is a concrete storable model whose instances ARE agents.
Config lives in DB fields (name, prompt, tools, llm). Use this when agents
are data -- created, configured, and managed at runtime via API. Think chatbots, scanners, assistants that users spin up on the fly.

```python
# Path A: existing model gains reasoning
class Product(ActorModel):
    __agent__ = True

# Path B: agent instances are data
scanner = AgentActor(name="Scanner", prompt="Find grants...", llm="anthropic:claude-sonnet-4-5-20250929")
AgentActor.create(scanner)
```

### 🎛️ Policy/Engine Split

This is the design decision you'll thank us for later.

`agentic()` is the policy layer -- resolves config via 3-tier cascade
(`config.AGENT_DEFAULTS` < `__agent__` dict < kwargs), auto-discovers
prompt and tools. Expose this via HTTP.

`run()` is the engine -- takes fully resolved params, executes the LLM
loop, returns results. Call directly for testing, pipelines, or when you
need full control. Never expose via HTTP.

Think of it this way: `agentic()` is the bouncer, `run()` is the dance floor.

### 🔍 Tool Discovery

Here's where the magic lives. Tools are discovered from actor addresses. Every actor registered in the
Matrix with a `schema()` method contributes tools:
- Storable models contribute CRUD tools (list, get, create, update, delete)
- All `@expose_route` methods become callable tools
- Instance methods auto-include an `id` parameter

Generated agent `update` tools are patch-oriented: only `id` is required and
supplied collection fields replace their complete stored value. Generated HTTP
`PUT` and raw actor updates use the same contract. Agents should not fetch and
resend unrelated fields.

```python
# Auto-discovered from schema relationships
Product.tools()  # -> ['products', 'comments']

# Explicit extras via config
class Scanner(ActorModel):
    __agent__ = {'tools': ['grants', 'web_tools']}
```

You never manually register tools. If it's in the Matrix, it's available.

### ⚙️ Config Cascade

Three tiers, each overriding the previous — so you set sensible defaults once and override only when you need to:

| Tier | Source | Example |
|------|--------|---------|
| 1 | `config.AGENT_DEFAULTS` | Global defaults from env/config |
| 2 | `__agent__` dict | Per-model config in class definition |
| 3 | `agentic()` kwargs | Per-call overrides at runtime |

---

## 📖 API Reference

Everything you can import from the package, at a glance:

| Export | Type | Purpose |
|--------|------|---------|
| `AgentMixin` | class | Injected mixin providing agent methods |
| `AgentActor` | class | Storable model whose instances are agents |
| `AgentTool` | class | Tool reference record (actor address + description) |
| `AgentDeps` | dataclass | Dependency context for Pydantic AI RunContext |
| `ToolSpec` | dataclass | Specification for a discovered tool |
| `discover_tools` | function | Discover ToolSpecs from actor addresses |
| `make_tool` | function | Create a Pydantic AI Tool from a ToolSpec |

### `AgentMixin`

All methods use `@fullmethod` (unified class/instance dispatch), so you call them the same way on a class or an instance:

```python
class AgentMixin:
    def ctx(target) -> str: ...
    def tools(target) -> list[str]: ...
    async def agentic(target, task: str, **kwargs) -> dict: ...
    async def run(target, task: str, prompt: str, tools: list,
                  user: dict = None, constraints: dict = None,
                  thread_id=None, result_type=None,
                  **kwargs) -> dict: ...
    async def agentic_stream(target, task: str, **kwargs): ...  # async gen
    async def run_stream(target, task: str, prompt: str, tools: list,
                         ...) -> AsyncGenerator[dict, None]: ...
```

`agentic()`/`run()` return: `{"answer": str, "usage": {"input_tokens", "output_tokens", "requests"}, "messages": list, "message_count": int}`

`run_stream()` yields: `{"name": "text"|"done"|"error", "data": {...}, "meta": {"stream": True, "seq": N}}`

See [docs/mixin.md](docs/mixin.md) for full method documentation.

### `AgentActor`

```python
class AgentActor(ActorModel):
    __tablename__ = 'agents'
    __storable__ = True
    __agent__ = True

    name: str           # Human-readable name
    prompt: str         # System prompt for the LLM
    tools: list[AgentTool]     # Ordered hydrated tool records
    llm: str            # Provider:model string (default: 'ollama:llama3.1')
    constraints: dict   # Budget/safety limits

    async def agentic(self, task: str, **kwargs) -> str: ...  # @expose_route
```

See [docs/agent-actor.md](docs/agent-actor.md) for full documentation.

### `discover_tools` / `make_tool`

```python
def discover_tools(actor_addrs: list, root, caller_addr: str = None) -> list[ToolSpec]: ...
def make_tool(spec: ToolSpec) -> pydantic_ai.Tool: ...
```

See [docs/tool-discovery.md](docs/tool-discovery.md) for the full pipeline.

---

## 📏 Patterns and Conventions

A few things to keep in mind as you build with agents:

1. **Always use `agentic()` for HTTP-exposed agent calls**, never `run()`.
   `agentic()` handles config resolution. `run()` is the raw engine for
   testing and internal pipelines.

2. **A Matrix must exist before running agents.** Both `agentic()` and
   `run()` require `Actor.root()` to return a Matrix. Without it, a
   `RuntimeError("No Matrix root")` is raised.

3. **Tool calls route through Matrix as TX messages.** Error TXs from
   tools raise `pydantic_ai.ModelRetry`, causing the LLM to retry. The
   agent never sees raw exceptions.

4. **Self-exclusion prevents loops.** `discover_tools()` automatically
   excludes the caller's own address via `caller_addr`. AgentActor
   subclasses also exclude `run` and `stream_run` methods from tools.

5. **Use `pydantic_ai.models.test.TestModel` in tests**, not real LLMs.
   Pass `TestModel(call_tools=[])` for no tool calls, or
   `TestModel(call_tools=['tool_name'])` to simulate specific tool calls.

---

## 🏗️ Package Ecosystem

Here's where n3tx-agents sits in the bigger picture:

```
n3tx (meta-package)
  |
  +-- n3tx-core        Models, schema, storage, config
  |     ^
  |     |
  +-- n3tx-actors      Actor, Matrix, TX, NetworkAdapter
  |     ^
  |     |
  +-- n3tx-agents  <-- THIS PACKAGE (AgentMixin, tool discovery, LLM)
  |
  +-- n3tx-ui          Frontend web components
```

n3tx-agents depends on both n3tx-core (for models, config, introspection)
and n3tx-actors (for Actor, Matrix, TX, NetworkAdapter). It does not
depend on n3tx-ui. The LLM integration uses pydantic-ai.

---

## 📚 Deep Dives

When you're ready to go deeper, these docs have your back:

| Topic | File | When to read |
|-------|------|--------------|
| AgentMixin Methods | [docs/mixin.md](docs/mixin.md) | Working with ctx/tools/agentic/run |
| AgentActor | [docs/agent-actor.md](docs/agent-actor.md) | Dynamic agents stored in DB |
| Tool Discovery | [docs/tool-discovery.md](docs/tool-discovery.md) | Understanding tool generation pipeline |

---

Now go give your models a brain. They've been waiting for this. 🧠
