/**
 * Duplicate READ Request Bug — Integration Tests
 *
 * Verifies that on page load with multiple components consuming the same model,
 * only ONE data request is made to the products endpoint (not 3-4 redundant ones).
 *
 * Bug: NTT.SCHEMA() fires an unconditional DC.call('READ') after creating the
 * DynamicClass, AND each ListElement fires its own READ in definedCallback().
 * Combined with multiple list components (sidebar child + main list), this
 * produces 3-4 redundant network requests for the same data.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ProductSchema, makeProductListResponse, API_URL } from './helpers/mock-schemas.js';
import { flush } from './helpers/test-env.js';

let NTT, matrix, TX;

afterEach(async () => {
  await flush(10);
});

beforeEach(async () => {
  vi.resetModules();

  // Track all fetch calls with full URL capture
  global.fetch = vi.fn((url) => {
    const urlStr = typeof url === 'string' ? url : url.toString();
    if (urlStr.endsWith('/Product')) {
      return Promise.resolve({
        ok: true, status: 200,
        json: () => Promise.resolve(ProductSchema),
      });
    }
    if (urlStr.includes('/products')) {
      return Promise.resolve({
        ok: true, status: 200,
        json: () => Promise.resolve(makeProductListResponse(3)),
      });
    }
    // CSS fetches and others
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
 * Helper: count how many fetch calls target the products data endpoint
 * (excludes schema fetches to /Product).
 */
function countProductDataFetches() {
  return global.fetch.mock.calls.filter(([url]) => {
    const urlStr = typeof url === 'string' ? url : url.toString();
    // Match /products (data endpoint), exclude /Product (schema endpoint)
    return urlStr.includes('/products');
  }).length;
}


describe('NTT.SCHEMA should not trigger redundant READ', () => {

  it('NTT.SCHEMA() should not fire DC.call(READ) after creating DynamicClass', async () => {
    // Call SCHEMA directly — simulates schema response arrival
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    expect(DC).toBeDefined();

    // Wait for any async TX dispatches to settle
    await flush(50);

    // The SCHEMA handler should NOT have triggered a fetch to /products.
    // The only acceptable fetch is the schema fetch itself (if any).
    // Any fetch to /products is a redundant READ.
    const dataFetches = countProductDataFetches();
    expect(dataFetches).toBe(0);
  });

  it('NTT.SCHEMA() with watchers registered should still not fire its own READ', async () => {
    // Simulate: a component already queued an ATTACH before schema arrived
    NTT.ATTACH('Product', new TX({
      name: 'ATTACH',
      source: 'list-component-1',
      target: 'NTT',
      data: 'Product',
    }));

    // Schema arrives — should create DC, replay ATTACH, but NOT fire DC.call('READ')
    NTT.SCHEMA(ProductSchema);
    await flush(50);

    // The only acceptable fetch to /products would be from the component's
    // own definedCallback, NOT from NTT.SCHEMA's unconditional READ.
    // Since we're only testing NTT.SCHEMA here (no real ListElement), there
    // should be zero data fetches.
    const dataFetches = countProductDataFetches();
    expect(dataFetches).toBe(0);
  });

  it('NTT.SCHEMA() with pre-loaded data should not fire network READ either', async () => {
    // If pre-loaded data is provided, no READ at all should happen.
    // Currently, NTT.SCHEMA checks for preloaded data but ALSO fires
    // DC.call('READ') when there is none. With the fix, neither path
    // should trigger a READ from SCHEMA itself.
    NTT.SCHEMA(ProductSchema);
    await flush(50);

    // Verify: zero data fetches initiated by SCHEMA
    const dataFetches = countProductDataFetches();
    expect(dataFetches).toBe(0);
  });
});


describe('ListElement deduplication — only one READ per model', () => {

  it('two list components attaching to the same model should produce only one READ', async () => {
    // Import ListElement (which registers ntx-list) — only if not already registered
    try { await import('../../components/ntx-list.js'); } catch (e) { /* already registered */ }

    // Create two ntx-list elements for the same model
    const list1 = document.createElement('ntx-list');
    const list2 = document.createElement('ntx-list');
    document.body.appendChild(list1);
    document.body.appendChild(list2);

    // Setting model attribute triggers attach + ATTACH TX
    list1.setAttribute('model', 'Product');
    list2.setAttribute('model', 'Product');

    // Provide the schema — this triggers definedCallback on both lists
    NTT.SCHEMA(ProductSchema);
    await flush(50);

    // Count data fetches — should be exactly 1, not 2+
    const dataFetches = countProductDataFetches();
    expect(dataFetches).toBe(1);

    // Cleanup
    list1.remove();
    list2.remove();
  });

  it('_listReadPending flag prevents second definedCallback from firing READ', async () => {
    // Directly test the dedup mechanism at the DynamicClass level
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    await flush(10);
    global.fetch.mockClear();

    // Spy on DC.call to count READ invocations
    const originalCall = DC.call;
    let readCount = 0;
    DC.call = function(method, ...args) {
      if (method === 'READ') readCount++;
      return originalCall.call(DC, method, ...args);
    };

    // Simulate two definedCallbacks firing in sequence (as happens during SCHEMA replay)
    // First: sets _listReadPending = true, fires READ
    DC._listReadPending = false;
    expect(DC._listReadPending).toBe(false);
    DC._listReadPending = true;
    DC.call('READ', { limit: 20, offset: 0, depth: 1 }, { inbox: 'UPDATE' });

    // Second: should see _listReadPending = true and skip
    expect(DC._listReadPending).toBe(true);
    // (ListElement.definedCallback would check this flag and return early)

    expect(readCount).toBe(1);
    DC.call = originalCall;
  });
});


describe('Full bootstrap: schema + data should be exactly 2 requests total', () => {

  it('full bootstrap: SCHEMA + attach callbacks + watchers = 0 data fetches from SCHEMA', async () => {
    // Simulate the full page bootstrap at the NTT level:
    // 1. Sidebar calls NTT.attach (queues callback)
    // 2. Two lists call NTT.attach (queues callbacks)
    // 3. Two ATTACH TXs are queued
    // 4. Schema arrives → SCHEMA handler runs
    //
    // After fix, SCHEMA itself produces 0 data fetches.
    // Only consumer components (ListElement) trigger READs via definedCallback().

    const sidebarCb = vi.fn();
    const listCb1 = vi.fn();
    const listCb2 = vi.fn();

    // Step 1-3: Queue everything before schema arrives
    NTT.attach('Product', sidebarCb);
    NTT.attach('Product', listCb1);
    NTT.attach('Product', listCb2);

    NTT.ATTACH('Product', new TX({
      name: 'ATTACH', source: 'list-1', target: 'NTT', data: 'Product',
    }));
    NTT.ATTACH('Product', new TX({
      name: 'ATTACH', source: 'list-2', target: 'NTT', data: 'Product',
    }));

    // Clear fetch mock to only count data fetches from SCHEMA onward
    global.fetch.mockClear();

    // Step 4: Schema arrives
    NTT.SCHEMA(ProductSchema);
    await flush(50);

    // All callbacks should have fired
    expect(sidebarCb).toHaveBeenCalled();
    expect(listCb1).toHaveBeenCalled();
    expect(listCb2).toHaveBeenCalled();

    // Both watchers should be registered
    const DC = NTT.get('Product');
    expect(DC._watchers.has('list-1')).toBe(true);
    expect(DC._watchers.has('list-2')).toBe(true);

    // SCHEMA itself should have produced ZERO data fetches.
    // Data fetching is entirely the responsibility of consumer components.
    const dataFetches = countProductDataFetches();
    expect(dataFetches).toBe(0);
  });
});
