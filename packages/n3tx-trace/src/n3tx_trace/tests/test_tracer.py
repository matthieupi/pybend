"""Tests for tracer.py — TraceCollector + TraceEntry."""

import asyncio
from dataclasses import dataclass

import pytest

from n3tx_trace.tracer import TraceCollector, TraceEntry


@dataclass
class FakeTX:
    """Minimal TX stand-in for testing."""
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


class TestTraceEntry:
    def test_to_dict(self):
        entry = TraceEntry(
            tx_uuid='tx-1', name='READ', source='api', target='products',
            timestamp=1000.0, trace_id='t-1',
        )
        d = entry.to_dict()
        assert d['tx_uuid'] == 'tx-1'
        assert d['name'] == 'READ'
        assert d['is_error'] is False


class TestTraceCollector:
    def test_capture_basic(self):
        collector = TraceCollector(maxlen=10)
        tx = FakeTX()
        entry = collector.capture(tx)
        assert entry.tx_uuid == 'tx-001'
        assert entry.name == 'READ'
        assert entry.source == 'api'
        assert entry.target == 'products'
        assert entry.trace_id == 'trace-1'
        assert len(collector) == 1

    def test_ring_buffer_overflow(self):
        collector = TraceCollector(maxlen=3)
        for i in range(5):
            collector.capture(FakeTX(uuid=f'tx-{i}', name=f'OP-{i}'))
        assert len(collector) == 3
        snap = collector.snapshot()
        assert snap[0]['tx_uuid'] == 'tx-2'
        assert snap[2]['tx_uuid'] == 'tx-4'

    def test_snapshot_returns_dicts(self):
        collector = TraceCollector()
        collector.capture(FakeTX())
        snap = collector.snapshot()
        assert isinstance(snap, list)
        assert isinstance(snap[0], dict)
        assert snap[0]['tx_uuid'] == 'tx-001'

    def test_capture_error_tx(self):
        collector = TraceCollector()
        tx = FakeTX(name='ERROR', is_error=True, meta={'trace_id': 't', 'error': True})
        entry = collector.capture(tx)
        assert entry.is_error is True

    def test_capture_stream_tx(self):
        collector = TraceCollector()
        tx = FakeTX(name='STREAM', meta={'trace_id': 't', 'stream': True, 'seq': 3})
        entry = collector.capture(tx)
        assert entry.is_stream is True
        assert entry.seq == 3

    def test_data_summary_dict(self):
        collector = TraceCollector()
        tx = FakeTX(data={'name': 'test', 'price': 10})
        entry = collector.capture(tx)
        assert 'name' in entry.data_summary
        assert 'price' in entry.data_summary

    def test_clear(self):
        collector = TraceCollector()
        collector.capture(FakeTX())
        collector.clear()
        assert len(collector) == 0

    def test_subscribe_and_fanout(self):
        collector = TraceCollector()
        queue = collector.subscribe('client-1')

        collector.capture(FakeTX(uuid='tx-A'))
        assert not queue.empty()
        entry = queue.get_nowait()
        assert entry['tx_uuid'] == 'tx-A'

    def test_unsubscribe(self):
        collector = TraceCollector()
        collector.subscribe('client-1')
        collector.unsubscribe('client-1')
        # No error, no fan-out
        collector.capture(FakeTX())
        assert len(collector) == 1

    def test_full_queue_drops_client(self):
        collector = TraceCollector()
        queue = collector.subscribe('client-slow')
        # Fill the queue
        for i in range(500):
            collector.capture(FakeTX(uuid=f'tx-{i}'))
        # Next capture should drop the client
        collector.capture(FakeTX(uuid='tx-overflow'))
        assert 'client-slow' not in collector._clients
