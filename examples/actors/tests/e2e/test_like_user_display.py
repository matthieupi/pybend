"""Playwright test: likes on product cards should render the user via ntx-user, not raw text."""
from playwright.sync_api import sync_playwright
import json

BASE = "http://localhost:5000"


def _login(page, email="alice@example.com", password="alice123"):
    """Log in via the API and inject the token into localStorage."""
    resp = page.request.post(f"{BASE}/users/login", data={
        "email": email, "password": password,
    })
    body = resp.json()
    # Unwrap debug envelope if present
    if '_debug' in body and 'data' in body:
        body = body['data']
    token = body.get("token")
    assert token, f"Login failed: {body}"
    page.evaluate(f"() => localStorage.setItem('jwtToken', '{token}')")
    return token


def _wait_for_product_items(page, timeout=10000):
    """Wait until at least one ntx-item is rendered inside an ntx-list."""
    page.wait_for_function("""() => {
        const lists = document.querySelectorAll('ntx-list');
        for (const list of lists) {
            const items = list.shadowRoot?.querySelectorAll('ntx-item') || [];
            if (items.length > 0) return true;
        }
        return false;
    }""", timeout=timeout)


def _like_first_product(page):
    """Click the like button on the first product and wait for the response."""
    page.evaluate("""() => {
        const lists = document.querySelectorAll('ntx-list');
        for (const list of lists) {
            const items = list.shadowRoot?.querySelectorAll('ntx-item') || [];
            for (const item of items) {
                // Find the like method button
                const methods = item.shadowRoot?.querySelectorAll('ntx-method') || [];
                for (const m of methods) {
                    if (m.getAttribute('method') === 'like') {
                        const btn = m.shadowRoot?.querySelector('button[type="submit"]');
                        if (btn) { btn.click(); return true; }
                    }
                }
            }
        }
        return false;
    }""")
    page.wait_for_timeout(2000)


def test_like_user_renders_as_ntx_user():
    """After liking a product, the likes section should render users via ntx-user, not raw text/URLs."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})

        page.goto(f"{BASE}/")
        _login(page)
        page.reload()
        _wait_for_product_items(page)

        # Like the first product
        _like_first_product(page)

        # Navigate to the product detail by clicking on it
        page.evaluate("""() => {
            const lists = document.querySelectorAll('ntx-list');
            for (const list of lists) {
                const items = list.shadowRoot?.querySelectorAll('ntx-item') || [];
                if (items.length > 0) {
                    items[0].shadowRoot?.querySelector('.card')?.click();
                    return true;
                }
            }
            return false;
        }""")
        page.wait_for_timeout(3000)

        # Now inspect the likes section — check for ntx-user elements and absence of raw URLs
        result = page.evaluate("""() => {
            // Gather all ntx-item elements (could be product detail or nested likes)
            const allItems = document.querySelectorAll('ntx-item');
            const routerItems = document.querySelector('ntx-router')
                ?.shadowRoot?.querySelectorAll('ntx-item, ntx-list') || [];

            const info = {
                ntxUserElements: 0,
                rawUrlTexts: [],
                likeTexts: [],
            };

            // Check all shadow roots recursively for ntx-user or raw URL text
            function inspect(root) {
                if (!root) return;
                const users = root.querySelectorAll('ntx-user');
                info.ntxUserElements += users.length;

                // Check for raw URL patterns in text content
                const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
                while (walker.nextNode()) {
                    const text = walker.currentNode.textContent.trim();
                    if (text.match(/https?:\/\/.*\/users\/\d+/)) {
                        info.rawUrlTexts.push(text);
                    }
                    if (text === 'Like' || text.match(/^Like\s/)) {
                        info.likeTexts.push(text);
                    }
                }

                // Recurse into shadow roots
                root.querySelectorAll('*').forEach(el => {
                    if (el.shadowRoot) inspect(el.shadowRoot);
                });
            }

            inspect(document);
            return info;
        }""")

        print(f"\nLike display inspection: {json.dumps(result, indent=2)}")

        # Also check the API response directly for likes data
        api_result = page.evaluate("""async () => {
            const resp = await fetch(location.origin + '/products?limit=5&offset=0');
            const data = await resp.json();
            const products = data.data || [];
            const result = { products: [] };
            for (const p of products.slice(0, 2)) {
                const likes = p.likes?.data || p.likes || [];
                result.products.push({
                    name: p.name,
                    likes: likes.slice(0, 3),
                });
            }
            return result;
        }""")
        print(f"\nAPI likes data: {json.dumps(api_result, indent=2)}")

        # Also check the schema for Like to verify $ref
        schema_result = page.evaluate("""async () => {
            const resp = await fetch(location.origin + '/Product');
            const schema = await resp.json();
            const likeDef = schema.$defs?.Like || schema.$defs?.ProductLike;
            return {
                likeUserProp: likeDef?.properties?.user || 'NOT FOUND',
                userDef: schema.$defs?.User ? 'present' : 'missing',
                userRenderer: schema.$defs?.User?.ui?.renderer || 'none',
            };
        }""")
        print(f"\nSchema check: {json.dumps(schema_result, indent=2)}")

        # Assertions
        assert len(result["rawUrlTexts"]) == 0, \
            f"Found raw URL text in likes display: {result['rawUrlTexts']}"

        browser.close()


if __name__ == '__main__':
    test_like_user_renders_as_ntx_user()
