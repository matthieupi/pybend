"""Tests for utils/decorators.py — @expose_route decorator."""

import pytest
from n3tx_core.utils.decorators import expose_route
from n3tx_core.authorize.rules import AUTHENTICATED, ANYONE, OWNER

pytestmark = pytest.mark.unit


class TestExposeRoute:

    def test_adds_endpoint_dict(self):
        @expose_route('/test', methods=['POST'])
        def handler(self):
            pass
        assert hasattr(handler, '__endpoint__')
        assert handler.__endpoint__['route'] == '/test'

    def test_methods_default_post(self):
        @expose_route('/test')
        def handler(self):
            pass
        assert handler.__endpoint__['methods'] == ['POST']

    def test_methods_get(self):
        @expose_route('/test', methods=['GET'])
        def handler(self):
            pass
        assert handler.__endpoint__['methods'] == ['GET']

    def test_methods_put(self):
        @expose_route('/test', methods=['PUT'])
        def handler(self):
            pass
        assert handler.__endpoint__['methods'] == ['PUT']

    def test_methods_delete(self):
        @expose_route('/test', methods=['DELETE'])
        def handler(self):
            pass
        assert handler.__endpoint__['methods'] == ['DELETE']

    def test_methods_multiple(self):
        @expose_route('/test', methods=['POST', 'PUT'])
        def handler(self):
            pass
        assert handler.__endpoint__['methods'] == ['POST', 'PUT']

    def test_access_none_default(self):
        @expose_route('/test')
        def handler(self):
            pass
        assert handler.__endpoint__['access'] is None

    def test_access_authenticated(self):
        @expose_route('/test', access=AUTHENTICATED)
        def handler(self):
            pass
        assert handler.__endpoint__['access'] is AUTHENTICATED

    def test_access_anyone(self):
        @expose_route('/test', access=ANYONE)
        def handler(self):
            pass
        assert handler.__endpoint__['access'] is ANYONE

    def test_access_owner(self):
        @expose_route('/test', access=OWNER)
        def handler(self):
            pass
        assert handler.__endpoint__['access'] is OWNER

    def test_access_composite(self):
        rule = OWNER | AUTHENTICATED
        @expose_route('/test', access=rule)
        def handler(self):
            pass
        assert handler.__endpoint__['access'] is rule

    def test_function_still_callable(self):
        @expose_route('/test')
        def handler():
            return 'hello'
        assert handler() == 'hello'

    def test_route_with_leading_slash(self):
        @expose_route('/action')
        def handler(self):
            pass
        assert handler.__endpoint__['route'] == '/action'

    def test_preserves_function_name(self):
        @expose_route('/test')
        def my_handler(self):
            pass
        assert my_handler.__name__ == 'my_handler'
