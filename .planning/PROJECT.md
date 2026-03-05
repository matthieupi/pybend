# Grant-Watch: Automated Grant Discovery & Eligibility System

## What This Is

A production-grade grant-watching application built on N3TX's agentic architecture. Automated agents scan government and institutional websites for open grants, evaluate eligibility against organizational documentation, and surface actionable opportunities — with a learning loop that reduces LLM costs over time as criteria are encountered and classified.

## Core Value

**Automated grant discovery with intelligent eligibility scoring.** The ONE thing that must work: a scheduled pipeline that finds new grants, evaluates them against org capabilities, and presents scored results — without human intervention for the happy path.

## Who It's For

A single organization's grants team. They configure sources to watch, provide org documentation, and review discovered grants with pre-computed eligibility scores. v1 is single-tenant.

## The Pipeline

```
┌──────────────┐     cron      ┌────────────────┐    creates     ┌───────────┐
│  Scheduler   │──────────────>│  Grant Scanner  │──────────────>│   Grant   │
│  Actor       │               │  Agent          │               │   Model   │
└──────────────┘               └────────────────┘               └─────┬─────┘
                                                                      │
                                                            after_create (TX)
                                                                      │
                                                                      v
┌──────────────┐   generates   ┌────────────────┐   scores     ┌─────────────────┐
│    Report    │<──────────────│ Grant Analyzer  │<────────────>│ GrantCriterion  │
│    Model     │               │ Agent           │              │ (join + score)  │
└──────────────┘               └───────┬────────┘              └────────┬────────┘
                                       │                                │
                                       v                                v
                               ┌───────────────┐              ┌──────────────┐
                               │   Org Docs    │              │  Criterion   │
                               │  (files/disk) │              │  (normalized)│
                               └───────────────┘              └──────────────┘
```

### Step-by-Step Flow

1. **SchedulerActor** wakes at predefined interval (cron expression stored in DB)
2. **Grant Scanner Agent** receives RUN task, lists all Sources
3. Scanner scrapes each source URL (configurable concurrency limit), handles pagination variations
4. Scanner extracts individual grant URLs from each source page
5. Scanner checks each URL against existing Grants in DB (URL match dedup)
6. For each new grant, Scanner creates a Grant record (status: `discovered`)
7. **Grant.after_create** lifecycle event publishes TX to Grant Analyzer Agent
8. **Grant Analyzer Agent** reads the grant details + org docs from `ORG_DOCS_PATH`
9. Analyzer extracts eligibility criteria from the grant, normalizes them into the Criterion table (with category)
10. For each criterion, Analyzer scores the org's match (0-1) and creates GrantCriterion records
11. Previously-seen criteria with human-confirmed status are auto-classified (no LLM call)
12. Analyzer aggregates scores, updates Grant status: `eligible` / `partly_eligible` / `not_eligible`
13. After all grants in a run are processed, a **Report** record is created summarizing findings

### The Criteria Learning Loop

```
Run 1: LLM evaluates all criteria (expensive)
         ↓
Human reviews, flips some criteria (eligible ↔ ineligible)
         ↓
Criterion.after_update → re-evaluates affected grants
         ↓
Run 2: Previously-seen criteria auto-classified (cheap), only new criteria hit LLM
         ↓
System gets cheaper and more accurate with each run
```

## Architecture

### Actors & Agents

| Actor | Type | Role |
|-------|------|------|
| SchedulerActor | Actor (new) | Cron-based job scheduling, DB-stored intervals |
| Grant Scanner | AgentActor instance | Scrapes sources, deduplicates, creates grants |
| Grant Analyzer | AgentActor instance | Evaluates eligibility, scores criteria |
| WebTools | ActorModel (existing) | HTTP scraping via httpx |
| FileReader | ActorModel (new) | Reads org docs from disk path |

### Data Models

| Model | Purpose | Key Fields |
|-------|---------|------------|
| Source | URLs to watch | name, url, category, scrape_config |
| Grant | Individual grants | title, agency, url, deadline, amount_min/max, status, description |
| Criterion | Normalized eligibility criteria | text, category (Literal), org_eligible (bool/null), source_count |
| GrantCriterion | Join: grant × criterion | grant_id, criterion_id, score (0-1), status (auto/manual), reasoning |
| Report | Scan run summary | run_date, grants_found, grants_eligible, summary |
| AgentRun | Agent execution history | agent_id, task, result, status, usage (tokens/cost), timestamps |
| AgentStep | Tool call log within a run | run_id, tool_name, args, result, duration |
| AgentActor | Agent definitions (existing) | name, prompt, tools, llm, constraints |

### Grant Status Lifecycle

```
discovered → eligible | partly_eligible | not_eligible
```

Eligibility is the terminal state in v1. Users browse grants in the UI and make decisions externally.

### LLM Configuration

- **Default:** Ollama local (free, private)
- **Supported:** Anthropic Claude, OpenAI, Google — any pydantic-ai provider
- **Per-agent:** Each AgentActor row specifies its `llm` field (e.g. `ollama:llama3.1`, `anthropic:claude-sonnet-4-5-20250929`)
- **Ollama deployment:** External to app stack (separate machine for prod, local for dev)

### Org Documentation

- Located at `ORG_DOCS_PATH` environment variable (directory of markdown files)
- FileReader actor reads and returns contents
- v2: Replace with remote source actors (Google Drive, Teams, Obsidian, etc.)

### Error Handling

- Source scrape failure: skip and continue, log failure in report
- LLM failure: surface error in AgentRun record, don't crash pipeline
- Tool call failure: pydantic-ai ModelRetry mechanism

### Observability

- **AgentRun**: Every agent execution logged with task, result, token usage, cost, status, timestamps
- **AgentStep**: Every tool call within a run logged with tool name, arguments, result, duration
- Progressive frontend: run history visible in UI (phase 2+)

## Frontend (Progressive)

| Phase | Scope |
|-------|-------|
| 1 - Minimal | Existing ntx-list/ntx-item for all models. Manual 'Run' button on agents. No streaming. |
| 2 - Operational | Agent run status indicator, toast on completion, run history list |
| 3 - Full | Live tool-call visualization, token usage display, chat-like interaction |

## Technology

- **Framework:** N3TX (existing) — ActorModel, Matrix, TX routing, schema-driven UI
- **Agent engine:** pydantic-ai (existing dependency)
- **HTTP client:** httpx (clear integration path for Playwright in v2)
- **LLM:** Ollama default, configurable per-agent
- **Storage:** SQLite (existing)
- **Frontend:** N3TX's vanilla JS Web Components (existing)

## Constraints

- **Single-tenant** — one organization, no multi-org
- **HTML only** — no PDF document parsing in v1
- **httpx only** — no headless browser / JS rendering in v1
- **No notifications** — no email/webhook alerts in v1
- **No user roles** — basic auth only, all authenticated users see everything
- **Brownfield** — builds on existing N3TX framework and agent system (63+ tests passing)

## Requirements

### Validated

- Grant, Source, WebTools models exist and work
- AgentActor with DB-stored config, tool discovery, Matrix routing
- AgentMixin injection via `__agent__ = True`
- Tool discovery from actor schemas (CRUD + custom methods)
- pydantic-ai integration (agent loop, tool calling, usage tracking)
- HTTP API endpoints for all models + agent run
- 63+ passing tests across core agent system and example app

### Active

- [ ] SchedulerActor with DB-stored cron expressions
- [ ] Grant Scanner agent (scraping, pagination, deduplication)
- [ ] Grant Analyzer agent (eligibility scoring, criteria extraction)
- [ ] Criterion model (normalized text, category, org eligibility)
- [ ] GrantCriterion join model (score, status, reasoning)
- [ ] Criteria learning loop (auto-classify known criteria)
- [ ] Report model (scan run summary)
- [ ] AgentRun model (execution history, usage tracking)
- [ ] AgentStep model (tool call logging)
- [ ] FileReader actor (org docs from disk)
- [ ] Lifecycle event wiring (Grant.after_create → Analyzer)
- [ ] Lifecycle event wiring (Criterion.after_update → re-evaluate grants)
- [ ] Real LLM integration (Ollama + Anthropic)
- [ ] HTTP integration tests (full request lifecycle)
- [ ] Configurable concurrency for source scraping
- [ ] Error handling hardening (skip-and-continue, logging)
- [ ] Frontend minimal (all models browsable, agent Run button)
- [ ] Frontend operational (run status, toasts, history)
- [ ] Frontend full (live tool visualization, chat interface)
- [ ] Mock HTTP unit tests + local server integration tests
- [ ] Docker Compose for production deployment

### Out of Scope

- Email/webhook notifications — v2 (architecture supports adding NotificationActor)
- Multi-tenant support — v2 (add org_id to models, tenant-aware queries)
- PDF document parsing — v2 (add PDFTools actor alongside WebTools)
- Role-based access control — v2 (N3TX already has RBAC primitives)
- Playwright/headless browser — v2 (swap httpx for Playwright in WebTools)
- Remote org doc sources — v2 (GoogleDriveActor, TeamsActor, ObsidianActor replace FileReader)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Separate agents (scanner, analyzer) over single orchestrator | Specialized prompts, independent scaling, clearer failure boundaries | Each agent is a distinct AgentActor DB row |
| Criteria learning loop | Reduces LLM cost per run, improves accuracy, enables human-in-the-loop | Criterion + GrantCriterion models with lifecycle re-evaluation |
| URL-based deduplication | Simple, reliable, sufficient for v1 | Grant.url is the uniqueness key |
| Lifecycle events for agent triggering | Reactive, decoupled, already supported by ActorModel | Grant.after_create → Analyzer, Criterion.after_update → re-evaluate |
| AgentRun + AgentStep for observability | Full audit trail without complexity of external tracing | Two new models, populated during agent_run() |
| Configurable LLM, Ollama default | Free/private for dev, swappable for prod | Per-agent `llm` field in AgentActor |
| httpx with Playwright path | Fast for v1, JS rendering available in v2 | WebTools uses httpx, interface stable for swap |
| Skip-and-continue on failure | Partial results better than no results | Failed sources logged in Report, pipeline continues |
| DB-stored cron for scheduler | Editable via API/UI, no config file changes needed | SchedulerActor with cron expression field |
| Progressive frontend | Ship value early, add polish iteratively | Three phases: minimal → operational → full |

---
*Last updated: 2026-03-04 after initialization*
