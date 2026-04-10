import { registerIcons } from './icon-resolver.js';

const line = (body, options = {}) => ({
  kind: 'svg',
  body,
  strokeWidth: '1.85',
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  ...options,
});

const solid = (body, options = {}) => ({
  kind: 'svg',
  body,
  fill: 'currentColor',
  stroke: 'none',
  ...options,
});

registerIcons({
  'veille-source': line(
    '<path d="M7.5 3.5h7L19 8v11.5a1.5 1.5 0 0 1-1.5 1.5h-10A1.5 1.5 0 0 1 6 19.5V5a1.5 1.5 0 0 1 1.5-1.5Z" /><path d="M14 3.5V8h5" /><path d="M9 12h6" /><path d="M9 15.5h6" />'
  ),
  'veille-grant': line(
    '<rect x="4" y="7" width="16" height="10" rx="2.5" /><circle cx="12" cy="12" r="2.25" />'
  ),
  'veille-analyze': line(
    '<circle cx="10.5" cy="10.5" r="5.5" /><path d="m15 15 4.5 4.5" /><path d="M10.5 8.5v4" /><path d="M8.5 10.5h4" />'
  ),
  'veille-run': line(
    '<circle cx="12" cy="13" r="7" /><path d="M12 13V9.5" /><path d="m12 13 2.5 2.5" /><path d="M12 4V2.5" />'
  ),
  'veille-execute': solid(
    '<path d="m8 7 9 5-9 5Z" />',
    { viewBox: '0 0 24 24' }
  ),
  'veille-adhoc': line(
    '<path d="M9 3h6" /><path d="M10 3v5l-4.5 7.5A2.5 2.5 0 0 0 7.7 19h8.6a2.5 2.5 0 0 0 2.2-3.5L14 8V3" /><path d="M8.5 13h7" />'
  ),
  'veille-organization': line(
    '<path d="M4 21V8l8-4 8 4v13" /><path d="M10 21v-4h4v4" /><path d="M8 11h8" /><path d="M8 14h8" />'
  ),
  'veille-user': line(
    '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" />'
  ),
  'veille-tools': line(
    '<path d="M14.5 6.5a4 4 0 0 1-5 5L5 16l3 3 4.5-4.5a4 4 0 0 0 5-5L15 12l-3-3Z" />'
  ),
  'veille-search': line(
    '<circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" />'
  ),
  'veille-dashboard': line(
    '<path d="M4 19h16" /><path d="M7 16v-5" /><path d="M12 16V7" /><path d="M17 16V9" />'
  ),
  'veille-registry': line(
    '<ellipse cx="12" cy="5" rx="7" ry="3" /><path d="M5 5v6c0 1.7 3.1 3 7 3s7-1.3 7-3V5" /><path d="M5 11v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6" />'
  ),
  'veille-new-pipeline': line(
    '<circle cx="12" cy="12" r="8" /><path d="M12 8v8" /><path d="M8 12h8" />'
  ),
  'veille-bolt': solid(
    '<path d="M13 2 4 14h6l-1 8 9-12h-6l1-8Z" />',
    { viewBox: '0 0 24 24' }
  ),
  'veille-chart': line(
    '<path d="M4 19V5" /><path d="M10 19V9" /><path d="M16 19v-6" /><path d="M22 19V7" />'
  ),
  'veille-arrow-right': line(
    '<path d="M5 12h14" /><path d="m13 6 6 6-6 6" />'
  ),
  'veille-insight': line(
    '<path d="m12 4 1.6 4.4L18 10l-4.4 1.6L12 16l-1.6-4.4L6 10l4.4-1.6L12 4Z" /><path d="M19 4v3" /><path d="M20.5 5.5h-3" />'
  ),
  'veille-empty': line(
    '<path d="M6 8.5h12" /><path d="M8 5.5h8l2 3H6Z" /><path d="M6 8.5V19a1.5 1.5 0 0 0 1.5 1.5h9A1.5 1.5 0 0 0 18 19V8.5" /><path d="M9 12h6" />'
  ),
  'veille-open': line(
    '<path d="M7 17 17 7" /><path d="M9 7h8v8" />'
  ),
  'veille-sector-energy': line(
    '<path d="M7 16c0-5 3.5-8.5 10-10-1 6.5-5 10-10 10Z" /><path d="M7 16c2-2 4.5-4 7.5-6" />'
  ),
  'veille-sector-digital': line(
    '<rect x="7" y="7" width="10" height="10" rx="2" /><path d="M9 3v2" /><path d="M15 3v2" /><path d="M9 19v2" /><path d="M15 19v2" /><path d="M19 9h2" /><path d="M19 15h2" /><path d="M3 9h2" /><path d="M3 15h2" />'
  ),
  'veille-sector-industrial': line(
    '<path d="M4 20V8l5 3V8l5 3V6l6 4v10" /><path d="M8 20v-4h4v4" />'
  ),
  'veille-sector-default': line(
    '<path d="m12 6 1.4 3.6L17 11l-3.6 1.4L12 16l-1.4-3.6L7 11l3.6-1.4L12 6Z" />'
  ),
});
