# CDN Capabilities x N3TX Agents: Technical Propositions

> *How CDN and edge computing principles can make N3TX agents cheaper, faster, and globally distributable.*
> *Based on research in `.traces/research/CDN-agents/` and codebase analysis of the actor, agent, and schema pipeline systems.*

---

## The Bridge

N3TX was built around a single conviction: **the model is the app**. Define a Python class, get a schema, an API, a UI, and an agent. That philosophy created something most frameworks lack -- a **self-describing contract** (JSON Schema) that travels with every response and governs every interaction. CDN architectures solve a different problem -- distributing content and computation across geographic edge nodes -- but they share an identical core requirement: **metadata that governs caching, routing, and validation decisions at the boundary**.

The connection is not superficial. N3TX already has four NetworkAdapters (HTTP, WebSocket, MCP, ActivityPub), each translating an external protocol into TX messages routed through the Matrix. Adding a CDN edge as a fifth adapter follows the **exact same pattern** with zero architectural changes. The `use()` interceptor chain already separates fast boundary checks (Tier 1) from deep resource checks (Tier 2) -- the same split CDN architectures use for edge auth vs. origin auth.

What makes this relevant *now* is cost. Agent workloads are the most expensive thing N3TX does -- a single `agentic()` call in `mixin.py` (line 383) triggers multiple LLM API calls at $0.01-1.00 each. Research shows semantic caching alone can cut that bill by **50-73%**, and it plugs directly into the `run()` method with no architectural disruption.

---

## Propositions

### Proposition 1: Add Cache-Control Headers to Schema and Public Read Routes

> **Proposition:** Emit proper `Cache-Control`, `ETag`, and `Vary` headers on schema endpoints and public read routes, making N3TX instantly CDN-compatible with zero framework changes.

**From the research:** Schema endpoints (`GET /{ClassName}`) are read-only, deterministic, and identical for all users. With proper headers, any CDN achieves ~99% cache hit rates on schemas. The research doc (02) identifies this as "zero code required" -- pure infrastructure gain.

**In our system:** Schema routes are registered in two places:
- `network_api.py` (`create_api_routes()`, line 57) for Level 3 routing
- `routes_fastapi.py` for Level 1/2 routing

Currently, streaming routes explicitly set `Cache-Control: no-cache` (network_api.py). Schema routes set nothing -- they inherit FastAPI's default (no caching). The schema pipeline in `proto_schema.py` already has a `metadata` stage (line 292) that stamps `$schema` and `$id` -- adding cache metadata is one additional stage.

**The idea:** Add a response middleware or modify the schema route factory to emit:
```
Schema routes:  Cache-Control: public, max-age=86400, s-maxage=86400
                ETag: sha256(schema_json)[:16]
Public reads:   Cache-Control: public, max-age=60
                Vary: Accept
Auth'd reads:   Cache-Control: private, no-cache
Mutations:      Cache-Control: no-store
```

The `access` stage in `proto_schema.py` (line 247) already serializes `__access__` rules into the schema. A CDN-aware middleware reads `schema['access']['read'] == 'anyone'` to decide whether a GET response is publicly cacheable -- **schema-driven CDN configuration** that no other framework offers.

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | **Low** -- 1-2 days. Modify route factories in two files. |
| Impact | **High** -- Eliminates the most common API call globally. Sub-20ms schema loads vs 200-500ms origin. |
| Risk | **None** -- Additive change. Worst case: CDN not deployed, headers are ignored. |
| Timeline | **Days** |

---

### Proposition 2: Add a `cache` Stage to the Schema Pipeline

> **Proposition:** Create a `@schema_extension(after='access')` stage that embeds cache hints (TTLs, invalidation strategy, cacheability) directly in the JSON Schema, making every model's caching policy self-documenting and edge-consumable.

**From the research:** The research doc (02) calls out that N3TX's unique advantage is "schema-driven edge intelligence." No other agent framework carries enough metadata in its schemas to enable edge-side caching decisions. Embedding cache hints in the schema means any edge consumer -- CDN, MCP client, federated server -- can make caching decisions without asking the origin.

**In our system:** The schema pipeline (`proto_schema.py`) is explicitly designed for this. The `register_stage()` function (line 57) and `@schema_extension` decorator (line 98) exist to let packages inject new stages without modifying core. The pipeline is currently: `base -> strip_hidden -> methods -> defs -> access -> ui -> metadata`. A `cache` stage slots after `access` naturally because it reads access rules to derive cacheability.

**The idea:**
```python
# packages/n3tx-core/src/n3tx_core/models/cache_schema.py
@schema_extension(after='access')
def cache(cls, schema: dict) -> dict:
    access = schema.get('access', {})
    cache_config = {
        'schema_ttl': 86400,
        'public': access.get('read') == 'anyone',
        'list_ttl': getattr(cls, '__cache_list_ttl__', 60) if access.get('read') == 'anyone' else 0,
        'item_ttl': getattr(cls, '__cache_item_ttl__', 300) if access.get('read') == 'anyone' else 0,
        'invalidation': 'lifecycle',
    }
    schema['cache'] = cache_config
    return schema
```

Models can override with `__cache_list_ttl__ = 300` (5-minute list cache) or `__cache__ = {'list_ttl': 0}` to disable. The pipeline becomes: `base -> strip_hidden -> methods -> defs -> access -> cache -> ui -> metadata`.

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | **Low** -- 3 days. One new file, one test file, docs update. |
| Impact | **Medium** -- Self-documenting cache policy. Enables all downstream CDN integrations. |
| Risk | **None** -- Schema extension. Ignored if no consumer reads it. |
| Timeline | **Days** |

---

### Proposition 3: Cache Tool Discovery Results in `discover_tools()`

> **Proposition:** Add in-memory caching to `discover_tools()` so that repeated agent invocations with the same tool addresses skip schema introspection entirely.

**From the research:** Tool discovery runs on *every* agent invocation. The research doc (02, Proposal 4) identifies this as wasteful: "For a stable set of models, these specs are identical across invocations." Caching tool specs locally is a prerequisite for distributing them to edge nodes.

**In our system:** `discover_tools()` in `tools.py` (line 43) iterates actor addresses, fetches each class via Matrix children, calls `cls.schema()`, and builds `ToolSpec` lists. This is synchronous and pure -- same inputs always produce same outputs (schemas don't change at runtime). Yet it runs fresh for every `run()` call in `mixin.py` (line 345).

**The idea:** Add a module-level cache keyed by `frozenset(actor_addrs)`:

```python
_tool_cache: dict[frozenset, list[ToolSpec]] = {}

def discover_tools(actor_addrs: list, root, caller_addr: str = None) -> list[ToolSpec]:
    cache_key = frozenset(actor_addrs)
    if cache_key in _tool_cache:
        return _tool_cache[cache_key]
    # ... existing discovery logic ...
    _tool_cache[cache_key] = specs
    return specs

def invalidate_tool_cache():
    _tool_cache.clear()
```

Call `invalidate_tool_cache()` from `register_model()` in `registrar.py` so the cache resets when models are registered (startup). This is a 15-line change with immediate savings on every agent call.

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | **Very Low** -- Half a day. 15 lines + tests. |
| Impact | **Medium** -- Eliminates redundant schema introspection on every agent call. Critical prerequisite for Propositions 7-8. |
| Risk | **Low** -- Cache could serve stale specs if models are dynamically registered post-startup (unlikely in production). |
| Timeline | **Hours** |

---

### Proposition 4: Semantic Cache Layer in `AgentMixin.run()`

> **Proposition:** Wrap the Pydantic AI agent loop in `run()` with a two-tier cache check (exact-match + semantic similarity), cutting LLM costs by 50-65% for repetitive agent queries.

**From the research:** At a 0.8 similarity threshold, semantic caching achieves a 68.8% hit rate with <1% false positives (GPT Semantic Cache, arxiv). The 20ms embedding overhead is negligible compared to 2-30s agent execution. At 50K requests/month with Claude Sonnet, this saves ~$580/month (research doc 01, ROI section).

**In our system:** `AgentMixin.run()` in `mixin.py` (line 268) is the single entry point for all agent execution. Line 383 is the hot path: `result = await ai_agent.run(task, **run_kwargs)`. A cache check wraps this naturally:

```python
# Before the Pydantic AI call (line 383)
cache_key = hashlib.sha256(f"{agent_addr}:{task}:{tuple(sorted(tools))}".encode()).hexdigest()
cached = await _check_agent_cache(cache_key)
if cached:
    cached['from_cache'] = 'exact'
    return cached

# After the Pydantic AI call
await _store_agent_cache(cache_key, result_dict, ttl=3600)
```

The semantic layer uses embeddings (via pydantic-ai's model or a dedicated embedding model) to find similar past queries. This is optional and configured via `config.AGENT_DEFAULTS['semantic_cache'] = True`.

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | **Medium** -- 2-3 weeks. Exact-match cache (Redis/in-memory) is simple. Semantic cache requires embedding infrastructure. |
| Impact | **Very High** -- 50-65% LLM cost reduction. Latency drops from seconds to milliseconds for cache hits. |
| Risk | **Medium** -- Stale responses for dynamic data. Mitigated by TTLs and LIFECYCLE-event-driven invalidation. |
| Timeline | **Weeks** |

---

### Proposition 5: `NetworkEdge` Adapter for Cache Invalidation

> **Proposition:** Create a `NetworkEdge(NetworkAdapter)` that subscribes to LIFECYCLE events and issues cache purge requests to CDN providers, keeping edge caches fresh on data mutation.

**From the research:** The research doc (02) identifies that `NetworkAP` already receives LIFECYCLE events and converts them to ActivityPub Activities. A CDN adapter follows the **identical subscription pattern** -- when a Product is updated, the edge adapter purges the cached `GET /products` and `GET /products/{id}` responses.

**In our system:** The LIFECYCLE event system is proven infrastructure. `ActorModel._publish_lifecycle()` sends `TX(name='LIFECYCLE')` to registered subscribers. The AP adapter (`network_ap.py`) consumes these. A `NetworkEdge` adapter would:

1. Subscribe via `Product._subscribers.append('edge')`
2. Receive `LIFECYCLE` TX with `data={'event': 'after_update', 'entity': {...}}`
3. Map event to CDN purge API calls (Cloudflare: `POST /zones/{zone}/purge_cache`)

```
ActorModel CRUD  -->  LIFECYCLE TX  -->  NetworkEdge.LIFECYCLE()  -->  CDN purge API
                                              |
                                    tx.source = 'products'
                                    data.event = 'after_create'
                                              |
                                    Purge: /products, /products/{id}
```

The adapter is CDN-provider-agnostic via a pluggable purge strategy (Cloudflare, Fastly, CloudFront, generic HTTP).

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | **Medium** -- 1-2 weeks. Adapter class + CDN provider integration + wiring in `create_app()`. |
| Impact | **High** -- Ensures edge caches serve fresh data. Required for any production CDN deployment. |
| Risk | **Low** -- Follows proven adapter pattern. Failure mode is stale cache (acceptable with short TTLs). |
| Timeline | **Weeks** |

---

### Proposition 6: AI Gateway Integration for LLM Call Observability

> **Proposition:** Route all `pydantic-ai` LLM calls through a CDN-layer AI Gateway (Cloudflare AI Gateway or equivalent) for automatic exact-match caching, rate limiting, and unified observability across all LLM providers.

**From the research:** Cloudflare AI Gateway provides caching, rate limiting, and observability across 20+ AI providers at zero per-request cost. Even exact-match caching alone delivers ~18% hit rate (Helicone data). The real value is **observability** -- unified logging of every LLM call, token usage, latency, and errors across all agents.

**In our system:** The `_resolve_llm()` function in `mixin.py` (line 72) already creates custom `OpenAIChatModel` instances for Ollama. The same pattern works for routing through an AI Gateway: configure the base URL to point at the gateway instead of the LLM provider directly. Pydantic AI's `Agent` class accepts custom HTTP clients.

```python
# In config.py or AGENT_DEFAULTS
AI_GATEWAY_URL = os.getenv('N3TX_AI_GATEWAY_URL', '')  # e.g., 'https://gateway.ai.cloudflare.com/v1/{account}/{gateway}'

# In _resolve_llm(), wrap providers with gateway URL
if config.AI_GATEWAY_URL:
    # Route through AI Gateway for caching + observability
    ...
```

This is ~10 lines of configuration. No agent code changes. No schema changes. Immediate cost savings and full visibility into LLM usage patterns.

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | **Very Low** -- 1 day. Configuration change in `_resolve_llm()` + environment variable. |
| Impact | **High** -- Immediate observability. ~18% cost reduction from exact-match caching. Rate limiting prevents runaway agent loops. |
| Risk | **Low** -- External dependency on gateway availability. Fallback: direct LLM calls if gateway is down. |
| Timeline | **Hours to Days** |

---

### Proposition 7: Edge-Side Request Classification (Smart Routing)

> **Proposition:** Deploy a lightweight classifier at the CDN edge that triages incoming agent requests into "cache-servable," "needs full agent," or "schema-only," eliminating 40-60% of unnecessary origin round-trips.

**From the research:** In enterprise support bots, 40-60% of queries are repetitive or highly similar (VentureBeat). A fine-tuned DistilBERT classifier routes at <8ms per decision (PMC study). Combined with semantic caching, this eliminates the majority of LLM API calls.

**In our system:** This does not modify N3TX core -- it sits in front of it. But N3TX's schema makes it uniquely enabled: the edge classifier reads cached schemas to understand which models exist, what tools are available, and what access rules apply. The `agentic()` policy layer in `mixin.py` (line 216) already separates policy from execution. An edge classifier mirrors this separation at the network boundary.

```
Client POST /agents/1/agentic {"task": "..."}
    |
    v
Edge Classifier (tiny model, <8ms)
    |-- "repetitive" --> Semantic Cache --> Return cached response
    |-- "novel"      --> Forward to origin N3TX server
    |-- "malformed"  --> Reject with 400 (validated against cached schema)
```

This is a **Phase 2** investment -- only justified when LLM costs exceed $500/month and query analysis shows >30% similarity.

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | **High** -- 3-4 weeks. Edge runtime setup + classifier training + integration testing. |
| Impact | **Very High** -- Eliminates 40-60% of origin requests. Sub-50ms response for classified queries. |
| Risk | **Medium** -- Classifier accuracy is critical. False negatives waste edge compute; false positives serve wrong answers. |
| Timeline | **Months** |

---

### Proposition 8: Agentic Plan Caching (Cache Strategy, Not Answers)

> **Proposition:** Implement plan-level caching in `AgentMixin.run()` that caches the *execution strategy* (tool call sequence) rather than the final answer, enabling cache reuse even when underlying data changes.

**From the research:** NeurIPS 2025's Agentic Plan Caching (APC) paper shows 50.31% cost reduction with 96.61% performance retention. Unlike semantic caching (which caches answers), plan caching extracts the tool-calling pattern from a successful agent run and reuses it for similar tasks with different parameters.

**In our system:** The `run()` method in `mixin.py` returns `result.all_messages()` (line 386) which contains the complete conversation including all tool calls. Extracting a "plan template" from this is straightforward:

```
Task: "Find renewable energy grants in California"
Plan: [grants_list(topic="renewable energy", location="California")]
       -> [grants_create(title=..., url=...)] x N

Template: "Find {topic} grants in {location}"
Plan: [grants_list(topic={topic}, location={location})]
       -> [grants_create(title=..., url=...)] x N
```

For a new task "Find healthcare grants in Texas," the cached plan template matches and executes with substituted parameters -- skipping the LLM reasoning loop entirely.

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | **High** -- 4-6 weeks. Plan extraction, template matching, parameter substitution, validation. |
| Impact | **Transformative** -- Caches *reasoning*, not just answers. Works even with dynamic data. |
| Risk | **High** -- Plan templates may not generalize. Requires careful validation that adapted plans produce correct results. |
| Timeline | **Months** (Moonshot) |

---

## Proposition Map

```
                        Impact
                    High |  P4 (Semantic Cache)   P8 (Plan Cache)
                         |  P6 (AI Gateway)       P7 (Edge Classify)
                         |  P1 (Cache Headers)    P5 (NetworkEdge)
                         |
                    Med  |  P2 (Schema Stage)
                         |  P3 (Tool Cache)
                         |
                    Low  |
                         +------+--------+--------+--------->
                              Low     Medium     High     Effort


Quick Wins (do now):        P1, P3, P6  (hours to days)
Strategic Investments:      P2, P4, P5  (weeks)
Moonshots:                  P7, P8      (months)
```

| Priority | Proposition | Effort | Impact | Timeline |
|----------|-------------|--------|--------|----------|
| 1 | P1: Cache Headers | Low | High | Days |
| 2 | P3: Tool Discovery Cache | Very Low | Medium | Hours |
| 3 | P6: AI Gateway | Very Low | High | Days |
| 4 | P2: Cache Schema Stage | Low | Medium | Days |
| 5 | P5: NetworkEdge Adapter | Medium | High | Weeks |
| 6 | P4: Semantic Agent Cache | Medium | Very High | Weeks |
| 7 | P7: Edge Classification | High | Very High | Months |
| 8 | P8: Plan Caching | High | Transformative | Months |

---

## What NOT to Do

**Anti-Pattern 1: Full edge inference for complex agent loops.** N3TX agents routinely make 5-30 tool calls per `agentic()` invocation, each requiring Matrix routing to storable models with SQLite backends. Moving the agent loop to the edge means replicating the entire data layer. Edge constraints (10GB storage per Durable Object, limited model sizes) make this impractical. Run classification at the edge; run reasoning at the origin.

**Anti-Pattern 2: Caching agent responses for dynamic data without invalidation.** A cached answer to "What grants are available?" becomes wrong the moment a new grant is created. Semantic caching without LIFECYCLE-event-driven invalidation produces silently stale answers. Always pair Proposition 4 with Proposition 5.

**Anti-Pattern 3: Building custom CDN infrastructure.** N3TX is a framework, not an infrastructure company. The research is unambiguous: buy the commodity layers (CDN, AI Gateway, edge compute). Build only the **N3TX-specific adapter** that maps schemas and LIFECYCLE events to the CDN's APIs. The crown jewel is the integration layer (`NetworkEdge`, cache schema stage), not the infrastructure.

---

## Recommended Starting Point

**Start with P1 + P3 + P6 in parallel.** These three propositions are independent, take less than a week combined, and provide immediate measurable benefits:

- **P1 (Cache Headers):** Deploy any CDN in front of N3TX. Schema loads drop from 200ms to 20ms globally. Validation: measure schema endpoint latency before/after with CDN.
- **P3 (Tool Cache):** Agent invocations skip redundant `cls.schema()` calls. Validation: time `discover_tools()` with and without cache in agent tests.
- **P6 (AI Gateway):** Full visibility into LLM usage. ~18% cost savings from exact-match caching. Validation: compare LLM spend before/after with gateway dashboard.

**Decision gate for Phase 2:** If LLM spend exceeds $500/month AND query analysis shows >30% repetition, proceed to P4 (Semantic Cache) + P5 (NetworkEdge). Measure cache hit rates in staging before deploying to production.
