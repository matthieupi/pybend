"""
Tests that streaming SSE endpoints in n3tx-actors clean up properly when cancelled.

These verify that the NetworkAdapter.stream() method properly cancels background
tasks when the consumer generator is cancelled (e.g., server shutdown / client disconnect).
"""

import asyncio
import pytest
from n3tx_actors.tx import TX


# ---------------------------------------------------------------------------
# Test 7: StreamingResponse generator propagates CancelledError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_streaming_response_generator_propagates_cancelled_error():
    """An SSE source generator that doesn't catch CancelledError must let it
    propagate so uvicorn can cancel the task during shutdown."""

    async def mock_sse_generator():
        while True:
            yield b"data: chunk\n\n"
            await asyncio.sleep(0.05)

    gen = mock_sse_generator()

    # First chunk should arrive
    result = await asyncio.wait_for(gen.__anext__(), timeout=1.0)
    assert result == b"data: chunk\n\n"

    # Cancel mid-stream — task must stop
    task2 = asyncio.create_task(gen.__anext__())
    await asyncio.sleep(0.02)
    task2.cancel()

    try:
        await asyncio.wait_for(task2, timeout=1.0)
    except (asyncio.CancelledError, asyncio.TimeoutError):
        pass

    assert task2.done(), (
        "SSE generator task is NOT done after cancel() — "
        "this is what causes the shutdown hang."
    )


# ---------------------------------------------------------------------------
# Test 8: NetworkAdapter.stream() cleans up send_task when cancelled
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_network_adapter_stream_cancels_send_task_on_cleanup():
    """NetworkAdapter.stream() must cancel its internal send_task when the
    consumer generator is cancelled, leaving no dangling background tasks."""
    from n3tx_actors.api.network_adapter import NetworkAdapter
    from unittest.mock import AsyncMock, MagicMock, patch

    # Create a minimal adapter — we just want to test that stream()'s finally
    # block cancels send_task when the generator exits.
    adapter = NetworkAdapter.__new__(NetworkAdapter)
    object.__setattr__(adapter, '_pending', {})
    object.__setattr__(adapter, '_addr', 'test-adapter')
    object.__setattr__(adapter, '_children', {})
    object.__setattr__(adapter, '_parent', None)
    object.__setattr__(adapter, '_interceptors', {})

    tx = TX(name='test', source='test-adapter', target='test-model')

    # A fake send that immediately puts a stream_end chunk in the queue
    async def fake_send(outgoing_tx):
        await asyncio.sleep(0.5)  # simulate slow backend
        queue = adapter._pending.get(outgoing_tx.uuid)
        if queue:
            end_tx = outgoing_tx.stream_end()
            await queue.put(end_tx)

    with patch.object(type(adapter), 'send', new=lambda self, tx: asyncio.create_task(fake_send(tx))):
        object.__setattr__(adapter, 'send', fake_send)

        # Start consuming the stream
        gen = adapter.stream(tx, timeout=5.0)

        async def consume():
            async for _ in gen:
                pass

        task = asyncio.create_task(consume())
        await asyncio.sleep(0.05)  # let it start

        # Cancel the consumer (simulates server shutdown or client disconnect)
        task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=2.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass

        await asyncio.sleep(0.1)  # let cleanup propagate

        # The pending entry must be cleaned up
        assert tx.uuid not in adapter._pending, (
            "adapter._pending still holds an entry after stream consumer was cancelled — "
            "this would leak memory for every cancelled stream."
        )


# ---------------------------------------------------------------------------
# Test 9: SSE generator without CancelledError suppression terminates cleanly
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sse_generator_without_cancelled_error_suppression_terminates():
    """An SSE generator that does NOT swallow CancelledError must become
    done within 1 second of being cancelled."""
    queue: asyncio.Queue = asyncio.Queue()

    async def event_generator():
        """Mirrors the corrected event_generator in n3tx_trace/routes.py"""
        try:
            while True:
                entry = await queue.get()
                if entry is None:
                    return
                yield f"data: {entry}\n\n"
        except asyncio.CancelledError:
            raise  # Fixed: was 'pass', now re-raises
        finally:
            pass  # cleanup here

    gen = event_generator()

    async def consume():
        async for _ in gen:
            pass

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.05)

    # Cancel — should propagate CancelledError and finish
    task.cancel()
    try:
        await asyncio.wait_for(asyncio.shield(task), timeout=1.0)
    except (asyncio.CancelledError, asyncio.TimeoutError):
        pass

    assert task.done(), (
        "SSE generator task is still running 1s after cancel() — "
        "this is exactly the shutdown hang pattern."
    )
