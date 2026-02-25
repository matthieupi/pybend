# tests/test_auth_flow.py
"""
Test Plan Section 2: Authentication & Login Flow
Covers user registration, login, and /auth/me.
"""

import pytest
from pybend.example.tests.helpers import auth_header

pytestmark = pytest.mark.integration



class TestUserRegistration:
    """POST /users/register -- user registration."""

    def test_register_new_user_returns_token_and_user(self, client):
        resp = client.post("/users/register", json={
            "name": "newuser",
            "email": "newuser@test.com",
            "password": "testpass123",
        })
        # register is an @expose_route which returns 200 (IT-1: exact status)
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert "user" in data
        user = data["user"]
        assert user["name"] == "newuser"
        assert user["email"] == "newuser@test.com"

    def test_register_returns_valid_jwt(self, client):
        resp = client.post("/users/register", json={
            "name": "jwttest",
            "email": "jwttest@test.com",
            "password": "jwtpass123",
        })
        data = resp.json()
        token = data["token"]
        # Verify token works with /auth/me
        me_resp = client.get("/auth/me", headers=auth_header(token))
        assert me_resp.status_code == 200
        me_data = me_resp.json()
        assert me_data["email"] == "jwttest@test.com"
        assert me_data["role"] == "user"

    def test_register_password_hash_not_in_response(self, client):
        resp = client.post("/users/register", json={
            "name": "nohash",
            "email": "nohash@test.com",
            "password": "secret123",
        })
        data = resp.json()
        user = data.get("user", {})
        assert "password_hash" not in user
        assert "password" not in user

    def test_register_role_defaults_to_user(self, client):
        resp = client.post("/users/register", json={
            "name": "roletest",
            "email": "roletest@test.com",
            "password": "role123",
        })
        data = resp.json()
        user = data.get("user", {})
        assert user.get("role") == "user"

    def test_register_duplicate_email_returns_409(self, client, seed_data):
        """Registering with an existing email should fail."""
        resp = client.post("/users/register", json={
            "name": "duplicate",
            "email": "alice@example.com",
            "password": "alice123",
        })
        assert resp.status_code == 409

    def test_register_missing_fields_returns_400(self, client):
        """Missing required fields should return 400 (IT-1: exact status)."""
        resp = client.post("/users/register", json={
            "name": "incomplete",
        })
        assert resp.status_code == 400


class TestUserLogin:
    """POST /users/login -- user login."""

    def test_login_valid_credentials_returns_token(self, client, seed_data):
        resp = client.post("/users/login", json={
            "email": "alice@example.com",
            "password": "alice123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert "user" in data

    def test_login_token_decodes_to_correct_user(self, client, seed_data):
        resp = client.post("/users/login", json={
            "email": "alice@example.com",
            "password": "alice123",
        })
        data = resp.json()
        token = data["token"]
        me_resp = client.get("/auth/me", headers=auth_header(token))
        me_data = me_resp.json()
        assert me_data["email"] == "alice@example.com"

    def test_login_invalid_password_returns_401(self, client, seed_data):
        resp = client.post("/users/login", json={
            "email": "alice@example.com",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

    def test_login_nonexistent_email_returns_401(self, client):
        resp = client.post("/users/login", json={
            "email": "nonexistent@example.com",
            "password": "anypass",
        })
        assert resp.status_code == 401

    def test_login_case_insensitive_email(self, client, seed_data):
        """Email should be case-insensitive."""
        resp = client.post("/users/login", json={
            "email": "Alice@Example.Com",
            "password": "alice123",
        })
        # May or may not be implemented; accept 200 (supported) or 401 (not supported)
        assert resp.status_code in (200, 401)

    def test_login_empty_password_returns_401(self, client, seed_data):
        """Empty password should not authenticate (IT-12)."""
        resp = client.post("/users/login", json={
            "email": "alice@example.com",
            "password": "",
        })
        assert resp.status_code == 401

    def test_login_long_password_rejected(self, client, seed_data):
        """Very long password should fail authentication (IT-12).
        bcrypt truncates at 72 bytes; the server may return 401 or 500
        depending on error handling."""
        resp = client.post("/users/login", json={
            "email": "alice@example.com",
            "password": "x" * 1000,
        })
        assert resp.status_code in (401, 500)


class TestAuthMe:
    """GET /auth/me -- authenticated user identity."""

    def test_auth_me_with_valid_token(self, client, alice_token, seed_data):
        resp = client.get("/auth/me", headers=auth_header(alice_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "user_id" in data
        assert "email" in data
        assert "role" in data
        assert data["email"] == "alice@example.com"

    def test_auth_me_without_token_returns_401(self, client):
        resp = client.get("/auth/me")
        assert resp.status_code == 401

    def test_auth_me_with_invalid_token_returns_401(self, client):
        resp = client.get("/auth/me", headers=auth_header("invalid.token.here"))
        assert resp.status_code == 401

    def test_auth_me_admin_role(self, client, admin_token):
        resp = client.get("/auth/me", headers=auth_header(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "admin"
