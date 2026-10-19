# Phase 2: Scraping and Grant Extraction - Research

**Researched:** 2026-03-20
**Domain:** N3TX AgentMixin, streaming routes, web scraping, Run model, grant deduplication
**Confidence:** HIGH (all findings from actual source code)

## Summary

Phase 2 adds a Run model with a streaming `execute` method that triggers an agentic scraping loop. The agent uses WebTools (an `ActorModel` with `@expose_route` scraping methods) as tools to fetch and parse grant pages. Scraped grants are deduped against existing records before being created. The user sees a live text log and grant cards streaming in real time.

The N3TX AgentMixin pattern is clean: a `Run` model with `__agent__ = True` gets `agentic_stream()` for free, which streams LLM events as TX-aligned chunks (`text`, `tool_call`, `tool_result`, `thinking`, `done`). The streaming route is declared with `@expose_route(stream=True, events={...})` and the frontend uses the `StreamActor` mixin to dispatch events to UPPERCASE handler methods.

Web scraping uses `httpx` (already installed) with stdlib `html.parser` for text extraction. Playwright (also installed) handles JS-heavy pages as a fallback via a `WebTools` actor model.

**Primary recommendation:** Create `WebTools` as a non-storable `ActorModel` with `scrape()` and `extract_text()` methods. Add `Run` as a storable `ActorModel` with `__agent__ = True` and an `@expose_route('/execute', stream=True)` method that calls `agentic_stream()`. Add `WebTools` to the `Run` model's `__agent__` config `tools` list. Register both in `main.py`. Build a custom `<ntx-run-panel>` web component using the `StreamActor` mixin pattern from `ntx-agent-live.js`.

## Standard Stack

### Core (verified from source)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `httpx` | 0.28.1 | Async HTTP fetching | Already installed, used in existing grants example `web_tools.py` |
| `playwright` | 1.58.0 | Headless browser fallback | Already installed AND browsers verified working |
| `html.parser` | stdlib | HTML text extraction | Already available, no extra install needed |
| `n3tx_agents.mixin.AgentMixin` | 0.10 | LLM agent loop + streaming | Injected via `__agent__ = True` |
| `pydantic_ai` | bundled | LLM abstraction layer | Used internally by AgentMixin |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `bs4` (BeautifulSoup) | NOT installed | Better HTML parsing | Would need `pip install beautifulsoup4` — use stdlib parser instead |
| `lxml` | NOT installed | Fast HTML parsing | Not available, do not use |

### Key Insight on Scraping Libraries
`bs4` is NOT installed. The grants example `web_tools.py` already exists and uses only `httpx` + `bs4.BeautifulSoup` for extraction. Veille must either: (a) install `beautifulsoup4` via pip, or (b) use stdlib `html.parser` for extraction. Given that the grants example already shows the `bs4` pattern and it is a common dependency, installing it is the right call. Alternatively, use stdlib exclusively.

**Verified installation status:**
- `httpx` 0.28.1: INSTALLED
- `playwright` 1.58.0: INSTALLED, browsers working (tested with `async_playwright().chromium.launch()`)
- `beautifulsoup4`: NOT INSTALLED (needs `pip install beautifulsoup4`)

**Installation:**
```bash
pip install beautifulsoup4
```

## Architecture Patterns

### Recommended Project Structure (additions to Phase 1)
```
apps/veille/
├── models/
│   ├── __init__.py          # add Run, WebTools exports
│   ├── run.py               # NEW: Run model with __agent__ = True
│   └── web_tools.py         # NEW: WebTools actor (scrape, extract_text, check_duplicate)
├── static/
│   ├── components/          # NEW directory
│   │   └── ntx-run-panel.js # NEW: custom streaming component for run UI
│   └── index.html           # MODIFIED: add Run sidebar entry, import ntx-run-panel.js
└── main.py                  # MODIFIED: add Run, WebTools to create_app models
```

### Pattern 1: Non-Storable Tool Actor (WebTools)
**What:** An `ActorModel` with `__storable__ = False` that provides tools for the agent. It is registered in `main.py` and appears in the Matrix as an addressable actor.
**When to use:** Any set of utility methods that aren't CRUD-based data models.
**Example:**
```python
# Source: examples/grants/models/web_tools.py (verified)
from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.utils.decorators import expose_route
from n3tx_core.authorize import AUTHENTICATED

class WebTools(ActorModel):
    __tablename__ = 'web_tools'
    __storable__ = False   # no DB table, no CRUD routes

    @expose_route('/scrape', methods=['POST'], access=AUTHENTICATED)
    async def scrape(self, url: str) -> dict:
        """Fetch a URL and return HTML content."""
        import httpx
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            resp = await client.get(url)
        return {'url': url, 'status': resp.status_code, 'html': resp.text[:50000]}

    @expose_route('/extract_text', methods=['POST'], access=AUTHENTICATED)
    def extract_text(self, html: str) -> dict:
        """Extract readable text from HTML, stripping scripts/styles."""
        from html.parser import HTMLParser
        # ... stdlib extraction
        return {'text': cleaned_text}
```
This mirrors the exact pattern in `examples/grants/models/web_tools.py`.

### Pattern 2: Agent Model with Streaming Method (Run)
**What:** A storable `ActorModel` with `__agent__ = True` that gives the Run record its own LLM capabilities via AgentMixin injection.
**When to use:** When a model instance IS the unit of agent execution (each run is a DB record).
**Example:**
```python
# Source: packages/n3tx-agents/src/n3tx_agents/mixin.py (verified pattern)
from n3tx_actors.models.actor_model import ActorModel
from n3tx_agents.actor import TextChunk, ToolCallEvent, ToolResultEvent, ThinkingChunk, DoneChunk
from n3tx_core.utils.decorators import expose_route
from n3tx_core.authorize import AUTHENTICATED

class Run(ActorModel):
    __tablename__ = 'runs'
    __storable__ = True
    __agent__ = {
        'llm': None,         # falls through to AGENT_DEFAULTS
        'self_tools': False, # Run doesn't need CRUD tools for itself
        'neighbors': False,  # no ListRef neighbors
        'tools': ['web_tools', 'grants', 'sources'],  # explicit tool list
    }

    # Fields...
    status: str = Field(default='pending')
    type: str = Field(default='full')
    # ...

    @expose_route('/execute', methods=['POST'], stream=True, access=AUTHENTICATED,
                  events={
                      'text': TextChunk, 'tool_call': ToolCallEvent,
                      'tool_result': ToolResultEvent, 'thinking': ThinkingChunk,
                      'done': DoneChunk,
                  })
    async def execute(self, adhoc_url: str = ''):
        """Run the scraping agent."""
        # update status to 'running'...
        async for chunk in self.agentic_stream(task=self._build_task(adhoc_url)):
            yield chunk
```

### Pattern 3: AgentMixin Config (`__agent__` dict)
**What:** Configures which tools the agent discovers, where the LLM comes from.
**When to use:** When the default auto-discovery is wrong (e.g., you need explicit tool list).

The `tools()` fullmethod auto-discovers from:
1. `self_tools=True` → own `__tablename__` (grants, sources tools)
2. `neighbors=True` → ListRef relationships
3. `tools=[...]` → explicit extra addresses

For Run, setting `self_tools=False` and `neighbors=False` and explicit `tools=['web_tools', 'grants', 'sources']` gives the agent exactly the tools it needs: scraping + CRUD for grants + read sources.

### Pattern 4: Streaming SSE Wire Format (Level 3)
**What:** How the streaming route reaches the frontend.

From `network_api.py` `_sse_from_stream()`:
- The agent yields `{'name': 'text', 'data': {'text': '...'}, 'meta': {'stream': True, 'seq': N}}`
- The actor model wraps this in a TX envelope: `TX(name='STREAM', data=chunk, meta={..., 'stream': True})`
- NetworkAPI serializes the full TX as an SSE event: `event: chunk\ndata: {json TX dict}\n\n`
- The final SSE event is `event: done\ndata: {json TX dict}\n\n`

The frontend `StreamActor.#dispatch()` unwraps the `STREAM` envelope:
```javascript
// Level 3: {name:'STREAM', data:{name:'text', data:{text:'hello'}}}
//   -> inner = {name:'text', data:{text:'hello'}}
//   -> this.TEXT({text:'hello'}, meta)
```

### Pattern 5: Custom Frontend Streaming Component
**What:** A Web Component using `StreamActor` mixin that streams from the Run model.
**When to use:** When `ntx-stream` (which only shows raw text) is insufficient — you need structured event rendering (grant cards appearing as they're extracted).

```javascript
// Source: packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js
import { StreamActor } from '../core/StreamActor.js';

class NTXRunPanel extends StreamActor(HTMLElement) {
    // Called when stream yields {name:'text', data:{text:'...'}}
    TEXT(data, meta)        { /* append to log */ }
    // Called when stream yields {name:'tool_call', data:{tool:'...', args:{...}}}
    TOOL_CALL(data, meta)   { /* show tool activity */ }
    TOOL_RESULT(data, meta) { /* update tool card */ }
    THINKING(data, meta)    { /* show thinking */ }
    DONE(data, meta)        { /* show summary */ }
    STREAM_END(data)        { /* update run status */ }
    STREAM_ERROR(err)       { /* show error */ }
}
```

The `StreamActor.js` is served from the agents package static dir. Its import path from veille's static component would be `../components/StreamActor.js` if the component lives in the framework's static folder, but since veille has a custom `static/` dir, the path depends on how N3TX serves files. Check where `StreamActor.js` ends up at runtime.

**IMPORTANT:** StreamActor is in the agents package at `n3tx_agents/static/components/StreamActor.js`. The veille index.html already imports `ntx-stream.js` from `./components/ntx-stream.js` — meaning N3TX's SSR='full' mode merges all static dirs and serves them at the same URL path. So `./components/StreamActor.js` will be available.

### Anti-Patterns to Avoid
- **Calling `agentic()` with no tools:** AgentMixin logs a warning if no tools are discovered. Always verify `__agent__` config registers at least `web_tools`.
- **Calling `run()` directly from HTTP:** Expose `agentic()` or a wrapper via `@expose_route`, never `run()`. The `run()` method has no guardrails or config cascade.
- **Blocking the event loop with Playwright:** Use `async_playwright()` context manager inside an `async` `@expose_route` method. Never run sync playwright in a sync route.
- **Using `ntx-stream` for rich event output:** `ntx-stream` only renders `data.text`. For structured events (grant cards, tool call logs), a custom `StreamActor`-based component is needed.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSE streaming | Custom SSE loop | `@expose_route(stream=True)` + async generator | NetworkAPI handles SSE framing, chunk/done/error events automatically |
| Tool dispatch through Matrix | Direct method calls | `discover_tools()` + `make_tool()` | Handles TX routing, auth context, error translation automatically |
| LLM iteration | Custom pydantic-ai loop | `agentic_stream()` | Already handles PartStartEvent/PartDeltaEvent/CallToolsNode graph, thinking, tool calls |
| HTML cleanup | Custom regex stripping | stdlib `html.parser` or `bs4` | Edge cases in malformed HTML will break naive regex |
| Agent auth context | Manual user injection | Declare `user: User = None` param on `@expose_route` | Route layer resolves from JWT automatically (from `routes_fastapi.py._resolve_user()`) |

**Key insight:** The entire streaming pipeline (LLM events → TX chunks → SSE frames → frontend dispatch) is handled by the framework. The implementation only needs to declare `stream=True`, yield TX-aligned dicts, and implement UPPERCASE handlers on the frontend.

## Common Pitfalls

### Pitfall 1: WebTools Not Registered in Matrix
**What goes wrong:** Agent gets "Tool discovery: actor 'web_tools' not found in Matrix" warning and has no scraping tools.
**Why it happens:** `WebTools` must be in the `models=[...]` list in `create_app()`. Non-storable models still need to be registered to appear in the Matrix.
**How to avoid:** Add `WebTools` to `create_app(models=[User, Organization, Source, Grant, Run, WebTools], ...)`.
**Warning signs:** `discover_tools` warning in server logs, LLM generates no tool calls.

### Pitfall 2: Import Ordering for Run Model
**What goes wrong:** `Run.__agent__ = True` silently does nothing — no `agentic_stream()` method on instances.
**Why it happens:** `import n3tx_agents` must run BEFORE `from models import Run` so `register_mixin('__agent__', AgentMixin)` fires before `Run`'s class body executes.
**How to avoid:** The veille `main.py` already has `import n3tx_agents` before model imports. Just add `Run` to the `models` import — it will pick up the mixin correctly.
**Warning signs:** `AttributeError: 'Run' object has no attribute 'agentic_stream'`.

### Pitfall 3: Playwright Blocking Event Loop
**What goes wrong:** Playwright's sync API blocks the async FastAPI event loop, causing timeouts.
**Why it happens:** Using `playwright.sync_api` instead of `playwright.async_api`.
**How to avoid:** Always use `from playwright.async_api import async_playwright` and `async with async_playwright() as p:`.
**Warning signs:** Server hangs on playwright requests, other requests time out during scraping.

### Pitfall 4: Grant Dedup — Checking by URL Race Condition
**What goes wrong:** Two concurrent runs create duplicate grants if the URL check and create are not atomic.
**Why it happens:** Agent checks "does this URL exist?" then creates — but between check and create, another run could have created the same grant.
**How to avoid:** For Phase 2 (single concurrent run), this is not a real issue. The `execute` method creates one Run at a time. Add a note in code that concurrent runs are not supported until a lock mechanism is added.

### Pitfall 5: `agentic_stream()` on Class vs Instance
**What goes wrong:** Calling `Run.agentic_stream(...)` on the class instead of on an instance gives schema context but not instance state (status, id, etc.).
**Why it happens:** `agentic_stream` is a `@fullmethod` — works on both class and instance, but instance mode includes `_build_instance_text()` which adds current field values to context.
**How to avoid:** In `execute()`, `self` is the Run instance — call `self.agentic_stream(...)` (or just `agentic_stream()` since it's a method on `self`). The `execute` method body runs as an instance method automatically.

### Pitfall 6: Grant `source_urls` List vs Single `source_url`
**What goes wrong:** Dedup tracking requires storing multiple source URLs per grant, but current `Grant.source_url` is a single `str` field.
**Why it happens:** Phase 1 designed `source_url` as a single string. Phase 2 dedup requires tracking "this grant was found at source A and source B."
**How to avoid:** Add a `source_urls` field as `list = Field(default_factory=list)` to Grant. Keep `source_url` for backward compat or migrate it. SQLite auto-serializes `list` fields to JSON TEXT.

### Pitfall 7: StreamActor Import Path in Custom Component
**What goes wrong:** `import { StreamActor } from './StreamActor.js'` 404s because the path is wrong.
**Why it happens:** `StreamActor.js` lives in `n3tx_agents/static/components/`. When N3TX merges static dirs (SSR='full'), it's served at `./components/StreamActor.js`. But the custom component in veille's static dir may be at a different relative position.
**How to avoid:** Use the same relative path as `ntx-agent-live.js` uses: `import { StreamActor } from './StreamActor.js'` (both in the `components/` folder). Place `ntx-run-panel.js` in a `static/components/` directory in veille (N3TX will merge it), OR copy the component directly inline.

## Code Examples

### WebTools Actor (verified pattern)
```python
# Source: examples/grants/models/web_tools.py
from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.utils.decorators import expose_route
from n3tx_core.authorize import AUTHENTICATED

class WebTools(ActorModel):
    __tablename__ = 'web_tools'
    __storable__ = False

    @expose_route('/scrape', methods=['POST'], access=AUTHENTICATED)
    async def scrape(self, url: str) -> dict:
        """Fetch a URL and return its text content."""
        import httpx
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            resp = await client.get(url)
        # Extract text from HTML using stdlib
        text = _html_to_text(resp.text)
        return {'url': url, 'status': resp.status_code, 'text': text[:20000]}

    @expose_route('/scrape_js', methods=['POST'], access=AUTHENTICATED)
    async def scrape_js(self, url: str) -> dict:
        """Fetch a JS-rendered page using Playwright."""
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=30000)
            html = await page.content()
            await browser.close()
        text = _html_to_text(html)
        return {'url': url, 'status': 200, 'text': text[:20000]}
```

### HTML-to-Text with Stdlib
```python
# Source: verified via python3 test
from html.parser import HTMLParser

class _TextExtractor(HTMLParser):
    _SKIP_TAGS = frozenset({'script', 'style', 'nav', 'header', 'footer', 'aside'})

    def __init__(self):
        super().__init__()
        self._skip = False
        self._parts = []

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP_TAGS:
            self._skip = True

    def handle_endtag(self, tag):
        if tag in self._SKIP_TAGS:
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            text = data.strip()
            if text:
                self._parts.append(text)


def _html_to_text(html: str) -> str:
    """Extract readable text from HTML, stripping scripts/styles."""
    extractor = _TextExtractor()
    extractor.feed(html)
    return ' '.join(extractor._parts)
```

### Run Model Streaming Method
```python
# Source: verified from mixin.py run_stream() pattern
from n3tx_agents.actor import TextChunk, ToolCallEvent, ToolResultEvent, ThinkingChunk, DoneChunk
from n3tx_core.utils.decorators import expose_route
from n3tx_core.authorize import AUTHENTICATED

class Run(ActorModel):
    __tablename__ = 'runs'
    __storable__ = True
    __agent__ = {
        'self_tools': False,
        'neighbors': False,
        'tools': ['web_tools', 'grants', 'sources'],
    }

    @expose_route('/execute', methods=['POST'], stream=True, access=AUTHENTICATED,
                  events={
                      'text': TextChunk,
                      'tool_call': ToolCallEvent,
                      'tool_result': ToolResultEvent,
                      'thinking': ThinkingChunk,
                      'done': DoneChunk,
                  })
    async def execute(self, adhoc_url: str = ''):
        """Execute the scraping run. Streams agent progress as events."""
        from datetime import datetime
        # Update status to running
        Run.update(self.id, {'status': 'running', 'started_at': datetime.utcnow().isoformat()})

        task = self._build_task(adhoc_url)
        prompt = self._build_prompt()

        try:
            async for chunk in self.agentic_stream(task=task, prompt=prompt):
                yield chunk

            Run.update(self.id, {'status': 'complete', 'completed_at': datetime.utcnow().isoformat()})
        except Exception as e:
            Run.update(self.id, {'status': 'failed'})
            raise
```

### Frontend StreamActor Component Skeleton
```javascript
// Source: pattern from packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js
import { StreamActor } from './StreamActor.js';
import { config } from '../config.js';

class NTXRunPanel extends StreamActor(HTMLElement) {
    connectedCallback() {
        this.attachShadow({ mode: 'open' });
        // ... render template
    }

    _startRun(runId, adhocUrl = '') {
        const url = `${config.API_URL}/runs/${runId}/execute`;
        this.stream(url, { adhoc_url: adhocUrl });
    }

    // TX inbox handlers — MUST be UPPERCASE
    TEXT(data, meta)        { this._appendLog(data.text); }
    TOOL_CALL(data, meta)   { this._appendLog(`Calling ${data.tool}...`); }
    TOOL_RESULT(data, meta) { /* update tool card */ }
    THINKING(data, meta)    { /* optional thinking display */ }
    DONE(data, meta)        { this._showSummary(data); }
    STREAM_END(data)        { this._setStatus('done'); }
    STREAM_ERROR(err)       { this._setStatus('error', err); }
}

customElements.define('ntx-run-panel', NTXRunPanel);
```

### Grant Deduplication in WebTools or Run
```python
# Source: based on StorableMixin.list() verified pattern
@expose_route('/check_duplicate', methods=['POST'], access=AUTHENTICATED)
def check_duplicate(self, url: str, title: str = '') -> dict:
    """Check if a grant already exists by URL or similar title."""
    # Fast: URL match
    existing = Grant.list(limit=100)
    data = existing.get('data', existing) if isinstance(existing, dict) else existing
    for grant in data:
        if url and grant.get('url') == url:
            return {'duplicate': True, 'id': grant.get('id'), 'method': 'url'}
        if url and grant.get('source_url') == url:
            return {'duplicate': True, 'id': grant.get('id'), 'method': 'source_url'}
    # No URL match found — return False; LLM can do title comparison in its reasoning
    return {'duplicate': False}
```

## Grant Model Changes Needed

The current `Grant` model needs two additions for Phase 2:

### 1. Add `source_urls` (list) for dedup tracking
```python
# Current: source_url: str = Field(default='')
# Add:
source_urls: list = Field(default_factory=list,
    json_schema_extra={'ui': {'display': False}})  # hide from UI, internal tracking
```
SQLite auto-serializes `list` to JSON TEXT (verified in MEMORY.md: "SQLite JSON fields: Now handled at framework level (v0.9)").

### 2. `run_id` already exists
The `run_id: Optional[int]` field is already in `Grant` — good for linking grants to the run that discovered them.

## Run Model Design

### Fields (complete set)
```python
class Run(ActorModel):
    __tablename__ = 'runs'
    __storable__ = True
    __agent__ = {
        'self_tools': False,
        'neighbors': False,
        'tools': ['web_tools', 'grants', 'sources'],
    }
    __access__ = {
        'read': AUTHENTICATED,
        'create': AUTHENTICATED,
        'update': AUTHENTICATED,
        'delete': ROLE('admin'),
    }
    __ui__ = {
        'field_order': ['status', 'type', 'started_at', 'completed_at', 'grants_found', 'sources_covered', 'error'],
        'groups': {'Status': ['status', 'type', 'started_at', 'completed_at'],
                   'Results': ['grants_found', 'sources_covered'],
                   'Errors': ['error']},
    }

    status: str = Field(default='pending')      # pending|running|complete|failed
    type: str = Field(default='full')           # full|adhoc
    started_at: Optional[str] = Field(default=None)
    completed_at: Optional[str] = Field(default=None)
    grants_found: int = Field(default=0)
    sources_covered: int = Field(default=0)
    adhoc_url: str = Field(default='')         # set for type='adhoc' runs
    error: str = Field(default='')
```

### Triggering Pattern (frontend → backend)
1. User clicks "Start Run" → frontend calls `POST /runs` with `{'type': 'full'}` to create Run record
2. Frontend immediately calls `POST /runs/{id}/execute` as an SSE stream
3. Backend streams events as agent works
4. On `DONE`, frontend shows summary; on `STREAM_END`, marks run complete in UI

For ad-hoc: `POST /runs` with `{'type': 'adhoc', 'adhoc_url': 'https://...'}` then same stream flow.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| AgentActor (data-as-agent) | Run with `__agent__ = True` (model-as-agent) | Phase 2 design | Run records are stored, queryable, have lifecycle; grants example uses AgentActor but veille needs persistent run history |
| `bs4` for HTML parsing | stdlib `html.parser` if bs4 not installed | N/A (missing dep) | Must install `beautifulsoup4` or use stdlib |

**Deprecated/outdated in context:**
- `stream_chunk`/`stream_end` on TX: Use `chunk()`/`end()` instead (alias kept for compat, verified in `tx.py`)
- Pydantic AI v1 API: Current code uses `ai_agent.iter()` not `ai_agent.run()` for streaming — this is the v2 graph API

## Open Questions

1. **`StreamActor.js` path from `ntx-run-panel.js`**
   - What we know: `StreamActor.js` is in `n3tx_agents/static/components/`. SSR='full' merges multiple static dirs.
   - What's unclear: The exact URL served for the agents package static files.
   - Recommendation: Check how `ntx-agent-live.js` is served and trace its import of `StreamActor`. If it works, the same relative import `./StreamActor.js` will work from a component in `static/components/`.

2. **Agent prompt for scraping runs**
   - What we know: `scraping_notes` per source is injected as prompt text per the CONTEXT.md design. `agentic_stream()` accepts a `prompt=` kwarg.
   - What's unclear: How to dynamically build the prompt that includes all active sources + their scraping_notes.
   - Recommendation: Build the prompt inside `execute()` by calling `Source.list()` and injecting source details. This is plain Python inside the model method.

3. **LLM response format for extracted grants**
   - What we know: `result_type` can be a Pydantic model for structured output. But streaming + structured output may conflict.
   - What's unclear: Whether `result_type` works with `run_stream()`.
   - Recommendation: Let the LLM call CRUD tools (`grants_create`) directly to store grants rather than returning structured data. This is the natural tool-use pattern and avoids the streaming+structured output issue.

## Sources

### Primary (HIGH confidence — verified from source code)
- `packages/n3tx-agents/src/n3tx_agents/mixin.py` — AgentMixin, agentic_stream(), run_stream(), TX-aligned chunk format
- `packages/n3tx-agents/src/n3tx_agents/actor.py` — AgentActor, TextChunk/ToolCallEvent/etc event models
- `packages/n3tx-agents/src/n3tx_agents/tools.py` — discover_tools(), tool auto-exclusion, tool registration
- `packages/n3tx-actors/src/n3tx_actors/api/network_api.py` — _sse_from_stream(), streaming route registration, SSE wire format
- `packages/n3tx-actors/src/n3tx_actors/models/actor_model.py` — streaming handler (isasyncgen), tx.chunk()/tx.end()
- `packages/n3tx-actors/src/n3tx_actors/tx.py` — TX.chunk(), TX.end(), stream_end meta flag
- `packages/n3tx-agents/src/n3tx_agents/static/components/StreamActor.js` — frontend stream dispatch, UPPERCASE convention, STREAM envelope unwrapping
- `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js` — reference implementation of custom streaming component
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js` — NTTStream (built-in text-only stream renderer)
- `packages/n3tx-core/src/n3tx_core/static/core/transport/HTTP.js` — HTTP.stream() SSE client
- `examples/grants/models/web_tools.py` — existing WebTools pattern (httpx + bs4)
- `apps/veille/models/grant.py` — current Grant model fields
- `apps/veille/main.py` — current app bootstrap with Level 3 routing pattern

### Secondary (verified environment)
- `pip show httpx` → httpx 0.28.1 installed
- `pip show playwright` → playwright 1.58.0 installed, chromium browser launches successfully
- `bs4` not installed (tested `python3 -c "import bs4"` → ImportError)
- stdlib `html.parser` functional (tested text extraction)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified via pip/imports
- Architecture patterns: HIGH — all from actual source code
- Streaming wire format: HIGH — traced through NetworkAPI → SSE → StreamActor
- Pitfalls: HIGH — derived from code inspection and MEMORY.md lessons
- WebTools pattern: HIGH — exact pattern exists in examples/grants/
- Frontend component: MEDIUM — pattern from ntx-agent-live.js is solid, but import path for StreamActor.js needs runtime verification

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (N3TX 0.10 is stable; pydantic-ai API is the main risk area)
