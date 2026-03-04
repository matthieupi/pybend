# Coding Conventions

**Analysis Date:** 2026-03-04

## Naming Patterns

**Files:**
- Python modules: `snake_case.py` (e.g., `actor_model.py`, `proto_schema.py`, `sqlite_storage.py`)
- Model files: singular noun in `snake_case` (e.g., `grant.py`, `source.py`, `user.py`)
- Test files: `test_{module_name}.py` (e.g., `test_actor_system.py`, `test_grants_crud.py`)
- Config files: `config.py` at app root, `pyproject.toml` at workspace root
- Helper files: `helpers.py` in test directories

**Classes:**
- Models: `PascalCase`, singular noun (`Grant`, `Source`, `User`, `WebTools`)
- Mixins: `PascalCase` + `Mixin` suffix (`StorableMixin`, `AgentMixin`, `ViewableMixin`)
- Base classes: `PascalCase` + `Base`/`Proto` prefix (`ProtoModel`, `BaseUser`)
- Bridge classes: compound name (`ActorModel` = Actor + ProtoModel)
- Internal test models: prefixed with underscore (`_CrudModel`, `_M`)

**Functions:**
- Public functions: `snake_case` (`create_app`, `register_model`, `expose_route`)
- Private functions: `_snake_case` with leading underscore (`_setup_test_db`, `_seed_users`, `_authorize`)
- Factory functions: `_make_{noun}` pattern (`_make_product`, `_make_comment`)
- Test functions: `test_{description}` in snake_case (`test_create_grant_authenticated`)

**Variables:**
- Constants: `UPPER_SNAKE_CASE` (`JWT_SECRET`, `SQLITE_DB_FILE`, `_CRUD_OPS`, `_NOT_HANDLED`)
- ClassVars: `__dunder__` for framework attrs (`__tablename__`, `__storable__`, `__access__`, `__agent__`)
- PrivateAttrs: `_snake_case` for Pydantic PrivateAttr (`_addr`, `_children`, `_parent`, `_interceptors`)
- Logger instances: `logger = logging.getLogger('pybend.{module}')` at module level

**Types:**
- Type aliases: `PascalCase` (`Ref`, `ListRef`, `CurrencyField`, `DateField`, `UrlField`)
- Widget fields: `PascalCase` + `Field` suffix (`CurrencyField`, `TextareaField`, `UrlField`)

## Code Style

**Formatting:**
- No dedicated formatter configured (no `.prettierrc`, `.flake8`, `ruff.toml` found)
- Indentation: 4 spaces (Python standard)
- Line length: generally stays under ~120 chars, no enforced limit
- String quotes: single quotes preferred for identifiers and keys (`'name'`), double quotes for docstrings and messages

**Linting:**
- No dedicated linter config file (no `.flake8`, `ruff.toml`)
- `# noqa:` comments used sparingly for intentional import side effects (e.g., `from main import app  # noqa: triggers model registration`)

**Docstrings:**
- Module-level docstrings describe purpose, usage examples, and architecture context
- Class docstrings: one-line summary or paragraph explaining purpose and relationship
- Function docstrings: present for public APIs, format is plain text (not NumPy/Google style)
- Docstrings omitted on obvious test methods — test name is self-documenting

## Import Organization

**Order:**
1. Standard library (`os`, `sys`, `logging`, `asyncio`, `json`, `time`, `tempfile`)
2. Third-party (`pydantic`, `fastapi`, `pytest`, `httpx`)
3. Framework internals (`pybend.core.actors`, `pybend.core.models`, `pybend.core.utils`)
4. Local app modules (`models`, `config`, `helpers`)

**Path Aliases:**
- No path aliases (`tsconfig` paths or similar) — uses `sys.path.insert()` in conftest and entry points
- Example apps prepend `src/` to `sys.path`: `sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))`
- Test conftest files use namespace shims for `pybend` and `pybend.core`:
  ```python
  _namespace_shims = {
      'pybend': _pybend,
      'pybend.core': _core,
  }
  for name, path in _namespace_shims.items():
      if name not in sys.modules:
          m = types.ModuleType(name)
          m.__path__ = [path]
          sys.modules[name] = m
  ```

**Model barrel files (`models/__init__.py`):**
```python
from .user import User
from .grant import Grant
from .source import Source
from .web_tools import WebTools

__all__ = ["User", "Grant", "Source", "WebTools"]
```

## Model Definition Patterns

**Canonical model structure** (follow this pattern for all new models):
```python
from __future__ import annotations
from typing import ClassVar, Optional
from pydantic import Field

from pybend.core.models.actor_model import ActorModel
from pybend.core.authorize import ANYONE, AUTHENTICATED, OWNER, ROLE
from pybend.core.widgets import UrlField, DateField, CurrencyField, TextareaField

class Grant(ActorModel):
    """A government grant discovered by an agent."""

    __tablename__: ClassVar[str] = 'grants'
    __storable__: ClassVar[bool] = True
    __protected_fields__: ClassVar[set] = {'user_owner'}
    __access__: ClassVar[dict] = {
        'read': ANYONE,
        'create': AUTHENTICATED,
        'update': AUTHENTICATED | ROLE('admin'),
        'delete': OWNER | ROLE('admin'),
    }

    title: str = Field(min_length=1, max_length=500)
    agency: str = Field(min_length=1, max_length=200)
    deadline: Optional[DateField] = Field(default=None, description="Application deadline")
    amount_min: Optional[CurrencyField] = Field(default=None, description="Minimum award amount")
    url: UrlField = Field(description="URL to the grant listing")
    description: TextareaField = Field(default='')
    status: Literal['discovered', 'reviewed', 'applied', 'expired'] = Field(default='discovered')
    user_owner: User = Field(default=None, json_schema_extra={'access': {'view': 'authenticated', 'edit': 'owner'}})
```

**Key conventions for models:**
- Always annotate `__tablename__`, `__storable__`, `__access__`, `__protected_fields__` with `ClassVar[...]`
- Use `from __future__ import annotations` for forward references
- Use `Field()` for all fields, never bare defaults
- Use Widget types (`UrlField`, `CurrencyField`, etc.) instead of raw `str`/`float` where semantically appropriate
- `__storable__ = False` for utility actors that have methods but no DB table (e.g., `WebTools`)
- Model inheritance: `ActorModel` for actor-routed apps, `ProtoModel` for direct-route apps

**Non-storable utility actors** (methods only, no DB):
```python
class WebTools(ActorModel):
    __tablename__: ClassVar[str] = 'web_tools'
    __storable__: ClassVar[bool] = False

    @expose_route('/scrape', methods=['POST'], access=AUTHENTICATED)
    async def scrape(self, url: str) -> dict:
        ...
```

## Mixin Injection via `__init_subclass__`

Use `__init_subclass__` to dynamically inject mixins based on class attributes. This is the framework's primary extension mechanism.

**Pattern in `ProtoModel.__init_subclass__`** (`src/pybend/core/models/proto_model.py`):
```python
def __init_subclass__(cls, **kwargs):
    __storable__ = getattr(cls, '__storable__', False)
    if __storable__:
        if not issubclass(cls, StorableMixin):
            cls.__bases__ = (StorableMixin,) + cls.__bases__
```

**Pattern in `AgentMixin`** (`src/pybend/core/agents/mixin.py`):
- `__agent__ = True` on a model triggers `AgentMixin` injection
- Provides `agent_run()` method for LLM execution

**Pattern in `ActorMeta` metaclass** (`src/pybend/core/actors/actor.py`):
- Each Actor subclass gets its own `__children__` dict and `__interceptors__` dict
- `__addr__` defaults from `__tablename__` or class name
- Auto-registers with root Matrix if `auto_register=True` (default)

## Custom Method Pattern (`@expose_route`)

Use `@expose_route` to add API endpoints to models:

```python
from pybend.core.utils.decorators import expose_route
from pybend.core.authorize import AUTHENTICATED

@expose_route('/like', methods=['POST'], access=AUTHENTICATED)
def like(self, user: User = None) -> str:
    """Like this entity. User is injected from JWT."""
    ...
```

The decorator stores endpoint metadata on `func.__endpoint__`:
```python
func.__endpoint__ = {
    'route': route,
    'methods': methods,
    'access': access,
}
```
Defined in `src/pybend/core/utils/decorators.py`.

## Error Handling

**MethodError for custom method errors:**
```python
from pybend.core.utils.erroring import MethodError

@expose_route('/like', methods=['POST'])
def like(self, user=None):
    if not user:
        raise MethodError("authentication required", 401)
```
Defined in `src/pybend/core/utils/erroring.py`. Route layer converts to HTTP response with proper status code.

**TX.error() for actor-routed error responses:**
```python
# In handler methods
return tx.error("Access denied", code=403)

# Exception mapping via tx.exception()
try:
    ...
except Exception as e:
    return tx.exception(e)
```
Exception-to-HTTP-code mapping (`src/pybend/core/actors/tx.py`):
| Exception | HTTP Code |
|-----------|-----------|
| `MethodError` | Uses its `.status_code` |
| `HTTPException` | Uses its `.status_code` |
| `ValidationError` (Pydantic) | 422 |
| `ValueError`, `TypeError` | 400 |
| `PermissionError` | 403 |
| `KeyError` | 400 |
| All others | 500 |

**Error TX short-circuit in interceptors:**
- Interceptors return `TX` objects. If `tx.is_error` is True after an interceptor, the chain stops.
- `is_error` checks `tx.name == 'ERROR'` or `tx.meta.get('error', False)`.

## Pydantic Patterns

**PrivateAttr for internal state:**
```python
from pydantic import PrivateAttr

_addr: str = PrivateAttr(default='')
_children: dict = PrivateAttr(default_factory=dict)
_parent: Optional[Any] = PrivateAttr(default=None)
```
Used in Actor class. Pop kwargs BEFORE `super().__init__()`, set PrivateAttrs AFTER.

**ConfigDict:**
```python
from pydantic import ConfigDict

model_config = ConfigDict(
    ignored_types=(actormethod, actorproperty),
    arbitrary_types_allowed=True,
    extra='allow',
)
```

**json_schema_extra for UI and access hints:**
```python
price: float = Field(
    gt=0,
    json_schema_extra={
        'ui': {'widget': 'currency'},
        'access': {'view': 'anyone', 'edit': 'admin'},
    }
)
```

**model_validator for storage deserialization:**
```python
@model_validator(mode='before')
@classmethod
def _deserialize_json_fields(cls, data):
    if isinstance(data, dict):
        for field in ('tools', 'constraints'):
            if isinstance(data.get(field), str):
                data[field] = json.loads(data[field])
    return data
```
Required for SQLite JSON fields (`list`/`dict` fields stored as JSON TEXT).

## Actor System Patterns

**actormethod descriptor** (unified class/instance dispatch):
```python
@actormethod
async def inbox(target, tx: TX) -> None:
    # target is cls when called as Product.inbox(tx)
    # target is self when called as product.inbox(tx)
    await target.handler(tx)
```

**actorproperty descriptor** (unified class/instance properties):
```python
@actorproperty
def addr(target) -> str:
    if isinstance(target, type):
        return target.__addr__
    return target._addr
```

**Interceptor registration:**
```python
actor.use(auth_interceptor, on='request')

@actor.use(on='inbox')
async def log_messages(tx: TX) -> TX:
    print(f"Received: {tx.name}")
    return tx
```

**TX message envelope:**
```python
tx = TX(name='create', source='api', target='products', data={...}, meta={'user': {...}})
reply = tx.reply(data={'id': 1})        # _RESPONSE suffix, swaps source/target
error = tx.error("Not found", code=404) # ERROR name, swaps source/target
```

## Test Patterns (Mock)

**mock_method for Pydantic instances** (Pydantic's `__setattr__` prevents normal patching):
```python
from contextlib import contextmanager

@contextmanager
def mock_method(instance, name, replacement):
    object.__setattr__(instance, name, replacement)
    try:
        yield replacement
    finally:
        object.__delattr__(instance, name)
```
Defined in `src/pybend/core/tests/unit/test_actor_system.py`. Use for any Actor/Model instance.

**TestModel for agent LLM testing:**
```python
from pydantic_ai.models.test import TestModel

result = await agent.run(
    task='Find grants',
    llm=TestModel(call_tools=['grants_list']),  # or call_tools=[] for no tool calls
)
```

**Reset actor state between tests:**
```python
@pytest.fixture(autouse=True)
def reset_actor_state():
    saved_matrix = Actor.__matrix__
    saved_children = Actor.__children__.copy()
    Actor.__matrix__ = None
    Actor.__children__ = {}
    yield
    Actor.__matrix__ = saved_matrix
    Actor.__children__ = saved_children
```

## Configuration Patterns

**Framework config (`src/pybend/core/config.py`):**
- Module-level globals with `UPPER_SNAKE_CASE`
- `PYBEND_*` env var overrides applied at import time
- `config.configure(**kwargs)` for programmatic override

**App config (`example_grants/config.py`):**
```python
import os
from pybend.core import config as _fw

HOST = os.environ.get("PYBEND_HOST", "0.0.0.0")
PORT = int(os.environ.get("PYBEND_PORT", "5000"))
SQLITE_DB_FILE = os.environ.get("PYBEND_SQLITE_DB", "grants.db")
JWT_SECRET = os.environ.get("PYBEND_JWT_SECRET", "pybend-dev-secret-change-in-production")

_fw.configure(host=HOST, port=PORT, api_url=API_URL, ...)
```

**Test config:** Tests skip doc generation with `os.environ["GENERATE_DOCS"] = "false"` before importing the app.

## Commit Message Conventions

```
type(scope): Description [wave]
```

- **type**: `feat`, `fix`, `test`, `docs`, `refactor`, `chore`
- **scope** (optional): `models`, `actors`, `api`, `ssr`, `frontend`, `schema`, `example`
- **Description**: imperative mood, capitalized ("Add", "Fix", not "Added", "Fixes")
- **[wave]**: current dev wave in brackets (e.g., `[0.9]`)

Examples:
```
feat(actors): Add interceptor mechanism and two-tier auth [0.8.2]
fix(api): Default DEBUG off, disable CORS credentials on wildcard [0.9]
test: Add auth, authorization, and security test suites [0.9]
```

## App Bootstrap Pattern

**Level 1 (create_app):**
```python
from pybend.core.app import create_app

app = create_app(
    models=[User, Grant, Source, WebTools, AgentTool, AgentActor],
    join_models=[(AgentActor, AgentTool)],
    storage=storage,
    routing='actor',
    static_dir=os.path.join(_HERE, 'static'),
    jwt_secret=config.JWT_SECRET,
    name="Grant Watcher",
)
```
See `example_grants/main.py` for the canonical example.

## Access Control Patterns

**Declarative ABAC via `__access__`:**
```python
from pybend.core.authorize import ANYONE, AUTHENTICATED, OWNER, ROLE

__access__ = {
    'read': ANYONE,
    'create': AUTHENTICATED,
    'update': OWNER | ROLE('admin'),
    'delete': OWNER | ROLE('admin'),
}
```
Rules compose with `|` (OR) and `&` (AND). The `authorize` package has zero PyBend imports.

**Method-level access:**
```python
@expose_route('/comment', methods=['POST'], access=AUTHENTICATED)
def comment(self, comment: Comment, user: User = None) -> str:
    ...
```

---

*Convention analysis: 2026-03-04*
