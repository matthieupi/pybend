import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../../utils/Assert.js', () => ({
  default: vi.fn((caller, cond, msg) => {
    if (!cond) throw new Error(msg || 'Assertion failed');
  }),
  caution: vi.fn(),
  inform: vi.fn(),
}));

vi.mock('../../config.js', () => ({
  config: { LOGGING: 3, LOGEVENTS: true, DEBUG: true, API_URL: 'http://localhost:5000',
    E: { CONNECT: 'CONNECT', UPDATE: 'UPDATE', READ: 'READ', ENABLE: 'ENABLE', DISABLE: 'DISABLE' }
  }
}));

vi.mock('../../utils/Logging.js', () => ({
  default: { warn: vi.fn(), error: vi.fn(), debug: vi.fn(), dev: vi.fn(), log: vi.fn(), init: vi.fn(), event: vi.fn() }
}));

import Observable from '../../core/Observable.js';

describe('Observable.js', () => {

  describe('static apply(Base)', () => {
    it('should augment class with signal, observe, notify methods', () => {
      class TestClass {}
      Observable.apply(TestClass);
      const instance = new TestClass();
      expect(typeof instance.signal).toBe('function');
      expect(typeof instance.observe).toBe('function');
      expect(typeof instance.notify).toBe('function');
    });

    it('should be idempotent (already applied)', () => {
      class TestClass {}
      Observable.apply(TestClass);
      Observable.apply(TestClass); // Apply again
      const instance = new TestClass();
      expect(typeof instance.signal).toBe('function');
    });

    it('should throw TypeError if Base is not a function', () => {
      expect(() => Observable.apply(null)).toThrow(TypeError);
      expect(() => Observable.apply('not a class')).toThrow(TypeError);
      expect(() => Observable.apply(42)).toThrow(TypeError);
    });
  });

  describe('signal(callback, wait)', () => {
    let TestClass, instance;

    beforeEach(() => {
      TestClass = class {};
      Observable.apply(TestClass);
      instance = new TestClass();
    });

    it('should fire all listeners when called with no callback', () => {
      const listener = vi.fn();
      instance.signal(listener);
      listener.mockClear();
      instance.signal(); // Fire all
      expect(listener).toHaveBeenCalledWith(instance);
    });

    it('should fire callback immediately if wait=false (default)', () => {
      const cb = vi.fn();
      instance.signal(cb);
      expect(cb).toHaveBeenCalledWith(instance);
    });

    it('should not fire callback immediately if wait=true', () => {
      const cb = vi.fn();
      instance.signal(cb, true);
      expect(cb).not.toHaveBeenCalled();
    });

    it('should register callback and return unsubscribe function', () => {
      const cb = vi.fn();
      const unsub = instance.signal(cb);
      expect(typeof unsub).toBe('function');
      cb.mockClear();
      instance.signal(); // Fire all
      expect(cb).toHaveBeenCalledTimes(1);
    });

    it('should remove listener on unsubscribe', () => {
      const cb = vi.fn();
      const unsub = instance.signal(cb);
      cb.mockClear();
      unsub();
      instance.signal(); // Fire all
      expect(cb).not.toHaveBeenCalled();
    });

    it('should throw if callback is not a function', () => {
      expect(() => instance.signal('not-a-function')).toThrow();
    });
  });

  describe('observe(property, callback)', () => {
    let TestClass, instance;

    beforeEach(() => {
      TestClass = class {};
      Observable.apply(TestClass);
      instance = new TestClass();
    });

    it('should register observer for property', () => {
      const cb = vi.fn();
      instance.observe('name', cb);
      instance.notify('name', 'new', 'old');
      expect(cb).toHaveBeenCalledWith('new', 'old', 'name', instance);
    });

    it('should return unsubscribe function', () => {
      const cb = vi.fn();
      const unsub = instance.observe('name', cb);
      expect(typeof unsub).toBe('function');
    });

    it('should cleanup on unsubscribe', () => {
      const cb = vi.fn();
      const unsub = instance.observe('name', cb);
      unsub();
      instance.notify('name', 'new', 'old');
      expect(cb).not.toHaveBeenCalled();
    });

    it('should throw if property is null/empty', () => {
      expect(() => instance.observe(null, vi.fn())).toThrow();
      expect(() => instance.observe('', vi.fn())).toThrow();
    });

    it('should throw if callback is null', () => {
      expect(() => instance.observe('name', null)).toThrow();
    });

    it('should support multiple observers for same property', () => {
      const cb1 = vi.fn();
      const cb2 = vi.fn();
      instance.observe('name', cb1);
      instance.observe('name', cb2);
      instance.notify('name', 'val', 'old');
      expect(cb1).toHaveBeenCalled();
      expect(cb2).toHaveBeenCalled();
    });

    it('should cleanup observer set when last observer removed', () => {
      const cb = vi.fn();
      const unsub = instance.observe('name', cb);
      unsub();
      // Notifying after cleanup should not throw
      instance.notify('name', 'val', 'old');
      expect(cb).not.toHaveBeenCalled();
    });
  });

  describe('notify(property, newValue, oldValue)', () => {
    let TestClass, instance;

    beforeEach(() => {
      TestClass = class {};
      Observable.apply(TestClass);
      instance = new TestClass();
    });

    it('should call all observers for property', () => {
      const cb1 = vi.fn();
      const cb2 = vi.fn();
      instance.observe('x', cb1);
      instance.observe('x', cb2);
      instance.notify('x', 10, 5);
      expect(cb1).toHaveBeenCalledWith(10, 5, 'x', instance);
      expect(cb2).toHaveBeenCalledWith(10, 5, 'x', instance);
    });

    it('should pass newValue, oldValue, property, this to callback', () => {
      const cb = vi.fn();
      instance.observe('count', cb);
      instance.notify('count', 42, 0);
      expect(cb).toHaveBeenCalledWith(42, 0, 'count', instance);
    });

    it('should throw if property is null/empty', () => {
      expect(() => instance.notify(null, 1, 0)).toThrow();
      expect(() => instance.notify('', 1, 0)).toThrow();
    });

    it('should no-op if property has no observers', () => {
      expect(() => instance.notify('unobserved', 1, 0)).not.toThrow();
    });
  });
});
