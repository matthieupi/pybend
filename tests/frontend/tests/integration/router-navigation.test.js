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

  it('object route data is supported', () => {
    const router = new Router('test-router-10', { hash: false });
    const routeData = { tag: 'custom-component', attrs: { id: 1 }, title: 'Custom' };
    router.NAVIGATE(routeData);
    expect(router.current).toEqual(routeData);
  });

  it('duplicate object route data is detected via JSON.stringify', () => {
    const router = new Router('test-router-11', { hash: false });
    const observer = vi.fn();
    router.observe('route', observer);

    const routeData = { tag: 'custom-component', attrs: { id: 1 } };
    router.NAVIGATE(routeData);
    router.NAVIGATE({ tag: 'custom-component', attrs: { id: 1 } }); // same shape
    expect(observer).toHaveBeenCalledTimes(1); // duplicate ignored
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

  it('hash sync clears hash on BACK to root', () => {
    const router = new Router('test-router-hash-2', { hash: true });
    router.NAVIGATE('Product/3');
    router.BACK();
    // Hash should be cleared (no # or empty)
    expect(window.location.hash).toBe('');
  });

  it('Router is registered in matrix', () => {
    const router = new Router('test-router-matrix', { hash: false });
    expect(matrix.children.has('test-router-matrix')).toBe(true);
  });
});
