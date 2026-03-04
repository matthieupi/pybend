"""PyBend Grant-Watching Example — an agentic app that scans for government grants.

Usage:
    cd /workspace/example_grants && python main.py

Models:
    User        — authentication (inherited from BaseUser)
    Grant       — discovered grant records
    Source      — websites to scan for grants
    WebTools    — web scraping utilities (no storage, methods only)
    AgentActor  — dynamic agents (the Grant Scanner is an instance)

The Grant Scanner agent is seeded by seed.py. Trigger it via:
    POST /agents/1/run {"task": "Scan all sources for new grants"}
"""
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import config
from pybend.core.app import create_app
from pybend.core.storage.sqlite_storage import SQLiteStorage
from pybend.core.agents.actor import AgentActor
from pybend.core.agents.tool_model import AgentTool
from models import User, Grant, Source, WebTools

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')

_HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get('PYBEND_SQLITE_DB') or os.path.join(_HERE, 'grants.db')

storage = SQLiteStorage(DB_PATH)
app = create_app(
    models=[User, Grant, Source, WebTools, AgentTool, AgentActor],
    join_models=[(AgentActor, AgentTool)],
    storage=storage,
    routing='actor',
    static_dir=os.path.join(_HERE, 'static'),
    jwt_secret=config.JWT_SECRET,
    name="Grant Watcher",
    version="0.10.0",
    description="Agentic grant-watching application",
)

# Run manual migrations (after create_app which handles auto-migration for new columns)
storage._migration.migrations_dir = os.path.join(_HERE, 'migrations')
storage._migration.run_migrations()

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host=config.HOST, port=config.PORT)
