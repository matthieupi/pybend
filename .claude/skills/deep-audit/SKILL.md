---
name: deep-audit
description: Comprehensive subsystem audit. Maps all components, analyzes architecture, surfaces bugs and risks, evaluates extensibility. Produces multi-resolution report usable for bug hunting, feature development, integration planning, and refactoring.
argument-hint: "<subsystem> [depth:quick|deep]  e.g. 'actor', 'tx depth:quick', 'agents', 'storage', 'schema pipeline'"
---

# Deep Audit: Comprehensive Subsystem Analysis

You are a senior systems architect performing a thorough audit of a subsystem.
Your goal is to disassemble every component, understand all design decisions,
surface risks, and produce a multi-resolution report that serves as the
foundation for multiple downstream activities: bug hunting, feature development,
integration planning, and refactoring.

**Raw arguments:** $ARGUMENTS

## Argument Parsing

Parse `$ARGUMENTS` to extract:
- **Subsystem**: The subsystem or component to audit (e.g., "actor", "tx",
  "agents", "storage", "schema")
- **Depth** (optional): `depth:quick` or `depth:deep` (default: **deep**)
  - `quick` — 2 analysis agents, condensed reports (~300-500 lines each)
  - `deep` — 4 analysis agents, comprehensive reports (~500-800 lines each)

If no subsystem is provided, ask the user what they'd like to audit.

---

## Phase 1: Scope Discovery

Before launching any agents, discover the subsystem boundary yourself using
Glob and Grep. This is fast and gives you the file list needed for agent prompts.

### Step 1: Find core files

Search for files belonging to the subsystem using multiple strategies:

```
Glob: **/*<subsystem>*/**/*.py
Glob: **/*<subsystem>*/**/*.js
Glob: **/*<subsystem>*.py
Glob: **/*<subsystem>*.js
```

Also search for the subsystem in directory names, class names, and module names.
Cast a wide net — it's better to include a false positive than miss a real file.
Exclude `node_modules/`, `.git/`, `__pycache__/`, `*.egg-info/` directories.

### Step 2: Find usage sites

Search for imports and references across the entire codebase:

```
Grep: import.*<subsystem>|from.*<subsystem>
Grep: <KeyClassName>  (identified from reading core files)
```

This reveals how other parts of the codebase depend on and interact with the
subsystem. Focus on imports, type hints, function calls, and inheritance.

### Step 3: Read key files

Read a few of the most central files (the main module, the __init__.py, the
primary class) to understand the subsystem's shape. Also read CLAUDE.md and
relevant sub-documents (claude-back.md, claude-front.md) for architectural
context that analysis agents will need.

### Step 4: Confirm scope with user

Present the discovered scope:

> **Subsystem: `<subsystem>`**
>
> **Core files** (N files):
> - `path/to/file1.py` — brief role description
> - `path/to/file2.py` — brief role description
> - ...
>
> **Key classes/functions**: `ClassName`, `function_name`, ...
>
> **Usage sites** (M files reference this subsystem):
> - `path/to/consumer1.py` — how it uses the subsystem
> - ...
>
> **Depth:** deep (4 dimensions) / quick (2 dimensions)
> **Output:** `.traces/audits/<subsystem>/`
>
> Proceed with audit?

Wait for user confirmation. They may adjust the scope (add/remove files) or
change the depth setting.

---

## Phase 2: Parallel Analysis

Create the output directory: `.traces/audits/<subsystem>/`

### Common Agent Instructions

Every analysis agent receives this preamble in its prompt:

```
You are performing a deep audit of the "<subsystem>" subsystem in the
<project-name> codebase. Your job is to read every relevant file, analyze it
thoroughly, and write a structured report.

## Project Context
<paste relevant sections from CLAUDE.md and sub-documents>

## Core Files — READ ALL OF THESE
<full file list from Phase 1>

## Usage Sites — READ RELEVANT ONES
<usage site list from Phase 1>

## Rules
- Read EVERY core file listed above. Do not skip any.
- For each claim, cite the specific file:line_number.
- Use tables, code snippets, and ASCII diagrams for clarity.
- Be specific and concrete — no vague generalities.
- If you find a bug or risk, show the exact code.
- Do not launch sub-agents. Do not modify any source code.
- Structure your report with clear H2/H3 headings for each topic.
- Consider the project's design philosophy when evaluating — judge against
  the project's own principles, not abstract best practices.
```

### Deep Mode (default) — 4 parallel agents

Launch **4 parallel agents** using `subagent_type: "general-purpose"` in a
**single message** (all 4 tool calls together).

---

#### Agent 1: Architecture & Design Patterns

**Output:** `.traces/audits/<subsystem>/01-architecture.md`

Analyze the subsystem's structural design:

- **Component inventory**: Every class, function, and module with a one-line
  role description. Organize as a table.
- **Responsibility map**: What each component does, WHY it exists, and what
  would break if it were removed.
- **Design patterns**: Name the patterns used (Observer, Strategy, Proxy,
  Metaclass, Mixin, etc.). For each: where it's applied, why it was chosen,
  and whether it's the right choice.
- **Data flow**: How data enters, transforms through, and exits the subsystem.
  Include ASCII diagrams showing the primary flows.
- **State management**: Where state lives (class vars, instance vars, module
  globals, external stores), how it's mutated, and its lifecycle.
- **Coupling analysis**: Which components know about each other directly.
  Identify tight coupling (concrete references) vs loose coupling (protocols,
  events, dependency injection). Rate each relationship.
- **Cohesion assessment**: For each module — is it doing one thing well, or
  is it a grab bag? Identify any god classes or modules with mixed concerns.
- **Boundary analysis**: What's internal implementation vs public surface.
  Are boundaries enforced (private, underscore convention, `__all__`) or just
  conventional?
- **Configuration surface**: What's configurable, what's hardcoded, what
  should be configurable but isn't.
- **Error propagation**: How errors flow through the subsystem. Where are
  they raised, caught, transformed, or silently swallowed?

Target: **500-800 lines** of dense, structured analysis.

---

#### Agent 2: API Surface & Contracts

**Output:** `.traces/audits/<subsystem>/02-api-contracts.md`

Analyze every public interface and usage pattern:

- **Public API inventory**: Every public callable — parameters, return types,
  side effects, exceptions. Organize as a reference table.
- **Contracts & invariants**: For each key API — what must be true before the
  call (preconditions), what's guaranteed after (postconditions), what's
  always true (invariants).
- **Error handling contracts**: What errors can each API raise? What does the
  caller see? Are error types consistent or ad-hoc?
- **Type safety**: Where are types enforced (runtime checks, Pydantic, type
  hints)? Where are they assumed? Where do they leak (Any, untyped dicts,
  dynamic attributes)?
- **Usage patterns in the codebase**: How does the rest of the codebase
  ACTUALLY use this API? Show real code examples. Are there misuse patterns?
- **Developer experience**: Is the API intuitive? Discoverable? Consistent
  with similar APIs in the project? What surprises would a new developer hit?
- **Naming analysis**: Are names consistent, descriptive, and following
  project conventions? Any misleading names?
- **Parameter validation**: What's validated at the boundary? What's trusted?
  Where could bad input sneak through?
- **Return value contracts**: What does the caller get back? Is the shape
  always consistent, or does it vary by code path?
- **Lifecycle & ordering**: Required call sequences, initialization protocols,
  cleanup requirements. What breaks if you call things out of order?
- **Documentation gaps**: What's undocumented? What's documented but wrong
  or stale?

Target: **500-800 lines** of dense, structured analysis.

---

#### Agent 3: Quality & Risk Assessment

**Output:** `.traces/audits/<subsystem>/03-quality-risks.md`

Find every bug, risk, and quality concern:

- **Potential bugs**: Logic errors, off-by-one, null/None handling, incorrect
  assumptions. For each: show the code, explain the scenario that triggers it,
  and rate the likelihood.
- **Edge cases**: What inputs, states, or sequences could break things?
  Boundary conditions, empty collections, concurrent access, large inputs.
- **Test coverage analysis**: What's tested? What's NOT tested? What SHOULD
  be tested? Identify the highest-risk untested paths.
- **Test quality**: Are existing tests testing the right things? Are there
  assertion gaps (test runs code but doesn't verify outcomes)? Are tests
  brittle or robust?
- **Error handling gaps**: Uncaught exceptions, swallowed errors, misleading
  error messages, missing try/except blocks on I/O or external calls.
- **Security considerations**: Injection risks, auth bypass potential,
  privilege escalation, data exposure, unsafe deserialization.
- **Performance risks**: O(n^2) algorithms, unbounded allocations, blocking
  calls in async context, missing caching opportunities, N+1 query patterns.
- **Concurrency issues**: Shared mutable state, race conditions, async
  pitfalls, deadlock potential, missing locks or synchronization.
- **Resource management**: File handles, connections, memory — are they
  properly opened/closed? Any leak potential?
- **Technical debt inventory**: TODO/FIXME/HACK comments, workarounds,
  deprecated patterns, copy-paste duplication.
- **Failure modes**: What happens when dependencies fail? Is there graceful
  degradation or catastrophic failure? What's the blast radius?

Target: **500-800 lines** of dense, structured analysis.

---

#### Agent 4: Extensibility & Integration

**Output:** `.traces/audits/<subsystem>/04-extensibility.md`

Analyze how the subsystem connects, extends, and evolves:

- **Extension points**: Where and how can new functionality be added WITHOUT
  modifying existing code? List each point with: mechanism (subclass,
  plugin, hook, config), difficulty (easy/moderate/hard), example.
- **Integration boundaries**: How this subsystem connects to every other
  subsystem. For each boundary: what crosses it (data format, protocol,
  function calls), coupling strength, and stability.
- **Dependency graph**: What this subsystem depends on (inbound) and what
  depends on it (outbound). Include an ASCII dependency diagram.
- **Data contracts at boundaries**: What format/structure crosses each
  boundary? Are contracts explicit (typed) or implicit (convention)?
- **What's easy to change**: Modifications that the current design supports
  naturally. Things you can do in under an hour.
- **What's hard to change**: Modifications that require significant
  restructuring. Things that fight the current architecture.
- **Constraints & limitations**: Fundamental limitations of the current
  design that cannot be fixed without a rewrite.
- **Feature integration guide**: Step-by-step guide for adding a new feature
  that touches this subsystem. What files to modify, what patterns to follow,
  what tests to add, what to watch out for.
- **Comparison with alternatives**: Are there simpler or better-known designs
  for the same problem? How does the current approach compare? What would a
  migration look like?
- **Evolution trajectory**: How has this subsystem changed over time (check
  git history)? What direction is it heading? Is the trajectory sustainable?
- **Cross-cutting concerns**: How does this subsystem interact with logging,
  error handling, configuration, authentication, serialization?

Target: **500-800 lines** of dense, structured analysis.

---

### Quick Mode — 2 parallel agents

Launch **2 parallel agents** using `subagent_type: "general-purpose"` in a
**single message**.

#### Agent 1: Architecture & API (combines dimensions 1+2)

**Output:** `.traces/audits/<subsystem>/01-architecture-api.md`

Cover all topics from the Architecture and API dimensions above, condensed.
Target: **400-600 lines**.

#### Agent 2: Quality & Extensibility (combines dimensions 3+4)

**Output:** `.traces/audits/<subsystem>/02-quality-extensibility.md`

Cover all topics from the Quality and Extensibility dimensions above, condensed.
Target: **400-600 lines**.

---

**Wait for all analysis agents to complete before proceeding.**

---

## Phase 3: Synthesis

Once all analysis reports are written, verify they exist and show the user
a brief status:

> Analysis complete (`.traces/audits/<subsystem>/`):
> - `01-architecture.md` — N lines
> - `02-api-contracts.md` — N lines
> - `03-quality-risks.md` — N lines
> - `04-extensibility.md` — N lines
>
> Synthesizing final audit...

Launch **1 synthesis agent** using `subagent_type: "general-purpose"`.

**Output:** `.traces/audits/<subsystem>/0{N+1}-<subsystem>-audit.md`
(where N = number of analysis files: 4 for deep, 2 for quick)

The synthesis agent's prompt:

```
You are synthesizing a comprehensive audit of the "<subsystem>" subsystem.
Read ALL analysis reports listed below, cross-reference findings, resolve
contradictions, and produce a single unified audit document.

## Analysis Reports to Read
<list all analysis file paths>

## Project Context
<relevant CLAUDE.md sections>

## Output Structure

Write the final audit to: <output path>

The document MUST follow this exact structure:

# <Subsystem> — Deep Audit Report

## Executive Summary
3-5 paragraphs: what this subsystem does, how well it does it, the most
important findings, and the top 3 recommendations. A reader should be able
to stop here and know the key takeaways.

## Component Overview
Consolidated component map with relationships. ASCII diagram of the full
subsystem showing all components and their connections.

## Key Findings

### Critical Issues
Issues that could cause bugs, data loss, security problems, or silent
incorrect behavior. Each entry:
- **Finding**: one-line description
- **Evidence**: file:line reference and code snippet
- **Severity**: Critical / High / Medium
- **Recommendation**: specific fix or investigation needed

### Design Strengths
What the current design does well. Important for knowing what NOT to
change during refactoring. Each entry with evidence.

### Design Trade-offs
Intentional trade-offs: what was gained, what was sacrificed, and whether
the trade-off still makes sense given current requirements.

### Improvement Opportunities
Non-critical improvements ranked by impact/effort ratio. Table format:
| # | Improvement | Impact | Effort | Category |

## Downstream Use Guide

### For Bug Hunting
- Known risk areas ranked by probability of containing bugs
- Untested edge cases with specific scenarios to test
- Suggested test cases to write (function names and what they verify)

### For Feature Development
- Extension points with difficulty ratings and examples
- Patterns to follow (cite existing code as templates)
- Constraints to be aware of before starting
- Common pitfalls when modifying this subsystem

### For Integration Planning
- All integration boundaries with data contracts
- Dependencies and their stability assessment
- Impact analysis checklist: what to verify when changing this subsystem
- Compatibility considerations for connecting new subsystems

### For Refactoring
- Technical debt items ranked by severity and coupling risk
- Suggested refactoring sequence (dependency order — what to change first)
- Risk assessment for each proposed change
- Before/after sketches for major refactoring candidates

## Appendix: Complete Finding Index
Table of ALL findings across all dimensions:
| ID | Dimension | Severity | Finding | File(s) | Status |

## Rules
- Cross-reference findings across dimension reports — if Architecture and
  Quality both flag the same area, consolidate into one finding.
- Resolve contradictions: if one report says X is good and another says X
  is risky, investigate and take a position.
- Every finding must have a file:line citation.
- The Downstream Use Guide sections must be ACTIONABLE — a developer should
  be able to pick up any section and start working immediately.
- Target: 800-1200 lines for the complete document.
```

**Wait for the synthesis agent to complete.**

---

## Phase 4: Delivery

After the final audit is written, verify it exists and report:

### Deep mode delivery:

> **Deep Audit Complete: `<subsystem>`**
>
> | Deliverable | File | Lines |
> |------------|------|-------|
> | Architecture & Design | `01-architecture.md` | N |
> | API & Contracts | `02-api-contracts.md` | N |
> | Quality & Risks | `03-quality-risks.md` | N |
> | Extensibility | `04-extensibility.md` | N |
> | **Final Audit** | `05-<subsystem>-audit.md` | N |
>
> **Top 3 findings:**
> 1. [most critical finding — one line]
> 2. [second finding — one line]
> 3. [third finding — one line]
>
> **How to use this audit:**
> - **5 min**: Executive Summary in the final audit — big picture and key decisions
> - **15 min**: Key Findings — what needs attention now
> - **30 min**: Downstream Use Guide — actionable next steps for your specific goal
> - **Deep dive**: Individual dimension reports — every detail with file:line refs
>
> **Next steps:** Use these findings with `/bugfix`, `/ideation`, or
> `/gsd:plan-phase` to act on specific recommendations.

### Quick mode delivery:

> **Deep Audit Complete: `<subsystem>`** (quick mode)
>
> | Deliverable | File | Lines |
> |------------|------|-------|
> | Architecture & API | `01-architecture-api.md` | N |
> | Quality & Extensibility | `02-quality-extensibility.md` | N |
> | **Final Audit** | `03-<subsystem>-audit.md` | N |
>
> **Top 3 findings:**
> 1. [most critical finding — one line]
> 2. [second finding — one line]
> 3. [third finding — one line]

---

## Error Handling

- If the subsystem name matches no files, search for partial matches and
  similar names in the codebase. Suggest alternatives and ask the user to
  pick one.
- If an analysis agent produces an empty or very short file (< 100 lines),
  resume it with instructions to expand, citing which sections are missing.
- If the synthesis agent produces fewer than 600 lines, resume it with
  instructions to expand the Downstream Use Guide and Finding Index.
- If the user's subsystem description is ambiguous (e.g., "model" could mean
  ProtoModel, ActorModel, or data models), ask one clarifying question using
  AskUserQuestion before proceeding.
- If an agent fails entirely, relaunch it once with the same prompt.

---

## Quality Standards for All Reports

These are embedded in every agent prompt:

1. **Read the code, don't guess.** Every claim must cite file:line.
2. **Be concrete.** "The error handling is weak" is useless. "In actor.py:142,
   `send()` catches Exception but logs nothing — a failed message is silently
   dropped" is useful.
3. **Show, don't tell.** Include code snippets for bugs, patterns, and examples.
4. **Quantify when possible.** "3 of 7 public methods lack input validation"
   beats "some methods lack validation."
5. **Distinguish fact from opinion.** "This IS a bug" vs "This COULD be a bug
   under condition X" — be explicit about certainty level.
6. **Judge against the project's own philosophy.** Read CLAUDE.md. Evaluate
   against the project's stated principles, not generic best practices from
   a textbook.
7. **Think about the reader.** Someone will use this report to find bugs, plan
   features, or execute a refactor. Every section should be directly actionable.
