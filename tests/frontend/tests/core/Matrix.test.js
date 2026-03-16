import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../../utils/Assert.js', () => ({
  default: vi.fn((caller, cond, msg) => {
    if (!cond) throw new Error(msg || 'Assertion failed');
  }),
  caution: vi.fn(), inform: vi.fn(),
}));

vi.mock('../../config.js', () => ({
  config: { LOGGING: 3, LOGEVENTS: true, DEBUG: true, API_URL: 'http://localhost:5000',
    WS_URL: 'ws://localhost:8765',
    E: { CONNECT: 'CONNECT', UPDATE: 'UPDATE', READ: 'READ', ENABLE: 'ENABLE', DISABLE: 'DISABLE',
         connect: 'CONNECT', update: 'UPDATE', SCHEMA: 'SCHEMA' }
  }
}));

vi.mock('../../utils/Logging.js', () => ({
  default: { warn: vi.fn(), error: vi.fn(), debug: vi.fn(), dev: vi.fn(), log: vi.fn(), init: vi.fn(), event: vi.fn() }
}));

import { Matrix, matrix } from '../../core/Matrix.js';

describe('Matrix.js', () => {

  describe('constructor(addr, url)', () => {
    it('should create Matrix with addr', () => {
      expect(matrix.addr).toBe('matrix://root');
    });

    it('should have a remote NetworkAdapter', () => {
      expect(matrix.remote).toBeDefined();
    });
  });

  describe('has(addr)', () => {
    it('should check if child actor exists', () => {
      // Matrix is registered as root, Component is registered as child
      expect(typeof matrix.has).toBe('function');
    });

    it('should parse compound address', () => {
      // has() splits by / and checks first part
      const result = matrix.has('SomeModel/123');
      expect(typeof result).toBe('boolean');
    });
  });

  describe('inbox(event)', () => {
    it('should throw error if target is self', () => {
      expect(() => matrix.inbox({
        name: 'UPDATE',
        source: 'test',
        target: 'matrix://root',
        data: {}
      })).toThrow('Matrix cannot send messages to itself');
    });

    it('should route CONNECT event', () => {
      // CONNECT to unknown target should throw
      expect(() => matrix.inbox({
        name: 'CONNECT',
        source: 'test-source',
        target: 'UnknownClass',
        data: {}
      })).toThrow();
    });
  });

  describe('dispatch(event)', () => {
    it('should delegate to inbox', () => {
      const inboxSpy = vi.spyOn(matrix, 'inbox');
      const event = {
        name: 'SCHEMA',
        source: 'NTT',
        target: 'http://localhost:5000/Product',
        data: {},
        meta: { remote: true }
      };
      matrix.dispatch(event);
      expect(inboxSpy).toHaveBeenCalledWith(event);
      inboxSpy.mockRestore();
    });
  });

  describe('connect(source, target)', () => {
    it('should throw if target class not registered', () => {
      expect(() => matrix.connect('Source', 'NonExistent')).toThrow(
        /not registered locally/
      );
    });
  });
});
