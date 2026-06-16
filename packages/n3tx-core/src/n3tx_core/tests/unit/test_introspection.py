"""Tests for utils/introspection.py — Schema and type introspection utilities."""

import pytest
from typing import Dict, Optional, List, Any
from unittest.mock import MagicMock

from pydantic import BaseModel, Field

from n3tx_core.utils.introspection import (
    pydantic_schema_for_type,
    record_model_type,
    _is_self_ref,
    get_json_fields,
    get_list_fields,
    get_ref_list_fields,
    get_ref_fields,
    get_many_to_many_fields,
    _unwrap_listref,
)
from n3tx_core.utils.typer import Ref, _SelfRefMarker
from n3tx_core.models.ref import ListRef, _ListRefMarker
from n3tx_core.models.relationships import ManyToMany
from n3tx_core.models.proto_model import ProtoModel

pytestmark = pytest.mark.unit



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


class TestGetManyToManyFields:

    def test_many_to_many_field(self):
        class Tag(ProtoModel):
            __tablename__ = 'tags'

        class Product(ProtoModel):
            __tablename__ = 'products'
            tags: ManyToMany[Tag] = Field(default=[])

        assert get_many_to_many_fields(Product) == [('tags', Tag, None)]

    def test_many_to_many_is_not_json_field(self):
        class Tag(ProtoModel):
            __tablename__ = 'tags'

        class Product(ProtoModel):
            __tablename__ = 'products'
            tags: ManyToMany[Tag] = Field(default=[])

        assert 'tags' not in get_json_fields(Product)

    def test_many_to_many_through_model_field(self):
        class Tag(ProtoModel):
            __tablename__ = 'tags'

        class ProductTag(ProtoModel):
            __tablename__ = 'product_tags'

        class Product(ProtoModel):
            __tablename__ = 'products'
            tags: ManyToMany[Tag, ProductTag] = Field(default=[])

        assert get_many_to_many_fields(Product) == [('tags', Tag, ProductTag)]


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


class TestGetRefListFields:

    def test_list_ref_field_detected_as_pointer_array(self):
        class File(BaseModel):
            id: int = 0

        class Job(BaseModel):
            files: list[Ref[File]] = Field(default=[])

        assert get_ref_list_fields(Job) == [('files', File)]

    def test_optional_list_ref_field_detected(self):
        class File(BaseModel):
            id: int = 0

        class Job(BaseModel):
            files: Optional[list[Ref[File]]] = Field(default=[])

        assert get_ref_list_fields(Job) == [('files', File)]

    def test_list_ref_is_not_local_relationship_field(self):
        class File(BaseModel):
            id: int = 0

        class Job(BaseModel):
            files: list[Ref[File]] = Field(default=[])

        assert get_list_fields(Job) == []

    def test_list_ref_is_json_backed(self):
        class File(BaseModel):
            id: int = 0

        class Job(BaseModel):
            files: list[Ref[File]] = Field(default=[])

        assert 'files' in get_json_fields(Job)


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


# ===================================================================
# CG-7: Edge case tests for introspection.py
# ===================================================================

class TestPydanticSchemaForTypeEdgeCases:
    """CG-7: Additional edge cases not covered above."""

    def test_ref_type_produces_ref(self):
        """Ref[SomeModel] should produce a $ref schema."""
        class Target(BaseModel):
            pass
        ref_type = Ref[Target]
        result = pydantic_schema_for_type(ref_type)
        assert result['type'] == '$ref'
        assert '$ref' in result

    def test_list_of_basemodel(self):
        class Target(BaseModel):
            pass
        result = pydantic_schema_for_type(List[Target])
        assert result['type'] == 'array'
        assert result['items']['type'] == '$ref'

    def test_none_fallback(self):
        """None type should fall back to string."""
        result = pydantic_schema_for_type(type(None))
        assert result == {'type': 'string'}


class TestRecordModelTypeEdgeCases:
    """CG-7: Edge cases for record_model_type."""

    def test_optional_model(self):
        """Optional[Model] should still record the model."""
        class Target(BaseModel):
            pass
        class Host(BaseModel):
            pass
        Host._referenced_models = set()
        record_model_type(Host, Optional[Target])
        assert Target in Host._referenced_models

    def test_set_of_models(self):
        """set[Model] should record the model."""
        from typing import Set
        class Target(BaseModel):
            pass
        class Host(BaseModel):
            pass
        Host._referenced_models = set()
        record_model_type(Host, Set[Target])
        assert Target in Host._referenced_models

    def test_dict_with_model_value(self):
        """Dict[str, Model] should record the model."""
        from typing import Dict
        class Target(BaseModel):
            pass
        class Host(BaseModel):
            pass
        Host._referenced_models = set()
        record_model_type(Host, Dict[str, Target])
        assert Target in Host._referenced_models


class TestGetListFieldsEdgeCases:
    """CG-7: Edge cases for get_list_fields."""

    def test_optional_listref(self):
        """Optional[ListRef[T]] should still be detected."""
        class Child(BaseModel):
            name: str = ''
        class Parent(BaseModel):
            children: Optional[ListRef[Child]] = Field(default=[])
        result = get_list_fields(Parent)
        assert len(result) == 1
        assert result[0][1] is Child

    def test_plain_list_of_basemodel(self):
        """List[BaseModel] without ListRef marker should still be detected."""
        class Child(BaseModel):
            name: str = ''
        class Parent(BaseModel):
            items: List[Child] = Field(default=[])
        result = get_list_fields(Parent)
        assert len(result) == 1
        assert result[0][1] is Child

    def test_plain_list_of_primitives_ignored(self):
        """List[str] should NOT be returned."""
        class Parent(BaseModel):
            tags: List[str] = Field(default=[])
        result = get_list_fields(Parent)
        assert result == []


class TestIsSelfRefEdgeCases:
    """CG-7: Edge cases for _is_self_ref."""

    def test_list_type_not_selfref(self):
        assert _is_self_ref(List[int]) is False

    def test_dict_type_not_selfref(self):
        from typing import Dict
        assert _is_self_ref(Dict[str, str]) is False

    def test_basemodel_not_selfref(self):
        class M(BaseModel):
            pass
        assert _is_self_ref(M) is False


class TestGetJsonFields:
    """Tests for get_json_fields() — detects dict/list fields for JSON TEXT storage."""

    def test_dict_detected(self):
        class M(BaseModel):
            metadata: dict = Field(default={})
        result = get_json_fields(M)
        assert 'metadata' in result

    def test_dict_str_any_detected(self):
        class M(BaseModel):
            metadata: Dict[str, Any] = Field(default={})
        result = get_json_fields(M)
        assert 'metadata' in result

    def test_optional_dict_detected(self):
        class M(BaseModel):
            metadata: Optional[dict] = Field(default=None)
        result = get_json_fields(M)
        assert 'metadata' in result

    def test_bare_list_detected(self):
        class M(BaseModel):
            tags: list = Field(default=[])
        result = get_json_fields(M)
        assert 'tags' in result

    def test_list_str_detected(self):
        class M(BaseModel):
            tags: List[str] = Field(default=[])
        result = get_json_fields(M)
        assert 'tags' in result

    def test_list_int_detected(self):
        class M(BaseModel):
            scores: List[int] = Field(default=[])
        result = get_json_fields(M)
        assert 'scores' in result

    def test_listref_not_detected(self):
        class Child(BaseModel):
            name: str = ''
        class M(BaseModel):
            children: ListRef[Child] = Field(default=[])
        result = get_json_fields(M)
        assert 'children' not in result

    def test_list_basemodel_not_detected(self):
        class Child(BaseModel):
            name: str = ''
        class M(BaseModel):
            items: List[Child] = Field(default=[])
        result = get_json_fields(M)
        assert 'items' not in result

    def test_no_json_fields(self):
        class M(BaseModel):
            name: str = ''
            value: int = 0
        result = get_json_fields(M)
        assert result == []

    def test_mixed_fields(self):
        class Child(BaseModel):
            name: str = ''
        class M(BaseModel):
            name: str = ''
            tags: list = Field(default=[])
            metadata: dict = Field(default={})
            children: ListRef[Child] = Field(default=[])
        result = get_json_fields(M)
        assert 'tags' in result
        assert 'metadata' in result
        assert 'children' not in result
        assert 'name' not in result
