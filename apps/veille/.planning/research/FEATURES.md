# Feature Landscape

**Domain:** Agentic grant monitoring application (Veille)
**Framework:** N3TX (Level 3 + Agents)
**Researched:** 2026-03-20

## Feature-to-Framework Mapping

The central question: for each Veille feature, what does N3TX provide for free, what requires minimal wiring, and what demands custom implementation?

### Legend

| Tag | Meaning |
|-----|---------|
| **FREE** | Zero custom code. Define a model, get it automatically. |
| **WIRE** | N3TX has the pattern. You write a model + config, framework does the rest. |
| **BUILD** | Custom implementation needed. N3TX provides the plumbing (routing, storage, schema), you write the logic. |
| **EXTEND** | Framework extension point used (custom widget, schema extension, expose_route). |

---

## Table Stakes: What N3TX Gives for Free

These features require only model definitions. No custom code beyond declaring fields, types, access rules, and UI hints.

### Source CRUD [FREE]

Define a `Source(ActorModel)` with `__storable__ = True`. N3TX generates:

| Generated | How |
|-----------|-----|
| `POST /sources` (create) | `register_routes()` |
| `GET /sources` (list, paginated) | `register_routes()` + `?limit=N&offset=M` |
| `GET /sources/{id}` (read) | `register_routes()` |
| `PUT /sources/{id}` (update) | `register_routes()` |
| `DELETE /sources/{id}` (delete) | `register_routes()` |
| `GET /Source` (JSON Schema) | `ProtoModel.schema()` |
| DB table + auto-migration | `StorableMixin` + `SQLiteMigration` |
| Frontend list + detail views | `ntx-list` + `ntx-item` via schema |
| Create/edit forms | `Formidable.getForm()` from schema properties |
| Client-side validation | `Formidable.validateForm()` from schema constraints |
| URL field as clickable link | `UrlField` widget (display) + `input[url]` (edit) |

**Effort:** ~30 lines of model definition. Zero frontend code.

**Example pattern** (from `examples/grants/models/source.py`):

```python
class Source(ActorModel):
    __tablename__ = 'sources'
    __storable__ = True
    name: str = Field(min_length=1, max_length=200)
    url: UrlField = Field(description="URL to scan for grants")
    category: str = Field(default='government')
```

Veille extends this with `is_agent_discovered: bool`, `notes: TextareaField`, `last_scraped: DateField`, etc.

### Grant CRUD [FREE]

Same pattern. Define `Grant(ActorModel)` with all detail fields. N3TX generates the full API, schema, storage, and UI.

**What comes free:**

| Feature | N3TX Mechanism |
|---------|---------------|
| Full detail storage (amount, deadlines, criteria, documents, process) | Model fields + SQLite JSON for complex types |
| Status field with enum constraint | `Literal['new', 'analyzed', 'admissible', 'partial', 'non_admissible']` |
| Currency display for amounts | `CurrencyField` widget |
| URL display as clickable link | `UrlField` widget |
| Date display for deadlines | `DateField` widget |
| Rich text for description/criteria | `TextareaField` or `MarkdownField` widget |
| Access control (admin-only) | `__access__` dict |
| Pagination on list endpoint | `?limit=N&offset=M` auto-supported |
| Searchable by any field | `sql_filter` parameter on `list()` |

**Complex fields stored as JSON:** Grant criteria, required documents, and application process details can be `dict` or `list` fields. N3TX auto-serializes these to JSON TEXT columns with zero boilerplate (via `_coerce_value()` / `_deserialize_json_fields()`).

### Organization Profile CRUD [FREE]

A singleton-style `OrgProfile(ActorModel)` with `__storable__ = True`. Since Veille is single-org, this is one record accessed by ID.

Fields like `mission`, `activities`, `legal_status`, `location`, `past_grants` (list/dict), `custom_criteria` (dict) all store natively.

### User Authentication [FREE]

Extend `BaseUser` exactly like `examples/grants/models/user.py`. N3TX generates:
- `POST /users/login` (JWT token)
- `POST /users/register` (create account)
- Password hashing (bcrypt)
- JWT middleware (ASGI-level, does not break SSE)
- Token in `x-access-token` header
- `__protected_fields__` for `user_owner` auto-injection

### Run History CRUD [FREE]

A `Run(ActorModel)` with fields like `status`, `started_at`, `completed_at`, `grant_count`, `source_count`, `error_count`. List/detail views auto-generated.

### Schema-Driven Frontend [FREE]

Every model gets a working UI without writing any JavaScript:
- Sidebar navigation (from registered models)
- List views with pagination and "Load More"
- Detail views with field grouping
- Create/edit modals with validation
- Field-level access control (show/hide based on role)
- Widget-based rendering (currency, URL, date, textarea, markdown)

**Confidence: HIGH** -- Verified from `examples/grants/` which uses this exact pattern for Grant, Source, and Agent models.

---

## Custom Features: What Veille Must Build

These features have no direct N3TX equivalent. The framework provides routing, storage, and agent infrastructure, but the domain logic is custom.

### Agentic Scraping [BUILD on WIRE]

**What N3TX provides:**
- `AgentActor` pattern for dynamic agents stored in DB
- `AgentMixin.agent_run()` for LLM reasoning loops
- Tool discovery from actor schemas (`discover_tools()`)
- `@expose_route` methods on non-storable actors become agent tools
- Streaming via `agentic_stream()` + `StreamActor` frontend mixin
- `WebTools` pattern from `examples/grants/` (scrape + extract methods)

**What Veille must build:**
- **Scraping tools actor** -- A `WebTools`-like actor with methods for:
  - `scrape(url)` -- Fetch page content (httpx, handle redirects/timeouts)
  - `extract_text(html)` -- Clean HTML to readable text (BeautifulSoup)
  - `extract_links(html, base_url)` -- Find grant listing links
  - `scrape_pdf(url)` -- Download and extract text from PDF documents
- **Scraping agent prompt** -- System prompt guiding the LLM to explore source pages, follow links, identify grant listings, and extract structured data
- **Grant creation via agent tools** -- Agent calls `grants_create` with extracted fields (N3TX routes this through Matrix automatically)

**Framework leverage:** The grants example already demonstrates this exact pattern. The `WebTools` actor + `AgentActor` with tools pointing to `['grants', 'sources', 'web_tools']` is the proven approach. Veille adds more sophisticated scraping methods and a more detailed agent prompt.

**Complexity: MEDIUM** -- The pattern exists. The hard part is prompt engineering for reliable extraction across diverse source formats.

### Admissibility Analysis [BUILD on WIRE]

**What N3TX provides:**
- `__agent__ = True` on any model enables `agentic()` method
- Structured output via `result_type=` (Pydantic model validation)
- `@expose_route` for custom analysis endpoints
- Streaming for long-running analysis (`agentic_stream()`)

**What Veille must build:**
- **Analysis method on Grant** -- `@expose_route('/analyze', methods=['POST'], stream=True)` that:
  1. Loads the org profile
  2. Reads grant details
  3. Calls `self.agentic()` with a prompt asking for criteria matching + reasoning
  4. Returns structured `AdmissibilityResult` (classification + justification + per-criterion scores)
- **Batch analysis** -- Run analysis on all new grants from a scraping run
- **Admissibility result storage** -- Fields on Grant or a separate `Analysis` model

**Pattern:**

```python
class AdmissibilityResult(ProtoModel):
    classification: Literal['admissible', 'partial', 'non_admissible']
    score: float
    justification: str
    criteria_matches: list  # [{criterion, match, reasoning}]

class Grant(ActorModel):
    __agent__ = True

    @expose_route('/analyze', methods=['POST'], stream=True,
                  events={'thinking': ThinkingChunk, 'done': DoneChunk})
    async def analyze(self, user: User = None):
        profile = OrgProfile.get(1)
        result = await self.agentic(
            task=f"Analyze this grant for admissibility...",
            prompt=f"You evaluate grants against org profiles. {profile.ctx()}",
            result_type=AdmissibilityResult,
        )
        # Save result to grant fields
        yield {'name': 'done', 'data': result}
```

**Complexity: MEDIUM-HIGH** -- The N3TX agent infrastructure handles LLM orchestration. The challenge is prompt design for consistent, accurate admissibility scoring.

### Run Orchestration [BUILD on WIRE]

**What N3TX provides:**
- `AgentActor` instances for the orchestrator agent
- TX messaging for inter-actor communication
- `@expose_route` with `stream=True` for long-running operations
- Lifecycle events (`_publish_lifecycle`) for reactive triggers

**What Veille must build:**
- **Run model** (`Run(ActorModel)`) -- Tracks execution state: `pending -> running -> completed/failed`
- **Run orchestration** -- Either:
  - **Option A (recommended):** A `@expose_route('/execute', stream=True)` method on `Run` that sequences: load sources -> scrape each -> extract grants -> deduplicate -> analyze admissibility -> generate report. Streams progress events.
  - **Option B:** A dedicated `RunAgent(AgentActor)` that uses tools to orchestrate the pipeline. More flexible but harder to control sequencing.
- **Progress streaming** -- The run streams events as it progresses (`source_started`, `grant_found`, `analysis_complete`, `report_ready`). N3TX `StreamActor` on the frontend handles display.

**Recommendation: Option A.** Agent orchestration (Option B) is elegant but introduces LLM non-determinism into the sequencing. A deterministic Python method that calls agents for scraping and analysis within a controlled loop is more reliable. The method itself is a `@expose_route(stream=True)` so the frontend gets real-time progress.

**Complexity: HIGH** -- This is the core pipeline. Each step (scrape, extract, deduplicate, analyze, report) has its own failure modes.

### Grant Deduplication [BUILD]

**What N3TX provides:**
- `list(sql_filter=...)` for querying existing grants by URL, title, etc.
- `dict`/`list` JSON fields for storing fingerprints or hashes

**What Veille must build:**
- **Dedup logic** -- Before creating a grant, check if it already exists:
  - URL exact match (fastest, catches most cases)
  - Title similarity (fuzzy match for same grant from different sources)
  - Optional: LLM-based comparison for borderline cases
- **Merge logic** -- When a duplicate is found, update the existing record with any new information rather than creating a new one

**Complexity: LOW-MEDIUM** -- URL matching is trivial. Title similarity adds moderate complexity. Can start with URL-only and iterate.

### Auto-Discovery of Sources [BUILD on WIRE]

**What N3TX provides:**
- Agent tools can call `sources_create` to add new sources
- `is_agent_discovered` field distinguishes human vs agent sources

**What Veille must build:**
- **Discovery prompt** -- Extension to the scraping agent prompt: "While scanning for grants, if you find links to other funding pages or grant directories, create them as new sources with `sources_create` and set `is_agent_discovered=true`"
- **Discovery validation** -- Agent-discovered sources should be flagged for human review before being included in regular scans

**Complexity: LOW** -- This is primarily prompt engineering. The CRUD infrastructure exists.

### Report Generation [BUILD + EXTEND]

**What N3TX provides:**
- `@expose_route` for report endpoints
- `TextareaField` / `MarkdownField` widgets for in-app display
- Streaming for real-time report building

**What Veille must build:**
- **Report model** (`Report(ActorModel)`) -- Stores generated report content, linked to a Run
- **In-app view** -- A custom component or markdown widget to display the report
- **PDF generation** -- Use a Python library (WeasyPrint, reportlab, or markdown-to-PDF) to convert report content to downloadable PDF. Exposed via `@expose_route('/pdf', methods=['GET'])` that returns a `FileResponse`.
- **Email notification** -- SMTP integration to send report summary after run completion. This is outside N3TX (use `smtplib` or a service like SendGrid).

**Complexity breakdown:**
- In-app report: LOW (store markdown, render via widget)
- PDF export: MEDIUM (library integration, formatting)
- Email notification: MEDIUM (SMTP config, template, delivery)

### Scheduled Runs [BUILD]

**What N3TX provides:**
- FastAPI `@app.on_event("startup")` or lifespan context manager for background tasks
- TX messaging to trigger agent runs programmatically

**What Veille must build:**
- **Scheduler** -- Options:
  - **APScheduler** (recommended) -- Lightweight, no external dependencies, runs in-process
  - **Celery** -- Overkill for this use case
  - **System cron** -- Simple but external
- **Schedule config** -- A field on OrgProfile or a separate ScheduleConfig model
- **Trigger mechanism** -- Scheduler calls `Run.create()` + triggers execution via TX or direct method call

**Complexity: LOW** -- APScheduler with a single cron-style job is straightforward.

---

## Framework Features to Leverage

Specific N3TX capabilities that map directly to Veille needs, requiring only configuration rather than custom code.

### Streaming for Long Operations [WIRE]

**Veille need:** Scraping runs take minutes. Users need progress feedback.
**N3TX pattern:** `@expose_route('/execute', stream=True)` + `StreamActor` frontend mixin.

The backend yields progress events:

```python
@expose_route('/execute', methods=['POST'], stream=True,
              events={
                  'progress': ProgressEvent,
                  'grant_found': GrantFoundEvent,
                  'analysis': AnalysisEvent,
                  'done': RunDoneEvent,
              })
async def execute(self):
    for source in sources:
        yield {'name': 'progress', 'data': {'source': source.name, 'phase': 'scraping'}}
        # ... scrape and extract ...
        for grant in found_grants:
            yield {'name': 'grant_found', 'data': {'title': grant.title}}
        # ... analyze ...
        yield {'name': 'analysis', 'data': {'grant': grant.title, 'result': 'admissible'}}
    yield {'name': 'done', 'data': {'total_grants': N, 'admissible': M}}
```

The frontend uses `StreamActor`:

```javascript
class RunProgress extends StreamActor(HTMLElement) {
    PROGRESS(data) { /* update progress bar */ }
    GRANT_FOUND(data) { /* add to found list */ }
    ANALYSIS(data) { /* show analysis result */ }
    DONE(data) { /* show summary */ }
}
```

**Confidence: HIGH** -- This is the exact pattern used by `ntx-agent-live` in the grants example.

### Agent Tool Discovery [WIRE]

**Veille need:** Agents need access to Source CRUD, Grant CRUD, and custom scraping tools.
**N3TX pattern:** `tools=['sources', 'grants', 'web_tools']` on the AgentActor.

Tool discovery reads schemas from Matrix children. Storable models get 5 CRUD tools (list, get, create, update, delete). `@expose_route` methods get individual tools. The agent sees:

- `sources_list`, `sources_get`, `sources_create`, etc.
- `grants_list`, `grants_get`, `grants_create`, etc.
- `web_tools_scrape`, `web_tools_extract`, `web_tools_extract_links`

**Confidence: HIGH** -- Verified from `examples/grants/seed.py` which sets up this exact tool graph.

### JSON Fields for Complex Data [FREE]

**Veille need:** Grant criteria, required documents, and org profile past-grants are structured but variable.
**N3TX pattern:** `dict` and `list` fields auto-serialize to JSON TEXT.

```python
class Grant(ActorModel):
    criteria: list = Field(default=[], description="Eligibility criteria")
    required_docs: list = Field(default=[], description="Documents needed")
    application_process: dict = Field(default={}, description="How to apply")

class OrgProfile(ActorModel):
    past_grants: list = Field(default=[], description="Previous grants received")
    custom_criteria: dict = Field(default={}, description="Org-specific eligibility info")
```

**Confidence: HIGH** -- Verified from storage.md and `AgentActor.constraints` field which uses the same pattern.

### Custom Widgets for Domain Fields [EXTEND]

**Veille need:** Specialized display for admissibility scores, grant status badges, run progress.
**N3TX pattern:** Extend `Widget` base class, register with `registerWidget()`.

Potential custom widgets:
- **admissibility** -- Color-coded badge (green/yellow/red) for classification
- **grant-status** -- Status badge with icon
- **score** -- Progress bar or percentage display
- **run-status** -- Running/completed/failed indicator with timing

```python
# Backend
admissibility: str = Field(json_schema_extra={'ui': {'widget': 'admissibility'}})
```

```javascript
// Frontend
class AdmissibilityWidget extends Widget {
    display(value) {
        const colors = { admissible: 'green', partial: 'orange', non_admissible: 'red' };
        return this.el('span', {
            class: 'badge',
            style: `background: ${colors[value]}`
        }, [value]);
    }
}
registerWidget('admissibility', new AdmissibilityWidget());
```

**Confidence: HIGH** -- The widget system is well-documented with clear extension API.

### Access Control for Admin-Only [FREE]

**Veille need:** All users are admins. No public access.
**N3TX pattern:**

```python
__access__ = {
    'read': AUTHENTICATED,
    'create': AUTHENTICATED,
    'update': AUTHENTICATED,
    'delete': ROLE('admin'),
}
```

Since there is no `__access__` default, N3TX already defaults to `AUTHENTICATED` for all actions. Setting `AUTHENTICATED` everywhere makes this explicit. Schema endpoints (`GET /Source`) are always public (needed for frontend bootstrap), but data endpoints require a valid JWT.

### Eager Loading for Related Data [WIRE]

**Veille need:** Run detail view should show its grants, analyses, and report without N+1 queries.
**N3TX pattern:** `populate` parameter on `get()` and `list()`.

```python
__ui__ = {
    'populate': {'depth': 2},  # Eagerly load 2 levels of relations
}
```

Or via API: `GET /runs/1?populate=grants,report&depth=1`

**Confidence: HIGH** -- Documented in storage.md with `PopulateSpec` pattern.

### Lifecycle Events for Reactive Triggers [WIRE]

**Veille need:** When a Run completes, trigger report generation and email notification.
**N3TX pattern:** `ActorModel._publish_lifecycle()` sends `LIFECYCLE` TX after CRUD operations.

```python
# Subscribe report generator to run lifecycle events
Run._subscribers.append('report_generator')

# ReportGenerator actor receives lifecycle events
class ReportGenerator(ActorModel):
    def LIFECYCLE(self, data, tx):
        if data['event'] == 'after_update' and data['entity']['status'] == 'completed':
            self.generate_report(data['entity']['id'])
```

**Confidence: MEDIUM** -- Lifecycle events are documented in ACTORS.md but the subscriber pattern is described as "future consumers" and may need validation against current implementation.

---

## Anti-Features: What NOT to Build

Common mistakes in this domain that Veille should explicitly avoid.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Custom REST API layer | N3TX generates all CRUD endpoints. Hand-rolling routes bypasses auth, schema, and UI generation. | Use `@expose_route` for custom methods on models. |
| Custom frontend data fetching | The frontend bootstraps from schema. Custom fetch calls bypass the DynamicClass system. | Let schema drive the UI. Use custom components only for domain-specific views. |
| Storing analysis results in a separate service | Adds deployment complexity. SQLite handles the load for single-org. | Store results as fields on Grant or as a related `Analysis` model. |
| Building a custom scheduler service | Overkill. Veille has one scheduled job (weekly scan). | APScheduler in-process, triggered at app startup. |
| Multi-page SPA with custom routing | N3TX Router handles model navigation. Custom routes fight the framework. | Use `ntx-router` with custom components for domain views (run progress, report viewer). |
| Abstracting scraping into a generic framework | Every source is different. A generic scraper adds complexity without value when the LLM handles variation. | Use the LLM-powered agent to adapt to each source. Keep scraping tools simple (fetch, extract text, extract links). |
| Real-time WebSocket for run progress | SSE via streaming endpoints is sufficient and simpler. WebSocket adds protocol complexity. | Use `@expose_route(stream=True)` + `StreamActor` mixin. |
| Custom auth system | N3TX BaseUser + JWT handles everything needed for admin-only access. | Extend `BaseUser`, use `AUTHENTICATED` access rules. |

---

## Feature Dependencies

```
OrgProfile ─────────────────────────────────────────┐
                                                     │
Source CRUD ──┐                                      │
              │                                      │
              ├── Scraping Agent ──┐                  │
              │   (needs sources   │                  │
              │    + web tools)    │                  │
              │                    ├── Grant Storage ─┼── Admissibility Analysis
              │                    │   (extracted     │   (needs grant + profile)
              │                    │    grants)       │
              │                    │                  │
User Auth ────┤                    │                  │
              │                    │                  │
              └── Run Management ──┘                  │
                  (orchestrates                       │
                   scraping +       ──── Report ──────┘
                   analysis)              (needs run results
                                           + admissibility)
```

**Critical path:** Source CRUD -> Scraping Agent -> Grant Storage -> Admissibility Analysis -> Report

**Parallel work:** OrgProfile can be built independently and connected to admissibility later.

---

## MVP Recommendation

### Phase 1: Foundation (All FREE/WIRE)

Build the data models. Get a working app with CRUD for all entities and a basic UI.

1. **Source model** -- CRUD with URL, name, category, is_agent_discovered, notes, last_scraped
2. **Grant model** -- CRUD with full detail fields (title, agency, deadline, amounts, URL, description, status, criteria, required_docs)
3. **OrgProfile model** -- CRUD for organization description (singleton)
4. **Run model** -- CRUD for execution tracking (status, timestamps, counts)
5. **User auth** -- BaseUser extension, admin-only access
6. **Report model** -- CRUD for generated reports (markdown content, linked to Run)
7. **App bootstrap** -- `create_app()` with all models, routing='actor'

**What you get:** A fully navigable web application where an admin can manually manage sources, grants, org profile, and runs. Forms, validation, pagination, auth -- all working.

**Effort estimate:** 1-2 days. Mostly model definitions (~200 lines of Python total).

### Phase 2: Scraping Pipeline (BUILD on WIRE)

Build the agent infrastructure for automated grant discovery.

1. **WebTools actor** -- Scraping utility methods (fetch, extract text, extract links, PDF)
2. **Scraping agent** -- AgentActor instance with tools pointing to sources, grants, web_tools
3. **Run execution** -- `@expose_route('/execute', stream=True)` on Run model
4. **Progress streaming** -- Stream events for frontend progress display
5. **Deduplication** -- URL-based + title similarity check before grant creation

**What you get:** Trigger a run, watch it scrape sources, extract grants, and populate the database.

### Phase 3: Intelligence (BUILD on WIRE)

Add admissibility analysis and automated reasoning.

1. **Analysis method** -- `@expose_route('/analyze')` on Grant using `agentic()` with org profile context
2. **Batch analysis** -- Run orchestrator calls analyze on each new grant
3. **Auto-discovery** -- Agent prompt extension for discovering new sources
4. **Custom widgets** -- Admissibility badge, grant status, score display

**What you get:** Grants are automatically evaluated for admissibility with detailed justification.

### Phase 4: Reporting and Automation

1. **Report generation** -- Markdown/HTML report from run results
2. **PDF export** -- WeasyPrint or equivalent for downloadable reports
3. **Email notification** -- SMTP integration for post-run notifications
4. **Scheduled runs** -- APScheduler for periodic execution
5. **Custom dashboard** -- Run history view, admissibility stats

### Defer to Post-MVP

- **Grant change tracking** -- Detecting when deadlines or criteria change between runs
- **Multi-source merge UI** -- Visual tool for resolving deduplication conflicts
- **Source reliability scoring** -- Track which sources yield actionable grants
- **Cost analytics** -- LLM token usage tracking per run (Pydantic AI `usage()` provides the data)

---

## Confidence Assessment

| Feature Area | Confidence | Basis |
|-------------|------------|-------|
| CRUD generation (Source, Grant, Run, Profile) | HIGH | Verified from examples/grants + framework docs |
| Agent tool discovery + routing | HIGH | Verified from examples/grants + tool-discovery.md |
| Streaming for long operations | HIGH | Verified from agent-actor.md + StreamActor.js docs |
| Widget extension for domain display | HIGH | Verified from widgets.md with clear API |
| JSON field storage for complex data | HIGH | Verified from storage.md + AgentActor.constraints |
| Lifecycle events for reactive triggers | MEDIUM | Documented but marked as "future consumers" in actors.md |
| Scheduled runs via APScheduler | MEDIUM | Standard Python pattern, not N3TX-specific -- needs library verification |
| PDF generation | LOW | Outside N3TX scope -- library choice needed (WeasyPrint/reportlab) |
| Email notification | LOW | Outside N3TX scope -- SMTP integration is standard Python |

---

## Sources

- `/workspace/docs/CORE.md` -- Schema-driven development, what gets generated
- `/workspace/docs/AGENTS.md` -- Agent capabilities, tool discovery, streaming
- `/workspace/docs/ACTORS.md` -- Actor system, TX messaging, lifecycle events
- `/workspace/docs/ARCHITECTURE.md` -- System architecture, extension points
- `/workspace/packages/n3tx-agents/docs/agent-actor.md` -- AgentActor fields, agentic() override
- `/workspace/packages/n3tx-agents/docs/mixin.md` -- AgentMixin methods, streaming
- `/workspace/packages/n3tx-agents/docs/tool-discovery.md` -- Tool discovery pipeline
- `/workspace/packages/n3tx-core/docs/storage.md` -- SQLite backend, JSON fields, pagination
- `/workspace/packages/n3tx-core/docs/authorization.md` -- Access rules, ABAC
- `/workspace/packages/n3tx-core/docs/app-bootstrap.md` -- create_app(), config
- `/workspace/packages/n3tx-ui/docs/widgets.md` -- Widget system, extension API
- `/workspace/packages/n3tx-ui/docs/components.md` -- Component hierarchy, StreamActor
- `/workspace/packages/n3tx-ui/docs/formidable.md` -- Schema-driven form generation
- `/workspace/packages/n3tx-ui/docs/viewable-mixin.md` -- UI hints, __ui__ config
- `/workspace/examples/grants/` -- Reference implementation for grant-watching app
- `/workspace/apps/veille/.planning/PROJECT.md` -- Veille project requirements
