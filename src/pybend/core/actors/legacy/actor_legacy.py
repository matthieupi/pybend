"""Actor -- Base class for the actor system.

Direct port of frontend Actor.js. Python MI replaces JS Actor.subclass().
Each actor has an address, parent, children, inbox, handler, and send.

Design constraints:
- PrivateAttr for Pydantic V2 compatibility in MI with ProtoModel
- __init_subclass__ creates per-class __children__, __addr__, auto-registers with root
- _parent defaults to self.__class__ (mirrors JS: this.#parent = this.constructor)
- register()/spawn() override _parent with the actual parent actor instance
- Async inbox/handler/send built on asyncio
"""

import asyncio
import logging
from typing import Any, ClassVar, Optional

from pydantic import BaseModel as PydanticBaseModel, PrivateAttr

from pybend.core.actors.tx import TX

logger = logging.getLogger('pybend.actors')


class Actor(PydanticBaseModel):
    """Base actor with address, parent, children, inbox, handler, send."""

    # Class-level state (per-class via __init_subclass__)
    __addr__: ClassVar[str] = ''
    __children__: ClassVar[dict] = {}
    __matrix__: ClassVar[Optional['Actor']] = None

    # Instance-level state (Pydantic PrivateAttr)
    _addr: str = PrivateAttr(default='')
    _children: dict = PrivateAttr(default_factory=dict)
    _parent: Optional[Any] = PrivateAttr(default=None)

    def __init_subclass__(cls, auto_register=True, **kwargs):
        super().__init_subclass__(**kwargs)
        # Each subclass gets its own children dict (not shared with parent class)
        cls.__children__ = {}
        # Default __addr__ to __tablename__ (for models) or class name
        if '__addr__' not in cls.__dict__:
            cls.__addr__ = getattr(cls, '__tablename__', cls.__name__)
        # Auto-register with root Matrix if available (class-level, not instance)
        if auto_register and Actor.__matrix__:
            Actor.__matrix__._children[cls.__addr__] = cls

    def __init__(self, *args, **kwargs):
        addr = kwargs.pop('addr', '')
        super().__init__(*args, **kwargs)
        self._addr = addr or self.__class__.__addr__ or self.__class__.__name__
        # Default parent is the class itself (mirrors JS: this.#parent = this.constructor)
        # spawn()/register() override this with the actual parent actor instance
        self._parent = self.__class__

    # ── Properties ──

    @property
    def addr(self) -> str:
        return self._addr

    @property
    def children(self) -> dict:
        return self._children

    @property
    def parent(self):
        return self._parent

    # ── Root actor (getter/setter) ──

    @classmethod
    def root(cls, actor: 'Actor' = None):
        """Get or set the root actor (Matrix).

        Actor.root()        -> returns the root actor
        Actor.root(matrix)  -> sets the root actor
        """
        if actor is None:
            return cls.__matrix__
        cls.__matrix__ = actor

    # ── Instance messaging ──

    async def inbox(self, tx: TX) -> None:
        """Receive a message. Fire-and-forget -- does NOT return a value."""
        await self.handler(tx)

    async def handler(self, tx: TX) -> None:
        """Dispatch to named method, wrap return in reply TX, send.

        Methods can return:
        - dict       -> wrapped in tx.reply(data=...)
        - TX         -> sent as-is (e.g., tx.error())
        - other      -> wrapped as {'result': value}
        - None       -> sends tx.reply() with empty data
        """
        method = getattr(self, tx.name, None)
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
        """Send message through parent chain for routing.

        _parent is either:
        - self.__class__ (default) -> route via class-level send_cls()
        - an Actor instance (set by spawn/register) -> route via parent.inbox()
        """
        if isinstance(self._parent, type):
            # Parent is a class — use class-level routing
            await self._parent.send_cls(tx)
        elif self._parent:
            # Parent is an actor instance (set by spawn/register)
            await self._parent.inbox(tx)
        else:
            raise RuntimeError(
                f"[{self.addr}] No parent or root actor. "
                "Initialize a Matrix first."
            )

    # ── Instance child management ──

    def register(self, child: 'Actor') -> 'Actor':
        """Register a child actor (instance-level)."""
        child._parent = self
        self._children[child.addr] = child
        return child

    def spawn(self, addr: str, actor_cls: type, *args, **kwargs) -> 'Actor':
        """Spawn and register a child actor."""
        if addr in self._children:
            raise ValueError(
                f"[{self.addr}] Child actor with address '{addr}' already exists."
            )
        child = actor_cls(*args, addr=addr, **kwargs)
        return self.register(child)

    # ── Class-level methods ──

    @classmethod
    def register_cls(cls, child: 'Actor'):
        """Register into the class-level children registry."""
        cls.__children__[child.addr] = child

    @classmethod
    async def send_cls(cls, tx: TX) -> None:
        """Class-level send -- mirrors JS Actor._send().

        Three routing cases:
        1. Target's first segment matches a class child -> route directly
        2. Target starts with this class's addr -> strip prefix, route to child
        3. No match -> prefix source with class addr, bubble to root Matrix
        """
        children = cls.__children__
        type_addr = cls.__addr__ or cls.__name__
        segments = [s for s in (tx.target or '').split('/') if s]
        target_parent = segments[0] if segments else ''
        target_child = segments[1] if len(segments) > 1 else ''

        # Case 1: target is directly one of our children
        if target_parent and target_parent in children:
            await children[target_parent].inbox(tx)

        # Case 2: target starts with our addr — strip prefix, route to child
        elif target_parent == type_addr and target_child and target_child in children:
            tx.target = '/'.join(segments[1:])
            await children[target_child].inbox(tx)

        # Case 3: bubble to root Matrix with source prefix
        elif Actor.__matrix__:
            tx.source = f'{type_addr}/{tx.source}' if tx.source else type_addr
            await Actor.__matrix__.inbox(tx)

    # ── Lifecycle hooks ──

    async def on_start(self):
        """Called after actor is fully initialized. Override in subclasses."""

    async def on_stop(self):
        """Called before actor is shut down. Override in subclasses."""
