# Option 2: Expand Agent Capabilities -- Advanced Tooling, Multi-Agent Pipelines, and Intelligent Orchestration

**Grant Watcher on PyBend v0.10**
*Research Date: 2026-03-04*

---

## Executive Summary

Grant Watcher today is a **single-agent system**: one LLM agent scrapes web pages, extracts grant data, and writes records to a database. It works. But it does not scale -- in accuracy, in coverage, in reliability, or in operational intelligence. This document analyzes how to evolve the agent layer from "one agent scrapes pages" to a **multi-agent grant intelligence platform**, while staying grounded in PyBend's existing Actor/Matrix/TX primitives.

> **Key Insight:** PyBend's Actor/Matrix/TX messaging system is already a multi-agent message bus. The infrastructure for inter-agent communication, routing, and correlation exists today. What is missing is not plumbing -- it is **orchestration logic, domain-specific tools, agent memory, and structured validation**.

The recommended path is a **three-phase rollout** over 8-12 weeks:

| Phase | What | Effort | Value |
|-------|------|--------|-------|
| Phase 1: Tool Expansion + Structured Output | New domain tools, Grants.gov API, validation | 2-3 weeks | 3x grant discovery accuracy |
| Phase 2: Two-Agent Pipeline (Scanner + Reviewer) | Quality gate, deduplication, confidence scoring | 2-3 weeks | Eliminate junk records, human trust |
| Phase 3: Parallel Scanners + Orchestrator | Source-type specialists, scheduling, cost tracking | 3-4 weeks | 10x coverage, operational maturity |

Estimated total LLM cost at Phase 3 operating scale: **$15-40/month** for 50-100 sources scanned weekly using Claude Sonnet 4.6 ($3/$15 per million tokens). Local Ollama fallback reduces this to near-zero for classification and deduplication tasks.

---

## Table of Contents

1. [Current Architecture Assessment](#-current-architecture-assessment)
2. [Tool Expansion Strategy](#-tool-expansion-strategy)
3. [Multi-Agent Architecture Patterns](#-multi-agent-architecture-patterns)
4. [Agent Memory and State](#-agent-memory-and-state)
5. [Structured Output and Validation](#-structured-output-and-validation)
6. [Orchestration Patterns](#-orchestration-patterns)
7. [Cost Analysis and LLM Economics](#-cost-analysis-and-llm-economics)
8. [Competitive Landscape](#-competitive-landscape)
9. [Feasibility and ROI Assessment](#-feasibility-and-roi-assessment)
10. [Recommended Phased Rollout](#-recommended-phased-rollout)
11. [Trade-offs and Risks](#-trade-offs-and-risks)
12. [Sources](#-sources)

---

## Current Architecture Assessment

### What Exists Today

The Grant Watcher agent system is built on four core components:

```
                        +-----------------+
                        |   AgentActor    |  (DB record: name, prompt, tools, llm)
                        |  "Grant Scanner"|
                        +--------+--------+
                                 |
                          agent_run()
                                 |
              +------------------+------------------+
              |                  |                  |
     +--------v-------+  +------v------+  +--------v--------+
     | discover_tools |  | Build       |  | Pydantic AI     |
     | (from schemas) |  | AgentDeps   |  | Agent.run()     |
     +--------+-------+  +------+------+  +--------+--------+
              |                  |                  |
              v                  v                  v
     +------------------------------------------+
     |  Transient NetworkAdapter (_agent_{uuid}) |
     |  - Future-based request/response          |
     |  - Routes tool calls through Matrix       |
     +--------------------+----------------------+
                          |
                    +-----v-----+
                    |   Matrix  |  (Root message router)
                    +-----+-----+
                          |
          +---------------+---------------+
          |               |               |
    +-----v-----+   +----v----+   +------v-------+
    |  grants   |   | sources |   |  web_tools   |
    | (CRUD)    |   | (CRUD)  |   | scrape/extract|
    +-----------+   +---------+   +--------------+
```

**Current flow**: Agent lists sources -> scrapes each URL -> extracts text -> checks for duplicates -> creates Grant records.

**Current tool set** (discovered from actor schemas):

| Tool | Source Actor | Type | Description |
|------|------------|------|-------------|
| `grants_list` | `grants` | CRUD | List existing grants |
| `grants_create` | `grants` | CRUD | Create new grant record |
| `grants_get` | `grants` | CRUD | Get grant by ID |
| `grants_update` | `grants` | CRUD | Update grant record |
| `grants_delete` | `grants` | CRUD | Delete grant record |
| `sources_list` | `sources` | CRUD | List scanning sources |
| `sources_get` | `sources` | CRUD | Get source by ID |
| `web_tools_scrape` | `web_tools` | Method | Fetch URL HTML (50KB limit) |
| `web_tools_extract` | `web_tools` | Method | CSS-selector text extraction |

**What works well:**
- Tool discovery from schemas is elegant -- add an `@expose_route` and agents can use it
- TX routing through Matrix gives us auth, interceptors, and audit for free
- Transient NetworkAdapter per run prevents state leakage between runs
- `AgentActor` as data-not-code means agents are reconfigurable without deploys

**What is missing:**

| Gap | Impact |
|-----|--------|
| No structured output validation | Agent creates malformed grants -- wrong dates, missing fields |
| No deduplication beyond prompt instruction | LLM "checking duplicates" is unreliable; exact/fuzzy match needed |
| No domain-specific tools | Grants.gov has a free API -- scraping HTML is wasteful |
| No confidence scoring | All grants created with equal confidence, no quality signal |
| Single agent bottleneck | One agent doing scanning + extraction + validation + creation |
| No memory between runs | Same URLs re-scraped, same grants re-discovered |
| No cost tracking | No visibility into token usage per run, per source |
| No retry/recovery | If scrape fails mid-run, entire run is lost |
| No scheduling | Manual trigger only (`POST /agents/1/run`) |

---

## Tool Expansion Strategy

### The WebTools Pattern: Pure Tool Providers

The existing `WebTools` class establishes a clean pattern for tool-only actors:

```python
class WebTools(ActorModel):
    __tablename__ = 'web_tools'
    __storable__ = False          # No database storage
    # Only @expose_route methods -- these become agent tools
```

This is the right pattern. Non-storable `ActorModel` subclasses register with Matrix, expose methods via schema, and tool discovery picks them up automatically. **No framework changes needed to add new tool providers.**

### Recommended New Tool Actors

#### 1. GrantsGovTools -- Structured API Access

The Grants.gov API provides [free, unauthenticated RESTful endpoints](https://www.grants.gov/api) for searching federal funding opportunities. Scraping their HTML when they offer structured JSON is like photocopying a book when they will email you the PDF.

```python
class GrantsGovTools(ActorModel):
    """Federal grant search via Grants.gov API (no auth required)."""
    __tablename__ = 'grants_gov_tools'
    __storable__ = False

    @expose_route('/search', methods=['POST'], access=AUTHENTICATED)
    async def search(self, keyword: str, agency: str = '',
                     status: str = 'posted') -> dict:
        """Search Grants.gov for funding opportunities."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                'https://www.grants.gov/api/search2',
                params={'keyword': keyword, 'oppStatus': status,
                        'agency': agency, 'rows': 25}
            )
        data = resp.json()
        return {
            'total': data.get('hitCount', 0),
            'opportunities': [
                {
                    'title': opp.get('title'),
                    'agency': opp.get('agencyName'),
                    'number': opp.get('number'),
                    'deadline': opp.get('closeDate'),
                    'url': f"https://www.grants.gov/search-results-detail/{opp.get('id')}",
                    'posted': opp.get('openDate'),
                    'award_floor': opp.get('awardFloor'),
                    'award_ceiling': opp.get('awardCeiling'),
                    'description': opp.get('synopsis', '')[:2000],
                }
                for opp in data.get('oppHits', [])[:25]
            ]
        }

    @expose_route('/detail', methods=['POST'], access=AUTHENTICATED)
    async def detail(self, opportunity_id: str) -> dict:
        """Fetch full details for a specific opportunity."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f'https://www.grants.gov/api/fetchOpportunity',
                params={'id': opportunity_id}
            )
        return resp.json()
```

**Why this matters**: Structured API data means no HTML parsing errors, no broken CSS selectors, and **10x faster** than scraping. The agent gets clean JSON with proper field names -- deadline, award amounts, agency -- already structured.

#### 2. DeduplicationTools -- Fuzzy Matching

```python
class DeduplicationTools(ActorModel):
    """Grant deduplication via title similarity and URL matching."""
    __tablename__ = 'dedup_tools'
    __storable__ = False

    @expose_route('/check', methods=['POST'], access=AUTHENTICATED)
    def check(self, title: str, url: str = '', agency: str = '') -> dict:
        """Check if a grant already exists. Returns match info."""
        from difflib import SequenceMatcher
        existing = Grant.list(limit=500)  # TODO: index for scale

        for grant in existing.get('data', []):
            # Exact URL match
            if url and grant.get('url') == url:
                return {'duplicate': True, 'match_type': 'exact_url',
                        'existing_id': grant['id'], 'similarity': 1.0}
            # Fuzzy title match (>85% similarity)
            ratio = SequenceMatcher(
                None, title.lower(), grant.get('title', '').lower()
            ).ratio()
            if ratio > 0.85:
                return {'duplicate': True, 'match_type': 'fuzzy_title',
                        'existing_id': grant['id'], 'similarity': ratio}

        return {'duplicate': False, 'match_type': None}
```

**Why deterministic > LLM for dedup**: Telling the LLM to "check for duplicates" costs tokens and is unreliable. A `SequenceMatcher` comparison is free, instant, and consistent. The agent calls `dedup_tools_check` before `grants_create` -- the tool says yes or no.

#### 3. ClassificationTools -- Grant Categorization

```python
class ClassificationTools(ActorModel):
    """Classify grants by field, eligibility, and relevance."""
    __tablename__ = 'classification_tools'
    __storable__ = False

    CATEGORIES = [
        'stem_research', 'health_biomedical', 'education',
        'environment_energy', 'social_services', 'infrastructure',
        'agriculture', 'arts_humanities', 'defense_security', 'other'
    ]

    @expose_route('/categorize', methods=['POST'], access=AUTHENTICATED)
    def categorize(self, title: str, description: str,
                   agency: str = '') -> dict:
        """Assign category based on keywords and agency mapping."""
        text = f"{title} {description} {agency}".lower()
        scores = {}
        # Keyword-based scoring (fast, deterministic)
        keyword_map = {
            'stem_research': ['research', 'science', 'nsf', 'technology'],
            'health_biomedical': ['health', 'nih', 'biomedical', 'clinical'],
            'education': ['education', 'school', 'student', 'teaching'],
            'environment_energy': ['energy', 'climate', 'doe', 'environmental'],
            # ... more mappings
        }
        for cat, keywords in keyword_map.items():
            scores[cat] = sum(1 for kw in keywords if kw in text)
        top = max(scores, key=scores.get) if any(scores.values()) else 'other'
        return {'category': top, 'confidence': min(scores[top] / 3.0, 1.0),
                'all_scores': scores}
```

#### 4. NotificationTools -- Alert on New Discoveries

```python
class NotificationTools(ActorModel):
    """Send notifications when high-value grants are discovered."""
    __tablename__ = 'notification_tools'
    __storable__ = False

    @expose_route('/alert', methods=['POST'], access=AUTHENTICATED)
    async def alert(self, grant_title: str, grant_url: str,
                    deadline: str = '', amount_max: float = 0) -> dict:
        """Log a notification (extensible to email/Slack/webhook)."""
        # Phase 1: just log it. Phase 2: email/webhook integration.
        import logging
        logger = logging.getLogger('grants.notifications')
        logger.info("NEW GRANT: %s | Deadline: %s | Up to $%s | %s",
                     grant_title, deadline, amount_max, grant_url)
        return {'notified': True, 'channel': 'log'}
```

### Tool Expansion Summary

| Tool Actor | Tools Added | Effort | Value |
|-----------|-------------|--------|-------|
| `GrantsGovTools` | `search`, `detail` | 1 day | Structured federal grant data, no scraping |
| `DeduplicationTools` | `check` | 0.5 day | Eliminates duplicate grants deterministically |
| `ClassificationTools` | `categorize` | 0.5 day | Auto-categorization without LLM tokens |
| `NotificationTools` | `alert` | 0.5 day | Extensible alert pipeline |
| **Enhanced WebTools** | `search_links`, `summarize` | 1 day | Better scraping for non-API sources |

> **Key Insight:** The best tool strategy is **LLM for reasoning, deterministic code for data operations**. Use the LLM to decide *what* to search and *how to interpret* results. Use code tools for matching, deduplication, categorization, and API calls. This cuts token usage by 30-50% while improving accuracy.

### How Tool Discovery Works (No Framework Changes)

Adding a new tool actor to Grant Watcher requires exactly two changes:

1. **Create the actor class** (e.g., `models/grants_gov_tools.py`)
2. **Register it in `main.py`**: Add to the `models=[]` list in `create_app()`

That is it. The `discover_tools()` function in `/workspace/src/pybend/core/agents/tools.py` reads the actor's `schema()`, finds all `@expose_route` methods, and generates `ToolSpec` objects. The agent's `AgentTool` join records just need a new entry pointing to the actor address:

```python
# In seed.py or via API
AgentTool(target="grants_gov_tools", description="Grants.gov API search")
```

The tool discovery flow:

```
agent.run(task="Find new grants")
    |
    v
_resolve_tool_addrs() -> ['grants', 'sources', 'web_tools', 'grants_gov_tools', ...]
    |
    v
discover_tools(addrs, root)
    |
    +-- For each addr:
    |       root._children[addr] -> Actor class
    |       cls.schema() -> JSON Schema with 'methods' section
    |       _method_tool_specs() -> ToolSpec per @expose_route
    |       _crud_tool_specs() -> ToolSpec per CRUD op (if storable)
    |
    v
[ToolSpec, ToolSpec, ...] -> make_tool() -> pydantic_ai.Tool objects
```

### Trade-off: Generic vs. Specialized vs. LLM-Generated Tools

| Approach | Example | Pros | Cons |
|----------|---------|------|------|
| **Generic** | `web_tools_scrape(url)` | Works on any site | Requires LLM to parse raw HTML; error-prone |
| **Specialized** | `grants_gov_search(keyword)` | Clean data, fast, reliable | Only works for one source type |
| **LLM-generated** | Agent writes Python code at runtime | Infinitely flexible | Security nightmare, unpredictable, slow |

**Recommendation**: Start with specialized tools for the highest-value sources (Grants.gov, NIH Reporter, NSF Awards), fall back to generic `web_tools_scrape` for everything else. Avoid LLM-generated tools -- the security and reliability costs are not worth the flexibility for this domain.

---

## Multi-Agent Architecture Patterns

### Why Multi-Agent?

The single-agent Grant Scanner is doing four jobs poorly instead of one job well:

1. **Discovery** -- finding grant listing pages
2. **Extraction** -- pulling structured data from messy HTML
3. **Validation** -- checking data quality, deduplication
4. **Persistence** -- creating and updating records

Each job has different optimal strategies, different failure modes, and different LLM requirements. [Anthropic's multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system) demonstrated that a multi-agent approach with Claude Opus 4 as lead + Claude Sonnet 4 subagents **outperformed single-agent Claude Opus 4 by 90.2%** on research evaluation benchmarks.

But multi-agent systems also use **15x more tokens than chat interactions** ([Anthropic](https://www.anthropic.com/engineering/multi-agent-research-system)). For economic viability, "multi-agent systems require tasks where the value of the task is high enough to pay for the increased performance."

Grant discovery qualifies: a single well-matched grant can be worth $100K-$1M+ in funding.

### Pattern Analysis for Grant Watcher

[Microsoft's AI Agent Design Patterns guide](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns) identifies five orchestration patterns. Here is how each maps to our domain:

| Pattern | Description | Fit for Grants | Recommendation |
|---------|------------|----------------|----------------|
| **Sequential (Pipeline)** | Agent A -> Agent B -> Agent C | **Excellent** | Scanner -> Reviewer is a natural pipeline |
| **Concurrent (Fan-out)** | N agents process same input in parallel | **Good** | Multiple scanners for different source types |
| **Group Chat** | Agents debate in shared thread | **Poor** | Over-complex for structured data extraction |
| **Handoff** | Dynamic delegation based on context | **Moderate** | Useful for source-type routing |
| **Magentic** | Dynamic planning + execution ledger | **Poor** | Grant scanning is well-understood, not open-ended |

### Recommended Architecture: Pipeline + Fan-Out Hybrid

```
                          +------------------+
                          |   Orchestrator   |
                          | (Scheduling,     |
                          |  Cost Tracking)  |
                          +--------+---------+
                                   |
                    +--------------+--------------+
                    |              |              |
              +-----v----+  +-----v-----+  +-----v-----+
              | Scanner  |  | Scanner   |  | Scanner   |
              | (Gov API)|  | (Web)     |  | (RSS/Feed)|
              +-----+----+  +-----+-----+  +-----+-----+
                    |              |              |
                    +--------------+--------------+
                                   |
                          +--------v---------+
                          |    Reviewer      |
                          | (Validate,       |
                          |  Deduplicate,    |
                          |  Score)          |
                          +--------+---------+
                                   |
                          +--------v---------+
                          |    Persister     |
                          | (Create/Update,  |
                          |  Notify)         |
                          +------------------+
```

### How PyBend's Matrix/TX Enables This Natively

This is the critical insight: **PyBend already has the multi-agent message bus**. The Actor/Matrix/TX system is exactly the inter-agent communication layer that frameworks like LangGraph, CrewAI, and AutoGen build from scratch.

Current Matrix routing already supports:

```python
# Agent A sends a message to Agent B through Matrix
tx = TX(name='review', source='scanner', target='reviewer',
        data={'grants': [...]})
await adapter.request(tx)  # Future-based correlation
```

The routing path:

```
Scanner Agent                      Matrix                       Reviewer Agent
     |                               |                              |
     |-- TX(target='reviewer') ---->>|                              |
     |                               |-- route to child ---------->>|
     |                               |                              |-- handler()
     |                               |                              |-- process
     |                               |<<-- TX.reply() --------------|
     |<<-- correlated response ------|                              |
```

**What Matrix already provides:**

| Capability | Status | How |
|-----------|--------|-----|
| Message routing between actors | Working | `Matrix.inbox()` routes by first address segment |
| Request/response correlation | Working | `NetworkAdapter.request()` with `asyncio.Future` |
| Error propagation | Working | `TX.error()` + `is_error` property |
| Interceptors (auth, logging) | Working | `actor.use(fn, on='inbox')` |
| Actor lifecycle | Working | `register()`, `spawn()`, `has()` |
| Timeout handling | Working | `NetworkAdapter.request(tx, timeout=30)` |

**What needs to be built:**

| Capability | Effort | Description |
|-----------|--------|-------------|
| Agent-to-agent delegation | 1 day | Tool function that invokes another agent's `run()` |
| Pipeline orchestrator | 2 days | Sequential agent chaining with state passing |
| Parallel fan-out | 1 day | `asyncio.gather()` over multiple scanner runs |
| Result aggregation | 1 day | Merge results from parallel scanners |

### Agent-to-Agent Communication via Pydantic AI Delegation

[Pydantic AI's multi-agent documentation](https://ai.pydantic.dev/multi-agent-applications/) describes three coordination strategies:

1. **Agent Delegation** -- one agent calls another via a tool
2. **Programmatic Hand-off** -- application code controls agent sequencing
3. **Graph-Based Control Flow** -- state machine orchestration

For Grant Watcher, **Programmatic Hand-off** is the best fit. The pipeline stages are known and deterministic -- we don't need agents deciding who to call next. Application code orchestrates:

```python
async def scan_and_review_pipeline(sources: list, user: dict):
    """Programmatic hand-off: Scanner -> Reviewer -> Persister."""
    usage = RunUsage()

    # Phase 1: Scan all sources (parallel fan-out)
    scanner = AgentActor.get(scanner_id)
    scan_tasks = [
        scanner.run(task=f"Scan {src.url} for grants", llm=...)
        for src in sources
    ]
    raw_results = await asyncio.gather(*scan_tasks, return_exceptions=True)

    # Phase 2: Review and validate (sequential)
    reviewer = AgentActor.get(reviewer_id)
    candidates = merge_scan_results(raw_results)
    reviewed = await reviewer.run(
        task=f"Review these grant candidates: {json.dumps(candidates)}",
        llm=...
    )

    # Phase 3: Persist approved grants
    approved = json.loads(reviewed).get('approved', [])
    for grant_data in approved:
        Grant.create(Grant(**grant_data))

    return {'discovered': len(candidates), 'approved': len(approved)}
```

> **Key Insight:** We do not need to pick between "pydantic-ai orchestration" and "PyBend TX routing." The beauty of the current architecture is that **pydantic-ai handles the LLM reasoning loop** (prompt -> think -> tool call -> repeat) while **Matrix/TX handles the tool execution** (tool call -> TX -> actor -> response). Each layer does what it is good at.

### Minimum Viable Multi-Agent: Scanner + Reviewer

Before building the full pipeline, the **highest-ROI step** is adding a single Reviewer agent:

```
Current:   Scanner -----> grants_create (anything goes)
Proposed:  Scanner -----> Reviewer -----> grants_create (quality gate)
```

**Scanner agent** (existing, refined prompt):
- System prompt: "Find grants, extract data, output as JSON array"
- Tools: `sources_list`, `grants_gov_search`, `web_tools_scrape`, `web_tools_extract`
- LLM: Claude Sonnet 4.6 (good at extraction)

**Reviewer agent** (new):
- System prompt: "Validate grant data quality. Check: required fields present, deadline is future date, amounts are reasonable, no duplicates, URL is valid. Assign confidence score 0-1. Reject grants below 0.6."
- Tools: `dedup_tools_check`, `classification_tools_categorize`, `grants_get`
- LLM: Claude Sonnet 4.6 or even a local Ollama model (cheaper, validation is simpler than extraction)

This two-agent setup gives us:
- Quality gate before persistence
- Confidence scores on every grant
- Deterministic deduplication
- Separation of concerns (extraction vs. validation)

---

## Agent Memory and State

### The Problem: Stateless Agents Re-Discover the World

Each `agent_run()` today creates a transient `NetworkAdapter`, runs the LLM loop, and discards everything. The agent has no memory of:

- Which URLs it has already scraped
- Which grants it found in previous runs
- What errors it encountered
- How many tokens it used historically

This means **every run re-scrapes the same pages** and **re-discovers the same grants** (relying on the prompt's instruction to "check existing grants" -- which is unreliable and token-expensive).

### Memory Architecture Options

| Memory Type | Storage | Scope | Use Case |
|------------|---------|-------|----------|
| **Run History** | `AgentRun` model (SQLite) | Per-agent, persistent | Audit trail, debugging, cost tracking |
| **Scrape Cache** | `ScrapeCache` model | Global, TTL-based | Avoid re-scraping within 24h window |
| **Conversation History** | Pydantic AI `messages` | Per-run, ephemeral | Within-run context (already works) |
| **Semantic Memory** | Vector store (ChromaDB/SQLite-VSS) | Global, persistent | "Find grants similar to X" |
| **Task State** | JSON field on `AgentActor` | Per-agent | Checkpoint/resume for long runs |

### Recommended: Run History + Scrape Cache (Phase 1)

The most valuable memory addition is **structured run history** -- a new `AgentRun` model that records every execution:

```python
class AgentRun(ActorModel):
    """Record of a single agent execution run."""
    __tablename__ = 'agent_runs'
    __storable__ = True

    agent_id: int = Field(description="Which agent ran")
    task: str = Field(description="Task prompt")
    status: str = Field(default='running')  # running | completed | failed
    started_at: DateTimeField = Field(default_factory=datetime.utcnow)
    completed_at: Optional[DateTimeField] = None
    input_tokens: int = Field(default=0)
    output_tokens: int = Field(default=0)
    requests: int = Field(default=0)
    tool_calls: int = Field(default=0)
    grants_found: int = Field(default=0)
    grants_created: int = Field(default=0)
    errors: list = Field(default=[])
    result_summary: str = Field(default='')
```

This gives us:
- **Cost tracking**: Token usage per run, per agent, over time
- **Debugging**: What went wrong and when
- **Scheduling intelligence**: "Last successful scan was 6 hours ago"
- **Metrics dashboard**: Grants discovered per run, error rates

### Scrape Cache: Don't Re-Fetch What You Just Fetched

```python
class ScrapeCache(ActorModel):
    """Cache layer for web scrapes with TTL."""
    __tablename__ = 'scrape_cache'
    __storable__ = True

    url: UrlField = Field(description="Scraped URL")
    content_hash: str = Field(description="SHA256 of response body")
    scraped_at: DateTimeField = Field(default_factory=datetime.utcnow)
    status_code: int = Field(default=200)
    content_length: int = Field(default=0)
```

Enhanced `WebTools.scrape()` checks the cache first:

```python
@expose_route('/scrape', methods=['POST'], access=AUTHENTICATED)
async def scrape(self, url: str, max_age_hours: int = 24) -> dict:
    """Fetch URL with cache. Returns cached version if fresh enough."""
    cached = ScrapeCache.list(filters={'url': url}, limit=1)
    if cached and is_fresh(cached, max_age_hours):
        return {'url': url, 'cached': True, 'html': cached.html}
    # ... actual fetch, then cache the result
```

### Semantic Memory: Future Phase (Vector Store)

For Phase 3+, a vector store enables semantic search over discovered grants ("find grants similar to this one"). Options:

| Vector Store | Integration Effort | Pros | Cons |
|-------------|-------------------|------|------|
| **ChromaDB** | 1-2 days | Python-native, embedded, simple | Limited scale |
| **SQLite-VSS** | 1 day | Stays in SQLite ecosystem | Experimental |
| **Qdrant** | 2-3 days | Production-grade, fast | External service |
| **pgvector** | 2-3 days | Mature, well-supported | Requires PostgreSQL |

For the Grant Watcher's scale (thousands, not millions of records), **ChromaDB embedded** is the pragmatic choice. It runs in-process, stores on disk, and requires no external infrastructure.

> **Key Insight:** Do not build vector search until you have enough grants to make it useful. With fewer than 1,000 grants, SQL `LIKE` queries and keyword matching are sufficient and simpler. The Grants.gov API itself has keyword search. Add semantic memory when you have 5,000+ grants and users asking "find grants like this one."

---

## Structured Output and Validation

### The Problem: LLMs Generate Creative Garbage

Today, the Grant Scanner agent creates grants via `grants_create` tool calls. If the LLM hallucinates a deadline of "March 32nd" or sets `amount_max` to negative, the tool call goes through Matrix, hits the CRUD handler, and either:

1. Pydantic validation catches it -> `ModelRetry` exception -> LLM retries (good)
2. Pydantic doesn't catch it (it is valid but wrong) -> Bad data persists (bad)

Case 2 is the real danger. A grant with `amount_max: 999999999` or `deadline: "2020-01-01"` (past date) passes Pydantic type validation but is operationally wrong.

### Solution: Pydantic AI Structured Output + Domain Validation

[Pydantic AI supports structured output](https://ai.pydantic.dev/output/) via the `output_type` parameter. Instead of the agent returning free-text that we hope contains valid data, we can **force the LLM to produce a typed object**:

```python
from pydantic import BaseModel, Field, field_validator
from datetime import date

class GrantCandidate(BaseModel):
    """Structured output for grant extraction."""
    title: str = Field(min_length=5, max_length=500)
    agency: str = Field(min_length=1, max_length=200)
    deadline: Optional[date] = None
    amount_min: Optional[float] = Field(default=None, ge=0, le=100_000_000)
    amount_max: Optional[float] = Field(default=None, ge=0, le=100_000_000)
    url: str = Field(pattern=r'^https?://')
    description: str = Field(max_length=5000)
    confidence: float = Field(ge=0.0, le=1.0,
                              description="How confident are you in this extraction?")

    @field_validator('deadline')
    @classmethod
    def deadline_must_be_future(cls, v):
        if v and v < date.today():
            raise ValueError('Deadline must be in the future')
        return v

    @field_validator('amount_max')
    @classmethod
    def max_must_exceed_min(cls, v, info):
        if v and info.data.get('amount_min') and v < info.data['amount_min']:
            raise ValueError('amount_max must be >= amount_min')
        return v


class ScanResult(BaseModel):
    """Structured output for a scanning run."""
    grants: list[GrantCandidate]
    source_url: str
    scan_notes: str = ''
```

Using this with Pydantic AI:

```python
scanner_agent = Agent(
    'anthropic:claude-sonnet-4-5-20250929',
    system_prompt="Extract grant opportunities from the provided content...",
    output_type=ScanResult,  # Forces structured output
    deps_type=AgentDeps,
    tools=ai_tools,
)

result = await scanner_agent.run(task, deps=deps)
# result.output is a ScanResult instance -- validated, typed, guaranteed
for grant in result.output.grants:
    if grant.confidence >= 0.6:
        Grant.create(Grant(**grant.model_dump(exclude={'confidence'})))
```

### Integration Path: Structured Output in AgentMixin

The current `agent_run()` returns `{'answer': result.output, ...}` where `output` is always a string. To support structured output:

```python
async def agent_run(self, prompt: str, tools: list, task: str,
                    user: dict = None, output_type=None, **kwargs) -> dict:
    """Execute LLM reasoning loop. Supports structured output."""
    # ... existing setup ...

    ai_agent = Agent(
        llm,
        system_prompt=prompt,
        deps_type=AgentDeps,
        tools=ai_tools,
        output_type=output_type,  # NEW: pass through to pydantic-ai
    )

    result = await ai_agent.run(task, deps=deps, usage_limits=usage_limits)

    output = result.output
    if output_type and not isinstance(output, str):
        output = output.model_dump(mode='json')  # Serialize Pydantic model

    return {
        'answer': output,
        'usage': { ... },
        'messages': len(result.all_messages()),
    }
```

### Error Recovery: ModelRetry

Pydantic AI has built-in retry via `ModelRetry`. When a tool call fails validation, the error message goes back to the LLM, which adjusts and retries. The current tool code already does this:

```python
# From /workspace/src/pybend/core/agents/tools.py line 195-196
if response.is_error:
    from pydantic_ai import ModelRetry
    raise ModelRetry(response.data.get('message', 'Tool call failed'))
```

This means **validation errors from CRUD operations already trigger retries**. The LLM gets the error message and can self-correct. Adding domain-specific validators to the Grant model strengthens this chain:

```
LLM produces bad data
    -> grants_create tool call
        -> TX to Grant actor
            -> Pydantic validation fails (e.g., deadline in past)
                -> TX.error() back to adapter
                    -> ModelRetry("Deadline must be in the future")
                        -> LLM sees error, corrects, retries
```

---

## Orchestration Patterns

### Scheduling: Periodic Scans

Grant Watcher needs automated scanning, not just `POST /agents/1/run`. Options:

| Approach | Complexity | Pros | Cons |
|----------|-----------|------|------|
| **External cron** | Low | Simple, reliable, no framework changes | No visibility in app, can't adjust dynamically |
| **APScheduler** | Medium | Python-native, async-compatible | Another dependency |
| **Built-in scheduler actor** | Medium | Fully integrated, TX-based, visible in UI | Framework addition |
| **Celery/Redis** | High | Battle-tested, distributed | Infrastructure overhead |

**Recommendation**: Start with **external cron** (Phase 1), graduate to a **scheduler actor** (Phase 3).

```bash
# crontab: scan every 6 hours
0 */6 * * * curl -s -X POST http://localhost:5000/agents/1/run \
  -H "Content-Type: application/json" \
  -H "x-access-token: $AGENT_TOKEN" \
  -d '{"task": "Scan all sources for new grants"}'
```

For Phase 3, a `SchedulerActor` fits naturally into the actor model:

```python
class SchedulerActor(ActorModel):
    __tablename__ = 'schedules'
    __storable__ = True

    agent_id: int
    cron_expression: str       # "0 */6 * * *"
    task: str                  # "Scan all sources"
    enabled: bool = True
    last_run: Optional[DateTimeField] = None
    next_run: Optional[DateTimeField] = None
```

### Rate Limiting

Two rate limits matter:

1. **Source websites**: Don't hammer Grants.gov with 100 requests/second
2. **LLM API**: Stay within token/request quotas

Source rate limiting belongs in `WebTools`:

```python
import asyncio

_rate_lock = asyncio.Semaphore(3)  # Max 3 concurrent scrapes

@expose_route('/scrape', methods=['POST'], access=AUTHENTICATED)
async def scrape(self, url: str) -> dict:
    async with _rate_lock:
        await asyncio.sleep(1)  # Polite delay
        # ... actual scrape
```

LLM rate limiting uses Pydantic AI's built-in `UsageLimits`:

```python
from pydantic_ai import UsageLimits

usage_limits = UsageLimits(
    request_limit=50,           # Max 50 LLM calls per run
    total_tokens_limit=100_000, # Max 100K tokens per run
)
```

### Cost Tracking

[Langfuse](https://langfuse.com/docs/observability/features/token-and-cost-tracking), [Helicone](https://www.helicone.ai/), and [LangWatch](https://langwatch.ai/) are purpose-built for LLM cost tracking. But for Grant Watcher's scale, **the `AgentRun` model is sufficient**.

The data is already available -- `agent_run()` returns `usage.input_tokens`, `usage.output_tokens`, and `usage.requests`. We just need to persist it:

```python
# After agent_run() completes
run_record = AgentRun(
    agent_id=self.id,
    task=task,
    status='completed',
    input_tokens=result['usage']['input_tokens'],
    output_tokens=result['usage']['output_tokens'],
    requests=result['usage']['requests'],
    grants_found=len(result.get('grants', [])),
)
AgentRun.create(run_record)
```

### Cost Estimation Per Run

Based on [2026 LLM pricing data](https://www.cloudidr.com/llm-pricing):

| Model | Input $/1M tokens | Output $/1M tokens | Typical Grant Scan Run | Cost/Run |
|-------|-------------------|--------------------|-----------------------|----------|
| Claude Sonnet 4.6 | $3.00 | $15.00 | ~20K in / ~5K out | $0.135 |
| GPT-4o | $2.50 | $10.00 | ~20K in / ~5K out | $0.100 |
| GPT-5.2 | $1.75 | $14.00 | ~20K in / ~5K out | $0.105 |
| Ollama (llama3.1 local) | $0 | $0 | ~20K in / ~5K out | $0 (electricity only) |

With 4 sources scanned 4x/day = 16 runs/day:

| Model | Daily Cost | Monthly Cost |
|-------|-----------|-------------|
| Claude Sonnet 4.6 | $2.16 | ~$65 |
| GPT-4o | $1.60 | ~$48 |
| **Hybrid** (Sonnet scan + Ollama review) | $1.08 | ~$32 |
| All-local Ollama | $0 | $0 (+ ~$5 electricity) |

> **Key Insight:** At 50 sources with a two-agent pipeline scanning 4x daily, the all-cloud cost is approximately **$30-65/month**. Using local Ollama for the Reviewer agent (which does simpler validation work) halves the cloud spend. For a grant platform where a single matched grant is worth $100K+, these costs are trivial.

### Retry and Recovery

[Production resilience patterns](https://dev.to/klement_gunndu/4-fault-tolerance-patterns-every-ai-agent-needs-in-production-jih) identify four layers:

| Layer | Pattern | Implementation |
|-------|---------|---------------|
| 1 | **Retry with backoff** | `ModelRetry` for tool failures, exponential backoff for HTTP |
| 2 | **Model fallback** | Claude Sonnet -> GPT-4o -> Ollama fallback chain |
| 3 | **Error classification** | Rate limit -> retry; bad data -> reformat; auth -> abort |
| 4 | **Checkpoint/resume** | Persist partial results in `AgentRun`, resume from last checkpoint |

Implementation for Layer 2 (model fallback):

```python
FALLBACK_CHAIN = [
    'anthropic:claude-sonnet-4-5-20250929',
    'openai:gpt-4o',
    'ollama:llama3.1',
]

async def run_with_fallback(agent, task, **kwargs):
    for model in FALLBACK_CHAIN:
        try:
            return await agent.run(task=task, llm=model, **kwargs)
        except Exception as e:
            logger.warning("Model %s failed: %s. Trying next.", model, e)
    raise RuntimeError("All models in fallback chain failed")
```

### Human-in-the-Loop

For high-value grant discovery, a **review queue** pattern lets agents propose grants that humans approve:

```
Agent discovers grant
    -> Creates Grant with status='pending_review'
    -> NotificationTools.alert() notifies human
    -> Human reviews in UI, changes status to 'approved' or 'rejected'
```

This requires only a status field change on the Grant model (already has `status: str` with values `discovered | reviewed | applied | expired`) and a UI filter for pending reviews. No framework changes needed.

---

## Cost Analysis and LLM Economics

### Token Usage Breakdown

Based on Anthropic's data, agents use **4x more tokens than chat** and multi-agent systems use **~15x more tokens** ([Anthropic engineering blog](https://www.anthropic.com/engineering/multi-agent-research-system)). Token usage explains **80% of performance variance**.

For Grant Watcher specifically:

```
Single Agent Run (current):
  System prompt:          ~500 tokens
  Per-source scrape loop:
    - sources_list call:   ~200 tokens (response)
    - Per source (4 sources):
      - scrape tool call:  ~100 tokens (request) + ~10,000 tokens (HTML response)
      - extract tool call: ~100 tokens (request) + ~2,000 tokens (response)
      - grants_list call:  ~200 tokens (response, for dedup)
      - grants_create:     ~200 tokens (per grant)
  LLM reasoning:          ~2,000 tokens (thinking between tool calls)
  ─────────────────────────────────
  Total per run:          ~50,000 tokens (4 sources)
  At Claude Sonnet:       ~$0.15-$0.50 per run

Two-Agent Pipeline (proposed):
  Scanner (per source):   ~15,000 tokens (prompt + scrape + extract + think)
  Reviewer (per batch):   ~5,000 tokens (prompt + validate + dedup + classify)
  ─────────────────────────────────
  Total per run:          ~65,000 tokens (4 sources) -- 30% more tokens
  But: quality is 2-3x better (validated, deduplicated, scored)
  At hybrid pricing:      ~$0.12-$0.35 per run (reviewer on Ollama)
```

### Cost Optimization Strategies

| Strategy | Token Savings | Quality Impact |
|----------|--------------|----------------|
| **Grants.gov API instead of scraping** | 60-80% (no HTML in context) | Better (structured data) |
| **Scrape cache (24h TTL)** | 50-70% (avoid re-fetching) | Neutral |
| **Deterministic dedup tools** | 20-30% (no LLM-based duplicate checking) | Better (reliable) |
| **Smaller model for reviewer** | 40-50% (Ollama = free) | Slightly worse extraction, but validation is simpler |
| **Structured output** | 10-20% (less back-and-forth) | Better (no reformatting retries) |
| **Combined** | **70-85%** | **Significantly better** |

> **Key Insight:** The irony of tool expansion is that **more tools means fewer tokens**. A `grants_gov_search` call returns 1KB of clean JSON. A `web_tools_scrape` call returns 50KB of raw HTML that the LLM must parse. Specialized tools are cheaper *and* more accurate.

---

## Competitive Landscape

### Existing Grant Discovery Platforms

The grant discovery market is well-established. [Fundsprout's comparison of 12 platforms](https://www.fundsprout.ai/resources/grant-discovery-platforms) reveals the landscape:

| Platform | Price | Grants Indexed | Key Feature |
|----------|-------|----------------|-------------|
| **Grants.gov** | Free | All federal | Official government portal |
| **Instrumentl** | $179+/mo | 20,000+ | AI-powered matching, funder intelligence |
| **Granted AI** | Paid | 85,000+ from 144 sources | AI search + proposal drafting |
| **OpenGrants** | Low monthly | US + EU + CA + UK | AI recommendations + consultant marketplace |
| **Candid (Foundation Directory)** | Expensive | Comprehensive foundations | Deep funder profiles, 990-PF data |
| **GrantWatch** | ~$18/week | Foundation + corporate + gov | Daily-updated listings |
| **GrantForward** | Custom institutional | 20,000+ research | Profile-based researcher matching |
| **Fundsprout** | Free entry + paid tiers | 275,000+ | AI-matched, compliance tracking |

### Where Grant Watcher Fits

Grant Watcher is **not competing** with these platforms. It is:

1. **A framework demonstration** -- showing how PyBend's agent system works
2. **A self-hosted alternative** -- for organizations that want to run their own grant discovery
3. **A customizable platform** -- where the matching criteria are defined by the user, not the vendor

The competitive advantage is **ownership and customization**: you control the agents, the prompts, the scoring criteria, and the data. No vendor lock-in, no per-seat pricing, no data leaving your infrastructure (with Ollama).

### Build vs. Buy Decision Matrix

| Factor | Build (Grant Watcher) | Buy (Instrumentl/Granted AI) |
|--------|----------------------|------|
| **Monthly cost** | $5-65 (LLM + hosting) | $179-500/mo |
| **Setup time** | 2-4 weeks development | 1 hour |
| **Data coverage** | Your configured sources | Pre-indexed 20K-275K grants |
| **Customization** | Complete control | Limited to platform features |
| **Privacy** | Self-hosted, your data | SaaS, vendor holds data |
| **Matching quality** | Depends on your prompts + tools | Years of ML refinement |
| **Maintenance** | You maintain it | Vendor maintains |

**Bottom line**: If you need grant discovery *right now* and have budget, buy. If you need it customized, self-hosted, and integrated into your own platform -- or if this is a framework showcase -- build.

---

## Feasibility and ROI Assessment

### Effort Estimates by Capability

| Capability | Effort | Complexity | Dependencies |
|-----------|--------|-----------|--------------|
| GrantsGovTools (API integration) | 1 day | Low | None |
| DeduplicationTools | 0.5 day | Low | None |
| ClassificationTools | 0.5 day | Low | None |
| NotificationTools | 0.5 day | Low | None |
| Structured output support in AgentMixin | 1 day | Medium | Pydantic AI output_type |
| AgentRun model (cost tracking) | 1 day | Low | None |
| ScrapeCache model | 0.5 day | Low | None |
| Reviewer agent (seed + prompt) | 1 day | Low | DeduplicationTools |
| Pipeline orchestrator | 2 days | Medium | Reviewer agent |
| Parallel scanner fan-out | 1 day | Medium | Pipeline orchestrator |
| External cron scheduling | 0.5 day | Low | None |
| Model fallback chain | 0.5 day | Low | None |
| Scheduler actor | 2 days | Medium | None |
| Vector store integration | 3 days | High | ChromaDB |
| Human review queue UI | 2 days | Medium | Frontend changes |

### Value/Effort Matrix

```
                HIGH VALUE
                    |
  Structured Output *  * Grants.gov API
                    |
  Reviewer Agent *  |  * Dedup Tools
                    |
  Pipeline Orch. *  |  * Scrape Cache
                    |
  AgentRun Model *  |  * Classification
                    |
  ─────────────────+────────────────────
                    |          * Scheduler Actor
  Vector Store *    |
                    |     * Notification Tools
  Parallel Scans *  |
                    |
                    |        * Human Review UI
                    |
                LOW VALUE
  HIGH EFFORT ──────────── LOW EFFORT
```

**Priority order** (highest ROI first):

1. Grants.gov API tools (1 day, massive data quality improvement)
2. Deduplication tools (0.5 day, eliminates #1 data quality problem)
3. Structured output (1 day, eliminates garbage data)
4. AgentRun model (1 day, visibility into costs and performance)
5. Reviewer agent (1 day, quality gate)
6. Scrape cache (0.5 day, cost reduction)
7. Pipeline orchestrator (2 days, ties it all together)

Items 1-6 are independently valuable and can ship incrementally. Item 7 ties them together into the full multi-agent pipeline.

### Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|-----------|
| **Over-engineering** | High | Wasted dev time | Ship incrementally, prove value at each step |
| **LLM cost overrun** | Medium | Budget impact | UsageLimits, model fallback, Ollama for simple tasks |
| **Prompt brittleness** | Medium | Bad extraction quality | Structured output forces schema compliance |
| **Source website changes** | High | Broken scraping | Prefer APIs over scraping; scrape cache softens impact |
| **Agent hallucination** | Medium | Phantom grants in database | Reviewer agent + dedup tools + human review queue |
| **Complexity creep** | Medium | Unmaintainable system | Keep agents as data (AgentActor), not code |

---

## Recommended Phased Rollout

### Phase 1: Tool Expansion + Structured Output (Weeks 1-3)

**Goal**: Better data quality from the existing single agent.

**Deliverables**:
- [ ] `GrantsGovTools` actor with `search` and `detail` methods
- [ ] `DeduplicationTools` actor with `check` method
- [ ] `ClassificationTools` actor with `categorize` method
- [ ] `AgentRun` model for cost/usage tracking
- [ ] `ScrapeCache` model for URL caching
- [ ] Structured output support in `AgentMixin.agent_run()` (add `output_type` parameter)
- [ ] Updated Grant Scanner prompt to use new tools
- [ ] External cron job for periodic scanning

**Expected outcome**: 3x improvement in grant data quality. 50% reduction in duplicate records. Visibility into token costs.

**Estimated effort**: 5-7 developer-days.

### Phase 2: Two-Agent Pipeline (Weeks 4-6)

**Goal**: Quality gate between discovery and persistence.

**Deliverables**:
- [ ] Reviewer agent (AgentActor record with validation-focused prompt)
- [ ] `NotificationTools` actor for new grant alerts
- [ ] Pipeline orchestrator (async Python function, not an actor yet)
- [ ] Model fallback chain (Claude -> GPT-4o -> Ollama)
- [ ] Domain validators on Grant model (future deadlines, reasonable amounts)
- [ ] Confidence score field on Grant model

**Expected outcome**: Elimination of garbage grant records. Confidence scoring enables prioritization. Human trust in agent output increases.

**Estimated effort**: 5-7 developer-days.

### Phase 3: Parallel Scanners + Orchestrator (Weeks 7-12)

**Goal**: Scale to 50+ sources with source-type specialization.

**Deliverables**:
- [ ] Source-type scanner agents (Gov API scanner, Web scanner, RSS scanner)
- [ ] Parallel fan-out via `asyncio.gather()`
- [ ] Scheduler actor (or APScheduler integration)
- [ ] Rate limiting on WebTools and LLM calls
- [ ] Human review queue (status='pending_review' flow)
- [ ] Dashboard view for agent runs, costs, and grant statistics

**Expected outcome**: 10x source coverage. Automated daily scanning. Full cost visibility. Human-in-the-loop for high-value grants.

**Estimated effort**: 8-12 developer-days.

### Phase 4: Intelligence Layer (Future)

**Goal**: Semantic search, recommendation, trend analysis.

**Deliverables**:
- [ ] ChromaDB vector store integration
- [ ] "Find grants similar to X" capability
- [ ] Grant trend analysis (new funding areas, deadline patterns)
- [ ] User preference matching (research interests -> grant recommendations)
- [ ] Slack/email notification integration

**Estimated effort**: 10-15 developer-days.

---

## Trade-offs and Risks

### Simple Prompts vs. Complex Architectures

The single most important lesson from Anthropic's multi-agent work: **start with better prompts before adding agents** ([Anthropic](https://www.anthropic.com/engineering/multi-agent-research-system)). A well-crafted prompt with clear step-by-step instructions and structured output can capture 70% of the value of a multi-agent system at 10% of the complexity.

Before adding a Reviewer agent, try this prompt improvement on the existing Scanner:

```
You are a grant discovery agent. Output ONLY valid JSON matching this schema:
{
  "grants": [
    {
      "title": "string (5-500 chars)",
      "agency": "string",
      "deadline": "YYYY-MM-DD (must be future date)",
      "amount_min": number or null,
      "amount_max": number or null (>= amount_min),
      "url": "https://...",
      "description": "string (max 2000 chars)",
      "confidence": 0.0-1.0
    }
  ]
}

Before creating a grant, ALWAYS call dedup_tools_check first.
Only create grants with confidence >= 0.6.
```

If this prompt alone brings quality to acceptable levels, Phase 2 can be deferred. **Measure first, architect second.**

### Tool Explosion vs. Tool Composition

| Approach | # Tools | LLM Confusion Risk | Maintenance |
|----------|---------|-------------------|-------------|
| Many narrow tools | 20+ | High (LLM picks wrong tool) | High |
| Few powerful tools | 5-8 | Low | Low |
| Composable primitives | 8-12 | Medium | Medium |

[Spring AI's research on dynamic tool discovery](https://spring.io/blog/2025/12/11/spring-ai-tool-search-tools-tzolov/) found that **tool selection accuracy degrades when models face 30+ similarly-named tools**, with the "tool search tool" pattern achieving **34-64% token savings** by providing tools on-demand rather than all at once.

**Recommendation**: Keep tools under 15 per agent. Use tool descriptions as the primary disambiguation mechanism. If two tools are similar, merge them.

### Local vs. Cloud LLMs

| Dimension | Ollama (Local) | Claude/GPT (Cloud) |
|-----------|---------------|-------------------|
| **Cost** | $0 (+ electricity ~$5/mo) | $30-65/mo at grant scale |
| **Speed** | 10-50 tok/s (consumer GPU) | 80-150 tok/s |
| **Quality (extraction)** | 70-80% of Claude Sonnet | 100% (reference) |
| **Quality (validation)** | 90-95% of Claude Sonnet | 100% (reference) |
| **Privacy** | Complete | Data sent to API provider |
| **Reliability** | Depends on hardware | 99.9%+ SLA |
| **Setup** | Install Ollama + download model | API key |

**Recommendation**: **Hybrid strategy**. Use cloud LLMs (Claude Sonnet 4.6) for the Scanner agent where extraction quality matters most. Use local Ollama (llama3.1) for the Reviewer agent where the task is simpler validation. This gives **best quality where it matters** at **~50% of all-cloud cost**.

As of 2026, [self-hosted LLMs have reached cost parity with cloud APIs](https://dasroot.net/posts/2026/01/self-hosted-llm-vs-cloud-apis-cost-performance/) within 1-4 months at moderate usage, with subsequent operations 40-200% cheaper. But this requires a **$1,500-2,500 GPU investment** -- only justified at scale.

### Real-Time vs. Batch Processing

| Approach | Latency | Cost | Complexity | Use Case |
|----------|---------|------|-----------|----------|
| **Real-time** | Seconds | High (always-on LLM) | High | User-triggered searches |
| **Batch (4x/day)** | Hours | Low (scheduled runs) | Low | Background discovery |
| **Hybrid** | Mixed | Medium | Medium | Batch + on-demand API search |

Grant discovery is inherently a **batch process** -- grants do not appear in real-time, and deadlines are measured in weeks/months. A 6-hour scan cycle is more than adequate. Real-time is only needed for user-initiated searches, which the Grants.gov API already supports without any LLM involvement.

---

## Sources

1. [Multi-Agent Patterns - Pydantic AI](https://ai.pydantic.dev/multi-agent-applications/) -- Official documentation on agent delegation, programmatic hand-off, and graph-based control flow.

2. [How we built our multi-agent research system - Anthropic](https://www.anthropic.com/engineering/multi-agent-research-system) -- Orchestrator-worker pattern achieving 90.2% improvement over single-agent, token usage analysis, cost considerations.

3. [AI Agent Orchestration Patterns - Microsoft Azure Architecture Center](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns) -- Comprehensive guide to sequential, concurrent, group chat, handoff, and magentic patterns with decision criteria.

4. [Agent orchestration - OpenAI Agents SDK](https://openai.github.io/openai-agents-python/multi_agent/) -- Manager pattern (agents as tools) and decentralized pattern (handoffs).

5. [Grants.gov API Resources](https://www.grants.gov/api) -- Free, unauthenticated RESTful APIs (search2, fetchOpportunity) for federal grant search.

6. [Smart Tool Selection: 34-64% Token Savings - Spring AI](https://spring.io/blog/2025/12/11/spring-ai-tool-search-tools-tzolov/) -- Tool search tool pattern for dynamic discovery, addressing tool explosion.

7. [4 Fault Tolerance Patterns Every AI Agent Needs in Production](https://dev.to/klement_gunndu/4-fault-tolerance-patterns-every-ai-agent-needs-in-production-jih) -- Retry, fallback, error classification, checkpoint recovery. Unrecoverable failures dropped from 23% to under 2%.

8. [LLM Pricing Comparison 2026 - CloudIDR](https://www.cloudidr.com/llm-pricing) -- Claude Sonnet 4.6 at $3/$15, GPT-4o at $2.50/$10, 80% price drop from 2025 to 2026.

9. [Self-Hosted LLMs vs Cloud APIs: Cost and Performance - DasRoot](https://dasroot.net/posts/2026/01/self-hosted-llm-vs-cloud-apis-cost-performance/) -- Cost parity within 1-4 months at moderate usage, 40-200% cheaper after break-even.

10. [The 12 Best Grant Discovery Platforms - Fundsprout](https://www.fundsprout.ai/resources/grant-discovery-platforms) -- Market overview: Instrumentl ($179+/mo), Granted AI (85K+ grants), Fundsprout (275K+ opportunities).

11. [Model Usage and Cost Tracking - Langfuse](https://langfuse.com/docs/observability/features/token-and-cost-tracking) -- Open-source LLM monitoring with predefined model tokenizers.

12. [Agent Memory: How to Build Agents that Learn and Remember - Letta](https://www.letta.com/blog/agent-memory) -- Episodic, semantic, and archival memory patterns for LLM agents.

13. [Pydantic AI Output Documentation](https://ai.pydantic.dev/output/) -- Structured output via output_type parameter, native JSON Schema mode.

14. [Building Intelligent Multi-Agent Systems with Pydantic AI - DataDo](https://medium.com/@DataDo/building-intelligent-multi-agent-systems-with-pydantic-ai-f5c3d9526366) -- Practical multi-agent patterns with Pydantic AI.

15. [How Anthropic Built a Multi-Agent Research System - ByteByteGo](https://blog.bytebytego.com/p/how-anthropic-built-a-multi-agent) -- Technical analysis of Anthropic's architecture, 15x token multiplier for multi-agent.

16. [The 2026 Guide to Agentic Workflow Architectures - Stack AI](https://www.stack-ai.com/blog/the-2026-guide-to-agentic-workflow-architectures) -- Survey of orchestration frameworks and patterns.

17. [Pydantic-DeepAgents - vStorm](https://github.com/vstorm-co/pydantic-deepagents) -- Production-grade framework for autonomous agents with planning, delegation, and structured outputs on Pydantic AI.

---

*Document generated 2026-03-04. Agent system analysis based on PyBend v0.10 codebase at `/workspace/src/pybend/core/agents/` and Grant Watcher application at `/workspace/example_grants/`.*
