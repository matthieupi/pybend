# examples/core Test Audit

## Result

- Status: failing
- Command: `.venv/bin/python -m pytest examples/core/tests/`
- Outcome: 416 passed, 16 failed, 1 error

## Failure groups

### Browser E2E failures

- A large portion of failures come from Playwright-based E2E tests.
- Chromium was installed successfully, but the browser cannot launch because the host is missing `libnspr4.so`.
- Affected files include:
  - `examples/core/tests/e2e/test_comment.py`
  - `examples/core/tests/e2e/test_like_favorite.py`
  - `examples/core/tests/e2e/test_method_click_propagation.py`
  - `examples/core/tests/e2e/test_shadow_dom_card_navigation.py`
  - `examples/core/tests/e2e/test_shadow_dom_click_propagation.py`
  - `examples/core/tests/e2e/test_streaming.py`

### Non-E2E assertion failures

- `examples/core/tests/test_comment_model.py`
  - Like/unlike response format assertions fail.
  - Tests expect simple action payloads such as `{"action": "liked"}`.
  - Actual responses include richer object payloads with fields like `_field`, `id`, `user`, and `created_at`.
- `examples/core/tests/test_product_model.py`
  - Favorite/unfavorite response format assertions fail for the same reason.

## What this means

- Most of the example's API and integration behavior is healthy.
- There are two active non-browser contract mismatches around like/favorite response shape.
- The rest of the red surface is blocked by missing system browser libraries rather than application logic.

## Recommended next actions

1. Install Playwright runtime dependencies, starting with `libnspr4`.
2. Decide whether the richer like/favorite response is the new intended contract.
3. Update either the handlers or the tests in `examples/core/tests/test_comment_model.py` and `examples/core/tests/test_product_model.py` to align on that contract.
