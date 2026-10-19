# N3TX Release Notes

## 0.12.0 (2026-07-11)

### n3tx-core / n3tx-actors: Generated PUT routes are now partial updates

Generated direct and actor HTTP `PUT` routes now share the same patch contract
as `Model.update(id, patch)`, raw actor update TX messages, and generated agent
update tools.

#### New update behavior

- Omitted fields remain unchanged, including required fields and fields with
  defaults.
- Supplied fields are merged with the persisted entity and the complete result
  is validated through the original model.
- Only explicitly supplied fields are written to storage.
- Explicit falsey values such as `0`, `false`, `""`, `[]`, and `{}` are retained.
- Explicit collection values replace the complete stored collection; omission
  preserves it.
- Empty or protected-only patches return the unchanged entity without a storage
  write or `after_update` lifecycle event.
- The route ID is authoritative. A body `id` cannot redirect the update.
- Pydantic aliases are normalized before validation and storage. Protected
  fields remain protected when addressed through an alias.
- Invalid owned `list[T]` replacements are rejected instead of silently
  resolving to an empty or partial collection.

Validation failures preserve useful downstream diagnostics without logging
submitted values. Model validation errors return `422`; invalid patch shapes or
relationship replacements return `400`. Unexpected actor failures continue to
log traceback context and return an error TX.

#### Migration notes

1. **Stop requiring complete objects in PUT clients.**
   - Before:
     `PUT /Product/1 {"name": "Renamed", "price": 25, "comments": [...]}`
   - After: `PUT /Product/1 {"name": "Renamed"}`
   - Existing complete-object requests remain valid, but they still replace
     every collection they explicitly include.

2. **Remove client-side default filling.**
   - Do not copy schema defaults such as `[]` or `{}` into an update merely
     because the field is omitted.
   - Send an empty collection only when the caller intends to clear it.

3. **Expect merged-state validation.**
   - Field and model validators run against the complete persisted entity plus
     the supplied patch.
   - Invalid updates now fail before storage, including raw Python and actor TX
     updates that previously could bypass complete-model validation.

4. **Review update OpenAPI consumers.**
   - Generated PUT request bodies are represented as generic JSON objects rather
     than separate per-model update schemas.
   - `GET /{ClassName}` remains the authoritative model/schema contract.
   - Clients should derive writable fields from that schema instead of expecting
     a generated `ProductUpdate`-style OpenAPI component.

5. **Keep atomic collection mutations in model methods.**
   - Collection replacement remains last-write-wins.
   - Use domain-specific `@expose_route` methods for concurrent append, remove,
     or toggle operations.

### Ref identities are now canonical absolute HTTP(S) URLs

N3TX now uses one public identity model across schemas, storage, actors, files,
and the frontend: an entity's absolute HTTP(S) `$id` URL. The framework no
longer translates remote identities through service-name addresses.

```text
https://storage.example.com/api/v1/File/file-12
```

This is a breaking change for applications that stored integer `Ref[T]` values,
stored or transmitted `n3tx://...` values, passed relative entity paths, or
depended on configured remote names as public identity.

#### Ref value and schema contract

- `Ref[T]` is an immutable, string-like absolute HTTP(S) entity URL.
- A Ref URL must end in `/{ClassName}/{id}` and must not contain a query string
  or fragment.
- `Ref[T]` and `list[Ref[T]]` store and emit URL strings unchanged.
- Raw local ids, relative paths, non-HTTP schemes, and target-class mismatches
  are rejected for explicit Ref fields.
- Local relationships remain separate: `T` and `list[T]` may store compact local
  ids and hydrate into local model objects.
- Ref JSON Schema uses a URL string plus an explicit target marker:

  ```json
  {
    "type": "string",
    "format": "uri",
    "x-ref": "File"
  }
  ```

`x-ref` identifies the model targeted by a URL pointer. JSON Schema `$ref`
continues to describe embedded/hydrated model structure and is not overloaded
for pointer values.

#### New Ref helpers

```python
ref = Ref[File]("https://storage.example.com/api/v1/File/file-12")

Ref.url(ref)       # complete validated URL
Ref.base_url(ref)  # https://storage.example.com/api/v1
Ref.schema(ref)    # File
Ref.id(ref)        # file-12

file = ref.hydrate(context=resolver)
```

`Ref.hydrate()` is synchronous in this release and may block when its explicit
resolver performs remote I/O. It does not mutate the Ref. Default validation,
storage reads, and response dumps do not dereference refs. Explicit `populate`
or positive depth may still use the configured storage resolver.

#### Removed Ref APIs and behavior

The previous service-address parsing and canonicalization helpers have been
removed, including:

- `canonicalize_ref()`
- `parse_ref_string()`
- `is_distributed_ref()`
- `is_external_link()`
- `public_ref()`

Configured `REMOTES` entries may still provide credentials and disambiguate API
base-path prefixes, but they no longer translate or define entity identity.

#### Remote actor migration

`RemoteRef`, `RemoteMatrix`, and `MatrixReferenceResolver` now route absolute
HTTP(S) targets directly:

```diff
- TX(name="get", target="n3tx://storage/File/12")
+ TX(name="get", target="https://storage.example.com/File/12")

- Artifact.ref("n3tx://storage/Artifact/42")
+ Artifact.ref("https://storage.example.com/Artifact/42")
```

Class-level remote capabilities use the absolute schema URL:

```python
TX(name="reindex", target="https://compute.example.com/Job")
```

Remote response `$id` values remain absolute URLs and are no longer rewritten
into a framework-specific scheme.

#### File reference migration

`n3tx-files` no longer maintains a parallel `FileAddress` grammar.
`File.resolve(ref)` and File-typed method materialization accept only a
canonical absolute File `$id` on the current API:

```diff
- {"audio": "n3tx://files/42"}
- {"audio": "/File/42"}
+ {"audio": "https://api.example.com/File/42"}
```

`FileAddress` and `parse_file_address()` have been removed. Binary transport
routes remain supported and are not entity identity formats:

```text
POST /files/upload
GET  /files/{id}/download
GET  /File/{id}/download
```

#### Frontend migration

- Read `properties[field].x-ref` to identify URL pointer fields.
- Treat Ref values as complete URLs; do not prepend a model name, hash route, or
  current origin.
- Edit the complete URL rather than a local id.
- Continue treating `$ref` and `array.items.$ref` as hydrated model shapes.
- Continue treating `list[Ref[T]]` as URL arrays rather than embedded objects.

The built-in `ReferenceWidget` follows this contract automatically.

#### Stored-data migration

There is no automatic production data migration for old Ref values. Migrate
existing scalar Ref columns and JSON `list[Ref[T]]` arrays before deploying this
version.

| Previous stored value | Required replacement |
|---|---|
| `n3tx://storage/File/12` | `{REMOTES.storage.url}/File/12` |
| configured remote HTTP URL | Keep the original absolute URL |
| local integer `12` in `Ref[File]` | `{API_URL}/File/12` |
| `/File/12` | `{API_URL}/File/12` |
| JSON array of old values | Map every element using the same rules |

Migration procedure:

1. Back up the database and record the old `API_URL` and remote-name-to-base-URL
   configuration used by the stored data.
2. Inventory every `Ref[T]` and `list[Ref[T]]` field from model annotations.
3. Rewrite scalar values and each JSON-array element to its absolute class-name
   entity URL.
4. Reject unknown service names instead of guessing a host.
5. Validate the rewritten schema segment against `T.__name__`.
6. Deploy application and client changes together; old values intentionally fail
   validation after this release.
7. Verify representative reads without populate, then verify explicit populate
   and `Ref.hydrate()` through the configured resolver.

Do not rewrite local `T` or `list[T]` relationship ids. Those are local storage
optimizations and are not explicit Ref fields.

### n3tx-core: Generated join models removed

The core relationship contract now uses normal model fields instead of generated
join-model machinery. Local owned collections should be declared as `list[T]` on
the owner model and every storable class should be registered explicitly.

#### What remains supported

| Concern | Supported contract |
|---|---|
| Owned local collections | `comments: list[Comment] = Field(default=[])` |
| Storage shape | Parent row stores ordered child ids as a JSON array |
| API response shape | Read responses hydrate `list[T]` ids into child objects with `$schema` and `$id` |
| Entity identity | Flat class-name URLs such as `/Comment/5` |
| Single local/distributed pointer | `Ref[T]` |
| Pointer arrays | `list[Ref[T]]` |
| Shared relationships | Explicit link models or existing `ManyToMany[T]` helper |

#### Removed APIs and behavior

- `generate_join_model(...)` has been removed from the core model API.
- `N3TXApp.join(...)` has been removed from the builder.
- `create_app(join_models=...)` now raises `TypeError` so stale bootstrap code
  fails loudly instead of silently creating legacy relationship routes.
- The `join_models` registry has been removed.
- Direct FastAPI routing no longer synthesizes parent-scoped nested routes from
  generated join metadata.
- `list[T]` fields no longer serialize as href arrays backed by generated join
  tables.

#### Migration notes

Existing apps that used generated joins should migrate in three steps:

1. **Register concrete models directly.**
   - Before: `create_app(models=[Product], join_models=[(Product, Comment)])`
   - After: `create_app(models=[Product, Comment])`

2. **Move relationship ownership into the model field.**
   - Define `comments: list[Comment] = Field(default=[])` on `Product`.
   - Use custom methods such as `Product.comment(...)` for append/toggle rules.

3. **Migrate existing data.**
   - Generated join tables are no longer read to populate `list[T]` fields.
   - Move old relationship rows into the parent's JSON id-array column before
     deploying this version against an existing database.

This is a breaking cleanup for clients or data migrations that depended on
`ListRef`, generated join models, generated nested routes, or href-array
collection responses. The supported replacement is simpler and model-first:
flat entities, explicit model registration, and schema-declared `list[T]`
relationships.

### n3tx-actors: NetworkAPI route grammar cleanup

`create_api_routes()` now uses the same flat model route grammar as direct
FastAPI routing. Level 3 actor HTTP routes are derived from the registered
model name and class name; the router no longer synthesizes parent-scoped
join/nested routes from legacy `__owner__`, `__parent__`, or `__tagname__`
metadata.

#### What remains supported

| Concern | Route shape |
|---|---|
| Schema | `GET /{ClassName}` |
| Table-name collection | `GET /{tablename}` |
| Table-name create | `POST /{tablename}` |
| Table-name item | `GET /{tablename}/{id:int}` |
| Table-name update/delete | `PUT /{tablename}/{id:int}`, `DELETE /{tablename}/{id:int}` |
| Class-name collection mirror | `GET /{ClassName}/_` |
| Class-name create mirror | `POST /{ClassName}` |
| Class-name item mirror | `GET /{ClassName}/{id:int}` |
| Class-name update/delete mirrors | `PUT /{ClassName}/{id:int}`, `DELETE /{ClassName}/{id:int}` |
| Custom instance methods | `/{tablename}/{id:int}/{route}` and `/{ClassName}/{id:int}/{route}` |
| Custom class/static/actor methods | `/{tablename}/{route}` and `/{ClassName}/{route}` |
| Streaming methods | Same literal `@expose_route` paths, served as SSE |

Optional package-owned hooks remain supported: models can still contribute
view routes via `register_view_routes()` and capability-specific API routes via
`register_extra_routes()`.

#### Removed legacy route shapes

The actor HTTP adapter no longer generates these parent-scoped routes:

```text
/{parent_tablename}/{parent_id:int}/{child_tagname}
/{parent_tablename}/{parent_id:int}/{child_tagname}/{id:int}
/{ParentClass}/{parent_id:int}/{ChildClass}
/{ParentClass}/{parent_id:int}/{ChildClass}/{id:int}
/{ParentClass}/{parent_id:int}/{ChildClass}/{id:int}/{method}
```

Because those paths are gone, `NetworkAPI` also no longer injects a parent FK
from `parent_id`, sends `parent_id` in list TX payloads, or post-filters list
responses by parent FK. Relationship ownership should be represented in the
model/schema/storage contract, not in route synthesis.

#### Migration notes

If your client called parent-scoped actor routes, migrate to one of these
N3TX-native patterns:

1. **Use flat child model routes for explicit child/link records.**
   - Before: `POST /products/5/comments`
   - After: `POST /comments` or `POST /Comment`
   - Include the relationship field in the body when the child/link model owns
     an explicit FK/ref field, for example `{"product_id": 5, ...}`.

2. **Use parent model methods for domain-specific owned collections.**
   - Define a method such as `Product.comment(...)` with `@expose_route`.
   - Call `POST /Product/5/comment` or `POST /products/5/comment`.
   - Keep append/toggle/validation behavior inside the model method instead of
     encoding it in a generated nested route.

3. **Use schema-declared relationships plus populate for reads.**
   - Define local owned collections as model fields, for example
     `comments: list[Comment]`.
   - Read the parent with `GET /Product/5?populate=comments&depth=1` when the
     UI or caller needs related child data.

4. **Keep ownership and authorization at the model boundary.**
   - Use model fields, `__access__`, protected fields such as `user_owner`, and
     custom methods for ownership semantics.
   - Do not rely on a URL parent segment to imply authorization or persistence
     behavior.

This is a breaking cleanup for clients that depended on legacy join-route
generation in Level 3 actor routing. Flat routes, class-name mirrors, custom
methods, streaming methods, TX metadata, and two-tier authorization remain the
supported contract.

### Frontend: Hydrated relationship objects and flat child identity

The frontend runtime now consumes the simplified backend relationship contract
directly instead of converting hydrated owned children back into href arrays.

#### Runtime behavior

| Relationship | Frontend value |
|---|---|
| Owned scalar `T` | Hydrated child object |
| Owned collection `list[T]` | Ordered array of hydrated child objects |
| Explicit pointer `Ref[T]` | Ref string |
| Explicit pointer collection `list[Ref[T]]` | Ordered array of ref strings |

- Hydrated children are registered in the appropriate DynamicClass cache while
  remaining plain serializable objects in their parent value.
- Child `$id` values from the backend are authoritative. Attaching a component
  can no longer replace a flat child identity such as `/Comment/2` with a
  parent-scoped URL.
- Already-hydrated children render from the cache without an additional read.
- Optimistic like/favorite responses derive flat child identity from the target
  relationship schema instead of constructing `/Parent/id/field/child-id`.
- Legacy nested hash navigation aliases may still be parsed, but they mount the
  child through flat NTT identity such as `Comment/2`; they are not API routes or
  canonical entity identity.

#### Agent tools

`AgentActor.tools: list[AgentTool]` now renders its hydrated `AgentTool` records
directly. Agent cards display each tool's `target` and expose its escaped
description without fetching the tool again. Plain actor-address strings and
legacy URL strings retain compatibility rendering.

#### Frontend migration notes

1. Treat owned relationship values as objects, not href strings:

   ```diff
   - comments: ["/Product/1/Comment/2"]
   + comments: [{"id": 2, "$schema": "/Comment", "$id": "/Comment/2", ...}]
   ```

2. Use each child's `$id` for links and component refs. Do not derive identity
   from the parent entity, field name, or array position.
3. Keep pointer-specific code for `Ref[T]` and `list[Ref[T]]`; this release does
   not turn explicit refs into embedded owned objects.
4. Replace frontend routes or API calls that rely on
   `/Parent/id/Child/id` with flat child routes such as `/Child/id`, or use a
   schema-declared parent method for domain-specific mutations.
