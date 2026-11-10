/** Native collection chrome, stable keyed children and packed card layout.
 * API: NTTList renders ListElement membership, native create/paging controls
 * and retained child controllers; focusFallback can receive retiring focus.
 * ListElement owns querying and correlation; NTT owns shared entity values.
 * Backend policy remains authoritative. Import registers the ntx-list tag;
 * use its query property or JSON query attribute for independent pages. */
import './ntx-item.js';
import {ListElement} from './ListElement.js';
import {NTT} from '../core/NTT.js';
import {Component} from '../core/Component.js';
import {permissions} from '../utils/Permissions.js';
import {NTTModal} from './ntx-modal.js';
import {Formidable} from '../generators/form.js';
import './ntx-icon.js';

/** Render native collections without replacing live child controllers. */
export class NTTList extends ListElement {
  #packedObserver = null;
  #packedLayoutFrame = 0;
  #childContexts = new WeakMap();
  #header;
  #count;
  #description;
  #icon;
  #createLabel;

  /** Optional focus destination when an owned card becomes unavailable.
   * @type {HTMLElement|null} */
  focusFallback = null;

  /** Resolve the default collection stylesheet.
   * @returns {string} Stylesheet URL. */
  get styles() { return new URL('./ntx-list.css', import.meta.url).href; }

  /** Release layout observers before native lifecycle cleanup.
   * @returns {void} */
  disconnectedCallback() {
    this.#teardownPackedLayout();
    super.disconnectedCallback();
  }

  /** Enable packing for wide cards outside compact sidebar lists.
   * @returns {boolean} Whether measured row spans should be used. */
  get usesPackedLayout() {
    return this.childDisplay === 'md' &&
      !this.hasAttribute('sidebar-dropdown');
  }

  /** Resolve native create-button visibility; applications may override it.
   * @returns {boolean} Whether creation should be offered. */
  get canCreate() {
    return !this.hasAttribute('headless') &&
      this.hasAttribute('allow-create') &&
      permissions.canAction(this.schema?.access, 'create');
  }

  /** Retain a live child outside current membership, such as an unsaved draft.
   * @param {HTMLElement} child Existing native item controller.
   * @returns {boolean} False by default; does not affect page counts. */
  retainChild(child) { return false; }

  /** Apply presentation-only record suppression without changing membership.
   * @param {Object|undefined} record Shared native entity value.
   * @returns {boolean} True by default; not an authorization check. */
  isVisibleRecord(record) { return true; }

  /** Control retained work independently of ordinary record filtering.
   * @param {HTMLElement} child Retained controller in the current context.
   * @returns {boolean} True by default; stale/error contexts remain hidden. */
  isVisibleRetainedChild(child) { return true; }

  /** Build stable public refs: items, heading, status, create and refresh,
   * plus paging and next. The heading is a text-only span beside the count.
   * @returns {void} */
  prerender() {
    if (this.items) return;
    // 0. Mount trusted structural markup once; listeners survive every render.
    this.shadowRoot.innerHTML = `
      <div class="list-header">
        <div class="list-heading">
          <div class="list-title-wrap">
            <ntx-icon class="list-title-icon"></ntx-icon>
            <h1><span class="list-title"></span>
              <span class="list-count"></span></h1>
          </div>
          <p class="list-description"></p>
        </div>
        <button type="button" class="refresh-btn">Refresh</button>
        <button type="button" class="add-btn">
          <span class="add-btn-plus">+</span>
          <span class="add-btn-label"></span>
        </button>
      </div>
      <p class="list-status" role="status" aria-live="polite"></p>
      <div class="list-grid"></div>
      <div class="list-paging">
        <button type="button" class="load-more-btn">Load More</button>
      </div>
    `;
    this.items = this.shadowRoot.querySelector('.list-grid');
    this.heading = this.shadowRoot.querySelector('.list-title');
    this.heading.tabIndex = -1;
    this.status = this.shadowRoot.querySelector('.list-status');
    this.create = this.shadowRoot.querySelector('.add-btn');
    this.refresh = this.shadowRoot.querySelector('.refresh-btn');
    this.paging = this.shadowRoot.querySelector('.list-paging');
    this.next = this.shadowRoot.querySelector('.load-more-btn');
    this.#header = this.shadowRoot.querySelector('.list-header');
    this.#count = this.shadowRoot.querySelector('.list-count');
    this.#description = this.shadowRoot.querySelector('.list-description');
    this.#icon = this.shadowRoot.querySelector('.list-title-icon');
    this.#createLabel = this.shadowRoot.querySelector('.add-btn-label');
    // 1. Keep create intent overridable and query retry explicitly user-driven.
    this.create.addEventListener('click', () => this.openCreateModal());
    this.refresh.addEventListener('click', () => {
      this.loadPage(0, {retain: true});
    });
    this.next.addEventListener('click', () => {
      if (this.hasQuery && this.state === 'error') {
        this.loadPage(this.requestedOffset, {
          retain: true, append: this.requestedOffset > 0,
        });
      } else this.loadMore();
    });
  }

  /** Stop scheduled measurements and optionally clear packed row spans.
   * @param {boolean} [clearSpans=false] Remove packing styles as well.
   * @returns {void} */
  #teardownPackedLayout(clearSpans = false) {
    // 0. Stop measurements before removing optional packing styles.
    if (this.#packedLayoutFrame) {
      cancelAnimationFrame(this.#packedLayoutFrame);
      this.#packedLayoutFrame = 0;
    }
    this.#packedObserver?.disconnect();
    if (!clearSpans || !this.items) return;
    this.items.classList.remove('list-grid--packed');
    Array.from(this.items.children).forEach(child => {
      child.style.removeProperty('grid-row-end');
    });
  }

  /** Coalesce child size changes into one packed-layout measurement.
   * @returns {void} */
  #schedulePackedLayout() {
    // 0. Share one pending frame across all child-size notifications.
    if (this.#packedLayoutFrame) return;
    this.#packedLayoutFrame = requestAnimationFrame(() => {
      this.#packedLayoutFrame = 0;
      this.#applyPackedLayout();
    });
  }

  /** Measure visible child heights and assign packed grid row spans.
   * @returns {void} */
  #applyPackedLayout() {
    // 0. Read the grid's row geometry once for all visible children.
    const grid = this.items;
    if (!grid || grid.hidden || !this.usesPackedLayout) return;
    const styles = getComputedStyle(grid);
    const rowSize = parseFloat(styles.getPropertyValue(
      '--ntx-list-packed-row-size',
    )) || 8;
    const gap = parseFloat(styles.rowGap || styles.gap) || 0;
    // 1. Convert each visible card height into an integral row span.
    Array.from(grid.children).forEach(child => {
      if (child.hidden) return;
      const height = child.getBoundingClientRect().height;
      const span = Math.max(1, Math.ceil((height + gap) / (rowSize + gap)));
      child.style.gridRowEnd = `span ${span}`;
    });
  }

  /** Observe the current stable grid children when packing is enabled.
   * @returns {void} */
  #syncPackedLayout() {
    // 0. Disable packing when the current presentation does not support it.
    if (!this.items) return;
    if (!this.usesPackedLayout) {
      this.#teardownPackedLayout(true);
      return;
    }
    // 1. Observe current children and coalesce their next measurement.
    this.items.classList.add('list-grid--packed');
    if (!this.#packedObserver) {
      this.#packedObserver = new ResizeObserver(() => {
        this.#schedulePackedLayout();
      });
    }
    this.#packedObserver.disconnect();
    Array.from(this.items.children).forEach(child => {
      this.#packedObserver.observe(child);
    });
    this.#schedulePackedLayout();
  }

  /** Open the native schema-driven create form; applications may override it.
   * @returns {void} */
  openCreateModal() {
    // 0. Mount the native editor in the standard creation modal.
    const modal = NTTModal.open({
      title: `New ${this.schema.__name__}`,
      submitLabel: 'Create',
    });
    const el = document.createElement(this.childTag);
    el.setAttribute('display', 'md');
    el.setAttribute('create-mode', '');
    el.mode = 'edit';
    el.schema = this.schema;
    el.value = {};
    modal.body.appendChild(el);
    // 1. Validate form values before dispatching native CREATE.
    modal.onSubmit = () => {
      if (!el.value || typeof el.value !== 'object') return;
      const errors = Formidable.validateForm({
        schema: el.schema, value: el.value, ref: el.ref, name: el.name,
      });
      if (errors.length > 0) {
        if (el.showFieldErrors) el.showFieldErrors(errors);
        return;
      }
      const data = {};
      for (const [k, v] of Object.entries(el.value)) {
        if (v != null && !(typeof v === 'number' && isNaN(v))) data[k] = v;
      }
      if (Object.keys(data).length === 0) return;
      this.proto.call('CREATE', data, {inbox: 'CREATE'});
      modal.close('submit');
    };
  }

  /** Reconcile addresses through the same stable renderer used by full renders.
   * @param {string[]} prev Previous native membership.
   * @param {string[]} next Current native membership.
   * @returns {boolean} Whether the existing structure handled the update. */
  update(prev, next) {
    if (!Array.isArray(prev) || !Array.isArray(next) || !this.items) {
      return false;
    }
    this.value = next;
    this.render();
    return true;
  }

  /** Check lifecycle opt-in throughout a light/open-shadow subtree.
   * Foreign custom elements need an open root and a move callback; closed
   * roots cannot be inspected for destructive descendant lifecycle hooks.
   * @param {Element} element Root or descendant to inspect.
   * @param {boolean} [nativeMove=true] Allow move-aware custom elements.
   * @returns {boolean} Whether every observable custom element is safe. */
  #canMoveSubtree(element, nativeMove = true) {
    // 0. Each custom descendant receives its own browser lifecycle reaction.
    const custom = element.localName.includes('-') ||
      element.hasAttribute('is');
    if (custom && (!nativeMove ||
        typeof element.connectedMoveCallback !== 'function' ||
        (!(element instanceof Component) && !element.shadowRoot))) {
      return false;
    }
    // 1. Inspect both trees; checking only the card host is insufficient.
    return [...element.children, ...(element.shadowRoot?.children || [])]
      .every(child => this.#canMoveSubtree(child, nativeMove));
  }

  /** Choose a state-preserving move or a narrowly supported native rebind.
   * @param {HTMLElement} child Existing controller to reposition.
   * @returns {string|null} Insert, preserve, rebind, or an immovable anchor. */
  #moveKind(child) {
    // 0. New nodes need no preservation; modern moves preserve focus as well.
    if (!child.isConnected) return 'insert';
    if (typeof this.items.moveBefore === 'function' &&
        this.#canMoveSubtree(child)) return 'preserve';
    // 1. Legacy moves support only idle stock cards with no custom children.
    // Reassigning ref after reconnect restores the native entity subscription.
    const active = this.shadowRoot.activeElement;
    if (this.retainChild(child) || child.mode !== 'display' ||
        child === active || child.contains(active) ||
        child.constructor !== customElements.get('ntx-item')) return null;
    const descendants = [...child.children, ...child.shadowRoot.children];
    return descendants.every(node => this.#canMoveSubtree(node, false))
      ? 'rebind' : null;
  }

  /** Physically order keyed controllers without destroying retained work.
   * @param {HTMLElement[]} members Desired members followed by retained work.
   * @returns {void} */
  #orderChildren(members) {
    // 0. Immovable controllers can stay anchored if their relative order fits.
    const kinds = new Map(members.map(child => [child, this.#moveKind(child)]));
    const anchors = members.filter(child => !kinds.get(child));
    const existingAnchors = [...this.items.children]
      .filter(child => !kinds.get(child));
    const blocked = anchors.some((child, index) =>
      child !== existingAnchors[index]);
    let focused = this.shadowRoot.activeElement;
    while (focused?.shadowRoot?.activeElement) {
      focused = focused.shadowRoot.activeElement;
    }
    const selection = typeof focused?.selectionStart === 'number'
      ? [focused.selectionStart, focused.selectionEnd,
        focused.selectionDirection] : null;
    // 1. Move only safe nodes, working backwards around untouched anchors.
    // On a blocked reorder, still mount new records but do not shuffle work.
    let before = null;
    for (const child of [...members].reverse()) {
      child.style.removeProperty('order');
      const kind = kinds.get(child);
      if (kind && (!blocked || kind === 'insert') &&
          (child.parentNode !== this.items ||
            child.nextElementSibling !== before)) {
        if (kind === 'preserve') this.items.moveBefore(child, before);
        else {
          this.items.insertBefore(child, before);
          if (kind === 'rebind') child.ref = child.ref;
        }
      }
      before = child;
    }
    // Chromium preserves focus during moveBefore, but may reset text selection.
    if (selection && focused.isConnected) {
      focused.setSelectionRange(...selection);
    }
    // 2. Never silently present a server order that was not physically applied.
    const deferred = members.some((child, index) =>
      this.items.children[index] !== child);
    this.toggleAttribute('data-order-deferred', deferred);
    if (deferred) {
      this.status.textContent = 'Order not applied: these cards cannot be ' +
        'moved safely in this browser. Finish retained work and refresh, ' +
        'or use a browser and card renderer with state-preserving moves.';
      this.status.hidden = false;
    }
  }

  /** Transfer focus before hiding or disconnecting its owning card.
   * @param {HTMLElement} child Card about to become unavailable.
   * @returns {void} */
  #retireFocus(child) {
    // 0. Never disturb focus outside the disappearing card's subtree.
    const active = this.shadowRoot.activeElement;
    if (!active || (active !== child && !child.contains(active))) return;
    const target = this.focusFallback?.isConnected
      ? this.focusFallback : this.heading;
    if (target?.isConnected) target.focus();
  }

  /** Reconcile membership while preserving connected controller identity.
   * @param {boolean} query Whether membership is owned by a query.
   * @returns {void} */
  #reconcile(query) {
    // 0. Keep controllers parked during reads/errors; never expose old callers.
    const context = this.queryContextKey;
    const current = query && this.hasCurrentPage && this.hasQueryContext;
    const existing = Array.from(this.items.children);
    if (query && !current) {
      for (const child of existing) this.#retireFocus(child);
    }
    this.items.hidden = query && !current;
    this.items.inert = this.items.hidden;
    if (query && !current) {
      this.removeAttribute('data-order-deferred');
      for (const child of existing) {
        child.hidden = true;
        child.inert = true;
      }
      return;
    }
    // 1. Index reusable controllers within the exact caller/model boundary.
    const byAddress = new Map(existing.filter(child =>
      !query || this.#childContexts.get(child) === context,
    ).map(child => [child.dataset.value, child]));
    const members = [];
    const templated = this.querySelector('template[item-template]');
    for (const [index, addr] of [...new Set(this.value)].entries()) {
      let child = byAddress.get(addr);
      const id = addr.split('/').pop();
      const record = NTT.get(`${this.model}/${id}`)?.value ?? child?.value;
      const visible = this.isVisibleRecord(record);
      if (!child && !visible) continue;
      if (!child) {
        child = this.createChild(addr);
        child.dataset.value = addr;
        child.style.setProperty('--stagger-delay', `${index * 50}ms`);
        this.#childContexts.set(child, context);
      }
      if (!templated && child.getAttribute('display') !== this.childDisplay) {
        child.setAttribute('display', this.childDisplay);
      }
      const hidden = !visible && !(this.retainChild(child) &&
        this.isVisibleRetainedChild(child));
      if (hidden) this.#retireFocus(child);
      child.hidden = hidden;
      child.inert = child.hidden;
      members.push(child);
    }
    // 2. Retained controllers are not page members and cannot inflate counts.
    const memberSet = new Set(members);
    for (const child of existing) {
      if (memberSet.has(child)) continue;
      if (!this.retainChild(child)) {
        this.#retireFocus(child);
        child.remove();
        continue;
      }
      if (!templated && this.#childContexts.get(child) === context &&
          child.getAttribute('display') !== this.childDisplay) {
        child.setAttribute('display', this.childDisplay);
      }
      const hidden = (query && this.#childContexts.get(child) !== context) ||
        !this.isVisibleRetainedChild(child);
      if (hidden) this.#retireFocus(child);
      child.hidden = hidden;
      child.inert = child.hidden;
      members.push(child);
    }
    // 3. Keep visual, reading and keyboard order aligned with accepted results.
    this.#orderChildren(members);
  }

  /** Update safe native chrome and keyed items without replacing structure.
   * @returns {void} */
  render() {
    if (!this.schema || !Array.isArray(this.value)) return;
    this.prerender();
    // 0. Derive counts only from accepted membership, never retained children.
    const query = this.hasQuery;
    if (query && !this.hasQueryContext &&
        (this.hasCurrentPage || this.meta || this.error)) {
      this.loadPage();
      if (!this.hasQueryContext) {
        this.failPage('Login or model changed. Refresh this collection.');
      }
    }
    const sameContext = !query || this.hasQueryContext;
    this.dataset.state = query ? this.state
      : this.value.length ? 'ready' : 'empty';
    const meta = sameContext
      ? query ? this.meta : this.proto?._paginationMeta : null;
    const count = sameContext ? this.value.length : 0;
    const total = meta?.total ?? count;
    const hasMore = query ? meta?.has_more
      : meta && (meta.has_more || this.value.length < total);
    this.#header.hidden = this.hasAttribute('headless');
    this.heading.textContent = `${this.model || this.schema.__name__ || ''}s`;
    this.#count.textContent = `${count}` +
      (meta ? ` / ${total}` : '');
    this.#description.textContent = this.schema.ui?.description || '';
    this.#description.hidden = !this.#description.textContent;
    this.#icon.hidden = !this.schema.ui?.icon;
    this.#icon.setAttribute('value', this.schema.ui?.icon || '');
    this.#icon.setAttribute('label', this.schema.__name__ || this.model || '');
    // 1. Refresh query-only controls while preserving native create overrides.
    const label = this.schema.ui?.create_label || '';
    this.create.hidden = !this.canCreate;
    this.create.classList.toggle('add-btn--text', Boolean(label));
    this.create.title = label || 'Add new';
    this.create.setAttribute('aria-label', label || 'Add new');
    this.#createLabel.textContent = label;
    this.#createLabel.hidden = !label;
    this.refresh.hidden = !query;
    this.refresh.disabled = Boolean(this.pending);
    const emptyText = meta?.total > 0 || meta?.offset > 0
      ? 'No records on this page. Refresh to return to the first page.'
      : 'No records found.';
    this.status.setAttribute('role', this.error ? 'alert' : 'status');
    this.status.setAttribute('aria-live', this.error ? 'assertive' : 'polite');
    this.status.textContent = !query ? '' : this.error ||
      (this.state === 'loading' ? 'Loading…' :
        this.state === 'empty' ? emptyText : '');
    this.status.hidden = !this.status.textContent;
    this.items.setAttribute('aria-busy', String(query && !!this.pending));
    this.paging.hidden = !hasMore && !(query && this.state === 'error');
    this.next.disabled = query && Boolean(this.pending);
    this.next.textContent = query && this.state === 'error'
      ? 'Retry' : 'Load More';
    // 2. Reconcile data and emit a generic post-render coordination signal.
    this.#reconcile(query);
    this.#syncPackedLayout();
    this.dispatchEvent(new CustomEvent('ntx:list-rendered', {
      bubbles: true, composed: true,
    }));
  }
}

customElements.define('ntx-list', NTTList);

/* Changelog
 * - 2026-11-10: Restore focus recovery for unavailable list cards.
 * - 2026-11-02: Recover focus before owned cards are hidden or removed.
 * - 2026-10-26: Preserve native chrome and keyed query child controllers.
 *   Project list state, defer unsafe moves and isolate retained visibility.
 *   Update reused displays and avoid creating suppressed controllers.
 *   Apply physical safe moves and visibly report blocked ordering.
 *   Preserve focused text selections during native browser moves.
 *   Present invalid declarative queries without enabling legacy reads. */
