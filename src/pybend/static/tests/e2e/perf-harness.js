/**
 * Performance instrumentation harness.
 *
 * Monkey-patches NTT.SCHEMA, Formidable.getForm, HTTP.get and HTTP.post
 * with performance.mark() / performance.measure() calls.
 *
 * Injected at test time via page.addScriptTag({ content, type: 'module' }).
 * Never served in production — lives in tests/e2e/.
 */

import HTTP from '/core/transport/HTTP.js';
import { Formidable } from '/generators/form.js';

const NTT = window.NTT;

// ── NTT.SCHEMA ──────────────────────────────────────────────
const _origSCHEMA = NTT.SCHEMA.bind(NTT);
NTT.SCHEMA = function(data, tx) {
    performance.mark('ntt-schema-start');
    const result = _origSCHEMA(data, tx);
    performance.mark('ntt-schema-end');
    performance.measure('NTT.SCHEMA:' + (data?.__name__ || 'unknown'), 'ntt-schema-start', 'ntt-schema-end');
    return result;
};

// ── Formidable.getForm ──────────────────────────────────────
const _origGetForm = Formidable.getForm;
Formidable.getForm = function(ntt, mode, attachedMethods) {
    performance.mark('form-getform-start');
    const result = _origGetForm.call(this, ntt, mode, attachedMethods);
    performance.mark('form-getform-end');
    performance.measure('getForm:' + (ntt?.schema?.__name__ || 'unknown'), 'form-getform-start', 'form-getform-end');
    return result;
};

// ── HTTP.get ────────────────────────────────────────────────
let _httpSeq = 0;
const _origGet = HTTP.get.bind(HTTP);
HTTP.get = function(url, onSuccess, onError) {
    const perfId = 'http-get-' + (++_httpSeq);
    performance.mark(perfId + '-start');

    const wrappedSuccess = function(resp) {
        performance.mark(perfId + '-end');
        performance.measure('HTTP.get:' + url.replace(/https?:\/\/[^/]+/, ''), perfId + '-start', perfId + '-end');
        onSuccess(resp);
    };

    const wrappedError = function(err) {
        performance.mark(perfId + '-end');
        performance.measure('HTTP.get:' + url.replace(/https?:\/\/[^/]+/, ''), perfId + '-start', perfId + '-end');
        onError(err);
    };

    return _origGet(url, wrappedSuccess, wrappedError);
};

// ── HTTP.post ───────────────────────────────────────────────
const _origPost = HTTP.post.bind(HTTP);
HTTP.post = function(url, data, onSuccess, onError) {
    const perfId = 'http-post-' + (++_httpSeq);
    performance.mark(perfId + '-start');

    const wrappedSuccess = function(resp) {
        performance.mark(perfId + '-end');
        performance.measure('HTTP.post:' + url.replace(/https?:\/\/[^/]+/, ''), perfId + '-start', perfId + '-end');
        onSuccess(resp);
    };

    const wrappedError = function(err) {
        performance.mark(perfId + '-end');
        performance.measure('HTTP.post:' + url.replace(/https?:\/\/[^/]+/, ''), perfId + '-start', perfId + '-end');
        onError(err);
    };

    return _origPost(url, data, wrappedSuccess, wrappedError);
};

window.__PYBEND_PERF_HARNESS__ = true;
