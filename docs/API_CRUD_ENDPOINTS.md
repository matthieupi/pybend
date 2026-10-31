# Standard CRUD Endpoints

Register a storable model to generate CRUD. This reference uses `Issue` with
table `issues`; the [tutorial](GETTING_STARTED.md) supplies a complete model and
authentication flow.

## Endpoint Pattern

| Operation | Table-name route | Class-name route |
|---|---|---|
| Schema | — | `GET /Issue` |
| Create | `POST /issues` | `POST /Issue` |
| List | `GET /issues` | `GET /Issue/_` |
| Read | `GET /issues/{id}` | `GET /Issue/{id}` |
| Update | `PUT /issues/{id}` | `PUT /Issue/{id}` |
| Delete | `DELETE /issues/{id}` | `DELETE /Issue/{id}` |

IDs in generated local routes are integers. Direct mirrors reuse the same
handlers. `@` routes are HTML views, not JSON operations. Methods get literal
declared routes, not a generic action catch-all.

## Get Model Schema

`GET /Issue` returns public schema: fields, constraints, `$defs`, methods,
access metadata and optional UI hints. It is not an issue record or an access
grant. `GET /Issue?scaffold=...` is a direct-route scaffold-generation option;
supported kinds are implementation-specific and invalid kinds return 400.

## Create Resource

POST a JSON object with declared writable fields. Do not supply identity metadata
or invent foreign-key representations. Model input validation precedes the route
body. Successful generated create returns **201** and an entity with top-level
`$schema`/`$id`.

`__protected_fields__` specially causes `user_owner` to be injected from the
authenticated identity on create. It is not a general create-time stripping rule
for every protected field. Give injected ownership a valid default so request
validation does not require the client to invent it. Restrict generic User CRUD
if fields such as `role` must not be client-controlled.

For user onboarding, use inherited `/users/register`, not generic user create.
For local relationships, register and save children before associating their IDs.

## List Resources

| Query | Direct route constraint | Behavior |
|---|---|---|
| `limit` | Integer 1–100 | Enables paginated `{data, meta}` response |
| `offset` | Integer >=0 | Offset with limit; defaults effectively to zero |
| `populate` | String paths, e.g. `labels` or comma-separated paths | Explicit population selection |
| `depth` | Integer 0–3 | Bounded population depth |

Without limit the response is an array. With limit:

```json
{"data": [], "meta": {"total": 0, "limit": 20, "offset": 0, "has_more": false}}
```

Total counts matching rows before pagination. No stable application sort order
is promised. Offset without limit is not a useful pagination contract. Count and
page reads are not a snapshot across concurrent changes.

⚠️ Direct list routes call only `sql_filter_for`, not `authorize`. AUTHENTICATED
currently produces `1=1` even for empty identity. Use a tested filter-capable policy
for private collections and verify anonymous/other-user lists. OWNER yields an
empty anonymous result. A custom rule returning None produces no SQL restriction.
See [Authorization](AUTHORIZATION.md#sql-pushdown).

## Get Single Resource

GET a table or class-name member path. The handler fetches, checks `read` against
the instance and returns an enriched response; missing records return 404.
`populate` and `depth` are accepted as on lists. Ordinary local relationship
hydration is distinct from explicit URL dereferencing.

Top-level identity is class-name based. GET responses enrich hydrated children
with their own identity. Direct create/update response-model validation can
rehydrate children and omit their nested `$id`/`$schema`; this was observed in
the tutorial verifier. Do not require those nested keys on every write response.

## Update Resource

Generated HTTP **PUT is patch-oriented**, not full replacement of the entity.

```http
PUT /Issue/1
Content-Type: application/json
x-access-token: <JWT>

{"title":"Fix keyboard focus order"}
```

The direct route fetches the entity, canonicalizes aliases and removes metadata,
then removes `id` and protected fields **before evaluating update policy**.
`AccessContext.patch` exposes a defensive snapshot of this effective patch, and
the route passes the same effective input to StorableMixin. The original model
validates the complete merged state; storage receives only supplied keys.
Python `Model.update(id, patch)`, actor CRUD updates and generated update tools
reuse this model boundary, though their transport/error/auth handling differs.

| Patch state | Result |
|---|---|
| Field omitted | Unchanged |
| Scalar supplied | Replaced after validation |
| List/dictionary supplied | Whole field replaced; no deep merge |
| `[]` or `{}` supplied | Whole field cleared if valid |
| Null supplied | Accepted only if the model and field-specific update path permit it |
| Alias and canonical name both supplied | Ambiguity rejected |
| Effective patch changes on repeated canonicalization | 400 before policy, including for admins |
| `$id` / `$schema` supplied | Removed from the canonical update patch |
| Protected field supplied over generated HTTP | Stripped, not changed |
| Unknown key supplied | Retained for policy inspection; no extra write grant |
| Empty effective patch | Policy still runs; if allowed, the update is a no-op |

The snapshot uses canonical field names and uncoerced input values. Its outer
mapping is read-only and its nested values are deep-copied, so policy mutation
cannot change the persisted payload. Unknown keys are not silently dropped before
policy. An allowlist must reject unwanted keys and require a nonempty patch when
appropriate. A protected-only request yields `{}`; an allowed-field request with
protected additions exposes only the allowed field. Alias conflicts return 400
before policy, even when the conflicting field would otherwise be stripped.

After stripping, the patch must remain identical when canonicalized again,
because the ordinary model update performs its own canonicalization. This
fixed-point check rejects overlapping alias chains that would redirect an
authorized key into a different field (including a protected field). It applies
equally to aliases, validation aliases and string `AliasChoices`. Stable patches
remain usable even on a schema containing overlapping aliases; admins do not
bypass the stability requirement. Unknown keys retain native interpretation and
remain visible to policy, rather than being silently discarded.

Only direct generated PUT supplies this context field automatically; other
entrypoints retain `patch=None`. Patch-dependent rules must fail closed when it
is absent. Body keys such as `user` and `context` cannot replace trusted middleware
identity or authorization context. See the
[rule API](../packages/n3tx-core/docs/authorization.md#accesscontext).

Prefer a narrow dictionary patch to resending a stale entity. `save()` and full
object updates can overwrite newer values. Writes are last-write-wins: re-fetching
reduces stale data but does not prevent a race. Domain append/remove/toggle
actions centralize behavior; they are **not automatically atomic**. Add explicit
transaction/concurrency support when the domain requires it.

Use model validators for invariants that must apply to both CRUD and actions.
Validator-derived changes to omitted fields are not automatically persisted:
only supplied patch keys are written. Test the stored result, not only validation.

## Delete Resource

DELETE checks the instance's delete policy and returns 200 with
`{"message":"Deleted successfully"}`. A subsequent read/delete returns 404.
No soft delete or general cascade is supplied. Deleting/clearing a relationship
is not equivalent to deleting its children. Plan cleanup for dangling references
and associated byte resources separately.

## Nested Resource Endpoints

Ordinary `list[T]` relationships do **not** generate nested CRUD paths such as
`/issues/1/labels/2`. Use the child's flat routes and the parent's relationship
field. Nested frontend navigation aliases do not change entity identity.

## Collection Routes

Use `/labels` or `/Label/_` for labels. Historical join-model collection paths
such as `/products/comments` are not the current ordinary list[T] contract.
Legacy ManyToMany helpers and explicit link models require their own source and
schema inspection; do not infer routes from an old generated snapshot.

## Complete CRUD Workflow Example

The [tutorial](GETTING_STARTED.md#test-your-api) verifies create, list, read,
partial update, domain action and delete, including denied and invalid requests.
It is the maintained runnable example rather than a second client implementation.

## TypeScript Integration

Read the running schema or use the native entity runtime. If maintaining a typed
external client, distinguish create input, partial update input, entity response
and paginated response; do not copy a historical Product/User interface and
assume it represents your app. Always check `response.ok` before decoding success.

## Performance Considerations

Use pagination and bounded population. Hydration may issue additional reads;
GET by ID is not necessarily one query. JSON fields are complete-field writes.
Measure actual workloads before promising latency, caching behavior or write
concurrency. See [storage](../packages/n3tx-core/docs/storage.md).
