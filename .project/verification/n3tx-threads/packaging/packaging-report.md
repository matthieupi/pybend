# Follow-up package and focused-consumer verification

Date: 2026-11-02. This is follow-up evidence; prior reports/logs were preserved. No source/test edits, source copies, overlays, shared-environment installs, publication, provider calls, service operations, or live CRM data access occurred. Build-generated ordinary metadata/artifacts remain as allowed. Interpreter: `/workspace/.venv-agents/bin/python`, Python 3.11.2; C interpreter: `/workspace/neuralys/collagen/.venv/bin/python`, Python 3.11.2.

## Packaging

1. Built all three requested wheels from the actual N checkout, with no dependency resolution, build isolation, or network index:

   `TMPDIR=<N>/.project/verification/n3tx-threads/packaging/tmp PIP_NO_INDEX=1 PYTHONDONTWRITEBYTECODE=1 /workspace/.venv-agents/bin/python -m pip wheel --no-deps --no-build-isolation --wheel-dir <N>/.project/verification/n3tx-threads/packaging/wheels ./packages/n3tx-threads ./packages/n3tx-agents ./packages/n3tx`

   Exit 0. Logs `logs/wheel-build.stdout`, `.stderr`, `.meta`. Wheels produced:
   - `n3tx_threads-0.12.0-py3-none-any.whl`, 27,811 bytes, SHA-256 `cfbf0255b10af955a1c73d1ee2103274441726d9107a2b6e5fcc2b51c49e244e`
   - `n3tx_agents-0.12.0-py3-none-any.whl`, 76,543 bytes, SHA-256 `78e9e8b591680a20f16adc2302380f44663caadc75845ab40d923c616331de17`
   - `n3tx-0.12.0-py3-none-any.whl`, 2,898 bytes, SHA-256 `73c5bd29b9d5ce5951a6c234e09a6ac40139c42775c730f2db4a624ee88daa11`

2. Installed only the built threads wheel into the disposable target, with no index/dependencies:

   `/workspace/.venv-agents/bin/python -m pip install --no-deps --no-index --target <N>/.project/verification/n3tx-threads/packaging/wheel-install <N>/.project/verification/n3tx-threads/packaging/wheels/n3tx_threads-0.12.0-py3-none-any.whl`

   Exit 0. Logs `logs/wheel-install.stdout`, `.stderr`, `.meta`.

3. Ran `wheel_smoke.py` from the artifact directory with `PYTHONPATH` ordered as wheel-install, then the actual N `n3tx-core/src` and `n3tx-actors/src`; no threads/agents/meta source paths were included. Environment: `PYTHONDONTWRITEBYTECODE=1`, `N3TX_DEBUG=false`, `N3TX_API_URL=https://threads.example`. The import finder raises `ModuleNotFoundError` for agents and Pydantic AI. Exit 0. Verified module `__file__` came from wheel-install, exact public exports, Thread construction, typed `TXRecord.thread` reference, thread wheel `Requires-Dist` exactly core and actors (no agents/SDK), and agents plus full-meta wheel metadata each requires `n3tx-threads`. Full output: `logs/wheel-smoke.stdout`, `.stderr`, `.meta`; reproducible helper: `wheel_smoke.py`.

## Remaining C focused tests (excluding known blocked test_agent_tools)

Exact command from C root:

`PYTHONPATH=<N/packages/{n3tx-core,n3tx-actors,n3tx-threads,n3tx-agents,n3tx-ui,n3tx-files,n3tx}/src>:C PYTHONDONTWRITEBYTECODE=1 N3TX_DEBUG=false N3TX_API_URL=https://neuralys.cloud C/.venv/bin/python -m pytest -p no:cacheprovider -q -ra --tb=short tests/test_agent_backend.py tests/test_query_offset_bounds.py tests/test_base_actor_model.py`

Exit 1 after 201.12s: **21 passed, 4 failed, 64 errors, 0 skips, 18 warnings**. Full output/tracebacks and all error identifiers are preserved in `logs/c-consumer-no-tools.stdout` and `.stderr`; command/environment/status in `.meta`.

Assertion failures (all in `tests/test_agent_backend.py`):
- `test_typed_history_counts_exclude_observation_records`: `assert total > result.message_count`; observed `3 > 3` false.
- `test_viewer_updates_display_native_protocol_notes_and_activity`: response differs from expected legacy rendered activity; actual response includes serialized protocol activity payload.
- `test_viewer_updates_keep_native_refs_unhydrated_and_external_urls_text`: response differs from expected legacy shape/content; see full assertion diff in log.
- `test_viewer_updates_filter_unknown_payloads_without_inventing_answers`: response differs from expected legacy filtering/order/content; full diff in log.

The 64 setup errors all fail in the shared `seeded` fixture while creating an Email without required owner; underlying exception is `n3tx_core.utils.erroring.MethodError: email_owner_required` from `core/models/email.py` via `core/mail_persistence.py:checked_owner`. Full test IDs and representative complete traces are in the log. These were not repaired or bypassed.

The earlier four-file command including `tests/test_agent_tools.py` remains blocked at collection by `ImportError: cannot import name 'AgentThreadAccess' from core.actors.agent_tools`; per caller guidance this is the preexisting removed-policy/source-import contract and was not changed. Its previous logs remain at the parent `final/c-consumer.*` evidence.

## Corrected style and syntax accounting

Ran exact helper command:

`PYTHONDONTWRITEBYTECODE=1 /workspace/.venv-agents/bin/python <N>/.project/verification/n3tx-threads/packaging/style_check.py`

Exit 0. The helper source contains the complete exact file list: **19 changed test paths and the original 23 runtime paths** (`style_check.py`). It checks AST parsing and `<=80` columns for both groups, plus module docstrings and every class/function/async-function docstring, including private definitions, for both groups. Results: 0 AST errors; 0 over-80 lines; 0 missing docs. Full stdout/stderr/status: `logs/style-check.stdout`, `.stderr`, `.meta`.

No framework-wide suites were rerun; the previous focused N suite evidence totals 42 passing cases (28 threads + 14 selected agents). C migrated-test collection evidence remains a collection-only result, not test execution.


Artifact closure and scoped staged/unstaged whitespace follow-up is documented in [artifact-closure-supplement.md](artifact-closure-supplement.md); all wheel members and command outputs are preserved in `logs/`.
