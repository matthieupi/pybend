"""Matrix -- Root actor and message router.

One Matrix per actor tree. Multiple matrices are supported for isolation
(e.g., separate trees for tests, microservice extraction).
Routes TX messages to local children or network adapters.
Mirrors Matrix.js from the frontend.

The first Matrix created auto-registers as root (like JS: new Matrix("matrix://root")).
A module-level default `matrix` instance is created at import time so that
__init_subclass__ auto-registration always has a root available.
"""

import logging
from typing import Any

from pydantic import PrivateAttr

from pybend.core.actors.actor import Actor
from pybend.core.actors.tx import TX

logger = logging.getLogger('pybend.actors')


class Matrix(Actor):
    """Root actor and message router."""

    _adapters: list = PrivateAttr(default_factory=list)

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
        Runs 'inbox' interceptors before routing."""
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
        if source_root and source_root in self._children:
            await self._children[source_root].inbox(error_tx)

    def register_adapter(self, adapter: Any):
        """Add a protocol adapter (HTTP, WS, MCP, AP...)."""
        self._adapters.append(adapter)


# Default root Matrix instance (mirrors JS: export const matrix = new Matrix("matrix://root"))
matrix = Matrix()
