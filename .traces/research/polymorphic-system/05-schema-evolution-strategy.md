# Schema Polymorphism as an Evolution Strategy

**Using discriminator-based schemas for API versioning, plugin architectures, and progressive type systems**

*Research Document -- February 2026*

---

## Executive Summary

Polymorphic data systems -- models that share a base type but carry different specializations -- are everywhere: Stripe's payment methods, Notion's block types, GitHub's webhook events, every CMS content model. The question is not whether your system needs polymorphism, but how you encode it.

This document argues that **discriminator-based schema polymorphism** is not just a modeling technique. It is an **evolution strategy** -- one that lets you version APIs without breaking clients, support plugin architectures without forking core code, and build progressive type systems where a single declaration propagates through storage, API, and UI layers simultaneously.

The core thesis: when the discriminator lives in the schema (not in application logic), three things become possible that are otherwise expensive:

1. **Backward-compatible API evolution** -- new types join the union without touching existing clients.
2. **Runtime extensibility** -- user-defined types register at startup (or later) without redeployment.
3. **Three-layer propagation** -- a single `type` field declaration cascades from database column to API schema to UI form adaptation.

We examine how this plays out across JSON Schema, OpenAPI 3.1, GraphQL, event sourcing registries, and schema-driven frameworks like PyBend.

---

## Table of Contents

1. [Foundations: What Schema Polymorphism Is](#1-foundations)
2. [Schema Polymorphism for API Versioning](#2-api-versioning)
3. [Plugin and Extension Architectures](#3-plugin-architectures)
4. [Runtime Type Registration](#4-runtime-type-registration)
5. [Type Narrowing and Widening](#5-type-narrowing-and-widening)
6. [Event-Driven Polymorphism](#6-event-driven-polymorphism)
7. [Polymorphic Search and Filtering](#7-polymorphic-search)
8. [Case Studies](#8-case-studies)
9. [The Schema-Driven Advantage](#9-schema-driven-advantage)
10. [Decision Framework](#10-decision-framework)
11. [Sources](#11-sources)

---

## 1. Foundations: What Schema Polymorphism Is {#1-foundations}

Polymorphism in data systems means a single collection (endpoint, table, index, topic) holds items that share a common structure but vary by type. The **discriminator** is the field that tells you which variant you are looking at.

### Three encoding strategies

| Strategy | Mechanism | JSON Schema keyword | OpenAPI keyword | Example |
|----------|-----------|-------------------|-----------------|---------|
| **Tagged union** | Explicit `type` field with `const` per variant | `oneOf` + `const` discriminator | `discriminator.propertyName` | Stripe `PaymentMethod.type` |
| **Structural union** | No tag; validators try each schema | `anyOf` (try all, accept first match) | N/A | Legacy APIs with implicit typing |
| **Interface inheritance** | Shared base fields, type-specific extensions | `allOf` (base + extension) | `allOf` + `discriminator` | GraphQL interfaces |

> **Key insight for leadership:** Tagged unions with an explicit discriminator field are overwhelmingly preferred in production systems. Stripe, GitHub, Notion, Figma, CloudEvents, and every major schema registry all use an explicit `type` field. The pattern is settled. The remaining design question is how to propagate that discriminator through your stack.

### The discriminator in JSON Schema (Draft 2020-12)

```json
{
  "oneOf": [
    {
      "type": "object",
      "properties": {
        "type": { "const": "card" },
        "last4": { "type": "string" },
        "exp_month": { "type": "integer" }
      },
      "required": ["type"]
    },
    {
      "type": "object",
      "properties": {
        "type": { "const": "bank_transfer" },
        "bank_name": { "type": "string" },
        "iban": { "type": "string" }
      },
      "required": ["type"]
    }
  ],
  "discriminator": { "propertyName": "type" }
}
```

JSON Schema can handle polymorphism without the `discriminator` keyword -- validators can test each `oneOf` branch sequentially. But the discriminator serves two purposes: it makes validation O(1) instead of O(n), and it makes the intent **machine-readable** so code generators, UI frameworks, and documentation tools can act on it.

### The discriminator in OpenAPI 3.1

OpenAPI 3.1 adopted full JSON Schema compatibility and added a `mapping` property to the discriminator object:

```yaml
components:
  schemas:
    PaymentMethod:
      oneOf:
        - $ref: '#/components/schemas/CardPayment'
        - $ref: '#/components/schemas/BankTransfer'
      discriminator:
        propertyName: type
        mapping:
          card: '#/components/schemas/CardPayment'
          bank_transfer: '#/components/schemas/BankTransfer'
```

The `mapping` solves a practical problem: when the discriminator value (`card`) does not match the schema name (`CardPayment`), the mapping provides the bridge. Without it, OpenAPI assumes the discriminator value is the schema name -- a constraint that rarely holds in real APIs.

---

## 2. Schema Polymorphism for API Versioning {#2-api-versioning}

### The version-as-type pattern

Instead of maintaining parallel `/v1/` and `/v2/` URL trees, a schema-polymorphic API can serve multiple response shapes from a single endpoint, using content negotiation or a version discriminator.

**Traditional versioning (endpoint proliferation):**

```
GET /v1/products     -> { name, price }
GET /v2/products     -> { name, price, variants: [...], seo: {...} }
GET /v3/products     -> { name, pricing: { base, tiers: [...] }, variants, seo }
```

**Schema-polymorphic versioning (single endpoint, negotiated shape):**

```
GET /products
Accept: application/vnd.api+json; version=3

Response schema: oneOf [ProductV1, ProductV2, ProductV3]
discriminator: { propertyName: "$schema_version" }
```

### Progressive type narrowing

The pattern works because each version is an `allOf` extension of the previous -- `ProductV2` uses `allOf: [$ref: ProductV1, { new fields }]` to extend without replacing. **V1 clients** ignore fields they do not recognize (standard JSON forward-compatibility). **V2 clients** get the full shape. The server returns the richest version; clients consume what they understand.

### Backward-compatible evolution rules

| Change type | Backward compatible? | Forward compatible? | Strategy |
|------------|---------------------|--------------------|---------|
| Add optional field | Yes | Yes | Simply add; old clients ignore it |
| Add required field | No | Yes | Provide default or make optional in base |
| Remove field | Yes | No | Deprecate, then remove after migration window |
| Rename field | No | No | Add new field, alias old, deprecate |
| Change field type | No | No | New field with new name; old field unchanged |
| Add new `oneOf` variant | Yes | Yes | Old clients never produce the new type |
| Remove `oneOf` variant | No | Yes | Migration required for existing data |

> **For the CEO:** Schema-based versioning means your API can grow new features (new fields, new types) without breaking any existing integration. Clients that were built against version 1 continue to work unchanged when version 3 ships. The only time you need a breaking change is when you *remove* something -- and the schema makes that visible and testable before deployment.

### How GraphQL handles this

GraphQL takes a different but philosophically aligned approach: **interfaces** define the base contract, **inline fragments** select type-specific fields.

```graphql
interface Node {
  id: ID!
  type: String!
}

type Article implements Node {
  id: ID!
  type: String!
  title: String!
  body: String!
}

type Video implements Node {
  id: ID!
  type: String!
  url: String!
  duration: Int!
}

query {
  feed {
    ... on Article { title, body }
    ... on Video { url, duration }
  }
}
```

The `__typename` field is the implicit discriminator -- always present, always queryable. GraphQL's evolution model avoids versioning entirely: you add fields and types; you deprecate old ones with `@deprecated`. Clients request exactly what they need. The schema is the version.

| Aspect | REST + OpenAPI | GraphQL |
|--------|---------------|---------|
| Discriminator | Explicit `type` field | Implicit `__typename` |
| Version mechanism | URL path, header, or schema version | Field-level deprecation |
| New type addition | Add to `oneOf` | Add implementing type |
| Client adaptation | Content negotiation | Query change |
| Schema delivery | `GET /schema` or OpenAPI spec | Introspection query |
| Breaking change risk | Medium (requires discipline) | Low (additive-only culture) |

---

## 3. Plugin and Extension Architectures {#3-plugin-architectures}

Polymorphic schemas are the backbone of every extensible platform. The pattern: a platform defines base types; extensions add specialized subtypes that conform to the base contract.

### WordPress: Custom post types as polymorphic content

WordPress's `register_post_type()` is runtime polymorphism in action:

```php
register_post_type('event', [
    'label' => 'Events',
    'public' => true,
    'show_in_rest' => true,       // Exposes via REST API
    'supports' => ['title', 'editor', 'thumbnail'],
]);
```

Every custom post type shares the `wp_posts` table (single-table inheritance with `post_type` as the discriminator). The REST API auto-generates endpoints at `/wp/v2/event`. Custom fields extend the shape via ACF or meta fields, each accessible through the same API structure.

**Architecture:**

```
wp_posts table
  ├── post_type = 'post'    -> /wp/v2/posts
  ├── post_type = 'page'    -> /wp/v2/pages
  ├── post_type = 'event'   -> /wp/v2/event    (plugin-defined)
  └── post_type = 'product' -> /wp/v2/product   (WooCommerce)
```

### Shopify: Metafield types as schema extension

Shopify takes a different approach -- the base types (Product, Order, Customer) are fixed, but **metafields** let merchants extend them with typed data:

```graphql
mutation {
  metafieldDefinitionCreate(definition: {
    name: "Warranty Period"
    namespace: "custom"
    key: "warranty_months"
    type: "number_integer"
    ownerType: PRODUCT
    validations: [{ name: "min", value: "0" }, { name: "max", value: "120" }]
  }) {
    createdDefinition { id }
  }
}
```

The metafield system is polymorphic at the value level -- a single `metafields` collection holds values of type `number_integer`, `single_line_text_field`, `json`, `file_reference`, etc. The `type` field on each metafield definition is the discriminator that drives both validation and UI rendering.

For richer structures, **metaobjects** provide user-defined types with multiple fields, each with its own type -- effectively a runtime schema system:

```
Metaobject Definition: "Material"
  ├── name: single_line_text_field
  ├── density: number_decimal
  ├── origin_country: single_line_text_field
  └── certification: file_reference
```

### Strapi / Contentful: Dynamic content types

Headless CMS platforms are the purest expression of runtime schema polymorphism.

**Strapi** allows content types to be created through a visual Content-Type Builder. Each content type generates:
- A database table (or collection)
- REST and GraphQL endpoints
- Admin panel CRUD interface
- TypeScript types (auto-generated)

Strapi's **Dynamic Zones** go further -- they allow a field to accept *any* of a predefined set of component types, making each record instance-level polymorphic:

```json
{
  "title": "Landing Page",
  "body": [
    { "__component": "blocks.hero", "heading": "Welcome", "image": "..." },
    { "__component": "blocks.features", "items": [...] },
    { "__component": "blocks.cta", "label": "Sign Up", "href": "/register" }
  ]
}
```

The `__component` field is the discriminator. The schema for the `body` field is an `anyOf` over registered component schemas.

**Contentful** follows a similar model: content types are defined via API or admin UI, each with up to 50 fields. The data model is API-first -- all content types, their fields, and validation rules are accessible via the Content Management API.

### JSON Schema extensibility primitives

For frameworks building their own extension systems, JSON Schema provides three mechanisms:

| Mechanism | Use case | Example |
|-----------|---------|---------|
| `additionalProperties: true` | Allow any extra fields | Base type accepts plugin-added fields |
| `patternProperties` | Fields matching a pattern | `"x-.*": { "type": "string" }` for extension fields |
| `$dynamicRef` / `$dynamicAnchor` | Runtime schema composition | Base schema references dynamic anchor; extensions provide it |

> **For leadership:** The CMS industry has converged on a pattern: define types through an admin interface, generate schemas and APIs automatically, render UI from the schema. Strapi, Contentful, Sanity, and others all work this way. Schema-driven frameworks like PyBend apply the same pattern but with code-first model definitions instead of a visual builder -- same principle, different entry point.

---

## 4. Runtime Type Registration {#4-runtime-type-registration}

### The problem: adding types without restarting

Traditional frameworks require server restarts to register new models. Schema-driven systems can do better if the registration pathway is designed for it.

### Registration flow patterns

**Static registration (most frameworks):**

```
Server start
  -> Import model modules
  -> register_model(Product, storage)
  -> register_routes(registered_models)
  -> Server ready (model set is frozen)
```

**Dynamic registration (CMS-style):**

```
Server running
  -> Admin creates "Event" content type via API
  -> System generates model class dynamically
  -> register_model(Event, storage) at runtime
  -> Schema endpoint becomes available
  -> Frontend fetches schema, creates DynamicClass
  -> UI renders "Event" CRUD immediately
```

### How this maps to PyBend's architecture

PyBend's current flow already has the primitives for runtime registration:

**Backend (`register_model` + `ProtoModel.schema()`):**

```python
# registrar.py -- the global model registry
registered_models: Dict[str, Type[Any]] = {}

def register_model(model_class, storage=None):
    if hasattr(model_class, '__storable__') and model_class.__storable__:
        model_class.set_storage(storage)
        model_class.create_table()
        if hasattr(storage, 'migrate_table'):
            storage.migrate_table(model_class)
    registered_models[model_class.__tablename__] = model_class
```

**Frontend (`NTT.SCHEMA()` + `prototype()`):** When the frontend receives a schema via `NTT.SCHEMA()`, it first iterates `$defs` to register nested types, then calls `prototype(addr, data, href)` to generate a DynamicClass -- a JavaScript class with typed properties, methods, and labels all derived from the JSON Schema document. This is already dynamic type registration. The `#prototypes` Map holds all registered DynamicClasses keyed by model name. The only missing piece for full CMS-style workflows is a backend API to create model classes from schema definitions (rather than from Python source code).

### What runtime registration requires

| Capability | Static systems | Runtime-capable systems |
|-----------|---------------|----------------------|
| Model definition | Python/Java source file | Schema document (JSON/YAML) |
| Table creation | At startup | On-demand (with migration) |
| Route creation | At startup | Hot-add to router |
| Schema endpoint | Available after boot | Available after registration |
| Frontend class | Created on first schema fetch | Same (already dynamic) |
| Schema cache invalidation | N/A | Required on type change |

### Dynamic class generation pattern (Python)

The core technique: iterate over schema `properties`, map JSON types to Python annotations, then use `type(name, (ProtoModel,), attrs)` to build the class dynamically. Set `__tablename__`, `__storable__ = True`, and call `register_model()`. This is the same pattern Strapi, Contentful, and WordPress use internally -- the entry point differs (visual builder vs. API call vs. code), but the mechanics are identical: schema in, model class out, routes generated.

---

## 5. Type Narrowing and Widening {#5-type-narrowing-and-widening}

### Progressive disclosure in schemas

Type narrowing means showing base-level information first, then revealing type-specific details on demand. This is both a UI pattern and a schema composition pattern.

**Schema composition for narrowing** uses `allOf` to layer type-specific fields onto a shared base. A `ContentBase` schema defines `id`, `type`, `title`, and `created_at`. Then `Article` uses `allOf: [ContentBase, { body, word_count, reading_time }]` with `type: { "const": "article" }`, while `Video` uses `allOf: [ContentBase, { url, duration, transcript }]` with `type: { "const": "video" }`. The base fields are always visible; type-specific fields appear only after the discriminator narrows the type.

### JSON Schema composition keywords compared

| Keyword | Semantics | Use case | Validation behavior |
|---------|-----------|---------|-------------------|
| `allOf` | Must match ALL schemas | Base + extension (inheritance) | Intersection of constraints |
| `oneOf` | Must match EXACTLY ONE | Discriminated union (alternatives) | Exclusive match required |
| `anyOf` | Must match AT LEAST ONE | Overlapping alternatives | First-match or multi-match |
| `if`/`then`/`else` | Conditional application | Type-dependent validation | Branch based on property value |

### Conditional schemas for polymorphic validation

JSON Schema Draft-07 introduced `if`/`then`/`else` for expressing type-dependent validation without `oneOf`:

```json
{
  "type": "object",
  "properties": {
    "payment_type": { "type": "string", "enum": ["card", "bank_transfer"] }
  },
  "if": {
    "properties": { "payment_type": { "const": "card" } }
  },
  "then": {
    "required": ["card_number", "exp_month", "exp_year"],
    "properties": {
      "card_number": { "type": "string", "pattern": "^[0-9]{16}$" },
      "exp_month": { "type": "integer", "minimum": 1, "maximum": 12 },
      "exp_year": { "type": "integer" }
    }
  },
  "else": {
    "required": ["iban", "bank_name"],
    "properties": {
      "iban": { "type": "string" },
      "bank_name": { "type": "string" }
    }
  }
}
```

### UI implications: adaptive forms

When the schema carries the discriminator and type-specific fields, the UI can adapt automatically:

```
User selects "Payment Type: Card"
  -> Form reads if/then/else (or oneOf with discriminator)
  -> Renders: card_number, exp_month, exp_year fields
  -> Hides: iban, bank_name fields

User switches to "Payment Type: Bank Transfer"
  -> Form re-evaluates conditional schema
  -> Renders: iban, bank_name fields
  -> Hides: card_number, exp_month, exp_year fields
```

This is the pattern that schema-driven form generators (like PyBend's `Formidable`) can implement: read the discriminator field, resolve which branch of the schema applies, render only the relevant fields.

### Widening: accepting broader types

Type widening is the inverse -- accepting a looser type where a stricter one was expected. This is the key to backward compatibility:

```
V1: price is "type": "number"
V2: price is "oneOf": [
      { "type": "number" },
      { "type": "object", "properties": { "amount": {...}, "currency": {...} } }
    ]
```

Old clients send a number. New clients send a price object. The widened schema accepts both. The server normalizes internally.

---

## 6. Event-Driven Polymorphism {#6-event-driven-polymorphism}

### Typed events in event sourcing

Event sourcing systems are inherently polymorphic -- the event store holds events of many types, all sharing a common envelope but carrying type-specific payloads.

```
Event Store (single append-only log)
  ├── OrderCreated   { order_id, customer_id, items: [...] }
  ├── OrderShipped   { order_id, tracking_number, carrier }
  ├── OrderCanceled  { order_id, reason, refund_amount }
  ├── PaymentReceived { order_id, amount, method }
  └── InventoryAdjusted { product_id, delta, reason }
```

The event `type` field is the discriminator. Every event shares a common envelope (id, timestamp, aggregate_id, type, version), but the payload schema varies by type.

### Schema registries

Schema registries enforce compatibility rules on evolving event schemas, preventing producers from publishing events that would break consumers.

**Confluent Schema Registry** supports six compatibility levels:

| Compatibility | Rule | When to use | Update order |
|--------------|------|-------------|--------------|
| **BACKWARD** | New schema can read old data | Adding optional fields | Consumers first |
| **FORWARD** | Old schema can read new data | Removing optional fields | Producers first |
| **FULL** | Both directions compatible | Adding/removing optional fields with defaults | Any order |
| **BACKWARD_TRANSITIVE** | Compatible with ALL previous versions | Long-lived schemas | Consumers first |
| **FORWARD_TRANSITIVE** | ALL previous can read new | Strict producer evolution | Producers first |
| **FULL_TRANSITIVE** | Both, against all versions | Maximum safety | Any order |

**AWS Glue Schema Registry** provides similar capabilities, supporting Avro, JSON Schema, and Protocol Buffers formats. When a new schema version is registered, it is validated against the compatibility rule. Incompatible registrations are rejected, ensuring a producer fails early rather than publishing events that downstream consumers cannot deserialize.

> **For leadership:** Schema registries are the compile-time type-checker for distributed systems. They catch schema incompatibilities at deployment time rather than at 3 AM when a consumer crashes. The cost is maintaining a registry; the benefit is that "we changed the event format and broke downstream" stops being a category of incident.

### CloudEvents: a natural discriminator standard

The CloudEvents specification defines a standard envelope for events across distributed systems. The `type` attribute is designated as the primary means by which consumers identify events:

```json
{
  "specversion": "1.0",
  "type": "com.example.order.created",
  "source": "/orders/service",
  "id": "A234-1234-1234",
  "time": "2026-01-15T10:30:00Z",
  "datacontenttype": "application/json",
  "data": {
    "order_id": "ORD-1234",
    "customer_id": "CUST-567",
    "total": 99.99
  }
}
```

The `type` field serves as a discriminator for routing, observability, policy enforcement, and handler dispatch -- "similar to HTTP's notion of methods," as the specification notes. Middleware uses it to route events to the correct consumer; consumers use it to select the correct deserialization schema.

### Event schema evolution and polymorphism intersection

When a new event type is added to an event-sourced system, it is operationally identical to adding a new variant to a polymorphic union:

```
V1 event store:  OrderCreated | OrderShipped | OrderCanceled
V2 event store:  OrderCreated | OrderShipped | OrderCanceled | OrderRefunded (new)
```

Consumers that only handle V1 types simply skip `OrderRefunded` events. This is forward-compatible by construction -- the same principle that makes `oneOf` with discriminator backward-compatible for API responses.

---

## 7. Polymorphic Search and Filtering {#7-polymorphic-search}

### Elasticsearch: the multi-type index lesson

Elasticsearch's history is a cautionary tale about implicit polymorphism. Before version 6.0, a single index could hold multiple "mapping types" -- conceptually like tables in a database. But because all types in an index shared the same underlying Lucene fields, a field named `title` in type A and `title` in type B had to have identical mappings.

**Timeline of mapping type removal:**

| Version | Behavior |
|---------|----------|
| ES 5.x | Multiple mapping types per index (legacy) |
| ES 6.x | Single mapping type per index only |
| ES 7.x | Mapping types completely removed |
| ES 8.x | No backward-compatibility support for types |

**The migration path Elasticsearch recommends** is exactly the discriminator pattern:

```json
{
  "mappings": {
    "properties": {
      "_doc_type": { "type": "keyword" },
      "title": { "type": "text" },
      "author": { "type": "keyword" },
      "duration": { "type": "integer" },
      "word_count": { "type": "integer" }
    }
  }
}
```

The `_doc_type` field is a custom discriminator. Articles have `word_count`; videos have `duration`. The index holds both. Queries filter by `_doc_type` when type-specific results are needed.

**Alternative: index-per-type.** Instead of a shared index with a discriminator, use separate indices (`articles`, `videos`) and query across them with multi-index search. This trades query flexibility for mapping independence.

### PostgreSQL table inheritance

PostgreSQL supports native table inheritance, but with significant caveats:

```sql
CREATE TABLE content (
    id SERIAL PRIMARY KEY,
    type VARCHAR(50) NOT NULL,
    title TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE article (
    body TEXT,
    word_count INTEGER
) INHERITS (content);

CREATE TABLE video (
    url TEXT,
    duration INTEGER
) INHERITS (content);
```

**Querying the parent table returns all children:**

```sql
SELECT * FROM content;          -- Returns articles AND videos
SELECT * FROM ONLY content;     -- Returns ONLY rows directly in content table
```

**Limitations that matter in practice:**

- Indexes on the parent table are NOT inherited by child tables
- Foreign keys cannot reference across the inheritance hierarchy
- `UNIQUE` constraints apply per-table, not across the hierarchy
- Query planner must scan all child tables (performance degrades with hierarchy depth)

For these reasons, most PostgreSQL users prefer the **discriminator column pattern** (single table with a `type` column) or **partitioning** (which PostgreSQL optimizes better than inheritance).

### Filtering by type in REST APIs

Two common patterns exist for polymorphic collections:

| Pattern | URL structure | Pros | Cons |
|---------|-------------|------|------|
| **Query parameter** | `GET /content?type=article` | Single endpoint, flexible filtering | Requires polymorphic response schema |
| **Dedicated endpoints** | `GET /articles`, `GET /videos` | Type-safe responses, simpler clients | Endpoint proliferation, cross-type queries harder |

**Hybrid approach (recommended):** Dedicated endpoints for type-specific operations; base endpoint with `?type=` filter for cross-type queries and discovery.

### GraphQL union type queries

GraphQL solves polymorphic querying elegantly with union types and `__typename`:

```graphql
union SearchResult = Article | Video | User

type Query {
  search(query: String!): [SearchResult!]!
}

query {
  search(query: "polymorphism") {
    __typename
    ... on Article { title, body }
    ... on Video { title, url, duration }
    ... on User { name, email }
  }
}
```

The `__typename` field is always available on every GraphQL object. Clients use it to branch rendering logic -- the exact same pattern as reading a discriminator field in a REST response.

---

## 8. Case Studies {#8-case-studies}

### Stripe: Polymorphic Payment Methods

**The evolution story:** Between 2011 and 2018, Stripe's Charge resource grew from 11 to 36 properties, and creation parameters grew from 5 to 14. The root cause was that the original API was designed around the simplest payment method (credit cards), which turned out to be the outlier -- cards were the only method that finalized immediately with no customer action.

**The polymorphic redesign:**

```json
{
  "id": "pm_1234",
  "object": "payment_method",
  "type": "card",
  "card": {
    "brand": "visa",
    "last4": "4242",
    "exp_month": 12,
    "exp_year": 2027
  }
}
```

```json
{
  "id": "pm_5678",
  "object": "payment_method",
  "type": "sepa_debit",
  "sepa_debit": {
    "bank_code": "37040044",
    "country": "DE",
    "last4": "3456"
  }
}
```

**Key design decisions:**
- `type` field is the discriminator
- Type-specific data lives in a nested hash whose key matches the `type` value
- Top-level fields are shared across all payment methods
- Adding a new payment method means adding a new `type` value and its hash -- zero changes to existing types

> **Lesson for framework builders:** Stripe's `type` field + matching nested hash pattern is the most widely imitated API polymorphism pattern in production. It is explicit, self-describing, and additively extensible.

### GitHub: Event Types API

GitHub's webhook system delivers polymorphic events to a single callback URL. The discriminator is the `X-GitHub-Event` HTTP header:

```
POST /webhook
X-GitHub-Event: push
X-GitHub-Delivery: abc-123

{
  "ref": "refs/heads/main",
  "commits": [...],
  "pusher": { "name": "octocat", "email": "..." }
}
```

```
POST /webhook
X-GitHub-Event: issues
X-GitHub-Delivery: def-456

{
  "action": "opened",
  "issue": { "title": "Bug report", "number": 42 },
  "sender": { "login": "octocat" }
}
```

**Two-level discrimination:** The header identifies the event family (`issues`); the `action` field within the payload identifies the specific variant (`opened`, `closed`, `labeled`). This is hierarchical polymorphism -- a discriminator within a discriminator.

**Scale:** GitHub defines 40+ event types, each with multiple action variants. The type definitions are published as TypeScript types, enabling client-side type narrowing:

```typescript
type WebhookEvent =
  | PushEvent
  | IssuesEvent
  | PullRequestEvent
  | ...;
```

### Notion: Block Types

Notion's entire data model is a polymorphic tree. Every page, paragraph, heading, image, toggle, and database is a "block" with a `type` discriminator:

```json
{
  "object": "block",
  "id": "block-uuid-123",
  "type": "paragraph",
  "paragraph": {
    "rich_text": [
      { "type": "text", "text": { "content": "Hello world" } }
    ]
  },
  "has_children": false
}
```

```json
{
  "object": "block",
  "id": "block-uuid-456",
  "type": "heading_2",
  "heading_2": {
    "rich_text": [
      { "type": "text", "text": { "content": "Section Title" } }
    ],
    "is_toggleable": false
  }
}
```

**The Stripe pattern recurs:** `type` field + matching nested object. Notion supports 50+ block types, all in a single tree structure. The `children` relationship enables recursive nesting (a toggle block contains paragraph blocks which contain text).

**Rich text is also polymorphic:** Within each block's content, the `rich_text` array contains objects with their own `type` discriminator (`text`, `mention`, `equation`), each with type-specific properties.

### Figma: Node Types

Figma's document model is a polymorphic tree of nodes:

```
DocumentNode (root)
  └── PageNode
      ├── FrameNode
      │   ├── TextNode
      │   ├── RectangleNode
      │   └── GroupNode
      │       ├── EllipseNode
      │       └── VectorNode
      └── ComponentNode
          └── InstanceNode
```

Each node type shares common properties (id, name, visible, locked, position) and adds type-specific ones. The Plugin API provides narrowly typed results when filtering by type:

```typescript
const texts = figma.currentPage.findAllWithCriteria({ types: ['TEXT'] });
// texts is TextNode[] — not SceneNode[]
```

This is the TypeScript equivalent of type narrowing: the discriminator (`types: ['TEXT']`) narrows the return type from the base union to the specific variant.

### Comparison matrix

| System | Discriminator field | Nesting pattern | Number of types | Type-specific data location |
|--------|-------------------|-----------------|----------------|---------------------------|
| Stripe | `type` | Hash with matching key | ~30 payment methods | `payment_method.{type}` |
| GitHub | `X-GitHub-Event` header + `action` field | Flat with event-specific fields | 40+ events | Top-level payload |
| Notion | `type` | Hash with matching key | 50+ blocks | `block.{type}` |
| Figma | Node class / `type` field | Tree with typed children | 20+ node types | Type-specific properties |
| CloudEvents | `type` attribute | `data` field (opaque) | Unbounded | `data` (schema varies) |

---

## 9. The Schema-Driven Advantage {#9-schema-driven-advantage}

### Single declaration, three-layer propagation

In a schema-driven framework, the discriminator declared in the model definition propagates automatically through all three layers of the stack:

```
┌──────────────────────────────────────────────────────────────────────┐
│                      MODEL DEFINITION (Python)                       │
│                                                                      │
│  class Content(ProtoModel):                                          │
│      type: Literal['article', 'video', 'podcast']                    │
│      title: str                                                      │
│                                                                      │
│  class Article(Content):                                             │
│      type: Literal['article'] = 'article'                            │
│      body: str                                                       │
│      word_count: int                                                 │
│                                                                      │
│  class Video(Content):                                               │
│      type: Literal['video'] = 'video'                                │
│      url: str                                                        │
│      duration: int                                                   │
│                                                                      │
└─────────────────────────┬────────────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          │               │               │
          ▼               ▼               ▼
   ┌──────────┐   ┌──────────┐   ┌──────────────┐
   │ STORAGE  │   │   API    │   │      UI      │
   │          │   │          │   │              │
   │ content  │   │ GET /    │   │ <ntt-list>   │
   │ ┌──────┐ │   │ Content  │   │ renders base │
   │ │type  │ │   │ returns  │   │ fields;      │
   │ │title │ │   │ oneOf    │   │              │
   │ │body? │ │   │ schema   │   │ <ntt-item>   │
   │ │url?  │ │   │ with     │   │ reads type,  │
   │ │...   │ │   │ discrim. │   │ shows type-  │
   │ └──────┘ │   │          │   │ specific     │
   │ WHERE    │   │ ?type=   │   │ fields       │
   │ type=... │   │ filters  │   │              │
   └──────────┘   └──────────┘   └──────────────┘
```

**Storage layer:** The `type` column enables efficient filtering. Single-table inheritance keeps queries simple. The framework generates the column and migration automatically.

**API layer:** `ProtoModel.schema()` generates a JSON Schema with `oneOf` + `discriminator` referencing the `type` field. Each variant is a `$defs` entry. The GET endpoint returns the polymorphic schema; CRUD operations validate against the correct variant based on the discriminator value.

**UI layer:** `NTT.SCHEMA()` receives the polymorphic schema, `prototype()` creates DynamicClasses for each variant. The form generator reads the discriminator and renders the appropriate fields. Type switching in a create/edit form dynamically swaps the field set.

### What auto-generation buys you

With a schema-driven framework, adding a new polymorphic type requires one action: define the subclass. Everything else is derived.

**Manual approach (without schema-driven framework):**

| Task | Files touched | Estimated effort |
|------|--------------|-----------------|
| Define model class | 1 | 5 min |
| Write DB migration | 1 | 10 min |
| Add API route(s) | 1-2 | 15 min |
| Update OpenAPI spec | 1 | 10 min |
| Add to discriminator mapping | 1-2 | 5 min |
| Create/update form component | 1-2 | 30 min |
| Add type-specific rendering | 1-2 | 20 min |
| Update tests | 2-3 | 30 min |
| **Total** | **9-14 files** | **~2 hours** |

**Schema-driven approach:**

| Task | Files touched | Estimated effort |
|------|--------------|-----------------|
| Define model subclass | 1 | 5 min |
| **Total** | **1 file** | **5 minutes** |

The migration, routes, schema, discriminator mapping, form, rendering, and type filtering are all derived from the model definition. The 24x reduction in effort compounds: 10 types in the manual approach means 20+ hours of boilerplate; in the schema-driven approach, it is still 50 minutes.

### Pydantic discriminated unions as the generation source

Pydantic v2 natively supports discriminated unions, and the generated JSON Schema includes the OpenAPI-compatible discriminator:

```python
from typing import Literal, Union, Annotated
from pydantic import BaseModel, Field

class Article(BaseModel):
    type: Literal['article']
    title: str
    body: str

class Video(BaseModel):
    type: Literal['video']
    title: str
    url: str
    duration: int

Content = Annotated[
    Union[Article, Video],
    Field(discriminator='type')
]

class Feed(BaseModel):
    items: list[Content]
```

Pydantic generates JSON Schema with `$defs` for each variant (Article, Video), each with `type: { "const": "article" }` / `type: { "const": "video" }`. The `items` field gets a `discriminator: { propertyName: "type", mapping: { article: "#/$defs/Article", video: "#/$defs/Video" } }` with `oneOf` referencing both. The discriminator is declared once (in the `Annotated` type hint). Pydantic generates it into JSON Schema. OpenAPI reads it. The frontend reads it. Validation uses it for O(1) dispatch. The logic for "which variant is this?" is never hand-written -- it flows from the type system.

> **For the CEO:** This is the compounding advantage of schema-driven architecture. Every polymorphic type you add costs 5 minutes of developer time and zero coordination between backend and frontend teams. The schema is the contract, the discriminator is the routing logic, and the framework handles the plumbing. Over 50 types, that is the difference between 4 hours and 4 weeks of development effort.

---

## 10. Decision Framework {#10-decision-framework}

### When to use each polymorphism strategy

```
                    ┌─────────────────────────────┐
                    │  Do types share >50% fields? │
                    └──────────┬──────────────────┘
                          Yes  │  No
                    ┌──────────┴──────────────────┐
                    │                              │
            ┌───────▼───────┐              ┌──────▼──────────┐
            │ Single table  │              │ Separate tables  │
            │ + discriminator│              │ (or collections) │
            └───────┬───────┘              └──────┬──────────┘
                    │                              │
            ┌───────▼───────────┐          ┌──────▼──────────┐
            │ Need cross-type   │          │ Need cross-type  │
            │ queries?          │          │ queries?         │
            │ Yes -> STI        │          │ Yes -> Union     │
            │ No  -> CTI or STI │          │ No  -> Separate  │
            └───────────────────┘          │       endpoints  │
                                           └─────────────────┘
```

### Storage strategy comparison

| Criterion | Single Table (STI) | Class Table (CTI) | Concrete Table | Separate Collections |
|-----------|-------------------|-------------------|---------------|---------------------|
| Query all types | Fast (one table) | Moderate (JOINs) | Slow (UNIONs) | Requires multi-query |
| Query one type | Fast (WHERE type=) | Fast (one JOIN) | Fastest (no JOINs) | Fast (direct) |
| Add new type | No migration | Add one table | Add one table | Add one collection |
| Null columns | Many (type-specific fields) | None | None | None |
| Referential integrity | Easy | Complex | Very complex | Per-collection |
| Schema evolution | One table to alter | Multiple tables | Multiple tables | Independent |
| Best when | <10 types, shared fields | 5-20 types, moderate overlap | Few types, little overlap | Types are truly independent |

### API pattern comparison

| Pattern | When to use | Examples |
|---------|------------|---------|
| `oneOf` + discriminator | Fixed set of types, compile-time known | Payment methods, content types |
| `allOf` base + extension | Hierarchical inheritance, shared behavior | API versioning, progressive disclosure |
| `if`/`then`/`else` | Same type, conditionally validated | Forms with dependent fields |
| `additionalProperties` | Open extension, plugin-added fields | Metafields, custom attributes |
| `$dynamicRef` | Composable schemas at runtime | Framework extension points |

### Checklist: is your system ready for schema polymorphism?

- [ ] Models share a clear base type (common fields, common operations)
- [ ] A natural discriminator field exists (or can be added)
- [ ] Types will grow over time (otherwise static typing suffices)
- [ ] Cross-type queries are a real requirement (otherwise separate endpoints are simpler)
- [ ] Schema generation is automated (manual schema maintenance defeats the purpose)
- [ ] Frontend consumes schema at runtime (otherwise the UI cannot adapt dynamically)
- [ ] Schema registry or versioning is in place (for event-driven systems)

---

## 11. Sources {#11-sources}

1. [OpenAPI Specification v3.1.0 -- Discriminator Object](https://spec.openapis.org/oas/v3.1.0.html) -- Official specification for the discriminator mechanism in OpenAPI.

2. [JSON Schema -- Conditional Validation (if/then/else)](https://json-schema.org/understanding-json-schema/reference/conditionals) -- Reference for conditional schema application in JSON Schema Draft-07+.

3. [Stripe's Payments APIs: The First 10 Years](https://stripe.com/blog/payment-api-design) -- Stripe's own account of evolving their payment API from card-centric to polymorphic.

4. [Stripe PaymentMethod Object API Reference](https://docs.stripe.com/api/payment_methods/object) -- Live documentation of Stripe's discriminator-based polymorphic payment method design.

5. [Confluent Schema Registry -- Schema Evolution and Compatibility](https://docs.confluent.io/platform/current/schema-registry/fundamentals/schema-evolution.html) -- Comprehensive documentation of backward, forward, and full compatibility rules.

6. [AWS Glue Schema Registry](https://docs.aws.amazon.com/glue/latest/dg/schema-registry.html) -- AWS implementation of schema evolution with compatibility validation for Avro, JSON Schema, and Protobuf.

7. [CloudEvents Specification](https://github.com/cloudevents/spec/blob/main/cloudevents/spec.md) -- The `type` attribute as the standard event discriminator for distributed systems.

8. [Notion API -- Block Reference](https://developers.notion.com/reference/block) -- Notion's polymorphic block type API with `type` field + matching nested hash pattern.

9. [Figma Plugin API -- Node Types](https://developers.figma.com/docs/plugins/api/nodes/) -- Figma's polymorphic tree model with typed nodes.

10. [GitHub Webhook Events and Payloads](https://docs.github.com/en/webhooks/webhook-events-and-payloads) -- GitHub's two-level discriminator pattern (event header + action field).

11. [Pydantic v2 -- Discriminated Unions](https://docs.pydantic.dev/latest/concepts/unions/) -- Pydantic's native support for tagged unions with automatic JSON Schema generation.

12. [Swagger/OpenAPI -- Inheritance and Polymorphism](https://swagger.io/docs/specification/v3_0/data-models/inheritance-and-polymorphism/) -- Practical guide to allOf composition and discriminator usage.

13. [Strapi -- Models and Content Types](https://docs.strapi.io/cms/backend-customization/models) -- Strapi's approach to dynamic content type definition and runtime schema generation.

14. [Shopify -- About Metafields](https://shopify.dev/docs/apps/build/metafields) -- Shopify's extensible typed data system for merchant-defined schema extensions.

15. [Contentful -- Data Model](https://www.contentful.com/developers/docs/concepts/data-model/) -- Contentful's API-first dynamic content type architecture.

16. [PostgreSQL Documentation -- Table Inheritance](https://www.postgresql.org/docs/current/ddl-inherit.html) -- Native database-level polymorphism and its limitations.

17. [Elastic Blog -- Removal of Mapping Types](https://www.elastic.co/blog/removal-of-mapping-types-elasticsearch) -- Elasticsearch's lesson in why implicit multi-type indexing fails and how explicit discriminator fields replace it.

18. [Martin Fowler -- Single Table Inheritance](https://www.martinfowler.com/eaaCatalog/singleTableInheritance.html) -- Canonical pattern description for STI with discriminator columns.

19. [Apollo GraphQL -- Unions and Interfaces](https://www.apollographql.com/docs/apollo-server/schema/unions-interfaces) -- GraphQL's type-safe approach to polymorphic queries with __typename.

20. [Endjin -- Composition, Polymorphism, and Pattern Matching with JSON Schema](https://endjin.com/blog/2025/07/composition-polymorphism-pattern-matching-with-json-schema-dotnet) -- 2025 analysis of JSON Schema polymorphism patterns in practice.

21. [WordPress REST API -- Adding Support for Custom Content Types](https://developer.wordpress.org/rest-api/extending-the-rest-api/adding-rest-api-support-for-custom-content-types/) -- WordPress runtime type registration via REST API.

22. [Redocly -- How to Use the OpenAPI Discriminator](https://redocly.com/learn/openapi/discriminator) -- Practical guide to discriminator mapping in OpenAPI specifications.

23. [ByteByteGo -- The First 10-Year Evolution of Stripe's Payments API](https://blog.bytebytego.com/p/the-first-10-year-evolution-of-stripes) -- Technical analysis of Stripe's API evolution from monomorphic to polymorphic design.

---

*Document generated February 2026. Schema specifications and API designs referenced are current as of publication date.*
