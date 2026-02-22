/**
 * ListElement — Collection base class.
 *
 * Handles the data lifecycle for a collection of entities:
 *   - On define: subscribes to the DynamicClass and triggers a READ
 *   - Receives address arrays via UPDATE handler
 *   - Renders by stamping one child element per address
 *
 * Override get childTag() to change which element is stamped per item.
 * Override render() for fully custom collection rendering.
 * The built-in NTTList (ntt-list.js) provides a zero-config default.
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
  };

  #selected = new Set();

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
    this.subscribe(this.proto, 'UPDATE', this.update.bind(this));
    this.proto.call('READ', {}, {inbox: 'UPDATE'});
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
      this.value = data;
      this.render();
    } else {
      console.warn('[ListElement] UPDATE expected array, got:', typeof data);
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
   * Internal update handler (bound and passed to subscribe).
   */
  update(data) {
    if (Array.isArray(data)) {
      this.value = data;
      this.render();
    }
  }

  /**
   * Append items to the collection.
   */
  append(data) {
    if (Array.isArray(data)) {
      this.value = [...this.value, ...data];
    } else {
      console.warn('[ListElement] append() expects an array');
    }
  }


  /** ─────────────────────────────────────────── **/
  /**         Child Element Resolution             **/
  /** ─────────────────────────────────────────── **/

  /**
   * The tag name to stamp per item. Override in subclass or use item-tag attribute.
   * Resolution: item-tag attribute > subclass override > schema hint > 'ntt-item'
   */
  get childTag() {
    return this.getAttribute('item-tag')
      || this.schema?.ui?.renderer?.item
      || 'ntt-item';
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
  /**         Default Render                       **/
  /** ─────────────────────────────────────────── **/

  render() {
    if (!this.schema || !Array.isArray(this.value)) return;
    Logging.debug(`[ListElement] Rendering ${this.model} — ${this.value.length} items`);

    this.shadowRoot.innerHTML = `
      <div class="list-header">
        <h1>${this.model}s</h1>
        <span class="list-count">${this.value.length}</span>
      </div>
      <div class="list-grid"></div>
    `;
    if (this.$styles) this.shadowRoot.appendChild(this.$styles);

    const grid = this.shadowRoot.querySelector('.list-grid');
    this.value.forEach((addr, i) => {
      const child = this.createChild(addr);
      child.style.setProperty('--stagger-delay', `${i * 50}ms`);
      grid.appendChild(child);
    });
  }
}
