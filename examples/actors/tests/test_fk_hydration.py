# tests/test_fk_hydration.py
"""
Test Plan Section 8: FK Hydration & Collection References
Tests href arrays, populated responses, depth levels, Ref fields.
"""

import json
import pytest
from helpers import auth_header

pytestmark = pytest.mark.integration



class TestRefFieldHydration:
    """Single FK Ref fields returned as href URLs."""

    def test_comment_user_owner_as_href(self, client, seed_data):
        """Comment.user_owner is Ref[User], should be hydrated as href (IT-1)."""
        product = seed_data["products"][0]
        comment = seed_data["comments"][0]
        resp = client.get(f"/Product/{product.id}/Comment/{comment.id}")
        data = resp.json()
        user_owner = data.get("user_owner")
        # Should be an href string like "http://localhost:5000/users/2"
        assert isinstance(user_owner, str), f"Expected href string, got {type(user_owner)}"
        assert "/users/" in user_owner


    def test_comment_href_is_resolvable(self, client, seed_data, alice_token):
        """IT-14: GETing an href URL should return the referenced entity."""
        product = seed_data["products"][0]
        resp = client.get(f"/Product/{product.id}", headers=auth_header(alice_token))
        data = resp.json()
        comments = data.get("comments", [])
        assert len(comments) > 0, "Product 0 should have comments from seed data"
        # Resolve the first href
        href = comments[0]
        assert isinstance(href, str)
        # Extract the path from the full URL (TestClient uses relative paths)
        from urllib.parse import urlparse
        path = urlparse(href).path
        resolve_resp = client.get(path)
        assert resolve_resp.status_code == 200
        resolved = resolve_resp.json()
        assert "name" in resolved
        assert "$id" in resolved


class TestListRefHydration:
    """ListRef fields returned as href arrays on GET."""

    def test_product_comments_as_href_array(self, client, seed_data, alice_token):
        product = seed_data["products"][0]
        resp = client.get(f"/Product/{product.id}", headers=auth_header(alice_token))
        data = resp.json()
        comments = data.get("comments", [])
        assert isinstance(comments, list)
        if comments:
            assert isinstance(comments[0], str)
            assert "/Product/" in comments[0]
            assert "/comments/" in comments[0]

    def test_product_favorites_as_href_array(self, client, seed_data, alice_token):
        product = seed_data["products"][0]
        resp = client.get(f"/Product/{product.id}", headers=auth_header(alice_token))
        data = resp.json()
        favorites = data.get("favorites", [])
        assert isinstance(favorites, list)
        if favorites:
            assert isinstance(favorites[0], str)
            assert "/Product/" in favorites[0]

    def test_comment_likes_as_href_array(self, client, seed_data):
        product = seed_data["products"][0]
        comment = seed_data["comments"][0]
        resp = client.get(f"/Product/{product.id}/Comment/{comment.id}")
        data = resp.json()
        likes = data.get("likes", [])
        assert isinstance(likes, list)


class TestSelfRefFK:
    """Ref['self'] -- self-referential FK."""

    def test_reply_has_parent_id(self, client, seed_data):
        """Replies have parent_id set to the parent comment's ID."""
        product = seed_data["products"][0]
        reply = seed_data["replies"][0]
        parent = seed_data["comments"][0]
        resp = client.get(f"/Product/{product.id}/Comment/{reply.id}")
        data = resp.json()
        assert data.get("parent_id") == parent.id

    def test_top_level_comment_has_null_parent_id(self, client, seed_data):
        product = seed_data["products"][0]
        comment = seed_data["comments"][0]
        resp = client.get(f"/Product/{product.id}/Comment/{comment.id}")
        data = resp.json()
        assert data.get("parent_id") is None

    def test_parent_id_schema_type_is_selfref(self, client):
        """Comment is registered as ProductComment join model."""
        schema = client.get("/ProductComment").json()
        parent_prop = schema["properties"]["parent_id"]
        assert parent_prop.get("type") == "selfref"


class TestHydrationOnList:
    """Href arrays present on every item in paginated list responses."""

    def test_list_products_each_has_comments_href(self, client, alice_token, seed_data):
        resp = client.get("/Product/_?limit=5&offset=0", headers=auth_header(alice_token))
        data = resp.json()
        for item in data["data"]:
            assert "comments" in item
            assert isinstance(item["comments"], list)


class TestPopulateDepthLevels:
    """?populate= and ?depth= for eager loading across depth 0, 1, 2."""

    # ── Depth 0 (no populate): href arrays only ──

    def test_depth_0_get_returns_href_arrays(self, client, alice_token, seed_data):
        """Without populate/depth, comments are href strings."""
        product = seed_data["products"][0]
        resp = client.get(f"/Product/{product.id}",
                          headers=auth_header(alice_token))
        data = resp.json()
        comments = data.get("comments", [])
        assert isinstance(comments, list), "comments must be a list"
        assert len(comments) > 0, "Product 0 has seed comments"
        assert isinstance(comments[0], str), "Without populate, comments are href strings"
        assert "/comments/" in comments[0]

    def test_depth_0_list_returns_href_arrays(self, client, alice_token, seed_data):
        """Without populate/depth, list items have href arrays."""
        resp = client.get("/Product/_?limit=2",
                          headers=auth_header(alice_token))
        data = resp.json()
        assert "data" in data
        first = data["data"][0]
        comments = first.get("comments", [])
        assert isinstance(comments, list)
        if comments:
            assert isinstance(comments[0], str), "Without populate, comments are href strings"

    # ── Depth 1 (populate=comments): one level of eager loading ──

    def test_depth_1_get_populates_comments(self, client, alice_token, seed_data):
        """?populate=comments returns comment objects with $schema/$id."""
        product = seed_data["products"][0]
        resp = client.get(f"/Product/{product.id}?populate=comments",
                          headers=auth_header(alice_token))
        data = resp.json()
        comments = data.get("comments")
        assert isinstance(comments, dict), f"Expected populated wrapper dict, got {type(comments)}"
        assert "data" in comments, "Populated field must have 'data' key"
        assert len(comments["data"]) > 0, "Product 0 has seed comments"
        comment_obj = comments["data"][0]
        assert "$schema" in comment_obj, "Populated comment must have $schema"
        assert "$id" in comment_obj, "Populated comment must have $id"
        assert "name" in comment_obj, "Populated comment must have name field"

    def test_depth_1_get_likes_still_hrefs(self, client, alice_token, seed_data):
        """?populate=comments at depth 1 — nested likes remain href strings."""
        product = seed_data["products"][0]
        resp = client.get(f"/Product/{product.id}?populate=comments",
                          headers=auth_header(alice_token))
        data = resp.json()
        comment_obj = data["comments"]["data"][0]
        likes = comment_obj.get("likes", [])
        # At depth 1, likes should NOT be populated — still href strings
        assert isinstance(likes, list), "likes must be a list"
        if likes:
            assert isinstance(likes[0], str), "At depth 1, nested likes are still hrefs"

    def test_depth_1_list_populates_comments(self, client, alice_token, seed_data):
        """?populate=comments on list endpoint returns populated wrapper."""
        resp = client.get("/Product/_?limit=2&populate=comments",
                          headers=auth_header(alice_token))
        data = resp.json()
        assert "data" in data
        assert len(data["data"]) > 0
        first = data["data"][0]
        comments = first.get("comments")
        assert isinstance(comments, dict), f"Expected populated wrapper, got {type(comments)}"
        assert "data" in comments
        assert isinstance(comments["data"], list)

    # ── Depth 2 (populate=comments&depth=2): two levels of eager loading ──

    def test_depth_2_get_populates_comments_and_likes(self, client, alice_token, seed_data):
        """?populate=comments&depth=2 loads comments AND their nested likes."""
        product = seed_data["products"][0]
        resp = client.get(f"/Product/{product.id}?populate=comments&depth=2",
                          headers=auth_header(alice_token))
        data = resp.json()
        comments = data.get("comments")
        assert isinstance(comments, dict), "comments must be populated wrapper"
        assert "data" in comments
        assert len(comments["data"]) > 0
        first_comment = comments["data"][0]
        likes = first_comment.get("likes")
        assert isinstance(likes, dict), f"At depth 2, likes must be populated wrapper, got {type(likes)}"
        assert "data" in likes, "Populated likes must have 'data' key"
        assert isinstance(likes["data"], list)

    def test_depth_2_list_populates_nested(self, client, alice_token, seed_data):
        """?populate=comments&depth=2 on list endpoint loads nested likes."""
        resp = client.get("/Product/_?limit=2&populate=comments&depth=2",
                          headers=auth_header(alice_token))
        data = resp.json()
        assert "data" in data
        first = data["data"][0]
        comments = first.get("comments")
        assert isinstance(comments, dict), "comments must be populated wrapper"
        assert "data" in comments
        if comments["data"]:
            first_comment = comments["data"][0]
            likes = first_comment.get("likes")
            assert isinstance(likes, dict), "At depth 2, likes must be populated wrapper"
            assert "data" in likes

    # ── Edge cases ──

    def test_populate_nonexistent_field_ignored(self, client, alice_token, seed_data):
        """Populating a non-existent field should not cause errors."""
        product = seed_data["products"][0]
        resp = client.get(f"/Product/{product.id}?populate=nonexistent_field",
                          headers=auth_header(alice_token))
        assert resp.status_code == 200

    def test_depth_only_without_populate(self, client, alice_token, seed_data):
        """?depth=1 without populate= populates all ListRef fields."""
        product = seed_data["products"][0]
        resp = client.get(f"/Product/{product.id}?depth=1",
                          headers=auth_header(alice_token))
        data = resp.json()
        comments = data.get("comments")
        # depth=1 should auto-populate all ListRef fields
        assert isinstance(comments, dict), f"depth=1 should populate comments, got {type(comments)}"
        assert "data" in comments
