# N3TX Documentation

## Learning Path

1. [Getting started](GETTING_STARTED.md): build and exercise a small issue app.
2. [Architecture](ARCHITECTURE.md): model, schema, transport and storage boundaries.
3. [Models](MODELS.md): validation, relationships, serialization and identity.
4. [Authorization](AUTHORIZATION.md): policies and actual enforcement boundaries.
5. [Operations](OPERATIONS.md): configuration, security, persistence and migration.

## Reference Map

| Concern | Application guide | Mechanism reference |
|---|---|---|
| Core concepts | [Core](CORE.md) | [Core package](../packages/n3tx-core/README.md) |
| Bootstrap | [Tutorial](GETTING_STARTED.md) | [App bootstrap](../packages/n3tx-core/docs/app-bootstrap.md) |
| HTTP API | [API index](API_INDEX.md), [overview](API_OVERVIEW.md) | [CRUD](API_CRUD_ENDPOINTS.md), [actions](API_CUSTOM_ENDPOINTS.md) |
| Python symbols | [API reference](API_REFERENCE.md) | [Models](MODELS.md) |
| Data shape | [Schema discovery](API_DATA_MODELS.md), [JSON fields](JSON_FIELDS.md) | [Storage](../packages/n3tx-core/docs/storage.md) |
| Schema extensions | [Models](MODELS.md#schema-pipeline-proto_schema) | [Schema pipeline](../packages/n3tx-core/docs/schema-pipeline.md) |
| Access rules | [Authorization](AUTHORIZATION.md) | [Authorization API](../packages/n3tx-core/docs/authorization.md) |
| Frontend | [Frontend architecture](frontend/ARCHITECTURE.md) | [UI package](../packages/n3tx-ui/README.md) |
| Messaging | [Actors](ACTORS.md) | [Actor package](../packages/n3tx-actors/README.md) |
| Agent history and execution capture | [Agent package](../packages/n3tx-agents/README.md) | [Canonical TTX history](../packages/n3tx-agents/docs/ttx-history.md) |
| TTX, User messaging and explicit Notes | [TTX package](../packages/n3tx-threads/README.md) | [Storage and typed kinds](../packages/n3tx-threads/docs/thread.md) |
| Agents | [Agents](AGENTS.md) | [Agent package](../packages/n3tx-agents/README.md) |
| Files | [File package](../packages/n3tx-files/README.md) | [File capability](../packages/n3tx-files/docs/file.md) |
| Applications | [Examples](EXAMPLES.md) | Checked-in model and test sources linked there |

The model schema at `GET /ClassName` describes the running application, not a
universal Product/User schema. `/openapi.json` describes its HTTP routes.

## Current and Historical Material

These guides describe the checked-out runtime. Package guides own subsystem
detail; root [AGENTS](../AGENTS.md), [BACKEND](../BACKEND.md) and
[FRONTEND](../FRONTEND.md) are contributor context, not alternative tutorials.
For agent history, the package README and `ttx-history.md` own the current
TTX-only contract. November 6 recovery and intermediate opt-in descriptions are
historical; they do not restore Thread/TXRecord exports or fallback execution.

`changelogs/` and root release records describe historical changes. Files under
`generated/` are older generated example snapshots whose freshness is not
established; do not use them as the current API contract. They remain unchanged
for provenance. `.project/` contains working audits and plans, not runtime APIs.
`ttx-pre.py` and `ttx-draft.py` are retained historical/concept source, not public
APIs or implementation templates. Old links to removed legacy agent-history
guides do not imply those files or APIs should be restored; an archived location
must be verified rather than guessed.
