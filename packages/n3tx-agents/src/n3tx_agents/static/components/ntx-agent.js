/**
 * <ntx-agent> — Purpose-built agent entity component.
 *
 * Renders AgentActor instances with rich display:
 *   - xs: robot icon + agent name pill
 *   - sm: compact row with LLM badge and tools count
 *   - md (display): header, prompt preview, tool chips, embedded ntx-agent-live
 *   - md (edit): standard Formidable form via super.md()
 *
 * Subclass and override individual section renderers to customize
 * specific sections without rebuilding the whole card.
 *
 * Usage:
 *   <ntx-list model="AgentActor" item-tag="ntx-agent"></ntx-list>
 *   <ntx-agent ref="agents/1"></ntx-agent>
 */
import { NTTItem } from './ntx-item.js';
import { permissions } from '../utils/Permissions.js';
import './ntx-agent-live.js';   // ensure registered


export class NtxAgent extends NTTItem {

  /**
   * Append agent-specific stylesheet after every render.
   * adoptedStyleSheets survives shadowRoot.innerHTML reassignment,
   * so this is the correct hook point.
   */
  render() {
    super.render();
    if (!NtxAgent._agentSheet) {
      NtxAgent._agentSheet = new CSSStyleSheet();
      NtxAgent._agentSheet.replaceSync(NtxAgent.agentStyles);
    }
    const sheets = this.shadowRoot.adoptedStyleSheets;
    if (!sheets.includes(NtxAgent._agentSheet)) {
      this.shadowRoot.adoptedStyleSheets = [...sheets, NtxAgent._agentSheet];
    }
  }


  /** ─────────────────────────────────────────── **/
  /**         Size Methods                         **/
  /** ─────────────────────────────────────────── **/

  /** xs — robot icon + agent name pill. */
  xs() {
    const name = this._esc(this.value.name || 'Agent');
    return `<span class="pill-label" data-value="name">\uD83E\uDD16 ${name}</span>`;
  }

  /** sm — compact row: robot glyph + name + LLM badges + tools count. */
  sm() {
    if (this.mode === 'edit') return super.md();

    const schema = this.schema;
    const canUpdate = permissions.canAction(schema.access, 'update', this.value);
    const canDelete = permissions.canAction(schema.access, 'delete', this.value);
    let actionsHtml = '';
    if (canUpdate || canDelete) {
      let btns = '';
      if (canDelete) btns += '<button class="delete-btn" title="Delete"></button>';
      if (canUpdate) {
        btns += '<button class="edit-btn mode-display" title="Edit"></button>';
      }
      actionsHtml = `<span class="sm-actions">${btns}</span>`;
    }

    const name = this._esc(this.value.name || schema.__name__);
    const { provider, model } = this._parseLlm(this.value.llm || '');
    const toolCount = Array.isArray(this.value.tools) ? this.value.tools.length : 0;

    return `
      <div class="agent-sm-icon">\uD83E\uDD16</div>
      <div class="sm-body">
        <span class="sm-name" data-value="name">${name}</span>
        <span class="sm-fields">
          ${provider ? `<span class="badge-provider">${this._esc(provider)}</span>` : ''}
          ${model ? `<span class="badge-model">${this._esc(model)}</span>` : ''}
          <span class="badge-tools">\u2699 ${toolCount}</span>
        </span>
      </div>
      ${actionsHtml}
    `;
  }

  /** md — full agent card. Edit mode delegates to super.md() (Formidable form). */
  md() {
    if (this.mode === 'edit') return super.md();
    return [
      this.renderCardActions(),
      this.renderHeader(),
      this.renderPrompt(),
      this.renderTools(),
      this.renderActivity(),
    ].join('');
  }

  /** Post-render hook: wire prompt expand/collapse toggle. */
  md_mounted() {
    const el = this.shadowRoot.querySelector('.agent-prompt-text');
    if (!el) return;
    el.addEventListener('click', () => {
      const collapsed = el.dataset.collapsed !== 'false';
      el.dataset.collapsed = collapsed ? 'false' : 'true';
    });
  }


  /** ─────────────────────────────────────────── **/
  /**         Section Renderers                    **/
  /** ─────────────────────────────────────────── **/

  /**
   * Edit / delete action buttons.
   * Uses the same class names (.edit-btn, .delete-btn, .cancel-btn) that
   * NTTItem's #bindEvents() listens for — so toggleMode(), cancelEdit(),
   * and deleteItem() all wire up automatically after render.
   */
  renderCardActions() {
    const schema = this.schema;
    const canUpdate = permissions.canAction(schema.access, 'update', this.value);
    const canDelete = permissions.canAction(schema.access, 'delete', this.value);
    if (!canUpdate && !canDelete) return '';
    let btns = '';
    if (canDelete) btns += '<button class="delete-btn" title="Delete"></button>';
    if (canUpdate) {
      if (this.mode === 'edit') {
        btns += '<button class="cancel-btn" title="Cancel"></button>';
      }
      const modeClass = this.mode === 'edit' ? 'mode-edit' : 'mode-display';
      btns += `<button class="edit-btn ${modeClass}" title="${this.mode === 'edit' ? 'Save' : 'Edit'}"></button>`;
    }
    return `<div class="card-actions">${btns}</div>`;
  }

  /** Agent name headline + LLM provider/model badges + tools count. */
  renderHeader() {
    const name = this._esc(this.value.name || this.schema.__name__);
    const { provider, model } = this._parseLlm(this.value.llm || '');
    const toolCount = Array.isArray(this.value.tools) ? this.value.tools.length : 0;
    return `
      <div class="agent-header">
        <div class="agent-name" data-value="name">${name}</div>
        <div class="agent-badges">
          ${provider ? `<span class="badge-provider">${this._esc(provider)}</span>` : ''}
          ${model ? `<span class="badge-model">${this._esc(model)}</span>` : ''}
          <span class="badge-tools">\u2699 ${toolCount} tools</span>
        </div>
      </div>`;
  }

  /** System prompt in a collapsible pre-formatted box. */
  renderPrompt() {
    const prompt = this.value.prompt || '';
    if (!prompt) return '';
    return `
      <div class="agent-prompt">
        <div class="section-label">Prompt</div>
        <div class="agent-prompt-text" data-collapsed="true">${this._esc(prompt)}</div>
      </div>`;
  }

  /**
   * Tool chips derived from the tools ListRef array.
   * Each element is an href string (e.g. "http://.../agent_tools/3").
   * _toolName() extracts a human-readable label.
   */
  renderTools() {
    const tools = Array.isArray(this.value.tools) ? this.value.tools : [];
    if (tools.length === 0) {
      return `<div class="agent-tools-row"><span class="agent-no-tools">No tools</span></div>`;
    }
    const chips = tools.map(href => {
      const label = this._toolName(href);
      return `<span class="tool-chip">${this._esc(label)}</span>`;
    }).join('');
    return `<div class="agent-tools-row">${chips}</div>`;
  }

  /** Embedded ntx-agent-live panel pre-scoped to this agent's ref. */
  renderActivity() {
    const tablename = this.schema.__tablename__;
    const ref = `${tablename}/${this.value.id}`;
    return `
      <div class="agent-activity-section">
        <div class="section-label">Activity</div>
        <ntx-agent-live model="${this.schema.__name__}" ref="${ref}" method="agentic_stream"></ntx-agent-live>
      </div>`;
  }


  /** ─────────────────────────────────────────── **/
  /**         Helpers                              **/
  /** ─────────────────────────────────────────── **/

  /** Split "provider:model" LLM string into parts. */
  _parseLlm(llm) {
    if (!llm) return { provider: '', model: '' };
    const idx = llm.indexOf(':');
    if (idx === -1) return { provider: '', model: llm };
    return { provider: llm.slice(0, idx), model: llm.slice(idx + 1) };
  }

  /**
   * Extract a human-readable label from a tool href.
   * Plain addr string (e.g. "grants") → shown as-is.
   * URL href (e.g. ".../agent_tools/3") → "⚙ #3".
   */
  _toolName(href) {
    if (typeof href !== 'string') return String(href);
    if (!href.includes('/')) return href;
    const parts = href.replace(/\/$/, '').split('/');
    return `\u2699 #${parts[parts.length - 1]}`;
  }

  /** HTML-escape a string. */
  _esc(t) {
    const d = document.createElement('div');
    d.textContent = String(t ?? '');
    return d.innerHTML;
  }


  /** ─────────────────────────────────────────── **/
  /**         Agent-Specific Styles               **/
  /** ─────────────────────────────────────────── **/

  static agentStyles = `
    /* sm icon */
    .agent-sm-icon {
      font-size: 1.2rem; flex-shrink: 0; margin-right: .3rem;
    }

    /* md header */
    .agent-header {
      display: flex; flex-direction: row; align-items: center;
      justify-content: space-between; gap: .5rem; flex-wrap: wrap;
      margin-bottom: .5rem;
    }
    .agent-name {
      font-size: 1.1rem; font-weight: 600; color: var(--text-0, #f0f0f0);
    }
    .agent-badges {
      display: flex; gap: .4rem; flex-wrap: wrap; align-items: center;
    }

    /* LLM + tools badges */
    .badge-provider, .badge-model, .badge-tools {
      display: inline-block; padding: .15rem .45rem;
      border-radius: 999px; font-size: .65rem; font-weight: 600;
      letter-spacing: .03em; white-space: nowrap;
    }
    .badge-provider {
      background: var(--accent-dim, rgba(76,201,240,.15));
      color: var(--accent, #4cc9f0); text-transform: uppercase;
    }
    .badge-model {
      background: var(--surface-3, #0f3460); color: var(--text-2, #aaa);
    }
    .badge-tools {
      background: var(--surface-3, #0f3460); color: var(--text-2, #aaa);
    }

    /* Prompt box */
    .agent-prompt { margin-top: .75rem; }
    .section-label {
      font-size: .65rem; text-transform: uppercase; letter-spacing: .05em;
      color: var(--text-3, #666); margin-bottom: .3rem;
    }
    .agent-prompt-text {
      font-size: .8rem; color: var(--text-2, #aaa);
      white-space: pre-wrap; word-break: break-word;
      display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical;
      overflow: hidden; cursor: pointer;
    }
    .agent-prompt-text[data-collapsed="false"] {
      display: block; overflow: visible;
    }

    /* Tool chips */
    .agent-tools-row {
      display: flex; flex-wrap: wrap; gap: .3rem; margin-top: .5rem;
    }
    .tool-chip {
      display: inline-block; padding: .15rem .4rem;
      background: var(--surface-3, #0f3460);
      border-left: 2px solid var(--accent-dim, rgba(76,201,240,.3));
      border-radius: 0 .25rem .25rem 0;
      font-size: .7rem; color: var(--text-2, #aaa);
    }
    .agent-no-tools {
      color: var(--text-3, #666); font-style: italic; font-size: .75rem;
    }

    /* Activity section */
    .agent-activity-section {
      margin-top: .75rem;
      border-top: 1px solid var(--glass-border, rgba(255,255,255,.08));
      padding-top: .5rem;
    }
    ntx-agent-live { display: block; }
  `;
}

customElements.define('ntx-agent', NtxAgent);
