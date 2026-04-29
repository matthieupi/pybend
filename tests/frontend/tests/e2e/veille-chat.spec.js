import { test, expect } from './fixtures/parallel.js';
import {
  loginAndOpenVeilleAssistant,
  sendVeilleChatTurn,
  waitForVeilleUi,
} from './fixtures/ui.js';

test.describe('Veille Assistant chat', () => {
  test('second reply still allows typing into the chat input', async ({ page }) => {
    await loginAndOpenVeilleAssistant(page);
    await sendVeilleChatTurn(page, 'Hello assistant');
    await sendVeilleChatTurn(page, 'And again');

    const state = await page.locator('#agent-detail').evaluate((el) => {
      const chat = el.shadowRoot.querySelector('ntx-chat');
      const textarea = chat.shadowRoot.querySelector('textarea');
      textarea.value = 'Third message';
      textarea.dispatchEvent(new Event('input', { bubbles: true, composed: true }));
      return {
        textareaValue: textarea.value,
        sendEnabled: !chat.shadowRoot.querySelector('.send-btn')?.disabled,
      };
    });

    expect(state.textareaValue).toBe('Third message');
    expect(state.sendEnabled).toBe(true);
  });

  test('second reply still allows sending another message', async ({ page }) => {
    await loginAndOpenVeilleAssistant(page);
    await sendVeilleChatTurn(page, 'Hello assistant');
    await sendVeilleChatTurn(page, 'And again');
    const state = await sendVeilleChatTurn(page, 'Third message');

    expect(state.sendEnabled).toBe(true);
    expect(state.messageCount).toBeGreaterThanOrEqual(6);
    expect(state.messages.some((text) => text.includes('Third message'))).toBe(true);
  });

  test('first reply keeps the chat shell mounted and usable', async ({ page }) => {
    await loginAndOpenVeilleAssistant(page);
    const state = await sendVeilleChatTurn(page, 'Hello assistant');

    expect(state.chatMounted).toBe(true);
    expect(state.hasTextarea).toBe(true);
    expect(state.sendEnabled).toBe(true);
    expect(state.messageCount).toBeGreaterThanOrEqual(2);
    expect(state.footerCount).toBe(1);
    expect(state.footerText).toContain('Tokens:');
  });

  test('second reply does not unmount the chat component', async ({ page }) => {
    await loginAndOpenVeilleAssistant(page);
    await sendVeilleChatTurn(page, 'Hello assistant');
    const state = await sendVeilleChatTurn(page, 'And again');

    expect(state.chatMounted).toBe(true);
    expect(state.hasTextarea).toBe(true);
    expect(state.sendEnabled).toBe(true);
    expect(state.messageCount).toBeGreaterThanOrEqual(4);
  });

  test('second reply preserves route and agent detail visibility', async ({ page }) => {
    await loginAndOpenVeilleAssistant(page);

    const beforeHash = await page.evaluate(() => window.location.hash);

    await sendVeilleChatTurn(page, 'Hello assistant');
    await sendVeilleChatTurn(page, 'And again');

    const state = await page.locator('#agent-detail').evaluate((el) => {
      const panel = document.getElementById('agent-panel');
      return {
        panelVisible: !!panel && getComputedStyle(panel).display !== 'none',
        detailVisible: !!el && getComputedStyle(el).display !== 'none',
      };
    });

    const afterHash = await page.evaluate(() => window.location.hash);

    expect(beforeHash).toMatch(/#AgentActor\/\d+/);
    expect(afterHash).toBe(beforeHash);
    expect(state.panelVisible).toBe(true);
    expect(state.detailVisible).toBe(true);
  });

  test('dashboard opens Assistant and completes a deterministic threaded chat flow', async ({ page }) => {
    const streamPayloads = [];
    page.on('request', (request) => {
      if (request.url().includes('/agentic_stream') && request.method() === 'POST') {
        const payload = request.postDataJSON();
        if (payload) streamPayloads.push(payload);
      }
    });

    await page.goto('/login.html');
    await page.fill('#email', 'admin@veille.local');
    await page.fill('#password', 'admin123');
    await page.click('button.auth-btn');
    await page.waitForURL('/');
    await waitForVeilleUi(page);

    await expect(page.locator('ntx-sidebar')).toContainText('DASHBOARD');
    await expect(page.locator('.agents-dashboard-card').filter({ hasText: 'Assistant' })).toBeVisible();
    await expect(page.locator('.agents-dashboard-card').filter({ hasText: 'Veille Scout' })).toBeVisible();
    await expect(page.locator('.agents-dashboard-card')).toHaveCount(2);

    await page.locator('.agents-dashboard-card').filter({ hasText: 'Assistant' }).click();
    await page.waitForURL(/#AgentActor\/\d+/);
    await waitForVeilleUi(page);

    const detail = page.locator('#agent-detail');
    await expect(detail).toBeAttached();

    const desktopState = await detail.evaluate((el) => {
      const chat = el.shadowRoot?.querySelector('ntx-chat');
      const tab = chat?.shadowRoot?.querySelector('.chat-tab');
      const textarea = chat?.shadowRoot?.querySelector('textarea');
      return {
        hasChat: !!chat,
        hasTextarea: !!textarea,
        inlineMode: !!tab && getComputedStyle(tab).display === 'none',
      };
    });

    expect(desktopState.hasChat).toBe(true);
    expect(desktopState.hasTextarea).toBe(true);
    expect(desktopState.inlineMode).toBe(true);

    const firstTurn = await sendVeilleChatTurn(page, 'Hello assistant');

    expect(firstTurn.messages.some((text) => text.includes('Hello assistant'))).toBe(true);
    expect(firstTurn.messages.some((text) => text.includes('success'))).toBe(true);
    expect(firstTurn.sendEnabled).toBe(true);
    expect(streamPayloads[0]?.thread_id).toBeUndefined();

    const secondTurn = await sendVeilleChatTurn(page, 'And again');

    expect(secondTurn.messages.filter((text) => text.includes('assistant')).length).toBeGreaterThan(1);
    expect(secondTurn.messages.some((text) => text.includes('success'))).toBe(true);
    expect(streamPayloads).toHaveLength(2);
    expect(streamPayloads[1]?.task).toBe('And again');
  });
});
