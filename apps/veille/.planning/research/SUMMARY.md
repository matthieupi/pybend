# Research Synthesis: Veille

**Project:** Agentic grant monitoring for non-profits
**Framework:** N3TX Level 3 (ActorModel + agents)
**Synthesized:** 2026-03-20
**Overall Confidence:** HIGH

---

## Executive Summary

Veille is a strong fit for N3TX Level 3. The framework provides everything needed for the CRUD backbone (Source, Grant, Organization, Run, Report models), authentication, schema-driven UI, and agent-powered scraping/analysis -- out of the box or with minimal wiring. The critical path is narrow: get models defined, wire the Run agent with tools, and iterate on prompts. The `examples/grants/` reference app validates that this exact pattern (agent + CRUD tools + WebTools + streaming) works end-to-end in the framework today.

The primary risk is not technology but prompt engineering. The framework handles tool routing, streaming, storage, and UI automatically. What remains custom is: (a) the scraping agent prompt that reliably extracts grants from diverse FR/EN source pages, (b) the admissibility analysis prompt that produces consistent scoring against the org profile, and (c) the Run orchestration that sequences scraping and analysis without letting LLM non-determinism break the pipeline. All three are solvable but require iteration.

The most important architectural decision is **deterministic orchestration with agentic steps**: a Python-controlled `execute()` method on Run that calls agents for the parts requiring LLM reasoning, rather than giving an LLM full control over pipeline sequencing. The agent gets explicit workflow instructions (steps 1-8) with latitude within each step but prescribed ordering. This balances reliability with AI capability.

The research identified 23 pitfalls, of which 5 are critical (silent agent mixin non-injection, actor handler deadlocks, SQLite memory DB gotcha, auth bypass on internal messages, schema cache invalidation). All have known prevention patterns. The most likely to bite early is import ordering -- one wrong line in `main.py` silently disables all agent capabilities.

---

## Stack Recommendations

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Framework | N3TX 0.10+ (all 4 packages) | Provides models, actors, agents, UI. Veille is an N3TX app. |
| Routing | Level 3 (`routing='actor'`) | Required for agent tool discovery via Matrix. |
| Models | `ActorModel` for everything | Level 3 mandate. Even non-agent models. |
| Agents | `__agent__` dict on Run + WebTools | Fixed tool sets, code-level config. Not AgentActor (DB-stored config is overkill). |
| Database | SQLite (file-based) | Native N3TX backend. Single-org deployment. Auto-migration, JSON fields, FK hydration. |
| LLM (prod) | Anthropic Claude Sonnet | Best reasoning for grant extraction and admissibility analysis. |
| LLM (dev) | Ollama llama3.1 | Free local inference for development iteration. |
| Scraping | httpx + BeautifulSoup | Inside `@expose_route` methods on WebTools actor. |
| PDF (Phase 6) | WeasyPrint or reportlab | Standard Python library, not N3TX concern. |
| Scheduling (Phase 6) | APScheduler | Lightweight, in-process, one cron job. |

**Not needed:** Celery, Redis, PostgreSQL, custom REST framework, WebSocket protocol, custom auth system. N3TX handles all of these concerns.

---

## Feature Landscape

### What N3TX Gives for Free (model definition only)

| Feature | Mechanism | Lines of Code |
|---------|-----------|---------------|
| Source CRUD (API + UI + forms + validation) | `ActorModel` + `__storable__` | ~25 |
| Grant CRUD with full detail fields | `ActorModel` + widgets (URL, Date, Textarea, Markdown) | ~40 |
| Organization profile CRUD | `ActorModel` + JSON fields for lists/dicts | ~25 |
| Run history CRUD | `ActorModel` + status/timestamp fields | ~20 |
| Report CRUD | `ActorModel` + JSON fields for sections | ~25 |
| User authentication (JWT, login, register) | `BaseUser + ActorModel` | ~5 |
| Schema-driven frontend (sidebar, list, detail, forms) | Schema pipeline + ntx-list/ntx-item | 0 (auto) |
| Pagination on all list endpoints | `?limit=N&offset=M` auto-supported | 0 (auto) |
| Access control (admin-only) | `__access__ = {'read': AUTHENTICATED, ...}` | 0 (config) |

### What Requires Wiring (N3TX pattern + config)

| Feature | Pattern | Effort |
|---------|---------|--------|
| Agent tool discovery | `__agent__ = {'tools': [...]}` on Run | Config only |
| Streaming execution progress | `@expose_route(stream=True)` + `StreamActor` mixin | LOW |
| JSON field storage (criteria, past_grants) | `list`/`dict` field types | 0 (automatic) |
| Custom widgets (admissibility badge, status) | Extend Widget class + `registerWidget()` | LOW per widget |

### What Must Be Built (custom logic)

| Feature | Complexity | Why Custom |
|---------|------------|------------|
| WebTools actor (fetch, extract_text, extract_grants) | MEDIUM | HTTP scraping logic, HTML parsing, LLM extraction |
| Run orchestration (execute endpoint) | HIGH | Pipeline sequencing, error handling, streaming |
| Admissibility analysis | MEDIUM-HIGH | Prompt design for consistent scoring |
| Grant deduplication | LOW-MEDIUM | URL match + title similarity |
| Source auto-discovery | LOW | Prompt engineering extension |
| Report generation (in-app) | LOW | Store markdown, render via widget |
| PDF export | MEDIUM | Library integration (Phase 6) |
| Email notification | MEDIUM | SMTP integration (Phase 6) |
| Scheduled runs | LOW | APScheduler + TX trigger (Phase 6) |

### Anti-Features (explicitly do not build)

- Custom REST API layer (use `@expose_route`)
- Custom frontend data fetching (let schema drive UI)
- Separate analysis microservice (SQLite handles the load)
- Multi-page SPA with custom routing (use `ntx-router`)
- Generic scraping framework (LLM handles source variation)
- Real-time WebSocket for progress (SSE via streaming endpoints)

---

## Architecture Overview

### Model Hierarchy

```
Matrix (root)
  |-- users           User (BaseUser + ActorModel)
  |-- organizations   Organization (ActorModel, storable, singleton)
  |-- sources         Source (ActorModel, storable)
  |-- grants          Grant (ActorModel, storable)
  |-- runs            Run (ActorModel, storable, __agent__)  <-- CORE VALUE
  |-- reports         Report (ActorModel, storable)
  |-- web_tools       WebTools (ActorModel, NON-storable, __agent__)
```

### Agent Topology

**Two agents, clear separation:**

- **Run** (`__agent__`): Orchestrates the full scraping + analysis workflow. Tools: `sources`, `grants`, `organizations`, `reports`, `web_tools`. Streaming execution via SSE. This is the core value delivery.
- **WebTools** (`__agent__`): Stateless web utility. Methods: `fetch` (HTTP), `extract_text` (HTML parsing), `extract_grants` (LLM extraction). Reusable by future agents.

**Why not more agents:** One agent maintains full LLM context across the workflow (remembers what it scraped, can reason about admissibility without re-reading). Multi-agent coordination adds overhead without benefit at this scale.

**Why not fewer:** WebTools is separated because scraping utilities are reusable and have no state. The Run agent calls WebTools as tools.

### Key Design Decisions

| Decision | Choice | Alternative Rejected |
|----------|--------|---------------------|
| Agent config | `__agent__` dict on model | AgentActor (DB-stored config) -- overkill for fixed tool sets |
| FK strategy | Plain `int` fields (source_id, run_id) | `Ref`/`ListRef` -- unnecessary join tables for one-directional FKs |
| Pipeline control | Structured agent prompt with explicit steps | Full LLM orchestration -- too non-deterministic for sequential pipeline |
| Org profile | Storable singleton in DB | Config file -- needs UI editing and agent read access |
| Report storage | Denormalized snapshot (JSON fields) | FK-only references -- reports must survive grant updates |

### Custom Frontend Components (3 total)

| Component | Type | Purpose |
|-----------|------|---------|
| `veille-run-detail` | StreamActor(HTMLElement) | Live execution view with UPPERCASE handlers |
| `veille-report` | HTMLElement | Formatted report with expandable grant sections |
| `veille-org-profile` | HTMLElement | Singleton profile editor with JSON field support |

Everything else uses standard `ntx-list`, `ntx-item`, `ntx-table` components.

---

## Critical Pitfalls (Top 5)

### 1. Agent Import Ordering (SILENT FAILURE)

`import n3tx_agents` MUST come before model imports in `main.py`. Otherwise `__agent__ = True` silently does nothing -- no error, just missing agent methods at runtime.

**Prevention:** First line of `main.py`: `import n3tx_agents`. Add assertion: `assert AgentMixin in Run.__mro__`.

### 2. `request()` Deadlock in Actor Handlers

Calling `Actor.root().request()` from within a handler blocks the actor thread. The reply TX cannot be processed. Complete deadlock, no error.

**Prevention:** Tool methods (`@expose_route`) should do work directly, not call other actors via `request()`. Use `send()` (fire-and-forget) or `_ask_via_temp()` if inter-actor communication is needed.

### 3. SQLite `:memory:` Creates Separate DBs per Connection

Tests using `SQLiteStorage(':memory:')` will fail because `create_table()` and CRUD operations use different connections (different databases).

**Prevention:** Always use `tmp_path / 'test.db'` in test fixtures. Never `:memory:`.

### 4. Auth Bypass on Internal TX Messages

Actor-to-actor messages skip Tier 2 auth (no `meta.user`). Scheduled jobs or custom TX creation without user context bypass all authorization.

**Prevention:** Always set `meta.user` on TX messages from non-HTTP paths. Use `NetworkAPI` + `auth_interceptor` for external traffic.

### 5. Tool Address Must Match `__tablename__` Exactly

If `__agent__['tools']` contains `'webtools'` but the model has `__tablename__ = 'web_tools'`, the tool is silently skipped. Agent runs without those tools.

**Prevention:** Verify tool addresses match `__tablename__`. Add startup assertions.

---

## Phase Recommendations

Based on dependency analysis across all 4 research files, here is the recommended build order.

### Phase 1: Foundation (~1-2 days)

**Delivers:** Working app skeleton with auth, org profile, and basic UI.

**Models:** User, Organization
**What:** `main.py` bootstrap, `config.py`, `seed.py` (admin user + FFT/RTS org profile), Level 3 routing, auth working.

**Must avoid:** Pitfall 1 (import ordering), Pitfall 5 (schema cache), Pitfall 20 (registry clear on reload), Pitfall 23 (table name validation).

**Research needed:** No -- standard N3TX bootstrap pattern, well-documented.

### Phase 2: Data Models (~1 day)

**Delivers:** Full CRUD for all entities. Navigable web app where admin can manage sources, grants, runs, reports manually.

**Models:** Source, Grant, Run, Report
**What:** Model definitions with fields, widgets, UI hints, access rules. Seed initial sources from `docs/sources.txt`.

**Can parallelize:** Source + Grant definitions are independent. Run and Report depend on nothing at this stage (just CRUD, no agent logic yet).

**Must avoid:** Pitfall 19 (URL field types -- use `str` not `AnyHttpUrl`), Pitfall 6 (method name collisions).

**Research needed:** No -- pure model definition, follows `examples/grants/` patterns.

### Phase 3: Agent Infrastructure (~2-3 days)

**Delivers:** Working scraping pipeline. Trigger a run, watch it scrape sources, extract grants, populate the database.

**What:** WebTools actor (fetch, extract_text, extract_grants), Run agent config (`__agent__` dict), `execute` streaming endpoint, basic deduplication, `veille-run-detail` StreamActor component.

**This is the core value delivery phase.** Highest risk (LLM non-determinism, diverse source formats, prompt reliability).

**Must avoid:** Pitfall 2 (request deadlock in tool handlers), Pitfall 9 (tool address mismatch), Pitfall 16 (tools=[] semantics), Pitfall 15 (LLM config cascade), Pitfall 18 (UPPERCASE handlers).

**Research needed:** YES -- `/gsd:research-phase` recommended for prompt engineering strategy, error handling patterns in long-running agent loops, and deduplication approach.

### Phase 4: Admissibility Analysis (~1-2 days)

**Delivers:** Grants automatically evaluated for admissibility with detailed justification.

**What:** Enhanced Run agent prompt with admissibility instructions, scoring thresholds (admissible >= 0.7, partial 0.3-0.7, non-admissible < 0.3), `analyze_grant` endpoint for single-grant re-analysis, custom admissibility widget.

**Must avoid:** Pitfall 8 (agentic() returns JSON string, not dict).

**Research needed:** Possibly -- admissibility scoring consistency may need prompt iteration.

### Phase 5: Reports (~1 day)

**Delivers:** End-of-run reports with admissible/partial/non-admissible breakdown, custom report view.

**What:** Report model wired to Run agent (creates report as final step), `veille-report` component, denormalized grant data in report.

**Research needed:** No -- straightforward CRUD + custom component.

### Phase 6: Polish and Automation (~2-3 days)

**Delivers:** PDF export, email notification, scheduled runs, source auto-discovery.

**What:** PDF generation (WeasyPrint), SMTP integration, APScheduler for periodic runs, agent prompt extension for source discovery, `veille-org-profile` component.

**Must avoid:** Pitfall 4 (auth bypass on scheduled job TX -- inject `meta.user`), Pitfall 13 (interceptors are per-adapter).

**Research needed:** Minimal -- standard Python library integration.

### Dependency Graph

```
Phase 1 (Foundation: User, Org)
  |
  +---> Phase 2 (Data Models: Source, Grant, Run, Report)
                    |
          Phase 3 (Agent Infrastructure)  <-- CORE VALUE, HIGHEST RISK
                    |
          Phase 4 (Admissibility Analysis)
                    |
          Phase 5 (Reports)
                    |
          Phase 6 (Polish + Automation)
```

Phases 1-2 are low-risk, high-confidence (pure N3TX patterns). Phase 3 is where the real work begins.

### Research Flags

| Phase | Needs `/gsd:research-phase`? | Rationale |
|-------|------------------------------|-----------|
| Phase 1 | No | Standard N3TX bootstrap |
| Phase 2 | No | Pure model definitions |
| Phase 3 | **YES** | Prompt engineering, error recovery, dedup strategy |
| Phase 4 | Possibly | Admissibility scoring calibration |
| Phase 5 | No | Straightforward CRUD + component |
| Phase 6 | No | Standard library integration |

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All from framework source code and working examples. No external unknowns except PDF library. |
| Features | HIGH | Feature-to-framework mapping verified against `examples/grants/` reference app. |
| Architecture | HIGH | Actor topology, model hierarchy, and message flow derived from framework docs and working patterns. |
| Pitfalls | HIGH | 23 pitfalls sourced from framework docs, test suites, and accumulated project memory. All have prevention strategies. |
| Prompt Engineering | LOW | No research on grant extraction / admissibility prompts yet. This is the primary unknown. |
| PDF Generation | LOW | Outside N3TX scope. Library choice deferred to Phase 6. |
| Email Delivery | LOW | SMTP config vs third-party service unresolved. Deferred to Phase 6. |

### Gaps to Address During Planning

1. **Prompt strategy for grant extraction** -- How to reliably extract structured grant data from diverse FR/EN source pages. Needs experimentation with real sources.
2. **Admissibility scoring calibration** -- What scoring thresholds produce useful classifications for the FFT/RTS profile. Needs validation with real grants.
3. **Error recovery in long runs** -- How to handle partial failures (one source down, one extraction fails) without losing the entire run. Needs design.
4. **Source page structure diversity** -- Government sites, foundation pages, and international orgs have vastly different layouts. The LLM must adapt. Needs testing with the actual source list.
5. **LLM cost estimation** -- Token usage per source scrape and per admissibility analysis. Determines operational budget.

---

## Open Questions (Consolidated)

| Question | Source | Priority | When to Resolve |
|----------|--------|----------|-----------------|
| Email delivery mechanism (SMTP vs service)? | PROJECT.md | LOW | Phase 6 |
| PDF generation library (WeasyPrint vs reportlab)? | PROJECT.md | LOW | Phase 6 |
| LLM cost per run (token budget)? | FEATURES.md | MEDIUM | Phase 3 testing |
| Lifecycle events for reactive triggers -- is subscriber pattern implemented? | FEATURES.md | MEDIUM | Phase 5 (report auto-generation) |
| Dedup strategy -- URL-only vs title similarity vs LLM comparison? | FEATURES.md | MEDIUM | Phase 3 |
| How to handle `agentic()` JSON string return in internal code? | PITFALLS.md | LOW | Phase 3 (use `run()` directly) |
| Max iterations constraint for Run agent? | ARCHITECTURE.md | MEDIUM | Phase 3 testing |

---

## Sources

All research derived from primary framework sources (HIGH confidence):

- N3TX framework documentation: `/workspace/docs/` (ARCHITECTURE, CORE, ACTORS, AGENTS, MODELS)
- Per-package docs: `/workspace/packages/n3tx-{core,actors,agents,ui}/docs/`
- Framework source code: `/workspace/packages/n3tx-{core,actors,agents,ui}/src/`
- Reference applications: `/workspace/examples/{grants,actors,chat}/`
- Project definition: `/workspace/apps/veille/.planning/PROJECT.md`
- Accumulated project memory: `/home/claude/.claude/projects/-workspace/memory/MEMORY.md`
