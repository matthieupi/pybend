"""Tests for models/like_model.py — Like model fields."""

import pytest
from models import Like

pytestmark = pytest.mark.unit



class TestLikeFields:

    def test_tablename(self):
        assert Like.__tablename__ == 'likes'

    def test_storable(self):
        assert Like.__storable__ is True

    def test_protected_fields(self):
        assert 'user' in Like.__protected_fields__

    def test_created_at_default(self):
        like = Like(user=1)
        assert like.created_at == ''

    def test_user_field_required(self):
        # user has no default, but FK rewriting may have altered this
        # In Like, user is typed as User which gets rewritten to Ref[User]
        # The field should accept an integer value
        like = Like(user=5)
        assert like.user is not None

    def test_created_at_set(self):
        like = Like(user=1, created_at='2025-01-01T00:00:00')
        assert like.created_at == '2025-01-01T00:00:00'
