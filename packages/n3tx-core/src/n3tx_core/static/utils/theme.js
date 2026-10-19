/**
 * Theme manager with persisted theme selection and configured cycling order.
 *
 * Auto-applies the resolved theme on import to prevent FOUC.
 * Dispatches `theme-change` CustomEvent on document when theme changes.
 */

const STORAGE_KEY = 'ntx-theme';
const DEFAULT_THEME = 'dark';
const DEFAULT_THEME_ORDER = Object.freeze(['dark', 'light']);

function normalizeThemeName(theme) {
    return typeof theme === 'string' ? theme.trim() : '';
}

function canUseDocument() {
    return typeof document !== 'undefined' && !!document.documentElement;
}

function canUseStorage() {
    try {
        return typeof localStorage !== 'undefined';
    } catch {
        return false;
    }
}

function readStoredTheme() {
    if (!canUseStorage()) return '';
    try {
        return normalizeThemeName(localStorage.getItem(STORAGE_KEY));
    } catch {
        return '';
    }
}

function writeStoredTheme(theme) {
    if (!canUseStorage()) return;
    try {
        localStorage.setItem(STORAGE_KEY, theme);
    } catch {
        // Ignore storage failures in restricted environments.
    }
}

export function hasThemeConfig() {
    return Array.isArray(globalThis.NTX_THEME_CONFIG?.themes);
}

export function getConfiguredThemes() {
    const rawThemes = globalThis.NTX_THEME_CONFIG?.themes;
    if (!Array.isArray(rawThemes)) {
        return [...DEFAULT_THEME_ORDER];
    }

    const themes = [];
    for (const rawTheme of rawThemes) {
        const theme = normalizeThemeName(rawTheme);
        if (!theme || themes.includes(theme)) continue;
        themes.push(theme);
    }

    return themes.length > 0 ? themes : [...DEFAULT_THEME_ORDER];
}

function getFallbackTheme() {
    return getConfiguredThemes()[0] || DEFAULT_THEME;
}

export function getNextTheme(currentTheme = getTheme()) {
    const themes = getConfiguredThemes();
    const current = normalizeThemeName(currentTheme);
    const index = themes.indexOf(current);

    if (index === -1) {
        return getFallbackTheme();
    }

    return themes[(index + 1) % themes.length] || getFallbackTheme();
}

/** @returns {string} */
export function getTheme() {
    return readStoredTheme() || getFallbackTheme();
}

/** @param {string} theme */
export function setTheme(theme) {
    const resolvedTheme = normalizeThemeName(theme) || getFallbackTheme();
    writeStoredTheme(resolvedTheme);

    if (canUseDocument()) {
        document.documentElement.dataset.theme = resolvedTheme;
        document.dispatchEvent(new CustomEvent('theme-change', { detail: { theme: resolvedTheme } }));
    }

    return resolvedTheme;
}

/** Cycle through configured themes in order. */
export function toggleTheme() {
    return setTheme(getNextTheme());
}

// Auto-apply on import — runs before first paint if script is in <head>
if (canUseDocument()) {
    document.documentElement.dataset.theme = getTheme();
}
