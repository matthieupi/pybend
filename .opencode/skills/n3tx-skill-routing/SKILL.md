---
name: n3tx-skill-routing
description: N3TX skill selection, routing, fresh codebase onboarding, established codebase changes, and choosing the right N3TX specialist skill. Use FIRST when a task is broad, ambiguous, spans backend/frontend/actors/agents/files, or asks which N3TX skill/context to use.
argument-hint: "<N3TX task or codebase context>"
---

# N3TX Skill Routing

Use this skill as the catalog index for N3TX work. Its job is to choose the
smallest useful skill set before implementation so agents do not over-load broad
context or miss specialist contracts.

## Read first

For implementation tasks, preserve the repository context-loading order:

1. Read `AGENTS.md` and relevant `/workspace/docs/` or package docs.
2. Read `BACKEND.md`, `FRONTEND.md`, or both based on the affected surface.
3. Load the primary skill below and any required companion skill.
4. Inspect framework source only when docs/skills are insufficient, stale, or
   contradicted by observed behavior.
5. If source reveals a stale contract, update or propose updates to docs/skills.

## Fresh N3TX codebase flow

```text
new app / feature idea
  -> n3tx-principles
  -> n3tx-build-app
  -> n3tx-app-bootstrap
  -> domain specialist(s)
  -> n3tx-testing
```

Choose the lowest routing level that satisfies the requirement:

| Need | Default level | Primary skill |
|---|---|---|
| CRUD/schema-driven app | Level 1: `ProtoModel` + direct routes | `n3tx-models` |
| Actor-capable entities with direct HTTP | Level 2: `ActorModel` + direct routes | `n3tx-actors` |
| TX/protocol routing, agents, MCP, WebSocket, federation | Level 3: `ActorModel` + `routing='actor'` | `n3tx-networking` |

## Established codebase flow

```text
existing N3TX app change
  -> n3tx-principles
  -> exact mechanism skill
  -> n3tx-testing
  -> n3tx-framework-maintenance only if framework internals/public contracts change
```

For bug fixes, use the normal bugfix/TDD workflow first, then load the exact
N3TX mechanism skill for the failing path.

## Routing matrix

| User intent / keywords / files | Primary skill | Combine with | Avoid as primary |
|---|---|---|---|
| app bootstrap, `create_app`, `N3TXApp`, static dirs, package imports | `n3tx-app-bootstrap` | `n3tx-build-app`, `n3tx-testing` | `n3tx-backend` |
| model fields, `ProtoModel`, `ActorModel`, `BaseUser`, schema, validation | `n3tx-models` | `n3tx-storage-relationships`, `n3tx-authorization` | `n3tx-backend` |
| storage, pagination, `ListRef`, joins, ownership, `ManyToMany` | `n3tx-storage-relationships` | `n3tx-json-fields`, `n3tx-testing` | raw SQL changes |
| dict/list persistence, JSON TEXT, nested object field storage | `n3tx-json-fields` | `n3tx-storage-relationships` | relationship skills alone |
| upload, download, blob, attachment, `File`, `FileStore`, `/files/upload` | `n3tx-files` | `n3tx-authorization`, `n3tx-testing`, `n3tx-external-integrations` | generic backend |
| auth, JWT, `__access__`, OWNER, ROLE, protected fields | `n3tx-authorization` | `n3tx-models`, `n3tx-testing` | frontend-only fixes |
| `@expose_route`, custom method, user injection, method schema | `n3tx-methods-routes` | `n3tx-authorization`, `n3tx-streaming` | custom FastAPI route |
| actor, TX, Matrix, lifecycle, reusable compute | `n3tx-actors` | `n3tx-networking`, `n3tx-agents` | plain helper functions |
| NetworkAPI, WebSocket, MCP, ActivityPub, protocol bridge | `n3tx-networking` | `n3tx-actors`, `n3tx-authorization` | direct internal HTTP |
| LLM, `AgentActor`, `__agent__`, tools, chat, agent stream | `n3tx-agents` | `n3tx-streaming`, `n3tx-actors` | separate tool-only APIs |
| SSE, `stream=True`, stream events, `NTTStream`, `NTTStreamAgent` | `n3tx-streaming` | `n3tx-methods-routes`, `n3tx-agents` | normal method skill alone |
| schema-driven UI, `__ui__`, field metadata, access adaptation | `n3tx-ui-schema` | `n3tx-frontend`, `n3tx-widgets` | duplicated frontend contracts |
| Web Components, `Component`, `NTTElement`, `ListElement`, renderers | `n3tx-ui-components` | `n3tx-ui-schema`, `n3tx-testing` | backend-only skills |
| field widgets, Formidable, widget registry | `n3tx-widgets` | `n3tx-ui-schema`, `n3tx-testing` | custom component first |
| theme, shell, topbar, sidebar, profile, route views | `n3tx-frontend` | `n3tx-ui-components`, `n3tx-ui-schema` | backend as primary |
| external API, scraping, webhooks, cloud provider | `n3tx-external-integrations` | `n3tx-actors`, `n3tx-files`, `n3tx-authorization` | scattered service calls |
| schema/dump extension, mixin, custom storage, custom adapter | `n3tx-extension-patterns` | `n3tx-framework-boundaries` | app-level workaround |
| framework packages, public contracts, package docs, test harness | `n3tx-framework-maintenance` | exact package/domain skill, `n3tx-testing` | app build skills |

## Broad skill rules

- `n3tx-build-app` is a workflow skill for end-to-end app construction.
- `n3tx-backend` is a backend index; delegate concrete work to models, storage,
  methods, auth, actors, agents, files, networking, or integrations.
- `n3tx-frontend` is a frontend index; delegate concrete work to UI schema,
  components, widgets, streaming, agents, route/view, or theme/shell guidance.
- `n3tx-framework-maintenance` is for framework internals, not app code.

## Stale-information guardrails

- Treat `AGENTS.md`, `BACKEND.md`, `FRONTEND.md`, `/workspace/docs/`, and
  package docs as authoritative contracts.
- Skills should summarize and route; avoid copying long command lists or route
  tables unless they include a drift anchor back to canonical docs.
- If a skill and a canonical doc disagree, trust the canonical doc and update or
  propose a skill change.
- After editing `.opencode/skills`, restart OpenCode so the running session sees
  the new skill catalog.
