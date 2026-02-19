import '../components/ntt-item.js';
import {isEmpty, generateId} from "./Utils.js";
import Logging from "../utils/Logging.js";
import {matrix} from "./Matrix.js";
import Actor from "./Actor.js";
import TX, {ConnectEvent} from "./TX.js";



/**
 * Component base class for matrix UI.
 * Extends HTMLElement to create custom web components, and implements the Actor interface
 * for message handling within Matrix.
 */
export class Component extends HTMLElement {
  
  #addr;
  #hash;
  //static #children = new Map();
 
  constructor() {
    super();
    this.#hash = this.getAttribute('hash') || generateId();
    this.#addr = this.getAttribute('addr') || `${this.constructor.name}-${this.#hash}`;
    matrix.register(this);
    this.constructor.register(this);
    // Register component reference in parent class
  }
  
  static get observedAttributes() {
    return ['addr', 'hash'];
  }
  
  static get addr() {
    return Component.name;
  }
  
 
  /** -------------------------------------------- **/
  /**   ACTOR Instance Interface Implementation    **/
  /** -------------------------------------------- **/
  
  get addr() { return this.#addr; }
  set addr(addr) {
    if (!this.#addr)
      this.#addr = addr;
    else if (this.#addr === addr)
      return;
    else
      throw new Error(`[${this.#addr}] Address is already set to ${this.#addr} and cannot be changed to ${addr}.`);
  }
 
  /** -------------------------------------------- **/
  /**     Web Component Lifecycle Callbacks        **/
  /** -------------------------------------------- **/
  
  
  connectedCallback() {
  }
  
  disconnectedCallback() {
    console.error(`Component ${this.addr} disconnected to DOM.`)
  }
 
  render() {
    throw new Error(`Not implemented error: Render method must be implemented in ${this.constructor.name} class.`);
  }
}

Actor.subclass(Component);
matrix.register(Component)

// As it is solely a parent class do we really need to define it?
// customElements.define('', NTTElement);

