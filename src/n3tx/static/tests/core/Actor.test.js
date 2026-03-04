import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../../utils/Assert.js', () => ({
  default: vi.fn((caller, cond, msg) => {
    if (!cond) throw new Error(msg || 'Assertion failed');
  }),
  caution: vi.fn(),
  inform: vi.fn(),
}));

vi.mock('../../config.js', () => ({
  config: { LOGGING: 3, LOGEVENTS: true, DEBUG: true, API_URL: 'http://localhost:5000',
    E: { CONNECT: 'CONNECT', UPDATE: 'UPDATE', READ: 'READ' }
  }
}));

vi.mock('../../utils/Logging.js', () => ({
  default: { warn: vi.fn(), error: vi.fn(), debug: vi.fn(), dev: vi.fn(), log: vi.fn(), init: vi.fn(), event: vi.fn() }
}));

import Actor from '../../core/Actor.js';

/**
 * The base Actor class requires this.constructor.register(this) in the
 * constructor.  Only subclasses that have gone through Actor.subclass()
 * have the static register() method.  So we create a TestActor subclass
 * for any test that needs to instantiate an Actor.
 */
class TestActor extends Actor {}
Actor.subclass(TestActor);

describe('Actor.js', () => {

  describe('constructor(addr) via subclassed Actor', () => {
    it('should auto-generate addr if empty', () => {
      const actor = new TestActor();
      expect(actor.addr).toBeTruthy();
      expect(actor.addr.startsWith('actor-')).toBe(true);
    });

    it('should use provided addr', () => {
      const actor = new TestActor('my-actor');
      expect(actor.addr).toBe('my-actor');
    });

    it('should initialize children map', () => {
      const actor = new TestActor('test-children');
      expect(actor.children).toBeInstanceOf(Map);
    });

    it('should bind inbox and send', () => {
      const actor = new TestActor('test-bind');
      expect(typeof actor.inbox).toBe('function');
      expect(typeof actor.send).toBe('function');
    });
  });

  describe('get addr', () => {
    it('should return the private addr', () => {
      const actor = new TestActor('test-addr');
      expect(actor.addr).toBe('test-addr');
    });
  });

  describe('get children', () => {
    it('should return children map', () => {
      const actor = new TestActor('test-ch-map');
      expect(actor.children).toBeInstanceOf(Map);
    });
  });

  describe('static get addr', () => {
    it('should return class name', () => {
      expect(Actor.addr).toBe('Actor');
    });

    it('should return subclass name for subclassed actors', () => {
      expect(TestActor.addr).toBe('TestActor');
    });
  });

  describe('static isActor(obj)', () => {
    it('should return true for Actor instances', () => {
      const actor = new TestActor('test-is');
      expect(Actor.isActor(actor)).toBe(true);
    });

    it('should return true for __TypeActor marked objects', () => {
      const obj = { __TypeActor: true };
      expect(Actor.isActor(obj)).toBe(true);
    });

    it('should return false for non-actors', () => {
      expect(Actor.isActor({})).toBe(false);
      // isActor(null) returns null (falsy) because null && ... short-circuits to null
      expect(Actor.isActor(null)).toBeFalsy();
      expect(Actor.isActor(42)).toBeFalsy();
      expect(Actor.isActor('string')).toBeFalsy();
    });
  });

  describe('send(event) via base Actor class', () => {
    it('should throw when base Actor constructor is called (no register method)', () => {
      // The base Actor class does not have static register(), so new Actor() throws
      expect(() => new Actor('test-send')).toThrow();
    });
  });

  describe('spawn(addr, ActorClass, ...args)', () => {
    it('should create child actor', () => {
      const parent = new TestActor('parent-s1');
      const child = parent.spawn('child-s1', TestActor);
      expect(child).toBeInstanceOf(Actor);
      expect(child.addr).toBe('child-s1');
    });

    it('should return the child actor', () => {
      const parent = new TestActor('parent-s2');
      const child = parent.spawn('child-s2', TestActor);
      // spawn() stores child in #children (private) and returns it
      expect(child).toBeInstanceOf(Actor);
      expect(child.addr).toBe('child-s2');
    });

    it('should throw on duplicate addr', () => {
      const parent = new TestActor('parent-s3');
      parent.spawn('dup-child', TestActor);
      expect(() => parent.spawn('dup-child', TestActor)).toThrow();
    });
  });

  describe('static subclass(ChildClass, ...Mixins)', () => {
    it('should add static addr, children, send, inbox to ChildClass', () => {
      class MyActor extends Actor {}
      Actor.subclass(MyActor);
      expect(typeof MyActor.addr).toBe('string');
      expect(MyActor.children).toBeInstanceOf(Map);
      expect(typeof MyActor.send).toBe('function');
      expect(typeof MyActor.inbox).toBe('function');
    });

    it('should be idempotent (already augmented class)', () => {
      class MyActor2 extends Actor {}
      Actor.subclass(MyActor2);
      Actor.subclass(MyActor2); // Should not throw or duplicate
      expect(MyActor2.__TypeActor).toBe(true);
    });

    it('should throw if ChildClass is not a function', () => {
      expect(() => Actor.subclass('not a class')).toThrow();
      expect(() => Actor.subclass(null)).toThrow();
    });

    it('should apply mixins', () => {
      class MyActor3 extends Actor {}
      const Mixin = {
        apply: vi.fn((Base) => Base),
        name: 'TestMixin'
      };
      Actor.subclass(MyActor3, Mixin);
      expect(Mixin.apply).toHaveBeenCalledWith(MyActor3);
    });

    it('should throw if mixin has no apply method', () => {
      class MyActor4 extends Actor {}
      expect(() => Actor.subclass(MyActor4, { name: 'BadMixin' })).toThrow();
    });

    it('should mark class with __TypeActor', () => {
      class MyActor5 extends Actor {}
      Actor.subclass(MyActor5);
      expect(MyActor5.__TypeActor).toBe(true);
    });

    it('should set up static register method', () => {
      class MyActor7 extends Actor {}
      Actor.subclass(MyActor7);
      expect(typeof MyActor7.register).toBe('function');
    });

    it('should set up instance prototype send/inbox', () => {
      class MyActor6 extends Actor {}
      Actor.subclass(MyActor6);
      const inst = new MyActor6('test-inst');
      expect(typeof inst.send).toBe('function');
      expect(typeof inst.inbox).toBe('function');
    });
  });

  describe('static registerRoot(actor)', () => {
    it('should have root property defined', () => {
      // Actor.root may or may not be set depending on test isolation;
      // verify the static getter exists
      expect('root' in Actor).toBe(true);
    });
  });

  describe('static get root', () => {
    it('should return null or the registered root actor', () => {
      const root = Actor.root;
      // root is null until Matrix sets it; the getter should not throw
      expect(root === null || typeof root === 'object').toBe(true);
    });
  });
});
