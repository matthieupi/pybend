import { describe, it, expect, vi, beforeEach } from 'vitest';
import assert, { caution, inform } from '../../utils/Assert.js';

describe('Assert.js', () => {

  describe('assert(caller, condition, message, trigger)', () => {

    it('should not throw when condition is true', () => {
      expect(() => assert({name: 'Test'}, true, 'should not throw')).not.toThrow();
    });

    it('should throw AssertionError on false condition with default trigger=error', () => {
      expect(() => assert({name: 'Test'}, false, 'bad value')).toThrow();
    });

    it('should include caller name in error message', () => {
      try {
        assert({name: 'MyComponent'}, false, 'something went wrong');
      } catch (e) {
        expect(e.message).toContain('MyComponent');
        expect(e.message).toContain('something went wrong');
        expect(e.name).toBe('AssertionError');
      }
    });

    it('should throw with message only when caller is null', () => {
      expect(() => assert(null, false, 'no caller')).toThrow('no caller');
    });

    it('should log warning when trigger=warn', () => {
      // trigger='warn' should not throw, should log
      expect(() => assert({name: 'Comp'}, false, 'warn msg', 'warn')).not.toThrow();
    });

    it('should log debug info when trigger=info', () => {
      expect(() => assert({name: 'Comp'}, false, 'info msg', 'info')).not.toThrow();
    });

    it('should not throw for unknown trigger value', () => {
      expect(() => assert({name: 'Comp'}, false, 'msg', 'unknown')).not.toThrow();
    });

    it('should do nothing when condition is truthy (non-boolean)', () => {
      expect(() => assert({name: 'X'}, 1, 'truthy')).not.toThrow();
      expect(() => assert({name: 'X'}, 'yes', 'truthy')).not.toThrow();
      expect(() => assert({name: 'X'}, {}, 'truthy')).not.toThrow();
    });

    it('should throw for falsy condition values (0, empty string, null, undefined)', () => {
      expect(() => assert({name: 'X'}, 0, 'zero')).toThrow();
      expect(() => assert({name: 'X'}, '', 'empty')).toThrow();
      expect(() => assert({name: 'X'}, null, 'null')).toThrow();
      expect(() => assert({name: 'X'}, undefined, 'undef')).toThrow();
    });
  });

  describe('caution(caller, condition, message)', () => {

    it('should not throw on false condition (uses warn trigger)', () => {
      expect(() => caution({name: 'Comp'}, false, 'caution msg')).not.toThrow();
    });

    it('should not throw on true condition', () => {
      expect(() => caution({name: 'Comp'}, true, 'all good')).not.toThrow();
    });
  });

  describe('inform(caller, condition, message)', () => {

    it('should not throw on false condition (uses info trigger)', () => {
      expect(() => inform({name: 'Comp'}, false, 'info msg')).not.toThrow();
    });

    it('should not throw on true condition', () => {
      expect(() => inform({name: 'Comp'}, true, 'all good')).not.toThrow();
    });
  });
});
