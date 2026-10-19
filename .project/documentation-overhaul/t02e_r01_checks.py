"""Persist exact R01 check output without editing the permanent test suite."""
import json
from pathlib import Path
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
PYTHON = '/workspace/.venv-agents/bin/python'
checks = [
    ('extracted-http-browser', ROOT, [PYTHON, str(OUT / 't02e_browser.py')]),
    ('tutorial-http', ROOT, [PYTHON, str(OUT / 'verify_tutorial.py')]),
    ('native-create', ROOT / 'tests/frontend', ['npx', 'vitest', 'run', '--config',
      str(OUT / 't02e-native-create.config.mjs'), '--maxWorkers=2', '--minWorkers=1']),
    ('frontend-suite', ROOT / 'tests/frontend', ['npm', 'test', '--', '--maxWorkers=2', '--minWorkers=1']),
]
results = []
for name, cwd, command in checks:
    result = subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=240)
    (OUT / f't02e-r01-{name}.log').write_text(result.stdout)
    results.append({'check': name, 'command': command, 'cwd': str(cwd), 'exit_code': result.returncode})
    print(name, 'exit', result.returncode, flush=True)
(OUT / 't02e-r01-checks.json').write_text(json.dumps(results, indent=2))
