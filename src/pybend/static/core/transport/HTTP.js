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
        // Explicit "error" field (backend convention)
        if (json.error)  return String(json.error);
        if (json.detail) return String(json.detail);
        if (json.message && status && status >= 400) return String(json.message);
        return null;
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
                showToast(`Resource not found: ${url}`, 'error');
                errorHandled = true;
                onError(resp);
                return;
            }
            else {
                errorHandled = true;
                return resp.json().then((json) => {
                    HTTP._toastHttpError(resp.status, json);
                    onError(json);
                });
            }
        }).then((resp) => {
            if (resp === undefined) return;
            if(resp.hasOwnProperty('token')) {
                window.localStorage['jwtToken'] = resp.token;
            }
            HTTP._checkBodyForError(resp);
            onSuccess(resp);

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
                    HTTP._toastHttpError(resp.status, json);
                    onError(json);
                });
            }
        }).then((resp) => {
            if (resp === undefined) return;
            if(resp.hasOwnProperty('token')) {
                window.localStorage['jwtToken'] = resp.token;
            }
            HTTP._checkBodyForError(resp);
            onSuccess(resp);
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
                    HTTP._toastHttpError(resp.status, json);
                    onError(json);
                });
            }
        }).then((resp) => {
            if (resp === undefined) return;
            if(resp.hasOwnProperty('token')) {
                window.localStorage['jwtToken'] = resp.token;
            }
            HTTP._checkBodyForError(resp);
            onSuccess(resp);
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
                    HTTP._toastHttpError(resp.status, json);
                    onError(json);
                });
            }
        }).then((resp) => {
            if (resp === undefined) return;
            HTTP._checkBodyForError(resp);
            onSuccess(resp);
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
}

window.Http = HTTP