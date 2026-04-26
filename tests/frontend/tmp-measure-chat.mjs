import { chromium } from '@playwright/test';

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });

try {
  await page.goto('http://localhost:5018/login.html');
  await page.fill('#email', 'admin@veille.local');
  await page.fill('#password', 'admin123');
  await page.click('button.auth-btn');
  await page.waitForURL('http://localhost:5018/');
  await page.waitForTimeout(1500);
  await page.locator('.agents-dashboard-card').filter({ hasText: 'Assistant' }).click();
  await page.waitForURL(/#AgentActor\/\d+/);
  await page.waitForTimeout(1500);
  const data = await page.locator('#agent-detail').evaluate(async (el) => {
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
    const panel = chat.shadowRoot.querySelector('.panel');
    const input = chat.shadowRoot.querySelector('.chat-input');
    const messages = chat.shadowRoot.querySelector('.chat-messages');
    const hostRect = chat.getBoundingClientRect();
    const panelRect = panel.getBoundingClientRect();
    const inputRect = input.getBoundingClientRect();
    const messagesRect = messages.getBoundingClientRect();
    return {
      scrollY: window.scrollY,
      viewportHeight: window.innerHeight,
      hostRect,
      hostOffsetHeight: chat.offsetHeight,
      hostOffsetTop: chat.offsetTop,
      panelRect,
      panelOffsetHeight: panel.offsetHeight,
      panelScrollHeight: panel.scrollHeight,
      panelDisplay: getComputedStyle(panel).display,
      inputRect,
      inputOffsetTop: input.offsetTop,
      inputVisible: input.checkVisibility ? input.checkVisibility() : true,
      inputDisplay: getComputedStyle(input).display,
      messagesRect,
      messagesOffsetHeight: messages.offsetHeight,
      messagesDisplay: getComputedStyle(messages).display,
      rootChildren: Array.from(chat.shadowRoot.children).map((node) => ({
        tag: node.tagName,
        className: node.className || '',
        text: (node.textContent || '').replace(/\s+/g, ' ').trim(),
      })),
      bodyScrollHeight: document.body.scrollHeight,
      bodyClientHeight: document.documentElement.clientHeight,
    };
  });
  console.log(JSON.stringify(data, null, 2));
} finally {
  await browser.close();
}
