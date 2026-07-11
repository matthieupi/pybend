"""Tests for utils/typer.py — Ref type and flatten_refs utility."""

import pytest
from typing import Annotated, get_args

from pydantic import BaseModel, Field

from n3tx_core.utils.typer import Ref, flatten_refs, _SelfRefMarker

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
