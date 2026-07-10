"""
Tests for models/proto_model.py — ProtoModel base class.
"""

import pytest
from unittest.mock import MagicMock
from typing import ClassVar, Optional

from pydantic import Field, BaseModel

from n3tx_core import config
from n3tx_core.models.proto_model import ProtoModel, _apply_field_exclusion, _AUTO_HIDE_FIELDS
from n3tx_core.models.storable_mixin import StorableMixin
from n3tx_core.utils.typer import Ref

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
        data = m.model_response()
        assert data['$schema'] == f'{config.API_URL}/M'
        assert data['$id'] == f'{config.API_URL}/M/1'

    def test_response_id_zero(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'dump_t3'
            name: str = Field(default='')
        m = M(id=0, name='test')
        data = m.model_response()
        assert data['$id'] == f'{config.API_URL}/M/0'

    def test_idempotent(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'dump_t4'
            name: str = Field(default='')
        m = M(id=1, name='test')
        assert m.model_dump() == m.model_dump()
        assert m.model_response() == m.model_response()

    def test_tablename_fallback(self):
        class MyModel(ProtoModel):
            name: str = Field(default='')
        m = MyModel(id=1, name='test')
        data = m.model_response()
        assert data['$id'] == f'{config.API_URL}/MyModel/1'


# ===================================================================
# __n3tx_methods_json_signature__
# ===================================================================

class TestMethodsJsonSignature:

    def test_exposed_method_present(self):
        from n3tx_core.utils.decorators import expose_route
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'mj_t1'
            @expose_route('/act', methods=['POST'])
            def act(self, text: str) -> str:
                return text
        methods = M.__n3tx_methods_json_signature__()
        assert 'act' in methods
        assert methods['act']['route'] == '/act'
        assert 'text' in methods['act']['parameters']

    def test_non_exposed_skipped(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'mj_t2'
            def helper(self): pass
        methods = M.__n3tx_methods_json_signature__()
        assert 'helper' not in methods

    def test_self_and_user_filtered(self):
        from n3tx_core.utils.decorators import expose_route
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'mj_t3'
            @expose_route('/do', methods=['POST'])
            def do(self, data: str, user: BaseModel = None) -> str:
                return data
        methods = M.__n3tx_methods_json_signature__()
        assert 'self' not in methods['do']['parameters']
        assert 'user' not in methods['do']['parameters']
        assert 'data' in methods['do']['parameters']

    def test_no_params_method(self):
        from n3tx_core.utils.decorators import expose_route
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'mj_t4'
            @expose_route('/ping', methods=['POST'])
            def ping(self) -> str:
                return 'pong'
        methods = M.__n3tx_methods_json_signature__()
        assert methods['ping']['parameters'] == {}

    def test_access_rule_in_method(self):
        from n3tx_core.utils.decorators import expose_route
        from n3tx_core.authorize.rules import AUTHENTICATED
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'mj_t5'
            @expose_route('/secure', methods=['POST'], access=AUTHENTICATED)
            def secure(self) -> str:
                return 'ok'
        methods = M.__n3tx_methods_json_signature__()
        assert methods['secure']['access'] == {'rule': 'authenticated'}

    def test_multiple_methods(self):
        from n3tx_core.utils.decorators import expose_route
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'mj_t6'
            @expose_route('/a', methods=['POST'])
            def a(self) -> str: return 'a'
            @expose_route('/b', methods=['GET'])
            def b(self) -> str: return 'b'
        methods = M.__n3tx_methods_json_signature__()
        assert 'a' in methods
        assert 'b' in methods

    def test_return_type(self):
        from n3tx_core.utils.decorators import expose_route
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'mj_t7'
            @expose_route('/count', methods=['POST'])
            def count(self) -> int: return 0
        methods = M.__n3tx_methods_json_signature__()
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
        from n3tx_core.authorize.rules import ANYONE, AUTHENTICATED
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
        import n3tx_ui  # registers the __ui__ schema extension before class definition

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
