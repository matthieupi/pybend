# N3TX Architecture Overview

N3TX uses Python models as the source of fields, validation, relationships, access
policy and exposed domain behavior. Schema and response pipelines make that
contract available to HTTP clients and the native JavaScript runtime.

## High-Level Architecture

```text
                         Model declarations
                         /                \
                  schema pipeline       storage registration
                        |                    |
 Browser runtime <- GET /ClassName        StorableMixin
     |                                       ^
 forms/entities -> HTTP -> direct routes -----|
                       \-> NetworkAPI -> TX -> Matrix -> ActorModel
                                                        |
                                                        +-> StorableMixin
```

Direct HTTP does not pass through Matrix. Actor routing is an optional execution
path, not a different way to construct the app. Both reuse model/storage
primitives; that is not a promise of identical authorization or serialization on
every transport.

### Construction and capability choices

| Axis | Choices | Meaning |
|---|---|---|
| Construction | Factory, builder, raw primitives | How registration/configuration is assembled |
| Model | ProtoModel, ActorModel | Whether the model participates in Python messaging |
| Routing | `direct`, `actor` | Direct route factories or HTTP-to-TX adapter |
| Optional capabilities | UI, threads, agents, files | Package-owned mixins, schema stages and route hooks |

See [App bootstrap](../packages/n3tx-core/docs/app-bootstrap.md). Factory and
builder return FastAPI apps. The legacy Flask adapter is not a parity-tested
alternative to the current FastAPI path.

## Core Components

| Component | Owns | Does not supply |
|---|---|---|
| ProtoModel | Pydantic model contract, schema, response serialization | A complete permission policy |
| StorableMixin | CRUD and merged-state update validation | Route authorization or multi-operation transactions |
| SQLiteStorage | Rows, JSON fields, local hydration and explicit population | Automatic child-level permission checks on hydrated values |
| Registrar | Prepared model registration, storage attachment, table/migration effects | Request handling |
| Direct routes | HTTP validation, policy checks, caller injection and response adaptation | Actor dispatch |
| ActorModel / Matrix | Message dispatch and actor-aware model behavior | A universal security boundary for arbitrary Python code |
| JS runtime | Schema-derived entities, messaging and transport | Visual components |
| UI package | Native forms/components, view shells, renderer/widget extensions | Backend enforcement |
| Agent package | Separate Thread/TXRecord storage, caller-attributed append, Notes projection | Atomic multi-append, exhaustive timestamp replay or access from scope metadata |
| Agent package | Policy/runtime binding to Pydantic AI and model-derived tools | Permission granted merely by discovery |
| File package | Metadata model plus explicit byte-store operations | A filesystem sandbox or static upload directory |

Implementation roots are `packages/<package>/src/<import_name>/`. Core's key
modules are `app.py`, `models/proto_model.py`, `models/storable_mixin.py`,
`models/proto_schema.py`, `models/proto_dump.py`, `utils/registrar.py`,
`api/routes_fastapi.py`, `api/backend.py` and `storage/sqlite_storage.py`.

## Data Flow

### Model registration

1. Import capability packages before defining models that use their flags.
2. Define models. StorableMixin and registered optional mixins are injected here.
3. Bootstrap prepares registrations, then attaches storage and creates/migrates
   tables. Register every storable child model, not just the parent.
4. Generate schema, CRUD, literal action and optional capability routes.
5. Mount discovery and the merged static namespace after API routes.

Registration may change an existing database. It is not a harmless introspection
step; review [migration behavior](OPERATIONS.md#migrations).

### Read and response identity

`GET /issues/1` loads the model, checks the read rule and serializes through
`model_response()`. The top-level `$schema` identifies `/Issue`; `$id` identifies
`/Issue/1`, regardless of which route spelling was requested. Local relationship
GET responses enrich children with their own flat class-name identity.
Create/update response validation can remove nested metadata; see
[CRUD](API_CRUD_ENDPOINTS.md).

`GET /Issue` is schema, `/Issue/_` is a JSON collection mirror, and `/Issue/@`
is an optional HTML view shell. Frontend `#Issue/@` is a client navigation route.
Neither HTML nor schema discovery grants access to issue data.

### Write boundary

```text
HTTP PUT patch -> load current entity -> canonical field names
              -> strip metadata/id/protected fields
              -> require stable canonical keys on repeated normalization
              -> policy (caller + entity + detached effective patch)
              -> merge -> model validation -> persist -> response
```

Collections are replaced, not merged. The read/validate/write sequence is not a
compare-and-set. A domain action can centralize business logic but does not
automatically create a transaction, lock or idempotency mechanism.

Direct UPDATE supplies `AccessContext.patch` as a detached snapshot with read-only
top-level keys. Other entrypoints leave it `None`; patch-dependent rules must deny
when the required context is absent. This supports ordinary CRUD with narrow
field-set policies without granting general self-service writes or adding setter
endpoints. See [Authorization](AUTHORIZATION.md) for scope and snapshot semantics.
Overlapping aliases that would redirect an effective field on the model's second
canonicalization pass are rejected before authorization, including for admins.

## Design Patterns

The useful boundaries are concrete: storage is injected; schemas and response
dumps use named pipeline stages; optional capabilities register mixins and small
route hooks; adapters translate protocols to TX. Keep customizations at those
boundaries instead of copying the framework's CRUD or entity lifecycle.

The authorization package consumes plain identity dictionaries and an
`AccessContext`, without importing N3TX models. The HTTP layer translates an
authenticated identity into the reserved `user` method argument. See
[Authorization](AUTHORIZATION.md) for the important differences between direct
list, member, action, actor and trusted Python paths.

## Extension Points

| Need | Native extension | Reference |
|---|---|---|
| New business operation | `@expose_route` on a model | [Actions](API_CUSTOM_ENDPOINTS.md) |
| New model metadata | Named schema stage | [Schema pipeline](../packages/n3tx-core/docs/schema-pipeline.md) |
| Response enrichment | `@dump_extension` | [Models](MODELS.md#dump-pipeline-proto_dump) |
| Optional model behavior | `register_mixin` before model declaration | [Schema pipeline](../packages/n3tx-core/docs/schema-pipeline.md#mixin-registry) |
| New persistence backend | Complete AbstractStorage contract | [Storage](../packages/n3tx-core/docs/storage.md) |
| New visual presentation | Renderer or widget, preserving native lifecycle | [Frontend](frontend/ARCHITECTURE.md) |
| Multipart/binary capability | Package-owned `register_extra_routes` hook | [File guide](../packages/n3tx-files/docs/file.md) |
| Alternate protocol | Actor network adapter | [Actors](ACTORS.md) |

## Security Considerations

Do not equate schema visibility, field UI hints, actor discoverability or tool
selection with authorization. Direct Python operations are trusted. Hydration
can expose child fields through a parent without separately checking the child's
route policy. Remote resolution introduces outbound network and delegated-identity
trust. Review policies at every enabled entrypoint and test denied requests.

## Testing Architecture

Use isolated file-backed SQLite, generated HTTP routes and actual schemas for
application contract checks. Add transport-specific checks when enabling actors
or tools. Test malformed input, another user's resources, parent/child visibility,
stream failures and retries as well as success. The tutorial's verifier extracts
its code from [Getting started](GETTING_STARTED.md); no second model definition
is maintained in the test artifact.
