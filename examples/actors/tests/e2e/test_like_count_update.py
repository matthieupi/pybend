# tests/e2e/test_like_count_update.py
"""
E2E bug reproduction: Like/favorite count badge doesn't update after click.

Tests that clicking like on a comment or favorite on a product causes
the displayed count to change in the UI. This is the primary user-facing
manifestation of the bug.
"""
import json
import pytest
from playwright.sync_api import sync_playwright

BASE = "http://localhost:5000"


def get_token(page, email="alice@example.com", password="alice123"):
    """Get JWT token and store in localStorage."""
    return page.evaluate("""async (args) => {
        const resp = await fetch('/users/login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({email: args.email, password: args.password}),
        });
        const data = await resp.json();
        const token = data.data ? data.data.token : data.token;
        window.localStorage.setItem('jwtToken', token);
        return token;
    }""", {"email": email, "password": password})


def find_method_buttons(page, method):
    """Find method buttons via shadow DOM traversal."""
    return page.evaluate("""(method) => {
        function findInShadow(root, depth = 0) {
            if (depth > 10) return [];
            const results = [];
            for (const el of root.querySelectorAll('ntx-method[method="' + method + '"]')) {
                results.push({
                    model: el.getAttribute('model'),
                    uuid: el.getAttribute('uuid'),
                    countField: el.getAttribute('count-field'),
                    countText: el.shadowRoot?.querySelector('.method-btn-count')?.textContent ?? 'N/A',
                });
            }
            for (const el of root.querySelectorAll('*')) {
                if (el.shadowRoot) results.push(...findInShadow(el.shadowRoot, depth + 1));
            }
            return results;
        }
        return findInShadow(document);
    }""", method)


def click_method_button(page, method, uuid):
    """Click a method button and return the action response."""
    return page.evaluate("""(args) => {
        function findInShadow(root, depth = 0) {
            if (depth > 10) return null;
            for (const el of root.querySelectorAll('ntx-method[method="' + args.method + '"]')) {
                if (el.getAttribute('uuid') === args.uuid) {
                    const btn = el.shadowRoot?.querySelector('.method-btn');
                    if (btn) { btn.click(); return 'clicked'; }
                    return 'no button';
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
        return findInShadow(document) || 'not found';
    }""", {"method": method, "uuid": uuid})


def get_displayed_count(page, method, uuid):
    """Get the displayed count from the method button badge."""
    return page.evaluate("""(args) => {
        function findInShadow(root, depth = 0) {
            if (depth > 10) return null;
            for (const el of root.querySelectorAll('ntx-method[method="' + args.method + '"]')) {
                if (el.getAttribute('uuid') === args.uuid)
                    return el.shadowRoot?.querySelector('.method-btn-count')?.textContent ?? null;
            }
            for (const el of root.querySelectorAll('*')) {
                if (el.shadowRoot) {
                    const r = findInShadow(el.shadowRoot, depth + 1);
                    if (r !== null) return r;
                }
            }
            return null;
        }
        return findInShadow(document);
    }""", {"method": method, "uuid": uuid})


def wait_for_method_buttons(page, method, timeout=10000):
    page.wait_for_function("""(method) => {
        function findInShadow(root, depth = 0) {
            if (depth > 10) return false;
            for (const el of root.querySelectorAll('ntx-method[method="' + method + '"]')) {
                if (el.shadowRoot?.querySelector('.method-btn-count')) return true;
            }
            for (const el of root.querySelectorAll('*')) {
                if (el.shadowRoot && findInShadow(el.shadowRoot, depth + 1)) return true;
            }
            return false;
        }
        return findInShadow(document);
    }""", arg=method, timeout=timeout)


def wait_for_method_count(page, method, uuid, expected, timeout=5000):
    page.wait_for_function("""(args) => {
        function findInShadow(root, depth = 0) {
            if (depth > 10) return null;
            for (const el of root.querySelectorAll('ntx-method[method="' + args.method + '"]')) {
                if (el.getAttribute('uuid') === args.uuid) {
                    return el.shadowRoot?.querySelector('.method-btn-count')?.textContent ?? null;
                }
            }
            for (const el of root.querySelectorAll('*')) {
                if (el.shadowRoot) {
                    const r = findInShadow(el.shadowRoot, depth + 1);
                    if (r !== null) return r;
                }
            }
            return null;
        }
        return Number(findInShadow(document)) === args.expected;
    }""", arg={"method": method, "uuid": uuid, "expected": expected}, timeout=timeout)


def response_action(response):
    body = response.json()
    if isinstance(body, str):
        body = json.loads(body)
    if '_debug' in body and 'data' in body:
        body = body['data']
    return body.get('action', '?')


def test_like_count_updates_after_click():
    """Bug: clicking like on a comment doesn't update the displayed count.

    The backend processes the request (200 OK) but the frontend count
    badge stays at the old value because DynamicClass._response_
    doesn't call pull() for action-only responses.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context().new_page()

        # Capture POST responses
        last_action = {}
        def on_response(resp):
            if resp.request.method == "POST" and resp.status == 200:
                try:
                    body = resp.json()
                    if isinstance(body, str):
                        body = json.loads(body)
                    if '_debug' in body and 'data' in body:
                        body = body['data']
                    if 'action' in body:
                        last_action['value'] = body['action']
                except:
                    pass
        page.on("response", on_response)

        # Boot app and authenticate
        page.goto(f"{BASE}/")
        get_token(page)
        page.reload()
        wait_for_method_buttons(page, 'like')

        # Find a like button
        likes = find_method_buttons(page, 'like')
        assert len(likes) > 0, "No like buttons found on page"

        target = likes[0]
        uuid = target['uuid']
        count_before = int(target['countText'])

        # Click like
        last_action.clear()
        with page.expect_response(lambda resp: resp.request.method == "POST" and "/like" in resp.url) as response_info:
            assert click_method_button(page, 'like', uuid) == 'clicked'
        action = response_action(response_info.value)

        # Verify count changed
        count_after = get_displayed_count(page, 'like', uuid)
        assert count_after is not None, "Count badge not found after click"
        count_after = int(count_after)
        if action == 'liked':
            expected = count_before + 1
        else:
            expected = count_before - 1
        wait_for_method_count(page, 'like', uuid, expected)
        count_after = int(get_displayed_count(page, 'like', uuid))

        assert count_after == expected, (
            f"Like count didn't update! action={action}, "
            f"count: {count_before} -> {count_after} (expected {expected}). "
            f"Backend processes the request but frontend _response_ handler "
            f"doesn't refresh the entity."
        )

        browser.close()


def test_favorite_count_updates_after_click():
    """Bug: clicking favorite on a product doesn't update the displayed count.

    Same root cause as the like bug — DynamicClass._response_ skips
    pull() for action-only responses.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context().new_page()

        last_action = {}
        def on_response(resp):
            if resp.request.method == "POST" and resp.status == 200:
                try:
                    body = resp.json()
                    if isinstance(body, str):
                        body = json.loads(body)
                    if '_debug' in body and 'data' in body:
                        body = body['data']
                    if 'action' in body:
                        last_action['value'] = body['action']
                except:
                    pass
        page.on("response", on_response)

        page.goto(f"{BASE}/")
        get_token(page)
        page.reload()
        wait_for_method_buttons(page, 'favorite')

        # Find a favorite button
        favs = find_method_buttons(page, 'favorite')
        assert len(favs) > 0, "No favorite buttons found on page"

        target = favs[0]
        uuid = target['uuid']
        count_before = int(target['countText'])

        # Click favorite
        last_action.clear()
        with page.expect_response(lambda resp: resp.request.method == "POST" and "/favorite" in resp.url) as response_info:
            assert click_method_button(page, 'favorite', uuid) == 'clicked'
        action = response_action(response_info.value)

        count_after = get_displayed_count(page, 'favorite', uuid)
        assert count_after is not None, "Count badge not found after click"
        count_after = int(count_after)
        if action == 'favorited':
            expected = count_before + 1
        else:
            expected = count_before - 1
        wait_for_method_count(page, 'favorite', uuid, expected)
        count_after = int(get_displayed_count(page, 'favorite', uuid))

        assert count_after == expected, (
            f"Favorite count didn't update! action={action}, "
            f"count: {count_before} -> {count_after} (expected {expected}). "
            f"Backend processes the request but frontend doesn't refresh."
        )

        browser.close()


def test_like_count_persists_after_page_refresh():
    """Bug: even after page refresh, likes may not show correctly
    if the entity data wasn't properly refreshed.

    This test likes a comment, refreshes the page, and verifies
    the count reflects the like.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context().new_page()

        last_action = {}
        def on_response(resp):
            if resp.request.method == "POST" and resp.status == 200:
                try:
                    body = resp.json()
                    if isinstance(body, str):
                        body = json.loads(body)
                    if '_debug' in body and 'data' in body:
                        body = body['data']
                    if 'action' in body:
                        last_action['value'] = body['action']
                except:
                    pass
        page.on("response", on_response)

        page.goto(f"{BASE}/")
        get_token(page)
        page.reload()
        wait_for_method_buttons(page, 'like')

        # Find and click like
        likes = find_method_buttons(page, 'like')
        assert len(likes) > 0, "No like buttons found"
        target = likes[0]
        uuid = target['uuid']
        count_before = int(target['countText'])

        last_action.clear()
        with page.expect_response(lambda resp: resp.request.method == "POST" and "/like" in resp.url) as response_info:
            click_method_button(page, 'like', uuid)
        action = response_action(response_info.value)

        # Refresh the page
        page.reload()
        wait_for_method_buttons(page, 'like')

        # Re-find the same button after refresh
        likes_after = find_method_buttons(page, 'like')
        matching = [b for b in likes_after if b['uuid'] == uuid]
        assert len(matching) > 0, f"Like button for uuid={uuid} not found after refresh"

        count_after_refresh = int(matching[0]['countText'])

        if action == 'liked':
            expected = count_before + 1
        else:
            expected = count_before - 1

        assert count_after_refresh == expected, (
            f"Like count wrong after page refresh! action={action}, "
            f"before={count_before}, after_refresh={count_after_refresh} (expected {expected})"
        )

        browser.close()
