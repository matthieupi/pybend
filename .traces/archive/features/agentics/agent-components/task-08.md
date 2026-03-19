# Create Pygentic seed.py and static/index.html

**ID:** task-08 | **Wave:** 4 | **Depends on:** task-07

## Intent

The seed script populates the database with sample data (users, agents, tasks, tool assignments) for development and testing. The index.html provides the frontend dashboard layout showcasing all agent components.

## Context

seed.py follows the pattern from examples/grants/seed.py: register models, create users (with _plain_password), create domain records, create agents with tool assignments via join table.

index.html follows the pattern from examples/grants/static/index.html: modulepreload chain, component imports, ntx-topbar + ntx-sidebar + ntx-router layout. The Pygentic version adds ntx-agent-live and ntx-chat components.

The static directory needs to serve files from both n3tx-ui (components, widgets, themes) and n3tx-agents (ntx-chat.js, ntx-agent-live.js). The create_app() factory handles static file serving from multiple packages via the n3tx-ui get_static_dir() + the app's own static_dir.

## Instructions

Create two files:

**1. /workspace/examples/pygentic/seed.py**:
```python
"""Seed script — populates the Pygentic database with sample data.

Usage:
    python seed.py          # seed
    python seed.py --reset  # delete DB and re-seed
"""
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import config
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_core.utils.registrar import register_model
from n3tx_core.models.proto_model import generate_join_model
from n3tx_agents.actor import AgentActor
from n3tx_agents.tool_model import AgentTool
from models import User, Task, Memory

logger = logging.getLogger('n3tx.seed')

_HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get('N3TX_SQLITE_DB') or os.path.join(_HERE, 'pygentic.db')


def seed():
    storage = SQLiteStorage(DB_PATH)

    for model in [User, Task, Memory, AgentTool, AgentActor]:
        register_model(model, storage=storage)

    join_cls = generate_join_model(AgentActor, AgentTool)
    register_model(join_cls, storage=storage)

    # ── Users ──
    users = [
        {'name': 'Alice Martin', 'email': 'alice@example.com', 'password': 'alice123',
         'image': 'https://api.dicebear.com/9.x/avataaars/svg?seed=Alice'},
        {'name': 'Bob Johnson', 'email': 'bob@example.com', 'password': 'bob123',
         'image': 'https://api.dicebear.com/9.x/avataaars/svg?seed=Bob'},
        {'name': 'Charlie Dev', 'email': 'charlie@example.com', 'password': 'charlie123',
         'image': 'https://api.dicebear.com/9.x/avataaars/svg?seed=Charlie'},
    ]
    created_users = {}
    for u in users:
        pw = u.pop('password')
        user = User(**u)
        user._plain_password = pw
        created = User.create(user)
        created_users[created.name.split()[0].lower()] = created
        logger.info('  + User: %s (%s)', created.name, created.email)

    # ── Tasks ──
    tasks_data = [
        {'title': 'Set up CI pipeline', 'description': 'Configure GitHub Actions for automated testing and deployment.', 'status': 'open', 'priority': 'high', 'user_owner': created_users['alice'].id},
        {'title': 'Review authentication flow', 'description': 'Audit the JWT-based auth system for security issues.', 'status': 'in_progress', 'priority': 'critical', 'assignee': 'Bob', 'user_owner': created_users['bob'].id},
        {'title': 'Write API documentation', 'description': 'Document all REST endpoints with examples.', 'status': 'open', 'priority': 'medium', 'user_owner': created_users['alice'].id},
        {'title': 'Optimize database queries', 'description': 'Profile slow queries and add indexes.', 'status': 'done', 'priority': 'medium', 'user_owner': created_users['charlie'].id},
        {'title': 'Design notification system', 'description': 'Plan WebSocket-based real-time notifications.', 'status': 'open', 'priority': 'low', 'user_owner': created_users['alice'].id},
    ]
    for t in tasks_data:
        created = Task.create(Task(**t))
        logger.info('  + Task: %s (%s)', created.title, created.status)

    # ── Agents ──
    general = AgentActor(
        name='General Assistant',
        prompt='You are a helpful general assistant. You can manage tasks and memories. Be concise and action-oriented.',
        llm='ollama:llama3.1',
        constraints={'max_iterations': 20},
    )
    created_general = AgentActor.create(general)
    logger.info('  + Agent: %s (id=%s)', created_general.name, created_general.id)

    analyzer = AgentActor(
        name='Task Analyzer',
        prompt='You are a task analysis expert. Analyze tasks for complexity, risk, dependencies, and suggest improvements. Be thorough but concise.',
        llm='ollama:llama3.1',
        constraints={'max_iterations': 10},
    )
    created_analyzer = AgentActor.create(analyzer)
    logger.info('  + Agent: %s (id=%s)', created_analyzer.name, created_analyzer.id)

    # ── Tool assignments ──
    tool_data = [
        (created_general.id, [('tasks', 'Task CRUD'), ('memories', 'Memory store')]),
        (created_analyzer.id, [('tasks', 'Task CRUD')]),
    ]
    for agent_id, tools in tool_data:
        for target, desc in tools:
            record = join_cls(target=target, description=desc, agentactor_id=agent_id)
            join_cls.create(record)
            logger.info('  + Tool: %s -> agent %s', target, agent_id)

    logger.info('Seeding complete.')


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')
    if '--reset' in sys.argv:
        if os.path.exists(DB_PATH):
            os.unlink(DB_PATH)
            logger.info('Deleted %s', DB_PATH)
    seed()
```

**2. /workspace/examples/pygentic/static/index.html**:
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Pygentic</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="./dark-theme.css">
    <link rel="stylesheet" href="./light-theme.css">
    <link rel="icon" type="image/svg+xml" href="./favicon.svg">
    <link rel="preload" href="./components/ntx-item.css" as="style">
    <link rel="preload" href="./components/ntx-list.css" as="style">
    <link rel="preload" href="./components/ntx-router.css" as="style">
    <link rel="preload" href="./components/ntx-topbar.css" as="style">
    <link rel="preload" href="./components/ntx-sidebar.css" as="style">
    <link rel="preload" href="./components/ntx-table.css" as="style">
    <link rel="preload" href="./components/ntx-row.css" as="style">
    <link rel="preload" href="./components/ntx-user.css" as="style">
    <link rel="preload" href="./widgets/widgets.css" as="style">
    <script src="./vendor/marked.min.js"></script>
    <script src="./vendor/ansi_up.min.js"></script>
    <link rel="modulepreload" href="./config.js">
    <link rel="modulepreload" href="./utils/Assert.js">
    <link rel="modulepreload" href="./utils/Logging.js">
    <link rel="modulepreload" href="./utils/Permissions.js">
    <link rel="modulepreload" href="./utils/theme.js">
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
    <link rel="modulepreload" href="./components/ntx-stream.js">
    <link rel="modulepreload" href="./components/ntx-topbar.js">
    <link rel="modulepreload" href="./components/ntx-sidebar.js">
    <link rel="modulepreload" href="./components/ntx-profile.js">
    <link rel="modulepreload" href="./components/ntx-row.js">
    <link rel="modulepreload" href="./components/ntx-user.js">
    <link rel="modulepreload" href="./components/ntx-table.js">
    <link rel="modulepreload" href="./components/ntx-chat.js">
    <link rel="modulepreload" href="./components/ntx-agent-live.js">
    <link rel="modulepreload" href="./generators/form.js">
    <link rel="modulepreload" href="./widgets/Widget.js">
    <link rel="modulepreload" href="./widgets/registry.js">
    <link rel="modulepreload" href="./widgets/index.js">
    <script type="module" src="./utils/theme.js"></script>
</head>
<body>

    <ntx-topbar brand="Pygentic" version="0.10.0" logo="PG"></ntx-topbar>
    <ntx-sidebar router="main">
        <ntx-list model="Task" allow-create></ntx-list>
        <ntx-list model="AgentActor"></ntx-list>
        <ntx-table model="Memory"></ntx-table>
    </ntx-sidebar>

    <div class="page">
        <ntx-router name="main" hash>
            <ntx-table model="Task" id="task-table" allow-create></ntx-table>
        </ntx-router>
    </div>

    <ntx-chat model="AgentActor" method="agentic_stream"></ntx-chat>

    <script type="module">
        import Logging from './utils/Logging.js';
        Logging.init('Loading Pygentic...');

        import {Matrix, matrix} from './core/Matrix.js';
        import { NTT } from './core/NTT.js';
        import { config } from './config.js';
        import { permissions } from './utils/Permissions.js';
        import './components/ntx-item.js';
        import './components/ntx-list.js';
        import './components/ntx-router.js';
        import './components/ntx-method.js';
        import './components/ntx-stream.js';
        import './components/ntx-topbar.js';
        import './components/ntx-sidebar.js';
        import './components/ntx-profile.js';
        import './components/ntx-user.js';
        import './components/ntx-row.js';
        import './components/ntx-table.js';
        import './components/ntx-chat.js';
        import './components/ntx-agent-live.js';

        permissions.init();
    </script>

</body>
</html>
```

## Conventions

seed.py: register models in dependency order (AgentTool before AgentActor). Use generate_join_model() for join tables. Users need _plain_password set before create(). index.html: modulepreload chain covers full dependency tree. Component imports in script module block. ntx-topbar with brand/version/logo attrs. ntx-sidebar with router attribute for navigation.

## Files

**Read:** - /workspace/examples/grants/seed.py
- /workspace/examples/grants/static/index.html

**Modify:** none

**Create:** - /workspace/examples/pygentic/seed.py
- /workspace/examples/pygentic/static/index.html

## Verification

**Commands:**
- `cd /workspace/examples/pygentic && python3 -c "import config; print('Config OK')" && python3 -c "from models import User, Task, Memory; print('Models OK')"`

**Checks:**
- seed.py creates 3 users, 5 tasks, 2 agents, tool assignments
- index.html includes ntx-chat with method=agentic_stream
- index.html imports ntx-agent-live.js
- All modulepreload links are valid paths
