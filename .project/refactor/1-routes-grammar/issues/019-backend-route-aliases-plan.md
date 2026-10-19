# Issue 019 Plan — Backend-Authoritative Route Aliases

## ✅ Recommendation

Implement backend route aliases as a **strict, additive model-name lookup layer**.

Aliases should create alternate public routes such as `/Agent` for a canonical
model class like `AgentActor`, but they must not create new model identities,
actor addresses, storage tables, schemas, or frontend DynamicClasses.

```python
class AgentActor(ActorModel):
    __tablename__ = 'agents'
    __route_aliases__ = ['Agent']
```

Target behavior:

```text
GET    /Agent               -> same schema body as /AgentActor
GET    /Agent/_             -> same collection as /AgentActor/_
POST   /Agent               -> same create behavior as /AgentActor
GET    /Agent/1             -> same entity as /AgentActor/1
PUT    /Agent/1             -> same update behavior as /AgentActor/1
DELETE /Agent/1             -> same delete behavior as /AgentActor/1
POST   /Agent/1/run         -> same method as /AgentActor/1/run
GET    /Agent/1/@           -> same view shell as /AgentActor/1/@
```

Canonical metadata remains canonical:

```json
{
  "__name__": "AgentActor",
  "canonical_name": "AgentActor",
  "__aliases__": ["Agent"],
  "__tablename__": "agents"
}
```

The best implementation is to compute aliases once during bootstrap/registration,
validate the full root route namespace, then let route-generation code iterate
over `canonical_name + aliases` when registering class-name grammar routes.

---

## 📍 Current State

| Area | Current behavior | Gap for issue 019 |
|---|---|---|
| Model registration | `registered_models` maps table name -> model class | No alias registry or validation |
| Schema metadata | `ProtoModel.schema()` emits `__name__`, `__tablename__`, `$id` | No `__aliases__` / `canonical_name` metadata |
| Direct routes | Registers `/ClassName`, `/ClassName/_`, `/ClassName/{id}`, `/ClassName/@...` | Need duplicate alias route registration using same handlers |
| Actor routes | `NetworkAPI` registers canonical class routes and dispatches to table-name actor target | Need alias route registration with same target and metadata |
| View routes | `ViewableMixin.register_view_routes()` owns `/ClassName/@...` | Needs alias parameter/hook support without core importing UI |
| Frontend | No alias lookup yet; issue 020 will consume schema metadata | Backend must expose alias metadata and schema routes first |
| Nested routes | Canonical nested class-name routes implemented | Alias interaction must be defined and implemented carefully |

---

## Architecture Invariants

1. **Aliases are route names, not model names.** The canonical class name remains
   `__name__`, schema `$id`, response `$schema`, and actor/tool identity.
2. **Aliases are backend-authoritative.** The frontend must learn aliases from
   schema metadata; no frontend-only aliases.
3. **Aliases do not create new storage or actor addresses.** All direct routes
   reuse canonical handlers; actor routes dispatch to the canonical table-name
   actor target.
4. **Aliases are additive.** Existing canonical class-name routes and legacy
   table-name routes remain unchanged.
5. **Aliases are case-sensitive.** `Agent` and `agent` are different tokens, but
   validation should discourage lowercase aliases that collide visually with
   table-name APIs.
6. **Root namespace validation is strict.** Alias collision bugs are public URL
   bugs and must fail at app build time.
7. **Nested alias support is explicit.** Root model aliases can appear in nested
   routes only after validation proves every segment resolves unambiguously.

---

## Alias Contract

### Model declaration

Preferred class variable:

```python
class Product(ProtoModel):
    __tablename__ = 'products'
    __route_aliases__ = ['CatalogItem', 'Item']
```

Rules:

- Type: `list[str]` or `tuple[str, ...]`.
- Empty or missing means no aliases.
- Aliases must be safe route tokens: `^[A-Z][A-Za-z0-9_]*$`.
- Aliases must not start with `@`.
- Aliases must not be `_`.
- Aliases must not contain `/`, `?`, `#`, `.`, `%`, or whitespace.

### Schema metadata

Add metadata to every canonical schema response:

```json
{
  "__name__": "AgentActor",
  "canonical_name": "AgentActor",
  "__aliases__": ["Agent"],
  "__tablename__": "agents"
}
```

Alias schema routes return the same canonical schema body:

```text
GET /Agent      -> body.__name__ == "AgentActor"
GET /AgentActor -> body.__name__ == "AgentActor"
```

This is the contract issue `020` uses to register alias lookups without creating
duplicate DynamicClasses.

### Identity behavior

Alias routes do **not** change response identity:

```text
GET /Agent/1
  -> $schema ends with /AgentActor
  -> $id ends with /AgentActor/1
```

Aliases are incoming route conveniences, not outgoing identity aliases.

---

## Collision and Validation Policy

Validation should run once during app build/registration, before route
registration.

Reject aliases that collide with:

| Collision target | Example | Why |
|---|---|---|
| Canonical class names | alias `Product` on another model | Root schema namespace conflict |
| Other aliases | `Agent` used by two models | Ambiguous lookup |
| Table names | alias `products` | Confuses legacy data API with schema/API grammar |
| Join table names | alias `products_comments` | Confuses collection routes |
| Reserved root routes | `auth`, `_meta`, `.well-known`, `index.html`, `static`, `ws` | Framework/system routes |
| Reserved grammar | `_`, `@`, `@profile`, `Agent/@` style aliases | `@` is a view marker, not a model name |
| Unsafe tokens | `../x`, `Agent/1`, `Agent?x=1`, `agent%2fadmin` | Path traversal / route ambiguity |

Recommended strict token regex:

```python
ALIAS_RE = re.compile(r'^[A-Z][A-Za-z0-9_]*$')
```

This intentionally keeps aliases class-like and distinct from lower-case table
names. If a product decision wants lower-case aliases later, it should include a
separate collision and OpenAPI policy.

---

## OpenAPI Policy

Recommendation: expose alias JSON API routes in OpenAPI by default, but make
their names clearly alias-prefixed and tag them with the canonical model tag.

Why:

- Alias routes are public API routes once declared.
- Hiding them makes generated API clients incomplete.
- Clear operation names avoid collisions.

Operation naming pattern:

```text
schema_Agent_alias
get_agents_alias_Agent
create_agents_alias_Agent
custom_agents_run_alias_Agent
```

HTML/view alias routes should stay `include_in_schema=False`, matching canonical
view route policy.

If this is too noisy, make exposure configurable later. Do not add a config flag
in the first implementation unless the current OpenAPI suite requires it.

---

## Data Structures

### `registrar.py`

Add alias registries next to existing global registries:

```python
registered_models: dict[str, type] = {}        # tablename -> model class
join_models: dict[tuple[str, str], type] = {}
route_aliases: dict[str, type] = {}            # alias -> canonical model class
model_aliases: dict[type, tuple[str, ...]] = {} # model class -> aliases
```

Add helpers:

```python
def get_route_aliases(model_class: type) -> tuple[str, ...]: ...
def validate_route_aliases(model_classes: Iterable[type]) -> None: ...
def rebuild_route_aliases(model_classes: Iterable[type]) -> None: ...
def route_names_for(model_class: type) -> tuple[str, ...]:
    return (model_class.__name__, *model_aliases.get(model_class, ()))
```

Keep `prepare_model()` pure if possible; alias validation can run over the final
prepared model set in `N3TXApp.build()` before `apply_registration()` side
effects.

### Validation source set

Validation should inspect all prepared classes:

```text
canonical class names: {cls.__name__}
tablenames:            {cls.__tablename__}
aliases:               cls.__route_aliases__
reserved roots:         framework reserved routes
```

Join models should usually **not** expose friendly aliases in issue 019. If a
generated join model declares aliases accidentally or via inheritance, ignore or
reject them unless explicitly allowed. Nested relation alias design belongs to a
future relation-aware phase.

---

## Backend Route Generation Plan

### Phase 1 — Alias registry and validation

Files:

- `packages/n3tx-core/src/n3tx_core/utils/registrar.py`
- `packages/n3tx-core/src/n3tx_core/app.py`
- `packages/n3tx-core/src/n3tx_core/tests/unit/test_registrar.py`
- `packages/n3tx-core/src/n3tx_core/tests/unit/test_app.py` if present, otherwise `test_routes.py`

Implementation sketch:

```python
def get_route_aliases(model_class):
    aliases = getattr(model_class, '__route_aliases__', ()) or ()
    if isinstance(aliases, str):
        raise ValueError('__route_aliases__ must be a list/tuple of strings')
    return tuple(aliases)

def rebuild_route_aliases(model_classes):
    route_aliases.clear()
    model_aliases.clear()
    validate_route_aliases(model_classes)
    for cls in model_classes:
        aliases = get_route_aliases(cls)
        if aliases:
            model_aliases[cls] = aliases
            for alias in aliases:
                route_aliases[alias] = cls
```

In `N3TXApp.build()`:

```python
prepared_classes = [result.model_class for result in preparations]
rebuild_route_aliases(prepared_classes)
```

Also clear alias registries when clearing `registered_models` / `join_models`.

Tests:

- accepts `__route_aliases__ = ['Agent']`.
- rejects string instead of list.
- rejects unsafe aliases.
- rejects alias colliding with class name.
- rejects alias colliding with tablename.
- rejects alias colliding with another alias.
- rejects reserved roots.

### Phase 2 — Schema metadata

Files:

- `packages/n3tx-core/src/n3tx_core/models/proto_schema.py`
- `packages/n3tx-core/src/n3tx_core/tests/unit/test_proto_schema.py` or existing schema tests

Implementation sketch in `metadata()` stage:

```python
aliases = tuple(getattr(cls, '__route_aliases__', ()) or ())
s['canonical_name'] = cls.__name__
s['__aliases__'] = list(aliases)
```

Keep schema `$id` canonical:

```python
s['$id'] = f'{config.API_URL}/{cls.__name__}'
```

Tests:

- canonical schema includes `canonical_name` and `__aliases__`.
- alias schema route returns identical canonical body.
- `$id` remains canonical class name.

### Phase 3 — Direct FastAPI alias routes

Files:

- `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py`
- `packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py`

Refactor target: replace single class route registration with iteration over
canonical + alias route names.

Helper shape:

```python
from n3tx_core.utils.registrar import route_names_for

def class_route_names(model_class):
    return route_names_for(model_class)
```

Schema:

```python
for route_name in route_names_for(model_class):
    router.get(f'/{route_name}', tags=[tag])(make_get_schema(model_class))
```

Root class JSON mirrors:

```python
for route_name in route_names_for(model_class):
    class_base = f'/{route_name}'
    router.post(class_base)(create_instance)
    router.get(f'{class_base}/_')(list_instances)
    router.get(f'{class_base}/{{id:int}}')(read_instance)
    router.put(f'{class_base}/{{id:int}}')(update_instance)
    router.delete(f'{class_base}/{{id:int}}')(delete_instance)
```

Literal methods:

```python
for route_name in route_names_for(model_class):
    class_route = f'/{route_name}/{{id:int}}{route}'
    router.add_api_route(class_route, handler, ...)
```

Nested alias route policy for issue 019:

Register nested route aliases only for the parent/child route-name combinations
that use validated aliases:

```text
/Agent/1/Comment/2          # parent alias
/Product/1/Feedback/2       # child alias if Comment aliases Feedback
/Agent/1/Feedback/2         # both aliases
```

This is powerful but increases route count. If this feels too broad for the
first alias slice, implement root aliases first and explicitly defer nested
alias combinations. Given issue 019 is a public URL decision, recommended first
implementation is:

```text
Root aliases:   implement now
Nested aliases: validate and document; implement only canonical nested routes now
```

Rationale: issue 020 can resolve hash aliases for root models first; nested alias
combinatorics can follow after browser tests prove root alias behavior.

Direct route tests:

- `GET /Alias` equals `GET /Canonical` and body is canonical.
- `POST /Alias`, `GET /Alias/_`, `GET /Alias/1`, `PUT /Alias/1`, `DELETE /Alias/1` mirror canonical routes.
- `POST /Alias/1/method` mirrors canonical method.
- `GET /Alias/1/@` returns HTML view shell if model is viewable.
- response `$schema`/`$id` remain canonical.
- alias routes do not register for non-storable JSON mirrors beyond schema unless canonical model would register them.

### Phase 4 — View route alias hook

Files:

- `packages/n3tx-ui/src/n3tx_ui/mixin.py`
- `packages/n3tx-ui/src/n3tx_ui/tests/test_viewable_mixin.py`
- `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py`
- `packages/n3tx-actors/src/n3tx_actors/api/network_api.py`

Current core/actor route generation delegates:

```python
register_view_routes(router, tag=tag)
```

Extend the protocol without hard-importing UI:

```python
register_view_routes(router, tag=tag, route_names=route_names_for(model_class))
```

For backward compatibility with custom hooks that only accept `router, tag`, use
signature inspection or a helper:

```python
def call_register_view_routes(hook, router, tag, route_names):
    try:
        hook(router, tag=tag, route_names=route_names)
    except TypeError:
        hook(router, tag=tag)
```

Preferred cleaner option: add a small utility in core route module and actor
route module to inspect `route_names` support. Avoid swallowing arbitrary
`TypeError` from inside hooks.

ViewableMixin then registers `/Agent/@...` and `/Agent/1/@...` alongside
canonical `/AgentActor/@...`.

### Phase 5 — Actor alias routes

Files:

- `packages/n3tx-actors/src/n3tx_actors/api/network_api.py`
- `packages/n3tx-actors/src/n3tx_actors/api/tests/test_network_api.py`

Use the same `route_names_for(model_class)` helper. Alias actor routes must
dispatch to canonical table-name actor target:

```python
TX(name='get', target='agents', meta={'model_cls': AgentActor})
```

Never dispatch to alias target:

```python
target='Agent'  # wrong
```

Tests:

- route generation includes `/Alias`, `/Alias/_`, `/Alias/{id:int}`, `/Alias/{id:int}/custom`.
- `GET /Alias` sends schema TX to canonical table-name target.
- CRUD aliases send same TX contract as canonical class routes.
- method aliases send same TX contract as canonical method routes.
- view aliases do not call `api.request()`.

### Phase 6 — Docs and issue handoff to 020

Files:

- `docs/CORE.md`
- `BACKEND.md`
- `FRONTEND.md` only to say frontend consumption is issue 020
- `packages/n3tx-core/docs/app-bootstrap.md`
- `packages/n3tx-actors/docs/network-adapters.md`

Docs should include:

- declaration syntax
- validation/collision policy
- canonical schema metadata
- response identity behavior
- OpenAPI policy
- limitation/deferment around nested alias combinations if deferred

---

## Recommended First Slice

Because issue 019 is HITL and public-URL-sensitive, land it as two commits:

### Commit 1 — Registry/schema decision

```text
feat(core): Add backend route alias registry [routes-grammar]
```

Includes:

- alias validation helpers
- alias registries
- schema metadata
- validation tests

This commit has no route behavior change beyond schema metadata and build-time
validation.

### Commit 2 — Direct/actor route aliases

```text
feat(api): Register class-name route aliases [routes-grammar]
```

Includes:

- direct FastAPI alias schema/CRUD/method routes
- actor alias schema/CRUD/method routes
- ViewableMixin alias route protocol
- tests and docs

This keeps the public routing change reviewable.

---

## Test Matrix

### Core alias validation

```python
class AgentActor(ProtoModel):
    __tablename__ = 'agents'
    __route_aliases__ = ['Agent']
```

Expected:

```text
route_aliases['Agent'] is AgentActor
model_aliases[AgentActor] == ('Agent',)
```

Invalid cases:

```text
__route_aliases__ = 'Agent'          -> ValueError
['Product'] collides with class name -> ValueError
['products'] collides with tablename -> ValueError
['@Agent'] unsafe/reserved           -> ValueError
['Agent/1'] unsafe                   -> ValueError
duplicate ['Agent'] across models    -> ValueError
```

### Direct API behavior

```text
GET    /Agent
GET    /Agent/_
POST   /Agent
GET    /Agent/1
PUT    /Agent/1
DELETE /Agent/1
POST   /Agent/1/run
GET    /Agent/1/@
```

Assertions:

- schema body has `__name__='AgentActor'`.
- schema body has `canonical_name='AgentActor'`.
- schema body has `__aliases__=['Agent']`.
- entity `$id` remains `/AgentActor/1`.
- alias routes match canonical class-name route responses.
- alias view route returns HTML and does not alter canonical component `ref`
  unless the view design intentionally keeps the alias ref. Recommendation:
  standalone alias view shells should mount canonical refs (`AgentActor/1`) so
  frontend cache identity stays canonical before issue 020.

### Actor API behavior

TX assertions for `/Agent/1`:

```python
tx.name == 'get'
tx.target == 'agents'
tx.meta['model_cls'] is AgentActor
```

TX assertions for `/Agent/1/run`:

```python
tx.name == 'run'
tx.target == 'agents'
tx.data['id'] == 1
```

### OpenAPI behavior

Assertions:

- alias JSON routes appear in OpenAPI if accepted policy is expose-by-default.
- alias HTML/view routes are hidden.
- operation IDs/names are unique.

---

## Risks and Mitigations

| Risk | Why it matters | Mitigation |
|---|---|---|
| Root namespace collision | `/Agent` can shadow schema/table/system routes | Strict build-time validation before route registration |
| Duplicate frontend classes | Alias schema route could create `Agent` DynamicClass | Schema returns canonical metadata; issue 020 maps alias to canonical |
| Actor address drift | Alias target could bypass canonical actor | Always dispatch to `model_class.__tablename__` |
| View route identity split | `/Agent/1/@` may mount alias refs before frontend alias support | Prefer canonical refs in alias HTML shells or coordinate with issue 020 |
| OpenAPI operation collisions | Same handler registered on many paths | Use unique alias route names/operation IDs |
| Nested alias combinatorics | Parent and child aliases multiply route count | Defer nested alias combinations unless explicitly required |

---

## Open Questions for Review

1. Should alias JSON routes be exposed in OpenAPI by default? Recommendation: yes.
2. Should nested alias combinations be implemented in issue 019 or deferred?
   Recommendation: defer route combinations; document the policy and keep nested
   canonical class names until issue 020/root aliases are stable.
3. Should alias view shells mount canonical refs or alias refs? Recommendation:
   canonical refs to avoid duplicate frontend identity before issue 020.
4. Should lowercase aliases ever be allowed? Recommendation: no for now; use
   class-like aliases only.

---

## Verification Commands

```bash
cd /workspace && /workspace/.venv/bin/python -m pytest \
  packages/n3tx-core/src/n3tx_core/tests/unit/test_registrar.py \
  packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py \
  packages/n3tx-actors/src/n3tx_actors/api/tests/test_network_api.py -q
```

If ViewableMixin is touched:

```bash
cd /workspace && /workspace/.venv/bin/python -m pytest \
  packages/n3tx-ui/src/n3tx_ui/tests/test_viewable_mixin.py -q
```

Broad backend smoke after the focused tests are green:

```bash
cd /workspace && python3 scripts/test-backend.py --short
```

---

## Critical Files for Implementation

- `packages/n3tx-core/src/n3tx_core/utils/registrar.py`
- `packages/n3tx-core/src/n3tx_core/models/proto_schema.py`
- `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py`
- `packages/n3tx-actors/src/n3tx_actors/api/network_api.py`
- `packages/n3tx-ui/src/n3tx_ui/mixin.py`
