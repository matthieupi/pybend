import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../../utils/Assert.js', () => ({
  default: vi.fn((caller, cond, msg) => { if (!cond) throw new Error(msg); }),
  caution: vi.fn(), inform: vi.fn(),
}));
vi.mock('../../config.js', () => ({
  config: {
    LOGGING: 3, LOGEVENTS: false, DEBUG: false,
    API_URL: 'http://localhost:5000',
  }
}));

import { registry, registrar, getRegistrar, dispatch } from '../../utils/registrar.js';

describe('registrar.js', () => {

  beforeEach(() => {
    // Clear registry between tests
    registry.clear();
  });

  describe('registrar(key, callback)', () => {
    it('should register a callback in the registry', () => {
      const cb = vi.fn();
      registrar('test-key', cb);
      expect(registry.has('test-key')).toBe(true);
      expect(registry.get('test-key')).toBe(cb);
    });

    it('should return an unregister function', () => {
      const cb = vi.fn();
      const unregister = registrar('test-key', cb);
      expect(typeof unregister).toBe('function');
    });

    it('should unregister when unregister function is called', () => {
      const cb = vi.fn();
      const unregister = registrar('test-key', cb);
      unregister();
      expect(registry.has('test-key')).toBe(false);
    });

    it('should overwrite existing registry entry', () => {
      const cb1 = vi.fn();
      const cb2 = vi.fn();
      registrar('key', cb1);
      registrar('key', cb2);
      expect(registry.get('key')).toBe(cb2);
    });

    it('should delete entry when callback is falsy', () => {
      const cb = vi.fn();
      registrar('key', cb);
      registrar('key', null);
      expect(registry.has('key')).toBe(false);
    });

    it('should warn when unregistering non-existent key', () => {
      const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
      registrar('non-existent', null);
      expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining('non-existent'));
      warnSpy.mockRestore();
    });

    it('should throw when key is undefined', () => {
      expect(() => registrar(undefined, vi.fn())).toThrow();
    });
  });

  describe('getRegistrar(key)', () => {
    // NOTE: The source has an inverted assertion on line 41:
    //   assert(this, !registry.has(key), `No entry found...`)
    // This asserts when key IS found (!) — the opposite of the error message.
    // The function still returns the correct value via registry.get(key),
    // but the assert fires incorrectly. This is a known source bug.
    // We test actual behavior as-is (assert fires, then returns value).

    it('should throw assertion when key exists (inverted assert bug)', () => {
      const cb = vi.fn();
      registrar('test-key', cb);
      // The assert incorrectly fires when key IS found
      expect(() => getRegistrar('test-key')).toThrow('No entry found');
    });

    it('should throw when key is undefined', () => {
      expect(() => getRegistrar(undefined)).toThrow();
    });
  });

  describe('dispatch(key, data, meta)', () => {
    it('should call the registered callback with data', () => {
      const cb = vi.fn();
      registrar('test-key', cb);
      dispatch('test-key', { msg: 'hello' });
      expect(cb).toHaveBeenCalledWith({ msg: 'hello' });
    });

    it('should throw when key is not in registry', () => {
      expect(() => dispatch('missing-key', {})).toThrow();
    });

    it('should catch errors thrown by callback', () => {
      const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      const badCb = vi.fn(() => { throw new Error('boom'); });
      registrar('bad-key', badCb);
      // dispatch should not throw — it catches internally
      expect(() => dispatch('bad-key', {})).not.toThrow();
      expect(errorSpy).toHaveBeenCalled();
      errorSpy.mockRestore();
    });

    it('should throw when key is undefined', () => {
      expect(() => dispatch(undefined, {})).toThrow();
    });
  });

  describe('registry Map', () => {
    it('should start empty (after beforeEach clear)', () => {
      expect(registry.size).toBe(0);
    });

    it('should track multiple registrations', () => {
      registrar('a', vi.fn());
      registrar('b', vi.fn());
      registrar('c', vi.fn());
      expect(registry.size).toBe(3);
    });
  });
});
