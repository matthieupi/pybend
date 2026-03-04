# N3TX as a Microservice Backbone: Strategic Analysis Report

## For: CEO & Engineering Team
## Date: February 2026
## Prepared by: Architecture Team

---

### How to Read This Document

This is a long document. Here are four paths through it depending on your time budget:

| Time | Path | Sections |
|------|------|----------|
| **5 min** | Executive Summary only | Executive Summary (below) |
| **15 min** | Decision-maker path | Executive Summary + Section 6 (Decision Framework) + Section 7 (Recommendation) |
| **30 min** | Technical leadership | Add Sections 3-4 (Architecture Overview + Our Stack Assessment) |
| **45 min** | Full read | Everything, start to finish |

Every section opens with a callout box summarizing the key finding. If you read only the callout boxes, you will have the thesis in three minutes.

---

## Executive Summary

**The core question:** Should N3TX evolve toward microservices, and if so, when and how?

**The short answer:** Not yet. But N3TX is already closer to microservice-ready than most frameworks at its stage, and the path from monolith to distributed services is unusually clean. The right move is to harden module boundaries now, extract services later when a concrete business trigger demands it, and avoid the premature decomposition trap that has burned 42% of organizations that adopted microservices too early.

### Key Findings

| Finding | Evidence | Implication |
|---------|----------|-------------|
| The microservices market is $9.1B and growing at 18-23% CAGR | IMARC, MRFR, Allied Market Research [01-industry-landscape.md] | The ecosystem investment is real and sustained |
| 85% of enterprises have microservices, but 90% batch-deploy like monoliths | Solo.io, DORA Metrics [01-industry-landscape.md] | Adoption != benefit. Most orgs get complexity without independence |
| 42% of adopters are consolidating services back | CNCF Survey via ByteIota [03-decision-framework.md] | The pendulum is swinging toward modular monoliths |
| `create_app()` already functions as a service factory | N3TX source: `app.py` lines 180-227 [04-our-stack-relevance.md] | Decomposition requires zero framework changes |
| The `authorize` package has zero N3TX imports | Source inspection: `rules.py`, `auth.py`, `context.py` [04-our-stack-relevance.md] | Auth is already a standalone, extractable module |
| JSON Schema as universal contract eliminates drift | `ProtoModel.schema()`: 55 lines of model -> 120 lines of contract [05-schema-as-service-contract.md] | N3TX's approach is structurally immune to the #1 integration failure |
| Teams under 50 engineers rarely break even on microservices | Cost analysis: 5-48x infrastructure multiplier [03-decision-framework.md] | The operational tax exceeds the benefit for most team sizes |

### Recommendation

**Phase 0 (Now):** Stay monolithic. Add health checks, request correlation IDs, and structured logging. Replace SQLite with PostgreSQL for production workloads. Effort: days, not weeks.

**Phase 1 (When team exceeds 10 engineers or deploy cadence diverges across domains):** Enforce module boundaries within the monolith. Namespace configuration. Build the `RemoteStorage` adapter. Effort: 2-4 weeks.

**Phase 2 (When a specific domain needs independent scaling or a separate team owns a domain end-to-end):** Extract that domain into its own `create_app()` instance. Use the same JSON Schema contract. Add an API gateway. Effort: 1-2 weeks per extraction.

**Phase 3 (When service count exceeds 5 and cross-service communication is frequent):** Invest in event-driven communication, distributed tracing (OpenTelemetry), and a platform engineering function. Effort: 4-8 weeks.

**Do not skip phases.** The number one failure pattern in the industry is jumping from Phase 0 to Phase 3.

---

## 1. What Are Microservices (and What They Are Not)?

> **Key Finding:** Microservices are an organizational scaling strategy disguised as a technical architecture. They solve the problem of multiple teams needing to deploy independently, not the problem of making code "better."

### 1.1 The Concept in Plain Language

Imagine a restaurant. A monolith is one kitchen where every chef shares every station, every oven, and every fridge. It works brilliantly when you have three chefs. When you have thirty, they trip over each other.

Microservices split the kitchen into independent stations -- one for appetizers, one for mains, one for desserts -- each with its own equipment, its own supplies, and its own team. The appetizer station can cook without waiting for the dessert station to finish. But now you need a system to coordinate orders across stations, a way to handle what happens when the main course is ready but the appetizer station is behind, and someone whose entire job is managing the kitchen layout.

The stations do not make the food better. They make it possible for thirty chefs to work without colliding.

### 1.2 The Technical Picture

```
MONOLITH:                              MICROSERVICES:

+---------------------------+          +--------+  +--------+  +--------+
|                           |          |Product |  | Order  |  |  User  |
|  Product  Order   User    |          |Service |  |Service |  |Service |
|  ------   -----   ----    |          |        |  |        |  |        |
|                           |          |  DB    |  |  DB    |  |  DB    |
|     Shared Database       |          +---+----+  +---+----+  +---+----+
|                           |              |           |           |
+---------------------------+          +---+-----------+-----------+---+
                                       |         API Gateway          |
         Single process.               +------------------------------+
         Single database.
         Single deploy.                 Multiple processes.
                                        Multiple databases.
                                        Independent deploys.
                                        Network between everything.
```

### 1.3 Historical Context

The microservices movement has a clear arc [01-industry-landscape.md]:

```
2002:  Bezos API Mandate at Amazon -- "communicate through service interfaces or be fired"
2011:  Netflix begins open-sourcing microservice tooling (Eureka, Hystrix, Zuul)
2014:  Martin Fowler and James Lewis publish the seminal "Microservices" article
2016:  Peak hype -- "microservices for everything"
2020:  COVID accelerates cloud migration; 92% adopter satisfaction (O'Reilly)
2023:  Amazon Prime Video moves back to monolith -- 90% cost reduction
2024:  85% enterprise adoption; "distributed monolith" recognized as dominant anti-pattern
2025:  42% of adopters consolidating services; modular monolith movement gains steam
2026:  Industry consensus: "it depends on your scale and team"
```

### 1.4 What Microservices Actually Solve

| Problem | How Microservices Help | Prerequisite |
|---------|----------------------|--------------|
| Multiple teams blocking each other on deploys | Independent deployment per service | Team owns service end-to-end |
| One component needs 100x more capacity | Independent scaling per service | Container orchestration (K8s) |
| Different components need different tech stacks | Polyglot persistence and runtime | Ops capacity per stack |
| One bug crashes the entire application | Fault isolation per service | Circuit breakers, health checks |
| Organizational scaling beyond ~50 engineers | Conway's Law alignment | Platform engineering team |

### 1.5 What They Do Not Solve

Microservices do not make code cleaner, APIs better, or developers more productive. They do not reduce bugs. They do not speed up a single team. They add network latency, distributed failure modes, and operational complexity. The only thing they reduce is the coordination cost between teams -- and that reduction only materializes when the teams, tooling, and organizational culture support it.

---

## 2. Industry Landscape

> **Key Finding:** The microservices market is $9.1 billion and growing, but the industry has matured past the hype cycle. The emerging consensus favors modular monoliths as the starting architecture, with selective service extraction when scaling demands it. This aligns precisely with N3TX's architecture.

### 2.1 Market Size and Growth

The microservices architecture market shows consistent double-digit growth, though absolute numbers vary by research methodology [01-industry-landscape.md]:

| Year | Market Size | Source | Scope |
|------|-------------|--------|-------|
| 2020 | ~$2.0B | Industry estimates | Core tooling |
| 2022 | ~$3.2B | IMARC Group | Core tooling |
| 2024 | ~$4.2B | IMARC Group | Core tooling |
| 2025 | ~$9.1B | Market Research Future | Tooling + orchestration |
| 2026 (projected) | ~$22.5B | Allied Market Research | Full cloud-native stack |
| 2033 (conservative) | $13.1B | IMARC (12.7% CAGR) | Core tooling |
| 2035 (aggressive) | $49.9B | MRFR (18.52% CAGR) | Full stack |

The 18-23% CAGR is consistent across sources. The absolute number depends on where you draw the line around "microservices market."

### 2.2 Adoption Rates

| Source | Year | Finding |
|--------|------|---------|
| Gartner Peer Community | 2024 | 74% of organizations use microservices; 23% plan to adopt |
| Solo.io Enterprise Survey | 2024 | 85% of enterprises have embraced microservices |
| CNCF Annual Survey | 2025 | 62.3% use microservices + container technologies |
| Stack Overflow Dev Survey | 2025 | 46% of backend developers work with microservices |

The gap between enterprise adoption (85%) and individual developer involvement (46%) is revealing. It means most orgs have microservices somewhere, but only a subset of senior engineers maintains them. This is concentrated ownership -- a pattern that suggests microservices are infrastructure, not a general-purpose development approach.

### 2.3 Who Succeeds

| Company | Architecture | Key Outcome | Lesson |
|---------|-------------|-------------|--------|
| **Netflix** | 700+ microservices | 99.99% uptime, 220M+ subscribers | Requires 15-20% of engineering on platform |
| **Amazon** | Thousands of services | 50M deploys/year, code every 11 seconds | Cultural prerequisite: "API mandate" in 2002 |
| **Spotify** | Squad-based ownership | 500M+ MAUs, rapid A/B testing | Org structure drove architecture, not vice versa |

### 2.4 Who Fails

| Company | What Happened | Outcome |
|---------|--------------|---------|
| **Amazon Prime Video** | Built video quality monitoring as microservices with Step Functions | Moved to monolith, 90% cost reduction |
| **Segment** | 150+ microservices overwhelmed the team | Migrated back to monolith, improved velocity |
| **Uber** | 1,000+ services without governance | Distributed monolith; recovered with domain-oriented architecture (DOMA) |
| **Unnamed startups** | 5-15 engineers starting with microservices | 3x cloud bills, lost orders from saga bugs, ran out of runway |

### 2.5 The Consolidation Trend

> **42% of organizations** that initially adopted microservices are now consolidating some services into larger deployable units or modular monoliths [03-decision-framework.md, citing CNCF Survey via ByteIota].

This does not mean microservices are dying. It means the industry learned that the default should be a modular monolith, with microservices reserved for domains where independent deployment and scaling genuinely matter.

### 2.6 The Python Framework Landscape

N3TX is built on FastAPI. FastAPI's trajectory is directly relevant [01-industry-landscape.md]:

| Framework | 2024 Share | 2025 Share | Trend |
|-----------|-----------|-----------|-------|
| Flask | 39% | ~36% | Slight decline |
| Django | 39% | ~37% | Slight decline |
| **FastAPI** | 25% | **38%** | **+52% YoY** |

FastAPI's admiration score on Stack Overflow is 74% -- second only to Phoenix (79%) across all web frameworks. This matters for hiring: building on FastAPI aligns with where Python developer interest is headed.

---

## 3. Technical Architecture Overview

> **Key Finding:** The technical patterns for microservices are well-established. The complexity is not in understanding the patterns but in operating them. Schema-driven development, as N3TX implements it, collapses several layers of microservice complexity into a single source of truth.

### 3.1 Communication Protocols Compared

| Protocol | Payload | Latency | Best For | N3TX Support |
|----------|---------|---------|----------|---------------|
| REST/JSON | Text (JSON) | Moderate (12ms p99 on FastAPI) | Public APIs, CRUD, external clients | Full (auto-generated) |
| gRPC | Binary (Protobuf) | Low (60% faster than REST) | Internal service-to-service | Not supported |
| GraphQL | Text (JSON) | Moderate-High | UI-heavy apps, BFF pattern | Not supported |
| Async events (Kafka, NATS) | Any | N/A (decoupled) | Cross-service state propagation | Not supported |

The 2025-2026 industry consensus: use REST for external APIs, gRPC for high-throughput internal calls, and async events for cross-service state changes [02-technical-deep-dive.md]. N3TX's REST-only position is fine for the monolith and early microservice stages. gRPC and event support become relevant at Phase 3.

### 3.2 Data Management: The Hard Part

The database-per-service pattern is not optional advice -- it is a foundational requirement for microservice independence [02-technical-deep-dive.md]. Sharing a database across services creates a distributed monolith. N3TX already supports per-model storage via the `storage=` parameter on `N3TXApp.model()`:

```python
# From /workspace/src/n3tx/core/app.py, lines 98-107
def model(self, model_class: Type, storage=None) -> "N3TXApp":
    """Register a model. Returns self for chaining.
    storage: Optional per-model storage override."""
    self._models.append((model_class, storage))
    return self
```

This means N3TX can run with one database today (simplicity) and split to per-model databases tomorrow (independence) with a configuration change, not an architecture change.

### 3.3 The Saga Pattern: Distributed Transactions

When an operation spans multiple services (e.g., "create order" requires Product, Payment, and Inventory), you need a saga -- a sequence of local transactions with compensating actions if any step fails [02-technical-deep-dive.md].

```
MONOLITH:                    MICROSERVICE SAGA:

BEGIN                        Order Service: Create order (PENDING)
  INSERT INTO orders ...         |
  UPDATE inventory ...       Inventory Service: Reserve stock
  INSERT INTO payments ...       | (if fails: compensate -> cancel order)
COMMIT                       Payment Service: Charge card
                                 | (if fails: compensate -> release stock,
(One DB, ACID guaranteed)        |                          cancel order)
                             Order Service: Confirm order (CONFIRMED)

                             (3 services, eventual consistency,
                              compensating transactions required)
```

N3TX does not support sagas today. In the monolith, it does not need to -- standard SQLite transactions provide ACID guarantees. Sagas become relevant only when services own separate databases. This is a Phase 3 concern.

### 3.4 The Service Mesh Question

Service mesh adoption has reached 70% among organizations running microservices [01-industry-landscape.md]. The two leading options:

| Mesh | Latency Overhead | Memory per Proxy | Complexity | Best For |
|------|-----------------|------------------|-----------|----------|
| **Istio** | Higher (sidecar proxy) | ~100-150 MB | High | Large enterprises, multi-cluster |
| **Linkerd** | 40-400% less than Istio | ~10 MB | Low | Teams that want mesh benefits without mesh pain |

> **Practical guidance from research:** Most teams under 500 engineers do not need a service mesh. If you have fewer than 20 microservices, application-level retries and circuit breakers (via `httpx` + `tenacity` in Python) deliver most of the benefit at a fraction of the complexity [01-industry-landscape.md].

### 3.5 Resilience Patterns

In a distributed system, failure is not an exception -- it is a certainty. The three core resilience patterns [02-technical-deep-dive.md]:

**Circuit Breaker:** Monitors calls to a downstream service and "trips" when failures exceed a threshold. Prevents the caller from hammering a failing service. Research data: circuit breakers alone reduced error rates by 58%.

```
CIRCUIT BREAKER STATES:

  CLOSED ---[failures exceed threshold]---> OPEN
    ^                                         |
    |                                    [timeout]
    |                                         |
    +---[test request succeeds]--- HALF-OPEN <+
```

**Bulkhead:** Isolates resource pools so one slow service cannot exhaust thread pools needed for other operations. Research data: bulkheads improved system availability by 10%.

**Retry with Exponential Backoff:** Handles transient failures with increasing delay between attempts. Always add jitter (randomized delay) to prevent the thundering herd problem. Research data: retries enhanced operation success rates by 21%.

N3TX does not implement any of these today. In monolith mode, they are unnecessary -- there are no network calls between components. They become essential at Phase 2 when services communicate over the network.

### 3.6 Observability: The Three Pillars

You cannot debug what you cannot see [02-technical-deep-dive.md]:

| Pillar | What | Tool | N3TX Status |
|--------|------|------|--------------|
| **Logs** | Discrete events with context | Structured JSON, correlation IDs | Partial (logging exists, no correlation IDs) |
| **Metrics** | Aggregated measurements over time | Prometheus/Grafana | Not implemented |
| **Traces** | Request flow across services | OpenTelemetry/Jaeger | Not implemented |

OpenTelemetry has become the industry standard: 79% of organizations either use or are evaluating it, and 89% of production users consider OTel compliance critical [02-technical-deep-dive.md].

For a monolith, structured logging with correlation IDs provides most of the debugging value. Distributed tracing (the expensive part) is only necessary when requests cross service boundaries.

### 3.7 Schema-Driven Development as a Pattern

The industry is converging on contract-first, model-driven approaches [01-industry-landscape.md, 05-schema-as-service-contract.md]:

| Approach | Source of Truth | Drift Risk | Maintenance | N3TX |
|----------|----------------|-----------|-------------|--------|
| Hand-written OpenAPI | YAML file | **High** | Manual, per-endpoint | N/A |
| Code-first OpenAPI | Code annotations | Medium | Semi-automatic | FastAPI provides this |
| Protocol Buffers | `.proto` file | Low (compiled) | Per-change | Not supported |
| **Model-first** | Model definition | **Zero** | **Zero** | **This is N3TX** |

When the model IS the schema, there is no separate spec to maintain. The frontend fetches the schema at runtime, the backend generates it from the same code that handles requests, and drift is structurally impossible. This is N3TX's strongest strategic advantage.

---

## 4. Our Current Architecture Assessment

> **Key Finding:** N3TX is a modular monolith with unusually clean service boundaries. The `create_app()` factory, per-model storage, auto-generated JSON Schema contracts, and standalone `authorize` package give it most of the microservice primitives without the distributed systems tax. The gaps are in infrastructure (service discovery, event bus, circuit breakers, distributed tracing) -- concerns that belong outside the application framework.

### 4.1 What N3TX Already Has

The assessment below is based on direct source code inspection, not documentation claims.

#### Service Factory: `create_app()`

From `/workspace/src/n3tx/core/app.py`, the `create_app()` function takes a list of models and produces a fully operational ASGI application:

```python
def create_app(
    models=None, join_models=None, storage=None,
    jwt_secret=None, name="N3TX", version="1.0.0", ...
):
    builder = N3TXApp(storage=storage, jwt_secret=jwt_secret, ...)
    for m in (models or []):
        builder.model(m)
    for parent, child in (join_models or []):
        builder.join(parent, child)
    return builder.build(name=name, version=version, ...)
```

This means you can already create independent services:

```python
# Product service -- standalone, self-contained
product_app = create_app(models=[Product], storage="sqlite:///product.db",
                         name="Product Service")

# User service -- completely independent
user_app = create_app(models=[User], storage="sqlite:///user.db",
                       name="User Service")
```

Each call produces an independent FastAPI application with its own storage, routes, middleware, and schema endpoints. These could be deployed to separate processes, containers, or machines today [04-our-stack-relevance.md].

#### Auto-Generated API Contracts

Every model generates a complete JSON Schema document via `ProtoModel.schema()` (lines 199-316 of `proto_model.py`). The schema carries:

- Field types and validation rules (from Pydantic)
- UI rendering hints (`ui.widget`, `ui.placeholder`, `ui.display`)
- Access control rules (`access.create`, `access.read`, `access.update`, `access.delete`)
- Callable methods with parameter types and return types
- Related entity schemas (`$defs` with full sub-schemas)
- Self-describing metadata (`$schema`, `$id` on every response)

This is richer than a standard OpenAPI spec. 55 lines of model definition produce ~120 lines of JSON Schema that describes the complete application concern [05-schema-as-service-contract.md].

#### Per-Model Storage Isolation

The `N3TXApp.model()` method accepts a per-model `storage` override. During build, each model gets its effective storage backend:

```python
for model_class, per_model_storage in self._models:
    effective_storage = (
        _resolve_storage(per_model_storage)
        if per_model_storage is not None
        else self._storage
    )
    register_model(model_class, storage=effective_storage)
```

This means database-per-service -- the foundational microservice data pattern -- is already supported at the framework level [04-our-stack-relevance.md].

#### Standalone Authorization

The `authorize` package (`/workspace/src/n3tx/core/authorize/`) has zero N3TX imports. It imports only from Python stdlib, typing, `jwt`, and `bcrypt`. The ABAC rules (`ANYONE`, `AUTHENTICATED`, `OWNER`, `ROLE`, `Where`) compose with `|`, `&`, `~` operators and serialize to JSON via `to_dict()`. The `AuthorizationResolver` protocol makes the entire resolution strategy swappable.

This is already a standalone library that happens to plug into N3TX. In a microservice architecture, it could be extracted as a shared package or a dedicated auth service with no code changes.

#### Model Registry

`registered_models` in `registrar.py` is an in-process dictionary mapping table names to model classes. It knows what models exist, what class implements each, what storage each uses, and what routes each exposes. This is the conceptual equivalent of a service registry, operating at module scope within a single Python process.

#### FK Hydration as HATEOAS

SQLiteStorage converts foreign key references into URLs (`sqlite_storage.py`, lines 174-179):

```python
for field_name, target_cls in ref_fields:
    val = record.get(field_name)
    if val is not None:
        target_table = getattr(target_cls, '__tablename__', target_cls.__name__.lower())
        record[field_name] = f"{config.API_URL}/{target_table}/{val}"
```

This means entities already reference each other via URLs, not raw IDs -- the correct pattern for distributed systems (HATEOAS). In a microservice world, `config.API_URL` resolves to the correct remote service. The change is configuration, not architecture.

### 4.2 What N3TX Lacks

```
+-------------------------------------------------------------------+
|              MICROSERVICE INFRASTRUCTURE GAP MAP                   |
+-------------------------------------------------------------------+
|  [create_app()]  [JSON Schema]  [Per-model DB]  [ABAC auth]      |
|   READY           READY          READY           READY            |
|                                                                   |
|  [Health checks]  [Schema versioning]  [Correlation IDs]         |
|   MISSING (small)  MISSING (small)       MISSING (small)          |
|                                                                   |
|  [Service client]  [Event system]  [Config namespace]            |
|   MISSING (medium)  MISSING (medium) MISSING (medium)             |
|                                                                   |
|  [Service discovery] [Circuit breakers] [Distributed tracing]    |
|   MISSING (large)     MISSING (large)    MISSING (large)          |
+-------------------------------------------------------------------+
```

Detailed gap analysis [04-our-stack-relevance.md]:

| Capability | Current State | Gap Size | Effort to Close |
|------------|---------------|----------|-----------------|
| Service factory | `create_app()` builds standalone apps | **None** | -- |
| API contracts | JSON Schema + OpenAPI auto-generated | **None** | -- |
| Per-service DB | `storage=` parameter per model | **None** | -- |
| Auth/AuthZ | JWT + ABAC, standalone package | **None** | -- |
| Health endpoint | Not implemented | Small | Add `/health` route (hours) |
| Schema versioning | `$id` URL but no version field | Small | Add version to schema (hours) |
| Request correlation IDs | Not implemented | Small | Middleware addition (days) |
| Service client | No built-in HTTP client for service calls | Medium | Build `RemoteStorage` adapter (1-2 weeks) |
| Event system | No pub/sub or event emission | Medium | Hook into `StorableMixin` lifecycle (2-4 weeks) |
| Config per service | Module globals, env var overrides | Medium | Namespace config module (1 week) |
| Service discovery | Not implemented | Large | Integrate Consul/DNS (4+ weeks) |
| Circuit breakers | Not implemented | Large | Add retry/fallback patterns (2-4 weeks) |
| Distributed tracing | Not implemented | Large | Add OpenTelemetry instrumentation (4+ weeks) |

### 4.3 The Unique Schema-Driven Advantage

Most microservice frameworks give you CRUD routes. N3TX gives you a **complete application contract** in a single schema document. The comparison [05-schema-as-service-contract.md]:

| Feature | OpenAPI (hand-written) | OpenAPI (code-first) | N3TX Schema |
|---------|----------------------|---------------------|---------------|
| Source of truth | YAML file | Code annotations | Model definition |
| Custom methods | Hand-written | Partial | From `@expose_route` |
| **Access control rules** | **Not included** | **Not included** | **From `__access__`** |
| **Field-level permissions** | **Not included** | **Not included** | **From `json_schema_extra`** |
| **UI rendering hints** | **Not included** | **Not included** | **From `__ui__`** |
| **Field ordering/grouping** | **Not included** | **Not included** | **From `field_order`, `groups`** |
| Drift risk | High | Medium | **Zero** |
| Maintenance burden | High | Low | **Zero** |

No framework in the comparison table generates a **working UI** from model definitions. In a microservice context, this means each service automatically has an admin interface, schema changes propagate to the UI without frontend deployments, and service teams get a functional dashboard for free [04-our-stack-relevance.md].

### 4.4 Comparison: N3TX vs. Established Microservice Frameworks

How does N3TX compare to frameworks designed for microservices from day one? [04-our-stack-relevance.md]:

| Feature | N3TX | Spring Boot | NestJS | FastAPI (raw) |
|---------|--------|-------------|--------|--------------|
| Model-driven CRUD | **Automatic** | Manual/JPA | Manual/TypeORM | Manual |
| API contract generation | **JSON Schema + OpenAPI** | OpenAPI | OpenAPI (Swagger) | OpenAPI |
| Schema-driven UI | **Built-in (N3TX.js)** | None | None | None |
| Auth/AuthZ | **Built-in (ABAC)** | Spring Security | Guards/Passport | Manual |
| Service factory | **`create_app()`** | `@SpringBootApplication` | `NestFactory.create()` | Manual |
| Service discovery | None | Eureka/Consul | None (manual) | None |
| Event bus | None | Spring Cloud Stream | CQRS module | None |
| Circuit breakers | None | Resilience4j | None (manual) | None |
| Health checks | None | Actuator | Terminus | None |

The pattern is clear: Spring Boot has the most mature microservice infrastructure, but N3TX has the most automated model-to-application pipeline. The missing pieces in N3TX (discovery, events, circuit breakers) are all infrastructure concerns that can be filled with external tools. N3TX's unique advantage -- the schema-driven UI and contract -- cannot be replicated by adding a library to Spring Boot.

### 4.5 The Frontend Actor System as a Microservice Pattern

The N3TX frontend already demonstrates a pattern relevant to microservices. The `Matrix` class in `Matrix.js` routes messages: local children get direct delivery, unknown targets go to the network. This is conceptually identical to a service mesh sidecar [04-our-stack-relevance.md]:

```
Matrix (Frontend Actor Bus)        Service Mesh Sidecar

Local children?                    Local service?
  |-- YES --> deliver directly       |-- YES --> forward locally
  |-- NO  --> route to network       |-- NO  --> route to remote service
```

A backend equivalent would route model operations locally when the model is registered in the same process, and forward to a remote service when it is not. The `RemoteStorage` adapter proposed in Phase 1 would implement exactly this pattern.

### 4.6 Code-Level Evidence: The Decomposition Path

N3TX's decomposition is mechanical, not architectural [04-our-stack-relevance.md]:

```
Step 1: Identify the model(s) to extract
Step 2: Create a new main.py:
          create_app(models=[ExtractedModel], storage="postgres://...")
Step 3: Migrate data to the new database
Step 4: Update API Gateway to route traffic
Step 5: Replace local references with remote hrefs
Step 6: Frontend continues to work -- schema contract unchanged
```

The key insight: the JSON Schema contract is identical whether the model lives in the monolith or in its own service. The frontend fetches the schema, creates DynamicClasses, and renders. It does not care where the schema came from.

---

## 5. Cost-Benefit Analysis

> **Key Finding:** Microservices infrastructure costs 5-48x more than a monolith. People costs (platform team, per-developer overhead) are often larger than infrastructure costs. For teams under 50 engineers, the break-even point rarely arrives. N3TX's schema-driven approach reduces the integration tax that accounts for 40-60% of microservice engineering effort.

### 5.1 Infrastructure Cost Comparison

From the decision framework research [03-decision-framework.md]:

| Category | Monolith | Modular Monolith | 10 Microservices | 50 Microservices |
|----------|----------|-----------------|-----------------|-----------------|
| Compute | $200/mo | $200-400/mo | $500-1,000/mo | $2,500-5,000/mo |
| Container orchestration | N/A | N/A | $200-500/mo | $500-2,000/mo |
| Service mesh | N/A | N/A | $200-400/mo | $500-1,500/mo |
| API gateway | Included | Included | $100-300/mo | $200-500/mo |
| Observability | $50-100/mo | $50-100/mo | $300-800/mo | $1,000-3,000/mo |
| CI/CD pipelines | 1 | 1 | 10 | 50 |
| **Total infra** | **$250-300/mo** | **$250-500/mo** | **$1,300-3,000/mo** | **$4,700-12,000/mo** |
| **Multiplier** | 1x | 1-2x | **5-12x** | **19-48x** |

### 5.2 People Cost (Often the Larger Number)

| Role | Monolith | Modular Monolith | Microservices |
|------|----------|-----------------|--------------|
| Platform engineering | 0 FTE | 0-0.5 FTE | 1-3 FTE |
| SRE / DevOps | 0.5 FTE | 0.5-1 FTE | 2-5 FTE |
| Per-developer overhead | ~5% time on infra | ~10% time on infra | ~25-35% time on infra |

At $150K/year per engineer, a 3-person platform team costs $450K/year before they write a single product feature. For a 15-person engineering org, that is 20% of the engineering budget on infrastructure that does not ship features.

### 5.3 Hidden Costs Documented in Post-Mortems

From industry research [01-industry-landscape.md]:

- **3x cloud bill increase** compared to monolithic deployment
- **60% of performance issues** stem from network latency and inter-service communication
- **3-4x longer debugging time** for distributed failures vs. monolithic failures
- CI/CD complexity grows **linearly with service count**

### 5.4 N3TX's Structural Cost Advantage

The schema-driven approach directly reduces the largest cost categories [05-schema-as-service-contract.md]:

| Cost Category | Conventional Microservices | N3TX Microservices |
|---------------|--------------------------|---------------------|
| API contract maintenance | Manual per endpoint | Auto-generated from model |
| Frontend sync | Separate deploy per change | Frontend reads schema at runtime |
| Contract testing | Pact tests per boundary | Schema IS the contract |
| Boilerplate per service | 200+ lines of glue code | ~20 lines of model definition |
| Integration debugging | 40-60% of engineering effort | Reduced -- single source of truth |

### 5.5 The Integration Tax

Every microservice boundary introduces an "integration tax" -- the engineering effort required to keep two services communicating correctly. Research estimates this at 40-60% of total engineering effort in microservice architectures [05-schema-as-service-contract.md]. The tax breaks down:

| Tax Component | Conventional | N3TX (Schema-Driven) |
|---------------|-------------|----------------------|
| API client maintenance | 10-15% of effort | Near-zero (schema IS the client spec) |
| Contract testing | 5-10% of effort | Reduced (schema validation replaces Pact) |
| Type synchronization | 5-10% of effort | Zero (types from model, not duplicated) |
| Documentation sync | 5-10% of effort | Zero (auto-generated from model) |
| Auth rule distribution | 5-10% of effort | Reduced (rules in schema, enforced per-service) |
| Frontend adaptation | 10-15% of effort | Zero (frontend reads schema at runtime) |

N3TX's schema-driven approach does not eliminate the integration tax entirely -- network calls, distributed debugging, and data consistency still cost engineering time. But it eliminates the **specification maintenance** component, which is the largest single contributor. When the model IS the spec, half the integration tax disappears.

### 5.6 The Developer Experience Cost

Microservices have a significant developer experience tax that is rarely quantified in advance [01-industry-landscape.md]:

| DX Problem | Monolith Impact | Microservice Impact |
|-----------|----------------|-------------------|
| Local development | Run one process | Run 10-50 services (or maintain mocks that drift) |
| Debugging a request | One stack trace | Trace across 5-10 services with correlation IDs |
| Running tests | One test suite | Per-service suites + contract tests + E2E |
| Onboarding a new developer | 1-2 weeks | 3-6 weeks (learn infrastructure + domain) |
| Making a cross-cutting change | One PR | N PRs across N repositories |

N3TX's model-driven approach mitigates several of these. In monolith mode, it is one process with one test suite. In microservice mode, each extracted service is self-documenting through its schema, reducing the onboarding burden. But the debugging and testing overhead remains -- that is an inherent property of distributed systems.

### 5.7 Investment Required by Phase

| Phase | Investment | Expected Return | Time to Value |
|-------|-----------|----------------|--------------|
| **Phase 0** (harden monolith) | Days of work (health checks, logging) | Immediate: better debugging, prod readiness | < 1 week |
| **Phase 1** (module boundaries) | 2-4 weeks | Cleaner codebase, testable domains, prep for extraction | 1-2 months |
| **Phase 2** (first extraction) | 1-2 weeks per service | Independent deploy/scale for hot paths | 2-4 weeks |
| **Phase 3** (full infrastructure) | 4-8 weeks + platform team | Full microservice benefits (if org needs them) | 3-6 months |

---

## 6. Decision Framework

> **Key Finding:** The right architecture depends on team size, domain complexity, scaling needs, and operational maturity. A scoring model based on five dimensions determines whether to stay monolithic, adopt a modular monolith, extract select services, or go full microservices. N3TX applications should remain monolithic until a concrete trigger demands otherwise.

### 6.1 The Five-Dimension Assessment

Score your organization across five dimensions (1-5 each) [03-decision-framework.md]:

| Dimension | 1 (Stay Monolith) | 3 (Modular Monolith) | 5 (Consider Microservices) |
|-----------|-------------------|---------------------|---------------------------|
| **Team Size** | 1-5 developers | 10-25 developers | 50+ developers |
| **Deploy Frequency** | Weekly or less | Daily | Multiple/day per team |
| **Scaling Needs** | Uniform load | Moderate variation | Hot-path needs 10x+ independent scaling |
| **Domain Complexity** | 1 bounded context | 3-5 bounded contexts | 10+ bounded contexts |
| **Operational Maturity** | Manual deploys | CI/CD, centralized logging | Platform team, canary deploys, tracing |

| Total Score | Recommended Architecture |
|-------------|------------------------|
| **5-10** | Simple monolith -- team overhead of distribution outweighs benefits |
| **11-17** | Modular monolith -- structure needed but distribution premature |
| **18-21** | Extract 2-5 services from hot paths |
| **22-25** | Full microservices with dedicated platform engineering |

### 6.2 Decision Tree

```
START
  |
  v
[Team size > 50 developers?]
  |
  +-- YES --> [Domain has 10+ distinct bounded contexts?]
  |             |
  |             +-- YES --> [DevOps maturity Level 3+?]
  |             |             |
  |             |             +-- YES --> MICROSERVICES (with platform team)
  |             |             |
  |             |             +-- NO  --> MODULAR MONOLITH
  |             |                         + invest in DevOps maturity
  |             |
  |             +-- NO  --> MODULAR MONOLITH
  |
  +-- NO
       |
       v
  [Team size 10-50?]
       |
       +-- YES --> [Specific component needs 10x independent scaling?]
       |             |
       |             +-- YES --> MODULAR MONOLITH + extract 1-3 hot-path services
       |             |
       |             +-- NO  --> MODULAR MONOLITH
       |
       +-- NO (team < 10)
            |
            v
       SIMPLE MONOLITH (revisit when team grows)
```

### 6.3 When NOT to Adopt Microservices

This is the most important subsection in this document [03-decision-framework.md]:

| Condition | Why Not |
|-----------|---------|
| **Team < 10 developers** | Coordination costs exceed benefits. Below 10 devs, monoliths outperform on delivery speed. |
| **Pre-product-market-fit** | Domain model changes weekly. Refactoring across service boundaries is 10x harder. |
| **Low traffic (< 1000 RPM)** | A single $50/month server handles this. Microservices start at $750/month for equivalent. |
| **Simple domain (1-3 contexts)** | Distribution adds latency and failure modes without organizational benefits. |
| **No platform/DevOps team** | Without platform engineering, developers build infrastructure instead of product. |
| **Tight deadline / PoC** | Microservices add 3-6 months of infrastructure setup before the first feature ships. |

### 6.4 Anti-Patterns to Avoid

| Anti-Pattern | Frequency | Consequence |
|-------------|-----------|-------------|
| **Distributed monolith** | 90% of microservice teams (DORA) | All complexity, no independence |
| **Nano-services** | Very common in early adopters | Deploy orchestration exceeds service value |
| **Shared database** | Extremely common | Destroys deployment independence |
| **Premature decomposition** | Almost universal in startups | Domain boundaries wrong; painful to fix |
| **Synchronous chains** | Common | 5+ service hops = cascading failures |

### 6.5 Alternatives to Full Microservices

Before committing to microservices, evaluate these lighter-weight alternatives [03-decision-framework.md]:

**Modular Monolith:** Single deployable artifact with enforced internal module boundaries. N3TX's model-driven architecture already provides natural boundaries. Shopify proves this scales to 32M+ req/min.

**Queue-Based Workers:** Background job processors consuming from a message queue. Deployed separately but sharing the same codebase. Gives independent scaling of web and worker tiers without service boundary complexity.

```
Web tier (N3TX)  --publish-->  Message Queue  --consume-->  Worker Process
                               (Redis, SQS)                  (same codebase,
                                                               different entry)
```

**Serverless Functions:** Offload specific tasks (PDF generation, email sending, image processing) to AWS Lambda or similar. Keep the core application as a monolith; extend with serverless for bursty, stateless work.

**Edge Workers:** Code running at CDN edge locations (Cloudflare Workers, Deno Deploy). Best for request routing, auth at the edge, and personalized content. Not suitable for database-heavy operations.

| Alternative | Operational Complexity | Independent Scaling | Team Autonomy | Cost |
|-------------|----------------------|-------------------|--------------|------|
| Modular Monolith | Low | No | Medium | Low |
| Queue Workers | Low-Medium | Yes (web vs. worker) | Low-Medium | Low-Medium |
| Serverless Functions | Low (managed) | Yes (per function) | Medium | Variable |
| Edge Workers | Low (managed) | Yes (per region) | Medium | Low |
| Microservices | **High** | Yes (per service) | High | **High** |

### 6.6 Measurable Triggers for Extraction

Do not decompose preemptively. Wait for a concrete, measurable trigger:

| Trigger | Threshold | Measurement |
|---------|-----------|-------------|
| Team size crossing | > 10 engineers on same codebase | Headcount |
| Deploy cadence divergence | One domain changes hourly, others weekly | Deploy frequency per module |
| Scaling requirement | One model needs 100x more capacity | Request volume per endpoint |
| Fault isolation need | One model's failure crashes unrelated features | Incident post-mortems |
| Technology mismatch | One model needs Elasticsearch, another needs Postgres | Technical requirements analysis |

---

## 7. Recommendation

> **Key Finding:** N3TX should remain a monolith while hardening its module boundaries. The investments that matter now -- health checks, correlation IDs, structured logging, PostgreSQL -- pay off regardless of future architecture. Decomposition should be triggered by concrete organizational or scaling needs, not by aspiration.

### 7.1 Phased Approach

#### Phase 0: Harden the Monolith (Now -- days, not weeks)

| Action | Effort | Value |
|--------|--------|-------|
| Add `GET /health` endpoint | Hours | Load balancer readiness, basic monitoring |
| Add request correlation IDs to JWT middleware | 1 day | Debugging aid; essential for future tracing |
| Add structured JSON logging | 1-2 days | Log aggregation readiness |
| Replace SQLite with PostgreSQL for production | 1-2 days | Concurrent writes, horizontal scaling |
| Containerize with Docker | 1 day | Deployment consistency |

**Review trigger:** When team exceeds 10 engineers OR deploy frequency exceeds twice per day.

#### Phase 1: Enforce Module Boundaries (When triggered -- 2-4 weeks)

| Action | Effort | Value |
|--------|--------|-------|
| Namespace the config module | 1 week | Multiple `create_app()` in same process for testing |
| Build `RemoteStorage` adapter | 1-2 weeks | One service can treat another's models as local |
| Add `/_meta` endpoint exposing model registry | Days | Service discovery preparation |
| Add schema versioning field | Hours | Backward compatibility checks in CI |
| Enforce Python package structure by domain | 1 week | Clear ownership boundaries |

**Review trigger:** When a specific domain needs independent scaling OR a separate team owns a domain end-to-end.

#### Phase 2: Selective Extraction (When triggered -- 1-2 weeks per service)

```
Step 1: Identify the model to extract (e.g., User/Auth -- typically first)
Step 2: create_app(models=[User], storage="postgres://...")
Step 3: Migrate data to new database
Step 4: API Gateway routes /users/* to new instance
Step 5: Replace ListRef with href references in other models
Step 6: Frontend continues to work (schema contract unchanged)
Step 7: Monitor DORA metrics for 2-4 weeks
Step 8: If metrics improve, proceed. If not, consolidate back.
```

**Review trigger:** When service count exceeds 5 AND cross-service communication is frequent.

#### Phase 3: Full Infrastructure (When triggered -- 4-8 weeks)

| Action | Effort | Value |
|--------|--------|-------|
| Event-driven communication (Redis Pub/Sub or NATS) | 2-4 weeks | Async cross-service state propagation |
| OpenTelemetry distributed tracing | 2-4 weeks | Cross-service debugging |
| Circuit breakers (`tenacity` + custom) | 1-2 weeks | Resilience against downstream failures |
| Platform engineering function | Ongoing | Sustainable microservice operations |

### 7.2 Architecture Diagram: Current vs. Decomposed

```
CURRENT: Schema-Driven Monolith
+------------------------------------------------------+
|                    Single Process                      |
|                                                        |
|  create_app(models=[User, Product, Comment], ...)      |
|                                                        |
|  +----------+  +----------+  +----------+              |
|  |   User   |  | Product  |  | Comment  |  shared     |
|  |  model   |  |  model   |  |  model   |  SQLite DB  |
|  +----------+  +----------+  +----------+              |
|       |              |             |                    |
|       v              v             v                    |
|  +--------------------------------------------------+  |
|  |          registered_models{} (in-process)         |  |
|  +--------------------------------------------------+  |
|       |              |             |                    |
|       v              v             v                    |
|  +--------------------------------------------------+  |
|  |      FastAPI Router (auto-generated CRUD)         |  |
|  +--------------------------------------------------+  |
|       |                                                 |
|       v                                                 |
|  +--------------------------------------------------+  |
|  |    JWTAuthMiddleware + ABAC Resolver              |  |
|  +--------------------------------------------------+  |
+------------------------------------------------------+


DECOMPOSED: Multiple N3TX Instances
+------------------+  +--------------------+  +-------------------+
|  User Service    |  |  Product Service   |  |  Comment Service  |
|                  |  |                    |  |                   |
| create_app(      |  | create_app(        |  | create_app(       |
|   models=[User]) |  |   models=[Product])|  |   models=[Comment]|
|                  |  |                    |  |   )               |
| Postgres: user   |  | Postgres: product  |  | Postgres: comment |
| Port: 5001       |  | Port: 5002         |  | Port: 5003        |
|                  |  |                    |  |                   |
| GET /User        |  | GET /Product       |  | GET /Comment      |
| GET /users       |  | GET /products      |  | GET /comments     |
| POST /users/login|  | POST /products     |  | POST /comments    |
+------------------+  +--------------------+  +-------------------+
         |                      |                       |
         v                      v                       v
+--------------------------------------------------------------+
|                     API Gateway (Kong/Traefik)                |
|  Routes: /users/* -> :5001, /products/* -> :5002, etc.       |
+--------------------------------------------------------------+
         |
         v
+--------------------------------------------------------------+
|                    Frontend (N3TX.js)                          |
|  Fetches schemas from gateway, renders dynamically           |
|  Schema contract identical -- frontend does not know the     |
|  difference between monolith and microservices               |
+--------------------------------------------------------------+
```

The critical observation: the frontend code is identical in both diagrams. It fetches a schema, creates DynamicClasses, and renders. Whether the schema comes from a monolith or a dedicated service is transparent.

### 7.3 What NOT to Do

1. **Do not decompose before Phase 0 is complete.** Health checks and logging are prerequisites.
2. **Do not skip the modular monolith phase.** It delivers 80% of microservice benefits at 10% of the cost.
3. **Do not extract more than one service at a time.** Each extraction changes the system's topology.
4. **Do not introduce a service mesh before you have 20+ services.** Application-level resilience is sufficient below that.
5. **Do not adopt Kubernetes until you have at least 5 independently deployed services.** A single Docker container on a VPS is operationally simpler and cheaper.
6. **Do not choose microservices because Netflix does.** Netflix has 15-20% of engineering on platform. Scale your architecture to your team, not to your ambition.

### 7.4 Success Metrics (DORA)

Track these four metrics before and after any architecture change [03-decision-framework.md]:

| Metric | Elite | High | Medium | Low |
|--------|-------|------|--------|-----|
| **Deploy Frequency** | Multiple/day | Weekly-monthly | Monthly-biannually | < once/6 months |
| **Lead Time for Changes** | < 1 hour | 1 day - 1 week | 1 week - 1 month | 1-6 months |
| **Change Failure Rate** | 0-5% | 5-10% | 10-15% | 16-30%+ |
| **MTTR** | < 1 hour | < 1 day | 1 day - 1 week | 1 week+ |

**Key insight from DORA research:** Elite performers are 2x more likely to exceed organizational goals in profitability, productivity, and customer satisfaction. Architecture changes should improve these metrics. If they do not, the change has not delivered value.

After each extraction, check:

| Signal | Healthy | Warning | Failure |
|--------|---------|---------|---------|
| Deploy frequency | Increased per team | Unchanged | Decreased (deploy coordination) |
| Lead time | Decreased | Unchanged | Increased (cross-service testing) |
| Change failure rate | Stable or decreased | Slight increase | Significant increase |
| MTTR | Decreased (fault isolation) | Unchanged | Increased (distributed debugging) |

If three or more signals show "Warning" or "Failure" after 4 weeks, consolidate back. The architecture is designed to make this reversal clean.

### 7.5 Review Cadence

| Review | Frequency | Participants | Decision |
|--------|-----------|-------------|----------|
| Architecture fitness check | Quarterly | CTO + lead engineers | Score the five dimensions; compare to previous quarter |
| DORA metrics review | Monthly | Engineering team | Track deploy frequency, lead time, failure rate, MTTR |
| Cost-benefit checkpoint | Quarterly | CEO + CTO | Compare actual infra + people cost vs. monolith baseline |
| Trigger assessment | As needed | Team leads | Is any trigger from Section 6.5 met? |

---

## 8. Risk Register

> **Key Finding:** The risks of premature microservice adoption are more severe than the risks of delayed adoption. N3TX's architecture makes the monolith-to-microservice transition reversible, which is its strongest strategic property.

### 8.1 Probability-Impact Matrix

| # | Risk | Probability | Impact | Risk Level | Mitigation |
|---|------|-------------|--------|------------|------------|
| R1 | **Premature decomposition** -- splitting before understanding domain boundaries | High (if we act without triggers) | High | **Critical** | Follow decision framework; require measured trigger before extraction |
| R2 | **Distributed monolith** -- extracting services that still deploy in lockstep | Medium | High | **High** | Score against warning signs checklist (Section 6.4); merge back if score > 5 |
| R3 | **SQLite production limitations** -- concurrent write contention under load | High (already present) | Medium | **High** | Migrate to PostgreSQL in Phase 0; immediate priority |
| R4 | **Schema contract breaks** -- accidental breaking change in model definition | Low (schema is auto-generated) | Medium | **Medium** | Add schema diff check in CI (compare old vs. new `model.schema()`) |
| R5 | **Complexity explosion** -- too many services, too fast | Medium (if Phase 3 reached) | High | **High** | Cap at 3-5 services per extraction round; measure DORA before and after |
| R6 | **Network failures in distributed mode** | Certain (in time) | Medium | **High** | Circuit breakers, retries with backoff, bulkheads. Design for failure from Phase 2 |
| R7 | **Skill gap** -- team lacks distributed systems experience | Medium | Medium | **Medium** | Invest in training before Phase 2; consider hiring or consulting |
| R8 | **Cost overrun** -- microservice infra cost exceeds budget | High (5-48x multiplier) | Medium | **High** | Budget 3-6x monolith cost; track actual vs. projected monthly |
| R9 | **Vendor lock-in** -- deep dependency on specific cloud services | Low (N3TX is cloud-agnostic) | Medium | **Low** | Use open standards: OCI containers, OpenTelemetry, CloudEvents |
| R10 | **Debugging difficulty** -- distributed traces across service boundaries | Certain (in distributed mode) | Medium | **Medium** | Invest in OpenTelemetry before Phase 3; correlation IDs from Phase 0 |

### 8.2 Risk Mitigation Summary

The strongest mitigation across all risks is **phased adoption with measurable triggers**. Every phase has a review gate. Every extraction has a rollback path (`create_app()` works identically in monolith and service mode). The architecture is designed so that the decision is reversible -- and that is the single most important property for managing risk in an uncertain environment.

---

## 9. Appendices

### Appendix A: Schema Evolution and CloudEvents Compatibility

A critical concern in microservice architectures is how schemas evolve without breaking consumers. N3TX's model-first approach has a structural advantage here [05-schema-as-service-contract.md]:

**Additive-Only Evolution (the default):** When a developer adds a field with a default value, the change is fully compatible. Old producers omit it; new consumers see the default. Old consumers ignore it; new producers include it. This happens naturally with Pydantic's `Field(default=...)` syntax.

```python
class Product(ProtoModel):
    name: str
    price: float
    currency: str = Field(default='USD')  # New field -- additive, compatible
```

The schema automatically includes the new field. The database migrates. The API returns it. The frontend form gains a new input. No manual version bump, no spec update, no consumer notification.

**Breaking Changes (require code review):** Removing a field or changing a type requires modifying the model, which means a pull request, which means the change is deliberate and visible. The schema cannot drift because it does not exist independently of the code.

**Schema Versioning Modes** (from Confluent Schema Registry conventions):

| Mode | Meaning | Safe Changes |
|------|---------|-------------|
| BACKWARD | New schema can read old data | Add optional fields, remove fields |
| FORWARD | Old schema can read new data | Add fields, remove optional fields |
| FULL | Both directions | Add/remove optional fields only |

A CI-level schema diff (comparing `old_model.schema()` vs `new_model.schema()`) can enforce FULL compatibility automatically.

**CloudEvents Compatibility:** N3TX entities already carry `$schema` and `$id` in every response via `model_dump(response=True)`. These map directly to CloudEvents' `dataschema` and `subject` attributes. Wrapping a N3TX entity in a CloudEvents envelope requires only metadata:

```python
def to_cloud_event(instance):
    data = instance.model_dump(response=True)
    return {
        "specversion": "1.0",
        "type": f"com.n3tx.{instance.__class__.__name__.lower()}.created",
        "source": f"/{instance.__tablename__}",
        "dataschema": data['$schema'],
        "data": data,
    }
```

Every consumer can resolve `dataschema` to get the complete contract. This is forward-compatible with the event-driven architecture needed at Phase 3.

### Appendix B: Glossary

| Term | Definition |
|------|-----------|
| **ABAC** | Attribute-Based Access Control. Rules compose with `\|`, `&`, `~`. N3TX implements this in the standalone `authorize` package. |
| **Bounded Context** | A domain-driven design concept: a linguistic and conceptual boundary within which a domain model is internally consistent. Often maps 1:1 to a microservice. |
| **CQRS** | Command Query Responsibility Segregation. Separates write models from read models for independent optimization. |
| **Conway's Law** | "Any organization that designs a system will produce a design whose structure is a copy of the organization's communication structure." |
| **DynamicClass** | N3TX frontend entity. Created at runtime from backend JSON Schema via `N3TX.prototype()`. |
| **DORA Metrics** | Four metrics for software delivery performance: deploy frequency, lead time, change failure rate, MTTR. |
| **HATEOAS** | Hypermedia as the Engine of Application State. N3TX's FK hydration produces URLs, not raw IDs. |
| **Modular Monolith** | Single deployable artifact with enforced internal module boundaries. Shopify's 2.8M-line Ruby codebase is the canonical example. |
| **ProtoModel** | N3TX's base model class. Generates JSON Schema, injects StorableMixin, handles serialization. |
| **RemoteStorage** | Proposed `AbstractStorage` implementation that delegates CRUD to a remote N3TX service's REST API. Key enabler for service extraction. |
| **Saga** | A pattern for managing distributed transactions across multiple services using local transactions and compensating actions. |
| **Schema Drift** | The divergence between an API specification and actual API behavior. N3TX's model-first approach makes this structurally impossible. |
| **Service Mesh** | Infrastructure layer (Istio, Linkerd) that handles mTLS, load balancing, and traffic management between services. |
| **Strangler Fig** | Migration pattern that incrementally replaces monolith functionality with new services. Named after the strangler fig tree. |
| **create_app()** | N3TX's one-liner factory. Takes a list of models, produces a complete ASGI application. Functions as a service factory. |

### Appendix C: Case Study Details

#### Amazon Prime Video (2023)

The Video Quality Analysis team built their monitoring system as microservices using AWS Step Functions and S3. Each video frame was serialized, uploaded to S3, then downloaded by the next service. The system hit scaling limits at 5% of expected load. AWS Step Functions charged per state transition -- costs exploded. Moving to a monolith reduced infrastructure costs by 90%.

**Lesson:** Microservices are for organizational scaling (independent teams deploying independently), not for decomposing compute-bound pipelines.

#### Shopify (Ongoing)

Shopify processes hundreds of billions in commerce annually. Their 2.8M-line Ruby monolith handles 30TB per minute and 32M+ requests per minute. Rather than splitting into microservices, they invested in component boundaries within the monolith using Rails Engines and Packwerk. Goal: "increased modularity without increasing the number of deployment units."

**Lesson:** A well-structured monolith scales further than most teams assume. The largest e-commerce platform in the world runs on one.

#### Segment (2018-2020)

Segment grew to 150+ microservices and then migrated back to a monolith. Each service required its own CI/CD pipeline, monitoring, alerting, and on-call rotation. The operational overhead exceeded engineering capacity. Developer velocity decreased as engineers spent more time on infrastructure than on product.

**Lesson:** Microservice count must match team capacity. When operational overhead exceeds product development capacity, consolidate.

#### Uber (2015-2020)

Uber aggressively decomposed from monolith to 1,000+ microservices. The initial benefit was rapid scaling from startup to global platform. But without architectural governance, dependency tangles and cascading failures became the norm. The company spent years recovering -- introducing domain-oriented microservices architecture (DOMA), global service standards, and quantifiable requirements for documentation, reliability, and fault tolerance.

**Lesson:** Going from monolith to 1,000+ services without governance creates a distributed monolith. Recovering after the fact (imposing domain boundaries retroactively) is harder than getting boundaries right from the start. This is exactly the approach N3TX's phased methodology avoids.

#### Kelsey Hightower's Position (2024-2026)

Kelsey Hightower, former Google and Kubernetes evangelist, became one of the most vocal advocates for the monolith-first approach:

> "Monoliths are the future. The problem people are trying to solve with microservices doesn't really line up with reality."
> "Start with a modular monolith, and let it evolve."
> "A monolithic architecture doesn't mean spaghetti code. You should be writing modular code regardless of the deployment model."

His position is not anti-microservices -- it is anti-premature-decomposition. The argument aligns with N3TX's strategy: build modular code in a monolith, extract only when organizational triggers demand it.

### Appendix D: Source References

#### Research Documents

| Document | Path | Focus |
|----------|------|-------|
| Industry Landscape | `/workspace/.traces/research/microservices/01-industry-landscape.md` | Market sizing, frameworks, adoption data, success/failure stories |
| Technical Deep Dive | `/workspace/.traces/research/microservices/02-technical-deep-dive.md` | Architecture patterns, communication protocols, resilience, testing |
| Decision Framework | `/workspace/.traces/research/microservices/03-decision-framework.md` | Five-dimension scoring, Conway's Law, cost analysis, alternatives |
| Our Stack Relevance | `/workspace/.traces/research/microservices/04-our-stack-relevance.md` | N3TX gap analysis, decomposition path, framework comparison |
| Schema as Contract | `/workspace/.traces/research/microservices/05-schema-as-service-contract.md` | JSON Schema ecosystem, contract testing, schema evolution, N3TX advantage |

#### Key Source Files

| File | Role |
|------|------|
| `/workspace/src/n3tx/core/app.py` | Service factory (`create_app`, `N3TXApp`) |
| `/workspace/src/n3tx/core/models/proto_model.py` | Schema generation, model lifecycle, `model_dump(response=True)` |
| `/workspace/src/n3tx/core/api/routes_fastapi.py` | Auto-generated CRUD routes, custom method routing |
| `/workspace/src/n3tx/core/storage/sqlite_storage.py` | SQLite backend with connection pool, FK hydration, batch loading |
| `/workspace/src/n3tx/core/utils/registrar.py` | Model registry (`registered_models`, `join_models`) |
| `/workspace/src/n3tx/core/authorize/rules.py` | ABAC rules: `ANYONE`, `AUTHENTICATED`, `OWNER`, `ROLE`, `Where` |
| `/workspace/src/n3tx/core/authorize/auth.py` | JWT: `create_token`, `decode_token`, `hash_password` |
| `/workspace/src/n3tx/core/config.py` | Configuration with env var overrides, `configure()` |

#### External Sources (Selected)

1. Gartner Peer Community -- Microservices Architecture survey (2024)
2. IMARC Group -- Microservices Architecture Market Size 2025-2033
3. Market Research Future -- Microservices Architecture Market Trends 2035
4. JetBrains -- Most Popular Python Frameworks 2025
5. Stack Overflow Developer Survey 2025
6. Shopify Engineering -- Under Deconstruction: The State of Shopify's Monolith
7. Amazon Prime Video -- Video Quality Analysis case study (2023)
8. CNCF Annual Survey 2025
9. DORA Report 2025 -- DevOps Research and Assessment
10. Kelsey Hightower -- "Monoliths are the future" (The New Stack)
11. Linkerd vs Istio benchmarks 2025 (Buoyant)
12. ByteIota -- "42% Ditch Microservices in 2026"

Full source lists with URLs are available in each research document in the appendix.

---

*This analysis was prepared for engineering leadership as a strategic assessment of N3TX's position relative to the microservices market. The recommendation is to stay monolithic, harden boundaries, and extract services only when measured triggers demand it. Review quarterly.*
