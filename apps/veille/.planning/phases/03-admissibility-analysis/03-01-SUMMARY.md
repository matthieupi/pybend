# Phase 3 Plan 01: Admissibility Analysis Backend Summary

## Status: COMPLETE

**One-liner:** Grant model becomes agent-enabled with __agent__ config (self_tools=True, tools=['organizations']), streaming POST /grants/{id}/analyze endpoint, and prompt builders; Run.execute() gains non-streaming batch analysis loop that runs after scraping completes.

## What was built

- `models/grant.py` -- Added `__agent__` class variable (`self_tools=True, neighbors=False, tools=['organizations']`), AgentMixin injected (agentic/agentic_stream available on instances). Added `analyze()` streaming instance method at `POST /grants/{id}/analyze` that pre-checks org profile, sets status='analyzing', streams agentic_stream(), resets status='new' on error. Added `_build_analysis_task()` with grant details + classification steps and `_build_analysis_prompt()` with strict classification/scoring rules.
- `models/run.py` -- Added batch admissibility analysis loop inside `execute()` after scraping stream completes and before Run.update(status='complete'). Loop filters for grants with run_id matching current run and status='new', checks org profile exists, calls `grant_instance.agentic()` (non-streaming) for each grant with the Grant prompt builders. Errors on individual grants are logged and skipped; the batch continues.

## Verification Results

- `Grant.__agent__` = `{'self_tools': True, 'neighbors': False, 'tools': ['organizations']}` -- PASS
- `hasattr(Grant, 'analyze')` = `True` -- PASS
- `hasattr(Grant, '_build_analysis_task')` = `True` -- PASS
- `hasattr(Grant, '_build_analysis_prompt')` = `True` -- PASS
- `hasattr(Grant, 'agentic')` = `True` (AgentMixin injected) -- PASS
- `hasattr(Grant, 'agentic_stream')` = `True` (AgentMixin injected) -- PASS
- `Run.execute` source contains `_build_analysis_task` -- PASS
- `Run.execute` source contains `_build_analysis_prompt` -- PASS
- `Run.execute` source contains `grant_instance` and `agentic(` -- PASS
- `Run.execute` source contains `Organization` (org profile check) -- PASS
- `Run.execute` source still contains `agentic_stream` (scraping intact) -- PASS
- `Run.execute` source still contains `_build_task` (scraping intact) -- PASS
- `Run.execute` source still contains `_build_prompt` (scraping intact) -- PASS
- Both files import cleanly with `from models import Grant, Run` -- PASS

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| `analyze()` pre-checks org profile before streaming | Avoids starting the agent only to have it fail on missing org; yields a clear error text chunk instead |
| status='analyzing' set before agentic_stream() | Shows progress in UI; reset to 'new' on error so the grant can be retried |
| Batch loop uses `_run_grants_data` variable | Extracted before the counting try/except to make it available for the batch filter without a second `dir()` check |
| Non-streaming `agentic()` for batch | SSE stream to client is already done after scraping; mixing analysis events into the scraping stream would confuse the frontend run panel |
| Org profile pre-check before batch | Prevents the agent from being invoked 20+ times only to fail on the first tool call in each case |
| Graceful per-grant error handling | One bad grant should not abort analysis of the rest; logged as WARNING and continue |

## Deviations from Plan

### Minor implementation difference

**Found during:** Task 2 implementation

**Issue:** The plan suggested using `'data' in dir()` to guard against `data` not being defined if the counting block fails. This is fragile — `dir()` checks names in scope but can produce unexpected results.

**Fix:** Renamed the variable to `_run_grants_data` and initialized it to `[]` before the try/except block. This guarantees it is always defined when the batch analysis filter runs, without the `dir()` guard.

**Files modified:** `apps/veille/models/run.py`

**Commit:** 5bab6d7

This is a correctness improvement, not a functional change.

## Commits

| Hash | Description |
|------|-------------|
| f22b6bf | feat(03-01): Add __agent__ and analyze() streaming endpoint to Grant model |
| 5bab6d7 | feat(03-01): Add batch admissibility analysis loop to Run.execute() |

## Duration

Start: 2026-03-20T18:03:02Z
End: 2026-03-20T18:04:41Z
Duration: ~2 minutes
