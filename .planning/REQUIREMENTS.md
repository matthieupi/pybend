# Grant-Watch v1 Requirements

## v1 Requirements

### Framework — N3TX Agentic Infrastructure

These requirements improve the N3TX framework to support agentic pipeline applications generically. They are not grant-watch specific.

- [ ] **FW-01**: SchedulerActor with DB-stored cron expressions, editable via API
- [ ] **FW-02**: Lifecycle event pub/sub — after_create, after_update, after_delete publish TX to subscriber actors
- [ ] **FW-03**: AgentRun model — execution history: agent_id, task, result, usage (tokens/cost), status, timestamps
- [ ] **FW-04**: AgentStep model — tool call log: run_id, tool_name, args, result, duration per step
- [ ] **FW-05**: FileReader actor — read files from a configured directory path (env var), return contents
- [ ] **FW-06**: Configurable concurrency for agent tool calls (max parallel tool executions)
- [ ] **FW-07**: Error hardening — graceful LLM failure handling, tool call timeouts, proper TX error propagation
- [ ] **FW-08**: Real LLM provider integration — Ollama default, Anthropic/OpenAI configurable per agent
- [ ] **FW-09**: Run queue / job status tracking in SchedulerActor (pending, running, completed, failed)
- [ ] **FW-10**: Agent run observability in schema — run history accessible via standard CRUD API

### App Architecture — Grant-Watch Data Model & Pipeline

These requirements define the data model and actor topology specific to the grant-watch application, built on the framework features above.

- [ ] **ARCH-01**: Grant model enhancement — status lifecycle (discovered → eligible / partly_eligible / not_eligible)
- [ ] **ARCH-02**: Criterion model — normalized eligibility criteria text, Literal category (financial, geographic, org_type, etc.), org_eligible flag (bool/null)
- [ ] **ARCH-03**: GrantCriterion join model — grant_id + criterion_id + score (0.0-1.0) + status (auto/manual) + reasoning text
- [ ] **ARCH-04**: Report model — scan run summary: run_date, grants_found, grants_eligible, summary text
- [ ] **ARCH-05**: Scanner Agent instance — AgentActor row with scraping prompt, tools=[sources, grants, web_tools], constraints
- [ ] **ARCH-06**: Analyzer Agent instance — AgentActor row with eligibility prompt, tools=[grants, criteria, file_reader], constraints
- [ ] **ARCH-07**: Lifecycle wiring — Grant.after_create → Analyzer agent receives TX, evaluates eligibility
- [ ] **ARCH-08**: Lifecycle wiring — Criterion.after_update → re-evaluate all affected grants via GrantCriterion join
- [ ] **ARCH-09**: Criteria learning loop — auto-classify previously-seen criteria with confirmed org_eligible status, skip LLM call

### Scanning Features

- [ ] **SCAN-01**: Source scraping via httpx — fetch source URLs, extract grant links, skip-and-continue on failure
- [ ] **SCAN-02**: Pagination handling — agent adapts to single-page and paginated source structures
- [ ] **SCAN-03**: URL deduplication — check each discovered grant URL against existing Grant records in DB
- [ ] **SCAN-04**: Configurable concurrency — max parallel sources setting on scanner agent constraints

### Eligibility Features

- [ ] **ELIG-01**: Analyzer reads org documentation from ORG_DOCS_PATH directory (markdown files)
- [ ] **ELIG-02**: Criteria extraction — analyzer parses grant requirements, normalizes into Criterion records with category
- [ ] **ELIG-03**: Per-criterion scoring — 0.0-1.0 match score against org docs with reasoning text
- [ ] **ELIG-04**: Human override — user can change criterion org_eligible flag (eligible <-> ineligible)
- [ ] **ELIG-05**: Automatic re-evaluation — Criterion.after_update lifecycle event triggers re-scoring of affected grants

### Frontend

- [ ] **UI-01**: All models browsable — ntx-list/ntx-item for Grants, Sources, Agents, Reports, Criteria, GrantCriterion
- [ ] **UI-02**: Agent Run button — manual trigger on agent detail view (POST /agents/{id}/run)
- [ ] **UI-03**: Run status + history — status indicator on agent, list of past AgentRun records with results
- [ ] **UI-04**: Eligibility dashboard — grant list with color-coded eligibility status, expandable criterion breakdown per grant

### Testing

- [ ] **TEST-01**: Mock HTTP unit tests — fixture HTML pages for scanner agent, deterministic scraping tests
- [ ] **TEST-02**: Local test server — serve fake grant pages for integration tests (real HTTP, controlled content)
- [ ] **TEST-03**: HTTP endpoint integration tests — full request lifecycle via test client (POST /agents/{id}/run with auth)
- [ ] **TEST-04**: Pipeline E2E test — Scheduler -> Scanner -> Analyzer -> Report, full chain with mock LLM

## v2 Requirements (Deferred)

- Email/webhook notifications when eligible grants found
- Multi-tenant support (org_id on all models, tenant-aware queries)
- PDF document parsing (PDFTools actor)
- Role-based access control (admin, reviewer, viewer)
- Playwright headless browser for JS-rendered source pages
- Remote org doc sources (GoogleDriveActor, TeamsActor, ObsidianActor)
- Live streaming of agent tool calls to frontend (SSE/WebSocket)
- Agent memory / conversation history persistence across runs
- Multi-agent coordination (agents as tools for other agents)

## Out of Scope

- Email notifications — v2 (architecture supports adding NotificationActor)
- Multi-tenant — v2 (add org_id, tenant-aware queries)
- PDF parsing — v2 (add PDFTools actor)
- User roles beyond basic auth — v2 (N3TX RBAC primitives exist)
- Playwright/headless browser — v2 (swap httpx in WebTools)
- Remote org doc sources — v2 (replace FileReader with remote actors)

## Traceability

| REQ-ID | Phase | Status |
|--------|-------|--------|
| FW-01 | Phase 1: Framework Agentic Infrastructure | Pending |
| FW-02 | Phase 1: Framework Agentic Infrastructure | Pending |
| FW-03 | Phase 1: Framework Agentic Infrastructure | Pending |
| FW-04 | Phase 1: Framework Agentic Infrastructure | Pending |
| FW-05 | Phase 1: Framework Agentic Infrastructure | Pending |
| FW-06 | Phase 1: Framework Agentic Infrastructure | Pending |
| FW-07 | Phase 1: Framework Agentic Infrastructure | Pending |
| FW-08 | Phase 1: Framework Agentic Infrastructure | Pending |
| FW-09 | Phase 1: Framework Agentic Infrastructure | Pending |
| FW-10 | Phase 1: Framework Agentic Infrastructure | Pending |
| ARCH-01 | Phase 2: App Architecture | Pending |
| ARCH-02 | Phase 2: App Architecture | Pending |
| ARCH-03 | Phase 2: App Architecture | Pending |
| ARCH-04 | Phase 2: App Architecture | Pending |
| ARCH-05 | Phase 2: App Architecture | Pending |
| ARCH-06 | Phase 2: App Architecture | Pending |
| ARCH-07 | Phase 2: App Architecture | Pending |
| ARCH-08 | Phase 2: App Architecture | Pending |
| ARCH-09 | Phase 2: App Architecture | Pending |
| SCAN-01 | Phase 3: Scanning Features | Pending |
| SCAN-02 | Phase 3: Scanning Features | Pending |
| SCAN-03 | Phase 3: Scanning Features | Pending |
| SCAN-04 | Phase 3: Scanning Features | Pending |
| ELIG-01 | Phase 4: Eligibility Features | Pending |
| ELIG-02 | Phase 4: Eligibility Features | Pending |
| ELIG-03 | Phase 4: Eligibility Features | Pending |
| ELIG-04 | Phase 4: Eligibility Features | Pending |
| ELIG-05 | Phase 4: Eligibility Features | Pending |
| UI-01 | Phase 5: Frontend | Pending |
| UI-02 | Phase 5: Frontend | Pending |
| UI-03 | Phase 5: Frontend | Pending |
| UI-04 | Phase 5: Frontend | Pending |
| TEST-01 | Phase 6: Testing & Hardening | Pending |
| TEST-02 | Phase 6: Testing & Hardening | Pending |
| TEST-03 | Phase 6: Testing & Hardening | Pending |
| TEST-04 | Phase 6: Testing & Hardening | Pending |
