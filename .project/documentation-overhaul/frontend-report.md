# T02B frontend documentation report

Scope: frontend documentation only. Baseline `a189f755153558cdaf472764f9abc78a50929eaa`.
The assessment covers all 18 documents below. Earlier context requested full-file
reads, but some tool output was truncated; this report does not claim exhaustive
line-by-line inspection of every original document. Guidance consulted includes
AGENTS, README, FRONTEND, BACKEND, AUDIT and REWRITE-PLAN. Historical proposals
are preserved, not silently rewritten into claims about current behavior.

## Per-path assessment before edits

Paths are relative to the repository root. V = value; P = presentation;
C = correctness; G = completeness gap. Each row records an independent assessment.

| Path | V | P | C | G | Disposition |
|---|---|---|---|---|---|
| `FRONTEND.md` | Contributor entry and source map | 593 lines mix reference, release notes and commands | Absolute checkout paths, obsolete runtime naming, contradictory agent hierarchy | Missing concise reading order | Rewrite as orientation linking canonical guides |
| `docs/frontend/ARCHITECTURE.md` | End-to-end learning path | Long repeated traces and status lists | N3TX.js, automatic initial READ, nested HTTP identity and no-tests claims stale | Native bootstrap and safe extension choices | Rewrite as frontend entry guide |
| `docs/frontend/COMPONENTS.md` | Component/routing usage | Duplicate NTTList sections and copied implementation | Contradictory list ownership, stream implementation and router defaults | Current routing grammar and explicit imports | Rewrite as usage/navigation reference; lifecycle in package guide |
| `docs/frontend/ACTORS.md` | Runtime mechanism reference | Useful tables buried in copied internals | Runtime export, collection URL, readiness and generated method examples stale | Async lifecycle limitations | Rewrite against Actor/NTT source |
| `docs/frontend/MESSAGE_PROTOCOL.md` | Trace/debug reference | Repeats full architecture | Wrong TX target, initial READ, nested relationship URLs | Current error/stream boundaries | Rewrite compact direction/payload tables |
| `docs/frontend/TRANSPORT.md` | Transport API detail | Useful API tables | Nested URLs stale; cancellation and fallback claims too broad | Method-name/path limitation | Rewrite actual transport behavior |
| `docs/frontend/PACKAGE_ARCHITECTURE.md` | Packaging decision history | Proposal presented near live guides | Hypothetical @ntt packages are not shipped imports | Current package map | Preserve body; label historical and link current guide |
| `docs/frontend/01_UI_SEPARATION_CONCERNS.md` | Refactor rationale | Historical before/after not marked globally | Old paths, unsafe templates, obsolete hierarchy | Current lifecycle pointer | Preserve body; historical notice |
| `docs/frontend/02_UI_PRIMITIVES_ENHANCEMENT.md` | Enhancement implementation history | DONE and future claims coexist | Old commands, blanket validation/completion claims | Current contract distinction | Preserve body; historical notice |
| `docs/frontend/03_SYSTEM_IMPROVEMENTS_REFACTOR.md` | Design critique including escaping | Recommendations resemble shipped APIs | Proposed discovery, hooks, TypedDict not implementation evidence | Explicit proposal status | Preserve body; historical notice |
| `packages/n3tx-ui/README.md` | Package orientation | Hype and duplicated manuals | UI-only mounting, missing imports, single Python export claim wrong | Native bootstrap prerequisites | Rewrite concise package map |
| `packages/n3tx-ui/docs/components.md` | Lifecycle and customization | Dense release-note prose | Unsafe renderer snippet, incorrect agent tree, overbroad cancellation | Working safe custom renderer and update hook | Rewrite retaining extension/reference detail |
| `packages/n3tx-ui/docs/formidable.md` | Form API and layout | Useful pipeline and signatures | Immediate join/unjoin claim stale; array validation omitted | Complete schema-based reading/save example; HTML safety boundary | Rewrite mechanism and limits |
| `packages/n3tx-ui/docs/widgets.md` | Widget API and built-ins | Good tables, misleading color example | Explicit-hint-only claim false; listeners lost to serialization | Working serialization-safe extension | Rewrite selection/serialization and example |
| `packages/n3tx-ui/docs/styling.md` | Theme ownership | Migration log rather than guide | Fixed workspace test paths, environment assumptions | Custom theme recipe and shadow CSS | Rewrite retaining canonical token contract |
| `packages/n3tx-ui/docs/viewable-mixin.md` | Python UI capability | Repeated snippets/schema | Late-import/schema-cache advice conflates stage and mixin; attach_to described as data mutation | Shell limits and complete imports | Rewrite capability and route resolution |
| `tests/frontend/README.md` | Some runtime explanations reusable | Misplaced 967-line app manual | N3TXTX, missing imports, stale config and routes | Almost no harness guidance | Replace with harness guide; runtime retained in frontend references |
| `tests/frontend/QUICKSTART.md` | Entry link worth keeping | Competing application tutorial | Old runtime/config/full-list promises | Test quick commands | Replace with test quickstart and tutorial links |

## Source evidence inspected

| Concern | Evidence |
|---|---|
| Native static namespace | `packages/n3tx-core/src/n3tx_core/api/backend.py`: `_discover_static_dirs`, `_mount_static`, `_CascadingStaticFiles` |
| Runtime bootstrap and identity | `packages/n3tx-core/src/n3tx_core/static/core/NTT.js`: `SCHEMA`, `modelHref`, DynamicClass `call`, `READ`, `ATTACH`, `_response_`; `tests/frontend/tests/integration/schema-bootstrap.test.js` |
| Lifecycle | `packages/n3tx-core/src/n3tx_core/static/core/Component.js`; UI `NTTElement.js`, `ListElement.js`, `ntx-item.js` |
| Transport/stream limits | Core `static/core/transport/NetworkAdapter.js`, `HTTP.js`; UI `static/components/ntx-stream.js` |
| Forms and widgets | UI `static/generators/form.js`, `static/widgets/registry.js`, `Widget.js`; `tests/frontend/tests/widgets/BoolWidget.test.js` |
| View capability | UI `src/n3tx_ui/mixin.py` and `__init__.py` |
| Theme | Core `static/utils/theme.js`; UI theme entrypoints |
| Harness | `tests/frontend/package.json`, `vitest.config.js`, E2E `paths.js`, Playwright configs and fixtures |

## Final outcome

✅ All 18 owned documents received the disposition recorded above: 14 rewritten
guides/references and four historical notices. Paths remain stable. The two test
documents now describe the harness rather than competing with the app tutorial.
The native bootstrap, runtime schema lifecycle, explicit imports, renderer/form/
widget/theme extension paths and backend-versus-presentation boundaries are covered.

### Method Signature Surface

No callable/interface signatures changed. Code blocks illustrate existing APIs;
they do not introduce runtime implementations into the repository.

## Verification

| Check | Actual result |
|---|---|
| `git diff --check` from the N3TX root | Passed; no whitespace errors |
| Read-only Python Markdown scan across the 18 owned docs | 135 relative inline link targets and their heading fragments resolved |
| Python `ast.parse` and Node `--input-type=module --check` on code blocks, including inline HTML scripts | 19 syntax checks passed; the styles getter was wrapped in a class for parsing |
| Historical preservation comparison with `git show HEAD:<path>` | All four original bodies match after removing the new title-adjacent notices |
| `npm test -- --no-cache --maxWorkers=2 --minWorkers=1` from `tests/frontend/` | Blocked before any tests ran: `sh: 1: vitest: not found` (reproduced on final verification) |
| Targeted source review | Confirmed extension exports, entity schema accessor, item permission checks, widget serialization, test scripts/configs and readiness helper names |

The initial syntax scan correctly rejected a class-member excerpt at module
scope and a signature-only reference block as executable Python. The getter
passed when checked in class context; the signature block is now fenced as text.
Link checking excludes preserved historical bodies (only their new navigation
notices are checked), remote URLs, and non-link prose paths. Heading checking is
a lightweight Markdown slug approximation, not a rendered-site build.

### Gaps and handoff

- Syntax and source inspection are **not execution** of the tutorial or custom
  components. Browser rendering, real form saves, widget round trips, computed
  theme CSS, mobile layout and accessibility remain unverified in this attempt.
- No Vitest suite ran; no Playwright suite or browser was launched. No dependencies
  were installed, no shared Python environment was changed, and no live requests
  or paid-provider calls were made.
- Existing implementation risks are documented, not fixed: Formidable is not a
  sanitizer; reference removal can delete a child; stream cancellation does not
  guarantee backend termination; generic method transport has route-name limits.
- Core/package writers have concurrent changes outside this ownership scope.
  Those changes were left untouched. Cross-writer links resolved at check time;
  repeat the link check after the whole documentation pass is integrated.
- The earlier full-read claim has been narrowed because truncated tool output
  cannot substantiate exhaustive original-document review.

📍 Deliverable: this report plus the 18 listed documentation files. No runtime,
test implementation, changelog history, shared inventory or ledger edits were
made in this pass; no commit was created.
