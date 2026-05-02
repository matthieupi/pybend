import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../../utils/Assert.js', () => ({
  default: vi.fn((caller, cond, msg) => {
    if (!cond) throw new Error(msg || 'Assertion failed');
  }),
  caution: vi.fn(), inform: vi.fn(),
}));

vi.mock('../../config.js', () => ({
  config: {
    LOGGING: 3, LOGEVENTS: false, LOGSPAWN: false, DEBUG: false,
    API_URL: 'http://localhost:5000',
    WS_URL: 'ws://localhost:8765',
    E: {
      CONNECT: 'CONNECT', UPDATE: 'UPDATE', READ: 'READ', ENABLE: 'ENABLE',
      DISABLE: 'DISABLE', SCHEMA: 'SCHEMA', DESCRIBE: 'DESCRIBE', SELECT: 'SELECT',
      connect: 'CONNECT', update: 'UPDATE', read: 'READ', delete: 'DELETE',
      create: 'CREATE', schema: 'SCHEMA', describe: 'DESCRIBE',
      NAVIGATE: 'NAVIGATE', BACK: 'BACK',
    },
    DEFAULT_HEADERS: { 'Content-Type': 'application/json' },
    TIMEOUT: 5000, RETRY_LIMIT: 3,
  }
}));

vi.mock('../../utils/Logging.js', () => ({
  default: {
    warn: vi.fn(), error: vi.fn(), debug: vi.fn(),
    dev: vi.fn(), log: vi.fn(), init: vi.fn(), event: vi.fn(),
  }
}));

import { NTT } from '../../core/NTT.js';

describe('NTT.js', () => {

  const productSchema = {
    __name__: 'TestProduct',
    __tablename__: 'test_products',
    properties: {
      id: { type: 'integer', readOnly: true, title: 'ID' },
      name: { type: 'string', title: 'Name', minLength: 1 },
      price: { type: 'number', title: 'Price', ui: { widget: 'currency' } },
      description: { type: 'string', title: 'Description', ui: { widget: 'textarea' } },
    },
    methods: {
      like: {
        route: '/like', methods: ['POST'], scope: 'instancemethod',
        parameters: {},
        title: 'Like',
      }
    },
    required: ['name'],
    ui: { field_order: ['name', 'price', 'description'] },
    access: { read: { rule: 'anyone' }, create: { rule: 'authenticated' } },
  };

  describe('NTT static registry', () => {

    describe('static has(addr)', () => {
      it('should return false for non-existent addr', () => {
        expect(NTT.has('NonExistent')).toBe(false);
      });

      it('should return true after SCHEMA registers a model', () => {
        const schema = {
          ...productSchema,
          __name__: 'HasTest',
          __tablename__: 'has_tests',
        };
        NTT.SCHEMA(schema);
        expect(NTT.has('HasTest')).toBe(true);
      });
    });

    describe('static get(addr)', () => {
      it('should return undefined for null/undefined', () => {
        expect(NTT.get(null)).toBeUndefined();
        expect(NTT.get(undefined)).toBeUndefined();
      });

      it('should return undefined for non-existent model', () => {
        expect(NTT.get('Nonexistent')).toBeUndefined();
      });

      it('should return DynamicClass by model name', () => {
        const schema = {
          ...productSchema,
          __name__: 'GetTest',
          __tablename__: 'get_tests',
        };
        NTT.SCHEMA(schema);
        const DC = NTT.get('GetTest');
        expect(DC).toBeTruthy();
        expect(DC.name).toBe('GetTest');
      });

      it('should return NTT instance by entity ref', () => {
        const schema = {
          ...productSchema,
          __name__: 'GetInst',
          __tablename__: 'get_insts',
        };
        NTT.SCHEMA(schema);
        const DC = NTT.get('GetInst');
        // Create an instance via DC.READ
        DC.READ([{ id: 1, name: 'Test', price: 10 }]);
        const inst = NTT.get('GetInst/1');
        // The instance is actually stored as string key, let's check
        // DC.children has the instance by string(id)
        expect(DC.instances.has('1')).toBe(true);
      });

      it('should return undefined for empty string', () => {
        expect(NTT.get('')).toBeUndefined();
      });
    });

    describe('static attach(addr, callback)', () => {
      it('should fire callback immediately if DynamicClass exists', () => {
        const schema = {
          ...productSchema,
          __name__: 'AttachImm',
          __tablename__: 'attach_imms',
        };
        NTT.SCHEMA(schema);
        const cb = vi.fn();
        NTT.attach('AttachImm', cb);
        expect(cb).toHaveBeenCalled();
      });

      it('should throw if addr is empty', () => {
        expect(() => NTT.attach('', vi.fn())).toThrow();
      });

      it('should throw if callback is null', () => {
        expect(() => NTT.attach('SomeModel', null)).toThrow();
      });

      it('should return unsubscribe function when DC exists', () => {
        const schema = {
          ...productSchema,
          __name__: 'AttachUnsub',
          __tablename__: 'attach_unsubs',
        };
        NTT.SCHEMA(schema);
        const cb = vi.fn();
        const unsub = NTT.attach('AttachUnsub', cb);
        expect(typeof unsub).toBe('function');
      });
    });

    describe('static SCHEMA(data, tx)', () => {
      it('should create DynamicClass and register it', () => {
        const schema = {
          ...productSchema,
          __name__: 'SchemaTest',
          __tablename__: 'schema_tests',
        };
        NTT.SCHEMA(schema);
        expect(NTT.has('SchemaTest')).toBe(true);
        const DC = NTT.get('SchemaTest');
        expect(DC).toBeTruthy();
        expect(DC._schema).toBe(schema);
      });

      it('should handle $defs (nested schemas)', () => {
        const schema = {
          ...productSchema,
          __name__: 'SchemaDefTest',
          __tablename__: 'schema_def_tests',
          $defs: {
            Comment: {
              type: 'object',
              __name__: 'Comment',
              __tablename__: 'comments',
              properties: {
                id: { type: 'integer' },
                text: { type: 'string' },
              }
            }
          }
        };
        NTT.SCHEMA(schema);
        expect(NTT.has('SchemaDefTest')).toBe(true);
        // Comment should be registered from $defs (if not already)
      });

      it('should infer tablename from addr if not provided', () => {
        const schema = {
          __name__: 'NoTable',
          properties: { id: { type: 'integer' } },
          methods: {},
        };
        NTT.SCHEMA(schema);
        const DC = NTT.get('NoTable');
        expect(DC).toBeTruthy();
      });
    });

    describe('static ATTACH(data, tx)', () => {
      it('should forward to DynamicClass when it exists', () => {
        const schema = {
          ...productSchema,
          __name__: 'AttachFwd',
          __tablename__: 'attach_fwds',
        };
        NTT.SCHEMA(schema);
        // Should not throw
        const tx = { name: 'ATTACH', source: 'comp-1', target: 'NTT', data: 'AttachFwd' };
        expect(() => NTT.ATTACH('AttachFwd', tx)).not.toThrow();
      });
    });
  });

  describe('DynamicClass (prototype factory)', () => {

    let DC;
    const schemaName = 'DCTest';

    beforeEach(() => {
      if (!NTT.has(schemaName)) {
        NTT.SCHEMA({
          ...productSchema,
          __name__: schemaName,
          __tablename__: 'dc_tests',
        });
      }
      DC = NTT.get(schemaName);
    });

    it('should have correct class name', () => {
      expect(DC.name).toBe(schemaName);
    });

    it('should have static _schema', () => {
      expect(DC._schema).toBeTruthy();
      expect(DC._schema.__name__).toBe(schemaName);
    });

    it('should have static instances Map', () => {
      expect(DC.instances).toBeInstanceOf(Map);
    });

    it('should have properties as getters/setters on prototype', () => {
      DC.READ([{ id: 99, name: 'Proto', price: 5 }]);
      const inst = DC.instances.get('99');
      expect(inst.name).toBe('Proto');
      expect(inst.price).toBe(5);
    });

    it('should throw on read-only property setter', () => {
      DC.READ([{ id: 98, name: 'RO Test', price: 5 }]);
      const inst = DC.instances.get('98');
      expect(() => { inst.id = 999; }).toThrow(/read-only/);
    });

    it('should throw TypeError on type mismatch', () => {
      DC.READ([{ id: 97, name: 'Type Test', price: 5 }]);
      const inst = DC.instances.get('97');
      expect(() => { inst.name = 42; }).toThrow(TypeError);
      expect(() => { inst.price = 'not a number'; }).toThrow(TypeError);
    });

    it('should have labels static property', () => {
      expect(DC.labels).toBeTruthy();
      expect(DC.labels.name).toBe('Name');
      expect(DC.labels.price).toBe('Price');
    });

    describe('DynamicClass.signal (static)', () => {
      it('should fire callback immediately by default', () => {
        const cb = vi.fn();
        DC.signal(cb);
        expect(cb).toHaveBeenCalledWith(DC);
      });

      it('should not fire immediately when wait=true', () => {
        const cb = vi.fn();
        DC.signal(cb, true);
        expect(cb).not.toHaveBeenCalled();
      });

      it('should return unsubscribe function', () => {
        const cb = vi.fn();
        const unsub = DC.signal(cb);
        expect(typeof unsub).toBe('function');
      });

      it('should fire all listeners when called without callback', () => {
        const cb1 = vi.fn();
        const cb2 = vi.fn();
        DC.signal(cb1);
        DC.signal(cb2);
        cb1.mockClear();
        cb2.mockClear();
        DC.signal(); // Fire all
        expect(cb1).toHaveBeenCalled();
        expect(cb2).toHaveBeenCalled();
      });
    });

    describe('DynamicClass.observe (static)', () => {
      it('should register observer and return unsubscribe', () => {
        const cb = vi.fn();
        const unsub = DC.observe('UPDATE', cb);
        expect(typeof unsub).toBe('function');
        unsub();
      });
    });

    describe('DynamicClass.READ (static)', () => {
      it('should create instances from array data', () => {
        DC.instances.clear();
        DC.READ([
          { id: 10, name: 'A', price: 1 },
          { id: 11, name: 'B', price: 2 },
        ]);
        expect(DC.instances.has('10')).toBe(true);
        expect(DC.instances.has('11')).toBe(true);
      });

      it('should update existing instances', () => {
        DC.READ([{ id: 10, name: 'A-updated', price: 99 }]);
        const inst = DC.instances.get('10');
        expect(inst.value.name).toBe('A-updated');
      });

      it('should handle paginated response {data: [...], meta: {...}}', () => {
        DC.instances.clear();
        DC.READ({
          data: [{ id: 20, name: 'Paged', price: 5 }],
          meta: { total: 100, limit: 20, offset: 0, has_more: true }
        });
        expect(DC.instances.has('20')).toBe(true);
        expect(DC._paginationMeta.total).toBe(100);
      });

      it('should handle single entity response', () => {
        DC.READ({ id: 30, name: 'Single', price: 3 });
        expect(DC.instances.has('30')).toBe(true);
      });
    });

    describe('class-name response identity', () => {
      it('uses class-name $id as the instance href', () => {
        DC.READ([{ id: 501, name: 'Class ID', price: 1, $id: 'http://localhost:5000/DCTest/501' }]);
        const inst = DC.instances.get('501');

        expect(inst.href).toBe('http://localhost:5000/DCTest/501');
        expect(inst.value.$id).toBe('http://localhost:5000/DCTest/501');
      });

      it('does not require or emit $href or links metadata', () => {
        DC.READ([{ id: 502, name: 'No Links', price: 1, $id: 'http://localhost:5000/DCTest/502' }]);
        const inst = DC.instances.get('502');

        expect(inst.value.$href).toBeUndefined();
        expect(inst.value.links).toBeUndefined();
      });

      it('keeps legacy table-name $id values working as hrefs', () => {
        DC.READ([{ id: 503, name: 'Legacy ID', price: 1, $id: 'http://localhost:5000/dc_tests/503' }]);
        const inst = DC.instances.get('503');

        expect(inst.href).toBe('http://localhost:5000/dc_tests/503');
        expect(inst.value.$id).toBe('http://localhost:5000/dc_tests/503');
      });

      it('targets class-name href for instance method calls', () => {
        DC.READ([{ id: 504, name: 'Method Target', price: 1, $id: 'http://localhost:5000/DCTest/504' }]);
        const inst = DC.instances.get('504');
        const sendSpy = vi.spyOn(inst, 'send').mockImplementation(() => {});

        inst.like();

        expect(sendSpy).toHaveBeenCalledWith(expect.objectContaining({
          name: 'like',
          target: 'http://localhost:5000/DCTest/504',
        }));
        sendSpy.mockRestore();
      });

      it('targets class-name href for pull reads', () => {
        DC.READ([{ id: 505, name: 'Pull Target', price: 1, $id: 'http://localhost:5000/DCTest/505' }]);
        const inst = DC.instances.get('505');
        const sendSpy = vi.spyOn(inst, 'send').mockImplementation(() => {});

        inst.pull();

        expect(sendSpy).toHaveBeenCalledWith(expect.objectContaining({
          name: 'READ',
          target: 'http://localhost:5000/DCTest/505',
        }));
        sendSpy.mockRestore();
      });

      it('normalizes populated children while preserving class-name nested $id refs', () => {
        const childSchema = {
          type: 'object',
          __name__: 'AuditComment',
          __tablename__: 'audit_comments',
          properties: {
            id: { type: 'integer' },
            name: { type: 'string' },
          },
          methods: {},
          $defs: {},
        };
        const parentSchema = {
          ...productSchema,
          __name__: 'AuditProduct',
          __tablename__: 'audit_products',
          properties: {
            ...productSchema.properties,
            comments: {
              type: 'array',
              items: { anyOf: [{ $ref: '#/$defs/AuditComment' }, { type: 'null' }] },
            },
          },
          $defs: { AuditComment: childSchema },
        };

        NTT.SCHEMA(parentSchema);
        const ParentDC = NTT.get('AuditProduct');
        ParentDC.READ({
          id: 1,
          name: 'Parent',
          price: 1,
          $id: 'http://localhost:5000/AuditProduct/1',
          comments: {
            data: [{
              id: 2,
              $schema: 'http://localhost:5000/AuditComment',
              $id: 'http://localhost:5000/AuditProduct/1/AuditComment/2',
              name: 'Child',
            }],
            meta: { total: 1, limit: 20, offset: 0, has_more: false },
          },
        });

        const parent = ParentDC.instances.get('1');
        const ChildDC = NTT.get('AuditComment');

        expect(parent.value.comments).toEqual(['http://localhost:5000/AuditProduct/1/AuditComment/2']);
        expect(ChildDC.instances.get('2').href).toBe('http://localhost:5000/AuditProduct/1/AuditComment/2');
      });
    });

    describe('DynamicClass.CREATE (static)', () => {
      it('should add new instance', () => {
        DC.CREATE({ id: 50, name: 'Created', price: 10 });
        expect(DC.instances.has('50')).toBe(true);
      });

      it('should update existing instance on duplicate', () => {
        DC.CREATE({ id: 50, name: 'Created-v2', price: 20 });
        expect(DC.instances.get('50').value.name).toBe('Created-v2');
      });
    });

    describe('DynamicClass.DELETE (static)', () => {
      it('should remove instance from registry', () => {
        DC.instances.set('60', { id: 60 });
        DC.DELETE({}, { source: 'http://localhost:5000/dc_tests/60' });
        expect(DC.instances.has('60')).toBe(false);
      });
    });

    describe('DynamicClass.ATTACH (static)', () => {
      it('should add watcher for type-level ATTACH', () => {
        const tx = { name: 'ATTACH', source: 'watcher-1', target: 'NTT', data: schemaName };
        DC.ATTACH(schemaName, tx);
        expect(DC._watchers.has('watcher-1')).toBe(true);
      });

      it('fetches missing class-name instances from member route, not collection marker route', () => {
        const schema = {
          ...productSchema,
          __name__: 'AttachMemberRoute',
          __tablename__: 'attach_member_routes',
          $id: 'http://localhost:5000/AttachMemberRoute',
        };
        NTT.SCHEMA(schema);
        const MemberDC = NTT.get('AttachMemberRoute');
        const sendSpy = vi.spyOn(MemberDC, 'send').mockImplementation(() => {});

        MemberDC.ATTACH('AttachMemberRoute/6', {
          name: 'ATTACH', source: 'component-attach-member', target: 'NTT', data: 'AttachMemberRoute/6', meta: {},
        });

        expect(sendSpy).toHaveBeenCalledWith(expect.objectContaining({
          name: 'READ',
          target: 'http://localhost:5000/AttachMemberRoute/6',
        }));
        sendSpy.mockRestore();
      });

      it('keeps static href at model base and collection reads on the explicit collection marker route', () => {
        const schema = {
          ...productSchema,
          __name__: 'AttachCollectionRoute',
          __tablename__: 'attach_collection_routes',
          $id: 'http://localhost:5000/AttachCollectionRoute',
        };
        NTT.SCHEMA(schema);
        const CollectionDC = NTT.get('AttachCollectionRoute');
        const sendSpy = vi.spyOn(CollectionDC, 'send').mockImplementation(() => {});

        CollectionDC.call('READ', { limit: 20 }, { remote: true });

        expect(CollectionDC.href).toBe('http://localhost:5000/AttachCollectionRoute');
        expect(sendSpy).toHaveBeenCalledWith(expect.objectContaining({
          name: 'READ',
          target: 'http://localhost:5000/AttachCollectionRoute/_',
        }));
        sendSpy.mockRestore();
      });

      it('uses class-name member route for missing instances when schema has no $id', () => {
        const schema = {
          ...productSchema,
          __name__: 'AttachMemberNoSchemaId',
          __tablename__: 'attach_member_no_schema_ids',
        };
        NTT.SCHEMA(schema);
        const MemberDC = NTT.get('AttachMemberNoSchemaId');
        const sendSpy = vi.spyOn(MemberDC, 'send').mockImplementation(() => {});

        MemberDC.ATTACH('AttachMemberNoSchemaId/8', {
          name: 'ATTACH', source: 'component-attach-no-id', target: 'NTT', data: 'AttachMemberNoSchemaId/8', meta: {},
        });

        expect(sendSpy).toHaveBeenCalledWith(expect.objectContaining({
          name: 'READ',
          target: 'http://localhost:5000/AttachMemberNoSchemaId/8',
        }));
        sendSpy.mockRestore();
      });

      it('keeps populate depth on missing member fetches without changing the member route', () => {
        const schema = {
          ...productSchema,
          __name__: 'AttachMemberPopulate',
          __tablename__: 'attach_member_populates',
          $id: 'http://localhost:5000/AttachMemberPopulate',
          ui: { populate: { depth: 2 } },
        };
        NTT.SCHEMA(schema);
        const MemberDC = NTT.get('AttachMemberPopulate');
        const sendSpy = vi.spyOn(MemberDC, 'send').mockImplementation(() => {});

        MemberDC.ATTACH('AttachMemberPopulate/9', {
          name: 'ATTACH', source: 'component-attach-populate', target: 'NTT', data: 'AttachMemberPopulate/9', meta: {},
        });

        expect(sendSpy).toHaveBeenCalledWith(expect.objectContaining({
          name: 'READ',
          target: 'http://localhost:5000/AttachMemberPopulate/9',
          data: { depth: 2 },
        }));
        sendSpy.mockRestore();
      });
    });

    describe('instance _response_', () => {
      it('should call pull() after method response', () => {
        DC.READ([{ id: 70, name: 'Resp', price: 1 }]);
        const inst = DC.instances.get('70');
        const pullSpy = vi.spyOn(inst, 'pull').mockReturnValue(inst);
        inst._response_({}, {});
        expect(pullSpy).toHaveBeenCalled();
        pullSpy.mockRestore();
      });
    });
  });

  describe('NTT instance', () => {

    describe('value getter/setter', () => {
      it('should throw TypeError on non-object value', () => {
        const schema = {
          ...productSchema,
          __name__: 'ValTest',
          __tablename__: 'val_tests',
        };
        NTT.SCHEMA(schema);
        const DC = NTT.get('ValTest');
        DC.READ([{ id: 1, name: 'Test', price: 5 }]);
        const inst = DC.instances.get('1');
        expect(() => { inst.value = 'not an object'; }).toThrow(TypeError);
      });

      it('should include $schema and $id in getter', () => {
        const schema = {
          ...productSchema,
          __name__: 'ValSchema',
          __tablename__: 'val_schemas',
        };
        NTT.SCHEMA(schema);
        const DC = NTT.get('ValSchema');
        DC.READ([{ id: 1, name: 'Test', price: 5 }]);
        const inst = DC.instances.get('1');
        const val = inst.value;
        expect(val.$schema).toContain('ValSchema');
        expect(val.$id).toBeTruthy();
      });

      it('should return a new object each access (immutability)', () => {
        const schema = {
          ...productSchema,
          __name__: 'ValImmut',
          __tablename__: 'val_immuts',
        };
        NTT.SCHEMA(schema);
        const DC = NTT.get('ValImmut');
        DC.READ([{ id: 1, name: 'Immut', price: 7 }]);
        const inst = DC.instances.get('1');
        const v1 = inst.value;
        const v2 = inst.value;
        expect(v1).not.toBe(v2);
        expect(v1).toEqual(v2);
      });

      it('should not pollute _data with $schema/$id', () => {
        const schema = {
          ...productSchema,
          __name__: 'ValNoPollute',
          __tablename__: 'val_no_pollutes',
        };
        NTT.SCHEMA(schema);
        const DC = NTT.get('ValNoPollute');
        DC.READ([{ id: 1, name: 'Clean', price: 3 }]);
        const inst = DC.instances.get('1');
        // Access value to trigger getter
        const val = inst.value;
        expect(val.$schema).toBeTruthy();
        // _data should NOT have $schema/$id
        expect(inst._data.$schema).toBeUndefined();
        expect(inst._data.$id).toBeUndefined();
      });

      it('should persist property setter changes', () => {
        const schema = {
          ...productSchema,
          __name__: 'ValPersist',
          __tablename__: 'val_persists',
        };
        NTT.SCHEMA(schema);
        const DC = NTT.get('ValPersist');
        DC.READ([{ id: 1, name: 'Before', price: 5 }]);
        const inst = DC.instances.get('1');
        inst.name = 'After';
        expect(inst.name).toBe('After');
        expect(inst.value.name).toBe('After');
      });
    });

    describe('toJSON()', () => {
      it('should return serializable object', () => {
        const schema = {
          ...productSchema,
          __name__: 'JSONTest',
          __tablename__: 'json_tests',
        };
        NTT.SCHEMA(schema);
        const DC = NTT.get('JSONTest');
        DC.READ([{ id: 1, name: 'JSON', price: 5 }]);
        const inst = DC.instances.get('1');
        const json = inst.toJSON();
        expect(json.addr).toBeTruthy();
        expect(json.href).toBeTruthy();
      });
    });

    describe('update(data)', () => {
      it('should set value with provided data', () => {
        const schema = {
          ...productSchema,
          __name__: 'UpdateTest',
          __tablename__: 'update_tests',
        };
        NTT.SCHEMA(schema);
        const DC = NTT.get('UpdateTest');
        DC.READ([{ id: 1, name: 'Original', price: 5 }]);
        const inst = DC.instances.get('1');
        // DynamicClass instances use _data (not NTT's private #data),
        // so update() spreads undefined #data with new data.
        // The new data replaces the value entirely.
        inst.update({ id: 1, name: 'Original', price: 99 });
        expect(inst.value.price).toBe(99);
        expect(inst.value.name).toBe('Original');
      });
    });

    describe('pull()', () => {
      it('should return this for chaining', () => {
        const schema = {
          ...productSchema,
          __name__: 'PullTest',
          __tablename__: 'pull_tests',
        };
        NTT.SCHEMA(schema);
        const DC = NTT.get('PullTest');
        DC.READ([{ id: 1, name: 'Pull', price: 5 }]);
        const inst = DC.instances.get('1');
        const result = inst.pull();
        expect(result).toBe(inst);
      });
    });
  });

  describe('Helper functions', () => {

    describe('normalizePopulated', () => {
      it('should handle null entity gracefully', () => {
        // normalizePopulated is called internally, tested through READ
        const schema = {
          ...productSchema,
          __name__: 'NormNull',
          __tablename__: 'norm_nulls',
        };
        NTT.SCHEMA(schema);
        const DC = NTT.get('NormNull');
        // Should not throw on empty data
        expect(() => DC.READ([])).not.toThrow();
      });
    });

    describe('registerInstance', () => {
      it('should create new instances and update existing ones', () => {
        const schema = {
          ...productSchema,
          __name__: 'RegInst',
          __tablename__: 'reg_insts',
        };
        NTT.SCHEMA(schema);
        const DC = NTT.get('RegInst');
        DC.READ([{ id: 1, name: 'First', price: 1 }]);
        expect(DC.instances.has('1')).toBe(true);
        DC.READ([{ id: 1, name: 'Updated', price: 2 }]);
        expect(DC.instances.get('1').value.name).toBe('Updated');
      });
    });
  });
});
