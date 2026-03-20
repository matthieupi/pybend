"""Playwright e2e tests: method button clicks should NOT navigate away from list.

Bug: Clicking a method button (like, favorite) on a card in list view
propagates the click event to the card, which triggers navigation to the
detail page. Edit/delete/confirm buttons work correctly (they stop
propagation), but method buttons do not.

Validates:
  1. Clicking a like button on a card does NOT change the URL hash
  2. Clicking a favorite button on a card does NOT navigate to detail view
  3. After clicking a method button, the list view remains visible
  4. The method's POST request still fires successfully (action works)
"""
from playwright.sync_api import sync_playwright

BASE = "http://localhost:5000"


def _login(page, email="alice@example.com", password="alice123"):
    """Log in via API and inject token into localStorage."""
    resp = page.request.post(f"{BASE}/users/login", data={
        "email": email, "password": password,
    })
    body = resp.json()
    # Response may wrap in data envelope: {data: {token: ...}} or {token: ...}
    token = body.get("token") or (body.get("data") or {}).get("token")
    assert token, f"Login failed: {body}"
    page.evaluate(f"() => localStorage.setItem('jwtToken', '{token}')")
    return token


def _wait_for_list_items(page, timeout=10000):
    """Wait until ntx-list has at least one ntx-item rendered with a card."""
    page.wait_for_function("""() => {
        const lists = document.querySelectorAll('ntx-list');
        for (const list of lists) {
            const grid = list.shadowRoot?.querySelector('.list-grid');
            if (!grid) continue;
            const items = grid.querySelectorAll('ntx-item');
            if (items.length === 0) continue;
            // Check first item has rendered its card
            if (items[0].shadowRoot?.querySelector('.card')) return true;
        }
        return false;
    }""", timeout=timeout)


def _find_method_button(page, method_name):
    """Find the first ntx-method button in a list view, traversing shadow DOMs.
    Returns {model, uuid, listVisible} or None."""
    return page.evaluate("""(method) => {
        function findInShadow(root, depth = 0) {
            if (depth > 10) return null;
            for (const el of root.querySelectorAll(`ntx-method[method="${method}"]`)) {
                const btn = el.shadowRoot?.querySelector('.method-btn');
                if (!btn) continue;
                return {
                    model: el.getAttribute('model'),
                    uuid: el.getAttribute('uuid'),
                };
            }
            for (const el of root.querySelectorAll('*')) {
                if (el.shadowRoot) {
                    const r = findInShadow(el.shadowRoot, depth + 1);
                    if (r) return r;
                }
            }
            return null;
        }
        return findInShadow(document);
    }""", method_name)


def _click_method_button(page, method_name, uuid):
    """Click a specific ntx-method button inside nested shadow DOMs."""
    return page.evaluate("""(args) => {
        function findInShadow(root, depth = 0) {
            if (depth > 10) return null;
            for (const el of root.querySelectorAll(`ntx-method[method="${args.method}"]`)) {
                if (el.getAttribute('uuid') === args.uuid) {
                    const btn = el.shadowRoot?.querySelector('.method-btn');
                    if (btn) { btn.click(); return 'clicked'; }
                    return 'no-btn';
                }
            }
            for (const el of root.querySelectorAll('*')) {
                if (el.shadowRoot) {
                    const r = findInShadow(el.shadowRoot, depth + 1);
                    if (r) return r;
                }
            }
            return null;
        }
        return findInShadow(document) || 'not-found';
    }""", {"method": method_name, "uuid": uuid})


def _is_list_visible(page):
    """Check if a list view (ntx-list with items) is currently visible."""
    return page.evaluate("""() => {
        const lists = document.querySelectorAll('ntx-list');
        for (const list of lists) {
            const grid = list.shadowRoot?.querySelector('.list-grid');
            if (!grid) continue;
            if (grid.querySelectorAll('ntx-item').length > 0) return true;
        }
        return false;
    }""")


# ─── Test 1: Like button click must NOT navigate ───

def test_like_button_click_does_not_navigate():
    """Clicking the like button on a product card should NOT change the URL hash.

    The like button is inside an ntx-method component inside an ntx-item card.
    The card has a click handler that navigates to the detail view. The method
    button click must not propagate to the card.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(BASE)
        _login(page)
        page.reload()
        _wait_for_list_items(page)

        # Get hash before clicking
        hash_before = page.evaluate("() => location.hash")
        assert hash_before == "" or hash_before == "#", \
            f"Expected no hash before click, got {hash_before}"

        # Find and click the like button
        btn = _find_method_button(page, "like")
        assert btn is not None, "No like button found in list view"
        result = _click_method_button(page, "like", btn["uuid"])
        assert result == "clicked", f"Failed to click like button: {result}"

        # Wait for any navigation to happen (if the bug exists)
        page.wait_for_timeout(2000)

        # Assert: URL hash should NOT have changed to a detail view
        hash_after = page.evaluate("() => location.hash")
        assert not hash_after.startswith("#"), \
            f"BUG: Clicking like button navigated to {hash_after} — event propagated to card"

        browser.close()


# ─── Test 2: Favorite button click must NOT navigate ───

def test_favorite_button_click_does_not_navigate():
    """Clicking the favorite button on a product card should NOT navigate away.

    Same propagation bug as like, but tests a different method button to
    confirm the issue is systemic across all ntx-method components, not
    specific to one method.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(BASE)
        _login(page)
        page.reload()
        _wait_for_list_items(page)

        hash_before = page.evaluate("() => location.hash")

        btn = _find_method_button(page, "favorite")
        assert btn is not None, "No favorite button found in list view"
        result = _click_method_button(page, "favorite", btn["uuid"])
        assert result == "clicked", f"Failed to click favorite button: {result}"

        page.wait_for_timeout(2000)

        hash_after = page.evaluate("() => location.hash")
        assert not hash_after.startswith("#"), \
            f"BUG: Clicking favorite button navigated to {hash_after} — event propagated to card"

        browser.close()


# ─── Test 3: List view must remain visible after method click ───

def test_list_view_stays_visible_after_method_click():
    """After clicking a method button, the list view should still be visible.

    When the bug occurs, the router replaces the list with a detail view.
    This test verifies the list remains visible after clicking a method button.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(BASE)
        _login(page)
        page.reload()
        _wait_for_list_items(page)

        # Confirm list is visible before click
        assert _is_list_visible(page), "List should be visible before clicking"

        # Click a method button
        btn = _find_method_button(page, "like")
        if btn is None:
            btn = _find_method_button(page, "favorite")
        assert btn is not None, "No method button found in list view"

        method = "like" if _find_method_button(page, "like") else "favorite"
        result = _click_method_button(page, method, btn["uuid"])
        assert result == "clicked", f"Failed to click button: {result}"

        page.wait_for_timeout(2000)

        # The list view should still be visible — not replaced by detail
        still_visible = _is_list_visible(page)
        assert still_visible, \
            "BUG: List view disappeared after clicking method button — " \
            "click event propagated to card, triggering navigation to detail view"

        browser.close()


# ─── Test 4: Method POST request fires despite propagation ───

def test_method_action_executes_on_click():
    """Clicking a method button should execute the method's POST action.

    Even with the propagation bug, we want to verify the method call itself
    fires. This test captures the POST response to confirm the action went through.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})

        # Track POST responses
        method_response = {}
        def on_response(resp):
            if resp.request.method == "POST" and "/like" in resp.url:
                try:
                    method_response["status"] = resp.status
                    method_response["body"] = resp.json()
                except:
                    method_response["status"] = resp.status
        page.on("response", on_response)

        page.goto(BASE)
        _login(page)
        page.reload()
        _wait_for_list_items(page)

        btn = _find_method_button(page, "like")
        assert btn is not None, "No like button found"
        _click_method_button(page, "like", btn["uuid"])

        page.wait_for_timeout(3000)

        # The method POST should have fired
        assert "status" in method_response, \
            "Method POST request did not fire when clicking the button"
        assert method_response["status"] == 200, \
            f"Method POST returned {method_response['status']}, expected 200"

        # AND the page should still show the list (no navigation)
        hash_after = page.evaluate("() => location.hash")
        assert not hash_after.startswith("#"), \
            f"BUG: Method fired but also navigated to {hash_after}"

        browser.close()
