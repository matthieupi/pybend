# Documentation Rewrite Disposition

## R02 Active Status

The completion claim below is superseded. **59 owned current guides still need
full current-revision review**, enumerated in `REMAINING.txt`. Ten guides have
direct, untruncated current-read evidence in `CURRENT-REVIEWS.json`; hashes and
exact ranges are checked during inventory regeneration. Do not turn prior batch
captures or the 45 closing-read claims into certified reads.

Keep the 53 writer reports attributed, the 55 historical/generated-reference
classifications bounded, the seven non-guide records separate, and all 24
`.egg-info` paths `classified-generated-metadata`. No metadata regeneration,
runtime edits, ledger changes or `.project/` content assessment is authorized.

The streaming skill correction is applied. Remaining work is the actual guide
review, any resulting owned-document corrections, and regeneration of inventory
and closing checks. Current link scanning finds no broken anchors; the earlier
two writer-owned link findings below are no longer active. Runtime and browser
verification gaps remain separate from document reading.

## Superseded T02D Status

Closing status, 2026-10-19: the revised 208-path assessment and T02D-owned
documentation cleanup are complete. The former plan below is historical context,
not an active instruction to assess `.project/` or rewrite writer-owned paths.
See [AUDIT.md](AUDIT.md) for current results and remaining acceptance gaps.

## Final Ownership

| Owner | Applied scope | Evidence |
|---|---|---|
| Core writer | 22 documents, including new Operations | `core-report.md` |
| Frontend writer | 18 documents | `frontend-report.md` |
| Capabilities writer | 13 documents | `capabilities-report.md` |
| T02D | 59 changed root, agent, generated, application and historical test documents | `CHANGED-FILES.json`, `T02D-DECISIONS.json`, `CLOSING-ASSESSMENTS.json` |

All 208 inventory paths have final retain/rewrite/notice dispositions with stable
destinations. Generic workflows and domain inputs were assessed for their own
purpose, not discarded as irrelevant. Previously proposed archive moves were
not performed. All `.project/` content is excluded from assessment; audit outputs
remain here. The orchestration ledger is neither assessed nor modified.

## Remaining Acceptance Work

1. Core owner: resolve the two `OPERATIONS.md#remote-trust` links identified in
   `CLOSING-CHECKS.json`. No missing local file target was found in the checked set.
2. Reviewer: distinguish attributed writer assessments, original read claims,
   closing direct reads and partial historical review. Do not infer full coverage
   from assessment totals or batch packets. Recertify original-manual preservation
   where exhaustive coverage is required.
3. Runtime owners: triage reported actor failures and approve/provision missing
   agent/File/frontend dependencies before running affected examples and suites.
   Documentation-only ownership does not authorize runtime repairs or installs.
4. Verify browser/mobile behavior, actual UI saves, restart/recovery, concurrency
   and remote caller boundaries separately. The 38-check tutorial HTTP rerun
   does not cover those guarantees.
5. Restart OpenCode before relying on revised skills/commands. No tool settings
   were changed, and no running workflow was exercised by reading its document.

## Repeatable Checks

From the N3TX checkout, without installing dependencies:

```sh
python3 .project/documentation-overhaul/inventory.py --check
python3 .project/documentation-overhaul/closing_checks.py --check
node .opencode/scripts/lint-skills.mjs
node --test .pi/extensions/skill-path-aliases/skill-aliases.test.mjs
PYTHONDONTWRITEBYTECODE=1 /workspace/.venv-agents/bin/python .project/documentation-overhaul/verify_tutorial.py
git diff --check
```

`closing_checks.py --check` validates persisted scan results, not a zero-issue
claim: inspect its `link_issues` and `limits`. Regenerate inventory and closing
checks after any further document changes. No commits were requested or made.

---

# Superseded Rewrite Plan

Status: **draft checkpoint; contingent on finishing T01 assessment**.
All paths are relative to the N3TX repository root. This plan authorizes no
runtime changes. Current work owns only `.project/documentation-overhaul/`.

## Information Architecture

| Canonical file | Responsibility | Changes |
|---|---|---|
| `README.md` | Product orientation, install, smallest complete example | Shorten; link to tutorial and package map; remove duplicated manuals and absolute promises. |
| `docs/README.md` | Single documentation navigation map | Learning path, concept/reference split, current versus historical labels. |
| `docs/GETTING_STARTED.md` | Complete model-first application tutorial | Replace stale setup, imports and Ref semantics; include auth, UI and verification. |
| `docs/ARCHITECTURE.md` | Model/schema authority and package boundaries | One end-to-end flow; separate construction API, model capability and routing mode. |
| `docs/MODELS.md` | Model declarations, relationships and serialization | Explicit local-versus-URL relationship decision table and lifecycle constraints. |
| `docs/CORE.md` | Concise core concept overview | Remove old source layout; link to model/schema references rather than duplicate them. |
| `docs/API_CRUD_ENDPOINTS.md` | CRUD wire contract | Preserve and verify partial-update semantics; explain replacement, validation and concurrency. |
| `docs/API_CUSTOM_ENDPOINTS.md` | Domain actions and method wire contract | Replace login example; verify method scope, caller injection, parameters and response shape. |
| `docs/AUTHORIZATION.md` | Trust/enforcement model | Policy resolution and per-entrypoint enforcement matrix; UI metadata is not enforcement. |
| `docs/ACTORS.md` | Messaging concepts and routing choices | Avoid "level 3" as a synonym for actor mode; link to adapter specifics. |
| `docs/AGENTS.md` | Agent selection, public API and execution | Replace obsolete method/route examples; show provider-free test usage and tool limits. |
| `docs/EXAMPLES.md` | Tested example catalog | For each app: working directory, prerequisites, capability, commands and limitations. |
| `docs/OPERATIONS.md` (new) | Configuration and deployment boundaries | Explicit debug/auth defaults, CORS, persistence/backups, concurrency, remote trust and budgets. |
| `docs/frontend/ARCHITECTURE.md` | Runtime/schema/component flow | Explain source-owned contracts and frontend extension choices without a second schema. |
| `packages/n3tx-core/docs/app-bootstrap.md` | Factory/builder/raw setup | Construction-versus-routing table, optional imports, static discovery and configuration order. |
| `packages/n3tx-core/docs/storage.md` | Storage and lifecycle limits | Document tested guarantees, not "prevents lock errors" assurances. |
| `packages/n3tx-core/docs/schema-pipeline.md` | Schema pipeline extension | Verify actual stage names/order and extension points against source. |
| `packages/n3tx-core/docs/authorization.md` | Authorization API details | Exact rules/context/resolver APIs; link cross-cutting enforcement matrix. |
| `packages/n3tx-agents/docs/agent-actor.md` | Data-backed agents | Current fields, exposed `/agentic` API, return shape and thread behavior. |
| `packages/n3tx-agents/docs/mixin.md` | Model reasoning API | `agentic` policy versus `run` runtime; imports and configuration precedence. |
| `packages/n3tx-agents/docs/tool-discovery.md` | Tools from model contracts | Explicit actor addresses, filtering, caller identity and denied calls. |
| `packages/n3tx-files/docs/file.md` | File metadata and bytes | Audit and retain native path; verify materialization/security and operational limits. |
| `packages/n3tx-ui/README.md` | UI install/orientation | Replace split manual-mount quick start; acknowledge ViewableMixin registration. |
| `packages/n3tx-ui/docs/components.md` | Component lifecycle/extension | Minimal custom renderer preserving native data/form lifecycle. |
| `packages/n3tx-ui/docs/viewable-mixin.md` | Python-side UI contract | Import order, declaration, routes and schema behavior. |
| `packages/n3tx-ui/docs/formidable.md` | Forms | Schema inputs, validation, field groups and permissions limitations. |
| `packages/n3tx-ui/docs/widgets.md` | Widget extension | Small registered widget example, display/edit behavior and tests. |
| `packages/n3tx-ui/docs/styling.md` | Theme contract | Keep verified token guidance; verify mobile and shell configuration. |
| `AGENTS.md`, `CLAUDE.md`, `BACKEND.md`, `FRONTEND.md` | Agent navigation and invariants | Align canonical ownership and portable paths; remove competing tutorials. |

For `packages/n3tx/README.md`, `packages/n3tx-core/README.md`,
`packages/n3tx-actors/README.md`, `packages/n3tx-agents/README.md` and
`packages/n3tx-files/README.md`, use the same brief structure: purpose,
dependencies, smallest runnable usage, canonical references, limitations.

Review `docs/API_INDEX.md`, `docs/API_OVERVIEW.md`, `docs/API_REFERENCE.md` and
`docs/API_DATA_MODELS.md` together before consolidating: determine which unique
content belongs in CRUD, actions, models and the package references. Keep stable
link stubs where existing inbound links require them. Do not remove files solely
because names overlap. Review `docs/JSON_FIELDS.md` similarly against storage docs.

Every additional path in `INVENTORY.jsonl` is still in audit scope. The table
above is a prioritized target structure, not a complete final rewrite manifest.

### Assessed Test Documents

| Exact source path | Proposed owner/destination | Disposition |
|---|---|---|
| `tests/frontend/README.md` | Test-contributor guide at the same path; verified runtime explanations belong in `docs/frontend/ARCHITECTURE.md` and `docs/frontend/MESSAGE_PROTOCOL.md` | Rewrite the misplaced application manual as harness instructions; coordinate extraction with frontend-reference owner. |
| `tests/frontend/QUICKSTART.md` | Tutorial owner, `docs/GETTING_STARTED.md` | Merge corrected application setup and leave a link stub. |
| `tests/frontend/CHANGELOG.md` | Historical record at the same path | Preserve versioned claims; do not update them to pretend they describe HEAD. |
| `tests/LATEST.md` | Historical testing record, proposed `docs/changelogs/testing/2026-04-test-recovery.md` | Archive dated recovery report and explain the move at the old path. Reported tests are not fresh validation. |

### Unresolved Contracts

- Scalar local model annotation rewriting remains in `ProtoModel.__init_subclass__`.
  Resolve the exact inheritance/annotation conditions before documenting a uniform
  local-T contract. This is not authorization to change framework code.
- Registration under DEBUG grants admin in the inspected implementation. The
  operations/authentication owners must warn explicitly; any behavior change is
  separate framework work.
- Complete denied-access checks across direct HTTP, actor HTTP, raw TX and agent
  tools before claiming parity. Discovery, UI visibility and descriptive fields
  are not permission enforcement.
- Final exact ownership for the remaining 455 unassessed paths is pending. These
  additions do not turn the prioritized plan into an accepted rewrite manifest.

## Tutorial Scope

Use one small issue-tracker application. The point is to demonstrate native
behavior, not invent generic services or hand-written REST handlers.

1. Declare a concrete BaseUser subclass and a storable Issue model. Specify
   explicit permissions, model validation and UI hints. Teach the default auth
   behavior before the first request.
2. Bootstrap with `create_app`, isolated SQLite storage and explicit environment
   settings. Show optional package imports before defining models when required.
3. Register/login through inherited BaseUser behavior. Create, list, update and
   delete through generated routes; show anonymous denial and expected responses.
4. Add a local related model and a separate HTTP(S) `Ref` field. Demonstrate
   their distinct serialized forms without contacting a remote service.
5. Use ordinary CRUD for a title/status edit. Add one genuine domain action with
   validation and an access rule. Do not claim atomicity unless the implemented
   storage path supplies it and a test demonstrates it.
6. Open the native UI, then extend one renderer and one widget while preserving
   runtime entity/schema/form handling. Show all required module imports.
7. Add an optional actor section without changing the conceptual model contract;
   explicitly state any tested wire differences.
8. Add optional File attachment and AgentActor sections. Verify agents using a
   mock provider, explicit tools and caller identity, not paid execution.
9. Demonstrate one streaming action, success/error termination and cancellation.
   Do not conflate a domain `done` event with transport completion.
10. Finish with configuration, backup/migration, security and test checklists.

Runnable application code should be extracted from fenced tutorial blocks into
temporary files by a documentation verification harness in a later authorized
slice. Do not duplicate a second hand-maintained tutorial implementation. If
new example/test files require expanding documentation-only ownership, obtain
that authorization first. Until extraction exists, record manual execution
commands and exact source blocks, never claim that copy/paste works untested.

## Execution Order

| Phase | Deliverable | Exit gate |
|---|---|---|
| 0 | Finish T01 current-doc and history review | Every inventory row has evidence-backed audience/value/issues/disposition/destination. Reconcile missing formats/aliases. |
| 1 | Correct high-risk contracts | F01-F09 addressed in retained current docs; tutorial imports/methods/routes run locally. |
| 2 | Build tutorial and canonical references | Model -> schema -> route -> UI -> actor/tool trace verified; no bespoke replacement infrastructure. |
| 3 | Synchronize navigation/agent guidance | Links, headings, terminology and package READMEs agree. |
| 4 | Classify historical/generated content | Preserve history; mark current-reference boundaries; prove generated-doc freshness or withdraw current-reference links. |
| 5 | Verify and review | Actual results recorded, limitations explicit, independent review complete. |

Hidden `.opencode/skills/n3tx-*/SKILL.md` guidance must be checked against the
same canonical contracts, not exempted from correctness review. This audit does
not edit skill configuration. A later editor must load the required OpenCode
configuration skill before making those changes. Generic `.agents/` workflows
need relevance/duplication assessment rather than blanket deletion.

Do not overwrite changelog statements or completed historical plans to look
current. Prefer preserving their paths and attaching a historical label/index
in a later approved documentation change. Application reference PDFs/text may be
domain inputs rather than framework guides; content-review them before assigning
archive disposition. Do not publish private/domain source content in summaries.

## Verification Commands

Run from repository root unless specified. These commands are a plan, not claims
of successful test execution.

```bash
python3 .project/documentation-overhaul/inventory.py --check
python3 scripts/test-backend.py --list
```

The required `/workspace/.venv-agents/bin/python` is absent in this checkout's
environment. Provision or approve the documented environment before backend
execution; do not silently switch to Collagen's environment. With it available:

```bash
/workspace/.venv-agents/bin/python scripts/test-backend.py --suite core -- -q
/workspace/.venv-agents/bin/python scripts/test-backend.py --suite actors -- -q
/workspace/.venv-agents/bin/python scripts/test-backend.py --suite agents -- -q
/workspace/.venv-agents/bin/python scripts/test-backend.py --suite files -- -q
/workspace/.venv-agents/bin/python scripts/test-backend.py --suite examples-core -- -q
/workspace/.venv-agents/bin/python scripts/test-backend.py --suite examples-actors -- -q
```

The runner defaults to writing `.project/test-runs/backend-test-overview.json`.
These are later-slice commands; T01's ownership does not permit that write.
Before executing under limited ownership, inspect runner output options and
redirect output to the authorized directory, or obtain scope approval.

From `tests/frontend/`, with existing dependencies available:

```bash
npm test
npm run test:e2e:serial
```

Do not install dependencies or run examples connected to paid providers as part
of this audit. E2E execution must use isolated seeded storage and the repository
harness. Check generated report/cache paths against the active ownership scope.

Add documentation verification for relative links/fragments, fenced runnable
imports, routes and expected JSON. Preserve external-link failures separately
from local broken links. Acceptance requires explicit denied access, invalid
input, missing dependency and stream-error cases, not only happy-path screenshots.

## Reviewer Checklist

- Each current guide is fully read and has an explicit disposition.
- Historical records are classified without pretending they describe HEAD.
- Every consequential claim has source/test evidence at the audited revision.
- Tutorial readers need no obsolete imports, guessed setup or undocumented auth.
- CRUD/actions, relationships/refs, construction/routing and UI/enforcement are distinct.
- No parallel CRUD API, duplicated client contract or second agent runtime appears.
- Actual command results and unverified behavior are clearly separated.
- Unrelated work and `.project/orchestration/` remain untouched.
