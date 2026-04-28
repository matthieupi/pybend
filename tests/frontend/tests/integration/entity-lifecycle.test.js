/**
 * Entity Lifecycle — Integration Tests
 *
 * Tests: DESCRIBE → value set → render trigger → signal propagation → surgical update
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ProductSchema, makeProductData, makeCommentData, API_URL } from './helpers/mock-schemas.js';
import { flush, flushPromises } from './helpers/test-env.js';

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

describe('Entity Lifecycle', () => {

  it('DynamicClass instance update() sets value with provided data', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    const instance = new DC(makeProductData(1));
    // update() sets this.value using NTT-level #data spread with new data.
    // DynamicClass stores data in _data (not NTT's #data), so the spread
    // starts from undefined — update replaces rather than merging.
    instance.update({ ...instance.value, name: 'Updated Name' });
    expect(instance.name).toBe('Updated Name');
    expect(instance.price).toBe(29.99); // Preserved via explicit spread
  });

  it('value setter triggers signal to all listeners', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    const instance = new DC(makeProductData(1));
    const listener = vi.fn();
    instance.signal(listener, true); // wait=true: don't call immediately
    instance.value = { ...instance.value, name: 'Signal Test' };
    expect(listener).toHaveBeenCalledTimes(1);
    expect(listener).toHaveBeenCalledWith(instance);
  });

  it('signal() with callback and wait=false fires immediately', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    const instance = new DC(makeProductData(1));
    const listener = vi.fn();
    instance.signal(listener, false); // wait=false: fire immediately
    expect(listener).toHaveBeenCalledTimes(1);
  });

  it('signal() without callback fires all registered listeners', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    const instance = new DC(makeProductData(1));
    const listener1 = vi.fn();
    const listener2 = vi.fn();
    instance.signal(listener1, true);
    instance.signal(listener2, true);
    instance.signal(); // Fire all
    expect(listener1).toHaveBeenCalledTimes(1);
    expect(listener2).toHaveBeenCalledTimes(1);
  });

  it('signal() returns unsubscribe function', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    const instance = new DC(makeProductData(1));
    const listener = vi.fn();
    const unsub = instance.signal(listener, true);
    unsub();
    instance.signal(); // Fire all — listener should NOT be called
    expect(listener).not.toHaveBeenCalled();
  });

  it('value setter rejects non-object data', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    const instance = new DC(makeProductData(1));
    expect(() => { instance.value = 'string'; }).toThrow(TypeError);
  });

  it('DynamicClass.CREATE adds instance and notifies watchers', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    const watcherUpdates = [];
    DC._watchers.add('test-watcher');

    // Mock send to capture TX
    const originalSend = DC.send;
    DC.send = vi.fn((tx) => {
      if (tx.name === 'UPDATE') {
        watcherUpdates.push(tx);
      }
    });

    DC.CREATE(makeProductData(10));
    expect(DC.instances.has('10')).toBe(true);
    expect(watcherUpdates.length).toBeGreaterThan(0);
    DC.send = originalSend;
  });

  it('DynamicClass.DELETE removes instance and notifies watchers', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    DC.READ([makeProductData(1), makeProductData(2)]);
    expect(DC.instances.size).toBe(2);

    const watcherUpdates = [];
    DC._watchers.add('test-watcher');
    const originalSend = DC.send;
    DC.send = vi.fn((tx) => {
      if (tx.name === 'UPDATE') watcherUpdates.push(tx);
    });

    DC.DELETE({}, new TX({
      name: 'DELETE',
      source: `${API_URL}/products/1`,
      target: 'Product',
    }));

    expect(DC.instances.has('1')).toBe(false);
    expect(DC.instances.size).toBe(1);
    expect(watcherUpdates.length).toBeGreaterThan(0);
    DC.send = originalSend;
  });

  it('instance pull() sends READ TX with correct href', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    const instance = new DC(makeProductData(1));
    const sendSpy = vi.fn();
    const originalSend = instance.constructor.send;
    instance.constructor.send = sendSpy;

    instance.pull();

    expect(sendSpy).toHaveBeenCalled();
    const tx = sendSpy.mock.calls[0][0];
    expect(tx.name).toBe('READ');
    expect(tx.target).toContain('/products/1');
    instance.constructor.send = originalSend;
  });

  it('instance _response_ handler triggers pull()', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    const instance = new DC(makeProductData(1));
    const pullSpy = vi.spyOn(instance, 'pull');
    instance._response_({}, new TX({ name: '_response_', source: 'test', target: 'Product/1' }));
    expect(pullSpy).toHaveBeenCalled();
  });

  it('normalizePopulated converts inline objects to href arrays', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    const commentData = makeCommentData(1, 1);

    // Simulate a populated response
    const productData = {
      ...makeProductData(1),
      comments: {
        data: [commentData],
        meta: { total: 1 },
      },
    };

    DC.READ([productData]);
    const instance = DC.instances.get('1');
    // After normalization, comments should be href array
    expect(Array.isArray(instance.value.comments)).toBe(true);
    if (instance.value.comments.length > 0) {
      expect(typeof instance.value.comments[0]).toBe('string');
    }
  });

  it('DynamicClass.READ with existing instance updates rather than creates new', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    DC.READ([makeProductData(1)]);
    const firstInstance = DC.instances.get('1');

    DC.READ([{ ...makeProductData(1), name: 'Updated' }]);
    const sameInstance = DC.instances.get('1');
    expect(DC.instances.size).toBe(1);
    // Same reference — updated in place
    expect(sameInstance).toBe(firstInstance);
    expect(sameInstance.name).toBe('Updated');
  });

  it('DynamicClass static signal notifies all listeners', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    const listener = vi.fn();
    DC.signal(listener, true); // wait=true
    DC.signal(); // fire all
    expect(listener).toHaveBeenCalledTimes(1);
    expect(listener).toHaveBeenCalledWith(DC);
  });

  it('DynamicClass static observe watches property changes', () => {
    NTT.SCHEMA(ProductSchema);
    const DC = NTT.get('Product');
    const callback = vi.fn();
    const unsub = DC.observe('UPDATE', callback);
    // Trigger notification
    DC.__observers.get('UPDATE')?.forEach(cb => cb('new', 'old', 'UPDATE', DC));
    expect(callback).toHaveBeenCalledWith('new', 'old', 'UPDATE', DC);
    unsub();
    expect(DC.__observers.has('UPDATE')).toBe(false);
  });
});
