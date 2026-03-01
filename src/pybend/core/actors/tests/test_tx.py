"""Tests for TX — message envelope for the actor system."""

import time

import pytest

from pybend.core.actors.tx import TX

pytestmark = pytest.mark.unit


class TestTXCreation:
    """TX construction and defaults."""

    def test_required_fields(self):
        tx = TX(name='READ', source='a', target='b')
        assert tx.name == 'READ'
        assert tx.source == 'a'
        assert tx.target == 'b'

    def test_defaults(self):
        tx = TX(name='X', source='a', target='b')
        assert tx.data == {}
        assert tx.meta == {}
        assert isinstance(tx.timestamp, float)
        assert isinstance(tx.uuid, str)
        assert len(tx.uuid) == 12

    def test_uuid_unique_per_instance(self):
        uuids = {TX(name='X', source='a', target='b').uuid for _ in range(100)}
        assert len(uuids) == 100

    def test_timestamp_is_recent(self):
        before = time.time()
        tx = TX(name='X', source='a', target='b')
        after = time.time()
        assert before <= tx.timestamp <= after

    def test_custom_data_and_meta(self):
        tx = TX(name='X', source='a', target='b',
                data={'key': 'val'}, meta={'trace': '123'})
        assert tx.data == {'key': 'val'}
        assert tx.meta == {'trace': '123'}

    def test_data_and_meta_independent_per_instance(self):
        tx1 = TX(name='X', source='a', target='b')
        tx2 = TX(name='X', source='a', target='b')
        tx1.data['key'] = 'val'
        tx1.meta['flag'] = True
        assert 'key' not in tx2.data
        assert 'flag' not in tx2.meta


class TestTXReply:
    """TX.reply() — create response message."""

    def test_swaps_source_target(self):
        tx = TX(name='READ', source='a', target='b')
        reply = tx.reply()
        assert reply.source == 'b'
        assert reply.target == 'a'

    def test_new_uuid(self):
        tx = TX(name='READ', source='a', target='b')
        reply = tx.reply()
        assert reply.uuid != tx.uuid

    def test_stores_original_uuid_in_meta(self):
        tx = TX(name='READ', source='a', target='b')
        reply = tx.reply()
        assert reply.meta['in_reply_to'] == tx.uuid

    def test_default_name_appends_response(self):
        tx = TX(name='READ', source='a', target='b')
        assert tx.reply().name == 'READ_RESPONSE'

    def test_custom_name(self):
        tx = TX(name='READ', source='a', target='b')
        assert tx.reply(name='CUSTOM').name == 'CUSTOM'

    def test_default_data_empty(self):
        tx = TX(name='X', source='a', target='b')
        assert tx.reply().data == {}

    def test_with_data(self):
        tx = TX(name='X', source='a', target='b')
        reply = tx.reply(data={'result': 42})
        assert reply.data == {'result': 42}

    def test_preserves_original_meta(self):
        tx = TX(name='X', source='a', target='b', meta={'trace': '123'})
        reply = tx.reply()
        assert reply.meta['trace'] == '123'
        assert reply.meta['in_reply_to'] == tx.uuid


class TestTXError:
    """TX.error() — create error response."""

    def test_name_is_error(self):
        tx = TX(name='READ', source='a', target='b')
        assert tx.error('fail').name == 'ERROR'

    def test_swaps_source_target(self):
        err = TX(name='X', source='a', target='b').error('fail')
        assert err.source == 'b'
        assert err.target == 'a'

    def test_data_contains_message_and_code(self):
        err = TX(name='X', source='a', target='b').error('broken', code=404)
        assert err.data == {'message': 'broken', 'code': 404}

    def test_default_code_is_500(self):
        err = TX(name='X', source='a', target='b').error('broken')
        assert err.data['code'] == 500

    def test_error_meta_flag(self):
        err = TX(name='X', source='a', target='b').error('broken')
        assert err.meta['error'] is True

    def test_preserves_original_meta(self):
        tx = TX(name='X', source='a', target='b', meta={'trace': '123'})
        err = tx.error('fail')
        assert err.meta['trace'] == '123'
        assert err.meta['error'] is True
        assert err.meta['in_reply_to'] == tx.uuid

    def test_new_uuid(self):
        tx = TX(name='X', source='a', target='b')
        err = tx.error('fail')
        assert err.uuid != tx.uuid


class TestTXIsError:
    """TX.is_error property."""

    def test_true_for_error_name(self):
        assert TX(name='ERROR', source='a', target='b').is_error is True

    def test_true_for_error_meta(self):
        tx = TX(name='CUSTOM', source='a', target='b', meta={'error': True})
        assert tx.is_error is True

    def test_false_for_normal(self):
        assert TX(name='READ', source='a', target='b').is_error is False

    def test_error_method_produces_is_error(self):
        tx = TX(name='X', source='a', target='b')
        assert tx.error('fail').is_error is True

    def test_reply_is_not_error(self):
        tx = TX(name='X', source='a', target='b')
        assert tx.reply().is_error is False
