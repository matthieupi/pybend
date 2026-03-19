/**
 * StreamActor — Mixin that adds TX-aware stream dispatch to any component.
 *
 * Unwraps STREAM envelopes (Level 3 actor routing) and dispatches
 * inner events to UPPERCASE handler methods on the component.
 *
 * Usage:
 *   class MyComponent extends StreamActor(HTMLElement) {
 *       TEXT(data, meta)  { ... }  // called when stream yields {name:'text', ...}
 *       DONE(data, meta)  { ... }  // called when stream yields {name:'done', ...}
 *       STREAM_END(data)  { ... }  // called when SSE stream closes
 *       STREAM_ERROR(err) { ... }  // called on stream error
 *   }
 *
 * Convention: UPPERCASE methods = TX inbox handlers.
 *            lowercase/camelCase = internal component logic.
 */
import HTTP from '../core/transport/HTTP.js';

export const StreamActor = (Base) => class extends Base {
    #handle = null;

    /**
     * Open a streaming connection. Chunks dispatch to UPPERCASE handlers.
     * @param {string} url - SSE endpoint URL
     * @param {object} payload - POST body
     */
    stream(url, payload = {}) {
        this.#handle?.cancel();
        this.#handle = HTTP.stream(url, payload,
            (data) => this.#dispatch(data),
            (data) => { this.#handle = null; this.STREAM_END?.(data); },
            (err)  => { this.#handle = null; this.STREAM_ERROR?.(err); },
        );
    }

    /**
     * Cancel an active stream.
     */
    streamClose() {
        this.#handle?.cancel();
        this.#handle = null;
    }

    /**
     * Unwrap STREAM envelope and dispatch to UPPERCASE handler.
     *
     * Level 3: {name:'STREAM', data:{name:'text', data:{text:'hello'}}}
     *   -> unwrap -> inner = {name:'text', data:{text:'hello'}}
     *   -> this.TEXT({text:'hello'})
     *
     * Level 1/2: {name:'text', data:{text:'hello'}}
     *   -> no unwrap needed
     *   -> this.TEXT({text:'hello'})
     */
    #dispatch(data) {
        let inner = data;
        if (inner?.name === 'STREAM') inner = inner.data;

        const name = inner?.name?.toUpperCase();
        console.debug('[StreamActor]', name, typeof this[name], inner?.data);
        if (name && typeof this[name] === 'function') {
            this[name](inner.data, inner.meta);
        }
    }

    /**
     * Schema-aware validation: warn if declared events have no handler.
     * Call after schema loads.
     */
    _validateStreamHandlers(schema, methodName) {
        const events = schema?.methods?.[methodName]?.events ?? {};
        for (const name of Object.keys(events)) {
            if (typeof this[name.toUpperCase()] !== 'function') {
                console.warn(`[${this.tagName}] No handler for stream event '${name.toUpperCase()}'`);
            }
        }
    }
};
