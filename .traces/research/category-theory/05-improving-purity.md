# Improving Abstraction Purity in PyBend Through Category Theory

**Research Document -- February 2026**
**Audience:** Technical CEOs, Engineering Leadership, Framework Architects

---

## Executive Summary

PyBend's core thesis -- "the model is the app" -- is a fundamentally algebraic claim. A Python class definition is a specification from which the framework *derives* an entire working stack: API, schema, storage, UI, permissions. This derivation pipeline is, in categorical terms, a series of functors mapping between categories of concern. The current implementation achieves this vision with remarkable economy, but several of these mappings exhibit impurities -- hidden side effects, broken composition laws, or structural inconsistencies -- that reduce predictability, testability, and composability.

This document identifies ten concrete areas where category-theoretic reasoning reveals structural defects in PyBend's abstractions, quantifies their practical impact, and provides prioritized, code-level recommendations for remediation. Each recommendation includes before/after examples, difficulty ratings, and an estimated return on investment.

**Key findings:**
- The `model_dump()` method conflates two distinct morphisms (data extraction and metadata injection), violating functor identity laws
- Error handling mixes success and failure channels (the 200-OK anti-pattern), correctable via a proper Result type
- The schema pipeline is a monolithic 120-line method decomposable into five composable transformations
- Actor messages lack type safety, preventing structure-preserving routing
- Storage create/retrieve pairs do not form a verified adjunction -- round-trip data preservation is assumed, not proven
- AccessRule composition implements Boolean algebra operators but does not verify algebraic laws
- Configuration uses mutable global state instead of monoidal merging

**Estimated total effort:** 15-25 engineering days for high-priority items
**Estimated impact:** 40-60% reduction in integration test surface area; elimination of an entire class of silent-failure bugs

---

## 1. Making model_dump() a Proper Functor

### Current State

`ProtoModel.model_dump()` (line 117, `proto_model.py`) serves two roles controlled by a boolean flag:

```python
# Current implementation
def model_dump(self, *, response: bool = False, **kwargs) -> Dict[str, Any]:
    data = super().model_dump(**kwargs)
    if response:
        cls = self.__class__
        if cls not in ProtoModel._response_meta_cache:
            tablename = getattr(cls, '__tablename__', cls.__name__.lower())
            ProtoModel._response_meta_cache[cls] = {
                'schema_url': f"{config.API_URL}/{cls.__name__}",
                'base_url': f"{config.API_URL}/{tablename}",
            }
        meta = ProtoModel._response_meta_cache[cls]
        instance_id = getattr(self, 'id', None)
        data = {
            '$schema': meta['schema_url'],
            '$id': f"{meta['base_url']}/{instance_id}" if instance_id is not None else None,
            **data
        }
    return data
```

### Category-Theoretic Analysis

A functor `F: C -> D` must satisfy two laws:

1. **Identity:** `F(id_A) = id_{F(A)}` -- mapping the identity morphism gives the identity on the mapped object
2. **Composition:** `F(g . f) = F(g) . F(f)` -- mapping a composition equals the composition of mappings

`model_dump(response=False)` approximates a forgetful functor `U: Model -> Dict` -- it strips the model's class structure and returns raw data. For an "identity model" (one with all defaults), `model_dump()` should return the identity dict (all defaults as a plain dict). This holds.

`model_dump(response=True)` is *not* the same functor. It is `inject_metadata . U` -- a composition of two distinct morphisms. Bundling them behind a boolean flag means:

- The caller cannot compose with `U` alone in contexts where metadata is unwanted (storage operations)
- The caller cannot compose with `inject_metadata` alone (e.g., to annotate an already-serialized dict)
- Testing requires probing both branches of the flag, rather than testing two independent, single-purpose functions

### Recommendation

Separate into two explicit functions. The metadata injection becomes a standalone, composable transformation.

```python
# Proposed: proto_model.py

def model_dump(self, **kwargs) -> Dict[str, Any]:
    """Pure data extraction. Forgetful functor: Model -> Dict."""
    return super().model_dump(**kwargs)

def model_dump_response(self, **kwargs) -> Dict[str, Any]:
    """API response serialization: model_dump composed with inject_metadata."""
    return self._inject_response_metadata(self.model_dump(**kwargs))

@classmethod
def _inject_response_metadata(cls, data: Dict[str, Any]) -> Dict[str, Any]:
    """Pure transformation: Dict -> Dict with $schema and $id."""
    if cls not in ProtoModel._response_meta_cache:
        tablename = getattr(cls, '__tablename__', cls.__name__.lower())
        ProtoModel._response_meta_cache[cls] = {
            'schema_url': f"{config.API_URL}/{cls.__name__}",
            'base_url': f"{config.API_URL}/{tablename}",
        }
    meta = ProtoModel._response_meta_cache[cls]
    instance_id = data.get('id')
    return {
        '$schema': meta['schema_url'],
        '$id': f"{meta['base_url']}/{instance_id}" if instance_id is not None else None,
        **data
    }
```

**Functor law verification:**
- Identity: `model_dump(Model(**defaults)) == {field: default for field in Model.fields}` -- pure data, no decoration
- Composition: `model_dump_response == inject_metadata . model_dump` -- explicit composition, each independently testable

### Call Site Migration

Every `model_dump(response=True)` call in `routes_fastapi.py` and `sqlite_storage.py` becomes `model_dump_response()`. The storage layer continues using plain `model_dump()`. The `_serialize()` helper in routes becomes:

```python
# routes_fastapi.py -- updated _serialize
def _serialize(instance):
    data = instance.model_dump_response()
    populated = instance.__dict__.get('_populated')
    if populated:
        data.update(populated)
    return data
```

| Metric | Value |
|--------|-------|
| Difficulty | Low (2-3 days) |
| Risk | Minimal -- purely additive; deprecate old signature gradually |
| Impact | Eliminates boolean-flag branching; enables independent testing of each morphism |
| Files changed | `proto_model.py`, `routes_fastapi.py`, `sqlite_storage.py` (6 call sites) |

---

## 2. Result Types Instead of Exceptions

### Current State

PyBend has three error channels, documented in CLAUDE.md's "200-OK error" case study:

1. **Exceptions** (`MethodError`, `HTTPException`) -- proper failures
2. **Error strings returned as success** -- the anti-pattern that CLAUDE.md warns about
3. **Route handler catch-all** -- `except Exception as e` in `make_create_instance` (line 84, `routes_fastapi.py`)

The `MethodError` class (`erroring.py`) was introduced specifically to solve the 200-OK problem:

```python
class MethodError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
```

The route handler translates this into an HTTPException:

```python
# routes_fastapi.py line 333
except MethodError as e:
    raise HTTPException(status_code=e.status_code, detail=e.message)
```

### Category-Theoretic Analysis

In category theory, the Either monad (also called the Result type or coproduct) `Result[T, E] = Ok(T) | Err(E)` models computations that may fail. It is a functor from the category of fallible operations to the category of values, with the critical property that **failure is explicit in the type, not hidden in the control flow**.

Exceptions break referential transparency -- a function `f(x)` that may raise an exception is not a morphism in the usual sense because its codomain is not `T` but `T + Exception`, and the `+ Exception` part is invisible at the call site. This means:

- Composition `g . f` may silently fail at `f` without `g` ever seeing the error
- The caller must wrap every call in try/except, creating defensive boilerplate
- Error paths are not composable -- you cannot `map` over a try/except chain

### Recommendation

Introduce a lightweight `Result[T, E]` type and use it for all model method returns.

```python
# Proposed: core/utils/result.py

from __future__ import annotations
from dataclasses import dataclass
from typing import TypeVar, Generic, Callable, Union

T = TypeVar('T')
E = TypeVar('E')
U = TypeVar('U')


@dataclass(frozen=True, slots=True)
class Ok(Generic[T]):
    value: T

    def is_ok(self) -> bool:
        return True

    def is_err(self) -> bool:
        return False

    def map(self, f: Callable[[T], U]) -> Result[U, E]:
        return Ok(f(self.value))

    def flat_map(self, f: Callable[[T], Result[U, E]]) -> Result[U, E]:
        return f(self.value)

    def unwrap(self) -> T:
        return self.value

    def unwrap_or(self, default: T) -> T:
        return self.value


@dataclass(frozen=True, slots=True)
class Err(Generic[E]):
    error: E
    status_code: int = 400

    def is_ok(self) -> bool:
        return False

    def is_err(self) -> bool:
        return True

    def map(self, f) -> Result:
        return self

    def flat_map(self, f) -> Result:
        return self

    def unwrap(self):
        raise ValueError(f"Called unwrap on Err: {self.error}")

    def unwrap_or(self, default):
        return default


Result = Union[Ok[T], Err[E]]
```

**Usage in model methods:**

```python
# Before (current)
@expose_route('/like', methods=['POST'])
def like(self, user=None):
    if not user:
        raise MethodError("authentication required", 401)
    # ... do work
    return "liked"

# After (proposed)
@expose_route('/like', methods=['POST'])
def like(self, user=None) -> Result[str, str]:
    if not user:
        return Err("authentication required", status_code=401)
    # ... do work
    return Ok("liked")
```

**Route handler integration:**

```python
# routes_fastapi.py -- updated make_custom_post handler
try:
    result = attr(instance, **parsed_args)
    if isinstance(result, Err):
        raise HTTPException(status_code=result.status_code, detail=result.error)
    if isinstance(result, Ok):
        return result.value
    return result  # backward compatible: plain returns still work
except MethodError as e:
    raise HTTPException(status_code=e.status_code, detail=e.message)
```

### Monad Laws Verification

For `Result` to be a proper monad:

| Law | Expression | Holds? |
|-----|-----------|--------|
| Left identity | `Ok(a).flat_map(f) == f(a)` | Yes -- `Ok` unwraps and applies |
| Right identity | `m.flat_map(Ok) == m` | Yes -- `Ok(m.value) == m` for Ok; `Err` short-circuits |
| Associativity | `m.flat_map(f).flat_map(g) == m.flat_map(lambda x: f(x).flat_map(g))` | Yes -- both paths produce same result |

| Metric | Value |
|--------|-------|
| Difficulty | Medium (3-4 days) |
| Risk | Low -- backward compatible; `MethodError` continues working alongside |
| Impact | Eliminates entire class of 200-OK bugs; makes error paths composable and testable |
| Files changed | New `result.py`; `routes_fastapi.py` handler; model methods (opt-in) |

---

## 3. Making the Schema Pipeline Composable

### Current State

`ProtoModel.schema()` (line 199, `proto_model.py`) is a 118-line monolithic method that performs seven distinct transformations in sequence:

1. Pydantic schema generation (line 209)
2. Hidden field stripping (lines 212-217)
3. Method signature injection (line 220)
4. Referenced model ($defs) collection and injection (lines 222-241)
5. Access rule serialization (lines 255-256)
6. Field exclusion/UI/protected-field decorations (lines 258-307)
7. Metadata injection ($schema, $id) (lines 309-311)

Each of these is a pure transformation `Dict -> Dict`, but they are tangled into a single function that is difficult to test in isolation, extend, or override.

### Category-Theoretic Analysis

The schema pipeline is a composition of endofunctors on the category of JSON Schema dictionaries:

```
schema = metadata . ui_decoration . access_rules . defs_injection . methods . field_strip . pydantic_base
```

In Haskell notation: `schema = metadata <<< ui <<< access <<< defs <<< methods <<< strip <<< base`

Each transformation should be an independent, testable, composable arrow. The current monolithic implementation means:

- Testing step 5 (access rules) requires executing steps 1-4 first
- Overriding step 6 (UI decoration) requires copy-pasting the entire method
- Adding a new step (e.g., analytics metadata) requires modifying the monolith

### Recommendation

Decompose into a pipeline of named transformations:

```python
# Proposed: proto_model.py -- schema pipeline

@classmethod
def schema(cls) -> Dict[str, Any]:
    """Compose schema transformations."""
    if cls in ProtoModel._schema_cache:
        return copy.deepcopy(ProtoModel._schema_cache[cls])

    pipeline = [
        cls._schema_base,          # Step 1: Pydantic base schema
        cls._schema_strip_hidden,   # Step 2: Remove hidden fields
        cls._schema_methods,        # Step 3: Inject method signatures
        cls._schema_defs,           # Step 4: Inject $defs for referenced models
        cls._schema_access,         # Step 5: Serialize access rules
        cls._schema_ui,             # Step 6: UI hints, field exclusion, protected fields
        cls._schema_metadata,       # Step 7: $schema and $id
    ]

    schema = {}
    for transform in pipeline:
        schema = transform(schema)

    ProtoModel._schema_cache[cls] = schema
    return copy.deepcopy(schema)

@classmethod
def _schema_base(cls, _: dict) -> dict:
    """Pure Pydantic JSON Schema generation."""
    return cls.model_json_schema(ref_template="#/$defs/{model}")

@classmethod
def _schema_strip_hidden(cls, schema: dict) -> dict:
    """Remove fields listed in __hidden_fields__."""
    hidden = getattr(cls, '__hidden_fields__', set())
    if hidden and 'properties' in schema:
        for name in hidden:
            schema['properties'].pop(name, None)
        if 'required' in schema:
            schema['required'] = [r for r in schema['required'] if r not in hidden]
    return schema

@classmethod
def _schema_methods(cls, schema: dict) -> dict:
    """Inject exposed method signatures."""
    schema['methods'] = cls.__pybend_methods_json_signature__()
    return schema

@classmethod
def _schema_access(cls, schema: dict) -> dict:
    """Serialize access rules into schema."""
    from pybend.core.authorize.schema import access_schema
    schema['access'] = access_schema(cls)
    return schema

@classmethod
def _schema_metadata(cls, schema: dict) -> dict:
    """Inject JSON Schema $schema and $id."""
    schema['$schema'] = f"{config.API_URL}/Schema"
    schema['$id'] = f"{config.API_URL}/{cls.__name__}"
    return schema
```

### Composition Verification

Each step is an endomorphism `Dict -> Dict`. Composition is associative by definition. The identity element is `lambda schema: schema`. Each step can be tested with a minimal input dict:

```python
# Test _schema_access in isolation
def test_schema_access_injection():
    class MockModel:
        __access__ = {'read': ANYONE}
    schema = {'properties': {'name': {'type': 'string'}}}
    result = MockModel._schema_access(schema)
    assert 'access' in result
    assert result['access']['read'] == {'rule': 'anyone'}
```

| Metric | Value |
|--------|-------|
| Difficulty | Medium (3-5 days) |
| Risk | Low -- internal refactor; public `schema()` signature unchanged |
| Impact | Each step independently testable; override any step via subclass; extensible pipeline |
| Files changed | `proto_model.py` (refactor, no new files) |

---

## 4. Actor Messaging as Typed Morphisms

### Current State

The `TX` class (`TX.js`) is the universal message type in the actor system:

```javascript
class TX {
    constructor(event) {
        let {name, source, target, data={}, meta={}, timestamp=Date.now()} = event
        this.name = name      // string -- the handler method name
        this.source = source   // string -- sender address
        this.target = target   // string -- recipient address
        this.data = data       // any -- untyped payload
        this.meta = meta       // object -- routing hints
        this.tst = timestamp   // number
    }
}
```

The `data` field is completely untyped. The `name` field is a string that must match a handler method name on the target actor. There is no compile-time or runtime validation that a TX's data matches what the handler expects.

### Category-Theoretic Analysis

In a categorical actor system, messages are morphisms in a category where:
- Objects are actor states (or actor types)
- Morphisms are message sends that transform the receiver's state

For this to be functorial (structure-preserving), the message type must carry enough information to verify:
1. **Domain correctness:** the data payload matches what the target handler expects
2. **Codomain consistency:** the handler's response type is known to the sender
3. **Composition:** sending message A then message B is equivalent to sending a composed message

Currently, `TX` satisfies none of these. The `name` field is a string, not a typed tag. The `data` field is `any`. Routing is string-pattern-matching on `target`.

### Recommendation

Introduce typed message constructors that carry schema information:

```javascript
// Proposed: TX.js -- typed message factories

class TX {
    // ... existing constructor ...

    /**
     * Create a typed CRUD message with schema validation.
     * The schema parameter carries the expected shape of data.
     */
    static crud(action, target, data, schema = null) {
        const validActions = ['CREATE', 'READ', 'UPDATE', 'DELETE'];
        if (!validActions.includes(action)) {
            throw new TypeError(`TX.crud: invalid action '${action}', expected one of ${validActions}`);
        }
        if (schema && data && action !== 'READ' && action !== 'DELETE') {
            TX.#validateAgainstSchema(data, schema);
        }
        return new TX({ name: action, target, data });
    }

    /**
     * Create a typed method-call message.
     * Validates parameters against the method's schema definition.
     */
    static method(methodName, target, args, methodSchema) {
        if (methodSchema?.parameters) {
            for (const [param, def] of Object.entries(methodSchema.parameters)) {
                if (def.required && !(param in args)) {
                    throw new TypeError(`TX.method: missing required parameter '${param}' for '${methodName}'`);
                }
            }
        }
        return new TX({ name: methodName, target, data: args });
    }

    /**
     * Validate data against a JSON Schema subset.
     */
    static #validateAgainstSchema(data, schema) {
        if (!schema.properties) return;
        for (const [field, def] of Object.entries(schema.properties)) {
            if (def.required && !(field in data)) {
                throw new TypeError(`TX validation: missing required field '${field}'`);
            }
        }
    }
}
```

**Usage in DynamicClass:**

```javascript
// Before: untyped
DynamicClass.prototype[method] = function(...args) {
    this.call(method, args, {});
};

// After: typed via schema
DynamicClass.prototype[method] = function(...args) {
    const tx = TX.method(method, this.href, args, definition);
    this.send(tx);
};
```

| Metric | Value |
|--------|-------|
| Difficulty | Medium (4-5 days) |
| Risk | Moderate -- must not break existing untyped flows; introduce gradually |
| Impact | Catches malformed messages at send time; enables future message-level routing optimization |
| Files changed | `TX.js`, `NTT.js` (prototype method generation) |

---

## 5. Storage as a Proper Adjunction

### Current State

The storage layer (`sqlite_storage.py`, `storable_mixin.py`) defines a create/retrieve pair:

- `create(model_class, data_dict) -> model_instance` (line 93, sqlite_storage.py)
- `get(model_class, id) -> model_instance` (line 240, sqlite_storage.py)

These are loosely paired -- there is no formal guarantee that `get(create(m).id).data == m.data`.

### Category-Theoretic Analysis

An **adjunction** `F -| G` between categories C and D consists of:
- A functor `F: C -> D` (the "free" or "store" functor)
- A functor `G: D -> C` (the "forgetful" or "retrieve" functor)
- A natural isomorphism: `Hom_D(F(c), d) ~ Hom_C(c, G(d))`

For storage, the relevant adjunction is:

```
store:    Model -> StoredRecord    (forgetful: drops methods, keeps data columns)
retrieve: StoredRecord -> Model    (free: adds methods, hydrates FKs, injects defaults)
```

The **unit** of the adjunction (the round-trip law) states:
```
retrieve(store(m)).field_data == m.field_data   for all storable fields
```

This is the fundamental data integrity invariant. Currently, it is *assumed* but not *verified*. Specific violations are possible:

1. **Default injection asymmetry:** `store` strips fields with default values when `exclude_unset=True`; `retrieve` re-injects defaults from the model class. If the defaults change between store and retrieve, the round-trip law breaks.

2. **FK hydration asymmetry:** `store` writes raw integer FK values; `retrieve` hydrates them into href URLs. The href contains the API_URL, which is a runtime configuration value. If API_URL changes, `retrieve(store(m)).fk_field != m.fk_field`.

3. **Collection field asymmetry:** `store` ignores ListRef fields entirely (they are not columns); `retrieve` hydrates them via JOIN queries. This is correct but means the round-trip is `retrieve(store(m)).collections = fresh_query_result`, not `m.collections`.

### Recommendation

Formalize and test the adjunction laws explicitly:

```python
# Proposed: core/tests/unit/test_storage_adjunction.py

import pytest
from pybend.core.models.proto_model import ProtoModel


class AdjunctionTestModel(ProtoModel):
    __tablename__ = 'adjunction_test'
    __storable__ = True
    name: str = ""
    value: int = 0


def test_roundtrip_preserves_scalar_data(storage):
    """Unit law: retrieve(store(m)).scalars == m.scalars"""
    original = AdjunctionTestModel(name="test", value=42)
    stored = AdjunctionTestModel.create(original)
    retrieved = AdjunctionTestModel.get(stored.id)

    assert retrieved.name == original.name
    assert retrieved.value == original.value


def test_roundtrip_preserves_defaults(storage):
    """Verify default-value fields survive the round trip."""
    original = AdjunctionTestModel(name="defaults")  # value defaults to 0
    stored = AdjunctionTestModel.create(original)
    retrieved = AdjunctionTestModel.get(stored.id)

    assert retrieved.value == 0  # default must be preserved


def test_store_is_idempotent_on_data(storage):
    """store(m1) then get gives same data regardless of method presence."""
    m1 = AdjunctionTestModel(name="idempotent", value=7)
    s1 = AdjunctionTestModel.create(m1)
    r1 = AdjunctionTestModel.get(s1.id)

    # Re-store the retrieved instance
    data_dict = r1.model_dump()
    data_dict.pop('id')
    m2 = AdjunctionTestModel(**data_dict)
    s2 = AdjunctionTestModel.create(m2)
    r2 = AdjunctionTestModel.get(s2.id)

    assert r1.name == r2.name
    assert r1.value == r2.value
```

Additionally, document the adjunction contract in `AbstractStorage`:

```python
# Proposed addition to abstract_storage.py docstring
class AbstractStorage(ABC):
    """
    Abstract storage interface.

    Adjunction Contract:
        For any model instance `m` with storable fields F:
            retrieved = get(model_class, create(model_class, m.dump()).id)
            assert all(getattr(retrieved, f) == getattr(m, f) for f in F)

        Exceptions:
            - Collection fields (ListRef) are hydrated from JOINs, not from the stored record
            - FK fields are hydrated as href URLs; raw integer equality does not hold
            - The `id` field is auto-generated; it is not part of the input data
    """
```

| Metric | Value |
|--------|-------|
| Difficulty | Low-Medium (2-3 days) |
| Risk | None -- test-only changes plus documentation |
| Impact | Catches storage bugs at the contract level; prevents silent data corruption |
| Files changed | New test file; docstring updates to `abstract_storage.py` |

---

## 6. AccessRule Composition as a Boolean Algebra

### Current State

The `AccessRule` hierarchy (`rules.py`) implements `__or__`, `__and__`, and `__invert__`:

```python
class AccessRule(ABC):
    def __or__(self, other): return OrRule(self, other)
    def __and__(self, other): return AndRule(self, other)
    def __invert__(self): return NotRule(self)
```

The composite rules (`OrRule`, `AndRule`, `NotRule`) correctly delegate evaluation. However, the algebraic laws of Boolean algebra are not verified:

| Law | Expression | Verified? |
|-----|-----------|-----------|
| Idempotence | `a \| a == a` | Not tested |
| Commutativity | `a \| b == b \| a` | Not tested |
| Associativity | `(a \| b) \| c == a \| (b \| c)` | Not tested |
| Distributivity | `a \| (b & c) == (a \| b) & (a \| c)` | Not tested |
| Double negation | `~~a == a` | Not tested |
| De Morgan's | `~(a \| b) == ~a & ~b` | Not tested |
| Identity | `a \| NEVER == a` | No NEVER rule exists |
| Annihilation | `a \| ANYONE == ANYONE` | Not tested |

### Category-Theoretic Analysis

AccessRules form a Boolean algebra (a complemented distributive lattice). In CT terms, this is a Heyting algebra -- a category where:
- Objects are access rules
- Morphisms are implication (if rule A grants access, does rule B?)
- Meet (AND) and join (OR) are the categorical product and coproduct

For the algebra to be well-behaved, the laws above must hold. Note that the laws need not hold on *structural equality* of the rule trees (i.e., `OrRule(a, a)` is not the same object as `a`), but they must hold on *behavioral equality*: for every `AccessContext`, the composed rule must produce the same boolean result.

### Recommendation

Add property-based tests that verify the algebra laws:

```python
# Proposed: core/tests/unit/test_access_algebra.py

import pytest
from pybend.core.authorize.rules import (
    ANYONE, AUTHENTICATED, OWNER, ROLE, Where,
    OrRule, AndRule, NotRule
)
from pybend.core.authorize.context import AccessContext


def make_ctx(authenticated=True, user_id=1, role='user', resource=None):
    """Factory for test contexts."""
    user = {'user_id': user_id, 'role': role} if authenticated else {}
    return AccessContext(user=user, action='read', model_class=type('M', (), {}), resource=resource)


CONTEXTS = [
    make_ctx(authenticated=False),
    make_ctx(authenticated=True, role='user'),
    make_ctx(authenticated=True, role='admin'),
]

RULES = [ANYONE, AUTHENTICATED, ROLE('admin'), ROLE('user')]


@pytest.mark.parametrize("rule", RULES)
@pytest.mark.parametrize("ctx", CONTEXTS)
def test_idempotence_or(rule, ctx):
    """a | a behaves like a"""
    assert (rule | rule).evaluate(ctx) == rule.evaluate(ctx)


@pytest.mark.parametrize("rule", RULES)
@pytest.mark.parametrize("ctx", CONTEXTS)
def test_idempotence_and(rule, ctx):
    """a & a behaves like a"""
    assert (rule & rule).evaluate(ctx) == rule.evaluate(ctx)


@pytest.mark.parametrize("a", RULES)
@pytest.mark.parametrize("b", RULES)
@pytest.mark.parametrize("ctx", CONTEXTS)
def test_commutativity_or(a, b, ctx):
    """a | b behaves like b | a"""
    assert (a | b).evaluate(ctx) == (b | a).evaluate(ctx)


@pytest.mark.parametrize("a", RULES)
@pytest.mark.parametrize("b", RULES)
@pytest.mark.parametrize("ctx", CONTEXTS)
def test_commutativity_and(a, b, ctx):
    """a & b behaves like b & a"""
    assert (a & b).evaluate(ctx) == (b & a).evaluate(ctx)


@pytest.mark.parametrize("rule", RULES)
@pytest.mark.parametrize("ctx", CONTEXTS)
def test_double_negation(rule, ctx):
    """~~a behaves like a"""
    assert (~~rule).evaluate(ctx) == rule.evaluate(ctx)


@pytest.mark.parametrize("a", RULES)
@pytest.mark.parametrize("b", RULES)
@pytest.mark.parametrize("ctx", CONTEXTS)
def test_de_morgan_or(a, b, ctx):
    """~(a | b) behaves like ~a & ~b"""
    assert (~(a | b)).evaluate(ctx) == (~a & ~b).evaluate(ctx)


@pytest.mark.parametrize("a", RULES)
@pytest.mark.parametrize("ctx", CONTEXTS)
def test_annihilation_or(a, ctx):
    """a | ANYONE behaves like ANYONE"""
    assert (a | ANYONE).evaluate(ctx) == ANYONE.evaluate(ctx)
```

Additionally, consider adding a `NEVER` rule (the bottom element of the lattice) for completeness:

```python
# Proposed addition to rules.py
class _Never(AccessRule):
    """Never grants access. Identity element for OR."""
    def evaluate(self, ctx): return False
    def sql_filter(self, ctx): return ("1=0", [])
    def to_dict(self): return {"rule": "never"}

NEVER = _Never()
```

**SQL filter algebra must also be verified.** The `sql_filter` method on composite rules must produce equivalent SQL. Currently, `OrRule.sql_filter` returns `None` if any child returns `None`, which means the SQL pushdown is "all or nothing." This is a pragmatic choice but should be documented as a deliberate weakening of the algebra.

| Metric | Value |
|--------|-------|
| Difficulty | Low (1-2 days) |
| Risk | None -- test-only changes plus optional NEVER rule |
| Impact | Guarantees that complex rule compositions behave predictably; prevents subtle auth bugs |
| Files changed | New test file; optional addition of `NEVER` to `rules.py` |

---

## 7. DynamicClass Creation as a Proper Functor

### Current State

The `prototype()` function (`NTT.js`, line 663) transforms a JSON Schema into a JavaScript class (DynamicClass):

```javascript
function prototype(addr, schema, href) {
    const DynamicClass = class extends NTT { ... };
    // Add properties from schema.properties
    for (const field of fields) { ... }
    // Add methods from schema.methods
    for (const method of methods) { ... }
    return DynamicClass;
}
```

### Category-Theoretic Analysis

`prototype` is a functor `F: Schema -> Class` mapping JSON Schema objects to JavaScript classes. For functor laws to hold:

1. **Identity:** `prototype(empty_schema)` should produce a class with no custom properties or methods (just the NTT base functionality). Currently, an empty schema (`{properties: {}, methods: {}}`) *does* produce a minimal DynamicClass, so identity approximately holds.

2. **Composition (homomorphism):** Does `prototype(merge(schema1, schema2))` behave equivalently to some merge of `prototype(schema1)` and `prototype(schema2)`? This is the critical question.

Currently, `prototype` does not support schema composition at all. Each DynamicClass is created from a single schema in isolation. The `$defs` mechanism handles nested schemas by creating *separate* DynamicClasses for each definition, not by merging.

### Key Issue: prototype() is not compositional but does not need to be

The `prototype` function maps *individual* schemas to *individual* classes. It is functorial in the sense that schema structure is preserved: properties become getters/setters, methods become callable functions, types are preserved via validation. The composition question is moot because schemas do not compose via merging in PyBend's model -- they compose via $defs references.

The real functor law to verify is:

```
For any schema S:
    let DC = prototype(S)
    For any field f in S.properties:
        DC.prototype[f] exists AND
        DC.prototype[f].getter returns value from instance._data[f] AND
        DC.prototype[f].setter validates type against S.properties[f].type
    For any method m in S.methods:
        DC.prototype[m] exists AND
        DC.prototype[m] calls this.call(m, args, {})
```

### Recommendation

Add structural verification tests:

```javascript
// Proposed: tests/ntt-prototype.spec.js

describe('prototype() functor laws', () => {
    test('identity: empty schema produces minimal DynamicClass', () => {
        const DC = prototype('Empty', { properties: {}, methods: {} }, '/api/empty');
        expect(DC.name).toBe('Empty');
        expect(DC._schema.properties).toEqual({});
        expect(DC._schema.methods).toEqual({});
    });

    test('property preservation: every schema property becomes a getter/setter', () => {
        const schema = {
            properties: {
                name: { type: 'string', title: 'Name' },
                count: { type: 'integer', title: 'Count' },
            },
            methods: {}
        };
        const DC = prototype('Test', schema, '/api/test');
        const desc_name = Object.getOwnPropertyDescriptor(DC.prototype, 'name');
        const desc_count = Object.getOwnPropertyDescriptor(DC.prototype, 'count');
        expect(desc_name.get).toBeDefined();
        expect(desc_name.set).toBeDefined();
        expect(desc_count.get).toBeDefined();
        expect(desc_count.set).toBeDefined();
    });

    test('method preservation: every schema method becomes callable', () => {
        const schema = {
            properties: { id: { type: 'integer' } },
            methods: {
                like: { route: '/like', methods: ['POST'], parameters: {} },
            }
        };
        const DC = prototype('Test', schema, '/api/test');
        expect(typeof DC.prototype.like).toBe('function');
    });

    test('type validation: setter rejects incompatible types', () => {
        const schema = {
            properties: { count: { type: 'integer' } },
            methods: {}
        };
        const DC = prototype('Test', schema, '/api/test');
        const inst = new DC({ id: 1, count: 5 });
        expect(() => { inst.count = 'not a number'; }).toThrow(TypeError);
    });
});
```

| Metric | Value |
|--------|-------|
| Difficulty | Low (1-2 days) |
| Risk | None -- test-only |
| Impact | Documents and verifies the structural contract between schema and DynamicClass |
| Files changed | New test file |

---

## 8. Configuration as a Monoid

### Current State

`config.py` uses module-level global variables with a `configure()` function that mutates them:

```python
# config.py
HOST = "0.0.0.0"
PORT = 5000
API_URL = f"http://localhost:{PORT}"
# ...

def configure(**kwargs):
    g = globals()
    for key, value in kwargs.items():
        key_upper = key.upper()
        if key_upper in g:
            g[key_upper] = value
        else:
            raise ValueError(f"Unknown config key: {key}")
```

Environment variables override globals at module load time. `configure()` mutates globals imperatively. Multiple calls to `configure()` overwrite previous values with no merge semantics.

### Category-Theoretic Analysis

Configuration should form a **monoid** `(Config, <>, empty)` where:
- `Config` is the set of all valid configurations
- `<>` is an associative binary operation (merge)
- `empty` is the identity element (defaults)

The monoid laws:
1. **Associativity:** `(a <> b) <> c == a <> (b <> c)` -- merge order grouping does not matter
2. **Identity:** `empty <> a == a == a <> empty` -- merging with defaults leaves config unchanged

The current system violates these because:
- `configure(port=8080); configure(host="0.0.0.0")` is *order-dependent* if a later call overwrites an earlier one
- There is no way to inspect the "merge" -- you just see the final global state
- The API_URL is computed from PORT at module load time but not recomputed when PORT changes via `configure()`

### Recommendation

Introduce a frozen configuration dataclass with explicit merge semantics:

```python
# Proposed: core/config.py

from __future__ import annotations
from dataclasses import dataclass, field, replace
from typing import Optional
import os


@dataclass(frozen=True)
class PyBendConfig:
    """Immutable configuration. Compose via merge()."""
    backend: str = "fastapi"
    version: str = "0.7.0"
    host: str = "0.0.0.0"
    port: int = 5000
    api_url: Optional[str] = None  # computed from port if None
    sqlite_db_file: str = "pybend.db"
    jwt_secret: str = "pybend-dev-secret-change-in-production"
    jwt_expiry_hours: int = 24
    debug: bool = True

    @property
    def effective_api_url(self) -> str:
        return self.api_url or f"http://localhost:{self.port}"

    def merge(self, overrides: PyBendConfig) -> PyBendConfig:
        """Monoidal merge: override only non-default fields from overrides."""
        defaults = PyBendConfig()
        changes = {}
        for f in self.__dataclass_fields__:
            override_val = getattr(overrides, f)
            if override_val != getattr(defaults, f):
                changes[f] = override_val
        return replace(self, **changes)

    @classmethod
    def from_env(cls) -> PyBendConfig:
        """Build config from PYBEND_* environment variables."""
        overrides = {}
        if os.getenv("PYBEND_BACKEND"):
            overrides['backend'] = os.environ["PYBEND_BACKEND"]
        if os.getenv("PYBEND_PORT"):
            overrides['port'] = int(os.environ["PYBEND_PORT"])
        if os.getenv("PYBEND_API_URL"):
            overrides['api_url'] = os.environ["PYBEND_API_URL"]
        if os.getenv("PYBEND_HOST"):
            overrides['host'] = os.environ["PYBEND_HOST"]
        if os.getenv("PYBEND_SQLITE_DB"):
            overrides['sqlite_db_file'] = os.environ["PYBEND_SQLITE_DB"]
        if os.getenv("PYBEND_JWT_SECRET"):
            overrides['jwt_secret'] = os.environ["PYBEND_JWT_SECRET"]
        if os.getenv("PYBEND_DEBUG"):
            overrides['debug'] = os.environ["PYBEND_DEBUG"].lower() in ("1", "true")
        return cls(**overrides) if overrides else cls()


# Monoid: defaults <> env <> user = final
DEFAULT_CONFIG = PyBendConfig()
ENV_CONFIG = PyBendConfig.from_env()

# Global active config (backward compat: migrate gradually)
_active: PyBendConfig = DEFAULT_CONFIG.merge(ENV_CONFIG)

# Backward-compatible accessors
HOST = _active.host
PORT = _active.port
API_URL = _active.effective_api_url
# ...
```

**Monoid law verification:**

```python
def test_monoid_identity():
    defaults = PyBendConfig()
    custom = PyBendConfig(port=8080)
    assert defaults.merge(custom).port == 8080
    assert custom.merge(defaults).port == 8080  # identity on right

def test_monoid_associativity():
    a = PyBendConfig(port=8080)
    b = PyBendConfig(host="127.0.0.1")
    c = PyBendConfig(debug=False)
    ab_c = a.merge(b).merge(c)
    a_bc = a.merge(b.merge(c))
    assert ab_c == a_bc
```

| Metric | Value |
|--------|-------|
| Difficulty | Medium-High (4-6 days) |
| Risk | Moderate -- many modules import `config.PORT` etc. directly; requires gradual migration |
| Impact | Eliminates global mutation bugs; makes config testable; enables per-test config isolation |
| Files changed | `config.py` (rewrite); all files that import from config (accessor compatibility layer) |

---

## 9. Registration as a Pure Operation

### Current State

`register_model()` (`registrar.py`) mutates a global dictionary:

```python
registered_models: Dict[str, Type[Any]] = {}

def register_model(model_class, storage=None):
    if hasattr(model_class, '__storable__') and model_class.__storable__:
        model_class.set_storage(storage)    # side effect: mutates class
        model_class.create_table()          # side effect: DDL
        if hasattr(storage, 'migrate_table'):
            storage.migrate_table(model_class)  # side effect: DDL
    registered_models[model_class.__tablename__] = model_class  # side effect: mutates global
```

A single call performs three distinct side effects: (1) injects storage into the class, (2) creates a database table, (3) adds to a global registry. These cannot be undone, tested in isolation, or recomposed.

### Category-Theoretic Analysis

Registration should be a morphism in the category of **application configurations**:
- Objects: application states (set of registered models, storage mappings, routes)
- Morphisms: registration operations that transform one state into another

Currently, registration is an *effectful* operation on global state. The `PyBendApp` builder (`app.py`) partially addresses this -- it accumulates model registrations as data (`self._models` list) and defers side effects to `build()`. This is the right pattern.

### Recommendation

Push the builder pattern further. Make `PyBendApp.build()` the *only* entry point for side effects.

```python
# Proposed: registrar.py -- pure accumulation, no side effects

@dataclass
class ModelRegistration:
    """Pure data: a model + its storage binding."""
    model_class: Type
    storage: AbstractStorage
    is_join: bool = False
    parent: Optional[Type] = None

class ModelRegistry:
    """Immutable accumulator. No side effects until materialize()."""

    def __init__(self, registrations=None):
        self._registrations = list(registrations or [])

    def register(self, model_class, storage) -> 'ModelRegistry':
        """Return a NEW registry with the model added. Does not mutate."""
        return ModelRegistry(
            self._registrations + [ModelRegistration(model_class, storage)]
        )

    def materialize(self) -> Dict[str, Type]:
        """Execute all side effects: set storage, create tables, migrate.
        Returns the final registered_models dict."""
        result = {}
        for reg in self._registrations:
            reg.model_class.set_storage(reg.storage)
            reg.model_class.create_table()
            if hasattr(reg.storage, 'migrate_table'):
                reg.storage.migrate_table(reg.model_class)
            result[reg.model_class.__tablename__] = reg.model_class
        return result
```

This makes the registration phase pure (just data accumulation) and the materialization phase explicit (all side effects in one place).

**PyBendApp.build() already does this partially.** The recommendation is to remove the direct `register_model()` function from the public API and route everything through the builder. Keep the function for backward compatibility but mark it as the effectful entry point.

| Metric | Value |
|--------|-------|
| Difficulty | Medium (3-4 days) |
| Risk | Moderate -- Level 3 bootstrap (raw primitives) uses `register_model()` directly |
| Impact | Pure registration enables testing model configurations without DB side effects |
| Files changed | `registrar.py`, `app.py`; backward compat wrapper for `register_model()` |

---

## 10. Priority Matrix

### Summary Table

| # | Recommendation | Difficulty | Risk | CT Benefit | Practical Impact | Priority |
|---|---------------|-----------|------|------------|-----------------|----------|
| 1 | model_dump() functor decomposition | Low (2-3d) | Minimal | High | Medium | **P0 -- Now** |
| 2 | Result type for error handling | Medium (3-4d) | Low | High | High | **P0 -- Now** |
| 3 | Schema pipeline decomposition | Medium (3-5d) | Low | High | High | **P0 -- Now** |
| 5 | Storage adjunction tests | Low-Med (2-3d) | None | High | Medium | **P1 -- Soon** |
| 6 | AccessRule algebra verification | Low (1-2d) | None | High | Medium | **P1 -- Soon** |
| 7 | DynamicClass functor tests | Low (1-2d) | None | Medium | Low | **P1 -- Soon** |
| 4 | Typed actor messages | Medium (4-5d) | Moderate | Medium | Medium | **P2 -- Later** |
| 8 | Configuration monoid | Med-High (4-6d) | Moderate | Medium | Medium | **P2 -- Later** |
| 9 | Pure registration | Medium (3-4d) | Moderate | Medium | Medium | **P2 -- Later** |

### Decision Framework

**P0 (Now) -- Items 1, 2, 3**: These are internal refactors with minimal risk, no API changes, and immediate benefits. The schema pipeline decomposition (item 3) is the highest-ROI change: it makes the core of the framework independently testable and extensible. The Result type (item 2) eliminates an entire class of bugs documented in the project's own CLAUDE.md. The model_dump decomposition (item 1) is a quick win that establishes the principle.

**P1 (Soon) -- Items 5, 6, 7**: These are test-only changes that verify existing behavior. Zero risk, high confidence gain. The AccessRule algebra tests (item 6) should be done first because authorization bugs are security bugs.

**P2 (Later) -- Items 4, 8, 9**: These require broader API changes and careful migration. The configuration monoid (item 8) has the widest blast radius because every file imports config values. The typed actor messages (item 4) require frontend changes. Pure registration (item 9) is partially done via PyBendApp already.

### What NOT to do

The following category-theoretic ideas were considered and rejected for PyBend:

| Idea | Why Not |
|------|---------|
| Full monad transformer stack for route handlers | Adds complexity without proportional benefit; FastAPI's dependency injection already handles composition |
| Free monad for storage operations | Over-engineering for a SQLite-backed framework; the adjunction tests (item 5) give the same guarantees with far less abstraction |
| Optics/lenses for model field access | Pydantic already provides typed field access; adding a lens layer would obscure rather than clarify |
| Full dependent types for schema validation | Python's type system does not support this; the schema-driven DynamicClass approach is the pragmatic equivalent |
| Category of categories (2-category structure) for the framework architecture | Intellectually interesting but provides no actionable engineering guidance |

### Implementation Sequence

```
Week 1:  Item 1 (model_dump functor)     -- 2 days
         Item 6 (AccessRule algebra)      -- 1 day
         Item 7 (DynamicClass tests)      -- 1 day

Week 2:  Item 2 (Result type)            -- 3 days
         Item 5 (Storage adjunction)      -- 2 days

Week 3:  Item 3 (Schema pipeline)        -- 5 days (largest refactor)

Week 4+: Items 4, 8, 9 as capacity allows
```

---

## Appendix A: Category Theory Glossary for Engineering Teams

| CT Concept | PyBend Equivalent | One-Line Definition |
|-----------|------------------|---------------------|
| **Functor** | `model_dump()`, `prototype()`, `schema()` | A structure-preserving map between two categories |
| **Monad** | `Result[T, E]` (proposed) | A functor with `return` and `bind` that chains computations |
| **Adjunction** | `create()`/`get()` pair | Two functors F, G where F is "free" and G is "forgetful", with a round-trip law |
| **Monoid** | Config merging (proposed) | A set with an associative operation and an identity element |
| **Boolean Algebra** | AccessRule composition | A complemented distributive lattice with AND, OR, NOT |
| **Morphism** | TX message, function call | An arrow between two objects in a category |
| **Natural Transformation** | Schema-to-class pipeline | A systematic way to transform one functor into another |
| **Endofunctor** | Each schema pipeline step | A functor from a category to itself (Dict -> Dict) |
| **Identity** | Default config, empty schema | The "do nothing" element that leaves things unchanged |
| **Composition** | Pipeline steps, rule chaining | Combining two morphisms into one: `g . f` |

## Appendix B: Mapping PyBend's Architecture to Categories

```
Category: Models
  Objects: ProtoModel subclasses (Product, User, Comment, ...)
  Morphisms: Model transformations (schema generation, serialization, join model creation)

Category: Schemas
  Objects: JSON Schema documents
  Morphisms: Schema transformations (_schema_base, _schema_methods, _schema_access, ...)

Category: Classes (Frontend)
  Objects: DynamicClass instances
  Morphisms: Class operations (prototype(), READ, CREATE, UPDATE, DELETE)

Category: Storage
  Objects: Database records (rows)
  Morphisms: CRUD operations (create, get, list, update, delete)

Category: AccessRules
  Objects: Authorization rules (ANYONE, AUTHENTICATED, OWNER, ROLE, Where)
  Morphisms: Rule composition (|, &, ~)

Functors between categories:
  schema():    Models -> Schemas        (ProtoModel.schema())
  prototype(): Schemas -> Classes       (NTT.prototype())
  create():    Models -> Storage        (StorableMixin.create())
  get():       Storage -> Models        (StorableMixin.get())
  access_schema(): AccessRules -> Schemas (authorize.schema.access_schema())
  model_dump(): Models -> Dicts         (ProtoModel.model_dump())
```

---

## Sources

1. Mac Lane, S. (1971). *Categories for the Working Mathematician*. Springer. -- Foundational reference for functor laws, natural transformations, and adjunctions.

2. Wadler, P. (1995). "Monads for Functional Programming." *Advanced Functional Programming*. Springer. -- Original formulation of the monad laws and their application to error handling.

3. Milewski, B. (2019). *Category Theory for Programmers*. -- Accessible introduction to CT concepts applied to software engineering. Available at https://bartoszmilewski.com/2014/10/28/category-theory-for-programmers-the-preface/

4. Hewitt, C. (1973). "A Universal Modular ACTOR Formalism for Artificial Intelligence." *IJCAI*. -- Original actor model paper; messages as morphisms in the actor category.

5. Python `returns` library. https://github.com/dry-python/returns -- Production-quality Result/Either monad implementation for Python. Reference for the Result type proposed in Section 2.

6. FastAPI Documentation. https://fastapi.tiangolo.com/ -- Framework underlying PyBend's API layer.

7. JSON Schema Specification (2020-12). https://json-schema.org/specification -- Reference for `$schema`, `$id`, `$defs` semantics used in PyBend's schema pipeline.

8. PyBend CLAUDE.md. `/workspace/CLAUDE.md` -- Project philosophy, the 200-OK error case study, and architectural documentation that informed this analysis.
