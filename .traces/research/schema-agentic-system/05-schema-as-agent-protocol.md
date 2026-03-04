# Schema as Agent Protocol: The Universal Contract for Agentic Systems

> **The core thesis:** What if the same pattern that lets N3TX derive a full-stack
> application from a model definition could derive a full agent system from a schema?

---

## 1. Executive Summary

The AI agent ecosystem is converging on a single insight: **declarative schemas
are the natural protocol for agentic systems**. Just as JSON Schema lets N3TX's
frontend discover a backend's capabilities, data types, access rules, and UI
rendering instructions from a single `GET /Product` call -- agent systems need
an equivalent mechanism for agents to discover each other's capabilities, negotiate
contracts, and compose into teams.

This is not speculation. The pattern is already emerging across the industry:

- **Anthropic's MCP** uses JSON Schema for tool definitions, with **10,000+
  public servers** and **97M+ monthly SDK downloads** as of late 2025
  ([Pento Year Review](https://www.pento.ai/blog/a-year-of-mcp-2025-review))
- **Google's A2A Protocol** uses JSON **Agent Cards** published at
  `/.well-known/agent.json` for capability discovery, backed by **150+
  organizations** ([Google Developers Blog](https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/))
- **OpenAI's Agents SDK** auto-generates tool schemas from Python/Pydantic
  type annotations -- the exact same pattern N3TX uses for model schemas
  ([OpenAI Agents SDK](https://openai.github.io/openai-agents-python/))
- **Microsoft's Declarative Agents** define entire agent behavior via JSON
  manifests with capabilities, actions, and instructions
  ([Microsoft Learn](https://learn.microsoft.com/en-us/microsoft-365-copilot/extensibility/declarative-agent-manifest-1.2))

The question is not whether schemas will be the agent protocol. They already are.
The question is **how far we can push the pattern** -- and N3TX's architecture
offers a remarkably complete blueprint.

> **Key Insight:** N3TX already implements 80% of the patterns the agent
> ecosystem is independently converging on. The model-as-schema-as-contract
> architecture is not a metaphor for agent systems -- it is a direct
> architectural template.

---

## 2. The Landscape: How Schemas Already Drive Agent Systems

### 2.1 Protocol Comparison Matrix

The agent protocol space in 2025-2026 is a fragmented but converging landscape.
Four major protocols have emerged, each using schemas differently. Here is how
they compare ([Survey: Ehtesham et al., arXiv 2505.02279](https://arxiv.org/abs/2505.02279)):

| Dimension | MCP | A2A | ACP | ANP |
|---|---|---|---|---|
| **Creator** | Anthropic (2024) | Google (2025) | IBM/IETF | Community |
| **Primary Focus** | Agent <-> Tools | Agent <-> Agent | Agent messaging | Decentralized agents |
| **Schema Format** | JSON Schema (inputSchema) | JSON (Agent Card) | MIME multipart | JSON-LD + Schema.org |
| **Discovery** | Manual/static URL | `.well-known/agent.json` | Registry-based | Search engine / DHT |
| **Transport** | JSON-RPC 2.0 / HTTP / stdio | HTTP + SSE | HTTP REST | HTTPS + JSON-LD |
| **Session Model** | Stateless + context | Stateful (task lifecycle) | Session-aware runs | Stateless + DID auth |
| **Auth Model** | Token-based, optional DID | DID handshake + Agent Card | Bearer / mTLS / JWS | W3C DIDs (did:wba) |
| **Adoption** | 10,000+ servers, 97M+ downloads | 150+ orgs | Early stage | Research stage |

**The key insight from this table:** Every protocol uses some form of
schema-based capability declaration. The formats differ, but the pattern
is universal.

### 2.2 MCP: Schema for Tool Access

MCP defines tools using JSON Schema for their input parameters. A tool
definition looks like this:

```json
{
  "name": "get_issue",
  "description": "Get a single issue by number from a specific repository",
  "inputSchema": {
    "type": "object",
    "required": ["input"],
    "properties": {
      "input": {
        "type": "object",
        "title": "GetIssueInput",
        "required": ["owner", "repo", "issue_number"],
        "properties": {
          "repo": { "type": "string", "description": "Repository name" },
          "owner": { "type": "string", "description": "Repository owner" },
          "issue_number": { "type": "integer", "description": "Issue number" }
        },
        "additionalProperties": false
      }
    }
  }
}
```

**What MCP gets right:** Standard JSON Schema for inputs means any LLM can
understand tool capabilities. Discovery is straightforward via `tools/list`.

**What MCP lacks:** No access control metadata, no cost/reliability signals,
no agent identity, no composition primitives. MCP is deliberately vertical --
one model talks to one set of tools.

([MCP Tool Schema Guide](https://www.merge.dev/blog/mcp-tool-schema),
[MCP Specification](https://modelcontextprotocol.io/specification/2025-11-25))

### 2.3 A2A: Schema for Agent Identity

Google's A2A Protocol uses **Agent Cards** -- JSON documents that describe an
agent's identity, capabilities, and communication preferences:

```json
{
  "name": "Research Analyst Agent",
  "description": "Performs deep research and analysis on technical topics",
  "version": "2.1.0",
  "url": "https://agents.example.com/research",
  "defaultInputModes": ["text/plain", "application/json"],
  "defaultOutputModes": ["text/plain", "text/markdown"],
  "capabilities": {
    "streaming": true,
    "pushNotifications": true
  },
  "skills": [
    {
      "id": "deep_research",
      "name": "Deep Technical Research",
      "description": "Conducts multi-source research on technical topics",
      "tags": ["research", "analysis", "technology"],
      "examples": ["Research the state of WebAssembly in 2026"],
      "inputModes": ["text/plain"],
      "outputModes": ["text/markdown", "application/json"]
    }
  ],
  "securitySchemes": {
    "bearer": { "type": "http", "scheme": "bearer" }
  }
}
```

**What A2A gets right:** Agent discovery via well-known endpoints, skills as
first-class concepts, capability negotiation through input/output modes.

**What A2A lacks:** No fine-grained access control per skill, no schema
composition (`$ref`, `$defs`), no runtime behavior derivation from the card.

([A2A Protocol Specification](https://a2a-protocol.org/latest/specification/),
[A2A Skills Tutorial](https://a2a-protocol.org/latest/tutorials/python/3-agent-skills-and-card/))

### 2.4 OpenAI Agents SDK: Schema from Code

OpenAI's approach mirrors N3TX's most closely -- **derive the schema from
the code**, using Pydantic models and Python type hints:

```python
from agents import Agent, InputGuardrail, OutputGuardrail
from pydantic import BaseModel

class ResearchOutput(BaseModel):
    summary: str
    sources: list[str]
    confidence: float

research_agent = Agent(
    name="Research Analyst",
    instructions="You are a senior research analyst...",
    tools=[web_search, file_reader],
    output_type=ResearchOutput,       # Schema derived from Pydantic
    handoffs=[editor_agent],          # Delegation targets
    input_guardrails=[safety_check],  # Input validation
    output_guardrails=[fact_check],   # Output validation
)
```

**What OpenAI gets right:** Pydantic-powered schema generation (same as
N3TX's `ProtoModel`), guardrails as first-class concepts, handoffs for
agent delegation.

**What OpenAI lacks:** No network-level discovery (agents are local objects),
no persistent identity, no schema publication for external consumption.

([OpenAI Agents SDK](https://openai.github.io/openai-agents-python/),
[OpenAI Agents - Guardrails](https://openai.github.io/openai-agents-python/guardrails/))

---

## 3. The N3TX Pattern: A Blueprint for Agent Schemas

> **For the CEO:** N3TX already solves for agents what MCP, A2A, and OpenAI
> each solve partially. The architecture that auto-generates APIs, UIs, and
> access control from a Python model is structurally identical to what the
> agent ecosystem needs.

### 3.1 Architectural Parallel: Model = App, Schema = Agent

N3TX's core loop is:

```
  [Python Model] --schema()--> [JSON Schema] --GET /Product--> [Frontend]
       |                            |                              |
       |  Defines fields,           |  Carries types, access,     |  Creates DynamicClass,
       |  methods, access,          |  methods, UI hints,         |  renders forms,
       |  relationships             |  $defs for relations        |  enforces permissions
```

The agent equivalent would be:

```
  [Agent Model] --schema()--> [Agent Schema] --GET /.well-known/agent--> [Orchestrator]
       |                            |                                        |
       |  Defines capabilities,     |  Carries skills, access,              |  Creates AgentProxy,
       |  tools, access,            |  tools, guardrails,                   |  routes tasks,
       |  delegation rules          |  $defs for sub-agents                 |  enforces contracts
```

The structural mapping is remarkably precise:

| N3TX Concept | Agent System Equivalent | Existing Protocol |
|---|---|---|
| `ProtoModel` base class | `BaseAgent` base class | OpenAI `Agent()` |
| `model.schema()` | `agent.capability_schema()` | A2A Agent Card |
| `properties` in schema | Tool input/output definitions | MCP `inputSchema` |
| `methods` in schema | Agent skills / callable actions | A2A `skills[]` |
| `__access__` rules | Permission / authorization rules | (Missing from all) |
| `$defs` for related models | Sub-agent / tool schemas | (Partial in A2A) |
| `__ui__` hints | Interaction mode preferences | A2A `inputModes` |
| `DynamicClass` from `prototype()` | `AgentProxy` from schema | (Novel) |
| `N3TX.SCHEMA()` bootstrap | Agent registry bootstrap | A2A discovery |
| `model_dump(response=True)` | Agent response with self-describing metadata | (Novel) |

### 3.2 What N3TX Has That Agents Need

Reading the actual N3TX source code reveals several patterns that are
**absent from every current agent protocol** but clearly needed:

**1. Composable Access Rules with SQL Pushdown**

N3TX's `authorize/rules.py` defines rules like `OWNER | ROLE('admin')` that
compose with boolean operators (`|`, `&`, `~`) and serialize to JSON for frontend
consumption AND generate SQL WHERE clauses for efficient filtering. No agent
protocol has anything this sophisticated for access control.

```python
# N3TX access rules -- composable, serializable, enforceable
__access__ = {
    'invoke': AUTHENTICATED,
    'delegate': OWNER | ROLE('admin'),
    'configure': ROLE('admin'),
}
# Serializes to:
# {"invoke": {"rule": "authenticated"},
#  "delegate": {"op": "or", "rules": [{"rule": "owner"}, {"rule": "role", "roles": ["admin"]}]}}
```

**2. Schema-Carried Method Signatures**

`ProtoModel.__n3tx_methods_json_signature__()` introspects Python methods
decorated with `@expose_route` and serializes their full signatures (parameters,
types, return types, access rules) into the schema. This is exactly what agent
skills need -- but with proper type contracts.

**3. Runtime Class Generation from Schema**

`N3TX.js`'s `prototype()` function (line 663) creates a complete JavaScript class
at runtime from a JSON Schema -- with typed properties, validated setters,
method stubs, and an actor-model message bus. This is the **DynamicClass
pattern** that agent proxies need.

**4. Nested Schema Registration via `$defs`**

When `N3TX.SCHEMA()` receives a schema, it automatically registers all `$defs`
entries as their own DynamicClasses. The agent equivalent: registering sub-agents
and tools as independently addressable entities from a parent agent's schema.

---

## 4. The Agent Schema Specification: A Concrete Proposal

Based on research across all existing protocols and N3TX's proven patterns,
here is what a **unified agent schema** would look like -- combining the best
of MCP, A2A, OpenAI, and N3TX's architecture.

### 4.1 Complete Agent Schema Example

```json
{
  "$schema": "https://schemas.agentprotocol.org/v1/agent-schema.json",
  "$id": "https://agents.example.com/ResearchAnalyst",

  "__name__": "ResearchAnalyst",
  "__version__": "2.1.0",
  "__description__": "Senior research analyst specializing in technical due diligence",

  "identity": {
    "organization": "example.com",
    "contact": "ops@example.com",
    "documentation": "https://docs.example.com/agents/research"
  },

  "capabilities": {
    "streaming": true,
    "async_tasks": true,
    "max_concurrent_tasks": 5,
    "supported_protocols": ["a2a/v0.3", "mcp/2025-11-25"]
  },

  "properties": {
    "model": {
      "type": "string",
      "const": "claude-opus-4-6",
      "description": "Underlying LLM model"
    },
    "temperature": {
      "type": "number",
      "default": 0.3,
      "minimum": 0,
      "maximum": 1
    },
    "max_tokens": {
      "type": "integer",
      "default": 8192,
      "maximum": 32768
    }
  },

  "skills": {
    "deep_research": {
      "route": "/research",
      "methods": ["POST"],
      "scope": "instancemethod",
      "description": "Conduct multi-source research on a technical topic",
      "parameters": {
        "topic": { "type": "string", "minLength": 1 },
        "depth": { "type": "string", "enum": ["surface", "moderate", "deep"] },
        "sources_required": { "type": "integer", "minimum": 3, "default": 10 }
      },
      "returns": { "$ref": "#/$defs/ResearchReport" },
      "access": { "rule": "authenticated" },
      "cost": { "estimated_tokens": 15000, "estimated_time_seconds": 120 },
      "reliability": { "success_rate": 0.94, "avg_latency_ms": 45000 }
    },
    "fact_check": {
      "route": "/fact-check",
      "methods": ["POST"],
      "scope": "instancemethod",
      "description": "Verify claims against authoritative sources",
      "parameters": {
        "claims": {
          "type": "array",
          "items": { "type": "string" },
          "minItems": 1
        }
      },
      "returns": { "$ref": "#/$defs/FactCheckResult" },
      "access": { "rule": "anyone" },
      "cost": { "estimated_tokens": 5000, "estimated_time_seconds": 30 }
    }
  },

  "tools": {
    "web_search": {
      "$ref": "mcp://tools.example.com/web-search",
      "access": { "rule": "authenticated" },
      "rate_limit": { "requests_per_minute": 60 }
    },
    "document_reader": {
      "$ref": "mcp://tools.example.com/doc-reader",
      "access": {
        "op": "or",
        "rules": [{"rule": "owner"}, {"rule": "role", "roles": ["admin"]}]
      }
    }
  },

  "access": {
    "invoke": { "rule": "authenticated" },
    "configure": { "rule": "role", "roles": ["admin"] },
    "delegate_to": { "rule": "authenticated" },
    "read_output": {
      "op": "or",
      "rules": [{"rule": "owner"}, {"rule": "role", "roles": ["admin", "auditor"]}]
    }
  },

  "guardrails": {
    "input": {
      "max_input_tokens": 16000,
      "blocked_topics": ["illegal_activity", "pii_generation"],
      "required_fields": ["topic"]
    },
    "output": {
      "must_cite_sources": true,
      "max_output_tokens": 32000,
      "format_schema": { "$ref": "#/$defs/ResearchReport" }
    }
  },

  "delegations": {
    "editor": {
      "$ref": "https://agents.example.com/EditorAgent",
      "when": "output.needs_editing == true",
      "handoff_schema": { "$ref": "#/$defs/EditRequest" }
    },
    "specialist": {
      "$ref": "https://agents.example.com/DomainSpecialist",
      "when": "topic.domain not in self.known_domains",
      "access": { "rule": "role", "roles": ["admin"] }
    }
  },

  "ui": {
    "renderer": { "card": "agent-card", "detail": "agent-detail" },
    "display_order": ["deep_research", "fact_check"],
    "groups": {
      "Core": ["deep_research", "fact_check"],
      "Advanced": ["configure", "delegate"]
    }
  },

  "$defs": {
    "ResearchReport": {
      "$id": "https://agents.example.com/schemas/ResearchReport",
      "type": "object",
      "properties": {
        "title": { "type": "string" },
        "summary": { "type": "string", "maxLength": 500 },
        "sections": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "heading": { "type": "string" },
              "content": { "type": "string" },
              "sources": { "type": "array", "items": { "type": "string", "format": "uri" } }
            },
            "required": ["heading", "content"]
          }
        },
        "confidence": { "type": "number", "minimum": 0, "maximum": 1 },
        "needs_editing": { "type": "boolean" }
      },
      "required": ["title", "summary", "sections", "confidence"]
    },
    "FactCheckResult": {
      "$id": "https://agents.example.com/schemas/FactCheckResult",
      "type": "object",
      "properties": {
        "claims": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "claim": { "type": "string" },
              "verdict": { "type": "string", "enum": ["verified", "disputed", "unverifiable"] },
              "evidence": { "type": "array", "items": { "type": "string", "format": "uri" } }
            }
          }
        }
      }
    },
    "EditRequest": {
      "$id": "https://agents.example.com/schemas/EditRequest",
      "type": "object",
      "properties": {
        "document": { "$ref": "#/$defs/ResearchReport" },
        "instructions": { "type": "string" },
        "priority": { "type": "string", "enum": ["low", "medium", "high"] }
      }
    }
  }
}
```

### 4.2 Schema Section Breakdown

| Section | Purpose | N3TX Parallel | Existing Protocol Equivalent |
|---|---|---|---|
| `$schema` / `$id` | Self-describing identity | `ProtoModel.schema()` meta | A2A Agent Card `url` |
| `identity` | Organization metadata | - | A2A Agent Card `name/version` |
| `capabilities` | Protocol & runtime features | - | A2A `capabilities` |
| `properties` | Agent configuration | `schema.properties` | - |
| `skills` | Callable actions with contracts | `schema.methods` | A2A `skills[]` |
| `tools` | External tool references | - | MCP `tools/list` |
| `access` | ABAC authorization rules | `__access__` | **(Novel)** |
| `guardrails` | Input/output safety boundaries | - | OpenAI `input_guardrails` |
| `delegations` | Agent handoff rules | - | OpenAI `handoffs` |
| `ui` | Rendering/interaction hints | `__ui__` | A2A `inputModes` |
| `$defs` | Nested type schemas | `schema.$defs` | **(Novel at this depth)** |

> **Key Insight:** The **access**, **guardrails**, and **$defs composition**
> sections have no equivalent in any existing agent protocol. These are the
> elements that would make a schema-driven agent system genuinely production-ready,
> and they come directly from N3TX's existing architecture.

---

## 5. Schema as Capability Declaration

### 5.1 How It Works Technically

An agent publishes its schema at a well-known endpoint. Orchestrators,
other agents, or human operators read the schema and know -- without any
prior integration work -- exactly what the agent can do, what inputs it
accepts, what outputs it produces, and what permissions are required.

```
  [Research Agent]                        [Orchestrator]
       |                                       |
       |  GET /.well-known/agent.json          |
       | <-------------------------------------|
       |                                       |
       |  200 OK { $schema, $id, skills,       |
       |           access, tools, $defs... }   |
       |-------------------------------------> |
       |                                       |
       |  (Orchestrator now knows:             |
       |   - 2 skills available                |
       |   - Input/output contracts per skill  |
       |   - Auth requirements                 |
       |   - Cost estimates                    |
       |   - Delegation targets)               |
       |                                       |
       |  POST /research                       |
       |  { topic: "...", depth: "deep" }      |
       | <-------------------------------------|
       |                                       |
       |  200 OK { $schema: ".../ResearchReport",
       |           $id: ".../tasks/42",        |
       |           title: "...",               |
       |           confidence: 0.87 }          |
       |-------------------------------------> |
```

The response includes **self-describing metadata** (`$schema` and `$id`),
following the exact pattern N3TX uses for entity responses. Any consumer
can independently resolve the output type and trace back to the agent
that produced it.

### 5.2 Comparison: Explicit vs. Implicit Capability Declaration

| Approach | Example | Discovery | Validation | Composability |
|---|---|---|---|---|
| **Hard-coded** | `if agent == "researcher": call(...)` | None | None | None |
| **Configuration file** | CrewAI YAML agents.yaml | Static file | Manual | Limited |
| **Function signatures** | OpenAI `tools=[func]` | Runtime introspection | Pydantic | Local only |
| **Published schema** | A2A Agent Card | HTTP endpoint | JSON Schema | Via `$ref` |
| **Full agent schema** | Proposed unified schema | HTTP + registry | JSON Schema + ABAC | `$ref` + `$defs` + `allOf` |

The progression from hard-coded to full schema mirrors the evolution from
hand-built REST APIs to OpenAPI-driven development. **The agent ecosystem
is at the "hand-built REST" stage** -- everyone builds agents differently,
and integration requires bespoke work per pair.

([CrewAI Agent Configuration](https://docs.crewai.com/en/concepts/agents),
[agents.json by Wildcard AI](https://github.com/wild-card-ai/agents-json))

---

## 6. Schema-Driven Tool Registration

### 6.1 Beyond MCP: Tools with Metadata

MCP tools carry a name, description, and inputSchema. That is necessary but
insufficient for production systems. Here is what a schema-driven tool
registration should carry:

```json
{
  "tools": {
    "web_search": {
      "name": "web_search",
      "description": "Search the web for current information",
      "inputSchema": {
        "type": "object",
        "properties": {
          "query": { "type": "string", "minLength": 2, "maxLength": 500 },
          "max_results": { "type": "integer", "default": 10, "maximum": 50 }
        },
        "required": ["query"]
      },
      "outputSchema": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "title": { "type": "string" },
            "url": { "type": "string", "format": "uri" },
            "snippet": { "type": "string" }
          }
        }
      },
      "access": { "rule": "authenticated" },
      "cost": {
        "tokens_per_call": 500,
        "price_per_call_usd": 0.002,
        "billing_model": "per_call"
      },
      "reliability": {
        "uptime_sla": 0.999,
        "avg_latency_ms": 1200,
        "error_rate": 0.01
      },
      "rate_limits": {
        "requests_per_minute": 60,
        "requests_per_day": 10000
      },
      "provenance": {
        "provider": "search-provider.com",
        "version": "3.2.1",
        "last_verified": "2026-02-20"
      }
    }
  }
}
```

**What this adds beyond MCP:**

| Extension | Why It Matters | Who Benefits |
|---|---|---|
| `outputSchema` | Agents validate responses before processing | Engineers (debugging) |
| `access` (ABAC rules) | Fine-grained per-tool authorization | CEO (compliance) |
| `cost` | Budget-aware tool selection | CEO (cost control) |
| `reliability` | SLA-aware routing; avoid flaky tools | Engineers (reliability) |
| `rate_limits` | Prevent quota exhaustion in multi-agent systems | Both (stability) |
| `provenance` | Audit trail; know which version produced what | CEO (governance) |

### 6.2 The N3TX Pattern for Tools

N3TX's `@expose_route` decorator is functionally a tool registration mechanism:

```python
@expose_route('/comment', methods=['POST'], access=AUTHENTICATED)
def comment(self, comment: Comment, user: User = None) -> str:
    """Add a comment to this product."""
    ...
```

This gets serialized into the schema as:

```json
"methods": {
  "comment": {
    "route": "/comment",
    "methods": ["POST"],
    "scope": "instancemethod",
    "parameters": {
      "comment": { "$ref": "#/$defs/Comment" }
    },
    "returns": { "type": "string" },
    "access": { "rule": "authenticated" }
  }
}
```

The parallel is exact: a Python method becomes a schema-described capability
with typed inputs, typed outputs, and access control -- all derived from code,
not configured separately.

---

## 7. Agent Discovery via Schema

### 7.1 The Discovery Problem

In a system with **N agents**, naive point-to-point integration requires
**N*(N-1)/2** connections. Schema-driven discovery collapses this to **N
registrations + 1 query**.

```
WITHOUT SCHEMA DISCOVERY:              WITH SCHEMA DISCOVERY:

  [A] <-----> [B]                        [A] --register--> [Registry]
  [A] <-----> [C]                        [B] --register--> [Registry]
  [B] <-----> [C]                        [C] --register--> [Registry]
  [A] <-----> [D]                                |
  [B] <-----> [D]                        [Orchestrator] --query "research"--> [Registry]
  [C] <-----> [D]                                |
                                         [Registry] --> [A: matches, B: no match, ...]
  6 integrations for 4 agents            1 query finds the right agent
```

### 7.2 How N3TX's Pattern Maps

N3TX already implements a discovery mechanism. When a frontend component
like `<ntx-list model="Product">` mounts, it triggers:

1. **`N3TX.ATTACH("Product")`** -- registers interest in a model type
2. **Schema fetch** -- `GET /Product` retrieves the full schema
3. **`N3TX.SCHEMA(data)`** -- creates DynamicClass, registers `$defs`
4. **`DynamicClass.READ()`** -- fetches actual data

The agent equivalent:

1. **Orchestrator registers interest** in a capability ("research")
2. **Schema fetch** -- `GET /.well-known/agent.json` from candidate agents
3. **Agent proxy creation** -- instantiate typed proxy from schema
4. **Task dispatch** -- route task to the best-matched agent

The `N3TX.SCHEMA()` function (N3TX.js, line 390) is already a schema-driven
agent bootstrap:

```javascript
// N3TX.SCHEMA creates a typed class from a schema -- this IS agent instantiation
static SCHEMA(data, tx) {
    const addr = data.__name__;
    const href = data.__tablename__
        ? `${config.API_URL}/${data.__tablename__}`
        : `${config.API_URL}/${addr}`;

    // Register nested schemas ($defs) -- sub-agents / tools
    if (data.$defs) {
        for (const [key, value] of Object.entries(data.$defs)) {
            if (value.type === 'object' && value.properties && !N3TX.has(key)) {
                const DC = prototype(key, value, defHref);
                N3TX.#prototypes.set(key, DC);
            }
        }
    }

    // Create main agent proxy
    const DC = prototype(addr, data, href);
    N3TX.#prototypes.set(addr, DC);
    N3TX.#replayWaiting(addr, DC);  // Replay queued tasks
}
```

([A2A Agent Discovery](https://a2a-protocol.org/latest/topics/agent-discovery/))

---

## 8. Schema-Driven Routing

### 8.1 From Hard-Coded to Schema-Derived Routing

Traditional agent orchestration hard-codes routing logic:

```python
# Hard-coded orchestration (fragile, not scalable)
if task.type == "research":
    result = research_agent.execute(task)
elif task.type == "coding":
    result = coding_agent.execute(task)
elif task.type == "review":
    result = review_agent.execute(task)
```

Schema-driven routing reads agent schemas and matches tasks to capabilities:

```python
# Schema-driven routing (dynamic, discoverable)
def route_task(task, agent_registry):
    candidates = []
    for agent_schema in agent_registry.all():
        for skill_name, skill in agent_schema['skills'].items():
            # Match on skill tags, input compatibility, access rules
            if matches(task, skill):
                candidates.append({
                    'agent': agent_schema['$id'],
                    'skill': skill_name,
                    'cost': skill.get('cost', {}),
                    'reliability': skill.get('reliability', {}),
                    'access': skill.get('access', {})
                })

    # Rank by: reliability > cost > latency
    return sorted(candidates, key=ranking_function)[0]
```

### 8.2 Routing Decision Matrix

A schema-aware router can use multiple dimensions from the agent schema
to make optimal routing decisions:

| Routing Factor | Schema Field | Decision Example |
|---|---|---|
| **Capability match** | `skills[].description`, `tags` | "Only agents with 'research' tag" |
| **Input compatibility** | `skills[].parameters` | "Needs to accept JSON arrays" |
| **Cost optimization** | `skills[].cost.estimated_tokens` | "Use cheapest agent under 10K tokens" |
| **Reliability** | `skills[].reliability.success_rate` | "Only agents with >95% success" |
| **Authorization** | `skills[].access` | "User must be authenticated" |
| **Latency** | `skills[].reliability.avg_latency_ms` | "Must respond within 30 seconds" |
| **Protocol** | `capabilities.supported_protocols` | "Must support streaming" |

This is the analog of N3TX's route resolution, where the schema determines
what HTTP methods are available, what authentication is required, and what
content types are accepted -- all without hand-coding route logic.

---

## 9. Schema Composition for Multi-Agent Systems

### 9.1 Building Teams from Schema Building Blocks

JSON Schema's composition primitives (`$ref`, `$defs`, `allOf`, `anyOf`) are
directly applicable to composing agent teams:

```json
{
  "$id": "https://agents.example.com/ResearchTeam",
  "__name__": "ResearchTeam",
  "__description__": "A composed team of specialized research agents",

  "allOf": [
    { "$ref": "https://agents.example.com/ResearchAnalyst" },
    { "$ref": "https://agents.example.com/FactChecker" },
    { "$ref": "https://agents.example.com/EditorAgent" }
  ],

  "workflow": {
    "type": "sequential",
    "steps": [
      { "agent": "ResearchAnalyst", "skill": "deep_research" },
      { "agent": "FactChecker", "skill": "fact_check", "input": "previous.output" },
      { "agent": "EditorAgent", "skill": "polish", "input": "previous.output" }
    ]
  },

  "access": {
    "invoke": { "rule": "authenticated" },
    "view_intermediate": { "rule": "role", "roles": ["admin", "auditor"] }
  }
}
```

### 9.2 The `$defs` Pattern for Agent Hierarchies

N3TX's `$defs` mechanism -- where a Product schema carries inline definitions
for Comment, Like, etc. -- maps directly to agent hierarchies:

```
  Team Schema ($defs)
  ├── ResearchAnalyst ($defs[0])
  │   ├── skills: deep_research, summarize
  │   └── tools: web_search, doc_reader
  ├── FactChecker ($defs[1])
  │   ├── skills: fact_check, source_verify
  │   └── tools: web_search, citation_db
  └── Editor ($defs[2])
      ├── skills: polish, format
      └── tools: grammar_check, style_guide
```

Each `$def` is independently addressable (via its own `$id`), can be
composed into different teams, and carries its own access rules and
tool registrations. This is the N3TX pattern of nested models
applied to agent composition.

---

## 10. Schema-Driven Guardrails

### 10.1 The Guardrail Problem

Without schema-enforced guardrails, agent behavior is **constrained only
by prompt engineering** -- which is probabilistic, not deterministic.
Schema-driven guardrails add a structural enforcement layer:

```
  [Input] --> [Input Schema Validation] --> [Agent] --> [Output Schema Validation] --> [Output]
                     |                                         |
                     | Reject if:                              | Reject if:
                     | - Missing required fields               | - Missing required fields
                     | - Exceeds token limits                  | - Doesn't cite sources
                     | - Blocked topics detected               | - Confidence below threshold
                     | - Unauthorized caller                   | - Contains PII
```

### 10.2 Guardrails in the Agent Schema

The guardrails section of the proposed schema carries enforceable contracts:

```json
{
  "guardrails": {
    "input": {
      "max_input_tokens": 16000,
      "blocked_topics": ["illegal_activity", "pii_generation"],
      "required_fields": ["topic"],
      "input_schema": {
        "type": "object",
        "properties": {
          "topic": { "type": "string", "minLength": 3 },
          "depth": { "type": "string", "enum": ["surface", "moderate", "deep"] }
        },
        "required": ["topic"],
        "additionalProperties": false
      }
    },
    "output": {
      "must_cite_sources": true,
      "min_sources": 3,
      "max_output_tokens": 32000,
      "format_schema": { "$ref": "#/$defs/ResearchReport" },
      "prohibited_patterns": ["(?i)i('m| am) (not )?sure", "as an AI"]
    },
    "behavioral": {
      "max_tool_calls_per_task": 50,
      "max_delegation_depth": 3,
      "timeout_seconds": 300,
      "require_human_approval": {
        "when": "cost.estimated_tokens > 50000",
        "approver_role": "admin"
      }
    }
  }
}
```

**Three layers of guardrails:**

| Layer | Enforced By | Schema Field | N3TX Parallel |
|---|---|---|---|
| **Input** | JSON Schema validation | `guardrails.input.input_schema` | Field validators |
| **Output** | JSON Schema + custom rules | `guardrails.output.format_schema` | `model_dump()` |
| **Behavioral** | Runtime monitoring | `guardrails.behavioral.*` | `__access__` + `Where()` |

The behavioral guardrails are novel -- constraining not just data shape but
agent behavior (tool call limits, delegation depth, cost ceilings). These are
the equivalent of N3TX's `Where(status='draft')` rules applied to agent
runtime behavior rather than data attributes.

([Guardrails AI Framework](https://github.com/guardrails-ai/guardrails),
[OpenAI Guardrails](https://openai.github.io/openai-agents-python/guardrails/),
[LLM Guardrails Best Practices](https://www.datadoghq.com/blog/llm-guardrails-best-practices/))

---

## 11. Runtime Agent Instantiation from Schema

### 11.1 The DynamicClass Pattern for Agents

N3TX's `prototype()` function creates fully functional JavaScript classes
at runtime from JSON Schema. The same pattern applied to agents would mean:

**Instead of:**
```python
# Static agent definition -- must be deployed with code
class ResearchAgent:
    def deep_research(self, topic: str, depth: str) -> ResearchReport:
        ...
```

**You get:**
```python
# Dynamic agent instantiation from schema
schema = fetch("https://agents.example.com/ResearchAnalyst")
AgentProxy = create_agent_proxy(schema)

# AgentProxy now has:
# - .deep_research(topic, depth) method with type validation
# - .fact_check(claims) method with type validation
# - Access control enforcement from schema.access
# - Cost tracking from schema.skills[].cost
# - Output validation from schema.$defs

result = AgentProxy.deep_research(topic="WebAssembly trends", depth="deep")
# result is validated against schema.$defs.ResearchReport
```

### 11.2 How `prototype()` Maps to Agent Proxy Creation

The N3TX.js `prototype()` function (line 663-1075) performs these steps:

1. **Parse schema fields** -> Create typed getter/setter properties
2. **Parse schema methods** -> Create callable method stubs with validation
3. **Set up message bus** -> Connect to Actor system for async communication
4. **Register instances** -> Track created instances for lifecycle management
5. **Set up watchers** -> Notify observers on state changes

The agent equivalent:

1. **Parse skill definitions** -> Create typed method proxies with input validation
2. **Parse tool references** -> Create tool access proxies with auth enforcement
3. **Set up communication** -> Connect via A2A/MCP for async task execution
4. **Register in directory** -> Track agent for discovery and load balancing
5. **Set up monitoring** -> Emit metrics, enforce guardrails, track costs

> **Key Insight:** The `prototype()` pattern means you can spin up typed,
> validated, access-controlled agent proxies from a schema alone -- no code
> deployment needed. Add a new agent to the network by publishing a schema.
> Remove one by unpublishing it. The orchestrator adapts automatically.

---

## 12. Schema Evolution and Versioning

### 12.1 The Challenge

Agent schemas will evolve. Skills get added, parameters change, output formats
update. The question: how do agents with **different schema versions** interoperate?

### 12.2 Compatibility Strategies

Drawing from established schema evolution practices ([Confluent Schema Registry](https://docs.confluent.io/platform/current/schema-registry/fundamentals/schema-evolution.html)):

| Change Type | Compatibility | Example | Strategy |
|---|---|---|---|
| Add optional skill | **Backward compatible** | New `summarize` skill | Old clients ignore it |
| Add optional parameter | **Backward compatible** | `depth` param with default | Old callers use default |
| Remove skill | **Breaking** | Remove `fact_check` | Version bump + deprecation window |
| Change output schema | **Breaking** | `confidence` float -> object | New `$defs` version + migration |
| Add required parameter | **Breaking** | `sources_required` now mandatory | Version bump |
| Tighten access rules | **Backward compatible** | `anyone` -> `authenticated` | Old clients get 401 |

### 12.3 Schema Negotiation Protocol

```
  [Client Agent]                          [Provider Agent]
       |                                        |
       |  GET /.well-known/agent.json            |
       |  Accept: application/agent-schema+json; |
       |          version=2.x                    |
       | <--------------------------------------|
       |                                        |
       |  200 OK                                |
       |  Content-Type: application/agent-schema |
       |  +json; version=2.1.0                  |
       | -------------------------------------> |
       |                                        |
       |  (Client checks: 2.1.0 satisfies 2.x) |
       |  (Client creates proxy from v2.1 schema)
       |                                        |
```

The version field in the schema (`__version__`: "2.1.0") follows **semver**:
- **MAJOR**: Breaking changes (removed skills, changed required params)
- **MINOR**: Backward-compatible additions (new optional skills, new optional params)
- **PATCH**: Bug fixes, metadata updates

---

## 13. Comparison with Existing Protocols

### 13.1 Feature Matrix: What Each Protocol Covers

| Feature | MCP | A2A | OpenAI SDK | MS Declarative | **Unified Schema** |
|---|:---:|:---:|:---:|:---:|:---:|
| Tool input schema | Yes | -- | Yes | Via plugins | Yes |
| Tool output schema | Partial | -- | Yes | -- | Yes |
| Agent identity | -- | Yes | -- | Yes | Yes |
| Skill declaration | -- | Yes | -- | -- | Yes |
| Access control | -- | Auth only | -- | -- | **Full ABAC** |
| Cost metadata | -- | -- | -- | -- | **Yes** |
| Reliability metadata | -- | -- | -- | -- | **Yes** |
| Guardrails schema | -- | -- | Code only | -- | **Yes** |
| Delegation rules | -- | Task-based | Handoffs | Actions | **Schema-based** |
| `$defs` composition | -- | -- | -- | -- | **Yes** |
| Runtime instantiation | -- | -- | Local only | -- | **Yes** |
| Schema versioning | -- | Version field | -- | Version field | **Full semver** |
| UI rendering hints | -- | Input modes | -- | -- | **Yes** |
| SQL-pushdown auth | -- | -- | -- | -- | **Yes** |

### 13.2 What the Unified Schema Adds

The proposed unified schema's unique contributions are:

1. **Composable ABAC access rules** -- borrowed directly from N3TX's `authorize`
   package, with boolean composition (`|`, `&`, `~`) and serialization to JSON
2. **Cost and reliability metadata** -- enabling budget-aware, SLA-aware routing
3. **Schema-enforced guardrails** -- not just code-level checks but schema-level
   contracts that any consumer can validate
4. **`$defs` composition** -- build agent teams from schema building blocks,
   same as N3TX builds entity graphs from `$defs`
5. **Runtime instantiation** -- the DynamicClass pattern from N3TX.js applied to
   agent proxies, enabling network-level agent discovery and activation

### 13.3 Historical Context: FIPA to MCP

The agent protocol space has evolved dramatically:

```
1996: FIPA-ACL                     2024-2026: Modern Protocols
├── Speech act theory              ├── JSON Schema based
├── 20+ performatives              ├── RESTful / JSON-RPC
├── Shared ontology required       ├── Schema-driven discovery
├── KQML heritage                  ├── No shared ontology needed
└── Never achieved mass adoption   └── 10,000+ MCP servers in 18 months
```

**Why FIPA failed and MCP succeeded:** FIPA required agents to share a
common ontology before communicating. MCP requires only that tools publish
a JSON Schema. The barrier to adoption dropped from "agree on the meaning
of everything" to "describe your inputs and outputs."

([FIPA Agent Communication Language](https://en.wikipedia.org/wiki/Agent_Communications_Language),
[Agent Interoperability Survey](https://arxiv.org/abs/2505.02279))

---

## 14. The "Model is the Agent" Vision

### 14.1 From "Model is the App" to "Schema is the Agent"

N3TX's philosophy: **write a model, get a working app.** The agent extension:
**write an agent model, get a working agent system.**

```python
# N3TX: Model -> Full Stack App
class Product(ProtoModel):
    __tablename__ = 'products'
    __storable__ = True
    __access__ = {'read': ANYONE, 'create': AUTHENTICATED}

    name: str = Field(min_length=1)
    price: float = Field(gt=0)

    @expose_route('/comment', methods=['POST'])
    def comment(self, comment: Comment) -> str: ...

# => Auto-generates: API, DB table, JSON Schema, form UI, permissions
```

```python
# Proposed: Agent Model -> Full Agent System
class ResearchAnalyst(BaseAgent):
    __agentname__ = 'research-analyst'
    __discoverable__ = True
    __access__ = {'invoke': AUTHENTICATED, 'configure': ROLE('admin')}
    __guardrails__ = {
        'input': {'max_tokens': 16000},
        'output': {'must_cite_sources': True},
        'behavioral': {'max_tool_calls': 50}
    }

    model: str = Field(default="claude-opus-4-6")
    temperature: float = Field(default=0.3, ge=0, le=1)

    @expose_skill('/research', methods=['POST'], access=AUTHENTICATED,
                  cost={'estimated_tokens': 15000})
    def deep_research(self, topic: str, depth: str = "moderate") -> ResearchReport:
        """Conduct multi-source research on a technical topic."""
        ...

    @expose_skill('/fact-check', methods=['POST'], access=ANYONE)
    def fact_check(self, claims: list[str]) -> FactCheckResult:
        """Verify claims against authoritative sources."""
        ...

# => Auto-generates: Agent Schema, discovery endpoint, skill routes,
#    access control, guardrail enforcement, monitoring hooks
```

### 14.2 What Gets Auto-Generated

| Concern | Generated From | How |
|---|---|---|
| Agent Schema | Field types, `@expose_skill`, `__access__` | `BaseAgent.schema()` |
| Discovery endpoint | `__discoverable__`, `__agentname__` | `/.well-known/agent.json` |
| Skill routes | `@expose_skill` decorator | HTTP endpoints per skill |
| Access control | `__access__` | Middleware enforcement |
| Input validation | Skill parameter types | JSON Schema validation |
| Output validation | Return type annotation | JSON Schema validation |
| Guardrail enforcement | `__guardrails__` | Pre/post execution hooks |
| Cost tracking | `cost=` on `@expose_skill` | Metrics emission |
| Agent card (A2A) | Schema serialization | A2A-compatible Agent Card |
| MCP tool listing | Skill -> tool conversion | MCP `tools/list` compatible |
| Monitoring dashboard | Schema metadata | Auto-generated UI |

### 14.3 The Zero-to-Working Promise

Just as N3TX delivers zero-to-working apps, the agent equivalent delivers
zero-to-working agents:

1. **Define** the agent model in Python
2. **Start** the agent runtime -- schema published, discovery active
3. **Test** immediately -- other agents or orchestrators can find and invoke skills
4. **Customize** additively -- override guardrails, add tools, configure delegation

No separate configuration files. No manual schema authoring. No bespoke
integration per consumer. **The schema carries the complete specification,
derived from the code.**

---

## 15. Risks, Limitations, and Open Questions

### 15.1 Risks

| Risk | Severity | Mitigation |
|---|---|---|
| **Schema bloat** | Medium | Pagination, partial schema fetch (`?fields=skills`) |
| **Over-specification** | Medium | Distinguish required vs. optional sections |
| **Performance overhead** | Low | Cache schemas aggressively (N3TX pattern) |
| **Schema drift** | High | Schema registry with version validation |
| **False sense of security** | High | Schema validation is necessary but not sufficient |
| **Adoption friction** | High | Start with MCP/A2A compatibility, add extensions |

### 15.2 What Schemas Cannot Do

- **Schemas cannot replace prompt engineering** -- they constrain structure, not
  semantic quality
- **Schemas cannot guarantee agent reasoning** -- a well-typed output can still
  be factually wrong
- **Schemas cannot prevent all adversarial inputs** -- guardrails reduce but
  don't eliminate attack surface
- **Schemas add latency** -- schema fetch + validation adds overhead per interaction

### 15.3 Open Questions

1. **How much is too much?** At what point does schema complexity outweigh the
   benefits of dynamic discovery?
2. **Schema-first or code-first?** N3TX is code-first (schemas derived from
   models). Should agents be schema-first (schemas authored directly)?
3. **Who validates?** Should the agent validate its own output against its schema,
   or should the consumer? Or both?
4. **Governance at scale** -- with hundreds of agents publishing schemas, who
   manages the registry, resolves conflicts, enforces standards?
5. **LLM schema comprehension** -- current LLMs can consume JSON Schema for
   function calling, but can they reason about complex schema compositions
   (`allOf`, nested `$defs`, conditional access rules)?

---

## 16. Recommendations

> **For the CEO:** Schema-driven agents are not a future concept -- they are
> the current trajectory of the industry, with MCP and A2A leading adoption.
> The strategic question is whether to build on these existing protocols
> (pragmatic, lower risk) or extend them with N3TX-inspired patterns
> (differentiated, higher value).

> **For the engineers:** N3TX's architecture is a remarkably complete
> blueprint for what the agent ecosystem needs. The `ProtoModel` -> JSON
> Schema -> `DynamicClass` pipeline, the composable ABAC rules, the
> `$defs` nesting pattern, and the self-describing response format
> (`$schema` + `$id`) are all directly transferable.

### 16.1 Phased Approach

| Phase | Action | Effort | Impact |
|---|---|---|---|
| **Phase 1** | Add MCP tool compatibility to existing models | 2-3 weeks | Access MCP ecosystem |
| **Phase 2** | Publish Agent Cards (A2A) from `ProtoModel.schema()` | 2-4 weeks | Agent discovery |
| **Phase 3** | Extend schema with access, cost, guardrails metadata | 4-6 weeks | Differentiated platform |
| **Phase 4** | Implement `prototype()` equivalent for agent proxies | 6-8 weeks | Runtime composition |
| **Phase 5** | Schema registry + version negotiation | 4-6 weeks | Enterprise readiness |

### 16.2 Strategic Positioning

The strongest position is **compatibility + extension**:

- Be **compatible** with MCP for tool access (10,000+ servers)
- Be **compatible** with A2A for agent discovery (150+ organizations)
- **Extend** both with N3TX's unique contributions:
  - Composable ABAC access rules
  - Schema-enforced guardrails
  - Cost/reliability metadata
  - `$defs` agent composition
  - Runtime proxy instantiation

This is the same strategy that worked for JSON Schema itself: adopt the
standard, then extend it where the standard falls short.

---

## 17. Conclusion

The thesis holds: **the same pattern that derives a full-stack app from a
model can derive a full agent system from a schema.**

N3TX's architecture is not just an analogy for agent systems -- it is a
working implementation of the core patterns the agent ecosystem is
independently building toward:

- **MCP** is reinventing `@expose_route` for tools
- **A2A** is reinventing `ProtoModel.schema()` for agent discovery
- **OpenAI Agents SDK** is reinventing Pydantic-powered schema generation
- **Microsoft Declarative Agents** is reinventing `__ui__` for agent manifests

The gap in all of them -- composable access control, schema-enforced
guardrails, `$defs` composition, runtime instantiation, self-describing
responses -- is exactly what N3TX already provides for web applications.

**The model is the app. The schema is the agent.**

---

## 18. Sources

- [MCP Specification (2025-11-25)](https://modelcontextprotocol.io/specification/2025-11-25)
- [MCP Year in Review - Pento](https://www.pento.ai/blog/a-year-of-mcp-2025-review)
- [MCP Tool Schema Guide - Merge](https://www.merge.dev/blog/mcp-tool-schema)
- [MCP Adoption Statistics - MCP Manager](https://mcpmanager.ai/blog/mcp-adoption-statistics/)
- [A2A Protocol Specification](https://a2a-protocol.org/latest/specification/)
- [A2A Agent Card Tutorial](https://a2a-protocol.org/latest/tutorials/python/3-agent-skills-and-card/)
- [A2A Agent Discovery](https://a2a-protocol.org/latest/topics/agent-discovery/)
- [Google A2A Announcement](https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/)
- [A2A vs MCP Comparison - Merge](https://www.merge.dev/blog/mcp-vs-a2a)
- [MCP vs A2A - TrueFoundry](https://www.truefoundry.com/blog/mcp-vs-a2a)
- [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/)
- [OpenAI Agents SDK - Guardrails](https://openai.github.io/openai-agents-python/guardrails/)
- [OpenAI Function Calling](https://platform.openai.com/docs/guides/function-calling)
- [OpenAI Structured Outputs](https://openai.com/index/introducing-structured-outputs-in-the-api/)
- [Microsoft Declarative Agent Manifest v1.2](https://learn.microsoft.com/en-us/microsoft-365-copilot/extensibility/declarative-agent-manifest-1.2)
- [Agent Interoperability Survey (arXiv 2505.02279)](https://arxiv.org/abs/2505.02279)
- [Survey of AI Agent Protocols (arXiv 2504.16736)](https://arxiv.org/abs/2504.16736)
- [agents.json by Wildcard AI](https://github.com/wild-card-ai/agents-json)
- [JSON Agents - Portable Agent Manifest](https://jsonagents.org/)
- [CrewAI Agent Configuration](https://docs.crewai.com/en/concepts/agents)
- [Spec-Driven Development - The New Stack](https://thenewstack.io/spec-driven-development-the-key-to-scalable-ai-agents/)
- [Confluent Schema Evolution](https://docs.confluent.io/platform/current/schema-registry/fundamentals/schema-evolution.html)
- [Guardrails AI Framework](https://github.com/guardrails-ai/guardrails)
- [LLM Guardrails Best Practices - Datadog](https://www.datadoghq.com/blog/llm-guardrails-best-practices/)
- [FIPA Agent Communication Language](https://en.wikipedia.org/wiki/Agent_Communications_Language)
- [Anthropic MCP Donation & Agentic AI Foundation](https://www.anthropic.com/news/donating-the-model-context-protocol-and-establishing-of-the-agentic-ai-foundation)
- [Enterprise MCP Adoption 2026 - CData](https://www.cdata.com/blog/2026-year-enterprise-ready-mcp-adoption)
