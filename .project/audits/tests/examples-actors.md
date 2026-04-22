# examples/actors Test Audit

## Result

- Status: failing
- Command: `.venv/bin/python -m pytest examples/actors/tests/`
- Outcome: 427 passed, 8 failed, 11 errors

## Failure groups

### Browser E2E failures and errors

- Playwright Chromium cannot launch because the host is missing `libnspr4.so`.
- This blocks the E2E suite, including:
  - `examples/actors/tests/e2e/test_agent_chat.py`
  - `examples/actors/tests/e2e/test_comment.py`
  - `examples/actors/tests/e2e/test_like_count_update.py`
  - `examples/actors/tests/e2e/test_like_favorite.py`
  - `examples/actors/tests/e2e/test_like_user_display.py`
  - `examples/actors/tests/e2e/test_login_redirect_loop.py`
  - `examples/actors/tests/e2e/test_streaming.py`

### Non-E2E failures

- `examples/actors/tests/e2e/test_card_overflow.py`
  - Static source assertion fails because `baseStyles` template literal was not found in `ntx-method.js`.
- `examples/actors/tests/test_likes_crud.py`
  - One CRUD assertion fails outside the browser environment.

## What this means

- The actors example is broadly stable in server-side and non-browser integration coverage.
- Active actionable issues are limited once the browser dependency problem is excluded.
- There is at least one frontend source contract drift around `ntx-method.js`, plus one likes CRUD failure.

## Recommended next actions

1. Install Playwright runtime libraries so the E2E suite can actually execute.
2. Inspect `examples/actors/tests/e2e/test_card_overflow.py` versus the current `ntx-method.js` style declaration shape.
3. Triage the single failing assertion in `examples/actors/tests/test_likes_crud.py`.
