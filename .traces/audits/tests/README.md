# Test Audit Reports

Generated on 2026-04-01 from a full project test run.

## Overall state

- Total collected: 2881
- Passed: 2820
- Failed: 36
- Errors: 19
- Skipped: 6

## Reports

- `./n3tx-core.md`
- `./n3tx-actors.md`
- `./n3tx-agents.md`
- `./examples-core.md`
- `./examples-actors.md`
- `./examples-grants.md`

## Cross-cutting observations

- Framework package suites are green after installing `pytest-asyncio`.
- Browser-based example E2E tests are blocked by a missing system shared library: `libnspr4.so`.
- Example application failures that are not browser-environment related are called out in the per-package reports.
