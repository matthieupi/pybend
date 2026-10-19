---
name: n3tx-testing
description: N3TX application testing and verification. Use when testing app models, routes, auth, actor routing, agents, frontend components, widgets, streaming, or E2E behavior.
argument-hint: "<test or verification task>"
---

# N3TX Testing

This skill covers application verification, not framework maintenance.

## Verification order

1. Narrow behavior test or direct schema/API check.
2. Adjacent backend/frontend tests.
3. Browser/E2E only when behavior needs real browser/auth/routing/layout.
4. Broader suites when the narrow boundary passes.

## Backend checks

Use generated contracts:

- `GET /{ClassName}` schema includes fields, methods, access, UI, `$defs`.
- CRUD routes work and enforce auth.
- Local `list[T]` hydration, URL refs and explicit shared-link models behave as documented.
- Custom methods work through generated routes.
- Check direct and actor paths independently; record differences rather than assuming parity.
- Entity responses include `$schema` and `$id`.

Repo commands:

```bash
# From the checkout root, using the approved interpreter:
"${N3TX_PYTHON:-/workspace/.venv-agents/bin/python}" scripts/test-backend.py --list
"${N3TX_PYTHON:-/workspace/.venv-agents/bin/python}" scripts/test-backend.py --suite core -- -q
"${N3TX_PYTHON:-/workspace/.venv-agents/bin/python}" scripts/test-backend.py --short
```

## Frontend checks

```bash
npm --prefix tests/frontend test
npm --prefix tests/frontend run test:e2e:fast
```

Use Vitest for schema-to-DOM/component/widget behavior. Use Playwright for auth/session, router history, layout, computed CSS, browser streaming, and backend-integrated flows.

## Agent checks

Use Pydantic AI `TestModel`:

```python
from pydantic_ai.models.test import TestModel

# Excerpt: use the registered, persisted AgentActor setup in docs/AGENTS.md.
result = await agent.agentic(task='List grants', llm=TestModel(call_tools=['grants_list']))
```

Use file-based SQLite databases for migration/storage tests, not `:memory:`.

## File capability checks

For `n3tx-files` features:

- `File` schema and CRUD routes are available when registered.
- `POST /files/upload` returns a `File` metadata response.
- `GET /files/{id}/download` and `GET /File/{id}/download` stream bytes.
- Range requests return `206` with `Content-Range`.
- File URL parameters apply read checks; test dict/instance materialization separately.
- Bytes are written through `FileStore`, not SQLite/static assets.

## Streaming checks

- Schema method has `stream: true` and event schemas.
- Chunks arrive in order.
- Done/end event terminates stream.
- UI cancels stream on disconnect.

## Test guardrails

- Do not test implementation details when contract behavior is enough.
- Do not duplicate schema expectations manually beyond what the test needs.
- Do not loosen tests without identifying current intended contract.
- Do not use fixed sleeps in Playwright when readiness helpers or DOM state waits apply.

## Source-reading policy

Read relevant docs/skills first, then current implementation/tests before meaningful
changes. Also inspect source when docs are incomplete or contradicted. Docs first
is not docs only; update or propose documentation corrections when gaps are found.
