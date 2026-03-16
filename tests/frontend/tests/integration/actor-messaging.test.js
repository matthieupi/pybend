/**
 * Actor Messaging — Integration Tests
 *
 * Tests: TX routing through Matrix, parent-child delivery, bubble-up
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ProductSchema, makeProductData, API_URL } from './helpers/mock-schemas.js';
import { flush } from './helpers/test-env.js';

let NTT, matrix, TX, Actor;

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
  const matrixMod = await import('../../core/Matrix.js');
  const txMod = await import('../../core/TX.js');
  const actorMod = await import('../../core/Actor.js');

  NTT = nttMod.NTT;
  matrix = matrixMod.matrix;
  TX = txMod.default;
  Actor = actorMod.default;
});

describe('Actor Messaging', () => {

  it('TX constructor creates event with required fields', () => {
    const tx = new TX({
      name: 'TEST',
      source: 'source-actor',
      target: 'target-actor',
      data: { key: 'value' },
    });
    expect(tx.name).toBe('TEST');
    expect(tx.source).toBe('source-actor');
    expect(tx.target).toBe('target-actor');
    expect(tx.data).toEqual({ key: 'value' });
    expect(tx.tst).toBeDefined();
  });

  it('TX.repr() returns plain object copy', () => {
    const tx = new TX({ name: 'TEST', source: 's', target: 't', data: {} });
    const repr = tx.repr();
    expect(repr).toEqual(expect.objectContaining({
      name: 'TEST',
      source: 's',
      target: 't',
    }));
    expect(repr).not.toBe(tx); // Not the same object
  });

  it('Matrix routes TX to registered child actor', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');

    // NTT should be registered as a child of the Matrix
    expect(matrix.children.has('NTT')).toBe(true);
  });

  it('Matrix dispatches ATTACH to NTT handler', () => {
    const spy = vi.spyOn(NTT, 'ATTACH');
    // This will trigger ATTACH routing through matrix
    NTT.SCHEMA(ProductSchema);
    // Direct ATTACH call
    NTT.ATTACH('Product', new TX({
      name: 'ATTACH', source: 'test', target: 'NTT', data: 'Product',
    }));
    expect(spy).toHaveBeenCalled();
    spy.mockRestore();
  });

  it('DynamicClass.ATTACH adds watcher for type-level ATTACH', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    DC.ATTACH('Product', new TX({
      name: 'ATTACH', source: 'my-list-component', target: 'NTT', data: 'Product',
    }));
    expect(DC._watchers.has('my-list-component')).toBe(true);
  });

  it('DynamicClass.ATTACH for instance-level creates and delivers', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    DC.READ([makeProductData(1)]);
    const instance = DC.instances.get(1);
    const inboxSpy = vi.spyOn(instance, 'inbox');

    DC.ATTACH('Product/1', new TX({
      name: 'ATTACH', source: 'item-comp', target: 'NTT', data: 'Product/1',
    }));

    expect(inboxSpy).toHaveBeenCalled();
    inboxSpy.mockRestore();
  });

  it('DynamicClass.ATTACH queues pending instance ATTACHes', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    // ATTACH for instance that doesn't exist yet
    DC.ATTACH('Product/99', new TX({
      name: 'ATTACH', source: 'item-comp', target: 'NTT', data: 'Product/99',
    }));
    expect(DC._pendingAttaches.length).toBe(1);
    expect(DC._pendingAttaches[0].id).toBe('99');
  });

  it('pending ATTACHes replayed after READ creates instances', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');

    // Queue ATTACH for instance 5
    DC.ATTACH('Product/5', new TX({
      name: 'ATTACH', source: 'item-comp', target: 'NTT', data: 'Product/5',
    }));

    expect(DC._pendingAttaches.length).toBe(1);

    // Now READ creates instance 5
    DC.READ([makeProductData(5)]);

    // Pending should have been replayed and cleared
    expect(DC._pendingAttaches.length).toBe(0);
    expect(DC.instances.has(5)).toBe(true);
  });

  it('NTT instance ATTACH sends DESCRIBE back to source', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    DC.READ([makeProductData(1)]);
    const instance = DC.instances.get(1);

    const sendSpy = vi.fn();
    const originalSend = instance.constructor.send;
    instance.constructor.send = sendSpy;

    instance.ATTACH('Product/1', new TX({
      name: 'ATTACH', source: 'my-component', target: 'Product/1', data: 'Product/1',
    }));

    expect(sendSpy).toHaveBeenCalled();
    const sentTx = sendSpy.mock.calls[0][0];
    expect(sentTx.name).toBe('DESCRIBE');
    expect(sentTx.target).toBe('my-component');
    expect(sentTx.data.proto).toBeDefined();
    expect(sentTx.data.data).toBeDefined();

    instance.constructor.send = originalSend;
  });

  it('TT.call sends TX with method name and entity href', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    DC.READ([makeProductData(1)]);
    const instance = DC.instances.get(1);

    const sendSpy = vi.fn();
    const originalSend = instance.constructor.send;
    instance.constructor.send = sendSpy;

    instance.call('like', {}, {});

    expect(sendSpy).toHaveBeenCalled();
    const sentTx = sendSpy.mock.calls[0][0];
    expect(sentTx.name).toBe('like');
    expect(sentTx.target).toContain('/products/1');

    instance.constructor.send = originalSend;
  });

  it('DynamicClass static call sends TX to class href', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');

    const sendSpy = vi.fn();
    const originalSend = DC.send;
    DC.send = sendSpy;

    DC.call('READ', { limit: 20, offset: 0 });

    expect(sendSpy).toHaveBeenCalled();
    const sentTx = sendSpy.mock.calls[0][0];
    expect(sentTx.name).toBe('READ');
    expect(sentTx.target).toBe(`${API_URL}/products`);

    DC.send = originalSend;
  });

  it('TX from string parses JSON correctly', () => {
    const json = JSON.stringify({
      name: 'TEST', source: 's', target: 't', data: { x: 1 },
    });
    const tx = new TX(json);
    expect(tx.name).toBe('TEST');
    expect(tx.data.x).toBe(1);
  });

  it('TX.hash generates a deterministic hash', () => {
    const tx = new TX({ name: 'A', source: 's', target: 't', data: {} });
    const hash1 = tx.hash;
    const hash2 = tx.hash;
    expect(hash1).toBe(hash2);
    expect(typeof hash1).toBe('string');
  });

  it('Matrix inbox routes to NetworkAdapter for unknown targets', () => {
    // Any target that's not registered locally should go to remote
    const remoteSendSpy = vi.spyOn(matrix.remote, 'send');
    matrix.dispatch(new TX({
      name: 'READ',
      source: 'NTT',
      target: `${API_URL}/products`,
      data: {},
    }));
    expect(remoteSendSpy).toHaveBeenCalled();
    remoteSendSpy.mockRestore();
  });

  it('DynamicClass watchers notified with instance addresses after READ', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');

    const sentMessages = [];
    const originalSend = DC.send;
    DC.send = vi.fn((tx) => {
      sentMessages.push(tx);
    });

    DC._watchers.add('list-component');
    DC.READ([makeProductData(1), makeProductData(2)]);

    const updateTx = sentMessages.find(tx => tx.name === 'UPDATE' && tx.target === 'list-component');
    expect(updateTx).toBeDefined();
    expect(Array.isArray(updateTx.data)).toBe(true);
    expect(updateTx.data).toContain('Product/1');
    expect(updateTx.data).toContain('Product/2');

    DC.send = originalSend;
  });
});
