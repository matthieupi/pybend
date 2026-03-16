"""Playwright e2e tests for list-to-detail navigation.

Validates:
  1. Main list items navigate to detail view on click (hash + router chrome + detail item)
  2. Sidebar items navigate to detail view on click
  3. Back button returns to the list view
  4. Hash-based deep linking works (navigate directly via URL hash)

Requires a running server: cd examples/grants && python main.py
"""
import json
from playwright.sync_api import sync_playwright

BASE = "http://localhost:5000"


def _login(page, email="alice@example.com", password="alice123"):
    """Log in via the API and inject the token into localStorage."""
    resp = page.request.post(f"{BASE}/users/login", data={
        "email": email, "password": password,
    })
    body = resp.json()
    token = body.get("token")
    assert token, f"Login failed: {body}"
    page.evaluate(f"() => localStorage.setItem('jwtToken', '{token}')")
    return token


def _wait_for_items(page, timeout=10000):
    """Wait until the main grant table has at least one fully-rendered row."""
    page.wait_for_function("""() => {
        const table = document.querySelector('#grant-table');
        if (!table) return false;
        const body = table.shadowRoot?.querySelector('.table-body');
        if (!body) return false;
        const rows = body.querySelectorAll('ntx-row');
        if (rows.length === 0) return false;
        // Ensure first row's shadow DOM is fully rendered
        return !!rows[0].shadowRoot?.querySelector('.row');
    }""", timeout=timeout)


def test_main_list_click_navigates():
    """Clicking an item in the main list navigates to its detail view."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(BASE)
        _login(page)
        page.reload()
        _wait_for_items(page)

        # Verify initial state: table is shown, no hash
        before = page.evaluate("""() => ({
            hash: location.hash,
            hasSlot: !!document.querySelector('ntx-router')?.shadowRoot?.querySelector('slot'),
            routerAttr: document.querySelector('#grant-table')?.getAttribute('router'),
        })""")
        assert before["hash"] == "", f"Expected no hash before click, got {before['hash']}"
        assert before["routerAttr"] == "main", "ntx-table should have router='main' set by ntx-router"

        # Click the first row
        page.evaluate("""() => {
            const table = document.querySelector('#grant-table');
            const body = table.shadowRoot.querySelector('.table-body');
            const row = body.querySelector('ntx-row');
            row.shadowRoot.querySelector('.row').click();
        }""")
        page.wait_for_timeout(1500)

        # Verify navigation occurred
        after = page.evaluate("""() => {
            const router = document.querySelector('ntx-router');
            const content = router?.shadowRoot?.querySelector('.router-content');
            const item = content?.querySelector('ntx-item');
            return {
                hash: location.hash,
                hasBackBtn: !!router?.shadowRoot?.querySelector('.back-btn'),
                routerTitle: router?.shadowRoot?.querySelector('.router-title')?.textContent,
                detailRef: item?.ref,
                detailHasSchema: !!item?.schema?.__name__,
                detailHasValue: !!item?.value && Object.keys(item.value).length > 0,
            };
        }""")
        assert after["hash"].startswith("#Grant/"), f"Expected hash like #Grant/N, got {after['hash']}"
        assert after["hasBackBtn"], "Router should show back button after navigation"
        assert after["routerTitle"] == "Grant", f"Router title should be 'Grant', got {after['routerTitle']}"
        assert after["detailRef"] is not None, "Detail item should have a ref"
        assert after["detailHasSchema"], "Detail item should have schema loaded"
        assert after["detailHasValue"], "Detail item should have value data"

        browser.close()


def test_back_button_returns_to_list():
    """Clicking the back button returns to the list view."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(BASE)
        _login(page)
        page.reload()
        _wait_for_items(page)

        # Navigate to detail
        page.evaluate("""() => {
            const table = document.querySelector('#grant-table');
            const body = table.shadowRoot.querySelector('.table-body');
            body.querySelector('ntx-row').shadowRoot.querySelector('.row').click();
        }""")
        page.wait_for_timeout(1500)

        # Click back
        page.evaluate("""() => {
            document.querySelector('ntx-router')
                .shadowRoot.querySelector('.back-btn').click();
        }""")
        page.wait_for_timeout(1000)

        # Verify we're back at the table
        after_back = page.evaluate("""() => ({
            hash: location.hash,
            hasSlot: !!document.querySelector('ntx-router')?.shadowRoot?.querySelector('slot'),
            hasBackBtn: !!document.querySelector('ntx-router')?.shadowRoot?.querySelector('.back-btn'),
            tableRowCount: document.querySelector('#grant-table')?.shadowRoot
                ?.querySelector('.table-body')?.querySelectorAll('ntx-row')?.length ?? 0,
        })""")
        assert after_back["hash"] == "", f"Hash should be empty after back, got {after_back['hash']}"
        assert after_back["hasSlot"], "Slot (table view) should be visible after back"
        assert not after_back["hasBackBtn"], "Back button should not be visible at home"
        assert after_back["tableRowCount"] > 0, "Table should still have rows after back"

        browser.close()


def test_hash_deep_link():
    """Navigating directly to a hash URL shows the detail view."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        # Login first (detail view hydrates user_owner FK which requires auth)
        page.goto(BASE)
        _login(page)
        page.goto(f"{BASE}/#Grant/1")
        page.wait_for_timeout(6000)

        state = page.evaluate("""() => {
            const router = document.querySelector('ntx-router');
            const content = router?.shadowRoot?.querySelector('.router-content');
            const item = content?.querySelector('ntx-item');
            return {
                hasBackBtn: !!router?.shadowRoot?.querySelector('.back-btn'),
                routerTitle: router?.shadowRoot?.querySelector('.router-title')?.textContent,
                detailRef: item?.ref,
                detailHasValue: !!item?.value && Object.keys(item.value).length > 0,
            };
        }""")
        assert state["hasBackBtn"], "Should show back button on deep link"
        assert state["routerTitle"] == "Grant", "Title should be 'Grant'"
        assert state["detailRef"] == "Grant/1", f"Detail ref should be Grant/1, got {state['detailRef']}"
        assert state["detailHasValue"], "Detail should have loaded data"

        browser.close()


def test_sidebar_item_navigates():
    """Clicking an item in the sidebar list navigates to detail view."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(BASE)
        _login(page)
        page.reload()
        _wait_for_items(page)

        # Expand the sidebar's first model section (Grant)
        page.evaluate("""() => {
            const sidebar = document.querySelector('ntx-sidebar');
            const header = sidebar.shadowRoot.querySelector('.model-header');
            header.click();
        }""")
        page.wait_for_timeout(3000)

        # Check that the sidebar list has router attribute
        sidebar_info = page.evaluate("""() => {
            const sidebar = document.querySelector('ntx-sidebar');
            const list = sidebar.shadowRoot.querySelector('ntx-list');
            if (!list) return { error: 'No list in sidebar' };
            const grid = list.shadowRoot?.querySelector('.list-grid');
            return {
                routerAttr: list.getAttribute('router'),
                headless: list.hasAttribute('headless'),
                itemCount: grid?.querySelectorAll('ntx-item')?.length ?? 0,
            };
        }""")
        assert sidebar_info.get("routerAttr") == "main", \
            f"Sidebar list should have router='main', got {sidebar_info.get('routerAttr')}"
        assert sidebar_info.get("headless"), "Sidebar list should be headless"

        if sidebar_info.get("itemCount", 0) == 0:
            browser.close()
            return  # Skip click test if no items (no seed data)

        # Click the first sidebar item
        page.evaluate("""() => {
            const sidebar = document.querySelector('ntx-sidebar');
            const list = sidebar.shadowRoot.querySelector('ntx-list');
            const grid = list.shadowRoot.querySelector('.list-grid');
            grid.querySelector('ntx-item').shadowRoot.querySelector('.card').click();
        }""")
        page.wait_for_timeout(2000)

        after = page.evaluate("""() => ({
            hash: location.hash,
            hasBackBtn: !!document.querySelector('ntx-router')?.shadowRoot?.querySelector('.back-btn'),
            routerTitle: document.querySelector('ntx-router')?.shadowRoot
                ?.querySelector('.router-title')?.textContent,
        })""")
        assert after["hash"].startswith("#Grant/"), \
            f"Hash should start with #Grant/ after sidebar click, got {after['hash']}"
        assert after["hasBackBtn"], "Should show back button after sidebar navigation"
        assert after["routerTitle"] == "Grant", "Router title should be 'Grant'"

        browser.close()
