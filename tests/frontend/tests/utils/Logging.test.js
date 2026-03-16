import { describe, it, expect, vi, beforeEach } from 'vitest';
import Logging from '../../utils/Logging.js';

describe('Logging.js', () => {

  beforeEach(() => {
    Logging.clear();
    // Remove all listeners
    const listeners = [];
    // We can't directly access #listeners, but clear() notifies them with undefined entry
  });

  describe('static get size', () => {
    it('should return 0 when no entries', () => {
      expect(Logging.size).toBe(0);
    });

    it('should increment after logging', () => {
      Logging.error('test error');
      expect(Logging.size).toBe(1);
    });
  });

  describe('static getEntries(filter)', () => {
    it('should return all entries when no filter', () => {
      Logging.error('e1');
      Logging.warn('w1');
      const entries = Logging.getEntries();
      expect(entries.length).toBe(2);
    });

    it('should return filtered entries by level', () => {
      Logging.error('e1');
      Logging.warn('w1');
      Logging.error('e2');
      const errors = Logging.getEntries('error');
      expect(errors.length).toBe(2);
      expect(errors.every(e => e.level === 'error')).toBe(true);
    });

    it('should return empty array when filter matches nothing', () => {
      Logging.error('e1');
      const devs = Logging.getEntries('dev');
      expect(devs.length).toBe(0);
    });

    it('should return a copy (not the internal array)', () => {
      Logging.error('e1');
      const entries = Logging.getEntries();
      entries.push({level: 'fake'});
      expect(Logging.size).toBe(1); // Internal array not modified
    });
  });

  describe('static clear()', () => {
    it('should clear all entries', () => {
      Logging.error('e1');
      Logging.warn('w1');
      expect(Logging.size).toBe(2);
      Logging.clear();
      expect(Logging.size).toBe(0);
    });

    it('should notify listeners with no entry argument', () => {
      const listener = vi.fn();
      Logging.addListener(listener);
      Logging.clear();
      expect(listener).toHaveBeenCalledWith();
      Logging.removeListener(listener);
    });
  });

  describe('static addListener / removeListener', () => {
    it('should add and call listener on new entry', () => {
      const listener = vi.fn();
      Logging.addListener(listener);
      Logging.error('test');
      expect(listener).toHaveBeenCalledTimes(1);
      const entry = listener.mock.calls[0][0];
      expect(entry.level).toBe('error');
      expect(entry.message).toBe('test');
      Logging.removeListener(listener);
    });

    it('should remove listener and no longer call it', () => {
      const listener = vi.fn();
      Logging.addListener(listener);
      Logging.removeListener(listener);
      Logging.error('test');
      expect(listener).not.toHaveBeenCalled();
    });

    it('should support multiple listeners', () => {
      const l1 = vi.fn();
      const l2 = vi.fn();
      Logging.addListener(l1);
      Logging.addListener(l2);
      Logging.error('test');
      expect(l1).toHaveBeenCalledTimes(1);
      expect(l2).toHaveBeenCalledTimes(1);
      Logging.removeListener(l1);
      Logging.removeListener(l2);
    });
  });

  describe('static #push (MAX_ENTRIES enforcement)', () => {
    it('should enforce MAX_ENTRIES (500) by dropping oldest', () => {
      for (let i = 0; i < 505; i++) {
        Logging.error(`entry-${i}`);
      }
      expect(Logging.size).toBe(500);
      const entries = Logging.getEntries();
      expect(entries[0].message).toBe('entry-5'); // First 5 dropped
    });
  });

  describe('level-specific methods', () => {
    it('static init() should push info entry when LOGGING >= 3', () => {
      Logging.init('init msg', {data: 1});
      const entries = Logging.getEntries('info');
      expect(entries.length).toBeGreaterThanOrEqual(1);
      const last = entries[entries.length - 1];
      expect(last.message).toBe('init msg');
    });

    it('static log() should push info entry', () => {
      Logging.log('log msg', 'detail');
      const entries = Logging.getEntries('info');
      expect(entries.some(e => e.message === 'log msg')).toBe(true);
    });

    it('static dev() should push dev entry when LOGGING >= 4', () => {
      // config.LOGGING is 3, so dev requires >= 4 and won't log
      Logging.dev('dev msg');
      const entries = Logging.getEntries('dev');
      // LOGGING is 3, so dev entries should NOT be logged
      expect(entries.length).toBe(0);
    });

    it('static event() should push event entry when LOGEVENTS is true', () => {
      const tx = { name: 'UPDATE', source: 'A', target: 'B', data: {} };
      Logging.event(tx);
      const entries = Logging.getEntries('event');
      expect(entries.length).toBeGreaterThanOrEqual(1);
      expect(entries[entries.length - 1].message).toContain('UPDATE');
    });

    it('static event() should format TX with name/source/target', () => {
      const tx = { name: 'READ', source: 'Comp1', target: 'http://api/products' };
      Logging.event(tx);
      const entries = Logging.getEntries('event');
      const last = entries[entries.length - 1];
      expect(last.message).toContain('READ');
      expect(last.message).toContain('Comp1');
      expect(last.message).toContain('http://api/products');
    });

    it('static event() should handle TX without name (toString fallback)', () => {
      Logging.event('raw string event');
      const entries = Logging.getEntries('event');
      expect(entries.length).toBeGreaterThanOrEqual(1);
    });

    it('static debug() should push debug entry when DEBUG is true', () => {
      Logging.debug('debug msg', 'detail');
      const entries = Logging.getEntries('debug');
      expect(entries.some(e => e.message === 'debug msg')).toBe(true);
    });

    it('static warn() should push warn entry when LOGGING >= 2', () => {
      Logging.warn('warn msg', 'detail');
      const entries = Logging.getEntries('warn');
      expect(entries.some(e => e.message === 'warn msg')).toBe(true);
    });

    it('static error() should push error entry when LOGGING >= 1', () => {
      Logging.error('error msg', 'detail');
      const entries = Logging.getEntries('error');
      expect(entries.some(e => e.message === 'error msg')).toBe(true);
    });
  });

  describe('entry structure', () => {
    it('should have level, message, detail, and timestamp', () => {
      Logging.error('test', {extra: true});
      const entries = Logging.getEntries();
      const entry = entries[entries.length - 1];
      expect(entry).toHaveProperty('level', 'error');
      expect(entry).toHaveProperty('message', 'test');
      expect(entry).toHaveProperty('detail');
      expect(entry.detail).toEqual({extra: true});
      expect(entry).toHaveProperty('timestamp');
      expect(typeof entry.timestamp).toBe('number');
    });
  });
});
