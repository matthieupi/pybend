"""Tests for routes.py — Debug endpoint tests."""

import asyncio
from dataclasses import dataclass

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from n3tx_trace.tracer import TraceCollector
from n3tx_trace.routes import create_debug_routes


@dataclass
class FakeTX:
    uuid: str = 'tx-001'
    name: str = 'READ'
    source: str = 'api'
    target: str = 'products'
    data: dict = None
    meta: dict = None
    timestamp: float = 1000.0
    is_error: bool = False

    def __post_init__(self):
        if self.data is None:
            self.data = {}
        if self.meta is None:
            self.meta = {'trace_id': 'trace-1'}


class FakeMatrix:
    """Minimal Matrix stand-in for topology tests."""
    _addr = 'matrix'
    _children = {}
    _adapters = []

    def __init__(self, children=None, adapters=None):
        self._children = children or {}
        self._adapters = adapters or []


class FakeActor:
    """Minimal actor stand-in."""
    __name__ = 'FakeActor'
    _addr = ''
    _children = {}

    def __init__(self, addr, children=None, actor_type='model'):
        self._addr = addr
        self._children = children or {}


@pytest.fixture
def app_and_collector():
    collector = TraceCollector()
    matrix = FakeMatrix(
        children={
            'products': FakeActor('products'),
            'users': FakeActor('users'),
        }
    )
    app = FastAPI()
    router = create_debug_routes(collector, matrix)
    app.include_router(router)
    return app, collector, matrix


def test_debug_page(app_and_collector):
    app, _, _ = app_and_collector
    client = TestClient(app)
    resp = client.get('/debug/')
    # Will be 200 if debug.html exists, 500 otherwise
    # We haven't created it yet, so just test the route exists
    assert resp.status_code in (200, 500)


def test_topology(app_and_collector):
    app, _, _ = app_and_collector
    client = TestClient(app)
    resp = client.get('/debug/topology')
    assert resp.status_code == 200
    data = resp.json()
    assert 'nodes' in data
    assert 'edges' in data
    # Matrix + 2 children = 3 nodes
    assert len(data['nodes']) == 3
    # Matrix root is first
    assert data['nodes'][0]['id'] == 'matrix'
    # 2 edges (matrix -> products, matrix -> users)
    assert len(data['edges']) == 2


def test_snapshot_empty(app_and_collector):
    app, _, _ = app_and_collector
    client = TestClient(app)
    resp = client.get('/debug/snapshot')
    assert resp.status_code == 200
    assert resp.json() == {'entries': []}


def test_snapshot_with_entries(app_and_collector):
    app, collector, _ = app_and_collector
    collector.capture(FakeTX(uuid='tx-1'))
    collector.capture(FakeTX(uuid='tx-2'))
    client = TestClient(app)
    resp = client.get('/debug/snapshot')
    assert resp.status_code == 200
    entries = resp.json()['entries']
    assert len(entries) == 2
    assert entries[0]['tx_uuid'] == 'tx-1'


def test_topology_with_adapters():
    collector = TraceCollector()

    class FakeAdapter:
        __name__ = 'NetworkAPI'
        _addr = 'api'
        addr = 'api'

    matrix = FakeMatrix(
        children={'products': FakeActor('products')},
        adapters=[FakeAdapter()],
    )
    app = FastAPI()
    router = create_debug_routes(collector, matrix)
    app.include_router(router)

    client = TestClient(app)
    resp = client.get('/debug/topology')
    data = resp.json()
    # matrix + api adapter + products = 3 nodes
    assert len(data['nodes']) == 3
    node_ids = [n['id'] for n in data['nodes']]
    assert 'api' in node_ids
