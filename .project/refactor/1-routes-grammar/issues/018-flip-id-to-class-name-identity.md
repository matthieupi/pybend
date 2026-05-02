# 018 — `$id` Identity Compatibility and Migration Notes

## ✅ Recommendation

Treat issue `018` as a **documentation, release-policy, and compatibility review**.

Do **not** implement new response metadata. Issue `010` already made the core identity decision:

```text
$schema -> /ClassName
$id     -> /ClassName/id or /ParentClass/parent_id/ChildClass/child_id
```

Issue `018` should close the loop by making the public migration explicit:

1. verify the implemented identity contract is accurately documented,
2. remove stale table-name `$id` examples from public API docs,
3. add release/migration guidance for clients that stored old `$id` values,
4. explicitly reject a compatibility flag unless a concrete consumer needs it,
5. mark issue `018` as superseded/closed with a clear decision record.

Recommended decision:

```text
No compatibility flag for response identity in this cycle.
Legacy table-name routes remain resolvable transport URLs.
Response identity is class-name based everywhere.
No $href and no links metadata are emitted.
```

---

## Context

Issue `018` was originally a later `$id` flip checkpoint, but that work was superseded by issue `010`.

The issue YAML states:

```text
This issue is superseded by issue 010.
Use it to decide whether external migration notes,
compatibility flags, or deprecation timelines are needed.
```

The current code and docs already show the intended implementation in several places:

- `proto_dump.instance_url()` emits class-name `$id` for regular and join models.
- `docs/CORE.md` documents canonical class-name `$id` and nested identity.
- `BACKEND.md` documents class-name response identity and legacy route compatibility.
- `FRONTEND.md` documents frontend href preservation from `$id`.

But some generated/reference docs still include table-name `$id` examples, especially:

- `docs/API_OVERVIEW.md`
- `docs/API_CRUD_ENDPOINTS.md`
- `docs/API_DATA_MODELS.md`

Issue `018` should clean that up and add migration guidance, not change runtime behavior.

---

## Target Compatibility Contract

```text
Canonical response identity:
  Regular entity: /Product/1
  Nested entity:  /Product/1/Comment/2

Compatibility transport:
  Legacy table-name routes remain available:
    /products/1
    /products/1/comments/2

Rejected for now:
  $href
  links.canonical
  links.legacy
  response identity compatibility flag
```

### Why no compatibility flag by default?

| Option | Result | Decision |
|---|---|---|
| Emit only class-name `$id` | Single source of truth, simplest frontend/runtime model | ✅ preferred |
| Add `$href` or `links` | Parallel identity concepts across backend/frontend/docs | ❌ rejected by issue 010 |
| Add response identity mode flag | Doubles response-shape test matrix and docs burden | ❌ reject unless a real external client requires it |
| Keep legacy table routes | Lets old stored URLs continue resolving as transport paths | ✅ required |

---

## Implementation Plan

## Phase 1 — Documentation Audit and Stale Example Sweep

Goal: find every public doc example that still implies table-name `$id` identity.

Use targeted searches:

```text
"$id": "http://localhost:8000/users/1"
"$id": "http://localhost:8000/comments/1"
"$id": "http://localhost:8000/products/1"
"user.$id === \"http://localhost:8000/users/1\""
"table-name $id"
"$id remains table-name"
```

Primary docs to update:

```text
docs/API_OVERVIEW.md
docs/API_CRUD_ENDPOINTS.md
docs/API_DATA_MODELS.md
docs/API_REFERENCE.md
docs/README.md
```

Expected replacements:

```json
// old
{
  "$schema": "http://localhost:8000/User",
  "$id": "http://localhost:8000/users/1"
}

// new
{
  "$schema": "http://localhost:8000/User",
  "$id": "http://localhost:8000/User/1"
}
```

Nested examples:

```json
// old
{
  "$schema": "http://localhost:8000/Comment",
  "$id": "http://localhost:8000/comments/1"
}

// new
{
  "$schema": "http://localhost:8000/Comment",
  "$id": "http://localhost:8000/Product/1/Comment/1"
}
```

Important: do not blindly replace every table-name URL. Table-name routes remain valid in request examples. Only response identity examples should move to class-name `$id`.

---

## Phase 2 — Add a Migration Note

Goal: give external API consumers a concise explanation of the public `$id` change.

Recommended new section in `docs/API_OVERVIEW.md` and/or `docs/API_CRUD_ENDPOINTS.md`:

```markdown
### `$id` Migration Note

N3TX response identity is now class-name based. A response fetched through either
`/users/1` or `/User/1` advertises:

```json
{
  "$schema": "http://localhost:8000/User",
  "$id": "http://localhost:8000/User/1"
}
```

Legacy table-name routes such as `/users/1` remain supported as compatibility
transport paths, but new clients should treat `$id` as the canonical entity URL.
N3TX does not emit `$href` or `links`; `$id` is the single response identity.
```

Recommended additions:

- explain regular identity: `/ClassName/id`
- explain nested identity: `/ParentClass/parent_id/ChildClass/child_id`
- explain legacy route compatibility: old URLs still route
- explain no compatibility flag: no alternate response-shape mode in this cycle

---

## Phase 3 — Update the Change Log / Release Notes

Goal: make the public behavior change visible outside the refactor folder.

File:

```text
CHANGELOG.md
```

Recommended entry near the top under a new unreleased or current route-grammar section:

```markdown
## Unreleased

### Backend / API

- Response `$id` identity is now class-name based: `/Product/1` instead of
  `/products/1`, and nested entities use `/Product/1/Comment/2`.
- Legacy table-name routes remain available as compatibility transport paths.
- N3TX does not emit `$href` or `links`; `$id` is the canonical response identity.
- Class-name JSON mirrors are available for collection, create, read, update,
  delete, and literal custom methods while `GET /ClassName` remains schema.
```

If the project avoids an `Unreleased` section, add the note to the active route-grammar wave documentation instead and link to it from `CHANGELOG.md` later.

---

## Phase 4 — Mark Issue 018 as Closed / Superseded

Goal: prevent future implementers from treating issue `018` as runtime work.

Update:

```text
.project/refactor/1-routes-grammar/issues/018-flip-id-to-class-name-identity.yaml
.project/refactor/1-routes-grammar/issues/index.yaml
```

Recommended YAML status:

```yaml
status: closed
resolution: superseded_by_010
decision: |
  No runtime work remains in issue 018. Issue 010 flipped response `$id`
  directly to class-name identity. Legacy table-name routes remain available;
  no `$href`, `links`, or response identity compatibility flag is introduced.
```

Also update the issue index entry:

```yaml
- id: 18
  status: closed
  resolution: superseded_by_010
```

---

## Phase 5 — Optional Validation Tests, Only If Docs Reveal a Gap

Issue `018` is documentation/release-policy only. Do not add tests unless the doc audit reveals an uncovered compatibility invariant.

If adding a small safety test is useful, prefer existing suites:

```text
packages/n3tx-core/src/n3tx_core/tests/unit/test_proto_dump_stages.py
packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py
tests/frontend/tests/core/NTT.test.js
```

Useful assertions, if not already present:

```python
assert response['$id'].endswith('/Product/1')
assert '$href' not in response
assert 'links' not in response
```

But avoid expanding scope: issue `010` and `011` should already own this runtime coverage.

---

## Compatibility Policy

### Supported

- Clients may continue requesting old table-name API paths.
- Clients may continue dereferencing old stored table-name URLs while legacy routes exist.
- New responses always advertise class-name `$id`.

### Not supported in this issue

- A response mode that emits old table-name `$id`.
- Parallel `$href` or `links` metadata.
- Automatic rewrite service for external stored URLs.
- Removing legacy table-name routes.

### Future issue trigger

Open a new HITL issue only if a concrete external client needs one of:

1. a deprecation timeline for table-name routes,
2. an explicit URL rewrite endpoint,
3. a temporary response identity compatibility mode,
4. link metadata for third-party hypermedia clients.

---

## Verification

Documentation-only verification:

```bash
cd /workspace && git diff -- docs/ CHANGELOG.md .project/refactor/1-routes-grammar/issues/018-flip-id-to-class-name-identity.yaml
```

Search verification:

```text
No public response examples should show:
  "$id": ".../users/1"
  "$id": ".../products/1"
  "$id": ".../comments/1"

Unless the surrounding text explicitly labels them as legacy transport URLs,
not response identity.
```

Optional runtime spot checks if any code changes are accidentally made:

```bash
cd /workspace && python3 -m pytest packages/n3tx-core/src/n3tx_core/tests/unit/test_proto_dump_stages.py -q
cd /workspace/tests/frontend && npx vitest run tests/core/NTT.test.js
```

---

## Acceptance Checklist

```text
[ ] Docs state response `$id` is class-name based.
[ ] Docs state legacy table-name routes remain compatibility transport paths.
[ ] Docs state no `$href` or `links` are emitted.
[ ] API examples no longer show table-name `$id` as current response identity.
[ ] Migration/release note calls out the public `$id` change.
[ ] Compatibility flag is explicitly rejected or split into a future issue.
[ ] Issue 018 is marked closed/superseded by issue 010.
```

---

## Suggested Commit Slice

```text
docs(api): Close class-name identity migration notes [routes-grammar]
```

Scope:

- API doc `$id` example cleanup
- migration/release note
- issue `018` status update
- no runtime code changes

---

## Critical Files for Implementation

- `docs/API_OVERVIEW.md`
- `docs/API_CRUD_ENDPOINTS.md`
- `docs/API_DATA_MODELS.md`
- `CHANGELOG.md`
- `.project/refactor/1-routes-grammar/issues/018-flip-id-to-class-name-identity.yaml`
