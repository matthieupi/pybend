"""Tests for models/comment_model.py — Comment model fields and methods."""

import pytest
from unittest.mock import MagicMock, patch
from typing import ClassVar

from pydantic import ValidationError

from models import Comment, Like
from n3tx_core.authorize import ANYONE, AUTHENTICATED, OWNER, ROLE
from n3tx_core.utils.erroring import MethodError

pytestmark = pytest.mark.unit



class TestCommentFields:

    def test_name_min_length(self):
        with pytest.raises(ValidationError):
            Comment(name='')

    def test_name_max_length(self):
        Comment(name='x' * 500)  # Should succeed

    def test_name_over_max(self):
        with pytest.raises(ValidationError):
            Comment(name='x' * 501)

    def test_description_default(self):
        c = Comment(name='test')
        assert c.description == ''

    def test_tablename(self):
        assert Comment.__tablename__ == 'comments'

    def test_storable(self):
        assert Comment.__storable__ is True

    def test_protected_fields(self):
        assert 'user_owner' in Comment.__protected_fields__

    def test_access_rules(self):
        assert 'read' in Comment.__access__
        assert 'create' in Comment.__access__
        assert 'update' in Comment.__access__
        assert 'delete' in Comment.__access__

    def test_access_read_anyone(self):
        from n3tx_core.authorize.rules import _Anyone
        assert isinstance(Comment.__access__['read'], _Anyone)

    def test_parent_id_default_none(self):
        c = Comment(name='test')
        assert c.parent_id is None

    def test_likes_default_empty(self):
        c = Comment(name='test')
        assert c.likes == []


class TestCommentLike:

    def test_like_no_user(self):
        c = Comment(id=1, name='test')
        with pytest.raises(MethodError):
            c.like(user=None)

    def test_like_creates_new(self):
        c = Comment(id=1, name='test')
        mock_user = MagicMock()
        mock_user.id = 1

        saved_like = Like(id=5, user=1)
        with patch.object(Like, 'create', return_value=saved_like), \
             patch.object(Comment, 'update', return_value=c) as update:
            result = c.like(user=mock_user)
            assert result['action'] == 'liked'
            assert result['_field'] == 'likes'
            assert result['id'] == 5
            assert result['user'] == 1
            assert 'created_at' in result
            update.assert_called_once_with(1, {'likes': [saved_like]})

    def test_unlike_existing(self):
        c = Comment(id=1, name='test')
        mock_user = MagicMock()
        mock_user.id = 1

        existing = Like(id=5, user=1)
        c.likes = [existing]

        with patch.object(Like, 'delete') as delete, \
             patch.object(Comment, 'update', return_value=c) as update:
            result = c.like(user=mock_user)
            assert result == {'action': 'unliked', '_field': 'likes', 'id': 5}
            delete.assert_called_once_with(5)
            update.assert_called_once_with(1, {'likes': []})


class TestCommentReply:

    def test_reply_creates_with_parent_id(self):
        c = Comment(id=10, name='parent')
        mock_user = MagicMock()
        mock_user.id = 2

        reply_comment = Comment(id=11, name='reply text', parent_id=10)
        with patch.object(Comment, 'create', return_value=reply_comment):
            result = c.reply(text='reply text', user=mock_user)
            assert isinstance(result, Comment)

    def test_reply_no_user(self):
        c = Comment(id=10, name='parent')
        reply_comment = Comment(id=11, name='reply text', parent_id=10)
        with patch.object(Comment, 'create', return_value=reply_comment):
            result = c.reply(text='reply text', user=None)
            assert isinstance(result, Comment)
