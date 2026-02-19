import os

#
BACKEND = "fastapi"  # or "flask"
VERSION = "0.5.0"
HOST = "0.0.0.0"
PORT = 5000
API_URL = f"http://localhost:{PORT}"

# Filesystem configuration
SQLITE_DB_FILE = "pybend.db"

# Auth configuration
JWT_SECRET = os.getenv("JWT_SECRET", "pybend-dev-secret-change-in-production")
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))
