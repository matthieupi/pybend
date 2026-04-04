import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

const mockTheme = {
  getTheme: vi.fn(() => 'dark'),
  getConfiguredThemes: vi.fn(() => ['dark', 'light']),
  getNextTheme: vi.fn(() => 'light'),
  toggleTheme: vi.fn(),
};

vi.mock('../../utils/theme.js', () => mockTheme);

await import('../../components/ntx-theme-button.js');

describe('ntx-theme-button.js', () => {
  beforeEach(() => {
    mockTheme.getTheme.mockReturnValue('dark');
    mockTheme.getConfiguredThemes.mockReturnValue(['dark', 'light']);
    mockTheme.getNextTheme.mockReturnValue('light');
    mockTheme.toggleTheme.mockReset();
  });

  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('registers the custom element', () => {
    expect(customElements.get('ntx-theme-button')).toBeTruthy();
  });

  it('renders footer variant by default', () => {
    const el = document.createElement('ntx-theme-button');
    document.body.appendChild(el);

    const button = el.shadowRoot.querySelector('.theme-button--footer');
    expect(button).toBeTruthy();
    expect(button.textContent).toContain('Theme');
    expect(button.textContent).toContain('Dark');
    expect(button.textContent).toContain('Next: Light');
  });

  it('renders menu variant when slotted into user-menu', () => {
    const el = document.createElement('ntx-theme-button');
    el.slot = 'user-menu';
    document.body.appendChild(el);

    expect(el.shadowRoot.querySelector('.theme-button--menu')).toBeTruthy();
  });

  it('calls toggleTheme when clicked', () => {
    const el = document.createElement('ntx-theme-button');
    document.body.appendChild(el);

    el.shadowRoot.querySelector('button').click();
    expect(mockTheme.toggleTheme).toHaveBeenCalledTimes(1);
  });

  it('disables itself when only one theme is configured', () => {
    mockTheme.getConfiguredThemes.mockReturnValue(['industrial']);
    mockTheme.getTheme.mockReturnValue('industrial');
    mockTheme.getNextTheme.mockReturnValue('industrial');

    const el = document.createElement('ntx-theme-button');
    document.body.appendChild(el);

    const button = el.shadowRoot.querySelector('button');
    expect(button.disabled).toBe(true);
    expect(button.textContent).toContain('Industrial');
  });

  it('re-renders on theme-change events', async () => {
    const el = document.createElement('ntx-theme-button');
    document.body.appendChild(el);
    expect(el.shadowRoot.textContent).toContain('Dark');

    mockTheme.getTheme.mockReturnValue('light');
    mockTheme.getNextTheme.mockReturnValue('dark');
    document.dispatchEvent(new CustomEvent('theme-change', { detail: { theme: 'light' } }));
    await Promise.resolve();

    expect(el.shadowRoot.textContent).toContain('Light');
    expect(el.shadowRoot.textContent).toContain('Next: Dark');
  });
});
