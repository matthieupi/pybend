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
        When the reply arrives, its meta['in_reply_to'] matches that uuid.
        If found, resolve the Future and short-circuit — no handler dispatch.
        Otherwise, fall through to normal Actor.inbox() → handler().
        """
        reply_to = tx.meta.get('in_reply_to')
        if reply_to and reply_to in self._pending:
            self._pending.pop(reply_to).set_result(tx)
            return
        await super().inbox(tx)

    async def request(self, tx: TX, timeout: float = 30.0) -> TX:
        """Send TX and await the correlated response.

        Bridges synchronous protocols (HTTP, MCP JSON-RPC) to async actor
        messaging. Runs 'request' interceptors first (e.g., authentication),
        then sends the TX and awaits the correlated reply.

        The reply TX arrives at self.inbox() with meta['in_reply_to'] set
        to the original tx.uuid — standard TX.reply() behavior from Wave 0.

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
