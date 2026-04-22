# :clipboard: Integrating a CDN Capability to N3TX Agents: Strategic Analysis Report

## For: CEO & Engineering Team
## Date: 2026-03-20
## Prepared by: Architecture Team

> *For the standalone executive summary, see [CDN-Agents-summary.md](../../vision/CDN-Agents-summary.md).*

---

### How to Read This Document

| Time | Path | What you'll get |
|------|------|-----------------|
| **5 min** | Executive Summary (Section 0) | The answer, the numbers, the recommendation |
| **15 min** | + Sections 1-2 | What CDN-for-agents means, who's doing it, what works |
| **30 min** | + Sections 3-5 | Technical architecture, our gaps, cost-benefit math |
| **45 min** | Full document | Decision framework, risk register, implementation details |

---

## :clipboard: Executive Summary

> :bulb: **Key Finding:** The highest-ROI CDN integration for N3TX agents is **not** moving inference to the edge -- it is moving *decisions about inference* to the edge. A CDN-layer gateway that caches schemas, routes requests, and semantically caches agent responses can **cut LLM costs by 50-73%** before deploying a single GPU at an edge location.

### The Core Question

Should N3TX integrate CDN capabilities into its agent system, and if so, how and when?

### The Short Answer

**Yes, but in three carefully sequenced phases.** Phase 1 (CDN for schemas + AI Gateway) is worth doing *today* -- it requires roughly 2 weeks of engineering time, costs $0-15/month, and delivers immediate global performance gains with a 99% schema cache hit rate. Phase 2 (semantic caching) is worth doing when LLM spend exceeds $500/month. Phase 3 (edge agents) is worth doing only when you have measured proof that latency -- not cost -- is the bottleneck.

### Key Findings at a Glance

| # | Finding | Implication for N3TX |
|---|---------|---------------------|
| 1 | Edge AI market projected at **$29.98B in 2026**, growing 21-30% CAGR | The market tailwind is real, but 68% of edge AI pilots fail to scale |
| 2 | Semantic caching achieves **68.8% hit rate** with <1% false positives at 0.8 threshold | Single highest-ROI optimization for any LLM-heavy system |
| 3 | Cloudflare's Durable Objects implement the **Actor Model** with built-in SQLite | Architecturally near-identical to N3TX's ActorModel + SQLite pattern |
| 4 | N3TX already has **4 NetworkAdapters** (HTTP, WS, MCP, AP) -- a 5th edge adapter fits with zero architectural changes | The adapter pattern was built for exactly this kind of extension |
| 5 | Schema endpoints are **inherently CDN-friendly**: immutable per deploy, self-describing, publicly accessible | Schema caching is a no-brainer: free, simple, eliminates the #1 API call |
| 6 | Agentic workloads see **up to 75% energy savings** from hybrid edge-cloud vs traditional inference | Agents benefit more from edge proximity than regular inference workloads |
| 7 | N3TX's two-tier auth **already implements** the edge/origin split pattern | JWT validation at edge (Tier 1), OWNER checks at origin (Tier 2) -- no redesign needed |

### Recommendation

**Phase 1 now. Phase 2 when LLM costs cross $500/month. Phase 3 only with measured latency evidence.** Do not skip phases. Each phase provides the observability data needed to justify the next.

---

## 1. :mag: What Is CDN-for-Agents? (And Why It Matters Now)

> :bulb: **Key Finding:** CDN-for-agents is not the same as "CDN for web pages." It is a three-layer strategy: caching static metadata at the edge, intelligently routing agent requests, and (eventually) running lightweight inference at edge locations. The layers are independent and can be adopted incrementally.

### The Plain-English Version

A CDN (Content Delivery Network) is a global network of servers that caches content closer to users. Traditionally, CDNs cache images, CSS, and HTML. The new frontier is using CDN infrastructure for AI workloads -- not to run full LLM inference at every edge location, but to **intercept, classify, cache, and route** agent requests so that fewer of them need the expensive round-trip to your central server and LLM API.

Think of it as a smart receptionist: instead of routing every visitor directly to the CEO, the receptionist handles the obvious questions, directs people to the right department, and only escalates the truly complex cases. The CDN edge plays the same role for your agents.

### The Technical Picture

CDN-agent integration operates at three distinct layers, each with different complexity and payoff:

```
Layer 3: Edge Inference          [High complexity, high reward, future]
  Run small LLMs at CDN edge for classification, FAQ, simple queries
  Requires: GPU at edge, model management, distributed state
                        |
Layer 2: Semantic Caching        [Medium complexity, highest ROI]
  Cache agent responses by semantic similarity (not just exact match)
  Requires: Embedding model, vector store, similarity matching
                        |
Layer 1: Schema + Response CDN   [Low complexity, immediate value]
  Cache schemas, public reads, and exact-match agent responses
  Requires: Cache-Control headers, CDN in front of origin
```

### Why Now?

Three forces converging make this timely for N3TX:

1. **The market is moving fast.** The edge AI market is projected to reach $29.98 billion in 2026, growing at 21-30% CAGR depending on the research firm ([Grand View Research](https://www.grandviewresearch.com/industry-analysis/edge-ai-market-report), [Fortune Business Insights](https://www.fortunebusinessinsights.com/edge-ai-market-107023)). Gartner predicts 40% of enterprise applications will feature task-specific AI agents by 2026 ([Gartner](https://www.gartner.com/en/newsroom/press-releases/2025-08-26-gartner-predicts-40-percent-of-enterprise-apps-will-feature-task-specific-ai-agents-by-2026-up-from-less-than-5-percent-in-2025)).

2. **LLM costs compound fast.** A single N3TX `agentic()` call can involve 5-30 LLM API calls, each costing $0.01-$0.10. At 50,000 agent requests/month, that is $900/month in LLM spend alone. At 500,000 requests/month, it is $9,000/month. Caching eliminates the most repetitive fraction of these calls.

3. **N3TX's architecture is already built for this.** The NetworkAdapter pattern, schema pipeline, TX message envelopes, and two-tier auth were designed for protocol-agnostic distribution. Adding CDN capability is less about bolting on a cache layer and more about treating the edge as another adapter in the existing chain (see [02-our-stack-relevance.md](02-our-stack-relevance.md)).

### Market Size Context

| Source | 2025 Estimate | 2026 Estimate | 2033-2034 Projection | CAGR |
|--------|--------------|--------------|---------------------|------|
| [Grand View Research](https://www.grandviewresearch.com/industry-analysis/edge-ai-market-report) | $24.91B | $29.98B | $118.69B (2033) | 21.7% |
| [Fortune Business Insights](https://www.fortunebusinessinsights.com/edge-ai-market-107023) | $35.81B | $47.59B | $385.89B (2034) | 29.9% |
| [Precedence Research](https://www.precedenceresearch.com/edge-ai-market) | -- | -- | $143.06B (2034) | 23.8% |
| [Market.us](https://market.us/report/edge-ai-market/) | $23.3B | $28.8B | $196.6B (2034) | 23.8% |

The variance (from $118B to $386B for 2033-2034) reflects different scoping definitions, but the directional signal is unambiguous: **this market is doubling every 3-4 years**. The question is not "will edge AI matter?" but "which layer of the edge stack should N3TX invest in?" (see [01-industry-and-decisions.md](01-industry-and-decisions.md)).

---

## 2. :office: Industry Landscape

> :bulb: **Key Finding:** Cloudflare has the most complete edge-agent story today, and its Durable Objects + Actor Model pattern is architecturally near-identical to N3TX's ActorModel. AWS is the enterprise play. Akamai is betting big on distributed GPUs but is still in early access. Vercel and Fastly provide edge compute but no native AI inference.

### Provider Comparison

| Provider | Edge AI Product | GPU at Edge? | Agent SDK? | Pricing Model | Maturity |
|----------|----------------|-------------|-----------|---------------|----------|
| **Cloudflare** | Workers AI + Agents SDK | Yes (Infire engine) | Yes (Durable Objects + MCP) | $0.011/1K Neurons | Production |
| **AWS** | Lambda@Edge + Bedrock | No native edge GPU | Bedrock AgentCore | Per-vCPU-second + per-token | Production |
| **Akamai** | Inference Cloud + EdgeWorkers | Yes (NVIDIA Blackwell) | No native SDK | Not yet public | Early access |
| **Vercel** | Edge Functions | No GPU | No agent SDK | $5/hr active CPU (Pro) | Production (no AI) |
| **Fastly** | Compute (Wasm) | No GPU | No agent SDK | Request-based | Production (no AI) |

### Success Stories with Measured Outcomes

**Baselime: 83% cost reduction** migrating from AWS to Cloudflare. The primary cost driver on AWS was I/O operations -- Lambda functions spent over 70% of wall time on I/O but were billed for full wall-clock time. Cloudflare's activity-based billing eliminated this waste. Daily compute cost fell from $650 to $25 ([Cloudflare blog](https://blog.cloudflare.com/80-percent-lower-cloud-cost-how-baselime-moved-from-aws-to-cloudflare/)).

**Cloudflare internal security agent: 77% savings.** Processing 7 billion tokens/day, projected annual cost dropped from $2.4M (proprietary model) to ~$552K using Kimi K2.5 on Workers AI. Key insight: for high-volume, quality-tolerant workloads, open-source models at the edge beat proprietary models centralized ([Cloudflare blog](https://blog.cloudflare.com/workers-ai-large-models/)).

**Hybrid edge-cloud research: 75% energy savings** for agentic workloads. Agentic workloads benefit more from hybrid edge-cloud than traditional inference because agents involve many sequential I/O-heavy steps (tool calls, DB queries, API requests) that benefit from edge proximity ([arxiv](https://arxiv.org/html/2501.14823v2)).

### Failure Stories and Lessons

**68% of industrial AI pilots fail to scale** -- most because of non-replicable data pipelines and unclear ROI baselines ([Edge IR](https://www.edgeir.com/why-edge-architectures-fail-and-how-to-design-around-it-20260316)). Only 34% of organizations have production edge AI systems with real-time data streaming; 66% are still in pilot/POC ([Computer Weekly](https://www.computerweekly.com/feature/Edge-AI-Whats-working-and-what-isnt)).

The most common failure pattern is not technical -- it is organizational. Teams deploy edge AI because it is exciting, not because they have measured a latency problem. The lesson: **always start with the question "What specific user experience or cost problem does edge solve?" If you cannot answer with a number, you are not ready.**

### Cloudflare: The Natural Mapping to N3TX

Cloudflare's architecture deserves particular attention because its primitives map almost 1:1 to N3TX concepts:

| Cloudflare Concept | N3TX Equivalent | Mapping Quality |
|---|---|---|
| Durable Objects (stateful, message-based) | ActorModel (stateful, TX-message-based) | Near-identical |
| Workers (request router) | Matrix (root actor, message router) | Same dispatch pattern |
| RPC messages | TX message envelopes | Both are routable, typed envelopes |
| MCP tool definitions | `@expose_route` method signatures | Both expose typed callables |
| Durable Object SQLite | StorableMixin + SQLiteStorage | Same storage model |

This is not coincidence -- both systems solve the same problem: stateful, message-driven compute with typed interfaces. The alignment means an N3TX-to-Cloudflare-edge adapter would involve translation, not reinvention (see [02-our-stack-relevance.md](02-our-stack-relevance.md)).

### Cloudflare Deep Dive: The Technical Details

Cloudflare has the most complete edge-agent story today:

- **Infire** is a proprietary Rust-based inference engine: up to 7% faster than vLLM 0.10.0 with ~82% lower CPU usage ([Cloudflare blog](https://blog.cloudflare.com/cloudflares-most-efficient-ai-inference-engine/))
- **Durable Objects** implement the Actor Model -- each agent runs as a stateful micro-server with its own SQLite database, WebSocket connections, and scheduling ([Cloudflare Agents docs](https://developers.cloudflare.com/agents/))
- **AI Gateway** provides caching, rate limiting, and observability across 20+ AI providers, reducing latency by up to 90% for cached responses ([Cloudflare AI Gateway](https://developers.cloudflare.com/ai-gateway/))
- **99.99% warm request rate** through "Shard and Conquer" consistent hashing, reducing cold starts by 10x ([dev.to analysis](https://dev.to/onepoint/architecting-agentic-systems-at-the-edge-a-technical-strategic-analysis-of-the-cloudflare-3761))
- Now supports large models up to 70B parameters (Kimi K2.5) with 256K context windows on edge GPUs ([Cloudflare blog](https://blog.cloudflare.com/workers-ai-large-models/))
- MCP server support built into the Agents SDK -- agents expose tools via the Model Context Protocol standard ([Cloudflare MCP docs](https://developers.cloudflare.com/agents/model-context-protocol/))

**Pricing:** $0.011 per 1,000 Neurons. Free tier of 10,000 Neurons/day. Embeddings are nearly free; text generation costs scale with model size ([Cloudflare pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/)).

### AWS: The Enterprise Alternative

AWS distributes AI capabilities across a three-tier model:

```
[Device Edge]           [Network Edge]           [Cloud Core]
 IoT Greengrass          Lambda@Edge              Bedrock + SageMaker
 On-device inference     CDN-layer logic           Heavy inference
 Offline-capable         Content personalization   Agent orchestration
```

Lambda@Edge runs at CloudFront edge locations but has no native GPU access. Bedrock AgentCore uses consumption-based pricing: CPU at ~$0.0895/3600 per vCPU, memory at ~$0.00945/3600 per GB ([AWS Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/pricing/)). Agents typically spend 30-70% of time in I/O wait, making active-CPU billing advantageous. Best for organizations already deep in the AWS ecosystem that need compliance-grade audit trails.

---

## 3. :zap: Technical Architecture Overview

> :bulb: **Key Finding:** Four architecture patterns exist for CDN-agent integration, ordered by complexity. The first two (AI Gateway and edge classification) deliver 80%+ of the value at 20% of the effort. The last two (schema propagation and full edge agents) are powerful but premature for N3TX's current stage.

### The Four Patterns

```
Pattern 1: CDN as AI Gateway             Pattern 2: Edge Classification
[Client] --> [CDN Edge]                   [Client] --> [Edge Classifier]
                 |                                          |
           [Rate Limit]                              [Simple?] ---- Yes --> [Cache/Static]
           [Cache Check]                                    |
           [Observability]                             No (complex)
                 |                                          |
           [cache miss]                              [Origin Agent]
                 |
           [Origin LLM]

Pattern 3: Schema + Tool Propagation      Pattern 4: Full Edge Agent
[Origin] ---publish schemas---> [CDN Edge] [CDN Edge (Durable Object)]
                                    |           |
                              [GET /Product]    +-- Agent State (SQLite)
                              [tool specs]      +-- Tool Definitions
                              [MCP tools/list]  +-- LLM Inference
                                    |           +-- Scheduled Tasks
                              [Clients fetch    +-- WebSocket
                               from nearest     |
                               edge node]       [Autonomous Agent at Edge]
```

### Pattern 1: CDN as AI Gateway (Highest ROI, Lowest Effort)

The simplest integration. Place a CDN-layer gateway between your application and LLM providers. Cloudflare AI Gateway does exactly this and supports 20+ providers ([Cloudflare AI Gateway](https://developers.cloudflare.com/ai-gateway/)).

**What it buys you:** exact-match caching (identical prompts return cached responses instantly), rate limiting against runaway agent loops, fallback routing between LLM providers, and unified observability across all LLM calls.

**Measured results:** AI Gateway caching reduces latency by up to 90% for cached responses ([Cloudflare AI Gateway](https://developers.cloudflare.com/ai-gateway/)). An analysis of 100,000 production queries found 18% were exact duplicates ([Helicone](https://www.helicone.ai/blog/effective-llm-caching)). Combined with semantic caching, 50-70% of LLM API calls can be eliminated entirely.

### Pattern 2: Edge-Side Classification + Central Inference

Run a small, fast model at the edge to classify and route requests. Only queries that need full agent reasoning get sent to the central server.

**Real-world numbers:** In enterprise support bots, 40-60% of queries are repetitive or highly similar ([VentureBeat](https://venturebeat.com/orchestration/why-your-llm-bill-is-exploding-and-how-semantic-caching-can-cut-it-by-73)). A lightweight classifier (e.g., fine-tuned DistilBERT) routes these at <8ms per decision ([PMC study](https://pmc.ncbi.nlm.nih.gov/articles/PMC9415810/)).

### Caching: The Three Tiers

This is the highest-ROI area for N3TX. Caching agent responses properly can cut LLM costs by 50-73% with relatively low implementation effort.

| Tier | Mechanism | Hit Rate | Latency | Best For |
|------|-----------|----------|---------|----------|
| **Exact-match** | Hash(prompt) -> response | ~18% in production | <1ms | Identical repeated queries |
| **Semantic** | Embedding similarity > 0.8 threshold | 61-69% in production | ~20ms | Similar queries |
| **Plan-level** | Extract + reuse agent execution plans | Variable | ~50ms | Multi-step agent tasks |

At a 0.8 similarity threshold, semantic caching achieves a **68.8% hit rate** with **<1% false positives**. The 20ms embedding overhead is negligible compared to the ~850ms LLM call it replaces ([GPT Semantic Cache](https://arxiv.org/html/2411.05276v3), [Helicone](https://www.helicone.ai/blog/effective-llm-caching)).

### Multi-Layer Caching Architecture

```
[Request]
    |
    v
[L1: Exact Match Cache]     -- ~18% hit rate, <1ms
    |
    miss
    |
    v
[L2: Semantic Cache]        -- ~50% hit rate, ~20ms
    |
    miss
    |
    v
[L3: Plan Template Cache]   -- variable, ~50ms adaptation
    |
    miss
    |
    v
[L4: Full Agent Execution]  -- full cost + latency
```

A production implementation using this layered approach reported a combined 41% of requests never reaching the LLM (exact 15%, semantic 12%, session 8%, segment reuse 6%) ([AWS Database Blog](https://aws.amazon.com/blogs/database/optimize-llm-response-costs-and-latency-with-effective-caching/)).

### Agentic Plan Caching: The New Frontier

A NeurIPS 2025 paper introduced Agentic Plan Caching (APC) -- caching at the **plan level** rather than the query level. It caches the *strategy*, not the *answer*, meaning it works even when specific data changes ([arxiv](https://arxiv.org/abs/2506.14852)).

| Metric | Improvement |
|--------|------------|
| Agent serving cost reduction | **50.31%** |
| Latency reduction | **27.28%** |
| Performance retained | **96.61%** of optimal |

### Proposed Full Architecture: CDN-Enhanced N3TX

Here is how a fully integrated CDN layer would sit in the N3TX architecture:

```
                          CDN Edge Layer (Global PoPs)
                    +-----------------------------------------+
                    |                                         |
                    |  [Schema Cache]    [Response Cache]     |
                    |       |                  |              |
                    |  [JWT Validator]  [Semantic Cache]      |
                    |       |                  |              |
                    |  [Edge Classifier]  [MCP Edge Cache]   |
                    |       |                  |              |
                    +-------+----- Edge Router +--------------+
                                    |
                              [Cache Miss?]
                                    |
                 ---- Internet ---- | ---- Internet ----
                                    |
                    +--------------+----------------+
                    |      Origin (N3TX Server)      |
                    |                                |
                    |  [NetworkAPI]  [NetworkMCP]     |
                    |       |           |            |
                    |  [Auth Interceptor]             |
                    |       |                        |
                    |    [Matrix Router]              |
                    |    /     |      \              |
                    | [Product] [Agent] [Tools]      |
                    |    |       |        |          |
                    | [SQLite] [LLM]  [Schema]       |
                    |                                |
                    | [NetworkAP]  [NetworkEdge]      |
                    |     |            |             |
                    | [Federation] [Invalidation]    |
                    +--------------------------------+
```

**Request flow for a typical agent query:**

1. Client sends `POST /agents/1/agentic {"task": "Find grants"}` to CDN edge
2. Edge validates JWT (Tier 1 equivalent)
3. Edge checks semantic cache -- **cache hit**: return cached response (~50ms)
4. **Cache miss**: forward to origin
5. Origin `NetworkAPI` runs auth interceptor (Tier 1)
6. Matrix routes to `AgentActor` instance
7. `AgentMixin.run()` discovers tools from cached specs, runs LLM loop
8. Response flows back through Matrix -> NetworkAPI -> CDN edge
9. Edge caches response (with semantic embedding) for future queries
10. Edge invalidates cache when `LIFECYCLE` event arrives for related data

### Security Considerations

N3TX's two-tier authorization model is already designed for the edge/origin split:

| Tier | Current Location | CDN Equivalent |
|------|-----------------|----------------|
| **Tier 1** (interceptor) | `NetworkAPI.request()` -- fast gate: JWT validation, role checks | **Edge auth**: validate tokens, check roles, rate limit |
| **Tier 2** (handler) | `ActorModel.handler_crud()` -- ABAC with resource instance: OWNER checks | **Origin auth**: resource-level authorization |

The split exists because OWNER-based rules need the resource instance, which only the origin has. This is the same constraint CDN architectures face. N3TX already solved this problem -- no redesign needed.

---

## 4. :mag: Our Current Architecture Assessment

> :bulb: **Key Finding:** N3TX's existing architecture provides **five foundational capabilities** that CDN integration can build on -- not aspirational, but shipping code. The NetworkAdapter abstraction, schema-as-cacheable-contract, lifecycle event system, two-tier auth, and request-response correlation pattern all map directly to CDN integration points.

### What We Already Have

**1. NetworkAdapter Abstraction (the centerpiece)**

File: `/workspace/packages/n3tx-actors/src/n3tx_actors/api/network_adapter.py`

The `NetworkAdapter` base class is the single most important integration point. Every external protocol -- HTTP, WebSocket, MCP, ActivityPub -- is just a NetworkAdapter registered as a Matrix child. Adding a CDN edge adapter follows the exact same pattern.

```
Current N3TX Level 3 Architecture:
                                                    Existing Adapters
                                                    ┌─────────────┐
Client ──HTTP──> NetworkAPI ──TX──> Matrix ──TX──>  │ ActorModel  │
                                      ^             └─────────────┘
Client ──WS───> NetworkWS ──TX──────┘
                                      ^
Client ──MCP──> NetworkMCP ──TX─────┘
                                      ^
Server ──AP───> NetworkAP ──TX──────┘

Proposed Addition (zero architectural change):
                                      ^
CDN ──────────> NetworkEdge ──TX────┘    (5th adapter, same pattern)
```

A `NetworkEdge` adapter would subclass `NetworkAdapter`, implement `request()` to check an edge cache first, and only fall through to `super().request()` on cache miss. The interceptor chain (`use()`) already supports composable middleware -- adding a cache-check as an interceptor requires **zero base class changes** (see [02-our-stack-relevance.md](02-our-stack-relevance.md)).

**2. Schema as Cacheable Contract**

File: `/workspace/packages/n3tx-core/src/n3tx_core/models/proto_schema.py`

The JSON Schema returned by `GET /{ClassName}` is inherently CDN-friendly:

- **Immutable per deployment** -- schemas don't change between deploys
- **Self-describing** -- every response carries `$schema` and `$id`
- **Composable pipeline** -- `base -> strip_hidden -> methods -> defs -> access -> ui -> metadata` is already modular; adding a `cache_hints` stage is one decorator

```python
# This is all it takes to add cache metadata to schemas:
@schema_extension(after='access')
def cache(cls, schema: dict) -> dict:
    access = schema.get('access', {})
    schema['cache'] = {
        'schema_ttl': 86400,      # Schema: 24h (immutable per deploy)
        'public_reads': access.get('read') == 'anyone',
        'list_ttl': 60 if access.get('read') == 'anyone' else 0,
        'item_ttl': 300 if access.get('read') == 'anyone' else 0,
    }
    return schema
```

The pipeline after this stage: `base -> strip_hidden -> methods -> defs -> access -> cache -> ui -> metadata`.

**3. ActivityPub Adapter = Proof of Distribution**

The AP adapter (`NetworkAP`) already handles distributed content delivery. It receives `LIFECYCLE` events from ActorModel after create/update/delete, converts them to Activities, and pushes to followers. This is **conceptually identical to CDN cache invalidation**:

```python
# Current: AP adapter receives lifecycle events
Product._subscribers.append('ap')

# Future: CDN adapter receives same lifecycle events (no new mechanism)
Product._subscribers.append('edge')

# Both receive:
# TX(name='LIFECYCLE', source='products', target='edge',
#    data={'event': 'after_update', 'entity': {...}})
```

**4. Two-Tier Auth (Already Edge-Ready)**

The `auth_interceptor.py` already handles the edge/origin split: schema requests are always public (CDN can cache forever), list requests compute SQL filters at the boundary (CDN can cache by filter), create requests get full checks at the boundary (no resource needed), and read/update/delete requests get identity gates only (full OWNER check at origin Tier 2).

**5. Request-Response Correlation**

Matrix's `request()` method uses asyncio.Future keyed by TX uuid for correlation. An edge adapter uses the same pattern: send a TX to the origin Matrix, await the correlated response, cache it, return it.

### Gap Analysis: What We Lack

| Gap | Severity | Effort | Blocking? |
|-----|----------|--------|-----------|
| No `Cache-Control` headers on responses | Low | 1-2 days | No |
| No cache invalidation adapter | Medium | 1-2 weeks | No (stale cache acceptable short-term) |
| No edge-side schema validation | Medium | 2-3 weeks | No (nice-to-have) |
| Distributed agent state | High | 4-8 weeks | Yes (for edge agents only) |
| Auth token propagation through CDN | Medium | 1 week | No (standard JWT pattern) |

### Unique Advantages

N3TX has something no other agent framework has: **schema-driven edge intelligence.** The schema carries access rules, method signatures, cache hints, and self-describing response metadata. An edge node reading the schema knows:

- Which endpoints are publicly cacheable (`access.read == "anyone"`)
- What payload structure tool calls expect (`methods[name].parameters`)
- How long to cache each response type (from `cache` hints)
- How to validate responses (`$schema`, `$id`)

No other agent framework -- not LangChain, not CrewAI, not Vercel AI SDK -- carries enough metadata in its schemas to enable edge-side decision making. This is N3TX's competitive differentiator for CDN integration (see [02-our-stack-relevance.md](02-our-stack-relevance.md)).

### Code-Level Integration Points

| Integration Point | File | Change Required |
|---|---|---|
| Schema cache headers | `network_api.py` -> `_register_schema_route()` | Add `Cache-Control: public, max-age=86400` |
| Read response caching | `network_api.py` -> `_register_crud_routes()` | Add conditional `Cache-Control` based on `__access__` |
| Schema pipeline extension | New `cache_schema.py` | `@schema_extension(after='access')` |
| Lifecycle invalidation | New `network_edge.py` | `NetworkEdge(NetworkAdapter)` subscribing to LIFECYCLE events |
| Agent response cache | `mixin.py` -> `run()` | Wrap execution with cache check/store |

### Concrete Code Sketch: NetworkEdge Adapter

The `NetworkEdge` adapter would follow the same pattern as `NetworkAP`. Here is the core design:

```python
class NetworkEdge(NetworkAdapter, auto_register=False):
    """CDN edge cache invalidation adapter.

    Subscribes to LIFECYCLE events from storable models and sends
    cache purge requests to the configured CDN provider.

    Usage:
        edge = NetworkEdge(edge_api='https://api.cloudflare.com/...')
        matrix.register(edge)
        for model in registered_models.values():
            if hasattr(model, '_subscribers'):
                model._subscribers.append('edge')
    """

    _edge_api: str = PrivateAttr(default='')
    _zone_id: str = PrivateAttr(default='')

    def __init__(self, edge_api: str = '', zone_id: str = '', **kwargs):
        kwargs.setdefault('addr', 'edge')
        super().__init__(**kwargs)
        self._edge_api = edge_api
        self._zone_id = zone_id

    def LIFECYCLE(self, data: dict, tx: TX):
        """Invalidate edge cache on data mutation."""
        event = data.get('event', '')
        entity = data.get('entity', {})
        tablename = tx.source  # e.g., 'products'

        if event in ('after_create', 'after_update', 'after_delete'):
            item_id = entity.get('id')
            if item_id:
                self._purge(f'/{tablename}/{item_id}')
            self._purge(f'/{tablename}')  # list is stale after any mutation

    def _purge(self, path: str):
        """Send cache purge request to CDN API."""
        # Cloudflare: POST /zones/{zone}/purge_cache
        # Fastly: POST /service/{id}/purge/{key}
        # Generic: configurable per CDN provider
        ...
```

This adapter is ~100 lines of code, follows existing patterns, and plugs into the existing subscription mechanism with zero changes to the core framework.

### Concrete Code Sketch: Semantic Cache in AgentMixin

The semantic cache integration wraps the existing `run()` method:

```python
# In AgentMixin.run(), around line 383 of mixin.py

# Before the Pydantic AI agent loop:
cache_key = f"agent:{agent_addr}:{hash((task, tuple(tools)))}"
cached = await _check_exact_cache(cache_key)
if cached:
    cached['from_cache'] = 'exact'
    return cached

if config.AGENT_DEFAULTS.get('semantic_cache'):
    semantic_result = await _semantic_cache_lookup(task, agent_addr)
    if semantic_result:
        semantic_result['from_cache'] = 'semantic'
        return semantic_result

# Existing: result = await ai_agent.run(task, **run_kwargs)

# After the Pydantic AI agent loop:
await _store_cache(cache_key, result_dict,
                   ttl=config.AGENT_DEFAULTS.get('cache_ttl', 3600))
```

The `from_cache` field in the response lets callers (and the frontend) know whether the response came from cache, enabling transparency and debugging.

---

## 5. :bar_chart: Cost-Benefit Analysis

> :bulb: **Key Finding:** Phase 1 (schema CDN + AI Gateway) costs $0-15/month and pays for itself on day one by eliminating 99% of schema requests and providing LLM observability. Phase 2 (semantic caching) saves $580/month at 50K requests and $5,800/month at 500K requests. Phase 3 (edge agents) is capital-intensive and only justified by measured latency data.

### Investment Required by Phase

| Phase | Engineering Time | Monthly Service Cost | Monthly Savings | Break-Even |
|-------|-----------------|---------------------|-----------------|------------|
| **Phase 1:** Schema CDN + AI Gateway | ~2 weeks | $0-15 | Schema: eliminates #1 API call; AI Gateway: observability + ~18% LLM cache hits | Immediate |
| **Phase 2:** Semantic Caching + Edge Classification | ~4-6 weeks | $50-500 | $580/mo at 50K req; $5,800/mo at 500K req | 2-4 months |
| **Phase 3:** Edge Agent Workers | ~8-12 weeks | Variable | Sub-100ms globally; additional savings TBD | 6-12 months |

### ROI Calculation: Semantic Caching (Phase 2)

**Assumptions (conservative):** 50,000 agent requests/month, average 2,000 tokens per request, Claude Sonnet at $3/M input + $15/M output tokens, 50% of tokens are output.

**Without caching:**

| Line Item | Calculation | Monthly Cost |
|-----------|-------------|-------------|
| Input tokens | 50,000 x 1,000 tokens = 50M x $3/M | $150 |
| Output tokens | 50,000 x 1,000 tokens = 50M x $15/M | $750 |
| **Total** | | **$900/month** |

**With semantic caching (65% hit rate):**

| Line Item | Calculation | Monthly Cost |
|-----------|-------------|-------------|
| Cache hits | 32,500 requests x $0 | $0 |
| Input tokens (misses) | 17,500 x 1,000 = 17.5M x $3/M | $52.50 |
| Output tokens (misses) | 17,500 x 1,000 = 17.5M x $15/M | $262.50 |
| Embedding cost | 50,000 x ~$0.0001 | $5 |
| **Total** | | **$320/month** |
| **Savings** | | **$580/month (64%)** |

**At scale (500,000 requests/month):** Without caching $9,000/month. With caching $3,200/month. **Annual savings: $69,600.**

### ROI Calculation: Schema CDN (Phase 1)

**Assumptions:** 100,000 schema requests/month, average schema size 5KB, origin server in US-East.

| Metric | Without CDN | With CDN (1h TTL) |
|--------|-------------|-------------------|
| Origin requests | 100,000/month | ~1,000/month (99% cache hit) |
| Origin bandwidth | 500MB/month | 5MB/month |
| Global latency | 50ms (US) to 300ms (Asia/EU) | <20ms globally |
| Cost | Origin compute | Free (within Cloudflare free tier) |

This is a **no-brainer optimization** -- free, simple, and immediately effective.

### Build vs. Buy Analysis

| Layer | Build | Buy/Integrate | Recommendation |
|-------|-------|--------------|----------------|
| CDN for static assets | Custom deployment | Cloudflare/Vercel/AWS CDN | **Buy.** Commodity. |
| AI Gateway (caching, routing, rate limiting) | Custom proxy | Cloudflare AI Gateway, Portkey, Helicone | **Buy first, build later.** |
| Edge agent runtime | N3TX on Durable Objects | Cloudflare Agents SDK | **Integrate.** Map N3TX patterns to edge primitives. |
| Semantic caching | Custom embedding + Redis | Redis Semantic Cache, GPTCache | **Buy for v1, build for v2.** |
| Edge inference | Self-host models at edge | Workers AI, Akamai Inference Cloud | **Buy.** GPU infra is not your business. |

### 3-Year Total Cost of Ownership

| Approach | Year 1 | Year 2 | Year 3 | 3-Year Total |
|----------|--------|--------|--------|-------------|
| **Build custom CDN integration** | $80-120K (eng time) | $40-60K (maintenance) | $40-60K (maintenance) | $160-240K |
| **Buy AI Gateway + CDN** | $5-15K (integration) + $2-10K/yr (service) | $2-10K (service) | $2-10K (service) | $11-45K |
| **Hybrid: Buy gateway, build adapter** | $20-40K (eng time) | $10-20K + $2-10K | $10-20K + $2-10K | $44-100K |

According to industry analysis, initial development accounts for less than 30% of total cost over an integration's lifetime -- the real expense is ongoing maintenance ([ThirstySprout](https://www.thirstysprout.com/post/build-vs-buy-software)). The **hybrid approach** is optimal for N3TX: buy the commodity layers, invest engineering time only in the N3TX-specific adapter.

### Hidden Costs Nobody Mentions

1. **Observability tax:** Budget 20-30% of edge deployment effort for monitoring. Debugging a misbehaving agent across 50 edge locations is exponentially harder than debugging one central server.
2. **Stale cache risk:** Semantic caching has a 0.8% false positive rate. At 500K requests/month, that is 4,000 potentially wrong answers served to users.
3. **Vendor lock-in gradient:** CDN headers (Phase 1) are vendor-neutral. Edge agent workers (Phase 3) create real lock-in. Plan accordingly.
4. **Team skill requirements:** Phases 1-2 require standard web engineering. Phase 3 requires distributed systems expertise.

---

## 6. :world_map: Decision Framework

> :bulb: **Key Finding:** The decision to adopt CDN-for-agents should be gated by measurable criteria, not enthusiasm. A maturity model with five levels provides clear trigger conditions for each investment phase.

### Decision Tree

```
START: Do you have agent workloads in production?
  |
  +-- NO --> Focus on agent correctness first. CDN is premature. STOP.
  |
  +-- YES
       |
       v
  Are LLM API costs a material concern (>$500/month)?
       |
       +-- NO --> Schema CDN only (free, no downside). Revisit at scale.
       |
       +-- YES
            |
            v
       What percentage of agent queries are repetitive/similar?
            |
            +-- <20%  --> Request routing, not caching. Go to Pattern 2.
            |
            +-- 20-50% --> Semantic caching is profitable. Go to Phase 2.
            |
            +-- >50%  --> Aggressive multi-layer caching. Go to Phase 2+.
                    |
                    v
               Is sub-100ms response time a requirement?
                    |
                    +-- NO  --> Central inference + CDN caching is sufficient.
                    |
                    +-- YES --> Evaluate edge inference. Go to Phase 3.
```

### Maturity Model: Where Is N3TX Today?

| Level | Description | N3TX Status | CDN Strategy |
|-------|-------------|-------------|-------------|
| **L0** | No agents in production | -- | None needed |
| **L1** | Agents working, small scale | **Current** | Schema caching via static CDN |
| **L2** | Multiple agents, growing LLM spend | Next 6 months | AI Gateway (Cloudflare or equivalent) |
| **L3** | High-volume agent workloads | 12+ months | Semantic caching + edge routing |
| **L4** | Latency-critical global deployment | 18+ months | Edge inference for classification |
| **L5** | Full edge agent orchestration | 24+ months | Durable Objects / full edge agents |

### Measurable Trigger Conditions

These are not suggestions -- they are minimum thresholds. Do not advance to the next level without meeting these criteria.

**L1 -> L2 (Add AI Gateway):**
- LLM API spend exceeds **$500/month**
- Agent query volume exceeds **10,000 requests/month**
- At least **3 distinct agent use cases** in production

**L2 -> L3 (Add Semantic Caching):**
- Cache hit analysis shows **>30% query similarity**
- LLM API spend exceeds **$2,000/month**
- P95 agent response latency exceeds **3 seconds**

**L3 -> L4 (Add Edge Routing/Classification):**
- Global user base with **>200ms geographic latency variance**
- Schema fetch volume exceeds **100,000 requests/month**
- Agent classification accuracy of edge model exceeds **95%**

**L4 -> L5 (Full Edge Agents):**
- Latency requirement is **<100ms end-to-end**
- Agent workload is **primarily stateless** or has clear session affinity
- Team has **distributed systems operational experience**
- Monthly edge compute budget exceeds **$5,000/month**

### Pattern Selection Guide: When to Use Each Pattern

| Scenario | Recommended Pattern | Why | Phase |
|----------|-------------------|-----|-------|
| Schema-driven frontend, global users | CDN for schemas | Free, instant, no code changes | 1 |
| Growing LLM spend, repetitive queries | AI Gateway + exact-match caching | 50-73% cost reduction | 1 |
| Multi-agent system, tool discovery | CDN for tool registry | Simplifies federation, MCP at edge | 1-2 |
| Enterprise support bot, FAQ-heavy | Semantic caching | 60%+ hit rate on similar queries | 2 |
| Global real-time personalization | Edge classification | Sub-50ms routing decisions | 2-3 |
| Latency-critical autonomous agents | Full edge agents | Sub-100ms end-to-end | 3 |
| Complex multi-step reasoning | **Central only** | Edge constraints too limiting | N/A |
| Agents with large context windows | **Central only** | Memory limits at edge | N/A |
| Agents updating shared databases | **Central only** | Distributed writes are hard | N/A |

### When CDN-for-Agents Does NOT Make Sense

| Scenario | Why Not | Alternative |
|----------|---------|-------------|
| Complex multi-step reasoning | Edge constraints (memory, model size) too limiting | Central inference only |
| Agents with large context windows (>128K tokens) | Memory limits at edge | Central inference only |
| Agents updating shared databases | Distributed writes are a consistency nightmare | Central with read replicas |
| Small-scale deployment (<1K requests/month) | Complexity cost exceeds savings | Direct origin calls |
| Rapidly changing schemas | CDN cache invalidation overhead exceeds benefit | Direct origin calls |

### Anti-Patterns to Avoid

**1. Premature edge inference.** "Let's run our 70B model at every edge location!" -- 68% of industrial AI pilots fail to scale ([Edge IR](https://www.edgeir.com/why-edge-architectures-fail-and-how-to-design-around-it-20260316)). Start with caching and routing. Move inference to the edge only with measurable proof that latency is the bottleneck.

**2. Caching non-deterministic agent output.** Aggressively caching responses from agents that use dynamic tools (web scraping, live APIs). A cached answer to "What grants are available?" becomes stale the moment new grants are published. Cache the *plan*, not the *answer*, for agents with dynamic data.

**3. Distributed state for stateful agents.** Running agents with conversation history across multiple edge locations. State synchronization across edge nodes introduces consistency problems. Stateless classification at the edge, stateful execution at a single location.

**4. Ignoring the observability tax.** Edge nodes generate metrics from thousands of distributed locations. Budget 20-30% of edge deployment effort for observability. If you cannot trace an agent's decision from request to response across edge and origin, you are not ready.

---

## 7. :bulb: Recommendation

> :bulb: **Key Finding:** A three-phase approach, gated by measurable triggers, is the right strategy. Phase 1 is a no-brainer for today. Phase 2 becomes urgent when LLM costs cross $500/month. Phase 3 is a future investment that depends on global deployment needs.

### The Phased Approach

**Phase 1: CDN for Schemas + AI Gateway (Now -- 3 months)**

*Effort:* ~2 weeks | *Cost:* $0-15/month | *Impact:* 99% schema cache hit rate + LLM observability

1. Deploy Cloudflare (or equivalent) CDN in front of N3TX static + schema endpoints
2. Add `Cache-Control: public, max-age=86400` headers on `GET /{ClassName}` responses
3. Route all `pydantic-ai` LLM calls through Cloudflare AI Gateway
4. Enable exact-match caching on AI Gateway with 1-hour TTL
5. Add `cache` stage to schema pipeline via `@schema_extension(after='access')`

```
[N3TX Frontend] --schema fetch--> [CDN Edge] --cache miss--> [N3TX Backend]
                                       |
                                  cache hit (99%)
                                       |
                                  [Cached Schema]

[N3TX Agent]   --LLM call-------> [AI Gateway] --cache miss--> [OpenAI/Anthropic]
                                       |
                                  cache hit (~18%)
                                       |
                                  [Cached Response]
```

Files to modify:
- `packages/n3tx-actors/src/n3tx_actors/api/network_api.py` -- `_register_schema_route()`, `_register_crud_routes()`
- `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py` -- same changes for Level 1/2
- New: `packages/n3tx-core/src/n3tx_core/models/cache_schema.py`

**Phase 2: Semantic Caching + Edge Classification (3-9 months)**

*Effort:* ~4-6 weeks | *Cost:* $50-500/month | *Impact:* 50-65% reduction in LLM costs

**Trigger:** LLM API spend exceeds $500/month AND >30% query similarity measured.

1. Add embedding step before agent dispatch: embed incoming query, check against cached queries
2. Implement similarity threshold (start at 0.85, tune toward 0.80 based on accuracy monitoring)
3. Deploy lightweight classification model at edge for request routing
4. Create `NetworkEdge` adapter subscribing to LIFECYCLE events for cache invalidation

```
[Request] --> [Edge Classifier]
                  |
                  +-- "cached" ------> [Semantic Cache] --> [Response]
                  |
                  +-- "novel" -------> [N3TX Agent] --> [Response + Cache Update]
                  |
                  +-- "schema" ------> [CDN Schema Cache] --> [Schema]
```

Files to modify:
- `packages/n3tx-agents/src/n3tx_agents/mixin.py` -- `run()` method (cache check wrapper)
- `packages/n3tx-agents/src/n3tx_agents/actor.py` -- `AgentActor` cache config fields
- New: `packages/n3tx-actors/src/n3tx_actors/api/network_edge.py`

**Architectural fit:** The `agentic()` method is already the policy boundary -- adding a cache-check step before `run()` fits the existing pattern perfectly. Tool discovery via `discover_tools()` already reads schemas -- caching tool definitions at the CDN level is a natural extension. The TX message envelope includes `meta` with `req` correlation IDs that can serve as cache keys.

**Phase 3: Edge Agent Workers (9-18 months, contingent on scale)**

*Effort:* ~8-12 weeks | *Cost:* Variable | *Impact:* Sub-100ms agent responses globally

**Prerequisites (all must be met):**
- [ ] Monthly agent request volume exceeds 100,000
- [ ] Global user base with measurable latency variance >200ms
- [ ] At least 3 agent types that are primarily stateless
- [ ] Operational runbook for distributed debugging

1. Build adapter mapping N3TX's ActorModel to Cloudflare Durable Objects
2. Deploy lightweight edge agents for classification, routing, simple tool execution
3. Keep complex reasoning centralized, distributed via CDN-cached schema + tool registry

**Architecture for edge agent workers:**

```
Client  ---->  CDN Edge (EdgeAgentWorker + edge LLM)
                    |
          [Simple query?]  ----Yes---->  Edge LLM responds
                    |                     (Cloudflare Workers AI,
          No (complex)                    50+ models available,
                    |                     100-500ms response)
          Forward to origin  ---->  Full N3TX agent loop
                    |                     (origin LLM, full tools,
                    |                      full state, 2-30s response)
          <---- stream response ----
```

**Key technical consideration:** The `EdgeAgentWorker` would be the first NetworkAdapter that can **short-circuit** the TX chain. Today, all adapters forward every request to the Matrix. An edge adapter would resolve some requests locally from cache or edge inference, only forwarding cache misses. This is architecturally novel for N3TX but fits into the existing `request()` / `inbox()` correlation pattern (see [02-our-stack-relevance.md](02-our-stack-relevance.md)).

**Strongest alignment:** N3TX's schema and tool discovery layer. The "schema is the contract" philosophy means schemas are already designed to be fetched, cached, and consumed by remote systems. Putting a CDN in front of schema endpoints amplifies an existing pattern.

**Weakest alignment:** The storage layer. N3TX uses SQLite with auto-migration; Durable Objects also use SQLite but with different lifecycle semantics. A full edge agent deployment would need a storage adapter -- not impossible, but non-trivial.

### What We Explicitly Do NOT Recommend

- **Full edge inference for complex agents.** Edge model constraints (10GB storage, limited context windows) make multi-step reasoning impractical at the edge. Keep it central.
- **Building a custom CDN.** CDN infrastructure is commodity. Buy it. N3TX's value is in the schema-driven integration layer, not the caching hardware.
- **Deploying semantic caching before measuring query similarity.** If your queries are 80% unique, semantic caching ROI is low. Measure first with the AI Gateway observability data from Phase 1.
- **Skipping phases.** Each phase provides the observability data needed to justify the next. Phase 1's AI Gateway metrics tell you whether Phase 2 is worth it. Phase 2's caching data tells you whether Phase 3 is worth it.

### Review Cadence

- **Monthly:** Review AI Gateway metrics (cache hit rate, LLM spend, latency percentiles)
- **Quarterly:** Evaluate readiness for next phase against trigger conditions
- **Annually:** Reassess provider landscape (Akamai, new entrants, pricing changes)

---

## 8. :shield: Risk Register

> :bulb: **Key Finding:** The top risks are organizational (overcommitting to edge before measuring), not technical. N3TX's adapter architecture provides natural containment for vendor lock-in risk.

| # | Risk | Probability | Impact | Phase | Mitigation |
|---|------|------------|--------|-------|------------|
| R1 | **Premature edge investment** -- spending engineering time on Phase 3 before Phase 1/2 data justifies it | High | High | All | Enforce measurable trigger conditions. Do not advance without data. |
| R2 | **Vendor lock-in** -- deep integration with Cloudflare Durable Objects creates switching costs | Medium | High | Phase 3 | Abstract via NetworkAdapter pattern (N3TX already uses adapters for HTTP, WS, MCP, AP). Edge adapter should be one of several. |
| R3 | **Stale cache serving wrong answers** -- semantic cache returns outdated agent responses after data changes | Medium | Medium | Phase 2 | TTL tuning, LIFECYCLE event-driven invalidation, similarity threshold monitoring. Start conservative (0.85), loosen with evidence. |
| R4 | **Operational complexity exceeds team capacity** -- debugging distributed agents across edge locations | High | High | Phase 3 | Phase gates with measurable criteria. Budget 20-30% of Phase 3 effort for observability tooling. |
| R5 | **Edge model quality insufficient** -- classification model at edge misroutes requests | Low | Medium | Phase 2-3 | Test edge models against central baseline. Fallback to central on low confidence scores. |
| R6 | **Cost overrun on edge compute** -- unexpected edge compute costs from misconfigured caching or runaway agent loops | Low | Medium | Phase 1-2 | Per-request billing + rate limiting via AI Gateway. Set budget alerts at $100, $500, $1,000/month. |
| R7 | **Security gap in edge JWT validation** -- edge node accepts forged or expired tokens | Low | High | Phase 2-3 | Use standard JWT public key distribution. Edge validates signature and expiry. Tier 2 origin auth provides defense-in-depth. |
| R8 | **Schema versioning conflicts** -- CDN serves stale schema after deployment | Low | Medium | Phase 1 | ETag-based validation. Deploy-time cache purge. Schema hash in `$id` URL for cache-busting. |
| R9 | **Competitor leapfrog** -- Cloudflare, Vercel, or LangChain ships native CDN-agent integration that makes our adapter obsolete | Medium | Low | Phase 2-3 | N3TX's value is schema-driven intelligence, not the CDN layer itself. If a provider ships something better, adopt it -- the adapter pattern makes switching cheap. |
| R10 | **Team distraction** -- CDN integration diverts engineering from core framework improvements | Medium | Medium | All | Timebox Phase 1 to 2 weeks. Defer Phase 2 until trigger conditions met. Phase 3 is explicitly contingent on scale. |

### Probability-Impact Matrix

```
              LOW IMPACT       MEDIUM IMPACT      HIGH IMPACT
HIGH PROB  |                |  R10 (distract)  |  R1 (premature)
           |                |                  |  R4 (complexity)
           |                |                  |
MED PROB   |                |  R3 (stale)      |  R2 (lock-in)
           |                |  R9 (competitor)  |
           |                |                  |
LOW PROB   |                |  R5 (quality)    |  R7 (security)
           |                |  R6 (cost)       |
           |                |  R8 (versioning) |
```

**Top 3 risks to actively manage:** R1 (premature investment), R2 (vendor lock-in), R4 (operational complexity). All three are mitigated by the same approach: **phased adoption with measurable gates.**

---

## 9. :paperclip: Appendices

### Appendix A: Glossary

| Term | Definition |
|------|-----------|
| **CDN** | Content Delivery Network -- a global network of servers that caches content closer to end users to reduce latency |
| **Edge** | Computing infrastructure located geographically close to end users (CDN PoPs, edge servers, IoT devices) |
| **PoP** | Point of Presence -- a physical location where a CDN has servers |
| **TTL** | Time To Live -- how long a cached response is considered valid before re-fetching from origin |
| **ETag** | Entity Tag -- a hash of a response's content used for cache validation (if content hasn't changed, serve from cache) |
| **Semantic caching** | Caching based on meaning similarity (via embeddings) rather than exact string match |
| **AI Gateway** | A proxy layer between applications and LLM providers that adds caching, rate limiting, and observability |
| **Durable Objects** | Cloudflare's stateful compute primitive -- a single-threaded actor with built-in SQLite and WebSocket support |
| **Workers AI** | Cloudflare's edge inference platform -- runs ML models at CDN edge locations |
| **Neuron** | Cloudflare's billing unit for Workers AI inference -- roughly proportional to model size x tokens processed |
| **NetworkAdapter** | N3TX's base class for protocol bridges -- translates between external protocols and internal TX messages |
| **TX** | Transaction message -- N3TX's internal message envelope carrying name, target, source, data, and metadata |
| **Matrix** | N3TX's root actor and message router -- all TX messages flow through Matrix for dispatch |
| **Schema pipeline** | N3TX's composable system for generating JSON Schema from model definitions -- `base -> strip_hidden -> methods -> defs -> access -> ui -> metadata` |
| **LIFECYCLE event** | TX message emitted by ActorModel after create/update/delete -- used for cache invalidation, federation, and side effects |
| **APC** | Agentic Plan Caching -- caching agent execution plans (strategies) rather than final answers, enabling reuse across similar but non-identical tasks |

### Appendix B: Competitive Positioning

| Feature | N3TX (proposed) | LangChain | CrewAI | Cloudflare Agents | Vercel AI SDK |
|---|---|---|---|---|---|
| Schema-driven caching | Native (schema carries cache hints) | No | No | No | No |
| Edge agent routing | Via NetworkEdge adapter | No native | No native | **Native** (Durable Objects) | **Native** (Edge Functions) |
| Tool discovery caching | Schema-embedded tools | No native | [Known issues](https://github.com/crewAIInc/crewAI/issues/886) | No (tools in code) | No (tools in code) |
| Semantic caching | Pluggable (via AgentMixin) | Via GPTCache | Planned | No native | Via middleware |
| Cache invalidation | LIFECYCLE events (existing) | Manual | Manual | Durable Object state | Revalidation API |
| Multi-protocol edge | HTTP + MCP + AP + WS | HTTP only | HTTP only | HTTP + WS + RPC | HTTP + WS |
| Auth at edge | Two-tier (already split) | Manual | Manual | Workers auth | Edge middleware |

N3TX's unique advantage is schema-driven edge intelligence. No other framework carries enough metadata in its schemas to enable edge-side decision-making: access rules, method signatures, cache hints, and self-describing responses.

### Appendix C: Implementation Roadmap Detail

| Phase | Week | Deliverable | Files |
|-------|------|-------------|-------|
| **1** | 1 | Cache-Control headers on schema + read routes | `network_api.py`, `routes_fastapi.py` |
| **1** | 1 | ETag support for schema responses | `network_api.py`, `routes_fastapi.py` |
| **1** | 2 | CDN deployment (Cloudflare free tier) | Infrastructure config |
| **1** | 2 | AI Gateway for LLM call routing | `pydantic-ai` config, `mixin.py` |
| **2** | 3 | Schema pipeline `cache` extension | New `cache_schema.py` |
| **2** | 3 | Per-model `__cache__` config support | `proto_model.py` |
| **2** | 4-5 | `NetworkEdge` adapter for LIFECYCLE invalidation | New `network_edge.py` |
| **2** | 5-8 | Semantic cache integration in `AgentMixin.run()` | `mixin.py`, `actor.py` |
| **3** | 9-10 | Edge complexity classifier prototype | New edge runtime code |
| **3** | 11-14 | `EdgeAgentWorker` adapter | New `network_edge_worker.py` |
| **3** | 15-18 | Production benchmarking + observability | Monitoring infrastructure |

### Appendix D: Edge Compute Pricing Reference

| Provider | Unit | Cost | Free Tier |
|----------|------|------|-----------|
| Cloudflare Workers | 1M requests | ~$0.30 | 100K req/day |
| Cloudflare Workers AI | 1K Neurons | $0.011 | 10K Neurons/day |
| Cloudflare AI Gateway | Per feature | Free (caching, logging) | Yes |
| AWS Lambda@Edge | 1M requests + GB-s | $0.60 + $0.00005/128MB-s | 1M req/month |
| AWS Bedrock (Claude Sonnet) | 1M input tokens | $3.00 | None |
| Vercel Edge Functions | Active CPU hour | $5/hr (Pro overage) | 500K invocations |

### Appendix E: Source References

**Industry & Market Data:**
1. [Grand View Research - Edge AI Market Report](https://www.grandviewresearch.com/industry-analysis/edge-ai-market-report)
2. [Fortune Business Insights - Edge AI Market](https://www.fortunebusinessinsights.com/edge-ai-market-107023)
3. [Gartner - 40% Enterprise Apps Will Feature AI Agents by 2026](https://www.gartner.com/en/newsroom/press-releases/2025-08-26-gartner-predicts-40-percent-of-enterprise-apps-will-feature-task-specific-ai-agents-by-2026-up-from-less-than-5-percent-in-2025)
4. [All About AI - Edge AI Statistics 2025](https://www.allaboutai.com/resources/ai-statistics/edge-ai/)
5. [WalkMe - State of Enterprise AI Adoption 2025](https://www.walkme.com/blog/enterprise-ai-adoption/)

**Provider Documentation:**
6. [Cloudflare Workers AI Docs](https://developers.cloudflare.com/workers-ai/)
7. [Cloudflare - Infire Inference Engine](https://blog.cloudflare.com/cloudflares-most-efficient-ai-inference-engine/)
8. [Cloudflare Agents SDK](https://developers.cloudflare.com/agents/)
9. [Cloudflare AI Gateway](https://developers.cloudflare.com/ai-gateway/)
10. [Cloudflare Workers AI Large Models](https://blog.cloudflare.com/workers-ai-large-models/)
11. [AWS Bedrock AgentCore Pricing](https://aws.amazon.com/bedrock/agentcore/pricing/)
12. [Akamai Inference Cloud](https://www.akamai.com/newsroom/press-release/akamai-inference-cloud-gains-early-traction-as-ai-moves-out-to-the-edge)

**Case Studies & Benchmarks:**
13. [Cloudflare - Baselime Migration: 80% Lower Cloud Cost](https://blog.cloudflare.com/80-percent-lower-cloud-cost-how-baselime-moved-from-aws-to-cloudflare/)
14. [Hybrid Edge-Cloud Energy/Cost Analysis (arxiv)](https://arxiv.org/html/2501.14823v2)
15. [GPT Semantic Cache (arxiv)](https://arxiv.org/html/2411.05276v3)
16. [Agentic Plan Caching - NeurIPS 2025 (arxiv)](https://arxiv.org/abs/2506.14852)
17. [Helicone - Effective LLM Caching](https://www.helicone.ai/blog/effective-llm-caching)
18. [VentureBeat - Semantic Caching Cuts LLM Bill by 73%](https://venturebeat.com/orchestration/why-your-llm-bill-is-exploding-and-how-semantic-caching-can-cut-it-by-73)
19. [AWS Database Blog - Optimize LLM Response Costs with Caching](https://aws.amazon.com/blogs/database/optimize-llm-response-costs-and-latency-with-effective-caching/)

**Failure Modes & Lessons:**
20. [Edge IR - Why Edge Architectures Fail](https://www.edgeir.com/why-edge-architectures-fail-and-how-to-design-around-it-20260316)
21. [Computer Weekly - Edge AI: What's Working and What Isn't](https://www.computerweekly.com/feature/Edge-AI-Whats-working-and-what-isnt)
22. [Gcore - AI Edge Deployment Challenges](https://gcore.com/learning/challenges-solutions-deploying-ai-edge)
23. [Edge Delta - Observability Framework for AI Systems](https://edgedelta.com/company/blog/a-new-observability-framework-for-ai-systems)

**Build vs. Buy & Cost Analysis:**
24. [ThirstySprout - Build vs Buy Decision Framework](https://www.thirstysprout.com/post/build-vs-buy-software)
25. [Market.us - Edge AI Market](https://market.us/report/edge-ai-market/)
26. [CIO - Edge vs Cloud TCO](https://www.cio.com/article/4109609/edge-vs-cloud-tco-the-strategic-tipping-point-for-ai-inference.html)

**N3TX Internal Research:**
27. [Industry Landscape & Decision Framework](01-industry-and-decisions.md)
28. [N3TX Architecture Integration Analysis](02-our-stack-relevance.md)

### Appendix F: Measurement Guide

**Phase 1 Metrics to Track:**

| Metric | How to Measure | Target |
|--------|---------------|--------|
| Schema cache hit rate | CDN analytics (Cloudflare dashboard) | >95% |
| Schema response latency (global) | CDN analytics, synthetic monitoring | <50ms P95 |
| LLM exact-match cache hit rate | AI Gateway dashboard | >15% |
| LLM API spend | AI Gateway cost tracking | Baseline for Phase 2 decision |
| Agent request volume | API logs, AI Gateway | Baseline for scaling decisions |

**Phase 2 Metrics to Track:**

| Metric | How to Measure | Target |
|--------|---------------|--------|
| Semantic cache hit rate | Custom instrumentation in `run()` | >40% |
| Semantic cache accuracy | Manual review of cached responses | >97% |
| False positive rate | Automated comparison: cached vs fresh response | <1% |
| LLM cost reduction | AI Gateway before/after comparison | >50% |
| Agent response latency (P50, P95) | API logs | P50 < 1s, P95 < 5s |
| Cache invalidation lag | Time from LIFECYCLE event to edge purge | <30s |

**Phase 3 Metrics to Track:**

| Metric | How to Measure | Target |
|--------|---------------|--------|
| Edge agent response latency | Edge analytics | <100ms P95 |
| Edge classification accuracy | Comparison: edge routing vs correct routing | >95% |
| Origin offload percentage | Ratio of edge-served vs origin-served agent requests | >40% |
| Edge compute cost | Provider billing | Within budget constraints |
| Distributed debugging resolution time | Incident tracking | <2 hours for P1 issues |
