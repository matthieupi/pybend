import { buildRoute } from '../core/Router.js';
import { NTTItem } from './ntx-item.js';

const TOOLTIP_SHOW_DELAY_MS = 220;
const TOOLTIP_CLASS = 'ntx-sidebar-link-tooltip';

let sharedTooltipEl = null;
let sharedTooltipOwner = null;

function escapeHtml(value) {
  const node = document.createElement('div');
  node.textContent = String(value ?? '');
  return node.innerHTML;
}

function escapeAttr(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function ensureTooltipEl() {
  if (!sharedTooltipEl) {
    sharedTooltipEl = document.createElement('div');
    sharedTooltipEl.className = TOOLTIP_CLASS;
    Object.assign(sharedTooltipEl.style, {
      position: 'fixed',
      top: '0px',
      left: '0px',
      zIndex: '10000',
      maxWidth: 'min(22rem, calc(100vw - 2rem))',
      padding: '0.48rem 0.62rem',
      borderRadius: '10px',
      background: 'rgba(25, 28, 29, 0.96)',
      color: '#f8fafb',
      fontFamily: 'var(--ntx-font-body, Manrope, sans-serif)',
      fontSize: '0.74rem',
      fontWeight: '600',
      lineHeight: '1.35',
      letterSpacing: '0.01em',
      boxShadow: '0 16px 38px rgba(25, 28, 29, 0.18)',
      pointerEvents: 'none',
      whiteSpace: 'normal',
      overflowWrap: 'anywhere',
      opacity: '0',
      visibility: 'hidden',
      transform: 'translateY(-4px)',
      transition: 'opacity 120ms ease, transform 120ms ease, visibility 0s linear 120ms',
    });
  }
  if (!sharedTooltipEl.isConnected) document.body.appendChild(sharedTooltipEl);
  return sharedTooltipEl;
}

function hideSharedTooltip() {
  if (!sharedTooltipEl) return;
  sharedTooltipEl.style.opacity = '0';
  sharedTooltipEl.style.visibility = 'hidden';
  sharedTooltipEl.style.transform = 'translateY(-4px)';
  sharedTooltipEl.removeAttribute('data-open');
}

function positionTooltip(anchor, tooltip) {
  const rect = anchor.getBoundingClientRect();
  const margin = 12;
  const width = tooltip.offsetWidth || 220;
  const height = tooltip.offsetHeight || 44;
  const left = Math.max(margin, Math.min(rect.left, window.innerWidth - width - margin));
  const belowTop = rect.bottom + 10;
  const aboveTop = rect.top - height - 10;
  const top = belowTop + height + margin <= window.innerHeight
    ? belowTop
    : Math.max(margin, aboveTop);

  tooltip.style.left = `${left}px`;
  tooltip.style.top = `${top}px`;
}

export class NTTSidebarLinkItem extends NTTItem {
  #tooltipTimer = null;
  #tooltipAC = null;

  get styles() {
    const base = super.styles;
    return [
      ...(Array.isArray(base) ? base : [base]),
      new URL('./ntx-sidebar-link-item.css', import.meta.url).href,
    ];
  }

  sm() {
    const modelName = this.schema?.__name__ || this.model || this.getAttribute('data-model') || '';
    const id = this.value?.id ?? this.ref?.split('/').pop();
    const route = id != null
      ? buildRoute({ type: 'detail', model: modelName, id: String(id), isViewRoute: true })
      : buildRoute({ type: 'model', model: modelName, isViewRoute: true });
    const label = this.value?.name || this.value?.title || (id != null ? `#${id}` : modelName);
    const escapedLabel = escapeHtml(label);
    const escapedAttrLabel = escapeAttr(label);

    return `
      <a class="sidebar-record-link" href="#${route}" aria-label="${escapedAttrLabel}" data-tooltip="${escapedAttrLabel}">
        <span class="sidebar-record-label">${escapedLabel}</span>
      </a>
    `;
  }

  sm_mounted() {
    this.#tooltipAC?.abort();
    this.#tooltipAC = new AbortController();
    const { signal } = this.#tooltipAC;
    const link = this.shadowRoot.querySelector('.sidebar-record-link');
    if (!link) return;

    const show = () => this.#scheduleTooltip(link);
    const hide = () => this.#hideTooltip();

    link.addEventListener('mouseenter', show, { signal });
    link.addEventListener('mouseleave', hide, { signal });
    link.addEventListener('focus', show, { signal });
    link.addEventListener('blur', hide, { signal });
    link.addEventListener('click', hide, { signal });
    window.addEventListener('scroll', hide, { signal, passive: true });
    window.addEventListener('resize', hide, { signal });
  }

  disconnectedCallback() {
    this.#tooltipAC?.abort();
    this.#clearTooltipTimer();
    if (sharedTooltipOwner === this) {
      sharedTooltipOwner = null;
      hideSharedTooltip();
    }
    super.disconnectedCallback();
  }

  #clearTooltipTimer() {
    if (this.#tooltipTimer) {
      window.clearTimeout(this.#tooltipTimer);
      this.#tooltipTimer = null;
    }
  }

  #scheduleTooltip(link) {
    this.#clearTooltipTimer();
    if (!this.#isLabelTruncated(link)) {
      if (sharedTooltipOwner === this) {
        sharedTooltipOwner = null;
        hideSharedTooltip();
      }
      return;
    }

    this.#tooltipTimer = window.setTimeout(() => {
      this.#tooltipTimer = null;
      this.#showTooltip(link);
    }, TOOLTIP_SHOW_DELAY_MS);
  }

  #isLabelTruncated(link) {
    const label = link.querySelector('.sidebar-record-label');
    if (!label) return false;
    return label.scrollWidth > label.clientWidth + 1;
  }

  #showTooltip(link) {
    const tooltipText = link.getAttribute('data-tooltip') || link.textContent?.trim();
    if (!tooltipText) return;

    if (sharedTooltipOwner && sharedTooltipOwner !== this) {
      hideSharedTooltip();
    }
    sharedTooltipOwner = this;

    const tooltip = ensureTooltipEl();
    tooltip.textContent = tooltipText;
    tooltip.setAttribute('data-open', 'true');
    tooltip.style.visibility = 'hidden';
    tooltip.style.opacity = '0';
    tooltip.style.transform = 'translateY(-4px)';

    positionTooltip(link, tooltip);

    tooltip.style.visibility = 'visible';
    tooltip.style.opacity = '1';
    tooltip.style.transform = 'translateY(0)';
  }

  #hideTooltip() {
    this.#clearTooltipTimer();
    if (sharedTooltipOwner !== this) return;
    sharedTooltipOwner = null;
    hideSharedTooltip();
  }
}

customElements.define('ntx-sidebar-link-item', NTTSidebarLinkItem);
