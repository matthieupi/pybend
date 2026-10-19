"""Local deployment config for Veille."""
import os
from n3tx_core import config as _fw

HOST = os.environ.get("N3TX_HOST", "0.0.0.0")
PORT = int(os.environ.get("N3TX_PORT", "4000"))
API_URL = os.environ.get("N3TX_API_URL", f"http://localhost:{PORT}")
SQLITE_DB_FILE = os.environ.get("N3TX_SQLITE_DB", "veille.db")
JWT_SECRET = os.environ.get("N3TX_JWT_SECRET", "veille-dev-secret-change-in-production")
JWT_EXPIRY_HOURS = int(os.environ.get("N3TX_JWT_EXPIRY_HOURS", "24"))
DEBUG = os.environ.get("N3TX_DEBUG", "true").lower() == "true"
SSR = os.environ.get("N3TX_SSR", "full")

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://172.20.0.1:11434")
DEFAULT_LLM = os.environ.get("N3TX_CHAT_LLM", "ollama:qwen3.5:9b")

APP_AGENT = {
    "key": "assistant",
    "name": "Assistant",
    "prompt": (
        "You are Veille's assistant. Help operators understand sources, grants, "
        "runs, and organization context. Be concise, practical, and action-oriented."
    ),
    "llm": DEFAULT_LLM,
    "constraints": {"max_iterations": 12},
    "tools": [
        {"target": "grants", "description": "Grant CRUD operations"},
        {"target": "sources", "description": "Source listing and management"},
        {"target": "web_tools", "description": "Web scraping utilities"},
        {"target": "organizations", "description": "Organization profile access"},
    ],
    "featured": True,
}

FEATURED_AGENTS = [
    {"system_key": "assistant"},
    {"name": "Veille Scout"},
]

APP_META = {
    "featured_agents": FEATURED_AGENTS,
}

if not os.environ.get("N3TX_AGENT_DEFAULTS"):
    os.environ["N3TX_AGENT_DEFAULTS"] = '{"llm": "ollama:qwen3.5:9b"}'

_fw.configure(host=HOST, port=PORT, api_url=API_URL,
              sqlite_db_file=SQLITE_DB_FILE, jwt_secret=JWT_SECRET,
              jwt_expiry_hours=JWT_EXPIRY_HOURS, debug=DEBUG, ssr=SSR,
              ollama_base_url=OLLAMA_BASE_URL)
