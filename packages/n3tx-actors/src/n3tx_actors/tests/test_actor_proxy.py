"""Tests for ActorProxy — generalist wrapper for the actor interface."""

from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from pydantic import Field

from n3tx_actors.actor import Actor
from n3tx_actors.actor_proxy import ActorProxy, ActorLike
from n3tx_actors.tx import TX
from .conftest import make_tx

pytestmark = pytest.mark.unit


# ===================================================================
# Address resolution
# ===================================================================

class TestActorProxyAddr:
    """Address resolution from various target types."""

    def test_explicit_addr(self):
        proxy = ActorProxy("anything", addr='custom')
        assert proxy.addr == 'custom'

    def test_class_with_addr(self):
        class MyActor(Actor, auto_register=False):
            __addr__ = 'my_addr'
        proxy = ActorProxy(MyActor)
        assert proxy.addr == 'my_addr'

    def test_class_with_tablename(self):
        class Model:
            __tablename__ = 'products'
        proxy = ActorProxy(Model)
        assert proxy.addr == 'products'

    def test_class_fallback_to_name(self):
        class Plain:
            pass
        proxy = ActorProxy(Plain)
        assert proxy.addr == 'Plain'

    def test_instance_with_addr_property(self):
        class HasAddr:
            @property
            def addr(self):
                return 'inst_addr'
        proxy = ActorProxy(HasAddr())
        assert proxy.addr == 'inst_addr'

    def test_instance_fallback_to_classname(self):
        class NoAddr:
            pass
        proxy = ActorProxy(NoAddr())
        assert proxy.addr == 'NoAddr'

    def test_proxy_wrapping_proxy(self):
        inner = ActorProxy("x", addr='inner')
        outer = ActorProxy(inner)
        assert outer.addr == 'inner'


# ===================================================================
# Properties
# ===================================================================

class TestActorProxyProperties:
    """Basic properties."""

    def test_target(self):
        obj = {"data": 42}
        proxy = ActorProxy(obj, addr='p')
        assert proxy.target is obj

    def test_children_starts_empty(self):
        proxy = ActorProxy("x", addr='p')
        assert proxy.children == {}

    def test_parent_default_none(self):
        proxy = ActorProxy("x", addr='p')
        assert proxy.parent is None

    def test_parent_setter(self):
        parent = ActorProxy("x", addr='parent')
        child = ActorProxy("y", addr='child')
        child.parent = parent
        assert child.parent is parent


# ===================================================================
# Handler dispatch
# ===================================================================

class CapturingProxy(ActorProxy):
    """ActorProxy subclass that captures inbox messages for testing."""

    __slots__ = ('_captured',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._captured = []

    async def inbox(self, tx):
        self._captured.append(tx)


class TestActorProxyHandler:
    """handler() dispatches to methods on the wrapped target."""

    @pytest.mark.asyncio
    async def test_sync_method_dict_return(self):
        class Target:
            def GREET(self, data, tx):
                return {'hello': data.get('name', 'world')}

        root = CapturingProxy("root", addr='root')
        proxy = root.register(ActorProxy(Target(), addr='t'))

        await proxy.handler(make_tx('GREET', target='t', data={'name': 'Alice'}))
        assert root._captured[0].data == {'hello': 'Alice'}
        assert root._captured[0].name == 'GREET_RESPONSE'

    @pytest.mark.asyncio
    async def test_async_method(self):
        class Target:
            async def COMPUTE(self, data, tx):
                return {'result': data.get('x', 0) * 2}

        root = CapturingProxy("root", addr='root')
        proxy = root.register(ActorProxy(Target(), addr='t'))

        await proxy.handler(make_tx('COMPUTE', target='t', data={'x': 5}))
        assert root._captured[0].data == {'result': 10}

    @pytest.mark.asyncio
    async def test_classmethod_dispatch(self):
        class Product:
            __tablename__ = 'products'
            @classmethod
            def SCHEMA(cls, data, tx):
                return {'schema': cls.__tablename__}

        root = CapturingProxy("root", addr='root')
        proxy = root.register(ActorProxy(Product, addr='products'))

        await proxy.handler(make_tx('SCHEMA', target='products'))
        assert root._captured[0].data == {'schema': 'products'}

    @pytest.mark.asyncio
    async def test_unhandled_message(self):
        root = CapturingProxy("root", addr='root')
        proxy = root.register(ActorProxy("empty", addr='e'))

        await proxy.handler(make_tx('NONEXISTENT', target='e'))
        assert root._captured[0].name == 'ERROR'
        assert 'Unhandled' in root._captured[0].data['message']

    @pytest.mark.asyncio
    async def test_exception_sends_error(self):
        class Broken:
            def BOOM(self, data, tx):
                raise ValueError("kaboom")

        root = CapturingProxy("root", addr='root')
        proxy = root.register(ActorProxy(Broken(), addr='b'))

        await proxy.handler(make_tx('BOOM', target='b'))
        assert root._captured[0].name == 'ERROR'
        assert 'kaboom' in root._captured[0].data['message']


# ===================================================================
# Inbox routing
# ===================================================================

class TestActorProxyInbox:
    """inbox() — 3-case routing: children → self → bubble up."""

    @pytest.mark.asyncio
    async def test_exact_child_match(self):
        parent = ActorProxy("p", addr='parent')
        child = CapturingProxy("c", addr='child')
        parent.register(child)

        tx = make_tx(target='child')
        await parent.inbox(tx)
        assert len(child._captured) == 1

    @pytest.mark.asyncio
    async def test_segment_based_routing(self):
        """parent addr='products', target='products/42' → routes to child '42'."""
        root = CapturingProxy("root", addr='root')
        parent = root.register(ActorProxy("p", addr='products'))
        child = CapturingProxy("c", addr='42')
        parent.register(child)

        tx = make_tx(target='products/42')
        await parent.inbox(tx)
        assert len(child._captured) == 1

    @pytest.mark.asyncio
    async def test_self_handle(self):
        """Target matches own addr → handler() called."""
        class Target:
            def PING(self, data, tx):
                return {'pong': True}

        root = CapturingProxy("root", addr='root')
        proxy = root.register(ActorProxy(Target(), addr='t'))

        await proxy.inbox(make_tx('PING', target='t'))
        assert root._captured[0].data == {'pong': True}

    @pytest.mark.asyncio
    async def test_bubble_up_to_parent(self):
        root = CapturingProxy("root", addr='root')
        child = root.register(ActorProxy("c", addr='child'))

        tx = make_tx(target='unknown')
        await child.inbox(tx)
        assert len(root._captured) == 1

    @pytest.mark.asyncio
    async def test_no_parent_no_route_logs_warning(self):
        proxy = ActorProxy("orphan", addr='orphan')
        tx = make_tx(target='elsewhere')
        with patch('n3tx_actors.actor_proxy.logger') as mock_logger:
            await proxy.inbox(tx)
            mock_logger.warning.assert_called_once()


# ===================================================================
# Send
# ===================================================================

class TestActorProxySend:
    """send() routes through parent."""

    @pytest.mark.asyncio
    async def test_send_routes_to_parent(self):
        root = CapturingProxy("root", addr='root')
        child = root.register(ActorProxy("c", addr='child'))

        tx = make_tx(target='somewhere')
        await child.send(tx)
        assert len(root._captured) == 1

    @pytest.mark.asyncio
    async def test_send_no_parent_raises(self):
        proxy = ActorProxy("orphan", addr='orphan')
        with pytest.raises(RuntimeError, match="No parent"):
            await proxy.send(make_tx(target='x'))


# ===================================================================
# Child management
# ===================================================================

class TestActorProxyRegister:
    """register() and spawn()."""

    def test_register_proxy(self):
        parent = ActorProxy("p", addr='p')
        child = ActorProxy("c", addr='c')
        result = parent.register(child)
        assert result is child
        assert 'c' in parent.children
        assert child.parent is parent

    def test_register_auto_wraps_non_proxy(self):
        parent = ActorProxy("p", addr='p')
        plain = MagicMock()
        plain.__class__.__name__ = 'PlainObj'
        result = parent.register(plain)
        assert isinstance(result, ActorProxy)
        assert result.target is plain
        assert result.parent is parent

    def test_spawn(self):
        parent = ActorProxy("p", addr='p')
        child = parent.spawn("target", addr='c')
        assert 'c' in parent.children
        assert child.parent is parent

    def test_spawn_duplicate_raises(self):
        parent = ActorProxy("p", addr='p')
        parent.spawn("t1", addr='c')
        with pytest.raises(ValueError, match="already exists"):
            parent.spawn("t2", addr='c')

    def test_has(self):
        parent = ActorProxy("p", addr='p')
        parent.register(ActorProxy("c", addr='worker'))
        assert parent.has('worker') is True
        assert parent.has('worker/sub') is True
        assert parent.has('nope') is False


# ===================================================================
# ActorLike Protocol
# ===================================================================

class TestActorLikeProtocol:
    """ActorProxy satisfies the ActorLike Protocol."""

    def test_proxy_is_actorlike(self):
        proxy = ActorProxy("x", addr='p')
        assert isinstance(proxy, ActorLike)

    def test_actor_instance_is_actorlike(self):
        """Actor instances also satisfy ActorLike (structural typing)."""
        a = Actor(addr='a')
        assert isinstance(a, ActorLike)


# ===================================================================
# Repr
# ===================================================================

class TestActorProxyRepr:
    """__repr__ for debugging."""

    def test_class_target_repr(self):
        class MyClass: pass
        proxy = ActorProxy(MyClass, addr='mc')
        r = repr(proxy)
        assert 'MyClass' in r
        assert 'class' in r
        assert 'mc' in r

    def test_instance_target_repr(self):
        class MyClass: pass
        proxy = ActorProxy(MyClass(), addr='mi')
        r = repr(proxy)
        assert 'MyClass' in r
        assert 'instance' in r
        assert 'mi' in r
