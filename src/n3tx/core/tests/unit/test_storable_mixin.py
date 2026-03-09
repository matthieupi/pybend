"""Tests for models/storable_mixin.py — StorableMixin CRUD."""
import pytest
from unittest.mock import MagicMock
from typing import ClassVar
from pydantic import Field
from n3tx.core.models.proto_model import ProtoModel
from n3tx.core.models.storable_mixin import StorableMixin

pytestmark = pytest.mark.unit



class TestStorageDict:
    def test_returns_dict(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'sd1'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='hello')
            value: int = Field(default=42)
        m = M(name='test', value=10)
        d = m._storage_dict(exclude_unset=False)
        assert d['name'] == 'test'
        assert d['value'] == 10

    def test_exclude_unset(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'sd2'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='hello')
            value: int = Field(default=42)
        m = M(name='explicit')
        d = m._storage_dict(exclude_unset=True)
        assert 'name' in d
        assert 'value' not in d

    def test_excluded_field_readded(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'sd3'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
            secret: str = Field(default='hidden', exclude=True)
        m = M(name='test', secret='my_secret')
        d = m._storage_dict(exclude_unset=False)
        assert d['secret'] == 'my_secret'


class TestSave:
    def test_new_calls_create(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'sv1'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        M.storage = MagicMock()
        M.storage.create.return_value = M(id=1, name='created')
        m = M(name='new')
        m.save()

    def test_existing_calls_update(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'sv2'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        M.storage = MagicMock()
        M.storage.update.return_value = None
        M.storage.get.return_value = M(id=5, name='updated')
        m = M(id=5, name='updated_item')
        m.save()


class TestSetStorage:
    def test_assigned(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'ss1'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        mock = MagicMock()
        M.set_storage(mock)
        assert M.storage is mock

    def test_set_none(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'ss2'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        M.set_storage(MagicMock())
        M.set_storage(None)
        assert M.storage is None


class TestCreate:
    def test_simple(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'cr1'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        M.storage = MagicMock()
        M.storage.create.return_value = M(id=1, name='created')
        result = M.create(M(name='test'))
        M.storage.create.assert_called_once()
        assert result.id == 1


class TestList:
    def test_delegates(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'ls1'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        M.storage = MagicMock()
        M.storage.list.return_value = []
        M.list()
        M.storage.list.assert_called_once_with(M, sql_filter=None, limit=None, offset=None, populate=None, ids=None)

    def test_with_filter(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'ls2'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        M.storage = MagicMock()
        M.storage.list.return_value = []
        M.list(sql_filter=("name = ?", ["test"]))
        M.storage.list.assert_called_once()


class TestGet:
    def test_delegates(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'gt1'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        M.storage = MagicMock()
        M.storage.get.return_value = M(id=1, name='found')
        M.get(1)
        M.storage.get.assert_called_once()

    def test_nonexistent(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'gt2'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        M.storage = MagicMock()
        M.storage.get.return_value = None
        assert M.get(999) is None


class TestUpdate:
    def test_with_dict(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'up1'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        M.storage = MagicMock()
        M.storage.get.return_value = M(id=1, name='updated')
        M.update(1, {'name': 'updated'})
        M.storage.update.assert_called_once()

    def test_invalid_type_raises(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'up2'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        M.storage = MagicMock()
        with pytest.raises(ValueError, match="Invalid data type"):
            M.update(1, "string")


class TestDelete:
    def test_delegates(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'dl1'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        M.storage = MagicMock()
        M.delete(1)
        M.storage.delete.assert_called_once_with(M, 1)


class TestListPagination:
    """UT-9: list() with pagination parameters."""

    def test_list_with_limit_offset(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'lp1'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        M.storage = MagicMock()
        M.storage.list.return_value = {'data': [], 'meta': {'total': 0}}
        M.list(limit=10, offset=5)
        M.storage.list.assert_called_once_with(M, sql_filter=None, limit=10, offset=5, populate=None, ids=None)

    def test_list_with_sql_filter_and_pagination(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'lp2'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        M.storage = MagicMock()
        M.storage.list.return_value = []
        filt = ("name = ?", ["test"])
        M.list(sql_filter=filt, limit=5)
        M.storage.list.assert_called_once_with(M, sql_filter=filt, limit=5, offset=None, populate=None, ids=None)

    def test_list_with_populate(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'lp3'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        M.storage = MagicMock()
        M.storage.list.return_value = []
        M.list(populate='comments')
        M.storage.list.assert_called_once_with(M, sql_filter=None, limit=None, offset=None, populate='comments', ids=None)


class TestGetWithPopulate:
    """UT-9: get() with populate parameter."""

    def test_get_with_populate(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'gp1'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        M.storage = MagicMock()
        M.storage.get.return_value = M(id=1, name='found')
        M.get(1, populate='comments')
        M.storage.get.assert_called_once_with(M, 1, as_dict=False, populate='comments')

    def test_get_as_dict(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'gp2'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        M.storage = MagicMock()
        M.storage.get.return_value = {'id': 1, 'name': 'dict'}
        M.get(1, as_dict=True)
        M.storage.get.assert_called_once_with(M, 1, as_dict=True, populate=None)


class TestSaveEdgeCases:
    """UT-9: save() edge cases."""

    def test_save_zero_id_calls_create(self):
        """id=0 is falsy, so save should call create."""
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'se1'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        M.storage = MagicMock()
        M.storage.create.return_value = M(id=1, name='created')
        m = M(id=0, name='new')
        m.save()
        M.storage.create.assert_called_once()

    def test_update_with_model_instance(self):
        """update() accepts a BaseModel instance."""
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'se2'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        M.storage = MagicMock()
        M.storage.get.return_value = M(id=1, name='updated')
        updated_instance = M(name='new_name')
        result = M.update(1, updated_instance)
        M.storage.update.assert_called_once()


class TestCreateTable:
    """UT-9: create_table delegates to storage."""

    def test_delegates(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'ct1'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        M.storage = MagicMock()
        M.create_table()
        M.storage.create_table.assert_called_once_with(M)
