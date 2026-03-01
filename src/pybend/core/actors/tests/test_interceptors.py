"""
Test plan for Actor interceptor mechanism
===========================================

The interceptor mechanism allows registering TX transformation functions that
run before inbox() and send() methods. Interceptors can modify the TX or
short-circuit execution by returning an error TX.

Key Concepts:
- Interceptors are registered via actor.use(fn, on='inbox' or 'send')
- Decorator form: @actor.use or @actor.use(on='send')
- Class-level: stored in __interceptors__ ClassVar
- Instance-level: stored in _interceptors PrivateAttr
- Chain execution: class interceptors first, then instance interceptors (FIFO)
- Error TX short-circuits: remaining interceptors are skipped
- Interceptor signature: async (TX) -> TX or sync (TX) -> TX

UNIT TESTS — core registration and retrieval
  - test_use_instance_registers_in_interceptors_dict
  - test_use_class_registers_in_class_interceptors
  - test_use_decorator_form_no_args_defaults_inbox
  - test_use_decorator_with_on_parameter
  - test_use_on_parameter_targets_correct_method
  - test_use_invalid_argument_raises_type_error
  - test_get_interceptors_instance_returns_combined_chain
  - test_get_interceptors_class_returns_class_chain_only
  - test_get_interceptors_empty_when_none_registered

CHAIN EXECUTION — FIFO order
  - test_run_interceptors_executes_in_registration_order
  - test_run_interceptors_supports_sync_and_async_mixed
  - test_run_interceptors_short_circuits_on_error_tx
  - test_run_interceptors_error_tx_skips_remaining_interceptors
  - test_run_interceptors_empty_list_returns_original_tx

INBOX INTEGRATION — interceptors run before handler
  - test_inbox_runs_interceptors_before_handler
  - test_inbox_with_error_interceptor_sends_error_back
  - test_inbox_error_tx_skips_handler
  - test_inbox_no_interceptors_backward_compat
  - test_inbox_multiple_interceptors_chain

SEND INTEGRATION — interceptors run before routing
  - test_send_runs_interceptors_before_routing
  - test_send_with_error_interceptor_drops_message_silently
  - test_send_error_tx_skips_routing
  - test_send_no_interceptors_backward_compat
  - test_send_multiple_interceptors_chain

CLASS AND INSTANCE COMBINATION
  - test_class_and_instance_interceptors_both_execute
  - test_class_interceptors_run_before_instance
  - test_class_only_interceptor_on_instance_call
  - test_instance_only_interceptor

MULTIPLE METHOD TARGETS
  - test_inbox_and_send_interceptors_independent
  - test_different_on_targets_dont_interfere

TX MODIFICATION
  - test_interceptor_can_modify_tx_data
  - test_interceptor_can_modify_tx_meta
  - test_multiple_interceptors_accumulate_changes
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from pybend.core.actors.actor import Actor
from pybend.core.actors.matrix import Matrix
from pybend.core.actors.tx import TX
from .conftest import mock_method, make_tx

pytestmark = pytest.mark.unit


# ===================================================================
# UNIT TESTS — core registration and retrieval
# ===================================================================

class TestInterceptorRegistration:
    """use() registers interceptors in correct storage location."""

    def test_use_instance_registers_in_interceptors_dict(self):
        a = Actor(addr='a')
        def my_interceptor(tx): return tx
        a.use(my_interceptor, on='inbox')
        assert 'inbox' in a._interceptors
        assert my_interceptor in a._interceptors['inbox']

    def test_use_class_registers_in_class_interceptors(self):
        class MyActor(Actor, auto_register=False):
            pass
        def my_interceptor(tx): return tx
        MyActor.use(my_interceptor, on='inbox')
        assert 'inbox' in MyActor.__interceptors__
        assert my_interceptor in MyActor.__interceptors__['inbox']

    def test_use_decorator_form_no_args_defaults_inbox(self):
        a = Actor(addr='a')
        @a.use
        def my_interceptor(tx): return tx
        assert 'inbox' in a._interceptors
        assert my_interceptor in a._interceptors['inbox']

    def test_use_decorator_with_on_parameter(self):
        a = Actor(addr='a')
        @a.use(on='send')
        def my_interceptor(tx): return tx
        assert 'send' in a._interceptors
        assert my_interceptor in a._interceptors['send']

    def test_use_on_parameter_targets_correct_method(self):
        a = Actor(addr='a')
        def inbox_fn(tx): return tx
        def send_fn(tx): return tx
        a.use(inbox_fn, on='inbox')
        a.use(send_fn, on='send')
        assert inbox_fn in a._interceptors['inbox']
        assert send_fn in a._interceptors['send']
        assert send_fn not in a._interceptors.get('inbox', [])
        assert inbox_fn not in a._interceptors.get('send', [])

    def test_use_invalid_argument_raises_type_error(self):
        a = Actor(addr='a')
        with pytest.raises(TypeError, match="Expected callable or None"):
            a.use("not a function")


class TestGetInterceptors:
    """_get_interceptors() combines class and instance chains."""

    def test_get_interceptors_instance_returns_combined_chain(self):
        class MyActor(Actor, auto_register=False):
            pass
        def cls_fn(tx): return tx
        def inst_fn(tx): return tx
        MyActor.use(cls_fn, on='inbox')
        a = MyActor(addr='a')
        a.use(inst_fn, on='inbox')

        chain = Actor._get_interceptors(a, 'inbox')
        assert chain == [cls_fn, inst_fn]

    def test_get_interceptors_class_returns_class_chain_only(self):
        class MyActor(Actor, auto_register=False):
            pass
        def cls_fn(tx): return tx
        MyActor.use(cls_fn, on='inbox')

        chain = Actor._get_interceptors(MyActor, 'inbox')
        assert chain == [cls_fn]

    def test_get_interceptors_empty_when_none_registered(self):
        a = Actor(addr='a')
        chain = Actor._get_interceptors(a, 'inbox')
        assert chain == []


# ===================================================================
# CHAIN EXECUTION — FIFO order
# ===================================================================

class TestRunInterceptors:
    """_run_interceptors() executes chain, supports sync/async, short-circuits on error."""

    @pytest.mark.asyncio
    async def test_run_interceptors_executes_in_registration_order(self):
        calls = []
        def first(tx):
            calls.append('first')
            return tx
        async def second(tx):
            calls.append('second')
            return tx
        def third(tx):
            calls.append('third')
            return tx

        interceptors = [first, second, third]
        tx = make_tx()
        await Actor._run_interceptors(interceptors, tx)
        assert calls == ['first', 'second', 'third']

    @pytest.mark.asyncio
    async def test_run_interceptors_supports_sync_and_async_mixed(self):
        def sync_fn(tx):
            tx.meta['sync'] = True
            return tx
        async def async_fn(tx):
            tx.meta['async'] = True
            return tx

        interceptors = [sync_fn, async_fn]
        tx = make_tx()
        result = await Actor._run_interceptors(interceptors, tx)
        assert result.meta['sync'] is True
        assert result.meta['async'] is True

    @pytest.mark.asyncio
    async def test_run_interceptors_short_circuits_on_error_tx(self):
        def first(tx):
            return tx.error("first error")
        async def second(tx):
            raise AssertionError("Should not execute")

        interceptors = [first, second]
        tx = make_tx()
        result = await Actor._run_interceptors(interceptors, tx)
        assert result.is_error
        assert result.data['message'] == 'first error'

    @pytest.mark.asyncio
    async def test_run_interceptors_error_tx_skips_remaining_interceptors(self):
        calls = []
        def first(tx):
            calls.append('first')
            return tx
        def second(tx):
            calls.append('second')
            return tx.error("stop here")
        def third(tx):
            calls.append('third')
            return tx

        interceptors = [first, second, third]
        tx = make_tx()
        await Actor._run_interceptors(interceptors, tx)
        assert calls == ['first', 'second']  # third never called

    @pytest.mark.asyncio
    async def test_run_interceptors_empty_list_returns_original_tx(self):
        tx = make_tx()
        result = await Actor._run_interceptors([], tx)
        assert result is tx


# ===================================================================
# INBOX INTEGRATION — interceptors run before handler
# ===================================================================

class TestInboxInterceptors:
    """inbox() runs interceptors before handler, sends error back on error TX."""

    @pytest.mark.asyncio
    async def test_inbox_runs_interceptors_before_handler(self):
        calls = []
        def interceptor(tx):
            calls.append('interceptor')
            return tx

        a = Actor(addr='a')
        a.use(interceptor, on='inbox')

        async def mock_handler(tx):
            calls.append('handler')

        with mock_method(a, 'handler', mock_handler):
            await a.inbox(make_tx())

        assert calls == ['interceptor', 'handler']

    @pytest.mark.asyncio
    async def test_inbox_with_error_interceptor_sends_error_back(self):
        def error_interceptor(tx):
            return tx.error("access denied")

        a = Actor(addr='a')
        a.use(error_interceptor, on='inbox')

        sent = []
        async def mock_send(tx):
            sent.append(tx)

        with mock_method(a, 'send', mock_send):
            await a.inbox(make_tx())

        assert len(sent) == 1
        assert sent[0].is_error
        assert sent[0].data['message'] == 'access denied'

    @pytest.mark.asyncio
    async def test_inbox_error_tx_skips_handler(self):
        def error_interceptor(tx):
            return tx.error("blocked")

        a = Actor(addr='a')
        a.use(error_interceptor, on='inbox')

        handler_called = []
        async def mock_handler(tx):
            handler_called.append(tx)

        async def mock_send(tx):
            pass

        with mock_method(a, 'handler', mock_handler), \
             mock_method(a, 'send', mock_send):
            await a.inbox(make_tx())

        assert len(handler_called) == 0

    @pytest.mark.asyncio
    async def test_inbox_no_interceptors_backward_compat(self):
        """inbox() works without interceptors — backward compatibility."""
        a = Actor(addr='a')
        handler_called = []

        async def mock_handler(tx):
            handler_called.append(tx)

        with mock_method(a, 'handler', mock_handler):
            await a.inbox(make_tx())

        assert len(handler_called) == 1

    @pytest.mark.asyncio
    async def test_inbox_multiple_interceptors_chain(self):
        calls = []
        def first(tx):
            calls.append('first')
            tx.meta['first'] = True
            return tx
        def second(tx):
            calls.append('second')
            tx.meta['second'] = True
            return tx

        a = Actor(addr='a')
        a.use(first, on='inbox')
        a.use(second, on='inbox')

        received_tx = None
        async def mock_handler(tx):
            nonlocal received_tx
            received_tx = tx

        with mock_method(a, 'handler', mock_handler):
            await a.inbox(make_tx())

        assert calls == ['first', 'second']
        assert received_tx.meta['first'] is True
        assert received_tx.meta['second'] is True


# ===================================================================
# SEND INTEGRATION — interceptors run before routing
# ===================================================================

class TestSendInterceptors:
    """send() runs interceptors before routing, drops error TX silently."""

    @pytest.mark.asyncio
    async def test_send_runs_interceptors_before_routing(self):
        calls = []
        def interceptor(tx):
            calls.append('interceptor')
            return tx

        a = Actor(addr='a')
        a.use(interceptor, on='send')

        # Use instance with parent set to avoid RuntimeError
        parent = Actor(addr='parent')
        a._parent = parent

        async def mock_parent_inbox(tx):
            calls.append('routing')

        with mock_method(parent, 'inbox', mock_parent_inbox):
            await a.send(make_tx(target='other'))

        assert calls == ['interceptor', 'routing']

    @pytest.mark.asyncio
    async def test_send_with_error_interceptor_drops_message_silently(self):
        def error_interceptor(tx):
            return tx.error("rejected")

        a = Actor(addr='a')
        a.use(error_interceptor, on='send')

        parent = Actor(addr='parent')
        a._parent = parent

        routed = []
        async def mock_parent_inbox(tx):
            routed.append(tx)

        with mock_method(parent, 'inbox', mock_parent_inbox):
            await a.send(make_tx(target='other'))

        # Error TX is dropped, not routed
        assert len(routed) == 0

    @pytest.mark.asyncio
    async def test_send_error_tx_skips_routing(self):
        def error_interceptor(tx):
            return tx.error("blocked")

        class TestRouter(Actor, auto_register=False):
            pass

        TestRouter.use(error_interceptor, on='send')

        child = MagicMock()
        child.inbox = AsyncMock()
        TestRouter.__children__['child'] = child

        await TestRouter.send(make_tx(target='child'))

        # Routing never happened
        child.inbox.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_send_no_interceptors_backward_compat(self):
        """send() works without interceptors — backward compatibility."""
        a = Actor(addr='a')
        parent = Actor(addr='parent')
        a._parent = parent

        routed = []
        async def mock_parent_inbox(tx):
            routed.append(tx)

        with mock_method(parent, 'inbox', mock_parent_inbox):
            await a.send(make_tx(target='other'))

        assert len(routed) == 1

    @pytest.mark.asyncio
    async def test_send_multiple_interceptors_chain(self):
        calls = []
        def first(tx):
            calls.append('first')
            return tx
        async def second(tx):
            calls.append('second')
            return tx

        a = Actor(addr='a')
        a.use(first, on='send')
        a.use(second, on='send')

        parent = Actor(addr='parent')
        a._parent = parent

        async def mock_parent_inbox(tx):
            calls.append('routing')

        with mock_method(parent, 'inbox', mock_parent_inbox):
            await a.send(make_tx(target='other'))

        assert calls == ['first', 'second', 'routing']


# ===================================================================
# CLASS AND INSTANCE COMBINATION
# ===================================================================

class TestClassInstanceCombination:
    """Class and instance interceptors combine (class first, then instance)."""

    @pytest.mark.asyncio
    async def test_class_and_instance_interceptors_both_execute(self):
        class MyActor(Actor, auto_register=False):
            pass

        calls = []
        def cls_fn(tx):
            calls.append('class')
            return tx
        def inst_fn(tx):
            calls.append('instance')
            return tx

        MyActor.use(cls_fn, on='inbox')
        a = MyActor(addr='a')
        a.use(inst_fn, on='inbox')

        async def mock_handler(tx):
            calls.append('handler')

        with mock_method(a, 'handler', mock_handler):
            await a.inbox(make_tx())

        assert calls == ['class', 'instance', 'handler']

    @pytest.mark.asyncio
    async def test_class_interceptors_run_before_instance(self):
        class MyActor(Actor, auto_register=False):
            pass

        order = []
        def cls_first(tx):
            order.append(1)
            return tx
        def cls_second(tx):
            order.append(2)
            return tx
        def inst_first(tx):
            order.append(3)
            return tx
        def inst_second(tx):
            order.append(4)
            return tx

        MyActor.use(cls_first, on='inbox')
        MyActor.use(cls_second, on='inbox')
        a = MyActor(addr='a')
        a.use(inst_first, on='inbox')
        a.use(inst_second, on='inbox')

        async def mock_handler(tx):
            pass

        with mock_method(a, 'handler', mock_handler):
            await a.inbox(make_tx())

        assert order == [1, 2, 3, 4]

    @pytest.mark.asyncio
    async def test_class_only_interceptor_on_instance_call(self):
        """Instance with no interceptors still executes class interceptors."""
        class MyActor(Actor, auto_register=False):
            pass

        calls = []
        def cls_fn(tx):
            calls.append('class')
            return tx

        MyActor.use(cls_fn, on='inbox')
        a = MyActor(addr='a')

        async def mock_handler(tx):
            calls.append('handler')

        with mock_method(a, 'handler', mock_handler):
            await a.inbox(make_tx())

        assert calls == ['class', 'handler']

    @pytest.mark.asyncio
    async def test_instance_only_interceptor(self):
        """Instance interceptors work without class interceptors."""
        a = Actor(addr='a')
        calls = []
        def inst_fn(tx):
            calls.append('instance')
            return tx

        a.use(inst_fn, on='inbox')

        async def mock_handler(tx):
            calls.append('handler')

        with mock_method(a, 'handler', mock_handler):
            await a.inbox(make_tx())

        assert calls == ['instance', 'handler']


# ===================================================================
# MULTIPLE METHOD TARGETS
# ===================================================================

class TestMultipleMethodTargets:
    """Interceptors on different methods (inbox vs send) don't interfere."""

    @pytest.mark.asyncio
    async def test_inbox_and_send_interceptors_independent(self):
        a = Actor(addr='a')
        inbox_calls = []
        send_calls = []

        def inbox_fn(tx):
            inbox_calls.append('inbox')
            return tx
        def send_fn(tx):
            send_calls.append('send')
            return tx

        a.use(inbox_fn, on='inbox')
        a.use(send_fn, on='send')

        # Test inbox
        async def mock_handler(tx):
            pass
        with mock_method(a, 'handler', mock_handler):
            await a.inbox(make_tx())

        assert inbox_calls == ['inbox']
        assert send_calls == []

        # Test send
        parent = Actor(addr='parent')
        a._parent = parent
        async def mock_parent_inbox(tx):
            pass
        with mock_method(parent, 'inbox', mock_parent_inbox):
            await a.send(make_tx(target='other'))

        assert send_calls == ['send']
        assert len(inbox_calls) == 1  # Still just the one from before

    @pytest.mark.asyncio
    async def test_different_on_targets_dont_interfere(self):
        """Interceptors registered for inbox don't run on send and vice versa."""
        a = Actor(addr='a')

        inbox_calls = []
        send_calls = []

        def inbox_fn(tx):
            inbox_calls.append('inbox')
            return tx
        def send_fn(tx):
            send_calls.append('send')
            return tx

        a.use(inbox_fn, on='inbox')
        a.use(send_fn, on='send')

        # inbox() should only run inbox interceptor
        async def mock_handler(tx):
            pass

        with mock_method(a, 'handler', mock_handler):
            await a.inbox(make_tx())

        assert inbox_calls == ['inbox']
        assert send_calls == []  # send interceptor should NOT have run

        # send() should only run send interceptor
        parent = Actor(addr='parent')
        a._parent = parent

        async def mock_parent_inbox(tx):
            pass

        with mock_method(parent, 'inbox', mock_parent_inbox):
            await a.send(make_tx(target='other'))

        assert send_calls == ['send']
        assert len(inbox_calls) == 1  # inbox interceptor should NOT have run again


# ===================================================================
# TX MODIFICATION
# ===================================================================

class TestTXModification:
    """Interceptors can modify TX; changes accumulate through the chain."""

    @pytest.mark.asyncio
    async def test_interceptor_can_modify_tx_data(self):
        def add_auth(tx):
            tx.data['user_id'] = 123
            return tx

        a = Actor(addr='a')
        a.use(add_auth, on='inbox')

        received_tx = None
        async def mock_handler(tx):
            nonlocal received_tx
            received_tx = tx

        with mock_method(a, 'handler', mock_handler):
            await a.inbox(make_tx())

        assert received_tx.data['user_id'] == 123

    @pytest.mark.asyncio
    async def test_interceptor_can_modify_tx_meta(self):
        def add_metadata(tx):
            tx.meta['processed_by'] = 'interceptor'
            return tx

        a = Actor(addr='a')
        a.use(add_metadata, on='inbox')

        received_tx = None
        async def mock_handler(tx):
            nonlocal received_tx
            received_tx = tx

        with mock_method(a, 'handler', mock_handler):
            await a.inbox(make_tx())

        assert received_tx.meta['processed_by'] == 'interceptor'

    @pytest.mark.asyncio
    async def test_multiple_interceptors_accumulate_changes(self):
        def first(tx):
            tx.meta['step1'] = 'done'
            return tx
        def second(tx):
            tx.meta['step2'] = 'done'
            tx.data['enriched'] = True
            return tx
        def third(tx):
            tx.meta['step3'] = 'done'
            return tx

        a = Actor(addr='a')
        a.use(first, on='inbox')
        a.use(second, on='inbox')
        a.use(third, on='inbox')

        received_tx = None
        async def mock_handler(tx):
            nonlocal received_tx
            received_tx = tx

        with mock_method(a, 'handler', mock_handler):
            await a.inbox(make_tx())

        assert received_tx.meta['step1'] == 'done'
        assert received_tx.meta['step2'] == 'done'
        assert received_tx.meta['step3'] == 'done'
        assert received_tx.data['enriched'] is True
