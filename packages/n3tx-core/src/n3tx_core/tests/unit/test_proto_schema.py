"""
Tests for models/proto_schema.py — composable schema pipeline stages.

Each stage is tested independently as a pure dict → dict function,
then the full pipeline is verified against ProtoModel.schema() output
to guarantee zero regression from the monolith decomposition.
"""

import pytest
from typing import ClassVar, Optional

from pydantic import Field

from n3tx_core import config
from n3tx_core.models.proto_model import ProtoModel
from n3tx_core.utils.typer import Ref
from n3tx_core.utils.decorators import expose_route
from n3tx_core.authorize.rules import ANYONE, AUTHENTICATED, OWNER, ROLE
import n3tx_core.models.proto_schema as proto_schema

pytestmark = pytest.mark.unit


# ===================================================================
# Helpers — test models defined once, reused across test classes
# ===================================================================

class _Simple(ProtoModel):
    __tablename__: ClassVar[str] = 'ps_simple'
    name: str = Field(default='')
    value: int = Field(default=0)


class _WithHidden(ProtoModel):
    __tablename__: ClassVar[str] = 'ps_hidden'
    __hidden_fields__: ClassVar[set] = {'secret'}
    name: str = Field(default='')
    secret: str = Field(default='shhh')


class _WithMethod(ProtoModel):
    __tablename__: ClassVar[str] = 'ps_method'
    name: str = Field(default='')

    @expose_route('/act', methods=['POST'])
    def act(self, text: str) -> str:
        return text


class _Child(ProtoModel):
    __tablename__: ClassVar[str] = 'ps_children'
    text: str = Field(default='')


class _WithRef(ProtoModel):
    __tablename__: ClassVar[str] = 'ps_withref'
    name: str = Field(default='')
    child: Optional[Ref[_Child]] = Field(default=None)


class _WithSelfRef(ProtoModel):
    __tablename__: ClassVar[str] = 'ps_selfref'
    name: str = Field(default='')
    parent_id: Optional[Ref['self']] = Field(default=None)


class _WithAccess(ProtoModel):
    __tablename__: ClassVar[str] = 'ps_access'
    __access__: ClassVar[dict] = {
        'read': ANYONE,
        'create': AUTHENTICATED,
        'update': OWNER | ROLE('admin'),
    }
    name: str = Field(default='')


class _WithProtected(ProtoModel):
    __tablename__: ClassVar[str] = 'ps_protected'
    __protected_fields__: ClassVar[set] = {'owner'}
    name: str = Field(default='')
    owner: int = Field(default=0)


# ===================================================================
# base()
# ===================================================================

class TestBase:

    def test_returns_dict_with_properties(self):
        s = proto_schema.base(_Simple)
        assert isinstance(s, dict)
        assert 'properties' in s
        assert 'name' in s['properties']
        assert 'value' in s['properties']

    def test_includes_id_and_image(self):
        s = proto_schema.base(_Simple)
        assert 'id' in s['properties']
        assert 'image' in s['properties']

    def test_selfref_patched(self):
        s = proto_schema.base(_WithSelfRef)
        assert s['properties']['parent_id'] == {'type': 'selfref'}

    def test_no_selfref_unaffected(self):
        s = proto_schema.base(_Simple)
        # name should be a normal schema, not selfref
        assert s['properties']['name'].get('type') != 'selfref'

    def test_has_pydantic_schema(self):
        s = proto_schema.base(_Simple)
        # Pydantic's __get_pydantic_json_schema__ injects $schema/$id,
        # but metadata() overwrites them with the canonical URLs.
        assert 'properties' in s


# ===================================================================
# strip_hidden()
# ===================================================================

class TestStripHidden:

    def test_removes_hidden_from_properties(self):
        s = proto_schema.base(_WithHidden)
        s = proto_schema.strip_hidden(_WithHidden, s)
        assert 'secret' not in s['properties']
        assert 'name' in s['properties']

    def test_removes_hidden_from_required(self):
        s = {'properties': {'a': {}, 'b': {}}, 'required': ['a', 'b']}

        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'ps_sh_req'
            __hidden_fields__: ClassVar[set] = {'a'}
            a: str = Field(default='')
            b: str = Field(default='')

        s = proto_schema.base(M)
        s = proto_schema.strip_hidden(M, s)
        assert 'a' not in s.get('required', [])

    def test_no_hidden_noop(self):
        s = proto_schema.base(_Simple)
        original_keys = set(s['properties'].keys())
        s = proto_schema.strip_hidden(_Simple, s)
        assert set(s['properties'].keys()) == original_keys

    def test_returns_same_dict(self):
        s = proto_schema.base(_Simple)
        result = proto_schema.strip_hidden(_Simple, s)
        assert result is s


# ===================================================================
# methods()
# ===================================================================

class TestMethods:

    def test_injects_methods_key(self):
        s = proto_schema.base(_Simple)
        s = proto_schema.methods(_Simple, s)
        assert 'methods' in s

    def test_empty_when_no_exposed(self):
        s = proto_schema.base(_Simple)
        s = proto_schema.methods(_Simple, s)
        assert s['methods'] == {}

    def test_exposed_method_present(self):
        s = proto_schema.base(_WithMethod)
        s = proto_schema.methods(_WithMethod, s)
        assert 'act' in s['methods']
        assert s['methods']['act']['route'] == '/act'
        assert 'text' in s['methods']['act']['parameters']

    def test_returns_same_dict(self):
        s = proto_schema.base(_Simple)
        result = proto_schema.methods(_Simple, s)
        assert result is s


# ===================================================================
# defs()
# ===================================================================

class TestDefs:

    def test_no_external_refs(self):
        """For a model with no external relationship fields, defs() only adds
        the model itself (collect_all_referenced_models includes cls)."""
        s = proto_schema.base(_Simple)
        result = proto_schema.defs(_Simple, s)
        # No external references — only _Simple itself in the set
        external_defs = {k for k in result.get('$defs', {}).keys()
                         if k != '_Simple'}
        assert external_defs == set()

    def test_adds_defs_for_referenced_model(self):
        s = proto_schema.base(_WithRef)
        s = proto_schema.defs(_WithRef, s)
        assert '$defs' in s
        assert '_Child' in s['$defs']

    def test_defs_have_id(self):
        s = proto_schema.base(_WithRef)
        s = proto_schema.defs(_WithRef, s)
        assert s['$defs']['_Child']['$id'] == f'{config.API_URL}/_Child'

    def test_defs_have_methods(self):
        s = proto_schema.base(_WithRef)
        s = proto_schema.defs(_WithRef, s)
        assert 'methods' in s['$defs']['_Child']

    def test_returns_same_dict(self):
        s = proto_schema.base(_WithRef)
        result = proto_schema.defs(_WithRef, s)
        assert result is s


# ===================================================================
# access()
# ===================================================================

class TestAccess:

    def test_adds_access_key(self):
        s = proto_schema.base(_WithAccess)
        s = proto_schema.access(_WithAccess, s)
        assert 'access' in s

    def test_access_rules_serialized(self):
        s = proto_schema.base(_WithAccess)
        s = proto_schema.access(_WithAccess, s)
        assert s['access']['read'] == {'rule': 'anyone'}
        assert s['access']['create'] == {'rule': 'authenticated'}

    def test_no_access_gets_defaults(self):
        s = proto_schema.base(_Simple)
        s = proto_schema.access(_Simple, s)
        assert 'access' in s
        assert '*' in s['access']

    def test_access_on_defs(self):
        s = proto_schema.base(_WithRef)
        s = proto_schema.defs(_WithRef, s)
        s = proto_schema.access(_WithRef, s)
        if '_Child' in s.get('$defs', {}):
            assert 'access' in s['$defs']['_Child']

    def test_returns_same_dict(self):
        s = proto_schema.base(_Simple)
        result = proto_schema.access(_Simple, s)
        assert result is s


# ===================================================================
# ui()
# ===================================================================

class TestUI:

    def test_auto_hides_id(self):
        s = proto_schema.base(_Simple)
        s = proto_schema.ui(_Simple, s)
        assert s['properties']['id']['ui']['display'] is False

    def test_auto_hides_image(self):
        s = proto_schema.base(_Simple)
        s = proto_schema.ui(_Simple, s)
        assert s['properties']['image']['ui']['display'] is False

    def test_auto_hides_fk_fields(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'ps_ui_fk'
            parent_id: int = Field(default=0)

        s = proto_schema.base(M)
        s = proto_schema.ui(M, s)
        assert s['properties']['parent_id']['ui']['display'] is False

    def test_regular_field_not_hidden(self):
        s = proto_schema.base(_Simple)
        s = proto_schema.ui(_Simple, s)
        assert 'ui' not in s['properties']['name']

    def test_protected_fields_marked(self):
        s = proto_schema.base(_WithProtected)
        s = proto_schema.ui(_WithProtected, s)
        assert s['properties']['owner']['ui']['protected'] is True

    def test_defs_field_exclusion(self):
        s = proto_schema.base(_WithRef)
        s = proto_schema.defs(_WithRef, s)
        s = proto_schema.ui(_WithRef, s)
        if '_Child' in s.get('$defs', {}):
            child_props = s['$defs']['_Child'].get('properties', {})
            if 'id' in child_props:
                assert child_props['id']['ui']['display'] is False

    def test_no_ui_config_noop(self):
        s = proto_schema.base(_Simple)
        s = proto_schema.ui(_Simple, s)
        assert 'ui' not in s

    def test_returns_same_dict(self):
        s = proto_schema.base(_Simple)
        result = proto_schema.ui(_Simple, s)
        assert result is s


# ===================================================================
# metadata()
# ===================================================================

class TestMetadata:

    def test_adds_schema_url(self):
        s = proto_schema.base(_Simple)
        s = proto_schema.metadata(_Simple, s)
        assert s['$schema'] == f'{config.API_URL}/Schema'

    def test_adds_id_url(self):
        s = proto_schema.base(_Simple)
        s = proto_schema.metadata(_Simple, s)
        assert s['$id'] == f'{config.API_URL}/_Simple'

    def test_returns_same_dict(self):
        s = proto_schema.base(_Simple)
        result = proto_schema.metadata(_Simple, s)
        assert result is s


# ===================================================================
# Pipeline composition — full pipeline matches ProtoModel.schema()
# ===================================================================

class TestPipelineComposition:

    def _run_pipeline(self, cls):
        """Run all stages manually, without caching."""
        s = proto_schema.base(cls)
        s = proto_schema.strip_hidden(cls, s)
        s = proto_schema.methods(cls, s)
        s = proto_schema.defs(cls, s)
        s = proto_schema.access(cls, s)
        s = proto_schema.ui(cls, s)
        s = proto_schema.metadata(cls, s)
        return s

    def test_simple_model_matches_schema(self):
        _Simple.invalidate_schema_cache()
        expected = _Simple.schema()
        result = self._run_pipeline(_Simple)
        assert result == expected

    def test_model_with_methods_matches(self):
        _WithMethod.invalidate_schema_cache()
        expected = _WithMethod.schema()
        result = self._run_pipeline(_WithMethod)
        assert result == expected

    def test_model_with_access_matches(self):
        _WithAccess.invalidate_schema_cache()
        expected = _WithAccess.schema()
        result = self._run_pipeline(_WithAccess)
        assert result == expected

    def test_model_with_hidden_matches(self):
        _WithHidden.invalidate_schema_cache()
        expected = _WithHidden.schema()
        result = self._run_pipeline(_WithHidden)
        assert result == expected

    def test_model_with_selfref_matches(self):
        _WithSelfRef.invalidate_schema_cache()
        expected = _WithSelfRef.schema()
        result = self._run_pipeline(_WithSelfRef)
        assert result == expected

    def test_model_with_protected_matches(self):
        _WithProtected.invalidate_schema_cache()
        expected = _WithProtected.schema()
        result = self._run_pipeline(_WithProtected)
        assert result == expected


# ===================================================================
# Stage independence — each stage is callable on its own
# ===================================================================

class TestStageIndependence:

    def test_base_standalone(self):
        s = proto_schema.base(_Simple)
        assert 'properties' in s

    def test_strip_hidden_on_raw_dict(self):
        """strip_hidden works on any dict with properties."""
        s = {'properties': {'a': {}, 'b': {}}, 'required': ['a', 'b']}

        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'ps_ind1'
            __hidden_fields__: ClassVar[set] = {'a'}

        result = proto_schema.strip_hidden(M, s)
        assert 'a' not in result['properties']

    def test_methods_on_raw_dict(self):
        """methods works on any dict."""
        s = {'properties': {}}
        result = proto_schema.methods(_Simple, s)
        assert 'methods' in result

    def test_metadata_on_raw_dict(self):
        """metadata works on any dict."""
        s = {}
        result = proto_schema.metadata(_Simple, s)
        assert '$schema' in result
        assert '$id' in result

    def test_access_on_raw_dict(self):
        """access works on any dict."""
        s = {}
        result = proto_schema.access(_Simple, s)
        assert 'access' in result

    def test_ui_on_raw_dict(self):
        """ui works on a dict with properties."""
        s = {'properties': {'id': {'type': 'integer'}}}
        result = proto_schema.ui(_Simple, s)
        assert result['properties']['id']['ui']['display'] is False


# ===================================================================
# Stage ordering
# ===================================================================

class TestStageOrdering:

    def test_metadata_must_be_last(self):
        """metadata stamps $schema/$id — running it early then running
        other stages shouldn't corrupt, but the final output should have
        the correct values regardless."""
        s = proto_schema.base(_Simple)
        s = proto_schema.metadata(_Simple, s)
        # Now run other stages after — they should not overwrite $schema/$id
        s = proto_schema.strip_hidden(_Simple, s)
        s = proto_schema.methods(_Simple, s)
        s = proto_schema.access(_Simple, s)
        s = proto_schema.ui(_Simple, s)
        assert s['$schema'] == f'{config.API_URL}/Schema'
        assert s['$id'] == f'{config.API_URL}/_Simple'

    def test_access_before_ui_or_after(self):
        """access and ui are independent — order between them shouldn't matter."""
        s1 = proto_schema.base(_WithAccess)
        s1 = proto_schema.methods(_WithAccess, s1)
        s1 = proto_schema.access(_WithAccess, s1)
        s1 = proto_schema.ui(_WithAccess, s1)

        _WithAccess.invalidate_schema_cache()

        s2 = proto_schema.base(_WithAccess)
        s2 = proto_schema.methods(_WithAccess, s2)
        s2 = proto_schema.ui(_WithAccess, s2)
        s2 = proto_schema.access(_WithAccess, s2)

        assert s1 == s2
