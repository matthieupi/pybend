/**
 * NTTList — Built-in default collection component.
 *
 * Provides zero-config rendering for any model collection.
 * Stamps <ntx-item> per entity by default.
 * For custom collection UIs, extend ListElement directly instead.
 */
import './ntx-item.js';
import {ListElement} from './ListElement.js';
import {permissions} from '../utils/Permissions.js';
import {NTTModal} from './ntx-modal.js';
import { Formidable } from '../generators/form.js';
import { iconMarkup } from '../utils/icon-resolver.js';
import './ntx-icon.js';


export class NTTList extends ListElement {

  #packedObserver = null;
  #packedLayoutFrame = 0;

  get styles() { return new URL('./ntx-list.css', import.meta.url).href; }

  disconnectedCallback() {
    this.#teardownPackedLayout();
    super.disconnectedCallback();
  }

  get usesPackedLayout() {
    return this.childDisplay === 'md' && !this.hasAttribute('sidebar-dropdown');
  }

  #teardownPackedLayout(clearSpans = false) {
    if (this.#packedLayoutFrame) {
      cancelAnimationFrame(this.#packedLayoutFrame);
      this.#packedLayoutFrame = 0;
    }
    this.#packedObserver?.disconnect();
    if (!clearSpans) return;

    const grid = this.shadowRoot?.querySelector('.list-grid');
    if (!grid) return;
    grid.classList.remove('list-grid--packed');
    Array.from(grid.children).forEach((child) => child.style.removeProperty('grid-row-end'));
  }

  #schedulePackedLayout() {
    if (this.#packedLayoutFrame) return;
    this.#packedLayoutFrame = requestAnimationFrame(() => {
      this.#packedLayoutFrame = 0;
      this.#applyPackedLayout();
    });
  }

  #applyPackedLayout() {
    const grid = this.shadowRoot?.querySelector('.list-grid');
    if (!grid || !this.usesPackedLayout) return;

    const children = Array.from(grid.children);
    if (children.length === 0) return;

    const styles = getComputedStyle(grid);
    const rowSize = parseFloat(styles.getPropertyValue('--ntx-list-packed-row-size')) || 8;
    const gap = parseFloat(styles.rowGap || styles.gap) || 0;

    children.forEach((child) => {
      const height = child.getBoundingClientRect().height;
      const span = Math.max(1, Math.ceil((height + gap) / (rowSize + gap)));
      child.style.gridRowEnd = `span ${span}`;
    });
  }

  #syncPackedLayout() {
    const grid = this.shadowRoot?.querySelector('.list-grid');
    if (!grid) return;

    if (!this.usesPackedLayout) {
      this.#teardownPackedLayout(true);
      return;
    }

    grid.classList.add('list-grid--packed');

    if (!this.#packedObserver) {
      this.#packedObserver = new ResizeObserver(() => this.#schedulePackedLayout());
    }

    this.#packedObserver.disconnect();
    Array.from(grid.children).forEach((child) => this.#packedObserver.observe(child));
    this.#schedulePackedLayout();
  }

  openCreateModal() {
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

    modal.onSubmit = () => {
      if (!el.value || typeof el.value !== 'object') return;
      const errors = Formidable.validateForm(el);
      if (errors.length > 0) {
        if (el.showFieldErrors) el.showFieldErrors(errors);
        return;
      }
      const data = {};
      for (const [k, v] of Object.entries(el.value)) {
        if (v != null && !(typeof v === 'number' && isNaN(v))) data[k] = v;
      }
      if (Object.keys(data).length === 0) return;
      this.proto.call('CREATE', data, { inbox: 'CREATE' });
      modal.close('submit');
    };
  }

  update(prev, next) {
    if (!Array.isArray(prev) || !Array.isArray(next)) return false;
    const grid = this.shadowRoot?.querySelector('.list-grid');
    if (!grid) return false;

    const prevSet = new Set(prev);
    const nextSet = new Set(next);

    const deletions = prev.filter(addr => !nextSet.has(addr));
    for (const addr of deletions) {
      const el = grid.querySelector(`[data-value="${addr}"]`);
      if (el) el.remove();
    }

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

    const countEl = this.shadowRoot.querySelector('.list-count');
    if (countEl) {
      const meta = this.proto?._paginationMeta;
      const total = meta?.total ?? next.length;
      countEl.textContent = `${next.length}${meta ? ` / ${total}` : ''}`;
    }

    this.#syncPackedLayout();

    return true;
  }

  render() {
    if (!this.schema || !Array.isArray(this.value)) return;

    this.#teardownPackedLayout();

    const meta = this.proto?._paginationMeta;
    const total = meta?.total ?? this.value.length;
    const hasMore = meta?.has_more ?? false;
    const headless = this.hasAttribute('headless');
    const canCreate = !headless && this.hasAttribute('allow-create') &&
                      permissions.canAction(this.schema?.access, 'create');
    const description = this.schema?.ui?.description || '';
    const createLabel = this.schema?.ui?.create_label || '';
    const addBtnClass = createLabel ? 'add-btn add-btn--text' : 'add-btn';
    const addBtnTitle = createLabel || 'Add new';
    const addBtnContent = createLabel
      ? `<span class="add-btn-plus">+</span><span class="add-btn-label">${createLabel}</span>`
      : '+';

    this.shadowRoot.innerHTML = `
      ${headless ? '' : `
      <div class="list-header">
        <div class="list-heading">
          <div class="list-title-wrap">
            ${iconMarkup(this.schema?.ui?.icon, { label: this.schema?.__name__ || this.model, className: 'list-title-icon' })}
            <h1>${this.model}s <span class="list-count">${this.value.length}${meta ? ` / ${total}` : ''}</span></h1>
          </div>
          ${description ? `<p class="list-description">${description}</p>` : ''}
        </div>
        ${canCreate ? `<button class="${addBtnClass}" title="${addBtnTitle}">${addBtnContent}</button>` : ''}
      </div>`}
      <div class="list-grid"></div>
      ${hasMore ? '<button class="load-more-btn">Load More</button>' : ''}
    `;

    const grid = this.shadowRoot.querySelector('.list-grid');
    const fragment = document.createDocumentFragment();
    this.value.forEach((addr, i) => {
      const child = this.createChild(addr);
      child.setAttribute('data-value', addr);
      child.style.setProperty('--stagger-delay', `${i * 50}ms`);
      fragment.appendChild(child);
    });
    grid.appendChild(fragment);

    this.#syncPackedLayout();

    this.shadowRoot.querySelector('.load-more-btn')?.addEventListener('click', () => this.loadMore());
    this.shadowRoot.querySelector('.add-btn')?.addEventListener('click', () => this.openCreateModal());
  }

}

customElements.define('ntx-list', NTTList);
