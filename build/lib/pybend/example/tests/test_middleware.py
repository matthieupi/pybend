# tests/test_middleware.py
"""
Test Plan Section 15: Middleware
Tests JWT authentication middleware and CORS middleware.
"""

import pytest
from pybend.example.tests.helpers import auth_header

pytestmark = pytest.mark.integration



class TestJWTMiddleware:
    """JWT Authentication Middleware behavior."""

    def test_schema_endpoint_no_auth_needed(self, client):
        """Schema endpoints (GET /{ClassName}) should not require auth."""
        resp = client.get("/Product")
        assert resp.status_code == 200

    def test_schema_endpoint_with_token_works(self, client, alice_token):
        """Schema endpoints should also work WITH a token."""
        resp = client.get("/Product", headers=auth_header(alice_token))
        assert resp.status_code == 200

    def test_login_exempt_from_auth(self, client, seed_data):
        """Login endpoint should not require auth."""
        resp = client.post("/users/login", json={
            "email": "alice@example.com",
            "password": "alice123",
        })
        assert resp.status_code == 200

    def test_register_exempt_from_auth(self, client):
        """Register endpoint should not require auth."""
        resp = client.post("/users/register", json={
            "name": "middleware_test",
            "email": "middleware@test.com",
            "password": "pass123",
        })
        assert resp.status_code == 200  # IT-1: @expose_route returns 200

    def test_invalid_token_returns_401_before_handler(self, client):
        """Invalid token should be caught by middleware, returning 401."""
        resp = client.get("/auth/me", headers=auth_header("invalid.jwt"))
        assert resp.status_code == 401
        data = resp.json()
        assert "detail" in data

    def test_expired_token_caught_by_middleware(self, client):
        """Expired token should return 401."""
        import jwt
        from datetime import datetime, timedelta, timezone
        import config
        expired_payload = {
            "user_id": 1,
            "email": "expired@test.com",
            "role": "user",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
        }
        token = jwt.encode(expired_payload, config.JWT_SECRET, algorithm="HS256")
        resp = client.get("/auth/me", headers=auth_header(token))
        assert resp.status_code == 401

    def test_valid_token_passes_middleware(self, client, alice_token):
        """Valid token passes middleware and reaches the handler."""
        resp = client.get("/auth/me", headers=auth_header(alice_token))
        assert resp.status_code == 200

    def test_no_token_passes_middleware_but_handler_may_reject(self, client):
        """No token: middleware sets empty user, handler decides access."""
        # /auth/me requires authentication and returns 401
        resp = client.get("/auth/me")
        assert resp.status_code == 401

    def test_no_token_on_public_endpoint(self, client, seed_data):
        """Public endpoint (Comment read = ANYONE) should work without token."""
        product = seed_data["products"][0]
        comment = seed_data["comments"][0]
        resp = client.get(f"/products/{product.id}/comments/{comment.id}")
        assert resp.status_code == 200


class TestCORSMiddleware:
    """CORS configuration verification (IT-15: assert actual CORS headers)."""

    def test_cors_headers_on_response(self, client):
        """Responses should include CORS headers when Origin is sent."""
        resp = client.get("/Product", headers={"origin": "http://localhost:3000"})
        assert resp.status_code == 200
        # CORSMiddleware should set access-control-allow-origin
        acao = resp.headers.get("access-control-allow-origin")
        assert acao is not None, "Missing access-control-allow-origin header"
        assert acao in ("*", "http://localhost:3000")

    def test_options_preflight(self, client):
        """OPTIONS preflight should return CORS headers."""
        resp = client.options("/products", headers={
            "origin": "http://localhost:3000",
            "access-control-request-method": "POST",
        })
        assert resp.status_code in (200, 204)
        # Should have CORS headers
        acao = resp.headers.get("access-control-allow-origin")
        assert acao is not None, "Missing access-control-allow-origin on preflight"


class TestMiddlewareExemptPaths:
    """Verify paths exempt from auth middleware processing."""

    def test_openapi_json_accessible(self, client):
        resp = client.get("/openapi.json")
        assert resp.status_code == 200

    def test_docs_accessible(self, client):
        resp = client.get("/docs")
        # FastAPI serves docs page or redirects to /docs/
        assert resp.status_code in (200, 307, 301)
