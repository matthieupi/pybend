# Grant-Watch Project State

## Project Reference

**Core Value:** Automated grant discovery with intelligent eligibility scoring -- a scheduled pipeline that finds new grants, evaluates them against org capabilities, and presents scored results without human intervention.

**Current Focus:** Roadmap created, awaiting approval to begin Phase 1.

## Current Position

**Phase:** -- (pre-execution)
**Plan:** --
**Status:** Roadmap drafted
**Progress:** [..........] 0/36 requirements

## Phase Summary

| Phase | Name | Reqs | Status |
|-------|------|------|--------|
| 1 | Framework Agentic Infrastructure | 10 | Not Started |
| 2 | App Architecture | 9 | Not Started |
| 3 | Scanning Features | 4 | Not Started |
| 4 | Eligibility Features | 5 | Not Started |
| 5 | Frontend | 4 | Not Started |
| 6 | Testing & Hardening | 4 | Not Started |

## Performance Metrics

| Metric | Value |
|--------|-------|
| Requirements completed | 0/36 |
| Phases completed | 0/6 |
| Plans completed | 0/? |
| Tests passing | 63+ (existing baseline) |

## Accumulated Context

### Key Decisions
- Phase 1 is purely framework (PyBend core), no app-specific code
- Phase 2 is purely data model and actor topology, no feature logic
- Feature phases (3-6) build on the framework + architecture foundation
- Existing 63+ tests form the regression baseline

### Known Risks
- SQLite writer contention under concurrent agent runs (CONCERNS.md)
- WebTools.scrape has no SSRF protection (validator exists but not wired)
- Agent tool calls have no action-level scoping (full CRUD access)
- Single-process actor system with no task queue (fire-and-forget lifecycle events)
- pydantic-ai is pre-1.0, API surface may change

### Blockers
None currently.

### TODOs
- Await roadmap approval
- Plan Phase 1 after approval

## Session Continuity

**Last action:** Roadmap creation
**Next action:** User reviews roadmap, then /gsd:plan-phase 1
**Context to preserve:** The strict phase ordering constraint -- framework first, architecture second, features third. Never mix framework work into app phases.

---

*Initialized: 2026-03-04*
