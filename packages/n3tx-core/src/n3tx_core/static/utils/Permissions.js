/** Evaluate schema presentation permissions; server policies remain binding. */
import { config } from '../config.js';
import Logging from './Logging.js';

/** Share authenticated identity and native schema presentation decisions. */
class Permissions {
  #user = null;
  #ready = false;
  #promise = null;
  #ruleCache = new Map();

  /** Read authenticated identity.
   * @returns {Object|null} Current user or null. */
  get user() { return this.#user; }

  /** Check whether an identity is available.
   * @returns {boolean} Whether the user is authenticated. */
  get authenticated() { return !!this.#user; }

  /** Read the current role.
   * @returns {string} Role, defaulting to anonymous. */
  get role() { return this.#user?.role || 'anonymous'; }

  /** Initialize identity once through the native authentication endpoint.
   * @returns {Promise<Object|null>} Current identity or null. */
  init() {
    // 0. Share the existing initialization request.
    if (this.#promise) return this.#promise;
    this.#promise = this.#fetchUser();
    return this.#promise;
  }

  /** Fetch authenticated identity without exposing tokens to consumers.
   * @returns {Promise<Object|null>} Current identity or null. */
  async #fetchUser() {
    // 0. Avoid unauthenticated requests when no native token is stored.
    const token = window.localStorage.getItem('jwtToken');
    if (!token) {
      this.#user = null;
      this.#ready = true;
      return null;
    }
    // 1. Resolve identity and invalidate cached field decisions.
    try {
      const headers = { 'x-access-token': token };
      const resp = await fetch(`${config.API_URL}/auth/me`, { headers });
      this.#user = resp.ok ? await resp.json() : null;
    } catch (error) {
      Logging.warn('[Permissions] Failed to fetch /auth/me', error.message);
      this.#user = null;
    }
    this.#ready = true;
    this.#ruleCache.clear();
    return this.#user;
  }

  /** Evaluate field visibility from its native schema access hint.
   * @param {Object} fieldDef Schema property definition.
   * @returns {boolean} Whether field presentation is permitted. */
  canView(fieldDef) {
    return this.#cachedEval(fieldDef?.access?.view);
  }

  /** Evaluate field editing from its native schema access hint.
   * @param {Object} fieldDef Schema property definition.
   * @returns {boolean} Whether editing presentation is permitted. */
  canEdit(fieldDef) {
    return this.#cachedEval(fieldDef?.access?.edit);
  }

  /** Evaluate a model action using its exact rule or wildcard fallback.
   * @param {Object} accessDict Native schema access rules.
   * @param {string} action Action name, including list or read.
   * @param {Object} [resource] Optional entity for ownership evaluation.
   * @returns {boolean} Whether the action may be presented. */
  canAction(accessDict, action, resource) {
    // 0. Preserve unrestricted presentation when no rule is declared.
    if (!accessDict) return true;
    const rule = accessDict[action] || accessDict['*'];
    if (!rule) return true;
    return this.#evaluateCompositeRule(rule, resource);
  }

  /** Memoize field-rule decisions until identity changes.
   * @param {string|null|undefined} rule Field access rule.
   * @returns {boolean} Cached or newly evaluated permission. */
  #cachedEval(rule) {
    // 0. Resolve common defaults before the memoized decision.
    if (rule === undefined || rule === null) return true;
    if (rule === 'anyone') return true;
    const cached = this.#ruleCache.get(rule);
    if (cached !== undefined) return cached;
    const result = this.#evaluateRule(rule);
    this.#ruleCache.set(rule, result);
    return result;
  }

  /** Evaluate a simple field-rule string against current identity.
   * @param {string|null|undefined} rule Field access rule.
   * @returns {boolean} Whether field presentation is permitted. */
  #evaluateRule(rule) {
    // 0. Resolve built-ins; other strings retain role-name interpretation.
    if (rule === undefined || rule === null) return true;
    if (rule === 'anyone') return true;
    if (rule === 'authenticated') return this.authenticated;
    if (rule === 'owner') return this.authenticated;
    return this.role === rule;
  }

  /** Evaluate a serialized native model rule.
   * @param {Object} rule Serialized rule or composition.
   * @param {Object} [resource] Entity for OWNER evaluation.
   * @returns {boolean} Whether the rule permits presentation. */
  #evaluateCompositeRule(rule, resource) {
    // 0. Evaluate leaf rules before their logical composition.
    if (!rule || typeof rule !== 'object') return true;
    if (typeof rule.rule === 'string') {
      if (rule.rule === 'never') return false;
      if (rule.rule === 'anyone') return true;
      if (rule.rule === 'authenticated') return this.authenticated;
      if (rule.rule === 'owner') return this.#evaluateOwner(rule, resource);
      if (rule.rule === 'role') {
        return Array.isArray(rule.roles) && rule.roles.includes(this.role);
      }
      return true;
    }
    // 1. Preserve logical rule composition, including explicit denial.
    if (rule.op === 'or') {
      return (rule.rules || []).some(r =>
        this.#evaluateCompositeRule(r, resource));
    }
    if (rule.op === 'and') {
      return (rule.rules || []).every(r =>
        this.#evaluateCompositeRule(r, resource));
    }
    if (rule.op === 'not') {
      return !this.#evaluateCompositeRule(rule.rule, resource);
    }
    return true;
  }

  /** Compare a resource's owner with the current authenticated identity.
   * @param {Object} rule Native owner rule with optional field override.
   * @param {Object} [resource] Entity; absence defers resource checks.
   * @returns {boolean} Whether owner presentation is permitted. */
  #evaluateOwner(rule, resource) {
    // 0. Require identity and compare a present ownership value.
    if (!this.authenticated) return false;
    if (!resource) return true;
    const field = rule.field || 'user_owner';
    let ownerVal = resource[field];
    if (ownerVal == null) return false;
    if (typeof ownerVal === 'string' && ownerVal.includes('/')) {
      const id = parseInt(ownerVal.replace(/\/+$/, '').split('/').pop());
      if (!isNaN(id)) ownerVal = id;
    }
    return ownerVal === this.#user?.user_id;
  }
}

/** Shared native presentation-permission evaluator. */
export const permissions = new Permissions();

/* Changelog
 * - 2026-11-02: Honor native NEVER rules in action presentation. */
