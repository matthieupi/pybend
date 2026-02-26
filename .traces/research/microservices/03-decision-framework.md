# Decision Framework: When to Adopt Microservices

**Audience:** Technical CEOs, CTOs, and Engineering Teams
**Last Updated:** 2026-02-26
**Context:** PyBend schema-driven monolithic framework; evaluating architectural evolution paths

---

## Executive Summary

The microservices vs. monolith debate has matured significantly. The 2025-2026 industry consensus rejects binary thinking: **42% of organizations that initially adopted microservices have consolidated at least some services back into larger deployable units** ([CNCF Survey via byteiota](https://byteiota.com/modular-monolith-42-ditch-microservices-in-2026/)). Amazon Prime Video's Video Quality Analysis team achieved a **90% infrastructure cost reduction** by moving from distributed microservices to a single-process monolith ([Amazon Prime Video Case Study](https://dev.to/indika_wimalasuriya/amazon-prime-videos-90-cost-reduction-throuh-moving-to-monolithic-k4a)). Shopify processes **30TB of data per minute** with a modular monolith serving 32+ million requests per minute ([Shopify Engineering](https://shopify.engineering/shopify-monolith)).

The right architecture is not the one that sounds most modern. It is the one that matches your team's size, your domain's complexity, your operational maturity, and your actual scaling needs. This document provides a structured framework for making that decision.

---

## Table of Contents

1. [The Architecture Spectrum](#1-the-architecture-spectrum)
2. [Decision Criteria: The Five Dimensions](#2-decision-criteria-the-five-dimensions)
3. [Conway's Law and Team Structure](#3-conways-law-and-team-structure)
4. [When NOT to Microservice](#4-when-not-to-microservice)
5. [Cost Analysis](#5-cost-analysis)
6. [The Distributed Monolith Trap](#6-the-distributed-monolith-trap)
7. [Migration Strategies](#7-migration-strategies)
8. [Organizational Readiness Assessment](#8-organizational-readiness-assessment)
9. [Risk Analysis](#9-risk-analysis)
10. [Alternatives to Microservices](#10-alternatives-to-microservices)
11. [Decision Tree](#11-decision-tree)
12. [Success Metrics: DORA and Beyond](#12-success-metrics-dora-and-beyond)
13. [PyBend-Specific Guidance](#13-pybend-specific-guidance)
14. [Sources](#14-sources)

---

## 1. The Architecture Spectrum

Architecture is not a binary choice. It is a spectrum with five distinct waypoints, each suited to different organizational realities. Understanding where you are and where you need to be is the first step.

### 1.1 The Five Waypoints

```
Simple            Modular           Service-         Micro-           Serverless /
Monolith  --->    Monolith   --->   Oriented   --->  services  --->   Event-Driven
                                    Architecture
```

| Architecture | Deployment Unit | Data Ownership | Communication | Team Model | Best For |
|---|---|---|---|---|---|
| **Simple Monolith** | Single artifact | Shared DB | In-process calls | 1 team, 1-8 devs | MVPs, startups, prototypes |
| **Modular Monolith** | Single artifact, internal module boundaries | Shared DB with schema separation | In-process calls with enforced interfaces | 2-8 teams, 5-50 devs | Growing products, scaling teams |
| **SOA** | Several large services | DB per service (or shared with strict ownership) | Sync + async (ESB/API gateway) | Domain-aligned teams | Enterprise integration |
| **Microservices** | Many small, independent services | DB per service (strict) | Async-first, API contracts | Autonomous product teams, 50+ devs | High-scale, high-velocity orgs |
| **Serverless / Event-Driven** | Individual functions / event handlers | Event store + projections | Events, no direct calls | Small teams, ops-free mindset | Bursty workloads, glue logic |

### 1.2 Key Transitions

Each transition rightward adds:

- **Operational complexity**: More things to deploy, monitor, and debug
- **Network dependency**: In-process calls become network calls with latency and failure modes
- **Team autonomy**: Teams can ship independently
- **Infrastructure cost**: More compute, more tooling, more platform engineering

Each transition also removes:

- **Coordination overhead**: Teams stop blocking each other on deployments
- **Blast radius**: A failure in one service does not crash the whole system
- **Scaling constraints**: Individual components scale independently

**The mistake most teams make is jumping from simple monolith directly to microservices**, skipping the modular monolith stage entirely. This is like going from a bicycle to a Formula 1 car without learning to drive. The modular monolith is where 80% of organizations should land and stay for years ([ThoughtWorks Technology Radar](https://www.javacodegeeks.com/2025/12/microservices-vs-modular-monoliths-in-2025-when-each-approach-wins.html)).

### 1.3 Where PyBend Sits Today

PyBend is a schema-driven monolith with strong modular characteristics:

```
PyBend Architecture Classification:
  - Deployment: Single process (Uvicorn + FastAPI)
  - Storage: Single SQLite database
  - Communication: In-process function calls
  - Module boundaries: Model-driven (ProtoModel, StorableMixin, authorize package)
  - Classification: Simple Monolith trending toward Modular Monolith
```

PyBend's `authorize` package is already fully decoupled (zero PyBend imports). The storage layer is abstracted behind `AbstractStorage`. These are the hallmarks of a codebase that can evolve toward a modular monolith without a rewrite.

---

## 2. Decision Criteria: The Five Dimensions

### 2.1 Dimension Matrix

Evaluate your organization across five dimensions. Each dimension scores on a 1-5 scale. Total score guides architecture selection.

| Dimension | Score 1 (Stay Monolith) | Score 3 (Modular Monolith) | Score 5 (Consider Microservices) |
|---|---|---|---|
| **Team Size** | 1-5 developers | 10-25 developers | 50+ developers |
| **Deployment Frequency** | Weekly or less | Daily | Multiple times per day, per team |
| **Scaling Requirements** | Uniform load, single region | Moderate variation, predictable peaks | Hot-path components need 10x+ independent scaling |
| **Domain Complexity** | Single bounded context | 3-5 bounded contexts, some coupling | 10+ bounded contexts, clear domain separation |
| **Operational Maturity** | Manual deployments, basic monitoring | CI/CD pipeline, centralized logging | Platform team, automated canary deploys, distributed tracing |

### 2.2 Scoring Guide

| Total Score | Recommended Architecture | Rationale |
|---|---|---|
| **5-10** | Simple Monolith | Team overhead of distribution outweighs benefits |
| **11-17** | Modular Monolith | Structure needed but distribution premature |
| **18-21** | Extract 2-5 services from hot paths | Targeted decomposition where scaling demands it |
| **22-25** | Full microservices | Organization, domain, and ops maturity justify it |

### 2.3 Worked Example: A PyBend Application

Consider a PyBend e-commerce application:

```
Dimension Assessment:
  Team Size:              8 developers            -> Score: 2
  Deployment Frequency:   Twice per week          -> Score: 2
  Scaling Requirements:   Black Friday spike 3x   -> Score: 3
  Domain Complexity:      Products, Orders, Users  -> Score: 2
  Operational Maturity:   GitHub Actions CI, basic -> Score: 2

  Total: 11  ->  Recommendation: Modular Monolith
```

This team should invest in module boundaries within their monolith, not in Kubernetes clusters. The PyBend model-driven approach already provides natural boundaries (each model is its own domain entity with schema, routes, and access rules).

---

## 3. Conway's Law and Team Structure

### 3.1 The Law

> "Any organization that designs a system will produce a design whose structure is a copy of the organization's communication structure."
> -- Melvin Conway, 1967 ([Martin Fowler's bliki](https://martinfowler.com/bliki/ConwaysLaw.html))

This is not a suggestion. It is an empirical observation with decades of evidence. Your architecture will mirror your org chart whether you intend it to or not.

### 3.2 The Inverse Conway Maneuver

Smart organizations use this law deliberately: design team structure to produce the architecture you want ([IT Revolution](https://itrevolution.com/articles/conways-law-critical-for-efficient-team-design-in-tech/)).

| If You Want This Architecture... | Organize Teams Like This |
|---|---|
| Simple monolith | One cross-functional team owns everything |
| Modular monolith | Teams own modules (domains) but deploy together |
| Microservices | Autonomous teams own services end-to-end (build, run, support) |

### 3.3 Team Topologies Framework

The Team Topologies model (Skelton & Pais) defines four team types that map to service boundaries ([O'Reilly - Enabling Microservice Success](https://www.oreilly.com/library/view/enabling-microservice-success/9781098130787/ch04.html)):

| Team Type | Role | Architecture Mapping |
|---|---|---|
| **Stream-aligned** | Delivers business value for a domain | Owns one or more services / modules |
| **Platform** | Provides internal tooling and infrastructure | Owns the deployment platform, CI/CD, observability |
| **Enabling** | Helps stream-aligned teams adopt new practices | Temporary; coaches teams on new patterns |
| **Complicated-subsystem** | Owns deeply specialized domains (ML, crypto) | Owns services requiring rare expertise |

### 3.4 Service Boundary Heuristics

Services should align with **bounded contexts**, not technical layers. Use these heuristics:

```
Good service boundary:
  - Team can deploy independently
  - Team can make schema changes without coordinating
  - Service has its own data store
  - Service failure does not cascade to unrelated features
  - Domain language is distinct from neighboring services

Bad service boundary:
  - "Database service" (technical layer, not domain)
  - "Auth service" with 47 callers and synchronous dependencies
  - Two services that always deploy together
  - Service that requires another service to validate its own data
```

### 3.5 Conway's Law for PyBend Teams

A PyBend application maps models to teams naturally:

```
Team "Commerce":   Product, Order, Cart models
Team "Community":  Comment, Like, Review models
Team "Identity":   User model + authorize package

Each team owns their models, schemas, and access rules.
All deploy as one artifact (modular monolith).
If/when Team Commerce needs independent scaling, extract their
models into a separate PyBend instance with its own database.
```

---

## 4. When NOT to Microservice

This is the most important section in this document. The default answer should be "no" unless specific conditions force a "yes."

### 4.1 Do Not Adopt Microservices If

| Condition | Why Not |
|---|---|
| **Team < 10 developers** | Coordination costs exceed benefits. Each developer spends more time on infrastructure than features. Below 10 devs, monoliths outperform microservices on delivery speed ([AgileSoft Labs](https://www.agilesoftlabs.com/blog/2026/02/monolith-vs-microservices-decision)). |
| **Pre-product-market-fit** | Your domain model will change weekly. Refactoring across service boundaries is 10x harder than within a monolith. Keep boundaries soft until you know what you are building. |
| **Low traffic (< 1000 RPM)** | A single $50/month server handles this. Microservices infrastructure starts at $750/month for equivalent functionality. You are paying 15x more to solve a problem you do not have. |
| **Simple domain (1-3 bounded contexts)** | Distribution adds latency and failure modes without delivering organizational benefits. A well-structured monolith serves this domain better. |
| **No platform/DevOps team** | Microservices require: container orchestration, service discovery, distributed tracing, centralized logging, CI/CD per service. Without a platform team, developers build infrastructure instead of product. |
| **Tight deadline / proof of concept** | Microservices add 3-6 months of infrastructure setup before the first feature ships. Monoliths ship features on day one. |
| **Team lacks distributed systems experience** | Debugging network partitions, eventual consistency, and distributed transactions requires specialized knowledge. Without it, you build a distributed monolith (see Section 6). |

### 4.2 The "Premature Decomposition" Trap

Martin Fowler's advice remains canonical: **"Don't even consider microservices unless you have a system that's too complex to manage as a monolith."**

Common symptoms of premature decomposition:
- Services that share a database
- Services that must be deployed in lockstep
- Cross-service transactions for basic operations
- More than 30% of developer time spent on infrastructure
- Debugging a user request requires tracing across 5+ services

### 4.3 Real-World Reversals

| Company | What Happened | Result |
|---|---|---|
| **Amazon Prime Video** | Moved video quality analysis from Step Functions + microservices to single-process monolith | 90% cost reduction ([DEVCLASS](https://devclass.com/2023/05/05/reduce-costs-by-90-by-moving-from-microservices-to-monolith-amazon-internal-case-study-raises-eyebrows/)) |
| **Shopify** | Chose modular monolith over microservices for 2.8M LOC Ruby codebase | Handles 30TB/min, 32M+ req/min ([Shopify Engineering](https://shopify.engineering/shopify-monolith)) |
| **Segment** | Moved from microservices back to monolith | Reduced operational complexity, improved developer velocity |
| **Istio** | Consolidated its own microservices into a single binary ("Istiod") | Simpler operations, faster startup |

---

## 5. Cost Analysis

### 5.1 Infrastructure Cost Comparison

| Category | Monolith | Modular Monolith | Microservices (10 services) | Microservices (50 services) |
|---|---|---|---|---|
| **Compute** | $200/mo (1 server) | $200-400/mo (1-2 servers) | $500-1,000/mo | $2,500-5,000/mo |
| **Container orchestration** | N/A | N/A | $200-500/mo (managed K8s) | $500-2,000/mo |
| **Service mesh** | N/A | N/A | $200-400/mo compute overhead | $500-1,500/mo |
| **API gateway** | Included (framework) | Included (framework) | $100-300/mo | $200-500/mo |
| **Observability** | $50-100/mo (basic) | $50-100/mo (basic) | $300-800/mo (distributed tracing) | $1,000-3,000/mo |
| **CI/CD** | 1 pipeline | 1 pipeline | 10 pipelines | 50 pipelines |
| **Total infra** | **$250-300/mo** | **$250-500/mo** | **$1,300-3,000/mo** | **$4,700-12,000/mo** |
| **Multiplier vs. monolith** | 1x | 1-2x | **5-12x** | **19-48x** |

Sources: [Medium - Pawel Piwosz](https://medium.com/@pawel.piwosz/monolith-vs-microservices-2025-real-cloud-migration-costs-and-hidden-challenges-8b453a3c71ec), [Medium - Tushar Singla](https://medium.com/@tusharsingla024/the-hidden-costs-of-microservices-when-a-monolithic-architecture-is-the-smarter-choice-d5d360f190bb)

### 5.2 People Cost (Often Larger Than Infra)

| Role | Monolith | Modular Monolith | Microservices |
|---|---|---|---|
| **Platform engineering** | 0 FTE | 0-0.5 FTE | 1-3 FTE |
| **SRE / DevOps** | 0.5 FTE | 0.5-1 FTE | 2-5 FTE |
| **Per-developer overhead** | ~5% time on infra | ~10% time on infra | ~25-35% time on infra |

At $150K/yr per engineer, a 3-person platform team costs $450K/yr before they write a single product feature. For a 15-person engineering org, that is 20% of your engineering budget on infrastructure.

### 5.3 Enterprise-Scale Comparison

| Metric | Monolith (est.) | Microservices (est.) |
|---|---|---|
| Monthly infrastructure | $15,000 | $40,000-65,000 |
| Platform team cost (annual) | $0-150K | $450K-750K |
| Developer productivity overhead | 5-10% | 25-35% |
| Time to onboard new developer | 1-2 weeks | 3-6 weeks |
| Incident MTTR (no platform team) | 30 min - 2 hrs | 2-8 hrs |

Source: [Medium - Pawel Piwosz](https://medium.com/@pawel.piwosz/monolith-vs-microservices-2025-real-cloud-migration-costs-and-hidden-challenges-8b453a3c71ec)

### 5.4 Service Mesh Overhead

If you adopt microservices, a service mesh (Istio, Linkerd) becomes necessary for observability, mTLS, and traffic management. The overhead is non-trivial:

| Metric | Istio | Linkerd |
|---|---|---|
| **Memory per proxy** | ~100-150 MB | ~10 MB |
| **Latency overhead (mTLS)** | +166% | +33% |
| **Operational complexity** | High (extensive config) | Moderate (convention-based) |
| **Additional compute cost (100 pods)** | $300-500/mo | $200-300/mo |
| **Engineer time** | 0.5-1 FTE | 0.25-0.5 FTE |

Sources: [Buoyant - Linkerd vs Istio](https://www.buoyant.io/linkerd-vs-istio), [ArXiv - Performance Comparison](https://arxiv.org/html/2411.02267v1)

### 5.5 The Break-Even Question

Microservices become cost-effective when:
1. Independent scaling saves more in compute than the platform overhead costs
2. Deployment independence saves more in developer time than coordination overhead
3. Fault isolation prevents outages whose cost exceeds the observability investment

**For most teams under 50 engineers, this break-even point never arrives.**

---

## 6. The Distributed Monolith Trap

### 6.1 Definition

A distributed monolith is a system that has the operational complexity of microservices (network calls, independent deployments, distributed data) but retains the coupling of a monolith (services cannot be deployed independently, changes cascade, shared databases) ([Gremlin](https://www.gremlin.com/blog/is-your-microservice-a-distributed-monolith)).

It is the worst of both worlds: all the costs of distribution with none of the benefits.

### 6.2 Warning Signs

Score your system. Each "yes" adds one point:

| # | Warning Sign | Points |
|---|---|---|
| 1 | Changing one service requires deploying another service | +1 |
| 2 | Multiple services read/write the same database tables | +1 |
| 3 | Services communicate primarily via synchronous HTTP calls | +1 |
| 4 | A single user request traverses 5+ services | +1 |
| 5 | There is a "deployment order" that teams must follow | +1 |
| 6 | Service A cannot start without Service B being available | +1 |
| 7 | Integration tests require spinning up all services | +1 |
| 8 | A library/SDK is shared across services and versioned in lockstep | +1 |
| 9 | Cross-service debugging requires correlating logs from 4+ sources | +1 |
| 10 | Teams spend >30% of time on "glue code" between services | +1 |

**Scoring:**
- **0-2**: Healthy microservices
- **3-5**: Early warning; address coupling before it compounds
- **6-8**: Distributed monolith territory; consider consolidation
- **9-10**: Consolidate. You have a monolith with network latency.

### 6.3 How It Happens

```
Step 1: Team reads "microservices" blog post
Step 2: Team splits monolith into 12 services
Step 3: Services share the same database "temporarily"
Step 4: Services call each other synchronously for every operation
Step 5: Team realizes they must deploy all 12 services together
Step 6: Team builds an "orchestrator service" to coordinate
Step 7: The orchestrator becomes the new monolith
Step 8: Team now has a monolith + 12 satellite services + network latency
```

### 6.4 Prevention

| Principle | Practice |
|---|---|
| **Database per service** | Each service owns its data. No shared tables. Ever. |
| **Async by default** | Use events/messages for inter-service communication. Reserve sync calls for queries that need immediate responses. |
| **Independent deployability** | If you cannot deploy Service A without touching Service B, they are not separate services. Merge them. |
| **Consumer-driven contracts** | Define API contracts from the consumer's perspective. Test them independently. |
| **No shared libraries with business logic** | Shared libraries for utilities (logging, HTTP clients) are fine. Shared domain models are coupling. |

### 6.5 Recovery Patterns

If you are already in a distributed monolith:

1. **Identify coupling clusters**: Map which services always deploy together. These are candidates for consolidation.
2. **Merge the tightly coupled**: Combine services that share data or deploy in lockstep into a single service with internal modules.
3. **Introduce async boundaries**: Replace synchronous call chains with event-driven communication where possible.
4. **Extract cleanly**: Once merged, identify the real boundaries (by domain, not by technical layer) and extract again with proper data isolation.

---

## 7. Migration Strategies

### 7.1 Strategy Comparison

| Strategy | Risk | Duration | Effort | Best For |
|---|---|---|---|---|
| **Strangler Fig** | Low | 6-24 months | Incremental | Large monoliths, risk-averse orgs |
| **Branch by Abstraction** | Low-Medium | 3-12 months per component | Moderate | Deeply embedded functionality |
| **Parallel Run** | Low | 2-6 months per service | High (double compute) | Mission-critical, zero-downtime |
| **Big Bang Rewrite** | **Extreme** | 12-36 months | **Very High** | **Almost never** |

### 7.2 Strangler Fig Pattern (Recommended)

The Strangler Fig pattern incrementally replaces monolith functionality with new services, routing traffic between old and new implementations until the monolith is fully replaced ([Microsoft Azure Architecture Center](https://learn.microsoft.com/en-us/azure/architecture/patterns/strangler-fig), [AWS Prescriptive Guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/strangler-fig.html)).

```
Phase 1: Intercept                    Phase 2: Implement
┌─────────────┐                       ┌─────────────┐
│   Clients   │                       │   Clients   │
└──────┬──────┘                       └──────┬──────┘
       │                                     │
  ┌────▼────┐                           ┌────▼────┐
  │  Proxy  │ ── routes all ──>         │  Proxy  │ ── routes /orders ──> New Service
  └────┬────┘    to monolith            └────┬────┘
       │                                     │── routes everything else
  ┌────▼────┐                           ┌────▼────┐
  │Monolith │                           │Monolith │ (minus /orders)
  └─────────┘                           └─────────┘

Phase 3: Expand                       Phase 4: Complete
┌─────────────┐                       ┌──────────────┐
│   Clients   │                       │   Clients    │
└──────┬──────┘                       └──────┬───────┘
       │                                     │
  ┌────▼────┐                           ┌────▼─────┐
  │  Proxy  │                           │  Gateway │
  └────┬────┘                           └────┬─────┘
       │── /orders ──> Order Service         │── /orders   ──> Order Service
       │── /users  ──> User Service          │── /users    ──> User Service
       │── rest    ──> Monolith              │── /products ──> Product Service
  ┌────▼────┐                                │── /auth     ──> Auth Service
  │Monolith │ (shrinking)
  └─────────┘                           Monolith retired.
```

**Timeline estimates:**

| Monolith Size | Services to Extract | Estimated Duration | Team Size Needed |
|---|---|---|---|
| Small (< 50K LOC) | 2-3 | 3-6 months | 2-4 devs |
| Medium (50K-200K LOC) | 5-10 | 6-18 months | 4-8 devs |
| Large (200K+ LOC) | 10-20 | 12-36 months | 8-15 devs |

Source: Estimates synthesized from [Baeldung](https://www.baeldung.com/cs/microservices-strangler-pattern), [CircleCI](https://circleci.com/blog/monolith-to-microservices-migration-strategies/), [microservices.io](https://microservices.io/patterns/refactoring/strangler-application.html)

### 7.3 Branch by Abstraction

Use when functionality is deeply embedded and cannot be intercepted at the routing layer ([Martin Fowler](https://martinfowler.com/bliki/BranchByAbstraction.html)).

```
Step 1: Insert abstraction layer in front of target code
Step 2: Existing code calls abstraction (no behavior change)
Step 3: Build new implementation (microservice) behind the abstraction
Step 4: Abstraction routes to new implementation (feature flag)
Step 5: Validate equivalence
Step 6: Remove old implementation and abstraction layer
```

Best for: database access layers, authentication systems, notification engines.

### 7.4 Parallel Run

Both old and new implementations process every request. Responses from the new implementation are validated against the old but not returned to users until verified ([Simran Chawla](https://simranchawla.com/unlocking-legacy-systems-strangler-fig-branch-by-abstraction-and-parallel-run-explained/)).

```
┌──────────┐
│ Request  │
└────┬─────┘
     │
     ├──────────────> Monolith (primary) ──> Response to user
     │
     └──────────────> New Service (shadow) ──> Log + compare
                                                (discard response)
```

Best for: payment processing, financial calculations, any domain where correctness must be proven before cutover.

### 7.5 Big Bang Rewrite: Why Not

| Risk | Probability | Impact |
|---|---|---|
| Scope creep extends timeline 2-3x | Very High | Budget blown, team burned out |
| Business logic lost in translation | High | Subtle bugs in production |
| Zero value delivered until rewrite complete | Certain | Opportunity cost of 12-36 months |
| Original monolith diverges during rewrite | High | Two systems to maintain, neither complete |
| Project cancelled before completion | Moderate | Total investment lost |

The software industry has decades of evidence: big bang rewrites fail more often than they succeed. Use incremental strategies.

---

## 8. Organizational Readiness Assessment

### 8.1 DevOps Maturity Model

Before adopting microservices, assess your organization against this maturity model. Microservices require **Level 3 or higher** ([Atlassian DevOps Maturity Model](https://www.atlassian.com/solutions/devops/maturity-model), [Spacelift](https://spacelift.io/blog/devops-maturity-model)).

| Level | Name | Capabilities | Microservices Ready? |
|---|---|---|---|
| **1** | Initial | Manual deployments, no CI, ad-hoc monitoring | No |
| **2** | Managed | Basic CI/CD, centralized logging, some automation | No |
| **3** | Defined | Automated CI/CD per service, container orchestration, centralized metrics | **Minimum** |
| **4** | Measured | Distributed tracing, canary deployments, SLO-based alerting, DORA tracking | Yes |
| **5** | Optimized | Self-service platform, automated incident response, chaos engineering | Yes |

### 8.2 Readiness Checklist

Score each item 0 (absent), 1 (partial), or 2 (complete). Total of 16+ required for microservices.

| # | Capability | Score (0/1/2) |
|---|---|---|
| 1 | Automated CI/CD pipeline for every deployable unit | ___ |
| 2 | Container runtime in production (Docker, containerd) | ___ |
| 3 | Container orchestration (Kubernetes, ECS, Nomad) | ___ |
| 4 | Service discovery and load balancing | ___ |
| 5 | Centralized logging with search (ELK, Loki, Datadog) | ___ |
| 6 | Distributed tracing (Jaeger, Zipkin, OpenTelemetry) | ___ |
| 7 | Metrics and dashboards (Prometheus/Grafana, Datadog) | ___ |
| 8 | Automated alerting with on-call rotation | ___ |
| 9 | Feature flags / progressive rollout capability | ___ |
| 10 | Automated rollback on deployment failure | ___ |
| 11 | Infrastructure as code (Terraform, Pulumi, CDK) | ___ |
| 12 | Secrets management (Vault, AWS Secrets Manager) | ___ |

**Scoring:**
- **0-8**: Not ready. Invest in DevOps foundations first.
- **9-15**: Partially ready. Fill gaps before decomposing services.
- **16-20**: Ready for targeted service extraction.
- **21-24**: Ready for full microservices adoption.

### 8.3 CI/CD Requirements for Microservices

Microservices demand a fundamentally different CI/CD approach than monoliths ([CircleCI](https://circleci.com/blog/ci-cd-requirements-for-microservices/)):

| Concern | Monolith CI/CD | Microservices CI/CD |
|---|---|---|
| **Pipelines** | 1 | 1 per service (10-50+) |
| **Test strategy** | Unit + integration + E2E | Unit + contract + integration + E2E per service |
| **Build time** | 5-15 min (full build) | 2-5 min per service, but 10-50 parallel |
| **Deployment** | Deploy once | Deploy independently, with dependency awareness |
| **Rollback** | Rollback one artifact | Rollback one service without affecting others |
| **Environment management** | 1 staging env | Per-service staging or shared with namespace isolation |

### 8.4 On-Call Culture

Microservices require "you build it, you run it" ownership:

- Each team is on-call for their services
- Runbooks exist for every service
- Incident response involves tracing requests across service boundaries
- Post-incident reviews examine cross-service failure modes

If your organization does not have an established on-call culture, microservices will create alert fatigue and finger-pointing between teams. Build the culture before you build the architecture.

---

## 9. Risk Analysis

### 9.1 Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **Complexity explosion** | High | High | Start with 2-3 services, not 20. Extract incrementally. |
| **Network failures** | Certain (in time) | Medium-High | Circuit breakers, retries with backoff, bulkheads. Design for failure. |
| **Data consistency** | High | High | Saga pattern, eventual consistency acceptance. Avoid distributed transactions. |
| **Debugging difficulty** | Certain | Medium | Distributed tracing (OpenTelemetry), structured logging, correlation IDs. |
| **Deployment coordination** | Medium | Medium | Consumer-driven contracts, backward-compatible APIs, semantic versioning. |
| **Cascading failures** | Medium | Critical | Circuit breakers (Hystrix pattern), timeout policies, graceful degradation. |
| **Skill gap** | High (for most teams) | High | Training investment, hiring, or choosing simpler architecture. |
| **Vendor lock-in** | Medium | Medium | Use open standards (OCI containers, OpenTelemetry, CloudEvents). |
| **Cost overrun** | High | Medium | Budget 3-6x monolith infra cost. Track actual vs. projected monthly. |

### 9.2 The CAP Theorem in Practice

Microservices force you to confront distributed systems realities:

- **Network partitions will happen**. Services will become unreachable. Your system must handle this gracefully.
- **Consistency vs. availability**. You must choose: reject writes during partitions (consistent but unavailable) or accept writes and reconcile later (available but eventually consistent).
- **Distributed transactions are expensive**. Two-phase commit blocks resources and introduces coordinator failure as a single point of failure. The Saga pattern is the standard alternative but requires compensating transactions for rollback.

```
Monolith transaction:              Microservice saga:
BEGIN                              Order Service: Create order (PENDING)
  INSERT INTO orders ...              │
  UPDATE inventory ...                ▼
  INSERT INTO payments ...         Inventory Service: Reserve stock
COMMIT                                │ (if fails: compensate -> cancel order)
                                      ▼
(One DB, ACID guaranteed)          Payment Service: Charge card
                                      │ (if fails: compensate -> release stock,
                                      │                          cancel order)
                                      ▼
                                   Order Service: Confirm order (CONFIRMED)

                                   (3 services, eventual consistency,
                                    compensating transactions required)
```

### 9.3 Debugging Cost

| Scenario | Monolith | Microservices |
|---|---|---|
| Stack trace for a bug | Single process, full trace | Distributed across services, requires correlation |
| Reproducing a production issue | Run locally with same DB | Spin up 5-10 services + dependencies |
| Finding the root cause of latency | Profile one process | Trace request across service mesh, analyze each hop |
| Time to resolve P1 incident | 30 min - 2 hrs (typical) | 2-8 hrs (typical, without mature tooling) |

---

## 10. Alternatives to Microservices

Before committing to microservices, evaluate these alternatives that deliver many of the same benefits with less complexity.

### 10.1 Modular Monolith

**What it is:** A single deployable artifact with enforced internal module boundaries. Modules communicate through defined interfaces, not direct database access.

**How to implement in PyBend:**

```python
# PyBend's model-driven architecture naturally creates module boundaries.
# Each model is its own domain entity with:
#   - Schema (data contract)
#   - Routes (API surface)
#   - Access rules (authorization boundary)
#   - Storage operations (data layer)

# Enforce boundaries:
# 1. Models only reference other models through ListRef/Ref (no raw SQL joins)
# 2. The authorize package has zero PyBend imports (already decoupled)
# 3. Storage is behind AbstractStorage interface (swappable)
# 4. Each model defines its own __access__ rules (domain-level auth)
```

**Real-world proof:** Shopify's 2.8M-line Ruby monolith uses Rails Engines + Packwerk for module boundary enforcement. It processes 30TB/min and supports thousands of engineers ([Shopify Engineering](https://shopify.engineering/deconstructing-monolith-designing-software-maximizes-developer-productivity)).

**When to choose:** 5-50 developers, moderate domain complexity, single deployment acceptable.

### 10.2 Serverless Functions

**What it is:** Individual functions deployed to cloud providers (AWS Lambda, Google Cloud Functions, Cloudflare Workers). No server management. Pay per invocation.

**Best for:**
- Event-driven workloads (image processing, email sending, webhook handling)
- Bursty traffic patterns with long idle periods
- Glue logic between systems
- Extending a monolith with async capabilities

**Not suitable for:**
- Long-running processes (typical timeout: 15 min)
- Stateful applications
- High-throughput, low-latency requirements (cold starts add 100ms-2s)
- Complex domain logic requiring local state

**Hybrid approach:** Keep PyBend as the core application; offload specific tasks:
```
PyBend (monolith)
  ├── Core CRUD operations, schema serving, auth
  ├── Synchronous request handling
  └── Publishes events to queue
         │
         ├── Lambda: Generate PDF reports (async)
         ├── Lambda: Send notification emails (async)
         ├── Lambda: Process image uploads (async)
         └── Lambda: Webhook delivery (async)
```

### 10.3 Queue-Based Workers

**What it is:** Background job processors that consume work from a message queue. Deployed separately from the web application but often sharing the same codebase.

**Best for:**
- CPU-intensive tasks (report generation, data processing)
- Tasks that can tolerate seconds-to-minutes of delay
- Workloads that need independent scaling from the web tier

**Implementation pattern:**
```
Web tier (PyBend)  ──publish──>  Message Queue  ──consume──>  Worker Process
                                (Redis, RabbitMQ,             (same codebase,
                                 SQS)                          different entry point)
```

This gives you independent scaling of web and worker tiers without the complexity of service boundaries, API contracts, or distributed data.

### 10.4 Edge Workers

**What it is:** Code running at CDN edge locations (Cloudflare Workers, Deno Deploy, Vercel Edge Functions).

**Best for:**
- Request routing and transformation
- Authentication and rate limiting at the edge
- Serving personalized content without origin roundtrips
- A/B testing and feature flags

**Not suitable for:** Database-heavy operations, complex business logic, stateful processing.

### 10.5 Alternative Comparison

| Alternative | Operational Complexity | Independent Scaling | Data Isolation | Team Autonomy | Cost |
|---|---|---|---|---|---|
| Modular Monolith | Low | No (scale whole app) | No (shared DB) | Medium (module ownership) | Low |
| Serverless Functions | Low (managed) | Yes (per function) | Yes (if separate DB) | Medium | Variable (pay-per-use) |
| Queue Workers | Low-Medium | Yes (web vs. worker) | No (shared DB) | Low-Medium | Low-Medium |
| Edge Workers | Low (managed) | Yes (per region) | N/A (stateless) | Medium | Low |
| Microservices | **High** | Yes (per service) | Yes (DB per service) | High | **High** |

---

## 11. Decision Tree

Use this flowchart to determine your recommended architecture. Start at the top.

```
START
  │
  ▼
[Team size > 50 developers?]
  │
  ├── YES ──> [Domain has 10+ distinct bounded contexts?]
  │             │
  │             ├── YES ──> [DevOps maturity Level 3+?]
  │             │             │
  │             │             ├── YES ──> MICROSERVICES
  │             │             │           (with platform team)
  │             │             │
  │             │             └── NO ───> MODULAR MONOLITH
  │             │                         + invest in DevOps maturity
  │             │                         + revisit in 6 months
  │             │
  │             └── NO ───> MODULAR MONOLITH
  │                         (team size alone does not justify microservices)
  │
  └── NO
       │
       ▼
  [Team size 10-50?]
       │
       ├── YES ──> [Specific component needs 10x independent scaling?]
       │             │
       │             ├── YES ──> MODULAR MONOLITH
       │             │           + extract 1-3 hot-path services
       │             │           (hybrid approach)
       │             │
       │             └── NO ───> MODULAR MONOLITH
       │                         (enforce module boundaries, single deploy)
       │
       └── NO (team < 10)
            │
            ▼
       [Pre-product-market-fit?]
            │
            ├── YES ──> SIMPLE MONOLITH
            │           (maximize iteration speed)
            │
            └── NO ───> [Traffic > 10K RPM with hot paths?]
                          │
                          ├── YES ──> MONOLITH + QUEUE WORKERS
                          │           (offload async work)
                          │
                          └── NO ───> SIMPLE MONOLITH
                                      (revisit when team grows)
```

### 11.1 Decision Summary Table

| Your Situation | Recommended Architecture | Next Step |
|---|---|---|
| Startup, 1-5 devs, finding PMF | Simple monolith (PyBend default) | Ship features, validate market |
| Growing startup, 5-15 devs, product validated | Modular monolith | Enforce module boundaries, add CI/CD |
| Scale-up, 15-50 devs, multiple domains | Modular monolith + 1-3 extracted services | Extract only what must scale independently |
| Enterprise, 50+ devs, complex domain | Microservices (with platform team) | Invest in platform, observability, contracts |
| High-traffic but simple domain | Monolith + queue workers + CDN | Scale vertically first, add workers for async |
| Event-driven / bursty workloads | Monolith + serverless functions | Keep core logic centralized, offload events |

---

## 12. Success Metrics: DORA and Beyond

### 12.1 The Four DORA Metrics

The DORA (DevOps Research and Assessment) framework provides the industry-standard metrics for measuring software delivery performance ([DORA](https://dora.dev/guides/dora-metrics/), [Atlassian](https://www.atlassian.com/devops/frameworks/dora-metrics)).

| Metric | Elite | High | Medium | Low |
|---|---|---|---|---|
| **Deployment Frequency** | On-demand (multiple/day) | Weekly-monthly | Monthly-biannually | Less than once/6 months |
| **Lead Time for Changes** | < 1 hour | 1 day - 1 week | 1 week - 1 month | 1-6 months |
| **Change Failure Rate** | 0-5% | 5-10% | 10-15% | 16-30%+ |
| **Time to Restore (MTTR)** | < 1 hour | < 1 day | 1 day - 1 week | 1 week - 1 month |

**Key insight from DORA research:** Elite performers are **2x more likely to exceed organizational goals** in profitability, productivity, and customer satisfaction ([Google Cloud](https://cloud.google.com/blog/products/devops-sre/using-the-four-keys-to-measure-your-devops-performance)).

### 12.2 Measuring Architecture Effectiveness

DORA metrics should improve after an architecture change. If they do not, the change has not delivered value.

**Before microservices migration, baseline:**
- Current deployment frequency per team
- Current lead time from commit to production
- Current change failure rate
- Current MTTR

**After migration, track:**

| Signal | Healthy | Warning | Failure |
|---|---|---|---|
| Deployment frequency | Increased per team | Unchanged | Decreased (deploy coordination) |
| Lead time | Decreased | Unchanged | Increased (cross-service testing) |
| Change failure rate | Decreased or stable | Slight increase during transition | Significant increase |
| MTTR | Decreased (fault isolation) | Unchanged | Increased (distributed debugging) |
| Developer satisfaction | Increased (autonomy) | Neutral | Decreased (infrastructure burden) |
| Infrastructure cost | Justified by business value | Growing but tracked | Spiraling without clear benefit |

### 12.3 Anti-Metrics (Vanity Signals)

Do not use these to justify microservices:

| Anti-Metric | Why It Misleads |
|---|---|
| "Number of services deployed" | More services is not better. Fewer, well-bounded services is better. |
| "Lines of code per service" | Small services can be under-bounded (nano-services), causing more harm than good. |
| "We use Kubernetes" | Kubernetes is infrastructure, not architecture. You can run a monolith on K8s. |
| "Our tech stack is modern" | Modern tools with bad architecture produce bad results faster. |

### 12.4 The AI Productivity Paradox

The DORA Report 2025 found that AI coding assistants increase individual output (21% more tasks, 98% more PRs merged) but **organizational delivery metrics remain flat** ([Faros AI - DORA Report 2025 Takeaways](https://www.faros.ai/blog/key-takeaways-from-the-dora-report-2025)). This means:

- AI makes developers faster at writing code
- The bottleneck shifts to review, integration, testing, and deployment
- Architecture decisions (monolith vs. microservices) affect the bottleneck location
- Microservices with immature CI/CD create new bottlenecks that AI cannot solve

---

## 13. PyBend-Specific Guidance

### 13.1 PyBend's Natural Architecture Evolution

PyBend's schema-driven, model-centric design creates a natural evolution path:

```
Stage 1: Single PyBend Instance (Today)
  - One create_app() call
  - One SQLite database
  - All models in one process
  - Perfect for: MVP, small teams, simple domains

Stage 2: Modular PyBend (6-18 months)
  - Same deployment, enforced module boundaries
  - Replace SQLite with PostgreSQL for concurrent access
  - Separate concerns: authorize (already standalone), storage, API
  - Multiple __access__ rule sets per domain
  - Perfect for: Growing teams, multiple domain areas

Stage 3: PyBend Service Extraction (18+ months)
  - Extract hot-path models into separate PyBend instances
  - Each instance: own create_app(), own database, own deployment
  - Shared schema contract (JSON Schema is the API)
  - API Gateway routes to correct PyBend instance
  - Perfect for: Independent scaling of specific domains

Stage 4: Full Service Architecture (Only if needed)
  - Multiple PyBend instances + non-PyBend services
  - Event-driven communication between services
  - Service mesh for observability
  - Platform team required
  - Perfect for: Large teams, complex domains, proven scaling needs
```

### 13.2 What PyBend Gets Right for Modularity

| Feature | How It Helps |
|---|---|
| Schema as contract | JSON Schema already defines the API contract. If you extract a model into a separate service, the schema does not change. Frontend does not know the difference. |
| `AbstractStorage` interface | Swap SQLite for PostgreSQL or a remote storage adapter without changing model code. |
| `authorize` package (zero imports) | Auth is already a standalone module. It can become a separate service with no code changes. |
| Model-driven routes | `register_routes()` generates API endpoints from models. Two PyBend instances with different models produce different, non-overlapping routes. |
| `@expose_route` with `access=` | Custom methods carry their own authorization. When extracted to a service, the access rules move with the method. |

### 13.3 What to Invest In Now (Regardless of Future Architecture)

Whether you eventually adopt microservices or stay monolithic, these investments pay off:

1. **Replace SQLite with PostgreSQL** for any production workload. SQLite does not support concurrent writes, which limits horizontal scaling.
2. **Enforce module boundaries** via Python package structure. Models that reference each other should be in the same package. Models that do not should be in separate packages.
3. **Add structured logging** with correlation IDs. This makes debugging easier in monoliths and is essential for microservices.
4. **Implement health checks and metrics**. A `/health` endpoint and Prometheus-compatible metrics are useful at any scale.
5. **Containerize** with Docker. Whether you deploy one container or twenty, containerization is the foundation.

### 13.4 Extraction Playbook: Moving a Model to Its Own Service

When the time comes to extract a PyBend model into a separate service:

```
Step 1: Identify the model to extract (e.g., Product)
Step 2: Create a new PyBend instance:
          app = create_app(models=[Product], storage="postgres://...")
Step 3: Migrate Product data to the new database
Step 4: Update API Gateway to route /products/* to the new instance
Step 5: Replace ListRef[Product] in other models with href references
Step 6: Frontend continues to work (schema contract unchanged)
Step 7: Monitor DORA metrics for 2-4 weeks
Step 8: If metrics improve, proceed. If not, consolidate back.
```

The key advantage of PyBend's architecture: the JSON Schema contract is the same whether the model lives in the monolith or in its own service. The frontend fetches the schema, creates DynamicClasses, and renders. It does not care where the schema came from.

---

## 14. Sources

### Primary References

1. [Microservices vs Monolith: The 2025 Decision Framework](https://kodekx-solutions.medium.com/microservices-vs-monolith-decision-framework-for-2025-b19570930cf7) - KodeKx Solutions, Medium
2. [Monolith vs Microservices Decision Framework 2026](https://www.agilesoftlabs.com/blog/2026/02/monolith-vs-microservices-decision) - AgileSoft Labs
3. [Modular Monolith: 42% Ditch Microservices in 2026](https://byteiota.com/modular-monolith-42-ditch-microservices-in-2026/) - ByteIota
4. [Microservices vs. Modular Monoliths in 2025: When Each Approach Wins](https://www.javacodegeeks.com/2025/12/microservices-vs-modular-monoliths-in-2025-when-each-approach-wins.html) - Java Code Geeks

### Cost and Infrastructure

5. [Monolith vs Microservices 2025: Real Cloud Migration Costs](https://medium.com/@pawel.piwosz/monolith-vs-microservices-2025-real-cloud-migration-costs-and-hidden-challenges-8b453a3c71ec) - Pawel Piwosz, Medium
6. [The Hidden Costs of Microservices](https://medium.com/@tusharsingla024/the-hidden-costs-of-microservices-when-a-monolithic-architecture-is-the-smarter-choice-d5d360f190bb) - Tushar Singla, Medium
7. [Linkerd vs Istio: Service Mesh Comparison](https://www.buoyant.io/linkerd-vs-istio) - Buoyant

### Case Studies

8. [Amazon Prime Video 90% Cost Reduction](https://dev.to/indika_wimalasuriya/amazon-prime-videos-90-cost-reduction-throuh-moving-to-monolithic-k4a) - DEV Community
9. [Shopify Monolith Architecture](https://shopify.engineering/shopify-monolith) - Shopify Engineering
10. [Deconstructing the Monolith - Shopify](https://shopify.engineering/deconstructing-monolith-designing-software-maximizes-developer-productivity) - Shopify Engineering
11. [Inside Shopify's Modular Monolith](https://newsletter.techworld-with-milan.com/p/inside-shopifys-modular-monolith) - Tech World with Milan

### Migration Patterns

12. [Strangler Fig Pattern - Azure Architecture Center](https://learn.microsoft.com/en-us/azure/architecture/patterns/strangler-fig) - Microsoft
13. [Strangler Fig Pattern - AWS Prescriptive Guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/strangler-fig.html) - Amazon Web Services
14. [Branch by Abstraction](https://martinfowler.com/bliki/BranchByAbstraction.html) - Martin Fowler
15. [Monolith to Microservices Migration Strategies](https://circleci.com/blog/monolith-to-microservices-migration-strategies/) - CircleCI

### Distributed Monolith and Anti-Patterns

16. [Is Your Microservice a Distributed Monolith?](https://www.gremlin.com/blog/is-your-microservice-a-distributed-monolith) - Gremlin
17. [10 Microservices Anti-Patterns](https://dzone.com/articles/10-microservices-anti-patterns-you-need-to-avoid) - DZone
18. [Microservices Antipattern: The Distributed Monolith](https://mehmetozkaya.medium.com/microservices-antipattern-the-distributed-monolith-%EF%B8%8F-46d12281b3c2) - Mehmet Ozkaya, Medium

### DORA Metrics and Measurement

19. [DORA Metrics Guide](https://dora.dev/guides/dora-metrics/) - DORA (Google)
20. [DORA Metrics - Atlassian](https://www.atlassian.com/devops/frameworks/dora-metrics) - Atlassian
21. [DORA Report 2025 Key Takeaways](https://www.faros.ai/blog/key-takeaways-from-the-dora-report-2025) - Faros AI
22. [Four Keys Metrics - Google Cloud](https://cloud.google.com/blog/products/devops-sre/using-the-four-keys-to-measure-your-devops-performance) - Google Cloud

### Organizational Design

23. [Conway's Law](https://martinfowler.com/bliki/ConwaysLaw.html) - Martin Fowler
24. [Conway's Law and Team Boundaries](https://datascienceleadership.com/docs/technical-leadership/conway-law-team-boundaries) - Data Science Leadership
25. [Conway's Law: Critical for Efficient Team Design](https://itrevolution.com/articles/conways-law-critical-for-efficient-team-design-in-tech/) - IT Revolution
26. [Enabling Microservice Success - Ch. 4: Conway's Law](https://www.oreilly.com/library/view/enabling-microservice-success/9781098130787/ch04.html) - O'Reilly

### DevOps Maturity and Readiness

27. [DevOps Maturity Model - Atlassian](https://www.atlassian.com/solutions/devops/maturity-model) - Atlassian
28. [DevOps Maturity Model Explained](https://spacelift.io/blog/devops-maturity-model) - Spacelift
29. [Microservices Assessment and Readiness - Azure](https://learn.microsoft.com/en-us/azure/architecture/guide/technology-choices/microservices-assessment) - Microsoft
30. [CI/CD Requirements for Microservices](https://circleci.com/blog/ci-cd-requirements-for-microservices/) - CircleCI

---

*This document is part of the PyBend research series on architecture decisions. It should be revisited quarterly as team size, traffic patterns, and operational maturity evolve.*
