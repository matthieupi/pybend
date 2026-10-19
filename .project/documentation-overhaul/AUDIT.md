# T02D Documentation Assessment And Cleanup

## R03: Current-Guide Reading Complete

2026-10-19: The bounded read pass completed **all 59 remaining current guides in
full**. `CURRENT-REVIEWS.json` now contains their exact complete line ranges,
current SHA256 values and per-path assessments alongside the ten preserved R02
entries. Regenerated inventory reports **69 current-revision-reviewed guides and
zero current-guide pending**. This supersedes R02's pending count below, not its
separation of evidence categories.

See [R03 read-pass report](R03-READ-PASS.md) for ten substantive editor findings,
source citations, presentation/completeness notes and verification boundaries.
Reading is complete; identified defects are **not fixed**. In particular, the
widget example violates Formidable's Node-return contract, commit workflows can
include unrelated staged work, and protected-field creation/UI claims overstate
actual behavior.

The other categories remain separate: 53 writer-reported, 55 historical/generated
reference classifications, 24 generated package metadata and seven non-guides.
**208 is an inventory total, not a substantive-review total.** No source docs,
runtime, ledger, external environment or other writer's `t02e*`/tutorial verifier
were edited in R03. All `.project` source docs remain excluded.

## R02 Correction: Review Still In Progress

2026-10-19: This section supersedes the T02D completion and evidence claims below.
The audit is **not complete**. There are **59 owned current guides remaining**,
listed exactly in `REMAINING.txt`. All `.project/` content remains excluded from
assessment; these files are audit outputs only.

| Current category | Paths | Evidence meaning |
|---|---:|---|
| Current revision reviewed | 10 | Untruncated direct reads, exact ranges and SHA256 in `CURRENT-REVIEWS.json` |
| Owned current guide review pending | 59 | Prior decisions retained; no full-current-review credit |
| Writer reported | 53 | Attributed reports only, not independent owned review |
| Classified historical or generated reference | 55 | Bounded classification, not substantive full assessment |
| Classified non-guide | 7 | Legal/dependency metadata and application domain sources/transcriptions |
| Classified generated package metadata | 24 | `.egg-info` classification only; no edits or regeneration |
| Total | 208 | Not a count of substantively assessed documents |

The 45 prior closing-read claims are now explicitly unverified rather than
accepted as untruncated evidence. The 10 current reviews cover AGENTS, BACKEND,
CLAUDE and the build-app, extension-patterns, external-integrations, files,
framework-boundaries, framework-maintenance and streaming skills. Review hashes
are manually recorded after actual reads; inventory regeneration cannot renew
them. A changed hash returns a current guide to the pending list.

The R02 public-document correction is
`.opencode/skills/n3tx-streaming/SKILL.md`: its SSE section now distinguishes
direct yielded payloads and empty completion from actor serialized TX envelopes,
and links the canonical transport section. No other public document was edited
in this continuation. Restart OpenCode to load the corrected skill.

Audit artifacts changed in this continuation: `inventory.py`, `closing_checks.py`,
`CURRENT-REVIEWS.json`, `INVENTORY.jsonl`, `SCOPE.json`, `REMAINING.txt`,
`CHANGED-FILES.json`, `CLOSING-CHECKS.json`, `AUDIT.md`, and `REWRITE-PLAN.md`.
The aggregate manifest remains 112 changed documents (59 owned, 53 writer-owned),
not 112 changes attributable to this continuation. Current hashes include the
writer revisions present at regeneration. The refreshed scan checks 557 links
with no flagged issues; the previous two broken-anchor findings are resolved in
the current writer-owned text. This is a source scan, not browser verification.

Checks rerun for this correction: `inventory.py --check` and
`closing_checks.py --check` passed; skill lint passed for 25 skills with zero
warnings; the six Pi skill-alias tests passed; `git diff --check` passed.
Consistency checks validate persisted accounting, not completion of pending
reviews. No backend/frontend runtime suite was rerun in this continuation.

## Superseded T02D Report

Closing report: 2026-10-19. Baseline remains
`a189f755153558cdaf472764f9abc78a50929eaa`.

## Current Outcome

**208/208 in-scope paths have an assessment and disposition; zero are unassessed.**
This completes the revised per-path assessment, not an exhaustive full-read or
runtime correctness certification. All `.project/` content is excluded by the
user, including research, plans, history and live orchestration. Audit artifacts
are stored here as outputs, not assessed inputs. The previous 559-path scope and
455-path remaining-work gate below are superseded.

There are **112 changed documentation paths: 59 T02D-owned and 53 writer-owned**.
Exact paths, attribution and current SHA256 values are in `CHANGED-FILES.json`.
No runtime source, dependency file, permission setting or orchestration ledger
was changed by T02D; no commit, installation or remote/provider call was made.
Skill description text changed where obsolete concepts were removed; tool/model/
permission frontmatter remained unchanged. Restart OpenCode to load updated
skills and commands.

## Applied Dispositions

- Root AGENTS, CLAUDE and BACKEND now own navigation and constraints rather than
  duplicate API manuals. Current detailed contracts remain with the writer-owned
  tutorial, cross-cutting guides and package references.
- Root historical release/backlog/design records and application research have
  explicit historical notices. `tests/LATEST.md` retains its dated chronology
  with a warning that its filename and test totals do not describe fresh results.
- Generated snapshots remain at their original paths with stale labels. Their
  index identifies the generator, missing revision/registration provenance and
  overwrite risk. No regeneration was attempted.
- N3TX skills were aligned with local relationships versus HTTP(S) refs, separate
  construction/routing choices, actual agent policy/runtime and caller limits,
  File privacy/materialization, and UI/stream extension constraints.
- Generic agent workflows were assessed rather than deleted. Targeted corrections
  address obsolete paths, unsafe whole-file rollback, blind execution of bad
  plans, read-only agents instructed to write, and implicit fixed attribution.
  Legacy template assumptions are explicitly qualified; harness execution is not
  certified. No discovery aliases or tool permissions were changed.
- The two application PDFs and text transcriptions are preserved domain sources,
  not framework specifications. Text extraction loses column/list layout; use
  the PDFs when quoting. External adoption/currentness was not verified.
- Previously proposed archive moves were not applied. Retained history, legal
  text and generated packaging metadata keep their existing destinations and
  recorded caveats. No removed entrypoint requires a redirect.

## Evidence Integrity

`INVENTORY.jsonl` records 208 current hashes (183 tracked paths), classifications,
value, issues, disposition and evidence. `SCOPE.json` records 11 excluded
directories and the `.agents/commands -> prompts` alias. `REMAINING.txt` is empty.

Assessment is deliberately distinct from reading coverage:

| Evidence category | Paths | Meaning |
|---|---:|---|
| Closing original reads | 45 | Untruncated direct reads/PDF parsed pages; subsequent small edits authored or content preserved |
| Prior-session coverage unverified | 69 | Decisions retained, but earlier full-read claims are not recertified |
| Writer-owned current revisions | 53 | Attributed reports, not independent T02D full reads |
| Prior recorded partial reads | 40 | Bounded historical/context review, not exhaustive verification |
| Prior recorded full read, unverified | 1 | Earlier coverage retained as a claim, not fresh proof |

`CLOSING-ASSESSMENTS.json` provides the 45 exact paths and observed original read
ranges/pages. `T02D-DECISIONS.json` now explicitly labels its older evidence
strings as unrecertified. Packet generation, a matching hash and a source-code
probe do not prove that every paragraph was read. Full original-document
preservation for rewritten manuals remains unproven; insertion-only checks below
cover the historical notices, not wholesale rewrites.

Writer reports remain separate evidence: core covers 22 paths including new
Operations; frontend covers 18; capabilities covers 13. Core/frontend acknowledge
earlier truncation; capabilities reports full closing rereads of its current
guides, not exhaustive original/source review. None is silently upgraded into
independent T02D coverage. The scalar annotation question F12 below was resolved
by the core writer: bare BaseModel rewriting occurs at first StorableMixin
injection; list/Optional/inherited cases differ. It is no longer a universal
unresolved question.

## Closing Verification

| Check | Result |
|---|---|
| `python3 .project/documentation-overhaul/inventory.py` | 208 assessed / 208 paths, zero unassessed; current hashes regenerated |
| `python3 .project/documentation-overhaul/closing_checks.py` | Manifest and boundary checks passed; 551 local inline links checked, two broken fragments identified |
| Historical-body comparison against HEAD | 17 notice-bearing documents preserve original lines except final-newline normalization |
| Agent/command frontmatter comparison | 38 changed definitions retain settings other than descriptions |
| `node .opencode/scripts/lint-skills.mjs` | 25 skills, zero warnings |
| `node --test .pi/extensions/skill-path-aliases/skill-aliases.test.mjs` | 6 passed, 0 failed |
| `PYTHONDONTWRITEBYTECODE=1 /workspace/.venv-agents/bin/python .project/documentation-overhaul/verify_tutorial.py` | Fresh PASS: 38 HTTP checks plus schema, forged-caller rejection, SQLite values, relationship replacement and HTML/assets |
| `npm test -- --no-cache --maxWorkers=2 --minWorkers=1` in `tests/frontend/` | Blocked: `vitest: not found`; no tests ran |
| `git diff --check` | Passed on closing edits |

The shared Python environment now exists; the older missing-environment statement
below is obsolete. Tutorial execution used disposable storage and no external
network/provider calls. It emitted wildcard-CORS and Starlette/httpx deprecation
warnings; neither implies production approval.

## Remaining Gaps

1. **Two writer-owned broken fragments:** `docs/API_OVERVIEW.md:34` and
   `docs/AUTHORIZATION.md:158` link to `OPERATIONS.md#remote-trust`, but Operations
   has no such section. Owner should add the intended trust section or retarget
   both links. T02D did not edit writer-owned files.
2. **Original/current full-read coverage is not universal.** Exact per-path
   limitations remain in the inventory. Zero unassessed is not zero review gaps.
3. **Runtime suites are not all green.** Separately attributed capabilities
   report: actors 910 passed/5 failed; files 13 passed/13 failed with missing
   multipart setup; agents blocked at collection by `pydantic_ai`. These are
   writer-run results, not fresh T02D reruns or certified baseline regressions.
4. Browser rendering, mobile/accessibility, real UI writes, restart durability,
   concurrent writes and remote/agent/File end-to-end flows are not certified by
   the tutorial run. No dependency installation was performed to unblock them.
5. Link checking excludes external URLs, preserved historical bodies and generic
   workflow templates; Markdown heading slugs are approximated, not rendered.
   Generic workflows still require harness-specific tool/path adaptation.
6. Independent review acceptance and shared nvim-user access remain unverified.
   Current docs describe runtime security gaps; this documentation task did not
   fix those implementation boundaries.

**Acceptance:** revised scope assessment and owned cleanup complete; full
documentation acceptance remains conditional on the explicit gaps above. No live
orchestration status was changed. The historical checkpoint below is retained only
for provenance; its scope, counts, ownership and proposed gates are not active.

---

# Superseded T01 Checkpoint

Baseline: `a189f755153558cdaf472764f9abc78a50929eaa` (N3TX 0.12 checkout).
Scope: T01, documentation research only. Status: **incomplete; not ready for T01 acceptance**.

## Outcome

The current entry points cannot reliably teach an application from scratch.
Verified examples use obsolete imports, conflate local relationships with URL
references, omit required package registration, and demonstrate unsafe login
logic. Parallel architecture explanations also disagree about bootstrap and
routing terminology. Correct these before polishing presentation.

No existing documentation, framework code, dependency configuration, or
orchestration ledger was changed. This directory contains audit artifacts only.

## Coverage

`INVENTORY.jsonl` accounts for 559 paths discovered by the declared extension
policy, including 534 tracked paths, hidden agent guidance, generated Markdown,
historical records, application planning, and reference material. This is a
**discovery inventory, not 559 completed assessments**. `SCOPE.json` records
excluded directories and the `.agents/commands -> prompts` alias.

The persisted inventory now records **104 assessed paths**: 30 detailed
assessments in `REVIEWS.json` and 74 bounded purpose/status/provenance assessments
in `HISTORICAL-REVIEWS.json`. The latter includes one live coordination ledger,
explicitly classified as live rather than historical. Detailed assessments also
include two historical test records and dependency metadata; they are not all
current application guides. **455 paths still lack completed assessment**;
six of those have preliminary findings.

Recorded reading coverage is 32 full reads and 78 partial reads. Historical
excerpts are deliberately partial. Batch rendering is not reading; only observed
windows and recorded reviewed batches contribute to these totals. Truncated
outputs must not be upgraded to full coverage. Source/test reads are evidence
for findings, not substitutes for reading every guide. This continuation directly
read all 413 lines of `docs/MODELS.md` and 736 lines of `docs/AGENTS.md` in bounded
windows before completing their assessments.

The review ledgers contain additional package-level findings beyond F01-F10,
including File privacy/materialization boundaries, actor trust boundaries,
widget selection, unsafe renderer examples, reference-list deletion, actual
configuration defaults and stale test-guide contracts. Consult per-path records;
the original finding table below is not an exhaustive count of review issues.

Each row includes path, hash, line count, audience, value, reading status,
assessment status, issue fields, disposition, and canonical destination.
Unassessed rows explicitly preserve the current location provisionally. A
provisional `keep` is not approval of accuracy. Path-derived audiences and
historical classification still require content assessment.

Discovery includes Markdown/MDX, reStructuredText, text, AsciiDoc, Org, JSONL,
PDF, LICENSE and NOTICE. It does not treat every source comment, HTML application
template, image, JSON configuration, or notebook as a standalone guide. Those
remain supporting evidence when linked from a guide. Review this boundary before
claiming all-format coverage. No vendored directory is silently excluded merely
because its name looks historical; generated `docs/generated/` remains included.
Dependency trees, Git internals and runtime caches are excluded because they are
not maintained N3TX documentation. Outputs exclude themselves to prevent recursion.

## Verified Findings

| ID | Priority | Document evidence | Implementation/check evidence | Required correction |
|---|---|---|---|---|
| F01 | High | `docs/GETTING_STARTED.md:7,17,24,42,54-55,85-88` specifies Python 3.8+, a placeholder clone URL, third-party dependency installation without N3TX, and old top-level imports. | `packages/n3tx-core/pyproject.toml:10-19` requires Python >=3.10 and declares the actual dependency set; installed modules live under `n3tx_core`. | Replace onboarding with package installation and one executable, current-import application. Distinguish package minimum from the tested tutorial interpreter. |
| F02 | High | `docs/GETTING_STARTED.md:75` teaches `Ref[User]` as a foreign key. | `packages/n3tx-core/src/n3tx_core/models/ref.py:3-5,36-64` requires HTTP(S) entity URLs. `packages/n3tx-core/src/n3tx_core/tests/unit/test_ref.py:31-47,64-80,89-121` covers rejected integer/relative references, schema metadata, local-ID extraction and explicit hydration. Tests read, not executed. | Teach `T`/`list[T]` local relationships separately from `Ref[T]`/`list[Ref[T]]` URLs; document explicit remote hydration and failure conditions. |
| F03 | High | `docs/API_CUSTOM_ENDPOINTS.md:36-40` accepts `password` but returns a user solely by matching email. | `packages/n3tx-core/src/n3tx_core/models/base_user.py:75-109` checks stored password hash, verifies the password, and returns a token plus user. | Remove the bespoke login example. Teach inherited BaseUser login; use a non-authentication domain action to explain method exposure. This is unsafe guidance, not a claim that the runtime's built-in login is bypassed. |
| F04 | High | `docs/API_CUSTOM_ENDPOINTS.md:69-80` passes a JSON body to browser `fetch` with `method: 'GET'`; its comment simultaneously says POST is required. | Node's Fetch `Request` constructor rejects the shown request shape with `TypeError: Request with GET/HEAD method cannot have body.` No network request was sent. | Choose a supported method/parameter contract and verify it through the actual route and browser. Do not fix only the comment or assume a GET route accepts POST. |
| F05 | Medium | `README.md:166-184` labels actor routing bootstrap level 3. `AGENTS.md:257-273` describes raw primitives as level 3, while `AGENTS.md:579-595` uses levels for model/routing combinations. | `packages/n3tx-core/src/n3tx_core/app.py:4-14,143-146` provides factory/builder/raw bootstrapping and a separate routing option. Its own class docstring also retains confusing level terminology. | Use two independent axes: construction API and routing mode. Do not promise transport parity without a tested matrix. Source docstrings are follow-up work outside this task's ownership. |
| F06 | High | `packages/n3tx-agents/README.md:35-58` defines an agent-enabled model without first importing `n3tx_agents`; lines 9-15 imply all system operations are automatically tools. | `packages/n3tx-agents/src/n3tx_agents/__init__.py:14-20` registers the mixin at import time. `tools.py:44-102` discovers from supplied actor addresses with self-exclusion and method filtering. | Include import order, registration/storage, async execution, provider prerequisites and explicit tool selection. Tool discovery is not a grant of permission. |
| F07 | High | `packages/n3tx-ui/README.md:25-48` says the Python export is a single helper, mounts only UI assets separately, and shows unimported topbar/router tags. | `packages/n3tx-ui/src/n3tx_ui/__init__.py:1-12` imports ViewableMixin and registers triggers. `packages/n3tx-core/src/n3tx_core/api/backend.py:46-82` merges package assets into one namespace. | Teach the native bootstrap/static namespace first, package import side effects, and explicit custom-element imports. Keep manual mounting only as a separately verified advanced example. Browser execution of this example is still pending. |
| F08 | Medium | `BACKEND.md:5-12`, `FRONTEND.md:8-12`, and `AGENTS.md:627-674` hard-code `/workspace` as repository root. | This checkout is `/workspace/neuralys/collagen/lib/n3tx`. `/workspace/.venv-agents/bin` does not exist. The backend runner correctly derives root from its own file. | Use repository-relative paths and a clearly identified test interpreter. Separate local agent-environment notes from portable contributor instructions. |
| F09 | High | `docs/AGENTS.md:54,64,72,78-102,228,328` teaches `run(task=...)`, `/run`, `call()` and `agent_run()` as the main agent interfaces. | `packages/n3tx-agents/src/n3tx_agents/mixin.py:169-192` exposes `agentic(task, **kwargs)` and lower-level `run(task, prompt, tools, ...)`. `actor.py:126-159` exposes `/agentic`, resolves stored configuration and returns a JSON string. Package grep finds no `def agent_run` or `def call`. | Rewrite against the current policy/runtime API, distinguishing AgentActor response shape from AgentMixin results. Verify generated endpoints rather than mechanically renaming every occurrence. |
| F10 | Medium | `README.md:3-5,32,91,120,229-233`, `AGENTS.md:68-78,294` repeatedly promise everything works automatically with no configuration. | F01-F09 show concrete prerequisites. `authorize/resolver.py:30-48` defaults unspecified actions to AUTHENTICATED, not an application-specific ownership policy. `backend.py:97-101` warns about default wildcard CORS. | Replace promotional assurances with capability/prerequisite/limit tables. State what developers must choose: permissions, identity, storage, optional package imports, deployment configuration and provider credentials. |

## Architectural Guidance

### Additional Source Findings

| ID | Evidence | Required treatment |
|---|---|---|
| F11 | `docs/MODELS.md:259-293` describes registration without noting `base_user.py:145-148`, which assigns `admin` when `config.DEBUG` is true. `config.py:28` defaults DEBUG to false but accepts the environment override. | Treat DEBUG as security-relevant, not merely error verbosity. Add an explicit warning to canonical authentication and operations guidance; verify with an isolated registration test in a later authorized slice. No exploit or runtime test was executed here. |
| F12 | `docs/MODELS.md:34,65` describes annotation rewriting; `proto_model.py:102-111` still rewrites certain BaseModel annotations to Ref, while the same guide's relationship section distinguishes local T from URL Ref. | Track an unresolved implementation-contract question. Inspect inheritance/annotation cases and tests before promising a universal scalar relationship rule; do not silently remove the description as stale. |
| F13 | `docs/AGENTS.md:293,414-440,600,639-640` describes plain tools, an adapter-bearing AgentDeps, run_endpoint, direct stream inheritance and transient adapter cleanup. `actor.py:95`, `agent.py:35-40`, `schema_ext.py:39-45` and inspected frontend component declarations differ. | Rewrite data-backed tool configuration, runtime ownership, emitted schema and component hierarchy together; changing route names alone is insufficient. |

The rewrite should preserve native mechanisms rather than respond to stale docs
by inventing application scaffolding:

| Concern | Documentation contract | Verification still needed |
|---|---|---|
| Model/schema authority | Fields, methods and metadata feed generated contracts; do not manually duplicate schemas in clients. | Trace model -> schema -> HTTP -> frontend for the tutorial. |
| CRUD versus actions | Use inherited CRUD for ordinary field changes; use `@expose_route` for genuine domain operations. | Partial updates, validation, collection replacement and concurrency behavior. An action name alone does not make a read-modify-write atomic. |
| Relationships | Separate local child IDs, URL references, and explicit link models. | Ownership/deletion, inverse collections, population limits and remote authorization. |
| Authorization | Explain resolver fallback, model/action policy, caller injection, and UI hints versus server enforcement. | Denied access through direct HTTP, actor HTTP, TX and tool paths; no blanket parity claim yet. |
| Frontend | Reuse runtime entities, schema-driven forms, component lifecycle, renderer and widget extension points. | Runnable minimal shell, custom-element registration, static precedence, mobile layout and error states. |
| Actors/agents | Separate messaging from LLM policy/runtime and data-backed agent configuration. | Current route names, caller propagation, tool scope, persistence and provider-free tests. |
| Files | Start with File metadata plus byte-store capability rather than bespoke upload APIs. | Materialization, path containment, upload/download policy and size/range limitations. |
| Streaming | Distinguish application event vocabulary from transport completion/error/cancellation. | SSE and WS delivery, terminal events and cancellation under disconnect. |
| Operations | Document actual defaults and explicit production prerequisites. | Secrets/debug, migrations/backups, SQLite contention, CORS, remote trust and resource budgets. |

## Coherence And Presentation

Keep one tutorial path in `docs/GETTING_STARTED.md`, one documentation map in
`docs/README.md`, cross-cutting concepts in root `docs/`, and deep implementation
references in package docs. Root/package READMEs should orient and link, not
duplicate long tutorials. Agent context should give constraints and reference
maps, not a competing API manual.

Historical plans and changelogs describe their time, not today's contract.
Preserve their truth and provenance. Decide archive moves after content review;
do not globally replace old API names in historical documents. Generated docs
need an identified generator and reproducible freshness check before retaining
them as current reference.

Use compact decision tables and one useful data-flow diagram per concept. Remove
marketing interjections and repeated "zero config" claims. Mark snippets as
runnable, excerpt, or pseudocode. Runnable examples must include imports, setup,
authentication, expected output and cleanup. Icons may aid navigation but must
not carry meaning alone.

## Actual Checks

| Check | Result |
|---|---|
| `git status --short` before edits | Only pre-existing untracked `.project/orchestration/`. |
| `git ls-files` documentation discovery | Tracked documentation enumerated, including hidden agent/history files. |
| `git ls-files -s` alias inspection | `.agents/commands` is a tracked symlink; not an independent documentation source. |
| `python3 .project/documentation-overhaul/inventory.py` | 559 paths, 534 tracked, 11 excluded directories, one directory alias. |
| `python3 .project/documentation-overhaul/inventory.py --check` | Passed; discovered paths, hashes, coverage metadata, exclusions and aliases match persisted artifacts. |
| `python3 scripts/test-backend.py --list` | Succeeded; lists core, actors, agents, files, examples-core, examples-actors, examples-grants and veille. Listing is not test execution. |
| Node Fetch Request reproduction | GET with body throws TypeError before networking, confirming F04. |
| Required Python environment availability | `/workspace/.venv-agents/bin` missing. Backend suites not run; no dependencies installed. |
| Source and test inspection | Evidence cited above. Not a full implementation/security audit. |
| Tutorial execution, frontend/browser suites, links | Not completed. |
| Final baseline/scope check | HEAD unchanged; status contains only this new audit directory and pre-existing orchestration directory. `git diff --check` passes for tracked changes; it does not check these untracked artifacts. |
| Shared-user mode prerequisite | New directory/files inherit private agent modes; `id nvim` reports no such user. Shared nvim access cannot be verified here. No unrelated permissions were broadened. |

## Acceptance Status

| Criterion | Status | Remaining gate |
|---|---|---|
| AC01: per-path assessment | Partial | Inventory exists, but most paths lack content assessment and final disposition. |
| AC02: accurate retained claims | Partial | Source-grounded findings and per-path reviews recorded; no general correctness sign-off. |
| AC04: architectural alignment | Partial | Priority native mechanisms mapped; authorization and transport paths need deeper checks. |
| AC05: coherence | Partial | Target ownership proposed, but full link/duplicate mapping pending. |
| AC07: concise presentation | Partial | Style problems identified; current guides intentionally unchanged. |

T01 must remain open. No independent review has occurred. Complete recorded
reading/assessment, extend source evidence, finalize destinations, then request
review before allowing T02 to treat the rewrite manifest as accepted scope.
