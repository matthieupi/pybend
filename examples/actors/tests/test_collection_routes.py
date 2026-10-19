# tests/test_collection_routes.py
"""
Test Plan Section 5: Flat collection routes.

Join-model collection routes are removed. First-class models expose flat
collection endpoints, while parent membership is represented by hydrated
``list[T]`` fields on the parent resource.
"""

import pytest
from helpers import auth_header

pytestmark = pytest.mark.integration



class TestCommentsCollection:
    """GET /Comment/_ -- all comments across products."""

    def test_collection_route_returns_200(self, client, alice_token, seed_data):
        resp = client.get("/Comment/_?limit=100", headers=auth_header(alice_token))
        assert resp.status_code == 200

    def test_collection_returns_list(self, client, alice_token, seed_data):
        resp = client.get("/Comment/_?limit=100", headers=auth_header(alice_token))
        items = resp.json().get("data", [])
        assert isinstance(items, list)
        assert len(items) >= 8  # 8 comments + 3 replies from seed

    def test_collection_supports_pagination(self, client, alice_token, seed_data):
        resp = client.get("/Comment/_?limit=2&offset=0",
                          headers=auth_header(alice_token))
        data = resp.json()
        assert "data" in data
        assert "meta" in data
        assert len(data["data"]) <= 2

    def test_collection_items_have_metadata(self, client, alice_token, seed_data):
        resp = client.get("/Comment/_?limit=1", headers=auth_header(alice_token))
        items = resp.json().get("data", [])
        if items:
            first = items[0]
            assert "$schema" in first
            assert "$id" in first


class TestLikesCollection:
    """GET /Like/_ -- all likes/favorites."""

    def test_collection_route_returns_200(self, client, alice_token, seed_data):
        resp = client.get("/Like/_?limit=100", headers=auth_header(alice_token))
        assert resp.status_code == 200

    def test_collection_returns_likes(self, client, alice_token, seed_data):
        resp = client.get("/Like/_?limit=100", headers=auth_header(alice_token))
        items = resp.json().get("data", [])
        assert isinstance(items, list)
        assert len(items) >= 5  # 5 likes from seed


class TestCollectionEdgeCases:
    """IT-6: Edge cases for collection routes."""

    def test_collection_with_populate(self, client, alice_token, seed_data):
        """IT-6: Collection route with populate parameter."""
        resp = client.get("/Comment/_?limit=2&populate=likes",
                          headers=auth_header(alice_token))
        assert resp.status_code == 200

    def test_collection_exact_count(self, client, alice_token, seed_data):
        """IT-6: Verify exact count in meta matches actual records."""
        resp = client.get("/Comment/_?limit=100",
                          headers=auth_header(alice_token))
        data = resp.json()
        items = data.get("data", [])
        meta = data.get("meta", {})
        # The returned items count should match total (since limit=100 > total)
        assert len(items) == meta.get("total", -1), \
            f"Items ({len(items)}) != meta.total ({meta.get('total')})"

    def test_collection_items_have_user_field(self, client, alice_token, seed_data):
        resp = client.get("/Like/_?limit=1", headers=auth_header(alice_token))
        items = resp.json().get("data", [])
        if items:
            first = items[0]
            assert "user" in first

    def test_removed_join_collection_routes_return_404(self, client, alice_token):
        for route in ("/products_comments", "/comments_likes", "/Product_likes"):
            resp = client.get(route, headers=auth_header(alice_token))
            assert resp.status_code == 404
