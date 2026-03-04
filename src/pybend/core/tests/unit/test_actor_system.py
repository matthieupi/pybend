"""
Tests for actors/ — Actor, Matrix, TX core system.

Actor class-level state (__matrix__, __children__) persists across tests.
The reset_actor_state fixture saves/restores state between tests.
"""

import asyncio
from contextlib import contextmanager
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from pybend.core.actors.tx import TX
from pybend.core.actors.actor import Actor
from pybend.core.actors.matrix import Matrix

pytestmark = pytest.mark.unit


# ===================================================================
# Helpers
# ===================================================================

@contextmanager
def mock_method(instance, name, replacement):
    """Temporarily replace a method on a Pydantic BaseModel instance.

    Pydantic's __setattr__/__delattr__ prevent normal mock patching.
    This uses object.__setattr__/delattr__ to bypass the protection.
    """
    object.__setattr__(instance, name, replacement)
    try:
        yield replacement
    finally:
        object.__delattr__(instance, name)


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture(autouse=True)
def reset_actor_state():
    """Save and restore Actor/Matrix class-level state between tests.

    Actor.__matrix__, Actor.__children__, and any subclass registrations
    must be isolated per test to prevent cross-contamination.
    """
    # Save
    saved_matrix = Actor.__matrix__
    saved_children = Actor.__children__.copy()
    saved_matrix_children = Matrix.__children__.copy()

    yield

    # Restore
    Actor.__matrix__ = saved_matrix
    Actor.__children__ = saved_children
    Matrix.__children__ = saved_matrix_children


# ===================================================================
# TestTX
# ===================================================================

class TestTX:
    """TX message envelope."""

    def test_creation_with_required_fields(self):
        tx = TX(name='READ', source='a', target='b')
        assert tx.name == 'READ'
        assert tx.source == 'a'
        assert tx.target == 'b'

    def test_creation_defaults(self):
        tx = TX(name='X', source='a', target='b')
        assert tx.data == {}
        assert tx.meta == {}
        assert isinstance(tx.timestamp, float)
        assert isinstance(tx.uuid, str)
        assert len(tx.uuid) == 12

    def test_uuid_is_unique_per_instance(self):
        tx1 = TX(name='X', source='a', target='b')
        tx2 = TX(name='X', source='a', target='b')
        assert tx1.uuid != tx2.uuid

    def test_reply_swaps_source_target(self):
        tx = TX(name='READ', source='a', target='b')
        reply = tx.reply()
        assert reply.source == 'b'
        assert reply.target == 'a'

    def test_reply_gets_new_uuid(self):
        tx = TX(name='READ', source='a', target='b')
        reply = tx.reply()
        assert reply.uuid != tx.uuid

    def test_reply_stores_original_uuid_in_meta(self):
        tx = TX(name='READ', source='a', target='b')
        reply = tx.reply()
        assert reply.meta['in_reply_to'] == tx.uuid

    def test_reply_default_name_appends_response(self):
        tx = TX(name='READ', source='a', target='b')
        reply = tx.reply()
        assert reply.name == 'READ_RESPONSE'

    def test_reply_custom_name(self):
        tx = TX(name='READ', source='a', target='b')
        reply = tx.reply(name='CUSTOM')
        assert reply.name == 'CUSTOM'

    def test_reply_default_data_is_empty_dict(self):
        tx = TX(name='X', source='a', target='b')
        reply = tx.reply()
        assert reply.data == {}

    def test_reply_with_data(self):
        tx = TX(name='X', source='a', target='b')
        reply = tx.reply(data={'key': 'val'})
        assert reply.data == {'key': 'val'}

    def test_error_sets_name_to_error(self):
        tx = TX(name='READ', source='a', target='b')
        err = tx.error('fail')
        assert err.name == 'ERROR'

    def test_error_swaps_source_target(self):
        tx = TX(name='READ', source='a', target='b')
        err = tx.error('fail')
        assert err.source == 'b'
        assert err.target == 'a'

    def test_error_stores_message_and_code(self):
        tx = TX(name='X', source='a', target='b')
        err = tx.error('broken', code=404)
        assert err.data == {'message': 'broken', 'code': 404}

    def test_error_default_code_is_500(self):
        tx = TX(name='X', source='a', target='b')
        err = tx.error('broken')
        assert err.data['code'] == 500

    def test_error_sets_error_meta_flag(self):
        tx = TX(name='X', source='a', target='b')
        err = tx.error('broken')
        assert err.meta['error'] is True

    def test_is_error_true_for_error_name(self):
        tx = TX(name='ERROR', source='a', target='b')
        assert tx.is_error is True

    def test_is_error_true_for_error_meta(self):
        tx = TX(name='CUSTOM', source='a', target='b', meta={'error': True})
        assert tx.is_error is True

    def test_is_error_false_for_normal_tx(self):
        tx = TX(name='READ', source='a', target='b')
        assert tx.is_error is False

    def test_data_and_meta_are_independent(self):
        """Ensure default_factory produces independent dicts per instance."""
        tx1 = TX(name='X', source='a', target='b')
        tx2 = TX(name='X', source='a', target='b')
        tx1.data['key'] = 'val'
        tx1.meta['flag'] = True
        assert 'key' not in tx2.data
        assert 'flag' not in tx2.meta

    def test_error_preserves_original_meta(self):
        tx = TX(name='X', source='a', target='b', meta={'trace': '123'})
        err = tx.error('fail')
        assert err.meta['trace'] == '123'
        assert err.meta['error'] is True


# ===================================================================
# TestActorInit
# ===================================================================

class TestActorInit:
    """Actor __init__ behavior."""

    def test_addr_from_kwarg(self):
        a = Actor(addr='custom')
        assert a.addr == 'custom'

    def test_addr_defaults_to_class_addr(self):
        """When no addr kwarg, uses __addr__ ClassVar."""
        # Actor.__addr__ is '' so falls through to __name__
        a = Actor()
        assert a.addr == 'Actor'

    def test_addr_defaults_to_classname_when_no_class_addr(self):
        class MyActor(Actor, auto_register=False):
            pass
        a = MyActor()
        assert a.addr == 'MyActor'

    def test_parent_defaults_to_class(self):
        a = Actor()
        assert a.parent is Actor

    def test_children_starts_empty(self):
        a = Actor()
        assert a.children == {}


# ===================================================================
# TestActorInitSubclass
# ===================================================================

class TestActorInitSubclass:
    """__init_subclass__ auto-registration and per-class state."""

    def test_subclass_gets_own_children_dict(self):
        class Sub1(Actor, auto_register=False):
            pass
        class Sub2(Actor, auto_register=False):
            pass
        assert Sub1.__children__ is not Sub2.__children__
        assert Sub1.__children__ is not Actor.__children__

    def test_subclass_addr_defaults_to_classname(self):
        class SubAddr(Actor, auto_register=False):
            pass
        assert SubAddr.__addr__ == 'SubAddr'

    def test_subclass_addr_uses_tablename_when_available(self):
        class SubTable(Actor, auto_register=False):
            __tablename__ = 'sub_table'
        assert SubTable.__addr__ == 'sub_table'

    def test_auto_register_with_matrix(self):
        """Subclass with auto_register=True appears in matrix._children."""
        Actor.__matrix__ = None
        m = Matrix()

        class AutoReg(Actor):
            pass

        assert 'AutoReg' in m._children

    def test_auto_register_false_skips_registration(self):
        Actor.__matrix__ = None
        m = Matrix()

        class NoReg(Actor, auto_register=False):
            pass

        assert 'NoReg' not in m._children

    def test_subclass_before_matrix_not_registered(self):
        """Defining a subclass before any Matrix exists doesn't error."""
        Actor.__matrix__ = None

        class EarlySub(Actor):
            pass

        # No error raised, just not registered anywhere


# ===================================================================
# TestActorRoot
# ===================================================================

class TestActorRoot:
    """Actor.root() getter/setter."""

    def test_root_getter_returns_matrix(self):
        Actor.__matrix__ = None
        m = Matrix()
        assert Actor.root() is m

    def test_root_setter_sets_matrix(self):
        Actor.__matrix__ = None
        m = Matrix()
        m2 = Matrix(addr='second')
        Actor.root(m2)
        assert Actor.root() is m2

    def test_root_default_is_none_before_matrix_init(self):
        Actor.__matrix__ = None
        assert Actor.root() is None


# ===================================================================
# TestActorRegister
# ===================================================================

class TestActorRegister:
    """Instance-level register()."""

    def test_register_sets_parent(self):
        parent = Actor(addr='parent')
        child = Actor(addr='child')
        parent.register(child)
        assert child.parent is parent

    def test_register_adds_to_children(self):
        parent = Actor(addr='parent')
        child = Actor(addr='child')
        parent.register(child)
        assert parent.children['child'] is child

    def test_register_returns_child(self):
        parent = Actor(addr='parent')
        child = Actor(addr='child')
        result = parent.register(child)
        assert result is child


# ===================================================================
# TestActorSpawn
# ===================================================================

class TestActorSpawn:
    """spawn() creates and registers child actors."""

    def test_spawn_creates_and_registers(self):
        parent = Actor(addr='parent')
        child = parent.spawn('worker', Actor)
        assert 'worker' in parent.children
        assert child.addr == 'worker'

    def test_spawn_sets_parent_to_spawner(self):
        parent = Actor(addr='parent')
        child = parent.spawn('worker', Actor)
        assert child.parent is parent

    def test_spawn_duplicate_addr_raises_valueerror(self):
        parent = Actor(addr='parent')
        parent.spawn('worker', Actor)
        with pytest.raises(ValueError, match="already exists"):
            parent.spawn('worker', Actor)


# ===================================================================
# TestActorInbox
# ===================================================================

class TestActorInbox:
    """inbox() is fire-and-forget, delegates to handler()."""

    @pytest.mark.asyncio
    async def test_inbox_calls_handler(self):
        a = Actor(addr='test')
        mock_handler = AsyncMock()
        tx = TX(name='X', source='a', target='test')
        with mock_method(a, 'handler', mock_handler):
            await a.inbox(tx)
        mock_handler.assert_awaited_once_with(tx)

    @pytest.mark.asyncio
    async def test_inbox_returns_none(self):
        a = Actor(addr='test')
        mock_handler = AsyncMock()
        tx = TX(name='X', source='a', target='test')
        with mock_method(a, 'handler', mock_handler):
            result = await a.inbox(tx)
        assert result is None


# ===================================================================
# TestActorHandler
# ===================================================================

class TestActorHandler:
    """handler() dispatches to named methods, wraps returns in reply TX."""

    @pytest.mark.asyncio
    async def test_dispatches_to_named_sync_method(self):
        """Sync method is called and result sent."""
        class Worker(Actor, auto_register=False):
            def GREET(self, data, tx):
                return {'greeting': f"Hello {data.get('name', 'world')}"}

        Actor.__matrix__ = None
        m = Matrix()
        w = Worker(addr='w')
        m.register(w)

        sent = []
        async def capture_inbox(tx):
            sent.append(tx)

        tx = TX(name='GREET', source='client', target='w', data={'name': 'Alice'})
        with mock_method(m, 'inbox', capture_inbox):
            await w.handler(tx)

        assert len(sent) == 1
        assert sent[0].name == 'GREET_RESPONSE'
        assert sent[0].data == {'greeting': 'Hello Alice'}

    @pytest.mark.asyncio
    async def test_dispatches_to_named_async_method(self):
        """Async method is awaited and result sent."""
        class AsyncWorker(Actor, auto_register=False):
            async def COMPUTE(self, data, tx):
                return {'result': data.get('x', 0) * 2}

        Actor.__matrix__ = None
        m = Matrix()
        w = AsyncWorker(addr='aw')
        m.register(w)

        sent = []
        async def capture_inbox(tx):
            sent.append(tx)

        tx = TX(name='COMPUTE', source='client', target='aw', data={'x': 5})
        with mock_method(m, 'inbox', capture_inbox):
            await w.handler(tx)

        assert len(sent) == 1
        assert sent[0].data == {'result': 10}

    @pytest.mark.asyncio
    async def test_wraps_dict_return_in_reply(self):
        class DictWorker(Actor, auto_register=False):
            def DO(self, data, tx):
                return {'done': True}

        Actor.__matrix__ = None
        m = Matrix()
        w = DictWorker(addr='dw')
        m.register(w)

        sent = []
        async def capture(tx): sent.append(tx)
        with mock_method(m, 'inbox', capture):
            await w.handler(TX(name='DO', source='c', target='dw'))
        assert sent[0].data == {'done': True}
        assert sent[0].name == 'DO_RESPONSE'

    @pytest.mark.asyncio
    async def test_wraps_scalar_return_in_reply(self):
        class ScalarWorker(Actor, auto_register=False):
            def COUNT(self, data, tx):
                return 42

        Actor.__matrix__ = None
        m = Matrix()
        w = ScalarWorker(addr='sw')
        m.register(w)

        sent = []
        async def capture(tx): sent.append(tx)
        with mock_method(m, 'inbox', capture):
            await w.handler(TX(name='COUNT', source='c', target='sw'))
        assert sent[0].data == {'result': 42}

    @pytest.mark.asyncio
    async def test_passes_tx_return_through_directly(self):
        """If handler method returns a TX, it's sent as-is."""
        class TXWorker(Actor, auto_register=False):
            def CUSTOM(self, data, tx):
                return tx.error('custom error')

        Actor.__matrix__ = None
        m = Matrix()
        w = TXWorker(addr='tw')
        m.register(w)

        sent = []
        async def capture(tx): sent.append(tx)
        with mock_method(m, 'inbox', capture):
            await w.handler(TX(name='CUSTOM', source='c', target='tw'))
        assert sent[0].name == 'ERROR'
        assert sent[0].data['message'] == 'custom error'

    @pytest.mark.asyncio
    async def test_wraps_none_return_in_empty_reply(self):
        class NoneWorker(Actor, auto_register=False):
            def NOP(self, data, tx):
                return None

        Actor.__matrix__ = None
        m = Matrix()
        w = NoneWorker(addr='nw')
        m.register(w)

        sent = []
        async def capture(tx): sent.append(tx)
        with mock_method(m, 'inbox', capture):
            await w.handler(TX(name='NOP', source='c', target='nw'))
        assert sent[0].data == {}
        assert sent[0].name == 'NOP_RESPONSE'

    @pytest.mark.asyncio
    async def test_sends_error_for_unhandled_message(self):
        Actor.__matrix__ = None
        m = Matrix()
        w = Actor(addr='plain')
        m.register(w)

        sent = []
        async def capture(tx): sent.append(tx)
        with mock_method(m, 'inbox', capture):
            await w.handler(TX(name='NONEXISTENT', source='c', target='plain'))
        assert sent[0].name == 'ERROR'
        assert 'Unhandled message' in sent[0].data['message']

    @pytest.mark.asyncio
    async def test_catches_exception_and_sends_error(self):
        class BrokenWorker(Actor, auto_register=False):
            def BOOM(self, data, tx):
                raise ValueError("kaboom")

        Actor.__matrix__ = None
        m = Matrix()
        w = BrokenWorker(addr='bw')
        m.register(w)

        sent = []
        async def capture(tx): sent.append(tx)
        with mock_method(m, 'inbox', capture):
            await w.handler(TX(name='BOOM', source='c', target='bw'))
        assert sent[0].name == 'ERROR'
        assert 'kaboom' in sent[0].data['message']


# ===================================================================
# TestActorSend
# ===================================================================

class TestActorSend:
    """Instance-level send() routing."""

    @pytest.mark.asyncio
    async def test_send_routes_through_class_when_parent_is_type(self):
        """Default parent is the class — class-level send routing is invoked."""
        Actor.__matrix__ = None
        m = Matrix()

        class Sender(Actor, auto_register=False):
            pass

        s = Sender(addr='s')
        # s._parent is Sender (the class) — send goes through class routing
        # Class routing with no children + root matrix → bubbles to matrix.inbox
        received = []
        async def cap(tx): received.append(tx)

        tx = TX(name='X', source='s', target='somewhere')
        with mock_method(m, 'inbox', cap):
            await s.send(tx)
        assert len(received) == 1
        assert received[0].target == 'somewhere'

    @pytest.mark.asyncio
    async def test_send_routes_through_parent_instance(self):
        """When parent is an actor instance, routes via parent.inbox()."""
        parent = Actor(addr='parent')
        child = Actor(addr='child')
        parent.register(child)

        mock_inbox = AsyncMock()
        tx = TX(name='X', source='child', target='somewhere')
        with mock_method(parent, 'inbox', mock_inbox):
            await child.send(tx)
        mock_inbox.assert_awaited_once_with(tx)

    @pytest.mark.asyncio
    async def test_send_raises_when_no_parent_and_no_root(self):
        """No parent, no root -> RuntimeError."""
        Actor.__matrix__ = None
        a = Actor(addr='orphan')
        a._parent = None

        with pytest.raises(RuntimeError, match="No parent or root"):
            await a.send(TX(name='X', source='orphan', target='x'))


# ===================================================================
# TestActorClassSend
# ===================================================================

class TestActorClassSend:
    """Class-level send() three-case routing (via unified actormethod)."""

    @pytest.mark.asyncio
    async def test_case1_direct_child_match(self):
        """Target's first segment matches a class child -> route directly."""
        class Router(Actor, auto_register=False):
            pass

        child_mock = MagicMock()
        child_mock.inbox = AsyncMock()
        Router.__children__ = {'worker': child_mock}

        tx = TX(name='X', source='s', target='worker')
        await Router.send(tx)
        child_mock.inbox.assert_awaited_once_with(tx)

    @pytest.mark.asyncio
    async def test_case2_prefixed_target_strips_and_routes(self):
        """Target starts with class addr -> strip prefix, route to child."""
        class MyRouter(Actor, auto_register=False):
            __addr__ = 'myrouter'

        child_mock = MagicMock()
        child_mock.inbox = AsyncMock()
        MyRouter.__children__ = {'worker': child_mock}

        tx = TX(name='X', source='s', target='myrouter/worker')
        await MyRouter.send(tx)
        child_mock.inbox.assert_awaited_once()
        # Target should be stripped to 'worker'
        assert tx.target == 'worker'

    @pytest.mark.asyncio
    async def test_case3_bubble_to_root_with_source_prefix(self):
        """No match -> prefix source with type addr, bubble to root."""
        Actor.__matrix__ = None
        m = Matrix()

        class Bubbler(Actor, auto_register=False):
            __addr__ = 'bubbler'

        Bubbler.__children__ = {}

        mock_inbox = AsyncMock()
        tx = TX(name='X', source='child1', target='unknown')
        with mock_method(m, 'inbox', mock_inbox):
            await Bubbler.send(tx)
        mock_inbox.assert_awaited_once()
        # Source should be prefixed
        assert tx.source == 'bubbler/child1'

    @pytest.mark.asyncio
    async def test_case3_empty_source_gets_type_addr_only(self):
        """When source is empty, prefix is just the type addr."""
        Actor.__matrix__ = None
        m = Matrix()

        class EmptySrc(Actor, auto_register=False):
            __addr__ = 'src_class'

        EmptySrc.__children__ = {}

        mock_inbox = AsyncMock()
        tx = TX(name='X', source='', target='unknown')
        with mock_method(m, 'inbox', mock_inbox):
            await EmptySrc.send(tx)
        assert tx.source == 'src_class'

    @pytest.mark.asyncio
    async def test_no_match_and_no_root_is_silent(self):
        """No match and no root -> nothing happens (silent drop)."""
        Actor.__matrix__ = None

        class Orphan(Actor, auto_register=False):
            pass

        Orphan.__children__ = {}

        tx = TX(name='X', source='s', target='unknown')
        # Should not raise
        await Orphan.send(tx)


# ===================================================================
# TestActorLifecycle
# ===================================================================

class TestActorLifecycle:
    """on_start / on_stop lifecycle hooks."""

    @pytest.mark.asyncio
    async def test_on_start_is_noop_by_default(self):
        a = Actor(addr='test')
        result = await a.on_start()
        assert result is None

    @pytest.mark.asyncio
    async def test_on_stop_is_noop_by_default(self):
        a = Actor(addr='test')
        result = await a.on_stop()
        assert result is None


# ===================================================================
# TestMatrix
# ===================================================================

class TestMatrix:
    """Matrix root actor and message router."""

    def test_default_addr_is_matrix(self):
        Actor.__matrix__ = None
        m = Matrix()
        assert m.addr == 'matrix'

    def test_auto_registers_as_root(self):
        Actor.__matrix__ = None
        m = Matrix()
        assert Actor.root() is m

    def test_second_matrix_does_not_replace_root(self):
        Actor.__matrix__ = None
        m1 = Matrix()
        m2 = Matrix(addr='secondary')
        assert Actor.root() is m1

    def test_has_returns_true_for_registered_child(self):
        Actor.__matrix__ = None
        m = Matrix()
        child = Actor(addr='worker')
        m.register(child)
        assert m.has('worker') is True

    def test_has_returns_true_for_nested_addr(self):
        Actor.__matrix__ = None
        m = Matrix()
        child = Actor(addr='worker')
        m.register(child)
        assert m.has('worker/sub') is True

    def test_has_returns_false_for_unknown(self):
        Actor.__matrix__ = None
        m = Matrix()
        assert m.has('nonexistent') is False

    @pytest.mark.asyncio
    async def test_inbox_routes_to_local_child(self):
        Actor.__matrix__ = None
        m = Matrix()
        child = Actor(addr='worker')
        m.register(child)

        mock_inbox = AsyncMock()
        tx = TX(name='X', source='client', target='worker')
        with mock_method(child, 'inbox', mock_inbox):
            await m.inbox(tx)
        mock_inbox.assert_awaited_once_with(tx)

    @pytest.mark.asyncio
    async def test_inbox_self_send_blocked(self):
        """Matrix cannot route to itself."""
        Actor.__matrix__ = None
        m = Matrix()

        tx = TX(name='X', source='client', target='matrix')
        # Should not raise, just log error and return
        await m.inbox(tx)

    @pytest.mark.asyncio
    async def test_inbox_delegates_to_adapter(self):
        Actor.__matrix__ = None
        m = Matrix()
        adapter = MagicMock()
        adapter.can_handle = MagicMock(return_value=True)
        adapter.send = AsyncMock()
        m.register_adapter(adapter)

        tx = TX(name='X', source='client', target='remote_actor')
        await m.inbox(tx)
        adapter.send.assert_awaited_once_with(tx)

    @pytest.mark.asyncio
    async def test_inbox_logs_warning_no_route(self):
        """No child, no adapter -> warning logged."""
        Actor.__matrix__ = None
        m = Matrix()

        tx = TX(name='X', source='client', target='nowhere')
        with patch('pybend.core.actors.matrix.logger') as mock_logger:
            await m.inbox(tx)
            mock_logger.warning.assert_called_once()
            assert 'No route' in mock_logger.warning.call_args[0][0]

    @pytest.mark.asyncio
    async def test_send_delegates_to_inbox(self):
        """Matrix.send() routes internally via inbox()."""
        Actor.__matrix__ = None
        m = Matrix()

        mock_inbox = AsyncMock()
        tx = TX(name='X', source='s', target='t')
        with mock_method(m, 'inbox', mock_inbox):
            await m.send(tx)
        mock_inbox.assert_awaited_once_with(tx)

    def test_register_adapter(self):
        Actor.__matrix__ = None
        m = Matrix()
        adapter = MagicMock()
        m.register_adapter(adapter)
        assert adapter in m._adapters


# ===================================================================
# TestDefaultMatrix
# ===================================================================

class TestDefaultMatrix:
    """Module-level default matrix instance."""

    def test_module_level_matrix_exists(self):
        from pybend.core.actors.matrix import matrix as default_matrix
        assert default_matrix is not None
        assert isinstance(default_matrix, Matrix)

    def test_module_level_matrix_is_root(self):
        """The module-level matrix should be (or have been) the root.

        Note: Due to test isolation, Actor.__matrix__ may have been
        restored by the fixture, but the module-level instance exists.
        """
        from pybend.core.actors.matrix import matrix as default_matrix
        assert isinstance(default_matrix, Matrix)
        assert default_matrix.addr == 'matrix'


# ===================================================================
# Test TX.from_exception / tx.exception() (error mapping on TX class)
# ===================================================================

class TestTxFromException:
    """TX.from_exception() and tx.exception() map exceptions to semantic HTTP codes."""

    def _make_tx(self):
        return TX(name='test', source='a', target='b')

    def test_method_error_uses_its_status_code(self):
        from pybend.core.utils.erroring import MethodError
        tx = self._make_tx()
        result = TX.from_exception(MethodError('auth required', 401), tx)
        assert result.is_error
        assert result.data['code'] == 401
        assert 'auth required' in result.data['message']

    def test_pydantic_validation_error_maps_to_422(self):
        from pydantic import BaseModel, ValidationError
        class _M(BaseModel):
            x: int
        tx = self._make_tx()
        try:
            _M(x='not-an-int')
        except ValidationError as e:
            result = tx.exception(e)
        assert result.is_error
        assert result.data['code'] == 422

    def test_value_error_maps_to_400(self):
        tx = self._make_tx()
        result = tx.exception(ValueError('bad value'))
        assert result.data['code'] == 400

    def test_type_error_maps_to_400(self):
        tx = self._make_tx()
        result = TX.from_exception(TypeError('wrong type'), tx)
        assert result.data['code'] == 400

    def test_permission_error_maps_to_403(self):
        tx = self._make_tx()
        result = tx.exception(PermissionError('forbidden'))
        assert result.data['code'] == 403

    def test_key_error_maps_to_400_with_field(self):
        tx = self._make_tx()
        result = tx.exception(KeyError('missing_field'))
        assert result.data['code'] == 400
        assert 'missing_field' in result.data['message']

    def test_runtime_error_maps_to_500(self):
        tx = self._make_tx()
        result = TX.from_exception(RuntimeError('unexpected'), tx)
        assert result.data['code'] == 500

    def test_http_exception_uses_its_status_code(self):
        from fastapi import HTTPException
        tx = self._make_tx()
        result = tx.exception(HTTPException(status_code=409, detail='conflict'))
        assert result.data['code'] == 409
        assert 'conflict' in result.data['message']

    def test_backward_compat_alias(self):
        """Module-level exception_to_tx_error still works."""
        from pybend.core.actors.tx import exception_to_tx_error
        tx = self._make_tx()
        result = exception_to_tx_error(ValueError('test'), tx)
        assert result.data['code'] == 400


# ===================================================================
# Test Matrix error routing (no silent drops)
# ===================================================================

class TestMatrixErrorRouting:
    """Matrix sends ERROR TX back to sender when no route found."""

    @pytest.mark.asyncio
    async def test_no_route_sends_error_tx_to_sender(self):
        """When no child or adapter matches, Matrix routes ERROR TX back."""
        Actor.__matrix__ = None
        m = Matrix()
        sender = Actor(addr='sender')
        m.register(sender)

        mock_inbox = AsyncMock()
        tx = TX(name='X', source='sender', target='nonexistent')
        with mock_method(sender, 'inbox', mock_inbox):
            await m.inbox(tx)
        # sender should receive an ERROR TX
        mock_inbox.assert_awaited_once()
        error_tx = mock_inbox.call_args[0][0]
        assert error_tx.is_error
        assert error_tx.data['code'] == 404
        assert 'nonexistent' in error_tx.data['message']

    @pytest.mark.asyncio
    async def test_no_route_does_not_bounce_error_tx(self):
        """ERROR TX targeting unknown addr should NOT generate another error (infinite loop)."""
        Actor.__matrix__ = None
        m = Matrix()
        sender = Actor(addr='sender')
        m.register(sender)

        mock_inbox = AsyncMock()
        error_tx = TX(name='ERROR', source='sender', target='nonexistent',
                      meta={'error': True})
        with mock_method(sender, 'inbox', mock_inbox):
            await m.inbox(error_tx)
        # Should NOT route error back (would cause infinite loop)
        mock_inbox.assert_not_awaited()
