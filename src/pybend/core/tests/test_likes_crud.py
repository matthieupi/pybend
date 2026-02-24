# tests/test_likes_crud.py
"""
Test Plan Section: Like model CRUD operations.
Likes are used as CommentLike and ProductLike (favorites) join models.
"""

import pytest
from tests.helpers import auth_header


class TestCommentLikes:
    """Likes on comments via the Comment.like() custom method."""

    def test_list_comment_likes_via_populated_comment(self, client, seed_data):
        """Verify likes appear on comments when fetched."""
        product = seed_data["products"][0]
        comment = seed_data["comments"][0]
        resp = client.get(f"/products/{product.id}/comments/{comment.id}")
        data = resp.json()
        likes = data.get("likes", [])
        assert isinstance(likes, list)
        # Comment 0 has 2 likes from seed data
        assert len(likes) >= 2


class TestProductFavorites:
    """Favorites on products via the Product.favorite() custom method."""

    def test_list_product_favorites_via_product(self, client, seed_data, alice_token):
        """Verify favorites appear on products when fetched."""
        product = seed_data["products"][0]
        resp = client.get(f"/products/{product.id}", headers=auth_header(alice_token))
        data = resp.json()
        favorites = data.get("favorites", [])
        assert isinstance(favorites, list)
        # Product 0 has 2 favorites from seed data
        assert len(favorites) >= 2


class TestLikeProtectedFields:
    """Like.user is a protected field -- auto-injected, never editable."""

    def test_like_schema_user_protected(self, client):
        """Like is registered as CommentLike join model."""
        schema = client.get("/CommentLike").json()
        user_prop = schema.get("properties", {}).get("user", {})
        assert user_prop.get("ui", {}).get("protected") is True
