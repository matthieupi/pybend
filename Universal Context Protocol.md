# Universal Context Protocol (UCP) Specification — Draft v0.1

## Introduction
The **Universal Context Protocol (UCP)** is a specification designed to enable seamless and standardized communication between heterogeneous backend systems and user interfaces. UCP aims to provide a machine-inspectable and semantically rich context model for interoperable data exchange, introspection, and presentation.

UCP is inspired by the strengths of GraphQL, JSON Schema, and REST, while simplifying the protocol to support wide adoption across backends with minimal implementation effort.

---

## Goals

- 📡 Define a protocol enabling frontends to query and interact with arbitrary backend services.
- 🧠 Encode machine-readable schema for all accessible objects.
- 🔍 Enable schema discovery, introspection, and contextual documentation.
- 🔄 Support dynamic UI rendering from backend types.
- 🧩 Be backend-agnostic and compatible with REST, RPC, and WebSocket-style APIs.

---

## Architecture Overview

- **Schema Endpoint**: Provides the introspectable type and endpoint structure.
- **Context Objects**: Objects provided by the backend, described using UCP Type Schema.
- **Operations**: Actions (GET, POST, PUT, DELETE) described declaratively alongside schemas.
- **Frontend Resolver**: Client-side interpreter that reads UCP schema and dynamically builds UI/forms.

---

## Core Concepts

### 1. UCP Schema
Each backend implements a single schema endpoint, e.g. `/ucp/schema`, returning a full description of types and endpoints:

```json
{
  "version": "0.1",
  "types": { "User": {...}, "Product": {...} },
  "endpoints": [
    {
      "route": "/users",
      "method": "POST",
      "input": "User",
      "output": "User"
    },
    {
      "route": "/products/list",
      "method": "GET",
      "output": "Product[]"
    }
  ]
}
```

### 2. Type Descriptions
Each UCP ProtoType contains:

```json
{
  "prototype": "<Class Name>",
  "description": "A human readable description of the type. It will be used for documentation and LLM parsing purposes.",
  "fields": {
    "id": { "type": "int", "readOnly": true },
    "name": { "type": "string" },
    "email": { "type": "string", "format": "email" }
  }
}
```

### 3. Instanciated object representation

### 4. Endpoint Objects
Each operation endpoint includes:
- `route`: Relative URL
- `method`: HTTP verb
- `input`: Optional input type (UCP type reference)
- `output`: Output type or array

---

## Specification Requirements

### Minimal Backend Support
A UCP-compliant server must:
- Serve a static or dynamic `/ucp/schema` endpoint that provides the 
  server's topology
- Serve a static or dynamic `/ucp/<prototype>` endpoint that provides the
  prototype for a given type
- Provide type metadata for all exposed objects
- Provide endpoint metadata for all operations

### Roadmap features
- `examples`, `descriptions`, and `tags` fields for documentation
- `permissions`, `validators`, and `hints` for frontend rendering

---

## Roadmap

### v0.1 (Current)
- Type and endpoint schema definitions
- Static discovery format

### v0.2
- Server metadata (name, description, auth info)
- Partial query introspection (field subsets)

### v1.0
- Dynamic resolvers
- Standardized error model
- WebSocket or subscription support

---

## Comparison with GraphQL
| Feature                | UCP           | GraphQL        |
|------------------------|----------------|----------------|
| Introspection         | ✅             | ✅              |
| REST compatibility    | ✅             | ❌              |
| Type system           | JSON-inspired  | GraphQL Schema |
| Transport flexibility | ✅ (HTTP/WS/etc)| Mostly HTTP     |
| Frontend dynamic UI   | ✅             | ⚠️ (custom tooling required) |

---

## License
UCP is released under the MIT License.

---

## Contributions
This is a working draft. Feedback, proposals, and reference implementations are welcome via GitHub Issues or Pull Requests.

