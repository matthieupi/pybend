# tests/test_likes_crud.py
"""
Test Plan Section: Like model CRUD operations.
Likes are first-class flat entities referenced by Comment.likes/Product.favorites.

IT-4: Expanded from 3 tests to comprehensive like CRUD coverage.
"""

import pytest
from helpers import auth_header

pytestmark = pytest.mark.integration



class TestCommentLikes:
    """Likes on comments via the Comment.like() custom method."""

    def test_list_comment_likes_via_populated_comment(self, client, alice_token, bob_token, seed_data):
        """Verify likes appear on comments when fetched."""
        product = seed_data["products"][0]
        created = client.post(f"/Product/{product.id}/comment", json={
            "comment": {"name": "Like visibility", "description": "has a like"},
        }, headers=auth_header(alice_token)).json()
        client.post(f"/Comment/{created['id']}/like", json={}, headers=auth_header(bob_token))

        resp = client.get(f"/Comment/{created['id']}")
        likes = resp.json().get("likes", [])
        assert isinstance(likes, list)
        assert len(likes) >= 1

    def test_like_creates_like_record(self, client, charlie_token, seed_data):
        """IT-4: Like via custom method should create a record that appears in likes."""
        comment = seed_data["comments"][2]  # comment on product 1
        before = client.get(f"/Comment/{comment.id}")
        initial_count = len(before.json().get("likes", []))

        resp = client.post(f"/Comment/{comment.id}/like", json={}, headers=auth_header(charlie_token))
        assert resp.status_code == 200
        data = resp.json()
        action = data["action"]

        after = client.get(f"/Comment/{comment.id}")
        after_likes = after.json().get("likes", [])
        if action == "liked":
            assert len(after_likes) == initial_count + 1
        else:  # "unliked"
            assert len(after_likes) == initial_count - 1

    def test_like_toggle_unlike(self, client, alice_token, seed_data):
        """IT-4: Two consecutive calls should toggle like/unlike."""
        comment = seed_data["comments"][3]
        resp1 = client.post(f"/Comment/{comment.id}/like", json={}, headers=auth_header(alice_token))
        data1 = resp1.json()
        resp2 = client.post(f"/Comment/{comment.id}/like", json={}, headers=auth_header(alice_token))
        data2 = resp2.json()
        assert data1["action"] != data2["action"]

    def test_like_unauthenticated_returns_401(self, client, seed_data):
        """IT-4: Anonymous user cannot like."""
        comment = seed_data["comments"][0]
        resp = client.post(f"/Comment/{comment.id}/like", json={})
        assert resp.status_code == 401

    def test_like_different_users(self, client, alice_token, bob_token, seed_data):
        """IT-4: Different users can independently like the same comment."""
        comment = seed_data["comments"][4]

        # Both users like
        r1 = client.post(f"/Comment/{comment.id}/like", json={}, headers=auth_header(alice_token))
        assert r1.status_code == 200
        r2 = client.post(f"/Comment/{comment.id}/like", json={}, headers=auth_header(bob_token))
        assert r2.status_code == 200


class TestProductFavorites:
    """Favorites on products via the Product.favorite() custom method."""

    def test_list_product_favorites_via_product(self, client, seed_data, alice_token):
        """Verify favorites appear on products when fetched."""
        product = seed_data["products"][0]
        resp = client.get(f"/Product/{product.id}", headers=auth_header(alice_token))
        data = resp.json()
        favorites = data.get("favorites", [])
        assert isinstance(favorites, list)
        # Product 0 has 2 favorites from seed data
        assert len(favorites) >= 2

    def test_favorite_creates_record(self, client, charlie_token, seed_data, alice_token):
        """IT-4: Favorite via custom method creates a persisted record."""
        product = seed_data["products"][3]
        before = client.get(f"/Product/{product.id}", headers=auth_header(alice_token))
        initial = len(before.json().get("favorites", []))

        resp = client.post(f"/Product/{product.id}/favorite",
                           json={}, headers=auth_header(charlie_token))
        assert resp.status_code == 200
        data = resp.json()
        action = data["action"]

        after = client.get(f"/Product/{product.id}", headers=auth_header(alice_token))
        final = len(after.json().get("favorites", []))
        if action == "favorited":
            assert final == initial + 1
        else:
            assert final == initial - 1


class TestLikeProtectedFields:
    """Like.user is a protected field -- auto-injected, never editable."""

    def test_like_schema_user_protected(self, client):
        """Like schema marks user as protected."""
        schema = client.get("/Like").json()
        user_prop = schema.get("properties", {}).get("user", {})
        assert user_prop.get("ui", {}).get("protected") is True


class TestDirectLikeCRUD:
    """IT-4: Removed nested like CRUD routes."""

    def test_create_like_via_nested_route_removed(self, client, alice_token, seed_data):
        product = seed_data["products"][0]
        comment = seed_data["comments"][1]
        resp = client.post(
            f"/Product/{product.id}/Comment/{comment.id}/likes",
            json={"user": seed_data["users"]["alice"].id},
            headers=auth_header(alice_token),
        )
        assert resp.status_code in (404, 405)

    def test_list_likes_via_nested_route_removed(self, client, seed_data):
        product = seed_data["products"][0]
        comment = seed_data["comments"][0]
        resp = client.get(f"/Product/{product.id}/Comment/{comment.id}/likes")
        assert resp.status_code in (404, 405)
