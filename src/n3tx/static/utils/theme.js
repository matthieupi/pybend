/**
 * Theme manager — dark/light toggle with localStorage persistence.
 *
 * Auto-applies the saved theme on import to prevent FOUC.
 * Dispatches 'theme-change' CustomEvent on document when theme changes.
 */

const STORAGE_KEY = 'ntx-theme';
const DEFAULT_THEME = 'dark';

/** @returns {'dark'|'light'} */
export function getTheme() {
    return localStorage.getItem(STORAGE_KEY) || DEFAULT_THEME;
}

/** @param {'dark'|'light'} theme */
export function setTheme(theme) {
    localStorage.setItem(STORAGE_KEY, theme);
    document.documentElement.dataset.theme = theme;
    document.dispatchEvent(new CustomEvent('theme-change', { detail: { theme } }));
}

/** Toggle between dark and light. */
export function toggleTheme() {
    setTheme(getTheme() === 'dark' ? 'light' : 'dark');
}

// Auto-apply on import — runs before first paint if script is in <head>
const saved = getTheme();
if (saved !== DEFAULT_THEME) {
    document.documentElement.dataset.theme = saved;
}
