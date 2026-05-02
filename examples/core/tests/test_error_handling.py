# tests/test_error_handling.py
"""
Test Plan Section 10: Error Handling & Edge Cases
Tests 404, 401, 403, 422, 400, 409 responses.
"""

import pytest
from helpers import auth_header

pytestmark = pytest.mark.integration



class TestNotFound404:
    """404 Not Found responses."""

    def test_get_nonexistent_product(self, client, alice_token):
        resp = client.get("/Product/99999", headers=auth_header(alice_token))
        assert resp.status_code == 404

    def test_get_nonexistent_comment(self, client, seed_data):
        product = seed_data["products"][0]
        resp = client.get(f"/Product/{product.id}/Comment/99999")
        assert resp.status_code == 404

    def test_put_nonexistent_product(self, client, alice_token):
        """PUT requires all required fields (including price) for validation to pass
        before the 404 check."""
        resp = client.put("/Product/99999", json={"name": "Ghost", "price": 10.00},
                          headers=auth_header(alice_token))
        assert resp.status_code == 404

    def test_delete_nonexistent_product(self, client, admin_token):
        resp = client.delete("/Product/99999", headers=auth_header(admin_token))
        assert resp.status_code == 404

    def test_custom_method_on_nonexistent_product(self, client, alice_token):
        resp = client.post("/Product/99999/comment", json={
            "comment": {"name": "Ghost", "description": "test"},
        }, headers=auth_header(alice_token))
        assert resp.status_code == 404


class TestUnauthorized401:
    """401 Unauthorized -- invalid or expired tokens."""

    def test_invalid_token_on_auth_me(self, client):
        resp = client.get("/auth/me", headers=auth_header("invalid.jwt.token"))
        assert resp.status_code == 401

    def test_malformed_token_on_auth_me(self, client):
        resp = client.get("/auth/me", headers=auth_header("not-a-jwt"))
        assert resp.status_code == 401

    def test_empty_token(self, client):
        resp = client.get("/auth/me", headers=auth_header(""))
        # Empty token is treated as no auth: middleware sets empty user, handler returns 401
        assert resp.status_code == 401

    def test_expired_token(self, client):
        """Test with a manually crafted expired token."""
        import jwt
        from datetime import datetime, timedelta, timezone
        expired_payload = {
            "user_id": 1,
            "email": "test@test.com",
            "role": "user",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
        }
        expired_token = jwt.encode(expired_payload, "ntx-dev-secret-change-in-production",
                                   algorithm="HS256")
        resp = client.get("/auth/me", headers=auth_header(expired_token))
        assert resp.status_code == 401

    def test_login_invalid_password(self, client, seed_data):
        resp = client.post("/users/login", json={
            "email": "alice@example.com",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post("/users/login", json={
            "email": "nobody@nowhere.com",
            "password": "anything",
        })
        assert resp.status_code == 401


class TestForbidden403:
    """403 Forbidden -- authenticated but not authorized."""

    def test_create_product_no_token(self, client):
        resp = client.post("/Product", json={"name": "Test", "price": 10.0})
        assert resp.status_code == 403

    def test_update_comment_non_owner(self, client, charlie_token, seed_data):
        """Comment 0 owned by bob, charlie cannot update."""
        comment = seed_data["comments"][0]
        product = seed_data["products"][0]
        resp = client.put(f"/Product/{product.id}/Comment/{comment.id}", json={
            "name": "Forbidden",
        }, headers=auth_header(charlie_token))
        assert resp.status_code == 403

    def test_delete_comment_non_owner(self, client, charlie_token, seed_data):
        comment = seed_data["comments"][0]
        product = seed_data["products"][0]
        resp = client.delete(f"/Product/{product.id}/Comment/{comment.id}",
                             headers=auth_header(charlie_token))
        assert resp.status_code == 403

    def test_custom_method_no_token(self, client, seed_data):
        product = seed_data["products"][0]
        resp = client.post(f"/Product/{product.id}/favorite", json={})
        assert resp.status_code == 403


class TestUnprocessableEntity422:
    """422 Unprocessable Entity -- validation errors."""

    def test_create_product_missing_required_name(self, client, alice_token):
        resp = client.post("/Product", json={"price": 10.0},
                           headers=auth_header(alice_token))
        assert resp.status_code == 422

    def test_create_product_invalid_price_type(self, client, alice_token):
        resp = client.post("/Product", json={"name": "Test", "price": "not-a-number"},
                           headers=auth_header(alice_token))
        assert resp.status_code == 422

    def test_create_product_negative_price(self, client, alice_token):
        resp = client.post("/Product", json={"name": "Test", "price": -5.0},
                           headers=auth_header(alice_token))
        assert resp.status_code == 422

    def test_create_product_zero_price(self, client, alice_token):
        resp = client.post("/Product", json={"name": "Test", "price": 0},
                           headers=auth_header(alice_token))
        assert resp.status_code == 422

    def test_create_product_name_too_long(self, client, alice_token):
        resp = client.post("/Product", json={"name": "x" * 201, "price": 10.0},
                           headers=auth_header(alice_token))
        assert resp.status_code == 422

    def test_create_product_name_empty(self, client, alice_token):
        resp = client.post("/Product", json={"name": "", "price": 10.0},
                           headers=auth_header(alice_token))
        assert resp.status_code == 422

    def test_pagination_limit_zero(self, client, alice_token):
        resp = client.get("/Product/_?limit=0", headers=auth_header(alice_token))
        assert resp.status_code == 422

    def test_pagination_limit_over_max(self, client, alice_token):
        resp = client.get("/Product/_?limit=101", headers=auth_header(alice_token))
        assert resp.status_code == 422

    def test_pagination_negative_offset(self, client, alice_token):
        resp = client.get("/Product/_?offset=-1", headers=auth_header(alice_token))
        assert resp.status_code == 422


class TestBadRequest400:
    """400 Bad Request -- invalid scaffold type, missing fields in custom methods."""

    def test_invalid_scaffold_type(self, client):
        resp = client.get("/Product?scaffold=nonexistent")
        assert resp.status_code == 400

    def test_custom_method_missing_required_field(self, client, alice_token, seed_data):
        """POST /Product/{id}/comment without comment field should return 400."""
        product = seed_data["products"][0]
        resp = client.post(f"/Product/{product.id}/comment", json={},
                           headers=auth_header(alice_token))
        assert resp.status_code == 400

    def test_reply_missing_text_field(self, client, alice_token, seed_data):
        """POST /Product/{pid}/Comment/{cid}/reply without text field."""
        product = seed_data["products"][0]
        comment = seed_data["comments"][0]
        resp = client.post(f"/Product/{product.id}/Comment/{comment.id}/reply",
                           json={}, headers=auth_header(alice_token))
        assert resp.status_code == 400


class TestConflict409:
    """409 Conflict -- duplicate resources."""

    def test_register_duplicate_email(self, client, seed_data):
        resp = client.post("/users/register", json={
            "name": "Duplicate",
            "email": "alice@example.com",
            "password": "anypass",
        })
        assert resp.status_code == 409


class TestSpecialCharacters:
    """Edge cases with special characters."""

    def test_create_product_with_html_in_name(self, client, alice_token):
        """IT-13: XSS test -- data is stored as-is, verify round-trip."""
        xss_name = "<script>alert('xss')</script>"
        resp = client.post("/Product", json={
            "name": xss_name,
            "price": 10.00,
        }, headers=auth_header(alice_token))
        assert resp.status_code == 201
        product_id = resp.json()["id"]
        # Verify data stored exactly as sent (no sanitization/escaping)
        get_resp = client.get(f"/Product/{product_id}", headers=auth_header(alice_token))
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == xss_name

    def test_create_product_with_unicode(self, client, alice_token):
        resp = client.post("/Product", json={
            "name": "Produit avec accents eaigu",
            "price": 15.00,
            "description": "Ceci est un test avec des caracteres speciaux",
        }, headers=auth_header(alice_token))
        assert resp.status_code == 201

    def test_create_comment_with_empty_description(self, client, alice_token, seed_data):
        product = seed_data["products"][0]
        resp = client.post(f"/Product/{product.id}/Comment", json={
            "name": "No description",
            "description": "",
        }, headers=auth_header(alice_token))
        assert resp.status_code == 201
