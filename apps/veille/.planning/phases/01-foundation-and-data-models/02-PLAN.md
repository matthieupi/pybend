---
wave: 2
depends_on: ["01-01"]
files_modified:
  - apps/veille/static/index.html
  - apps/veille/static/login.html
  - apps/veille/static/register.html
  - apps/veille/main.py
autonomous: true

must_haves:
  truths:
    - "Unauthenticated user visiting / is redirected to /login.html"
    - "User can log in on /login.html and is redirected to the main app"
    - "User can register on /register.html and is redirected to the main app"
    - "Authenticated user sees a sidebar with Source and Grant navigation"
    - "User can upload a PDF/txt document via the upload endpoint and it appears in the Organization documents list"
    - "User can download a previously uploaded document"
  artifacts:
    - path: "apps/veille/static/login.html"
      provides: "Login page"
    - path: "apps/veille/static/register.html"
      provides: "Registration page"
    - path: "apps/veille/static/index.html"
      provides: "Main app page with sidebar, router, and auth gate"
    - path: "apps/veille/main.py"
      provides: "Updated with document upload/download/delete routes"
  key_links:
    - from: "static/login.html"
      to: "/users/login"
      via: "fetch POST"
      pattern: "fetch.*users/login"
    - from: "static/register.html"
      to: "/users/register"
      via: "fetch POST"
      pattern: "fetch.*users/register"
    - from: "static/index.html"
      to: "permissions.init()"
      via: "JS module import"
      pattern: "permissions\\.init"
    - from: "main.py upload route"
      to: "Organization.update"
      via: "updates documents list"
      pattern: "Organization\\.update"
---

# Plan 02: Frontend + Document Upload

## Objective

Deliver the complete frontend (login, register, main app pages) and the custom document upload/download API routes. After this plan, a user can log in, navigate the app, browse Sources/Organizations/Grants via the standard N3TX UI, and upload strategic documents.

Purpose: This completes the Phase 1 user experience. All requirements (AUTH-01, AUTH-02, ORG-01-03, SRC-01-03) are fully functional through the UI.

Output: 3 HTML files + updated main.py with upload routes.

## Context

**Plan 01 must be complete before this plan runs.** Plan 01 delivers the server, models, and seed data. This plan adds the frontend and document upload routes.

**N3TX SSR='full' serves static files** from the `static_dir` passed to `create_app()`. The static mount is a catch-all at `"/"` -- it is the LAST route. Custom API routes must be inserted BEFORE this catch-all using `app.router.routes.insert(-1, route)`.

**Auth flow:**
- `login.html` POSTs to `/users/login`, receives `{token: "..."}` (possibly nested under `result` or `result.data` in debug mode), stores in `localStorage.jwtToken`, redirects to `/`.
- `register.html` POSTs to `/users/register` with `{name, email, password}`, same token flow.
- `index.html` calls `permissions.init()` which fetches `/auth/me` with the stored token. If no valid token, redirects to `/login.html`.

**Token validation on login/register pages:** The actors example probes `GET /Product` to check if an existing token is still valid. For Veille, probe `GET /Source` instead (a schema endpoint that requires no auth but confirms the server is running).

**Frontend uses N3TX standard components:** `ntx-topbar`, `ntx-sidebar`, `ntx-router`, `ntx-list`, `ntx-item`. These are served automatically by N3TX's SSR='full' mode from the framework's static directories. No need to copy component JS files -- they are bundled and served by the framework.

**Document upload:** N3TX does not support multipart/form-data in `@expose_route`. A custom FastAPI `APIRouter` with `UploadFile` is added to `main.py`, with routes inserted before the static mount.

**Working directory:** All paths relative to `/workspace/apps/veille/`.

## Tasks

<task id="1" title="Create login.html, register.html, and index.html">

Create three HTML files in the `static/` directory. These are adapted from the actors example (`/workspace/examples/actors/static/`).

### File 1: `static/login.html`

Copy the structure from `/workspace/examples/actors/static/login.html` with these changes:
- Title: `Login -- Veille` (not `Login -- NTT`)
- Header h1: `Welcome back` (keep as-is)
- Header p: `Sign in to Veille` (not generic)
- Auth link text: `Don't have an account? <a href="/register.html">Register</a>` (keep as-is)
- Token validation probe: change `/Product` to `/Source` in the existing-token check at the bottom

Full file content:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Login — Veille</title>
  <link rel="stylesheet" href="./dark-theme.css" />
  <link rel="stylesheet" href="./light-theme.css" />
  <link rel="icon" type="image/svg+xml" href="./favicon.svg" />
  <script type="module" src="./utils/theme.js"></script>
  <style>
    .auth-page {
      position: relative;
      z-index: 1;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      padding: 2rem;
    }

    .auth-card {
      width: 100%;
      max-width: 400px;
      background: var(--glass-bg);
      background-image: var(--glass-gradient);
      backdrop-filter: blur(var(--glass-blur-lg, 28px)) saturate(1.2);
      -webkit-backdrop-filter: blur(var(--glass-blur-lg, 28px)) saturate(1.2);
      border: 1px solid var(--glass-border);
      border-top-color: var(--light-highlight);
      border-radius: var(--radius-xl);
      padding: 2.5rem;
      box-shadow: var(--shadow-xl);
    }

    .auth-header {
      text-align: center;
      margin-bottom: 2rem;
    }

    .auth-header h1 {
      font-size: 1.5rem;
      margin-bottom: 0.5rem;
    }

    .auth-header p {
      color: var(--text-2);
      font-size: 0.875rem;
    }

    .form-group {
      margin-bottom: 1.25rem;
    }

    .form-group label {
      display: block;
      font-size: 0.8rem;
      font-weight: 500;
      color: var(--text-2);
      margin-bottom: 0.4rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    .form-group input {
      width: 100%;
    }

    .auth-btn {
      width: 100%;
      padding: 0.75rem;
      font-size: 0.9rem;
      margin-top: 0.5rem;
    }

    .auth-link {
      text-align: center;
      margin-top: 1.5rem;
      font-size: 0.85rem;
      color: var(--text-2);
    }

    .auth-link a {
      color: var(--accent-text);
      text-decoration: none;
    }

    .auth-link a:hover {
      text-decoration: underline;
    }

    .auth-error {
      background: rgba(248, 113, 113, 0.1);
      border: 1px solid rgba(248, 113, 113, 0.2);
      color: var(--error);
      padding: 0.6rem 0.85rem;
      border-radius: var(--radius-sm);
      font-size: 0.825rem;
      margin-bottom: 1rem;
      display: none;
    }
  </style>
</head>
<body>
  <div class="auth-page">
    <div class="auth-card">
      <div class="auth-header">
        <h1>Welcome back</h1>
        <p>Sign in to Veille</p>
      </div>

      <div class="auth-error" id="error-msg"></div>

      <form id="login-form">
        <div class="form-group">
          <label for="email">Email</label>
          <input type="email" id="email" placeholder="you@example.com" required />
        </div>
        <div class="form-group">
          <label for="password">Password</label>
          <input type="password" id="password" placeholder="Your password" required />
        </div>
        <button type="submit" class="auth-btn">Sign in</button>
      </form>

      <div class="auth-link">
        Don't have an account? <a href="/register.html">Register</a>
      </div>
    </div>
  </div>

  <script>
    const form = document.getElementById('login-form');
    const errorEl = document.getElementById('error-msg');

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      errorEl.style.display = 'none';

      const email = document.getElementById('email').value;
      const password = document.getElementById('password').value;

      try {
        const resp = await fetch('/users/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password }),
        });

        if (!resp.ok) {
          const err = await resp.json();
          throw new Error(err.detail || 'Login failed');
        }

        const data = await resp.json();
        const payload = data.result || data;
        const token = payload.token || (payload.data && payload.data.token);
        window.localStorage.setItem('jwtToken', token);
        window.location.href = '/';
      } catch (err) {
        errorEl.textContent = err.message;
        errorEl.style.display = 'block';
      }
    });

    // If already logged in, validate token then redirect
    const existingToken = window.localStorage.getItem('jwtToken');
    if (existingToken) {
      fetch('/Source', { headers: { 'x-access-token': existingToken } })
        .then(resp => {
          if (resp.ok) {
            window.location.href = '/';
          } else {
            window.localStorage.removeItem('jwtToken');
          }
        })
        .catch(() => {
          window.localStorage.removeItem('jwtToken');
        });
    }
  </script>
</body>
</html>
```

### File 2: `static/register.html`

Same structure as login.html with these differences:
- Title: `Register -- Veille`
- Header h1: `Create account`
- Header p: `Get started with Veille`
- Form has Name, Email, Password fields
- POSTs to `/users/register` with `{name, email, password}`
- Link: `Already have an account? <a href="/login.html">Sign in</a>`

Full file content:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Register — Veille</title>
  <link rel="stylesheet" href="./dark-theme.css" />
  <link rel="stylesheet" href="./light-theme.css" />
  <link rel="icon" type="image/svg+xml" href="./favicon.svg" />
  <script type="module" src="./utils/theme.js"></script>
  <style>
    .auth-page {
      position: relative;
      z-index: 1;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      padding: 2rem;
    }

    .auth-card {
      width: 100%;
      max-width: 400px;
      background: var(--glass-bg);
      background-image: var(--glass-gradient);
      backdrop-filter: blur(var(--glass-blur-lg, 28px)) saturate(1.2);
      -webkit-backdrop-filter: blur(var(--glass-blur-lg, 28px)) saturate(1.2);
      border: 1px solid var(--glass-border);
      border-top-color: var(--light-highlight);
      border-radius: var(--radius-xl);
      padding: 2.5rem;
      box-shadow: var(--shadow-xl);
    }

    .auth-header {
      text-align: center;
      margin-bottom: 2rem;
    }

    .auth-header h1 {
      font-size: 1.5rem;
      margin-bottom: 0.5rem;
    }

    .auth-header p {
      color: var(--text-2);
      font-size: 0.875rem;
    }

    .form-group {
      margin-bottom: 1.25rem;
    }

    .form-group label {
      display: block;
      font-size: 0.8rem;
      font-weight: 500;
      color: var(--text-2);
      margin-bottom: 0.4rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    .form-group input {
      width: 100%;
    }

    .auth-btn {
      width: 100%;
      padding: 0.75rem;
      font-size: 0.9rem;
      margin-top: 0.5rem;
    }

    .auth-link {
      text-align: center;
      margin-top: 1.5rem;
      font-size: 0.85rem;
      color: var(--text-2);
    }

    .auth-link a {
      color: var(--accent-text);
      text-decoration: none;
    }

    .auth-link a:hover {
      text-decoration: underline;
    }

    .auth-error {
      background: rgba(248, 113, 113, 0.1);
      border: 1px solid rgba(248, 113, 113, 0.2);
      color: var(--error);
      padding: 0.6rem 0.85rem;
      border-radius: var(--radius-sm);
      font-size: 0.825rem;
      margin-bottom: 1rem;
      display: none;
    }
  </style>
</head>
<body>
  <div class="auth-page">
    <div class="auth-card">
      <div class="auth-header">
        <h1>Create account</h1>
        <p>Get started with Veille</p>
      </div>

      <div class="auth-error" id="error-msg"></div>

      <form id="register-form">
        <div class="form-group">
          <label for="name">Name</label>
          <input type="text" id="name" placeholder="Your name" required />
        </div>
        <div class="form-group">
          <label for="email">Email</label>
          <input type="email" id="email" placeholder="you@example.com" required />
        </div>
        <div class="form-group">
          <label for="password">Password</label>
          <input type="password" id="password" placeholder="Choose a password" required minlength="6" />
        </div>
        <button type="submit" class="auth-btn">Create account</button>
      </form>

      <div class="auth-link">
        Already have an account? <a href="/login.html">Sign in</a>
      </div>
    </div>
  </div>

  <script>
    const form = document.getElementById('register-form');
    const errorEl = document.getElementById('error-msg');

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      errorEl.style.display = 'none';

      const name = document.getElementById('name').value;
      const email = document.getElementById('email').value;
      const password = document.getElementById('password').value;

      try {
        const resp = await fetch('/users/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, email, password }),
        });

        if (!resp.ok) {
          const err = await resp.json();
          throw new Error(err.detail || 'Registration failed');
        }

        const data = await resp.json();
        const payload = data.result || data;
        const token = payload.token || (payload.data && payload.data.token);
        window.localStorage.setItem('jwtToken', token);
        window.location.href = '/';
      } catch (err) {
        errorEl.textContent = err.message;
        errorEl.style.display = 'block';
      }
    });

    // If already logged in, validate token then redirect
    const existingToken = window.localStorage.getItem('jwtToken');
    if (existingToken) {
      fetch('/Source', { headers: { 'x-access-token': existingToken } })
        .then(resp => {
          if (resp.ok) {
            window.location.href = '/';
          } else {
            window.localStorage.removeItem('jwtToken');
          }
        })
        .catch(() => {
          window.localStorage.removeItem('jwtToken');
        });
    }
  </script>
</body>
</html>
```

### File 3: `static/index.html`

The main application page. Adapted from `/workspace/examples/actors/static/index.html` with these changes:
- Title: `Veille - Grant Monitoring`
- Sidebar shows `Source` model (the primary navigation entity)
- Router default view shows `Source` list with `allow-create`
- No `ntx-chat`, `ntx-logs`, `ntx-favorites`, `ntx-profile`, or `ntx-user` components (not needed for Phase 1)
- Auth gate: `permissions.init()` redirects to `/login.html` if no valid user
- Logging init message: `Loading Veille v1.0...`

Full file content:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Veille - Grant Monitoring</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="./dark-theme.css">
    <link rel="stylesheet" href="./light-theme.css">
    <link rel="icon" type="image/svg+xml" href="./favicon.svg">
    <link rel="preload" href="./components/ntx-item.css" as="style">
    <link rel="preload" href="./components/ntx-list.css" as="style">
    <link rel="preload" href="./components/ntx-router.css" as="style">
    <link rel="preload" href="./components/ntx-topbar.css" as="style">
    <link rel="preload" href="./components/ntx-sidebar.css" as="style">
    <link rel="preload" href="./components/ntx-modal.css" as="style">
    <link rel="preload" href="./widgets/widgets.css" as="style">
    <script src="./vendor/marked.min.js"></script>
    <!-- Modulepreload -- eliminates import waterfall -->
    <link rel="modulepreload" href="./config.js">
    <link rel="modulepreload" href="./utils/Assert.js">
    <link rel="modulepreload" href="./utils/Logging.js">
    <link rel="modulepreload" href="./utils/Permissions.js">
    <link rel="modulepreload" href="./core/Utils.js">
    <link rel="modulepreload" href="./core/TX.js">
    <link rel="modulepreload" href="./core/Observable.js">
    <link rel="modulepreload" href="./core/Actor.js">
    <link rel="modulepreload" href="./core/Matrix.js">
    <link rel="modulepreload" href="./core/Component.js">
    <link rel="modulepreload" href="./core/Router.js">
    <link rel="modulepreload" href="./core/NTT.js">
    <link rel="modulepreload" href="./core/transport/HTTP.js">
    <link rel="modulepreload" href="./core/transport/NetworkAdapter.js">
    <link rel="modulepreload" href="./components/NTTElement.js">
    <link rel="modulepreload" href="./components/ListElement.js">
    <link rel="modulepreload" href="./components/ntx-item.js">
    <link rel="modulepreload" href="./components/ntx-list.js">
    <link rel="modulepreload" href="./components/ntx-router.js">
    <link rel="modulepreload" href="./components/ntx-method.js">
    <link rel="modulepreload" href="./components/ntx-modal.js">
    <link rel="modulepreload" href="./components/ntx-sidebar.js">
    <link rel="modulepreload" href="./components/ntx-stream.js">
    <link rel="modulepreload" href="./generators/form.js">
    <link rel="modulepreload" href="./widgets/Widget.js">
    <link rel="modulepreload" href="./widgets/registry.js">
    <link rel="modulepreload" href="./widgets/index.js">
    <script type="module" src="./utils/theme.js"></script>
</head>
<body>
    <ntx-topbar></ntx-topbar>
    <ntx-sidebar router="main">
        <ntx-list model="Source" allow-create></ntx-list>
    </ntx-sidebar>

    <div class="page">
        <ntx-router name="main" hash>
            <ntx-list model="Source" id="source-list" allow-create></ntx-list>
        </ntx-router>
    </div>

    <script type="module">
        import Logging from './utils/Logging.js';
        Logging.init("Loading Veille v1.0...");

        import { Matrix, matrix } from './core/Matrix.js';
        import { NTT } from './core/NTT.js';
        import { config } from './config.js';
        import { permissions } from './utils/Permissions.js';
        import './components/ntx-item.js';
        import './components/ntx-list.js';
        import './components/ntx-router.js';
        import './components/ntx-topbar.js';
        import './components/ntx-sidebar.js';
        import './components/ntx-stream.js';

        // Redirect to login if not authenticated
        permissions.init().then(user => {
            if (!user) {
                window.location.href = '/login.html';
            }
        });
    </script>
</body>
</html>
```

**Verify:** All three files exist in `static/`:
```bash
ls -la /workspace/apps/veille/static/login.html /workspace/apps/veille/static/register.html /workspace/apps/veille/static/index.html
```

**Done:** Three HTML files created. Login and register pages use standalone auth forms. Main page has auth gate, sidebar with Source navigation, and router with Source list as default view.

</task>

<task id="2" title="Add document upload routes to main.py">

Modify `/workspace/apps/veille/main.py` to add three custom FastAPI routes for document upload, download, and delete. These routes are inserted BEFORE the static mount (catch-all at "/") to avoid being shadowed.

**IMPORTANT:** The `python-multipart` package is required for `UploadFile` to work. Install it first:
```bash
pip install python-multipart aiofiles
```

Add the following code to `main.py` AFTER the `app = create_app(...)` call and BEFORE the `if __name__ == '__main__':` block:

```python
# ── Document upload routes (custom, not auto-generated) ──────────────
from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse, FileResponse

_api_router = APIRouter()
UPLOAD_DIR = os.path.join(_HERE, 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)


@_api_router.post("/organizations/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload a strategic document for the organization."""
    allowed = {'.pdf', '.txt', '.md', '.doc', '.docx'}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed:
        return JSONResponse(status_code=400, content={"detail": f"File type {ext} not allowed"})

    filepath = os.path.join(UPLOAD_DIR, file.filename)
    content = await file.read()
    with open(filepath, 'wb') as f:
        f.write(content)

    # Update organization documents list
    from models import Organization
    orgs = Organization.list()
    if orgs:
        data = orgs if isinstance(orgs, list) else orgs.get('data', [])
        if data:
            org = data[0]
            docs = org.documents or []
            if file.filename not in docs:
                docs.append(file.filename)
                Organization.update(org.id, {'documents': docs})

    return {"filename": file.filename, "size": len(content)}


@_api_router.get("/organizations/documents/{filename}")
async def get_document(filename: str):
    """Download a stored document."""
    filepath = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(filepath):
        return JSONResponse(status_code=404, content={"detail": "File not found"})
    return FileResponse(filepath)


@_api_router.delete("/organizations/documents/{filename}")
async def delete_document(filename: str):
    """Delete a stored document."""
    filepath = os.path.join(UPLOAD_DIR, filename)
    if os.path.exists(filepath):
        os.remove(filepath)

    from models import Organization
    orgs = Organization.list()
    if orgs:
        data = orgs if isinstance(orgs, list) else orgs.get('data', [])
        if data:
            org = data[0]
            docs = [d for d in (org.documents or []) if d != filename]
            Organization.update(org.id, {'documents': docs})

    return {"deleted": filename}


# Insert custom routes BEFORE the static mount (last route is catch-all at "/")
for route in _api_router.routes:
    app.router.routes.insert(-1, route)
```

The complete `main.py` after modification should look like this (full file for reference):

```python
"""Veille -- Grant monitoring application."""
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import config  # noqa: E402

# CRITICAL: Must import n3tx_agents BEFORE model imports.
import n3tx_agents  # noqa: F401, E402

from n3tx_core.app import create_app  # noqa: E402
from n3tx_core.storage.sqlite_storage import SQLiteStorage  # noqa: E402
from models import User, Organization, Source, Grant  # noqa: E402

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')

_HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_HERE, config.SQLITE_DB_FILE)

storage = SQLiteStorage(DB_PATH)
app = create_app(
    models=[User, Organization, Source, Grant],
    storage=storage,
    routing='actor',
    jwt_secret=config.JWT_SECRET,
    static_dir=os.path.join(_HERE, 'static'),
    ssr='full',
    name='Veille',
    version='1.0.0',
    description='Agentic grant monitoring for non-profits',
)

# ── Document upload routes (custom, not auto-generated) ──────────────
from fastapi import APIRouter, UploadFile, File  # noqa: E402
from fastapi.responses import JSONResponse, FileResponse  # noqa: E402

_api_router = APIRouter()
UPLOAD_DIR = os.path.join(_HERE, 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)


@_api_router.post("/organizations/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload a strategic document for the organization."""
    allowed = {'.pdf', '.txt', '.md', '.doc', '.docx'}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed:
        return JSONResponse(status_code=400, content={"detail": f"File type {ext} not allowed"})

    filepath = os.path.join(UPLOAD_DIR, file.filename)
    content = await file.read()
    with open(filepath, 'wb') as f:
        f.write(content)

    # Update organization documents list
    orgs = Organization.list()
    if orgs:
        data = orgs if isinstance(orgs, list) else orgs.get('data', [])
        if data:
            org = data[0]
            docs = org.documents or []
            if file.filename not in docs:
                docs.append(file.filename)
                Organization.update(org.id, {'documents': docs})

    return {"filename": file.filename, "size": len(content)}


@_api_router.get("/organizations/documents/{filename}")
async def get_document(filename: str):
    """Download a stored document."""
    filepath = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(filepath):
        return JSONResponse(status_code=404, content={"detail": "File not found"})
    return FileResponse(filepath)


@_api_router.delete("/organizations/documents/{filename}")
async def delete_document(filename: str):
    """Delete a stored document."""
    filepath = os.path.join(UPLOAD_DIR, filename)
    if os.path.exists(filepath):
        os.remove(filepath)

    orgs = Organization.list()
    if orgs:
        data = orgs if isinstance(orgs, list) else orgs.get('data', [])
        if data:
            org = data[0]
            docs = [d for d in (org.documents or []) if d != filename]
            Organization.update(org.id, {'documents': docs})

    return {"deleted": filename}


# Insert custom routes BEFORE the static mount (last route is catch-all at "/")
for route in _api_router.routes:
    app.router.routes.insert(-1, route)


if __name__ == '__main__':
    import uvicorn
    if config.DEBUG:
        uvicorn.run('main:app', host=config.HOST, port=config.PORT, reload=True)
    else:
        uvicorn.run(app, host=config.HOST, port=config.PORT)
```

Note: In the upload route, `Organization` is already imported at the top of the file, so no need for lazy import inside the function.

### Verify upload routes

1. **Ensure dependencies are installed:**
```bash
pip install python-multipart aiofiles
```

2. **Start server and seed** (if not already seeded):
```bash
cd /workspace/apps/veille
rm -f veille.db
python seed.py
timeout 10 python main.py &
sleep 3
```

3. **Get auth token:**
```bash
TOKEN=$(curl -s -X POST http://localhost:5000/users/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@veille.local","password":"admin123"}' | python3 -c "import sys,json; d=json.load(sys.stdin); r=d.get('result',d); print(r.get('token','') or r.get('data',{}).get('token',''))")
```

4. **Test upload:**
```bash
echo "Test document content" > /tmp/test-doc.txt
curl -s -X POST http://localhost:5000/organizations/upload \
  -F "file=@/tmp/test-doc.txt" | python3 -c "import sys,json; d=json.load(sys.stdin); print('Upload OK:', d.get('filename'))"
```

5. **Test download:**
```bash
curl -s http://localhost:5000/organizations/documents/test-doc.txt | head -1
```

6. **Test that org documents list was updated:**
```bash
curl -s http://localhost:5000/organizations -H "x-access-token: $TOKEN" | python3 -c "
import sys, json
d = json.load(sys.stdin)
data = d.get('data', d) if isinstance(d, dict) else d
if data:
    org = data[0] if isinstance(data, list) else data
    docs = org.get('documents', [])
    print('Org documents:', docs)
    assert 'test-doc.txt' in docs, 'test-doc.txt not in documents list'
    print('Documents list updated OK')
"
```

7. **Test delete:**
```bash
curl -s -X DELETE http://localhost:5000/organizations/documents/test-doc.txt | python3 -c "import sys,json; d=json.load(sys.stdin); print('Delete OK:', d)"
```

8. **Test disallowed file type:**
```bash
echo "bad" > /tmp/test.exe
curl -s -X POST http://localhost:5000/organizations/upload \
  -F "file=@/tmp/test.exe" | python3 -c "import sys,json; d=json.load(sys.stdin); print('Rejected:', d.get('detail', 'no error'))"
```

9. **Test that frontend pages are served:**
```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/login.html
curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/register.html
curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/
```
All three should return `200`.

10. **Kill the server:**
```bash
kill %1 2>/dev/null || true
```

If upload returns a 422 error about missing `python-multipart`, ensure the package is installed. If routes return 404, check that `app.router.routes.insert(-1, route)` is used (not `app.include_router`).

**Done:** main.py has upload/download/delete routes. Upload accepts PDF/txt/md/doc/docx, saves to `uploads/`, and updates the Organization's documents list. Download serves files from `uploads/`. Delete removes file and updates the documents list. Frontend pages (login.html, register.html, index.html) are served by the static mount.

</task>

## Verification

- [ ] `GET /login.html` returns 200 with a login form
- [ ] `GET /register.html` returns 200 with a registration form
- [ ] `GET /` returns 200 with the main app page containing `ntx-sidebar` and `ntx-router`
- [ ] Login form POSTs to `/users/login` and stores JWT token
- [ ] Register form POSTs to `/users/register` and stores JWT token
- [ ] `POST /organizations/upload` with a .txt file returns `{"filename": "...", "size": N}`
- [ ] `POST /organizations/upload` with a .exe file returns 400 error
- [ ] `GET /organizations/documents/{filename}` returns the uploaded file content
- [ ] `DELETE /organizations/documents/{filename}` removes the file and updates org documents list
- [ ] Organization documents list is updated after upload (new filename appears in the list)
- [ ] index.html contains `permissions.init()` auth gate that redirects to `/login.html`

## must_haves

- Unauthenticated users are redirected from / to /login.html (auth gate via permissions.init())
- Login page authenticates against /users/login and stores JWT in localStorage
- Register page creates account via /users/register and stores JWT in localStorage
- Main app page shows ntx-sidebar with Source model and ntx-router with Source list
- Document upload endpoint accepts PDF/txt/md/doc/docx, saves to uploads/, and updates Organization.documents
- Document download endpoint serves files from uploads/
- Document delete endpoint removes file and updates Organization.documents
- Disallowed file types are rejected with 400 error
