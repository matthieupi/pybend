import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('../../config.js', () => ({
  config: {
    LOGGING: 3,
    LOGEVENTS: false,
    DEBUG: false,
    API_URL: 'http://localhost:5000',
  }
}));

const mockPermissions = {
  user: null,
  authenticated: false,
  role: 'anonymous',
  init: vi.fn(() => Promise.resolve(null)),
};

vi.mock('../../utils/Permissions.js', () => ({
  permissions: mockPermissions,
}));

const mockTheme = {
  getTheme: vi.fn(() => 'dark'),
  getConfiguredThemes: vi.fn(() => ['dark', 'light']),
  getNextTheme: vi.fn(() => 'light'),
  hasThemeConfig: vi.fn(() => true),
  setTheme: vi.fn(),
  toggleTheme: vi.fn(),
};

vi.mock('../../utils/theme.js', () => mockTheme);

await import('../../components/ntx-topbar.js');

describe('ntx-topbar.js', () => {
  const originalLocation = window.location;

  beforeEach(() => {
    mockPermissions.user = null;
    mockPermissions.authenticated = false;
    mockPermissions.role = 'anonymous';
    mockPermissions.init.mockResolvedValue(null);

    mockTheme.getTheme.mockReturnValue('dark');
    mockTheme.getConfiguredThemes.mockReturnValue(['dark', 'light']);
    mockTheme.getNextTheme.mockReturnValue('light');
    mockTheme.toggleTheme.mockReset();

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ name: 'Test App', version: '1.2.3' }),
    });
  });

  afterEach(() => {
    document.body.innerHTML = '';
    window.location = originalLocation;
    vi.restoreAllMocks();
  });

  it('registers the custom element', () => {
    expect(customElements.get('ntx-topbar')).toBeTruthy();
  });

  it('creates a shadow root with stylesheet link', () => {
    const el = document.createElement('ntx-topbar');
    expect(el.shadowRoot).toBeTruthy();
    const link = el.shadowRoot.querySelector('link');
    expect(link).toBeTruthy();
    expect(link.getAttribute('href')).toContain('ntx-topbar.css');
  });

  it('shows sign-in state when unauthenticated', async () => {
    const el = document.createElement('ntx-topbar');
    document.body.appendChild(el);
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(el.shadowRoot.textContent).toContain('Sign in');
    expect(el.shadowRoot.querySelector('nav.topbar')).toBeTruthy();
    expect(el.shadowRoot.querySelector('.topbar-brand')?.getAttribute('href')).toBe('/');
    expect(el.shadowRoot.querySelector('.topbar-title')?.textContent).toBe('Test App');
    expect(el.shadowRoot.querySelector('.topbar-logo')?.textContent.trim()).toBe('TE');
    expect(el.shadowRoot.querySelector('.topbar-tag')?.textContent.trim()).toBe('v1.2.3');
    expect(el.shadowRoot.querySelector('.signin-link')?.getAttribute('href')).toBe('/login.html');
    expect(el.shadowRoot.querySelector('.user-pill')).toBeNull();
    expect(el.shadowRoot.querySelector('.user-dropdown')).toBeNull();
    expect(el.shadowRoot.querySelector('a[href="#@favorites"]')).toBeNull();
    expect(el.shadowRoot.querySelector('a[href="#@profile"]')).toBeNull();
    expect(el.shadowRoot.querySelector('slot[name="user-menu"]')).toBeNull();
  });

  it('renders user dropdown details when authenticated', async () => {
    mockPermissions.user = { name: 'Alice', email: 'alice@test.com', role: 'admin' };
    mockPermissions.authenticated = true;
    mockPermissions.role = 'admin';
    mockPermissions.init.mockResolvedValue(mockPermissions.user);

    const el = document.createElement('ntx-topbar');
    document.body.appendChild(el);
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(el.shadowRoot.textContent).toContain('Alice');
    expect(el.shadowRoot.textContent).toContain('alice@test.com');
    expect(el.shadowRoot.textContent).toContain('admin');
    expect(el.shadowRoot.textContent).toContain('Profile');
    expect(el.shadowRoot.textContent).toContain('Logout');
    expect(el.shadowRoot.querySelector('.signin-link')).toBeNull();
    expect(el.shadowRoot.querySelector('.user-pill')).toBeTruthy();
    expect(el.shadowRoot.querySelector('.user-avatar')?.textContent.trim()).toBe('A');
    expect(el.shadowRoot.querySelector('.user-name')?.textContent.trim()).toBe('Alice');
    expect(el.shadowRoot.querySelector('.user-chevron')).toBeTruthy();
    expect(el.shadowRoot.querySelector('.dropdown-header')).toBeTruthy();
    expect(el.shadowRoot.querySelector('.dropdown-email')?.textContent.trim()).toBe('alice@test.com');
    expect(el.shadowRoot.querySelector('.dropdown-role')?.textContent.trim()).toBe('admin');
    expect(el.shadowRoot.querySelector('a[href="#@profile"]')).toBeTruthy();
    expect(el.shadowRoot.querySelector('.logout-btn')).toBeTruthy();
    expect(el.shadowRoot.querySelectorAll('.dropdown-divider').length).toBeGreaterThanOrEqual(1);
    expect(el.shadowRoot.querySelectorAll('.dropdown-item').length).toBeGreaterThanOrEqual(2);
    expect(el.shadowRoot.querySelector('slot[name="user-menu"]')).toBeTruthy();
    expect(el.shadowRoot.querySelector('.theme-toggle')).toBeNull();
  });

  it('derives user initials and labels from the authenticated user', async () => {
    mockPermissions.user = { name: 'Bob Johnson', email: 'bob@example.com', role: 'user' };
    mockPermissions.authenticated = true;
    mockPermissions.role = 'user';
    mockPermissions.init.mockResolvedValue(mockPermissions.user);

    const el = document.createElement('ntx-topbar');
    document.body.appendChild(el);
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(el.shadowRoot.querySelector('.user-avatar')?.textContent.trim()).toBe('B');
    expect(el.shadowRoot.querySelector('.user-name')?.textContent.trim()).toBe('Bob Johnson');
    expect(el.shadowRoot.querySelector('.dropdown-email')?.textContent.trim()).toBe('bob@example.com');
  });

  it('assigns slotted nav content to the nav slot', async () => {
    const el = document.createElement('ntx-topbar');
    const navLink = document.createElement('a');
    navLink.slot = 'nav';
    navLink.textContent = 'Dashboard';
    el.appendChild(navLink);

    document.body.appendChild(el);
    await new Promise((resolve) => setTimeout(resolve, 0));

    const slot = el.shadowRoot.querySelector('slot[name="nav"]');
    expect(slot).toBeTruthy();
    expect(slot.assignedElements()).toContain(navLink);
  });

  it('assigns slotted user-menu content when authenticated', async () => {
    mockPermissions.user = { name: 'Alice', email: 'alice@test.com', role: 'admin' };
    mockPermissions.authenticated = true;
    mockPermissions.role = 'admin';
    mockPermissions.init.mockResolvedValue(mockPermissions.user);

    const el = document.createElement('ntx-topbar');
    const themeButton = document.createElement('ntx-theme-button');
    themeButton.slot = 'user-menu';
    el.appendChild(themeButton);

    document.body.appendChild(el);
    await new Promise((resolve) => setTimeout(resolve, 0));

    const slot = el.shadowRoot.querySelector('slot[name="user-menu"]');
    expect(slot).toBeTruthy();
    expect(slot.assignedElements()).toContain(themeButton);
  });

  it('logs out by clearing the JWT token', async () => {
    mockPermissions.user = { name: 'Alice', email: 'alice@test.com', role: 'user' };
    mockPermissions.authenticated = true;
    mockPermissions.init.mockResolvedValue(mockPermissions.user);
    window.localStorage.setItem('jwtToken', 'token');
    window.location = { href: '' };

    const el = document.createElement('ntx-topbar');
    document.body.appendChild(el);
    await new Promise((resolve) => setTimeout(resolve, 0));

    el.shadowRoot.querySelector('.logout-btn').click();

    expect(window.localStorage.getItem('jwtToken')).toBeNull();
    expect(window.location.href).toBe('/login.html');
  });
});
