# Phase 2 Plan 01: Scraping Backend Models Summary

## Status: COMPLETE

**One-liner:** WebTools non-storable scraping actor (httpx + Playwright + stdlib HTML parsing) and Run storable ActorModel with `__agent__=True` and streaming `execute()` method using AgentMixin's `agentic_stream()`.

## What was built

- `models/web_tools.py` -- Non-storable ActorModel with three tools: `scrape()` (httpx, HTML-to-text via stdlib html.parser), `scrape_js()` (Playwright headless Chromium), `check_duplicate()` (URL/source_url/source_urls match check against existing grants). No bs4 dependency.
- `models/grant.py` -- Added `source_urls: list` field for dedup tracking (hidden from UI via `display: False`; SQLite auto-serializes to JSON TEXT). Existing `source_url` field kept for backward compat.
- `models/run.py` -- Storable ActorModel (pending/running/complete/failed lifecycle), `__agent__` config with explicit `tools=['web_tools', 'grants', 'sources']`, `execute()` streaming SSE endpoint with TX-aligned event vocabulary (TextChunk, ToolCallEvent, ToolResultEvent, ThinkingChunk, DoneChunk), `_build_task()` for full/adhoc run task assembly, `_build_prompt()` with organization context injection.
- `models/__init__.py` -- Added Run and WebTools exports.
- `main.py` -- Added Run and WebTools to create_app() models list. App now boots with 54 routes including `/runs/{id}/execute` streaming endpoint.

## Verification Results

- `WebTools.__tablename__` = `'web_tools'`, `__storable__` = `False` -- PASS
- `Grant.source_urls` defaults to `[]` with type `list` -- PASS
- `Run.__agent__` = `{'self_tools': False, 'neighbors': False, 'tools': [...]}` -- PASS
- `hasattr(Run, 'agentic_stream')` = `True` (AgentMixin injected) -- PASS
- `hasattr(Run, 'execute')` = `True` -- PASS
- All 6 models import cleanly from `models` package -- PASS
- App creates with 54 routes (Run + WebTools registered in Matrix) -- PASS

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| stdlib html.parser instead of bs4 | bs4 is not installed; html.parser achieves same result for text extraction |
| `__agent__` uses explicit `tools` list | `self_tools=False` (Run doesn't need CRUD on itself), `neighbors=False` (no ListRef fields), explicit tool actors named by `__tablename__` |
| Agent creates grants via tool calls | Tool-use pattern (grants_create) is more natural than structured output; agent extracts and creates grants as it scrapes |
| httpx imported lazily inside method | Avoids import-time dependency; consistent with grants example pattern |
| Playwright imported lazily inside method | Optional dependency; only loaded if scrape_js() is actually called |

## Deviations from Plan

None - plan executed exactly as written.

## Commits

| Hash | Description |
|------|-------------|
| c6e5064 | feat(02-01): Create WebTools actor and update Grant model with source_urls |
| 7c649df | feat(02-01): Create Run model with streaming agentic execute() method |
| 76ec141 | feat(02-01): Wire Run and WebTools into models/__init__.py and main.py |

## Duration

Start: 2026-03-20T17:28:31Z
End: 2026-03-20T17:31:24Z
Duration: ~3 minutes
