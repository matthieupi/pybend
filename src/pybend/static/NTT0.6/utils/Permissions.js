/**
 * Permissions — Frontend access control utility.
 *
 * Fetches the current user's identity from /auth/me and evaluates
 * field-level access rules from JSON Schema against the user's role.
 *
 * Usage:
 *   import { permissions } from '../utils/Permissions.js';
 *   await permissions.init();
 *   permissions.canView(fieldDef);   // → boolean
 *   permissions.canEdit(fieldDef);   // → boolean
 *   permissions.user;                // → { user_id, email, role } or null
 */
import { config } from '../config.js';

class Permissions {

  #user = null;
  #ready = false;
  #promise = null;

  /** Current user identity (null if not authenticated). */
  get user() { return this.#user; }

  /** Whether the user is authenticated. */
  get authenticated() { return !!this.#user; }

  /** Current user's role (defaults to 'anonymous' if not logged in). */
  get role() { return this.#user?.role || 'anonymous'; }

  /**
   * Fetch the current user from /auth/me.
   * Safe to call multiple times — deduplicates the request.
   * Returns the user object or null if not authenticated.
   */
  init() {
    if (this.#promise) return this.#promise;

    this.#promise = this.#fetchUser();
    return this.#promise;
  }

  async #fetchUser() {
    const token = window.localStorage.getItem('jwtToken');
    if (!token) {
      this.#user = null;
      this.#ready = true;
      return null;
    }

    try {
      const headers = { 'x-access-token': token };
      const resp = await fetch(`${config.API_URL}/auth/me`, { headers });
      if (resp.ok) {
        this.#user = await resp.json();
      } else {
        this.#user = null;
      }
    } catch (e) {
      console.warn('[Permissions] Failed to fetch /auth/me:', e.message);
      this.#user = null;
    }

    this.#ready = true;
    return this.#user;
  }

  /**
   * Evaluate whether the current user can VIEW a field.
   *
   * Checks `fieldDef.access.view` against the current user:
   *   - undefined / missing → visible (no restriction)
   *   - 'anyone'            → always visible
   *   - 'authenticated'     → visible if logged in
   *   - 'owner'             → visible if logged in (ownership checked server-side)
   *   - 'admin' / role name → visible if user.role matches
   *
   * @param {Object} fieldDef — Schema property definition (e.g. schema.properties.price)
   * @returns {boolean}
   */
  canView(fieldDef) {
    return this.#evaluateRule(fieldDef?.access?.view);
  }

  /**
   * Evaluate whether the current user can EDIT a field.
   * Same rule semantics as canView but checks `fieldDef.access.edit`.
   *
   * @param {Object} fieldDef
   * @returns {boolean}
   */
  canEdit(fieldDef) {
    return this.#evaluateRule(fieldDef?.access?.edit);
  }

  /**
   * Evaluate whether the current user can perform an action on a model.
   * Checks `schema.access[action]` (model-level ABAC rules serialized to schema).
   *
   * Handles the serialized rule format from authorize.schema:
   *   - { rule: 'anyone' }
   *   - { rule: 'authenticated' }
   *   - { rule: 'owner' }
   *   - { rule: 'role', roles: ['admin'] }
   *   - { op: 'or', rules: [...] }
   *   - { op: 'and', rules: [...] }
   *   - { op: 'not', rule: {...} }
   *
   * @param {Object} accessDict — schema.access object
   * @param {string} action — 'read', 'create', 'update', 'delete'
   * @returns {boolean}
   */
  canAction(accessDict, action) {
    if (!accessDict) return true;
    const rule = accessDict[action] || accessDict['*'];
    if (!rule) return true;
    return this.#evaluateCompositeRule(rule);
  }

  // ── Internal ──

  /**
   * Evaluate a simple string rule against the current user.
   */
  #evaluateRule(rule) {
    if (rule === undefined || rule === null) return true;
    if (rule === 'anyone') return true;
    if (rule === 'authenticated') return this.authenticated;
    if (rule === 'owner') return this.authenticated; // ownership is server-enforced
    // Treat as role name
    return this.role === rule;
  }

  /**
   * Evaluate a composite rule object (from authorize.schema serialization).
   */
  #evaluateCompositeRule(rule) {
    if (!rule || typeof rule !== 'object') return true;

    // Simple rule: { rule: 'anyone' }
    if (rule.rule) {
      if (rule.rule === 'anyone') return true;
      if (rule.rule === 'authenticated') return this.authenticated;
      if (rule.rule === 'owner') return this.authenticated;
      if (rule.rule === 'role') {
        return Array.isArray(rule.roles) && rule.roles.includes(this.role);
      }
      return true;
    }

    // Composite: { op: 'or'|'and'|'not', rules: [...] }
    if (rule.op === 'or') {
      return (rule.rules || []).some(r => this.#evaluateCompositeRule(r));
    }
    if (rule.op === 'and') {
      return (rule.rules || []).every(r => this.#evaluateCompositeRule(r));
    }
    if (rule.op === 'not') {
      return !this.#evaluateCompositeRule(rule.rule);
    }

    return true;
  }
}

/** Singleton instance — import this. */
export const permissions = new Permissions();
