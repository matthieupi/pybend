# CDN Capabilities Applied to N3TX Agents: A Technical Whitepaper

> *How principles from CDN architecture and edge computing can reshape N3TX's agent cost structure and global performance -- and where they cannot.*
> *Companion to the [propositions document](CDN-agents-propositions.md).*

---

## Abstract

N3TX agents are the framework's most expensive and latency-sensitive operation. A single `agentic()` call triggers multiple LLM API requests costing $0.01-1.00, takes 2-30 seconds, and produces results that are frequently similar to prior queries. CDN and edge computing principles -- caching, distribution, boundary classification -- can reduce these costs by 50-65% without changing how agents reason. N3TX is uniquely positioned for this integration because its schema-driven architecture already provides the metadata CDN systems need: access rules that determine cacheability, self-describing responses with `$schema` and `$id`, and a lifecycle event system that enables invalidation. This whitepaper argues for a three-phase approach: (1) cache headers and AI gateway integration as immediate wins, (2) semantic caching in `AgentMixin.run()` as a medium-term investment, and (3) a `NetworkEdge` adapter for event-driven invalidation. The core principle: move *decisions about inference* to the boundary, not inference itself.

---

## 1. Introduction: Why This Matters Now

N3TX's agent system (v0.10) is feature-complete: `AgentMixin` provides policy and execution layers, `AgentActor` enables data-driven agent instances, tool discovery reads schemas from the actor tree, and streaming delivers progressive results via SSE. The next challenge is not capability but **economics**.

Every call to `AgentMixin.run()` (mixin.py, line 268) creates a fresh Pydantic AI Agent, discovers tools, and executes the LLM loop. For a grant-scanning agent with 3 tool sources, this means:
- `discover_tools()` reads 3 schemas (~5ms each)
- Pydantic AI sends 3-15 LLM requests (~1-5 seconds each, ~$0.01-0.10 each)
- Total: 5-30 seconds, $0.05-1.00 per invocation

At 10,000 agent requests/month (a modest production load), that is $500-10,000/month in LLM costs alone. At 100,000 requests, it becomes untenable without optimization. Research shows 40-60% of enterprise agent queries are repetitive or highly similar (VentureBeat). Semantic caching achieves 68.8% hit rates at 0.8 similarity threshold with <1% false positives (GPT Semantic Cache, arxiv). The math is compelling: caching halves the bill.

But the opportunity goes deeper than cost. N3TX's schema-driven philosophy -- where `GET /Product` returns a complete JSON Schema with access rules, methods, and UI hints -- creates a natural fit with CDN architectures that need metadata to make boundary decisions. No other agent framework carries this level of self-describing metadata in its wire protocol.

---

## 2. Principles Worth Importing

### Principle 1: Move Decisions to the Boundary

CDN architectures never ask "should we cache this?" at the origin. The origin declares cacheability via `Cache-Control` headers; the edge makes the decision autonomously. The same principle applies to agent workloads: the origin (N3TX server) should declare *what is cacheable* through its schema, and the boundary (CDN edge, AI gateway, or the `agentic()` policy layer itself) should decide *whether to cache*.

N3TX already partially implements this. The `agentic()` method in `mixin.py` (line 216) is explicitly documented as "the boundary where you enforce constraints." The `access` schema stage (proto_schema.py, line 247) serializes access rules that determine which endpoints are public. What is missing is the final step: embedding cache hints (`schema['cache']`) so that any boundary consumer -- CDN, reverse proxy, or N3TX's own middleware -- can make caching decisions without origin round-trips.

### Principle 2: Layered Caching with Fallthrough

Production CDN systems use multiple cache layers with different characteristics:

```
L1: Exact match       ~18% hit rate    <1ms      Hash(request)
L2: Semantic match     ~50% hit rate   ~20ms     Embedding similarity
L3: Plan template      Variable        ~50ms     Strategy reuse
L4: Full execution     0% (miss)       2-30s     Origin agent loop
```

Each layer is a filter: if it hits, the request never reaches the more expensive layer below. The combined effect is that 40-70% of requests never touch the LLM.

N3TX has no caching layers today. Every `run()` call in `mixin.py` goes directly to L4 (full execution). Adding L1 (exact match) is trivial -- hash the `(agent_addr, task, tools)` tuple, check a dict. L2 (semantic) requires embedding infrastructure but plugs in at the same point in `run()`.

### Principle 3: Event-Driven Invalidation

CDN caches are only useful if they serve fresh data. The standard approach is TTL-based expiry, but CDN best practices use **event-driven invalidation** (cache purge on write). N3TX already has this infrastructure: `ActorModel._publish_lifecycle()` sends `LIFECYCLE` TX events to registered subscribers after every create/update/delete. The ActivityPub adapter (`network_ap.py`) proves this works at scale.

A `NetworkEdge` adapter would subscribe to the same events and translate them to CDN purge API calls. The existing subscriber pattern (`Product._subscribers.append('edge')`) requires zero changes to ActorModel.

### Principle 4: Schema as Configuration Distribution

CDN systems distribute configuration (routing rules, WAF policies, TLS certs) from origin to edge nodes. In N3TX, the JSON Schema *is* the configuration. A schema contains:
- **Type information:** field types, required fields, constraints
- **Method signatures:** tool definitions with parameter types
- **Access rules:** who can read, create, update, delete
- **UI hints:** how to render each field

Distributing schemas to edge nodes gives them everything they need to validate requests (reject malformed payloads before they reach origin), make caching decisions (public reads are cacheable), and serve tool discovery responses (MCP `tools/list` from cache).

### Principle 5: Adapters, Not Infrastructure

The research is clear: for a framework-stage product, **buy the commodity layers and build only the integration**. Initial development accounts for less than 30% of total cost over an integration's lifetime (ThirstySprout). N3TX should not build CDN infrastructure. It should build `NetworkEdge` -- a 200-line adapter that maps LIFECYCLE events to CDN purge APIs and reads cache hints from schemas.

---

## 3. Our Architecture Through This Lens

When we re-examine N3TX through the CDN lens, several things stand out.

### Strengths We Have Not Articulated

**Self-describing responses are cache-key-rich.** Every `model_response()` call injects `$schema` (schema URL) and `$id` (instance URL). A CDN edge node can derive cache keys directly from these fields without parsing the request URL. This is JSON-LD-style linked data -- the response tells you how to cache it.

**Two-tier auth is already edge/origin split.** The auth interceptor in `auth_interceptor.py` handles schema (always public), list (compute SQL filter at boundary), and create (full check at boundary) at Tier 1. Only read/update/delete with OWNER rules need Tier 2 at the handler. This is *exactly* the edge-auth/origin-auth split CDN architectures use. We designed it for actor routing but it works unchanged for geographic distribution.

**The NetworkAdapter pattern is protocol-agnostic by design.** Adding `NetworkEdge` as a fifth adapter is architecturally identical to adding `NetworkAP` or `NetworkMCP`. The base class (`network_adapter.py`) provides `request()`/`stream()` correlation, `use()` interceptors, and Matrix-child registration. A CDN adapter inherits all of this.

### Current Architecture (Annotated with CDN Concepts)

```
Client Layer
  HTTP | MCP | ActivityPub | WebSocket
    |      |        |           |
    v      v        v           v
Network Adapter Layer                    <-- CDN BOUNDARY would go HERE
  NetworkAPI | NetworkMCP | NetworkAP | NetworkWS
    |             |            |          |
    |        [Interceptors: auth, rate limit]  <-- EDGE AUTH equivalent
    |             |            |          |
    v             v            v          v
Matrix Router                            <-- CDN ROUTING equivalent
    |
    +-- ActorModel (products, agents)    <-- ORIGIN SERVERS
    |     |
    |     +-- handler_crud()             <-- ORIGIN AUTH (Tier 2)
    |     +-- StorableMixin.CRUD()       <-- DATA LAYER
    |     +-- _publish_lifecycle()       <-- INVALIDATION EVENTS
    |
    +-- AgentMixin.run()                 <-- MOST EXPENSIVE OPERATION
          |
          +-- discover_tools()           <-- CACHEABLE (schemas don't change)
          +-- ai_agent.run()             <-- CACHEABLE (semantic similarity)
```

### Weaknesses That Become Obvious

**No caching at any layer.** Every request hits the origin, every agent call hits the LLM. The framework has all the metadata needed for caching (access rules, self-describing responses, lifecycle events) but no mechanism to use it.

**`discover_tools()` is stateless across calls.** Each `run()` invocation in `mixin.py` calls `discover_tools()` fresh (line 345), reading schemas from Matrix children. These schemas have not changed since startup. This is wasted work -- easily 50-100ms per agent call with multiple tool sources.

**No cache metadata in HTTP responses.** Schema endpoints return JSON with no `Cache-Control` headers. A CDN in front of N3TX today would cache nothing because the origin does not declare cacheability.

---

## 4. The Synthesis: Where Two Worlds Meet

### Integration Point A: Schema Pipeline + Cache Headers (The Foundation)

**Current state:** The schema pipeline (`proto_schema.py`) produces complete JSON Schemas through 7 composable stages. HTTP responses carry no cache metadata.

**Proposed state:** An 8th pipeline stage (`cache`) embeds cache hints in every schema. Route factories emit `Cache-Control` and `ETag` headers based on these hints.

```
BEFORE:
  GET /Product -> FastAPI -> schema pipeline -> JSON (no cache headers)
  CDN: nothing to cache

AFTER:
  GET /Product -> FastAPI -> schema pipeline (+ cache stage) -> JSON
     + Cache-Control: public, max-age=86400, s-maxage=86400
     + ETag: "a3f2b1..."
  CDN: caches for 24h, validates with ETag on revalidation

  Schema JSON now includes:
  {
    "cache": {
      "schema_ttl": 86400,
      "public": true,
      "list_ttl": 60,
      "item_ttl": 300,
      "invalidation": "lifecycle"
    }
  }
```

**Migration path:**
1. Add `cache` stage to `proto_schema.py` via `@schema_extension(after='access')`
2. Modify schema route in `network_api.py` to emit `Cache-Control` + `ETag`
3. Modify CRUD routes to emit `Cache-Control` based on `model.__access__`
4. Same changes in `routes_fastapi.py` for Level 1/2
5. Deploy any CDN (Cloudflare free tier is sufficient)

**Expected outcomes:**
- Schema endpoint: 99% cache hit rate, <20ms global latency (vs 200-500ms)
- Public read endpoints: 80%+ cache hit rate with 60s TTL
- Origin load reduction: 90%+ for schema requests, 50%+ for public reads

### Integration Point B: Semantic Cache in AgentMixin.run() (The Cost Cutter)

**Current state:** Every `run()` call goes through the full Pydantic AI loop.

```
run() --> discover_tools() --> Agent(llm, tools) --> ai_agent.run(task)
                                                         |
                                                   3-15 LLM calls
                                                   $0.05-1.00
                                                   5-30 seconds
```

**Proposed state:** A two-tier cache wraps the agent loop.

```
run() --> discover_tools_cached() --> exact_cache_check(task, tools)
              |                              |
              |                    hit: return cached (1ms)
              |                              |
              |                    miss: semantic_cache_check(task)
              |                              |
              |                    hit: return cached (20ms)
              |                              |
              |                    miss: Agent(llm, tools) --> ai_agent.run(task)
              |                                                    |
              |                                              store in both caches
              |                                              3-15 LLM calls
```

**The key change is in `mixin.py`, `run()` method, around line 383:**

```python
# ── Cache check (before LLM call) ──
import hashlib
cache_key = hashlib.sha256(
    f"{agent_addr}:{task}:{tuple(sorted(tools))}".encode()
).hexdigest()

cached = await _check_cache(cache_key)  # L1: exact match
if cached:
    cached['from_cache'] = 'exact'
    return cached

if config.AGENT_DEFAULTS.get('semantic_cache'):
    semantic_hit = await _semantic_check(task, agent_addr)  # L2
    if semantic_hit:
        semantic_hit['from_cache'] = 'semantic'
        return semantic_hit

# ── Normal execution ──
result = await ai_agent.run(task, **run_kwargs)

# ── Cache store ──
await _store_cache(cache_key, result_dict, task_embedding=...)
```

**Migration path:**
1. Add exact-match cache (in-memory dict or Redis) -- 1 day
2. Add `from_cache` field to agent response schema -- hours
3. Add semantic cache layer (requires embedding model) -- 1-2 weeks
4. Add `LIFECYCLE`-event-driven invalidation for related models -- 1 week
5. Add cache hit/miss metrics to `AgentActor` schema extension -- days

**Expected outcomes:**
- 50-65% reduction in LLM API costs
- Cache hits return in <50ms vs 5-30s for full execution
- Response includes `from_cache` field for transparency and debugging

### Integration Point C: NetworkEdge Adapter (The Invalidation Bridge)

**Current state:** No mechanism to notify external systems (CDN, cache) when data changes. LIFECYCLE events exist but only the AP adapter consumes them.

**Proposed state:** A `NetworkEdge` adapter subscribes to LIFECYCLE events and translates them to CDN purge API calls.

```
BEFORE:
  Product.update(1, {price: 99}) --> DB updated --> LIFECYCLE TX to AP adapter
                                                    (federation only)
  CDN: serves stale GET /products/1 until TTL expires

AFTER:
  Product.update(1, {price: 99}) --> DB updated --> LIFECYCLE TX to AP adapter
                                                    AND to NetworkEdge adapter
                                                          |
                                          NetworkEdge.LIFECYCLE()
                                                          |
                                          CDN purge: /products, /products/1
  CDN: immediately serves fresh data on next request
```

**The adapter follows the proven pattern from `network_ap.py`:**

```python
class NetworkEdge(NetworkAdapter, auto_register=False):
    _purge_fn: callable = PrivateAttr(default=None)

    def __init__(self, purge_fn=None, **kwargs):
        kwargs.setdefault('addr', 'edge')
        super().__init__(**kwargs)
        self._purge_fn = purge_fn or _default_purge

    def LIFECYCLE(self, data: dict, tx: TX):
        event = data.get('event', '')
        entity = data.get('entity', {})
        tablename = tx.source
        if event.startswith('after_'):
            self._purge_fn(f'/{tablename}')
            if entity.get('id'):
                self._purge_fn(f'/{tablename}/{entity["id"]}')
```

**Migration path:**
1. Create `network_edge.py` in `packages/n3tx-actors/src/n3tx_actors/api/`
2. Implement Cloudflare purge strategy (first provider)
3. Wire in `create_app()`: register adapter + subscribe storable models
4. Add generic HTTP purge strategy for other CDN providers
5. Document configuration (CDN API keys, zone IDs)

**Expected outcomes:**
- Edge cache freshness within seconds of data mutation
- No stale data in production CDN deployments
- Pluggable purge strategies for multiple CDN providers

---

## 5. Boundaries: Where This Does Not Apply

**Full edge inference is premature.** N3TX agents make 5-30 tool calls per invocation, each routed through Matrix to storable models backed by SQLite. Moving the agent loop to a CDN edge (Cloudflare Durable Object) means replicating the data layer. Durable Objects have a 10GB storage limit and different migration semantics than N3TX's `sqlite_migration.py`. The complexity is not justified until latency (not cost) is the bottleneck, and the workload is primarily stateless.

**Stateful agent conversations cannot be edge-distributed.** The `Thread` model stores conversation history at the origin. An agent in the middle of a multi-turn conversation must read and write this state. Distributing state across edge nodes creates consistency problems that N3TX's single-writer SQLite model does not address. Keep stateful agents at the origin.

**The actor system internals should not change.** Matrix routing (`matrix.py`), TX message format (`tx.py`), and the `use()` interceptor chain are foundational primitives. CDN integration sits *on top* of these -- as a new adapter, a new schema stage, and a cache layer in `run()`. Modifying the actor routing to be "CDN-aware" would violate the "transparent, not magical" philosophy and add complexity where none is needed.

**Write paths should never be cached.** POST, PUT, DELETE operations mutate state. Caching them (even with sophisticated invalidation) introduces consistency bugs. The `cache` schema stage should explicitly mark mutations as `Cache-Control: no-store`, and the `NetworkEdge` adapter should only handle invalidation, never caching of write responses.

---

## 6. A Path Forward

### Phase 1: Cache Infrastructure (Weeks 1-2)

**Goal:** Make N3TX CDN-compatible with immediate performance gains.

**Actions:**
- Add `Cache-Control` + `ETag` headers to schema routes in `network_api.py` and `routes_fastapi.py`
- Add `cache` stage to schema pipeline via `@schema_extension`
- Add tool discovery caching in `discover_tools()`
- Route LLM calls through AI Gateway (Cloudflare or equivalent)
- Deploy CDN in front of N3TX

**Success criteria:**
- [ ] Schema endpoint returns `Cache-Control: public, max-age=86400`
- [ ] CDN dashboard shows >95% cache hit rate on schema routes
- [ ] AI Gateway dashboard shows LLM call observability
- [ ] `discover_tools()` serves from cache on second call

**Decision gate:** Measure LLM costs and query patterns for 30 days. If LLM spend >$500/month AND >30% query similarity, proceed to Phase 2.

### Phase 2: Agent Caching (Weeks 3-6)

**Goal:** Cut LLM costs by 50%+ with semantic caching.

**Actions:**
- Implement exact-match agent cache in `AgentMixin.run()`
- Add semantic cache layer (embedding model + vector similarity)
- Create `NetworkEdge` adapter for LIFECYCLE-driven invalidation
- Wire invalidation to agent cache (purge cached responses when underlying data changes)

**Success criteria:**
- [ ] Agent cache hit rate >40% in production
- [ ] LLM cost reduction >50% vs Phase 1 baseline
- [ ] Cache invalidation fires within 5 seconds of data mutation
- [ ] No stale responses reported (zero false-positive cache hits)

**Decision gate:** Monitor cache accuracy for 30 days. If false-positive rate >2% OR stale response complaints emerge, tune similarity threshold up before expanding. If latency (not cost) becomes the bottleneck AND global user base exists, evaluate Phase 3.

### Phase 3: Edge Intelligence (Months 3-6, Contingent)

**Goal:** Sub-100ms agent responses for classified queries.

**Actions:**
- Deploy edge classifier for request triage
- Implement edge-side schema validation
- Evaluate Cloudflare Workers AI for lightweight edge agents
- Benchmark edge vs. origin for representative workloads

**Success criteria:**
- [ ] Edge classifier accuracy >95% on test set
- [ ] 40%+ of agent requests served from edge without origin
- [ ] P95 latency <200ms for edge-classified queries
- [ ] Operational runbook for distributed debugging

**Prerequisites (hard gates):**
- Monthly agent request volume >100,000
- Global user base with measurable latency variance >200ms
- At least 3 agent types that are primarily stateless
- Phase 2 operational for >90 days with stable cache metrics

---

## 7. Conclusion

The core insight from this analysis is not that N3TX should "add CDN support." It is that N3TX already possesses the architectural primitives -- schemas as contracts, lifecycle events as change notifications, interceptors as boundary checks, adapters as protocol bridges -- that CDN systems need. The gap is not structural; it is **declarative**. N3TX needs to declare its caching policy through the same schema mechanism that already declares access rules, UI hints, and method signatures.

The recommended immediate action is Phase 1: cache headers, schema pipeline extension, tool discovery caching, and AI gateway routing. These changes are small (days of work), safe (additive, no behavior changes), and immediately measurable (CDN hit rates, LLM cost dashboards). They provide the observability data needed to justify Phase 2.

The medium-term investment -- semantic caching in `AgentMixin.run()` -- is the highest-ROI optimization available. Research consistently shows 50-73% cost reduction for LLM workloads with repetitive queries. The implementation plugs into a single method in a single file (`mixin.py`, line 383) with no architectural changes.

The vision this enables: a N3TX application where defining a model with `__agent__ = True` gives you not just an LLM-powered agent, but an agent whose responses are automatically cached, whose cache is automatically invalidated on data changes, and whose cost scales sub-linearly with usage. The model remains the single source of truth -- for the schema, the API, the UI, the agent behavior, and now for the caching policy that makes it all economically viable at scale.

---

## References

**Research Documents:**
- `.traces/research/CDN-agents/01-industry-and-decisions.md` -- Industry landscape, cost modeling, decision framework
- `.traces/research/CDN-agents/02-our-stack-relevance.md` -- Architecture mapping, integration points, gap analysis

**Codebase Files:**
- `packages/n3tx-agents/src/n3tx_agents/mixin.py` -- AgentMixin: `run()` (line 268), `agentic()` (line 216)
- `packages/n3tx-agents/src/n3tx_agents/tools.py` -- `discover_tools()` (line 43), `ToolSpec`, tool function generation
- `packages/n3tx-agents/src/n3tx_agents/actor.py` -- AgentActor, stream event models
- `packages/n3tx-actors/src/n3tx_actors/api/network_adapter.py` -- NetworkAdapter base: `request()`, `stream()`, interceptors
- `packages/n3tx-actors/src/n3tx_actors/api/network_api.py` -- NetworkAPI: HTTP-to-TX bridge, route factories
- `packages/n3tx-actors/src/n3tx_actors/matrix.py` -- Matrix: root router, request-response correlation
- `packages/n3tx-core/src/n3tx_core/models/proto_schema.py` -- Schema pipeline: stages, extensions, `run_pipeline()`
- `packages/n3tx-core/src/n3tx_core/models/proto_model.py` -- ProtoModel: `schema()`, `model_response()`, mixin registry

**External Sources:**
- GPT Semantic Cache (arxiv 2411.05276v3) -- 68.8% hit rate at 0.8 threshold
- Agentic Plan Caching (NeurIPS 2025, arxiv 2506.14852) -- 50.31% cost reduction
- VentureBeat -- 40-60% query repetition in enterprise support bots
- Cloudflare AI Gateway -- Caching, rate limiting, observability for 20+ LLM providers
- Cloudflare Agents SDK -- Durable Objects, stateful edge agents, MCP support
- Helicone -- 18% exact-match cache hit rate in production
