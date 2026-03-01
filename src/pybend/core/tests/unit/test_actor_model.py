"""
Tests for models/actor_model.py — ActorModel bridge class.

MI correctness, model_config merging, actor properties, and instance creation.
"""

import pytest
from typing import ClassVar

from pydantic import BaseModel as PydanticBaseModel, Field

from pybend.core.models.actor_model import ActorModel
from pybend.core.actors.actor import Actor, actormethod, actorproperty
from pybend.core.models.proto_model import ProtoModel
from pybend.core.models.storable_mixin import StorableMixin
from pybend.core import config

pytestmark = pytest.mark.unit


# ===================================================================
# Test helper models
# ===================================================================

class _TestProduct(ActorModel, auto_register=False):
    __tablename__: ClassVar[str] = 'am_products'
    name: str = Field(default='test')
    price: float = Field(default=0.0)


class _TestWidget(ActorModel, auto_register=False):
    __tablename__: ClassVar[str] = 'am_widgets'
    __storable__: ClassVar[bool] = True
    label: str = Field(default='widget')


class _TestPlain(ActorModel, auto_register=False):
    """No __storable__ set — should NOT get StorableMixin."""
    __tablename__: ClassVar[str] = 'am_plain'
    value: int = Field(default=0)


class _TestValidated(ActorModel, auto_register=False):
    __tablename__: ClassVar[str] = 'am_validated'
    title: str = Field(min_length=2, max_length=50, default='ok')


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture(autouse=True)
def reset_actor_state():
    """Save and restore Actor class-level state between tests."""
    saved_matrix = Actor.__matrix__
    saved_children = Actor.__children__.copy()

    yield

    Actor.__matrix__ = saved_matrix
    Actor.__children__ = saved_children


@pytest.fixture(autouse=True)
def clear_schema_cache():
    """Ensure schema cache does not leak between tests."""
    ProtoModel._schema_cache.clear()
    yield
    ProtoModel._schema_cache.clear()


# ===================================================================
# TestMRO
# ===================================================================

class TestMRO:
    """MRO includes ActorModel, Actor, ProtoModel, BaseModel in correct order.
    Subclass is instance of all four."""

    def test_mro_contains_actor_model(self):
        assert ActorModel in _TestProduct.__mro__

    def test_mro_contains_actor(self):
        assert Actor in _TestProduct.__mro__

    def test_mro_contains_proto_model(self):
        assert ProtoModel in _TestProduct.__mro__

    def test_mro_contains_pydantic_base_model(self):
        assert PydanticBaseModel in _TestProduct.__mro__

    def test_mro_order_actor_model_before_actor(self):
        mro = _TestProduct.__mro__
        assert mro.index(ActorModel) < mro.index(Actor)

    def test_mro_order_actor_before_proto_model(self):
        mro = _TestProduct.__mro__
        assert mro.index(Actor) < mro.index(ProtoModel)

    def test_mro_order_proto_model_before_base_model(self):
        mro = _TestProduct.__mro__
        assert mro.index(ProtoModel) < mro.index(PydanticBaseModel)

    def test_isinstance_actor_model(self):
        p = _TestProduct()
        assert isinstance(p, ActorModel)

    def test_isinstance_actor(self):
        p = _TestProduct()
        assert isinstance(p, Actor)

    def test_isinstance_proto_model(self):
        p = _TestProduct()
        assert isinstance(p, ProtoModel)

    def test_isinstance_pydantic_base_model(self):
        p = _TestProduct()
        assert isinstance(p, PydanticBaseModel)

    def test_subclass_of_all_four(self):
        assert issubclass(_TestProduct, ActorModel)
        assert issubclass(_TestProduct, Actor)
        assert issubclass(_TestProduct, ProtoModel)
        assert issubclass(_TestProduct, PydanticBaseModel)


# ===================================================================
# TestModelConfig
# ===================================================================

class TestModelConfig:
    """model_config has ignored_types with actormethod and actorproperty,
    arbitrary_types_allowed is True, extra is 'allow'."""

    def test_ignored_types_includes_actormethod(self):
        ignored = _TestProduct.model_config.get('ignored_types', ())
        assert actormethod in ignored

    def test_ignored_types_includes_actorproperty(self):
        ignored = _TestProduct.model_config.get('ignored_types', ())
        assert actorproperty in ignored

    def test_arbitrary_types_allowed(self):
        assert _TestProduct.model_config.get('arbitrary_types_allowed') is True

    def test_extra_is_allow(self):
        assert _TestProduct.model_config.get('extra') == 'allow'


# ===================================================================
# TestActorProperties
# ===================================================================

class TestActorProperties:
    """Class-level addr reads from __tablename__, class-level children is a dict,
    class-level parent returns Matrix or None. Instance addr defaults to __tablename__
    (from Actor.__init__), instance children is empty dict, instance parent defaults
    to class."""

    def test_class_addr_reads_from_tablename(self):
        assert _TestProduct.addr == 'am_products'

    def test_class_children_is_dict(self):
        assert isinstance(_TestProduct.children, dict)

    def test_class_parent_returns_matrix_or_none(self):
        # parent at class level is Actor.__matrix__
        parent = _TestProduct.parent
        assert parent is None or hasattr(parent, 'inbox')

    def test_instance_addr_defaults_to_tablename(self):
        p = _TestProduct()
        assert p.addr == 'am_products'

    def test_instance_children_is_empty_dict(self):
        p = _TestProduct()
        assert p.children == {}
        assert isinstance(p.children, dict)

    def test_instance_parent_defaults_to_class(self):
        p = _TestProduct()
        assert p.parent is _TestProduct

    def test_instance_addr_custom_kwarg(self):
        p = _TestProduct(addr='custom/1')
        assert p.addr == 'custom/1'

    def test_class_addr_for_widget(self):
        assert _TestWidget.addr == 'am_widgets'


# ===================================================================
# TestProtoModelProperties
# ===================================================================

class TestProtoModelProperties:
    """schema() works (returns dict with 'properties'), model_dump() returns plain data
    (no $schema), model_response() returns enriched data with $schema/$id, id field exists
    with default 0, Field validators work (e.g. min_length)."""

    def test_schema_returns_dict(self):
        schema = _TestProduct.schema()
        assert isinstance(schema, dict)

    def test_schema_has_properties(self):
        schema = _TestProduct.schema()
        assert 'properties' in schema
        assert 'name' in schema['properties']
        assert 'price' in schema['properties']

    def test_model_dump_returns_plain_data(self):
        p = _TestProduct(name='widget', price=9.99)
        data = p.model_dump()
        assert '$schema' not in data
        assert '$id' not in data
        assert data['name'] == 'widget'
        assert data['price'] == 9.99

    def test_model_response_returns_enriched_data(self):
        p = _TestProduct(id=5, name='widget', price=9.99)
        data = p.model_response()
        assert '$schema' in data
        assert '$id' in data
        assert data['$schema'] == f'{config.API_URL}/_TestProduct'
        assert data['$id'] == f'{config.API_URL}/am_products/5'

    def test_id_field_exists_with_default_zero(self):
        p = _TestProduct()
        assert hasattr(p, 'id')
        assert p.id == 0

    def test_id_field_in_model_fields(self):
        assert 'id' in _TestProduct.model_fields

    def test_field_validator_min_length(self):
        with pytest.raises(Exception):
            # min_length=2, so single char should fail
            _TestValidated(title='x')

    def test_field_validator_max_length(self):
        with pytest.raises(Exception):
            # max_length=50, so 51 chars should fail
            _TestValidated(title='a' * 51)

    def test_field_validator_valid_value(self):
        v = _TestValidated(title='hello')
        assert v.title == 'hello'

    def test_schema_has_metadata(self):
        schema = _TestProduct.schema()
        assert '$schema' in schema
        assert '$id' in schema


# ===================================================================
# TestStorableMixinInjection
# ===================================================================

class TestStorableMixinInjection:
    """__storable__=True models get StorableMixin injected,
    __storable__ not set means no StorableMixin."""

    def test_storable_true_injects_mixin(self):
        assert issubclass(_TestWidget, StorableMixin)

    def test_storable_not_set_no_mixin(self):
        assert not issubclass(_TestPlain, StorableMixin)

    def test_storable_not_set_on_test_product(self):
        # _TestProduct has no __storable__ set
        assert not issubclass(_TestProduct, StorableMixin)

    def test_storable_widget_has_crud_methods(self):
        """StorableMixin provides create, get, list, update, delete class methods."""
        assert hasattr(_TestWidget, 'create')
        assert hasattr(_TestWidget, 'get')
        assert hasattr(_TestWidget, 'list')
        assert hasattr(_TestWidget, 'update')
        assert hasattr(_TestWidget, 'delete')

    def test_non_storable_lacks_storage_class_method(self):
        """Non-storable models lack StorableMixin's set_storage method."""
        assert not hasattr(_TestPlain, 'set_storage')


# ===================================================================
# TestInstanceCreation
# ===================================================================

class TestInstanceCreation:
    """Create instance with kwargs, addr on instance defaults to class __tablename__,
    extra kwargs allowed (extra='allow' in config)."""

    def test_create_with_kwargs(self):
        p = _TestProduct(name='gadget', price=19.99)
        assert p.name == 'gadget'
        assert p.price == 19.99

    def test_create_with_defaults(self):
        p = _TestProduct()
        assert p.name == 'test'
        assert p.price == 0.0

    def test_addr_defaults_to_tablename(self):
        p = _TestProduct()
        assert p.addr == 'am_products'

    def test_extra_kwargs_allowed(self):
        """extra='allow' in model_config permits additional fields."""
        p = _TestProduct(name='thing', price=5.0, custom_field='extra_value')
        assert p.custom_field == 'extra_value'

    def test_id_defaults_to_zero(self):
        p = _TestProduct()
        assert p.id == 0

    def test_id_can_be_set(self):
        p = _TestProduct(id=42, name='test')
        assert p.id == 42

    def test_multiple_instances_independent(self):
        p1 = _TestProduct(name='a', price=1.0)
        p2 = _TestProduct(name='b', price=2.0)
        assert p1.name == 'a'
        assert p2.name == 'b'
        assert p1.children is not p2.children
