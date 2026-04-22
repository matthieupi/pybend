# Create Pygentic example app skeleton

**ID:** task-07 | **Wave:** 4 | **Depends on:** task-01, task-02

## Intent

The Pygentic app is a kitchen-sink example showcasing all agent features: agent management, live activity view, streaming, and tool integration. This task creates the app structure following the exact pattern of examples/grants/.

## Context

Example apps follow a standard structure: config.py (deployment config), main.py (create_app factory), models/ directory, seed.py, static/index.html, tests/ directory. The grants example at examples/grants/ is the reference pattern.

Key patterns from grants:
- config.py imports n3tx_core.config and calls configure()
- main.py uses create_app() with routing='actor' for Level 3
- Models extend ActorModel, use ClassVar for class-level config
- User extends BaseUser + ActorModel (for actor + auth capabilities)
- seed.py registers models manually and creates records
- Tests use session-scoped fixtures for DB, seed data, client, tokens

Differences from grants:
- Pygentic includes a Task model with __agent__ = True
- Pygentic includes a Memory placeholder model
- DB file: pygentic.db
- Brand: 'Pygentic'

## Instructions

Create the following files under /workspace/examples/pygentic/:

**1. /workspace/examples/pygentic/__init__.py** — empty

**2. /workspace/examples/pygentic/config.py** — copy from grants, change DB name:
```python
"""Local deployment config — edit these values per deployment."""
import os

from n3tx_core import config as _fw

HOST = os.environ.get("N3TX_HOST", "0.0.0.0")
PORT = int(os.environ.get("N3TX_PORT", "5000"))
API_URL = os.environ.get("N3TX_API_URL", f"http://localhost:{PORT}")
SQLITE_DB_FILE = os.environ.get("N3TX_SQLITE_DB", "pygentic.db")
JWT_SECRET = os.environ.get("N3TX_JWT_SECRET", "ntx-dev-secret-change-in-production")
JWT_EXPIRY_HOURS = int(os.environ.get("N3TX_JWT_EXPIRY_HOURS", "24"))
DEBUG = os.environ.get("N3TX_DEBUG", "true").lower() == "true"
SSR = os.environ.get("N3TX_SSR", "full")

_fw.configure(host=HOST, port=PORT, api_url=API_URL,
              sqlite_db_file=SQLITE_DB_FILE, jwt_secret=JWT_SECRET,
              jwt_expiry_hours=JWT_EXPIRY_HOURS, debug=DEBUG, ssr=SSR)
```

**3. /workspace/examples/pygentic/models/__init__.py**:
```python
from .user import User
from .task import Task
from .memory import Memory

__all__ = ['User', 'Task', 'Memory']
```

**4. /workspace/examples/pygentic/models/user.py**:
```python
from __future__ import annotations
from typing import ClassVar, Optional
from pydantic import Field

from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.models.base_user import BaseUser


class User(BaseUser, ActorModel):
    __tablename__: ClassVar[str] = 'users'
    __abstract__: ClassVar[bool] = False
    __ui__: ClassVar[dict] = {
        'renderer': {'item': 'ntx-user'},
    }

    image: str = Field(
        default='https://ui-avatars.com/api/?name=User&background=94a3b8&color=fff&size=128&rounded=true'
    )
```

**5. /workspace/examples/pygentic/models/task.py**:
```python
from __future__ import annotations
from typing import ClassVar, Literal, Optional
from pydantic import Field

from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.authorize import ANYONE, AUTHENTICATED, OWNER, ROLE
from n3tx_core.utils.decorators import expose_route


class Task(ActorModel):
    """A task with agent-powered analysis."""

    __tablename__: ClassVar[str] = 'tasks'
    __storable__: ClassVar[bool] = True
    __agent__: ClassVar = True
    __protected_fields__: ClassVar[set] = {'user_owner'}
    __access__: ClassVar[dict] = {
        'read': ANYONE,
        'create': AUTHENTICATED,
        'update': OWNER | ROLE('admin'),
        'delete': ROLE('admin'),
    }
    __ui__: ClassVar[dict] = {
        'field_order': ['title', 'status', 'priority', 'description', 'assignee'],
    }

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default='', json_schema_extra={'ui': {'widget': 'textarea'}})
    status: Literal['open', 'in_progress', 'done'] = Field(default='open')
    priority: Literal['low', 'medium', 'high', 'critical'] = Field(default='medium')
    assignee: str = Field(default='')
    user_owner: Optional[int] = Field(default=None)

    @expose_route('/analyze', methods=['POST'], stream=True, access=AUTHENTICATED)
    async def analyze(self, task: str = '', user=None):
        """Analyze this task using agent reasoning."""
        query = task or f'Analyze this task: {self.title}. {self.description}'
        async for chunk in self.agentic_stream(task=query, user=user):
            yield chunk
```

**6. /workspace/examples/pygentic/models/memory.py**:
```python
from __future__ import annotations
from typing import ClassVar, Optional
from pydantic import Field

from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.authorize import AUTHENTICATED, OWNER, ROLE


class Memory(ActorModel):
    """Long-term memory store for agents — placeholder model."""

    __tablename__: ClassVar[str] = 'memories'
    __storable__: ClassVar[bool] = True
    __protected_fields__: ClassVar[set] = {'user_owner'}
    __access__: ClassVar[dict] = {
        'read': AUTHENTICATED,
        'create': AUTHENTICATED,
        'update': OWNER | ROLE('admin'),
        'delete': OWNER | ROLE('admin'),
    }

    content: str = Field(min_length=1)
    category: str = Field(default='fact')
    agent_id: str = Field(default='')
    tags: list = Field(default=[])
    relevance: float = Field(default=1.0, ge=0.0, le=1.0)
    user_owner: Optional[int] = Field(default=None)
```

**7. /workspace/examples/pygentic/main.py**:
```python
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
    join_models=[(AgentActor, AgentTool)],
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
```

## Conventions

Import style: from n3tx_actors.models.actor_model import ActorModel. ClassVar for class-level config (__tablename__, __storable__, etc.). Field types from pydantic. Access control from n3tx_core.authorize. Example apps use sys.path.insert for development mode.

## Files

**Read:** - /workspace/examples/grants/main.py
- /workspace/examples/grants/config.py
- /workspace/examples/grants/models/__init__.py
- /workspace/examples/grants/models/user.py
- /workspace/examples/grants/models/grant.py

**Modify:** none

**Create:** - /workspace/examples/pygentic/__init__.py
- /workspace/examples/pygentic/config.py
- /workspace/examples/pygentic/models/__init__.py
- /workspace/examples/pygentic/models/user.py
- /workspace/examples/pygentic/models/task.py
- /workspace/examples/pygentic/models/memory.py
- /workspace/examples/pygentic/main.py

## Verification

**Commands:**
- `cd /workspace/examples/pygentic && python3 -c "import config; from models import User, Task, Memory; print('Models OK')"`
- `cd /workspace/examples/pygentic && python3 -c "from main import app; print('App created:', type(app).__name__)"`

**Checks:**
- config.py configures framework correctly
- All 3 models import successfully
- Task model has __agent__ = True
- Task has /analyze streaming method
- Memory has access control
- main.py creates app with routing='actor'
- main.py includes AgentActor and AgentTool in model list
