# :clipboard: Integrating a CDN Capability to N3TX Agents: Executive Summary

> *This is a standalone summary of the full strategic analysis report.*
> *For the complete analysis with technical details, case studies, and*
> *appendices, see [05-CDN-agents-analysis.md](../research/CDN-agents/05-CDN-agents-analysis.md).*
>
> *See also: [CDN-agents-propositions.md](CDN-agents-propositions.md) | [CDN-agents-whitepaper.md](CDN-agents-whitepaper.md)*

---

## :dart: The Question

**Should N3TX integrate CDN capabilities into its agent system, and if so, how and when?**

The edge AI market is projected to reach **$29.98 billion in 2026** ([Grand View Research](https://www.grandviewresearch.com/industry-analysis/edge-ai-market-report)), growing at 21-30% CAGR. Every major CDN provider -- Cloudflare, AWS, Akamai -- is investing heavily in AI-at-the-edge. Gartner predicts **40% of enterprise applications will feature task-specific AI agents by 2026**, up from less than 5% in 2025 ([Gartner](https://www.gartner.com/en/newsroom/press-releases/2025-08-26-gartner-predicts-40-percent-of-enterprise-apps-will-feature-task-specific-ai-agents-by-2026-up-from-less-than-5-percent-in-2025)). The question is not whether CDN + agents matters -- it is **which layer of the edge stack to invest in** and **when to start**.

The short answer: **invest now in caching and distribution (weeks of work, immediate payoff), defer edge inference until cost or latency data demands it (months away at earliest).**

---

## :bar_chart: Key Findings at a Glance

| # | Finding | Implication for N3TX |
|---|---------|---------------------|
| 1 | **Semantic caching cuts LLM costs 50-73%** at a 0.8 similarity threshold with <1% false positives ([GPT Semantic Cache](https://arxiv.org/html/2411.05276v3)) | The single highest-ROI optimization for any agent workload |
| 2 | **N3TX already has 4 NetworkAdapters** (HTTP, WS, MCP, ActivityPub); a 5th `NetworkEdge` adapter fits with zero architectural changes | CDN integration follows an existing, proven pattern |
| 3 | **68% of industrial AI pilots fail to scale** -- mostly due to premature edge deployment ([Edge IR](https://www.edgeir.com/why-edge-architectures-fail-and-how-to-design-around-it-20260316)) | Phased rollout with measurable triggers is essential |
| 4 | **Schema endpoints are already CDN-ready** -- public, deterministic, identical for all users, ~99% cache hit potential | Phase 1 requires days of work, not weeks |
| 5 | **Cloudflare's Durable Objects map nearly 1:1 to N3TX's ActorModel** -- stateful, message-based, with built-in SQLite | Future edge agents would extend, not rebuild, our architecture |
| 6 | **Agentic Plan Caching (APC) reduces agent costs by 50.31%** by caching execution plans, not answers ([NeurIPS 2025](https://arxiv.org/abs/2506.14852)) | Works even when underlying data changes -- high value for N3TX grant scanning |
| 7 | **Two-tier auth already splits edge vs. origin concerns** -- Tier 1 interceptor does fast identity checks, Tier 2 handler does OWNER checks | JWT validation at edge requires no auth refactoring |

> :bulb: **Key Insight:** The biggest win is not moving inference to the edge -- it is **moving decisions about inference to the edge**. A CDN-layer gateway that caches, routes, and classifies agent requests can cut costs by 50%+ before you deploy a single GPU at an edge location.

---

## :office: What the Industry Tells Us

The edge AI market is real and growing fast, but **production deployments are still the minority**. Only 34% of organizations have production edge AI systems with real-time data streaming ([Computer Weekly](https://www.computerweekly.com/feature/Edge-AI-Whats-working-and-what-isnt)). The winners are those picking the right *layer* -- not the ones rushing to deploy GPUs at 200 edge locations.

**The companies winning today are using CDN as an AI gateway, not as an inference platform.** Baselime migrated from AWS to Cloudflare and cut daily cloud spend by **83%** -- from $790/day to $325/day -- primarily because Lambda billed for I/O wait time that Cloudflare doesn't ([Cloudflare blog](https://blog.cloudflare.com/80-percent-lower-cloud-cost-how-baselime-moved-from-aws-to-cloudflare/)). Cloudflare's own internal security agent processes **7 billion tokens/day** and achieved **77% cost reduction** by running open-source models at the edge instead of proprietary ones centrally ([Cloudflare blog](https://blog.cloudflare.com/workers-ai-large-models/)). A peer-reviewed study on hybrid edge-cloud architectures found agentic AI workloads save **up to 75% energy** via edge distribution -- more than traditional inference -- because agents involve many sequential I/O-heavy steps that benefit from proximity ([arxiv](https://arxiv.org/html/2501.14823v2)).

**The cautionary signal is equally clear.** 68% of industrial edge AI pilots fail to scale. The top failure modes: premature edge inference without latency baselines, caching non-deterministic agent output, distributing state for stateful agents, and ignoring the observability tax. Every failed project shares one trait: they deployed edge AI because it was exciting, not because they had measured a specific problem.

### Provider Landscape

| Provider | Edge AI Product | Agent Support | Pricing Model | N3TX Fit |
|----------|----------------|--------------|---------------|----------|
| **Cloudflare** | Workers AI + Agents SDK | Durable Objects + MCP | $0.011/1K Neurons | **Best** -- Actor model, SQLite, MCP align |
| **AWS** | Lambda@Edge + Bedrock | AgentCore | Per-vCPU-second | Good -- enterprise compliance |
| **Akamai** | Inference Cloud | No native SDK | Not yet public | Too early -- no pricing, early access |
| **Vercel** | Edge Functions | No agent SDK | $5/hr active CPU | Partial -- no GPU, no agents |
| **Fastly** | Compute (Wasm) | No agent SDK | Request-based | Partial -- Wasm limits model size |

Cloudflare is the strongest match. Their Durable Objects implement the Actor Model with built-in SQLite -- architecturally identical to N3TX's `ActorModel`. Their MCP server support aligns with N3TX's `@expose_route` tool discovery. Their AI Gateway (caching, rate limiting, 20+ provider support) is **free** and immediately useful.

---

## :mag: Where We Stand Today

N3TX's architecture is **surprisingly well-positioned for CDN integration** -- but in a non-obvious way. The framework was designed for protocol-agnostic distribution, even if CDN was not the original goal.

### How CDN Maps to Our Architecture

```
Current N3TX Flow:

Client --HTTP--> NetworkAPI --TX--> Matrix --TX--> ActorModel --TX--> Reply
                     |                 |                |
                 Tier 1 Auth       Route by         Tier 2 Auth
                 (interceptor)     address           (handler)


Proposed CDN-Enhanced Flow:

Client --HTTP--> CDN Edge --HTTP--> NetworkAPI --TX--> Matrix --TX--> ActorModel
                    |                    |                |                |
               Edge Cache           Tier 1 Auth       Route by        Tier 2 Auth
               Schema Valid.        (interceptor)     address          (handler)
               JWT Valid.                |                |
               Rate Limiting         <--TX--          <--TX--
                    |               (response)        (reply)
               [cache hit?]
               Yes: return
               No: forward
```

**What we already have:**

- **NetworkAdapter abstraction** -- Every protocol (HTTP, WebSocket, MCP, ActivityPub) is a pluggable adapter translating between external protocols and TX messages. A `NetworkEdge` adapter follows the exact same pattern. No base class changes needed.

- **Schema as cacheable contract** -- `GET /Product` returns a JSON Schema that is immutable per deployment, self-describing (`$schema`, `$id`), and carries access rules, method signatures, and tool specs. This is inherently CDN-friendly.

- **LIFECYCLE events for invalidation** -- The ActivityPub adapter already subscribes to model lifecycle events (create/update/delete). A CDN adapter would subscribe the same way: `Product._subscribers.append('edge')`. The wiring is identical.

- **Two-tier auth already splits edge/origin** -- Tier 1 interceptors handle fast identity checks at the protocol boundary; Tier 2 handlers check OWNER rules at the resource level. This is the same constraint CDN architectures face, and N3TX already solved it.

- **Schema pipeline is extensible** -- Adding a `cache` stage via `@schema_extension(after='access')` is one decorator. The schema then carries its own cache hints -- TTLs, public/private flags, invalidation strategies. No other agent framework has this.

### What is Missing

| Gap | Severity | Effort | Blocking for Phase 1? |
|-----|----------|--------|-----------------------|
| No `Cache-Control` headers on schema routes | Low | 1-2 days | No -- add headers |
| No CDN invalidation adapter | Medium | 1-2 weeks | No -- stale cache acceptable short-term |
| No edge-side schema validation | Medium | 2-3 weeks | No -- nice-to-have |
| Distributed agent state | High | 4-8 weeks | Only for full edge agents (Phase 3) |
| JWT propagation through CDN | Medium | 1 week | No -- standard pattern |

None of the gaps block Phase 1. The first two phases require **days to weeks** of work, not months. The only high-severity gap -- distributed agent state -- is only needed for full edge agents in Phase 3, which we recommend deferring 9-18 months.

---

## :bar_chart: The Numbers

### Investment vs. Return by Phase

| Phase | Timeline | Eng Effort | Monthly Cost | Expected Savings |
|-------|----------|-----------|-------------|-----------------|
| **1: Schema CDN + AI Gateway** | Now -- 3 months | ~2 weeks | $0-15 (Cloudflare free/pro) | 99% schema cache hit; ~18% LLM exact-match cache; full observability |
| **2: Semantic Caching + Edge Classification** | 3-9 months | 4-6 weeks | $50-500 | **50-65% LLM cost reduction**; 40-60% fewer unnecessary agent calls |
| **3: Edge Agent Adapter** | 9-18 months | 8-12 weeks | Variable | Sub-100ms agent responses globally; federation support |

### The Caching Stack -- Three Tiers of Savings

Agent caching is not one thing. The highest-performing systems stack multiple layers:

| Tier | How It Works | Hit Rate | Latency | Best For |
|------|-------------|----------|---------|----------|
| **Exact-match** | Hash of (prompt + task) | ~18% ([Helicone](https://www.helicone.ai/blog/effective-llm-caching)) | <1ms | Identical repeated queries |
| **Semantic** | Embedding similarity > 0.8 threshold | 61-69% ([arxiv](https://arxiv.org/html/2411.05276v3)) | ~20ms | Similar queries, paraphrases |
| **Plan-level** | Cache execution strategy, adapt to new params | Variable | ~50ms | Multi-step agent tasks |

A production implementation using layered caching reported **41% of requests never reaching the LLM** ([AWS Database Blog](https://aws.amazon.com/blogs/database/optimize-llm-response-costs-and-latency-with-effective-caching/)). For N3TX, the most natural entry point is exact-match caching via AI Gateway (Phase 1, zero code), graduating to semantic caching in `AgentMixin.run()` (Phase 2, moderate code).

### ROI Example: Semantic Caching at Scale

At **50,000 agent requests/month** using Claude Sonnet ($3/M input + $15/M output tokens):

| Scenario | Monthly LLM Cost |
|----------|-----------------|
| No caching | **$900** |
| With 65% semantic cache hit rate | **$320** |
| **Monthly savings** | **$580 (64%)** |

At **500,000 requests/month**, that becomes **$5,800/month saved = $69,600/year**. The embedding overhead is ~$5/month at 50K requests -- negligible compared to savings.

### Build vs. Buy

For a framework-stage product, **buy the commodity layers, build only the N3TX-specific adapter**. 3-year TCO comparison:

| Approach | 3-Year Total |
|----------|-------------|
| Build everything custom | $160-240K |
| Buy AI Gateway + CDN (no custom work) | $11-45K |
| **Hybrid: buy gateway, build N3TX adapter** | **$44-100K** |

The hybrid approach is optimal. 71% of tech teams choose off-the-shelf solutions to accelerate time-to-value ([ThirstySprout](https://www.thirstysprout.com/post/build-vs-buy-software)). What makes N3TX unique is the **schema-driven agent pattern**, not CDN infrastructure. The CDN layer should amplify that pattern, not compete for engineering resources.

---

## :bulb: The Recommendation

### Phased Approach with Measurable Triggers

**Phase 1 (start now):** Put a CDN in front of N3TX schema and static endpoints. Route LLM calls through Cloudflare AI Gateway for caching and observability. This requires **~2 weeks of engineering** and costs near-zero. No architectural changes needed.

**Phase 2 (trigger: LLM spend exceeds $500/month OR query similarity > 30%):** Add semantic caching to `AgentMixin.run()` -- a cache check before execution, a cache store after. Deploy an edge classifier to route simple queries away from the full agent loop. This requires **4-6 weeks** and yields 50-65% LLM cost reduction.

**Phase 3 (trigger: monthly requests > 100K AND global latency variance > 200ms):** Build a `NetworkEdge` adapter mapping N3TX's actor pattern to Cloudflare Durable Objects. Run lightweight agents at the edge for classification and FAQ. Keep complex reasoning centralized. Requires distributed systems operational experience on the team.

### What We Explicitly Do NOT Recommend

- **Running full LLM inference at the edge today.** The models are there (Cloudflare now supports 70B parameters), but the operational complexity is premature for a framework-stage product.

- **Skipping phases.** Each phase generates the observability data that justifies the next. Without Phase 1 metrics, Phase 2 is guesswork.

- **Building custom CDN infrastructure.** N3TX's value is schema-driven intelligence, not network plumbing. Buy the plumbing, build the intelligence layer.

- **Caching agent answers for dynamic data.** For agents that query live databases or scrape websites, cache the *execution plan*, not the *answer*. Stale answers erode user trust faster than slow responses.

---

## :warning: Top 3 Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| **Stale cache serving wrong answers** -- agent responses cached when underlying data has changed | Medium | Medium | TTL tuning; LIFECYCLE event-driven invalidation; cache the *plan*, not the *answer* for dynamic data agents; monitor false positive rate |
| **Operational complexity exceeding team capacity** (especially Phase 3) | High for Phase 3 | High | Phase gates with measurable criteria; do not advance without data; budget 20-30% of edge deployment effort for observability |
| **Vendor lock-in** to Cloudflare Durable Objects | Medium | High | Abstract via `NetworkAdapter` pattern (already our standard); N3TX's adapter architecture makes provider swaps a new adapter class, not a rewrite |

---

## :world_map: Next Steps (30 Days)

1. **Week 1: Add cache headers to schema routes.** Set `Cache-Control: public, max-age=86400` on `GET /{ClassName}` responses in both `network_api.py` (Level 3) and `routes_fastapi.py` (Level 1/2). Add `ETag` support based on schema content hash. Add `Cache-Control: private, no-cache` for authenticated data routes.

2. **Week 2: Deploy a CDN in front of dev/staging.** Cloudflare free tier is sufficient. Verify schema cache hit rate reaches ~99%. Measure latency improvement for global schema fetches versus direct origin requests.

3. **Week 2: Route LLM calls through AI Gateway.** Cloudflare AI Gateway supports 20+ providers and provides caching + observability for free. Configure `pydantic-ai`'s HTTP client to route through the gateway -- approximately 10 lines of configuration, zero framework changes.

4. **Week 3: Create schema pipeline extension.** Add `@schema_extension(after='access')` that emits `cache` metadata in every model's schema -- TTLs, public/private flag, invalidation strategy. This makes cache policy **self-documenting and schema-driven**, a capability no competing agent framework offers.

5. **Week 4: Instrument and measure.** Log cache hit rates, LLM call volumes, query similarity distributions, and latency percentiles. This data determines when (and whether) to start Phase 2. **Do not proceed to semantic caching without at least 30 days of production metrics showing > 30% query similarity.**

---

> :bulb: **The bottom line:** Phase 1 is worth doing today. It requires minimal effort, costs near-zero, provides immediate benefits, and -- critically -- generates the observability data to make intelligent decisions about Phase 2 and beyond. N3TX has a unique architectural advantage: schemas that carry enough metadata for edge nodes to make caching, routing, and validation decisions autonomously. No other agent framework has this. The worst outcome is not doing the wrong thing at the edge. It is doing nothing while LLM costs grow and competitors discover what schema-driven edge intelligence can do.
