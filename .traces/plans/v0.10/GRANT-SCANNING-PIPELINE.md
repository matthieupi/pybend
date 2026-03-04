# Grant Scanning Pipeline — Implementation Plan

## Context

The Grant Watcher app currently has models (Grant, Source, WebTools, AgentActor) but no automated pipeline. Users must manually trigger the agent or create grants by hand. This plan implements an end-to-end automated pipeline: a scheduler wakes up periodically, scrapes all sources for grant URLs, deduplicates against the DB, creates new Grant entries, runs LLM eligibility analysis against org docs, and produces a WatchReport.

## Architecture

```
SchedulerActor (asyncio loop, configurable interval)
    │
    ▼ triggers
ScanPipeline._execute_scan()
    │
    ├── 1. Source.list() → load all sources
    ├── 2. WebTools.scrape(source.url) → get HTML per source
    ├── 3. Parse HTML for grant-like links (BeautifulSoup)
    ├── 4. Grant.list() → dedup by URL
    ├── 5. Grant.create() → insert new grants (eligibility='pending')
    ├── 6. GrantAnalyzer.analyze(grant) → LLM eligibility per grant
    │       └── loads org docs from example_grants/org_docs/
    │       └── calls agent_run() (pydantic-ai, no tools, text analysis only)
    │       └── updates grant.eligibility + grant.eligibility_reasoning
    └── 7. WatchReport.create() → persist scan results
```

All new actors live in `example_grants/actors/` (app-level, not framework core).

---

## Step 1: Add eligibility fields to Grant

**File:** `example_grants/models/grant.py`

Add two fields to the `Grant` class:
- `eligibility: Literal['pending', 'eligible', 'partial', 'ineligible']` — default `'pending'`
- `eligibility_reasoning: TextareaField` — default `''`, LLM explanation

These are orthogonal to the existing `status` workflow field. SQLite auto-migration adds the columns on startup (TEXT with defaults — no manual migration needed).

## Step 2: Create WatchReport model

**New file:** `example_grants/models/watch_report.py`

Storable ActorModel capturing pipeline run results:
- `scan_date: str` — ISO timestamp
- `sources_scanned: int`
- `grants_found: int` — total URLs discovered
- `grants_new: int` — new grants created (after dedup)
- `grants_eligible: int` — grants marked eligible/partial
- `status: Literal['running', 'completed', 'failed']`
- `summary: TextareaField` — human-readable summary
- `error_log: TextareaField` — errors (hidden in UI via `display: False`)

Access: ANYONE read, AUTHENTICATED create, ROLE('admin') update/delete.

**Update:** `example_grants/models/__init__.py` — add WatchReport export.

## Step 3: Create org docs utility

**New file:** `example_grants/utils/org_docs.py`

`load_org_context(docs_dir=None) -> str`: reads all `.md`/`.txt` files from `example_grants/org_docs/`, returns concatenated string with file headers. Returns fallback message if dir missing/empty. This is the abstraction boundary — when Teams/Drive/Obsidian agents arrive later, only this function changes.

**New file:** `example_grants/org_docs/mission.md`

Sample org profile: name, mission, focus areas, eligibility criteria, ineligible categories. Gives the LLM something concrete to analyze against.

## Step 4: Create GrantAnalyzer actor

**New file:** `example_grants/actors/analyzer.py`

Non-storable ActorModel with `__agent__ = True` (injects AgentMixin):
- `__tablename__ = 'grant_analyzer'`, `__storable__ = False`
- `analyze(grant) -> dict` — loads org docs via `load_org_context()`, constructs prompt with grant details + org context, calls `self.agent_run(prompt=..., tools=[], task=...)`. Parses LLM response into `(eligibility, reasoning)`, updates Grant record.
- `_parse_eligibility(answer) -> tuple[str, str]` — parses LLM output into status + reasoning.

Key: `tools=[]` means no tool calls — pure text analysis. The LLM reads the grant description and org docs, returns eligibility determination.

## Step 5: Create ScanPipeline actor

**New file:** `example_grants/actors/pipeline.py`

Non-storable ActorModel that orchestrates a single scan run:
- `__tablename__ = 'scan_pipeline'`, `__storable__ = False`
- `@expose_route('/run', methods=['POST'], access=ROLE('admin'))` — manual trigger via API
- `_execute_scan(user=None) -> dict` — core pipeline:
  1. Create WatchReport with `status='running'`
  2. `Source.list()` → iterate sources
  3. Per source: `WebTools().scrape(url)` → parse HTML for grant-like links
  4. `Grant.list(limit=10000)` → collect existing URLs for dedup
  5. Filter out known URLs
  6. `Grant.create()` for each new discovery
  7. `GrantAnalyzer().analyze(grant)` for each new grant
  8. Update WatchReport with final stats, `status='completed'`
  9. Return summary dict

- `_scrape_source(source) -> list[dict]` — calls WebTools.scrape(), parses HTML with BeautifulSoup for `a[href]` links that match grant keywords
- `_looks_like_grant(href, text) -> bool` — heuristic keyword matching (grant, funding, solicitation, opportunity, etc.)

## Step 6: Create SchedulerActor

**New file:** `example_grants/actors/scheduler.py`

Non-storable ActorModel with pure asyncio scheduling:
- `__tablename__ = 'scheduler'`, `__storable__ = False`
- Constructor takes `interval_seconds` (default 6h, configurable via `SCAN_INTERVAL_SECONDS` env var)
- `start()` — sets `_running=True`, launches `asyncio.create_task(self._loop())`
- `stop()` — sets `_running=False`, cancels task
- `_loop()` — calls `run_once()`, then `asyncio.sleep(interval)`, repeat
- `run_once()` — creates ScanPipeline, calls `_execute_scan()`. Testable without timer.
- `@expose_route('/trigger')` — manual trigger via API (admin only)
- `@expose_route('/status')` — returns running state + interval

Uses `object.__setattr__` for `_task`, `_running`, `_interval` (Pydantic V2 compatibility — these are runtime state, not model fields).

Disabled when `interval_seconds=0` (for tests).

## Step 7: Wire into main.py

**File:** `example_grants/main.py`

1. Import new models: `WatchReport`, `ScanPipeline`, `SchedulerActor`, `GrantAnalyzer`
2. Add to `create_app(models=[...])` list
3. Create scheduler instance with configurable interval
4. Add FastAPI lifespan context manager:
   ```python
   @asynccontextmanager
   async def lifespan(app):
       if scheduler._interval > 0:
           await scheduler.start()
       yield
       await scheduler.stop()
   app.router.lifespan_context = lifespan
   ```
5. Add `SCAN_INTERVAL_SECONDS` env var (default 21600 = 6h)

## Step 8: Create actors package

**New file:** `example_grants/actors/__init__.py`

Exports: `SchedulerActor`, `ScanPipeline`, `GrantAnalyzer`

## Step 9: Update seed.py

**File:** `example_grants/seed.py`

- Import WatchReport
- Register WatchReport with storage
- Add one sample completed WatchReport to seed data

## Step 10: Update conftest.py

**File:** `example_grants/tests/conftest.py`

Minimal changes — the existing `from main import app` triggers all model registration. Add WatchReport import to `_seed_*` if needed. Set `SCAN_INTERVAL_SECONDS=0` in test env to prevent scheduler from running during tests.

## Step 11: Comprehensive tests

**New file:** `example_grants/tests/test_scan_pipeline.py`

Test classes following existing patterns (pytest, `conftest.py` fixtures):

| Test Class | Tests |
|---|---|
| **TestGrantEligibility** | new fields exist, default values, schema includes them, update works |
| **TestWatchReport** | CRUD, schema endpoint, status values, list/get |
| **TestOrgDocs** | reads files, missing dir fallback, empty dir fallback, extension filter |
| **TestGrantAnalyzer** | parse eligibility response, analyze with mocked LLM (TestModel), error handling |
| **TestScanPipelineDedup** | filters existing URLs, allows new URLs, handles empty DB |
| **TestScanPipelineScrape** | mocked httpx for scrape, non-200 handling, keyword heuristic |
| **TestPipelineFull** | end-to-end with mocked scrape + LLM, creates report, handles failures |
| **TestScheduler** | run_once, start/stop lifecycle, trigger API, status API, configurable interval |

LLM calls mocked with `pydantic_ai.models.test.TestModel(call_tools=[])`. HTTP calls mocked at the WebTools level (pass mock HTML directly).

---

## Files Summary

| File | Action |
|---|---|
| `example_grants/models/grant.py` | Modify — add eligibility + eligibility_reasoning |
| `example_grants/models/watch_report.py` | Create — WatchReport model |
| `example_grants/models/__init__.py` | Modify — export WatchReport |
| `example_grants/utils/org_docs.py` | Create — org doc loader |
| `example_grants/org_docs/mission.md` | Create — sample org profile |
| `example_grants/actors/__init__.py` | Create — package init |
| `example_grants/actors/analyzer.py` | Create — GrantAnalyzer actor |
| `example_grants/actors/pipeline.py` | Create — ScanPipeline orchestrator |
| `example_grants/actors/scheduler.py` | Create — SchedulerActor |
| `example_grants/main.py` | Modify — register models, lifespan hook |
| `example_grants/seed.py` | Modify — seed WatchReport |
| `example_grants/tests/conftest.py` | Modify — env var for scheduler |
| `example_grants/tests/test_scan_pipeline.py` | Create — full test suite |

## Verification

1. **Unit tests:** `cd /workspace && python -m pytest example_grants/tests/test_scan_pipeline.py -v`
2. **All existing tests still pass:** `cd /workspace && python -m pytest example_grants/tests/ -v`
3. **Manual smoke test:**
   - `cd /workspace/example_grants && python seed.py --reset && python main.py`
   - `GET /WatchReport` — schema endpoint returns valid JSON schema
   - `GET /Grant` — schema includes eligibility + eligibility_reasoning fields
   - `POST /scan_pipeline/run` (admin token) — triggers pipeline
   - `GET /watch_reports` — shows completed report
   - `GET /scheduler/status` — shows running state
