"""Tests for authorize/schema.py — access_schema serialization."""

import pytest
from unittest.mock import MagicMock

from authorize.schema import access_schema
from authorize.rules import ANYONE, AUTHENTICATED, OWNER, ROLE, Where


class TestAccessSchema:

    def test_no_access_defaults(self):
        model = MagicMock(spec=[])
        # No __access__ attribute
        model_no_access = type('M', (), {})
        result = access_schema(model_no_access)
        assert '*' in result
        assert result['*'] == {'rule': 'authenticated'}

    def test_anyone_serialized(self):
        model = type('M', (), {'__access__': {'read': ANYONE}})
        result = access_schema(model)
        assert result['read'] == {'rule': 'anyone'}

    def test_authenticated_serialized(self):
        model = type('M', (), {'__access__': {'create': AUTHENTICATED}})
        result = access_schema(model)
        assert result['create'] == {'rule': 'authenticated'}

    def test_owner_serialized(self):
        model = type('M', (), {'__access__': {'update': OWNER}})
        result = access_schema(model)
        assert result['update'] == {'rule': 'owner'}

    def test_role_serialized(self):
        model = type('M', (), {'__access__': {'delete': ROLE('admin')}})
        result = access_schema(model)
        assert result['delete'] == {'rule': 'role', 'roles': ['admin']}

    def test_composite_or_serialized(self):
        model = type('M', (), {'__access__': {'update': OWNER | ROLE('admin')}})
        result = access_schema(model)
        assert result['update']['op'] == 'or'
        assert len(result['update']['rules']) == 2

    def test_composite_and_serialized(self):
        model = type('M', (), {'__access__': {'read': AUTHENTICATED & Where(status='published')}})
        result = access_schema(model)
        assert result['read']['op'] == 'and'

    def test_where_serialized(self):
        model = type('M', (), {'__access__': {'read': Where(status='published')}})
        result = access_schema(model)
        assert result['read'] == {'rule': 'where', 'conditions': {'status': 'published'}}

    def test_multiple_actions(self):
        model = type('M', (), {'__access__': {
            'read': ANYONE,
            'create': AUTHENTICATED,
            'update': OWNER,
            'delete': ROLE('admin'),
        }})
        result = access_schema(model)
        assert len(result) == 4
        assert 'read' in result
        assert 'create' in result
        assert 'update' in result
        assert 'delete' in result

    def test_non_rule_fallback(self):
        model = type('M', (), {'__access__': {'custom': 'some_string'}})
        result = access_schema(model)
        assert result['custom'] == {'rule': 'some_string'}
