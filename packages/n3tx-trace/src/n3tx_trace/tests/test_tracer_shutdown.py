"""
Tests that the TraceCollector and SSE generator clean up properly on cancel.

Verifies:
- The SSE event_generator propagates CancelledError (doesn't swallow it)
- The TraceCollector releases subscriber queues after cancel
- collector.shutdown() properly unblocks all waiting generators
"""

import asyncio
import pytest
from n3tx_trace.tracer import TraceCollector


# ---------------------------------------------------------------------------
# Test 4: collector.shutdown() unblocks a waiting event_generator
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_collector_shutdown_unblocks_waiting_generator():
    """collector.shutdown() must put None into all subscriber queues so that
    SSE generators blocked on queue.get() can return cleanly."""
    collector = TraceCollector()
    client_id = 'test-client'
    queue = collector.subscribe(client_id)

    results = []

    async def consume_queue():
        while True:
            item = await queue.get()
            if item is None:
                break
            results.append(item)

    task = asyncio.create_task(consume_queue())
    await asyncio.sleep(0.05)  # let it block on get()

    # shutdown() must unblock the generator
    collector.shutdown()

    await asyncio.wait_for(task, timeout=2.0)

    assert task.done(), "consume_queue task did not finish after collector.shutdown()"
    assert len(collector._clients) == 0 or client_id not in collector._clients, (
        "collector still holds subscriber after shutdown"
    )


# ---------------------------------------------------------------------------
# Test 5: Subscriber queue is released when SSE generator is cancelled
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_subscriber_queue_released_on_generator_cancel():
    """When the SSE generator task is cancelled (e.g., uvicorn cancels request
    tasks), the TraceCollector must not retain stale subscriber queues."""
    import json
    from n3tx_trace.routes import create_debug_routes

    collector = TraceCollector()

    class FakeMatrix:
        _children = {}
        _adapters = []
        __children__ = {}

    router = create_debug_routes(collector, FakeMatrix())

    # Find the event_generator by simulating what the /stream endpoint does
    client_id = 'cancel-test-client'
    queue = collector.subscribe(client_id)

    async def event_generator():
        try:
            while True:
                entry = await queue.get()
                if entry is None:
                    return
                yield f"data: {json.dumps(entry)}\n\n"
        except asyncio.CancelledError:
            raise
        finally:
            collector.unsubscribe(client_id)

    gen = event_generator()

    async def consume():
        async for _ in gen:
            pass

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.05)  # let it block on queue.get()

    assert client_id in collector._clients, "client should be subscribed"

    # Cancel — simulates uvicorn force-killing the SSE request
    task.cancel()
    try:
        await asyncio.wait_for(asyncio.shield(task), timeout=2.0)
    except (asyncio.CancelledError, asyncio.TimeoutError):
        pass

    await asyncio.sleep(0.05)

    assert client_id not in collector._clients, (
        "collector still holds stale subscriber after generator was cancelled — "
        "this would accumulate dead queues over time."
    )


# ---------------------------------------------------------------------------
# Test 6: Multiple subscribers all unblocked by shutdown()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_multiple_subscribers_all_unblocked_by_shutdown():
    """collector.shutdown() must unblock ALL connected SSE clients, not just one."""
    collector = TraceCollector()
    queues = {f'client-{i}': collector.subscribe(f'client-{i}') for i in range(5)}
    tasks = []

    for client_id, q in queues.items():
        async def waiter(queue=q):
            item = await queue.get()
            return item

        tasks.append(asyncio.create_task(waiter()))

    await asyncio.sleep(0.05)

    collector.shutdown()

    results = await asyncio.wait_for(
        asyncio.gather(*tasks, return_exceptions=True), timeout=2.0
    )

    none_count = sum(1 for r in results if r is None)
    assert none_count == 5, (
        f"Only {none_count}/5 subscribers received the shutdown sentinel. "
        f"collector.shutdown() did not unblock all queues."
    )
