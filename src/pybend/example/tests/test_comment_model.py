"""Tests for models/comment_model.py — Comment model fields and methods."""

import json
import pytest
from unittest.mock import MagicMock, patch
from typing import ClassVar

from pydantic import ValidationError

from pybend.example.models import Comment, Like
from pybend.core.authorize import ANYONE, AUTHENTICATED, OWNER, ROLE
from pybend.core.utils.erroring import MethodError

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
        from pybend.core.authorize.rules import _Anyone
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

    def test_like_join_model_not_registered(self):
        c = Comment(id=1, name='test')
        mock_user = MagicMock()
        mock_user.id = 1

        with patch('pybend.example.models.comment.join_models', {}):
            with pytest.raises(MethodError):
                c.like(user=mock_user)

    def test_like_creates_new(self):
        c = Comment(id=1, name='test')
        mock_user = MagicMock()
        mock_user.id = 1

        mock_join = MagicMock()
        mock_join.list.return_value = []

        with patch('pybend.example.models.comment.join_models', {('Comment', 'Like'): mock_join}):
            with patch.object(Like, 'save', return_value=Like(user=1)):
                result = c.like(user=mock_user)
                parsed = json.loads(result)
                assert parsed['action'] == 'liked'

    def test_unlike_existing(self):
        c = Comment(id=1, name='test')
        mock_user = MagicMock()
        mock_user.id = 1

        existing = MagicMock()
        existing.id = 5
        mock_join = MagicMock()
        mock_join.list.return_value = [existing]

        with patch('pybend.example.models.comment.join_models', {('Comment', 'Like'): mock_join}):
            result = c.like(user=mock_user)
            parsed = json.loads(result)
            assert parsed['action'] == 'unliked'
            mock_join.delete.assert_called_once_with(5)


class TestCommentReply:

    def test_reply_creates_with_parent_id(self):
        c = Comment(id=10, name='parent')
        mock_user = MagicMock()
        mock_user.id = 2

        reply_comment = Comment(id=11, name='reply text', parent_id=10)
        with patch.object(Comment, 'save', return_value=reply_comment):
            result = c.reply(text='reply text', user=mock_user)
            # result is model_dump_json of the created comment
            assert isinstance(result, str)

    def test_reply_no_user(self):
        c = Comment(id=10, name='parent')
        reply_comment = Comment(id=11, name='reply text', parent_id=10)
        with patch.object(Comment, 'save', return_value=reply_comment):
            result = c.reply(text='reply text', user=None)
            assert isinstance(result, str)
