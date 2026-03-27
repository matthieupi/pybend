"""E2E test — agent chat widget full pipeline for Grant Watcher.

Uses Playwright to test the ntx-chat widget and direct HTTP calls.
The server runs with N3TX_AGENT_DEFAULTS llm=test for pydantic-ai TestModel.
Tests the complete flow: UI interaction -> HTTP -> actor routing -> agent -> response -> UI.
"""
import json
import pytest
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5000"  # Patched by conftest


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
    result = p.evaluate("""async (base) => {
        const resp = await fetch(`${base}/users/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: 'alice@example.com', password: 'alice123' }),
        });
        if (!resp.ok) return { error: resp.status };
        const data = await resp.json();
        const token = data.data ? data.data.token : data.token;
        localStorage.setItem('jwtToken', token);
        return { ok: true, token: token };
    }""", base)
    assert result.get('ok'), f"Login failed: {result}"
    yield p
    p.close()
    ctx.close()


@pytest.fixture(scope="module")
def test_agent_id(browser, e2e_server):
    """Create a simple test agent (no tools, llm=test) via API."""
    base = e2e_server
    ctx = browser.new_context()
    p = ctx.new_page()
    p.goto(f"{base}/")
    p.wait_for_load_state("networkidle")

    result = p.evaluate("""async (base) => {
        // Login first
        const loginResp = await fetch(`${base}/users/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: 'alice@example.com', password: 'alice123' }),
        });
        const { token } = await loginResp.json();

        // Create a simple test agent
        const agentResp = await fetch(`${base}/agents`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'x-access-token': token,
            },
            body: JSON.stringify({
                name: 'E2E Test Agent',
                prompt: 'You are a helpful test agent. Answer briefly.',
                llm: 'test',
            }),
        });
        if (!agentResp.ok) return { error: agentResp.status, body: await agentResp.text() };
        const agent = await agentResp.json();
        return { id: agent.id, token };
    }""", base)

    p.close()
    ctx.close()

    assert 'error' not in result, f"Failed to create test agent: {result}"
    return result['id']


class TestChatWidgetLoads:
    """Verify the ntx-chat widget loads in the Grant Watcher app."""

    def test_chat_widget_exists_in_dom(self, page, e2e_server):
        page.goto(f"{e2e_server}/")
        page.wait_for_load_state("networkidle")
        chat = page.query_selector("ntx-chat")
        assert chat is not None, "ntx-chat element not found in DOM"

    def test_chat_widget_has_shadow_dom_elements(self, page, e2e_server):
        page.goto(f"{e2e_server}/")
        page.wait_for_load_state("networkidle")
        has_elements = page.evaluate("""() => {
            const chat = document.querySelector('ntx-chat');
            if (!chat?.shadowRoot) return false;
            return !!(
                chat.shadowRoot.querySelector('textarea') &&
                chat.shadowRoot.querySelector('.instance-select') &&
                chat.shadowRoot.querySelector('.send-btn')
            );
        }""")
        assert has_elements, "Chat widget missing shadow DOM elements"

    def test_chat_widget_loads_agents(self, page, e2e_server):
        """Widget should populate the select with agent instances."""
        page.goto(f"{e2e_server}/")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)
        options = page.evaluate("""() => {
            const chat = document.querySelector('ntx-chat');
            if (!chat?.shadowRoot) return [];
            const sel = chat.shadowRoot.querySelector('.instance-select');
            return Array.from(sel.options).map(o => ({ value: o.value, text: o.text }));
        }""")
        assert len(options) > 0, "No agents in select dropdown"


class TestAgentRunHTTPPipeline:
    """Test the non-streaming agent /run endpoint via direct HTTP call from the browser."""

    def test_agent_run_full_pipeline(self, authed_page, e2e_server, test_agent_id):
        """Call /agents/{id}/run from the browser and verify the response."""
        base = e2e_server
        page = authed_page
        page.goto(f"{base}/")
        page.wait_for_load_state("networkidle")

        result = page.evaluate("""async (args) => {
            const [base, agentId] = args;
            const token = localStorage.getItem('jwtToken');

            const resp = await fetch(`${base}/agents/${agentId}/run`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'x-access-token': token,
                },
                body: JSON.stringify({ task: 'What can you do?' }),
            });

            if (!resp.ok) return { error: `HTTP ${resp.status}`, body: await resp.text() };
            const data = await resp.json();
            return data;
        }""", [base, test_agent_id])

        assert 'error' not in result, f"Agent run failed: {result}"
        # Response may be a debug envelope or direct result
        data = result
        if 'result' in data and '_debug' in data:
            data = data['result']
        assert 'answer' in data, f"No 'answer' in response: {list(data.keys())}"
        assert 'usage' in data, f"No 'usage' in response: {list(data.keys())}"
        assert data['usage']['requests'] >= 1

    def test_agent_run_requires_auth(self, page, e2e_server, test_agent_id):
        """Agent run without auth should return 401/403."""
        base = e2e_server
        page.goto(f"{base}/")
        page.wait_for_load_state("networkidle")

        result = page.evaluate("""async (args) => {
            const [base, agentId] = args;
            const resp = await fetch(`${base}/agents/${agentId}/run`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ task: 'hello' }),
            });
            return { status: resp.status };
        }""", [base, test_agent_id])

        assert result['status'] in (401, 403), f"Expected auth error, got {result['status']}"


class TestChatWidgetInteraction:
    """Test sending a message through the chat widget (non-streaming flow)."""

    def test_send_message_via_widget(self, authed_page, e2e_server, test_agent_id):
        """Type a task in the chat widget and verify the agent responds."""
        base = e2e_server
        page = authed_page
        page.goto(f"{base}/")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1500)  # Let schema + instances load

        result = page.evaluate("""async (args) => {
            const [base, agentId] = args;
            const chat = document.querySelector('ntx-chat');
            if (!chat?.shadowRoot) return { error: 'no shadow root' };

            const select = chat.shadowRoot.querySelector('.instance-select');
            const textarea = chat.shadowRoot.querySelector('textarea');
            const sendBtn = chat.shadowRoot.querySelector('.send-btn');

            // Select our test agent
            select.value = String(agentId);
            select.dispatchEvent(new Event('change'));

            // Type a message
            textarea.value = 'Hello agent, what can you help with?';
            textarea.dispatchEvent(new Event('input'));

            // Send
            sendBtn.click();

            // Wait for response (up to 15s)
            let attempts = 0;
            let messages;
            while (attempts < 150) {
                await new Promise(r => setTimeout(r, 100));
                messages = chat.shadowRoot.querySelectorAll('.msg');
                if (messages.length >= 2) {
                    const lastMsg = messages[messages.length - 1];
                    const role = lastMsg.querySelector('.msg-role')?.textContent;
                    if (role === 'assistant' || role === 'system') {
                        const text = lastMsg.querySelector('.msg-text')?.textContent;
                        if (text && text.length > 0) {
                            return {
                                messageCount: messages.length,
                                lastRole: role,
                                lastText: text,
                            };
                        }
                    }
                }
                attempts++;
            }
            // Collect debug info
            const msgInfo = messages ? Array.from(messages).map(m => ({
                role: m.querySelector('.msg-role')?.textContent,
                text: m.querySelector('.msg-text')?.textContent?.slice(0, 100),
            })) : [];
            return {
                error: 'timeout',
                messageCount: messages?.length || 0,
                messages: msgInfo,
            };
        }""", [base, test_agent_id])

        assert 'error' not in result, f"Widget interaction failed: {json.dumps(result, indent=2)}"
        assert result['messageCount'] >= 2
