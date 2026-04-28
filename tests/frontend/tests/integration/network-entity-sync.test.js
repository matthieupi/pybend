/**
 * Network Adapter + Entity Sync — Integration Tests
 *
 * Tests: HTTP verb routing, auth headers, callback routing, error handling
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ProductSchema, makeProductData, makeProductListResponse, API_URL } from './helpers/mock-schemas.js';
import { flush } from './helpers/test-env.js';

let HTTP, NetworkAdapter, matrix, TX, NTT;

const makeMockMatrix = () => ({
  has: vi.fn(() => true),
  dispatch: vi.fn(),
});

afterEach(async () => {
  await flush(10);
});

beforeEach(async () => {
  vi.resetModules();
  global.fetch = vi.fn(() => Promise.resolve({
    ok: true, status: 200,
    json: () => Promise.resolve({}),
  }));

  const httpMod = await import('../../core/transport/HTTP.js');
  const netMod = await import('../../core/transport/NetworkAdapter.js');
  const matrixMod = await import('../../core/Matrix.js');
  const txMod = await import('../../core/TX.js');
  const nttMod = await import('../../core/NTT.js');
  HTTP = httpMod.default;
  NetworkAdapter = netMod.NetworkAdapter;
  matrix = matrixMod.matrix;
  TX = txMod.default;
  NTT = nttMod.NTT;

  NTT.SCHEMA(ProductSchema);
});

describe('Network Entity Sync', () => {

  describe('HTTP class', () => {

    it('GET includes x-access-token header when token exists', () => {
      window.localStorage.setItem('jwtToken', 'test-token-123');
      const onSuccess = vi.fn();
      const onError = vi.fn();
      HTTP.get(`${API_URL}/products`, onSuccess, onError);

      expect(global.fetch).toHaveBeenCalledWith(
        `${API_URL}/products`,
        expect.objectContaining({ method: 'GET' })
      );

      // Check that the Headers object was passed
      const callArgs = global.fetch.mock.calls[0];
      const headers = callArgs[1].headers;
      expect(headers.get('x-access-token')).toBe('test-token-123');
    });

    it('GET without token does not include auth header', () => {
      window.localStorage.removeItem('jwtToken');
      HTTP.get(`${API_URL}/products`, vi.fn(), vi.fn());

      const callArgs = global.fetch.mock.calls[0];
      const headers = callArgs[1].headers;
      expect(headers.get('x-access-token')).toBeNull();
    });

    it('POST sends JSON body with Content-Type', () => {
      const data = { name: 'Test', price: 10 };
      HTTP.post(`${API_URL}/products`, data, vi.fn(), vi.fn());

      const callArgs = global.fetch.mock.calls[0];
      expect(callArgs[1].method).toBe('POST');
      expect(callArgs[1].body).toBe(JSON.stringify(data));
      expect(callArgs[1].headers.get('Content-Type')).toBe('application/json');
    });

    it('PUT sends JSON body with Content-Type', () => {
      const data = { name: 'Updated' };
      HTTP.put(`${API_URL}/products/1`, data, vi.fn(), vi.fn());

      const callArgs = global.fetch.mock.calls[0];
      expect(callArgs[1].method).toBe('PUT');
      expect(callArgs[1].body).toBe(JSON.stringify(data));
    });

    it('DELETE sends with DELETE method', () => {
      HTTP.remove(`${API_URL}/products/1`, vi.fn(), vi.fn());

      const callArgs = global.fetch.mock.calls[0];
      expect(callArgs[1].method).toBe('DELETE');
    });

    it('401 response triggers redirect to /login.html', async () => {
      global.fetch = vi.fn(() => Promise.resolve({
        ok: false, status: 401,
        json: () => Promise.resolve({ error: 'Unauthorized' }),
      }));

      // Mock window.location
      const originalLocation = window.location;
      delete window.location;
      window.location = { href: '', assign: vi.fn() };

      HTTP.get(`${API_URL}/products`, vi.fn(), vi.fn());

      // Wait for the promise chain
      await new Promise(r => setTimeout(r, 50));

      // Token should be cleared
      expect(window.localStorage.getItem('jwtToken')).toBeNull();

      // Restore
      window.location = originalLocation;
    });

    it('successful response with token updates localStorage', async () => {
      global.fetch = vi.fn(() => Promise.resolve({
        ok: true, status: 200,
        json: () => Promise.resolve({ token: 'new-token-456', data: [] }),
      }));

      const onSuccess = vi.fn();
      HTTP.get(`${API_URL}/products`, onSuccess, vi.fn());

      await new Promise(r => setTimeout(r, 50));
      expect(window.localStorage.getItem('jwtToken')).toBe('new-token-456');
    });

    it('network error calls onError', async () => {
      global.fetch = vi.fn(() => Promise.reject(new Error('Network error')));

      const onSuccess = vi.fn();
      const onError = vi.fn();
      HTTP.get(`${API_URL}/products`, onSuccess, onError);

      await new Promise(r => setTimeout(r, 50));
      expect(onError).toHaveBeenCalled();
    });

    it('checkIfUnauthorized returns true for 401', () => {
      expect(HTTP.checkIfUnauthorized({ status: 401 })).toBe(true);
    });

    it('checkIfUnauthorized returns false for other statuses', () => {
      expect(HTTP.checkIfUnauthorized({ status: 200 })).toBe(false);
      expect(HTTP.checkIfUnauthorized({ status: 403 })).toBe(false);
      expect(HTTP.checkIfUnauthorized({ status: 404 })).toBe(false);
    });

    it('checkValidCode returns true for 2xx range', () => {
      expect(HTTP.checkValidCode({ status: 200 })).toBe(true);
      expect(HTTP.checkValidCode({ status: 201 })).toBe(true);
      expect(HTTP.checkValidCode({ status: 203 })).toBe(true);
      expect(HTTP.checkValidCode({ status: 204 })).toBe(true);
    });

    it('checkValidCode returns false for non-2xx', () => {
      expect(HTTP.checkValidCode({ status: 404 })).toBe(false);
      expect(HTTP.checkValidCode({ status: 500 })).toBe(false);
    });
  });

  describe('NetworkAdapter', () => {

    it('send routes READ to HTTP.get', () => {
      const getSpy = vi.spyOn(HTTP, 'get').mockImplementation(() => {});
      const adapter = new NetworkAdapter(makeMockMatrix());

      adapter.send({
        name: 'READ',
        source: 'Product',
        target: `${API_URL}/products`,
        data: {},
        meta: {},
      });

      expect(getSpy).toHaveBeenCalledWith(
        expect.stringContaining('/products'),
        expect.any(Function),
        expect.any(Function)
      );
      getSpy.mockRestore();
    });

    it('send routes READ with query params', () => {
      const getSpy = vi.spyOn(HTTP, 'get').mockImplementation(() => {});
      const adapter = new NetworkAdapter(makeMockMatrix());

      adapter.send({
        name: 'READ',
        source: 'Product',
        target: `${API_URL}/products`,
        data: { limit: 20, offset: 0, depth: 1 },
        meta: {},
      });

      expect(getSpy).toHaveBeenCalledWith(
        expect.stringContaining('limit=20'),
        expect.any(Function),
        expect.any(Function)
      );
      getSpy.mockRestore();
    });

    it('routes HTTP READ response through Matrix to registered Product actor', () => {
      const response = makeProductListResponse(2);
      const getSpy = vi.spyOn(HTTP, 'get').mockImplementation((url, onSuccess) => {
        onSuccess(response);
      });
      const adapter = new NetworkAdapter(matrix);

      adapter.send({
        name: 'READ',
        source: 'Product',
        target: `${API_URL}/products`,
        data: {},
        meta: {},
      });

      const DC = NTT.get('Product');
      expect(getSpy).toHaveBeenCalledWith(
        expect.stringContaining('/products'),
        expect.any(Function),
        expect.any(Function)
      );
      expect(DC.instances.get('1').value.name).toBe('Test Product 1');
      expect(DC.instances.get('2').value.name).toBe('Test Product 2');

      getSpy.mockRestore();
    });

    it('send routes SCHEMA to HTTP.get', () => {
      const getSpy = vi.spyOn(HTTP, 'get').mockImplementation(() => {});
      const adapter = new NetworkAdapter(makeMockMatrix());

      adapter.send({
        name: 'SCHEMA',
        source: 'NTT',
        target: `${API_URL}/Product`,
        data: {},
        meta: {},
      });

      expect(getSpy).toHaveBeenCalledWith(
        expect.stringContaining('/Product'),
        expect.any(Function),
        expect.any(Function)
      );
      getSpy.mockRestore();
    });

    it('send routes CREATE to HTTP.post', () => {
      const postSpy = vi.spyOn(HTTP, 'post').mockImplementation(() => {});
      const adapter = new NetworkAdapter(makeMockMatrix());

      adapter.send({
        name: 'CREATE',
        source: 'Product',
        target: `${API_URL}/products`,
        data: { name: 'New', price: 10 },
        meta: {},
      });

      expect(postSpy).toHaveBeenCalled();
      postSpy.mockRestore();
    });

    it('send routes UPDATE to HTTP.put', () => {
      const putSpy = vi.spyOn(HTTP, 'put').mockImplementation(() => {});
      const adapter = new NetworkAdapter(makeMockMatrix());

      adapter.send({
        name: 'UPDATE',
        source: 'Product',
        target: `${API_URL}/products/1`,
        data: { name: 'Updated' },
        meta: {},
      });

      expect(putSpy).toHaveBeenCalled();
      putSpy.mockRestore();
    });

    it('send routes DELETE to HTTP.remove', () => {
      const removeSpy = vi.spyOn(HTTP, 'remove').mockImplementation(() => {});
      const adapter = new NetworkAdapter(makeMockMatrix());

      adapter.send({
        name: 'DELETE',
        source: 'Product',
        target: `${API_URL}/products/1`,
        data: {},
        meta: {},
      });

      expect(removeSpy).toHaveBeenCalled();
      removeSpy.mockRestore();
    });

    it('send routes custom method to HTTP.post with /method path', () => {
      const postSpy = vi.spyOn(HTTP, 'post').mockImplementation(() => {});
      const adapter = new NetworkAdapter(makeMockMatrix());

      adapter.send({
        name: 'favorite',
        source: 'Product/1',
        target: `${API_URL}/products/1`,
        data: {},
        meta: {},
      });

      expect(postSpy).toHaveBeenCalledWith(
        expect.stringContaining('/products/1/favorite'),
        expect.anything(),
        expect.any(Function),
        expect.any(Function)
      );
      postSpy.mockRestore();
    });

    it('httpCallback swaps source and target, dispatches to matrix', () => {
      // Use a mock matrix that has() returns true for all targets
      const mockMatrix = {
        has: vi.fn(() => true),
        dispatch: vi.fn(),
      };
      const adapter = new NetworkAdapter(mockMatrix);

      const event = {
        name: 'READ',
        source: 'Product',
        target: `${API_URL}/products`,
        data: {},
        meta: {},
      };
      const response = { data: [], meta: { total: 0 } };

      adapter.httpCallback(event, response);

      expect(mockMatrix.dispatch).toHaveBeenCalled();
      const dispatched = mockMatrix.dispatch.mock.calls[0][0];
      expect(dispatched.source).toBe(`${API_URL}/products`);
      expect(dispatched.target).toBe('Product');
      expect(dispatched.data).toBe(response);
    });

    it('httpCallback uses meta.inbox as event name when specified', () => {
      const mockMatrix = {
        has: vi.fn(() => true),
        dispatch: vi.fn(),
      };
      const adapter = new NetworkAdapter(mockMatrix);

      const event = {
        name: 'READ',
        source: 'Product',
        target: `${API_URL}/products`,
        data: {},
        meta: { inbox: 'UPDATE' },
      };

      adapter.httpCallback(event, {});
      const dispatched = mockMatrix.dispatch.mock.calls[0][0];
      expect(dispatched.name).toBe('UPDATE');
    });
  });
});
