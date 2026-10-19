"""Playwright test to verify product comment submission fires once."""
from playwright.sync_api import sync_playwright


BASE = "http://localhost:5000"


def _wait_for_comment_method(page, timeout=10000):
    page.wait_for_function("""() => {
        const lists = document.querySelectorAll('ntx-list');
        for (const list of lists) {
            const items = list.shadowRoot?.querySelectorAll('ntx-item') || [];
            for (const item of items) {
                const methods = item.shadowRoot?.querySelectorAll('ntx-method') || [];
                for (const m of methods) {
                    if (m.getAttribute('method') !== 'comment') continue;
                    const btn = m.shadowRoot?.querySelector('button[type="submit"], .method-btn');
                    const input = m.shadowRoot?.querySelector('textarea, input');
                    if (btn && input) return true;
                }
            }
        }
        return false;
    }""", timeout=timeout)


def _login(page, email="alice@example.com", password="alice123"):
    token = page.evaluate("""async (args) => {
        const resp = await fetch('/users/login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({email: args.email, password: args.password}),
        });
        const data = await resp.json();
        const payload = data.data || data.result || data;
        const token = payload.token || (payload.data && payload.data.token);
        window.localStorage.setItem('jwtToken', token);
        return token;
    }""", {'email': email, 'password': password})
    assert token, 'Login did not return a token'


def test_comment_submits_once():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        requests_log = []
        responses_log = []

        def on_request(req):
            if 'comment' in req.url.lower() and req.method == 'POST':
                requests_log.append({
                    'url': req.url,
                    'method': req.method,
                    'body': req.post_data,
                })

        def on_response(resp):
            if 'comment' in resp.url.lower() and resp.request.method == 'POST':
                responses_log.append({
                    'url': resp.url,
                    'status': resp.status,
                })

        page.on("request", on_request)
        page.on("response", on_response)

        page.goto(f"{BASE}/")
        _login(page)
        page.reload()
        _wait_for_comment_method(page)

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
                            inputTags: Array.from(inputs).map(i => i.tagName.toLowerCase()),
                        };
                    }
                }
            }
            return null;
        }""")

        assert method_info is not None, "Comment method not found"
        assert method_info['method'] == 'comment'
        assert method_info['inputCount'] >= 1
        assert 'textarea' in method_info['inputTags'] or 'input' in method_info['inputTags']

        filled = page.evaluate("""() => {
            const lists = document.querySelectorAll('ntx-list');
            for (const list of lists) {
                const items = list.shadowRoot?.querySelectorAll('ntx-item') || [];
                for (const item of items) {
                    const methods = item.shadowRoot?.querySelectorAll('ntx-method') || [];
                    for (const m of methods) {
                        if (m.getAttribute('method') !== 'comment') continue;
                        const input = m.shadowRoot?.querySelector('textarea, input');
                        if (!input) return false;
                        input.value = 'Test Comment';
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                        return true;
                    }
                }
            }
            return false;
        }""")
        assert filled is True, "Failed to fill comment input"

        with page.expect_response(lambda resp: 'comment' in resp.url.lower()
                                  and resp.request.method == 'POST'):
            clicked = page.evaluate("""() => {
                const lists = document.querySelectorAll('ntx-list');
                for (const list of lists) {
                    const items = list.shadowRoot?.querySelectorAll('ntx-item') || [];
                    for (const item of items) {
                        const methods = item.shadowRoot?.querySelectorAll('ntx-method') || [];
                        for (const m of methods) {
                            if (m.getAttribute('method') !== 'comment') continue;
                            const btn = m.shadowRoot?.querySelector('button[type="submit"], .method-btn');
                            if (!btn) return false;
                            btn.click();
                            return true;
                        }
                    }
                }
                return false;
            }""")
        assert clicked is True, "Failed to click comment submit button"

        assert len(requests_log) == 1, requests_log
        assert len(responses_log) == 1, responses_log
        assert responses_log[0]['status'] in (200, 201), responses_log

        browser.close()


if __name__ == '__main__':
    test_comment_submits_once()
