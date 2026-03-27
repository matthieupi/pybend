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

    it('should silently ignore non-string data', () => {
      const cb = vi.fn();
      router.observe('route', cb);
      router.NAVIGATE({ tag: 'ntx-item', attrs: { ref: 'x' } });
      expect(cb).not.toHaveBeenCalled();
      expect(router.current).toBeNull();
    });

    it('should handle multiple navigations', () => {
      router.NAVIGATE('A');
      router.NAVIGATE('B');
      router.NAVIGATE('C');
      expect(router.current).toBe('C');
      expect(router.canGoBack).toBe(true);
    });

    it('should ignore objects, numbers, null, undefined', () => {
      const cb = vi.fn();
      router.observe('route', cb);
      router.NAVIGATE({ tag: 'ntx-profile' });
      router.NAVIGATE(42);
      router.NAVIGATE(null);
      router.NAVIGATE(undefined);
      router.NAVIGATE('');
      expect(cb).not.toHaveBeenCalled();
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

  describe('navigate() / back() sugar', () => {
    it('navigate() sets current like NAVIGATE', () => {
      router.navigate('Product/1');
      expect(router.current).toBe('Product/1');
    });

    it('back() pops like BACK', () => {
      router.navigate('A');
      router.navigate('B');
      router.back();
      expect(router.current).toBe('A');
    });

    it('navigate() triggers observers', () => {
      const cb = vi.fn();
      router.observe('route', cb);
      router.navigate('X');
      expect(cb).toHaveBeenCalledWith('X', null, 'route', router);
    });
  });

  describe('stack cap', () => {
    it('should cap stack at 50 entries', () => {
      for (let i = 0; i < 55; i++) {
        router.NAVIGATE(`route-${i}`);
      }
      expect(router.current).toBe('route-54');
      // Back 50 times should exhaust the stack
      let backs = 0;
      while (router.canGoBack) {
        router.BACK();
        backs++;
      }
      expect(backs).toBe(50);
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

  describe('resolved (getter)', () => {
    it('should return null when no route', () => {
      expect(router.resolved).toBeNull();
    });

    it('should return resolveRoute output for string route', () => {
      router.NAVIGATE('Product/3');
      const r = router.resolved;
      expect(r.tag).toBe('ntx-item'); // no schema → default
      expect(r.attrs.ref).toBe('Product/3');
      expect(r.attrs.display).toBe('lg');
    });

    it('should use getSchema when provided', () => {
      const name = `schema-${Math.random().toString(36).slice(2)}`;
      const schema = { ui: { renderer: { detail: 'ntx-custom' } } };
      const r = new Router(name, { hash: false, getSchema: () => schema });
      r.NAVIGATE('Product/3');
      expect(r.resolved.tag).toBe('ntx-custom');
    });

    it('should resolve app routes', () => {
      router.NAVIGATE('@profile');
      const r = router.resolved;
      expect(r.tag).toBe('ntx-profile');
      expect(r.title).toBe('Profile');
    });

    it('should resolve model routes', () => {
      router.NAVIGATE('Grant');
      const r = router.resolved;
      expect(r.tag).toBe('ntx-list');
      expect(r.attrs.model).toBe('Grant');
    });
  });
});
