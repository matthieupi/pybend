"""Tests for ViewableMixin injection and schema output (n3tx-ui)."""

import pytest

import n3tx_ui  # side-effect: registers ViewableMixin via register_mixin()
from n3tx_core.models.proto_model import ProtoModel
from n3tx_ui.mixin import ViewableMixin
from n3tx_core.utils.decorators import expose_route
from pydantic import Field
from typing import ClassVar


# ===================================================================
# Injection
# ===================================================================

class TestInjection:

    def test_explicit_flag_injects_mixin(self):
        class Flagged(ProtoModel):
            __tablename__: ClassVar[str] = 'ui_flagged'
            __viewable__ = True
        assert issubclass(Flagged, ViewableMixin)

    def test_ui_dict_guardrail_injects_mixin(self):
        class WithUI(ProtoModel):
            __tablename__: ClassVar[str] = 'ui_withui'
            __ui__ = {'field_order': ['name']}
        assert issubclass(WithUI, ViewableMixin)
        assert WithUI.__viewable__ is True

    def test_plain_model_no_mixin(self):
        class Plain(ProtoModel):
            __tablename__: ClassVar[str] = 'ui_plain'
        assert not issubclass(Plain, ViewableMixin)

    def test_false_flag_no_injection(self):
        class NotViewable(ProtoModel):
            __tablename__: ClassVar[str] = 'ui_not_viewable'
            __viewable__ = False
        assert not issubclass(NotViewable, ViewableMixin)


# ===================================================================
# Schema output
# ===================================================================

class TestSchemaOutput:

    def test_ui_config_in_schema(self):
        class Viewable(ProtoModel):
            __tablename__: ClassVar[str] = 'ui_vschema'
            __ui__ = {'field_order': ['name']}
            name: str = Field(default='')

        Viewable.invalidate_schema_cache()
        s = Viewable.schema()
        assert 'ui' in s
        assert s['ui']['field_order'] == ['name']

    def test_ui_groups_in_schema(self):
        class Grouped(ProtoModel):
            __tablename__: ClassVar[str] = 'ui_grouped'
            __ui__ = {
                'field_order': ['name', 'value'],
                'groups': {'main': ['name', 'value']},
            }
            name: str = Field(default='')
            value: int = Field(default=0)

        Grouped.invalidate_schema_cache()
        s = Grouped.schema()
        assert s['ui']['groups'] == {'main': ['name', 'value']}

    def test_model_icon_in_schema(self):
        class WithIcon(ProtoModel):
            __tablename__: ClassVar[str] = 'ui_with_icon'
            __ui__ = {'icon': '📚'}
            name: str = Field(default='')

        WithIcon.invalidate_schema_cache()
        s = WithIcon.schema()
        assert s['ui']['icon'] == '📚'

    def test_model_lookup_icon_in_schema(self):
        class WithLookupIcon(ProtoModel):
            __tablename__: ClassVar[str] = 'ui_with_lookup_icon'
            __ui__ = {'icon': 'books'}
            name: str = Field(default='')

        WithLookupIcon.invalidate_schema_cache()
        s = WithLookupIcon.schema()
        assert s['ui']['icon'] == 'books'

    def test_method_ui_hints(self):
        class WithMethodUI(ProtoModel):
            __tablename__: ClassVar[str] = 'ui_method_ui'
            __ui__ = {'methods': {'ping': {'icon': 'send'}}}
            name: str = Field(default='')

            @expose_route('/ping', methods=['POST'])
            def ping(self) -> str:
                return 'pong'

        WithMethodUI.invalidate_schema_cache()
        s = WithMethodUI.schema()
        assert s['methods']['ping']['ui'] == {'icon': 'send'}

    def test_method_emoji_icon_hints(self):
        class WithMethodEmoji(ProtoModel):
            __tablename__: ClassVar[str] = 'ui_method_emoji'
            __ui__ = {'methods': {'ping': {'icon': '🔎'}}}
            name: str = Field(default='')

            @expose_route('/ping', methods=['POST'])
            def ping(self) -> str:
                return 'pong'

        WithMethodEmoji.invalidate_schema_cache()
        s = WithMethodEmoji.schema()
        assert s['methods']['ping']['ui']['icon'] == '🔎'

    def test_method_lookup_icon_hints(self):
        class WithMethodLookup(ProtoModel):
            __tablename__: ClassVar[str] = 'ui_method_lookup'
            __ui__ = {'methods': {'ping': {'icon': 'analyze'}}}
            name: str = Field(default='')

            @expose_route('/ping', methods=['POST'])
            def ping(self) -> str:
                return 'pong'

        WithMethodLookup.invalidate_schema_cache()
        s = WithMethodLookup.schema()
        assert s['methods']['ping']['ui']['icon'] == 'analyze'

    def test_viewable_flag_no_ui_config(self):
        class ViewableNoConfig(ProtoModel):
            __tablename__: ClassVar[str] = 'ui_vno_config'
            __viewable__ = True
            # no __ui__

        ViewableNoConfig.invalidate_schema_cache()
        s = ViewableNoConfig.schema()
        assert 'ui' not in s  # viewable but no config → no ui key

    def test_plain_model_no_ui_key(self):
        class PlainModel(ProtoModel):
            __tablename__: ClassVar[str] = 'ui_plain2'
            name: str = Field(default='')

        PlainModel.invalidate_schema_cache()
        s = PlainModel.schema()
        assert 'ui' not in s
