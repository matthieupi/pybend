# examples/grants Test Audit

## Result

- Status: failing
- Command: `.venv/bin/python -m pytest examples/grants/tests/`
- Outcome: 144 passed, 12 failed, 7 errors, 1 skipped

## Failure groups

### Browser E2E failures and errors

- Playwright Chromium cannot launch because the host is missing `libnspr4.so`.
- This blocks the browser-facing suites, including:
  - `examples/grants/tests/e2e/test_agent_chat.py`
  - `examples/grants/tests/e2e/test_agent_live_first_token.py`
  - `examples/grants/tests/e2e/test_create_validation.py`
  - `examples/grants/tests/e2e/test_grant_edit.py`
  - `examples/grants/tests/e2e/test_navigation.py`

### Non-E2E failures

- `examples/grants/tests/test_agent_live_first_token.py`
  - Two failures remain outside the browser environment.
  - These indicate a real issue around streamed first-token delivery or agent-live rendering expectations.

## What this means

- The grants app backend and non-browser coverage are largely healthy.
- The main genuine regression signal is around first-token streaming behavior in the non-E2E agent-live tests.
- Most remaining red tests are blocked by missing host browser libraries.

## Recommended next actions

1. Install Playwright runtime libraries, starting with `libnspr4`.
2. Prioritize `examples/grants/tests/test_agent_live_first_token.py` as the primary real app-level failure.
3. Re-run the grants suite after environment repair to separate browser-only issues from app issues.
