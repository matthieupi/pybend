"""
Tests for login/register page availability in example_chat.

Bug: GET /login.html returns 404 Not Found, breaking the auth redirect flow.
Other examples (example_actor, example_grants) serve login.html correctly.
"""


def test_login_html_returns_200(client):
    """Login page must be served as static HTML."""
    resp = client.get("/login.html")
    assert resp.status_code == 200, f"Expected 200 for /login.html, got {resp.status_code}"


def test_register_html_returns_200(client):
    """Register page must be served as static HTML."""
    resp = client.get("/register.html")
    assert resp.status_code == 200, f"Expected 200 for /register.html, got {resp.status_code}"


def test_login_html_contains_form(client):
    """Login page must contain a login form with email and password fields."""
    resp = client.get("/login.html")
    assert resp.status_code == 200
    body = resp.text
    assert "email" in body.lower(), "Login page should contain an email field"
    assert "password" in body.lower(), "Login page should contain a password field"


def test_index_html_returns_200(client):
    """Index page must be served as static HTML."""
    resp = client.get("/")
    assert resp.status_code == 200


def test_authenticated_conversations_returns_200(client, alice_token):
    """Authenticated request to conversations should succeed."""
    resp = client.get(
        "/conversations?limit=20&offset=0",
        headers={"x-access-token": alice_token},
    )
    assert resp.status_code == 200
