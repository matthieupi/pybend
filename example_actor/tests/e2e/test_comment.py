"""Playwright test to verify ntx-method loop fix and comment flow."""
from playwright.sync_api import sync_playwright
import json

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
        page.goto("http://localhost:5000/")
        page.wait_for_timeout(5000)

        # Check ntx-method exists and has correct form
        method_info = page.evaluate("""() => {
            const lists = document.querySelectorAll('ntx-list');
            for (const list of lists) {
                const items = list.shadowRoot?.querySelectorAll('ntx-item') || [];
                for (const item of items) {
                    const methods = item.shadowRoot?.querySelectorAll('ntx-method') || [];
                    for (const m of methods) {
                        const inputs = m.shadowRoot?.querySelectorAll('input') || [];
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
                        const inputs = m.shadowRoot?.querySelectorAll('input');
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

        # Click Run button
        page.evaluate("""() => {
            const lists = document.querySelectorAll('ntx-list');
            for (const list of lists) {
                const items = list.shadowRoot?.querySelectorAll('ntx-item') || [];
                for (const item of items) {
                    const methods = item.shadowRoot?.querySelectorAll('ntx-method') || [];
                    for (const m of methods) {
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

        # Wait and check - if loop is fixed, should be just 1 request
        page.wait_for_timeout(3000)

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
