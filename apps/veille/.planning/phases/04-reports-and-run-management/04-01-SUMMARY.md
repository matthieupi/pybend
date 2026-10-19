---
phase: "04"
plan: "01"
name: "Report endpoint, schedule fields, and background scheduler"
subsystem: backend
tags: [report, scheduler, organization, run, asyncio, fastapi]

dependency-graph:
  requires:
    - "03-02: Grant.analyze() and admissibility pipeline"
    - "01-01: Organization model"
    - "01-02: Run model"
  provides:
    - "GET /runs/report?run_id=N returns grouped grant data"
    - "Organization.schedule_enabled and schedule_interval_hours fields"
    - "Background asyncio scheduler at app startup"
  affects:
    - "04-02: Frontend report panel uses Run.report() endpoint"

tech-stack:
  added: []
  patterns:
    - "Class-level @expose_route (no self) for collection-scoped GET endpoints"
    - "app.router.on_startup.append() for non-deprecated FastAPI startup hooks"
    - "asyncio.create_task() inside async startup function"

key-files:
  created: []
  modified:
    - apps/veille/models/run.py
    - apps/veille/models/organization.py
    - apps/veille/main.py
    - packages/n3tx-actors/src/n3tx_actors/api/network_api.py

decisions:
  - "Plain function (no self/cls) for report() registers as GET /runs/report, not instance-scoped"
  - "Scheduler uses app.router.on_startup.append(), not deprecated app.on_event('startup')"
  - "asyncio.create_task() inside _start_scheduler() async fn, never at module level"
  - "Query params merged into body payload in _parse_method_args so GET ?run_id= works"

metrics:
  duration: "5 minutes"
  completed: "2026-03-20"
  tasks-completed: 2
  tasks-total: 2
---

# Phase 4 Plan 01: Report Endpoint, Schedule Fields, and Background Scheduler Summary

**One-liner:** Report endpoint groups grants by admissibility bucket; Organization gains schedule fields; asyncio scheduler auto-triggers runs.

## What Was Built

### Task 1: Report endpoint (Run.report) and Organization schedule fields

**`apps/veille/models/run.py`**

Added `Run.report()` as a class-level `@expose_route` (no `self` parameter) that registers as `GET /runs/report`. The method:
- Accepts `run_id: int` query parameter
- Fetches run metadata via `Run.get(run_id)` for the `run` key
- Queries grants via `Grant.list(sql_filter=('run_id = ?', [run_id]), limit=1000)`
- Groups grants into four buckets: `admissible`, `partially_admissible`, `non_admissible`, `new`
- Sorts scored buckets (`admissible`, `partially_admissible`) by `admissibility_score` descending
- Returns JSON with `run_id`, `run`, all four buckets, and `counts` dict with per-bucket and total counts

**`apps/veille/models/organization.py`**

Added two new fields:
- `schedule_enabled: bool = Field(default=False)`
- `schedule_interval_hours: int = Field(default=168)` (weekly)

Added `Schedule` UI group and appended both fields to `field_order`.

### Task 2: Background scheduler loop (`main.py`)

Added:
- `_scheduler_loop()`: async function running every 15 minutes that:
  1. Reads `Organization.schedule_enabled` and `schedule_interval_hours`
  2. Skips if no org configured or scheduling disabled
  3. Skips if any run is already `running` (no overlapping runs)
  4. Computes elapsed time since last completed full run
  5. Creates and executes a new `Run` if interval has elapsed
- `_start_scheduler()`: async startup hook registered via `app.router.on_startup.append()`
- Logger `veille.scheduler` for scheduler events
- Imports: `asyncio`, `datetime`, `timezone` added at module level

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed GET query param handling in network_api._parse_method_args**

- **Found during:** Task 1 verification
- **Issue:** `_parse_method_args` only read from request body (`data.get(name)`). For GET requests, the body is empty (`{}`), so `run_id` from `?run_id=N` was never injected into the payload. The endpoint returned a 500 with "missing required positional argument: run_id".
- **Fix:** Merged `request.query_params` as a fallback dict before reading params; body values take precedence over query params.
- **Files modified:** `packages/n3tx-actors/src/n3tx_actors/api/network_api.py`
- **Commit:** 1e810f7

## Verification Results

All success criteria met:

1. `GET /runs/report?run_id=999` returns `{"run_id": 999, "run": {}, "admissible": [], "partially_admissible": [], "non_admissible": [], "new": [], "counts": {...}}`
2. Organization schema has `schedule_enabled` (default: `false`) and `schedule_interval_hours` (default: `168`)
3. Organization UI has `Schedule` group containing both fields
4. `_scheduler_loop` and `_start_scheduler` present in `main.py`; registered via `app.router.on_startup.append()`
5. Server starts cleanly (no import or syntax errors)
6. No circular imports between `run.py` and `grant.py` (lazy import inside function)

## Next Phase Readiness

Phase 4 Plan 02 (frontend report panel) can proceed. The `GET /runs/report?run_id=N` endpoint provides the grouped grant data needed for the report view.
