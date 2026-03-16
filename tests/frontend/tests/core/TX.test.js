import { describe, it, expect, vi } from 'vitest';

// Mock dependencies before import
vi.mock('../../utils/Assert.js', () => ({
  default: vi.fn((caller, cond, msg) => {
    if (!cond) throw new Error(msg || 'Assertion failed');
  }),
  caution: vi.fn(),
  inform: vi.fn(),
}));

vi.mock('../../config.js', () => ({
  config: {
    LOGGING: 3, LOGEVENTS: true, DEBUG: true,
    API_URL: 'http://localhost:5000',
    E: { CONNECT: 'CONNECT', UPDATE: 'UPDATE', READ: 'READ', ENABLE: 'ENABLE', DISABLE: 'DISABLE' }
  }
}));

vi.mock('../../utils/Logging.js', () => ({
  default: { warn: vi.fn(), error: vi.fn(), debug: vi.fn(), dev: vi.fn(), log: vi.fn(), init: vi.fn(), event: vi.fn() }
}));

import TX from '../../core/TX.js';

describe('TX.js', () => {

  describe('constructor(event)', () => {
    it('should create TX from object with all fields', () => {
      const tx = new TX({
        name: 'UPDATE',
        source: 'A',
        target: 'B',
        data: { foo: 1 },
        meta: { remote: true },
        timestamp: 12345
      });
      expect(tx.name).toBe('UPDATE');
      expect(tx.source).toBe('A');
      expect(tx.target).toBe('B');
      expect(tx.data).toEqual({ foo: 1 });
      expect(tx.meta).toEqual({ remote: true });
      expect(tx.tst).toBe(12345);
    });

    it('should default data to empty object', () => {
      const tx = new TX({ name: 'READ', source: 'A', target: 'B' });
      expect(tx.data).toEqual({});
    });

    it('should default meta to empty object', () => {
      const tx = new TX({ name: 'READ', source: 'A', target: 'B' });
      expect(tx.meta).toEqual({});
    });

    it('should default timestamp to Date.now()', () => {
      const before = Date.now();
      const tx = new TX({ name: 'READ', source: 'A', target: 'B' });
      const after = Date.now();
      expect(tx.tst).toBeGreaterThanOrEqual(before);
      expect(tx.tst).toBeLessThanOrEqual(after);
    });

    it('should parse JSON string event', () => {
      const json = JSON.stringify({
        name: 'SCHEMA',
        source: 'NTT',
        target: 'http://localhost:5000/Product',
        data: {},
        meta: { remote: true },
      });
      const tx = new TX(json);
      expect(tx.name).toBe('SCHEMA');
      expect(tx.source).toBe('NTT');
      expect(tx.target).toBe('http://localhost:5000/Product');
    });

    it('should throw on invalid JSON string', () => {
      expect(() => new TX('not-json')).toThrow();
    });

    it('should initialize _hash to null', () => {
      const tx = new TX({ name: 'X', source: 'A', target: 'B' });
      expect(tx._hash).toBeNull();
    });
  });

  describe('hash (getter)', () => {
    it('should compute on first access', () => {
      const tx = new TX({ name: 'X', source: 'A', target: 'B', data: { x: 1 } });
      expect(tx._hash).toBeNull();
      const hash = tx.hash;
      expect(hash).toBeTruthy();
      expect(typeof hash).toBe('string');
    });

    it('should cache result on subsequent access', () => {
      const tx = new TX({ name: 'Y', source: 'A', target: 'B' });
      const hash1 = tx.hash;
      const hash2 = tx.hash;
      expect(hash1).toBe(hash2);
    });
  });

  describe('repr()', () => {
    it('should return object with all TX fields', () => {
      const tx = new TX({
        name: 'UPDATE',
        source: 'A',
        target: 'B',
        data: { x: 1 },
        meta: { remote: true },
        timestamp: 99
      });
      const r = tx.repr();
      expect(r.name).toBe('UPDATE');
      expect(r.source).toBe('A');
      expect(r.target).toBe('B');
      expect(r.data).toEqual({ x: 1 });
      expect(r.meta).toEqual({ remote: true });
      expect(r.tst).toBe(99);
    });

    it('should include hash (null if not computed)', () => {
      const tx = new TX({ name: 'X', source: 'A', target: 'B' });
      const r = tx.repr();
      expect(r.hash).toBeNull();
    });
  });

  describe('str()', () => {
    it('should return JSON string of repr', () => {
      const tx = new TX({ name: 'READ', source: 'X', target: 'Y', data: { a: 1 } });
      const s = tx.str();
      const parsed = JSON.parse(s);
      expect(parsed.name).toBe('READ');
      expect(parsed.source).toBe('X');
      expect(parsed.target).toBe('Y');
      expect(parsed.data).toEqual({ a: 1 });
    });
  });

  describe('static fromString(str)', () => {
    it('should parse JSON string to TX', () => {
      const json = JSON.stringify({
        name: 'UPDATE',
        source: 'A',
        target: 'B',
        data: { k: 'v' },
        meta: { inbox: 'UPDATE' },
        timestamp: 123
      });
      const tx = TX.fromString(json);
      expect(tx).toBeInstanceOf(TX);
      expect(tx.name).toBe('UPDATE');
      expect(tx.source).toBe('A');
      expect(tx.target).toBe('B');
    });

    it('should throw on invalid JSON', () => {
      expect(() => TX.fromString('not valid json')).toThrow();
    });

    it('should default meta to empty object', () => {
      const json = JSON.stringify({ name: 'X', source: 'A', target: 'B' });
      const tx = TX.fromString(json);
      expect(tx.meta).toEqual({});
    });
  });
});
