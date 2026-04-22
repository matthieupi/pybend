# Model Definition Patterns Audit

**Date**: 2026-03-26
**Scope**: All Python model files across packages/, examples/, and apps/
**Focus**: Consistency of model definitions, field patterns, class hierarchies, and schema configuration

---

## Executive Summary

30 unique models were cataloged across the codebase. The framework foundation models (ProtoModel, BaseUser, ActorModel, AgentActor) are well-documented and consistent. However, **significant drift exists in example and app models** around access control declarations, agent configuration types, field defaults, and import paths.

---

## Models Inventory

### Framework Foundation Models

#### ProtoModel (`packages/n3tx-core/src/n3tx_core/models/proto_model.py`)
- **Base class**: PydanticBaseModel
- **Role**: Foundation for all models
- **Key fields**: `id: int = 0`, `image: str = ''`
- **Docstring**: Present (comprehensive)
- **Notes**: Mixin registry pattern (`_mixin_registry`) expects mixins registered before model definition. Auto-hides fields matching `_AUTO_HIDE_FIELDS`.

#### BaseUser (`packages/n3tx-core/src/n3tx_core/models/base_user.py`)
- **Base class**: ProtoModel
- **`__storable__`**: True
- **`__abstract__`**: True (requires `__abstract__ = False` in subclass)
- **Key fields**: `name`, `email`, `role`, `password_hash` (excluded)
- **Methods**: `login()`, registration via `@expose_route`
- **Docstring**: Present (comprehensive)
- **Issues**:
  - Uses `__hidden_fields__ = {'password_hash'}` -- non-standard ClassVar, not documented
  - Uses `__owner_field__ = 'id'` -- non-standard ClassVar, not documented
  - Field validator for `role` coercion

#### StorableMixin (`packages/n3tx-core/src/n3tx_core/models/storable_mixin.py`)
- **Pattern**: Injected via `__init_subclass__` when `__storable__ = True`
- **`__pk__`**: `'id'`
- **Key methods**: `save()`, `create()`, `list()`, `update()`, `delete()`
- **Issues**: No docstrings on most methods. Join table logic mixed with CRUD.

#### ActorModel (`packages/n3tx-actors/src/n3tx_actors/models/actor_model.py`)
- **Base class**: `Actor, ProtoModel` (MI)
- **Key methods**: `handler()` as `@fullmethod`, `handler_crud()` adapter
- **Docstring**: Present (comprehensive)
- **Issues**: `_subscribers: ClassVar[list] = []` (non-standard pattern). `_NOT_HANDLED` sentinel for CRUD dispatch.

#### AgentActor (`packages/n3tx-agents/src/n3tx_agents/actor.py`)
- **Base class**: ActorModel
- **`__tablename__`**: `'agents'`
- **`__storable__`**: True
- **`__agent__`**: True
- **Key fields**: `name`, `prompt`, `tools: ListRef[AgentTool]`, `llm`, `constraints: dict`
- **Docstring**: Present (comprehensive)
- **Issues**:
  - No `__access__` defined (security risk on a concrete storable model)
  - `constraints: dict` uses raw dict (should be typed)
  - Stream event models (TextChunk, ToolCallEvent, etc.) defined in same file

#### AgentTool (`packages/n3tx-agents/src/n3tx_agents/tool_model.py`)
- **Base class**: ActorModel
- **`__tablename__`**: `'agent_tools'`
- **`__storable__`**: True
- **Issues**: No `__access__`, no `__ui__`

---

### Example Models -- Core (Level 1/2)

#### Product (`examples/core/models/product.py`)
- **Base class**: ProtoModel
- **`__tablename__`**: `'products'`
- **`__storable__`**: True
- **`__access__`**: Not set (inherits defaults)
- **`__ui__`**: Comprehensive (field_order, groups, methods, populate, renderer)
- **Fields**: Uses widget types (`CurrencyField`, `TextareaField`), `ListRef[Comment]`
- **Methods**: `comment()`, `countdown()` (streaming), `favorite()`
- **Issues**: Forward ref update at EOF: `Product.update_forward_refs()`

#### Comment (`examples/core/models/comment.py`)
- **Base class**: ProtoModel
- **`__tablename__`**: `'comments'`
- **`__storable__`**: True
- **`__protected_fields__`**: `{'user_owner'}`
- **`__access__`**: Dict with ANYONE/AUTHENTICATED/OWNER/ROLE
- **`__ui__`**: Dict with field_order, methods
- **Fields**: `parent_id: Optional[Ref['self']]` (self-referential)
- **Issues**: Forward ref via `Comment.model_rebuild()`

#### Like (`examples/core/models/like.py`)
- **Base class**: ProtoModel
- **`__tablename__`**: `'likes'`
- **`__storable__`**: True
- **`__protected_fields__`**: `{'user'}`
- **`__access__`**: Not set
- **`__ui__`**: Not set
- **Issues**: No docstring, no access control, `created_at: str` instead of datetime

#### User (`examples/core/models/user.py`)
- **Base class**: BaseUser
- **`__tablename__`**: `'users'`
- **`__abstract__`**: False
- **`__ui__`**: Dict with 'renderer'
- **`__access__`**: Not set
- **Issues**: Also defines `Bot` model in same file (should be separate). No docstring.

---

### Example Models -- Actors (Level 3)

#### Product (`examples/actors/models/product.py`)
- **Base class**: ActorModel (instead of ProtoModel)
- **Identical to Core** except: adds `__agent__: ClassVar[dict] = True`, adds `/ask` method
- **Issues**: `__agent__ = True` (bare bool, inconsistent with dict pattern elsewhere). Return type `AsyncGenerator[TX, Any]` is experimental.

#### Comment, Like, User (`examples/actors/models/`)
- **Base class**: ActorModel versions of Core models
- **Issues**: Comment `/reply` uses `access=AUTHENTICATED | OWNER` (differs from Core version). User MRO: `BaseUser, ActorModel` order.

---

### Example Models -- Chat

#### User (`examples/chat/models/user.py`)
- **CRITICAL**: Uses OLD import path `from n3tx.core.models.actor_model import ActorModel`

#### Message (`examples/chat/models/message.py`)
- **Base class**: ActorModel
- **`__tablename__`**: `'messages'`
- **`__access__`**: Dict with AUTHENTICATED/ROLE
- **Issues**:
  - Custom `_storage_dict()` override (manual JSON serialization -- pre-v0.9 pattern)
  - Custom `_deserialize_json_fields()` validator (now handled by framework)
  - Uses OLD import paths

#### Conversation (`examples/chat/models/conversation.py`)
- **Base class**: AgentActor
- **`__agent__`**: Dict `{'self_tools': False, 'neighbors': False}`
- **Issues**: Overrides `tools` field from AgentActor. Uses OLD import paths.

---

### Example Models -- Grants

#### Grant (`examples/grants/models/grant.py`)
- **Base class**: ActorModel
- **`__tablename__`**: `'grants'`
- **`__protected_fields__`**: `{'user_owner'}`
- **`__access__`**: Dict (ANYONE/AUTHENTICATED/OWNER|ROLE)
- **`__ui__`**: Not set (minimal -- should have field hints)
- **Fields**: Uses widget types (DateField, CurrencyField, UrlField, TextareaField)

#### Source (`examples/grants/models/source.py`)
- **Issues**: No `__access__`, no `__ui__`

#### WebTools (`examples/grants/models/web_tools.py`)
- **`__storable__`**: False (non-storable utility actor)
- **Issues**: No class-level `__access__` despite method-level `access=AUTHENTICATED`

---

### Example Models -- Pygentic

#### Task (`examples/pygentic/models/task.py`)
- **`__agent__`**: True (bare bool)
- **`__protected_fields__`**: `{'user_owner'}`
- **`__access__`**: Dict (ANYONE/AUTHENTICATED/OWNER|ROLE)
- Streaming `analyze()` method

#### Memory (`examples/pygentic/models/memory.py`)
- **Issues**: `tags: list` without type parameter, `relevance: float` constrained 0-1

---

### App Models -- Veille

#### Grant (`apps/veille/models/grant.py`)
- **19 fields total**
- **`_subscribers`**: `['runs']` (non-standard lifecycle event pattern)
- **`__agent__`**: Dict `{'self_tools': True, 'neighbors': False, 'tools': ['organizations']}`
- **`__ui__`**: Comprehensive
- **Issues**: Many fields without validation. Event declarations on streaming methods. MarkdownField widget (new).

#### Run (`apps/veille/models/run.py`)
- **`__agent__`**: Dict `{'self_tools': False, 'neighbors': False, 'tools': ['web_tools', 'grants', 'sources']}`
- **Issues**: Event model definitions at module level. Helper functions at module level. `_STREAM_EVENTS` dict shared by methods.

#### Source, Organization (`apps/veille/models/`)
- Consistent patterns with minor gaps (no docstrings on Organization)

---

## Cross-Cutting Inconsistencies

### 1. `__tablename__` Convention
**Status**: UNIVERSALLY CONSISTENT -- plural snake_case everywhere.

### 2. `__access__` Coverage

| Model | Has `__access__` | Severity |
|-------|-------------------|----------|
| Product (Core/Actors) | No | HIGH |
| Like (Core/Actors) | No | HIGH |
| Bot | No | MEDIUM |
| WebTools | No (method-level only) | MEDIUM |
| Source (Grants) | No | HIGH |
| AgentTool | No | HIGH |
| AgentActor | No | HIGH |
| User (all) | No (inherits from BaseUser?) | MEDIUM |

**Impact**: Unclear what the default behavior is when `__access__` is omitted. Security risk.

### 3. `__agent__` Value Type

| Model | Value | Type |
|-------|-------|------|
| Product (Actors) | `True` | bool |
| Task (Pygentic) | `True` | bool |
| AgentActor | `True` | bool |
| Grant (Veille) | `{'self_tools': True, ...}` | dict |
| Run (Veille) | `{'self_tools': False, ...}` | dict |
| Conversation | `{'self_tools': False, ...}` | dict |

**Inconsistency**: No documented standard for bool vs dict. Dict keys (`self_tools`, `neighbors`, `tools`) not documented in CLAUDE.md.

### 4. Field Default Anti-Pattern

Multiple models use `Field(default=[])` instead of `Field(default_factory=list)`:
- Product.comments, Product.favorites
- Comment.likes
- Various ListRef fields

**Impact**: Shared mutable default across instances.

### 5. Import Path Violations

| Location | Style | Status |
|----------|-------|--------|
| All packages/ | `from n3tx_core.*` | CORRECT |
| examples/core, actors, grants, pygentic | `from n3tx_core.*` | CORRECT |
| examples/chat/ (7 files, 25 imports) | `from n3tx.core.*` | WRONG |

### 6. `__protected_fields__` Coverage

Applied to: Comment, Like, Grant, Task, Memory, Conversation.
Missing from: Run (Veille) -- should probably protect status/timestamps.

### 7. `__ui__` Coverage

Comprehensive: Product (Core), Grant (Veille), Run (Veille), Organization.
Missing entirely: Like, Bot, WebTools, Source (Grants), Message, Memory.

### 8. Docstring Coverage

Framework models: comprehensive.
Example models: inconsistent (Comment, Like, Bot, Source, Organization missing).

---

## Canonical Model Pattern (Inferred)

```python
from __future__ import annotations
from typing import ClassVar, Optional
from pydantic import Field
from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.authorize import ANYONE, AUTHENTICATED, OWNER, ROLE
from n3tx_core.models.ref import ListRef
from n3tx_core.utils.decorators import expose_route

class MyModel(ActorModel):
    """Brief docstring explaining model purpose."""

    __tablename__: ClassVar[str] = 'my_models'  # plural snake_case
    __storable__: ClassVar[bool] = True
    __protected_fields__: ClassVar[set] = {'user_owner'}
    __access__: ClassVar[dict] = {
        'read': ANYONE,
        'create': AUTHENTICATED,
        'update': OWNER | ROLE('admin'),
        'delete': ROLE('admin'),
    }
    __ui__: ClassVar[dict] = {
        'field_order': ['field1', 'field2'],
        'groups': {'Group': ['field1', 'field2']},
        'renderer': {'item': 'ntx-item', 'list': 'ntx-list'},
    }
    __agent__: ClassVar[dict] = {  # if agent-enabled
        'self_tools': True,
        'neighbors': False,
        'tools': ['other_actor'],
    }

    field1: str = Field(min_length=1, max_length=200)
    field2: Optional[int] = Field(default=None)
    related: ListRef[OtherModel] = Field(default_factory=list)
    user_owner: Optional[int] = Field(default=None)

    @expose_route('/action', methods=['POST'], access=AUTHENTICATED)
    def action(self, param: str, user: User = None) -> dict:
        """Method docstring."""
        return {'result': 'value'}
```

---

## Recommendations

### Immediate (Before Next Release)
1. Update chat example imports from `n3tx.core.*` to `n3tx_core.*`/`n3tx_agents.*`
2. Define `__access__` on all storable models (or document the default)
3. Replace all `Field(default=[])` with `Field(default_factory=list)`
4. Remove custom JSON serialization from Message model

### Documentation Updates
1. Document `__agent__` dict keys in CLAUDE.md
2. Document `__hidden_fields__` and `__owner_field__` patterns from BaseUser
3. Document widget system (CurrencyField, TextareaField, etc.)
4. Add canonical model template to docs/

### Standards Enforcement
1. All storable models must define `__tablename__` and `__access__`
2. All models must have class-level docstrings
3. No `default=[]` or `default={}` on Field()
4. Standardize `__agent__` value type (document when bool vs dict)
