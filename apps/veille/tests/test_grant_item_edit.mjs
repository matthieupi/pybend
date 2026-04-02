import test from 'node:test';
import assert from 'node:assert/strict';
import { lstat, mkdir, readFile, rm, symlink } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
import { JSDOM } from 'jsdom';

const CORE_STATIC = '/workspace/packages/n3tx-core/src/n3tx_core/static';
const UI_STATIC = '/workspace/packages/n3tx-ui/src/n3tx_ui/static';
const CUSTOM_ITEM = '/workspace/apps/veille/static/components/ntx-grant-item.js';
const TEMP_LINKS = [];

async function ensureTestImports() {
  const links = [
    [`${UI_STATIC}/config.js`, `${CORE_STATIC}/config.js`],
    [`${UI_STATIC}/core`, `${CORE_STATIC}/core`],
    [`${UI_STATIC}/utils/Assert.js`, `${CORE_STATIC}/utils/Assert.js`],
    [`${UI_STATIC}/utils/DateFormat.js`, `${CORE_STATIC}/utils/DateFormat.js`],
    [`${UI_STATIC}/utils/Logging.js`, `${CORE_STATIC}/utils/Logging.js`],
    [`${UI_STATIC}/utils/Permissions.js`, `${CORE_STATIC}/utils/Permissions.js`],
    [`${UI_STATIC}/utils/registrar.js`, `${CORE_STATIC}/utils/registrar.js`],
    [`${UI_STATIC}/utils/Snippets.js`, `${CORE_STATIC}/utils/Snippets.js`],
    [`${UI_STATIC}/utils/str_utils.js`, `${CORE_STATIC}/utils/str_utils.js`],
  ];

  for (const [linkPath, targetPath] of links) {
    try {
      await lstat(linkPath);
      continue;
    } catch {}
    await mkdir(linkPath.slice(0, linkPath.lastIndexOf('/')), { recursive: true });
    await symlink(targetPath, linkPath);
    TEMP_LINKS.push(linkPath);
  }
}

async function cleanupTestImports() {
  await Promise.all(TEMP_LINKS.splice(0).reverse().map((linkPath) => rm(linkPath, { force: true, recursive: true })));
}

function veilleGrantSchema() {
  return {
    __name__: 'Grant',
    title: 'Grant',
    access: { update: { rule: 'authenticated' }, delete: { rule: 'role', roles: ['admin'] } },
    properties: {
      id: { type: 'integer', ui: { display: false } },
      title: { type: 'string', title: 'Title' },
      funder: { type: 'string', title: 'Funder' },
      status: { type: 'string', title: 'Status' },
      url: { type: 'string', title: 'Url' },
      source_url: { type: 'string', title: 'Source Url' },
      amount_min: { anyOf: [{ type: 'number' }, { type: 'null' }], title: 'Amount Min' },
      amount_max: { anyOf: [{ type: 'number' }, { type: 'null' }], title: 'Amount Max' },
      deadline: { anyOf: [{ type: 'string' }, { type: 'null' }], title: 'Deadline' },
      description: { type: 'string', title: 'Description', ui: { widget: 'textarea' } },
      eligibility_criteria: { type: 'array', title: 'Eligibility Criteria' },
      required_documents: { type: 'array', title: 'Required Documents' },
      application_process: { type: 'string', title: 'Application Process', ui: { widget: 'textarea' } },
      admissibility_score: { anyOf: [{ type: 'number' }, { type: 'null' }], title: 'Admissibility Score' },
      admissibility_reasoning: { type: 'string', title: 'Admissibility Reasoning' },
    },
    required: ['title'],
    methods: {},
    $defs: {},
  };
}

function veilleGrantValue() {
  return {
    id: 1,
    title: 'Quebec Innovation Grant',
    funder: 'Ministry of Innovation',
    status: 'new',
    url: 'https://example.com/grant',
    source_url: 'https://example.com/source',
    amount_min: 10000,
    amount_max: 25000,
    deadline: '2026-04-01',
    description: 'Support for innovation projects.',
    eligibility_criteria: ['SMEs', 'Quebec-based'],
    required_documents: ['Budget', 'Project plan'],
    application_process: 'Submit through the portal.',
    admissibility_score: 0.82,
    admissibility_reasoning: 'Strong match.',
  };
}

function veilleRunSchema() {
  return {
    __name__: 'Run',
    title: 'Run',
    access: { update: { rule: 'authenticated' } },
    properties: {
      id: { type: 'integer', ui: { display: false } },
      type: { type: 'string', title: 'Type' },
      status: { type: 'string', title: 'Status' },
      adhoc_url: { type: 'string', title: 'URL' },
      error: { type: 'string', title: 'Error', ui: { widget: 'textarea' } },
      started_at: { type: 'string', title: 'Started At' },
      completed_at: { type: 'string', title: 'Completed At' },
      grants_found: { type: 'integer', title: 'Grants Found' },
      sources_covered: { type: 'integer', title: 'Sources Covered' },
    },
    required: ['type'],
    methods: {},
    $defs: {},
  };
}

function veilleRunValue() {
  return {
    id: 7,
    type: 'full',
    status: 'complete',
    adhoc_url: 'https://example.com/run',
    error: '',
    started_at: '2026-04-01T10:00:00Z',
    completed_at: '2026-04-01T10:10:00Z',
    grants_found: 12,
    sources_covered: 5,
  };
}

let boot = null;

async function initEnvironment() {
  if (boot) return boot;

  const dom = new JSDOM('<!doctype html><html><body></body></html>', {
    url: 'http://localhost',
    pretendToBeVisual: true,
  });
  const { window } = dom;

  globalThis.window = window;
  globalThis.document = window.document;
  globalThis.customElements = window.customElements;
  globalThis.HTMLElement = window.HTMLElement;
  globalThis.Node = window.Node;
  globalThis.Event = window.Event;
  globalThis.CustomEvent = window.CustomEvent;
  globalThis.MutationObserver = window.MutationObserver;
  globalThis.localStorage = window.localStorage;
  globalThis.AbortController = window.AbortController;
  globalThis.ResizeObserver = class { observe() {} disconnect() {} unobserve() {} };
  globalThis.CSSStyleSheet = class { replaceSync() {} };
  globalThis.requestAnimationFrame = (cb) => { cb(); return 0; };
  Object.defineProperty(globalThis, 'navigator', { value: window.navigator, configurable: true });

  globalThis.fetch = async (url) => {
    if (String(url).endsWith('/auth/me')) {
      return { ok: true, json: async () => ({ user_id: 1, role: 'user', email: 'alice@example.com' }) };
    }
    return { ok: true, text: async () => '' };
  };

  await ensureTestImports();
  try {
    await import(`${UI_STATIC}/components/ntx-item.js`);
    const { Formidable } = await import(`${UI_STATIC}/generators/form.js`);
    const { permissions } = await import(`${UI_STATIC}/utils/Permissions.js`);

    const itemModuleUrl = pathToFileURL(`${UI_STATIC}/components/ntx-item.js`).href;
    const source = await readFile(CUSTOM_ITEM, 'utf8');
    const patched = source.replace("'./ntx-item.js'", `'${itemModuleUrl}'`);
    await import(`data:text/javascript;charset=utf-8,${encodeURIComponent(patched)}`);

    const runItemSource = await readFile('/workspace/apps/veille/static/components/ntx-run-item.js', 'utf8');
    const patchedRunItem = runItemSource.replace("'./ntx-item.js'", `'${itemModuleUrl}'`);
    await import(`data:text/javascript;charset=utf-8,${encodeURIComponent(patchedRunItem)}`);

    boot = { dom, permissions, Formidable };
    return boot;
  } finally {
    await cleanupTestImports();
  }
}

async function setupCustomGrantItem() {
  const { dom, permissions, Formidable } = await initEnvironment();
  document.body.innerHTML = '';
  Formidable.clearCache();
  localStorage.setItem('jwtToken', 'test-token');
  await permissions.init();

  const item = document.createElement('ntx-grant-item');
  item.schema = veilleGrantSchema();
  item.ref = 'Grant/1';
  item.value = veilleGrantValue();
  document.body.appendChild(item);
  item.render();
  return { item, dom, permissions };
}

async function setupCustomRunItem() {
  const { dom, permissions, Formidable } = await initEnvironment();
  document.body.innerHTML = '';
  Formidable.clearCache();
  localStorage.setItem('jwtToken', 'test-token');
  await permissions.init();

  const item = document.createElement('ntx-run-item');
  item.schema = veilleRunSchema();
  item.ref = 'Run/7';
  item.value = veilleRunValue();
  document.body.appendChild(item);
  item.render();
  return { item, dom, permissions };
}

test('custom veille grant item enters a real edit form', async () => {
  const { item } = await setupCustomGrantItem();

  item.shadowRoot.querySelector('.edit-btn').click();

  assert.equal(item.mode, 'edit');
  assert.ok(item.shadowRoot.querySelector('input[data-key="title"]'));
  assert.ok(item.shadowRoot.querySelector('textarea[data-key="description"]'));
});

test('custom veille grant item hides display-only grant chrome in edit mode', async () => {
  const { item } = await setupCustomGrantItem();

  item.shadowRoot.querySelector('.edit-btn').click();

  assert.equal(item.mode, 'edit');
  assert.equal(!!item.shadowRoot.querySelector('.grant-info-grid'), false);
  assert.equal(!!item.shadowRoot.querySelector('.grant-header'), false);
});

test('custom veille grant item save sends edited values', async () => {
  const { item } = await setupCustomGrantItem();
  let sentTx = null;
  item.send = (tx) => { sentTx = tx; };

  item.shadowRoot.querySelector('.edit-btn').click();
  const titleInput = item.shadowRoot.querySelector('input[data-key="title"]');
  titleInput.value = 'Edited Veille Grant';
  titleInput.dispatchEvent(new Event('input', { bubbles: true }));
  item.shadowRoot.querySelector('.edit-btn').click();

  assert.equal(item.mode, 'display');
  assert.equal(sentTx?.name, 'UPDATE');
  assert.equal(sentTx?.data?.title, 'Edited Veille Grant');
});

test('custom veille run item also falls back to the base edit form', async () => {
  const { item } = await setupCustomRunItem();

  item.mode = 'edit';
  item.render();

  assert.equal(item.mode, 'edit');
  assert.ok(item.shadowRoot.querySelector('input[data-key="type"]'));
  assert.ok(item.shadowRoot.querySelector('input[data-key="adhoc_url"]'));
  assert.equal(!!item.shadowRoot.querySelector('.run-info-grid'), false);
});
