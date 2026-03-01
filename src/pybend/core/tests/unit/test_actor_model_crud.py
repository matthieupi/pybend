"""Tests for ActorModel.handler_crud() — CRUD adapter that translates
TX messages to StorableMixin method signatures.

handler_crud is a @classmethod that receives a TX and returns:
- A dict/TX for CRUD operations (schema, create, get, list, update, delete)
- _NOT_HANDLED sentinel for anything else

Storage is mocked since no real backend is connected.
"""

import pytest
from unittest.mock import MagicMock, patch
from typing import ClassVar

from pydantic import Field

from pybend.core.models.actor_model import ActorModel, _NOT_HANDLED
from pybend.core.actors.tx import TX

pytestmark = pytest.mark.unit


# ===================================================================
# Test model
# ===================================================================

class _CrudModel(ActorModel, auto_register=False):
    __tablename__: ClassVar[str] = 'crud_test'
    __storable__: ClassVar[bool] = True
    name: str = Field(default='')
    value: int = Field(default=0)


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture(autouse=True)
def mock_storage():
    """Inject a mock storage backend for every test, clean up after."""
    storage = MagicMock()
    _CrudModel.storage = storage
    yield storage
    _CrudModel.storage = None


@pytest.fixture
def make_tx():
    """Factory for TX messages targeting the CRUD model."""
    def _make(name, data=None):
        return TX(name=name, source='test', target='crud_test', data=data or {})
    return _make


# ===================================================================
# Helpers
# ===================================================================

def _make_instance(id=1, name='Widget', value=42):
    """Create a _CrudModel instance without hitting storage.

    Bypasses the ProtoModel __init__ shortcut that tries to fetch
    from storage when only 'id' is passed, by always providing
    all fields.
    """
    return _CrudModel(id=id, name=name, value=value)


# ===================================================================
# TestHandlerCrudSchema
# ===================================================================

class TestHandlerCrudSchema:
    """TX(name='schema') returns cls.schema() result."""

    def test_schema_returns_dict(self, make_tx):
        tx = make_tx('schema')
        result = _CrudModel.handler_crud(tx)
        assert isinstance(result, dict)

    def test_schema_has_properties(self, make_tx):
        tx = make_tx('schema')
        result = _CrudModel.handler_crud(tx)
        assert 'properties' in result

    def test_schema_properties_include_model_fields(self, make_tx):
        tx = make_tx('schema')
        result = _CrudModel.handler_crud(tx)
        props = result['properties']
        assert 'name' in props
        assert 'value' in props

    def test_schema_matches_cls_schema(self, make_tx):
        """handler_crud result should match cls.schema() output."""
        tx = make_tx('schema')
        result = _CrudModel.handler_crud(tx)
        expected = _CrudModel.schema()
        assert result == expected

    def test_schema_case_insensitive(self, make_tx):
        """'SCHEMA', 'Schema', 'schema' all work — name is lowercased."""
        for name in ('schema', 'Schema', 'SCHEMA'):
            tx = TX(name=name, source='test', target='crud_test')
            result = _CrudModel.handler_crud(tx)
            assert isinstance(result, dict)
            assert 'properties' in result


# ===================================================================
# TestHandlerCrudCreate
# ===================================================================

class TestHandlerCrudCreate:
    """TX(name='create', data={...}) creates an entity via storage."""

    def test_create_calls_storage(self, mock_storage, make_tx):
        instance = _make_instance()
        mock_storage.create.return_value = instance
        tx = make_tx('create', {'name': 'Widget', 'value': 42})
        _CrudModel.handler_crud(tx)
        mock_storage.create.assert_called_once()

    def test_create_returns_model_response(self, mock_storage, make_tx):
        instance = _make_instance(id=1, name='Widget', value=42)
        mock_storage.create.return_value = instance
        tx = make_tx('create', {'name': 'Widget', 'value': 42})
        result = _CrudModel.handler_crud(tx)
        assert isinstance(result, dict)
        assert '$schema' in result

    def test_create_response_has_data(self, mock_storage, make_tx):
        instance = _make_instance(id=1, name='Widget', value=42)
        mock_storage.create.return_value = instance
        tx = make_tx('create', {'name': 'Widget', 'value': 42})
        result = _CrudModel.handler_crud(tx)
        assert result['name'] == 'Widget'
        assert result['value'] == 42

    def test_create_failure_returns_error_tx(self, mock_storage, make_tx):
        """When storage.create returns None, handler returns tx.error()."""
        mock_storage.create.return_value = None
        tx = make_tx('create', {'name': 'Broken'})
        result = _CrudModel.handler_crud(tx)
        assert isinstance(result, TX)
        assert result.is_error


# ===================================================================
# TestHandlerCrudGet
# ===================================================================

class TestHandlerCrudGet:
    """TX(name='get', data={id: N}) retrieves an entity."""

    def test_get_calls_storage(self, mock_storage, make_tx):
        instance = _make_instance(id=1)
        mock_storage.get.return_value = instance
        tx = make_tx('get', {'id': 1})
        _CrudModel.handler_crud(tx)
        mock_storage.get.assert_called_once()

    def test_get_returns_model_response(self, mock_storage, make_tx):
        instance = _make_instance(id=1, name='Widget', value=42)
        mock_storage.get.return_value = instance
        tx = make_tx('get', {'id': 1})
        result = _CrudModel.handler_crud(tx)
        assert isinstance(result, dict)
        assert '$schema' in result
        assert result['name'] == 'Widget'

    def test_get_without_id_returns_error(self, make_tx):
        """Missing 'id' in data returns tx.error() with code 400."""
        tx = make_tx('get', {})
        result = _CrudModel.handler_crud(tx)
        assert isinstance(result, TX)
        assert result.is_error
        assert result.data['code'] == 400

    def test_get_nonexistent_returns_404_error(self, mock_storage, make_tx):
        """storage.get returns None -> tx.error() with code 404."""
        mock_storage.get.return_value = None
        tx = make_tx('get', {'id': 999})
        result = _CrudModel.handler_crud(tx)
        assert isinstance(result, TX)
        assert result.is_error
        assert result.data['code'] == 404

    def test_get_404_message_includes_class_name(self, mock_storage, make_tx):
        mock_storage.get.return_value = None
        tx = make_tx('get', {'id': 999})
        result = _CrudModel.handler_crud(tx)
        assert '_CrudModel' in result.data['message']
        assert '999' in result.data['message']


# ===================================================================
# TestHandlerCrudList
# ===================================================================

class TestHandlerCrudList:
    """TX(name='list') retrieves entity list with optional pagination."""

    def test_list_with_limit_offset(self, mock_storage, make_tx):
        mock_storage.list.return_value = []
        tx = make_tx('list', {'limit': 10, 'offset': 0})
        _CrudModel.handler_crud(tx)
        mock_storage.list.assert_called_once_with(
            _CrudModel, sql_filter=None, limit=10, offset=0, populate=None,
        )

    def test_list_empty_data_passes_none(self, mock_storage, make_tx):
        """TX(name='list', data={}) calls cls.list(limit=None, offset=None)."""
        mock_storage.list.return_value = []
        tx = make_tx('list', {})
        _CrudModel.handler_crud(tx)
        mock_storage.list.assert_called_once_with(
            _CrudModel, sql_filter=None, limit=None, offset=None, populate=None,
        )

    def test_list_returns_storage_result(self, mock_storage, make_tx):
        expected = [{'id': 1, 'name': 'A'}, {'id': 2, 'name': 'B'}]
        mock_storage.list.return_value = expected
        tx = make_tx('list', {'limit': 10, 'offset': 0})
        result = _CrudModel.handler_crud(tx)
        assert result == expected

    def test_list_returns_paginated_dict(self, mock_storage, make_tx):
        """Storage may return a paginated dict with data + meta."""
        paginated = {
            'data': [{'id': 1}],
            'meta': {'total': 1, 'limit': 10, 'offset': 0, 'has_more': False},
        }
        mock_storage.list.return_value = paginated
        tx = make_tx('list', {'limit': 10, 'offset': 0})
        result = _CrudModel.handler_crud(tx)
        assert result == paginated

    def test_list_with_only_limit(self, mock_storage, make_tx):
        mock_storage.list.return_value = []
        tx = make_tx('list', {'limit': 5})
        _CrudModel.handler_crud(tx)
        mock_storage.list.assert_called_once_with(
            _CrudModel, sql_filter=None, limit=5, offset=None, populate=None,
        )


# ===================================================================
# TestHandlerCrudUpdate
# ===================================================================

class TestHandlerCrudUpdate:
    """TX(name='update', data={id: N, ...}) updates an entity."""

    def test_update_calls_storage(self, mock_storage, make_tx):
        instance = _make_instance(id=1, name='New')
        mock_storage.update.return_value = None
        mock_storage.get.return_value = instance
        tx = make_tx('update', {'id': 1, 'name': 'New'})
        _CrudModel.handler_crud(tx)
        mock_storage.update.assert_called_once()

    def test_update_returns_model_response(self, mock_storage, make_tx):
        instance = _make_instance(id=1, name='New', value=99)
        mock_storage.update.return_value = None
        mock_storage.get.return_value = instance
        tx = make_tx('update', {'id': 1, 'name': 'New', 'value': 99})
        result = _CrudModel.handler_crud(tx)
        assert isinstance(result, dict)
        assert '$schema' in result
        assert result['name'] == 'New'

    def test_update_strips_id_from_data(self, mock_storage, make_tx):
        """The 'id' key should be removed from the update data dict."""
        instance = _make_instance(id=1, name='New')
        mock_storage.update.return_value = None
        mock_storage.get.return_value = instance
        tx = make_tx('update', {'id': 1, 'name': 'New'})
        _CrudModel.handler_crud(tx)
        # storage.update receives (cls, id, data_dict) — data_dict should not contain 'id'
        call_args = mock_storage.update.call_args
        update_data = call_args[0][2]  # third positional arg: the data dict
        assert 'id' not in update_data

    def test_update_without_id_returns_error(self, make_tx):
        """Missing 'id' in data returns tx.error() with code 400."""
        tx = make_tx('update', {'name': 'NoId'})
        result = _CrudModel.handler_crud(tx)
        assert isinstance(result, TX)
        assert result.is_error
        assert result.data['code'] == 400

    def test_update_failure_returns_error_tx(self, mock_storage, make_tx):
        """When storage.update + get returns None, handler returns error."""
        mock_storage.update.return_value = None
        mock_storage.get.return_value = None
        tx = make_tx('update', {'id': 1, 'name': 'Fail'})
        result = _CrudModel.handler_crud(tx)
        assert isinstance(result, TX)
        assert result.is_error


# ===================================================================
# TestHandlerCrudDelete
# ===================================================================

class TestHandlerCrudDelete:
    """TX(name='delete', data={id: N}) deletes an entity."""

    def test_delete_calls_storage(self, mock_storage, make_tx):
        tx = make_tx('delete', {'id': 1})
        _CrudModel.handler_crud(tx)
        mock_storage.delete.assert_called_once_with(_CrudModel, 1)

    def test_delete_returns_deleted_id(self, mock_storage, make_tx):
        tx = make_tx('delete', {'id': 1})
        result = _CrudModel.handler_crud(tx)
        assert isinstance(result, dict)
        assert result == {'deleted': 1}

    def test_delete_without_id_returns_error(self, make_tx):
        """Missing 'id' in data returns tx.error() with code 400."""
        tx = make_tx('delete', {})
        result = _CrudModel.handler_crud(tx)
        assert isinstance(result, TX)
        assert result.is_error
        assert result.data['code'] == 400

    def test_delete_with_different_id(self, mock_storage, make_tx):
        tx = make_tx('delete', {'id': 42})
        result = _CrudModel.handler_crud(tx)
        assert result == {'deleted': 42}
        mock_storage.delete.assert_called_once_with(_CrudModel, 42)


# ===================================================================
# TestHandlerCrudNotHandled
# ===================================================================

class TestHandlerCrudNotHandled:
    """Non-CRUD message names return the _NOT_HANDLED sentinel."""

    def test_unknown_op_returns_not_handled(self, make_tx):
        tx = make_tx('unknown_op')
        result = _CrudModel.handler_crud(tx)
        assert result is _NOT_HANDLED

    def test_favorite_returns_not_handled(self, make_tx):
        tx = TX(name='FAVORITE', source='test', target='crud_test')
        result = _CrudModel.handler_crud(tx)
        assert result is _NOT_HANDLED

    def test_empty_name_returns_not_handled(self):
        tx = TX(name='', source='test', target='crud_test')
        result = _CrudModel.handler_crud(tx)
        assert result is _NOT_HANDLED

    def test_crud_prefix_not_matched(self, make_tx):
        """'create_user' is not 'create' — should not be handled."""
        tx = make_tx('create_user')
        result = _CrudModel.handler_crud(tx)
        assert result is _NOT_HANDLED

    def test_custom_method_name_not_handled(self, make_tx):
        tx = make_tx('publish')
        result = _CrudModel.handler_crud(tx)
        assert result is _NOT_HANDLED

    def test_not_handled_is_distinct_from_none(self):
        """_NOT_HANDLED is not None — they must be distinguishable."""
        assert _NOT_HANDLED is not None


# ===================================================================
# TestHandlerCrudErrors
# ===================================================================

class TestHandlerCrudErrors:
    """Exceptions during CRUD operations return tx.error()."""

    def test_create_exception_returns_error_tx(self, mock_storage, make_tx):
        mock_storage.create.side_effect = RuntimeError('DB connection lost')
        tx = make_tx('create', {'name': 'Widget', 'value': 42})
        result = _CrudModel.handler_crud(tx)
        assert isinstance(result, TX)
        assert result.is_error
        assert 'DB connection lost' in result.data['message']

    def test_get_exception_returns_error_tx(self, mock_storage, make_tx):
        mock_storage.get.side_effect = RuntimeError('Query failed')
        tx = make_tx('get', {'id': 1})
        result = _CrudModel.handler_crud(tx)
        assert isinstance(result, TX)
        assert result.is_error
        assert 'Query failed' in result.data['message']

    def test_list_exception_returns_error_tx(self, mock_storage, make_tx):
        mock_storage.list.side_effect = RuntimeError('Table not found')
        tx = make_tx('list', {'limit': 10, 'offset': 0})
        result = _CrudModel.handler_crud(tx)
        assert isinstance(result, TX)
        assert result.is_error
        assert 'Table not found' in result.data['message']

    def test_update_exception_returns_error_tx(self, mock_storage, make_tx):
        mock_storage.update.side_effect = RuntimeError('Constraint violation')
        tx = make_tx('update', {'id': 1, 'name': 'Bad'})
        result = _CrudModel.handler_crud(tx)
        assert isinstance(result, TX)
        assert result.is_error
        assert 'Constraint violation' in result.data['message']

    def test_delete_exception_returns_error_tx(self, mock_storage, make_tx):
        mock_storage.delete.side_effect = RuntimeError('FK constraint')
        tx = make_tx('delete', {'id': 1})
        result = _CrudModel.handler_crud(tx)
        assert isinstance(result, TX)
        assert result.is_error
        assert 'FK constraint' in result.data['message']

    def test_error_tx_has_default_500_code(self, mock_storage, make_tx):
        mock_storage.create.side_effect = ValueError('bad data')
        tx = make_tx('create', {'name': 'X'})
        result = _CrudModel.handler_crud(tx)
        assert result.data['code'] == 500

    def test_error_tx_source_target_swapped(self, mock_storage):
        """Error TX has source/target swapped from original TX."""
        mock_storage.create.side_effect = ValueError('fail')
        tx = TX(name='create', source='client', target='crud_test')
        result = _CrudModel.handler_crud(tx)
        assert result.source == 'crud_test'
        assert result.target == 'client'

    def test_error_tx_has_in_reply_to(self, mock_storage, make_tx):
        """Error TX meta includes in_reply_to referencing original uuid."""
        mock_storage.create.side_effect = ValueError('fail')
        tx = make_tx('create', {'name': 'X'})
        result = _CrudModel.handler_crud(tx)
        assert result.meta['in_reply_to'] == tx.uuid
