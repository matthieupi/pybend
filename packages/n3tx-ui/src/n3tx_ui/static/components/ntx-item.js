/**
 * NTTItem — Built-in default single entity component.
 *
 * Provides zero-config rendering for any model:
 *   - Schema-driven form via Formidable
 *   - Display / edit mode toggle
 *   - Method buttons via <ntx-method>
 *   - Adaptive display: xs (pill), sm (compact), md (card), lg/xl (detail)
 *
 * Size methods (xs, sm, md, lg, xl) return HTML strings.
 * render() dispatches to the current size method, commits DOM, and binds events.
 *
 * For custom rendering, extend NTTElement directly instead.
 */
import {NTTElement} from './NTTElement.js';
import {NTT} from '../core/NTT.js';
import {Formidable} from '../generators/form.js';
import {permissions} from '../utils/Permissions.js';
import {getWidgetForField} from '../widgets/index.js';
import TX from '../core/TX.js';
import Logging from '../utils/Logging.js';
import './ntx-method.js';
import './ntx-stream.js';


export class NTTItem extends NTTElement {

  mode = 'display';

  /** Custom display components usually inherit the base edit form. */
  get usesCustomEditLayout() { return false; }

  /** Snapshot of value before edit — used by cancelEdit() to revert without saving. */
  #editSnapshot = null;

  /** AbortController for event listeners — aborted on each re-render to prevent accumulation. */
  #eventAC = null;

  get styles() {
    return [
      new URL('./ntx-item.css', import.meta.url).href,
      new URL('../widgets/widgets.css', import.meta.url).href,
    ];
  }

  prerender() {
    if (!this.schema?.__name__) {
      const size = this.displayMode;
      this.shadowRoot.innerHTML =
        `<div class="card skeleton" data-display="${size}">${this.placeholder(size)}</div>`;
    }
  }

  /** Return layout-matching bone HTML for the skeleton placeholder. */
  placeholder(size) {
    switch (size) {
      case 'xs':
        return '<span class="bone" style="width:4rem;height:0.9rem;border-radius:999px"></span>';
      case 'sm':
        return `
          <span class="bone" style="width:28px;height:28px;border-radius:50%;flex-shrink:0"></span>
          <div style="display:flex;flex-direction:column;gap:0.3rem;min-width:0;flex:1">
            <span class="bone" style="width:45%;height:0.7rem"></span>
            <span class="bone" style="width:30%;height:0.55rem"></span>
          </div>`;
      default: // md, lg, xl
        return `
          <span class="bone" style="width:55%;height:0.85rem;margin-bottom:0.6rem"></span>
          <span class="bone" style="width:100%;height:0.6rem;margin-bottom:0.45rem"></span>
          <span class="bone" style="width:70%;height:0.6rem"></span>`;
    }
  }

  /** ── Delete ── **/

  deleteItem() {
    if (!permissions.canAction(this.schema?.access, 'delete', this.value)) return;

    // Detect nested context: this item lives inside another ntx-item's
    // list field (e.g. a tool inside an agent's tools array).
    const parentHost = typeof this.getRootNode === 'function'
      ? this.getRootNode()?.host : undefined;
    const nestedField = parentHost ? this.#findParentArrayField(parentHost) : null;

    if (nestedField) {
      // ── Unlink from parent list ──
      // The entity may be referenced by multiple parents (e.g. a tool used by
      // several agents), so we only remove the association — not the entity itself.
      if (!confirm(`Remove this ${this.schema.__name__} from the list?`)) return;

      // Optimistic: remove ref from parent's array
      const arr = parentHost.value[nestedField];
      const updated = { ...parentHost.value, [nestedField]: arr.filter(r => r !== this.ref) };
      parentHost.value = updated;

      // Persist via TX: send DELETE to the join URL, routed through the parent
      // entity. The response goes to _response_ (which calls pull() to refresh
      // the parent), NOT to the child DC's DELETE handler — so the child entity
      // stays in the global instances map.
      const parentModel = parentHost.schema?.__name__;
      const parentId = parentHost.value?.id;
      const parentEntity = (parentModel && parentId) ? NTT.get(`${parentModel}/${parentId}`) : null;
      if (parentEntity) {
        parentEntity.send(new TX({
          name: 'DELETE',
          source: parentEntity.addr,
          target: this.ref,
          meta: { inbox: '_response_' }
        }));
      }
    } else {
      // ── Top-level delete ──
      // Actually delete the entity from the database.
      if (!confirm(`Delete this ${this.schema.__name__}?`)) return;

      const target = (this.ref && this.ref.startsWith('http')) ? this.ref : this.value.$id;
      // Route through DynamicClass so the response triggers DC.DELETE,
      // which removes the instance from the registry and notifies list watchers.
      const DC = NTT.get(this.schema.__name__);
      if (DC) {
        DC.send(new TX({
          name: 'DELETE',
          target: target,
          meta: { inbox: 'DELETE' },
        }));
      }
    }
  }

  /** ── Edit / Save toggle ── **/

  toggleMode() {
    if (!permissions.canAction(this.schema?.access, 'update', this.value)) return;
    const isEdit = this.mode === 'edit';
    if (isEdit) {
      const nextValue = Formidable.readFormValue(this.shadowRoot, this);
      // Client-side validation before save
      const errors = Formidable.validateForm({
        schema: this.schema,
        value: nextValue,
        ref: this.ref,
        name: this.name,
      });
      if (errors.length > 0) {
        Formidable.showFieldErrors(this.shadowRoot, errors);
        return;
      }
      this.value = nextValue;
      this.save();
      this.#editSnapshot = null;
    } else {
      // Snapshot value before entering edit mode (for cancel revert)
      this.#editSnapshot = structuredClone(this.value);
    }
    this.mode = isEdit ? 'display' : 'edit';
    this.render();
  }

  /** Cancel edit: revert to pre-edit value and switch back to display mode. */
  cancelEdit() {
    if (this.#editSnapshot) {
      this.value = this.#editSnapshot;
      this.#editSnapshot = null;
    }
    this.mode = 'display';
    this.render();
  }

  /** ── Validation error display ── **/

  /**
   * Override NTTElement hook: switch to edit mode and highlight fields.
   * Called when backend returns structured validation errors (422).
   */
  onValidationError(errors) {
    this.mode = 'edit';
    this.render();
    // Show field errors on next frame (after render commits DOM)
    requestAnimationFrame(() => Formidable.showFieldErrors(this.shadowRoot, errors));
  }

  /**
   * Highlight invalid fields and insert error messages.
   * Clears previous errors before showing new ones.
   */
  showFieldErrors(errors) {
    Formidable.showFieldErrors(this.shadowRoot, errors);
  }

  /** ── Input change handler ── **/

  handleInputChange(e) {
    const el = e.target;
    const key = el.dataset.key;
    const index = el.dataset.index;
    const type = el.dataset.type;

    let newValue;
    if (type === 'boolean' || el.type === 'checkbox') {
      newValue = el.checked;
    } else if (type === 'number' || type === 'integer') {
      if (el.value.trim() === '') { newValue = null; }
      else {
        const num = type === 'integer' ? parseInt(el.value, 10) : parseFloat(el.value);
        newValue = isNaN(num) ? null : num;
      }
    } else if (type === 'object') {
      try { newValue = JSON.parse(el.value); } catch { newValue = el.value; }
    } else {
      newValue = el.value;
    }

    if (index !== undefined) {
      const idx = parseInt(index);
      if (!Array.isArray(this.value[key])) this.value[key] = [];
      this.value[key][idx] = newValue;
    } else {
      this.value[key] = newValue;
    }
  }


  /** ─────────────────────────────────────────── **/
  /**         Size Methods (return HTML strings)   **/
  /** ─────────────────────────────────────────── **/

  /** xs — Pill: entity name as a compact badge. */
  xs() {
    const name = this.value.name || this.value.title || this.schema.__name__;
    return `<span class="pill-label" data-value="name">${name}</span>`;
  }

  /**
   * sm — Compact row: leading element + name + inline field values.
   *
   * Respects field_order. If the first renderable field is a $ref,
   * it renders as a leading avatar/pill. Otherwise falls back to
   * the entity's image thumbnail. 'name' renders as the identity text.
   * Remaining fields fill the right side (up to 3 total).
   */
  sm() {
    // In edit mode, delegate to md() for the full form experience
    if (this.mode === 'edit') return this.md();

    const schema = this.schema;
    const props = schema.properties || {};
    const renderable = this.#smFields();

    let leadingHtml = '';
    let nameHtml = '';
    const smFields = [];

    // Action buttons (edit/delete) gated by permissions (resource-aware OWNER check)
    const canUpdate = permissions.canAction(schema.access, 'update', this.value);
    const canDelete = permissions.canAction(schema.access, 'delete', this.value);
    let actionsHtml = '';
    if (canUpdate || canDelete) {
      let btns = '';
      if (canDelete) btns += '<button class="delete-btn" title="Delete"></button>';
      if (canUpdate) {
        if (this.mode === 'edit') {
          btns += '<button class="cancel-btn" title="Cancel"></button>';
        }
        const modeClass = this.mode === 'edit' ? 'mode-edit' : 'mode-display';
        btns += `<button class="edit-btn ${modeClass}" title="${this.mode === 'edit' ? 'Save' : 'Edit'}"></button>`;
      }
      actionsHtml = `<span class="sm-actions">${btns}</span>`;
    }

    for (const key of renderable) {
      const def = props[key];
      const val = this.value[key] ?? '';

      // First $ref field → leading avatar (thumb position)
      if (!leadingHtml && (def?.type === '$ref' || def?.$ref)) {
        let refUrl = null;
        if (typeof val === 'string' && val.startsWith('http')) {
          refUrl = val;
        } else if (val && typeof val === 'object' && val.$id) {
          refUrl = val.$id;
        }
        if (refUrl) {
          const refModel = (def.$ref || '').split('/').pop();
          const childTag = this.#resolveChildTag(refModel);
          leadingHtml = `<${childTag} ref="${refUrl}" display="xs" data-model="${refModel}"></${childTag}>`;
          continue;
        }
      }

      // 'name' field → sm-name identity text
      if (key === 'name' && !nameHtml) {
        nameHtml = `<span class="sm-name" data-value="name">${val || schema.__name__}</span>`;
        continue;
      }

      // Everything else → sm-field
      if (smFields.length >= 3) break;
      if ((def?.type === '$ref' || def?.$ref)) {
        let refUrl = null;
        if (typeof val === 'string' && val.startsWith('http')) refUrl = val;
        else if (val && typeof val === 'object' && val.$id) refUrl = val.$id;
        if (refUrl) {
          const refModel = (def.$ref || '').split('/').pop();
          const childTag = this.#resolveChildTag(refModel);
          smFields.push(`<span class="sm-field sm-ref" data-value="${key}"><${childTag} ref="${refUrl}" display="xs" data-model="${refModel}"></${childTag}></span>`);
        }
        continue;  // Skip plain-text fallback for $ref fields (avoid [object Object])
      }
      const _wr = getWidgetForField(def);
      const display = _wr.widget
        ? _wr.widget.list(val, _wr.config, def)
        : val;
      smFields.push(`<span class="sm-field" data-value="${key}">${display}</span>`);
    }

    // Fallbacks
    if (!leadingHtml && this.value.image) {
      leadingHtml = `<img class="sm-thumb" src="${this.value.image}" alt="" />`;
    }
    if (!nameHtml) {
      const name = this.value.name || this.value.title || schema.__name__;
      nameHtml = `<span class="sm-name" data-value="name">${name}</span>`;
    }

    // Button-layout methods (like, favorite) for sm row
    const methods = schema.methods || {};
    let methodsHtml = '';
    for (const [name, def] of Object.entries(methods)) {
      if (def.ui?.layout === 'button') {
        const tag = def.ui?.renderer || (def.stream ? 'ntx-stream' : 'ntx-method');
        methodsHtml += `<${tag}
          model="${schema.__name__}"
          uuid="${this.value?.id || ''}"
          method="${name}"
          layout="button"
          icon="${def.ui.icon || ''}"
          count-field="${def.ui.count_field || ''}"
          label="${def.title || name}">
        </${tag}>`;
      }
    }

    // Reply button (if reply method exists)
    const hasReply = Object.entries(methods).some(([, def]) =>
      def.ui?.layout === 'inline' && def.ui?.placeholder?.toLowerCase().includes('reply'));
    if (hasReply) {
      methodsHtml += `<button class="sm-reply-btn" title="Reply">
        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 17 4 12 9 7"/><path d="M20 18v-2a4 4 0 0 0-4-4H4"/></svg>
      </button>`;
    }

    const smMethodsHtml = methodsHtml ? `<span class="sm-methods">${methodsHtml}</span>` : '';

    // When a $ref leads, stack name + fields vertically beside it
    if (leadingHtml && leadingHtml.includes('display="xs"')) {
      return `
        ${leadingHtml}
        <div class="sm-body">
          ${nameHtml}
          <span class="sm-fields">${smFields.join('')}</span>
        </div>
        ${smMethodsHtml}
        ${actionsHtml}
      `;
    }
    return `
      ${leadingHtml}
      ${nameHtml}
      <span class="sm-fields">${smFields.join('')}</span>
      ${smMethodsHtml}
      ${actionsHtml}
    `;
  }

  /** md — Card: image + edit/delete buttons + full form + methods (current default). */
  md() {
    const html = [];
    const canUpdate = permissions.canAction(this.schema.access, 'update', this.value);
    const canDelete = permissions.canAction(this.schema.access, 'delete', this.value);
    if (canUpdate || canDelete) {
      html.push('<div class="card-actions">');
      if (canDelete) {
        html.push('<button class="delete-btn" title="Delete"></button>');
      }
      if (canUpdate) {
        if (this.mode === 'edit') {
          html.push('<button class="cancel-btn" title="Cancel"></button>');
        }
        const modeClass = this.mode === 'edit' ? 'mode-edit' : 'mode-display';
        html.push(`<button class="edit-btn ${modeClass}" title="${this.mode === 'edit' ? 'Save' : 'Edit'}"></button>`);
      }
      html.push('</div>');
    }
    if (this.value.image) {
      html.push(`<img class="card-image" src="${this.value.image}" alt="${this.value.name || ''}" />`);
    }

    // Split methods: attached go into form groups, standalone go at bottom
    const methods = this.schema.methods || {};
    const attached = {};
    const standalone = {};
    for (const [name, def] of Object.entries(methods)) {
      if (def.ui?.attach_to) attached[name] = def;
      else standalone[name] = def;
    }

    html.push(Formidable.getForm({schema: this.schema, value: this.value, ref: this.ref}, this.mode, attached));
    if (this.mode !== 'edit') {
      html.push(this.#standaloneMethodsHtml(standalone));
    }
    return html.join('');
  }

  /**
   * row — Table row: raw cells for each renderable field.
   * Returns unstyled <span class="cell"> elements for use in ntx-table / ntx-row.
   * Same field filtering as sm() but includes more fields (table has room).
   */
  row() {
    const schema = this.schema;
    const props = schema.properties || {};
    const renderable = this.#smFields();
    const cells = [];
    for (const key of renderable) {
      const def = props[key];
      const val = this.value[key] ?? '';
      const display = Formidable.formatDisplayValue(def, key, val);
      cells.push(`<span class="cell" data-value="${key}">${display}</span>`);
    }
    return cells.join('');
  }

  /** lg — Detail: same as card (future: show normally-hidden fields). */
  lg() {
    return this.md();
  }

  /** xl — Page: same as card (future: full metadata, expanded children). */
  xl() {
    return this.md();
  }

  /** Base edit form renderer used as the default fallback for subclasses. */
  renderEditForm() {
    return NTTItem.prototype.md.call(this);
  }


  /** ─────────────────────────────────────────── **/
  /**         Surgical DOM Update                  **/
  /** ─────────────────────────────────────────── **/

  /** Patch individual DOM values in-place. Returns false → full render(). */
  update(prev, next) {
    if (!prev || !next) return false;
    const root = this.shadowRoot;
    if (!this._rendered) return false;  // Skeleton placeholder or no DOM → full render

    const props = this.schema.properties || {};

    for (const key of Object.keys(props)) {
      if (prev[key] === next[key]) continue;  // No change

      // Array fields: reconcile child elements in the list-field container
      if (props[key]?.type === 'array') {
        if (!this.#updateListField(root, key, prev[key], next[key])) return false;
        continue;
      }

      // Display mode: find data-value element
      const el = root.querySelector(`[data-value="${key}"]`);
      if (el) {
        const def = props[key];
        if (def?.type === '$ref' || def?.$ref) {
          return false;  // $ref contains child component — full re-render
        }
        const formatted = Formidable.formatDisplayValue(props[key], key, next[key]);
        if (props[key]?.enum) el.innerHTML = formatted;
        else el.textContent = formatted;
        continue;
      }

      // Edit mode: find data-key input (skip if user is typing in it)
      const input = root.querySelector(`[data-key="${key}"]`);
      if (input) {
        if (root.activeElement !== input) {
          if (input.type === 'checkbox') input.checked = !!next[key];
          else input.value = next[key] ?? '';
        }
        continue;
      }

      // Element not found for this key (e.g. 'id') — skip
    }

    return true;
  }

  /**
   * Surgically reconcile children in a .list-field container.
   *
   * DOM structure (from form.js getListInput, VISIBLE_COUNT=2):
   *   .list-field
   *     .list-field-header
   *     ntx-item (visible 0)
   *     ntx-item (visible 1)
   *     .nested-collapsed
   *       ntx-item (2+)
   *     .show-more-btn
   *
   * Returns false if container not found (bail to full render).
   */
  #updateListField(root, key, prevArr, nextArr) {
    const VISIBLE_COUNT = 2;
    const container = root.querySelector(`.list-field[data-value="${key}"]`);
    if (!container) return false;

    // Normalize: populated wrappers {data: [...], meta: {...}} → extract array
    const normArr = (v) => Array.isArray(v) ? v : (v?.data && Array.isArray(v.data)) ? v.data : [];
    const toRef = (v) => typeof v === 'string' ? v : v?.$id || null;
    const prevRefs = normArr(prevArr).map(toRef).filter(Boolean);
    const nextRefs = normArr(nextArr).map(toRef).filter(Boolean);
    const prevSet = new Set(prevRefs);
    const nextSet = new Set(nextRefs);
    const collapsed = container.querySelector('.nested-collapsed');

    // Removals
    for (const ref of prevRefs) {
      if (!nextSet.has(ref)) {
        const el = container.querySelector(`[ref="${ref}"]`);
        if (el) el.remove();
      }
    }

    // After removals, promote collapsed items to visible slots if needed
    if (collapsed) {
      const visibleItems = Array.from(container.children)
        .filter(c => c.matches?.('ntx-item, ntx-user'));
      while (visibleItems.length < VISIBLE_COUNT && collapsed.firstElementChild) {
        container.insertBefore(collapsed.firstElementChild, collapsed);
        visibleItems.push(visibleItems); // just bump count
      }
    }

    // Additions
    const modelName = container.dataset.model;
    const childTag = this.#resolveChildTag(modelName) || 'ntx-item';
    for (const ref of nextRefs) {
      if (!prevSet.has(ref)) {
        const el = document.createElement(childTag);
        el.setAttribute('display', 'sm');
        if (modelName) el.setAttribute('data-model', modelName);
        // Place inside .nested-collapsed if it exists, otherwise at end
        if (collapsed) {
          collapsed.appendChild(el);
        } else {
          container.appendChild(el);
        }
        // Set ref last — setAttribute triggers attributeChangedCallback
        // → ref setter → ATTACH/READ flow, and keeps the HTML attribute
        // in sync for querySelector-based removal.
        el.setAttribute('ref', ref);
      }
    }

    // Update count badge
    const countEl = container.querySelector('.list-field-count');
    if (countEl) countEl.textContent = nextRefs.length;

    // Update or remove show-more button
    const showMore = container.querySelector('.show-more-btn');
    const collapsedCount = collapsed ? collapsed.children.length : 0;
    if (collapsedCount > 0 && showMore) {
      // Update text only if not currently expanded
      if (!collapsed.classList.contains('expanded')) {
        showMore.textContent = `Show ${collapsedCount} more`;
      }
    } else if (collapsedCount === 0) {
      // No more collapsed items — remove both
      collapsed?.remove();
      showMore?.remove();
    }

    return true;
  }


  /** ─────────────────────────────────────────── **/
  /**         Render Dispatch                      **/
  /** ─────────────────────────────────────────── **/

  render() {
    if (!this.schema || !this.value) return;

    const size = this.displayMode;
    const useBaseEditForm = this.mode === 'edit' && size !== 'row' && !this.usesCustomEditLayout;
    const html = useBaseEditForm
      ? this.renderEditForm()
      : (this[size] || this.md).call(this);

    // Error banner — persistent, dismissible, appears above the card content
    const errorHtml = this.error
      ? `<div class="ntx-error"><span class="ntx-error-msg">${this.error}</span><button class="ntx-error-dismiss" title="Dismiss">&times;</button></div>`
      : '';

    // Row mode: output raw cells without card wrapper (NTTRow provides structure)
    if (size === 'row') {
      this.shadowRoot.innerHTML = errorHtml + html;
      this._rendered = true;
      this[`${size}_mounted`]?.call(this);
      return;
    }

    // When editing in compact sizes, sm() delegates to md() for the full form.
    // Match the card layout so CSS styles apply correctly.
    const layoutSize = (this.mode === 'edit' && (size === 'sm' || size === 'xs' || useBaseEditForm)) ? 'md' : size;
    // Check for reply indent (comments with parent_id)
    const isReply = this.value?.parent_id && this.schema?.properties?.parent_id?.type === 'selfref';
    const indentClass = isReply ? ' reply-indent' : '';
    this.shadowRoot.innerHTML = `${errorHtml}<div class="card${indentClass}" data-display="${layoutSize}">${html}</div>`;
    this._rendered = true;

    this.#bindEvents();
    this[`${size}_mounted`]?.call(this);
  }


  /** ─────────────────────────────────────────── **/
  /**         Private Helpers                      **/
  /** ─────────────────────────────────────────── **/

  /** Bind event listeners to current shadow DOM contents. */
  #bindEvents() {
    // Abort previous listeners before binding new ones.
    // Prevents listener accumulation across re-renders.
    this.#eventAC?.abort();
    this.#eventAC = new AbortController();
    const {signal} = this.#eventAC;

    // Error dismiss button
    this.shadowRoot.querySelector('.ntx-error-dismiss')?.addEventListener('click', () => {
      this.error = null;
      this.shadowRoot.querySelector('.ntx-error')?.remove();
    }, {signal});

    // Edit button
    this.shadowRoot.querySelector('.edit-btn')?.addEventListener('click', () => this.toggleMode(), {signal});

    // Cancel button (edit mode only)
    this.shadowRoot.querySelector('.cancel-btn')?.addEventListener('click', (e) => {
      e.stopPropagation();
      this.cancelEdit();
    }, {signal});

    // Delete button
    this.shadowRoot.querySelector('.delete-btn')?.addEventListener('click', (e) => {
      e.stopPropagation();
      this.deleteItem();
    }, {signal});

    // Input changes
    this.shadowRoot.querySelectorAll('input, textarea, select').forEach(el => {
      const event = (el.type === 'checkbox' || el.tagName === 'SELECT') ? 'change' : 'input';
      el.addEventListener(event, e => this.handleInputChange(e), {signal});
    });

    this.shadowRoot.querySelectorAll('ntx-list-field').forEach(field => {
      field.addEventListener('field-change', (e) => {
        const { field: key, value } = e.detail || {};
        if (!key) return;
        this.value = { ...this.value, [key]: value };
      }, {signal});
    });

    // Show-more toggle
    this.shadowRoot.querySelectorAll('.show-more-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const collapsed = btn.previousElementSibling;
        if (collapsed?.classList.contains('nested-collapsed')) {
          collapsed.classList.toggle('expanded');
          const count = collapsed.children.length;
          btn.textContent = collapsed.classList.contains('expanded')
            ? 'Show less' : `Show ${count} more`;
        }
      }, {signal});
    });

    // Reply button toggle — shows/hides inline reply input under the card
    this.shadowRoot.querySelector('.sm-reply-btn')?.addEventListener('click', (e) => {
      e.stopPropagation();
      const card = this.shadowRoot.querySelector('.card');
      let replyBox = this.shadowRoot.querySelector('.reply-input-box');
      if (replyBox) {
        replyBox.remove();
        return;
      }
      // Find the reply method name from schema
      const methods = this.schema?.methods || {};
      const replyEntry = Object.entries(methods).find(([, def]) =>
        def.ui?.layout === 'inline' && def.ui?.placeholder?.toLowerCase().includes('reply'));
      if (!replyEntry) return;
      const [methodName, methodDef] = replyEntry;

      replyBox = document.createElement('div');
      replyBox.className = 'reply-input-box';
      replyBox.innerHTML = `
        <input type="text" class="reply-input" placeholder="${methodDef.ui.placeholder || 'Write a reply...'}" />
        <button class="reply-submit-btn">${methodDef.ui.button_label || 'Reply'}</button>
      `;
      card.after(replyBox);

      const input = replyBox.querySelector('.reply-input');
      const btn = replyBox.querySelector('.reply-submit-btn');
      input.focus();

      const submit = () => {
        const text = input.value.trim();
        if (!text) return;
        // Route through the NTT Actor — href is authoritative (carries correct
        // nested URL like /Product/1/Comment/3) after the $id fix.
        const entity = NTT.get(this.schema.__name__ + '/' + this.value.id);
        if (entity?.call) {
          entity.call(methodName, { text }, { inbox: '_response_' });
          // _response_ handler calls pull() on the entity, but we also need the
          // parent (e.g. Product) to re-fetch so the new reply appears in its list.
          const parentHost = this.getRootNode()?.host;
          const parentModel = parentHost?.schema?.__name__;
          const parentId = parentHost?.value?.id;
          if (parentModel && parentId) {
            const parent = NTT.get(`${parentModel}/${parentId}`);
            if (parent) {
              // Small delay to let the backend process the reply before re-fetching
              setTimeout(() => parent.pull(), 300);
            }
          }
        }
        replyBox.remove();
      };
      btn.addEventListener('click', (ev) => { ev.stopPropagation(); submit(); }, {signal});
      input.addEventListener('keydown', (ev) => {
        if (ev.key === 'Enter') { ev.preventDefault(); submit(); }
        if (ev.key === 'Escape') replyBox.remove();
      }, {signal});
    }, {signal});

    // Card click → SELECT (skip interactive elements and edit mode)
    if (this.mode !== 'edit') {
      this.shadowRoot.querySelector('.card')?.addEventListener('click', (e) => {
        if (e.target.closest('button, input, textarea, select, a, ntx-method, ntx-stream, ntx-stream-agent, .reply-input-box, ntx-ref-picker')) return;
        const target = this.getAttribute('select-target');
        if (target) {
          this.send(new TX({
            name: 'SELECT', source: this.addr, target: target, data: this.ref
          }));
        }
      }, {signal});
    }
  }

  /**
   * If this item is nested inside a parent host's array field,
   * return the field key. Otherwise return null (top-level context).
   */
  #findParentArrayField(parentHost) {
    if (!parentHost?.value || !parentHost?.schema || !this.ref) return null;
    const parentProps = parentHost.schema.properties || {};
    for (const [key, def] of Object.entries(parentProps)) {
      if (def?.type !== 'array') continue;
      const arr = parentHost.value[key];
      if (Array.isArray(arr) && arr.includes(this.ref)) return key;
    }
    return null;
  }

  /**
   * Return ordered renderable field keys for sm() display.
   * Respects ui.field_order. Skips only id, hidden, array, and selfref fields.
   */
  #smFields() {
    const schema = this.schema;
    const fields = schema.properties || {};
    const ui = schema.ui || {};

    const order = ui.field_order
      ? ui.field_order.filter(k => k in fields)
      : Object.keys(fields);
    for (const k of Object.keys(fields)) {
      if (!order.includes(k)) order.push(k);
    }

    return order.filter(key => {
      if (key === 'id') return false;
      const def = fields[key];
      if (def?.ui?.display === false) return false;
      if (def?.type === 'array') return false;
      if (def?.type === 'selfref') return false;
      if (!permissions.canView(def)) return false;
      return true;
    });
  }

  /**
   * Resolve the child component tag for a $ref model.
   * Checks local $defs first, falls back to NTT registry.
   */
  #resolveChildTag(refModel) {
    const defs = this.schema?.$defs || {};
    const fromDefs = defs[refModel]?.ui?.renderer?.item;
    if (fromDefs) return fromDefs;
    const DC = NTT.get(refModel);
    return DC?.schema?.ui?.renderer?.item || 'ntx-item';
  }

  /** Build HTML for standalone method buttons (those without ui.attach_to). */
  #standaloneMethodsHtml(methods) {
    return Object.entries(methods).map(([name, def]) => {
      const humanized = String(name).replace(/_/g, ' ');
      const label = def.title || humanized;
      const ui = def.ui || {};
      const tag = def.ui?.renderer || (def.stream ? 'ntx-stream' : 'ntx-method');
      return `
        <${tag}
          model="${this.schema?.__name__ || ''}"
          uuid="${this.value?.id || ''}"
          method="${name}"
          layout="${ui.layout || 'fieldset'}"
          placeholder="${ui.placeholder || ''}"
          button-label="${ui.button_label || 'Run'}"
          widget="${ui.widget || ''}"
          icon="${ui.icon || ''}"
          count-field="${ui.count_field || ''}"
          label="${label}">
        </${tag}>
      `;
    }).join('');
  }
}

customElements.define('ntx-item', NTTItem);
