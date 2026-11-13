/** @file Shared native icon registry and value resolution for ntx-icon.
 * API: registerIcons adds trusted definitions; resolveIcon returns render data;
 * iconMarkup emits escaped native element attributes. SVG definitions are
 * trusted code-owned data, never user-provided markup. Native ntx-icon owns
 * rendering, accessibility and sizing; consumers select names or direct values.
 * Usage: <ntx-icon value="search" decorative></ntx-icon>. */

/** Normalize a trusted SVG definition with native presentation defaults.
 * @param {*} body Trusted SVG inner markup.
 * @param {Object} [options={}] SVG presentation settings.
 * @param {string} [options.viewBox='0 0 24 24'] Coordinate system.
 * @param {string} [options.fill='none'] Default fill.
 * @param {string} [options.stroke='currentColor'] Default stroke.
 * @param {string} [options.strokeWidth='2'] Stroke width.
 * @param {string} [options.strokeLinecap='round'] Line-end style.
 * @param {string} [options.strokeLinejoin='round'] Corner style.
 * @returns {Object} Normalized trusted SVG definition. */
function svgIcon(body, options = {}) {
  return {
    kind: 'svg',
    body: String(body || '').trim(),
    viewBox: String(options.viewBox || '0 0 24 24').trim(),
    fill: String(options.fill || 'none').trim(),
    stroke: String(options.stroke || 'currentColor').trim(),
    strokeWidth: String(options.strokeWidth || '2').trim(),
    strokeLinecap: String(options.strokeLinecap || 'round').trim(),
    strokeLinejoin: String(options.strokeLinejoin || 'round').trim(),
  };
}


/** Retain a normalized trusted SVG definition or direct icon value.
 * @param {*} value Registry definition or value.
 * @returns {Object|string} Normalized definition or trimmed value. */
function normalizeRegistryValue(value) {
  if (value && typeof value === 'object' && value.kind === 'svg') {
    return svgIcon(value.body || value.value, value);
  }
  return String(value || '').trim();
}

const _registry = new Map([
  ['dashboard', svgIcon(
    '<rect x="3" y="3" width="7" height="9" rx="1" />' +
    '<rect x="14" y="3" width="7" height="5" rx="1" />' +
    '<rect x="14" y="12" width="7" height="9" rx="1" />' +
    '<rect x="3" y="16" width="7" height="5" rx="1" />',
  )],
  ['heart', svgIcon(
    '<path d="m20.84 4.61-1.45-1.45a5.5 5.5 0 0 0-7.78 0L12 3.56l.39-.4' +
    'a5.5 5.5 0 0 0-7.78 7.78l1.45 1.45L12 18.33l5.94-5.94 1.45-1.45' +
    'a5.5 5.5 0 0 0 0-7.78Z" />',
  )],
  ['star', svgIcon(
    '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 ' +
    '12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />',
  )],
  ['reply', svgIcon(
    '<polyline points="9 17 4 12 9 7" />' +
    '<path d="M20 18v-2a4 4 0 0 0-4-4H4" />',
  )],
  ['upload', svgIcon(
    '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />' +
    '<polyline points="17 8 12 3 7 8" />' +
    '<line x1="12" y1="3" x2="12" y2="15" />',
  )],
  ['user', svgIcon(
    '<path d="M20 21a8 8 0 0 0-16 0" />' +
    '<circle cx="12" cy="7" r="4" />',
  )],
  ['search', svgIcon(
    '<circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />',
  )],
  ['download', svgIcon(
    '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />' +
    '<polyline points="7 10 12 15 17 10" />' +
    '<line x1="12" y1="3" x2="12" y2="15" />',
  )],
]);

const PATH_PREFIX = /^(https?:\/\/|\/|\.\/?|\.\.\/)/i;
const FILE_SUFFIX = /\.(svg|png|jpg|jpeg|webp)(\?.*)?$/i;
const EMOJI_PATTERN = /[\p{Extended_Pictographic}\uFE0F]/u;


/** Escape a value for a double-quoted HTML attribute.
 * @param {*} [value=''] Attribute value.
 * @returns {string} Escaped value. */
function escapeAttr(value = '') {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}


/** Recognize supported image paths or URLs without fetching them.
 * @param {string} value Resolved icon value.
 * @returns {boolean} Whether the value has image-path syntax. */
function looksLikePath(value) {
  return PATH_PREFIX.test(value) || FILE_SUFFIX.test(value);
}


/** Recognize pictographic characters for native emoji presentation.
 * @param {string} value Resolved icon value.
 * @returns {boolean} Whether the value contains an emoji marker. */
function looksLikeEmoji(value) {
  return EMOJI_PATTERN.test(value);
}


/** Register trusted icon definitions, removing explicitly empty entries.
 * @param {Object<string, *>} [entries={}] Named trusted definitions.
 * @returns {void} */
export function registerIcons(entries = {}) {
  // 0. Normalize definitions without treating registry content as user markup.
  for (const [key, value] of Object.entries(entries)) {
    const name = String(key || '').trim();
    if (!name) continue;
    if (value == null || value === '') _registry.delete(name);
    else _registry.set(name, normalizeRegistryValue(value));
  }
}


/** Resolve a registered name or direct value without loading resources.
 * @param {*} value Icon name, SVG registry key, path, emoji or fallback text.
 * @returns {?Object} Native render data, or null for an empty value. */
export function resolveIcon(value) {
  // 0. Resolve trusted registry entries before direct-value classification.
  const raw = String(value || '').trim();
  if (!raw) return null;

  const resolved = _registry.get(raw) || raw;
  const source = _registry.has(raw) ? 'registry' : 'direct';

  if (resolved && typeof resolved === 'object' &&
      resolved.kind === 'svg' && resolved.body) {
    return {
      kind: 'svg',
      value: resolved.body,
      viewBox: resolved.viewBox,
      fill: resolved.fill,
      stroke: resolved.stroke,
      strokeWidth: resolved.strokeWidth,
      strokeLinecap: resolved.strokeLinecap,
      strokeLinejoin: resolved.strokeLinejoin,
      source,
      raw,
    };
  }

  if (looksLikePath(resolved)) {
    return { kind: 'image', value: resolved, source, raw };
  }

  if (looksLikeEmoji(resolved)) {
    return { kind: 'emoji', value: resolved, source, raw };
  }

  return { kind: 'text', value: resolved, source, raw };
}


/** Emit native icon markup while preserving renderer ownership.
 * @param {*} value Icon name or direct value.
 * @param {Object} [options={}] Accessibility and presentation attributes.
 * @param {string} [options.label] Accessible name.
 * @param {string} [options.title] Tooltip text.
 * @param {string} [options.className] Host CSS classes.
 * @param {boolean} [options.decorative=true] Hide artwork from assistive tools.
 * @returns {string} Escaped ntx-icon markup, or an empty string. */
export function iconMarkup(value, options = {}) {
  // 0. The component owns rendering; this helper emits only escaped attributes.
  const icon = resolveIcon(value);
  if (!icon) return '';

  const attrs = [
    `value="${escapeAttr(icon.raw)}"`,
  ];

  if (options.label) attrs.push(`label="${escapeAttr(options.label)}"`);
  if (options.title) attrs.push(`title="${escapeAttr(options.title)}"`);
  if (options.className) attrs.push(`class="${escapeAttr(options.className)}"`);
  if (options.decorative !== false) attrs.push('decorative');

  return `<ntx-icon ${attrs.join(' ')}></ntx-icon>`;
}

if (typeof window !== 'undefined') {
  window.registerIcons = registerIcons;
}

/* Changelog
 * - 2026-11-12: Add generic Search/Download SVGs without font dependencies;
 *   document native resolution and preserve existing registry values. */
