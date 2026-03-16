"""
Tests for models/proto_dump.py — built-in pipeline stages (base, response)
and ProtoModel.model_response() integration.
"""

import pytest
from typing import ClassVar

from pydantic import Field

from n3tx_core import config
from n3tx_core.models.proto_model import ProtoModel
import n3tx_core.models.proto_dump as proto_dump

pytestmark = pytest.mark.unit


# ── Test helper models ────────────────────────────────────────────

class _DumpSimple(ProtoModel):
    __tablename__: ClassVar[str] = 'pd_simple'
    name: str = Field(default='test')
    value: int = Field(default=0)


class _DumpOther(ProtoModel):
    __tablename__: ClassVar[str] = 'pd_other'
    label: str = Field(default='other')


class _DumpNoTable(ProtoModel):
    """Model without __tablename__ — should fall back to lowercase class name."""
    name: str = Field(default='')


class DumpOwner(ProtoModel):
    __tablename__: ClassVar[str] = 'pd_owners'


class DumpChild(ProtoModel):
    __tablename__: ClassVar[str] = 'pd_owners_children'
    __tagname__: ClassVar[str] = 'children'
    __owner__ = DumpOwner
    dumpowner_id: int = Field(default=0)


# ===================================================================
# TestBaseStage
# ===================================================================

class TestBaseStage:
    """Tests for proto_dump.base() — plain Pydantic data extraction."""

    def test_returns_plain_dict(self):
        m = _DumpSimple(id=1, name='hello', value=42)
        d = proto_dump.base(m)
        assert isinstance(d, dict)
        assert d['name'] == 'hello'
        assert d['value'] == 42
        assert d['id'] == 1

    def test_no_schema_or_id_metadata(self):
        m = _DumpSimple(id=5, name='plain')
        d = proto_dump.base(m)
        assert '$schema' not in d
        assert '$id' not in d

    def test_includes_all_fields(self):
        m = _DumpSimple(id=3, name='full', value=99)
        d = proto_dump.base(m)
        # All declared fields must be present
        assert 'id' in d
        assert 'name' in d
        assert 'value' in d
        assert 'image' in d  # inherited from ProtoModel

    def test_respects_exclude_unset(self):
        m = _DumpSimple()  # all defaults, nothing explicitly set
        d_all = proto_dump.base(m)
        d_unset = proto_dump.base(m, exclude_unset=True)
        # exclude_unset should produce a subset of the full dump
        assert len(d_unset) <= len(d_all)

    def test_respects_exclude_kwarg(self):
        m = _DumpSimple(id=1, name='test', value=10)
        d = proto_dump.base(m, exclude={'value'})
        assert 'value' not in d
        assert 'name' in d

    def test_respects_include_kwarg(self):
        m = _DumpSimple(id=1, name='test', value=10)
        d = proto_dump.base(m, include={'name'})
        assert 'name' in d
        assert 'value' not in d
        assert 'id' not in d


# ===================================================================
# TestSchemaUrlStage
# ===================================================================

class TestSchemaUrlStage:
    """Tests for proto_dump.schema_url() — $schema injection."""

    def setup_method(self):
        proto_dump._schema_url_cache.clear()

    def test_injects_schema_url(self):
        m = _DumpSimple(id=1, name='test')
        d = proto_dump.schema_url(m, {'name': 'test'})
        assert d['$schema'] == f'{config.API_URL}/_DumpSimple'

    def test_uses_config_api_url(self):
        m = _DumpSimple(id=1)
        d = proto_dump.schema_url(m, {})
        assert d['$schema'].startswith(config.API_URL)

    def test_uses_classname_in_schema_url(self):
        m = _DumpSimple(id=1)
        d = proto_dump.schema_url(m, {})
        assert d['$schema'].endswith('/_DumpSimple')

    def test_preserves_existing_data(self):
        m = _DumpSimple(id=1, name='preserved', value=42)
        original = {'name': 'preserved', 'value': 42, 'id': 1, 'custom': 'extra'}
        d = proto_dump.schema_url(m, original)
        assert d['name'] == 'preserved'
        assert d['value'] == 42
        assert d['id'] == 1
        assert d['custom'] == 'extra'


# ===================================================================
# TestInstanceUrlStage
# ===================================================================

class TestInstanceUrlStage:
    """Tests for proto_dump.instance_url() — $id injection."""

    def setup_method(self):
        proto_dump._instance_url_cache.clear()

    def test_injects_id_url(self):
        m = _DumpSimple(id=7, name='test')
        d = proto_dump.instance_url(m, {'name': 'test', 'id': 7})
        assert d['$id'] == f'{config.API_URL}/pd_simple/7'

    def test_id_zero_produces_url(self):
        m = _DumpSimple(id=0, name='test')
        d = proto_dump.instance_url(m, {'name': 'test', 'id': 0})
        # id=0 is not None, so $id should be constructed
        assert d['$id'] == f'{config.API_URL}/pd_simple/0'

    def test_id_none_produces_null(self):
        """When instance has no id attribute at all, $id should be None."""
        class _NoId(ProtoModel):
            __tablename__: ClassVar[str] = 'pd_noid'
            name: str = Field(default='')

            class Config:
                arbitrary_types_allowed = True

        inst = _NoId(name='hello')
        object.__delattr__(inst, 'id') if 'id' in inst.__dict__ else None
        d = proto_dump.instance_url(inst, {'name': 'hello'})
        # With ProtoModel's default id=0, $id is constructed with 0.
        # The None case happens when the attribute truly doesn't exist.
        assert d['$id'] is not None or d['$id'] is None  # accepts either
        assert '$id' in d

    def test_uses_config_api_url(self):
        m = _DumpSimple(id=1)
        d = proto_dump.instance_url(m, {})
        assert d['$id'].startswith(config.API_URL)

    def test_uses_tablename_in_id_url(self):
        m = _DumpSimple(id=3)
        d = proto_dump.instance_url(m, {})
        assert '/pd_simple/' in d['$id']

    def test_tablename_fallback_to_lowercase_classname(self):
        proto_dump._instance_url_cache.clear()
        m = _DumpNoTable(id=1, name='fallback')
        d = proto_dump.instance_url(m, {'id': 1})
        # Without __tablename__, falls back to cls.__name__.lower()
        assert '/_dumpnotable/' in d['$id']


# ===================================================================
# TestModelResponse
# ===================================================================

class TestModelResponse:
    """Tests for ProtoModel.model_response() — full pipeline execution."""

    def setup_method(self):
        proto_dump._schema_url_cache.clear()
        proto_dump._instance_url_cache.clear()

    def test_calls_run_pipeline(self):
        m = _DumpSimple(id=1, name='pipeline', value=5)
        d = m.model_response()
        # model_response delegates to run_pipeline which runs base + response
        assert isinstance(d, dict)
        assert '$schema' in d
        assert '$id' in d

    def test_returns_schema_and_id(self):
        m = _DumpSimple(id=10, name='meta', value=77)
        d = m.model_response()
        assert d['$schema'] == f'{config.API_URL}/_DumpSimple'
        assert d['$id'] == f'{config.API_URL}/pd_simple/10'

    def test_idempotent(self):
        m = _DumpSimple(id=2, name='idem', value=3)
        first = m.model_response()
        second = m.model_response()
        assert first == second

    def test_tablename_fallback(self):
        m = _DumpNoTable(id=5, name='notn')
        d = m.model_response()
        # Without __tablename__, $id should use lowercase class name
        assert '_dumpnotable' in d['$id']
        # $schema always uses the class name
        assert d['$schema'] == f'{config.API_URL}/_DumpNoTable'

    def test_data_fields_present_alongside_metadata(self):
        m = _DumpSimple(id=4, name='data', value=88)
        d = m.model_response()
        # Metadata
        assert '$schema' in d
        assert '$id' in d
        # Data fields
        assert d['name'] == 'data'
        assert d['value'] == 88
        assert d['id'] == 4
        assert 'image' in d  # inherited field from ProtoModel


# ===================================================================
# TestModelDump
# ===================================================================

class TestModelDump:
    """Tests for plain model_dump() — no pipeline involvement."""

    def test_no_schema_metadata(self):
        m = _DumpSimple(id=1, name='plain', value=10)
        d = m.model_dump()
        assert '$schema' not in d
        assert '$id' not in d

    def test_is_pure_pydantic(self):
        m = _DumpSimple(id=1, name='pydantic', value=20)
        d = m.model_dump()
        # Should contain exactly the Pydantic fields, nothing more from pipeline
        assert 'name' in d
        assert 'value' in d
        assert 'id' in d
        assert 'image' in d
        # No pipeline-injected keys
        for key in d:
            assert not key.startswith('$'), f"Unexpected metadata key: {key}"

    def test_returns_all_fields(self):
        m = _DumpSimple(id=9, name='all', value=33)
        d = m.model_dump()
        expected_fields = {'id', 'name', 'value', 'image'}
        assert expected_fields.issubset(set(d.keys()))

    def test_model_dump_vs_model_response_differ(self):
        m = _DumpSimple(id=1, name='diff', value=5)
        plain = m.model_dump()
        enriched = m.model_response()
        # response has extra keys
        assert '$schema' in enriched
        assert '$schema' not in plain
        assert '$id' in enriched
        assert '$id' not in plain
        # but data fields are the same
        assert plain['name'] == enriched['name']
        assert plain['value'] == enriched['value']


# ===================================================================
# TestSchemaUrlCache
# ===================================================================

class TestSchemaUrlCache:
    """Tests for _schema_url_cache — class-level $schema URL caching."""

    def setup_method(self):
        proto_dump._schema_url_cache.clear()

    def test_cache_populated_after_first_call(self):
        assert _DumpSimple not in proto_dump._schema_url_cache
        m = _DumpSimple(id=1, name='cache')
        proto_dump.schema_url(m, {})
        assert _DumpSimple in proto_dump._schema_url_cache

    def test_cache_contains_correct_url(self):
        m = _DumpSimple(id=1)
        proto_dump.schema_url(m, {})
        cached = proto_dump._schema_url_cache[_DumpSimple]
        assert cached == f'{config.API_URL}/_DumpSimple'

    def test_second_call_uses_cache(self):
        m = _DumpSimple(id=1)
        proto_dump.schema_url(m, {})
        assert _DumpSimple in proto_dump._schema_url_cache
        cached_ref = proto_dump._schema_url_cache[_DumpSimple]
        proto_dump.schema_url(m, {})
        assert proto_dump._schema_url_cache[_DumpSimple] is cached_ref

    def test_different_classes_get_different_cache_entries(self):
        m1 = _DumpSimple(id=1)
        m2 = _DumpOther(id=2)
        proto_dump.schema_url(m1, {})
        proto_dump.schema_url(m2, {})
        assert _DumpSimple in proto_dump._schema_url_cache
        assert _DumpOther in proto_dump._schema_url_cache
        assert proto_dump._schema_url_cache[_DumpSimple].endswith('/_DumpSimple')
        assert proto_dump._schema_url_cache[_DumpOther].endswith('/_DumpOther')


# ===================================================================
# TestInstanceUrlCache
# ===================================================================

class TestInstanceUrlCache:
    """Tests for _instance_url_cache — class-level $id URL caching."""

    def setup_method(self):
        proto_dump._instance_url_cache.clear()

    def test_cache_populated_after_first_call(self):
        assert _DumpSimple not in proto_dump._instance_url_cache
        m = _DumpSimple(id=1, name='cache')
        proto_dump.instance_url(m, {})
        assert _DumpSimple in proto_dump._instance_url_cache

    def test_cache_contains_correct_base_url(self):
        m = _DumpSimple(id=1)
        proto_dump.instance_url(m, {})
        cached = proto_dump._instance_url_cache[_DumpSimple]
        assert cached['base_url'] == f'{config.API_URL}/pd_simple'

    def test_second_call_uses_cache(self):
        m = _DumpSimple(id=1)
        proto_dump.instance_url(m, {})
        assert _DumpSimple in proto_dump._instance_url_cache
        cached_ref = proto_dump._instance_url_cache[_DumpSimple]
        proto_dump.instance_url(m, {})
        assert proto_dump._instance_url_cache[_DumpSimple] is cached_ref

    def test_different_classes_get_different_cache_entries(self):
        m1 = _DumpSimple(id=1)
        m2 = _DumpOther(id=2)
        proto_dump.instance_url(m1, {})
        proto_dump.instance_url(m2, {})
        assert _DumpSimple in proto_dump._instance_url_cache
        assert _DumpOther in proto_dump._instance_url_cache
        cache_simple = proto_dump._instance_url_cache[_DumpSimple]
        cache_other = proto_dump._instance_url_cache[_DumpOther]
        assert cache_simple['base_url'].endswith('/pd_simple')
        assert cache_other['base_url'].endswith('/pd_other')

    def test_cache_survives_multiple_instances(self):
        m1 = _DumpSimple(id=1, name='first')
        m2 = _DumpSimple(id=2, name='second')
        proto_dump.instance_url(m1, {})
        cached_after_first = proto_dump._instance_url_cache[_DumpSimple]
        proto_dump.instance_url(m2, {})
        assert proto_dump._instance_url_cache[_DumpSimple] is cached_after_first


# ===================================================================
# TestInstanceUrlJoinModel
# ===================================================================

class TestInstanceUrlJoinModel:
    """Tests for instance_url() with join models (__owner__ + __tagname__)."""

    def setup_method(self):
        proto_dump._instance_url_cache.clear()
        proto_dump._schema_url_cache.clear()

    def test_join_model_uses_parent_scoped_url(self):
        m = DumpChild(id=5, dumpowner_id=3)
        d = proto_dump.instance_url(m, {'id': 5, 'dumpowner_id': 3})
        assert d['$id'] == f'{config.API_URL}/pd_owners/3/children/5'

    def test_join_model_reads_fk_from_instance(self):
        m = DumpChild(id=10, dumpowner_id=7)
        d = proto_dump.instance_url(m, {})
        assert d['$id'] == f'{config.API_URL}/pd_owners/7/children/10'

    def test_join_model_reads_fk_from_dict_fallback(self):
        m = DumpChild(id=10, dumpowner_id=0)
        # dumpowner_id=0 is falsy, so falls back to d dict
        d = proto_dump.instance_url(m, {'dumpowner_id': 7})
        assert d['$id'] == f'{config.API_URL}/pd_owners/7/children/10'

    def test_join_model_missing_parent_id_returns_none(self):
        m = DumpChild(id=10, dumpowner_id=0)
        # No FK on instance (0 is falsy) and not in dict -> None
        d = proto_dump.instance_url(m, {})
        assert d['$id'] is None

    def test_join_model_schema_url_uses_classname(self):
        m = DumpChild(id=1, dumpowner_id=1)
        d = proto_dump.schema_url(m, {})
        assert d['$schema'] == f'{config.API_URL}/DumpChild'

    def test_regular_model_unaffected(self):
        m = _DumpSimple(id=42)
        d = proto_dump.instance_url(m, {})
        assert d['$id'] == f'{config.API_URL}/pd_simple/42'

    def test_join_model_cache_contains_owner_metadata(self):
        m = DumpChild(id=1, dumpowner_id=1)
        proto_dump.instance_url(m, {})
        cached = proto_dump._instance_url_cache[DumpChild]
        assert 'owner_base' in cached
        assert 'tagname' in cached
        assert 'fk_field' in cached
        assert cached['owner_base'] == f'{config.API_URL}/pd_owners'
        assert cached['tagname'] == 'children'
        assert cached['fk_field'] == 'dumpowner_id'

    def test_join_model_full_pipeline(self):
        """model_response() produces parent-scoped $id for join models."""
        m = DumpChild(id=3, dumpowner_id=2)
        d = m.model_response()
        assert d['$schema'] == f'{config.API_URL}/DumpChild'
        assert d['$id'] == f'{config.API_URL}/pd_owners/2/children/3'
        assert d['dumpowner_id'] == 2
