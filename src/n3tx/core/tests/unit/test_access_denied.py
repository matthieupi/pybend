"""Tests for authorize/errors.py — AccessDenied exception."""

import pytest
from n3tx.core.authorize.errors import AccessDenied

pytestmark = pytest.mark.unit



class TestAccessDenied:

    def test_basic(self):
        e = AccessDenied(action='create', model='Product')
        assert e.action == 'create'
        assert e.model == 'Product'

    def test_user_id(self):
        e = AccessDenied(action='delete', model='Comment', user_id=5)
        assert e.user_id == 5

    def test_user_id_none(self):
        e = AccessDenied(action='read', model='M')
        assert e.user_id is None

    def test_auto_detail(self):
        e = AccessDenied(action='update', model='Product', user_id=1)
        assert 'update' in e.detail
        assert 'Product' in e.detail
        assert '1' in e.detail

    def test_custom_detail(self):
        e = AccessDenied(action='read', model='M', detail='Custom message')
        assert e.detail == 'Custom message'

    def test_inherits_exception(self):
        e = AccessDenied(action='read', model='M')
        assert isinstance(e, Exception)

    def test_str(self):
        e = AccessDenied(action='delete', model='Comment', user_id=3)
        s = str(e)
        assert 'delete' in s
        assert 'Comment' in s

    def test_can_be_raised(self):
        with pytest.raises(AccessDenied):
            raise AccessDenied(action='create', model='Product', user_id=1)

    def test_can_be_caught(self):
        try:
            raise AccessDenied(action='update', model='Product')
        except AccessDenied as e:
            assert e.action == 'update'
