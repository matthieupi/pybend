# n3tx-actors Test Audit

## Result

- Status: passing
- Command: `.venv/bin/python -m pytest packages/n3tx-actors/src/n3tx_actors/tests/`
- Outcome: 630 passed

## What changed during execution

- Initial run failed widely because async tests were collected without `pytest-asyncio`.
- After installing `pytest-asyncio`, the full actors package suite passed cleanly.

## What this means

- Actor routing, proxies, interceptors, auth interception, CRUD dispatch, and streaming tests are green.
- The failures were environmental, not package regressions.

## Notable warnings

- Unknown `pytest.mark.unit` markers are not registered.
- Some tests emit coroutine-not-awaited runtime warnings in mocked lifecycle paths.
- Pydantic v2 deprecation warnings still apply through shared core code.

## Assessment

- Package health is good.
- The main follow-up is test-hygiene cleanup for warnings, not correctness fixes.
