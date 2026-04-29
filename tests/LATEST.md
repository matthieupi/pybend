# Test Audit Reports

Updated on 2026-04-24 from the latest full multi-suite test audit.

## Current snapshot

| Metric | Before | Now |
|---|---:|---:|
| `P0–P2` tracked phases resolved | 0 / 3 | 3 / 3 |
| P0 tracked boundary tests passing | 24 / 37 | 37 / 37 |
| P1 tracked boundary tests passing | red contract boundary | 48 / 48 |
| P2 tracked runtime boundary tests passing | red runtime boundary | 130 / 130 |

Quick take:

- **P0 resolved** — grants users/auth actor-routing storage regression fixed
- **P1 resolved** — transport tests/docs aligned to the TX-native Socket contract
- **P2 resolved (tracked scope)** — core NTT/DynamicClass runtime boundary suites now green
- **Next biggest remaining clusters** — agent `threads` routing/bootstrap, method-response contract drift, Formidable/UI drift

## Starting state

This README originally reflected the **2026-04-24 baseline audit** before the tracked `P0–P2` recovery work landed.

- `P0–P2` tracked phases resolved: **0 / 3**
- grants users/auth actor-routing storage was still a live blocker
- frontend transport contract tests were still red
- NTT/DynamicClass runtime boundary suites were still red

## Overall state

| Metric | Starting state | Current full rerun | Latest full rerun | Post P4-P5 rerun | After P5 / latest |
|---|---:|---:|---:|---:|---:|
| Total collected | 4761 | 4708 | 4740 | 4739 | — |
| Passed | 4397 | 4459 | 4485 | 4292 | — |
| Failed | 328 | 240 | 222 | 362 | — |
| Errors | 5 | 2 | 2 | 53 | — |
| Skipped | 7 | 7 | 7 | 7 | — |
| Not run | 24 (frontend Playwright) | 24 (frontend Playwright) | 24 (frontend Playwright) | 25 | — |

Populate new columns only from a fresh full multi-suite rerun. This keeps the baseline intact while making longitudinal test progress easy to track through the refactor.

Current full rerun values were refreshed from a cross-suite rerun on 2026-04-27.

Latest full rerun values were refreshed from another cross-suite rerun on 2026-04-28. The frontend Vitest failed count includes suite/import-level red files so the longitudinal totals remain internally consistent.

Post P4-P5 rerun values were refreshed from a new cross-suite rerun on 2026-04-28. This pass exposed substantial regression in example E2E server readiness and broad browser surfaces; the frontend Vitest failed count again includes suite/import-level red files so the totals reconcile against the collected count.

## Suite-by-suite movement

| Suite | Previous rerun | Post P4-P5 rerun | Delta | Main shift |
|---|---|---|---|---|
| `packages/n3tx-core` | `1074 passed, 5 skipped` | `1074 passed, 5 skipped` | stable | no change |
| `packages/n3tx-actors` | `635 passed` | `635 passed` | stable | no change |
| `packages/n3tx-agents` | `23 failed, 122 passed` | `23 failed, 122 passed` | stable | `threads` routing/bootstrap still red |
| `examples/core` | `4 failed, 429 passed` | `4 failed, 415 passed, 14 errors` | regressed | E2E server readiness failures added on top of existing like/favorite contract drift |
| `examples/actors` | `8 failed, 438 passed` | `5 failed, 418 passed, 23 errors` | regressed | some pure test failures dropped, but broad E2E startup failures appeared |
| `examples/grants` | `20 failed, 147 passed, 1 skipped, 1 error` | `10 failed, 143 passed, 1 skipped, 15 errors` | mixed / regressed | direct failures dropped, but many E2E startup errors appeared |
| `apps/veille` Python | `7 failed, 14 passed` | `7 failed, 14 passed` | stable | bool deserialization + source fetch still red |
| `apps/veille` Node `.mjs` | `2 failed, 17 passed` | `1 failed, 18 passed` | improved | return-to-index checks mostly resolved; one grant-card render failure remains |
| Frontend Vitest | `11 failed, 1205 passed, 1 skipped, 1 error` | `11 failed, 1205 passed, 1 skipped, 1 error` | stable | remaining failures concentrated in ref-picker, profile, row, schema-bootstrap, display constants, import-level suites |
| Frontend Playwright | `138 failed, 405 passed, 24 not run` | `294 failed, 248 passed, 25 not run` | sharply regressed | widespread browser failures plus one extra not-run due to performance/visual follow-on interruption |

Interpretation:

- The **framework package backend layer** remained stable.
- The strongest regressions came from **example E2E startup/server-readiness** and **broad Playwright/browser** surfaces.
- `apps/veille` browser-style node tests improved overall, but that improvement was outweighed by the broader cross-stack regressions.

## Current report set

- `./README.md`
- `./contract-triage-p-1.md`
- `./n3tx-core.md`
- `./n3tx-actors.md`
- `./n3tx-agents.md`
- `./examples-core.md`
- `./examples-actors.md`
- `./examples-grants.md`
- `./full-test-failure-audit-2026-04-24.md`

## Coverage in the 2026-04-24 audit

- Framework backend suites
  - `packages/n3tx-core`
  - `packages/n3tx-actors`
  - `packages/n3tx-agents`
- Example applications
  - `examples/core`
  - `examples/actors`
  - `examples/grants`
- App-specific suites
  - `apps/veille` Python tests
  - `apps/veille` Node `.mjs` tests
- Frontend shared suites
  - Vitest runtime/component/integration tests
  - Playwright browser tests

## Cross-cutting observations

- Before fixing any failing test, apply `./contract-triage-p-1.md`: classify the failure as product regression, stale test contract, test infrastructure issue, or unresolved contract decision. Do not change production code solely to satisfy stale tests.
- Framework package backend suites are green.
- The largest regression surfaces are currently:
  - grants auth/users routing
  - frontend transport/runtime (`Socket`, `NetworkAdapter`, `NTT`, `DynamicClass`)
  - form/method/navigation UI contract drift
  - Veille bool deserialization and shell navigation regressions
- The comprehensive per-failure catalog now lives in `./full-test-failure-audit-2026-04-24.md`.

## Progress review — current implementation status

This section tracks progress made **after** the 2026-04-24 baseline audit. The totals above remain the historical baseline snapshot; the notes below describe what has since been fixed and what remains.

### Phase advancement against the test triage plan

| Phase | Status | Notes |
|---|---|---|
| `P-1` Contract triage | active | still the required gate before any production-code change |
| `P0` Grants users/auth actor-routing storage | ✅ done | original grants auth/bootstrap blocker fixed |
| `P1` Frontend transport contract | ✅ done | Socket/NetworkAdapter tests and docs aligned to current TX-native contract |
| `P2` NTT/DynamicClass lifecycle | ◐ partial | core runtime/lifecycle tests now mostly green, but response-contract edges remain |
| `P3` Formidable + method UI contracts | ⏳ not done | now one of the largest remaining frontend Vitest clusters |
| `P4` Router/topbar/browser polish | ⏳ not done | broad Playwright/browser-visible contract drift remains |
| `P5` Suite hardening | ⏳ not done | worker OOMs, fixture drift, and broad-suite instability remain |

### Completed since the baseline audit

#### `P0` completed

The original grants users/auth storage regression was fixed.

Previously failing grants tests that now pass include:

- `examples/grants/tests/test_boot.py::TestAppBoot::test_all_routes_accessible`
- `examples/grants/tests/test_auth_flow.py::TestRegistrationFlow::*`
- `examples/grants/tests/test_auth_flow.py::TestLoginFlow::*`
- `examples/grants/tests/test_auth_flow.py::TestCompleteFlow::*`

Root fix:

- actor-routing bootstrap now re-syncs Matrix children to the finalized registered actor model classes after storage registration, preventing stale import-time actor classes from handling requests with `storage=None`.

#### `P1` completed

Frontend transport contract cleanup is complete.

Green transport boundaries:

- `tests/frontend/tests/transport/Socket.test.js`
- `tests/frontend/tests/transport/NetworkAdapter.test.js`

Supporting docs updated:

- `docs/frontend/TRANSPORT.md`

Decision preserved:

- keep the simplified TX-native Socket contract
- do **not** restore the legacy Socket API just to satisfy stale tests

#### `P2` partially advanced

The runtime substrate is in a substantially better state than the baseline audit.

Now green:

- `tests/frontend/tests/core/NTT.test.js`
- `tests/frontend/tests/core/DynamicClassFunctor.test.js`
- `tests/frontend/tests/integration/actor-messaging.test.js`
- `tests/frontend/tests/integration/schema-bootstrap.test.js`
- `tests/frontend/tests/integration/entity-lifecycle.test.js`
- `tests/frontend/tests/integration/nested-entities.test.js`
- `tests/frontend/tests/integration/method-execution.test.js`
- `tests/frontend/tests/integration/method-response-flow.test.js`

This means transport is no longer the main frontend blocker, and core entity lifecycle behavior is much healthier than in the baseline audit.

### Current major remaining clusters

#### 1. Agent thread routing / storage bootstrap

A newly exposed backend/agent cluster is now prominent:

```text
No route to 'threads'
```

This is affecting:

- `packages/n3tx-agents` test suite
- `examples/grants` agent/chat/streaming tests
- some `examples/actors` agent streaming paths

This is now one of the highest-leverage remaining backend/runtime blockers.

#### 2. Method response contract drift (`pull` vs no-pull)

Remaining frontend integration tests disagree about whether `_response_()` should trigger a follow-up `pull()` after action responses.

Examples:

- `tests/frontend/tests/integration/method-response-pull.test.js`
- `tests/frontend/tests/integration/response-no-pull.test.js`

This remains a `P2`/contract-decision surface and should be resolved explicitly before broader UI work.

#### 3. Formidable / method / UI contract drift

The largest current frontend Vitest cluster is now centered on:

- `tests/frontend/tests/integration/form-entity-binding.test.js`
- component contract drift like `ntx-ref-picker`, `ntx-profile`, `ntx-row`
- display-mode / `Component.SIZES` contract drift

This is the clearest `P3` workstream.

#### 4. Veille regressions remain intact

Still failing:

- empty-string bool deserialization
- source fetch persistence / change detection

These remain separate from the P0/P1 work already completed.

#### 5. Broad browser-level Playwright failures remain

Playwright reruns still show broad failures in:

- authentication dropdown/favorites visibility
- authorization contract expectations
- comments/favorites/likes UI
- navigation/back-button behavior
- data-integrity and error-structure expectations

These should be revisited only after the remaining runtime/backend blockers are stabilized.

### Recommended next focus

Best next high-leverage targets, in order:

1. `threads` actor routing / storage bootstrap
2. `_response_()` contract decision (`pull` vs no-pull)
3. Formidable / method / UI contract drift

### Important note on totals

The summary numbers at the top of this file are still the **baseline 2026-04-24 audit totals**. They should not be interpreted as the current post-fix totals. Use this progress review plus fresh reruns to understand current advancement.
