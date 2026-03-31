/**
 * Router — Pure navigation state Actor.
 *
 * Manages route state, history stack, and optional hash sync.
 * No DOM, no view management — that's ntx-router's job.
 *
 * TX Handlers:
 *   NAVIGATE(data) — push route onto stack, update hash, notify observers
 *   BACK(data)     — pop route from stack, update hash, notify observers
 *
 * Observable property: 'route' — fires (newRoute, oldRoute) on change.
 *
 * Route grammar (all routes are strings):
 *   @appName[?params]               — app-level view (e.g. @profile, @settings?tab=security)
 *   Model[/id[/action]][?params]    — entity view (e.g. Product, Product/3, Grant/5/analyze)
 *
 * Pure utility functions (framework-agnostic, no state):
 *   parseRoute(string)              — route string → structured data
 *   buildRoute(parts)               — structured data → route string
 *   resolveRoute(parsed, getSchema) — parsed route + schema → { tag, attrs, title }
 */
import Actor from './Actor.js';
import Observable from './Observable.js';
import { matrix } from './Matrix.js';

const routers = new Map();
const STACK_MAX = 50;

// ── Pure Route Functions (stateless, framework-agnostic) ──

/**
 * Parse a route string into structured data.
 * @param {string|null} route
 * @returns {{ type: string, app?: string, model?: string, id?: string, action?: string, params: object }}
 */
export function parseRoute(route) {
    if (!route || typeof route !== 'string') return { type: 'home' };

    // App routes: @profile, @settings?tab=security
    if (route.startsWith('@')) {
        const [path, query] = route.slice(1).split('?');
        return {
            type: 'app',
            app: path,
            params: query ? Object.fromEntries(new URLSearchParams(query)) : {},
        };
    }

    // Entity routes: Model, Model/id, Model/id/action, all with optional ?params
    const [path, query] = route.split('?');
    const parts = path.split('/');
    const params = query ? Object.fromEntries(new URLSearchParams(query)) : {};
    const model = parts[0];
    const id = parts[1] || null;
    const action = parts[2] || null;

    let type = 'model';
    if (id && action) type = 'action';
    else if (id) type = 'detail';

    return { type, model, id, action, params };
}

/**
 * Build a route string from structured parts (inverse of parseRoute).
 * @param {{ type: string, app?: string, model?: string, id?: string, action?: string, params?: object }} parts
 * @returns {string}
 */
export function buildRoute(parts) {
    if (!parts || parts.type === 'home') return '';

    let route;
    if (parts.type === 'app') {
        route = '@' + parts.app;
    } else {
        route = parts.model || '';
        if (parts.id) route += '/' + parts.id;
        if (parts.action) route += '/' + parts.action;
    }

    const params = parts.params;
    if (params && Object.keys(params).length > 0) {
        route += '?' + new URLSearchParams(params).toString();
    }
    return route;
}

/**
 * Resolve a parsed route to a mount instruction: { tag, attrs, title }.
 * Pure function — no side effects, no global state access.
 *
 * @param {object} parsed — output of parseRoute()
 * @param {function} [getSchema] — (modelName) => schema object or null
 * @returns {{ tag: string, attrs: object, title: string } | null}
 */
export function resolveRoute(parsed, getSchema = () => null) {
    if (!parsed || parsed.type === 'home') return null;

    const params = parsed.params || {};

    if (parsed.type === 'app') {
        return {
            tag: 'ntx-' + parsed.app,
            attrs: { ...params },
            title: parsed.app.charAt(0).toUpperCase() + parsed.app.slice(1),
        };
    }

    const schema = getSchema(parsed.model);
    const renderer = schema?.ui?.renderer || {};

    // Filter out 'view' from pass-through params
    const passthrough = {};
    for (const [k, v] of Object.entries(params)) {
        if (k !== 'view') passthrough[k] = v;
    }

    if (parsed.type === 'model') {
        // List view: view= param overrides schema default
        let tag;
        if (params.view) {
            tag = params.view.startsWith('ntx-') ? params.view : 'ntx-' + params.view;
        } else {
            tag = renderer.list || 'ntx-list';
        }
        return {
            tag,
            attrs: { model: parsed.model, ...passthrough },
            title: schema?.title || schema?.__name__ || parsed.model,
        };
    }

    if (parsed.type === 'detail') {
        const tag = renderer.detail || renderer.item || 'ntx-item';
        return {
            tag,
            attrs: { ref: parsed.model + '/' + parsed.id, display: 'lg', ...passthrough },
            title: schema?.title || schema?.__name__ || parsed.model,
        };
    }

    if (parsed.type === 'action') {
        // Action view: check schema methods for renderer hint
        const methodDef = schema?.methods?.[parsed.action];
        const tag = methodDef?.ui?.renderer
            || (methodDef?.stream ? 'ntx-stream' : null)
            || renderer.detail || renderer.item || 'ntx-item';
        return {
            tag,
            attrs: {
                ref: parsed.model + '/' + parsed.id,
                method: parsed.action,
                display: 'lg',
                ...passthrough,
            },
            title: (schema?.title || schema?.__name__ || parsed.model) + ' / ' + parsed.action,
        };
    }

    return null;
}

export class Router extends Actor {

    #current = null;
    #stack = [];
    #hashSync = false;
    #schemaAccessor = () => null;
    #boundLocationChange = null;

    constructor(addr, { hash = true, getSchema = null } = {}) {
        super(addr);
        matrix.register(this);
        this.#hashSync = hash;
        if (getSchema) this.#schemaAccessor = getSchema;
        if (hash) {
            this.#boundLocationChange = () => this.#fromHash();
            window.addEventListener('hashchange', this.#boundLocationChange);
            this.#fromHash();
        }
        routers.set(addr, this);
    }

    get current()   { return this.#current; }
    get canGoBack() { return this.#stack.length > 0; }

    /** Fully resolved mount instruction for the current route. */
    get resolved() {
        return resolveRoute(parseRoute(this.#current), this.#schemaAccessor);
    }

    // ── TX Handlers ──

    NAVIGATE(data, tx) {
        if (typeof data !== 'string' || !data) return;
        if (data === this.#current) return;

        const old = this.#current;
        this.#stack.push(old);
        if (this.#stack.length > STACK_MAX) this.#stack.shift();
        this.#current = data;
        if (this.#hashSync) this.#toHash();
        this.notify('route', this.#current, old);
    }

    BACK(data, tx) {
        if (!this.canGoBack) return;
        const old = this.#current;
        this.#current = this.#stack.pop() ?? null;
        if (this.#hashSync) this.#toHash();
        this.notify('route', this.#current, old);
    }

    // ── Imperative API (sugar over TX handlers) ──

    /** Navigate to a route string. */
    navigate(route) { this.NAVIGATE(route); }

    /** Go back to the previous route. */
    back() { this.BACK(); }

    // ── Hash Sync (string routes only) ──

    #toHash() {
        if (this.#current) {
            location.hash = this.#current;
        } else {
            history.replaceState(null, '', location.pathname + location.search);
        }
    }

    #fromHash() {
        const hash = location.hash.slice(1);
        if (hash && hash !== this.#current) {
            const old = this.#current;
            if (old === null && this.#stack.length === 0) {
                this.#current = hash;
                this.notify('route', this.#current, old);
                return;
            }
            if (this.#stack[this.#stack.length - 1] === hash) {
                this.#stack.pop();
            } else {
                this.#stack.push(old);
                if (this.#stack.length > STACK_MAX) this.#stack.shift();
            }
            this.#current = hash;
            this.notify('route', this.#current, old);
        } else if (!hash && this.#current) {
            const old = this.#current;
            if (this.#stack[this.#stack.length - 1] === null) {
                this.#stack.pop();
            } else if (this.#stack.length === 1 && this.#stack[0] === old) {
                this.#stack.pop();
            }
            this.#current = null;
            this.notify('route', this.#current, old);
        }
    }
}

export function getRouter(addr) {
    return routers.get(addr);
}

Actor.subclass(Router, Observable);
