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

# -- Document upload routes (custom, not auto-generated) --------
# All routes require JWT authentication via the x-access-token header.
# The JWTAuthMiddleware (in n3tx_core/api/backend.py) already decodes
# the token and stores the payload in request.state.user. We just need
# to check that user dict is non-empty.
from fastapi import APIRouter, UploadFile, File, Request  # noqa: E402
from fastapi.responses import JSONResponse, FileResponse  # noqa: E402

_api_router = APIRouter()
UPLOAD_DIR = os.path.join(_HERE, 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)


@_api_router.post("/organizations/upload")
async def upload_document(request: Request, file: UploadFile = File(...)):
    """Upload a strategic document for the organization. Requires JWT auth."""
    user = getattr(request.state, 'user', {}) or {}
    if not user.get('user_id'):
        return JSONResponse(status_code=401, content={"detail": "Authentication required"})

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
async def get_document(request: Request, filename: str):
    """Download a stored document. Requires JWT auth."""
    user = getattr(request.state, 'user', {}) or {}
    if not user.get('user_id'):
        return JSONResponse(status_code=401, content={"detail": "Authentication required"})

    filepath = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(filepath):
        return JSONResponse(status_code=404, content={"detail": "File not found"})
    return FileResponse(filepath)


@_api_router.delete("/organizations/documents/{filename}")
async def delete_document(request: Request, filename: str):
    """Delete a stored document. Requires JWT auth."""
    user = getattr(request.state, 'user', {}) or {}
    if not user.get('user_id'):
        return JSONResponse(status_code=401, content={"detail": "Authentication required"})

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
