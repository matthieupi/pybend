"""Tests for first-class JSON field support in the storage layer.

Verifies that dict and list fields are transparently serialized to JSON TEXT
on write and deserialized back to Python objects on read — no model-level
boilerplate required.
"""

import pytest
from typing import ClassVar, Dict, List, Any, Optional

from pydantic import BaseModel, Field

from n3tx_core.storage.sqlite_storage import SQLiteStorage, _coerce_value, _deserialize_json_fields
from n3tx_core.models.proto_model import ProtoModel
from n3tx_core.utils.introspection import get_json_fields

pytestmark = pytest.mark.unit


@pytest.fixture
def tmp_db(tmp_path):
    db_path = str(tmp_path / 'test.db')
    return db_path


@pytest.fixture
def storage(tmp_db):
    return SQLiteStorage(database=tmp_db)


def _make_json_model(tablename, storage_backend):
    """Create a model with dict/list JSON fields and wire storage."""
    class M(ProtoModel):
        __tablename__: ClassVar[str] = tablename
        __storable__: ClassVar[bool] = True
        name: str = Field(default='')
        tags: list = Field(default=[])
        metadata: dict = Field(default={})
        scores: List[int] = Field(default=[])
    M.set_storage(storage_backend)
    storage_backend.create_table(M)
    storage_backend.migrate_table(M)
    return M


# ── _coerce_value ──

class TestCoerceValue:

    def test_dict_serialized_to_json(self):
        result = _coerce_value({"key": "value"})
        assert isinstance(result, str)
        assert '"key"' in result

    def test_list_serialized_to_json(self):
        result = _coerce_value([1, 2, 3])
        assert isinstance(result, str)
        assert result == '[1, 2, 3]'

    def test_nested_dict(self):
        result = _coerce_value({"a": {"b": 1}})
        assert isinstance(result, str)
        assert '"b"' in result

    def test_empty_dict(self):
        result = _coerce_value({})
        assert result == '{}'

    def test_empty_list(self):
        result = _coerce_value([])
        assert result == '[]'

    def test_native_types_unchanged(self):
        assert _coerce_value(42) == 42
        assert _coerce_value(3.14) == 3.14
        assert _coerce_value("hello") == "hello"
        assert _coerce_value(None) is None


# ── _deserialize_json_fields ──

class TestDeserializeJsonFields:

    def test_deserializes_dict_string(self):
        class M(BaseModel):
            data: dict = Field(default={})
        record = {'data': '{"key": "val"}'}
        _deserialize_json_fields(M, record)
        assert record['data'] == {"key": "val"}

    def test_deserializes_list_string(self):
        class M(BaseModel):
            tags: list = Field(default=[])
        record = {'tags': '["a", "b"]'}
        _deserialize_json_fields(M, record)
        assert record['tags'] == ["a", "b"]

    def test_leaves_non_string_alone(self):
        class M(BaseModel):
            data: dict = Field(default={})
        record = {'data': {"already": "parsed"}}
        _deserialize_json_fields(M, record)
        assert record['data'] == {"already": "parsed"}

    def test_invalid_json_no_crash(self):
        class M(BaseModel):
            data: dict = Field(default={})
        record = {'data': 'not-json'}
        _deserialize_json_fields(M, record)
        assert record['data'] == 'not-json'  # unchanged

    def test_missing_field_no_crash(self):
        class M(BaseModel):
            data: dict = Field(default={})
        record = {}
        _deserialize_json_fields(M, record)  # should not raise


# ── Round-trip integration ──

class TestJsonFieldRoundTrip:

    def test_create_and_get(self, storage, tmp_db):
        M = _make_json_model('rt_create_get', storage)
        created = storage.create(M, {
            'name': 'test',
            'tags': ['a', 'b'],
            'metadata': {'key': 'value'},
            'scores': [10, 20],
        })
        assert created.id == 1

        fetched = storage.get(M, 1)
        assert fetched.tags == ['a', 'b']
        assert fetched.metadata == {'key': 'value'}
        assert fetched.scores == [10, 20]

    def test_create_and_list(self, storage, tmp_db):
        M = _make_json_model('rt_create_list', storage)
        storage.create(M, {
            'name': 'item1',
            'tags': ['x'],
            'metadata': {'n': 1},
            'scores': [5],
        })
        storage.create(M, {
            'name': 'item2',
            'tags': ['y', 'z'],
            'metadata': {'n': 2},
            'scores': [6, 7],
        })
        results = storage.list(M)
        assert len(results) == 2
        assert results[0].tags == ['x']
        assert results[1].metadata == {'n': 2}
        assert results[1].scores == [6, 7]

    def test_update_json_field(self, storage, tmp_db):
        M = _make_json_model('rt_update', storage)
        storage.create(M, {
            'name': 'orig',
            'tags': ['old'],
            'metadata': {'v': 1},
            'scores': [1],
        })
        storage.update(M, 1, {
            'tags': ['new', 'updated'],
            'metadata': {'v': 2, 'extra': True},
            'scores': [100],
        })
        fetched = storage.get(M, 1)
        assert fetched.tags == ['new', 'updated']
        assert fetched.metadata == {'v': 2, 'extra': True}
        assert fetched.scores == [100]

    def test_empty_collections(self, storage, tmp_db):
        M = _make_json_model('rt_empty', storage)
        storage.create(M, {
            'name': 'empty',
            'tags': [],
            'metadata': {},
            'scores': [],
        })
        fetched = storage.get(M, 1)
        assert fetched.tags == []
        assert fetched.metadata == {}
        assert fetched.scores == []

    def test_nested_dict(self, storage, tmp_db):
        M = _make_json_model('rt_nested', storage)
        nested = {'a': {'b': {'c': [1, 2, 3]}}}
        storage.create(M, {
            'name': 'nested',
            'metadata': nested,
        })
        fetched = storage.get(M, 1)
        assert fetched.metadata == nested

    def test_optional_dict_field(self, storage, tmp_db):
        """Optional[dict] should also round-trip correctly."""
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'rt_optional'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
            config: Optional[dict] = Field(default=None)
        M.set_storage(storage)
        storage.create_table(M)
        storage.migrate_table(M)

        storage.create(M, {'name': 'test', 'config': {'debug': True}})
        fetched = storage.get(M, 1)
        assert fetched.config == {'debug': True}


# ── Migration creates TEXT columns ──

class TestJsonFieldMigration:

    def test_create_table_has_text_columns(self, storage, tmp_db):
        M = _make_json_model('mig_create', storage)
        import sqlite3
        conn = sqlite3.connect(tmp_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(mig_create)")
        cols = {row[1]: row[2] for row in cursor.fetchall()}
        conn.close()
        assert cols.get('tags') == 'TEXT'
        assert cols.get('metadata') == 'TEXT'
        assert cols.get('scores') == 'TEXT'

    def test_migrate_adds_missing_json_columns(self, storage, tmp_db):
        """If a model gains a new dict field, migrate should add a TEXT column."""
        # Start with a simple model
        class M1(ProtoModel):
            __tablename__: ClassVar[str] = 'mig_add'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        M1.set_storage(storage)
        storage.create_table(M1)

        # "Add" a dict field via a new model class
        class M2(ProtoModel):
            __tablename__: ClassVar[str] = 'mig_add'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
            config: dict = Field(default={})
        M2.set_storage(storage)
        storage.migrate_table(M2)

        import sqlite3
        conn = sqlite3.connect(tmp_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(mig_add)")
        cols = {row[1]: row[2] for row in cursor.fetchall()}
        conn.close()
        assert cols.get('config') == 'TEXT'
