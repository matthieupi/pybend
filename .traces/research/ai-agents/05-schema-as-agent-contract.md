# Schema as the Universal Agent Contract

**How JSON Schema became the lingua franca of AI agent systems --- and why
a schema-driven framework holds a structural advantage in the agent
orchestration space.**

*Research Document -- February 2026*
*Audience: Technical CEO + Engineering Team*

---

## Executive Summary

Every major AI provider --- OpenAI, Anthropic, Google --- has converged on
**JSON Schema** as the standard format for defining what tools an AI agent
can use, what inputs those tools accept, and what outputs they produce.
This is not a coincidence. JSON Schema is the only widely-adopted,
machine-readable, language-agnostic format that simultaneously describes
structure, validation constraints, and documentation.

A framework whose core architecture already produces rich JSON Schema as
its primary output --- not as an afterthought, but as the single source
of truth for the entire application --- sits at a unique intersection.
Its model schemas are, structurally, already agent tool definitions. The
gap between "web application framework" and "agent-native platform" is
not a rewrite. It is a translation layer.

This document examines the convergence on schema-driven tool definitions
across the AI ecosystem, maps the structural alignment between PyBend's
schema output and the major agent protocols, and lays out the concrete
path from "define a model, get an app" to "define a model, get an agent."

---

## Table of Contents

1. [The Convergence: JSON Schema as Agent Interface](#1-the-convergence)
2. [Protocol Comparison: How the Big Three Define Tools](#2-protocol-comparison)
3. [MCP Deep Dive: Anthropic's Schema-Native Standard](#3-mcp-deep-dive)
4. [PyBend Schema Anatomy: What Already Exists](#4-pybend-schema-anatomy)
5. [The Translation Layer: Schema to Tool Definition](#5-the-translation-layer)
6. [Schema as Capability Declaration](#6-schema-as-capability-declaration)
7. [Self-Describing Agents: Discovery Without Integration](#7-self-describing-agents)
8. [Schema Composition: Multi-Agent Capability Maps](#8-schema-composition)
9. [Schema Evolution: Automatic Agent Adaptation](#9-schema-evolution)
10. [Human-in-the-Loop via Schema](#10-human-in-the-loop)
11. [Structured Outputs: Closing the Reliability Loop](#11-structured-outputs)
12. [Competitive Analysis: Schema-First vs. Framework-First](#12-competitive-analysis)
13. [The "Define a Model, Get an Agent" Architecture](#13-define-a-model-get-an-agent)
14. [Implementation Roadmap](#14-implementation-roadmap)
15. [Sources](#15-sources)

---

## 1. The Convergence

### Every major AI provider chose JSON Schema

Between 2023 and 2025, every frontier AI provider independently arrived
at the same conclusion: **JSON Schema is the correct format for
describing tool capabilities to language models.**

| Provider   | Feature              | Schema Format      | Year Standardized |
|------------|----------------------|--------------------|-------------------|
| OpenAI     | Function Calling     | JSON Schema        | 2023 (GA 2024)    |
| Anthropic  | Tool Use / MCP       | JSON Schema        | 2024              |
| Google     | Gemini Function Call | OpenAPI (JSON Schema subset) | 2024   |
| OpenAI     | Structured Outputs   | JSON Schema strict | 2024              |
| Anthropic  | MCP v2025-06-18      | JSON Schema + outputSchema | 2025     |
| Google     | A2A Protocol         | JSON (Agent Cards) | 2025              |

This convergence was not coordinated. It emerged because JSON Schema
uniquely satisfies four requirements that no other format handles well:

1. **Machine-parseable**: An LLM can read a schema and understand what
   parameters a function expects, their types, and constraints.
2. **Validatable**: Both caller and callee can validate payloads against
   the schema, catching errors before execution.
3. **Self-documenting**: Field descriptions, titles, and examples are
   embedded in the schema itself --- no separate documentation needed.
4. **Composable**: Schemas reference other schemas via `$ref` and
   `$defs`, enabling complex nested structures without duplication.

The implication is clear: **any system that already produces rich JSON
Schema is, structurally, already producing agent tool definitions.** The
remaining work is formatting, not fundamental.

---

## 2. Protocol Comparison: How the Big Three Define Tools

### OpenAI Function Calling

OpenAI's tool definitions wrap a JSON Schema `parameters` object inside
a function descriptor:

```json
{
  "type": "function",
  "function": {
    "name": "create_product",
    "description": "Create a new product in the catalog",
    "strict": true,
    "parameters": {
      "type": "object",
      "properties": {
        "name": {
          "type": "string",
          "description": "Product name",
          "minLength": 1,
          "maxLength": 200
        },
        "price": {
          "type": "number",
          "description": "Product price",
          "exclusiveMinimum": 0
        },
        "description": {
          "type": "string",
          "description": "Product description"
        }
      },
      "required": ["name", "price"],
      "additionalProperties": false
    }
  }
}
```

With `strict: true`, OpenAI guarantees the model's output will exactly
match the schema --- no hallucinated fields, no missing required
parameters. This is not "best effort"; it is constrained decoding at
the token level.

### Anthropic MCP Tool Definition

MCP (Model Context Protocol) uses a nearly identical structure, with
`inputSchema` carrying the JSON Schema:

```json
{
  "name": "create_product",
  "title": "Create Product",
  "description": "Create a new product in the catalog",
  "inputSchema": {
    "type": "object",
    "properties": {
      "name": {
        "type": "string",
        "description": "Product name"
      },
      "price": {
        "type": "number",
        "description": "Product price"
      },
      "description": {
        "type": "string",
        "description": "Product description"
      }
    },
    "required": ["name", "price"]
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "id": { "type": "integer" },
      "name": { "type": "string" },
      "price": { "type": "number" }
    },
    "required": ["id", "name", "price"]
  }
}
```

As of the MCP 2025-06-18 spec update, `outputSchema` and
`structuredContent` were added, enabling validated structured responses
from tools --- not just validated inputs.

### Google Gemini Function Declaration

Google uses an OpenAPI-compatible subset of JSON Schema:

```json
{
  "name": "create_product",
  "description": "Create a new product in the catalog",
  "parameters": {
    "type": "object",
    "properties": {
      "name": {
        "type": "string",
        "description": "Product name"
      },
      "price": {
        "type": "number",
        "description": "Product price"
      }
    },
    "required": ["name", "price"]
  }
}
```

### The Pattern

Strip the outer wrapper, and all three providers are asking for the
same thing:

```
name        : string       -- what to call it
description : string       -- what it does (for the LLM)
inputSchema : JSON Schema  -- what it accepts
outputSchema: JSON Schema  -- what it returns (optional)
```

**This is not a coincidence. This is a protocol.** Any system that can
produce `{ name, description, inputSchema, outputSchema }` can
participate in the agent ecosystem across all three major providers.

---

## 3. MCP Deep Dive: Anthropic's Schema-Native Standard

### What MCP Is

The Model Context Protocol, open-sourced by Anthropic in November 2024,
is a JSON-RPC 2.0 based protocol for connecting AI applications to
external data and tools. It defines three primitives:

- **Tools**: Functions the model can execute (schema-defined)
- **Resources**: Data the model can read (URI-addressed)
- **Prompts**: Templated interaction patterns

By early 2026, MCP has become the de facto standard for tool
integration, supported by Claude, Cursor, Windsurf, and over 100 other
AI applications.

### MCP Tool Lifecycle

```
1. Discovery    Client sends tools/list
                Server responds with array of tool definitions
                Each tool has name + description + inputSchema

2. Selection    LLM reads tool schemas, selects appropriate tool

3. Invocation   Client sends tools/call with { name, arguments }
                Server validates arguments against inputSchema
                Server executes tool logic
                Server returns { content, structuredContent, isError }

4. Evolution    Server sends notifications/tools/list_changed
                Client re-fetches tool list
                LLM adapts to new capabilities automatically
```

### Key MCP Design Decisions

1. **`inputSchema` follows JSON Schema Draft 2020-12** by default (or
   Draft-07 if explicitly specified via `$schema`).

2. **`outputSchema` is optional but recommended** --- when present,
   servers MUST return `structuredContent` that conforms to it.

3. **Tool annotations** describe behavioral properties (read-only vs.
   destructive, idempotent vs. not). These are explicitly **untrusted**
   unless the server is trusted.

4. **`listChanged` notifications** allow servers to push schema changes
   to clients, enabling runtime capability evolution.

### Alignment with PyBend

Consider what PyBend's `ProtoModel.schema()` already produces:

| MCP Concept       | PyBend Equivalent                       |
|--------------------|-----------------------------------------|
| Tool `name`        | Method name from `@expose_route`        |
| Tool `description` | Method docstring or route path          |
| `inputSchema`      | `schema.methods[name].parameters`       |
| `outputSchema`     | `schema.methods[name].returns`          |
| Tool annotations   | `schema.methods[name].access`           |
| `tools/list`       | `GET /{ClassName}` returns full schema  |
| `listChanged`      | Server restart / schema cache invalidation |
| Resources          | Entity instances (`GET /{tablename}/{id}`) |

The structural overlap is remarkable. PyBend's schema output is not a
tool definition format, but it contains everything a tool definition
needs. The gap is formatting, not content.

---

## 4. PyBend Schema Anatomy: What Already Exists

When a client requests `GET /Product`, PyBend returns a JSON Schema
document that carries far more than type definitions. Here is the
actual structure:

```json
{
  "$schema": "http://localhost:5000/Schema",
  "$id": "http://localhost:5000/Product",
  "__name__": "Product",
  "__tablename__": "products",

  "properties": {
    "name": {
      "type": "string",
      "minLength": 1,
      "maxLength": 200,
      "title": "Name",
      "ui": { "placeholder": "Product name..." }
    },
    "price": {
      "type": "number",
      "exclusiveMinimum": 0,
      "title": "Price",
      "ui": { "widget": "currency" },
      "access": { "view": "anyone", "edit": "admin" }
    },
    "description": {
      "type": "string",
      "default": "",
      "title": "Description",
      "ui": { "widget": "textarea" }
    },
    "comments": {
      "type": "array",
      "items": { "$ref": "#/$defs/Comment" },
      "title": "Comments"
    }
  },

  "methods": {
    "comment": {
      "route": "/comment",
      "methods": ["POST"],
      "scope": "instancemethod",
      "parameters": {
        "comment": {
          "$ref": "#/$defs/Comment",
          "properties": { "name": {...}, "description": {...} }
        }
      },
      "returns": { "type": "string" },
      "access": { "rule": "authenticated" }
    },
    "favorite": {
      "route": "/favorite",
      "methods": ["POST"],
      "scope": "instancemethod",
      "parameters": {},
      "returns": { "type": "string" },
      "access": { "rule": "authenticated" }
    }
  },

  "access": {
    "read":   { "rule": "anyone" },
    "create": { "rule": "authenticated" },
    "update": { "op": "or", "rules": [
      { "rule": "owner" },
      { "rule": "role", "roles": ["admin"] }
    ]},
    "delete": { "rule": "role", "roles": ["admin"] }
  },

  "ui": {
    "field_order": ["name", "price", "description", "comments", "favorites"],
    "groups": {
      "main": ["name", "description", "price"],
      "Social": ["comments", "favorites"]
    },
    "methods": {
      "comment": {
        "layout": "inline",
        "attach_to": "comments",
        "button_label": "Post"
      }
    }
  },

  "$defs": {
    "Comment": {
      "$id": "http://localhost:5000/Comment",
      "properties": { "name": {...}, "description": {...} },
      "methods": { "like": {...}, "reply": {...} },
      "access": { "read": {"rule": "anyone"}, ... }
    }
  }
}
```

### What the schema already carries

| Concern                | Schema Section                    | Agent Relevance                        |
|------------------------|-----------------------------------|----------------------------------------|
| Entity structure       | `properties`                      | Input/output validation                |
| Callable operations    | `methods`                         | Tool definitions                       |
| Input parameters       | `methods.*.parameters`            | Tool inputSchema                       |
| Return types           | `methods.*.returns`               | Tool outputSchema                      |
| Authorization rules    | `access`, `methods.*.access`      | Permission checks, safety annotations  |
| Relationships          | `$defs`, `$ref`                   | Multi-entity capability mapping        |
| CRUD endpoints         | `__tablename__`, `$id`            | Resource addressing                    |
| UI rendering hints     | `ui`                              | Human-in-the-loop form generation      |
| Validation constraints | `minLength`, `gt`, `required`     | Input validation                       |
| Self-identification    | `$schema`, `$id`                  | Agent self-description                 |

This is not a web framework's schema. **This is already an agent
capability manifest** --- it just needs a translation layer to speak
the right protocol.

---

## 5. The Translation Layer: Schema to Tool Definition

### PyBend Method to MCP Tool

The transformation from a PyBend `@expose_route` method to an MCP tool
definition is mechanical:

```python
# PyBend model method
class Product(ProtoModel):
    @expose_route('/comment', methods=['POST'], access=AUTHENTICATED)
    def comment(self, comment: Comment, user: User = None) -> str:
        """Add a comment to the product."""
        ...
```

PyBend's `__pybend_methods_json_signature__()` already produces:

```json
{
  "comment": {
    "route": "/comment",
    "methods": ["POST"],
    "scope": "instancemethod",
    "parameters": {
      "comment": {
        "$ref": "#/$defs/Comment",
        "properties": {
          "name": { "type": "string", "minLength": 1, "maxLength": 500 },
          "description": { "type": "string", "default": "" }
        },
        "required": ["name"]
      }
    },
    "returns": { "type": "string" },
    "access": { "rule": "authenticated" }
  }
}
```

The MCP equivalent:

```json
{
  "name": "product_comment",
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
          "name": { "type": "string", "minLength": 1, "maxLength": 500 },
          "description": { "type": "string", "default": "" }
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

### The Translation Function

A general-purpose translator from PyBend schema to MCP tools:

```python
def schema_to_mcp_tools(schema: dict) -> list[dict]:
    """Convert a PyBend model schema to MCP tool definitions."""
    tools = []
    model_name = schema.get('__name__', 'Unknown')
    tablename = schema.get('__tablename__', model_name.lower())

    # CRUD operations as tools
    crud_ops = {
        'create': {
            'description': f'Create a new {model_name}',
            'input': _properties_to_input(schema.get('properties', {})),
        },
        'read': {
            'description': f'Get a {model_name} by ID',
            'input': {'type': 'object', 'properties': {
                'id': {'type': 'integer', 'description': f'{model_name} ID'}
            }, 'required': ['id']},
        },
        'list': {
            'description': f'List all {model_name} entities',
            'input': {'type': 'object', 'properties': {
                'limit': {'type': 'integer', 'default': 20},
                'offset': {'type': 'integer', 'default': 0},
            }},
        },
        'update': {
            'description': f'Update a {model_name} by ID',
            'input': _properties_to_input(schema.get('properties', {}),
                                          include_id=True),
        },
        'delete': {
            'description': f'Delete a {model_name} by ID',
            'input': {'type': 'object', 'properties': {
                'id': {'type': 'integer', 'description': f'{model_name} ID'}
            }, 'required': ['id']},
        },
    }

    for action, config in crud_ops.items():
        access = schema.get('access', {}).get(action, {})
        tools.append({
            'name': f'{tablename}_{action}',
            'title': f'{action.title()} {model_name}',
            'description': config['description'],
            'inputSchema': config['input'],
            'annotations': _access_to_annotations(access),
        })

    # Custom methods as tools
    for method_name, method_def in schema.get('methods', {}).items():
        params = method_def.get('parameters', {})
        input_schema = {'type': 'object', 'properties': {}, 'required': []}

        # Instance methods need an entity ID
        if method_def.get('scope') == 'instancemethod':
            input_schema['properties']['id'] = {
                'type': 'integer',
                'description': f'{model_name} ID'
            }
            input_schema['required'].append('id')

        # Add method parameters
        for param_name, param_schema in params.items():
            input_schema['properties'][param_name] = param_schema
            input_schema['required'].append(param_name)

        tools.append({
            'name': f'{tablename}_{method_name}',
            'title': f'{model_name}.{method_name}()',
            'description': method_def.get('description',
                           f'Call {method_name} on {model_name}'),
            'inputSchema': input_schema,
            'annotations': _access_to_annotations(
                method_def.get('access', {})),
        })

    return tools
```

### OpenAI Function Calling Format

The same schema translates to OpenAI's format with a thin wrapper:

```python
def schema_to_openai_tools(schema: dict) -> list[dict]:
    """Convert PyBend schema to OpenAI function calling tools."""
    mcp_tools = schema_to_mcp_tools(schema)
    return [
        {
            'type': 'function',
            'function': {
                'name': tool['name'],
                'description': tool['description'],
                'strict': True,
                'parameters': _make_strict(tool['inputSchema']),
            }
        }
        for tool in mcp_tools
    ]
```

The key insight: **the translation is lossless in one direction.** A
PyBend schema contains strictly more information than any individual
tool definition format requires. It carries authorization rules, UI
hints, relationship graphs, and validation constraints that tool
definitions cannot express but agents can use.

---

## 6. Schema as Capability Declaration

### Beyond "What Inputs Do You Accept?"

Traditional tool definitions answer a narrow question: "What parameters
does this function take?" A PyBend schema answers a much richer set:

```
Traditional tool definition:
  "I accept {name: string, price: number} and return a Product"

PyBend schema declaration:
  "I am a Product entity.
   I have properties: name (string, 1-200 chars), price (number, >0),
     description (text, optional), comments (array of Comment).
   I support operations: create, read, list, update, delete.
   I also support: comment(Comment) -> str, favorite() -> str.
   Create requires authentication. Update requires ownership or admin role.
   Delete requires admin role. Comment requires authentication.
   My comments are nested entities with their own methods:
     like() and reply(text).
   Each comment has access rules: anyone can read, only owner can edit.
   My UI renders name first, then price, then description, grouped into
     'main' and 'Social' sections."
```

This is not a tool definition. **This is a capability manifest.** It
tells an agent not just what it can do, but:

- What it **should** do (access rules as guardrails)
- What it **cannot** do (permission boundaries)
- What **related capabilities** exist ($defs, relationships)
- How to **present results** to humans (UI hints)
- How to **validate** its own behavior (constraints)

### The ABAC-as-Safety-Net Pattern

PyBend's access control rules, serialized into the schema, function as
**agent safety annotations**:

```json
{
  "access": {
    "create": { "rule": "authenticated" },
    "delete": { "rule": "role", "roles": ["admin"] }
  },
  "methods": {
    "favorite": {
      "access": { "rule": "authenticated" }
    }
  }
}
```

An agent reading this schema knows:
- It cannot create anything without authenticating first
- It cannot delete anything unless acting as an admin
- It cannot invoke `favorite` without a user identity

MCP's tool annotations (readOnlyHint, destructiveHint) are a primitive
version of this. PyBend's access rules are a full Attribute-Based Access
Control system with composable operators (`|`, `&`, `~`), SQL pushdown
for efficient filtering, and per-field granularity. The access rules
even compose logically:

```python
__access__ = {
    'update': OWNER | ROLE('admin'),   # OR composition
    'publish': OWNER & Where(status='draft'),  # AND with condition
}
```

Serialized, this becomes a machine-readable policy that an agent
orchestrator can evaluate before ever making a network call.

---

## 7. Self-Describing Agents: Discovery Without Integration

### The Agent Card Pattern

Google's A2A (Agent-to-Agent) protocol introduced "Agent Cards" ---
JSON metadata documents that describe an agent's identity, capabilities,
and access patterns. An Agent Card is published at
`/.well-known/agent.json` and enables capability discovery without
any prior integration.

A PyBend application already produces something structurally
equivalent:

```
A2A Agent Card:
  GET /.well-known/agent.json
  Returns: { name, description, skills, endpoint, auth }

PyBend Schema:
  GET /Product
  Returns: { __name__, properties, methods, access, $id, $defs }

PyBend Blueprint:
  ProtoModel.blueprint()
  Returns: { "Product": {schema}, "Comment": {schema}, "User": {schema} }
```

The `ProtoModel.blueprint()` static method already aggregates schemas
for all registered models into a single document. This is, structurally,
an agent capability catalog:

```python
@staticmethod
def blueprint():
    """Returns the blueprint of registered models."""
    from pybend.core.utils.registrar import registered_models
    blueprint = {}
    for model_name, model_cls in registered_models.items():
        blueprint[model_name] = model_cls.schema()
    return blueprint
```

### Discoverable Capability Graphs

Because schemas carry `$defs` and `$ref` pointers, the relationship
graph between entities is embedded in the schema itself:

```
Product schema
  |-- methods: comment(), favorite()
  |-- $defs: Comment, Like
  |     |-- Comment.methods: like(), reply()
  |     |-- Comment.$defs: Like
  |     |-- Like (leaf entity)
  |-- access: {create: authenticated, delete: admin}
```

An agent that reads the Product schema automatically discovers:
1. Product supports CRUD + comment + favorite
2. Comments are nested under Products
3. Comments themselves support like and reply
4. The entire capability tree, with access rules at every node

No hardcoded integrations. No API documentation to parse. No SDK to
install. **Read the schema, understand the system.**

### Multi-Hop Discovery

```
Agent A reads GET /Product
  --> discovers comment() accepts Comment entity
  --> reads $defs.Comment schema
  --> discovers Comment has like() and reply() methods
  --> discovers Comment references Like entities
  --> can now orchestrate: create Product, add Comment, like Comment
```

This is the same pattern as MCP's `tools/list` followed by `tools/call`,
but with relational depth. MCP tools are flat (a list of independent
functions). PyBend schemas are a graph (entities with methods,
relationships, and nested capabilities).

---

## 8. Schema Composition: Multi-Agent Capability Maps

### The Blueprint as Agent Manifest

Consider a PyBend application with four models: Product, Comment, User,
Like. The `blueprint()` output is:

```json
{
  "Product": {
    "properties": { "name": {...}, "price": {...} },
    "methods": { "comment": {...}, "favorite": {...} },
    "access": { "create": {"rule": "authenticated"} }
  },
  "Comment": {
    "properties": { "name": {...}, "description": {...} },
    "methods": { "like": {...}, "reply": {...} },
    "access": { "create": {"rule": "authenticated"} }
  },
  "User": {
    "properties": { "name": {...}, "email": {...} },
    "methods": { "login": {...}, "register": {...} },
    "access": { "read": {"rule": "anyone"} }
  },
  "Like": {
    "properties": { "user": {...}, "created_at": {...} },
    "access": { "create": {"rule": "authenticated"} }
  }
}
```

This is a complete capability map for the entire application. An
orchestrating agent can:

1. **Enumerate all entities** --- four model types
2. **Enumerate all operations** --- CRUD on each + custom methods
3. **Understand relationships** --- Comments belong to Products, Likes
   belong to Comments
4. **Respect permissions** --- knows which operations need auth, which
   need admin
5. **Plan multi-step workflows** --- register user, create product, add
   comment, like comment

### Cross-Service Composition

If two PyBend services exist --- an e-commerce service and an analytics
service --- an orchestrating agent can compose their blueprints:

```python
# Agent orchestrator reads schemas from two services
ecommerce_blueprint = fetch("http://ecommerce:5000/blueprint")
analytics_blueprint = fetch("http://analytics:5001/blueprint")

# Combined capability map
capabilities = {
    "ecommerce": ecommerce_blueprint,
    "analytics": analytics_blueprint,
}

# Agent now knows: create products (ecommerce), analyze sales (analytics)
# No integration code. Just schema composition.
```

This is the pattern A2A aims for with Agent Cards, but PyBend's
approach carries more information per schema entry: not just "what can
I do" but "what constraints apply" and "how do the parts relate."

---

## 9. Schema Evolution: Automatic Agent Adaptation

### The Problem with Hardcoded Tool Definitions

In LangChain, CrewAI, and AutoGen, tool definitions are written in
application code:

```python
# LangChain: tool definition is in the application
class ProductSearchTool(BaseTool):
    name = "product_search"
    description = "Search for products"
    args_schema = ProductSearchInput  # Pydantic model
    def _run(self, query: str) -> str: ...
```

When the backend changes --- a field is added, a method is renamed, a
parameter type changes --- the tool definition must be manually
updated. This creates a coupling between the agent code and the service
code. In organizations with separate teams for agent development and
service development, this coupling becomes a coordination bottleneck.

### Schema-Driven Adaptation

In a schema-first architecture, tool definitions are derived at
runtime from the schema:

```
1. Service adds a new field: rating (float, 0-5)
2. Service restarts, schema regenerates automatically
3. Agent fetches schema on next interaction
4. Agent discovers new field in properties
5. Agent can now use rating in create/update operations
6. No agent code changed. No deployment needed.
```

This is exactly how MCP's `listChanged` notification works: the server
signals that tools have changed, the client re-fetches, and the LLM
adapts. PyBend's schema cache invalidation (`invalidate_schema_cache()`)
provides the backend mechanism; the frontend's `NTT.SCHEMA()` handler
already re-bootstraps the entity system from fresh schema data.

### Breaking vs. Additive Changes

Schema evolution semantics matter for agent reliability:

| Change Type          | Schema Impact           | Agent Impact             |
|----------------------|-------------------------|--------------------------|
| Add optional field   | New property in schema  | Agent can use it or not  |
| Add required field   | New required entry      | Agent must supply it     |
| Remove field         | Property disappears     | Agent stops using it     |
| Rename field         | Old gone, new appears   | Agent adapts at next fetch|
| Add method           | New entry in methods    | Agent gains capability   |
| Change access rule   | Access dict changes     | Agent updates permissions|

The key advantage: **additive changes require zero agent modification.**
A new field, a new method, a relaxed permission --- the agent reads the
updated schema and adapts. This is the same forward-compatibility
guarantee that GraphQL provides through schema evolution, but applied
to the agent interface layer.

---

## 10. Human-in-the-Loop via Schema

### The Overlooked Advantage

Every major agent framework wrestles with human-in-the-loop: how do you
let a human review, approve, or modify an agent's intended action before
it executes? LangGraph uses `interrupt()` to pause execution. CrewAI has
approval workflows. Microsoft's Agent Framework provides custom review
forms.

**PyBend already solves this problem** --- it generates HTML forms from
JSON Schema.

The `Formidable` form generator (`form.js`) takes a schema and produces
a complete, validated form:

```javascript
// form.js reads schema properties and generates form HTML
for (const [key, def] of Object.entries(schema.properties)) {
    if (def.ui?.widget === 'textarea') {
        // Generate textarea element
    } else if (def.type === 'number') {
        // Generate number input with min/max from schema
    } else if (def.type === 'string') {
        // Generate text input with minLength/maxLength
    }
}
```

This means: **any agent action that can be described by a schema can
automatically get a human review form.** The form is not hand-coded; it
is generated from the same schema that defines the tool.

### The Human-in-the-Loop Flow

```
1. Agent decides to execute: product.comment({name: "Great!", ...})

2. Orchestrator intercepts, generates form from schema:
   - Reads methods.comment.parameters.comment schema
   - Generates form with fields: name (text, required), description (textarea)
   - Pre-fills with agent's proposed values

3. Human reviews form:
   - Sees the agent's proposed comment
   - Can edit, approve, or reject
   - Form validates against schema constraints

4. On approval: orchestrator sends the (possibly modified) request

5. On rejection: agent receives denial, can try different approach
```

The schema carries everything needed for this flow:
- **Field types** determine input widgets
- **Validation constraints** enforce correctness
- **UI hints** (placeholder, widget type) improve the form
- **Access rules** determine whether the human even sees certain fields
- **Field grouping** (`ui.groups`) organizes complex forms

No other agent framework generates review forms from tool definitions.
They all require custom UI work. PyBend gets it for free because the
schema was always the single source of truth for both machine
consumption and human presentation.

### MCP Elicitation Alignment

The MCP 2025-06-18 spec added **Elicitation** --- a mechanism for
servers to request additional information from users during tool
execution. This is structurally similar to PyBend's form generation:
both use schema to describe what information is needed, and both
generate a user-facing interface from that schema.

---

## 11. Structured Outputs: Closing the Reliability Loop

### The Reliability Problem

The biggest challenge in agent systems is reliability: agents must
produce well-formed outputs that downstream systems can parse and
validate. A wrong field name, a missing required parameter, a type
mismatch --- any of these breaks the chain.

### How Pydantic Solves This

PyBend models are Pydantic models. Pydantic is already the dominant
library for structured output validation in the AI ecosystem:

- **Instructor** (11k+ GitHub stars, 3M+ monthly downloads) uses
  Pydantic models to define and validate LLM outputs.
- **PydanticAI** (Pydantic's official agent runtime) uses Pydantic
  models as output schemas.
- **OpenAI Structured Outputs** accepts Pydantic model schemas for
  response validation.

A PyBend model is simultaneously:
1. A database entity definition
2. An API request/response schema
3. A form definition
4. An LLM output schema
5. An agent tool parameter definition

```python
class Product(ProtoModel):
    name: str = Field(min_length=1, max_length=200)
    price: float = Field(gt=0)
    description: str = Field(default='')
```

This model can be used directly with Instructor:

```python
import instructor
from openai import OpenAI

client = instructor.from_openai(OpenAI())
product = client.chat.completions.create(
    model="gpt-4o",
    response_model=Product,   # PyBend model IS the validation schema
    messages=[{"role": "user", "content": "Create a laptop product"}]
)
# product is a validated Product instance, ready for product.save()
```

The bidirectional loop closes: the LLM's output is validated against
the exact same schema that the database uses for storage and the API
uses for transport. **One model, one schema, one validation boundary.**

---

## 12. Competitive Analysis: Schema-First vs. Framework-First

### LangChain

**Tool definition pattern:**
```python
class ProductTool(BaseTool):
    name = "create_product"
    description = "Create a product"
    args_schema = ProductInput  # Separate Pydantic model
    def _run(self, name: str, price: float) -> str:
        return api.create_product(name, price)
```

**Limitations:**
- Tool definitions are written separately from the service
- Schema changes require updating both the service and the tool definition
- No built-in relationship between tools (each tool is independent)
- No access control in the tool definition itself
- Over 600 integrations, but each is manually maintained

**PyBend advantage:** Tool definitions are derived from the model. The
model IS the tool schema. Zero duplication, zero drift.

### CrewAI

**Tool definition pattern:**
```python
class ProductInput(BaseModel):
    name: str = Field(description="Product name")
    price: float = Field(description="Product price")

class ProductTool(BaseTool):
    name: str = "create_product"
    description: str = "Create a product"
    args_schema: Type[BaseModel] = ProductInput
    def _run(self, name: str, price: float) -> str:
        return api.create_product(name, price)
```

**Limitations:**
- Same duplication problem as LangChain
- Role-based task assignment, but no schema-level access control
- No entity relationships in tool definitions
- No automatic UI for human review

**PyBend advantage:** Access control is embedded in the schema. Entity
relationships are first-class. Human review forms are generated
automatically.

### AutoGen

**Tool definition pattern:**
```python
@agent.register_for_llm(description="Create a product")
def create_product(name: str, price: float) -> str:
    return api.create_product(name, price)
```

**Limitations:**
- Clean function decorator pattern, but still separate from the service
- Multi-agent conversation is powerful but tools are stateless
- No schema-driven discovery across agents

**PyBend advantage:** Models are stateful entities with CRUD lifecycle.
Agents can discover capabilities via schema without knowing the
implementation. Relationships between entities are navigable.

### Comparison Matrix

```
                    LangChain  CrewAI  AutoGen  PyBend (Schema-first)
----------------------------------------------------------------------
Tool from model       No        No      No       Yes (automatic)
Schema-driven UI      No        No      No       Yes (Formidable)
Access in schema      No        No      No       Yes (ABAC)
Entity relationships  No        No      No       Yes ($defs, $ref)
Schema evolution      Manual    Manual  Manual   Automatic
Human review forms    Custom    Custom  Custom   Generated from schema
CRUD generation       No        No      No       Yes (register_routes)
MCP-compatible output Partial   No      No       Translatable
Discovery protocol    No        No      No       GET /{Model} + blueprint()
Structured validation External  External External Native (Pydantic)
```

The fundamental difference: agent frameworks define tools as wrappers
around services. A schema-first framework defines services that **are**
tools. The wrapper disappears.

---

## 13. The "Define a Model, Get an Agent" Architecture

### What This Means Concretely

Today, `define a model, get an app` means:

```python
class Product(ProtoModel):
    __tablename__ = 'products'
    __storable__ = True
    name: str = Field(min_length=1, max_length=200)
    price: float = Field(gt=0)

app = create_app(models=[Product])
# Result: CRUD API + JSON Schema + database + web UI
```

`Define a model, get an agent` means the same model definition also
produces:

```
1. MCP Server         tools/list returns CRUD + method tools
                      tools/call routes to existing API endpoints
                      resources/list returns entity instances

2. OpenAI Tools       Function definitions for all model operations
                      Strict mode enabled by default

3. Agent Card         /.well-known/agent.json for A2A discovery
                      Lists all model capabilities + auth requirements

4. Human Review       Schema-generated approval forms for any action
                      Pre-filled with agent-proposed values

5. Structured I/O     Pydantic models as LLM response validators
                      Same model validates agent output + database input
```

### Architecture Diagram

```
                    PyBend Model Definition
                    ========================
                    class Product(ProtoModel):
                        name: str
                        price: float
                        @expose_route('/analyze')
                        def analyze(self): ...
                            |
                            v
                    ProtoModel.schema()
                    ====================
                    JSON Schema with properties,
                    methods, access, $defs, ui
                            |
            +---------------+----------------+
            |               |                |
            v               v                v
    Web Application    Agent Interfaces    Human Interfaces
    ===============    ================    ================
    FastAPI routes     MCP tools/list     Formidable forms
    CRUD endpoints     OpenAI functions   Review/approve UI
    Frontend NTT       A2A Agent Card     Field validation
    ntt-list/item      Gemini tools       Access-aware views
            |               |                |
            +---------------+----------------+
                            |
                            v
                    Single Source of Truth
                    ======================
                    One model. One schema.
                    Multiple consumers.
```

### The Implementation Path

The path from current state to agent-native is surprisingly short:

**Already exists (zero new code needed):**
- JSON Schema generation from models
- Method signatures with parameters and return types
- Access rules serialized to JSON
- Validation constraints in schema
- Entity relationships via $defs
- Form generation from schema
- Blueprint aggregation across models

**Translation layers needed (thin wrappers):**
- `schema_to_mcp_tools()`: Convert methods to MCP tool format
- `schema_to_openai_tools()`: Convert methods to OpenAI function format
- `schema_to_agent_card()`: Generate A2A discovery document
- MCP JSON-RPC handler: Route `tools/call` to existing API endpoints

**New capabilities (modest additions):**
- MCP transport layer (JSON-RPC over stdio or HTTP/SSE)
- `listChanged` notifications on schema cache invalidation
- Resource exposure for entity instances
- Prompt templates for common model operations

The total new code for MCP support is estimated at 200-400 lines ---
the rest is already built.

---

## 14. Implementation Roadmap

### Phase 1: Translation Layer (1-2 weeks)

Implement `schema_to_mcp_tools()` and expose via MCP server.

```python
# New file: src/pybend/core/mcp/server.py
from pybend.core.models.proto_model import ProtoModel

class PyBendMCPServer:
    """MCP server that exposes PyBend models as tools."""

    def handle_tools_list(self) -> dict:
        tools = []
        for model_name, model_cls in registered_models.items():
            schema = model_cls.schema()
            tools.extend(schema_to_mcp_tools(schema))
        return {"tools": tools}

    def handle_tools_call(self, name: str, arguments: dict) -> dict:
        # Route to existing FastAPI endpoints
        model_name, operation = name.rsplit('_', 1)
        # ... dispatch to existing CRUD/method handlers
```

### Phase 2: Agent Discovery (1 week)

Expose blueprint as A2A-compatible agent card.

```python
# New route: GET /.well-known/agent.json
@router.get("/.well-known/agent.json")
async def agent_card():
    return {
        "name": config.APP_NAME,
        "description": "PyBend application",
        "version": "1.0",
        "url": config.API_URL,
        "capabilities": {
            "tools": True,
            "resources": True,
            "streaming": False,
        },
        "skills": [
            {
                "name": model_name,
                "description": f"CRUD and custom operations for {model_name}",
                "schema": f"{config.API_URL}/{model_name}",
            }
            for model_name in registered_models
        ],
        "authentication": {
            "type": "bearer",
            "scheme": "JWT",
        }
    }
```

### Phase 3: Structured Output Integration (1 week)

Enable PyBend models as Instructor/PydanticAI response validators.

```python
# Using existing PyBend models with Instructor
from pybend.example.models.product import Product
import instructor

client = instructor.from_openai(OpenAI())
product = client.chat.completions.create(
    model="gpt-4o",
    response_model=Product,
    messages=[{
        "role": "user",
        "content": "Create a gaming laptop, priced around $1500"
    }]
)

# product is a validated Product instance
product.save()  # Direct to database via StorableMixin
```

### Phase 4: Human-in-the-Loop Forms (1 week)

Add agent action review to the existing form generation pipeline.

```javascript
// Extend Formidable to generate review forms from agent actions
class AgentReviewForm extends NTTElement {
    static DESCRIBE(data) {
        const { action, schema, proposed_values } = data;
        // Generate form from schema
        const form = Formidable.getForm(schema, proposed_values);
        // Add approve/reject buttons
        form.append(approveButton, rejectButton);
        return form;
    }
}
```

### Phase 5: Multi-Agent Composition (2-3 weeks)

Enable cross-service schema composition for agent orchestration.

```python
# Agent orchestrator discovers and composes capabilities
class AgentOrchestrator:
    def discover(self, service_urls: list[str]):
        """Fetch and compose blueprints from multiple services."""
        self.capabilities = {}
        for url in service_urls:
            blueprint = fetch(f"{url}/blueprint")
            for model_name, schema in blueprint.items():
                tools = schema_to_mcp_tools(schema)
                self.capabilities[f"{url}/{model_name}"] = tools

    def plan(self, goal: str) -> list[dict]:
        """Use LLM to plan a sequence of tool calls."""
        # Feed all capabilities to LLM, get execution plan
        ...
```

---

## 15. Sources

1. [OpenAI Function Calling Documentation](https://platform.openai.com/docs/guides/function-calling) --- Function calling with JSON Schema tool definitions, strict mode, and structured outputs.

2. [OpenAI Structured Outputs](https://openai.com/index/introducing-structured-outputs-in-the-api/) --- Constrained decoding ensuring model outputs match JSON Schema exactly.

3. [MCP Specification (2025-11-25)](https://modelcontextprotocol.io/specification/2025-11-25) --- Model Context Protocol specification: tools, resources, prompts.

4. [MCP Tools Specification (Draft)](https://modelcontextprotocol.io/specification/draft/server/tools) --- Detailed tool definition format with inputSchema, outputSchema, annotations.

5. [MCP 2025-06-18 Spec Update](https://forgecode.dev/blog/mcp-spec-updates/) --- Added structured output, OAuth 2.0 resource server classification, elicitation.

6. [Google Gemini Function Calling](https://ai.google.dev/gemini-api/docs/function-calling) --- OpenAPI-compatible JSON Schema for Gemini tool declarations.

7. [Google A2A Protocol Announcement](https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/) --- Agent-to-Agent protocol with Agent Cards for capability discovery.

8. [A2A Protocol Overview](https://a2a-protocol.org/latest/specification/) --- Agent Cards, discovery via /.well-known/agent.json, skill definitions.

9. [Instructor Library](https://python.useinstructor.com/) --- Pydantic-based structured output extraction from LLMs, 3M+ monthly downloads.

10. [PydanticAI Agent Runtime](https://ai.pydantic.dev/) --- Official Pydantic agent framework using models as output schemas.

11. [LangChain StructuredTool](https://api.python.langchain.com/en/latest/tools/langchain_core.tools.StructuredTool.html) --- Tool definitions with Pydantic args_schema.

12. [CrewAI Custom Tools](https://docs.crewai.com/en/learn/create-custom-tools) --- BaseTool with Pydantic args_schema for input validation.

13. [OpenAI Agents SDK Tool Schemas](https://openai.github.io/openai-agents-python/ref/function_schema/) --- Function schema generation from callables.

14. [Comparing AI Agent Frameworks (Langfuse)](https://langfuse.com/blog/2025-03-19-ai-agent-comparison) --- LangChain vs. CrewAI vs. AutoGen architecture comparison.

15. [AI Agent Frameworks 2026 (Turing)](https://www.turing.com/resources/ai-agent-frameworks) --- Comprehensive framework comparison including tool definition patterns.

16. [AgenticAPI](https://agenticapi.com/) --- Self-describing API standard with OpenAPI extensions for agent interaction.

17. [Pydantic for LLMs](https://pydantic.dev/articles/llm-intro) --- How Pydantic models serve as JSON Schema generators for LLM applications.

18. [Human-in-the-Loop for AI Agents (Permit.io)](https://www.permit.io/blog/human-in-the-loop-for-ai-agents-best-practices-frameworks-use-cases-and-demo) --- Best practices for human oversight in agent workflows.

19. [Human-in-the-Loop Workflows (Microsoft)](https://learn.microsoft.com/en-us/agent-framework/workflows/human-in-the-loop) --- Microsoft Agent Framework patterns for human approval.

20. [MCP Schema Registry Transformation](https://medium.com/@aywengo/mcp-2025-06-18-revolutionized-everything-our-schema-registry-server-transformation-8ca027c296f4) --- Schema registry patterns for MCP tool management.

---

## Conclusion

The AI agent ecosystem has converged on JSON Schema as the universal
interface format. Every major provider --- OpenAI, Anthropic, Google ---
uses it for tool definitions. Every major framework --- LangChain,
CrewAI, AutoGen --- uses Pydantic (which generates JSON Schema) for
input validation.

A framework whose core architecture already produces rich, validated,
self-describing JSON Schema for every model in the system has a
structural advantage that purpose-built agent frameworks cannot match.
Those frameworks build tools as wrappers around services. A schema-first
framework's services **are** tools.

The gap between "define a model, get an app" and "define a model, get
an agent" is not a rewrite. It is not even a major feature. It is a
set of thin translation layers --- 200-400 lines of new code --- that
convert an already-complete capability manifest into the formats that
agent protocols expect.

The deeper advantage is architectural: when the schema is the single
source of truth, schema evolution automatically propagates to every
consumer --- human interfaces, machine interfaces, agent interfaces.
No integration updates. No SDK bumps. No coordination across teams.
The model changes, the schema regenerates, and every agent in the
ecosystem adapts.

**The question is not whether schema-driven frameworks will play a role
in the agent ecosystem. The question is how quickly they move from
"happens to produce the right format" to "deliberately serves as the
agent interface layer."**
