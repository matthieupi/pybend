# Polymorphic Data Systems: Decision Framework

**When to use polymorphism, when to avoid it, and what to use instead.**

Research document for engineering leadership. February 2026.

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [What Polymorphic Data Systems Actually Are](#what-polymorphic-data-systems-actually-are)
3. [When Polymorphism Is the Right Choice](#when-polymorphism-is-the-right-choice)
4. [When Polymorphism Is the Wrong Choice](#when-polymorphism-is-the-wrong-choice)
5. [Implementation Strategies Compared](#implementation-strategies-compared)
6. [Alternatives to Polymorphism](#alternatives-to-polymorphism)
7. [Decision Criteria Matrix](#decision-criteria-matrix)
8. [The Decision Tree](#the-decision-tree)
9. [Cost-Benefit Analysis](#cost-benefit-analysis)
10. [Anti-Patterns and Failure Modes](#anti-patterns-and-failure-modes)
11. [Migration Strategies](#migration-strategies)
12. [Industry Recommendations](#industry-recommendations)
13. [Real-World Case Studies](#real-world-case-studies)
14. [Summary Checklist](#summary-checklist)
15. [Sources](#sources)

---

## Executive Summary

Polymorphic data systems allow multiple specialized types to share a common base
structure --- a `PaymentMethod` that can be a credit card, bank transfer, or
digital wallet; a `Content` entity that can be an article, video, or podcast.
The promise is elegant: write shared logic once, specialize where needed, query
across all types uniformly.

The reality is more nuanced. Polymorphism is a force multiplier when the domain
genuinely has shared behavior and cross-type queries. It becomes a liability
when types share only a name, diverge over time, or accumulate into a bloated
"god table" of nullable columns. GitLab officially banned new uses of Single
Table Inheritance in their codebase after experiencing these costs at scale.

**The core decision:** if your types share more than 70% of their fields and
you routinely query across types, polymorphism pays for itself. If types share
less than 30% or you almost never query across types, use separate models.
Everything in between requires the decision framework in this document.

---

## What Polymorphic Data Systems Actually Are

"Polymorphic data" is data that can take multiple different structural forms
while still being treated uniformly at some level. The term comes from Greek
roots: *poly* (many) + *morphe* (form).

In practice, this manifests in three layers:

| Layer | What Varies | Example |
|-------|-------------|---------|
| **Application code** | Class hierarchy with shared base | `PaymentMethod` -> `CreditCard`, `BankTransfer` |
| **Database schema** | Table structure representing the hierarchy | Single table with discriminator, or joined tables |
| **API/UI** | Uniform interface consuming varied shapes | `GET /payments` returns mixed types |

The fundamental tension: relational databases have no native concept of
inheritance. SQL predates object-oriented programming by over a decade. Every
polymorphic system is a bridge between two paradigms that do not naturally
align.

---

## When Polymorphism Is the Right Choice

### 1. Shared Behavior Across Types

Polymorphism earns its keep when types share *behavior*, not just fields.

**Strong signals:** All types go through the same CRUD lifecycle. Shared validation rules apply to 70%+ of fields. A single rendering pipeline handles all types with minor variations. Authorization rules are uniform.

**Example:** `PhysicalProduct`, `DigitalProduct`, `Subscription` --- sharing `name`, `price`, `sku`, cart behavior, checkout flow. Specializations (`weight` for physical, `download_url` for digital, `billing_cycle` for subscription) are minor additions.

### 2. Cross-Type Collection Queries

The strongest justification: the "show me everything" query.

**Strong signals:** Mixed-type feeds, timelines, and activity streams. Search spanning types. Reporting that aggregates across the hierarchy. Uniform sorting/filtering.

**Example:** A CMS homepage mixing articles, videos, and podcasts --- sorted by `published_at`, filtered by `category` and `author`.

### 3. Plugin/Extension Architectures

When third parties add new types that must integrate with existing infrastructure.

**Strong signals:** Third-party developers create new subtypes. New types must work with existing admin UIs, APIs, and workflows. The set of types is unbounded. Schema-driven systems auto-generate UIs from model definitions.

### 4. Event Systems with Typed Events

Event-driven architectures naturally produce polymorphic data: shared envelope (`id`, `timestamp`, `source`, `type`) with type-specific payloads.

**Strong signals:** Events flow through shared pipelines. Consumers subscribe to all events and filter by type. Audit logs record all events uniformly. Event replay treats all events as a single ordered stream.

---

## When Polymorphism Is the Wrong Choice

### 1. Types Share Only a Name, Not Behavior (False Abstraction)

> "A `User` and a `SystemProcess` both have an `id` and a `name`. They are not the same kind of thing."

**Warning signs:** Base class has only `id`, `created_at`, and maybe `name`. Subtypes have completely different field sets. Operations on one type make no sense for another. You never actually query across types.

**Real-world failure:** A SaaS platform modeled `EmailNotification`, `SMSNotification`, `PushNotification`, and `WebhookNotification` as a single hierarchy. They shared only `id`, `created_at`, `recipient_id`, and `status`. Each type had entirely different delivery logic, retry strategies, payload formats, and vendor integrations. They never displayed mixed notification lists --- the polymorphism added cost with zero benefit.

### 2. Types Diverge More Than They Converge Over Time

The most insidious failure mode --- the decision was correct at inception but types grow apart.

**Warning signs:** Each release adds columns used by only one type. Conditional logic (`if type == 'X'`) proliferates. Types develop independent lifecycle rules. Teams working on different types step on each other.

**The divergence test:** Track the shared-to-specific field ratio over time. Below 50%? Consider splitting.

### 3. Performance-Critical Paths Where JOIN Cost Matters

CTI requires a JOIN per hierarchy level. At read-heavy scale, this compounds.

**Warning signs:** Polymorphic query is in a hot path. p99 latency exceeds SLO. Hierarchy is 3+ levels deep. Index-only scans are impossible because data spans tables.

**Benchmark note:** For simple single-type queries, STI outperforms CTI (no JOINs). For complex queries with GROUP BY, CTI can outperform STI by ~2x (smaller tables, tighter indexes). The crossover depends on your query patterns.

### 4. Simple Composition Would Suffice

**Warning signs:** The "base type" is a shared component (address, metadata, audit trail), not an identity. Types form a "has-a" relationship, not "is-a." The shared part could be a separate table referenced by FK.

### 5. The "God Model" Anti-Pattern

When STI accumulates too many types, the table becomes a "God Table."

**Quantitative thresholds:**

| Metric | Healthy | Warning | Critical |
|--------|---------|---------|----------|
| Nullable columns | < 5 | 5-15 | 15+ |
| Subtypes in one table | 2-4 | 5-8 | 9+ |
| Total columns | < 30 | 30-60 | 60+ |
| % of NULLs per row (avg) | < 20% | 20-50% | 50%+ |
| Type-specific conditionals in code | < 10 | 10-30 | 30+ |

**GitLab's experience:** GitLab now bans new STI tables. They found STI led to enormous row counts, increased lightweight lock contention from additional indexes, and added filtering overhead to every query.

---

## Implementation Strategies Compared

Six primary approaches exist for implementing polymorphic data in a relational
database. Each makes different tradeoffs.

### Strategy Comparison Table

```
+------------------------+----------+----------+-----------+---------+---------+
| Strategy               | Shared   | Type-    | Cross-    | Schema  | FK      |
|                        | Query    | Specific | Type      | Evolve  | Integ-  |
|                        | Perf     | Query    | Query     | Cost    | rity    |
|                        |          | Perf     | Ability   |         |         |
+------------------------+----------+----------+-----------+---------+---------+
| Single Table (STI)     | Best     | Good*    | Excellent | High    | Weak    |
| Class Table (CTI)      | Moderate | Best     | Good      | Low     | Strong  |
| Concrete Table         | N/A      | Best     | Poor      | Low     | Strong  |
| Exclusive Belongs-To   | Moderate | Good     | Good      | High    | Strong  |
| Tagged Union (Discrim) | Good     | Good     | Good      | Mod     | Weak    |
| JSON/Semi-Structured   | Good     | Moderate | Good      | None    | None    |
+------------------------+----------+----------+-----------+---------+---------+

 * STI type-specific queries degrade as table grows due to full-table scans
   filtered by discriminator
```

### Strategy Details

#### Single Table Inheritance (STI)

All types in one table. A `type` discriminator column identifies the subclass.

```sql
CREATE TABLE content (
    id          SERIAL PRIMARY KEY,
    type        VARCHAR(50) NOT NULL,  -- 'article', 'video', 'podcast'
    title       VARCHAR(200) NOT NULL,
    body        TEXT,                  -- articles only
    video_url   VARCHAR(500),          -- videos only
    audio_url   VARCHAR(500),          -- podcasts only
    duration_s  INTEGER,               -- videos and podcasts
    word_count  INTEGER,               -- articles only
    created_at  TIMESTAMP NOT NULL
);
```

| Pros | Cons |
|------|------|
| No JOINs --- fastest cross-type queries | Nullable columns accumulate |
| Simple schema, simple migrations | Cannot use NOT NULL on type-specific fields |
| Easy to add new types (add columns) | Table grows wide and sparse |
| ORM support is excellent | Index bloat (indexes span all types) |
| Single-table rollback is trivial | "God Table" risk at scale |

**Best for:** 2-4 types sharing 70%+ of fields, read-heavy workloads, small-to-medium data volumes.

#### Class Table Inheritance (CTI)

One table per class in the hierarchy. Child tables reference the parent via FK.

```sql
CREATE TABLE content (
    id          SERIAL PRIMARY KEY,
    type        VARCHAR(50) NOT NULL,
    title       VARCHAR(200) NOT NULL,
    created_at  TIMESTAMP NOT NULL
);

CREATE TABLE article (
    id          INTEGER PRIMARY KEY REFERENCES content(id),
    body        TEXT NOT NULL,
    word_count  INTEGER NOT NULL
);

CREATE TABLE video (
    id          INTEGER PRIMARY KEY REFERENCES content(id),
    video_url   VARCHAR(500) NOT NULL,
    duration_s  INTEGER NOT NULL
);
```

| Pros | Cons |
|------|------|
| No nullable columns | JOIN per level of hierarchy |
| NOT NULL constraints on type-specific fields | Cross-type queries require UNION or LEFT JOIN |
| Each table is compact and well-indexed | INSERT/UPDATE touches multiple tables |
| Strong referential integrity | ORM mapping is more complex |
| Type-specific queries are fast | Schema changes may need coordinated migration |

**Best for:** Types with significant type-specific fields, strong data integrity requirements, write-moderate workloads.

#### Concrete Table Inheritance

One table per concrete (leaf) class. No shared parent table.

```sql
CREATE TABLE article (
    id          SERIAL PRIMARY KEY,
    title       VARCHAR(200) NOT NULL,
    body        TEXT NOT NULL,
    word_count  INTEGER NOT NULL,
    created_at  TIMESTAMP NOT NULL
);

CREATE TABLE video (
    id          SERIAL PRIMARY KEY,
    title       VARCHAR(200) NOT NULL,
    video_url   VARCHAR(500) NOT NULL,
    duration_s  INTEGER NOT NULL,
    created_at  TIMESTAMP NOT NULL
);
```

| Pros | Cons |
|------|------|
| Simplest per-type queries | Cross-type queries require UNION ALL |
| Full NOT NULL support | Shared field changes must be applied N times |
| No JOINs for any single-type operation | No shared FK target (cannot reference "any content") |
| Independent scaling per type | ID uniqueness across types requires coordination |
| Clean separation of concerns | Schema duplication |

**Best for:** Types that are queried independently, rarely or never mixed, with different scaling characteristics.

#### Exclusive Belongs-To

A polymorphic reference table with multiple nullable FKs and a CHECK constraint.

```sql
CREATE TABLE tag_assignment (
    id           SERIAL PRIMARY KEY,
    tag_id       INTEGER NOT NULL REFERENCES tag(id),
    article_id   INTEGER REFERENCES article(id),
    video_id     INTEGER REFERENCES video(id),
    podcast_id   INTEGER REFERENCES podcast(id),
    CHECK (
        (article_id IS NOT NULL)::int +
        (video_id IS NOT NULL)::int +
        (podcast_id IS NOT NULL)::int = 1
    )
);
```

| Pros | Cons |
|------|------|
| Full FK integrity | Adding types requires ALTER TABLE |
| Database enforces exclusivity | Wide reference table with many NULLs |
| Standard SQL, no ORM magic needed | CHECK constraint becomes unwieldy at 10+ types |
| Clear, auditable relationships | Every JOIN must handle N nullable columns |

**Best for:** Polymorphic *associations* (tagging, commenting, ACLs) rather than polymorphic *entities*.

#### JSON / Semi-Structured

Shared columns for common fields; a JSON column for type-specific data.

```sql
CREATE TABLE content (
    id          SERIAL PRIMARY KEY,
    type        VARCHAR(50) NOT NULL,
    title       VARCHAR(200) NOT NULL,
    created_at  TIMESTAMP NOT NULL,
    attributes  JSONB NOT NULL DEFAULT '{}'
);

-- Article: attributes = {"body": "...", "word_count": 1500}
-- Video:   attributes = {"video_url": "...", "duration_s": 360}
```

| Pros | Cons |
|------|------|
| No schema changes for new types | No database-level NOT NULL on type-specific fields |
| Single table, no JOINs | JSON querying is slower than column access |
| Excellent for high-cardinality types | Index support varies by database |
| Schema flexibility | Validation must be application-side |
| PostgreSQL JSONB has GIN indexes | Harder to reason about data shape |

**Best for:** High type cardinality, rapidly evolving schemas, event/log data, systems where flexibility outweighs strictness.

---

## Alternatives to Polymorphism

When polymorphism is not the right tool, these alternatives address the same
underlying needs.

### 1. Composition Over Inheritance (Has-A vs Is-A)

Instead of a hierarchy, extract shared concerns into separate models and
compose them.

```
INSTEAD OF:                          USE:

  Content (base)                     BlogPost
    |-- Article                        has ContentMeta
    |-- Video                          has SEOData
    |-- Podcast
                                     Video
                                       has ContentMeta
                                       has SEOData
                                       has MediaInfo
```

**When to prefer:** The shared part is a *component*, not an *identity*.
A blog post is not a "kind of content" --- it is a blog post that *has*
content metadata.

**Implementation:** Separate tables joined by FK, or embedded structs in the
application layer. In ORMs, use mixins or traits rather than class inheritance.

### 2. Separate Models with Shared Mixins/Traits

Application-level code sharing without database-level coupling.

```python
# Python example with mixins
class TimestampMixin:
    created_at: datetime
    updated_at: datetime

class AuditMixin:
    created_by: int
    modified_by: int

class Article(TimestampMixin, AuditMixin, BaseModel):
    title: str
    body: str

class Video(TimestampMixin, AuditMixin, BaseModel):
    title: str
    video_url: str
```

Each model gets its own table. Shared behavior lives in mixins. No database
inheritance, no JOINs, no nullable columns. Cross-type queries require
application-level aggregation or a search index.

**When to prefer:** Types share behavior but not storage. You want independent
schema evolution. Teams own different types independently.

### 3. Generic Relations (Django ContentType Pattern)

A framework-provided mechanism for "this row can reference any model."

```
+-----------------+     +------------------+
| Comment         |     | content_type     |
|  content_type --|---->| (app + model)    |
|  object_id      |     +------------------+
|  body           |
+-----------------+
```

**When to prefer:** You need a single model (comments, tags, activity log)
that can attach to *any* other model without knowing about it at design time.

**Tradeoffs:** No FK integrity at the database level. Queries are more
complex. Performance degrades with scale. GitLab's documentation recommends
against polymorphic associations for new features, preferring explicit
join tables per association.

### 4. Tagged Data with Schema Validation

Store data as flexible documents (JSON, JSONB) with validation rules applied
at the application layer or via database JSON Schema support.

**When to prefer:** Type cardinality is very high (50+ types), types change
frequently, and strict relational integrity is not required. Common in
event logging, analytics ingestion, and configuration storage.

### 5. Event Sourcing with Typed Events

Instead of modeling current state polymorphically, model the *events* that
produce state. Each event type is its own schema; the event store is a
uniform append-only log.

```
Event Store:
  { event_id, stream_id, type: "OrderCreated",  data: {...}, timestamp }
  { event_id, stream_id, type: "ItemAdded",     data: {...}, timestamp }
  { event_id, stream_id, type: "PaymentFailed", data: {...}, timestamp }
```

**When to prefer:** Audit trails are required. You need temporal queries
("what was the state at time T?"). The system is event-driven and the
events themselves are the primary data. Read models are built via
projections (CQRS).

**Tradeoffs:** Significant architectural complexity. Not a drop-in
replacement for polymorphic models --- it is a fundamentally different
paradigm.

### 6. Search Index as Cross-Type Query Layer

Keep types in separate tables. Use a search engine (Elasticsearch, Meilisearch,
Typesense) for cross-type queries.

```
PostgreSQL:                    Elasticsearch:
  articles table               content_index
  videos table        --->       { type, title, author, date, ... }
  podcasts table                 (denormalized, all types)
```

**When to prefer:** Cross-type queries are search-oriented (full-text,
faceted, ranked). Read patterns are very different from write patterns.
You need scoring, relevance, and fuzzy matching.

---

## Decision Criteria Matrix

Use this matrix to score your situation. Each criterion pushes toward or
against polymorphism.

```
+-----------------------------+---------------------+---------------------+
| Criterion                   | Favors              | Favors              |
|                             | Polymorphism        | Separate Models     |
+-----------------------------+---------------------+---------------------+
| Number of types             | 2-5 types           | 10+ or unbounded    |
| Shared field %              | > 70%               | < 30%               |
| Cross-type queries          | Primary use case     | Rare or never       |
| Schema evolution            | Types evolve together | Types evolve        |
|                             |                     | independently       |
| Data integrity needs        | Moderate             | Strict NOT NULL     |
|                             |                     | per type            |
| Query performance priority  | Read-heavy, mixed    | Write-heavy or      |
|                             | type reads           | per-type reads      |
| Team structure              | Single team owns     | Different teams own |
|                             | all types            | different types     |
| Type lifecycle              | Types share CRUD     | Types have distinct |
|                             | and workflow         | workflows           |
| Extensibility needs         | Closed set of types  | Open for extension  |
|                             |                     | by third parties    |
+-----------------------------+---------------------+---------------------+
```

### Scoring Guide

For each criterion, score +1 (favors polymorphism), 0 (neutral), or -1
(favors separate models).

| Score Range | Recommendation |
|-------------|----------------|
| +6 to +9 | Strong case for polymorphism (STI or CTI) |
| +3 to +5 | Polymorphism likely appropriate; validate with performance tests |
| -2 to +2 | Gray zone --- consider composition or JSON hybrid |
| -5 to -3 | Separate models preferred; use mixins for shared behavior |
| -9 to -6 | Strong case against polymorphism; use concrete tables |

---

## The Decision Tree

Follow this tree from top to bottom.

```
START: Do your types share a common base with meaningful shared behavior?
  |
  +--[NO]---> Do they share only an interface (same operations, different data)?
  |             |
  |             +--[YES]---> Use SEPARATE MODELS + SHARED MIXINS/TRAITS
  |             |            (application-level polymorphism, no DB coupling)
  |             |
  |             +--[NO]----> Use COMPLETELY INDEPENDENT MODELS
  |                          (they are different things; stop trying to unify them)
  |
  +--[YES]--> Do you need cross-type queries ("show all X regardless of type")?
      |
      +--[NO]---> Are there more than 5 types?
      |             |
      |             +--[YES]---> Use CONCRETE TABLE INHERITANCE
      |             |            (separate tables, shared code via mixins)
      |             |
      |             +--[NO]----> Use CONCRETE TABLE INHERITANCE or
      |                          CLASS TABLE INHERITANCE
      |                          (CTI if you want a shared FK target)
      |
      +--[YES]--> What % of fields are shared across all types?
          |
          +--[> 70% shared]--> How many types?
          |   |
          |   +--[2-5 types]-----> Use SINGLE TABLE INHERITANCE
          |   |                    (simple, fast, manageable NULLs)
          |   |
          |   +--[6-10 types]----> Use CLASS TABLE INHERITANCE
          |   |                    (avoids god table, keeps cross-type queries)
          |   |
          |   +--[10+ types]-----> Use JSON/SEMI-STRUCTURED HYBRID
          |                        (shared columns + JSONB for type-specific)
          |
          +--[30-70% shared]--> Use CLASS TABLE INHERITANCE
          |                     (shared table for common fields,
          |                      child tables for specializations)
          |
          +--[< 30% shared]---> Use SEPARATE TABLES + SEARCH INDEX
                                (cross-type queries via Elasticsearch/similar,
                                 not via SQL)
```

### Quick Reference: Strategy Selection by Type Count

| Types | Shared Fields | Query Pattern | Recommended Strategy |
|-------|--------------|---------------|---------------------|
| 2-3 | > 70% | Mixed | Single Table Inheritance |
| 2-3 | 30-70% | Mixed | Class Table Inheritance |
| 2-3 | < 30% | Per-type | Concrete Tables |
| 4-8 | > 70% | Mixed | STI (monitor for god table) or CTI |
| 4-8 | 30-70% | Mixed | Class Table Inheritance |
| 4-8 | < 30% | Per-type | Concrete Tables + Mixins |
| 9+ | > 70% | Mixed | JSON Hybrid |
| 9+ | Any | Per-type | Concrete Tables + Search Index |
| Unbounded | Any | Mixed | JSON Hybrid or Event Sourcing |

---

## Cost-Benefit Analysis

### Development Cost

| Cost Factor | STI | CTI | Concrete | JSON Hybrid |
|-------------|-----|-----|----------|-------------|
| Initial schema design | Low | Medium | Low | Low |
| Migration complexity | Low | High | Low | None |
| ORM mapping effort | Low | Medium | Low | Medium |
| Validation complexity | High* | Low | Low | High* |
| Testing burden | Medium | Medium | Low | High |
| New type cost | Add columns | Add table + FK | Add table | Add validation |

\* STI and JSON require application-level validation for type-specific
constraints because the database cannot enforce NOT NULL per type.

**Quantified example:** Adding a new type to each strategy:

- **STI:** 1 migration (add columns), 0-1 hours. But existing queries and
  validations must be audited for the new type.
- **CTI:** 1 migration (create child table + FK), 1-2 hours. Clean separation
  means existing types are unaffected.
- **Concrete:** 1 migration (create table), 0.5-1 hour. Must duplicate shared
  columns and update any aggregation logic.
- **JSON:** 0 migrations, 0.5 hours. Must add application-side validation.
  No database-level safety net.

### Runtime Cost

| Cost Factor | STI | CTI | Concrete | JSON Hybrid |
|-------------|-----|-----|----------|-------------|
| Single-type read | Fast | Moderate (JOIN) | Fastest | Fast |
| Cross-type read | Fastest | Moderate (JOIN/UNION) | Slow (UNION) | Fast |
| Write (create) | Fast | Moderate (multi-table) | Fast | Fast |
| Storage efficiency | Poor (NULLs) | Best | Good (duplication) | Good |
| Index effectiveness | Degraded* | Good | Best | Moderate** |
| Cache hit rate | Lower (wide rows) | Higher (compact) | Highest | Moderate |

\* STI indexes span all types; queries for one type scan irrelevant entries.
\** JSONB GIN indexes are effective but slower than B-tree on typed columns.

**Performance benchmarks (approximate, PostgreSQL 15, 1M rows):**

```
Operation                    STI      CTI       Concrete   JSON
---------------------------------------------------------------
SELECT by type + id          0.1ms    0.3ms     0.1ms      0.2ms
SELECT all types, LIMIT 50   0.2ms    1.5ms     3.0ms*     0.3ms
COUNT by type                0.5ms    0.2ms     0.1ms      0.5ms
INSERT one record            0.1ms    0.3ms     0.1ms      0.1ms
Full-text search, one type   1.0ms    0.8ms     0.5ms      1.2ms

* Concrete requires UNION ALL across N tables
```

> **Note:** These are order-of-magnitude estimates synthesized from published
> benchmarks and PostgreSQL performance documentation. Actual numbers depend
> heavily on schema shape, index strategy, hardware, and data distribution.
> Always benchmark your specific workload.

### Maintenance Cost

| Cost Factor | STI | CTI | Concrete | JSON Hybrid |
|-------------|-----|-----|----------|-------------|
| Adding shared field | 1 migration | 1 migration | N migrations | 1 migration |
| Adding type-specific field | 1 migration | 1 migration | 1 migration | 0 migrations |
| Changing shared behavior | 1 code change | 1 code change | N code changes | 1 code change |
| Debugging type-specific bug | Hard (shared table) | Easy (isolated table) | Easiest | Hard (JSON) |
| Schema documentation | Complex (which cols for which type?) | Clear (table = type) | Clear | Opaque |
| Onboarding new developer | Moderate | Easy | Easiest | Hard |

---

## Anti-Patterns and Failure Modes

### 1. "Polymorphism Envy" --- Forcing Inheritance Where Composition Fits

**Symptom:** A developer notices two models share 3-4 fields and immediately
reaches for STI.

**Problem:** Sharing a few fields does not make things the same *kind* of
entity. A `User` and a `Company` both have `name`, `email`, and `address`.
They are not subtypes of `ContactableEntity`.

**Fix:** Use composition. Extract the shared fields into a mixin or a
separate `ContactInfo` model.

**Detection rule:** If the "base type" name sounds artificial or abstract
(`BaseEntity`, `GenericItem`, `ThingWithMetadata`), you are probably
forcing inheritance.

### 2. The "Kitchen Sink" Base Class

**Symptom:** The base class/table accumulates fields that apply to only
some subtypes, eventually containing 40-60+ columns.

**Problem:** Every query pays the cost of the full row width. Validation
becomes a maze of conditional rules. New developers cannot tell which
fields belong to which type without reading the codebase.

**Quantitative trigger:** If more than 50% of columns are NULL in the
average row, the table has become a kitchen sink.

**Fix:** Migrate to CTI or Concrete Table Inheritance. Extract
type-specific columns into child tables.

### 3. Leaky Abstractions in the UI Layer

**Symptom:** The frontend receives a polymorphic response and must
implement type-specific rendering logic that grows unboundedly.

```javascript
// This code smell grows with every new type
if (item.type === 'article') { renderArticle(item); }
else if (item.type === 'video') { renderVideo(item); }
else if (item.type === 'podcast') { renderPodcast(item); }
// ... 15 more types
```

**Problem:** The polymorphism that simplified the backend has leaked
into the frontend as a giant switch statement.

**Fix:** Push rendering hints into the schema. Schema-driven frameworks
solve this by having each type carry its own rendering instructions ---
the frontend follows instructions rather than interpreting types.

### 4. Type Explosion

**Symptom:** The hierarchy grows from 3 types to 20+ because every
variation gets its own subtype.

**Problem:** `Pizza` -> `MargheritaPizza`, `PepperoniPizza`,
`VeggiePizza`, `HawaiianPizza`, `BBQChickenPizza` ...

This is not polymorphism --- it is data masquerading as types. The
variations should be *field values*, not subtypes.

**Detection rule:** If new "types" can be fully described by adding a
row (not a column or table), they are data, not types.

**Fix:** Use a single model with a `variant` or `category` field.
Reserve subtypes for structural differences (different fields, different
behavior), not value differences.

### 5. The Phantom Base Query

**Symptom:** The system was built with cross-type queries as the
justification for polymorphism, but analytics show the cross-type query
is used < 5% of the time.

**Problem:** You are paying the architectural cost of polymorphism for a
feature almost nobody uses.

**Fix:** Audit actual query patterns. If 95%+ of queries target a
single type, the cross-type query can be served by an application-level
merge or a materialized view, and the models should be separate.

### 6. The Unchangeable Discriminator

**Symptom:** An entity needs to change type (a `DraftPost` becomes a
`PublishedPost`), but the discriminator column is deeply embedded in
application logic.

**Problem:** STI makes type changes a row update. CTI makes type changes
a row deletion + insertion across tables. Neither is clean.

**Fix:** If entities regularly change type, polymorphism based on
lifecycle state is the wrong abstraction. Use a `status` field instead.
Reserve type hierarchies for intrinsic, permanent categories.

---

## Migration Strategies

### From Flat Models to Polymorphic Hierarchy

**When:** You have N independent models that you realize should be
queryable as a group.

**Approach:**
1. Create the parent table with shared columns
2. Add FK from each existing table to the parent
3. Backfill: INSERT into parent for each existing row, UPDATE child FK
4. Migrate application code to query parent table for cross-type needs
5. (Optional) Drop duplicated columns from child tables

**Risk:** Step 4 changes query semantics. Test thoroughly.

**Duration estimate:** 2-4 weeks for a medium-complexity system, including
migration scripting, application code changes, and testing.

### From STI to CTI

**When:** Your single table has grown too wide, NULLs dominate, and you
need stronger data integrity.

**Two-stage approach (FutureLearn pattern):**

1. **Stage 1 (code only):** Create new model classes with CTI structure. Add indirection mapping new API to existing STI table. Deploy. Verify behavior is identical.
2. **Stage 2 (schema):** Create child tables. Backfill from STI table using discriminator. Add FKs. Remove indirection layer. Drop unused columns.

**Key insight:** Separating code migration from schema migration lets you roll back each independently.

### From CTI to STI

**When:** JOINs are hurting performance and you need faster cross-type queries.

**Approach:**
1. Add all child-table columns (nullable) to the parent table
2. Backfill parent table from child tables
3. Add discriminator column if not present
4. Migrate application code to use single table
5. Drop child tables

**Warning:** This trades data integrity for query speed. Be sure the
tradeoff is worth it.

### From Polymorphic to Composition

**When:** Types have diverged beyond the point where the hierarchy helps.

**Approach:** Identify truly shared fields. Extract into a `Metadata` table/mixin. Create independent tables per former subtype. Migrate data (each old row becomes a type-specific row + shared row). Update FKs and application code.

**Duration estimate:** 4-8 weeks. The hardest migration --- it changes the conceptual model, not just storage layout.

### Incremental Migration Patterns (Zero-Downtime)

- **Dual-write:** Write to both old and new schemas. Read from old. Verify consistency. Switch reads. Stop old writes.
- **Shadow table:** New schema alongside old. Background sync. Compare results. Switch when consistent.
- **Strangler fig:** New features write to new schema. Gradually migrate old features. Old schema shrinks until droppable.

---

## Industry Recommendations

### Martin Fowler (Patterns of Enterprise Application Architecture)

Fowler defines three strategies: Single Table Inheritance, Class Table
Inheritance, and Concrete Table Inheritance. His guidance:

- **STI** when the hierarchy is simple and types share most fields
- **CTI** when you need data integrity and types have significant
  type-specific fields
- **Concrete** when types are independent and cross-type queries are rare
- You can mix strategies: "use Class Table Inheritance for the classes
  at the top of the hierarchy and Concrete Table Inheritance for those
  lower down"

### Eric Evans (Domain-Driven Design)

Evans does not prescribe specific database patterns but provides the
conceptual framework:

- Model types within a **Bounded Context** --- polymorphic hierarchies
  should not cross context boundaries
- If two "types" exist in different bounded contexts, they are
  different models, not subtypes
- The **Ubiquitous Language** should drive type decisions: if domain
  experts talk about "articles and videos" as distinct things (not as
  "content items"), separate models may better reflect the domain

### PostgreSQL Documentation

PostgreSQL natively supports table inheritance via the `INHERITS` clause.
However, the documentation itself carries important caveats:

- "Indexes (including unique constraints) and foreign key constraints
  only apply to single tables, not to their inheritance children"
- Table inheritance is most useful for partitioning, not for OOP-style
  type hierarchies
- For type hierarchies, use application-level patterns (STI, CTI, or
  Concrete) rather than native inheritance

### GitLab Engineering Guidelines

GitLab's official stance: **do not use STI for new tables.** Their
rationale:

- STI leads to oversized tables with poor query performance
- Additional indexes increase lock contention
- Filtering by type adds overhead to every query
- Solution: use separate tables per type

### thoughtbot (Ruby Science)

thoughtbot recommends:

- Use STI only when subclasses share most attributes
- If using STI for behavior reuse, **replace subclasses with strategies**
  (composition)
- If using STI for table-level polymorphism, switch to **polymorphic
  associations** (explicit join tables)
- Follow **composition over inheritance** as the default stance

### SQLAlchemy / ORM Framework Guidance

SQLAlchemy supports all three Fowler patterns. Their documentation notes:

- Joined Table Inheritance (CTI) is the most flexible but incurs JOIN cost
- Single Table Inheritance is simplest but least type-safe
- `with_polymorphic()` can optimize cross-type queries by eagerly loading
  specific subtypes
- Switching between STI and CTI is designed to be straightforward at the
  ORM layer

---

## Real-World Case Studies

### Stripe: Payment Methods

Stripe supports an ever-growing set of payment instruments. Their `PaymentMethod` has shared fields (`id`, `type`, `created`, `customer`) and a `payment_method_details` typed hash with type-specific data. This is essentially the JSON hybrid approach --- new payment types require no schema migration.

**Lesson:** When type cardinality is unbounded and types evolve independently, semi-structured storage within a structured envelope is the pragmatic choice.

### GitLab: The STI Retreat

GitLab used STI extensively. Tables like `keys` (both `Key` and `DeployKey`) grew to millions of rows with significant NULL waste. They now mandate separate tables. Migration pattern: create new table, dual-write, backfill, switch reads, drop old column.

**Lesson:** STI convenient at 10K rows becomes a burden at 10M rows. Migration cost grows with delay.

### Django Content Types

Django's `ContentType` framework provides generic foreign keys via `(content_type_id, object_id)`. Maximum flexibility, but no FK integrity, complex queries, and poor performance at scale. The community increasingly recommends explicit join tables for production.

**Lesson:** Generic relations are a framework escape hatch, not a primary modeling strategy.

---

## Summary Checklist

Before choosing polymorphism, answer these questions:

```
[ ] Do the types share more than 50% of their fields?
[ ] Do you need cross-type queries as a primary use case?
[ ] Do the types share meaningful behavior (not just field names)?
[ ] Are there fewer than 10 types (or is the set closed)?
[ ] Do the types evolve together (not independently)?
[ ] Does a single team own all the types?
[ ] Will the types remain more similar than different over time?
```

**Score:**
- 6-7 YES: Strong candidate for polymorphism (STI or CTI)
- 4-5 YES: Consider polymorphism with CTI or JSON hybrid
- 2-3 YES: Prefer composition, separate models, or search index
- 0-1 YES: These are not polymorphic. Use independent models.

---

## Sources

1. [Martin Fowler - Single Table Inheritance](https://www.martinfowler.com/eaaCatalog/singleTableInheritance.html) --- Pattern catalog from *Patterns of Enterprise Application Architecture*.

2. [Martin Fowler - Class Table Inheritance](https://martinfowler.com/eaaCatalog/classTableInheritance.html) --- CTI pattern description with tradeoff analysis.

3. [Martin Fowler - Concrete Table Inheritance](https://martinfowler.com/eaaCatalog/concreteTableInheritance.html) --- Alternative inheritance mapping for independent types.

4. [DoltHub - Choosing a Database Schema for Polymorphic Data (2024)](https://www.dolthub.com/blog/2024-06-25-polymorphic-associations/) --- Comprehensive comparison of five schema approaches with SQL examples.

5. [Hashrocket - Modeling Polymorphic Associations in a Relational Database](https://hashrocket.com/blog/posts/modeling-polymorphic-associations-in-a-relational-database) --- Exclusive belongs-to pattern as the recommended alternative to polymorphic joins.

6. [Real Python - Modeling Polymorphism in Django](https://realpython.com/modeling-polymorphism-django-python/) --- Six approaches compared: naive, sparse, semi-structured, abstract base, concrete base, generic FK.

7. [GitLab - Single Table Inheritance (Development Docs)](https://docs.gitlab.com/development/database/single_table_inheritance/) --- GitLab's official ban on new STI usage with rationale.

8. [thoughtbot - Single Table Inheritance (Ruby Science)](https://thoughtbot.com/ruby-science/single-table-inheritance-sti.html) --- When STI is appropriate and when to prefer composition.

9. [PostgreSQL Documentation - Table Inheritance](https://www.postgresql.org/docs/current/ddl-inherit.html) --- Native inheritance support with caveats on indexes and FK constraints.

10. [SQLAlchemy - Mapping Class Inheritance Hierarchies](https://docs.sqlalchemy.org/en/21/orm/inheritance.html) --- ORM-level support for all three Fowler patterns.

11. [Stripe - Payments APIs: The First 10 Years](https://stripe.com/blog/payment-api-design) --- Real-world polymorphic design at scale using typed hashes.

12. [Martin Fowler - Event Sourcing](https://martinfowler.com/eaaDev/EventSourcing.html) --- Event sourcing as an alternative paradigm for typed data.

13. [Software Patterns Lexicon - The God Table Anti-Pattern](https://softwarepatternslexicon.com/patterns-sql/16/2/1/) --- Detection criteria and refactoring strategies for monolithic tables.

14. [Eric Evans - Domain-Driven Design Reference](https://www.domainlanguage.com/wp-content/uploads/2016/05/DDD_Reference_2015-03.pdf) --- Bounded Context patterns for organizing type hierarchies.

15. [Django Documentation - The ContentTypes Framework](https://docs.djangoproject.com/en/6.0/ref/contrib/contenttypes/) --- Generic relations for framework-level polymorphic associations.

16. [TypeDB Blog - Inheritance and Polymorphism: Where the Cracks in SQL Begin to Show](https://typedb.com/blog/inheritance-and-polymorphism-where-the-cracks-in-sql-begin-to-show) --- Analysis of SQL's fundamental limitations for modeling inheritance.
