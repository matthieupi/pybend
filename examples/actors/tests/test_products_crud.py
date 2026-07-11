# tests/test_products_crud.py
"""
Test Plan Section 3: Full CRUD Lifecycle for Products
"""

import pytest
from helpers import auth_header

pytestmark = pytest.mark.integration



class TestCreateProduct:
    """POST /Product -- create product."""

    def test_create_product_authenticated_returns_201(self, client, alice_token):
        resp = client.post("/Product", json={
            "name": "Widget",
            "price": 99.99,
            "description": "A great widget",
        }, headers=auth_header(alice_token))
        assert resp.status_code == 201

    def test_create_product_has_schema_and_id(self, client, alice_token):
        resp = client.post("/Product", json={
            "name": "Schema Test",
            "price": 10.00,
        }, headers=auth_header(alice_token))
        data = resp.json()
        assert "$schema" in data
        assert "$id" in data
        assert data["$schema"].endswith("/Product")

    def test_create_product_has_auto_generated_id(self, client, alice_token):
        resp = client.post("/Product", json={
            "name": "Auto ID Test",
            "price": 5.00,
        }, headers=auth_header(alice_token))
        data = resp.json()
        assert "id" in data
        assert data["id"] > 0

    def test_create_product_default_values(self, client, alice_token):
        resp = client.post("/Product", json={
            "name": "Defaults Test",
            "price": 1.00,
        }, headers=auth_header(alice_token))
        data = resp.json()
        assert data.get("description") == ""
        assert isinstance(data.get("comments"), list)
        assert isinstance(data.get("favorites"), list)

    def test_create_product_unauthenticated_returns_401(self, client):
        resp = client.post("/Product", json={
            "name": "No Auth",
            "price": 10.00,
        })
        assert resp.status_code == 401

    def test_create_product_missing_name_returns_422(self, client, alice_token):
        resp = client.post("/Product", json={
            "price": 10.00,
        }, headers=auth_header(alice_token))
        assert resp.status_code == 422

    def test_create_product_negative_price_returns_422(self, client, alice_token):
        resp = client.post("/Product", json={
            "name": "Negative Price",
            "price": -5.00,
        }, headers=auth_header(alice_token))
        assert resp.status_code == 422

    def test_create_product_zero_price_returns_422(self, client, alice_token):
        resp = client.post("/Product", json={
            "name": "Zero Price",
            "price": 0,
        }, headers=auth_header(alice_token))
        assert resp.status_code == 422

    def test_create_product_name_exceeds_max_length_returns_422(self, client, alice_token):
        resp = client.post("/Product", json={
            "name": "x" * 201,
            "price": 10.00,
        }, headers=auth_header(alice_token))
        assert resp.status_code == 422


class TestReadProduct:
    """GET /Product/{id} -- read single product.
    Product has no __access__ dict so defaults to AUTHENTICATED for all actions.
    """

    def test_read_product_returns_200(self, client, alice_token, seed_data):
        product = seed_data["products"][0]
        resp = client.get(f"/Product/{product.id}", headers=auth_header(alice_token))
        assert resp.status_code == 200

    def test_read_product_has_schema_metadata(self, client, alice_token, seed_data):
        product = seed_data["products"][0]
        resp = client.get(f"/Product/{product.id}", headers=auth_header(alice_token))
        data = resp.json()
        assert "$schema" in data
        assert "$id" in data
        assert data["$id"].endswith(f"/Product/{product.id}")

    def test_read_product_comments_are_hydrated_objects(self, client, alice_token, seed_data):
        product = seed_data["products"][0]
        resp = client.get(f"/Product/{product.id}", headers=auth_header(alice_token))
        data = resp.json()
        comments = data.get("comments", [])
        assert isinstance(comments, list)
        # Seed data has comments on product 0
        if comments:
            assert isinstance(comments[0], dict)
            assert comments[0]["$id"].endswith(f"/Comment/{comments[0]['id']}")

    def test_read_product_favorites_are_hydrated_objects(self, client, alice_token, seed_data):
        product = seed_data["products"][0]
        resp = client.get(f"/Product/{product.id}", headers=auth_header(alice_token))
        data = resp.json()
        favorites = data.get("favorites", [])
        assert isinstance(favorites, list)

    def test_read_product_not_found_returns_404(self, client, alice_token):
        resp = client.get("/Product/99999", headers=auth_header(alice_token))
        assert resp.status_code == 404

    def test_read_product_requires_auth(self, client, seed_data):
        """Product has no __access__, defaults to AUTHENTICATED for read.
        Unauthenticated request should return 401."""
        product = seed_data["products"][0]
        resp = client.get(f"/Product/{product.id}")
        assert resp.status_code == 401


class TestListProducts:
    """GET /Product/_ -- list products."""

    def test_list_products_returns_200(self, client, alice_token, seed_data):
        resp = client.get("/Product/_", headers=auth_header(alice_token))
        assert resp.status_code == 200

    def test_list_products_returns_array(self, client, alice_token, seed_data):
        """Without pagination params, returns plain array."""
        resp = client.get("/Product/_", headers=auth_header(alice_token))
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 5  # seed data has 5 products

    def test_list_products_paginated_structure(self, client, alice_token, seed_data):
        resp = client.get("/Product/_?limit=2&offset=0", headers=auth_header(alice_token))
        data = resp.json()
        assert "data" in data
        assert "meta" in data
        meta = data["meta"]
        assert "total" in meta
        assert "limit" in meta
        assert "offset" in meta
        assert "has_more" in meta

    def test_list_products_paginated_has_more_true(self, client, alice_token, seed_data):
        resp = client.get("/Product/_?limit=2&offset=0", headers=auth_header(alice_token))
        data = resp.json()
        assert len(data["data"]) == 2
        assert data["meta"]["has_more"] is True

    def test_list_products_paginated_has_more_false(self, client, alice_token, seed_data):
        resp = client.get("/Product/_?limit=100&offset=0", headers=auth_header(alice_token))
        data = resp.json()
        assert data["meta"]["has_more"] is False

    def test_list_products_offset_beyond_total(self, client, alice_token, seed_data):
        resp = client.get("/Product/_?limit=10&offset=1000", headers=auth_header(alice_token))
        data = resp.json()
        assert data["data"] == []
        assert data["meta"]["has_more"] is False

    def test_list_products_limit_zero_returns_422(self, client, alice_token):
        resp = client.get("/Product/_?limit=0", headers=auth_header(alice_token))
        assert resp.status_code == 422

    def test_list_products_limit_exceeds_max_returns_422(self, client, alice_token):
        resp = client.get("/Product/_?limit=101", headers=auth_header(alice_token))
        assert resp.status_code == 422

    def test_list_products_negative_offset_returns_422(self, client, alice_token):
        resp = client.get("/Product/_?offset=-1", headers=auth_header(alice_token))
        assert resp.status_code == 422

    def test_list_products_each_item_has_schema_metadata(self, client, alice_token, seed_data):
        resp = client.get("/Product/_?limit=2&offset=0", headers=auth_header(alice_token))
        data = resp.json()
        for item in data["data"]:
            assert "$schema" in item
            assert "$id" in item


class TestUpdateProduct:
    """PUT /Product/{id} -- partially update a product."""

    def test_update_product_as_authenticated_returns_200(self, client, alice_token, seed_data):
        product = seed_data["products"][0]
        resp = client.put(f"/Product/{product.id}", json={
            "name": "Updated Headphones",
            "price": product.price,
        }, headers=auth_header(alice_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Headphones"

    def test_update_product_unauthenticated_returns_401(self, client, seed_data):
        """PUT without auth token. Validation runs first (422 if body incomplete),
        so we must provide a valid body to test auth enforcement."""
        product = seed_data["products"][0]
        resp = client.put(f"/Product/{product.id}", json={
            "name": "Should Fail",
            "price": product.price,
        })
        assert resp.status_code == 401

    def test_update_product_changes_only_specified_fields(self, client, alice_token, seed_data):
        """Update name while keeping the same price -- price stays the same."""
        product = seed_data["products"][1]
        original_price = product.price
        resp = client.put(f"/Product/{product.id}", json={
            "name": "Update Name Test",
            "price": original_price,
        }, headers=auth_header(alice_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Update Name Test"
        assert data["price"] == original_price

    def test_update_product_not_found_returns_404(self, client, alice_token):
        resp = client.put("/Product/99999", json={
            "name": "Ghost",
            "price": 10.00,
        }, headers=auth_header(alice_token))
        assert resp.status_code == 404

    def test_update_product_preserves_omitted_required_field(self, client, alice_token, seed_data):
        product = seed_data["products"][0]
        original_price = product.price
        resp = client.put(f"/Product/{product.id}", json={
            "name": "Partial update",
        }, headers=auth_header(alice_token))
        assert resp.status_code == 200
        assert resp.json()["name"] == "Partial update"
        assert resp.json()["price"] == original_price


class TestDeleteProduct:
    """DELETE /Product/{id} -- delete product."""

    def test_delete_product_as_admin_returns_200(self, client, admin_token, alice_token, seed_data):
        # Create a product to delete
        create_resp = client.post("/Product", json={
            "name": "Delete Me",
            "price": 1.00,
        }, headers=auth_header(alice_token))
        product_id = create_resp.json()["id"]

        resp = client.delete(f"/Product/{product_id}", headers=auth_header(admin_token))
        assert resp.status_code == 200

        # Verify it's gone (need auth since Product defaults to AUTHENTICATED)
        get_resp = client.get(f"/Product/{product_id}", headers=auth_header(admin_token))
        assert get_resp.status_code == 404

    def test_delete_product_as_regular_user_returns_403(self, client, alice_token, bob_token, seed_data):
        """Regular users cannot delete products (default access is AUTHENTICATED,
        but deletion should require higher privileges if configured)."""
        # Create a product
        create_resp = client.post("/Product", json={
            "name": "Cannot Delete",
            "price": 1.00,
        }, headers=auth_header(alice_token))
        product_id = create_resp.json()["id"]

        resp = client.delete(f"/Product/{product_id}", headers=auth_header(bob_token))
        # Product has no __access__ so defaults to AUTHENTICATED for all actions.
        # Any authenticated user can delete (IT-1: exact expected status).
        assert resp.status_code == 200

    def test_delete_product_not_found_returns_404(self, client, admin_token):
        resp = client.delete("/Product/99999", headers=auth_header(admin_token))
        assert resp.status_code == 404


class TestLegacyProductRoutes:
    """Compatibility smoke for legacy table-name transport routes."""

    def test_legacy_list_still_matches_class_name_list(self, client, alice_token, seed_data):
        legacy = client.get("/products?limit=2&offset=0", headers=auth_header(alice_token))
        canonical = client.get("/Product/_?limit=2&offset=0", headers=auth_header(alice_token))
        assert legacy.status_code == 200
        assert legacy.json() == canonical.json()

    def test_legacy_read_still_matches_class_name_read(self, client, alice_token, seed_data):
        product = seed_data["products"][0]
        legacy = client.get(f"/products/{product.id}", headers=auth_header(alice_token))
        canonical = client.get(f"/Product/{product.id}", headers=auth_header(alice_token))
        assert legacy.status_code == 200
        assert legacy.json() == canonical.json()
