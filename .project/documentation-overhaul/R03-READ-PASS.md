# R03 Bounded Current-Guide Read Pass

Date: 2026-10-19. Scope: the exact 59 paths in the incoming `REMAINING.txt`.

## Coverage

All **59 guides were read directly in full**, from line 1 through the explicit
end-of-file line reported by Read. Each was a separate untruncated Read result,
grouped in manageable parallel batches. No rendered historical batch, grep hit,
head/tail sample, writer report or hash calculation received full-read credit.
The three long JSONL lines in build-feature were visible without line truncation.

`CURRENT-REVIEWS.json` records each path, exact complete range, SHA256 and
individual value/presentation/correctness/completeness assessment. Hashes were
obtained with `sha256sum` after reading; inventory regeneration independently
compares them with current bytes and line counts. The existing ten R02 entries
were preserved, not claimed as new R03 reads.

| Category | Count | Meaning |
|---|---:|---|
| Newly read in full by R03 | 59 | Independent complete current-guide text reads |
| Existing R02 current reads | 10 | Preserved revision-pinned prior evidence |
| Current guides reviewed, combined | 69 | Full text coverage, not runtime certification |
| Current guides pending | 0 | At regeneration; changed hashes reopen review |
| Writer reported | 53 | Separate attribution, not R03 independent reads |
| Historical/generated reference | 55 | Classification, not substantive full review |
| Generated package metadata | 24 | Classification, not substantive full review |
| Non-guide | 7 | Separate classification |
| Total inventoried | 208 | Never a claim of 208 substantive reviews |

All `.project` source material remains excluded. Audit outputs live here solely
as evidence. No source documentation, runtime, dependency, ledger, `t02e*` file or
`verify_tutorial.py` was edited. No external requests, installs, commits or
environment changes were performed.

## Editor Findings

These findings remain **unfixed**. Full reading does not mean approval of the
text. Per-path assessments include additional lower-priority presentation notes.

### R03-01: Widget Example Violates Runtime Interface

Priority: high. `.opencode/skills/n3tx-widgets/SKILL.md:38-47` returns
`outerHTML` strings from `display` and `edit`. Formidable calls
`widgetEl.querySelector` and `appendChild`, so the example cannot render through
that path. The second `edit` argument is config, not a field name.

Source evidence: `packages/n3tx-ui/src/n3tx_ui/static/widgets/Widget.js:14-49`
specifies Node returns for display/edit, string for list;
`packages/n3tx-ui/src/n3tx_ui/static/generators/form.js:325-348` consumes nodes.
Return the DOM nodes, use the actual signature, and demonstrate safe list output
as well: inherited `Widget.list` merely stringifies values. The existing note
about listeners lost during Formidable serialization remains useful. This is a
source-established mismatch, not an executed browser reproduction.

### R03-02: Commit Workflow Can Include Unapproved Changes

Priority: high. `.agents/prompts/git-smart.md:120-126` and
`.opencode/commands/git-smart.md:122-128` tell the agent to assign whole mixed
files to the dominant group, contradicting their ownership-clarification
preambles. The execute phase stages selected paths then commits the entire
index without a gate for pre-existing unrelated staged paths.

Remove auto-assignment and require explicit ownership/index reconciliation before
each commit. Do not unstage or overwrite another contributor's work implicitly.
Replace fixed attribution/obsolete scope templates rather than relying solely on
an introductory override.

### R03-03: Validation Testing Guidance Is Unsound

Priority: medium. `.agents/agents/test-writer.md:240-242` advises skipping cases
that Python's type system or Pydantic will catch. Python annotations do not
enforce runtime argument types, and schema-driven boundary tests must verify
that validation is actually invoked. Preserve invalid-input integration tests.
Line 293 also uses unspecified `python`, contrary to approved interpreter and
isolated suite guidance. Lines 209-212 overgeneralize instance patch limitations
to all Pydantic mocking; distinguish class/instance/config cases.

### R03-04: Ideation Links And Run Isolation Are Inconsistent

Priority: medium. `.agents/agents/ideation-agent.md:240` links to an unnumbered
analysis filename, whereas the orchestrator generates `05-...` or another
numbered prefix. Line 180's research-relative example also resolves to the wrong
directory from the declared analysis location. Pass exact output paths and
derive relative links.

`.agents/skills/research/ideation/SKILL.md:102-106` claims each run avoids
collisions but uses only topic slug, so repeated same-topic runs share files.
Lines 197-224 launch summary and analysis concurrently without reconciliation,
although summary presents itself as a summary of that full analysis. Snapshot
research inputs, specify overwrite/run identity policy, and reconcile outputs.

### R03-05: Bugfix Gates Contradict Their Procedure

Priority: medium. `.agents/prompts/bugfix.md:25` requires three test files while
lines 42-69 require three tests. Read-only diagnosis at lines 93-95 permits
temporary source print edits at 111-112. Full-suite validation examples at
237-242 only select three backend suites. Use one consistent minimum meaningful
reproduction rule, qualify diagnostic edits, and report actual selected coverage.
Passing regression controls need not be rewritten merely to force every test red.

### R03-06: Partial Feature Tasks Lack Dependency Gates

Priority: medium. `.agents/prompts/build-feature.md:291-294,359-360` permits
skipping failed tasks or accepting partial results without blocking consumers of
their unmet outputs. Require dependency acceptance before downstream scheduling.
Lines 248-257 also refer to branch merging while the executor prohibits commits;
specify whether and how uncommitted worktree changes are integrated. The existing
checkout adaptation correctly labels legacy paths as templates, not commands.

### R03-07: Performance Advice Needs Measurement And Bounds

Priority: medium. `.agents/agents/perf-audit-frontend.md:19` assumes one reflow
per append; browsers can batch layout unless synchronous layout is forced.
`.agents/skills/perf/perf-analysis/SKILL.md` distinguishes static hypotheses but
does not require a controlled before/after benchmark before claiming improvement.
Its unbounded `lru_cache(maxsize=None)` advice at 113 needs key-space/memory
limits, and arbitrary pool sizing/startup exclusions at 137-139 are not universal.

### R03-08: Non-Reproduction Does Not Prove A Stale Report

Priority: medium. `.agents/prompts/fix-test.md:64` and
`.agents/skills/dev/fix-test/SKILL.md:65` declare the audit stale if the failure
does not reproduce. Use not-reproduced/unresolved status and record environment,
ordering and intermittent-failure limitations. Preserve the rule not to invent
a fix; do not falsely disprove a report from one successful run.

### R03-09: Source-Reading Policies Conflict

Priority: medium. `.opencode/skills/README.md:38`,
`n3tx-skill-routing/SKILL.md:20-21`, `n3tx-principles/SKILL.md:55` and several
specialist skills prohibit source inspection unless docs are insufficient.
`AGENTS.md` requires inspecting current implementation/tests before meaningful
changes; principles itself repeats that at line 93. Use docs first, then relevant
source/tests for implementation. A docs-first policy is not a docs-only policy.

Affected R03 specialist entries: actors, authorization, frontend, methods-routes,
testing, UI-components, UI-schema and widgets. Other prior-reviewed specialist
skills were not independently reread in this pass.

### R03-10: Protected-Field Contract Is Overstated

Priority: medium. `.opencode/skills/n3tx-authorization/SKILL.md:69` generalizes
auto-injection to every protected field. Direct creation only injects
`user_owner` when protected and authenticated `user_id` is truthy
(`packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py:93-99`); update strips
all protected fields (`197-200`). Application-defined protected names do not
automatically receive server-owned values on create.

The same line and `n3tx-ui-schema/SKILL.md:38` say hidden in edit forms, but
Formidable `getInput:297-298` changes edit to display-only. Describe read-only
presentation accurately and distinguish create/update/transport behavior.
Service-token acceptance wording at authorization lines 100-104 also needs scope:
`backend.py:169-209` processes `x-access-token` before the service-header branch.

## Other Editorial Notes

- Research/audit line-count and source quotas should permit an honest
  insufficient-evidence result, rather than demanding padding or false precision.
- Distill and distill-deep have the same operational body; define a meaningful
  depth distinction or consolidate with an intentional invocation migration.
- `prd-to-issue` requests comments but should show `gh issue view --comments`.
- PRD/refactor templates need explicit success/acceptance criteria and should
  allow revision-qualified source references instead of banning all paths.
- Handoff's literal Markdown template nests equal-length fences; use a longer
  outer fence. Replace fixed workspace values with discovered paths.
- TDD support examples are conceptual, not runnable complete TypeScript/Jest;
  clarify that and avoid blanket bans on persistence/exactly-once observations.
- Pi alias behavior matches inspected implementation. Its git-status/bugfix
  examples describe possible installations, not the current shared prompt tree.

## Verification Boundaries

Source spot-checks were targeted, not full-package reviews. In addition to the
code cited above, this pass read Pi `index.ts` and `skill-aliases.mjs` fully,
frontend `package.json` fully, and NTTElement lines 1-180; class inheritance and
widget call sites were searched. These partial source reads are **not** included
in the documentation full-read count.

Inventory/check regeneration validates hashes, exact ranges and accounting, not
the absence of substantive defects. Runtime/backend/frontend/browser/provider
suites and live harness discovery were not run. The other writer owns browser,
link and tutorial verification artifacts; they were not changed here.

Executed checks:

- `inventory.py` regeneration and `inventory.py --check`: passed, 69 exact-hash
  full-current reads, zero pending; `REMAINING.txt` directly read as empty.
- `closing_checks.py` regeneration and `closing_checks.py --check`: passed,
  557 scanned local inline links, zero flagged issues. Generic workflow templates
  are excluded by this scanner, so this does not negate R03-04's template defects.
- `git diff --check -- .project/documentation-overhaul`: returned success, but
  the directory is untracked, so this is not a whitespace validation of its new
  contents. JSON validity and coverage were validated by inventory/check scripts.

Regenerated outputs: `INVENTORY.jsonl`, `SCOPE.json`, `REMAINING.txt`,
`CHANGED-FILES.json`, `CLOSING-CHECKS.json`. The changed-file manifest describes
the aggregate existing documentation work, not changes attributable to R03.
