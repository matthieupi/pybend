/**
 * Router + Navigation — Integration Tests
 *
 * Tests: NAVIGATE, BACK, hash sync, route types, canGoBack
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { flush } from './helpers/test-env.js';

let Router, getRouter, matrix, TX;

afterEach(async () => {
  await flush(10);
});

beforeEach(async () => {
  vi.resetModules();
  // Reset hash
  window.location.hash = '';

  global.fetch = vi.fn(() => Promise.resolve({
    ok: true, status: 200,
    json: () => Promise.resolve({}),
  }));

  const routerMod = await import('../../core/Router.js');
  const matrixMod = await import('../../core/Matrix.js');
  const txMod = await import('../../core/TX.js');
  Router = routerMod.Router;
  getRouter = routerMod.getRouter;
  matrix = matrixMod.matrix;
  TX = txMod.default;
});

describe('Router Navigation', () => {

  it('Router constructor initializes with null current', () => {
    const router = new Router('test-router-1', { hash: false });
    expect(router.current).toBeNull();
    expect(router.canGoBack).toBe(false);
  });

  it('getRouter retrieves by name', () => {
    const router = new Router('test-router-2', { hash: false });
    expect(getRouter('test-router-2')).toBe(router);
  });

  it('NAVIGATE changes current and updates stack', () => {
    const router = new Router('test-router-3', { hash: false });
    router.NAVIGATE('Product/1');
    expect(router.current).toBe('Product/1');
    expect(router.canGoBack).toBe(true);
  });

  it('NAVIGATE fires route observers', () => {
    const router = new Router('test-router-4', { hash: false });
    const observer = vi.fn();
    router.observe('route', observer);

    router.NAVIGATE('Product/1');
    expect(observer).toHaveBeenCalledWith('Product/1', null, 'route', router);
  });

  it('duplicate NAVIGATE with same data is a no-op', () => {
    const router = new Router('test-router-5', { hash: false });
    const observer = vi.fn();
    router.observe('route', observer);

    router.NAVIGATE('Product/1');
    router.NAVIGATE('Product/1'); // duplicate
    expect(observer).toHaveBeenCalledTimes(1);
  });

  it('BACK pops route from stack', () => {
    const router = new Router('test-router-6', { hash: false });
    router.NAVIGATE('Product/1');
    router.NAVIGATE('Product/2');
    expect(router.current).toBe('Product/2');

    router.BACK();
    expect(router.current).toBe('Product/1');
    expect(router.canGoBack).toBe(true);

    router.BACK();
    expect(router.current).toBeNull();
    expect(router.canGoBack).toBe(false);
  });

  it('BACK at root does nothing', () => {
    const router = new Router('test-router-7', { hash: false });
    const observer = vi.fn();
    router.observe('route', observer);

    router.BACK(); // No history — should be no-op
    expect(observer).not.toHaveBeenCalled();
    expect(router.current).toBeNull();
  });

  it('BACK fires route observers', () => {
    const router = new Router('test-router-8', { hash: false });
    const observer = vi.fn();

    router.NAVIGATE('Product/1');
    router.observe('route', observer);
    router.BACK();

    expect(observer).toHaveBeenCalledWith(null, 'Product/1', 'route', router);
  });

  it('multiple NAVIGATE builds correct stack depth', () => {
    const router = new Router('test-router-9', { hash: false });
    router.NAVIGATE('A');
    router.NAVIGATE('B');
    router.NAVIGATE('C');
    router.NAVIGATE('D');

    expect(router.current).toBe('D');
    expect(router.canGoBack).toBe(true);

    router.BACK();
    expect(router.current).toBe('C');
    router.BACK();
    expect(router.current).toBe('B');
    router.BACK();
    expect(router.current).toBe('A');
    router.BACK();
    expect(router.current).toBeNull();
    expect(router.canGoBack).toBe(false);
  });

  it('non-string data is silently ignored', () => {
    const router = new Router('test-router-10', { hash: false });
    const observer = vi.fn();
    router.observe('route', observer);
    router.NAVIGATE({ tag: 'ntx-profile', attrs: {} });
    router.NAVIGATE(42);
    expect(observer).not.toHaveBeenCalled();
    expect(router.current).toBeNull();
  });

  it('full flow: buildRoute string → NAVIGATE → resolved', async () => {
    const { buildRoute, parseRoute, resolveRoute } = await import('../../core/Router.js');
    const router = new Router('test-router-11', { hash: false });
    const route = buildRoute({ type: 'model', model: 'Grant', params: { view: 'table' } });
    expect(route).toBe('Grant?view=table');
    router.NAVIGATE(route);
    expect(router.current).toBe('Grant?view=table');
    // resolved getter works (no schema → ntx-table via view= param)
    const resolved = resolveRoute(parseRoute(router.current));
    expect(resolved.tag).toBe('ntx-table');
    expect(resolved.attrs.model).toBe('Grant');
    expect(resolved.attrs.view).toBeUndefined(); // filtered from passthrough
  });

  it('@ prefixed routes resolve to ntx-{name} tag', () => {
    const router = new Router('test-router-12', { hash: false });
    router.NAVIGATE('@profile');
    expect(router.current).toBe('@profile');
    // ntx-router component would resolve this to <ntx-profile>
  });

  it('string routes with / resolve model and id', () => {
    const router = new Router('test-router-13', { hash: false });
    router.NAVIGATE('Product/3');
    expect(router.current).toBe('Product/3');
  });

  it('hash sync updates location.hash on NAVIGATE', () => {
    const router = new Router('test-router-hash-1', { hash: true });
    router.NAVIGATE('Product/3');
    expect(window.location.hash).toBe('#Product/3');
  });

  it('hash sync preserves named collection view routes exactly', () => {
    const router = new Router('test-router-hash-view', { hash: true });
    router.NAVIGATE('Product/@table');
    expect(router.current).toBe('Product/@table');
    expect(window.location.hash).toBe('#Product/@table');
  });

  it('full flow: named collection view route resolves schema renderer', async () => {
    const { buildRoute, parseRoute, resolveRoute } = await import('../../core/Router.js');
    const router = new Router('test-router-named-view-flow', { hash: false });
    const route = buildRoute({ type: 'model', model: 'Product', isViewRoute: true, view: 'table' });
    expect(route).toBe('Product/@table');
    router.NAVIGATE(route);
    expect(router.current).toBe('Product/@table');

    const schema = { ui: { renderer: { table: 'ntx-product-table' } } };
    const resolved = resolveRoute(parseRoute(router.current), () => schema);
    expect(resolved.tag).toBe('ntx-product-table');
    expect(resolved.attrs).toEqual({ model: 'Product' });
  });

  it('full flow: member default view route resolves schema renderer', async () => {
    const { buildRoute, parseRoute, resolveRoute } = await import('../../core/Router.js');
    const router = new Router('test-router-member-view-flow', { hash: false });
    const route = buildRoute({ type: 'detail', model: 'Product', id: '1', isViewRoute: true });
    expect(route).toBe('Product/1/@');
    router.NAVIGATE(route);
    expect(router.current).toBe('Product/1/@');

    const schema = { ui: { renderer: { detail: 'ntx-product-detail', item: 'ntx-product-card' } } };
    const resolved = resolveRoute(parseRoute(router.current), () => schema);
    expect(resolved.tag).toBe('ntx-product-detail');
    expect(resolved.attrs).toEqual({ ref: 'Product/1', display: 'lg' });
    expect(resolved.attrs.method).toBeUndefined();
  });

  it('full flow: named member view route resolves schema renderer without method attrs', async () => {
    const { buildRoute, parseRoute, resolveRoute } = await import('../../core/Router.js');
    const router = new Router('test-router-named-member-view-flow', { hash: false });
    const route = buildRoute({ type: 'detail', model: 'Product', id: '1', isViewRoute: true, view: 'chat' });
    expect(route).toBe('Product/1/@chat');
    router.NAVIGATE(route);
    expect(router.current).toBe('Product/1/@chat');

    const schema = { ui: { renderer: { chat: 'ntx-product-chat' } } };
    const resolved = resolveRoute(parseRoute(router.current), () => schema);
    expect(resolved.tag).toBe('ntx-product-chat');
    expect(resolved.attrs).toEqual({ ref: 'Product/1', display: 'lg' });
    expect(resolved.attrs.method).toBeUndefined();
  });

  it('full flow: method and same-named view routes stay distinct', async () => {
    const { parseRoute, resolveRoute } = await import('../../core/Router.js');
    const schema = {
      ui: { renderer: { run: 'ntx-run-view' } },
      methods: { run: { ui: { renderer: 'ntx-run-method' } } },
    };

    const action = resolveRoute(parseRoute('Product/1/run'), () => schema);
    const view = resolveRoute(parseRoute('Product/1/@run'), () => schema);

    expect(action.attrs.method).toBe('run');
    expect(view.tag).toBe('ntx-run-view');
    expect(view.attrs.method).toBeUndefined();
  });

  it('hash sync clears hash on BACK to root', () => {
    const router = new Router('test-router-hash-2', { hash: true });
    router.NAVIGATE('Product/3');
    router.BACK();
    // Hash should be cleared (no # or empty)
    expect(window.location.hash).toBe('');
  });

  it('rapid sequential hash changes keep router state valid', async () => {
    const errors = [];
    const onError = (event) => errors.push(event.error?.message || event.message || String(event));
    window.addEventListener('error', onError);

    try {
      const router = new Router('test-router-rapid-hash', { hash: true });

      window.location.hash = '#Product/1';
      window.dispatchEvent(new HashChangeEvent('hashchange'));
      window.location.hash = '#Product/2';
      window.dispatchEvent(new HashChangeEvent('hashchange'));
      window.location.hash = '#Product/3';
      window.dispatchEvent(new HashChangeEvent('hashchange'));
      window.location.hash = '';
      window.dispatchEvent(new HashChangeEvent('hashchange'));

      await flush();

      expect(router.current).toBeNull();
      expect(router.resolved).toBeNull();
      expect(errors).toEqual([]);
    } finally {
      window.removeEventListener('error', onError);
    }
  });

  it('Router is registered in matrix', () => {
    const router = new Router('test-router-matrix', { hash: false });
    expect(matrix.children.has('test-router-matrix')).toBe(true);
  });
});
