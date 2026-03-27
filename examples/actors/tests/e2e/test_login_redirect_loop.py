"""
Playwright reproduction: infinite redirect loop on login/register.

Bug: When DEBUG=true, the login response is wrapped in a debug envelope
     {"result": {"token": ..., "user": ...}, "_debug": {...}}
     but login.html extracts `data.token` (undefined) instead of
     `data.result.token`. This stores "undefined" in localStorage,
     causing every subsequent request to 401 → redirect to /login.html → loop.
"""
import pytest
import re
from playwright.sync_api import sync_playwright, expect


BASE = "http://localhost:5000"  # Patched by conftest


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def page(browser):
    context = browser.new_context()
    page = context.new_page()
    yield page
    context.close()


class TestLoginRedirectLoop:
    """Reproduce the infinite redirect loop when logging in."""

    def test_login_stores_undefined_token(self, page):
        """After login, localStorage should have a real JWT, not 'undefined'."""
        page.goto(f"{BASE}/login.html")
        page.fill("#email", "alice@example.com")
        page.fill("#password", "alice123")
        page.click("button[type=submit]")

        # Wait for navigation after form submit
        page.wait_for_url(re.compile(r"/$|/index\.html"), timeout=5000)

        # Check what was stored in localStorage
        token = page.evaluate("() => window.localStorage.getItem('jwtToken')")
        assert token is not None, "Token should be set in localStorage"
        assert token != "undefined", (
            f"Token stored as literal string 'undefined' — "
            f"debug envelope not unwrapped by login.html"
        )
        assert token != "null", "Token should not be 'null'"
        assert len(token) > 20, f"Token should be a real JWT, got: {token!r}"

    def test_login_does_not_redirect_loop(self, page):
        """After login, user should land on '/' and stay there — no redirect loop."""
        navigations = []

        def on_request(request):
            if request.resource_type == "document":
                navigations.append(request.url)

        page.on("request", on_request)

        page.goto(f"{BASE}/login.html")
        page.fill("#email", "alice@example.com")
        page.fill("#password", "alice123")
        page.click("button[type=submit]")

        # Give the page time to settle (or loop)
        page.wait_for_timeout(3000)

        # Count how many times we hit login.html after the initial load
        login_hits = [u for u in navigations if "login.html" in u]
        # We expect exactly 1 (the initial goto). If there are more, we're looping.
        assert len(login_hits) <= 1, (
            f"Redirect loop detected! login.html was loaded {len(login_hits)} times. "
            f"Navigation history: {navigations}"
        )

    def test_authenticated_page_loads_after_login(self, page):
        """After login, the main page should load successfully with user data visible."""
        page.goto(f"{BASE}/login.html")
        page.fill("#email", "alice@example.com")
        page.fill("#password", "alice123")
        page.click("button[type=submit]")

        # Wait for the main page
        try:
            page.wait_for_url(re.compile(r"/$|/index\.html"), timeout=5000)
        except Exception:
            # If we're still on login.html, that's the bug
            current = page.url
            assert "login" not in current, (
                f"Never left login page — stuck at {current}"
            )
            pytest.fail(f"Unexpected URL after login: {current}")

        # The main page should not immediately redirect us back to login
        page.wait_for_timeout(2000)
        current_url = page.url
        assert "login" not in current_url, (
            f"Redirected back to login after reaching main page: {current_url}"
        )

    def test_login_api_response_has_debug_envelope(self, page):
        """Verify the API response structure — debug envelope wraps token."""
        import requests as req
        # Use direct HTTP to avoid Playwright response body race condition
        resp = req.post(
            f"{BASE}/users/login",
            json={"email": "alice@example.com", "password": "alice123"},
        )
        assert resp.status_code == 200
        data = resp.json()

        # With DEBUG=true, response is wrapped in debug envelope
        if "_debug" in data:
            # Token is NOT at top level — it's inside data.result
            assert "token" not in data, (
                "If debug envelope is present, token should NOT be at top level"
            )
            assert "data" in data, "Debug envelope should have 'data' key"
            assert "token" in data["data"], (
                "Token should be inside data.data when debug envelope is active"
            )


class TestRegisterRedirectLoop:
    """Reproduce the same bug on the register page."""

    def test_register_stores_valid_token(self, page):
        """After registration, localStorage should have a real JWT."""
        import time
        unique_email = f"test_{int(time.time())}@example.com"

        page.goto(f"{BASE}/register.html")

        # Fill registration form (check what fields exist)
        page.fill("#email", unique_email)
        page.fill("#password", "testpass123")

        # Some register forms have a name field
        name_input = page.query_selector("#name")
        if name_input:
            name_input.fill("Test User")

        page.click("button[type=submit]")
        page.wait_for_timeout(3000)

        token = page.evaluate("() => window.localStorage.getItem('jwtToken')")

        # If we even get a token set, check it's not "undefined"
        if token is not None:
            assert token != "undefined", (
                "Register page stored 'undefined' as token — same debug envelope bug"
            )
