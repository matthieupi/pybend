# Polymorphic Systems for PyBend: Strategic Analysis Report

## For: CEO & Engineering Team
## Date: February 2026
## Prepared by: Architecture Team

---

### How to Read This Document

This report is structured in layers. The **Executive Summary** (Section 0) gives you the full picture in two pages. **Sections 1-3** build context: what polymorphism is, who uses it, and how it works technically. **Section 4** is the core assessment: where PyBend stands today and what it would take. **Sections 5-7** are the decision layer: costs, framework, and our recommendation. **Section 8** covers risks. **Section 9** has appendices for reference.

**If you read nothing else**, read the Executive Summary and Section 7 (Recommendation).

---

## Executive Summary

**The question:** Should PyBend add first-class polymorphic data model support -- the ability for multiple specialized types (Article, Video, Podcast) to share a common base (Content) with automatic storage discrimination, schema union generation, and type-aware frontend rendering?

**The answer:** Yes, and we are closer than it appears. PyBend's existing architecture already contains **60-70% of the machinery** needed for polymorphism. The `ProtoModel` inheritance chain, `__init_subclass__()` hook, JSON Schema `$defs`, and the frontend's DynamicClass system provide a foundation that most frameworks lack entirely. The remaining work is estimated at **13-19 engineering days** across four phases.

**Why it matters:**

| Dimension | Without Polymorphism | With Polymorphism |
|-----------|---------------------|-------------------|
| Adding a new content type | Define model + separate routes + separate UI | Define model subclass. Done. |
| Mixed-type collections | Query N endpoints, merge client-side | `GET /content` returns all types |
| Type-specific rendering | Manual switch/case per type in frontend | Schema carries rendering hints per subtype |
| Per-subtype access control | Already works (separate models) | Already works + unified query filtering |
| Schema contract | One schema per model (works) | `oneOf` + discriminator (industry standard) |
| Competitive positioning | On par with Django, Rails | **Unique**: schema-propagated polymorphism |

**The strategic opportunity:** No framework in the market today offers schema-propagated polymorphism -- where defining a Python subclass automatically generates a discriminated union schema, adapts the storage layer, creates polymorphic API endpoints, and drives type-aware frontend rendering. Django requires `django-polymorphic` + manual serializer updates + frontend changes. Rails offers STI but no schema output. Strapi has dynamic zones but no type inheritance. PyBend can do what none of them do: **one model definition, full-stack polymorphism**.

**The cost:**
- **Phase 1** (STI discriminator): 2-3 engineering days
- **Phase 2** (schema union generation): 3-4 engineering days
- **Phase 3** (frontend type dispatch): 5-7 engineering days
- **Phase 4** (polymorphic routes): 3-5 engineering days
- **Total:** 13-19 engineering days, no external dependencies, no breaking changes

**The recommendation:** Implement Phases 1-2 immediately (5-7 days). This gives PyBend discriminator-based storage and `oneOf` schema output -- the two capabilities that unlock the most value with the least risk. Defer Phases 3-4 until a concrete use case demands mixed-type frontend rendering.

---

## 1. What Is Polymorphism (and Why Does It Matter)?

### 1.1 The Plain-English Version

Polymorphism means "many forms." In data systems, it means a single concept -- Payment, Content, Notification -- can take multiple specialized shapes while still being treated uniformly at some level.

```
                    Payment
                   /   |   \
                  /    |    \
           CreditCard  BankTransfer  CryptoPayment
           ----------  -----------  --------------
           card_num    account_num  wallet_address
           exp_date    routing_num  chain
           cvv_hash    swift_code   tx_hash

           Shared: id, amount, status, created_at, user_owner
```

Every application with more than one "kind of thing" faces this challenge. The question is never _whether_ to handle it, but _how_.

### 1.2 Why It Matters for PyBend Specifically

PyBend's core promise is **"define a model, get an app."** The model is the single source of truth for storage, API, schema, and UI. This promise works beautifully for flat, independent models. But the moment an application needs a `Content` base type with `Article` and `Video` subtypes sharing a unified feed, the developer hits a wall:

- They can define `Article` and `Video` as separate models (works today), but lose unified queries
- They can manually aggregate separate endpoints in the frontend (works today), but it is tedious
- They cannot define a polymorphic hierarchy where `GET /content` returns both types

**This is a gap in the "model is the app" promise.** Polymorphism is the mechanism that would close it.

### 1.3 The Three Layers of Polymorphic Design

Polymorphism touches every layer of the stack:

```
+──────────────────────────────────────────────────────────+
|                    APPLICATION LAYER                      |
|  Python class hierarchy: Content → Article, Video        |
|  Discriminator: type: Literal['article'] = 'article'    |
+──────────────────────────────────────────────────────────+
                         |
+──────────────────────────────────────────────────────────+
|                     STORAGE LAYER                         |
|  Single table with _type column (STI)                    |
|  OR base table + child tables (CTI)                      |
|  OR separate tables (today's PyBend)                     |
+──────────────────────────────────────────────────────────+
                         |
+──────────────────────────────────────────────────────────+
|                      API LAYER                            |
|  JSON Schema: oneOf + discriminator mapping              |
|  Endpoint: GET /content returns mixed types              |
|  Filtering: GET /content?_type=article                   |
+──────────────────────────────────────────────────────────+
                         |
+──────────────────────────────────────────────────────────+
|                       UI LAYER                            |
|  DynamicClass per subtype (from $defs)                   |
|  Form adapts to selected type                            |
|  List renders mixed types with per-type tags             |
+──────────────────────────────────────────────────────────+
```

The fundamental tension: **relational databases have no native concept of inheritance**. SQL predates OOP by over a decade. Every polymorphic system is a bridge between two paradigms that do not naturally align ([TypeDB Blog: Inheritance and Polymorphism in SQL](https://typedb.com/blog/inheritance-and-polymorphism-where-the-cracks-in-sql-begin-to-show)).

---

## 2. Industry Landscape

### 2.1 Who Uses Polymorphic Data Models

Polymorphism is not a niche pattern. It is the **dominant architectural choice** at every major platform company:

| Company | Polymorphic Pattern | Scale | Key Insight |
|---------|-------------------|-------|-------------|
| **Stripe** | Discriminated type hash (`PaymentMethod.type`) | $1T+ processed annually, 15+ payment types | Rebuilt entire API around polymorphism after initial monomorphic design failed ([Stripe Blog](https://stripe.com/blog/payment-api-design)) |
| **WordPress** | Single-table inheritance (`wp_posts.post_type`) | 43% of all websites, billions of rows | Largest STI deployment in production; EAV metadata table is the #1 performance bottleneck ([WP Docs](https://developer.wordpress.org/themes/basics/post-types/)) |
| **Shopify** | Composition + metafields (Product → Option → Variant) | $235.9B GMV, 4.6M+ merchants | Chose composition over inheritance; metafields handle type-specific attributes without schema changes ([Shopify Dev](https://shopify.dev/docs/apps/build/graphql/migrate/new-product-model/product-model-components)) |
| **Salesforce** | Polymorphic relationships + Record Types | 150,000+ customers | `WhoId` can reference Contact or Lead; SOQL's `TYPEOF` expression queries across polymorphic references ([Salesforce SOQL](https://developer.salesforce.com/docs/atlas.en-us.soql_sosl.meta/soql_sosl/sforce_api_calls_soql_relationships_and_polymorph_keys.htm)) |
| **Amazon** | EAV + category-specific attribute tables | 350M+ products, ~12M updates/day | Maximum flexibility at maximum infrastructure cost |
| **Notion** | Discriminated block types (`block.type`) | 50+ block types in a single tree | Uses Stripe's pattern: `type` field + matching nested hash ([Notion API](https://developers.notion.com/reference/block)) |
| **GitHub** | Two-level event discrimination (header + action) | 40+ event types, each with multiple actions | Hierarchical polymorphism for webhook dispatch ([GitHub Webhooks](https://docs.github.com/en/webhooks/webhook-events-and-payloads)) |

### 2.2 The Stripe Case Study: Three Eras of Polymorphism

Stripe's API evolution is the most thoroughly documented case of polymorphic system design in the industry. Over 10 years, they went through three distinct architectures:

```
ERA 1 (2011-2015): Charges + Tokens
+-----------+
| Charge    |  Card-only. Simple.
| card_num  |  Problem: can't represent async flows
| amount    |
+-----------+

ERA 2 (2015-2017): Sources API (polymorphic state machine)
+------------------+
| Source            |  One abstraction for all methods.
| type: card|bank  |  Problem: "confusing integration and
| state_machine    |  overloaded abstractions"
+------------------+

ERA 3 (2018-present): PaymentIntents + PaymentMethods
+------------------+     +-------------------+
| PaymentIntent    |     | PaymentMethod     |
| amount, status   |<--->| type: card|bank   |
| lifecycle        |     | {type}: {details} |
+------------------+     +-------------------+
  "What to do"             "How to pay"
```

**Key numbers from Stripe's engineering blog:**
- Charge object grew from **11 to 36 properties** between 2011 and 2018
- Redesign team: **5 people** (4 engineers + 1 PM) for **3 months**
- Full migration from Charges to PaymentIntents: **~2 years**
- Now handles **15+ distinct payment method types**

> **The lesson:** Stripe's biggest mistake was the Sources API -- forcing all payment methods into a single polymorphic state machine. Card payments finalize immediately; bank transfers take days; redirect methods need customer action. Forcing them into one abstraction created more complexity than separate integrations would have. **The fix was separating intent from method** -- a pattern that applies beyond payments. ([ByteByteGo: Stripe API Evolution](https://blog.bytebytego.com/p/the-first-10-year-evolution-of-stripes))

### 2.3 The GitLab Cautionary Tale

GitLab maintains an explicit **policy against new single-table inheritance** in their development guidelines. They are a monolithic Rails application with 30M+ registered users.

**What happened:**
1. Multiple tables used STI (e.g., `ci_builds` stored different build step types)
2. Tables grew to hundreds of millions of rows
3. Lock contention from frequent writes + heavy indexing caused production incidents
4. Filtering by `type` on every query added measurable I/O overhead

**GitLab's resolution:** No new STI. Migrate existing STI to separate tables or enum-based discrimination. ([GitLab Docs: STI](https://docs.gitlab.com/development/database/single_table_inheritance/))

> **The takeaway for PyBend:** STI works at modest scale (sub-10M rows). PyBend's SQLite-based applications will likely stay well under that threshold. GitLab's pain applies to PostgreSQL databases serving millions of concurrent users -- a different order of magnitude than PyBend's target deployment.

### 2.4 How Major ORMs Handle Polymorphism

| ORM | STI | CTI (Joined) | Concrete | Discriminator | Auto-Downcast |
|-----|:---:|:----------:|:--------:|:------------:|:------------:|
| **SQLAlchemy** (Python) | Yes | Yes | Yes | Configurable | Yes |
| **Django** (Python) | Proxy only | Yes (default) | Via abstract | Implicit (ptr) | Via `django-polymorphic` |
| **ActiveRecord** (Rails) | Built-in | No | No | `type` column | Yes (STI) |
| **Hibernate/JPA** (Java) | Yes (default) | Yes | Yes | `@DiscriminatorColumn` | Yes |
| **Prisma** (TypeScript) | No | No | No | No | No |
| **Entity Framework** (C#) | Yes (TPH) | Yes (TPT) | Yes (TPC) | Yes | Yes |

([SQLAlchemy Docs](https://docs.sqlalchemy.org/en/21/orm/inheritance.html)), ([Django Docs](https://docs.djangoproject.com/en/4.2/topics/db/models/))

**The Prisma gap is strategically significant:** The fastest-growing ORM in the TypeScript ecosystem (4.5M+ weekly npm downloads) has **no native polymorphism support**. GitHub issues requesting union types have 1,000+ reactions. The ZenStack extension layer added polymorphism in 2024. ([ZenStack Blog](https://zenstack.dev/blog/polymorphism))

### 2.5 Industry Trends

Three converging trends are shaping polymorphic system design in 2026:

**1. Language-level discriminated unions.** TypeScript (2016), Kotlin (2017), Rust (2015), Java (2021), and Python (2020) have all added first-class sum type support. The industry is moving type boundaries **earlier in the stack** -- from runtime database queries to compile-time type checks.

**2. GraphQL's native polymorphism.** GraphQL has interfaces and union types as first-class primitives. The `__typename` field is a built-in discriminator. The `@oneOf` directive (RFC stage, 2023-2024) adds discriminated union inputs, closing the input/output asymmetry. Used by Meta, GitHub, Shopify, Stripe, Airbnb, Netflix. ([Apollo Docs](https://www.apollographql.com/docs/apollo-server/schema/unions-interfaces))

**3. Composition over inheritance.** Shopify, Stripe, and the headless CMS ecosystem favor **composition with typed metadata** over classical inheritance hierarchies. This aligns with API-first, schema-driven architectures -- the exact category PyBend occupies.

---

## 3. Technical Architecture Overview

### 3.1 Storage Strategies Compared

Six primary approaches exist for implementing polymorphic data in a relational database:

```
STORAGE STRATEGY DECISION MAP
================================================================

How many subtypes share this table?

  2-5, sharing 80%+ fields ──────────> SINGLE TABLE (STI)
  │                                     One table, type column
  │                                     Zero JOINs, fast reads
  │                                     Nullable type-specific cols
  │
  5-15, significant divergence ──────> CLASS TABLE (CTI)
  │                                     Base table + child tables
  │                                     Normalized, strong integrity
  │                                     JOIN per read
  │
  Types queried independently ────────> CONCRETE TABLE
  │                                     Fully independent tables
  │                                     Fastest per-type queries
  │                                     UNION for cross-type
  │
  Schema evolves frequently ──────────> JSONB HYBRID
  │                                     Shared cols + JSON column
  │                                     No migrations for new types
  │                                     GIN-indexed for querying
  │
  Truly unbounded attributes ─────────> EAV (last resort)
                                         Every attribute is a row
                                         Maximum flexibility
                                         Worst query performance
```

### 3.2 Performance Profile by Strategy

Based on published benchmarks and PostgreSQL documentation:

| Operation | STI | CTI (Joined) | Concrete | JSONB Hybrid |
|-----------|-----|:----------:|:--------:|:-----------:|
| Single row by ID | ~0.1ms | ~0.2-0.3ms | ~0.1ms | ~0.1ms |
| 1000 rows, single type | ~2ms | ~4-6ms | ~1.5ms | ~2ms |
| 1000 rows, all types | ~2ms | ~8-15ms | ~5-8ms (UNION) | ~2ms |
| Aggregate across types | ~3ms | ~10-20ms | ~8-12ms | ~3ms |
| INSERT single row | ~0.2ms | ~0.4ms (2 tables) | ~0.2ms | ~0.2ms |
| Filter on type-specific field | ~1ms | ~2-3ms | ~0.8ms | ~3-8ms* |

*JSONB field query without expression index; with expression index approaches native column speed.

([Replacing EAV with JSONB in PostgreSQL](https://coussej.github.io/2016/01/14/Replacing-EAV-with-JSONB-in-PostgreSQL/))

> **KEY INSIGHT:** For PyBend's SQLite-based target deployments, the performance differences between strategies are negligible at typical scale (sub-100K rows). The choice should be driven by **developer ergonomics and schema evolution flexibility**, not raw query speed. STI is the right default.

### 3.3 JSON Schema Polymorphism Encoding

JSON Schema provides three composition keywords for expressing "this could be one of several types":

| Keyword | Rule | Use Case | OpenAPI Support |
|---------|------|----------|:--------------:|
| `oneOf` | Exactly 1 matches | Discriminated union (alternatives) | 3.0+ |
| `anyOf` | At least 1 matches | Overlapping alternatives | 3.0+ |
| `allOf` | All must match | Inheritance (base + extension) | 3.0+ |
| `if/then/else` | Conditional | Type-dependent validation | 3.1 only |
| `discriminator` | Tooling hint | Performance optimization for `oneOf` | 3.0+ |

The OpenAPI `discriminator` object with `mapping` is the industry-standard pattern:

```json
{
  "oneOf": [
    { "$ref": "#/$defs/Article" },
    { "$ref": "#/$defs/Video" }
  ],
  "discriminator": {
    "propertyName": "_type",
    "mapping": {
      "article": "#/$defs/Article",
      "video": "#/$defs/Video"
    }
  }
}
```

> **For PyBend:** Pydantic v2 natively generates this JSON Schema output from discriminated unions. The machinery exists; PyBend's `ProtoModel.schema()` simply does not invoke it yet. ([Pydantic Discriminated Unions](https://docs.pydantic.dev/latest/concepts/unions/))

### 3.4 Security Considerations

Polymorphic systems introduce a specific vulnerability category: **type confusion attacks**, where an attacker provides data that causes the system to instantiate the wrong type, bypassing validation or access controls.

| Threat | STI Risk | CTI Risk | Mitigation |
|--------|:-------:|:-------:|------------|
| Type confusion (wrong discriminator) | Medium | Low | Validate discriminator against explicit allowlist |
| Deserialization RCE (Java Jackson CVEs) | N/A for Python | N/A | Pydantic uses `Literal` values, not class names |
| Unauthorized subtype access | High | Medium | Resolve authorization AFTER type discrimination |
| SQL injection via type column | Low | N/A | Parameterized queries (PyBend already does this) |

**PyBend's position:** Pydantic's discriminated unions use `Literal` values as discriminators, not class names. There is no mechanism for a JSON payload to specify an arbitrary Python class. This is inherently safer than Java's `@JsonTypeInfo(use = Id.CLASS)` pattern that has generated dozens of CVEs. ([Jackson CVE Criteria](https://github.com/FasterXML/jackson/wiki/Jackson-Polymorphic-Deserialization-CVE-Criteria))

---

## 4. Our Current Architecture Assessment

### 4.1 What We Already Have (60-70% of the Machinery)

PyBend's architecture was not designed for polymorphism, but it contains a surprising number of the required building blocks:

| Capability | Status | Where It Lives |
|-----------|:------:|----------------|
| Shared base class with common fields | **Already works** | `ProtoModel` with `id`, `image` fields (`proto_model.py:62-63`) |
| Automatic mixin injection for subclasses | **Already works** | `__init_subclass__()` injects `StorableMixin` (`proto_model.py:72-93`) |
| Per-subclass `__tablename__` | **Already works** | Each model sets its own table name |
| Per-subclass `__access__` rules | **Already works** | ABAC rules per model (`rules.py`) |
| Per-subclass `__ui__` configuration | **Already works** | Independent UI hints per model (`proto_model.py:284-307`) |
| Schema generation per model | **Already works** | `ProtoModel.schema()` (`proto_model.py:199-316`) |
| `$defs` for referenced models | **Already works** | Schema includes nested model schemas (`proto_model.py:222-246`) |
| Frontend DynamicClass per type | **Already works** | `NTT.SCHEMA()` + `prototype()` (`NTT.js:390-426`) |
| `__abstract__` flag on base types | **Already works** | `BaseUser` uses `__abstract__ = True` (`base_user.py:28`) |
| Per-model component tag resolution | **Already works** | `#resolveChildTag()` in `ntt-item.js` (lines 632-638) |
| Access rule SQL pushdown | **Already works** | `Where.sql_filter()` generates parameterized SQL (`rules.py:265-275`) |

> **The BaseUser pattern is polymorphism in embryonic form.** `BaseUser` declares `__abstract__ = True` and provides shared fields plus `login()`/`register()` endpoints. The concrete `User` subclass inherits everything. This is STI without the discriminator column -- the seed of the pattern we would formalize.

### 4.2 What Is Missing (The 30-40% Gap)

Six specific gaps exist between PyBend's current capabilities and full polymorphic support:

**Gap 1: Discriminator Column in Storage**

`sqlite_storage.py` uses one table per `__tablename__`. There is no concept of a `_type` column that marks which subtype a row belongs to.

```python
# Current: no type discrimination
def create(self, model_class, data):
    table_name = model_class.__tablename__
    # INSERT INTO {table_name} ... — no _type injected
```

**Gap 2: Type-Aware Query Filtering**

`list()` queries the entire table with no subtype filter. If `Article` and `Video` shared a `content` table, `Article.list()` would return ALL rows.

```python
# Current: queries whole table
select_sql = f"SELECT * FROM {table_name}"
# Missing: WHERE _type = 'article'
```

**Gap 3: Schema Union Generation (`oneOf`/`anyOf`)**

`ProtoModel.schema()` generates a flat schema per model. It does not generate JSON Schema union types with discriminator mapping.

**Gap 4: Frontend Rendering Dispatch by Subtype**

`ntt-list` stamps a single `childTag` for every entity. There is no per-item type inspection to stamp `ntt-article` for one entity and `ntt-video` for another.

```javascript
// Current: same tag for all items
const el = document.createElement(this.childTag);
// Missing: resolve tag per entity based on _type
```

**Gap 5: Form Generation for Type-Specific Fields**

`form.js` renders ALL `schema.properties`. With STI, it would show Video-specific fields when editing an Article.

**Gap 6: Polymorphic Route Generation**

Each model gets its own endpoint set. There is no mechanism for a single `/content` endpoint that returns both Articles and Videos, or a `POST /content` that inspects a discriminator to decide which subclass to instantiate.

### 4.3 Architecture Diagram: Current vs. Proposed

```
CURRENT ARCHITECTURE (Separate Models)
=================================================================

  Article Model          Video Model           (independent)
       |                      |
       v                      v
  articles table         videos table          (separate tables)
       |                      |
       v                      v
  GET /Article           GET /Video            (separate schemas)
  GET /articles          GET /videos           (separate endpoints)
       |                      |
       v                      v
  DynamicClass:          DynamicClass:         (separate classes)
  Article                Video
       |                      |
       v                      v
  <ntt-list              <ntt-list             (separate lists)
   model="Article">       model="Video">


PROPOSED ARCHITECTURE (Polymorphic Hierarchy)
=================================================================

  Content (base)
    |-- Article(Content)       type: Literal['article']
    |-- Video(Content)         type: Literal['video']
            |
            v
    content table              (_type column discriminates)
    +----+--------+---------+-------+-----------+----------+
    | id | _type  | title   | body  | video_url | duration |
    +----+--------+---------+-------+-----------+----------+
    |  1 | article| Hello   | World | NULL      | NULL     |
    |  2 | video  | Demo    | NULL  | https://  | 120      |
    +----+--------+---------+-------+-----------+----------+
            |
            v
    GET /Content               (returns oneOf schema with discriminator)
    GET /content               (returns ALL types)
    GET /content?_type=article (returns only Articles)
            |
            v
    DynamicClass: Content      (base, with discriminator mapping)
    DynamicClass: Article      (from $defs, with type-specific props)
    DynamicClass: Video        (from $defs, with type-specific props)
            |
            v
    <ntt-list model="Content"> (renders mixed types, per-entity tags)
```

### 4.4 What Works TODAY with Zero Framework Changes

Even without any implementation, developers can simulate polymorphism using existing patterns:

```python
# Approach: Shared base, separate tables, manual aggregation
class Content(ProtoModel):
    __abstract__ = True
    __storable__ = False
    title: str
    author: str

class Article(Content):
    __tablename__ = 'articles'
    __storable__ = True
    body: str

class Video(Content):
    __tablename__ = 'videos'
    __storable__ = True
    video_url: str
    duration: int

app = create_app(models=[Article, Video], ...)
```

**What works:** Shared fields inherited from `Content`. Each subtype gets its own table, routes, schema, DynamicClass. Per-subtype access rules, UI config, methods.

**What does NOT work:** No unified `/content` endpoint. No mixed-type collections in the frontend. No `oneOf`/`anyOf` schema. Must query `/articles` and `/videos` separately.

**Verdict:** Good enough for many applications where each subtype has its own listing page.

---

## 5. Cost-Benefit Analysis

### 5.1 Implementation Cost by Phase

| Phase | Scope | Effort | Files Changed | Risk |
|-------|-------|--------|:------------:|:----:|
| **Phase 1: Discriminator Column** | Add `__discriminator__` ClassVar, inject `_type` column, filter by type on read/write | 2-3 days | `proto_model.py`, `sqlite_storage.py`, `sqlite_migration.py` | Low |
| **Phase 2: Schema Union Generation** | Generate `oneOf` + `discriminator` in `schema()`, register subtype DynamicClasses, per-entity type resolution | 3-4 days | `proto_model.py`, `NTT.js` | Medium |
| **Phase 3: Frontend Type Dispatch** | Per-entity `childTag` resolution, schema swap in forms, type selector in create forms, mixed-type collection rendering | 5-7 days | `ListElement.js`, `form.js`, `ntt-item.js` | Medium-High |
| **Phase 4: Polymorphic Routes** | `/content` returns all subtypes, per-subtype auth composition, `POST /content` dispatches by `_type` | 3-5 days | `routes_fastapi.py` | Medium |
| **Total** | | **13-19 days** | **~8 files** | |

### 5.2 Developer Productivity Impact

The compounding advantage of schema-driven polymorphism is the cost of adding new types:

**Without schema-driven polymorphism (manual approach):**

| Task | Files Touched | Time |
|------|:------------:|:----:|
| Define model class | 1 | 5 min |
| Write DB migration | 1 | 10 min |
| Add API route(s) | 1-2 | 15 min |
| Update OpenAPI spec | 1 | 10 min |
| Add to discriminator mapping | 1-2 | 5 min |
| Create/update form component | 1-2 | 30 min |
| Add type-specific rendering | 1-2 | 20 min |
| Update tests | 2-3 | 30 min |
| **Total** | **9-14 files** | **~2 hours** |

**With PyBend polymorphism (Phase 4 complete):**

| Task | Files Touched | Time |
|------|:------------:|:----:|
| Define model subclass | 1 | 5 min |
| **Total** | **1 file** | **5 minutes** |

> **The math:** 10 types in the manual approach = 20+ hours of boilerplate. In the schema-driven approach, it is 50 minutes. Over 50 types, that is the difference between **4 hours and 4 weeks**.

### 5.3 What We Get at Each Phase

```
CUMULATIVE VALUE BY PHASE
================================================================

Phase 0 (Today):
  [x] Shared base class inheritance
  [x] Per-subtype access rules
  [x] Per-subtype UI config
  [ ] Unified queries
  [ ] Mixed-type collections
  [ ] Schema union output
  [ ] Type-aware rendering

Phase 1 (+2-3 days):
  [x] STI with discriminator column
  [x] Type-filtered queries
  [x] Single table for related types
  [ ] Schema union output          <-- still missing
  [ ] Mixed-type collections
  [ ] Type-aware rendering

Phase 2 (+3-4 days):
  [x] oneOf + discriminator in schema
  [x] Subtype DynamicClasses from $defs
  [x] Per-entity type resolution
  [ ] Mixed-type lists              <-- still missing
  [ ] Type-aware forms

Phase 3 (+5-7 days):
  [x] Mixed-type list rendering
  [x] Per-entity component tags
  [x] Type-aware form generation
  [x] Type selector in create forms
  [ ] Unified API endpoint          <-- still missing

Phase 4 (+3-5 days):
  [x] GET /content returns all types
  [x] POST /content dispatches by _type
  [x] Per-subtype auth on unified endpoint
  [x] COMPLETE POLYMORPHISM
```

### 5.4 Maintenance and Evolution Cost

| Cost Factor | STI (Our Recommendation) | CTI | Concrete (Today) |
|-------------|:-----------------------:|:---:|:----------------:|
| Adding shared field | 1 migration | 1 migration | N migrations |
| Adding type-specific field | 1 migration (nullable col) | 1 migration | 1 migration |
| Adding new type | Add discriminator value | Add table + FK | Add table |
| Debugging type-specific bug | Medium (shared table) | Easy (isolated) | Easiest |
| Schema documentation | `oneOf` + `$defs` (self-documenting) | Complex | Simple per model |
| Onboarding new developer | Learning curve: discriminator concept | Easy | Easiest |

---

## 6. Decision Framework

### 6.1 When to Use Polymorphism in PyBend

Score each criterion +1 (favors polymorphism), 0 (neutral), or -1 (favors separate models):

```
+────────────────────────────────+──────────────+──────────────+
| Criterion                      | Favors       | Favors       |
|                                | Polymorphism | Separate     |
+────────────────────────────────+──────────────+──────────────+
| Types share >70% of fields     | +1           |              |
| Cross-type queries are primary | +1           |              |
| Shared CRUD lifecycle          | +1           |              |
| 2-8 types (bounded set)        | +1           |              |
| Types evolve together          | +1           |              |
| Single team owns all types     | +1           |              |
|                                |              |              |
| Types share <30% of fields     |              | -1           |
| Types queried independently    |              | -1           |
| 10+ or unbounded types         |              | -1           |
| Types evolve independently     |              | -1           |
| Different teams own types      |              | -1           |
+────────────────────────────────+──────────────+──────────────+

  Score +4 to +6: Strong case for STI polymorphism
  Score +1 to +3: Consider CTI or JSON hybrid
  Score -2 to  0: Gray zone — composition or separate models
  Score -3 to -6: Separate models, use mixins for shared code
```

### 6.2 Decision Tree for PyBend Developers

```
START: Do types share a common base with meaningful shared behavior?
  |
  +--[NO]---> Do they share only an interface?
  |             +--[YES]--> SEPARATE MODELS + SHARED MIXINS (Phase 0)
  |             +--[NO]---> INDEPENDENT MODELS (no polymorphism needed)
  |
  +--[YES]--> Do you need cross-type queries?
      |
      +--[NO]---> SEPARATE MODELS with shared base (Phase 0)
      |           Each gets own table, routes, UI. Sufficient.
      |
      +--[YES]--> How many types?
          |
          +--[2-5, >70% shared]---> STI (Phase 1-2)
          |                          Single table, discriminator column
          |                          Fastest cross-type queries
          |
          +--[5-10, 30-70% shared]-> CTI (future phase)
          |                          Base + child tables
          |                          Normalized, strong integrity
          |
          +--[10+ or rapidly evolving]-> JSONB HYBRID (future phase)
                                         Shared cols + JSON for type-specific
                                         No migration for new types
```

### 6.3 Pattern Selection: Industry Consensus

| Domain | Dominant Pattern | Why | Example |
|--------|-----------------|-----|---------|
| CMS/Content | STI + metadata | Content types share structure; metadata varies | WordPress |
| E-commerce (SMB) | Composition + metafields | Products share purchase interface | Shopify |
| E-commerce (Enterprise) | EAV | Unlimited attribute flexibility required | Magento, Amazon |
| Payments | Discriminated type hash | Payment methods have different lifecycles | Stripe |
| Notifications | STI + type column | Channels share metadata; delivery varies | Most SaaS |
| CI/CD | Separate tables | Build step types have fundamentally different schemas | GitLab |

---

## 7. Recommendation

### 7.1 What We Recommend

**Implement Phases 1 and 2 now. Defer Phases 3 and 4.**

Phases 1-2 (5-7 engineering days) deliver the **core polymorphic capability** -- discriminator-based storage and JSON Schema `oneOf` output -- without the complexity of frontend mixed-type rendering. This gives PyBend a genuine differentiator:

> **Define a Python subclass. Get a discriminator column, type-filtered queries, and a `oneOf` schema with discriminator mapping. Automatically. No other framework does this.**

Phases 3-4 add frontend polish (mixed-type lists, type-aware forms, polymorphic routes) that is valuable but only matters when a specific use case demands it. Build it when needed, not speculatively.

### 7.2 Why STI First

| Factor | STI | CTI | Our Choice |
|--------|-----|-----|:----------:|
| SQLite compatibility | Excellent (no complex JOINs) | Requires multi-table transactions | **STI** |
| Developer ergonomics | Simplest (one table) | More complex (base + child tables) | **STI** |
| Zero-to-working philosophy | Fastest to implement | More infrastructure | **STI** |
| Query performance at PyBend scale | Equivalent | Slightly worse (JOINs) | **STI** |
| Schema evolution | Easy (add nullable columns) | Harder (add tables, FKs) | **STI** |
| Future migration to CTI | Straightforward (Strangler Fig pattern) | N/A | **STI** |

STI aligns with PyBend's "zero to working, then customize" principle. It works out of the box. If a project outgrows STI (unlikely at PyBend's typical scale), migrating to CTI is a well-understood incremental process.

### 7.3 The Model Definition We Are Targeting

After Phase 2, a PyBend developer would write:

```python
class Content(ProtoModel):
    __tablename__ = 'content'
    __storable__ = True
    __discriminator__ = '_type'      # NEW: enables STI polymorphism
    title: str
    author: str

class Article(Content):
    # No __tablename__ — shares parent's table
    body: str
    word_count: int = 0

class Video(Content):
    # No __tablename__ — shares parent's table
    video_url: str
    duration: int = 0

app = create_app(models=[Content], ...)
# Article and Video auto-registered as subtypes
```

And `GET /Content` would return:

```json
{
  "$schema": "http://localhost:5000/Schema",
  "$id": "http://localhost:5000/Content",
  "__name__": "Content",
  "__tablename__": "content",
  "oneOf": [
    { "$ref": "#/$defs/Article" },
    { "$ref": "#/$defs/Video" }
  ],
  "discriminator": {
    "propertyName": "_type",
    "mapping": {
      "article": "#/$defs/Article",
      "video": "#/$defs/Video"
    }
  },
  "$defs": {
    "Article": {
      "$id": "http://localhost:5000/Article",
      "properties": {
        "title": { "type": "string" },
        "body": { "type": "string" },
        "word_count": { "type": "integer", "default": 0 },
        "_type": { "const": "article" }
      },
      "access": { "read": { "rule": "anyone" } },
      "ui": { ... }
    },
    "Video": {
      "$id": "http://localhost:5000/Video",
      "properties": {
        "title": { "type": "string" },
        "video_url": { "type": "string" },
        "duration": { "type": "integer", "default": 0 },
        "_type": { "const": "video" }
      },
      "access": { ... },
      "ui": { ... }
    }
  }
}
```

### 7.4 Competitive Positioning After Implementation

| Feature | Django | Rails | Strapi | Prisma | **PyBend (Phase 2)** |
|---------|:------:|:-----:|:------:|:------:|:--------------------:|
| STI | Via plugin | Built-in | No | No | **Yes** |
| Discriminator column | Manual | Automatic | N/A | No | **Automatic** |
| Polymorphic queries | Via manager | Built-in | N/A | No | **Yes** |
| `oneOf`/discriminator schema | No | No | No | No | **Yes (unique)** |
| Schema-driven UI for subtypes | No | No | Partial | No | **Yes (unique)** |
| Access rules per subtype | Manual | Manual | Plugin | Manual | **Already works** |
| Frontend type dispatch | N/A (server) | N/A | Partial | N/A | Phase 3 |

The two "unique" rows are the differentiator. No other framework generates a discriminated union JSON Schema from model definitions, and no other framework auto-adapts frontend rendering from that schema.

---

## 8. Risk Register

### Risk 1: STI Table Bloat at Scale

| | |
|---|---|
| **Probability** | Low for PyBend's target deployment |
| **Impact** | Medium (query degradation, NULL waste) |
| **Trigger** | >10M rows in a single STI table |
| **Mitigation** | Document maximum recommended type count (5-8). Provide migration path to CTI. Monitor table width in docs. |
| **Context** | GitLab hit this at PostgreSQL scale with 30M+ users. PyBend targets SQLite applications that rarely exceed 100K rows per table. |

### Risk 2: Breaking Existing Model Definitions

| | |
|---|---|
| **Probability** | Very Low |
| **Impact** | High (existing apps break) |
| **Trigger** | `__discriminator__` conflicts with existing field names or changes `__init_subclass__()` behavior |
| **Mitigation** | Polymorphism is opt-in via `__discriminator__` ClassVar. Models without it are completely unaffected. Add comprehensive tests before release. |

### Risk 3: Frontend Schema Parsing Complexity

| | |
|---|---|
| **Probability** | Medium |
| **Impact** | Medium (DynamicClass creation fails for edge cases) |
| **Trigger** | `oneOf` + `discriminator` interaction with existing `$defs` processing |
| **Mitigation** | Phase 2 extends existing `$defs` handling (already works). Add `oneOf` detection to `NTT.SCHEMA()` with clear fallback: if `oneOf` is not present, behavior is identical to today. |

### Risk 4: Pydantic Schema Generation Mismatch

| | |
|---|---|
| **Probability** | Medium |
| **Impact** | Medium (schema output does not match expected format) |
| **Trigger** | Pydantic's `model_json_schema()` for union types may produce different `$defs` structure than PyBend's manual `$defs` injection expects |
| **Mitigation** | Prototype the Pydantic `Annotated[Union[...], Discriminator('type')]` → `model_json_schema()` output early. Validate it matches the target schema format before building the full pipeline. |

### Risk 5: Authorization Gap with Shared Tables

| | |
|---|---|
| **Probability** | Low |
| **Impact** | High (data exposure across subtypes) |
| **Trigger** | `Article` has `__access__ = {'read': ANYONE}` but `Draft` has `__access__ = {'read': OWNER}`. A query on the shared `content` table returns Drafts to unauthenticated users. |
| **Mitigation** | Compose type filter with access filter: `WHERE (_type = 'article' AND 1=1) OR (_type = 'draft' AND user_owner = ?)`. The `Where` rule class already supports SQL pushdown for this pattern. |

### Risk 6: SQLite JSON Column Limitations

| | |
|---|---|
| **Probability** | Low (only applies if we pursue JSONB hybrid) |
| **Impact** | Medium |
| **Trigger** | SQLite's JSON support is less capable than PostgreSQL's JSONB (no GIN indexes, limited path queries) |
| **Mitigation** | Recommend STI (not JSONB hybrid) as the default for SQLite. JSONB hybrid would be a PostgreSQL-only advanced feature. |

### Risk 7: Feature Creep Into CTI/Concrete Before STI Is Proven

| | |
|---|---|
| **Probability** | Medium |
| **Impact** | High (scope explosion, delayed delivery) |
| **Trigger** | Engineers want to "do it right" and implement all three strategies simultaneously |
| **Mitigation** | Explicit scope: Phase 1-2 is STI only. CTI is a documented future extension, not a Phase 1 deliverable. Ship STI, gather feedback, then decide. |

### Risk 8: Developer Confusion About When to Use Polymorphism

| | |
|---|---|
| **Probability** | High |
| **Impact** | Low-Medium (misuse creates messy schemas, not crashes) |
| **Trigger** | Developers create polymorphic hierarchies for types that should be separate models (the "Polymorphism Envy" anti-pattern) |
| **Mitigation** | Include decision framework in documentation. Add warnings for common anti-patterns: >8 subtypes, <30% shared fields, artificial base class names (`BaseEntity`, `GenericItem`). The detection rule: if the base type name sounds artificial, you are forcing inheritance. |

---

## 9. Appendices

### Appendix A: Detailed File Impact Analysis

**Phase 1 Changes:**

| File | Change | Lines Affected |
|------|--------|:-------------:|
| `proto_model.py` | Add `__discriminator__` ClassVar detection in `__init_subclass__()`. Register subtypes in class-level `__subtypes__` dict. | ~20 new lines |
| `sqlite_migration.py` | When model has `__discriminator__`, add `_type TEXT NOT NULL DEFAULT '{classname}'` column. Collect columns from all registered subtypes. | ~30 new lines |
| `sqlite_storage.py` `create()` | Inject `_type = model_class.__name__` into data before INSERT. | ~5 new lines |
| `sqlite_storage.py` `list()` | Add `WHERE _type = ?` when called with a subtype model. | ~10 new lines |
| `sqlite_storage.py` `get()` | Add `WHERE _type = ?` when model has discriminator. | ~5 new lines |

**Phase 2 Changes:**

| File | Change | Lines Affected |
|------|--------|:-------------:|
| `proto_model.py` `schema()` | When `__discriminator__` is set: generate `oneOf` + `discriminator`, include subtype schemas in `$defs`, merge methods. | ~50 new lines |
| `NTT.js` `SCHEMA()` | Detect `oneOf` + `discriminator` in schema. Map discriminator values to subtype DynamicClasses from `$defs`. | ~30 new lines |
| `NTT.js` `DynamicClass.READ` | Route incoming entities to correct subtype DynamicClass based on discriminator field value. | ~20 new lines |

### Appendix B: Pydantic Discriminated Union Schema Output

Pydantic v2 natively generates the exact JSON Schema structure we need:

```python
from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field

class Article(BaseModel):
    type: Literal['article'] = 'article'
    title: str
    body: str

class Video(BaseModel):
    type: Literal['video'] = 'video'
    title: str
    video_url: str
    duration: int

Content = Annotated[Union[Article, Video], Field(discriminator='type')]
```

Pydantic's `model_json_schema()` for a model containing `Content` produces:

```json
{
  "$defs": {
    "Article": {
      "properties": {
        "type": { "const": "article", "title": "Type" },
        "title": { "type": "string" },
        "body": { "type": "string" }
      },
      "required": ["title", "body"]
    },
    "Video": {
      "properties": {
        "type": { "const": "video", "title": "Type" },
        "title": { "type": "string" },
        "video_url": { "type": "string" },
        "duration": { "type": "integer" }
      },
      "required": ["title", "video_url", "duration"]
    }
  },
  "discriminator": {
    "mapping": {
      "article": "#/$defs/Article",
      "video": "#/$defs/Video"
    },
    "propertyName": "type"
  },
  "oneOf": [
    { "$ref": "#/$defs/Article" },
    { "$ref": "#/$defs/Video" }
  ]
}
```

This is exactly the format our frontend needs. The `discriminator.mapping` provides the lookup table; the `$defs` entries carry the complete subtype schemas.

### Appendix C: Industry Pattern Adoption by Domain

| Domain | Dominant Pattern | Notable Users | Why This Pattern Wins |
|--------|-----------------|--------------|----------------------|
| Payments | Discriminated type hash | Stripe, Adyen, Square | Payment methods have different lifecycles |
| CMS | STI + EAV metadata | WordPress, Drupal | Content types share structure; metadata unbounded |
| Headless CMS | Document-per-type + references | Contentful, Sanity | Types independent; relationships explicit |
| E-commerce (SMB) | Composition + metafields | Shopify, BigCommerce | Products share purchase interface |
| E-commerce (Enterprise) | EAV | Magento, Amazon | Unlimited flexibility required |
| CRM | Record types (behavioral) | Salesforce, HubSpot | Objects share workflow; behavior varies |
| CI/CD | Separate tables | GitLab, GitHub Actions | Fundamentally different schemas per step type |
| Notifications | STI + type column | Most SaaS | Channels share metadata; delivery varies |
| IAM/Auth | Joined table | Auth0, Okta | Different credential schemas per provider |

### Appendix D: Key Sources

1. [Stripe Engineering Blog: Payments APIs -- The First 10 Years](https://stripe.com/blog/payment-api-design)
2. [GitLab Docs: Single Table Inheritance](https://docs.gitlab.com/development/database/single_table_inheritance/)
3. [SQLAlchemy 2.1 Docs: Inheritance Mapping](https://docs.sqlalchemy.org/en/21/orm/inheritance.html)
4. [Pydantic v2: Discriminated Unions](https://docs.pydantic.dev/latest/concepts/unions/)
5. [Replacing EAV with JSONB in PostgreSQL](https://coussej.github.io/2016/01/14/Replacing-EAV-with-JSONB-in-PostgreSQL/)
6. [TypeDB Blog: Inheritance and Polymorphism in SQL](https://typedb.com/blog/inheritance-and-polymorphism-where-the-cracks-in-sql-begin-to-show)
7. [Shopify Dev: Product Model Components](https://shopify.dev/docs/apps/build/graphql/migrate/new-product-model/product-model-components)
8. [WordPress Developer Docs: Post Types](https://developer.wordpress.org/themes/basics/post-types/)
9. [ZenStack Blog: Polymorphism in Prisma](https://zenstack.dev/blog/polymorphism)
10. [OpenAPI 3.1 Discriminator Specification](https://spec.openapis.org/oas/v3.1.0.html)
11. [Apollo GraphQL: Unions and Interfaces](https://www.apollographql.com/docs/apollo-server/schema/unions-interfaces)
12. [Notion API: Block Reference](https://developers.notion.com/reference/block)
13. [GitHub Webhook Events](https://docs.github.com/en/webhooks/webhook-events-and-payloads)
14. [Confluent Schema Registry: Schema Evolution](https://docs.confluent.io/platform/current/schema-registry/fundamentals/schema-evolution.html)
15. [CloudEvents Specification](https://github.com/cloudevents/spec/blob/main/cloudevents/spec.md)
16. [Martin Fowler: Single Table Inheritance](https://www.martinfowler.com/eaaCatalog/singleTableInheritance.html)
17. [Martin Fowler: Class Table Inheritance](https://martinfowler.com/eaaCatalog/classTableInheritance.html)
18. [Baeldung: Hibernate Inheritance Mapping](https://www.baeldung.com/hibernate-inheritance)
19. [Jackson CVE Criteria](https://github.com/FasterXML/jackson/wiki/Jackson-Polymorphic-Deserialization-CVE-Criteria)
20. [DoltHub: Choosing a Database Schema for Polymorphic Data](https://www.dolthub.com/blog/2024-06-25-polymorphic-associations/)
21. [ByteByteGo: Stripe API Evolution](https://blog.bytebytego.com/p/the-first-10-year-evolution-of-stripes)
22. [Salesforce SOQL: Polymorphic Relationships](https://developer.salesforce.com/docs/atlas.en-us.soql_sosl.meta/soql_sosl/sforce_api_calls_soql_relationships_and_polymorph_keys.htm)
23. [Contentful: Data Model](https://www.contentful.com/developers/docs/concepts/data-model/)
24. [PostgreSQL Docs: Table Inheritance](https://www.postgresql.org/docs/current/ddl-inherit.html)
25. [Rails Guides: Active Record Associations](https://guides.rubyonrails.org/association_basics.html)

### Appendix E: Glossary

| Term | Definition |
|------|-----------|
| **STI** | Single Table Inheritance. All subtypes in one table with a discriminator column. |
| **CTI** | Class Table Inheritance. Base table + child tables joined by FK. |
| **Discriminator** | A field whose value determines which subtype a record belongs to. |
| **oneOf** | JSON Schema keyword: exactly one subschema must match. Used for discriminated unions. |
| **DynamicClass** | PyBend frontend's runtime-generated JavaScript class created from a JSON Schema. |
| **EAV** | Entity-Attribute-Value. Every attribute is stored as a separate row. Maximum flexibility, worst performance. |
| **JSONB** | PostgreSQL's binary JSON column type with indexing support. |
| **Discriminated Union** | A type that is exactly one of several variants, identified by a tag/discriminator field. Also called "tagged union" or "sum type." |
| **ProtoModel** | PyBend's base model class providing schema generation, serialization, and storage injection. |
| **$defs** | JSON Schema keyword containing reusable schema definitions. PyBend uses it for referenced/nested model schemas. |

---

*Report compiled from 5 research documents totaling 227,000+ characters, 25+ primary sources, and direct codebase analysis of 8 key framework files. Performance numbers are sourced from published benchmarks and should be validated against your specific workload. All codebase references are accurate as of the `profiling` branch, commit 7550aeb.*
