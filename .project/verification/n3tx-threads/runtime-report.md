# n3tx-threads extraction focused runtime checks

- Date: 2026-11-02
- Working directory: `/workspace/neuralys/collagen/lib/n3tx`
- Interpreter: `/workspace/.venv-agents/bin/python`; version recorded in `python-version.txt`.
- Python environment for checks: `PYTHONDONTWRITEBYTECODE=1`, `N3TX_DEBUG=false`, `N3TX_API_URL=https://threads.example`, and `PYTHONPATH` containing, in order, `packages/n3tx-core/src`, `packages/n3tx-actors/src`, `packages/n3tx-threads/src`, `packages/n3tx-agents/src`, `packages/n3tx-ui/src`, `packages/n3tx-files/src`, `packages/n3tx/src`.
- All invocation logs below include exact argv, cwd, settings, elapsed time, exit code, complete stdout and stderr. No test suite or wheel build was run.

## Commands and evidence

| Check | Exact invocation | Exit / elapsed | Evidence |
|---|---|---|---|
| Suite discovery only | `/workspace/.venv-agents/bin/python scripts/test-backend.py --list` | 0 / 0.068s | `list-suites.log` |
| Isolated package/app smoke | `/workspace/.venv-agents/bin/python -c <full code in log>` | 0 / 1.055s | `threads-smoke.log` |
| Plain core/actor import bootstrap | `/workspace/.venv-agents/bin/python -c <full code in log>` | 0 / 0.604s | `core-actor-bootstrap.log` |
| Shell syntax | `sh -n install-dev.sh` | 0 / 0.001s | `install-dev-shell.log` |
| AST/style | `/workspace/.venv-agents/bin/python .project/verification/n3tx-threads/run_checks.py` (the script invokes and records all scoped checks) | completed; 23 specified files, 0 syntax errors, 0 lines >80 columns, 0 missing module or named class/function docstrings | `ast-style.log`; checker `run_checks.py` |
| Metadata | Same runner invocation above | 5 manifests/configs parsed | `metadata.log` |

Smoke result: verified notes field declaration and storage table, Thread/TXRecord storage tables, non-storable `ThreadedMixin + ActorModel` declaration, `NOTE` payload round-trip, foreign-owner read denial specifically via `AccessDenied`, no `Thread.history`, and no attempted direct agent/SDK imports or loaded modules. The import finder raises `ModuleNotFoundError(name=fullname)`, allowing optional package probes to behave as absent. The smoke emitted a warning that CORS allows all origins; it did not alter configuration.

The separate bootstrap import guard treated `n3tx_threads`, `n3tx_agents` and `pydantic_ai` as unavailable and confirmed core/actor imports work without them. No history activation was observed.

AST/style scope was exactly the 13 assigned N runtime files plus the 10 assigned C runtime files, listed in `ast-style.log`; no unrelated dirty files were scanned. The style check is an 80-column maximum and checks module docstrings plus every `ClassDef`, `FunctionDef`, and `AsyncFunctionDef`, including private names. Syntax: 23 parsed, 0 errors. Lines exceeding 80: 0. Missing docstrings: 0. Changed packaging TOML/JSON manifests under N package roots plus C `pyrightconfig.json` parsed: five, all passed.

## Setup failure accounting

Three early smoke attempts failed before the captured final successful run; complete tracebacks are preserved in `prior-setup-attempts.log`: wrong `SQLiteStorage` import path (ImportError); non-storable actor incorrectly supplied as an app model (AttributeError for `__tablename__`); and wrong `TX` export path (AttributeError). The earlier AssertionError blocker attempt, which caught core's optional-package probe, was replaced with the required `ModuleNotFoundError` behavior and did not recur in the final smoke. These setup failures were not test assertion failures and did not modify source.

No source files were edited. Permanent suites and wheel build remain unrun, as directed.
