/**
 * NTTRouter — Thin view container ("mini browser").
 *
 * Mounts components based on Router.resolved output.
 * Chrome (back button, title) rendered once in prerender(), updated in-place.
 *
 * Attributes:
 *   name  — Router actor address (required for addressing)
 *   hash  — Enable hash sync (presence = true)
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

    prerender() {
        this.shadowRoot.innerHTML = `
            <div class="router-chrome" hidden>
                <button class="back-btn" title="Back"></button>
                <h1 class="router-title"></h1>
            </div>
            <div class="router-content"><slot></slot></div>
        `;
        // Wire back button once — persists across navigations
        this.shadowRoot.querySelector('.back-btn').addEventListener('click', () => {
            if (this.#router) {
                this.send(new TX({ name: 'BACK', source: this.addr, target: this.#router.addr }));
            }
        });
    }

    connectedCallback() {
        super.connectedCallback();

        const name = this.getAttribute('name') || `router-${this.addr}`;
        let router = getRouter(name);
        if (!router) {
            const getSchema = (model) => window.NTT?.get(model)?.schema || null;
            router = new Router(name, {
                hash: this.hasAttribute('hash'),
                getSchema,
            });
        }
        this.#router = router;
        this.#routerUnsub = router.observe('route', () => this.render());

        // Auto-configure router attr on slot children
        this.querySelectorAll('[model]').forEach(el => {
            if (!el.hasAttribute('router')) el.setAttribute('router', name);
        });

        this.render();
    }

    disconnectedCallback() {
        super.disconnectedCallback();
        this.#routerUnsub?.();
    }

    render() {
        const resolved = this.#router?.resolved;
        const chrome = this.shadowRoot.querySelector('.router-chrome');
        const content = this.shadowRoot.querySelector('.router-content');
        if (!chrome || !content) return;  // prerender not called yet

        if (!resolved) {
            // Home state: hide chrome, show slot, remove any mounted view
            chrome.hidden = true;
            if (this.#currentView) {
                this.#currentView.remove();
                this.#currentView = null;
            }
            if (!content.querySelector('slot')) {
                content.innerHTML = '<slot></slot>';
            }
            return;
        }

        // Navigation state: show chrome, mount component
        chrome.hidden = false;
        chrome.querySelector('.router-title').textContent = resolved.title;
        chrome.querySelector('.back-btn').hidden = !this.#router.canGoBack;

        // Remove slot and previous view
        const slot = content.querySelector('slot');
        if (slot) slot.remove();
        if (this.#currentView) this.#currentView.remove();

        // Create and mount
        const el = document.createElement(resolved.tag);
        for (const [key, val] of Object.entries(resolved.attrs)) {
            if (typeof val === 'object') {
                el[key] = val;
            } else {
                el.setAttribute(key, String(val));
            }
        }
        if (el.hasAttribute('model') && !el.hasAttribute('router')) {
            el.setAttribute('router', this.#router.addr);
        }
        this.#currentView = el;
        content.appendChild(el);
    }
}

customElements.define('ntx-router', NTTRouter);
