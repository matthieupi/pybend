# Hypertext Linking (`@field` Reference Aliases) - Implementation Plan

## Purpose

This document is written for a memoryless implementation agent.

Its job is to capture the current N3TX behavior, the constraints already agreed
with the user, the technical caveats discovered during repository inspection,
and the full implementation plan required to add hypertext-style reference
aliases such as `@comments` without breaking N3TX's schema-driven architecture.

This plan is intentionally implementation-oriented. It is not a philosophical
essay about hypertext, and it is not yet the final public spec.

Note: the repository convention is `.traces/`, not `traces/`. This file lives at
`.traces/features/hypertext-linking/plan.md`.

---

## Goal

Add a first-class hypertext-linking feature where a canonical relational field
such as `comments` may be represented on the wire in two interchangeable forms:

- embedded form: `comments`
- reference form: `@comments`

The critical requirement is that the canonical property definition remains
`comments` in the model and in `schema.properties`. The `@comments` key is a wire
alias for the reference form of the same relation, not a new model field.

The feature must work across:

- Pydantic validation
- FastAPI request/response handling
- direct routing and actor routing
- dump/paginate/populate flows
- frontend schema bootstrap and runtime normalization
- generated UI and action flows

---

## Why This Exists

N3TX already behaves like a schema-driven hypermedia system, but relation values
are currently overloaded:

- collection relations like `comments` are often emitted as href arrays
- populated reads may emit embedded objects under the same canonical key
- frontend normalization collapses populated objects back to href strings

That gives N3TX flexibility, but it does not make the two modes explicit.

The desired hypertext contract is clearer:

- `comments` means embedded comments
- `@comments` means references to comments

This preserves the canonical semantic field name while making embedded-vs-link
representation explicit in the document itself.

---

## Agreed Constraints

These decisions are fixed for this plan unless the user explicitly changes them.

| Topic | Decision |
|------|----------|
| Canonical model field name | stays `comments`, never becomes `@comments` |
| Schema property names | stay canonical in `schema.properties` |
| Wire alias marker | `@` prefix, e.g. `@comments` |
| Primary feature scope | relational fields only (`Ref[T]`, `ListRef[T]`, populated relation outputs) |
| Internal backend state | canonical field names |
| Internal frontend state | canonical field names |
| Storage schema | remains canonical; no DB column named `@comments` |
| Route grammar | stays canonical; no route renaming to `@comments` |
| Backward compatibility | preserve current legacy behavior by default or behind explicit profile negotiation |
| Pydantic alias strategy | do not use field aliases as the primary implementation mechanism |

Anything that renames schema properties to `@comments` is wrong.

---

## Non-Goals For The First Implementation

- no renaming of Python model fields
- no DB-level persistence of `@field` keys as standalone columns
- no route renaming based on aliases
- no generic relation-mutation redesign for parent CRUD routes
- no full media type redesign in this wave
- no replacement of `$schema`, `$id`, `methods`, or the existing schema contract
- no attempt to make arbitrary scalar fields support `@field` twins

Important non-goal clarification:

This feature should make relational representations interchangeable on the wire.
It should not silently expand which relations are writable. If a relation is not
currently writable through parent CRUD semantics, adding `@field` does not by
itself make it writable.

---

## Required Reading Order

Before making code changes, read these files in this order:

1. `/workspace/docs/ARCHITECTURE.md`
2. `/workspace/docs/CORE.md`
3. `/workspace/BACKEND.md`
4. `/workspace/FRONTEND.md`
5. `/workspace/packages/n3tx-core/docs/schema-pipeline.md`
6. `/workspace/packages/n3tx-ui/docs/components.md`
7. `/workspace/packages/n3tx-ui/docs/formidable.md`
8. `/workspace/packages/n3tx-core/src/n3tx_core/models/proto_model.py`
9. `/workspace/packages/n3tx-core/src/n3tx_core/models/proto_dump.py`
10. `/workspace/packages/n3tx-core/src/n3tx_core/models/ref.py`
11. `/workspace/packages/n3tx-core/src/n3tx_core/utils/introspection.py`
12. `/workspace/packages/n3tx-core/src/n3tx_core/utils/typer.py`
13. `/workspace/packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py`
14. `/workspace/packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py`
15. `/workspace/packages/n3tx-core/src/n3tx_core/static/core/NTT.js`
16. `/workspace/packages/n3tx-core/src/n3tx_core/static/core/transport/NetworkAdapter.js`
17. `/workspace/packages/n3tx-core/src/n3tx_core/static/core/transport/HTTP.js`
18. `/workspace/packages/n3tx-ui/src/n3tx_ui/static/generators/form.js`
19. `/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/NTTElement.js`
20. `/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js`
21. `/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js`
22. `/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js`
23. `/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-list-field.js`
24. `/workspace/packages/n3tx-actors/src/n3tx_actors/api/network_api.py`
25. `/workspace/packages/n3tx-actors/src/n3tx_actors/models/actor_model.py`

Then inspect the tests most likely to fail under shape changes:

26. `/workspace/packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py`
27. `/workspace/packages/n3tx-core/src/n3tx_core/tests/unit/test_proto_schema.py`
28. `/workspace/packages/n3tx-core/src/n3tx_core/tests/unit/test_ref.py`
29. `/workspace/tests/frontend/tests/generators/form.test.js`
30. `/workspace/tests/frontend/tests/components/ntx-item.test.js`
31. `/workspace/tests/frontend/tests/e2e/flow-product-crud.spec.js`
32. `/workspace/examples/core/tests/test_cross_model_workflows.py`

Do not start by adding Pydantic aliases. That approach conflicts with the core
requirement that canonical property names remain unchanged in schema output.

---

## Current State Summary

### 1. Validation already tolerates undeclared `@field` keys

`ProtoModel` uses `extra = 'allow'` in
`packages/n3tx-core/src/n3tx_core/models/proto_model.py`, so extra keys like
`@comments` are accepted by Pydantic and can survive FastAPI response validation.

This is useful, but it is not sufficient to implement the feature correctly.

### 2. Pydantic aliases are the wrong primary mechanism

Repository inspection and live probes show that a field declared with
`alias='@comments'` or `validation_alias='@comments'` changes the generated JSON
Schema property name to `@comments`.

That violates the requirement that `schema.properties.comments` remain the
canonical property definition.

### 3. `ListRef[T]` already accepts either embedded objects or href strings

`ListRef[T]` is implemented as `Annotated[List[Union[T, str]], ...]` in
`packages/n3tx-core/src/n3tx_core/models/ref.py`.

That means the backend already validates both of these on the canonical field:

- `comments: [{...embedded comment...}]`
- `comments: ["/comments/1"]`

This is close to the target semantics, but it does not expose link-vs-embed
mode explicitly in the document.

### 4. Extra `@field` keys are not persisted

Storage create/update paths in
`packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py` whitelist only
declared `model_fields` and exclude collection fields from parent table writes.

An undeclared key like `@comments` may appear in a create response because
`model_dump()` includes extras, but it is not stored and disappears on the next
read.

### 5. Frontend runtime ignores undeclared relation aliases

The frontend only generates dynamic properties from `schema.properties` in
`packages/n3tx-core/src/n3tx_core/static/core/NTT.js`. Form generation and most
component rendering also key off canonical schema property names.

So even though `@comments` can ride along in raw JSON, it is not a first-class
runtime concept today.

### 6. Populated relation normalization currently erases the distinction

`normalizePopulated()` in `NTT.js` converts populated embedded relation objects
back into href arrays on canonical field names.

That is convenient for current runtime behavior, but it directly conflicts with
the desired explicit distinction between `comments` and `@comments`.

### 7. Custom method responses are inconsistent

CRUD responses usually flow through `model_response()` and the dump pipeline.
Custom method responses in direct routing, actor routing, and debug wrappers do
not always do so.

If hypertext aliasing is implemented only in the dump pipeline, custom method
responses will drift unless they are explicitly routed through the same shaping
logic.

---

## Verified Technical Findings

These findings were confirmed during repository inspection and local runtime
probes.

### Pydantic / FastAPI findings

- undeclared `@comments` survives request parsing when `extra='allow'`
- undeclared `@comments` survives FastAPI response validation for the same reason
- aliased fields rewrite schema property names and therefore cannot be the main
  implementation strategy

### Storage findings

- create responses can temporarily echo undeclared `@comments`
- subsequent reads drop undeclared `@comments` because storage never persisted it
- collection relation fields are not stored on the parent row at all

### Frontend findings

- runtime class generation only knows about canonical schema fields
- populated relation normalization currently rewrites embedded objects into hrefs
- components expect canonical state keys such as `comments`, `favorites`, etc.

These findings mean the correct architecture is:

- canonical inside the system
- alias-aware only at schema, transport, and serialization boundaries

---

## Target Feature Contract

## 1. Canonical vs alias roles

For a relational field `comments`:

- `comments` = embedded form
- `@comments` = reference form

The canonical model/schema field remains `comments`.

The alias `@comments` is a transport-level representation alias for the ref form
of the same relation.

## 2. Supported field kinds in wave 1

The feature should apply to:

- `Ref[T]` fields
- `ListRef[T]` fields
- populated relation payloads generated from those fields

It should not apply to arbitrary scalar arrays or plain JSON fields.

## 3. Input acceptance rules

For any supported relational field `field` with alias `@field`:

- accept `field` only
- accept `@field` only
- accept both `field` and `@field`

Normalization target:

- downstream model validation sees canonical field names only

## 4. Output rules in hypertext mode

Recommended behavior:

- if only ref data is available, emit `@field`
- if embedded data is available, emit `field`
- if embedded data is available and stable ref URLs can also be derived, emit both
  `field` and `@field`

This preserves hypertext explicitness while allowing embedded and referenced
navigation paths to coexist.

## 5. Output rules in legacy mode

Legacy mode keeps current behavior so existing clients do not break:

- relations continue to appear under canonical field names
- existing populate behavior remains stable

The new hypertext behavior should therefore be either:

- opt-in via request negotiation, or
- guarded by a config flag during migration

Do not silently switch all existing responses to `@field` without a compatibility
strategy.

---

## Recommended Negotiation Strategy

Because current tests and clients assume canonical field names in responses, the
safest rollout is profile-based.

## Recommended profiles

- `legacy` - current behavior, default
- `hypertext` - emits `@field` aliases according to the new contract

## Acceptable activation mechanisms

At least one of these should exist in the first implementation:

- query param, e.g. `?profile=hypertext`
- request header, e.g. `X-N3TX-Profile: hypertext`

Optional future shape:

- media type/profile negotiation for `application/vnd.n3tx+json`

The first wave does not need to fully standardize the media type, but it must
have a deterministic way to request the hypertext representation.

---

## Wire Semantics Examples

## Example A - non-populated list relation in hypertext mode

```json
{
  "$schema": "http://localhost:5000/Product",
  "$id": "http://localhost:5000/products/1",
  "id": 1,
  "name": "Headphones",
  "@comments": [
    "http://localhost:5000/products/1/comments/1",
    "http://localhost:5000/products/1/comments/2"
  ]
}
```

## Example B - populated list relation in hypertext mode

```json
{
  "$schema": "http://localhost:5000/Product",
  "$id": "http://localhost:5000/products/1",
  "id": 1,
  "name": "Headphones",
  "comments": [
    {
      "$schema": "http://localhost:5000/Comment",
      "$id": "http://localhost:5000/products/1/comments/1",
      "id": 1,
      "name": "First comment"
    }
  ],
  "@comments": [
    "http://localhost:5000/products/1/comments/1"
  ]
}
```

## Example C - accepted write payloads

Reference form:

```json
{
  "@comments": [
    "http://localhost:5000/products/1/comments/1"
  ]
}
```

Embedded form:

```json
{
  "comments": [
    {
      "name": "First comment",
      "description": "Hello"
    }
  ]
}
```

Dual form:

```json
{
  "comments": [
    {
      "$id": "http://localhost:5000/products/1/comments/1",
      "id": 1,
      "name": "First comment"
    }
  ],
  "@comments": [
    "http://localhost:5000/products/1/comments/1"
  ]
}
```

---

## Canonical Normalization Rules

The implementation should use one shared normalization algorithm, not ad hoc
per-route logic.

For each supported relation field `field`:

1. compute alias `@field`
2. if only `@field` is present:
   - move or copy it to canonical `field` for downstream validation
3. if only `field` is present:
   - leave as-is
4. if both are present:
   - prefer canonical `field` as the authoritative application value
   - if both can be normalized to hrefs, validate consistency
   - reject mismatches with a clear `400` or `422` instead of silently diverging
5. after normalization, downstream model code should only need to reason about
   canonical field names

Important backward-compatibility rule:

Current N3TX accepts mixed arrays such as `comments: [{...}, "href"]` because
`ListRef[T]` is `Union[T, str]`. The new hypertext contract should tolerate this
during migration, but it should not emit mixed arrays in hypertext mode.

---

## Schema Contract

The feature must be discoverable in schema without renaming properties.

## Recommendation

Add a new schema section, for example:

```json
{
  "hypertext": {
    "enabled": true,
    "profiles": ["legacy", "hypertext"],
    "fields": {
      "comments": {
        "ref_alias": "@comments",
        "kind": "collection",
        "target": "Comment"
      },
      "user_owner": {
        "ref_alias": "@user_owner",
        "kind": "single",
        "target": "User"
      }
    }
  }
}
```

This keeps:

- `schema.properties.comments` canonical
- alias metadata discoverable
- frontend/runtime behavior inspectable

Do not encode the alias only via `additionalProperties: true`. That is too weak
for a spec-grade runtime contract.

---

## Architectural Invariants

These rules must hold after the feature ships:

1. canonical model and schema names do not change
2. `@field` is a wire alias, not a Python field
3. storage remains canonical
4. direct and actor routing expose the same semantics
5. frontend components continue to work against canonical runtime state
6. output shaping is centralized, not reimplemented in each route handler
7. schema declares alias metadata explicitly
8. populated and non-populated responses obey one deterministic contract

---

## Recommended Architecture

## 1. One backend hypertext utility module

Add a dedicated backend helper module, for example:

- `packages/n3tx-core/src/n3tx_core/hypertext.py`

Responsibilities:

- inspect supported relational fields on a model class
- compute alias metadata (`field` -> `@field`)
- normalize incoming payloads from alias form to canonical form
- serialize canonical response dicts into hypertext wire shape
- provide result-shaping helpers for CRUD and custom method responses
- expose profile parsing helpers (`legacy`, `hypertext`)

This keeps the feature explicit and inspectable instead of spreading alias logic
through unrelated modules.

## 2. Keep storage canonical

Do not store `@field` keys in the DB layer.

The storage layer should continue to deal only with canonical field names and
current join-table logic. Any alias transformation should happen:

- before validation on ingress
- after serialization on egress

## 3. Keep frontend runtime canonical

Do not teach every component to read both `comments` and `@comments`.

Instead:

- normalize hypertext responses into canonical runtime state at a single ingress
  seam
- optionally translate outbound writes into hypertext form at a single egress seam

This preserves the schema-driven component architecture.

## 4. Make schema aware of aliases

The frontend should not need to guess which fields have `@field` aliases.

It should read schema-level metadata declaring which canonical fields have alias
representations.

---

## Backend File-by-File Plan

## 1. New hypertext core helper module

File:

- `packages/n3tx-core/src/n3tx_core/hypertext.py`

Add:

- `get_hypertext_fields(model_class)`
- `get_ref_alias(field_name)`
- `normalize_wire_payload(model_class, data, *, profile='legacy')`
- `serialize_hypertext_dict(model_class, data, *, profile='legacy')`
- `shape_result(result, *, model_class=None, profile='legacy')`
- helpers to derive hrefs from embedded populated values when possible

Notes:

- this module should be the single source of truth for alias rules
- relation-field discovery should use `get_ref_fields()` and `get_list_fields()`
- do not entangle this logic with storage-specific code

## 2. Schema pipeline extension

Files:

- `packages/n3tx-core/src/n3tx_core/models/proto_schema.py`
- `packages/n3tx-core/src/n3tx_core/models/proto_model.py`

Changes:

- add a new schema stage such as `hypertext` before `metadata`
- emit schema metadata describing canonical relation fields and their `@field`
  aliases
- invalidate or update schema cache behavior as needed

Notes:

- this is core schema behavior, not a UI-only extension
- keep canonical `schema.properties` untouched

## 3. Dump pipeline output shaping

Files:

- `packages/n3tx-core/src/n3tx_core/models/proto_dump.py`

Changes:

- add a dump stage after `populate` that can emit hypertext aliases when the
  requested profile is `hypertext`
- preserve current dump behavior in `legacy` mode

Notes:

- shaping must happen after populated overlays are applied
- the stage should not require DB access; it should transform already-serialized
  dicts

## 4. Direct CRUD route normalization and profile parsing

File:

- `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py`

Changes:

- add one helper to parse requested representation profile from query/header
- normalize inbound CRUD payloads before model instantiation
- ensure outbound CRUD responses use the requested profile
- unify custom method responses with the same shaping path

Important implementation detail:

FastAPI currently validates CRUD request bodies via typed parameters such as
`data: param_class`. That means alias-only payloads cannot be normalized after
Pydantic has already rejected them.

Therefore CRUD request handling likely needs one of these refactors:

- accept raw `dict` bodies and instantiate the model after normalization, or
- introduce a dedicated request dependency/body preprocessor before typed parsing

The simplest and most explicit path is usually raw `dict` body -> normalize ->
`param_class(**normalized)`.

## 5. Direct custom method normalization

File:

- `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py`

Changes:

- for custom methods, normalize request payloads against parameter types or
  nested BaseModel argument types before constructing those objects
- after the method returns, shape the result through the same hypertext helper

Notes:

- nested `BaseModel` args may themselves contain relation aliases
- do not limit normalization to top-level CRUD models only

## 6. Debug wrapper parity

File:

- `packages/n3tx-core/src/n3tx_core/utils/decorators.py`

Changes:

- if debug wrappers call `model_dump()` directly, route those outputs through the
  same hypertext result-shaping helper so `DEBUG` mode does not silently bypass
  the feature

## 7. Actor routing parity

Files:

- `packages/n3tx-actors/src/n3tx_actors/api/network_api.py`
- `packages/n3tx-actors/src/n3tx_actors/models/actor_model.py`

Changes:

- mirror the same request normalization and profile parsing in actor-routed HTTP
  endpoints
- ensure actor custom method returns also go through the same shaping path as
  direct routes

Notes:

- direct and actor routing must not diverge on wire shape
- actor-internal method dispatch may also need normalization if TX payloads can
  arrive with alias keys from agent/tool or websocket clients

---

## Frontend File-by-File Plan

## 1. Ingress normalization in runtime bootstrap

File:

- `packages/n3tx-core/src/n3tx_core/static/core/NTT.js`

Changes:

- read schema hypertext metadata when registering a DynamicClass
- add a normalization step that maps `@field` response data into canonical field
  names for internal runtime state
- preserve dual-form data only if the runtime explicitly needs both; otherwise
  canonicalize immediately

Notes:

- this is the most important frontend seam
- components should not need to know whether the server responded with
  `comments` or `@comments`

## 2. Replace or refine populated normalization

File:

- `packages/n3tx-core/src/n3tx_core/static/core/NTT.js`

Changes:

- refactor `normalizePopulated()` so it no longer destroys the distinction the
  hypertext wire format is trying to preserve
- canonical internal state may still collapse to one representation, but the
  conversion must happen knowingly from schema metadata, not as an accidental
  side effect of the current populate logic

Recommended internal policy:

- store canonical relation state under `field`
- if a hypertext response provides only `@field`, map it into canonical `field`
- if a hypertext response provides both `field` and `@field`, keep `field` as
  runtime truth and optionally keep a hidden alias map only if needed for egress

## 3. Outbound request shaping

Files:

- `packages/n3tx-core/src/n3tx_core/static/core/transport/NetworkAdapter.js`
- `packages/n3tx-core/src/n3tx_core/static/core/transport/HTTP.js`

Changes:

- add one outbound shaping step that can convert canonical runtime data to
  hypertext wire payloads when a request is sent in `hypertext` profile mode
- keep legacy mode unchanged

Notes:

- do this once at the transport layer, not in every component's `save()` logic
- this is the frontend equivalent of backend canonicalization

## 4. Component and form verification

Files to inspect and only adjust if canonicalization is not sufficient:

- `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/NTTElement.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-list-field.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js`

Goal:

- confirm that early ingress normalization means these components can remain
  schema-keyed and canonical
- if any component relies on raw transport shape, fix it there, but treat that
  as a bug in normalization layering

---

## Relationship Write Semantics

This feature intersects with a pre-existing limitation in N3TX:

- parent CRUD routes do not generically persist `ListRef` relation membership on
  the parent model

That means an incoming payload like `@comments: [...]` cannot be expected to
fully mutate join state unless the underlying route already supports relation
mutation.

## Recommended first-wave rule

- alias support should match existing write semantics, not expand them

Implications:

- if a route currently accepts canonical relation values meaningfully, it should
  also accept `@field`
- if a route currently ignores parent relation writes, `@field` should not invent
  new persistence semantics behind the user's back

Document this clearly so users do not confuse representation interchangeability
with generic relation mutation.

---

## Safe Implementation Phases

## Phase 0 - Lock the contract and compatibility strategy

### Goal

Resolve the exact response contract before changing code.

### Tasks

- confirm the profile strategy (`legacy` vs `hypertext`)
- confirm output rules for populated relations: ref-only vs dual form
- confirm whether request bodies may contain both `field` and `@field`
- confirm mismatch behavior when both are present

### Output

- a written contract section in docs/tests and the new helper module

### Acceptance criteria

- implementation agent can describe exactly what a non-populated and populated
  response look like in both profiles

---

## Phase 1 - Core hypertext field inspection and schema metadata

### Goal

Teach the backend and frontend which fields have `@field` aliases.

### Files

- add `packages/n3tx-core/src/n3tx_core/hypertext.py`
- modify `packages/n3tx-core/src/n3tx_core/models/proto_schema.py`
- update tests for schema output

### Tasks

- discover relational fields from introspection helpers
- generate alias metadata without changing canonical property names
- add tests covering `Ref[T]` and `ListRef[T]`

### Acceptance criteria

- schema exposes alias metadata for relational fields
- `schema.properties` remains canonical

---

## Phase 2 - Direct-route input normalization

### Goal

Allow FastAPI direct CRUD and custom methods to accept `@field` payloads.

### Files

- `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py`
- `packages/n3tx-core/src/n3tx_core/hypertext.py`

### Tasks

- refactor CRUD typed-body parsing to raw-body normalization -> model instantiation
- normalize nested BaseModel custom-method parameters
- add clear mismatch errors for conflicting `field` and `@field`

### Acceptance criteria

- direct CRUD routes accept canonical, alias, and dual-form inputs
- custom method params containing relation models accept alias payloads too

---

## Phase 3 - Output shaping and dump unification

### Goal

Emit deterministic hypertext responses in one place.

### Files

- `packages/n3tx-core/src/n3tx_core/models/proto_dump.py`
- `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py`
- `packages/n3tx-core/src/n3tx_core/utils/decorators.py`

### Tasks

- add profile-aware alias shaping after populate
- route CRUD outputs through that shaping
- route custom method and debug-wrapper outputs through that shaping

### Acceptance criteria

- no route family bypasses the feature silently
- legacy profile remains unchanged
- hypertext profile obeys the agreed relation-key contract

---

## Phase 4 - Frontend ingress and egress normalization

### Goal

Keep UI/components canonical while supporting hypertext wire shapes.

### Files

- `packages/n3tx-core/src/n3tx_core/static/core/NTT.js`
- `packages/n3tx-core/src/n3tx_core/static/core/transport/NetworkAdapter.js`
- `packages/n3tx-core/src/n3tx_core/static/core/transport/HTTP.js`

### Tasks

- canonicalize `@field` responses on ingress
- refine populated normalization to align with the new contract
- add outbound payload shaping in hypertext mode

### Acceptance criteria

- components continue to read canonical field names only
- transport can send canonical or hypertext payloads based on requested profile

---

## Phase 5 - Component verification and targeted fixes

### Goal

Confirm the UI still works under normalized hypertext responses.

### Files

- `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/NTTElement.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-list-field.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js`

### Tasks

- verify rendering, counts, nested lists, save flows, and ref-pickers still work
- fix any place that depends on raw transport shape instead of canonical runtime
  state

### Acceptance criteria

- UI behavior is unchanged in legacy mode
- UI works equally in hypertext mode after runtime normalization

---

## Phase 6 - Actor-routing parity

### Goal

Make Level 3 actor routing semantically identical to direct routing.

### Files

- `packages/n3tx-actors/src/n3tx_actors/api/network_api.py`
- `packages/n3tx-actors/src/n3tx_actors/models/actor_model.py`

### Tasks

- apply the same profile parsing and normalization rules
- ensure actor custom method outputs route through the shared shaper

### Acceptance criteria

- direct and actor mode return the same payload shape for the same request

---

## Phase 7 - Documentation and examples

### Goal

Document the contract so it becomes a real framework behavior instead of an
accidental implementation detail.

### Files

- `docs/ARCHITECTURE.md`
- `docs/CORE.md`
- `BACKEND.md`
- `FRONTEND.md`
- `docs/frontend/ARCHITECTURE.md`
- `packages/n3tx-core/docs/schema-pipeline.md`
- `packages/n3tx-ui/docs/formidable.md`

### Tasks

- document canonical-vs-alias semantics
- document the schema `hypertext` metadata section
- document negotiation/profile rules
- document normalization policy for frontend runtime

### Acceptance criteria

- a new contributor can understand the feature from docs alone

---

## Testing Plan

## Backend unit tests

Add:

- `packages/n3tx-core/src/n3tx_core/tests/unit/test_hypertext.py`
- `packages/n3tx-core/src/n3tx_core/tests/unit/test_proto_dump_hypertext.py`
- `packages/n3tx-core/src/n3tx_core/tests/unit/test_routes_hypertext.py`

Cover:

- relation field discovery
- alias metadata emission in schema
- request normalization rules
- `field` only / `@field` only / both present cases
- mismatch detection when both forms disagree
- legacy profile output stability
- hypertext profile output shaping for populated and non-populated relations
- custom method result shaping parity

## Actor tests

Add:

- `packages/n3tx-actors/src/n3tx_actors/tests/test_network_api_hypertext.py`
- `packages/n3tx-actors/src/n3tx_actors/tests/test_actor_model_hypertext.py`

Cover:

- actor route input normalization
- actor output parity with direct routes
- custom actor method result shaping

## Frontend unit tests

Add or extend:

- `tests/frontend/tests/core/ntt-hypertext.test.js`
- `tests/frontend/tests/transport/network-adapter-hypertext.test.js`
- `tests/frontend/tests/generators/form.test.js`
- `tests/frontend/tests/components/ntx-item.test.js`
- `tests/frontend/tests/components/ntx-method.test.js`

Cover:

- schema hypertext metadata ingestion
- ingress normalization from `@field` to canonical runtime state
- populated response handling
- outbound transport shaping
- badge/count rendering still using canonical runtime state
- create/edit flows in legacy and hypertext mode

## Example and integration tests

Add or extend:

- `/workspace/examples/core/tests/test_cross_model_workflows.py`
- `/workspace/tests/frontend/tests/e2e/flow-product-crud.spec.js`

Cover:

- legacy profile unchanged
- hypertext profile emits `@comments`
- populated hypertext profile emits `comments` plus `@comments`
- frontend can render both profiles without special-case component code

---

## Risks And Watchouts

## 1. Schema alias drift

Risk:

- implementing with direct Pydantic aliases renames `schema.properties`

Mitigation:

- keep aliases in explicit hypertext metadata, not in field aliases

## 2. FastAPI request parsing order

Risk:

- typed body parsing rejects alias-only payloads before route logic runs

Mitigation:

- normalize raw request dicts before constructing Pydantic models

## 3. Custom method inconsistency

Risk:

- CRUD responses gain hypertext behavior but custom methods do not

Mitigation:

- add one shared result-shaping helper and use it everywhere

## 4. Populated response ambiguity

Risk:

- unclear rules for when to emit `field`, `@field`, or both create client drift

Mitigation:

- lock explicit populated and non-populated examples into tests before rollout

## 5. Frontend canonicalization regressions

Risk:

- runtime normalization breaks counts, nested rendering, or writeback behavior

Mitigation:

- normalize once at ingress, keep component state canonical, and add focused
  frontend tests around relation-heavy surfaces

## 6. Relation mutation confusion

Risk:

- users assume `@comments` makes parent CRUD mutate join membership generically

Mitigation:

- document that wire alias support follows existing write semantics and does not
  redesign relation mutation

## 7. Direct vs actor divergence

Risk:

- Level 1/2 and Level 3 produce different shapes for the same request

Mitigation:

- centralize normalization and shaping in shared helpers, then add parity tests

---

## Suggested Commit Slices

1. add core hypertext helper module and schema metadata
2. refactor direct-route request parsing to support alias normalization
3. add dump-stage/profile-aware output shaping and custom method parity
4. normalize frontend ingress and outbound transport shaping
5. fix any component/runtime regressions exposed by canonicalization
6. add actor-routing parity
7. update tests and documentation

---

## Verification Commands

Run at least:

```bash
cd /workspace && python3 -m pytest packages/n3tx-core/src/n3tx_core/tests/unit/
cd /workspace && python3 -m pytest packages/n3tx-actors/src/n3tx_actors/tests/
cd /workspace && python3 -m pytest examples/core/tests/
cd /workspace/tests/frontend && npx vitest run
cd /workspace/tests/frontend && npx playwright test --config=tests/e2e/playwright.config.js
```

If the hypertext feature is profile-gated, tests must exercise both `legacy` and
`hypertext` modes explicitly.

---

## Recommendation

Implement this as a boundary feature, not as a new field model.

That means:

- canonical names inside the system
- explicit alias metadata in schema
- input normalization at the API boundary
- output shaping at the dump/transport boundary
- canonical frontend runtime state

This approach matches N3TX's actual architecture:

- the model stays the source of truth
- schema stays canonical
- transport gains hypertext expressiveness
- components stay simple

It also avoids the two biggest traps:

- renaming schema properties via Pydantic aliases
- letting undeclared `@field` extras float around as untyped accidental data

---

## Done Definition

This plan is fully implemented when all of the following are true:

1. canonical relational fields remain unchanged in Python models and
   `schema.properties`
2. schema exposes explicit metadata mapping canonical relation fields to `@field`
   aliases
3. direct CRUD and custom methods accept canonical, alias, and dual-form inputs
   where semantically applicable
4. legacy output mode remains backward compatible
5. hypertext output mode emits deterministic `field` / `@field` representations
6. CRUD and custom method outputs use the same shaping rules
7. direct and actor routing behave identically
8. frontend runtime canonicalizes hypertext responses into canonical schema-keyed
   state
9. UI components work without having to learn raw alias keys directly
10. docs and tests describe the feature as a first-class framework contract
