import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('../../utils/Logging.js', () => ({
  default: { warn: vi.fn(), error: vi.fn(), debug: vi.fn(), dev: vi.fn(), log: vi.fn(), init: vi.fn(), event: vi.fn() }
}));

import Socket from '../../core/transport/Socket.js';
import Logging from '../../utils/Logging.js';

describe('Socket.js', () => {
  let mockWs;

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();

    mockWs = {
      send: vi.fn(),
      close: vi.fn(),
      readyState: 1,
      onopen: null,
      onclose: null,
      onmessage: null,
      onerror: null,
    };

    global.WebSocket = vi.fn(() => mockWs);
    global.WebSocket.OPEN = 1;
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('constructor(url)', () => {
    it('stores url and disconnected state', () => {
      const sock = new Socket('ws://localhost:5000/ws');
      expect(sock.url).toBe('ws://localhost:5000/ws');
      expect(sock.ws).toBeNull();
      expect(sock.ready).toBe(false);
      expect(sock.onmessage).toBeNull();
      expect(sock._queue).toEqual([]);
    });
  });

  describe('connect(token)', () => {
    it('creates websocket with token query parameter', () => {
      const sock = new Socket('ws://localhost:5000/ws');
      sock.connect('abc123');
      expect(global.WebSocket).toHaveBeenCalledWith('ws://localhost:5000/ws?token=abc123');
      expect(sock.ws).toBe(mockWs);
    });

    it('creates websocket without token when omitted', () => {
      const sock = new Socket('ws://localhost:5000/ws');
      sock.connect();
      expect(global.WebSocket).toHaveBeenCalledWith('ws://localhost:5000/ws');
    });

    it('sets ready on open and flushes queued payloads', () => {
      const sock = new Socket('ws://localhost:5000/ws');
      sock.send({ name: 'READ', id: 1 });
      sock.send({ repr: () => ({ name: 'UPDATE', id: 2 }) });
      expect(sock._queue).toHaveLength(2);

      sock.connect();
      mockWs.onopen();

      expect(sock.ready).toBe(true);
      expect(mockWs.send).toHaveBeenNthCalledWith(1, JSON.stringify({ name: 'READ', id: 1 }));
      expect(mockWs.send).toHaveBeenNthCalledWith(2, JSON.stringify({ name: 'UPDATE', id: 2 }));
      expect(sock._queue).toEqual([]);
    });

    it('forwards parsed non-heartbeat messages to onmessage callback', () => {
      const sock = new Socket('ws://localhost:5000/ws');
      const cb = vi.fn();
      sock.onmessage = cb;

      sock.connect();
      mockWs.onmessage({ data: JSON.stringify({ name: 'READ', data: { id: 1 } }) });

      expect(cb).toHaveBeenCalledWith({ name: 'READ', data: { id: 1 } });
    });

    it('ignores heartbeat messages', () => {
      const sock = new Socket('ws://localhost:5000/ws');
      const cb = vi.fn();
      sock.onmessage = cb;

      sock.connect();
      mockWs.onmessage({ data: JSON.stringify({ heartbeat: true }) });

      expect(cb).not.toHaveBeenCalled();
    });

    it('logs invalid JSON parse errors', () => {
      const sock = new Socket('ws://localhost:5000/ws');
      sock.connect();

      mockWs.onmessage({ data: 'not-json' });

      expect(Logging.error).toHaveBeenCalled();
    });

    it('schedules reconnect on close when not manually closed', () => {
      const sock = new Socket('ws://localhost:5000/ws');
      sock.connect('abc');
      mockWs.onclose({ code: 1006 });

      expect(sock.ready).toBe(false);

      vi.advanceTimersByTime(2000);
      expect(global.WebSocket).toHaveBeenCalledTimes(2);
      expect(global.WebSocket).toHaveBeenLastCalledWith('ws://localhost:5000/ws?token=abc');
    });

    it('logs websocket construction failure and schedules reconnect', () => {
      global.WebSocket = vi.fn(() => { throw new Error('Connection refused'); });
      global.WebSocket.OPEN = 1;

      const sock = new Socket('ws://localhost:5000/ws');
      sock.connect();

      expect(Logging.error).toHaveBeenCalled();
      vi.advanceTimersByTime(2000);
      expect(global.WebSocket).toHaveBeenCalledTimes(2);
    });
  });

  describe('send(tx)', () => {
    it('queues payload while disconnected', () => {
      const sock = new Socket('ws://localhost:5000/ws');
      sock.send({ name: 'READ', id: 1 });

      expect(sock._queue).toEqual([{ name: 'READ', id: 1 }]);
      expect(mockWs.send).not.toHaveBeenCalled();
    });

    it('serializes repr() when connected', () => {
      const sock = new Socket('ws://localhost:5000/ws');
      sock.connect();
      mockWs.onopen();

      sock.send({ repr: () => ({ name: 'READ', id: 1 }) });

      expect(mockWs.send).toHaveBeenCalledWith(JSON.stringify({ name: 'READ', id: 1 }));
    });

    it('queues payload if websocket exists but is not open', () => {
      const sock = new Socket('ws://localhost:5000/ws');
      sock.connect();
      sock.ready = true;
      mockWs.readyState = 0;

      sock.send({ name: 'READ', id: 1 });

      expect(sock._queue).toEqual([{ name: 'READ', id: 1 }]);
      expect(mockWs.send).not.toHaveBeenCalled();
    });
  });

  describe('close()', () => {
    it('marks socket closed and closes websocket', () => {
      const sock = new Socket('ws://localhost:5000/ws');
      sock.connect();
      mockWs.onopen();

      sock.close();

      expect(sock.ready).toBe(false);
      expect(sock._closed).toBe(true);
      expect(mockWs.close).toHaveBeenCalledWith(1000, 'Client closing');
      expect(sock.ws).toBeNull();
    });

    it('prevents reconnect after manual close', () => {
      const sock = new Socket('ws://localhost:5000/ws');
      sock.connect('abc');
      sock.close();

      mockWs.onclose({ code: 1006 });
      vi.advanceTimersByTime(2000);

      expect(global.WebSocket).toHaveBeenCalledTimes(1);
    });
  });

  describe('heartbeat behavior', () => {
    it('sends heartbeat every 30s while connected', () => {
      const sock = new Socket('ws://localhost:5000/ws');
      sock.connect();
      mockWs.onopen();
      mockWs.send.mockClear();

      vi.advanceTimersByTime(30000);

      expect(mockWs.send).toHaveBeenCalledWith(JSON.stringify({ heartbeat: true }));
    });

    it('stops heartbeat after close', () => {
      const sock = new Socket('ws://localhost:5000/ws');
      sock.connect();
      mockWs.onopen();
      sock.close();
      mockWs.send.mockClear();

      vi.advanceTimersByTime(30000);

      expect(mockWs.send).not.toHaveBeenCalled();
    });
  });
});
