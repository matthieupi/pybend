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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import config

logger = logging.getLogger('n3tx.seed')
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from models import Product, Comment, Like, User, Bot
from n3tx_core.models.proto_model import generate_join_model
from n3tx_core.utils.registrar import register_model, join_models
from n3tx_core.authorize import hash_password

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

    # ── Users (6) ──
    users = [
        {"name": "Alice Martin",   "email": "alice@example.com",   "password": "alice123",  "age": 28,
         "image": "https://api.dicebear.com/9.x/avataaars/svg?seed=Alice"},
        {"name": "Bob Johnson",    "email": "bob@example.com",     "password": "bob123",    "age": 34,
         "image": "https://api.dicebear.com/9.x/avataaars/svg?seed=Bob"},
        {"name": "Charlie Lee",    "email": "charlie@example.com", "password": "charlie123", "age": 22,
         "image": "https://api.dicebear.com/9.x/avataaars/svg?seed=Charlie"},
        {"name": "Diana Park",     "email": "diana@example.com",   "password": "diana123",  "age": 31,
         "image": "https://api.dicebear.com/9.x/avataaars/svg?seed=Diana"},
        {"name": "Ethan Ross",     "email": "ethan@example.com",   "password": "ethan123",  "age": 27,
         "image": "https://api.dicebear.com/9.x/avataaars/svg?seed=Ethan"},
        {"name": "Fiona Chen",     "email": "fiona@example.com",   "password": "fiona123",  "age": 35,
         "image": "https://api.dicebear.com/9.x/avataaars/svg?seed=Fiona"},
    ]

    created_users = []
    for u in users:
        pw = u.pop("password")
        user = User(**u)
        user._plain_password = pw
        created = User.create(user)
        created_users.append(created)
        logger.info("  + User: %s (%s)", created.name, created.email)

    # ── Products (20) ──
    products = [
        # Tech
        {"name": "Wireless Headphones", "price": 79.99,
         "description": "Noise-cancelling over-ear headphones with 30h battery life.",
         "image": "https://fastly.picsum.photos/id/1041/400/300.jpg?hmac=HcI2xbviGnFAbd-4qFp_OCc_mA0ASWzX9cWunjllpTo"},
        {"name": "Mechanical Keyboard", "price": 129.50,
         "description": "Cherry MX Brown switches, RGB backlight, TKL layout.",
         "image": "https://fastly.picsum.photos/id/600/400/300.jpg?hmac=jrhQkia-iBrgN3EgdNp1QjsDthRpU6jTtDVGSEYrtD4"},
        {"name": "USB-C Hub", "price": 45.00,
         "description": "7-in-1 hub: HDMI, USB-A x3, SD, microSD, PD charging.",
         "image": "https://fastly.picsum.photos/id/965/400/300.jpg?hmac=DShMIYxC4lJjNNDmiRdRiON-2dcwcFXigRKNrgo6Dy8"},
        {"name": "Standing Desk Mat", "price": 39.99,
         "description": "Anti-fatigue ergonomic mat, 20x34 inches.",
         "image": "https://fastly.picsum.photos/id/120/400/300.jpg?hmac=oYnt2GLhEMWVz-1Ncwy6bGqiNcAJ07X-otSM76xOIgo"},
        {"name": "Monitor Light Bar", "price": 54.95,
         "description": "Asymmetric LED light bar, adjustable color temperature.",
         "image": "https://fastly.picsum.photos/id/84/400/300.jpg?hmac=5SPN4ZbRXMopndUrHWflh5wuU7XxpSz3mGnqwqFDSJc"},
        {"name": "Portable SSD 1TB", "price": 89.99,
         "description": "NVMe external drive, 1050 MB/s read, USB-C, pocket-sized.",
         "image": "https://fastly.picsum.photos/id/201/400/300.jpg?hmac=cBf-BtCukiBuTIz6OWxcSunJOO3lhjXWxydX6aeygjY"},
        {"name": "Webcam 4K", "price": 119.00,
         "description": "4K30 sensor, auto-focus, built-in privacy shutter.",
         "image": "https://fastly.picsum.photos/id/250/400/300.jpg?hmac=6xhdR2eoEN02XR95DMWvxRozD2worJM_BFDArufVnWQ"},
        {"name": "Bluetooth Mouse", "price": 34.99,
         "description": "Ergonomic vertical mouse, quiet clicks, 6 buttons.",
         "image": "https://fastly.picsum.photos/id/60/400/300.jpg?hmac=T3FQynHXWQLsYKA34ScITly8QswvTv_PIB1XPOmGOHQ"},
        # Home
        {"name": "Smart LED Bulbs (4-pack)", "price": 42.00,
         "description": "WiFi RGBW bulbs, 800 lumens each, voice assistant compatible.",
         "image": "https://fastly.picsum.photos/id/163/400/300.jpg?hmac=W6Z0_dT0sh9HpOu1YIsX5U2LrWUxqSFyAh9nQobt3IQ"},
        {"name": "Pour-Over Coffee Set", "price": 28.50,
         "description": "Ceramic dripper, glass carafe, 40 paper filters included.",
         "image": "https://fastly.picsum.photos/id/225/400/300.jpg?hmac=fYa1ri3NHEOL73-zDqUF3Llvas5wIQolSeRZ0VUGd6o"},
        {"name": "Cast Iron Skillet 12\"", "price": 35.00,
         "description": "Pre-seasoned, oven-safe to 500 F, lifetime warranty.",
         "image": "https://fastly.picsum.photos/id/312/400/300.jpg?hmac=rheDmE3u5ebZsvOy_qXh_WcTr7FNRXcUOLtMnVlG7s0"},
        {"name": "Bamboo Desk Organizer", "price": 24.99,
         "description": "5-slot organizer for pens, phone, cards. Natural bamboo finish.",
         "image": "https://fastly.picsum.photos/id/180/400/300.jpg?hmac=M9jTg4LauWtLpFDOoZYf1Z0MHwdBU7FvJ2ht9Vp3mHI"},
        # Outdoor
        {"name": "Hiking Daypack 25L", "price": 64.99,
         "description": "Ripstop nylon, hydration-compatible, rain cover included.",
         "image": "https://fastly.picsum.photos/id/385/400/300.jpg?hmac=hAUyY7rrTn3vsOedJTgZX0P0qnkLhbDUe3MnonrCrws"},
        {"name": "Titanium Water Bottle", "price": 48.00,
         "description": "750 ml, double-wall insulated, keeps cold 24h / hot 12h.",
         "image": "https://fastly.picsum.photos/id/425/400/300.jpg?hmac=SmsIoIL6PQxRzYalJp3nr0hAFxTdAgtulaVTK-7uoRo"},
        {"name": "Compact Binoculars", "price": 72.50,
         "description": "10x42 roof prism, multi-coated optics, waterproof.",
         "image": "https://fastly.picsum.photos/id/54/400/300.jpg?hmac=pv-6BOZ71KMjJ9G2CoaaVe3e4dMA8rD3YXEG7lXElxo"},
        {"name": "Camping Hammock", "price": 32.00,
         "description": "Parachute nylon, supports 400 lbs, tree straps included.",
         "image": "https://fastly.picsum.photos/id/325/400/300.jpg?hmac=ROKERxSnhf_DL4WK31a8p8TP9MALMb6-b-EuZVDGTt8"},
        # Creative / Misc
        {"name": "Sketchbook A4 (200 pages)", "price": 15.99,
         "description": "Acid-free 120gsm paper, hardcover, lay-flat binding.",
         "image": "https://fastly.picsum.photos/id/169/400/300.jpg?hmac=d5P5pcEINrk8GyeDiQ45n_vP38w7bO19-kNC_C-SUio"},
        {"name": "Wireless Charging Pad", "price": 22.00,
         "description": "15W Qi fast charge, LED indicator, slim profile.",
         "image": "https://fastly.picsum.photos/id/367/400/300.jpg?hmac=W6Wq17nT-hIk8M_wugWVBBdhgkXc3isk10YhX6Ij_8Q"},
        {"name": "Noise Machine", "price": 29.95,
         "description": "30 sound profiles, auto-off timer, USB or battery powered.",
         "image": "https://fastly.picsum.photos/id/453/400/300.jpg?hmac=19cErdap35ZD3TFJZzBb6kEwO8dGJC90VTCHvuabLf0"},
        {"name": "Desk Cable Clips (10-pack)", "price": 8.99,
         "description": "Adhesive-backed silicone clips, fits cables up to 7mm.",
         "image": "https://fastly.picsum.photos/id/572/400/300.jpg?hmac=op_WouuC6MkJS-Px0ftuSEqPpyg9LkwA3E9qkjxnLZM"},
    ]

    created_products = []
    for p in products:
        product = Product(**p)
        created = Product.create(product)
        created_products.append(created)
        logger.info("  + Product: %s ($%s)", created.name, created.price)

    # ── Comments on products (65 top-level) ──
    # product_idx: index into created_products, user_idx: index into created_users
    comments = [
        # Product 0: Wireless Headphones
        {"product_idx": 0, "user_idx": 1, "name": "Great sound",           "description": "Best headphones I've owned. ANC is incredible."},
        {"product_idx": 0, "user_idx": 2, "name": "Comfortable",           "description": "Wore them for 8 hours straight, no issues."},
        {"product_idx": 0, "user_idx": 3, "name": "Battery is amazing",    "description": "I charge once a week with daily 4-hour use."},
        {"product_idx": 0, "user_idx": 5, "name": "Worth the upgrade",     "description": "Upgraded from budget earbuds. Night and day difference."},
        # Product 1: Mechanical Keyboard
        {"product_idx": 1, "user_idx": 0, "name": "Perfect for coding",    "description": "The tactile feedback is just right. Love the layout."},
        {"product_idx": 1, "user_idx": 2, "name": "A bit loud",            "description": "Switches are louder than expected in a quiet office."},
        {"product_idx": 1, "user_idx": 4, "name": "RGB is tasteful",       "description": "Not over the top — subtle and customizable."},
        {"product_idx": 1, "user_idx": 5, "name": "Build quality",         "description": "Aluminum frame feels premium. No flex at all."},
        # Product 2: USB-C Hub
        {"product_idx": 2, "user_idx": 0, "name": "Works perfectly",       "description": "All ports recognized immediately on macOS and Linux."},
        {"product_idx": 2, "user_idx": 3, "name": "Compact design",        "description": "Fits in my laptop sleeve without any issues."},
        {"product_idx": 2, "user_idx": 4, "name": "PD charging works",     "description": "Pass-through charging at 60W, exactly as advertised."},
        # Product 3: Standing Desk Mat
        {"product_idx": 3, "user_idx": 1, "name": "Feet love it",          "description": "Standing all day is much easier with this mat."},
        {"product_idx": 3, "user_idx": 2, "name": "Good thickness",        "description": "Not too soft, not too firm. Perfect balance."},
        {"product_idx": 3, "user_idx": 5, "name": "Easy to clean",         "description": "Spilled coffee on it, wiped right off."},
        # Product 4: Monitor Light Bar
        {"product_idx": 4, "user_idx": 0, "name": "No more eye strain",    "description": "Huge difference for late-night work sessions."},
        {"product_idx": 4, "user_idx": 1, "name": "Easy to install",       "description": "Clips right onto the monitor, no tools needed."},
        {"product_idx": 4, "user_idx": 4, "name": "Color temp control",    "description": "Warm light at night, cool during the day. Love it."},
        # Product 5: Portable SSD
        {"product_idx": 5, "user_idx": 0, "name": "Blazing fast",          "description": "Transferred 50GB in under a minute. Incredible."},
        {"product_idx": 5, "user_idx": 1, "name": "Tiny form factor",      "description": "Smaller than a credit card. Fits in any pocket."},
        {"product_idx": 5, "user_idx": 3, "name": "Reliable backup",       "description": "Using it for Time Machine backups. No issues in 6 months."},
        # Product 6: Webcam 4K
        {"product_idx": 6, "user_idx": 2, "name": "Sharp video",           "description": "Way better than my laptop cam. Coworkers noticed immediately."},
        {"product_idx": 6, "user_idx": 4, "name": "Privacy shutter",       "description": "Love the physical shutter. Peace of mind."},
        {"product_idx": 6, "user_idx": 5, "name": "Auto-focus is smooth",  "description": "No hunting or jitter even when I move around."},
        # Product 7: Bluetooth Mouse
        {"product_idx": 7, "user_idx": 0, "name": "Wrist saver",           "description": "Vertical design fixed my wrist pain within a week."},
        {"product_idx": 7, "user_idx": 3, "name": "Silent clicks",         "description": "Can use it in meetings without annoying anyone."},
        {"product_idx": 7, "user_idx": 5, "name": "Multi-device",          "description": "Switches between laptop and tablet seamlessly."},
        # Product 8: Smart LED Bulbs
        {"product_idx": 8, "user_idx": 1, "name": "Easy setup",            "description": "Connected all 4 bulbs in under 10 minutes."},
        {"product_idx": 8, "user_idx": 2, "name": "Great for ambiance",    "description": "Movie night with dim red lighting is perfect."},
        {"product_idx": 8, "user_idx": 4, "name": "Alexa compatible",      "description": "Voice control works flawlessly. No lag."},
        # Product 9: Pour-Over Coffee Set
        {"product_idx": 9, "user_idx": 0, "name": "Morning ritual",        "description": "Slowed down my mornings in the best way possible."},
        {"product_idx": 9, "user_idx": 3, "name": "Clean taste",           "description": "Paper filter gives a much cleaner cup than French press."},
        {"product_idx": 9, "user_idx": 5, "name": "Beautiful carafe",      "description": "Looks great on the counter. Gets compliments."},
        # Product 10: Cast Iron Skillet
        {"product_idx": 10, "user_idx": 1, "name": "Perfect sear",         "description": "Best steak I've ever made at home. Even heat."},
        {"product_idx": 10, "user_idx": 2, "name": "Heavy but worth it",   "description": "It's hefty. But the cooking performance is unmatched."},
        {"product_idx": 10, "user_idx": 4, "name": "Seasoning holds",      "description": "Pre-seasoning is legit. Gets better with each use."},
        # Product 11: Bamboo Desk Organizer
        {"product_idx": 11, "user_idx": 0, "name": "Decluttered my desk",  "description": "Everything has a place now. Looks clean and minimal."},
        {"product_idx": 11, "user_idx": 3, "name": "Solid construction",   "description": "Bamboo is thick, no wobble. Feels premium."},
        {"product_idx": 11, "user_idx": 5, "name": "Phone slot is handy",  "description": "Perfect angle for seeing notifications while working."},
        # Product 12: Hiking Daypack
        {"product_idx": 12, "user_idx": 1, "name": "Comfortable carry",    "description": "Hiked 12 miles, barely felt it on my back."},
        {"product_idx": 12, "user_idx": 2, "name": "Rain cover saved me",  "description": "Got caught in a downpour. Everything stayed dry."},
        {"product_idx": 12, "user_idx": 4, "name": "Lots of pockets",      "description": "Hip belt pockets for snacks are a game changer."},
        # Product 13: Titanium Water Bottle
        {"product_idx": 13, "user_idx": 0, "name": "Stays cold forever",   "description": "Ice still in there after 20 hours. Impressive."},
        {"product_idx": 13, "user_idx": 3, "name": "No metallic taste",    "description": "Titanium is worth it over stainless. Zero taste."},
        {"product_idx": 13, "user_idx": 5, "name": "Dent-proof",           "description": "Dropped it on rocks twice. Not a scratch."},
        # Product 14: Compact Binoculars
        {"product_idx": 14, "user_idx": 1, "name": "Great for birding",    "description": "Spotted a hawk at 200 yards. Crystal clear."},
        {"product_idx": 14, "user_idx": 4, "name": "Lightweight",          "description": "Barely notice them around my neck on long hikes."},
        {"product_idx": 14, "user_idx": 5, "name": "Waterproof tested",    "description": "Used in pouring rain on a boat. No fogging."},
        # Product 15: Camping Hammock
        {"product_idx": 15, "user_idx": 0, "name": "Best nap ever",        "description": "Set it up between two oaks. Slept like a baby."},
        {"product_idx": 15, "user_idx": 2, "name": "Easy setup",           "description": "Tree straps make it a 2-minute job. No knots needed."},
        {"product_idx": 15, "user_idx": 3, "name": "Holds my weight",      "description": "I'm 220 lbs, feels totally secure."},
        # Product 16: Sketchbook
        {"product_idx": 16, "user_idx": 1, "name": "Paper quality",        "description": "No bleed-through with markers. Smooth for pencil."},
        {"product_idx": 16, "user_idx": 4, "name": "Lay-flat binding",     "description": "Actually stays flat. Most sketchbooks don't."},
        {"product_idx": 16, "user_idx": 5, "name": "Great for travel",     "description": "Hardcover protects pages in my bag perfectly."},
        # Product 17: Wireless Charging Pad
        {"product_idx": 17, "user_idx": 0, "name": "No more cables",       "description": "Just drop the phone and walk away. So convenient."},
        {"product_idx": 17, "user_idx": 2, "name": "Fast charge works",    "description": "Charges my Pixel noticeably faster than old pad."},
        {"product_idx": 17, "user_idx": 3, "name": "Slim and quiet",       "description": "No fan noise, barely visible on the nightstand."},
        # Product 18: Noise Machine
        {"product_idx": 18, "user_idx": 1, "name": "Sleep game changer",   "description": "Brown noise setting knocked me out in minutes."},
        {"product_idx": 18, "user_idx": 4, "name": "Office white noise",   "description": "Masks chatter in open office perfectly."},
        {"product_idx": 18, "user_idx": 5, "name": "Timer is useful",      "description": "Auto-off after 1 hour so it doesn't run all night."},
        # Product 19: Cable Clips
        {"product_idx": 19, "user_idx": 0, "name": "Neat desk finally",    "description": "No more cables falling behind the desk."},
        {"product_idx": 19, "user_idx": 2, "name": "Strong adhesive",      "description": "Stuck them 3 months ago, not one has fallen off."},
        {"product_idx": 19, "user_idx": 3, "name": "Simple but effective",  "description": "Best $9 I've spent on desk accessories."},
        {"product_idx": 19, "user_idx": 5, "name": "Fit USB-C cables",     "description": "7mm max fits all my cables including braided ones."},
        # Extra comments to round out count
        {"product_idx": 13, "user_idx": 2, "name": "Travel friendly",       "description": "Fits in the side pocket of my daypack. Light enough to forget."},
        {"product_idx": 16, "user_idx": 0, "name": "200 pages is plenty",   "description": "Lasted me three months of daily sketching."},
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

    # ── Nested replies using parent_id (15 replies → 80 total comments) ──
    replies = [
        # Replies on Product 0 (Headphones)
        {"parent_idx": 0,  "product_idx": 0,  "user_idx": 0, "name": "Agreed!",             "description": "The ANC on these is next level."},
        {"parent_idx": 0,  "product_idx": 0,  "user_idx": 2, "name": "Which model?",         "description": "Are you talking about the v2 or v3?"},
        {"parent_idx": 1,  "product_idx": 0,  "user_idx": 4, "name": "Same experience",      "description": "The ear cushions are memory foam, right? Super comfy."},
        # Replies on Product 1 (Keyboard)
        {"parent_idx": 4,  "product_idx": 1,  "user_idx": 1, "name": "Same here",            "description": "Cherry Browns are the sweet spot for me too."},
        {"parent_idx": 5,  "product_idx": 1,  "user_idx": 0, "name": "Try O-rings",          "description": "Dampener rings cut the noise by half. Highly recommend."},
        # Replies on Product 5 (Portable SSD)
        {"parent_idx": 17, "product_idx": 5,  "user_idx": 2, "name": "What interface?",       "description": "Is that USB 3.2 Gen 2 or Thunderbolt?"},
        {"parent_idx": 17, "product_idx": 5,  "user_idx": 4, "name": "Can confirm",           "description": "I benchmarked 980 MB/s sustained writes. Legit."},
        # Replies on Product 9 (Coffee Set)
        {"parent_idx": 29, "product_idx": 9,  "user_idx": 1, "name": "What beans?",           "description": "Any recommendations for medium roast?"},
        {"parent_idx": 29, "product_idx": 9,  "user_idx": 2, "name": "Same ritual",           "description": "Pour-over + a good podcast = perfect morning."},
        # Replies on Product 12 (Daypack)
        {"parent_idx": 38, "product_idx": 12, "user_idx": 0, "name": "Which trail?",          "description": "12 miles sounds great! Where did you hike?"},
        {"parent_idx": 39, "product_idx": 12, "user_idx": 3, "name": "Good to know",          "description": "Rain cover is a must-have. Glad they included it."},
        # Replies on Product 15 (Hammock)
        {"parent_idx": 47, "product_idx": 15, "user_idx": 1, "name": "How's the sag?",        "description": "Does it keep a flat-ish profile or deep banana curve?"},
        # Replies on Product 18 (Noise Machine)
        {"parent_idx": 56, "product_idx": 18, "user_idx": 0, "name": "Brown noise fan",       "description": "Brown noise is scientifically the best for sleep."},
        {"parent_idx": 57, "product_idx": 18, "user_idx": 2, "name": "Volume control?",       "description": "Can you set specific volume levels or just presets?"},
        # Replies on Product 19 (Cable Clips)
        {"parent_idx": 59, "product_idx": 19, "user_idx": 1, "name": "Totally agree",         "description": "Cheap fix for a problem I ignored for years."},
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

    # ── Likes on comments (50) ──
    # comment_idx: index into created_comments (top-level only, 0-64)
    like_data = [
        # Headphones comments
        {"comment_idx": 0,  "user_idx": 0},
        {"comment_idx": 0,  "user_idx": 3},
        {"comment_idx": 0,  "user_idx": 4},
        {"comment_idx": 1,  "user_idx": 0},
        {"comment_idx": 1,  "user_idx": 5},
        {"comment_idx": 2,  "user_idx": 1},
        {"comment_idx": 3,  "user_idx": 2},
        # Keyboard comments
        {"comment_idx": 4,  "user_idx": 1},
        {"comment_idx": 4,  "user_idx": 3},
        {"comment_idx": 5,  "user_idx": 0},
        {"comment_idx": 6,  "user_idx": 2},
        {"comment_idx": 7,  "user_idx": 0},
        # USB-C Hub comments
        {"comment_idx": 8,  "user_idx": 1},
        {"comment_idx": 8,  "user_idx": 5},
        {"comment_idx": 9,  "user_idx": 0},
        {"comment_idx": 10, "user_idx": 2},
        # Standing Desk Mat comments
        {"comment_idx": 11, "user_idx": 0},
        {"comment_idx": 11, "user_idx": 3},
        {"comment_idx": 12, "user_idx": 4},
        # Monitor Light Bar comments
        {"comment_idx": 14, "user_idx": 2},
        {"comment_idx": 14, "user_idx": 5},
        {"comment_idx": 15, "user_idx": 3},
        # Portable SSD comments
        {"comment_idx": 17, "user_idx": 2},
        {"comment_idx": 17, "user_idx": 4},
        {"comment_idx": 18, "user_idx": 0},
        # Webcam comments
        {"comment_idx": 20, "user_idx": 0},
        {"comment_idx": 21, "user_idx": 1},
        # Bluetooth Mouse comments
        {"comment_idx": 23, "user_idx": 1},
        {"comment_idx": 23, "user_idx": 4},
        # Smart LED Bulbs comments
        {"comment_idx": 26, "user_idx": 0},
        {"comment_idx": 27, "user_idx": 3},
        # Coffee Set comments
        {"comment_idx": 29, "user_idx": 1},
        {"comment_idx": 29, "user_idx": 4},
        # Cast Iron comments
        {"comment_idx": 32, "user_idx": 0},
        {"comment_idx": 33, "user_idx": 3},
        # Daypack comments
        {"comment_idx": 38, "user_idx": 0},
        {"comment_idx": 38, "user_idx": 5},
        {"comment_idx": 39, "user_idx": 1},
        # Water Bottle comments
        {"comment_idx": 41, "user_idx": 2},
        {"comment_idx": 42, "user_idx": 4},
        # Binoculars comments
        {"comment_idx": 44, "user_idx": 0},
        {"comment_idx": 45, "user_idx": 3},
        # Hammock comments
        {"comment_idx": 47, "user_idx": 1},
        {"comment_idx": 48, "user_idx": 4},
        # Sketchbook comments
        {"comment_idx": 50, "user_idx": 0},
        {"comment_idx": 51, "user_idx": 2},
        # Noise Machine comments
        {"comment_idx": 56, "user_idx": 0},
        {"comment_idx": 56, "user_idx": 3},
        # Cable Clips comments
        {"comment_idx": 59, "user_idx": 1},
        {"comment_idx": 60, "user_idx": 4},
    ]

    for ld in like_data:
        comment = created_comments[ld["comment_idx"]]
        user = created_users[ld["user_idx"]]
        like = Like(user=user.id, created_at=datetime.now().isoformat())
        like.__owner__ = comment
        like.save()
        logger.info("  + Like on '%s' by %s", comment.name, user.name)

    # ── Favorites on products (45) ──
    fav_data = [
        # Product 0: Headphones — 4 favs
        {"product_idx": 0,  "user_idx": 0},
        {"product_idx": 0,  "user_idx": 1},
        {"product_idx": 0,  "user_idx": 3},
        {"product_idx": 0,  "user_idx": 5},
        # Product 1: Keyboard — 3 favs
        {"product_idx": 1,  "user_idx": 0},
        {"product_idx": 1,  "user_idx": 2},
        {"product_idx": 1,  "user_idx": 4},
        # Product 2: USB-C Hub — 3 favs
        {"product_idx": 2,  "user_idx": 2},
        {"product_idx": 2,  "user_idx": 3},
        {"product_idx": 2,  "user_idx": 5},
        # Product 3: Desk Mat — 2 favs
        {"product_idx": 3,  "user_idx": 1},
        {"product_idx": 3,  "user_idx": 4},
        # Product 4: Light Bar — 3 favs
        {"product_idx": 4,  "user_idx": 0},
        {"product_idx": 4,  "user_idx": 1},
        {"product_idx": 4,  "user_idx": 4},
        # Product 5: SSD — 3 favs
        {"product_idx": 5,  "user_idx": 0},
        {"product_idx": 5,  "user_idx": 2},
        {"product_idx": 5,  "user_idx": 3},
        # Product 6: Webcam — 2 favs
        {"product_idx": 6,  "user_idx": 4},
        {"product_idx": 6,  "user_idx": 5},
        # Product 7: Mouse — 2 favs
        {"product_idx": 7,  "user_idx": 0},
        {"product_idx": 7,  "user_idx": 3},
        # Product 8: LED Bulbs — 2 favs
        {"product_idx": 8,  "user_idx": 1},
        {"product_idx": 8,  "user_idx": 4},
        # Product 9: Coffee — 3 favs
        {"product_idx": 9,  "user_idx": 0},
        {"product_idx": 9,  "user_idx": 3},
        {"product_idx": 9,  "user_idx": 5},
        # Product 10: Skillet — 2 favs
        {"product_idx": 10, "user_idx": 1},
        {"product_idx": 10, "user_idx": 2},
        # Product 11: Organizer — 2 favs
        {"product_idx": 11, "user_idx": 0},
        {"product_idx": 11, "user_idx": 5},
        # Product 12: Daypack — 2 favs
        {"product_idx": 12, "user_idx": 1},
        {"product_idx": 12, "user_idx": 4},
        # Product 13: Water Bottle — 2 favs
        {"product_idx": 13, "user_idx": 0},
        {"product_idx": 13, "user_idx": 5},
        # Product 14: Binoculars — 1 fav
        {"product_idx": 14, "user_idx": 1},
        # Product 15: Hammock — 2 favs
        {"product_idx": 15, "user_idx": 0},
        {"product_idx": 15, "user_idx": 2},
        # Product 16: Sketchbook — 1 fav
        {"product_idx": 16, "user_idx": 4},
        # Product 17: Charging Pad — 2 favs
        {"product_idx": 17, "user_idx": 0},
        {"product_idx": 17, "user_idx": 2},
        # Product 18: Noise Machine — 2 favs
        {"product_idx": 18, "user_idx": 1},
        {"product_idx": 18, "user_idx": 5},
        # Product 19: Cable Clips — 2 favs
        {"product_idx": 19, "user_idx": 3},
        {"product_idx": 19, "user_idx": 5},
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
