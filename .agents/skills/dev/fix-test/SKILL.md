---
name: fix-test
description: Repair failing or stale tests safely by reproducing the failure, triaging whether the test still matches the intended contract, then fixing product code, tests, fixtures, or docs without regressing current behavior.
argument-hint: "<test failure, suite, file, or cluster to fix>"
---

# Fix Test

You are a senior test-recovery engineer. Your job is to fix failing tests in a
stale or drifting test suite **without accidentally regressing product code to
old behavior**.

**Test failure / cluster:** $ARGUMENTS

This skill is inspired by `/bugfix`, but it is different in one crucial way:
a failing test is not automatically proof that production code is wrong.

Every failing test or cluster must first be classified as one of:

- **Product regression** — production code no longer satisfies the current intended contract.
- **Stale test contract** — the test asserts old behavior that intentionally changed.
- **Test infrastructure issue** — failure comes from fixtures, mocks, global state, timing, environment, or harness setup.
- **Unresolved contract decision** — both the test expectation and current behavior are plausible; a human/product decision is needed.

---

## CRITICAL: Execution Order

You MUST follow these phases in strict sequential order.

| # | Phase | Gate before moving on |
|---|---|---|
| 1 | **Reproduce current failure** | Exact failing command captured; failure observed or stale audit disproven |
| 2 | **Contract triage** | Failure classified with evidence |
| 3 | **Propose solution — USER REVIEW** | User approves the exact intended diff target before any file update |
| 4 | **Apply minimal fix** | Only approved target changed |
| 5 | **Verify narrow boundary** | Original failing command passes or classification is revised |
| 6 | **Adjacent validation** | Closest related tests pass or remaining failures are classified separately |
| 7 | **Contract note + summary** | Required contract note included; no auto-commit |

Never skip Phase 2. The contract triage gate is the entire point of this skill.

---

## Phase 1: Reproduce Current Failure

Start by running the narrowest command that reproduces the reported failure.

Examples:

```bash
python3 -m pytest examples/grants/tests/test_auth_flow.py::TestLoginFlow::test_login_with_correct_credentials_returns_token -v
python3 -m pytest examples/grants/tests/test_boot.py examples/grants/tests/test_auth_flow.py -v
cd tests/frontend && npx vitest run tests/transport/Socket.test.js
cd tests/frontend && npx playwright test --config=tests/e2e/playwright.config.js tests/e2e/authentication.spec.js
```

### Requirements

- Use the repo’s expected interpreter/environment when known, e.g. `/workspace/.venv/bin/python` if system Python lacks pytest.
- Save the exact command. Reuse it throughout the fix.
- Capture the failure text, assertion, status code, stack trace, or DOM/API mismatch.
- If the reported failure no longer reproduces, stop and report that the audit is stale. Do not invent a fix.

### If no exact command is provided

Infer the narrowest reasonable reproducer from the failure description. Prefer one file or one test case before broad suites.

---

## Phase 2: Mandatory Contract Triage

Before changing anything, answer:

```text
Failing test or cluster
        |
        v
Does the test assert the current intended contract?
        |
        +-- Yes
        |     -> product regression
        |     -> fix code; preserve or strengthen the test
        |
        +-- No
        |     -> stale test / contract drift
        |     -> update test and docs; do not regress code to old behavior
        |
        +-- Unclear
              -> inspect docs, neighboring code, app behavior, and history
              -> record a contract decision before implementation
```

### Classification rubric

| Classification | Meaning | Required action |
|---|---|---|
| Product regression | Code no longer satisfies the intended current contract | Fix production code; keep or strengthen the failing test |
| Stale test contract | Test asserts old API/DOM/runtime behavior that intentionally changed | Update tests and relevant docs |
| Test infrastructure issue | Fixtures, mocks, global state, timing, stale setup, or environment caused the failure | Fix harness/fixtures/mocks first |
| Unresolved contract decision | Current behavior and test expectation are both plausible | Stop and get a decision before changing code/tests |

### Evidence checklist

Collect enough evidence to justify the classification:

| Question | Signal | Likely action |
|---|---|---|
| Does current documentation describe the test expectation? | Test matches docs | Product regression more likely |
| Does current documentation describe current implementation instead? | Test contradicts docs | Stale test more likely |
| Does neighboring runtime/app code rely on current behavior? | Current behavior is integrated | Avoid reverting code blindly |
| Does isolated rerun differ from full-suite failure? | Shared-state sensitivity | Test infrastructure issue |
| Would satisfying the test reintroduce older architecture? | Architecture regression risk | Update test or add compatibility intentionally |
| Is there no authoritative contract? | Ambiguous | Unresolved contract decision |

### Read-only diagnosis rules

During triage, you may read code, docs, audits, and test files. Do not edit
production code, test code, fixtures, or docs until Phase 3 approval.

Useful project-local references when present:

- `.project/plans/tests/contract-triage-p-1.md`
- `.project/plans/tests/test-failure-triage-action-plan.md`
- `.project/plans/tests/test-failure-triage-p0-p2-execution-plan.md`
- `.project/plans/tests/full-test-failure-audit-2026-04-24.md`

---

## Phase 3: Decision Checkpoint — USER REVIEW

STOP before editing. Once all preliminary work is complete — reproducing the
failure, identifying the failing test(s), classifying the contract, finding the
root cause, and designing the code/test/fixture/docs diff — present the
proposed solution to the user for validation.

Do **not** make any actual update to production code, tests, fixtures, or docs
until the user approves the proposed solution. This applies even when the root
cause seems obvious.

Include:

1. **Failure reproduced** — command and observed failure.
2. **Classification** — product regression, stale test, infrastructure, or unresolved.
3. **Intended contract** — what behavior should be true now.
4. **Evidence** — docs/code/tests/runtime facts supporting the classification.
5. **Root cause** — exact failing test assumption, exact code regression, or exact bug in code/fixture/harness.
6. **Proposed solution** — concrete diff shape: files, functions/classes/tests to change, and representative pseudo-diff when useful.
7. **Proposed target** — production code, tests, fixtures, docs, or stop/escalate.
8. **Scope and risk** — files likely to change and regression risks.

Do not proceed until the user approves the target. If the user redirects,
revise the classification or proposed target and ask again.

---

## Phase 4: Apply Minimal Fix

Apply the smallest fix consistent with the approved classification.

### If product regression

- Keep the failing test or add a focused regression test if needed.
- Fix production code only where the current contract is violated.
- Avoid broad refactors unless the bug is architectural and approved.

### If stale test contract

- Update the test to assert current intended behavior.
- Update docs if the contract was undocumented or stale.
- Do not change production code merely to restore old behavior.

### If test infrastructure issue

- Fix fixture scope, setup/teardown, mocks, environment, clock/timing, or global state.
- Prefer harness fixes that make tests deterministic rather than loosening assertions.

### If unresolved contract decision

- Do not implement a behavioral fix.
- Record the decision needed and stop, unless the user explicitly resolves it.

### Failed fix attempts

If the approved fix fails the narrow verification and the failure contradicts
your theory, revert the attempted changes and return to Phase 2 or Phase 3.
Do not pile additional patches on top of a wrong fix.

---

## Phase 5: Verify Narrow Boundary

Run the exact command from Phase 1.

The result must match the classification:

- Product regression → original failing test now passes.
- Stale test → updated test passes and asserts current contract.
- Infrastructure issue → test passes deterministically under the fixed harness.
- Unresolved → no behavioral fix applied; decision documented.

If it fails, classify why:

- wrong fix;
- incomplete fix;
- classification was wrong;
- adjacent failure now exposed.

Then either revise with approval or stop with findings.

---

## Phase 6: Adjacent Validation

Run the closest related tests, not the entire suite first.

Examples:

```bash
python3 -m pytest examples/grants/tests/test_boot.py examples/grants/tests/test_auth_flow.py -v
python3 -m pytest examples/grants/tests/ -v
cd tests/frontend && npx vitest run tests/transport/Socket.test.js tests/transport/NetworkAdapter.test.js
```

Only after the narrow and adjacent boundaries pass should broader suites be
run, if time and environment allow.

If adjacent tests fail, do not automatically broaden the fix. Classify the new
failure separately using Phase 2.

---

## Phase 7: Required Contract Note + Summary

Every completed cluster must include this note:

```md
Contract decision:
- Classification: product regression | stale test | test infrastructure | unresolved decision
- Intended behavior:
- Evidence:
- Changed:
  - production code: yes/no
  - tests: yes/no
  - docs: yes/no
- Regression risk:
```

Then summarize:

```md
Failure: <one-line description>
Reproducer: <exact command>
Classification: <classification>
Fix: <what changed and why>
Files modified: <list>
Verification: <commands and results>
Remaining work: <separate failures or decisions>
```

Do not commit. The user decides when to commit.

---

## Common Classification Examples

| Failure cluster | Likely classification | Reason |
|---|---|---|
| Actor route reaches storable model with `storage=None` | Product regression | Runtime route should never dispatch to an unconfigured model |
| Test expects top-level token but current debug envelope returns `data.token` | Stale test or environment drift | Response envelope may intentionally wrap method results |
| Socket tests expect legacy `sendEvent()` / `watchdog()` API but runtime is TX-native | Stale tests/docs | Reintroducing legacy API may regress architecture |
| Numeric `instances.get(1)` vs string actor addresses | Unresolved contract decision | Both database ergonomics and actor routing have plausible claims |
| Failure disappears when run isolated | Test infrastructure issue | Suite order or shared state is contaminating result |

---

## Safety Rails

- NEVER change production code before contract triage.
- NEVER update a test just to make it pass without documenting the intended contract.
- NEVER loosen assertions as a substitute for understanding the contract.
- NEVER restore old APIs or DOM structures solely because old tests expect them.
- NEVER mix unrelated clusters in one fix.
- ALWAYS save and reuse the narrow reproducer command.
- ALWAYS include the required contract note.
- ALWAYS ask for approval before applying the chosen fix target.
