# 🔧 Schema-Driven Agentic Systems x Our System: Technical Propositions

> *How schema-as-agent-protocol principles can improve our architecture.*
> *Based on research in `.traces/research/schema-agentic-system/` and codebase analysis.*

---

## 🎯 The Bridge

N3TX's fundamental axiom -- **the model is the app** -- maps onto an insight the entire AI agent industry arrived at independently between 2023 and 2026: **the schema is the agent**. OpenAI, Anthropic, Google, and Microsoft all converged on JSON Schema as the universal contract for defining what an agent can do, what inputs it accepts, and what outputs it produces. N3TX already generates rich, typed, access-controlled JSON Schema from Python model definitions. The structural alignment is not a metaphor -- it is architectural isomorphism.

The research identifies nine direct architectural parallels between our existing primitives and agent system requirements: `ProtoModel.schema()` maps to capability manifests, `@expose_route` maps to `@function_tool`, `Actor/Matrix/TX` maps to the agent communication bus, ABAC rules map to agent permission scoping, `StorableMixin` maps to agent state persistence, and `prototype()`/`DynamicClass` maps to runtime agent instantiation. The estimated coverage of agent infrastructure is 65%, with the missing 35% (LLM integration, planning loops, memory) being additive -- layers on top, not rewrites underneath.

The opportunity is not to become an agent framework. The opportunity is to recognize that our schema pipeline is the most expensive piece of infrastructure the agent ecosystem is building, and we already have it. Every proposition below is about making that existing asset available to the agent ecosystem, not about abandoning what we have.

---

## 💡 Propositions

### Proposition 1: Expose existing model schemas as MCP tools -- zero LLM cost, immediate ecosystem access

> 🔧 **Proposition:** Auto-generate MCP `tools/list` responses from `ProtoModel.schema()` output, making every N3TX model instantly accessible to Claude, GPT, Cursor, and 300+ MCP clients.

**From the research:** MCP has 97M+ monthly SDK downloads and 10,000+ public servers. It is the fastest-adopted developer protocol since Docker. Every major AI provider -- including OpenAI, Google, and Microsoft -- has adopted Anthropic's protocol. The tool definition format is JSON Schema with `name`, `description`, and `inputSchema` fields. (01-industry-landscape.md, Section 3)

**In our system:** `ProtoModel.__n3tx_methods_json_signature__()` (proto_model.py, line 140) already extracts typed parameter schemas from `@expose_route` methods. The `schema()` method (line 199) produces a JSON Schema document with `methods`, `properties`, `access`, and `$defs`. The conversion from our schema format to MCP's `tools/list` format is a field rename, not a structural transformation.

**The idea:** Build a thin adapter layer -- approximately 200 lines of code -- that reads each registered `ProtoModel` subclass, iterates over `schema().methods`, and serves them as MCP tool definitions via JSON-RPC over stdio or HTTP. For a `Product` model with a `comment` method, the adapter would emit:

```
ProtoModel.schema().methods.comment    -->    MCP tools/list response
  route: "/comment"                           name: "product_comment"
  parameters: {comment: {$ref: Comment}}      inputSchema: {type: "object", ...}
  returns: {type: "string"}                   outputSchema: {type: "string"}
  access: {rule: "authenticated"}             annotations: {requiresAuth: true}
```

The result: any MCP client -- Claude Desktop, VS Code Copilot, ChatGPT with MCP plugins -- can interact with N3TX data through typed, validated tools. No LLM spend. No agent logic. Just schema publication.

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | **Low** -- ~200 LOC adapter, 2-3 weeks with one engineer. Reuses existing `__n3tx_methods_json_signature__()` output. |
| Impact | **High** -- Unlocks the entire MCP ecosystem (97M+ downloads/month). Creates permanent optionality for agent features. |
| Risk | **Very Low** -- Publishing schemas, not running agents. No LLM cost. Reversible in minutes. |
| Timeline | **2-4 weeks** |

---

### Proposition 2: Publish A2A Agent Cards from model schemas for cross-system discovery

> 🔧 **Proposition:** Generate A2A-compatible Agent Card JSON from `ProtoModel.schema()` and serve it at `/.well-known/agent.json`, enabling other agents to discover and negotiate with our system.

**From the research:** Google's A2A protocol uses Agent Cards -- JSON documents describing capabilities, skills, and authentication -- published at well-known endpoints for discovery. 150+ organizations back it through the Linux Foundation. Agent Cards carry `name`, `skills[]`, `capabilities`, and `securitySchemes`. (01-industry-landscape.md, Section 4; 05-schema-as-agent-protocol.md, Section 7)

**In our system:** `ProtoModel.schema()` already carries `__name__`, `methods` (which map to A2A skills), `access` rules (which map to security schemes), and `$defs` for related types. The `schema()` method on line 310-311 of proto_model.py sets `$schema` and `$id` -- the self-describing identity pattern A2A expects.

**The idea:** Add a `/.well-known/agent.json` route to `FastAPIBackend` that aggregates all registered models into a single Agent Card. Each model's `methods` become A2A `skills`. Access rules serialize into `securitySchemes`. UI renderer hints map to `inputModes`/`outputModes`. This is a ~100 LOC transformation function plus a single FastAPI route.

```
GET /.well-known/agent.json
{
  "name": "N3TX Application",
  "skills": [
    {
      "id": "product-comment",           <-- from schema.methods.comment
      "name": "Add Product Comment",     <-- from method docstring
      "inputModes": ["application/json"],
      "outputModes": ["application/json"]
    }
  ],
  "securitySchemes": {                   <-- from schema.access
    "bearer": {"type": "http", "scheme": "bearer"}
  }
}
```

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | **Low** -- ~100 LOC + 1 route. Mechanical field mapping. |
| Impact | **Medium** -- Positions us in the A2A ecosystem. Enables agent-to-agent discovery of our capabilities. |
| Risk | **Very Low** -- Read-only endpoint. No behavioral change. |
| Timeline | **2-3 days** |

---

### Proposition 3: Add an `@expose_tool` decorator that mirrors `@expose_route` for agent-specific metadata

> 🔧 **Proposition:** Create an `@expose_tool` decorator that extends the `@expose_route` pattern with agent-specific metadata: description for LLM consumption, cost estimates, timeout constraints, and output schema declarations.

**From the research:** Every major agent framework uses a decorator pattern for tool registration: OpenAI's `@function_tool`, LangChain's `@tool`, Microsoft's `@ai_function`, PydanticAI's `@agent.tool`. The description field is the most important -- Anthropic's documentation emphasizes it conveys semantic intent that JSON Schema alone cannot. MCP added `outputSchema` in June 2025, closing the full input/output contract. (02-technical-deep-dive.md, Section 2; 04-our-stack-relevance.md, Section 4)

**In our system:** `@expose_route` in `decorators.py` (line 3) attaches `__endpoint__` metadata to methods. `__n3tx_methods_json_signature__()` reads this metadata and serializes it into the schema. The pattern is identical to what agent frameworks do -- the only missing piece is agent-specific fields.

**The idea:** `@expose_tool` would be a superset of `@expose_route`:

```python
@expose_tool(
    description="Search the web for current information",  # LLM reads this
    cost={'estimated_tokens': 500},                         # Budget-aware routing
    timeout=30,                                             # Safety boundary
    access=AUTHENTICATED                                    # Reuse ABAC
)
def web_search(self, query: str) -> list[dict]:
    """Search the web."""
    ...
```

Internally, it sets both `func.__endpoint__` (for HTTP routes) and `func.__tool__` (for agent tool metadata). The schema generation in `__n3tx_methods_json_signature__()` would pick up the `__tool__` attribute and include `cost`, `timeout`, and enhanced `description` in the schema's `methods` section. This is ~30 lines of new code in `decorators.py` and ~20 lines of schema generation changes in `proto_model.py`.

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | **Low** -- ~50 LOC total across two files. Follows established `@expose_route` pattern exactly. |
| Impact | **Medium** -- Makes tool definitions richer for LLM consumption. Enables cost-aware and timeout-aware agent routing. |
| Risk | **Very Low** -- Additive to existing decorator. Backward compatible. |
| Timeline | **2-3 days** |

---

### Proposition 4: Extend ABAC rules with agent-specific access constraints (budget, delegation depth, rate limits)

> 🔧 **Proposition:** Add new `AccessRule` leaf classes -- `Budget`, `RateLimit`, `DelegationDepth` -- that enforce agent-specific boundaries using the existing composable rule engine.

**From the research:** OWASP's 2026 Agentic AI Top 10 identifies "Tool Misuse" and "Excessive Permissions" as critical risks. Their core principle: Least Agency (minimum autonomy for bounded tasks). No agent framework has access control as sophisticated as our ABAC system -- CrewAI's enterprise RBAC is role-based only. Schema-enforced capability boundaries are the primary defense against both accidental and adversarial agent misbehavior. (02-technical-deep-dive.md, Section 8; 04-our-stack-relevance.md, Section 7)

**In our system:** `authorize/rules.py` defines `AccessRule` with `evaluate()`, `sql_filter()`, and `to_dict()` -- composable with `|`, `&`, `~`. Adding agent-specific rules requires **zero changes to the engine**. A `Budget` rule follows the exact pattern of the existing `Where` rule (line 211). The `DefaultResolver` in `resolver.py` (line 30) resolves rules from `__access__` dicts and enforces them -- new rule types plug in transparently.

**The idea:** Three new leaf rules:

```python
class Budget(AccessRule):
    """Grants access only if remaining budget exceeds threshold."""
    def __init__(self, min_remaining: float):
        self.min_remaining = min_remaining

    def evaluate(self, ctx: AccessContext) -> bool:
        budget = getattr(ctx.resource, 'budget', None)
        return budget is not None and budget >= self.min_remaining

class RateLimit(AccessRule):
    """Grants access if invocation count is within limit."""
    ...

class DelegationDepth(AccessRule):
    """Grants access only if delegation chain depth is within limit."""
    ...
```

Usage: `__access__ = {'invoke': AUTHENTICATED & Budget(min_remaining=0.10)}`

These serialize to JSON via `to_dict()`, appear in the schema, and are enforced both at the route layer and in SQL pushdown for list queries. An agent that runs out of budget is denied at the authorization layer -- not at the LLM layer where prompt injection could bypass it.

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | **Low** -- ~80 LOC per rule. Follows existing `Where` pattern. No engine changes. |
| Impact | **High** -- Addresses OWASP's top agent security risks. Differentiates from every competing framework. |
| Risk | **Low** -- New leaf rules cannot break existing rules. Fully backward compatible. |
| Timeline | **1 week** |

---

### Proposition 5: Build an `AgentMixin` that adds LLM-powered `run()` loops to any ProtoModel

> 🔧 **Proposition:** Create an `AgentMixin` class -- analogous to `StorableMixin` -- that injects a `run()` method, tool dispatch, and LLM client into any ProtoModel subclass, enabling "define a model, get an agent."

**From the research:** The Plan-and-Execute pattern is the most schema-amenable agent architecture because both the plan structure and tool calls are fully schema-definable. LangGraph proves this with typed `AgentState` schemas that flow through directed graphs. The ReAct pattern (observe-reason-act loop) is the production default. Both can be driven by the tool schemas our models already produce. (02-technical-deep-dive.md, Sections 1 and 3)

**In our system:** `StorableMixin` (storable_mixin.py, line 16) demonstrates the pattern: a mixin injected into `ProtoModel` subclasses via `__init_subclass__()` (proto_model.py, line 72). It adds CRUD methods without modifying the base class. An `AgentMixin` would follow the same injection pattern but add `run()`, `think()`, and tool dispatch.

**The idea:** When a model declares `__agent__ = True`, `__init_subclass__()` injects `AgentMixin` alongside `StorableMixin`:

```python
class ResearchAgent(ProtoModel):
    __tablename__ = 'research_agents'
    __storable__ = True
    __agent__ = True
    __llm__ = {'provider': 'anthropic', 'model': 'claude-sonnet-4-20250514'}
    __prompt__ = {'system': "You are a research analyst..."}
    __access__ = {'invoke': AUTHENTICATED & Budget(min_remaining=0.10)}

    topic: str = Field(default="")
    report: str = Field(default="")
    budget: float = Field(default=1.0)

    @expose_tool(description="Search the web")
    def web_search(self, query: str) -> list[dict]: ...
```

`AgentMixin.run(task)` implements a ReAct loop: call the LLM with the model's tool schemas, dispatch tool calls to `@expose_tool` methods, validate responses against output schemas, repeat until done or budget exhausted. The model's `schema()` output already contains everything the LLM needs to know about available tools.

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | **High** -- 3-4 weeks. Requires LLM client abstraction, ReAct loop, tool dispatch, cost tracking. |
| Impact | **Very High** -- Achieves "define a model, get an agent." No other framework offers this level of integration from a single definition. |
| Risk | **Medium** -- LLM integration introduces non-determinism. Requires evaluation infrastructure. |
| Timeline | **4-6 weeks** |

---

### Proposition 6: Port the Actor/Matrix message bus to Python for backend agent communication

> 🔧 **Proposition:** Create a Python-side `Actor`/`Matrix`/`TX` system that mirrors the frontend's message bus, enabling backend agents to communicate via typed, routed messages with supervision.

**From the research:** The actor model maps precisely onto multi-agent systems. Akka explicitly positions its actor runtime as infrastructure for AI agents. The five-property mapping is exact: Actor = Agent, Message = Task, Mailbox = Task queue, Isolated state = Context window, Supervision tree = Error recovery hierarchy. Blackboard architectures (shared state via message bus) achieve 13-57% improvements over direct messaging in task success rates. (02-technical-deep-dive.md, Section 5.5; 04-our-stack-relevance.md, Section 5)

**In our system:** `Actor.js` (static/core/Actor.js) provides addressable identity, child hierarchy, inbox dispatch, and spawn. `Matrix.js` routes messages by address with local/remote fallback. `TX` carries name, source, target, data, meta, and timestamp. These patterns translate directly to Python with `asyncio`.

**The idea:** A Python `Matrix` class that routes `TX` messages between `AgentMixin`-powered models:

```
Backend Agent Bus (Python)
  matrix.send(TX(name="RESEARCH", source="orchestrator", target="research-agent-1", data={topic: "..."}))
    |
    +-- local lookup: matrix.children["research-agent-1"]
    +-- delivery: agent.inbox(tx)
    +-- agent.run() processes the task
    +-- response: TX(name="RESULT", source="research-agent-1", target="orchestrator", data={report: "..."})
```

This reuses the existing `TX` envelope structure and routing logic. The Python port would add async message delivery, durable message persistence via `StorableMixin`, and supervision (restart failed agents). The frontend and backend Matrix instances could eventually bridge via WebSocket, enabling cross-boundary agent coordination.

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | **Medium** -- 2-3 weeks. Python port of existing JS patterns plus asyncio integration. |
| Impact | **High** -- Enables multi-agent coordination on the backend. Foundation for Phase 3 orchestration. |
| Risk | **Medium** -- Distributed systems complexity. Requires careful error handling and supervision. |
| Timeline | **3-4 weeks** |

---

### Proposition 7: Add schema-carried guardrails for input/output/behavioral constraints

> 🔧 **Proposition:** Extend the schema with a `guardrails` section that declares input token limits, output format requirements, max tool calls per task, delegation depth limits, and human-approval triggers -- all enforced at the framework layer, not the prompt layer.

**From the research:** Without schema-enforced guardrails, agent behavior is constrained only by prompt engineering -- which is probabilistic. The Replit incident (agent executed `DROP TABLE` despite explicit instructions) demonstrates that prompt-level constraints fail under pressure. Schema-driven guardrails add structural enforcement: reject if missing required fields, exceeds token limits, or exceeds tool call budget. OWASP's Agentic AI Top 10 recommends Least Agency (minimum autonomy) and Least Privilege (minimum tool access), both expressible as schema constraints. (02-technical-deep-dive.md, Section 8; 05-schema-as-agent-protocol.md, Section 10)

**In our system:** The pattern already exists in `__ui__` (proto_model.py, lines 283-308) and `__access__` (line 256). Both are class-level dicts that get serialized into the schema and enforced at runtime. A `__guardrails__` dict would follow the identical pattern.

**The idea:**

```python
class ResearchAgent(ProtoModel, AgentMixin):
    __guardrails__ = {
        'input': {'max_tokens': 16000, 'required_fields': ['topic']},
        'output': {'must_cite_sources': True, 'format_schema': 'ResearchReport'},
        'behavioral': {
            'max_tool_calls_per_task': 50,
            'max_delegation_depth': 3,
            'timeout_seconds': 300,
            'require_human_approval_when': 'cost > 0.50'
        }
    }
```

`schema()` would serialize `__guardrails__` into the schema document. The `AgentMixin.run()` loop would enforce behavioral limits (tool call counts, timeouts) at each iteration. Input/output guardrails would be enforced via JSON Schema validation before and after LLM calls. No existing agent protocol has schema-level guardrails -- this is a novel contribution.

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | **Medium** -- 1-2 weeks for schema serialization + enforcement hooks in AgentMixin.run(). |
| Impact | **High** -- Addresses the #1 cause of agent failure (unbounded behavior). Novel in the ecosystem. |
| Risk | **Low** -- Additive schema section. Enforcement is deterministic, not probabilistic. |
| Timeline | **2 weeks** |

---

### Proposition 8: Implement runtime DynamicClass agent proxies on the backend (mirror the frontend pattern)

> 🔧 **Proposition:** Port the frontend `prototype()` pattern to Python, enabling the backend to create typed agent proxy classes from remote Agent Card schemas at runtime -- discover an agent, generate a typed client, and invoke it with full validation.

**From the research:** The DynamicClass pattern -- reading a schema and creating a fully functional typed class at runtime -- is what agent proxies need. Instead of hand-coding client integrations per agent, you fetch the schema and get a typed proxy with validated method calls. This is the agent equivalent of how GraphQL clients auto-generate typed queries from schemas. (05-schema-as-agent-protocol.md, Section 11; 04-our-stack-relevance.md, Section 6)

**In our system:** `N3TX.js`'s `prototype()` (N3TX.js, line 663+) creates JavaScript classes from JSON Schema at runtime with typed getters/setters, method stubs, and actor-model messaging. `generate_join_model()` (proto_model.py, line 383) already creates Python model classes dynamically using `type()`. The backend pattern exists -- it just needs to target remote agent schemas instead of local join models.

**The idea:** A function `create_agent_proxy(schema)` that:
1. Fetches an Agent Card from `/.well-known/agent.json`
2. Parses skill definitions into typed method signatures
3. Creates a Python class with methods that validate inputs against `inputSchema`, call the remote agent via HTTP, and validate outputs against `outputSchema`
4. Registers the proxy in a local agent directory for discovery

```python
schema = fetch("https://agents.example.com/.well-known/agent.json")
ResearchProxy = create_agent_proxy(schema)
# ResearchProxy.deep_research(topic="...", depth="deep") validates and calls remote
```

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | **High** -- 3-4 weeks. Dynamic class creation, HTTP client, schema validation, error handling. |
| Impact | **High** -- Enables composing external agents into our system without hand-coded integrations. |
| Risk | **Medium** -- Dynamic class creation requires careful testing. Remote agent reliability varies. |
| Timeline | **4-6 weeks** |

---

### Proposition 9: Add cost and reliability metadata to schema method entries

> 🔧 **Proposition:** Extend schema method entries with `cost` (estimated tokens, price per call) and `reliability` (success rate, average latency) fields, enabling budget-aware and SLA-aware agent routing.

**From the research:** 96% of organizations report AI costs higher than expected at production scale. One documented incident cost $47K in 11 days from a recursive agent loop. No existing agent protocol carries cost or reliability metadata per tool/skill. Adding this to the schema enables orchestrators to make economically rational routing decisions: use the cheapest agent that meets the SLA, route away from unreliable agents, and enforce per-task budgets. (03-decision-framework.md, Section 6; 05-schema-as-agent-protocol.md, Section 6)

**In our system:** Schema method entries in `__n3tx_methods_json_signature__()` already carry `route`, `methods`, `parameters`, `returns`, and `access`. Adding `cost` and `reliability` is a dict extension -- no structural change.

**The idea:** The `@expose_tool` decorator (Proposition 3) would accept `cost` and `reliability` dicts. The schema generation would include them:

```json
"methods": {
  "web_search": {
    "parameters": {...},
    "returns": {...},
    "access": {"rule": "authenticated"},
    "cost": {"estimated_tokens": 500, "price_per_call_usd": 0.002},
    "reliability": {"success_rate": 0.99, "avg_latency_ms": 1200}
  }
}
```

An orchestrating agent could then: prefer cheaper tools when quality is equivalent, avoid tools with success rates below a threshold, and enforce per-task cost ceilings by summing estimated costs before invocation.

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | **Low** -- ~30 LOC in schema generation. Metadata is declarative, not behavioral. |
| Impact | **Medium** -- Enables cost-aware routing. Novel metadata that no protocol currently carries. |
| Risk | **Very Low** -- Additive schema fields. Consumers that don't understand them ignore them. |
| Timeline | **1-2 days** |

---

### Proposition 10: Build a schema registry with version negotiation for agent ecosystem participation

> 🔧 **Proposition:** Implement a lightweight schema registry that tracks schema versions, supports semver-based negotiation, and enables agents to discover compatible versions of our capabilities.

**From the research:** Agent schemas will evolve. Skills get added, parameters change, output formats update. Confluent's Schema Registry patterns (backward compatible: add optional fields; breaking: remove fields or change required params) apply directly. A2A includes a `version` field in Agent Cards. Schema negotiation -- client requests `version=2.x`, server returns `2.1.0` -- prevents integration breakage across agent networks. (05-schema-as-agent-protocol.md, Section 12)

**In our system:** `ProtoModel.schema()` generates immutable schemas cached per class. There is no versioning mechanism. Adding a version would mean tracking schema changes over time and serving compatible versions on request.

**The idea:** A `SchemaRegistry` service that:
- Assigns semver versions to schema snapshots
- Stores historical versions for backward compatibility
- Supports `Accept: application/agent-schema+json; version=2.x` header negotiation
- Returns the latest compatible version

This is the agent equivalent of API versioning -- essential for production multi-agent systems where different agents may be running different versions of their consumers.

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | **Medium** -- 2-3 weeks. Schema diffing, version storage, negotiation logic. |
| Impact | **Medium** -- Required for production multi-agent systems. Prevents integration breakage. |
| Risk | **Low** -- Additive infrastructure. Does not change existing schema generation. |
| Timeline | **3-4 weeks** |

---

## 🏗️ Proposition Map

### Quick Wins (Days -- low effort, immediate value)
| # | Proposition | Effort | Impact |
|---|------------|--------|--------|
| 2 | A2A Agent Card generation | 2-3 days | Medium |
| 3 | `@expose_tool` decorator | 2-3 days | Medium |
| 9 | Cost/reliability metadata in schema | 1-2 days | Medium |

### Strategic Investments (Weeks -- moderate effort, high value)
| # | Proposition | Effort | Impact |
|---|------------|--------|--------|
| 1 | MCP tool exposure | 2-4 weeks | High |
| 4 | Agent-specific ABAC rules | 1 week | High |
| 7 | Schema-carried guardrails | 2 weeks | High |
| 6 | Python Actor/Matrix port | 3-4 weeks | High |

### Moonshots (Months -- significant effort, transformative value)
| # | Proposition | Effort | Impact |
|---|------------|--------|--------|
| 5 | AgentMixin with LLM `run()` loop | 4-6 weeks | Very High |
| 8 | Runtime DynamicClass agent proxies | 4-6 weeks | High |
| 10 | Schema registry with version negotiation | 3-4 weeks | Medium |

---

## ⚠️ What NOT to Do

**1. Do not build a custom agent orchestration framework from scratch.** The OSS ecosystem (LangGraph, CrewAI, PydanticAI) handles orchestration well and improves monthly. In-house AI project success rate is 22%. Build the **bridge** that makes our unique schema capabilities accessible to these frameworks -- not a competing framework. The value is in our schema pipeline, not in reimplementing ReAct loops that LangGraph already has.

**2. Do not attempt multi-agent orchestration before single agents are proven.** The 17x error amplification in unstructured agent networks is well-documented. A system of 10 agents each at 95% reliability delivers only 60% end-to-end reliability (0.95^10). Propositions 5-6 (AgentMixin, Python Matrix) are tempting to start with but should come after Propositions 1-4 validate the schema-to-agent bridge.

**3. Do not make everything agentic.** 40% of agentic AI projects will be canceled by 2027 (Gartner) due to applying agent complexity to problems that do not require it. If a task is fully specifiable with deterministic rules, use a workflow engine. If it does not require multi-step reasoning, use a single LLM API call. Our schema pipeline has value for agents, but not every schema needs to become an agent.

---

## 🎯 Recommended Starting Point

**Start with Proposition 1 (MCP tool exposure) and Proposition 3 (`@expose_tool` decorator) in parallel.** Together, they take 2-4 weeks and achieve the single most valuable outcome: making every N3TX model accessible to the entire MCP ecosystem at zero LLM cost.

**Why these two first:**
- Proposition 1 creates immediate, tangible value -- any Claude, GPT, or Cursor session can interact with N3TX data
- Proposition 3 enriches tool definitions with descriptions that LLMs can read effectively, multiplying the value of Proposition 1
- Both are low-risk and fully reversible
- They validate the core hypothesis (our schemas are agent-ready) before committing to heavier investments

**Validation approach:**
1. Deploy MCP server adapter for the example app (Product, Comment, User, Like)
2. Connect Claude Desktop and attempt 10 natural language queries against N3TX data
3. Measure: tool call accuracy (target >90%), schema validation pass rate (target 100%), zero unintended side effects
4. If successful: proceed to Proposition 4 (agent ABAC rules) and Proposition 7 (guardrails) to harden the foundation before adding LLM-powered agents in Proposition 5

**Decision gate:** If MCP tool exposure does not achieve >90% tool call accuracy after prompt tuning, investigate whether the issue is schema quality (fix descriptions) or architectural (reassess approach). Do not proceed to Proposition 5 until Propositions 1-4 are validated.
