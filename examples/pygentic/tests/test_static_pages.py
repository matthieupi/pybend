"""Tests for static HTML pages — login.html and register.html must be served."""
import pytest

pytestmark = pytest.mark.integration


class TestLoginPage:
    """The /login.html route must return a valid HTML page, not 404."""

    def test_login_html_returns_200(self, client):
        """GET /login.html should return 200, not 404."""
        resp = client.get('/login.html')
        assert resp.status_code == 200, (
            f'Expected 200 for /login.html, got {resp.status_code}: {resp.text[:200]}'
        )

    def test_login_html_is_html_content(self, client):
        """GET /login.html should return HTML content, not JSON error."""
        resp = client.get('/login.html')
        assert resp.status_code == 200
        content_type = resp.headers.get('content-type', '')
        assert 'text/html' in content_type, (
            f'Expected text/html content-type, got: {content_type}'
        )
        assert '<!DOCTYPE html>' in resp.text or '<html' in resp.text, (
            'Response body does not look like HTML'
        )

    def test_login_html_has_login_form(self, client):
        """GET /login.html should contain a login form with email/password fields."""
        resp = client.get('/login.html')
        assert resp.status_code == 200
        body = resp.text.lower()
        assert 'email' in body, 'Login page should contain an email field'
        assert 'password' in body, 'Login page should contain a password field'


class TestRegisterPage:
    """The /register.html route must return a valid HTML page, not 404."""

    def test_register_html_returns_200(self, client):
        """GET /register.html should return 200, not 404."""
        resp = client.get('/register.html')
        assert resp.status_code == 200, (
            f'Expected 200 for /register.html, got {resp.status_code}: {resp.text[:200]}'
        )


class TestIndexPage:
    """The /index.html route (which already exists) should continue to work."""

    def test_index_html_returns_200(self, client):
        """GET /index.html should return 200 — baseline sanity check."""
        resp = client.get('/index.html')
        assert resp.status_code == 200, (
            f'Expected 200 for /index.html, got {resp.status_code}: {resp.text[:200]}'
        )
