import os

import jwt
import bcrypt
from datetime import datetime, timedelta, timezone

# ── Package-level configuration ──────────────────────────
# Defaults read from env vars. Override via configure().
_jwt_secret: str = os.getenv("JWT_SECRET", "authorize-dev-secret-change-in-production")
_jwt_expiry_hours: int = int(os.getenv("JWT_EXPIRY_HOURS", "24"))


def configure(*, jwt_secret: str = None, jwt_expiry_hours: int = None) -> None:
    """Configure the authorize package. Call once at application startup."""
    global _jwt_secret, _jwt_expiry_hours
    if jwt_secret is not None:
        _jwt_secret = jwt_secret
    if jwt_expiry_hours is not None:
        _jwt_expiry_hours = jwt_expiry_hours


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_token(user_id: int, email: str, role: str = "user") -> str:
    payload = {
        "user_id": user_id,
        "email": email,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=_jwt_expiry_hours),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, _jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict:
    return jwt.decode(token, _jwt_secret, algorithms=["HS256"])
