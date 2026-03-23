"""TraceCollector — Ring buffer for TX trace entries with SSE fan-out.

Captures TX messages flowing through Matrix.inbox() and distributes
them to connected SSE clients via asyncio.Queue fan-out.
"""

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field, asdict


@dataclass
class TraceEntry:
    """Single captured TX event."""
    tx_uuid: str
    name: str
    source: str
    target: str
    timestamp: float
    trace_id: str
    req: str = ''
    is_error: bool = False
    is_stream: bool = False
    seq: int = 0
    data_summary: str = ''

    def to_dict(self) -> dict:
        return asdict(self)


class TraceCollector:
    """Ring buffer for trace entries with SSE fan-out.

    - capture(tx): Sync — called from inbox hook. Extracts TraceEntry and
      fans out to connected SSE clients via put_nowait.
    - snapshot(): Returns current buffer as list of dicts.
    - subscribe(client_id): Returns Queue for SSE client.
    - unsubscribe(client_id): Cleanup.
    """

    def __init__(self, maxlen: int = 2000):
        self._buffer: deque[TraceEntry] = deque(maxlen=maxlen)
        self._clients: dict[str, asyncio.Queue] = {}

    def capture(self, tx) -> TraceEntry:
        """Capture a TX into the trace buffer and fan out to SSE clients."""
        meta = tx.meta if hasattr(tx, 'meta') else {}

        # Build data summary (truncated string representation)
        data = tx.data if hasattr(tx, 'data') else {}
        if isinstance(data, dict):
            keys = list(data.keys())[:5]
            summary = '{' + ', '.join(f'{k}: ...' for k in keys) + '}' if keys else '{}'
        else:
            summary = str(data)[:100]

        entry = TraceEntry(
            tx_uuid=tx.uuid,
            name=tx.name,
            source=tx.source or '',
            target=tx.target or '',
            timestamp=tx.timestamp if hasattr(tx, 'timestamp') else time.time(),
            trace_id=meta.get('trace_id', ''),
            req=meta.get('req', ''),
            is_error=getattr(tx, 'is_error', False),
            is_stream=meta.get('stream', False),
            seq=meta.get('seq', 0),
            data_summary=summary,
        )
        self._buffer.append(entry)

        # Fan-out to SSE clients (zero cost when none connected)
        entry_dict = entry.to_dict()
        dead_clients = []
        for client_id, queue in self._clients.items():
            try:
                queue.put_nowait(entry_dict)
            except asyncio.QueueFull:
                dead_clients.append(client_id)

        for client_id in dead_clients:
            self._clients.pop(client_id, None)

        return entry

    def snapshot(self) -> list[dict]:
        """Return current buffer as list of dicts (oldest first)."""
        return [e.to_dict() for e in self._buffer]

    def subscribe(self, client_id: str) -> asyncio.Queue:
        """Create and return a Queue for an SSE client."""
        queue = asyncio.Queue(maxsize=500)
        self._clients[client_id] = queue
        return queue

    def unsubscribe(self, client_id: str) -> None:
        """Remove an SSE client."""
        self._clients.pop(client_id, None)

    def clear(self) -> None:
        """Clear all trace entries."""
        self._buffer.clear()

    def __len__(self) -> int:
        return len(self._buffer)
