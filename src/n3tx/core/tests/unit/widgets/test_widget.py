"""
Tests for Widget class, WidgetMeta metaclass, dual syntax, and auto-detection.
"""

import pytest
from datetime import date, datetime
from typing import Annotated, Optional, get_origin, get_args

from pydantic import BaseModel, Field, AnyHttpUrl, EmailStr

from n3tx_core.widgets.widget import (
    Widget, WidgetMeta,
    UrlField, EmailField, DateField, DateTimeField,
    MarkdownField, ConsoleField, ReferenceField,
    CurrencyField, TextareaField,
    AUTO_DETECT_MAP, register_auto_detect, get_auto_widget,
)

pytestmark = pytest.mark.unit


# ===================================================================
# Widget class basics
# ===================================================================

class TestWidgetClass:

    def test_widget_has_metaclass(self):
        assert type(Widget) is WidgetMeta

    def test_widget_default_name(self):
        assert Widget.name == 'default'

    def test_widget_default_base_type(self):
        assert Widget.base_type is str


# ===================================================================
# Built-in field types — names and base types
# ===================================================================

class TestBuiltinFields:

    @pytest.mark.parametrize('cls, expected_name, expected_type', [
        (UrlField, 'url', AnyHttpUrl),
        (EmailField, 'email', EmailStr),
        (DateField, 'date', date),
        (DateTimeField, 'datetime', datetime),
        (MarkdownField, 'markdown', str),
        (ConsoleField, 'console', str),
        (ReferenceField, 'reference', str),
        (CurrencyField, 'currency', float),
        (TextareaField, 'textarea', str),
    ])
    def test_field_name_and_type(self, cls, expected_name, expected_type):
        assert cls.name == expected_name
        assert cls.base_type is expected_type

    def test_all_fields_are_widget_subclasses(self):
        for cls in [UrlField, EmailField, DateField, DateTimeField,
                    MarkdownField, ConsoleField, ReferenceField,
                    CurrencyField, TextareaField]:
            assert issubclass(cls, Widget)


# ===================================================================
# Dual syntax — bare annotation vs called with config
# ===================================================================

class TestDualSyntax:

    def test_bare_usage_is_a_type(self):
        """MarkdownField (bare) is a type, usable as annotation."""
        assert isinstance(MarkdownField, type)
        assert issubclass(MarkdownField, Widget)

    def test_called_returns_annotated(self):
        """MarkdownField(rows=10) returns Annotated[str, <instance>]."""
        result = MarkdownField(rows=10)
        assert get_origin(result) is Annotated

    def test_called_annotated_base_type(self):
        """Annotated has correct base type."""
        result = MarkdownField(rows=10)
        args = get_args(result)
        assert args[0] is str  # base_type of MarkdownField

    def test_called_annotated_widget_instance(self):
        """Annotated contains a Widget instance marker."""
        result = MarkdownField(rows=10)
        args = get_args(result)
        instance = args[1]
        assert isinstance(instance, MarkdownField)
        assert isinstance(instance, Widget)

    def test_called_config_stored(self):
        """Config kwargs are stored on the instance."""
        result = MarkdownField(rows=10)
        instance = get_args(result)[1]
        assert instance.config == {'rows': 10}

    def test_called_name_preserved(self):
        """Widget name is preserved on instance."""
        result = MarkdownField(rows=10)
        instance = get_args(result)[1]
        assert instance.name == 'markdown'

    def test_called_with_no_config(self):
        """MarkdownField() with no kwargs still works."""
        result = MarkdownField()
        assert get_origin(result) is Annotated
        instance = get_args(result)[1]
        assert instance.config == {}

    def test_called_multiple_config_keys(self):
        """Multiple config kwargs are stored."""
        result = ConsoleField(rows=30, theme='dark')
        instance = get_args(result)[1]
        assert instance.config == {'rows': 30, 'theme': 'dark'}

    def test_url_called_returns_annotated(self):
        """UrlField() returns Annotated with AnyHttpUrl base."""
        result = UrlField(target='_blank')
        args = get_args(result)
        assert args[0] is AnyHttpUrl
        assert args[1].config == {'target': '_blank'}

    def test_currency_called_returns_annotated(self):
        """CurrencyField(symbol='EUR') returns Annotated with float base."""
        result = CurrencyField(symbol='EUR')
        args = get_args(result)
        assert args[0] is float
        assert args[1].config == {'symbol': 'EUR'}


# ===================================================================
# Pydantic validation — __get_pydantic_core_schema__
# ===================================================================

class TestPydanticValidation:

    def test_bare_str_field_validates(self):
        class M(BaseModel):
            body: MarkdownField
        m = M(body='hello')
        assert m.body == 'hello'

    def test_bare_str_field_rejects_invalid(self):
        class M(BaseModel):
            body: MarkdownField
        with pytest.raises(Exception):
            M(body=123)

    def test_bare_url_validates(self):
        class M(BaseModel):
            site: UrlField
        m = M(site='https://example.com')
        assert 'example.com' in str(m.site)

    def test_bare_url_rejects_invalid(self):
        class M(BaseModel):
            site: UrlField
        with pytest.raises(Exception):
            M(site='not-a-url')

    def test_bare_email_validates(self):
        class M(BaseModel):
            contact: EmailField
        m = M(contact='user@example.com')
        assert m.contact == 'user@example.com'

    def test_bare_email_rejects_invalid(self):
        class M(BaseModel):
            contact: EmailField
        with pytest.raises(Exception):
            M(contact='not-an-email')

    def test_bare_date_validates(self):
        class M(BaseModel):
            published: DateField
        m = M(published='2024-01-15')
        assert m.published == date(2024, 1, 15)

    def test_bare_datetime_validates(self):
        class M(BaseModel):
            created: DateTimeField
        m = M(created='2024-01-15T10:30:00')
        assert m.created == datetime(2024, 1, 15, 10, 30, 0)

    def test_bare_currency_validates(self):
        class M(BaseModel):
            price: CurrencyField
        m = M(price=9.99)
        assert m.price == 9.99

    def test_bare_currency_rejects_string(self):
        class M(BaseModel):
            price: CurrencyField
        with pytest.raises(Exception):
            M(price='not-a-number')

    def test_called_with_config_still_validates(self):
        """MarkdownField(rows=10) produces Annotated[str, ...] — Pydantic validates as str."""
        class M(BaseModel):
            body: MarkdownField(rows=10)
        m = M(body='hello world')
        assert m.body == 'hello world'

    def test_optional_widget_field(self):
        """Optional[WidgetField] works."""
        class M(BaseModel):
            site: Optional[UrlField] = None
        m = M()
        assert m.site is None
        m2 = M(site='https://example.com')
        assert 'example.com' in str(m2.site)


# ===================================================================
# Custom widget creation
# ===================================================================

class TestCustomWidget:

    def test_custom_widget_name_auto_derived(self):
        class ColorField(Widget, name='color', base_type=str):
            pass
        assert ColorField.name == 'color'
        assert ColorField.base_type is str

    def test_custom_widget_name_from_classname(self):
        """If no name given, derived from class name minus 'Field'."""
        class SpecialField(Widget, base_type=int):
            pass
        assert SpecialField.name == 'special'

    def test_custom_widget_bare_validates(self):
        class ColorField(Widget, name='color', base_type=str):
            pass
        class M(BaseModel):
            color: ColorField
        m = M(color='#ff0000')
        assert m.color == '#ff0000'

    def test_custom_widget_called_with_config(self):
        class ColorField(Widget, name='color', base_type=str):
            pass
        result = ColorField(swatches=True)
        assert get_origin(result) is Annotated
        instance = get_args(result)[1]
        assert instance.name == 'color'
        assert instance.config == {'swatches': True}

    def test_custom_widget_is_subclass(self):
        class ColorField(Widget, name='color', base_type=str):
            pass
        assert issubclass(ColorField, Widget)


# ===================================================================
# Auto-detection registry
# ===================================================================

class TestAutoDetect:

    def test_url_auto_detect(self):
        assert get_auto_widget(AnyHttpUrl) == 'url'

    def test_email_auto_detect(self):
        assert get_auto_widget(EmailStr) == 'email'

    def test_date_auto_detect(self):
        assert get_auto_widget(date) == 'date'

    def test_datetime_auto_detect(self):
        assert get_auto_widget(datetime) == 'datetime'

    def test_str_no_auto_detect(self):
        assert get_auto_widget(str) is None

    def test_int_no_auto_detect(self):
        assert get_auto_widget(int) is None

    def test_register_custom_auto_detect(self):
        """Custom type can be registered for auto-detection."""
        class CustomType(str):
            pass

        initial_len = len(AUTO_DETECT_MAP)
        register_auto_detect(CustomType, 'custom')
        assert get_auto_widget(CustomType) == 'custom'

        # Cleanup
        AUTO_DETECT_MAP.pop()
        assert len(AUTO_DETECT_MAP) == initial_len
