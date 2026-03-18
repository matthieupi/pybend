/**
 * <ntx-agent> — Purpose-built agent entity component.
 *
 * Renders AgentActor instances with rich display:
 *   - xs: robot icon + agent name pill
 *   - sm: compact row with LLM badge and tools count
 *   - md (display): header, prompt preview, tool chips, embedded ntx-agent-live
 *   - md (edit): standard Formidable form via super.md()
 *   - lg: detail view — full prompt (no truncation) + activity panel
 *   - xl: page view — full prompt + constraints JSON + expanded activity panel
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

  /**
   * lg — Detail: full-bleed hero banner + full prompt + colorful tool chips.
   * card-actions floats absolute at top-right over the hero (ntx-item.css).
   */
  lg() {
    if (this.mode === 'edit') return super.md();
    return [
      this.renderCardActions(),
      this.renderHero(),
      this.renderPromptFull(),
      this.renderToolsColored(),
      this.renderActivity(),
    ].join('');
  }

  /**
   * xl — Page: hero + 2-column grid (prompt | constraints) + colored chips + activity.
   * card-actions floats absolute at top-right over the hero (ntx-item.css).
   */
  xl() {
    if (this.mode === 'edit') return super.md();
    return [
      this.renderCardActions(),
      this.renderHero(),
      `<div class="agent-xl-cols">
        <div class="agent-xl-col">${this.renderPromptFull()}</div>
        <div class="agent-xl-col">${this.renderConstraintsKV()}</div>
      </div>`,
      this.renderToolsColored(),
      this.renderActivity(),
    ].join('');
  }

  /** Post-render hook: wire prompt expand/collapse toggle (md only). */
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

  /**
   * Full-bleed hero banner for lg/xl.
   * Uses negative margins (same trick as .card-image in ntx-item.css) to
   * break out of the card padding and stretch edge-to-edge. The gradient
   * is derived from the LLM provider via _providerColor().
   */
  renderHero() {
    const { provider, model } = this._parseLlm(this.value.llm || '');
    const colors = this._providerColor(provider);
    const name = this._esc(this.value.name || this.schema.__name__);
    const toolCount = Array.isArray(this.value.tools) ? this.value.tools.length : 0;
    return `
      <div class="agent-hero" style="background: ${colors.gradient}">
        <div class="agent-hero-glyph">\uD83E\uDD16</div>
        <div class="agent-hero-content">
          <div class="agent-hero-name" data-value="name">${name}</div>
          <div class="agent-hero-badges">
            ${provider ? `<span class="badge-provider" style="background:${colors.dim};color:${colors.accent}">${this._esc(provider)}</span>` : ''}
            ${model ? `<span class="badge-model">${this._esc(model)}</span>` : ''}
            <span class="badge-tools" style="color:${colors.accent}">\u2699 ${toolCount} tools</span>
          </div>
        </div>
      </div>`;
  }

  /**
   * Tool chips with per-chip hue rotation, anchored to the provider's base hue.
   * Used by lg() and xl() for visual variety.
   */
  renderToolsColored() {
    const tools = Array.isArray(this.value.tools) ? this.value.tools : [];
    if (tools.length === 0) {
      return `<div class="agent-tools-colored"><span class="agent-no-tools">No tools</span></div>`;
    }
    const { provider } = this._parseLlm(this.value.llm || '');
    const baseHue = { anthropic: 270, ollama: 160, openai: 200, groq: 240, google: 45 }[provider] ?? 195;
    const chips = tools.map((href, i) => {
      const hue = (baseHue + i * 43) % 360;
      const label = this._toolName(href);
      return `<span class="tool-chip-colored" style="--ch:${hue}">${this._esc(label)}</span>`;
    }).join('');
    return `<div class="agent-tools-colored">${chips}</div>`;
  }

  /**
   * Constraints rendered as a colored key-value table.
   * Used by xl() in the right column of the 2-column grid.
   * Shows "None set" when constraints is empty so the column isn't blank.
   */
  renderConstraintsKV() {
    const c = this.value.constraints;
    if (!c || Object.keys(c).length === 0) {
      return `
        <div class="agent-constraints">
          <div class="section-label">Constraints</div>
          <span class="agent-no-constraints">None set</span>
        </div>`;
    }
    const { provider } = this._parseLlm(this.value.llm || '');
    const colors = this._providerColor(provider);
    const rows = Object.entries(c).map(([k, v]) => {
      const val = typeof v === 'object' ? JSON.stringify(v) : String(v);
      return `<tr>
        <td class="kv-key" style="color:${colors.accent}">${this._esc(k)}</td>
        <td class="kv-val">${this._esc(val)}</td>
      </tr>`;
    }).join('');
    return `
      <div class="agent-constraints">
        <div class="section-label">Constraints</div>
        <table class="agent-kv-table">${rows}</table>
      </div>`;
  }

  /**
   * System prompt shown in full — no line-clamp, no collapse toggle.
   * Used by lg() and xl() where there is room to show the whole prompt.
   */
  renderPromptFull() {
    const prompt = this.value.prompt || '';
    if (!prompt) return '';
    return `
      <div class="agent-prompt">
        <div class="section-label">Prompt</div>
        <div class="agent-prompt-text agent-prompt-full">${this._esc(prompt)}</div>
      </div>`;
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

  /**
   * Gradient + accent color for a given LLM provider.
   * Used by renderHero() and renderConstraintsKV() to theme by provider.
   */
  _providerColor(provider) {
    const map = {
      anthropic: { gradient: 'linear-gradient(135deg,#3b1a6b 0%,#6d28d9 100%)', accent: '#a78bfa', dim: 'rgba(167,139,250,.2)' },
      ollama:    { gradient: 'linear-gradient(135deg,#064e3b 0%,#065f46 100%)', accent: '#34d399', dim: 'rgba(52,211,153,.2)' },
      openai:    { gradient: 'linear-gradient(135deg,#0c4a6e 0%,#0369a1 100%)', accent: '#38bdf8', dim: 'rgba(56,189,248,.2)' },
      groq:      { gradient: 'linear-gradient(135deg,#1e1b4b 0%,#3730a3 100%)', accent: '#818cf8', dim: 'rgba(129,140,248,.2)' },
      google:    { gradient: 'linear-gradient(135deg,#1a1200 0%,#92400e 100%)', accent: '#fbbf24', dim: 'rgba(251,191,36,.2)' },
    };
    return map[provider] ?? { gradient: 'linear-gradient(135deg,#0f3460 0%,#16213e 100%)', accent: '#4cc9f0', dim: 'rgba(76,201,240,.2)' };
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
    /* ── Hero banner (lg / xl) ── */
    .agent-hero {
      /* md fallback margins — overridden per card size below */
      margin: -1.5rem -1.75rem 1.25rem;
      padding: 1.25rem 1.75rem;
      display: flex; align-items: center; gap: .85rem;
      border-radius: var(--radius-lg, 16px) var(--radius-lg, 16px) 0 0;
      min-height: 82px;
      position: relative;
    }
    .card[data-display="lg"] .agent-hero {
      margin: -2rem -2.25rem 1.5rem;
      padding: 1.5rem 2.25rem;
      min-height: 92px;
    }
    .card[data-display="xl"] .agent-hero {
      margin: -2.5rem -3rem 1.75rem;
      padding: 1.75rem 3rem;
      min-height: 108px;
    }
    .agent-hero-glyph {
      font-size: 2.2rem; flex-shrink: 0;
      filter: drop-shadow(0 2px 6px rgba(0,0,0,.5));
    }
    .card[data-display="xl"] .agent-hero-glyph { font-size: 2.8rem; }
    .agent-hero-name {
      font-size: 1.3rem; font-weight: 700;
      color: #fff; text-shadow: 0 1px 6px rgba(0,0,0,.5);
    }
    .card[data-display="xl"] .agent-hero-name { font-size: 1.6rem; }
    .agent-hero-badges {
      display: flex; gap: .4rem; flex-wrap: wrap; margin-top: .35rem;
    }

    /* ── xl 2-column grid ── */
    .agent-xl-cols {
      display: grid; grid-template-columns: 1fr 1fr; gap: 1.25rem;
      margin-bottom: .5rem;
    }
    .agent-xl-col { min-width: 0; }

    /* ── Colorful tool chips (lg / xl) ── */
    .agent-tools-colored {
      display: flex; flex-wrap: wrap; gap: .4rem; margin-top: .5rem;
    }
    .tool-chip-colored {
      display: inline-flex; align-items: center;
      padding: .2rem .55rem;
      background: hsl(var(--ch), 40%, 10%);
      border: 1px solid hsl(var(--ch), 55%, 28%);
      border-radius: .3rem;
      font-size: .75rem; font-weight: 500;
      color: hsl(var(--ch), 70%, 65%);
      white-space: nowrap;
    }

    /* ── Constraints KV table (xl right column) ── */
    .agent-constraints { height: 100%; }
    .agent-kv-table {
      width: 100%; border-collapse: collapse; font-size: .78rem;
      margin-top: .1rem;
    }
    .kv-key {
      font-weight: 600; padding: .3rem .6rem .3rem 0;
      white-space: nowrap; vertical-align: top; width: 42%;
    }
    .kv-val {
      color: var(--text-1, #eee); padding: .3rem 0;
      word-break: break-word; vertical-align: top;
    }
    .agent-kv-table tr + tr td { border-top: 1px solid var(--glass-border, rgba(255,255,255,.06)); }
    .agent-no-constraints {
      color: var(--text-3, #666); font-style: italic; font-size: .75rem;
    }

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
    /* lg/xl: full prompt — no clamp */
    .agent-prompt-full {
      display: block; overflow: visible; cursor: default;
      -webkit-line-clamp: unset;
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
