/**
 * Router — Pure navigation state Actor.
 *
 * Manages route state, history stack, and optional hash sync.
 * No DOM, no view management — that's ntt-router's job.
 *
 * TX Handlers:
 *   NAVIGATE(data) — push route onto stack, update hash, notify observers
 *   BACK(data)     — pop route from stack, update hash, notify observers
 *
 * Observable property: 'route' — fires (newRoute, oldRoute) on change.
 *
 * Route data can be:
 *   - string: entity ref like "Product/3" (serialized to hash)
 *   - object: { tag, attrs, title } (programmatic only, no hash)
 */
import Actor from './Actor.js';
import Observable from './Observable.js';
import { matrix } from './Matrix.js';

const routers = new Map();

export class Router extends Actor {

    #current = null;
    #stack = [];
    #hashSync = false;

    constructor(addr, { hash = false } = {}) {
        super(addr);
        matrix.register(this);
        this.#hashSync = hash;
        if (hash) {
            window.addEventListener('hashchange', () => this.#fromHash());
            this.#fromHash();
        }
        routers.set(addr, this);
    }

    get current()   { return this.#current; }
    get canGoBack() { return this.#stack.length > 0; }

    // ── TX Handlers ──

    NAVIGATE(data, tx) {
        if (data === this.#current) return;
        if (typeof data === 'object' && typeof this.#current === 'object'
            && JSON.stringify(data) === JSON.stringify(this.#current)) return;
        const old = this.#current;
        this.#stack.push(old);
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

    // ── Hash Sync (string routes only) ──

    #toHash() {
        if (typeof this.#current === 'string') {
            location.hash = this.#current;
        } else if (this.#current === null) {
            history.replaceState(null, '', location.pathname + location.search);
        }
    }

    #fromHash() {
        const hash = location.hash.slice(1);
        if (hash && hash !== this.#current) {
            const old = this.#current;
            this.#stack.push(old);
            this.#current = hash;
            this.notify('route', this.#current, old);
        } else if (!hash && this.#current) {
            const old = this.#current;
            this.#current = null;
            this.notify('route', this.#current, old);
        }
    }
}

export function getRouter(addr) {
    return routers.get(addr);
}

Actor.subclass(Router, Observable);
