/**
 * ListElement — Collection base class.
 *
 * Handles the data lifecycle for a collection of entities:
 *   - On define: subscribes to the DynamicClass and triggers a READ
 *   - Receives address arrays via UPDATE handler
 *   - Manages selection and pagination state
 *   - Provides child-stamping helpers for concrete renderers
 *
 * Override render()/update() to build a concrete collection UI.
 * The built-in NTTList (ntx-list.js) provides the default grid list renderer.
 */
import {Component} from '../core/Component.js';
import TX from '../core/TX.js';
import Logging from '../utils/Logging.js';


export class ListElement extends Component {

  // Size cascade: parent display mode → child display mode
  static SIZE_CASCADE = {
    xl: 'md',
    lg: 'sm',
    md: 'sm',
    sm: 'xs',
    xs: 'xs',
    row: 'row',
  };

  #selected = new Set();
  #pageSize = 20;
  #offset = 0;

  constructor() {
    super([]);  // Default value: array
  }


  /** ─────────────────────────────────────────── **/
  /**         Selection API                        **/
  /** ─────────────────────────────────────────── **/

  get selected()    { return this.#selected; }
  select(addr)      { this.#selected.add(addr); }
  deselect(addr)    { this.#selected.delete(addr); }
  toggle(addr)      { this.#selected.has(addr) ? this.deselect(addr) : this.select(addr); }
  clearSelection()  { this.#selected.clear(); }

  /**
   * Called when the DynamicClass prototype arrives.
   * Subscribes to the proto's UPDATE observable and triggers the initial READ.
   */
  definedCallback() {
    this.subscribe(this.proto, 'UPDATE', (data) => this.UPDATE(data));
    if (this.value.length > 0) {
      this.scheduleRender();  // Data arrived before schema — render now
      return;
    }
    // Dedup: if another list already triggered a READ for this model, skip.
    // All list watchers will be notified when that READ completes.
    if (this.proto._listReadPending || this.proto.instances?.size > 0) return;
    this.proto._listReadPending = true;
    this.#offset = 0;
    const popDepth = this.proto._schema?.ui?.populate?.depth ?? 1;
    const popParams = popDepth > 0 ? {depth: popDepth} : {};
    this.proto.call('READ', { limit: this.#pageSize, offset: 0, ...popParams }, {inbox: 'UPDATE'});
  }

  /**
   * Load next page of results and append to the current list.
   */
  loadMore() {
    this.#offset += this.#pageSize;
    const popDepth = this.proto._schema?.ui?.populate?.depth ?? 1;
    const popParams = popDepth > 0 ? {depth: popDepth} : {};
    this.proto.call('READ', { limit: this.#pageSize, offset: this.#offset, ...popParams }, {inbox: 'UPDATE'});
  }

  /** ─────────────────────────────────────────── **/
  /**         Message Handlers                     **/
  /** ─────────────────────────────────────────── **/

  /**
   * Receives an array of entity addresses from the DynamicClass watcher.
   */
  UPDATE(data) {
    Logging.dev(`[ListElement] ${this.schema.__name__} — UPDATE`, data);
    if (Array.isArray(data)) {
      const prev = this.value;
      this.value = data;
      if (!this.update(prev, data)) this.scheduleRender();
    } else {
      Logging.warn('[ListElement] UPDATE expected array, got', typeof data);
    }
  }

  /**
   * Receives a SELECT TX from a child item.
   * Toggles selection state and forwards as NAVIGATE if router is configured.
   */
  SELECT(data, tx) {
    this.toggle(data);
    const routerAddr = this.getAttribute('router');
    if (routerAddr) {
      this.send(new TX({ name: 'NAVIGATE', source: this.addr, target: routerAddr, data: data }));
    }
  }


  /** ─────────────────────────────────────────── **/
  /**         Collection Helpers                   **/
  /** ─────────────────────────────────────────── **/

  /**
   * Append items to the collection.
   */
  append(data) {
    if (Array.isArray(data)) {
      this.value = [...this.value, ...data];
    } else {
      Logging.warn('[ListElement] append() expects an array');
    }
  }


  /** ─────────────────────────────────────────── **/
  /**         Child Element Resolution             **/
  /** ─────────────────────────────────────────── **/

  /**
   * The tag name to stamp per item. Override in subclass or use item-tag attribute.
   * Resolution: item-tag attribute > subclass override > schema hint > 'ntx-item'
   */
  get childTag() {
    return this.getAttribute('item-tag')
      || this.schema?.ui?.renderer?.item
      || 'ntx-item';
  }

  /**
   * Resolved display mode for child items.
   * Priority: item-display attribute > auto cascade from parent's displayMode.
   */
  get childDisplay() {
    const explicit = this.getAttribute('item-display');
    if (explicit) return Component.normalizeDisplay(explicit) || explicit;
    return ListElement.SIZE_CASCADE[this.displayMode] || 'xs';
  }

  /**
   * Creates a child element for a given address.
   * Checks for a <template item-template> in light DOM first.
   * Stamps the resolved childDisplay on each child.
   */
  createChild(addr) {
    // Priority 1: <template item-template> in light DOM
    const template = this.querySelector('template[item-template]');
    if (template) {
      const el = template.content.firstElementChild.cloneNode(true);
      el.setAttribute('ref', addr);
      el.setAttribute('select-target', this.addr);
      return el;
    }
    // Priority 2: childTag resolution chain
    const el = document.createElement(this.childTag);
    el.ref = addr;
    el.setAttribute('display', this.childDisplay);
    el.setAttribute('select-target', this.addr);
    return el;
  }


  /** ─────────────────────────────────────────── **/
  /**         Surgical DOM Update                  **/
  /** ─────────────────────────────────────────── **/

  update(prev, next) {
    return false;
  }
}
