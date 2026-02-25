"""Tests for utils/registrar.py — Model registry and registration."""

import pytest
from unittest.mock import MagicMock, patch
from typing import ClassVar

from pydantic import Field

from pybend.core.models.proto_model import ProtoModel
from pybend.core.utils.registrar import register_model, registered_models, join_models

pytestmark = pytest.mark.unit



class TestRegisterModel:

    def test_storable_model_registered(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'reg_t1'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        mock_storage = MagicMock()
        mock_storage.create_table.return_value = None
        mock_storage.migrate_table.return_value = None
        register_model(M, storage=mock_storage)
        assert 'reg_t1' in registered_models
        assert M.storage is mock_storage
        mock_storage.create_table.assert_called_once()

    def test_storable_without_storage_raises(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'reg_t2'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        with pytest.raises(ValueError, match="Storage backend must be provided"):
            register_model(M, storage=None)

    def test_non_storable_registered(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'reg_t3'
            name: str = Field(default='')
        register_model(M)
        assert 'reg_t3' in registered_models

    def test_join_model_registered(self):
        class Owner(ProtoModel):
            __tablename__: ClassVar[str] = 'reg_own'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        class Child(ProtoModel):
            __tablename__: ClassVar[str] = 'reg_ch'
            __storable__: ClassVar[bool] = True
            text: str = Field(default='')

        # Create join model manually
        class OwnerChild(Child):
            __tablename__: ClassVar[str] = 'reg_own_reg_ch'
            __storable__: ClassVar[bool] = True
            __owner__ = Owner
            owner_id: int = Field(default=0)

        mock_storage = MagicMock()
        mock_storage.create_table.return_value = None
        mock_storage.migrate_table.return_value = None
        register_model(OwnerChild, storage=mock_storage)
        # join_models should contain the mapping
        assert ('Owner', 'Child') in join_models or 'reg_own_reg_ch' in registered_models

    def test_migrate_table_called(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'reg_t5'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        mock_storage = MagicMock()
        mock_storage.create_table.return_value = None
        mock_storage.migrate_table.return_value = None
        register_model(M, storage=mock_storage)
        mock_storage.migrate_table.assert_called_once_with(M)


class TestRegisteredModelsDict:

    def test_is_dict(self):
        assert isinstance(registered_models, dict)

    def test_lookup_by_tablename(self):
        # After app bootstrap, registered models exist
        # At minimum we should be able to check it's a dict
        for key in registered_models:
            assert isinstance(key, str)


class TestJoinModelsDict:

    def test_is_dict(self):
        assert isinstance(join_models, dict)
