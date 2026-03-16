"""
API workload runner for profiling.

Runs an API workload at each data tier (empty -> small -> medium -> full)
to measure how performance scales with data volume.

Usage:
    python -m n3tx.core.tests.profiling.run_profile <label>
    python -m n3tx.core.tests.profiling.run_profile baseline
    python -m n3tx.core.tests.profiling.run_profile optimized
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import requests

from n3tx_core.tests.profiling.seed_perf import tier_record_count

WORKSPACE = Path(__file__).resolve().parents[5]
EXAMPLE_DIR = WORKSPACE / 'src' / 'n3tx' / 'example'
SEED_SCRIPT = Path(__file__).resolve().parent / 'seed_perf.py'
PROFILING_DIR = WORKSPACE / '.traces' / '.profiling'
PROFILING_PORT = 5099
SERVER_URL = f'http://localhost:{PROFILING_PORT}'
TIERS = ['empty', 'small', 'medium', 'large', 'full']


def wait_for_server(url=SERVER_URL, timeout=30):
    """Wait until the server responds to a health check."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(f'{url}/Product', timeout=2)
            if r.status_code in (200, 401, 403):
                return True
        except requests.ConnectionError:
            pass
        time.sleep(0.3)
    return False


def start_server(db_path, label='run'):
    """Start the N3TX server on an isolated port with a dedicated DB."""
    env = os.environ.copy()
    env['N3TX_PROFILING'] = '1'
    env['N3TX_SQLITE_DB'] = str(db_path)
    env['N3TX_PROFILING_DIR'] = str(PROFILING_DIR)
    env['N3TX_PORT'] = str(PROFILING_PORT)
    env['N3TX_PROFILING_LABEL'] = label
    proc = subprocess.Popen(
        [sys.executable, 'main.py'],
        cwd=str(EXAMPLE_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if not wait_for_server():
        # Capture server output for diagnostics
        proc.terminate()
        stdout, stderr = proc.communicate(timeout=5)
        diag = stderr.decode(errors='replace')[-2000:] or stdout.decode(errors='replace')[-2000:]
        raise RuntimeError(
            f'Server failed to start on port {PROFILING_PORT} within timeout.\n'
            f'DB: {db_path}\n'
            f'Server output:\n{diag}'
        )
    return proc


def stop_server(proc):
    """Gracefully stop the server."""
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def seed_db(db_path, tier):
    """Seed the database at the given tier."""
    if os.path.exists(db_path):
        os.remove(db_path)
    env = os.environ.copy()
    env['N3TX_SQLITE_DB'] = str(db_path)
    subprocess.run(
        [sys.executable, str(SEED_SCRIPT), '--reset', '--tier', tier],
        env=env,
        check=True,
        capture_output=True,
    )


def timed_request(method, url, **kwargs):
    """Make a request and return (response, duration_ms)."""
    start = time.perf_counter()
    resp = getattr(requests, method)(url, **kwargs)
    elapsed = (time.perf_counter() - start) * 1000
    return resp, elapsed


def login(email='alice@example.com', password='alice123'):
    """Login and return JWT token."""
    resp, _ = timed_request('post', f'{SERVER_URL}/users/login', json={
        'email': email, 'password': password,
    })
    if resp.status_code == 200:
        return resp.json().get('token')
    return None


def run_workload(tier, token=None):
    """Run the API workload and return timing results."""
    headers = {'x-access-token': token} if token else {}
    results = []

    def record(name, method, url, expect_status=200, **kwargs):
        resp, ms = timed_request(method, url, **kwargs)
        status = resp.status_code
        ok = status == expect_status
        if not ok:
            print(f'    !! {name}: expected {expect_status}, got {status} ({method.upper()} {url.replace(SERVER_URL, "")})')
        results.append({
            'name': name,
            'tier': tier,
            'method': method.upper(),
            'url': url.replace(SERVER_URL, ''),
            'status': status,
            'duration_ms': round(ms, 2),
            'error': not ok,
        })
        return resp

    # Schema fetches (cold + warm) — only top-level models
    # Child models (Comment, Like) are embedded in parent $defs, no standalone route.
    for model in ['Product', 'User']:
        record(f'schema_{model}_cold', 'get', f'{SERVER_URL}/{model}')
        record(f'schema_{model}_warm', 'get', f'{SERVER_URL}/{model}')
        record(f'schema_{model}_warm2', 'get', f'{SERVER_URL}/{model}')

    # List endpoints at each populate depth (matches frontend behavior)
    # depth=0: href arrays only (no eager loading)
    # depth=1: default frontend behavior (ListElement sends depth=1)
    # depth=2: deep populate (nested children)
    for depth in [0, 1, 2]:
        for limit in [10, 25]:
            record(f'list_products_d{depth}_limit_{limit}', 'get',
                   f'{SERVER_URL}/products?limit={limit}&depth={depth}', headers=headers)

    # Full collection fetch (no depth — baseline)
    record('list_products_all', 'get',
           f'{SERVER_URL}/products?limit=100', headers=headers)

    # User list
    record('list_users', 'get', f'{SERVER_URL}/users', headers=headers)

    # Individual product fetches at each depth (auth required for read)
    if token:
        for depth in [0, 1, 2]:
            for pid in range(1, 4):
                record(f'get_product_{pid}_d{depth}', 'get',
                       f'{SERVER_URL}/products/{pid}?depth={depth}', headers=headers)

    # Individual user fetch
    if token:
        record('get_user_1', 'get', f'{SERVER_URL}/users/1', headers=headers)

    # Child collections: comments on products
    if token:
        for pid in [1, 2]:
            record(f'get_product_{pid}_comments', 'get',
                   f'{SERVER_URL}/products/{pid}/comments', headers=headers)

    # Child collections: favorites on products
    if token:
        for pid in [1, 2]:
            record(f'get_product_{pid}_favorites', 'get',
                   f'{SERVER_URL}/products/{pid}/favorites', headers=headers)

    # Login (bcrypt + JWT)
    if tier != 'empty':
        record('login', 'post', f'{SERVER_URL}/users/login', json={
            'email': 'alice@example.com', 'password': 'alice123',
        })

    # Write operations (only if we have auth and data)
    if token and tier != 'empty':
        # Multiple product creates
        for i in range(3):
            record(f'create_product_{i+1}', 'post', f'{SERVER_URL}/products',
                   expect_status=201, headers=headers, json={
                       'name': f'Perf Test Product {i+1} ({tier})',
                       'price': 49.99 + i * 10,
                       'description': f'Created during profiling run #{i+1}',
                   })

        # Comments on different products
        for pid in [1, 2]:
            record(f'comment_on_product_{pid}', 'post',
                   f'{SERVER_URL}/products/{pid}/comment',
                   headers=headers, json={
                       'comment': {
                           'name': f'Perf comment on p{pid} ({tier})',
                           'description': 'Test comment from profiling',
                       },
                   })

        # Favorite multiple products
        for pid in [1, 2, 3]:
            record(f'favorite_product_{pid}', 'post',
                   f'{SERVER_URL}/products/{pid}/favorite', headers=headers)

    return results


def run_tier(label, tier, db_path):
    """Seed, start server, run workload, stop server for a single tier."""
    print(f'\n  [{tier}] Seeding database...')
    seed_db(db_path, tier)

    print(f'  [{tier}] Starting server...')
    proc = start_server(db_path, label=label)

    try:
        token = None
        if tier != 'empty':
            token = login()

        print(f'  [{tier}] Running workload...')
        results = run_workload(tier, token)
        return results
    finally:
        stop_server(proc)


def build_summary(label, all_results):
    """Build summary stats for the run."""
    tier_summaries = {}
    for tier in TIERS:
        tier_results = [r for r in all_results if r['tier'] == tier]
        if tier_results:
            total = sum(r['duration_ms'] for r in tier_results)
            errors = sum(1 for r in tier_results if r.get('error'))
            tier_summaries[tier] = {
                'ops': len(tier_results),
                'total_ms': round(total, 2),
                'avg_ms': round(total / len(tier_results), 2),
                'db_records': tier_record_count(tier),
                'errors': errors,
            }
    grand_total = sum(s['total_ms'] for s in tier_summaries.values())
    grand_ops = sum(s['ops'] for s in tier_summaries.values())
    grand_errors = sum(s['errors'] for s in tier_summaries.values())
    return {
        'grand_total_ms': round(grand_total, 2),
        'grand_ops': grand_ops,
        'grand_errors': grand_errors,
        'tiers': tier_summaries,
    }


def main():
    if len(sys.argv) < 2:
        print('Usage: python -m n3tx.core.tests.profiling.run_profile <label>')
        print('  label: e.g. "baseline" or "optimized"')
        sys.exit(1)

    label = sys.argv[1]
    PROFILING_DIR.mkdir(parents=True, exist_ok=True)
    db_path = PROFILING_DIR / f'perf_{label}.db'

    all_results = []
    print(f'=== Profiling run: {label} ===')
    print(f'Running workload at each data tier: {TIERS}')

    for tier in TIERS:
        results = run_tier(label, tier, db_path)
        all_results.extend(results)

    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    summary = build_summary(label, all_results)

    # Build the full run record
    run_record = {
        'label': label,
        'timestamp': timestamp,
        'tiers': TIERS,
        'summary': summary,
        'results': all_results,
    }

    # Write the latest run as a standalone JSON (overwritten each time)
    output_path = PROFILING_DIR / f'api_perf_{label}.json'
    with open(output_path, 'w') as f:
        json.dump(run_record, f, indent=2)
    print(f'\nResults written to {output_path}')

    # Append to history (one JSON line per run)
    history_path = PROFILING_DIR / 'profiling_history.jsonl'
    with open(history_path, 'a') as f:
        f.write(json.dumps(run_record) + '\n')
    print(f'Run appended to {history_path}')

    # Write human-readable log file: summary table first, then per-tier details
    log_path = PROFILING_DIR / f'perf_run_{label}.log'
    with open(log_path, 'a') as f:
        f.write(f'{"#" * 72}\n')
        f.write(f'# API Profiling: {label}\n')
        f.write(f'# {timestamp}\n')
        f.write(f'{"#" * 72}\n\n')

        # Summary table at the top
        f.write(f'{"Tier":<10} {"Records":>8} {"Ops":<6} {"Errors":<7} {"Total ms":>12} {"Avg ms":>10}\n')
        f.write(f'{"-" * 55}\n')
        for tier in TIERS:
            s = summary['tiers'].get(tier)
            if s:
                err_str = str(s['errors']) if s['errors'] else '-'
                f.write(f'{tier:<10} {s["db_records"]:>8} {s["ops"]:<6} {err_str:<7} {s["total_ms"]:>12.1f} {s["avg_ms"]:>10.1f}\n')
        f.write(f'{"-" * 55}\n')
        f.write(f'{"TOTAL":<10} {"":>8} {summary["grand_ops"]:<6} {summary["grand_errors"] or "-":<7} {summary["grand_total_ms"]:>12.1f}\n')
        if summary['grand_errors'] > 0:
            f.write(f'\n  !! {summary["grand_errors"]} operation(s) returned unexpected status codes\n')
        f.write('\n')

        # Per-tier operation details
        for tier in TIERS:
            tier_results = [r for r in all_results if r['tier'] == tier]
            if not tier_results:
                continue
            records = tier_record_count(tier)
            f.write(f'--- Tier: {tier} ({len(tier_results)} operations, {records} records) ---\n')
            f.write(f'{"Operation":<40} {"Method":<6} {"Status":<6} {"ms":>10}\n')
            f.write(f'{"-" * 64}\n')
            for r in tier_results:
                flag = ' !! ERROR' if r.get('error') else ''
                f.write(f'{r["name"]:<40} {r["method"]:<6} {r["status"]:<6} {r["duration_ms"]:>10.2f}{flag}\n')
            total_ms = sum(r['duration_ms'] for r in tier_results)
            f.write(f'{"-" * 64}\n')
            f.write(f'{"TOTAL":<40} {"":6} {"":6} {total_ms:>10.2f}\n\n')

    print(f'Log written to {log_path}')

    # Print quick summary to stdout
    print(f'\n{"Tier":<10} {"Records":>8} {"Ops":<6} {"Errors":<7} {"Total ms":>12} {"Avg ms":>10}')
    print(f'{"-" * 55}')
    for tier in TIERS:
        s = summary['tiers'].get(tier)
        if s:
            err_str = str(s['errors']) if s['errors'] else '-'
            print(f'{tier:<10} {s["db_records"]:>8} {s["ops"]:<6} {err_str:<7} {s["total_ms"]:>12.1f} {s["avg_ms"]:>10.1f}')

    if summary['grand_errors'] > 0:
        print(f'\n  !! {summary["grand_errors"]} operation(s) returned unexpected status codes — check logs for details')

    # Clean up temp DB
    if db_path.exists():
        os.remove(db_path)


if __name__ == '__main__':
    main()
