# tests/test_fk_hydration.py
"""
Test Plan Section 8: FK Hydration & Collection References
Tests flat identity URLs, shallow list[T] hydration, depth levels, Ref fields.
"""

import json
import pytest
from helpers import auth_header

pytestmark = pytest.mark.integration



class TestRefFieldHydration:
    """Single FK Ref fields returned as href URLs."""

    def test_comment_user_owner_as_href(self, client, seed_data):
        """Comment.user_owner is Ref[User], should be hydrated as href (IT-1)."""
        comment = seed_data["comments"][0]
        resp = client.get(f"/Comment/{comment.id}")
        data = resp.json()
        user_owner = data.get("user_owner")
        # Local refs use canonical class-name identity.
        assert isinstance(user_owner, str), f"Expected href string, got {type(user_owner)}"
        assert "/User/" in user_owner


    def test_comment_identity_url_is_resolvable(self, client, seed_data, alice_token):
        """IT-14: GETing a hydrated object's $id should return the entity."""
        product = seed_data["products"][0]
        resp = client.get(f"/Product/{product.id}", headers=auth_header(alice_token))
        data = resp.json()
        comments = data.get("comments", [])
        assert len(comments) > 0, "Product 0 should have comments from seed data"
        comment = comments[0]
        assert isinstance(comment, dict)
        href = comment["$id"]
        # Extract the path from the full URL (TestClient uses relative paths)
        from urllib.parse import urlparse
        path = urlparse(href).path
        resolve_resp = client.get(path)
        assert resolve_resp.status_code == 200
        resolved = resolve_resp.json()
        assert "name" in resolved
        assert "$id" in resolved


class TestModelListHydration:
    """list[T] fields returned as hydrated object arrays on GET."""

    def test_product_comments_as_hydrated_objects(self, client, seed_data, alice_token):
        product = seed_data["products"][0]
        resp = client.get(f"/Product/{product.id}", headers=auth_header(alice_token))
        data = resp.json()
        comments = data.get("comments", [])
        assert isinstance(comments, list)
        if comments:
            assert isinstance(comments[0], dict)
            assert comments[0]["$id"].endswith(f"/Comment/{comments[0]['id']}")
            assert "name" in comments[0]

    def test_product_favorites_as_hydrated_objects(self, client, seed_data, alice_token):
        product = seed_data["products"][0]
        resp = client.get(f"/Product/{product.id}", headers=auth_header(alice_token))
        data = resp.json()
        favorites = data.get("favorites", [])
        assert isinstance(favorites, list)
        if favorites:
            assert isinstance(favorites[0], dict)
            assert favorites[0]["$id"].endswith(f"/Like/{favorites[0]['id']}")

    def test_comment_likes_as_hydrated_objects(self, client, seed_data):
        comment = seed_data["comments"][0]
        resp = client.get(f"/Comment/{comment.id}")
        data = resp.json()
        likes = data.get("likes", [])
        assert isinstance(likes, list)
        if likes:
            assert isinstance(likes[0], dict)
            assert likes[0]["$id"].endswith(f"/Like/{likes[0]['id']}")


class TestSelfRefFK:
    """Ref['self'] -- self-referential FK."""

    def test_reply_has_parent_id(self, client, seed_data):
        """Replies have parent_id set to the parent comment's ID."""
        reply = seed_data["replies"][0]
        parent = seed_data["comments"][0]
        resp = client.get(f"/Comment/{reply.id}")
        data = resp.json()
        assert data.get("parent_id") == parent.id

    def test_top_level_comment_has_null_parent_id(self, client, seed_data):
        comment = seed_data["comments"][0]
        resp = client.get(f"/Comment/{comment.id}")
        data = resp.json()
        assert data.get("parent_id") is None

    def test_parent_id_schema_type_is_selfref(self, client):
        """Comment schema keeps parent_id as a selfref."""
        schema = client.get("/Comment").json()
        parent_prop = schema["properties"]["parent_id"]
        assert parent_prop.get("type") == "selfref"


class TestHydrationOnList:
    """Hydrated list[T] arrays present on every item in paginated responses."""

    def test_list_products_each_has_comments_href(self, client, alice_token, seed_data):
        resp = client.get("/Product/_?limit=5&offset=0", headers=auth_header(alice_token))
        data = resp.json()
        for item in data["data"]:
            assert "comments" in item
            assert isinstance(item["comments"], list)


class TestPopulateDepthLevels:
    """?populate= and ?depth= preserve shallow list[T] hydration."""

    # ── Depth 0 (no populate): shallow hydrated arrays ──

    def test_depth_0_get_returns_hydrated_arrays(self, client, alice_token, seed_data):
        """Without populate/depth, comments are hydrated objects."""
        product = seed_data["products"][0]
        resp = client.get(f"/Product/{product.id}",
                          headers=auth_header(alice_token))
        data = resp.json()
        comments = data.get("comments", [])
        assert isinstance(comments, list), "comments must be a list"
        assert len(comments) > 0, "Product 0 has seed comments"
        assert isinstance(comments[0], dict), "Without populate, comments are hydrated objects"
        assert comments[0]["$id"].endswith(f"/Comment/{comments[0]['id']}")

    def test_depth_0_list_returns_hydrated_arrays(self, client, alice_token, seed_data):
        """Without populate/depth, list items have hydrated arrays."""
        resp = client.get("/Product/_?limit=2",
                          headers=auth_header(alice_token))
        data = resp.json()
        assert "data" in data
        first = data["data"][0]
        comments = first.get("comments", [])
        assert isinstance(comments, list)
        if comments:
            assert isinstance(comments[0], dict), "Without populate, comments are hydrated objects"

    # ── Depth 1 (populate=comments): list[T] remains a hydrated array ──

    def test_depth_1_get_populates_comments(self, client, alice_token, seed_data):
        """?populate=comments returns comment objects with $schema/$id."""
        product = seed_data["products"][0]
        resp = client.get(f"/Product/{product.id}?populate=comments",
                          headers=auth_header(alice_token))
        data = resp.json()
        comments = data.get("comments")
        assert isinstance(comments, list), f"Expected hydrated list, got {type(comments)}"
        assert len(comments) > 0, "Product 0 has seed comments"
        comment_obj = comments[0]
        assert "$schema" in comment_obj, "Populated comment must have $schema"
        assert "$id" in comment_obj, "Populated comment must have $id"
        assert "name" in comment_obj, "Populated comment must have name field"

    def test_depth_1_get_likes_stay_hydrated_list(self, client, alice_token, seed_data):
        """?populate=comments at depth 1 keeps nested list[T] as hydrated objects."""
        product = seed_data["products"][0]
        resp = client.get(f"/Product/{product.id}?populate=comments",
                          headers=auth_header(alice_token))
        data = resp.json()
        comment_obj = data["comments"][0]
        likes = comment_obj.get("likes", [])
        assert isinstance(likes, list), "likes must be a list"
        if likes:
            assert isinstance(likes[0], dict), "At depth 1, nested likes are hydrated objects"

    def test_depth_1_list_returns_hydrated_comments(self, client, alice_token, seed_data):
        """?populate=comments on list endpoint returns hydrated comments."""
        resp = client.get("/Product/_?limit=2&populate=comments",
                          headers=auth_header(alice_token))
        data = resp.json()
        assert "data" in data
        assert len(data["data"]) > 0
        first = data["data"][0]
        comments = first.get("comments")
        assert isinstance(comments, list), f"Expected hydrated list, got {type(comments)}"

    # ── Depth 2: current list[T] hydration remains object arrays ──

    def test_depth_2_get_populates_comments_and_likes(self, client, alice_token, seed_data):
        """?populate=comments&depth=2 keeps comments and nested likes as arrays."""
        product = seed_data["products"][0]
        resp = client.get(f"/Product/{product.id}?populate=comments&depth=2",
                          headers=auth_header(alice_token))
        data = resp.json()
        comments = data.get("comments")
        assert isinstance(comments, list), "comments must be a hydrated list"
        assert len(comments) > 0
        first_comment = comments[0]
        likes = first_comment.get("likes")
        assert isinstance(likes, list), f"At depth 2, likes must be a hydrated list, got {type(likes)}"

    def test_depth_2_list_keeps_nested_lists_hydrated(self, client, alice_token, seed_data):
        """?populate=comments&depth=2 on list endpoint keeps nested likes hydrated."""
        resp = client.get("/Product/_?limit=2&populate=comments&depth=2",
                          headers=auth_header(alice_token))
        data = resp.json()
        assert "data" in data
        first = data["data"][0]
        comments = first.get("comments")
        assert isinstance(comments, list), "comments must be a hydrated list"
        if comments:
            first_comment = comments[0]
            likes = first_comment.get("likes")
            assert isinstance(likes, list), "At depth 2, likes must be a hydrated list"

    # ── Edge cases ──

    def test_populate_nonexistent_field_ignored(self, client, alice_token, seed_data):
        """Populating a non-existent field should not cause errors."""
        product = seed_data["products"][0]
        resp = client.get(f"/Product/{product.id}?populate=nonexistent_field",
                          headers=auth_header(alice_token))
        assert resp.status_code == 200

    def test_depth_only_without_populate(self, client, alice_token, seed_data):
        """?depth=1 without populate= keeps local model-list fields hydrated."""
        product = seed_data["products"][0]
        resp = client.get(f"/Product/{product.id}?depth=1",
                          headers=auth_header(alice_token))
        data = resp.json()
        comments = data.get("comments")
        # depth=1 should keep local model-list fields hydrated
        assert isinstance(comments, list), f"depth=1 should keep hydrated comments, got {type(comments)}"
