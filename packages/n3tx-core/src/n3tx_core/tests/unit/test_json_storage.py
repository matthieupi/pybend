"""Tests for storage/json_storage.py — JSONStorage CRUD operations.

CG-3: Coverage gap — json_storage.py has zero test coverage.
Tests file-based JSON storage backend implementing AbstractStorage.

Note: JSONStorage is an older/alternative backend that does NOT implement
the current AbstractStorage interface (missing `get`/`list` — it has
`get_all`/`get_by_id` instead). We can't instantiate it directly because
of abstract method enforcement. We test it by subclassing with stubs.
"""

import json
import os
import tempfile
import pytest
from typing import ClassVar, Any, Dict, List, Type
from pydantic import Field

from n3tx_core.storage.json_storage import JSONStorage
from n3tx_core.storage.abstract_storage import AbstractStorage
from n3tx_core.models.proto_model import ProtoModel

pytestmark = pytest.mark.unit



class _TestableJSONStorage(JSONStorage):
    """Concrete subclass that stubs the missing abstract methods
    so we can instantiate and test the JSON file operations."""

    def get(self, model_class, id_=None, as_dict=False, populate=None, **kwargs):
        return self.get_by_id(model_class, id_)

    def list(self, model_class, sql_filter=None, limit=None, offset=None, populate=None, ids=None):
        return self.get_all(model_class)


@pytest.fixture
def tmp_dir():
    """Create a temporary directory for JSON storage files."""
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def storage(tmp_dir):
    """Create a testable JSONStorage instance pointing at a temp directory."""
    return _TestableJSONStorage(directory=tmp_dir)


class _Item(ProtoModel):
    """Minimal model for testing JSONStorage."""
    __tablename__: ClassVar[str] = 'items'
    name: str = Field(default='')
    value: int = Field(default=0)


class TestJSONStorageInit:

    def test_creates_directory_if_missing(self):
        with tempfile.TemporaryDirectory() as parent:
            subdir = os.path.join(parent, "nested", "data")
            storage = _TestableJSONStorage(directory=subdir)
            assert os.path.isdir(subdir)

    def test_uses_existing_directory(self, tmp_dir):
        storage = _TestableJSONStorage(directory=tmp_dir)
        assert storage.directory == tmp_dir

    def test_is_abstract_storage(self, storage):
        assert isinstance(storage, AbstractStorage)

    def test_json_storage_missing_methods(self):
        """JSONStorage itself can't be instantiated because it lacks get/list."""
        with tempfile.TemporaryDirectory() as d:
            with pytest.raises(TypeError, match="abstract methods"):
                JSONStorage(directory=d)


class TestCreateTable:

    def test_creates_json_file(self, storage, tmp_dir):
        storage.create_table(_Item)
        file_path = os.path.join(tmp_dir, "items.json")
        assert os.path.exists(file_path)

    def test_file_contains_empty_list(self, storage, tmp_dir):
        storage.create_table(_Item)
        file_path = os.path.join(tmp_dir, "items.json")
        with open(file_path) as f:
            data = json.load(f)
        assert data == []

    def test_idempotent(self, storage, tmp_dir):
        storage.create_table(_Item)
        storage.create_table(_Item)
        file_path = os.path.join(tmp_dir, "items.json")
        with open(file_path) as f:
            data = json.load(f)
        assert data == []


class TestCreate:

    def test_returns_model_instance(self, storage):
        storage.create_table(_Item)
        result = storage.create(_Item, {"name": "test", "value": 42})
        assert isinstance(result, _Item)

    def test_assigns_id(self, storage):
        storage.create_table(_Item)
        result = storage.create(_Item, {"name": "first", "value": 1})
        assert result.id == 1

    def test_auto_increments_id(self, storage):
        storage.create_table(_Item)
        r1 = storage.create(_Item, {"name": "a", "value": 1})
        r2 = storage.create(_Item, {"name": "b", "value": 2})
        assert r1.id == 1
        assert r2.id == 2

    def test_preserves_data(self, storage):
        storage.create_table(_Item)
        result = storage.create(_Item, {"name": "hello", "value": 99})
        assert result.name == "hello"
        assert result.value == 99

    def test_persists_to_file(self, storage, tmp_dir):
        storage.create_table(_Item)
        storage.create(_Item, {"name": "persisted", "value": 7})
        file_path = os.path.join(tmp_dir, "items.json")
        with open(file_path) as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["name"] == "persisted"


class TestGetAll:

    def test_empty(self, storage):
        storage.create_table(_Item)
        result = storage.get_all(_Item)
        assert result == []

    def test_returns_all(self, storage):
        storage.create_table(_Item)
        storage.create(_Item, {"name": "a", "value": 1})
        storage.create(_Item, {"name": "b", "value": 2})
        result = storage.get_all(_Item)
        assert len(result) == 2

    def test_returns_model_instances(self, storage):
        storage.create_table(_Item)
        storage.create(_Item, {"name": "a", "value": 1})
        result = storage.get_all(_Item)
        assert isinstance(result[0], _Item)


class TestGetById:

    def test_existing(self, storage):
        storage.create_table(_Item)
        created = storage.create(_Item, {"name": "find me", "value": 42})
        result = storage.get_by_id(_Item, created.id)
        assert result is not None
        assert result.name == "find me"

    def test_nonexistent_returns_none(self, storage):
        storage.create_table(_Item)
        result = storage.get_by_id(_Item, 99999)
        assert result is None

    def test_returns_correct_id(self, storage):
        storage.create_table(_Item)
        storage.create(_Item, {"name": "a", "value": 1})
        r2 = storage.create(_Item, {"name": "b", "value": 2})
        result = storage.get_by_id(_Item, r2.id)
        assert result.name == "b"


class TestUpdate:

    def test_updates_field(self, storage, tmp_dir):
        storage.create_table(_Item)
        created = storage.create(_Item, {"name": "old", "value": 1})
        storage.update(_Item, created.id, {"name": "new"})
        # Verify from file
        file_path = os.path.join(tmp_dir, "items.json")
        with open(file_path) as f:
            data = json.load(f)
        assert data[0]["name"] == "new"

    def test_nonexistent_no_error(self, storage):
        storage.create_table(_Item)
        # Should not raise
        storage.update(_Item, 99999, {"name": "ghost"})

    def test_preserves_other_fields(self, storage, tmp_dir):
        storage.create_table(_Item)
        created = storage.create(_Item, {"name": "keep", "value": 99})
        storage.update(_Item, created.id, {"name": "changed"})
        file_path = os.path.join(tmp_dir, "items.json")
        with open(file_path) as f:
            data = json.load(f)
        assert data[0]["value"] == 99


class TestDelete:

    def test_removes_record(self, storage, tmp_dir):
        storage.create_table(_Item)
        created = storage.create(_Item, {"name": "bye", "value": 1})
        storage.delete(_Item, created.id)
        file_path = os.path.join(tmp_dir, "items.json")
        with open(file_path) as f:
            data = json.load(f)
        assert len(data) == 0

    def test_nonexistent_no_error(self, storage):
        storage.create_table(_Item)
        # Should not raise
        storage.delete(_Item, 99999)

    def test_only_removes_target(self, storage, tmp_dir):
        storage.create_table(_Item)
        r1 = storage.create(_Item, {"name": "a", "value": 1})
        r2 = storage.create(_Item, {"name": "b", "value": 2})
        storage.delete(_Item, r1.id)
        file_path = os.path.join(tmp_dir, "items.json")
        with open(file_path) as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["name"] == "b"
