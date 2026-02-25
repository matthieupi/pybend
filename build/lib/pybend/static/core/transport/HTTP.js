import Logging from '../../utils/Logging.js';

export default class HTTP {
    
    constructor() {
    }
    
    static baseURL(action) {
        return "/api/";
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

        fetch(url, {
            method: 'GET',
            headers: header
        }).then((resp) => {
            if(resp.ok) {
                return resp.json();
            }
            else if(this.checkIfUnauthorized(resp)) {
                window.location = "/login.html";
            }
            else if (resp.status == 404) {
                Logging.warn("[HTTP] Resource not found", url);
                onError(resp);
                return new Promise((resolve, reject) => {
                    return {};
                })
            }
            else {
                resp.json().then((json) => {
                    onError(resp);
                });
            }
        }).then((resp) => {
            let response = resp;
            if(response && response.hasOwnProperty('token')) {
                window.localStorage['jwtToken'] = response.token;
            }
            onSuccess(response);

        }).catch((e) => {
            Logging.error("[HTTP] Error fetching " + url, e.message);
            onError(e.message);
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
            }
            else {
                resp.json().then((json) => {
                    onError(json.error);
                });
            }
        }).then((resp) => {
            if(resp.hasOwnProperty('token')) {
                window.localStorage['jwtToken'] = resp.token;
            }
            onSuccess(resp);
        }).catch((e) => {
            Logging.error("[HTTP] PUT error", e.message);
            onError(e.message);
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
            }
            else {
                resp.json().then((json) => {
                    onError(json.error + resp.toString());
                });
            }
        }).then((resp) => {
            if(resp?.hasOwnProperty('token')) {
                window.localStorage['jwtToken'] = resp.token;
            }
            onSuccess(resp);
        }).catch((e) => {
            Logging.error("[HTTP] POST error", e.message);
            onError(e.message);
        });
    }

    static remove(url, onSuccess, onError) {
        let token = window.localStorage['jwtToken'];
        let header = new Headers();
        if(token) {
            header.append('x-access-token', `${token}`);
        }

        fetch(url, {
            method: 'DELETE',
            headers: header
        }).then((resp) => {
            if(resp.ok) {
                return resp.json();
            }
            else if(this.checkIfUnauthorized(resp)) {
                window.location = "/login.html";
            }
            else {
                resp.json().then((json) => {
                    onError(json.error);
                });
            }
        }).then((resp) => {
            onSuccess(resp);
        }).catch((e) => {
            onError(e.message);
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