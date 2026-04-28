import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../../utils/Assert.js', () => ({
  default: vi.fn((caller, cond, msg) => { if (!cond) throw new Error(msg); }),
  caution: vi.fn(), inform: vi.fn(),
}));
vi.mock('../../config.js', () => ({
  config: {
    LOGGING: 3, LOGEVENTS: false, DEBUG: false,
    API_URL: 'http://localhost:5000',
    E: { load: 'LOAD', update: 'UPDATE', read: 'READ', CONNECT: 'CONNECT' },
  }
}));
vi.mock('../../utils/Logging.js', () => ({
  default: { warn: vi.fn(), error: vi.fn(), debug: vi.fn(), dev: vi.fn(), log: vi.fn(), init: vi.fn(), event: vi.fn() }
}));
vi.mock('../../core/transport/HTTP.js', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    remove: vi.fn(),
    _extractValidationErrors: vi.fn(() => null),
  }
}));
vi.mock('../../core/transport/Socket.js', () => ({
  default: class FakeSocket {
    constructor(url) {
      this.url = url;
      this.ready = true;
      this.onmessage = null;
      this.send = vi.fn();
      this.connect = vi.fn();
    }
  }
}));

import { NetworkAdapter } from '../../core/transport/NetworkAdapter.js';
import HTTP from '../../core/transport/HTTP.js';
import Logging from '../../utils/Logging.js';

describe('NetworkAdapter.js', () => {

  let matrix;

  beforeEach(() => {
    vi.clearAllMocks();
    matrix = {
      has: vi.fn(() => true),
      dispatch: vi.fn(),
    };
  });

  describe('constructor(matrix, url, mode)', () => {
    it('should default to http mode', () => {
      const adapter = new NetworkAdapter(matrix);
      expect(adapter.mode).toBe('http');
    });

    it('should use config.API_URL when no url provided', () => {
      const adapter = new NetworkAdapter(matrix);
      expect(adapter.url).toBe('http://localhost:5000');
    });

    it('should use provided url', () => {
      const adapter = new NetworkAdapter(matrix, 'http://example.com');
      expect(adapter.url).toBe('http://example.com');
    });

    it('should store matrix reference', () => {
      const adapter = new NetworkAdapter(matrix);
      expect(adapter.matrix).toBe(matrix);
    });

    it('should set socket to null in http mode', () => {
      const adapter = new NetworkAdapter(matrix);
      expect(adapter.socket).toBeNull();
    });

    it('should bind send method', () => {
      const adapter = new NetworkAdapter(matrix);
      expect(typeof adapter.send).toBe('function');
    });
  });

  describe('httpCallback(event, response)', () => {
    it('should dispatch reply with swapped source and target', () => {
      const adapter = new NetworkAdapter(matrix);
      const event = {
        name: 'READ', source: 'actor-1', target: 'http://localhost:5000/products',
        data: null, meta: {},
      };
      adapter.httpCallback(event, { id: 1 });

      const reply = matrix.dispatch.mock.calls[0][0];
      expect(reply.source).toBe('http://localhost:5000/products');
      expect(reply.target).toBe('actor-1');
    });

    it('should not mutate the original event', () => {
      const adapter = new NetworkAdapter(matrix);
      const event = {
        name: 'READ', source: 'actor-1', target: 'http://localhost:5000/products',
        data: null, meta: {},
      };
      adapter.httpCallback(event, { id: 1 });
      expect(event.source).toBe('actor-1');
      expect(event.target).toBe('http://localhost:5000/products');
      expect(event.data).toBe(null);
    });

    it('should set reply data to response', () => {
      const adapter = new NetworkAdapter(matrix);
      const event = {
        name: 'READ', source: 'actor-1', target: 'http://localhost:5000/products',
        data: null, meta: {},
      };
      const response = { id: 1, name: 'Product' };
      adapter.httpCallback(event, response);
      const reply = matrix.dispatch.mock.calls[0][0];
      expect(reply.data).toBe(response);
    });

    it('should use meta.inbox as reply name when provided', () => {
      const adapter = new NetworkAdapter(matrix);
      const event = {
        name: 'READ', source: 'actor-1', target: 'http://localhost:5000/products',
        data: null, meta: { inbox: 'DESCRIBE' },
      };
      adapter.httpCallback(event, {});
      const reply = matrix.dispatch.mock.calls[0][0];
      expect(reply.name).toBe('DESCRIBE');
    });

    it('should keep event.name in reply when no meta.inbox', () => {
      const adapter = new NetworkAdapter(matrix);
      const event = {
        name: 'READ', source: 'actor-1', target: 'http://localhost:5000/products',
        data: null, meta: {},
      };
      adapter.httpCallback(event, {});
      const reply = matrix.dispatch.mock.calls[0][0];
      expect(reply.name).toBe('READ');
    });

    it('should dispatch reply via matrix', () => {
      const adapter = new NetworkAdapter(matrix);
      const event = {
        name: 'READ', source: 'actor-1', target: 'http://localhost:5000/products',
        data: null, meta: {},
      };
      adapter.httpCallback(event, {});
      expect(matrix.dispatch).toHaveBeenCalledTimes(1);
      const reply = matrix.dispatch.mock.calls[0][0];
      expect(reply.source).toBe('http://localhost:5000/products');
      expect(reply.target).toBe('actor-1');
      expect(reply.name).toBe('READ');
    });

    it('should include timestamp in reply', () => {
      const adapter = new NetworkAdapter(matrix);
      const event = {
        name: 'READ', source: 'actor-1', target: 'http://localhost:5000/products',
        data: null, meta: {}, timestamp: Date.now(),
      };
      adapter.httpCallback(event, {});
      const reply = matrix.dispatch.mock.calls[0][0];
      expect(reply.timestamp).toBeDefined();
      expect(typeof reply.timestamp).toBe('number');
    });

    it('should preserve event id in reply', () => {
      const adapter = new NetworkAdapter(matrix);
      const event = {
        name: 'READ', id: 'evt-12345', source: 'actor-1', target: 'http://localhost:5000/products',
        data: null, meta: {},
      };
      adapter.httpCallback(event, {});
      const reply = matrix.dispatch.mock.calls[0][0];
      expect(reply.id).toBe('evt-12345');
    });

    it('should preserve meta in reply', () => {
      const adapter = new NetworkAdapter(matrix);
      const event = {
        name: 'READ', source: 'actor-1', target: 'http://localhost:5000/products',
        data: null, meta: { foo: 'bar', baz: 123 },
      };
      adapter.httpCallback(event, {});
      const reply = matrix.dispatch.mock.calls[0][0];
      expect(reply.meta.foo).toBe('bar');
      expect(reply.meta.baz).toBe(123);
    });
  });

  describe('onError(event, response)', () => {
    it('should log error via Logging.error', () => {
      const adapter = new NetworkAdapter(matrix);
      const event = {
        name: 'READ', id: '123', source: 'actor-1', target: 'http://localhost:5000/products',
        data: null, meta: {}, timestamp: Date.now(),
      };
      // onError calls this.emit which will throw because callback is undefined,
      // but we can still verify the log
      try {
        adapter.onError(event, { error: 'not found' });
      } catch (e) {
        // emit will throw due to assert on undefined callback
      }
      expect(Logging.error).toHaveBeenCalled();
      const firstCallArgs = Logging.error.mock.calls[0];
      expect(firstCallArgs[0]).toContain('NetworkAdapter');
    });

    it('should dispatch ERROR TX through matrix', () => {
      const adapter = new NetworkAdapter(matrix);
      const event = {
        name: 'READ', id: 'err-123', source: 'actor-1', target: 'http://localhost:5000/products',
        data: null, meta: {}, timestamp: Date.now(),
      };
      const response = { error: 'not found', status: 404 };

      // onError calls this.emit which will throw, but matrix.dispatch should be called first
      try {
        adapter.onError(event, response);
      } catch (e) {
        // emit will throw due to assert on undefined callback
      }

      expect(matrix.dispatch).toHaveBeenCalledTimes(1);
      const errorTx = matrix.dispatch.mock.calls[0][0];
      expect(errorTx.name).toBe('ERROR');
      expect(errorTx.source).toBe('http://localhost:5000/products');
      expect(errorTx.target).toBe('actor-1');
      expect(errorTx.data).toBe(event); // data is the original event
      expect(errorTx.id).toBe('err-123');
      expect(errorTx.meta.error).toBe(true);
      expect(errorTx.meta.remote).toBe(true);
      expect(errorTx.meta.response).toBe(response); // response in meta
    });
  });

  describe('pull(target, callback)', () => {
    it('should call send with a read event', () => {
      const adapter = new NetworkAdapter(matrix);
      const sendSpy = vi.spyOn(adapter, 'send');
      adapter.pull('http://localhost:5000/products');
      expect(sendSpy).toHaveBeenCalled();
      const sentEvent = sendSpy.mock.calls[0][0];
      expect(sentEvent.name).toBe('read');
      expect(sentEvent.target).toBe('http://localhost:5000/products');
      expect(sentEvent.meta.remote).toBe(true);
    });

    it('should set source to remote', () => {
      const adapter = new NetworkAdapter(matrix);
      const sendSpy = vi.spyOn(adapter, 'send');
      adapter.pull('http://localhost:5000/products');
      const sentEvent = sendSpy.mock.calls[0][0];
      expect(sentEvent.source).toBe('remote');
    });

    it('should accept optional callback', () => {
      const adapter = new NetworkAdapter(matrix);
      const sendSpy = vi.spyOn(adapter, 'send');
      const cb = vi.fn();
      adapter.pull('http://localhost:5000/products', cb);
      expect(sendSpy).toHaveBeenCalled();
    });
  });

  describe('send(event) — HTTP mode', () => {
    it('should route READ events to HTTP.get', () => {
      const adapter = new NetworkAdapter(matrix);
      adapter.send({
        name: 'READ', source: 'actor-1', target: 'http://localhost:5000/products',
        data: null, meta: {}, id: '1', timestamp: Date.now(),
      });
      expect(HTTP.get).toHaveBeenCalled();
      const [url] = HTTP.get.mock.calls[0];
      expect(url).toBe('http://localhost:5000/products');
    });

    it('should append query params for READ with data object', () => {
      const adapter = new NetworkAdapter(matrix);
      adapter.send({
        name: 'READ', source: 'actor-1', target: 'http://localhost:5000/products',
        data: { limit: 20, offset: 0 }, meta: {}, id: '1', timestamp: Date.now(),
      });
      expect(HTTP.get).toHaveBeenCalled();
      const [url] = HTTP.get.mock.calls[0];
      expect(url).toContain('limit=20');
      expect(url).toContain('offset=0');
    });

    it('should not append params for READ with null data', () => {
      const adapter = new NetworkAdapter(matrix);
      adapter.send({
        name: 'READ', source: 'actor-1', target: 'http://localhost:5000/products',
        data: null, meta: {}, id: '1', timestamp: Date.now(),
      });
      const [url] = HTTP.get.mock.calls[0];
      expect(url).toBe('http://localhost:5000/products');
    });

    it('should route SCHEMA events to HTTP.get', () => {
      const adapter = new NetworkAdapter(matrix);
      adapter.send({
        name: 'SCHEMA', source: 'actor-1', target: 'http://localhost:5000/Product',
        data: null, meta: {}, id: '1', timestamp: Date.now(),
      });
      expect(HTTP.get).toHaveBeenCalled();
      const [url] = HTTP.get.mock.calls[0];
      expect(url).toBe('http://localhost:5000/Product');
    });

    it('should route CREATE events to HTTP.post', () => {
      const adapter = new NetworkAdapter(matrix);
      const payload = { name: 'New Product' };
      adapter.send({
        name: 'CREATE', source: 'actor-1', target: 'http://localhost:5000/products',
        data: payload, meta: {}, id: '1', timestamp: Date.now(),
      });
      expect(HTTP.post).toHaveBeenCalled();
      const [url, data] = HTTP.post.mock.calls[0];
      expect(url).toBe('http://localhost:5000/products');
      expect(data).toBe(payload);
    });

    it('should route UPDATE events to HTTP.put', () => {
      const adapter = new NetworkAdapter(matrix);
      const payload = { name: 'Updated' };
      adapter.send({
        name: 'UPDATE', source: 'actor-1', target: 'http://localhost:5000/products/1',
        data: payload, meta: {}, id: '1', timestamp: Date.now(),
      });
      expect(HTTP.put).toHaveBeenCalled();
      const [url, data] = HTTP.put.mock.calls[0];
      expect(url).toBe('http://localhost:5000/products/1');
      expect(data).toBe(payload);
    });

    it('should route DELETE events to HTTP.remove', () => {
      const adapter = new NetworkAdapter(matrix);
      adapter.send({
        name: 'DELETE', source: 'actor-1', target: 'http://localhost:5000/products/1',
        data: null, meta: {}, id: '1', timestamp: Date.now(),
      });
      expect(HTTP.remove).toHaveBeenCalled();
      const [url] = HTTP.remove.mock.calls[0];
      expect(url).toBe('http://localhost:5000/products/1');
    });

    it('should route custom method names to HTTP.post with /{target}/{method}', () => {
      const adapter = new NetworkAdapter(matrix);
      adapter.send({
        name: 'favorite', source: 'actor-1', target: 'http://localhost:5000/products/1',
        data: {}, meta: {}, id: '1', timestamp: Date.now(),
      });
      expect(HTTP.post).toHaveBeenCalled();
      const [url] = HTTP.post.mock.calls[0];
      expect(url).toBe('http://localhost:5000/products/1/favorite');
    });

    it('should handle case-insensitive event names', () => {
      const adapter = new NetworkAdapter(matrix);
      adapter.send({
        name: 'read', source: 'actor-1', target: 'http://localhost:5000/products',
        data: null, meta: {}, id: '1', timestamp: Date.now(),
      });
      expect(HTTP.get).toHaveBeenCalled();
    });

    it('should skip null values in READ query params', () => {
      const adapter = new NetworkAdapter(matrix);
      adapter.send({
        name: 'READ', source: 'actor-1', target: 'http://localhost:5000/products',
        data: { limit: 20, offset: null }, meta: {}, id: '1', timestamp: Date.now(),
      });
      const [url] = HTTP.get.mock.calls[0];
      expect(url).toContain('limit=20');
      expect(url).not.toContain('offset');
    });
  });

  describe('send(event) — WS mode', () => {
    it('should delegate to socket.send when in ws mode with socket available', async () => {
      const adapter = new NetworkAdapter(matrix, '', 'ws');
      // Wait for dynamic import to resolve
      await vi.waitFor(() => expect(adapter.socket).toBeTruthy());
      const sendSpy = vi.spyOn(adapter.socket, 'send');
      adapter.send({
        name: 'READ', source: 'actor-1', target: 'http://localhost:5000/products',
        data: null, meta: {}, id: '1', timestamp: Date.now(),
      });
      expect(adapter.socket.connect).toHaveBeenCalled();
      expect(sendSpy).toHaveBeenCalled();
    });

    it('should dispatch websocket messages through matrix', async () => {
      const adapter = new NetworkAdapter(matrix, '', 'ws');
      await vi.waitFor(() => expect(adapter.socket).toBeTruthy());

      const message = { name: 'UPDATE', target: 'actor-1', data: { ok: true } };
      adapter.socket.onmessage(message);

      expect(matrix.dispatch).toHaveBeenCalledWith(message);
    });
  });
});
