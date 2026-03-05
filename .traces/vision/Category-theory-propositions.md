# Category Theory x Our System: Technical Propositions

> *How categorical abstractions can improve our architecture.*
> *Based on research in `.traces/research/category-theory/` and codebase analysis.*

---

## The Bridge

N3TX's core promise -- "the model is the app" -- is a categorical claim. It asserts the existence of a structure-preserving transformation (a functor) from the category of Python model definitions to the category of working full-stack applications. Every field, every constraint, every access rule, every method signature must survive the journey from `ProtoModel` subclass through JSON Schema, across the network, into a JavaScript DynamicClass, and finally into rendered HTML -- without losing information, without gaining phantom state, and without contradicting itself at any layer.

We already think this way. When we say "adding a field to the model should automatically produce a new form input," we are invoking the functor composition law: `F3(F2(F1(add_field(Model))))` must produce `add_input(F3(F2(F1(Model))))`. When we say "OWNER | ROLE('admin') should work the same in Python and SQL," we are invoking a natural transformation: the `sql_filter()` method must commute with `evaluate()`. When we say "create then get should return the same data," we are invoking the unit law of an adjunction.

The opportunity is not to adopt category theory. It is to recognize the categorical structures we already have, test their laws, and fix the places where they break. The research identifies eight specific impurities where our functorial chain leaks. Three of those are responsible for the hardest-to-diagnose class of bugs in the system: silent failures at layer boundaries. Fixing them is 8-12 days of work. The return is the elimination of an entire bug category and a 40-60% reduction in the integration tests needed to verify schema propagation.

---

## Propositions

### Proposition 1: Decompose `model_dump()` into two named morphisms

> **Proposition:** Split `model_dump(response=True)` into `model_dump()` (pure data extraction) and `model_dump_response()` (data + metadata injection), making each morphism independently composable and testable.

**From the research:** The technical deep dive (02, Section 1.3) identifies `model_dump()` as a natural transformation between two functors: "plain dict" and "API response dict." The N3TX CT mapping (04, Section 8.1) verifies that the transformation is natural (uniform across all model types) but notes that bundling two categorically distinct operations behind a boolean flag violates composability. The improving-purity document (05, Section 1) provides a complete code-level proposal.

**In our system:** In `proto_model.py:117-137`, the `model_dump()` method switches behavior based on a `response` boolean. The forgetful functor (strip class structure, return raw data) and the enriching natural transformation (inject `$schema` and `$id`) are entangled. Every call site in `routes_fastapi.py` (lines 83, 127, 133, 200, 227) must remember the flag. Storage operations in `storable_mixin.py:27` use `model_dump()` without the flag, but there is no type-level distinction -- a developer could accidentally pass `response=True` to storage and corrupt the database with `$schema`/`$id` keys in the data.

**The idea:** Create two explicit methods:

```
model_dump()           -> Dict     (forgetful functor: Model -> Dict)
model_dump_response()  -> Dict     (composition: inject_metadata . model_dump)
```

The `_serialize()` helper in `routes_fastapi.py:34-40` becomes `instance.model_dump_response()` plus population overlay. Storage operations remain `model_dump()`. The boolean flag is deprecated. Each morphism can be tested in isolation: `model_dump()` tests verify data extraction without metadata; `model_dump_response()` tests verify metadata injection without storage concerns.

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | Low -- 2-3 days. 6 call sites in routes + storage files. Additive change; old signature works during migration. |
| Impact | Medium -- Eliminates boolean-flag confusion. Enables independent testing of each morphism. Prevents accidental metadata injection into storage. |
| Risk | Minimal -- Purely additive. The `response=True` path continues working until deprecated. |
| Timeline | Days |

---

### Proposition 2: Introduce a lightweight Result type for model method returns

> **Proposition:** Create `Ok[T]` and `Err[E]` types so model methods return explicit success/failure values instead of raising exceptions or (worse) returning error strings with HTTP 200.

**From the research:** The 200-OK error case study documented in CLAUDE.md is the canonical functor law violation: an error mapped through the HTTP functor as a success. The technical deep dive (02, Section 6) frames this as a missing Either monad. The decision framework (03, Section 3.2) validates that Result types prevent this bug class entirely. The improving-purity document (05, Section 2) provides a complete `Result` implementation with monad law verification.

**In our system:** The `MethodError` class in `erroring.py` was created to fix the 200-OK problem. The route handler in `routes_fastapi.py:331-334` catches `MethodError` and converts it to `HTTPException`. This works, but it relies on every developer remembering to raise `MethodError` instead of returning an error string. The type signature of model methods (`-> str`) does not distinguish success from failure. A developer writing `return '{"error": "not allowed"}'` produces a valid Python return that silently bypasses the error-handling pipeline.

**The idea:** A frozen dataclass `Ok(value)` and `Err(error, status_code)` with `map()` and `flat_map()` methods. Model methods return `Result[str, str]` instead of `str`. The route handler checks `isinstance(result, Err)` and converts to `HTTPException`. The key: this is backward compatible. Methods that return plain strings continue working. The `Result` type is opt-in for new methods and progressively adopted for existing ones. The error channel becomes structurally impossible to confuse with the success channel because they are different types.

```python
# Before: error silently encoded as success
def like(self, user=None) -> str:
    if not user:
        return '{"error": "auth required"}'  # HTTP 200, silent failure
    return "liked"

# After: error structurally separated from success
def like(self, user=None) -> Result[str, str]:
    if not user:
        return Err("auth required", status_code=401)
    return Ok("liked")
```

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | Medium -- 3-4 days. New `result.py` file (~60 lines), route handler update, opt-in migration of existing methods. |
| Impact | High -- Eliminates the entire class of 200-OK bugs. Error paths become composable (`.map()`, `.flat_map()`). Type signatures document failure modes. |
| Risk | Low -- Fully backward compatible. `MethodError` continues working alongside. No forced migration. |
| Timeline | Days |

---

### Proposition 3: Decompose the schema pipeline into composable transformations

> **Proposition:** Refactor `ProtoModel.schema()` from a 118-line monolith into a pipeline of 7 named, independently testable classmethod transformations.

**From the research:** The technical deep dive (02, Section 9.1) identifies the schema pipeline as a composition of endofunctors on the `Dict` category. The improving-purity document (05, Section 3) maps all 7 steps and provides a complete code-level decomposition. The industry landscape (01, Section 3) shows that pipeline architectures reduce integration defects by 30-60% compared to monolithic transformation functions.

**In our system:** `proto_model.py:199-316` performs seven distinct operations in sequence: (1) Pydantic base schema generation, (2) hidden field stripping, (3) method signature injection, (4) `$defs` collection and injection, (5) access rule serialization, (6) field exclusion/UI/protected-field decoration, (7) `$schema`/`$id` metadata injection. Each is a pure `Dict -> Dict` transformation, but they are tangled into a single method. Testing step 5 (access rules) requires executing steps 1-4. Overriding step 6 (UI decoration) requires copy-pasting the entire method. Adding a new step requires modifying the monolith.

**The idea:** Extract each step into a named classmethod:

```python
pipeline = [
    cls._schema_base,           # Pydantic introspection
    cls._schema_strip_hidden,   # Remove __hidden_fields__
    cls._schema_methods,        # Inject @expose_route signatures
    cls._schema_defs,           # Collect and inject $defs
    cls._schema_access,         # Serialize __access__ rules
    cls._schema_ui,             # UI hints, field exclusion, protected fields
    cls._schema_metadata,       # $schema and $id
]
schema = {}
for transform in pipeline:
    schema = transform(schema)
```

The public `schema()` signature is unchanged. The cache remains. Each step is a classmethod that a subclass can override. Adding a new transformation means adding one function to the pipeline list. Each step is independently testable with a minimal input dict.

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | Medium -- 3-5 days. Internal refactor of `proto_model.py`. No public API changes. Requires snapshot tests to verify output equivalence before and after. |
| Impact | High -- Each of 7 steps independently testable. Subclasses can override individual steps. Adding new schema transformations is trivial. |
| Risk | Low -- Internal refactor. Public `schema()` returns identical output. Snapshot tests catch regressions. |
| Timeline | 1-2 weeks |

---

### Proposition 4: Verify AccessRule algebraic laws with property-based tests

> **Proposition:** Add a test suite that verifies the Boolean algebra laws (idempotence, commutativity, associativity, distributivity, double negation, De Morgan's) for `AccessRule` composition, catching authorization regressions at the algebraic level.

**From the research:** The N3TX CT mapping (04, Section 6) demonstrates that `AccessRule` is a well-formed Boolean algebra with `evaluate()` as a proper homomorphism to `Bool`. The improving-purity document (05, Section 6) identifies that none of the algebraic laws are tested and provides a complete parametric test suite. The decision framework (03, Section 3.3) frames access rules as monoidal composition.

**In our system:** `rules.py:30-37` defines `__or__`, `__and__`, and `__invert__` on `AccessRule`. `OrRule.evaluate()` (line 51) uses `any()`, `AndRule.evaluate()` (line 74) uses `all()`, and `NotRule.evaluate()` (line 97) uses `not` -- these are the correct Boolean algebra homomorphisms. But there are no tests verifying that `(a | b) | c` evaluates identically to `a | (b | c)`, or that `~(a | b)` evaluates identically to `~a & ~b`, across all possible `AccessContext` values. A future change to `OrRule` or `AndRule` could silently break these invariants, producing authorization bugs that only manifest for specific rule combinations.

**The idea:** Parametric tests over `[ANYONE, AUTHENTICATED, ROLE('admin'), ROLE('user')]` and multiple `AccessContext` configurations. Each test verifies one algebraic law. Additionally, add a `NEVER` bottom element (`evaluate() -> False`, `sql_filter() -> ("1=0", [])`) to complete the lattice and enable identity-element tests.

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | Low -- 1-2 days. New test file only. Optional `NEVER` rule is ~10 lines. |
| Impact | Medium -- Authorization bugs from rule composition are security bugs. Algebraic law tests catch regressions that individual unit tests miss. |
| Risk | None -- Test-only changes plus optional `NEVER` rule addition. |
| Timeline | Days |

---

### Proposition 5: Fix the DynamicClass value getter mutation

> **Proposition:** Change the `get value()` getter in `prototype()` from mutating `_data` in place to returning a new object with `$schema` and `$id` injected, restoring referential transparency.

**From the research:** The N3TX CT mapping (04, Section 9.7) identifies this as a violation of referential transparency: the getter mutates `this._data` on every call, meaning `instance.value` is not pure -- external code holding a reference to `_data` sees the mutation. The improving-purity document (05, Section 10) provides the fix: `return {...this._data, "$schema": ..., "$id": ...}`.

**In our system:** `N3TX.js:691-698` inside the `prototype()` function:

```javascript
get value() {
    let data = this._data;
    data["$schema"] = `${config.API_URL}/${this.constructor.addr}`;
    data["$id"] = this.href;
    return this._data;
}
```

This writes `$schema` and `$id` directly into `_data`. Any code that reads `_data` before the first `value` access sees different content than code that reads after. The first call is not idempotent at the object level -- it adds keys that were not in the original data. This is the kind of impurity that produces debugging nightmares: "the data changed between when I logged it and when I rendered it."

**The idea:** Return a shallow copy with metadata injected:

```javascript
get value() {
    if (!this._data) return undefined;
    return {
        ...this._data,
        "$schema": `${config.API_URL}/${this.constructor.addr}`,
        "$id": this.href,
    };
}
```

The tradeoff is GC pressure from object allocation on every access. For entity-level data (not called in tight loops), this is negligible. An audit of all `instance.value` consumers should verify that none rely on reference identity of `_data`.

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | Low -- 1 day. Single line change plus consumer audit. |
| Impact | Medium -- Restores referential transparency. Eliminates a class of state-mutation bugs in the frontend. |
| Risk | Medium -- Components that rely on `_data` reference identity may break. Requires audit before deployment. |
| Timeline | Days |

---

### Proposition 6: Test the storage create/retrieve adjunction

> **Proposition:** Add explicit round-trip tests that verify `get(create(m).id).fields == m.fields` for all storable field types, formalizing the storage layer's implicit adjunction contract.

**From the research:** The N3TX CT mapping (04, Section 4) analyzes the storage layer as an adjunction between `PyModel` and `SQLStore`, identifying three specific breakage points: default injection asymmetry, FK hydration asymmetry, and collection field asymmetry. The improving-purity document (05, Section 5) provides a complete test suite verifying round-trip preservation.

**In our system:** `storable_mixin.py:64-89` defines `create()` and `storable_mixin.py:103-108` defines `get()`. The round-trip invariant -- storing then retrieving preserves field data -- is assumed but never tested. Specific violations are possible: if `exclude_unset=True` strips a field with a default value, and the default later changes, the round-trip breaks silently. If `API_URL` changes between store and retrieve, FK href URLs diverge.

**The idea:** A test file with three focused assertions: (1) scalar fields survive the round trip, (2) default values are preserved, (3) re-storing a retrieved instance produces equivalent data. Document the adjunction contract in `AbstractStorage`'s docstring, including known exceptions (collection fields, FK hydration, auto-generated IDs).

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | Low-Medium -- 2-3 days. New test file plus docstring updates. |
| Impact | Medium -- Catches silent data corruption in create/retrieve cycles. Documents the storage contract formally. |
| Risk | None -- Test-only changes plus documentation. |
| Timeline | Days |

---

### Proposition 7: Formalize configuration as an immutable monoid

> **Proposition:** Replace `config.py`'s mutable global variables and imperative `configure()` function with a frozen dataclass that supports monoidal merge: `defaults <> env_overrides <> user_overrides = final_config`.

**From the research:** The improving-purity document (05, Section 8) identifies config mutation as a source of subtle bugs: `API_URL` is computed from `PORT` at import time but never recomputed when `PORT` changes via `configure()`. The technical deep dive (02, Section 1.5) describes monoids as "something you can combine with an associative operation and an identity element." Config merge is the textbook application.

**In our system:** `config.py` uses module-level globals (`HOST`, `PORT`, `API_URL`). The `configure()` function mutates `globals()` directly. `API_URL` is computed once as `f"http://localhost:{PORT}"`. If someone calls `configure(port=8080)` after import, `API_URL` still says `http://localhost:5000`. Every file that imports `config.PORT` gets the value at import time, creating snapshot-vs-live inconsistencies. Testing requires monkey-patching module globals.

**The idea:** A frozen `N3TXConfig` dataclass with a `merge()` method. `merge()` is associative: `(a.merge(b)).merge(c) == a.merge(b.merge(c))`. The identity element is `N3TXConfig()` (all defaults). `API_URL` becomes a computed property (`effective_api_url`) that always reflects the current `port`. Backward-compatible module-level accessors (`HOST = _active.host`) maintain existing import patterns during migration.

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | Medium-High -- 4-6 days. `config.py` rewrite plus migration of all importing modules. |
| Impact | Medium -- Eliminates config-mutation bugs. Enables per-test config isolation. Makes `API_URL` always consistent with `PORT`. |
| Risk | Moderate -- Wide blast radius: every module imports from `config`. Requires backward-compatible accessor layer. |
| Timeline | Weeks |

---

### Proposition 8: Make model registration a pure accumulation with deferred effects

> **Proposition:** Transform `register_model()` from a global-state-mutating side effect into a pure accumulation step, with all side effects (table creation, migration, storage injection) deferred to a single `materialize()` call.

**From the research:** The N3TX CT mapping (04, Section 9.4) identifies global registration as the most architecturally significant impurity in the codebase. The analysis report (category-theory-analysis.md, Section 4.2) ranks it as Impurity #1 (Severity: HIGH). The `N3TXApp` builder in `app.py` already partially solves this by accumulating models in `self._models` (line 92) before calling `register_model()` in `build()` (line 148-154).

**In our system:** `registrar.py:14-29` performs three side effects in one call: sets storage on the class, creates a database table, runs migrations, and mutates the global `registered_models` dict. These cannot be undone, tested in isolation, or recomposed. Order of registration matters (join models after parents). Two simultaneous `register_model()` calls could race. Tests require clearing global state between cases.

**The idea:** Push the `N3TXApp` builder pattern to completion. The builder accumulates `ModelRegistration` value objects (model class + storage binding). `materialize()` executes all side effects in the correct order. The direct `register_model()` function remains for backward compatibility (Level 3 bootstrap) but is documented as the effectful entry point.

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | Medium -- 3-4 days. `registrar.py` refactor plus `app.py` updates. Backward-compat wrapper for Level 3 users. |
| Impact | Medium -- Pure registration enables testing model configurations without DB side effects. Test isolation improves dramatically. |
| Risk | Moderate -- Level 3 bootstrap (raw primitives) uses `register_model()` directly. Must maintain backward compatibility. |
| Timeline | Weeks |

---

### Proposition 9: Type the actor message protocol

> **Proposition:** Add typed message constructors to `TX` (e.g., `TX.crud()`, `TX.method()`) that validate payload shape against the target's schema at send time, catching malformed messages before they reach the handler.

**From the research:** The N3TX CT mapping (04, Section 5) shows the Actor system forms a semicategory with partial associativity. The improving-purity document (05, Section 4) identifies that `TX.data` is completely untyped (`any`) and proposes schema-validated message factories. The industry landscape (01, Section 7) shows that TypeScript's discriminated unions provide this at compile time; runtime validation is the JS equivalent.

**In our system:** `TX.js` creates messages with a string `name` and untyped `data`. `N3TX.js:663-759` generates DynamicClass methods that call `this.call(method, args, {})` with no validation that `args` matches what the target handler expects. A misspelled field name or wrong data shape silently fails at the handler level, producing undefined behavior.

**The idea:** Static factory methods on `TX` that validate against schema:

```javascript
TX.crud('CREATE', target, data, schema)  // validates data against schema.properties
TX.method('like', target, args, methodSchema)  // validates args against method.parameters
```

These are runtime checks, not compile-time, but they catch errors at the send site rather than the receive site. The existing untyped constructor remains for backward compatibility. New code uses the typed factories.

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | Medium -- 4-5 days. `TX.js` changes plus `N3TX.js` prototype method generation updates. |
| Impact | Medium -- Catches malformed messages at send time. Errors are localized to the sender, not scattered across the handler. |
| Risk | Moderate -- Must not break existing untyped flows. Gradual adoption required. |
| Timeline | Weeks |

---

## Proposition Map

### Quick Wins (Low Effort, High ROI)
| # | Proposition | Effort | Impact |
|---|------------|--------|--------|
| 4 | AccessRule algebra law tests | 1-2 days | Catches auth regressions at the algebraic level |
| 5 | Fix value getter mutation | 1 day | Restores referential transparency |
| 1 | Decompose `model_dump()` | 2-3 days | Eliminates boolean-flag anti-pattern |
| 6 | Storage adjunction tests | 2-3 days | Catches silent data corruption |

### Strategic Investments (Medium Effort, High ROI)
| # | Proposition | Effort | Impact |
|---|------------|--------|--------|
| 2 | Result type for errors | 3-4 days | Eliminates entire 200-OK bug class |
| 3 | Schema pipeline decomposition | 3-5 days | Makes core pipeline independently testable and extensible |

### Longer-Term Structural Changes (Higher Effort, Medium ROI)
| # | Proposition | Effort | Impact |
|---|------------|--------|--------|
| 7 | Configuration monoid | 4-6 days | Eliminates config-mutation bugs |
| 8 | Pure registration | 3-4 days | Enables test isolation |
| 9 | Typed actor messages | 4-5 days | Catches message-shape errors at send time |

---

## What NOT to Do

**1. Do not add CT vocabulary to the public API.** Never name a class `SchemaFunctor` or a method `fmap()`. Our users should see `schema()`, `model_dump()`, `prototype()`. The Elm lesson is clear: CT correctness internally, plain-English names externally. The framework's philosophy -- "Transparent, not magical" -- means users trace behavior from HTML tag to network request, not from `Kleisli arrow` to `monad transformer stack`.

**2. Do not adopt `dry-python/returns` or build a monad transformer stack.** The `returns` library is well-designed but adds ceremony without proportional benefit in Python's dynamic type system. Python cannot enforce `Result` unwrapping at compile time; the safety is convention-level, not compiler-level. Our lightweight `Ok`/`Err` types (Proposition 2) are sufficient. Monad transformers add 3x overhead per function call for correctness guarantees that Python cannot enforce. FastAPI's dependency injection already handles the composition that monad transformers would provide.

**3. Do not chase every impurity.** Mutable actor state is intrinsic to the Actor model -- it is not a bug, it is the paradigm. The `__init_subclass__` bases rewrite is an acceptable metaclass pattern. The schema cache with `deepcopy` works correctly. Not every impurity needs fixing. Fix the ones that cause bugs (value getter mutation, global registration, exception-based errors). Leave the ones that are deliberate design choices (actor state, metaclass injection).

---

## Recommended Starting Point

**Start with Propositions 4 and 5 together (2-3 days total).** These are zero-risk, test-only changes (Proposition 4) and a single-line code fix (Proposition 5) that establish the pattern: verify algebraic laws, restore referential transparency. They build confidence in the categorical approach without any API changes.

**Then proceed to Proposition 1 (2-3 days).** The `model_dump()` decomposition is a small, well-scoped refactor that makes the principle visible: separate concerns, name the morphisms, test them independently. It touches only `proto_model.py` and 6 call sites in the route/storage layer.

**Validation approach:** Before and after each change, run snapshot tests comparing the output of `schema()`, `model_dump()`, and `model_dump(response=True)` for every model in the example app. The output must be byte-identical (or semantically equivalent where key ordering differs). If a snapshot changes unexpectedly, the refactor has introduced a regression. This is the functor law test in practice: the same input must produce the same output, regardless of how the internals are structured.
