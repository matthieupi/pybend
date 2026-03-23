"""Tests reproducing: GET /debug returns 404 (Not Found).

The bug: in a real N3TXApp with actor routing and a catch-all static
mount at "/", requesting /debug (without trailing slash) returns 404
because the debug submount's inner route "/" doesn't match the empty
remaining path, and the catch-all static mount catches it instead.
"""

import os
import tempfile
from dataclasses import dataclass

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.staticfiles import StaticFiles

from n3tx_trace import enable_tracing
from n3tx_trace.tracer import TraceCollector
from n3tx_trace.routes import create_debug_routes, mount_debug_static


# ── Fakes ──

class FakeMatrix:
    _addr = 'matrix'
    _children = {}
    _adapters = []
    meta = {}

    async def inbox(self, tx):
        pass


class FakeActor:
    __name__ = 'FakeActor'
    _addr = ''
    _children = {}

    def __init__(self, addr):
        self._addr = addr


def _make_app_with_catchall():
    """Build a FastAPI app with debug routes + catch-all static mount
    (simulates the real N3TXApp.build() flow)."""
    collector = TraceCollector()
    matrix = FakeMatrix()
    matrix._children = {'products': FakeActor('products')}

    app = FastAPI()

    # 1. Register debug routes (same as enable_tracing does)
    router = create_debug_routes(collector, matrix)
    app.include_router(router)
    mount_debug_static(app)

    # 2. Add catch-all static mount AFTER debug routes (same as get_app)
    tmpdir = tempfile.mkdtemp()
    with open(os.path.join(tmpdir, 'dummy.js'), 'w') as f:
        f.write('// dummy')
    app.mount("/", StaticFiles(directory=tmpdir), name="static")

    return app, tmpdir


# ── Test 1: /debug without trailing slash + catch-all mount ──

def test_debug_no_trailing_slash_with_catchall():
    """GET /debug (no trailing slash) should NOT return 404 when
    a catch-all static mount exists at /."""
    app, tmpdir = _make_app_with_catchall()
    client = TestClient(app)

    resp = client.get('/debug', follow_redirects=True)
    assert resp.status_code == 200, (
        f"GET /debug returned {resp.status_code}, expected 200. "
        f"Body: {resp.text[:200]}"
    )


# ── Test 2: /debug/ with trailing slash + catch-all mount ──

def test_debug_trailing_slash_with_catchall():
    """GET /debug/ (with trailing slash) should return 200 even
    with a catch-all static mount at /."""
    app, tmpdir = _make_app_with_catchall()
    client = TestClient(app)

    resp = client.get('/debug/')
    assert resp.status_code == 200, (
        f"GET /debug/ returned {resp.status_code}, expected 200. "
        f"Body: {resp.text[:200]}"
    )


# ── Test 3: enable_tracing full flow + catch-all mount ──

def test_enable_tracing_with_catchall_static():
    """Full enable_tracing() + catch-all mount should serve /debug."""
    matrix = FakeMatrix()
    matrix._children = {'products': FakeActor('products')}

    app = FastAPI()
    enable_tracing(app, matrix)

    # Simulate framework catch-all
    tmpdir = tempfile.mkdtemp()
    with open(os.path.join(tmpdir, 'dummy.js'), 'w') as f:
        f.write('// dummy')
    app.mount("/", StaticFiles(directory=tmpdir), name="static")

    client = TestClient(app)
    resp = client.get('/debug', follow_redirects=True)
    assert resp.status_code == 200, (
        f"GET /debug returned {resp.status_code}, expected 200"
    )


# ── Test 4: /debug/topology still works with catch-all ──

def test_debug_topology_with_catchall():
    """GET /debug/topology should return JSON, not 404, when
    a catch-all static mount exists."""
    app, tmpdir = _make_app_with_catchall()
    client = TestClient(app)

    resp = client.get('/debug/topology')
    assert resp.status_code == 200, (
        f"GET /debug/topology returned {resp.status_code}, expected 200"
    )
    data = resp.json()
    assert 'nodes' in data
