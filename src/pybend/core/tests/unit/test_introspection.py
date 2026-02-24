"""Tests for utils/introspection.py — Schema and type introspection utilities."""

import pytest
from typing import Optional, List
from unittest.mock import MagicMock

from pydantic import BaseModel, Field

from utils.introspection import (
    pydantic_schema_for_type,
    record_model_type,
    _is_self_ref,
    get_list_fields,
    get_ref_fields,
    _unwrap_listref,
)
from utils.typer import Ref, _SelfRefMarker
from models.ref import ListRef, _ListRefMarker
from models.proto_model import ProtoModel


class TestPydanticSchemaForType:

    def test_str(self):
        result = pydantic_schema_for_type(str)
        assert result == {'type': 'string'}

    def test_int(self):
        result = pydantic_schema_for_type(int)
        assert result == {'type': 'integer'}

    def test_float(self):
        result = pydantic_schema_for_type(float)
        assert result == {'type': 'number'}

    def test_bool(self):
        result = pydantic_schema_for_type(bool)
        assert result == {'type': 'boolean'}

    def test_basemodel(self):
        class M(BaseModel):
            pass
        result = pydantic_schema_for_type(M)
        assert result == {'type': '$ref', '$ref': '#/$defs/M'}

    def test_list_of_str(self):
        result = pydantic_schema_for_type(List[str])
        assert result == {'type': 'array', 'items': {'type': 'string'}}

    def test_list_of_int(self):
        result = pydantic_schema_for_type(List[int])
        assert result == {'type': 'array', 'items': {'type': 'integer'}}

    def test_dict(self):
        from typing import Dict
        result = pydantic_schema_for_type(Dict[str, str])
        assert result == {'type': 'object'}

    def test_unknown_fallback(self):
        result = pydantic_schema_for_type(bytes)
        assert result == {'type': 'string'}


class TestRecordModelType:

    def test_records_basemodel(self):
        class Target(BaseModel):
            pass
        class Host(BaseModel):
            pass
        Host._referenced_models = set()
        record_model_type(Host, Target)
        assert Target in Host._referenced_models

    def test_records_from_list(self):
        class Target(BaseModel):
            pass
        class Host(BaseModel):
            pass
        Host._referenced_models = set()
        record_model_type(Host, List[Target])
        assert Target in Host._referenced_models

    def test_ignores_primitives(self):
        class Host(BaseModel):
            pass
        Host._referenced_models = set()
        record_model_type(Host, str)
        assert len(Host._referenced_models) == 0

    def test_none_type(self):
        class Host(BaseModel):
            pass
        Host._referenced_models = set()
        record_model_type(Host, None)
        assert len(Host._referenced_models) == 0


class TestIsSelfRef:

    def test_ref_self(self):
        from typing import Annotated
        annotation = Annotated[int, _SelfRefMarker()]
        assert _is_self_ref(annotation) is True

    def test_optional_ref_self(self):
        from typing import Annotated
        annotation = Optional[Annotated[int, _SelfRefMarker()]]
        assert _is_self_ref(annotation) is True

    def test_plain_int(self):
        assert _is_self_ref(int) is False

    def test_plain_str(self):
        assert _is_self_ref(str) is False

    def test_ref_self_via_typer(self):
        result = Ref['self']
        assert _is_self_ref(result) is True


class TestGetListFields:

    def test_listref_field(self):
        class Child(BaseModel):
            name: str = ''
        class Parent(BaseModel):
            children: ListRef[Child] = Field(default=[])
        result = get_list_fields(Parent)
        assert len(result) == 1
        assert result[0][0] == 'children'
        assert result[0][1] is Child

    def test_no_list_fields(self):
        class M(BaseModel):
            name: str = ''
            value: int = 0
        result = get_list_fields(M)
        assert result == []

    def test_multiple_list_fields(self):
        class A(BaseModel):
            name: str = ''
        class B(BaseModel):
            name: str = ''
        class Parent(BaseModel):
            items_a: ListRef[A] = Field(default=[])
            items_b: ListRef[B] = Field(default=[])
        result = get_list_fields(Parent)
        names = [r[0] for r in result]
        assert 'items_a' in names
        assert 'items_b' in names


class TestGetRefFields:

    def test_no_ref_fields(self):
        class M(BaseModel):
            name: str = ''
        result = get_ref_fields(M)
        assert result == []

    def test_does_not_include_selfref(self):
        from typing import ClassVar
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'introspection_ref1'
            name: str = Field(default='')
            parent_id: Optional[Ref['self']] = Field(default=None)
        result = get_ref_fields(M)
        # parent_id is a self-ref, should NOT appear
        field_names = [r[0] for r in result]
        assert 'parent_id' not in field_names


class TestUnwrapListref:

    def test_listref_marker(self):
        class M(BaseModel):
            pass
        marker = _ListRefMarker(M)
        field_type = MagicMock()
        field_type.__metadata__ = [marker]
        result = _unwrap_listref(field_type)
        assert result is M

    def test_no_marker(self):
        result = _unwrap_listref(int)
        assert result is None

    def test_pydantic_metadata(self):
        class M(BaseModel):
            pass
        marker = _ListRefMarker(M)
        result = _unwrap_listref(str, field_metadata=[marker])
        assert result is M
