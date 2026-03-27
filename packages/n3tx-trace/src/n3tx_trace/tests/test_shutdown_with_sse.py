"""
Tests that the server shuts down cleanly (within a timeout) when:
- An active SSE stream connection is open (TX inspector /debug/stream)

Reproduces bug: `ctrl+c` hangs when TX inspector tab is open.
Root cause: collector.shutdown() was registered via @app.on_event('shutdown')
which fires AFTER uvicorn drains connections — but the SSE connection can't
close until collector.shutdown() unblocks its queue.  Fix: register a signal
handler at startup that fires collector.shutdown() immediately on SIGINT/SIGTERM.
"""

import signal
import subprocess
import sys
import time
import threading
import pytest
import httpx

# ---------------------------------------------------------------------------
# Shared server startup helper (uses n3tx-trace enable_tracing)
# ---------------------------------------------------------------------------

_SERVER_CODE = """
import asyncio
import uvicorn
from fastapi import FastAPI
from n3tx_trace import enable_tracing
from n3tx_trace.tracer import TraceCollector

class FakeMatrix:
    _children = {}
    _adapters = []
    _addr = 'matrix'
    __children__ = {}

    async def inbox(self, tx):
        pass

app = FastAPI()
matrix = FakeMatrix()
enable_tracing(app, matrix)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=PORT)
"""


def _start_trace_server(port):
    """Start a FastAPI server with enable_tracing on the given port."""
    code = _SERVER_CODE.replace("port=PORT", f"port={port}")
    proc = subprocess.Popen(
        [sys.executable, "-c", code],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # Wait until the server is accepting connections
    deadline = time.time() + 8
    while time.time() < deadline:
        try:
            httpx.get(f"http://127.0.0.1:{port}/debug/snapshot", timeout=0.5)
            break
        except Exception:
            time.sleep(0.2)
    else:
        proc.kill()
        out, err = proc.communicate()
        pytest.fail(
            f"Server on port {port} never became ready.\n"
            f"stdout: {out.decode()[:500]}\n"
            f"stderr: {err.decode()[:500]}"
        )
    return proc


# ---------------------------------------------------------------------------
# Test 1: Server shuts down within 5s with one SSE client connected
# ---------------------------------------------------------------------------

def test_server_shuts_down_within_timeout_with_sse_client_connected():
    """Server must exit within 5 seconds after SIGINT even if an SSE client
    is actively connected and receiving events."""
    proc = _start_trace_server(19991)
    stop_client = threading.Event()
    client_connected = threading.Event()

    def sse_client():
        try:
            with httpx.Client(timeout=None) as client:
                with client.stream("GET", "http://127.0.0.1:19991/debug/stream") as resp:
                    client_connected.set()
                    for _ in resp.iter_lines():
                        if stop_client.is_set():
                            break
        except Exception:
            pass

    t = threading.Thread(target=sse_client, daemon=True)
    t.start()

    assert client_connected.wait(timeout=5), "SSE client never connected to /debug/stream"

    proc.send_signal(signal.SIGINT)

    deadline = 5
    try:
        proc.wait(timeout=deadline)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        stop_client.set()
        pytest.fail(
            f"Server did NOT shut down within {deadline}s after SIGINT "
            f"with an active SSE client on /debug/stream — shutdown hang bug."
        )
    finally:
        stop_client.set()
        if proc.poll() is None:
            proc.kill()
            proc.wait()


# ---------------------------------------------------------------------------
# Test 2: SIGTERM also causes clean exit
# ---------------------------------------------------------------------------

def test_server_exits_on_sigterm_with_active_sse_stream():
    """SIGTERM must also terminate the server cleanly within 5s."""
    proc = _start_trace_server(19992)
    client_connected = threading.Event()
    stop_client = threading.Event()

    def sse_client():
        try:
            with httpx.Client(timeout=None) as client:
                with client.stream("GET", "http://127.0.0.1:19992/debug/stream") as resp:
                    client_connected.set()
                    for _ in resp.iter_lines():
                        if stop_client.is_set():
                            break
        except Exception:
            pass

    t = threading.Thread(target=sse_client, daemon=True)
    t.start()

    assert client_connected.wait(timeout=5), "SSE client never connected"

    proc.send_signal(signal.SIGTERM)

    deadline = 5
    try:
        proc.wait(timeout=deadline)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        stop_client.set()
        pytest.fail(
            f"Server did NOT shut down within {deadline}s after SIGTERM "
            f"with an active SSE client."
        )
    finally:
        stop_client.set()
        if proc.poll() is None:
            proc.kill()
            proc.wait()


# ---------------------------------------------------------------------------
# Test 3: Multiple concurrent SSE connections don't block shutdown
# ---------------------------------------------------------------------------

def test_server_shuts_down_with_multiple_concurrent_sse_connections():
    """Multiple open SSE connections (multiple inspector tabs) must not
    prevent server shutdown."""
    proc = _start_trace_server(19993)
    stop_all = threading.Event()
    connected_events = [threading.Event() for _ in range(3)]

    def make_sse_client(port, connected_event):
        def sse_client():
            try:
                with httpx.Client(timeout=None) as client:
                    with client.stream("GET", f"http://127.0.0.1:{port}/debug/stream") as resp:
                        connected_event.set()
                        for _ in resp.iter_lines():
                            if stop_all.is_set():
                                break
            except Exception:
                pass
        return sse_client

    threads = []
    for ev in connected_events:
        t = threading.Thread(target=make_sse_client(19993, ev), daemon=True)
        t.start()
        threads.append(t)

    for ev in connected_events:
        assert ev.wait(timeout=5), "An SSE client never connected"

    proc.send_signal(signal.SIGINT)

    deadline = 5
    try:
        proc.wait(timeout=deadline)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        stop_all.set()
        pytest.fail(
            f"Server did NOT shut down within {deadline}s with 3 concurrent "
            f"SSE connections on /debug/stream — shutdown hang bug."
        )
    finally:
        stop_all.set()
        if proc.poll() is None:
            proc.kill()
            proc.wait()
