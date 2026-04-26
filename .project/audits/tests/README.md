# Test Audit Reports

Updated on 2026-04-24 from the latest full multi-suite test audit.

## Overall state

- Total collected: 4761
- Passed: 4397
- Failed: 328
- Errors: 5
- Skipped: 7
- Not run: 24 (frontend Playwright)

## Current report set

- `./README.md`
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

- Framework package backend suites are green.
- The largest regression surfaces are currently:
  - grants auth/users routing
  - frontend transport/runtime (`Socket`, `NetworkAdapter`, `NTT`, `DynamicClass`)
  - form/method/navigation UI contract drift
  - Veille bool deserialization and shell navigation regressions
- The comprehensive per-failure catalog now lives in `./full-test-failure-audit-2026-04-24.md`.
