import HTTP from "./HTTP.js";

class MyObject {
  constructor() {
    this.data = {}
  }
  set(name, value){
    this.data[name] = value
  }
  get(name){
    return this.data[name]
  }
}

MyObject.get()
let obj = MyObject()
obj.get()


let API_URL = "http://localhost:8000/api/"
let COMPONENT_URL = "http://localhost:3000/"

export default class Handler {
    static data = {}
    static store = {}
    static factory = {}
    static prototypes = {}
    
    constructor() {
    }
    
    
    /**
     * This function calls a backend (url) to discover the topology (prototypes) of the given service
     * @param name
     */
    static discover(url){
        HTTP.get(
            url,
            (data) => {
                // The data is returned as a json pydantic schema of the Server objects
                // for each item in the $defs object, create a local prototype and register it in the Handler.prototypes
                // object
                for (const [key, value] of Object.entries(data.$defs)) {
                    let prototype = value
                }
                
                Handler.prototypes = data;
                console.log(data)
            },
            (error)=>{
                console.log(error)
            }
        )
    }
    
    static set(uuid, value){
        Handler.data[uuid] = value
        Handler.factory[uuid].onSuccess(value)
        
    }
    static register(uuid, model, onSuccess, onError, url=API_URL){
        Handler.factory[uuid] = {
            url: url,
            data: undefined,
            model:model,
            onSuccess:onSuccess,
            onError:onError}
        
    }
    
    static create(uuid, data){
        HTTP.post(
            Handler.factory[uuid].url,
            data,
            (data) => {
                // Updata data store
                idx == -1 ? Handler.data[uuid] = data : Handler.data[uuid][idx] = data
                // Save last modification and forward to onSuccess
                Handler.factory[uuid].data = data;
                Handler.factory[uuid].onSuccess(data);
            },
            (error)=>{
                console.log(error)
            }
        )
    }
    
    static update(uuid, data, idx=-1){
        HTTP.put(
            Handler.factory[uuid].url,
            data,
            (data) => {
                // Updata data store
                idx == -1 ? Handler.data[uuid] = data : Handler.data[uuid][idx] = data
                // Save last modification and forward to onSuccess
                Handler.factory[uuid].data = data;
                Handler.factory[uuid].onSuccess(data);
            },
            (error)=>{
                console.log(error)
            }
        )
    }
    
    static pull(name){
        HTTP.get(
            Handler.factory[name].url,
            (data) => {
                Handler.factory[name].data = data;
                Handler.factory[name].onSuccess(data);
            },
            (error)=>{
                console.log(error)
            }
        )
    }
    
    access(uuid){
        return Handler.data[uuid]
    }
}


window.Storage = new Handler()
