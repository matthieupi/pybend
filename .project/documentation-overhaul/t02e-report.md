# T02E — focused corrections and verification

## R01 rereview correction — latest results

**The original Issue `title` model was incompatible with native empty-value
creation.** `ntx-list.openCreateModal()` initializes the editor with `value={}`;
Formidable chooses `title` only when that key already exists in the value,
otherwise renders a `name` header input. Both heading fields are excluded from
the body. A required title therefore had no matching create input. This defect
was not caught by the original HTTP-only verification.

### Changes

- Changed only the tutorial's Issue heading to required `name`, including
  `ui.field_order`, curl payloads, invalid-input instructions and persistence
  instructions. Added an explicit explanation of the native create constraint.
- Limited the demo Issue name to the same ASCII alphabet as Label name, while
  retaining the trusted-input-only warning. This does not sanitize arbitrary
  fields or make the UI safe for shared untrusted content.
- Updated both HTTP verifiers (`verify_tutorial.py`, `t02e_browser.py`), including
  schema, payload, response and SQLite column assertions. The frontend
  continuation contains no Issue title field references, so required no edits.
- Browser smoke now scopes heading selectors to
  `ntx-modal ntx-item input[data-key="name"]` and the collection item's
  `input[data-key="name"]`; header inputs have no `name` attribute. Also corrected
  resolve's selector to `data-key="resolution"` and its submit button.
- Removed the HTTP-create fallback entirely. Native creation must succeed, and
  the persisted collection must contain the entered name, before subsequent
  edit/action checks proceed. HTTP GET is used only to assert persistence.

### Exact checks executed

All results are persisted by `t02e_r01_checks.py`; commands and exit codes are
in `t02e-r01-checks.json`. Python commands run from repository root; npm/Vitest
commands run from `tests/frontend`.

| Command | Result |
|---|---|
| `/workspace/.venv-agents/bin/python .project/documentation-overhaul/t02e_browser.py` | **21 HTTP checks passed**; overall exit 1 from the known Chromium launch blocker |
| `/workspace/.venv-agents/bin/python .project/documentation-overhaul/verify_tutorial.py` | **39 HTTP checks passed**, schema/caller/SQLite/relationship assertions passed |
| `npx vitest run --config ../../.project/documentation-overhaul/t02e-native-create.config.mjs --maxWorkers=2 --minWorkers=1` | **3 tests passed**, 1 file |
| `npm test -- --maxWorkers=2 --minWorkers=1` | **69 files passed; 1,397 tests passed, 1 skipped** (Permissions suite); 36.72 seconds on final run |

Final `git diff --check` and `node --check` on the browser verifier passed.
The refreshed global link scan covered 177 Markdown files / 650 local references
with zero current-doc errors; historical/template findings remain separately
classified. No tracked Python/JS/JSON/TOML/lockfile diff was present.

The focused jsdom tests import **native Formidable**, reuse the existing frontend
harness and consume `t02e-issue-schema.json` captured from the extracted tutorial's
real `/Issue` response. They establish:

1. `value={}` renders `input[data-key="name"]` without a `name` attribute;
   native validation rejects the empty value, then accepts the typed name read
   through `Formidable.readFormValue()`.
2. Empty and HTML-bearing names fail native validation.
3. The former required-title schema reproduces the missing title input and
   native validation failure under the same empty-value conditions.

These tests cover form generation/reading/validation, **not** a live modal's
event-to-transport flow or browser persistence. The initial artifact test failed
collection because Vite transformed `import.meta.url` to a non-file URL; replacing
the filesystem URL read with a JSON import corrected the harness. Final logs
contain the successful rerun. No permanent suite/runtime changes were made.

Evidence: `t02e-r01-native-create.log`, `t02e-r01-frontend-suite.log`,
`t02e-r01-tutorial-http.log`, `t02e-r01-extracted-http-browser.log`, plus refreshed
HTTP results, schema and browser-launch logs. The older 17-check result below
describes the original pass, not the revised tutorial.

### Remaining boundaries

- Browser launch remains blocked by missing host `libglib-2.0.so.0`; no OS
  packages installed. Full native login/create/edit/save/resolve still needs a
  real-browser rerun. No successful browser result is claimed.
- Native Formidable's required-title create mismatch remains in the runtime;
  this task changes the tutorial model, not framework behavior.
- Existing Formidable HTML safety limits and the initial agent-test dependency
  gap remain. No new dependencies installed in R01.
- No inventory, ledger, runtime, permanent test-suite, configuration or lockfile
  changes; no commits. New test config is an artifact-only Vitest entrypoint.

### Method Signature Surface

No runtime signatures changed; existing verifier function signatures unchanged.
The added artifact test hooks/callbacks have `() => void` signatures. The added
check runner is top-level orchestration, with no new callable interface.

## ✅ Scope and outcome

Implemented the five accepted documentation corrections. No runtime source,
configuration, lockfile, ledger or commit changes. Existing writers' edits were
preserved. `.project` was not used as documentation authority; this directory
contains only work/verification artifacts for this pass.

| File | Correction |
|---|---|
| `docs/GETTING_STARTED.md` | Trusted-input local-only warning; server-validated ASCII label alphabet; complete app-owned static shell with identity initialization before protected component imports/mount; `allow-create`; viewing-only distinction for generated `@` shells; explicit browser verification gap |
| `docs/frontend/ARCHITECTURE.md` | Continues existing `main.py`, registers User/Label/Issue, retains SQLite/security/SSR settings, correct static path; imports protected components dynamically after permissions initialization |
| `docs/AGENTS.md` | Canonical `app_agent` fields, AgentActor/AgentTool registration, table targets, overwrite/reconciliation semantics and caller limits |
| `packages/n3tx-core/docs/app-bootstrap.md` | Links canonical configuration section |
| `docs/API_OVERVIEW.md`, `docs/AUTHORIZATION.md` | Replace nonexistent remote-trust anchor with network-adapter section |

Label validation is deliberately not described as sanitization of arbitrary
fields. Formidable remains unsafe for general untrusted HTML-bearing content.
The optional scaffold reference expansion was deferred to keep this pass finite.

## Source evidence

- UI `mixin.py` emits minimal collection/member pages without Permissions.init;
  collection pages omit allow-create.
- Core `static/utils/Permissions.js` starts with null identity, initializes from
  `/auth/me` using localStorage jwtToken, and gates OWNER using user_id.
- UI `ntx-list.js` gates creation on both allow-create and permissions; delegates
  native forms and CREATE through its existing entity/Matrix plumbing.
- Current Formidable guide documents header interpolation and security limits.
- Agents `app_agent.py` and `tests/test_app_agent.py` establish config validation,
  system-key/name lookup, overwrites and ordered tool reconciliation. No provider
  was executed. Provisioning tests were attempted but could not collect because
  the approved Python environment lacks `pydantic_ai`; source inspection is not
  presented as a passing test run.

## 🧪 Verification

### Extracted tutorial + generated HTTP

Command: `/workspace/.venv-agents/bin/python .project/documentation-overhaul/t02e_browser.py`

The harness extracts the marked Python and HTML blocks from the current guide,
creates a temporary application under this artifact directory, starts loopback
Uvicorn on an ephemeral port, and cleans up the process and SQLite directory.
No production storage or providers are used.

**17 HTTP checks passed:** registration and login for Alice/Bob, authenticated
identity, HTML-bearing label rejection (422), valid label creation (201), issue
creation, title edit, resolution, persisted readback, Bob's empty list and denied
read/update/resolve/delete (403), then owner deletion. Exact statuses are in
`t02e-http-results.json`. This is HTTP evidence, not browser evidence.

### Browser: blocked before page load

The executable `t02e_browser.mjs` attempts built-in login, permissions readiness,
native collection creation, edit/save, resolution, and second-user denial. It
has **not executed these steps**: Chromium exits 127 loading
`libglib-2.0.so.0`. Exact output is persisted in `t02e-browser-launch.log`;
server output is in `t02e-server.log`. Selector/runtime correctness remains
unverified. The script fails nonzero on launch or recorded step failures.

No N3TX runtime defect is established by this launch failure. Native browser
create/edit/save/resolve remains an acceptance gap. Re-run on a host with
Chromium's shared libraries; any runtime failure must be recorded without
patching framework source under this task's authorization.

### Link/anchor scan

Command: `/workspace/.venv-agents/bin/python .project/documentation-overhaul/t02e_links.py`

Repository-wide Markdown scan excludes `.project`, dependencies and Git. Current
docs have zero detected local path/anchor errors. Historical proposal/release/
generated bodies are classified separately, not counted as current failures.
The initial scan covered 177 Markdown files and 649 local references; final exact
counts and all findings are in `t02e-links.json`. Eleven agent-template references
are separately classified (placeholder `url`, `<Slug>` and generated output
paths). Twenty-seven historical findings were retained, not rewritten; they are
outside this pass's edits, including old `src/n3tx/...` links in CHANGELOG.

This is a lightweight Markdown-link/GitHub-style ATX-anchor checker, not an
external URL crawler or complete Markdown parser. Root-absolute browser paths
and remote links are not checked. Historical anchor findings can depend on the
renderer; they are scan findings, not a claim of audited historical correctness.

## Environment changes and limits

- Parent locations verified with `ls` before installs. `/tmp/opencode` was not
  accessible; temporary test apps instead used this authorized artifact directory.
- `npm ci` in existing `tests/frontend`: installed 140 packages from its lockfile.
  npm reported 10 vulnerabilities (2 moderate, 6 high, 2 critical). No audit fixes
  or dependency/lockfile edits were made. npm also warned about esbuild's
  unapproved install script; not relevant to this direct Chromium launch.
- `npx playwright install chromium`: downloaded Chromium and headless shell 1208
  to the user's Playwright cache. No host library installation attempted.
- Initial Python startup lacked n3tx_ui. A UI-only editable install failed to
  resolve unpublished n3tx-core. Then installed local editable `n3tx-core==0.12.0`
  and `n3tx-ui==0.12.0` only into `/workspace/.venv-agents`; their declared runtime
  dependencies were already satisfied. No other Python packages installed.

## Method Signature Surface

No runtime callable/interface signatures changed. New verification helpers only:

```text
t02e_browser.py
  + block(text, name, language)
  + main()
  + verify_http(origin)
t02e_browser.mjs
  + async step(name, fn)
  + async login(p, email)
t02e_links.py
  + historical(path)
  + prose(text)
  + anchors(path)
  + main()
```

## Follow-up

Final checks passed: `git diff --check`, `node --check` on the browser smoke,
and `/workspace/.venv-agents/bin/python -m pip check` (no broken requirements).
`git diff --name-only -- '*.py' '*.js' '*.json' '*.toml' '*.lock'` returned no
tracked source/config/lockfile changes. Work scripts are untracked artifacts,
not runtime modifications.

Browser acceptance remains open pending a suitable host; app-agent executable
tests remain open pending its dependencies. No paid calls, runtime fixes or
unrelated documentation rewrites were attempted.
