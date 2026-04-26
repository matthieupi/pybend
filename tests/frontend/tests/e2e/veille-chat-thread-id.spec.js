import { test, expect } from '@playwright/test';

async function loginAndOpenAssistant(page) {
  await page.goto('/login.html');
  await page.fill('#email', 'admin@veille.local');
  await page.fill('#password', 'admin123');
  await page.click('button.auth-btn');
  await page.waitForURL('/');
  await page.waitForTimeout(1500);
  await page.locator('.agents-dashboard-card').filter({ hasText: 'Assistant' }).click();
  await page.waitForURL(/#AgentActor\/\d+/);
  await page.waitForTimeout(1500);
}

test('second chat request includes thread_id from the current conversation', async ({ page }) => {
  const streamPayloads = [];
  page.on('request', (request) => {
    if (request.url().includes('/agentic_stream') && request.method() === 'POST') {
      streamPayloads.push(request.postDataJSON());
    }
  });

  await loginAndOpenAssistant(page);

  await page.locator('#agent-detail').evaluate(async (el) => {
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
    await runTurn('What did I just ask you?');
  });

  expect(streamPayloads).toHaveLength(2);
  expect(streamPayloads[0]?.thread_id).toBeUndefined();
  expect(streamPayloads[1]?.thread_id).toBeTruthy();
});
