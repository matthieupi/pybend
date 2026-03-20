# Veille -- Roadmap

## Overview

- Phases: 4
- Requirements: 22 mapped
- Coverage: 100%
- Depth: Quick (compressed from 6 research phases into 4 delivery boundaries)

Veille delivers value in a tight sequence: stand up the data models and UI, wire the scraping agent to populate grants, add admissibility analysis to evaluate them, then polish with reports and scheduling. The core value (scraping + extraction + admissibility) lands across Phases 2 and 3. Phase 1 is pure N3TX scaffolding. Phase 4 is output and automation.

---

## Phase 1: Foundation and Data Models -- COMPLETE

**Goal:** User can log in, configure their organization profile, and manage scraping sources through a working web interface.

**Dependencies:** None (first phase)

**Requirements:** AUTH-01, AUTH-02, ORG-01, ORG-02, ORG-03, SRC-01, SRC-02, SRC-03

**Plans:** 2 plans

Plans:
- [x] 01-01-PLAN.md -- App skeleton, models (User, Organization, Source, Grant), config, seed script
- [x] 01-02-PLAN.md -- Frontend (login, register, main app), document upload routes

**Verification:** Passed (13/13 must-haves verified)

**Success Criteria:**
1. User can log in with email/password and access the application (unauthenticated users see nothing)
2. User can create and edit an organization profile with mission, legal status, location, and custom eligibility criteria
3. User can upload strategic documents (PDF/text) that are stored and accessible for agent context
4. User can add, edit, and delete scraping sources with URL, name, description, and per-source scraping notes
5. Sources display whether they are human-added or agent-discovered

---

## Phase 2: Scraping and Grant Extraction -- COMPLETE

**Goal:** User can trigger a scraping run and watch the agent discover, extract, and store grant opportunities from all configured sources in real time.

**Dependencies:** Phase 1 (sources and org profile must exist)

**Requirements:** GRANT-01, GRANT-02, GRANT-03, GRANT-04, SRC-04, RUN-01, RUN-03

**Plans:** 2 plans

Plans:
- [x] 02-01-PLAN.md -- Backend: Run model, WebTools actor, Grant dedup field, main.py wiring
- [x] 02-02-PLAN.md -- Frontend: ntx-run-panel streaming component, index.html Runs navigation

**Verification:** Passed (14/14 must-haves verified)

**Success Criteria:**
1. User can trigger a full scraping run across all configured sources and see streaming progress as the agent works
2. Grants appear in the database with full extracted details (amount, deadlines, criteria, required documents, application process)
3. The same grant discovered from multiple sources is automatically deduplicated into a single record
4. User can run the agent on a specific ad-hoc URL and see extracted grants from that page
5. The agent discovers and adds new sources during runs, flagged as agent-discovered

---

## Phase 3: Admissibility Analysis

**Goal:** Every grant is automatically evaluated against the organization profile and classified with detailed justification.

**Dependencies:** Phase 2 (grants must exist in the system), Phase 1 (org profile provides evaluation criteria)

**Requirements:** ADM-01, ADM-02, ADM-03, ADM-04

**Success Criteria:**
1. After a scraping run, each grant is automatically scored by matching its criteria against the organization profile fields
2. The agent provides holistic LLM reasoning about organization-grant fit with a written justification per grant
3. Each grant is labeled admissible, partially admissible, or non-admissible based on the analysis
4. User can re-run admissibility analysis on a specific grant (e.g., after updating the organization profile) and see updated results

---

## Phase 4: Reports and Run Management

**Goal:** User can review structured reports from each run, browse run history, and schedule automated runs.

**Dependencies:** Phase 3 (admissibility results needed for meaningful reports)

**Requirements:** RPT-01, RUN-02, RUN-04

**Success Criteria:**
1. Each completed run generates an in-app report showing admissible, partially admissible, and non-admissible grants with justifications
2. User can browse full run history and compare results across runs (new grants found, status changes)
3. User can configure scheduled automated runs at a chosen frequency (e.g., weekly) that execute without manual intervention

---

## Coverage Map

| REQ-ID | Requirement | Phase |
|--------|-------------|-------|
| AUTH-01 | Login with email/password | 1 |
| AUTH-02 | Register account | 1 |
| ORG-01 | Organization profile (mission, legal status, location) | 1 |
| ORG-02 | Custom eligibility criteria | 1 |
| ORG-03 | Upload strategic documents | 1 |
| SRC-01 | Source CRUD (add, edit, remove, list) | 1 |
| SRC-02 | Source human-added vs agent-discovered flag | 1 |
| SRC-03 | Per-source scraping context/notes | 1 |
| GRANT-01 | Agentic scraping of sources | 2 |
| GRANT-02 | Full grant detail extraction | 2 |
| GRANT-03 | Grant deduplication | 2 |
| GRANT-04 | Ad-hoc URL scanning | 2 |
| SRC-04 | Agent auto-discovery of new sources | 2 |
| RUN-01 | Trigger scraping run across all sources | 2 |
| RUN-03 | Real-time streaming progress | 2 |
| ADM-01 | Criteria matching against org profile | 3 |
| ADM-02 | LLM reasoning with detailed justification | 3 |
| ADM-03 | Admissible / partially / non-admissible classification | 3 |
| ADM-04 | Re-run analysis on specific grant | 3 |
| RPT-01 | In-app report view per run | 4 |
| RUN-02 | Full run history with comparison | 4 |
| RUN-04 | Scheduled automated runs | 4 |

**Mapped: 22/22**

---
*Last updated: 2026-03-20 after Phase 2 completion*
