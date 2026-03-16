"""Tests for storage/sqlite_helpers.py — get_parent_fk_columns."""

import pytest
from unittest.mock import patch
from typing import ClassVar

from pydantic import Field, BaseModel

from n3tx_core.storage.sqlite_helpers import get_parent_fk_columns
from n3tx_core.models.proto_model import ProtoModel
from n3tx_core.models.ref import ListRef

pytestmark = pytest.mark.unit



class TestGetParentFkColumns:

    def test_with_registered_parent(self):
        class Child(BaseModel):
            name: str = ''

        class Parent(BaseModel):
            __tablename__: ClassVar[str] = 'helpers_parents'
            children: ListRef[Child] = Field(default=[])

        Parent.__name__ = 'Parent'

        # Patch registered_models to contain our Parent
        with patch('n3tx_core.storage.sqlite_helpers.registered_models',
                   {'helpers_parents': Parent}):
            result = get_parent_fk_columns(Child)
            assert len(result) == 1
            assert result[0] == ('parent', 'parent_id')

    def test_no_parents(self):
        class Orphan(BaseModel):
            name: str = ''

        with patch('n3tx_core.storage.sqlite_helpers.registered_models', {}):
            result = get_parent_fk_columns(Orphan)
            assert result == []

    def test_multiple_parents(self):
        class SharedChild(BaseModel):
            name: str = ''

        class ParentA(BaseModel):
            __tablename__: ClassVar[str] = 'helpers_pa'
            items: ListRef[SharedChild] = Field(default=[])
        ParentA.__name__ = 'ParentA'

        class ParentB(BaseModel):
            __tablename__: ClassVar[str] = 'helpers_pb'
            items: ListRef[SharedChild] = Field(default=[])
        ParentB.__name__ = 'ParentB'

        with patch('n3tx_core.storage.sqlite_helpers.registered_models',
                   {'helpers_pa': ParentA, 'helpers_pb': ParentB}):
            result = get_parent_fk_columns(SharedChild)
            fk_cols = [r[1] for r in result]
            assert 'parenta_id' in fk_cols
            assert 'parentb_id' in fk_cols

    def test_unrelated_model_ignored(self):
        class Child(BaseModel):
            name: str = ''

        class Unrelated(BaseModel):
            __tablename__: ClassVar[str] = 'helpers_unrelated'
            other: str = ''
        Unrelated.__name__ = 'Unrelated'

        with patch('n3tx_core.storage.sqlite_helpers.registered_models',
                   {'helpers_unrelated': Unrelated}):
            result = get_parent_fk_columns(Child)
            assert result == []
