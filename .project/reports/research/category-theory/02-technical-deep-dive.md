# Category Theory and N3TX: A Technical Deep Dive

**How CT Concepts Map to Software Engineering Patterns -- and Where N3TX's Abstractions Already Embody Them**

---

## Executive Summary

Category theory (CT) is the mathematics of structure and composition. It provides a
language for describing how things relate, transform, and compose -- the same
concerns that dominate software architecture. This document maps core CT concepts
to concrete engineering patterns, then shows how N3TX's schema-driven architecture
already embodies many of these structures, often without naming them. More importantly,
it identifies where making these structures *explicit* could improve composability,
correctness guarantees, and testability.

N3TX's central thesis -- "the model is the app" -- is, in CT terms, a functor from
the category of Python models to the category of full-stack applications. This
document makes that precise.

**Audience:** Technical CEOs, engineering leads, and senior engineers who think in
code but want to understand the mathematical structures that make code composable.

**Reading time:** 25-35 minutes.

---

## Table of Contents

1. [Core CT Concepts for Software Engineers](#1-core-ct-concepts-for-software-engineers)
2. [CT Patterns Hiding in Everyday Code](#2-ct-patterns-hiding-in-everyday-code)
3. [Algebraic Data Types](#3-algebraic-data-types)
4. [Laws and Correctness](#4-laws-and-correctness)
5. [Type Theory Connections](#5-type-theory-connections)
6. [Effect Systems and Algebraic Effects](#6-effect-systems-and-algebraic-effects)
7. [Commutative Diagrams as Architecture Diagrams](#7-commutative-diagrams-as-architecture-diagrams)
8. [N3TX Through the CT Lens](#8-ntx-through-the-ct-lens)
9. [Opportunities: Purifying the Abstractions](#9-opportunities-purifying-the-abstractions)
10. [Sources](#10-sources)

---

## 1. Core CT Concepts for Software Engineers

Category theory studies the *structure of structure*. Where algebra studies
sets-with-operations, CT studies the relationships *between* algebraic structures.
For engineers, this translates to: CT is the study of interfaces, transformations,
and composition guarantees.

### 1.1 Categories

A **category** has three ingredients:

| Ingredient    | Math                           | Software                          |
|---------------|--------------------------------|-----------------------------------|
| Objects       | Abstract "things"              | Types (int, str, Product, User)   |
| Morphisms     | Arrows between objects         | Functions / transformations        |
| Composition   | If f: A->B and g: B->C exist, then g.f: A->C exists | Function composition: `g(f(x))` |
| Identity      | For every object A, id_A: A->A | The identity function: `lambda x: x` |

```
    Category of Python Types
    ========================

    Objects:  int, str, float, Product, User, Comment, ...

    Morphisms (functions between types):

        str ──── len ────> int
        Product ── model_dump ──> dict
        dict ──── json.dumps ──> str

    Composition:

        Product ── model_dump ──> dict ── json.dumps ──> str
                          =
        Product ─── json_serialize ──> str

    Identity:

        Product ── id ──> Product    (lambda p: p)
```

**The key insight:** A category is defined not by what its objects *are*, but by
how they *relate*. Two categories can have completely different objects but identical
relational structure. This is what makes CT useful for architecture: it captures
shape without locking into implementation.

> **N3TX connection:** The registered_models dict is a category. Objects are
> model classes. Morphisms are the transformations between them: `model_dump()`,
> `schema()`, `model_dump(response=True)`. Composition is guaranteed by the
> framework -- `schema()` always produces a valid JSON Schema, `model_dump(response=True)`
> always injects `$schema` and `$id`.

### 1.2 Functors

A **functor** is a structure-preserving map between two categories. It maps objects
to objects and morphisms to morphisms, preserving composition and identity.

```
    FUNCTOR: F maps Category C to Category D
    =========================================

    Category C (Python)          F          Category D (JSON Schema)
    ┌─────────────────┐     ──────>     ┌──────────────────────┐
    │  Product         │                │  {"type": "object",   │
    │     |            │                │   "properties": ...}  │
    │  model_dump()    │                │        |              │
    │     |            │                │   JSON transform      │
    │     v            │                │        |              │
    │   dict           │                │        v              │
    │                  │                │  {"type": "object"}   │
    └─────────────────┘                └──────────────────────┘

    F preserves structure:
      F(Product) = ProductSchema
      F(model_dump) = schema_transform
      F(id) = id    (identity maps to identity)
```

**In code, functors appear as:**

```python
# Array.map is a functor from (a -> b) to (List[a] -> List[b])
prices = [p.price for p in products]       # map(lambda p: p.price, products)

# Promise.then is a functor from (a -> b) to (Promise[a] -> Promise[b])
# fetch('/api/products').then(r => r.json()).then(data => data.length)
```

The critical property: **functors preserve composition**.

```python
# These must be equivalent (functor law):
list(map(len, map(str, [1, 2, 3])))     # map(f) . map(g)
list(map(lambda x: len(str(x)), [1, 2, 3]))  # map(f . g)
# Both produce [1, 1, 1]
```

| CT Concept      | Python Example                   | JS Example                    |
|-----------------|----------------------------------|-------------------------------|
| Functor         | `map(f, list)`                   | `array.map(f)`               |
| Endofunctor     | `Optional[T]`, `List[T]`        | `Promise<T>`, `Array<T>`     |
| Functor law 1   | `map(id, xs) == xs`             | `arr.map(x => x) === arr`    |
| Functor law 2   | `map(f, map(g, xs)) == map(f.g, xs)` | `arr.map(g).map(f) === arr.map(x => f(g(x)))` |

> **N3TX connection:** `ProtoModel.schema()` is a functor from the category of
> Python model classes to the category of JSON Schema documents. It maps each model
> (object) to its schema and each field transformation (morphism) to a schema
> property definition. The `prototype()` function in `N3TX.js` is a second functor
> that maps JSON Schema objects to DynamicClass constructors. The composition
> `prototype(schema(Model))` is itself a functor from Python models to JS runtime
> classes.

### 1.3 Natural Transformations

A **natural transformation** is a morphism *between functors*. Given two functors
F and G from category C to category D, a natural transformation alpha provides,
for every object A in C, a morphism alpha_A: F(A) -> G(A) in D -- and these
morphisms "commute" with the functors.

```
    Natural Transformation: alpha : F => G
    ========================================

    For every object A in C:

         F(A) ──── alpha_A ────> G(A)
          |                        |
       F(f)|                       |G(f)
          v                        v
         F(B) ──── alpha_B ────> G(B)

    The square commutes:  alpha_B . F(f) = G(f) . alpha_A
```

**In code:**

```python
# Two "functors" for representing a Product:
# F = model_dump (Python dict representation)
# G = model_dump(response=True) (API response representation)

# The natural transformation between them is the injection of $schema/$id:

product = Product(id=1, name="Widget", price=9.99)

f_product = product.model_dump()
# {'id': 1, 'name': 'Widget', 'price': 9.99, 'image': '', ...}

g_product = product.model_dump(response=True)
# {'$schema': 'http://localhost:5000/Product',
#  '$id': 'http://localhost:5000/products/1',
#  'id': 1, 'name': 'Widget', 'price': 9.99, ...}

# The natural transformation alpha: F => G adds metadata.
# It commutes: for any field transformation f on Product,
#   alpha(F(f(product))) = G(f(product))
```

**Other natural transformations in software:**

| Transformation           | From functor       | To functor          |
|--------------------------|--------------------|--------------------|
| `list()` on a generator  | Generator[T]       | List[T]            |
| `.json()` on Response     | Response[T]        | Promise<JSON>       |
| Adapter pattern           | InterfaceA[T]      | InterfaceB[T]       |
| Serializer                | InMemory[T]        | Serialized[T]       |

> **N3TX connection:** The `_serialize()` function in `routes_fastapi.py` is a
> natural transformation. It maps from the "in-memory model instance" functor to the
> "API response dict" functor. The `access_schema()` function is another: it
> transforms from the "Python access rule objects" functor to the "JSON-serialized
> access rules" functor.

### 1.4 Monads

A **monad** is an endofunctor M (a functor from a category to itself) equipped with
two natural transformations:

- **unit** (also called `return` or `pure`): wraps a value into the monadic context. `a -> M(a)`
- **join** (also called `flatten`): collapses nested contexts. `M(M(a)) -> M(a)`

Equivalently, via **bind** (`>>=` or `flatMap`): `M(a) -> (a -> M(b)) -> M(b)`

```
    Monad M
    =======

    unit: a ──────> M(a)           "wrap a value"
    join: M(M(a)) ──> M(a)        "flatten one layer"
    bind: M(a) ──> (a -> M(b)) ──> M(b)   "chain operations"


    Example: Optional (Maybe) monad

    unit:  5       ──>  Some(5)
    join:  Some(Some(5)) ──>  Some(5)
           Some(None)    ──>  None
    bind:  Some(5) >>= (lambda x: Some(x+1)) = Some(6)
           None    >>= (lambda x: Some(x+1)) = None
```

**In Python:**

```python
from typing import Optional

# Optional IS the Maybe monad
def get_user(id: int) -> Optional[User]: ...
def get_email(user: User) -> Optional[str]: ...

# Without monadic composition (pyramid of doom):
user = get_user(1)
if user is not None:
    email = get_email(user)
    if email is not None:
        send_notification(email)

# With monadic bind (Python doesn't have sugar, but the pattern is clear):
# Some(1) >>= get_user >>= get_email >>= send_notification
```

**In JavaScript:**

```javascript
// Promise IS a monad
//   unit  = Promise.resolve(value)
//   bind  = promise.then(f)       where f returns a Promise

fetch('/api/products')           // Promise<Response>
  .then(r => r.json())           // bind: Response -> Promise<JSON>
  .then(data => data[0])         // bind: JSON -> Promise<Product>
  .then(p => console.log(p.name)) // bind: Product -> Promise<void>
```

| Monad Pattern     | Python              | JavaScript              | What it does            |
|-------------------|---------------------|-------------------------|------------------------|
| Maybe/Optional    | `Optional[T]`       | `x?.prop`               | Short-circuits on None |
| Result/Either     | `Result[T, E]`      | `Promise<T>`            | Propagates errors      |
| List              | `List[T]`           | `Array<T>.flatMap`      | Non-determinism        |
| IO                | (no stdlib)         | `async/await`           | Defers side effects    |
| Reader            | dependency injection | context/closure         | Environment threading  |

> **N3TX connection:** The `StorableMixin` CRUD chain is monadic. Each operation
> returns an `Optional` result that can fail (entity not found = None). The
> `_resolve_user()` function in `routes_fastapi.py` is a Reader-monad-like pattern:
> it threads the request context through to resolve the user type hint into an actual
> model instance.

### 1.5 Monoids

A **monoid** is a set with an associative binary operation and an identity element.

```
    Monoid (M, *, e)
    ================
    * : M x M -> M        (binary operation, closed)
    e : M                  (identity element)

    Laws:
      (a * b) * c = a * (b * c)    (associativity)
      e * a = a = a * e            (identity)
```

| Monoid           | Set           | Operation    | Identity     |
|------------------|---------------|-------------|-------------|
| String concat    | strings       | `+`         | `""`        |
| List append      | lists         | `+`         | `[]`        |
| Integer addition | integers      | `+`         | `0`         |
| Integer multiply | integers      | `*`         | `1`         |
| Boolean AND      | booleans      | `and`       | `True`      |
| Boolean OR       | booleans      | `or`        | `False`     |
| Dict merge       | dicts         | `{**a, **b}`| `{}`        |
| Function compose | endofunctions | `.`         | `id`        |
| Config merge     | config dicts  | deep_merge  | `{}`        |

> **N3TX connection:** The `AccessRule` algebra is a monoid-like structure.
> `OrRule` and `AndRule` compose rules associatively. However, there is no explicit
> identity element defined (which would be `ANYONE` for OR and a hypothetical
> `ALWAYS` for AND). The `model_dump(response=True)` dict merge
> `{'$schema': ..., '$id': ..., **data}` is a monoid operation on dicts.

### 1.6 Adjunctions

An **adjunction** is a pair of functors F and G between categories C and D that
are "optimal inverses" of each other:

```
    Adjunction: F -| G
    ===================

    F: C -> D    (left adjoint, "free" construction)
    G: D -> C    (right adjoint, "forgetful" functor)

    For all A in C, B in D:
      Hom_D(F(A), B)  ~=  Hom_C(A, G(B))

    "Morphisms from F(A) to B in D correspond exactly to
     morphisms from A to G(B) in C"
```

**In software, adjunctions appear as:**

| Left adjoint (F)         | Right adjoint (G)       | Relationship                  |
|--------------------------|------------------------|-------------------------------|
| Free monoid (List)       | Forgetful (underlying set) | Lists are the "freest" monoid |
| Parser                   | Printer/Serializer      | Parsing is left adjoint to serialization |
| SQL query builder        | SQL result set          | Queries are free, results forget structure |
| Schema -> Form generator | Form submission -> Data | Form generation is adjoint to data extraction |
| `create_app(models=...)`| `registered_models`     | Registration is adjoint to lookup |

> **N3TX connection:** The entire `ProtoModel -> JSON Schema -> DynamicClass` pipeline
> can be understood as an adjunction. `schema()` is the left adjoint (free construction:
> given a model, freely generate everything the frontend needs). The `prototype()` function
> in N3TX.js is the right adjoint's action: it "forgets" the Python-specific details and
> retains only what JS needs. The adjunction guarantees that round-tripping preserves
> essential structure.

### 1.7 Products and Coproducts

**Products** (AND-types) and **Coproducts** (OR-types) are the categorical
generalization of tuples and unions.

```
    Product (A x B)                    Coproduct (A + B)
    ===============                    =================

         A x B                              A + B
        /     \                            /     \
    pi_1       pi_2                   inj_1       inj_2
      /         \                      /             \
     A           B                    A               B

    "Has both A AND B"             "Has either A OR B"
    Tuples, structs, records       Unions, enums, variants
```

| CT Concept  | Python                        | TypeScript                   |
|-------------|-------------------------------|------------------------------|
| Product     | `class P: a: int; b: str`     | `type P = { a: number, b: string }` |
| Product     | `Tuple[int, str]`             | `[number, string]`           |
| Coproduct   | `Union[int, str]`             | `number \| string`           |
| Coproduct   | `Optional[T]` = `Union[T, None]` | `T \| null`              |
| Unit (terminal object) | `None`             | `void` / `undefined`         |
| Void (initial object)  | `NoReturn`         | `never`                      |

> **N3TX connection:** Every Pydantic model is a product type -- it has field A
> AND field B AND field C. The `anyOf` construct in JSON Schema (used by
> `resolveAnyOf()` in `form.js`) represents coproducts. The `Optional[Ref['self']]`
> type on `Comment.parent_id` is a coproduct: either a self-reference integer OR None.

---

## 2. CT Patterns Hiding in Everyday Code

Engineers use category theory daily -- they just call it something else.

### Pattern Mapping Table

| Everyday Pattern          | CT Name                    | Structure Preserved           |
|---------------------------|----------------------------|-------------------------------|
| `map/filter/reduce`       | Functorial operations      | Container structure           |
| Middleware chains          | Kleisli composition        | Effect sequencing             |
| Builder pattern            | Free monoid / free monad   | Deferred computation          |
| Strategy pattern           | Morphism selection         | Interface (same source/target)|
| Adapter pattern            | Natural transformation     | Structure between representations |
| Pipeline / chain           | Composition in a category  | Sequential transformation     |
| Optional / Result          | Maybe / Either monads      | Failure propagation           |
| Decorator pattern          | Endofunctor                | Wrapping preserves interface  |
| Observer pattern           | Coalgebra / comonad        | State observation             |
| Dependency injection       | Reader monad               | Environment threading         |
| Event sourcing             | Free monad                 | Deferred interpretation       |
| State machine              | Coalgebra                  | State transitions             |

### 2.1 map/filter/reduce as Functorial Operations

```python
products = [Product(name="A", price=10), Product(name="B", price=20)]

# map is a functor: preserves list structure, transforms contents
names = list(map(lambda p: p.name, products))  # ["A", "B"]

# filter is a natural transformation from List to List
# (it preserves the "listness" but changes the contents)
cheap = list(filter(lambda p: p.price < 15, products))

# reduce is a catamorphism (fold): collapses the list structure
total = functools.reduce(lambda acc, p: acc + p.price, products, 0)  # 30
```

### 2.2 Middleware Chains as Kleisli Composition

```
    Request ──> Middleware1 ──> Middleware2 ──> Handler ──> Response

    Each middleware: Request -> M(Request)   where M = "with side effects"

    Kleisli composition:
      (a -> M(b)) >=> (b -> M(c))  =  (a -> M(c))
```

In N3TX, the FastAPI middleware chain follows this pattern:

```python
# JWTAuthMiddleware: Request -> Request-with-user
# CORS middleware: Request -> Request-with-headers
# Authorization: Request -> Request-or-403

# Composed:
# Request -> JWTAuth -> CORS -> Auth -> Handler -> Response
# Each step is a Kleisli arrow in the "HTTP effect" monad
```

### 2.3 Builder Pattern as Free Monoid

```python
# N3TXApp builder is a free monoid over model registrations
pb = N3TXApp(storage="sqlite:///app.db")
pb.model(Product)    # append operation
  .model(User)       # append operation
  .join(Product, Comment)  # append operation
app = pb.build()     # interpret the accumulated structure

# The list of operations is "free" -- it accumulates without executing.
# build() is the "fold" that interprets the accumulated monoid.
```

### 2.4 Strategy Pattern as Morphism Selection

```python
# AuthorizationResolver Protocol defines a morphism interface:
#   resolve_rule: (ModelClass, action) -> AccessRule
#   authorize:    AccessContext -> None | raise
#   sql_filter_for: AccessContext -> Optional[Tuple[str, list]]

# DefaultResolver is one morphism (strategy).
# Any class implementing AuthorizationResolver is another.
# The Protocol defines the Hom-set; each implementation is a morphism in it.
```

### 2.5 The Adapter Pattern as Natural Transformation

```python
# access_schema() is a natural transformation:
#   For every model M:  access_rules(M) -> json_dict(M)
#
# It transforms the "AccessRule functor" into the "JSON dict functor"
# while preserving the rule structure (OR stays OR, AND stays AND).

def access_schema(model_class):
    access = getattr(model_class, '__access__', None)
    if access is None:
        return {"*": AUTHENTICATED.to_dict()}
    result = {}
    for action, rule in access.items():
        result[action] = rule.to_dict()  # Natural transformation component
    return result
```

---

## 3. Algebraic Data Types

### 3.1 Product Types vs Sum Types

Software types fall into two fundamental categories, directly corresponding to
categorical products and coproducts.

```
    Product Type (AND)                  Sum Type (OR)
    ==================                  ===============

    class Product:                      AccessRule = (
        name: str          # AND            _Anyone          # OR
        price: float       # AND            _Authenticated   # OR
        description: str   # AND            _Owner           # OR
                                            _Role            # OR
    # Inhabitants:                          OrRule           # OR
    # Every instance has ALL fields.        AndRule          # OR
    # Cardinality: |str| * |float| * |str|  NotRule          # OR
                                            Where
                                        )
                                        # Each instance is ONE of these.
                                        # Cardinality: |_Anyone| + |_Auth| + ...
```

### 3.2 How Pydantic Models Map

Every Pydantic `BaseModel` (and therefore every `ProtoModel`) is a product type:

```python
class Product(ProtoModel):
    name: str              # Field 1: str
    price: float           # Field 2: float
    description: str       # Field 3: str
    comments: ListRef[Comment]  # Field 4: List[Comment]

# Product ~ str x float x str x List[Comment]
# This is a categorical product.
```

Sum types in Python use `Union`:

```python
# Optional is a sum type: T + None
parent_id: Optional[Ref['self']]   # Ref[self] + None

# The JSON Schema representation:
# {"anyOf": [{"type": "selfref"}, {"type": "null"}]}
# This is a coproduct.
```

### 3.3 The N3TX Type Algebra

```
    N3TX's type algebra
    =====================

    Primitives:   int, float, str, bool (terminal objects)

    Products:     ProtoModel subclasses (named products with fields)
                  Product = str x float x str x List[Comment]

    Coproducts:   Optional[T] = T + None
                  Union[A, B] = A + B
                  anyOf in JSON Schema

    Recursion:    ListRef[T] = mu X. 1 + (T x X)    (list is recursive coproduct)
                  Ref['self'] = mu X. ... x Optional[X]  (self-referential)

    Exponentials: Callable methods (@expose_route)
                  (Input) -> Output  = Output^Input
```

### 3.4 Pattern Matching as Structural Recursion

Pattern matching on sum types is the computational dual of construction on product types:

```python
# Construction (product type): combine all fields
product = Product(name="Widget", price=9.99, description="...")

# Destruction (pattern matching on sum type):
match access_rule:
    case _Anyone():        handle_public()
    case _Authenticated(): handle_auth()
    case _Owner():         handle_owner()
    case OrRule(rules):    handle_or(rules)
    case AndRule(rules):   handle_and(rules)

# In N3TX's AccessRule, this happens via polymorphic dispatch:
# rule.evaluate(ctx)  -- each subclass implements its own case
# This is "Church-encoded" pattern matching via virtual dispatch.
```

---

## 4. Laws and Correctness

### 4.1 Functor Laws

```
    Law 1 (Identity):     F(id_A) = id_{F(A)}
    Law 2 (Composition):  F(g . f) = F(g) . F(f)
```

**Why these matter in N3TX:**

```python
# Law 1: schema(identity_transform(Model)) should equal schema(Model)
# If schema() adds spurious modifications when no fields change,
# Law 1 is violated.

# Law 2: schema(add_field(rename_field(Model))) should equal
#         schema_transform(add_field)(schema_transform(rename_field)(schema(Model)))
# The schema transformation should compose cleanly.

# VIOLATION EXAMPLE (hypothetical):
# If schema() caches a result and cache invalidation fails,
# then schema(modified_model) returns stale data.
# This breaks Law 2: the composition of "modify then generate schema"
# diverges from "generate schema then transform schema."
```

> **Current N3TX status:** The `_schema_cache` with `invalidate_schema_cache()`
> is a manual enforcement of functor Law 1 -- it ensures that `schema()` returns
> fresh results when the model changes. The `deepcopy` on cache hits prevents
> mutation from breaking Law 2.

### 4.2 Monad Laws

```
    Left identity:   unit(a) >>= f     =  f(a)
    Right identity:  m >>= unit        =  m
    Associativity:   (m >>= f) >>= g   =  m >>= (x -> f(x) >>= g)
```

**In N3TX's CRUD chain:**

```python
# Left identity: Creating then immediately getting should return the same thing.
# unit: Product(**data) wraps data into a model
# >>= : .create() persists it
# f: .get(id) retrieves it

created = Product.create(Product(name="X", price=5))
fetched = Product.get(created.id)
# Left identity: these should be equivalent (modulo id assignment)

# Right identity: Getting a record and re-saving it should be a no-op.
product = Product.get(1)
Product.update(1, product.model_dump())
refetched = Product.get(1)
# product and refetched should be equivalent

# Associativity: chaining operations should not depend on grouping.
# (create >>= update) >>= get  =  create >>= (update >>= get)
```

### 4.3 What Happens When Laws Are Violated

| Violated Law             | Symptom                                    | N3TX Example                     |
|--------------------------|--------------------------------------------|------------------------------------|
| Functor identity         | Transforming with no-op changes output     | Schema cache returns stale data    |
| Functor composition      | Order of transforms matters unexpectedly   | Field exclusion applied twice      |
| Monad left identity      | Wrap-then-unwrap loses data                | Create then Get loses populated fields |
| Monad right identity     | Unwrap-then-wrap adds phantom changes      | Update with no changes bumps timestamp |
| Monad associativity      | Chaining order changes result              | Nested saves create duplicate FKs  |
| Monoid associativity     | Merging order matters                      | Config dict merge is order-dependent |

> **The 200-OK error case study from CLAUDE.md is a law violation.** The HTTP
> response functor should map errors to error-status responses and successes to
> success-status responses. When an error was returned with 200 OK, the functor
> law was broken: `F(error) != error_response`. The fix (MethodError -> HTTPException)
> restored the law.

---

## 5. Type Theory Connections

### 5.1 Curry-Howard Correspondence

The Curry-Howard correspondence establishes a deep connection:

| Logic                    | Type Theory              | Category Theory          |
|--------------------------|--------------------------|--------------------------|
| Proposition              | Type                     | Object                   |
| Proof                    | Program (value)          | Morphism (arrow)         |
| Implication A => B       | Function A -> B          | Morphism A -> B          |
| Conjunction A AND B      | Product type (A, B)      | Product A x B            |
| Disjunction A OR B       | Sum type A | B           | Coproduct A + B          |
| True                     | Unit type ()             | Terminal object 1        |
| False                    | Empty type (Never)       | Initial object 0         |
| Universal quantification | Polymorphism (forall a)  | Natural transformation   |

**What this means for N3TX:**

```python
# The type signature IS a proposition:
def get(cls, id: int, as_dict: bool = False) -> Any:
    ...

# This "claims": Given an int and a bool, I can produce Any.
# A working implementation IS the proof of this claim.

# A more precise type would be a stronger claim:
def get(cls, id: int) -> Optional[Product]:
    ...
# This claims: Given an int, I can produce either a Product or Nothing.
# This is a more honest contract.
```

### 5.2 Parametric Polymorphism and Free Theorems

When a function is polymorphic (works for all types), its behavior is severely
constrained by its type alone -- we get "theorems for free."

```python
# For any function f: List[A] -> List[A] where A is generic:
# f MUST be some combination of reordering, duplicating, or dropping elements.
# It CANNOT fabricate new elements (it doesn't know what A is).

# N3TX's AbstractStorage interface is parametrically polymorphic:
class AbstractStorage(ABC):
    def list(self, model_class: Type[Any], ...) -> List[Any]: ...
    def get(self, model_class: Type[Any], id_: int, ...) -> Any: ...

# The free theorem: ANY implementation of AbstractStorage that satisfies
# these signatures MUST treat model_class uniformly. It cannot have
# special-case behavior for Product vs Comment (though it may use
# their metadata, like __tablename__, which is part of the type).
```

### 5.3 JSON Schema Types and Type Theory

JSON Schema is a type theory in its own right:

```
    JSON Schema          Type Theory         Category Theory
    ===========          ===========         ===============
    "type": "string"     String              Object in Set
    "type": "number"     Number              Object in Set
    "type": "object"     Record/Product      Product
    "type": "array"      List                Functor (List endofunctor)
    "anyOf": [...]       Union/Sum           Coproduct
    "allOf": [...]       Intersection        Pullback (limit)
    "$ref"               Named type / alias  Morphism via name
    "enum": [...]        Literal type        Finite coproduct
    "const"              Singleton type      Terminal object
    "properties"         Named fields        Projection morphisms
    "required"           Non-optional        No coproduct with unit
```

> **N3TX's schema generation is a type-theoretic compiler.** `ProtoModel.schema()`
> translates from Python's type system (Pydantic annotations) to JSON Schema's type
> system. The `prototype()` function in N3TX.js then translates from JSON Schema to
> JavaScript's runtime type system (DynamicClass with typed getters/setters). This is
> a chain of type-preserving translations -- exactly what a functor is.

---

## 6. Effect Systems and Algebraic Effects

### 6.1 The Problem: Side Effects Break Composition

Pure functions compose trivially: `g(f(x))` works if the types match. But real
software has side effects: database reads, network calls, logging, authentication.
These break simple composition.

```python
# Pure: composes easily
def double(x: int) -> int: return x * 2
def increment(x: int) -> int: return x + 1
result = increment(double(5))  # 11, always

# Effectful: composition is fragile
def get_product(id: int) -> Product:  # may fail (DB read)
    return Product.get(id)             # may return None
def get_price(p: Product) -> float:   # assumes p is valid
    return p.price
# get_price(get_product(1))  -- crashes if get_product returns None
```

### 6.2 Monads as Effect Handlers

Monads *encode* effects as types, making them composable again:

```
    Effect          Monad              Encoding
    ======          =====              ========
    Failure         Maybe/Optional     None represents failure
    Error info      Either/Result      Left(error) | Right(value)
    Non-determinism List               Multiple possible results
    State           State              Thread state through computation
    I/O             IO                 Defer side effect to runtime
    Environment     Reader             Thread config/context implicitly
    Logging         Writer             Accumulate log alongside value
    Async           Promise/Future     Deferred computation
```

### 6.3 How Effects Map to N3TX

```
    N3TX's Effect Stack
    =====================

    Request arrives
        |
        v
    [Reader effect: extract JWT user from request.state]
        |
        v
    [Either effect: authorization check (AccessDenied or continue)]
        |
        v
    [IO effect: database read/write via StorableMixin]
        |
        v
    [Writer effect: logging via logger.info/debug/error]
        |
        v
    [Either effect: serialize response or raise HTTPException]
        |
        v
    Response sent
```

Each layer in this stack is an effect, and the composition of these effects
follows monad transformer rules -- even though N3TX doesn't explicitly use
monads.

### 6.4 Algebraic Effects (Modern Alternative to Monads)

Algebraic effects separate the *declaration* of an effect from its *handling*.
Instead of choosing a specific monad, you declare what effects your code needs,
and a handler interprets them.

```
    Traditional (monad-based):
    ==========================
    def get_product(id):           # Locked to IO + Maybe
        result = db.query(id)      # IO effect baked in
        if not result:
            return None            # Maybe effect baked in
        return result

    Algebraic effects (conceptual):
    ===============================
    def get_product(id):
        result = perform DatabaseRead(id)   # Declare "I need DB"
        result = perform Validate(result)   # Declare "I need validation"
        return result

    # Handler decides HOW to fulfill these:
    with handler(DatabaseRead=sqlite_backend, Validate=strict):
        product = get_product(1)
```

> **N3TX already does this structurally.** The `StorableMixin` is injected via
> `__init_subclass__` -- it's a handler for the "storage effect." The
> `AbstractStorage` protocol is the effect declaration. `SQLiteStorage` is one
> handler. The `AuthorizationResolver` Protocol is another effect declaration,
> with `DefaultResolver` as the default handler. This is algebraic effects
> implemented via dependency injection and the strategy pattern.

### 6.5 Practical Benefits of Explicit Effects

| Benefit          | Without explicit effects         | With explicit effects              |
|------------------|----------------------------------|-----------------------------------|
| Testability      | Mock the entire DB               | Swap the storage handler           |
| Composition      | Manually chain try/except        | Effects compose automatically      |
| Error handling   | Scattered try/except             | Centralized error handler          |
| Refactoring      | Change ripples through stack     | Change the handler, not the code   |
| Documentation    | Read the implementation          | Read the effect signature          |

---

## 7. Commutative Diagrams as Architecture Diagrams

### 7.1 "The Diagram Commutes" = "The System Is Consistent"

In CT, a commutative diagram asserts that all paths between the same endpoints
produce the same result. In software, this is a consistency guarantee.

```
    N3TX's Core Commutative Diagram
    ==================================

    ProtoModel ─── schema() ───> JSON Schema ─── prototype() ──> DynamicClass
        |                            |                               |
    model_dump()              schema transform                  .value getter
        |                            |                               |
        v                            v                               v
    Python dict ──── serialize ───> JSON ──── parse ────────> JS Object
        |                            |                               |
    model_dump(response=True)   add $schema/$id              inject $schema/$id
        |                            |                               |
        v                            v                               v
    API Response ── HTTP transport ─> JSON body ── DynamicClass ─> N3TX Instance


    COMMUTATIVITY REQUIREMENT:
    Going right-then-down must equal going down-then-right.

    schema(model).properties["price"].type  ==  typeof DynamicClass.prototype.price
    model_dump(response=True)["$id"]        ==  ntt_instance.value["$id"]
    access_schema(model)["update"]          ==  schema.access.update (in JS)
```

### 7.2 When the Diagram Doesn't Commute: Bugs

Every bug where "the backend says X but the frontend shows Y" is a failure of
diagram commutativity. The 200-OK error from CLAUDE.md is a textbook example:

```
    BROKEN DIAGRAM (200-OK error):

    Method call ── success? ──> HTTP 200
        |                          |
    returns error string      frontend sees "success"
        |                          |
        v                          v
    '{"error": "auth required"}'  pull() refresh
        |                          |
        v                          v
    actual error               no visible error
        !=                     != expected behavior
    expected 401/403           expected error toast

    The square does NOT commute:
    "error result via success path" != "error result via error path"
```

The fix (MethodError -> HTTPException) restored commutativity:

```
    FIXED DIAGRAM:

    Method call ── raises MethodError ──> HTTPException(401)
        |                                      |
    error propagation                    frontend sees 401
        |                                      |
        v                                      v
    {"detail": "auth required"}          error toast shown
        ==                               == expected behavior
    expected error                       expected user feedback
```

### 7.3 N3TX's Full Architecture as a Commutative Diagram

```
                              BACKEND                                  FRONTEND
    ┌───────────────────────────────────────────────┐    ┌────────────────────────────────────┐
    │                                               │    │                                    │
    │  Model Definition                             │    │   Schema Bootstrap                  │
    │  (ProtoModel subclass)                        │    │   (N3TX.SCHEMA handler)              │
    │       |                                       │    │       |                             │
    │       |  __init_subclass__                     │    │       |  prototype()                │
    │       v                                       │    │       v                             │
    │  StorableMixin injected ──── schema() ────────│───>│── DynamicClass created              │
    │       |                        |              │    │       |         |                    │
    │       |                    access_schema()     │    │   typed getters  method stubs       │
    │       |                        |              │    │       |         |                    │
    │  register_model()              v              │    │       v         v                    │
    │       |              JSON Schema document      │    │   N3TX instance  ntx-method buttons  │
    │       v                   |       |           │    │       |                             │
    │  register_routes()   $defs    methods         │    │   form.js renders                   │
    │       |                   |       |           │    │       |                             │
    │       v                   v       v           │    │       v                             │
    │  CRUD endpoints      Nested schemas Method    │    │   HTML form with validation         │
    │  GET/POST/PUT/DEL    Comment, Like  routes    │    │   FieldSet groups, widgets          │
    │       |                                       │    │       |                             │
    │       v                                       │    │       v                             │
    │  SQLite storage <──── HTTP request/response ──│───<│── User interaction                  │
    │                                               │    │                                    │
    └───────────────────────────────────────────────┘    └────────────────────────────────────┘

    ALL paths from "Model Definition" to "User interaction" must commute.
    Adding a field to the model must produce a new form input.
    Changing __access__ must change button visibility.
    Adding @expose_route must create both an API endpoint AND a UI button.
```

---

## 8. N3TX Through the CT Lens

Now that the CT vocabulary is established, let us systematically identify
the categorical structures already present in N3TX.

### 8.1 The Schema Functor

**Claim:** `ProtoModel.schema()` is a functor from **Mod** (the category of N3TX
models) to **Sch** (the category of JSON Schema documents).

```
    F: Mod -> Sch

    On objects:
      F(Product) = {type: "object", properties: {name: {type: "string"}, ...}, ...}
      F(Comment) = {type: "object", properties: {name: {type: "string"}, ...}, ...}

    On morphisms (field transformations):
      F(add_field(f)) = add_property(F(f))
      F(rename_field(f, old, new)) = rename_property(F(f), old, new)
      F(change_type(f, T)) = change_property_type(F(f), T)

    Identity preservation:
      F(id_Product) = id_{F(Product)}    (no change to model -> no change to schema)

    Composition preservation:
      F(g . f) = F(g) . F(f)            (composing model changes = composing schema changes)
```

**Current status:** The functor laws hold *at startup* because schema generation
happens once and is cached. The `invalidate_schema_cache()` method exists for
the rare case where models change at runtime (tests).

### 8.2 The Prototype Functor

**Claim:** `prototype()` in N3TX.js is a functor from **Sch** to **DC** (the category
of DynamicClasses).

```
    G: Sch -> DC

    On objects:
      G(ProductSchema) = class Product extends N3TX { ... }
      G(CommentSchema) = class Comment extends N3TX { ... }

    On morphisms:
      G(add_property) = add Object.defineProperty to prototype
      G(add_method) = add method to prototype
      G(set_access) = configure permission checks
```

### 8.3 The Composite Functor: Model -> Working App

**Claim:** The composition `G . F` is a functor from **Mod** to **DC**.

```
    G . F : Mod -> DC

    This IS "the model is the app":
      (G . F)(Product) = A fully functional JS class with typed properties,
                         method stubs, CRUD operations, Observable state,
                         and Actor-model messaging.
```

But this isn't the full picture. The complete pipeline is:

```
    Mod ──F──> Sch ──G──> DC ──H──> UI

    Where H: DC -> UI maps DynamicClasses to rendered web components.

    H is realized by:
      ntx-list.js: DynamicClass -> <ntx-list> (list view)
      ntx-item.js: DynamicClass -> <ntx-item> (item view, size-adaptive)
      form.js:     Schema -> HTML form elements (with validation)
```

### 8.4 The Access Rule Algebra

The `AccessRule` hierarchy forms a **Boolean algebra** (which is a special kind
of category -- a lattice category):

```
    Access Rule Boolean Algebra
    ===========================

    ANYONE ──────── top element (True, allows everything)
       |
    AUTHENTICATED
       |
    ┌──┴──┐
    OWNER  ROLE('admin')
       |     |
       └──┬──┘
          |
    OrRule(OWNER, ROLE('admin'))
          |
    AndRule(OWNER, Where(status='draft'))
          |
    NotRule(ROLE('banned'))
          |
       ┌──┴──┐
    (1=0)    (composite conditions)
       |
    bottom element (False, denies everything)

    Operations:
      |   (OR)  = join / supremum  (OrRule)
      &   (AND) = meet / infimum   (AndRule)
      ~   (NOT) = complement       (NotRule)
```

This is already well-structured. The `__or__`, `__and__`, and `__invert__` methods
on `AccessRule` make it a proper Boolean algebra in Python's operator system.

### 8.5 The Actor System as a Category

The Matrix/Actor system in N3TX.js forms a category:

```
    Category: Act (Actor System)
    ============================

    Objects: Actors (Matrix, N3TX, DynamicClass instances, Router, ...)
    Morphisms: TX messages (events sent between actors)
    Composition: TX routing (Matrix.inbox -> Actor.inbox -> handler)
    Identity: An actor sending a message to itself (self-loop)

    The routing table (children map) defines the morphism structure.
    The inbox method is the "apply" of a morphism to an object.
```

### 8.6 Natural Transformations in N3TX

| Transformation                 | Source Functor              | Target Functor              |
|-------------------------------|----------------------------|-----------------------------|
| `model_dump(response=True)`   | InMemoryModel              | APIResponseDict             |
| `access_schema()`             | PythonAccessRules          | JSONAccessRules             |
| `_serialize()` (routes)       | ModelInstance               | SerializedResponse          |
| `normalizePopulated()` (N3TX)  | PopulatedResponse          | HrefArrayResponse           |
| `Formidable.getForm()`        | SchemaProperties           | HTMLFormElements            |
| `validationAttrs()` (form.js) | JSONSchemaConstraints      | HTML5ValidationAttributes   |

---

## 9. Opportunities: Purifying the Abstractions

This section identifies where N3TX's abstractions could be made more
categorically pure, improving composability and correctness.

### 9.1 Make the Schema Functor Explicit

**Current state:** `schema()` is a classmethod on `ProtoModel`. It works as a
functor, but the functorial nature is implicit.

**Opportunity:** Extract schema generation into an explicit functor class:

```python
# Conceptual -- make the functor a first-class object:
class SchemaFunctor:
    """Maps Model objects to Schema objects, preserving structure."""

    def map_object(self, model_class: Type[ProtoModel]) -> dict:
        """F(Model) -> Schema"""
        return model_class.schema()

    def map_morphism(self, transform: Callable) -> Callable:
        """F(field_transform) -> schema_transform"""
        def schema_transform(schema: dict) -> dict:
            return self.map_object(transform(schema))
        return schema_transform
```

**Benefit:** Makes the contract explicit: any change to `map_object` must
preserve identity and composition. Testing becomes: verify the functor laws.

### 9.2 Formalize model_dump as a Natural Transformation

**Current state:** `model_dump()` and `model_dump(response=True)` are two different
"functors" from models to dicts. The `response=True` flag switches between them.

**Opportunity:** Make the transformation between them explicit:

```python
# The natural transformation alpha: plain_dump => response_dump
# is currently embedded in model_dump() via the response flag.
# Making it a separate, composable function:

def response_transform(plain: dict, model_class: type) -> dict:
    """Natural transformation: plain dict -> API response dict."""
    meta = _get_response_meta(model_class)
    return {'$schema': meta['schema_url'], '$id': ..., **plain}

# This separates concerns:
# - model_dump() is always a "pure" dump
# - response_transform() is the natural transformation
# - Composition: response_transform(model_dump(instance))
```

**Benefit:** The two concerns (serialization and metadata injection) become
independently testable. The natural transformation laws can be verified
separately.

### 9.3 Strengthen the Storage Interface with Laws

**Current state:** `AbstractStorage` defines the CRUD interface but does not
specify laws that implementations must satisfy.

**Opportunity:** Document and test the monad-like laws:

```python
class AbstractStorage(ABC):
    """
    Storage backend interface.

    Laws (implementors MUST satisfy):
      1. Round-trip: get(create(data)).fields == data.fields  (left identity)
      2. Idempotent read: get(id) == get(id)                  (right identity)
      3. Associative ops: update(create(data), delta) ==
                          create(merge(data, delta))           (associativity)
      4. Delete terminality: get(delete(id)) is None           (absorption)
    """
```

**Benefit:** Any new storage backend (PostgreSQL, MongoDB, in-memory for tests)
can be validated against these laws automatically. Property-based testing
frameworks like Hypothesis can generate arbitrary test cases.

### 9.4 Make the AccessRule Algebra a Verified Boolean Algebra

**Current state:** AccessRule has `|`, `&`, `~` operators but no explicit identity
elements or verified algebraic laws.

**Opportunity:**

```python
# Define identity elements explicitly:
ALWAYS = _Anyone()       # Identity for AND: ALWAYS & rule == rule
NEVER = _Never()         # Identity for OR:  NEVER | rule == rule (add this)

# Verify the Boolean algebra laws:
# Commutativity:  a | b == b | a,  a & b == b & a
# Associativity:  (a | b) | c == a | (b | c)
# Distributivity: a & (b | c) == (a & b) | (a & c)
# Identity:       a | NEVER == a,  a & ALWAYS == a
# Complement:     a | ~a == ALWAYS,  a & ~a == NEVER
# De Morgan:      ~(a | b) == ~a & ~b
```

**Benefit:** These laws guarantee that complex access rules simplify predictably.
Testing reduces from O(n^2) pairwise checks to verifying a handful of algebraic
laws -- the laws then guarantee correctness for all compositions.

### 9.5 Introduce Result Types for Error Handling

**Current state:** Errors are communicated via exceptions (HTTPException,
MethodError, AccessDenied) or None returns. The 200-OK error case study showed
the danger of mixing error channels.

**Opportunity:** Introduce an explicit Result type (Either monad):

```python
from dataclasses import dataclass
from typing import TypeVar, Generic, Union

T = TypeVar('T')
E = TypeVar('E')

@dataclass(frozen=True)
class Ok(Generic[T]):
    value: T

@dataclass(frozen=True)
class Err(Generic[E]):
    error: E
    status_code: int = 400

Result = Union[Ok[T], Err[E]]

# Usage in model methods:
@expose_route('/favorite', methods=['POST'])
def favorite(self, user: User = None) -> Result[str, str]:
    if not user:
        return Err("authentication required", status_code=401)
    # ...
    return Ok('{"action": "favorited"}')

# The route layer handles Result uniformly:
def handle_result(result: Result) -> Response:
    match result:
        case Ok(value): return JSONResponse(value)
        case Err(error, code): return JSONResponse({"error": error}, status_code=code)
```

**Benefit:** Errors *cannot* sneak through the success channel. The type system
(and exhaustive pattern matching) ensures every error is handled. This is the
Either monad making the error-handling effect explicit.

### 9.6 Formalize the N3TX State Machine as a Coalgebra

**Current state:** N3TX entities have implicit states (uninitialized, schema-pending,
ready, error). These are tracked via `#prototypes` Map values: `undefined` -> `null`
-> DynamicClass.

**Opportunity:** Make the state machine explicit:

```javascript
// Current implicit states:
//   undefined  -> never seen
//   null       -> schema in flight
//   DynamicClass -> ready

// Explicit state machine (coalgebra):
const N3TXState = {
    UNKNOWN:   Symbol('UNKNOWN'),
    LOADING:   Symbol('LOADING'),
    READY:     Symbol('READY'),
    ERROR:     Symbol('ERROR'),
};

// Transition function (coalgebra observation):
function transition(state, event) {
    switch(state) {
        case N3TXState.UNKNOWN:
            if (event === 'FETCH')  return N3TXState.LOADING;
            break;
        case N3TXState.LOADING:
            if (event === 'SCHEMA') return N3TXState.READY;
            if (event === 'ERROR')  return N3TXState.ERROR;
            break;
        case N3TXState.READY:
            // Terminal state for schema lifecycle
            break;
        case N3TXState.ERROR:
            if (event === 'RETRY')  return N3TXState.LOADING;
            break;
    }
    return state;
}
```

**Benefit:** The state machine becomes verifiable. You can prove properties
like "READY is reachable from UNKNOWN" and "ERROR has a recovery path."

### 9.7 Make the Actor Message Protocol a Category

**Current state:** TX messages have `name`, `source`, `target`, `data`. The routing
is handled by pattern matching on target addresses in Matrix.inbox and Actor._send.

**Opportunity:** Formalize the message protocol as a category:

```
    Message Category
    ================

    Objects: Actor addresses (strings)
    Morphisms: TX messages from source to target
    Composition: Message forwarding (Matrix routes A->B->C as A->C)
    Identity: DESCRIBE message (actor describes itself to requestor)

    Laws:
      1. A message from A to A via Matrix = direct A.inbox
      2. Routing through B is transparent: (A->B->C) = (A->C)
      3. DESCRIBE(ATTACH(A, B)) = B's current state to A
```

### 9.8 Summary of Improvement Opportunities

| Area                    | Current Pattern              | CT Structure              | Improvement                         | Impact           |
|------------------------|------------------------------|---------------------------|--------------------------------------|------------------|
| Schema generation       | Implicit functor             | Explicit functor class     | Testable functor laws               | Correctness      |
| model_dump variants     | Flag-switched behavior       | Natural transformation     | Separated, composable transforms    | Composability    |
| Storage interface       | Unverified CRUD              | Monad with laws            | Property-based law verification     | Reliability      |
| Access rules            | Partial Boolean algebra      | Complete Boolean algebra   | Identity elements, law verification | Predictability   |
| Error handling          | Mixed exception/return       | Either monad (Result type) | Type-safe error channel             | Safety           |
| N3TX state machine       | Implicit null/undefined      | Explicit coalgebra         | Verifiable state transitions        | Debuggability    |
| Actor messaging         | Ad-hoc routing               | Message category           | Formal routing laws                 | Reliability      |
| Schema -> UI pipeline   | Implicit functor chain       | Explicit functor composition | End-to-end law verification       | Consistency      |

### 9.9 Prioritized Recommendations

**High impact, low effort:**

1. **Result types for model methods** -- Prevents the 200-OK error class entirely.
   Introduces the Either monad at the boundary where errors are most likely to be
   mishandled.

2. **Storage law documentation and tests** -- Add law assertions to the existing
   test suite. No code changes needed; just tests that verify round-trip, idempotency,
   and associativity.

3. **AccessRule identity elements** -- Add `NEVER` (bottom element). Minimal code
   change; enables law verification.

**Medium impact, medium effort:**

4. **Explicit N3TX state machine** -- Replace the implicit null/undefined/DynamicClass
   trichotomy with named states. Improves debuggability significantly.

5. **Separated natural transformations** -- Extract `response_transform` from
   `model_dump`. Makes the transformation chain testable in isolation.

**High impact, higher effort:**

6. **Functor law test harness** -- Build a test framework that verifies functor laws
   across the full schema pipeline: `Model -> Schema -> DynamicClass -> UI`.
   Any schema change that breaks a functor law is caught automatically.

7. **Algebraic effect formalization** -- Make the "effect stack" (auth, storage,
   logging, serialization) explicit. Each effect becomes a swappable handler.
   This is already partially done (AbstractStorage, AuthorizationResolver Protocol);
   completing it makes the architecture fully modular.

---

## 10. Sources

### Category Theory Foundations

- Awodey, S. (2010). *Category Theory*. Oxford University Press.
  Accessible graduate-level introduction.

- Milewski, B. (2019). *Category Theory for Programmers*.
  https://bartoszmilewski.com/2014/10/28/category-theory-for-programmers-the-preface/
  Free online book mapping CT concepts directly to Haskell and C++.

- Fong, B. & Spivak, D. (2019). *An Invitation to Applied Category Theory: Seven Sketches in Compositionality*. Cambridge University Press.
  https://arxiv.org/abs/1803.05316
  Applied CT with real-world examples.

### CT in Software Engineering

- Wadler, P. (1989). "Theorems for Free!" *Functional Programming Languages and Computer Architecture*.
  https://people.mpi-sws.org/~dreyer/tor/papers/wadler.pdf
  Foundational paper on parametric polymorphism and free theorems.

- Wadler, P. (1995). "Monads for Functional Programming." *Advanced Functional Programming*.
  https://homepages.inf.ed.ac.uk/wadler/papers/marktoberdorf/baastad.pdf
  The canonical tutorial on monads for programmers.

- Moggi, E. (1991). "Notions of Computation and Monads." *Information and Computation*.
  The original paper connecting monads to computational effects.

### Algebraic Effects

- Plotkin, G. & Pretnar, M. (2013). "Handling Algebraic Effects." *Logical Methods in Computer Science*.
  https://arxiv.org/abs/1312.1399
  Theoretical foundation for algebraic effects.

- Effect-TS. "The Effect library for TypeScript."
  https://effect.website/
  Production-grade algebraic effects in TypeScript.

- ZIO. "Type-safe, composable asynchronous and concurrent programming for Scala."
  https://zio.dev/
  Effect-based architecture in Scala.

### Type Theory

- Wadler, P. (2015). "Propositions as Types." *Communications of the ACM*.
  https://homepages.inf.ed.ac.uk/wadler/papers/propositions-as-types/propositions-as-types.pdf
  Accessible introduction to Curry-Howard correspondence.

- Pierce, B.C. (2002). *Types and Programming Languages*. MIT Press.
  Standard reference on type theory for computer scientists.

### JSON Schema as Type Theory

- JSON Schema Specification. https://json-schema.org/specification
  The formal specification that N3TX's schema generation targets.

- Pezoa, F. et al. (2016). "Foundations of JSON Schema." *International World Wide Web Conference*.
  Formal foundations and decidability results for JSON Schema.

### N3TX-Specific

- N3TX CLAUDE.md (project instructions): `/workspace/CLAUDE.md`
  Architecture overview, key patterns, development workflow.

- N3TX source code:
  - Schema functor: `/workspace/src/n3tx/core/models/proto_model.py` (lines 199-316)
  - Prototype functor: `/workspace/src/n3tx/static/core/N3TX.js` (lines 663-1075)
  - Access rule algebra: `/workspace/src/n3tx/core/authorize/rules.py` (full file)
  - Storage interface: `/workspace/src/n3tx/core/storage/abstract_storage.py` (full file)
  - Route generation: `/workspace/src/n3tx/core/api/routes_fastapi.py` (full file)
  - Actor system: `/workspace/src/n3tx/static/core/Actor.js` (full file)
  - Natural transformation (serialization): `/workspace/src/n3tx/core/api/routes_fastapi.py` (lines 34-40)
  - Form functor: `/workspace/src/n3tx/static/generators/form.js` (full file)

---

*Document generated 2026-02-26. Analysis based on N3TX codebase at commit 7550aeb (profiling branch).*
