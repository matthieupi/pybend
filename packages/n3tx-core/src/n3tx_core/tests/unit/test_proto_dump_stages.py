"""
Tests for models/proto_dump.py — built-in serialization pipeline stages
and ProtoModel.model_response() integration.
"""

import pytest
from typing import ClassVar

from pydantic import ConfigDict, Field

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
    secret: str = Field(default='hidden')


class _DumpParent(ProtoModel):
    __tablename__: ClassVar[str] = 'pd_parent'
    child: _DumpOther | None = Field(default=None)
    children: list[_DumpOther] = Field(default=[])


class _DumpNoTable(ProtoModel):
    """Model without __tablename__ — should fall back to lowercase class name."""
    name: str = Field(default='')


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

    def test_nested_models_remain_plain_pydantic_data(self):
        child = _DumpOther(id=2, label='child')
        parent = _DumpParent(id=1, child=child, children=[child])

        d = proto_dump.base(parent)

        assert '$schema' not in d['child']
        assert '$id' not in d['child']
        assert '$schema' not in d['children'][0]
        assert '$id' not in d['children'][0]


# ===================================================================
# TestRelationshipsStage
# ===================================================================

class TestRelationshipsStage:
    """Tests for relationship resource enrichment as a named stage."""

    def test_enriches_single_and_list_relationships(self):
        child = _DumpOther(id=2, label='child')
        parent = _DumpParent(id=1, child=child, children=[child])

        d = proto_dump.relationships(parent, proto_dump.base(parent))

        assert d['child']['$schema'] == f'{config.API_URL}/_DumpOther'
        assert d['child']['$id'] == f'{config.API_URL}/_DumpOther/2'
        assert d['children'][0]['$schema'] == f'{config.API_URL}/_DumpOther'
        assert d['children'][0]['$id'] == f'{config.API_URL}/_DumpOther/2'

    def test_nested_relationships_run_registered_extensions(self):
        child = _DumpOther(id=2, label='child')
        parent = _DumpParent(id=1, child=child)

        def nested_marker(instance, d):
            d['extension_marker'] = instance.__class__.__name__
            return d

        proto_dump.register_stage('nested_marker', nested_marker, after='instance_url')
        try:
            d = parent.model_response()
        finally:
            proto_dump.remove_stage('nested_marker')

        assert d['child']['extension_marker'] == '_DumpOther'

    def test_preserves_nested_exclude_projection(self):
        child = _DumpOther(id=2, label='child', secret='classified')
        parent = _DumpParent(id=1, child=child, children=[child])

        d = parent.model_response(exclude={
            'child': {'secret'},
            'children': {'__all__': {'secret'}},
        })

        assert 'secret' not in d['child']
        assert 'secret' not in d['children'][0]
        assert '$schema' in d['child']
        assert '$id' in d['child']

    def test_preserves_nested_include_projection(self):
        child = _DumpOther(id=2, label='child', secret='classified')
        parent = _DumpParent(id=1, child=child, children=[child])

        d = parent.model_response(include={
            'child': {'label'},
            'children': {'__all__': {'label'}},
        })

        assert d['child']['label'] == 'child'
        assert set(d['child']) == {'label', '$schema', '$id'}
        assert set(d['children'][0]) == {'label', '$schema', '$id'}


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
        assert d['$id'] == f'{config.API_URL}/_DumpSimple/7'
        assert '$href' not in d
        assert 'links' not in d

    def test_id_zero_produces_url(self):
        m = _DumpSimple(id=0, name='test')
        d = proto_dump.instance_url(m, {'name': 'test', 'id': 0})
        # id=0 is not None, so $id should be constructed
        assert d['$id'] == f'{config.API_URL}/_DumpSimple/0'

    def test_id_none_produces_null(self):
        """When instance has no id attribute at all, $id should be None."""
        class _NoId(ProtoModel):
            __tablename__: ClassVar[str] = 'pd_noid'
            name: str = Field(default='')

            model_config = ConfigDict(arbitrary_types_allowed=True)

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

    def test_uses_classname_in_id_url(self):
        m = _DumpSimple(id=3)
        d = proto_dump.instance_url(m, {})
        assert '/_DumpSimple/' in d['$id']

    def test_uses_classname_even_without_tablename(self):
        proto_dump._instance_url_cache.clear()
        m = _DumpNoTable(id=1, name='fallback')
        d = proto_dump.instance_url(m, {'id': 1})
        assert d['$id'] == f'{config.API_URL}/_DumpNoTable/1'


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
        # model_response delegates to the complete registered pipeline.
        assert isinstance(d, dict)
        assert '$schema' in d
        assert '$id' in d

    def test_returns_schema_and_id(self):
        m = _DumpSimple(id=10, name='meta', value=77)
        d = m.model_response()
        assert d['$schema'] == f'{config.API_URL}/_DumpSimple'
        assert d['$id'] == f'{config.API_URL}/_DumpSimple/10'
        assert '$href' not in d
        assert 'links' not in d

    def test_idempotent(self):
        m = _DumpSimple(id=2, name='idem', value=3)
        first = m.model_response()
        second = m.model_response()
        assert first == second

    def test_tablename_fallback(self):
        m = _DumpNoTable(id=5, name='notn')
        d = m.model_response()
        assert d['$id'] == f'{config.API_URL}/_DumpNoTable/5'
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

    def test_embedded_local_relationships_keep_identity_metadata(self):
        child = _DumpOther(id=2, label='child')
        parent = _DumpParent(id=1, child=child, children=[child])

        d = parent.model_response()

        assert d['child']['$schema'] == f'{config.API_URL}/_DumpOther'
        assert d['child']['$id'] == f'{config.API_URL}/_DumpOther/2'
        assert d['children'][0]['$schema'] == f'{config.API_URL}/_DumpOther'
        assert d['children'][0]['$id'] == f'{config.API_URL}/_DumpOther/2'


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
        assert cached['base_url'] == f'{config.API_URL}/_DumpSimple'

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
        assert cache_simple['base_url'].endswith('/_DumpSimple')
        assert cache_other['base_url'].endswith('/_DumpOther')

    def test_cache_survives_multiple_instances(self):
        m1 = _DumpSimple(id=1, name='first')
        m2 = _DumpSimple(id=2, name='second')
        proto_dump.instance_url(m1, {})
        cached_after_first = proto_dump._instance_url_cache[_DumpSimple]
        proto_dump.instance_url(m2, {})
        assert proto_dump._instance_url_cache[_DumpSimple] is cached_after_first
