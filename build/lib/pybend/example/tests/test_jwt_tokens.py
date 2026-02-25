# tests/test_jwt_tokens.py
"""
Test Plan Section 13: Token & JWT Handling
Tests create_token, decode_token, header extraction, user resolution.
"""

import pytest
import jwt
from datetime import datetime, timedelta, timezone
from pybend.example.tests.helpers import auth_header

pytestmark = pytest.mark.integration



class TestCreateToken:
    """authorize.create_token() -- JWT creation."""

    def test_create_token_returns_string(self):
        from pybend.core.authorize import create_token
        token = create_token(user_id=1, email="test@test.com", role="user")
        assert isinstance(token, str)

    def test_create_token_has_required_claims(self):
        from pybend.core.authorize import create_token, decode_token
        token = create_token(user_id=42, email="claims@test.com", role="admin")
        payload = decode_token(token)
        assert payload["user_id"] == 42
        assert payload["email"] == "claims@test.com"
        assert payload["role"] == "admin"
        assert "exp" in payload
        assert "iat" in payload

    def test_create_token_uses_hs256(self):
        from pybend.core.authorize import create_token
        import config
        token = create_token(user_id=1, email="algo@test.com", role="user")
        # Decode without verification to check header
        header = jwt.get_unverified_header(token)
        assert header["alg"] == "HS256"


class TestDecodeToken:
    """authorize.decode_token() -- JWT validation."""

    def test_decode_valid_token(self):
        from pybend.core.authorize import create_token, decode_token
        token = create_token(user_id=10, email="valid@test.com", role="user")
        payload = decode_token(token)
        assert payload["user_id"] == 10
        assert payload["email"] == "valid@test.com"

    def test_decode_expired_token_raises(self):
        import config
        expired_payload = {
            "user_id": 1,
            "email": "expired@test.com",
            "role": "user",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
        }
        token = jwt.encode(expired_payload, config.JWT_SECRET, algorithm="HS256")
        from pybend.core.authorize import decode_token
        with pytest.raises(jwt.ExpiredSignatureError):
            decode_token(token)

    def test_decode_invalid_signature_raises(self):
        token = jwt.encode({"user_id": 1}, "wrong-secret", algorithm="HS256")
        from pybend.core.authorize import decode_token
        with pytest.raises(jwt.InvalidSignatureError):
            decode_token(token)


class TestTokenHeaderExtraction:
    """x-access-token header processing by middleware."""

    def test_valid_token_sets_user_state(self, client, alice_token):
        """Middleware should decode token and set request.state.user."""
        resp = client.get("/auth/me", headers=auth_header(alice_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "alice@example.com"

    def test_no_token_sets_empty_user(self, client):
        """No token means request.state.user is empty dict."""
        resp = client.get("/auth/me")
        # /auth/me explicitly checks for user, returns 401
        assert resp.status_code == 401

    def test_invalid_token_returns_401(self, client):
        """Invalid JWT in header should return 401 from middleware."""
        resp = client.get("/auth/me", headers=auth_header("garbage-token"))
        assert resp.status_code == 401


class TestUserParameterResolution:
    """_resolve_user() bridge: JWT dict -> model instance."""

    def test_user_resolved_in_custom_method(self, client, alice_token, seed_data):
        """Comment method receives user: User which should be resolved from JWT."""
        product = seed_data["products"][0]
        import json
        resp = client.post(f"/products/{product.id}/comment", json={
            "comment": {"name": "User resolve", "description": "test"},
        }, headers=auth_header(alice_token))
        assert resp.status_code == 200
        data = resp.json()
        if isinstance(data, str):
            data = json.loads(data)
        # user_owner should be alice's ID (resolved from User model)
        alice = seed_data["users"]["alice"]
        user_owner = data.get("user_owner")
        if isinstance(user_owner, str) and "/" in user_owner:
            user_owner = int(user_owner.rstrip("/").rsplit("/", 1)[-1])
        assert user_owner == alice.id

    def test_user_resolved_in_favorite(self, client, alice_token, seed_data):
        """Favorite method receives user: User to check existing likes."""
        product = seed_data["products"][3]
        import json
        resp = client.post(f"/products/{product.id}/favorite",
                           json={}, headers=auth_header(alice_token))
        assert resp.status_code == 200
        data = resp.json()
        if isinstance(data, str):
            data = json.loads(data)
        assert "action" in data


class TestPasswordHashing:
    """authorize.hash_password() / verify_password()."""

    def test_hash_password_returns_bcrypt_string(self):
        from pybend.core.authorize import hash_password
        hashed = hash_password("testpassword")
        assert isinstance(hashed, str)
        assert hashed.startswith("$2")

    def test_verify_password_correct(self):
        from pybend.core.authorize import hash_password, verify_password
        hashed = hash_password("mypass123")
        assert verify_password("mypass123", hashed) is True

    def test_verify_password_incorrect(self):
        from pybend.core.authorize import hash_password, verify_password
        hashed = hash_password("correct")
        assert verify_password("wrong", hashed) is False

    def test_hash_is_unique_per_call(self):
        from pybend.core.authorize import hash_password
        h1 = hash_password("same")
        h2 = hash_password("same")
        # bcrypt generates unique salts
        assert h1 != h2
