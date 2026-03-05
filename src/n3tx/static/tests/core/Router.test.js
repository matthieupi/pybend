import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('../../utils/Assert.js', () => ({
  default: vi.fn((caller, cond, msg) => {
    if (!cond) throw new Error(msg || 'Assertion failed');
  }),
  caution: vi.fn(), inform: vi.fn(),
}));

vi.mock('../../config.js', () => ({
  config: { LOGGING: 3, LOGEVENTS: true, DEBUG: true, API_URL: 'http://localhost:5000',
    E: { CONNECT: 'CONNECT', UPDATE: 'UPDATE', READ: 'READ', NAVIGATE: 'NAVIGATE', BACK: 'BACK' }
  }
}));

vi.mock('../../utils/Logging.js', () => ({
  default: { warn: vi.fn(), error: vi.fn(), debug: vi.fn(), dev: vi.fn(), log: vi.fn(), init: vi.fn(), event: vi.fn() }
}));

import { Router, getRouter } from '../../core/Router.js';

describe('Router.js', () => {

  let router;

  beforeEach(() => {
    // Create a fresh router for each test
    const name = `test-router-${Math.random().toString(36).slice(2)}`;
    router = new Router(name, { hash: false });
  });

  describe('constructor(addr, {hash})', () => {
    it('should create router with hash sync off', () => {
      expect(router.current).toBeNull();
      expect(router.canGoBack).toBe(false);
    });

    it('should register in global routers map', () => {
      const name = `global-${Math.random().toString(36).slice(2)}`;
      const r = new Router(name);
      expect(getRouter(name)).toBe(r);
    });
  });

  describe('current (getter)', () => {
    it('should return null initially', () => {
      expect(router.current).toBeNull();
    });

    it('should return current route after navigation', () => {
      router.NAVIGATE('Product/1');
      expect(router.current).toBe('Product/1');
    });
  });

  describe('canGoBack (getter)', () => {
    it('should return false when stack is empty', () => {
      expect(router.canGoBack).toBe(false);
    });

    it('should return true after navigation', () => {
      router.NAVIGATE('Product/1');
      expect(router.canGoBack).toBe(true);
    });
  });

  describe('NAVIGATE(data, tx)', () => {
    it('should push old route to stack and set current', () => {
      router.NAVIGATE('Product/1');
      expect(router.current).toBe('Product/1');
      expect(router.canGoBack).toBe(true);
    });

    it('should notify observers', () => {
      const cb = vi.fn();
      router.observe('route', cb);
      router.NAVIGATE('Product/1');
      expect(cb).toHaveBeenCalledWith('Product/1', null, 'route', router);
    });

    it('should return early if navigating to same route (string)', () => {
      router.NAVIGATE('Product/1');
      const cb = vi.fn();
      router.observe('route', cb);
      router.NAVIGATE('Product/1'); // Same route
      expect(cb).not.toHaveBeenCalled();
    });

    it('should return early if navigating to same route (object)', () => {
      const route = { tag: 'ntx-item', attrs: { ref: 'x' } };
      router.NAVIGATE(route);
      const cb = vi.fn();
      router.observe('route', cb);
      router.NAVIGATE({ tag: 'ntx-item', attrs: { ref: 'x' } }); // Same by JSON
      expect(cb).not.toHaveBeenCalled();
    });

    it('should handle multiple navigations', () => {
      router.NAVIGATE('A');
      router.NAVIGATE('B');
      router.NAVIGATE('C');
      expect(router.current).toBe('C');
      expect(router.canGoBack).toBe(true);
    });

    it('should handle object routes', () => {
      const route = { tag: 'ntx-profile', attrs: {}, title: 'Profile' };
      router.NAVIGATE(route);
      expect(router.current).toEqual(route);
    });
  });

  describe('BACK(data, tx)', () => {
    it('should pop from stack and revert to previous route', () => {
      router.NAVIGATE('A');
      router.NAVIGATE('B');
      router.BACK();
      expect(router.current).toBe('A');
    });

    it('should notify observers', () => {
      router.NAVIGATE('A');
      router.NAVIGATE('B');
      const cb = vi.fn();
      router.observe('route', cb);
      router.BACK();
      expect(cb).toHaveBeenCalledWith('A', 'B', 'route', router);
    });

    it('should return early when no stack (canGoBack false)', () => {
      const cb = vi.fn();
      router.observe('route', cb);
      router.BACK();
      expect(cb).not.toHaveBeenCalled();
    });

    it('should pop to null when stack has one item', () => {
      router.NAVIGATE('A');
      router.BACK();
      expect(router.current).toBeNull();
      expect(router.canGoBack).toBe(false);
    });

    it('should handle multiple backs', () => {
      router.NAVIGATE('A');
      router.NAVIGATE('B');
      router.NAVIGATE('C');
      router.BACK();
      expect(router.current).toBe('B');
      router.BACK();
      expect(router.current).toBe('A');
      router.BACK();
      expect(router.current).toBeNull();
    });
  });

  describe('getRouter(addr)', () => {
    it('should retrieve registered router', () => {
      const name = `get-test-${Math.random().toString(36).slice(2)}`;
      const r = new Router(name);
      expect(getRouter(name)).toBe(r);
    });

    it('should return undefined for unregistered addr', () => {
      expect(getRouter('nonexistent')).toBeUndefined();
    });
  });

  describe('hash sync', () => {
    it('should create router with hash sync on', () => {
      const name = `hash-${Math.random().toString(36).slice(2)}`;
      const r = new Router(name, { hash: true });
      expect(r).toBeTruthy();
    });
  });
});
