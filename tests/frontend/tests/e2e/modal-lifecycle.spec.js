import { test, expect } from '@playwright/test';
import { readFile } from 'node:fs/promises';

const assets = new URL('../../../../packages/n3tx-ui/src/n3tx_ui/static/components/', import.meta.url);
const origin = 'http://modal-lifecycle.invalid';

// Declared synthetic stylesheet fixture of Collagen static/collagen.css's
// 2026-10-21 reduced-motion interaction. Not a copy of application source:
// only the consumed global suppression rule is modeled; private shadow CSS
// remains the actual native asset. Descendant motion is injected where needed.
const appMotionFixture = `@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation: none !important;
    transition: none !important;
    scroll-behavior: auto !important;
  }
}`;

test.beforeEach(async ({ page }) => {
  await page.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.origin !== origin) return route.abort();
    if (url.pathname === '/') return route.fulfill({
      contentType: 'text/html',
      body: `<!doctype html><html><head><style>${appMotionFixture}</style></head>
        <body><button id="opener">Open</button><script type="module">
        import { NTTModal } from '/components/ntx-modal.js';
        window.NTTModal = NTTModal;
        window.records = [];
        </script></body></html>`,
    });
    const name = url.pathname.slice('/components/'.length);
    if (url.pathname === `/components/${name}` && ['ntx-modal.js', 'ntx-modal.css'].includes(name)) {
      return route.fulfill({
        contentType: name.endsWith('.js') ? 'text/javascript' : 'text/css',
        body: await readFile(new URL(name, assets)),
      });
    }
    return route.abort();
  });
  await page.goto(origin);
  await page.waitForFunction(() => !!window.NTTModal);
  await page.locator('#opener').focus();
});

test.afterEach(async ({ page }, testInfo) => {
  await testInfo.attach('lifecycle-state', {
    contentType: 'application/json',
    body: JSON.stringify(await page.evaluate(() => ({
      reducedMotion: matchMedia('(prefers-reduced-motion: reduce)').matches,
      bodyStyle: document.body.style.cssText,
      activeElement: document.activeElement?.outerHTML,
      records: window.records?.map(r => ({
        connected: r.modal.isConnected, classes: r.modal.className,
        hostAnimation: getComputedStyle(r.modal).animationName,
        panelAnimation: r.modal.shadowRoot.querySelector('.modal-panel') ?
          getComputedStyle(r.modal.shadowRoot.querySelector('.modal-panel')).animationName : null,
        events: r.events, settlements: r.settlements, result: r.result,
        animationEvents: r.animationEvents,
      })),
    })), null, 2),
  });
});

async function openModal(page, { ready = true } = {}) {
  const index = await page.evaluate(() => {
    const promise = NTTModal.prompt({ title: 'Synthetic lifecycle regression' });
    const modal = [...document.querySelectorAll('ntx-modal')].at(-1);
    const record = { modal, events: [], settlements: 0, animationEvents: [] };
    records.push(record);
    modal.addEventListener('modal-close', event => record.events.push(event.detail));
    for (const name of ['animationstart', 'animationend', 'animationcancel']) {
      modal.addEventListener(name, event => record.animationEvents.push({
        type: name, name: event.animationName, trusted: event.isTrusted,
        target: event.target === modal ? 'host' : 'descendant',
      }));
    }
    promise.then(result => { record.settlements++; record.result = result; });
    return records.length - 1;
  });
  if (ready) {
    await page.waitForFunction(i => records[i].modal.shadowRoot.adoptedStyleSheets.length === 1, index);
    await page.waitForFunction(i => records[i].modal.shadowRoot.activeElement?.className === 'close-btn', index);
  }
  return index;
}

async function expectClosed(page, index, reason = 'cancel') {
  await expect.poll(() => page.evaluate(i => {
    const r = records[i];
    return { connected: r.modal.isConnected, events: r.events, settlements: r.settlements, result: r.result };
  }, index)).toEqual({ connected: false, events: [{ reason }], settlements: 1, result: { reason } });
}

for (const reducedMotion of ['no-preference', 'reduce']) {
  test(`close removes node and settles once: ${reducedMotion}`, async ({ page }) => {
    await page.emulateMedia({ reducedMotion });
    const index = await openModal(page);
    const before = await page.evaluate(i => ({
      host: getComputedStyle(records[i].modal).animationName,
      panel: getComputedStyle(records[i].modal.shadowRoot.querySelector('.modal-panel')).animationName,
    }), index);
    expect(before).toEqual({ host: reducedMotion === 'reduce' ? 'none' : 'modalFadeIn', panel: 'none' });
    const immediate = await page.evaluate(i => {
      records[i].modal.close('submit');
      return { connected: records[i].modal.isConnected, animation: getComputedStyle(records[i].modal).animationName };
    }, index);
    if (reducedMotion === 'no-preference') expect(immediate).toEqual({ connected: true, animation: 'modalFadeOut' });
    await expectClosed(page, index, 'submit');
    await expect(page.locator('body')).toHaveCSS('overflow', 'visible');
  });

  test(`restores preexisting body styles and opener focus: ${reducedMotion}`, async ({ page }) => {
    await page.emulateMedia({ reducedMotion });
    const before = await page.evaluate(() => {
      document.body.style.cssText = 'overflow: scroll !important; color: rgb(1, 2, 3);';
      return document.body.style.cssText;
    });
    const index = await openModal(page);
    await page.evaluate(i => records[i].modal.close(), index);
    await expectClosed(page, index);
    expect(await page.evaluate(() => document.body.style.cssText)).toBe(before);
    await expect(page.locator('#opener')).toBeFocused();
  });
}

test('absent host animation does not await private panel animation', async ({ page }) => {
  await page.addStyleTag({ content: 'ntx-modal { animation: none !important; }' });
  const index = await openModal(page);
  await page.evaluate(i => {
    const modal = records[i].modal;
    modal.shadowRoot.querySelector('.modal-panel').animate(
      [{ opacity: 0.5 }, { opacity: 1 }], { duration: 1000, iterations: Infinity });
    modal.close();
  }, index);
  await expectClosed(page, index);
});

for (const interruption of ['cancel', 'suppress', 'remove', 'pause', 'zero-rate']) {
  test(`interrupted exit completes cleanup: ${interruption}`, async ({ page }) => {
    const index = await openModal(page);
    await page.evaluate(({ index, interruption }) => {
      const modal = records[index].modal;
      modal.close();
      const animation = modal.getAnimations().find(a => a.effect.target === modal);
      if (!animation) throw new Error('Expected actual host exit animation');
      if (interruption === 'cancel') animation.cancel();
      if (interruption === 'suppress') modal.style.animation = 'none';
      if (interruption === 'remove') modal.remove();
      if (interruption === 'pause') animation.pause();
      if (interruption === 'zero-rate') animation.playbackRate = 0;
    }, { index, interruption });
    await expectClosed(page, index);
    await expect(page.locator('body')).toHaveCSS('overflow', 'visible');
    await expect(page.locator('#opener')).toBeFocused();
  });
}

test('repeated close retains first reason and dispatches once', async ({ page }) => {
  const index = await openModal(page);
  await page.evaluate(i => {
    records[i].modal.close('submit');
    records[i].modal.close('cancel');
  }, index);
  await expectClosed(page, index, 'submit');
  await page.evaluate(i => records[i].modal.close('escape'), index);
  await expectClosed(page, index, 'submit');
});

test('descendant animationend cannot finish host exit', async ({ page }) => {
  const index = await openModal(page);
  const connected = await page.evaluate(i => {
    const modal = records[i].modal;
    modal.close();
    const child = document.createElement('span');
    modal.append(child);
    child.dispatchEvent(new AnimationEvent('animationend', { bubbles: true, animationName: 'unrelated' }));
    return modal.isConnected;
  }, index);
  expect(connected).toBe(true);
  await expectClosed(page, index);
});

for (const order of ['inner-first', 'outer-first']) {
  test(`nested modal scroll and focus ownership: ${order}`, async ({ page }) => {
    await page.evaluate(() => { document.body.style.overflow = 'auto'; });
    const outer = await openModal(page);
    const inner = await openModal(page);
    const first = order === 'inner-first' ? inner : outer;
    const second = order === 'inner-first' ? outer : inner;
    await page.evaluate(i => records[i].modal.close(), first);
    await expectClosed(page, first);
    await expect(page.locator('body')).toHaveCSS('overflow', 'hidden');
    expect(await page.evaluate(i => document.activeElement === records[i].modal &&
      records[i].modal.shadowRoot.activeElement?.className === 'close-btn', second)).toBe(true);
    await page.evaluate(i => records[i].modal.close(), second);
    await expectClosed(page, second);
    await expect(page.locator('body')).toHaveCSS('overflow', 'auto');
    await expect(page.locator('#opener')).toBeFocused();
  });
}

test('Escape closes only the top modal', async ({ page }) => {
  const outer = await openModal(page);
  const inner = await openModal(page);
  await page.keyboard.press('Escape');
  await expectClosed(page, inner, 'escape');
  expect(await page.evaluate(i => records[i].modal.isConnected, outer)).toBe(true);
  await expect(page.locator('body')).toHaveCSS('overflow', 'hidden');
  await page.keyboard.press('Escape');
  await expectClosed(page, outer, 'escape');
});

test('empty stylesheet does not strand the modal', async ({ page }) => {
  await page.route('**/ntx-modal.css', route => route.fulfill({ contentType: 'text/css', body: '' }));
  const index = await openModal(page, { ready: false });
  await page.evaluate(i => records[i].modal.close(), index);
  await expectClosed(page, index);
  await expect(page.locator('#opener')).toBeFocused();
});

test('preserves independently prioritized body overflow axes', async ({ page }) => {
  const before = await page.evaluate(() => {
    document.body.style.cssText = 'overflow-x: scroll !important; overflow-y: auto; color: red;';
    return document.body.style.cssText;
  });
  const index = await openModal(page);
  await page.evaluate(i => records[i].modal.close(), index);
  await expectClosed(page, index);
  expect(await page.evaluate(() => document.body.style.cssText)).toBe(before);
});

test('close before delayed stylesheet adoption cleans up and keeps focus', async ({ page }) => {
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  await page.route('**/ntx-modal.css', async route => {
    await gate;
    await route.fulfill({ contentType: 'text/css', body: await readFile(new URL('ntx-modal.css', assets)) });
  });
  try {
    const index = await openModal(page, { ready: false });
    expect(await page.evaluate(i => records[i].modal.shadowRoot.adoptedStyleSheets.length, index)).toBe(0);
    await page.evaluate(i => records[i].modal.close(), index);
    await expectClosed(page, index);
    release();
    await page.waitForFunction(i => records[i].modal.shadowRoot.adoptedStyleSheets.length === 1, index);
    await expectClosed(page, index);
    await expect(page.locator('#opener')).toBeFocused();
  } finally {
    release();
  }
});

test('NML-R1: upgrades two declarative modals present before module import', async ({ page }, testInfo) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route(`${origin}/declarative`, route => route.fulfill({
    contentType: 'text/html',
    body: `<!doctype html><html><body><button id="opener">Open</button>
      <script>document.querySelector('#opener').focus(); window.records = [];</script>
      <ntx-modal></ntx-modal><ntx-modal></ntx-modal>
      <script type="module">
      import { NTTModal } from '/components/ntx-modal.js';
      window.NTTModal = NTTModal;
      for (const modal of document.querySelectorAll('ntx-modal')) {
        const record = { modal, events: [], settlements: 0, animationEvents: [] };
        records.push(record);
        modal.addEventListener('modal-close', event => record.events.push(event.detail));
      }
      </script></body></html>`,
  }));
  await page.goto(`${origin}/declarative`);
  await page.waitForFunction(() => records.length === 2);
  await testInfo.attach('upgrade-errors', { contentType: 'application/json', body: JSON.stringify(errors) });
  expect(errors).toEqual([]);
  await page.waitForFunction(() => records.every(r => r.modal.shadowRoot.adoptedStyleSheets.length === 1));
  await expect(page.locator('ntx-modal [role="dialog"]')).toHaveCount(2);
  await expect(page.locator('body')).toHaveCSS('overflow', 'hidden');
  await page.evaluate(() => records[1].modal.close());
  await expect(page.locator('ntx-modal')).toHaveCount(1);
  await expect(page.locator('body')).toHaveCSS('overflow', 'hidden');
  await page.evaluate(() => records[0].modal.close());
  await expect(page.locator('ntx-modal')).toHaveCount(0);
  await expect(page.locator('body')).toHaveCSS('overflow', 'visible');
  expect(await page.evaluate(() => records.map(r => r.events))).toEqual([[{ reason: 'cancel' }], [{ reason: 'cancel' }]]);
  await expect(page.locator('#opener')).toBeFocused();
});

for (const variant of ['after-inner-focus', 'before-focus-inner-first', 'before-focus-outer-first']) {
  test(`NML-R2: rapid opens retain surviving modal focus: ${variant}`, async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    const first = variant === 'before-focus-outer-first' ? 0 : 1;
    const second = 1 - first;
    const immediate = await page.evaluate(({ variant, first, second }) => {
      document.body.style.overflow = 'auto';
      document.querySelector('#opener').focus();
      // Both opens deliberately occur in one task, before either initial-focus RAF.
      for (let i = 0; i < 2; i++) {
        const promise = NTTModal.prompt({ title: `Rapid modal ${i}` });
        const modal = [...document.querySelectorAll('ntx-modal')].at(-1);
        const record = { modal, events: [], settlements: 0, animationEvents: [] };
        records.push(record);
        modal.addEventListener('modal-close', event => record.events.push(event.detail));
        promise.then(result => { record.settlements++; record.result = result; });
      }
      if (variant === 'after-inner-focus') return null;
      records[first].modal.close('submit');
      records[first].modal.close('cancel');
      return document.activeElement === records[second].modal &&
        records[second].modal.shadowRoot.activeElement?.className === 'close-btn';
    }, { variant, first, second });
    if (variant === 'after-inner-focus') {
      await page.waitForFunction(() => records[1].modal.shadowRoot.activeElement?.className === 'close-btn');
      await page.evaluate(() => {
        records[1].modal.close('submit');
        records[1].modal.close('cancel');
      });
    } else {
      // Assert in the closing task, not after the survivor's pending RAF masks it.
      expect(immediate).toBe(true);
    }
    await expectClosed(page, first, 'submit');
    expect(await page.evaluate(i => records[i].modal.isConnected &&
      document.activeElement === records[i].modal &&
      records[i].modal.shadowRoot.activeElement?.className === 'close-btn', second)).toBe(true);
    await expect(page.locator('body')).toHaveCSS('overflow', 'hidden');
    await page.evaluate(i => records[i].modal.close(), second);
    await expectClosed(page, second);
    await expect(page.locator('body')).toHaveCSS('overflow', 'auto');
    await expect(page.locator('#opener')).toBeFocused();
  });
}
