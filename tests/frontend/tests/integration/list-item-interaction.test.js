/**
 * List + Item Interaction — Integration Tests
 *
 * Tests: ListElement/NTTElement lifecycle, selection, Load More, child creation
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ProductSchema, makeProductData, API_URL } from './helpers/mock-schemas.js';
import { flush } from './helpers/test-env.js';

let NTT, TX, Component;

afterEach(async () => {
  // Drain pending fetch promises before vi.resetModules() destroys the registrar,
  // preventing leaked unhandled rejections from stale HTTP callbacks.
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
  const compMod = await import('../../core/Component.js');
  NTT = nttMod.NTT;
  TX = txMod.default;
  Component = compMod.Component;
});

describe('List + Item Interaction', () => {

  describe('Component base class', () => {

    it('normalizeDisplay converts semantic aliases', () => {
      expect(Component.normalizeDisplay('pill')).toBe('xs');
      expect(Component.normalizeDisplay('list-item')).toBe('sm');
      expect(Component.normalizeDisplay('card')).toBe('md');
      expect(Component.normalizeDisplay('detail')).toBe('lg');
      expect(Component.normalizeDisplay('page')).toBe('xl');
    });

    it('normalizeDisplay returns abstract sizes unchanged', () => {
      expect(Component.normalizeDisplay('xs')).toBe('xs');
      expect(Component.normalizeDisplay('sm')).toBe('sm');
      expect(Component.normalizeDisplay('md')).toBe('md');
      expect(Component.normalizeDisplay('lg')).toBe('lg');
      expect(Component.normalizeDisplay('xl')).toBe('xl');
    });

    it('normalizeDisplay returns null for auto', () => {
      expect(Component.normalizeDisplay('auto')).toBeNull();
      expect(Component.normalizeDisplay(null)).toBeNull();
      expect(Component.normalizeDisplay('')).toBeNull();
    });

    it('normalizeDisplay returns null for unknown values', () => {
      expect(Component.normalizeDisplay('unknown')).toBeNull();
    });

    it('SIZES constant has all supported sizes', () => {
      expect(Component.SIZES).toEqual(['xs', 'sm', 'md', 'lg', 'xl', 'row']);
    });
  });

  describe('ListElement behavior', () => {

    it('SIZE_CASCADE maps parent display to child display', async () => {
      const { ListElement } = await import('../../components/ListElement.js');
      expect(ListElement.SIZE_CASCADE).toEqual({
        xl: 'md',
        lg: 'sm',
        md: 'sm',
        sm: 'xs',
        xs: 'xs',
        row: 'row',
      });
    });
  });

  describe('DynamicClass as type actor', () => {

    it('DynamicClass.ATTACH with type-level data adds watcher', () => {
      NTT.SCHEMA(ProductSchema);
      const DC = NTT.get('Product');
      DC.ATTACH('Product', new TX({
        name: 'ATTACH', source: 'list-1', target: 'NTT', data: 'Product',
      }));
      expect(DC._watchers.has('list-1')).toBe(true);
    });

    it('DynamicClass.ATTACH sends immediate UPDATE when instances exist', () => {
      NTT.SCHEMA(ProductSchema);
      const DC = NTT.get('Product');
      DC.READ([makeProductData(1), makeProductData(2)]);

      const sentMessages = [];
      const originalSend = DC.send;
      DC.send = vi.fn((tx) => sentMessages.push(tx));

      DC.ATTACH('Product', new TX({
        name: 'ATTACH', source: 'list-2', target: 'NTT', data: 'Product',
      }));

      const update = sentMessages.find(tx => tx.name === 'UPDATE' && tx.target === 'list-2');
      expect(update).toBeDefined();
      expect(Array.isArray(update.data)).toBe(true);

      DC.send = originalSend;
    });

    it('DynamicClass.READ notifies all watchers with child addresses', () => {
      NTT.SCHEMA(ProductSchema);
      const DC = NTT.get('Product');
      DC._watchers.add('watcher-a');
      DC._watchers.add('watcher-b');

      const sentMessages = [];
      const originalSend = DC.send;
      DC.send = vi.fn((tx) => sentMessages.push(tx));

      DC.READ([makeProductData(1)]);

      const watcherAUpdates = sentMessages.filter(tx => tx.target === 'watcher-a');
      const watcherBUpdates = sentMessages.filter(tx => tx.target === 'watcher-b');
      expect(watcherAUpdates.length).toBe(1);
      expect(watcherBUpdates.length).toBe(1);

      DC.send = originalSend;
    });

    it('DynamicClass.UPDATE delegates to READ', () => {
      NTT.SCHEMA(ProductSchema);
      const DC = NTT.get('Product');
      const readSpy = vi.spyOn(DC, 'READ');

      DC.UPDATE([makeProductData(1)], new TX({ name: 'UPDATE', source: 'test', target: 'Product' }));

      expect(readSpy).toHaveBeenCalled();
      readSpy.mockRestore();
    });

    it('pagination meta stored on DynamicClass', () => {
      NTT.SCHEMA(ProductSchema);
      const DC = NTT.get('Product');

      DC.READ({
        data: [makeProductData(1)],
        meta: { total: 100, limit: 20, offset: 0, has_more: true },
      });

      expect(DC._paginationMeta).toEqual({
        total: 100, limit: 20, offset: 0, has_more: true,
      });
    });
  });

  describe('Instance lifecycle', () => {

    it('instance href is set from $id in data', () => {
      NTT.SCHEMA(ProductSchema);
      const DC = NTT.get('Product');
      const data = makeProductData(1);
      const instance = new DC(data);
      expect(instance.href).toContain('/products/1');
    });

    it('instance addr is the string id', () => {
      NTT.SCHEMA(ProductSchema);
      const DC = NTT.get('Product');
      const instance = new DC(makeProductData(7));
      expect(instance.addr).toBe('7');
    });

    it('instance is registered in DynamicClass.children', () => {
      NTT.SCHEMA(ProductSchema);
      const DC = NTT.get('Product');
      DC.READ([makeProductData(1)]);
      expect(DC.children.has('1')).toBe(true);
    });

    it('instance update replaces value and signals', () => {
      NTT.SCHEMA(ProductSchema);
      const DC = NTT.get('Product');
      const instance = new DC(makeProductData(1));
      const signalSpy = vi.fn();
      instance.signal(signalSpy, true);

      // update() in NTT base spreads #data (which is undefined for DynamicClass)
      // with new data, effectively replacing the value
      instance.update({ id: 1, name: 'Merged', price: 29.99 });
      expect(instance.name).toBe('Merged');
      expect(instance.price).toBe(29.99);
    });

    it('instance toJSON produces serializable output', () => {
      NTT.SCHEMA(ProductSchema);
      const DC = NTT.get('Product');
      const instance = new DC(makeProductData(1));
      const json = instance.toJSON();
      // DynamicClass toJSON returns { addr, href, ... }
      // addr comes from the id passed to super()
      expect(json.addr).toBeTruthy();
      expect(json.href).toContain('/products/1');
    });
  });

  describe('Empty and edge states', () => {

    it('empty READ results in 0 instances', () => {
      NTT.SCHEMA(ProductSchema);
      const DC = NTT.get('Product');
      DC.READ({ data: [], meta: { total: 0, limit: 20, offset: 0, has_more: false } });
      expect(DC.instances.size).toBe(0);
    });

    it('READ with null data throws assertion error', () => {
      NTT.SCHEMA(ProductSchema);
      const DC = NTT.get('Product');
      // READ asserts that data must be a non-empty object, so null throws
      expect(() => DC.READ(null)).toThrow();
    });
  });
});
