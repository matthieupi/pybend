"""E2E test fixtures — spins up a real HTTP server for Playwright tests.

Session-scoped: one server per pytest session, torn down at the end.
Each test module's BASE variable is patched to the server's actual URL.
"""
import os
import sys
import shutil
import tempfile
import pytest

_WORKSPACE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_APP_DIR = os.path.join(_WORKSPACE, 'example_actor')

# Make the shared helpers importable
sys.path.insert(0, os.path.join(_WORKSPACE, 'tests'))
from e2e_helpers import find_free_port, wait_for_server, start_server, run_seed, stop_server


@pytest.fixture(scope="session", autouse=True)
def e2e_server(request):
    """Start a real server subprocess with a fresh temp DB."""
    port = find_free_port()
    tmp_dir = tempfile.mkdtemp(prefix="e2e_actor_")
    db_path = os.path.join(tmp_dir, "test_e2e.db")
    base_url = f"http://127.0.0.1:{port}"

    # Seed the temp DB
    run_seed(_APP_DIR, db_path)

    # Start the server
    proc = start_server(_APP_DIR, port, db_path)
    try:
        wait_for_server(f"{base_url}/Product", timeout=30)
    except Exception:
        stop_server(proc)
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise

    # Patch BASE on all collected e2e test modules
    for item in request.session.items:
        mod = item.module
        if hasattr(mod, 'BASE'):
            mod.BASE = base_url

    yield base_url

    stop_server(proc)
    shutil.rmtree(tmp_dir, ignore_errors=True)
