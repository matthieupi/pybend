# Veille -- Project State

## Project Reference

**Core value:** Reliably discover new grants from configured sources, extract their details, and evaluate admissibility against the organization profile -- with justification.

**Current focus:** Phase 1 complete and verified (13/13 must-haves). Ready for Phase 2 (Scraping & Grant Extraction).

## Current Phase

Phase 1: Foundation and Data Models -- Complete
Plan: 2 of 2 complete
Status: Phase complete
Last activity: 2026-03-20 - Completed 01-02-PLAN.md

## Phase Status

| Phase | Name | Status | Plans |
|-------|------|--------|-------|
| 1 | Foundation and Data Models | Complete | 01 complete, 02 complete |
| 2 | Scraping and Grant Extraction | Not Started | -- |
| 3 | Admissibility Analysis | Not Started | -- |
| 4 | Reports and Run Management | Not Started | -- |

## Progress

```
Phase 1 [======] Foundation and Data Models   (2/2 plans)
Phase 2 [      ] Scraping and Grant Extraction
Phase 3 [      ] Admissibility Analysis
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

### Accumulated Context

- Port 5000 may be occupied by other N3TX examples; use alternate port for testing
- BaseUser provides name, email, role, password_hash, login(), register_user() -- do not redeclare
- n3tx_agents must be imported BEFORE model imports in main.py
- python-multipart already installed in environment; aiofiles installed during phase 1 plan 2
- Upload dir: apps/veille/uploads/ (created at startup by main.py)
- Document upload routes are custom FastAPI routes inserted before static mount catch-all

### Blockers
(none)

### TODOs
(none)

---
*Last updated: 2026-03-20 after Phase 1 completion (verified 13/13 must-haves)*
