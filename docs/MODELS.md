# N3TX Model Layer

Models own fields, validation, relationships, access rules and exposed behavior.
The [tutorial](GETTING_STARTED.md) is a complete application; examples here are
reference fragments unless stated otherwise.

## ProtoModel

Import `ProtoModel` from `n3tx_core.models.proto_model`. It extends Pydantic v2,
provides `id: int = 0` and `image: str = ''`, and permits extra fields so response
metadata can survive response validation. Extra fields are not automatically
persistable database columns; declare application fields explicitly.

| Declaration | Effect |
|---|---|
| `__storable__ = True` | Inject StorableMixin if not already inherited |
| `__tablename__ = 'issues'` | Storage table and collection route |
| `__access__` | Model action policy; missing actions fall back to authenticated |
| `__owner_field__` | Attribute compared by OWNER; defaults to `user_owner` |
| `__protected_fields__` | Generated update strips these; create specially injects `user_owner` |
| `__hidden_fields__` | Removes fields from schema, not a general response privacy mechanism |
| `Field(exclude=True)` | Excludes a value from normal Pydantic dumps; storage preserves declared excluded fields |
| `__ui__` | Model UI configuration, when UI package is imported before declaration |

`Model.schema()` returns a deep copy of a per-class cached schema.
`Model.invalidate_schema_cache()` clears that class's entry. Establish config
and extensions before the first schema call; changing API_URL later can leave
cached identities inconsistent.

## Schema Pipeline (proto_schema)

The seven core stages are `base`, `strip_hidden`, `methods`, `defs`, `access`,
`ui`, `metadata`. Imported packages insert stages relative to those names.
`widget` is inserted before `ui`; UI's `viewable` follows `ui`; the agent stage
is inserted after `methods`, not after UI.

The schema carries properties, required fields, method parameters/returns,
descriptor scope, access rules, nested `$defs` and identity URLs. Method inputs
omit `self`, `cls` and reserved `user`. `events=` declares stream event schemas;
it is not automatic validation of every yielded event.

Use the [pipeline reference](../packages/n3tx-core/docs/schema-pipeline.md) for
stage registration, named pipelines and current Ref schema inconsistencies.

## Dump Pipeline (proto_dump)

| Method | Result |
|---|---|
| `instance.model_dump()` | Pydantic field data; does not synthesize identity metadata |
| `instance.model_response()` | Response pipeline: relationships and identity metadata |
| `Model.referenced_json_schema()` | Schema fragment used in `$defs` |
| `ProtoModel.blueprint()` | Registered model schemas keyed by registry/table name |

The response stages are `base -> relationships -> schema_url -> instance_url ->
populate`. Hydrated children run through their response pipelines. Populated
values overlay the base output. A stored entity's public identity is flat:
`http://localhost:5000/Comment/2`, not `/Product/1/Comment/2`.

Datetime handling uses native Pydantic behavior. UTC offsets containing seconds
or fractional seconds are intentionally unsupported; exact JSON round trips are
not guaranteed for those values. This does not exclude timestamp microseconds or
ordinary minute-aligned UTC offsets.

Extension fragment:

```python
from n3tx_core.models.proto_dump import dump_extension

@dump_extension(after='instance_url')
def provenance(instance, data: dict) -> dict:
    data['source_type'] = type(instance).__name__
    return data
```

Extensions are process-wide registrations. Avoid duplicate names and unexpected
side effects. Direct action handlers return the method result, not an automatic
`model_response()` conversion of every return type. For guaranteed enriched
action output, return an explicit response dictionary as in the tutorial.

## StorableMixin

Register each storable model with storage, normally through `create_app`.
Constructing a model does not save it. Constructing a storable model with only
`id` triggers a storage read; use `Model.get(id)` when handling missing rows.

| Python operation | Contract |
|---|---|
| `Model.create(Model(...))` | Persist a validated model instance; bare dict is not accepted by this mixin's create implementation |
| `Model.get(id, as_dict=False, populate=None)` | Instance or None; optional raw dictionary/population |
| `Model.list(sql_filter=None, limit=None, offset=None, populate=None, ids=None, *, order_asc=None, order_desc=None, where=None)` | List, or `{data, meta}` when paginated; optional public-field ordering and ANDed field conditions |
| `Model.update(id, patch)` / `instance.update(patch)` | Validate merged state; persist supplied keys |
| `Model.delete(id)` | Delete row; no general relationship cascade |
| `instance.save()` | Create if ID is falsey, otherwise update |

Direct Python calls do not enforce `__access__`. Do not expose them from an
unchecked custom route, tool or batch action. An instance update can validate
against that instance's stale state. See [storage](../packages/n3tx-core/docs/storage.md)
and [HTTP updates](API_CRUD_ENDPOINTS.md#update-resource).

## References

### Local relationships versus URL pointers

| Annotation | Meaning | Persistence and response |
|---|---|---|
| `list[T]` | Ordered local related entities | Parent JSON ID array; hydrated child objects on read |
| Local scalar `T` that remains a model annotation | Local related entity | Local ID storage and hydration; see rewrite caveat below |
| `Ref[T]` | Absolute HTTP(S) entity identity | URL string, no automatic remote I/O |
| `list[Ref[T]]` | Ordered URL pointers | JSON URL array, not local child ID array |
| `Ref['self']` | Historical self-parent shorthand | Annotated integer marker, not URL Ref |
| `dict` / primitive lists | Embedded values | JSON TEXT, no independent identity |
| Explicit link model | Shared relationship with fields/identity | Its own registered resource |

### Scalar annotation rewriting

The runtime is not uniform across inheritance shapes. During
`ProtoModel.__init_subclass__`, **only when StorableMixin is first injected**, it
resolves type hints and rewrites bare Pydantic model class annotations other than
the class itself into `Ref[T]`.

| Declaration condition | Effective annotation |
|---|---|
| Fresh `class Parent(ProtoModel)` with `__storable__=True`, `child: Child` | `Ref[Child]`, requiring a URL |
| `children: list[Child]` in that class | Unchanged local collection |
| `child: Optional[Child]` in that class | Not a bare class; not rewritten |
| New `child: Child` on a subclass already inheriting StorableMixin | Not rewritten; local model field |
| Self type or unresolved/cyclic declarations | Requires explicit inspection/rebuild testing; do not assume a URL or local contract |

This behavior was reproduced against the checked-out implementation. Inspect
`Model.model_fields[field].annotation`, not just the written annotation, before
choosing storage or request values. Do not refactor inheritance casually on a
persisted model. Prefer the verified `list[T]` collection path where appropriate;
nullable scalar and forward-reference storage/migration paths need their own
tests. Pydantic `model_rebuild()` is the v2 rebuild API, not `update_forward_refs`.

### URL reference contract

```python
from n3tx_core.models.ref import Ref

# Given a model class Label:
ref = Ref[Label]('https://labels.example/api/Label/42')
Ref.base_url(ref)  # 'https://labels.example/api'
Ref.schema(ref)    # 'Label'
Ref.id(ref)        # '42' (string)
```

URLs must have HTTP(S), an authority and final schema/ID path segments; query and
fragment are rejected. Typed refs check the target class name. Integer IDs,
relative `/Label/1` paths and `n3tx://...` are not valid URL refs. Whitespace and
a trailing slash are normalized. Pydantic field input is a string; helper
constructors can additionally extract `$id` from supported objects.

`ref.hydrate(user=..., context=resolver)` explicitly calls a resolver. Without
one it raises RuntimeError. Ordinary validation, dumps and unpopulated storage
reads do not contact the URL. `local_ref_id` extracts local relationship IDs only
when an absolute URL belongs to the configured API; it does not make every Ref
local. `public_id_url` builds local class-name identities.

Core exposes `Ref` as a URI string with `x-ref` at the type level. The enriched
schema pipeline still rewrites bare scalar Ref fields into a legacy `$ref`
shape; list Ref items retain URI metadata. This is a schema inconsistency, not
permission to send an integer. See the [pipeline guide](../packages/n3tx-core/docs/schema-pipeline.md).

### Relationship lifecycle

Register parent and child. Use existing saved children for association; a list
field is not an automatic nested-create API. Replacing or clearing a list does
not delete child rows. Deleting a parent does not guarantee cascade cleanup.
No inverse collection or access inheritance follows from declaring a relation.
Parent hydration does not independently authorize every child; do not attach
private children to publicly readable parents without a verified policy design.

`ManyToMany[T]` remains a legacy link-model mechanism. It generates relationship
metadata and link tables/indexes, not the ordinary `list[T]` storage contract.
Existing join-backed data needs explicit migration before adopting JSON ID lists.

## BaseUser

Subclass `n3tx_core.models.base_user.BaseUser`, set `__tablename__` and
`__abstract__ = False`. Fields include `name`, `email`, `role` (default `user`)
and excluded `password_hash`. The owner field is `id`.

| Inherited method | Route for table `users` | Result |
|---|---|---|
| `register_user(name, email, password)` | `POST /users/register` | Token and user; duplicate email is 409 |
| `login(email, password)` | `POST /users/login` | Token and user; invalid credentials are 401 |

Both methods explicitly allow ANYONE. Registration lowercases email, hashes the
password via the create path and returns a JWT. The method is `register_user`,
not `register`, to avoid the actor registration name. Email uniqueness is an
application-level scan, not a concurrency-safe uniqueness guarantee.

⚠️ Registration grants admin under global DEBUG. Generic User CRUD can also
expose role assignment if you permit it: declare a restrictive User policy.
Hidden schema fields alone do not protect request writes. See
[Authentication](AUTHORIZATION.md#authentication-jwt).

## ActorModel

`n3tx_actors.models.actor_model.ActorModel` combines Actor and ProtoModel.
Its CRUD handler adapts schema/create/get/list/update/delete TX messages to model
operations and publishes lifecycle events. Use [Actors](ACTORS.md) for message
addresses, dispatch, interceptors and transport policy. Do not infer that a plain
Python call has passed those guards.

## Optional File Resource (`n3tx-files`)

`File(ActorModel)` stores metadata; FileStore stores bytes. Upload/download routes
are explicit, not static files. Typed File method parameters can resolve canonical
local absolute File URLs after package import. `public` metadata is not by itself
an access rule. Read the [File capability guide](../packages/n3tx-files/docs/file.md)
for materialization, caller propagation, byte access and storage lifecycle.

## File Layout

Core model files live under `packages/n3tx-core/src/n3tx_core/models/`.
ActorModel lives in the actors package; ViewableMixin in UI; AgentMixin in agents.
The old `n3tx.core.*` import layout is not the current package API.
