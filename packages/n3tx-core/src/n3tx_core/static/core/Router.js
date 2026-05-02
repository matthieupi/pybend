/**
 * Router — Pure navigation state Actor.
 *
 * Manages route state, history stack, and optional hash sync.
 * No DOM, no view management — that's ntx-router's job.
 *
 * TX Handlers:
 *   NAVIGATE(data) — push route onto stack, or reset stack for base routes/home, update hash, notify observers
 *   BACK(data)     — pop route from stack, update hash, notify observers
 *
 * Observable property: 'route' — fires (newRoute, oldRoute) on change.
 *
 * Route grammar (all routes are strings):
 *   @appName[?params]               — app-level view (e.g. @profile, @settings?tab=security)
 *   Model[/id[/action]][?params]    — entity view (e.g. Product, Product/3, Grant/5/analyze)
 *   Model/@[view][?params]          — collection view route (e.g. Product/@, Product/@table)
 *   Model/id/@[view][?params]       — member view route (e.g. Product/1/@, Product/1/@chat)
 *
 * Pure utility functions (framework-agnostic, no state):
 *   parseRoute(string)              — route string → structured data
 *   buildRoute(parts)               — structured data → route string
 *   resolveRoute(parsed, getSchema) — parsed route + schema → { tag, attrs, title }
 */
import Actor from './Actor.js';
import Observable from './Observable.js';
import { matrix } from './Matrix.js';
import { config } from '../config.js';

const routers = new Map();
const STACK_MAX = 50;
const VIEW_TOKEN_RE = /^[A-Za-z0-9][A-Za-z0-9_-]*$/;
const COMPONENT_TAG_RE = /^[a-z][a-z0-9]*(-[a-z0-9]+)+$/;

function invalidRoute(route, reason) {
    return { type: 'invalid', route, reason };
}

function isSafeViewToken(token) {
    return typeof token === 'string' && VIEW_TOKEN_RE.test(token);
}

function isSafeComponentTag(tag) {
    return typeof tag === 'string' && COMPONENT_TAG_RE.test(tag);
}

function isClassNameToken(token) {
    return typeof token === 'string' && /^[A-Z][A-Za-z0-9_]*$/.test(token);
}

function rendererTag(renderer, view) {
    const tag = view ? renderer[view] : null;
    return isSafeComponentTag(tag) ? tag : null;
}

function resolveViewTag(schema, view, scope) {
    const renderer = schema?.ui?.renderer || {};

    if (view && renderer[view]) return rendererTag(renderer, view);

    if (!view && scope === 'collection') {
        if (renderer.page) return isSafeComponentTag(renderer.page) ? renderer.page : null;
        if (renderer.list) return isSafeComponentTag(renderer.list) ? renderer.list : null;
        return 'ntx-list';
    }

    if (!view && scope === 'member') {
        if (renderer.detail) return isSafeComponentTag(renderer.detail) ? renderer.detail : null;
        if (renderer.item) return isSafeComponentTag(renderer.item) ? renderer.item : null;
        return 'ntx-item';
    }

    const known = scope === 'member'
        ? {
            item: renderer.item || 'ntx-item',
            detail: renderer.detail || renderer.item || 'ntx-item',
            chat: 'ntx-chat',
        }
        : {
            list: 'ntx-list',
            table: 'ntx-table',
        };

    if (view && known[view]) return known[view];
    if (view) return null;

    return 'ntx-list';
}

function apiRef(path) {
    return `${config.API_URL}/${path}`;
}

// ── Pure Route Functions (stateless, framework-agnostic) ──

/**
 * Parse a route string into structured data.
 * @param {string|null} route
 * @returns {{ type: string, app?: string, model?: string, id?: string|null, action?: string|null, view?: string|null, isViewRoute?: boolean, params?: object }}
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
    const parts = path.replace(/^\/+|\/+$/g, '').split('/').filter(Boolean);
    const params = query ? Object.fromEntries(new URLSearchParams(query)) : {};
    const model = parts[0];
    const id = parts[1] || null;
    const action = parts[2] || null;

    if (parts.length > 5) {
        return invalidRoute(route, 'too_many_segments');
    }

    // Nested class-name routes: Parent/1/Child[/2[/action|@view]]
    if (parts.length >= 3 && isClassNameToken(parts[2])) {
        const [parentModel, parentId, childModel, childId, nestedAction] = parts;

        if (parts.length === 3) {
            return {
                type: 'nested-collection', parentModel, parentId,
                model: childModel, id: null, action: null, params,
            };
        }

        if (childId === '@' || childId?.startsWith('@')) {
            if (parts.length > 4) return invalidRoute(route, 'too_many_segments');
            const view = childId === '@' ? null : childId.slice(1);
            if (view !== null && !isSafeViewToken(view)) {
                return invalidRoute(route, 'invalid_view');
            }
            return {
                type: 'nested-collection', parentModel, parentId,
                model: childModel, id: null, action: null,
                view, isViewRoute: true, params,
            };
        }

        if (nestedAction === '@' || nestedAction?.startsWith('@')) {
            const view = nestedAction === '@' ? null : nestedAction.slice(1);
            if (view !== null && !isSafeViewToken(view)) {
                return invalidRoute(route, 'invalid_view');
            }
            return {
                type: 'nested-detail', parentModel, parentId,
                model: childModel, id: childId, action: null,
                view, isViewRoute: true, params,
            };
        }

        if (parts.length === 4) {
            return {
                type: 'nested-detail', parentModel, parentId,
                model: childModel, id: childId, action: null, params,
            };
        }

        return {
            type: 'nested-action', parentModel, parentId,
            model: childModel, id: childId, action: nestedAction, params,
        };
    }

    if (parts.length > 3) {
        return invalidRoute(route, 'too_many_segments');
    }

    if (id === '@' || id?.startsWith('@')) {
        if (parts.length > 2) return invalidRoute(route, 'too_many_segments');
        const view = id === '@' ? null : id.slice(1);
        if (view !== null && !isSafeViewToken(view)) {
            return invalidRoute(route, 'invalid_view');
        }
        return {
            type: 'model', model, id: null, action: null,
            view, isViewRoute: true, params,
        };
    }

    if (action === '@' || action?.startsWith('@')) {
        const view = action === '@' ? null : action.slice(1);
        if (view !== null && !isSafeViewToken(view)) {
            return invalidRoute(route, 'invalid_view');
        }
        return {
            type: 'detail', model, id, action: null,
            view, isViewRoute: true, params,
        };
    }

    let type = 'model';
    if (id && action) type = 'action';
    else if (id) type = 'detail';

    return { type, model, id, action, params };
}

/**
 * Build a route string from structured parts (inverse of parseRoute).
 * @param {{ type: string, app?: string, model?: string, id?: string, action?: string, view?: string|null, isViewRoute?: boolean, params?: object }} parts
 * @returns {string}
 */
export function buildRoute(parts) {
    if (!parts || parts.type === 'home' || parts.type === 'invalid') return '';

    let route;
    if (parts.type === 'app') {
        route = '@' + parts.app;
    } else if (parts.type === 'nested-collection' || parts.type === 'nested-detail' || parts.type === 'nested-action') {
        route = `${parts.parentModel || ''}/${parts.parentId || ''}/${parts.model || ''}`;
        if (parts.id) route += '/' + parts.id;
        if (parts.isViewRoute) route += '/@' + (parts.view || '');
        else if (parts.action) route += '/' + parts.action;
    } else {
        route = parts.model || '';
        if (parts.id) route += '/' + parts.id;
        if (parts.isViewRoute) route += '/@' + (parts.view || '');
        else if (parts.action) route += '/' + parts.action;
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
    if (!parsed || parsed.type === 'home' || parsed.type === 'invalid') return null;

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
        if (parsed.isViewRoute) {
            const tag = resolveViewTag(schema, parsed.view, 'collection');
            if (!tag) return null;
            return {
                tag,
                attrs: { model: parsed.model, ...passthrough },
                title: schema?.title || schema?.__name__ || parsed.model,
            };
        }

        // List view: view= param overrides schema default
        let tag;
        if (params.view) {
            tag = resolveViewTag(schema, params.view, 'collection');
            if (!tag) return null;
        } else {
            tag = renderer.list || 'ntx-list';
            if (!isSafeComponentTag(tag)) return null;
        }
        return {
            tag,
            attrs: { model: parsed.model, ...passthrough },
            title: schema?.title || schema?.__name__ || parsed.model,
        };
    }

    if (parsed.type === 'detail') {
        const tag = parsed.isViewRoute
            ? resolveViewTag(schema, parsed.view, 'member')
            : renderer.detail || renderer.item || 'ntx-item';
        if (!tag || !isSafeComponentTag(tag)) return null;
        const detailAttrs = { ref: parsed.model + '/' + parsed.id, display: 'lg', ...passthrough };
        if (parsed.isViewRoute) delete detailAttrs.method;
        return {
            tag,
            attrs: detailAttrs,
            title: schema?.title || schema?.__name__ || parsed.model,
        };
    }

    if (parsed.type === 'nested-collection') {
        const tag = parsed.isViewRoute
            ? resolveViewTag(schema, parsed.view, 'collection')
            : renderer.list || 'ntx-list';
        if (!tag || !isSafeComponentTag(tag)) return null;
        return {
            tag,
            attrs: {
                model: parsed.model,
                parent: `${parsed.parentModel}/${parsed.parentId}`,
                ...passthrough,
            },
            title: schema?.title || schema?.__name__ || parsed.model,
        };
    }

    if (parsed.type === 'nested-detail') {
        const tag = parsed.isViewRoute
            ? resolveViewTag(schema, parsed.view, 'member')
            : renderer.detail || renderer.item || 'ntx-item';
        if (!tag || !isSafeComponentTag(tag)) return null;
        const ref = `${parsed.parentModel}/${parsed.parentId}/${parsed.model}/${parsed.id}`;
        return {
            tag,
            attrs: { 'data-model': parsed.model, ref: apiRef(ref), display: 'lg', ...passthrough },
            title: schema?.title || schema?.__name__ || parsed.model,
        };
    }

    if (parsed.type === 'nested-action') {
        const methodDef = schema?.methods?.[parsed.action];
        const tag = methodDef?.ui?.renderer
            || (methodDef?.stream ? 'ntx-stream' : null)
            || renderer.detail || renderer.item || 'ntx-item';
        if (!tag || !isSafeComponentTag(tag)) return null;
        return {
            tag,
            attrs: {
                'data-model': parsed.model,
                ref: apiRef(`${parsed.parentModel}/${parsed.parentId}/${parsed.model}/${parsed.id}`),
                method: parsed.action,
                display: 'lg',
                ...passthrough,
            },
            title: (schema?.title || schema?.__name__ || parsed.model) + ' / ' + parsed.action,
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
        const route = typeof data === 'string' ? data : data?.route;
        if (typeof route !== 'string') return;
        const next = route || null;

        const reset = tx?.meta?.reset === true || data?.reset === true;
        if (next === this.#current && !reset) return;

        const old = this.#current;
        if (reset) {
            this.#stack = [];
        } else {
            this.#stack.push(old);
            if (this.#stack.length > STACK_MAX) this.#stack.shift();
        }
        this.#current = next;
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
    navigate(route, options = {}) { this.NAVIGATE({ route, ...options }); }

    /** Navigate to a route and clear prior history. */
    reset(route) { this.NAVIGATE({ route, reset: true }); }

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
