# Data Models Reference

N3TX does not define a universal Product or Comment application schema. The
running model is authoritative; this page maps discovery and the maintained
examples instead of duplicating their fields in handwritten client interfaces.

## Schema Discovery

`GET /ClassName` returns the model schema. Inspect:

| Key | Meaning |
|---|---|
| `properties`, `required` | Field types, constraints and required inputs |
| `methods` | Literal route, methods, scope, requires_instance, parameters and returns |
| `access` | Serialized policy metadata; not client-side enforcement |
| `ui` / property UI hints | Native form/layout/renderer configuration |
| `$defs` | Related model contracts |
| `$id`, `$schema` | Schema identity and meta-schema URL |

The enriched schema has N3TX extensions and legacy Ref patching; it is not merely
the raw Pydantic schema. See [Models](MODELS.md) and
[pipeline details](../packages/n3tx-core/docs/schema-pipeline.md).

## User Model

Applications normally subclass [BaseUser](MODELS.md#baseuser). Name, email, role
and password hash originate there; fields such as age are application choices,
not framework guarantees. Register/login return token plus user, not just a User
object. Do not expose broad generic User writes to implement onboarding.

## Product Model

The checked-in [core example models](../examples/core/models/) define a catalog
with related comments/likes and exposed domain methods. Inspect `/Product` on
that app for actual fields and actions. These are example application contracts,
not generated endpoints that every N3TX app has.

## Comment Model

Inspect [core example models](../examples/core/models/) and `/Comment`.
Local children retain flat `/Comment/{id}` identity. A parent list field does not
generate a nested CRUD API or automatically enforce the child's read rule while
hydrating the parent.

## Like Model

Like/favorite behavior belongs to example model methods. A toggle may create or
delete a child and replace a parent collection; it is not a built-in atomic
database operation or an idempotent retry contract.

## Working with Foreign Keys

See [References](MODELS.md#references) for the local T/list[T] versus HTTP(S)
Ref distinction and scalar annotation caveat. Do not resolve URL refs by
concatenating a local endpoint with an integer, or create parallel `*_obj` fields
to duplicate native hydration.

## Complete Frontend Integration Example

The [getting-started tutorial](GETTING_STARTED.md) includes the native backend
HTML shell. For advanced presentation, use the runtime entity and schema-driven
form lifecycle in [frontend architecture](frontend/ARCHITECTURE.md). A second
handwritten React CRUD client/form generator is not needed to use N3TX's UI.

## TypeScript Interface

For an external typed client, derive types from the deployed schema and distinguish
inputs, responses, URL pointers and hydrated models. Validate transport errors
and pagination at runtime; TypeScript interfaces do not validate incoming JSON.

## Getting Your Own Model Schemas

Start your app, request `/Issue` (or your class name), and inspect `/openapi.json`.
Use live schemas rather than `docs/generated/` snapshots, which are retained as
historical output and have no established freshness guarantee.
