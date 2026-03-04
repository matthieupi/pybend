"""Local deployment config — edit these values per deployment."""
import os

# Import framework config and override
from pybend.core import config as _fw

# Deployment settings (edit these)
HOST = os.environ.get("PYBEND_HOST", "0.0.0.0")
PORT = int(os.environ.get("PYBEND_PORT", "5000"))
API_URL = os.environ.get("PYBEND_API_URL", f"http://localhost:{PORT}")
SQLITE_DB_FILE = os.environ.get("PYBEND_SQLITE_DB", "grants.db")
JWT_SECRET = os.environ.get("PYBEND_JWT_SECRET", "pybend-dev-secret-change-in-production")
JWT_EXPIRY_HOURS = int(os.environ.get("PYBEND_JWT_EXPIRY_HOURS", "24"))
DEBUG = os.environ.get("PYBEND_DEBUG", "true").lower() == "true"
SSR = os.environ.get("PYBEND_SSR", "full")

# Propagate to framework (required for schema URLs, etc.)
_fw.configure(host=HOST, port=PORT, api_url=API_URL,
              sqlite_db_file=SQLITE_DB_FILE, jwt_secret=JWT_SECRET,
              jwt_expiry_hours=JWT_EXPIRY_HOURS, debug=DEBUG, ssr=SSR)
