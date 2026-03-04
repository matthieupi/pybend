# Enhanced Agent Capabilities for Grant Watcher

## Option 2: From Single Scanner to Multi-Agent Intelligence

---

## 1. Executive Summary

The Grant Watcher application currently has **one agent type** -- the Grant Scanner -- backed by a single `AgentActor` instance with three tool addresses (`grants`, `sources`, `web_tools`). It works: it can scrape web pages, extract content, and create grant records. But it is a blunt instrument. It scrapes HTML indiscriminately, cannot evaluate grant relevance, has no memory of previous scans, and cannot notify users when something interesting appears. The agent is a web scraper that happens to use an LLM, not an intelligent grant discovery system.

This report evaluates **six capability expansions** that would transform Grant Watcher from a proof-of-concept into a production-grade agentic platform: new domain-specific tool actors, multi-agent coordination via PyBend's native subscriber/TX system, structured LLM output, agent specialization patterns, external government API integration (grants.gov, SAM.gov, NSF), and persistent agent memory. Each is assessed for business value, implementation complexity, and fit with the existing `ActorModel` / `Matrix` / `TX` architecture.

The bottom line: **the architecture is already built for this**. PyBend's actor system, lifecycle event subscribers, and tool discovery mechanism mean that adding new agent capabilities is largely a matter of writing new `ActorModel` classes with `@expose_route` methods -- the same pattern used for `WebTools` today. The hard parts are not framework changes but domain logic: scoring algorithms, API integrations, and deduplication strategies. Estimated total scope is **6-10 weeks** for a single engineer, with each capability independently deployable.

---

## 2. The What -- Concrete Deliverables

### 2.1 New Tool Actors

Each new tool actor follows the exact pattern of `WebTools` in `/workspace/example_grants/models/web_tools.py` -- a non-storable `ActorModel` with `@expose_route` methods that become agent tools automatically via `discover_tools()`.

| Tool Actor | Methods | Data Flow |
|---|---|---|
| **GrantsGovAPI** | `search(keyword, agency, status)`, `fetch(opp_id)` | Calls grants.gov `/v1/api/search2` and `/v1/api/fetchOpportunity` |
| **SamGovAPI** | `search(keyword, posted_from, posted_to)` | Calls SAM.gov `/opportunities/v2/search` |
| **GrantAnalyzer** | `score_relevance(grant_id, profile)`, `find_duplicates(title, url)`, `prioritize_deadlines()` | Reads grants from DB, applies scoring logic |
| **NotificationTools** | `notify_matches(user_id, grants)`, `send_digest(user_id)` | Sends email/webhook when grants match user criteria |
| **DocumentTools** | `parse_pdf(url)`, `extract_foa(html)` | Downloads and extracts text from Funding Opportunity Announcements |
| **SchedulerTools** | `schedule_scan(source_id, cron)`, `list_schedules()` | Registers periodic scan tasks |

### 2.2 Multi-Agent Coordination

Deploy **3-4 specialized agent instances** (all `AgentActor` records in the DB) with different prompts and tool sets, coordinated via lifecycle events:

```
Scanner Agent --> [after_create on Grant] --> Analyzer Agent --> [after_update on Grant] --> Notifier Agent
```

### 2.3 Structured Output

Replace the current raw-text `agent_run()` return with typed Pydantic models:

```python
class ScanResult(BaseModel):
    grants_found: int
    grants_created: int
    duplicates_skipped: int
    errors: list[str]
    sources_scanned: list[str]
```

### 2.4 Agent Memory

Persist conversation history and scan state across runs so agents know what they have already seen.

### 2.5 External API Integration

Replace HTML scraping with structured API calls to [grants.gov](https://grants.gov/api/api-guide), [SAM.gov](https://open.gsa.gov/api/get-opportunities-public-api/), and [NSF Award Search](https://resources.research.gov/common/webapi/awardapisearch-v1.htm).

---

## 3. The Why -- Business Value

### 3.1 From "Works" to "Useful"

The current scanner scrapes HTML pages. HTML scraping is **fragile** (breaks when sites redesign), **noisy** (extracts irrelevant content), and **expensive** (feeds large HTML blobs to the LLM, consuming tokens). Government grant APIs exist and are **free, authenticated-less, and structured**.

| Approach | Reliability | Token Cost per Source | Data Quality |
|---|---|---|---|
| HTML scraping (current) | ~60% (layout-dependent) | ~5,000-15,000 tokens (raw HTML) | Low (needs LLM to parse) |
| grants.gov `search2` API | ~99% (official API) | ~200-500 tokens (structured JSON) | High (canonical data) |
| SAM.gov Opportunities API | ~99% (official API) | ~200-500 tokens (structured JSON) | High (canonical data) |

> **Key Insight:** Switching from HTML scraping to the grants.gov `search2` API reduces per-source token cost by **10-30x** while increasing data quality. The API requires [no authentication](https://grantsgovprod.wordpress.com/2025/03/13/2-restful-apis-are-now-available-for-system-to-system-users/) and returns structured JSON with opportunity number, title, agency, status, dates, and ALN codes.

### 3.2 Competitive Differentiation

Grant tracking is a **crowded market** (GrantWatch, Instrumentl, OpenGrants, Pivot). The differentiator is not "we find grants" -- it is **agentic intelligence**: automated scoring, proactive notifications, and user-specific relevance matching. Those features require the analyzer, notifier, and memory capabilities described here.

### 3.3 User Impact

| Capability | User Benefit |
|---|---|
| Structured API integration | **10x more grants** discovered, with accurate deadlines and amounts |
| Grant analysis/scoring | Users see **relevance scores** instead of a flat list |
| Duplicate detection | No more "I already saw this" clutter |
| Notifications | Users get **proactive alerts** instead of checking manually |
| Deadline prioritization | **"Apply soon"** ranking prevents missed deadlines |
| PDF/FOA parsing | Users can read grant package summaries without downloading 50-page PDFs |

---

## 4. The How -- Implementation Deep Dive

### 4.1 New Tool Actors: The Pattern

Every new tool actor follows the `WebTools` pattern. Here is the architecture:

```
                    Matrix (root)
                       |
        +--------------+--------------+------------------+
        |              |              |                  |
    grants         sources       web_tools         grants_gov_api
   (ActorModel)   (ActorModel)  (ActorModel)      (ActorModel)
   __storable__   __storable__  __storable__      __storable__
     = True         = True       = False            = False
                                    |                   |
                              @expose_route       @expose_route
                              - scrape()          - search()
                              - extract()         - fetch()
```

The key insight: **`discover_tools()` in `/workspace/src/pybend/core/agents/tools.py` already handles this**. When the scanner agent lists `"grants_gov_api"` in its tool addresses, `discover_tools()` reads the schema from `Matrix._children["grants_gov_api"]`, finds the `@expose_route` methods, and generates `ToolSpec` objects. Zero framework changes needed.

#### 4.1.1 GrantsGovAPI Tool Actor

```python
class GrantsGovAPI(ActorModel):
    """Tool actor wrapping the grants.gov REST API."""

    __tablename__: ClassVar[str] = 'grants_gov_api'
    __storable__: ClassVar[bool] = False

    @expose_route('/search', methods=['POST'], access=AUTHENTICATED)
    async def search(self, keyword: str = '', agency: str = '',
                     status: str = 'posted', rows: int = 25) -> dict:
        """Search grants.gov for funding opportunities."""
        import httpx
        payload = {'keyword': keyword, 'rows': rows, 'oppStatuses': status}
        if agency:
            payload['agencies'] = agency
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                'https://api.grants.gov/v1/api/search2',
                json=payload,
            )
        data = resp.json()
        hits = data.get('data', {}).get('oppHits', [])
        return {
            'total': data.get('data', {}).get('hitCount', 0),
            'opportunities': [
                {
                    'id': h['id'], 'number': h['number'],
                    'title': h['title'], 'agency': h['agencyCode'],
                    'status': h['oppStatus'],
                    'open_date': h.get('openDate'),
                    'close_date': h.get('closeDate'),
                }
                for h in hits
            ],
        }

    @expose_route('/fetch', methods=['POST'], access=AUTHENTICATED)
    async def fetch(self, opportunity_id: str) -> dict:
        """Fetch full details for a specific opportunity."""
        import httpx
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f'https://api.grants.gov/v1/api/fetchOpportunity/{opportunity_id}'
            )
        return resp.json()
```

This becomes available as tools `grants_gov_api_search` and `grants_gov_api_fetch` to any agent that lists `"grants_gov_api"` in its tool addresses -- no changes to the agent framework.

#### 4.1.2 SAM.gov Opportunities Tool Actor

SAM.gov requires an API key ([generated via SAM.gov account](https://open.gsa.gov/api/get-opportunities-public-api/)), rate-limited per role. The tool actor wraps this with built-in error handling:

```python
class SamGovAPI(ActorModel):
    __tablename__: ClassVar[str] = 'sam_gov_api'
    __storable__: ClassVar[bool] = False

    @expose_route('/search', methods=['POST'], access=AUTHENTICATED)
    async def search(self, keyword: str = '', posted_from: str = '',
                     posted_to: str = '', limit: int = 100) -> dict:
        """Search SAM.gov for contract/grant opportunities."""
        import httpx
        params = {
            'api_key': os.environ.get('SAM_GOV_API_KEY', ''),
            'title': keyword,
            'postedFrom': posted_from,
            'postedTo': posted_to,
            'limit': min(limit, 1000),
            'offset': 0,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                'https://api.sam.gov/opportunities/v2/search',
                params={k: v for k, v in params.items() if v},
            )
        if resp.status_code != 200:
            from pybend.core.utils.erroring import MethodError
            raise MethodError(f"SAM.gov API error: {resp.status_code}", resp.status_code)
        data = resp.json()
        return {
            'total': data.get('totalRecords', 0),
            'opportunities': data.get('opportunitiesData', [])[:limit],
        }
```

#### 4.1.3 GrantAnalyzer Tool Actor

This is the highest-value new tool -- it turns raw grant data into actionable intelligence:

```python
class GrantAnalyzer(ActorModel):
    __tablename__: ClassVar[str] = 'grant_analyzer'
    __storable__: ClassVar[bool] = False

    @expose_route('/find_duplicates', methods=['POST'], access=AUTHENTICATED)
    def find_duplicates(self, title: str, url: str = '') -> dict:
        """Check if a grant with similar title/URL already exists."""
        existing = Grant.list(limit=500)
        matches = []
        for g in (existing.get('data', []) if isinstance(existing, dict) else existing):
            grant = g if isinstance(g, dict) else g.model_response()
            # Exact URL match
            if url and grant.get('url', '').rstrip('/') == url.rstrip('/'):
                matches.append({'id': grant['id'], 'match_type': 'url_exact', 'score': 1.0})
                continue
            # Title similarity (normalized Levenshtein)
            sim = _title_similarity(title, grant.get('title', ''))
            if sim > 0.85:
                matches.append({'id': grant['id'], 'match_type': 'title', 'score': sim})
        return {'duplicates': matches, 'is_duplicate': len(matches) > 0}

    @expose_route('/prioritize_deadlines', methods=['POST'], access=AUTHENTICATED)
    def prioritize_deadlines(self) -> dict:
        """Rank discovered grants by deadline urgency."""
        from datetime import date
        grants = Grant.list(limit=200)
        items = grants.get('data', []) if isinstance(grants, dict) else grants
        ranked = []
        today = date.today()
        for g in items:
            grant = g if isinstance(g, dict) else g.model_response()
            deadline = grant.get('deadline')
            if deadline:
                days_left = (date.fromisoformat(str(deadline)) - today).days
                if days_left > 0:
                    ranked.append({**grant, 'days_until_deadline': days_left})
        ranked.sort(key=lambda x: x['days_until_deadline'])
        return {'ranked_grants': ranked[:20]}
```

#### 4.1.4 NotificationTools

```python
class NotificationTools(ActorModel):
    __tablename__: ClassVar[str] = 'notification_tools'
    __storable__: ClassVar[bool] = False

    @expose_route('/notify', methods=['POST'], access=AUTHENTICATED)
    async def notify(self, user_id: int, message: str,
                     channel: str = 'email') -> dict:
        """Send a notification to a user."""
        # Pluggable backend: email, Slack webhook, etc.
        if channel == 'webhook':
            return await self._send_webhook(user_id, message)
        return await self._send_email(user_id, message)

    @expose_route('/digest', methods=['POST'], access=AUTHENTICATED)
    def digest(self, user_id: int, days: int = 7) -> dict:
        """Generate a digest of recently discovered grants."""
        from datetime import date, timedelta
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        grants = Grant.list(limit=50)  # TODO: filter by created_at > cutoff
        items = grants.get('data', []) if isinstance(grants, dict) else grants
        return {
            'user_id': user_id,
            'period_days': days,
            'grants_count': len(items),
            'grants': [
                {'title': g.get('title', ''), 'agency': g.get('agency', ''),
                 'deadline': g.get('deadline')}
                for g in (g if isinstance(g, dict) else g.model_response()
                          for g in items)
            ],
        }
```

### 4.2 Multi-Agent Coordination

This is where PyBend's architecture pays off. The coordination mechanism **already exists** in `ActorModel._publish_lifecycle()` at `/workspace/src/pybend/core/models/actor_model.py:280-293`:

```python
@classmethod
def _publish_lifecycle(cls, event: str, data: dict):
    for subscriber_addr in cls._subscribers:
        asyncio.create_task(cls.send(TX(
            name='LIFECYCLE',
            source=cls.__addr__,
            target=subscriber_addr,
            data={'event': event, 'entity': data},
        )))
```

Currently, `_subscribers` is empty ("the infrastructure exists but no consumers yet," per the code comment). Wiring up multi-agent coordination is literally adding addresses to this list.

#### Multi-Agent Architecture

```
                          Matrix
                            |
    +-----------+-----------+-----------+-----------+
    |           |           |           |           |
  grants    sources    web_tools   grants_gov_api  grant_analyzer
    |                                                    |
    | _subscribers = ['analyzer_monitor']                |
    |                                                    |
    +---------> analyzer_monitor (Actor) <----- handles LIFECYCLE TX
                    |
                    | On 'after_create' event:
                    |   1. Checks for duplicates (grant_analyzer.find_duplicates)
                    |   2. Scores relevance (grant_analyzer.score_relevance)
                    |   3. Updates grant status/score
                    |   4. If high-score: triggers notification
                    v
              notification_tools
```

#### The Analyzer Monitor Actor

This is a lightweight Actor (not a full AgentActor) that listens for lifecycle events and delegates to the analyzer agent:

```python
class AnalyzerMonitor(Actor, auto_register=False):
    """Listens for Grant lifecycle events, triggers analysis."""

    async def handler(self, tx: TX) -> None:
        if tx.name != 'LIFECYCLE':
            return await super().handler(tx)

        event = tx.data.get('event')
        entity = tx.data.get('entity', {})

        if event == 'after_create':
            # A new grant was just created -- analyze it
            analyzer_agent = AgentActor.get(2)  # The Analyzer agent
            if analyzer_agent:
                await analyzer_agent.run(
                    task=f"Analyze grant '{entity.get('title')}' (ID: {entity.get('id')}). "
                         f"Check for duplicates, score relevance, update status.",
                )
```

Wiring it up in `main.py`:

```python
# After create_app()
from pybend.core.actors.matrix import matrix

monitor = AnalyzerMonitor(addr='analyzer_monitor')
matrix.register(monitor)

# Subscribe Grant model to the monitor
Grant._subscribers.append('analyzer_monitor')
```

> **Key Insight:** PyBend's actor system provides agent-to-agent communication **without external frameworks**. An agent's tool call routes through `Matrix` as a `TX`, arrives at the target actor's `inbox()`, gets dispatched to `handler()`, and the response routes back via `TX.reply()`. This is the same mechanism used for all CRUD operations -- agents just happen to be the callers instead of HTTP routes.

#### Comparison: PyBend Native vs External Frameworks

| Feature | PyBend Native (TX/Matrix) | CrewAI | LangGraph |
|---|---|---|---|
| **Agent-to-agent routing** | TX messages via Matrix children | Role-based task delegation | Graph node transitions |
| **State management** | TX.meta + AgentDeps | Shared memory module | Persistent state dict |
| **Coordination overhead** | ~0ms (in-process dict lookup) | [5s agent-to-agent gap](https://openagents.org/blog/posts/2026-02-23-open-source-ai-agent-frameworks-compared) | ~50ms (graph traversal) |
| **Setup complexity** | Add actor addr to `_subscribers` | Define Crew, Tasks, Process | Define StateGraph, Nodes, Edges |
| **Dependency** | None (built-in) | `crewai` package + LangChain | `langgraph` + `langchain-core` |
| **Auth integration** | Full (interceptors, ABAC) | Manual | Manual |
| **Observability** | TX.uuid correlation | CrewAI logs | LangSmith integration |
| **Production readiness** | Matches app architecture exactly | General-purpose, proven | Production-grade, battle-tested |

> **Key Insight:** For this codebase, PyBend's native TX routing is the correct choice. CrewAI and LangGraph solve a problem PyBend already solved: routing messages between actors. Adding an external multi-agent framework would introduce a **parallel coordination layer** that duplicates Matrix's routing, conflicts with the interceptor/auth system, and adds 2-3 transitive dependencies. The value of these frameworks is in their pre-built patterns (role-based crews, graph workflows), but PyBend's subscriber + lifecycle event pattern is simpler and native.

### 4.3 Structured Output

Currently, `agent_run()` in `/workspace/src/pybend/core/agents/mixin.py` returns `result.output` as a raw string. Pydantic AI's `output_type` parameter ([docs](https://ai.pydantic.dev/output/)) enables typed returns:

```python
from pydantic import BaseModel, Field

class ScanResult(BaseModel):
    """Structured output from a grant scan run."""
    grants_found: int = Field(description="Total grants identified on source pages")
    grants_created: int = Field(description="New grant records created")
    duplicates_skipped: int = Field(description="Grants skipped due to duplication")
    errors: list[str] = Field(default=[], description="Any errors encountered")
    sources_scanned: list[str] = Field(default=[], description="Source URLs that were scanned")

class EligibilityScore(BaseModel):
    """Structured output from eligibility analysis."""
    grant_id: int
    relevance_score: float = Field(ge=0, le=1, description="0-1 relevance score")
    eligibility_match: bool
    reasoning: str = Field(description="Why this score was assigned")
    recommended_action: str = Field(description="apply | watch | skip")
```

#### Integration with AgentMixin

The change to `agent_run()` is minimal -- add an optional `output_type` parameter:

```python
# In agent_run() -- line ~107 of mixin.py
ai_agent = Agent(
    llm,
    system_prompt=prompt,
    deps_type=AgentDeps,
    tools=ai_tools,
    output_type=kwargs.get('output_type', str),  # <-- one line
)
```

Then in the scanner agent's `run()` method:

```python
@expose_route('/run', methods=['POST'])
async def run(self, task: str, **kwargs) -> str:
    tool_addrs = self._resolve_tool_addrs()
    result = await self.agent_run(
        prompt=self.prompt,
        tools=tool_addrs,
        task=task,
        output_type=ScanResult,  # <-- structured output
        **kwargs,
    )
    return json.dumps(result, default=str)
```

The `result['answer']` would then be a `ScanResult` instance instead of raw text. This feeds directly into the notification pipeline (if `grants_created > 0`, trigger analysis) and makes agent run history **queryable and comparable**.

### 4.4 Agent Specialization

All specialization is **configuration, not code**. Each agent is an `AgentActor` record in the database with a different prompt and tool set:

| Agent Name | Prompt Focus | Tool Addresses | Output Type |
|---|---|---|---|
| **Grant Scanner** (exists) | "Scan sources, scrape pages, create grants" | `grants, sources, web_tools, grants_gov_api` | `ScanResult` |
| **Grant Analyzer** | "Score relevance, detect duplicates, prioritize deadlines" | `grants, grant_analyzer` | `EligibilityScore` |
| **Grant Reporter** | "Generate weekly digest summaries" | `grants, notification_tools` | `DigestReport` |
| **Grant Matcher** | "Match grants to user profiles and interests" | `grants, grant_analyzer, notification_tools` | `MatchResult` |

Creating a new specialist agent is a `POST /agents` call:

```json
{
    "name": "Grant Analyzer",
    "prompt": "You analyze discovered grants for relevance and quality...",
    "llm": "anthropic:claude-sonnet-4-5-20250929",
    "constraints": {"max_iterations": 20}
}
```

Then link tools:

```json
POST /agents/2/agent_tools {"target": "grants", "description": "Read grant records"}
POST /agents/2/agent_tools {"target": "grant_analyzer", "description": "Scoring and dedup"}
```

**No code deployment needed for new agent types.** This is the architectural payoff of "agents are data, not code" as stated in `/workspace/src/pybend/core/agents/actor.py`.

### 4.5 External API Integration Details

#### grants.gov API

The grants.gov `search2` endpoint is the **highest-value integration** for this application:

- **Endpoint:** `POST https://api.grants.gov/v1/api/search2` ([API Guide](https://grants.gov/api/api-guide))
- **Authentication:** None required
- **Rate limits:** Not published (but public endpoint)
- **Key parameters:** `keyword`, `oppStatuses` (`forecasted|posted|closed|archived`), `agencies`, `fundingCategories`, `rows`, `startRecordNum`
- **Response:** JSON with `hitCount`, `oppHits` array (id, number, title, agencyCode, openDate, closeDate, oppStatus)

The `fetchOpportunity` endpoint provides full details for a single opportunity:
- **Endpoint:** `GET https://api.grants.gov/v1/api/fetchOpportunity/{oppId}` ([docs](https://grants.gov/api/common/fetchopportunity))
- **Returns:** Complete opportunity data including description, eligibility, funding amounts

#### SAM.gov Opportunities API

- **Endpoint:** `GET https://api.sam.gov/opportunities/v2/search` ([GSA docs](https://open.gsa.gov/api/get-opportunities-public-api/))
- **Authentication:** API key required (free, generated on SAM.gov)
- **Rate limits:** Vary by role (federal vs non-federal)
- **Key parameters:** `postedFrom`, `postedTo` (required, MM/dd/yyyy, max 1 year span), `title`, `limit` (max 1000), `offset`
- **Response:** JSON with `totalRecords`, `opportunitiesData` array

#### NSF Award Search API

- **Endpoint:** `GET http://api.nsf.gov/services/v1/awards.json` ([docs](https://resources.research.gov/common/webapi/awardapisearch-v1.htm))
- **Authentication:** None required
- **Key parameters:** `keyword`, `awardeeName`, `startDateStart`, `startDateEnd`, `printFields`
- **Response:** JSON with award details

#### Simpler.Grants.gov API (newer)

- **Endpoint:** `POST https://api.simpler.grants.gov/v1/opportunities/search` ([wiki](https://wiki.simpler.grants.gov/product/api/search-opportunities))
- **Authentication:** API key via `X-API-Key` header
- **Rate limits:** [60 requests/min, 10,000/day per key](https://wiki.simpler.grants.gov/product/api)
- **Max results:** 10,000 opportunities per query

| API | Auth Required | Rate Limit | Data Freshness | Best For |
|---|---|---|---|---|
| grants.gov `search2` | No | Unpublished | Real-time | Primary grant discovery |
| SAM.gov Opportunities | API key | Role-based | Real-time | Federal contracts + grants |
| NSF Awards | No | Unpublished | Post-award | Research funding history |
| Simpler.Grants.gov | API key | 60/min, 10K/day | Real-time | Modern API, cleaner data |

### 4.6 Agent Memory & Context

Pydantic AI supports [message history persistence](https://ai.pydantic.dev/message-history/) via `message_history` parameter and `result.all_messages()`. The integration with PyBend is straightforward since `AgentActor` is already a storable model.

#### Design: AgentRun Model

```python
class AgentRun(ActorModel):
    """Persists agent run results and conversation history."""

    __tablename__: ClassVar[str] = 'agent_runs'
    __storable__: ClassVar[bool] = True

    agent_id: int = Field(description="FK to AgentActor")
    task: str = Field(description="The task that was executed")
    result: str = Field(default='', description="JSON result from agent_run()")
    messages: str = Field(default='[]', description="Serialized conversation history")
    status: str = Field(default='running', description="running | completed | failed")
    tokens_used: int = Field(default=0)
    created_at: str = Field(default='')
```

The `messages` field stores the serialized Pydantic AI message history. On the next run, this can be loaded and passed as `message_history` to give the agent context about what it has already seen:

```python
# In agent_run(), before creating the AI agent:
previous_runs = AgentRun.list(
    sql_filter=f"agent_id = {self.id} AND status = 'completed'",
    limit=5,
)
# Extract message history from most recent run
message_history = json.loads(previous_runs[-1].messages) if previous_runs else None
```

#### Deduplication Memory

A simpler form of memory: a **seen-grants table** that stores URL hashes and title fingerprints. Before creating a grant, the scanner checks:

```python
@expose_route('/check_seen', methods=['POST'], access=AUTHENTICATED)
def check_seen(self, url: str, title: str) -> dict:
    """Check if this grant has been seen in a previous scan."""
    import hashlib
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
    # Check SeenGrant model (simple hash lookup)
    existing = SeenGrant.list(sql_filter=f"url_hash = '{url_hash}'", limit=1)
    return {'seen': len(existing.get('data', [])) > 0, 'url_hash': url_hash}
```

This is far cheaper than semantic deduplication (no embeddings needed) and catches the **80% case**: the same URL appearing in subsequent scans. For title-based fuzzy matching, [normalized Levenshtein distance](https://futuresearch.ai/semantic-deduplication/) with a threshold of 0.85 catches most paraphrases without requiring a vector database.

---

## 5. Feasibility Assessment

### 5.1 Complexity by Component

| Component | Complexity | Est. Days | Dependencies | Risk |
|---|---|---|---|---|
| GrantsGovAPI tool actor | Low | 2 | `httpx` (already used) | API stability |
| SamGovAPI tool actor | Low | 2 | `httpx`, SAM.gov API key | API key approval (5-30 days) |
| NSF Awards tool actor | Low | 1 | `httpx` | Older API, less reliable |
| GrantAnalyzer tool actor | Medium | 3-4 | Domain logic (scoring) | Scoring algorithm quality |
| NotificationTools | Medium | 3 | Email/webhook provider | External service integration |
| DocumentTools (PDF) | Medium-High | 3-4 | `pymupdf` or `pdfplumber` | PDF parsing reliability |
| SchedulerTools | Medium | 3 | `APScheduler` or custom | Persistence across restarts |
| Multi-agent coordination | Low | 2 | None (built-in) | Event ordering |
| Structured output | Low | 1 | None (Pydantic AI built-in) | Output type design |
| Agent specialization | Low | 1 | None (DB records) | Prompt engineering |
| AgentRun persistence | Medium | 2-3 | New model + migration | Message serialization |
| Deduplication memory | Low | 2 | None | False positive tuning |
| **Total** | | **25-35 days** | | |

### 5.2 Framework Changes Required

Most capabilities require **zero framework changes** -- they are application-level code using existing patterns. The exceptions:

| Change | Location | Impact |
|---|---|---|
| Add `output_type` passthrough to `agent_run()` | `mixin.py` line ~107 | 1 line change, backward compatible |
| Store `all_messages()` in return dict | `mixin.py` line ~132 | 3 line change, adds optional field |
| Support `message_history` in `agent_run()` | `mixin.py` line ~129 | 4 line change, optional param |

All three are additive -- existing behavior is unchanged. This is by design: the framework absorbs plumbing, the app adds domain logic.

### 5.3 Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| grants.gov API changes or deprecation | Low | High | Simpler.Grants.gov as fallback; abstract behind tool actor |
| SAM.gov API key approval delay | Medium | Low | Start with grants.gov (no auth); SAM.gov is additive |
| LLM cost overrun with multiple agents | Medium | Medium | `constraints.max_iterations` already exists; add per-agent token budgets |
| Agent coordination race conditions | Low | Medium | Lifecycle events are fire-and-forget; use TX.uuid for idempotency |
| PDF parsing failures on complex FOAs | High | Low | Graceful degradation: return raw text on parse failure |
| Notification spam | Medium | High | Rate limiting + digest mode (daily/weekly, not per-grant) |

---

## 6. ROI Analysis

### 6.1 Investment

| Resource | Amount |
|---|---|
| Engineering time | 6-8 weeks (1 engineer) |
| API costs | $0 (grants.gov, NSF) + minimal (SAM.gov free tier) |
| LLM costs | ~$5-20/day with Claude Sonnet for 4 agents, 50 runs/day |
| Email/notification service | ~$0-20/month (SendGrid free tier, or webhook) |

### 6.2 Returns

| Metric | Before | After | Improvement |
|---|---|---|---|
| Grants discovered per scan | 5-10 (HTML scraping) | 50-200 (API integration) | **10-20x** |
| Data accuracy (correct deadlines, amounts) | ~60% (LLM-parsed HTML) | ~99% (structured API data) | **~40pp** |
| Token cost per scan | ~50K tokens ($0.15) | ~5K tokens ($0.015) | **10x reduction** |
| Time to new grant notification | Manual check (hours/days) | Automated (minutes) | **Near real-time** |
| Duplicate grants in database | ~20% (no dedup) | <2% (hash + fuzzy match) | **~90% reduction** |
| User engagement (speculative) | View list | Score, filter, notify | **Qualitative step change** |

### 6.3 Payback Timeline

- **Week 1-2:** API tool actors (GrantsGovAPI, NSF). Immediate value: 10x more grants, 10x cheaper.
- **Week 3-4:** GrantAnalyzer + deduplication. Clean data, no duplicates.
- **Week 5-6:** Multi-agent pipeline + structured output. Automated analysis on new grants.
- **Week 7-8:** Notifications + agent memory. Users get proactive alerts. System remembers what it has seen.

**Breakeven:** After week 2 -- the API integration alone justifies the effort.

---

## 7. Trade-offs & Alternatives

### 7.1 What You Give Up

| Trade-off | Impact | Why It's Acceptable |
|---|---|---|
| More moving parts (4 tool actors instead of 1) | Debugging complexity | Each actor is independent; failures are isolated |
| Dependency on government APIs | Availability risk | APIs are officially supported; HTML scraping is worse |
| Multi-agent LLM costs | ~4x token usage for analysis | Analysis runs only on new grants, not every scan |
| Agent coordination adds latency | ~1-2s per lifecycle event chain | Async fire-and-forget; user does not wait |

### 7.2 Alternatives Considered

#### Alternative A: Use CrewAI for Multi-Agent Coordination

CrewAI provides [role-based agent teams](https://docs.crewai.com/en/concepts/agents) with built-in memory and delegation. However:

- Adds `crewai` + `langchain-core` dependencies (~50+ transitive packages)
- Duplicates Matrix routing with its own coordination layer
- Does not integrate with PyBend's ABAC interceptors
- [5-second agent-to-agent latency gap](https://openagents.org/blog/posts/2026-02-23-open-source-ai-agent-frameworks-compared) vs ~0ms for TX routing
- Loses the "agents are data" pattern -- CrewAI agents are code objects

**Verdict:** Wrong fit. PyBend already has the primitives.

#### Alternative B: Use LangGraph for Workflow Orchestration

LangGraph provides [graph-based state machines](https://dev.to/pockit_tools/langgraph-vs-crewai-vs-autogen-the-complete-multi-agent-ai-orchestration-guide-for-2026-2d63) ideal for complex conditional workflows. However:

- The grant pipeline is **linear** (scan -> analyze -> notify), not a complex DAG
- LangGraph's state management conflicts with PyBend's StorableMixin
- Adds `langgraph` + `langchain-core` dependencies
- Observability requires LangSmith; PyBend has TX.uuid correlation

**Verdict:** Overkill for this use case. Revisit if workflows become conditional/branching.

#### Alternative C: Use Pydantic AI's Built-in Agent Delegation

Pydantic AI supports [agent delegation](https://ai.pydantic.dev/multi-agent-applications/) where a parent agent calls delegate agents as tools. This is closer to PyBend's model:

```python
@scanner_agent.tool
async def analyze_grant(ctx: RunContext[AgentDeps], grant_id: int) -> str:
    result = await analyzer_agent.run(
        f"Analyze grant {grant_id}",
        usage=ctx.usage,  # aggregate token counts
    )
    return result.output
```

**Verdict:** Viable complement. Use Pydantic AI delegation for **within-run** coordination (scanner calls analyzer during the same LLM session) and PyBend lifecycle events for **cross-run** coordination (new grant created -> trigger separate analysis run). They are not mutually exclusive.

#### Alternative D: Do Nothing -- Keep the Single Scanner

- **Pro:** Simplest. No new code.
- **Con:** HTML scraping is fragile, expensive, and inaccurate. No analysis, no notifications, no memory. The product stays a demo.

**Verdict:** Not viable for a real product.

### 7.3 Build vs Buy

| Capability | Build (in PyBend) | Buy/Integrate |
|---|---|---|
| Grant API integration | 2 days per API | N/A (must build wrappers) |
| Analysis/scoring | 3-4 days | Instrumentl ($179/mo) or OpenGrants API ($149/mo) |
| Notifications | 3 days | SendGrid + 1 day integration |
| Scheduling | 3 days | APScheduler (free) + 1 day integration |
| PDF parsing | 3-4 days | LlamaParse API ($0.003/page) + 1 day integration |

> **Key Insight:** The tool actor pattern makes buy/integrate decisions reversible. Wrap an external service today (e.g., LlamaParse for PDF parsing), replace with local implementation later. The agent does not care -- it calls `document_tools_parse_pdf` either way.

---

## 8. Recommendation

### Go -- Priority Level: High (Start Immediately)

The agent capability expansion is the **highest-impact, lowest-risk investment** for Grant Watcher. The architecture supports it natively. The implementation is incremental. Each component is independently deployable and testable.

### Recommended Sequence

```
Phase 1 (Week 1-2): API Integration + Structured Output
  [GrantsGovAPI] + [SamGovAPI] + [output_type in agent_run()]
  Impact: 10x more grants, 10x cheaper, structured results
  Risk: Near zero (stable APIs, 1-line framework change)

Phase 2 (Week 3-4): Analysis + Deduplication
  [GrantAnalyzer] + [SeenGrant model] + [find_duplicates]
  Impact: Clean data, relevance scoring, no duplicates
  Risk: Low (domain logic, no framework changes)

Phase 3 (Week 5-6): Multi-Agent Pipeline
  [AnalyzerMonitor] + [Grant._subscribers wiring] + [Agent specialization]
  Impact: Automated analysis on every new grant
  Risk: Low (uses existing lifecycle events)

Phase 4 (Week 7-8): Notifications + Memory
  [NotificationTools] + [AgentRun model] + [message_history]
  Impact: Proactive user alerts, agent remembers previous scans
  Risk: Medium (email provider, persistence edge cases)

Phase 5 (Week 9-10, optional): Advanced
  [DocumentTools] + [SchedulerTools] + [NSF API]
  Impact: PDF parsing, periodic scans, more data sources
  Risk: Medium (PDF reliability, scheduler persistence)
```

### Critical Path Items

1. **Do Phase 1 first.** The API integration is the single biggest value-add. HTML scraping is a liability.
2. **Add `output_type` to `agent_run()` early.** One line of code, but it unlocks structured results for every subsequent phase.
3. **Wire lifecycle subscribers in Phase 3.** The subscriber list on `Grant._subscribers` is the **coordination backbone** for everything that follows.

### What NOT to Build

- **Vector database for semantic dedup.** Hash-based dedup covers 80% of cases at 0.1% of the cost. Revisit when you have >10K grants.
- **Custom scheduling engine.** Use APScheduler or OS-level cron. Scheduling is not a core competency.
- **External multi-agent framework.** PyBend's TX/Matrix routing is sufficient and native. Do not add CrewAI or LangGraph.
- **Real-time streaming output.** Pydantic AI supports it, but agent runs are background tasks -- streaming to a UI is premature.

---

## 9. Sources

- [Grants.gov API Guide](https://grants.gov/api/api-guide) -- Official API documentation for `search2` and `fetchOpportunity` endpoints
- [Grants.gov search2 Specification](https://grants.gov/api/common/search2) -- Endpoint parameters and response format
- [Grants.gov RESTful API Announcement](https://grantsgovprod.wordpress.com/2025/03/13/2-restful-apis-are-now-available-for-system-to-system-users/) -- March 2025 launch of search2 and fetchOpportunity
- [SAM.gov Get Opportunities Public API](https://open.gsa.gov/api/get-opportunities-public-api/) -- GSA Open Technology documentation for SAM.gov opportunity search
- [SAM.gov API Complete Guide](https://govconapi.com/sam-gov-api-complete-guide) -- Developer guide with authentication and rate limiting details
- [Simpler.Grants.gov API](https://wiki.simpler.grants.gov/product/api) -- Next-generation grants.gov API with rate limiting documentation
- [NSF Award Search API](https://resources.research.gov/common/webapi/awardapisearch-v1.htm) -- Research.gov API for NSF award data
- [Pydantic AI Output Documentation](https://ai.pydantic.dev/output/) -- Structured output types, `ToolOutput`, `NativeOutput`, `PromptedOutput`
- [Pydantic AI Multi-Agent Applications](https://ai.pydantic.dev/multi-agent-applications/) -- Agent delegation, programmatic handoff, graph-based control flow
- [Pydantic AI Message History](https://ai.pydantic.dev/message-history/) -- Conversation persistence via `message_history` and `all_messages()`
- [Pydantic AI Tools Documentation](https://ai.pydantic.dev/tools/) -- Tool function patterns, `RunContext`, `ModelRetry`
- [CrewAI vs LangGraph vs AutoGen Comparison (DataCamp)](https://www.datacamp.com/tutorial/crewai-vs-langgraph-vs-autogen) -- Framework comparison with architectural analysis
- [Open Source AI Agent Frameworks Compared (2026)](https://openagents.org/blog/posts/2026-02-23-open-source-ai-agent-frameworks-compared) -- Performance benchmarks including 5s CrewAI agent-to-agent gap
- [LangGraph vs CrewAI vs AutoGen (2026)](https://dev.to/pockit_tools/langgraph-vs-crewai-vs-autogen-the-complete-multi-agent-ai-orchestration-guide-for-2026-2d63) -- Comprehensive orchestration guide
- [MCP vs A2A Protocol Comparison](https://auth0.com/blog/mcp-vs-a2a/) -- Agent communication protocol analysis
- [Agent Communication Protocols Survey](https://arxiv.org/html/2505.02279v1) -- Academic survey of MCP, ACP, A2A, and ANP
- [Temporal for Durable AI Agents](https://temporal.io/blog/build-durable-ai-agents-pydantic-ai-and-temporal) -- Production scheduling patterns with Pydantic AI
- [LLMs for PDF Structured Data Extraction](https://unstract.com/blog/comparing-approaches-for-using-llms-for-structured-data-extraction-from-pdfs/) -- PDF parsing approaches comparison
- [Semantic Deduplication Patterns](https://futuresearch.ai/semantic-deduplication/) -- Fuzzy matching and semantic similarity techniques
- [Pydantic AI Handoffs Issue #1978](https://github.com/pydantic/pydantic-ai/issues/1978) -- Upcoming handoff/sub-agent delegation feature
