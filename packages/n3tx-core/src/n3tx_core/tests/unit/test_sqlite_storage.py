"""Tests for storage/sqlite_storage.py — SQLite storage backend."""

import os
import sqlite3
import pytest
from typing import ClassVar, Optional
from unittest.mock import patch

from pydantic import Field, BaseModel, AnyHttpUrl

from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_core.models.proto_model import ProtoModel
from n3tx_core.utils.populate import PopulateSpec
from n3tx_core.widgets import UrlField

pytestmark = pytest.mark.unit



@pytest.fixture
def tmp_db(tmp_path):
    """Create a temporary database file."""
    db_path = str(tmp_path / 'test.db')
    return db_path


@pytest.fixture
def storage(tmp_db):
    """Create a SQLiteStorage connected to a temp DB."""
    return SQLiteStorage(database=tmp_db)


def _make_model(tablename, storage_backend):
    """Helper to create a simple storable model and set up its table."""
    class M(ProtoModel):
        __tablename__: ClassVar[str] = tablename
        __storable__: ClassVar[bool] = True
        name: str = Field(default='')
        value: int = Field(default=0)
    M.set_storage(storage_backend)
    storage_backend.create_table(M)
    return M


class TestSQLiteStorageInit:

    def test_init_default(self):
        s = SQLiteStorage(database=':memory:')
        assert s.database == ':memory:'

    def test_init_custom_path(self, tmp_db):
        s = SQLiteStorage(database=tmp_db)
        assert s.database == tmp_db


class TestCreate:

    def test_simple_create(self, storage, tmp_db):
        M = _make_model('test_create1', storage)
        result = storage.create(M, {'name': 'hello', 'value': 42})
        assert result.id == 1
        assert result.name == 'hello'
        assert result.value == 42

    def test_auto_increment_id(self, storage, tmp_db):
        M = _make_model('test_create2', storage)
        r1 = storage.create(M, {'name': 'first', 'value': 1})
        r2 = storage.create(M, {'name': 'second', 'value': 2})
        assert r2.id == r1.id + 1

    def test_empty_fields(self, storage, tmp_db):
        M = _make_model('test_create3', storage)
        result = storage.create(M, {'name': '', 'value': 0})
        assert result.id == 1


class TestList:

    def test_empty_table(self, storage, tmp_db):
        M = _make_model('test_list1', storage)
        result = storage.list(M)
        assert result == []

    def test_returns_all(self, storage, tmp_db):
        M = _make_model('test_list2', storage)
        storage.create(M, {'name': 'a', 'value': 1})
        storage.create(M, {'name': 'b', 'value': 2})
        result = storage.list(M)
        assert len(result) == 2

    def test_with_filter(self, storage, tmp_db):
        M = _make_model('test_list3', storage)
        storage.create(M, {'name': 'a', 'value': 1})
        storage.create(M, {'name': 'b', 'value': 2})
        result = storage.list(M, sql_filter=("name = ?", ["a"]))
        assert len(result) == 1
        assert result[0].name == 'a'

    def test_pagination(self, storage, tmp_db):
        M = _make_model('test_list4', storage)
        for i in range(5):
            storage.create(M, {'name': f'item_{i}', 'value': i})
        result = storage.list(M, limit=2, offset=0)
        assert isinstance(result, dict)
        assert len(result['data']) == 2
        assert result['meta']['total'] == 5
        assert result['meta']['has_more'] is True

    def test_pagination_offset(self, storage, tmp_db):
        M = _make_model('test_list5', storage)
        for i in range(5):
            storage.create(M, {'name': f'item_{i}', 'value': i})
        result = storage.list(M, limit=3, offset=3)
        assert len(result['data']) == 2
        assert result['meta']['has_more'] is False

    def test_no_pagination(self, storage, tmp_db):
        M = _make_model('test_list6', storage)
        storage.create(M, {'name': 'a', 'value': 1})
        result = storage.list(M)
        assert isinstance(result, list)
        assert len(result) == 1


class TestGet:

    def test_existing_record(self, storage, tmp_db):
        M = _make_model('test_get1', storage)
        created = storage.create(M, {'name': 'hello', 'value': 42})
        result = storage.get(M, created.id)
        assert result.name == 'hello'
        assert result.value == 42

    def test_nonexistent(self, storage, tmp_db):
        M = _make_model('test_get2', storage)
        result = storage.get(M, 999)
        assert result is None

    def test_as_dict(self, storage, tmp_db):
        M = _make_model('test_get3', storage)
        created = storage.create(M, {'name': 'test', 'value': 10})
        result = storage.get(M, created.id, as_dict=True)
        assert isinstance(result, dict)
        assert result['name'] == 'test'


class TestUpdate:

    def test_partial_update(self, storage, tmp_db):
        M = _make_model('test_update1', storage)
        created = storage.create(M, {'name': 'original', 'value': 1})
        storage.update(M, created.id, {'name': 'updated'})
        result = storage.get(M, created.id)
        assert result.name == 'updated'
        assert result.value == 1  # unchanged

    def test_empty_data_raises(self, storage, tmp_db):
        M = _make_model('test_update2', storage)
        created = storage.create(M, {'name': 'test', 'value': 1})
        with pytest.raises(ValueError, match="No valid fields"):
            storage.update(M, created.id, {})


class TestDelete:

    def test_delete_existing(self, storage, tmp_db):
        M = _make_model('test_delete1', storage)
        created = storage.create(M, {'name': 'test', 'value': 1})
        storage.delete(M, created.id)
        result = storage.get(M, created.id)
        assert result is None

    def test_delete_nonexistent(self, storage, tmp_db):
        M = _make_model('test_delete2', storage)
        # Should not raise
        storage.delete(M, 999)


class TestCreateTable:

    def test_creates_table(self, storage, tmp_db):
        M = _make_model('test_ct1', storage)
        conn = sqlite3.connect(tmp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test_ct1'")
        result = cursor.fetchone()
        conn.close()
        assert result is not None

    def test_has_id_column(self, storage, tmp_db):
        M = _make_model('test_ct2', storage)
        conn = sqlite3.connect(tmp_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(test_ct2)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()
        assert 'id' in columns

    def test_has_model_columns(self, storage, tmp_db):
        M = _make_model('test_ct3', storage)
        conn = sqlite3.connect(tmp_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(test_ct3)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()
        assert 'name' in columns
        assert 'value' in columns


class TestMigrateTable:

    def test_adds_missing_column(self, storage, tmp_db):
        # Create a model and table
        M = _make_model('test_mt1', storage)
        # Extend model with a new field
        class M2(ProtoModel):
            __tablename__: ClassVar[str] = 'test_mt1'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
            value: int = Field(default=0)
            extra: str = Field(default='')
        M2.set_storage(storage)
        storage.migrate_table(M2)

        conn = sqlite3.connect(tmp_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(test_mt1)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()
        assert 'extra' in columns


class TestCRUDFlow:

    def test_full_flow(self, storage, tmp_db):
        M = _make_model('test_crud', storage)
        # Create
        created = storage.create(M, {'name': 'test', 'value': 1})
        assert created.id >= 1
        # Read
        fetched = storage.get(M, created.id)
        assert fetched.name == 'test'
        # Update
        storage.update(M, created.id, {'value': 99})
        updated = storage.get(M, created.id)
        assert updated.value == 99
        # Delete
        storage.delete(M, created.id)
        assert storage.get(M, created.id) is None
        # List
        assert storage.list(M) == []


class TestPydanticTypeCoercion:
    """Non-native Pydantic types (AnyHttpUrl, etc.) must be coerced to str
    before binding to SQLite parameters."""

    def test_create_with_anyhttpurl(self, storage, tmp_db):
        """AnyHttpUrl field should be stored as TEXT, not rejected by sqlite3."""
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'tc_create'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
            url: UrlField = Field(default=None)
        M.set_storage(storage)
        storage.create_table(M)

        result = storage.create(M, {
            'name': 'test',
            'url': AnyHttpUrl('https://example.com/placeholder'),
        })
        assert result.id == 1
        fetched = storage.get(M, result.id)
        assert 'example.com' in str(fetched.url)

    def test_update_with_anyhttpurl(self, storage, tmp_db):
        """AnyHttpUrl field should be updatable without sqlite3 binding error."""
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'tc_update'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
            url: UrlField = Field(default=None)
        M.set_storage(storage)
        storage.create_table(M)

        created = storage.create(M, {
            'name': 'test',
            'url': AnyHttpUrl('https://example.com/old'),
        })
        storage.update(M, created.id, {
            'url': AnyHttpUrl('https://example.com/new'),
        })
        updated = storage.get(M, created.id)
        assert 'new' in str(updated.url)

    def test_roundtrip_preserves_url(self, storage, tmp_db):
        """URL value should survive create → get roundtrip."""
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'tc_round'
            __storable__: ClassVar[bool] = True
            url: UrlField = Field(default=None)
        M.set_storage(storage)
        storage.create_table(M)

        original_url = 'https://example.com/grants/12345'
        created = storage.create(M, {'url': AnyHttpUrl(original_url)})
        fetched = storage.get(M, created.id)
        assert str(fetched.url) == original_url
