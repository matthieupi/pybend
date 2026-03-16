/**
 * Method Response Full Flow — traces actual network requests
 *
 * Unlike the unit-level tests, this test exercises the FULL actor routing
 * chain: instance.call() → Actor routing → NetworkAdapter → HTTP → reply routing.
 *
 * Bug: After clicking "like", the user sees a redundant list GET and visual
 * disruption (layout shifts, image reloads). This test captures all fetch
 * calls made during the like flow to identify the source.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ProductSchema, makeProductData, makeProductListResponse, API_URL } from './helpers/mock-schemas.js';
import { flush } from './helpers/test-env.js';

let NTT, matrix, TX;

/** Detailed log of all fetch calls */
let fetchLog = [];

afterEach(async () => {
  await flush(10);
});

beforeEach(async () => {
  vi.resetModules();
  fetchLog = [];

  global.fetch = vi.fn((url, opts) => {
    const urlStr = typeof url === 'string' ? url : url.toString();
    const method = opts?.method?.toUpperCase() || 'GET';
    fetchLog.push({ url: urlStr, method, time: Date.now() });

    // Schema fetch
    if (urlStr.endsWith('/Product')) {
      return Promise.resolve({
        ok: true, status: 200,
        json: () => Promise.resolve(ProductSchema),
      });
    }
    // Individual product fetch (pull response) — includes depth param
    if (/\/products\/\d+/.test(urlStr) && method === 'GET') {
      const id = parseInt(urlStr.match(/\/products\/(\d+)/)[1]);
      const data = makeProductData(id);
      data.likes = [`${API_URL}/likes/99`];
      return Promise.resolve({
        ok: true, status: 200,
        json: () => Promise.resolve(data),
      });
    }
    // Method call (like/favorite) POST
    if (/\/products\/\d+\/like/.test(urlStr) && method === 'POST') {
      return Promise.resolve({
        ok: true, status: 200,
        json: () => Promise.resolve({ action: 'liked' }),
      });
    }
    // List fetch
    if (urlStr.includes('/products') && method === 'GET') {
      return Promise.resolve({
        ok: true, status: 200,
        json: () => Promise.resolve(makeProductListResponse(3)),
      });
    }
    // CSS
    if (urlStr.endsWith('.css')) {
      return Promise.resolve({
        ok: true, status: 200,
        text: () => Promise.resolve(':host { display: block; }'),
      });
    }
    return Promise.resolve({
      ok: true, status: 200,
      json: () => Promise.resolve({}),
      text: () => Promise.resolve(''),
    });
  });

  const nttMod = await import('../../core/NTT.js');
  const matrixMod = await import('../../core/Matrix.js');
  const txMod = await import('../../core/TX.js');

  NTT = nttMod.NTT;
  matrix = matrixMod.matrix;
  TX = txMod.default;
});

function getListGets() {
  return fetchLog.filter(f =>
    f.method === 'GET' &&
    f.url.includes('/products') &&
    !/\/products\/\d+/.test(f.url) &&
    !f.url.endsWith('/Product')
  );
}

function getPullGets() {
  return fetchLog.filter(f =>
    f.method === 'GET' &&
    /\/products\/\d+/.test(f.url)
  );
}

function getMethodPosts() {
  return fetchLog.filter(f =>
    f.method === 'POST' &&
    /\/products\/\d+\//.test(f.url)
  );
}


describe('Full like flow — network request audit', () => {

  it('should audit all network requests during like action via instance.call()', async () => {
    // Phase 1: Bootstrap
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    DC.READ(makeProductListResponse(3));
    await flush(50);

    // Clear fetch log — only track post-like requests
    fetchLog = [];
    global.fetch.mockClear();

    // Phase 2: Simulate like via the Actor system (full routing)
    const instance = DC.children.get('1');
    expect(instance).toBeDefined();
    expect(instance.href).toContain('/products/1');

    // This is what ntx-method.callMethod() does:
    instance.call('like', {}, { inbox: '_response_' });
    await flush(300);

    // Phase 3: Audit
    console.log('=== Fetch Log ===');
    fetchLog.forEach((f, i) => console.log(`  ${i}: ${f.method} ${f.url}`));

    const listGets = getListGets();
    const pullGets = getPullGets();
    const posts = getMethodPosts();

    console.log(`Posts: ${posts.length}, Pull GETs: ${pullGets.length}, List GETs: ${listGets.length}`);

    // Expectations:
    expect(posts.length).toBe(1);              // 1 POST for the like action
    expect(pullGets.length).toBeLessThanOrEqual(1);  // At most 1 pull GET
    expect(listGets.length).toBe(0);           // ZERO list-level GETs
  });

  it('should audit requests when like is called via DynamicClass.call (class-level)', async () => {
    // This tests the case where the method is called on the class level
    // (e.g., when ntx-method uses proto as the caller)
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    DC.READ(makeProductListResponse(3));
    await flush(50);

    fetchLog = [];
    global.fetch.mockClear();

    // Some ntx-method components use proto.call() instead of instance.call()
    // if uuid is not set. In this case, the method goes to the class href.
    // This should NOT trigger a list GET either.
    DC.call('like', {}, { inbox: '_response_' });
    await flush(300);

    console.log('=== Fetch Log (class-level call) ===');
    fetchLog.forEach((f, i) => console.log(`  ${i}: ${f.method} ${f.url}`));

    const listGets = getListGets();
    // Class-level call response routes to DynamicClass._response_ (if exists)
    // which might behave differently. At minimum, no redundant list GET.
    expect(listGets.length).toBe(0);
  });

  it('watcher notification count after like should be zero', async () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    DC.READ(makeProductListResponse(3));
    await flush(50);

    // Register a watcher and count UPDATE notifications
    let updateCount = 0;
    DC._watchers.add('test-list-watcher');
    const originalSend = DC.send;
    DC.send = function(event) {
      const tx = event instanceof TX ? event : new TX(event);
      if (tx.name === 'UPDATE' && tx.target === 'test-list-watcher') {
        updateCount++;
      }
      return originalSend.call(DC, event);
    };

    fetchLog = [];
    global.fetch.mockClear();

    // Like product 1 via full actor routing
    const instance = DC.children.get('1');
    instance.call('like', {}, { inbox: '_response_' });
    await flush(300);

    console.log(`Watcher UPDATE notifications: ${updateCount}`);

    // The list watcher should NOT receive any UPDATE notifications
    // from the like action. Only entity-level signals should fire.
    expect(updateCount).toBe(0);

    DC.send = originalSend;
    DC._watchers.delete('test-list-watcher');
  });
});
