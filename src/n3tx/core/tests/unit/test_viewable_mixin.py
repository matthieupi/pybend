"""Tests for models/viewable_mixin.py — ViewableMixin view() and href.

CG-4: Coverage gap — viewable_mixin.py has zero test coverage.
"""

import pytest

from n3tx.core.models.viewable_mixin import ViewableMixin

pytestmark = pytest.mark.unit



class TestViewableMixinInit:

    def test_basic_creation(self):
        v = ViewableMixin(name="test", desc="description", src="/inbox")
        assert v.name == "test"
        assert v.desc == "description"
        assert v.src == "/inbox"

    def test_defaults_name_to_class(self):
        v = ViewableMixin(name="", desc="", src="")
        # name is passed as empty string
        assert v.name == ""

    def test_empty_desc(self):
        v = ViewableMixin(name="test", desc="", src="")
        assert v.desc == ""


class TestViewableMixinSubclass:

    def test_subclass_href_set(self):
        class MyWidget(ViewableMixin):
            pass
        assert MyWidget.href == "/mywidget"

    def test_subclass_href_lowercased(self):
        class BigComponent(ViewableMixin):
            pass
        assert BigComponent.href == "/bigcomponent"

    def test_multiple_subclasses_independent(self):
        class WidgetA(ViewableMixin):
            pass
        class WidgetB(ViewableMixin):
            pass
        assert WidgetA.href == "/widgeta"
        assert WidgetB.href == "/widgetb"


class TestViewMethod:

    def test_returns_view_url(self):
        class TestView(ViewableMixin):
            pass
        result = TestView.view()
        assert result == "/testview/view"

    def test_has_expose_route(self):
        assert hasattr(ViewableMixin.view, '__endpoint__')

    def test_expose_route_path(self):
        endpoint = ViewableMixin.view.__endpoint__
        assert endpoint['route'] == '/view'

    def test_expose_route_method(self):
        endpoint = ViewableMixin.view.__endpoint__
        assert 'GET' in endpoint['methods']
