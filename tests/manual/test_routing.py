"""
Test that like/reply frontend buttons POST to the correct nested API routes.
Run: python3 test_routing.py
"""
import json
import urllib.request
from playwright.sync_api import sync_playwright


def get_token():
    req = urllib.request.Request(
        'http://localhost:5000/users/login',
        data=json.dumps({"email": "alice@example.com", "password": "alice123"}).encode(),
        headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())['token']


def run():
    token = get_token()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        api_calls = []
        page.on('request', lambda req: api_calls.append(
            {'url': req.url, 'method': req.method}
        ) if any(k in req.url for k in ['/like', '/reply', '/favorite']) else None)

        errors = []
        page.on('pageerror', lambda err: errors.append(str(err)))

        page.goto('http://localhost:5000/index.html')
        page.evaluate(f"() => localStorage.setItem('jwtToken', '{token}')")
        page.reload()
        page.wait_for_timeout(6000)

        # ── Test 1: Click like button on comment ──
        print("=== Test 1: Like button on comment ===")
        click_result = page.evaluate("""() => {
            const list = document.querySelector('ntx-list');
            if (!list || !list.shadowRoot) return { error: 'no list' };
            const product = list.shadowRoot.querySelector('ntx-item');
            if (!product || !product.shadowRoot) return { error: 'no product' };
            const comment = product.shadowRoot.querySelector('ntx-item');
            if (!comment || !comment.shadowRoot) return { error: 'no comment' };
            const method = comment.shadowRoot.querySelector('ntx-method[icon="heart"]');
            if (!method) return { error: 'no heart method' };
            const ref = method.getAttribute('ref');
            const btn = method.shadowRoot ? method.shadowRoot.querySelector('.method-btn') : null;
            if (btn) btn.click();
            return { ref: ref, clicked: !!btn };
        }""")
        print(f"  Result: {json.dumps(click_result)}")
        page.wait_for_timeout(2000)

        like_calls = [c for c in api_calls if '/like' in c['url'] and c['method'] == 'POST']
        print(f"  Like POST calls: {[c['url'] for c in like_calls]}")
        like_ok = any('/Product/' in c['url'] and '/Comment/' in c['url'] for c in like_calls)
        like_bad = any('/Comment/' in c['url'] for c in like_calls)
        print(f"  Correct path: {like_ok}, Wrong path: {like_bad}")

        # ── Test 2: Reply to comment ──
        print("\n=== Test 2: Reply button on comment ===")
        # Click reply button to show input
        page.evaluate("""() => {
            const list = document.querySelector('ntx-list');
            const product = list.shadowRoot.querySelector('ntx-item');
            const comment = product.shadowRoot.querySelector('ntx-item');
            const btn = comment.shadowRoot.querySelector('.sm-reply-btn');
            if (btn) btn.click();
        }""")
        page.wait_for_timeout(500)

        # Type and submit
        page.evaluate("""() => {
            const list = document.querySelector('ntx-list');
            const product = list.shadowRoot.querySelector('ntx-item');
            const comment = product.shadowRoot.querySelector('ntx-item');
            const input = comment.shadowRoot.querySelector('.reply-input');
            const btn = comment.shadowRoot.querySelector('.reply-submit-btn');
            if (input && btn) {
                input.value = 'Test reply from frontend';
                btn.click();
            }
        }""")
        page.wait_for_timeout(2000)

        reply_calls = [c for c in api_calls if '/reply' in c['url'] and c['method'] == 'POST']
        print(f"  Reply POST calls: {[c['url'] for c in reply_calls]}")
        reply_ok = any('/Product/' in c['url'] and '/Comment/' in c['url'] for c in reply_calls)
        reply_bad = any('/Comment/' in c['url'] for c in reply_calls)
        print(f"  Correct path: {reply_ok}, Wrong path: {reply_bad}")

        # ── Test 3: Favorite on product ──
        print("\n=== Test 3: Favorite button on product ===")
        page.evaluate("""() => {
            const list = document.querySelector('ntx-list');
            const product = list.shadowRoot.querySelector('ntx-item');
            const method = product.shadowRoot.querySelector('ntx-method[icon="star"]');
            if (method && method.shadowRoot) {
                const btn = method.shadowRoot.querySelector('.method-btn');
                if (btn) btn.click();
            }
        }""")
        page.wait_for_timeout(2000)

        fav_calls = [c for c in api_calls if '/favorite' in c['url'] and c['method'] == 'POST']
        print(f"  Favorite POST calls: {[c['url'] for c in fav_calls]}")
        fav_ok = any('/Product/' in c['url'] for c in fav_calls)
        print(f"  Correct path: {fav_ok}")

        # ── Errors ──
        print(f"\nPage errors: {len(errors)}")
        for e in errors[:5]:
            print(f"  {e[:200]}")

        browser.close()

        # ── Summary ──
        all_ok = like_ok and not like_bad and reply_ok and not reply_bad and fav_ok
        print(f"\n{'='*50}")
        if all_ok:
            print("ALL URL ROUTING CORRECT")
        else:
            print("URL ROUTING ISSUES FOUND")
            if not like_ok or like_bad:
                print("  - Like button routes incorrectly")
            if not reply_ok or reply_bad:
                print("  - Reply routes incorrectly")
            if not fav_ok:
                print("  - Favorite routes incorrectly")
        return 0 if all_ok else 1


if __name__ == '__main__':
    exit(run())
