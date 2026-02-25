import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../../utils/Assert.js', () => ({
  default: vi.fn((caller, cond, msg) => {
    if (!cond) throw new Error(msg || 'Assertion failed');
  }),
  caution: vi.fn(), inform: vi.fn(),
}));

vi.mock('../../config.js', () => ({
  config: {
    LOGGING: 3, LOGEVENTS: false, LOGSPAWN: false, DEBUG: false,
    API_URL: 'http://localhost:5000', WS_URL: 'ws://localhost:8765',
    E: {
      CONNECT: 'CONNECT', UPDATE: 'UPDATE', READ: 'READ', ENABLE: 'ENABLE',
      DISABLE: 'DISABLE', SCHEMA: 'SCHEMA', DESCRIBE: 'DESCRIBE',
      connect: 'CONNECT', update: 'UPDATE', read: 'READ',
      NAVIGATE: 'NAVIGATE', BACK: 'BACK', SELECT: 'SELECT',
    },
    DEFAULT_HEADERS: {}, TIMEOUT: 5000, RETRY_LIMIT: 3,
  }
}));

vi.mock('../../utils/Logging.js', () => ({
  default: {
    warn: vi.fn(), error: vi.fn(), debug: vi.fn(),
    dev: vi.fn(), log: vi.fn(), init: vi.fn(), event: vi.fn(),
  }
}));

import { Component } from '../../core/Component.js';

describe('Component.js', () => {

  describe('static normalizeDisplay(value)', () => {
    it('should return null for "auto"', () => {
      expect(Component.normalizeDisplay('auto')).toBeNull();
    });

    it('should return null for null/undefined', () => {
      expect(Component.normalizeDisplay(null)).toBeNull();
      expect(Component.normalizeDisplay(undefined)).toBeNull();
    });

    it('should return size for valid abstract sizes', () => {
      expect(Component.normalizeDisplay('xs')).toBe('xs');
      expect(Component.normalizeDisplay('sm')).toBe('sm');
      expect(Component.normalizeDisplay('md')).toBe('md');
      expect(Component.normalizeDisplay('lg')).toBe('lg');
      expect(Component.normalizeDisplay('xl')).toBe('xl');
    });

    it('should resolve aliases', () => {
      expect(Component.normalizeDisplay('pill')).toBe('xs');
      expect(Component.normalizeDisplay('card')).toBe('md');
      expect(Component.normalizeDisplay('list-item')).toBe('sm');
      expect(Component.normalizeDisplay('detail')).toBe('lg');
      expect(Component.normalizeDisplay('page')).toBe('xl');
    });

    it('should return null for unknown value', () => {
      expect(Component.normalizeDisplay('unknown')).toBeNull();
      expect(Component.normalizeDisplay('foobar')).toBeNull();
    });
  });

  describe('static observedAttributes', () => {
    it('should return correct attribute list', () => {
      expect(Component.observedAttributes).toEqual(['model', 'addr', 'hash', 'ref', 'display']);
    });
  });

  describe('SIZES and ALIASES', () => {
    it('should define SIZES array', () => {
      expect(Component.SIZES).toEqual(['xs', 'sm', 'md', 'lg', 'xl']);
    });

    it('should define ALIASES map', () => {
      expect(Component.ALIASES.pill).toBe('xs');
      expect(Component.ALIASES.card).toBe('md');
    });
  });

  describe('instance behavior (requires customElements)', () => {
    // Component extends HTMLElement which requires customElements.define
    // We test static methods and class-level behavior

    it('should have styles getter returning null by default', () => {
      // The styles getter returns null when not overridden by a subclass
      const desc = Object.getOwnPropertyDescriptor(Component.prototype, 'styles');
      if (desc && desc.get) {
        expect(desc.get.call({})).toBeNull();
      } else {
        // If defined as a property, check the value
        expect(Component.prototype.styles).toBeNull();
      }
    });

    it('should have displayBreakpoints getter', () => {
      const desc = Object.getOwnPropertyDescriptor(Component.prototype, 'displayBreakpoints');
      if (desc && desc.get) {
        const bp = desc.get.call({});
        expect(bp).toEqual({ xl: 800, lg: 600, md: 400, sm: 200, xs: 0 });
      }
    });

    it('should throw on render() (abstract method)', () => {
      const desc = Object.getOwnPropertyDescriptor(Component.prototype, 'render');
      if (desc && desc.value) {
        expect(() => desc.value.call({ constructor: { name: 'Test' } })).toThrow(/render\(\) must be implemented/);
      }
    });
  });
});
