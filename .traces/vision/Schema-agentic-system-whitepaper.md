# 📄 Schema-Driven Agentic Systems Applied: A Technical Whitepaper

> *How principles from schema-driven agent architectures can reshape our system -- and where they can't.*
> *Companion to the [propositions document](schema-agentic-system-propositions.md).*

---

## Abstract

Between 2023 and 2026, the AI agent industry converged on a single architectural insight: JSON Schema is the universal contract for defining what agents can do, what data they accept, and how they communicate. OpenAI's function calling, Anthropic's Model Context Protocol (97M+ monthly SDK downloads), Google's Agent-to-Agent protocol (150+ organizations), and Microsoft's declarative agent manifests all use JSON Schema as their interface layer. N3TX's architecture -- where a Python model definition generates the entire application stack via JSON Schema -- is structurally isomorphic to what the agent ecosystem is independently building. This whitepaper examines that alignment in detail, identifies where our existing primitives (`ProtoModel.schema()`, `@expose_route`, `Actor/Matrix/TX`, ABAC authorization, `DynamicClass` via `prototype()`) directly map onto agent system requirements, and proposes a phased integration path. The core argument: we should not become an agent framework. We should recognize that our schema pipeline -- the most expensive piece of infrastructure in the agent ecosystem -- already exists, and make it accessible to the agents that need it. The estimated gap is 35% additive infrastructure (LLM integration, planning loops, memory management), achievable in 10-14 weeks, layered on top of an architecture that does not need to change.

---

## 1. Introduction: Why This Matters Now

There is a structural shift happening in software architecture that directly concerns any schema-driven system. The AI agent market reached $7.8 billion in 2025 and is projected to hit $52.6 billion by 2030. But the market size is not the point. The point is **where the value is accumulating**.

The model layer -- the LLMs themselves -- is commoditizing. GPT-4o, Claude Opus, Gemini, Llama: they are converging in capability and competing on price. The protocol layer -- MCP for tool access, A2A for agent communication -- is standardizing under Linux Foundation governance. The real differentiation is happening at the **agent definition layer**: how you specify what agents can do, what constraints they operate under, and how they compose into systems.

This is precisely the layer where schema-driven architectures have an unfair advantage. An agent framework like LangChain requires developers to define tools, wire up storage, configure permissions, build APIs, and set up monitoring -- all separately, in different files, using different patterns. A schema-driven system derives all of those from a single declaration. The question is whether our particular schema-driven system can participate in this shift, and what it would take.

The answer, after reading the research and the codebase side by side, is more encouraging than expected. Not because we need to build an agent framework -- we do not -- but because the infrastructure the agent ecosystem needs most is the infrastructure we already have.

---

## 2. Principles Worth Importing

Five principles from the schema-driven agent literature stand out as directly applicable to our system. Each represents a concept the industry is converging on, where we already have partial implementation, and where targeted investment would complete the picture.

### 2.1 Schema as Capability Declaration

**What it is:** An agent publishes a structured document -- an Agent Card (A2A), a `tools/list` response (MCP), a function calling definition (OpenAI) -- that describes its capabilities in machine-readable form. Any consumer that reads the document knows, without prior integration work, exactly what the agent can do, what inputs it accepts, what outputs it produces, and what authentication is required.

**Why it matters for us:** `ProtoModel.schema()` already produces documents that carry this information. The `methods` section describes callable endpoints with typed parameters and return types. The `access` section describes authorization requirements. The `$defs` section describes related types. The `$id` provides a unique identity URL. The gap is not structural -- it is format. Our schema carries a superset of what MCP and A2A require; we just need thin adapters to emit their specific envelope formats.

**Where we already partially implement it:** Every `GET /{ClassName}` endpoint serves a capability declaration. The frontend's `N3TX.SCHEMA()` handler consumes it and creates a fully functional typed class at runtime. This is the pattern -- schema in, capability out -- that the agent ecosystem is standardizing. We have had it since before MCP existed.

### 2.2 Composable Access Control at the Schema Level

**What it is:** Agent security requires fine-grained, per-tool authorization that is declared in the schema -- not scattered across code. OWASP's 2026 Agentic AI Top 10 identifies "Excessive Permissions" and "Tool Misuse" as top risks. The principle of Least Agency (minimum autonomy) and Least Privilege (minimum tool access) must be **structurally enforced**, not just prompted.

**Why it matters for us:** Our `authorize` package is more sophisticated than anything in the agent ecosystem. CrewAI's enterprise RBAC is role-based only. OpenAI's Agents SDK has no built-in permissions. Microsoft delegates to Entra ID. We have attribute-based access control with boolean composition (`|`, `&`, `~`), JSON serialization for schema exposure, and SQL pushdown for efficient filtering. This is a genuine competitive advantage.

**Where we already partially implement it:** `rules.py` defines `ANYONE`, `AUTHENTICATED`, `OWNER`, `ROLE()`, and `Where()` -- all composable, all serializable via `to_dict()`. The `access_schema()` function in `authorize/schema.py` serializes model-level access rules into the JSON Schema. The frontend reads these rules from the schema and enforces them via `Permissions.js`. The agent equivalent would be: read the access rules from the schema and enforce them before tool invocation.

### 2.3 Runtime Behavior Derivation from Schema

**What it is:** The most powerful property of schema-driven systems: behavior is derived from the schema at runtime, not hardcoded. Adding a tool to the schema automatically makes it available. Removing a permission immediately restricts behavior. The schema is not documentation -- it is the executable specification. Thoughtworks' 2025 Technology Radar highlighted this as "spec-driven development": the schema IS the spec.

**Why it matters for us:** This is our core architecture. `ProtoModel.schema()` generates the spec, `register_routes()` derives API endpoints from it, `N3TX.SCHEMA()` derives frontend classes from it, `form.js` derives form fields from it, `Permissions.js` derives access controls from it. Adding agent behavior derivation -- "read the schema, know what tools are available, know what permissions apply" -- is the same pattern applied to a new consumer.

**Where we already partially implement it:** The entire frontend is runtime-derived from the schema. `prototype()` in `N3TX.js` creates JavaScript classes from schema properties and methods. The `DynamicClass` pattern is exactly what agent proxies need. The backend has `generate_join_model()` which creates Python classes dynamically from `type()`. Both halves of the runtime derivation pipeline exist.

### 2.4 Actor-Based Message Routing for Agent Communication

**What it is:** The actor model (Hewitt, 1973) maps precisely onto multi-agent systems. Each agent encapsulates private state, communicates via messages, and is supervised by a parent. Akka explicitly positions its actor runtime as agent infrastructure. The five-property mapping -- Actor=Agent, Message=Task, Mailbox=Queue, Isolated state=Context, Supervision=Error recovery -- is not an analogy but an equivalence.

**Why it matters for us:** We have an actor system. `Actor.js` provides addressable identity, child hierarchy, inbox dispatch, and spawn. `Matrix.js` routes messages by address with local/remote fallback. `TX` carries the full message envelope: name, source, target, data, meta, timestamp. This is not a toy implementation -- it is a production message bus that routes every frontend interaction through typed, addressed messages.

**Where we already partially implement it:** The frontend actor system is fully operational. The gap is on the backend: there is no Python-side `Matrix` for routing messages between agent models. The JS/Python bridge exists via `NetworkAdapter` (HTTP + WebSocket), but backend-to-backend agent communication would require a Python port of the routing logic. The patterns are identical; the port is mechanical.

### 2.5 Schema Composition via `$defs` and `$ref`

**What it is:** JSON Schema's composition primitives (`$ref`, `$defs`, `allOf`, `oneOf`) enable building complex agent capabilities from reusable building blocks. A research team schema can reference a researcher agent, a fact-checker agent, and an editor agent -- each defined as a `$def` with its own identity, skills, and access rules. This is how MCP is addressing token bloat: deduplicate shared schemas via `$ref` instead of inlining them repeatedly.

**Why it matters for us:** We already use `$defs` extensively. When a `Product` model references `Comment` and `Like`, those appear as `$defs` entries in the schema, each with their own `$id`, properties, methods, and access rules. `N3TX.SCHEMA()` registers each `$def` as an independent `DynamicClass`. The agent equivalent -- registering sub-agents from a parent agent's `$defs` -- follows the same pattern exactly.

**Where we already partially implement it:** `schema()` in `proto_model.py` (lines 222-247) collects referenced models, generates their schemas, bubbles up `$defs`, and assigns each a `$id`. The frontend processes these in `N3TX.SCHEMA()` (N3TX.js, line 390+) by iterating `data.$defs` and calling `prototype()` for each. This is agent composition via schema -- we just call the composed entities "models" instead of "agents."

---

## 3. Our Architecture Through This Lens

Looking at our codebase through the vocabulary of agentic systems reveals how much of the agent infrastructure we have already built, and how cleanly it maps.

### 3.1 The Data Flow as an Agent Lifecycle

Our current data flow:

```
[Python Model]                [JSON Schema]               [Frontend]
      |                            |                           |
  ProtoModel                   schema()                   N3TX.SCHEMA()
  defines fields,             carries types,              creates DynamicClass,
  methods, access,            methods, access,            renders forms,
  relationships               UI hints, $defs             enforces permissions
```

The agent equivalent:

```
[Agent Model]                [Agent Schema]              [Orchestrator]
      |                            |                           |
  AgentModel                   schema()                   create_proxy()
  defines skills,             carries skills,             creates AgentProxy,
  tools, access,              tools, access,              routes tasks,
  guardrails                  guardrails, $defs           enforces contracts
```

The structural mapping is one-to-one:

| Our Concept | Agent Equivalent | Same Mechanism? |
|------------|-----------------|-----------------|
| `ProtoModel` base class | `BaseAgent` base class | Yes -- Pydantic model with schema generation |
| `model.schema()` | `agent.capability_schema()` | Yes -- `model_json_schema()` + metadata injection |
| `schema.properties` | Agent state fields | Yes -- typed fields with validation |
| `schema.methods` | Agent skills/tools | Yes -- `@expose_route` metadata + type signatures |
| `schema.__access__` | Agent permissions | Yes -- composable ABAC rules |
| `schema.$defs` | Sub-agent schemas | Yes -- referenced model schemas with own `$id` |
| `schema.__ui__` | Interaction hints | Yes -- rendering preferences |
| `prototype()` -> DynamicClass | Agent proxy creation | Yes -- typed class from schema at runtime |
| `N3TX.SCHEMA()` bootstrap | Agent discovery | Yes -- fetch schema, create class, replay queue |
| `model_dump(response=True)` | Self-describing response | Yes -- `$schema` + `$id` on every entity |

### 3.2 What Our Schema Carries That Agent Protocols Miss

Reading the actual A2A and MCP specifications alongside our schema output reveals that our schemas carry **more information** than any existing agent protocol:

**Access rules with boolean composition.** MCP has no access control metadata. A2A has a `securitySchemes` section for authentication (bearer tokens, OAuth) but nothing for authorization logic. Our schema carries `{"op": "or", "rules": [{"rule": "owner"}, {"rule": "role", "roles": ["admin"]}]}` -- composable, serializable, and enforceable at both the API and SQL layers. This is the piece every agent security analysis identifies as missing.

**Field-level UI and display hints.** A2A has `inputModes` and `outputModes` at the agent level. Our schema carries per-field `ui.widget`, `ui.placeholder`, `ui.display`, and `ui.protected` flags. These could inform how an LLM presents tool results to users or how an orchestrator formats inputs.

**Nested model composition with independent identity.** MCP tools are flat: each tool has an `inputSchema` but no mechanism for shared sub-schemas. Our `$defs` entries each have their own `$id`, `methods`, `access`, and `ui` -- they are fully independent entities that happen to be referenced by a parent. This is the composition primitive that agent teams need: define a researcher, a fact-checker, and an editor as `$defs`, compose them into a team schema via `allOf`.

**Self-describing responses.** Every entity response includes `$schema` (the schema URL) and `$id` (the instance URL). Any consumer can independently resolve the type and trace back to the source. No agent protocol currently mandates self-describing responses -- they are assumed to follow the schema of the tool that was called.

### 3.3 The Actor System as Agent Infrastructure

The frontend actor system deserves special attention because it is the most directly translatable component:

```
Frontend Actor System (existing)          Agent Communication System (target)
====================================      ====================================

Matrix (root router)                      Agent Bus (message router)
  |-- routes by address                     |-- routes by agent ID
  |-- local/remote fallback                 |-- local/remote fallback
  |-- children map                          |-- agent registry
  |                                         |
Actor (addressable entity)                Agent (addressable entity)
  |-- #addr (unique identity)               |-- agent_id (unique identity)
  |-- #parent (supervisor)                  |-- supervisor_agent
  |-- #children (managed entities)          |-- sub_agents
  |-- inbox(event) (message handler)        |-- receive(task) (task handler)
  |-- spawn(addr, Class) (create child)     |-- delegate(agent_id, task)
  |                                         |
TX (message envelope)                     AgentMessage (task envelope)
  |-- name (event type)                     |-- type (task type)
  |-- source (sender address)               |-- from_agent (sender ID)
  |-- target (receiver address)             |-- to_agent (receiver ID)
  |-- data (payload)                        |-- payload (task data)
  |-- meta (routing metadata)               |-- metadata (trace, cost, priority)
  |-- tst (timestamp)                       |-- timestamp
```

The routing logic in `Matrix.inbox()` -- check if target is local, forward to child, or delegate to remote -- is the exact decision tree an agent bus needs. The `Actor.subclass()` mechanism that adds static `send`, `inbox`, `children`, and `register` to any class is the exact augmentation pattern an `AgentMixin` would use.

---

## 4. The Synthesis: Where Two Worlds Meet

Three integration points stand the highest chance of creating value with the least architectural disruption. Each builds on existing infrastructure rather than replacing it.

### 4.1 Integration Point: Schema as MCP Tool Manifest

**Before:**

```
N3TX Model                    MCP Ecosystem
===========                     =============
Product.schema()                Claude Desktop, GPT, Cursor, VS Code
  |-- methods.comment             (300+ MCP clients)
  |-- methods.like                  |
  |-- methods.favorite              |
  |                                 |
  (consumed only by                (no connection)
   our own frontend)
```

**After:**

```
N3TX Model                    MCP Ecosystem
===========                     =============
Product.schema()  --adapter-->  MCP tools/list response
  |-- methods.comment              |-- tool: product_comment
  |-- methods.like                 |-- tool: product_like
  |-- methods.favorite             |-- tool: product_favorite
  |                                 |
  (consumed by our frontend        (consumed by 300+ MCP clients:
   AND the agent ecosystem)         Claude, GPT, Cursor, VS Code, etc.)
```

**Migration path:** The adapter is a ~200 LOC module that reads `schema().methods` for each registered model and emits MCP-compatible `tools/list` responses. It serves these via JSON-RPC over stdio (for local agents like Claude Desktop) or HTTP (for remote agents). No changes to `ProtoModel`, no changes to existing routes, no changes to the frontend.

**Expected outcome:** Any MCP-compatible AI assistant can interact with N3TX data through typed, validated tool calls. A user in Claude Desktop could say "show me all products over $50" and Claude would call the MCP tool backed by our `Product.list()` with appropriate filters. The schema carries the type information; the LLM handles natural language understanding.

### 4.2 Integration Point: ABAC Rules as Agent Security Layer

**Before (agent frameworks today):**

```
Agent invokes tool
  |
  v
Tool executes                   (no authorization check)
  |
  v
Response returned               (any agent can call any tool)
```

**After (with our ABAC):**

```
Agent invokes tool
  |
  v
ABAC rule evaluation            schema.access.invoke = AUTHENTICATED & Budget(>0.10)
  |-- Is caller authenticated?    -> ctx.is_authenticated
  |-- Does agent have budget?     -> ctx.resource.budget >= 0.10
  |-- Is caller the owner?        -> ctx.user_id == resource.user_owner
  |
  +-- DENIED --> 403 + structured error
  +-- GRANTED --> tool executes -> response returned
```

**Migration path:** The `authorize` package has zero N3TX imports -- it is already a standalone ABAC library. Adding agent-specific rule subclasses (`Budget`, `RateLimit`, `DelegationDepth`) requires no changes to the engine. They plug into `__access__` dicts exactly like `OWNER` and `ROLE()`. The route layer in `routes_fastapi.py` already enforces access rules before executing methods; the same enforcement applies to agent tool invocations.

**Expected outcome:** Every tool invocation -- whether from a frontend user, an API client, or an AI agent -- goes through the same authorization pipeline. An agent that exhausts its budget is denied at the authorization layer, not at the LLM layer where prompt injection could bypass it. The access rules are in the schema, so any consumer (frontend, agent runtime, audit system) can read and respect them.

### 4.3 Integration Point: DynamicClass Pattern for Agent Proxies

**Before (integrating with a remote agent):**

```python
# Hand-coded integration per agent (fragile, unmaintained)
import httpx

class ResearchAgentClient:
    def deep_research(self, topic: str, depth: str = "moderate"):
        response = httpx.post(
            "https://agents.example.com/research",
            json={"topic": topic, "depth": depth},
            headers={"Authorization": f"Bearer {token}"}
        )
        return response.json()  # No type validation
```

**After (DynamicClass from schema):**

```python
# Auto-generated proxy from Agent Card (typed, validated, maintained by schema)
schema = fetch("https://agents.example.com/.well-known/agent.json")
ResearchProxy = create_agent_proxy(schema)

# ResearchProxy.deep_research(topic, depth) now:
# 1. Validates inputs against schema.skills.deep_research.parameters
# 2. Checks access rules against schema.access.invoke
# 3. Calls the remote endpoint
# 4. Validates response against schema.skills.deep_research.returns
# 5. Returns typed result
```

**Migration path:** `generate_join_model()` in `proto_model.py` already creates Python classes dynamically using `type()`. The agent proxy generator would follow the same pattern: read a schema, create a class with typed methods, add validation hooks. The frontend `prototype()` function is the reference implementation for the logic; the backend port is a Python translation.

**Expected outcome:** Integrating with a new external agent becomes a one-liner: `proxy = create_agent_proxy(agent_card_url)`. The proxy is typed, validated, and access-controlled. When the remote agent updates its schema (adds skills, changes parameters), fetching the updated Agent Card regenerates the proxy automatically. No hand-coded client code to maintain.

---

## 5. Boundaries: Where This Doesn't Apply

Intellectual honesty requires identifying where agent patterns would hurt our architecture rather than help it.

### 5.1 Not Everything Should Be an Agent

Gartner projects that 40% of agentic AI projects will be canceled by 2027, with the root cause being applying agent complexity to problems that don't require it. Our system serves a clear purpose: schema-driven full-stack application development. Adding agent capabilities should extend that purpose, not replace it.

A `Product` model that generates CRUD endpoints, forms, and permissions does not need to become an agent. It needs to be **accessible to agents** -- which is what the MCP adapter achieves without changing the model itself. The temptation to make every model agent-capable should be resisted. The `__agent__ = True` flag (proposed in Proposition 5 of the companion document) should be used sparingly and intentionally.

### 5.2 LLM Non-Determinism vs. Schema Determinism

Our architecture's strength is determinism. `ProtoModel.schema()` produces the same output every time. `register_routes()` generates the same endpoints. The frontend renders the same forms. This predictability is what makes the system trustworthy.

AI agents introduce fundamental non-determinism. The same input to an LLM can produce different tool selections, different parameter values, and different reasoning paths. This conflicts with our "transparent, not magical" principle -- an LLM-powered agent is, by nature, opaque in its decision-making.

The resolution is **boundaries**: use schemas at every integration boundary (deterministic, validatable), use LLMs in the middle (non-deterministic, but constrained). Input validation, output validation, access control, cost limits, and tool boundaries are all schema-enforced and deterministic. The LLM handles reasoning within those boundaries. This is the "schema at the boundaries, code in the middle" pattern the industry is converging on.

### 5.3 Latency Constraints

Each agent handoff adds 100-500ms of latency. An LLM tool call adds 200ms-2s. A multi-agent pipeline with 5 steps can take 10-30 seconds. Our current system serves API responses in <100ms and renders frontend forms instantly from cached schemas.

Agent-powered features must be clearly separated from latency-sensitive paths. Schema endpoints (`GET /Product`) should never route through an LLM. CRUD operations should remain direct database calls. Agent capabilities are for tasks that justify the latency: natural language queries, multi-step reasoning, document analysis. Mixing agent latency into the critical path would degrade the system for non-agent users.

### 5.4 The Abstraction Trap

Our design philosophy states: "Modular where it simplifies, coupled where it must." The agent ecosystem is littered with over-abstracted frameworks: generic agent buses that add three layers of indirection over a simple HTTP call, orchestration engines that require a PhD to configure, and plugin systems where the plugin API is more complex than the code it wraps.

We should resist adding abstraction layers for agent support. The MCP adapter should be a thin translation function, not a framework. The `AgentMixin` should add methods to existing models, not wrap them in an agent container. The Python `Matrix` should route messages, not interpret them. Each addition should pass the test from our design philosophy: "does this boundary make the code easier to read, easier to test, or easier to replace one side without touching the other?"

---

## 6. A Path Forward

The propositions document identifies 10 specific proposals. Here they are organized into a phased roadmap with explicit success criteria and decision gates.

### Phase 0: Schema Exposure (Weeks 1-4)

**Goal:** Make our existing schemas accessible to the agent ecosystem without building any agent logic.

**Work:**
- Build MCP tool adapter from `ProtoModel.schema()` output (Proposition 1)
- Generate A2A Agent Cards from the same schema (Proposition 2)
- Add `@expose_tool` decorator for agent-specific metadata (Proposition 3)
- Add cost/reliability metadata to schema method entries (Proposition 9)

**Success criteria:**
- 3+ internal users successfully query N3TX data through MCP clients
- Schema-to-MCP conversion achieves 100% fidelity (every method correctly exposed)
- Zero changes to existing `ProtoModel`, `routes_fastapi.py`, or frontend code

**Decision gate:** If tool call accuracy (correct tool selected for user intent) exceeds 90% in testing, proceed to Phase 1. If below 70%, investigate schema description quality before proceeding.

**Investment:** 2-4 weeks, 1-2 engineers. Zero LLM cost.

### Phase 1: Hardened Foundation (Weeks 5-8)

**Goal:** Add the security and governance infrastructure that production agents require.

**Work:**
- Add agent-specific ABAC rules: `Budget`, `RateLimit`, `DelegationDepth` (Proposition 4)
- Add schema-carried guardrails: `__guardrails__` dict pattern (Proposition 7)

**Success criteria:**
- Budget exhaustion correctly blocks tool invocation (100% enforcement rate)
- Rate limiting prevents runaway agent loops (verified with synthetic load)
- Guardrail violations produce structured error responses, not silent failures

**Decision gate:** If the security layer passes adversarial testing (simulated prompt injection, budget exhaustion, rate limit bypass attempts), proceed to Phase 2.

**Investment:** 2-3 weeks, 1 engineer. Zero LLM cost.

### Phase 2: Single Agent (Weeks 9-14)

**Goal:** Build one bounded agent that demonstrates "define a model, get an agent."

**Work:**
- Build `AgentMixin` with ReAct-style `run()` loop (Proposition 5)
- Build `LLMClient` abstraction for provider-agnostic LLM integration
- Build evaluation suite with 100+ test cases

**Success criteria:**
- Task completion rate > 90% for the chosen use case
- Cost per task < $0.15
- Zero production incidents in 30-day window
- Evaluation suite runs on every deployment

**Decision gate:** If single-agent metrics meet targets, proceed to Phase 3. If task completion < 70% after two prompt iterations, reassess the use case.

**Investment:** 4-6 weeks, 2 engineers. ~$0.09/task LLM cost.

### Phase 3: Multi-Agent Foundation (Months 4-6)

**Goal:** Enable agents to communicate and compose.

**Work:**
- Port Actor/Matrix to Python for backend agent communication (Proposition 6)
- Build runtime agent proxy generation from remote schemas (Proposition 8)
- Build schema registry with version negotiation (Proposition 10)

**Success criteria:**
- Two agents can exchange typed messages via Python Matrix
- Remote agent proxy generation works for 3+ external Agent Card formats
- Schema versioning prevents integration breakage across agent updates

**Decision gate:** End-to-end multi-agent task completion > 95% before expanding beyond 3 agents. Cost within 120% of budget estimates.

**Investment:** 6-10 weeks, 2-3 engineers. ~$0.50-2.00/task LLM cost.

### What We Do Not Build

At no point in this roadmap do we build:
- A custom LLM orchestration engine (use LangGraph or CrewAI for complex orchestration)
- A vector database for agent memory (use existing solutions like Redis, Postgres with pgvector)
- A prompt management UI (use LangSmith or similar tooling)
- A model fine-tuning pipeline (out of scope for a framework)

We build the **bridge** between our schema infrastructure and the agent ecosystem. Everything else has existing, well-maintained solutions that we should adopt, not rebuild.

---

## 7. Conclusion

The thesis that began as a question -- "can schema-as-agent-protocol concepts improve our architecture?" -- resolves into something more precise: our architecture already implements the core patterns the agent ecosystem is standardizing, and the improvements are a matter of exposure and extension, not transformation.

The model is the app. The schema is the contract. What the agent ecosystem adds is a new class of consumers for that contract: LLMs that read tool schemas instead of rendering forms, orchestrators that compose capability manifests instead of navigating URLs, and autonomous systems that enforce access rules instead of displaying permission buttons.

Our `ProtoModel.schema()` is an MCP capability manifest that doesn't know it yet. Our `@expose_route` is an `@function_tool` decorator wearing a different name. Our `Actor/Matrix/TX` is an agent communication bus that currently routes UI events instead of task assignments. Our ABAC authorization is the most sophisticated agent permission system in the ecosystem -- it just hasn't met an agent yet.

The path forward is not to pivot toward agents. It is to recognize the structural alignment, make our schemas accessible through standard protocols, and let the agent ecosystem come to us. Phase 0 costs 2-4 weeks and zero LLM spend. It creates permanent optionality. If the agent ecosystem delivers on its trajectory -- and with $690B in hyperscaler AI capex committed for 2026, the infrastructure investment is real -- our schema pipeline becomes exponentially more valuable with each new MCP client, each new A2A-compatible orchestrator, and each new agent that discovers our capabilities through a published schema.

The model is the app. The schema is the agent. The bridge is within reach.
