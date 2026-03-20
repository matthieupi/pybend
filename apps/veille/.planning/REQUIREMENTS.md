# Veille -- Requirements

## v1 Requirements

### Authentication & Users
- [ ] **AUTH-01**: User can log in with email and password (JWT-based)
- [ ] **AUTH-02**: User can register an account (development convenience)

### Organization Profile
- [ ] **ORG-01**: User can create and edit an organization profile with mission, legal status, and location
- [ ] **ORG-02**: User can define custom eligibility criteria (budget size, employee count, capabilities)
- [ ] **ORG-03**: User can upload strategic documents to enrich agent context

### Source Management
- [ ] **SRC-01**: User can add, edit, remove, and list scraping sources with URL, name, and description
- [ ] **SRC-02**: Sources are flagged as human-added or agent-discovered
- [ ] **SRC-03**: User can add per-source scraping context/notes to guide the agent
- [ ] **SRC-04**: Agent auto-discovers and adds new sources during runs (flagged as agent-discovered)

### Scraping & Grants
- [ ] **GRANT-01**: Agentic scraping scans each source for grant opportunities with context-aware exploration
- [ ] **GRANT-02**: Full grant detail extraction (amount, deadlines, criteria, required documents, application process)
- [ ] **GRANT-03**: Automatic deduplication of same grant found across multiple sources
- [ ] **GRANT-04**: User can run the agent on a specific ad-hoc URL on demand

### Admissibility Analysis
- [ ] **ADM-01**: Criteria matching -- extract grant criteria, match against org profile fields
- [ ] **ADM-02**: LLM reasoning -- agent reasons holistically about org-grant fit with detailed justification
- [ ] **ADM-03**: Classification -- each grant labeled admissible / partially admissible / non-admissible
- [ ] **ADM-04**: User can re-run analysis on a specific grant (e.g., after profile changes)

### Run Management
- [ ] **RUN-01**: User can trigger a scraping run across all sources
- [ ] **RUN-02**: Full run history with results, comparable across runs
- [ ] **RUN-03**: Real-time streaming progress during run execution
- [ ] **RUN-04**: Scheduled automated runs (weekly or configurable frequency)

### Reporting
- [ ] **RPT-01**: In-app report view showing admissible/partial/non-admissible breakdown per run

## v2 Requirements (Deferred)

- PDF export of reports
- Email notifications after run completion
- Past grants tracking (history of received funding)
- Role-based access (admin vs viewer)
- Grant change tracking (deadline extensions, criteria updates)
- User management CRUD

## Out of Scope

- Multi-tenant (multiple orgs per instance) -- deploy separate instances
- Public-facing pages -- admin-only
- Grant application submission -- Veille finds and evaluates, doesn't apply
- Bilingual UI -- English primary, French source scraping handled by LLM
- Real-time push notifications (WebSocket) -- in-app + streaming is sufficient

## Traceability

| REQ-ID | Phase | Status |
|--------|-------|--------|
| AUTH-01 | Phase 1 | Complete |
| AUTH-02 | Phase 1 | Complete |
| ORG-01 | Phase 1 | Complete |
| ORG-02 | Phase 1 | Complete |
| ORG-03 | Phase 1 | Complete |
| SRC-01 | Phase 1 | Complete |
| SRC-02 | Phase 1 | Complete |
| SRC-03 | Phase 1 | Complete |
| SRC-04 | Phase 2 | Complete |
| GRANT-01 | Phase 2 | Complete |
| GRANT-02 | Phase 2 | Complete |
| GRANT-03 | Phase 2 | Complete |
| GRANT-04 | Phase 2 | Complete |
| RUN-01 | Phase 2 | Complete |
| RUN-03 | Phase 2 | Complete |
| ADM-01 | Phase 3 | Complete |
| ADM-02 | Phase 3 | Complete |
| ADM-03 | Phase 3 | Complete |
| ADM-04 | Phase 3 | Complete |
| RPT-01 | Phase 4 | Pending |
| RUN-02 | Phase 4 | Pending |
| RUN-04 | Phase 4 | Pending |

---
*Last updated: 2026-03-20 after Phase 3 completion (19 requirements marked Complete)*
