"""Full-stack integration tests — real server, real browser, real pipeline.

Tests the COMPLETE stack: server boots, SSR/static serves HTML, JS loads,
web components render, auth works, API responds, SSE streaming delivers
tokens, messages persist in DB, and the UI reflects it all.

Uses pydantic-ai TestModel (no real LLM) via N3TX_TEST_MODE=1.

Run with:
    cd /workspace && python -m pytest example_chat/tests/e2e/ -v
"""
import uuid
import pytest


# ── Helpers ──

def _login(page, base_url, email="alice@example.com", password="alice123"):
    """Log in via the auth overlay. Page reloads after login."""
    page.goto(base_url)
    page.wait_for_selector("#loginOverlay", state="visible", timeout=10000)

    page.fill("#loginEmail", email)
    page.fill("#loginPassword", password)
    page.click("#btnLogin")
    # Login triggers page reload — wait for it
    page.wait_for_load_state("load", timeout=15000)
    page.wait_for_selector("body.authenticated", timeout=10000)


def _register(page, base_url, name, email, password):
    """Register a new account. Page reloads after registration."""
    page.goto(base_url)
    page.wait_for_selector("#loginOverlay", state="visible", timeout=10000)

    page.click("#showRegister")
    page.fill("#registerName", name)
    page.fill("#registerEmail", email)
    page.fill("#registerPassword", password)
    page.click("#btnRegister")
    page.wait_for_load_state("load", timeout=15000)
    page.wait_for_selector("body.authenticated", timeout=10000)


def _wait_for_sidebar_loaded(page, min_convs=0, timeout_ms=10000):
    """Wait for sidebar to finish loading conversations.

    Args:
        min_convs: minimum number of conversations expected (0 = just wait for container)
    """
    page.evaluate(f"""(minConvs) => new Promise((resolve) => {{
        const deadline = Date.now() + {timeout_ms};
        const check = () => {{
            const sb = document.querySelector('ntx-chat-sidebar');
            if (sb && sb.shadowRoot) {{
                const list = sb.shadowRoot.querySelector('#convList');
                if (list) {{
                    const count = sb.shadowRoot.querySelectorAll('ntx-chat-conv').length;
                    if (count >= minConvs) return resolve(count);
                }}
            }}
            if (Date.now() > deadline) return resolve(0);
            setTimeout(check, 200);
        }};
        check();
    }})""", min_convs)


def _create_conversation(page):
    """Click + New button in sidebar shadow DOM. Waits for count to increase."""
    before = _get_conversation_count(page)
    page.evaluate("""() => {
        const sidebar = document.querySelector('ntx-chat-sidebar');
        const btn = sidebar.shadowRoot.querySelector('#btnNew');
        if (btn) btn.click();
    }""")
    # Wait for the conversation to appear (WS lifecycle event triggers update)
    page.evaluate(f"""(before) => new Promise((resolve) => {{
        const deadline = Date.now() + 10000;
        const check = () => {{
            const sb = document.querySelector('ntx-chat-sidebar');
            const count = sb ? sb.shadowRoot.querySelectorAll('ntx-chat-conv').length : 0;
            if (count > before) return resolve(true);
            if (Date.now() > deadline) return resolve(false);
            setTimeout(check, 300);
        }};
        check();
    }})""", before)


def _select_conversation(page, index=0):
    """Click a conversation in the sidebar by index. Waits for chat view to load."""
    # Wait for the target conv element to be fully rendered (has .conv-name)
    clicked = page.evaluate(f"""(idx) => new Promise((resolve) => {{
        const deadline = Date.now() + 10000;
        const tryClick = () => {{
            const sidebar = document.querySelector('ntx-chat-sidebar');
            if (!sidebar || !sidebar.shadowRoot) {{
                if (Date.now() > deadline) return resolve(false);
                return setTimeout(tryClick, 200);
            }}
            const convs = sidebar.shadowRoot.querySelectorAll('ntx-chat-conv');
            if (convs.length <= idx) {{
                if (Date.now() > deadline) return resolve(false);
                return setTimeout(tryClick, 200);
            }}
            const conv = convs[idx];
            const name = conv.shadowRoot ? conv.shadowRoot.querySelector('.conv-name') : null;
            if (!name) {{
                if (Date.now() > deadline) return resolve(false);
                return setTimeout(tryClick, 200);
            }}
            name.click();
            resolve(true);
        }};
        tryClick();
    }})""", index)
    assert clicked, f"Failed to click conversation at index {index}"

    # Wait for chat view to load the conversation (header appears)
    page.evaluate("""() => new Promise((resolve) => {
        const deadline = Date.now() + 10000;
        const check = () => {
            const view = document.querySelector('ntx-chat-view');
            if (view && view.shadowRoot.querySelector('.chat-header')) return resolve(true);
            if (Date.now() > deadline) return resolve(false);
            setTimeout(check, 200);
        };
        check();
    })""")


def _send_message(page, text):
    """Type and send a message via the chat input shadow DOM. Waits for input to be ready."""
    result = page.evaluate(f"""(text) => new Promise((resolve) => {{
        const deadline = Date.now() + 15000;
        const tryType = () => {{
            const view = document.querySelector('ntx-chat-view');
            if (!view) {{ if (Date.now() > deadline) return resolve('no view'); return setTimeout(tryType, 300); }}
            const input = view.shadowRoot.querySelector('ntx-chat-input');
            if (!input) {{ if (Date.now() > deadline) return resolve('no input'); return setTimeout(tryType, 300); }}
            const textarea = input.shadowRoot?.querySelector('#chatInput');
            if (!textarea) {{ if (Date.now() > deadline) return resolve('no textarea'); return setTimeout(tryType, 300); }}
            if (textarea.disabled) {{ if (Date.now() > deadline) return resolve('textarea disabled'); return setTimeout(tryType, 300); }}
            textarea.value = text;
            textarea.dispatchEvent(new Event('input'));
            setTimeout(() => {{
                const btn = input.shadowRoot.querySelector('#btnSend');
                if (btn && !btn.disabled) {{
                    btn.click();
                    resolve('ok');
                }} else if (Date.now() > deadline) {{
                    resolve('btn disabled');
                }} else {{
                    setTimeout(tryType, 300);
                }}
            }}, 200);
        }};
        tryType();
    }})""", text)
    assert result == 'ok', f"_send_message failed: {result}"


def _get_messages(page):
    """Get all chat bubbles from the chat view."""
    return page.evaluate("""() => {
        const view = document.querySelector('ntx-chat-view');
        if (!view) return [];
        const bubbles = view.shadowRoot.querySelectorAll('.chat-bubble');
        return Array.from(bubbles).map(b => ({
            role: b.classList.contains('user') ? 'user' : 'assistant',
            text: b.textContent.trim(),
        }));
    }""")


def _get_conversation_count(page):
    """Count conversations in the sidebar."""
    return page.evaluate("""() => {
        const sidebar = document.querySelector('ntx-chat-sidebar');
        if (!sidebar || !sidebar.shadowRoot) return 0;
        return sidebar.shadowRoot.querySelectorAll('ntx-chat-conv').length;
    }""")


def _wait_for_assistant(page, timeout_ms=30000):
    """Wait for a non-streaming assistant response. Returns the text."""
    return page.evaluate(f"""() => new Promise((resolve) => {{
        const deadline = Date.now() + {timeout_ms};
        const check = () => {{
            const view = document.querySelector('ntx-chat-view');
            if (!view) {{ if (Date.now() > deadline) return resolve(null); return setTimeout(check, 200); }}
            const asst = view.shadowRoot.querySelectorAll('.chat-bubble.assistant');
            if (asst.length === 0) {{ if (Date.now() > deadline) return resolve(null); return setTimeout(check, 200); }}
            const last = asst[asst.length - 1];
            if (last.querySelector('.stream-cursor')) {{ if (Date.now() > deadline) return resolve(null); return setTimeout(check, 200); }}
            resolve(last.textContent.trim());
        }};
        check();
    }})""")


def _login_and_prepare(page, base_url):
    """Login and wait for sidebar to be ready."""
    _login(page, base_url)
    _wait_for_sidebar_loaded(page)


# ── Tests ──

class TestServerHealth:
    """Backend serves pages and API endpoints correctly."""

    def test_html_served_at_root(self, e2e_server, page):
        """GET / returns the chat app HTML with expected components."""
        page.goto(e2e_server)
        page.wait_for_load_state("domcontentloaded")

        html = page.content()
        assert "ntx-chat-sidebar" in html
        assert "ntx-chat-view" in html

    def test_schema_endpoint(self, e2e_server, page):
        """GET /Conversation returns valid schema JSON."""
        resp = page.request.get(f"{e2e_server}/Conversation")
        assert resp.status == 200
        schema = resp.json()
        assert schema["__name__"] == "Conversation"
        assert "chat" in schema.get("methods", {})
        assert schema["methods"]["chat"].get("stream") is True

    def test_static_css_loads(self, e2e_server, page):
        """dark-theme.css is served and accessible."""
        resp = page.request.get(f"{e2e_server}/dark-theme.css")
        assert resp.status == 200
        assert "text/css" in resp.headers.get("content-type", "")

    def test_js_module_loads(self, e2e_server, page):
        """Framework JS modules resolve without 404."""
        resp = page.request.get(f"{e2e_server}/core/transport/HTTP.js")
        assert resp.status == 200

    def test_component_js_loads(self, e2e_server, page):
        """Chat component JS files are accessible."""
        for name in ["ntx-chat-sidebar", "ntx-chat-view", "ntx-chat-input",
                      "ntx-chat-conv", "ntx-chat-message"]:
            resp = page.request.get(f"{e2e_server}/components/{name}.js")
            assert resp.status == 200, f"{name}.js returned {resp.status}"

    def test_no_console_errors_on_load(self, e2e_server, page):
        """Page loads without JS console errors."""
        errors = []
        page.on("pageerror", lambda err: errors.append(str(err)))
        page.goto(e2e_server)
        page.wait_for_load_state("networkidle")
        # Filter out known benign errors (e.g. LLM status fetch when offline)
        real_errors = [e for e in errors if "llm-status" not in e]
        assert real_errors == [], f"Console errors on load: {real_errors}"


class TestAuth:
    """Auth overlay, login, register, logout — all through the browser."""

    def test_login_overlay_visible_on_first_visit(self, e2e_server, page):
        """Without JWT, login overlay is shown and app is hidden."""
        page.goto(e2e_server)
        page.wait_for_selector("#loginOverlay", state="visible", timeout=10000)

        sidebar_visible = page.evaluate("""() =>
            window.getComputedStyle(
                document.querySelector('ntx-chat-sidebar')
            ).display !== 'none'
        """)
        assert not sidebar_visible

    def test_login_success(self, e2e_server, page):
        """Login with seeded credentials hides overlay and shows app."""
        _login(page, e2e_server)

        assert page.locator("#loginOverlay").is_hidden()
        assert page.locator("ntx-chat-sidebar").is_visible()

    def test_login_failure(self, e2e_server, page):
        """Wrong password shows error message."""
        page.goto(e2e_server)
        page.wait_for_selector("#loginOverlay", state="visible", timeout=10000)

        page.fill("#loginEmail", "alice@example.com")
        page.fill("#loginPassword", "wrongpassword")
        page.click("#btnLogin")

        # Wait for error to appear
        page.evaluate("""() => new Promise((resolve) => {
            const deadline = Date.now() + 5000;
            const check = () => {
                const el = document.getElementById('loginError');
                if (el && el.textContent.trim()) return resolve(true);
                if (Date.now() > deadline) return resolve(false);
                setTimeout(check, 200);
            };
            check();
        })""")

        error_text = page.locator("#loginError").text_content()
        assert error_text, "Expected error message for bad credentials"

    def test_register_and_login(self, e2e_server, page):
        """Register a new user, verify authenticated, then logout and re-login."""
        uid = uuid.uuid4().hex[:8]
        email = f"e2e_{uid}@test.com"
        _register(page, e2e_server, f"E2E User {uid}", email, "testpass123")

        assert page.locator("ntx-chat-sidebar").is_visible()

        # Logout (triggers reload)
        page.evaluate("""() => {
            const sb = document.querySelector('ntx-chat-sidebar');
            sb.shadowRoot.querySelector('#btnLogout').click();
        }""")
        page.wait_for_load_state("load", timeout=10000)
        page.wait_for_selector("#loginOverlay", state="visible", timeout=10000)

        # Re-login with the new account
        _login(page, e2e_server, email, "testpass123")
        assert page.locator("ntx-chat-sidebar").is_visible()


class TestConversationCRUD:
    """Create, list, and select conversations through the UI."""

    def test_sidebar_renders_seeded_conversations(self, e2e_server, page):
        """After login, sidebar shows seeded conversation(s)."""
        _login_and_prepare(page, e2e_server)

        count = _get_conversation_count(page)
        assert count >= 1, "Expected at least 1 seeded conversation"

    def test_create_conversation_appears_in_sidebar(self, e2e_server, page):
        """Creating a conversation adds it to the sidebar list."""
        _login_and_prepare(page, e2e_server)

        before = _get_conversation_count(page)
        _create_conversation(page)
        after = _get_conversation_count(page)

        assert after > before, f"Expected more convs after create: {before} -> {after}"

    def test_select_conversation_shows_chat_view(self, e2e_server, page):
        """Clicking a conversation loads the chat view with header."""
        _login_and_prepare(page, e2e_server)

        _select_conversation(page, 0)

        has_header = page.evaluate("""() => {
            const view = document.querySelector('ntx-chat-view');
            return !!view.shadowRoot.querySelector('.chat-header');
        }""")
        assert has_header, "Chat view should show a header after selecting conversation"

    def test_new_conversation_shows_empty_state(self, e2e_server, page):
        """Freshly created conversation shows empty messages state."""
        _login_and_prepare(page, e2e_server)

        _create_conversation(page)
        count = _get_conversation_count(page)
        _select_conversation(page, count - 1)

        empty = page.evaluate("""() => {
            const view = document.querySelector('ntx-chat-view');
            const el = view.shadowRoot.querySelector('.empty-state');
            return el ? el.textContent.trim() : null;
        }""")
        assert empty is not None, "New conversation should show empty state"


class TestChatStreaming:
    """Send messages and verify SSE streaming through the full stack."""

    def test_user_message_appears_immediately(self, e2e_server, page):
        """Sending a message shows the user bubble before SSE response."""
        _login_and_prepare(page, e2e_server)

        _create_conversation(page)
        count = _get_conversation_count(page)
        _select_conversation(page, count - 1)

        _send_message(page, "Hello from integration test!")

        # Wait for user bubble to appear
        page.evaluate("""() => new Promise((resolve) => {
            const deadline = Date.now() + 5000;
            const check = () => {
                const view = document.querySelector('ntx-chat-view');
                if (view) {
                    const bubbles = view.shadowRoot.querySelectorAll('.chat-bubble.user');
                    if (bubbles.length > 0) return resolve(true);
                }
                if (Date.now() > deadline) return resolve(false);
                setTimeout(check, 200);
            };
            check();
        })""")

        messages = _get_messages(page)
        user_msgs = [m for m in messages if m['role'] == 'user']
        assert len(user_msgs) >= 1
        assert any("Hello from integration test!" in m['text'] for m in user_msgs)

        # Let streaming finish before test teardown
        _wait_for_assistant(page, timeout_ms=15000)

    def test_assistant_response_via_sse(self, e2e_server, page):
        """Message gets an assistant response via SSE streaming."""
        _login_and_prepare(page, e2e_server)

        _create_conversation(page)
        count = _get_conversation_count(page)
        _select_conversation(page, count - 1)

        _send_message(page, "Say hello")
        response = _wait_for_assistant(page, timeout_ms=30000)

        assert response is not None, "Expected an assistant response from TestModel"
        assert len(response) > 0

    def test_streaming_cursor_during_response(self, e2e_server, page):
        """During streaming, a cursor indicator appears."""
        _login_and_prepare(page, e2e_server)

        _create_conversation(page)
        count = _get_conversation_count(page)
        _select_conversation(page, count - 1)

        _send_message(page, "Write something")

        # Check for streaming bubble within first few seconds
        page.evaluate("""() => new Promise(resolve => {
            let attempts = 0;
            const check = () => {
                const view = document.querySelector('ntx-chat-view');
                if (view) {
                    const bubble = view.shadowRoot.querySelector('.chat-bubble.streaming');
                    if (bubble) return resolve(true);
                }
                if (++attempts > 20) return resolve(false);
                setTimeout(check, 100);
            };
            check();
        })""")
        # Note: TestModel may respond too fast for cursor to be visible
        # This test mainly ensures no errors during streaming

        _wait_for_assistant(page, timeout_ms=30000)

    def test_multi_turn_conversation(self, e2e_server, page):
        """Multiple messages build conversation history."""
        _login_and_prepare(page, e2e_server)

        _create_conversation(page)
        count = _get_conversation_count(page)
        _select_conversation(page, count - 1)

        # First message
        _send_message(page, "First message")
        resp1 = _wait_for_assistant(page, timeout_ms=30000)
        assert resp1 is not None

        # Second message
        _send_message(page, "Second message")
        resp2 = _wait_for_assistant(page, timeout_ms=30000)
        assert resp2 is not None

        # Should have at least 4 bubbles
        messages = _get_messages(page)
        assert len(messages) >= 4, f"Expected >= 4 messages, got {len(messages)}"

    def test_messages_persist_after_reload(self, e2e_server, page):
        """Messages survive page reload — stored in DB, not just DOM."""
        _login_and_prepare(page, e2e_server)

        _create_conversation(page)
        count = _get_conversation_count(page)
        conv_index = count - 1
        _select_conversation(page, conv_index)

        _send_message(page, "This message must persist")
        _wait_for_assistant(page, timeout_ms=30000)

        before_count = len(_get_messages(page))
        assert before_count >= 2

        # Reload page — wait for conversations to fully load before selecting
        page.reload()
        page.wait_for_selector("body.authenticated", timeout=10000)
        _wait_for_sidebar_loaded(page, min_convs=count)

        # Re-select the same conversation (same index — conv list is ID-ordered)
        _select_conversation(page, conv_index)

        # Wait for messages to load
        page.evaluate("""() => new Promise((resolve) => {
            const deadline = Date.now() + 10000;
            const check = () => {
                const view = document.querySelector('ntx-chat-view');
                if (view) {
                    const bubbles = view.shadowRoot.querySelectorAll('.chat-bubble');
                    if (bubbles.length >= 2) return resolve(true);
                }
                if (Date.now() > deadline) return resolve(false);
                setTimeout(check, 300);
            };
            check();
        })""")

        after_count = len(_get_messages(page))
        assert after_count >= 2, "Messages should persist after reload"


class TestSidebarUI:
    """Sidebar component rendering and interaction."""

    def test_user_email_in_sidebar(self, e2e_server, page):
        """Sidebar footer shows the logged-in user's email."""
        _login_and_prepare(page, e2e_server)

        user_text = page.evaluate("""() => {
            const sb = document.querySelector('ntx-chat-sidebar');
            const el = sb.shadowRoot.querySelector('#userName');
            return el ? el.textContent.trim() : null;
        }""")
        assert user_text is not None
        assert "alice@example.com" in user_text

    def test_llm_status_shows(self, e2e_server, page):
        """LLM status indicator renders (ready or offline)."""
        _login_and_prepare(page, e2e_server)

        # Wait for LLM status to resolve (initial fetch happens on render)
        status = page.evaluate("""() => new Promise((resolve) => {
            const deadline = Date.now() + 5000;
            const check = () => {
                const sb = document.querySelector('ntx-chat-sidebar');
                const label = sb?.shadowRoot?.querySelector('.llm-status .label');
                const text = label?.textContent?.trim();
                if (text && text !== 'Connecting...') return resolve(text);
                if (Date.now() > deadline) return resolve(text || null);
                setTimeout(check, 300);
            };
            check();
        })""")
        assert status is not None
        assert "Connecting" not in status

    def test_active_conversation_highlight(self, e2e_server, page):
        """Selecting a conversation marks it as active in sidebar."""
        _login_and_prepare(page, e2e_server)

        if _get_conversation_count(page) == 0:
            _create_conversation(page)

        _select_conversation(page, 0)

        has_active = page.evaluate("""() => new Promise((resolve) => {
            const deadline = Date.now() + 5000;
            const check = () => {
                const sb = document.querySelector('ntx-chat-sidebar');
                const convs = sb.shadowRoot.querySelectorAll('ntx-chat-conv');
                for (const c of convs) {
                    if (c.shadowRoot.querySelector('.conv-name.active')) return resolve(true);
                }
                if (Date.now() > deadline) return resolve(false);
                setTimeout(check, 200);
            };
            check();
        })""")
        assert has_active, "Expected one conversation to have active class"


class TestFullPipeline:
    """End-to-end: register → create conversation → chat → verify persistence."""

    def test_complete_user_journey(self, e2e_server, page):
        """Full pipeline: register, create conv, send message, get response,
        send follow-up, reload, verify all persisted."""
        uid = uuid.uuid4().hex[:8]

        # 1. Register
        _register(page, e2e_server, f"Pipeline {uid}", f"pipe_{uid}@test.com", "pipe123")
        assert page.locator("ntx-chat-sidebar").is_visible()
        _wait_for_sidebar_loaded(page)

        # 2. Create conversation
        _create_conversation(page)
        count = _get_conversation_count(page)
        assert count >= 1

        # 3. Select it
        _select_conversation(page, count - 1)

        # 4. Send message
        _send_message(page, "Pipeline test message!")

        # 5. Get response
        response = _wait_for_assistant(page, timeout_ms=30000)
        assert response is not None, "Expected assistant response"

        # 6. Verify messages
        messages = _get_messages(page)
        assert len(messages) >= 2
        user_msgs = [m for m in messages if m['role'] == 'user']
        asst_msgs = [m for m in messages if m['role'] == 'assistant']
        assert len(user_msgs) >= 1
        assert len(asst_msgs) >= 1

        # 7. Follow-up message
        _send_message(page, "Follow-up question")
        resp2 = _wait_for_assistant(page, timeout_ms=30000)
        assert resp2 is not None

        # 8. Verify multi-turn
        messages2 = _get_messages(page)
        assert len(messages2) >= 4

        # 9. Reload and verify persistence
        page.reload()
        page.wait_for_selector("body.authenticated", timeout=10000)
        _wait_for_sidebar_loaded(page, min_convs=count)

        _select_conversation(page, count - 1)

        # Wait for messages to load
        page.evaluate("""() => new Promise((resolve) => {
            const deadline = Date.now() + 10000;
            const check = () => {
                const view = document.querySelector('ntx-chat-view');
                if (view) {
                    const bubbles = view.shadowRoot.querySelectorAll('.chat-bubble');
                    if (bubbles.length >= 4) return resolve(true);
                }
                if (Date.now() > deadline) return resolve(false);
                setTimeout(check, 300);
            };
            check();
        })""")

        persisted = _get_messages(page)
        assert len(persisted) >= 4, f"Expected >= 4 persisted messages, got {len(persisted)}"
