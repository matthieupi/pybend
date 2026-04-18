"""Veille -- Grant monitoring application."""
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

import config  # noqa: E402

# CRITICAL: Must import n3tx_agents BEFORE model imports.
import n3tx_agents  # noqa: F401, E402

from n3tx_core.app import create_app  # noqa: E402
from n3tx_core.storage.sqlite_storage import SQLiteStorage  # noqa: E402
from n3tx_agents.actor import AgentActor  # noqa: E402
from n3tx_agents.tool_model import AgentTool  # noqa: E402
from models import User, Organization, Source, Grant, Run, WebTools  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('veille.scheduler')

_HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_HERE, config.SQLITE_DB_FILE)

storage = SQLiteStorage(DB_PATH)
app = create_app(
    models=[User, Organization, Source, Grant, Run, WebTools, AgentTool, AgentActor],
    join_models=[(AgentActor, AgentTool)],
    storage=storage,
    routing='actor',
    jwt_secret=config.JWT_SECRET,
    static_dir=os.path.join(_HERE, 'static'),
    ssr='full',
    name='Veille',
    version='1.0.0',
    description='Agentic grant monitoring for non-profits',
)

# -- Background scheduler loop ─────────────────────────────────

async def _scheduler_loop():
    """Background loop: check every 15 minutes if a scheduled run is due."""
    CHECK_INTERVAL = 900  # 15 minutes
    await asyncio.sleep(30)  # Let app fully start
    while True:
        try:
            orgs = Organization.list(limit=1)
            data = orgs.get('data', orgs) if isinstance(orgs, dict) else orgs
            if not data:
                await asyncio.sleep(CHECK_INTERVAL)
                continue

            org = data[0]
            enabled = (org.get('schedule_enabled') if isinstance(org, dict)
                       else getattr(org, 'schedule_enabled', False))
            interval = (org.get('schedule_interval_hours') if isinstance(org, dict)
                        else getattr(org, 'schedule_interval_hours', 168))

            if not enabled:
                await asyncio.sleep(CHECK_INTERVAL)
                continue

            # Avoid overlapping runs
            all_runs = Run.list(sql_filter=("type = ?", ['full']), limit=1000)
            runs_data = all_runs.get('data', all_runs) if isinstance(all_runs, dict) else all_runs
            running = [r for r in runs_data
                       if (r.get('status') if isinstance(r, dict)
                           else getattr(r, 'status', '')) == 'running']
            if running:
                await asyncio.sleep(CHECK_INTERVAL)
                continue

            # Find last completed full run
            completed = [r for r in runs_data
                         if (r.get('completed_at') if isinstance(r, dict)
                             else getattr(r, 'completed_at', None))]
            now = datetime.now(timezone.utc)
            should_run = True
            if completed:
                last_run = max(completed, key=lambda r: (
                    r.get('completed_at') if isinstance(r, dict)
                    else getattr(r, 'completed_at', '')))
                last_ts_str = (last_run.get('completed_at') if isinstance(last_run, dict)
                               else getattr(last_run, 'completed_at', None))
                if last_ts_str:
                    try:
                        last_ts = datetime.fromisoformat(last_ts_str)
                        if last_ts.tzinfo is None:
                            last_ts = last_ts.replace(tzinfo=timezone.utc)
                        elapsed_hours = (now - last_ts).total_seconds() / 3600
                        should_run = elapsed_hours >= interval
                    except (ValueError, TypeError):
                        pass

            if should_run:
                logger.info("Triggering scheduled full run")
                try:
                    run_record = Run.create(Run(type='full', status='pending'))
                    run_id = (run_record.get('id') if isinstance(run_record, dict)
                              else getattr(run_record, 'id', None))
                    if run_id:
                        raw = Run.get(run_id)
                        run_instance = Run(**raw) if isinstance(raw, dict) else raw
                        system_user = {'user_id': 0, 'role': 'system', 'email': 'scheduler@veille'}
                        async for _ in run_instance.execute(user=system_user):
                            pass

                        # Batch analysis for un-analyzed grants (no UI to drive streaming)
                        grant_data = Grant.list(
                            sql_filter=('run_id = ? AND status = ?', [run_id, 'new']),
                            limit=200,
                        )
                        glist = (grant_data.get('data', grant_data)
                                 if isinstance(grant_data, dict) else grant_data)
                        for g in glist:
                            gid = g.get('id') if isinstance(g, dict) else getattr(g, 'id', None)
                            if gid:
                                await Run._analyze_grant_background(gid)

                        logger.info(f"Scheduled run {run_id} complete")
                except Exception as e:
                    logger.error(f"Scheduled run failed: {e}")

        except Exception as e:
            logger.error(f"Scheduler loop error: {e}")

        await asyncio.sleep(CHECK_INTERVAL)


async def _start_scheduler():
    asyncio.create_task(_scheduler_loop())


app.router.on_startup.append(_start_scheduler)


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
        uvicorn.run('main:app', host=config.HOST, port=config.PORT, reload=True, log_config=None)
    else:
        uvicorn.run(app, host=config.HOST, port=config.PORT, log_config=None)
