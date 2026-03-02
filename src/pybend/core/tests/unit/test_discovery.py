"""Tests for api/discovery.py — /_meta and /.well-known/agent.json."""

import pytest
from unittest.mock import MagicMock

from pybend.core.api.discovery import _build_meta, _build_agent_card
from pybend.core.authorize.rules import ANYONE, AUTHENTICATED, OWNER, ROLE

pytestmark = pytest.mark.unit


def _make_model(name, tablename, access=None, federated=False, methods=None):
    """Create a mock model class with the given attributes."""
    cls = type(name, (), {
        '__name__': name,
        '__tablename__': tablename,
    })
    if access:
        cls.__access__ = access
    if federated:
        cls.__federated__ = True
    # Add mock methods with _route_path
    for method_name, route_info in (methods or {}).items():
        fn = MagicMock()
        fn._route_path = route_info['route']
        fn._route_methods = route_info['methods']
        setattr(cls, method_name, fn)
    return cls


class TestBuildMeta:

    def test_basic_structure(self):
        models = {'products': _make_model('Product', 'products')}
        meta = _build_meta(models, 'TestApp', '1.0.0', 'http://localhost:5000')

        assert meta['name'] == 'TestApp'
        assert meta['version'] == '1.0.0'
        assert meta['base_url'] == 'http://localhost:5000'
        assert 'products' in meta['models']
        assert 'capabilities' in meta

    def test_model_info(self):
        models = {'products': _make_model('Product', 'products')}
        meta = _build_meta(models, 'App', '1.0', 'http://localhost:5000')
        product = meta['models']['products']

        assert product['name'] == 'Product'
        assert product['tablename'] == 'products'
        assert product['schema_url'] == 'http://localhost:5000/Product'
        assert product['collection_url'] == 'http://localhost:5000/products'

    def test_access_rules_serialized(self):
        models = {'products': _make_model('Product', 'products', access={
            'read': ANYONE,
            'create': AUTHENTICATED,
        })}
        meta = _build_meta(models, 'App', '1.0', 'http://localhost:5000')
        product = meta['models']['products']

        assert product['access']['read'] == {'rule': 'anyone'}
        assert product['access']['create'] == {'rule': 'authenticated'}

    def test_federated_flag(self):
        models = {'products': _make_model('Product', 'products', federated=True)}
        meta = _build_meta(models, 'App', '1.0', 'http://localhost:5000')

        assert meta['models']['products']['federated'] is True

    def test_non_federated_no_flag(self):
        models = {'products': _make_model('Product', 'products')}
        meta = _build_meta(models, 'App', '1.0', 'http://localhost:5000')

        assert 'federated' not in meta['models']['products']

    def test_custom_methods_included(self):
        models = {'products': _make_model('Product', 'products', methods={
            'favorite': {'route': '/favorite', 'methods': ['POST']},
        })}
        meta = _build_meta(models, 'App', '1.0', 'http://localhost:5000')
        product = meta['models']['products']

        assert 'methods' in product
        assert 'favorite' in product['methods']
        assert product['methods']['favorite']['route'] == '/favorite'

    def test_default_capabilities(self):
        meta = _build_meta({}, 'App', '1.0', 'http://localhost:5000')
        caps = meta['capabilities']

        assert caps['crud'] is True
        assert caps['schema'] is True
        assert caps['authentication'] is True
        assert caps['authorization'] is True

    def test_custom_capabilities_merged(self):
        meta = _build_meta(
            {}, 'App', '1.0', 'http://localhost:5000',
            capabilities={'mcp': True, 'federation': True},
        )
        caps = meta['capabilities']

        assert caps['mcp'] is True
        assert caps['federation'] is True
        assert caps['crud'] is True  # defaults preserved

    def test_empty_models(self):
        meta = _build_meta({}, 'App', '1.0', 'http://localhost:5000')
        assert meta['models'] == {}

    def test_multiple_models(self):
        models = {
            'products': _make_model('Product', 'products'),
            'users': _make_model('User', 'users'),
        }
        meta = _build_meta(models, 'App', '1.0', 'http://localhost:5000')

        assert len(meta['models']) == 2
        assert 'products' in meta['models']
        assert 'users' in meta['models']


class TestBuildAgentCard:

    def test_basic_structure(self):
        models = {'products': _make_model('Product', 'products')}
        card = _build_agent_card(models, 'TestApp', '1.0.0', 'http://localhost:5000')

        assert card['name'] == 'TestApp'
        assert card['version'] == '1.0.0'
        assert card['url'] == 'http://localhost:5000'
        assert 'capabilities' in card
        assert 'authentication' in card
        assert 'skills' in card

    def test_crud_skill_per_model(self):
        models = {'products': _make_model('Product', 'products')}
        card = _build_agent_card(models, 'App', '1.0', 'http://localhost:5000')
        skills = card['skills']

        crud_skills = [s for s in skills if s['id'] == 'products_crud']
        assert len(crud_skills) == 1
        assert crud_skills[0]['name'] == 'Product Management'
        assert 'crud' in crud_skills[0]['tags']

    def test_custom_method_skill(self):
        models = {'products': _make_model('Product', 'products', methods={
            'favorite': {'route': '/favorite', 'methods': ['POST']},
        })}
        card = _build_agent_card(models, 'App', '1.0', 'http://localhost:5000')
        skills = card['skills']

        method_skills = [s for s in skills if s['id'] == 'products_favorite']
        assert len(method_skills) == 1
        assert method_skills[0]['name'] == 'Product.favorite'

    def test_authentication_info(self):
        card = _build_agent_card({}, 'App', '1.0', 'http://localhost:5000')
        auth = card['authentication']

        assert 'bearer' in auth['schemes']
        assert auth['credentials'] == 'http://localhost:5000/users/login'

    def test_default_description(self):
        card = _build_agent_card({}, 'App', '1.0', 'http://localhost:5000')
        assert card['description'] == 'App — a PyBend application'

    def test_custom_description(self):
        card = _build_agent_card(
            {}, 'App', '1.0', 'http://localhost:5000',
            description='My custom app',
        )
        assert card['description'] == 'My custom app'

    def test_io_modes(self):
        card = _build_agent_card({}, 'App', '1.0', 'http://localhost:5000')
        assert 'application/json' in card['defaultInputModes']
        assert 'application/json' in card['defaultOutputModes']

    def test_multiple_models_multiple_skills(self):
        models = {
            'products': _make_model('Product', 'products'),
            'users': _make_model('User', 'users'),
        }
        card = _build_agent_card(models, 'App', '1.0', 'http://localhost:5000')
        skills = card['skills']

        crud_ids = [s['id'] for s in skills if s['id'].endswith('_crud')]
        assert 'products_crud' in crud_ids
        assert 'users_crud' in crud_ids
