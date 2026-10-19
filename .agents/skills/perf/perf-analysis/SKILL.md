---
name: perf-analysis
description: Deep-dive performance audit and optimization. Launches parallel backend/frontend profiling agents, produces prioritized fix list, then implements fixes via propose-review-apply workflow with full test verification and changelog documentation.
argument-hint: "[focus: 'backend', 'frontend', or blank for full stack]"
---

# Performance Audit & Optimization

You are a performance engineer. Your job is to find and fix every bottleneck
in this codebase through a systematic 4-phase workflow.

**Focus area:** $ARGUMENTS

If no focus area is specified, audit the entire stack (backend + frontend).

---

## Phase 1: Parallel Deep-Dive Audit

Launch the custom audit agents in parallel using the Task tool (or one agent
if the user specified a single stack). Each agent has its own system prompt
with detailed audit checklists.

- **Backend**: `Task(subagent_type="perf-audit-backend", prompt="Audit this codebase's backend performance. Follow your system prompt.")`
- **Frontend**: `Task(subagent_type="perf-audit-frontend", prompt="Audit this codebase's frontend performance. Follow your system prompt.")`

Launch both in parallel for a full-stack audit. They return read-only findings;
the orchestrator saves reports under `.project/`. Separate source-based
hypotheses from benchmarks measured in a controlled environment.

After agents complete, present a combined summary of all findings to the user.

---

## Phase 2: Prioritized Task List

After both audit reports are complete, present a combined summary to the user
and synthesize findings into a prioritized task list.

Prioritize by:
1. **Impact** — How much does this affect real-world user experience?
2. **Blast radius** — How many operations/requests does this bottleneck affect?
3. **Effort** — Prefer high-impact, low-effort fixes first.

Create numbered tasks using the TaskCreate tool. Group related fixes that
touch the same file (e.g., connection pooling + WAL mode = one task).

Present the full list to the user before starting implementation.

---

## Phase 3: Propose-Review-Apply Loop

For **each task**, follow this exact workflow:

### Step 1 — Read before writing

Read every file you're about to change. Understand existing patterns, intent,
and how the change fits the architecture. Never propose changes to code you
haven't read.

### Step 2 — Propose the diff

Present the proposed changes with:
- **Problem**: What's slow and why (1-2 sentences)
- **Fix**: What the change does (1-2 sentences)
- **Diff**: Code changes in diff format with enough surrounding context
- **Behavioral impact**: "Zero behavioral changes" or describe differences
- **Measurement plan**: representative workload/data, metric and baseline;
  fixed environment/concurrency, warm-up policy and repeated runs with variance.
  Record cold-start separately when relevant; set memory/resource bounds.

### Step 3 — Wait for approval

**Do not apply changes until the user approves.** They may:
- Approve as-is — apply and test
- Request modifications — revise and re-propose
- Reject entirely — skip and move to next task
- Identify the architecture already handles it — scrub the task

### Step 4 — Apply and test

After approval:
- Apply changes using the Edit tool (surgical edits, not full rewrites)
- Add brief comments explaining **intent** (why, not what)
- Run the full test suite immediately
- Report: "N tests pass, M pre-existing failures"
- Run controlled before/after benchmarks under the same recorded conditions.
  Report timing/throughput distributions and memory/resource trade-offs, not a
  single best run. Tests prove behavior, not speed. If measurement is unavailable
  or inconclusive, label the change unmeasured/inconclusive; do not claim improvement.

### Step 5 — Mark complete and continue

Update task status and move to the next one. If tests fail, fix the root
cause — don't revert unless the approach is fundamentally wrong.

---

## Phase 4: Changelog Documentation

After all tasks are complete, create changelog entries:

1. **Detailed reports** in the project's changelog directory (one per stack)
   — Table of contents, summary table, per-fix sections with Problem/Fix/Rationale,
   file-by-file change summary, verification results

2. **Concise entries** in the main CHANGELOG.md
   — One bullet per optimization with a one-line description, linked to
   the detailed report

---

## Common Fix Patterns (Reference)

### Backend

| Pattern | When to use |
|---|---|
| Bounded `@lru_cache(maxsize=...)` | Repeated pure calls; choose capacity from measured key cardinality/value size and a memory budget; define invalidation. Unbounded only with a proven finite, budgeted key space. |
| `copy.deepcopy` on cached dicts | Callers might mutate the returned dict |
| `WHERE col IN (?, ?, ...)` | N+1 query pattern (one query per parent row) |
| Bounded connection pool | Measured connection overhead; size/test against concurrency, connection/thread rules, timeouts and DB contention, not an arbitrary constant |
| WAL mode (SQLite) | Concurrent read/write contention |
| `CREATE INDEX` on FK columns | Joins/lookups on unindexed FK columns |
| Cache key = class object | Stable, unique key (avoids name/id collisions) |

### Frontend

| Pattern | When to use |
|---|---|
| `DocumentFragment` | Candidate for batching construction; benchmark the actual rendering path |
| `AbortController` + `{signal}` | Listeners added on re-render without cleanup |
| Event delegation | Many identical listeners on sibling elements |
| `requestAnimationFrame` batching | Multiple DOM reads/writes interleaved |
| `IntersectionObserver` | Off-screen elements being rendered/computed |
| `WeakMap` / `WeakRef` | Per-object caching without preventing GC |

---

## Anti-Patterns — Do NOT

- **Don't add caching that hides bugs** — stale cache is worse than slow
- **Don't ignore startup/migrations** — measure cold-start and operational budgets;
  prioritize one-time paths when they materially affect users or availability
- **Don't break dev experience for prod perf** — no aggressive HTTP caching in dev
- **Don't pre-optimize for scale you don't have** — tune bounded resources from
  measured workloads; SQLite contention and deployment limits determine pool size
- **Don't change behavior** — same inputs, same outputs, faster
