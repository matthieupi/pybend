# N3TX Contributor Guide

> **Recovery checkpoint — 2026-11-06:** executable source is October 31
> `d75bee4` plus archived dirty changes; newer commits are preserved on `threads`,
> `master` is at `d75bee4`, and current work is on `reconciliation`.
> Thread/TXRecord are in `n3tx_agents`, not a
> separate TTX package. Later documentation is preserved, not evidence of the
> restored API. See the
> [recovery report](../../../.project/docs/reconciliation-20261106.md).

This file owns contribution rules and navigation, not a second API manual.
Paths and commands are relative to the N3TX checkout, which may itself be a
separate repository inside an application.

## Working Standard

Work as a rigorous staff engineer: verify claims, understand the whole affected
path, prefer simple native mechanisms, and preserve the user's work. Distinguish
implementation evidence, intended design, reported tests and tests actually run.
Do not conceal missing guarantees with application workarounds.

1. Read [README](README.md), [the documentation map](docs/README.md), and the
   relevant subsystem below before proposing changes.
2. Explain the intended change, ownership, invariants and verification approach.
3. Inspect the current implementation and relevant tests. Local precedent and
   historical plans can be stale; resolve discrepancies before relying on them.
4. Make the smallest complete change. Preserve unrelated edits and concurrent
   work. Do not reset, commit, push or change dependencies without authorization.
5. Verify the actual entrypoint, including invalid input and denied access, then
   update the canonical documentation and affected navigation.
6. Report a concise Step Review: changed behavior/files, checks, failures and
   unverified boundaries. Do not claim coverage from truncated reads.

For bug fixes, reproduce the failure with a test first, make the minimal fix,
then refactor if needed. If reproduction is unavailable, state why and retain
the verification gap. Explain architectural concerns separately from the fix.

## Read By Subsystem

| Work | Start here |
|---|---|
| Model-first application | [Getting started](docs/GETTING_STARTED.md), [architecture](docs/ARCHITECTURE.md) |
| Models, storage, API, auth | [Backend navigation](BACKEND.md), [models](docs/MODELS.md), [authorization](docs/AUTHORIZATION.md) |
| Actor messaging and transports | [Actors](docs/ACTORS.md), [actor package](packages/n3tx-actors/README.md) |
| Reasoning and tools | [Agents](docs/AGENTS.md), [agent package](packages/n3tx-agents/README.md) |
| Files and byte storage | [File guide](packages/n3tx-files/docs/file.md) |
| UI, forms, widgets, themes | [Frontend navigation](FRONTEND.md), [UI package](packages/n3tx-ui/README.md) |
| Deployment and defaults | [Operations](docs/OPERATIONS.md) |

Read both backend and frontend navigation for cross-stack work. Package guides
own detailed mechanisms; `docs/` owns cross-cutting contracts. `.project/` holds
working artifacts, not current API authority. Historical and generated snapshots
are not substitutes for current guides or live schema.

## Architectural Constraints

- Keep model fields, validation, permissions, methods and UI hints authoritative.
  Reuse generated CRUD; use `@expose_route` for genuine domain behavior, not a
  second CRUD implementation. An exposed method is not automatically atomic.
- Separate factory/builder/raw construction from direct/actor routing. Actor
  capability does not imply actor HTTP or identical authorization on every path.
- Import optional mixin packages before defining models that use their flags.
  Register storable models explicitly. Keep local relationships distinct from
  absolute HTTP(S) `Ref[T]`; consult the scalar-annotation caveat in the model guide.
- Reuse schema-driven entities, forms, widgets and renderer hooks rather than
  duplicating schemas in clients. UI hiding and tool discovery are not access gates.
- Verify caller propagation and permission enforcement on the enabled transport.
  Do not trust a body-supplied identity or assume raw Python/TX has HTTP guards.
- Keep secrets and runtime data out of Git. Use isolated test storage. Debug
  registration grants admin in this checkout; production needs explicit security
  configuration. Paid calls, live imports and deployment need authorization.

## Tests

Run backend commands from the N3TX repository root. Select the approved Python
environment explicitly; do not silently use a parent application's interpreter.
In the shared agent environment it is `/workspace/.venv-agents/bin/python`.
Elsewhere set `N3TX_PYTHON` to the absolute path of your prepared environment.

```sh
"${N3TX_PYTHON:-/workspace/.venv-agents/bin/python}" scripts/test-backend.py --list
"${N3TX_PYTHON:-/workspace/.venv-agents/bin/python}" scripts/test-backend.py --suite core -- -q
"${N3TX_PYTHON:-/workspace/.venv-agents/bin/python}" scripts/test-backend.py --short
```

The runner isolates suites by process and working directory to avoid example
module collisions. Listing suites is not test execution. Inspect its report
output path when operating under restricted file ownership. Missing dependencies
must be reported; install only into the approved environment when authorized.

Frontend setup and Vitest/Playwright commands are maintained in the
[test harness guide](tests/frontend/README.md). Run example apps from their own
directories using the [example catalog](docs/EXAMPLES.md); seed only disposable
databases. Test credentials in examples are not production credentials.

## Commits And Documentation

When a commit is requested, follow `type(scope): Description [wave]`, checking
recent history for the active wave. Update package mechanism documentation first,
then cross-cutting guides and navigation. Keep changelog/release facts historical;
add a dated correction or current-guide pointer instead of rewriting the past.

Preserve shared editor access on new project files where the identities exist;
do not broaden permissions on secrets, runtime data or unrelated directories.
