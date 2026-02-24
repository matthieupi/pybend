# tests/test_collection_routes.py
"""
Test Plan Section 5: Collection Routes (Join Models)
Tests GET-only collection routes that return all records across parents.
"""

import pytest
from tests.helpers import auth_header


class TestProductCommentsCollection:
    """GET /products_comments -- all comments across all products."""

    def test_collection_route_returns_200(self, client, alice_token, seed_data):
        resp = client.get("/products_comments", headers=auth_header(alice_token))
        assert resp.status_code == 200

    def test_collection_returns_list(self, client, alice_token, seed_data):
        resp = client.get("/products_comments", headers=auth_header(alice_token))
        data = resp.json()
        items = data if isinstance(data, list) else data.get("data", [])
        assert isinstance(items, list)
        assert len(items) >= 8  # 8 comments + 3 replies from seed

    def test_collection_supports_pagination(self, client, alice_token, seed_data):
        resp = client.get("/products_comments?limit=2&offset=0",
                          headers=auth_header(alice_token))
        data = resp.json()
        assert "data" in data
        assert "meta" in data
        assert len(data["data"]) <= 2

    def test_collection_items_have_metadata(self, client, alice_token, seed_data):
        resp = client.get("/products_comments", headers=auth_header(alice_token))
        data = resp.json()
        items = data if isinstance(data, list) else data.get("data", [])
        if items:
            first = items[0]
            assert "$schema" in first
            assert "$id" in first


class TestCommentLikesCollection:
    """GET /comments_likes -- all likes across all comments."""

    def test_collection_route_returns_200(self, client, alice_token, seed_data):
        resp = client.get("/comments_likes", headers=auth_header(alice_token))
        assert resp.status_code == 200

    def test_collection_returns_likes(self, client, alice_token, seed_data):
        resp = client.get("/comments_likes", headers=auth_header(alice_token))
        data = resp.json()
        items = data if isinstance(data, list) else data.get("data", [])
        assert isinstance(items, list)
        assert len(items) >= 5  # 5 likes from seed


class TestProductLikesCollection:
    """GET /products_likes -- all favorites across all products."""

    def test_collection_route_returns_200(self, client, alice_token, seed_data):
        resp = client.get("/products_likes", headers=auth_header(alice_token))
        assert resp.status_code == 200

    def test_collection_returns_favorites(self, client, alice_token, seed_data):
        resp = client.get("/products_likes", headers=auth_header(alice_token))
        data = resp.json()
        items = data if isinstance(data, list) else data.get("data", [])
        assert isinstance(items, list)
        assert len(items) >= 5  # 5 favorites from seed

    def test_collection_items_have_user_field(self, client, alice_token, seed_data):
        resp = client.get("/products_likes", headers=auth_header(alice_token))
        data = resp.json()
        items = data if isinstance(data, list) else data.get("data", [])
        if items:
            first = items[0]
            assert "user" in first
