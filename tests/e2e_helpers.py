"""Shared helpers for e2e Playwright tests — server lifecycle management.

Each example app's tests/e2e/conftest.py uses these to spin up a real HTTP
server subprocess with a fresh temp database, so e2e tests are fully isolated
and don't require a manually started server.
"""
import os
import socket
import subprocess
import sys
import time
import urllib.request
import urllib.error

_WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_free_port():
    """Bind to port 0 and let the OS pick an available port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for_server(url, timeout=30):
    """Poll *url* until it returns a 200, or raise after *timeout* seconds."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            resp = urllib.request.urlopen(url, timeout=2)
            if resp.status == 200:
                return
        except (urllib.error.URLError, ConnectionError, OSError):
            pass
        time.sleep(0.3)
    raise RuntimeError(f"Server at {url} did not become ready within {timeout}s")


def start_server(app_dir, port, db_path):
    """Start ``python main.py`` in *app_dir* as a subprocess.

    Environment variables control the port and database path so the server
    uses a fresh temp DB on a random port.
    """
    env = {
        **os.environ,
        "N3TX_HOST": "127.0.0.1",
        "N3TX_PORT": str(port),
        "N3TX_SQLITE_DB": db_path,
        "GENERATE_DOCS": "false",
        "PYTHONPATH": os.path.join(_WORKSPACE, "src"),
    }
    proc = subprocess.Popen(
        [sys.executable, "main.py"],
        cwd=app_dir,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return proc


def run_seed(app_dir, db_path):
    """Run ``seed.py --reset`` in *app_dir* with the given DB path."""
    env = {
        **os.environ,
        "N3TX_SQLITE_DB": db_path,
        "PYTHONPATH": os.path.join(_WORKSPACE, "src"),
    }
    result = subprocess.run(
        [sys.executable, "seed.py", "--reset"],
        cwd=app_dir,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"seed.py failed (rc={result.returncode}):\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


def stop_server(proc):
    """Terminate the server process, with a hard-kill fallback."""
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=3)
