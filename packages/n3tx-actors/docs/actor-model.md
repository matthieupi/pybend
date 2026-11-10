# ActorModel: dispatch and enforcement

[Package](../README.md) · [Adapters](network-adapters.md)

ActorModel combines Actor and ProtoModel. Storage still comes from
`__storable__` and model registration; actor auto-registration is not storage
setup. The same model/schema remains the source for HTTP routes and tool specs.

## Dispatch contract

```text
TX -> handler_crud
        | schema/create/get/list/update/delete -> model storage/schema
        | otherwise
        v
exposed method? -> resolve instance -> access/materialize -> inject caller
        | no
        v
ordinary named handler(data, tx)
```

CRUD names are case-normalized. CRUD dispatch is class-level even when invoked
on an instance. `_NOT_HANDLED` distinguishes an unknown operation from a CRUD
operation returning None.

| TX | Data / result |
|---|---|
| `schema` | No storage lookup; schema dictionary |
| `create` | Model fields; validated instance then `create`; entity response or 409 |
| `get` | Required truthy `id`, optional `populate/depth`; entity or 404 |
| `list` | Optional `limit/offset/populate/depth/order_asc/order_desc/where`; storage list result serialized |
| `update` | Required `id` plus patch; merge/validate through storage update; entity or error |
| `delete` | Required `id`; fetch, authorize, delete; `{deleted: id}` |

Updates preserve omitted fields and replace supplied collections; they are
last-write-wins, not concurrency control. See the
[CRUD contract](../../../docs/API_CRUD_ENDPOINTS.md#update-resource).
Class `Model.update(id, patch)` and actor instance `instance.update(patch)` share
the update primitive; neither direct Python call is an HTTP authorization gate.

LIST forwards `where` conditions to the model. Actor HTTP decodes a JSON query
parameter; internal TX uses a dictionary directly. The model compiles conditions
and ANDs them with the boundary-supplied SQL policy before storage counts/pages.
Invalid list conditions produce a 422 TX error. This does not add authorization
to raw internal LIST dispatch; its existing caller/policy boundaries still apply.

LIST forwards supplied ordering options to native storage. `order_asc` and
`order_desc` accept one stored model field and are mutually exclusive. Invalid
ordering returns a 422 error TX, translated to HTTP 422 by NetworkAPI. Ordering
does not change list authorization filters, counts or response hydration.

Exposed methods use descriptor-aware scope. Instance methods load `data.id`;
class/static/actor methods do not. Arguments other than reserved `id` and `user`
are passed as kwargs after registered materializers run. An explicitly named
`user` parameter is supplied from trusted metadata as described below.
Plain named handlers retain
`(data, tx)`. Async generators emit `tx.chunk(...)` followed by `tx.end()`;
mid-stream exceptions emit an error instead.

ActorModel replies differ from plain Actor: lists/dicts are returned directly,
BaseModels use `model_dump()`, and strings are JSON-decoded if possible. This
explains why AgentActor JSON text becomes an object through actor HTTP.

## Authorization: two tiers, not universal enforcement

| Entry/boundary | Behavior |
|---|---|
| Generated actor HTTP | Supplies `meta.user` (anonymous `{}`) and `meta.model_cls`; NetworkAPI request interceptor gates calls |
| Tier 1 `auth_interceptor` | Public schema; create check; list SQL filter; identity/resource-independent prechecks; custom default authenticated gate |
| Tier 2 CRUD | `_authorize` on create/get/update/delete, using fetched resource where applicable |
| Tier 2 list | Uses supplied `sql_filter`; does not independently authorize or derive a filter |
| Tier 2 exposed method | Evaluates explicit decorator `access=` with resolved instance, only when caller is not None |
| Internal TX | Missing/None user bypasses Tier 2; absent model `__access__` also passes CRUD guard |

Both HTTP tiers matter. Calling Matrix directly does not run NetworkAPI's
request interceptor. A caller dictionary alone does not make list operations
row-filtered. Schema or UI visibility is not server enforcement.

### Caller arguments and protected fields

ActorModel exposed-action dispatch ignores body `user` before materialization.
Only a named `user` parameter receives the caller resolved from `tx.meta.user`:

| Method declaration | Injected value |
|---|---|
| `user: dict = None` or another non-storable annotation | Detached authenticated identity dictionary |
| `user: User = None`, where User is a concrete storable class | `User.get(authenticated_user_id)` |
| No named `user` parameter, including `**kwargs` only | No injected caller argument |
| Missing authenticated identity | `None`, regardless of body identity |

A concrete caller lookup returning no stored User produces a 403 before method
invocation. Optional/union model annotations are not resolved as concrete model
types by this branch. The identity dictionary requires a `user_id`; it is not
inferred from `source`, action data or a target entity.

Generated NetworkAPI HTTP parsing already reserves the named caller argument.
Agent-generated tools omit `user` from their parameter schema and supply trusted
identity in metadata; ActorModel now bridges that metadata into named action
arguments. This does not authenticate arbitrary metadata or replace action
authorization. Existing access checks still precede injection. Ordinary named
handlers retain their `(data, tx)` contract without this adaptation.

HTTP create/update also performs owner injection/protected-field handling that
raw CRUD TXs do not reproduce. Treat raw TX/data/meta as trusted process inputs;
do not expose arbitrary actor dispatch to clients. Non-exposed named handlers
remain callable by TX and need their own trust boundary.

## Lifecycle events

| Mutation path | Publication |
|---|---|
| TX create | `after_create` with serialized entity |
| TX delete | `after_delete` with `{id}` |
| Shared StorableMixin update on ActorModel | `after_update`, including direct class/instance updates |

Subscribers receive `LIFECYCLE` with `{event, entity}`. `_publish_lifecycle`
uses `asyncio.create_task`; delivery is not durable, transactional, acknowledged,
or guaranteed before the CRUD response. Direct create/delete should not be
assumed to publish the TX adapter's events. Use an explicit per-model subscriber
list when configuring consumers rather than accidentally sharing inherited
mutable state. Do not use these notifications as a reliable audit log or job queue.

Evidence: [actor_model.py](../src/n3tx_actors/models/actor_model.py),
[auth tests](../src/n3tx_actors/tests/test_actormodel_auth.py),
[lifecycle tests](../src/n3tx_actors/tests/unit/test_actor_model_lifecycle.py).

## Changelog

- 2026-11-09: Document metadata-only exposed-action caller injection, ignored
  body identity, concrete stored callers and the unchanged authorization limits.
