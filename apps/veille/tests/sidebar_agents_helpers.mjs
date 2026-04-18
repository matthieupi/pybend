import assert from 'node:assert/strict';
import { lstat, mkdir, readFile, rm, symlink } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
import { JSDOM } from 'jsdom';

const CORE_STATIC = '/workspace/packages/n3tx-core/src/n3tx_core/static';
const UI_STATIC = '/workspace/packages/n3tx-ui/src/n3tx_ui/static';
const VEILLE_INDEX = '/workspace/apps/veille/static/index.html';
const TEMP_LINKS = [];

let boot = null;

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
  await Promise.all(
    TEMP_LINKS.splice(0).reverse().map((linkPath) => rm(linkPath, { force: true, recursive: true })),
  );
}

export async function initSidebarEnvironment() {
  if (boot) return boot;

  const dom = new JSDOM('<!doctype html><html><body></body></html>', {
    url: 'http://localhost/',
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
  globalThis.DOMParser = window.DOMParser;
  globalThis.localStorage = window.localStorage;
  globalThis.AbortController = window.AbortController;
  globalThis.ResizeObserver = class { observe() {} disconnect() {} unobserve() {} };
  globalThis.CSSStyleSheet = class { replaceSync() {} };
  globalThis.requestAnimationFrame = (cb) => { cb(); return 0; };
  Object.defineProperty(globalThis, 'navigator', { value: window.navigator, configurable: true });

  globalThis.fetch = async () => ({ ok: true, text: async () => '', json: async () => ({}) });

  await ensureTestImports();
  try {
    await import(pathToFileURL(`${UI_STATIC}/components/ntx-sidebar.js`).href);
    const { NTT } = await import(pathToFileURL(`${CORE_STATIC}/core/NTT.js`).href);
    NTT.attach = () => () => {};
    boot = { dom, NTT };
    return boot;
  } finally {
    await cleanupTestImports();
  }
}

export async function mountVeilleSidebar() {
  await initSidebarEnvironment();
  document.body.innerHTML = '';

  const html = await readFile(VEILLE_INDEX, 'utf8');
  const wrapper = document.createElement('div');
  wrapper.innerHTML = html;

  const sourceSidebar = wrapper.querySelector('ntx-sidebar');
  assert.ok(sourceSidebar, 'expected Veille index.html to contain an ntx-sidebar');

  const sidebar = sourceSidebar.cloneNode(true);
  document.body.appendChild(sidebar);
  return { sidebar, html };
}

export function renderedSidebarLabels(sidebar) {
  return [...sidebar.shadowRoot.querySelectorAll('.model-name')].map((node) => node.textContent.trim());
}

export function clickSidebarHeader(sidebar, modelName) {
  const header = sidebar.shadowRoot.querySelector(`.model-section[data-model="${modelName}"] .model-header`);
  assert.ok(header, `expected sidebar header for ${modelName}`);
  header.click();
}
