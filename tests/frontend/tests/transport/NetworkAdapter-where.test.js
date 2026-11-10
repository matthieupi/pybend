/** Native collection READ predicate serialization and correlated replies. */
import {beforeEach, describe, expect, it, vi} from 'vitest';
import {NetworkAdapter} from '../../core/transport/NetworkAdapter.js';
import HTTP from '../../core/transport/HTTP.js';

vi.mock('../../core/transport/HTTP.js', () => ({
  default: {get: vi.fn(), post: vi.fn()},
}));
vi.mock('../../utils/Logging.js', () => ({
  default: {dev: vi.fn(), error: vi.fn()},
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe('native READ where transport', () => {
  it('JSON-encodes predicates only, preserving bound-looking text and OR',
    () => {
      // 0. Include URL metacharacters and SQL-looking values as plain data.
      const router = {has: vi.fn(() => true), dispatch: vi.fn()};
      const adapter = new NetworkAdapter(router);
      const where = {
        status: 'open',
        $or: [{name__contains: 'A%_ & + # é'},
          {name__in: ["' OR 1=1 --", 'second']}],
      };
      const original = structuredClone(where);
      const request = {
        name: 'READ', source: 'list-1',
        target: 'http://localhost:5000/Entry/_',
        data: {
          where, order_desc: 'id', limit: 20, offset: 0, depth: 0,
          populate: 'children.tags', unused: null,
        },
        meta: {inbox: 'RESULT', correlation: 'read-1'},
      };
      // 1. Dispatch through the production HTTP adapter without a server.
      adapter.send(request);
      const [address, success] = HTTP.get.mock.calls[0];
      const url = new URL(address);
      // 2. Only where is JSON; scalar options retain native query spelling.
      expect(url.pathname).toBe('/Entry/_');
      expect(JSON.parse(url.searchParams.get('where'))).toEqual(original);
      expect(url.searchParams.get('where')).toBe(JSON.stringify(original));
      expect(url.searchParams.get('order_desc')).toBe('id');
      expect(url.searchParams.get('populate')).toBe('children.tags');
      expect(url.searchParams.get('depth')).toBe('0');
      expect(url.searchParams.get('offset')).toBe('0');
      expect(url.searchParams.get('limit')).toBe('20');
      expect(url.searchParams.has('unused')).toBe(false);
      expect(HTTP.post).not.toHaveBeenCalled();
      expect(request.data.where).toEqual(original);
      // 3. Native response routing retains instance correlation and identity.
      const page = {
        data: [],
        meta: {total: 0, limit: 20, offset: 0, has_more: false},
      };
      success(page);
      expect(router.dispatch).toHaveBeenCalledWith(expect.objectContaining({
        name: 'RESULT', source: request.target, target: request.source,
        data: page, meta: request.meta,
      }));
    });

  it('keeps explicit empty where distinct from an omitted legacy query',
    () => {
      // 0. Compare instance-owned unrestricted predicates and legacy READ.
      const adapter = new NetworkAdapter({has: vi.fn(() => true)});
      const base = {
        name: 'READ', source: 'list-1',
        target: 'http://localhost:5000/Entry/_', meta: {},
      };
      // 1. Native query mode sends an object, while legacy mode omits it.
      adapter.send({...base, data: {where: {}, limit: 20}});
      adapter.send({...base, data: {limit: 20}});
      const urls = HTTP.get.mock.calls.map(([url]) => new URL(url));
      // 2. Do not silently discard or stringify unrelated options as JSON.
      expect(urls[0].searchParams.get('where')).toBe('{}');
      expect(urls[1].searchParams.has('where')).toBe(false);
      expect(urls[1].searchParams.get('limit')).toBe('20');
    });
});

/* Changelog
 * - 2026-11-10: Restore native predicate transport coverage.
 * - 2026-11-02: Cover native GET predicate serialization and RESULT routing. */
