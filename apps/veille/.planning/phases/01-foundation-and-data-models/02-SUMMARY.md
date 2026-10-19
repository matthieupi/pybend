# Phase 1 Plan 02: Frontend + Document Upload Summary

## Status: COMPLETE

**One-liner:** Login/register/main HTML pages with auth gate, sidebar navigation, and JWT-authenticated document upload/download/delete API routes.

## What was built

- `static/login.html` -- Auth form POSTing to /users/login; stores JWT in localStorage; probes /sources (CRUD, auth-required) for existing token validation
- `static/register.html` -- Registration form POSTing to /users/register with name/email/password; same token storage and probe pattern
- `static/index.html` -- Main app with ntx-topbar, ntx-sidebar (Source, Organization, Grant), ntx-router, permissions.init() auth gate redirecting to /login.html, and document upload UI (file input + JS fetch to /organizations/upload)
- `main.py` -- Updated with three custom FastAPI routes: POST /organizations/upload, GET /organizations/documents/{filename}, DELETE /organizations/documents/{filename}; all require JWT auth via request.state.user; routes inserted before static mount catch-all

## Verification Results

- `GET /login.html` returns 200 with login form -- PASS
- `GET /register.html` returns 200 with registration form -- PASS
- `GET /` returns 200 with main app page -- PASS
- `POST /organizations/upload` without token returns 401 "Authentication required" -- PASS
- `GET /organizations/documents/{f}` without token returns 401 "Authentication required" -- PASS
- `DELETE /organizations/documents/{f}` without token returns 401 "Authentication required" -- PASS
- `POST /organizations/upload` with JWT and .txt file returns {"filename": "test-doc.txt", "size": 22} -- PASS
- `GET /organizations/documents/test-doc.txt` with JWT returns file content -- PASS
- `DELETE /organizations/documents/test-doc.txt` with JWT returns {"deleted": "test-doc.txt"} -- PASS
- Org documents list updated after upload (test-doc.txt appears in org.documents) -- PASS
- `.exe` file upload rejected with 400 "File type .exe not allowed" -- PASS

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| Token probe uses /sources (not /Source) | /sources requires AUTHENTICATED; /Source is schema endpoint (always public, returns 200 regardless) |
| Routes inserted via app.router.routes.insert(-1, route) | Inserts before static mount catch-all at "/"; app.include_router would add AFTER catch-all |
| Each route inlines the 401 check (no helper raising) | Raising non-Exception from helper does not propagate correctly in FastAPI; each route returns JSONResponse directly |
| python-multipart was already installed | No additional installation needed; aiofiles installed for future async file reading |

## Deviations from Plan

None - plan executed exactly as written.

## Commits

| Hash | Description |
|------|-------------|
| 8042365 | feat(01-02): Add login, register, and main app HTML pages |
| fc8eed0 | feat(01-02): Add JWT-authenticated document upload/download/delete routes |

## Duration

Start: 2026-03-20T16:45:32Z
End: 2026-03-20T16:57:00Z (approx)
Duration: ~12 minutes
