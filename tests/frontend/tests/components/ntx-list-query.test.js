/** Native query ownership, transport and persistent presentation checks. */
import {beforeEach, describe, expect, it, vi} from 'vitest';
import {NTT} from '../../core/NTT.js';
import {matrix} from '../../core/Matrix.js';
import {permissions} from '../../utils/Permissions.js';
import {ListElement} from '../../components/ListElement.js';
import '../../components/ntx-list.js';

vi.mock('../../utils/Permissions.js', () => ({
  permissions: {
    user: null, canAction: () => true, canView: () => true,
    canEdit: () => true,
  },
}));
vi.mock('../../utils/Logging.js', () => ({
  default: {
    dev: vi.fn(), warn: vi.fn(), error: vi.fn(), init: vi.fn(),
    event: vi.fn(), log: vi.fn(),
  },
}));

let serial = 0;
let schema;
let proto;
let requests;

/** Wait for native attachment microtasks and coalesced renders.
 * @returns {Promise<void>} Completion after two rendering frames. */
async function settle() {
  // 0. Allow attachment and its coalesced render to finish in order.
  await new Promise(resolve => requestAnimationFrame(resolve));
  await new Promise(resolve => requestAnimationFrame(resolve));
}

/** Register an isolated runtime model with a declared collection POST method.
 * @returns {Object} Native model schema. */
function modelSchema() {
  // 0. Isolate native registry membership without resetting component classes.
  const name = `QueryList${++serial}`;
  const result = {
    __name__: name, __tablename__: name,
    $id: `http://localhost:5000/${name}`,
    type: 'object', properties: {
      id: {type: 'integer'}, name: {type: 'string'},
    },
    methods: {
      SEARCH: {
        route: '/search', methods: ['POST'], requires_instance: false,
        parameters: {},
      },
    },
  };
  NTT.SCHEMA(result);
  return result;
}

/** Mount a real native query list against the current runtime model.
 * @param {Object} [query={}] Instance-owned query arguments.
 * @returns {Promise<HTMLElement>} Connected native list. */
async function mount(query = {}) {
  // 0. Exercise native schema attachment and lifecycle rather than fake protos.
  const list = document.createElement('ntx-list');
  list.query = query;
  list.model = schema.__name__;
  document.body.append(list);
  await settle();
  return list;
}

/** Build a canonical page row for the current model.
 * @param {number} id Entity identifier.
 * @param {Object} [extra={}] Additional row fields.
 * @returns {Object} Canonical native entity response. */
function row(id, extra = {}) {
  // 0. Keep synthetic entity identities within this test's runtime schema.
  return {
    id, name: `Record ${id}`, $schema: schema.$id,
    $id: `${schema.$id}/${id}`, ...extra,
  };
}

/** Deliver a page through the real native HTTP reply adapter and Matrix.
 * @param {Object} request Captured outbound native transaction.
 * @param {Object[]} rows Canonical records.
 * @param {number} [total=rows.length] Complete result count.
 * @returns {void} */
function reply(request, rows, total = rows.length) {
  // 0. Exercise source qualification and reply-target stripping in Matrix.
  const {limit, offset} = request.data;
  matrix.remote.httpCallback(request, {
    data: rows,
    meta: {total, limit, offset, has_more: offset + rows.length < total},
  });
}

/** Find the latest query transaction owned by a list.
 * @param {HTMLElement} list Native query list.
 * @returns {Object|undefined} Captured native request. */
function lastRequest(list) {
  return requests.mock.calls.map(([request]) => request)
    .filter(request => request.source === list.addr ||
      request.source === `${list.constructor.addr}/${list.addr}`).at(-1);
}

beforeEach(() => {
  permissions.user = {user_id: 7, role: 'staff'};
  requests = vi.spyOn(matrix.remote, 'send').mockImplementation(() => {});
  schema = modelSchema();
  proto = NTT.get(schema.__name__);
});

describe('declarative native queries', () => {
  it.each([true, false])('binds HTML in either attribute order: %s',
    async modelFirst => {
      const model = `model="${schema.__name__}"`;
      const query = `query='{"filters":{"status":"open"}}'`;
      document.body.innerHTML = '<ntx-list ' +
        (modelFirst ? `${model} ${query}` : `${query} ${model}`) +
        '></ntx-list>';
      await settle();
      const list = document.querySelector('ntx-list');
      expect(requests).toHaveBeenCalledTimes(1);
      expect(lastRequest(list).name).toBe('CREATE');
      expect(lastRequest(list).data.filters).toEqual({status: 'open'});
    });

  it('binds markup present before custom-element upgrade', async () => {
    const tag = `upgraded-query-list-${serial}`;
    document.body.innerHTML = `<${tag} model="${schema.__name__}" ` +
      `query='{"filters":{"status":"open"}}'></${tag}>`;

    /** Exercise native upgrade using the production list lifecycle. */
    class UpgradedList extends customElements.get('ntx-list') {}
    customElements.define(tag, UpgradedList);
    await settle();
    const list = document.querySelector(tag);
    expect(requests).toHaveBeenCalledTimes(1);
    expect(lastRequest(list).name).toBe('CREATE');
    expect(list.query.filters).toEqual({status: 'open'});
  });

  it.each([
    '{filters: {status: "open"}}', '[]', 'null', 'true', '1', '"text"',
    '{"filters":[]}', '{"query":{}}', '{"direction":"sideways"}',
    '{"limit":0}', '{"method":7}', '{"order_by":[]}',
    '{"text":"open"}', '{"orderBy":"name"}', '{"offset":20}',
  ])('retires a query and stays fail-closed after invalid JSON %s',
    async invalid => {
      const list = document.createElement('ntx-list');
      list.setAttribute('query', '{"filters":{"status":"open"}}');
      list.setAttribute('model', schema.__name__);
      document.body.append(list);
      await settle();
      const old = lastRequest(list);
      expect(old?.name).toBe('CREATE');
      list.setAttribute('query', invalid);
      expect(list.pending).toBeNull();
      reply(old, [row(1)]);
      list.loadPage();
      list.loadMore();
      await settle();
      expect(list.status.hidden).toBe(false);
      expect(list.status.getAttribute('role')).toBe('alert');
      expect(list.items.hidden).toBe(true);
      list.next.click();
      list.remove();
      document.body.append(list);
      const other = modelSchema();
      list.setAttribute('model', other.__name__);
      list.setAttribute('model', schema.__name__);
      await settle();
      expect(requests).toHaveBeenCalledTimes(1);
      expect(list.state).toBe('error');
      expect(list.value).toEqual([]);
      expect(proto.instances.size).toBe(0);
      list.setAttribute('query', '{"filters":{"status":"open"}}');
      expect(requests).toHaveBeenCalledTimes(2);
      reply(lastRequest(list), [row(2)]);
      expect(list.state).toBe('ready');
    });

  it('keeps property assignments ahead of stale markup on reconnect',
    async () => {
      const list = document.createElement('ntx-list');
      list.setAttribute('query', '{"filters":{"status":"open"}}');
      list.query = {filters: {status: 'closed'}};
      list.setAttribute('model', schema.__name__);
      document.body.append(list);
      await settle();
      expect(lastRequest(list).data.filters).toEqual({status: 'closed'});
      list.remove();
      document.body.append(list);
      await settle();
      list.define(proto);
      expect(lastRequest(list).data.filters).toEqual({status: 'closed'});
      expect(list.getAttribute('query')).toContain('open');
      expect('searchQuery' in list).toBe(false);
    });

  it('removes the attribute through the public setter into legacy mode',
    async () => {
      const list = document.createElement('ntx-list');
      list.setAttribute('query', '{}');
      list.setAttribute('model', schema.__name__);
      document.body.append(list);
      await settle();
      reply(lastRequest(list), [row(1)]);
      list.setAttribute('query', '{');
      list.removeAttribute('query');
      expect(list.query).toBeNull();
      expect(list.value).toEqual([`${schema.__name__}/1`]);
      list.loadMore();
      expect(requests.mock.calls.at(-1)[0].name).toBe('READ');
    });

  it.each([true, false])('rejects initial invalid markup; model first=%s',
    async modelFirst => {
      const model = `model="${schema.__name__}"`;
      const query = `query='{"filters":[]}'`;
      document.body.innerHTML = '<ntx-list ' +
        (modelFirst ? `${model} ${query}` : `${query} ${model}`) +
        '></ntx-list>';
      await settle();
      const list = document.querySelector('ntx-list');
      expect(requests).not.toHaveBeenCalled();
      expect(list.queryInvalid).toBe(true);
      expect(list.hasQuery).toBe(true);
      expect(list.query).toBeNull();
      expect(list.status.hidden).toBe(false);
      expect(list.status.textContent).toMatch(/invalid query attribute/i);
      list.query = {};
      expect(list.queryInvalid).toBe(false);
      expect(lastRequest(list).name).toBe('CREATE');
    });

  it('reroutes an updated attribute without altering another list',
    async () => {
      const left = await mount({filters: {status: 'left'}});
      const right = await mount({filters: {status: 'right'}});
      const leftRequest = lastRequest(left);
      const rightRequest = lastRequest(right);
      left.setAttribute('query', '{"filters":{"status":"updated"}}');
      expect(lastRequest(left)).not.toBe(leftRequest);
      expect(lastRequest(left).data.filters).toEqual({status: 'updated'});
      expect(lastRequest(right)).toBe(rightRequest);
      reply(leftRequest, [row(1)]);
      reply(rightRequest, [row(2)]);
      expect(left.value).toEqual([]);
      expect(right.value).toEqual([row(2).$id]);
    });

  it('catches subclass validation and blocks automatic reconfiguration',
    async () => {
      const inputs = [];

      /** Model an adapter that configures defaults while loading a page. */
      class AdapterList extends customElements.get('ntx-list') {

        /** Expose the same native defensive configuration snapshot.
         * @returns {Object|null} Valid native configuration. */
        get query() { return super.query; }

        /** Validate explicit input before delegating to native configuration.
         * @param {Object|null} value Explicit query or legacy reset.
         * @returns {void}
         * @throws {TypeError} The synthetic adapter rejects one filter. */
        set query(value) {
          inputs.push(value);
          if (value?.filters?.status === 'rejected') {
            throw new TypeError('Rejected adapter filter.');
          }
          super.query = value;
        }

        /** Keep adapter defaults from reviving rejected explicit input.
         * @param {number} [offset=0] Requested native page offset.
         * @param {Object} [options={}] Native retain/append options.
         * @param {boolean} [options.retain=false] Retain the accepted page.
         * @param {boolean} [options.append=false] Append returned records.
         * @returns {void} */
        loadPage(offset = 0, options = {}) {
          // 0. Never repair a binding failure using automatic configuration.
          if (this.queryInvalid) return;
          super.loadPage(offset, options);
        }
      }
      const tag = `adapter-query-list-${serial}`;
      customElements.define(tag, AdapterList);
      const list = document.createElement(tag);
      list.setAttribute('query', '{"filters":{"status":"open"}}');
      list.setAttribute('model', schema.__name__);
      document.body.append(list);
      await settle();
      list.setAttribute('query', '{"filters":{"status":"rejected"}}');
      expect(list.queryInvalid).toBe(true);
      expect(list.query).toBeNull();
      list.loadPage();
      list.remove();
      document.body.append(list);
      await settle();
      expect(requests).toHaveBeenCalledTimes(1);
      list.setAttribute('query', '{"filters":{"status":"open"}}');
      expect(requests).toHaveBeenCalledTimes(2);
      expect(inputs).toEqual([
        {filters: {status: 'open'}}, {filters: {status: 'rejected'}},
        {filters: {status: 'open'}},
      ]);
      list.removeAttribute('query');
      expect(inputs.at(-1)).toBeNull();
      expect(list.hasQuery).toBe(false);
    });

  it.each([undefined, [], 'text', {text: 'open'}, {filters: null}])(
    'rejects invalid property input %j and permits explicit recovery',
    async invalid => {
      const list = await mount({filters: {status: 'open'}});
      const old = lastRequest(list);
      expect(() => { list.query = invalid; }).toThrow(TypeError);
      expect(list.queryInvalid).toBe(true);
      expect(list.pending).toBeNull();
      reply(old, [row(1)]);
      expect(list.value).toEqual([]);
      list.query = {filters: {status: 'open'}};
      expect(list.queryInvalid).toBe(false);
      expect(lastRequest(list)).not.toBe(old);
    },
  );

  it('lets explicit null beat stale markup through reconnect', async () => {
    const list = document.createElement('ntx-list');
    list.setAttribute('query', '{}');
    list.setAttribute('model', schema.__name__);
    document.body.append(list);
    await settle();
    reply(lastRequest(list), [row(1)]);
    list.query = null;
    const count = requests.mock.calls.length;
    list.remove();
    document.body.append(list);
    await settle();
    expect(list.getAttribute('query')).toBe('{}');
    expect(list.query).toBeNull();
    expect(list.hasQuery).toBe(false);
    expect(requests).toHaveBeenCalledTimes(count);
  });

  it('hides accepted membership and retires an in-flight refresh on errors',
    async () => {
      const list = await mount({filters: {status: 'open'}});
      reply(lastRequest(list), [row(1)]);
      await settle();
      const child = list.items.firstElementChild;
      list.loadPage(0, {retain: true});
      const old = lastRequest(list);
      list.setAttribute('query', '{');
      reply(old, [row(2)]);
      matrix.remote.onError(old, {detail: 'Obsolete failure'});
      await settle();
      expect(list.query).toBeNull();
      expect(list.value).toEqual([]);
      expect(list.meta).toBeNull();
      expect(list.items.firstElementChild).toBe(child);
      expect(child.hidden).toBe(true);
      expect(child.inert).toBe(true);
      expect(list.status.textContent).toMatch(/invalid query attribute/i);
      list.query = {filters: {status: 'open'}};
      reply(lastRequest(list), [row(1)]);
      await settle();
      expect(list.items.firstElementChild).toBe(child);
      expect(child.hidden).toBe(false);
    });
});

describe('native instance-owned collection queries', () => {
  it('dispatches declared POST via CREATE with defaults and cloned queries',
    async () => {
      const input = {filters: {name: ['one']}};
      const list = await mount(input);
      input.filters.name.push('two');
      list.query.filters.name.push('three');
      const request = lastRequest(list);
      expect(request.name).toBe('CREATE');
      expect(request.target).toBe(`${schema.$id}/search`);
      expect(request.meta.inbox).toBe('RESULT');
      expect(request.data).toEqual({
        query: '', filters: {name: ['one']}, order_by: 'id',
        direction: 'asc', limit: 20, offset: 0,
      });
      expect(list.pending).toMatchObject({
        correlation: request.meta.correlation, model: schema.__name__,
        operation: 'read', limit: 20, offset: 0,
      });
      expect(list.query.filters).toEqual({name: ['one']});
    });

  it('keeps two same-model pages, counts and pagination independent',
    async () => {
      const left = await mount({filters: {name: 'left'}, limit: 1});
      const right = await mount({filters: {name: 'right'}, limit: 1});
      reply(lastRequest(left), [row(1)], 3);
      reply(lastRequest(right), [row(2)], 1);
      await settle();
      expect(left.value).toEqual([row(1).$id]);
      expect(right.value).toEqual([row(2).$id]);
      expect(left.meta.total).toBe(3);
      expect(right.meta.total).toBe(1);
      expect(left.paging.hidden).toBe(false);
      expect(right.paging.hidden).toBe(true);
      left.loadMore();
      expect(lastRequest(left).data.offset).toBe(1);
      reply(lastRequest(left), [row(3)], 3);
      expect(left.value).toEqual([row(1).$id, row(3).$id]);
      expect(right.value).toEqual([row(2).$id]);
      expect(right.meta.offset).toBe(0);
    });

  it('discovers renamed collection actions and declared routes', async () => {
    schema.methods.FIND = {
      ...schema.methods.SEARCH, route: '/queries/find',
    };
    delete schema.methods.SEARCH;
    const list = await mount({method: 'FIND'});
    expect(lastRequest(list).target).toBe(`${schema.$id}/queries/find`);
    reply(lastRequest(list), [row(1)]);
    expect(list.state).toBe('ready');
  });

  it('accepts short pages and advances by received rows, not the limit',
    async () => {
      const list = await mount({limit: 20});
      reply(lastRequest(list), [row(1), row(2)], 7);
      expect(list.state).toBe('ready');
      list.loadMore();
      expect(lastRequest(list).data.offset).toBe(2);
      reply(lastRequest(list), [row(3)], 7);
      list.loadMore();
      expect(lastRequest(list).data.offset).toBe(3);
      expect(list.value).toEqual([row(1).$id, row(2).$id, row(3).$id]);
    });

  it('timestamps only accepted successful reads on the performance clock',
    async () => {
      const list = await mount();
      expect(list.completedRead).toBe(0);
      const before = performance.now();
      reply(lastRequest(list), [row(1)]);
      expect(list.completedRead).toBeGreaterThanOrEqual(before);
      expect(list.completedRead).toBeLessThanOrEqual(performance.now());
      list.loadPage();
      expect(list.completedRead).toBe(0);
      matrix.remote.onError(lastRequest(list), {detail: 'Denied'});
      expect(list.completedRead).toBe(0);
      expect(list.state).toBe('error');
    });

  it('hydrates once, emits entity signals and never requests page members',
    async () => {
      const list = await mount();
      const read = vi.spyOn(proto, 'READ');
      const metadata = {total: 400};
      proto._paginationMeta = metadata;
      reply(lastRequest(list), [row(1)]);
      await settle();
      const child = list.items.firstElementChild;
      const entity = NTT.get(`${schema.__name__}/1`);
      const signal = vi.fn();
      entity.signal(signal, true);
      list.loadPage(0, {retain: true});
      reply(lastRequest(list), [row(1, {name: 'Updated'})]);
      await settle();
      expect(read).toHaveBeenCalledTimes(2);
      expect(read.mock.calls.every(([data]) => Array.isArray(data))).toBe(true);
      expect(signal).toHaveBeenCalledTimes(1);
      expect(entity.value.name).toBe('Updated');
      expect(child.value.name).toBe('Updated');
      expect(list.items.firstElementChild).toBe(child);
      expect(proto._paginationMeta).toBe(metadata);
      expect(requests.mock.calls.map(([request]) => request.name))
        .toEqual(['CREATE', 'CREATE']);
    });

  it('does not adopt global cache membership on READ, CREATE or DELETE',
    async () => {
      const list = await mount();
      reply(lastRequest(list), [row(1)]);
      proto.READ([row(2)]);
      proto.CREATE(row(3));
      proto.DELETE({}, {source: row(2).$id});
      list.UPDATE([`${schema.__name__}/99`]);
      expect(list.value).toEqual([row(1).$id]);
      expect(list.meta.total).toBe(1);
      expect(requests).toHaveBeenCalledTimes(1);
    });

  it('rejects old queries, late errors and wrong response provenance',
    async () => {
      const list = await mount();
      const old = lastRequest(list);
      list.query = {query: 'new'};
      const current = lastRequest(list);
      reply(old, [row(1)]);
      matrix.remote.onError(old, {detail: 'Old denied request'});
      const data = {
        data: [row(1)],
        meta: {total: 1, limit: 20, offset: 0, has_more: false},
      };
      list.RESULT(data, {
        source: 'http://untrusted/search', target: list.addr,
        meta: current.meta,
      });
      list.RESULT(data, {
        source: current.target, target: 'another-list', meta: current.meta,
      });
      expect(list.value).toEqual([]);
      expect(list.pending.correlation).toBe(current.meta.correlation);
      reply(current, [row(2)]);
      expect(list.value).toEqual([row(2).$id]);
      expect(list.state).toBe('ready');
    });

  it('retires pending replies when a subclass defers the replacement query',
    async () => {

      /** Model an adapter whose disabled guard defers native page loading. */
      class DeferredLoadList extends customElements.get('ntx-list') {

        /** Respect the adapter guard before dispatching a native page.
         * @param {number} [offset=0] Requested native page offset.
         * @param {Object} [options={}] Native page loading options.
         * @param {boolean} [options.retain=false] Retain the accepted page.
         * @param {boolean} [options.append=false] Append returned records.
         * @returns {void} */
        loadPage(offset = 0, options = {}) {
          // 0. Defer dispatch without changing native query or reply handling.
          if (this.hasAttribute('disabled')) return;
          super.loadPage(offset, options);
        }
      }
      // 0. Keep query A pending before the adapter blocks new page dispatch.
      const tag = `deferred-load-query-list-${serial}`;
      customElements.define(tag, DeferredLoadList);
      const list = document.createElement(tag);
      list.query = {query: 'A'};
      list.model = schema.__name__;
      document.body.append(list);
      await settle();
      const old = lastRequest(list);
      expect(old.data.query).toBe('A');
      expect(list.pending.correlation).toBe(old.meta.correlation);
      list.setAttribute('disabled', '');
      list.query = {query: 'B'};
      // 1. Changing authority must retire A even before B can be dispatched.
      expect(requests).toHaveBeenCalledTimes(1);
      expect(list.pending).toBeNull();
      reply(old, [row(1)]);
      await settle();
      expect(proto.instances.size).toBe(0);
      expect(NTT.get(`${schema.__name__}/1`)).toBeUndefined();
      expect(list.value).toEqual([]);
      expect(list.meta).toBeNull();
      expect(list.hasCurrentPage).toBe(false);
      expect(requests).toHaveBeenCalledTimes(1);
      // 2. Releasing the guard permits only B to establish the current page.
      list.removeAttribute('disabled');
      list.loadPage();
      const current = lastRequest(list);
      expect(requests).toHaveBeenCalledTimes(2);
      expect(current.meta.correlation).not.toBe(old.meta.correlation);
      expect(current.data).toMatchObject({query: 'B', offset: 0});
      reply(current, [row(2)]);
      expect(list.value).toEqual([row(2).$id]);
      expect(list.hasCurrentPage).toBe(true);
      expect(proto.instances.size).toBe(1);
    });

  it('rejects changed caller and role snapshots before publishing records',
    async () => {
      const list = await mount();
      const old = lastRequest(list);
      permissions.user = {user_id: 8, role: 'staff'};
      reply(old, [row(1)]);
      expect(proto.instances.size).toBe(0);
      expect(list.value).toEqual([]);
      expect(list.pending).toBeNull();
      expect(list.state).toBe('error');
      expect(list.error).toMatch(/login|model/i);
      await settle();
      expect(list.items.hidden).toBe(true);
      expect(list.next.textContent).toBe('Retry');
      list.loadPage();
      const changedRole = lastRequest(list);
      permissions.user.role = 'client';
      reply(changedRole, [row(2)]);
      expect(proto.instances.size).toBe(0);
      list.loadPage();
      reply(lastRequest(list), [row(3)]);
      expect(list.value).toEqual([row(3).$id]);
    });

  it('retargets model safely and ignores old schema callbacks', async () => {
    const list = await mount();
    const old = lastRequest(list);
    const oldProto = proto;
    schema = modelSchema();
    proto = NTT.get(schema.__name__);
    list.setAttribute('model', schema.__name__);
    await settle();
    list.define(oldProto);
    expect(list.proto).toBe(proto);
    reply(old, [row(1)]);
    expect(list.value).toEqual([]);
    reply(lastRequest(list), [row(2)]);
    expect(list.value).toEqual([row(2).$id]);
  });

  it('resumes the original model after a rapid A/B/A retarget', async () => {
    const list = await mount();
    const original = schema;
    const oldRequest = lastRequest(list);
    list.model = 'UnresolvedQueryModel';
    list.model = original.__name__;
    await settle();
    expect(lastRequest(list).meta.correlation)
      .not.toBe(oldRequest.meta.correlation);
    reply(lastRequest(list), [row(1)]);
    expect(list.state).toBe('ready');
  });

  it('does not accept a page after its schema identity changes', async () => {
    const list = await mount();
    const request = lastRequest(list);
    list.schema = {...schema, $id: 'http://other.example/Model'};
    reply(request, [row(1)]);
    expect(proto.instances.size).toBe(0);
    expect(list.hasCurrentPage).toBe(false);
    expect(list.state).toBe('error');
  });

  it('does not overwrite a request started by a native hydration observer',
    async () => {
      const list = await mount();
      const first = lastRequest(list);
      const unsubscribe = proto.observe('UPDATE', () => {
        list.query = {query: 'changed during hydration'};
      });
      reply(first, [row(1)]);
      unsubscribe();
      expect(list.pending.correlation).not.toBe(first.meta.correlation);
      expect(list.value).toEqual([]);
      reply(lastRequest(list), [row(2)]);
      expect(list.value).toEqual([row(2).$id]);
    });

  it('invalidates detached reads and resumes with a fresh request',
    async () => {
      const list = await mount();
      const old = lastRequest(list);
      list.remove();
      reply(old, [row(1)]);
      expect(proto.instances.size).toBe(0);
      document.body.append(list);
      await settle();
      const current = lastRequest(list);
      expect(current.meta.correlation).not.toBe(old.meta.correlation);
      reply(old, [row(1)]);
      reply(current, [row(2)]);
      expect(list.value).toEqual([row(2).$id]);
    });

  it('waits until connected and schema-ready before sending the query',
    async () => {
      const list = document.createElement('ntx-list');
      list.query = {};
      list.model = schema.__name__;
      list.define(proto);
      list.query = {query: 'changed'};
      expect(requests).not.toHaveBeenCalled();
      document.body.append(list);
      await settle();
      expect(requests).toHaveBeenCalledTimes(1);
      expect(lastRequest(list).data.query).toBe('changed');
    });

  it('ignores delayed schema delivery after disconnect and resumes on attach',
    async () => {
      const list = document.createElement('ntx-list');
      const name = `DeferredQueryList${++serial}`;
      const delayed = {
        ...schema, __name__: name, __tablename__: name,
        $id: `http://localhost:5000/${name}`,
      };
      list.query = {};
      list.model = name;
      document.body.append(list);
      expect(lastRequest(list)).toBeUndefined();
      list.remove();
      NTT.SCHEMA(delayed);
      await settle();
      expect(lastRequest(list)).toBeUndefined();
      document.body.append(list);
      await settle();
      expect(lastRequest(list).target).toBe(`${delayed.$id}/search`);
    });

  it.each([
    {},
    {route: '/search', methods: ['GET'], requires_instance: false},
    {route: '/search', methods: ['POST'], requires_instance: true},
    {route: '//other.example', methods: ['POST'], requires_instance: false},
  ])('fails closed for unsupported method metadata %j', async method => {
    schema.methods.SEARCH = method;
    const list = await mount();
    expect(list.state).toBe('error');
    expect(list.completedRead).toBe(0);
    expect(requests).not.toHaveBeenCalled();
  });

  it.each([
    null,
    {data: []},
    {data: [], meta: {total: -1, limit: 20, offset: 0, has_more: false}},
    {data: [], meta: {total: 0, limit: 5, offset: 0, has_more: false}},
    {data: [], meta: {total: 0, limit: 20, offset: 2, has_more: false}},
    {data: [], meta: {total: 1, limit: 20, offset: 0, has_more: true}},
  ])('rejects malformed page envelopes %j without fallback', async data => {
    const list = await mount();
    matrix.remote.httpCallback(lastRequest(list), data);
    expect(list.state).toBe('error');
    expect(list.hasCurrentPage).toBe(false);
    expect(proto.instances.size).toBe(0);
    expect(requests).toHaveBeenCalledTimes(1);
  });

  it('validates all row identities before partially hydrating a page',
    async () => {
      const list = await mount();
      reply(lastRequest(list), [row(1), row(2, {$schema: 'wrong'})]);
      expect(list.state).toBe('error');
      expect(proto.instances.size).toBe(0);
    });

  it('keeps failed-page controllers hidden and supports native retry',
    async () => {
      const list = await mount({limit: 1});
      reply(lastRequest(list), [row(1)], 2);
      await settle();
      const child = list.items.firstElementChild;
      list.loadMore();
      matrix.remote.onError(lastRequest(list), {detail: 'Access denied'});
      await settle();
      expect(list.items.hidden).toBe(true);
      expect(list.items.inert).toBe(true);
      expect(list.items.firstElementChild).toBe(child);
      expect(list.status.textContent).toBe('Access denied');
      expect(list.status.getAttribute('role')).toBe('alert');
      expect(list.dataset.state).toBe('error');
      expect(list.next.textContent).toBe('Retry');
      list.next.click();
      expect(lastRequest(list).data.offset).toBe(1);
      reply(lastRequest(list), [row(2)], 2);
      await settle();
      expect(list.value).toEqual([row(1).$id, row(2).$id]);
      expect(list.items.hidden).toBe(false);
      expect(list.items.firstElementChild).toBe(child);
    });

  it('emits generic accepted-page and rendered notifications', async () => {
    const list = await mount();
    const loaded = vi.fn();
    const rendered = vi.fn();
    document.addEventListener('ntx:page-loaded', loaded, {once: true});
    document.addEventListener('ntx:list-rendered', rendered, {once: true});
    reply(lastRequest(list), []);
    await settle();
    expect(list.state).toBe('empty');
    expect(loaded).toHaveBeenCalledTimes(1);
    expect(loaded.mock.calls[0][0].composed).toBe(true);
    expect(loaded.mock.calls[0][0].detail.value).toEqual([]);
    expect(rendered).toHaveBeenCalledTimes(1);
  });
});

describe('stable native list presentation', () => {
  it('supports borrowing the child factory without ListElement private state',
    () => {
      const owner = document.createElement('div');
      owner.childTag = 'div';
      owner.childDisplay = 'md';
      owner.model = schema.__name__;
      owner.addr = 'borrowed-factory';
      const child = ListElement.prototype.createChild.call(owner, row(1).$id);
      expect(child.ref).toBe(row(1).$id);
      expect(child.getAttribute('select-target')).toBe(owner.addr);
      expect(child.getAttribute('display')).toBe('md');
    });

  it('distinguishes empty pages and collections and projects native state',
    async () => {
      const list = await mount();
      expect(list.dataset.state).toBe('loading');
      reply(lastRequest(list), []);
      await settle();
      const emptyCollection = list.status.textContent;
      expect(list.dataset.state).toBe('empty');
      expect(list.status.getAttribute('role')).toBe('status');
      list.loadPage(20);
      reply(lastRequest(list), [], 7);
      await settle();
      expect(list.status.textContent).not.toBe(emptyCollection);
      expect(list.status.textContent).toMatch(/page/i);
      expect(list.dataset.state).toBe('empty');
      list.loadPage();
      reply(lastRequest(list), [row(1)]);
      await settle();
      expect(list.dataset.state).toBe('ready');
    });

  it('physically reorders default items and rebinds native subscriptions',
    async () => {
      const list = await mount();
      reply(lastRequest(list), [row(1), row(2), row(3)]);
      await settle();
      const refs = [list.items, list.heading, list.status, list.create,
        list.refresh, list.paging, list.next];
      const children = [...list.items.children];
      children[0].draft = {text: 'unsaved'};
      list.render();
      expect([...list.items.children]).toEqual(children);
      list.loadPage(0, {retain: true});
      reply(lastRequest(list), [row(3), row(1), row(2)]);
      await settle();
      expect([...list.items.children])
        .toEqual([children[2], children[0], children[1]]);
      expect(list.hasAttribute('data-order-deferred')).toBe(false);
      expect(list.value).toEqual([row(3).$id, row(1).$id, row(2).$id]);
      expect(children.every(child => child.style.order === '')).toBe(true);
      expect(children[0].draft).toEqual({text: 'unsaved'});
      expect([list.items, list.heading, list.status, list.create,
        list.refresh, list.paging, list.next]).toEqual(refs);
      proto.READ(row(3, {name: 'Still subscribed after reorder'}));
      expect(children[2].value.name).toBe('Still subscribed after reorder');
    });

  it('keeps nested focus and child subscriptions through an order-only change',
    async () => {
      const list = await mount();
      reply(lastRequest(list), [row(1), row(2)]);
      await settle();
      const child = list.items.firstElementChild;
      const input = document.createElement('input');
      child.shadowRoot.append(input);
      input.value = 'unfinished';
      input.focus();
      input.setSelectionRange(2, 5);
      list.value = [row(2).$id, row(1).$id];
      list.render();
      expect(child.shadowRoot.activeElement).toBe(input);
      expect(input.value).toBe('unfinished');
      expect([input.selectionStart, input.selectionEnd]).toEqual([2, 5]);
      expect(list.items.lastElementChild).toBe(child);
      expect(child.style.order).toBe('');
      expect(list.hasAttribute('data-order-deferred')).toBe(false);
      proto.READ(row(1, {name: 'New cached value'}));
      expect(child.value.name).toBe('New cached value');
    });

  it('visibly blocks unsafe retained moves and retries after release',
    async () => {
      const list = await mount();
      reply(lastRequest(list), [row(1), row(2)]);
      await settle();
      const children = [...list.items.children];
      list.retainChild = () => true;
      children[0].draft = {text: 'retained draft'};
      list.value = [row(2).$id, row(1).$id];
      list.render();
      expect([...list.items.children]).toEqual(children);
      expect(list.hasAttribute('data-order-deferred')).toBe(true);
      expect(list.status.hidden).toBe(false);
      expect(list.status.textContent).toMatch(/order not applied/i);
      expect(children[0].draft.text).toBe('retained draft');
      list.retainChild = () => false;
      list.render();
      expect([...list.items.children]).toEqual(children.reverse());
      expect(list.hasAttribute('data-order-deferred')).toBe(false);
      expect(list.status.hidden).toBe(true);
    });

  it('moves safe siblings around a retained focused anchor', async () => {
    const list = await mount();
    reply(lastRequest(list), [row(1), row(2), row(3)]);
    await settle();
    const children = [...list.items.children];
    const retained = children[2];
    list.retainChild = child => child === retained;
    const input = document.createElement('input');
    retained.shadowRoot.append(input);
    input.focus();
    list.query = {order_by: 'id', direction: 'desc'};
    reply(lastRequest(list), [row(3), row(2), row(1)]);
    await settle();
    expect([...list.items.children]).toEqual(children.reverse());
    expect(retained.shadowRoot.activeElement).toBe(input);
    expect(list.hasAttribute('data-order-deferred')).toBe(false);
    proto.READ(row(1, {name: 'Rebound after query change'}));
    expect(children[2].value.name).toBe('Rebound after query change');
  });

  it('checks shadow descendants before moving a retained native host',
    async () => {
      const list = await mount();
      reply(lastRequest(list), [row(1), row(2)]);
      await settle();
      const disconnected = vi.fn();

      /** Foreign controller with destructive lifecycle and an open root. */
      class UnsafeChild extends HTMLElement {

        /** Create an inspectable custom subtree. */
        constructor() {
          super();
          this.attachShadow({mode: 'open'});
        }

        /** Expose unintended disconnection to the test.
         * @returns {void} */
        disconnectedCallback() { disconnected(); }
      }
      const tag = `unsafe-query-child-${serial}`;
      customElements.define(tag, UnsafeChild);
      const children = [...list.items.children];
      for (const child of children) {
        child.shadowRoot.append(document.createElement(tag));
      }
      list.retainChild = () => true;
      list.items.moveBefore = vi.fn();
      list.value = [row(2).$id, row(1).$id];
      list.render();
      expect(list.items.moveBefore).not.toHaveBeenCalled();
      expect(disconnected).not.toHaveBeenCalled();
      expect([...list.items.children]).toEqual(children);
      expect(list.status.hidden).toBe(false);
      expect(list.status.textContent).toMatch(/order not applied/i);
    });

  it('retains drafts without adding membership or inflating counts',
    async () => {
      const list = await mount();
      reply(lastRequest(list), [row(1)]);
      await settle();
      const child = list.items.firstElementChild;
      list.retainChild = item => item === child;
      list.loadPage();
      reply(lastRequest(list), [row(2)]);
      await settle();
      expect(list.items.contains(child)).toBe(true);
      expect(child.hidden).toBe(false);
      expect(list.value).toEqual([row(2).$id]);
      expect(list.shadowRoot.querySelector('.list-count').textContent)
        .toBe('1 / 1');
    });

  it('hides and inerts retained controllers after a caller change',
    async () => {
      const list = await mount();
      reply(lastRequest(list), [row(1)]);
      await settle();
      const oldChild = list.items.firstElementChild;
      list.retainChild = () => true;
      permissions.user = {user_id: 9, role: 'staff'};
      list.loadPage(0, {retain: true});
      await settle();
      expect(list.items.hidden).toBe(true);
      reply(lastRequest(list), [row(1)]);
      await settle();
      expect(list.items.children).toHaveLength(2);
      expect(list.items.firstElementChild).not.toBe(oldChild);
      expect(oldChild.hidden).toBe(true);
      expect(oldChild.inert).toBe(true);
      expect(list.value).toHaveLength(1);
    });

  it('supports presentation filtering without changing accepted membership',
    async () => {
      const list = await mount();
      const factory = vi.spyOn(list, 'createChild');
      list.isVisibleRecord = record => record?.id !== 1;
      reply(lastRequest(list), [row(1), row(2)]);
      await settle();
      expect(factory).toHaveBeenCalledTimes(1);
      expect(factory).toHaveBeenCalledWith(row(2).$id);
      expect(list.items.children).toHaveLength(1);
      expect(list.items.children[0].hidden).toBe(false);
      expect(list.value).toHaveLength(2);
      expect(list.meta.total).toBe(2);
    });

  it('keeps retained old-model controllers hidden after retarget', async () => {
    const list = await mount();
    reply(lastRequest(list), [row(1)]);
    await settle();
    const oldChild = list.items.firstElementChild;
    list.retainChild = () => true;
    schema = modelSchema();
    list.model = schema.__name__;
    reply(lastRequest(list), [row(1)]);
    await settle();
    expect(list.items.contains(oldChild)).toBe(true);
    expect(oldChild.hidden).toBe(true);
    expect(oldChild.inert).toBe(true);
    expect(list.value).toEqual([row(1).$id]);
  });

  it('lets the retained-visibility hook suppress protected controllers',
    async () => {
      const list = await mount();
      reply(lastRequest(list), [row(1)]);
      await settle();
      const child = list.items.firstElementChild;
      list.retainChild = () => true;
      list.isVisibleRecord = record => record?.id !== 1;
      list.isVisibleRetainedChild = () => false;
      list.loadPage();
      reply(lastRequest(list), [row(2)]);
      await settle();
      expect(list.items.contains(child)).toBe(true);
      expect(child.hidden).toBe(true);
      expect(child.inert).toBe(true);
      expect(list.value).toEqual([row(2).$id]);
    });

  it('inserts new children in actual DOM order without moving live siblings',
    async () => {
      const list = await mount();
      reply(lastRequest(list), [row(2)]);
      await settle();
      const existing = list.items.firstElementChild;
      list.loadPage(0, {retain: true});
      reply(lastRequest(list), [row(1), row(2), row(3)]);
      await settle();
      expect([...list.items.children].map(child => child.dataset.value))
        .toEqual([row(1).$id, row(2).$id, row(3).$id]);
      expect(list.items.children[1]).toBe(existing);
      expect(list.hasAttribute('data-order-deferred')).toBe(false);
      proto.READ(row(2, {name: 'Still subscribed'}));
      expect(existing.value.name).toBe('Still subscribed');
    });

  it.each([false, true])('updates reused child displays; query=%s',
    async query => {
      const list = query ? await mount() : document.createElement('ntx-list');
      if (query) reply(lastRequest(list), [row(1)]);
      else {
        list.model = schema.__name__;
        list.schema = schema;
        list.value = [row(1).$id];
      }
      list.render();
      const child = list.items.firstElementChild;
      list.setAttribute('display', 'xl');
      list.render();
      expect(list.items.firstElementChild).toBe(child);
      expect(child.getAttribute('display')).toBe('md');
      list.setAttribute('display', 'sm');
      list.render();
      expect(child.getAttribute('display')).toBe('xs');
    });

  it('preserves explicit template displays when the list display changes',
    async () => {
      const list = await mount();
      const template = document.createElement('template');
      template.setAttribute('item-template', '');
      template.innerHTML = '<ntx-item display="row"></ntx-item>';
      list.appendChild(template);
      reply(lastRequest(list), [row(1)]);
      await settle();
      const child = list.items.firstElementChild;
      list.setAttribute('display', 'xl');
      list.render();
      expect(list.items.firstElementChild).toBe(child);
      expect(child.getAttribute('display')).toBe('row');
    });

  it('keeps same-context retained conversations visible despite row filters',
    async () => {
      const list = await mount();
      reply(lastRequest(list), [row(1)]);
      await settle();
      const child = list.items.firstElementChild;
      list.retainChild = item => item === child;
      list.isVisibleRecord = record => record?.id !== 1;
      list.render();
      expect(child.hidden).toBe(false);
      list.loadPage();
      reply(lastRequest(list), [row(2)]);
      await settle();
      expect(child.hidden).toBe(false);
      expect(list.value).toEqual([row(2).$id]);
      list.failPage('Source read failed');
      list.render();
      expect(list.items.hidden).toBe(true);
      expect(child.hidden).toBe(true);
      expect(child.inert).toBe(true);
    });

  it.each(['ready', 'error'])('clears old caller counts and %s status',
    async state => {
      const list = await mount();
      reply(lastRequest(list), [row(1)], 12);
      await settle();
      if (state === 'error') list.failPage('Private old-caller error');
      permissions.user = {user_id: 99, role: 'staff'};
      list.loadPage = vi.fn();
      list.render();
      expect(list.value).toEqual([]);
      expect(list.meta).toBeNull();
      expect(list.shadowRoot.querySelector('.list-count').textContent)
        .toBe('0');
      expect(list.status.textContent).not.toContain('Private');
      expect(list.status.textContent).toMatch(/login|model/i);
      expect(list.items.hidden).toBe(true);
    });

  it('inserts schema titles, descriptions and create labels as text',
    async () => {
      const injection = '<img src=x onerror=alert(1)>';
      schema.ui = {description: injection, create_label: injection};
      const list = await mount();
      list.setAttribute('allow-create', '');
      list.render();
      expect(list.shadowRoot.querySelector('img')).toBeNull();
      expect(list.shadowRoot.querySelector('.list-description').textContent)
        .toBe(injection);
      expect(list.create.textContent).toContain(injection);
    });

  it('preserves legacy shared READ and load-more behavior without queries',
    async () => {
      const list = document.createElement('ntx-list');
      const call = vi.spyOn(proto, 'call').mockImplementation(() => {});
      list.model = schema.__name__;
      list.define(proto);
      expect(list.query).toBeNull();
      expect(call).toHaveBeenCalledWith('READ', {
        limit: 20, offset: 0, depth: 1,
      }, {inbox: 'UPDATE'});
      proto.READ([row(1), row(2)]);
      expect(list.value).toEqual([
        `${schema.__name__}/1`, `${schema.__name__}/2`,
      ]);
      list.loadMore();
      expect(call).toHaveBeenLastCalledWith('READ', {
        limit: 20, offset: 20, depth: 1,
      }, {inbox: 'UPDATE'});
      list.disconnectedCallback();
    });

  it('starts fresh query paging after adopting legacy cache membership',
    async () => {
      // 0. Query A owns a page distinct from the larger shared model cache.
      const list = await mount({query: 'A', limit: 2});
      reply(lastRequest(list), [row(1), row(2)], 9);
      proto.READ(row(3));
      list.query = null;
      expect(list.query).toBeNull();
      expect(list.value).toEqual([
        `${schema.__name__}/1`, `${schema.__name__}/2`,
        `${schema.__name__}/3`,
      ]);
      const count = requests.mock.calls.length;
      // 1. Legacy cache membership and A's metadata cannot satisfy query B.
      list.query = {query: 'B', limit: 3};
      await settle();
      expect(requests).toHaveBeenCalledTimes(count + 1);
      const first = lastRequest(list);
      expect(first.name).toBe('CREATE');
      expect(first.data).toMatchObject({query: 'B', limit: 3, offset: 0});
      expect(list.value).toEqual([]);
      expect(list.meta).toBeNull();
      expect(list.hasCurrentPage).toBe(false);
      reply(first, [row(10)], 4);
      expect(list.value).toEqual([row(10).$id]);
      expect(list.meta).toEqual({
        total: 4, limit: 3, offset: 0, has_more: true,
      });
      // 2. Append advances by B's received rows, not A or global cache size.
      list.loadMore();
      expect(requests).toHaveBeenCalledTimes(count + 2);
      const append = lastRequest(list);
      expect(append.data).toMatchObject({query: 'B', limit: 3, offset: 1});
      reply(append, [row(11), row(12)], 4);
      expect(list.value).toEqual([row(10).$id, row(11).$id, row(12).$id]);
      expect(list.meta).toEqual({
        total: 4, limit: 3, offset: 1, has_more: true,
      });
    });

  it('can return from a query to legacy shared-cache membership', async () => {
    const list = await mount();
    reply(lastRequest(list), [row(1)]);
    proto.READ(row(2));
    list.query = null;
    expect(list.value).toEqual([
      `${schema.__name__}/1`, `${schema.__name__}/2`,
    ]);
    expect(list.query).toBeNull();
  });
});

/* Changelog
 * - 2026-10-28: Guard query/legacy mode transitions and retire stale replies
 *   when a subclass defers dispatch of the replacement query.
 * - 2026-10-26: Cover query ownership, reply guards and stable rendering.
 *   Cover short pages, borrowed factories, timestamps and native status.
 *   Verify physical reorder, subscriptions and visible retained-move limits.
 *   Cover canonical query objects, strict JSON binding and invalid recovery. */
