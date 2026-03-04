"""
Performance seed script — populates the database for profiling.

Supports incremental seeding at different scale tiers:
    python -m n3tx.core.tests.profiling.seed_perf --tier empty      # 0 records
    python -m n3tx.core.tests.profiling.seed_perf --tier small      # ~36 records
    python -m n3tx.core.tests.profiling.seed_perf --tier medium     # ~197 records
    python -m n3tx.core.tests.profiling.seed_perf --tier large      # ~433 records
    python -m n3tx.core.tests.profiling.seed_perf --tier full       # ~2000 records
    python -m n3tx.core.tests.profiling.seed_perf --reset --tier full
"""

import logging
import os
import sys
from datetime import datetime

from n3tx.core import config

logger = logging.getLogger('n3tx.seed_perf')
logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')

from n3tx.core.storage.sqlite_storage import SQLiteStorage
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..', '..', 'example_api'))
from models import Product, Comment, Like, User, Bot
from n3tx.core.models.proto_model import generate_join_model
from n3tx.core.utils.registrar import register_model, join_models
from n3tx.core.authorize import hash_password

# Database path — use the example app's location for compatibility
_EXAMPLE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..', '..', 'example_api')
DB_PATH = os.path.join(_EXAMPLE_DIR, config.SQLITE_DB_FILE)

# Deterministic data pools
DESCRIPTIONS = [
    "Premium build quality with excellent attention to detail. Highly recommended for daily use.",
    "Good value for the price. Works as expected with no major issues.",
    "Outstanding performance in real-world testing. Exceeds expectations.",
    "Solid design and reliable functionality. A great addition to any setup.",
    "Compact and portable. Perfect for on-the-go professionals.",
    "Impressive battery life and fast charging capabilities.",
    "Ergonomic design reduces fatigue during extended use sessions.",
    "Clean aesthetics that blend seamlessly into any workspace.",
    "Feature-rich without being overwhelming. Intuitive controls.",
    "Durable construction that should last for years of regular use.",
]

COMMENT_TITLES = [
    "Great product!", "Highly recommend", "Worth every penny", "Decent quality",
    "Love it", "Not bad", "Excellent choice", "Solid purchase",
    "Perfect for work", "Very satisfied", "Good but pricey", "Best I've owned",
    "Impressive quality", "Does the job", "Exceeded expectations", "Really useful",
    "Fantastic design", "Works perfectly", "Amazing value", "Top notch",
]

COMMENT_BODIES = [
    "I've been using this for weeks now and it's held up perfectly.",
    "The quality is really impressive at this price point.",
    "Setup was quick and easy, everything works out of the box.",
    "Compared to similar products, this one stands out significantly.",
    "Would definitely buy again. My colleagues are jealous.",
    "The packaging was premium and the product matches that expectation.",
    "I was skeptical at first but this really delivers on its promises.",
    "Customer support was helpful when I had a question about features.",
    "The build materials feel premium and should last a long time.",
    "Perfect for my workflow. Saves me time every single day.",
    "My second purchase from this brand and still very satisfied.",
    "Fits perfectly on my desk without taking up too much space.",
    "The color temperature adjustment is surprisingly useful.",
    "Battery lasts even longer than advertised in my experience.",
    "Compatible with all my devices without any driver issues.",
    "The noise cancellation is a game changer for open offices.",
    "Lightweight enough to carry in a bag without noticing it.",
    "The texture and finish feel much more expensive than the price.",
    "Fast shipping and the product was exactly as described online.",
    "This replaced my old setup entirely and I couldn't be happier.",
]

PRODUCT_NAMES = [
    "Wireless Headphones", "Mechanical Keyboard", "USB-C Hub",
    "Standing Desk Mat", "Monitor Light Bar", "Webcam HD Pro",
    "Laptop Stand", "Desk Organizer", "Cable Management Kit",
    "Portable SSD 1TB", "Bluetooth Speaker", "Wireless Mouse",
    "Screen Protector Pack", "Phone Stand", "USB Microphone",
    "Noise Machine", "Desk Lamp LED", "Keyboard Wrist Rest",
    "Monitor Arm", "Power Strip Smart", "HDMI Switch 4K",
    "Ethernet Adapter", "Wireless Charger", "Webcam Cover",
    "Mini Projector",
]

PRODUCT_PRICES = [
    79.99, 129.50, 45.00, 39.99, 54.95, 89.00, 49.95, 24.99,
    19.99, 109.00, 59.95, 34.99, 12.99, 15.00, 69.99, 29.95,
    42.00, 22.50, 149.00, 35.00, 27.99, 18.95, 39.00, 8.99, 199.00,
]

USER_DATA = [
    {"name": "Alice Martin",   "email": "alice@example.com",   "password": "alice123",   "age": 28},
    {"name": "Bob Johnson",    "email": "bob@example.com",     "password": "bob123",     "age": 34},
    {"name": "Charlie Lee",    "email": "charlie@example.com", "password": "charlie123", "age": 22},
    {"name": "Diana Park",    "email": "diana@example.com",    "password": "diana123",   "age": 31},
    {"name": "Eve Torres",    "email": "eve@example.com",      "password": "eve123",     "age": 27},
    {"name": "Frank Wu",      "email": "frank@example.com",    "password": "frank123",   "age": 40},
    {"name": "Grace Kim",     "email": "grace@example.com",    "password": "grace123",   "age": 25},
    {"name": "Henry Patel",   "email": "henry@example.com",    "password": "henry123",   "age": 36},
]

# Tier configs: (num_users, num_products, comments_per_product, replies_ratio, likes_per_comment, favs_per_product)
TIERS = {
    'empty':  (0, 0, 0, 0, 0, 0),
    'small':  (3, 5, 2, 4, 1, 1),
    'medium': (5, 12, 4, 4, 2, 2),
    'large':  (8, 25, 4, 4, 2, 3),
    'full':   (8, 50, 8, 3, 3, 5),
}


def tier_record_count(tier):
    """Compute total DB records for a tier from the TIERS config."""
    num_users, num_products, cmt_per_prod, reply_ratio, likes_per_cmt, favs_per_prod = TIERS[tier]
    if num_users == 0:
        return 0
    comments = num_products * cmt_per_prod
    replies = len(range(0, comments, reply_ratio)) if reply_ratio > 0 and comments > 0 else 0
    likes = comments * likes_per_cmt
    favorites = num_products * favs_per_prod
    return num_users + num_products + comments + replies + likes + favorites


def seed(tier='full'):
    storage = SQLiteStorage(DB_PATH)
    register_model(Product, storage=storage)
    register_model(User, storage=storage)
    register_model(generate_join_model(Product, Comment), storage=storage)
    register_model(generate_join_model(Comment, Like), storage=storage)
    register_model(generate_join_model(Product, Like), storage=storage)

    num_users, num_products, cmt_per_prod, reply_ratio, likes_per_cmt, favs_per_prod = TIERS[tier]

    if num_users == 0:
        logger.info("Tier 'empty': models registered, no data seeded.")
        return {'users': 0, 'products': 0, 'comments': 0, 'replies': 0, 'likes': 0, 'favorites': 0}

    # Users
    created_users = []
    for i in range(num_users):
        u = USER_DATA[i].copy()
        pw = u.pop("password")
        u["image"] = f"https://api.dicebear.com/9.x/avataaars/svg?seed={u['name'].split()[0]}"
        user = User(**u)
        user._plain_password = pw
        created = User.create(user)
        created_users.append(created)
    logger.info("  Created %d users", len(created_users))

    # Products
    created_products = []
    for i in range(num_products):
        p = Product(
            name=PRODUCT_NAMES[i % len(PRODUCT_NAMES)],
            price=PRODUCT_PRICES[i % len(PRODUCT_PRICES)],
            description=DESCRIPTIONS[i % len(DESCRIPTIONS)],
            image=f"https://picsum.photos/seed/product{i}/400/300",
        )
        created = Product.create(p)
        created_products.append(created)
    logger.info("  Created %d products", len(created_products))

    # Comments on products
    created_comments = []
    for pi, product in enumerate(created_products):
        for ci in range(cmt_per_prod):
            idx = pi * cmt_per_prod + ci
            user = created_users[idx % len(created_users)]
            comment = Comment(
                name=COMMENT_TITLES[idx % len(COMMENT_TITLES)],
                description=COMMENT_BODIES[idx % len(COMMENT_BODIES)],
                user_owner=user.id,
            )
            comment.__owner__ = product
            created = comment.save()
            created_comments.append(created)
    logger.info("  Created %d comments", len(created_comments))

    # Replies (~1 per reply_ratio comments)
    reply_count = 0
    if reply_ratio > 0 and created_comments:
        for ci in range(0, len(created_comments), reply_ratio):
            parent = created_comments[ci]
            user = created_users[(ci + 1) % len(created_users)]
            prod_idx = ci // cmt_per_prod if cmt_per_prod > 0 else 0
            product = created_products[prod_idx % len(created_products)]
            reply = Comment(
                name=f"Re: {parent.name}"[:500],
                description=COMMENT_BODIES[(ci + 5) % len(COMMENT_BODIES)],
                user_owner=user.id,
                parent_id=parent.id,
            )
            reply.__owner__ = product
            reply.save()
            reply_count += 1
    logger.info("  Created %d replies", reply_count)

    # Likes on comments
    like_count = 0
    if likes_per_cmt > 0 and created_comments:
        for ci, comment in enumerate(created_comments):
            for li in range(likes_per_cmt):
                user = created_users[(ci + li + 1) % len(created_users)]
                like = Like(user=user.id, created_at=datetime.now().isoformat())
                like.__owner__ = comment
                like.save()
                like_count += 1
    logger.info("  Created %d comment likes", like_count)

    # Favorites on products
    fav_count = 0
    if favs_per_prod > 0 and created_products:
        for pi, product in enumerate(created_products):
            for fi in range(favs_per_prod):
                user = created_users[(pi + fi) % len(created_users)]
                fav = Like(user=user.id, created_at=datetime.now().isoformat())
                fav.__owner__ = product
                fav.save()
                fav_count += 1
    logger.info("  Created %d product favorites", fav_count)

    totals = {
        'users': len(created_users),
        'products': len(created_products),
        'comments': len(created_comments),
        'replies': reply_count,
        'likes': like_count,
        'favorites': fav_count,
    }
    total = sum(totals.values())
    logger.info("Done. Seeded %d total records: %s", total, totals)
    return totals


if __name__ == "__main__":
    tier = 'full'
    for arg in sys.argv[1:]:
        if arg == '--reset':
            if os.path.exists(DB_PATH):
                os.remove(DB_PATH)
                print(f"Deleted {DB_PATH}")
        elif arg.startswith('--tier'):
            if '=' in arg:
                tier = arg.split('=', 1)[1]
            else:
                idx = sys.argv.index(arg)
                if idx + 1 < len(sys.argv):
                    tier = sys.argv[idx + 1]

    if tier not in TIERS:
        print(f"Unknown tier '{tier}'. Available: {list(TIERS.keys())}")
        sys.exit(1)

    if tier != 'empty' and User.storage and User.list():
        print("Database already has data. Use --reset to wipe and re-seed.")
        sys.exit(0)

    print(f"Seeding database (tier={tier})...")
    seed(tier)
