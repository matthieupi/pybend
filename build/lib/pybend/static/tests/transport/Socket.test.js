import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('../../utils/Logging.js', () => ({
  default: { warn: vi.fn(), error: vi.fn(), debug: vi.fn(), dev: vi.fn(), log: vi.fn(), init: vi.fn(), event: vi.fn() }
}));

// SocketEvent is used in Socket.js but not defined there — provide a global stub
class SocketEvent {
  constructor(name, type, source, target, data) {
    this.name = name;
    this.type = type;
    this.source = source;
    this.target = target;
    this.data = data;
  }
  static fromString(str) {
    try {
      const parsed = JSON.parse(str);
      return new SocketEvent(parsed.name, parsed.type, parsed.source, parsed.target, parsed.data);
    } catch (e) {
      return new SocketEvent('unknown', 'unknown', '', '', {});
    }
  }
  toString() { return JSON.stringify(this); }
}
globalThis.SocketEvent = SocketEvent;

import Socket from '../../core/transport/Socket.js';
import Logging from '../../utils/Logging.js';

describe('Socket.js', () => {

  let mockWs;

  beforeEach(() => {
    vi.clearAllMocks();
    // Reset Socket statics
    Socket.resources = {};
    Socket.defaultSocket = undefined;

    // Reset global WebSocket mock to capture instantiation
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

    // Prevent actual intervals
    vi.useFakeTimers();

    // Provide window.success, window.warn etc. that Socket.js calls
    window.success = vi.fn();
    window.warn = vi.fn();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('constructor(url, targets, ttl)', () => {
    it('should set url', () => {
      const sock = new Socket('localhost:8765');
      expect(sock.url).toBe('localhost:8765');
    });

    it('should set state to CONNECTING', () => {
      const sock = new Socket('localhost:8765');
      // connect() sets state to CONNECTING
      expect(sock.state).toBe('CONNECTING');
    });

    it('should set default ttl to 1000', () => {
      const sock = new Socket('localhost:8765');
      expect(sock.ttl).toBe(1000);
    });

    it('should accept custom ttl', () => {
      const sock = new Socket('localhost:8765', {}, 5000);
      expect(sock.ttl).toBe(5000);
    });

    it('should set retries to 0', () => {
      const sock = new Socket('localhost:8765');
      expect(sock.retries).toBe(0);
    });

    it('should set isDisabled to true', () => {
      const sock = new Socket('localhost:8765');
      expect(sock.isDisabled).toBe(true);
    });

    it('should initialize empty queue', () => {
      const sock = new Socket('localhost:8765');
      expect(sock.queue).toEqual([]);
    });

    it('should register in Socket.resources', () => {
      const sock = new Socket('localhost:8765');
      expect(Socket.resources['localhost:8765']).toBe(sock);
    });

    it('should set itself as defaultSocket', () => {
      const sock = new Socket('localhost:8765');
      expect(Socket.defaultSocket).toBe(sock);
    });

    it('should create WebSocket connection', () => {
      const sock = new Socket('localhost:8765');
      expect(global.WebSocket).toHaveBeenCalledWith('ws://localhost:8765');
    });

    it('should store targets', () => {
      const targets = { myTarget: vi.fn() };
      const sock = new Socket('localhost:8765', targets);
      expect(sock.targets).toBe(targets);
    });
  });

  describe('static register(name, socket)', () => {
    it('should add socket to resources', () => {
      const fakeSock = { url: 'test' };
      Socket.register('test-sock', fakeSock);
      expect(Socket.resources['test-sock']).toBe(fakeSock);
    });

    it('should warn on overwrite', () => {
      Socket.resources['existing'] = {};
      Socket.register('existing', {});
      expect(Logging.warn).toHaveBeenCalled();
    });
  });

  describe('static unregister(name)', () => {
    it('should disconnect and remove socket from resources', () => {
      const disconnectFn = vi.fn();
      Socket.resources['test'] = { disconnect: disconnectFn };
      Socket.unregister('test');
      expect(disconnectFn).toHaveBeenCalled();
      expect(Socket.resources['test']).toBeUndefined();
    });
  });

  describe('heartbeat(msg)', () => {
    it('should update lrh timestamp', () => {
      const sock = new Socket('localhost:8765');
      const before = Date.now();
      sock.heartbeat();
      expect(sock.lrh).toBeGreaterThanOrEqual(before);
    });

    it('should call sendMessage with heartbeat key', () => {
      const sock = new Socket('localhost:8765');
      const spy = vi.spyOn(sock, 'sendMessage');
      sock.heartbeat('ping');
      expect(spy).toHaveBeenCalledWith('heartbeat', 'ping');
    });

    it('should default msg to true', () => {
      const sock = new Socket('localhost:8765');
      const spy = vi.spyOn(sock, 'sendMessage');
      sock.heartbeat();
      expect(spy).toHaveBeenCalledWith('heartbeat', true);
    });
  });

  describe('connect(url, callback)', () => {
    it('should create new WebSocket', () => {
      const sock = new Socket('localhost:8765');
      global.WebSocket.mockClear();
      sock.connect('localhost:9999');
      expect(global.WebSocket).toHaveBeenCalledWith('ws://localhost:9999');
    });

    it('should set state to CONNECTING', () => {
      const sock = new Socket('localhost:8765');
      sock.state = 'DISCONNECTED';
      sock.connect('localhost:8765');
      expect(sock.state).toBe('CONNECTING');
    });

    it('should store connect callback', () => {
      const sock = new Socket('localhost:8765');
      const cb = vi.fn();
      sock.connect('localhost:8765', cb);
      expect(sock.connectCallback).toBe(cb);
    });

    it('should return this for chaining', () => {
      const sock = new Socket('localhost:8765');
      const result = sock.connect('localhost:8765');
      expect(result).toBe(sock);
    });

    it('should set state to FAILED on WebSocket creation error', () => {
      const sock = new Socket('localhost:8765');
      global.WebSocket = vi.fn(() => { throw new Error('Connection refused'); });
      sock.connect('localhost:9999');
      expect(sock.state).toBe('FAILED');
    });
  });

  describe('reconnect()', () => {
    it('should increment retries', () => {
      const sock = new Socket('localhost:8765');
      const initialRetries = sock.retries;
      sock.reconnect();
      expect(sock.retries).toBe(initialRetries + 1);
    });

    it('should close existing websocket', () => {
      const sock = new Socket('localhost:8765');
      sock.reconnect();
      expect(mockWs.close).toHaveBeenCalled();
    });

    it('should set state to RECONNECT', () => {
      const sock = new Socket('localhost:8765');
      sock.reconnect();
      expect(sock.state).toBe('RECONNECT');
    });

    it('should call disconnect when retries exceed MAX_TRIES', () => {
      const sock = new Socket('localhost:8765');
      sock.retries = 6; // MAX_TRIES is 5
      const disconnectSpy = vi.spyOn(sock, 'disconnect');
      sock.reconnect();
      expect(disconnectSpy).toHaveBeenCalled();
    });
  });

  describe('disconnect()', () => {
    it('should set state to DISCONNECTED', () => {
      const sock = new Socket('localhost:8765');
      sock.disconnect();
      expect(sock.state).toBe('DISCONNECTED');
    });

    it('should reset retries to 0', () => {
      const sock = new Socket('localhost:8765');
      sock.retries = 3;
      sock.disconnect();
      expect(sock.retries).toBe(0);
    });

    it('should clear interval if set', () => {
      const sock = new Socket('localhost:8765');
      sock.interval = setInterval(() => {}, 1000);
      sock.disconnect();
      expect(sock.interval).toBeUndefined();
    });
  });

  describe('setTarget(target, callback)', () => {
    it('should add target callback', () => {
      const sock = new Socket('localhost:8765');
      const cb = vi.fn();
      sock.setTarget('my-actor', cb);
      expect(sock.targets['my-actor']).toBe(cb);
    });

    it('should return this for chaining', () => {
      const sock = new Socket('localhost:8765');
      const result = sock.setTarget('my-actor', vi.fn());
      expect(result).toBe(sock);
    });
  });

  describe('removeTarget(id)', () => {
    it('should remove target', () => {
      const sock = new Socket('localhost:8765', { actor1: vi.fn() });
      sock.removeTarget('actor1');
      expect(sock.targets['actor1']).toBeUndefined();
    });

    it('should return this for chaining', () => {
      const sock = new Socket('localhost:8765', { actor1: vi.fn() });
      const result = sock.removeTarget('actor1');
      expect(result).toBe(sock);
    });
  });

  describe('dispatchEvent(event)', () => {
    it('should call target callback with event', () => {
      const cb = vi.fn();
      const sock = new Socket('localhost:8765', { 'my-actor': cb });
      const event = { target: 'my-actor', name: 'READ', data: {} };
      sock.dispatchEvent(event);
      expect(cb).toHaveBeenCalledWith(event);
    });

    it('should log error when target not found', () => {
      const sock = new Socket('localhost:8765');
      const event = { target: 'unknown-actor', name: 'READ', data: {} };
      sock.dispatchEvent(event);
      expect(Logging.error).toHaveBeenCalled();
    });
  });

  describe('onMessage(msg)', () => {
    it('should set state to CONNECTED', () => {
      const sock = new Socket('localhost:8765');
      sock.state = 'CONNECTING';
      sock.onMessage({ data: JSON.stringify({ heartbeat: true }) });
      expect(sock.state).toBe('CONNECTED');
    });

    it('should process heartbeat messages by calling heartbeat()', () => {
      const sock = new Socket('localhost:8765');
      const spy = vi.spyOn(sock, 'heartbeat');
      sock.onMessage({ data: JSON.stringify({ heartbeat: true }) });
      expect(spy).toHaveBeenCalled();
    });

    it('should update lrh timestamp', () => {
      const sock = new Socket('localhost:8765');
      const before = Date.now();
      sock.onMessage({ data: JSON.stringify({ heartbeat: true }) });
      expect(sock.lrh).toBeGreaterThanOrEqual(before);
    });

    it('should log error for invalid JSON', () => {
      const sock = new Socket('localhost:8765');
      sock.onMessage({ data: 'not-json{{{' });
      expect(Logging.error).toHaveBeenCalled();
    });

    it('should flush queued messages when connected', () => {
      const sock = new Socket('localhost:8765');
      sock.queue = [{ key: 'test', msg: 'hello' }];
      sock.onMessage({ data: JSON.stringify({ heartbeat: true }) });
      // Queue should be cleared
      expect(sock.queue).toEqual([]);
    });
  });

  describe('sendMessage(key, msg, plain)', () => {
    it('should queue message when websocket is not ready', () => {
      const sock = new Socket('localhost:8765');
      sock.websocket.readyState = 0; // CONNECTING
      sock.sendMessage('test', { data: 1 });
      expect(sock.queue.length).toBeGreaterThan(0);
    });

    it('should send JSON.stringify when readyState is 1', () => {
      const sock = new Socket('localhost:8765');
      sock.websocket.readyState = 1;
      sock.sendMessage('test', { data: 1 });
      expect(mockWs.send).toHaveBeenCalled();
      const sent = mockWs.send.mock.calls[mockWs.send.mock.calls.length - 1][0];
      const parsed = JSON.parse(sent);
      expect(parsed.test).toEqual({ data: 1 });
    });

    it('should send without key wrapper when key is null/undefined', () => {
      const sock = new Socket('localhost:8765');
      sock.websocket.readyState = 1;
      sock.sendMessage(undefined, { action: 'hello' });
      const sent = mockWs.send.mock.calls[mockWs.send.mock.calls.length - 1][0];
      const parsed = JSON.parse(sent);
      expect(parsed.action).toBe('hello');
    });

    it('should send plain message when plain=true', () => {
      const sock = new Socket('localhost:8765');
      sock.websocket.readyState = 1;
      sock.sendMessage('key', 'raw-string', true);
      const sent = mockWs.send.mock.calls[mockWs.send.mock.calls.length - 1][0];
      expect(sent).toBe('raw-string');
    });

    it('should return this when message is sent', () => {
      const sock = new Socket('localhost:8765');
      sock.websocket.readyState = 1;
      const result = sock.sendMessage('test', 'data');
      expect(result).toBe(sock);
    });

    it('should return undefined when message is queued', () => {
      const sock = new Socket('localhost:8765');
      sock.websocket.readyState = 0;
      const result = sock.sendMessage('test', 'data');
      expect(result).toBeUndefined();
    });
  });

  describe('sendEvent(event)', () => {
    it('should call websocket.send with event.toString()', () => {
      const sock = new Socket('localhost:8765');
      const event = { toString: () => '{"name":"READ"}' };
      sock.sendEvent(event);
      expect(mockWs.send).toHaveBeenCalledWith('{"name":"READ"}');
    });
  });

  describe('onOpen(event)', () => {
    it('should set state to CONNECTING', () => {
      const sock = new Socket('localhost:8765');
      sock.state = 'DISCONNECTED';
      sock.onOpen({});
      expect(sock.state).toBe('CONNECTING');
    });

    it('should call connectCallback', () => {
      const sock = new Socket('localhost:8765');
      const cb = vi.fn();
      sock.connectCallback = cb;
      sock.onOpen({});
      expect(cb).toHaveBeenCalled();
    });

    it('should send allStatesRequest', () => {
      const sock = new Socket('localhost:8765');
      const spy = vi.spyOn(sock, 'sendMessage');
      sock.onOpen({});
      expect(spy).toHaveBeenCalledWith('allStatesRequest', true);
    });

    it('should call heartbeat', () => {
      const sock = new Socket('localhost:8765');
      const spy = vi.spyOn(sock, 'heartbeat');
      sock.onOpen({});
      expect(spy).toHaveBeenCalled();
    });
  });

  describe('onClose(event)', () => {
    it('should set state to DISCONNECTED', () => {
      const sock = new Socket('localhost:8765');
      sock.state = 'CONNECTED';
      sock.onClose({ code: 1000 });
      expect(sock.state).toBe('DISCONNECTED');
    });

    it('should call disable()', () => {
      const sock = new Socket('localhost:8765');
      const spy = vi.spyOn(sock, 'disable');
      sock.onClose({ code: 1000 });
      expect(spy).toHaveBeenCalled();
    });

    it('should log warning', () => {
      const sock = new Socket('localhost:8765');
      sock.onClose({ code: 1000 });
      expect(Logging.warn).toHaveBeenCalled();
    });
  });

  describe('disable()', () => {
    it('should set isDisabled to true', () => {
      const sock = new Socket('localhost:8765');
      sock.isDisabled = false;
      sock.disable();
      expect(sock.isDisabled).toBe(true);
    });

    it('should call target callbacks when not already disabled', () => {
      const cb = vi.fn();
      const sock = new Socket('localhost:8765', { actor1: cb });
      sock.isDisabled = false;
      sock.disable();
      expect(cb).toHaveBeenCalled();
      const callArg = cb.mock.calls[0][0];
      expect(callArg.name || callArg.event).toBeDefined();
    });

    it('should not call targets when already disabled', () => {
      const cb = vi.fn();
      const sock = new Socket('localhost:8765', { actor1: cb });
      sock.isDisabled = true;
      cb.mockClear();
      sock.disable();
      expect(cb).not.toHaveBeenCalled();
    });
  });

  describe('enable()', () => {
    it('should set isDisabled to false', () => {
      const sock = new Socket('localhost:8765');
      sock.isDisabled = true;
      sock.enable();
      expect(sock.isDisabled).toBe(false);
    });

    it('should call target callbacks when was disabled', () => {
      const cb = vi.fn();
      const sock = new Socket('localhost:8765', { actor1: cb });
      sock.isDisabled = true;
      sock.enable();
      expect(cb).toHaveBeenCalled();
    });

    it('should not call targets when already enabled', () => {
      const cb = vi.fn();
      const sock = new Socket('localhost:8765', { actor1: cb });
      sock.isDisabled = false;
      cb.mockClear();
      sock.enable();
      expect(cb).not.toHaveBeenCalled();
    });
  });

  describe('watchdog()', () => {
    it('should transition CONNECTING to WAITING', () => {
      const sock = new Socket('localhost:8765');
      sock.state = 'CONNECTING';
      sock.watchdog();
      expect(sock.state).toBe('WAITING');
    });

    it('should transition RECONNECT to WAITING', () => {
      const sock = new Socket('localhost:8765');
      sock.state = 'RECONNECT';
      sock.watchdog();
      expect(sock.state).toBe('WAITING');
    });

    it('should call reconnect when FAILED', () => {
      const sock = new Socket('localhost:8765');
      sock.state = 'FAILED';
      const spy = vi.spyOn(sock, 'reconnect');
      sock.watchdog();
      expect(spy).toHaveBeenCalled();
    });

    it('should enable on CONNECTED state', () => {
      const sock = new Socket('localhost:8765');
      sock.state = 'CONNECTED';
      sock.lrh = Date.now(); // recent heartbeat
      const spy = vi.spyOn(sock, 'enable');
      sock.watchdog();
      expect(spy).toHaveBeenCalled();
    });

    it('should transition to WAITING when TTL exceeded', () => {
      const sock = new Socket('localhost:8765', {}, 1000);
      sock.state = 'CONNECTED';
      sock.lrh = Date.now() - 2000; // 2 seconds ago, TTL is 1s
      sock.watchdog();
      expect(sock.state).toBe('WAITING');
    });
  });
});
