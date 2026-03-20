---
wave: 1
depends_on: []
files_modified:
  - apps/veille/config.py
  - apps/veille/main.py
  - apps/veille/seed.py
  - apps/veille/models/__init__.py
  - apps/veille/models/user.py
  - apps/veille/models/organization.py
  - apps/veille/models/source.py
  - apps/veille/models/grant.py
autonomous: true

must_haves:
  truths:
    - "Server starts on port 5000 with `python main.py` and responds to HTTP requests"
    - "GET /Source returns JSON Schema for the Source model"
    - "GET /Organization returns JSON Schema for the Organization model"
    - "GET /Grant returns JSON Schema for the Grant model"
    - "After running seed.py, admin user can log in and CRUD endpoints return data"
  artifacts:
    - path: "apps/veille/config.py"
      provides: "Local deployment config"
    - path: "apps/veille/main.py"
      provides: "App bootstrap with Level 3 actor routing"
    - path: "apps/veille/models/__init__.py"
      provides: "Model re-exports"
    - path: "apps/veille/models/user.py"
      provides: "User model with auth"
    - path: "apps/veille/models/organization.py"
      provides: "Organization singleton model"
    - path: "apps/veille/models/source.py"
      provides: "Source CRUD model"
    - path: "apps/veille/models/grant.py"
      provides: "Grant stub model"
    - path: "apps/veille/seed.py"
      provides: "Database seeding script"
---

# Plan 01: App Skeleton + All Models

## Objective

Deliver a working N3TX Level 3 application with four models (User, Organization, Source, Grant), a config file, and a seed script. After this plan, the server starts, schema endpoints return valid JSON Schema, and seeded data is queryable via the API.

Purpose: This is the backend foundation. Every subsequent plan depends on the server running and models being registered.

Output: 8 files comprising the complete backend. The server is startable and the API is functional.

## Context

**Framework:** N3TX Level 3 with actor routing. Follow `/workspace/examples/actors/` pattern exactly.

**CRITICAL import ordering:** In `main.py`, `import n3tx_agents` MUST appear BEFORE any model imports. This registers the AgentMixin in `proto_model._mixin_registry`. Without this, `__agent__ = True` on future models silently does nothing. Even though Phase 1 models do not use `__agent__`, the import ordering must be correct from the start.

**CRITICAL ClassVar annotations:** All dunder class attributes (`__tablename__`, `__storable__`, `__access__`, `__ui__`) MUST use `ClassVar` type hints. Without `ClassVar`, Pydantic treats them as instance fields, causing validation errors or polluted schema output.

**Widget field types available** (from `n3tx_core.widgets`): `TextareaField` (str, renders as textarea), `MarkdownField` (str, renders as markdown), `UrlField` (AnyHttpUrl, renders as link), `CurrencyField` (float, renders as currency), `DateField` (date), `DateTimeField` (datetime), `EmailField` (EmailStr).

**BaseUser provides these fields and methods** (do NOT redeclare): `name`, `email`, `role`, `password_hash`, `login()`, `register_user()`. It sets `__storable__ = True`, `__abstract__ = True`, `__hidden_fields__ = {'password_hash'}`, `__owner_field__ = 'id'`.

**Working directory:** All file paths are relative to `/workspace/apps/veille/`.

## Tasks

<task id="1" title="Create config.py and models">

Create the following 6 files. All paths relative to `/workspace/apps/veille/`.

### File 1: `config.py`

```python
"""Local deployment config for Veille."""
import os
from n3tx_core import config as _fw

HOST = os.environ.get("N3TX_HOST", "0.0.0.0")
PORT = int(os.environ.get("N3TX_PORT", "5000"))
API_URL = os.environ.get("N3TX_API_URL", f"http://localhost:{PORT}")
SQLITE_DB_FILE = os.environ.get("N3TX_SQLITE_DB", "veille.db")
JWT_SECRET = os.environ.get("N3TX_JWT_SECRET", "veille-dev-secret-change-in-production")
JWT_EXPIRY_HOURS = int(os.environ.get("N3TX_JWT_EXPIRY_HOURS", "24"))
DEBUG = os.environ.get("N3TX_DEBUG", "true").lower() == "true"
SSR = os.environ.get("N3TX_SSR", "full")

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://172.20.0.1:11434")
DEFAULT_LLM = os.environ.get("N3TX_CHAT_LLM", "ollama:qwen3.5:9b")

if not os.environ.get("N3TX_AGENT_DEFAULTS"):
    os.environ["N3TX_AGENT_DEFAULTS"] = '{"llm": "ollama:qwen3.5:9b"}'

_fw.configure(host=HOST, port=PORT, api_url=API_URL,
              sqlite_db_file=SQLITE_DB_FILE, jwt_secret=JWT_SECRET,
              jwt_expiry_hours=JWT_EXPIRY_HOURS, debug=DEBUG, ssr=SSR,
              ollama_base_url=OLLAMA_BASE_URL)
```

### File 2: `models/__init__.py`

```python
from .user import User
from .organization import Organization
from .source import Source
from .grant import Grant

__all__ = ['User', 'Organization', 'Source', 'Grant']
```

### File 3: `models/user.py`

```python
from __future__ import annotations
from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.models.base_user import BaseUser
from typing import ClassVar
from pydantic import Field


class User(BaseUser, ActorModel):
    __tablename__: ClassVar[str] = 'users'
    __abstract__: ClassVar[bool] = False

    __ui__: ClassVar[dict] = {
        'renderer': {
            'item': 'ntx-item',
        },
    }

    image: str = Field(
        default='https://ui-avatars.com/api/?name=User&background=94a3b8&color=fff&size=128&rounded=true'
    )
```

Note: Using `'item': 'ntx-item'` (not `'ntx-user'`) because we do not have a custom user component. The actors example uses `ntx-user` which is a custom component in that example. We use the standard `ntx-item`.

### File 4: `models/organization.py`

```python
from __future__ import annotations
from typing import ClassVar, Optional
from pydantic import Field
from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.authorize import AUTHENTICATED, ROLE
from n3tx_core.widgets import TextareaField


class Organization(ActorModel):
    __tablename__: ClassVar[str] = 'organizations'
    __storable__: ClassVar[bool] = True
    __access__: ClassVar[dict] = {
        'read': AUTHENTICATED,
        'create': ROLE('admin'),
        'update': AUTHENTICATED,
        'delete': ROLE('admin'),
    }
    __ui__: ClassVar[dict] = {
        'field_order': [
            'name', 'mission', 'activities', 'legal_status',
            'province', 'charitable_status',
            'employee_count', 'annual_budget',
            'focus_areas', 'custom_criteria', 'documents',
        ],
        'groups': {
            'Identity': ['name', 'mission', 'activities'],
            'Legal': ['legal_status', 'province', 'charitable_status'],
            'Size': ['employee_count', 'annual_budget'],
            'Eligibility': ['focus_areas', 'custom_criteria'],
            'Documents': ['documents'],
        },
    }

    # Identity
    name: str = Field(min_length=1, max_length=300)
    mission: TextareaField = Field(default='')
    activities: TextareaField = Field(default='')

    # Legal/location
    legal_status: str = Field(default='')
    province: str = Field(default='')
    charitable_status: str = Field(default='')

    # Size
    employee_count: Optional[int] = Field(default=None)
    annual_budget: Optional[float] = Field(default=None)

    # Eligibility context (JSON fields -- auto-serialized by SQLite storage)
    focus_areas: list = Field(default_factory=list)
    custom_criteria: dict = Field(default_factory=dict)

    # Document references (list of filenames stored on disk)
    documents: list = Field(default_factory=list)
```

### File 5: `models/source.py`

```python
from __future__ import annotations
from typing import ClassVar, Optional
from pydantic import Field
from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.authorize import AUTHENTICATED, ROLE
from n3tx_core.widgets import TextareaField


class Source(ActorModel):
    __tablename__: ClassVar[str] = 'sources'
    __storable__: ClassVar[bool] = True
    __access__: ClassVar[dict] = {
        'read': AUTHENTICATED,
        'create': AUTHENTICATED,
        'update': AUTHENTICATED,
        'delete': ROLE('admin'),
    }
    __ui__: ClassVar[dict] = {
        'field_order': [
            'name', 'url', 'description', 'language',
            'scraping_notes', 'agent_discovered', 'active',
        ],
    }

    name: str = Field(min_length=1, max_length=300,
                      json_schema_extra={'ui': {'placeholder': 'Source name...'}})
    url: str = Field(min_length=1,
                     json_schema_extra={'ui': {'placeholder': 'https://...'}})
    description: TextareaField = Field(default='')
    language: str = Field(default='en')
    scraping_notes: TextareaField = Field(default='',
                                          json_schema_extra={'ui': {'placeholder': 'Hints for the scraping agent...'}})
    agent_discovered: bool = Field(default=False)
    active: bool = Field(default=True)
    last_scraped: Optional[str] = Field(default=None)
```

IMPORTANT: Use `str` for the `url` field, NOT `UrlField`. `UrlField` uses Pydantic's `AnyHttpUrl` which is too strict for agent-populated URLs. Plain `str` with `min_length=1` is correct here.

### File 6: `models/grant.py`

```python
from __future__ import annotations
from typing import ClassVar, Optional
from pydantic import Field
from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.authorize import AUTHENTICATED, ROLE
from n3tx_core.widgets import TextareaField, MarkdownField


class Grant(ActorModel):
    __tablename__: ClassVar[str] = 'grants'
    __storable__: ClassVar[bool] = True
    __access__: ClassVar[dict] = {
        'read': AUTHENTICATED,
        'create': AUTHENTICATED,
        'update': AUTHENTICATED,
        'delete': ROLE('admin'),
    }
    __ui__: ClassVar[dict] = {
        'field_order': [
            'title', 'funder', 'status', 'url', 'source_url',
            'amount_min', 'amount_max', 'deadline',
            'description', 'eligibility_criteria',
            'required_documents', 'application_process',
            'admissibility_score', 'admissibility_reasoning',
        ],
        'groups': {
            'Overview': ['title', 'funder', 'status', 'url', 'source_url'],
            'Funding': ['amount_min', 'amount_max', 'deadline'],
            'Details': ['description', 'eligibility_criteria',
                        'required_documents', 'application_process'],
            'Analysis': ['admissibility_score', 'admissibility_reasoning'],
        },
    }

    # Core identification
    title: str = Field(min_length=1, max_length=500)
    funder: str = Field(default='')
    url: str = Field(default='')
    source_url: str = Field(default='')

    # Details
    description: TextareaField = Field(default='')
    amount_min: Optional[float] = Field(default=None)
    amount_max: Optional[float] = Field(default=None)
    deadline: Optional[str] = Field(default=None)
    eligibility_criteria: list = Field(default_factory=list)
    required_documents: list = Field(default_factory=list)
    application_process: TextareaField = Field(default='')

    # Admissibility (set by analysis agent in Phase 3)
    status: str = Field(default='new')
    admissibility_score: Optional[float] = Field(default=None)
    admissibility_reasoning: MarkdownField = Field(default='')

    # Metadata
    language: str = Field(default='en')
    discovered_at: Optional[str] = Field(default=None)
    run_id: Optional[int] = Field(default=None)
    source_id: Optional[int] = Field(default=None)
```

**Verify:** All 6 files exist, Python can import them without error:
```bash
cd /workspace/apps/veille && python -c "from models import User, Organization, Source, Grant; print('All models imported OK')"
```

**Done:** All 6 files created. Models importable. ClassVar annotations present on all dunder attributes.

</task>

<task id="2" title="Create main.py and seed.py">

### File 1: `main.py`

```python
"""Veille -- Grant monitoring application."""
import logging
import os
import sys

# Add current directory to path for local imports
sys.path.insert(0, os.path.dirname(__file__))

import config  # noqa: E402

# CRITICAL: Must import n3tx_agents BEFORE model imports.
# Registers AgentMixin in proto_model._mixin_registry.
# Without this, __agent__ = True on future models silently does nothing.
import n3tx_agents  # noqa: F401, E402

from n3tx_core.app import create_app  # noqa: E402
from n3tx_core.storage.sqlite_storage import SQLiteStorage  # noqa: E402
from models import User, Organization, Source, Grant  # noqa: E402

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')

_HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_HERE, config.SQLITE_DB_FILE)

storage = SQLiteStorage(DB_PATH)
app = create_app(
    models=[User, Organization, Source, Grant],
    storage=storage,
    routing='actor',
    jwt_secret=config.JWT_SECRET,
    static_dir=os.path.join(_HERE, 'static'),
    ssr='full',
    name='Veille',
    version='1.0.0',
    description='Agentic grant monitoring for non-profits',
)

if __name__ == '__main__':
    import uvicorn
    if config.DEBUG:
        uvicorn.run('main:app', host=config.HOST, port=config.PORT, reload=True)
    else:
        uvicorn.run(app, host=config.HOST, port=config.PORT)
```

### File 2: `seed.py`

```python
"""Seed script -- creates admin user, org profile, and initial sources."""
import os
import sys
import logging

sys.path.insert(0, os.path.dirname(__file__))
import config  # noqa: E402

from n3tx_core.storage.sqlite_storage import SQLiteStorage  # noqa: E402
from n3tx_core.utils.registrar import register_model  # noqa: E402
from models import User, Organization, Source, Grant  # noqa: E402

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')
logger = logging.getLogger('veille.seed')

_HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_HERE, config.SQLITE_DB_FILE)


def seed():
    storage = SQLiteStorage(DB_PATH)
    register_model(User, storage=storage)
    register_model(Organization, storage=storage)
    register_model(Source, storage=storage)
    register_model(Grant, storage=storage)

    # Admin user
    admin = User(name='Admin', email='admin@veille.local')
    admin._plain_password = 'admin123'
    admin.role = 'admin'
    User.create(admin)
    logger.info("Created admin user: admin@veille.local / admin123")

    # Organization profile (singleton -- only one record should exist)
    org = Organization(
        name='Federation franco-tenoise',
        mission='Represent, defend, and promote the rights of francophones in the Northwest Territories.',
        activities='Political advocacy, community development, immigration services, EDI initiatives.',
        legal_status='Registered non-profit',
        province='Northwest Territories',
        charitable_status='Not-for-profit corporation',
        employee_count=15,
        annual_budget=500000.0,
        focus_areas=[
            'Francophone minority services',
            'Health services in French',
            'Immigration and integration',
            'Community development',
            'Equity, diversity, inclusion',
        ],
        custom_criteria={
            'geographic_focus': 'Northwest Territories, Canada',
            'language_focus': 'French and bilingual',
            'target_population': 'Francophone minority community',
        },
    )
    Organization.create(org)
    logger.info("Created organization profile: FFT")

    # Initial scraping sources
    sources = [
        {
            'name': 'Friendly Future Foundation',
            'url': 'https://www.friendlyfuture.com/en/foundation/apply-for-funding',
            'description': 'Private foundation funding for community projects.',
            'language': 'en',
        },
        {
            'name': 'CCNDR',
            'url': 'https://ccndr.ca/',
            'description': 'National centre for community development resources.',
            'language': 'fr',
        },
        {
            'name': 'NRC Outreach Initiative',
            'url': 'https://nrc.canada.ca/en/support-technology-innovation/outreach-initiative-grants-contributions-program',
            'description': 'Federal government grants and contributions program.',
            'language': 'en',
        },
        {
            'name': 'OIF Appels a projets',
            'url': 'https://www.francophonie.org/appels-projets-candidatures-initiatives-1111',
            'description': 'International Organization of Francophonie project calls.',
            'language': 'fr',
        },
    ]
    for s in sources:
        Source.create(Source(**s))
        logger.info("Created source: %s", s['name'])


if __name__ == '__main__':
    if '--reset' in sys.argv:
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
            print(f"Deleted {DB_PATH}")

    if User.storage and User.list():
        print("Database already has data. Use --reset to wipe and re-seed.")
        sys.exit(0)

    print("Seeding database...")
    seed()
    print("Done.")
```

### Create `static/` directory

Create the `static/` directory so `main.py` can reference it (even though it will be empty until Plan 02):

```bash
mkdir -p /workspace/apps/veille/static
```

Also create the `uploads/` directory for document storage:

```bash
mkdir -p /workspace/apps/veille/uploads
```

### Verify the full stack

1. **Start the server** (in background, briefly):
```bash
cd /workspace/apps/veille && timeout 10 python main.py &
sleep 3
```

2. **Check schema endpoints** (these are public, no auth needed):
```bash
curl -s http://localhost:5000/Source | python3 -c "import sys,json; d=json.load(sys.stdin); print('Source schema OK:', 'properties' in d)"
curl -s http://localhost:5000/Organization | python3 -c "import sys,json; d=json.load(sys.stdin); print('Org schema OK:', 'properties' in d)"
curl -s http://localhost:5000/Grant | python3 -c "import sys,json; d=json.load(sys.stdin); print('Grant schema OK:', 'properties' in d)"
```

3. **Seed and test CRUD:**
```bash
cd /workspace/apps/veille && python seed.py --reset
```

4. **Login and query:**
```bash
TOKEN=$(curl -s -X POST http://localhost:5000/users/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@veille.local","password":"admin123"}' | python3 -c "import sys,json; d=json.load(sys.stdin); r=d.get('result',d); print(r.get('token','') or r.get('data',{}).get('token',''))")
echo "Token: $TOKEN"
curl -s http://localhost:5000/sources -H "x-access-token: $TOKEN" | python3 -c "import sys,json; d=json.load(sys.stdin); print('Sources count:', len(d.get('data', d) if isinstance(d, dict) else d))"
curl -s http://localhost:5000/organizations -H "x-access-token: $TOKEN" | python3 -c "import sys,json; d=json.load(sys.stdin); print('Orgs:', d)"
```

5. **Kill the server:**
```bash
kill %1 2>/dev/null || true
```

If any verification step fails, debug and fix before moving on. The most common issues are:
- Import errors from wrong module paths
- Missing `ClassVar` annotations causing Pydantic validation errors
- SQLite table creation failures from type mismatches

**Done:** Server starts, schema endpoints return valid JSON Schema with `properties`, seed script populates admin user + 1 organization + 4 sources, login returns JWT token, authenticated CRUD queries return data.

</task>

## Verification

- [ ] `python -c "from models import User, Organization, Source, Grant"` succeeds without errors
- [ ] `python main.py` starts server on port 5000 without errors
- [ ] `GET /Source` returns JSON Schema with `properties.name`, `properties.url`, `properties.agent_discovered`
- [ ] `GET /Organization` returns JSON Schema with `properties.mission`, `properties.focus_areas`, `properties.documents`
- [ ] `GET /Grant` returns JSON Schema with `properties.title`, `properties.admissibility_score`
- [ ] `python seed.py --reset` creates admin user, 1 org, 4 sources without errors
- [ ] `POST /users/login` with admin credentials returns a JWT token
- [ ] `GET /sources` with token returns 4 sources
- [ ] `GET /organizations` with token returns 1 organization

## must_haves

- Server starts with `python main.py` and listens on port 5000
- All four schema endpoints (`/User`, `/Source`, `/Organization`, `/Grant`) return valid JSON Schema
- Seed script creates admin user (admin@veille.local / admin123), one Organization, and four Sources
- Admin can log in and query all CRUD endpoints with JWT authentication
- Organization model has all profile fields: name, mission, activities, legal_status, province, charitable_status, employee_count, annual_budget, focus_areas, custom_criteria, documents
- Source model has agent_discovered boolean flag and scraping_notes textarea
- Grant model has admissibility fields: status, admissibility_score, admissibility_reasoning
