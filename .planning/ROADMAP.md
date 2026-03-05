# Grant-Watch Roadmap

## Overview

Build a production-grade grant-watching application on N3TX's agentic architecture. The work proceeds in strict layers: first harden the N3TX framework for agentic pipelines (framework-generic), then define the grant-watch data model and actor topology (app-specific architecture), then build the scanning and eligibility features, wire the frontend, and validate the full pipeline with tests.

**Phases:** 6
**Depth:** Standard
**Total v1 Requirements:** 36

---

## Phase 1: Framework Agentic Infrastructure

**Goal:** N3TX's agentic infrastructure is production-grade -- any agentic pipeline application can be built on it without hitting framework gaps.

**Dependencies:** None (builds on existing 63+ passing tests)

**Requirements:**
- FW-01: SchedulerActor with DB-stored cron expressions, editable via API
- FW-02: Lifecycle event pub/sub -- after_create, after_update, after_delete publish TX to subscriber actors
- FW-03: AgentRun model -- execution history: agent_id, task, result, usage (tokens/cost), status, timestamps
- FW-04: AgentStep model -- tool call log: run_id, tool_name, args, result, duration per step
- FW-05: FileReader actor -- read files from a configured directory path (env var), return contents
- FW-06: Configurable concurrency for agent tool calls (max parallel tool executions)
- FW-07: Error hardening -- graceful LLM failure handling, tool call timeouts, proper TX error propagation
- FW-08: Real LLM provider integration -- Ollama default, Anthropic/OpenAI configurable per agent
- FW-09: Run queue / job status tracking in SchedulerActor (pending, running, completed, failed)
- FW-10: Agent run observability in schema -- run history accessible via standard CRUD API

**Success Criteria:**
1. A SchedulerActor can be configured with a cron expression via the API, and it fires TX messages to target actors on schedule
2. When an ActorModel record is created/updated/deleted, subscriber actors receive lifecycle TX messages automatically
3. Every agent run persists an AgentRun record with token usage, cost, status, and timestamps -- queryable via GET /agent_runs
4. Every tool call within an agent run persists an AgentStep record with tool name, arguments, result, and duration
5. An agent run that encounters an LLM failure or tool timeout records the error in AgentRun (status=failed) and does not crash the server process

---

## Phase 2: App Architecture -- Data Model & Pipeline Topology

**Goal:** The grant-watch data model and actor topology are fully defined -- all models exist, relationships are wired, and the pipeline shape is testable with mock data.

**Dependencies:** Phase 1 (lifecycle events, AgentRun/AgentStep, SchedulerActor)

**Requirements:**
- ARCH-01: Grant model enhancement -- status lifecycle (discovered -> eligible / partly_eligible / not_eligible)
- ARCH-02: Criterion model -- normalized eligibility criteria text, Literal category, org_eligible flag
- ARCH-03: GrantCriterion join model -- grant_id + criterion_id + score + status + reasoning
- ARCH-04: Report model -- scan run summary: run_date, grants_found, grants_eligible, summary text
- ARCH-05: Scanner Agent instance -- AgentActor row with scraping prompt, tools, constraints
- ARCH-06: Analyzer Agent instance -- AgentActor row with eligibility prompt, tools, constraints
- ARCH-07: Lifecycle wiring -- Grant.after_create -> Analyzer agent receives TX, evaluates eligibility
- ARCH-08: Lifecycle wiring -- Criterion.after_update -> re-evaluate all affected grants via GrantCriterion join
- ARCH-09: Criteria learning loop -- auto-classify previously-seen criteria with confirmed org_eligible status, skip LLM call

**Success Criteria:**
1. A Grant record can be created with status "discovered" and transitioned to "eligible", "partly_eligible", or "not_eligible" -- status is a constrained Literal field enforced by Pydantic
2. Criterion and GrantCriterion records can be created, linked, and queried -- GrantCriterion scores are 0.0-1.0 floats with reasoning text visible in the API
3. Creating a Grant record with status "discovered" triggers a lifecycle TX that reaches the Analyzer agent address
4. Updating a Criterion's org_eligible flag triggers re-evaluation of all grants linked via GrantCriterion
5. All new models (Criterion, GrantCriterion, Report) are browsable via GET /{ClassName} schema and GET /{tablename} list endpoints

---

## Phase 3: Scanning Features

**Goal:** The scanner agent can discover new grants from configured sources -- scraping, pagination, and deduplication work end-to-end.

**Dependencies:** Phase 2 (Grant model, Source model, Scanner Agent instance)

**Requirements:**
- SCAN-01: Source scraping via httpx -- fetch source URLs, extract grant links, skip-and-continue on failure
- SCAN-02: Pagination handling -- agent adapts to single-page and paginated source structures
- SCAN-03: URL deduplication -- check each discovered grant URL against existing Grant records in DB
- SCAN-04: Configurable concurrency -- max parallel sources setting on scanner agent constraints

**Success Criteria:**
1. Running the scanner agent against a source URL produces new Grant records in the database with status "discovered"
2. When a source page contains pagination, the scanner follows subsequent pages and extracts grants from all of them
3. Running the scanner twice against the same source does not create duplicate Grant records (URL dedup)
4. When a source URL is unreachable, the scanner logs the failure and continues processing remaining sources

---

## Phase 4: Eligibility Features

**Goal:** The analyzer agent evaluates discovered grants against org documentation and produces scored eligibility results with a learning loop that reduces LLM cost over time.

**Dependencies:** Phase 2 (Criterion, GrantCriterion, Analyzer Agent, lifecycle wiring), Phase 3 (grants exist to analyze)

**Requirements:**
- ELIG-01: Analyzer reads org documentation from ORG_DOCS_PATH directory (markdown files)
- ELIG-02: Criteria extraction -- analyzer parses grant requirements, normalizes into Criterion records with category
- ELIG-03: Per-criterion scoring -- 0.0-1.0 match score against org docs with reasoning text
- ELIG-04: Human override -- user can change criterion org_eligible flag (eligible <-> ineligible)
- ELIG-05: Automatic re-evaluation -- Criterion.after_update lifecycle event triggers re-scoring of affected grants

**Success Criteria:**
1. After the analyzer processes a grant, the grant has GrantCriterion records linking it to normalized Criterion entries, each with a score and reasoning
2. The analyzer reads org documentation from the configured ORG_DOCS_PATH and uses it to inform eligibility scoring
3. A user can update a Criterion's org_eligible flag via PUT /criteria/{id}, and affected grants are automatically re-scored
4. On a second run, criteria that were previously seen and have a confirmed org_eligible status are auto-classified without an LLM call

---

## Phase 5: Frontend

**Goal:** Users can browse all grant-watch data, trigger agent runs, view run history, and see eligibility results through the N3TX UI.

**Dependencies:** Phase 2 (all models exist), Phase 3 + 4 (data to display)

**Requirements:**
- UI-01: All models browsable -- ntx-list/ntx-item for Grants, Sources, Agents, Reports, Criteria, GrantCriterion
- UI-02: Agent Run button -- manual trigger on agent detail view (POST /agents/{id}/run)
- UI-03: Run status + history -- status indicator on agent, list of past AgentRun records with results
- UI-04: Eligibility dashboard -- grant list with color-coded eligibility status, expandable criterion breakdown per grant

**Success Criteria:**
1. Every model (Grant, Source, Criterion, GrantCriterion, Report, AgentActor, AgentRun) is navigable in the sidebar and renders a list view and detail view
2. An agent detail page has a "Run" button that triggers the agent and displays the result
3. An agent detail page shows a history of past runs with status, timestamps, and token usage
4. The grant list displays color-coded eligibility status (green/yellow/red) and each grant can be expanded to show per-criterion scores and reasoning

---

## Phase 6: Testing & Hardening

**Goal:** The full pipeline is validated end-to-end -- from scheduler trigger through scanning, analysis, and report generation -- with deterministic tests at every layer.

**Dependencies:** Phase 3 (scanning), Phase 4 (eligibility), Phase 5 (frontend models registered)

**Requirements:**
- TEST-01: Mock HTTP unit tests -- fixture HTML pages for scanner agent, deterministic scraping tests
- TEST-02: Local test server -- serve fake grant pages for integration tests (real HTTP, controlled content)
- TEST-03: HTTP endpoint integration tests -- full request lifecycle via test client (POST /agents/{id}/run with auth)
- TEST-04: Pipeline E2E test -- Scheduler -> Scanner -> Analyzer -> Report, full chain with mock LLM

**Success Criteria:**
1. Scanner agent tests run against fixture HTML (no network) and produce deterministic Grant records
2. Integration tests start a local HTTP server with fake grant pages and run the scanner against it end-to-end
3. POST /agents/{id}/run via the test client (with auth token) returns a successful agent run response and persists AgentRun/AgentStep records
4. A full pipeline test runs Scheduler -> Scanner -> Analyzer -> Report with mock LLM and verifies that Reports, Grants, Criteria, and GrantCriterion records are all created correctly

---

## Progress

| Phase | Name | Requirements | Status |
|-------|------|--------------|--------|
| 1 | Framework Agentic Infrastructure | FW-01..FW-10 (10) | Not Started |
| 2 | App Architecture | ARCH-01..ARCH-09 (9) | Not Started |
| 3 | Scanning Features | SCAN-01..SCAN-04 (4) | Not Started |
| 4 | Eligibility Features | ELIG-01..ELIG-05 (5) | Not Started |
| 5 | Frontend | UI-01..UI-04 (4) | Not Started |
| 6 | Testing & Hardening | TEST-01..TEST-04 (4) | Not Started |

**Coverage:** 36/36 requirements mapped

---

*Created: 2026-03-04*
