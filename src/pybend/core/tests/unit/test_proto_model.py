"""
Tests for models/proto_model.py — ProtoModel base class.
"""

import pytest
from unittest.mock import MagicMock, patch
from typing import ClassVar, Optional

from pydantic import Field, BaseModel

from pybend.core import config
from pybend.core.models.proto_model import ProtoModel, _apply_field_exclusion, _AUTO_HIDE_FIELDS, generate_join_model
from pybend.core.models.storable_mixin import StorableMixin
from pybend.core.utils.typer import Ref
from pybend.core.models.ref import ListRef

pytestmark = pytest.mark.unit



# ===================================================================
# __init_subclass__
# ===================================================================

class TestInitSubclass:

    def test_storable_true_injects_mixin(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'is_test1'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        assert issubclass(M, StorableMixin)

    def test_storable_false_no_mixin(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'is_test2'
            __storable__: ClassVar[bool] = False
            name: str = Field(default='')
        assert not issubclass(M, StorableMixin)

    def test_no_storable_defaults_false(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'is_test3'
            name: str = Field(default='')
        assert not issubclass(M, StorableMixin)

    def test_double_injection_prevented(self):
        class Parent(ProtoModel):
            __tablename__: ClassVar[str] = 'is_parent'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        class Child(Parent):
            __tablename__: ClassVar[str] = 'is_child'
            __storable__: ClassVar[bool] = True
            extra: str = Field(default='')
        mro_count = sum(1 for cls in Child.__mro__ if cls is StorableMixin)
        assert mro_count == 1

    def test_referenced_models_created(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'is_test4'
            name: str = Field(default='')
        assert hasattr(M, '_referenced_models')
        assert isinstance(M._referenced_models, set)

    def test_empty_model(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'is_test5'
        assert 'id' in M.model_fields
        assert 'image' in M.model_fields


# ===================================================================
# __init__
# ===================================================================

class TestInit:

    def test_normal_init(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'init_t1'
            name: str = Field(default='hello')
            value: int = Field(default=10)
        m = M(name='test', value=42)
        assert m.name == 'test'
        assert m.value == 42

    def test_owner_from_kwargs(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'init_t2'
            name: str = Field(default='')
        m = M(name='test', __owner__='ref')
        assert m.__owner__ == 'ref'

    def test_owner_none_by_default(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'init_t3'
            name: str = Field(default='')
        m = M(name='test')
        assert m.__owner__ is None

    def test_empty_kwargs(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'init_t4'
            name: str = Field(default='default')
        m = M()
        assert m.name == 'default'
        assert m.id == 0

    def test_storable_id_only_triggers_get(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'init_t5'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        M.storage = MagicMock()
        M.storage.get.return_value = {'id': 5, 'name': 'fetched', 'image': ''}
        m = M(id=5)
        assert m.name == 'fetched'


# ===================================================================
# model_dump
# ===================================================================

class TestModelDump:

    def test_plain_no_metadata(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'dump_t1'
            name: str = Field(default='test')
        m = M(id=1, name='hi')
        data = m.model_dump()
        assert '$schema' not in data
        assert '$id' not in data

    def test_response_has_metadata(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'dump_t2'
            name: str = Field(default='test')
        m = M(id=1, name='hi')
        data = m.model_dump(response=True)
        assert data['$schema'] == f'{config.API_URL}/M'
        assert data['$id'] == f'{config.API_URL}/dump_t2/1'

    def test_response_id_zero(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'dump_t3'
            name: str = Field(default='')
        m = M(id=0, name='test')
        data = m.model_dump(response=True)
        assert data['$id'] == f'{config.API_URL}/dump_t3/0'

    def test_idempotent(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'dump_t4'
            name: str = Field(default='')
        m = M(id=1, name='test')
        assert m.model_dump() == m.model_dump()
        assert m.model_dump(response=True) == m.model_dump(response=True)

    def test_tablename_fallback(self):
        class MyModel(ProtoModel):
            name: str = Field(default='')
        m = MyModel(id=1, name='test')
        data = m.model_dump(response=True)
        assert 'mymodel' in data['$id']


# ===================================================================
# __pybend_methods_json_signature__
# ===================================================================

class TestMethodsJsonSignature:

    def test_exposed_method_present(self):
        from utils.decorators import expose_route
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'mj_t1'
            @expose_route('/act', methods=['POST'])
            def act(self, text: str) -> str:
                return text
        methods = M.__pybend_methods_json_signature__()
        assert 'act' in methods
        assert methods['act']['route'] == '/act'
        assert 'text' in methods['act']['parameters']

    def test_non_exposed_skipped(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'mj_t2'
            def helper(self): pass
        methods = M.__pybend_methods_json_signature__()
        assert 'helper' not in methods

    def test_self_and_user_filtered(self):
        from utils.decorators import expose_route
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'mj_t3'
            @expose_route('/do', methods=['POST'])
            def do(self, data: str, user: BaseModel = None) -> str:
                return data
        methods = M.__pybend_methods_json_signature__()
        assert 'self' not in methods['do']['parameters']
        assert 'user' not in methods['do']['parameters']
        assert 'data' in methods['do']['parameters']

    def test_no_params_method(self):
        from utils.decorators import expose_route
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'mj_t4'
            @expose_route('/ping', methods=['POST'])
            def ping(self) -> str:
                return 'pong'
        methods = M.__pybend_methods_json_signature__()
        assert methods['ping']['parameters'] == {}

    def test_access_rule_in_method(self):
        from utils.decorators import expose_route
        from pybend.core.authorize.rules import AUTHENTICATED
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'mj_t5'
            @expose_route('/secure', methods=['POST'], access=AUTHENTICATED)
            def secure(self) -> str:
                return 'ok'
        methods = M.__pybend_methods_json_signature__()
        assert methods['secure']['access'] == {'rule': 'authenticated'}

    def test_multiple_methods(self):
        from utils.decorators import expose_route
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'mj_t6'
            @expose_route('/a', methods=['POST'])
            def a(self) -> str: return 'a'
            @expose_route('/b', methods=['GET'])
            def b(self) -> str: return 'b'
        methods = M.__pybend_methods_json_signature__()
        assert 'a' in methods
        assert 'b' in methods

    def test_return_type(self):
        from utils.decorators import expose_route
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'mj_t7'
            @expose_route('/count', methods=['POST'])
            def count(self) -> int: return 0
        methods = M.__pybend_methods_json_signature__()
        assert methods['count']['returns'] == {'type': 'integer'}


# ===================================================================
# schema()
# ===================================================================

class TestSchema:

    def test_has_metadata(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'sc_t1'
            name: str = Field(default='')
        schema = M.schema()
        assert schema['$schema'] == f'{config.API_URL}/Schema'
        assert schema['$id'] == f'{config.API_URL}/M'

    def test_has_properties(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'sc_t2'
            name: str = Field(default='')
            value: int = Field(default=0)
        schema = M.schema()
        assert 'name' in schema['properties']
        assert 'value' in schema['properties']

    def test_auto_hides_id(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'sc_t3'
            name: str = Field(default='')
        schema = M.schema()
        assert schema['properties']['id']['ui']['display'] is False

    def test_auto_hides_image(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'sc_t4'
            name: str = Field(default='')
        schema = M.schema()
        assert schema['properties']['image']['ui']['display'] is False

    def test_auto_hides_fk_fields(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'sc_t5'
            name: str = Field(default='')
            parent_id: int = Field(default=0)
        schema = M.schema()
        assert schema['properties']['parent_id']['ui']['display'] is False

    def test_methods_section(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'sc_t6'
            name: str = Field(default='')
        schema = M.schema()
        assert 'methods' in schema

    def test_access_section(self):
        from pybend.core.authorize.rules import ANYONE, AUTHENTICATED
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'sc_t7'
            __access__: ClassVar[dict] = {'read': ANYONE, 'create': AUTHENTICATED}
            name: str = Field(default='')
        schema = M.schema()
        assert schema['access']['read'] == {'rule': 'anyone'}
        assert schema['access']['create'] == {'rule': 'authenticated'}

    def test_no_access_defaults(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'sc_t8'
            name: str = Field(default='')
        schema = M.schema()
        assert '*' in schema['access']

    def test_ui_config(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'sc_t9'
            __ui__: ClassVar[dict] = {'field_order': ['name', 'value']}
            name: str = Field(default='')
            value: int = Field(default=0)
        schema = M.schema()
        assert schema['ui']['field_order'] == ['name', 'value']

    def test_protected_fields(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'sc_t10'
            __protected_fields__: ClassVar[set] = {'owner'}
            name: str = Field(default='')
            owner: int = Field(default=0)
        schema = M.schema()
        assert schema['properties']['owner']['ui']['protected'] is True

    def test_hidden_fields_removed(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'sc_t11'
            __hidden_fields__: ClassVar[set] = {'secret'}
            name: str = Field(default='')
            secret: str = Field(default='')
        schema = M.schema()
        assert 'secret' not in schema['properties']

    def test_selfref_field(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'sc_t12'
            name: str = Field(default='')
            parent_id: Optional[Ref['self']] = Field(default=None)
        schema = M.schema()
        assert schema['properties']['parent_id']['type'] == 'selfref'

    def test_empty_methods(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'sc_t13'
            name: str = Field(default='')
        schema = M.schema()
        assert schema['methods'] == {}


# ===================================================================
# referenced_json_schema
# ===================================================================

class TestReferencedJsonSchema:

    def test_basic(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'rjs_t1'
            name: str = Field(default='')
        schema = M.referenced_json_schema()
        assert 'properties' in schema

    def test_selfref(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'rjs_t2'
            name: str = Field(default='')
            parent_id: Optional[Ref['self']] = Field(default=None)
        schema = M.referenced_json_schema()
        assert schema['properties']['parent_id'] == {'type': 'selfref'}


# ===================================================================
# generate_join_model
# ===================================================================

class TestGenerateJoinModel:

    def test_correct_name(self):
        class O(ProtoModel):
            __tablename__: ClassVar[str] = 'gj_owners'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        class C(ProtoModel):
            __tablename__: ClassVar[str] = 'gj_children'
            __storable__: ClassVar[bool] = True
            text: str = Field(default='')
        O.storage = MagicMock()
        jm = generate_join_model(O, C)
        assert jm.__name__ == 'OC'

    def test_tablename(self):
        class O(ProtoModel):
            __tablename__: ClassVar[str] = 'gj_own2'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        class C(ProtoModel):
            __tablename__: ClassVar[str] = 'gj_ch2'
            __storable__: ClassVar[bool] = True
            text: str = Field(default='')
        O.storage = MagicMock()
        jm = generate_join_model(O, C)
        assert jm.__tablename__ == 'gj_own2_gj_ch2'

    def test_owner_and_parent(self):
        class O(ProtoModel):
            __tablename__: ClassVar[str] = 'gj_own3'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        class C(ProtoModel):
            __tablename__: ClassVar[str] = 'gj_ch3'
            __storable__: ClassVar[bool] = True
            text: str = Field(default='')
        O.storage = MagicMock()
        jm = generate_join_model(O, C)
        assert jm.__owner__ is O
        assert jm.__parent__ is C

    def test_fk_field(self):
        class O(ProtoModel):
            __tablename__: ClassVar[str] = 'gj_own4'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        class C(ProtoModel):
            __tablename__: ClassVar[str] = 'gj_ch4'
            __storable__: ClassVar[bool] = True
            text: str = Field(default='')
        O.storage = MagicMock()
        jm = generate_join_model(O, C)
        assert 'o_id' in jm.model_fields

    def test_assert_not_protomodel(self):
        class NotModel:
            pass
        class C(ProtoModel):
            __tablename__: ClassVar[str] = 'gj_ch5'
            text: str = Field(default='')
        with pytest.raises(AssertionError):
            generate_join_model(NotModel, C)

    def test_ref_model_not_protomodel(self):
        """UT-2: ref_model must also be a ProtoModel."""
        class O(ProtoModel):
            __tablename__: ClassVar[str] = 'gj_own5'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        class NotModel:
            pass
        O.storage = MagicMock()
        with pytest.raises(AssertionError):
            generate_join_model(O, NotModel)

    def test_owner_without_storable_raises(self):
        """UT-2: Owner without __storable__ (non-storable) has no storage attr."""
        class O(ProtoModel):
            __tablename__: ClassVar[str] = 'gj_own6'
            # __storable__ NOT set => no StorableMixin => no storage attr
            name: str = Field(default='')
        class C(ProtoModel):
            __tablename__: ClassVar[str] = 'gj_ch6'
            __storable__: ClassVar[bool] = True
            text: str = Field(default='')
        with pytest.raises(AssertionError, match="storage"):
            generate_join_model(O, C)

    def test_join_model_inherits_from_ref(self):
        """UT-2: Join model is a subclass of the ref_model."""
        class O(ProtoModel):
            __tablename__: ClassVar[str] = 'gj_own7'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        class C(ProtoModel):
            __tablename__: ClassVar[str] = 'gj_ch7'
            __storable__: ClassVar[bool] = True
            text: str = Field(default='')
        O.storage = MagicMock()
        jm = generate_join_model(O, C)
        assert issubclass(jm, C)

    def test_join_model_is_storable(self):
        """UT-2: Join model should have __storable__ = True."""
        class O(ProtoModel):
            __tablename__: ClassVar[str] = 'gj_own8'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        class C(ProtoModel):
            __tablename__: ClassVar[str] = 'gj_ch8'
            __storable__: ClassVar[bool] = True
            text: str = Field(default='')
        O.storage = MagicMock()
        jm = generate_join_model(O, C)
        assert jm.__storable__ is True

    def test_join_model_tagname(self):
        """UT-2: __tagname__ should be set to child tablename."""
        class O(ProtoModel):
            __tablename__: ClassVar[str] = 'gj_own9'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        class C(ProtoModel):
            __tablename__: ClassVar[str] = 'gj_ch9'
            __storable__: ClassVar[bool] = True
            text: str = Field(default='')
        O.storage = MagicMock()
        jm = generate_join_model(O, C)
        assert jm.__tagname__ == 'gj_ch9'

    def test_join_model_inherits_methods(self):
        """UT-2: Join model inherits exposed methods from ref_model."""
        from utils.decorators import expose_route
        class O(ProtoModel):
            __tablename__: ClassVar[str] = 'gj_own10'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        class C(ProtoModel):
            __tablename__: ClassVar[str] = 'gj_ch10'
            __storable__: ClassVar[bool] = True
            text: str = Field(default='')
            @expose_route('/custom', methods=['POST'])
            def custom(self) -> str:
                return 'inherited'
        O.storage = MagicMock()
        jm = generate_join_model(O, C)
        assert hasattr(jm, 'custom')
        assert hasattr(jm.custom, '__endpoint__')


# ===================================================================
# _apply_field_exclusion
# ===================================================================

class TestApplyFieldExclusion:

    def test_id_hidden(self):
        schema = {'properties': {'id': {'type': 'integer'}}}
        _apply_field_exclusion(schema)
        assert schema['properties']['id']['ui']['display'] is False

    def test_image_hidden(self):
        schema = {'properties': {'image': {'type': 'string'}}}
        _apply_field_exclusion(schema)
        assert schema['properties']['image']['ui']['display'] is False

    def test_created_at_hidden(self):
        schema = {'properties': {'created_at': {'type': 'string'}}}
        _apply_field_exclusion(schema)
        assert schema['properties']['created_at']['ui']['display'] is False

    def test_fk_hidden(self):
        schema = {'properties': {'parent_id': {'type': 'integer'}}}
        _apply_field_exclusion(schema)
        assert schema['properties']['parent_id']['ui']['display'] is False

    def test_regular_not_hidden(self):
        schema = {'properties': {'name': {'type': 'string'}}}
        _apply_field_exclusion(schema)
        assert 'ui' not in schema['properties']['name']

    def test_existing_display_preserved(self):
        schema = {'properties': {'id': {'type': 'integer', 'ui': {'display': True}}}}
        _apply_field_exclusion(schema)
        assert schema['properties']['id']['ui']['display'] is True

    def test_no_properties(self):
        schema = {'title': 'Test'}
        _apply_field_exclusion(schema)
        assert 'properties' not in schema

    def test_non_dict_field_skipped(self):
        schema = {'properties': {'weird': 'not_a_dict'}}
        _apply_field_exclusion(schema)
        assert schema['properties']['weird'] == 'not_a_dict'

    def test_auto_hide_set(self):
        assert 'id' in _AUTO_HIDE_FIELDS
        assert 'image' in _AUTO_HIDE_FIELDS
        assert 'created_at' in _AUTO_HIDE_FIELDS
        assert 'updated_at' in _AUTO_HIDE_FIELDS
