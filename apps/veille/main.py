"""Veille -- Grant monitoring application."""
import logging
import os
import sys

# Add current directory to path for local imports
sys.path.insert(0, os.path.dirname(__file__))

import config  # noqa: E402

# CRITICAL: Must import n3tx_agents BEFORE model imports.
# Registers AgentMixin in proto_model._mixin_registry.
# Without this, __agent__ = True on future models silently does nothing.
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

if __name__ == '__main__':
    import uvicorn
    if config.DEBUG:
        uvicorn.run('main:app', host=config.HOST, port=config.PORT, reload=True)
    else:
        uvicorn.run(app, host=config.HOST, port=config.PORT)
