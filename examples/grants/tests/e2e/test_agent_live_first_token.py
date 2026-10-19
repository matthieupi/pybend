"""E2E tests for the first-token-missing bug in ntx-agent-live component.

Bug: When the agent-live streaming response is rendered in the UI, the first
token (word) of the response is always missing from the displayed text.

Uses Playwright to test the real browser rendering of streaming responses.
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


@pytest.fixture(scope="module")
def streaming_agent_id(browser, e2e_server):
    """Create a test agent and return its id for streaming tests."""
    base = e2e_server
    ctx = browser.new_context()
    p = ctx.new_page()
    p.goto(f"{base}/")
    p.wait_for_load_state("networkidle")

    result = p.evaluate("""async (base) => {
        const loginResp = await fetch(`${base}/users/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: 'alice@example.com', password: 'alice123' }),
        });
        const loginData = await loginResp.json();
        const token = loginData.token || loginData.data?.token;

        const agentResp = await fetch(`${base}/agents`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'x-access-token': token,
            },
            body: JSON.stringify({
                name: 'Streaming E2E Agent',
                prompt: 'You are a test agent.',
                llm: 'test',
            }),
        });
        if (!agentResp.ok) return { error: agentResp.status };
        const agent = await agentResp.json();
        return { id: agent.id, token };
    }""", base)

    p.close()
    ctx.close()
    assert 'error' not in result, f"Failed to create agent: {result}"
    return result['id']


class TestStreamFirstTokenNotDropped:
    """NTTStream/NTTStreamAgent must not drop the first TEXT event."""

    def test_agent_live_renders_complete_streamed_answer(self, browser, e2e_server, streaming_agent_id):
        """ntx-agent-live must display the full answer including the first word.

        Makes a real streaming call and checks that the rendered text in the
        ntx-agent-live component starts with the first word of the answer.
        """
        base = e2e_server
        ctx = browser.new_context()
        p = ctx.new_page()
        p.goto(f"{base}/")
        p.wait_for_load_state("networkidle")

        result = p.evaluate("""async (args) => {
            function unwrapStreamEvent(payload) {
                let event = payload;
                while (event && event.name === 'STREAM' && event.data && typeof event.data === 'object') {
                    event = event.data;
                }
                return event || {};
            }

            const [base, agentId] = args;

            // Login
            const loginResp = await fetch(`${base}/users/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: 'alice@example.com', password: 'alice123' }),
            });
            const loginData = await loginResp.json();
            const token = loginData.token || loginData.data?.token;
            localStorage.setItem('jwtToken', token);

            // First, collect the expected full answer from the SSE stream
            const resp = await fetch(`${base}/agents/${agentId}/agentic_stream`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'x-access-token': token,
                },
                body: JSON.stringify({ task: 'Say hello briefly' }),
            });
            if (!resp.ok) return { error: `HTTP ${resp.status}` };

            const reader = resp.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            const textChunks = [];
            let doneAnswer = null;

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\\n');
                buffer = lines.pop();
                for (const line of lines) {
                    if (!line.trim() || line.startsWith(':')) continue;
                    if (line.startsWith('data:')) {
                        try {
                            const payload = JSON.parse(line.slice(5).trim());
                            const event = unwrapStreamEvent(payload);
                            const name = event.name || event.event;
                            const data = event.data || {};
                            if (name === 'text') textChunks.push(data.text || '');
                            if (name === 'done') doneAnswer = data.answer || '';
                        } catch {}
                    }
                }
            }

            const fullAnswer = textChunks.join('');
            const firstWord = fullAnswer.trim().split(/\\s+/)[0];

            return { fullAnswer, doneAnswer, firstWord, chunkCount: textChunks.length };
        }""", [base, streaming_agent_id])

        p.close()
        ctx.close()

        assert 'error' not in result, f"Streaming test failed: {result}"
        assert result['chunkCount'] >= 1, "No text chunks received from stream"
        assert result['firstWord'], "First word of answer is empty"

        # The full answer assembled from chunks must start with the first word
        assert result['fullAnswer'].startswith(result['firstWord']), (
            f"Assembled text is missing the first word.\n"
            f"First word:    {result['firstWord']!r}\n"
            f"Full answer:   {result['fullAnswer']!r}\n"
            f"Done answer:   {result['doneAnswer']!r}\n"
        )

        # If doneAnswer is available, compare it to the assembled chunks
        if result['doneAnswer']:
            assert result['fullAnswer'] == result['doneAnswer'], (
                f"Text assembled from chunks != done.answer.\n"
                f"Chunks: {result['fullAnswer']!r}\n"
                f"Done:   {result['doneAnswer']!r}\n"
                f"This indicates the first chunk is dropped before accumulation."
            )
