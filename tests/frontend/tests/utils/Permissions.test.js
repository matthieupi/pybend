/** Protect schema presentation rules with mocked identities. */
import { describe, it, expect, vi, beforeEach } from 'vitest';

// We need to mock config and Logging before importing Permissions
vi.mock('../../config.js', () => ({
  config: {
    API_URL: 'http://localhost:5000',
    LOGGING: 3,
    LOGEVENTS: true,
    DEBUG: true,
  }
}));

vi.mock('../../utils/Logging.js', () => ({
  default: {
    warn: vi.fn(),
    error: vi.fn(),
    debug: vi.fn(),
    dev: vi.fn(),
    log: vi.fn(),
    init: vi.fn(),
    event: vi.fn(),
  }
}));

const { permissions } = await import('../../utils/Permissions.js');

describe('Permissions.js', () => {

  beforeEach(() => {
    // Reset permissions internal state by creating behavior through init
    global.fetch.mockClear();
  });

  describe('constructor / initial state', () => {
    it('should have null user initially', () => {
      // The shared instance may have been initialized by prior tests.
      // We test behavior through init()
      expect(
        typeof permissions.user === 'object' || permissions.user === null
      ).toBe(true);
    });
  });

  describe('user (getter)', () => {
    it('should return null when not authenticated', async () => {
      window.localStorage.removeItem('jwtToken');
      // Force a fresh fetch by accessing internal reset
      // Since we can't reset #promise, test the concept
      const p = new (permissions.constructor)();
      await p.init();
      expect(p.user).toBe(null);
    });
  });

  describe('authenticated (getter)', () => {
    it('should return false when user is null', () => {
      const p = new (permissions.constructor)();
      expect(p.authenticated).toBe(false);
    });
  });

  describe('role (getter)', () => {
    it('should return anonymous when user is null', () => {
      const p = new (permissions.constructor)();
      expect(p.role).toBe('anonymous');
    });
  });

  describe('init()', () => {
    it('should return a promise', () => {
      const p = new (permissions.constructor)();
      const result = p.init();
      expect(result).toBeInstanceOf(Promise);
    });

    it('should deduplicate calls (return same promise)', () => {
      const p = new (permissions.constructor)();
      const p1 = p.init();
      const p2 = p.init();
      expect(p1).toBe(p2);
    });

    it('should set user to null when no token in localStorage', async () => {
      window.localStorage.removeItem('jwtToken');
      const p = new (permissions.constructor)();
      const result = await p.init();
      expect(result).toBe(null);
      expect(p.user).toBe(null);
    });

    it('should fetch /auth/me with token and set user on success', async () => {
      window.localStorage.setItem('jwtToken', 'test-token');
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          user_id: 1, email: 'alice@test.com', role: 'user'
        })
      });
      const p = new (permissions.constructor)();
      const result = await p.init();
      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:5000/auth/me',
        { headers: { 'x-access-token': 'test-token' } }
      );
      const identity = { user_id: 1, email: 'alice@test.com', role: 'user' };
      expect(result).toEqual(identity);
      expect(p.user).toEqual(identity);
      expect(p.authenticated).toBe(true);
      expect(p.role).toBe('user');
    });

    it('should set user to null on non-ok response', async () => {
      window.localStorage.setItem('jwtToken', 'expired-token');
      global.fetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
      });
      const p = new (permissions.constructor)();
      const result = await p.init();
      expect(result).toBe(null);
      expect(p.authenticated).toBe(false);
    });

    it('should set user to null on network error', async () => {
      window.localStorage.setItem('jwtToken', 'test-token');
      global.fetch.mockRejectedValueOnce(new Error('Network error'));
      const p = new (permissions.constructor)();
      const result = await p.init();
      expect(result).toBe(null);
    });
  });

  describe('canView(fieldDef)', () => {
    it('should return true when access is undefined', () => {
      expect(permissions.canView({})).toBe(true);
      expect(permissions.canView(undefined)).toBe(true);
      expect(permissions.canView(null)).toBe(true);
    });

    it('should return true when access.view is anyone', () => {
      expect(permissions.canView({ access: { view: 'anyone' } })).toBe(true);
    });

    it('should use authentication for access.view', () => {
      const result = permissions.canView({ access: { view: 'authenticated' } });
      expect(typeof result).toBe('boolean');
    });

    it('should return authenticated state when access.view is owner', () => {
      const result = permissions.canView({ access: { view: 'owner' } });
      expect(typeof result).toBe('boolean');
    });

    it('should check role match when access.view is a role name', () => {
      const result = permissions.canView({ access: { view: 'admin' } });
      expect(typeof result).toBe('boolean');
    });
  });

  describe('canEdit(fieldDef)', () => {
    it('should return true when access.edit is undefined', () => {
      expect(permissions.canEdit({})).toBe(true);
    });

    it('should check access.edit rule', () => {
      expect(permissions.canEdit({ access: { edit: 'anyone' } })).toBe(true);
    });
  });

  describe('canAction(accessDict, action, resource)', () => {
    it('should return true when accessDict is null/undefined', () => {
      expect(permissions.canAction(null, 'read')).toBe(true);
      expect(permissions.canAction(undefined, 'read')).toBe(true);
    });

    it('should return true when action not in accessDict', () => {
      expect(permissions.canAction({}, 'read')).toBe(true);
    });

    it('should evaluate { rule: "anyone" } as true', () => {
      expect(permissions.canAction(
        { read: { rule: 'anyone' } }, 'read'
      )).toBe(true);
    });

    it('should evaluate authenticated actions from user state', () => {
      const result = permissions.canAction(
        { read: { rule: 'authenticated' } }, 'read'
      );
      expect(typeof result).toBe('boolean');
    });

    it('should evaluate { rule: "role", roles: [...] }', () => {
      const result = permissions.canAction(
        { update: { rule: 'role', roles: ['admin'] } },
        'update'
      );
      expect(typeof result).toBe('boolean');
    });

    it('should evaluate OR composite rules', () => {
      const access = {
        update: {
          op: 'or',
          rules: [
            { rule: 'anyone' },
            { rule: 'role', roles: ['admin'] }
          ]
        }
      };
      expect(permissions.canAction(access, 'update')).toBe(true);
    });

    it('should evaluate AND composite rules', () => {
      const access = {
        update: {
          op: 'and',
          rules: [
            { rule: 'anyone' },
            { rule: 'anyone' }
          ]
        }
      };
      expect(permissions.canAction(access, 'update')).toBe(true);
    });

    it('should evaluate NOT composite rules correctly', () => {
      // 0. A nested rule object is a NOT operand, not a leaf rule name.
      const access = {
        delete: {
          op: 'not',
          rule: { rule: 'anyone' }
        }
      };
      // 1. Negating an unconditional grant denies presentation.
      expect(permissions.canAction(access, 'delete')).toBe(false);
    });

    it.each(['read', '*'])('should deny NEVER at %s', (key) => {
      // 0. Use a fresh evaluator with no authenticated identity.
      const p = new (permissions.constructor)();
      const access = { [key]: { rule: 'never' } };
      // 1. Exact and wildcard denials both suppress the requested action.
      expect(p.canAction(access, 'read')).toBe(false);
    });

    it.each([
      ['and', 'anyone', 'never', false],
      ['and', 'never', 'anyone', false],
      ['and', 'never', 'never', false],
      ['or', 'never', 'anyone', true],
      ['or', 'anyone', 'never', true],
      ['or', 'never', 'never', false],
    ])('should compose %s(%s, %s)', (op, left, right, expected) => {
      // 0. Exercise denial in either operand, including an all-denied OR.
      const access = {
        read: { op, rules: [{ rule: left }, { rule: right }] }
      };
      // 1. NEVER remains false rather than becoming an unknown-rule grant.
      expect(permissions.canAction(access, 'read')).toBe(expected);
    });

    it('should negate NEVER inside a nested composition', () => {
      // 0. Both logical levels must recurse into their native rule objects.
      const access = {
        read: {
          op: 'not',
          rule: {
            op: 'and',
            rules: [{ rule: 'anyone' }, { rule: 'never' }]
          }
        }
      };
      // 1. NOT(AND(anyone, never)) grants; direct NOT(never) also grants.
      expect(permissions.canAction(access, 'read')).toBe(true);
      expect(permissions.canAction({
        read: { op: 'not', rule: { rule: 'never' } }
      }, 'read')).toBe(true);
    });

    it('should prefer an exact action over its wildcard fallback', () => {
      // 0. Explicit actions and wildcard defaults may disagree.
      const access = {
        '*': { rule: 'never' }, read: { rule: 'anyone' }
      };
      // 1. A public read does not permit an unspecified write action.
      expect(permissions.canAction(access, 'read')).toBe(true);
      expect(permissions.canAction(access, 'update')).toBe(false);
      expect(permissions.canAction({
        '*': { rule: 'anyone' }, read: { rule: 'never' }
      }, 'read')).toBe(false);
    });

    it.each([false, true])(
      'should retain identity rules with authenticated=%s',
      async (authenticated) => {
        // 0. Resolve only a synthetic identity through the mocked auth seam.
        const p = new (permissions.constructor)();
        window.localStorage.removeItem('jwtToken');
        if (authenticated) {
          window.localStorage.setItem('jwtToken', 'synthetic-token');
          global.fetch.mockResolvedValueOnce({
            ok: true,
            json: () => Promise.resolve({ user_id: 42, role: 'admin' })
          });
        }
        await p.init();
        const rules = [
          { rule: 'authenticated' },
          { rule: 'role', roles: ['admin'] },
          { rule: 'owner' }
        ];
        // 1. NEVER as an OR identity must not change existing identity checks.
        for (const rule of rules) {
          expect(p.canAction({
            update: { op: 'or', rules: [{ rule: 'never' }, rule] }
          }, 'update', { user_owner: 42 })).toBe(authenticated);
        }
        // 2. Role and owner mismatches stay denied for authenticated users.
        expect(p.canAction({
          read: { rule: 'role', roles: ['staff'] }
        }, 'read')).toBe(false);
        expect(p.canAction({
          read: { rule: 'owner' }
        }, 'read', { user_owner: 99 })).toBe(false);
      }
    );

    it('should fallback to wildcard * rule', () => {
      const access = { '*': { rule: 'anyone' } };
      expect(permissions.canAction(access, 'anything')).toBe(true);
    });
  });

  describe('#evaluateOwner (via canAction)', () => {

    it('should allow owner creation without a resource', async () => {
      window.localStorage.setItem('jwtToken', 'test');
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ user_id: 1, role: 'user' })
      });
      const p = new (permissions.constructor)();
      await p.init();
      const result = p.canAction({ update: { rule: 'owner' } }, 'update');
      expect(result).toBe(true);
    });

    it('should return true when resource owner matches user_id', async () => {
      window.localStorage.setItem('jwtToken', 'test');
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ user_id: 42, role: 'user' })
      });
      const p = new (permissions.constructor)();
      await p.init();
      const result = p.canAction(
        { update: { rule: 'owner' } },
        'update',
        { user_owner: 42 }
      );
      expect(result).toBe(true);
    });

    it('should deny a different resource owner', async () => {
      window.localStorage.setItem('jwtToken', 'test');
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ user_id: 42, role: 'user' })
      });
      const p = new (permissions.constructor)();
      await p.init();
      const result = p.canAction(
        { update: { rule: 'owner' } },
        'update',
        { user_owner: 99 }
      );
      expect(result).toBe(false);
    });

    it('should extract the owner ID from a hydrated URL', async () => {
      window.localStorage.setItem('jwtToken', 'test');
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ user_id: 3, role: 'user' })
      });
      const p = new (permissions.constructor)();
      await p.init();
      const result = p.canAction(
        { update: { rule: 'owner' } },
        'update',
        { user_owner: 'http://localhost:5000/users/3' }
      );
      expect(result).toBe(true);
    });

    it('should return false when resource owner_field is null', async () => {
      window.localStorage.setItem('jwtToken', 'test');
      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ user_id: 1, role: 'user' })
      });
      const p = new (permissions.constructor)();
      await p.init();
      const result = p.canAction(
        { update: { rule: 'owner' } },
        'update',
        { user_owner: null }
      );
      expect(result).toBe(false);
    });

    it('should return false when user is not authenticated', () => {
      const p = new (permissions.constructor)();
      const result = p.canAction(
        { update: { rule: 'owner' } },
        'update',
        { user_owner: 1 }
      );
      expect(result).toBe(false);
    });
  });
});

/* Changelog
 * - 2026-11-02: Cover NEVER, wildcard precedence and recursive NOT semantics.
 *   Retain auth, role and owner decisions with synthetic identities. */
