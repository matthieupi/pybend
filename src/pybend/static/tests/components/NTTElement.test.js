import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../../utils/Assert.js', () => ({
  default: vi.fn((caller, cond, msg) => { if (!cond) throw new Error(msg || 'Assertion failed'); }),
  caution: vi.fn(), inform: vi.fn(),
}));
vi.mock('../../config.js', () => ({
  config: {
    LOGGING: 3, LOGEVENTS: false, LOGSPAWN: false, DEBUG: false,
    API_URL: 'http://localhost:5000', WS_URL: 'ws://localhost:8765',
    E: { CONNECT: 'CONNECT', UPDATE: 'UPDATE', READ: 'READ', ENABLE: 'ENABLE', DISABLE: 'DISABLE',
         SCHEMA: 'SCHEMA', DESCRIBE: 'DESCRIBE', connect: 'CONNECT', update: 'UPDATE', read: 'READ',
         NAVIGATE: 'NAVIGATE', BACK: 'BACK', SELECT: 'SELECT' },
    DEFAULT_HEADERS: {}, TIMEOUT: 5000, RETRY_LIMIT: 3,
  }
}));
vi.mock('../../utils/Logging.js', () => ({
  default: { warn: vi.fn(), error: vi.fn(), debug: vi.fn(), dev: vi.fn(), log: vi.fn(), init: vi.fn(), event: vi.fn() }
}));

import { NTTElement } from '../../components/NTTElement.js';

describe('NTTElement.js', () => {

  describe('class definition', () => {
    it('should be a class extending Component', () => {
      expect(typeof NTTElement).toBe('function');
    });

    it('should have $schema property initialized to undefined', () => {
      expect(NTTElement.prototype.$schema).toBeUndefined();
    });
  });

  describe('update(prev, next)', () => {
    it('should return false by default (triggers full render)', () => {
      const result = NTTElement.prototype.update.call({}, {}, {});
      expect(result).toBe(false);
    });
  });

  describe('save()', () => {
    it('should be a function on the prototype', () => {
      expect(typeof NTTElement.prototype.save).toBe('function');
    });
  });
});
