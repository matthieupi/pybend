import test from 'node:test';
import assert from 'node:assert/strict';
import { lstat, mkdir, rm, symlink } from 'node:fs/promises';
import { JSDOM } from 'jsdom';

const CORE_STATIC = '/workspace/packages/n3tx-core/src/n3tx_core/static';
const UI_STATIC = '/workspace/packages/n3tx-ui/src/n3tx_ui/static';
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

function grantSchema() {
  return {
    __name__: 'Grant',
    title: 'Grant',
    access: {
      update: { rule: 'authenticated' },
      delete: { rule: 'owner' },
    },
    properties: {
      id: { type: 'integer', ui: { display: false } },
      title: { type: 'string', title: 'Title' },
      agency: { type: 'string', title: 'Agency' },
      deadline: { type: 'string', title: 'Deadline', ui: { widget: 'date' } },
      amount_min: { type: 'number', title: 'Amount Min', ui: { widget: 'currency' } },
      amount_max: { type: 'number', title: 'Amount Max', ui: { widget: 'currency' } },
      url: { type: 'string', title: 'Url', ui: { widget: 'url' } },
      description: { type: 'string', title: 'Description', ui: { widget: 'textarea' } },
      status: { type: 'string', title: 'Status', enum: ['discovered', 'reviewed'] },
      user_owner: { type: '$ref', $ref: '#/$defs/User', ui: { protected: true } },
    },
    methods: {},
    $defs: {},
  };
}

function generatedGrantSchema() {
  return {
    __name__: 'Grant',
    title: 'Grant',
    access: {
      update: { op: 'or', rules: [{ rule: 'authenticated' }, { rule: 'role', roles: ['admin'] }] },
      delete: { op: 'or', rules: [{ rule: 'owner' }, { rule: 'role', roles: ['admin'] }] },
    },
    properties: {
      id: { type: 'integer', ui: { display: false } },
      image: { type: 'string', ui: { display: false } },
      title: { type: 'string', title: 'Title', minLength: 1, maxLength: 500 },
      agency: { type: 'string', title: 'Agency', minLength: 1, maxLength: 200 },
      deadline: {
        title: 'Deadline',
        anyOf: [{ type: 'string', format: 'date' }, { type: 'null' }],
        ui: { widget: 'date' },
      },
      amount_min: {
        title: 'Amount Min',
        anyOf: [{ type: 'number' }, { type: 'null' }],
        ui: { widget: 'currency' },
      },
      amount_max: {
        title: 'Amount Max',
        anyOf: [{ type: 'number' }, { type: 'null' }],
        ui: { widget: 'currency' },
      },
      url: { type: 'string', title: 'Url', minLength: 1, ui: { widget: 'url' } },
      description: { type: 'string', title: 'Description', ui: { widget: 'textarea' } },
      status: { type: 'string', title: 'Status', enum: ['discovered', 'reviewed', 'applied', 'expired'] },
      user_owner: { type: '$ref', $ref: '#/$defs/User', ui: { protected: true } },
    },
    methods: {},
    $defs: {},
    required: ['title', 'agency', 'url'],
  };
}

function grantValue() {
  return {
    id: 1,
    title: 'Existing Grant',
    agency: 'NSF',
    deadline: '2026-01-31',
    amount_min: 1000,
    amount_max: 5000,
    url: 'https://example.com/grant',
    description: 'Important grant description',
    status: 'discovered',
    user_owner: 1,
  };
}

function grantListSchema() {
  return {
    __name__: 'Grant',
    __tablename__: 'grants',
    title: 'Grant',
    access: { update: { rule: 'authenticated' } },
    properties: {
      id: { type: 'integer', ui: { display: false } },
      title: { type: 'string', title: 'Title' },
      tags: { type: 'array', title: 'Tags', items: { type: 'string' } },
      reviewers: { type: 'array', title: 'Reviewers', items: { $ref: '#/$defs/User' } },
    },
    required: ['title'],
    methods: {},
    $defs: {
      User: {
        __name__: 'User',
        __tablename__: 'users',
        ui: { renderer: { item: 'ntx-test-ref-item' } },
        properties: {
          id: { type: 'integer' },
          name: { type: 'string', title: 'Name' },
        },
        methods: {},
      },
    },
  };
}

function grantListValue() {
  return {
    id: 3,
    title: 'Grant With Lists',
    tags: ['ai', 'robotics'],
    reviewers: ['http://localhost:5000/users/1', 'http://localhost:5000/users/2'],
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
    if (!customElements.get('ntx-test-ref-item')) {
      customElements.define('ntx-test-ref-item', class extends HTMLElement {});
    }
    boot = { dom, permissions, Formidable };
    return boot;
  } finally {
    await cleanupTestImports();
  }
}

async function setup() {
  const { dom, permissions, Formidable } = await initEnvironment();
  document.body.innerHTML = '';
  Formidable.clearCache();
  localStorage.setItem('jwtToken', 'test-token');
  await permissions.init();

  const item = document.createElement('ntx-item');
  item.schema = grantSchema();
  item.ref = 'Grant/1';
  item.value = grantValue();
  document.body.appendChild(item);
  item.render();

  return { item, permissions, dom };
}

async function setupGeneratedGrant() {
  const { dom, permissions, Formidable } = await initEnvironment();
  document.body.innerHTML = '';
  Formidable.clearCache();
  localStorage.setItem('jwtToken', 'test-token');
  await permissions.init();

  const item = document.createElement('ntx-item');
  item.schema = generatedGrantSchema();
  item.ref = 'Grant/1';
  item.value = grantValue();
  document.body.appendChild(item);
  item.render();

  return { item, permissions, dom };
}

async function setupGrantWithLists() {
  const { dom, permissions, Formidable } = await initEnvironment();
  document.body.innerHTML = '';
  Formidable.clearCache();
  localStorage.setItem('jwtToken', 'test-token');
  await permissions.init();

  const item = document.createElement('ntx-item');
  item.schema = grantListSchema();
  item.ref = 'Grant/3';
  item.value = grantListValue();
  document.body.appendChild(item);
  item.render();

  return { item, permissions, dom };
}

async function setupRow() {
  const { permissions, dom } = await initEnvironment();
  document.body.innerHTML = '';
  localStorage.setItem('jwtToken', 'test-token');
  await permissions.init();

  await ensureTestImports();
  try {
    await import(`${UI_STATIC}/components/ntx-row.js`);
  } finally {
    await cleanupTestImports();
  }

  const row = document.createElement('ntx-row');
  row.schema = grantSchema();
  row.ref = 'Grant/1';
  row.value = grantValue();
  document.body.appendChild(row);
  row.render();

  return { row, permissions, dom };
}

test('grant edit button enters edit mode', async () => {
  const { item } = await setup();
  const editBtn = item.shadowRoot.querySelector('.edit-btn');

  assert.ok(editBtn, 'expected edit button to render for authenticated grant viewer');
  editBtn.click();

  assert.equal(item.mode, 'edit');
  assert.ok(item.shadowRoot.querySelector('input[data-key="title"]'));
  assert.ok(item.shadowRoot.querySelector('.cancel-btn'));
});

test('grant edit mode renders widget-backed inputs', async () => {
  const { item } = await setup();

  item.shadowRoot.querySelector('.edit-btn').click();

  assert.ok(item.shadowRoot.querySelector('input[data-key="url"]'));
  assert.ok(item.shadowRoot.querySelector('input[data-key="amount_min"]'));
  assert.ok(item.shadowRoot.querySelector('input[data-key="amount_max"]'));
  assert.ok(item.shadowRoot.querySelector('textarea[data-key="description"]'));
});

test('grant save button emits update after editing title', async () => {
  const { item } = await setup();
  let sentTx = null;
  item.send = (tx) => { sentTx = tx; };

  item.shadowRoot.querySelector('.edit-btn').click();
  const titleInput = item.shadowRoot.querySelector('input[data-key="title"]');
  titleInput.value = 'Edited Grant Title';
  titleInput.dispatchEvent(new Event('input', { bubbles: true }));

  item.shadowRoot.querySelector('.edit-btn').click();

  assert.equal(item.mode, 'display');
  assert.equal(item.value.title, 'Edited Grant Title');
  assert.equal(sentTx?.name, 'UPDATE');
  assert.equal(sentTx?.target, 'Grant/1');
  assert.equal(sentTx?.data?.title, 'Edited Grant Title');
});

test('grant detail edit click does not bubble into card selection', async () => {
  const { item } = await setup();
  const sent = [];
  item.send = (tx) => sent.push(tx);
  item.setAttribute('select-target', 'main');
  item.render();

  item.shadowRoot.querySelector('.edit-btn').click();

  assert.equal(item.mode, 'edit');
  assert.equal(sent.some((tx) => tx?.name === 'SELECT'), false);
});

test('grant table row edit button enters inline edit mode', async () => {
  const { row } = await setupRow();

  row.shadowRoot.querySelector('.edit-btn').click();

  assert.equal(row.mode, 'edit');
  assert.ok(row.shadowRoot.querySelector('input[data-key="title"]'));
  assert.ok(row.shadowRoot.querySelector('input[data-key="url"]'));
});

test('grant table row save emits update after editing title', async () => {
  const { row } = await setupRow();
  let sentTx = null;
  row.send = (tx) => { sentTx = tx; };

  row.shadowRoot.querySelector('.edit-btn').click();
  const titleInput = row.shadowRoot.querySelector('input[data-key="title"]');
  titleInput.value = 'Edited Row Grant';
  titleInput.dispatchEvent(new Event('input', { bubbles: true }));
  row.shadowRoot.querySelector('.edit-btn').click();

  assert.equal(row.mode, 'display');
  assert.equal(row.value.title, 'Edited Row Grant');
  assert.equal(sentTx?.name, 'UPDATE');
  assert.equal(sentTx?.data?.title, 'Edited Row Grant');
});

test('generated grant schema still renders editable form fields', async () => {
  const { item } = await setupGeneratedGrant();

  item.shadowRoot.querySelector('.edit-btn').click();

  assert.equal(item.mode, 'edit');
  assert.ok(item.shadowRoot.querySelector('input[data-key="title"]'));
  assert.ok(item.shadowRoot.querySelector('input[data-key="agency"]'));
  assert.ok(item.shadowRoot.querySelector('input[data-key="deadline"]'));
  assert.ok(item.shadowRoot.querySelector('input[data-key="amount_min"]'));
  assert.ok(item.shadowRoot.querySelector('input[data-key="amount_max"]'));
  assert.ok(item.shadowRoot.querySelector('input[data-key="url"]'));
  assert.ok(item.shadowRoot.querySelector('textarea[data-key="description"]'));
  assert.ok(item.shadowRoot.querySelector('select[data-key="status"]'));
});

test('scalar array fields render editable rows and add items', async () => {
  const { item } = await setupGrantWithLists();

  item.shadowRoot.querySelector('.edit-btn').click();
  const listField = item.shadowRoot.querySelector('ntx-list-field[field="tags"]');

  assert.equal(item.mode, 'edit');
  assert.ok(listField?.shadowRoot?.querySelector('[data-index="0"]'));
  listField.shadowRoot.querySelector('[data-array-action="add-scalar"]').click();

  assert.equal(item.value.tags.length, 3);
  assert.equal(item.value.tags[2], '');
});

test('scalar array fields support removing existing items', async () => {
  const { item } = await setupGrantWithLists();

  item.shadowRoot.querySelector('.edit-btn').click();
  const listField = item.shadowRoot.querySelector('ntx-list-field[field="tags"]');
  listField.shadowRoot.querySelector('[data-array-action="remove-scalar"][data-index="0"]').click();

  assert.deepEqual(item.value.tags, ['robotics']);
  assert.ok(listField.shadowRoot.querySelector('[data-index="0"]'));
});

test('ref array fields show remove controls and stage added refs', async () => {
  const { item } = await setupGrantWithLists();

  item.shadowRoot.querySelector('.edit-btn').click();
  const listField = item.shadowRoot.querySelector('ntx-list-field[field="reviewers"]');

  const picker = listField.shadowRoot.querySelector('ntx-ref-picker[field="reviewers"]');
  assert.ok(picker);
  assert.equal(listField.shadowRoot.querySelectorAll('[data-array-action="remove-ref"]').length, 2);

  picker.dispatchEvent(new CustomEvent('ref-added', {
    bubbles: true,
    composed: true,
    detail: { field: 'reviewers', ref: 'http://localhost:5000/users/3' },
  }));

  assert.deepEqual(item.value.reviewers, [
    'http://localhost:5000/users/1',
    'http://localhost:5000/users/2',
    'http://localhost:5000/users/3',
  ]);
});

test('ref array fields support removing linked refs in edit mode', async () => {
  const { item } = await setupGrantWithLists();

  item.shadowRoot.querySelector('.edit-btn').click();
  const listField = item.shadowRoot.querySelector('ntx-list-field[field="reviewers"]');
  listField.shadowRoot.querySelector('[data-array-action="remove-ref"][data-ref="http://localhost:5000/users/1"]').click();

  assert.deepEqual(item.value.reviewers, ['http://localhost:5000/users/2']);
});
