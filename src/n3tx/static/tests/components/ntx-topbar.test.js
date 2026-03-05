import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../../config.js', () => ({
  config: {
    LOGGING: 3, LOGEVENTS: false, DEBUG: false,
    API_URL: 'http://localhost:5000',
  }
}));
vi.mock('../../utils/Logging.js', () => ({
  default: { warn: vi.fn(), error: vi.fn(), debug: vi.fn(), dev: vi.fn(), log: vi.fn(), init: vi.fn(), event: vi.fn() }
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
  toggleTheme: vi.fn(),
};
vi.mock('../../utils/theme.js', () => mockTheme);

// Import after mocks
await import('../../components/ntx-topbar.js');
const { permissions } = await import('../../utils/Permissions.js');

describe('ntx-topbar.js (NTTTopbar)', () => {

  beforeEach(() => {
    mockPermissions.user = null;
    mockPermissions.authenticated = false;
    mockPermissions.role = 'anonymous';
    mockPermissions.init.mockImplementation(() => Promise.resolve(null));
    mockTheme.getTheme.mockReturnValue('dark');
    mockTheme.toggleTheme.mockClear();
  });

  describe('custom element registration', () => {
    it('should be registered as ntx-topbar', () => {
      const Ctor = customElements.get('ntx-topbar');
      expect(Ctor).toBeTruthy();
    });
  });

  describe('constructor', () => {
    it('should create shadow DOM', () => {
      const el = document.createElement('ntx-topbar');
      expect(el.shadowRoot).toBeTruthy();
    });

    it('should contain stylesheet link', () => {
      const el = document.createElement('ntx-topbar');
      const link = el.shadowRoot.querySelector('link');
      expect(link).toBeTruthy();
      expect(link.getAttribute('rel')).toBe('stylesheet');
    });
  });

  describe('render (unauthenticated)', () => {
    it('should show sign-in link when no user', () => {
      const el = document.createElement('ntx-topbar');
      const html = el.shadowRoot.innerHTML;
      expect(html).toContain('Sign in');
    });

    it('should render brand section with NTT', () => {
      const el = document.createElement('ntx-topbar');
      const html = el.shadowRoot.innerHTML;
      expect(html).toContain('NTT');
    });

    it('should render brand with version tag v0.6', () => {
      const el = document.createElement('ntx-topbar');
      const html = el.shadowRoot.innerHTML;
      expect(html).toContain('v0.6');
    });

    it('should not show favorites nav link when unauthenticated', () => {
      const el = document.createElement('ntx-topbar');
      const html = el.shadowRoot.innerHTML;
      expect(html).not.toContain('Favorites');
    });

    it('should not show user pill when unauthenticated', () => {
      const el = document.createElement('ntx-topbar');
      const html = el.shadowRoot.innerHTML;
      expect(html).not.toContain('user-pill');
    });
  });

  describe('render (authenticated)', () => {
    beforeEach(() => {
      mockPermissions.user = { name: 'Alice', email: 'alice@test.com', role: 'admin' };
      mockPermissions.authenticated = true;
      mockPermissions.role = 'admin';
      mockPermissions.init.mockImplementation(() => {
        return Promise.resolve(mockPermissions.user);
      });
    });

    it('should show user pill after permissions resolve', async () => {
      const el = document.createElement('ntx-topbar');
      document.body.appendChild(el);
      await mockPermissions.init();
      // Allow microtask for .then() to fire
      await new Promise(r => setTimeout(r, 10));
      const html = el.shadowRoot.innerHTML;
      expect(html).toContain('user-pill');
      document.body.removeChild(el);
    });

    it('should display user name', async () => {
      const el = document.createElement('ntx-topbar');
      document.body.appendChild(el);
      await mockPermissions.init();
      await new Promise(r => setTimeout(r, 10));
      const html = el.shadowRoot.innerHTML;
      expect(html).toContain('Alice');
      document.body.removeChild(el);
    });

    it('should display user email in dropdown', async () => {
      const el = document.createElement('ntx-topbar');
      document.body.appendChild(el);
      await mockPermissions.init();
      await new Promise(r => setTimeout(r, 10));
      const html = el.shadowRoot.innerHTML;
      expect(html).toContain('alice@test.com');
      document.body.removeChild(el);
    });

    it('should display user role in dropdown', async () => {
      const el = document.createElement('ntx-topbar');
      document.body.appendChild(el);
      await mockPermissions.init();
      await new Promise(r => setTimeout(r, 10));
      const html = el.shadowRoot.innerHTML;
      expect(html).toContain('admin');
      document.body.removeChild(el);
    });

    it('should show Favorites nav link when authenticated', async () => {
      const el = document.createElement('ntx-topbar');
      document.body.appendChild(el);
      await mockPermissions.init();
      await new Promise(r => setTimeout(r, 10));
      const html = el.shadowRoot.innerHTML;
      expect(html).toContain('Favorites');
      expect(html).toContain('#@favorites');
      document.body.removeChild(el);
    });

    it('should show Profile link in dropdown', async () => {
      const el = document.createElement('ntx-topbar');
      document.body.appendChild(el);
      await mockPermissions.init();
      await new Promise(r => setTimeout(r, 10));
      const html = el.shadowRoot.innerHTML;
      expect(html).toContain('Profile');
      expect(html).toContain('#@profile');
      document.body.removeChild(el);
    });

    it('should show Logout button in dropdown', async () => {
      const el = document.createElement('ntx-topbar');
      document.body.appendChild(el);
      await mockPermissions.init();
      await new Promise(r => setTimeout(r, 10));
      const btn = el.shadowRoot.querySelector('.logout-btn');
      expect(btn).toBeTruthy();
      expect(btn.textContent).toContain('Logout');
      document.body.removeChild(el);
    });

    it('should show user initial when no image', async () => {
      const el = document.createElement('ntx-topbar');
      document.body.appendChild(el);
      await mockPermissions.init();
      await new Promise(r => setTimeout(r, 10));
      const avatar = el.shadowRoot.querySelector('.user-avatar');
      expect(avatar).toBeTruthy();
      expect(avatar.textContent).toBe('A'); // initial of "Alice"
      document.body.removeChild(el);
    });

    it('should use email prefix as display name when name is missing', async () => {
      mockPermissions.user = { email: 'bob@test.com', role: 'user' };
      const el = document.createElement('ntx-topbar');
      document.body.appendChild(el);
      await mockPermissions.init();
      await new Promise(r => setTimeout(r, 10));
      const html = el.shadowRoot.innerHTML;
      expect(html).toContain('bob');
      document.body.removeChild(el);
    });
  });

  describe('logout handler', () => {
    it('should remove jwtToken from localStorage on logout click', async () => {
      mockPermissions.user = { name: 'Alice', email: 'alice@test.com', role: 'user' };
      mockPermissions.authenticated = true;
      mockPermissions.init.mockImplementation(() => Promise.resolve(mockPermissions.user));

      window.localStorage.setItem('jwtToken', 'test-token');
      const el = document.createElement('ntx-topbar');
      document.body.appendChild(el);
      await mockPermissions.init();
      await new Promise(r => setTimeout(r, 10));

      const logoutBtn = el.shadowRoot.querySelector('.logout-btn');
      expect(logoutBtn).toBeTruthy();

      // Prevent actual navigation in jsdom
      const originalHref = Object.getOwnPropertyDescriptor(window, 'location');
      delete window.location;
      window.location = { href: '' };

      logoutBtn.click();
      expect(window.localStorage.getItem('jwtToken')).toBeNull();

      // Restore
      if (originalHref) Object.defineProperty(window, 'location', originalHref);
      else window.location = { href: '' };
      document.body.removeChild(el);
    });
  });

  describe('theme toggle', () => {
    it('should show theme toggle button in dropdown', async () => {
      mockPermissions.user = { name: 'Alice', email: 'alice@test.com', role: 'user' };
      mockPermissions.authenticated = true;
      mockPermissions.init.mockImplementation(() => Promise.resolve(mockPermissions.user));

      const el = document.createElement('ntx-topbar');
      document.body.appendChild(el);
      await mockPermissions.init();
      await new Promise(r => setTimeout(r, 10));

      const themeBtn = el.shadowRoot.querySelector('.theme-toggle');
      expect(themeBtn).toBeTruthy();
      document.body.removeChild(el);
    });

    it('should call toggleTheme when theme button is clicked', async () => {
      mockPermissions.user = { name: 'Alice', email: 'alice@test.com', role: 'user' };
      mockPermissions.authenticated = true;
      mockPermissions.init.mockImplementation(() => Promise.resolve(mockPermissions.user));

      const el = document.createElement('ntx-topbar');
      document.body.appendChild(el);
      await mockPermissions.init();
      await new Promise(r => setTimeout(r, 10));

      const themeBtn = el.shadowRoot.querySelector('.theme-toggle');
      themeBtn.click();
      expect(mockTheme.toggleTheme).toHaveBeenCalled();
      document.body.removeChild(el);
    });

    it('should show "Light mode" label when current theme is dark', async () => {
      mockTheme.getTheme.mockReturnValue('dark');
      mockPermissions.user = { name: 'Alice', email: 'alice@test.com', role: 'user' };
      mockPermissions.authenticated = true;
      mockPermissions.init.mockImplementation(() => Promise.resolve(mockPermissions.user));

      const el = document.createElement('ntx-topbar');
      document.body.appendChild(el);
      await mockPermissions.init();
      await new Promise(r => setTimeout(r, 10));

      const themeBtn = el.shadowRoot.querySelector('.theme-toggle');
      expect(themeBtn.textContent).toContain('Light mode');
      document.body.removeChild(el);
    });

    it('should show "Dark mode" label when current theme is light', async () => {
      mockTheme.getTheme.mockReturnValue('light');
      mockPermissions.user = { name: 'Alice', email: 'alice@test.com', role: 'user' };
      mockPermissions.authenticated = true;
      mockPermissions.init.mockImplementation(() => Promise.resolve(mockPermissions.user));

      const el = document.createElement('ntx-topbar');
      document.body.appendChild(el);
      await mockPermissions.init();
      await new Promise(r => setTimeout(r, 10));

      const themeBtn = el.shadowRoot.querySelector('.theme-toggle');
      expect(themeBtn.textContent).toContain('Dark mode');
      document.body.removeChild(el);
    });
  });
});
