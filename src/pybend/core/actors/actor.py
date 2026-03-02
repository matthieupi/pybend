"""ActorMeta — Metaclass approach for transparent class/instance dispatch.

The goal: Product.inbox(tx) and product.inbox(tx) both work, same code.
And: Product.children, product.children — same accessor, same behavior.

The key insight: every actor operation is the SAME on classes and instances.
The only difference is where the state lives (__children__ vs _children,
__addr__ vs _addr). Two descriptors make this transparent:

    actormethod   — binds target = cls or self, returns bound method
    actorproperty — resolves to class or instance state, returns value

    @actormethod
    async def inbox(target, tx):   # target is cls OR self
        await target.handler(tx)   # works for both

    @actorproperty
    def children(target):          # target is cls OR self
        ...                        # returns __children__ or _children

Architecture:
    ActorMeta      (metaclass)   → class construction only (children, addr, interceptors, auto-register)
    actormethod    (descriptor)  → binds target = cls or self (for methods)
    actorproperty  (descriptor)  → resolves class or instance state (for properties)
    Actor          (class)       → fully unified API: everything works on both

Interceptors:
    actor.use(fn, on='inbox')    → register TX interceptor on a method
    Interceptor signature:         async (TX) -> TX  (return error TX to short-circuit)
    Runs before the method body. Class + instance interceptors combine.
    Supports decorator form:       @actor.use(on='request')

Usage:
    class Product(Actor):
        __tablename__ = 'products'

        @classmethod
        def SCHEMA(cls, data, tx):
            return cls.schema()

    # Everything works on both — same API, same behavior:
    Product.addr              # 'products'
    product.addr              # 'products/1'
    Product.children          # class-level children dict
    product.children          # instance-level children dict
    Product.register(child)   # registers into class children
    product.register(child)   # registers into instance children
    await Product.inbox(tx)   # dispatches via class
    await product.inbox(tx)   # dispatches via instance
"""

import asyncio
import logging
from types import MethodType
from typing import Any, ClassVar, Optional, TYPE_CHECKING

from pydantic import BaseModel as PydanticBaseModel, ConfigDict, PrivateAttr

from pybend.core.actors.tx import TX

logger = logging.getLogger('pybend.actors')

# Pydantic's metaclass — extend it to stay compatible
_PydanticMeta = type(PydanticBaseModel)

# ── Descriptors ───────────────────────────────────────────────────

if TYPE_CHECKING:
    # Static analysis: transparent passthrough — IDE sees original signatures
    from typing import TypeVar

    _F = TypeVar('_F')


    def actormethod(fn: _F) -> _F:
        ...  # noqa: E704


    def actorproperty(fn: _F) -> _F:
        ...  # noqa: E704
else:
    class actormethod:
        """A method that works on both classes and instances.

        The first parameter receives the class (when called as cls.method())
        or the instance (when called as self.method()). One function, one
        implementation — no dual paths.

            @actormethod
            async def inbox(target, tx):  # target is cls or self
                await target.handler(tx)

        Python mechanics:
            Product.inbox  → __get__(None, Product) → MethodType(fn, Product)
            product.inbox  → __get__(product, type) → MethodType(fn, product)
        """

        def __init__(self, fn):
            self.fn = fn
            self.__doc__ = fn.__doc__
            self.__name__ = fn.__name__

        def __set_name__(self, owner, name):
            self.__name__ = name

        def __get__(self, obj, cls=None):
            target = obj if obj is not None else cls
            return MethodType(self.fn, target)


    class actorproperty:
        """A property that works on both classes and instances.

        The function receives the class or instance and returns a value.
        Unlike actormethod, this returns the value directly — not a callable.

            @actorproperty
            def children(target):          # target is cls or self
                if isinstance(target, type):
                    return target.__children__
                return target._children

        Python mechanics:
            Product.children  → __get__(None, Product) → fn(Product) → dict
            product.children  → __get__(product, type)  → fn(product) → dict
        """

        def __init__(self, fn):
            self.fn = fn
            self.__doc__ = fn.__doc__

        def __set_name__(self, owner, name):
            self.__name__ = name

        def __get__(self, obj, cls=None):
            target = obj if obj is not None else cls
            return self.fn(target)


# ── ActorMeta metaclass ────────────────────────────────────────────

class ActorMeta(_PydanticMeta):
    """Metaclass for Actor class construction.

    Handles per-class setup: __children__, __addr__, __interceptors__, auto-registration.
    Messaging lives on Actor via actormethod — NOT on the metaclass.
    """

    def __new__(mcs, name, bases, namespace, auto_register=True, **kwargs):
        # Consume auto_register before it reaches type.__new__ / __init_subclass__
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)

        # Each class gets its own children dict and interceptors dict
        cls.__children__ = {}
        cls.__interceptors__ = {}

        # Default __addr__ from __tablename__ or class name
        if '__addr__' not in namespace:
            cls.__addr__ = getattr(cls, '__tablename__', name)

        # Auto-register with root Matrix if available
        root = getattr(cls, '__matrix__', None)
        if auto_register and root and name != 'Actor':
            root._children[cls.__addr__] = cls

        return cls


# ── Actor class ─────────────────────────────────────────────────────

class Actor(PydanticBaseModel, metaclass=ActorMeta, auto_register=False):
    """Base actor with unified class/instance dispatch.

    Everything works identically on classes and instances:

        Product.addr / product.addr
        Product.children / product.children
        Product.parent / product.parent
        Product.register(child) / product.register(child)
        await Product.inbox(tx) / await product.inbox(tx)

    Two descriptors make this possible:
        actormethod   — binds target = cls or self (inbox, handler, send, register, spawn)
        actorproperty — resolves to class or instance state (addr, children, parent)

    State:
        Class-level:    __addr__, __children__, __matrix__ (set by ActorMeta)
        Instance-level: _addr, _children, _parent (Pydantic PrivateAttr)
    """

    # Tell Pydantic to ignore our custom descriptors
    model_config = ConfigDict(ignored_types=(actormethod, actorproperty))

    # Class-level state (managed by ActorMeta.__new__)
    __addr__: ClassVar[str] = ''
    __children__: ClassVar[dict] = {}
    __interceptors__: ClassVar[dict] = {}
    __matrix__: ClassVar[Optional['Actor']] = None

    # Instance-level state (Pydantic PrivateAttr for MI compatibility)
    _addr: str = PrivateAttr(default='')
    _children: dict = PrivateAttr(default_factory=dict)
    _parent: Optional[Any] = PrivateAttr(default=None)
    _interceptors: dict = PrivateAttr(default_factory=dict)

    def __init__(self, *args, **kwargs):
        addr = kwargs.pop('addr', '')
        super().__init__(*args, **kwargs)
        self._addr = addr or self.__class__.__addr__ or self.__class__.__name__
        # Default parent = class itself (mirrors JS: this.#parent = this.constructor)
        self._parent = self.__class__

    # ── Unified properties (class and instance) ──

    @actorproperty
    def addr(target) -> str:
        """Actor address. Class: __addr__. Instance: _addr."""
        if isinstance(target, type):
            return target.__addr__
        return target._addr

    @actorproperty
    def children(target) -> dict:
        """Children dict. Class: __children__. Instance: _children."""
        if isinstance(target, type):
            return target.__children__
        return target._children

    @actorproperty
    def parent(target):
        """Parent actor. Class: __matrix__ (root). Instance: _parent."""
        if isinstance(target, type):
            return target.__matrix__
        return target._parent

    # ── Root actor (getter/setter) ──

    @classmethod
    def root(cls, actor: 'Actor' = None):
        """Get or set the root actor (Matrix)."""
        if actor is None:
            return cls.__matrix__
        cls.__matrix__ = actor

    # ── Interceptors ──

    @actormethod
    def use(target, interceptor=None, *, on='inbox'):
        """Register a TX interceptor on a specific method.

        Interceptor signature: async (TX) -> TX
        Return error TX to short-circuit the chain.

        Works as plain call or decorator:
            actor.use(auth_check)               # on='inbox' (default)
            actor.use(auth_check, on='send')    # explicit method target

            @actor.use                          # decorator form
            async def auth_check(tx: TX) -> TX: ...

            @actor.use(on='request')            # decorator with method target
            async def rate_limit(tx: TX) -> TX: ...
        """
        def _register(fn):
            if isinstance(target, type):
                target.__interceptors__.setdefault(on, []).append(fn)
            else:
                target._interceptors.setdefault(on, []).append(fn)
            return fn

        if interceptor is None:
            return _register
        if callable(interceptor):
            return _register(interceptor)
        raise TypeError(f"Expected callable or None, got {type(interceptor)}")

    @staticmethod
    def _get_interceptors(target, method_name: str) -> list:
        """Get interceptors for a method, combining class + instance chains."""
        if isinstance(target, type):
            return target.__interceptors__.get(method_name, [])
        cls_chain = target.__class__.__interceptors__.get(method_name, [])
        inst_chain = target._interceptors.get(method_name, [])
        if cls_chain and inst_chain:
            return cls_chain + inst_chain
        return cls_chain or inst_chain

    @staticmethod
    async def _run_interceptors(interceptors: list, tx: TX) -> TX:
        """Run interceptor chain. Returns (possibly modified) TX.
        Short-circuits on error TX."""
        for fn in interceptors:
            if asyncio.iscoroutinefunction(fn):
                tx = await fn(tx)
            else:
                tx = fn(tx)
            if tx.is_error:
                return tx
        return tx

    # ── Core messaging (ONE implementation for both class and instance) ──

    @actormethod
    async def inbox(target, tx: TX) -> None:
        """Receive a message. Runs 'inbox' interceptors, then handler.

        Works on both classes and instances:
            await Product.inbox(tx)   # target = Product
            await product.inbox(tx)   # target = product
        """
        print(tx)
        interceptors = Actor._get_interceptors(target, 'inbox')
        if interceptors:
            tx = await Actor._run_interceptors(interceptors, tx)
            if tx.is_error:
                await target.send(tx)
                return
        await target.handler(tx)

    @actormethod
    async def handler(target, tx: TX) -> None:
        """Dispatch to named method on target, wrap result, route reply.

        getattr(target, tx.name) works on both classes and instances:
        - Class:    getattr(Product, 'CREATE') → bound classmethod
        - Instance: getattr(product, 'DUMP')   → bound instance method

        Error and response TXs that have no handler are silently dropped
        to prevent infinite bounce loops between actors.
        """
        method = getattr(target, tx.name, None)
        if method and callable(method):
            try:
                if asyncio.iscoroutinefunction(method):
                    result = await method(tx.data, tx)
                else:
                    result = method(tx.data, tx)
            except Exception as e:
                logger.error(f"[{target.addr}] Error in {tx.name}: {e}")
                await target.send(tx.error(str(e)))
                return

            if isinstance(result, TX):
                await target.send(result)
            elif isinstance(result, dict):
                await target.send(tx.reply(data=result))
            elif result is not None:
                await target.send(tx.reply(data={'result': result}))
            else:
                await target.send(tx.reply())
        else:
            # Drop errors and responses silently — sending an error in
            # response to an error creates infinite bounce loops.
            if tx.is_error or tx.name.endswith('_RESPONSE'):
                addr = target.addr if not isinstance(target, type) else target.__addr__
                logger.debug("[%s] Dropped unhandled %s from %s", addr, tx.name, tx.source)
                return
            await target.send(tx.error(f"Unhandled message: {tx.name}"))

    @actormethod
    async def send(target, tx: TX) -> None:
        """Route message for delivery. Runs 'send' interceptors first.

        Class:    route through children or bubble to parent (matrix)
        Instance: route through parent chain
        """
        interceptors = Actor._get_interceptors(target, 'send')
        if interceptors:
            tx = await Actor._run_interceptors(interceptors, tx)
            if tx.is_error:
                return  # Drop — don't route rejected outbound messages

        if isinstance(target, type):
            # ── Class-level routing (mirrors JS Actor._send) ──
            children = target.children
            addr = target.addr
            segments = [s for s in (tx.target or '').split('/') if s]
            seg_first = segments[0] if segments else ''
            seg_second = segments[1] if len(segments) > 1 else ''

            if seg_first and seg_first in children:
                await children[seg_first].inbox(tx)
            elif seg_first == addr and seg_second in children:
                tx.target = '/'.join(segments[1:])
                await children[seg_second].inbox(tx)
            elif target.parent:
                tx.source = f'{addr}/{tx.source}' if tx.source else addr
                await target.parent.inbox(tx)
        else:
            # ── Instance-level routing (through parent chain) ──
            parent = target.parent
            if isinstance(parent, type):
                await parent.send(tx)
            elif parent:
                await parent.inbox(tx)
            else:
                raise RuntimeError(
                    f"[{target.addr}] No parent or root for routing. "
                    "Initialize a Matrix first."
                )

    # ── Unified child management ──

    @actormethod
    def register(target, child: 'Actor') -> 'Actor':
        """Register a child actor. Works on both classes and instances.

            Product.register(child)   # into class __children__
            product.register(child)   # into instance _children, sets child._parent
        """
        child_addr = child.addr

        if isinstance(target, type):
            target.__children__[child_addr] = child
        else:
            target._children[child_addr] = child

        # Set parent on instance children
        if not isinstance(child, type):
            child._parent = target

        return child

    @actormethod
    def spawn(target, addr: str, actor_cls: type, *args, **kwargs) -> 'Actor':
        """Spawn and register a child actor."""
        if addr in target.children:
            raise ValueError(
                f"[{target.addr}] Child '{addr}' already exists."
            )
        child = actor_cls(*args, addr=addr, **kwargs)
        return target.register(child)

    @actormethod
    def has(target, addr: str) -> bool:
        """Check if a child exists by first address segment."""
        return addr.split('/')[0] in target.children

    # ── Lifecycle hooks ──

    async def on_start(self):
        """Called after actor is fully initialized. Override in subclasses."""

    async def on_stop(self):
        """Called before actor is shut down. Override in subclasses."""
