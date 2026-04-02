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
 * The built-in NTTList (ntx-list.js) provides a zero-config default.
 */
import {Component} from '../core/Component.js';
import TX from '../core/TX.js';
import Logging from '../utils/Logging.js';
import {permissions} from '../utils/Permissions.js';
import {NTTModal} from './ntx-modal.js';
import { Formidable } from '../generators/form.js';
import { iconMarkup } from '../utils/icon-resolver.js';
import './ntx-icon.js';


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
  /**         Create (Modal)                       **/
  /** ─────────────────────────────────────────── **/

  /** Open a modal with a create form for this entity type. */
  openCreateModal() {
    const modal = NTTModal.open({
      title: `New ${this.schema.__name__}`,
      submitLabel: 'Create',
    });

    // Stamp an ntx-item in create/edit mode inside the modal body
    const el = document.createElement(this.childTag);
    el.setAttribute('display', 'md');
    el.setAttribute('create-mode', '');
    el.mode = 'edit';
    el.schema = this.schema;
    el.value = {};
    modal.body.appendChild(el);

    modal.onSubmit = () => {
      if (!el.value || typeof el.value !== 'object') return;
      // Client-side validation before sending
      const errors = Formidable.validateForm(el);
      if (errors.length > 0) {
        if (el.showFieldErrors) el.showFieldErrors(errors);
        return;
      }
      // Strip null/NaN values before sending to avoid invalid payloads
      const data = {};
      for (const [k, v] of Object.entries(el.value)) {
        if (v != null && !(typeof v === 'number' && isNaN(v))) data[k] = v;
      }
      if (Object.keys(data).length === 0) return;
      this.proto.call('CREATE', data, { inbox: 'CREATE' });
      modal.close('submit');
    };
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

  /** Patch list DOM in-place: remove deletions, append additions. Returns false → full render(). */
  update(prev, next) {
    if (!Array.isArray(prev) || !Array.isArray(next)) return false;
    const grid = this.shadowRoot?.querySelector('.list-grid');
    if (!grid) return false;

    const prevSet = new Set(prev);
    const nextSet = new Set(next);

    // Deletions: remove children whose addr is no longer in list
    const deletions = prev.filter(addr => !nextSet.has(addr));
    for (const addr of deletions) {
      const el = grid.querySelector(`[data-value="${addr}"]`);
      if (el) el.remove();
    }

    // Additions: batch into a fragment so we only trigger one reflow
    const additions = next.filter(addr => !prevSet.has(addr));
    if (additions.length > 0) {
      const fragment = document.createDocumentFragment();
      for (const addr of additions) {
        const child = this.createChild(addr);
        child.setAttribute('data-value', addr);
        fragment.appendChild(child);
      }
      grid.appendChild(fragment);
    }

    // Update count
    const countEl = this.shadowRoot.querySelector('.list-count');
    if (countEl) {
      const meta = this.proto?._paginationMeta;
      const total = meta?.total ?? next.length;
      countEl.textContent = `${next.length}${meta ? ` / ${total}` : ''}`;
    }

    return true;
  }


  /** ─────────────────────────────────────────── **/
  /**         Default Render                       **/
  /** ─────────────────────────────────────────── **/

  render() {
    if (!this.schema || !Array.isArray(this.value)) return;

    const meta = this.proto?._paginationMeta;
    const total = meta?.total ?? this.value.length;
    const hasMore = meta?.has_more ?? false;
    const headless = this.hasAttribute('headless');
    const canCreate = !headless && this.hasAttribute('allow-create') &&
                      permissions.canAction(this.schema?.access, 'create');

    this.shadowRoot.innerHTML = `
      ${headless ? '' : `
      <div class="list-header">
        <div class="list-title-wrap">
          ${iconMarkup(this.schema?.ui?.icon, { label: this.schema?.__name__ || this.model, className: 'list-title-icon' })}
          <h1>${this.model}s</h1>
        </div>
        <span class="list-count">${this.value.length}${meta ? ` / ${total}` : ''}</span>
        ${canCreate ? '<button class="add-btn" title="Add new">+</button>' : ''}
      </div>`}
      <div class="list-grid"></div>
      ${hasMore ? '<button class="load-more-btn">Load More</button>' : ''}
    `;

    // Batch all child elements into a DocumentFragment first so the browser
    // only performs a single reflow when the fragment is appended to the grid.
    const grid = this.shadowRoot.querySelector('.list-grid');
    const fragment = document.createDocumentFragment();
    this.value.forEach((addr, i) => {
      const child = this.createChild(addr);
      child.setAttribute('data-value', addr);
      child.style.setProperty('--stagger-delay', `${i * 50}ms`);
      fragment.appendChild(child);
    });
    grid.appendChild(fragment);

    // Bind events
    this.shadowRoot.querySelector('.load-more-btn')?.addEventListener('click', () => this.loadMore());
    this.shadowRoot.querySelector('.add-btn')?.addEventListener('click', () => this.openCreateModal());
  }
}
