"""N3TX Chat Example — multi-turn LLM chat with SSE streaming.

Usage:
    cd /workspace/example_chat && python main.py

Models:
    User         — authentication (BaseUser + ActorModel)
    Conversation — chat agent (__agent__=True), manages message history
    Message      — mirrors pydantic-ai ModelMessage format

Chat uses SSE streaming via @expose_route:
    POST /conversations/{id}/chat  {"content": "hello"}
    → SSE: event: chunk, data: {"text": "token"} ...
    → SSE: event: done,  data: {}

WebSocket is still enabled for real-time sidebar updates (conversation
create/delete lifecycle events).
"""
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import config

# Test mode: use pydantic-ai TestModel instead of real LLM
# Set N3TX_TEST_MODE=1 to enable (used by e2e test conftest)
if os.environ.get('N3TX_TEST_MODE'):
    from pydantic_ai.models.test import TestModel
    from n3tx.core import config as _fw_config
    _fw_config.AGENT_DEFAULTS['llm'] = TestModel()

from n3tx.core.app import create_app
from n3tx.core.storage.sqlite_storage import SQLiteStorage
from n3tx.core.agents.tool_model import AgentTool
from models import User, Conversation, Message

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')

_HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get('N3TX_SQLITE_DB') or os.path.join(_HERE, 'chat.db')

storage = SQLiteStorage(DB_PATH)
app = create_app(
    models=[User, Conversation, Message, AgentTool],
    join_models=[(Conversation, Message), (Conversation, AgentTool)],
    storage=storage,
    routing='actor',
    ws=True,
    static_dir=os.path.join(_HERE, 'static'),
    jwt_secret=config.JWT_SECRET,
    name="N3TX Chat",
    version="0.10.0",
    description="Multi-turn LLM chat with pydantic-ai message history",
)

# ── LLM health-check endpoint ──
# Must be inserted before the static mount (catch-all at "/") to be reachable.
from fastapi import APIRouter

_api_router = APIRouter()

@_api_router.get("/api/llm-status")
async def llm_status():
    """Ping the configured LLM provider and return status."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(config.OLLAMA_BASE_URL)
            return {"status": "ready", "provider": "ollama", "model": config.DEFAULT_LLM}
    except Exception:
        return {"status": "offline", "provider": "ollama", "model": config.DEFAULT_LLM}

# Insert before the last route (static mount) so it doesn't get shadowed
app.router.routes.insert(-1, _api_router.routes[0])


if __name__ == '__main__':
    import uvicorn
    if config.DEBUG:
        uvicorn.run("main:app", host=config.HOST, port=config.PORT, reload=True)
    else:
        uvicorn.run(app, host=config.HOST, port=config.PORT)
