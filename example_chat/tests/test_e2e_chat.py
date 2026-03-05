"""End-to-end test: login, create conversation, send message, get LLM response.

Requires a running chat server with Ollama backend.
Run with: pytest example_chat/tests/test_e2e_chat.py -v --base-url http://localhost:5111
"""
import re
import pytest
from playwright.sync_api import Page, expect


BASE_URL = "http://localhost:5111"


@pytest.fixture(scope="module")
def browser_context(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    yield context
    context.close()
    browser.close()


@pytest.fixture
def page(browser_context):
    page = browser_context.new_page()
    yield page
    page.close()


class TestChatE2E:
    def test_login_create_send_receive(self, page: Page):
        """Full flow: login -> new conversation -> send message -> get response."""
        page.goto(BASE_URL)

        # ── Login ──
        # Login form should be visible
        login_overlay = page.locator("#loginOverlay")
        expect(login_overlay).to_be_visible()

        # Fill credentials (alice is seeded)
        page.fill("#loginEmail", "alice@example.com")
        page.fill("#loginPassword", "alice123")
        page.click("#loginForm button")

        # Wait for login to complete — sidebar should appear
        sidebar = page.locator("#sidebar")
        expect(sidebar).to_be_visible(timeout=5000)

        # Login overlay should be hidden
        expect(login_overlay).to_be_hidden()

        # ── LLM status pill should show ready ──
        llm_status = page.locator("#llmStatus .label")
        expect(llm_status).not_to_have_text("Connecting...", timeout=10000)

        # ── Create new conversation ──
        page.click(".btn-new")

        # Wait for the conversation to appear in the sidebar
        page.wait_for_timeout(1000)
        conv_items = page.locator(".conv-item")
        expect(conv_items.first).to_be_visible(timeout=5000)

        # Click the newest conversation (first in list or last created)
        # After creating, it should auto-select, but let's click to be sure
        conv_items.last.click()
        page.wait_for_timeout(500)

        # ── Send a message ──
        chat_input = page.locator("#chatInput")
        expect(chat_input).to_be_visible()

        chat_input.fill("Say hello in exactly 3 words")
        page.click("#btnSend")

        # User message should appear immediately
        user_messages = page.locator(".message.user")
        expect(user_messages.last).to_have_text("Say hello in exactly 3 words", timeout=3000)

        # ── Wait for assistant response ──
        # The typing indicator "..." appears then gets replaced by the real response
        assistant_messages = page.locator(".message.assistant")
        # Wait for a non-"..." assistant message (LLM response, may take a while)
        expect(assistant_messages.last).not_to_have_text("...", timeout=60000)

        # Verify we got a real response (not empty, not an error)
        response_text = assistant_messages.last.text_content()
        assert response_text, "Assistant response should not be empty"
        assert len(response_text) > 0
        print(f"\nLLM Response: {response_text}")

        # ── Verify messages persisted ──
        # Reload the page and check messages are still there
        page.reload()
        page.wait_for_timeout(2000)

        # Need to re-login after reload (token is in localStorage, should persist)
        sidebar_after = page.locator("#sidebar")
        expect(sidebar_after).to_be_visible(timeout=5000)

        # Click the conversation again
        conv_items_after = page.locator(".conv-item")
        expect(conv_items_after.first).to_be_visible(timeout=5000)
        conv_items_after.last.click()
        page.wait_for_timeout(2000)

        # Messages should still be there
        messages_after = page.locator(".message.user")
        expect(messages_after.last).to_be_visible(timeout=5000)
