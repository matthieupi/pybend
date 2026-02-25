# tests/test_pagination.py
"""
Test Plan Section 9: Pagination & Metadata
Tests limit/offset, has_more, total count, boundary conditions.
"""

import pytest
from pybend.example.tests.helpers import auth_header

pytestmark = pytest.mark.integration



class TestPaginationStructure:
    """Response structure: {data: [...], meta: {total, limit, offset, has_more}}."""

    def test_paginated_response_has_data_and_meta(self, client, alice_token, seed_data):
        resp = client.get("/products?limit=2&offset=0", headers=auth_header(alice_token))
        data = resp.json()
        assert "data" in data
        assert "meta" in data

    def test_meta_has_required_fields(self, client, alice_token, seed_data):
        resp = client.get("/products?limit=2&offset=0", headers=auth_header(alice_token))
        meta = resp.json()["meta"]
        assert "total" in meta
        assert "limit" in meta
        assert "offset" in meta
        assert "has_more" in meta

    def test_meta_limit_matches_request(self, client, alice_token, seed_data):
        resp = client.get("/products?limit=3&offset=0", headers=auth_header(alice_token))
        meta = resp.json()["meta"]
        assert meta["limit"] == 3

    def test_meta_offset_matches_request(self, client, alice_token, seed_data):
        resp = client.get("/products?limit=2&offset=2", headers=auth_header(alice_token))
        meta = resp.json()["meta"]
        assert meta["offset"] == 2


class TestTotalCount:
    """meta.total = count of ALL records before LIMIT."""

    def test_total_count_reflects_all_records(self, client, alice_token, seed_data):
        resp = client.get("/products?limit=1&offset=0", headers=auth_header(alice_token))
        meta = resp.json()["meta"]
        # Seed data has at least 5 products (might have more from other test creates)
        assert meta["total"] >= 5

    def test_total_count_consistent_across_pages(self, client, alice_token, seed_data):
        resp1 = client.get("/products?limit=2&offset=0", headers=auth_header(alice_token))
        resp2 = client.get("/products?limit=2&offset=2", headers=auth_header(alice_token))
        assert resp1.json()["meta"]["total"] == resp2.json()["meta"]["total"]


class TestHasMoreFlag:
    """has_more = (offset + returned_count) < total."""

    def test_has_more_true_when_more_pages(self, client, alice_token, seed_data):
        resp = client.get("/products?limit=2&offset=0", headers=auth_header(alice_token))
        data = resp.json()
        meta = data["meta"]
        if meta["total"] > 2:
            assert meta["has_more"] is True

    def test_has_more_false_when_all_returned(self, client, alice_token, seed_data):
        resp = client.get("/products?limit=100&offset=0", headers=auth_header(alice_token))
        meta = resp.json()["meta"]
        assert meta["has_more"] is False

    def test_has_more_false_on_last_page(self, client, alice_token, seed_data):
        # Get total first
        resp_total = client.get("/products?limit=1&offset=0", headers=auth_header(alice_token))
        total = resp_total.json()["meta"]["total"]

        # Fetch last page
        resp = client.get(f"/products?limit=2&offset={max(total - 2, 0)}",
                          headers=auth_header(alice_token))
        meta = resp.json()["meta"]
        assert meta["has_more"] is False


class TestBoundaryConditions:
    """Edge cases for pagination parameters."""

    def test_offset_beyond_total_returns_empty(self, client, alice_token, seed_data):
        resp = client.get("/products?limit=10&offset=10000", headers=auth_header(alice_token))
        data = resp.json()
        assert data["data"] == []
        assert data["meta"]["has_more"] is False

    def test_limit_zero_returns_422(self, client, alice_token):
        resp = client.get("/products?limit=0", headers=auth_header(alice_token))
        assert resp.status_code == 422

    def test_limit_over_100_returns_422(self, client, alice_token):
        resp = client.get("/products?limit=101", headers=auth_header(alice_token))
        assert resp.status_code == 422

    def test_negative_offset_returns_422(self, client, alice_token):
        resp = client.get("/products?offset=-1", headers=auth_header(alice_token))
        assert resp.status_code == 422

    def test_limit_without_offset_defaults_offset_to_zero(self, client, alice_token, seed_data):
        resp = client.get("/products?limit=2", headers=auth_header(alice_token))
        meta = resp.json()["meta"]
        assert meta["offset"] == 0


class TestPaginationDefaults:
    """IT-10: Default limit behavior and edge cases."""

    def test_default_limit_returns_all(self, client, alice_token, seed_data):
        """No limit/offset params returns plain array (default behavior)."""
        resp = client.get("/products", headers=auth_header(alice_token))
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 5

    def test_limit_one_returns_single_item(self, client, alice_token, seed_data):
        """limit=1 should return exactly one item."""
        resp = client.get("/products?limit=1", headers=auth_header(alice_token))
        data = resp.json()
        assert len(data["data"]) == 1
        assert data["meta"]["limit"] == 1

    def test_exact_boundary_page(self, client, alice_token, seed_data):
        """IT-10: When offset + limit == total, has_more should be False."""
        # Get total
        resp = client.get("/products?limit=1&offset=0", headers=auth_header(alice_token))
        total = resp.json()["meta"]["total"]

        if total > 1:
            # Fetch at exact boundary
            boundary_resp = client.get(
                f"/products?limit=1&offset={total - 1}",
                headers=auth_header(alice_token),
            )
            data = boundary_resp.json()
            assert len(data["data"]) == 1
            assert data["meta"]["has_more"] is False

    def test_string_limit_rejected(self, client, alice_token):
        """Non-numeric limit should return 422."""
        resp = client.get("/products?limit=abc", headers=auth_header(alice_token))
        assert resp.status_code == 422


class TestPaginationWithComments:
    """Pagination also works on nested comment routes."""

    def test_comments_paginated(self, client, seed_data):
        product = seed_data["products"][0]
        resp = client.get(f"/products/{product.id}/comments?limit=1")
        data = resp.json()
        assert "data" in data
        assert "meta" in data
        assert len(data["data"]) <= 1

    def test_comments_total_count(self, client, seed_data):
        product = seed_data["products"][0]
        resp = client.get(f"/products/{product.id}/comments?limit=1")
        meta = resp.json()["meta"]
        # Product 0 has at least 2 comments plus replies
        assert meta["total"] >= 2
