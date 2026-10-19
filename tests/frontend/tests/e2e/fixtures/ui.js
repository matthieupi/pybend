import { expect } from '@playwright/test';

export async function waitForAppServer(page) {
  await expect.poll(async () => {
    try {
      const resp = await page.request.get('/Product');
      return resp.ok();
    } catch {
      return false;
    }
  }, {
    timeout: 10000,
    intervals: [100, 250, 500],
  }).toBe(true);
}

export async function gotoApp(page, path = '/') {
  let lastError;
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      await page.goto(path, { waitUntil: 'domcontentloaded' });
      return;
    } catch (err) {
      lastError = err;
      if (!String(err?.message || err).includes('ERR_CONNECTION_REFUSED') || attempt === 2) break;
      await waitForAppServer(page);
    }
  }
  throw lastError;
}

export async function reloadApp(page) {
  await page.reload({ waitUntil: 'domcontentloaded' });
}

export async function waitForTopbar(page) {
  await expect(page.locator('ntx-topbar')).toBeVisible();
  await page.waitForFunction(() => {
    const topbar = document.querySelector('ntx-topbar');
    return !!topbar?.shadowRoot?.querySelector('.topbar');
  });
}

export async function waitForAnonymousTopbar(page) {
  await waitForTopbar(page);
  await page.waitForFunction(() => {
    const topbar = document.querySelector('ntx-topbar');
    return !!topbar?.shadowRoot?.querySelector('.signin-link');
  });
}

export async function waitForAuthenticatedTopbar(page) {
  await waitForTopbar(page);
  await page.waitForFunction(() => {
    const topbar = document.querySelector('ntx-topbar');
    return !!topbar?.shadowRoot?.querySelector('.user-pill');
  });
}

export async function waitForProductList(page) {
  await expect(page.locator('#product-list')).toBeVisible();
  await page.waitForFunction(() => {
    const list = document.querySelector('#product-list');
    return !!list?.shadowRoot?.querySelector('.list-grid ntx-item');
  });
}

export async function waitForAppReady(page) {
  await waitForTopbar(page);

  const hash = await page.evaluate(() => window.location.hash || '');
  if (/^#?Product\/\d+/.test(hash)) {
    await waitForRouterItem(page);
    return;
  }

  if (hash && hash !== '#') {
    await waitForRouterContent(page);
    return;
  }

  const hasProductList = await page.locator('#product-list').count();
  if (hasProductList > 0) {
    await waitForProductList(page);
  }
}

export async function waitForRouterContent(page) {
  await expect(page.locator('ntx-router')).toBeVisible();
  await page.waitForFunction(() => {
    const router = document.querySelector('ntx-router');
    return !!router?.shadowRoot?.querySelector('.router-content');
  });
}

export async function waitForRouterItem(page) {
  await waitForRouterContent(page);
  await page.waitForFunction(() => {
    const router = document.querySelector('ntx-router');
    return !!router?.shadowRoot?.querySelector('ntx-item')?.shadowRoot;
  });
}

export async function waitForUiSettled(page) {
  await page.evaluate(() => new Promise((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(resolve));
  }));
}

export async function waitForVeilleUi(page) {
  const hash = await page.evaluate(() => window.location.hash || '');
  if (/^#AgentActor\/\d+/.test(hash)) {
    await expect(page.locator('#agent-detail')).toBeAttached();
    await page.waitForFunction(() => {
      const detail = document.querySelector('#agent-detail');
      const chat = detail?.shadowRoot?.querySelector('ntx-chat');
      return !!chat?.shadowRoot?.querySelector('textarea');
    });
    return;
  }

  await expect(page.locator('.agents-dashboard-card').filter({ hasText: 'Assistant' })).toBeVisible();
}

export async function loginAndOpenVeilleAssistant(page) {
  await page.goto('/login.html', { waitUntil: 'domcontentloaded' });
  await page.fill('#email', 'admin@veille.local');
  await page.fill('#password', 'admin123');
  await page.click('button.auth-btn');
  await page.waitForURL('/');
  await waitForVeilleUi(page);

  await page.locator('.agents-dashboard-card').filter({ hasText: 'Assistant' }).click();
  await page.waitForURL(/#AgentActor\/\d+/);
  await waitForVeilleUi(page);
}

export async function getVeilleChatState(page) {
  return page.locator('#agent-detail').evaluate((el) => {
    const chat = el.shadowRoot?.querySelector('ntx-chat');
    const root = chat?.shadowRoot;
    const textarea = root?.querySelector('textarea');
    const send = root?.querySelector('.send-btn');
    const messages = Array.from(root?.querySelectorAll('.msg') || []).map((node) =>
      node.textContent.replace(/\s+/g, ' ').trim()
    );

    return {
      chatMounted: !!chat,
      hasTextarea: !!textarea,
      textareaValue: textarea?.value || '',
      sendEnabled: !!send && !send.disabled,
      messageCount: messages.length,
      footerCount: root?.querySelectorAll('.stream-footer').length || 0,
      footerText: root?.querySelector('.stream-footer')?.textContent || '',
      messages,
      raw: root?.textContent || '',
    };
  });
}

export async function sendVeilleChatTurn(page, text) {
  const before = await getVeilleChatState(page);

  await page.locator('#agent-detail').evaluate((el, message) => {
    const chat = el.shadowRoot?.querySelector('ntx-chat');
    const textarea = chat?.shadowRoot?.querySelector('textarea');
    const send = chat?.shadowRoot?.querySelector('.send-btn');
    if (!textarea || !send) throw new Error('Veille chat input is not ready');

    textarea.value = message;
    textarea.dispatchEvent(new Event('input', { bubbles: true, composed: true }));
    send.click();
  }, text);

  await page.waitForFunction(({ messageCount, footerCount }) => {
    const detail = document.querySelector('#agent-detail');
    const chat = detail?.shadowRoot?.querySelector('ntx-chat');
    const root = chat?.shadowRoot;
    const send = root?.querySelector('.send-btn');
    const messages = root?.querySelectorAll('.msg').length || 0;
    const footers = root?.querySelectorAll('.stream-footer').length || 0;
    return !!send && !send.disabled && messages >= messageCount + 2 && footers >= footerCount + 1;
  }, { messageCount: before.messageCount, footerCount: before.footerCount });

  return getVeilleChatState(page);
}
