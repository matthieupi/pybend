import './ntt-item.js';
import {PTT} from '../core/NTT.js';
import {isEmpty, generateId} from "../core/Utils.js";
import Logging from "../utils/Logging.js";
import {matrix} from "../core/Matrix.js";
import {Component} from "../core/Component.js";



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
    return ['model', 'addr', 'hash'];
  }
 
  
  attributeChangedCallback(name, oldVal, newVal) {
    console.log("ATTR CHANGED:      ", `${this.constructor.name}.${name} ${oldVal} => ${newVal}`)
    if (oldVal === newVal) return; // No change, no need to update
    
    if (name === 'model') {
      this.model = newVal;
      // Detach and reattach to the new model
      this.#detach?.();
      this.#detach = PTT.attach(newVal, this.define);
    } else {
      this[name] = newVal;
    }
  }
  
  disconnectedCallback() {
    this.#detach?.();
    this.#unsubscribe?.();
  }
  
  get schema() { return this.#proto?.schema || {}; }
  
  get proto() { return this.#proto; }
  
  get value() { return this.#data || this.#defaultValue; }
  set value(data) {
    if (typeof data !== typeof this.#defaultValue) {
        Logging.dev(`Data type mismatch: Expected ${typeof this.#defaultValue}, got ${typeof data} in ${this.constructor.name}.`);
        return;
    }
    if (data !== this.value){
      this.#data = data;
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
    console.error(isEmpty(this.value), isEmpty(this.#data))
    if (!data) return
    this.value = data;
  }
  
  subscribe(tt, attribute, callback) {
    this.#unsubscribe?.();
    this.#unsubscribe = tt.observe(attribute, callback);
  }
  
  attach(addr) {
    this.#detach?.();
    this.#detach = PTT.attach(addr, this.define);
  }
  
  render() {
    throw new Error(`Not implemented error: Render method must be implemented in ${this.constructor.name} class.`);
  }
}

customElements.define('ntt-element', NTTElement);
