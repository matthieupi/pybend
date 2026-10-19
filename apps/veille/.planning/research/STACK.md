# Technology Stack: Veille Grant Monitoring App

**Project:** Veille
**Researched:** 2026-03-20
**Confidence:** HIGH (primary source: N3TX framework source code, docs, and working examples)

---

## Recommended Stack

### Core Framework

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| N3TX (meta-package) | 0.10+ | Full-stack framework | Provides models, actors, agents, UI in one coherent system. Veille is explicitly built on N3TX. |
| n3tx-core | 0.10+ | Models, storage, auth, routes, JS runtime | Foundation: ProtoModel, StorableMixin, SQLiteStorage, BaseUser, JSON Schema pipeline |
| n3tx-actors | 0.10+ | Actor messaging, Level 3 routing | NetworkAPI for actor routing, TX messaging for inter-model communication |
| n3tx-agents | 0.10+ | LLM-powered reasoning | AgentMixin, AgentActor, tool discovery, streaming -- the core of Veille's intelligence |
| n3tx-ui | 0.10+ | Web components, widgets, themes | Schema-driven UI: ntx-list, ntx-item, ntx-stream, Formidable forms |
| FastAPI | 0.100+ | HTTP layer (used by N3TX internally) | Underlying ASGI server. Not imported directly in app code. |
| Pydantic | 2.x | Validation (used by N3TX internally) | Model field types, JSON Schema generation. Used via N3TX's ProtoModel. |
| Pydantic AI | 1.0+ | LLM agent loop (used by n3tx-agents) | Multi-provider LLM support, ReAct-style tool calling, streaming. Not imported directly. |

### Database

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| SQLite | 3.x | Primary data store | N3TX's native storage backend. Auto-migration, JSON field serialization, FK hydration all built-in. Single-org deployment makes SQLite appropriate. |

### LLM Providers

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Anthropic Claude | claude-sonnet-4-5-20250929 | Primary LLM for scraping/analysis | Best reasoning for grant admissibility analysis. Configurable via `llm` field on agents. |
| Ollama (local) | llama3.1 | Development/fallback | Free local inference for development. Default in N3TX config. |

### Supporting Libraries (App-Level)

| Library | Purpose | When to Use |
|---------|---------|-------------|
| httpx | HTTP client for web scraping | Inside `@expose_route` scraping methods on tool models |
| beautifulsoup4 | HTML parsing | Extract structured content from scraped pages |
| weasyprint or reportlab | PDF generation | Report export feature (Phase 3+) |
| smtplib (stdlib) | Email sending | Report notification feature (Phase 3+) |

### Infrastructure

| Technology | Purpose | Why |
|------------|---------|-----|
| uvicorn | ASGI server | Standard for FastAPI/N3TX apps |
| Docker | Containerization | Production deployment |

---

## N3TX Components for Veille

### Level 3 Architecture (Actor Routing)

Veille uses Level 3 routing (`routing='actor'`). This means:

1. All HTTP requests flow through `NetworkAPI` adapter
2. Requests become TX messages routed through `Matrix`
3. `ActorModel` classes handle messages via `handler_crud()`
4. Two-tier auth: `auth_interceptor` (Tier 1) + `_authorize()` (Tier 2)

**Why Level 3:** Agents need Matrix for tool call routing. `discover_tools()` reads schemas from Matrix children. Tool calls create TX messages routed through `Actor.root().request()`. Without Level 3, agent tool calling does not work.

```python
# main.py bootstrap pattern
import n3tx_agents  # MUST be before model imports (registers AgentMixin)
from models import User, Source, Grant, OrgProfile, Run, Report
from n3tx_core.app import create_app
from n3tx_core.storage.sqlite_storage import SQLiteStorage

storage = SQLiteStorage('veille.db')
app = create_app(
    models=[User, Source, Grant, OrgProfile, Run, Report],
    join_models=[...],
    storage=storage,
    routing='actor',
    jwt_secret='veille-secret-change-me',
    static_dir='static/',
    ssr='full',
    name='Veille',
    version='0.1.0',
    description='Agentic grant monitoring for non-profits',
)
```

### Model Definitions

All Veille models use `ActorModel` (not `ProtoModel`) because Level 3 requires it.

**Import pattern:**
```python
from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.models.base_user import BaseUser
from n3tx_core.models.ref import ListRef
from n3tx_core.utils.decorators import expose_route
from n3tx_core.authorize import ANYONE, AUTHENTICATED, OWNER, ROLE
from n3tx_core.widgets import UrlField, TextareaField, MarkdownField, DateField
from pydantic import Field
from typing import ClassVar, Optional
```

**Model structure pattern:**
```python
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
        'field_order': ['title', 'source_url', 'amount', 'deadline', 'status', 'admissibility'],
        'groups': {
            'main': ['title', 'description', 'source_url'],
            'Details': ['amount', 'deadline', 'criteria', 'required_documents', 'application_process'],
            'Analysis': ['status', 'admissibility', 'admissibility_reasoning'],
        },
        'renderer': {'item': 'ntx-item', 'list': 'ntx-list'},
    }

    title: str = Field(min_length=1, max_length=500)
    description: TextareaField = Field(default='')
    source_url: UrlField = Field(default='')
    amount: str = Field(default='', description='Grant amount or range')
    deadline: str = Field(default='', description='Application deadline')
    criteria: TextareaField = Field(default='', description='Eligibility criteria')
    required_documents: TextareaField = Field(default='')
    application_process: TextareaField = Field(default='')
    status: str = Field(default='new', description='new|analyzed|admissible|partial|non-admissible')
    admissibility: str = Field(default='pending', description='pending|admissible|partial|non-admissible')
    admissibility_reasoning: MarkdownField = Field(default='')
    source_id: Optional[int] = Field(default=None, description='FK to source')
    run_id: Optional[int] = Field(default=None, description='FK to run that discovered this')
```

### Agent System

Veille needs two types of agents:

#### Type 1: Agentic Models (Primary Pattern)

Models with `__agent__ = True` that have LLM-powered methods. This is the right pattern for Veille because:
- The Run model orchestrates scraping and analysis -- it IS the thing that reasons
- Custom `@expose_route` methods with `stream=True` give real-time progress
- Config comes from the model definition, not DB fields

```python
class Run(ActorModel):
    __tablename__: ClassVar[str] = 'runs'
    __storable__: ClassVar[bool] = True
    __agent__: ClassVar = {
        'self_tools': True,
        'neighbors': False,      # We specify tools explicitly
        'tools': ['sources', 'grants', 'org_profiles', 'web_tools'],
        'prompt': 'You are a grant monitoring agent...',
    }

    status: str = Field(default='pending')
    started_at: str = Field(default='')
    completed_at: str = Field(default='')
    grants_found: int = Field(default=0)
    grants_admissible: int = Field(default=0)
    report_summary: MarkdownField = Field(default='')

    @expose_route('/execute', methods=['POST'], stream=True, access=AUTHENTICATED,
                  events={
                      'text': TextChunk, 'tool_call': ToolCallEvent,
                      'tool_result': ToolResultEvent, 'done': DoneChunk,
                  })
    async def execute(self, user: User = None):
        """Execute the run -- scrape all sources and analyze grants."""
        async for chunk in self.agentic_stream(
            task='Scrape all configured sources for new grants...',
            user=user,
        ):
            yield chunk
```

**Config cascade for `__agent__`:**
```
config.AGENT_DEFAULTS < __agent__ dict < agentic() kwargs
```

The `__agent__` dict supports:
- `self_tools` (bool): Include own CRUD as tools (default True)
- `neighbors` (bool): Include ListRef neighbor models as tools (default True)
- `tools` (list[str]): Extra actor addresses to include
- `prompt` (str): System prompt prepended to auto-generated context
- `llm` (str): Override default LLM
- `constraints` (dict): Override default constraints

#### Type 2: Tool Models (Non-Storable Actors)

Models that provide custom tools (scraping, web fetching) but don't store data. These are NOT agents -- they are tool collections that agents use.

```python
class WebTools(ActorModel):
    __tablename__: ClassVar[str] = 'web_tools'
    __storable__: ClassVar[bool] = False  # No DB table

    @expose_route('/scrape', methods=['POST'], access=AUTHENTICATED)
    async def scrape(self, url: str) -> dict:
        """Fetch a URL and return its content."""
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url)
        return {'url': url, 'status': resp.status_code, 'html': resp.text[:50000]}

    @expose_route('/extract_text', methods=['POST'], access=AUTHENTICATED)
    async def extract_text(self, url: str) -> dict:
        """Fetch a URL and extract clean text content."""
        import httpx
        from bs4 import BeautifulSoup
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url)
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text(separator='\n', strip=True)
        return {'url': url, 'text': text[:50000]}
```

**How tool discovery works:**

1. `discover_tools(['sources', 'grants', 'web_tools'], matrix)` is called
2. For each address, looks up the actor in `matrix._children`
3. Gets the class, calls `cls.schema()`
4. If storable: generates CRUD tool specs (list, get, create, update, delete)
5. For each `@expose_route` method: generates a method tool spec
6. Tool naming: `{tablename}_{method}` (e.g., `web_tools_scrape`, `grants_create`)

**Tool call routing:**

Generated tool functions create TX messages:
```
TX(name='scrape', source='matrix', target='web_tools', data={'url': '...'})
```
Sent via `Actor.root().request(tx)` for Future-based correlation.
Error TXs raise `ModelRetry` (Pydantic AI retries with the LLM).

### Streaming

Veille heavily uses streaming for real-time progress during long-running agent operations.

**Backend pattern:**
```python
@expose_route('/execute', methods=['POST'], stream=True, access=AUTHENTICATED,
              events={
                  'text': TextChunk, 'tool_call': ToolCallEvent,
                  'tool_result': ToolResultEvent, 'thinking': ThinkingChunk,
                  'done': DoneChunk,
              })
async def execute(self, task: str = '', user: User = None):
    async for chunk in self.agentic_stream(task=task, user=user):
        yield chunk
```

**Stream event models** (shipped with n3tx-agents):
```python
from n3tx_agents.actor import TextChunk, ToolCallEvent, ToolResultEvent, ThinkingChunk, DoneChunk
```

| Event Model | Fields | When Emitted |
|-------------|--------|--------------|
| `TextChunk` | `text: str` | LLM produces text tokens |
| `ToolCallEvent` | `tool: str, args: dict, call_id: str` | LLM calls a tool |
| `ToolResultEvent` | `tool: str, result: str, call_id: str` | Tool returns result |
| `ThinkingChunk` | `text: str` | LLM reasoning/thinking |
| `DoneChunk` | `answer: str, usage: dict, tool_calls: int` | Agent completes task |

**SSE wire format:**
```
event: chunk
data: {"name": "text", "data": {"text": "Found grant..."}, "meta": {"stream": true, "seq": 0}}

event: chunk
data: {"name": "tool_call", "data": {"tool": "grants_create", "args": {...}}, "meta": {"stream": true, "seq": 1}}

event: done
data: {"name": "done", "data": {"answer": "...", "usage": {...}}, "meta": {"stream_end": true}}
```

**Frontend consumption via StreamActor mixin:**
```javascript
import { StreamActor } from './StreamActor.js';

class VeilleRunView extends StreamActor(HTMLElement) {
    TEXT(data, meta)        { /* Append data.text to output */ }
    TOOL_CALL(data, meta)   { /* Show "Calling: grants_create..." */ }
    TOOL_RESULT(data, meta) { /* Show tool result */ }
    THINKING(data, meta)    { /* Show thinking indicator */ }
    DONE(data, meta)        { /* data.answer, data.usage — show summary */ }
    STREAM_END(data)        { /* Cleanup, enable re-run button */ }
    STREAM_ERROR(err)       { /* Show error */ }
}
```

### Storage

**SQLite with automatic features:**

| Feature | How It Works | Relevant for Veille |
|---------|-------------|---------------------|
| Auto-migration | `sqlite_migration.py` adds new columns when model fields change | Models will evolve as we iterate |
| JSON fields | `dict` and `list` fields auto-serialize to JSON TEXT | Grant criteria, org profile fields, run results |
| FK hydration | `ListRef[T]` fields return href arrays, hydrated on read | Grant -> Source relationship |
| Pagination | `?limit=N&offset=M` on list endpoints | Grant list, run history |
| Protected fields | `__protected_fields__` auto-injected on create, stripped on update | `user_owner` on runs |

**JSON field pattern** (automatic in N3TX 0.10+):
```python
class OrgProfile(ActorModel):
    mission: str = Field(default='')
    activities: list = Field(default=[])          # Auto-serialized to JSON TEXT
    past_grants: list = Field(default=[])         # Auto-serialized to JSON TEXT
    custom_criteria: dict = Field(default={})     # Auto-serialized to JSON TEXT
```

No need for manual `_storage_dict()` or `@model_validator` -- the framework handles it via `_coerce_value()` and `_deserialize_json_fields()` in `sqlite_storage.py`.

### Authentication & Authorization

**User model:**
```python
class User(BaseUser, ActorModel):
    __tablename__: ClassVar[str] = 'users'
    __abstract__: ClassVar[bool] = False
    __ui__: ClassVar[dict] = {
        'renderer': {'item': 'ntx-user'},
    }
    image: str = Field(default='https://ui-avatars.com/api/?name=User&...')
```

`BaseUser` provides: `name`, `email`, `role`, `password_hash`, plus `login()` and `register_user()` endpoints. Note: method is `register_user()` (not `register()`) to avoid MRO collision with `Actor.register()`.

**Access rules for Veille** (admin-only app):
```python
# All users are admins -- but we still use AUTHENTICATED for consistency
__access__ = {
    'read': AUTHENTICATED,
    'create': AUTHENTICATED,
    'update': AUTHENTICATED,
    'delete': ROLE('admin'),
}
```

**JWT flow:**
1. `POST /users/login` with email/password returns JWT token
2. All subsequent requests include `x-access-token: <token>` header
3. Schema endpoints (`GET /ClassName`) are always public (no auth)
4. Custom methods can receive user via `user: User = None` parameter

### Frontend

**Schema-driven rendering.** The frontend receives JSON Schema from the backend and adapts automatically:

1. `<ntx-list model="Grant">` triggers schema fetch `GET /Grant`
2. Schema includes properties, UI hints, access rules, methods
3. `prototype()` creates DynamicClass with typed getters/setters
4. Data fetch `GET /grants?limit=20&offset=0` returns paginated results
5. Each item rendered via `<ntx-item>` with forms from `Formidable`

**Available widgets (Python side):**

| Widget | Import | Validates As | Frontend Renders As |
|--------|--------|-------------|---------------------|
| `UrlField` | `from n3tx_core.widgets import UrlField` | `AnyHttpUrl` | Clickable link |
| `TextareaField` | `from n3tx_core.widgets import TextareaField` | `str` | Multi-line textarea |
| `MarkdownField` | `from n3tx_core.widgets import MarkdownField` | `str` | Markdown renderer |
| `DateField` | `from n3tx_core.widgets import DateField` | `date` | Date picker |
| `DateTimeField` | `from n3tx_core.widgets import DateTimeField` | `datetime` | Datetime picker |
| `CurrencyField` | `from n3tx_core.widgets import CurrencyField` | `float` | Currency input |
| `EmailField` | `from n3tx_core.widgets import EmailField` | `EmailStr` | Email input |
| `ConsoleField` | `from n3tx_core.widgets import ConsoleField` | `str` | Code/console display |

**Available frontend components:**

| Component | Tag | Purpose |
|-----------|-----|---------|
| `ntx-list` | `<ntx-list model="Grant">` | Grid/list of entities with pagination |
| `ntx-item` | `<ntx-item>` | Single entity view (xs pill to xl page) |
| `ntx-table` | `<ntx-table model="Grant">` | Table view of entities |
| `ntx-row` | `<ntx-row>` | Table row |
| `ntx-method` | `<ntx-method>` | Method call button |
| `ntx-stream` | `<ntx-stream>` | Streaming method output with progressive rendering |
| `ntx-agent-live` | `<ntx-agent-live>` | Real-time agent activity log (StreamActor) |
| `ntx-chat` | `<ntx-chat>` | Agent chat panel (StreamActor) |
| `ntx-sidebar` | `<ntx-sidebar>` | Model navigation sidebar |
| `ntx-topbar` | `<ntx-topbar>` | Header/nav bar |
| `ntx-modal` | `<ntx-modal>` | Modal overlay |
| `ntx-ref-picker` | `<ntx-ref-picker>` | Reference field picker |
| `ntx-router` | `<ntx-router>` | View container (loads any component via Router) |
| `ntx-profile` | `<ntx-profile>` | User profile page |
| `ntx-user` | `<ntx-user>` | User display |

**Custom frontend components for Veille:**

For run execution with real-time progress, extend `StreamActor`:
```javascript
import { StreamActor } from './StreamActor.js';

class VeilleRunView extends StreamActor(HTMLElement) {
    // UPPERCASE handlers for stream events
    TEXT(data, meta) { /* ... */ }
    TOOL_CALL(data, meta) { /* ... */ }
    DONE(data, meta) { /* ... */ }
    STREAM_END(data) { /* ... */ }
}
customElements.define('veille-run-view', VeilleRunView);
```

For standard CRUD views, the built-in `ntx-list` and `ntx-item` work out of the box. Custom components are only needed for:
- Run execution view (streaming agent progress)
- Dashboard/report view (aggregated data)
- Organization profile editor (specialized form)

**Static file serving:**
App-specific static files in `apps/veille/static/` are merged with framework statics via `create_app(static_dir='static/')`. App files override framework defaults (e.g., custom `index.html`).

---

## Key Patterns to Follow

### 1. Import Ordering (Critical)

```python
# main.py -- order matters!
import n3tx_agents        # 1. Register AgentMixin BEFORE model imports
from models import ...    # 2. Models can now use __agent__ = True
from n3tx_core.app import create_app  # 3. App builder
```

If `n3tx_agents` is imported after model definitions, `AgentMixin` is silently not injected. This causes agent methods (`agentic()`, `run()`, etc.) to not exist on the model.

### 2. ActorModel for Everything

Every Veille model uses `ActorModel` (from `n3tx_actors.models.actor_model`), not `ProtoModel`. This is required for Level 3 routing.

```python
from n3tx_actors.models.actor_model import ActorModel

class Source(ActorModel):
    __tablename__ = 'sources'
    __storable__ = True
    ...
```

### 3. Non-Storable Tool Models

Tool-providing models that have `@expose_route` methods but no DB table:

```python
class WebTools(ActorModel):
    __tablename__ = 'web_tools'
    __storable__ = False  # No DB table -- just a tool collection

    @expose_route('/scrape', methods=['POST'])
    async def scrape(self, url: str) -> dict:
        ...
```

These still register with Matrix (via `__tablename__`) and are discoverable by agents.

### 4. Streaming Agent Methods

The pattern for streaming agent execution on any model:

```python
@expose_route('/execute', methods=['POST'], stream=True, access=AUTHENTICATED,
              events={...})
async def execute(self, task: str = '', user: User = None):
    async for chunk in self.agentic_stream(task=task, user=user):
        yield chunk
```

`self.agentic_stream()` handles: LLM resolution, tool discovery, Pydantic AI agent loop, TX-aligned chunk yielding.

### 5. Join Models for Parent-Child

```python
# In main.py
from n3tx_core.models.proto_model import generate_join_model

app = create_app(
    models=[User, Source, Grant, OrgProfile, Run, Report],
    join_models=[
        (Run, Grant),      # RunGrant join: /runs/{id}/grants/...
        (Source, Grant),   # SourceGrant: /sources/{id}/grants/...
    ],
    ...
)
```

Join models auto-generate FK columns, nested routes, and collection endpoints.

### 6. ClassVar Annotations

Always annotate class variables with `ClassVar` to prevent Pydantic from treating them as fields:

```python
from typing import ClassVar

class Source(ActorModel):
    __tablename__: ClassVar[str] = 'sources'
    __storable__: ClassVar[bool] = True
    __agent__: ClassVar = True
    __access__: ClassVar[dict] = {...}
    __ui__: ClassVar[dict] = {...}
```

### 7. Protected Fields

Fields that the backend auto-injects on create (never from user input):

```python
class Run(ActorModel):
    __protected_fields__: ClassVar[set] = {'user_owner', 'started_at'}
    user_owner: Optional[int] = Field(default=None)
    started_at: str = Field(default='')
```

`routes_fastapi.py` auto-injects these on create, strips them on update. `form.js` hides them in edit mode.

### 8. UI Hints

Control frontend rendering without writing frontend code:

```python
__ui__ = {
    'field_order': ['title', 'source_url', 'amount', 'deadline', 'status'],
    'groups': {
        'main': ['title', 'description', 'source_url'],
        'Details': ['amount', 'deadline', 'criteria'],
        'Analysis': ['status', 'admissibility', 'reasoning'],
    },
    'methods': {
        'analyze': {'layout': 'inline', 'button_label': 'Analyze'},
    },
    'renderer': {'item': 'ntx-item', 'list': 'ntx-list'},
}
```

---

## Veille-Specific Model Architecture

### Proposed Models

| Model | Base | Storable | Agent | Purpose |
|-------|------|----------|-------|---------|
| `User` | `BaseUser + ActorModel` | Yes | No | Authentication |
| `OrgProfile` | `ActorModel` | Yes | No | Organization description for admissibility |
| `Source` | `ActorModel` | Yes | No | Scraping source URL + metadata |
| `Grant` | `ActorModel` | Yes | No | Discovered grant with full details |
| `Run` | `ActorModel` | Yes | Yes (`__agent__`) | Scraping + analysis execution |
| `Report` | `ActorModel` | Yes | No | End-of-run summary |
| `WebTools` | `ActorModel` | No | No | Scraping/extraction tool provider |

### Agent Architecture

**Single-Agent with Tool Delegation:**
- `Run` is the agent model (`__agent__ = True`)
- It orchestrates scraping and analysis via tools
- Tools: `sources` (list sources), `grants` (CRUD grants), `org_profiles` (read profile), `web_tools` (scraping)

**Why not multiple specialized agents?**
- Simpler to reason about
- Single prompt can be tuned for the full workflow
- Pydantic AI's tool calling is powerful enough for the full pipeline
- Multiple agents add coordination complexity without clear benefit at this scale

**Agent tools available to Run:**
| Tool Name | Source | Operation |
|-----------|--------|-----------|
| `sources_list` | Source (storable) | List configured sources |
| `sources_get` | Source (storable) | Get source details |
| `grants_list` | Grant (storable) | List existing grants (for dedup) |
| `grants_create` | Grant (storable) | Create new grant |
| `grants_update` | Grant (storable) | Update grant (set status, admissibility) |
| `org_profiles_get` | OrgProfile (storable) | Read organization profile |
| `web_tools_scrape` | WebTools | Fetch URL content |
| `web_tools_extract_text` | WebTools | Fetch and extract clean text |

### Relationships

```
OrgProfile (singleton per deployment)
    |
Source ---< Grant (source_id FK)
    |         |
    |         +--- admissibility_reasoning (analyzed against OrgProfile)
    |
Run ---< Grant (run_id FK, which run discovered it)
    |
    +--- Report (summary of run results)
```

### Deduplication Strategy

Before creating a grant, the agent lists existing grants and checks for title/URL matches. This is handled in the agent prompt:
```
"Before creating a new grant, search existing grants by title. If a match is found, update it instead of creating a duplicate."
```

---

## Configuration

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `N3TX_PORT` | `5000` | HTTP port |
| `N3TX_JWT_SECRET` | `ntx-dev-secret...` | JWT signing secret |
| `N3TX_SQLITE_DB` | `n3tx.db` | Database file path |
| `N3TX_SSR` | `off` | SSR mode (use `full` for Veille) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Local Ollama URL |
| `N3TX_AGENT_DEFAULTS` | (JSON) | Override default agent config |
| `N3TX_LOG_LEVEL` | `WARNING` | Log level |

### App-Level Config File

Follow the pattern from `examples/actors/config.py`:
```python
# apps/veille/config.py
import os

DEBUG = os.getenv('VEILLE_DEBUG', 'false').lower() in ('1', 'true')
HOST = os.getenv('VEILLE_HOST', '0.0.0.0')
PORT = int(os.getenv('VEILLE_PORT', '5000'))
JWT_SECRET = os.getenv('VEILLE_JWT_SECRET', 'veille-dev-secret-change-in-production')
SQLITE_DB_FILE = os.getenv('VEILLE_DB', 'veille.db')

# LLM Configuration
DEFAULT_LLM = os.getenv('VEILLE_LLM', 'anthropic:claude-sonnet-4-5-20250929')
OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
```

---

## Sources

All findings are from direct source code reading (HIGH confidence):

| Source | Path | What It Provided |
|--------|------|-----------------|
| CLAUDE.md | `/workspace/CLAUDE.md` | Complete framework guide, import patterns, architecture overview |
| BACKEND.md | `/workspace/BACKEND.md` | Backend patterns, streaming, widgets, auth |
| FRONTEND.md | `/workspace/FRONTEND.md` | Frontend architecture, components, StreamActor |
| ARCHITECTURE.md | `/workspace/docs/ARCHITECTURE.md` | System architecture, design patterns, data flow |
| CORE.md | `/workspace/docs/CORE.md` | Schema-driven development, model patterns |
| ACTORS.md | `/workspace/docs/ACTORS.md` | Actor system, TX messaging, NetworkAdapter |
| AGENTS.md | `/workspace/docs/AGENTS.md` | AgentMixin, AgentActor, tool discovery, streaming |
| MODELS.md | `/workspace/docs/MODELS.md` | Model layer, pipelines, StorableMixin |
| AgentMixin source | `packages/n3tx-agents/src/n3tx_agents/mixin.py` | Full agent implementation (ctx, tools, agentic, run, streaming) |
| AgentActor source | `packages/n3tx-agents/src/n3tx_agents/actor.py` | Dynamic agent model, stream events |
| Tool discovery source | `packages/n3tx-agents/src/n3tx_agents/tools.py` | ToolSpec, discover_tools, tool function generation |
| Widget source | `packages/n3tx-core/src/n3tx_core/widgets/widget.py` | Available widget field types |
| App bootstrap source | `packages/n3tx-core/src/n3tx_core/app.py` | create_app, N3TXApp, Level 3 wiring |
| Config source | `packages/n3tx-core/src/n3tx_core/config.py` | All configuration options |
| Actors example | `/workspace/examples/actors/` | Level 3 app pattern, model definitions |
| Chat example | `/workspace/examples/chat/` | AgentActor streaming pattern, conversation model |
| Thread model | `packages/n3tx-agents/src/n3tx_agents/thread.py` | Conversation persistence pattern |
| AgentTool model | `packages/n3tx-agents/src/n3tx_agents/tool_model.py` | Tool reference model |
