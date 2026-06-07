# Domain Pitfalls

**Domain:** Agentic grant monitoring application (Veille) on N3TX framework
**Researched:** 2026-03-20
**Confidence:** HIGH (derived from framework documentation, test suites, and accumulated project memory)

---

## Critical Pitfalls

Mistakes that cause silent failures, broken features, or require rewrites.

---

### Pitfall 1: Agent Import Ordering — Silent Mixin Non-Injection

**What goes wrong:** Models with `__agent__ = True` are defined before `import n3tx_agents` executes. The `AgentMixin` is never injected. The model class has no `agentic()`, `run()`, `ctx()`, or `tools()` methods. No error is raised -- the flag fires against an empty mixin registry and is silently skipped.

**Why it happens:** `n3tx_agents.__init__` calls `register_mixin('__agent__', AgentMixin)` which populates `proto_model._mixin_registry`. If a model module is imported before this registration, `__init_subclass__` runs with an empty registry. Python's import system makes this easy to trigger with circular imports or wrong import order in `main.py`.

**Consequences:** Agent methods (`agentic()`, `run()`, `agentic_stream()`) are missing at runtime. `AttributeError` when the agent is triggered. Appears to work during import (no error), fails only at call time.

**Prevention:**
```python
# main.py -- CORRECT order
import n3tx_agents                    # Step 1: registers AgentMixin
from models import Grant, Source      # Step 2: models pick up __agent__ = True
```

```python
# main.py -- WRONG order (silent failure)
from models import Grant, Source      # __agent__ = True fires with empty registry
import n3tx_agents                    # too late
```

**Detection:** Add an assertion in your bootstrap:
```python
from n3tx_agents.mixin import AgentMixin
assert AgentMixin in Grant.__mro__, "AgentMixin not injected -- check import order"
```

**Phase relevance:** Phase 1 (project bootstrap). Must be correct from the first line of `main.py`. Also applies whenever a new model file with `__agent__ = True` is added.

**Source:** `/workspace/docs/AGENTS.md` lines 211-224, `/workspace/packages/n3tx-core/docs/schema-pipeline.md` lines 120-125

---

### Pitfall 2: `ask()` / `request()` Deadlock Inside Actor Handlers

**What goes wrong:** Calling `Actor.root().request()` (or any synchronous await on a Future) from within an actor handler blocks the actor's processing. The reply TX that would resolve the Future cannot be processed because the handler is still waiting. Deadlock.

**Why it happens:** Actors process messages sequentially. If a handler awaits a `request()` that produces a reply routed back through the same actor, the reply can never be dispatched because the actor is blocked waiting for it.

**Consequences:** Complete deadlock. The agent run hangs forever (or until timeout, which returns an error TX with code 504). No error message -- just silence.

**Prevention:**
- AgentMixin's `run()` uses `Actor.root().request()` which routes through Matrix, not through the calling actor. This is safe because Matrix is a separate routing entity.
- Never call `request()` from within a handler targeting the same actor tree path.
- For custom tool models: tool methods (`@expose_route`) should do their work directly, not call other actors via `request()`. If inter-actor communication is needed from a handler, use fire-and-forget `send()` or the `_ask_via_temp()` pattern (create a temporary Actor to make the blocking call).

**Detection:** If an agent run hangs with no error, check whether any tool handler is calling `request()` or `ask()` internally.

**Phase relevance:** Phase 2-3 (when building scraping tools and analysis agents). WebTools or custom scraping actors that need to call other actors are the most likely trigger.

**Source:** `/home/claude/.claude/projects/-workspace/memory/MEMORY.md` "Pyctor ask() deadlock" entry

---

### Pitfall 3: SQLite `:memory:` Creates Separate Databases per Connection

**What goes wrong:** Tests use `SQLiteStorage(':memory:')`. The storage pool opens a connection for `create_table()`, then a different connection for CRUD operations. Each `:memory:` connection is a completely separate database. Tables created on one connection do not exist on another. All CRUD operations fail with "no such table".

**Why it happens:** SQLite `:memory:` databases are connection-scoped. `SQLiteStorage` uses a connection pool (`queue.Queue`). Each pool member is a separate connection, each with its own empty database.

**Consequences:** Tests pass during table creation (no error) but fail on first `create()` or `list()` with `sqlite3.OperationalError: no such table`. Extremely confusing because `create_table()` succeeded.

**Prevention:** Always use file-based SQLite in tests:
```python
@pytest.fixture
def storage(tmp_path):
    return SQLiteStorage(str(tmp_path / 'test.db'))
```

Never use:
```python
# BROKEN for any test that does CRUD after create_table
storage = SQLiteStorage(':memory:')
```

**Detection:** Any test that uses `SQLiteStorage(':memory:')` and does both `create_table()` and CRUD will fail. The `memory_storage` fixture in agent tests (`/workspace/packages/n3tx-agents/src/n3tx_agents/tests/conftest.py`) exists but is only safe for operations that don't span connections.

**Phase relevance:** Phase 1 (test setup). Every test fixture that touches storage must use `tmp_path`.

**Source:** `/workspace/packages/n3tx-core/docs/storage.md` line 156, `/workspace/docs/AGENTS.md` lines 687-690

---

### Pitfall 4: Two-Tier Auth Bypass on Internal Messages

**What goes wrong:** Actor-to-actor TX messages (e.g., agent tool calls) have no `tx.meta['user']` set. The `_authorize()` method in `ActorModel.handler_crud()` returns `None` for internal messages, meaning they pass Tier 2 auth unchecked. If external input is routed into the actor system without setting `meta.user`, it bypasses all resource-level authorization.

**Why it happens:** By design, internal actor messages are trusted. But if a developer creates a TX from external input (e.g., a webhook, scheduled job, or custom endpoint) without populating `meta.user`, the message looks "internal" and skips auth.

**Consequences:** Unauthorized CRUD operations succeed. Users can create, update, or delete resources they shouldn't have access to. Security vulnerability.

**Prevention:**
- Always use `NetworkAPI` + `auth_interceptor` for external traffic. The interceptor populates `meta.user` from JWT.
- For scheduled jobs or internal triggers, explicitly set `meta.user` to a service account:
```python
TX(name='create', target='grants', data={...},
   meta={'user': {'user_id': 0, 'role': 'system'}})
```
- For Veille's scheduled runs: the scheduler actor must inject a valid user context into the TX meta.

**Detection:** Audit all TX creation points outside of `NetworkAPI`. Any `TX()` without `meta.user` bypasses Tier 2 auth.

**Phase relevance:** Phase 2 (agent tools), Phase 4 (scheduled runs). Any time a non-HTTP path creates TX messages.

**Source:** `/workspace/packages/n3tx-actors/docs/actor-model.md` line 146

---

### Pitfall 5: Schema Cache Invalidation After Extension Registration

**What goes wrong:** `ProtoModel.schema()` caches results in `_schema_cache`. If an external package registers a schema extension (via `@schema_extension`) after `schema()` has already been called on a model, the cached schema will not include the new extension. Tool discovery, frontend rendering, and agent metadata may all be incomplete.

**Why it happens:** Schema caching is aggressive for performance. Extensions registered at import time work fine because they're registered before any `schema()` call. But if modules are imported lazily or in wrong order, the cache seals before extensions arrive.

**Consequences:** Agent metadata missing from schema (`agent: {enabled: true}` absent). Tool discovery may miss methods. Frontend may render incorrectly.

**Prevention:**
- Import all packages (`n3tx_agents`, `n3tx_ui`) before any `create_app()` call.
- `create_app()` calls `schema()` during route generation. All extensions must be registered before this point.
- In tests, call `cls.invalidate_schema_cache()` after registering extensions:
```python
from n3tx_core.models.proto_schema import register_stage
register_stage('custom', custom_stage, after='methods')
MyModel.invalidate_schema_cache()  # Clear stale cache
```

**Detection:** Check schema output: `MyModel.schema()` should contain `agent`, `ui`, and `methods` keys as expected.

**Phase relevance:** Phase 1 (bootstrap), tests throughout.

**Source:** `/workspace/packages/n3tx-core/docs/schema-pipeline.md` lines 169-171

---

## Moderate Pitfalls

Mistakes that cause delays, incorrect behavior, or technical debt.

---

### Pitfall 6: Actor.register() vs BaseUser.register() Name Collision

**What goes wrong:** `Actor` has a `register()` method for child actor registration. `BaseUser` also has (or had) a `register()` method for user registration. When a User model extends both (`ActorModel` which includes `Actor`), MRO resolves to the wrong `register()`. Calling `User.register(child_actor)` might try to register a user, or vice versa.

**Why it happens:** Multiple inheritance with method name collisions. `BaseUser.register()` was renamed to `register_user()` to avoid this, but the lesson applies to any custom model that defines methods with names matching Actor API: `register`, `send`, `inbox`, `handler`, `spawn`, `has`.

**Prevention:**
- Never define methods named `register`, `send`, `inbox`, `handler`, `spawn`, or `has` on ActorModel subclasses unless you intend to override the actor API.
- For Veille's User model, use `BaseUser` patterns and verify no name collisions.

**Detection:** Check `MRO` with `MyModel.__mro__` and verify which `register` resolves.

**Phase relevance:** Phase 1 (model definition). Relevant when creating the User model.

**Source:** `/home/claude/.claude/projects/-workspace/memory/MEMORY.md` "Actor.register vs BaseUser.register" entry

---

### Pitfall 7: Pydantic `__setattr__` Blocks Mock Patching in Tests

**What goes wrong:** Standard Python mock patching (`instance.method = AsyncMock()`, `patch.object(instance, ...)`) fails on Pydantic BaseModel subclasses. `__setattr__` and `__delattr__` raise `ValueError` because Pydantic protects model fields.

**Why it happens:** All N3TX actors and models extend `PydanticBaseModel`. Pydantic V2's `__setattr__` validates assignments against the model schema. Assigning a mock function where a field or method is expected triggers validation errors.

**Consequences:** Tests that need to mock actor/model methods fail at setup time with `ValueError`, not at assertion time. Confusing error messages.

**Prevention:** Use `object.__setattr__` directly, or the `mock_method()` context manager from the test conftest:
```python
from n3tx_actors.tests.conftest import mock_method

captured = []
async def capture(tx):
    captured.append(tx)

with mock_method(actor_instance, 'inbox', capture):
    await actor_instance.inbox(tx)
```

The `mock_method()` implementation:
```python
@contextmanager
def mock_method(instance, name, replacement):
    object.__setattr__(instance, name, replacement)
    try:
        yield replacement
    finally:
        object.__delattr__(instance, name)
```

**Phase relevance:** All phases (testing). Every test that mocks model/actor methods.

**Source:** `/workspace/packages/n3tx-actors/src/n3tx_actors/tests/conftest.py` lines 12-22, `/workspace/docs/ACTORS.md` lines 717-732

---

### Pitfall 8: `agentic()` Returns JSON String, Not Dict

**What goes wrong:** `AgentActor.agentic()` is decorated with `@expose_route` (HTTP endpoint). It returns a JSON **string**, not a Python dict. Code that calls `agentic()` and tries to access `result['answer']` gets a `TypeError: string indices must be integers`.

**Why it happens:** `@expose_route` methods return values that are serialized for HTTP responses. `AgentActor.agentic()` calls `json.dumps()` on the result dict before returning. This is correct for HTTP but confusing when calling from code.

**Consequences:** `TypeError` or `KeyError` when accessing result fields. Silent data corruption if the string is stored instead of parsed.

**Prevention:** Always parse the result:
```python
import json
result_str = await agent.agentic(task="Find grants")
result = json.loads(result_str)
print(result['answer'])
```

Or call `run()` directly for internal use (returns a dict):

```python
result = await agent.call(task="Find grants", prompt=agent.prompt,
                          tools=agent_tools, llm=agent.llm)
print(result['answer'])  # Works directly
```

**Phase relevance:** Phase 2-3 (when building agent orchestration). Any code that triggers agents programmatically.

**Source:** `/workspace/packages/n3tx-agents/docs/agent-actor.md` lines 150-154

---

### Pitfall 9: Tool Address Must Match Registered Actor Address

**What goes wrong:** Agent's `tools` list contains addresses like `'web_tools'` but no actor is registered at that address in the Matrix. `discover_tools()` logs a warning and skips the address. The agent runs without those tools, producing incomplete or incorrect results.

**Why it happens:** Tool addresses must exactly match `__tablename__` values of registered ActorModels. Typos, case mismatches, or forgetting to register a model all cause silent tool omission.

**Consequences:** Agent runs without expected tools. LLM tries to accomplish the task without scraping or CRUD capabilities. Results are wrong or the agent reports inability to complete the task. No error raised -- just a log warning.

**Prevention:**
- Verify tool addresses match `__tablename__` exactly:
```python
class WebTools(ActorModel):
    __tablename__ = 'web_tools'  # Agent tools list must use 'web_tools'
```
- All tool-providing models must be passed to `create_app(models=[...])` so they're registered with Matrix.
- Add a startup check:
```python
from n3tx_actors.actor import Actor
root = Actor.root()
for addr in ['grants', 'sources', 'web_tools']:
    assert root.has(addr), f"Tool actor '{addr}' not registered in Matrix"
```

**Detection:** Check logs for "Actor not found" or "Skipping tool" warnings during agent runs.

**Phase relevance:** Phase 2 (agent tool wiring). Every time a new tool model is added.

**Source:** `/workspace/packages/n3tx-agents/docs/tool-discovery.md` lines 57-58

---

### Pitfall 10: `list()` Return Type Changes With Pagination

**What goes wrong:** `Model.list()` returns a `list[Model]` without pagination params, but returns a `dict` with `data` and `meta` keys when `limit` is provided. Code that always expects a list (or always expects a dict) breaks when the other case occurs.

**Why it happens:** The storage layer uses return type as a signal for pagination. Routes always pass `limit`/`offset` from query params. Internal code may or may not pass them.

**Consequences:** `TypeError` when iterating a dict, or `AttributeError` when accessing `.data` on a list.

**Prevention:** Always be explicit about pagination:
```python
# If you want a list, don't pass limit:
grants = Grant.list()  # Returns list[Grant]

# If you want paginated, always unpack:
result = Grant.list(limit=20, offset=0)
grants = result['data']  # list[Grant]
meta = result['meta']    # {total, limit, offset, has_more}
```

For agent tools, CRUD `list` tool specs always pass pagination parameters, so tool results are always the paginated dict format.

**Phase relevance:** Phase 1-2 (model CRUD operations, agent tool integration).

**Source:** `/workspace/packages/n3tx-core/docs/storage.md` lines 155-156

---

### Pitfall 11: Streaming First-Token Drop with OpenAI/Ollama Models

**What goes wrong:** When streaming with OpenAI or Ollama-compatible LLM providers, the first text token arrives as a `PartStartEvent` with `TextPart(content='first_token')`. If `run_stream()` does not handle `PartStartEvent` for `TextPart`, the first token is silently dropped from the stream.

**Why it happens:** Different LLM providers emit stream events differently. `TestModel` (used in tests) sends an empty `PartStartEvent` then all words via `PartDeltaEvent`. Real OpenAI/Ollama models send the first token inside `PartStartEvent`. The framework must handle both patterns.

**Consequences:** Streamed text is missing its first word/token. Done event's `answer` field contains the complete text, but the progressive stream is incomplete. Frontend displays text missing the first token.

**Prevention:** This was a known bug that was fixed in wave 0.10 (commit `332bd96`). Ensure you're on the latest framework version. If customizing streaming behavior, handle both `PartStartEvent` with non-empty `TextPart` content and `PartDeltaEvent`.

**Detection:** Write a test using `FakeOpenAIModel` (see `/workspace/packages/n3tx-agents/src/n3tx_agents/tests/test_run_stream_first_token.py`) that verifies first-token delivery.

**Phase relevance:** Phase 3 (streaming agent output to UI).

**Source:** `/workspace/packages/n3tx-agents/src/n3tx_agents/tests/test_run_stream_first_token.py`

---

### Pitfall 12: `auto_start` Race Condition in Actor Subclasses

**What goes wrong:** If a subclass `__init__` sets `PrivateAttr` values AFTER calling `super().__init__(auto_start=True)`, the `on_start()` method may run before the attrs are initialized. Accessing uninitialized attrs in `on_start()` raises `AttributeError`.

**Why it happens:** `auto_start=True` triggers `on_start()` during `super().__init__()`. At that point, the subclass's `__init__` hasn't finished setting up its own private attributes.

**Prevention:**
```python
class MyActor(Actor, auto_register=False):
    _custom_state: dict = PrivateAttr(default_factory=dict)

    def __init__(self, **kwargs):
        super().__init__(auto_start=False, **kwargs)  # Don't auto-start
        self._custom_state = {'ready': True}           # Set state
        self.start()                                    # Start manually
```

**Phase relevance:** Phase 2 (if building custom actor subclasses for scraping workers or schedulers).

**Source:** `/home/claude/.claude/projects/-workspace/memory/MEMORY.md` "Pyctor auto_start race" entry

---

### Pitfall 13: Interceptors Are Per-Actor, Not Global

**What goes wrong:** Developer registers `auth_interceptor` on `NetworkAPI` and assumes all actors check auth. But interceptors only run on the specific actor (or class) where they're registered. A TX that bypasses `NetworkAPI` (e.g., from a scheduled job or internal code) does not pass through the interceptor.

**Why it happens:** Interceptors are stored per-actor in `_interceptors` (instance) or `__interceptors__` (class). There is no global interceptor mechanism. This is by design but surprising.

**Consequences:** Auth bypass on non-HTTP paths. Security holes for scheduled jobs, WebSocket messages (if interceptor not registered on WS adapter), or direct Matrix injection.

**Prevention:**
- Register interceptors on every adapter that receives external input:
```python
api.use(auth_interceptor, on='request')
ws.use(auth_interceptor, on='request')  # Don't forget WebSocket
```
- For scheduled jobs, inject user context in the TX meta (see Pitfall 4).

**Phase relevance:** Phase 1 (app bootstrap), Phase 4 (scheduled runs).

**Source:** `/workspace/packages/n3tx-actors/docs/interceptors.md` lines 124-125

---

### Pitfall 14: Actor State Leaks Between Tests

**What goes wrong:** Actor class-level state (`__matrix__`, `__children__`, `__interceptors__`) persists between tests. A model registered in one test appears in another test's Matrix. Interceptors registered in one test fire in another.

**Why it happens:** `Actor.__children__` and `Matrix.__children__` are class-level dicts (ClassVars). They survive across test functions unless explicitly cleaned up.

**Consequences:** Flaky tests. Tests pass in isolation but fail when run together. Non-deterministic behavior based on test execution order.

**Prevention:** Use the `reset_actor_state` autouse fixture from the framework test conftest:
```python
@pytest.fixture(autouse=True)
def reset_actor_state():
    saved_matrix = Actor.__matrix__
    saved_children = Actor.__children__.copy()
    saved_matrix_children = Matrix.__children__.copy()
    saved_models = dict(registered_models)

    Actor.__matrix__ = None
    Actor.__children__ = {}
    Matrix.__children__ = {}
    registered_models.clear()

    yield

    Actor.__matrix__ = saved_matrix
    Actor.__children__ = saved_children
    Matrix.__children__ = saved_matrix_children
    registered_models.clear()
    registered_models.update(saved_models)
```

Also reset registered models:
```python
from n3tx_core.utils.registrar import registered_models
```

**Phase relevance:** All phases (testing).

**Source:** `/workspace/packages/n3tx-agents/src/n3tx_agents/tests/conftest.py`, `/workspace/packages/n3tx-actors/src/n3tx_actors/tests/conftest.py`

---

## Minor Pitfalls

Mistakes that cause annoyance or confusion but are easily fixable.

---

### Pitfall 15: LLM Config Cascade — "No LLM" ValueError

**What goes wrong:** `run()` raises `ValueError("No LLM configured")` because no LLM resolves from the 3-tier cascade: kwargs > model `__agent__` dict > instance `.llm` attr > `config.AGENT_DEFAULTS['llm']`.

**Why it happens:** In tests, no real LLM is configured. In development, `AGENT_DEFAULTS` may not be set. The cascade silently falls through all tiers and finds nothing.

**Prevention:** Always provide an LLM explicitly:
- In tests: `llm=TestModel(call_tools=[])`
- In `__agent__` config: `__agent__ = {'llm': 'anthropic:claude-sonnet-4-5-20250929'}`
- In `config.py`: `AGENT_DEFAULTS = {'llm': 'anthropic:claude-sonnet-4-5-20250929'}`
- For AgentActor instances: the `llm` field has a default of `'ollama:llama3.1'`

**Phase relevance:** Phase 1 (config setup), all phases (testing).

**Source:** `/workspace/packages/n3tx-agents/docs/mixin.md` lines 173-174

---

### Pitfall 16: `tools=[]` vs Omitting `tools` in `agentic()`

**What goes wrong:** Developer passes `tools=[]` to `agentic()` expecting it to auto-discover tools. But `tools=[]` explicitly means "no tools". The agent runs without any tool access.

**Why it happens:** `agentic()` uses `'tools' in kwargs` (presence check), not truthiness. Passing `tools=[]` means "I explicitly want zero tools". Omitting `tools` entirely means "auto-discover from model config".

**Prevention:**
```python
# Auto-discover tools (from __agent__ config + self + neighbors):
result = await model.agentic(task="Find grants")

# Explicitly no tools:
result = await model.agentic(task="Summarize this", tools=[])

# Explicitly these tools:
result = await model.agentic(task="Find grants", tools=['grants', 'web_tools'])
```

**Phase relevance:** Phase 2-3 (agent configuration).

**Source:** `/workspace/packages/n3tx-agents/docs/mixin.md` lines 171-172

---

### Pitfall 17: CSS Token Split — Styles Not Loading

**What goes wrong:** CSS custom property changes have no visible effect. Variables defined in `_tokens.css` (spacing, fonts) are not available because only `styles.css` is loaded.

**Why it happens:** The CSS is split across multiple files. If the HTML only loads one stylesheet, variables from the other are undefined. `getComputedStyle()` returns empty strings for unresolved variables.

**Prevention:** When debugging CSS issues:
1. Use `getComputedStyle(element).getPropertyValue('--var-name')` to check if variables resolve.
2. Verify all CSS files are loaded in the HTML.
3. Check that `_tokens.css` is imported by `styles.css` or loaded separately.

**Phase relevance:** Phase 3 (frontend/UI work).

**Source:** `/home/claude/.claude/projects/-workspace/memory/MEMORY.md` "CSS token split bug" entry

---

### Pitfall 18: UPPERCASE Handler Convention

**What goes wrong:** Developer defines a stream handler in camelCase (`textHandler`) or lowercase (`text`). The `StreamActor` mixin dispatches to UPPERCASE methods (`TEXT`, `TOOL_CALL`, `DONE`). The handler is never called.

**Why it happens:** TX inbox handlers follow the UPPERCASE convention from the backend actor pattern. `StreamActor.js` converts event names to UPPERCASE before dispatching (`this[NAME.toUpperCase()](data, meta)`).

**Prevention:** Always use UPPERCASE for TX handlers in frontend components:
```javascript
class MyComponent extends StreamActor(HTMLElement) {
    TEXT(data, meta)        { /* data.text */ }
    TOOL_CALL(data, meta)   { /* data.tool, data.args */ }
    TOOL_RESULT(data, meta) { /* data.tool, data.result */ }
    DONE(data, meta)        { /* data.answer, data.usage */ }
    STREAM_END(data)        { /* cleanup */ }
    STREAM_ERROR(err)       { /* error handling */ }
}
```

**Phase relevance:** Phase 3 (streaming UI components).

**Source:** `/workspace/docs/AGENTS.md` lines 524-536, 561

---

### Pitfall 19: `_coerce_value()` Converts Non-Native Types to String

**What goes wrong:** A model field with a Pydantic type (e.g., `AnyHttpUrl`, `EmailStr`) is stored as its string representation instead of the actual URL/email string. Reading it back produces a string of the Pydantic type repr, not the value.

**Why it happens:** `_coerce_value()` in SQLite storage applies `str()` to any value that isn't `int`, `float`, `str`, `bytes`, `bool`, `None`, `datetime`, `dict`, or `list`. Pydantic types like `AnyHttpUrl` are objects, not plain strings.

**Prevention:** For URL and email fields, use `str` type with Pydantic validators instead of Pydantic URL/Email types:
```python
# GOOD: plain str, validated by Pydantic
url: str = Field(json_schema_extra={'ui': {'widget': 'url'}})

# RISKY: Pydantic type, may serialize oddly in SQLite
url: AnyHttpUrl = Field(...)
```

**Phase relevance:** Phase 1 (model definition). Source and Grant models will have URL fields.

**Source:** `/workspace/packages/n3tx-core/docs/storage.md` line 157

---

### Pitfall 20: `build()` Clears Global Registries

**What goes wrong:** During development with `uvicorn --reload`, the app re-imports and calls `build()` again. `build()` calls `registered_models.clear()` at the start. If model registration happens outside of `build()` (e.g., in module-level code that doesn't re-run), models are lost.

**Why it happens:** `build()` clears registries to support hot-reload without accumulating duplicate registrations. But this means all model registrations must happen inside the `create_app()` / `build()` call path, not in module-level side effects.

**Prevention:** Pass all models to `create_app(models=[...])`. Don't register models manually in module-level code that might not re-execute on reload.

**Phase relevance:** Phase 1 (development workflow).

**Source:** `/workspace/packages/n3tx-core/docs/app-bootstrap.md` line 156

---

### Pitfall 21: Join Model Registration Order

**What goes wrong:** `generate_join_model(Parent, Child)` creates a join model class. If this class is not registered with `register_model()` and passed through `create_app()`, the ListRef relationship has no backing table. FK hydration returns empty lists.

**Why it happens:** Join models are auto-generated but must still be explicitly registered for table creation and storage binding.

**Prevention:** Always include join models in `create_app()`:
```python
app = create_app(
    models=[Grant, Source, AgentActor, AgentTool, ...],
    join_models=[(AgentActor, AgentTool)],  # Generates + registers join model
    ...
)
```

Or register manually:
```python
join_cls = generate_join_model(AgentActor, AgentTool)
register_model(join_cls, storage=storage)
```

**Phase relevance:** Phase 1 (model relationships). Any model with `ListRef[T]` fields.

**Source:** `/workspace/packages/n3tx-agents/docs/agent-actor.md` lines 138-146, `/workspace/examples/grants/main.py` line 37

---

### Pitfall 22: `pydantic-ai` Import Locations

**What goes wrong:** Importing `UsageLimits` from the wrong module (`from pydantic_ai.settings import UsageLimits` instead of `from pydantic_ai import UsageLimits`). Similarly, `TestModel` must come from `pydantic_ai.models.test`, not from a top-level import.

**Prevention:**
```python
# CORRECT
from pydantic_ai import UsageLimits
from pydantic_ai.models.test import TestModel

# WRONG
from pydantic_ai.settings import UsageLimits  # Does not exist
```

**Phase relevance:** All phases (testing and agent configuration).

**Source:** `/home/claude/.claude/projects/-workspace/memory/MEMORY.md` "pydantic-ai UsageLimits" and "pydantic-ai TestModel" entries

---

### Pitfall 23: Table Names Cannot Contain Hyphens

**What goes wrong:** `__tablename__ = 'web-tools'` causes `_validate_identifier()` to reject the name. Only `^[a-zA-Z_][a-zA-Z0-9_]*$` is allowed.

**Prevention:** Use underscores in table names:
```python
class WebTools(ActorModel):
    __tablename__ = 'web_tools'  # OK
    # __tablename__ = 'web-tools'  # REJECTED
```

**Phase relevance:** Phase 1 (model definition).

**Source:** `/workspace/packages/n3tx-core/docs/storage.md` line 160

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Project bootstrap | Import ordering (Pitfall 1) | `import n3tx_agents` before model imports in `main.py` |
| Project bootstrap | Schema cache (Pitfall 5) | Import all packages before `create_app()` |
| Project bootstrap | Registry clear on reload (Pitfall 20) | Pass all models via `create_app(models=[...])` |
| Model definition | URL field types (Pitfall 19) | Use `str` with validators, not Pydantic URL types |
| Model definition | Table name validation (Pitfall 23) | Underscores only in `__tablename__` |
| Model definition | Join model registration (Pitfall 21) | Include in `join_models=` param |
| Model definition | Actor method name collisions (Pitfall 6) | Avoid `register`, `send`, `inbox`, `handler` as method names |
| Agent tool wiring | Tool address mismatch (Pitfall 9) | Verify addresses match `__tablename__` values |
| Agent tool wiring | `tools=[]` semantics (Pitfall 16) | Omit `tools` for auto-discovery, pass `[]` only for "no tools" |
| Agent tool wiring | LLM config cascade (Pitfall 15) | Set LLM at config, model, or call level |
| Agent CRUD in code | `agentic()` return type (Pitfall 8) | Parse JSON string with `json.loads()` |
| Scraping tool handlers | ask() deadlock (Pitfall 2) | Never call `request()` inside a handler |
| Auth + scheduled jobs | Internal msg auth bypass (Pitfall 4) | Always set `meta.user` on externally-sourced TX |
| Auth + scheduled jobs | Interceptor scope (Pitfall 13) | Register auth on every adapter |
| Streaming UI | UPPERCASE handlers (Pitfall 18) | Use `TEXT()`, `DONE()`, `STREAM_END()` naming |
| Streaming UI | First-token drop (Pitfall 11) | Verify with real LLM providers, not just TestModel |
| Frontend CSS | Token loading (Pitfall 17) | Check `getComputedStyle()` for variable resolution |
| Testing | `:memory:` SQLite (Pitfall 3) | Use `tmp_path / 'test.db'` in fixtures |
| Testing | Actor state leaks (Pitfall 14) | Use `reset_actor_state` autouse fixture |
| Testing | Pydantic mock patching (Pitfall 7) | Use `object.__setattr__()` or `mock_method()` |
| Testing | pydantic-ai imports (Pitfall 22) | `from pydantic_ai import UsageLimits`, `from pydantic_ai.models.test import TestModel` |

---

## Sources

All findings sourced from authoritative framework documentation and project memory:

- `/workspace/docs/AGENTS.md` -- Agent system documentation (HIGH confidence)
- `/workspace/docs/ACTORS.md` -- Actor system documentation (HIGH confidence)
- `/workspace/packages/n3tx-core/docs/storage.md` -- Storage layer internals (HIGH confidence)
- `/workspace/packages/n3tx-core/docs/schema-pipeline.md` -- Schema pipeline mechanics (HIGH confidence)
- `/workspace/packages/n3tx-core/docs/app-bootstrap.md` -- App initialization (HIGH confidence)
- `/workspace/packages/n3tx-core/docs/authorization.md` -- Auth system (HIGH confidence)
- `/workspace/packages/n3tx-actors/docs/actor-messaging.md` -- Actor messaging (HIGH confidence)
- `/workspace/packages/n3tx-actors/docs/actor-model.md` -- ActorModel bridge (HIGH confidence)
- `/workspace/packages/n3tx-actors/docs/interceptors.md` -- Interceptor pattern (HIGH confidence)
- `/workspace/packages/n3tx-actors/docs/network-adapters.md` -- Network adapters (HIGH confidence)
- `/workspace/packages/n3tx-agents/docs/mixin.md` -- AgentMixin methods (HIGH confidence)
- `/workspace/packages/n3tx-agents/docs/agent-actor.md` -- AgentActor (HIGH confidence)
- `/workspace/packages/n3tx-agents/docs/tool-discovery.md` -- Tool discovery pipeline (HIGH confidence)
- `/home/claude/.claude/projects/-workspace/memory/MEMORY.md` -- Accumulated project lessons (HIGH confidence)
- `/workspace/packages/n3tx-agents/src/n3tx_agents/tests/conftest.py` -- Test fixtures (HIGH confidence)
- `/workspace/packages/n3tx-actors/src/n3tx_actors/tests/conftest.py` -- Test fixtures (HIGH confidence)
- `/workspace/packages/n3tx-agents/src/n3tx_agents/tests/test_run_stream_first_token.py` -- Streaming bug test (HIGH confidence)
- `/workspace/examples/grants/main.py` -- Reference app patterns (HIGH confidence)
