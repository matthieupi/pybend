"""n3tx-trace — Actor transaction visualization and debugging tool.

Usage:
    # Automatic (via N3TXApp with debug=True):
    app = create_app(models=[...], routing='actor', debug=True)
    # n3tx-trace is auto-detected and enabled if installed.

    # Manual:
    from n3tx_trace import enable_tracing
    enable_tracing(fastapi_app, matrix_instance)
"""

import asyncio

from n3tx_trace.tracer import TraceCollector
from n3tx_trace.trace_context import get_trace_id, set_trace_id
from n3tx_trace.routes import create_debug_routes, mount_debug_static

# Module-level collector (singleton per process)
_collector: TraceCollector | None = None


def get_collector() -> TraceCollector | None:
    """Get the active TraceCollector, or None if tracing is not enabled."""
    return _collector


def enable_tracing(app, matrix, maxlen: int = 2000) -> TraceCollector:
    """Enable TX tracing on a Matrix instance.

    Wraps matrix.inbox() to capture all TX messages into a ring buffer
    and propagate trace_id via contextvars. Mounts debug routes on the
    FastAPI app.

    Args:
        app: FastAPI application instance.
        matrix: Matrix actor instance to trace.
        maxlen: Ring buffer size (default 2000).

    Returns:
        The TraceCollector instance.
    """
    global _collector
    collector = TraceCollector(maxlen=maxlen)
    _collector = collector

    # Save original inbox method
    original_inbox = matrix.inbox

    async def traced_inbox(tx):
        """Wrapped inbox that captures TXs and propagates trace_id."""
        # ── trace_id propagation ──
        meta = tx.meta
        trace_id = meta.get('trace_id')
        if not trace_id:
            ctx_trace = get_trace_id()
            trace_id = ctx_trace or tx.uuid
            meta['trace_id'] = trace_id
        token = set_trace_id(trace_id)

        # ── capture ──
        collector.capture(tx)

        try:
            await original_inbox(tx)
        finally:
            if token:
                token.var.reset(token)

    # Monkey-patch the instance method using object.__setattr__
    # (Pydantic's __setattr__ blocks direct assignment on BaseModel subclasses)
    object.__setattr__(matrix, 'inbox', traced_inbox)

    # Mount debug routes
    router = create_debug_routes(collector, matrix)
    app.include_router(router)
    mount_debug_static(app)

    # Graceful shutdown — signal SSE clients to disconnect BEFORE uvicorn drains
    # connections. We register a signal handler at startup rather than using
    # @app.on_event('shutdown') because uvicorn's shutdown hook only fires AFTER
    # all connections close — but the SSE connection can't close until
    # collector.shutdown() puts None into its queue. Classic deadlock.
    #
    # Uvicorn uses signal.signal() (not loop.add_signal_handler()) via its
    # capture_signals() context manager, which runs before lifespan startup.
    # At startup time, signal.getsignal() returns uvicorn's handle_exit method.
    # We chain: our handler → collector.shutdown() first, then uvicorn's handle_exit.
    @app.on_event('startup')
    async def _setup_trace_shutdown_handler():
        import signal as _signal
        loop = asyncio.get_running_loop()

        for sig in (_signal.SIGINT, _signal.SIGTERM):
            try:
                existing_handler = _signal.getsignal(sig)

                def _make_handler(existing_h):
                    def _handler(signum, frame):
                        # Schedule collector.shutdown() in the event loop so it runs
                        # before uvicorn starts waiting for connections to drain.
                        loop.call_soon_threadsafe(collector.shutdown)
                        # Then chain to uvicorn's handle_exit (sets should_exit=True)
                        if callable(existing_h) and existing_h not in (
                            _signal.SIG_DFL, _signal.SIG_IGN
                        ):
                            existing_h(signum, frame)
                    return _handler

                _signal.signal(sig, _make_handler(existing_handler))
            except (OSError, ValueError):
                # Signal registration not supported (Windows restricted context, etc.)
                pass

    @app.on_event('shutdown')
    async def _shutdown_trace():
        # Fallback: fires after connections close on platforms that don't support
        # signal registration (e.g. Windows), or if handler wasn't installed.
        collector.shutdown()

    return collector
