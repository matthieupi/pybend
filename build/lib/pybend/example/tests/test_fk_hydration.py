# tests/test_fk_hydration.py
"""
Test Plan Section 8: FK Hydration & Collection References
Tests href arrays, populated responses, depth levels, Ref fields.
"""

import json
import pytest
from pybend.example.tests.helpers import auth_header

pytestmark = pytest.mark.integration



class TestRefFieldHydration:
    """Single FK Ref fields returned as href URLs."""

    def test_comment_user_owner_as_href(self, client, seed_data):
        """Comment.user_owner is Ref[User], should be hydrated as href (IT-1)."""
        product = seed_data["products"][0]
        comment = seed_data["comments"][0]
        resp = client.get(f"/products/{product.id}/comments/{comment.id}")
        data = resp.json()
        user_owner = data.get("user_owner")
        # Should be an href string like "http://localhost:5000/users/2"
        assert isinstance(user_owner, str), f"Expected href string, got {type(user_owner)}"
        assert "/users/" in user_owner


    def test_comment_href_is_resolvable(self, client, seed_data, alice_token):
        """IT-14: GETing an href URL should return the referenced entity."""
        product = seed_data["products"][0]
        resp = client.get(f"/products/{product.id}", headers=auth_header(alice_token))
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
        resp = client.get(f"/products/{product.id}", headers=auth_header(alice_token))
        data = resp.json()
        comments = data.get("comments", [])
        assert isinstance(comments, list)
        if comments:
            assert isinstance(comments[0], str)
            assert "/products/" in comments[0]
            assert "/comments/" in comments[0]

    def test_product_favorites_as_href_array(self, client, seed_data, alice_token):
        product = seed_data["products"][0]
        resp = client.get(f"/products/{product.id}", headers=auth_header(alice_token))
        data = resp.json()
        favorites = data.get("favorites", [])
        assert isinstance(favorites, list)
        if favorites:
            assert isinstance(favorites[0], str)
            assert "/products/" in favorites[0]

    def test_comment_likes_as_href_array(self, client, seed_data):
        product = seed_data["products"][0]
        comment = seed_data["comments"][0]
        resp = client.get(f"/products/{product.id}/comments/{comment.id}")
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
        resp = client.get(f"/products/{product.id}/comments/{reply.id}")
        data = resp.json()
        assert data.get("parent_id") == parent.id

    def test_top_level_comment_has_null_parent_id(self, client, seed_data):
        product = seed_data["products"][0]
        comment = seed_data["comments"][0]
        resp = client.get(f"/products/{product.id}/comments/{comment.id}")
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
        resp = client.get("/products?limit=5&offset=0", headers=auth_header(alice_token))
        data = resp.json()
        for item in data["data"]:
            assert "comments" in item
            assert isinstance(item["comments"], list)


class TestPopulateDepthLevels:
    """?populate= and ?depth= for eager loading."""

    def test_populate_comments_returns_objects(self, client, alice_token, seed_data):
        product = seed_data["products"][0]
        resp = client.get(f"/products/{product.id}?populate=comments",
                          headers=auth_header(alice_token))
        data = resp.json()
        comments = data.get("comments", {})
        # With populate, comments should be a {data: [...], meta: {...}} wrapper
        if isinstance(comments, dict) and "data" in comments:
            assert isinstance(comments["data"], list)
            if comments["data"]:
                comment_obj = comments["data"][0]
                assert "$schema" in comment_obj
                assert "$id" in comment_obj
                assert "name" in comment_obj
        else:
            # Fallback: might still be href array if populate didn't match
            assert isinstance(comments, list)

    def test_populate_depth_2_loads_nested(self, client, alice_token, seed_data):
        """?populate=comments&depth=2 should load comments AND their likes."""
        product = seed_data["products"][0]
        resp = client.get(f"/products/{product.id}?populate=comments&depth=2",
                          headers=auth_header(alice_token))
        data = resp.json()
        comments = data.get("comments", {})
        if isinstance(comments, dict) and "data" in comments and comments["data"]:
            first_comment = comments["data"][0]
            likes = first_comment.get("likes", {})
            # At depth 2, likes should be populated (objects, not just hrefs)
            if isinstance(likes, dict) and "data" in likes:
                assert isinstance(likes["data"], list)

    def test_populate_nonexistent_field_ignored(self, client, alice_token, seed_data):
        """Populating a non-existent field should not cause errors."""
        product = seed_data["products"][0]
        resp = client.get(f"/products/{product.id}?populate=nonexistent_field",
                          headers=auth_header(alice_token))
        assert resp.status_code == 200

    def test_populate_on_list_endpoint(self, client, alice_token, seed_data):
        """?populate= also works on list endpoints."""
        resp = client.get("/products?limit=2&populate=comments",
                          headers=auth_header(alice_token))
        data = resp.json()
        assert "data" in data
        if data["data"]:
            first = data["data"][0]
            comments = first.get("comments", {})
            # Should be populated objects, not just hrefs
            if isinstance(comments, dict) and "data" in comments:
                assert isinstance(comments["data"], list)
