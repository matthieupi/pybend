# Artifact-closure and diff-check supplement

Date: 2026-11-02. This narrow follow-up did not rerun tests or builds; it inspected the already-built three wheels and ran scoped whitespace checks. No source/test edits or environment changes were made.

## Built-wheel closure check

Exact command from the artifact directory:

`PYTHONDONTWRITEBYTECODE=1 /workspace/.venv-agents/bin/python artifact_closure.py`

Exit 0. Exact output, including complete member lists and wheel `Name`, `Version`, and `Requires-Dist`, is `logs/artifact-closure.stdout`; stderr/status are `logs/artifact-closure.stderr` and `.meta`. Reproducible helper is `artifact_closure.py`.

Assertions passed:
- The agents wheel contains none of `n3tx_agents/thread.py`, `n3tx_agents/tx_record.py`, `n3tx_agents/notes_mixin.py`, or `n3tx_agents/threaded_mixin.py`.
- The threads wheel contains all canonical `n3tx_threads/{thread,tx_record,notes_mixin,threaded_mixin}.py`, and no `n3tx_agents/` or `pydantic_ai/` package members.
- Built `n3tx_agents/history.py` imports `Thread` from `n3tx_threads`; built `n3tx_agents/agent.py` imports `Thread` and `current_execution` from canonical `n3tx_threads` modules.
- Agents and full-meta wheel metadata each declares `n3tx-threads`; threads metadata declares core and actors only.
- Complete wheel member listings are in the log (including shipped agents tests and static assets). This is artifact evidence only, not a runtime test claim.

## Scoped git whitespace checks

All four commands exited 0 with empty stdout/stderr. Unstaged and staged checks were run separately:

- N unstaged: `git diff --check -- <17 explicit N paths>`
- N staged: `git diff --cached --check -- <same 17 N paths>`
- C unstaged: `git diff --check -- core/native_models.py core/app.py core/agents/backend.py core/agents/history.py core/agents/runtime.py core/actors/agent_tools.py core/models/email.py apps/hr/models/resume.py n3tx_ext/playground/policy.py scripts/live_agent_check.py`
- C staged: `git diff --cached --check -- <same 10 C paths>`

N path arguments were the 5 canonical threads runtime modules, agents `__init__.py`, `agent.py`, `history.py`, `tools.py`, the three removed legacy module paths, core `app.py` and `api/routes_fastapi.py`, `apps/veille/main.py`, `scripts/test-backend.py`, and `packages/n3tx/src/n3tx_meta/__init__.py`. Exact path arguments and both exit codes are in `logs/n-diff-check.meta` and `logs/c-diff-check.meta`; individual output streams are recorded in the four corresponding `*-diff-check-{staged,unstaged}.{stdout,stderr}` files.

These scoped source whitespace checks do not imply a runtime pass or expand into unrelated dirty paths. Prior C test failures and counts remain as recorded in `packaging-report.md`; no assertion was altered or bypassed.
