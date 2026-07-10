"""
Seed script — populates the grant-watching database with sample data.

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
from n3tx_agents.actor import AgentActor
from n3tx_agents.tool_model import AgentTool
from models import User, Grant, Source, WebTools

logger = logging.getLogger('n3tx.seed')

_HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get('N3TX_SQLITE_DB') or os.path.join(_HERE, 'grants.db')


def seed():
    storage = SQLiteStorage(DB_PATH)

    for model in [User, Grant, Source, WebTools, AgentTool, AgentActor]:
        register_model(model, storage=storage)

    # ── Users ──
    users = [
        {"name": "Alice Martin", "email": "alice@example.com", "password": "alice123",
         "image": "https://api.dicebear.com/9.x/avataaars/svg?seed=Alice"},
        {"name": "Bob Johnson", "email": "bob@example.com", "password": "bob123",
         "image": "https://api.dicebear.com/9.x/avataaars/svg?seed=Bob"},
    ]
    for u in users:
        pw = u.pop("password")
        user = User(**u)
        user._plain_password = pw
        created = User.create(user)
        logger.info("  + User: %s (%s)", created.name, created.email)

    # ── Sources ──
    sources = [
        {"name": "NSF", "url": "https://www.nsf.gov/funding/", "category": "government"},
        {"name": "NIH", "url": "https://grants.nih.gov/funding/searchguide/index.html", "category": "government"},
        {"name": "DOE", "url": "https://www.energy.gov/funding-financing", "category": "government"},
        {"name": "USDA NIFA", "url": "https://www.nifa.usda.gov/grants", "category": "government"},
    ]
    for s in sources:
        created = Source.create(Source(**s))
        logger.info("  + Source: %s (%s)", created.name, created.url)

    # ── Sample grants (pre-discovered) ──
    grants = [
        {
            "title": "Computer and Information Science and Engineering Research",
            "agency": "NSF",
            "deadline": "2026-06-15",
            "amount_min": 100000,
            "amount_max": 500000,
            "url": "https://www.nsf.gov/funding/example-cise",
            "description": "Supports research in all areas of computer science and engineering.",
            "status": "discovered",
            "user_owner": 1,
        },
        {
            "title": "Biomedical Research Support Grant",
            "agency": "NIH",
            "deadline": "2026-09-01",
            "amount_min": 250000,
            "amount_max": 1000000,
            "url": "https://grants.nih.gov/example-biomed",
            "description": "Funds biomedical and behavioral research projects.",
            "status": "discovered",
            "user_owner": 1,
        },
    ]
    for g in grants:
        created = Grant.create(Grant(**g))
        logger.info("  + Grant: %s (%s)", created.title, created.agency)

    # ── Grant Scanner Agent ──
    scanner = AgentActor(
        name="Grant Scanner",
        prompt=(
            "You are a government grant discovery agent.\n"
            "Your job: scan web pages for open grants, extract structured data, "
            "create Grant records.\n"
            "Steps:\n"
            "1. List all sources (sources_list)\n"
            "2. For each source, scrape the URL (web_tools_scrape)\n"
            "3. Extract relevant sections (web_tools_extract)\n"
            "4. For each grant found, check existing grants (grants_list) to avoid duplicates\n"
            "5. Create new Grant records (grants_create) with: title, agency, deadline, "
            "amounts, url, description\n"
            "Be thorough but cost-efficient."
        ),
        llm="anthropic:claude-sonnet-4-5-20250929",
        constraints={"max_iterations": 50},
    )
    created_agent = AgentActor.create(scanner)
    logger.info("  + Agent: %s (id=%s)", created_agent.name, created_agent.id)

    # ── Link tools to agent via list[T] ──
    tool_data = [
        {"target": "grants", "description": "Grant CRUD operations"},
        {"target": "sources", "description": "Source listing and management"},
        {"target": "web_tools", "description": "Web scraping utilities"},
    ]
    tools = []
    for t in tool_data:
        created = AgentTool.create(AgentTool(**t))
        tools.append(created)
        logger.info("  + AgentTool: %s (id=%s)", created.target, created.id)
    AgentActor.update(created_agent.id, {'tools': tools})

    logger.info("Seeding complete.")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')

    if '--reset' in sys.argv:
        if os.path.exists(DB_PATH):
            os.unlink(DB_PATH)
            logger.info("Deleted %s", DB_PATH)

    seed()
