"""NetworkAdapter — Base class for protocol adapters.

An Actor that bridges external protocols to the Matrix. ALL external
interaction flows through a NetworkAdapter:

    NetworkMCP        — AI agents discover and call model methods (MCP JSON-RPC)
    NetworkAP         — Fediverse actors exchange activities (ActivityPub)
    NetworkAPI        — HTTP clients call CRUD and custom endpoints (FastAPI/Flask/Django)
    NetworkWebSocket  — Frontend Matrix bridges to backend Matrix (WebSocket)

Each adapter:
1. Receives external protocol messages
2. Translates to TX
3. Routes through Matrix via request() or send()
4. Translates response TX back to external protocol

The adapter IS an Actor registered as a child of Matrix. Response TXs
route back through normal Matrix routing — no special mechanism needed.

The request() method bridges synchronous protocols (HTTP, MCP JSON-RPC)
to the fire-and-forget actor model using correlation_id matching and
asyncio.Future.
"""

import asyncio
import logging

from pydantic import PrivateAttr

from n3tx.core.actors.actor import Actor
from n3tx.core.actors.tx import TX

logger = logging.getLogger('n3tx.network')


class NetworkAdapter(Actor, auto_register=False):
    """Base for actors that bridge external protocols to the Matrix.

    Provides request() for request/response bridging over fire-and-forget
    messaging. Responses route back through normal Matrix routing — the
    adapter is a child actor, so reply TXs with target=adapter.addr
    arrive at adapter.inbox() automatically.

    Subclasses should also use auto_register=False since they need
    constructor arguments and manual registration via matrix.register().

    Usage:
        mcp = NetworkMCP(addr='mcp')
        matrix.register(mcp)

        # Response TXs with target='mcp' route here automatically
        response = await mcp.request(TX(source='mcp', target='products', name='schema'))
    """

    _pending: dict = PrivateAttr(default_factory=dict)

    async def inbox(self, tx: TX) -> None:
        """Check for pending request correlation before normal dispatch.

        When request() sends a TX, it stores a Future keyed by tx.uuid.
        When stream() sends a TX, it stores a Queue keyed by tx.uuid.
        Reply TXs with meta['req'] matching that uuid resolve the
        Future (single response) or feed the Queue (streaming chunks).
        Otherwise, fall through to normal Actor.inbox() → handler().
        """
        reply_to = tx.meta.get('req')
        if reply_to and reply_to in self._pending:
            pending = self._pending[reply_to]
            if isinstance(pending, asyncio.Future):
                self._pending.pop(reply_to)
                pending.set_result(tx)
            elif isinstance(pending, asyncio.Queue):
                await pending.put(tx)
                if tx.is_error or tx.meta.get('stream_end'):
                    self._pending.pop(reply_to, None)
            return
        await super().inbox(tx)

    async def request(self, tx: TX, timeout: float = 30.0) -> TX:
        """Send TX and await the correlated response.

        Bridges synchronous protocols (HTTP, MCP JSON-RPC) to async actor
        messaging. Runs 'request' interceptors first (e.g., authentication),
        then sends the TX and awaits the correlated reply.

        The reply TX arrives at self.inbox() with meta['req'] set
        to the original tx.uuid — standard TX.reply() behavior from Wave 0.

        For streaming (multiple correlated replies), use stream() instead.

        Args:
            tx: The message to send. tx.source should be this adapter's addr.
            timeout: Seconds to wait before returning a timeout error TX.

        Returns:
            The response TX (reply or error).
        """
        # Run 'request' interceptors (e.g., auth, rate limiting)
        from n3tx.core.actors.actor import Actor
        interceptors = Actor._get_interceptors(self, 'request')
        if interceptors:
            tx = await Actor._run_interceptors(interceptors, tx)
            if tx.is_error:
                return tx  # Rejected — never enters actor system

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

        Like request() but yields multiple TX responses. Terminates on
        stream_end or error TX. Uses asyncio.Queue for correlation.

        Args:
            tx: The message to send. tx.source should be this adapter's addr.
            timeout: Seconds to wait for each chunk before yielding a timeout error.

        Yields:
            TX: Stream chunk, stream_end, or error TXs.
        """
        from n3tx.core.actors.actor import Actor
        interceptors = Actor._get_interceptors(self, 'request')
        if interceptors:
            tx = await Actor._run_interceptors(interceptors, tx)
            if tx.is_error:
                yield tx
                return

        queue = asyncio.Queue()
        self._pending[tx.uuid] = queue
        await self.send(tx)
        try:
            while True:
                try:
                    chunk = await asyncio.wait_for(queue.get(), timeout=timeout)
                except asyncio.TimeoutError:
                    yield tx.error(f"Stream timed out after {timeout}s", code=504)
                    return
                yield chunk
                if chunk.is_error or chunk.meta.get('stream_end'):
                    return
        finally:
            self._pending.pop(tx.uuid, None)
