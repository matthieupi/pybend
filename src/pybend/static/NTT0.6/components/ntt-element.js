import './ntt-item.js';
import {NTT} from '../core/NTT.js';
import {isEmpty, generateId} from "../core/Utils.js";
import Logging from "../utils/Logging.js";
import {matrix} from "../core/Matrix.js";
import {Component} from "../core/Component.js";
import TX from "../core/TX.js";



export class NTTElement extends Component {
  
  #href;
  #model;
  #proto = {};
  #data;
  #defaultValue = {};
  #unsubscribe = undefined;
  #detach = undefined;
  
  constructor(defaultValue={}) {
    super();
    this.attachShadow({mode: 'open'});
    this.#model = this.getAttribute('model') || undefined;
    this.#href = this.getAttribute('href') || undefined;
    this.#data = defaultValue;
    this.#defaultValue = defaultValue;
    
    this.describe = this.describe.bind(this);
    this.define = this.define.bind(this);
    //matrix.register(this);
  }
  
  static get observedAttributes() {
    return ['model', 'addr', 'hash', 'ref'];
  }
  
  get ref() { return this.#href; }
  set ref(href) {
    this.#href = href;
    this.send(new TX({
        name: 'ATTACH',
        source: this.addr,
        target: 'NTT',
        data: href,
        }))
  }
 
  
  attributeChangedCallback(name, oldVal, newVal) {
    console.log("ATTR CHANGED:      ", `${this.constructor.name}.${name} ${oldVal} => ${newVal}`)
    if (oldVal === newVal) return; // No change, no need to update
    
    if (name === 'model') {
      this.send(new TX({
        name: 'ATTACH',
        source: this.addr,
        target: 'NTT',
        data: newVal
      }))
      /*
      this.model = newVal;
      // Detach and reattach to the new model
      this.#detach?.();
      this.#detach = NTT.attach(newVal, this.define);
      */
    } else if (name === 'ref') {
      this.ref = newVal;
    }
    this[name] = newVal;
  }
  
  disconnectedCallback() {
    this.#detach?.();
    this.#unsubscribe?.();
  }
  
  get schema() {
    if (!this._schema)
      this._schema = this.#proto?.schema || {};
    return this._schema;
  }
  
  set schema(schema) {
    this._schema = schema;
  }
  
  get proto() { return this.#proto; }
  
  get value() { return this.#data || this.#defaultValue; }
  set value(data) {
    if (typeof data !== typeof this.#defaultValue) {
        Logging.dev(`Data type mismatch: Expected ${typeof this.#defaultValue}, got ${typeof data} in ${this.constructor.name}.`);
        return;
    }
    if (data !== this.value){
      this.#data = data;
      if (this._type)
        this.render();
    }
  }
  
  get model() { return this.#model; }
  set model(model_name) {
    this.#model = model_name;
  }
 
  define(ptt) {
    Logging.debug(`[NTT-ELEMENT] ${this.model} - Defining Element with `, ptt);
    if (!ptt.schema || ptt.schema.__name__ === this.#proto?.schema?.__name__) return;
    if (!this.model) {this.model = ptt.schema.__name__;}
    this.#proto = ptt;
    this.definedCallback();
  }
  
  describe(proto, data) {
    if (!proto.schema) return
    // Clean up previous subscription if it exists
    if (!this.#model) { this.#model = proto.schema.__name__ }
    this.#proto = proto;
    this.value = data || this.#defaultValue;
  }
  
  update(data) {
    if (!data) return
    this.value = data;
  }
  
  subscribe(tt, attribute, callback) {
    this.#unsubscribe?.();
    this.#unsubscribe = tt.observe(attribute, callback);
  }
  
  attach(addr) {
    this.#detach?.();
    this.#detach = NTT.attach(addr, this.define);
  }
  
  render() {
    throw new Error(`Not implemented error: Render method must be implemented in ${this.constructor.name} class.`);
  }
}

customElements.define('ntt-element', NTTElement);
