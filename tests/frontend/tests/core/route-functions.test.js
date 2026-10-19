import { describe, it, expect, vi } from 'vitest';

vi.mock('../../utils/Assert.js', () => ({
  default: vi.fn((caller, cond, msg) => {
    if (!cond) throw new Error(msg || 'Assertion failed');
  }),
  caution: vi.fn(), inform: vi.fn(),
}));
vi.mock('../../config.js', () => ({
  config: { LOGGING: 3, LOGEVENTS: true, DEBUG: true, API_URL: 'http://localhost:5000',
    E: { CONNECT: 'CONNECT', UPDATE: 'UPDATE', READ: 'READ', NAVIGATE: 'NAVIGATE', BACK: 'BACK' }
  }
}));
vi.mock('../../utils/Logging.js', () => ({
  default: { warn: vi.fn(), error: vi.fn(), debug: vi.fn(), dev: vi.fn(), log: vi.fn(), init: vi.fn(), event: vi.fn() }
}));

import { parseRoute, buildRoute, resolveRoute } from '../../core/Router.js';

// ── parseRoute ──

describe('parseRoute(route)', () => {

  it('null → { type: "home" }', () => {
    expect(parseRoute(null)).toEqual({ type: 'home' });
  });

  it('empty string → { type: "home" }', () => {
    expect(parseRoute('')).toEqual({ type: 'home' });
  });

  it('undefined → { type: "home" }', () => {
    expect(parseRoute(undefined)).toEqual({ type: 'home' });
  });

  it('non-string → { type: "home" }', () => {
    expect(parseRoute(42)).toEqual({ type: 'home' });
    expect(parseRoute({})).toEqual({ type: 'home' });
  });

  it('@profile → app route', () => {
    expect(parseRoute('@profile')).toEqual({
      type: 'app', app: 'profile', params: {},
    });
  });

  it('@settings?tab=security → app route with params', () => {
    expect(parseRoute('@settings?tab=security')).toEqual({
      type: 'app', app: 'settings', params: { tab: 'security' },
    });
  });

  it('Product → model route', () => {
    expect(parseRoute('Product')).toEqual({
      type: 'model', model: 'Product', id: null, action: null, params: {},
    });
  });

  it('Grant?view=table&allow-create= → model with params', () => {
    expect(parseRoute('Grant?view=table&allow-create=')).toEqual({
      type: 'model', model: 'Grant', id: null, action: null,
      params: { view: 'table', 'allow-create': '' },
    });
  });

  it('Product/3 → detail route', () => {
    expect(parseRoute('Product/3')).toEqual({
      type: 'detail', model: 'Product', id: '3', action: null, params: {},
    });
  });

  it('Grant/5/analyze → action route', () => {
    expect(parseRoute('Grant/5/analyze')).toEqual({
      type: 'action', model: 'Grant', id: '5', action: 'analyze', params: {},
    });
  });

  it('Product/@ → collection default view route', () => {
    expect(parseRoute('Product/@')).toEqual({
      type: 'model', model: 'Product', id: null, action: null,
      view: null, isViewRoute: true, params: {},
    });
  });

  it('Product/@table → named collection view route', () => {
    expect(parseRoute('Product/@table')).toEqual({
      type: 'model', model: 'Product', id: null, action: null,
      view: 'table', isViewRoute: true, params: {},
    });
  });

  it('named collection view routes preserve view names and params', () => {
    expect(parseRoute('Product/@list').view).toBe('list');
    expect(parseRoute('Product/@custom-card').view).toBe('custom-card');
    expect(parseRoute('Product/@ntx-custom-card').view).toBe('ntx-custom-card');
    expect(parseRoute('Product/@0').view).toBe('0');
    expect(parseRoute('Product/@table?limit=10&offset=20').params)
      .toEqual({ limit: '10', offset: '20' });
  });

  it('unsafe collection view tokens and extra segments are invalid', () => {
    expect(parseRoute('Product/@/extra').type).toBe('invalid');
    expect(parseRoute('Product/@table/extra').type).toBe('invalid');
    expect(parseRoute('Product/@../../x').type).toBe('invalid');
    expect(parseRoute('Product/@%2e%2e').type).toBe('invalid');
    expect(parseRoute('Product/@<script>').type).toBe('invalid');
  });

  it('Product/1/@ → member default view route', () => {
    expect(parseRoute('Product/1/@')).toEqual({
      type: 'detail', model: 'Product', id: '1', action: null,
      view: null, isViewRoute: true, params: {},
    });
  });

  it('Product/1/@item → named member view route', () => {
    expect(parseRoute('Product/1/@item')).toEqual({
      type: 'detail', model: 'Product', id: '1', action: null,
      view: 'item', isViewRoute: true, params: {},
    });
  });

  it('named member view routes preserve view names and params', () => {
    expect(parseRoute('Product/1/@detail').view).toBe('detail');
    expect(parseRoute('Product/1/@chat').view).toBe('chat');
    expect(parseRoute('Product/1/@custom-card').view).toBe('custom-card');
    expect(parseRoute('Product/1/@0').view).toBe('0');
    expect(parseRoute('Product/1/@chat?thread=abc').params)
      .toEqual({ thread: 'abc' });
  });

  it('unsafe member view tokens and extra segments are invalid', () => {
    expect(parseRoute('Product/1/@/extra').type).toBe('invalid');
    expect(parseRoute('Product/1/@item/extra').type).toBe('invalid');
    expect(parseRoute('Product/1/@../../x').type).toBe('invalid');
    expect(parseRoute('Product/1/@%2e%2e').type).toBe('invalid');
    expect(parseRoute('Product/1/@<script>').type).toBe('invalid');
  });

  it('method and same-named member view routes remain distinct', () => {
    expect(parseRoute('Product/1/run')).toEqual({
      type: 'action', model: 'Product', id: '1', action: 'run', params: {},
    });
    expect(parseRoute('Product/1/@run')).toEqual({
      type: 'detail', model: 'Product', id: '1', action: null,
      view: 'run', isViewRoute: true, params: {},
    });
  });

  it('nested class-name routes parse as nested collection/detail/action/view routes', () => {
    expect(parseRoute('Product/1/Comment')).toEqual({
      type: 'nested-collection', parentModel: 'Product', parentId: '1',
      model: 'Comment', id: null, action: null, params: {},
    });
    expect(parseRoute('Product/1/Comment/@table')).toEqual({
      type: 'nested-collection', parentModel: 'Product', parentId: '1',
      model: 'Comment', id: null, action: null,
      view: 'table', isViewRoute: true, params: {},
    });
    expect(parseRoute('Product/1/Comment/2')).toEqual({
      type: 'nested-detail', parentModel: 'Product', parentId: '1',
      model: 'Comment', id: '2', action: null, params: {},
    });
    expect(parseRoute('Product/1/Comment/2/@item')).toEqual({
      type: 'nested-detail', parentModel: 'Product', parentId: '1',
      model: 'Comment', id: '2', action: null,
      view: 'item', isViewRoute: true, params: {},
    });
    expect(parseRoute('Product/1/Comment/2/like')).toEqual({
      type: 'nested-action', parentModel: 'Product', parentId: '1',
      model: 'Comment', id: '2', action: 'like', params: {},
    });
  });

  it('nested default view routes and params parse deterministically', () => {
    expect(parseRoute('Product/1/Comment/@')).toEqual({
      type: 'nested-collection', parentModel: 'Product', parentId: '1',
      model: 'Comment', id: null, action: null,
      view: null, isViewRoute: true, params: {},
    });
    expect(parseRoute('Product/1/Comment/2/@')).toEqual({
      type: 'nested-detail', parentModel: 'Product', parentId: '1',
      model: 'Comment', id: '2', action: null,
      view: null, isViewRoute: true, params: {},
    });
    expect(parseRoute('Product/1/Comment/2/@item?tab=history').params)
      .toEqual({ tab: 'history' });
  });

  it('invalid nested class-name route boundaries are deterministic', () => {
    expect(parseRoute('Product/1/Comment/2/@/extra')).toMatchObject({
      type: 'invalid', reason: 'too_many_segments',
    });
    expect(parseRoute('Product/1/Comment/2/@item/extra')).toMatchObject({
      type: 'invalid', reason: 'too_many_segments',
    });
    expect(parseRoute('Product/1/Comment/2/like/extra')).toMatchObject({
      type: 'invalid', reason: 'too_many_segments',
    });
  });

  it('nested action and same-named nested view routes remain distinct', () => {
    expect(parseRoute('Product/1/Comment/2/like').type).toBe('nested-action');
    expect(parseRoute('Product/1/Comment/2/@like')).toMatchObject({
      type: 'nested-detail', isViewRoute: true, view: 'like', action: null,
    });
  });

  it('member default view route preserves params', () => {
    expect(parseRoute('Product/1/@?tab=history')).toEqual({
      type: 'detail', model: 'Product', id: '1', action: null,
      view: null, isViewRoute: true, params: { tab: 'history' },
    });
  });

  it('Product/3?expanded=true → detail with params', () => {
    expect(parseRoute('Product/3?expanded=true')).toEqual({
      type: 'detail', model: 'Product', id: '3', action: null,
      params: { expanded: 'true' },
    });
  });

  it('Grant/5/analyze?format=pdf → action with params', () => {
    expect(parseRoute('Grant/5/analyze?format=pdf')).toEqual({
      type: 'action', model: 'Grant', id: '5', action: 'analyze',
      params: { format: 'pdf' },
    });
  });
});

// ── buildRoute ──

describe('buildRoute(parts)', () => {

  it('null → empty string', () => {
    expect(buildRoute(null)).toBe('');
  });

  it('{ type: "home" } → empty string', () => {
    expect(buildRoute({ type: 'home' })).toBe('');
  });

  it('app route → @profile', () => {
    expect(buildRoute({ type: 'app', app: 'profile' })).toBe('@profile');
  });

  it('app route with params → @settings?tab=security', () => {
    expect(buildRoute({ type: 'app', app: 'settings', params: { tab: 'security' } }))
      .toBe('@settings?tab=security');
  });

  it('model route → Grant', () => {
    expect(buildRoute({ type: 'model', model: 'Grant' })).toBe('Grant');
  });

  it('model route with params → Grant?view=table', () => {
    expect(buildRoute({ type: 'model', model: 'Grant', params: { view: 'table' } }))
      .toBe('Grant?view=table');
  });

  it('collection default view route → Product/@', () => {
    expect(buildRoute({ type: 'model', model: 'Product', isViewRoute: true }))
      .toBe('Product/@');
  });

  it('named collection view route → Product/@table', () => {
    expect(buildRoute({ type: 'model', model: 'Product', isViewRoute: true, view: 'table' }))
      .toBe('Product/@table');
  });

  it('named collection view route with params → Product/@table?limit=10', () => {
    expect(buildRoute({
      type: 'model', model: 'Product', isViewRoute: true,
      view: 'table', params: { limit: '10' },
    })).toBe('Product/@table?limit=10');
  });

  it('member default view route → Product/1/@', () => {
    expect(buildRoute({ type: 'detail', model: 'Product', id: '1', isViewRoute: true }))
      .toBe('Product/1/@');
  });

  it('member default view route with params → Product/1/@?tab=history', () => {
    expect(buildRoute({
      type: 'detail', model: 'Product', id: '1', isViewRoute: true,
      params: { tab: 'history' },
    })).toBe('Product/1/@?tab=history');
  });

  it('named member view route → Product/1/@item', () => {
    expect(buildRoute({ type: 'detail', model: 'Product', id: '1', isViewRoute: true, view: 'item' }))
      .toBe('Product/1/@item');
  });

  it('named member view route with params → Product/1/@chat?thread=abc', () => {
    expect(buildRoute({
      type: 'detail', model: 'Product', id: '1', isViewRoute: true,
      view: 'chat', params: { thread: 'abc' },
    })).toBe('Product/1/@chat?thread=abc');
  });

  it('detail route → Product/3', () => {
    expect(buildRoute({ type: 'detail', model: 'Product', id: '3' })).toBe('Product/3');
  });

  it('action route → Grant/5/analyze', () => {
    expect(buildRoute({ type: 'action', model: 'Grant', id: '5', action: 'analyze' }))
      .toBe('Grant/5/analyze');
  });

  it('nested routes build canonical nested class-name strings', () => {
    expect(buildRoute({
      type: 'nested-collection', parentModel: 'Product', parentId: '1', model: 'Comment',
    })).toBe('Product/1/Comment');
    expect(buildRoute({
      type: 'nested-detail', parentModel: 'Product', parentId: '1', model: 'Comment', id: '2',
    })).toBe('Product/1/Comment/2');
    expect(buildRoute({
      type: 'nested-detail', parentModel: 'Product', parentId: '1', model: 'Comment', id: '2',
      isViewRoute: true, view: 'item',
    })).toBe('Product/1/Comment/2/@item');
    expect(buildRoute({
      type: 'nested-action', parentModel: 'Product', parentId: '1', model: 'Comment', id: '2', action: 'like',
    })).toBe('Product/1/Comment/2/like');
  });
});

// ── Round-trip ──

describe('parseRoute ↔ buildRoute round-trip', () => {

  const cases = [
    '@profile',
    '@settings?tab=security',
    'Product',
    'Product/3',
    'Product/@',
    'Product/@table',
    'Product/@table?limit=10&offset=20',
    'Product/1/@',
    'Product/1/@?tab=history',
    'Product/1/@item',
    'Product/1/@detail',
    'Product/1/@chat?thread=abc',
    'Product/1/@run',
    'Product/1/Comment',
    'Product/1/Comment/@table',
    'Product/1/Comment/2',
    'Product/1/Comment/2/@',
    'Product/1/Comment/2/@item',
    'Product/1/Comment/2/@item?tab=history',
    'Product/1/Comment/2/like',
    'Grant/5/analyze',
    'Grant?view=table',
  ];

  for (const route of cases) {
    it(`round-trips: "${route}"`, () => {
      expect(buildRoute(parseRoute(route))).toBe(route);
    });
  }

  it('normalizes leading and trailing slashes for named view routes', () => {
    expect(buildRoute(parseRoute('/Product/@table/'))).toBe('Product/@table');
    expect(buildRoute(parseRoute('/Product/1/@item/'))).toBe('Product/1/@item');
  });

  it('invalid routes build to empty string', () => {
    expect(buildRoute(parseRoute('Product/@table/extra'))).toBe('');
    expect(buildRoute(parseRoute('Product/1/@item/extra'))).toBe('');
  });
});

// ── resolveRoute ──

describe('resolveRoute(parsed, getSchema)', () => {

  it('null → null', () => {
    expect(resolveRoute(null)).toBeNull();
  });

  it('home → null', () => {
    expect(resolveRoute({ type: 'home' })).toBeNull();
  });

  it('app route → ntx-{name}', () => {
    const r = resolveRoute({ type: 'app', app: 'profile', params: {} });
    expect(r.tag).toBe('ntx-profile');
    expect(r.title).toBe('Profile');
    expect(r.attrs).toEqual({});
  });

  it('app route passes through params as attrs', () => {
    const r = resolveRoute({ type: 'app', app: 'settings', params: { tab: 'security' } });
    expect(r.tag).toBe('ntx-settings');
    expect(r.attrs).toEqual({ tab: 'security' });
  });

  it('model route with no schema → ntx-list default', () => {
    const r = resolveRoute({ type: 'model', model: 'Product', params: {} });
    expect(r.tag).toBe('ntx-list');
    expect(r.attrs).toEqual({ model: 'Product' });
    expect(r.title).toBe('Product');
  });

  it('model route with schema ui.renderer.list → uses schema', () => {
    const schema = { ui: { renderer: { list: 'ntx-table' } } };
    const r = resolveRoute(
      { type: 'model', model: 'Grant', params: {} },
      () => schema,
    );
    expect(r.tag).toBe('ntx-table');
  });

  it('collection default view route prefers renderer.page', () => {
    const schema = { ui: { renderer: { page: 'ntx-products-page', list: 'ntx-products' } } };
    const r = resolveRoute(parseRoute('Product/@'), () => schema);
    expect(r.tag).toBe('ntx-products-page');
    expect(r.attrs).toEqual({ model: 'Product' });
  });

  it('collection default view route falls back to renderer.list', () => {
    const schema = { ui: { renderer: { list: 'ntx-products' } } };
    const r = resolveRoute(parseRoute('Product/@'), () => schema);
    expect(r.tag).toBe('ntx-products');
    expect(r.attrs).toEqual({ model: 'Product' });
  });

  it('collection default view route with no schema → ntx-list', () => {
    const r = resolveRoute(parseRoute('Product/@'));
    expect(r.tag).toBe('ntx-list');
    expect(r.attrs).toEqual({ model: 'Product' });
  });

  it('named collection view route uses schema renderer first', () => {
    const schema = { ui: { renderer: { table: 'ntx-product-table' } } };
    const r = resolveRoute(parseRoute('Product/@table'), () => schema);
    expect(r.tag).toBe('ntx-product-table');
    expect(r.attrs).toEqual({ model: 'Product' });
  });

  it('named collection view route falls back to known framework tags', () => {
    expect(resolveRoute(parseRoute('Product/@table')).tag).toBe('ntx-table');
    expect(resolveRoute(parseRoute('Product/@list')).tag).toBe('ntx-list');
  });

  it('named collection custom views require schema renderers', () => {
    expect(resolveRoute(parseRoute('Product/@custom-card'))).toBeNull();
    expect(resolveRoute(parseRoute('Product/@ntx-custom-card'))).toBeNull();
    expect(resolveRoute(parseRoute('Product/@0'))).toBeNull();

    const schema = { ui: { renderer: { 'custom-card': 'ntx-custom-card', '0': 'ntx-zero-view' } } };
    expect(resolveRoute(parseRoute('Product/@custom-card'), () => schema).tag).toBe('ntx-custom-card');
    expect(resolveRoute(parseRoute('Product/@0'), () => schema).tag).toBe('ntx-zero-view');
  });

  it('named collection view route passes through params except query view', () => {
    const schema = { ui: { renderer: { table: 'ntx-product-table' } } };
    const r = resolveRoute(parseRoute('Product/@table?limit=10&view=list'), () => schema);
    expect(r.tag).toBe('ntx-product-table');
    expect(r.attrs).toEqual({ model: 'Product', limit: '10' });
    expect(r.attrs.view).toBeUndefined();
  });

  it('member default view route prefers renderer.detail', () => {
    const schema = { ui: { renderer: { detail: 'ntx-product-detail', item: 'ntx-product-card' } } };
    const r = resolveRoute(parseRoute('Product/1/@'), () => schema);
    expect(r.tag).toBe('ntx-product-detail');
    expect(r.attrs).toEqual({ ref: 'Product/1', display: 'lg' });
    expect(r.attrs.method).toBeUndefined();
  });

  it('member default view route falls back to renderer.item', () => {
    const schema = { ui: { renderer: { item: 'ntx-product-card' } } };
    const r = resolveRoute(parseRoute('Product/1/@'), () => schema);
    expect(r.tag).toBe('ntx-product-card');
    expect(r.attrs).toEqual({ ref: 'Product/1', display: 'lg' });
  });

  it('member default view route with no schema → ntx-item', () => {
    const r = resolveRoute(parseRoute('Product/1/@'));
    expect(r.tag).toBe('ntx-item');
    expect(r.attrs).toEqual({ ref: 'Product/1', display: 'lg' });
  });

  it('member default view route passes through params except query view', () => {
    const r = resolveRoute(parseRoute('Product/1/@?tab=history&view=item'));
    expect(r.attrs).toEqual({ ref: 'Product/1', display: 'lg', tab: 'history' });
    expect(r.attrs.view).toBeUndefined();
    expect(r.attrs.method).toBeUndefined();
  });

  it('named member view route uses schema renderer first', () => {
    const schema = { ui: { renderer: { item: 'ntx-product-card', detail: 'ntx-product-detail', chat: 'ntx-product-chat' } } };
    expect(resolveRoute(parseRoute('Product/1/@item'), () => schema).tag).toBe('ntx-product-card');
    expect(resolveRoute(parseRoute('Product/1/@detail'), () => schema).tag).toBe('ntx-product-detail');
    expect(resolveRoute(parseRoute('Product/1/@chat'), () => schema).tag).toBe('ntx-product-chat');
  });

  it('named member view route falls back to known tags only', () => {
    expect(resolveRoute(parseRoute('Product/1/@item')).tag).toBe('ntx-item');
    expect(resolveRoute(parseRoute('Product/1/@detail')).tag).toBe('ntx-item');
    expect(resolveRoute(parseRoute('Product/1/@chat')).tag).toBe('ntx-chat');
  });

  it('named member custom views require schema renderers', () => {
    expect(resolveRoute(parseRoute('Product/1/@custom-card'))).toBeNull();
    expect(resolveRoute(parseRoute('Product/1/@0'))).toBeNull();

    const schema = { ui: { renderer: { 'custom-card': 'ntx-custom-card', '0': 'ntx-zero-view' } } };
    expect(resolveRoute(parseRoute('Product/1/@custom-card'), () => schema).tag).toBe('ntx-custom-card');
    expect(resolveRoute(parseRoute('Product/1/@0'), () => schema).tag).toBe('ntx-zero-view');
  });

  it('named member view route passes through params without method attrs', () => {
    const r = resolveRoute(parseRoute('Product/1/@chat?thread=abc&view=item'));
    expect(r.attrs).toEqual({ ref: 'Product/1', display: 'lg', thread: 'abc' });
    expect(r.attrs.method).toBeUndefined();
    expect(r.attrs.view).toBeUndefined();
  });

  it('method route and same-named member view route resolve distinctly', () => {
    const schema = {
      ui: { renderer: { run: 'ntx-run-view' } },
      methods: { run: { ui: { renderer: 'ntx-run-method' } } },
    };
    const action = resolveRoute(parseRoute('Product/1/run'), () => schema);
    const view = resolveRoute(parseRoute('Product/1/@run'), () => schema);

    expect(action.tag).toBe('ntx-run-method');
    expect(action.attrs.method).toBe('run');
    expect(view.tag).toBe('ntx-run-view');
    expect(view.attrs.method).toBeUndefined();
  });

  it('nested class-name detail and action routes resolve to canonical refs', () => {
    const schema = {
      ui: { renderer: { item: 'ntx-comment-card', like: 'ntx-like-view' } },
      methods: { like: { ui: { renderer: 'ntx-like-method' } } },
    };
    const detail = resolveRoute(parseRoute('Product/1/Comment/2'), () => schema);
    expect(detail.tag).toBe('ntx-comment-card');
    expect(detail.attrs).toEqual({
      'data-model': 'Comment',
      ref: 'Comment/2',
      display: 'lg',
    });

    const view = resolveRoute(parseRoute('Product/1/Comment/2/@like'), () => schema);
    expect(view.tag).toBe('ntx-like-view');
    expect(view.attrs).toEqual({
      'data-model': 'Comment',
      ref: 'Comment/2',
      display: 'lg',
    });
    expect(view.attrs.method).toBeUndefined();

    const action = resolveRoute(parseRoute('Product/1/Comment/2/like'), () => schema);
    expect(action.tag).toBe('ntx-like-method');
    expect(action.attrs).toEqual({
      'data-model': 'Comment',
      ref: 'Comment/2',
      method: 'like',
      display: 'lg',
    });
  });

  it('nested class-name detail routes resolve with child schema and filter internal params', () => {
    const getSchema = vi.fn((model) => ({
      ui: { renderer: model === 'Comment' ? { item: 'ntx-comment-card' } : { item: 'ntx-product-card' } },
    }));

    const route = resolveRoute(parseRoute('Product/1/Comment/2/@item?view=detail&tab=history'), getSchema);

    expect(getSchema).toHaveBeenCalledWith('Comment');
    expect(route.tag).toBe('ntx-comment-card');
    expect(route.attrs).toEqual({
      'data-model': 'Comment',
      ref: 'Comment/2',
      display: 'lg',
      tab: 'history',
    });
    expect(route.attrs.view).toBeUndefined();
  });

  it('nested collection routes resolve with parent context', () => {
    const schema = { ui: { renderer: { table: 'ntx-comment-table' } } };
    const collection = resolveRoute(parseRoute('Product/1/Comment'), () => schema);
    expect(collection.tag).toBe('ntx-list');
    expect(collection.attrs).toEqual({ model: 'Comment', parent: 'Product/1' });

    const table = resolveRoute(parseRoute('Product/1/Comment/@table?limit=10'), () => schema);
    expect(table.tag).toBe('ntx-comment-table');
    expect(table.attrs).toEqual({ model: 'Comment', parent: 'Product/1', limit: '10' });
  });

  it('invalid routes resolve to null', () => {
    expect(resolveRoute(parseRoute('Product/@/extra'))).toBeNull();
    expect(resolveRoute(parseRoute('Product/1/@item/extra'))).toBeNull();
    expect(resolveRoute(parseRoute('Product/@../../x'))).toBeNull();
  });

  it('model route with view= param → overrides schema', () => {
    const schema = { ui: { renderer: { list: 'ntx-list' } } };
    const r = resolveRoute(
      { type: 'model', model: 'Grant', params: { view: 'table' } },
      () => schema,
    );
    expect(r.tag).toBe('ntx-table');
  });

  it('legacy model route view= param uses schema renderer lookup', () => {
    const schema = { ui: { renderer: { table: 'ntx-product-table', list: 'ntx-list' } } };
    const r = resolveRoute(
      { type: 'model', model: 'Grant', params: { view: 'table' } },
      () => schema,
    );
    expect(r.tag).toBe('ntx-product-table');
    expect(r.attrs.view).toBeUndefined();
  });

  it('model route view= param with ntx- prefix passes through', () => {
    const r = resolveRoute(
      { type: 'model', model: 'Grant', params: { view: 'ntx-custom-list' } },
    );
    expect(r).toBeNull();
  });

  it('model route filters view from pass-through attrs', () => {
    const r = resolveRoute(
      { type: 'model', model: 'Grant', params: { view: 'table', 'allow-create': '' } },
    );
    expect(r.attrs).toEqual({ model: 'Grant', 'allow-create': '' });
    expect(r.attrs.view).toBeUndefined();
  });

  it('detail route with no schema → ntx-item default', () => {
    const r = resolveRoute({ type: 'detail', model: 'Product', id: '3', params: {} });
    expect(r.tag).toBe('ntx-item');
    expect(r.attrs.ref).toBe('Product/3');
    expect(r.attrs.display).toBe('lg');
  });

  it('detail route with schema renderer.detail → uses it', () => {
    const schema = { ui: { renderer: { detail: 'ntx-custom' } } };
    const r = resolveRoute(
      { type: 'detail', model: 'Product', id: '3', params: {} },
      () => schema,
    );
    expect(r.tag).toBe('ntx-custom');
  });

  it('detail route falls back to renderer.item if no detail', () => {
    const schema = { ui: { renderer: { item: 'ntx-user' } } };
    const r = resolveRoute(
      { type: 'detail', model: 'User', id: '1', params: {} },
      () => schema,
    );
    expect(r.tag).toBe('ntx-user');
  });

  it('detail route with schema title uses it', () => {
    const schema = { __name__: 'My Product' };
    const r = resolveRoute(
      { type: 'detail', model: 'Product', id: '3', params: {} },
      () => schema,
    );
    expect(r.title).toBe('My Product');
  });

  it('action route with method renderer → uses it', () => {
    const schema = { methods: { analyze: { ui: { renderer: 'ntx-grant-analyze' } } } };
    const r = resolveRoute(
      { type: 'action', model: 'Grant', id: '5', action: 'analyze', params: {} },
      () => schema,
    );
    expect(r.tag).toBe('ntx-grant-analyze');
    expect(r.attrs.ref).toBe('Grant/5');
    expect(r.attrs.method).toBe('analyze');
  });

  it('action route with stream method → ntx-stream', () => {
    const schema = { methods: { generate: { stream: true } } };
    const r = resolveRoute(
      { type: 'action', model: 'Task', id: '1', action: 'generate', params: {} },
      () => schema,
    );
    expect(r.tag).toBe('ntx-stream');
  });

  it('action route with no schema → falls back to ntx-item', () => {
    const r = resolveRoute(
      { type: 'action', model: 'Grant', id: '5', action: 'analyze', params: {} },
    );
    expect(r.tag).toBe('ntx-item');
    expect(r.title).toBe('Grant / analyze');
  });
});
