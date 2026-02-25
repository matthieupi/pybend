"""
Seed script — populates the database with sample data.

Usage:
    python seed.py          # seed (creates DB if needed)
    python seed.py --reset  # delete DB and re-seed from scratch
"""

import logging
import os
import sys
from datetime import datetime

from pybend.core import config

logger = logging.getLogger('pybend.seed')
from pybend.core.storage.sqlite_storage import SQLiteStorage
from pybend.example.models import Product, Comment, Like, User, Bot
from pybend.core.models.proto_model import generate_join_model
from pybend.core.utils.registrar import register_model, join_models
from pybend.core.authorize import hash_password

# Database path — resolve relative to this file so it's stable regardless of CWD
_HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_HERE, config.SQLITE_DB_FILE)


def seed():
    # ── Storage & model registration ──
    storage = SQLiteStorage(DB_PATH)
    register_model(Product, storage=storage)
    register_model(User, storage=storage)
    register_model(generate_join_model(Product, Comment), storage=storage)
    register_model(generate_join_model(Comment, Like), storage=storage)
    register_model(generate_join_model(Product, Like), storage=storage)

    # ── Users ──
    users = [
        {"name": "Alice Martin",   "email": "alice@example.com",   "password": "alice123",  "age": 28,
         "image": "https://api.dicebear.com/9.x/avataaars/svg?seed=Alice"},
        {"name": "Bob Johnson",    "email": "bob@example.com",     "password": "bob123",    "age": 34,
         "image": "https://api.dicebear.com/9.x/avataaars/svg?seed=Bob"},
        {"name": "Charlie Lee",    "email": "charlie@example.com", "password": "charlie123", "age": 22,
         "image": "https://api.dicebear.com/9.x/avataaars/svg?seed=Charlie"},
    ]

    created_users = []
    for u in users:
        pw = u.pop("password")
        user = User(**u)
        user._plain_password = pw
        created = User.create(user)
        created_users.append(created)
        logger.info("  + User: %s (%s)", created.name, created.email)

    # ── Products ──
    products = [
        {"name": "Wireless Headphones", "price": 79.99,  "description": "Noise-cancelling over-ear headphones with 30h battery life.",
         "image": "https://picsum.photos/seed/headphones/400/300"},
        {"name": "Mechanical Keyboard", "price": 129.50, "description": "Cherry MX Brown switches, RGB backlight, TKL layout.",
         "image": "https://picsum.photos/seed/keyboard/400/300"},
        {"name": "USB-C Hub",           "price": 45.00,  "description": "7-in-1 hub: HDMI, USB-A x3, SD, microSD, PD charging.",
         "image": "https://picsum.photos/seed/usbhub/400/300"},
        {"name": "Standing Desk Mat",   "price": 39.99,  "description": "Anti-fatigue ergonomic mat, 20x34 inches.",
         "image": "https://picsum.photos/seed/deskmat/400/300"},
        {"name": "Monitor Light Bar",   "price": 54.95,  "description": "Asymmetric LED light bar, adjustable color temperature.",
         "image": "https://picsum.photos/seed/lightbar/400/300"},
    ]

    created_products = []
    for p in products:
        product = Product(**p)
        created = Product.create(product)
        created_products.append(created)
        logger.info("  + Product: %s ($%s)", created.name, created.price)

    # ── Comments (on products) ──
    comments = [
        {"product_idx": 0, "user_idx": 1, "name": "Great sound",       "description": "Best headphones I've owned. ANC is incredible."},
        {"product_idx": 0, "user_idx": 2, "name": "Comfortable",       "description": "Wore them for 8 hours straight, no issues."},
        {"product_idx": 1, "user_idx": 0, "name": "Perfect for coding", "description": "The tactile feedback is just right. Love the layout."},
        {"product_idx": 1, "user_idx": 2, "name": "A bit loud",        "description": "Switches are louder than expected in a quiet office."},
        {"product_idx": 2, "user_idx": 0, "name": "Works perfectly",   "description": "All ports recognized immediately on macOS and Linux."},
        {"product_idx": 3, "user_idx": 1, "name": "Feet love it",      "description": "Standing all day is much easier with this mat."},
        {"product_idx": 4, "user_idx": 0, "name": "No more eye strain", "description": "Huge difference for late-night work sessions."},
        {"product_idx": 4, "user_idx": 1, "name": "Easy to install",   "description": "Clips right onto the monitor, no tools needed."},
    ]

    created_comments = []
    for c in comments:
        product = created_products[c["product_idx"]]
        user = created_users[c["user_idx"]]
        comment = Comment(name=c["name"], description=c["description"], user_owner=user.id)
        comment.__owner__ = product
        created = comment.save()
        created_comments.append(created)
        logger.info("  + Comment on '%s' by %s: %s", product.name, user.name, c['name'])

    # ── Nested replies (using parent_id) ──
    replies = [
        {"parent_idx": 0, "product_idx": 0, "user_idx": 0, "name": "Agreed!",        "description": "The ANC on these is next level."},
        {"parent_idx": 0, "product_idx": 0, "user_idx": 2, "name": "Which model?",    "description": "Are you talking about the v2 or v3?"},
        {"parent_idx": 2, "product_idx": 1, "user_idx": 1, "name": "Same here",       "description": "Cherry Browns are the sweet spot for me too."},
    ]

    for r in replies:
        parent = created_comments[r["parent_idx"]]
        product = created_products[r["product_idx"]]
        user = created_users[r["user_idx"]]
        reply = Comment(
            name=r["name"],
            description=r["description"],
            user_owner=user.id,
            parent_id=parent.id,
        )
        reply.__owner__ = product
        reply.save()
        logger.info("  + Reply to '%s' by %s: %s", parent.name, user.name, r['name'])

    # ── Likes on comments ──
    like_data = [
        {"comment_idx": 0, "user_idx": 0},  # Alice likes "Great sound"
        {"comment_idx": 0, "user_idx": 2},  # Charlie likes "Great sound"
        {"comment_idx": 2, "user_idx": 1},  # Bob likes "Perfect for coding"
        {"comment_idx": 4, "user_idx": 1},  # Bob likes "Works perfectly"
        {"comment_idx": 6, "user_idx": 2},  # Charlie likes "No more eye strain"
    ]

    for ld in like_data:
        comment = created_comments[ld["comment_idx"]]
        user = created_users[ld["user_idx"]]
        like = Like(user=user.id, created_at=datetime.now().isoformat())
        like.__owner__ = comment
        like.save()
        logger.info("  + Like on '%s' by %s", comment.name, user.name)

    # ── Favorites on products ──
    fav_data = [
        {"product_idx": 0, "user_idx": 0},  # Alice favorites Headphones
        {"product_idx": 1, "user_idx": 0},  # Alice favorites Keyboard
        {"product_idx": 0, "user_idx": 1},  # Bob favorites Headphones
        {"product_idx": 2, "user_idx": 2},  # Charlie favorites USB-C Hub
        {"product_idx": 4, "user_idx": 1},  # Bob favorites Monitor Light Bar
    ]

    for fd in fav_data:
        product = created_products[fd["product_idx"]]
        user = created_users[fd["user_idx"]]
        fav = Like(user=user.id, created_at=datetime.now().isoformat())
        fav.__owner__ = product
        fav.save()
        logger.info("  + Favorite '%s' by %s", product.name, user.name)

    logger.info(
        "Done. Seeded %d users, %d products, %d comments, %d replies, %d likes, %d favorites.",
        len(created_users), len(created_products), len(comments),
        len(replies), len(like_data), len(fav_data),
    )


if __name__ == "__main__":
    if "--reset" in sys.argv:
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
            print(f"Deleted {DB_PATH}")

    if User.storage and User.list():
        print("Database already has data. Use --reset to wipe and re-seed.")
        sys.exit(0)

    print("Seeding database...")
    seed()
