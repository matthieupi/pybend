"""
Seed script — populates the chat database with sample data.

Usage:
    python seed.py          # seed (creates DB if needed)
    python seed.py --reset  # delete DB and re-seed from scratch
"""
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import config
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_core.utils.registrar import register_model
from models import User, Conversation, Message

logger = logging.getLogger('n3tx.seed')

_HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get('N3TX_SQLITE_DB') or os.path.join(_HERE, 'chat.db')


def seed():
    storage = SQLiteStorage(DB_PATH)

    for model in [User, Conversation, Message]:
        register_model(model, storage=storage)

    # ── Users ──
    users_data = [
        {"name": "Alice Martin", "email": "alice@example.com", "password": "alice123",
         "image": "https://api.dicebear.com/9.x/avataaars/svg?seed=Alice"},
        {"name": "Bob Johnson", "email": "bob@example.com", "password": "bob123",
         "image": "https://api.dicebear.com/9.x/avataaars/svg?seed=Bob"},
    ]
    users = {}
    for u in users_data:
        pw = u.pop("password")
        user = User(**u)
        user._plain_password = pw
        created = User.create(user)
        users[created.name.split()[0].lower()] = created
        logger.info("  + User: %s (%s)", created.name, created.email)

    # ── Sample conversation ──
    conv = Conversation(
        name="Hello World",
        prompt="You are a helpful assistant.",
        user_owner=users["alice"].id,
    )
    created_conv = Conversation.create(conv)
    logger.info("  + Conversation: %s (id=%s)", created_conv.name, created_conv.id)

    logger.info("Seeding complete.")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')

    if '--reset' in sys.argv:
        if os.path.exists(DB_PATH):
            os.unlink(DB_PATH)
            logger.info("Deleted %s", DB_PATH)

    seed()
