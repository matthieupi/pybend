# N3TX as Schema-Driven AI Agent Orchestration: Strategic Analysis Report

## For: CEO & Engineering Team
## Date: February 2026
## Prepared by: Architecture Team

---

### How to Read This Document

| Time | Path | Sections |
|------|------|----------|
| **5 min** | Core question + recommendation | Executive Summary, Section 7 (Recommendation) |
| **15 min** | Strategic picture | Add Sections 1, 2, 5 (Cost-Benefit), 6 (Decision Framework) |
| **30 min** | Technical depth | Add Sections 3 (Architecture), 4 (Our Assessment) |
| **45 min** | Full analysis with risks | Read everything, including Risk Register and Appendices |

---

## Executive Summary

> **Key Finding:** N3TX's schema-driven architecture already implements approximately 65% of what an AI agent framework requires. The Actor system IS agent messaging. The JSON Schema IS a capability manifest. `@expose_route` IS tool definition. ABAC IS agent permission scoping. The missing 35% --- LLM integration, prompt management, memory, and planning --- is additive, not architectural.

**The core question:** Should N3TX evolve into a schema-driven AI agent orchestration platform, and if so, how?

**The short answer:** Yes --- but not by building an agent framework. Build the *bridge*: auto-generate MCP-compatible tool definitions from existing model schemas, then let the mature orchestration ecosystem (LangGraph, CrewAI, Claude Agent SDK) handle the agent runtime. The unique value is the schema layer, not the orchestration layer.

### Key Findings

| Finding | Evidence | Source |
|---------|----------|--------|
| The agent market is real but volatile | $10.9B in 2026, but 40%+ projects will be canceled by 2027 | Gartner, Precedence Research [01] |
| JSON Schema is the universal agent contract | OpenAI, Anthropic, Google all use JSON Schema for tool definitions | All major provider docs [05] |
| N3TX's schema already produces agent-ready output | `ProtoModel.schema()` generates typed methods, access rules, validation constraints | Source code analysis [04] |
| The Actor model maps directly to agent patterns | Isolated state, message passing, supervision hierarchy | Actor.js, Matrix.js analysis [04] |
| Schema-driven MCP tools can be auto-generated | Translation from N3TX schema to MCP/OpenAI/Anthropic format is mechanical | 05-schema-as-agent-contract |
| The highest-ROI path is tool exposure, not agent building | Phase 0 (MCP server generation) costs 2-4 weeks, zero LLM API spend | 03-decision-framework |

### Recommendation

**Phase 0 (immediate, 2-4 weeks):** Auto-generate an MCP server from registered models. Every N3TX application becomes agent-accessible. Zero LLM cost. Maximum leverage.

**Phase 1 (months 2-3):** Build a single schema-aware agent prototype using an adopted orchestration framework. Validate the pattern with a constrained use case.

**Phase 2+ (months 4-9):** Expand only if Phase 1 metrics justify it. Consider Actor-model integration only if the architectural elegance proves measurably superior.

**What NOT to do:** Do not build a general-purpose agent orchestration framework. Do not make existing CRUD flows agentic. Do not deploy agents without observability.

---

## 1. What Is AI Agent Orchestration?

> **Key Finding:** An "agent" is an LLM operating in a loop --- observing, reasoning, acting, repeating --- rather than producing a single response. "Orchestration" is the coordination of multiple such agents toward a shared goal. The industry has converged on JSON Schema as the universal contract between agents and the tools they use.

### The Concept in Plain Language

Think of a traditional API as a vending machine: you press a button, you get a specific item. An AI agent is more like a junior employee with a desk full of tools. You give them a goal ("research competitor pricing and write a summary"), and they figure out which tools to use, in what order, handling unexpected results along the way.

**Orchestration** is what happens when you have a team of these employees. Someone needs to assign tasks, route information, handle it when one employee gets stuck, and synthesize the results. That coordination layer --- who talks to whom, who decides what, how failures are handled --- is orchestration.

### The Technical Picture

```
                    Traditional API                    AI Agent System
                    ===============                    ================

  Request  ──>  Fixed Handler  ──>  Response     Task  ──>  Agent Loop  ──>  Result
                                                              │
                                                     ┌───────┼───────┐
                                                     v       v       v
                                                   Think   Act    Observe
                                                     │       │       │
                                                     │    ┌──┴──┐    │
                                                     │    │Tool │    │
                                                     │    │Call │    │
                                                     │    └─────┘    │
                                                     └───────┬───────┘
                                                             │
                                                    Loop until done
                                                    or max iterations
```

The agent loop --- called ReAct (Reason + Act) in the literature --- is the dominant production pattern. Claude Code, GitHub Copilot, and most customer-facing AI assistants use this pattern: one LLM, a set of well-defined tools, and a loop [02-technical-deep-dive, Section 1.1].

### The Strategic Context

The agent orchestration market is at the Peak of Inflated Expectations on Gartner's Hype Cycle [01, Section 6.1]. Maximum hype, maximum funding, maximum vendor claims. The Trough of Disillusionment is expected mid-2026 to mid-2027, with 40%+ project cancellations [01, Section 5.1]. The Plateau of Productivity --- where agents reliably power enterprise software --- is projected for 2029+.

This timing matters for our strategy. We are not late. We are early enough to build the foundation and late enough to learn from others' mistakes.

---

## 2. Industry Landscape

> **Key Finding:** The market is consolidating fast. Four frameworks dominate (LangGraph, CrewAI, AutoGen, OpenAI Agents SDK), model providers are absorbing orchestration, and standards (MCP, A2A) are reducing the need for framework-specific abstractions. The surviving frameworks will be those providing value *beyond* model access.

### Market Numbers

| Metric | Value | Source |
|--------|-------|--------|
| Global AI agents market (2025) | $7.6-7.8B | Grand View Research, Precedence Research |
| Global AI agents market (2026, projected) | $10.9B | DemandSage |
| Global AI agents market (2033, projected) | $183B | Precedence Research |
| CAGR (2026-2033) | 49.6% | Precedence Research |
| AI agent startup funding (2024) | $3.8B (nearly 3x YoY) | Warmly AI |
| LangChain total funding | $260M at $1.25B valuation | Sacra |
| Enterprises with agents in production | 11% | Deloitte |
| Agentic AI projects expected canceled by 2027 | 40%+ | Gartner |
| GenAI pilots failing to deliver measurable ROI | 95% | MIT Project NANDA |

Sources: [01-industry-landscape, Sections 2, 5]

### The Big Four Frameworks

| Framework | Stars | Funding | Key Strength | Weakness |
|-----------|-------|---------|--------------|----------|
| **LangChain/LangGraph** | ~127K | $260M at $1.25B | Largest ecosystem, graph-based runtime | Complex abstractions, >1s latency per call |
| **CrewAI** | ~44.6K | $18M Series A | Role-based multi-agent, intuitive metaphor | Scaling walls after 6-12 months |
| **AutoGen + Semantic Kernel** (MS) | ~54.7K + ~27.2K | Microsoft-backed | Enterprise Azure integration | Still merging, GA targeting Q1 2026 |
| **OpenAI Agents SDK** | Growing | OpenAI-backed | Lowest barrier to entry | Hard vendor lock-in (OpenAI only) |

Source: [01-industry-landscape, Section 1.1]

### The Model-Provider Compression

A critical shift: model providers are releasing their own agent SDKs.

**Anthropic Claude Agent SDK** (March 2025, renamed September 2025) exposes the same infrastructure powering Claude Code. Supports MCP integration, Agent Skills, and tool use. The February 2026 release of Claude Opus 4.6 was specifically designed for agentic performance.

**OpenAI Agents SDK** replaced the experimental Swarm project. OpenAI announced the Assistants API will be sunsetted in 2026, pushing users toward the Agents SDK.

> **Implication:** When model providers ship their own frameworks, third-party orchestration layers face compression. The surviving frameworks will provide value *beyond* model access: workflow orchestration, state management, tool ecosystems, and schema enforcement [01, Section 1.2]. This is precisely the category where schema-driven frameworks can differentiate.

### Production Success Stories

| Company | What They Did | Result |
|---------|---------------|--------|
| **Salesforce Agentforce** | Sales/service automation agents | $900M AI+Data Cloud revenue in 6 months, 8K+ customers |
| **Major fintech** (unnamed) | Customer conversation agent | 2.3M conversations/mo, resolution 11min to 2min, ~$40M profit improvement |
| **Canva** | Internal information retrieval agent | 12+ hours/month saved per team |
| **Oracle** | Invoice processing agents | 70%+ reduction in processing time |

Source: [01-industry-landscape, Section 4.1]

### What Successful Deployments Share

The pattern is consistent across documented production deployments [01, Section 4.3]:

1. **Constrained domains** with clear success metrics
2. **Well-defined tool interfaces** (JSON Schema, typed parameters)
3. **Deterministic routing** where possible, LLM-driven only where necessary
4. **Human-in-the-loop** for high-stakes decisions
5. **Cost guardrails** (token budgets, timeout limits)
6. **Structured outputs** enforced at every boundary

The boring wins. Document processing, data reconciliation, compliance checks, invoice handling. Not autonomous decision-making. Not swarm intelligence. The work no one wants to do but everyone needs done.

### The Failure Rate

The data is stark [01, Section 5]:

- **40%+** of agentic AI projects will be canceled by 2027 (Gartner)
- **95%** of GenAI pilots fail to deliver measurable ROI (MIT Project NANDA)
- **62%** of organizations find GenAI harder to implement than expected (RSM)

The five failure modes: hallucination cascades, infinite loops (one documented $47,000 weekend bill), 3x cost overruns from reasoning tokens, brittle integrations (31.88% of LangChain developer questions relate to API churn), and the demo-to-production gap.

---

## 3. Technical Architecture Overview

> **Key Finding:** The agent ecosystem has converged on five architecture patterns, one universal tool protocol (MCP), and JSON Schema as the interface contract. The Actor model from distributed systems theory maps directly to multi-agent patterns --- and N3TX already implements an Actor system.

### Architecture Patterns Compared

| Pattern | Token Cost | Latency | Adaptability | Production Readiness | Best For |
|---------|-----------|---------|-------------|---------------------|----------|
| **ReAct** (single agent loop) | Medium | Medium | High | High | Dynamic tool use, research |
| **Plan-and-Execute** | Low | Low-Medium | Low | High | Structured workflows |
| **Supervisor** (hub-and-spoke) | Medium-High | Medium | Medium | High | Multi-domain tasks |
| **Assembly Line** (sequential) | Low | Medium | Low | High | Content pipelines, QA |
| **Swarm / Parallel** | High | Low (parallel) | Medium | Medium | Cross-checking, research |

Source: [02-technical-deep-dive, Sections 1, 5]

The overwhelming majority of production deployments use **single-agent ReAct** or **sequential pipelines**. Multi-agent systems report 45% faster problem resolution and 60% more accurate outcomes --- but at significantly higher cost and operational complexity [01, Section 3.2].

### MCP: The Standard That Won

The Model Context Protocol, open-sourced by Anthropic in November 2024 and donated to the Linux Foundation in December 2025, has become the de facto standard for tool integration [02, Section 3].

```
MCP Architecture
================

Host Application (Claude, Cursor, VS Code, Custom App)
    |
    |── MCP Client A ──> MCP Server (GitHub)
    |                     Tools: search, create
    |                     Resources: repos
    |
    |── MCP Client B ──> MCP Server (Postgres)
                          Tools: query, schema
                          Resources: tables
```

**Key adoption milestones:**
- Nov 2024: Anthropic announces MCP
- Mar 2025: OpenAI adopts MCP across ChatGPT desktop
- Apr 2025: Google confirms MCP support in Gemini
- Dec 2025: MCP donated to Linux Foundation (Agentic AI Foundation)
- Feb 2026: 10,000+ public MCP servers, 97M+ monthly SDK downloads

**Why MCP matters for N3TX:** MCP tools are defined via JSON Schema. N3TX's `ProtoModel.schema()` already generates JSON Schema with typed methods, parameters, and return types. The gap between N3TX's schema output and an MCP tool definition is a thin translation layer [05, Section 3].

### A2A: Agent-to-Agent Protocol

Google's A2A protocol (April 2025) fills the gap MCP does not cover: agent-to-agent interaction. While MCP connects agents to tools, A2A connects agents to other agents.

**Agent Cards** --- JSON documents at `/.well-known/agent.json` --- describe an agent's capabilities, supported tasks, and authentication requirements. N3TX's `ProtoModel.blueprint()` already aggregates all model schemas into a single document that is structurally equivalent [05, Section 7].

### The JSON Schema Convergence

Every major AI provider independently arrived at JSON Schema as the standard for tool definitions:

| Provider | Format | Mechanism |
|----------|--------|-----------|
| **OpenAI** | JSON Schema in `parameters` | Function calling + Structured Outputs (guaranteed adherence) |
| **Anthropic** | JSON Schema in `input_schema` | Tool use + MCP |
| **Google Gemini** | JSON Schema (OpenAPI subset) | Function declarations |
| **All MCP tools** | JSON Schema in `inputSchema` | Protocol-level enforcement |

Source: [05-schema-as-agent-contract, Section 1]

This convergence was not coordinated. JSON Schema uniquely satisfies four requirements: machine-parseable, validatable, self-documenting, and composable. **Any system that already produces rich JSON Schema is, structurally, already producing agent tool definitions.** The remaining work is formatting.

### Security Considerations

Agent security is categorically different from traditional application security [02, Section 11]:

```
Agent Attack Surface
====================
Prompt Injection  ── Direct (user crafts malicious input)
                  ── Indirect (malicious content in fetched data)
Tool Abuse        ── Agent tricked into destructive tool calls
Data Exfiltration ── Agent leaks sensitive context via tool calls
Privilege Escalation ── Agent accesses resources beyond scope
Confused Deputy   ── Agent follows instructions from untrusted sources
```

Defense requires five layers: input sanitization, tool permission scoping (least privilege), sandbox execution, output validation, and network egress control. **N3TX's ABAC system provides a structural advantage here** --- access rules are already serialized into the schema, giving agents machine-readable permission boundaries without hallucinating what they can do.

Only **34%** of enterprises have AI-specific security controls in place. Prompt injection is the single most exploited vulnerability in AI agent systems as of 2026. Trail of Bits demonstrated that prompt injection can escalate to remote code execution in agents with code execution capabilities (October 2025) [02, Section 11.2].

### The Actor Model Parallel

The actor model, originated by Carl Hewitt in 1973, is a remarkably close analog to multi-agent AI systems [02, Section 12]:

| Actor Model Concept | Agent System Equivalent |
|--------------------|------------------------|
| **Actor** | Agent (LLM + tools + state) |
| **Message** | Task / prompt / observation |
| **Mailbox** | Task queue / context buffer |
| **Isolated state** | Agent's context window + memory |
| **Supervision tree** | Supervisor agent pattern |
| **Behavior** | Agent's system prompt + tools |
| **Location transparency** | MCP/A2A protocol abstraction |

N3TX's frontend already implements this pattern. `Actor.js` provides isolated state, address-based identity, message-driven execution, supervision hierarchy via `spawn()`, and hierarchical routing. `Matrix.js` provides the message bus. `TX.js` provides the message envelope with name, source, target, data, meta, and timestamp.

The mapping is not an analogy --- it is structural identity.

---

## 4. Our Current Architecture Assessment

> **Key Finding:** N3TX implements approximately 65% of what an agent framework requires. The existing primitives --- Actor messaging, schema generation, typed methods, ABAC authorization, DynamicClass creation --- map directly to agent concepts. The missing 35% is the AI-specific layer: LLM client, prompt management, memory, planning, and observability.

### What We Have: Component-by-Component Inventory

This assessment is based on direct analysis of the source files.

| Agent Requirement | N3TX Component | File | Coverage |
|-------------------|-----------------|------|----------|
| Agent identity & addressing | `Actor.addr`, `N3TX.$id` | `Actor.js`, `N3TX.js` | 95% |
| Agent messaging | `Actor.inbox/send`, `TX`, `Matrix` | `Actor.js`, `Matrix.js`, `TX.js` | 80% |
| Agent state schema | `ProtoModel`, JSON Schema generation | `proto_model.py` | 90% |
| Tool definitions | `@expose_route`, `__n3tx_methods_json_signature__` | `decorators.py`, `proto_model.py` | 75% |
| Tool parameter validation | Pydantic models, `make_custom_post` type parsing | `routes_fastapi.py` | 85% |
| Permission scoping | `authorize` package (ABAC) | `rules.py` | 90% |
| State persistence | `StorableMixin`, SQLite backend | `storable_mixin.py` | 85% |
| Runtime class creation | `prototype()` in N3TX.js | `N3TX.js` | 70% |
| Event subscriptions | `Observable` mixin | `Observable.js` | 80% |
| API generation | `register_routes()` | `routes_fastapi.py` | 90% |
| Schema discovery | `N3TX.SCHEMA()`, `GET /{ClassName}`, `blueprint()` | `N3TX.js`, `proto_model.py` | 90% |
| Self-describing responses | `model_dump(response=True)` injects `$schema`/`$id` | `proto_model.py` | 95% |

Source: [04-our-stack-relevance, Section 8]

### What We Lack: Gap Analysis

| Missing Capability | Complexity | Proposed Approach |
|-------------------|-----------|-------------------|
| **LLM integration** (client, streaming, retries, token counting) | Medium | New `LLMMixin`, analogous to `StorableMixin` |
| **Prompt management** (system prompts, templates, versioning) | Small | `__prompt__` dict on models, like `__ui__` |
| **Conversation memory** (short/medium/long-term) | Medium | `AgentMemory` as a `ProtoModel` with `StorableMixin` |
| **Planning / reasoning loop** (ReAct, Plan-and-Execute) | Large | Core innovation space; Actor messaging provides the substrate |
| **Tool execution sandbox** | Medium | `@expose_tool(sandbox=True)` → subprocess with resource limits |
| **Cost tracking / budgets** | Small-Medium | Extend `TX` with cost metadata; per-agent budgets |
| **Agent observability** (tracing, logging, cost dashboards) | Medium | Structured `AgentTrace` model; TX already has timestamps |
| **Multi-agent coordination** | Large | Actor/Matrix pattern provides the foundation |

Source: [04-our-stack-relevance, Section 9]

### Code-Level Evidence: Schema to Tool Definition

The translation from N3TX's existing schema output to agent tool definitions is mechanical. Here is what `ProtoModel.schema()` already produces for a model method (from `proto_model.py`, lines 140-188):

```python
@classmethod
def __n3tx_methods_json_signature__(cls) -> dict:
    methods = {}
    for method_name in dir(cls):
        method = getattr(cls, method_name)
        if not (callable(method) and hasattr(method, '__endpoint__')):
            continue
        sig = inspect.signature(method)
        type_hints = get_type_hints(method, ...)
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

This already produces typed parameter schemas and return type schemas. Converting to MCP format requires [05, Section 5]:

1. Rename `parameters` to `properties` (wrap in `type: object`)
2. Extract `description` from the method docstring
3. Compute `required` from parameters without defaults
4. Drop HTTP-specific fields (`route`, `methods`, `scope`)

That is a thin adapter function --- not an architectural change.

### Code-Level Evidence: Actor as Agent Foundation

From `Actor.js` (lines 11-338), the Actor base class provides:

```javascript
export default class Actor {
    #addr;          // Unique identity → agent ID
    #parent;        // Supervision hierarchy → orchestrator
    #children;      // Managed actors → sub-agents

    inbox(event) {  // Message handler → task receiver
        return Actor._inbox.call(this, event);
    }

    send(event) {   // Message dispatch → task delegation
        // Routes locally first, bubbles to Matrix
    }

    spawn(addr, ActorClass, ...args) {  // Create child → spawn sub-agent
        const child = new ActorClass(addr, ...args);
        this.#children.set(addr, child);
        return child;
    }
}
```

From `Matrix.js` (lines 11-81), the message bus provides:

```javascript
export class Matrix extends Actor {
    inbox(event) {
        let tx = event instanceof TX ? event : new TX(event);
        let targetAddr = tx.target.split('/')[0];

        if (tx.name === E.connect) {
            tx = this.connect(tx.source, tx.target);    // Establish channel
        } else if (this.children.has(targetAddr)) {
            tx = this.children.get(targetAddr).inbox(tx.repr());  // Local routing
        } else {
            tx = this.remote.send(tx);                   // Remote forwarding
        }
        return tx;
    }
}
```

This is the agent communication bus --- routing messages between addressed actors with local-first delivery and remote forwarding. The `TX` message envelope carries `name`, `source`, `target`, `data`, `meta`, and `timestamp`: everything an agent message needs.

### Code-Level Evidence: ABAC as Agent Safety

From `rules.py` (lines 13-279), the authorization system provides composable rules:

```python
class AccessRule(ABC):
    def evaluate(self, ctx: AccessContext) -> bool: ...
    def sql_filter(self, ctx) -> Optional[Tuple[str, List[Any]]]: ...
    def to_dict(self) -> Dict[str, Any]: ...   # Serializable to JSON
    def __or__(self, other): return OrRule(self, other)
    def __and__(self, other): return AndRule(self, other)
    def __invert__(self): return NotRule(self)
```

With leaf rules: `ANYONE`, `AUTHENTICATED`, `OWNER`, `ROLE(*roles)`, and `Where(**conditions)`. These compose logically:

```python
__access__ = {
    'update': OWNER | ROLE('admin'),
    'publish': OWNER & Where(status='draft'),
}
```

Critically, the `authorize` package has **zero N3TX imports** --- it is a standalone ABAC library. Adding agent-specific rules (e.g., `BUDGET(remaining__gt=0)`, `CAPABILITY('web_search')`, `DELEGATION_DEPTH(max=3)`) requires zero changes to the core engine. Just new `AccessRule` subclasses.

These rules serialize to JSON via `to_dict()` and are embedded in the schema. An agent reading the schema knows what it can and cannot do --- without hallucinating permissions.

### Unique Advantages

No existing agent framework provides what a schema-driven approach would:

| Capability | Schema-Driven (N3TX) | Generic Framework + Agent |
|-----------|----------------------|--------------------------|
| Time to expose tools to agents | Days (auto-generate from schema) | Weeks (hand-write each tool) |
| Tool accuracy (hallucination risk) | Very low (schema-validated) | Medium (prompt-dependent) |
| Permission enforcement | Automatic (schema carries rules) | Manual (duplicate in agent config) |
| New model = new tools | Automatic (deploy, restart) | Manual (update agent config) |
| Relationship navigation | Automatic (`$defs`, FK hydration) | Manual (encode in prompts) |
| Schema versioning | Automatic (schema is code) | Manual (update tool docs) |
| Human review forms | Generated from schema (Formidable) | Custom UI per tool |
| Schema evolution | Agents adapt automatically at next fetch | Manual tool definition updates |

Source: [04, Section 11; 05, Section 12]

### Honest Limitations

The assessment is not all favorable. Key limitations:

1. **The Actor system is frontend-only and synchronous.** Agent execution requires async processing (LLM calls take seconds to minutes). A backend Actor equivalent does not exist yet.

2. **No backpressure mechanism.** When an orchestrator spawns 10 agents each making LLM calls, rate limiting is needed. The current Actor has no flow control.

3. **No lifecycle hooks.** `on_start()`, `on_stop()`, `on_error()` --- the Actor has `spawn()` but no lifecycle management beyond construction.

4. **No distributed bus.** The Matrix is single-instance. Multi-process or multi-server agent communication would require architectural extension.

5. **The schema is powerful but not infinite.** It carries types, methods, access rules, and UI hints --- but it does not carry behavioral semantics (e.g., "this agent prefers exhaustive research over quick answers"). That is prompt engineering territory.

---

## 5. Cost-Benefit Analysis

> **Key Finding:** Agent systems are expensive to run and expensive to debug. Token costs for agentic workflows are 10-50x higher than single-call LLM use. The cost-effective path is exposing your system as tools (zero LLM cost) before consuming LLM APIs for orchestration.

### LLM API Pricing (February 2026)

| Model | Input (per 1M tokens) | Output (per 1M tokens) | Cache Hit Discount |
|-------|:---:|:---:|:---:|
| GPT-4o | $2.50 | $10.00 | 50% |
| GPT-5 | $10.00 | $30.00 | 50% |
| Claude Sonnet 4.5 | $3.00 | $15.00 | 90% |
| Claude Opus 4.6 | $5.00 | $25.00 | 90% |
| DeepSeek V3.2 | $0.14 | $0.28 | - |
| Gemini 2.0 Flash | $0.10 | $0.40 | - |

Source: [03-decision-framework, Section 5]

### Token Usage by Agent Pattern

| Pattern | Input Tokens | Output Tokens | Cost (Claude Sonnet) | Cost (GPT-4o) |
|---------|:---:|:---:|:---:|:---:|
| Single LLM call (no agent) | 2,000 | 500 | $0.014 | $0.010 |
| Single agent + 3 tool calls | 15,000 | 3,000 | $0.090 | $0.068 |
| Multi-agent (3 agents, 5 turns) | 80,000 | 15,000 | $0.465 | $0.350 |
| Complex orchestration (5 agents, 10+ turns) | 300,000 | 50,000 | $1.650 | $1.250 |
| Recursive/research (unbounded) | 1,000,000+ | 200,000+ | $6.00+ | $4.50+ |

**The 10-50x multiplier is real.** A task costing $0.01 as a single call can cost $0.50-$6.00 as an agentic workflow.

### Monthly Cost Projections at Scale

| Scenario | Tasks/Day | Cost/Task | Monthly | Annual |
|----------|:---------:|:---------:|:-------:|:------:|
| Customer support triage (single agent) | 1,000 | $0.09 | $2,700 | $32,400 |
| Data enrichment pipeline (multi-agent) | 500 | $0.47 | $7,050 | $84,600 |
| Code review agent (complex) | 200 | $1.65 | $9,900 | $118,800 |
| Research assistant (recursive) | 50 | $6.00 | $9,000 | $108,000 |
| **Combined workload** | **1,750** | - | **$28,650** | **$343,800** |

### Investment Required by Phase

| Phase | What | Engineering Weeks | LLM API Cost | Infrastructure |
|-------|------|:-----------------:|:------------:|:--------------:|
| **Phase 0: MCP Server** | Auto-generate tools from schemas | 2-4 | $0 | $0 |
| **Phase 1: Single Agent** | Schema-aware agent prototype | 4-6 | $200-500/mo | $100-500/mo |
| **Phase 2: Specialized Agents** | 2-3 bounded-scope agents | 6-10 | $1,000-3,000/mo | $500-2,000/mo |
| **Phase 3: Multi-Agent** | Coordinated workflows | 8-16 | $3,000-10,000/mo | $2,000-5,000/mo |

### Build vs. Adopt Cost Comparison

| Component | Adopt (integration work) | Build from scratch |
|-----------|:---:|:---:|
| State machine / graph execution | 0 weeks (provided) | 8-16 weeks |
| Error recovery / checkpointing | 0 weeks (provided) | 4-8 weeks |
| Multi-agent coordination | 0 weeks (provided) | 8-16 weeks |
| Schema-to-tool bridge | 2-4 weeks | 2-4 weeks |
| MCP server generation | 2-4 weeks | 2-4 weeks |
| Permission-aware filtering | 1-2 weeks | 1-2 weeks |
| Observability / tracing | 0-2 weeks (provided) | 6-12 weeks |
| **Total** | **5-12 weeks** | **31-62 weeks** |

The hybrid approach (adopt orchestration, build schema bridge) costs 5-12 engineering weeks. Full custom costs 31-62 weeks --- 6x more for capabilities that already exist as battle-tested open source [03, Section 4].

### Expected Returns

The ROI depends entirely on use case selection. The research is clear on where agents pay for themselves [01, Section 4.2]:

| Domain | Typical Savings | Example |
|--------|:--------------:|---------|
| Document processing | 70%+ reduction in processing time | Oracle invoice agents |
| Customer support triage | 80%+ reduction in resolution time | Major fintech (11min to 2min) |
| Data reconciliation | 40-60% efficiency gain | Enterprise data pipelines |
| Testing / QA automation | 40% faster feature shipping | Doctolib |

### Hidden Costs

1. **Observability platform:** $500-5,000/month (LangSmith, Langfuse, Arize)
2. **Evaluation suite maintenance:** Ongoing engineering time for golden test sets
3. **Prompt engineering iteration:** Non-trivial, non-one-time effort
4. **Security review:** Every tool an agent can access requires review
5. **Cultural shift:** Testing becomes statistical, not deterministic [03, Section 7]

### Cost Optimization Strategies

1. **Prompt caching:** 90% savings on cache hits (Anthropic). Schema content is highly cacheable.
2. **Model routing:** DeepSeek/Gemini Flash for simple tasks ($0.10-0.28/1M tokens), Opus for complex reasoning ($5-25/1M tokens).
3. **Agent budgets:** Hard per-task token limits. Kill runaway loops.
4. **Deterministic fallbacks:** If agent cannot complete in N turns, fall back to rules.
5. **Batch processing:** 50% discount for non-real-time workloads (OpenAI Batch API).

---

## 6. Decision Framework

> **Key Finding:** Most CRUD workflows should never be agentic. Agents add value at the edges --- unstructured input, adaptive decision-making, natural language interfaces --- not at the core data operations that schema-driven code already handles perfectly.

### When to Use Agents vs. Traditional Code

```
                    Is the task fully specifiable
                    with deterministic rules?
                           |
                    +------+------+
                    |             |
                   YES            NO
                    |             |
             Use traditional    Does the task involve
             code/workflows     unstructured data or
                                natural language?
                                     |
                              +------+------+
                              |             |
                             YES            NO
                              |             |
                        Does it require    Is the decision space
                        multi-step         too large for rules?
                        reasoning?              |
                              |          +------+------+
                       +------+------+   |             |
                       |             |  YES            NO
                      YES            NO  |             |
                       |             |  Use agents    Use traditional
                  Use multi-agent   Use single        code with ML
                  orchestration     LLM call          classification
                                   (no agent)
```

Source: [03-decision-framework, Section 2]

### The Seven Anti-Patterns

| Anti-Pattern | Why It Fails | When It IS Appropriate |
|-------------|-------------|----------------------|
| **Agentic CRUD** | Schema-driven forms are faster, cheaper, deterministic | When input is unstructured (parse email into product) |
| **Agent as Router** | Switch statements are infinitely cheaper than LLM calls | When routing requires NL understanding |
| **Agentic Everything** | 40% project cancellation rate from this mistake | Never |
| **Agents Without Budgets** | $47K weekend bills | Never |
| **Agents for Low-Latency Paths** | LLM calls take 200-500ms minimum | Never (for <100ms SLAs) |
| **Agents Without Observability** | Cannot debug non-deterministic systems | Never |
| **LLM Where Classification Suffices** | A classifier costs $0.0001/task; an agent costs $0.09/task | When the decision requires multi-step reasoning |

Source: [03, Section 8]

### Five-Question Decision Filter

Before adding an agent to any workflow:

1. **Can a deterministic rule handle this?** If yes, stop. Your schema-driven CRUD is already optimal.
2. **Can a simple classifier handle this?** If yes, use classification, not an agent. 900x cheaper.
3. **Does this require multi-step reasoning?** If no, use a single LLM call, not an agent.
4. **Is the cost per task justified by the value delivered?** Calculate explicitly against the tables in Section 5.
5. **Can you observe and debug it?** If no, you are not ready.

### Decision Tree: Agent Integration for N3TX

```
We have a schema-driven framework.
Where do agents add value?
    |
    +── Expose our schemas AS tools for external agents (Phase 0)
    |   Cost: 2-4 weeks. Zero LLM spend.
    |   Value: Any MCP-compatible agent can use our system.
    |   Risk: Near zero.
    |   TRIGGER: Proceed immediately.
    |
    +── Build agents that USE our schemas (Phase 1+)
    |   Cost: 4-6 weeks + ongoing LLM API costs.
    |   Value: NL query interface, data import, adaptive workflows.
    |   Risk: Moderate.
    |   TRIGGER: When a customer requests NL interaction with entities,
    |            OR when a workflow requires unstructured input processing,
    |            OR when manual data entry costs exceed $5K/month.
    |
    +── Multi-agent orchestration (Phase 3+)
        Cost: 8-16 weeks + significant LLM API costs.
        Value: Complex cross-entity workflows, autonomous operations.
        Risk: High.
        TRIGGER: When single-agent task completion rate exceeds 95%,
                 AND cost per task is within 120% of budget,
                 AND observability platform is operational.
```

### Measurable Phase Triggers

| Phase | Trigger Metric | Threshold |
|-------|---------------|-----------|
| Phase 0 -> Phase 1 | Customer demand for NL interface | 3+ customer requests OR strategic initiative |
| Phase 1 -> Phase 2 | Single-agent task completion rate | > 90% on evaluation suite |
| Phase 2 -> Phase 3 | Per-agent cost efficiency | Cost/task within 120% of budget, declining trend |
| Phase 3 -> Phase 4 (autonomous) | Hallucination rate | < 2% on production data |
| Any phase -> Pause | Monthly LLM spend | Exceeds 150% of budget for 2 consecutive months |

---

## 7. Recommendation

> **Key Finding:** The optimal strategy is "adopt for orchestration, build for integration." Our unique value is the schema layer --- the ability to auto-generate typed, permission-aware, self-describing tool definitions from model definitions. We should not compete with LangGraph on orchestration; we should be the best thing that plugs into it.

### The Phased Approach

**Phase 0: Make N3TX Agent-Accessible (Weeks 1-4)**

Build an MCP server generator that reads `registered_models`, converts each model's schema into MCP tool definitions, and serves them via the MCP protocol. Deliverables:

- `schema_to_mcp_tools()` function: converts `ProtoModel.schema()` output to MCP format
- MCP server with `tools/list` (returns all model tools) and `tools/call` (routes to existing FastAPI endpoints)
- CRUD operations exposed as tools with permission enforcement
- Custom `@expose_route` methods become callable tools
- `GET /.well-known/agent.json` for A2A discovery

**Cost:** 2-4 engineering weeks. Zero LLM API cost (we are a tool provider, not a consumer).

**Value:** Any MCP-compatible agent --- Claude Code, Cursor, ChatGPT, custom --- can now interact with any N3TX application through typed, validated, permission-aware tools. This alone is a significant product capability.

**Phase 1: Single Agent Prototype (Weeks 5-10)**

Build a single schema-aware agent using an adopted orchestration framework (recommend LangGraph for state management or Claude Agent SDK for simplicity). Use cases:

- Natural language query interface: "Show me all products over $50 created this week"
- Data import assistant: "Parse this CSV and create products from it"
- Support bot: "Find the user's recent orders and summarize their account"

**Cost:** ~$200-500/month LLM API cost at prototype scale. 4-6 engineering weeks.

**Phase 2: Specialized Agents (Weeks 11-20)**

Multiple single-purpose agents, each with bounded scope:

- Data Quality Agent: scans entities for inconsistencies
- Onboarding Agent: guides multi-step entity creation
- Report Agent: generates summaries from entity data

**Key constraint:** Independent agents. No multi-agent coordination. Each has its own token budget.

**Phase 3: Multi-Agent Orchestration (Weeks 21-36)**

Only after Phase 2 agents are stable, measured, and cost-effective. Prerequisites:

- Observability platform operational
- Cost monitoring and alerting active
- Evaluation suites measuring completion, accuracy, cost
- Human-in-the-loop process for high-stakes operations

**Phase 4: Autonomous Workflows (Months 9+)**

Agents operating with minimal human oversight. Requirements:

- Task completion rate > 95%
- Cost per task within 110% of target
- Hallucination rate < 2%
- Full audit trail for every decision
- Human escalation path for low-confidence outputs

### What NOT to Do

1. **Do not build a general-purpose agent orchestration framework.** LangGraph has 127K stars, $260M in funding, and years of production hardening. Our advantage is not orchestration --- it is the schema layer.

2. **Do not make existing CRUD flows agentic.** They work. They are fast. They are deterministic. They cost nothing. Adding agents to CRUD adds $0.09/operation minimum, 200-500ms latency, and hallucination risk for zero benefit.

3. **Do not deploy agents without observability.** 96% of organizations report generative AI costs higher than expected at production scale [03, Section 6]. You cannot manage what you cannot see.

4. **Do not commit to a single LLM vendor.** Multi-model support is a requirement. Today's best model may not be tomorrow's best model. The schema bridge should work with any provider.

5. **Do not skip the cost analysis.** Run the numbers from Section 5 with your actual task volumes before committing engineering resources.

### Review Cadence

| Checkpoint | When | Decision |
|-----------|------|----------|
| Phase 0 completion review | Week 4 | Did MCP tools generate correctly? Can Claude Code use them? Proceed to Phase 1? |
| Phase 1 prototype review | Week 10 | Task completion rate? Cost per task? User feedback? Expand or pivot? |
| Monthly cost review | Every month | LLM spend vs. budget? Cost trends? Optimization opportunities? |
| Quarterly strategy review | Every quarter | Market landscape changes? New protocols? Competitive moves? |

---

## 8. Risk Register

> **Key Finding:** The highest-probability risks are cost overruns and debugging complexity. The highest-impact risks are security vulnerabilities and hallucination cascades. Schema-driven architecture mitigates several risks that other approaches face unprotected.

### Probability-Impact Matrix

```
                    IMPACT
                    Low        Medium       High         Critical
              +----------+-----------+-----------+------------+
    High      |          | Reproduci-| Cost      | Security   |
              |          | bility    | runaway   | (prompt    |
P             |          | failure   |           | injection) |
R   Medium    |          | Latency   | Vendor    | Data       |
O             |          | degradati-| dependency| leakage    |
B             |          | on        |           |            |
A   Low       |          |           | Framework | Hallucina- |
B             |          |           | obsole-   | tion       |
              |          |           | scence    | cascades   |
    Very Low  |          |           |           |            |
              +----------+-----------+-----------+------------+
```

### Detailed Risk Register

| # | Risk | Prob. | Impact | Mitigation | Residual | Schema Advantage |
|---|------|:-----:|:------:|------------|:--------:|-----------------|
| R1 | **Hallucination** --- agent fabricates operations or data | High | Critical | Schema validation, tool whitelisting, output verification against Pydantic models | Medium | Schema provides ground truth; agent cannot hallucinate operations that do not exist in schema |
| R2 | **Cost runaway** --- recursive loops burn API budget | High | High | Per-task token budgets, circuit breakers, hard spending limits with alerts | Low | N/A (cost is LLM-specific) |
| R3 | **Debugging complexity** --- non-deterministic multi-agent systems are hard to trace | High | High | Observability from day one; structured tracing; deterministic fallbacks; staged rollout | Medium | TX message envelope already carries timestamps and routing metadata |
| R4 | **Prompt injection** --- user input or fetched data manipulates agent behavior | High | Critical | Input sanitization, tool permission scoping via ABAC, sandboxed execution, output validation | Medium | ABAC rules are machine-enforced at the route layer, not prompt-dependent |
| R5 | **Vendor dependency** --- LLM API changes, pricing shifts, provider outages | Medium | High | Multi-model abstraction layer, open-source model fallbacks (DeepSeek, Llama) | Low | Schema bridge works with any provider |
| R6 | **Reproducibility failure** --- same input produces different outputs | High | Medium | Temperature 0, seed parameters, output logging, deterministic fallbacks | Medium | Schema validation catches structural deviations even if content varies |
| R7 | **Data leakage** --- PII sent to external LLM | Medium | Critical | Field-level access rules in schema, data masking before LLM calls, local models for sensitive data | Low | Schema `access` rules identify sensitive fields (`access.view: admin`) |
| R8 | **Latency degradation** --- agent tasks take too long for user expectations | Medium | Medium | Async patterns, prompt caching (90% savings), model routing, SLA monitoring | Low | N/A |
| R9 | **Framework obsolescence** --- chosen orchestration framework declines | Medium | High | Keep orchestration layer thin; schema bridge is framework-agnostic; evaluate alternatives quarterly | Low | Schema is the stable layer; orchestration is swappable |
| R10 | **Team skill gap** --- engineering team lacks LLMOps experience | Medium | Medium | Upskill existing engineers (1-2 AI-specialized roles needed); evaluation pipelines as forcing function | Medium | Schema-driven approach reduces surface area of AI-specific code |

### Financial exposure from hallucination

Financial losses from hallucination-related incidents exceed $250M annually across the industry, with each enterprise employee costing approximately $14,200/year in hallucination mitigation [03, Section 6]. Schema-driven mitigation provides a structural advantage: the schema IS the ground truth. The agent does not need to guess what fields exist, what types they are, or what operations are available. RAG-based grounding (which reduces hallucination rates by 71%) becomes trivially effective when the retrieval source is a deterministic, always-current schema.

### EU AI Act Compliance

The EU AI Act entered into force August 1, 2024. Full applicability for high-risk systems: August 2, 2026 [03, Section 12]. Penalties up to EUR 35 million or 7% of global annual turnover.

Schema-driven compliance advantage:
- Every operation is typed and logged through `register_routes()`
- Access rules are declarative, version-controlled, and auditable
- No hidden operations (schema is the single source of truth)
- Field-level data classification via schema access rules

---

## 9. Appendices

### Appendix A: Glossary

| Term | Definition |
|------|-----------|
| **Agent** | An LLM operating in a loop (observe, reason, act, repeat) rather than producing a single response |
| **MCP** | Model Context Protocol --- Anthropic's open standard for connecting LLM applications to external tools and data |
| **A2A** | Agent-to-Agent Protocol --- Google's standard for inter-agent communication and capability discovery |
| **ReAct** | Reason + Act --- the dominant single-agent pattern (think, call tool, observe result, repeat) |
| **ABAC** | Attribute-Based Access Control --- N3TX's authorization system with composable rules |
| **DynamicClass** | A runtime-generated JavaScript class created from a JSON Schema by `prototype()` in N3TX.js |
| **ProtoModel** | N3TX's base model class that generates JSON Schema, injects StorableMixin, and produces method signatures |
| **Tool** | A function an agent can invoke, defined by a JSON Schema describing its parameters and return type |
| **Structured Outputs** | Model responses constrained to match a JSON Schema exactly (guaranteed at the token level) |
| **Agent Card** | A JSON document (at `/.well-known/agent.json`) describing an agent's capabilities for A2A discovery |
| **Hallucination** | An LLM generating plausible but factually incorrect information |
| **Token** | The atomic unit of text processing for LLMs; roughly 0.75 words per token |
| **Prompt Injection** | An attack where malicious instructions override an agent's intended behavior |
| **Orchestration** | The coordination of multiple agents toward a shared goal --- task routing, error handling, result synthesis |
| **Schema drift** | When tool definitions and actual service behavior diverge; a top cause of broken automations |

### Appendix B: Case Study --- Salesforce Agentforce

Salesforce launched Agentforce for sales and service automation, reaching 8,000+ customers within six months and generating $900M in combined AI + Data Cloud revenue. The deployment uses:

- Constrained domain (sales/service workflows with known patterns)
- Structured tool interfaces (typed Salesforce APIs)
- Human-in-the-loop for complex cases
- Cost guardrails with per-transaction limits

Relevance to N3TX: Salesforce's success came from constraining agents to well-defined tool interfaces --- exactly what schema-driven tool generation provides automatically.

### Appendix C: Case Study --- The $47,000 Recursive Loop

A documented production incident: a multi-agent research tool built on an open-source stack entered a recursive loop where two agents talked to each other non-stop for 11 days before anyone noticed. The API bill: $47,000 [03, Section 6].

Prevention pattern:
```python
class AgentDispatcher:
    MAX_TURNS_PER_TASK = 10
    MAX_TOKENS_PER_TASK = 50_000
    MAX_COST_PER_TASK_USD = 0.50

    def execute(self, task):
        for turn in range(self.MAX_TURNS_PER_TASK):
            result = self.agent.step(task)
            if result.done or self.budget_exceeded():
                break
        if not result.done:
            return self.deterministic_fallback(task)
```

### Appendix D: N3TX Schema to MCP Tool Translation

A concrete example showing the mechanical translation from N3TX's schema output to MCP tool format:

**N3TX schema (existing output from `ProtoModel.schema()`):**
```json
{
  "methods": {
    "comment": {
      "route": "/comment",
      "methods": ["POST"],
      "scope": "instancemethod",
      "parameters": {
        "comment": {
          "$ref": "#/$defs/Comment",
          "properties": {
            "name": {"type": "string", "minLength": 1, "maxLength": 500},
            "description": {"type": "string", "default": ""}
          },
          "required": ["name"]
        }
      },
      "returns": {"type": "string"},
      "access": {"rule": "authenticated"}
    }
  }
}
```

**MCP tool (generated output):**
```json
{
  "name": "products_comment",
  "title": "Add Comment to Product",
  "description": "Add a comment to the product.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "product_id": {
        "type": "integer",
        "description": "ID of the product to comment on"
      },
      "comment": {
        "type": "object",
        "properties": {
          "name": {"type": "string", "minLength": 1, "maxLength": 500},
          "description": {"type": "string", "default": ""}
        },
        "required": ["name"]
      }
    },
    "required": ["product_id", "comment"]
  },
  "annotations": {
    "readOnlyHint": false,
    "destructiveHint": false
  }
}
```

The translation adds `product_id` for instance methods, wraps parameters in `inputSchema`, extracts description from the method docstring, and maps access rules to MCP annotations. The input schema properties come directly from N3TX's existing schema output.

### Appendix E: Proposed Entity vs. Agent Side-by-Side

**Today: A N3TX Entity**
```python
class Product(ProtoModel):
    __tablename__ = 'products'
    __storable__ = True
    __access__ = {
        'read': ANYONE,
        'create': AUTHENTICATED,
        'update': OWNER | ROLE('admin'),
    }

    name: str = Field(min_length=1, max_length=200)
    price: float = Field(gt=0)
    description: str = Field(default='')

    @expose_route('/comment', methods=['POST'])
    def comment(self, comment: Comment, user: User = None) -> str:
        comment.user_owner = user.id if user else 1
        comment.__owner__ = self
        comment.save()
        return comment.model_dump_json()
```

From this: CRUD API + JSON Schema + database + web UI. Zero config.

**Future: A N3TX Agent**
```python
class ResearchAgent(ProtoModel, AgentMixin):
    __tablename__ = 'research_agents'
    __storable__ = True
    __agent__ = True
    __llm__ = {'provider': 'anthropic', 'model': 'claude-sonnet-4', 'temperature': 0.3}
    __prompt__ = {'system': "You are a research analyst..."}
    __access__ = {'invoke': AUTHENTICATED & BUDGET(remaining__gt=0)}

    topic: str = Field(default="")
    report: str = Field(default="")
    budget_remaining: float = Field(default=1.0)

    @expose_tool(description="Search the web")
    def web_search(self, query: str) -> list[dict]: ...

    @expose_route('/research', methods=['POST'])
    async def research(self, topic: str, user: User = None) -> str:
        result = await self.run(task=f"Research: {topic}")
        return result
```

From this: everything above PLUS LLM tool definitions + agent loop + cost tracking. Same patterns: field definitions, access rules, exposed methods, storage, schema generation.

### Appendix F: Source References

**Research Documents:**
- [01] `/workspace/.traces/research/ai-agents/01-industry-landscape.md` --- Market data, framework comparison, success/failure stories
- [02] `/workspace/.traces/research/ai-agents/02-technical-deep-dive.md` --- Architecture patterns, MCP, memory, security, Actor model
- [03] `/workspace/.traces/research/ai-agents/03-decision-framework.md` --- Decision criteria, cost analysis, anti-patterns, roadmap
- [04] `/workspace/.traces/research/ai-agents/04-our-stack-relevance.md` --- Architectural mapping, coverage analysis, gap analysis
- [05] `/workspace/.traces/research/ai-agents/05-schema-as-agent-contract.md` --- Schema convergence, protocol comparison, translation layer

**Codebase Source Files:**
- `/workspace/src/n3tx/core/models/proto_model.py` --- Schema generation, `__n3tx_methods_json_signature__`, `model_dump(response=True)`
- `/workspace/src/n3tx/static/core/Actor.js` --- Actor base class, message routing, supervision, `spawn()`
- `/workspace/src/n3tx/static/core/Matrix.js` --- Message bus, local/remote routing
- `/workspace/src/n3tx/static/core/N3TX.js` --- Entity system, `prototype()` DynamicClass factory, SCHEMA handler
- `/workspace/src/n3tx/core/api/routes_fastapi.py` --- Route generation, auth integration, `make_custom_post`
- `/workspace/src/n3tx/core/utils/decorators.py` --- `@expose_route` decorator
- `/workspace/src/n3tx/core/authorize/rules.py` --- ABAC rules: `ANYONE`, `AUTHENTICATED`, `OWNER`, `ROLE`, `Where`

**External Sources (selected; full lists in research documents):**
- Gartner: Hype Cycle for AI 2025; 40% project cancellation prediction
- Deloitte: State of AI in the Enterprise 2026; TMT Predictions 2026
- Precedence Research: Agentic AI Market ($183B by 2033)
- Anthropic: MCP Specification; Claude Agent SDK
- OpenAI: Structured Outputs; Agents SDK
- Google: A2A Protocol; Gemini Function Calling
- Trail of Bits: Prompt Injection to RCE in AI Agents (October 2025)
- OWASP: AI Agent Security Cheat Sheet
- Galileo AI: Hidden Cost of Agentic AI ($47K incident)
- EU AI Act: Full applicability August 2, 2026

---

*This analysis was prepared in February 2026. The AI agent landscape is evolving rapidly. Market data, pricing, and framework capabilities should be verified against current sources before making investment decisions. The codebase analysis reflects the state of the `profiling` branch as of February 26, 2026.*
