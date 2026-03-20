# Phase 4: Reports and Run Management - Research

**Researched:** 2026-03-20
**Domain:** Run report generation, run history comparison, asyncio-based scheduling, N3TX class-level expose_route, html.parser aggregation
**Confidence:** HIGH (all findings from source code in the veille codebase and N3TX framework)

## Summary

Phase 4 has three distinct concerns that map to three success criteria:

**RPT-01 (Run Reports):** Each completed run needs a structured report view showing grants grouped by admissibility classification (admissible / partially admissible / non-admissible) with justifications. The data already exists — `Grant.run_id`, `Grant.status`, `Grant.admissibility_score`, and `Grant.admissibility_reasoning` are all populated after Phase 3. No new model fields required. The report is computed by filtering grants by `run_id` and grouping by `status`. The cleanest pattern is a class-level `@expose_route('/report', methods=['GET'])` on `Run` that returns a structured report dict, plus a `<ntx-run-report>` frontend component in the app's `static/components/`.

**RUN-02 (Run History):** The `runs` table already contains all needed fields (`status`, `type`, `started_at`, `completed_at`, `grants_found`, `sources_covered`). Run history browsing means navigating the existing `ntx-list model="Run"` data. Comparison across runs (new grants found, status changes) requires querying grants by `run_id`. The run panel component can be extended with a history tab, or a separate `<ntx-run-history>` component can present runs as a timeline/table.

**RUN-04 (Scheduled Runs):** No external scheduler library is installed. The correct approach is a pure-asyncio background loop started via `app.router.on_startup.append()` in `main.py`. The schedule configuration (enabled flag + interval) lives on the `Organization` model (add 2 fields: `schedule_enabled: bool` and `schedule_interval_hours: int`). The loop reads the org schedule config, checks the last completed run time, and triggers a new `full` run if the interval has elapsed.

**Primary recommendation:** Three backend additions (Run.report() class method, schedule fields on Organization, startup scheduler loop in main.py), one new frontend component (`<ntx-run-report>`), and expansion of `<ntx-run-panel>` with a history section. No new DB migrations beyond Organization schedule fields.

---

## Existing State (verified from source code)

### Grant fields relevant to reports (already present after Phase 3)

| Field | Type | Report relevance |
|-------|------|-----------------|
| `run_id` | `Optional[int]` | Groups grants by run |
| `status` | `str` | Classification bucket: `admissible`, `partially admissible`, `non-admissible`, `new` |
| `admissibility_score` | `Optional[float]` | Sort criterion within each bucket (0.0–1.0) |
| `admissibility_reasoning` | `MarkdownField` | Justification text (rendered as Markdown) |
| `title` | `str` | Display name in report |
| `funder` | `str` | Display in report |
| `deadline` | `Optional[str]` | Key field for urgency sorting |
| `amount_min/max` | `Optional[float]` | Financial context in report |
| `url` | `str` | Link from report to grant page |

### Run fields relevant to history (already present)

| Field | Type | History relevance |
|-------|------|-----------------|
| `id` | `int` | Unique run identifier |
| `status` | `str` | `pending`, `running`, `complete`, `failed` |
| `type` | `str` | `full`, `adhoc` |
| `started_at` | `Optional[str]` | Timestamp for timeline |
| `completed_at` | `Optional[str]` | Duration calculation |
| `grants_found` | `int` | Key metric for comparison |
| `sources_covered` | `int` | Context for full runs |
| `error` | `str` | Error detail for failed runs |

**Conclusion:** No new fields needed on `Grant` or `Run` for RPT-01 and RUN-02. Only `Organization` needs 2 new fields for RUN-04.

---

## Standard Stack

### Core (already installed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.135.1 | App framework | Already in use |
| asyncio | stdlib | Background scheduler loop | No external dependency needed |
| N3TX ActorModel + expose_route | 0.10 | Backend patterns | Established in phases 1-3 |

### Supporting (already installed)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| sse-starlette | 3.3.2 | SSE for streaming | Already used by execute/analyze |
| marked.js | vendor | Markdown rendering | Already loaded in index.html |

### Not Needed (confirmed absent and not required)

| Excluded | Reason |
|----------|--------|
| APScheduler | Overkill for one background loop; pure asyncio is simpler and stdlib-only |
| Celery/Redis | Overkill; single-process, single-org app |
| External cron | Would require system-level configuration outside the app |

**Installation:** Nothing new to install.

---

## Architecture Patterns

### Recommended Change to Project Structure

```
apps/veille/
├── models/
│   ├── organization.py       # MODIFIED: add schedule_enabled, schedule_interval_hours fields
│   └── run.py               # MODIFIED: add class-level report() @expose_route
├── main.py                   # MODIFIED: add startup scheduler loop
└── static/
    └── components/
        ├── ntx-run-panel.js  # MODIFIED: add run history section
        └── ntx-run-report.js  # NEW: report view component for a single run
```

---

### Pattern 1: Class-Level @expose_route for Report Aggregation

**What:** A class method (no `self`) on `Run` that takes `run_id` as a query param and returns grouped grant data. Gets registered at `GET /runs/report`.

**When to use:** When the route doesn't operate on a single Run instance, but aggregates data across Grants for a given run.

**Verified in:** `network_api.py:_register_custom_routes` line 393-396: `is_instance_method = 'self' in sig.parameters`. If `self` absent, `full_route = f"{endpoint_base}{route}"` (no `/{id:int}`).

```python
# Source: pattern verified from network_api.py _register_custom_routes
@expose_route('/report', methods=['GET'], access=AUTHENTICATED)
def report(cls, run_id: int) -> dict:
    """Return structured admissibility report for a run.

    Route: GET /runs/report?run_id=42
    Returns grants grouped by status with counts and score averages.
    """
    from models.grant import Grant

    # Filter grants for this run using sql_filter
    grants_data = Grant.list(
        sql_filter=('run_id = ?', [run_id]),
        limit=1000
    )
    data = grants_data.get('data', grants_data) if isinstance(grants_data, dict) else grants_data

    admissible = []
    partial = []
    inadmissible = []
    new = []

    for g in data:
        gd = g if isinstance(g, dict) else (g.model_dump() if hasattr(g, 'model_dump') else {})
        status = gd.get('status', 'new')
        if status == 'admissible':
            admissible.append(gd)
        elif status == 'partially admissible':
            partial.append(gd)
        elif status == 'non-admissible':
            inadmissible.append(gd)
        else:
            new.append(gd)

    return {
        'run_id': run_id,
        'admissible': sorted(admissible, key=lambda g: g.get('admissibility_score') or 0, reverse=True),
        'partially_admissible': sorted(partial, key=lambda g: g.get('admissibility_score') or 0, reverse=True),
        'non_admissible': inadmissible,
        'new': new,
        'counts': {
            'admissible': len(admissible),
            'partially_admissible': len(partial),
            'non_admissible': len(inadmissible),
            'new': len(new),
            'total': len(data),
        },
    }
```

**Note on `sql_filter`:** `StorableMixin.list()` accepts `sql_filter=(where_clause, params)` as a raw WHERE clause tuple. Verified in `sqlite_storage.py:list()` line 182-186. This is the correct way to filter grants by `run_id` without loading all grants.

**Important:** The `report` method must be a `@classmethod` decorator on the model (not just a plain function). The N3TX `@expose_route` decorator works on classmethods.

```python
@classmethod
@expose_route('/report', methods=['GET'], access=AUTHENTICATED)
def report(cls, run_id: int) -> dict:
    ...
```

---

### Pattern 2: Organization Schedule Fields

**What:** Two new fields on `Organization` control when automated runs fire.

**When to use:** The scheduler loop reads these fields at each check interval.

```python
# Source: pattern from apps/veille/models/organization.py (to be modified)

# Schedule config (RUN-04)
schedule_enabled: bool = Field(default=False)
schedule_interval_hours: int = Field(default=168)  # 168 hours = weekly
```

`schedule_interval_hours` defaults to 168 (one week). Configurable via the org profile edit form (auto-generated by Formidable from schema). The UI group for these fields should be `'Schedule'`.

---

### Pattern 3: Asyncio Background Scheduler in main.py

**What:** An async loop started at app startup that checks whether a scheduled run is due and triggers it.

**When to use:** For the single scheduled job (RUN-04). No external library needed.

**FastAPI startup hook:** `app.router.on_startup` is a list. Appending a coroutine function to it works and avoids `on_event('startup')` deprecation warnings (verified: `on_event` shows deprecation warning in FastAPI 0.135.1; `app.router.on_startup.append()` does not).

```python
# Source: pattern from FastAPI internals (verified)
# In main.py, AFTER the app = create_app(...) call:

import asyncio
from datetime import datetime, timezone

async def _scheduler_loop():
    """Background loop that fires scheduled runs.

    Checks every 15 minutes whether a scheduled run is due.
    Reads schedule config from the Organization model.
    """
    CHECK_INTERVAL = 900  # 15 minutes between checks

    await asyncio.sleep(30)  # Wait for app to fully start

    while True:
        try:
            from models.organization import Organization
            from models.run import Run

            orgs = Organization.list(limit=1)
            data = orgs.get('data', orgs) if isinstance(orgs, dict) else orgs

            if not data:
                await asyncio.sleep(CHECK_INTERVAL)
                continue

            org = data[0]
            enabled = (org.get('schedule_enabled') if isinstance(org, dict)
                       else getattr(org, 'schedule_enabled', False))
            interval = (org.get('schedule_interval_hours') if isinstance(org, dict)
                        else getattr(org, 'schedule_interval_hours', 168))

            if not enabled:
                await asyncio.sleep(CHECK_INTERVAL)
                continue

            # Find the last completed full run
            all_runs = Run.list(
                sql_filter=("status = ? AND type = ?", ['complete', 'full']),
                limit=1000
            )
            runs_data = (all_runs.get('data', all_runs)
                         if isinstance(all_runs, dict) else all_runs)

            # Sort by completed_at descending, find most recent
            completed = [r for r in runs_data
                         if (r.get('completed_at') if isinstance(r, dict)
                             else getattr(r, 'completed_at', None))]

            now = datetime.now(timezone.utc)
            should_run = True

            if completed:
                # Parse most recent completed_at
                last_run = max(
                    completed,
                    key=lambda r: (r.get('completed_at') if isinstance(r, dict)
                                   else getattr(r, 'completed_at', ''))
                )
                last_ts_str = (last_run.get('completed_at') if isinstance(last_run, dict)
                               else getattr(last_run, 'completed_at', None))
                if last_ts_str:
                    try:
                        last_ts = datetime.fromisoformat(last_ts_str)
                        if last_ts.tzinfo is None:
                            last_ts = last_ts.replace(tzinfo=timezone.utc)
                        elapsed_hours = (now - last_ts).total_seconds() / 3600
                        should_run = elapsed_hours >= interval
                    except (ValueError, TypeError):
                        pass

            if should_run:
                logger.info("Scheduler: triggering scheduled full run")
                try:
                    from datetime import datetime as _dt, timezone as _tz
                    run_record = Run.create(Run(
                        type='full',
                        status='pending',
                    ))
                    run_id = (run_record.get('id') if isinstance(run_record, dict)
                              else getattr(run_record, 'id', None))
                    if run_id:
                        raw = Run.get(run_id)
                        run_instance = (Run(**raw) if isinstance(raw, dict)
                                        else raw)
                        # Run execute() non-streaming (background task)
                        # We consume the async generator to drive execution
                        async for _ in run_instance.execute():
                            pass
                        logger.info(f"Scheduler: run {run_id} complete")
                except Exception as e:
                    logger.error(f"Scheduler: run failed: {e}")

        except Exception as e:
            logger.error(f"Scheduler loop error: {e}")

        await asyncio.sleep(CHECK_INTERVAL)


# Wire up scheduler AFTER app is created:
app.router.on_startup.append(_scheduler_loop)
```

**Important:** `asyncio.create_task()` cannot be called before the event loop is running. Using `app.router.on_startup.append()` defers the task creation until Uvicorn has started the event loop. Inside the handler, wrap `asyncio.create_task(_scheduler_loop())` to make it non-blocking.

```python
# Correct startup registration pattern:
async def _start_scheduler():
    asyncio.create_task(_scheduler_loop())

app.router.on_startup.append(_start_scheduler)
```

---

### Pattern 4: sql_filter for Run History Queries

**What:** Using `StorableMixin.list(sql_filter=...)` to query runs and grants with WHERE clauses.

**Verified in:** `sqlite_storage.py:list()` line 182-186: `select_sql += f" WHERE {clause}"`.

```python
# Query grants by run_id:
grants_data = Grant.list(
    sql_filter=('run_id = ?', [run_id]),
    limit=1000
)

# Query completed full runs ordered by time:
# Note: StorableMixin.list() does NOT support ORDER BY in sql_filter
# ORDER must be done in Python after fetching
runs_data = Run.list(
    sql_filter=("status = ? AND type = ?", ['complete', 'full']),
    limit=1000
)
```

**IMPORTANT:** `sql_filter` only supports WHERE clauses. It does NOT support `ORDER BY` or `GROUP BY`. Sorting must be done in Python after the list() call. This is a key constraint.

---

### Pattern 5: Frontend Report Component

**What:** A `<ntx-run-report>` Web Component that loads report data from `GET /runs/report?run_id=N` and renders grants in three sections.

**When to use:** Activated from `#report/{run_id}` hash route, same pattern as `#analyze/{id}` for ntx-grant-analyze.

```javascript
// Source: pattern mirrors ntx-grant-analyze.js exactly
import { config } from '../config.js';

class NTXRunReport extends HTMLElement {
    #runId = null;
    #els;

    static get observedAttributes() { return ['run-id']; }

    attributeChangedCallback(name, oldVal, newVal) {
        if (name === 'run-id' && newVal && newVal !== oldVal) {
            this.#runId = newVal;
            if (this.shadowRoot) this.#loadReport();
        }
    }

    connectedCallback() {
        this.attachShadow({ mode: 'open' });
        // ... render skeleton ...
        if (this.#runId) this.#loadReport();
    }

    async #loadReport() {
        const token = localStorage.getItem('jwtToken');
        const resp = await fetch(
            `${config.API_URL}/runs/report?run_id=${this.#runId}`,
            { headers: { 'x-access-token': token } }
        );
        const data = await resp.json();
        this.#renderReport(data);
    }

    #renderReport(data) {
        // Render three sections: admissible, partially admissible, non-admissible
        // Each section shows: title, funder, score, deadline, link to analyze panel
    }
}

customElements.define('ntx-run-report', NTXRunReport);
export { NTXRunReport };
```

---

### Pattern 6: Run History in ntx-run-panel

**What:** Extend the existing `<ntx-run-panel>` to show a list of past runs with a "View Report" link for each completed run.

**When to use:** The run panel already shows current run status. Adding a history tab gives RUN-02 without a separate component.

**Implementation approach:** Fetch `GET /runs?limit=20` (existing CRUD endpoint) on panel mount. Render a history list below the controls showing run records with their key metrics.

```javascript
// Inside NTXRunPanel.connectedCallback(), after wiring button handlers:
this.#loadHistory();

async #loadHistory() {
    const token = localStorage.getItem('jwtToken');
    const resp = await fetch(`${config.API_URL}/runs?limit=20`, {
        headers: { 'x-access-token': token },
    });
    const data = await resp.json();
    const runs = data.data || data;
    this.#renderHistory(runs);
}

#renderHistory(runs) {
    const historyEl = this.shadowRoot.getElementById('history');
    // Sort by started_at descending (do in JS since list() doesn't ORDER BY)
    const sorted = [...runs].sort((a, b) =>
        (b.started_at || '').localeCompare(a.started_at || '')
    );
    historyEl.innerHTML = sorted.map(r => `
        <div class="history-row ${r.status}">
            <span class="run-date">${r.started_at?.slice(0, 10) || '—'}</span>
            <span class="run-type">${r.type}</span>
            <span class="run-status">${r.status}</span>
            <span class="run-grants">${r.grants_found} grants</span>
            ${r.status === 'complete' ? `
                <a class="view-report-link" href="#report/${r.id}">View Report</a>
            ` : ''}
        </div>
    `).join('');
}
```

---

### Pattern 7: Hash Routing Additions in index.html

**What:** Add two new hash routes: `#report/{run_id}` and updated `handleRoute()` in index.html.

**When to use:** Same hide-all-then-show pattern already in use (confirmed decision: Hide-all-then-show in handleRoute()).

```javascript
// Source: apps/veille/static/index.html handleRoute() (to be modified)
function handleRoute() {
    const hash = window.location.hash.replace('#', '') || '';

    // Panels to manage (add reportPanel to the list)
    const runPanel = document.getElementById('run-panel');
    const sourceList = document.getElementById('source-list');
    const uploadSection = document.getElementById('upload-section');
    const analyzePanel = document.getElementById('analyze-panel');
    const reportPanel = document.getElementById('report-panel');  // NEW

    // Hide all panels
    [runPanel, sourceList, uploadSection, analyzePanel, reportPanel].forEach(el => {
        if (el) el.style.display = 'none';
    });

    if (hash === 'runs') {
        if (runPanel) runPanel.style.display = 'block';
    } else if (hash.startsWith('analyze/')) {
        const grantId = hash.split('/')[1];
        if (analyzePanel && grantId) {
            analyzePanel.setAttribute('grant-id', grantId);
            analyzePanel.style.display = 'block';
        }
    } else if (hash.startsWith('report/')) {     // NEW
        const runId = hash.split('/')[1];
        if (reportPanel && runId) {
            reportPanel.setAttribute('run-id', runId);
            reportPanel.style.display = 'block';
        }
    } else {
        if (sourceList) sourceList.style.display = '';
        if (uploadSection) uploadSection.style.display = '';
    }
}
```

---

### Anti-Patterns to Avoid

- **Fetching all grants and filtering in Python post-list:** Use `sql_filter=('run_id = ?', [run_id])` not `Grant.list(limit=10000)` followed by Python filter. The former is efficient; the latter loads the whole table.
- **Using `@expose_route` with `self` for a report method:** The report operates across multiple grants for a run; it is not an instance-level operation on a single Run record. Use a classmethod.
- **`asyncio.create_task()` directly in `main.py` module body:** Module-level async code has no running event loop. The task must be created inside a coroutine registered with the ASGI startup.
- **Using `app.on_event('startup')` decorator:** Deprecated in FastAPI 0.135.1. Use `app.router.on_startup.append(coro_fn)` instead.
- **Storing a pre-built Report in a new DB table:** The report is derived data (filtered/grouped grants). Computing it on-demand avoids a cache invalidation problem when grants are re-analyzed. No `Report` model needed.
- **Using ORDER BY in sql_filter:** `StorableMixin.list()` does not support ORDER BY — only WHERE clause. Sort in Python after fetching.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Per-run grant aggregation | Custom SQL query outside ORM | `Grant.list(sql_filter=('run_id = ?', [id]))` | Keeps storage abstraction; same pattern as auth pushdown filters |
| Scheduling library | APScheduler integration | Pure asyncio loop + `app.router.on_startup.append()` | No new dependency; stdlib asyncio handles one background loop cleanly |
| Report storage model | `Report` DB table | Computed on demand in `Run.report()` classmethod | Data already in `grants` table; avoids cache staleness after re-analysis |
| Run history pagination | Custom paginator | `Run.list(limit=20)` (existing pagination) | Automatically returns `{data: [...], meta: {total, ...}}` |
| Markdown rendering in report | Custom Markdown parser | `marked.js` (already loaded in index.html) | Already available as `window.marked`; zero setup |

**Key insight:** Reports are a view over existing data (grants grouped by run_id and status). The data model is already complete after Phase 3. Phase 4 adds a query endpoint, a presentation component, and a scheduler — not new storage.

---

## Common Pitfalls

### Pitfall 1: `@classmethod` + `@expose_route` Decorator Order

**What goes wrong:** `@expose_route` applied directly to a classmethod's inner function instead of to the classmethod descriptor raises `AttributeError` or silently skips the route.
**Why it happens:** Python descriptor protocol: `@classmethod` must wrap `@expose_route`, or equivalently, `@expose_route` must be the outermost decorator.
**How to avoid:** Apply decorators in this order (innermost to outermost, i.e., bottom to top):
```python
@classmethod
@expose_route('/report', methods=['GET'], access=AUTHENTICATED)
def report(cls, run_id: int) -> dict:
    ...
```
**Warning signs:** `GET /runs/report` returns 404 or is missing from route list.

**Verification needed:** The exact decorator order for `@classmethod` + `@expose_route` needs runtime testing. If it fails, the fallback is a plain function (not classmethod) — N3TX detects it's not an instance method (`self` absent) and registers it as a class-level route regardless.

### Pitfall 2: `asyncio.create_task()` Before Event Loop is Running

**What goes wrong:** `asyncio.create_task(_scheduler_loop())` at module level raises `RuntimeError: no running event loop`.
**Why it happens:** The asyncio event loop doesn't exist until Uvicorn starts it. Module-level code runs before Uvicorn.
**How to avoid:** Always wrap `asyncio.create_task()` inside a startup coroutine:
```python
async def _start_scheduler():
    asyncio.create_task(_scheduler_loop())

app.router.on_startup.append(_start_scheduler)
```
**Warning signs:** `RuntimeError: no running event loop` in server startup logs.

### Pitfall 3: Scheduler Loop Blocking the Event Loop

**What goes wrong:** The scheduler loop calls synchronous code (SQLite queries, Run.create()) that blocks the asyncio event loop, preventing other requests from being served.
**Why it happens:** `StorableMixin` storage operations are synchronous (SQLite). When called from an async context, they run in the event loop thread.
**How to avoid:** Keep the `await asyncio.sleep(CHECK_INTERVAL)` between iterations. For the actual run execution (`execute()` async generator), use `asyncio.create_task()` so the scheduler loop doesn't wait for the run to finish:
```python
if should_run:
    asyncio.create_task(_run_scheduled_run())
```
**Warning signs:** App becomes unresponsive during scheduled run execution.

### Pitfall 4: Internal TX Auth Bypass on Scheduled Runs

**What goes wrong:** Scheduled run creates a Run record and triggers `execute()` programmatically. The `execute()` method calls `Grant.list()`, `Run.update()` etc. internally — these go through the actor system (Level 3) without a JWT token, potentially with no `meta.user` context.
**Why it happens:** In Level 3, ALL operations go through the Matrix actor system. Internal operations from Python code (not from HTTP) have no user context in TX meta. The `auth_interceptor` on `NetworkAPI` only fires for incoming HTTP requests. Direct `Run.create()` / `Run.update()` calls from Python bypass this.
**How to avoid:** At Level 3, direct Python calls to `Model.create()`, `Model.update()`, `Model.list()` go through the Actor's `handler_crud()`. The second-tier auth (`_authorize()`) checks `tx.meta.get('user')` — if absent (None), it trusts the call (internal message). This is safe for a single-org server where the scheduler is a trusted internal process.
**Warning signs:** If authorization is tightened later (per-resource ownership), scheduled runs may fail. Document the assumption that scheduler is a trusted process.

### Pitfall 5: sql_filter Parameters Type Mismatch

**What goes wrong:** `Grant.list(sql_filter=('run_id = ?', run_id))` where `run_id` is an int raises `sqlite3.ProgrammingError: Error binding parameter 0`.
**Why it happens:** `sql_filter` takes `(clause, params)` where `params` must be an iterable (list or tuple), not a bare value.
**How to avoid:** Always pass params as a list:
```python
# WRONG:
Grant.list(sql_filter=('run_id = ?', run_id))

# CORRECT:
Grant.list(sql_filter=('run_id = ?', [run_id]))
```
**Warning signs:** `sqlite3.ProgrammingError` in server logs when `/runs/report` is called.

### Pitfall 6: Report Link in ntx-run-panel Opens Before Run is Complete

**What goes wrong:** User clicks "View Report" while run is still in `running` status. Report shows empty grant list.
**Why it happens:** `grants_found` count is only reliable after `status='complete'`. Grants may not be analyzed yet.
**How to avoid:** Only show "View Report" link for runs with `status='complete'` in the history list (already handled in Pattern 6 template: `${r.status === 'complete' ? ... : ''}`).
**Warning signs:** Report shows 0 grants for active runs.

### Pitfall 7: Scheduler Fires Multiple Runs if Check is Too Frequent

**What goes wrong:** Scheduler fires a new run every 15 minutes because the previous run is still in `running` status and thus not counted as the "last completed" run.
**Why it happens:** The check only looks at `completed` runs. A long-running run (60+ minutes) could cause the scheduler to fire again.
**How to avoid:** Also check for `running` runs before scheduling:
```python
running = [r for r in runs_data
           if (r.get('status') if isinstance(r, dict)
               else getattr(r, 'status', '')) == 'running']
if running:
    # Skip — a run is already in progress
    await asyncio.sleep(CHECK_INTERVAL)
    continue
```
**Warning signs:** Multiple concurrent runs in the database.

---

## Code Examples

### Run.report() classmethod

```python
# Source: pattern from StorableMixin.list() sql_filter (verified)
# In apps/veille/models/run.py

@classmethod
@expose_route('/report', methods=['GET'], access=AUTHENTICATED)
def report(cls, run_id: int) -> dict:
    """Return a structured admissibility report for a completed run.

    Route: GET /runs/report?run_id=42
    """
    from models.grant import Grant

    grants_raw = Grant.list(
        sql_filter=('run_id = ?', [run_id]),
        limit=1000
    )
    grants = grants_raw.get('data', grants_raw) if isinstance(grants_raw, dict) else grants_raw

    admissible, partial, inadmissible, pending = [], [], [], []
    for g in grants:
        gd = g if isinstance(g, dict) else (g.model_dump() if hasattr(g, 'model_dump') else {})
        status = gd.get('status', 'new')
        if status == 'admissible':
            admissible.append(gd)
        elif status == 'partially admissible':
            partial.append(gd)
        elif status == 'non-admissible':
            inadmissible.append(gd)
        else:
            pending.append(gd)

    def by_score(g):
        return g.get('admissibility_score') or 0

    return {
        'run_id': run_id,
        'admissible': sorted(admissible, key=by_score, reverse=True),
        'partially_admissible': sorted(partial, key=by_score, reverse=True),
        'non_admissible': inadmissible,
        'new': pending,
        'counts': {
            'admissible': len(admissible),
            'partially_admissible': len(partial),
            'non_admissible': len(inadmissible),
            'new': len(pending),
            'total': len(grants),
        },
    }
```

### Organization schedule fields

```python
# Source: apps/veille/models/organization.py (to be modified)
# Add to Organization model after existing fields:

# Schedule config (RUN-04)
schedule_enabled: bool = Field(default=False)
schedule_interval_hours: int = Field(default=168,  # 168h = weekly
    json_schema_extra={'ui': {'widget': 'number', 'placeholder': '168 (weekly)'}})
```

And add `'schedule_enabled', 'schedule_interval_hours'` to `__ui__`:
```python
__ui__ = {
    'field_order': [
        'name', 'mission', 'activities', 'legal_status',
        'province', 'charitable_status',
        'employee_count', 'annual_budget',
        'focus_areas', 'custom_criteria', 'documents',
        'schedule_enabled', 'schedule_interval_hours',  # ADD
    ],
    'groups': {
        ...
        'Schedule': ['schedule_enabled', 'schedule_interval_hours'],  # ADD
    },
}
```

### Scheduler wiring in main.py

```python
# Source: FastAPI docs + verified app.router.on_startup.append() works in FastAPI 0.135.1
# In apps/veille/main.py, after the `app = create_app(...)` block:

async def _scheduler_loop():
    """Background asyncio loop for scheduled automated runs."""
    CHECK_INTERVAL = 900  # 15 minutes

    await asyncio.sleep(30)  # Wait for startup to complete

    while True:
        try:
            # [see Pattern 3 above for full implementation]
            pass
        except Exception as e:
            logger.error(f"Scheduler loop error: {e}")
        await asyncio.sleep(CHECK_INTERVAL)


async def _start_scheduler():
    asyncio.create_task(_scheduler_loop())


app.router.on_startup.append(_start_scheduler)
```

### ntx-run-report component skeleton

```javascript
// Source: pattern mirrors apps/veille/static/components/ntx-grant-analyze.js
// New file: apps/veille/static/components/ntx-run-report.js

import { config } from '../config.js';

class NTXRunReport extends HTMLElement {
    #runId = null;
    #els;

    static get observedAttributes() { return ['run-id']; }

    attributeChangedCallback(name, _, newVal) {
        if (name === 'run-id' && newVal !== this.#runId) {
            this.#runId = newVal;
            if (this.shadowRoot) this.#loadReport();
        }
    }

    connectedCallback() {
        this.attachShadow({ mode: 'open' });
        this.shadowRoot.innerHTML = `
            <style>${NTXRunReport.styles}</style>
            <div class="panel">
                <div class="panel-header">
                    <div class="header-left">
                        <button class="back-btn" id="back-btn">← Back to Runs</button>
                        <h2 id="title">Report</h2>
                    </div>
                </div>
                <div class="report-body" id="report-body">
                    <div class="loading">Loading...</div>
                </div>
            </div>
        `;
        this.#els = {
            title:      this.shadowRoot.getElementById('title'),
            reportBody: this.shadowRoot.getElementById('report-body'),
            backBtn:    this.shadowRoot.getElementById('back-btn'),
        };
        this.#els.backBtn.addEventListener('click', () => {
            window.location.hash = 'runs';
        });
        if (this.#runId) this.#loadReport();
    }

    async #loadReport() {
        const token = localStorage.getItem('jwtToken');
        if (!token || !this.#runId) return;
        try {
            const resp = await fetch(
                `${config.API_URL}/runs/report?run_id=${this.#runId}`,
                { headers: { 'x-access-token': token } }
            );
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            this.#els.title.textContent = `Report: Run #${this.#runId}`;
            this.#renderReport(data);
        } catch (err) {
            this.#els.reportBody.innerHTML =
                `<div class="error">Failed to load report: ${this.#esc(err.message)}</div>`;
        }
    }

    #renderReport(data) {
        const { admissible = [], partially_admissible = [],
                non_admissible = [], new: pending = [], counts = {} } = data;

        const renderSection = (title, grants, cls) => {
            if (!grants.length) return '';
            return `
                <div class="section section-${cls}">
                    <h3>${this.#esc(title)} <span class="badge">${grants.length}</span></h3>
                    <div class="grant-list">
                        ${grants.map(g => this.#renderGrantRow(g)).join('')}
                    </div>
                </div>
            `;
        };

        this.#els.reportBody.innerHTML = `
            <div class="summary-bar">
                <span class="summary-item admissible">${counts.admissible || 0} Admissible</span>
                <span class="summary-item partial">${counts.partially_admissible || 0} Partial</span>
                <span class="summary-item inadmissible">${counts.non_admissible || 0} Non-admissible</span>
                <span class="summary-item pending">${counts.new || 0} Pending</span>
            </div>
            ${renderSection('Admissible', admissible, 'admissible')}
            ${renderSection('Partially Admissible', partially_admissible, 'partial')}
            ${renderSection('Non-Admissible', non_admissible, 'inadmissible')}
            ${renderSection('Not Yet Analyzed', pending, 'pending')}
        `;
    }

    #renderGrantRow(g) {
        const score = g.admissibility_score != null
            ? `${Math.round(g.admissibility_score * 100)}%` : '—';
        const reasoning = g.admissibility_reasoning || '';
        const reasoningHtml = (typeof marked !== 'undefined' && marked.parse)
            ? marked.parse(reasoning)
            : this.#esc(reasoning);
        return `
            <div class="grant-row">
                <div class="grant-header">
                    <span class="grant-title">${this.#esc(g.title || '—')}</span>
                    <span class="grant-score">${score}</span>
                    ${g.url ? `<a class="grant-link" href="${this.#esc(g.url)}" target="_blank">View Grant</a>` : ''}
                    <a class="analyze-link" href="#analyze/${g.id}">Re-analyze</a>
                </div>
                <div class="grant-funder">${this.#esc(g.funder || '—')}</div>
                ${reasoning ? `<div class="grant-reasoning">${reasoningHtml}</div>` : ''}
            </div>
        `;
    }

    #esc(t) {
        const d = document.createElement('div');
        d.textContent = String(t);
        return d.innerHTML;
    }

    static styles = `/* ... dark-theme styles following ntx-grant-analyze.js pattern ... */`;
}

customElements.define('ntx-run-report', NTXRunReport);
export { NTXRunReport };
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| External scheduler (cron, Celery) | `asyncio.create_task()` in startup hook | No external deps; all scheduling is in-process |
| `app.on_event('startup')` | `app.router.on_startup.append()` | No deprecation warning in FastAPI 0.135+ |
| Separate Report model + DB table | Report computed on demand from existing grants table | No cache staleness; no extra migration |
| APScheduler (mentioned in earlier research) | Pure asyncio loop | Available via pip but unnecessary; stdlib is sufficient |

**Deprecated/outdated:**
- `@app.on_event('startup')`: Deprecated in FastAPI 0.95+. Use `app.router.on_startup.append()`.
- APScheduler: Mentioned in earlier planning docs as the recommendation, but for a single background loop, pure asyncio is preferable (no extra dependency, no thread pool, simpler code).

---

## Open Questions

1. **`@classmethod` + `@expose_route` exact decorator order**
   - What we know: N3TX detects instance vs class method by checking `'self' in sig.parameters`. If the exposed function lacks `self`, it's registered as a class-level route.
   - What's unclear: Whether `@classmethod` works with `@expose_route` in the correct order without runtime issues.
   - Recommendation: Test at plan execution. Fallback: use a plain `@staticmethod` (or just a regular function with `cls` named differently) to avoid the descriptor issue. The critical thing is that `self` is NOT in the signature.

2. **`execute()` async generator behavior when called from scheduler**
   - What we know: `execute()` is decorated with `@expose_route(stream=True)` which makes it an async generator yielding SSE chunks.
   - What's unclear: Whether iterating the generator from Python (not from an HTTP SSE endpoint) works correctly — the chunks are just yielded into a loop that discards them.
   - Recommendation: Test `async for _ in run_instance.execute(): pass` pattern. This should work because `execute()` is a standard async generator; the `@expose_route(stream=True)` decorator adds route metadata but doesn't change the generator behavior.

3. **Grant list sort order without ORDER BY in sql_filter**
   - What we know: `StorableMixin.list()` does not support `ORDER BY`. The report sorts grants by `admissibility_score` in Python.
   - What's unclear: Whether the default SQLite row order (insertion order = run order) is good enough as a secondary sort.
   - Recommendation: Sort admissible/partial by score descending in Python (already in Pattern 1 code). This is sufficient for the report view.

---

## Sources

### Primary (HIGH confidence — verified from source code)

- `apps/veille/models/run.py` — Run model, execute() pattern, streaming method structure
- `apps/veille/models/grant.py` — Grant fields (run_id, status, admissibility_score, admissibility_reasoning)
- `apps/veille/models/organization.py` — Organization model structure for schedule fields
- `apps/veille/main.py` — App bootstrap pattern, route insertion approach
- `apps/veille/static/components/ntx-grant-analyze.js` — Component pattern to mirror for ntx-run-report
- `apps/veille/static/components/ntx-run-panel.js` — Run panel to extend with history section
- `apps/veille/static/index.html` — handleRoute() hide-all-then-show pattern
- `packages/n3tx-core/src/n3tx_core/models/storable_mixin.py` — `list(sql_filter=...)` API (lines 92-103)
- `packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py` — sql_filter WHERE clause implementation (lines 182-186)
- `packages/n3tx-actors/src/n3tx_actors/api/network_api.py` — class vs instance method routing (lines 391-396)
- `packages/n3tx-core/src/n3tx_core/api/backend.py` — FastAPIBackend, no lifespan registration
- Python3 runtime check: `app.router.on_startup` is a list; `append()` works, no deprecation warnings
- Python3 runtime check: `app.on_event('startup')` shows deprecation warning in FastAPI 0.135.1

### Secondary (MEDIUM confidence)

- `apps/veille/.planning/research/FEATURES.md` — APScheduler vs asyncio analysis, scheduling complexity assessment
- `apps/veille/.planning/research/PITFALLS.md` — Auth bypass pitfall for scheduled runs (Pitfall 4), interceptor scope (Pitfall 13)
- `apps/veille/.planning/research/SUMMARY.md` — Stack decisions: APScheduler mentioned but not installed

---

## Metadata

**Confidence breakdown:**
- Run.report() classmethod pattern: HIGH — sql_filter verified in sqlite_storage.py; class vs instance method routing verified in network_api.py
- Organization schedule fields: HIGH — same pattern as all other Organization fields; migration is automatic
- asyncio scheduler loop: HIGH — verified app.router.on_startup.append() works in FastAPI 0.135.1; asyncio.create_task pattern is stdlib
- ntx-run-report component: HIGH — direct mirror of ntx-grant-analyze.js with established pattern
- @classmethod + @expose_route decorator order: MEDIUM — needs runtime verification

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (stable N3TX 0.10; no external library risk)
