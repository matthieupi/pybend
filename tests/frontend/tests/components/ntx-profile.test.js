import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../../config.js', () => ({
  config: {
    API_URL: 'http://localhost:5000',
    LOGGING: 3, LOGEVENTS: false, DEBUG: false,
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

// Import after mocks
await import('../../components/ntx-profile.js');

describe('ntx-profile.js (NTTProfile)', () => {

  beforeEach(() => {
    mockPermissions.user = null;
    mockPermissions.authenticated = false;
    mockPermissions.role = 'anonymous';
    mockPermissions.init.mockImplementation(() => Promise.resolve(null));
  });

  describe('custom element registration', () => {
    it('should be registered as ntx-profile', () => {
      const Ctor = customElements.get('ntx-profile');
      expect(Ctor).toBeTruthy();
    });
  });

  describe('constructor', () => {
    it('should create shadow DOM', () => {
      const el = document.createElement('ntx-profile');
      expect(el.shadowRoot).toBeTruthy();
    });
  });

  describe('connectedCallback (unauthenticated)', () => {
    it('should show "Not authenticated" when user is null', async () => {
      const el = document.createElement('ntx-profile');
      document.body.appendChild(el);
      await mockPermissions.init();
      await new Promise(r => setTimeout(r, 10));
      const html = el.shadowRoot.innerHTML;
      expect(html).toContain('Not authenticated');
      document.body.removeChild(el);
    });
  });

  describe('connectedCallback (authenticated)', () => {
    beforeEach(() => {
      mockPermissions.user = { name: 'Alice', email: 'alice@test.com', role: 'admin' };
      mockPermissions.authenticated = true;
      mockPermissions.role = 'admin';
      mockPermissions.init.mockImplementation(() => Promise.resolve(mockPermissions.user));
    });

    it('should render profile card when user exists', async () => {
      const el = document.createElement('ntx-profile');
      document.body.appendChild(el);
      await mockPermissions.init();
      await new Promise(r => setTimeout(r, 10));
      const card = el.shadowRoot.querySelector('.profile-card');
      expect(card).toBeTruthy();
      document.body.removeChild(el);
    });

    it('should display user initial as avatar', async () => {
      const el = document.createElement('ntx-profile');
      document.body.appendChild(el);
      await mockPermissions.init();
      await new Promise(r => setTimeout(r, 10));
      const avatar = el.shadowRoot.querySelector('.avatar');
      expect(avatar).toBeTruthy();
      expect(avatar.textContent).toBe('A'); // "Alice"
      document.body.removeChild(el);
    });

    it('should display user name in h2', async () => {
      const el = document.createElement('ntx-profile');
      document.body.appendChild(el);
      await mockPermissions.init();
      await new Promise(r => setTimeout(r, 10));
      const h2 = el.shadowRoot.querySelector('h2');
      expect(h2.textContent).toBe('Alice');
      document.body.removeChild(el);
    });

    it('should display user email', async () => {
      const el = document.createElement('ntx-profile');
      document.body.appendChild(el);
      await mockPermissions.init();
      await new Promise(r => setTimeout(r, 10));
      const email = el.shadowRoot.querySelector('.email');
      expect(email.textContent).toBe('alice@test.com');
      document.body.removeChild(el);
    });

    it('should display user role', async () => {
      const el = document.createElement('ntx-profile');
      document.body.appendChild(el);
      await mockPermissions.init();
      await new Promise(r => setTimeout(r, 10));
      const role = el.shadowRoot.querySelector('.role');
      expect(role).toBeTruthy();
      expect(role.textContent).toBe('admin');
      document.body.removeChild(el);
    });

    it('should fallback to email prefix when name is missing', async () => {
      mockPermissions.user = { email: 'bob@test.com', role: 'user' };
      const el = document.createElement('ntx-profile');
      document.body.appendChild(el);
      await mockPermissions.init();
      await new Promise(r => setTimeout(r, 10));
      const h2 = el.shadowRoot.querySelector('h2');
      expect(h2.textContent).toBe('bob');
      document.body.removeChild(el);
    });

    it('should use email initial when name is missing', async () => {
      mockPermissions.user = { email: 'bob@test.com', role: 'user' };
      const el = document.createElement('ntx-profile');
      document.body.appendChild(el);
      await mockPermissions.init();
      await new Promise(r => setTimeout(r, 10));
      const avatar = el.shadowRoot.querySelector('.avatar');
      expect(avatar.textContent).toBe('B');
      document.body.removeChild(el);
    });

    it('should not render role badge when role is empty', async () => {
      mockPermissions.user = { name: 'Charlie', email: 'charlie@test.com', role: '' };
      const el = document.createElement('ntx-profile');
      document.body.appendChild(el);
      await mockPermissions.init();
      await new Promise(r => setTimeout(r, 10));
      const role = el.shadowRoot.querySelector('.role');
      expect(role).toBeNull();
      document.body.removeChild(el);
    });

    it('should show placeholder message about settings', async () => {
      const el = document.createElement('ntx-profile');
      document.body.appendChild(el);
      await mockPermissions.init();
      await new Promise(r => setTimeout(r, 10));
      const placeholder = el.shadowRoot.querySelector('.placeholder');
      expect(placeholder).toBeTruthy();
      expect(placeholder.textContent).toContain('coming soon');
      document.body.removeChild(el);
    });
  });
});
