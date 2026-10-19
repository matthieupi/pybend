# T02A core documentation rewrite

Baseline: `a189f755153558cdaf472764f9abc78a50929eaa`. Scope is documentation only.
Global T01 remains incomplete; this report assesses the bounded owned surface.
The assessment covers 21 existing owned Markdown files, including the long
overlapping API manuals. No changelog is in this surface. Context loading was
recorded in the preceding work; this report does not certify that every earlier
tool output was untruncated.

## Per-path assessment

Paths are repository-relative. “Rewrite” retains the path; “consolidate” retains
a navigation/reference page rather than deleting the entry point.

| Path | Value | Presentation before rewrite | Correctness before rewrite | Disposition |
|---|---|---|---|---|
| README.md | Entry point, package map | Promotional, duplicates manuals | Old run/test paths; Ref and routing conflation | Rewrite orientation; canonical tutorial link |
| docs/README.md | Documentation landing page | Second long README | Placeholder install, unsafe login, stale roadmap | Rewrite as documentation index |
| docs/GETTING_STARTED.md | Complete learning path | Long disconnected snippets | Obsolete imports, integer Ref, unauthenticated requests, unsafe login | Replace with executable issue app |
| docs/ARCHITECTURE.md | Boundaries and extension map | Repeated diagrams and speculative code | All HTTP claimed actor-based, incorrect Ref/pipeline and transaction claims | Rewrite native flow and extension boundaries |
| docs/CORE.md | Concept overview | Duplicates models and architecture | Old source tree/run commands, overly broad enforcement | Consolidate concept map with links |
| docs/MODELS.md | Model lifecycle and relationship reference | Useful tables; duplicated pipelines | Unqualified scalar rewrite; missing debug registration warning | Rewrite; retain lifecycle, schema/dump, BaseUser and Ref detail |
| docs/API_INDEX.md | API navigation | 459-line duplicated manual | Stale example paths, statuses and relationship shapes | Consolidate to API map |
| docs/API_OVERVIEW.md | Wire conventions | Repeats CRUD and schema examples | Uniform error/response and transport parity claims; integer refs | Rewrite wire conventions, auth and errors |
| docs/API_REFERENCE.md | Python symbol lookup | 1136-line competing reference | Old imports/signatures, ViewableMixin ownership, Ref, agents | Consolidate symbol map; retain storage/decorator/utilities navigation |
| docs/API_DATA_MODELS.md | Example schema orientation | Handwritten types, clients and React forms | Invented age/constraints, nested identity, integer refs, login shape | Consolidate to live schema discovery and example source map |
| docs/API_CRUD_ENDPOINTS.md | CRUD contract | Excessive repeated request/response examples | Nested routes no longer generated; overbroad error guarantees | Rewrite; retain stable CRUD headings, pagination and patch contract |
| docs/API_CUSTOM_ENDPOINTS.md | Actions, caller injection, streaming | 1103-line duplicated examples | Password ignored in login example; GET bodies; default argument and response promises | Rewrite exact direct routing contract and native auth links |
| docs/AUTHORIZATION.md | Enforcement model | Duplicated package API | Missing-token middleware claim; unsafe sql_filter=None advice | Rewrite entrypoint matrix and security boundaries |
| docs/JSON_FIELDS.md | Useful JSON storage reference | Repeated examples and implementation prose | Mostly accurate; create(dict), absolute workspace paths, broad child auth implication | Rewrite compactly, preserve lossiness/migration/normalization caveats |
| docs/EXAMPLES.md | Application patterns | 738 lines of untested sketches | Unsafe bespoke auth, missing imports, integer Ref; production-ready claim | Replace with checked-in example catalog and native pattern links |
| packages/n3tx-core/README.md | Package orientation | Hype, competing tutorial | Wrong ViewableMixin export/Ref description; incomplete ownership example | Rewrite concise package guide |
| packages/n3tx-core/docs/app-bootstrap.md | Detailed bootstrap reference | Generally structured | CORS forwarding assumed; DEBUG=false reset implied; level conflation | Rewrite, preserve static precedence, hooks, SSR and assistant lifecycle |
| packages/n3tx-core/docs/storage.md | Storage mechanisms and limits | Useful compact reference | busy_timeout prevents locks claim; unconditional scalar T and method atomicity implication | Rewrite; preserve normalization, populate, update and migration details |
| packages/n3tx-core/docs/authorization.md | Rule/context/resolver API | Useful tables | SQL None risk understated; no per-entrypoint boundary | Rewrite API details; link enforcement matrix |
| packages/n3tx-core/docs/schema-pipeline.md | Extension protocol | Good structure, repeated warnings | Agent stage order and integer Ref schema wrong | Rewrite exact stages/cache/extension registries |
| packages/n3tx/README.md | Meta-package installation/import map | Duplicates entire root README with hype | Old paths, exports, routing/ref semantics | Rewrite dependency/import guide |

The table contains **21 existing paths**. New owned
guide: `docs/OPERATIONS.md`. Historical changelogs and generated snapshots are
preserved unchanged and classified in the new index, not promoted as HEAD APIs.

## Source evidence and resolved contracts

| Evidence | Finding |
|---|---|
| `models/proto_model.py:93-122` (core source root) | Bare BaseModel annotations are rewritten only during first StorableMixin injection; list/Optional annotations do not satisfy the bare-type test. Runtime probe confirms fresh `child: Child` becomes Ref while inherited `other: Child` stays local. |
| `models/ref.py:36-85,159-237` | Ref validates HTTP(S), target class and final identity segments; schema is URI string plus x-ref; hydration requires explicit resolver. Historical Ref['self'] is an annotated integer exception. |
| `models/storable_mixin.py:92-99,123-236` | create expects model instance; update validates merged state and writes supplied keys; no transaction across read/validate/write. |
| `api/routes_fastapi.py:82-233,296-421,437-521` | CRUD mirrors, public schema, SQL-only list filter, protected update fields, reserved user injection; direct custom args ignore defaults and reject null. |
| `authorize/resolver.py:40-61`, `authorize/rules.py:148-198` | list does not call authorize; AUTHENTICATED SQL is 1=1; OWNER SQL denies anonymous with 1=0. None filters are not fail-closed. |
| `api/backend.py:97-118,147-211` | Wildcard CORS default; missing token installs empty identity, invalid token returns 401; forwarded identity trusted only after service-token check. Docs UI is DEBUG-dependent. |
| `app.py:198-207,250-296,394-469` | cors_origins is stored but not forwarded; debug=False does not reset an already true global DEBUG; factory always constructs FastAPI. |
| `models/base_user.py:65-151` | Built-in password hashing/login; registration grants admin under DEBUG; role claims copied into JWT. |
| `n3tx_ui/mixin.py:102-126,162-220,230-253` | Native collection/member HTML shells import runtime/component modules and use normal schema/data flow. |

Core source root: `packages/n3tx-core/src/n3tx_core/`.

## Verification status

Initial environment provisioning: `python3 -m venv /workspace/.venv-agents`
failed because system ensurepip is absent, leaving an isolated venv. System curl
and pip are also absent. Bootstrapped pip inside that venv from the official PyPA
HTTPS bootstrap using urllib; installed only core dependencies plus httpx,
pytest and pytest-asyncio. No Collagen environment or global install used.

Initial annotation probe passed on Python 3.11 / Pydantic 2.14.1. No paid provider
or remote reference execution is permitted in these checks.

### Current verification checkpoint

Executed from the N3TX checkout:

```text
/workspace/.venv-agents/bin/python .project/documentation-overhaul/verify_tutorial.py
Result: PASS; 38 HTTP checks
```

Additional assertions passed: live schema contract, forged body caller ignored,
SQLite persisted values, relationship replacement retaining the child row, and
HTML shell/static asset delivery. Denial and invalid-input cases are included.
The run emitted the expected wildcard-CORS warning and a Starlette/httpx
deprecation warning. Neither was suppressed or treated as production approval.

Scoped `git diff --check` passed for the tracked owned documentation paths.
The new Operations page has been added; EXAMPLES is now a native-pattern catalog.
Authorization and schema-pipeline references received focused corrections while
preserving their detailed interface material.

Remaining verification: comprehensive local links/anchors, focused core test
suites, and final source/signature reconciliation. Browser rendering, process
restart, concurrent writes, actor transport and remote refs were not verified by
the tutorial run. This checkpoint is not a final completion certification.

Runtime issues documented, not fixed: scalar Ref schema rewriting differs from
its URI input contract; direct list authorization uses SQL only; factory CORS is
not forwarded; raw ValueError validation context can fail direct PUT error JSON
serialization; nested identity metadata differs between create/update and GET.
The tutorial uses JSON-safe PydanticCustomError for its cross-field validator.
