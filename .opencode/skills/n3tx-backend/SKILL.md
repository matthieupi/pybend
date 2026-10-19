---
name: n3tx-backend
description: N3TX backend workflow and context routing for models, storage, auth, actions, actors, agents, files and integrations. Use when backend scope is broad or unclear.
argument-hint: "<backend feature>"
---

# N3TX Backend

Read [AGENTS](../../../AGENTS.md), [backend navigation](../../../BACKEND.md)
and the relevant package guide. Use `n3tx-skill-routing` to choose focused skills.

Trace model -> registration -> schema -> routes/TX -> storage -> response.
Keep fields, validation, permissions and methods authoritative in the model.
Use generated CRUD instead of parallel controllers; expose genuine domain actions
with `@expose_route`. Ordinary helpers need not become actors unless addressable
or reusable actor capabilities are required.

| Task | Focused skill |
|---|---|
| Model declarations | n3tx-models |
| Local relationships and URL refs | n3tx-storage-relationships |
| JSON serialization | n3tx-json-fields |
| Permissions and caller propagation | n3tx-authorization |
| Model actions | n3tx-methods-routes |
| Dispatch and remote protocols | n3tx-actors, n3tx-networking |
| Reasoning and tools | n3tx-agents |
| Entry point and registration | n3tx-app-bootstrap |
| File bytes and metadata | n3tx-files |
| Third-party APIs | n3tx-external-integrations |

Do not revive ListRef, generated joins, relative File references or n3tx-scheme
identity. Use local model collections separately from absolute HTTP(S) Ref values.
Do not assume actor/raw-TX/tool enforcement equals HTTP. Verify success, denial,
validation and persistence through the enabled path, using isolated storage.

Current commands and environment selection live in [AGENTS](../../../AGENTS.md).
Inspect source/tests before implementing, and update canonical docs when a
contract changes. This skill is navigation, not a second API reference.
