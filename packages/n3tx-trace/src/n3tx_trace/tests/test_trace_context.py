"""Tests for trace_context.py — contextvars-based trace_id propagation."""

import asyncio

from n3tx_trace.trace_context import get_trace_id, set_trace_id


def test_default_is_none():
    """Default trace_id should be None."""
    assert get_trace_id() is None


def test_set_and_get():
    """set_trace_id should make the value retrievable via get_trace_id."""
    token = set_trace_id('trace-abc')
    assert get_trace_id() == 'trace-abc'
    token.var.reset(token)
    assert get_trace_id() is None


def test_reset_restores_previous():
    """Resetting a token should restore the previous value."""
    token1 = set_trace_id('first')
    token2 = set_trace_id('second')
    assert get_trace_id() == 'second'
    token2.var.reset(token2)
    assert get_trace_id() == 'first'
    token1.var.reset(token1)
    assert get_trace_id() is None


def test_async_propagation():
    """trace_id should propagate through await chains."""
    results = []

    async def inner():
        results.append(get_trace_id())

    async def outer():
        token = set_trace_id('async-trace')
        await inner()
        token.var.reset(token)

    asyncio.run(outer())
    assert results == ['async-trace']


def test_async_task_copies_context():
    """asyncio.create_task() should copy the current context."""
    results = []

    async def task_fn():
        results.append(get_trace_id())

    async def main():
        token = set_trace_id('task-trace')
        t = asyncio.create_task(task_fn())
        await t
        token.var.reset(token)

    asyncio.run(main())
    assert results == ['task-trace']
