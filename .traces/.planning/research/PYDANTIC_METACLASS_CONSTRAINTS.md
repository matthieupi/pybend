# Pydantic v2 Metaclass Behavior and Multiple Inheritance Constraints

**Project:** PyBend
**Researched:** 2026-02-26
**Python:** 3.11.2
**Pydantic:** 2.12.5
**Overall confidence:** HIGH (verified via live testing against actual runtime)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [ModelMetaclass Class Creation](#1-modelmetaclass-class-creation)
3. [__init_subclass__ vs __pydantic_init_subclass__](#2-init_subclass-vs-pydantic_init_subclass)
4. [Dynamic __bases__ Modification](#3-dynamic-bases-modification)
5. [Multiple Inheritance with Pydantic](#4-multiple-inheritance-with-pydantic)
6. [Mixin Patterns](#5-mixin-patterns)
7. [__init_subclass__ Chaining](#6-init_subclass-chaining)
8. [Descriptor and Property Conflicts](#7-descriptor-and-property-conflicts)
9. [SQLModel Precedent](#8-sqlmodel-precedent)
10. [Current PyBend Pattern Analysis](#9-current-pybend-pattern-analysis)
11. [Recommendations for Actor Integration](#10-recommendations-for-actor-integration)
12. [Risk Assessment](#11-risk-assessment)
13. [Sources](#sources)

---

## Executive Summary

**The core question:** Can we safely add Actor messaging behavior to Pydantic models in PyBend?

**Answer: YES**, with well-understood constraints. The research reveals that PyBend's existing pattern of injecting `StorableMixin` via `cls.__bases__` modification in `__init_subclass__` is technically sound and can be extended to support an `ActorMixin`. Key findings:

1. **`cls.__bases__` modification works reliably** with Pydantic v2 models. Pydantic's schema, validation, serialization, and `model_fields` all continue to function correctly after bases are modified. Verified empirically.

2. **`__init_subclass__` has a critical timing limitation**: `model_fields` is EMPTY when `__init_subclass__` runs. Pydantic provides `__pydantic_init_subclass__` as the alternative, which runs after full class initialization.

3. **Mixins without `__slots__` are safe**. Mixins with `__slots__` cause `TypeError: multiple bases have instance lay-out conflict`. This is a hard Python constraint, not a Pydantic limitation.

4. **Mixin `__init__` methods DO execute** when injected via `__bases__`, participating correctly in the MRO chain via `super()`.

5. **Properties on mixins do NOT interfere** with Pydantic fields unless they shadow a field name (in which case the property wins at the Python level but `model_dump()` still returns the stored field value).

6. **Multiple injection hooks can coexist**: both `__init_subclass__` (for early injection like StorableMixin) and `__pydantic_init_subclass__` (for post-initialization injection) can safely inject different mixins into the same class.

---

## 1. ModelMetaclass Class Creation

**Confidence: HIGH** (verified via Pydantic source + live testing)

### What ModelMetaclass Does

Pydantic v2 uses `pydantic._internal._model_construction.ModelMetaclass` as the metaclass for all `BaseModel` subclasses. During class creation, ModelMetaclass performs:

1. **Field extraction**: Scans annotations and namespace for field definitions
2. **Schema building**: Constructs the pydantic-core validation schema
3. **`__init__` generation**: Creates a synthetic `__init__` method for validation
4. **Slot allocation**: Defines `__slots__` = `('__dict__', '__pydantic_fields_set__', '__pydantic_extra__', '__pydantic_private__')`
5. **Class attribute population**: Sets `model_fields`, `model_computed_fields`, `__pydantic_complete__`, etc.

### Execution Order During Class Creation

```
type.__new__() called by ModelMetaclass.__new__()
    |
    v
Python calls __init_subclass__()     <-- model_fields NOT YET AVAILABLE
    |
    v
ModelMetaclass continues processing
    |
    v
Field extraction + schema building
    |
    v
model_fields populated
    |
    v
__pydantic_init_subclass__() called  <-- model_fields AVAILABLE
    |
    v
Class object returned
```

This ordering is the root cause of the timing constraint. Python's `type.__new__()` calls `__init_subclass__` as part of its standard class creation protocol, before ModelMetaclass has finished its work. Pydantic's maintainers explicitly state this would require "a prohibitively large refactor" to change.

### Verified Behavior

```python
class ParentModel(BaseModel):
    def __init_subclass__(cls, **kwargs):
        print(list(cls.model_fields.keys()))  # [] (EMPTY!)
        super().__init_subclass__(**kwargs)

class ChildModel(ParentModel):
    name: str = 'hello'
    value: int = 42
# Prints: []
```

```python
class ParentModel(BaseModel):
    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs):
        print(list(cls.model_fields.keys()))  # ['name', 'value']
        super().__pydantic_init_subclass__(**kwargs)

class ChildModel(ParentModel):
    name: str = 'hello'
    value: int = 42
# Prints: ['name', 'value']
```

---

## 2. __init_subclass__ vs __pydantic_init_subclass__

**Confidence: HIGH** (verified via live testing)

### Key Differences

| Aspect | `__init_subclass__` | `__pydantic_init_subclass__` |
|--------|---------------------|------------------------------|
| When called | During `type.__new__()` | After ModelMetaclass finishes |
| `model_fields` available | NO (empty dict) | YES (fully populated) |
| `cls.__bases__` modifiable | YES | YES |
| Mixin injection works | YES | YES |
| Receives kwargs | YES | YES (same kwargs) |
| Standard Python hook | YES | NO (Pydantic-specific) |
| Called for `__bases__` injection | NO (on the injected mixin) | NO (on the injected mixin) |

### Critical Implication for PyBend

PyBend's current `ProtoModel.__init_subclass__` does NOT need `model_fields` for its work. It only checks `__storable__` (a ClassVar) and modifies `__bases__`. This is WHY the current pattern works -- it uses `__init_subclass__` for operations that don't require field metadata.

If a future mixin injection needs to inspect `model_fields` (e.g., to validate that certain fields exist), it MUST use `__pydantic_init_subclass__` instead.

### Practical Rule

- **Use `__init_subclass__`** for: ClassVar checks, `__bases__` injection, flag setting
- **Use `__pydantic_init_subclass__`** for: field validation, schema-dependent setup, field-aware configuration

---

## 3. Dynamic __bases__ Modification

**Confidence: HIGH** (verified via live testing of all scenarios)

### Does It Work?

**YES.** Modifying `cls.__bases__` after Pydantic class creation is functionally safe. Python automatically recalculates the MRO, and Pydantic's cached schema/validation logic remains intact because the core schema was built at class creation time and references the class's `__dict__` and `model_fields`, not the MRO.

### What Works After `__bases__` Modification

| Capability | Status | Verified |
|-----------|--------|----------|
| Instance creation | Works | YES |
| `model_fields` | Intact | YES |
| `model_dump()` | Works | YES |
| `model_dump_json()` | Works | YES |
| `model_validate()` | Works | YES |
| `model_json_schema()` | Works | YES |
| `model_rebuild()` | Works | YES |
| Mixin classmethods | Accessible | YES |
| Mixin instance methods | Accessible | YES |
| Mixin properties | Accessible | YES |
| Mixin ClassVars | Accessible, NOT in schema | YES |
| Pydantic validation | Still enforced | YES |
| `issubclass()` checks | Correct | YES |

### What Does NOT Work

| Scenario | Failure | Reason |
|----------|---------|--------|
| Mixin with `__slots__` | `TypeError: multiple bases have instance lay-out conflict` | Python limitation -- two bases with non-empty `__slots__` cannot coexist when either defines `__dict__` |
| Mixin `__init_subclass__` | NOT called | Python only calls `__init_subclass__` during `type.__new__()`, not when `__bases__` is modified later |
| Property shadowing a field name | Property wins for attribute access, but `model_dump()` returns the field value | Pydantic's internal storage bypasses Python descriptors for known fields |

### The `__slots__` Constraint

This is the most important constraint. Pydantic's `BaseModel` defines:

```python
__slots__ = ('__dict__', '__pydantic_fields_set__', '__pydantic_extra__', '__pydantic_private__')
```

Any mixin injected via `__bases__` MUST NOT define `__slots__`, or it will trigger:

```
TypeError: multiple bases have instance lay-out conflict
```

**Solution:** Mixins should use regular instance attributes (stored in `__dict__`), ClassVars, or Pydantic's PrivateAttr mechanism.

### MRO Behavior After Modification

When `cls.__bases__ = (NewMixin,) + cls.__bases__` is executed:

1. Python recalculates the C3 linearization for the MRO
2. The new MRO includes the mixin before the original bases
3. Method resolution follows the new MRO correctly
4. `issubclass()` and `isinstance()` reflect the new hierarchy

Verified with PyBend's actual `ProtoModel`:

```python
class ActorProduct(ProtoModel):
    __storable__ = True  # StorableMixin injected in __init_subclass__
    name: str = ''

# After __init_subclass__:
# MRO: [ActorProduct, StorableMixin, ProtoModel, BaseModel, object]

ActorProduct.__bases__ = (ActorMixin,) + ActorProduct.__bases__

# After manual injection:
# MRO: [ActorProduct, ActorMixin, StorableMixin, ProtoModel, BaseModel, object]
# All Pydantic operations still work correctly.
```

---

## 4. Multiple Inheritance with Pydantic

**Confidence: HIGH** (verified via testing + official discussions)

### Can Pydantic Models Inherit from Non-Pydantic Classes?

**YES**, with constraints:

1. **No `__slots__` conflicts** (see above)
2. **MRO must be consistent** (standard C3 linearization rules)
3. **Only one class in the hierarchy can be a Pydantic model** with its own field definitions (otherwise fields from multiple Pydantic bases merge, which works but can be confusing)

### What About `__init__` Generation Conflicts?

Pydantic generates a synthetic `__init__` at class creation time. When a mixin also defines `__init__`:

- If the mixin is in the bases at definition time, its `__init__` participates in MRO normally
- If the mixin is injected via `__bases__`, its `__init__` is called IF it's earlier in the MRO than `BaseModel` and uses `super().__init__()` properly

**Verified:** A mixin with `__init__` injected via `__bases__` has its `__init__` called, and both the mixin's initialization and Pydantic's validation execute correctly.

### ClassVar Handling

ClassVars from mixins are handled correctly:
- They are NOT treated as Pydantic fields
- They do NOT appear in `model_fields`
- They do NOT appear in `model_json_schema()`
- They ARE accessible as class attributes

### Known Pydantic Multiple Inheritance Bugs

1. **Private attributes don't respect MRO** (Issue #11700, Pydantic 2.11.2+): When class C inherits from A and B, both defining `_private`, C gets B's value instead of A's (MRO says A should win). Labeled "Under consideration for V3."

2. **Config propagation issues** (Issue #9992): Model configuration from multiple bases doesn't always follow MRO correctly.

These bugs affect models inheriting from MULTIPLE Pydantic BaseModel subclasses. They do NOT affect the pattern of injecting a plain (non-Pydantic) mixin into a single Pydantic model hierarchy.

---

## 5. Mixin Patterns

**Confidence: HIGH** (verified via live testing)

### Safe Mixin Design for Pydantic Models

A mixin that works correctly with Pydantic must follow these rules:

```python
class SafeMixin:
    """A mixin safe for use with Pydantic BaseModel subclasses."""

    # 1. Use ClassVar for class-level state (not __slots__)
    _class_state: ClassVar[dict] = {}

    # 2. NO __slots__ definition
    # __slots__ = ('foo',)  # NEVER DO THIS

    # 3. Instance methods are fine
    def mixin_method(self):
        return self.name  # Can access Pydantic fields

    # 4. Class methods are fine
    @classmethod
    def class_method(cls):
        return cls.__name__

    # 5. Properties are fine (but don't shadow field names)
    @property
    def computed(self):
        return f"computed: {getattr(self, 'name', 'unknown')}"

    # 6. __init__ is OK but must call super()
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Can set instance attributes here
        # BUT: use object.__setattr__ to bypass Pydantic's __setattr__
        # if needed for non-field attributes
```

### What to Avoid in Mixins

| Pattern | Problem | Alternative |
|---------|---------|------------|
| `__slots__` | Layout conflict | Use ClassVar or `__dict__` |
| Property with same name as field | Shadows field access | Use different name |
| Defining Pydantic `Field()` | Confuses field resolution | Only define fields in the model class |
| `PrivateAttr` in mixin | MRO issues with private attrs | Use ClassVar or regular instance attrs |
| `model_config` in mixin | Config propagation bugs | Only configure in the model class |

### Adding Instance State Without Interfering

For non-field instance state on a mixin:

```python
class StatefulMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Use object.__setattr__ to bypass Pydantic's __setattr__
        # which would try to validate or reject unknown attrs
        object.__setattr__(self, '_mixin_state', {})
```

However, Pydantic's `Config.extra = 'allow'` (which PyBend uses) means extra attributes are accepted without needing `object.__setattr__`. They end up in `__pydantic_extra__`.

---

## 6. __init_subclass__ Chaining

**Confidence: HIGH** (verified via live testing)

### Execution Order with Multiple Base Classes

When a class inherits from multiple bases, `__init_subclass__` follows the MRO:

```python
class MixinA:
    def __init_subclass__(cls, **kwargs):
        print('MixinA')
        super().__init_subclass__(**kwargs)

class MixinB:
    def __init_subclass__(cls, **kwargs):
        print('MixinB')
        super().__init_subclass__(**kwargs)

class Combined(MixinA, MixinB, BaseModel):
    name: str = 'test'

# Output:
#   MixinA.__init_subclass__ for Combined
#   MixinB.__init_subclass__ for Combined
# MRO: [Combined, MixinA, MixinB, BaseModel, object]
```

**Rule:** `__init_subclass__` hooks chain through `super()` following the MRO. If ALL hooks call `super().__init_subclass__(**kwargs)`, all hooks execute.

### Critical: Injected Mixins Don't Get Their __init_subclass__ Called

When a mixin is injected via `cls.__bases__` modification (as PyBend does), Python does NOT retroactively call the mixin's `__init_subclass__`. This means:

```python
class ActorMixin:
    def __init_subclass__(cls, **kwargs):
        cls._actor_initialized = True  # THIS NEVER RUNS
        super().__init_subclass__(**kwargs)

class ProtoModel(BaseModel):
    def __init_subclass__(cls, **kwargs):
        if getattr(cls, '__actor__', False):
            cls.__bases__ = (ActorMixin,) + cls.__bases__
        super().__init_subclass__(**kwargs)

class MyModel(ProtoModel):
    __actor__ = True
    name: str = 'test'

# ActorMixin is in the MRO, but _actor_initialized is False
# because ActorMixin.__init_subclass__ was never called
```

**Implication:** Any initialization logic that would normally go in the mixin's `__init_subclass__` must instead be performed explicitly by the injector (ProtoModel's `__init_subclass__` or `__pydantic_init_subclass__`).

### Combining __init_subclass__ and __pydantic_init_subclass__

Both hooks can safely coexist on the same class:

```python
class ProtoModel(BaseModel):
    def __init_subclass__(cls, **kwargs):
        # Runs first, model_fields NOT available
        if getattr(cls, '__storable__', False):
            cls.__bases__ = (StorableMixin,) + cls.__bases__
        super().__init_subclass__(**kwargs)

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs):
        # Runs second, model_fields IS available
        if getattr(cls, '__actor__', False):
            cls.__bases__ = (ActorMixin,) + cls.__bases__
        super().__pydantic_init_subclass__(**kwargs)
```

**Verified:** This pattern produces a correct MRO with both mixins injected:
```
[FullModel, ActorMixin, StorableMixin, ProtoModel, BaseModel, object]
```

---

## 7. Descriptor and Property Conflicts

**Confidence: HIGH** (verified via live testing)

### Properties from Mixins

Properties defined on a mixin work correctly with Pydantic models:

```python
class PropMixin:
    @property
    def computed(self):
        return 'from property'

class PropModel(BaseModel):
    name: str = 'test'

PropModel.__bases__ = (PropMixin,) + PropModel.__bases__
inst = PropModel()
inst.computed  # 'from property' -- works fine
inst.name      # 'test' -- also works fine
```

### Property Shadowing a Pydantic Field

When a property on a mixin has the SAME NAME as a Pydantic field:

```python
class ShadowMixin:
    @property
    def name(self):
        return 'OVERRIDDEN'

class ShadowModel(BaseModel):
    name: str = 'original'

ShadowModel.__bases__ = (ShadowMixin,) + ShadowModel.__bases__
inst = ShadowModel(name='hello')
inst.name         # 'OVERRIDDEN' (property wins for attribute access)
inst.model_dump() # {'name': 'hello'} (Pydantic uses internal storage)
```

This creates a **split brain** situation: Python attribute access returns the property value, but Pydantic serialization returns the stored field value. This is almost certainly a bug waiting to happen. **Avoid name collisions between mixin attributes and Pydantic fields.**

### `__get__`/`__set__` Descriptors

Pydantic v2 uses its own `__setattr__` and `__getattr__` overrides that check for descriptors. The behavior:

- **On read:** If a descriptor exists AND a Pydantic field exists with the same name, Pydantic's stored value takes precedence for `model_dump()` but the descriptor wins for attribute access
- **On write:** Pydantic's `__setattr__` intercepts writes to known field names and stores them internally
- **Non-field descriptors:** Work normally (Pydantic ignores them)

### `@computed_field` (Pydantic Native)

Pydantic v2 provides `@computed_field` as the official way to add derived properties:

```python
from pydantic import computed_field

class MyModel(BaseModel):
    name: str

    @computed_field
    @property
    def upper_name(self) -> str:
        return self.name.upper()
```

This is included in `model_dump()` and `model_json_schema()`. It does NOT conflict with mixin properties that have different names.

**Limitation:** You cannot override a parent's regular field with a `@computed_field` in a child class (raises TypeError).

---

## 8. SQLModel Precedent

**Confidence: HIGH** (well-documented open source project)

### How SQLModel Solves the Same Problem

SQLModel faces the exact same challenge as PyBend: combining Pydantic validation with a second concern (SQLAlchemy ORM). Its approach:

**Custom dual metaclass:**

```python
class SQLModelMetaclass(ModelMetaclass, DeclarativeMeta):
    def __new__(cls, name, bases, namespace, **kwargs):
        # Phase 1: Pydantic processing
        new_class = ModelMetaclass.__new__(cls, name, bases, namespace, **kwargs)

        # Phase 2: SQLAlchemy processing (only if table=True)
        if is_table_model:
            DeclarativeMeta.__init__(new_class, name, bases, namespace)

        return new_class
```

**Key differences from PyBend's approach:**

| Aspect | SQLModel | PyBend |
|--------|----------|--------|
| Metaclass | Custom dual metaclass | Standard ModelMetaclass |
| Injection | At metaclass level | Via `__bases__` in `__init_subclass__` |
| Toggle | `table=True` kwarg | `__storable__=True` ClassVar |
| Scope | Always SQLAlchemy | Conditional mixin |

**Why PyBend's approach is actually simpler and less fragile:**

1. No custom metaclass = no risk of metaclass conflicts with future Pydantic versions
2. `__bases__` injection is a standard Python feature
3. Less coupling to Pydantic internals
4. Easier to add additional mixins without metaclass diamond problems

**SQLModel's known issue:** SQLModel models cannot be extended with non-Pydantic bases (Issue #348) precisely BECAUSE of the dual metaclass constraint. PyBend does not have this limitation.

---

## 9. Current PyBend Pattern Analysis

**Confidence: HIGH** (verified against actual codebase)

### How It Works Today

```python
class ProtoModel(PydanticBaseModel):
    def __init_subclass__(cls, **kwargs):
        __storable__ = getattr(cls, '__storable__', False)
        cls._referenced_models = set()
        if __storable__:
            if not issubclass(cls, StorableMixin):
                cls.__bases__ = (StorableMixin,) + cls.__bases__
                # FK rewriting follows...
        super().__init_subclass__(**kwargs)
```

### Verified Properties

1. **StorableMixin is a plain class** (not a BaseModel subclass) -- this is correct and avoids Pydantic multi-model inheritance issues

2. **StorableMixin has no `__slots__`** -- this is correct and avoids the layout conflict

3. **StorableMixin uses ClassVars** (`__pk__`, `__tablename__`, `storage`) -- these are correctly excluded from Pydantic fields

4. **StorableMixin methods use `self.model_dump()`** -- this works because `self` is a Pydantic model instance and `model_dump` is resolved via MRO

5. **Double injection prevention** (`if not issubclass(cls, StorableMixin)`) -- correctly prevents MRO pollution when a storable model inherits from another storable model

6. **`super().__init_subclass__(**kwargs)` called last** -- ensures the chain continues

### Existing Patterns in the Codebase

- `ViewableMixin(BaseModel)` -- Note: this extends BaseModel, which is different from StorableMixin (plain class). This means it can define Pydantic fields (`name`, `desc`, `src`) but introduces the multi-Pydantic-model inheritance concern.

- `BaseBackend(ABC, BaseModel)` -- Combines ABC with BaseModel. Works because ABC doesn't define `__slots__`.

---

## 10. Recommendations for Actor Integration

**Confidence: HIGH** (based on verified technical findings)

### Recommended Approach: Plain Mixin + `__bases__` Injection

Follow the exact pattern established by StorableMixin:

```python
class ActorMixin:
    """
    Mixin that adds actor/messaging capabilities to models.
    Must NOT define __slots__.
    Must NOT extend BaseModel.
    """

    # Class-level state via ClassVar
    _actor_address: ClassVar[str] = ''
    _message_handlers: ClassVar[dict] = {}

    # Instance methods
    def send(self, target, message):
        """Send a message to another actor."""
        ...

    def receive(self, message):
        """Handle an incoming message."""
        ...

    # Class methods
    @classmethod
    def register_handler(cls, message_type, handler):
        """Register a message handler."""
        ...
```

### Injection Strategy

**Option A: Use existing `__init_subclass__`** (recommended if no field inspection needed)

```python
def __init_subclass__(cls, **kwargs):
    __storable__ = getattr(cls, '__storable__', False)
    __actor__ = getattr(cls, '__actor__', False)
    cls._referenced_models = set()

    if __storable__:
        if not issubclass(cls, StorableMixin):
            cls.__bases__ = (StorableMixin,) + cls.__bases__

    if __actor__:
        if not issubclass(cls, ActorMixin):
            cls.__bases__ = (ActorMixin,) + cls.__bases__
            # Perform any actor initialization here
            # (since ActorMixin.__init_subclass__ won't be called)
            cls._actor_address = f"actor://{cls.__name__}"

    super().__init_subclass__(**kwargs)
```

**Option B: Use `__pydantic_init_subclass__`** (if actor setup needs field metadata)

```python
@classmethod
def __pydantic_init_subclass__(cls, **kwargs):
    if getattr(cls, '__actor__', False):
        if not issubclass(cls, ActorMixin):
            cls.__bases__ = (ActorMixin,) + cls.__bases__
            # Can inspect model_fields here
            message_fields = [f for f in cls.model_fields if f.startswith('msg_')]
    super().__pydantic_init_subclass__(**kwargs)
```

**Option C: Direct inheritance** (simplest, but changes class definition)

```python
class Product(ActorMixin, ProtoModel):
    __storable__ = True
    name: str = ''
```

This is the simplest approach and avoids the `__init_subclass__` timing issues entirely. The cost is that every developer must remember to include `ActorMixin` in their class definition.

### Design Constraints for ActorMixin

| Constraint | Reason | Enforcement |
|-----------|--------|-------------|
| No `__slots__` | Layout conflict with BaseModel | Code review / assertion |
| No BaseModel inheritance | Multi-model inheritance bugs | Keep as plain class |
| No field name collisions | Split brain on access vs dump | Prefix actor attrs with `_actor_` |
| ClassVar for class state | Excluded from Pydantic schema | Use `ClassVar[...]` annotation |
| `super().__init__()` if defining `__init__` | MRO chain must continue | Pattern requirement |
| Initialize in injector, not `__init_subclass__` | Mixin's hook not called on injection | Document clearly |

### MRO Result

With both StorableMixin and ActorMixin:

```
[Product, ActorMixin, StorableMixin, ProtoModel, BaseModel, object]
```

or (depending on injection order):

```
[Product, StorableMixin, ActorMixin, ProtoModel, BaseModel, object]
```

Both are safe. The order only matters if the two mixins define methods with the same name (they shouldn't).

---

## 11. Risk Assessment

### Low Risk

| Risk | Mitigation | Confidence |
|------|-----------|------------|
| `__bases__` modification breaks validation | Verified: it doesn't | HIGH |
| Mixin methods conflict with Pydantic | Use `_actor_` prefix | HIGH |
| Schema includes mixin attributes | ClassVars are excluded | HIGH |
| Serialization breaks | Verified: `model_dump()` still works | HIGH |
| Child class inheritance breaks | Verified: child MRO is correct | HIGH |

### Medium Risk

| Risk | Mitigation | Confidence |
|------|-----------|------------|
| Future Pydantic version breaks `__bases__` pattern | Pin Pydantic version; pattern is standard Python | MEDIUM |
| ActorMixin `__init__` interferes with Pydantic init | Don't define `__init__` on ActorMixin; use `model_post_init` or class methods | HIGH |
| Private attribute MRO bugs (Pydantic #11700) | Don't use Pydantic PrivateAttr in mixins | HIGH |

### High Risk (if constraints violated)

| Risk | Trigger | Consequence |
|------|---------|-------------|
| `__slots__` conflict | Mixin defines `__slots__` | `TypeError` at class creation |
| Split brain | Mixin property shadows field name | Attribute access != serialization |
| Config propagation bugs | Mixin defines `model_config` | Unpredictable validation behavior |

---

## Python 3.11+ Specifics

**Confidence: MEDIUM** (based on changelog review, not deeply verified)

### Python 3.11

- No significant changes to `__init_subclass__` mechanics
- Enum members now defined before `__init_subclass__()` is called (not relevant to PyBend)
- Performance improvements to `type.__new__()` (beneficial but transparent)

### Python 3.12

- `__set_name__()` exceptions no longer wrapped by RuntimeError (minor improvement)
- PEP 695 type parameter syntax (`class Foo[T]:`) -- cosmetic, doesn't change metaclass behavior
- No changes to `__init_subclass__` or `__bases__` modification behavior

### Python 3.13+ (speculative)

- PEP 702 deprecated decorators may affect type checking of mixin patterns
- No known changes to class creation protocol

### `__class_getitem__` and Generics

Not directly relevant. `__class_getitem__` is used for generic type subscripting (`MyModel[int]`). It doesn't interfere with `__bases__` modification or mixin injection. If ActorMixin needs to be generic (e.g., `ActorMixin[MessageType]`), this can be achieved with standard `__class_getitem__` without affecting Pydantic.

---

## Sources

### Primary (HIGH confidence)

- [Pydantic v2 Models Documentation](https://docs.pydantic.dev/latest/concepts/models/) -- Official docs on model behavior, `model_post_init`, custom `__init__`
- [Pydantic v2 BaseModel API](https://docs.pydantic.dev/latest/api/base_model/) -- `model_rebuild()`, `__pydantic_init_subclass__`, `__slots__` definition
- [Pydantic Discussion #7177: __init_subclass__ and model_fields](https://github.com/pydantic/pydantic/discussions/7177) -- Definitive explanation of timing issue and `__pydantic_init_subclass__` hook
- [Pydantic Discussion #5974: Multiple inheritance conventions](https://github.com/pydantic/pydantic/discussions/5974) -- Maintainer guidance on mixin patterns
- Live testing against Pydantic 2.12.5 / Python 3.11.2 (18 test scenarios executed)

### Secondary (MEDIUM confidence)

- [SQLModel Base Class Architecture](https://deepwiki.com/fastapi/sqlmodel/2.1-sqlmodel-class) -- SQLModelMetaclass dual-inheritance approach
- [Pydantic Issue #11700: Private attributes MRO](https://github.com/pydantic/pydantic/issues/11700) -- Known bug with multiple Pydantic base inheritance
- [PEP 487: Simpler customisation of class creation](https://peps.python.org/pep-0487/) -- `__init_subclass__` specification
- [Pydantic Discussion #9309: Cross-version config mixins](https://github.com/pydantic/pydantic/discussions/9309) -- Mixin pattern examples

### Tertiary (LOW confidence -- context only)

- [Pydantic Discussion #7185: ModelField and ModelMetaclass in v2](https://github.com/pydantic/pydantic/discussions/7185) -- Historical context on v1->v2 migration
- [Pydantic AI Multi-Agent Patterns](https://ai.pydantic.dev/multi-agent-applications/) -- Not the same "actor" concept, but shows Pydantic team's thinking about agent/messaging patterns

---

## Appendix: Test Results Summary

All tests run against Python 3.11.2, Pydantic 2.12.5, on the actual PyBend codebase.

| Test # | Scenario | Result |
|--------|----------|--------|
| 1 | `__init_subclass__` timing | model_fields EMPTY (confirmed) |
| 2 | `__pydantic_init_subclass__` timing | model_fields POPULATED (confirmed) |
| 3 | Multiple `__init_subclass__` chaining | Both hooks execute via MRO |
| 4 | Mixin with methods via `__bases__` | Works: send/receive/model_dump all OK |
| 5 | Property from mixin (no name conflict) | Works correctly |
| 6 | Mixin with `__init__` | `__init__` called, instance works |
| 7 | Mixin with `__slots__` | FAILS: TypeError layout conflict |
| 8 | PrivateAttr + mixin | Works correctly |
| 9 | Property shadowing field name | Split brain: property wins access, field wins dump |
| 10 | `model_rebuild()` after `__bases__` mod | Works correctly |
| 11 | ProtoModel-like simulation | Full pattern verified |
| 12A | Mixin in class definition (explicit) | Both hooks called, all works |
| 12B | Mixin injected via `__init_subclass__` | Mixin present but its hook NOT called |
| 13 | `__pydantic_init_subclass__` injection | Works, model_fields available |
| 14 | Double injection (both hooks) | Both mixins injected, MRO correct |
| 15 | Schema generation after `__bases__` mod | Schema correct, ClassVars excluded |
| 16 | JSON serialization after `__bases__` mod | Works correctly |
| 17 | `model_validate` after `__bases__` mod | Works correctly |
| 18 | Abstract Pydantic model | ABC + BaseModel works |
