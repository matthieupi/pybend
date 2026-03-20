# Architecture Patterns: Veille

**Domain:** Agentic grant monitoring application
**Framework:** N3TX Level 3 (ActorModel + actor routing + agents)
**Researched:** 2026-03-20

---

## Recommended Architecture

Veille is a Level 3 N3TX application: every model extends `ActorModel`, HTTP routes go through the `NetworkAPI` adapter via the Matrix, and agents use `AgentMixin` for LLM-powered scraping and analysis.

```
                     +-----------------------+
                     |   FastAPI (ASGI)      |
                     |  NetworkAPI adapter   |
                     |  auth_interceptor     |
                     +-----------+-----------+
                                 |  TX messages
                     +-----------v-----------+
                     |       Matrix          |
                     |  (root actor router)  |
                     +-----------+-----------+
                                 |
          +----------+-----------+-----------+----------+----------+
          |          |           |           |          |          |
     +----v---+ +---v----+ +---v-----+ +---v---+ +---v----+ +---v-------+
     | Source | | Grant  | |  Run    | |Report | | Org    | | WebTools  |
     |        | |        | | (Agent) | |       | |Profile | | (Agent)   |
     +--------+ +--------+ +---------+ +-------+ +--------+ +-----------+
         ActorModel  ActorModel  ActorModel  ActorModel  ActorModel  ActorModel
         __storable__  __storable__  __storable__  __storable__  __storable__  NON-STORABLE
                                  __agent__=True                     __agent__=True
```

### Design Rationale

**Why Level 3 (not Level 1/2):** The scraping/analysis workflow requires actors sending TX messages to each other -- a Run actor triggers WebTools to scrape, creates Grants, then triggers analysis. Level 3 routes everything through Matrix, so tool calls during agent execution naturally use the same TX routing as CRUD operations. Level 1/2 would require direct function calls, losing the actor topology benefits.

**Why two agents (Run + WebTools), not one mega-agent or five specialized agents:** The Run agent orchestrates the entire workflow using other actors as tools. WebTools provides low-level web capabilities (fetch, extract, parse) as stateless tool endpoints. This separation means WebTools is reusable by future agents (e.g., a source-discovery agent) without coupling to Run's workflow. Conversely, splitting into separate ScrapingAgent/AnalysisAgent/ReportAgent creates unnecessary coordination overhead -- the LLM loses context between agent invocations.

### Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| `User` | Authentication, JWT tokens, role management | All models (via auth context) |
| `Organization` | Singleton org profile for admissibility matching | Run (read by agent for context) |
| `Source` | Stores scraping source URLs and metadata | Run (provides sources to scrape) |
| `Grant` | Stores discovered grants with details + admissibility | Run (creates/updates), Source (origin FK) |
| `Run` | Orchestrates scraping + analysis execution (agent) | Source, Grant, Organization, WebTools, Report (as tools) |
| `Report` | Stores end-of-run summary document | Run (creates report as final step) |
| `WebTools` | HTTP scraping + content extraction utilities (agent) | Run (called as tool during execution) |

---

## Proposed Model Definitions

### 1. Organization (singleton profile)

The organization profile is a singleton -- one record per deployment. All admissibility analysis references this profile.

```python
class Organization(ActorModel):
    __tablename__ = 'organizations'
    __storable__ = True
    __access__ = {
        'read': AUTHENTICATED,
        'create': ROLE('admin'),
        'update': AUTHENTICATED,
        'delete': ROLE('admin'),
    }
    __ui__ = {
        'field_order': ['name', 'mission', 'legal_status', 'location',
                        'focus_areas', 'past_grants', 'custom_criteria'],
        'groups': {
            'Identity': ['name', 'mission', 'legal_status', 'location'],
            'Eligibility': ['focus_areas', 'past_grants', 'custom_criteria'],
        },
    }

    # Identity
    name: str = Field(min_length=1, max_length=300)
    mission: str = Field(default='')               # textarea widget
    legal_status: str = Field(default='')           # e.g., "registered charity"
    location: str = Field(default='')               # e.g., "Yellowknife, NT, Canada"

    # Eligibility context (stored as JSON TEXT in SQLite automatically)
    focus_areas: list = Field(default_factory=list)  # ["francophone services", "health"]
    past_grants: list = Field(default_factory=list)  # [{name, funder, year, amount}]
    custom_criteria: dict = Field(default_factory=dict)  # {budget_size: "500K", employees: 12}
```

**Rationale:**
- Single record, stored in DB (not config file) so it can be edited via UI and read by agents.
- `focus_areas`, `past_grants`, `custom_criteria` are JSON fields -- N3TX auto-serializes `list`/`dict` fields to JSON TEXT in SQLite.
- No `__agent__` flag. Organization is data that agents read, not an entity that reasons.

### 2. Source

A website or page to scrape for grant opportunities.

```python
class Source(ActorModel):
    __tablename__ = 'sources'
    __storable__ = True
    __access__ = {
        'read': AUTHENTICATED,
        'create': AUTHENTICATED,
        'update': AUTHENTICATED,
        'delete': ROLE('admin'),
    }
    __ui__ = {
        'field_order': ['name', 'url', 'description', 'language',
                        'agent_discovered', 'scraping_notes', 'last_scraped', 'active'],
    }

    name: str = Field(min_length=1, max_length=300)
    url: str = Field(min_length=1)                   # base URL to scrape
    description: str = Field(default='')              # what this source provides
    language: str = Field(default='en')               # 'en', 'fr', or 'bi' (bilingual)
    scraping_notes: str = Field(default='')           # hints for the scraping agent
    agent_discovered: bool = Field(default=False)     # True if agent found this
    last_scraped: Optional[str] = Field(default=None) # ISO datetime of last scrape
    active: bool = Field(default=True)                # can be deactivated without deleting
```

**Rationale:**
- No `__agent__` flag. Sources are passive data read by the Run agent.
- `agent_discovered` distinguishes human-curated sources from agent-found ones.
- `scraping_notes` lets admins give per-source hints (e.g., "grants listed under /funding, French only").
- `active` flag allows deactivation without deletion.

### 3. Grant

A specific funding program or grant opportunity.

```python
class Grant(ActorModel):
    __tablename__ = 'grants'
    __storable__ = True
    __access__ = {
        'read': AUTHENTICATED,
        'create': AUTHENTICATED,
        'update': AUTHENTICATED,
        'delete': ROLE('admin'),
    }
    __ui__ = {
        'field_order': ['title', 'funder', 'status', 'amount_min', 'amount_max',
                        'deadline', 'url', 'source_url', 'description',
                        'eligibility_criteria', 'required_documents',
                        'application_process', 'admissibility_score',
                        'admissibility_reasoning'],
        'groups': {
            'Overview': ['title', 'funder', 'status', 'url', 'source_url'],
            'Funding': ['amount_min', 'amount_max', 'deadline'],
            'Details': ['description', 'eligibility_criteria',
                        'required_documents', 'application_process'],
            'Analysis': ['admissibility_score', 'admissibility_reasoning'],
        },
    }

    # Core identification
    title: str = Field(min_length=1, max_length=500)
    funder: str = Field(default='')
    url: str = Field(default='')                    # direct URL to the grant page
    source_url: str = Field(default='')             # the Source URL where it was found

    # Details (extracted by agent)
    description: str = Field(default='')
    amount_min: Optional[float] = Field(default=None)
    amount_max: Optional[float] = Field(default=None)
    deadline: Optional[str] = Field(default=None)   # ISO date or "ongoing"
    eligibility_criteria: list = Field(default_factory=list)  # list of criteria strings
    required_documents: list = Field(default_factory=list)    # list of required doc names
    application_process: str = Field(default='')

    # Admissibility (set by analysis agent)
    status: str = Field(default='new')
        # Values: 'new', 'analyzed', 'admissible', 'partial', 'non_admissible'
    admissibility_score: Optional[float] = Field(default=None)  # 0.0 to 1.0
    admissibility_reasoning: str = Field(default='')

    # Metadata
    language: str = Field(default='en')
    discovered_at: Optional[str] = Field(default=None)  # ISO datetime
    run_id: Optional[int] = Field(default=None)         # which Run found this
    source_id: Optional[int] = Field(default=None)      # FK to Source (manual int, not Ref)
```

**Rationale:**
- `status` is a string enum with lifecycle: new -> analyzed -> (admissible | partial | non_admissible).
- `source_id` and `run_id` are plain integer FKs, not `Ref` or `ListRef`. This keeps Grant decoupled -- it doesn't import Source or Run.
- `eligibility_criteria` and `required_documents` are JSON lists extracted by the agent.
- `admissibility_reasoning` stores the full LLM justification. This is the key output users read.

### 4. Run (core orchestrating agent)

A scraping + analysis execution. This is the core agent that orchestrates the entire workflow.

```python
class Run(ActorModel):
    __tablename__ = 'runs'
    __storable__ = True
    __agent__: ClassVar = {
        'self_tools': True,      # can update own status/counters
        'neighbors': False,      # explicit tool list, not auto-discovered
        'tools': ['sources', 'grants', 'organizations', 'reports', 'web_tools'],
        'constraints': {'max_iterations': 50},
    }
    __access__ = {
        'read': AUTHENTICATED,
        'create': AUTHENTICATED,
        'update': AUTHENTICATED,
        'delete': ROLE('admin'),
    }
    __ui__ = {
        'field_order': ['status', 'mode', 'target_url', 'started_at',
                        'completed_at', 'grants_found', 'grants_admissible',
                        'error_log'],
    }

    # Execution state
    status: str = Field(default='pending')
        # Values: 'pending', 'running', 'completed', 'failed'
    mode: str = Field(default='full')
        # Values: 'full' (all sources), 'single' (one URL), 'analysis_only'
    target_url: Optional[str] = Field(default=None)  # for mode='single'

    # Timestamps
    started_at: Optional[str] = Field(default=None)
    completed_at: Optional[str] = Field(default=None)

    # Results summary
    grants_found: int = Field(default=0)
    grants_admissible: int = Field(default=0)
    grants_partial: int = Field(default=0)
    grants_non_admissible: int = Field(default=0)
    sources_scanned: int = Field(default=0)
    new_sources_discovered: int = Field(default=0)

    # Error tracking
    error_log: list = Field(default_factory=list)  # [{source, error, timestamp}]

    # LLM usage
    total_tokens: int = Field(default=0)
    total_requests: int = Field(default=0)

    @expose_route('/execute', methods=['POST'], stream=True, access=AUTHENTICATED,
                  events={
                      'text': TextChunk, 'tool_call': ToolCallEvent,
                      'tool_result': ToolResultEvent, 'thinking': ThinkingChunk,
                      'done': DoneChunk,
                  })
    async def execute(self, user: User = None):
        """Execute the full scraping + analysis run with streaming output."""
        ...

    @expose_route('/analyze_grant', methods=['POST'], stream=True, access=AUTHENTICATED)
    async def analyze_grant(self, grant_id: int, user: User = None):
        """Run admissibility analysis on a single grant."""
        ...
```

**Rationale:**
- Uses `__agent__` dict (not `AgentActor`). The tool list and constraints are fixed at code level, not stored in DB. This avoids the complexity of AgentActor's DB-stored tool resolution.
- Explicit tool list: `sources` (read source list), `grants` (CRUD grants), `organizations` (read org profile), `reports` (create report), `web_tools` (scrape URLs).
- `self_tools: True` so the agent can call `runs_update()` to update its own status/counters.
- `execute()` is the main streaming endpoint. `analyze_grant()` is for re-analyzing a single grant.
- `error_log` is JSON. Each failed source adds an entry, letting the run continue past individual failures.

### 5. Report

End-of-run summary document.

```python
class Report(ActorModel):
    __tablename__ = 'reports'
    __storable__ = True
    __access__ = {
        'read': AUTHENTICATED,
        'create': AUTHENTICATED,
        'update': ROLE('admin'),
        'delete': ROLE('admin'),
    }
    __ui__ = {
        'field_order': ['title', 'run_id', 'created_at', 'summary',
                        'admissible_grants', 'partial_grants',
                        'non_admissible_grants', 'new_sources'],
    }

    title: str = Field(default='')
    run_id: Optional[int] = Field(default=None)     # FK to Run
    created_at: Optional[str] = Field(default=None)

    # Content sections (JSON)
    summary: str = Field(default='')                 # executive summary text
    admissible_grants: list = Field(default_factory=list)
        # [{grant_id, title, funder, score, reasoning_summary}]
    partial_grants: list = Field(default_factory=list)
        # [{grant_id, title, funder, score, gaps}]
    non_admissible_grants: list = Field(default_factory=list)
        # [{grant_id, title, funder, reason}]
    new_sources: list = Field(default_factory=list)
        # [{source_id, name, url, discovered_by}]

    # Metadata
    total_grants_analyzed: int = Field(default=0)
    org_snapshot: dict = Field(default_factory=dict)  # org profile at time of report
```

**Rationale:**
- Report stores denormalized grant data (not just FK references). The report is a snapshot -- even if grants are later modified, the report retains the original analysis.
- `org_snapshot` captures the Organization profile at report creation time. Historical reports reflect what was analyzed against.
- The Run agent creates the Report as its final step via `reports_create()` tool.

### 6. WebTools (non-storable utility agent)

Provides web scraping capabilities as tools for other agents.

```python
class WebTools(ActorModel):
    __tablename__ = 'web_tools'
    __storable__ = False   # no DB table, pure tool endpoints
    __agent__: ClassVar = {
        'self_tools': False,
        'neighbors': False,
    }

    @expose_route('/fetch', methods=['POST'], access=AUTHENTICATED)
    async def fetch(self, url: str) -> dict:
        """Fetch a URL and return raw HTML content."""
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={'User-Agent': VEILLE_UA})
        return {
            'url': str(resp.url),
            'status': resp.status_code,
            'html': resp.text[:100000],  # cap at 100K chars
            'content_type': resp.headers.get('content-type', ''),
        }

    @expose_route('/extract_text', methods=['POST'], access=AUTHENTICATED)
    async def extract_text(self, html: str, url: str = '') -> dict:
        """Extract clean text content from HTML, stripping nav/footer/scripts."""
        # Uses BeautifulSoup
        return {'text': cleaned_text, 'links': extracted_links}

    @expose_route('/extract_grants', methods=['POST'], access=AUTHENTICATED)
    async def extract_grants(self, text: str, url: str,
                              source_context: str = '') -> dict:
        """Use LLM to extract structured grant data from page text."""
        result = await self.agentic(
            task=f"Extract all grants from this page.\nURL: {url}\n"
                 f"Context: {source_context}\n\n{text}",
            tools=[],  # pure LLM extraction, no tools needed
        )
        return json.loads(result['answer'])
```

**Rationale:**
- Non-storable (`__storable__ = False`). No persistent state, just tool endpoints.
- Three tool methods: `fetch` (HTTP), `extract_text` (HTML parsing), `extract_grants` (LLM extraction).
- `extract_grants` uses `self.agentic()` internally -- "agentic model method" pattern (Path B). It calls the LLM to parse unstructured text into structured grant data, no tools needed.
- The Run agent discovers these as tools: `web_tools_fetch`, `web_tools_extract_text`, `web_tools_extract_grants`.

### 7. User

Standard BaseUser + ActorModel, same pattern as examples.

```python
class User(BaseUser, ActorModel):
    __tablename__ = 'users'
    __abstract__ = False
    __ui__ = {'renderer': {'item': 'ntx-user'}}

    image: str = Field(default='https://ui-avatars.com/api/?name=Admin&...')
```

All users are admins. No role-based differentiation needed for v1.

---

## Actor Topology and Message Flow

### Actor Tree (Matrix children)

```
Matrix (root)
  |-- api             (NetworkAPI adapter -- HTTP bridge)
  |-- users           (User class actor)
  |-- organizations   (Organization class actor)
  |-- sources         (Source class actor)
  |-- grants          (Grant class actor)
  |-- runs            (Run class actor -- has __agent__)
  |     |-- runs/5    (Run instance actor -- when executing)
  |-- reports         (Report class actor)
  |-- web_tools       (WebTools class actor -- has __agent__)
```

All class actors auto-register with Matrix when defined (default `auto_register=True`). Instance actors (e.g., `runs/5`) are created as children of their class actor during execution.

### Tool Discovery Map

When Run agent executes, `discover_tools()` reads schemas from these actors:

| Actor Address | Discovered Tools |
|---------------|-----------------|
| `runs` | `runs_list`, `runs_get`, `runs_create`, `runs_update`, `runs_delete` |
| `sources` | `sources_list`, `sources_get`, `sources_create`, `sources_update`, `sources_delete` |
| `grants` | `grants_list`, `grants_get`, `grants_create`, `grants_update`, `grants_delete` |
| `organizations` | `organizations_list`, `organizations_get`, `organizations_create`, `organizations_update`, `organizations_delete` |
| `reports` | `reports_list`, `reports_get`, `reports_create`, `reports_update`, `reports_delete` |
| `web_tools` | `web_tools_fetch`, `web_tools_extract_text`, `web_tools_extract_grants` |

The LLM gets all these tools. In practice it primarily uses: `sources_list`, `organizations_get`, `web_tools_fetch`, `web_tools_extract_text`, `web_tools_extract_grants`, `grants_list`, `grants_create`, `grants_update`, `reports_create`, `runs_update`.

### Message Flow: Complete Scraping Run

Step-by-step flow when a user triggers a full run.

```
1. User clicks "Start Run" in the UI
   |
   v
2. Frontend: POST /runs  {"mode": "full"}
   |
   v
3. NetworkAPI.request(TX(name='create', target='runs', data={mode:'full'}))
   -> auth_interceptor validates JWT
   -> Matrix routes to Run class actor
   -> Run.handler_crud() creates Run record (id=5, status='pending')
   -> Returns Run instance
   |
   v
4. Frontend: POST /runs/5/execute  {}
   -> SSE stream opened
   |
   v
5. NetworkAPI opens stream(TX(name='execute', target='runs/5'))
   -> Matrix routes to Run class -> strips prefix -> Run instance id=5
   -> Run.execute() begins streaming
   |
   v
6. Run.execute() calls self.agentic_stream(task=..., prompt=...)
   -> AgentMixin.run_stream() resolves LLM from __agent__['llm'] cascade
   -> discover_tools(['runs','sources','grants','organizations','reports','web_tools'], matrix)
   -> Builds pydantic-ai Agent with ~25 tools
   |
   v
7. Pydantic AI agent loop begins. LLM reasons:

   7a. "First, get org profile for context"
       -> Tool: organizations_list()
       -> TX(name='list', target='organizations') through Matrix
       -> Returns org profile
       -> [stream: tool_call event, tool_result event]

   7b. "Get all active sources"
       -> Tool: sources_list()
       -> TX(name='list', target='sources') through Matrix
       -> Returns source records
       -> [stream: tool_call event, tool_result event]

   7c. For each source:
       "Fetch the source URL"
       -> Tool: web_tools_fetch(url=source.url)
       -> TX(name='fetch', target='web_tools') through Matrix
       -> WebTools.fetch() makes HTTP request
       -> Returns {html, status, ...}

   7d. "Extract text from HTML"
       -> Tool: web_tools_extract_text(html=..., url=...)
       -> TX(name='extract_text', target='web_tools')
       -> Returns {text, links}

   7e. "Extract grants from this page"
       -> Tool: web_tools_extract_grants(text=..., url=..., source_context=...)
       -> TX(name='extract_grants', target='web_tools')
       -> WebTools.extract_grants() internally calls self.agentic()
         (nested LLM call for structured extraction)
       -> Returns list of extracted grant objects

   7f. For each extracted grant:
       "Check if this grant already exists"
       -> Tool: grants_list() with search
       -> If new: grants_create({title, funder, url, ...})
       -> If exists: grants_update(id, {...})

   7g. "Analyze admissibility against org profile"
       -> For each new/updated grant:
       -> LLM reasons about eligibility_criteria vs org focus_areas,
         legal_status, location, past_grants
       -> Tool: grants_update(id, {status, admissibility_score, admissibility_reasoning})

   7h. "Update source last_scraped and run counters"
       -> Tool: sources_update(id, {last_scraped: now()})
       -> Tool: runs_update(id, {grants_found: N, grants_admissible: M, ...})

   7i. "Generate report"
       -> Tool: reports_create({title, run_id, summary, admissible_grants, ...})

   7j. "Mark run complete"
       -> Tool: runs_update(id, {status: 'completed', completed_at: now()})

   |
   v
8. run_stream() yields final done chunk:
   {'name':'done', 'data':{'answer':'...', 'usage':{...}}, 'meta':{'stream_end':true}}
   |
   v
9. SSE stream closes. Frontend shows completion and link to report.
```

### Message Flow: Single URL Scan

```
POST /runs  {"mode": "single", "target_url": "https://example.com/grants"}
POST /runs/{id}/execute  {}

-> Same agent loop, but LLM prompt says:
  "Scan only this specific URL: https://example.com/grants"
  -> Skips sources_list
  -> web_tools_fetch(url=target_url) directly
  -> Extract and analyze as normal
  -> Creates grants + report for this URL only
```

### Message Flow: Re-analyze Single Grant

```
POST /runs/{id}/analyze_grant  {"grant_id": 42}

-> Agent loads:
  - Grant record: grants_get(id=42)
  - Organization profile: organizations_list()
-> LLM reasons about admissibility
-> Updates grant: grants_update(42, {status, score, reasoning})
-> Returns analysis result
```

---

## Agent Workflow Detail

### System Prompt Architecture

The Run agent's system prompt is assembled dynamically from the org profile and run mode.

```python
def build_run_prompt(org: Organization) -> str:
    return f"""You are a grant monitoring agent for {org.name}.

Organization Profile:
- Mission: {org.mission}
- Legal Status: {org.legal_status}
- Location: {org.location}
- Focus Areas: {', '.join(org.focus_areas)}
- Past Grants: {json.dumps(org.past_grants, indent=2)}
- Custom Criteria: {json.dumps(org.custom_criteria, indent=2)}

Your workflow:
1. Scan assigned sources for grant and funding opportunities.
2. For each source URL, use web_tools_fetch to get the page, then
   web_tools_extract_text to get clean text, then web_tools_extract_grants
   to identify individual grants.
3. For each grant found, check for duplicates via grants_list before creating.
4. Evaluate each grant's admissibility against the organization profile.
5. For each grant, set:
   - status: 'admissible' (score >= 0.7), 'partial' (0.3-0.7), 'non_admissible' (< 0.3)
   - admissibility_score: 0.0 to 1.0
   - admissibility_reasoning: detailed justification referencing specific criteria
6. Update run counters as you go (runs_update with grants_found, etc.).
7. When finished, create a Report summarizing all findings.
8. Mark the run as completed.

Deduplication: Before creating a grant, search for existing grants with similar
title and funder. Update rather than duplicate.

Language: Sources may be in English or French. Extract details in the source
language but provide admissibility reasoning in English.

Error handling: If a source fails to load, log the error and continue.
"""
```

### Admissibility Analysis Logic

The Run agent performs admissibility analysis inline during the main loop:

1. **Criteria matching:** For each eligibility criterion, check if the org meets it.
   - Legal status requirements vs org's `legal_status`
   - Geographic requirements vs org's `location`
   - Focus area alignment vs org's `focus_areas`
   - Size/budget requirements vs org's `custom_criteria`

2. **Scoring scale:**
   - 1.0 = all criteria met, strong alignment
   - 0.5-0.9 = most criteria met, some gaps
   - 0.1-0.4 = significant gaps
   - 0.0 = clearly ineligible

3. **Classification thresholds:**
   - `admissible` (score >= 0.7): Org clearly qualifies
   - `partial` (0.3 <= score < 0.7): Some criteria met, gaps identified
   - `non_admissible` (score < 0.3): Org does not qualify

### WebTools Agent Prompt (for extract_grants)

```
"You are a grant extraction specialist. Given page text from a funding website,
extract ALL grant/funding programs mentioned. For each, provide: title, funder,
url, description, amount_min, amount_max, deadline, eligibility_criteria (list),
required_documents (list), application_process. Return a JSON array. If no grants
found, return []. Only extract actual funding programs, not news articles."
```

---

## Frontend View Structure

### Pages / Routes

```
/ (root)
  |-- /runs             -> Run list (ntx-list, "Start New Run" button)
  |-- /runs/:id         -> Run detail + streaming execution view
  |-- /grants           -> Grant list (filterable by status)
  |-- /grants/:id       -> Grant detail with admissibility analysis
  |-- /sources          -> Source management (CRUD)
  |-- /sources/:id      -> Source detail + edit form
  |-- /reports          -> Report list
  |-- /reports/:id      -> Report detail view (main output)
  |-- /organization     -> Organization profile editor (singleton)
```

### Component Map

| Route | Component | Standard/Custom |
|-------|-----------|----------------|
| `/runs` | `ntx-list model="Run"` | Standard (+ "Start Run" button) |
| `/runs/:id` | `veille-run-detail` | **Custom** -- StreamActor for live execution |
| `/grants` | `ntx-list model="Grant"` | Standard (+ status filter) |
| `/grants/:id` | `ntx-item model="Grant"` | Standard (field groups) |
| `/sources` | `ntx-list model="Source"` | Standard |
| `/sources/:id` | `ntx-item model="Source"` | Standard |
| `/reports` | `ntx-list model="Report"` | Standard |
| `/reports/:id` | `veille-report` | **Custom** -- formatted report layout |
| `/organization` | `veille-org-profile` | **Custom** -- singleton editor |

### Custom Components Needed

**`veille-run-detail`** -- Extends `StreamActor(HTMLElement)`:
- Shows run metadata (status, mode, timestamps)
- When status is 'pending', shows "Execute" button
- On execute, opens SSE stream to `/runs/{id}/execute`
- Displays real-time agent activity via UPPERCASE handlers:
  ```javascript
  TEXT(data, meta)        { /* append agent reasoning text */ }
  TOOL_CALL(data, meta)   { /* show "Calling web_tools_fetch..." */ }
  TOOL_RESULT(data, meta) { /* show tool result summary */ }
  THINKING(data, meta)    { /* show thinking indicator */ }
  DONE(data, meta)        { /* show completion, link to report */ }
  ```
- On completion, displays summary and links to generated report

**`veille-report`** -- Custom read-only component:
- Renders report sections: summary, admissible grants, partial, non-admissible, new sources
- Each grant entry is expandable (shows reasoning, criteria match)
- PDF export button (calls backend endpoint)

**`veille-org-profile`** -- Custom form component:
- Loads singleton Organization record (id=1)
- Form for editing profile fields
- JSON/structured editor for `focus_areas` and `past_grants`
- Save calls `Organization.update(1, {...})`

### Standard Components (no customization needed)

- Source CRUD: `ntx-list` + `ntx-item` with auto-generated Formidable forms
- Grant list/detail: `ntx-list` with status filtering + `ntx-item` with field groups
- Report list: `ntx-list` showing report titles and dates

---

## Patterns to Follow

### Pattern 1: `__agent__` Dict on Domain Model (not AgentActor)

**What:** Use `__agent__` dict on Run for agent capabilities instead of extending `AgentActor`.

**When:** Agent behavior is fixed -- known tools, known prompt structure, not user-reconfigurable.

**Why:** AgentActor stores config (prompt, tools, llm) in DB fields, designed for dynamic agents created at runtime. Veille's Run has a fixed tool set and prompt template built from code. Using `__agent__` dict avoids:
- DB-stored ListRef[AgentTool] resolution complexity
- The need for AgentTool join tables
- Runtime tool configuration (not needed)

```python
class Run(ActorModel):
    __agent__: ClassVar = {
        'self_tools': True,
        'neighbors': False,
        'tools': ['sources', 'grants', 'organizations', 'reports', 'web_tools'],
        'constraints': {'max_iterations': 50},
    }
```

### Pattern 2: Non-Storable Tool Actor

**What:** `ActorModel` with `__storable__ = False` that provides utility methods as tools.

**When:** Need to expose functionality (HTTP, parsing, email) as tools without a database entity.

```python
class WebTools(ActorModel):
    __tablename__ = 'web_tools'
    __storable__ = False

    @expose_route('/fetch', methods=['POST'], access=AUTHENTICATED)
    async def fetch(self, url: str) -> dict:
        ...
```

Agent discovers these as `web_tools_fetch`, `web_tools_extract_text`, etc.

### Pattern 3: Singleton Configuration Model

**What:** A storable model where only one record exists (Organization profile).

**When:** App-wide config that needs CRUD, schema-driven UI, and agent-readable access.

```python
# Access via tools: organizations_list() returns [org], organizations_get(id=1) returns org
# Seed on first run:
if not Organization.list():
    Organization.create(Organization(name='...', mission='...'))
```

### Pattern 4: Streaming Execution with Custom Events

**What:** Define domain-specific event ProtoModels, declare via `events=` on `@expose_route`.

**When:** Streaming method needs to communicate domain progress beyond text/tool_call/done.

```python
class SourceProgress(ProtoModel):
    source_name: str = Field(default='')
    phase: str = Field(default='')  # 'scraping' | 'extracting' | 'analyzing'

@expose_route('/execute', methods=['POST'], stream=True,
              events={'source_progress': SourceProgress, 'text': TextChunk, ...})
async def execute(self, user: User = None):
    yield {'name': 'source_progress', 'data': {'source_name': 'grants.gov', 'phase': 'scraping'}}
```

Frontend handler: `SOURCE_PROGRESS(data) { /* update progress display */ }`

### Pattern 5: Manual Integer FK (not Ref/ListRef)

**What:** Store foreign key as `Optional[int]` instead of `Ref[Source]` or `ListRef[Source]`.

**When:** The relationship is one-directional and does not need schema-level reference resolution, FK hydration, or join tables.

```python
class Grant(ActorModel):
    source_id: Optional[int] = Field(default=None)  # FK to Source, plain int
    run_id: Optional[int] = Field(default=None)      # FK to Run, plain int
```

**Why for Veille:** Grant's `source_id` and `run_id` are metadata set by the agent during creation. They don't need to appear as navigable relationships in the UI schema. Using `Ref` would add unnecessary join table overhead and coupling between model files.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: One Agent Per Concern

**What:** Creating separate ScrapingAgent, ExtractionAgent, AnalysisAgent, ReportAgent as distinct agent instances.

**Why bad:** Coordination overhead. Each agent starts with empty LLM context -- it doesn't know what the previous agent found. Requires shared state or message passing between agents. Multiple LLM session setups waste tokens on repeated context.

**Instead:** One Run agent with access to all tools. The LLM maintains context across the entire workflow -- it remembers what it scraped and can reason about admissibility without re-reading.

### Anti-Pattern 2: Full Agent Orchestration for the Pipeline

**What:** Giving the LLM full control ("Here are the tools, figure out the workflow").

**Why bad:** LLMs are non-deterministic. They might skip sources, forget analysis, create duplicates, or spend tokens on irrelevant exploration. For a pipeline with clear sequential steps, unstructured reasoning wastes budget and reduces reliability.

**Instead:** The Run agent's prompt gives explicit workflow instructions (steps 1-8). The LLM has latitude within each step (how to explore a page, how to extract grants, how to reason about admissibility) but follows the prescribed order.

### Anti-Pattern 3: Hand-Rolled Routes

**What:** Creating custom FastAPI routes for scraping/analysis instead of `@expose_route`.

**Why bad:** Bypasses schema generation, auto-discovery by agents, TX routing, and auth interceptors. The route won't appear in `schema.methods`, so frontend can't auto-render it.

**Instead:** Everything is `@expose_route`. Agent tools are discovered from schema. Auth works automatically.

### Anti-Pattern 4: Importing `n3tx_agents` After Models

**What:** `from models import Run` before `import n3tx_agents` in `main.py`.

**Why bad:** AgentMixin silently not injected. `__agent__ = True` has no effect. No error -- just missing `.agentic()`, `.run()`, etc.

**Instead:** Always `import n3tx_agents` before any model imports in `main.py`.

### Anti-Pattern 5: Making Organization an Agent

**What:** Adding `__agent__ = True` to Organization.

**Why bad:** Organization is static configuration data. It doesn't reason. The Run agent reads the org profile and reasons about it.

**Instead:** Organization is a plain ActorModel. Agents read it via `organizations_list()` / `organizations_get()` tools.

---

## Build Order (Dependencies)

### Phase 1: Foundation

**What:** User, Organization, app skeleton (main.py, config, create_app)

**Depends on:** Nothing

**Deliverables:**
- `models/user.py` -- BaseUser + ActorModel
- `models/organization.py` -- singleton profile
- `main.py` -- create_app with Level 3 routing
- `config.py` -- PORT, HOST, JWT, DB path, AGENT_DEFAULTS
- `seed.py` -- initial admin user + default FFT/RTS org profile
- Basic auth working (login, JWT)

**Why first:** Everything depends on auth and the org profile.

### Phase 2: Source Management

**What:** Source CRUD

**Depends on:** Phase 1

**Deliverables:**
- `models/source.py` -- Source model
- Seed data from initial source list
- UI: `/sources` list + edit forms

**Why second:** Sources are input to scraping. Must exist before agents can scrape.

### Phase 3: Grant Model + WebTools

**What:** Grant CRUD, WebTools utility actor

**Depends on:** Phase 1

**Deliverables:**
- `models/grant.py` -- Grant model
- `models/web_tools.py` -- WebTools with fetch/extract methods
- UI: `/grants` list + detail views
- Manual verification: call web_tools_fetch via API

**Why third:** Grants are the output of scraping. WebTools provides scraping infrastructure. Both must exist before Run agent.

### Phase 4: Run Agent (Core Value)

**What:** Run model with `__agent__`, execute endpoint, streaming UI

**Depends on:** Phases 1, 2, 3 (all must exist as tools)

**Deliverables:**
- `models/run.py` -- Run with agent config + execute endpoint
- System prompt construction
- Custom `veille-run-detail` component (StreamActor)
- UI: `/runs` list + streaming execution view
- End-to-end test: create sources -> trigger run -> verify grants created

**Why fourth:** This IS the core value. Highest risk (non-deterministic agent behavior).

### Phase 5: Admissibility Analysis

**What:** Admissibility scoring within Run agent, re-analysis endpoint

**Depends on:** Phase 4

**Deliverables:**
- Enhanced Run prompt with admissibility instructions
- `analyze_grant()` endpoint for single-grant re-analysis
- Updated Grant UI showing admissibility details
- Testing against FFT/RTS profile

**Why fifth:** Analysis builds on working scraping. Iterate on quality independently.

### Phase 6: Report Generation

**What:** Report model, report creation in Run agent, report views

**Depends on:** Phases 4, 5

**Deliverables:**
- `models/report.py` -- Report model
- Run agent creates Report as final step
- Custom `veille-report` component
- UI: `/reports` list + formatted view

### Phase 7: Polish and Extras

**What:** PDF export, email, scheduling, auto-discovery

**Depends on:** Phase 6

**Deliverables:** PDF generation, email notification, scheduled runs, source auto-discovery, improved dedup

### Dependency Graph

```
Phase 1 (Foundation)
  |
  +---> Phase 2 (Sources) ----+
  |                            |
  +---> Phase 3 (Grants+WebTools) --+
                                     |
                           Phase 4 (Run Agent) <-- CORE VALUE
                                     |
                           Phase 5 (Admissibility)
                                     |
                           Phase 6 (Reports)
                                     |
                           Phase 7 (Polish)
```

Phases 2 and 3 can be built in parallel. Phases 4-7 are sequential.

---

## main.py Structure

```python
"""Veille -- Grant monitoring application."""
import os
import logging
import config

import n3tx_agents  # MUST be before model imports

from n3tx_core.app import create_app
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from models import User, Organization, Source, Grant, Run, Report, WebTools

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')

_HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_HERE, config.SQLITE_DB_FILE)

storage = SQLiteStorage(DB_PATH)
app = create_app(
    models=[User, Organization, Source, Grant, Run, Report, WebTools],
    storage=storage,
    routing='actor',
    jwt_secret=config.JWT_SECRET,
    static_dir=os.path.join(_HERE, 'static'),
    ssr='full',
    name='Veille',
    version='1.0.0',
    description='Agentic grant monitoring for non-profits',
)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run('main:app', host=config.HOST, port=config.PORT, reload=config.DEBUG)
```

**Key points:**
- `import n3tx_agents` before model imports (mandatory for `__agent__` injection).
- No `join_models` needed -- Grant uses plain int FKs, not ListRef.
- WebTools is registered like any other model despite being non-storable.
- `routing='actor'` for Level 3 (full TX routing through Matrix).

---

## Scalability Considerations

| Concern | Single org (now) | 10+ orgs (future) |
|---------|-----------------|-------------------|
| Data isolation | Single SQLite DB | Separate Veille instances per org |
| LLM costs | Tracked per Run (total_tokens) | Add billing/quota model |
| Concurrent runs | One at a time (sufficient) | Queue system |
| Source count | 10-50 sources | Paginated scanning with progress |
| Grant volume | Hundreds per run | Batch processing with checkpoints |
| Storage | SQLite single file, backup = copy | Same pattern per org |

---

## Sources

- N3TX Architecture: `/workspace/docs/ARCHITECTURE.md` (HIGH confidence)
- N3TX Actors: `/workspace/docs/ACTORS.md` (HIGH confidence)
- N3TX Agents: `/workspace/docs/AGENTS.md` (HIGH confidence)
- N3TX Models: `/workspace/docs/MODELS.md` (HIGH confidence)
- AgentMixin source: `/workspace/packages/n3tx-agents/src/n3tx_agents/mixin.py` (HIGH confidence)
- AgentActor source: `/workspace/packages/n3tx-agents/src/n3tx_agents/actor.py` (HIGH confidence)
- Tool discovery docs: `/workspace/packages/n3tx-agents/docs/tool-discovery.md` (HIGH confidence)
- Agent mixin docs: `/workspace/packages/n3tx-agents/docs/mixin.md` (HIGH confidence)
- Chat example (streaming pattern): `/workspace/examples/chat/models/conversation.py` (HIGH confidence)
- Actors example (Level 3 pattern): `/workspace/examples/actors/main.py` (HIGH confidence)
- create_app source: `/workspace/packages/n3tx-core/src/n3tx_core/app.py` (HIGH confidence)
- Veille PROJECT.md: `/workspace/apps/veille/.planning/PROJECT.md` (HIGH confidence)
