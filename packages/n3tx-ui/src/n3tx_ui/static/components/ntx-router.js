/**
 * NTTRouter — Generic view container ("mini browser").
 *
 * Loads any component dynamically on NAVIGATE, restores slot content on BACK.
 * Never needs editing to support new views — any custom element can be loaded.
 *
 * Attributes:
 *   name  — Router actor address (default: auto-generated)
 *   hash  — Enable hash sync (presence = true)
 *
 * Slot content = "home page": declared children are the default view.
 * NAVIGATE pushes a new view: hides slot, creates requested component, mounts it.
 * BACK pops the view: destroys current view, shows previous (or slot if at bottom).
 */
import { Component } from '../core/Component.js';
import { Router, getRouter } from '../core/Router.js';
import TX from '../core/TX.js';

export class NTTRouter extends Component {

    #router = null;
    #routerUnsub = null;
    #currentView = null;

    constructor() {
        super({});
    }

    get styles() { return new URL('./ntx-router.css', import.meta.url).href; }

    connectedCallback() {
        super.connectedCallback();

        // Create or reference Router actor
        const name = this.getAttribute('name') || `router-${this.addr}`;
        let router = getRouter(name);
        if (!router) {
            router = new Router(name, { hash: this.hasAttribute('hash') });
        }
        this.#router = router;

        // Observe route changes
        this.#routerUnsub = router.observe('route', () => this.render());

        // Auto-configure: set router attribute on child elements with model attr
        this.querySelectorAll('[model]').forEach(el => {
            if (!el.hasAttribute('router')) {
                el.setAttribute('router', name);
            }
        });

        this.render();
    }

    disconnectedCallback() {
        super.disconnectedCallback();
        this.#routerUnsub?.();
    }

    // ── Render ──

    render() {
        const route = this.#router?.current;
        if (route) {
            this.#mountView(route);
        } else {
            this.#showSlot();
        }
    }

    /** Show slotted (home) content */
    #showSlot() {
        if (this.#currentView) {
            this.#currentView.remove();
            this.#currentView = null;
        }
        this.shadowRoot.innerHTML = '<slot></slot>';
    }

    /** Resolve route data -> element tag + attributes, create and mount */
    #mountView(routeData) {
        let tag, attrs = {}, title = '';

        if (typeof routeData === 'string' && routeData.startsWith('@')) {
            // App route: @profile → <ntx-profile>, @settings → <ntx-settings>
            const routeName = routeData.slice(1);
            tag = `ntx-${routeName}`;
            title = routeName.charAt(0).toUpperCase() + routeName.slice(1);
        } else if (typeof routeData === 'string') {
            const model = routeData.split('/')[0];
            tag = this.#resolveTag(model);
            attrs = { ref: routeData };
            title = model;
        } else if (typeof routeData === 'object' && routeData.tag) {
            tag = routeData.tag;
            attrs = routeData.attrs || {};
            title = routeData.title || tag;
        } else {
            return this.#showSlot();
        }

        // Build shadow DOM: chrome (back button) + content area
        const showBack = this.#router.canGoBack;
        this.shadowRoot.innerHTML = `
            <div class="router-chrome">
                ${showBack ? '<button class="back-btn" title="Back"></button>' : ''}
                <h1 class="router-title">${title}</h1>
            </div>
            <div class="router-content"></div>
        `;

        // Back button -> BACK TX to Router
        if (showBack) {
            this.shadowRoot.querySelector('.back-btn').addEventListener('click', () => {
                this.send(new TX({ name: 'BACK', source: this.addr, target: this.#router.addr }));
            });
        }

        // Create and mount the component
        const el = document.createElement(tag);
        for (const [key, val] of Object.entries(attrs)) {
            if (typeof val === 'object') {
                el[key] = val;
            } else {
                el.setAttribute(key, String(val));
            }
        }
        // Auto-set router on model-bearing children (mirrors connectedCallback)
        if (el.hasAttribute('model') && !el.hasAttribute('router')) {
            el.setAttribute('router', this.#router.addr);
        }
        this.#currentView = el;
        this.shadowRoot.querySelector('.router-content').appendChild(el);
    }

    /** Resolve component tag from schema for a given model name */
    #resolveTag(model) {
        const NTT = window.NTT;
        if (!NTT) return 'ntx-item';
        const DC = NTT.get(model);
        return DC?.schema?.ui?.renderer?.detail
            || DC?.schema?.ui?.renderer?.item
            || 'ntx-item';
    }
}

customElements.define('ntx-router', NTTRouter);
