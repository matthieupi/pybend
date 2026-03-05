# AgentMixin v2: Self-Aware Models

**Status:** Plan
**Date:** 2026-03-05
**Context:** Conversation exploring whether to keep the AgentMixin/AgentActor split or collapse them. Conclusion: the split becomes genuinely valuable if the mixin auto-derives tools and context from the model it's mixed into.

---

## The Insight

Today `__storable__ = True` gives a model zero-config persistence. But `__agent__ = True` gives almost nothing — just an `agent_run()` method that still requires the developer to provide prompt, tools, and task manually.

The model's `schema()` already contains everything the mixin needs: field names, types, constraints, descriptions, methods, access rules, relationships, widget hints. The mixin just doesn't use any of it.

**Goal:** Make `__agent__ = True` as powerful as `__storable__ = True`. One flag, zero config, the model can reason about itself.

---

## What Changes

### AgentMixin gains three auto-derivation methods

```python
class AgentMixin:

    def _agent_self_tools(self) -> list[str]:
        """Actor addresses for self + neighbor models from ListRef fields."""
        addrs = [cls.__tablename__]
        for field_name, model_cls in get_list_fields(cls):
            if hasattr(model_cls, '__tablename__'):
                addrs.append(model_cls.__tablename__)
        return addrs

    def _agent_context(self) -> str:
        """Auto-generate system prompt context from schema."""
        schema = cls.schema()
        # Builds structured context from:
        # - Model name + tablename
        # - Field descriptions, types, constraints (from properties)
        # - Widget hints (currency → decimal format, textarea → multiline, etc.)
        # - Relationships (ListRef fields → related model names)
        # - Access rules (who can read/create/update/delete)
        # - Protected fields (auto-injected, warn LLM not to set)
        # - Available methods (from schema['methods'])

    def _agent_instance_context(self) -> str:
        """Current instance data as LLM context. Empty string if called on class."""
        if isinstance(self, type):
            return ""
        data = self.model_dump(exclude={'id'})
        return f"Current instance (id={self.id}):\n{json.dumps(data, indent=2, default=str)}"
```

### agent_run() signature changes — prompt and tools become optional

```python
async def agent_run(self, task: str, prompt: str = None,
                    tools: list = None, user: dict = None, **kwargs) -> dict:
    # prompt defaults to _agent_context() + _agent_instance_context()
    # tools defaults to _agent_self_tools()
    # Both still fully overridable
```

### AgentActor stays the same

AgentActor's `run()` already passes explicit `prompt=self.prompt` and `tools=self._resolve_tool_addrs()`. These override the mixin's auto-derived defaults. No changes needed to AgentActor.

---

## The Split Justified

| | AgentMixin ("self-aware model") | AgentActor ("orchestrator agent") |
|---|---|---|
| **Tools** | Auto: own CRUD + methods + neighbor models | Configured: any models, stored in DB |
| **Prompt** | Auto: generated from schema metadata | Stored in DB, fully custom |
| **Config** | Derived from model definition | Data — user-editable at runtime |
| **Use case** | "Product, analyze yourself" | "Agent, coordinate across Products, Sources, Grants" |
| **Trigger** | `self.agent_run(task=...)` from within a method | `POST /agents/{id}/run` from API |
| **Persistence** | No agent config to store — it IS the model | Agent config lives in DB rows |

---

## Auto-Generated Context Example

Given:
```python
class Product(ActorModel):
    __tablename__ = 'products'
    __storable__ = True
    __agent__ = True
    __access__ = {'read': ANYONE, 'create': AUTHENTICATED, 'update': OWNER, 'delete': ROLE('admin')}

    name: str = Field(min_length=1, max_length=200, description="Product name")
    price: float = Field(gt=0, json_schema_extra={'ui': {'widget': 'currency'}})
    description: str = Field(default='', json_schema_extra={'ui': {'widget': 'textarea'}})
    comments: ListRef[Comment] = Field(default=[])

    @expose_route('/comment', methods=['POST'])
    def comment(self, comment: Comment) -> str: ...
```

The mixin auto-generates:
```
You operate on Product entities (table: products).

Fields:
  - name (string, required, 1-200 chars): Product name
  - price (number, required, > 0, currency format)
  - description (string, optional, textarea)

Relationships:
  - comments → Comment (list)

Access rules:
  - read: anyone
  - create: authenticated users
  - update: resource owner only
  - delete: admin role only

Available methods:
  - comment(comment: Comment) → string [POST, instance method]
```

And when called on an instance:
```
Current instance (id=42):
  name: "Widget Pro"
  price: 29.99
  description: "A professional widget"
```

Auto-discovered tools: `['products', 'comments']`

---

## Usage: Before and After

### Before (v1 — everything manual)
```python
class Product(ActorModel):
    __agent__ = True
    # ...

    @expose_route('/analyze', methods=['POST'])
    async def analyze(self, query: str) -> str:
        result = await self.agent_run(
            prompt="You are a product manager. You operate on Product entities with fields: name (str), price (float), description (str). You can also manage comments.",
            tools=['products', 'comments'],
            task=query,
        )
        return result['answer']
```

### After (v2 — auto-derived)
```python
class Product(ActorModel):
    __agent__ = True
    # ...

    @expose_route('/analyze', methods=['POST'])
    async def analyze(self, query: str) -> str:
        result = await self.agent_run(task=query)
        return result['answer']
```

Same behavior. Zero manual config. Prompt and tools derived from schema.

### Override when needed
```python
result = await self.agent_run(
    task=query,
    prompt="Custom override for this specific use case...",  # replaces auto-generated
    tools=['products', 'comments', 'suppliers'],  # replaces auto-discovered
)
```

---

## Implementation Plan

### Step 1: Add `_agent_context()` to AgentMixin
- Reads `cls.schema()` to extract field info, constraints, descriptions
- Reads `cls.__access__` for access rules (via `access_schema()`)
- Reads `schema['methods']` for available methods
- Reads `cls.__protected_fields__` to warn LLM
- Formats as structured text block
- ~40 lines

### Step 2: Add `_agent_self_tools()` to AgentMixin
- Returns `[cls.__tablename__]` + tablenames from `get_list_fields(cls)`
- Uses existing `n3tx.core.utils.introspection.get_list_fields()`
- ~10 lines

### Step 3: Add `_agent_instance_context()` to AgentMixin
- Returns `self.model_dump()` formatted as context when called on instance
- Returns empty string when called on class
- ~10 lines

### Step 4: Update `agent_run()` signature
- `prompt` and `tools` become optional (default `None`)
- When `None`, derive from `_agent_context()` and `_agent_self_tools()`
- When provided, use as-is (full override)
- Append `_agent_instance_context()` to prompt if non-empty
- ~10 lines of changes to existing method

### Step 5: Tests
- Test `_agent_context()` produces correct output for a model with fields, access, methods
- Test `_agent_self_tools()` discovers self + neighbor models
- Test `_agent_instance_context()` includes instance data, empty on class
- Test `agent_run(task=...)` works with no explicit prompt/tools
- Test explicit prompt/tools still override auto-derived values
- Test AgentActor.run() still works unchanged (passes explicit values)

### Step 6: Update CLAUDE.md
- Document the enhanced mixin pattern
- Update the AgentMixin vs AgentActor distinction
- Add usage examples

---

## Estimated Effort

~70 lines of new code in mixin.py, ~100 lines of tests. No changes to AgentActor, tools.py, deps.py, or schema_ext.py.

---

## Open Questions

1. **Prompt composition vs replacement:** When the developer provides a custom `prompt`, should it fully replace the auto-generated context, or should it be appended? Current plan: full replacement. The developer can call `self._agent_context()` explicitly to compose.

2. **Neighbor depth:** Should auto-discovery follow ListRef one level deep (Product → Comment) or recursively (Product → Comment → User)? Current plan: one level only. Recursive could bloat the tool list.

3. **Tool deduplication:** If a developer passes `tools=['comments']` and auto-discovery also finds `comments`, should we deduplicate? Yes — simple set union.

4. **Context format:** Plain text (current plan) vs structured (JSON/YAML) vs XML tags? Plain text is most token-efficient and LLMs handle it well. Could make configurable later via `__agent_context_format__` class var.
