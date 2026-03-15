/**
 * Method Response + Pull Bug — Integration Tests
 *
 * Verifies that after a method call (like, favorite, comment):
 *   1. The response does NOT trigger a redundant list-level GET
 *   2. Only a single pull GET is made (for the individual entity, not the list)
 *   3. The pull response updates only the specific entity via instance-level READ
 *   4. Class-level watcher notification is NOT triggered by pull()
 *
 * Bug: After clicking "like", the _response_ handler calls pull() which
 * GETs the individual entity. But the response routing or signal chain
 * triggers a full list re-render, causing layout shift and image reloads.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ProductSchema, makeProductData, makeProductListResponse, API_URL } from './helpers/mock-schemas.js';
import { flush } from './helpers/test-env.js';

let NTT, matrix, TX;

afterEach(async () => {
  await flush(10);
});

beforeEach(async () => {
  vi.resetModules();

  // Track all fetch calls with full URL capture
  global.fetch = vi.fn((url, opts) => {
    const urlStr = typeof url === 'string' ? url : url.toString();
    const method = opts?.method?.toUpperCase() || 'GET';

    // Schema fetch
    if (urlStr.endsWith('/Product')) {
      return Promise.resolve({
        ok: true, status: 200,
        json: () => Promise.resolve(ProductSchema),
      });
    }
    // Individual product fetch (pull response)
    if (/\/products\/\d+/.test(urlStr) && method === 'GET') {
      const id = parseInt(urlStr.match(/\/products\/(\d+)/)[1]);
      const data = makeProductData(id);
      // After a like, the product has an updated likes array
      data.likes = [`${API_URL}/likes/99`];
      return Promise.resolve({
        ok: true, status: 200,
        json: () => Promise.resolve(data),
      });
    }
    // Method call (like/favorite) response
    if (/\/products\/\d+\//.test(urlStr) && method === 'POST') {
      return Promise.resolve({
        ok: true, status: 200,
        json: () => Promise.resolve({ action: 'favorited' }),
      });
    }
    // List fetch
    if (urlStr.includes('/products')) {
      return Promise.resolve({
        ok: true, status: 200,
        json: () => Promise.resolve(makeProductListResponse(3)),
      });
    }
    // CSS and other
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


/**
 * Helper: count how many fetch calls target the products LIST endpoint
 * (excludes schema fetches and individual product fetches).
 */
function countProductListFetches() {
  return global.fetch.mock.calls.filter(([url, opts]) => {
    const urlStr = typeof url === 'string' ? url : url.toString();
    const method = opts?.method?.toUpperCase() || 'GET';
    // Match GET /products but NOT /products/123 (individual) or /Product (schema)
    return method === 'GET' && urlStr.includes('/products') && !/\/products\/\d+/.test(urlStr);
  }).length;
}

/**
 * Helper: count pull (individual entity) fetches.
 */
function countPullFetches() {
  return global.fetch.mock.calls.filter(([url, opts]) => {
    const urlStr = typeof url === 'string' ? url : url.toString();
    const method = opts?.method?.toUpperCase() || 'GET';
    return method === 'GET' && /\/products\/\d+/.test(urlStr);
  }).length;
}

/**
 * Helper: count method POST calls.
 */
function countMethodPosts() {
  return global.fetch.mock.calls.filter(([url, opts]) => {
    const urlStr = typeof url === 'string' ? url : url.toString();
    const method = opts?.method?.toUpperCase() || 'GET';
    return method === 'POST' && /\/products\/\d+\//.test(urlStr);
  }).length;
}


describe('_response_ after method call should not trigger list-level fetch', () => {

  it('pull() after _response_ should only fetch the individual entity, not the list', async () => {
    // Bootstrap: create DynamicClass with instances
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    expect(DC).toBeDefined();

    // Simulate initial data load (3 products)
    const listData = makeProductListResponse(3);
    DC.READ(listData);
    await flush(50);

    // Clear fetch mock to only count post-action fetches
    global.fetch.mockClear();

    // Get product instance
    const instance = DC.children.get('1');
    expect(instance).toBeDefined();

    // Simulate: the like method response arrives at the instance
    // This is what happens when httpCallback routes the reply back
    instance._response_({ action: 'favorited' });
    await flush(100);

    // After _response_ → pull(), we expect:
    //   - 1 GET for the individual product (pull)
    //   - 0 GETs for the product list
    const pullFetches = countPullFetches();
    const listFetches = countProductListFetches();

    expect(pullFetches).toBeLessThanOrEqual(1);  // At most 1 pull
    expect(listFetches).toBe(0);  // NO list fetches
  });

  it('pull() response should NOT trigger class-level watcher notification', async () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    DC.READ(makeProductListResponse(3));
    await flush(50);

    // Add a watcher (simulates ListElement subscribing)
    const watcherUpdates = [];
    DC._watchers.add('test-watcher');
    // Spy on DC.send to detect watcher notifications
    const originalSend = DC.send;
    DC.send = function(event) {
      const tx = event instanceof TX ? event : new TX(event);
      if (tx.name === 'UPDATE' && tx.target === 'test-watcher') {
        watcherUpdates.push(tx);
      }
      return originalSend.call(DC, event);
    };

    global.fetch.mockClear();

    // Trigger _response_ → pull() on a specific instance
    const instance = DC.children.get('1');
    instance._response_({ action: 'favorited' });
    await flush(100);

    // The watcher should NOT receive an UPDATE from pull()
    // (pull is an instance-level operation, not a list-level one)
    expect(watcherUpdates.length).toBe(0);

    DC.send = originalSend;
    DC._watchers.delete('test-watcher');
  });

  it('class-level DynamicClass.READ should NOT be called by pull() response', async () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    DC.READ(makeProductListResponse(3));
    await flush(50);

    // Spy on class-level READ
    const originalClassREAD = DC.READ;
    let classReadCalls = 0;
    DC.READ = function(...args) {
      classReadCalls++;
      return originalClassREAD.apply(DC, args);
    };

    global.fetch.mockClear();

    const instance = DC.children.get('1');
    instance._response_({ action: 'favorited' });
    await flush(100);

    // Class-level READ should NOT be invoked by pull() response
    expect(classReadCalls).toBe(0);

    DC.READ = originalClassREAD;
  });
});


describe('Entity signal behavior after _response_', () => {

  it('_response_ with entity data should signal the targeted instance only', async () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    DC.READ(makeProductListResponse(3));
    await flush(50);

    // Track signals on ALL instances
    const signals = { '1': 0, '2': 0, '3': 0 };
    for (const id of ['1', '2', '3']) {
      const inst = DC.children.get(id);
      if (inst?.signal) {
        inst.signal(() => { signals[id]++; }, true);
      }
    }

    global.fetch.mockClear();

    // _response_ with entity data (has id) should update + signal
    const entityData = makeProductData(1);
    entityData.name = 'Updated';
    entityData.likes = [`${API_URL}/likes/99`];
    DC.children.get('1')._response_(entityData);
    await flush(100);

    // Only product 1 should have signaled (direct update, no pull)
    expect(signals['1']).toBeGreaterThanOrEqual(1);
    expect(signals['2']).toBe(0);
    expect(signals['3']).toBe(0);
  });

  it('_response_ with action data should NOT signal (no data change)', async () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    DC.READ(makeProductListResponse(3));
    await flush(50);

    const instance = DC.children.get('1');
    let signalCount = 0;
    instance.signal(() => { signalCount++; }, true);

    // Action response (no id) → no update, no signal
    instance._response_({ action: 'favorited' });
    await flush(100);

    expect(signalCount).toBe(0);
  });
});


describe('Total network requests for like action', () => {

  it('like action should produce exactly 1 POST, zero GETs', async () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    DC.READ(makeProductListResponse(3));
    await flush(50);
    global.fetch.mockClear();

    // Simulate the full like action flow:
    // ntx-method calls instance.call('like', {}, {inbox: '_response_'})
    const instance = DC.children.get('1');
    instance.call('like', {}, { inbox: '_response_' });
    await flush(200);

    // Count requests
    const posts = countMethodPosts();
    const pulls = countPullFetches();
    const listGets = countProductListFetches();

    // Exactly 1 POST (the like action)
    expect(posts).toBe(1);
    // ZERO pull GETs — _response_ no longer calls pull()
    expect(pulls).toBe(0);
    // ZERO list-level GETs
    expect(listGets).toBe(0);
  });
});
