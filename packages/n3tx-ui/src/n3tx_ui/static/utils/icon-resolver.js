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

function normalizeRegistryValue(value) {
  if (value && typeof value === 'object' && value.kind === 'svg') {
    return svgIcon(value.body || value.value, value);
  }
  return String(value || '').trim();
}

const _registry = new Map([
  ['dashboard', svgIcon('<rect x="3" y="3" width="7" height="9" rx="1" /><rect x="14" y="3" width="7" height="5" rx="1" /><rect x="14" y="12" width="7" height="9" rx="1" /><rect x="3" y="16" width="7" height="5" rx="1" />')],
  ['heart', svgIcon('<path d="m20.84 4.61-1.45-1.45a5.5 5.5 0 0 0-7.78 0L12 3.56l.39-.4a5.5 5.5 0 0 0-7.78 7.78l1.45 1.45L12 18.33l5.94-5.94 1.45-1.45a5.5 5.5 0 0 0 0-7.78Z" />')],
  ['star', svgIcon('<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />')],
  ['reply', svgIcon('<polyline points="9 17 4 12 9 7" /><path d="M20 18v-2a4 4 0 0 0-4-4H4" />')],
  ['upload', svgIcon('<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" />')],
  ['user', svgIcon('<path d="M20 21a8 8 0 0 0-16 0" /><circle cx="12" cy="7" r="4" />')],
]);

const PATH_PREFIX = /^(https?:\/\/|\/|\.\/?|\.\.\/)/i;
const FILE_SUFFIX = /\.(svg|png|jpg|jpeg|webp)(\?.*)?$/i;
const EMOJI_PATTERN = /[\p{Extended_Pictographic}\uFE0F]/u;

function escapeAttr(value = '') {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function looksLikePath(value) {
  return PATH_PREFIX.test(value) || FILE_SUFFIX.test(value);
}

function looksLikeEmoji(value) {
  return EMOJI_PATTERN.test(value);
}

export function registerIcons(entries = {}) {
  for (const [key, value] of Object.entries(entries)) {
    const name = String(key || '').trim();
    if (!name) continue;
    if (value == null || value === '') _registry.delete(name);
    else _registry.set(name, normalizeRegistryValue(value));
  }
}

export function resolveIcon(value) {
  const raw = String(value || '').trim();
  if (!raw) return null;

  const resolved = _registry.get(raw) || raw;
  const source = _registry.has(raw) ? 'registry' : 'direct';

  if (resolved && typeof resolved === 'object' && resolved.kind === 'svg' && resolved.body) {
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

export function iconMarkup(value, options = {}) {
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
