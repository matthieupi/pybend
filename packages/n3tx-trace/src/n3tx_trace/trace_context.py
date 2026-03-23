"""Trace context propagation via contextvars.

Links nested TXs into request chains. When a TX enters Matrix without
a trace_id, it gets trace_id = tx.uuid (root). The contextvar persists
through await chains — when Matrix routes TX to an actor handler and
that handler sends sub-requests, those sub-requests inherit the trace_id.
"""

import contextvars

_current_trace: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    'n3tx_trace_id', default=None
)


def get_trace_id() -> str | None:
    """Get the current trace_id from context."""
    return _current_trace.get()


def set_trace_id(trace_id: str) -> contextvars.Token:
    """Set the current trace_id in context. Returns token for reset."""
    return _current_trace.set(trace_id)
