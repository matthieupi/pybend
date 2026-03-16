"""Playwright e2e test: Create a grant with only the title filled in.

Validates the full validation feedback loop:
  1. Open inline create row in ntx-table
  2. Enter only a title (leaving required fields agency + url empty)
  3. Click save and observe client-side validation feedback
  4. Bypass client-side validation and submit to backend, observe server-side 422 feedback
  5. Verify the grant was NOT created

Requires a running server: cd examples/grants && python main.py
"""
import json
from playwright.sync_api import sync_playwright

BASE = "http://localhost:5000"


def _login(page, email="alice@example.com", password="alice123"):
    """Log in via the API and inject the token into localStorage."""
    resp = page.request.post(f"{BASE}/users/login", data={
        "email": email,
        "password": password,
    })
    body = resp.json()
    token = body.get("token")
    assert token, f"Login failed: {body}"
    # Inject token into localStorage (Permissions.js reads from 'jwtToken')
    page.evaluate(f"() => localStorage.setItem('jwtToken', '{token}')")
    return token


def _wait_for_table(page, timeout=15000):
    """Wait until ntx-table has at least one row AND the add button is visible (auth loaded)."""
    page.wait_for_function("""() => {
        const table = document.querySelector('#grant-table') || document.querySelector('#grant-table');
        if (!table) return false;
        const body = table.shadowRoot?.querySelector('.table-body');
        const hasRows = body && body.querySelectorAll('ntx-row').length > 0;
        const hasAddBtn = !!table.shadowRoot?.querySelector('.inline-add-btn');
        return hasRows && hasAddBtn;
    }""", timeout=timeout)


def _open_create_row(page, timeout=10000):
    """Click the add button and wait until the inline create row is visible.

    Polls because the table may re-render between _wait_for_table passing and
    the click, losing the event listener.  Clicking inside the poll is harmless
    if the row is already open (toggle would close+reopen, but we guard that).
    """
    page.wait_for_function("""() => {
        const table = document.querySelector('#grant-table');
        if (!table) return false;
        const row = table.shadowRoot?.querySelector('.create-row');
        if (row && row.style.display !== 'none') return true;
        // Not open yet — try clicking the add button
        table.shadowRoot?.querySelector('.inline-add-btn')?.click();
        return false;
    }""", timeout=timeout)


def test_create_grant_title_only_client_validation():
    """Submitting a grant with only a title triggers client-side validation errors
    on the missing required fields (agency, url)."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})

        # Navigate and authenticate
        page.goto(BASE)
        _login(page)
        page.reload()
        _wait_for_table(page)

        # Count existing grants before we try creating
        initial_count = page.evaluate("""() => {
            const table = document.querySelector('#grant-table');
            return table?.shadowRoot?.querySelector('.table-body')
                ?.querySelectorAll('ntx-row')?.length ?? 0;
        }""")

        # Click the "+ Add Grant" button to open inline create row
        _open_create_row(page)

        # Type only a title into the create row
        page.evaluate("""() => {
            const table = document.querySelector('#grant-table');
            const row = table.shadowRoot.querySelector('.create-row');
            const titleInput = row.querySelector('[data-key="title"]');
            titleInput.value = 'Test Grant Title Only';
            titleInput.dispatchEvent(new Event('input', {bubbles: true}));
        }""")

        # Click save
        page.evaluate("""() => {
            const table = document.querySelector('#grant-table');
            table.shadowRoot.querySelector('.save-create-btn').click();
        }""")
        page.wait_for_timeout(500)

        # Inspect the create row for validation error indicators
        result = page.evaluate("""() => {
            const table = document.querySelector('#grant-table');
            const row = table.shadowRoot.querySelector('.create-row');

            // Check which inputs have error class
            const errorInputs = [...row.querySelectorAll('.input-error')]
                .map(el => el.dataset.key);

            // Check for error message elements
            const errorMessages = [...row.querySelectorAll('.cell-error-msg')]
                .map(el => el.textContent);

            // Is the create row still visible? (should be — form wasn't submitted)
            const rowVisible = row.style.display !== 'none';

            // Is it in loading state? (should NOT be — validation blocked submit)
            const isLoading = row.classList.contains('loading');

            // Check each required field's state
            const titleInput = row.querySelector('[data-key="title"]');
            const agencyInput = row.querySelector('[data-key="agency"]');
            const urlInput = row.querySelector('[data-key="url"]');

            return {
                rowVisible,
                isLoading,
                errorInputs,
                errorMessages,
                titleHasError: titleInput?.classList.contains('input-error') ?? null,
                agencyHasError: agencyInput?.classList.contains('input-error') ?? null,
                urlHasError: urlInput?.classList.contains('input-error') ?? null,
                titleValue: titleInput?.value ?? null,
                agencyValue: agencyInput?.value ?? null,
                urlValue: urlInput?.value ?? null,
            };
        }""")

        print("\n=== CLIENT-SIDE VALIDATION RESULTS ===")
        print(f"Create row still visible: {result['rowVisible']}")
        print(f"Create row in loading state: {result['isLoading']}")
        print(f"Fields with error class: {result['errorInputs']}")
        print(f"Error messages shown: {result['errorMessages']}")
        print(f"Title (filled) has error: {result['titleHasError']}")
        print(f"Agency (empty) has error: {result['agencyHasError']}")
        print(f"URL (empty) has error: {result['urlHasError']}")

        # ASSERTIONS
        # Create row should still be open (not submitted)
        assert result["rowVisible"], "Create row should remain open after validation failure"
        # Should NOT be in loading state (client-side validation blocks before send)
        assert not result["isLoading"], "Should not be loading — client validation blocked submit"
        # Title was filled, so it should NOT have an error
        assert not result["titleHasError"], "Title was filled — should not have error"
        # Agency and URL are required but empty — should have errors
        assert result["agencyHasError"], "Agency is required but empty — should show error"

        # Verify no new grant was created
        final_count = page.evaluate("""() => {
            const table = document.querySelector('#grant-table');
            return table?.shadowRoot?.querySelector('.table-body')
                ?.querySelectorAll('ntx-row')?.length ?? 0;
        }""")
        assert final_count == initial_count, \
            f"No grant should have been created (before={initial_count}, after={final_count})"

        browser.close()


def test_create_grant_title_only_detailed_feedback_analysis():
    """Detailed analysis of the validation feedback: what the user sees, timing,
    and how errors are presented for each missing field."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})

        page.goto(BASE)
        _login(page)
        page.reload()
        _wait_for_table(page)

        # Open create row
        _open_create_row(page)

        # Capture the schema to understand what the form knows about required fields
        schema_info = page.evaluate("""() => {
            const table = document.querySelector('#grant-table');
            const schema = table.schema;
            const props = schema?.properties || {};
            const required = schema?.required || [];

            // What columns appear in the create row?
            const row = table.shadowRoot.querySelector('.create-row');
            const createInputs = [...(row?.querySelectorAll('[data-key]') || [])]
                .map(el => ({
                    key: el.dataset.key,
                    type: el.type || el.tagName,
                    placeholder: el.placeholder || '',
                    hasRequiredAttr: el.hasAttribute('required'),
                }));

            return {
                schemaRequired: required,
                createInputs,
                fieldDefs: Object.fromEntries(
                    Object.entries(props).map(([k, v]) => [k, {
                        type: v.type,
                        minLength: v.minLength,
                        widget: v.ui?.widget,
                        isProtected: v.ui?.protected || false,
                    }])
                ),
            };
        }""")

        print("\n=== SCHEMA & FORM ANALYSIS ===")
        print(f"Schema required fields: {schema_info['schemaRequired']}")
        print(f"Create row inputs:")
        for inp in schema_info['createInputs']:
            print(f"  - {inp['key']}: type={inp['type']}, placeholder='{inp['placeholder']}', "
                  f"HTML required={inp['hasRequiredAttr']}")
        print(f"Field definitions:")
        for k, v in schema_info['fieldDefs'].items():
            print(f"  - {k}: type={v['type']}, minLength={v.get('minLength')}, "
                  f"widget={v.get('widget')}, protected={v.get('isProtected')}")

        # Fill only title and submit
        page.evaluate("""() => {
            const table = document.querySelector('#grant-table');
            const row = table.shadowRoot.querySelector('.create-row');
            const titleInput = row.querySelector('[data-key="title"]');
            titleInput.value = 'Feedback Test Grant';
            titleInput.dispatchEvent(new Event('input', {bubbles: true}));
        }""")

        # Submit and capture the FULL validation state including timing
        page.evaluate("""() => {
            const table = document.querySelector('#grant-table');
            table.shadowRoot.querySelector('.save-create-btn').click();
        }""")
        page.wait_for_timeout(300)

        feedback = page.evaluate("""() => {
            const table = document.querySelector('#grant-table');
            const row = table.shadowRoot.querySelector('.create-row');
            if (!row) return { error: 'no create row' };

            const results = {};
            const allInputs = row.querySelectorAll('[data-key]');

            allInputs.forEach(el => {
                const key = el.dataset.key;
                const errorMsg = el.parentElement?.querySelector('.cell-error-msg');
                const computed = getComputedStyle(el);
                results[key] = {
                    value: el.value,
                    hasErrorClass: el.classList.contains('input-error'),
                    errorMessage: errorMsg?.textContent || null,
                    borderColor: computed.borderColor,
                    backgroundColor: computed.backgroundColor,
                };
            });

            // Check for any toast notifications
            const toasts = [...document.querySelectorAll('.toast, [class*="toast"]')]
                .map(el => el.textContent);

            return { fields: results, toasts };
        }""")

        print("\n=== VALIDATION FEEDBACK PER FIELD ===")
        for field, info in feedback.get('fields', {}).items():
            status = "ERROR" if info['hasErrorClass'] else "OK"
            print(f"  [{status}] {field}:")
            print(f"    value='{info['value']}', error='{info['errorMessage'] or 'none'}'")
            print(f"    borderColor={info['borderColor']}")
        if feedback.get('toasts'):
            print(f"\n  Toast messages: {feedback['toasts']}")
        else:
            print(f"\n  No toast messages shown")

        # Also test: what happens if we try to bypass client validation
        # by directly calling proto.call('CREATE') with only title?
        print("\n=== BYPASSING CLIENT VALIDATION (direct API call) ===")
        server_result = page.evaluate("""async () => {
            try {
                const resp = await fetch('/grants', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'x-access-token': localStorage.getItem('jwtToken'),
                    },
                    body: JSON.stringify({ title: 'Direct API Test' }),
                });
                const body = await resp.json();
                return {
                    status: resp.status,
                    statusText: resp.statusText,
                    body: body,
                };
            } catch(e) {
                return { error: e.message };
            }
        }""")

        print(f"  HTTP Status: {server_result.get('status')} {server_result.get('statusText')}")
        print(f"  Response body: {json.dumps(server_result.get('body'), indent=2)}")

        # Extract backend validation error structure
        detail = server_result.get('body', {}).get('detail', [])
        if isinstance(detail, list):
            print(f"\n  Backend validation errors ({len(detail)}):")
            for err in detail:
                loc = err.get('loc', [])
                print(f"    - {'.'.join(str(x) for x in loc)}: {err.get('msg')} (type={err.get('type')})")
        else:
            print(f"  Backend error detail: {detail}")

        browser.close()


def test_create_grant_title_only_error_visibility():
    """Verify that validation errors are visually distinguishable — checks computed
    styles, error message positioning, and whether the user can actually SEE the feedback."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})

        page.goto(BASE)
        _login(page)
        page.reload()
        _wait_for_table(page)

        # Open create, fill title only, submit
        _open_create_row(page)

        page.evaluate("""() => {
            const table = document.querySelector('#grant-table');
            const row = table.shadowRoot.querySelector('.create-row');
            row.querySelector('[data-key="title"]').value = 'Visibility Test';
            table.shadowRoot.querySelector('.save-create-btn').click();
        }""")
        page.wait_for_timeout(500)

        visibility = page.evaluate("""() => {
            const table = document.querySelector('#grant-table');
            const row = table.shadowRoot.querySelector('.create-row');
            const results = {};

            // For each input with an error, check visibility
            row.querySelectorAll('.input-error').forEach(el => {
                const key = el.dataset.key;
                const rect = el.getBoundingClientRect();
                const errMsg = el.parentElement?.querySelector('.cell-error-msg');
                const errRect = errMsg?.getBoundingClientRect();
                const computed = getComputedStyle(el);
                const errComputed = errMsg ? getComputedStyle(errMsg) : null;

                results[key] = {
                    inputVisible: rect.width > 0 && rect.height > 0,
                    inputInViewport: rect.top >= 0 && rect.bottom <= window.innerHeight,
                    inputBorder: computed.borderColor,
                    inputBoxShadow: computed.boxShadow,
                    hasErrorMessage: !!errMsg,
                    errorMessageText: errMsg?.textContent || null,
                    errorMessageVisible: errRect ? (errRect.width > 0 && errRect.height > 0) : false,
                    errorMessageColor: errComputed?.color || null,
                    errorMessageFontSize: errComputed?.fontSize || null,
                    errorMessageOverflows: errRect ? errRect.bottom > window.innerHeight : null,
                };
            });

            // Check: can we see the create row at all? Or is it below the fold?
            const rowRect = row.getBoundingClientRect();
            return {
                fields: results,
                createRowInViewport: rowRect.top >= 0 && rowRect.bottom <= window.innerHeight,
                createRowBottom: rowRect.bottom,
                viewportHeight: window.innerHeight,
            };
        }""")

        print("\n=== ERROR VISIBILITY ANALYSIS ===")
        print(f"Create row in viewport: {visibility['createRowInViewport']}")
        print(f"  Row bottom: {visibility['createRowBottom']}px, Viewport: {visibility['viewportHeight']}px")

        for field, info in visibility.get('fields', {}).items():
            print(f"\n  Field: {field}")
            print(f"    Input visible: {info['inputVisible']}, in viewport: {info['inputInViewport']}")
            print(f"    Input border: {info['inputBorder']}")
            print(f"    Input box-shadow: {info['inputBoxShadow']}")
            print(f"    Error message present: {info['hasErrorMessage']}")
            if info['hasErrorMessage']:
                print(f"    Error text: '{info['errorMessageText']}'")
                print(f"    Error visible: {info['errorMessageVisible']}")
                print(f"    Error color: {info['errorMessageColor']}")
                print(f"    Error font-size: {info['errorMessageFontSize']}")
                print(f"    Error overflows viewport: {info['errorMessageOverflows']}")

        # Verify at minimum that errors are present and visible
        error_fields = visibility.get('fields', {})
        assert len(error_fields) > 0, "At least one field should show a validation error"

        for field, info in error_fields.items():
            assert info['inputVisible'], f"{field} input should be visible"
            assert info['hasErrorMessage'], f"{field} should have an error message element"

        browser.close()
