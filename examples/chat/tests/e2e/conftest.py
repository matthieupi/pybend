"""E2E test fixtures — spins up a real HTTP server for Playwright tests.

Session-scoped: one server per pytest session, torn down at the end.
Uses N3TX_TEST_MODE=1 so the server uses pydantic-ai TestModel (no real LLM).
"""
import os
import sys
import shutil
import tempfile
import pytest

_WORKSPACE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
_APP_DIR = os.path.join(_WORKSPACE, 'examples', 'chat')

# Make the shared helpers importable
sys.path.insert(0, os.path.join(_WORKSPACE, 'tests'))
from e2e_helpers import find_free_port, wait_for_server, start_server, run_seed, stop_server


def _start_chat_server(app_dir, port, db_path, log_path=None):
    """Start the chat server with test mode enabled."""
    import subprocess
    env = {
        **os.environ,
        "N3TX_HOST": "127.0.0.1",
        "N3TX_PORT": str(port),
        "N3TX_SQLITE_DB": db_path,
        "N3TX_TEST_MODE": "1",
        "GENERATE_DOCS": "false",
        "PYTHONPATH": os.path.join(_WORKSPACE, "src"),
    }
    stdout_target = open(log_path, 'w') if log_path else subprocess.PIPE
    proc = subprocess.Popen(
        [sys.executable, "main.py"],
        cwd=app_dir,
        env=env,
        stdout=stdout_target,
        stderr=subprocess.STDOUT,
    )
    proc._log_file = stdout_target if log_path else None
    return proc


@pytest.fixture(scope="session")
def e2e_server():
    """Start a real chat server subprocess with a fresh temp DB."""
    port = find_free_port()
    tmp_dir = tempfile.mkdtemp(prefix="e2e_chat_")
    db_path = os.path.join(tmp_dir, "test_e2e.db")
    base_url = f"http://127.0.0.1:{port}"

    # Seed the temp DB
    run_seed(_APP_DIR, db_path)

    # Start the server with test mode (TestModel instead of real LLM)
    log_path = os.path.join(tmp_dir, "server.log")
    proc = _start_chat_server(_APP_DIR, port, db_path, log_path=log_path)
    try:
        # Wait for server to be ready (Conversation schema endpoint)
        wait_for_server(f"{base_url}/Conversation", timeout=30)
    except Exception:
        # Dump server output for debugging
        stop_server(proc)
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise

    yield base_url

    stop_server(proc)
    if proc._log_file:
        proc._log_file.close()
    # Print server log for debugging if tests failed
    if os.path.exists(log_path):
        with open(log_path) as f:
            log_content = f.read()
        if log_content:
            print(f"\n=== SERVER LOG ===\n{log_content[-3000:]}\n=== END SERVER LOG ===")
    shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.fixture(scope="session")
def browser(e2e_server):
    """Shared browser instance — one per session."""
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    b = pw.chromium.launch(headless=True)
    yield b
    b.close()
    pw.stop()


@pytest.fixture
def page(browser):
    """Fresh browser page per test — clean state.

    Navigates to about:blank before closing to ensure WebSocket connections
    are properly torn down (Socket.js auto-reconnect + heartbeat intervals).
    """
    ctx = browser.new_context()
    p = ctx.new_page()
    yield p
    # Navigate away to tear down all JS context (WS connections, intervals)
    try:
        p.goto("about:blank", timeout=5000)
    except Exception:
        pass
    p.close()
    ctx.close()
