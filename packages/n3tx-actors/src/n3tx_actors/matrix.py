"""Matrix -- Root actor and message router.

One Matrix per actor tree. Multiple matrices are supported for isolation
(e.g., separate trees for tests, microservice extraction).
Routes TX messages to local children or network adapters.
Mirrors Matrix.js from the frontend.

The first Matrix created auto-registers as root (like JS: new Matrix("matrix://root")).
A module-level default `matrix` instance is created at import time so that
__init_subclass__ auto-registration always has a root available.
"""

import asyncio
import logging
from typing import Any

from pydantic import PrivateAttr

from n3tx_actors.actor import Actor
from n3tx_actors.tx import TX

logger = logging.getLogger('n3tx.actors')


class Matrix(Actor):
    """Root actor and message router.

    Provides request() for internal request-response over fire-and-forget
    messaging. Any actor can call Actor.root().request(tx) to send a TX
    and await the correlated reply — no NetworkAdapter needed.
    """

    _adapters: list = PrivateAttr(default_factory=list)
    _pending: dict = PrivateAttr(default_factory=dict)

    def __init__(self, **kwargs):
        kwargs.setdefault('addr', 'matrix')
        super().__init__(**kwargs)
        # Auto-register as root if no root exists (mirrors JS Matrix constructor)
        if not Actor.root():
            Actor.root(self)

    def has(self, addr: str) -> bool:
        """Check if a child actor exists by first address segment."""
        return addr.split('/')[0] in self._children

    async def inbox(self, tx: TX) -> None:
        """Route message to local child actor or network adapter.
        Runs 'inbox' interceptors before routing.

        Checks pending request() correlations first — a reply TX with
        meta['req'] matching a pending future resolves it directly,
        bypassing normal routing (including self-send prevention).
        """
        # ── Correlation: resolve pending request() futures ──
        reply_to = tx.meta.get('req')
        if reply_to and reply_to in self._pending:
            pending = self._pending.pop(reply_to)
            if isinstance(pending, asyncio.Future) and not pending.done():
                pending.set_result(tx)
            elif isinstance(pending, asyncio.Queue):
                await pending.put(tx)
                if not (tx.is_error or tx.meta.get('stream_end')):
                    self._pending[reply_to] = pending  # keep open
            return

        # Run interceptors (e.g., routing authorization)
        interceptors = Actor._get_interceptors(self, 'inbox')
        if interceptors:
            tx = await Actor._run_interceptors(interceptors, tx)
            if tx.is_error:
                return

        target_root = tx.target.split('/')[0]

        # Self-send prevention
        if target_root == self.addr:
            logger.error(f"[Matrix] Cannot route to self at {self.addr}")
            return

        # Local children first (mirrors JS: this.children.has(targetAddr))
        if target_root in self._children:
            await self._children[target_root].inbox(tx)

        # Try network adapters (HTTP, WS, MCP, AP...)
        elif self._adapters:
            for adapter in self._adapters:
                if adapter.can_handle(tx):
                    await adapter.send(tx)
                    return
            logger.warning(f"[Matrix] No route to {tx.target}")
            await self._route_error(tx)

        else:
            logger.warning(f"[Matrix] No route to {tx.target}")
            await self._route_error(tx)

    async def send(self, tx: TX) -> None:
        """Matrix routes internally -- no parent needed."""
        await self.inbox(tx)

    async def _route_error(self, tx: TX) -> None:
        """Route error TX back to sender when no route is found."""
        # Don't bounce error TXs — prevents infinite loops
        if tx.is_error:
            return
        error_tx = tx.error(f"No route to '{tx.target}'", code=404)
        source_root = tx.source.split('/')[0] if tx.source else ''
        if source_root == self.addr:
            # Source is matrix itself — route through inbox for correlation
            await self.inbox(error_tx)
        elif source_root and source_root in self._children:
            await self._children[source_root].inbox(error_tx)

    async def request(self, tx: TX, timeout: float = 30.0) -> TX:
        """Send TX and await the correlated response.

        Internal request-response for any actor that needs to send a
        message and wait for a reply. No adapter registration needed.

            response = await Actor.root().request(
                TX(name='get', source='matrix', target='products', data={'id': 1})
            )

        The reply TX arrives at inbox() with meta['req'] == tx.uuid,
        resolving the future before normal routing runs.

        Args:
            tx: The message to send. source is set to self.addr automatically.
            timeout: Seconds to wait before returning a timeout error TX.

        Returns:
            The response TX (reply or error).
        """
        tx.source = tx.source or self.addr
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending[tx.uuid] = future
        await self.send(tx)
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(tx.uuid, None)
            return tx.error(
                f"Request to {tx.target} timed out after {timeout}s", code=504
            )

    async def stream(self, tx: TX, timeout: float = 120.0):
        """Send TX and yield correlated stream chunks.

        Internal streaming twin of request(). Uses an asyncio.Queue keyed by
        the outbound TX uuid and yields correlated replies until stream_end or
        error.
        """
        tx.source = tx.source or self.addr
        queue = asyncio.Queue()
        self._pending[tx.uuid] = queue

        send_task = asyncio.create_task(self.send(tx))

        try:
            while True:
                try:
                    chunk = await asyncio.wait_for(queue.get(), timeout=timeout)
                except asyncio.TimeoutError:
                    yield tx.error(
                        f"Stream to {tx.target} timed out after {timeout}s", code=504
                    )
                    return
                yield chunk
                if chunk.is_error or chunk.meta.get('stream_end'):
                    return
        finally:
            self._pending.pop(tx.uuid, None)
            if not send_task.done():
                send_task.cancel()

    def register_adapter(self, adapter: Any):
        """Add a protocol adapter (HTTP, WS, MCP, AP...)."""
        self._adapters.append(adapter)


# Default root Matrix instance (mirrors JS: export const matrix = new Matrix("matrix://root"))
matrix = Matrix()
