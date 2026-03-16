"""
Playwright test for social features: like, favorite, reply, collection routes.
Run: python3 test_social.py
Requires server running on localhost:5000 with seeded data.
"""
import json
import sys


def get_token():
    """Get JWT token via API"""
    import urllib.request
    req = urllib.request.Request(
        'http://localhost:5000/users/login',
        data=json.dumps({"email": "alice@example.com", "password": "alice123"}).encode(),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())['token']


def run_tests():
    from playwright.sync_api import sync_playwright

    token = get_token()
    print(f"Got JWT token: {token[:20]}...")
    passed = 0
    failed = 0

    def check(name, condition, detail=""):
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"  PASS: {name}")
        else:
            failed += 1
            print(f"  FAIL: {name} — {detail}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        errors = []
        page.on('pageerror', lambda err: errors.append(str(err)))

        # ── Set token and go to matrix ──
        print("\n=== API Tests (via Playwright fetch) ===")
        page.goto('http://localhost:5000/index.html')
        page.evaluate(f"() => localStorage.setItem('jwtToken', '{token}')")
        page.reload()
        page.wait_for_timeout(3000)

        # 1. Product schema
        schema_resp = page.evaluate("""() => fetch('/Product').then(r => r.json())""")
        methods = list(schema_resp.get('methods', {}).keys())
        check("Product has 'comment' method", 'comment' in methods, f"got {methods}")
        check("Product has 'favorite' method", 'favorite' in methods, f"got {methods}")
        check("Product has 'favorites' property", 'favorites' in schema_resp.get('properties', {}))

        # 2. Comment schema (via ProductComment)
        comment_schema = page.evaluate("""() => fetch('/ProductComment').then(r => r.json())""")
        cmethods = list(comment_schema.get('methods', {}).keys())
        check("Comment has 'like' method", 'like' in cmethods, f"got {cmethods}")
        check("Comment has 'reply' method", 'reply' in cmethods, f"got {cmethods}")

        # 3. Favorite toggle
        fav1 = page.evaluate("""(token) => fetch('/products/1/favorite', {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'x-access-token': token},
            body: '{}'
        }).then(r => r.json()).then(r => typeof r === 'string' ? JSON.parse(r) : r)""", token)
        check("Favorite returns action", 'action' in fav1, f"got {fav1}")
        fav2 = page.evaluate("""(token) => fetch('/products/1/favorite', {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'x-access-token': token},
            body: '{}'
        }).then(r => r.json()).then(r => typeof r === 'string' ? JSON.parse(r) : r)""", token)
        check("Favorite toggles", fav1.get('action') != fav2.get('action'),
              f"{fav1.get('action')} → {fav2.get('action')}")

        # 4. Like toggle
        like1 = page.evaluate("""(token) => fetch('/products/1/comments/1/like', {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'x-access-token': token},
            body: '{}'
        }).then(r => r.json()).then(r => typeof r === 'string' ? JSON.parse(r) : r)""", token)
        check("Like returns action", 'action' in like1, f"got {like1}")

        # 5. Reply
        reply = page.evaluate("""(token) => fetch('/products/1/comments/2/reply', {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'x-access-token': token},
            body: JSON.stringify({text: 'Playwright reply'})
        }).then(r => r.json()).then(r => typeof r === 'string' ? JSON.parse(r) : r)""", token)
        check("Reply has correct name", reply.get('name') == 'Playwright reply', f"got {reply.get('name')}")
        check("Reply has parent_id=2", reply.get('parent_id') == 2, f"got {reply.get('parent_id')}")
        check("Reply has non-zero id", reply.get('id', 0) > 0, f"got id={reply.get('id')}")

        # 6. Collection routes
        likes_raw = page.evaluate("""(token) => fetch('/products/likes', {
            headers: {'x-access-token': token}
        }).then(r => r.ok ? r.json() : {error: r.status})""", token)
        check("Collection /products/likes returns list",
              isinstance(likes_raw, list), f"got {str(likes_raw)[:200]}")

        comments_raw = page.evaluate("""(token) => fetch('/products/comments', {
            headers: {'x-access-token': token}
        }).then(r => r.ok ? r.json() : {error: r.status})""", token)
        check("Collection /products/comments returns list",
              isinstance(comments_raw, list), f"got {str(comments_raw)[:200]}")

        # ── Frontend rendering tests ──
        print("\n=== Frontend Rendering Tests ===")
        page.goto('http://localhost:5000/index.html')
        page.evaluate(f"() => localStorage.setItem('jwtToken', '{token}')")
        page.reload()
        page.wait_for_timeout(6000)

        # 7. Page structure
        page_state = page.evaluate("""() => ({
            router: !!document.querySelector('ntx-router'),
            topbar: !!document.querySelector('ntx-topbar'),
        })""")
        check("ntx-router present", page_state.get('router'))
        check("ntx-topbar present", page_state.get('topbar'))

        # 8. Topbar Favorites link
        has_fav_link = page.evaluate("""() => {
            const tb = document.querySelector('ntx-topbar');
            return !!tb?.shadowRoot?.querySelector('a[href="#@favorites"]');
        }""")
        check("Favorites link in topbar", has_fav_link)

        # 9. ntx-list rendered with products
        # The ntx-router contains an ntx-list, but it might be in shadow DOM or slotted
        list_info = page.evaluate("""() => {
            // Try direct child first
            let list = document.querySelector('ntx-list');
            // If not found, check inside ntx-router shadow
            if (!list) {
                const router = document.querySelector('ntx-router');
                list = router?.shadowRoot?.querySelector('ntx-list');
            }
            if (!list) return { found: false };
            const sr = list.shadowRoot;
            if (!sr) return { found: true, shadow: false };
            const items = sr.querySelectorAll('ntx-item');
            return { found: true, shadow: true, itemCount: items.length };
        }""")
        check("ntx-list found", list_info.get('found'), f"state={list_info}")
        if list_info.get('found') and list_info.get('shadow'):
            check("Products rendered", list_info.get('itemCount', 0) > 0,
                  f"{list_info.get('itemCount')} items")

        # 10. Favorite button (star) on product items
        star_info = page.evaluate("""() => {
            // Find first product ntx-item
            const list = document.querySelector('ntx-list');
            if (!list?.shadowRoot) return { found: false, reason: 'no list' };
            const item = list.shadowRoot.querySelector('ntx-item');
            if (!item?.shadowRoot) return { found: false, reason: 'no item' };
            // Look for ntx-method with icon=star
            const method = item.shadowRoot.querySelector('ntx-method[icon="star"]');
            if (!method) {
                // Check all ntx-methods
                const all = Array.from(item.shadowRoot.querySelectorAll('ntx-method'));
                return { found: false, reason: `${all.length} ntx-methods, none with icon=star`,
                         attrs: all.map(m => ({icon: m.getAttribute('icon'), method: m.getAttribute('method')})) };
            }
            // Check the button inside shadow
            const btn = method.shadowRoot?.querySelector('.method-btn');
            return { found: true, hasBtn: !!btn };
        }""")
        check("Star (favorite) button on product", star_info.get('found'),
              f"detail={json.dumps(star_info)}")

        # 11. Heart button (like) on comment items
        heart_info = page.evaluate("""() => {
            // Comments are nested inside product items
            const list = document.querySelector('ntx-list');
            if (!list?.shadowRoot) return { found: false, reason: 'no list' };
            const item = list.shadowRoot.querySelector('ntx-item');
            if (!item?.shadowRoot) return { found: false, reason: 'no product item' };
            // Look for nested ntx-item (comments)
            const commentItems = item.shadowRoot.querySelectorAll('ntx-item');
            if (!commentItems.length) return { found: false, reason: 'no comment items' };
            // Check first comment for heart button
            const comment = commentItems[0];
            if (!comment.shadowRoot) return { found: false, reason: 'comment has no shadow' };
            const method = comment.shadowRoot.querySelector('ntx-method[icon="heart"]');
            return { found: !!method, commentCount: commentItems.length };
        }""")
        check("Heart (like) button on comment", heart_info.get('found'),
              f"detail={json.dumps(heart_info)}")

        # 12. Reply button on comments
        reply_info = page.evaluate("""() => {
            const list = document.querySelector('ntx-list');
            if (!list?.shadowRoot) return { found: false, reason: 'no list' };
            const item = list.shadowRoot.querySelector('ntx-item');
            if (!item?.shadowRoot) return { found: false, reason: 'no product item' };
            const commentItems = item.shadowRoot.querySelectorAll('ntx-item');
            if (!commentItems.length) return { found: false, reason: 'no comment items' };
            const comment = commentItems[0];
            if (!comment.shadowRoot) return { found: false, reason: 'comment has no shadow' };
            // Reply button or inline reply method
            const replyBtn = comment.shadowRoot.querySelector('.sm-reply-btn');
            const replyMethod = comment.shadowRoot.querySelector('ntx-method[method="reply"]');
            return { found: !!(replyBtn || replyMethod), hasBtn: !!replyBtn, hasMethod: !!replyMethod };
        }""")
        check("Reply button on comment", reply_info.get('found'),
              f"detail={json.dumps(reply_info)}")

        # 13. Reply indent (comments with parent_id have indent class)
        indent_info = page.evaluate("""() => {
            const list = document.querySelector('ntx-list');
            if (!list?.shadowRoot) return { found: false, reason: 'no list' };
            const items = list.shadowRoot.querySelectorAll('ntx-item');
            let indented = 0;
            let total = 0;
            for (const item of items) {
                total++;
                if (item.shadowRoot?.querySelector('.reply-indent')) indented++;
            }
            // Also check nested comments inside product items
            for (const item of items) {
                if (!item.shadowRoot) continue;
                const nested = item.shadowRoot.querySelectorAll('ntx-item');
                for (const n of nested) {
                    total++;
                    if (n.shadowRoot?.querySelector('.reply-indent')) indented++;
                }
            }
            return { indented, total };
        }""")
        # We should have some indented replies from seed data
        check("Reply indent CSS applied", indent_info.get('indented', 0) > 0,
              f"{indent_info.get('indented', 0)} indented out of {indent_info.get('total', 0)}")

        # 14. Navigate to favorites
        page.evaluate("""() => {
            const tb = document.querySelector('ntx-topbar');
            tb?.shadowRoot?.querySelector('a[href="#@favorites"]')?.click();
        }""")
        page.wait_for_timeout(2000)
        fav_url = page.url
        check("Favorites URL", '@favorites' in fav_url or 'favorites' in fav_url, f"url={fav_url}")

        # 15. Console errors
        stack_overflows = sum(1 for e in errors if 'Maximum call stack' in e)
        other = [e for e in errors if 'Maximum call stack' not in e]
        check("No stack overflow errors", stack_overflows == 0,
              f"{stack_overflows} stack overflows")
        if other:
            print(f"  INFO: {len(other)} other console errors:")
            for e in other[:5]:
                print(f"    - {e[:150]}")

        browser.close()

        print(f"\n{'='*50}")
        print(f"Results: {passed} passed, {failed} failed, {passed+failed} total")
        if failed:
            print("SOME TESTS FAILED")
            sys.exit(1)
        print("ALL TESTS PASSED")


if __name__ == '__main__':
    run_tests()
