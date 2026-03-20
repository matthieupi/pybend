# Veille -- Project State

## Project Reference

**Core value:** Reliably discover new grants from configured sources, extract their details, and evaluate admissibility against the organization profile -- with justification.

**Current focus:** Phase 3 complete. Ready for Phase 4 (Reports and Run Management).

## Current Phase

Phase 3: Admissibility Analysis -- Complete
Plan: 2 of 2 (03-01 complete, 03-02 complete)
Status: Phase complete
Last activity: 2026-03-20 - Completed 03-02-PLAN.md

## Phase Status

| Phase | Name | Status | Plans |
|-------|------|--------|-------|
| 1 | Foundation and Data Models | Complete | 01 complete, 02 complete |
| 2 | Scraping and Grant Extraction | Complete | 01 complete, 02 complete |
| 3 | Admissibility Analysis | Complete | 01 complete, 02 complete |
| 4 | Reports and Run Management | Not Started | -- |

## Progress

```
Phase 1 [======] Foundation and Data Models    (2/2 plans)
Phase 2 [======] Scraping and Grant Extraction (2/2 plans)
Phase 3 [======] Admissibility Analysis        (2/2 plans)
Phase 4 [      ] Reports and Run Management
```

## Memory

### Decisions

| Decision | Context | Date |
|----------|---------|------|
| Level 3 actor routing | All models use ActorModel, routing='actor' in create_app | 2026-03-20 |
| Plain str for URL fields | UrlField (AnyHttpUrl) too strict for agent-populated URLs | 2026-03-20 |
| ntx-item for User renderer | No custom user component; use standard ntx-item | 2026-03-20 |
| Token probe uses /sources not /Source | /sources requires AUTHENTICATED; /Source is schema endpoint (always public) | 2026-03-20 |
| Routes inserted via app.router.routes.insert(-1, route) | Inserts before static mount catch-all; app.include_router would add after catch-all | 2026-03-20 |
| stdlib html.parser instead of bs4 | bs4 not installed; html.parser achieves same result for text extraction | 2026-03-20 |
| __agent__ explicit tools list | self_tools=False, neighbors=False, tools=['web_tools','grants','sources'] by tablename | 2026-03-20 |
| Agent creates grants via tool calls | Tool-use (grants_create) more natural than structured output for agent scraping pattern | 2026-03-20 |
| Grant analyze() pre-checks org profile | Avoids starting stream agent only to fail; yields clear error text chunk instead | 2026-03-20 |
| Batch analysis non-streaming in Run.execute() | SSE stream done after scraping; mixing analysis events would confuse frontend run panel | 2026-03-20 |
| ntx-run-panel in app static/components/ | ssr='full' serves app static files; placing component in static/components/ makes it available at /components/ntx-run-panel.js alongside framework components | 2026-03-20 |
| Hash routing with handleRoute() | Simple display:none/block toggle for run-panel vs source-list; no ntx-router internals needed | 2026-03-20 |
| Hide-all-then-show in handleRoute() | Cleaner pattern; new panels don't require changes to every existing branch | 2026-03-20 |
| STREAM_END reloads grant info | Shows updated score/status/justification immediately after analysis without page refresh | 2026-03-20 |
| attributeChangedCallback drives grant load | Natural signal for attribute change; guards against double-load edge case | 2026-03-20 |

### Accumulated Context

- Port 5000 may be occupied by other N3TX examples; use alternate port for testing
- BaseUser provides name, email, role, password_hash, login(), register_user() -- do not redeclare
- n3tx_agents must be imported BEFORE model imports in main.py
- python-multipart already installed in environment; aiofiles installed during phase 1 plan 2
- Upload dir: apps/veille/uploads/ (created at startup by main.py)
- Document upload routes are custom FastAPI routes inserted before static mount catch-all
- WebTools is non-storable (no DB table, no CRUD routes) but registered in Matrix for tool discovery
- Run model uses agentic_stream() from AgentMixin injected by __agent__ = True
- App has 54 routes after Phase 2 Plan 01 (Run + WebTools added); Phase 3 adds POST /grants/{id}/analyze (streaming)
- Grant model now agent-enabled: agentic() and agentic_stream() available on instances
- Grant.analyze() sets status='analyzing' during analysis, resets to 'new' on error
- Run.execute() runs batch non-streaming analysis after scraping via grant_instance.agentic()
- httpx and playwright are imported lazily inside WebTools methods (optional at import time)
- ntx-run-panel.js lives in apps/veille/static/components/ (app-level, not framework-level)
- StreamActor import in ntx-run-panel.js: './StreamActor.js' (same merged /components/ URL space)
- marked.js already loaded in index.html as vendor script; TEXT handler checks typeof marked
- ntx-grant-analyze.js lives in apps/veille/static/components/ (app-level, same as ntx-run-panel)
- Hash route #analyze/{id} sets grant-id attribute on <ntx-grant-analyze> and shows the panel
- handleRoute() now uses hide-all-then-show pattern for cleaner multi-panel management

### Blockers

(none)

### TODOs

- Proceed to Phase 4 (Reports and Run Management)

---
*Last updated: 2026-03-20 after Phase 3 Plan 02 completion (frontend: ntx-grant-analyze StreamActor component + index.html hash routing)*
