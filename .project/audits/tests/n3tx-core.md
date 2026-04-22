# n3tx-core Test Audit

## Result

- Status: passing
- Command: `.venv/bin/python -m pytest packages/n3tx-core/src/n3tx_core/tests/unit/`
- Outcome: 1073 passed, 5 skipped

## What this means

- Core model, auth, storage, schema, route, and SSR unit coverage is currently healthy.
- No failing unit coverage was observed in the core package.

## Notable warnings

- Pydantic v2 deprecation warnings around class-based config.
- Unknown `pytest.mark.unit` markers are not registered.
- JWT tests use short secrets and trigger insecure key length warnings.

## Assessment

- The package is operationally stable from a unit-test perspective.
- Remaining work is cleanup-oriented rather than failure-driven.
