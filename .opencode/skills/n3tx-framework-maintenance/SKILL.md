---
name: n3tx-framework-maintenance
description: Improve or modify the N3TX framework itself. Use only when changing packages/n3tx-core, n3tx-actors, n3tx-ui, n3tx-agents, framework docs, architecture, tests, or extension internals.
argument-hint: "<framework change>"
---

# N3TX Framework Maintenance

Use this skill only for modifying N3TX internals, not normal app development.

## Maintenance principles

- Preserve the model-as-contract architecture.
- Keep package dependencies acyclic: `core <- actors/ui <- agents`, meta-package depends on all.
- Prefer extension points over special cases.
- Keep backend authoritative and frontend schema-driven.
- Keep protocol IO behind network adapters.
- Keep actors independent from HTML and UI packages.
- Do not introduce duplicate contracts across layers.

## Package boundaries

```text
n3tx-core      models, schema, storage, auth, route factories, JS runtime
n3tx-actors    Actor/TX/Matrix, ActorModel, network adapters
n3tx-ui        visual Web Components, widgets, themes, ViewableMixin
n3tx-agents    AgentMixin, AgentActor, tool discovery, agent UI
n3tx           meta-package
```

## Framework change workflow

1. Read docs first: `/workspace/docs/*`, `BACKEND.md`, `FRONTEND.md`, package docs.
2. Identify the public contract being changed.
3. Add/update tests before or with behavior changes.
4. Implement at the smallest correct architectural boundary.
5. Update package docs and cross-cutting docs if behavior changes.
6. Run relevant package/application tests.

## When source inspection is expected

Framework maintenance normally requires reading source. Still start from docs to preserve intent, then inspect source to implement precise changes.

## Verification examples

```bash
cd /workspace && python3 scripts/test-backend.py --suite core -- -q
cd /workspace && python3 scripts/test-backend.py --suite actors -- -q
cd /workspace && python3 scripts/test-backend.py --suite agents -- -q
cd /workspace/tests/frontend && npx vitest run
```

## Documentation requirement

If behavior, architecture, public APIs, schema contracts, routes, components, or verification workflows change, update relevant docs and consider updating these skills.
