# N3TX Release Notes

## Unreleased

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
