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

  it('detail route → Product/3', () => {
    expect(buildRoute({ type: 'detail', model: 'Product', id: '3' })).toBe('Product/3');
  });

  it('action route → Grant/5/analyze', () => {
    expect(buildRoute({ type: 'action', model: 'Grant', id: '5', action: 'analyze' }))
      .toBe('Grant/5/analyze');
  });
});

// ── Round-trip ──

describe('parseRoute ↔ buildRoute round-trip', () => {

  const cases = [
    '@profile',
    '@settings?tab=security',
    'Product',
    'Product/3',
    'Grant/5/analyze',
    'Grant?view=table',
  ];

  for (const route of cases) {
    it(`round-trips: "${route}"`, () => {
      expect(buildRoute(parseRoute(route))).toBe(route);
    });
  }
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

  it('model route with view= param → overrides schema', () => {
    const schema = { ui: { renderer: { list: 'ntx-list' } } };
    const r = resolveRoute(
      { type: 'model', model: 'Grant', params: { view: 'table' } },
      () => schema,
    );
    expect(r.tag).toBe('ntx-table');
  });

  it('model route view= param with ntx- prefix passes through', () => {
    const r = resolveRoute(
      { type: 'model', model: 'Grant', params: { view: 'ntx-custom-list' } },
    );
    expect(r.tag).toBe('ntx-custom-list');
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
