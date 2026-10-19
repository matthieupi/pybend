"""Pygentic — Agent management and live activity showcase.

Usage:
    cd /workspace/examples/pygentic && python main.py
"""
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import config
from n3tx_core.app import create_app
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_agents.actor import AgentActor
from n3tx_agents.tool_model import AgentTool
from models import User, Task, Memory

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')

_HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get('N3TX_SQLITE_DB') or os.path.join(_HERE, 'pygentic.db')

storage = SQLiteStorage(DB_PATH)
app = create_app(
    models=[User, Task, Memory, AgentTool, AgentActor],
    storage=storage,
    routing='actor',
    static_dir=os.path.join(_HERE, 'static'),
    jwt_secret=config.JWT_SECRET,
    name='Pygentic',
    version='0.10.0',
    description='Agent management, live view, and memory showcase',
)

if __name__ == '__main__':
    import uvicorn
    if config.DEBUG:
        uvicorn.run('main:app', host=config.HOST, port=config.PORT, reload=True)
    else:
        uvicorn.run(app, host=config.HOST, port=config.PORT)
