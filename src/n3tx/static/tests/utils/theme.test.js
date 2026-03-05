import { describe, it, expect, vi, beforeEach } from 'vitest';

// theme.js auto-applies on import, so we need to test carefully.
// We import after resetting localStorage to control the auto-apply behavior.

describe('theme.js', () => {

  beforeEach(() => {
    window.localStorage.removeItem('ntx-theme');
    document.documentElement.dataset.theme = '';
  });

  // Use dynamic import to get fresh module exports.
  // The module-level auto-apply runs on first import, but the functions
  // are still testable since they read/write localStorage directly.

  it('getTheme() should return "dark" as default when no theme is stored', async () => {
    const { getTheme } = await import('../../utils/theme.js');
    window.localStorage.removeItem('ntx-theme');
    expect(getTheme()).toBe('dark');
  });

  it('getTheme() should return stored theme from localStorage', async () => {
    const { getTheme } = await import('../../utils/theme.js');
    window.localStorage.setItem('ntx-theme', 'light');
    expect(getTheme()).toBe('light');
  });

  it('setTheme() should store theme in localStorage', async () => {
    const { setTheme } = await import('../../utils/theme.js');
    setTheme('light');
    expect(window.localStorage.getItem('ntx-theme')).toBe('light');
  });

  it('setTheme() should update document.documentElement.dataset.theme', async () => {
    const { setTheme } = await import('../../utils/theme.js');
    setTheme('light');
    expect(document.documentElement.dataset.theme).toBe('light');
  });

  it('setTheme() should dispatch theme-change CustomEvent', async () => {
    const { setTheme } = await import('../../utils/theme.js');
    const handler = vi.fn();
    document.addEventListener('theme-change', handler);
    setTheme('light');
    expect(handler).toHaveBeenCalledTimes(1);
    const event = handler.mock.calls[0][0];
    expect(event.detail).toEqual({ theme: 'light' });
    document.removeEventListener('theme-change', handler);
  });

  it('toggleTheme() should switch from dark to light', async () => {
    const { toggleTheme, getTheme } = await import('../../utils/theme.js');
    window.localStorage.setItem('ntx-theme', 'dark');
    toggleTheme();
    expect(getTheme()).toBe('light');
  });

  it('toggleTheme() should switch from light to dark', async () => {
    const { toggleTheme, getTheme } = await import('../../utils/theme.js');
    window.localStorage.setItem('ntx-theme', 'light');
    toggleTheme();
    expect(getTheme()).toBe('dark');
  });

  it('toggleTheme() should update DOM dataset', async () => {
    const { toggleTheme } = await import('../../utils/theme.js');
    window.localStorage.setItem('ntx-theme', 'dark');
    toggleTheme();
    expect(document.documentElement.dataset.theme).toBe('light');
  });
});
