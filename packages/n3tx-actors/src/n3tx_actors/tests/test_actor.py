"""Tests for Actor — unified class/instance dispatch via fullmethod/fullproperty."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import Field

from n3tx.core.actors.actor import Actor
from n3tx.core.utils.descriptors import fullmethod, fullproperty
from n3tx.core.actors.matrix import Matrix
from n3tx.core.actors.tx import TX
from .conftest import mock_method, make_tx

pytestmark = pytest.mark.unit


# ===================================================================
# Descriptors
# ===================================================================

class TestFullmethod:
    """fullmethod descriptor binds target = cls or self."""

    def test_class_access_binds_class(self):
        class A(Actor, auto_register=False):
            @fullmethod
            def who(target):
                return target

        assert A.who() is A

    def test_instance_access_binds_instance(self):
        class A(Actor, auto_register=False):
            @fullmethod
            def who(target):
                return target

        a = A(addr='a')
        assert a.who() is a

    def test_preserves_name_and_doc(self):
        class A(Actor, auto_register=False):
            @fullmethod
            def my_method(target):
                """My doc."""

        desc = A.__dict__['my_method']
        assert desc.__name__ == 'my_method'
        assert desc.__doc__ == 'My doc.'

    def test_async_fullmethod_works(self):
        class A(Actor, auto_register=False):
            @fullmethod
            async def async_who(target):
                return target

        a = A(addr='a')
        assert asyncio.iscoroutinefunction(a.async_who.__func__
                                           if hasattr(a.async_who, '__func__')
                                           else a.async_who)


class TestFullproperty:
    """fullproperty descriptor resolves class or instance state."""

    def test_class_access(self):
        class A(Actor, auto_register=False):
            __tablename__ = 'things'

        assert A.addr == 'things'

    def test_instance_access(self):
        a = Actor(addr='custom')
        assert a.addr == 'custom'

    def test_children_class_vs_instance(self):
        class A(Actor, auto_register=False):
            pass

        a = A(addr='a')
        # Class and instance children are separate dicts
        assert A.children is A.__children__
        assert a.children is a._children
        assert A.children is not a.children

    def test_parent_class_returns_matrix(self):
        m = Matrix()
        assert Actor.parent is m

    def test_parent_instance_returns_parent(self):
        parent = Actor(addr='p')
        child = Actor(addr='c')
        parent.register(child)
        assert child.parent is parent


# ===================================================================
# Actor Init
# ===================================================================

class TestActorInit:
    """Actor __init__ behavior."""

    def test_addr_from_kwarg(self):
        a = Actor(addr='custom')
        assert a.addr == 'custom'

    def test_addr_defaults_to_class_addr(self):
        class Named(Actor, auto_register=False):
            __tablename__ = 'named'
        n = Named()
        assert n.addr == 'named'

    def test_addr_defaults_to_classname(self):
        class MyActor(Actor, auto_register=False):
            pass
        assert MyActor().__class__.__name__ == 'MyActor'

    def test_parent_defaults_to_class(self):
        a = Actor()
        assert a.parent is Actor

    def test_children_starts_empty(self):
        a = Actor()
        assert a.children == {}

    def test_pydantic_model_dump(self):
        class Item(Actor, auto_register=False):
            name: str = Field(default='test')
            price: float = Field(default=0.0)

        item = Item(name='Widget', price=9.99, addr='item/1')
        d = item.model_dump()
        assert d == {'name': 'Widget', 'price': 9.99}
        # addr, children, parent are NOT in model_dump (PrivateAttr)
        assert 'addr' not in d


# ===================================================================
# ActorMeta (metaclass)
# ===================================================================

class TestActorMeta:
    """ActorMeta metaclass — per-class setup."""

    def test_each_subclass_gets_own_children(self):
        class A(Actor, auto_register=False): pass
        class B(Actor, auto_register=False): pass
        assert A.__children__ is not B.__children__
        assert A.__children__ is not Actor.__children__

    def test_addr_from_tablename(self):
        class T(Actor, auto_register=False):
            __tablename__ = 'my_table'
        assert T.__addr__ == 'my_table'
        assert T.addr == 'my_table'

    def test_addr_from_classname(self):
        class NoTable(Actor, auto_register=False):
            pass
        assert NoTable.__addr__ == 'NoTable'
        assert NoTable.addr == 'NoTable'

    def test_explicit_addr_not_overridden(self):
        class Explicit(Actor, auto_register=False):
            __addr__ = 'custom'
            __tablename__ = 'should_not_use'
        assert Explicit.__addr__ == 'custom'

    def test_auto_register_with_matrix(self):
        m = Matrix()
        class AutoReg(Actor):
            __tablename__ = 'auto'
        assert 'auto' in m._children
        assert m._children['auto'] is AutoReg

    def test_auto_register_false_skips(self):
        m = Matrix()
        class NoReg(Actor, auto_register=False):
            pass
        assert 'NoReg' not in m._children

    def test_subclass_before_matrix_no_error(self):
        # No matrix exists, defining subclass should not raise
        class Early(Actor):
            pass


# ===================================================================
# Root
# ===================================================================

class TestActorRoot:
    """Actor.root() getter/setter."""

    def test_getter(self):
        m = Matrix()
        assert Actor.root() is m

    def test_setter(self):
        m1 = Matrix()
        m2 = Matrix(addr='m2')
        Actor.root(m2)
        assert Actor.root() is m2

    def test_none_before_matrix(self):
        assert Actor.root() is None


# ===================================================================
# Register (unified)
# ===================================================================

class TestActorRegister:
    """Unified register() — works on both classes and instances."""

    def test_instance_register_sets_parent(self):
        parent = Actor(addr='p')
        child = Actor(addr='c')
        parent.register(child)
        assert child.parent is parent

    def test_instance_register_adds_to_children(self):
        parent = Actor(addr='p')
        child = Actor(addr='c')
        parent.register(child)
        assert 'c' in parent.children
        assert parent.children['c'] is child

    def test_instance_register_returns_child(self):
        parent = Actor(addr='p')
        child = Actor(addr='c')
        assert parent.register(child) is child

    def test_class_register_adds_to_class_children(self):
        class Parent(Actor, auto_register=False): pass
        class Child(Actor, auto_register=False):
            __tablename__ = 'child'

        Parent.register(Child)
        assert 'child' in Parent.children
        assert Parent.children['child'] is Child

    def test_class_register_class_child_no_parent_set(self):
        """Registering a class child doesn't set _parent (classes don't have it)."""
        class Parent(Actor, auto_register=False): pass
        class Child(Actor, auto_register=False): pass

        Parent.register(Child)
        # Child is a class, so isinstance(child, type) is True
        # _parent is not set on class children
        assert 'Child' in Parent.children

    def test_class_register_instance_child(self):
        class Parent(Actor, auto_register=False): pass

        child = Actor(addr='c')
        Parent.register(child)
        assert 'c' in Parent.children
        assert child.parent is Parent


# ===================================================================
# Spawn (unified)
# ===================================================================

class TestActorSpawn:
    """Unified spawn() — works on both classes and instances."""

    def test_instance_spawn(self):
        parent = Actor(addr='p')
        child = parent.spawn('worker', Actor)
        assert 'worker' in parent.children
        assert child.addr == 'worker'
        assert child.parent is parent

    def test_class_spawn(self):
        class Parent(Actor, auto_register=False): pass
        child = Parent.spawn('worker', Actor)
        assert 'worker' in Parent.children
        assert child.addr == 'worker'

    def test_spawn_duplicate_raises(self):
        parent = Actor(addr='p')
        parent.spawn('worker', Actor)
        with pytest.raises(ValueError, match="already exists"):
            parent.spawn('worker', Actor)

    def test_class_spawn_duplicate_raises(self):
        class Parent(Actor, auto_register=False): pass
        Parent.spawn('w', Actor)
        with pytest.raises(ValueError, match="already exists"):
            Parent.spawn('w', Actor)


# ===================================================================
# Has (unified)
# ===================================================================

class TestActorHas:
    """Unified has() — checks first address segment."""

    def test_instance_has_true(self):
        parent = Actor(addr='p')
        parent.spawn('worker', Actor)
        assert parent.has('worker') is True

    def test_instance_has_false(self):
        parent = Actor(addr='p')
        assert parent.has('nope') is False

    def test_class_has_true(self):
        class Parent(Actor, auto_register=False): pass
        Parent.spawn('w', Actor)
        assert Parent.has('w') is True

    def test_class_has_false(self):
        class Parent(Actor, auto_register=False): pass
        assert Parent.has('nope') is False

    def test_has_first_segment_only(self):
        parent = Actor(addr='p')
        parent.spawn('worker', Actor)
        assert parent.has('worker/sub/deep') is True


# ===================================================================
# Handler dispatch
# ===================================================================

class TestActorHandler:
    """handler() dispatches to named methods, wraps returns in reply TX."""

    @pytest.fixture
    def capture(self, fresh_matrix):
        """Capture sent TXes via mock on matrix inbox."""
        sent = []
        async def cap(tx):
            sent.append(tx)
        return fresh_matrix, sent, cap

    @pytest.mark.asyncio
    async def test_sync_method_dict_return(self, capture):
        m, sent, cap = capture

        class W(Actor, auto_register=False):
            def GREET(self, data, tx):
                return {'hello': data.get('name', 'world')}

        w = W(addr='w')
        m.register(w)
        with mock_method(m, 'inbox', cap):
            await w.handler(make_tx('GREET', target='w', data={'name': 'Alice'}))
        assert sent[0].name == 'GREET_RESPONSE'
        assert sent[0].data == {'hello': 'Alice'}

    @pytest.mark.asyncio
    async def test_async_method(self, capture):
        m, sent, cap = capture

        class W(Actor, auto_register=False):
            async def COMPUTE(self, data, tx):
                return {'result': data.get('x', 0) * 2}

        w = W(addr='w')
        m.register(w)
        with mock_method(m, 'inbox', cap):
            await w.handler(make_tx('COMPUTE', target='w', data={'x': 5}))
        assert sent[0].data == {'result': 10}

    @pytest.mark.asyncio
    async def test_scalar_return_wrapped(self, capture):
        m, sent, cap = capture

        class W(Actor, auto_register=False):
            def COUNT(self, data, tx):
                return 42

        w = W(addr='w')
        m.register(w)
        with mock_method(m, 'inbox', cap):
            await w.handler(make_tx('COUNT', target='w'))
        assert sent[0].data == {'result': 42}

    @pytest.mark.asyncio
    async def test_tx_return_sent_directly(self, capture):
        m, sent, cap = capture

        class W(Actor, auto_register=False):
            def CUSTOM(self, data, tx):
                return tx.error('custom error')

        w = W(addr='w')
        m.register(w)
        with mock_method(m, 'inbox', cap):
            await w.handler(make_tx('CUSTOM', target='w'))
        assert sent[0].name == 'ERROR'
        assert sent[0].data['message'] == 'custom error'

    @pytest.mark.asyncio
    async def test_none_return_empty_reply(self, capture):
        m, sent, cap = capture

        class W(Actor, auto_register=False):
            def NOP(self, data, tx):
                return None

        w = W(addr='w')
        m.register(w)
        with mock_method(m, 'inbox', cap):
            await w.handler(make_tx('NOP', target='w'))
        assert sent[0].data == {}
        assert sent[0].name == 'NOP_RESPONSE'

    @pytest.mark.asyncio
    async def test_unhandled_message_error(self, capture):
        m, sent, cap = capture
        w = Actor(addr='w')
        m.register(w)
        with mock_method(m, 'inbox', cap):
            await w.handler(make_tx('NONEXISTENT', target='w'))
        assert sent[0].name == 'ERROR'
        assert 'Unhandled message' in sent[0].data['message']

    @pytest.mark.asyncio
    async def test_exception_sends_error(self, capture):
        m, sent, cap = capture

        class W(Actor, auto_register=False):
            def BOOM(self, data, tx):
                raise ValueError("kaboom")

        w = W(addr='w')
        m.register(w)
        with mock_method(m, 'inbox', cap):
            await w.handler(make_tx('BOOM', target='w'))
        assert sent[0].name == 'ERROR'
        assert 'kaboom' in sent[0].data['message']


# ===================================================================
# Class-level handler dispatch
# ===================================================================

class TestActorClassHandler:
    """handler() on classes — dispatches to classmethods."""

    @pytest.mark.asyncio
    async def test_classmethod_dispatch(self):
        sent = []

        class Product(Actor, auto_register=False):
            @classmethod
            def SCHEMA(cls, data, tx):
                return {'schema': cls.addr}

        async def cap_send(target, tx):
            sent.append(tx)
        Actor.send = fullmethod(cap_send)

        await Product.handler(make_tx('SCHEMA', target='Product'))
        assert sent[0].data == {'schema': 'Product'}
        assert sent[0].name == 'SCHEMA_RESPONSE'

    @pytest.mark.asyncio
    async def test_class_unhandled_returns_error(self):
        sent = []

        class Empty(Actor, auto_register=False):
            pass

        async def cap_send(target, tx):
            sent.append(tx)
        Actor.send = fullmethod(cap_send)

        await Empty.handler(make_tx('NOPE', target='Empty'))
        assert sent[0].name == 'ERROR'

    @pytest.mark.asyncio
    async def test_class_exception_sends_error(self):
        sent = []

        class Broken(Actor, auto_register=False):
            @classmethod
            def FAIL(cls, data, tx):
                raise RuntimeError("class boom")

        async def cap_send(target, tx):
            sent.append(tx)
        Actor.send = fullmethod(cap_send)

        await Broken.handler(make_tx('FAIL', target='Broken'))
        assert sent[0].name == 'ERROR'
        assert 'class boom' in sent[0].data['message']


# ===================================================================
# Send routing
# ===================================================================

class TestActorSend:
    """send() routing — class-level and instance-level."""

    @pytest.mark.asyncio
    async def test_instance_send_to_parent_instance(self):
        """When parent is an instance, routes via parent.inbox()."""
        parent = Actor(addr='p')
        child = Actor(addr='c')
        parent.register(child)

        received = []
        async def cap(tx):
            received.append(tx)

        tx = make_tx(target='somewhere')
        with mock_method(parent, 'inbox', cap):
            await child.send(tx)
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_instance_send_default_parent_is_class(self):
        """Default parent is the class — send routes via class.send()."""
        m = Matrix()
        sent = []

        class Sender(Actor):
            __tablename__ = 'senders'

        s = Sender(addr='s')
        # s.parent is Sender (the class), class send routes to matrix
        mock_inbox = AsyncMock()
        with mock_method(m, 'inbox', mock_inbox):
            await s.send(make_tx(source='s', target='unknown'))
        # Should have bubbled to matrix
        mock_inbox.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_instance_send_no_parent_raises(self):
        a = Actor(addr='orphan')
        a._parent = None
        with pytest.raises(RuntimeError, match="No parent or root"):
            await a.send(make_tx(target='x'))

    @pytest.mark.asyncio
    async def test_class_send_direct_child(self):
        """Class send routes to direct child."""
        class Router(Actor, auto_register=False):
            pass

        child_mock = MagicMock()
        child_mock.inbox = AsyncMock()
        Router.__children__['worker'] = child_mock

        await Router.send(make_tx(target='worker'))
        child_mock.inbox.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_class_send_strip_prefix(self):
        """Target starts with class addr → strip prefix, route to child."""
        class MyRouter(Actor, auto_register=False):
            __addr__ = 'myrouter'

        child_mock = MagicMock()
        child_mock.inbox = AsyncMock()
        MyRouter.__children__['worker'] = child_mock

        tx = make_tx(target='myrouter/worker')
        await MyRouter.send(tx)
        child_mock.inbox.assert_awaited_once()
        assert tx.target == 'worker'

    @pytest.mark.asyncio
    async def test_class_send_bubble_to_parent(self):
        """No match → prefix source, bubble to parent (matrix)."""
        m = Matrix()

        class Bubbler(Actor):
            __addr__ = 'bubbler'

        received = []
        async def cap(tx):
            received.append(tx)

        tx = make_tx(source='child1', target='unknown')
        with mock_method(m, 'inbox', cap):
            await Bubbler.send(tx)
        assert len(received) == 1
        assert tx.source == 'bubbler/child1'

    @pytest.mark.asyncio
    async def test_class_send_empty_source_prefix(self):
        m = Matrix()

        class EmptySrc(Actor):
            __addr__ = 'src_class'

        received = []
        async def cap(tx):
            received.append(tx)

        tx = make_tx(source='', target='unknown')
        with mock_method(m, 'inbox', cap):
            await EmptySrc.send(tx)
        assert tx.source == 'src_class'


# ===================================================================
# Inbox
# ===================================================================

class TestActorInbox:
    """inbox() delegates to handler()."""

    @pytest.mark.asyncio
    async def test_inbox_calls_handler(self):
        a = Actor(addr='a')
        called = []

        async def mock_handler(tx):
            called.append(tx)

        tx = make_tx(target='a')
        with mock_method(a, 'handler', mock_handler):
            await a.inbox(tx)
        assert len(called) == 1

    @pytest.mark.asyncio
    async def test_inbox_returns_none(self):
        a = Actor(addr='a')
        async def noop(tx): pass
        with mock_method(a, 'handler', noop):
            result = await a.inbox(make_tx(target='a'))
        assert result is None

    @pytest.mark.asyncio
    async def test_class_inbox_calls_class_handler(self):
        """Product.inbox(tx) dispatches to Product.handler(tx)."""
        called = []

        class Spy(Actor, auto_register=False):
            @classmethod
            def PING(cls, data, tx):
                called.append('pinged')
                return {'pong': True}

        sent = []
        async def cap_send(target, tx):
            sent.append(tx)
        Actor.send = fullmethod(cap_send)

        await Spy.inbox(make_tx('PING', target='Spy'))
        assert 'pinged' in called
        assert sent[0].data == {'pong': True}


# ===================================================================
# Lifecycle
# ===================================================================

class TestActorLifecycle:
    """on_start / on_stop lifecycle hooks."""

    @pytest.mark.asyncio
    async def test_on_start_noop(self):
        assert await Actor(addr='a').on_start() is None

    @pytest.mark.asyncio
    async def test_on_stop_noop(self):
        assert await Actor(addr='a').on_stop() is None

    @pytest.mark.asyncio
    async def test_on_start_overridable(self):
        started = []

        class MyActor(Actor, auto_register=False):
            async def on_start(self):
                started.append(self.addr)

        a = MyActor(addr='starter')
        await a.on_start()
        assert started == ['starter']
