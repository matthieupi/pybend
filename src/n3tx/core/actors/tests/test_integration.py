"""Integration tests — end-to-end message routing through actor trees."""

import pytest
from pydantic import Field

from n3tx.core.actors.actor import Actor, actormethod
from n3tx.core.actors.matrix import Matrix
from n3tx.core.actors.actor_proxy import ActorProxy
from n3tx.core.actors.tx import TX
from .conftest import mock_method, make_tx

pytestmark = pytest.mark.unit


class TestMatrixToClassChild:
    """Matrix routes to auto-registered class children."""

    @pytest.mark.asyncio
    async def test_matrix_routes_to_class_via_handler(self):
        """Matrix.inbox(tx) → class child.inbox(tx) → classmethod dispatch."""
        m = Matrix()
        sent = []

        class Product(Actor):
            __tablename__ = 'products'

            @classmethod
            def SCHEMA(cls, data, tx):
                return {'name': cls.addr, 'type': 'schema'}

        # Capture sends at the matrix level
        async def cap(tx):
            sent.append(tx)
        with mock_method(m, 'inbox', cap):
            # Manually invoke what Matrix.inbox would do
            child = m._children.get('products')
            assert child is Product
            await Product.handler(make_tx('SCHEMA', target='products'))

        assert sent[0].data == {'name': 'products', 'type': 'schema'}


class TestMatrixToInstanceChild:
    """Matrix routes to registered instance children."""

    @pytest.mark.asyncio
    async def test_routes_to_instance(self):
        m = Matrix()

        class Worker(Actor, auto_register=False):
            name: str = Field(default='')

            def DUMP(self, data, tx):
                return {'name': self.name, 'addr': self.addr}

        w = Worker(name='Widget', addr='w1')
        m.register(w)

        sent = []
        async def cap(tx): sent.append(tx)
        with mock_method(m, 'inbox', cap):
            await w.handler(make_tx('DUMP', target='w1'))

        assert sent[0].data == {'name': 'Widget', 'addr': 'w1'}


class TestMultiLevelRouting:
    """Messages route through multiple actor levels."""

    @pytest.mark.asyncio
    async def test_parent_child_handler_dispatch(self):
        """Child handler dispatches correctly, reply captured at send level."""
        m = Matrix()
        parent = Actor(addr='parent')
        m.register(parent)

        class Child(Actor, auto_register=False):
            def PING(self, data, tx):
                return {'pong': True, 'from': self.addr}

        child = Child(addr='child')
        parent.register(child)

        # Capture at child.send — before reply enters routing tree
        sent = []
        async def cap(tx): sent.append(tx)
        with mock_method(child, 'send', cap):
            await child.handler(make_tx('PING', source='client', target='child'))

        assert sent[0].data == {'pong': True, 'from': 'child'}
        assert sent[0].name == 'PING_RESPONSE'

    @pytest.mark.asyncio
    async def test_child_send_routes_through_parent_chain(self):
        """Message from child bubbles: child → parent → class → matrix."""
        m = Matrix()
        parent = Actor(addr='parent')
        m.register(parent)
        child = Actor(addr='child')
        parent.register(child)

        assert child.parent is parent
        assert parent.parent is m  # set by m.register(parent)

        # Sending from child should reach matrix via parent chain
        received = []
        async def cap(tx): received.append(tx)

        tx = make_tx(source='child', target='somewhere')
        with mock_method(m, 'inbox', cap):
            await child.send(tx)

        assert len(received) == 1


class TestClassAndInstanceCoexistence:
    """Class actors and instance actors coexist in the same tree."""

    @pytest.mark.asyncio
    async def test_class_and_instance_same_matrix(self):
        m = Matrix()

        class Product(Actor):
            __tablename__ = 'products'

            @classmethod
            def SCHEMA(cls, data, tx):
                return {'schema': True}

        # Product class auto-registered as 'products'
        assert 'products' in m._children

        # Also register an instance
        worker = Actor(addr='worker')
        m.register(worker)
        assert 'worker' in m._children

        # Both coexist
        assert len(m._children) >= 2


class TestProxyInActorTree:
    """ActorProxy integrates with Actor/Matrix tree."""

    @pytest.mark.asyncio
    async def test_proxy_as_matrix_child(self):
        """Proxy registered with matrix, receives messages."""
        m = Matrix()

        class Service:
            def HEALTH(self, data, tx):
                return {'status': 'ok'}

        proxy = m.register(ActorProxy(Service(), addr='health'))

        sent = []
        async def cap(tx): sent.append(tx)
        with mock_method(m, 'inbox', cap):
            await proxy.handler(make_tx('HEALTH', target='health'))

        assert sent[0].data == {'status': 'ok'}

    @pytest.mark.asyncio
    async def test_proxy_tree_routing(self):
        """Proxy-based tree routes messages through parent chain."""
        from .test_actor_proxy import CapturingProxy

        root = CapturingProxy("root", addr='root')

        class Calculator:
            def ADD(self, data, tx):
                return {'sum': data.get('a', 0) + data.get('b', 0)}

        calc = root.register(ActorProxy(Calculator(), addr='calc'))

        await calc.handler(make_tx('ADD', target='calc', data={'a': 3, 'b': 4}))
        assert root._captured[0].data == {'sum': 7}


class TestPydanticCompatibility:
    """Actor system works correctly with Pydantic models."""

    def test_model_dump_excludes_actor_state(self):
        class Item(Actor, auto_register=False):
            name: str = Field(default='')
            price: float = Field(default=0.0)

        item = Item(name='Widget', price=9.99, addr='item/1')
        d = item.model_dump()
        assert d == {'name': 'Widget', 'price': 9.99}
        assert 'addr' not in d
        assert '_children' not in d
        assert '_parent' not in d

    def test_model_fields_work(self):
        class Item(Actor, auto_register=False):
            name: str = Field(min_length=1)
            count: int = Field(default=0, ge=0)

        item = Item(name='Test', count=5, addr='i')
        assert item.name == 'Test'
        assert item.count == 5

    def test_model_validation(self):
        from pydantic import ValidationError

        class Strict(Actor, auto_register=False):
            name: str = Field(min_length=1)

        with pytest.raises(ValidationError):
            Strict(name='', addr='s')

    def test_multiple_subclasses_independent(self):
        class A(Actor, auto_register=False):
            x: int = Field(default=0)

        class B(Actor, auto_register=False):
            y: str = Field(default='')

        a = A(x=1, addr='a')
        b = B(y='hello', addr='b')
        assert a.model_dump() == {'x': 1}
        assert b.model_dump() == {'y': 'hello'}
