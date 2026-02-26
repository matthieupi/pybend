# PyBend Through the Category Theory Lens

**Mapping PyBend's Architecture to Categorical Structures**

*Research Document -- February 2026*

---

## Executive Summary

PyBend is a schema-driven full-stack framework where a single Python model
definition generates an API, database schema, JSON Schema, access control,
and a runtime frontend. This document analyzes PyBend's architecture through
the formal lens of category theory (CT), identifying where its abstractions
already embody categorical structures, where the functor laws hold, and where
they break. The goal is not academic decoration but actionable insight: by
understanding *which* categorical laws PyBend's pipeline satisfies and *which*
it violates, we can identify concrete opportunities to make its abstractions
more composable, more predictable, and more testable.

**Key findings:**
- PyBend's `Model -> Schema -> DynamicClass` pipeline is a composition of two
  functors that *mostly* preserves structure, with specific, enumerable points
  of failure.
- The `AccessRule` algebra is already a well-formed Boolean algebra (a
  Heyting algebra), and `evaluate()` is a proper functor to `Bool`.
- The Actor/Matrix messaging system forms a category with known deficiencies
  in associativity that can be remedied.
- The `model_dump()` / `Model(**dict)` pair approximates an adjunction but
  fails the unit/counit laws due to metadata injection and lossy serialization.
- Eight specific impurities are identified with concrete paths to resolution.

---

## 1. Categorical Foundations in PyBend

### 1.1 The Categories at Play

PyBend's architecture spans several implicit categories:

```
Category          Objects                  Morphisms
-----------       ----------------------   ----------------------------------
PyModel           Python model classes     Model transformations (subclassing,
                                           generate_join_model)
JSchema           JSON Schema documents    Schema transformations ($defs
                                           inclusion, field projection)
JSType            JavaScript classes       Class creation (prototype()),
                                           instantiation
SQLStore          SQL tables + rows        SQL operations (INSERT, SELECT,
                                           UPDATE, DELETE)
BoolAlg           {True, False}            Logical connectives
ActorMsg          Actor instances          TX messages (send, inbox, dispatch)
HTTPEnd           HTTP endpoints           Route handlers (GET, POST, PUT,
                                           DELETE)
```

The entire PyBend pipeline can be understood as functors and natural
transformations between these categories.

---

## 2. The Model-to-Schema Functor

### 2.1 Definition

The function `ProtoModel.schema()` maps from **PyModel** to **JSchema**:

```
F_schema : PyModel -> JSchema
F_schema(ModelClass) = ModelClass.schema()
```

Concretely, this is defined at line 199 of
`/workspace/src/pybend/core/models/proto_model.py`:

```python
@classmethod
def schema(cls) -> Dict[str, Any]:
    # ...
    referenced_models = collect_all_referenced_models(cls)
    schema = cls.model_json_schema(ref_template="#/$defs/{model}")
    # ... adds methods, access, ui, $defs, $schema, $id
    return copy.deepcopy(schema)
```

### 2.2 Does It Preserve Identity?

A functor must map the identity morphism to the identity morphism:
`F(id_A) = id_{F(A)}`.

The "identity" in **PyModel** is the base model with no fields beyond the
defaults. `ProtoModel` itself has `id: int` and `image: str` (line 62-63).

```python
class Empty(ProtoModel):
    __tablename__ = 'empty'
    __storable__ = True
```

`Empty.schema()` returns:

```json
{
  "$schema": "http://localhost:5000/Schema",
  "$id": "http://localhost:5000/Empty",
  "properties": { "id": {...}, "image": {...} },
  "methods": {},
  "access": {"*": {"rule": "authenticated"}}
}
```

**Verdict: PARTIAL.** The schema of the "empty" model is not empty -- it
carries `$schema`, `$id`, `access`, and the inherited `id`/`image` fields.
This is a *faithful* representation (no information is lost), but the functor
adds metadata that has no pre-image in the source category. In CT terms,
`F_schema` is not the identity on the terminal object.

This is analogous to a *pointed* functor -- it adjoins a base point
(`$schema`, `$id`) to every object in the target category.

### 2.3 Does It Preserve Composition?

Composition in **PyModel** means: if model A contains a `ListRef[B]`, then A
is "composed with" B. The functor should satisfy:

```
F_schema(A o B) = F_schema(A) o F_schema(B)
```

In practice, when `Product` contains `comments: ListRef[Comment]`:

1. `Product.schema()` calls `collect_all_referenced_models(Product)` which
   discovers `Comment`.
2. `Comment.referenced_json_schema()` is called (line 229).
3. The result is injected into `Product`'s schema under `$defs.Comment`
   (line 236).
4. `$defs.Comment` receives its own `$id`, `methods`, `access`, and `ui`
   (lines 244-307).

```
Product.schema().$defs.Comment  ~=  Comment.schema()  (minus top-level metadata)
```

**Verification:**

```
Product.schema() produces:
  properties.comments -> { type: "array", items: { $ref: "#/$defs/Comment" } }
  $defs.Comment -> { properties: {...}, methods: {...}, access: {...}, $id: "..." }

Comment.schema() produces:
  { $schema: "...", $id: "...", properties: {...}, methods: {...}, access: {...} }
```

The `$defs.Comment` entry matches `Comment.schema()` structurally, but with
two differences:
- `$defs.Comment` has no `$schema` field (only `$id`).
- `$defs.Comment` may have its own `$defs` removed to prevent circular
  references (line 231: `defs = ref_schema.pop('$defs', {})`).

**Verdict: NEAR-PRESERVATION.** The composition law holds at the structural
level (nested models produce nested schemas). The law breaks at the metadata
level: `$schema` is stripped from nested schemas, and transitive `$defs` are
flattened to the top level rather than nested. This is a deliberate design
choice (JSON Schema's `$defs` are scoped to the root document), but it means
the functor is *faithful* (injective on morphisms) but not *full* (there
exist schema transformations with no corresponding model transformation).

### 2.4 The Functor Laws -- Summary

```
                  Identity        Composition
                  Preservation    Preservation
Model->Schema     PARTIAL (*)     NEAR (**)

(*)  Adds $schema, $id, access defaults; not zero on terminal object
(**) Flattens nested $defs; strips $schema from nested entries
```

### 2.5 Where the Functor Law Breaks

The precise points of failure, with line references:

| Breakage | Location | Effect |
|----------|----------|--------|
| Metadata injection | `proto_model.py:310-311` | Every schema gets `$schema` + `$id` regardless of model content |
| Access default | `proto_model.py:256` | Models without `__access__` get `AUTHENTICATED` default injected |
| Field exclusion | `proto_model.py:259` | `_apply_field_exclusion()` mutates schema based on naming conventions, not model structure |
| `$defs` flattening | `proto_model.py:231-232` | Transitive references are bubbled up and merged, destroying nesting hierarchy |
| Protected fields | `proto_model.py:262-266` | `__protected_fields__` adds `ui.protected` markers with no corresponding model-level annotation |

---

## 3. The Schema-to-DynamicClass Functor

### 3.1 Definition

The `prototype()` function in `/workspace/src/pybend/static/core/NTT.js`
(line 663) maps from **JSchema** to **JSType**:

```
F_proto : JSchema -> JSType
F_proto(schema) = prototype(addr, schema, href)
```

### 3.2 Structure Preservation

The functor processes schema properties into typed getters/setters (lines
725-758) and schema methods into callable functions (lines 763-791):

```javascript
// Line 731-754: For each field in schema.properties
Object.defineProperty(DynamicClass.prototype, field, {
    get() { return this.value?.[field] },
    set(value) {
        if (isReadonly) throw new Error(...);
        if (!isTypeCompatible(value, expectedType)) throw new TypeError(...);
        this.value[field] = value;
        this.notify(field, value, oldValue);
    },
});
```

**Key structural mappings:**

```
Schema Property          DynamicClass Feature
-----------------        -------------------------
properties[f].type       -> type-checked setter
properties[f].readOnly   -> read-only getter (throws on set)
properties[f].title      -> DynamicClass.labels[f]
methods[m].route         -> prototype method calling this.call(m, ...)
methods[m].parameters    -> parameter validation before call
$defs[D]                 -> separate DynamicClass (registered in NTT.SCHEMA)
```

### 3.3 Nested Schema Handling

`NTT.SCHEMA()` (line 390) processes `$defs` before creating the main
DynamicClass:

```javascript
// Line 397-407: Register nested schemas first
if (data.$defs && typeof data.$defs === 'object') {
    for (const [key, value] of Object.entries(data.$defs)) {
        if (key === addr) continue;
        if (value.type === 'object' && value.properties && !NTT.has(key)) {
            const DC = prototype(key, value, defHref);
            NTT.#prototypes.set(key, DC);
            NTT.#replayWaiting(key, DC);
        }
    }
}
```

**Composition verification:**

```
F_proto(ProductSchema)  produces:
  - DynamicClass("Product") with typed properties
  - DynamicClass("Comment") registered from $defs.Comment
  - Product.instances: Map<id, NTT>
  - Comment.instances: Map<id, NTT>

F_proto(CommentSchema)  produces:
  - DynamicClass("Comment") with typed properties
```

**Verdict: PRESERVES COMPOSITION** with caveats. If `Comment` is already
registered (from a prior `SCHEMA` call), the `!NTT.has(key)` guard (line
400) prevents re-registration. This makes the functor *idempotent* on nested
types, which is desirable but means `F_proto(A.schema) != F_proto(A.schema)`
on repeated application (the second call is a no-op for `$defs`).

### 3.4 Information Loss in the Schema-to-Class Functor

The `prototype()` functor loses certain schema information:

| Schema Feature | DynamicClass Equivalent | Preserved? |
|----------------|------------------------|------------|
| `type` | Type-checking in setter | YES |
| `minLength`, `maxLength` | NOT checked in setter | NO |
| `minimum`, `maximum` | NOT checked in setter | NO |
| `pattern` | NOT checked in setter | NO |
| `ui.widget` | Not in DynamicClass; consumed by `form.js` | DEFERRED |
| `access` | Not in DynamicClass; consumed by `Permissions.js` | DEFERRED |
| `$defs` | Separate DynamicClasses | YES |
| `methods` | Prototype methods | YES |

The functor is **faithful but not full**: it maps every schema to a class,
but it does not capture all schema constraints in the class itself. Some
constraints are "deferred" to rendering-time consumption by other components.

---

## 4. The Storage Adjunction

### 4.1 The Forgetful Functor

The storage layer implements a *forgetful functor* from **PyModel** to
**SQLStore**:

```
U : PyModel -> SQLStore
U(ModelClass) = SQL table with columns for scalar fields
```

This functor "forgets":
- Methods (only data is stored)
- Access rules (not persisted)
- UI hints (not persisted)
- Collection fields (stored in separate join tables, not in the parent row)
- Behavioral mixins (Observable, Actor patterns)

The implementation is in `/workspace/src/pybend/core/storage/sqlite_storage.py`.
The `create()` method (line 93) explicitly excludes collection fields:

```python
collection_field_names = {name for name, _cls in get_list_fields(model_class)}
fields = [f for f in model_class.model_fields.keys()
          if f != 'id' and f not in collection_field_names]
```

### 4.2 The Free Functor (Hydration)

The left adjoint to the forgetful functor is the *hydration* operation:
constructing a rich model instance from a SQL row.

```
F : SQLStore -> PyModel
F(row) = model_class(**record)
```

In `sqlite_storage.py`, the `get()` method (line 240) performs hydration:

```python
record = dict(zip(columns, row))
# ... coerce NULLs, hydrate Ref fields as href URLs ...
# ... hydrate collection fields as href arrays ...
instance = model_class(**data)
```

### 4.3 Does This Form an Adjunction?

An adjunction `F -| U` requires natural transformations:
- **Unit** `eta: Id -> U . F` (embed -> forget -> reconstruct should be identity)
- **Counit** `epsilon: F . U -> Id` (reconstruct -> embed should be identity)

**Testing the Unit (`model -> dump -> reconstruct`):**

```python
product = Product(id=1, name="Widget", price=9.99)
dumped = product.model_dump()           # U(product)
reconstructed = Product(**dumped)       # F(U(product))
assert reconstructed == product         # eta: Id -> U.F ?
```

This *almost* works, but fails when:
1. Collection fields (`comments`) are empty lists in the model but become
   href arrays after storage hydration.
2. `model_dump(response=True)` adds `$schema` and `$id` which are not
   model fields. The `Config.extra = 'allow'` (line 67) lets them pass
   through, but they leak into the reconstructed instance.

**Testing the Counit (`row -> model -> dump`):**

```python
row_dict = {"id": 1, "name": "Widget", "price": 9.99, "image": ""}
instance = Product(**row_dict)          # F(row)
dumped = instance.model_dump()          # U(F(row))
assert dumped == row_dict               # epsilon: F.U -> Id ?
```

This fails when:
1. Default values are injected (e.g., `image` defaults to `''`).
2. Collection fields get default `[]` from the model but don't exist in the
   raw row dict.

**Verdict: APPROXIMATE ADJUNCTION.** The unit and counit hold for the
"scalar field" subspace but break on collection fields, metadata injection,
and default values.

### 4.4 The Adjunction Diagram

```
                    U (forgetful)
    PyModel ────────────────────> SQLStore
       |                             |
       |  eta (unit)                 |  epsilon (counit)
       |  model_dump()               |  Model(**dict)
       v                             v
    SQLStore <──────────────────── PyModel
                    F (free/hydration)


    Round-trip breakage points:

    Model -> dump -> Model:
      * Collection fields: ListRef[] -> [] (not href arrays)
      * response=True: $schema/$id injected, leak into reconstructed model

    Row -> Model -> dump:
      * Default values injected (image='', comments=[])
      * Ref fields hydrated to href strings, not raw ints
```

---

## 5. Actor Messaging as a Category

### 5.1 Category Definition

The Actor system defined in `/workspace/src/pybend/static/core/Actor.js` and
`/workspace/src/pybend/static/core/Matrix.js` forms a category:

```
Category ActorMsg:
  Objects:    Actor instances (and classes, which are also actors)
  Morphisms:  TX messages (source -> target)
  Identity:   Self-addressed TX (actor sending to itself)
  Composition: Message forwarding through the hierarchy
```

### 5.2 Message Routing as Composition

A TX object (`/workspace/src/pybend/static/core/TX.js`, line 7) carries:

```javascript
constructor(event) {
    this.name = name       // method name to invoke
    this.source = source   // sender address
    this.target = target   // recipient address
    this.data = data       // payload
    this.meta = meta       // routing metadata
    this.tst = timestamp   // temporal ordering
}
```

The Matrix (`Matrix.js`, line 26) routes messages:

```javascript
inbox(event) {
    let tx = event instanceof TX ? event : new TX(event);
    let targetAddr = tx.target.split('/')[0];

    if (tx.name === E.connect) {
        tx = this.connect(tx.source, tx.target);
    } else if (this.children.has(targetAddr)) {
        tx = this.children.get(targetAddr).inbox(tx.repr());
    } else {
        tx = this.remote.send(tx);
    }
    return tx;
}
```

### 5.3 Associativity of Message Chains

For a category, composition must be associative:
`(A -> B -> C) = A -> (B -> C)`

In the Actor system, message forwarding happens through `Actor._send()`
(Actor.js, line 62):

```javascript
static _send(event) {
    let tx = event instanceof TX ? event : new TX(event);
    const children = Type.children;

    // Case 1: target is a direct child
    if (children && children.has(targetParent)) {
        children.get(targetParent).inbox(tx.repr());
    }
    // Case 2: target is /this.addr/child-addr
    else if (targetParent === this.addr) {
        children.get(targetChild).inbox(tx.repr());
    }
    // Case 3: bubble to root Matrix
    else {
        tx.source = tx.source ? `${typeAddr}/${tx.source}` : typeAddr;
        return ROOT_ACTOR.inbox(tx.repr());
    }
}
```

**Associativity analysis:**

Consider three actors A, B, C where A sends to B which forwards to C:

```
Path 1: A.send(TX{target:B}) -> B.inbox() -> B.send(TX{target:C}) -> C.inbox()
Path 2: A.send(TX{target:C, via:B}) -- no direct support for routing chains
```

**Verdict: NOT ASSOCIATIVE in the general case.** The Actor system supports
direct routing (parent -> child) and hierarchical bubbling (up to Matrix),
but there is no explicit composition operation for chaining messages. Each
`send()` is an independent dispatch. Message chains are *sequential* but not
*composable* in the categorical sense.

However, the system does preserve identity: an Actor can receive its own
messages via the `_inbox` dispatch (Actor.js, line 131-149):

```javascript
static _inbox(event) {
    const tx = event instanceof TX ? event : new TX(event);
    if (tx.target === `/${Type.addr}` || tx.target === Type.addr) {
        if (typeof this[tx.name] === "function") {
            return this[tx.name](tx.data, tx);
        }
    } else {
        Type.send(event);
    }
}
```

### 5.4 The Actor Category -- Refined Assessment

```
Property          Status    Notes
Identity          HOLDS     Actor.inbox dispatches to self handlers
Associativity     PARTIAL   Sequential dispatch, no explicit chain composition
Composition       IMPLICIT  Matrix routes; no first-class composed morphisms
Closure           HOLDS     All TX produce TX (or void); system is closed
```

The Actor system is closer to a **semicategory** (composition is partial)
or, more precisely, a **message-passing algebra** than a strict category.

---

## 6. AccessRules as a Boolean Algebra

### 6.1 The Algebraic Structure

The `AccessRule` hierarchy in
`/workspace/src/pybend/core/authorize/rules.py` defines:

```python
class AccessRule(ABC):
    def evaluate(self, ctx: AccessContext) -> bool: ...
    def to_dict(self) -> Dict[str, Any]: ...

    def __or__(self, other) -> OrRule: ...    # line 30-31
    def __and__(self, other) -> AndRule: ...  # line 33-34
    def __invert__(self) -> NotRule: ...      # line 36-37
```

With concrete leaf rules:
```
ANYONE       : evaluate(ctx) = True                    (top element)
AUTHENTICATED: evaluate(ctx) = ctx.is_authenticated    (predicate)
OWNER        : evaluate(ctx) = resource.owner == user  (predicate)
ROLE(r)      : evaluate(ctx) = ctx.user_role in r      (predicate)
Where(**cond): evaluate(ctx) = all(cond match resource) (predicate)
```

### 6.2 Boolean Algebra Verification

A Boolean algebra requires:
- **Closure**: `|`, `&`, `~` produce `AccessRule`. *Verified* (lines 30-37).
- **Associativity**: `(A | B) | C = A | (B | C)`. *Verified* -- `OrRule`
  flattens to `any(r.evaluate(ctx) for r in self.rules)` (line 51).
- **Commutativity**: `A | B = B | A`. *Verified* -- `any()` is order-
  independent on booleans.
- **Distributivity**: `A & (B | C) = (A & B) | (A & C)`. *Verified* at the
  `evaluate()` level since `and`/`or`/`not` on booleans are distributive.
- **Identity elements**: `ANYONE` is top (always True), and a hypothetical
  `NOBODY` would be bottom (always False). *Partial* -- no explicit bottom
  element exists.
- **Complement**: `~ANYONE` should be bottom. *Verified* -- `NotRule(ANYONE)`
  evaluates to `False` for all contexts.

**Verdict: WELL-FORMED BOOLEAN ALGEBRA** (technically a bounded lattice
lacking only an explicit bottom element).

### 6.3 `evaluate()` as a Functor

```
F_eval : BoolAlg(AccessRule) -> Bool
F_eval(rule) = rule.evaluate(ctx)
```

This is a **Boolean algebra homomorphism** (and therefore a functor from
the category of AccessRules to Bool):

```python
# OrRule.evaluate (line 50-51):
def evaluate(self, ctx):
    return any(r.evaluate(ctx) for r in self.rules)

# Homomorphism: F_eval(A | B) = F_eval(A) or F_eval(B)  CHECK

# AndRule.evaluate (line 73-74):
def evaluate(self, ctx):
    return all(r.evaluate(ctx) for r in self.rules)

# Homomorphism: F_eval(A & B) = F_eval(A) and F_eval(B)  CHECK

# NotRule.evaluate (line 96-97):
def evaluate(self, ctx):
    return not self.rule.evaluate(ctx)

# Homomorphism: F_eval(~A) = not F_eval(A)               CHECK
```

### 6.4 `to_dict()` as a Natural Transformation

The `to_dict()` method maps from the **AccessRule** functor to a **JSON
serialization** functor:

```
eta : F_rule -> F_json
eta_A = A.to_dict()
```

This is a natural transformation because the diagram commutes:

```
AccessRule A ──evaluate()──> Bool
     |                         |
  to_dict()              JSON.parse(to_dict()) -> re-evaluate
     |                         |
     v                         v
  JSON dict ──deserialize──> AccessRule A' ──evaluate()──> Bool

The naturality condition requires:
  evaluate(deserialize(to_dict(A))) = evaluate(A)
  for all A and all contexts ctx.
```

**Verdict: NATURAL TRANSFORMATION** -- `to_dict()` faithfully serializes
the rule structure. Each composite rule serializes its children recursively:

```python
# OrRule.to_dict (line 64-65):
def to_dict(self):
    return {"op": "or", "rules": [r.to_dict() for r in self.rules]}
```

The one gap: there is no `from_dict()` deserializer in the codebase, so the
transformation is one-way. The naturality square is *open* on the
deserialization side.

### 6.5 `sql_filter()` as a Second Natural Transformation

```
eta_sql : F_rule -> F_sql
eta_sql(A) = A.sql_filter(ctx)
```

This maps rules to SQL WHERE clauses, preserving the Boolean structure:

```python
# OrRule.sql_filter (line 53-62):
def sql_filter(self, ctx):
    parts, params = [], []
    for r in self.rules:
        f = r.sql_filter(ctx)
        if f is None: return None    # <-- escape hatch breaks naturality
        parts.append(f"({clause})")
        params.extend(p)
    return (" OR ".join(parts), params)
```

**Naturality breakage:** When any child rule returns `None` from
`sql_filter()`, the entire composite returns `None`. This means:

```
evaluate(OWNER | Where(status="draft"))  may be True
sql_filter(OWNER | Where(status="draft"))  returns a valid SQL clause

But:
sql_filter(OWNER | CustomRule())  returns None
```

The `None` return acts as an **absorbing element** that breaks the
homomorphism property. This is deliberate (it signals "cannot push down to
SQL") but means `sql_filter` is a *partial* natural transformation.

---

## 7. The Full Pipeline: Commutative Diagram

### 7.1 The Ideal Diagram

```
                    F_schema                    F_proto
  PyModel ────────────────────> JSchema ──────────────────> JSType
     |                            |                           |
     | model_dump()               | JSON.stringify()          | .value getter
     |                            |                           |
     v                            v                           v
  PyDict ─────────────────────> JSON ────────────────────> JSObject
                serialize                   JSON.parse
```

### 7.2 Commutativity Check

**Left square (Model -> Dict -> JSON vs Model -> Schema -> JSON):**

```python
# Path 1: Model -> Dict -> JSON
product = Product(id=1, name="Widget", price=9.99)
dict_result = product.model_dump()
json_result_1 = json.dumps(dict_result)

# Path 2: Model -> Schema -> ... (schema is not per-instance)
# The schema describes the TYPE, not the INSTANCE.
```

**This square does not commute** because the left column operates on
*instances* while the top row operates on *types*. The schema functor maps
model *classes* to JSON Schema *documents*, while `model_dump()` maps model
*instances* to JSON *data*. These are morphisms in different categories.

The correct diagram separates type-level and instance-level:

```
TYPE LEVEL:

  ModelClass ──schema()──> JSON Schema ──SCHEMA()──> DynamicClass
                                                         |
                                                    .instances (Map)
                                                         |
                                                         v
INSTANCE LEVEL:                                    NTT instances

  model_instance ──model_dump(response=True)──> JSON data ──new DC(data)──> NTT
       |                                            |                         |
       | .id                                        | .id                     | .addr
       v                                            v                         v
    Integer                                      Integer                   String
```

### 7.3 Where the Instance-Level Diagram Commutes

```python
# Backend:
product = Product(id=1, name="Widget", price=9.99)
response = product.model_dump(response=True)
# response = {"$schema": ".../Product", "$id": ".../products/1",
#             "id": 1, "name": "Widget", "price": 9.99, "image": ""}
```

```javascript
// Frontend (after JSON transport):
const data = JSON.parse(responseText);
const instance = new DynamicClass(data);
// instance.value = data
// instance.value.$schema = ".../Product"  (injected by value getter, line 696)
// instance.value.$id = instance.href      (injected by value getter, line 697)
```

**Commutativity check:**

```
Backend: model_dump(response=True).$schema == "http://.../Product"
Frontend: instance.value.$schema           == "http://.../Product"  (from config)

Backend: model_dump(response=True).$id     == "http://.../products/1"
Frontend: instance.value.$id              == instance.href         == "http://.../products/1"
```

**Verdict: COMMUTES for $schema and $id.** The frontend value getter (NTT.js
lines 691-698) independently reconstructs the same metadata that the backend
injects. This is a form of *naturality*: both paths produce the same result.

**Where it breaks:**

The DynamicClass value getter (line 696-697) computes `$schema` and `$id`
from the class name and instance href, *overwriting* whatever the backend
sent. If the backend's `config.API_URL` differs from the frontend's
`config.API_URL` (e.g., behind a proxy), the values diverge:

```javascript
// Line 696-697 in NTT.js:
get value() {
    let data = this._data;
    data["$schema"] = `${config.API_URL}/${this.constructor.addr}`;
    data["$id"] = this.href;
    return this._data;
}
```

This overwrites backend-provided `$schema`/`$id` with frontend-computed
values. The diagram commutes only when `backend.config.API_URL ==
frontend.config.API_URL`.

---

## 8. Natural Transformations in PyBend

### 8.1 `model_dump()` vs `model_dump(response=True)`

These are two functors from **PyModel** instances to **PyDict**:

```
F_plain    : Instance -> Dict       (model_dump())
F_response : Instance -> Dict       (model_dump(response=True))
```

The natural transformation `eta: F_plain -> F_response` is defined at
`proto_model.py` lines 117-137:

```python
def model_dump(self, *, response: bool = False, **kwargs) -> Dict[str, Any]:
    data = super().model_dump(**kwargs)
    if response:
        data = {
            '$schema': meta['schema_url'],
            '$id': f"{meta['base_url']}/{instance_id}",
            **data
        }
    return data
```

**Naturality verification:**

For any model morphism `f: A -> B` (e.g., `Product -> ProductComment`):

```
eta_A . F_plain(a) == F_response(a) . eta_A

model_dump(response=True)(product) ==
    {"$schema": ..., "$id": ..., **model_dump()(product)}
```

This holds trivially because `response=True` simply prepends two keys.
The transformation is natural because it does not depend on the specific
model class -- it works uniformly for all `ProtoModel` subclasses using
cached class-level metadata (lines 124-130).

### 8.2 `@expose_route` as a Natural Transformation

The `@expose_route` decorator (`/workspace/src/pybend/core/utils/decorators.py`)
transforms Python methods into HTTP endpoints:

```
eta_route : F_method -> F_http
eta_route(method) = HTTP endpoint at route_path
```

The decorator itself is minimal (lines 3-19):

```python
def expose_route(route, methods=["POST"], access=None):
    def decorator(func):
        func.__endpoint__ = {
            'route': route,
            'methods': methods,
            'access': access,
        }
        return func
    return decorator
```

The actual transformation happens in `routes_fastapi.py` lines 428-493,
where `register_routes()` discovers `__endpoint__`-annotated methods and
creates FastAPI route handlers:

```python
for attr_name in dir(model_class):
    attr = getattr(model_class, attr_name)
    if callable(attr) and hasattr(attr, '__endpoint__'):
        handler = make_custom_post(attr, model_class, full_route)
        router.add_api_route(full_route, handler, methods=methods, ...)
```

**Naturality:** This transformation is natural in the sense that it works
uniformly across all model classes. The same `make_custom_post()` factory
(line 278) handles parameter parsing, user injection, and error handling
for any method on any model.

### 8.3 `access_schema()` as a Natural Transformation

The function in `/workspace/src/pybend/core/authorize/schema.py` (line 11)
maps access rules to JSON:

```python
def access_schema(model_class: Type[Any]) -> Dict[str, Any]:
    access = getattr(model_class, '__access__', None)
    if access is None:
        return {"*": AUTHENTICATED.to_dict()}
    result = {}
    for action, rule in access.items():
        if isinstance(rule, AccessRule):
            result[action] = rule.to_dict()
    return result
```

This composes two natural transformations:
1. `model_class.__access__` extracts the rule dictionary (a projection)
2. `rule.to_dict()` serializes each rule (the `to_dict` transformation from
   Section 6.4)

The composition is itself a natural transformation from the **Model** functor
to the **JSON** functor, restricted to the access-rule component.

---

## 9. Where PyBend's Abstractions Are NOT Pure

### 9.1 Side Effects in Model Methods

Model methods decorated with `@expose_route` perform side effects:

```python
@expose_route('/comment', methods=['POST'])
def comment(self, comment: Comment, user: User = None) -> str:
    comment.user_owner = user.id if user else 1    # mutation
    self.comments.append(comment)                   # mutation
    comment.save()                                  # DB write (side effect)
    return "Comment added"                          # stringly-typed result
```

**CT violation:** In a pure categorical framework, morphisms are functions
between objects with no side effects. Here, `comment()` mutates the receiver,
writes to the database, and returns a string instead of a typed result.

**Impact:** The method cannot be composed with other methods safely (order
of execution matters due to side effects), and the return type carries no
structured information about success/failure.

### 9.2 Mutable State in Actor Instances

The Actor system relies heavily on mutable state:

```javascript
// Actor.js line 25:
this.#children = new Map();

// NTT.js line 528:
update(data) {
    this.value = {...this.#data, ...data};  // destructive merge
}
```

**CT violation:** Morphisms in a category should be *referentially
transparent*. The same message sent to the same actor at different times
may produce different results because the actor's internal state has changed.

### 9.3 Non-Composable Error Handling

PyBend uses exceptions for error signaling:

```python
# routes_fastapi.py line 64-65:
try:
    _resolver.authorize(ctx)
except AccessDenied as e:
    raise HTTPException(status_code=403, detail=str(e))
```

**CT violation:** Exceptions are not morphisms -- they bypass the normal
composition chain. In categorical terms, the `authorize -> route handler`
composition is *partial*: it is undefined when access is denied.

A pure approach would use a **Result** monad:

```
authorize : Context -> Result<(), AccessDenied>
handler   : Context -> Result<Response, Error>
pipeline  : Context -> Result<Response, AccessDenied | Error>

pipeline = authorize >>= handler   (monadic bind, total function)
```

### 9.4 Registration as Global Side Effect

The `registered_models` dictionary in
`/workspace/src/pybend/core/utils/registrar.py` is a module-level mutable
global:

```python
registered_models: Dict[str, Type[Any]] = {}    # line 9
join_models: Dict[tuple[str, str], Type[Any]] = {}  # line 11
```

The `register_model()` function (line 14) mutates this global state:

```python
def register_model(model_class, storage=None):
    # ... side effects: sets storage, creates table, runs migrations ...
    registered_models[model_class.__tablename__] = model_class
```

**CT violation:** This is the most significant impurity in PyBend's
architecture. The `register_model` function is not a morphism -- it modifies
shared global state. The `register_routes()` function then reads this global
state to generate routes. This means:

- The order of `register_model()` calls matters (join models must be
  registered after their parents).
- Two simultaneous `register_model()` calls could race.
- Testing requires clearing global state between test cases.
- The entire pipeline from model definition to route registration is
  stateful and order-dependent.

### 9.5 The Schema Cache as Hidden State

```python
# proto_model.py lines 56, 205-206:
_schema_cache: ClassVar[dict] = {}

if cls in ProtoModel._schema_cache:
    return copy.deepcopy(ProtoModel._schema_cache[cls])
```

The schema cache makes `schema()` idempotent (calling it twice returns the
same result), which is good for categorical purity. But it introduces hidden
state that can produce stale results if a model is modified after the first
`schema()` call. The `invalidate_schema_cache()` method (line 191) is the
escape hatch.

### 9.6 The `__init_subclass__` Side Effect

```python
# proto_model.py lines 72-93:
def __init_subclass__(cls, **kwargs):
    __storable__ = getattr(cls, '__storable__', False)
    cls._referenced_models = set()
    if __storable__:
        if not issubclass(cls, StorableMixin):
            cls.__bases__ = (StorableMixin,) + cls.__bases__
```

Dynamically rewriting `cls.__bases__` during class creation is a
metaclass-level side effect. It means the class hierarchy is not fixed at
definition time -- it is modified by the `ProtoModel` base class. This makes
the **PyModel** category itself mutable: the identity of objects changes
during construction.

### 9.7 The DynamicClass Value Getter Mutation

```javascript
// NTT.js lines 691-698:
get value() {
    if (!this._data) return undefined;
    let data = this._data;
    data["$schema"] = `${config.API_URL}/${this.constructor.addr}`;
    data["$id"] = this.href;
    return this._data;
}
```

This getter *mutates* `this._data` every time it is called. A pure getter
should not have side effects. This means:

- `instance.value` is not referentially transparent
- The first call to `value` modifies the data; subsequent calls are
  idempotent (same mutation applied again)
- External code that holds a reference to `_data` sees the mutation

### 9.8 The `_populate_fields` Mutation Chain

```python
# sqlite_storage.py lines 466-468:
if not hasattr(inst, '_populated') or inst._populated is None:
    inst.__dict__['_populated'] = {}
inst.__dict__['_populated'][field_name] = populated_wrapper
```

The populate operation mutates model instances by injecting a `_populated`
dictionary into their `__dict__`. This is a side effect that changes the
identity of the object without going through Pydantic's field system.

---

## 10. Toward Purer Abstractions: Recommendations

### 10.1 Priority Matrix

| Impurity | Severity | Effort | CT Concept | Recommendation |
|----------|----------|--------|------------|----------------|
| Global registration | HIGH | MEDIUM | Monoidal context | Replace with Registry monad |
| Exception-based errors | HIGH | MEDIUM | Partial morphisms | Introduce Result type |
| Value getter mutation | MEDIUM | LOW | Referential transparency | Copy before inject |
| Side-effecting methods | MEDIUM | HIGH | Effect system | Command/Event split |
| Mutable actor state | LOW | HIGH | State monad | Functional state transitions |
| `__init_subclass__` bases rewrite | LOW | LOW | Object identity | Accept as metaclass pattern |
| Schema cache | LOW | LOW | Memoization | Already idempotent; acceptable |
| `_populated` injection | MEDIUM | MEDIUM | Lens/Optic | Return new enriched instances |

### 10.2 Concrete Improvement: Registry as Context

Replace the global `registered_models` dict with a contextual registry that
threads through the pipeline:

```
Current (impure):
    register_model(Product, storage)    # global side effect
    register_routes()                    # reads global state

Proposed (pure):
    registry = Registry()
                .register(Product, storage)
                .register(User, storage)
    routes = generate_routes(registry)   # pure function of registry
    app = mount(routes)                  # pure function of routes
```

The `PyBendApp` builder (in `/workspace/src/pybend/core/app.py`) already
*approximates* this pattern -- it collects models in `self._models` (line 92)
before calling `register_model()` in `build()` (line 148-154). The
improvement would be to make `register_model()` return a new registry value
instead of mutating the global dict.

### 10.3 Concrete Improvement: Result Type for Method Calls

```python
# Current:
@expose_route('/comment', methods=['POST'])
def comment(self, comment: Comment, user: User = None) -> str:
    comment.save()
    return "Comment added"

# Proposed:
@expose_route('/comment', methods=['POST'])
def comment(self, comment: Comment, user: User = None) -> Result[Comment, MethodError]:
    comment.user_owner = user.id if user else 1
    saved = comment.save()
    return Ok(saved)  # or Err(MethodError(...))
```

The route layer would pattern-match on `Result`:

```python
result = attr(instance, **parsed_args)
match result:
    case Ok(value):  return value
    case Err(error): raise HTTPException(status_code=error.status_code, ...)
```

This makes the method a total function (always returns a value) and makes
the error path explicit in the type signature.

### 10.4 Concrete Improvement: Immutable Value Getter

```javascript
// Current (mutating):
get value() {
    let data = this._data;
    data["$schema"] = `${config.API_URL}/${this.constructor.addr}`;
    data["$id"] = this.href;
    return this._data;
}

// Proposed (pure):
get value() {
    if (!this._data) return undefined;
    return {
        ...this._data,
        "$schema": `${config.API_URL}/${this.constructor.addr}`,
        "$id": this.href,
    };
}
```

This returns a new object each time, preserving `_data` immutability.
The tradeoff is GC pressure from object allocation, which is negligible
for entity-level data.

---

## 11. Comparison with Explicit CT Frameworks

### 11.1 PyBend vs. Explicit CT Libraries

| Framework | CT Approach | PyBend Equivalent |
|-----------|-------------|-------------------|
| **Haskell (Lens)** | Optics for nested data access | `model_dump()` + `form.js` field access |
| **Scala (Cats)** | Typeclass-based functors, monads | `ProtoModel.schema()` as implicit functor |
| **fp-ts** (TypeScript) | Explicit `Functor`, `Monad` interfaces | Actor messaging as implicit composition |
| **Arrow** (Kotlin) | Validated, Either for error handling | Exceptions (no explicit Result type) |
| **Elm Architecture** | `Model -> Msg -> Model` pure cycle | `Actor.inbox(TX) -> state change` (impure) |

### 11.2 What PyBend Gets Right Without Trying

PyBend's architecture, despite not being designed with CT in mind, naturally
embodies several categorical patterns:

1. **The AccessRule algebra is a textbook Boolean algebra.** The `|`, `&`,
   `~` operators with `evaluate()` as a homomorphism to `Bool` is exactly
   what a CT practitioner would design.

2. **The schema pipeline is a genuine functor composition.** `Model ->
   Schema -> DynamicClass` preserves structure at each stage, with the
   breakages being *deliberate design choices* (metadata injection, `$defs`
   flattening) rather than bugs.

3. **The `model_dump(response=True)` transformation is a legitimate natural
   transformation.** It works uniformly across all model types and commutes
   with model morphisms.

4. **The Observable mixin is a covariant functor from Actors to event
   streams.** `signal()` maps state changes to callback invocations,
   preserving the update ordering.

### 11.3 What Would Change If PyBend Were Explicitly Categorical

If PyBend adopted explicit CT constructs, the architecture would look like:

```
# Functor typeclass
class SchemaFunctor(Protocol):
    def map(self, model: Type[ProtoModel]) -> Dict: ...

# Natural transformation
class ResponseTransform(Protocol):
    def transform(self, F: SchemaFunctor, instance: ProtoModel) -> Dict: ...

# Monad for effects
class AppMonad(Protocol):
    def bind(self, f: Callable[[A], AppMonad[B]]) -> AppMonad[B]: ...
    def pure(self, value: A) -> AppMonad[A]: ...

# Pipeline as composed functors
pipeline = SchemaFunctor() >> PrototypeFunctor() >> RenderFunctor()
```

The question is whether this abstraction pays for itself. PyBend's philosophy
("primitives, not opinions") suggests that explicit CT would be over-
engineering for most users. The *implicit* CT that already exists -- the
schema pipeline, the Boolean algebra, the natural transformations -- provides
the structural guarantees without requiring users to understand the theory.

---

## 12. The Complete Categorical Map

```
                              PyBend Architecture
                          (Categorical Structure Map)

    +-----------+     F_schema      +-----------+     F_proto      +-----------+
    |  PyModel  |  ===============> |  JSchema  |  ===============> |  JSType   |
    |           |   (Functor)       |           |   (Functor)       |           |
    | ProtoModel|   proto_model.py  | JSON      |   NTT.js          | Dynamic   |
    | subclasses|   :199-316        | Schema    |   :663-1074       | Class     |
    +-----------+                   +-----------+                   +-----------+
         |                               |                               |
         | U (forgetful)                 | eta_json (nat. trans.)        | F_render
         | model_dump()                  | JSON.stringify()              | ntt-item.js
         |                               |                               |
         v                               v                               v
    +-----------+     serialize     +-----------+     parse         +-----------+
    |  PyDict   |  --------------> |   JSON    |  --------------> | JSObject  |
    +-----------+                  +-----------+                   +-----------+
         ^                                                              ^
         |  F (free/hydration)                                          |
         |  Model(**dict)                                               |
         |                                                              |
    +-----------+                                                  +-----------+
    |  SQLStore |                                                  | ActorMsg  |
    |           |                                                  |           |
    | sqlite_   |                                                  | Matrix +  |
    | storage.py|                                                  | Actor.js  |
    +-----------+                                                  +-----------+
                                                                        |
                                                                   TX messages
                                                                   (morphisms)

    Cross-cutting:

    +-----------+     F_eval        +-----------+
    | BoolAlg   |  ===============> |   Bool    |
    | (Access   |   (Homomorphism)  | {T, F}    |
    |  Rules)   |                   |           |
    +-----------+                   +-----------+
         |
         | eta_dict (nat. trans.)        eta_sql (partial nat. trans.)
         |                               |
         v                               v
    +-----------+                   +-----------+
    | JSON dict |                   | SQL WHERE |
    +-----------+                   +-----------+
```

---

## 13. Summary of Findings

### Functors Identified

| Functor | Source | Target | Laws | Fidelity |
|---------|--------|--------|------|----------|
| `F_schema` | PyModel | JSchema | Identity: partial, Composition: near | Faithful, not full |
| `F_proto` | JSchema | JSType | Identity: N/A, Composition: preserves | Faithful, not full |
| `F_eval` | AccessRule | Bool | All laws hold | Isomorphism (homomorphism) |
| `U` (storage) | PyModel | SQLStore | Forgetful | Loses methods, rules, UI |
| `F` (hydration) | SQLStore | PyModel | Free | Adds defaults, hrefs |

### Natural Transformations Identified

| Transformation | From | To | Natural? |
|---------------|------|-----|----------|
| `model_dump(response=True)` | F_plain | F_response | YES |
| `to_dict()` | F_rule | F_json | YES (one-way) |
| `sql_filter()` | F_rule | F_sql | PARTIAL (None absorbs) |
| `@expose_route` | F_method | F_http | YES |
| `access_schema()` | F_model | F_json | YES |

### Impurities Ranked

1. **Global registration** -- most architecturally significant
2. **Exception-based errors** -- most practically impactful
3. **Value getter mutation** -- easiest to fix
4. **Side-effecting model methods** -- hardest to fix, deepest impact
5. **Mutable actor state** -- intrinsic to the Actor model pattern

---

## Sources

- Mac Lane, S. (1971). *Categories for the Working Mathematician*. Springer.
- Milewski, B. (2019). *Category Theory for Programmers*. Blurb.
- Awodey, S. (2010). *Category Theory*. Oxford University Press.
- Riehl, E. (2016). *Category Theory in Context*. Dover.
- PyBend codebase: `/workspace/src/pybend/` (commit `7550aeb`)
- JSON Schema Specification: https://json-schema.org/specification
- Hewitt, C. (1973). "A Universal Modular ACTOR Formalism for Artificial
  Intelligence." *IJCAI*.
- Wadler, P. (1995). "Monads for functional programming." *AFP*.
