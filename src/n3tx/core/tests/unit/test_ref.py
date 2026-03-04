"""Tests for models/ref.py — ListRef type alias."""

import pytest
from typing import get_args, get_origin, Annotated, List, Union

from pydantic import BaseModel, Field

from n3tx.core.models.ref import ListRef, _ListRefMarker

pytestmark = pytest.mark.unit



class TestListRefMarker:

    def test_marker_stores_type(self):
        marker = _ListRefMarker(int)
        assert marker.model_type is int

    def test_marker_stores_basemodel(self):
        class M(BaseModel):
            pass
        marker = _ListRefMarker(M)
        assert marker.model_type is M


class TestListRefGetItem:

    def test_produces_annotated_type(self):
        class M(BaseModel):
            pass
        result = ListRef[M]
        # Should be Annotated[List[Union[M, str]], _ListRefMarker(M)]
        assert get_origin(result) is Annotated or hasattr(result, '__metadata__')

    def test_marker_in_metadata(self):
        class M(BaseModel):
            pass
        result = ListRef[M]
        metadata = result.__metadata__
        marker = metadata[0]
        assert isinstance(marker, _ListRefMarker)
        assert marker.model_type is M

    def test_list_union_type(self):
        class M(BaseModel):
            pass
        result = ListRef[M]
        # Unwrap Annotated to get the base type
        base = get_args(result)[0]  # List[Union[M, str]]
        assert get_origin(base) is list

    def test_can_use_in_field(self):
        class Child(BaseModel):
            name: str = ''

        class Parent(BaseModel):
            children: ListRef[Child] = Field(default=[])

        p = Parent()
        assert p.children == []

    def test_accepts_string_values(self):
        class Child(BaseModel):
            name: str = ''

        class Parent(BaseModel):
            children: ListRef[Child] = Field(default=[])

        p = Parent(children=['http://localhost/children/1', 'http://localhost/children/2'])
        assert len(p.children) == 2
        assert p.children[0] == 'http://localhost/children/1'
