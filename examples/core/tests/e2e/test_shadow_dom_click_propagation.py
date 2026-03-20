"""Playwright e2e tests: click propagation through nested shadow DOM.

Bug: When a custom element with interactive content in its shadow DOM
(like ntx-agent-live with textarea/button) is rendered inside an ntx-item
card in a list, clicking on the interactive content causes navigation to
the detail page because:

1. The card click handler uses e.target.closest() to check for interactive elements
2. e.target is retargeted to the custom element's host (e.g. ntx-agent-live)
3. The host element doesn't match any selector in the guard list
4. The click propagates to the card handler, triggering SELECT → navigation

Edit, delete and cancel buttons work because they use stopPropagation().
ntx-method and ntx-stream work because they ARE in the guard selector list.
But any other custom element with interactive shadow DOM content is NOT guarded.

This reproduces the ntx-agent-live bug reported in the pygentic/agentics example.
"""
from playwright.sync_api import sync_playwright

BASE = "http://localhost:5000"


def _login(page, email="alice@example.com", password="alice123"):
    """Log in via API and inject token into localStorage."""
    resp = page.request.post(f"{BASE}/users/login", data={
        "email": email, "password": password,
    })
    body = resp.json()
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
            if (items[0].shadowRoot?.querySelector('.card')) return true;
        }
        return false;
    }""", timeout=timeout)


def _inject_interactive_element(page):
    """Inject a custom element with interactive shadow DOM into a card.

    Simulates what ntx-agent-live does: a custom element with textarea
    and button inside its shadow root, embedded inside an ntx-item card.
    """
    return page.evaluate("""() => {
        // Define a test custom element with interactive shadow DOM content
        if (!customElements.get('test-interactive-widget')) {
            class TestWidget extends HTMLElement {
                connectedCallback() {
                    this.attachShadow({mode: 'open'});
                    this.shadowRoot.innerHTML = `
                        <div class="widget-panel">
                            <textarea placeholder="Enter task..." rows="2"></textarea>
                            <button class="widget-btn">Run</button>
                        </div>
                    `;
                    // Bind handlers (same as ntx-agent-live)
                    this.shadowRoot.querySelector('.widget-btn').addEventListener('click', () => {
                        // action handler — does NOT stopPropagation (same as ntx-agent-live)
                    });
                }
            }
            customElements.define('test-interactive-widget', TestWidget);
        }

        // Find the first card in a list and inject the widget
        const lists = document.querySelectorAll('ntx-list');
        for (const list of lists) {
            const grid = list.shadowRoot?.querySelector('.list-grid');
            if (!grid) continue;
            const item = grid.querySelector('ntx-item');
            if (!item) continue;
            const card = item.shadowRoot?.querySelector('.card');
            if (!card) continue;
            // Verify this item has select-target (will trigger navigation)
            if (!item.getAttribute('select-target')) continue;
            const el = document.createElement('test-interactive-widget');
            card.appendChild(el);
            return {
                injected: true,
                selectTarget: item.getAttribute('select-target'),
            };
        }
        return { injected: false };
    }""")


# ─── Test 1: Textarea click inside custom element shadow DOM ───

def test_textarea_in_custom_element_shadow_dom_does_not_navigate():
    """Clicking a textarea inside a custom element's shadow DOM within a card
    should NOT trigger navigation. This reproduces the ntx-agent-live bug.

    The card click guard uses e.target.closest() which sees the custom element
    host (not the textarea inside shadow DOM). If the host isn't in the guard's
    selector list, the click propagates and triggers navigation.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(BASE)
        _login(page)
        page.reload()
        _wait_for_list_items(page)

        # Inject widget into card
        result = _inject_interactive_element(page)
        assert result["injected"], "Failed to inject test widget into a card"

        hash_before = page.evaluate("() => location.hash")

        # Click on the textarea inside the widget's shadow DOM
        click_result = page.evaluate("""() => {
            const lists = document.querySelectorAll('ntx-list');
            for (const list of lists) {
                const grid = list.shadowRoot?.querySelector('.list-grid');
                if (!grid) continue;
                const item = grid.querySelector('ntx-item');
                if (!item) continue;
                const widget = item.shadowRoot?.querySelector('test-interactive-widget');
                if (!widget) continue;
                const textarea = widget.shadowRoot?.querySelector('textarea');
                if (textarea) {
                    textarea.click();
                    return 'clicked';
                }
            }
            return 'not-found';
        }""")
        assert click_result == "clicked", f"Could not click textarea: {click_result}"

        page.wait_for_timeout(2000)

        hash_after = page.evaluate("() => location.hash")
        assert not hash_after.startswith("#"), \
            f"BUG: Clicking textarea inside custom element's shadow DOM " \
            f"navigated to {hash_after} — event propagated through shadow boundary"

        browser.close()


# ─── Test 2: Button click inside custom element shadow DOM ───

def test_button_in_custom_element_shadow_dom_does_not_navigate():
    """Clicking a button inside a custom element's shadow DOM within a card
    should NOT trigger navigation.

    Same root cause as test 1 but with a button element. Even though the guard
    checks for 'button' in closest(), the button is inside the custom element's
    shadow DOM and e.target at the card level is the custom element host, not
    the button.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(BASE)
        _login(page)
        page.reload()
        _wait_for_list_items(page)

        result = _inject_interactive_element(page)
        assert result["injected"], "Failed to inject test widget into a card"

        hash_before = page.evaluate("() => location.hash")

        # Click on the button inside the widget's shadow DOM
        click_result = page.evaluate("""() => {
            const lists = document.querySelectorAll('ntx-list');
            for (const list of lists) {
                const grid = list.shadowRoot?.querySelector('.list-grid');
                if (!grid) continue;
                const item = grid.querySelector('ntx-item');
                if (!item) continue;
                const widget = item.shadowRoot?.querySelector('test-interactive-widget');
                if (!widget) continue;
                const btn = widget.shadowRoot?.querySelector('.widget-btn');
                if (btn) {
                    btn.click();
                    return 'clicked';
                }
            }
            return 'not-found';
        }""")
        assert click_result == "clicked", f"Could not click button: {click_result}"

        page.wait_for_timeout(2000)

        hash_after = page.evaluate("() => location.hash")
        assert not hash_after.startswith("#"), \
            f"BUG: Clicking button inside custom element's shadow DOM " \
            f"navigated to {hash_after} — event propagated through shadow boundary"

        browser.close()


# ─── Test 3: List stays visible after shadow DOM click ───

def test_list_stays_visible_after_shadow_dom_widget_click():
    """After clicking interactive content inside a custom element's shadow DOM,
    the list view should remain visible (not replaced by a detail view).

    When the bug occurs, the router replaces the list with the detail view of
    the clicked item, removing the list from the DOM entirely.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(BASE)
        _login(page)
        page.reload()
        _wait_for_list_items(page)

        result = _inject_interactive_element(page)
        assert result["injected"], "Failed to inject test widget"

        # Click on the widget's textarea
        page.evaluate("""() => {
            const lists = document.querySelectorAll('ntx-list');
            for (const list of lists) {
                const grid = list.shadowRoot?.querySelector('.list-grid');
                if (!grid) continue;
                const item = grid.querySelector('ntx-item');
                if (!item) continue;
                const widget = item.shadowRoot?.querySelector('test-interactive-widget');
                if (!widget) continue;
                const textarea = widget.shadowRoot?.querySelector('textarea');
                if (textarea) { textarea.click(); return; }
            }
        }""")

        page.wait_for_timeout(2000)

        # Check if the list is still visible
        list_visible = page.evaluate("""() => {
            const lists = document.querySelectorAll('ntx-list');
            for (const list of lists) {
                const grid = list.shadowRoot?.querySelector('.list-grid');
                if (grid && grid.querySelectorAll('ntx-item').length > 0) return true;
            }
            return false;
        }""")

        assert list_visible, \
            "BUG: List disappeared after clicking widget textarea — " \
            "click event propagated to card, triggering navigation to detail view"

        browser.close()
