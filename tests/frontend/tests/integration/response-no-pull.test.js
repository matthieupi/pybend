/**
 * _response_ should NOT unconditionally pull — Integration Tests
 *
 * Bug: After any method call (like, favorite, comment), DynamicClass.prototype._response_
 * calls this.pull() which:
 *   1. Makes a redundant GET request to refetch the entity
 *   2. The response triggers a full re-render via signal → NTTElement → scheduleRender → innerHTML
 *   3. Full innerHTML rebuild destroys img elements, causing image reloads and layout shifts
 *
 * Fix: _response_ should only pull when the response data isn't sufficient.
 *   - If the response contains entity data (has id), update directly (no network)
 *   - If the response is a structured action result with _field + id, update locally
 *   - Components that need fresh data can call pull() explicitly
 *
 * The key insight: the extra GET is wasteful because:
 *   - For entity-data responses: the data is right there in the response
 *   - For social action responses ({action, _field, id}): the count/state update
 *     is encoded in the response and can update locally.
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

  global.fetch = vi.fn((url, opts) => {
    const urlStr = typeof url === 'string' ? url : url.toString();
    const method = opts?.method?.toUpperCase() || 'GET';

    if (urlStr.endsWith('/Product')) {
      return Promise.resolve({
        ok: true, status: 200,
        json: () => Promise.resolve(ProductSchema),
      });
    }
    // Individual product fetch
    if (/\/Product\/\d+/.test(urlStr) && method === 'GET') {
      const id = parseInt(urlStr.match(/\/Product\/(\d+)/)[1]);
      return Promise.resolve({
        ok: true, status: 200,
        json: () => Promise.resolve(makeProductData(id)),
      });
    }
    // Product favorite toggle response carries enough data for local update.
    if (/\/Product\/\d+\/favorite/.test(urlStr) && method === 'POST') {
      return Promise.resolve({
        ok: true, status: 200,
        json: () => Promise.resolve({ action: 'favorited', _field: 'favorites', id: 99, user: 1 }),
      });
    }
    // Product comment returns a child Comment entity, so Product must pull.
    if (/\/Product\/\d+\/comment/.test(urlStr) && method === 'POST') {
      return Promise.resolve({
        ok: true, status: 200,
        json: () => Promise.resolve({
          id: 99,
          $schema: `${API_URL}/Comment`,
          $id: `${API_URL}/Product/1/Comment/99`,
          name: 'Great!',
          description: '',
        }),
      });
    }
    // List fetch
    if (urlStr.includes('/Product/_')) {
      return Promise.resolve({
        ok: true, status: 200,
        json: () => Promise.resolve(makeProductListResponse(3)),
      });
    }
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


describe('_response_ should not trigger network pull for action responses', () => {

  it('_response_ with structured action data should NOT call pull() or make any GET request', async () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    DC.READ(makeProductListResponse(3));
    await flush(50);

    const instance = DC.children.get('1');

    // Spy on pull
    let pullCalled = false;
    const originalPull = instance.pull;
    instance.pull = function() { pullCalled = true; return originalPull.call(this); };

    global.fetch.mockClear();

    // Simulate structured favorite response
    instance._response_({ action: 'favorited', _field: 'favorites', id: 99, user: 1 });
    await flush(100);

    // _response_ with structured action data should NOT call pull()
    expect(pullCalled).toBe(false);
    expect(instance.value?.favorites).toContain(`${API_URL}/Product/1/favorites/99`);

    // No network requests should have been made
    const gets = global.fetch.mock.calls.filter(([u, o]) => (o?.method || 'GET').toUpperCase() === 'GET');
    expect(gets.length).toBe(0);

    instance.pull = originalPull;
  });

  it('_response_ with entity data (has id) should update directly without pull', async () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    DC.READ(makeProductListResponse(3));
    await flush(50);

    const instance = DC.children.get('1');
    const origName = instance.value?.name;

    let pullCalled = false;
    const originalPull = instance.pull;
    instance.pull = function() { pullCalled = true; return originalPull.call(this); };

    global.fetch.mockClear();

    // Simulate response that returns entity data (e.g., backend returns updated entity)
    const entityData = makeProductData(1);
    entityData.name = 'Updated Product';
    entityData.favorites = [`${API_URL}/Product/1/favorites/99`];
    instance._response_(entityData);
    await flush(100);

    // Should NOT have called pull — response had entity data
    expect(pullCalled).toBe(false);

    // Should have updated the instance directly
    expect(instance.value?.name).toBe('Updated Product');

    // No GET requests
    const gets = global.fetch.mock.calls.filter(([u, o]) => (o?.method || 'GET').toUpperCase() === 'GET');
    expect(gets.length).toBe(0);

    instance.pull = originalPull;
  });

  it('_response_ should still work after the fix — entity signals should fire for direct updates', async () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    DC.READ(makeProductListResponse(3));
    await flush(50);

    const instance = DC.children.get('1');

    // Track signals
    let signalCount = 0;
    instance.signal(() => { signalCount++; }, true);

    // Entity data response → should update + signal
    const entityData = makeProductData(1);
    entityData.name = 'Signaled Product';
    instance._response_(entityData);
    await flush(50);

    // Signal should have fired (from instance.update → value setter → signal)
    expect(signalCount).toBeGreaterThanOrEqual(1);
    expect(instance.value?.name).toBe('Signaled Product');
  });
});


describe('Full method call flow with fixed _response_', () => {

  it('favorite via instance.call() should produce only 1 POST, zero GETs', async () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    DC.READ(makeProductListResponse(3));
    await flush(50);

    global.fetch.mockClear();

    const instance = DC.children.get('1');
    instance.call('favorite', {}, { inbox: '_response_' });
    await flush(300);

    const allCalls = global.fetch.mock.calls.map(([url, opts]) => ({
      url: typeof url === 'string' ? url : url.toString(),
      method: opts?.method?.toUpperCase() || 'GET',
    }));

    const posts = allCalls.filter(c => c.method === 'POST');
    const gets = allCalls.filter(c => c.method === 'GET');

    // 1 POST for the favorite action
    expect(posts.length).toBe(1);
    expect(posts[0].url).toContain('/Product/1/favorite');

    // ZERO GETs — no pull after _response_
    expect(gets.length).toBe(0);
  });

  it('comment via instance.call() should pull because the method returns a child entity', async () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    DC.READ(makeProductListResponse(3));
    await flush(50);

    global.fetch.mockClear();

    const instance = DC.children.get('1');
    instance.call('comment', { comment: { name: 'Great!' } }, { inbox: '_response_' });
    await flush(300);

    const allCalls = global.fetch.mock.calls.map(([url, opts]) => ({
      url: typeof url === 'string' ? url : url.toString(),
      method: opts?.method?.toUpperCase() || 'GET',
    }));

    const posts = allCalls.filter(c => c.method === 'POST');
    const gets = allCalls.filter(c => c.method === 'GET');

    expect(posts.length).toBe(1);
    // Product.comment returns a Comment entity, so Product pulls to refresh comments.
    expect(gets.length).toBe(1);
  });
});
