import '../components/ntt-item.js';
import {PTT} from './NTT.js';
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
    console.log(this)
    // Register component reference in parent class
  }
  
  static get observedAttributes() {
    return ['addr', 'hash'];
  }
  
  static get addr() {
    return Component.name;
  }
  
 
  /**
  connect(target) {
    let connectEvent = new ConnectEvent(this.addr, target);
    Component.send(connectEvent.repr());
  }
  
  static register(component) {
    if (!this.#children.has(component.addr)) {
      this.#children.set(component.addr, component);
      Logging.debug(`[COMPONENT] Registered component at address:`, component.addr);
    } else {
      Logging.warn(`[COMPONENT] Component at address ${component.addr} is already registered.`);
    }
  }
   */
  
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
 
  inbox(event) {
      // Parse event into TX if necessary
      let tx = typeof event !== 'TX' ? new TX(event) : event;
      // Handle if tx target matches this component's address
      if (tx.target === this.addr || tx.target === `/${this.addr})`) {
        console.warn(`Event ${tx.name} received in Element:`, tx);
        // Call internal event handler
        let event_method = `$${tx.name}`;
        if (this.hasAttribute(tx.name) && typeof this[event_method] === 'function') {
          this[event_method](tx.data);
        } else {
          console.warn(`No handler for event ${tx.name} in Component ${this.addr} ${this.prototype.name}.`);
        }
      } else {
        // Forward the event up to the Component static send method
        this.send(event);
      }
  }
  
  send(event) {
    return Component.send(event);
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

