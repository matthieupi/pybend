# Project: Veille

## What This Is

An agentic grant monitoring application built on the N3TX framework. Veille automates the process of discovering, extracting, and evaluating government and private grants/programs for non-profit organizations. It scrapes known funding sources, detects new opportunities, extracts full grant details, and analyzes admissibility against a configurable organization profile.

The name comes from the French concept of "veille" (technological/financing watch) — systematic monitoring of an information landscape.

## Why It Exists

Non-profits spend significant time manually reviewing new grants and programs published weekly by government and private institutions. This is repetitive, error-prone, and takes staff away from mission-critical work. A single missed deadline or overlooked program means lost funding.

The first client is the Fédération franco-ténoise (FFT) and Réseau TNO Santé (RTS) — francophone community organizations in Canada's Northwest Territories that serve the French-speaking minority through health services, immigration support, community development, and advocacy.

The FFT's own 2025-2030 strategic plan explicitly calls for integrating AI into information gathering and political environment monitoring by 2027. Veille is the answer.

## Core Value

**The ONE thing that must work:** The system reliably discovers new grants from configured sources, extracts their details, and tells the organization whether they're eligible — with justification.

Everything else (email reports, auto-discovery, run history) is valuable but secondary. If scraping + extraction + admissibility analysis works, the app delivers value.

## Who Uses It

- **Non-profit staff (admin):** Manage sources, configure organization profile, trigger runs, review reports
- **N3TX team (operators):** Initial setup, monitoring, source onboarding

All users are admins. No public access. Single organization per deployment (but the profile system is generic — any non-profit can use Veille by configuring their own profile).

## First Client Context

**FFT (Fédération franco-ténoise):**
- Porte-parole of the francophone community in the Northwest Territories
- Mandate: represent, defend, promote francophone rights and interests
- Focus areas: political advocacy, community development, immigration, equity/diversity/inclusion
- Strategic orientations: political leadership, community consultation, inclusive development, French language vitality, organizational health

**RTS (Réseau TNO Santé):**
- Facilitates access to French-language health services in NWT
- Works with government, health institutions, training bodies, health professionals, and community
- Focus: bilingual workforce recruitment, health service access, innovation in health, community empowerment

**Relevant grant domains for first deployment:**
- Francophone minority community programs
- Health services in French
- Immigration and integration support
- Community development and infrastructure
- Equity, diversity, inclusion initiatives
- Indigenous-francophone reconciliation projects
- Canadian francophonie programs (federal, OIF)

**Reference documents:** `apps/veille/docs/` contains FFT 2025-2030 strategic plan and RTS 2023-2028 strategic orientations.

## Technical Decisions

| Decision | Rationale | Status |
|----------|-----------|--------|
| N3TX Level 3 + Agents | Full actor routing with agent capabilities needed for agentic scraping, analysis, and streaming | Decided |
| Single org per instance | Simpler deployment model, each non-profit gets their own Veille | Decided |
| English primary UI | Scrapes FR/EN sources, but interface and reports in English | Decided |
| Admin-only access | Small team, no public-facing features | Decided |
| Located at `apps/veille/` | Lives in N3TX monorepo as a reference app | Decided |
| Fresh start (ignore prototype) | Previous prototype had bad architecture, unreliable scraping, inaccurate admissibility, and used outdated framework patterns | Decided |
| Auto-deduplication | Same grant from multiple sources should be merged automatically | Decided |
| Auto-explore sources | Agent can discover and add new sources (flagged as agent-discovered vs human-added) | Decided |

## Constraints

- **Framework:** Must use N3TX patterns — ActorModel, agents, schema-driven UI. No hand-rolled routes or custom data plumbing.
- **Scraping:** Sources are diverse (government sites in FR/EN, private foundations, international orgs). Must handle varied page structures.
- **LLM costs:** Admissibility analysis runs per-grant. Need to be mindful of token usage on large batches.
- **No prototype reuse:** Start completely fresh. Do not read or reference previous app code.

## Key Concepts

### Organization Profile
Configurable description of the non-profit using the app:
- Mission and activities (what the org does, who they serve)
- Legal status and location (province/territory, incorporation type, charitable status)
- Past grants received (history of funding, to avoid duplicates and show track record)
- Custom eligibility criteria (budget size, employee count, specific capabilities)

### Source
A website or page to scrape for grant opportunities:
- URL, name, description
- Human-added vs agent-discovered (boolean flag)
- Scraping notes/context to guide the agent

### Grant
A specific funding program or grant opportunity:
- Full details: amount, description, deadlines, admissibility criteria, required documents, application process
- Source URL and origin
- Status: new, analyzed, admissible, partially admissible, non-admissible

### Run
A scraping + analysis execution:
- Covers all sources (scheduled or manual)
- Can also target a single URL (ad-hoc)
- Full history kept — every run logged with results
- Generates a report at completion

### Admissibility Analysis
Two-layer evaluation of each grant against the org profile:
1. **Criteria matching:** Extract grant criteria, match against org profile fields, score each criterion
2. **LLM reasoning:** Agent reads full grant details + org profile, reasons about overall fit with justification

Result: admissible / partially admissible / non-admissible — with detailed reasoning.

### Report
End-of-run summary:
- Admissible grants (with justification)
- Partially admissible grants (with gaps identified)
- Non-admissible grants (with reason for exclusion)
- New sources discovered (if any)
- Available in-app, as PDF export, and via email notification

## Requirements

### Validated

(None yet — fresh build)

### Active

- [ ] Source CRUD — add, edit, remove, list scraping sources with URL, name, description
- [ ] Source discrimination — flag sources as human-added vs agent-discovered
- [ ] Organization profile — configurable mission, legal status, location, past grants, custom criteria
- [ ] Scraping agent — scan sources for new grants/programs with context-aware exploration
- [ ] Wide-net scraping — agent explores sites broadly, directed by org context but not narrowly filtered
- [ ] Grant extraction — full detail capture (amount, deadlines, criteria, documents, process)
- [ ] Grant deduplication — detect and merge same grant from multiple sources
- [ ] Admissibility analysis — criteria matching + LLM reasoning against org profile
- [ ] Admissibility classification — admissible / partially admissible / non-admissible with justification
- [ ] Run management — trigger runs (all sources or single URL), track execution
- [ ] Run history — full logging of past runs with results, compare across runs
- [ ] Scheduled runs — automated periodic scraping (weekly or configurable)
- [ ] Ad-hoc URL scanning — run agent on a specific URL on demand
- [ ] Report generation — end-of-run summary with admissible/partial/non-admissible breakdown
- [ ] In-app report view — dashboard showing run results
- [ ] PDF export — downloadable report document
- [ ] Email notification — send report summary after run completion
- [ ] Auto-discovery — agent follows leads to find new funding sources, adds them (flagged)

### Out of Scope

- Multi-tenant (multiple orgs per instance) — deploy separate instances instead
- Public-facing pages — admin-only for now
- Grant application submission — Veille finds and evaluates grants, doesn't apply for them
- Real-time notifications (WebSocket push) — email + in-app is sufficient
- Bilingual UI — English primary, French source scraping is handled by LLM
- Grant change tracking (deadline extensions, criteria updates) — v2 consideration

## Open Questions

- Email delivery mechanism (SMTP config? Third-party service?)
- Scheduled run implementation (cron? Built-in scheduler?)
- PDF generation library choice
- LLM provider and model for scraping/analysis agents (Anthropic Claude? OpenAI? Configurable?)

---
*Last updated: 2026-03-20 after initialization*
