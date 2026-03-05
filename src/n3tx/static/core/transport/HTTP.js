import Logging from '../../utils/Logging.js';
import { showToast } from '../../utils/Toast.js';

export default class HTTP {
    constructor() {
    }
    
    static baseURL(action) {
        return "/api/";
    }

    /**
     * Extract a human-readable error message from a parsed JSON body or a
     * raw fetch Response.  Returns null when no error is detected.
     */
    static _extractError(json, status) {
        if (!json || typeof json !== 'object') return null;
        // Pydantic 422: detail is an array of validation error objects
        if (Array.isArray(json.detail)) {
            return json.detail.map(e => {
                const field = Array.isArray(e.loc) ? e.loc[e.loc.length - 1] : '?';
                return `${field}: ${e.msg}`;
            }).join('; ');
        }
        // FastAPI standard format (primary)
        if (json.detail) return String(json.detail);
        // Legacy format (fallback)
        if (json.error) return String(json.error);
        if (json.message && status && status >= 400) return String(json.message);
        return null;
    }

    /**
     * Extract structured validation errors from a Pydantic 422 response.
     * Returns null for non-validation errors, or [{field, message, type, input}]
     * for field-level display.
     */
    static _extractValidationErrors(json) {
        if (!json || typeof json !== 'object') return null;
        if (!Array.isArray(json.detail) || json.detail.length === 0) return null;
        return json.detail.map(e => ({
            field: Array.isArray(e.loc) ? e.loc[e.loc.length - 1] : '?',
            message: e.msg,
            type: e.type,
            input: e.input,
        }));
    }

    /**
     * Show a toast for an HTTP-level error (4xx / 5xx) with a parsed body.
     */
    static _toastHttpError(status, json) {
        const msg = HTTP._extractError(json, status)
            || `Request failed (${status})`;
        showToast(msg, 'error');
    }

    /**
     * Check a successful (2xx) JSON response for an embedded error field.
     * Some backend endpoints return 200 with {"error": "..."}.
     */
    static _checkBodyForError(json) {
        const msg = HTTP._extractError(json);
        if (msg) {
            showToast(msg, 'error');
            return true;
        }
        return false;
    }
    
    static rpc(method_name, args={}, kwargs={}, onSuccess=()=>{}) {
        let data= JSON.stringify({method_name: method_name, args:args, kwargs:kwargs})
        HTTP.post('rpc', data, onSuccess, ()=>{alert("FAIL")})
        
    }
    

    static get(url, onSuccess, onError) {
        let token = window.localStorage['jwtToken'];
        let header = new Headers();
        if(token) {
            header.append('x-access-token', `${token}`);
        }

        let errorHandled = false;
        fetch(url, {
            method: 'GET',
            headers: header
        }).then((resp) => {
            if(resp.ok) {
                return resp.json();
            }
            else if(this.checkIfUnauthorized(resp)) {
                window.location = "/login.html";
                return;
            }
            else if (resp.status == 404) {
                Logging.warn("[HTTP] Resource not found", url);
                errorHandled = true;
                onError({detail: `Resource not found: ${url}`});
                return;
            }
            else {
                errorHandled = true;
                return resp.json().then((json) => {
                    onError(json);
                });
            }
        }).then((resp) => {
            if (resp === undefined) return;
            if(resp.hasOwnProperty('token')) {
                window.localStorage['jwtToken'] = resp.token;
            }
            if (HTTP._checkBodyForError(resp)) {
                onError(resp);
            } else {
                onSuccess(resp);
            }

        }).catch((e) => {
            Logging.error("[HTTP] Error fetching " + url, e.message);
            if (!errorHandled) {
                showToast(e.message || 'Network error', 'error');
                onError(e.message);
            }
        });

    }

    static put(url, data, onSuccess, onError) {
        let token = window.localStorage['jwtToken'];
        let header = new Headers();

        // 0.0 Authorization
        if(token)
            header.append('x-access-token', `${token}`);
        // 0.1 Stringify if data is object
        if (typeof data == "object")
            data = JSON.stringify(data)
        // 0.2 Header
        header.append('Content-Type', 'application/json');
        // 0.3 Debug print
        Logging.dev("[HTTP] PUT", url);

        let errorHandled = false;
        fetch(url, {
            method: 'PUT',
            headers: header,
            body: data
        }).then((resp) => {
            if(resp.ok) {
                return resp.json();
            }
            else if(this.checkIfUnauthorized(resp)) {
                window.location = "/login.html";
                return;
            }
            else {
                errorHandled = true;
                return resp.json().then((json) => {
                    onError(json);
                });
            }
        }).then((resp) => {
            if (resp === undefined) return;
            if(resp.hasOwnProperty('token')) {
                window.localStorage['jwtToken'] = resp.token;
            }
            if (HTTP._checkBodyForError(resp)) {
                onError(resp);
            } else {
                onSuccess(resp);
            }
        }).catch((e) => {
            Logging.error("[HTTP] PUT error", e.message);
            if (!errorHandled) {
                showToast(e.message || 'Network error', 'error');
                onError(e.message);
            }
        });
    }

    static post(url, data, onSuccess, onError) {
        let token = window.localStorage['jwtToken'];
        let header = new Headers();

        // 0.0 Authorization
        if(token)
            header.append('x-access-token', `${token}`);
        // 0.1 Stringify if data is object
        if (typeof data == "object")
            data = JSON.stringify(data)
        // 0.2 Header
        header.append('Content-Type', 'application/json');
        // 0.3 Debug print
        Logging.dev("[HTTP] POST", url);

        let errorHandled = false;
        fetch(url, {
            method: 'POST',
            headers: header,
            body: data
        }).then((resp) => {
            if(resp.ok) {
                return resp.json();
            }
            else if(this.checkIfUnauthorized(resp)) {
                window.location = "/login.html";
                return;
            }
            else {
                errorHandled = true;
                return resp.json().then((json) => {
                    onError(json);
                });
            }
        }).then((resp) => {
            if (resp === undefined) return;
            if(resp.hasOwnProperty('token')) {
                window.localStorage['jwtToken'] = resp.token;
            }
            if (HTTP._checkBodyForError(resp)) {
                onError(resp);
            } else {
                onSuccess(resp);
            }
        }).catch((e) => {
            Logging.error("[HTTP] POST error", e.message);
            if (!errorHandled) {
                showToast(e.message || 'Network error', 'error');
                onError(e.message);
            }
        });
    }

    static remove(url, onSuccess, onError) {
        let token = window.localStorage['jwtToken'];
        let header = new Headers();
        if(token) {
            header.append('x-access-token', `${token}`);
        }

        let errorHandled = false;
        fetch(url, {
            method: 'DELETE',
            headers: header
        }).then((resp) => {
            if(resp.ok) {
                return resp.json();
            }
            else if(this.checkIfUnauthorized(resp)) {
                window.location = "/login.html";
                return;
            }
            else {
                errorHandled = true;
                return resp.json().then((json) => {
                    onError(json);
                });
            }
        }).then((resp) => {
            if (resp === undefined) return;
            if (HTTP._checkBodyForError(resp)) {
                onError(resp);
            } else {
                onSuccess(resp);
            }
        }).catch((e) => {
            if (!errorHandled) {
                showToast(e.message || 'Network error', 'error');
                onError(e.message);
            }
        });
    }

    static checkIfUnauthorized(res) {
        if(res.status == 401) {
            // Clear the expired/invalid token to prevent redirect loops
            // (login.html would otherwise see the stale token and bounce back)
            window.localStorage.removeItem('jwtToken');
            return true;
        }
        return false;
    }
    
    static checkValidCode(res) {
        if (res.status==200){
            Logging.dev("[HTTP] OK")
            return true
        }
        else if (res.status==201){
            Logging.dev("[HTTP] CREATED")
            return true
        }
        else if (res.status==203){
            Logging.dev("[HTTP] ACCEPTED")
            return true
        }
        else if (res.status >= 200 && res.status < 300) {
            return true;
        }
        return false;
    }
    
    static checkRessource(res){
        switch (res.status) {
            case 404:
                Logging.warn("[HTTP] Resource not found");
                return false
            case 301:
                Logging.warn("[HTTP] Moved permanently");
                return false
            case 308:
                Logging.warn("[HTTP] Permanent redirect");
                return false
            case 400:
                Logging.error("[HTTP] Bad Request");
                return false
            case 500:
                Logging.error("[HTTP] Internal Server Error");
                return false
        }
        return true
    }

    /**
     * Stream an SSE response from a POST endpoint.
     *
     * Sends a POST request and reads the response body as a stream of
     * Server-Sent Events (SSE). Each SSE frame is parsed and dispatched
     * to the appropriate callback based on the event type:
     *   - "chunk" (default) → onChunk(parsed)
     *   - "done"            → onDone(parsed)
     *   - "error"           → onError(parsed)
     *
     * @param {string} url - The endpoint URL
     * @param {Object} data - The POST body (JSON-serialized)
     * @param {Function} onChunk - Called for each streamed chunk
     * @param {Function} onDone - Called when the stream completes
     * @param {Function} onError - Called on error (HTTP or stream)
     * @returns {{ cancel: Function }} - Call cancel() to abort the stream
     */
    static stream(url, data, onChunk, onDone, onError) {
        const token = window.localStorage?.getItem('jwtToken');
        const headers = { 'Content-Type': 'application/json' };
        if (token) headers['x-access-token'] = token;

        const controller = new AbortController();

        fetch(url, {
            method: 'POST', headers,
            body: JSON.stringify(data),
            signal: controller.signal,
        }).then(response => {
            if (!response.ok) return response.json().then(onError);
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            function pump() {
                reader.read().then(({ done, value }) => {
                    if (done) { onDone({}); return; }
                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop();
                    let eventType = 'chunk';
                    for (const line of lines) {
                        if (line.startsWith('event: ')) eventType = line.slice(7).trim();
                        else if (line.startsWith('data: ')) {
                            try {
                                const parsed = JSON.parse(line.slice(6));
                                if (eventType === 'error') onError(parsed);
                                else if (eventType === 'done') onDone(parsed);
                                else onChunk(parsed);
                            } catch (e) { /* partial JSON, wait for more data */ }
                        }
                    }
                    pump();
                }).catch(e => {
                    if (e.name !== 'AbortError') onError(e);
                });
            }
            pump();
        }).catch(e => {
            if (e.name !== 'AbortError') onError(e);
        });

        return { cancel: () => controller.abort() };
    }
}

window.Http = HTTP