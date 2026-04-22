# CDN-Backed Agents: N3TX Architecture Integration Analysis

**Research Angle:** How CDN capabilities map to N3TX's actor/agent architecture, where they plug in, what we already have, and what's missing.

**Date:** 2026-03-20 | **Audience:** Technical CEO + Engineering Leadership

---

## Executive Summary

N3TX's architecture is **surprisingly well-positioned** for CDN integration -- but not in the obvious way. The framework's existing abstractions (NetworkAdapter, schema pipeline, Matrix routing, TX message envelopes) were designed for protocol-agnostic distribution. Adding CDN capability is less about bolting on a cache layer and more about **treating the edge as another NetworkAdapter** in the existing adapter chain.

> **Key Insight:** N3TX already has four network adapters (HTTP, WebSocket, MCP, ActivityPub) registered as Matrix children. A fifth adapter -- `NetworkEdge` -- would fit the same pattern with zero architectural changes. The adapter translates between CDN edge protocols and TX messages, just like `NetworkAP` translates between ActivityPub and TX.

The real value isn't generic HTTP caching (any reverse proxy does that). It's **schema-aware edge intelligence**: distributing model schemas to edge nodes so they can validate requests, serve cached responses, and route agent tool calls without round-tripping to origin. This is the CDN capability that *only* a schema-driven framework like N3TX can offer.

**Bottom line:** Four concrete integration points exist today. Two require no new code (schema caching, response caching). Two require new adapters but follow existing patterns (edge agents, tool distribution). Estimated effort: 2-4 weeks for the first two, 6-8 weeks for the full stack.

---

## Table of Contents

1. [Architecture Mapping: N3TX Concepts to CDN Concepts](#-architecture-mapping)
2. [What We Already Have](#-what-we-already-have)
3. [Integration Points: Where CDN Plugs In](#-integration-points)
4. [Gap Analysis: What's Missing](#-gap-analysis)
5. [Concrete Integration Proposals](#-concrete-integration-proposals)
6. [Competitive Positioning](#-competitive-positioning)
7. [Implementation Roadmap](#-implementation-roadmap)
8. [Sources](#-sources)

---

## Architecture Mapping

**The CEO read:** N3TX's internal message-passing system maps neatly to CDN routing. Actors are like edge nodes. TX messages are like edge-routed requests. The Matrix router is like a CDN's routing logic. This isn't coincidence -- both systems solve the same problem: routing requests to the right handler through an intermediary layer.

**The engineering read:** Let's trace the mapping precisely.

### Concept-by-Concept Mapping

| N3TX Concept | CDN Equivalent | Why the Mapping Works |
|---|---|---|
| **Actor address** (`products`, `agents/1`) | Edge node / PoP identifier | Both are addressable endpoints in a routing hierarchy |
| **TX message** (`TX(name='get', target='products')`) | Edge-routed HTTP request | Both carry: action, target, payload, metadata, correlation ID |
| **Matrix router** (`matrix.inbox(tx)`) | CDN routing logic (anycast, geo-routing) | Both resolve target from address and dispatch to handler |
| **NetworkAdapter** (`NetworkAPI`, `NetworkMCP`) | CDN protocol adapter (HTTP/2, QUIC, WS) | Both translate external protocols to internal routing |
| **Interceptors** (`adapter.use(auth, on='request')`) | Edge middleware (WAF, auth, rate limiting) | Both are composable request/response transformers |
| **Schema pipeline** (`proto_schema.run_pipeline()`) | Schema propagation / configuration distribution | Both distribute metadata that governs behavior |
| **`model_response()`** (`$schema`, `$id` injection) | Cache key derivation + self-describing responses | Both enable cache-aware, self-describing payloads |
| **ActivityPub adapter** (`NetworkAP`) | Federation / multi-origin CDN | Both distribute content across independent nodes |
| **Two-tier auth** (Tier 1 interceptor + Tier 2 handler) | Edge auth + origin auth | Both split fast checks at boundary from deep checks at origin |

### Data Flow Comparison

**Current N3TX Level 3 request flow:**

```
Client  ----HTTP---->  NetworkAPI  --TX-->  Matrix  --TX-->  ActorModel
                           |                  |                  |
                       Tier 1 Auth        Route by           Tier 2 Auth
                       (interceptor)      address            (handler)
                           |                  |                  |
                       <---TX----  <---TX----  <---TX----
                       (response)  (relay)     (reply)
```

**Proposed CDN-enhanced flow:**

```
Client  ----HTTP---->  CDN Edge  ----HTTP---->  NetworkAPI  --TX-->  Matrix
                          |                        |                   |
                      Edge Cache               Tier 1 Auth          Route
                      Schema Validation        (interceptor)        by addr
                      Rate Limiting                |                   |
                          |                    <---TX----          ActorModel
                      [cache hit?]             (response)             |
                      Yes: return                                  Tier 2
                      No: forward                                  (handler)
```

**With `NetworkEdge` adapter (full integration):**

```
Client  ----HTTP---->  CDN Edge (NetworkEdge adapter)  --TX-->  Matrix
                              |                                    |
                          Edge Schema Cache                    Route
                          Request Validation                   by addr
                          Tool Discovery Cache                    |
                          Agent Response Cache              ActorModel
                              |                                |
                          [cache hit?]                      Handler
                          Yes: TX.reply() locally              |
                          No: forward TX to origin          TX.reply()
```

> **Key Insight:** The `NetworkEdge` adapter would be the **first adapter that can short-circuit** the TX chain. Today, all adapters (API, MCP, AP, WS) forward every request to the Matrix. An edge adapter would resolve some requests locally from cache, only forwarding cache misses. This is architecturally novel for N3TX but fits cleanly into the existing `request()` / `inbox()` correlation pattern.

---

## What We Already Have

N3TX's existing patterns provide **four foundational capabilities** that CDN integration can build on. These aren't aspirational -- they're shipping code.

### 1. NetworkAdapter Abstraction (Pluggable Transport)

**File:** `/workspace/packages/n3tx-actors/src/n3tx_actors/api/network_adapter.py`

The `NetworkAdapter` base class is the single most important integration point. Every external protocol -- HTTP, WebSocket, MCP, ActivityPub -- is just a NetworkAdapter registered as a Matrix child. Adding a CDN edge adapter follows the exact same pattern:

```python
class NetworkAdapter(Actor, auto_register=False):
    """Base for actors that bridge external protocols to the Matrix."""

    async def request(self, tx: TX, timeout: float = 30.0) -> TX:
        """Send TX, await correlated response via asyncio.Future."""
        # Run 'request' interceptors (e.g., auth, rate limiting)
        interceptors = Actor._get_interceptors(self, 'request')
        if interceptors:
            tx = await Actor._run_interceptors(interceptors, tx)
            if tx.is_error:
                return tx  # Rejected before entering actor system
        # ...send and correlate...
```

**What this means for CDN:** A `NetworkEdge` adapter would subclass `NetworkAdapter`, implement `request()` to check an edge cache first, and only fall through to `super().request()` on cache miss. The interceptor chain (`use()`) already supports composable middleware -- adding cache-check as an interceptor requires **zero base class changes**.

**Existing adapters as reference:**

| Adapter | File | Lines | What It Translates |
|---|---|---|---|
| `NetworkAPI` | `network_api.py` | 587 | HTTP REST <--> TX |
| `NetworkMCP` | `network_mcp.py` | ~400 | JSON-RPC 2.0 <--> TX |
| `NetworkAP` | `network_ap.py` | ~300 | ActivityPub <--> TX |
| `NetworkWebSocket` | `network_ws.py` | ~200 | WebSocket <--> TX |

### 2. Schema as Cacheable Contract

**File:** `/workspace/packages/n3tx-core/src/n3tx_core/models/proto_schema.py`

The JSON Schema returned by `GET /{ClassName}` is **inherently CDN-friendly**:

- **Immutable per deployment** -- schemas don't change between deploys. A schema for `Product` is the same for every request until the code changes.
- **Self-describing** -- every response carries `$schema` and `$id` pointing back to its schema URL. CDN edge nodes can validate responses against cached schemas.
- **Composable pipeline** -- the schema pipeline (`base -> strip_hidden -> methods -> defs -> access -> ui -> metadata`) is already modular. Adding a `cache_hints` stage is one decorator:

```python
@schema_extension(after='metadata')
def cache_hints(cls, schema: dict) -> dict:
    """Add CDN cache control hints to schema."""
    schema['cache'] = {
        'schema_ttl': 86400,      # Schema itself: 24h (immutable per deploy)
        'list_ttl': 60,           # List responses: 1 min
        'item_ttl': 300,          # Individual items: 5 min
        'invalidation': 'event',  # Use lifecycle events for invalidation
    }
    return schema
```

**Schema endpoint response example** (already cacheable):
```json
{
    "$schema": "http://localhost:5000/Schema",
    "$id": "http://localhost:5000/Product",
    "properties": { "name": {"type": "string"}, "price": {"type": "number"} },
    "methods": { "like": {"route": "/like", "methods": ["POST"]} },
    "access": { "read": "anyone", "create": "authenticated" },
    "cache": { "schema_ttl": 86400, "list_ttl": 60 }
}
```

### 3. ActivityPub Adapter (Federation = Distribution)

**File:** `/workspace/packages/n3tx-actors/src/n3tx_actors/api/network_ap.py`

The AP adapter is proof that N3TX already handles **distributed content delivery**. It:

- Receives lifecycle events (`LIFECYCLE` TX) from ActorModel after create/update/delete
- Converts events to ActivityPub Activities stored in an outbox
- Handles inbound federation (other servers pushing content)
- Manages followers and subscriptions per actor

**This is conceptually identical to CDN cache invalidation.** When a Product is updated, the AP adapter publishes a `Update` activity to followers. A CDN adapter would publish a cache invalidation to edge nodes. The subscription model (`Product._subscribers.append('ap')`) works unchanged for a CDN adapter.

```python
# Current: AP adapter receives lifecycle events
Product._subscribers.append('ap')

# Future: CDN adapter receives same lifecycle events
Product._subscribers.append('edge')

# Both receive:
# TX(name='LIFECYCLE', source='products', target='edge',
#    data={'event': 'after_update', 'entity': {...}})
```

### 4. Two-Tier Auth (Already Edge-Ready)

**File:** `/workspace/packages/n3tx-actors/src/n3tx_actors/api/auth_interceptor.py`

The two-tier authorization model was designed for **exactly the edge/origin split**:

| Tier | Where | What It Checks | CDN Equivalent |
|---|---|---|---|
| **Tier 1** | `NetworkAPI.request()` interceptor | Fast gate: schema pass-through, list sql_filter, create/read identity check | **Edge auth**: JWT validation, rate limiting, basic access checks |
| **Tier 2** | `ActorModel.handler_crud()` | Full ABAC with resource instance: OWNER checks | **Origin auth**: resource-level authorization |

The split exists because **OWNER-based rules need the resource instance**, which only the origin has. This is the same constraint CDN architectures face: the edge can validate tokens and check roles, but ownership checks require the resource. N3TX already solved this problem.

```python
# auth_interceptor.py already handles the edge/origin split:

async def auth_interceptor(tx: TX) -> TX:
    if action == 'schema':
        return tx  # Always public -- CDN can cache forever

    if action == 'list':
        # Compute SQL filter at boundary -- CDN can cache by filter
        tx.meta['sql_filter'] = _resolver.sql_filter_for(ctx)
        return tx

    if action == 'create':
        # Full check at boundary -- no resource needed
        rule = _resolver.resolve_rule(model_cls, 'create')
        if not rule.evaluate(ctx):
            return _deny(tx, user)
        return tx

    # read/update/delete: identity gate only
    # Full OWNER check at origin (Tier 2)
    return tx
```

### 5. Matrix Request-Response Correlation

**File:** `/workspace/packages/n3tx-actors/src/n3tx_actors/matrix.py`

Matrix's `request()` method uses **asyncio.Future keyed by TX uuid** for request-response correlation. This is the same pattern CDN edge nodes use for origin-pull:

```python
async def request(self, tx: TX, timeout: float = 30.0) -> TX:
    future = loop.create_future()
    self._pending[tx.uuid] = future
    await self.send(tx)
    return await asyncio.wait_for(future, timeout=timeout)
```

An edge adapter could use this same pattern: send a TX to the origin Matrix, await the correlated response, cache it, and return it. The correlation mechanism is protocol-agnostic.

---

## Integration Points

Where specifically does CDN capability plug into the N3TX stack? There are **five concrete integration points**, ordered by complexity.

### Integration Point 1: Schema Caching (Zero Code Required)

**Complexity:** None -- pure infrastructure configuration

Schema endpoints (`GET /{ClassName}`) are **read-only, deterministic, and identical for all users**. A standard CDN or reverse proxy caches them perfectly:

```
GET /Product  ->  CDN cache hit (TTL 24h)  ->  return cached JSON Schema
GET /products ->  CDN passes through to origin  ->  origin queries DB
```

**Cache headers already set** (in `_add_streaming_handler` in `network_api.py`, line 518):
```python
headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
```

For schema routes, we'd change this to:
```python
# Schema routes: cache aggressively
headers={"Cache-Control": "public, max-age=86400, s-maxage=86400"}

# Data routes: no cache (or short TTL)
headers={"Cache-Control": "private, no-cache"}
```

**Impact:** Schema fetch is the first request every frontend makes (`N3TX.SCHEMA()` triggers `GET /Product`). Caching it at the edge eliminates the most common request. For a global deployment, this means **sub-50ms schema loads** instead of 200-500ms origin round-trips.

### Integration Point 2: Read Response Caching (Minimal Code)

**Complexity:** Low -- add Cache-Control headers + vary-by-user logic

List and item responses can be cached at the edge with appropriate vary headers:

| Endpoint | Cacheability | Cache Key | TTL |
|---|---|---|---|
| `GET /{ClassName}` (schema) | **Fully cacheable** | URL | 24h |
| `GET /{tablename}` (list, public) | Cacheable if `access.read == ANYONE` | URL + query params | 1-5 min |
| `GET /{tablename}/{id}` (item, public) | Cacheable if `access.read == ANYONE` | URL | 5-15 min |
| `GET /{tablename}` (list, authenticated) | **Not cacheable** at edge | -- | -- |
| `POST/PUT/DELETE` (mutations) | **Never cacheable** | -- | -- |
| `POST /{tablename}/{id}/agentic` (agent) | Conditionally cacheable | URL + task hash | Varies |

The schema already carries access rules:
```json
{ "access": { "read": "anyone", "create": "authenticated" } }
```

An edge node can read `access.read == "anyone"` from the cached schema and **know which GET endpoints are publicly cacheable without asking the origin**. This is schema-driven CDN configuration -- unique to N3TX.

### Integration Point 3: Schema Pipeline Extension

**Complexity:** Low -- add a new pipeline stage

**File:** `/workspace/packages/n3tx-core/src/n3tx_core/models/proto_schema.py`

The schema pipeline already supports extensions via `@schema_extension`. A CDN-specific stage would add cache control metadata to every model's schema:

```python
from n3tx_core.models.proto_schema import schema_extension

@schema_extension(after='access')
def cache(cls, schema: dict) -> dict:
    """Add edge cache hints derived from model access rules."""
    access = schema.get('access', {})

    cache_config = {}

    # Schema itself: always cacheable
    cache_config['schema_ttl'] = 86400

    # Read responses: cacheable only if read is public
    if access.get('read') == 'anyone':
        cache_config['list_ttl'] = getattr(cls, '__cache_list_ttl__', 60)
        cache_config['item_ttl'] = getattr(cls, '__cache_item_ttl__', 300)
        cache_config['public'] = True
    else:
        cache_config['public'] = False

    # Invalidation strategy
    cache_config['invalidation'] = 'lifecycle'  # Uses LIFECYCLE TX events

    schema['cache'] = cache_config
    return schema
```

The pipeline after this stage:
```
base -> strip_hidden -> methods -> defs -> access -> cache -> ui -> metadata
```

### Integration Point 4: Lifecycle Event-Driven Invalidation

**Complexity:** Medium -- new adapter class

**File reference:** `/workspace/packages/n3tx-actors/src/n3tx_actors/api/network_ap.py` (same pattern)

The ActivityPub adapter already receives `LIFECYCLE` events from ActorModel. A CDN invalidation adapter would follow the same subscription pattern:

```python
class NetworkEdge(NetworkAdapter, auto_register=False):
    """CDN edge cache invalidation adapter."""

    _edge_api: str = PrivateAttr(default='')

    def __init__(self, edge_api: str = '', **kwargs):
        kwargs.setdefault('addr', 'edge')
        super().__init__(**kwargs)
        self._edge_api = edge_api

    def LIFECYCLE(self, data: dict, tx: TX):
        """Invalidate edge cache on data mutation."""
        event = data.get('event', '')
        entity = data.get('entity', {})
        tablename = tx.source  # e.g., 'products'

        if event in ('after_create', 'after_update', 'after_delete'):
            # Purge specific item
            item_id = entity.get('id')
            if item_id:
                self._purge(f'/{tablename}/{item_id}')

            # Purge list (stale after any mutation)
            self._purge(f'/{tablename}')

    def _purge(self, path: str):
        """Send cache purge request to CDN API."""
        # Cloudflare: POST /zones/{zone}/purge_cache
        # Fastly: POST /service/{id}/purge/{key}
        # Generic: configurable per CDN provider
        ...
```

**Subscription wiring** (in `create_app` or manually):
```python
edge = NetworkEdge(edge_api='https://api.cloudflare.com/...')
matrix.register(edge)

# Subscribe all storable models to edge invalidation
for model in registered_models.values():
    if hasattr(model, '_subscribers'):
        model._subscribers.append('edge')
```

### Integration Point 5: Agent Response Caching (Semantic Cache)

**Complexity:** High -- requires semantic similarity matching

Agent responses are the **most expensive** content N3TX produces. A single `POST /agents/1/agentic` call can involve 5-30 LLM API calls, each costing $0.01-0.10. Caching deterministic agent queries saves both latency and money.

The challenge: agent queries are **natural language**, so exact-match caching has low hit rates. [Semantic caching](https://github.com/zilliztech/GPTCache) uses embeddings to match similar queries, achieving **2-10x speedups** and **over 92% hit ratios** for equivalent queries ([GPTCache paper](https://arxiv.org/html/2411.05276v1)).

**Where this plugs in:** The `AgentMixin.run()` method in `/workspace/packages/n3tx-agents/src/n3tx_agents/mixin.py` is the single entry point for all agent execution. A cache check wraps naturally:

```python
# In AgentMixin.run() (mixin.py, around line 383)
# Before: result = await ai_agent.run(task, **run_kwargs)

# After (with semantic cache):
cache_key = _semantic_hash(prompt, task, tools)
cached = await self._check_agent_cache(cache_key)
if cached:
    return cached

result = await ai_agent.run(task, **run_kwargs)
await self._store_agent_cache(cache_key, result)
```

---

## Gap Analysis

What's **missing** from N3TX for full CDN-backed agent deployment? Four categories of gaps, ordered by severity.

### Gap 1: No Cache Metadata in Responses (Severity: Low)

**Current state:** `model_response()` injects `$schema` and `$id` but no `Cache-Control` or `ETag` headers. The streaming handler explicitly sets `Cache-Control: no-cache`.

**What's needed:** Per-model cache control based on access rules. Models with `access.read == ANYONE` should emit `Cache-Control: public, max-age=60`. Models with `access.read == AUTHENTICATED` should emit `Cache-Control: private, no-cache`.

**Effort:** 1-2 days. Add a response header middleware in `routes_fastapi.py` and `network_api.py` that reads `model.__access__` and sets appropriate headers.

### Gap 2: No Cache Invalidation Mechanism (Severity: Medium)

**Current state:** The `LIFECYCLE` event system exists (AP adapter uses it) but no CDN-focused consumer. Cache invalidation requires:

1. A `NetworkEdge` adapter that subscribes to LIFECYCLE events
2. CDN provider-specific purge API integration
3. Surrogate key / tag-based invalidation for efficient purging

**Effort:** 1-2 weeks. The adapter pattern is well-established; the work is in CDN provider integration.

### Gap 3: No Edge-Side Schema Validation (Severity: Medium)

**Current state:** Request validation happens at the origin (FastAPI/Pydantic). Edge nodes receive raw requests and forward them blindly.

**What's needed:** Edge nodes cache model schemas and use them to validate requests before forwarding. This rejects malformed requests at the edge, saving origin resources.

**Why this matters for agents:** Agent tool calls (`POST /agents/1/agentic {"task": "..."}`) carry complex payloads. Validating the payload structure at the edge catches errors 100-300ms sooner.

**Effort:** 2-3 weeks. Requires edge-side JSON Schema validation (standard libraries exist for every edge runtime: Cloudflare Workers, Deno Deploy, Lambda@Edge).

### Gap 4: Distributed Agent State (Severity: High)

**Current state:** Agent state (conversation history, tool results, intermediate reasoning) lives in the origin's SQLite database. The `Thread` model stores conversation history. The `AgentMixin.run()` method reads/writes thread state via TX messages to the `threads` actor.

**What's needed for edge agents:**

| State Type | Current Location | Edge Requirement |
|---|---|---|
| Thread history | Origin SQLite | Replicated to edge (read) or write-through to origin |
| Agent config | Origin SQLite (AgentActor fields) | Cached at edge (immutable per session) |
| Tool definitions | Discovered from Matrix at runtime | Cached at edge from schema |
| In-flight reasoning | In-memory (Pydantic AI agent loop) | Must run at origin or on edge with local LLM |
| Conversation context | In-memory during `run()` | Not distributable (LLM context window) |

The **hard problem** is in-flight reasoning: an agent in the middle of a 10-step tool-calling loop cannot be migrated between nodes. This is a fundamental constraint of LLM agent architectures, not specific to N3TX.

**Effort:** 4-8 weeks for partial solution (edge caching of config + tools, origin for reasoning). Full edge agents require edge LLM inference (see Cloudflare Workers AI below).

### Gap 5: Auth Token Propagation Through CDN (Severity: Medium)

**Current state:** JWT tokens are passed via `x-access-token` header. The `JWTAuthMiddleware` validates them at the origin. `_get_user(request)` extracts user dict from `request.state`.

**What's needed:** Edge nodes need to validate JWTs without calling the origin. This requires:

1. JWT public key distribution to edge nodes
2. Token validation at the edge (standard pattern; Cloudflare Workers, Lambda@Edge all support this)
3. Passing the validated user identity to origin requests (for Tier 2 auth)

**Effort:** 1 week. Standard JWT edge validation pattern; well-documented for every CDN provider.

### Gap Summary Table

| Gap | Severity | Effort | Blocking? |
|---|---|---|---|
| No cache metadata in responses | Low | 1-2 days | No |
| No cache invalidation mechanism | Medium | 1-2 weeks | No (stale cache acceptable short-term) |
| No edge-side schema validation | Medium | 2-3 weeks | No (nice-to-have) |
| Distributed agent state | High | 4-8 weeks | Yes (for edge agents) |
| Auth token propagation | Medium | 1 week | No (standard pattern) |

---

## Concrete Integration Proposals

Four specific ways to integrate CDN capabilities into N3TX agents, ordered by ROI.

### Proposal 1: Schema CDN -- Cache and Distribute Model Schemas Globally

**Business case:** Schema fetches are the **#1 API call** in any N3TX app. Every page load starts with `GET /Product` (or similar). Caching schemas at CDN edge eliminates the most common request.

**Technical design:**

```
                          CDN Edge PoP (Cloudflare / Fastly / CloudFront)
                                |
              [GET /Product] ---+--- [Cache Hit?]
                                |       |
                              Yes      No
                                |       |
                          Return cached  Forward to origin
                          schema (TTL    |
                          24h, ETag)     Origin returns schema
                                         + Cache-Control: public, max-age=86400
                                         + ETag: sha256(schema_json)
                                |
                          Store in edge cache
```

**Implementation:**

1. **Schema route headers** (in `_register_schema_route` in `network_api.py`):
```python
@router.get(f"/{class_name}", tags=[tag])
async def get_schema(request: Request, _addr=addr, _cls=model_class):
    response = await api_adapter.request(
        TX(name='schema', source=api_adapter.addr, target=_addr),
        timeout=10.0,
    )
    result = _response_or_raise(response)

    # CDN cache headers
    import hashlib, json
    etag = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()[:16]

    from fastapi.responses import JSONResponse
    return JSONResponse(
        content=result,
        headers={
            "Cache-Control": "public, max-age=86400, s-maxage=86400",
            "ETag": f'"{etag}"',
            "Vary": "Accept",
        }
    )
```

2. **Schema pipeline extension** (new file: `packages/n3tx-core/src/n3tx_core/models/cache_schema.py`):
```python
@schema_extension(after='access')
def cache(cls, schema: dict) -> dict:
    access = schema.get('access', {})
    schema['cache'] = {
        'schema_ttl': 86400,
        'public_reads': access.get('read') == 'anyone',
        'list_ttl': 60 if access.get('read') == 'anyone' else 0,
        'item_ttl': 300 if access.get('read') == 'anyone' else 0,
    }
    return schema
```

**Metrics:**
- Schema size: typically **2-10 KB** per model (highly compressible)
- CDN edge latency: **5-20ms** (vs 100-500ms origin)
- Cache hit ratio: **~99%** (schemas rarely change)
- Cost savings: eliminates the most common API call

> **Key Insight:** This is the **lowest-effort, highest-impact** CDN integration. A CDN in front of N3TX with proper `Cache-Control` headers on schema routes provides immediate global performance gains with zero framework changes. The schema pipeline extension makes it self-documenting.

---

### Proposal 2: Agent Response CDN -- Cache Deterministic Agent Outputs

**Business case:** Agent calls are the **most expensive** operation in N3TX. A single `agentic()` call costs $0.01-$1.00 in LLM API fees and takes 2-30 seconds. Identical or similar queries happen repeatedly (e.g., "summarize this grant", "list renewable energy grants"). Caching saves both money and time.

**How it works:**

```
POST /agents/1/agentic {"task": "Find grants about renewable energy"}
                |
        [Semantic Cache Check]
                |
    Cache Hit (similarity > 0.95)     Cache Miss
                |                          |
    Return cached response          Run agent loop
    (latency: ~50ms)               (latency: 5-30s, cost: $0.01-1.00)
                                        |
                                  Store response + embedding
                                  in semantic cache
```

**Technical design:**

Two layers of caching, each with different characteristics:

| Layer | Match Strategy | Hit Rate | Latency | Storage |
|---|---|---|---|---|
| **Exact match** | Hash of (agent_id, task, tools) | Low (5-15%) | ~1ms | Redis / edge KV |
| **Semantic match** | Embedding cosine similarity > 0.95 | High (40-70%) | ~20ms | Vector DB (edge-near) |

**Integration with AgentMixin:**

The `run()` method in `mixin.py` (line 269) is the single point where all agent execution happens. A cache wrapper:

```python
# New method on AgentMixin
@fullmethod
async def run(target, task: str, prompt: str, tools: list, **kwargs) -> dict:
    # ... existing config resolution ...

    # ── Cache check (exact match) ──
    cache_key = f"agent:{agent_addr}:{hash((task, tuple(tools)))}"
    cached = await _check_cache(cache_key)
    if cached:
        cached['from_cache'] = True
        return cached

    # ── Cache check (semantic match, if enabled) ──
    if config.AGENT_DEFAULTS.get('semantic_cache'):
        semantic_result = await _semantic_cache_lookup(task, agent_addr)
        if semantic_result:
            semantic_result['from_cache'] = True
            semantic_result['cache_type'] = 'semantic'
            return semantic_result

    # ── Normal agent execution ──
    result = await ai_agent.run(task, **run_kwargs)

    # ── Cache store ──
    await _store_cache(cache_key, result, ttl=config.AGENT_DEFAULTS.get('cache_ttl', 3600))

    return result_dict
```

**Performance reference:** According to [GPTCache benchmarks](https://arxiv.org/html/2411.05276v1), semantic caching delivers **2-10x response speed improvement** when the cache is hit, with ensemble embedding approaches achieving **over 92% hit ratios** for semantically equivalent queries. [AWS reports](https://aws.amazon.com/blogs/database/optimize-llm-response-costs-and-latency-with-effective-caching/) that organizations using semantic caching see LLM API cost reductions of **40-60%**.

> **Warning:** Semantic caching introduces **stale response risk**. If the underlying data changes (new grants added), cached agent responses about "current grants" become stale. The `LIFECYCLE` event system can trigger cache invalidation when the data the agent operates on changes -- but this requires tracking which data each agent query touched, which is complex.

---

### Proposal 3: Edge Agent Workers -- Run Lightweight Agent Logic at the Edge

**Business case:** For simple agent queries (classification, routing, FAQ), a small LLM at the edge can respond in **under 500ms** without hitting the origin. For complex queries, the edge worker triages and routes to the appropriate origin agent.

**This is the most architecturally interesting proposal** because it leverages N3TX's `NetworkAdapter` pattern to create a new kind of adapter: one that runs (limited) agent logic locally.

**Architecture:**

```
Client  ---->  CDN Edge (NetworkEdge + edge LLM)
                    |
          [Simple query?]  ----Yes---->  Edge LLM responds
                    |                     (Cloudflare Workers AI,
          No (complex)                    50+ models available)
                    |
          Forward to origin  ---->  Full N3TX agent loop
                    |                     (origin LLM, full tools,
                    |                      full state)
          <---- stream response ----
```

**Reference platform:** [Cloudflare Agents](https://developers.cloudflare.com/agents/) runs on Durable Objects -- **stateful micro-servers with their own SQL database, WebSocket connections, and scheduling**. Each agent runs on a Durable Object that scales to tens of millions of instances ([Cloudflare docs](https://developers.cloudflare.com/agents/)).

Cloudflare Workers AI now supports [large models including Kimi K2.5](https://blog.cloudflare.com/workers-ai-large-models/) with **256k context window, multi-turn tool calling, vision inputs, and structured outputs** -- all at the edge.

**N3TX integration sketch:**

```python
class EdgeAgentWorker(NetworkAdapter, auto_register=False):
    """Lightweight agent that runs at the CDN edge.

    Handles simple queries locally (classification, FAQ, routing).
    Forwards complex queries to origin for full agent execution.
    """

    _edge_llm: str = PrivateAttr(default='')  # Edge model ID
    _tool_cache: dict = PrivateAttr(default_factory=dict)  # Cached tool specs
    _schema_cache: dict = PrivateAttr(default_factory=dict)  # Cached schemas

    async def request(self, tx: TX, timeout: float = 30.0) -> TX:
        """Handle agent requests at the edge when possible."""
        if tx.name != 'agentic' and tx.name != 'run':
            return await super().request(tx, timeout)  # Forward non-agent

        task = tx.data.get('task', '')
        complexity = await self._estimate_complexity(task)

        if complexity == 'simple':
            return await self._edge_run(tx)  # Local edge LLM
        else:
            return await super().request(tx, timeout)  # Forward to origin

    async def _estimate_complexity(self, task: str) -> str:
        """Classify query complexity using a tiny model at the edge."""
        # Use a small classifier (e.g., distilbert) to decide:
        # "simple" = FAQ, classification, lookup
        # "complex" = multi-step reasoning, tool calling, data mutation
        ...

    async def _edge_run(self, tx: TX) -> TX:
        """Run a simplified agent loop at the edge."""
        # Use cached tool specs (read-only tools only)
        # Use edge LLM (smaller, faster)
        # Return response as TX.reply()
        ...
```

**Metrics:**
- Edge LLM latency: **100-500ms** (vs 2-30s for origin)
- Cloudflare Workers AI pricing: **pay-per-request, no idle cost** ([Cloudflare pricing](https://workers.cloudflare.com/product/workers-ai/))
- Suitable for: **40-60% of agent queries** (classification, FAQ, simple lookups)
- Not suitable for: multi-step tool calling, data mutations, complex reasoning

---

### Proposal 4: Tool Distribution Network -- Propagate Tool Definitions to Edge

**Business case:** Tool discovery (`discover_tools()` in `tools.py`) currently runs at the origin for every agent invocation. It reads schemas from Matrix children and builds `ToolSpec` lists. For a stable set of models, these specs are **identical across invocations**.

Distributing tool definitions to edge nodes enables:
1. **Edge-side tool routing** -- edge nodes know which tools exist and can validate tool call payloads
2. **MCP at the edge** -- edge nodes serve MCP `tools/list` responses from cache
3. **Agent pre-planning** -- edge LLMs can plan tool usage using cached specs

**Technical design:**

The `discover_tools()` function in `/workspace/packages/n3tx-agents/src/n3tx_agents/tools.py` (line 43) reads schemas synchronously:

```python
def discover_tools(actor_addrs: list, root, caller_addr: str = None) -> list[ToolSpec]:
    for addr in actor_addrs:
        child = children.get(addr)
        cls = child if isinstance(child, type) else child.__class__
        schema = cls.schema()
        # ... build ToolSpec from schema ...
```

**Caching this is straightforward:**

```python
_tool_cache: dict[str, list[ToolSpec]] = {}

def discover_tools_cached(actor_addrs: list, root, caller_addr: str = None) -> list[ToolSpec]:
    cache_key = tuple(sorted(actor_addrs))
    if cache_key in _tool_cache:
        return _tool_cache[cache_key]

    specs = discover_tools(actor_addrs, root, caller_addr)
    _tool_cache[cache_key] = specs
    return specs

def invalidate_tool_cache():
    """Called on model registration or schema change."""
    _tool_cache.clear()
```

For edge distribution, the tool specs are serialized as part of the schema and served via the schema CDN (Proposal 1). An edge node caching `GET /Product` already has the tool specs embedded in `schema.methods`.

**MCP at the edge:** The `NetworkMCP` adapter's `tools/list` response is a direct serialization of discovered tool specs. Caching this at the edge means AI clients (Claude Desktop, etc.) get tool lists from the nearest edge node:

```
Claude Desktop  --->  CDN Edge  --->  [MCP tools/list cached]  --->  Return tool specs
                                                                     (TTL: 1h)
```

---

## Competitive Positioning

How do other frameworks handle CDN/edge distribution for AI agents?

### Framework Comparison

| Feature | N3TX (proposed) | LangChain/LangGraph | CrewAI | Cloudflare Agents | Vercel AI SDK |
|---|---|---|---|---|---|
| **Schema-driven caching** | Native (schema carries cache hints) | No (manual) | No | No | No |
| **Edge agent routing** | Via NetworkEdge adapter | No native support | No native support | **Native** (Durable Objects) | **Native** (Edge Functions) |
| **Tool discovery caching** | Schema-embedded tools | No native caching | [Known caching issues](https://github.com/crewAIInc/crewAI/issues/886) | No (tools defined in code) | No (tools defined in code) |
| **Semantic caching** | Pluggable (via AgentMixin) | Via GPTCache integration | Planned | No native support | Via middleware |
| **Cache invalidation** | LIFECYCLE events (existing) | Manual | Manual | Durable Object state | Revalidation API |
| **Multi-protocol edge** | HTTP + MCP + AP + WS (all adaptable) | HTTP only | HTTP only | HTTP + WS + RPC | HTTP + WS |
| **Auth at edge** | Two-tier (already split) | Manual | Manual | Workers auth | Edge middleware |
| **Streaming at edge** | SSE + WS (existing) | SSE | No streaming | WS (Durable Objects) | SSE (native) |

### Key Differentiators

**N3TX's unique advantage is schema-driven edge intelligence.** No other agent framework carries enough metadata in its schemas to enable edge-side decision making:

1. **Access rules in schema** -- edge knows which endpoints are public (cacheable) vs authenticated
2. **Method signatures in schema** -- edge can validate tool call payloads before forwarding
3. **Cache hints in schema** (proposed) -- edge reads TTL and invalidation strategy from the schema itself
4. **Self-describing responses** (`$schema`, `$id`) -- edge can validate and categorize responses

> **Key Insight:** Cloudflare Agents and Vercel AI SDK have **better edge runtime support** (Durable Objects, Edge Functions). N3TX has **better metadata for edge decision-making** (schema-driven caching, access rules, tool specs). The ideal architecture combines N3TX's schema intelligence with a modern edge runtime.

### What N3TX Can Learn From Others

| Platform | Lesson | Applicability to N3TX |
|---|---|---|
| **Cloudflare Agents** | Durable Objects provide **stateful edge agents** with built-in SQLite, WebSocket, and scheduling | N3TX's Actor + SQLite pattern is architecturally identical; edge deployment would need a JS/WASM runtime |
| **Vercel AI SDK** | [SSE as standard streaming protocol](https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol) with built-in reconnect and cache handling | N3TX already uses SSE; could adopt Vercel's reconnect/keep-alive patterns |
| **MCP ecosystem** | [Cloudflare hosted MCP servers](https://blog.cloudflare.com/workers-ai-large-models/) validate MCP as production-grade distributed infrastructure | N3TX's `NetworkMCP` adapter could be deployed as a Cloudflare Worker |
| **GPTCache** | [Semantic caching with ensemble embeddings](https://arxiv.org/html/2411.05276v1) achieves 92%+ hit rates | Integrate as optional dependency in `AgentMixin.run()` |

---

## Implementation Roadmap

### Phase 1: Cache Headers (Week 1)

**Zero architectural change. Maximum immediate impact.**

- Add `Cache-Control` headers to schema routes (`max-age=86400`)
- Add `ETag` support for schema responses
- Add `Cache-Control: private, no-cache` for authenticated data routes
- Add `Cache-Control: public, max-age=60` for public read routes
- Deploy any CDN (Cloudflare, CloudFront, Fastly) in front of N3TX

**Files to modify:**
- `/workspace/packages/n3tx-actors/src/n3tx_actors/api/network_api.py` -- `_register_schema_route()`, `_register_crud_routes()`
- `/workspace/packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py` -- same changes for Level 1/2

### Phase 2: Schema Cache Extension (Week 2)

**Add cache metadata to schemas via pipeline extension.**

- Create `cache_schema.py` with `@schema_extension(after='access')`
- Add per-model `__cache__` config (optional overrides for TTLs)
- Document the cache schema contract for edge consumers

**New files:**
- `/workspace/packages/n3tx-core/src/n3tx_core/models/cache_schema.py`

### Phase 3: Cache Invalidation Adapter (Weeks 3-4)

**Event-driven cache purging via existing LIFECYCLE events.**

- Create `NetworkEdge` adapter subscribed to LIFECYCLE events
- Implement CDN-specific purge APIs (Cloudflare, Fastly, generic)
- Wire subscription in `create_app()` for storable models

**New files:**
- `/workspace/packages/n3tx-actors/src/n3tx_actors/api/network_edge.py`

### Phase 4: Agent Response Caching (Weeks 5-6)

**Semantic cache integration for agent queries.**

- Add optional `GPTCache` or custom semantic cache to `AgentMixin.run()`
- Add `__cache__` config to `AgentActor` model
- Add cache hit/miss metrics to agent response (`from_cache`, `cache_type`)
- LIFECYCLE event-driven invalidation for stale agent responses

**Files to modify:**
- `/workspace/packages/n3tx-agents/src/n3tx_agents/mixin.py` -- `run()` method
- `/workspace/packages/n3tx-agents/src/n3tx_agents/actor.py` -- `AgentActor` cache config

### Phase 5: Edge Agent Workers (Weeks 7-10)

**Run lightweight agent logic at CDN edge. Research + prototype.**

- Evaluate Cloudflare Workers AI vs Lambda@Edge vs Deno Deploy
- Prototype `EdgeAgentWorker` adapter
- Implement complexity classifier (simple vs complex queries)
- Implement read-only tool execution at edge
- Benchmark latency and cost vs origin-only execution

**New files:**
- `/workspace/packages/n3tx-actors/src/n3tx_actors/api/network_edge_worker.py`
- Edge runtime code (TypeScript for Cloudflare Workers, Deno for Deno Deploy)

### Effort Summary

| Phase | Effort | Impact | Risk |
|---|---|---|---|
| Phase 1: Cache Headers | 2 days | High (global perf) | None |
| Phase 2: Schema Cache Extension | 3 days | Medium (metadata) | None |
| Phase 3: Invalidation Adapter | 2 weeks | High (data freshness) | Low |
| Phase 4: Agent Response Cache | 2 weeks | Very High (cost savings) | Medium (stale responses) |
| Phase 5: Edge Agent Workers | 3-4 weeks | Transformative | High (new runtime) |

---

## Appendix: Full Architecture Diagram (Proposed)

```
                         CDN Edge Layer (Global PoPs)
                    +-----------------------------------------+
                    |                                         |
                    |  [Schema Cache]    [Response Cache]     |
                    |       |                  |              |
                    |  [JWT Validator]  [Semantic Cache]      |
                    |       |                  |              |
                    |  [Edge Agent Worker]    [MCP Edge]      |
                    |       |                  |              |
                    +-------+-----|  Edge  |---+--------------+
                            |     | Router |   |
                            +-----|--------|---+
                                  |
                            [Cache Miss]
                                  |
               ---- Internet ---- | ---- Internet ----
                                  |
                    +-------------+---------------+
                    |     Origin (N3TX Server)     |
                    |                              |
                    |  [NetworkAPI] [NetworkMCP]   |
                    |       |           |          |
                    |  [Auth Interceptor]          |
                    |       |                      |
                    |    [Matrix Router]           |
                    |    /     |      \            |
                    | [Product] [Agent] [Tools]   |
                    |    |       |        |        |
                    | [SQLite] [LLM]  [Schema]    |
                    |                              |
                    | [NetworkAP]  [NetworkEdge]   |
                    |     |            |           |
                    | [Federation] [Invalidation]  |
                    +------------------------------+
```

**Request flow for a typical agent query:**

1. Client sends `POST /agents/1/agentic {"task": "Find grants"}` to CDN edge
2. Edge validates JWT (Tier 1 equivalent)
3. Edge checks semantic cache -- **cache hit**: return cached response (50ms)
4. **Cache miss**: forward to origin
5. Origin `NetworkAPI` runs auth interceptor (Tier 1)
6. Matrix routes to `AgentActor` instance
7. `AgentMixin.run()` discovers tools, runs LLM loop
8. Response flows back through Matrix -> NetworkAPI -> CDN edge
9. Edge caches response (with semantic embedding) for future queries
10. Edge invalidates cache when `LIFECYCLE` event arrives for related data

---

## Sources

- [NVIDIA AI Grid Architecture for Distributed Edge Inference](https://blockchain.news/news/nvidia-ai-grid-distributed-edge-inference-gtc-2026)
- [Cloudflare Agents SDK Documentation](https://developers.cloudflare.com/agents/)
- [Cloudflare Workers AI -- Edge Inference Platform](https://workers.cloudflare.com/product/workers-ai/)
- [Cloudflare Workers AI Large Models (Kimi K2.5)](https://blog.cloudflare.com/workers-ai-large-models/)
- [GPTCache -- Semantic Cache for LLMs](https://github.com/zilliztech/GPTCache)
- [GPT Semantic Cache: Reducing LLM Costs and Latency](https://arxiv.org/html/2411.05276v1)
- [AWS -- Optimize LLM Response Costs with Effective Caching](https://aws.amazon.com/blogs/database/optimize-llm-response-costs-and-latency-with-effective-caching/)
- [Vercel AI SDK v6 Stream Protocols](https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol)
- [Vercel AI SDK 5 Announcement](https://vercel.com/blog/ai-sdk-5)
- [FastAPI Cache Invalidation Patterns](https://oneuptime.com/blog/post/2026-02-02-fastapi-cache-invalidation/view)
- [FastAPI Edge Caching Patterns](https://medium.com/@Praxen/instant-fastapi-5-edge-caching-patterns-that-work-3fe18f30e48b)
- [Cloudflare Durable Objects Documentation](https://www.cloudflare.com/developer-platform/products/durable-objects/)
- [MCP November 2025 Specification](https://medium.com/@dave-patten/mcps-next-phase-inside-the-november-2025-specification-49f298502b03)
- [MCP Distributed AI Architecture](https://digitalkin.com/en/learn/futur-mcp-agentic-web)
- [CrewAI LangChain Caching Issues](https://github.com/crewAIInc/crewAI/issues/886)
- [NxCode -- CrewAI vs LangChain 2026 Comparison](https://www.nxcode.io/resources/news/crewai-vs-langchain-ai-agent-framework-comparison-2026)
- [AgentEdge: Agentic AI for Edge-Cloud Service Orchestration](https://www.techrxiv.org/users/706396/articles/1321948/master/file/data/Magazine_2___Agentic_AI_for_Service_Orchestration_in_the_Edge_Cloud_Continuum-2/Magazine_2___Agentic_AI_for_Service_Orchestration_in_the_Edge_Cloud_Continuum-2.pdf?inline=true)
- [Akamai AI Grid for Distributed Inference at 4,400 Edge Locations](https://cloudnews.tech/akamai-launches-ai-grid-intelligent-orchestration-for-distributed-inference-at-4400-edge-locations/)
- [IETF Agent Directory Service Draft](https://www.ietf.org/archive/id/draft-mp-agntcy-ads-00.html)
- [On-Device LLMs: State of the Union 2026 (Meta)](https://v-chandra.github.io/on-device-llms/)
