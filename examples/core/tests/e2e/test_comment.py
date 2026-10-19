"""Playwright test to verify ntx-method loop fix and comment flow."""
from playwright.sync_api import sync_playwright
import json

BASE = "http://localhost:5000"


def wait_for_method_form(page, timeout=10000):
    """Wait until the app has rendered an actionable ntx-method form."""
    page.wait_for_function("""() => {
        const lists = document.querySelectorAll('ntx-list');
        for (const list of lists) {
            const items = list.shadowRoot?.querySelectorAll('ntx-item') || [];
            for (const item of items) {
                const methods = item.shadowRoot?.querySelectorAll('ntx-method') || [];
                for (const method of methods) {
                    if (method.getAttribute('method') !== 'comment') continue;
                    const button = method.shadowRoot?.querySelector('button[type="submit"]');
                    const fields = method.shadowRoot?.querySelectorAll('input, textarea') || [];
                    const namedField = Array.from(fields).some(field => field.name || field.dataset?.key);
                    if (button && fields.length > 0 && namedField) return true;
                }
            }
        }
        return false;
    }""", timeout=timeout)


def wait_for_render_settle(page):
    """Wait for queued click/render work without sleeping for a fixed duration."""
    page.evaluate("""() => new Promise(resolve => {
        requestAnimationFrame(() => requestAnimationFrame(resolve));
    })""")


def get_token(page, email="alice@example.com", password="alice123"):
    """Get JWT token via API and store it for authenticated method rendering."""
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

def test_comment():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Capture network requests for comment endpoint
        requests_log = []
        def on_request(req):
            if 'comment' in req.url.lower() and req.method == 'POST':
                requests_log.append({
                    'url': req.url,
                    'method': req.method,
                    'body': req.post_data
                })
        page.on("request", on_request)

        responses_log = []
        def on_response(resp):
            if 'comment' in resp.url.lower() and resp.request.method == 'POST':
                try:
                    body = resp.text()
                except:
                    body = f"status: {resp.status}"
                responses_log.append({
                    'url': resp.url,
                    'status': resp.status,
                    'body': body[:300]
                })
        page.on("response", on_response)

        # Navigate
        page.goto(f"{BASE}/")
        get_token(page)
        page.reload()
        wait_for_method_form(page)

        # Check ntx-method exists and has correct form
        method_info = page.evaluate("""() => {
            const lists = document.querySelectorAll('ntx-list');
            for (const list of lists) {
                const items = list.shadowRoot?.querySelectorAll('ntx-item') || [];
                for (const item of items) {
                    const methods = item.shadowRoot?.querySelectorAll('ntx-method') || [];
                    for (const m of methods) {
                        if (m.getAttribute('method') !== 'comment') continue;
                        const inputs = m.shadowRoot?.querySelectorAll('input, textarea') || [];
                        return {
                            model: m.getAttribute('model'),
                            method: m.getAttribute('method'),
                            uuid: m.getAttribute('uuid'),
                            inputCount: inputs.length,
                            inputNames: Array.from(inputs).map(i => i.name),
                            schemaParams: m.schema?.parameters,
                        };
                    }
                }
            }
            return null;
        }""")
        print(f"Method element: {json.dumps(method_info, indent=2)}")

        # Fill form
        page.evaluate("""() => {
            const lists = document.querySelectorAll('ntx-list');
            for (const list of lists) {
                const items = list.shadowRoot?.querySelectorAll('ntx-item') || [];
                for (const item of items) {
                    const methods = item.shadowRoot?.querySelectorAll('ntx-method') || [];
                    for (const m of methods) {
                        if (m.getAttribute('method') !== 'comment') continue;
                        const inputs = m.shadowRoot?.querySelectorAll('input, textarea');
                        if (inputs && inputs.length > 0) {
                            inputs[0].value = 'Test Comment';
                            inputs[0].dispatchEvent(new Event('input', {bubbles: true}));
                            return true;
                        }
                    }
                }
            }
            return false;
        }""")

        # Click Run button and let browser/network queues settle instead of sleeping.
        page.evaluate("""() => {
            const lists = document.querySelectorAll('ntx-list');
            for (const list of lists) {
                const items = list.shadowRoot?.querySelectorAll('ntx-item') || [];
                for (const item of items) {
                    const methods = item.shadowRoot?.querySelectorAll('ntx-method') || [];
                    for (const m of methods) {
                        if (m.getAttribute('method') !== 'comment') continue;
                        const btn = m.shadowRoot?.querySelector('button[type="submit"]');
                        if (btn) {
                            btn.click();
                            return true;
                        }
                    }
                }
            }
            return false;
        }""")
        page.wait_for_load_state("networkidle")
        wait_for_render_settle(page)

        print(f"\n=== REQUESTS: {len(requests_log)} (should be 1 if loop is fixed) ===")
        for i, r in enumerate(requests_log[:5]):
            print(f"  [{i}] {r['method']} {r['url']}")
            print(f"      Body: {r['body']}")

        print(f"\n=== RESPONSES: {len(responses_log)} ===")
        for i, r in enumerate(responses_log[:5]):
            print(f"  [{i}] {r['status']} {r['url']}")
            print(f"      Body: {r['body'][:100]}")

        if len(requests_log) > 3:
            print("\n*** LOOP NOT FIXED - still sending multiple requests ***")
        elif len(requests_log) == 1:
            print("\n*** LOOP FIXED - only 1 request sent ***")

        browser.close()

if __name__ == '__main__':
    test_comment()
