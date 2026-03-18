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
        llm='ollama:qwen3.5:9b',
        constraints={'max_iterations': 20},
    )
    created_general = AgentActor.create(general)
    logger.info('  + Agent: %s (id=%s)', created_general.name, created_general.id)

    analyzer = AgentActor(
        name='Task Analyzer',
        prompt='You are a task analysis expert. Analyze tasks for complexity, risk, dependencies, and suggest improvements. Be thorough but concise.',
        llm='ollama:qwen3.5:9b',
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
