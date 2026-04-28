/**
 * Method Execution — Integration Tests
 *
 * Tests: instance/class methods, TX routing, response handling
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ProductSchema, makeProductData, API_URL } from './helpers/mock-schemas.js';
import { flush } from './helpers/test-env.js';

let NTT, TX;

afterEach(async () => {
  await flush(10);
});

beforeEach(async () => {
  vi.resetModules();
  global.fetch = vi.fn(() => Promise.resolve({
    ok: true, status: 200,
    json: () => Promise.resolve({}),
  }));

  const nttMod = await import('../../core/NTT.js');
  const txMod = await import('../../core/TX.js');
  NTT = nttMod.NTT;
  TX = txMod.default;
});

describe('Method Execution', () => {

  it('instance method call sends TX to entity href', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    DC.READ([makeProductData(1)]);
    const instance = DC.instances.get('1');

    const sentTxs = [];
    const originalSend = instance.constructor.send;
    instance.constructor.send = vi.fn((tx) => sentTxs.push(tx));

    instance.call('favorite', {}, { inbox: '_response_' });

    const favoriteTx = sentTxs.find(tx => tx.name === 'favorite');
    expect(favoriteTx).toBeDefined();
    expect(favoriteTx.target).toContain('/products/1');
    expect(favoriteTx.meta.inbox).toBe('_response_');

    instance.constructor.send = originalSend;
  });

  it('class-level call sends TX to DynamicClass href', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');

    const sentTxs = [];
    const originalSend = DC.send;
    DC.send = vi.fn((tx) => sentTxs.push(tx));

    DC.call('READ', { limit: 20, offset: 0 });

    const readTx = sentTxs.find(tx => tx.name === 'READ');
    expect(readTx).toBeDefined();
    expect(readTx.target).toBe(`${API_URL}/products`);

    DC.send = originalSend;
  });

  it('method with payload includes data in TX', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    DC.READ([makeProductData(1)]);
    const instance = DC.instances.get('1');

    const sentTxs = [];
    const originalSend = instance.constructor.send;
    instance.constructor.send = vi.fn((tx) => sentTxs.push(tx));

    instance.call('comment', { text: 'Hello!' }, {});

    const commentTx = sentTxs.find(tx => tx.name === 'comment');
    expect(commentTx).toBeDefined();
    expect(commentTx.data).toEqual({ text: 'Hello!' });

    instance.constructor.send = originalSend;
  });

  it('_response_ handler triggers pull() on instance', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    DC.READ([makeProductData(1)]);
    const instance = DC.instances.get('1');

    const pullSpy = vi.spyOn(instance, 'pull');
    instance._response_('Comment added', new TX({
      name: '_response_',
      source: `${API_URL}/products/1/comment`,
      target: 'Product/1',
    }));

    expect(pullSpy).toHaveBeenCalled();
    pullSpy.mockRestore();
  });

  it('pull() sends READ TX to instance href', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    DC.READ([makeProductData(1)]);
    const instance = DC.instances.get('1');

    const sentTxs = [];
    const originalSend = instance.constructor.send;
    instance.constructor.send = vi.fn((tx) => sentTxs.push(tx));

    instance.pull();

    const readTx = sentTxs.find(tx => tx.name === 'READ');
    expect(readTx).toBeDefined();
    expect(readTx.target).toContain('/products/1');
    expect(readTx.meta.remote).toBe(true);

    instance.constructor.send = originalSend;
  });

  it('pull() with populate depth includes depth parameter', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    DC.READ([makeProductData(1)]);
    const instance = DC.instances.get('1');

    const sentTxs = [];
    const originalSend = instance.constructor.send;
    instance.constructor.send = vi.fn((tx) => sentTxs.push(tx));

    instance.pull();

    const readTx = sentTxs.find(tx => tx.name === 'READ');
    expect(readTx.data).toEqual(expect.objectContaining({ depth: 1 }));

    instance.constructor.send = originalSend;
  });

  it('generated prototype methods exist on instances', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    const instance = new DC(makeProductData(1));

    // Methods from schema
    expect(typeof instance.comment).toBe('function');
    expect(typeof instance.favorite).toBe('function');
  });

  it('DynamicClass labels map generated from schema titles', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    expect(DC.labels.name).toBe('Name');
    expect(DC.labels.price).toBe('Price');
    expect(DC.labels.description).toBe('Description');
  });

  it('DynamicClass.CREATE adds new instance and notifies watchers', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    DC._watchers.add('test-list');

    const sentTxs = [];
    const originalSend = DC.send;
    DC.send = vi.fn((tx) => sentTxs.push(tx));

    DC.CREATE(makeProductData(99));

    expect(DC.instances.has('99')).toBe(true);
    const updateTx = sentTxs.find(tx => tx.name === 'UPDATE' && tx.target === 'test-list');
    expect(updateTx).toBeDefined();
    expect(updateTx.data).toContain('Product/99');

    DC.send = originalSend;
  });

  it('DynamicClass.CREATE with existing id updates instead of creating', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    DC.READ([makeProductData(1)]);
    const firstCount = DC.instances.size;

    DC.CREATE({ ...makeProductData(1), name: 'Updated via CREATE' });
    expect(DC.instances.size).toBe(firstCount);
    expect(DC.instances.get('1').name).toBe('Updated via CREATE');
  });

  it('call with meta.inbox routes response to correct handler', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    DC.READ([makeProductData(1)]);
    const instance = DC.instances.get('1');

    const sentTxs = [];
    const originalSend = instance.constructor.send;
    instance.constructor.send = vi.fn((tx) => sentTxs.push(tx));

    instance.call('favorite', {}, { inbox: '_response_' });

    const tx = sentTxs.find(tx => tx.name === 'favorite');
    expect(tx.meta.inbox).toBe('_response_');

    instance.constructor.send = originalSend;
  });
});
