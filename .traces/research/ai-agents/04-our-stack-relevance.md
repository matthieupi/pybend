# AI Agent Orchestration Mapped to N3TX's Architecture

**Research Document -- Relevance to Our Stack**
Date: 2026-02-26 | Audience: Technical CEO + Engineering Team

---

## Executive Summary

N3TX is a schema-driven framework where a Python model definition is the
single source of truth for the entire stack: storage, API, validation, UI
rendering, and access control. This document examines how N3TX's existing
primitives -- Actor messaging, schema generation, typed methods, ABAC
authorization, and runtime DynamicClass creation -- map onto the requirements
of an AI agent orchestration framework.

The central thesis: **N3TX already implements roughly 60-70% of what an
agent framework needs.** The Actor system IS agent messaging. The schema IS a
capability manifest. `@expose_route` IS tool definition. ABAC IS agent
permission scoping. DynamicClass IS runtime agent instantiation. The missing
pieces -- LLM integration, prompt management, memory, planning, and
execution sandboxing -- are additive, not architectural rewrites.

The implication is significant: N3TX could offer something no existing
agent framework provides -- **"define a model, get an agent"** -- with the
same schema-driven philosophy that already powers its full-stack story.

---

## Table of Contents

1. [Architectural Mapping: N3TX Primitives to Agent Concepts](#1-architectural-mapping)
2. [Actor to Agent: The Messaging Foundation](#2-actor-to-agent)
3. [Matrix to Agent Bus: Message Routing](#3-matrix-to-agent-bus)
4. [Schema to Capability Manifest](#4-schema-to-capability-manifest)
5. [@expose_route to Agent Tools](#5-expose-route-to-agent-tools)
6. [ABAC to Agent Permissions](#6-abac-to-agent-permissions)
7. [DynamicClass to Runtime Agents](#7-dynamicclass-to-runtime-agents)
8. [What N3TX Already Has: Coverage Analysis](#8-coverage-analysis)
9. [What Is Missing: Gap Analysis](#9-gap-analysis)
10. [Proposed Architecture: The Agent Model](#10-proposed-architecture)
11. [Competitive Position](#11-competitive-position)
12. [Implementation Roadmap](#12-implementation-roadmap)

---

## 1. Architectural Mapping

The following table maps every N3TX primitive to its agent-framework
equivalent. Each row represents a concept that exists today in the codebase
and its natural extension into agent orchestration.

| N3TX Primitive | Location | Agent Concept | Mapping Quality |
|---|---|---|---|
| `Actor` base class | `static/core/Actor.js` | Agent base class | Direct -- isolated state, message handlers, supervision tree |
| `Matrix` message bus | `static/core/Matrix.js` | Agent communication bus | Direct -- routes messages between actors by address |
| `TX` transaction | `static/core/TX.js` | Agent message envelope | Direct -- name, source, target, data, meta, timestamp |
| `ProtoModel` | `core/models/proto_model.py` | Agent capability definition | Strong -- schema carries fields, methods, access rules |
| `@expose_route` | `core/utils/decorators.py` | Tool definition decorator | Strong -- typed params, return types, access control |
| `__n3tx_methods_json_signature__` | `core/models/proto_model.py` | Tool manifest generation | Strong -- produces function-calling-compatible signatures |
| `AccessRule` / ABAC | `core/authorize/rules.py` | Agent permission scoping | Direct -- composable rules with SQL pushdown |
| `DynamicClass` / `prototype()` | `static/core/N3TX.js` | Runtime agent instantiation | Strong -- creates typed classes from schema at runtime |
| `Observable` mixin | `static/core/Observable.js` | Agent event/state subscriptions | Direct -- signal/observe pattern |
| `StorableMixin` | `core/models/storable_mixin.py` | Agent state persistence | Direct -- CRUD with injected storage backend |
| `NetworkAdapter` | `static/core/transport/NetworkAdapter.js` | Remote agent transport | Partial -- HTTP/WS, needs agent-specific protocols |
| `N3TX.SCHEMA()` bootstrap | `static/core/N3TX.js` | Agent capability discovery | Strong -- fetches schema, creates runtime class, replays queued messages |

---

## 2. Actor to Agent: The Messaging Foundation

### What N3TX's Actor Already Provides

The `Actor` class in `/workspace/src/n3tx/static/core/Actor.js` implements
a textbook actor model inspired by Akka:

```javascript
// From Actor.js -- the base class
export default class Actor {
    #addr;
    #parent;
    #children;

    constructor(addr = "") {
        this.#addr = addr;
        this.#parent = this.constructor;
        this.#children = new Map();
        this.constructor.register(this);
        this.inbox = this.inbox.bind(this);
        this.send = this.send.bind(this);
    }

    inbox(event) {
        return Actor._inbox.call(this, event);
    }

    spawn(addr, ActorClass, ...args) {
        const child = new ActorClass(addr, ...args);
        this.#children.set(addr, child);
        return child;
    }
}
```

This gives us five agent fundamentals for free:

1. **Isolated state** -- Each actor has private `#addr`, `#parent`,
   `#children`. An agent's working memory, context window, and tool state
   would live here.

2. **Address-based identity** -- Every actor has a unique address. Agents
   need addressable identity for routing tasks and tracking provenance.

3. **Message-driven execution** -- The `inbox()` method dispatches events to
   handler methods by name. An agent receiving a "research" task would
   have a `RESEARCH(data, tx)` handler, identical to how `N3TX` has
   `ATTACH`, `READ`, `UPDATE` handlers today.

4. **Supervision hierarchy** -- `spawn()` creates child actors under a
   parent. An orchestrator agent spawning specialist agents is the same
   pattern: `orchestrator.spawn('researcher', ResearchAgent, config)`.

5. **Hierarchical routing** -- `Actor._send()` routes locally first, then
   bubbles up to the root. This is exactly how agent delegation works:
   try local handling, escalate to the orchestrator.

### The Mapping in Practice

```
N3TX Actor                          AI Agent
--------------------------------------------
actor.addr                     →      agent.id ("research-agent-001")
actor.inbox(event)             →      agent.receive(task)
actor.send(event)              →      agent.delegate(task)
actor.spawn(addr, Class)       →      orchestrator.create_agent(role, config)
actor.children                 →      orchestrator.managed_agents
Actor._send routing            →      agent message routing / delegation
Actor.subclass(Class, Mixin)   →      Agent.subclass(Class, LLMMixin, ToolMixin)
```

### What Needs Extension

The current Actor is synchronous and frontend-only. Agent execution requires:

- **Async message processing** -- Agents wait for LLM responses (seconds to
  minutes). The backend Actor needs async `inbox()` with queue semantics.
- **Backpressure** -- When an orchestrator spawns 10 agents each making LLM
  calls, we need rate limiting. The current Actor has no flow control.
- **Lifecycle hooks** -- `on_start()`, `on_stop()`, `on_error()`. The Actor
  has `spawn()` but no lifecycle management beyond construction.

---

## 3. Matrix to Agent Bus: Message Routing

### Current Matrix Architecture

The `Matrix` in `/workspace/src/n3tx/static/core/Matrix.js` is the root
actor and universal message router:

```javascript
// From Matrix.js
export class Matrix extends Actor {
    constructor(addr, url="") {
        super(addr);
        if (!Actor.root) {
            Actor.registerRoot(this);
        }
        this.remote = new NetworkAdapter(this, url);
    }

    inbox(event) {
        let tx = event instanceof TX ? event : new TX(event);
        let targetAddr = tx.target.split('/')[0];

        if (tx.name === E.connect) {
            tx = this.connect(tx.source, tx.target);
        } else if (this.children.has(targetAddr)) {
            tx = this.children.get(targetAddr).inbox(tx.repr());
        } else {
            tx = this.remote.send(tx);  // Forward to network
        }
        return tx;
    }
}
```

The routing logic is three steps:

1. **Local child lookup** -- If the target actor is registered locally,
   deliver directly.
2. **Remote forwarding** -- If not local, forward via `NetworkAdapter`
   (HTTP or WebSocket).
3. **Connect protocol** -- Special `CONNECT` event for establishing
   actor-to-actor bindings.

### How This Maps to Agent Communication

```
Matrix Routing                        Agent Bus Routing
------------------------------------------------------------
matrix.children.has(target)    →      bus.has_agent(agent_id)
matrix.children.get(target)    →      bus.get_agent(agent_id)
  .inbox(tx)                          .receive(message)
matrix.remote.send(tx)         →      bus.forward_to_remote(message)
matrix.connect(src, tgt)       →      bus.establish_channel(agent_a, agent_b)
```

The `TX` message envelope already has everything an agent message needs:

```javascript
// From TX.js -- the message envelope
class TX {
    constructor(event) {
        let {name, source, target, data={}, meta={}, timestamp=Date.now()} = event;
        this.name = name;       // → message type: "RESEARCH", "SUMMARIZE", "APPROVE"
        this.source = source;   // → sender agent ID
        this.target = target;   // → recipient agent ID
        this.data = data;       // → task payload (prompt, context, parameters)
        this.meta = meta;       // → routing metadata (priority, ttl, trace_id)
        this.tst = timestamp;   // → timing for observability
    }
}
```

### What the Agent Bus Needs Beyond Matrix

| Matrix Has | Agent Bus Needs | Gap |
|---|---|---|
| Synchronous delivery | Async with acknowledgment | Medium -- need queue semantics |
| Local + HTTP routing | Multi-transport (HTTP, WebSocket, inter-process) | Small -- NetworkAdapter already supports WS |
| Address-based routing | Content-based routing + capability matching | Medium -- need a skill registry |
| No persistence | Message durability / replay | Medium -- add event store |
| No observability | Tracing, logging, cost tracking | Medium -- needs instrumentation layer |
| Single Matrix instance | Distributed bus (multi-process) | Large -- architectural extension |

---

## 4. Schema to Capability Manifest

### The Schema IS an Agent's Self-Description

This is the most powerful mapping. N3TX's `ProtoModel.schema()` generates
a JSON Schema document that carries everything about an entity: its data
structure, validation rules, callable methods, access permissions, and UI
hints. Replace "entity" with "agent" and the schema becomes a **capability
manifest**.

From `/workspace/src/n3tx/core/models/proto_model.py`:

```python
# ProtoModel.schema() generates:
{
    "$schema": "http://localhost:5000/Schema",
    "$id": "http://localhost:5000/Product",
    "__name__": "Product",
    "__tablename__": "products",
    "properties": {
        "name": {"type": "string", "minLength": 1, "maxLength": 200},
        "price": {"type": "number", "exclusiveMinimum": 0},
        "description": {"type": "string"}
    },
    "methods": {
        "comment": {
            "route": "/comment",
            "methods": ["POST"],
            "scope": "instancemethod",
            "parameters": {
                "comment": {"$ref": "#/$defs/Comment"}
            },
            "returns": {"type": "string"}
        },
        "favorite": {
            "route": "/favorite",
            "methods": ["POST"],
            "scope": "instancemethod",
            "parameters": {},
            "returns": {"type": "string"},
            "access": {"rule": "authenticated"}
        }
    },
    "access": {
        "read": {"rule": "anyone"},
        "create": {"rule": "authenticated"},
        "update": {"op": "or", "rules": [{"rule": "owner"}, {"rule": "role", "roles": ["admin"]}]},
        "delete": {"rule": "role", "roles": ["admin"]}
    },
    "$defs": { ... }
}
```

### Mapping Schema to Agent Capability Manifest

Now consider what an agent capability manifest looks like:

```
N3TX Schema Section              Agent Capability Manifest
------------------------------------------------------------
properties                  →      Agent state / working memory schema
methods                     →      Agent tools / callable actions
methods[x].parameters       →      Tool parameter schemas (typed)
methods[x].returns          →      Tool return type
methods[x].access           →      Tool permission requirements
access                      →      Agent-level permission scope
$defs                       →      Dependency agent schemas
$id                         →      Agent endpoint / identity URL
ui.renderer                 →      Agent interface type (chat, dashboard, API)
```

The `__n3tx_methods_json_signature__()` method in `proto_model.py`
already generates method signatures that are structurally close to
OpenAI's function calling format and Anthropic's tool use format:

```python
# From proto_model.py -- method signature extraction
@classmethod
def __n3tx_methods_json_signature__(cls) -> dict:
    methods = {}
    for method_name in dir(cls):
        method = getattr(cls, method_name)
        if not (callable(method) and hasattr(method, '__endpoint__')):
            continue
        sig = inspect.signature(method)
        type_hints = get_type_hints(method)

        parameters = {}
        for name, param in sig.parameters.items():
            if name in ('cls', 'self', 'user'):
                continue
            ptype = type_hints.get(name, param.annotation)
            parameters[name] = pydantic_schema_for_type(ptype)

        rtype = type_hints.get('return', None)
        methods[method_name] = {
            'route': endpoint_info['route'],
            'methods': endpoint_info['methods'],
            'scope': method_type,
            'parameters': parameters,
            'returns': pydantic_schema_for_type(rtype),
        }
    return methods
```

This is already 80% of what you need to generate an OpenAI-compatible
`tools` array or an Anthropic `tool_use` block. The conversion is mechanical.

---

## 5. @expose_route to Agent Tools

### The Decorator Today

From `/workspace/src/n3tx/core/utils/decorators.py`:

```python
def expose_route(route, methods=["POST"], access=None):
    """
    Decorator to mark a method as an endpoint to be exposed via the API.
    """
    def decorator(func):
        func.__endpoint__ = {
            'route': route,
            'methods': methods,
            'access': access,
        }
        return func
    return decorator
```

And its usage in `/workspace/src/n3tx/example/models/product.py`:

```python
@expose_route('/comment', methods=['POST'])
def comment(self, comment: Comment, user: User = None) -> str:
    """Add a comment to the product."""
    comment.user_owner = user.id if user else 1
    comment.__owner__ = self
    comment.save()
    return comment.model_dump_json()

@expose_route('/favorite', methods=['POST'], access=AUTHENTICATED)
def favorite(self, user: User = None) -> str:
    """Toggle favorite."""
    ...
```

### How Close Is This to Function-Calling / MCP?

Side-by-side comparison:

```python
# N3TX @expose_route (existing)
@expose_route('/comment', methods=['POST'])
def comment(self, comment: Comment, user: User = None) -> str:
    """Add a comment to the product."""
    ...

# OpenAI function calling format (target)
{
    "type": "function",
    "function": {
        "name": "comment",
        "description": "Add a comment to the product.",
        "parameters": {
            "type": "object",
            "properties": {
                "comment": {"$ref": "#/$defs/Comment"}
            },
            "required": ["comment"]
        }
    }
}

# Anthropic tool_use format (target)
{
    "name": "comment",
    "description": "Add a comment to the product.",
    "input_schema": {
        "type": "object",
        "properties": {
            "comment": {"$ref": "#/$defs/Comment"}
        },
        "required": ["comment"]
    }
}
```

The conversion from N3TX's existing `__n3tx_methods_json_signature__()`
output to either format requires:

1. Rename `parameters` to `properties` (and wrap in `type: object`)
2. Extract `description` from the docstring
3. Compute `required` from parameters without defaults
4. Drop `route`, `methods`, `scope` (HTTP-specific, not LLM-relevant)

This is a thin adapter function, not an architectural change.

### The @expose_tool Decorator (Proposed)

```python
# Proposed: @expose_tool -- same pattern, agent-specific metadata
@expose_tool(
    description="Search the web for recent information",
    access=AUTHENTICATED,
    cost_limit=0.05,       # Max cost per invocation
    timeout=30,            # Seconds
    sandbox=True,          # Run in isolated environment
)
def web_search(self, query: str, max_results: int = 5) -> list[dict]:
    """Search the web and return structured results."""
    ...
```

The implementation would follow the same pattern as `expose_route`:
attach metadata to the function, let the framework extract it during
schema generation, and include it in the capability manifest.

---

## 6. ABAC to Agent Permissions

### Current Authorization Architecture

From `/workspace/src/n3tx/core/authorize/rules.py`:

```python
class AccessRule(ABC):
    @abstractmethod
    def evaluate(self, ctx: AccessContext) -> bool: ...

    def sql_filter(self, ctx: AccessContext) -> Optional[Tuple[str, List[Any]]]: ...

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]: ...

    def __or__(self, other): return OrRule(self, other)
    def __and__(self, other): return AndRule(self, other)
    def __invert__(self): return NotRule(self)


ANYONE = _Anyone()           # Always grants access
AUTHENTICATED = _Authenticated()  # Requires authentication
OWNER = _Owner()             # Matches resource owner
def ROLE(*roles): ...        # Matches user role
class Where(AccessRule): ... # Attribute-based conditions
```

And from `/workspace/src/n3tx/core/authorize/context.py`:

```python
@dataclass(frozen=True)
class AccessContext:
    user: Dict[str, Any]
    action: str
    model_class: Type[Any]
    resource: Optional[Any] = None
    parent_id: Optional[int] = None

    @property
    def user_id(self) -> Optional[int]: ...
    @property
    def user_role(self) -> Optional[str]: ...
    @property
    def is_authenticated(self) -> bool: ...
```

### Mapping to Agent Permission Scoping

Agent permissions are a superset of user permissions. An agent acts
**on behalf of** a user, with additional constraints:

```python
# Current: User permissions
__access__ = {
    'read':   ANYONE,
    'create': AUTHENTICATED,
    'update': OWNER | ROLE('admin'),
    'delete': ROLE('admin'),
}

# Proposed: Agent permissions (extends the same system)
__access__ = {
    'read':   ANYONE,
    'create': AUTHENTICATED,
    'update': OWNER | ROLE('admin'),
    'delete': ROLE('admin'),
    # New agent-specific actions:
    'delegate':    ROLE('orchestrator'),      # Can delegate tasks to other agents
    'invoke_tool': AUTHENTICATED & BUDGET(remaining__gt=0),  # Can use tools if budget remains
    'spawn':       ROLE('orchestrator') & Where(agent_count__lt=10),  # Can create child agents
}
```

The composable rule algebra (`|`, `&`, `~`) already supports this. New
leaf rules would be:

```python
# Proposed agent-specific rules (same AccessRule base class)
class BUDGET(AccessRule):
    """Grants access only if the agent's remaining budget meets conditions."""
    def evaluate(self, ctx): ...
    def to_dict(self): return {"rule": "budget", "conditions": self.conditions}

class CAPABILITY(AccessRule):
    """Grants access only if the agent has the required capability."""
    def evaluate(self, ctx): ...
    def to_dict(self): return {"rule": "capability", "required": self.capabilities}

class DELEGATION_DEPTH(AccessRule):
    """Limits how deep agent delegation chains can go."""
    def evaluate(self, ctx): ...
    def to_dict(self): return {"rule": "delegation_depth", "max": self.max_depth}
```

The key insight: **the authorize package has zero N3TX imports**. It is
already a standalone ABAC library. Adding agent-specific rules requires zero
changes to the core authorization engine -- just new `AccessRule` subclasses.

---

## 7. DynamicClass to Runtime Agents

### How DynamicClass Works Today

From `/workspace/src/n3tx/static/core/N3TX.js`, the `prototype()` function:

```javascript
function prototype(addr, schema, href) {
    const fields = Object.keys(schema.properties || {});
    const methods = Object.keys(schema.methods || {});

    // 1. Create a subclass of N3TX with dynamic properties
    const DynamicClass = class extends N3TX {
        static instances = new Map();
        static _schema = schema;

        constructor(data) {
            super(className, data.id);
            this.value = data;
        }
    };

    // 2. Add schema properties as typed getters/setters
    for (const field of fields) {
        Object.defineProperty(DynamicClass.prototype, field, {
            get() { return this.value?.[field]; },
            set(value) {
                // Type checking against schema
                if (!isTypeCompatible(value, definition.type)) {
                    throw new TypeError(...);
                }
                this.value[field] = value;
                this.notify(field, value, oldValue);
            },
        });
    }

    // 3. Add schema methods as callable functions
    for (const method of methods) {
        DynamicClass.prototype[method] = function(...args) {
            // Validate args against schema
            this.call(method, args, {});
        };
    }

    // 4. Apply Actor and Observable mixins
    Actor.subclass(DynamicClass, Observable);

    return DynamicClass;
}
```

### The Mapping: Schema In, Agent Out

The `prototype()` function takes a JSON schema and produces a fully
functional class with:

- Typed properties (from `schema.properties`)
- Callable methods (from `schema.methods`)
- Message handling (from `Actor.subclass`)
- Event subscriptions (from `Observable` mixin)
- Instance registry (from `DynamicClass.instances`)

Replace "entity" with "agent":

```
N3TX.SCHEMA(data) → prototype(addr, schema, href) → DynamicClass
    ↓                                                    ↓
AgentRegistry.register(manifest) → agentPrototype(name, manifest) → AgentClass
```

A backend equivalent of `prototype()` would:

```python
# Proposed: Backend DynamicAgent creation from schema
def create_agent_class(name: str, manifest: dict) -> Type[Agent]:
    """Create an Agent class from a capability manifest at runtime."""

    # Build Pydantic model for agent state
    state_fields = {}
    for field_name, field_def in manifest.get('properties', {}).items():
        state_fields[field_name] = (
            _resolve_type(field_def),
            Field(default=field_def.get('default'))
        )

    # Build tool methods
    tools = {}
    for method_name, method_def in manifest.get('methods', {}).items():
        tools[method_name] = _build_tool_function(method_def)

    # Build access rules
    access = _deserialize_access(manifest.get('access', {}))

    # Create the class dynamically
    AgentClass = type(name, (ProtoModel, AgentMixin), {
        '__tablename__': manifest.get('__tablename__', name.lower() + 's'),
        '__storable__': True,
        '__access__': access,
        '__annotations__': {k: v[0] for k, v in state_fields.items()},
        **tools,
    })

    return AgentClass
```

This is the most compelling part of the mapping: **the mechanism for
creating typed, capable entities from schema at runtime already exists**.
The frontend does it today for UI entities. The backend can do it for
agent entities using the same schema format.

---

## 8. What N3TX Already Has: Coverage Analysis

### Component-by-Component Inventory

| Agent Framework Requirement | N3TX Component | Status | Coverage |
|---|---|---|---|
| **Agent identity & addressing** | `Actor.addr`, `N3TX.$id` | Exists | 95% |
| **Agent messaging** | `Actor.inbox/send`, `TX`, `Matrix` | Exists | 80% |
| **Agent state schema** | `ProtoModel`, JSON Schema generation | Exists | 90% |
| **Tool definitions** | `@expose_route`, `__n3tx_methods_json_signature__` | Exists | 75% |
| **Tool parameter validation** | Pydantic models, `make_custom_post` type parsing | Exists | 85% |
| **Permission scoping** | `authorize` package (ABAC) | Exists | 90% |
| **State persistence** | `StorableMixin`, SQLite/JSON backends | Exists | 85% |
| **Runtime class creation** | `prototype()` in N3TX.js | Exists (frontend) | 70% |
| **Event subscriptions** | `Observable` mixin | Exists | 80% |
| **API generation** | `register_routes()`, `routes_fastapi.py` | Exists | 90% |
| **App bootstrapping** | `create_app()`, `N3TXApp` builder | Exists | 85% |
| **Supervision hierarchy** | `Actor.spawn()`, `children` Map | Exists | 60% |
| **Remote transport** | `NetworkAdapter` (HTTP + WS) | Exists | 50% |
| **Schema discovery** | `N3TX.SCHEMA()`, `GET /{ClassName}` | Exists | 90% |
| **User injection** | `_resolve_user()` in routes | Exists | 80% |
| **Error semantics** | `MethodError`, HTTP status codes | Exists | 75% |
| --- | --- | --- | --- |
| **LLM integration** | -- | Missing | 0% |
| **Prompt management** | -- | Missing | 0% |
| **Conversation memory** | -- | Missing | 0% |
| **Planning / reasoning** | -- | Missing | 0% |
| **Tool execution sandbox** | -- | Missing | 0% |
| **Cost tracking / budgets** | -- | Missing | 0% |
| **Agent observability** | -- | Missing | 0% |
| **Multi-agent coordination** | -- | Missing | 0% |

### Coverage Estimate

**Existing infrastructure that maps directly to agent needs: ~65%**

The 65% is not a loose analogy. These are concrete, production-tested
components: a message bus that routes typed messages between addressed
actors, a schema generator that produces capability manifests with typed
method signatures, an authorization engine with composable rules, a
storage layer with CRUD operations, and a runtime class factory.

The remaining 35% is the AI-specific layer: the LLM client, prompt
engineering, memory management, planning loops, and the coordination
protocols that make multiple agents work together.

---

## 9. What Is Missing: Gap Analysis

### Gap 1: LLM Integration Layer

**What it is:** A client that sends prompts to LLM providers (OpenAI,
Anthropic, local models) and handles streaming responses, retries,
token counting, and cost tracking.

**Why N3TX doesn't have it:** N3TX is a web framework, not an AI
framework. It has never needed to call an LLM.

**Proposed integration point:** A new mixin, analogous to `StorableMixin`:

```python
class LLMMixin:
    """Injected into Agent models that need LLM capabilities."""
    __llm_provider__: ClassVar[str] = 'anthropic'
    __llm_model__: ClassVar[str] = 'claude-sonnet-4-20250514'
    __system_prompt__: ClassVar[str] = ''

    async def think(self, messages: list[dict]) -> str:
        """Send messages to LLM and return response."""
        ...

    async def think_with_tools(self, messages: list[dict], tools: list[dict]) -> dict:
        """Send messages with tool definitions, handle tool_use responses."""
        ...
```

**Effort estimate:** Medium. The client itself is straightforward (httpx +
provider SDKs). The complexity is in streaming, retries, and cost tracking.

### Gap 2: Prompt Management

**What it is:** System prompts, few-shot examples, template rendering,
prompt versioning. The instructions that tell an agent how to behave.

**Why it maps to schema:** A model's `__ui__` dict already carries rendering
hints for the frontend. An agent's `__prompt__` dict would carry behavior
hints for the LLM:

```python
class ResearchAgent(ProtoModel, AgentMixin):
    __prompt__ = {
        'system': "You are a research analyst. You produce structured reports.",
        'few_shot': [
            {"role": "user", "content": "Research X"},
            {"role": "assistant", "content": "## Report on X\n..."},
        ],
        'temperature': 0.3,
        'max_tokens': 4096,
    }
```

**Effort estimate:** Small. Prompt management is configuration, not
architecture. The schema already carries arbitrary metadata.

### Gap 3: Conversation Memory / Context

**What it is:** Short-term (conversation history), medium-term (session
context), and long-term (vector store) memory for agents.

**Proposed approach:** Memory as a model:

```python
class AgentMemory(ProtoModel):
    __tablename__ = 'agent_memories'
    __storable__ = True

    agent_id: int = Field(...)
    role: str = Field(...)        # "user", "assistant", "tool"
    content: str = Field(...)
    embedding: Optional[list[float]] = Field(default=None)
    created_at: str = Field(...)
    token_count: int = Field(default=0)
```

This leverages `StorableMixin` for persistence. SQLite handles short/medium
term. A vector extension (sqlite-vec or external) handles long-term
similarity search.

**Effort estimate:** Medium. The storage layer exists. The memory management
logic (context window trimming, summarization, retrieval) is new work.

### Gap 4: Planning / Reasoning Loop

**What it is:** The agent execution loop: receive task, plan steps, execute
tools, observe results, iterate or complete.

**This is the core innovation space.** Frameworks like LangGraph, CrewAI,
and AutoGen each have their own approach. N3TX's contribution would be
the schema-driven approach: the plan is derived from the capability
manifest, not hand-coded.

**Effort estimate:** Large. This is the most complex missing piece. But the
Actor messaging pattern provides the execution substrate.

### Gap 5: Tool Execution Sandbox

**What it is:** Isolated execution environments for agent tools, preventing
a rogue tool call from affecting the system.

**Proposed approach:** `@expose_tool(sandbox=True)` runs the tool in a
subprocess with resource limits. Non-sandboxed tools run in-process
(like `@expose_route` today).

**Effort estimate:** Medium. Python's `subprocess` + resource limits cover
basic sandboxing. Heavier isolation (containers) is optional.

### Gap 6: Agent Observability

**What it is:** Tracing agent decisions, tool calls, costs, latencies.
The equivalent of the `Logging` utility that N3TX already has, but
structured for AI operations.

**Proposed approach:** Extend `TX` with trace metadata:

```python
@dataclass
class AgentTrace:
    trace_id: str
    agent_id: str
    action: str           # "think", "tool_call", "delegate"
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int
    timestamp: datetime
```

**Effort estimate:** Small-Medium. The messaging layer already has
timestamps and metadata. Adding structured tracing is incremental.

---

## 10. Proposed Architecture: The Agent Model

### The Core Idea

```python
class ResearchAgent(ProtoModel, AgentMixin):
    """Define a model, get an agent."""
```

Just as `ProtoModel` with `__storable__ = True` gives you CRUD, API
endpoints, schema generation, and UI rendering, `ProtoModel` with
`AgentMixin` would give you an LLM-powered agent with tools, memory,
permissions, and orchestration -- all derived from the model definition.

### Concrete Example

```python
from n3tx import ProtoModel, expose_route, Field, ListRef
from n3tx.agent import AgentMixin, expose_tool, BUDGET
from n3tx.core.authorize import AUTHENTICATED, ROLE

class ResearchAgent(ProtoModel, AgentMixin):
    """An agent that researches topics and produces structured reports."""

    __tablename__ = 'research_agents'
    __storable__ = True
    __agent__ = True

    # Agent configuration (carried in schema, like __ui__)
    __llm__ = {
        'provider': 'anthropic',
        'model': 'claude-sonnet-4-20250514',
        'temperature': 0.3,
        'max_tokens': 4096,
    }
    __prompt__ = {
        'system': (
            "You are a senior research analyst. You produce comprehensive, "
            "well-sourced reports on technical topics. Use your tools to "
            "gather information before writing."
        ),
    }

    # Agent permissions
    __access__ = {
        'create':  ROLE('admin'),
        'invoke':  AUTHENTICATED & BUDGET(remaining__gt=0),
        'read':    AUTHENTICATED,
        'delete':  ROLE('admin'),
    }

    # Agent state (persisted via StorableMixin)
    name: str = Field(default="Research Agent")
    status: str = Field(default="idle")  # idle, working, done, error
    topic: str = Field(default="")
    report: str = Field(default="")
    budget_remaining: float = Field(default=1.0)  # USD
    memories: ListRef['AgentMemory'] = Field(default=[])

    # Tools (exposed as both API endpoints AND LLM tool definitions)
    @expose_tool(
        description="Search the web for information on a topic",
        access=AUTHENTICATED,
        cost_limit=0.02,
    )
    def web_search(self, query: str, max_results: int = 5) -> list[dict]:
        """Search the web and return structured results."""
        import httpx
        # ... actual search implementation
        return results

    @expose_tool(
        description="Read and extract content from a URL",
        access=AUTHENTICATED,
        cost_limit=0.01,
    )
    def read_url(self, url: str) -> str:
        """Fetch and extract the main content from a URL."""
        # ... actual fetch implementation
        return content

    @expose_tool(
        description="Save a section of the research report",
        access=AUTHENTICATED,
    )
    def save_section(self, title: str, content: str) -> str:
        """Save a section to the report."""
        self.report += f"\n## {title}\n{content}\n"
        self.save()
        return f"Saved section: {title}"

    # High-level task endpoint (like @expose_route, but triggers agent loop)
    @expose_route('/research', methods=['POST'], access=AUTHENTICATED)
    async def research(self, topic: str, user: 'User' = None) -> str:
        """Start a research task on the given topic."""
        self.topic = topic
        self.status = "working"
        self.save()

        # The agent loop (provided by AgentMixin)
        result = await self.run(
            task=f"Research the following topic and produce a comprehensive report: {topic}",
            tools=[self.web_search, self.read_url, self.save_section],
            max_iterations=10,
        )

        self.status = "done"
        self.save()
        return result
```

### What Gets Generated From This Definition

| Concern | Generated From | How |
|---|---|---|
| Agent state schema | Field definitions | `ProtoModel.schema()` (existing) |
| CRUD API for agent instances | `__storable__`, `__tablename__` | `register_routes()` (existing) |
| Tool definitions for LLM | `@expose_tool` methods | `__agent_tools_signature__()` (new, modeled on `__n3tx_methods_json_signature__`) |
| Agent API endpoints | `@expose_route` methods | `register_routes()` (existing) |
| Permission scoping | `__access__` | `authorize` package (existing) |
| State persistence | `StorableMixin` | Injected via `__storable__` (existing) |
| Capability manifest | All of the above | Extended `schema()` method |
| Frontend agent card | Schema properties + ui | `ntx-item` (existing) |
| Agent memory table | `ListRef[AgentMemory]` | Join model generation (existing) |

### The Agent Execution Loop

```
                         AgentMixin.run()
                              |
                    +---------+---------+
                    |                   |
               [1] THINK          [4] COMPLETE
                    |                   |
            LLM generates          Return result
            response               Update state
                    |
            +-------+-------+
            |               |
       [2] TOOL_USE    [3] TEXT
            |               |
       Execute tool    Add to memory
       Add result      Check if done
       to memory            |
            |          If not done → [1]
            +-→ [1]
```

This loop maps directly onto the Actor messaging pattern:

```
THINK   → agent.send(TX{name: "THINK", data: {messages, tools}})
         → LLMMixin handles, returns response
TOOL    → agent.send(TX{name: "TOOL_CALL", data: {name, input}})
         → Tool executor handles, returns result
RESULT  → agent.send(TX{name: "TOOL_RESULT", data: {result}})
         → Added to memory, triggers next THINK
DONE    → agent.send(TX{name: "COMPLETE", data: {result}})
         → State updated, watchers notified
```

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    N3TX Agent Layer                     │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ ResearchAgent│  │ CoderAgent   │  │ ReviewAgent  │  │
│  │ (ProtoModel  │  │ (ProtoModel  │  │ (ProtoModel  │  │
│  │  + AgentMixin│  │  + AgentMixin│  │  + AgentMixin│  │
│  │  + Storable) │  │  + Storable) │  │  + Storable) │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
│         │                  │                  │          │
│  ┌──────┴──────────────────┴──────────────────┴──────┐  │
│  │              Agent Message Bus (Matrix)            │  │
│  │  TX{name, source, target, data, meta, timestamp}  │  │
│  └──────────────────────┬────────────────────────────┘  │
│                         │                                │
│  ┌──────────────────────┴────────────────────────────┐  │
│  │                 Shared Services                     │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ │  │
│  │  │   LLM   │ │  Auth   │ │ Storage │ │  Tools  │ │  │
│  │  │ (new)   │ │(existing│ │(existing│ │(existing│ │  │
│  │  │         │ │  ABAC)  │ │ SQLite) │ │ routes) │ │  │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ │  │
│  └───────────────────────────────────────────────────┘  │
│                                                          │
├──────────────────────────────────────────────────────────┤
│                 Existing N3TX Stack                     │
│                                                          │
│  ProtoModel → Schema → Routes → Frontend (N3TX/Matrix)   │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

---

## 11. Competitive Position

### The Current Landscape (2025-2026)

| Framework | Approach | Strengths | Weaknesses |
|---|---|---|---|
| **LangChain/LangGraph** | Graph-based agent workflows | Mature ecosystem, many integrations | Heavy abstraction, complex debugging |
| **CrewAI** | Role-based multi-agent | Intuitive role metaphor, collaboration patterns | Limited customization, opinionated |
| **AutoGen** (Microsoft) | Conversational agents | Multi-agent chat, human-in-loop | Complex setup, Microsoft-centric |
| **Semantic Kernel** (Microsoft) | Plugin-based AI orchestration | Enterprise integration, .NET/Python | Heavy, enterprise-focused |
| **DSPy** (Stanford) | Programmatic prompt optimization | Novel approach, automatic prompt tuning | Academic, steep learning curve |
| **Instructor** | Structured LLM outputs | Pydantic integration, simple | Not an agent framework, just output parsing |
| **MCP** (Anthropic) | Tool protocol standard | Standardized tool interface | Protocol only, not a framework |

### What None of Them Offer

No existing framework provides the **"define a model, get an agent"**
experience. Every framework requires the developer to:

1. Define the agent's tools separately from its data model
2. Wire up storage manually
3. Configure permissions independently
4. Build API endpoints by hand
5. Create monitoring dashboards separately

N3TX's schema-driven approach would unify all of these:

```python
# One definition. Everything else is derived.
class ResearchAgent(ProtoModel, AgentMixin):
    __tablename__ = 'research_agents'
    __storable__ = True
    __agent__ = True
    __access__ = { 'invoke': AUTHENTICATED }

    topic: str = Field(...)
    report: str = Field(default="")

    @expose_tool(description="Search the web")
    def web_search(self, query: str) -> list[dict]: ...
```

From this single definition, you get:

- SQLite table for agent state
- CRUD API endpoints for managing agent instances
- JSON Schema with capability manifest
- LLM tool definitions (derived from @expose_tool)
- Permission enforcement (ABAC)
- Frontend rendering of agent status and results
- Persistent memory (via ListRef[AgentMemory])

### Viability Assessment

**Is "define a model, get an agent" viable?**

Yes, with caveats:

1. **For structured, tool-using agents** -- Highly viable. The schema-driven
   approach maps perfectly onto agents that have defined capabilities,
   typed inputs/outputs, and persistent state.

2. **For conversational agents** -- Partially viable. The model captures
   state and tools, but conversation flow requires additional abstractions
   (dialogue trees, intent classification) that are not schema-derived.

3. **For autonomous research/coding agents** -- Viable as a foundation.
   The planning loop is the custom part; the infrastructure (messaging,
   storage, permissions, tools) is provided by the framework.

4. **For multi-agent orchestration** -- Strongly viable. The Actor/Matrix
   pattern is inherently multi-agent. The supervision hierarchy, message
   routing, and permission scoping are all designed for multi-entity
   systems.

### Defensible Differentiation

The competitive moat is not any single feature but the **integration depth**:

- LangChain gives you tools and chains. You add everything else.
- CrewAI gives you roles and collaboration. You add storage and APIs.
- N3TX-Agent would give you **the entire stack** from one model definition.

This is the same value proposition that makes N3TX compelling as a web
framework: absorb the plumbing so developers focus on what makes their
agent unique.

---

## 12. Implementation Roadmap

### Phase 0: Foundation (2-3 weeks)

**Goal:** Prove the concept with a single agent type, no multi-agent.

1. **`AgentMixin`** -- Base mixin with `async run()`, tool dispatch, memory.
   Modeled on `StorableMixin` (injected, not inherited).
2. **`LLMClient`** -- Async client for Anthropic Claude (primary) and
   OpenAI (secondary). Streaming, retries, token counting.
3. **`@expose_tool`** -- Decorator that attaches tool metadata (like
   `@expose_route`). Tool schema generation method.
4. **Schema extension** -- `ProtoModel.schema()` includes `tools` section
   when `__agent__ = True`.
5. **One working agent** -- `ResearchAgent` that can search, read, and
   produce a report.

### Phase 1: Multi-Agent (3-4 weeks)

**Goal:** Multiple agents communicating via the message bus.

1. **Backend Matrix** -- Python equivalent of the JS Matrix. Message routing
   between agent instances.
2. **Agent registry** -- Discover agents by capability, not just address.
3. **Delegation protocol** -- Agent A sends task to Agent B, receives result.
4. **Coordination patterns** -- Sequential, parallel, voting, review chain.
5. **Budget/cost tracking** -- Per-agent and per-task cost limits.

### Phase 2: Production (4-6 weeks)

**Goal:** Production-ready agent infrastructure.

1. **Observability** -- Structured tracing, cost dashboards, decision logs.
2. **Memory management** -- Context window optimization, summarization,
   vector search.
3. **Sandbox execution** -- Isolated tool execution for untrusted operations.
4. **Frontend agent UI** -- `<ntx-agent>` component that renders agent status,
   conversation, and tool calls.
5. **MCP compatibility** -- Export agent tools as MCP servers.

### Phase 3: Ecosystem (Ongoing)

1. **Agent marketplace** -- Share agent definitions as N3TX models.
2. **Pre-built agents** -- Research, coding, data analysis, customer support.
3. **Integration adapters** -- Connect to external services (Slack, GitHub,
   databases).
4. **Prompt optimization** -- Auto-tune prompts based on agent performance.

---

## Appendix A: Side-by-Side Code Comparison

### N3TX Entity Today vs. N3TX Agent (Proposed)

```python
# ═══════════════════════════════════════════════
# TODAY: A N3TX Entity (Product)
# ═══════════════════════════════════════════════

class Product(ProtoModel):
    __tablename__ = 'products'
    __storable__ = True
    __ui__ = {
        'field_order': ['name', 'price', 'description'],
        'groups': {'main': ['name', 'description', 'price']},
    }
    __access__ = {
        'read': ANYONE,
        'create': AUTHENTICATED,
        'update': OWNER | ROLE('admin'),
    }

    name: str = Field(min_length=1, max_length=200)
    price: float = Field(gt=0)
    description: str = Field(default='')
    comments: ListRef[Comment] = Field(default=[])

    @expose_route('/comment', methods=['POST'])
    def comment(self, comment: Comment, user: User = None) -> str:
        comment.user_owner = user.id if user else 1
        comment.__owner__ = self
        comment.save()
        return comment.model_dump_json()


# ═══════════════════════════════════════════════
# PROPOSED: A N3TX Agent (ResearchAgent)
# ═══════════════════════════════════════════════

class ResearchAgent(ProtoModel, AgentMixin):
    __tablename__ = 'research_agents'
    __storable__ = True
    __agent__ = True
    __llm__ = {
        'provider': 'anthropic',
        'model': 'claude-sonnet-4-20250514',
        'temperature': 0.3,
    }
    __prompt__ = {
        'system': "You are a research analyst...",
    }
    __access__ = {
        'read': AUTHENTICATED,
        'invoke': AUTHENTICATED & BUDGET(remaining__gt=0),
    }

    name: str = Field(default="Research Agent")
    topic: str = Field(default="")
    report: str = Field(default="")
    budget_remaining: float = Field(default=1.0)
    memories: ListRef[AgentMemory] = Field(default=[])

    @expose_tool(description="Search the web")
    def web_search(self, query: str, max_results: int = 5) -> list[dict]:
        # ... implementation
        return results

    @expose_route('/research', methods=['POST'])
    async def research(self, topic: str, user: User = None) -> str:
        self.topic = topic
        result = await self.run(task=f"Research: {topic}")
        return result
```

The structural similarity is deliberate. The same patterns -- field
definitions, access rules, exposed methods, storage, schema generation --
apply to both entities and agents. The agent adds LLM configuration and
a `run()` loop; everything else is inherited from the framework.

---

## Appendix B: Schema Output Comparison

### Current Product Schema (Actual)

```json
{
    "$schema": "http://localhost:5000/Schema",
    "$id": "http://localhost:5000/Product",
    "__name__": "Product",
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "price": {"type": "number", "exclusiveMinimum": 0}
    },
    "methods": {
        "comment": {
            "route": "/comment",
            "methods": ["POST"],
            "parameters": {"comment": {"$ref": "#/$defs/Comment"}},
            "returns": {"type": "string"}
        }
    },
    "access": {
        "read": {"rule": "anyone"},
        "create": {"rule": "authenticated"}
    }
}
```

### Proposed Agent Schema (Future)

```json
{
    "$schema": "http://localhost:5000/Schema",
    "$id": "http://localhost:5000/ResearchAgent",
    "__name__": "ResearchAgent",
    "__agent__": true,
    "properties": {
        "name": {"type": "string", "default": "Research Agent"},
        "topic": {"type": "string"},
        "report": {"type": "string"},
        "budget_remaining": {"type": "number", "default": 1.0},
        "status": {"type": "string", "enum": ["idle", "working", "done", "error"]}
    },
    "tools": {
        "web_search": {
            "description": "Search the web for information on a topic",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer", "default": 5}
                },
                "required": ["query"]
            },
            "returns": {"type": "array", "items": {"type": "object"}},
            "cost_limit": 0.02
        }
    },
    "methods": {
        "research": {
            "route": "/research",
            "methods": ["POST"],
            "parameters": {"topic": {"type": "string"}},
            "returns": {"type": "string"}
        }
    },
    "access": {
        "read": {"rule": "authenticated"},
        "invoke": {"op": "and", "rules": [
            {"rule": "authenticated"},
            {"rule": "budget", "conditions": {"remaining__gt": 0}}
        ]}
    },
    "llm": {
        "provider": "anthropic",
        "model": "claude-sonnet-4-20250514",
        "temperature": 0.3
    }
}
```

The agent schema is a natural extension of the entity schema. It adds
`tools` (derived from `@expose_tool`), `llm` (from `__llm__`), and
`__agent__: true` as a type discriminator. The frontend can use
`__agent__` to render an agent-specific UI component instead of the
standard `ntx-item`.

---

## Appendix C: Message Flow Comparison

### Current: User Creates a Comment (Entity Flow)

```
Frontend                    Matrix                  Backend
   │                          │                        │
   │  TX{ATTACH, "Product"}   │                        │
   ├─────────────────────────>│                        │
   │                          │  GET /Product (schema) │
   │                          ├───────────────────────>│
   │                          │  ← JSON Schema         │
   │                          │<───────────────────────┤
   │  TX{SCHEMA, data}        │                        │
   │<─────────────────────────┤                        │
   │  prototype() → DC        │                        │
   │                          │                        │
   │  TX{READ}                │  GET /products         │
   ├─────────────────────────>├───────────────────────>│
   │                          │  ← [{...}, {...}]      │
   │  TX{UPDATE, data}        │<───────────────────────┤
   │<─────────────────────────┤                        │
   │                          │                        │
   │  comment("Great!")       │  POST /products/1/comment
   ├─────────────────────────>├───────────────────────>│
   │                          │  ← "ok"                │
   │  TX{_response_}          │<───────────────────────┤
   │<─────────────────────────┤                        │
   │  pull() → re-fetch       │                        │
```

### Proposed: Orchestrator Delegates Research Task (Agent Flow)

```
User/API               Orchestrator             ResearchAgent          LLM
   │                        │                        │                  │
   │  POST /orchestrator    │                        │                  │
   │  /assign               │                        │                  │
   ├───────────────────────>│                        │                  │
   │                        │  TX{RESEARCH,          │                  │
   │                        │    topic:"AI agents"}  │                  │
   │                        ├───────────────────────>│                  │
   │                        │                        │  think(messages) │
   │                        │                        ├─────────────────>│
   │                        │                        │  ← tool_use:    │
   │                        │                        │    web_search    │
   │                        │                        │<─────────────────┤
   │                        │                        │                  │
   │                        │                        │  [execute tool]  │
   │                        │                        │  web_search(     │
   │                        │                        │    "AI agents")  │
   │                        │                        │                  │
   │                        │                        │  think(messages  │
   │                        │                        │   + tool_result) │
   │                        │                        ├─────────────────>│
   │                        │                        │  ← text:        │
   │                        │                        │    "## Report.." │
   │                        │                        │<─────────────────┤
   │                        │                        │                  │
   │                        │  TX{COMPLETE,          │                  │
   │                        │    report:"## ..."}    │                  │
   │                        │<───────────────────────┤                  │
   │  ← {report: "## ..."}  │                        │                  │
   │<───────────────────────┤                        │                  │
```

The message shapes are identical. `TX{name, source, target, data, meta}`
carries agent tasks the same way it carries entity operations. The Matrix
routes between agents the same way it routes between N3TX DynamicClasses.

---

## Appendix D: Key File Reference

All analysis in this document is based on the following source files:

| File | Role in This Analysis |
|---|---|
| `/workspace/src/n3tx/static/core/Actor.js` | Base actor class -- agent messaging foundation |
| `/workspace/src/n3tx/static/core/Matrix.js` | Message bus -- agent communication routing |
| `/workspace/src/n3tx/static/core/N3TX.js` | Entity system and `prototype()` -- runtime class creation |
| `/workspace/src/n3tx/static/core/TX.js` | Transaction envelope -- agent message format |
| `/workspace/src/n3tx/static/core/Observable.js` | Observable mixin -- agent event subscriptions |
| `/workspace/src/n3tx/core/models/proto_model.py` | Schema generation -- capability manifest source |
| `/workspace/src/n3tx/core/models/storable_mixin.py` | Storage mixin -- agent state persistence |
| `/workspace/src/n3tx/core/api/routes_fastapi.py` | Route generation -- tool API endpoint creation |
| `/workspace/src/n3tx/core/authorize/rules.py` | ABAC rules -- agent permission scoping |
| `/workspace/src/n3tx/core/authorize/context.py` | Access context -- agent authorization context |
| `/workspace/src/n3tx/core/utils/decorators.py` | `@expose_route` -- tool definition pattern |
| `/workspace/src/n3tx/core/app.py` | App builder -- agent app bootstrapping |
| `/workspace/src/n3tx/example/models/product.py` | Example entity -- reference for agent model pattern |

---

## Conclusion

N3TX's architecture was not designed for AI agents, but it was designed
for exactly the problem agents present: taking a structured definition and
deriving an entire operational stack from it. The Actor system, message bus,
schema generation, typed methods, ABAC authorization, storage layer, and
runtime class creation are not analogies to agent concepts -- they ARE agent
concepts, applied to web entities.

The path from "schema-driven web framework" to "schema-driven agent
framework" is not a pivot. It is an extension. The same `ProtoModel` base
class, the same `@expose_route` pattern (as `@expose_tool`), the same
authorization engine, the same storage backend, the same message bus. The
LLM integration layer sits on top; it does not replace anything underneath.

The strategic question is not "can N3TX support agents" -- the code
analysis shows it can. The question is "should N3TX be the framework
that offers define-a-model-get-an-agent" -- and the answer depends on
whether the team wants to compete in the agent framework space or stay
focused on the web framework story. The architecture supports both paths
without conflict.
