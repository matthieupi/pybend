/**
 * NTTItem — Built-in default single entity component.
 *
 * Provides zero-config rendering for any model:
 *   - Schema-driven form via Formidable
 *   - Display / edit mode toggle
 *   - Method buttons via <ntt-method>
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
import TX from '../core/TX.js';
import './ntt-method.js';


export class NTTItem extends NTTElement {

  mode = 'display';

  get styles() { return new URL('./ntt-item.css', import.meta.url).href; }

  connectedCallback() {
    super.connectedCallback();
    // Show skeleton placeholder only if no schema has been set yet (via define() or DESCRIBE)
    if (!this.schema?.__name__) {
      const size = this.displayMode;
      this.shadowRoot.innerHTML =
        `<div class="card skeleton" data-display="${size}">${this.placeholder(size)}</div>`;
      if (this.$styles) this.shadowRoot.appendChild(this.$styles);
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
    if (!confirm(`Delete this ${this.schema.__name__}?`)) return;
    // Use ref (the actual API endpoint URL) when available, otherwise fall back
    // to value.$id. For nested entities (e.g. comments inside products), ref holds
    // the correct CRUD path while $id may point to the schema-derived DynamicClass URL.
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

    // Optimistic parent update: if this item lives inside another ntt-item's
    // shadow DOM (e.g. a comment inside a product card), remove the deleted
    // ref from the parent's array field so the UI updates immediately.
    const parentHost = this.getRootNode()?.host;
    if (parentHost?.value && parentHost?.schema && this.ref) {
      const parentProps = parentHost.schema.properties || {};
      for (const [key, def] of Object.entries(parentProps)) {
        if (def?.type !== 'array') continue;
        const arr = parentHost.value[key];
        if (!Array.isArray(arr) || !arr.includes(this.ref)) continue;
        // Found the array field containing this ref — update parent value
        const updated = { ...parentHost.value, [key]: arr.filter(r => r !== this.ref) };
        parentHost.value = updated;
        break;
      }
    }
  }

  /** ── Edit / Save toggle ── **/

  toggleMode() {
    if (!permissions.canAction(this.schema?.access, 'update', this.value)) return;
    const isEdit = this.mode === 'edit';
    if (isEdit) this.save();
    this.mode = isEdit ? 'display' : 'edit';
    this.render();
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
    } else if (type === 'number') {
      newValue = parseFloat(el.value);
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
      const display = def?.ui?.widget === 'currency' && typeof val === 'number'
        ? `$${val.toFixed(2)}` : val;
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
        methodsHtml += `<ntt-method
          model="${schema.__name__}"
          uuid="${this.value?.id || ''}"
          method="${name}"
          layout="button"
          icon="${def.ui.icon || ''}"
          count-field="${def.ui.count_field || ''}"
          label="${def.title || name}">
        </ntt-method>`;
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

  /** lg — Detail: same as card (future: show normally-hidden fields). */
  lg() {
    return this.md();
  }

  /** xl — Page: same as card (future: full metadata, expanded children). */
  xl() {
    return this.md();
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
        el.textContent = Formidable.formatDisplayValue(props[key], key, next[key]);
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
   *     ntt-item (visible 0)
   *     ntt-item (visible 1)
   *     .nested-collapsed
   *       ntt-item (2+)
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
        .filter(c => c.matches?.('ntt-item, ntt-user'));
      while (visibleItems.length < VISIBLE_COUNT && collapsed.firstElementChild) {
        container.insertBefore(collapsed.firstElementChild, collapsed);
        visibleItems.push(visibleItems); // just bump count
      }
    }

    // Additions
    const modelName = container.dataset.model;
    const childTag = this.#resolveChildTag(modelName) || 'ntt-item';
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
    const html = (this[size] || this.md).call(this);

    // When editing in compact sizes, sm() delegates to md() for the full form.
    // Match the card layout so CSS styles apply correctly.
    const layoutSize = (this.mode === 'edit' && (size === 'sm' || size === 'xs')) ? 'md' : size;
    // Check for reply indent (comments with parent_id)
    const isReply = this.value?.parent_id && this.schema?.properties?.parent_id?.type === 'selfref';
    const indentClass = isReply ? ' reply-indent' : '';
    this.shadowRoot.innerHTML = `<div class="card${indentClass}" data-display="${layoutSize}">${html}</div>`;
    if (this.$styles) this.shadowRoot.appendChild(this.$styles);
    this._rendered = true;

    this.#bindEvents();
    this[`${size}_mounted`]?.call(this);
  }


  /** ─────────────────────────────────────────── **/
  /**         Private Helpers                      **/
  /** ─────────────────────────────────────────── **/

  /** Bind event listeners to current shadow DOM contents. */
  #bindEvents() {
    // Edit button
    this.shadowRoot.querySelector('.edit-btn')?.addEventListener('click', () => this.toggleMode());

    // Delete button
    this.shadowRoot.querySelector('.delete-btn')?.addEventListener('click', (e) => {
      e.stopPropagation();
      this.deleteItem();
    });

    // Input changes
    this.shadowRoot.querySelectorAll('input, textarea').forEach(el => {
      const event = (el.type === 'checkbox') ? 'change' : 'input';
      el.addEventListener(event, e => this.handleInputChange(e));
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
      });
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
        // nested URL like /products/1/comments/3) after the $id fix.
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
      btn.addEventListener('click', (ev) => { ev.stopPropagation(); submit(); });
      input.addEventListener('keydown', (ev) => {
        if (ev.key === 'Enter') { ev.preventDefault(); submit(); }
        if (ev.key === 'Escape') replyBox.remove();
      });
    });

    // Card click → SELECT (skip interactive elements and edit mode)
    if (this.mode !== 'edit') {
      this.shadowRoot.querySelector('.card')?.addEventListener('click', (e) => {
        if (e.target.closest('button, input, textarea, select, a, ntt-method, .reply-input-box')) return;
        const target = this.getAttribute('select-target');
        if (target) {
          this.send(new TX({
            name: 'SELECT', source: this.addr, target: target, data: this.ref
          }));
        }
      });
    }
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
    return DC?.schema?.ui?.renderer?.item || 'ntt-item';
  }

  /** Build HTML for standalone method buttons (those without ui.attach_to). */
  #standaloneMethodsHtml(methods) {
    return Object.entries(methods).map(([name, def]) => {
      const label = def.title || name;
      const ui = def.ui || {};
      return `
        <ntt-method
          model="${this.schema?.__name__ || ''}"
          uuid="${this.value?.id || ''}"
          method="${name}"
          layout="${ui.layout || 'fieldset'}"
          icon="${ui.icon || ''}"
          count-field="${ui.count_field || ''}"
          label="${label}">
        </ntt-method>
      `;
    }).join('');
  }
}

customElements.define('ntt-item', NTTItem);
