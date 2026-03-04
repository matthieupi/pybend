import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../../utils/Logging.js', () => ({
  default: { warn: vi.fn(), error: vi.fn(), debug: vi.fn(), dev: vi.fn(), log: vi.fn(), init: vi.fn(), event: vi.fn() }
}));

vi.mock('../../utils/Toast.js', () => ({
  showToast: vi.fn()
}));

import HTTP from '../../core/transport/HTTP.js';
import { showToast } from '../../utils/Toast.js';

describe('HTTP.js', () => {

  beforeEach(() => {
    global.fetch.mockClear();
    showToast.mockClear();
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

  describe('error handling overhaul', () => {
    // 1. GET: should not call onError twice on 500
    it('GET should not double-report errors on 500', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: () => Promise.resolve({ error: 'Internal Server Error' })
      });
      const onSuccess = vi.fn();
      const onError = vi.fn();
      HTTP.get('http://localhost:5000/fail', onSuccess, onError);

      await vi.waitFor(() => expect(onError).toHaveBeenCalled());
      expect(onError).toHaveBeenCalledTimes(1);
      expect(onSuccess).not.toHaveBeenCalled();
      // Toasts removed from HTTP.js — handled by NTTElement.ERROR via ERROR TX
      expect(showToast).not.toHaveBeenCalled();
    });

    // 2. GET: should pass json object to onError (not string)
    it('GET should pass json object to onError on 500', async () => {
      const errorResponse = { error: 'Internal Server Error', code: 500 };
      global.fetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: () => Promise.resolve(errorResponse)
      });
      const onSuccess = vi.fn();
      const onError = vi.fn();
      HTTP.get('http://localhost:5000/fail', onSuccess, onError);

      await vi.waitFor(() => expect(onError).toHaveBeenCalled());
      expect(onError).toHaveBeenCalledWith(errorResponse);
      expect(onError).toHaveBeenCalledTimes(1);
    });

    // 3. POST: should not call onSuccess after error response
    it('POST should not call onSuccess after 400 error', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: () => Promise.resolve({ error: 'Bad Request' })
      });
      const onSuccess = vi.fn();
      const onError = vi.fn();
      HTTP.post('http://localhost:5000/products', { name: '' }, onSuccess, onError);

      await vi.waitFor(() => expect(onError).toHaveBeenCalled());
      expect(onError).toHaveBeenCalledTimes(1);
      expect(onSuccess).not.toHaveBeenCalled();
    });

    // 4. PUT: should not call onSuccess after 401 redirect
    it('PUT should not call onSuccess after 401 redirect', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: () => Promise.resolve({})
      });
      const onSuccess = vi.fn();
      const onError = vi.fn();

      // Mock window.location to prevent actual navigation in test
      delete window.location;
      window.location = { href: '' };

      HTTP.put('http://localhost:5000/products/1', { name: 'Test' }, onSuccess, onError);

      await vi.waitFor(() => expect(window.location).toBe('/login.html'));
      expect(onSuccess).not.toHaveBeenCalled();
      expect(onError).not.toHaveBeenCalled();
    });

    // 5. DELETE: should not call onError twice on 500
    it('DELETE should not double-report errors on 500', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: () => Promise.resolve({ error: 'Server error' })
      });
      const onSuccess = vi.fn();
      const onError = vi.fn();
      HTTP.remove('http://localhost:5000/products/1', onSuccess, onError);

      await vi.waitFor(() => expect(onError).toHaveBeenCalled());
      expect(onError).toHaveBeenCalledTimes(1);
      expect(onSuccess).not.toHaveBeenCalled();
      // Toasts removed from HTTP.js — handled by NTTElement.ERROR via ERROR TX
      expect(showToast).not.toHaveBeenCalled();
    });

    // 6. GET 404: should call onError once, not call onSuccess
    it('GET 404 should call onError once and not call onSuccess', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: false,
        status: 404
      });
      const onSuccess = vi.fn();
      const onError = vi.fn();
      HTTP.get('http://localhost:5000/missing', onSuccess, onError);

      await vi.waitFor(() => expect(onError).toHaveBeenCalled());
      expect(onError).toHaveBeenCalledTimes(1);
      expect(onSuccess).not.toHaveBeenCalled();
      // Toasts removed from HTTP.js — handled by NTTElement.ERROR via ERROR TX
      expect(showToast).not.toHaveBeenCalled();
    });

    // 7. Network error: should call onError once with message
    it('GET network error should call onError once', async () => {
      global.fetch.mockRejectedValueOnce(new Error('Network failure'));
      const onSuccess = vi.fn();
      const onError = vi.fn();
      HTTP.get('http://localhost:5000/fail', onSuccess, onError);

      await vi.waitFor(() => expect(onError).toHaveBeenCalled());
      expect(onError).toHaveBeenCalledTimes(1);
      expect(onError).toHaveBeenCalledWith('Network failure');
      expect(onSuccess).not.toHaveBeenCalled();
      expect(showToast).toHaveBeenCalledTimes(1);
    });

    // 8. POST: should pass json to onError (not json.error + resp.toString())
    it('POST should pass full json object to onError', async () => {
      const errorResponse = { error: 'Validation failed', details: ['name required'] };
      global.fetch.mockResolvedValueOnce({
        ok: false,
        status: 422,
        json: () => Promise.resolve(errorResponse)
      });
      const onSuccess = vi.fn();
      const onError = vi.fn();
      HTTP.post('http://localhost:5000/products', {}, onSuccess, onError);

      await vi.waitFor(() => expect(onError).toHaveBeenCalled());
      expect(onError).toHaveBeenCalledWith(errorResponse);
      expect(onError).toHaveBeenCalledTimes(1);
    });

    // 9. PUT: should pass json to onError (not json.error string)
    it('PUT should pass full json object to onError', async () => {
      const errorResponse = { error: 'Forbidden', message: 'Not owner' };
      global.fetch.mockResolvedValueOnce({
        ok: false,
        status: 403,
        json: () => Promise.resolve(errorResponse)
      });
      const onSuccess = vi.fn();
      const onError = vi.fn();
      HTTP.put('http://localhost:5000/products/1', { name: 'Test' }, onSuccess, onError);

      await vi.waitFor(() => expect(onError).toHaveBeenCalled());
      expect(onError).toHaveBeenCalledWith(errorResponse);
      expect(onError).toHaveBeenCalledTimes(1);
    });

    // 10. DELETE: should pass json to onError on error response
    it('DELETE should pass full json object to onError', async () => {
      const errorResponse = { error: 'Cannot delete', reason: 'Has dependencies' };
      global.fetch.mockResolvedValueOnce({
        ok: false,
        status: 409,
        json: () => Promise.resolve(errorResponse)
      });
      const onSuccess = vi.fn();
      const onError = vi.fn();
      HTTP.remove('http://localhost:5000/products/1', onSuccess, onError);

      await vi.waitFor(() => expect(onError).toHaveBeenCalled());
      expect(onError).toHaveBeenCalledWith(errorResponse);
      expect(onError).toHaveBeenCalledTimes(1);
    });

    // 11. POST network error should not double-report
    it('POST network error should call onError once', async () => {
      global.fetch.mockRejectedValueOnce(new Error('Connection refused'));
      const onSuccess = vi.fn();
      const onError = vi.fn();
      HTTP.post('http://localhost:5000/products', { name: 'Test' }, onSuccess, onError);

      await vi.waitFor(() => expect(onError).toHaveBeenCalled());
      expect(onError).toHaveBeenCalledTimes(1);
      expect(showToast).toHaveBeenCalledTimes(1);
    });

    // 12. PUT network error should not double-report
    it('PUT network error should call onError once', async () => {
      global.fetch.mockRejectedValueOnce(new Error('Timeout'));
      const onSuccess = vi.fn();
      const onError = vi.fn();
      HTTP.put('http://localhost:5000/products/1', { name: 'Test' }, onSuccess, onError);

      await vi.waitFor(() => expect(onError).toHaveBeenCalled());
      expect(onError).toHaveBeenCalledTimes(1);
      expect(showToast).toHaveBeenCalledTimes(1);
    });

    // 13. DELETE network error should not double-report
    it('DELETE network error should call onError once', async () => {
      global.fetch.mockRejectedValueOnce(new Error('Network down'));
      const onSuccess = vi.fn();
      const onError = vi.fn();
      HTTP.remove('http://localhost:5000/products/1', onSuccess, onError);

      await vi.waitFor(() => expect(onError).toHaveBeenCalled());
      expect(onError).toHaveBeenCalledTimes(1);
      expect(showToast).toHaveBeenCalledTimes(1);
    });

    // 14. GET 401 should redirect and not call onError
    it('GET 401 should redirect to login and not call onError', async () => {
      window.localStorage.setItem('jwtToken', 'expired-token');
      global.fetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: () => Promise.resolve({})
      });
      const onSuccess = vi.fn();
      const onError = vi.fn();

      delete window.location;
      window.location = { href: '' };

      HTTP.get('http://localhost:5000/products', onSuccess, onError);

      await vi.waitFor(() => expect(window.location).toBe('/login.html'));
      expect(onSuccess).not.toHaveBeenCalled();
      expect(onError).not.toHaveBeenCalled();
      expect(window.localStorage.getItem('jwtToken')).toBeNull();
    });

    // 15. HTTP.js no longer calls showToast directly — errors go through onError → ERROR TX
    it('GET should pass error json to onError (no direct toast)', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: () => Promise.resolve({ error: 'Database connection failed' })
      });
      const onSuccess = vi.fn();
      const onError = vi.fn();
      HTTP.get('http://localhost:5000/fail', onSuccess, onError);

      await vi.waitFor(() => expect(onError).toHaveBeenCalled());
      expect(onError).toHaveBeenCalledWith({ error: 'Database connection failed' });
      expect(showToast).not.toHaveBeenCalled();
    });

    // 16. HTTP.js passes error json to onError (no direct toast)
    it('POST should pass error json to onError (no direct toast)', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: () => Promise.resolve({ detail: 'Invalid input format' })
      });
      const onSuccess = vi.fn();
      const onError = vi.fn();
      HTTP.post('http://localhost:5000/products', {}, onSuccess, onError);

      await vi.waitFor(() => expect(onError).toHaveBeenCalled());
      expect(onError).toHaveBeenCalledWith({ detail: 'Invalid input format' });
      expect(showToast).not.toHaveBeenCalled();
    });

    // 17. Pydantic 422 validation errors — passed to onError (no direct toast)
    it('should pass Pydantic 422 json to onError (no direct toast)', async () => {
      const errorBody = {
        detail: [
          { loc: ['body', 'website'], msg: 'Invalid URL', type: 'value_error', input: 'not-a-url' }
        ]
      };
      global.fetch.mockResolvedValueOnce({
        ok: false,
        status: 422,
        json: () => Promise.resolve(errorBody)
      });
      const onSuccess = vi.fn();
      const onError = vi.fn();
      HTTP.post('http://localhost:5000/products', {}, onSuccess, onError);

      await vi.waitFor(() => expect(onError).toHaveBeenCalled());
      expect(onError).toHaveBeenCalledWith(errorBody);
      expect(showToast).not.toHaveBeenCalled();
    });

    // 18. Multiple Pydantic validation errors — passed to onError
    it('should pass multiple Pydantic errors to onError', async () => {
      const errorBody = {
        detail: [
          { loc: ['body', 'name'], msg: 'Field required', type: 'missing' },
          { loc: ['body', 'price'], msg: 'Value must be greater than 0', type: 'value_error' },
        ]
      };
      global.fetch.mockResolvedValueOnce({
        ok: false,
        status: 422,
        json: () => Promise.resolve(errorBody)
      });
      const onSuccess = vi.fn();
      const onError = vi.fn();
      HTTP.post('http://localhost:5000/products', {}, onSuccess, onError);

      await vi.waitFor(() => expect(onError).toHaveBeenCalled());
      expect(onError).toHaveBeenCalledWith(errorBody);
      expect(showToast).not.toHaveBeenCalled();
    });

    // 19. String detail — passed to onError
    it('should pass string detail to onError', async () => {
      const errorBody = { detail: 'Simple string error' };
      global.fetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: () => Promise.resolve(errorBody)
      });
      const onSuccess = vi.fn();
      const onError = vi.fn();
      HTTP.post('http://localhost:5000/products', {}, onSuccess, onError);

      await vi.waitFor(() => expect(onError).toHaveBeenCalled());
      expect(onError).toHaveBeenCalledWith(errorBody);
      expect(showToast).not.toHaveBeenCalled();
    });

    // 20. Embedded error in 200 response now routes to onError (not onSuccess)
    it('GET should route embedded error in 200 response to onError', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ error: 'authentication required' })
      });
      const onSuccess = vi.fn();
      const onError = vi.fn();
      HTTP.get('http://localhost:5000/products/1/favorite', onSuccess, onError);

      await vi.waitFor(() => expect(onError).toHaveBeenCalled());
      expect(onError).toHaveBeenCalledWith({ error: 'authentication required' });
      expect(onSuccess).not.toHaveBeenCalled();
    });
  });

  describe('_extractError priority order', () => {
    it('should check detail before error (FastAPI format primary)', () => {
      // When both detail and error exist, detail wins
      const json = { detail: 'FastAPI error', error: 'Legacy error' };
      expect(HTTP._extractError(json)).toBe('FastAPI error');
    });

    it('should return error when detail is absent', () => {
      const json = { error: 'Legacy error' };
      expect(HTTP._extractError(json)).toBe('Legacy error');
    });

    it('should handle Pydantic array detail before string detail', () => {
      const json = {
        detail: [{ loc: ['body', 'name'], msg: 'Required' }],
      };
      expect(HTTP._extractError(json)).toBe('name: Required');
    });

    it('should return null for clean response body', () => {
      const json = { id: 1, name: 'Product' };
      expect(HTTP._extractError(json)).toBeNull();
    });
  });

  describe('_extractValidationErrors(json)', () => {
    it('should return structured errors for Pydantic 422 array detail', () => {
      const json = {
        detail: [
          { loc: ['body', 'website'], msg: 'Invalid URL', type: 'value_error', input: 'not-a-url' },
          { loc: ['body', 'price'], msg: 'Value must be > 0', type: 'value_error.number', input: -5 },
        ]
      };
      const result = HTTP._extractValidationErrors(json);
      expect(result).toEqual([
        { field: 'website', message: 'Invalid URL', type: 'value_error', input: 'not-a-url' },
        { field: 'price', message: 'Value must be > 0', type: 'value_error.number', input: -5 },
      ]);
    });

    it('should return null for string detail', () => {
      const result = HTTP._extractValidationErrors({ detail: 'Not found' });
      expect(result).toBeNull();
    });

    it('should return null for non-object input', () => {
      expect(HTTP._extractValidationErrors(null)).toBeNull();
      expect(HTTP._extractValidationErrors(undefined)).toBeNull();
      expect(HTTP._extractValidationErrors('string')).toBeNull();
    });

    it('should return null when detail is missing', () => {
      expect(HTTP._extractValidationErrors({ error: 'something' })).toBeNull();
    });

    it('should return null for empty detail array', () => {
      expect(HTTP._extractValidationErrors({ detail: [] })).toBeNull();
    });

    it('should use last element of loc as field name', () => {
      const json = {
        detail: [
          { loc: ['body', 'nested', 'field_name'], msg: 'Bad value', type: 'type_error' }
        ]
      };
      const result = HTTP._extractValidationErrors(json);
      expect(result[0].field).toBe('field_name');
    });
  });
});
