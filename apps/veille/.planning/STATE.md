# Veille -- Project State

## Project Reference

**Core value:** Reliably discover new grants from configured sources, extract their details, and evaluate admissibility against the organization profile -- with justification.

**Current focus:** Phase 1 Plan 01 complete. App skeleton running with all 4 models.

## Current Phase

Phase 1: Foundation and Data Models -- In Progress
Plan: 1 of 2 complete
Status: In progress
Last activity: 2026-03-20 - Completed 01-01-PLAN.md

## Phase Status

| Phase | Name | Status | Plans |
|-------|------|--------|-------|
| 1 | Foundation and Data Models | In Progress | 01 complete, 02 pending |
| 2 | Scraping and Grant Extraction | Not Started | -- |
| 3 | Admissibility Analysis | Not Started | -- |
| 4 | Reports and Run Management | Not Started | -- |

## Progress

```
Phase 1 [=     ] Foundation and Data Models   (1/2 plans)
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

### Accumulated Context

- Port 5000 may be occupied by other N3TX examples; use alternate port for testing
- BaseUser provides name, email, role, password_hash, login(), register_user() -- do not redeclare
- n3tx_agents must be imported BEFORE model imports in main.py

### Blockers
(none)

### TODOs
(none yet)

---
*Last updated: 2026-03-20 after completing Plan 01 (App Skeleton + All Models)*
