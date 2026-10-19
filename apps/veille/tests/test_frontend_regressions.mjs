import test from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';

const { chromium } = await import('file:///workspace/tests/frontend/node_modules/playwright/index.mjs');

const APP_DIR = '/workspace/apps/veille';
const PYTHON = '/workspace/.venv-e2e/bin/python';
const PORT = 4110;
const BASE_URL = `http://localhost:${PORT}`;
const PYTHONPATH = [
  '/workspace/packages/n3tx-core/src',
  '/workspace/packages/n3tx-actors/src',
  '/workspace/packages/n3tx-agents/src',
  '/workspace/packages/n3tx-ui/src',
].join(':');

let serverProcess = null;
let browser = null;
let dbDir = null;
let dbPath = null;

async function waitForServer(url, timeoutMs = 45000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    try {
      const response = await fetch(url, { cache: 'no-store' });
      if (response.ok) return;
    } catch {}
    await delay(500);
  }
  throw new Error(`Server did not start: ${url}`);
}

async function seedTestDatabase(env) {
  await new Promise((resolve, reject) => {
    const seedProcess = spawn(PYTHON, ['seed.py', '--reset'], {
      cwd: APP_DIR,
      env,
      stdio: 'ignore',
    });
    seedProcess.once('error', reject);
    seedProcess.once('exit', (code) => {
      if (code === 0) resolve();
      else reject(new Error(`Veille seed failed with exit code ${code}`));
    });
  });
}

async function startServer() {
  if (serverProcess) return;
  dbDir = await mkdtemp(join(tmpdir(), 'veille-p4-'));
  dbPath = join(dbDir, 'veille-test.db');
  const env = {
    ...process.env,
    PYTHONPATH,
    N3TX_PORT: String(PORT),
    N3TX_API_URL: BASE_URL,
    N3TX_SQLITE_DB: dbPath,
  };
  await seedTestDatabase(env);
  serverProcess = spawn(PYTHON, ['main.py'], {
    cwd: APP_DIR,
    env,
    stdio: 'ignore',
  });
  await waitForServer(`${BASE_URL}/login.html`);
}

async function stopServer() {
  if (serverProcess) {
    serverProcess.kill('SIGTERM');
    await Promise.race([
      new Promise((resolve) => serverProcess.once('exit', resolve)),
      delay(10000).then(() => serverProcess.kill('SIGKILL')),
    ]);
    serverProcess = null;
  }
  if (dbDir) {
    await rm(dbDir, { recursive: true, force: true });
    dbDir = null;
    dbPath = null;
  }
}

async function getBrowser() {
  if (!browser) {
    browser = await chromium.launch({ headless: true, args: ['--disable-http-cache'] });
  }
  return browser;
}

async function newPage() {
  const instance = await getBrowser();
  return instance.newPage({ viewport: { width: 1440, height: 1200 } });
}

async function login(page) {
  await page.goto(`${BASE_URL}/login.html`, { waitUntil: 'networkidle' });
  await page.fill('#email', 'admin@veille.local');
  await page.fill('#password', 'admin123');
  await Promise.all([
    page.waitForURL(`${BASE_URL}/`),
    page.click('button[type="submit"]'),
  ]);
  await page.waitForLoadState('networkidle');
}

async function sidebarClick(page, label) {
  await page.locator('ntx-sidebar').evaluate((el, target) => {
    const root = el.shadowRoot;
    const item = [...root.querySelectorAll('.model-name')].find((node) => node.textContent.trim() === target);
    if (!item) throw new Error(`Missing sidebar item: ${target}`);
    item.click();
  }, label);
}

async function sidebarExpand(page, modelName) {
  await page.locator('ntx-sidebar').evaluate((el, target) => {
    const root = el.shadowRoot;
    const header = root.querySelector(`.model-section[data-model="${target}"] .model-header`);
    if (!header) throw new Error(`Missing sidebar header: ${target}`);
    header.click();
  }, modelName);
}

async function routeSignature(page) {
  return page.locator('ntx-router').evaluate((el) => {
    const content = el.shadowRoot?.querySelector('.router-content') || el.shadowRoot;
    if (!content) return '';
    const tags = [...content.children].map((child) => {
      const bits = [child.tagName.toLowerCase()];
      if (child.getAttribute('model')) bits.push(`model=${child.getAttribute('model')}`);
      if (child.className) bits.push(`class=${child.className}`);
      return bits.join(':');
    });
    const text = content.textContent.replace(/\s+/g, ' ').trim().slice(0, 240);
    return `${tags.join('|')}::${text}`;
  });
}

async function waitForRouteSignature(page, expected, timeoutMs = 10000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    if ((await routeSignature(page)) === expected) return;
    await delay(200);
  }
  assert.equal(await routeSignature(page), expected, 'expected router to return to the index view');
}

async function clickSidebarHome(page) {
  await page.locator('ntx-sidebar').evaluate((el) => {
    const root = el.shadowRoot;
    const candidates = [
      '.sidebar-brand-copy',
      '.sidebar-brand-title',
      '.sidebar-brand',
      '.sidebar-header .sidebar-title',
      '.sidebar-header',
      'header',
    ];
    const target = candidates.map((selector) => root.querySelector(selector)).find(Boolean);
    if (!target) throw new Error('Missing sidebar home target');
    target.click();
  });
}

async function clickNewPipeline(page) {
  await page.locator('.veille-shell-cta').click();
}

async function clickAnalytics(page) {
  await page.locator('.veille-topbar-icon').first().click();
}

async function openProfileFromTopbar(page) {
  await page.locator('ntx-topbar').evaluate((el) => {
    const root = el.shadowRoot;
    const link = [...root.querySelectorAll('a.dropdown-item')]
      .find((node) => node.textContent.trim() === 'Profile');
    if (!link) throw new Error('Missing profile link');
    link.click();
  });
}

async function profileState(page) {
  return page.locator('ntx-router').evaluate((el) => {
    const content = el.shadowRoot?.querySelector('.router-content');
    const profile = content?.querySelector('ntx-profile');
    const root = profile?.shadowRoot;
    const text = root?.textContent?.replace(/\s+/g, ' ').trim() || '';
    return {
      mounted: !!profile,
      registered: !!customElements.get('ntx-profile'),
      hasShadowRoot: !!root,
      hasCard: !!root?.querySelector('.profile-card'),
      text,
      email: root?.querySelector('.email')?.textContent?.trim() || '',
      role: root?.querySelector('.role')?.textContent?.trim() || '',
    };
  });
}

async function waitForProfile(page, timeoutMs = 10000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const state = await profileState(page);
    if (state.hasCard) return state;
    await delay(200);
  }
  assert.equal((await profileState(page)).hasCard, true, 'expected profile card to render');
}

test.before(async () => {
  await startServer();
});

test.after(async () => {
  if (browser) await browser.close();
  await stopServer();
});

test('grant page renders cards after sidebar navigation', async () => {
  const page = await newPage();
  const errors = [];
  page.on('pageerror', (error) => errors.push(String(error)));

  try {
    await login(page);
    await sidebarClick(page, 'Grant');
    await delay(1500);

    const cardCount = await page.locator('ntx-router').evaluate((el) => {
      const list = el.shadowRoot.querySelector('.router-content ntx-list');
      const grid = list?.shadowRoot?.querySelector('.list-grid');
      return grid ? grid.children.length : 0;
    });

    assert.deepEqual(errors, []);
    assert.ok(cardCount > 0, 'expected grant cards to render');
  } finally {
    await page.close();
  }
});

test('source page renders rows after sidebar navigation', async () => {
  const page = await newPage();
  const errors = [];
  page.on('pageerror', (error) => errors.push(String(error)));

  try {
    await login(page);
    await sidebarClick(page, 'Source');
    await delay(1500);

    const rowCount = await page.locator('ntx-router').evaluate((el) => {
      const table = el.shadowRoot.querySelector('.router-content ntx-table');
      const body = table?.shadowRoot?.querySelector('.table-body');
      return body ? body.children.length : 0;
    });

    assert.deepEqual(errors, []);
    assert.ok(rowCount > 0, 'expected source rows to render');
  } finally {
    await page.close();
  }
});

test('source accordion in sidebar renders nested records', async () => {
  const page = await newPage();
  const errors = [];
  page.on('pageerror', (error) => errors.push(String(error)));

  try {
    await login(page);
    await sidebarExpand(page, 'Source');
    await delay(1500);

    const nestedCount = await page.locator('ntx-sidebar').evaluate((el) => {
      const root = el.shadowRoot;
      const list = root.querySelector('.model-section[data-model="Source"] .model-records ntx-list');
      const grid = list?.shadowRoot?.querySelector('.list-grid');
      return grid ? grid.children.length : 0;
    });

    assert.deepEqual(errors, []);
    assert.ok(nestedCount > 0, 'expected sidebar accordion records to render');
  } finally {
    await page.close();
  }
});

test('sidebar header returns to the index page', async () => {
  const page = await newPage();
  const errors = [];
  page.on('pageerror', (error) => errors.push(String(error)));

  try {
    await login(page);
    const home = await routeSignature(page);
    await sidebarClick(page, 'Grant');
    await delay(1500);
    assert.notEqual(await routeSignature(page), home, 'expected to leave the index view before clicking home');

    await clickSidebarHome(page);
    await waitForRouteSignature(page, home);

    assert.deepEqual(errors, []);
  } finally {
    await page.close();
  }
});

test('new pipeline action returns to the index page', async () => {
  const page = await newPage();
  const errors = [];
  page.on('pageerror', (error) => errors.push(String(error)));

  try {
    await login(page);
    const home = await routeSignature(page);
    await sidebarClick(page, 'Source');
    await delay(1500);
    assert.notEqual(await routeSignature(page), home, 'expected to leave the index view before clicking new pipeline');

    await clickNewPipeline(page);
    await waitForRouteSignature(page, home);

    assert.deepEqual(errors, []);
  } finally {
    await page.close();
  }
});

test('topbar analytics action returns to the index page', async () => {
  const page = await newPage();
  const errors = [];
  page.on('pageerror', (error) => errors.push(String(error)));

  try {
    await login(page);
    const home = await routeSignature(page);
    await sidebarClick(page, 'Grant');
    await delay(1500);
    assert.notEqual(await routeSignature(page), home, 'expected to leave the index view before clicking analytics');

    await clickAnalytics(page);
    await waitForRouteSignature(page, home);

    assert.deepEqual(errors, []);
  } finally {
    await page.close();
  }
});

test('direct profile route renders the shared profile page', async () => {
  const page = await newPage();
  const errors = [];
  page.on('pageerror', (error) => errors.push(String(error)));

  try {
    await login(page);
    await page.evaluate(() => { window.location.hash = '#@profile'; });
    const state = await waitForProfile(page);

    assert.deepEqual(errors, []);
    assert.equal(state.registered, true, 'expected ntx-profile to be registered');
    assert.equal(state.mounted, true, 'expected router to mount ntx-profile');
    assert.equal(state.hasShadowRoot, true, 'expected ntx-profile to render with shadow DOM');
  } finally {
    await page.close();
  }
});

test('topbar profile action opens the profile page', async () => {
  const page = await newPage();
  const errors = [];
  page.on('pageerror', (error) => errors.push(String(error)));

  try {
    await login(page);
    await openProfileFromTopbar(page);
    const state = await waitForProfile(page);

    assert.deepEqual(errors, []);
    assert.equal(new URL(page.url()).hash, '#@profile');
    assert.equal(state.hasCard, true, 'expected profile card to render from topbar navigation');
  } finally {
    await page.close();
  }
});

test('profile page shows authenticated user identity', async () => {
  const page = await newPage();
  const errors = [];
  page.on('pageerror', (error) => errors.push(String(error)));

  try {
    await login(page);
    await page.evaluate(() => { window.location.hash = '#@profile'; });
    const state = await waitForProfile(page);

    assert.deepEqual(errors, []);
    assert.match(state.text, /admin/i);
    assert.match(state.email, /admin@veille\.local/i);
    assert.match(state.role, /admin/i);
  } finally {
    await page.close();
  }
});
