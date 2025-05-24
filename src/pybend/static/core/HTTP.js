export default class HTTP {
    
    constructor() {
        console.log("HTTPPPPPP")
    }
    
    static baseURL(action) {
        return "/api/";
    }
    
    static rpc(method_name, args={}, kwargs={}, onSuccess=()=>{}) {
        let data= JSON.stringify({method_name: method_name, args:args, kwargs:kwargs})
        HTTP.post('rpc', data, onSuccess, ()=>{alert("FAIL")})
        
    }
    

    static get(url, onSuccess, onError) {
        console.log("GET: "+ url)
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
                console.log(resp)
                console.log(resp.body)
                return resp.json();
            }
            else if(this.checkIfUnauthorized(resp)) {
                window.location = "/#login";
            }
            else {
                resp.json().then((json) => {
                    onError(json.error);
                });
            }
        }).then((resp) => {
            let response = resp; console.log(resp)
            if(response && response.hasOwnProperty('token')) {
                window.localStorage['jwtToken'] = response.token;
            }
            console.log(url, onSuccess)
            onSuccess(response);

        })/*.catch((e) => {
            console.log(e)
            console.log(e.lineNumber)
            console.log(e.filename)
            onError(e.message);
        });

        */
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
        console.log("PUT: "+ url)
        console.log(JSON.parse(data))

        fetch(url, {
            method: 'PUT',
            headers: header,
            body: JSON.stringify(data)
        }).then((resp) => {
            if(resp.ok) {
                return resp.json();
            }
            else if(this.checkIfUnauthorized(resp)) {
                window.location = "/#login";
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
            console.log(e)
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
        console.log("POST: "+ url, JSON.parse(data))

        fetch(url, {
            method: 'POST',
            headers: header,
            body: JSON.stringify(data)
        }).then((resp) => {
            if(resp.ok) {
                return resp.json();
            }
            else if(this.checkIfUnauthorized(resp)) {
                window.location = "/#login";
            }
            else {
                resp.json().then((json) => {
                    onError(json.error + resp.toString());
                });
            }
        }).then((resp) => {
            if(resp.hasOwnProperty('token')) {
                window.localStorage['jwtToken'] = resp.token;
            }
            onSuccess(resp);
        }).catch((e) => {
            console.log(e)
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
                window.location = "/#login";
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
            return true;
        }
        return false;
    }
    
    static checkValidCode(res) {
        if (res.status==200){
            console.log("OK")
            return true
        }
        else if (res.status==201){
            console.log("CREATED")
            return true
        }
        else if (res.status==203){
            console.log("ACCEPTED")
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
                console.log("Ressource not found");
                return false
            case 301:
                console.log("Moved permanently");
                return false
            case 308:
                console.log("Permanent redirect");
                return false
            case 400:
                console.log("Bad Request");
                return false
            case 500:
                console.log("Internal Server Error");
                return false
        }
        return true
    }
}

window.Http = HTTP