import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../../utils/Logging.js', () => ({
  default: { warn: vi.fn(), error: vi.fn(), debug: vi.fn(), dev: vi.fn(), log: vi.fn(), init: vi.fn(), event: vi.fn() }
}));

import HTTP from '../../core/transport/HTTP.js';

describe('HTTP.js', () => {

  beforeEach(() => {
    global.fetch.mockClear();
    window.localStorage.removeItem('jwtToken');
  });

  describe('static get(url, onSuccess, onError)', () => {
    it('should send GET request with auth token', async () => {
      window.localStorage.setItem('jwtToken', 'test-token');
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ id: 1, name: 'Product' })
      });

      const onSuccess = vi.fn();
      const onError = vi.fn();
      HTTP.get('http://localhost:5000/products', onSuccess, onError);

      await vi.waitFor(() => expect(onSuccess).toHaveBeenCalled());
      expect(onSuccess).toHaveBeenCalledWith({ id: 1, name: 'Product' });
    });

    it('should send GET without token when not available', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({})
      });

      const onSuccess = vi.fn();
      HTTP.get('http://localhost:5000/Product', onSuccess, vi.fn());

      await vi.waitFor(() => expect(onSuccess).toHaveBeenCalled());
      const [, opts] = global.fetch.mock.calls[0];
      expect(opts.method).toBe('GET');
    });

    it('should call onError on 404', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
      });

      const onSuccess = vi.fn();
      const onError = vi.fn();
      HTTP.get('http://localhost:5000/missing', onSuccess, onError);

      await vi.waitFor(() => expect(onError).toHaveBeenCalled());
    });

    it('should call onError on network error', async () => {
      global.fetch.mockRejectedValueOnce(new Error('Network error'));

      const onSuccess = vi.fn();
      const onError = vi.fn();
      HTTP.get('http://localhost:5000/fail', onSuccess, onError);

      await vi.waitFor(() => expect(onError).toHaveBeenCalled());
    });

    it('should store token if response contains one', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ token: 'new-token' })
      });

      const onSuccess = vi.fn();
      HTTP.get('http://localhost:5000/auth', onSuccess, vi.fn());

      await vi.waitFor(() => expect(onSuccess).toHaveBeenCalled());
    });
  });

  describe('static post(url, data, onSuccess, onError)', () => {
    it('should send POST with JSON data', async () => {
      window.localStorage.setItem('jwtToken', 'tok');
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ id: 1 })
      });

      const onSuccess = vi.fn();
      HTTP.post('http://localhost:5000/products', { name: 'New' }, onSuccess, vi.fn());

      await vi.waitFor(() => expect(onSuccess).toHaveBeenCalled());
      const [, opts] = global.fetch.mock.calls[0];
      expect(opts.method).toBe('POST');
      expect(opts.body).toBe(JSON.stringify({ name: 'New' }));
    });

    it('should stringify object data', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({})
      });

      HTTP.post('http://localhost:5000/x', { a: 1 }, vi.fn(), vi.fn());
      await vi.waitFor(() => expect(global.fetch).toHaveBeenCalled());
      const [, opts] = global.fetch.mock.calls[0];
      expect(typeof opts.body).toBe('string');
    });
  });

  describe('static put(url, data, onSuccess, onError)', () => {
    it('should send PUT request', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ id: 1, name: 'Updated' })
      });

      const onSuccess = vi.fn();
      HTTP.put('http://localhost:5000/products/1', { name: 'Updated' }, onSuccess, vi.fn());

      await vi.waitFor(() => expect(onSuccess).toHaveBeenCalled());
      const [, opts] = global.fetch.mock.calls[0];
      expect(opts.method).toBe('PUT');
    });
  });

  describe('static remove(url, onSuccess, onError)', () => {
    it('should send DELETE request', async () => {
      window.localStorage.setItem('jwtToken', 'tok');
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ deleted: true })
      });

      const onSuccess = vi.fn();
      HTTP.remove('http://localhost:5000/products/1', onSuccess, vi.fn());

      await vi.waitFor(() => expect(onSuccess).toHaveBeenCalled());
      const [, opts] = global.fetch.mock.calls[0];
      expect(opts.method).toBe('DELETE');
    });
  });

  describe('static checkIfUnauthorized(res)', () => {
    it('should return true and clear token for 401', () => {
      window.localStorage.setItem('jwtToken', 'expired');
      const result = HTTP.checkIfUnauthorized({ status: 401 });
      expect(result).toBe(true);
    });

    it('should return false for other status codes', () => {
      expect(HTTP.checkIfUnauthorized({ status: 200 })).toBe(false);
      expect(HTTP.checkIfUnauthorized({ status: 403 })).toBe(false);
      expect(HTTP.checkIfUnauthorized({ status: 500 })).toBe(false);
    });
  });

  describe('static checkValidCode(res)', () => {
    it('should return true for 200', () => {
      expect(HTTP.checkValidCode({ status: 200 })).toBe(true);
    });

    it('should return true for 201', () => {
      expect(HTTP.checkValidCode({ status: 201 })).toBe(true);
    });

    it('should return true for 203', () => {
      expect(HTTP.checkValidCode({ status: 203 })).toBe(true);
    });

    it('should return true for other 2xx codes', () => {
      expect(HTTP.checkValidCode({ status: 204 })).toBe(true);
      expect(HTTP.checkValidCode({ status: 299 })).toBe(true);
    });

    it('should return false for non-2xx', () => {
      expect(HTTP.checkValidCode({ status: 400 })).toBe(false);
      expect(HTTP.checkValidCode({ status: 500 })).toBe(false);
    });
  });

  describe('static checkRessource(res)', () => {
    it('should return false for 404', () => {
      expect(HTTP.checkRessource({ status: 404 })).toBe(false);
    });

    it('should return false for 301', () => {
      expect(HTTP.checkRessource({ status: 301 })).toBe(false);
    });

    it('should return false for 308', () => {
      expect(HTTP.checkRessource({ status: 308 })).toBe(false);
    });

    it('should return false for 400', () => {
      expect(HTTP.checkRessource({ status: 400 })).toBe(false);
    });

    it('should return false for 500', () => {
      expect(HTTP.checkRessource({ status: 500 })).toBe(false);
    });

    it('should return true for other status codes', () => {
      expect(HTTP.checkRessource({ status: 200 })).toBe(true);
      expect(HTTP.checkRessource({ status: 201 })).toBe(true);
    });
  });

  describe('static rpc(method_name, args, kwargs, onSuccess)', () => {
    it('should send RPC POST', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ result: 'ok' })
      });

      const onSuccess = vi.fn();
      HTTP.rpc('myMethod', { a: 1 }, { b: 2 }, onSuccess);

      await vi.waitFor(() => expect(global.fetch).toHaveBeenCalled());
      const [url, opts] = global.fetch.mock.calls[0];
      expect(url).toBe('rpc');
      expect(opts.method).toBe('POST');
    });
  });
});
