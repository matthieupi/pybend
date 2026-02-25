"""Tests for utils/typer.py — Ref type and flatten_refs utility."""

import pytest
from typing import Annotated, get_args

from pydantic import BaseModel, Field

from pybend.core.utils.typer import Ref, flatten_refs, _SelfRefMarker

pytestmark = pytest.mark.unit



class TestSelfRefMarker:

    def test_instance(self):
        marker = _SelfRefMarker()
        assert isinstance(marker, _SelfRefMarker)


class TestRefClassGetItem:

    def test_self_produces_annotated_int(self):
        result = Ref['self']
        # Should be Annotated[int, _SelfRefMarker()]
        args = get_args(result)
        assert args[0] is int
        assert isinstance(args[1], _SelfRefMarker)

    def test_non_self_returns_generic(self):
        class M(BaseModel):
            pass
        result = Ref[M]
        # Should be a generic alias
        assert result is not None


class TestRefInit:

    def test_from_int(self):
        r = Ref(5)
        assert r.id == 5

    def test_from_dict(self):
        r = Ref({'id': 10})
        assert r.id == 10

    def test_from_model(self):
        class M(BaseModel):
            id: int = 0
        m = M(id=7)
        r = Ref(m)
        assert r.id == 7

    def test_from_zero(self):
        r = Ref(0)
        assert r.id == 0

    def test_invalid_raises(self):
        with pytest.raises(ValueError, match="Invalid FK assignment"):
            Ref("invalid_string")

    def test_list_raises(self):
        with pytest.raises(ValueError, match="Invalid FK assignment"):
            Ref([1, 2, 3])


class TestRefInt:

    def test_int_conversion(self):
        r = Ref(5)
        assert int(r) == 5

    def test_int_zero(self):
        r = Ref(0)
        assert int(r) == 0


class TestRefStr:

    def test_str(self):
        r = Ref(5)
        assert str(r) == '<Ref id=5>'

    def test_repr(self):
        r = Ref(5)
        assert repr(r) == '5'


class TestRefJson:

    def test_json_returns_id(self):
        r = Ref(42)
        assert r.__json__() == 42


class TestRefModelDump:

    def test_model_dump(self):
        r = Ref(99)
        assert r.model_dump() == 99


class TestRefToPython:

    def test_to_python(self):
        r = Ref(7)
        assert r.to_python() == 7


class TestRefValidate:

    def test_validate_int(self):
        r = Ref.validate(5)
        assert isinstance(r, Ref)
        assert r.id == 5


class TestFlattenRefs:

    def test_basic_model(self):
        class M(BaseModel):
            name: str = 'test'
            value: int = 10
        m = M()
        result = flatten_refs(m)
        assert result == {'name': 'test', 'value': 10}

    def test_nested_model(self):
        class Inner(BaseModel):
            x: int = 5
        class Outer(BaseModel):
            inner: Inner = Field(default_factory=Inner)
        o = Outer()
        result = flatten_refs(o)
        assert result['inner'] == {'x': 5}

    def test_empty_model(self):
        class M(BaseModel):
            pass
        m = M()
        result = flatten_refs(m)
        assert result == {}
