const _registry = new Map([
  ['heart', '❤️'],
  ['star', '⭐'],
  ['reply', '↩️'],
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
    else _registry.set(name, String(value).trim());
  }
}

export function resolveIcon(value) {
  const raw = String(value || '').trim();
  if (!raw) return null;

  const resolved = _registry.get(raw) || raw;
  const source = _registry.has(raw) ? 'registry' : 'direct';

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
