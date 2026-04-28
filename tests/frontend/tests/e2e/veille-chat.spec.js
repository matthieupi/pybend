import { test, expect } from '@playwright/test';

test.describe('Veille Assistant chat', () => {
  test('second reply still allows typing into the chat input', async ({ page }) => {
    await page.goto('/login.html');
    await page.fill('#email', 'admin@veille.local');
    await page.fill('#password', 'admin123');
    await page.click('button.auth-btn');
    await page.waitForURL('/');
    await page.waitForTimeout(1500);

    await page.locator('.agents-dashboard-card').filter({ hasText: 'Assistant' }).click();
    await page.waitForURL(/#AgentActor\/\d+/);
    await page.waitForTimeout(1500);

    const state = await page.locator('#agent-detail').evaluate(async (el) => {
      const runTurn = async (text) => {
        const chat = el.shadowRoot.querySelector('ntx-chat');
        const textarea = chat.shadowRoot.querySelector('textarea');
        const send = chat.shadowRoot.querySelector('.send-btn');
        textarea.value = text;
        textarea.dispatchEvent(new Event('input', { bubbles: true, composed: true }));
        send.click();
        await new Promise((resolve) => setTimeout(resolve, 2500));
      };

      await runTurn('Hello assistant');
      await runTurn('And again');

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
    await page.goto('/login.html');
    await page.fill('#email', 'admin@veille.local');
    await page.fill('#password', 'admin123');
    await page.click('button.auth-btn');
    await page.waitForURL('/');
    await page.waitForTimeout(1500);

    await page.locator('.agents-dashboard-card').filter({ hasText: 'Assistant' }).click();
    await page.waitForURL(/#AgentActor\/\d+/);
    await page.waitForTimeout(1500);

    const state = await page.locator('#agent-detail').evaluate(async (el) => {
      const runTurn = async (text) => {
        const chat = el.shadowRoot.querySelector('ntx-chat');
        const textarea = chat.shadowRoot.querySelector('textarea');
        const send = chat.shadowRoot.querySelector('.send-btn');
        textarea.value = text;
        textarea.dispatchEvent(new Event('input', { bubbles: true, composed: true }));
        send.click();
        await new Promise((resolve) => setTimeout(resolve, 2500));
      };

      await runTurn('Hello assistant');
      await runTurn('And again');

      const chat = el.shadowRoot.querySelector('ntx-chat');
      const textarea = chat.shadowRoot.querySelector('textarea');
      const send = chat.shadowRoot.querySelector('.send-btn');
      textarea.value = 'Third message';
      textarea.dispatchEvent(new Event('input', { bubbles: true, composed: true }));
      send.click();
      await new Promise((resolve) => setTimeout(resolve, 2500));

      const messages = Array.from(chat.shadowRoot.querySelectorAll('.msg')).map((node) =>
        node.textContent.replace(/\s+/g, ' ').trim()
      );
      return {
        sendEnabled: !send.disabled,
        messageCount: chat.shadowRoot.querySelectorAll('.msg').length,
        messages,
      };
    });

    expect(state.sendEnabled).toBe(true);
    expect(state.messageCount).toBeGreaterThanOrEqual(6);
    expect(state.messages.some((text) => text.includes('Third message'))).toBe(true);
  });

  test('first reply keeps the chat shell mounted and usable', async ({ page }) => {
    await page.goto('/login.html');
    await page.fill('#email', 'admin@veille.local');
    await page.fill('#password', 'admin123');
    await page.click('button.auth-btn');
    await page.waitForURL('/');
    await page.waitForTimeout(1500);

    await page.locator('.agents-dashboard-card').filter({ hasText: 'Assistant' }).click();
    await page.waitForURL(/#AgentActor\/\d+/);
    await page.waitForTimeout(1500);

    const state = await page.locator('#agent-detail').evaluate(async (el) => {
      const chat = el.shadowRoot.querySelector('ntx-chat');
      const textarea = chat?.shadowRoot?.querySelector('textarea');
      const send = chat?.shadowRoot?.querySelector('.send-btn');
      textarea.value = 'Hello assistant';
      textarea.dispatchEvent(new Event('input', { bubbles: true, composed: true }));
      send.click();
      await new Promise((resolve) => setTimeout(resolve, 2500));
      return {
        chatMounted: !!el.shadowRoot.querySelector('ntx-chat'),
        hasTextarea: !!chat?.shadowRoot?.querySelector('textarea'),
        sendEnabled: !chat?.shadowRoot?.querySelector('.send-btn')?.disabled,
        messageCount: chat?.shadowRoot?.querySelectorAll('.msg').length || 0,
        footerCount: chat?.shadowRoot?.querySelectorAll('.stream-footer').length || 0,
        footerText: chat?.shadowRoot?.querySelector('.stream-footer')?.textContent || '',
      };
    });

    expect(state.chatMounted).toBe(true);
    expect(state.hasTextarea).toBe(true);
    expect(state.sendEnabled).toBe(true);
    expect(state.messageCount).toBeGreaterThanOrEqual(2);
    expect(state.footerCount).toBe(1);
    expect(state.footerText).toContain('Tokens:');
  });

  test('second reply does not unmount the chat component', async ({ page }) => {
    await page.goto('/login.html');
    await page.fill('#email', 'admin@veille.local');
    await page.fill('#password', 'admin123');
    await page.click('button.auth-btn');
    await page.waitForURL('/');
    await page.waitForTimeout(1500);

    await page.locator('.agents-dashboard-card').filter({ hasText: 'Assistant' }).click();
    await page.waitForURL(/#AgentActor\/\d+/);
    await page.waitForTimeout(1500);

    const state = await page.locator('#agent-detail').evaluate(async (el) => {
      const runTurn = async (text) => {
        const chat = el.shadowRoot.querySelector('ntx-chat');
        const textarea = chat?.shadowRoot?.querySelector('textarea');
        const send = chat?.shadowRoot?.querySelector('.send-btn');
        textarea.value = text;
        textarea.dispatchEvent(new Event('input', { bubbles: true, composed: true }));
        send.click();
        await new Promise((resolve) => setTimeout(resolve, 2500));
      };

      await runTurn('Hello assistant');
      await runTurn('And again');

      const chat = el.shadowRoot.querySelector('ntx-chat');
      return {
        chatMounted: !!chat,
        hasTextarea: !!chat?.shadowRoot?.querySelector('textarea'),
        sendEnabled: !chat?.shadowRoot?.querySelector('.send-btn')?.disabled,
        messageCount: chat?.shadowRoot?.querySelectorAll('.msg').length || 0,
      };
    });

    expect(state.chatMounted).toBe(true);
    expect(state.hasTextarea).toBe(true);
    expect(state.sendEnabled).toBe(true);
    expect(state.messageCount).toBeGreaterThanOrEqual(4);
  });

  test('second reply preserves route and agent detail visibility', async ({ page }) => {
    await page.goto('/login.html');
    await page.fill('#email', 'admin@veille.local');
    await page.fill('#password', 'admin123');
    await page.click('button.auth-btn');
    await page.waitForURL('/');
    await page.waitForTimeout(1500);

    await page.locator('.agents-dashboard-card').filter({ hasText: 'Assistant' }).click();
    await page.waitForURL(/#AgentActor\/\d+/);
    await page.waitForTimeout(1500);

    const beforeHash = await page.evaluate(() => window.location.hash);

    const state = await page.locator('#agent-detail').evaluate(async (el) => {
      const runTurn = async (text) => {
        const chat = el.shadowRoot.querySelector('ntx-chat');
        const textarea = chat?.shadowRoot?.querySelector('textarea');
        const send = chat?.shadowRoot?.querySelector('.send-btn');
        textarea.value = text;
        textarea.dispatchEvent(new Event('input', { bubbles: true, composed: true }));
        send.click();
        await new Promise((resolve) => setTimeout(resolve, 2500));
      };

      await runTurn('Hello assistant');
      await runTurn('And again');

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
    await page.waitForTimeout(1500);

    await expect(page.locator('ntx-sidebar')).toContainText('DASHBOARD');
    await expect(page.locator('.agents-dashboard-card').filter({ hasText: 'Assistant' })).toBeVisible();
    await expect(page.locator('.agents-dashboard-card').filter({ hasText: 'Veille Scout' })).toBeVisible();
    await expect(page.locator('.agents-dashboard-card')).toHaveCount(2);

    await page.locator('.agents-dashboard-card').filter({ hasText: 'Assistant' }).click();
    await page.waitForURL(/#AgentActor\/\d+/);
    await page.waitForTimeout(1500);

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

    const firstTurn = await detail.evaluate(async (el) => {
      const chat = el.shadowRoot.querySelector('ntx-chat');
      const textarea = chat.shadowRoot.querySelector('textarea');
      const send = chat.shadowRoot.querySelector('.send-btn');
      textarea.value = 'Hello assistant';
      textarea.dispatchEvent(new Event('input', { bubbles: true, composed: true }));
      send.click();
      await new Promise((resolve) => setTimeout(resolve, 2500));

      const messages = Array.from(chat.shadowRoot.querySelectorAll('.msg')).map((node) => node.textContent.replace(/\s+/g, ' ').trim());
      return {
        sendDisabled: send.disabled,
        messages,
        raw: chat.shadowRoot.textContent,
      };
    });

    expect(firstTurn.messages.some((text) => text.includes('Hello assistant'))).toBe(true);
    expect(firstTurn.messages.some((text) => text.includes('success'))).toBe(true);
    expect(firstTurn.sendDisabled).toBe(false);
    expect(streamPayloads[0]?.thread_id).toBeUndefined();

    const secondTurn = await detail.evaluate(async (el) => {
      const chat = el.shadowRoot.querySelector('ntx-chat');
      const textarea = chat.shadowRoot.querySelector('textarea');
      const send = chat.shadowRoot.querySelector('.send-btn');
      const waitUntilEnabled = async () => {
        const start = Date.now();
        while (send.disabled && Date.now() - start < 5000) {
          await new Promise((resolve) => setTimeout(resolve, 100));
        }
      };

      await waitUntilEnabled();
      textarea.value = 'And again';
      textarea.dispatchEvent(new Event('input', { bubbles: true, composed: true }));
      send.click();
      await new Promise((resolve) => setTimeout(resolve, 2500));

      const messages = Array.from(chat.shadowRoot.querySelectorAll('.msg')).map((node) => node.textContent.replace(/\s+/g, ' ').trim());
      return {
        messages,
        messageCount: chat.shadowRoot.querySelectorAll('.msg').length,
        raw: chat.shadowRoot.textContent,
      };
    });

    expect(secondTurn.messages.filter((text) => text.includes('assistant')).length).toBeGreaterThan(1);
    expect(secondTurn.messages.some((text) => text.includes('success'))).toBe(true);
    expect(streamPayloads).toHaveLength(2);
    expect(streamPayloads[1]?.task).toBe('And again');
  });
});
