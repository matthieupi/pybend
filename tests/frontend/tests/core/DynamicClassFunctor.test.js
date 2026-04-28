/**
 * DynamicClass Functor Verification Tests
 *
 * Verifies the Schema → DynamicClass transformation preserves structure.
 * The prototype() factory is a functor: it maps schema objects to JS classes
 * while preserving the schema's structural relationships.
 */

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

// ── Test schemas ───────────────────────────────────────────────────

const baseSchema = {
  __name__: 'FunctorBase',
  __tablename__: 'functor_bases',
  properties: {
    id: { type: 'integer', readOnly: true, title: 'ID' },
    name: { type: 'string', title: 'Name', minLength: 1 },
    price: { type: 'number', title: 'Price' },
    active: { type: 'boolean', title: 'Active' },
    description: { type: 'string', title: 'Description', readOnly: true },
  },
  methods: {
    like: {
      route: '/like', methods: ['POST'], scope: 'instancemethod',
      parameters: {}, title: 'Like',
    },
    publish: {
      route: '/publish', methods: ['POST'], scope: 'classmethod',
      parameters: { status: { type: 'string' } }, title: 'Publish',
    },
  },
  required: ['name'],
  ui: { field_order: ['name', 'price', 'description'] },
  access: { read: { rule: 'anyone' } },
};


describe('DynamicClass Functor Verification', () => {

  // ── Property Functor ────────────────────────────────────────────

  describe('Property Functor', () => {

    let DC;
    const schemaName = 'PropFunctor';

    beforeEach(() => {
      if (!NTT.has(schemaName)) {
        NTT.SCHEMA({ ...baseSchema, __name__: schemaName, __tablename__: 'prop_functors' });
      }
      DC = NTT.get(schemaName);
    });

    it('maps each schema property to a prototype getter', () => {
      const schemaFields = Object.keys(baseSchema.properties);
      DC.READ([{ id: 1, name: 'Test', price: 10, active: true, description: 'desc' }]);
      const inst = DC.instances.get('1');
      for (const field of schemaFields) {
        // Property descriptor should exist on prototype
        const desc = Object.getOwnPropertyDescriptor(DC.prototype, field);
        expect(desc).toBeTruthy();
        expect(desc.get).toBeTruthy();
      }
    });

    it('maps readOnly schema fields to throwing setters', () => {
      DC.READ([{ id: 2, name: 'RO', price: 5, active: false, description: 'readonly' }]);
      const inst = DC.instances.get('2');
      expect(() => { inst.id = 999; }).toThrow(/read-only/);
      expect(() => { inst.description = 'changed'; }).toThrow(/read-only/);
    });

    it('maps writable schema fields to working setters', () => {
      DC.READ([{ id: 3, name: 'Writable', price: 5, active: true, description: 'x' }]);
      const inst = DC.instances.get('3');
      inst.name = 'Changed';
      expect(inst.name).toBe('Changed');
      inst.price = 99;
      expect(inst.price).toBe(99);
    });

    it('maps schema title to labels', () => {
      expect(DC.labels.name).toBe('Name');
      expect(DC.labels.price).toBe('Price');
      expect(DC.labels.id).toBe('ID');
    });
  });


  // ── Type Validation Functor ─────────────────────────────────────

  describe('Type Validation Functor', () => {

    let DC;
    const schemaName = 'TypeFunctor';

    beforeEach(() => {
      if (!NTT.has(schemaName)) {
        NTT.SCHEMA({ ...baseSchema, __name__: schemaName, __tablename__: 'type_functors' });
      }
      DC = NTT.get(schemaName);
    });

    it('rejects wrong type for string field', () => {
      DC.READ([{ id: 1, name: 'Test', price: 5, active: true, description: 'x' }]);
      const inst = DC.instances.get('1');
      expect(() => { inst.name = 42; }).toThrow(TypeError);
    });

    it('rejects wrong type for number field', () => {
      DC.READ([{ id: 2, name: 'Test', price: 5, active: true, description: 'x' }]);
      const inst = DC.instances.get('2');
      expect(() => { inst.price = 'not-a-number'; }).toThrow(TypeError);
    });

    it('accepts correct types', () => {
      DC.READ([{ id: 3, name: 'Test', price: 5, active: true, description: 'x' }]);
      const inst = DC.instances.get('3');
      inst.name = 'valid string';
      expect(inst.name).toBe('valid string');
      inst.price = 42.5;
      expect(inst.price).toBe(42.5);
    });
  });


  // ── Method Functor ──────────────────────────────────────────────

  describe('Method Functor', () => {

    let DC;
    const schemaName = 'MethodFunctor';

    beforeEach(() => {
      if (!NTT.has(schemaName)) {
        NTT.SCHEMA({ ...baseSchema, __name__: schemaName, __tablename__: 'method_functors' });
      }
      DC = NTT.get(schemaName);
    });

    it('maps each schema method to a callable function on instances', () => {
      DC.READ([{ id: 1, name: 'Test', price: 5, active: true, description: 'x' }]);
      const inst = DC.instances.get('1');
      for (const methodName of Object.keys(baseSchema.methods)) {
        expect(typeof inst[methodName]).toBe('function');
      }
    });

    it('preserves method count', () => {
      DC.READ([{ id: 2, name: 'Test', price: 5, active: true, description: 'x' }]);
      const inst = DC.instances.get('2');
      const schemaMethods = Object.keys(baseSchema.methods);
      const instanceMethods = schemaMethods.filter(m => typeof inst[m] === 'function');
      expect(instanceMethods.length).toBe(schemaMethods.length);
    });
  });


  // ── $defs Functor ───────────────────────────────────────────────

  describe('$defs Functor', () => {

    it('maps nested object $defs to DynamicClasses', () => {
      const schema = {
        ...baseSchema,
        __name__: 'DefsFunctor',
        __tablename__: 'defs_functors',
        $defs: {
          NestedComment: {
            type: 'object',
            __name__: 'NestedComment',
            __tablename__: 'nested_comments',
            properties: {
              id: { type: 'integer', readOnly: true },
              text: { type: 'string', title: 'Text' },
            },
            methods: {},
          },
        },
      };
      NTT.SCHEMA(schema);
      expect(NTT.has('DefsFunctor')).toBe(true);
      // Nested model should also be registered
      expect(NTT.has('NestedComment')).toBe(true);
      const NestedDC = NTT.get('NestedComment');
      expect(NestedDC).toBeTruthy();
      expect(NestedDC.name).toBe('NestedComment');
    });

    it('skips non-object $defs', () => {
      const schema = {
        ...baseSchema,
        __name__: 'DefsSkip',
        __tablename__: 'defs_skips',
        $defs: {
          PrimitiveRef: {
            type: 'string',
            enum: ['draft', 'published'],
          },
        },
      };
      // Should not throw
      expect(() => NTT.SCHEMA(schema)).not.toThrow();
      expect(NTT.has('DefsSkip')).toBe(true);
    });
  });


  // ── Value Getter Immutability ───────────────────────────────────

  describe('Value Getter Immutability', () => {

    let DC;
    const schemaName = 'ImmutFunctor';

    beforeEach(() => {
      if (!NTT.has(schemaName)) {
        NTT.SCHEMA({ ...baseSchema, __name__: schemaName, __tablename__: 'immut_functors' });
      }
      DC = NTT.get(schemaName);
    });

    it('returns a new object on each access', () => {
      DC.READ([{ id: 1, name: 'Test', price: 5, active: true, description: 'x' }]);
      const inst = DC.instances.get('1');
      const v1 = inst.value;
      const v2 = inst.value;
      expect(v1).not.toBe(v2);
      expect(v1).toEqual(v2);
    });

    it('_data does not contain $schema or $id', () => {
      DC.READ([{ id: 2, name: 'Clean', price: 3, active: false, description: 'y' }]);
      const inst = DC.instances.get('2');
      // Trigger getter
      const val = inst.value;
      expect(val.$schema).toBeTruthy();
      expect(val.$id).toBeTruthy();
      // But _data should be clean
      expect(inst._data.$schema).toBeUndefined();
      expect(inst._data.$id).toBeUndefined();
    });

    it('includes $schema and $id in returned value', () => {
      DC.READ([{ id: 3, name: 'Meta', price: 1, active: true, description: 'z' }]);
      const inst = DC.instances.get('3');
      const val = inst.value;
      expect(val.$schema).toContain('ImmutFunctor');
      expect(val.$id).toBeTruthy();
    });
  });
});
