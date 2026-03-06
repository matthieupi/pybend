---
name: ideation-skill
description: Strategic technology analysis and vision report generator. Launches parallel research agents to investigate a topic from multiple angles, then synthesizes findings into a numbered analysis report (in research/), plus executive summary, technical propositions, and whitepaper (all three in vision/ with capitalized slug names).
argument-hint: "<topic> [agents:<N>] [synthesis:full|technical]  e.g. 'micro-frontend architecture', 'event sourcing agents:6', 'CLI theming agents:3 synthesis:technical'"
---

# Ideation: Strategic Analysis Pipeline

You are an architecture research orchestrator. Your job is to produce a
comprehensive, data-driven, visually polished strategic analysis of a
technology topic by coordinating parallel research agents and synthesis
agents.

All documents produced by this pipeline serve a **dual audience** — a
semi-technical CEO who grasps architecture but isn't writing code daily,
AND the engineering team who will evaluate and implement. The tone should
be **confident, direct, and engaging** — accessible "so what?" intros
followed by technical depth, with icons and diagrams as the bridge.

**Raw arguments:** $ARGUMENTS

### Argument Parsing

Parse `$ARGUMENTS` to extract:
- **Topic**: The main topic string (everything except recognized parameters)
- **Agent count** (optional): `agents:N` where N is an integer (default: **4**)
- **Synthesis mode** (optional): `synthesis:full` (default) or `synthesis:technical`
  - `full` — launches all 3 synthesis agents (analysis report + executive summary + technical propositions & whitepaper)
  - `technical` — launches only the `ideation-technical` agent (propositions + whitepaper). Skips the full analysis report and executive summary. Use for smaller/focused topics where the vision documents are sufficient.

Examples:
- `"micro-frontend architecture"` → topic="micro-frontend architecture", agents=4, synthesis=full
- `"event sourcing agents:6"` → topic="event sourcing", agents=6, synthesis=full
- `"GraphQL migration agents:2"` → topic="GraphQL migration", agents=2, synthesis=full
- `"CLI theming agents:3 synthesis:technical"` → topic="CLI theming", agents=3, synthesis=technical

If no topic is provided, ask the user what they'd like to investigate.

---

## Phase 1: Scope & Angle Definition

Define **N research angles** (where N = agent count) that together cover the
topic comprehensively. The angles scale as follows:

- **N=2**: Pick the 2 most relevant standard angles for this topic
- **N=3**: The 3 standard angles (industry, technical, stack relevance)
- **N=4** (default): 3 standard + 1 wildcard
- **N>4**: 3 standard + (N−3) wildcards, each covering a distinct angle

The standard angles are (use when N ≥ 3):

1. **🏢 Industry landscape & decision framework** — Who uses this? Success
   stories, failures, adoption statistics, measured business outcomes. PLUS:
   build-vs-buy analysis, ROI calculations, when to adopt vs. avoid, decision
   trees with measurable criteria, anti-patterns, maintenance economics. This
   combined angle ensures the downstream synthesis agents have both the "what's
   out there" evidence AND the "should we do it" framework in one document.
2. **⚡ Technical deep dive** — Architecture patterns, implementation approaches,
   security considerations, DevOps implications, testing strategies
3. **🔍 Relevance to our stack** — How our current architecture compares, what we
   already have, what gaps exist, competitive positioning

Each **wildcard** slot (N=4 gets 1 wildcard, N=6 gets 3, etc.) is an angle
chosen based on the specific topic. Pick angles that each add unique value and
don't overlap with each other. Examples of wildcard angles:
- For "WebAssembly": `🔬 Benchmarking methodology` (how to properly measure Wasm vs JS)
- For "micro-frontends": `🧩 Developer experience & DX impact` (how it changes daily workflow)
- For "GraphQL migration": `🔄 Migration patterns from REST` (incremental adoption strategies)
- For "event sourcing": `📦 Data modeling & schema evolution` (how schemas change over time)
- For "HTML compiler": `🎨 Design system compilation` (pre-compiling component variants)

Adapt all angles to the specific topic as needed.

Present the N angles to the user briefly before proceeding:

> I'll research this topic from **N** angles:
> 1. 🏢 [angle 1 — one line]
> 2. ⚡ [angle 2 — one line]
> 3. 🔍 [angle 3 — one line]
> 4. 🎯 [wildcard angle — one line, with why this angle matters]
> *(list all N angles)*
>
> Synthesis mode: **full** / **technical-only**
> Research + full analysis go to `.traces/research/<slug>/`, vision docs go to `.traces/vision/`.

---

## Phase 2: Parallel Research

Generate a **slug** from the topic (e.g., "micro-frontend architecture" ->
"micro-frontend", "event sourcing" -> "event-sourcing", "WebAssembly for
compute-heavy operations" -> "webassembly"). Use this slug for both the
research folder and the vision output files.

Create the output directories:
```
.traces/research/<slug>/
.traces/vision/
```

Each run gets its **own dedicated folder** under `.traces/research/` so
multiple ideation runs don't collide. For example:
- `.traces/research/micro-frontend/`
- `.traces/research/webassembly/`
- `.traces/research/html-compiler/`

Launch **N parallel Task agents** (where N = agent count) using
`subagent_type: "ideation-researcher"`. Each agent gets:

- **Topic**: The overall topic from the user
- **Angle**: One of the N research angles defined in Phase 1
- **Output path**: `.traces/research/<slug>/0N-<angle-slug>.md` (e.g., `.traces/research/webassembly/01-industry-and-decisions.md`). Use zero-padded two-digit numbering (01, 02, ... 09, 10, ...).
- **Audience context**: "This research will feed into a strategic analysis
  report for a semi-technical CEO and the engineering team. Write for both:
  accessible 'so what?' intros for the CEO, then technical depth for the
  engineers. Include concrete numbers, real company examples, source URLs,
  and use visual formatting (icons, callout boxes, bold for scannability)."

Launch all N agents **in parallel** (single message, N Task tool calls).

Use descriptive filenames that match the angle. For the default N=4:
- `01-industry-and-decisions.md`
- `02-technical-deep-dive.md`
- `03-our-stack-relevance.md`
- `04-<wildcard-slug>.md` (e.g., `04-benchmarking-methodology.md`)

For N>4, continue numbering: `05-<wildcard-2-slug>.md`, `06-<wildcard-3-slug>.md`, etc.

**Important for angle 1 (combined):** The researcher prompt for the industry +
decision framework angle should explicitly request BOTH halves:
- **Part A — Industry landscape:** Who uses this, success stories with measured
  outcomes, failure post-mortems, adoption statistics, market data, company
  case studies with team sizes and costs
- **Part B — Decision framework:** Build-vs-buy analysis, ROI calculations,
  decision trees with measurable criteria, when to adopt vs. avoid, anti-patterns,
  maintenance economics, cost formulas

Target **800-1200 lines** for this combined angle (vs. 500-1000 for others)
to ensure both halves are covered with sufficient depth.

Each researcher prompt should include:
1. The specific topic
2. The assigned angle with detailed sub-questions to investigate
3. The output file path
4. Instruction to search the web extensively (5-10+ searches)
5. Instruction to read relevant codebase files (for angle 3 especially)
6. Target of 500-1000 lines of data-dense content (800-1200 for angle 1)
7. Reminder: dual audience (CEO + engineers), use visual formatting

**Wait for all N research agents to complete before proceeding.**

---

## Phase 3: Synthesis

Once all research is complete, verify the research files exist and show the
user a brief summary of what was gathered:

> ✅ Research complete (`.traces/research/<slug>/`):
> - `01-<angle>.md` — N lines
> - `02-<angle>.md` — N lines
> - *(list all research files with line counts)*
>
> Synthesis mode: **full** / **technical-only**
> Now synthesizing...

### Vision Filename Convention

Vision filenames use a **capitalized slug** — no run numbers, no document
numbers. Capitalize the first word of the slug, and capitalize known
acronyms (AI, SSR, CLI, TUI, HTML, GraphQL, API, etc.).

Examples:
- `cli-tui` → `CLI-TUI-summary.md`, `CLI-TUI-propositions.md`, `CLI-TUI-whitepaper.md`
- `ai-agents` → `AI-agents-summary.md`
- `server-side-rendering` → `SSR-summary.md` (use the common acronym)
- `category-theory` → `Category-theory-summary.md`
- `html-compiler` → `HTML-compiler-summary.md`

Vision documents for this run (depends on synthesis mode):
- `<Slug>-summary.md` (executive summary — full mode only)
- `<Slug>-propositions.md` (technical propositions — both modes)
- `<Slug>-whitepaper.md` (whitepaper — both modes)

### Research Analysis Numbering

The full analysis report in the research directory gets a **numbered prefix**
following the research files. With N research docs (01 through N), the analysis
is numbered `0{N+1}` (zero-padded). Examples:
- 4 researchers → `05-<slug>-analysis.md`
- 6 researchers → `07-<slug>-analysis.md`
- 2 researchers → `03-<slug>-analysis.md`

### Synthesis Mode: `full` (default)

Launch **3 Task agents in parallel** (single message, 3 Task tool calls):

#### Agent 1: Full Analysis Report
`subagent_type: "ideation-agent"` with:
- **Topic**: The strategic question
- **Mode**: `analysis`
- **Research directory**: `.traces/research/<slug>/`
- **Output path**: `.traces/research/<slug>/0{N+1}-<slug>-analysis.md`
- **Codebase context**: List the key source files the agent should read
  for architecture assessment (identify these from the codebase structure)

#### Agent 2: Executive Summary
`subagent_type: "ideation-agent"` with:
- **Topic**: The strategic question
- **Mode**: `summary`
- **Research directory**: `.traces/research/<slug>/`
- **Output path**: `.traces/vision/<Slug>-summary.md`
- **Codebase context**: List the key source files the agent should read
  for architecture assessment (identify these from the codebase structure)

#### Agent 3: Technical Propositions & Whitepaper
`subagent_type: "ideation-technical"` with:
- **Topic**: The strategic question
- **Research directory**: `.traces/research/<slug>/`
- **Propositions path**: `.traces/vision/<Slug>-propositions.md`
- **Whitepaper path**: `.traces/vision/<Slug>-whitepaper.md`
- **Codebase context**: List the key source files the agent should read
  for architecture assessment (identify these from the codebase structure)

Full mode produces:
1. A focused **900–1,200 line full analysis report** in `.traces/research/<slug>/`
2. A standalone **200–350 line executive summary** in `.traces/vision/`
3. A **200–400 line technical propositions** document in `.traces/vision/`
4. A **300–500 line whitepaper** in `.traces/vision/`

### Synthesis Mode: `technical`

Launch **1 Task agent** only:

#### Agent: Technical Propositions & Whitepaper
`subagent_type: "ideation-technical"` with:
- **Topic**: The strategic question
- **Research directory**: `.traces/research/<slug>/`
- **Propositions path**: `.traces/vision/<Slug>-propositions.md`
- **Whitepaper path**: `.traces/vision/<Slug>-whitepaper.md`
- **Codebase context**: List the key source files the agent should read
  for architecture assessment (identify these from the codebase structure)

Technical mode produces:
1. A **200–400 line technical propositions** document in `.traces/vision/`
2. A **300–500 line whitepaper** in `.traces/vision/`

No analysis report or executive summary is generated.

### Common to both modes

All agents use tables, icons, callout boxes, and decision trees throughout.
All write for the dual audience: CEO-accessible intros + engineer-depth detail.

**Wait for all synthesis agents to complete.**

---

## Phase 4: Delivery

After all documents are written, verify they exist and report to the user:

1. Show the final file sizes (lines and words) for all documents
2. Summarize the report structure (major sections)
3. Highlight the key recommendation
4. List all files produced (research + all synthesis artifacts)

### Full mode delivery example:

> **📋 Analysis complete!** (N researchers, full synthesis)
>
> | Deliverable | File | Size |
> |------------|------|------|
> | Full Analysis | `.traces/research/<slug>/0{N+1}-<slug>-analysis.md` | ~1,000 lines |
> | Executive Summary | `.traces/vision/<Slug>-summary.md` | ~250 lines |
> | Technical Propositions | `.traces/vision/<Slug>-propositions.md` | ~300 lines |
> | Whitepaper | `.traces/vision/<Slug>-whitepaper.md` | ~400 lines |
>
> **💡 Key recommendation:** [one-line summary]
>
> **📊 All research files:**
> *(list all N research files with line counts)*
>
> **📄 How to read these:**
> - **5 min**: Executive summary (`.traces/vision/<Slug>-summary.md`) — the board-meeting briefing
> - **15 min**: Add the propositions (`.traces/vision/<Slug>-propositions.md`) — see what we could build
> - **30 min**: Add the whitepaper (`.traces/vision/<Slug>-whitepaper.md`) — understand the deeper argument
> - **60 min**: The full analysis (`.traces/research/<slug>/0{N+1}-*-analysis.md`) — every detail, every number, every tradeoff

### Technical mode delivery example:

> **📋 Analysis complete!** (N researchers, technical synthesis)
>
> | Deliverable | File | Size |
> |------------|------|------|
> | Technical Propositions | `.traces/vision/<Slug>-propositions.md` | ~300 lines |
> | Whitepaper | `.traces/vision/<Slug>-whitepaper.md` | ~400 lines |
>
> **💡 Key recommendation:** [one-line summary]
>
> **📊 All research files:**
> *(list all N research files with line counts)*
>
> **📄 How to read these:**
> - **10 min**: Propositions (`.traces/vision/<Slug>-propositions.md`) — see what we could build
> - **20 min**: Whitepaper (`.traces/vision/<Slug>-whitepaper.md`) — understand the deeper argument
> - **Browse**: Research files in `.traces/research/<slug>/` — raw data and evidence

---

## Error Handling

- If a research agent fails or produces an empty file, relaunch it once
  with the same prompt
- If the analysis agent produces fewer than 800 lines for the full report,
  resume it with instructions to expand thin sections
- If the executive summary is missing or under 100 lines, resume the agent
  with instructions to write/expand it
- If the technical agent produces an empty propositions or whitepaper file,
  resume it with instructions to complete the missing artifact
- If the user's topic is too vague, ask one clarifying question before
  launching research (use AskUserQuestion)

---

## Customization

### Inline parameters (parsed from $ARGUMENTS)
- **`agents:N`** — Number of research agents to launch (default: 4). Min: 2, max: 8.
- **`synthesis:full|technical`** — Synthesis mode (default: full). `technical` skips analysis report and executive summary, produces only propositions + whitepaper.

### Natural language modifiers (in the topic string)
- **Focus area**: "focus on security implications" — weight angle 2 toward security
- **Audience**: "for engineering team only" — adjust tone to be more technical, less business
- **Depth**: "quick overview" — equivalent to `agents:2 synthesis:technical`
- **Comparison**: "compare X vs Y" — restructure angles around the two options
