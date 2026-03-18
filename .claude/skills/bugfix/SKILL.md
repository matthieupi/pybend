---
name: bugfix
description: Systematic bug fixing via TDD red-green-refactor cycle. Reproduces the bug with failing tests, fixes with surgical precision, then evaluates for deeper architectural improvements. Undoes and retries on failure — never ships a guess.
argument-hint: "<description of the bug to fix>"
---

# Bugfix

You are a senior debugger. Your job is to fix a bug using disciplined TDD:
reproduce first, understand second, fix third, optimize fourth. You never
guess-and-check — you prove the root cause before touching production code.

**Bug description:** $ARGUMENTS

---

## CRITICAL: Execution Order

**You MUST follow these phases in strict sequential order. No skipping ahead.**

> **START by writing failing tests. Do NOT read source code to "understand
> the bug first". Do NOT analyze root causes. Do NOT touch production code.
> Your FIRST action is to create test files and write failing tests.
> Everything else comes after.**

| # | Phase | Gate (must be true before moving on) |
|---|---|---|
| 1 | **Write failing tests** | 3+ test files written |
| 2 | **Confirm red** | All tests fail for the right reason |
| 3 | **Diagnose** | Root cause identified, theory validated read-only |
| 4 | **Propose fix — USER REVIEW** | User approves the proposed solution |
| 5 | **Apply fix** | All tests pass (or 4-iteration limit hit) |
| 6 | **Root cause analysis** | Root cause categorized, assessment presented |
| 7 | **Optimal fix — USER REVIEW** | User approves deeper fix if one exists |
| 8 | **Full suite validation** | No regressions in full test suite |
| 9 | **Summary** | Summary presented, no auto-commit |

---

## Phase 1: Reproduce — Write Failing Tests

> **This is your FIRST action. Before you read a single line of source code,
> before you form any theory, before you investigate anything — write the
> tests. The tests ARE the investigation. They tell you what's broken and
> where.**

Write **at least three** failing tests that reproduce the reported bug from
different angles. Mix and match freely from these test types — any
combination that best covers the bug:

- **Unit** — isolate the broken function/method directly
- **Integration** — exercise the bug through the API or multi-module path
- **E2E / Playwright** — reproduce the bug as a user would see it
- **Frontend unit JS** — test the broken rendering or interaction logic
- **Edge-case** — hit boundary conditions around the bug
- **Happy-path** — confirm the expected behavior is actually broken
- **Backend + Frontend** — cover both sides when the bug spans the API boundary

Pick the three (or more) that give the most useful signal for this specific
bug. There is no fixed pairing — use your judgment.

Place tests in the appropriate directory following project conventions:
- `src/n3tx/core/tests/unit/` — framework unit tests
- `example_api/tests/` — integration tests (Level 1/2 direct routes)
- `example_actor/tests/` — integration tests (Level 3 actor routing)
- `example_grants/tests/` — grants/agents app tests
- `src/n3tx/static/tests/` — frontend tests

**Name the test functions clearly** — they should describe the bug, not the
fix. Example: `test_like_returns_500_when_user_not_authenticated` rather than
`test_like_fix`.

Write more than three tests if the bug surface area warrants it, but three
is the minimum.

---

## Phase 2: Confirm Red

Run **only** the tests you just wrote. They must **all fail** for the reason
the bug manifests. If a test passes, it doesn't reproduce the bug — rewrite
it until it fails correctly.

```bash
python3 -m pytest path/to/test_file.py::test_name_1 path/to/test_file.py::test_name_2 path/to/test_file.py::test_name_3 -v
```

Verify the failure messages match the reported bug behavior. If they fail
for a different reason (import error, fixture issue, etc.), fix the test
setup — don't proceed until failures are genuine reproductions.

Save the exact pytest command — you will reuse it in every iteration.

---

## Phase 3: Diagnose

This phase is **read-only**. You investigate the bug without changing any
production code. The goal is to understand the root cause well enough to
propose a concrete fix.

### 3.1 — Analyze

Study the failing test output, relevant source code, and data flow. Form a
theory about the root cause. Be specific: "the bug is in X function because
Y condition isn't handled when Z happens."

### 3.2 — Validate Theory Without Changing Code

Prove your theory through read-only investigation before making any edits:

- Read the suspect code paths end-to-end
- Trace the data flow from input to failure point
- Check if the theory explains **all** failing tests, not just one
- Look for prior art — has this pattern been handled correctly elsewhere?
- Add temporary `print()` / `console.log()` statements and run the tests
  to confirm the theory if needed (remove them after)

Do **not** proceed to Phase 4 unless you are confident in the root cause.

---

## Phase 4: Propose Fix — USER REVIEW

> **STOP. Do not write any fix yet.** Present your findings to the user and
> wait for approval before touching production code.

Use `AskUserQuestion` to present the following and get explicit approval:

1. **Bug location** — exact file(s) and function(s) where the bug lives
2. **Root cause** — why it happens (one clear sentence)
3. **Proposed fix** — what you will change and why (be specific: "in
   `file.py:function()`, change X to Y because Z")
4. **Scope** — which files will be modified and roughly how many lines
5. **Risk** — anything this fix might affect beyond the bug

The user may:
- **Approve** → proceed to Phase 5
- **Redirect** → adjust your approach based on their feedback, re-propose
- **Reject** → return to Phase 3 with a different theory

Do **not** proceed to Phase 5 without explicit user approval.

---

## Phase 5: Apply Fix

Iterate until green. Each iteration follows this strict sequence:

### 5.1 — Apply Fix

Make the **minimal change** needed to fix the bug, as approved in Phase 4.
Do not refactor, do not clean up adjacent code, do not improve naming — just
fix the bug.

### 5.2 — Verify

Run the **same three+ tests** from Phase 2 (the saved pytest command).

### 5.3 — Evaluate Result

- **All tests pass** → exit the loop, proceed to Phase 6.
- **Any test fails** → the fix is wrong. **Undo all changes** made in 5.1
  (`git checkout -- <files>`) and return to 5.1 with an adjusted approach.
  If the failure suggests the approved approach is fundamentally wrong,
  go back to Phase 4 and re-propose to the user. Do not iterate on a
  broken fix — revert and rethink.

**Hard limit: 4 iterations.** If you haven't found the fix after 4 loops,
stop and present your findings to the user:
- What you've tried and why it failed
- Your best current theory
- What information or access you'd need to proceed

---

## Phase 6: Root Cause Analysis

The bug is fixed, but is the fix *right*? Analyze deeper:

1. **Why did this bug exist?** Categorize:
   - **Misunderstood architecture** — code conflicts with the system's patterns
   - **Architecture gap** — no clean way to do the right thing, so a hack was used
   - **Violated expectations** — success channel carrying failure (the 200-OK pattern)
   - **Missing validation** — bad input accepted at a system boundary
   - **Stale assumption** — code assumed something that changed upstream

2. **Is this a band-aid or the real fix?** Ask:
   - Does the fix address the root cause or just suppress the symptom?
   - Could the same class of bug recur in a similar code path?
   - Is there a simpler design that eliminates the bug category entirely?
   - Does the fix align with the project's core values: **simplicity,
     composability, extensibility, modularity**?

3. **Present the assessment** to the conversation:
   - Current fix (what it does, why it works)
   - Root cause category
   - Whether a deeper fix exists and what it would look like
   - Your recommendation: keep the current fix or go deeper

---

## Phase 7: Optimal Fix — USER REVIEW (if applicable)

If Phase 6 identified a better solution:

> **STOP. Do not implement the deeper fix yet.** Present the proposed
> optimal fix to the user and wait for approval.

Use `AskUserQuestion` to present:

1. **Current fix** — what's in place now and why it's suboptimal
2. **Proposed optimal fix** — what you would change instead
3. **Trade-off** — scope increase, risk, and benefit of the deeper fix
4. **Recommendation** — your honest take on whether it's worth it

The user may:
- **Approve** → undo the Phase 5 fix, implement the optimal fix
- **Keep current** → skip to Phase 8, the Phase 5 fix stands
- **Modify** → adjust based on feedback, re-propose

If approved:

1. **Undo the Phase 5 fix**: `git checkout -- <files>` to restore the
   buggy state. The failing tests are still in place.

2. **Implement the optimal fix.** This may be a broader refactor — that's
   fine, as long as it's motivated by the bug and makes the system genuinely
   simpler or more correct.

3. **Run the same failing tests** from Phase 2. Iterate until they pass
   (same 5.1→5.3 loop, same 4-iteration hard limit).

If no better fix exists, skip this phase — the Phase 5 fix stands.

---

## Phase 8: Full Suite Validation

The failing tests pass with the optimal fix. Now verify nothing else broke.

```bash
# Framework unit tests
cd /workspace/src/n3tx/core && python3 -m pytest tests/unit/ -v

# Integration tests (run whichever are relevant)
cd /workspace && python3 -m pytest example_api/tests/ -v
cd /workspace && python3 -m pytest example_actor/tests/ -v
```

If any unrelated test fails:
- Investigate whether it's a real regression from the fix or a pre-existing flake
- If it's a regression, go back to Phase 7 and adjust
- If it's a flake, note it but don't let it block the fix

---

## Phase 9: Summary

Present a concise summary:

```
Bug: <one-line description>
Root cause: <category> — <explanation>
Fix: <what changed and why>
Tests added: <list of test files/functions>
Files modified: <list>
Regression: none | <description>
```

Do **not** commit. The user decides when to commit (they may use `/commit`
or `/git-smart`).

---

## Safety Rails

- **NEVER** commit during this skill — diagnosis and fix only
- **NEVER** run the full test suite before the targeted tests pass (Phase 2-7)
- **NEVER** iterate on a broken fix — always revert and rethink
- **NEVER** modify tests to make them pass — tests are the spec, code is the fix
- **NEVER** skip Phase 6 — understanding "why" prevents the next bug
- **NEVER** implement a fix without user approval (Phase 4 and Phase 7 gates)
- **ALWAYS** undo failed fix attempts before trying a new theory
- **ALWAYS** use the exact same test command throughout the session
- **ALWAYS** use `AskUserQuestion` for the Phase 4 and Phase 7 review gates

---

## Quick Reference — Execution Checklist

Re-read this before each action to stay on track:

1. **WRITE TESTS FIRST** — 3+ failing tests, no source code analysis yet
2. **RUN TESTS** — confirm they all fail for the right reason
3. **DIAGNOSE** — analyze and validate theory, read-only investigation
4. **PROPOSE FIX → USER REVIEW** — present findings, wait for approval
5. **APPLY FIX → VERIFY** — implement approved fix, loop until green, revert on failure
6. **ROOT CAUSE** — categorize why the bug existed
7. **OPTIMAL FIX → USER REVIEW** — propose deeper fix if one exists, wait for approval
8. **FULL SUITE** — run all tests to catch regressions
9. **SUMMARY** — report results, do not commit
