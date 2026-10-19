"""Tests for utils/registrar.py — Model registry and registration."""

import pytest
from unittest.mock import MagicMock
from typing import ClassVar

from pydantic import Field

from n3tx_core.models.proto_model import ProtoModel
from n3tx_core.utils.registrar import (
    register_model, registered_models,
    prepare_model, apply_registration, RegistrationResult,
)

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


# ===================================================================
# TestPrepareModel — pure, no side effects
# ===================================================================

class TestPrepareModel:

    def test_returns_registration_result(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'prep_t1'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        mock_storage = MagicMock()
        result = prepare_model(M, storage=mock_storage)
        assert isinstance(result, RegistrationResult)
        assert result.model_class is M
        assert result.tablename == 'prep_t1'
        assert result.is_storable is True
        assert result.storage is mock_storage

    def test_no_mutation_of_registered_models(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'prep_t2'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        mock_storage = MagicMock()
        before = dict(registered_models)
        prepare_model(M, storage=mock_storage)
        assert registered_models == before, "prepare_model mutated registered_models"

    def test_no_storage_calls(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'prep_t3'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        mock_storage = MagicMock()
        prepare_model(M, storage=mock_storage)
        mock_storage.create_table.assert_not_called()
        mock_storage.migrate_table.assert_not_called()

    def test_storable_without_storage_raises(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'prep_t4'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        with pytest.raises(ValueError, match="Storage backend must be provided"):
            prepare_model(M, storage=None)

    def test_non_storable_no_storage_needed(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'prep_t5'
            name: str = Field(default='')
        result = prepare_model(M)
        assert result.is_storable is False
        assert result.storage is None

# ===================================================================
# TestApplyRegistration — executes side effects
# ===================================================================

class TestApplyRegistration:

    def test_adds_to_registered_models(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'apply_t1'
            name: str = Field(default='')
        result = RegistrationResult(
            model_class=M, tablename='apply_t1', storage=None,
            is_storable=False,
        )
        apply_registration(result)
        assert 'apply_t1' in registered_models

    def test_calls_storage_for_storable(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'apply_t2'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        mock_storage = MagicMock()
        mock_storage.create_table.return_value = None
        mock_storage.migrate_table.return_value = None
        result = RegistrationResult(
            model_class=M, tablename='apply_t2', storage=mock_storage,
            is_storable=True,
        )
        apply_registration(result)
        mock_storage.create_table.assert_called_once()
        mock_storage.migrate_table.assert_called_once_with(M)
        assert M.storage is mock_storage
