"""AST, 80-column and documentation audit for the assigned changed files."""
import ast
import pathlib

N = pathlib.Path('/workspace/neuralys/collagen/lib/n3tx')
C = pathlib.Path('/workspace/neuralys/collagen')
tests = [
'N/packages/n3tx-threads/src/n3tx_threads/tests/__init__.py',
'N/packages/n3tx-threads/src/n3tx_threads/tests/conftest.py',
'N/packages/n3tx-threads/src/n3tx_threads/tests/test_thread.py',
'N/packages/n3tx-threads/src/n3tx_threads/tests/test_notes_mixin.py',
'N/packages/n3tx-threads/src/n3tx_threads/tests/test_standalone.py',
'N/packages/n3tx-agents/src/n3tx_agents/tests/conftest.py',
'N/packages/n3tx-agents/src/n3tx_agents/tests/test_thread.py',
'N/packages/n3tx-agents/src/n3tx_agents/tests/test_notes_mixin.py',
'C/tests/test_agent_backend.py',
'C/tests/test_agent_execution.py',
'C/tests/test_agent_tools.py',
'C/tests/test_base_actor_model.py',
'C/tests/test_hr_backend.py',
'C/tests/test_hr_processing.py',
'C/tests/test_organization_research.py',
'C/tests/test_api_ai.py',
'C/tests/test_permissions.py',
'C/tests/test_query_offset_bounds.py',
'C/tests/playground/runtime_probe.py',
]
runtime = [
'N/packages/n3tx-threads/src/n3tx_threads/__init__.py',
'N/packages/n3tx-threads/src/n3tx_threads/thread.py',
'N/packages/n3tx-threads/src/n3tx_threads/threaded_mixin.py',
'N/packages/n3tx-threads/src/n3tx_threads/notes_mixin.py',
'N/packages/n3tx-threads/src/n3tx_threads/tx_record.py',
'N/packages/n3tx-agents/src/n3tx_agents/agent.py',
'N/packages/n3tx-agents/src/n3tx_agents/history.py',
'N/packages/n3tx-agents/src/n3tx_agents/__init__.py',
'N/packages/n3tx-core/src/n3tx_core/app.py',
'N/packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py',
'N/apps/veille/main.py',
'N/scripts/test-backend.py',
'N/packages/n3tx/src/n3tx_meta/__init__.py',
'C/core/native_models.py',
'C/core/app.py',
'C/core/agents/backend.py',
'C/core/agents/history.py',
'C/core/agents/runtime.py',
'C/core/actors/agent_tools.py',
'C/core/models/email.py',
'C/apps/hr/models/resume.py',
'C/n3tx_ext/playground/policy.py',
'C/scripts/live_agent_check.py',
]
errors, over80, missing_docs = [], [], []
for group, entries in [('test', tests), ('runtime', runtime)]:
    for entry in entries:
        path = N / entry[2:] if entry.startswith('N/') else C / entry[2:]
        try:
            source = path.read_text()
            tree = ast.parse(source, filename=str(path))
        except Exception as exc:
            errors.append(f'{group} {path}: {type(exc).__name__}: {exc}')
            continue
        for line_no, line in enumerate(source.splitlines(), 1):
            if len(line) > 80:
                over80.append(f'{group} {path}:{line_no}: {len(line)} columns')
        if ast.get_docstring(tree) is None:
            missing_docs.append(f'{group} {path}: missing module docstring')
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and ast.get_docstring(node) is None:
                missing_docs.append(f'{group} {path}:{node.lineno}: {node.name} missing docstring')
print(f'files: tests={len(tests)}, runtime={len(runtime)}')
print(f'AST parse errors: {len(errors)}')
print(f'lines >80 columns across both groups: {len(over80)}')
print(f'missing module/class/function docstrings across both groups: {len(missing_docs)}')
for item in errors + over80 + missing_docs:
    print('FINDING:', item)
if errors or over80 or missing_docs:
    raise SystemExit(1)
