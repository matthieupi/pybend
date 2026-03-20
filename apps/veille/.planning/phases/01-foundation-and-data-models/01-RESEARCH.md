# Phase 1: Foundation and Data Models - Research

**Researched:** 2026-03-20
**Domain:** N3TX Level 3 app bootstrap, models, auth, file upload, schema-driven UI
**Confidence:** HIGH

## Summary

Phase 1 delivers a working N3TX Level 3 application with authentication, organization profile management, source CRUD, a stub Grant model, and document upload capability. The research covers the exact bootstrap pattern (main.py, config.py, models/, static/, seed.py), model definitions verified against working Level 3 examples, the singleton Organization pattern, file upload integration (not natively supported by N3TX -- requires custom FastAPI route), and frontend structure.

The standard approach is straightforward: follow the `examples/actors/` pattern exactly for app skeleton and User model, define Organization/Source/Grant as ActorModel subclasses with appropriate `__access__`, `__ui__`, and field types, add a custom FastAPI route for document upload alongside N3TX's auto-generated routes, and use standard `ntx-list`/`ntx-item` components for the UI with minimal customization.

The most critical implementation detail is import ordering: `import n3tx_agents` MUST appear before any model imports in `main.py`, even though Phase 1 models don't use `__agent__`. This prevents a silent mixin injection failure when agent models are added in later phases.

**Primary recommendation:** Follow the actors example skeleton exactly, define four models (User, Organization, Source, Grant stub), add a custom `/organizations/upload` route for document handling, and ship standard ntx-list/ntx-item UI.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `n3tx-core` | 0.10+ | Models, storage, auth, API, JS runtime | Foundation framework |
| `n3tx-actors` | 0.10+ | Actor messaging, Level 3 routing | Required for Level 3 |
| `n3tx-agents` | 0.10+ | Agent mixin registration | Must import before models for future agent phases |
| `n3tx-ui` | 0.10+ | Web components, widgets, themes | Standard frontend rendering |
| `FastAPI` | (bundled) | ASGI server | Used by N3TX backend |
| `uvicorn` | (bundled) | ASGI server runner | Standard for FastAPI |
| `SQLite` | (stdlib) | Database | N3TX native storage backend |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `python-multipart` | latest | File upload parsing | Required by FastAPI for `UploadFile` |
| `aiofiles` | latest | Async file writes | Saving uploaded documents to disk |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| File on disk | SQLite BLOB | Disk is simpler, files are readable, no size limit in DB |
| Custom upload route | N3TX @expose_route | N3TX routes don't support multipart/form-data natively |
| Custom org editor component | Standard ntx-item | ntx-item handles Organization fine via Formidable forms; custom component deferred |

**Installation:**
```bash
pip install n3tx  # meta-package installs all four
pip install python-multipart aiofiles  # for file upload support
```

## Architecture Patterns

### Recommended Project Structure
```
apps/veille/
  main.py              # App bootstrap (create_app, Level 3)
  config.py            # Local config overrides (PORT, JWT, DB, LLM)
  seed.py              # Seed script (admin user + org profile + initial sources)
  models/
    __init__.py         # Re-exports all models
    user.py             # User(BaseUser, ActorModel)
    organization.py     # Organization(ActorModel) -- singleton profile
    source.py           # Source(ActorModel) -- scraping sources
    grant.py            # Grant(ActorModel) -- stub for Phase 2+
  static/
    index.html          # Main app page (sidebar + router)
    login.html          # Login page (copy from actors example, customize)
    register.html       # Registration page
    components/         # Custom components (future phases)
  docs/                 # Strategic documents (already exists)
    *.pdf               # FFT/RTS strategic plans
    *.txt               # Text versions of strategic plans
    sources_examples.txt # Initial source URLs
  uploads/              # Uploaded documents directory (created at runtime)
```

### Pattern 1: Level 3 App Bootstrap (main.py)
**What:** Standard N3TX Level 3 application entry point.
**When to use:** Always -- this is the only correct bootstrap pattern.
**Example:**
```python
# Source: /workspace/examples/actors/main.py (verified)
"""Veille -- Grant monitoring application."""
import logging
import os
import sys

# Add current directory to path for local imports
sys.path.insert(0, os.path.dirname(__file__))

import config

# CRITICAL: Must import n3tx_agents BEFORE model imports.
# Registers AgentMixin in proto_model._mixin_registry.
# Without this, __agent__ = True on future models silently does nothing.
import n3tx_agents  # noqa: F401

from n3tx_core.app import create_app
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from models import User, Organization, Source, Grant

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

### Pattern 2: User Model (BaseUser + ActorModel)
**What:** Standard user model combining authentication with actor capabilities.
**When to use:** Every N3TX Level 3 app that needs auth.
**Example:**
```python
# Source: /workspace/examples/actors/models/user.py (verified)
from __future__ import annotations
from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.models.base_user import BaseUser
from typing import ClassVar, Optional
from pydantic import Field


class User(BaseUser, ActorModel):
    __tablename__: ClassVar[str] = 'users'
    __abstract__: ClassVar[bool] = False

    __ui__: ClassVar[dict] = {
        'renderer': {
            'item': 'ntx-user',
        },
    }

    # App-specific fields (auth fields inherited from BaseUser)
    image: str = Field(
        default='https://ui-avatars.com/api/?name=Admin&background=94a3b8&color=fff&size=128&rounded=true'
    )
```

**Key points from BaseUser source** (`/workspace/packages/n3tx-core/src/n3tx_core/models/base_user.py`):
- BaseUser provides: `name`, `email`, `role`, `password_hash` fields
- BaseUser provides: `login()` and `register_user()` class methods as `@expose_route`
- `__storable__ = True` is set on BaseUser (no need to redeclare)
- `__abstract__ = True` on BaseUser (MUST set `__abstract__ = False` on concrete subclass)
- `__hidden_fields__ = {'password_hash'}` hides password from schema
- `__owner_field__ = 'id'` means user owns themselves
- In DEBUG mode, `register_user()` auto-sets `role = 'admin'`
- Password hashing happens in `create()` override

### Pattern 3: Singleton Organization Model
**What:** A storable model where only one record should exist.
**When to use:** App-wide configuration that needs CRUD, UI editing, and agent access.
**Example:**
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

**Singleton enforcement strategy:** NOT enforced at the model level. Instead:
- Seed script creates the single org record (id=1)
- Frontend loads Organization list, takes first item
- UI shows an edit form, not a create form
- `create` access limited to `ROLE('admin')` to prevent duplicates
- The org profile page fetches with `GET /organizations?limit=1` and edits with `PUT /organizations/1`

This is the established N3TX pattern. No framework support for true singletons exists, but the combination of seed data + UI behavior + access rules achieves the same effect.

### Pattern 4: Source Model (Standard CRUD)
**What:** Standard storable ActorModel with proper field types and UI configuration.
**Example:**
```python
from __future__ import annotations
from typing import ClassVar, Optional
from pydantic import Field
from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.authorize import AUTHENTICATED, ROLE
from n3tx_core.widgets import TextareaField, UrlField


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

**IMPORTANT -- Use `str` for URL fields, NOT `UrlField`/`AnyHttpUrl`:**
The `UrlField` widget type uses Pydantic's `AnyHttpUrl` as its base type, which adds strict URL validation. While correct for display-only URLs, this causes issues during agent-driven creation where URLs may have edge cases. Use plain `str` with `min_length=1` for URL fields that agents will populate. The `json_schema_extra={'ui': {'widget': 'url'}}` can be added for frontend rendering hint without triggering backend validation.

### Pattern 5: Grant Model (Stub for Future Phases)
**What:** Define the Grant model now with all fields, but no agent logic.
**When to use:** When a model needs to exist for relationship/schema reasons before its primary functionality is built.
**Example:**
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

    # Admissibility (set by analysis agent in Phase 4)
    status: str = Field(default='new')
    admissibility_score: Optional[float] = Field(default=None)
    admissibility_reasoning: MarkdownField = Field(default='')

    # Metadata
    language: str = Field(default='en')
    discovered_at: Optional[str] = Field(default=None)
    run_id: Optional[int] = Field(default=None)
    source_id: Optional[int] = Field(default=None)
```

**Why define Grant now:** The Source model and Grant model have a conceptual relationship (source_id FK). Defining Grant early means:
1. The schema is available for frontend navigation (sidebar shows Grants)
2. Manual grant entry is possible for testing admissibility later
3. No model definition changes needed when agent phases begin

### Pattern 6: Document Upload (Custom Route)
**What:** FastAPI file upload endpoint alongside N3TX auto-generated routes.
**When to use:** N3TX does not natively support multipart/form-data file uploads.
**Example:**
```python
# In main.py, after create_app returns:
from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse, FileResponse
import os

_api_router = APIRouter()
UPLOAD_DIR = os.path.join(_HERE, 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

@_api_router.post("/organizations/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload a strategic document for the organization."""
    # Validate file type
    allowed = {'.pdf', '.txt', '.md', '.doc', '.docx'}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed:
        return JSONResponse(status_code=400, content={"detail": f"File type {ext} not allowed"})

    # Save to disk
    filepath = os.path.join(UPLOAD_DIR, file.filename)
    content = await file.read()
    with open(filepath, 'wb') as f:
        f.write(content)

    # Update organization documents list
    from models import Organization
    orgs = Organization.list()
    if orgs:
        data = orgs if isinstance(orgs, list) else orgs.get('data', [])
        if data:
            org = data[0]
            docs = org.documents or []
            if file.filename not in docs:
                docs.append(file.filename)
                Organization.update(org.id, {'documents': docs})

    return {"filename": file.filename, "size": len(content)}

@_api_router.get("/organizations/documents/{filename}")
async def get_document(filename: str):
    """Download a stored document."""
    filepath = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(filepath):
        return JSONResponse(status_code=404, content={"detail": "File not found"})
    return FileResponse(filepath)

@_api_router.delete("/organizations/documents/{filename}")
async def delete_document(filename: str):
    """Delete a stored document."""
    filepath = os.path.join(UPLOAD_DIR, filename)
    if os.path.exists(filepath):
        os.remove(filepath)

    # Update organization documents list
    from models import Organization
    orgs = Organization.list()
    if orgs:
        data = orgs if isinstance(orgs, list) else orgs.get('data', [])
        if data:
            org = data[0]
            docs = [d for d in (org.documents or []) if d != filename]
            Organization.update(org.id, {'documents': docs})

    return {"deleted": filename}

# Insert routes before the static mount (catch-all at "/")
for route in _api_router.routes:
    app.router.routes.insert(-1, route)
```

**Why a custom route instead of @expose_route:** N3TX's `@expose_route` works with JSON request bodies (application/json). File uploads require `multipart/form-data`, which needs FastAPI's `UploadFile` parameter. The `@expose_route` decorator does not support this content type. The custom route pattern is established in `examples/chat/main.py` (the `llm_status` endpoint).

**Route insertion strategy:** `app.router.routes.insert(-1, route)` inserts before the last route, which is the static file mount (catch-all). Without this, the upload route would be shadowed by the static mount.

### Pattern 7: Config File
**What:** Local deployment configuration matching the actors example pattern.
**Example:**
```python
# Source: /workspace/examples/actors/config.py (verified pattern)
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

### Pattern 8: Seed Script
**What:** Database population script for initial admin user, organization profile, and sources.
**Example:**
```python
# Source: /workspace/examples/actors/seed.py (verified pattern)
"""Seed script -- creates admin user, org profile, and initial sources."""
import os, sys, logging
sys.path.insert(0, os.path.dirname(__file__))
import config

from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_core.utils.registrar import register_model
from n3tx_core.authorize import hash_password
from models import User, Organization, Source, Grant

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
    logger.info("Created admin user: admin@veille.local")

    # Organization profile (singleton)
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

    # Initial sources
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
```

### Anti-Patterns to Avoid
- **Using UrlField for agent-populated URLs:** Pydantic's `AnyHttpUrl` validation is too strict for URLs that agents extract from web pages. Use `str` with min_length.
- **Using Ref/ListRef for Grant->Source FK:** Adds join table overhead for a simple one-directional foreign key. Use `Optional[int]` for `source_id` and `run_id`.
- **Adding `__agent__` to Organization/Source/Grant:** These models are data, not reasoning entities. The Run agent reads them via tools.
- **Creating a custom component for Organization in Phase 1:** Standard `ntx-item` with Formidable form handles all Organization fields including JSON lists/dicts. Custom component deferred to Phase 6.
- **Importing model files before `import n3tx_agents`:** Silent mixin injection failure.
- **Using `ssr='schema'` or `ssr='off'`:** Use `ssr='full'` for best initial load performance and automatic JS bundling.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CRUD API endpoints | Custom FastAPI routes | `ActorModel` + `__storable__` + `create_app(routing='actor')` | Auto-generates REST API, auth, pagination, schema |
| Login/registration | Custom auth endpoints | `BaseUser` with `login()` and `register_user()` | JWT handling, password hashing, token creation built-in |
| Form generation | Custom HTML forms | `Formidable` (auto-reads schema) | Handles field types, widgets, groups, validation |
| List views | Custom table components | `ntx-list` with `model="Source"` | Pagination, CRUD actions, schema-driven |
| Detail/edit views | Custom detail pages | `ntx-item` with field groups | Read/edit toggle, owner-aware, schema-driven |
| Navigation | Custom client-side router | `ntx-sidebar` + `ntx-router` | Auto-generates nav from registered models |
| JSON field serialization | Manual JSON.dumps/loads | `list`/`dict` field types on model | SQLite storage auto-serializes/deserializes |
| Access control | Custom middleware | `__access__` dict on model | ABAC rules evaluate at both Tier 1 (interceptor) and Tier 2 (handler) |
| Schema endpoint | Custom schema route | `GET /ClassName` (auto-generated) | Returns complete JSON Schema with UI hints, methods, access rules |

**Key insight:** In N3TX, the model definition IS the application. Every feature listed above is derived from model class attributes. Writing custom implementations bypasses the schema pipeline and breaks the frontend's ability to auto-render.

## Common Pitfalls

### Pitfall 1: Import Ordering (CRITICAL)
**What goes wrong:** `import n3tx_agents` appears after model imports. AgentMixin is never injected into models with `__agent__`.
**Why it happens:** Natural to import models first. No error raised.
**How to avoid:** First meaningful import in `main.py` is `import n3tx_agents`. Add assertion: `assert 'AgentMixin' in str(Run.__mro__)` (for future phases).
**Warning signs:** `AttributeError: 'Run' object has no attribute 'agentic'` at runtime.

### Pitfall 2: Missing ClassVar Annotations
**What goes wrong:** `__tablename__ = 'sources'` without `ClassVar[str]` type hint causes Pydantic to treat it as an instance field.
**Why it happens:** Easy to forget the `ClassVar` wrapper.
**How to avoid:** Always use `__tablename__: ClassVar[str] = 'sources'` pattern. Copy from working examples.
**Warning signs:** Field appears in JSON schema output, or `ValidationError` on model creation.

### Pitfall 3: Singleton Organization Has Multiple Records
**What goes wrong:** Users create multiple Organization records via the API.
**Why it happens:** Standard CRUD generates a `POST /organizations` endpoint.
**How to avoid:** Set `'create': ROLE('admin')` in `__access__`, seed the single record in `seed.py`, and design the frontend to always load/edit the first record.
**Warning signs:** Multiple orgs in the database, ambiguous which one the agent reads.

### Pitfall 4: SQLite :memory: in Tests
**What goes wrong:** Tests use `SQLiteStorage(':memory:')`. Each connection gets a separate database.
**Why it happens:** Seems like the simple option for test isolation.
**How to avoid:** Always use `tmp_path / 'test.db'` fixture. Never `:memory:`.
**Warning signs:** `sqlite3.OperationalError: no such table` despite `create_table()` succeeding.

### Pitfall 5: Upload Route Shadowed by Static Mount
**What goes wrong:** Custom FastAPI routes for document upload return 404 or serve static files instead.
**Why it happens:** N3TX's static file mount is a catch-all at `"/"`. Routes added after it are unreachable.
**How to avoid:** Insert custom routes before the static mount using `app.router.routes.insert(-1, route)`.
**Warning signs:** Upload endpoint returns HTML instead of JSON, or 404.

### Pitfall 6: Paginated vs Plain List Returns
**What goes wrong:** Code assumes `Model.list()` returns a plain list, but it returns `{data: [...], meta: {...}}` when `limit`/`offset` are provided.
**Why it happens:** N3TX auto-adds pagination when query params are present.
**How to avoid:** Handle both cases: `result if isinstance(result, list) else result.get('data', [])`.
**Warning signs:** `TypeError: 'dict' object is not iterable` when iterating over list results.

### Pitfall 7: BaseUser.register vs Actor.register Name Collision
**What goes wrong:** MRO collision between `BaseUser` and `Actor` if both define `register()`.
**Why it happens:** Both classes in the MRO have methods with the same name.
**How to avoid:** BaseUser uses `register_user()` (renamed specifically to avoid this collision). Already handled in the framework.
**Warning signs:** N/A -- already fixed. Just be aware if extending either class.

### Pitfall 8: Registry Clear on Reload
**What goes wrong:** `uvicorn --reload` clears `registered_models` and `join_models` dictionaries, but models may have stale storage references.
**Why it happens:** `N3TXApp.build()` calls `registered_models.clear()` for clean reload.
**How to avoid:** This is handled by the framework. Just be aware that hot reload re-registers everything.
**Warning signs:** Intermittent 500 errors after code changes during development.

## Code Examples

### Complete models/__init__.py
```python
# Source: /workspace/examples/actors/models/__init__.py (verified pattern)
from .user import User
from .organization import Organization
from .source import Source
from .grant import Grant

__all__ = ['User', 'Organization', 'Source', 'Grant']
```

### Frontend index.html Structure
```html
<!-- Source: /workspace/examples/actors/static/index.html (verified, adapted) -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Veille - Grant Monitoring</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="./dark-theme.css">
    <link rel="stylesheet" href="./light-theme.css">
    <link rel="icon" type="image/svg+xml" href="./favicon.svg">
    <link rel="preload" href="./components/ntx-item.css" as="style">
    <link rel="preload" href="./components/ntx-list.css" as="style">
    <link rel="preload" href="./components/ntx-router.css" as="style">
    <link rel="preload" href="./components/ntx-topbar.css" as="style">
    <link rel="preload" href="./components/ntx-sidebar.css" as="style">
    <link rel="preload" href="./components/ntx-modal.css" as="style">
    <link rel="preload" href="./widgets/widgets.css" as="style">
    <script src="./vendor/marked.min.js"></script>
    <!-- Modulepreload -- eliminates import waterfall -->
    <link rel="modulepreload" href="./config.js">
    <link rel="modulepreload" href="./utils/Assert.js">
    <link rel="modulepreload" href="./utils/Logging.js">
    <link rel="modulepreload" href="./utils/Permissions.js">
    <link rel="modulepreload" href="./core/Utils.js">
    <link rel="modulepreload" href="./core/TX.js">
    <link rel="modulepreload" href="./core/Observable.js">
    <link rel="modulepreload" href="./core/Actor.js">
    <link rel="modulepreload" href="./core/Matrix.js">
    <link rel="modulepreload" href="./core/Component.js">
    <link rel="modulepreload" href="./core/Router.js">
    <link rel="modulepreload" href="./core/NTT.js">
    <link rel="modulepreload" href="./core/transport/HTTP.js">
    <link rel="modulepreload" href="./core/transport/NetworkAdapter.js">
    <link rel="modulepreload" href="./components/NTTElement.js">
    <link rel="modulepreload" href="./components/ListElement.js">
    <link rel="modulepreload" href="./components/ntx-item.js">
    <link rel="modulepreload" href="./components/ntx-list.js">
    <link rel="modulepreload" href="./components/ntx-router.js">
    <link rel="modulepreload" href="./components/ntx-method.js">
    <link rel="modulepreload" href="./components/ntx-modal.js">
    <link rel="modulepreload" href="./components/ntx-sidebar.js">
    <link rel="modulepreload" href="./components/ntx-stream.js">
    <link rel="modulepreload" href="./generators/form.js">
    <link rel="modulepreload" href="./widgets/Widget.js">
    <link rel="modulepreload" href="./widgets/registry.js">
    <link rel="modulepreload" href="./widgets/index.js">
    <script type="module" src="./utils/theme.js"></script>
</head>
<body>
    <ntx-topbar></ntx-topbar>
    <ntx-sidebar router="main">
        <ntx-list model="Source" allow-create></ntx-list>
    </ntx-sidebar>

    <div class="page">
        <ntx-router name="main" hash>
            <ntx-list model="Source" id="source-list" allow-create></ntx-list>
        </ntx-router>
    </div>

    <script type="module">
        import Logging from './utils/Logging.js';
        Logging.init("Loading Veille v1.0...");

        import { Matrix, matrix } from './core/Matrix.js';
        import { NTT } from './core/NTT.js';
        import { config } from './config.js';
        import { permissions } from './utils/Permissions.js';
        import './components/ntx-item.js';
        import './components/ntx-list.js';
        import './components/ntx-router.js';
        import './components/ntx-topbar.js';
        import './components/ntx-sidebar.js';
        import './components/ntx-stream.js';

        // Redirect to login if not authenticated
        permissions.init().then(user => {
            if (!user) {
                window.location.href = '/login.html';
            }
        });
    </script>
</body>
</html>
```

**Auth gate in index.html:** The `permissions.init()` call checks the JWT token. If no valid token exists, it redirects to `/login.html`. This implements the "unauthenticated users see nothing" requirement. The login page is a standalone HTML file (no N3TX components needed).

### Seed Data from docs/sources_examples.txt
```python
# Source URLs from /workspace/apps/veille/docs/sources_examples.txt (verified)
INITIAL_SOURCES = [
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
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `ProtoModel` for Level 1/2 | `ActorModel` for Level 3 | N3TX 0.10 | All models must extend ActorModel for actor routing |
| `register()` on BaseUser | `register_user()` on BaseUser | N3TX 0.10 | Avoids MRO collision with Actor.register() |
| Manual schema pipeline stages | `@schema_extension` decorator | N3TX 0.9 | Extensions auto-register without modifying core pipeline |
| `n3tx.core.*` import paths | `n3tx_core.*` import paths | N3TX 0.10 | Multi-package split, clean import style |
| `ntt-*` HTML tags | `ntx-*` HTML tags | N3TX 0.10 | Shorter prefix, class names still NTT* |

**Deprecated/outdated:**
- `from n3tx.core.models import ...` -- old single-package import path; use `from n3tx_core.models...`
- `BaseUser.register()` -- renamed to `register_user()` to avoid Actor.register collision
- `__storable__ = True` without `ClassVar` annotation -- must use `ClassVar[bool]`

## Open Questions

Things that could not be fully resolved:

1. **Formidable handling of JSON list/dict fields**
   - What we know: SQLite storage auto-serializes `list`/`dict` fields. The schema correctly declares them as `type: array` or `type: object`.
   - What is unclear: How well does Formidable's auto-generated form handle editing nested JSON fields (e.g., `focus_areas` as a list of strings, `custom_criteria` as a key-value dict)?
   - Recommendation: Test with standard ntx-item first. If the form UX is poor for JSON fields, add `json_schema_extra={'ui': {'widget': 'textarea'}}` to render as a JSON text editor. A custom widget can be built in Phase 6 if needed.

2. **Auth redirect timing**
   - What we know: `permissions.init()` fetches `/auth/me` async, then redirects if no user.
   - What is unclear: There may be a brief flash of the main page content before redirect.
   - Recommendation: Add a CSS rule `body { visibility: hidden }` that is removed by JS after auth check completes. Or use a loading state.

3. **Organization documents list in schema**
   - What we know: `documents: list` stores filenames as a JSON array in SQLite.
   - What is unclear: The frontend won't automatically render file upload UI -- it will render the list as a JSON array field.
   - Recommendation: For Phase 1, documents are managed via the custom upload endpoint. The Organization form shows the document list as read-only. A custom widget for file management can be added later.

4. **Strategic documents already in docs/ directory**
   - What we know: FFT and RTS strategic plans exist as PDFs and text files in `/workspace/apps/veille/docs/`.
   - What is unclear: Should these be copied to the `uploads/` directory during seeding, or kept separate?
   - Recommendation: Keep them in `docs/` as reference. Seed the Organization's `documents` list with their filenames. The upload endpoint handles new documents. Pre-existing docs in `docs/` can be served via a separate route or symlinked.

## Sources

### Primary (HIGH confidence)
- `/workspace/examples/actors/main.py` -- Level 3 bootstrap pattern (verified line by line)
- `/workspace/examples/actors/models/user.py` -- User model pattern (verified)
- `/workspace/examples/actors/config.py` -- Config pattern (verified)
- `/workspace/examples/actors/seed.py` -- Seed script pattern (verified)
- `/workspace/examples/actors/static/index.html` -- Frontend structure (verified)
- `/workspace/examples/actors/static/login.html` -- Auth page pattern (verified)
- `/workspace/packages/n3tx-core/src/n3tx_core/models/base_user.py` -- BaseUser implementation (verified)
- `/workspace/packages/n3tx-core/src/n3tx_core/models/proto_model.py` -- ProtoModel, mixin injection (verified)
- `/workspace/packages/n3tx-core/src/n3tx_core/models/storable_mixin.py` -- CRUD operations (verified)
- `/workspace/packages/n3tx-core/src/n3tx_core/app.py` -- create_app, N3TXApp builder (verified)
- `/workspace/packages/n3tx-core/src/n3tx_core/api/backend.py` -- FastAPIBackend, static mount (verified)
- `/workspace/packages/n3tx-actors/src/n3tx_actors/models/actor_model.py` -- ActorModel bridge (verified)
- `/workspace/packages/n3tx-core/src/n3tx_core/widgets/widget.py` -- Widget field types (verified)
- `/workspace/packages/n3tx-core/src/n3tx_core/authorize/__init__.py` -- Access rules (verified)
- `/workspace/packages/n3tx-core/src/n3tx_core/config.py` -- Framework config (verified)
- `/workspace/packages/n3tx-core/src/n3tx_core/static/utils/Permissions.js` -- Frontend auth (verified)
- `/workspace/examples/chat/main.py` -- Custom route insertion pattern (verified)

### Secondary (MEDIUM confidence)
- `/workspace/apps/veille/.planning/research/ARCHITECTURE.md` -- Model definitions from project research
- `/workspace/apps/veille/.planning/research/SUMMARY.md` -- Stack recommendations from project research
- `/workspace/apps/veille/.planning/research/PITFALLS.md` -- Pitfall catalog from project research

### Tertiary (LOW confidence)
- File upload handling with `python-multipart` -- based on FastAPI documentation knowledge (training data). Needs validation that `UploadFile` works alongside N3TX's ASGI middleware stack.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all from verified framework source code and working examples
- Architecture: HIGH -- project structure directly mirrors actors example with minimal adaptation
- Model definitions: HIGH -- field types, ClassVar annotations, access rules verified against framework source
- File upload: MEDIUM -- custom route pattern verified (chat example), but multipart integration untested with N3TX middleware
- Frontend: HIGH -- index.html structure copied from working example, auth redirect verified via Permissions.js
- Pitfalls: HIGH -- all sourced from framework code, test suites, and accumulated project memory

**Research date:** 2026-03-20
**Valid until:** 60 days (stable N3TX patterns, no fast-moving dependencies)
