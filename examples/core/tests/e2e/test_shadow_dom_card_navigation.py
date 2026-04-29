"""Playwright e2e tests: shadow DOM click propagation on cards in list view.

Bug: When a custom element with interactive content in its shadow DOM
(like ntx-agent-live with textarea/button) is rendered inside an ntx-item
card in list view, clicking the interactive content causes navigation to
the detail page because:

1. The card click handler uses e.target.closest() to check for interactive elements
2. e.target is retargeted to the custom element's host (e.g. ntx-agent-live)
3. The host element doesn't match any selector in the guard list
4. The click propagates to the card handler, triggering SELECT -> navigation

Fix: Components with interactive shadow DOM content must call
e.stopPropagation() on their click events to prevent propagation to
the card handler. This follows the same pattern as ntx-method's
renderButton(), which already stops propagation.

This reproduces the ntx-agent-live bug from the pygentic/agentics example.
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


def _wait_for_routed_list(page, timeout=10000):
    """Wait until the router's slotted ntx-list has rendered items with cards."""
    page.wait_for_function("""() => {
        // ntx-list is a light DOM child of ntx-router (projected via <slot>)
        const router = document.querySelector('ntx-router');
        if (!router) return false;
        const lists = router.querySelectorAll('ntx-list');
        for (const list of lists) {
            const grid = list.shadowRoot?.querySelector('.list-grid');
            if (!grid) continue;
            const items = grid.querySelectorAll('ntx-item');
            for (const item of items) {
                const card = item.shadowRoot?.querySelector('.card');
                if (card && item.getAttribute('select-target')) return true;
            }
        }
        return false;
    }""", timeout=timeout)


def _wait_for_render_settle(page):
    """Wait for queued event/render work without adding a fixed sleep."""
    page.evaluate("""() => new Promise(resolve => {
        requestAnimationFrame(() => requestAnimationFrame(resolve));
    })""")


def _wait_for_hash_change(page, hash_before, timeout=5000):
    page.wait_for_function(
        "before => location.hash !== before && location.hash.startsWith('#')",
        arg=hash_before,
        timeout=timeout,
    )


def _inject_widget(page, stop_propagation=False):
    """Inject a custom element with interactive shadow DOM into a routed card.

    When stop_propagation=True, the widget calls e.stopPropagation() on its
    host element click — the same fix pattern applied to ntx-agent-live.
    When stop_propagation=False, clicks propagate through (the bug).
    """
    tag = 'test-fixed-widget' if stop_propagation else 'test-broken-widget'
    return page.evaluate("""(args) => {
        const tag = args.tag;
        const stopProp = args.stopProp;

        if (!customElements.get(tag)) {
            class TestWidget extends HTMLElement {
                connectedCallback() {
                    this.attachShadow({mode: 'open'});
                    this.shadowRoot.innerHTML = `
                        <div class="widget-panel">
                            <textarea placeholder="Enter task..." rows="2"></textarea>
                            <button class="widget-btn">Run</button>
                        </div>
                    `;
                    this.shadowRoot.querySelector('.widget-btn').addEventListener('click', () => {
                        // action handler — same as ntx-agent-live
                    });

                    // Fix pattern: stop propagation at host level
                    if (stopProp) {
                        this.addEventListener('click', (e) => e.stopPropagation());
                    }
                }
            }
            customElements.define(tag, TestWidget);
        }

        // Find a card inside the router's slotted list
        const router = document.querySelector('ntx-router');
        if (!router) return { injected: false, reason: 'no router' };

        const lists = router.querySelectorAll('ntx-list');
        for (const list of lists) {
            const grid = list.shadowRoot?.querySelector('.list-grid');
            if (!grid) continue;
            const items = grid.querySelectorAll('ntx-item');
            for (const item of items) {
                const card = item.shadowRoot?.querySelector('.card');
                if (!card) continue;
                if (!item.getAttribute('select-target')) continue;
                const el = document.createElement(tag);
                card.appendChild(el);
                return {
                    injected: true,
                    tag: tag,
                    display: item.getAttribute('display') || 'unknown',
                    selectTarget: item.getAttribute('select-target'),
                };
            }
        }
        return { injected: false, reason: 'no suitable card' };
    }""", {"tag": tag, "stopProp": stop_propagation})


def _click_widget_element(page, widget_tag, selector):
    """Click an element inside the injected widget's shadow DOM."""
    return page.evaluate("""(args) => {
        const router = document.querySelector('ntx-router');
        if (!router) return 'no-router';
        const lists = router.querySelectorAll('ntx-list');
        for (const list of lists) {
            const grid = list.shadowRoot?.querySelector('.list-grid');
            if (!grid) continue;
            const items = grid.querySelectorAll('ntx-item');
            for (const item of items) {
                const widget = item.shadowRoot?.querySelector(args.tag);
                if (!widget) continue;
                const target = widget.shadowRoot?.querySelector(args.sel);
                if (target) {
                    target.click();
                    return 'clicked';
                }
            }
        }
        return 'not-found';
    }""", {"tag": widget_tag, "sel": selector})


# --- Test 1: Widget WITH stopPropagation - textarea click must not navigate ---

def test_widget_with_stop_propagation_textarea_does_not_navigate():
    """A custom element that calls stopPropagation on its host click
    should NOT trigger card navigation when its textarea is clicked.

    This verifies the fix pattern: ntx-agent-live (and similar components)
    must stop click propagation at the host element level.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(BASE)
        _login(page)
        page.reload()
        _wait_for_routed_list(page)

        result = _inject_widget(page, stop_propagation=True)
        assert result["injected"], f"Failed to inject widget: {result}"

        hash_before = page.evaluate("() => location.hash")

        click_result = _click_widget_element(page, "test-fixed-widget", "textarea")
        assert click_result == "clicked", f"Could not click textarea: {click_result}"

        _wait_for_render_settle(page)

        hash_after = page.evaluate("() => location.hash")
        assert hash_after == hash_before, \
            f"BUG: Widget with stopPropagation still navigated " \
            f"from '{hash_before}' to '{hash_after}'"

        browser.close()


# --- Test 2: Widget WITH stopPropagation - button click must not navigate ---

def test_widget_with_stop_propagation_button_does_not_navigate():
    """A custom element that calls stopPropagation on its host click
    should NOT trigger card navigation when its button is clicked.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(BASE)
        _login(page)
        page.reload()
        _wait_for_routed_list(page)

        result = _inject_widget(page, stop_propagation=True)
        assert result["injected"], f"Failed to inject widget: {result}"

        hash_before = page.evaluate("() => location.hash")

        click_result = _click_widget_element(page, "test-fixed-widget", ".widget-btn")
        assert click_result == "clicked", f"Could not click button: {click_result}"

        _wait_for_render_settle(page)

        hash_after = page.evaluate("() => location.hash")
        assert hash_after == hash_before, \
            f"BUG: Widget with stopPropagation still navigated " \
            f"from '{hash_before}' to '{hash_after}'"

        browser.close()


# --- Test 3: Widget WITH stopPropagation - router stays on list view ---

def test_widget_with_stop_propagation_list_stays_visible():
    """After clicking a widget that uses stopPropagation, the router
    should still show the list (not switch to detail view).
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(BASE)
        _login(page)
        page.reload()
        _wait_for_routed_list(page)

        result = _inject_widget(page, stop_propagation=True)
        assert result["injected"], f"Failed to inject widget: {result}"

        click_result = _click_widget_element(page, "test-fixed-widget", "textarea")
        assert click_result == "clicked"

        _wait_for_render_settle(page)

        # Router should NOT have switched to detail view
        router_on_detail = page.evaluate("() => location.hash.startsWith('#')")
        assert not router_on_detail, \
            "BUG: Router switched to detail view after clicking widget " \
            "with stopPropagation — the pattern doesn't work"

        browser.close()


# --- Test 4: Widget WITHOUT stopPropagation - confirms the bug exists ---

def test_widget_without_stop_propagation_does_navigate():
    """A custom element that does NOT call stopPropagation allows click
    propagation through the shadow boundary, triggering card navigation.

    This is the bug: ntx-agent-live (before the fix) doesn't stop propagation.
    The card click handler sees e.target as the custom element host, which
    doesn't match any selector in the guard list, so navigation fires.

    This test confirms the underlying vulnerability exists — it's the
    negative proof that the fix pattern is necessary.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(BASE)
        _login(page)
        page.reload()
        _wait_for_routed_list(page)

        result = _inject_widget(page, stop_propagation=False)
        assert result["injected"], f"Failed to inject widget: {result}"

        hash_before = page.evaluate("() => location.hash")

        click_result = _click_widget_element(page, "test-broken-widget", "textarea")
        assert click_result == "clicked", f"Could not click textarea: {click_result}"

        _wait_for_hash_change(page, hash_before)

        hash_after = page.evaluate("() => location.hash")
        # This SHOULD navigate (the bug) — proving the vulnerability exists
        assert hash_after != hash_before and hash_after.startswith("#"), \
            f"Expected navigation due to missing stopPropagation, " \
            f"but hash stayed at '{hash_after}'"

        browser.close()
