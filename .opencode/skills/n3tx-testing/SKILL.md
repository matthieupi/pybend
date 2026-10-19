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
- Relationship routes/link models work for `ListRef[T]` and `ManyToMany[T]` contracts.
- Custom methods work through generated routes.
- Actor-routed apps preserve direct-route behavior.
- Entity responses include `$schema` and `$id`.

Repo commands:

```bash
cd /workspace && python3 scripts/test-backend.py --list
cd /workspace && python3 scripts/test-backend.py --suite core -- -q
cd /workspace && python3 scripts/test-backend.py --short
```

## Frontend checks

```bash
cd /workspace/tests/frontend && npx vitest run
cd /workspace/tests/frontend && npm run test:e2e:fast
```

Use Vitest for schema-to-DOM/component/widget behavior. Use Playwright for auth/session, router history, layout, computed CSS, browser streaming, and backend-integrated flows.

## Agent checks

Use Pydantic AI `TestModel`:

```python
from pydantic_ai.models.test import TestModel

result = await agent.run(task='List grants', llm=TestModel(call_tools=['grants_list']))
```

Use file-based SQLite databases for migration/storage tests, not `:memory:`.

## File capability checks

For `n3tx-files` features:

- `File` schema and CRUD routes are available when registered.
- `POST /files/upload` returns a `File` metadata response.
- `GET /files/{id}/download` and `GET /File/{id}/download` stream bytes.
- Range requests return `206` with `Content-Range`.
- `File`-typed method parameters materialize addresses into authorized `File` instances.
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

Inspect framework source only when docs/skills are insufficient, do not cover the intended implementation, or observed behavior contradicts docs. Update/propose docs when gaps are found.
