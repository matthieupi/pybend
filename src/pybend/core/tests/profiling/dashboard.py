"""
Profiling dashboard — web UI to run profiling, view results, and compare runs.

Usage:
    python -m pybend.core.tests.profiling.dashboard
    # Opens http://localhost:5555
"""
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

WORKSPACE = Path(__file__).resolve().parents[5]
PROFILING_DIR = WORKSPACE / '.profiling'
HISTORY_FILE = PROFILING_DIR / 'profiling_history.jsonl'
DASHBOARD_HTML = Path(__file__).parent / 'dashboard.html'

app = FastAPI(title="PyBend Profiling Dashboard")

# Track running jobs
_running_jobs = {}


# ── API Routes ──

@app.get('/', response_class=HTMLResponse)
async def index():
    return DASHBOARD_HTML.read_text()


@app.get('/api/history')
async def get_history():
    """Return all historical runs from profiling_history.jsonl."""
    if not HISTORY_FILE.exists():
        return []
    runs = []
    for line in HISTORY_FILE.read_text().strip().split('\n'):
        if line.strip():
            try:
                record = json.loads(line)
                # Return summary only (strip per-operation results for listing)
                runs.append({
                    'label': record['label'],
                    'timestamp': record['timestamp'],
                    'summary': record.get('summary', {}),
                    'tiers': record.get('tiers', []),
                })
            except json.JSONDecodeError:
                continue
    return runs


@app.get('/api/run/{label}')
async def get_run(label: str):
    """Return full results for a specific run label (latest match)."""
    # Try the standalone file first
    standalone = PROFILING_DIR / f'api_perf_{label}.json'
    if standalone.exists():
        return json.loads(standalone.read_text())
    # Fall back to history
    if HISTORY_FILE.exists():
        for line in reversed(HISTORY_FILE.read_text().strip().split('\n')):
            if line.strip():
                try:
                    record = json.loads(line)
                    if record['label'] == label:
                        return record
                except json.JSONDecodeError:
                    continue
    return JSONResponse({'error': f'Run "{label}" not found'}, status_code=404)


@app.get('/api/run-by-index/{index}')
async def get_run_by_index(index: int):
    """Return full results for a run by history index."""
    if not HISTORY_FILE.exists():
        return JSONResponse({'error': 'No history'}, status_code=404)
    lines = [l for l in HISTORY_FILE.read_text().strip().split('\n') if l.strip()]
    if 0 <= index < len(lines):
        return json.loads(lines[index])
    return JSONResponse({'error': 'Index out of range'}, status_code=404)


@app.get('/api/frontend-run/{label}')
async def get_frontend_run(label: str):
    """Return frontend profiling results for a specific run label."""
    path = PROFILING_DIR / f'frontend_perf_{label}.json'
    if not path.exists():
        return JSONResponse({'error': f'Frontend run "{label}" not found'}, status_code=404)
    return json.loads(path.read_text())


@app.get('/api/compare')
async def compare_runs(a: str = Query(...), b: str = Query(...)):
    """Compare two runs by label. Returns structured comparison data."""
    from pybend.core.tests.profiling.compare import compare_json
    file_a = PROFILING_DIR / f'api_perf_{a}.json'
    file_b = PROFILING_DIR / f'api_perf_{b}.json'
    if not file_a.exists():
        return JSONResponse({'error': f'Run "{a}" not found'}, status_code=404)
    if not file_b.exists():
        return JSONResponse({'error': f'Run "{b}" not found'}, status_code=404)
    return compare_json(str(file_a), str(file_b))


SCRIPTS_DIR = WORKSPACE / 'scripts'


@app.post('/api/start')
async def start_run(body: dict):
    """Start a profiling run in the background.

    body.mode: 'all' (default) | 'api' | 'e2e'
    """
    label = body.get('label', 'run')
    mode = body.get('mode', 'all')
    if label in _running_jobs and _running_jobs[label].get('running'):
        return JSONResponse({'error': f'Run "{label}" already in progress'}, status_code=409)

    job = {'running': True, 'label': label, 'mode': mode,
           'started': time.strftime('%H:%M:%S'), 'output': ''}

    def run_profiling():
        try:
            profile_sh = str(SCRIPTS_DIR / 'profile.sh')
            if mode == 'e2e':
                cmd = ['bash', profile_sh, 'e2e', label]
            elif mode == 'api':
                cmd = ['bash', profile_sh, 'api-only', label]
            else:
                # "all" = run API then E2E sequentially via two calls
                cmd = ['bash', '-c', f'bash "{profile_sh}" api-only "{label}" && bash "{profile_sh}" e2e "{label}"']
            env = os.environ.copy()
            env['PYTHONUNBUFFERED'] = '1'
            proc = subprocess.Popen(
                cmd, cwd=str(WORKSPACE), env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
            )
            for line in proc.stdout:
                job['output'] += line
            proc.wait()
            job['exit_code'] = proc.returncode
        except Exception as e:
            job['output'] = str(e)
            job['exit_code'] = 1
        finally:
            job['running'] = False
            job['finished'] = time.strftime('%H:%M:%S')

    _running_jobs[label] = job
    threading.Thread(target=run_profiling, daemon=True).start()
    return {'status': 'started', 'label': label, 'mode': mode}


@app.get('/api/job/{label}')
async def get_job(label: str):
    """Check status of a running profiling job."""
    job = _running_jobs.get(label)
    if not job:
        return JSONResponse({'error': 'No such job'}, status_code=404)
    return job


@app.get('/api/log-labels')
async def get_log_labels():
    """Return available per-run log labels, most recent first."""
    logs = sorted(PROFILING_DIR.glob('perf_run_*.log'), key=lambda p: p.stat().st_mtime, reverse=True)
    return [p.stem.replace('perf_run_', '') for p in logs]


@app.get('/api/logs')
async def get_logs(label: str = None):
    """Return per-run log content. If no label given, return the most recent."""
    if label:
        log_path = PROFILING_DIR / f'perf_run_{label}.log'
    else:
        logs = sorted(PROFILING_DIR.glob('perf_run_*.log'), key=lambda p: p.stat().st_mtime)
        log_path = logs[-1] if logs else None
    if not log_path or not log_path.exists():
        return {'content': '(no logs yet)'}
    return {'label': log_path.stem.replace('perf_run_', ''), 'content': log_path.read_text()[-50000:]}


def main():
    PROFILING_DIR.mkdir(parents=True, exist_ok=True)
    print(f'Profiling dashboard: http://localhost:5555')
    print(f'Reading from: {PROFILING_DIR}')
    uvicorn.run(app, host='0.0.0.0', port=5555, log_level='warning')


if __name__ == '__main__':
    main()
