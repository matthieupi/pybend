# Backend Unit Test Plan — PyBend Framework

> **Scope**: Every function, method, class, and behavior in the Python backend.
> **Framework**: pytest with mocking (unittest.mock), in-memory SQLite
> **Estimated test cases**: ~600+

---

## 1. PROTO_MODEL.PY — Base Model & Schema Generation

### 1.1 `ProtoModel.__init_subclass__(**kwargs)`

**Happy Path:**
- Model with `__storable__=True` gets StorableMixin injected into bases
- Model with `__storable__=False` does NOT get StorableMixin
- FK field annotations rewritten correctly (e.g., `user: User` → `user: Ref[User]`)

**Edge Cases:**
- Model with no `__storable__` attribute (defaults to False)
- Model inheriting from another storable model (double injection prevention)
- Model with multiple field types mixing Pydantic models and primitives
- Model with no fields besides inherited `id` and `image`
- Model with circular FK references (A references B, B references A)
- Empty model class

**Error Conditions:**
- FK field annotated with non-BaseModel type that looks like a model
- Model with conflicting field names after FK rewriting

### 1.2 `ProtoModel.__init__(self, *args, **kwargs)`

**Happy Path:**
- Normal initialization with multiple fields
- Initialization with `id=N` and other fields (uses provided values)
- Initialization with only `id=N` (retrieves from storage via `.get()`)
- `__owner__` set from kwargs

**Edge Cases:**
- `id=None` (should not trigger storage retrieval)
- `id=0` (falsy but technically valid)
- Empty kwargs dict
- `__owner__=None` passed explicitly
- Very large id values

**Error Conditions:**
- `id=N` with storage backend not set
- `id=N` for non-existent record (returns None from `.get()`)
- Non-storable model with `id=N`
- Invalid field values (Pydantic validation errors)

### 1.3 `ProtoModel.model_dump(*, response: bool = False, **kwargs)`

**Happy Path:**
- `model_dump()` returns clean dict with no metadata
- `model_dump(response=True)` includes `$schema` and `$id`
- `$schema` = `http://localhost:5000/{ClassName}`
- `$id` = `http://localhost:5000/{tablename}/{id}` when id exists

**Edge Cases:**
- id=None or id=0 (no `$id` URL)
- Model with no `__tablename__`
- response=True with empty config.API_URL
- Dumping model multiple times (idempotent)

**Error Conditions:**
- config.API_URL malformed or None
- Instance missing id attribute

### 1.4 `ProtoModel.__pybend_methods_json_signature__()`

**Happy Path:**
- Method with no parameters (besides self)
- Method with primitive parameters (str, int, float, bool)
- Method with Pydantic model parameters
- Method with return type, access control parameter
- Filters out 'self' and 'user' from parameters
- Identifies instance/class/static methods correctly

**Edge Cases:**
- Method with no @expose_route (skipped)
- Method with no return type annotation
- Method with optional/default parameters
- Method with *args and **kwargs
- Multiple methods on same model
- Method with same name in parent and child class

**Error Conditions:**
- Invalid @expose_route (missing route or methods)
- Method with unresolvable type hint

### 1.5 `ProtoModel.schema()`

**Happy Path:**
- Schema with auto-hidden fields (id, image, *_id, created_at, updated_at)
- Schema with __ui__ config, __access__ rules serialized, __protected_fields__
- Schema with methods and signatures, $defs for referenced models
- Each $defs entry gets $id URL, access rules, protected field markers

**Edge Cases:**
- Model with no methods, no referenced models (empty $defs)
- Model with self-referential parent_id (Ref['self'])
- Model with empty __ui__, __access__=None, __protected_fields__=set()
- Schema for join model (has __owner__ and __parent__)

**Error Conditions:**
- Referenced model doesn't exist in registry
- Circular reference in $defs
- access_schema() raises exception

### 1.6 `ProtoModel.referenced_json_schema()`

**Happy Path:**
- Ref[T] → `{"type": "$ref", "$ref": "#/$defs/T"}`
- Ref['self'] → `{"type": "selfref"}`

**Edge Cases:**
- Model with no Ref fields
- Model already in _referenced_models

### 1.7 `generate_join_model(owner_cls, ref_model, field_name=None)`

**Happy Path:**
- Creates join model with correct name (ProductComment)
- Sets __tablename__, __owner__, __parent__
- Adds FK field (product_id), caches on owner.__fk_models__

**Edge Cases:**
- field_name auto-resolved if not provided
- Multiple join models for same owner
- Join model already cached (idempotent)

**Error Conditions:**
- owner_cls not subclass of ProtoModel
- owner_cls.storage not set

### 1.8 `_apply_field_exclusion(schema)`

**Happy Path:**
- 'id', 'image', 'created_at', 'updated_at' get ui.display=false
- Fields ending in '_id' (except 'id') get ui.display=false
- Does not overwrite existing ui.display values

**Edge Cases:**
- Field already has ui.display=true (NOT overwritten)
- Schema has no properties
- Empty _AUTO_HIDE_FIELDS set

---

## 2. STORABLE_MIXIN.PY — CRUD Operations

### 2.1 `StorableMixin._storage_dict(exclude_unset=True)`

**Happy Path:**
- Returns dict with all model fields
- exclude_unset=True omits unset fields
- Re-adds Pydantic exclude=True fields

**Edge Cases:**
- Model with no fields, all fields unset
- Ref field containing model instance
- ListRef field containing href array

### 2.2 `StorableMixin.save(self)`

**Happy Path:**
- id=0/None → calls create()
- id>0 → calls update()

**Edge Cases:**
- id is falsy (0, "", None)
- Multiple saves on same instance

**Error Conditions:**
- Storage backend not set

### 2.3 `StorableMixin.set_storage(cls, storage)`

**Happy Path:**
- Storage backend assigned to cls.storage
- Can set before CRUD operations

**Edge Cases:**
- Called with None (clears)
- Called multiple times

### 2.4 `StorableMixin.create(cls, data)`

**Happy Path:**
- Simple model: creates record, returns instance with id
- Join model with __owner__: finds join_models, adds FK field
- Ref field unwrapped to int before insert

**Edge Cases:**
- data has __owner__ (join model), no __owner__ (normal)
- Ref field as model instance vs int
- Empty data dict

**Error Conditions:**
- join_models lookup fails
- Storage backend not set
- Database insert fails

### 2.5 `StorableMixin.list(cls, sql_filter=None, limit=None, offset=None, populate=None)`

**Happy Path:**
- No filter: all records
- With filter: WHERE clause applied
- limit=20: paginated response {data, meta}
- limit=None: unpaginated list (backward compat)
- populate loads nested entities

**Edge Cases:**
- limit=1, offset=0, offset beyond total
- Empty result set, single record
- sql_filter=None vs ("1=1", [])

**Error Conditions:**
- Storage not set, sql_filter malformed

### 2.6 `StorableMixin.get(cls, id, as_dict=False, populate=None)`

**Happy Path:**
- as_dict=False → model instance, as_dict=True → dict
- Record exists: found, doesn't exist: None
- populate loads nested entities

**Edge Cases:**
- id=0, id=None
- NULL fields coerced to defaults

### 2.7 `StorableMixin.update(cls, id, data)`

**Happy Path:**
- data as BaseModel → model_dump(exclude_unset=True)
- data as dict → used directly
- Unspecified fields unchanged

**Edge Cases:**
- data = {} (raises ValueError)
- data with extra fields (filtered)
- ListRef fields filtered out

**Error Conditions:**
- No valid fields (ValueError)
- Database update fails

### 2.8 `StorableMixin.delete(cls, id)`

**Happy Path:**
- Record deleted

**Edge Cases:**
- Record doesn't exist (silent no-op)

---

## 3. MODEL DEFINITIONS — Product, Comment, Like

### 3.1 Product Model

**Field Validation:**
- name: min_length=1, max_length=200 → test boundaries ("", "x", "x"*200, "x"*201)
- price: gt=0 → test 0.01, 0, -1, 999999.99
- description: default="" → test empty, very long
- comments: default=[] → test initially empty
- favorites: default=[] → test initially empty

### 3.2 Product.comment(self, comment, user)

**Happy Path:**
- Valid comment + user: comment added, user_owner set, saved
- comment.__owner__ set to self

**Edge Cases:**
- user=None, comment with parent_id (nested reply)

**Error Conditions:**
- comment is None, save fails

### 3.3 Product.favorite(self, user)

**Happy Path:**
- First call: Like created → {"action": "favorited"}
- Second call: Like removed → {"action": "unfavorited"}

**Edge Cases:**
- user=None, multiple users favorite same product

**Error Conditions:**
- join_models lookup fails

### 3.4 Comment Model

**Field Validation:**
- name: min_length=1, max_length=500
- parent_id: Optional[Ref['self']] — None or valid comment ID
- user_owner: protected field

### 3.5 Comment.like(self, user)

**Happy Path:**
- Toggle like on/off

### 3.6 Comment.reply(self, text, user)

**Happy Path:**
- Creates reply with parent_id=self.id, user_owner=user.id
- Saved to join table with product context

**Edge Cases:**
- text="", user=None, nested reply to a reply

### 3.7 Like Model

**Field Validation:**
- user: protected field
- created_at: default=""

---

## 4. REF.PY — Reference Types

### 4.1 `ListRef[T]`
- Produces `Annotated[List[Union[T, str]], _ListRefMarker(T)]`
- Serializes as list of strings (hrefs)
- _ListRefMarker captured for introspection

### 4.2 `_ListRefMarker`
- Created with model_type
- Stored in Annotated metadata

---

## 5. TYPER.PY — Ref Type & Utilities

### 5.1 `Ref[T]` Generic Type

**`Ref.__init__(value)`:**
- Ref(model_instance) → extracts model.id
- Ref(5) → stores id=5
- Ref({"id": 10}) → stores id=10
- Ref(None) → id=None
- Edge cases: Ref(0), Ref("5"), Ref(model with no id)
- Error: Ref("invalid"), Ref([])

**`Ref.__int__()`:** int(Ref(5)) → 5; Edge: int(Ref(None))

**`Ref.__str__()` / `__repr__()`:** str(Ref(5)) → "5"

**`Ref.__json__()`:** returns self.id

**`Ref.__get_pydantic_core_schema__`:** accepts int, string→int, Ref instance

**`Ref.__get_pydantic_json_schema__`:** Ref[User] → $ref, Ref no args → integer

### 5.2 `flatten_refs(obj)`
- Ref(5) → 5, nested models with Refs, lists of Refs
- Edge: empty object, no Refs, deep nesting

---

## 6. DECORATORS.PY — @expose_route

**`expose_route(route, methods=["POST"], access=None)`:**
- Adds __endpoint__ dict with route, methods, access
- Tests: methods=['GET'], ['PUT'], ['DELETE'], ['POST','PUT']
- access=None, OWNER, ROLE('admin'), OWNER | ROLE('admin')
- Edge: decorating non-method, invalid HTTP method

---

## 7. REGISTRAR.PY — Model Registry

### 7.1 `register_model(model_class, storage=None)`
- Storable model: storage set, table created, migrations run
- Non-storable model: added to registered_models
- Join model: added to join_models dict

### 7.2 `registered_models` / `join_models` Dicts
- Lookup by tablename / (parent, ref) tuple
- Edge: collision, empty registry

---

## 8. SQLITE_STORAGE.PY — SQLite Backend

### 8.1 `SQLiteStorage.__init__(database)`
- Happy path: default database.db, custom path
- Edge: ':memory:', absolute/relative paths

### 8.2 `SQLiteStorage.create(model_class, data)`
- Filters ListRef fields, unwraps Ref to ints, returns instance with id
- Edge: model with no fields, extra fields, BaseModel in data

### 8.3 `SQLiteStorage.list(model_class, ...)`
- No filter → SELECT *, with filter → WHERE, limit/offset → pagination
- Ref fields as hrefs, ListRef as href arrays, populate loads nested
- Edge: empty table, NULL values, FK table missing

### 8.4 `SQLiteStorage.get(model_class, id, ...)`
- Record exists → instance/dict, not found → None
- Ref/ListRef hydration, populate

### 8.5 `SQLiteStorage._populate_fields(model_class, instances, populate, conn, _visited)`
- Batch loads related entities, prevents cycles, respects depth
- Edge: no instances, circular refs, deep nesting

### 8.6 `SQLiteStorage.update(model_class, id, data)`
- Partial update, filters valid fields
- Error: empty data → ValueError

### 8.7 `SQLiteStorage.delete(model_class, id)`
- Record deleted; Edge: doesn't exist (no-op)

### 8.8 `SQLiteStorage.create_table(model_class)`
- id PRIMARY KEY AUTOINCREMENT, Ref→INTEGER, String→TEXT, Float→REAL
- ListRef fields skipped, parent FK columns auto-added

### 8.9 `SQLiteStorage.migrate_table(model_class)`
- Adds missing columns, removes orphaned, auto-adds FK columns

---

## 9. SQLITE_MIGRATION.PY — Schema Management

### 9.1 `Migration` Base Class
- up(cursor) / down(cursor) — abstract methods

### 9.2 `SQLiteMigration.__init__(database, migrations_dir)`
- Ensures _migrations table exists, migrations_dir created

### 9.3 `_ensure_migrations_table()`
- Creates id, name, applied_at table

### 9.4 `_get_applied_migrations()`
- Returns set of applied migration names

### 9.5 `_record_migration(name)` / `_unrecord_migration(name)`
- Track applied migrations

### 9.6 `create_table(model_class)`
- All model fields → SQL columns, type mapping, FK auto-detection
- Edge: no fields, Optional types, Ref with custom names

### 9.7 `migrate_table(model_class)`
- Missing column → ALTER ADD, orphaned → ALTER DROP, FK auto-add
- Edge: table doesn't exist, column already exists

### 9.8 `_discover_migrations()`
- Scans migrations/ for *.py files, sorted by filename
- Edge: no files, special files filtered

### 9.9 `_load_migration_class(filename)`
- Dynamically imports, finds Migration subclass
- Error: no subclass found

### 9.10 `run_migrations()`
- Discovers, skips applied, runs pending up(), records
- Error: up() raises → rollback + RuntimeError

### 9.11 `rollback(steps=1)`
- Rolls back last N in reverse, calls down(), unrecords
- Error: file not found, down() raises

### 9.12 `migration_status()`
- Returns {applied: [...], pending: [...]}

---

## 10. SQLITE_HELPERS.PY

### `get_parent_fk_columns(child_model_class)`
- Scans registered models for parents with ListRef[child]
- Returns [(parent_name_lower, fk_column_name)]
- Edge: no parents, multiple parents

---

## 11. AUTHORIZE/AUTH.PY — JWT & Password

### 11.1 `configure(*, jwt_secret, jwt_expiry_hours)`
- Sets global config, affects subsequent tokens
- Edge: called multiple times, with None, empty string

### 11.2 `hash_password(plain)`
- Returns bcrypt hash
- Edge: empty string, very long, special/unicode chars

### 11.3 `verify_password(plain, hashed)`
- Correct → True, wrong → False
- Edge: empty plain, malformed hash

### 11.4 `create_token(user_id, email, role)`
- Returns JWT with user_id, email, role, exp, iat
- Edge: user_id=0, email="", role="unknown"

### 11.5 `decode_token(token)`
- Valid → payload dict
- Expired → ExpiredSignatureError
- Tampered → InvalidSignatureError
- Malformed → DecodeError

---

## 12. AUTHORIZE/RULES.PY — Access Control Rules

### 12.1 `_Anyone` (ANYONE)
- evaluate(ctx) → always True
- sql_filter(ctx) → ("1=1", [])
- to_dict() → {"rule": "anyone"}

### 12.2 `_Authenticated` (AUTHENTICATED)
- Authenticated → True, unauthenticated → False
- sql_filter: N/A or ("1=1", []) when authenticated

### 12.3 `_Owner` (OWNER)
- user_id matches resource owner → True, mismatch → False
- resource=None (create) → True
- Custom owner field via _field='author_id'
- Href extraction from "http://.../users/5"
- sql_filter: "user_owner = ?" or "1=0"

### 12.4 `_Role` (ROLE)
- ROLE('admin') — role matches → True, doesn't → False
- ROLE('admin', 'moderator') — multiple roles
- Not authenticated → False

### 12.5 `Where` Rule
- Where(status='published') — field matches → True
- Operators: __lt, __gt, __lte, __gte, __ne, __in
- Multiple conditions (AND logic)
- sql_filter: "field = ?", "field < ?", etc.

### 12.6 `OrRule` (|)
- OWNER | ROLE('admin') — either True → True
- sql_filter: "(clause1) OR (clause2)"
- Edge: child sql_filter returns None → entire None

### 12.7 `AndRule` (&)
- AUTHENTICATED & Where(status='published') — both True → True
- sql_filter: "(clause1) AND (clause2)"

### 12.8 `NotRule` (~)
- ~OWNER — inverts
- sql_filter: "NOT (clause)"
- Double negation: ~~OWNER = OWNER

---

## 13. AUTHORIZE/CONTEXT.PY

### `AccessContext` Dataclass
- user_id, user_role, user_email properties from user dict
- is_authenticated checks user_id
- Frozen (immutable)
- Edge: user={}, resource=None, action='custom'

---

## 14. AUTHORIZE/RESOLVER.PY

### 14.1 `DefaultResolver.resolve_rule(model_class, action)`
- model.__access__['create'] → rule
- model.__access__['*'] → wildcard
- No __access__ → AUTHENTICATED

### 14.2 `DefaultResolver.authorize(ctx)`
- Rule True → no exception; False → AccessDenied

### 14.3 `DefaultResolver.sql_filter_for(ctx)`
- Rule has sql_filter → (clause, params)
- Rule has no sql_filter → None

---

## 15. AUTHORIZE/ERRORS.PY

### `AccessDenied`
- Raised with action, model, user_id
- Auto-constructed message
- Custom detail parameter

---

## 16. AUTHORIZE/SCHEMA.PY

### `access_schema(model_class)`
- No __access__ → {"*": AUTHENTICATED.to_dict()}
- __access__ dict → serialized rules
- Composite rules → {op: "or", rules: [...]}

---

## 17. ROUTES_FASTAPI.PY — HTTP Route Handlers

### 17.1 `_get_user(request)`
- Extracts user from request.state
- Edge: user=None, no attribute

### 17.2 `_build_context(request, model_class, action, resource, parent_id)`
- Returns AccessContext

### 17.3 `_serialize(instance)`
- model_dump(response=True) + _populated overlay

### 17.4 `register_route(path, fn, method)`
- GET/POST/PUT/DELETE

### 17.5 `make_create_instance(model_class)`
- Authorization, protected fields auto-injection, validation
- Edge: parent_id (join model), no data

### 17.6 `make_get_all_instances(model_class)`
- Pagination (limit/offset), populate, authorization SQL pushdown
- Join model: filtered by parent_id

### 17.7 `make_collection_list(model_class)`
- GET for join models across all parents

### 17.8 `make_get_schema(model_class)`
- Returns schema, optional scaffold

### 17.9 `make_get_instance(model_class)`
- GET by id, populate, authorization

### 17.10 `make_update_instance(model_class)`
- Protected fields stripped, partial update

### 17.11 `make_delete_instance(model_class)`
- Authorization, 404 if not found

### 17.12 `_resolve_user(type_hint, request)`
- StorableMixin subclass → .get(user_id)
- dict → raw JWT payload
- Not authenticated → None

### 17.13 `make_custom_post(attr, model_class, route_path)`
- Signature inspection, parameter parsing
- User parameter resolution
- Custom access rules from __endpoint__
- Instance method vs classmethod/staticmethod

---

## 18. CONFIG.PY

- BACKEND, VERSION, HOST, PORT, API_URL, SQLITE_DB_FILE
- JWT_SECRET from env or default
- JWT_EXPIRY_HOURS from env or default

---

## 19. SEED.PY

### `seed()` Function
- Creates users, products, comments, replies, likes, favorites
- Edge: DB already has data (skipped), --reset flag

---

## 20. UTILS/POPULATE.PY — Eager Loading

### `PopulateSpec`
- depth, fields, is_empty, should_populate, child_spec
- Edge: depth=0, empty fields, nested specs, limit

### `parse_populate(populate_param, depth_param)`
- "comments" → single field
- "comments,likes" → multiple
- "comments.likes" → nested
- Edge: None, empty string, malformed

---

## 21. UTILS/INTROSPECTION.PY

### `pydantic_schema_for_type(t)`
- str→string, int→integer, float→number, bool→boolean
- Ref[User]→$ref, BaseModel→$ref, list[T]→array, dict→object
- Edge: Union, Optional, unknown type

### `record_model_type(cls_, type_)`
- Adds type to _referenced_models
- Edge: already in set, nested collections

### `collect_all_referenced_models(cls_, seen)`
- Recursively collects all transitive refs
- Edge: no refs, circular (seen set prevents loop)

### `_is_self_ref(annotation)`
- Ref['self'] → True, Ref[User] → False

### `get_list_fields(model_class)` / `get_ref_fields(model_class)`
- Extracts ListRef and Ref fields from model
- Edge: no fields, multiple fields

---

## 22. INTEGRATION TESTS (Multi-component)

### Full CRUD Flow
- Create → Read → Update → Delete → Verify with DB

### Authentication Flow
- Register → hash verified → Login → token valid → expired token rejected

### Authorization Flow
- ANYONE/AUTHENTICATED/OWNER/ROLE rules correct
- SQL pushdown filters list correctly

### Relationships & FK Hydration
- ListRef → href arrays, populate → full objects
- Nested populate with depth

### Join Models
- Product.comment() creates via join table
- Comments under /products/1/comments

### Schema Generation
- All sections present, protected/hidden fields correct

### Custom Methods & User Injection
- Method parameters parsed, user resolved from JWT

### Protected Fields
- Auto-inject on create, strip on update

### Error Handling
- 400, 404, 403, 409, 422 — correct status codes and messages
