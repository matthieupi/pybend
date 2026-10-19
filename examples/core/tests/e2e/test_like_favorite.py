"""Playwright test: Like a comment and favorite a product, verify counts update.

Validates that:
  1. Clicking like on a comment toggles the count correctly
  2. Clicking favorite on a product toggles the count correctly
  3. The N3TX instance value matches the displayed count
  4. Toggle back reverses the count
"""
import json
from playwright.sync_api import sync_playwright

BASE = "http://localhost:5000"


def get_token(page, email="alice@example.com", password="alice123"):
    """Get JWT token via API and store in localStorage."""
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


def wait_for_method_buttons(page, timeout=10000):
    """Wait until like and favorite buttons are rendered in Shadow DOM."""
    page.wait_for_function("""() => {
        function findInShadow(root, method, depth = 0) {
            if (depth > 10) return false;
            for (const el of root.querySelectorAll(`ntx-method[method="${method}"]`)) {
                if (el.shadowRoot?.querySelector('.method-btn-count')) return true;
            }
            for (const el of root.querySelectorAll('*')) {
                if (el.shadowRoot && findInShadow(el.shadowRoot, method, depth + 1)) return true;
            }
            return false;
        }
        return findInShadow(document, 'like') && findInShadow(document, 'favorite');
    }""", timeout=timeout)


def wait_for_method_count(page, method, uuid, expected, timeout=5000):
    """Wait until a method button exposes the expected rendered count."""
    page.wait_for_function("""(args) => {
        function findInShadow(root, depth = 0) {
            if (depth > 10) return null;
            for (const el of root.querySelectorAll(`ntx-method[method="${args.method}"]`)) {
                if (el.getAttribute('uuid') === args.uuid) {
                    return el.shadowRoot?.querySelector('.method-btn-count')?.textContent ?? null;
                }
            }
            for (const el of root.querySelectorAll('*')) {
                if (el.shadowRoot) {
                    const result = findInShadow(el.shadowRoot, depth + 1);
                    if (result !== null) return result;
                }
            }
            return null;
        }
        return Number(findInShadow(document)) === args.expected;
    }""", arg={"method": method, "uuid": uuid, "expected": expected}, timeout=timeout)


def response_action(response):
    """Extract action from direct or debug-enveloped method responses."""
    body = response.json()
    if '_debug' in body and 'data' in body:
        body = body['data']
    return body.get('action', '?')


def find_buttons(page, method):
    """Find all method buttons by traversing shadow DOMs."""
    return page.evaluate("""(method) => {
        function findInShadow(root, depth = 0) {
            if (depth > 10) return [];
            const results = [];
            for (const el of root.querySelectorAll(`ntx-method[method="${method}"]`)) {
                results.push({
                    model: el.getAttribute('model'),
                    uuid: el.getAttribute('uuid'),
                    countField: el.getAttribute('count-field'),
                    countText: el.shadowRoot?.querySelector('.method-btn-count')?.textContent ?? 'N/A',
                });
            }
            for (const el of root.querySelectorAll('*')) {
                if (el.shadowRoot)
                    results.push(...findInShadow(el.shadowRoot, depth + 1));
            }
            return results;
        }
        return findInShadow(document);
    }""", method)


def click_button(page, method, uuid):
    """Click a method button inside nested shadow DOMs."""
    return page.evaluate("""(args) => {
        function findInShadow(root, depth = 0) {
            if (depth > 10) return null;
            for (const el of root.querySelectorAll(`ntx-method[method="${args.method}"]`)) {
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


def get_count(page, method, uuid):
    """Get the displayed count for a specific method button."""
    return page.evaluate("""(args) => {
        function findInShadow(root, depth = 0) {
            if (depth > 10) return null;
            for (const el of root.querySelectorAll(`ntx-method[method="${args.method}"]`)) {
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


def get_ntt_field(page, model, uuid, field):
    """Get a specific field from the N3TX instance's value."""
    return page.evaluate("""(args) => {
        const ntt = window.NTT?.get(args.model + '/' + args.uuid);
        if (!ntt) return null;
        const v = ntt.value?.[args.field];
        return Array.isArray(v) ? v.length : (v?.data ? v.data.length : v);
    }""", {"model": model, "uuid": uuid, "field": field})


def test_like_and_favorite():
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context().new_page()

        # Capture POST responses to know action direction
        last_action = {}
        def on_response(resp):
            if resp.request.method == "POST" and resp.status == 200:
                try:
                    body = resp.json()
                    # Unwrap debug envelope if present
                    if '_debug' in body and 'data' in body:
                        body = body['data']
                    if 'action' in body:
                        last_action['value'] = body['action']
                except:
                    pass
        page.on("response", on_response)

        # Boot the app
        page.goto(f"{BASE}/")
        get_token(page)
        page.reload()
        wait_for_method_buttons(page)

        # ─── TEST: LIKE TOGGLE ───
        likes = find_buttons(page, 'like')
        assert len(likes) > 0, "No like buttons found"
        target = likes[0]
        model, uuid = target['model'], target['uuid']
        count_before = int(target['countText'])

        # Click 1: toggle
        last_action.clear()
        with page.expect_response(lambda resp: resp.request.method == "POST" and "/like" in resp.url) as response_info:
            assert click_button(page, 'like', uuid) == 'clicked'
        action_1 = response_action(response_info.value)

        if action_1 == 'liked':
            expected_1 = count_before + 1
        else:
            expected_1 = count_before - 1
        wait_for_method_count(page, 'like', uuid, expected_1)
        count_after_1 = int(get_count(page, 'like', uuid))
        ntt_count_1 = get_ntt_field(page, model, uuid, 'likes')

        like_pass_1 = count_after_1 == expected_1 and count_after_1 == ntt_count_1
        results.append(('Like toggle 1', like_pass_1,
                        f"action={action_1} count: {count_before}→{count_after_1} (expected {expected_1}), N3TX={ntt_count_1}"))

        # Click 2: toggle back
        last_action.clear()
        with page.expect_response(lambda resp: resp.request.method == "POST" and "/like" in resp.url) as response_info:
            click_button(page, 'like', uuid)
        action_2 = response_action(response_info.value)
        wait_for_method_count(page, 'like', uuid, count_before)

        count_after_2 = int(get_count(page, 'like', uuid))
        ntt_count_2 = get_ntt_field(page, model, uuid, 'likes')

        like_pass_2 = count_after_2 == count_before and count_after_2 == ntt_count_2
        results.append(('Like toggle 2 (back)', like_pass_2,
                        f"action={action_2} count: {count_after_1}→{count_after_2} (expected {count_before}), N3TX={ntt_count_2}"))

        # ─── TEST: FAVORITE TOGGLE ───
        favs = find_buttons(page, 'favorite')
        assert len(favs) > 0, "No favorite buttons found"
        target = favs[0]
        model, uuid = target['model'], target['uuid']
        count_before = int(target['countText'])

        # Click 1: toggle
        last_action.clear()
        with page.expect_response(lambda resp: resp.request.method == "POST" and "/favorite" in resp.url) as response_info:
            assert click_button(page, 'favorite', uuid) == 'clicked'
        action_1 = response_action(response_info.value)

        if action_1 == 'favorited':
            expected_1 = count_before + 1
        else:
            expected_1 = count_before - 1
        wait_for_method_count(page, 'favorite', uuid, expected_1)
        count_after_1 = int(get_count(page, 'favorite', uuid))
        ntt_count_1 = get_ntt_field(page, model, uuid, 'favorites')

        fav_pass_1 = count_after_1 == expected_1 and count_after_1 == ntt_count_1
        results.append(('Favorite toggle 1', fav_pass_1,
                        f"action={action_1} count: {count_before}→{count_after_1} (expected {expected_1}), N3TX={ntt_count_1}"))

        # Click 2: toggle back
        last_action.clear()
        with page.expect_response(lambda resp: resp.request.method == "POST" and "/favorite" in resp.url) as response_info:
            click_button(page, 'favorite', uuid)
        action_2 = response_action(response_info.value)
        wait_for_method_count(page, 'favorite', uuid, count_before)

        count_after_2 = int(get_count(page, 'favorite', uuid))
        ntt_count_2 = get_ntt_field(page, model, uuid, 'favorites')

        fav_pass_2 = count_after_2 == count_before and count_after_2 == ntt_count_2
        results.append(('Favorite toggle 2 (back)', fav_pass_2,
                        f"action={action_2} count: {count_after_1}→{count_after_2} (expected {count_before}), N3TX={ntt_count_2}"))

        browser.close()

    # Report
    print("\n" + "="*60)
    all_pass = True
    for name, passed, detail in results:
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False
        print(f"  [{status}] {name}: {detail}")
    print("="*60)

    if not all_pass:
        raise AssertionError("Some tests failed — see details above")
    print("All tests passed!")


if __name__ == "__main__":
    test_like_and_favorite()
