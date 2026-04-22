# n3tx-agents Test Audit

## Result

- Status: passing
- Command: `.venv/bin/python -m pytest packages/n3tx-agents/src/n3tx_agents/tests/`
- Outcome: 130 passed

## What changed during execution

- Initial run failed because async tests were collected without `pytest-asyncio`.
- After installing `pytest-asyncio`, all agent package tests passed.

## What this means

- Agent actor behavior, mixin execution, streaming, thread persistence, auth propagation, and tool routing are currently green.
- The package itself does not show active regressions in its direct suite.

## Notable warnings

- Unknown `pytest.mark.unit` markers are not registered.
- Shared warnings from core remain: Pydantic deprecations and field shadowing on `AgentActor.tools`.

## Assessment

- Package health is good.
- Remaining concerns are environmental and warning cleanup, not red tests.
