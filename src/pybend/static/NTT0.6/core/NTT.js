import assert from "../utils/Assert.js";
import {config} from "../config.js";
import {isEmpty, isTypeCompatible, isUrl, Utils} from './Utils.js';
//import {registry, registrar, getRegistrar} from "./registrar.js";
import TX from "./TX.js";
import {remote} from "./transport/NetworkAdapter.js";
import Logging from "../utils/Logging.js";
import Actor from "./Actor.js";

import {matrix} from "./Matrix.js";
import Observable from "./Observable.js";

const E = config.E;

/**
 * TT (Transfer Type) - Base class for transfer types
 */
class TT extends Actor{
    
    #href;
    #watchers = new Set();
    #observers = new Map();
    
    constructor(addr, href) {
        super(addr);
        assert(this, addr && typeof addr === 'string', `Address must be a non-empty string.`);
        //assert(this, href && typeof isUrl(href), `[TT] ${addr} - HREF must be a valid URL, got: ${href}`);
        
        if (!href)
            href = `${config.API_URL}/${addr}`;
        this.#href = href;
    }
    
    // Protected getters for subclasses
    get href() { return this.#href; }
    set href(href) {
        assert(this, isUrl(href), `[TT] ${this.addr} - HREF must be a valid URL, got: ${href}`);
        const oldHref = this.#href;
        this.#href = href
    }
    
    watch(addr, immediate = true) {
        this.#watchers.add(addr);
        if (this.value && immediate){
            this.send(new TX({
                name: E.update,
                source: this.addr,
                target: addr,
                data: this.value
            }))
        }
    }
    
    
    notify(value) {
        let data = []
        if (!value){
            data = [...this.value].map(child => child.addr);
        }
        else {
            data = Array.isArray(value) ? value : [value];
        }
        this.#watchers.forEach( (addr) => {
            this.send(
                new TX({
                    name: E.update,
                    source: this.addr,
                    target: addr,
                    data: data,
                })
            )
        });
    }
    
    ATTACH(data, tx) {
        console.log("ATTACHING")
        this.watch(tx.source)
    }
    
    
    
    
    /**
    notify(property, newValue, oldValue) {
        assert(this, property && typeof property === 'string', `Property must be a non-empty string.`);
        //assert(this, this.#observers.has(property), `No observers registered for property '${property}'.`);
        // Notify all observers for the specified property
        if (this.#observers.has(property)) {
            this.#observers.get(property).forEach(callback => callback(newValue, oldValue, property, this));
        }
    }
    
    signal(callback = undefined, wait = false) {
        assert(this, !callback || typeof callback === 'function', `Callback must be a function if given.`);
        if (callback) {
            if (!wait) {
                // When wait is false, immediately call the callback
                callback(this);
            }
            // Add the callback to the signals set
            this.#signals.add(callback);
            // Return an unsubscribe function
            return () => { this.#signals.delete(callback); };
        }
        else {
            // When called with no callback, signal to all listeners
            this.#signals.forEach((callback) => { callback(this); });
        }
        
    }
     **/
   
    /**
     * Send an event via the registrar callback
     * @param event {TX}
     */
    
    /**
    send(event) {
        assert(this, event && typeof event === 'object', `Data must be a non-empty object.`);
        // Retrieve href callback and dispatch the event to it
        Logging.event(`Sending event '${event.name}' from ${event.source} to ${event.target}\n`, event.str())
        matrix.dispatch(event)
    }
     **/
    
    /**
     * Inbox method to handle incoming events
     * @param event {TX}
     */
    /**
    inbox(event) {
        // Check if the event name matches a method in this class
        let method_name = `_${event.name}_`.toLowerCase();
        // Dispatch the event internally to the corresponding method
        if (typeof this[method_name] === 'function') {
            this[method_name](event.data);
        } else if (this.#observers.has(event.name)) {
            // If the event name is registered as an observer, notify observers
            this.#observers.get(event.name).forEach(callback => callback(event.data));
        } else {
            Logging.dev(`No handler ${method_name} for event '${event.name}' in PTT [${this.addr}] instance.`);
            Logging.debug(event)
        }
        
    }
     **/
    
    /**
    observe(property, callback) {
        assert(this, property && typeof property === 'string', `Property must be a non-empty string.`);
        assert(this, callback && typeof callback === 'function', `Callback must be a function.`);
        // Create a new Set for observers if it doesn't exist
        if (!this.#observers.has(property)) {
            this.#observers.set(property, new Set());
        }
        // Add subscriber to the property observers
        this.#observers.get(property).add(callback);
        // Return unsubscribe function
        return () => {
            this.#observers.get(property).delete(callback);
            if (this.#observers.get(property).size === 0) {
                this.#observers.delete(property);
            }
        };
    }
     **/
  
    /**
     * Call a distant method on the PTT instance
     * @param method {string} - Method name to call
     * @param data {Object} - Data (args and kwargs) to send with the method call
     * @param [meta] {Object} - Additional metadata for the call
     */
    call(method, data = {}, meta = {}) {
      this.send(
        new TX({
            name: method,
            source: this.addr,
            target: this.href,
            data: data,
            meta: meta,
            timestamp: Date.now()
        })
      )
    }
    
    _error_(event) {
        console.groupCollapsed(`[TT] Error received from ${event.source}:`, event.name);
        console.error(`[TT] Error received from ${event.source}->${event.target}`);
        console.warn(`[TT] Error data:`, event.data);
        console.warn(`[TT] Event meta:`, event.meta);
        console.groupEnd()
    }
}


/**
 * PTT (ProtoTransferType) - Protocol Transfer Type
 * Acts as a proxy for remote registered models
 */
export class PTT extends TT{
  
    static #prototypes = new Map();
    
    #instances;
    #data;
    #cls;
  
    constructor(addr, href, schema = undefined) {
        Logging.debug(`[PTT] Creating PTT instance for ${addr}`, schema ? 'WITH SCHEMA' : 'WITHOUT SCHEMA');
        assert(PTT, !PTT.#prototypes.has(addr), `Address '${addr}' is already registered.`);
        super(addr, href);
        // Save the Prototype instance to the PTT local registry
        PTT.#prototypes.set(addr, this);
        this.#instances = new Map();
        // Register the inbox method to handle incoming events
        //matrix.register(this)
    }
    
    get schema() { return this.#data; }
    get value() {
        let data = this.#data;
        data["@context"] = this.href;
        data["@type"] = this.addr
        return this.#data; }
    set value(val) {
        this.#data = val;
        this.#cls = prototype(this);
        this.signal()
    }
    
    pull() {
        assert(this, isUrl(this.href), `[PTT] ${this.addr} HREF must be a valid HTTP URL, got: ${this.href}`);
        this.call('SCHEMA', {}, {remote: true});
        return this;
    }
    
    SCHEMA(data) {
        // If the data has a __tablename__, we need to link this prototype to the endpoint
        if (data['__tablename__']) {
            this.href = `${config.API_URL}/${data['__tablename__']}`;
            //registrar(this.href, remote.send)
        }
        // Create a subclass of NTT with the provided schema
        this.value = data;
        // If the schema has a $defs, register them as PTTs
        if (data.$defs && typeof data.$defs === 'object') {
            for (const [key, value] of Object.entries(data.$defs)) {
                if (value.type === 'object' && value.properties) {
                    // Register the prototype with the address
                    if (!PTT.has(key)) {
                        PTT.factory(key, `${value['__url__']}`, value);
                    } else {
                        Logging.dev(`[PTT.schema] Prototype for ${key} is already registered.`);
                    }
                }
            }
        }
    }
    
    UPDATE(data) {
        matrix.dispatch(new TX({
            name: E.update,
            source: `${this.addr}/${this.href}`,
            target: this.addr,
            data: data,
        }));
    }
    
    READ(data) {
        assert(this, data && typeof data === 'object', `Data must be a non-empty object.`);
        if (Array.isArray(data)){
                // Update all instances with the received data
                for (const value of data) {
                    const addr = value.id;
                    if (this.#instances.has(addr)) {
                        this.#instances.get(addr).update(value);
                    } else {
                        const instance = new this.#cls(value);
                        this.#instances.set(addr, instance);
                    }
                }
            }
        else if (typeof data === 'object') {
            // Update all instances with the received data
            for (const [addr, value] of Object.entries(data)) {
                if (this.#instances.has(addr)) {
                    this.#instances.get(addr).update(value);
                } else {
                    const instance = new this.#cls(value);
                    this.#instances.set(addr, instance);
                }
            }
        }
        // Make list of instances addresses
        const instanceAddrs = new Set(this.#instances.keys());
        // Add Product/ prefix to addresses
        const childrenAddrs = [...instanceAddrs].map( addr => addr.toString().startsWith(`${this.addr}/`) ? addr : `${this.addr}/${addr}`);
        console.warn("CHILDREN ADDR", childrenAddrs )
        this.notify(childrenAddrs)
        
        
        
        
    }
   
    // ------------------ Static Methods ------------------ //
    
    static has(addr) {
        assert(this, addr && typeof addr === 'string', `Address must be a non-empty string.`);
        return this.#prototypes.has(addr);
    }
    
    static get(addr) {
        assert(this, addr && typeof addr === 'string', `Address must be a non-empty string.`);
        if (!PTT.#prototypes.has(addr)) {
            return new PTT(addr, `${config.API_URL}/${addr}`).pull();
        }
        return PTT.#prototypes.get(addr);
    }
    
    has(addr) {
        assert(this, addr && typeof addr === 'string', `Address must be a non-empty string.`);
        return this.#instances.has(addr);
    }
    
    get(addr) {
        assert(this, addr && typeof addr === 'string', `Address must be a non-empty string.`);
        return this.#instances.get(addr) || undefined;
    }
   
    static ATTACH(data, tx) {
        tx = tx instanceof TX ? tx : new TX(tx);
        // Handle attach event
        const addr = tx.data
        if (PTT.#prototypes.has(addr)) {
            return PTT.#prototypes.get(addr).inbox(tx.repr());
        } else {
            console.warn(`[PTT] No prototype registered for address '${addr}' to attach.`);
            return PTT.get(addr).signal( (ptt) => {
                    console.error(ptt);
                    ptt.watch(tx.source)
                console.warn(`[PTT] Watch to prototype '${ptt.addr}' from source '${tx.source}'.`)
                console.log(ptt)
                console.log(ptt.watch)
                ptt.call('READ', {})
                },
                true);
        }
    }
    
    static attach(addr, callback) {
        assert(this, addr && typeof addr === 'string', `Address must be a non-empty string.`);
        assert(this, callback && typeof callback === 'function', `Callback must be a function.`);
        let unsubscribe;
        // If the address is not registered, get the PTT instance from the backend
        if (!PTT.#prototypes.has(addr)) {
            unsubscribe = PTT.get(addr).signal(callback, true);
        } else {
            unsubscribe = PTT.#prototypes.get(addr).signal(callback);
        }
        // Return unregister
        return unsubscribe;
    }
    
    /**
     * Creates a PTT instance and registers it in the global registry.
     * Used for pre-registring models for faster access later.
     * @param addr {string} - Unique local address for the model, usually in the form of `model/instance_id`
     * @param href {string} - URL for the model, usually in the form of `http://api.example.com/model`
     * @param schema {Object|string} - Schema or URL for the model
     * @returns {PTT}
     */
    static factory(addr, href, schema = undefined) {
        assert(this, !PTT.#prototypes.has(addr), `Address '${addr}' is already registered.`, 'warn');
        if (!schema) return new PTT(addr, href).pull();
        else return new PTT(addr, href, schema);
    }
    
    /**
    register(instance) {
        Logging.warn(`[${this.addr}] Registering in PTT`,`${instance.addr}`)
        this.#instances.set(instance.addr, instance);
    }
     */
    
}

/**
 * NTT (Named Transfer Type) - Core entity class
 * Represents virtual backend entities with functional state management.
 * This class is designed to be extended for specific entity types, and is not intended to be instantiated directly.
 */
export class NTT extends TT {
    
    static #instances = new Map();
    #proto;
    #data; // Will be redefined in subclass
    #detach;
    #unsubscribe;
    #meta = {};
    
    /**
     * Create a new NTT instance
     * @param {string} name - Entity name
     * @param {string} addr - Backend address/endpoint
     * @param {string} [href] - View URL (defaults to addr)
     * @param {Object} [data={}] - Initial data/state
     * @param {Object|string} [schema={}] - Schema or URL
     * @param {Object} [meta={}] - Additional metadata
     * @param {string} [id] - Custom ID (auto-generated if not provided)
     */
    constructor(model, hash, data = {}, meta = {}) {
        const id = hash || Utils.generateId();
        const href = `${config.API_URL}/${model}/${id}`;
        const addr = `${id}`;
        super(addr, href);
        // Attach to the type definition
        //NTT.#instances.set(addr, this);
        //this.#detach = PTT.attach(model, this.define.bind(this));
        //if (!isEmpty(data)) {
        //    this.value = data; // Initialize value with provided data
        //}
        //// Register the upstream and downstream links
        //this.proto.register(this)
        //// Initialize functional state management in meta. Functionality is not implemented yet but will be added later
        //this.#meta = {
        //    // ...meta,
        //    // remoteState: { ...data },          // Last known server state
        //    // pendingOps: [],                    // Uncommitted transformations
        //};
    }
    
    static UPDATE(data) {
        // TODO update to use addr (right now index) when the backend is updated to return dict of addr: value instead of list
        for (const [addr, value] of Object.entries(data)) {
            const instance = this.get(value.id);
            if (instance) {
                instance.update(value);
            } else {
                new this(value)
            }
            
        }
    }
    
    ATTACH(data, event) {
        const tx = event instanceof TX ? event : new TX(event);
        this.watch(tx.source, false);
        this.send(new TX({
            name: 'DESCRIBE',
            source: this.addr,
            target: tx.source,
            data: this.proto ? {proto: this.proto.schema(), data: this.value} : {proto: this.constructor._schema, data: this.value}
        }))
    }
    
    get value() {
        return this.#data
    }
    
    set value(val) {
        if (typeof val !== 'object') {
            throw new TypeError('data must be an object');
        }
        this.#data = val;
        if (this.#proto) {
        } else {
            this.signal()
        }
    }
    
    get proto() {
        return this.#proto;
    }
    
    get schema() {
        return this.#proto?.schema
    }
    
    define(proto) {
        this.#proto = proto;
        this.href = `${proto.href}/${this.hash}`;
    }
    
    describe(proto, data) {
        if (!proto || typeof proto !== 'object') return
        this.define(proto)
        this.update(data || this.#data || {});
    }
    
    static READ(data) {
        assert(this, data && typeof data === 'object', `Data must be a non-empty object.`);
        // Update the NTT instance with the received data
        this.update(data);
    }
    
    UPDATE(data, event) {
        this.update(data);
        if (!event.source?.startsWith('http')) {
            this.call('UPDATE', this.value);
        }
    }

    update(data) {
        this.value = {...this.#data, ...data};
        if (data.hasOwnProperty('name') && data.name === "error") {
            console.warn(`[NTT] Error received from ${this.addr}:`, data.message || data.error || "Unknown error")
        }
    }
    
    ERROR(event) {
        console.error(`[NTT] ${event.name} from ${event.source}:`, event.data);
    }
    
    _read_(data) {
        assert(this, data && typeof data === 'object', `Data must be a non-empty object.`);
        // Update the NTT instance with the received data
        this.update(data);
    }
    
    /**
     * Serialize NTT instance to JSON
     * @returns {Object} JSON representation
     */
    toJSON() {
        return {
            addr: this.addr,
            href: this.href,
            data: this.#data,
            meta: {
                ...structuredClone(this.#meta),
                // Exclude non-serializable items
                subscribers: undefined,
                propertyObservers: undefined,
                conflictResolver: undefined
            }
        };
    }
   
    pull() {
        assert(this, isUrl(this.href), `[NTT] ${this.addr} HREF must be a valid HTTP URL, got: ${this.href}`);
        this.call('READ', {}, {remote: true});
        return this;
    }
    
    // ------------------ Static Methods  ------------------ //
    
    /**
     * Get NTT instance by address
     * @param {string} addr - Instance identifier
     * @returns {NTT|null} NTT instance or null if not found
     */
    static get(addr) {
        assert(this, addr && typeof addr === 'string' || addr && typeof addr === 'number',
            `Address must be a non-empty string.`);
        if (typeof addr === 'number'){
            // Conver to string
            addr = addr.toString();
        }
        if (!this.children.has(addr)) {
            return undefined
        }
        return this.children.get(addr);
    }
    
    static attach(model, hash, callback) {
        // Compute local address and href
        const addr = `${model}/${hash || Utils.generateId()}`;
        const href = `${config.API_URL}/${addr}`;
        let unsubscribe;
        // If the address is not registered, get the NTT instance from the backend
        if (!NTT.#instances.has(addr)) {
            const wait = !!NTT.#instances.get(addr)?.schema;
            console.error("[WAIT] ", addr, wait)
            unsubscribe = NTT.get(addr).signal(callback, true);
        } else {
            unsubscribe = NTT.#instances.get(addr).signal(callback);
        }
        return unsubscribe;
    }
    
    /**
     */
    static create(model, data, callback = null) {
        
        const evt = new NTT.Event(
            'create',
            Utils.generateId(),
            model,
            `${config.API_URL}/${model}`,
            data,
            callback
        );
        
        evt.dispatch();
    }
    
}

// Global exposure for backward compatibility
//

/**
 *
 * @param addr
 * @param schema
 * @returns {class}
 */
function prototype(ptt) {

    console.error(`Creating PTT prototype class for ${ptt.addr}:`)
    const fields = Object.keys(ptt.schema.properties || {});
    const methods = Object.keys(ptt.schema.methods || {});
    const className = ptt.addr
    const schema = ptt.schema;
    

    // 1. Create a subclass of NTT with dynamic properties
    const DynamicClass = class extends NTT {
      
      static instances = new Map();
      static _schema = schema
      
      _data;
      
      
      constructor(data) {
      Logging.init(`Dynamic ${DynamicClass.name} ${data.id}`, data)
        super(DynamicClass.name, data.id);
        this.value = data;
        this.href = `${ptt.href}/${this.id}`; // Set the href based on the PTT instance
          console.warn(`Created instance of ${DynamicClass.name} with addr ${this.addr}`)
      }
      
      get value() {
          if (!this._data) {
              return undefined
          }
          let data = this._data;
          data["@context"] = this.href;
          data["@type"] = this.constructor.addr
          return this._data;
      }
      set value(val) {
            if (typeof val !== 'object') {
                throw new TypeError('data must be an object');
            }
            this._data = val;
            this.signal();
      }
    };
    
    // 1.1 Set the class name dynamically
    Object.defineProperty(DynamicClass, 'name', {value: className});
    Object.defineProperty(DynamicClass, 'proto', {value: ptt});
    

    // 2. Add schema properties to the subclass prototype
    for (const field of fields) {
      const definition = schema.properties[field];
      const isReadonly = definition.readOnly === true;
      const label = definition.title || field;
      const hidden = definition.extra && definition.extra.hidden;

      Object.defineProperty(DynamicClass.prototype, field, {
        enumerable: !hidden,
        configurable: true,
        // 2.1 Variable access
        get() {
          return this.value?.[field]
        },
        // 2.2 Variable assignment with type checking and validation
        set(value) {
          if (isReadonly) {
            throw new Error(`Trying to set read-only '${field}' with data ${JSON.stringify(value)}.`);
          }
          const expectedType = definition.type;
          if (expectedType && !isTypeCompatible(value, expectedType)) {
            throw new TypeError(`Invalid type for '${field}': expected ${expectedType}`);
          }
          // Cache the old value for observers
          const oldValue = this.value[field];
          // Assign the value to the field
          this.value[field] = value;
          // If this field has property observers, notify them
          this.notify(field, value, oldValue);
        },
      });

      // 2.3 Add fields labels for UI representation
      if (!DynamicClass.labels) DynamicClass.labels = {};
      DynamicClass.labels[field] = label;
    }
    
 
    // 3. Add schema functions to the subclass prototype
    for (const method of methods) {
      const definition = schema.methods[method];
      // Add the method to the prototype
      DynamicClass.prototype[method] = function(...args) {
          // Validate the arguments against the method definition
        if (definition.parameters) {
            for (const [param, paramDef] of Object.entries(definition.parameters)) {
                // Check if the parameter is a required field
                if (paramDef.required && !args[param]) {
                    throw new TypeError(`Missing required parameter '${param}' in method '${method}'.`);
                }
                // Check if the type is a reference to another schema
                if (paramDef.$ref) {
                    // If the parameter is a reference, ensure it matches the schema
                    const refSchemaName = schema.$defs[paramDef.$ref.replace('#/$defs/', '')];
                    // Validate the argument against the referenced schema
                    if (args[param] && args[param]?.addr !== refSchemaName) {
                        throw new TypeError(`Parameter '${param}' in method '${method}' must match schema '${refSchemaName}'. ` +
                            `Got: ${JSON.stringify(args[param])}`);
                    }
                } else if (!isTypeCompatible(args[param], paramDef.type)) {
                    throw new TypeError(`Invalid type for parameter '${param}' in method '${method}': expected ${paramDef.type}`);
                }
            }
        }
        // Call the remote method with the provided arguments
        this.call(method, args, {});
      };
    }
    

    // 3. Add schema static methods to the subclass prototype
    // ToDo: When backend is ready, implement remote method calling (RPC) from the constructor
    
    
    // Apply Actor and Mixins
    Actor.subclass(DynamicClass, Observable);

    return DynamicClass;
}


window.NTT = NTT;

Actor.subclass(TT);

Actor.subclass(PTT, Observable);

Actor.subclass(NTT)
