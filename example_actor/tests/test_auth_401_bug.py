# test_auth_401_bug.py
"""
Bug: After reseeding the DB, register returns 200 OK but all subsequent
requests return 401 Unauthorized. Token extraction fails because the
expose_route debug envelope wraps the response when DEBUG=True.

Response without debug: {"token": "...", "user": {...}}
Response with debug:    {"data": {"token": "...", "user": {...}}, "_debug": {...}}

Frontend does: data.result || data -> payload.token -> UNDEFINED when wrapped.
"""

import pytest
from helpers import auth_header
from n3tx.core import config as n3tx_config


# ---------------------------------------------------------------------------
# Tests with DEBUG=False (baseline — these pass today)
# ---------------------------------------------------------------------------

class TestRegisterThenUseToken:
    """Register a brand new user via API, then use the returned token."""

    def test_register_returns_valid_token_for_auth_me(self, client):
        """Register, take the token, call /auth/me — should get 200 with user info."""
        resp = client.post("/users/register", json={
            "name": "bugtest",
            "email": "bugtest_register@test.com",
            "password": "testpass123",
        })
        assert resp.status_code == 200, f"Registration failed: {resp.text}"
        data = resp.json()
        assert "token" in data, f"No token in register response: {data}"
        token = data["token"]

        me_resp = client.get("/auth/me", headers=auth_header(token))
        assert me_resp.status_code == 200, (
            f"Expected 200 from /auth/me with fresh register token, got {me_resp.status_code}: {me_resp.text}"
        )
        me_data = me_resp.json()
        assert me_data["email"] == "bugtest_register@test.com"


class TestLoginWithRegisteredCreds:
    """Register a user, then login with the same credentials."""

    def test_login_after_register_succeeds(self, client):
        """Register a user, then login with those exact credentials — should get 200 + token."""
        reg_resp = client.post("/users/register", json={
            "name": "logintest",
            "email": "logintest@test.com",
            "password": "mypassword",
        })
        assert reg_resp.status_code == 200, f"Registration failed: {reg_resp.text}"

        login_resp = client.post("/users/login", json={
            "email": "logintest@test.com",
            "password": "mypassword",
        })
        assert login_resp.status_code == 200, (
            f"Expected 200 from login after register, got {login_resp.status_code}: {login_resp.text}"
        )
        login_data = login_resp.json()
        assert "token" in login_data, f"No token in login response: {login_data}"


class TestLoginWithSeedUsers:
    """Login with seed users that were created via _seed_users()."""

    def test_seed_user_login_succeeds(self, client, seed_data):
        """Alice (seed user) should be able to login with her password."""
        login_resp = client.post("/users/login", json={
            "email": "alice@example.com",
            "password": "alice123",
        })
        assert login_resp.status_code == 200, (
            f"Expected 200 for seed user login, got {login_resp.status_code}: {login_resp.text}"
        )
        data = login_resp.json()
        assert "token" in data

    def test_seed_user_token_accesses_protected_endpoint(self, client, seed_data, alice_token):
        """Seed user token (pre-generated) should access /auth/me."""
        resp = client.get("/auth/me", headers=auth_header(alice_token))
        assert resp.status_code == 200, (
            f"Expected 200 from /auth/me with seed token, got {resp.status_code}: {resp.text}"
        )


# ---------------------------------------------------------------------------
# Tests with DEBUG=True (reproduce the bug)
# ---------------------------------------------------------------------------

class TestDebugEnvelopeTokenExtraction:
    """The expose_route debug wrapper nests the token under 'data' when DEBUG=True.
    The frontend compat logic extracts token from either location:
        token = payload.token || (payload.data && payload.data.token)
    These tests verify the compat extraction works."""

    @staticmethod
    def _extract_token(data):
        """Compat extraction — mirrors the frontend logic.
        TODO: remove once responses use TX-based wire format."""
        payload = data.get('result') or data
        return payload.get('token') or (
            payload.get('data', {}).get('token')
            if isinstance(payload.get('data'), dict) else None
        )

    def test_register_token_extractable_with_debug(self, client, monkeypatch):
        """Register response token must be extractable via compat path when DEBUG=True."""
        monkeypatch.setattr(n3tx_config, 'DEBUG', True)

        resp = client.post("/users/register", json={
            "name": "debugtest",
            "email": "debugtest@test.com",
            "password": "testpass123",
        })
        assert resp.status_code == 200, f"Registration failed: {resp.text}"
        data = resp.json()

        token = self._extract_token(data)
        assert token is not None, (
            f"Token not extractable via compat path. Response keys: {list(data.keys())}."
        )

    def test_login_token_extractable_with_debug(self, client, seed_data, monkeypatch):
        """Login response token must be extractable via compat path when DEBUG=True."""
        monkeypatch.setattr(n3tx_config, 'DEBUG', True)

        resp = client.post("/users/login", json={
            "email": "alice@example.com",
            "password": "alice123",
        })
        assert resp.status_code == 200, f"Login failed: {resp.text}"
        data = resp.json()

        token = self._extract_token(data)
        assert token is not None, (
            f"Token not extractable via compat path. Response keys: {list(data.keys())}."
        )

    def test_token_from_debug_register_works_for_auth_me(self, client, monkeypatch):
        """Token extracted via compat path (DEBUG=True) must work for /auth/me."""
        monkeypatch.setattr(n3tx_config, 'DEBUG', True)

        resp = client.post("/users/register", json={
            "name": "tokentest",
            "email": "tokentest@test.com",
            "password": "pass123",
        })
        assert resp.status_code == 200
        data = resp.json()

        token = self._extract_token(data)
        assert token is not None, f"No token in response: {data}"
        assert token != 'undefined', f"Token is the string 'undefined'"

        me_resp = client.get("/auth/me", headers=auth_header(token))
        assert me_resp.status_code == 200, (
            f"Token from register doesn't work for /auth/me: {me_resp.status_code} {me_resp.text}"
        )


class TestLoginAfterRegisterWithDebug:
    """Register then login flow with DEBUG=True."""

    def test_login_with_registered_creds_debug_mode(self, client, monkeypatch):
        """Register, then login with same creds — both must return usable tokens via compat path."""
        monkeypatch.setattr(n3tx_config, 'DEBUG', True)

        # Register
        client.post("/users/register", json={
            "name": "flowtest",
            "email": "flowtest@test.com",
            "password": "flowpass",
        })

        # Login
        login_resp = client.post("/users/login", json={
            "email": "flowtest@test.com",
            "password": "flowpass",
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        data = login_resp.json()

        # Extract token via compat path (same as frontend)
        # TODO: simplify once responses use TX-based wire format
        payload = data.get('result') or data
        token = payload.get('token') or (
            payload.get('data', {}).get('token')
            if isinstance(payload.get('data'), dict) else None
        )
        assert token is not None, f"No token extractable from login response: {data}"

        # Verify token works
        me_resp = client.get("/auth/me", headers=auth_header(token))
        assert me_resp.status_code == 200, (
            f"Login token doesn't work: {me_resp.status_code}"
        )
