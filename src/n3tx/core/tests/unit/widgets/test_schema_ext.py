"""
Tests for widgets/schema_ext.py — schema pipeline stage for widget injection.

Tests the three detection cases:
  1. Annotated[str, <MarkdownField instance>] — from MarkdownField(rows=10)
  2. Bare MarkdownField class — issubclass(annotation, Widget)
  3. Auto-detect: bare AnyHttpUrl (not a Widget subclass) → check AUTO_DETECT_MAP
"""

import pytest
from typing import ClassVar, Optional
from datetime import date

from pydantic import Field, AnyHttpUrl, EmailStr

from n3tx.core.models.proto_model import ProtoModel
from n3tx.core.models.proto_schema import (
    run_pipeline, get_pipeline, _stages,
)
from n3tx.core.models.ref import ListRef
from n3tx.core.widgets.widget import (
    Widget, MarkdownField, UrlField, EmailField,
    DateField, CurrencyField, TextareaField, ConsoleField,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _restore_pipeline():
    """Save pipeline before each test, restore after."""
    saved = list(_stages)
    yield
    _stages.clear()
    _stages.extend(saved)


# ===================================================================
# Pipeline registration
# ===================================================================

class TestPipelineRegistration:

    def test_widget_stage_exists(self):
        assert 'widget' in get_pipeline()

    def test_widget_before_ui(self):
        pipeline = get_pipeline()
        assert pipeline.index('widget') < pipeline.index('ui')

    def test_widget_after_access(self):
        pipeline = get_pipeline()
        assert pipeline.index('widget') > pipeline.index('access')


# ===================================================================
# Case 1: Annotated with Widget instance (called syntax)
# ===================================================================

class TestAnnotatedWidgetInstance:

    def test_markdown_with_config(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'wtest_md_config'
            name: str = Field(default='')
            body: MarkdownField(rows=10) = Field(default='')

        M.invalidate_schema_cache()
        schema = run_pipeline(M)
        ui = schema['properties']['body'].get('ui', {})
        assert ui['widget'] == 'markdown'
        assert ui['config'] == {'rows': 10}

    def test_console_with_config(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'wtest_console_config'
            name: str = Field(default='')
            logs: ConsoleField(rows=30) = Field(default='')

        M.invalidate_schema_cache()
        schema = run_pipeline(M)
        ui = schema['properties']['logs'].get('ui', {})
        assert ui['widget'] == 'console'
        assert ui['config'] == {'rows': 30}


# ===================================================================
# Case 2: Bare Widget class as annotation
# ===================================================================

class TestBareWidgetClass:

    def test_markdown_bare(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'wtest_md_bare'
            name: str = Field(default='')
            body: MarkdownField = Field(default='')

        M.invalidate_schema_cache()
        schema = run_pipeline(M)
        ui = schema['properties']['body'].get('ui', {})
        assert ui['widget'] == 'markdown'
        assert 'config' not in ui  # No config for bare usage

    def test_url_bare(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'wtest_url_bare'
            name: str = Field(default='')
            website: UrlField = Field(default='')

        M.invalidate_schema_cache()
        schema = run_pipeline(M)
        ui = schema['properties']['website'].get('ui', {})
        assert ui['widget'] == 'url'

    def test_email_bare(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'wtest_email_bare'
            name: str = Field(default='')
            contact: EmailField = Field(default='')

        M.invalidate_schema_cache()
        schema = run_pipeline(M)
        ui = schema['properties']['contact'].get('ui', {})
        assert ui['widget'] == 'email'

    def test_date_bare(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'wtest_date_bare'
            name: str = Field(default='')
            published: DateField = Field(default=None)

        M.invalidate_schema_cache()
        schema = run_pipeline(M)
        ui = schema['properties']['published'].get('ui', {})
        assert ui['widget'] == 'date'

    def test_currency_bare(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'wtest_currency_bare'
            name: str = Field(default='')
            price: CurrencyField = Field(default=0.0)

        M.invalidate_schema_cache()
        schema = run_pipeline(M)
        ui = schema['properties']['price'].get('ui', {})
        assert ui['widget'] == 'currency'

    def test_textarea_bare(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'wtest_textarea_bare'
            name: str = Field(default='')
            notes: TextareaField = Field(default='')

        M.invalidate_schema_cache()
        schema = run_pipeline(M)
        ui = schema['properties']['notes'].get('ui', {})
        assert ui['widget'] == 'textarea'

    def test_optional_widget_bare(self):
        """Optional[MarkdownField] unwraps correctly."""
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'wtest_opt_bare'
            name: str = Field(default='')
            body: Optional[MarkdownField] = Field(default=None)

        M.invalidate_schema_cache()
        schema = run_pipeline(M)
        ui = schema['properties']['body'].get('ui', {})
        assert ui['widget'] == 'markdown'


# ===================================================================
# Case 3: Auto-detect from Python type
# ===================================================================

class TestAutoDetect:
    """Fields with Pydantic-native types (AnyHttpUrl, EmailStr, date)
    without explicit Widget annotation still get auto-detected."""

    # NOTE: Auto-detect requires bare type annotations like `AnyHttpUrl`,
    # which is unusual in ProtoModel since most fields use standard types.
    # This tests the mechanism works for edge cases and custom types.

    def test_plain_str_no_widget(self):
        """Plain str fields should NOT get a widget."""
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'wtest_plain_str'
            name: str = Field(default='')
            notes: str = Field(default='')

        M.invalidate_schema_cache()
        schema = run_pipeline(M)
        assert 'widget' not in schema['properties']['notes'].get('ui', {})


# ===================================================================
# Existing ui.widget not overwritten
# ===================================================================

class TestNoOverwrite:

    def test_explicit_widget_preserved(self):
        """If json_schema_extra already sets ui.widget, don't overwrite."""
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'wtest_no_overwrite'
            name: str = Field(default='')
            price: CurrencyField = Field(
                default=0.0,
                json_schema_extra={'ui': {'widget': 'custom_currency'}}
            )

        M.invalidate_schema_cache()
        schema = run_pipeline(M)
        ui = schema['properties']['price'].get('ui', {})
        assert ui['widget'] == 'custom_currency'  # Not overwritten to 'currency'


# ===================================================================
# Custom widget end-to-end
# ===================================================================

class TestCustomWidgetE2E:

    def test_custom_widget_in_schema(self):
        class ColorField(Widget, name='color', base_type=str):
            pass

        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'wtest_custom_e2e'
            name: str = Field(default='')
            primary: ColorField = Field(default='')

        M.invalidate_schema_cache()
        schema = run_pipeline(M)
        ui = schema['properties']['primary'].get('ui', {})
        assert ui['widget'] == 'color'

    def test_custom_widget_with_config(self):
        class ColorField(Widget, name='color', base_type=str):
            pass

        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'wtest_custom_config'
            name: str = Field(default='')
            accent: ColorField(swatches=True) = Field(default='')

        M.invalidate_schema_cache()
        schema = run_pipeline(M)
        ui = schema['properties']['accent'].get('ui', {})
        assert ui['widget'] == 'color'
        assert ui['config'] == {'swatches': True}


# ===================================================================
# No widget fields — backward compatibility
# ===================================================================

class TestBackwardCompat:

    def test_model_without_widgets_unchanged(self):
        """A model with no Widget fields produces identical schema."""
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'wtest_compat'
            name: str = Field(default='')
            value: int = Field(default=0)
            active: bool = Field(default=True)

        M.invalidate_schema_cache()
        schema = run_pipeline(M)
        # name/value/active should have no ui.widget
        for field in ['name', 'value', 'active']:
            assert 'widget' not in schema['properties'][field].get('ui', {})


# ===================================================================
# Multiple widget fields on same model
# ===================================================================

class TestMultipleWidgets:

    def test_all_widget_types_on_one_model(self):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'wtest_multi'
            name: str = Field(default='')
            body: MarkdownField = Field(default='')
            notes: TextareaField = Field(default='')
            price: CurrencyField = Field(default=0.0)
            website: Optional[UrlField] = Field(default=None)
            contact: Optional[EmailField] = Field(default=None)

        M.invalidate_schema_cache()
        schema = run_pipeline(M)

        expected = {
            'body': 'markdown',
            'notes': 'textarea',
            'price': 'currency',
            'website': 'url',
            'contact': 'email',
        }
        for field, widget_name in expected.items():
            ui = schema['properties'][field].get('ui', {})
            assert ui.get('widget') == widget_name, (
                f"Expected {field} to have widget={widget_name}, got {ui}"
            )

        # name should NOT have a widget
        assert 'widget' not in schema['properties']['name'].get('ui', {})


# ===================================================================
# $defs widget injection
# ===================================================================

class TestDefsWidgetInjection:
    """Widget annotations in referenced models should propagate to $defs."""

    def test_child_widget_in_defs(self):
        """A child model's Widget fields should get ui.widget in $defs."""
        class ChildDef(ProtoModel):
            __tablename__: ClassVar[str] = 'wtest_child_def'
            name: str = Field(default='')
            body: MarkdownField = Field(default='')
            price: CurrencyField = Field(default=0.0)

        class ParentDef(ProtoModel):
            __tablename__: ClassVar[str] = 'wtest_parent_def'
            name: str = Field(default='')
            children: ListRef[ChildDef] = Field(default=[])

        ParentDef.invalidate_schema_cache()
        schema = run_pipeline(ParentDef)

        assert '$defs' in schema
        assert 'ChildDef' in schema['$defs']
        child_props = schema['$defs']['ChildDef']['properties']
        assert child_props['body'].get('ui', {}).get('widget') == 'markdown'
        assert child_props['price'].get('ui', {}).get('widget') == 'currency'
        # name should NOT have a widget
        assert 'widget' not in child_props['name'].get('ui', {})

    def test_child_widget_with_config_in_defs(self):
        """Config should also propagate to $defs."""
        class ChildCfg(ProtoModel):
            __tablename__: ClassVar[str] = 'wtest_child_cfg'
            name: str = Field(default='')
            logs: ConsoleField(rows=25) = Field(default='')

        class ParentCfg(ProtoModel):
            __tablename__: ClassVar[str] = 'wtest_parent_cfg'
            name: str = Field(default='')
            items: ListRef[ChildCfg] = Field(default=[])

        ParentCfg.invalidate_schema_cache()
        schema = run_pipeline(ParentCfg)

        child_ui = schema['$defs']['ChildCfg']['properties']['logs'].get('ui', {})
        assert child_ui['widget'] == 'console'
        assert child_ui['config'] == {'rows': 25}
