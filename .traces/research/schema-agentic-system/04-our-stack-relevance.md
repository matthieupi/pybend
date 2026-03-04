# Schema-Driven Agentic Systems: Relevance to N3TX

**Research Document -- N3TX Stack Analysis**
Date: 2026-02-26 | Audience: Technical CEO + Engineering Team

---

## Executive Summary

N3TX is a schema-driven framework where **a single Python model definition generates the entire application stack**: database, API, validation, permissions, and frontend rendering. This document performs a deep codebase analysis to answer a specific question: **how do N3TX's existing architectural primitives map to the requirements of schema-driven agentic AI systems, and what would it take to bridge the gap?**

> **Key Insight:** The 2024-2026 AI ecosystem has converged on **JSON Schema as the universal contract** for agent-to-tool, agent-to-agent, and agent-to-environment communication. OpenAI function calling, Anthropic's MCP (97M+ monthly SDK downloads), Google's A2A protocol (50+ technology partners), and Microsoft's Agent Framework all use JSON Schema as their tool definition format. N3TX already produces rich JSON Schema as its primary output -- not as documentation, but as the operational contract that drives the entire system. This is not an analogy. It is a structural alignment.

The analysis identifies **9 direct architectural parallels** between N3TX's existing components and agent system primitives. The estimated coverage of agent infrastructure needs is **60-70%**, with the missing pieces (LLM integration, planning loops, memory management) being **additive** rather than architectural rewrites.

---

## Table of Contents

1. [The Industry Convergence on Schema](#1-industry-convergence)
2. [Architectural Mapping: N3TX to Agent Primitives](#2-architectural-mapping)
3. [Deep Dive: ProtoModel as Agent Capability Manifest](#3-protomodel-as-manifest)
4. [Deep Dive: @expose_route to @expose_tool](#4-expose-route-to-expose-tool)
5. [Deep Dive: Actor/Matrix as Agent Communication Backbone](#5-actor-matrix-backbone)
6. [Deep Dive: DynamicClass as Runtime Agent Instantiation](#6-dynamicclass-agents)
7. [Deep Dive: ABAC as Agent Permission Scoping](#7-abac-permissions)
8. [Deep Dive: StorableMixin as Agent State Management](#8-storable-state)
9. [Gap Analysis: What Exists vs. What Is Missing](#9-gap-analysis)
10. [Competitive Positioning: Schema-Driven vs. Framework-First](#10-competitive-positioning)
11. [The Proposed AgentModel Pattern](#11-proposed-agentmodel)
12. [Sources](#12-sources)

---

## 1. Industry Convergence

**The "so what?" for the CEO:** Every major AI company -- OpenAI, Anthropic, Google, Microsoft -- independently arrived at the same conclusion: JSON Schema is the right way for AI agents to describe what they can do. If your framework already speaks fluent JSON Schema, you have a head start that others are spending millions to build toward.

**The technical detail for engineers:** Between 2023 and 2026, the AI ecosystem converged on JSON Schema as the universal interface layer for agent tool definitions. Here is the timeline:

| Provider | Protocol | Schema Format | Year | Current Scale |
|---|---|---|---|---|
| **OpenAI** | Function Calling | JSON Schema (`parameters`) | 2023 | Built into GPT-4o, o1, Agents SDK |
| **Anthropic** | Tool Use / [MCP](https://modelcontextprotocol.io/specification/2025-11-25) | JSON Schema (`inputSchema`) | 2024 | [97M+ monthly SDK downloads](https://guptadeepak.com/the-complete-guide-to-model-context-protocol-mcp-enterprise-adoption-market-trends-and-implementation-strategies/) |
| **Google** | [A2A Protocol](https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/) | JSON Agent Cards | 2025 | 50+ enterprise partners, Linux Foundation |
| **Microsoft** | [Agent Framework](https://devblogs.microsoft.com/foundry/introducing-microsoft-agent-framework-the-open-source-engine-for-agentic-ai-apps/) | OpenAPI JSON Schema | 2025 | Semantic Kernel + AutoGen merged |
| **OpenAI** | [Agents SDK](https://openai.github.io/openai-agents-python/) | Pydantic -> JSON Schema | 2025 | `@function_tool` decorator |
| **Community** | [Open Agent Spec](https://www.emergentmind.com/topics/open-agent-specification-agent-spec) | JSON/YAML + JSON Schema | 2025 | Emerging open standard |

The convergence is not coordinated. It emerged because JSON Schema uniquely satisfies what [Peter Hrynkow calls](https://peterhrynkow.com/ai/architecture/2025/02/01/schema-driven-platforms.html) "constraints as leverage" -- the schema encodes not just structure but **intent**, **validation**, and **documentation** in a single artifact.

> **Key Insight:** Anthropic donated MCP to the Linux Foundation in December 2025 (as the [Agentic AI Foundation](https://robomotion.io/blog/mcp-explained-why-model-context-protocol-matters-in-2026/)), co-founded with Block and OpenAI. This signals that schema-driven tool definition is becoming infrastructure, not a competitive differentiator. The differentiator is how efficiently you can **produce** those schemas.

The standard agent tool definition, across all providers, boils down to four fields:

```
name         : string       -- what to call it
description  : string       -- what it does (read by the LLM)
inputSchema  : JSON Schema  -- what it accepts
outputSchema : JSON Schema  -- what it returns (optional)
```

**Any system that can produce `{name, description, inputSchema, outputSchema}` can participate in the agent ecosystem across all providers.** N3TX already produces all four.

---

## 2. Architectural Mapping

This table maps every relevant N3TX primitive to its agent-framework equivalent, with specific file paths and line numbers from the codebase.

| N3TX Primitive | Source File | Agent Concept | Mapping Quality |
|---|---|---|---|
| `ProtoModel.schema()` | `core/models/proto_model.py:199` | Agent capability manifest | **Direct** -- produces typed properties, methods, access rules |
| `@expose_route` decorator | `core/utils/decorators.py:3` | Tool definition (`@function_tool`) | **Direct** -- attaches metadata to callable methods |
| `__n3tx_methods_json_signature__` | `core/models/proto_model.py:140` | Tool schema generation | **Direct** -- extracts typed parameter schemas |
| `AccessRule` / ABAC | `core/authorize/rules.py:13` | Agent permission scoping | **Direct** -- composable rules with `\|`, `&`, `~` |
| `AccessContext` | `core/authorize/context.py:8` | Tool invocation context | **Direct** -- immutable snapshot of caller identity |
| `Actor` base class | `static/core/Actor.js:11` | Agent base class | **Strong** -- addressable identity, inbox, children hierarchy |
| `Matrix` message bus | `static/core/Matrix.js:10` | Agent communication bus | **Strong** -- routes messages by address, supports remote |
| `TX` transaction envelope | `static/core/TX.js:7` | Agent message format | **Direct** -- name, source, target, data, meta, timestamp |
| `DynamicClass` / `prototype()` | `static/core/N3TX.js:663` | Runtime agent instantiation | **Strong** -- creates typed classes from schema |
| `N3TX.SCHEMA()` bootstrap | `static/core/N3TX.js:390` | Agent capability discovery | **Strong** -- fetch schema, create class, replay queue |
| `StorableMixin` | `core/models/storable_mixin.py:16` | Agent state persistence | **Direct** -- CRUD with injected storage backend |
| `Observable` mixin | `static/core/Observable.js:20` | Agent event subscriptions | **Direct** -- signal/observe/notify pattern |
| `Router` state actor | `static/core/Router.js:23` | Agent navigation/workflow state | **Partial** -- manages state transitions, history stack |
| `NetworkAdapter` | `static/core/transport/NetworkAdapter.js:7` | Remote agent transport | **Partial** -- HTTP + WebSocket, needs agent protocols |
| `create_app()` / `N3TXApp` | `core/app.py:180` | Agent app bootstrapping | **Direct** -- one-liner setup from model definitions |

**Visual summary: what maps and what doesn't**

```
N3TX Today                              Agent Framework Needs
===========                              ====================

[ProtoModel] ----schema()--->  [JSON Schema]  ===  [Capability Manifest]   HAVE IT
[   fields  ]                  [properties ]  ===  [Agent state schema]    HAVE IT
[  methods  ] --signatures-->  [  methods  ]  ===  [Tool definitions  ]    HAVE IT
[ __access__] --to_dict()--->  [  access   ]  ===  [Agent permissions ]    HAVE IT
[   Actor   ] ----inbox()--->  [  handler  ]  ===  [Agent message recv]    HAVE IT
[  Matrix   ] --dispatch()--> [  routing   ]  ===  [Agent message bus ]    HAVE IT
[    TX     ]                  [ envelope  ]  ===  [Agent message fmt ]    HAVE IT
[  Storage  ] ----CRUD()--->   [ persist   ]  ===  [Agent state mgmt ]    HAVE IT
[DynamicCls ] -prototype()->  [typed class ]  ===  [Runtime agent     ]    HAVE IT

                         ?????                ===  [LLM Integration   ]    MISSING
                         ?????                ===  [Prompt Management ]    MISSING
                         ?????                ===  [Planning Loop     ]    MISSING
                         ?????                ===  [Memory/Context    ]    MISSING
                         ?????                ===  [Observability     ]    MISSING
```

---

## 3. ProtoModel as Agent Capability Manifest

**The "so what?":** N3TX's `ProtoModel.schema()` already generates documents that are structurally identical to what MCP, A2A, and OpenAI expect as agent/tool descriptions. The conversion is mechanical, not architectural.

### What schema() produces today

From `/workspace/src/n3tx/core/models/proto_model.py`, the `schema()` classmethod (line 199) produces a JSON Schema document by:

1. Calling Pydantic's `model_json_schema()` for property definitions (line 209)
2. Adding method signatures via `__n3tx_methods_json_signature__()` (line 220)
3. Collecting `$defs` for referenced models (lines 222-241)
4. Injecting ABAC access rules via `access_schema()` (line 256)
5. Applying UI hints from `__ui__` (lines 283-308)
6. Setting `$schema` and `$id` metadata (lines 310-311)

The resulting document carries **everything an agent manifest needs**:

```python
# What ProtoModel.schema() returns (actual structure from proto_model.py)
{
    "$schema": "http://localhost:5000/Schema",   # Meta-schema URL
    "$id": "http://localhost:5000/Product",       # This agent's identity
    "__name__": "Product",                        # Agent type name
    "__tablename__": "products",                  # API collection path

    "properties": {                               # Agent STATE schema
        "name":  {"type": "string", "minLength": 1},
        "price": {"type": "number", "exclusiveMinimum": 0},
    },

    "methods": {                                  # Agent TOOLS
        "comment": {
            "route": "/comment",
            "methods": ["POST"],
            "scope": "instancemethod",
            "parameters": {"comment": {"$ref": "#/$defs/Comment"}},
            "returns": {"type": "string"},
            "access": {"rule": "authenticated"}
        }
    },

    "access": {                                   # Agent PERMISSIONS
        "read":   {"rule": "anyone"},
        "create": {"rule": "authenticated"},
        "update": {"op": "or", "rules": [{"rule": "owner"}, {"rule": "role", "roles": ["admin"]}]}
    },

    "$defs": { ... }                              # Dependency schemas
}
```

### Side-by-side: N3TX schema vs. agent protocol formats

| N3TX Schema Field | OpenAI Function Calling | Anthropic MCP | Google A2A Agent Card |
|---|---|---|---|
| `__name__` | `function.name` | `tool.name` | `agentCard.name` |
| Method docstring | `function.description` | `tool.description` | `agentCard.description` |
| `methods[x].parameters` | `function.parameters` | `tool.inputSchema` | N/A (task-based) |
| `methods[x].returns` | N/A (inferred) | `tool.outputSchema` | N/A |
| `methods[x].access` | N/A | `tool.annotations` | `agentCard.securitySchemes` |
| `$id` | N/A | N/A | `agentCard.url` |
| `properties` | N/A | MCP Resources | Agent state (internal) |
| `access` | N/A | Server auth | `agentCard.authentication` |

### The conversion is trivially mechanical

The `__n3tx_methods_json_signature__()` method (line 140 of `proto_model.py`) already extracts typed parameter schemas via `pydantic_schema_for_type()`. Converting to OpenAI format requires:

```python
# Pseudocode: N3TX method signature -> OpenAI function calling format
def to_openai_tools(schema: dict) -> list[dict]:
    tools = []
    for name, method in schema.get("methods", {}).items():
        tools.append({
            "type": "function",
            "function": {
                "name": name,
                "description": method.get("description", ""),
                "parameters": {
                    "type": "object",
                    "properties": method["parameters"],
                    "required": [k for k, v in method["parameters"].items()
                                 if not v.get("default")],
                }
            }
        })
    return tools
```

This is a **20-line adapter function**, not an architectural change.

> **Key Insight:** N3TX's schema carries MORE information than any single agent protocol requires. The schema includes access rules, UI hints, field validation, and relationship references -- metadata that agent protocols are still evolving to support. The schema is a **superset** of what the agent ecosystem needs, not a subset.

---

## 4. @expose_route to @expose_tool

**The "so what?":** The pattern N3TX uses to expose Python methods as API endpoints is structurally identical to how every major agent framework exposes methods as LLM tools. The decorator, the metadata attachment, the schema extraction -- it is the same pattern.

### The decorator today

From `/workspace/src/n3tx/core/utils/decorators.py`:

```python
def expose_route(route, methods=["POST"], access=None):
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
```

### How major agent frameworks define tools

| Framework | Decorator/Pattern | Schema Source | Example |
|---|---|---|---|
| **OpenAI Agents SDK** | [`@function_tool`](https://openai.github.io/openai-agents-python/tools/) | Type hints + docstring | `@function_tool async def search(query: str) -> str:` |
| **LangChain** | [`@tool`](https://docs.langchain.com/oss/python/langchain/tools) | Type hints + `args_schema` | `@tool def search(query: str) -> str:` |
| **Microsoft Agent Framework** | [`@ai_function`](https://devblogs.microsoft.com/foundry/introducing-microsoft-agent-framework-the-open-source-engine-for-agentic-ai-apps/) | Reflection-based | `@ai_function def search(query: str) -> str:` |
| **CrewAI** | `BaseTool` subclass | Pydantic model | `class SearchTool(BaseTool): args_schema = SearchSchema` |
| **Pydantic AI** | [`@agent.tool`](https://ai.pydantic.dev/tools/) | Pydantic types | `@agent.tool async def search(ctx, query: str) -> str:` |
| **N3TX (existing)** | `@expose_route` | Type hints + Pydantic | `@expose_route('/search', methods=['POST'])` |

The structural similarity is not coincidence -- every framework follows the same pattern:

```
[Decorator] attaches metadata to function
    -> [Framework] inspects signature + type hints
    -> [Framework] generates JSON Schema for parameters
    -> [Schema] is served to consumer (LLM, frontend, other agent)
```

### What an @expose_tool decorator would look like

```python
# Proposed: @expose_tool (same pattern as @expose_route, different metadata)
def expose_tool(description=None, access=None, cost_limit=None, timeout=None):
    def decorator(func):
        func.__tool__ = {
            'description': description or func.__doc__,
            'access': access,
            'cost_limit': cost_limit,
            'timeout': timeout,
        }
        # Also mark as route so it gets both HTTP and tool exposure
        func.__endpoint__ = {
            'route': f'/{func.__name__}',
            'methods': ['POST'],
            'access': access,
        }
        return func
    return decorator
```

The schema extraction in `__n3tx_methods_json_signature__()` (line 140 of `proto_model.py`) would need a parallel method:

```python
@classmethod
def __agent_tools_signature__(cls) -> list[dict]:
    """Generate tool definitions in OpenAI/MCP-compatible format."""
    tools = []
    for method_name in dir(cls):
        method = getattr(cls, method_name)
        if not (callable(method) and hasattr(method, '__tool__')):
            continue
        sig = inspect.signature(method)
        type_hints = get_type_hints(method)
        tool_info = method.__tool__

        parameters = {}
        required = []
        for name, param in sig.parameters.items():
            if name in ('cls', 'self', 'user'):
                continue
            ptype = type_hints.get(name, param.annotation)
            parameters[name] = pydantic_schema_for_type(ptype)
            if param.default is inspect.Parameter.empty:
                required.append(name)

        tools.append({
            "name": method_name,
            "description": tool_info.get('description', ''),
            "inputSchema": {
                "type": "object",
                "properties": parameters,
                "required": required,
            },
        })
    return tools
```

This reuses the existing `pydantic_schema_for_type()` from `/workspace/src/n3tx/core/utils/introspection.py`. The new code is ~30 lines.

---

## 5. Actor/Matrix as Agent Communication Backbone

**The "so what?":** N3TX already has an actor-based message bus that routes typed messages between addressed entities. This is exactly what agent frameworks call an "agent communication backbone." The pattern is not similar to agent communication -- it IS agent communication, applied to web entities.

### The Actor pattern in agent literature

According to [Pradeep Loganathan's analysis](https://pradeepl.com/blog/agentic-ai/akka-actor-model-agentic-ai/), "An agent IS an actor. It encapsulates its own private state (memory, goals) and behavior within a protective boundary." Akka itself [now offers an Agent component](https://akka.io/blog/introducing-akkas-new-agent-component) built directly on their actor runtime, with the tagline: "agentic services execute on an award-winning actor-based runtime."

The [synergy between actors and agents](https://www.robotmunki.com/blog/actor-pattern-and-ai.html) is well-documented: isolated state, message-driven execution, supervision hierarchies, and location-transparent routing are fundamental to both paradigms.

### N3TX's Actor today

From `/workspace/src/n3tx/static/core/Actor.js`:

```javascript
export default class Actor {
    #addr;       // Unique address (agent identity)
    #parent;     // Parent actor (supervisor)
    #children;   // Child actors (managed agents)

    inbox(event) {                     // Message handler dispatch
        return Actor._inbox.call(this, event);
    }

    spawn(addr, ActorClass, ...args) { // Create child agent
        const child = new ActorClass(addr, ...args);
        this.#children.set(addr, child);
        return child;
    }
}
```

### Matrix routing maps to agent bus routing

From `/workspace/src/n3tx/static/core/Matrix.js`:

```javascript
export class Matrix extends Actor {
    inbox(event) {
        let tx = event instanceof TX ? event : new TX(event);
        let targetAddr = tx.target.split('/')[0];

        if (this.children.has(targetAddr)) {
            // LOCAL: Forward to registered agent
            tx = this.children.get(targetAddr).inbox(tx.repr());
        } else {
            // REMOTE: Forward via network transport
            tx = this.remote.send(tx);
        }
        return tx;
    }
}
```

This three-step routing (local lookup -> child delivery -> remote fallback) is **identical** to how agent communication buses work:

```
Matrix Routing                        Agent Bus Routing
------------------------------------------------------------
matrix.children.has(target)    ->     bus.has_agent(agent_id)
matrix.children.get(target)    ->     bus.get_agent(agent_id)
  .inbox(tx)                            .receive(message)
matrix.remote.send(tx)         ->     bus.forward_to_remote(message)
```

### TX envelope already carries everything an agent message needs

From `/workspace/src/n3tx/static/core/TX.js`:

```javascript
class TX {
    constructor(event) {
        this.name = name;       // -> message type: "RESEARCH", "ANALYZE"
        this.source = source;   // -> sender agent ID
        this.target = target;   // -> recipient agent ID or URL
        this.data = data;       // -> task payload
        this.meta = meta;       // -> routing metadata (priority, trace_id)
        this.tst = timestamp;   // -> timing for observability
    }
}
```

Compare to Google's [A2A protocol message format](https://a2a-protocol.org/latest/specification/): JSON-RPC 2.0 over HTTP with method name, params, and metadata. The TX envelope is structurally equivalent.

### What the agent bus needs beyond Matrix

| Matrix Has | Agent Bus Needs | Gap Size | Notes |
|---|---|---|---|
| Synchronous delivery | Async with acknowledgment | **Medium** | Need queue + callback pattern |
| Local + HTTP routing | Multi-transport | **Small** | NetworkAdapter already supports WS |
| Address-based routing | Capability-based discovery | **Medium** | Need skill registry |
| No message persistence | Durable message replay | **Medium** | Add event store (StorableMixin pattern) |
| No observability | Tracing + cost tracking | **Medium** | Extend TX.meta |
| Single-process | Distributed bus | **Large** | Architectural extension |

---

## 6. DynamicClass as Runtime Agent Instantiation

**The "so what?":** N3TX's frontend already creates fully functional typed classes from JSON Schema at runtime. The same mechanism -- reading a schema, creating a class with typed properties and callable methods -- is exactly what's needed to instantiate agents from capability manifests.

### How prototype() works today

From `/workspace/src/n3tx/static/core/N3TX.js` (line 663):

```javascript
function prototype(addr, schema, href) {
    const fields = Object.keys(schema.properties || {});
    const methods = Object.keys(schema.methods || {});

    // 1. Create N3TX subclass with schema-driven properties
    const DynamicClass = class extends N3TX {
        static instances = new Map();
        static _schema = schema;
        constructor(data) {
            super(className, data.id);
            this.value = data;
        }
    };

    // 2. Add typed getters/setters from schema properties
    for (const field of fields) {
        Object.defineProperty(DynamicClass.prototype, field, {
            get() { return this.value?.[field]; },
            set(value) {
                if (!isTypeCompatible(value, definition.type))
                    throw new TypeError(`Invalid type for '${field}'`);
                this.value[field] = value;
                this.notify(field, value, oldValue);
            },
        });
    }

    // 3. Add callable methods from schema
    for (const method of methods) {
        DynamicClass.prototype[method] = function(...args) {
            this.call(method, args, {});  // Routes via Matrix -> Network
        };
    }

    // 4. Apply Actor + Observable mixins
    Actor.subclass(DynamicClass, Observable);
    return DynamicClass;
}
```

### The schema-in-agent-out pattern

The `N3TX.SCHEMA()` handler (line 390) orchestrates the full bootstrap:

```
1. Receive schema from backend       GET /Product -> JSON Schema
2. Register nested $defs schemas      for each $def, create DynamicClass
3. Create main DynamicClass           prototype(addr, schema, href)
4. Replay queued messages             pending ATTACHes get delivered
5. Trigger initial data fetch         DynamicClass.call('READ', {})
```

Replace "entity" with "agent" and the flow is:

```
1. Receive manifest from registry    GET /ResearchAgent -> Capability Manifest
2. Register dependency agents         for each $def, create AgentClass
3. Create main AgentClass             agentPrototype(name, manifest)
4. Replay queued tasks                pending task assignments get delivered
5. Trigger initial state load         AgentClass.loadState()
```

### Backend equivalent (proposed)

```python
# Backend DynamicAgent creation from capability manifest
def create_agent_class(name: str, manifest: dict) -> Type[ProtoModel]:
    """Create an Agent class from a capability manifest at runtime."""

    # Build state fields from manifest properties
    annotations = {}
    defaults = {}
    for field_name, field_def in manifest.get('properties', {}).items():
        annotations[field_name] = _resolve_type(field_def)
        if 'default' in field_def:
            defaults[field_name] = Field(default=field_def['default'])

    # Build access rules from manifest
    access = _deserialize_access(manifest.get('access', {}))

    # Create the class dynamically (same pattern as generate_join_model)
    AgentClass = type(name, (ProtoModel,), {
        '__tablename__': manifest.get('__tablename__', name.lower() + 's'),
        '__storable__': True,
        '__access__': access,
        '__annotations__': annotations,
        **defaults,
    })
    return AgentClass
```

Note: this follows the same pattern as `generate_join_model()` in `proto_model.py` (line 383), which already creates model classes dynamically using `type()`.

---

## 7. ABAC as Agent Permission Scoping

**The "so what?":** [OWASP's 2026 AI Agent Security Top 10](https://medium.com/@oracle_43885/owasps-ai-agent-security-top-10-agent-security-risks-2026-fc5c435e86eb) identifies "Excessive Permissions" and "Unauthorized Tool Invocation" as top agent security risks. N3TX's ABAC system -- composable, serializable, SQL-pushdown-capable -- is more sophisticated than what most agent frameworks offer. [CrewAI's enterprise RBAC](https://docs.crewai.com/en/enterprise/features/rbac) is role-based only. N3TX's is **attribute-based**, supporting arbitrary conditions via `Where()`.

### The authorize package: zero N3TX imports

From `/workspace/src/n3tx/core/authorize/rules.py`:

```python
class AccessRule(ABC):
    def evaluate(self, ctx: AccessContext) -> bool: ...   # Runtime check
    def sql_filter(self, ctx: AccessContext) -> ...: ...  # SQL pushdown
    def to_dict(self) -> Dict[str, Any]: ...              # Schema serialization

    def __or__(self, other):  return OrRule(self, other)   # Composable
    def __and__(self, other): return AndRule(self, other)
    def __invert__(self):     return NotRule(self)

# Built-in rules
ANYONE        = _Anyone()           # Always grants
AUTHENTICATED = _Authenticated()    # Requires auth
OWNER         = _Owner()            # Matches resource owner
ROLE('admin') = _Role('admin')      # Matches user role
Where(status='published')           # Attribute conditions
```

### Mapping to agent permission scenarios

| Agent Permission Need | N3TX ABAC Expression | Already Works? |
|---|---|---|
| Any authenticated user can invoke | `AUTHENTICATED` | Yes |
| Only admins can create agents | `ROLE('admin')` | Yes |
| Agent owner can modify their agent | `OWNER` | Yes |
| Only orchestrators can delegate | `ROLE('orchestrator')` | Yes |
| Budget must be positive | `Where(budget__gt=0)` | Yes |
| Tool access requires specific role | `AUTHENTICATED & ROLE('analyst')` | Yes |
| Agent count limited per user | Needs new `CountRule` | New leaf rule |
| Delegation depth limited | Needs new `DepthRule` | New leaf rule |

The key insight: adding agent-specific rules requires **zero changes to the authorization engine**. New `AccessRule` subclasses plug in naturally:

```python
class BUDGET(AccessRule):
    """Grants access only if agent's remaining budget meets conditions."""
    def __init__(self, **conditions):
        self.conditions = conditions

    def evaluate(self, ctx: AccessContext) -> bool:
        if ctx.resource is None: return True
        for field, op, value in self._parse():
            actual = getattr(ctx.resource, field, None)
            if op == '>' and not (actual is not None and actual > value):
                return False
        return True

    def to_dict(self):
        return {"rule": "budget", "conditions": self.conditions}
```

This follows the exact pattern of the existing `Where` rule (line 211 of `rules.py`).

### Schema serialization is already solved

From `/workspace/src/n3tx/core/authorize/schema.py`:

```python
def access_schema(model_class):
    access = getattr(model_class, '__access__', None)
    if access is None:
        return {"*": AUTHENTICATED.to_dict()}
    result = {}
    for action, rule in access.items():
        if isinstance(rule, AccessRule):
            result[action] = rule.to_dict()
    return result
```

Every rule serializes to JSON via `to_dict()`. The frontend reads these rules from the schema and enforces them client-side (via `Permissions.js`). An agent runtime would read the same rules and enforce them before tool invocation.

---

## 8. StorableMixin as Agent State Management

**The "so what?":** Agents need persistent state -- conversation history, task progress, accumulated knowledge. N3TX's `StorableMixin` provides exactly this: CRUD operations with an injected storage backend that requires no configuration.

### What StorableMixin provides today

From `/workspace/src/n3tx/core/models/storable_mixin.py`:

```python
class StorableMixin:
    __pk__: ClassVar[str] = 'id'
    __tablename__: ClassVar[str]
    storage: ClassVar[StorageInterface] = None  # Injected

    def save(self):           # Create or update
    @classmethod
    def create(cls, data):    # Insert new record
    @classmethod
    def list(cls, ...):       # Query with SQL filter, pagination
    @classmethod
    def get(cls, id):         # Fetch by ID
    @classmethod
    def update(cls, id, data):# Update record
    @classmethod
    def delete(cls, id):      # Delete record
```

### Agent state as a model

Agent state maps directly to StorableMixin:

| Agent State Need | StorableMixin Method | Notes |
|---|---|---|
| Save agent configuration | `agent.save()` | Creates/updates |
| Load agent state | `Agent.get(agent_id)` | Fetch by ID |
| List available agents | `Agent.list(sql_filter=...)` | With ABAC pushdown |
| Delete agent | `Agent.delete(agent_id)` | Cleanup |
| Conversation history | `AgentMemory` model with `ListRef` | Same FK pattern as comments |
| Task results | Field on agent model | `report: str = Field(default='')` |

The existing `ListRef` pattern for parent-child relationships (Products -> Comments) maps directly to agent -> memories:

```python
# Existing pattern (Product -> Comment)
class Product(ProtoModel):
    comments: ListRef[Comment] = Field(default=[])

# Agent equivalent (Agent -> AgentMemory)
class ResearchAgent(ProtoModel, AgentMixin):
    memories: ListRef[AgentMemory] = Field(default=[])
```

---

## 9. Gap Analysis

### What N3TX has vs. what agents need

| Requirement | Status | Coverage | Effort to Add |
|---|---|---|---|
| **Agent identity & addressing** | **Exists** (`Actor.addr`, `$id`) | 95% | -- |
| **Agent messaging** | **Exists** (`Actor/Matrix/TX`) | 80% | Small (add async) |
| **Agent state schema** | **Exists** (`ProtoModel`, JSON Schema) | 90% | -- |
| **Tool definitions** | **Exists** (`@expose_route`, method signatures) | 75% | Small (adapter) |
| **Tool parameter validation** | **Exists** (Pydantic + route parsing) | 85% | -- |
| **Permission scoping** | **Exists** (`authorize` package, ABAC) | 90% | Small (new rules) |
| **State persistence** | **Exists** (`StorableMixin`, SQLite) | 85% | -- |
| **Runtime class creation** | **Exists** (`prototype()` frontend) | 70% | Medium (backend port) |
| **Event subscriptions** | **Exists** (`Observable` mixin) | 80% | -- |
| **API generation** | **Exists** (`register_routes()`) | 90% | -- |
| **App bootstrapping** | **Exists** (`create_app()`, builder) | 85% | -- |
| **Schema discovery** | **Exists** (`GET /{ClassName}`) | 90% | -- |
| **MCP compatibility** | **Missing** | 0% | Medium (protocol adapter) |
| **A2A Agent Card** | **Missing** | 0% | Small (schema transform) |
| **LLM integration** | **Missing** | 0% | Medium (client + streaming) |
| **Prompt management** | **Missing** | 0% | Small (config, like `__ui__`) |
| **Conversation memory** | **Missing** | 0% | Medium (context window mgmt) |
| **Planning / reasoning loop** | **Missing** | 0% | Large (core innovation) |
| **Tool execution sandbox** | **Missing** | 0% | Medium (subprocess isolation) |
| **Cost tracking / budgets** | **Missing** | 0% | Small (new model + middleware) |
| **Agent observability** | **Missing** | 0% | Medium (structured tracing) |

> **Key Insight:** The existing infrastructure covers approximately **65% of agent framework requirements**. The missing 35% is the AI-specific layer: LLM clients, prompt engineering, memory management, and planning loops. Critically, the missing pieces are **additive** -- they layer on top of the existing architecture without replacing anything.

### Effort estimation for the bridge

| Gap | Approach | Estimated Effort | Dependencies |
|---|---|---|---|
| LLM integration | `LLMMixin` with provider clients | 2-3 weeks | httpx, provider SDKs |
| @expose_tool decorator | Copy pattern from @expose_route | 2-3 days | None |
| Tool schema generation | Extend `__n3tx_methods_json_signature__` | 2-3 days | None |
| MCP server adapter | Generate MCP `tools/list` from schema | 1 week | MCP SDK |
| A2A Agent Card | Transform schema to Agent Card JSON | 2-3 days | None |
| Prompt management | `__prompt__` class var (like `__ui__`) | 2-3 days | None |
| Agent memory model | New `AgentMemory` ProtoModel | 1 week | StorableMixin (exists) |
| Planning loop | `AgentMixin.run()` with tool dispatch | 3-4 weeks | LLM integration |
| Cost tracking | `AgentCost` model + middleware | 1 week | StorableMixin (exists) |
| Observability | Extend TX with trace fields | 1-2 weeks | None |
| Backend Actor/Matrix | Python port of JS Actor system | 2-3 weeks | asyncio |

**Total estimated effort: 10-14 weeks** for a working single-agent system with MCP compatibility. Multi-agent coordination adds 4-6 weeks.

---

## 10. Competitive Positioning

**The "so what?":** Every existing agent framework requires developers to wire up storage, APIs, permissions, and UI separately from agent definitions. A schema-driven approach would be the first to offer "define a model, get an agent" -- the same value proposition that makes N3TX compelling as a web framework.

### Framework comparison

| Framework | Approach | Tool Definition | Permissions | State | API | UI |
|---|---|---|---|---|---|---|
| [LangChain](https://langchain-tutorials.github.io/langchain-tools-agents-2026/) | Graph-based | `@tool` decorator | None built-in | Manual | Manual | None |
| [CrewAI](https://www.crewai.com/open-source) | Role-based | `BaseTool` class | [Enterprise RBAC](https://docs.crewai.com/en/enterprise/features/rbac) | Manual | Manual | Dashboard |
| [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/) | Multi-agent | `@function_tool` | None built-in | Manual | Manual | None |
| [Microsoft Agent Framework](https://devblogs.microsoft.com/foundry/introducing-microsoft-agent-framework-the-open-source-engine-for-agentic-ai-apps/) | Plugin-based | `@ai_function` | Via Entra ID | Manual | OpenAPI | None |
| [Pydantic AI](https://ai.pydantic.dev/) | Dependency injection | `@agent.tool` | None built-in | Manual | Manual | None |
| **N3TX (proposed)** | **Schema-driven** | `@expose_tool` | **ABAC built-in** | **Auto** | **Auto** | **Auto** |

### What "define a model, get an agent" means in practice

With existing frameworks (e.g., LangChain):
```python
# LangChain: you write ALL of this
from langchain.tools import tool
from langchain.agents import AgentExecutor
from langchain.memory import ConversationBufferMemory
from sqlalchemy import create_engine, Column, String, Float
import fastapi

# 1. Define the tool (separate from everything else)
@tool
def web_search(query: str) -> str:
    """Search the web.""" ...

# 2. Define state storage (separate ORM model)
class AgentState(Base):
    __tablename__ = 'agent_states' ...

# 3. Define API endpoints (separate FastAPI routes)
app = fastapi.FastAPI()
@app.post("/agents/{id}/research")
async def research(id: int, topic: str): ...

# 4. Configure permissions (separate middleware)
# 5. Build the agent executor (separate wiring)
# 6. Set up memory (separate configuration)
# 7. Create monitoring (separate system)
```

With proposed N3TX approach:
```python
# N3TX: you write THIS and everything else is derived
class ResearchAgent(ProtoModel, AgentMixin):
    __tablename__ = 'research_agents'
    __storable__ = True
    __agent__ = True
    __llm__ = {'provider': 'anthropic', 'model': 'claude-sonnet-4-20250514'}
    __prompt__ = {'system': "You are a research analyst..."}
    __access__ = {'invoke': AUTHENTICATED & Where(budget__gt=0)}

    topic: str = Field(default="")
    report: str = Field(default="")
    budget: float = Field(default=1.0)

    @expose_tool(description="Search the web")
    def web_search(self, query: str) -> list[dict]: ...

    @expose_route('/research', methods=['POST'])
    async def research(self, topic: str, user: User = None) -> str:
        return await self.run(task=f"Research: {topic}")
```

From this single definition, the framework derives:
- SQLite table with auto-migration
- CRUD API endpoints (`GET/POST/PUT/DELETE /research_agents/...`)
- JSON Schema with capability manifest
- LLM tool definitions (from `@expose_tool`)
- MCP server endpoint (from schema)
- ABAC permission enforcement
- Frontend rendering via N3TX/ntx-item
- Agent memory via `ListRef[AgentMemory]`

### The unique advantage

As [Godspeed Systems articulates](https://godspeed.systems/blog/schema-driven-development-and-single-source-of-truth): "Instead of manually coding each component, the schema drives the generation of APIs, validations, documentation, and even test cases." N3TX already does this for web applications. Extending it to agents leverages the same architecture for a new domain.

The defensible moat is not any single feature but **integration depth**. LangChain gives you tools and chains. CrewAI gives you roles. N3TX-Agent would give you the **entire operational stack** from one model definition.

---

## 11. The Proposed AgentModel Pattern

### Architecture overview

```
+-----------------------------------------------------------------+
|                     N3TX Agent Layer (NEW)                     |
|                                                                  |
|  +------------------+  +------------------+  +----------------+  |
|  |  ResearchAgent   |  |   CoderAgent     |  |  ReviewAgent   |  |
|  |  (ProtoModel     |  |  (ProtoModel     |  |  (ProtoModel   |  |
|  |   + AgentMixin   |  |   + AgentMixin   |  |   + AgentMixin |  |
|  |   + Storable)    |  |   + Storable)    |  |   + Storable)  |  |
|  +--------+---------+  +--------+---------+  +-------+--------+  |
|           |                      |                    |           |
|  +--------+----------------------+--------------------+--------+  |
|  |           Backend Agent Bus (Python Matrix)                  |  |
|  |  TX{name, source, target, data, meta, timestamp}           |  |
|  +----------------------------+-------------------------------+  |
|                               |                                   |
|  +----------------------------+-------------------------------+  |
|  |                    Shared Services                          |  |
|  |  +---------+ +---------+ +---------+ +----------+ +------+ |  |
|  |  |   LLM   | |  Auth   | | Storage | |  Schema  | | MCP  | |  |
|  |  |  Client  | |  ABAC   | | SQLite  | |  Gen.    | | Srv  | |  |
|  |  | (NEW)   | |(EXISTS) | |(EXISTS) | | (EXISTS) | |(NEW) | |  |
|  |  +---------+ +---------+ +---------+ +----------+ +------+ |  |
|  +------------------------------------------------------------+  |
|                                                                   |
+==================================================================+
|                   Existing N3TX Stack (UNCHANGED)               |
|                                                                   |
|  ProtoModel -> Schema -> Routes -> Frontend (N3TX/Matrix/Actor)   |
|                                                                   |
+------------------------------------------------------------------+
```

### What each layer provides

| Layer | Source | Agent Contribution |
|---|---|---|
| `ProtoModel` | Existing | State schema, field validation, model_dump |
| `AgentMixin` | **New** | `run()` loop, `think()`, tool dispatch |
| `StorableMixin` | Existing (injected) | State persistence, CRUD |
| `LLMClient` | **New** | Provider clients, streaming, cost tracking |
| `@expose_tool` | **New** (mirrors @expose_route) | Tool definition + schema generation |
| `authorize` | Existing | Permission scoping for tool invocation |
| `register_routes` | Existing | API endpoint generation |
| `schema()` | Existing (extended) | Capability manifest with `tools` section |
| MCP adapter | **New** | Translate schema -> MCP `tools/list` |
| A2A adapter | **New** | Translate schema -> Agent Card JSON |

### Protocol compatibility matrix

| Protocol | N3TX Equivalent | Conversion Complexity | LOC Estimate |
|---|---|---|---|
| OpenAI Function Calling | `__agent_tools_signature__()` | Trivial (rename fields) | ~30 |
| Anthropic MCP `tools/list` | `schema()` -> MCP format | Small (wrap + serve via JSON-RPC) | ~200 |
| Google A2A Agent Card | `schema()` -> Agent Card JSON | Small (field mapping) | ~100 |
| OpenAI Agents SDK `@function_tool` | `@expose_tool` | Identical pattern | ~20 (decorator) |
| Microsoft `@ai_function` | `@expose_tool` + reflection | Near-identical | ~50 |

---

## 12. Sources

**Industry protocols and specifications:**
- [OpenAI Function Calling Documentation](https://platform.openai.com/docs/guides/function-calling)
- [OpenAI Agents SDK - Tools](https://openai.github.io/openai-agents-python/tools/)
- [OpenAI Agents SDK - Function Schema](https://openai.github.io/openai-agents-python/ref/function_schema/)
- [MCP Specification 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25)
- [MCP Tool Schema Explained](https://www.merge.dev/blog/mcp-tool-schema)
- [Google A2A Protocol Announcement](https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/)
- [A2A Protocol Specification](https://a2a-protocol.org/latest/specification/)
- [Microsoft Agent Framework](https://devblogs.microsoft.com/foundry/introducing-microsoft-agent-framework-the-open-source-engine-for-agentic-ai-apps/)
- [Open Agent Specification](https://www.emergentmind.com/topics/open-agent-specification-agent-spec)

**Agent frameworks and tools:**
- [LangChain Tools: 2026 Production Patterns](https://langchain-tutorials.github.io/langchain-tools-agents-2026/)
- [CrewAI Enterprise RBAC](https://docs.crewai.com/en/enterprise/features/rbac)
- [CrewAI Framework 2025 Review](https://latenode.com/blog/ai-frameworks-technical-infrastructure/crewai-framework/crewai-framework-2025-complete-review-of-the-open-source-multi-agent-ai-platform)
- [Pydantic AI - Function Tools](https://ai.pydantic.dev/tools/)
- [Top AI Agent Frameworks 2026](https://www.vellum.ai/blog/top-ai-agent-frameworks-for-developers)
- [Best AI Agent Frameworks 2025](https://www.getmaxim.ai/articles/top-5-ai-agent-frameworks-in-2025-a-practical-guide-for-ai-builders/)

**Actor model and agent architecture:**
- [Akka Actor Model for Agentic AI](https://pradeepl.com/blog/agentic-ai/akka-actor-model-agentic-ai/)
- [Actor Pattern and AI Natural Synergy](https://www.robotmunki.com/blog/actor-pattern-and-ai.html)
- [Akka Agent Component](https://akka.io/blog/introducing-akkas-new-agent-component)
- [Akka Inter-Agent Communications](https://doc.akka.io/concepts/inter-agent-comms.html)

**Schema-driven development:**
- [Schema-Driven Platforms: JSON Schema as Underrated Tool](https://peterhrynkow.com/ai/architecture/2025/02/01/schema-driven-platforms.html)
- [Schema-Driven Development and Single Source of Truth](https://godspeed.systems/blog/schema-driven-development-and-single-source-of-truth)
- [AI Agent Tools with Strong Schemas](https://arunangshudas.com/blog/ai-agent/ai-agent-tools-with-strong-schema/)
- [JSON Schema for Structured AI Agent Output](https://demo.wallsneedlove.com/blog/json-schema-for-structured-ai-agent-output)

**Security and permissions:**
- [OWASP AI Agent Security Top 10 2026](https://medium.com/@oracle_43885/owasps-ai-agent-security-top-10-agent-security-risks-2026-fc5c435e86eb)
- [ABAC for AI Agents](https://www.knostic.ai/blog/attribute-based-access-control-abac)
- [ABAC Implementation Strategy](https://www.knostic.ai/blog/abac-implementation-strategy)
- [AI Agent Security Landscape 2025](https://www.obsidiansecurity.com/blog/ai-agent-market-landscape)

**MCP ecosystem:**
- [MCP Impact 2025 - Thoughtworks](https://www.thoughtworks.com/en-us/insights/blog/generative-ai/model-context-protocol-mcp-impact-2025)
- [MCP Enterprise Adoption Guide](https://guptadeepak.com/the-complete-guide-to-model-context-protocol-mcp-enterprise-adoption-market-trends-and-implementation-strategies/)
- [MCP Explained: Why It Matters in 2026](https://robomotion.io/blog/mcp-explained-why-model-context-protocol-matters-in-2026/)

**N3TX codebase files analyzed:**
- `/workspace/src/n3tx/core/models/proto_model.py` -- Base model, schema generation
- `/workspace/src/n3tx/core/models/storable_mixin.py` -- CRUD operations
- `/workspace/src/n3tx/core/api/routes_fastapi.py` -- Auto-generated routes
- `/workspace/src/n3tx/core/authorize/rules.py` -- ABAC access rules
- `/workspace/src/n3tx/core/authorize/schema.py` -- Rule serialization to JSON
- `/workspace/src/n3tx/core/authorize/context.py` -- Access context dataclass
- `/workspace/src/n3tx/core/authorize/resolver.py` -- Authorization resolver protocol
- `/workspace/src/n3tx/core/utils/decorators.py` -- @expose_route decorator
- `/workspace/src/n3tx/core/utils/introspection.py` -- Schema type resolution
- `/workspace/src/n3tx/core/utils/registrar.py` -- Model registry
- `/workspace/src/n3tx/core/app.py` -- N3TXApp builder + create_app()
- `/workspace/src/n3tx/static/core/N3TX.js` -- Frontend entity system, DynamicClass
- `/workspace/src/n3tx/static/core/Matrix.js` -- Message bus / actor system
- `/workspace/src/n3tx/static/core/Actor.js` -- Base actor class
- `/workspace/src/n3tx/static/core/Router.js` -- Navigation state actor
- `/workspace/src/n3tx/static/core/TX.js` -- Transaction envelope
- `/workspace/src/n3tx/static/core/Observable.js` -- Observable mixin
- `/workspace/src/n3tx/static/core/transport/NetworkAdapter.js` -- HTTP/WS transport
- `/workspace/src/n3tx/example/models/product.py` -- Example entity model

---

