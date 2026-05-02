"""E2E test — agent chat widget full pipeline.

Uses Playwright to interact with the ntx-chat widget in the browser.
The server uses 'test' LLM (pydantic-ai TestModel) so no real LLM is needed.
Tests the complete flow: UI interaction -> HTTP -> actor routing -> agent pipeline -> response -> UI.
"""
import json
import pytest
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5000"  # Patched by conftest


def wait_for_chat_ready(page, timeout=10000):
    page.wait_for_function("""() => {
        const chat = document.querySelector('ntx-chat');
        const root = chat?.shadowRoot;
        const select = root?.querySelector('.instance-select');
        return !!root?.querySelector('textarea')
            && !!root?.querySelector('.send-btn')
            && !!select
            && select.options.length > 0
            && select.value !== '';
    }""", timeout=timeout)


def wait_for_chat_response(page, timeout=15000):
    page.wait_for_function("""() => {
        const chat = document.querySelector('ntx-chat');
        const messages = chat?.shadowRoot?.querySelectorAll('.msg') || [];
        if (messages.length < 2) return false;
        const lastMsg = messages[messages.length - 1];
        const role = lastMsg.querySelector('.msg-role')?.textContent;
        const text = lastMsg.querySelector('.entry-text-output-content')?.textContent
            || lastMsg.querySelector('.msg-text')?.textContent;
        return role === 'assistant' && !!text && text.length > 0;
    }""", timeout=timeout)


def _unwrap_stream_event(event):
    """Unwrap actor-style STREAM envelopes down to the inner event payload."""
    data = event
    while isinstance(data, dict) and data.get('name') == 'STREAM' and isinstance(data.get('data'), dict):
        data = data['data']
    return data


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.fixture
def page(browser):
    ctx = browser.new_context()
    p = ctx.new_page()
    yield p
    p.close()
    ctx.close()


@pytest.fixture
def authed_page(browser, e2e_server):
    """Page with a logged-in user session."""
    base = e2e_server
    ctx = browser.new_context()
    p = ctx.new_page()
    p.goto(f"{base}/")
    p.wait_for_load_state("networkidle")
    # Log in via API and set JWT
    result = p.evaluate("""async (base) => {
        const resp = await fetch(`${base}/users/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: 'alice@example.com', password: 'alice123' }),
        });
        if (!resp.ok) return { error: resp.status };
        const data = await resp.json();
        const payload = data.data || data.result || data;
        const token = payload.token || (payload.data && payload.data.token);
        localStorage.setItem('jwtToken', token);
        return { ok: true, token: token };
    }""", base)
    assert result.get('ok'), f"Login failed: {result}"
    yield p
    p.close()
    ctx.close()


class TestChatWidgetLoads:
    """Verify the ntx-chat widget loads and renders correctly."""

    def test_chat_widget_exists_in_dom(self, page, e2e_server):
        """ntx-chat element should be present in the page."""
        page.goto(f"{e2e_server}/")
        page.wait_for_load_state("networkidle")
        chat = page.query_selector("ntx-chat")
        assert chat is not None, "ntx-chat element not found in DOM"

    def test_chat_widget_has_shadow_dom(self, page, e2e_server):
        """Widget should have shadow DOM with input and controls."""
        page.goto(f"{e2e_server}/")
        page.wait_for_load_state("networkidle")
        has_shadow = page.evaluate("""() => {
            const chat = document.querySelector('ntx-chat');
            if (!chat || !chat.shadowRoot) return false;
            const textarea = chat.shadowRoot.querySelector('textarea');
            const select = chat.shadowRoot.querySelector('.instance-select');
            const sendBtn = chat.shadowRoot.querySelector('.send-btn');
            return !!(textarea && select && sendBtn);
        }""")
        assert has_shadow, "Chat widget missing shadow DOM elements"

    def test_chat_widget_loads_instances(self, page, e2e_server):
        """Widget should populate the instance select with products."""
        page.goto(f"{e2e_server}/")
        page.wait_for_load_state("networkidle")
        wait_for_chat_ready(page)
        options = page.evaluate("""() => {
            const chat = document.querySelector('ntx-chat');
            if (!chat?.shadowRoot) return [];
            const select = chat.shadowRoot.querySelector('.instance-select');
            return Array.from(select.options).map(o => ({ value: o.value, text: o.text }));
        }""")
        assert len(options) > 0, "No options loaded in instance select"
        # First option should be a real product (not "Loading...")
        assert options[0]['value'] != '', f"Select still showing placeholder: {options}"


class TestChatWidgetStreaming:
    """Test the full streaming agent pipeline via the chat widget."""

    def test_send_message_receives_streaming_response(self, authed_page, e2e_server):
        """Type a message, send it, and verify the response appears."""
        base = e2e_server
        page = authed_page
        page.goto(f"{base}/")
        page.wait_for_load_state("networkidle")
        wait_for_chat_ready(page)

        # Use page.evaluate to interact with shadow DOM and verify full pipeline
        result = page.evaluate("""async (base) => {
            const chat = document.querySelector('ntx-chat');
            if (!chat?.shadowRoot) return { error: 'no shadow root' };

            const select = chat.shadowRoot.querySelector('.instance-select');
            const textarea = chat.shadowRoot.querySelector('textarea');
            const sendBtn = chat.shadowRoot.querySelector('.send-btn');

            if (!select.value) return { error: 'no instance selected' };
            if (!sendBtn) return { error: 'no send button' };

            // Type a message
            textarea.value = 'Hello, tell me about this product';
            textarea.dispatchEvent(new Event('input'));

            // Click send
            sendBtn.click();

            return { ok: true };
        }""", base)

        assert 'error' not in result, f"E2E setup failed: {result}"
        wait_for_chat_response(page)
        result = page.evaluate("""() => {
            const chat = document.querySelector('ntx-chat');
            const messages = chat.shadowRoot.querySelectorAll('.msg');
            const lastMsg = messages[messages.length - 1];
            return {
                messageCount: messages.length,
                assistantText: lastMsg.querySelector('.entry-text-output-content')?.textContent
                    || lastMsg.querySelector('.msg-text')?.textContent,
                userText: messages[0].querySelector('.msg-text')?.textContent,
            };
        }""")

        assert 'error' not in result, f"E2E failed: {result}"
        assert result['messageCount'] >= 2, f"Expected >= 2 messages, got {result['messageCount']}"
        assert result['userText'] == 'Hello, tell me about this product'
        assert len(result['assistantText']) > 0, "Assistant response is empty"


class TestAgentHTTPPipeline:
    """Test the HTTP pipeline directly (no widget) for finer-grained assertions."""

    def test_ask_endpoint_streams_sse(self, page, e2e_server):
        """POST /Product/{id}/ask should return SSE with text chunks and done."""
        base = e2e_server

        # First login
        page.goto(f"{base}/")
        page.wait_for_load_state("networkidle")
        login_result = page.evaluate("""async (base) => {
            const resp = await fetch(`${base}/users/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: 'alice@example.com', password: 'alice123' }),
            });
            const data = await resp.json();
            const payload = data.data || data.result || data;
            const token = payload.token || (payload.data && payload.data.token);
            localStorage.setItem('jwtToken', token);
            return token;
        }""", base)

        # Call the agent endpoint and parse SSE
        result = page.evaluate("""async (args) => {
            const [base, token] = args;
            const resp = await fetch(`${base}/Product/1/ask`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'x-access-token': token,
                },
                body: JSON.stringify({ task: 'Describe this product briefly' }),
            });

            if (!resp.ok) return { error: `HTTP ${resp.status}` };

            const reader = resp.body.getReader();
            const decoder = new TextDecoder();
            const events = [];
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\\n');
                buffer = lines.pop();
                let eventType = 'chunk';
                for (const line of lines) {
                    if (line.startsWith('event: ')) eventType = line.slice(7).trim();
                    else if (line.startsWith('data: ')) {
                        try {
                            events.push({ type: eventType, data: JSON.parse(line.slice(6)) });
                        } catch(e) {}
                    }
                }
            }
            return { events, count: events.length };
        }""", [base, login_result])

        assert 'error' not in result, f"Request failed: {result}"
        assert result['count'] >= 2, f"Expected >= 2 SSE events, got {result['count']}"

        # Verify we got text and done chunks
        events = result['events']
        chunk_events = [e for e in events if e['type'] == 'chunk']
        done_sentinel = [e for e in events if e['type'] == 'done']

        inner_events = [_unwrap_stream_event(e['data']) for e in chunk_events]

        # text chunk should have data.name='text'
        text_chunks = [e for e in inner_events if e.get('name') == 'text']
        assert len(text_chunks) >= 1, f"No text chunks. Events: {events}"

        # done chunk should have data.name='done' with answer
        done_chunks = [e for e in inner_events if e.get('name') == 'done']
        assert len(done_chunks) >= 1, f"No done chunk. Events: {events}"
        assert 'answer' in done_chunks[0].get('data', {}), f"Done chunk missing answer: {done_chunks[0]}"

        # SSE stream should end with event:done sentinel
        assert len(done_sentinel) == 1, f"Expected 1 done sentinel, got {len(done_sentinel)}"
