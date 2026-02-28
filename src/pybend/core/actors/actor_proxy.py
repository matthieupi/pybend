"""ActorProxy — Generalist wrapper giving any target the actor interface.

Wraps a class OR instance and provides inbox/handler/send/register/spawn.
The Matrix (or any parent) can call child.inbox(tx) uniformly — no
isinstance checks, no special routing for classes vs instances.

    # Wrap a class — handler dispatches to classmethods (SCHEMA, CREATE, ...)
    proxy = ActorProxy(Product)

    # Wrap an instance — handler dispatches to instance methods (DUMP, ...)
    proxy = ActorProxy(product_instance)

    # Register with any parent — Matrix just calls .inbox(tx)
    matrix_proxy.register(proxy)

Design notes:
- getattr(target, tx.name) works for both classes and instances.
  On classes it finds classmethods/staticmethods; on instances it finds
  instance methods. The proxy doesn't interfere with Python's lookup.
- __slots__ for lightweight memory footprint (many proxies in a tree).
- ActorLike Protocol for IDE type checking.
"""

import asyncio
import logging
from typing import Any, Optional, Protocol, runtime_checkable

from pybend.core.actors.tx import TX

logger = logging.getLogger('pybend.actors')


@runtime_checkable
class ActorLike(Protocol):
    """Protocol: anything the Matrix can route to."""

    @property
    def addr(self) -> str: ...
    async def inbox(self, tx: TX) -> None: ...
    async def send(self, tx: TX) -> None: ...


class ActorProxy:
    """Wraps any target (class or instance) as a routable actor.

    The proxy IS the actor from the Matrix's perspective. It holds the
    routing state (addr, parent, children) and delegates message handling
    to the wrapped target via getattr.
    """

    __slots__ = ('_target', '_addr', '_parent', '_children')

    def __init__(
        self,
        target: Any,
        addr: str = '',
        parent: Optional['ActorProxy'] = None,
    ):
        self._target = target
        self._addr = addr or self._resolve_addr(target)
        self._parent = parent
        self._children: dict[str, 'ActorProxy'] = {}

    # ── Address resolution ──

    @staticmethod
    def _resolve_addr(target: Any) -> str:
        """Extract address from any target type."""
        # Class: check __addr__ (Actor), __tablename__ (ProtoModel), __name__
        if isinstance(target, type):
            return getattr(target, '__addr__',
                   getattr(target, '__tablename__', target.__name__))
        # ActorProxy: delegate
        if isinstance(target, ActorProxy):
            return target.addr
        # Instance: check addr property, _addr private, fallback to class name
        return getattr(target, 'addr',
               getattr(target, '_addr', target.__class__.__name__))

    # ── Properties ──

    @property
    def addr(self) -> str:
        return self._addr

    @property
    def target(self) -> Any:
        """The wrapped class or instance."""
        return self._target

    @property
    def children(self) -> dict[str, 'ActorProxy']:
        return self._children

    @property
    def parent(self) -> Optional['ActorProxy']:
        return self._parent

    @parent.setter
    def parent(self, value: Optional['ActorProxy']):
        self._parent = value

    # ── Core actor interface ──

    async def inbox(self, tx: TX) -> None:
        """Receive a message. Three routing cases:

        1. Target matches a child → route to child
        2. Target matches us (or is our responsibility) → handle locally
        3. Neither → bubble up to parent for routing

        This mirrors the JS pattern: actors route to children, handle
        their own messages, and bubble everything else up to the Matrix.
        """
        target = tx.target

        # 1. Exact child match
        if target in self._children:
            await self._children[target].inbox(tx)
            return

        # Segment-based child routing:
        # our addr='products', target='products/42' → child 'products/42' or '42'
        prefix = self._addr + '/'
        if target.startswith(prefix):
            remainder = target[len(prefix):]
            child_key = remainder.split('/')[0]
            for key in (f'{self._addr}/{child_key}', child_key):
                if key in self._children:
                    await self._children[key].inbox(tx)
                    return

        # 2. Target is us → handle locally
        if target == self._addr:
            await self.handler(tx)
            return

        # 3. Not for us, not for our children → bubble up
        if self._parent:
            await self._parent.inbox(tx)
        else:
            logger.warning(f"[{self.addr}] No route to {target}")

    async def handler(self, tx: TX) -> None:
        """Dispatch to named method on the wrapped target.

        Uses getattr(target, tx.name) which works for:
        - Classes: finds classmethods, staticmethods (SCHEMA, CREATE, READ...)
        - Instances: finds instance methods (DUMP, DUMP_RESPONSE, custom...)
        """
        method = getattr(self._target, tx.name, None)
        if method and callable(method):
            try:
                if asyncio.iscoroutinefunction(method):
                    result = await method(tx.data, tx)
                else:
                    result = method(tx.data, tx)
            except Exception as e:
                logger.error(f"[{self.addr}] Error in {tx.name}: {e}")
                await self.send(tx.error(str(e)))
                return

            if isinstance(result, TX):
                await self.send(result)
            elif isinstance(result, dict):
                await self.send(tx.reply(data=result))
            elif result is not None:
                await self.send(tx.reply(data={'result': result}))
            else:
                await self.send(tx.reply())
        else:
            await self.send(tx.error(f"Unhandled message: {tx.name}"))

    async def send(self, tx: TX) -> None:
        """Route message through parent for delivery."""
        if self._parent:
            await self._parent.inbox(tx)
        else:
            raise RuntimeError(
                f"[{self.addr}] No parent for routing. "
                "Register this proxy with a parent first."
            )

    # ── Child management ──

    def register(self, child: Any) -> 'ActorProxy':
        """Register a child. Wraps in ActorProxy if needed."""
        if not isinstance(child, ActorProxy):
            child = ActorProxy(child)
        child._parent = self
        self._children[child.addr] = child
        return child

    def spawn(self, target: Any, addr: str = '') -> 'ActorProxy':
        """Create a proxy for target and register as child."""
        proxy = ActorProxy(target, addr=addr)
        if proxy.addr in self._children:
            raise ValueError(
                f"[{self.addr}] Child '{proxy.addr}' already exists."
            )
        return self.register(proxy)

    def has(self, addr: str) -> bool:
        """Check if a child exists by first address segment."""
        return addr.split('/')[0] in self._children

    # ── Repr ──

    def __repr__(self) -> str:
        kind = 'class' if isinstance(self._target, type) else 'instance'
        name = (self._target.__name__ if isinstance(self._target, type)
                else self._target.__class__.__name__)
        return f"ActorProxy({name}, addr='{self.addr}', {kind})"
