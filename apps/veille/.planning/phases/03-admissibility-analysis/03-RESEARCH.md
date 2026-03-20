# Phase 3: Admissibility Analysis - Research

**Researched:** 2026-03-20
**Domain:** N3TX AgentMixin streaming, Grant model extension, custom @expose_route instance methods
**Confidence:** HIGH (all findings from actual source code in the veille codebase and N3TX framework)

## Summary

Phase 3 adds automatic admissibility analysis to every discovered grant. The agent reads the organization profile and each grant's eligibility criteria, then produces a score (0-1), a three-value classification (admissible / partially admissible / non-admissible), and a written justification (stored as Markdown).

The Grant model already has the admissibility fields from Phase 1: `status`, `admissibility_score`, and `admissibility_reasoning`. The `status` field (currently `'new'`) doubles as the admissibility classification bucket — it needs to support the values `admissible`, `partially admissible`, `non-admissible` (and keep `new` for unanalyzed grants). No new fields are required on Grant.

The cleanest integration strategy is a two-tier approach:

1. **Automatic post-scrape:** After the Run's `execute()` completes, call `Grant.analyze_all(run_id=self.id)` to queue analysis for newly discovered grants. This happens inside the existing `execute()` method after the scraping loop, keeping analysis linked to the run that created the grants.
2. **Per-grant re-run (ADM-04):** Add a streaming `@expose_route('/analyze', stream=True)` instance method on `Grant`. The user can trigger it from the UI on any grant to re-run analysis (e.g., after updating the org profile).

The admissibility agent does NOT need a separate model. The `Grant` model gets `__agent__ = True` with tools pointing to `organizations` (to read the org profile) and its own `self_tools=True` (so the agent can update itself). The agent is given the grant's current data as instance context via `self.agentic_stream()`, and the org profile via `tools=['organizations']`.

The frontend for the per-grant re-run can be either a compact inline panel in the grant card (extending `ntx-item`) or a standalone `<ntx-grant-analyze>` component on a dedicated route. Given the existing hash-routing pattern, a standalone panel on `#analyze/{grant_id}` is the simplest approach.

**Primary recommendation:** Add `__agent__ = True` to `Grant` with `self_tools=True, neighbors=False, tools=['organizations']`. Add `analyze()` streaming instance method on `Grant`. In `Run.execute()`, call a non-streaming `analyze_batch()` class method after scraping completes to analyze all new grants. Build `<ntx-grant-analyze>` as a StreamActor component in `static/components/`.

---

## Existing Model Fields (verified from source code)

### Grant model fields (current state after Phase 2)

```
apps/veille/models/grant.py
```

| Field | Type | Default | Phase 3 relevance |
|-------|------|---------|-------------------|
| `title` | `str` | required | Agent reads to identify the grant |
| `funder` | `str` | `''` | Agent context |
| `url` | `str` | `''` | Agent context |
| `status` | `str` | `'new'` | **Classification target** — will hold `admissible/partially admissible/non-admissible` |
| `admissibility_score` | `Optional[float]` | `None` | **Score target** — 0.0 to 1.0 |
| `admissibility_reasoning` | `MarkdownField` | `''` | **Justification target** — written as Markdown |
| `eligibility_criteria` | `list` | `[]` | Agent reads these to match against org profile |
| `description` | `TextareaField` | `''` | Agent reads for context |
| `amount_min/max` | `Optional[float]` | `None` | Agent reads for financial fit |
| `deadline` | `Optional[str]` | `None` | Agent context |
| `run_id` | `Optional[int]` | `None` | Used to find grants from a specific run |
| `source_urls` | `list` | `[]` | Hidden UI field, irrelevant to analysis |

**Conclusion:** No new fields needed on Grant. All three output fields (`status`, `admissibility_score`, `admissibility_reasoning`) already exist.

### Organization model fields (current state)

```
apps/veille/models/organization.py
```

| Field | Type | Phase 3 relevance |
|-------|------|-------------------|
| `name` | `str` | Agent context |
| `mission` | `TextareaField` | **Core matching criterion** |
| `activities` | `TextareaField` | **Core matching criterion** |
| `legal_status` | `str` | **Eligibility criterion** |
| `province` | `str` | **Geographic eligibility** |
| `charitable_status` | `str` | **Eligibility criterion** |
| `employee_count` | `Optional[int]` | **Size criterion** |
| `annual_budget` | `Optional[float]` | **Size criterion** |
| `focus_areas` | `list` | **Thematic matching** |
| `custom_criteria` | `dict` | **Custom eligibility criteria** |
| `documents` | `list` | Document filenames stored on disk |

**Key insight:** The `organizations` actor exposes CRUD tools. With `tools=['organizations']` in `__agent__`, the grant analysis agent can call `organizations_list()` to read the org profile in full. This is more robust than injecting the profile as a string in the prompt (it's live data, not snapshot).

---

## Architecture Patterns

### Recommended Change to Project Structure

```
apps/veille/
├── models/
│   └── grant.py                     # MODIFIED: add __agent__ = True + analyze() method
├── models/
│   └── run.py                       # MODIFIED: call analyze_batch() after execute() completes
└── static/
    └── components/
        └── ntx-grant-analyze.js     # NEW: streaming analysis panel for per-grant re-run
```

No new models. No new DB tables. No new routes file changes needed.

### Pattern 1: Grant as Agent Model

**What:** Add `__agent__ = True` to `Grant` with explicit tool configuration.
**When to use:** When the model instance is both the subject of reasoning AND the actor that updates itself.

```python
# Source: apps/veille/models/grant.py (to be modified)
class Grant(ActorModel):
    __tablename__ = 'grants'
    __storable__ = True
    __agent__ = {
        'self_tools': True,       # Agent can call grants_update to save results
        'neighbors': False,       # No ListRef neighbors to discover
        'tools': ['organizations'],  # Read the org profile to evaluate fit
    }
    # ... existing fields unchanged ...
```

`self_tools=True` means the agent gets `grants_list`, `grants_get`, `grants_create`, `grants_update`, `grants_delete` as tools. The agent will use `grants_update` to save the analysis result (score, classification, reasoning) back to the grant record.

### Pattern 2: Streaming Instance Method on Grant (ADM-04)

**What:** `@expose_route('/analyze', stream=True)` on Grant — an instance method that streams analysis progress for a single grant.
**When to use:** Per-grant re-run triggered by the user (ADM-04).

The route becomes `POST /grants/{id}/analyze` — exactly the pattern used by `Run.execute()` at `POST /runs/{id}/execute`.

```python
# Source: pattern from apps/veille/models/run.py (verified)
from n3tx_agents.actor import (
    TextChunk, ToolCallEvent, ToolResultEvent, ThinkingChunk, DoneChunk,
)
from n3tx_core.utils.decorators import expose_route
from n3tx_core.authorize import AUTHENTICATED

@expose_route('/analyze', methods=['POST'], stream=True, access=AUTHENTICATED,
              events={
                  'text': TextChunk,
                  'tool_call': ToolCallEvent,
                  'tool_result': ToolResultEvent,
                  'thinking': ThinkingChunk,
                  'done': DoneChunk,
              })
async def analyze(self):
    """Analyze this grant's admissibility against the org profile. Streams progress."""
    task = self._build_analysis_task()
    prompt = self._build_analysis_prompt()
    async for chunk in self.agentic_stream(task=task, prompt=prompt):
        yield chunk
```

The `analyze()` method is an instance method (`self` present) — N3TX automatically routes it to `/grants/{id}/analyze` with `id` extracted from the URL path (verified in `network_api.py:_register_custom_routes`, line 393-394: `if is_instance_method: full_route = f"{endpoint_base}/{{id:int}}{route}"`).

### Pattern 3: Batch Analysis After Scraping (Automatic Post-Scrape)

**What:** After `Run.execute()` completes scraping, call `Grant.agentic()` (non-streaming) on each newly discovered grant.
**When to use:** Automatic analysis after a scraping run completes (Success Criterion 1).

This runs INSIDE `Run.execute()` after the scraping loop, before the status is set to `complete`:

```python
# Source: apps/veille/models/run.py (to be modified)
# After the agentic_stream scraping loop completes:

# Analyze each new grant from this run
from models.grant import Grant
grants = Grant.list(limit=1000)
data = grants.get('data', grants) if isinstance(grants, dict) else grants
new_grants = [g for g in data
              if (g.get('run_id') if isinstance(g, dict)
                  else getattr(g, 'run_id', None)) == self.id]

for grant_record in new_grants:
    grant_id = grant_record.get('id') if isinstance(grant_record, dict) else grant_record.id
    try:
        grant_instance = Grant.get(grant_id)
        # Non-streaming call — fire and forget per grant, results saved via tool call
        await grant_instance.agentic(
            task=grant_instance._build_analysis_task(),
            prompt=grant_instance._build_analysis_prompt(),
        )
    except Exception as e:
        logger.warning(f"Analysis failed for grant {grant_id}: {e}")

Run.update(self.id, {'status': 'complete', ...})
```

**Important:** The batch call uses non-streaming `agentic()` (not `agentic_stream()`). The Run's streaming endpoint is already in progress streaming scraping events to the user. Adding analysis events to the same stream would be possible but adds complexity. The simpler approach is to run non-streaming analysis synchronously between scraping completion and Run status update — the user sees the stream end, then grants appear as analyzed when they view the list.

**Alternative (streaming analysis events in same stream):** Yield analysis events from `Run.execute()` by calling `grant_instance.agentic_stream()` and yielding those chunks too. This is richer but adds significant stream duration. Research verdict: use non-streaming batch for Phase 3, leave streaming as optional enhancement.

### Pattern 4: Analysis Task and Prompt Construction

**What:** Build the analysis task and system prompt inside Grant model methods.
**When to use:** Both for batch (post-scrape) and per-grant (ADM-04) analysis.

```python
def _build_analysis_task(self) -> str:
    """Build the analysis task for this grant."""
    return (
        f"Analyze the admissibility of this grant for our organization.\n\n"
        f"Grant: {self.title}\n"
        f"Funder: {self.funder}\n"
        f"Description: {self.description[:500]}\n"
        f"Eligibility criteria: {self.eligibility_criteria}\n"
        f"Amount: {self.amount_min} - {self.amount_max}\n"
        f"Deadline: {self.deadline}\n\n"
        f"Steps:\n"
        f"1. Use organizations_list to read the organization profile.\n"
        f"2. Match each eligibility criterion against the org's profile fields.\n"
        f"3. Determine if the org is: admissible, partially admissible, or non-admissible.\n"
        f"4. Write a detailed justification in Markdown explaining each criterion match/mismatch.\n"
        f"5. Assign a score between 0.0 (fully inadmissible) and 1.0 (fully admissible).\n"
        f"6. Use grants_update to save: id={self.id}, "
        f"status=<classification>, admissibility_score=<float>, admissibility_reasoning=<markdown>.\n"
    )

def _build_analysis_prompt(self) -> str:
    """Build the system prompt for the admissibility agent."""
    return (
        "You are a grant admissibility analyst for a non-profit organization. "
        "Your job is to evaluate whether a grant opportunity matches the organization's profile "
        "and eligibility criteria.\n\n"
        "RULES:\n"
        "- Always call organizations_list first to read the organization profile.\n"
        "- Classify strictly as 'admissible', 'partially admissible', or 'non-admissible'.\n"
        "- Score: 0.0 = completely inadmissible, 0.5 = partially eligible, 1.0 = fully eligible.\n"
        "- Reasoning must be in Markdown format, referencing specific criteria.\n"
        "- Always call grants_update to save your analysis results.\n"
        "- Be thorough but concise. Focus on actionable criteria mismatches.\n"
    )
```

### Pattern 5: Agent Tool Discovery for Grant with `__agent__`

**What:** How `discover_tools()` resolves tool addresses for a `Grant` with `__agent__` config.
**When verified:** tools.py `discover_tools()`, mixin.py `tools()` fullmethod.

With `__agent__ = {'self_tools': True, 'neighbors': False, 'tools': ['organizations']}`:

1. `self_tools=True` → adds `'grants'` to address list (Grant's own `__tablename__`)
2. `neighbors=False` → no ListRef auto-discovery
3. `tools=['organizations']` → adds `'organizations'`

Final tool list: `['grants', 'organizations']`

Discovered tools:
- `grants_list`, `grants_get`, `grants_create`, `grants_update`, `grants_delete` (from CRUD)
- `organizations_list`, `organizations_get`, `organizations_create`, `organizations_update`, `organizations_delete` (from CRUD)

The agent will use `organizations_list()` to read the org profile and `grants_update(id=..., status=..., admissibility_score=..., admissibility_reasoning=...)` to save results.

**Key verification:** `discover_tools()` looks up actor addresses in `root._children`. `organizations` is registered in Matrix because `Organization` is in `create_app(models=[...])`. This works identically to how `Run` accesses `grants` and `web_tools`.

### Anti-Patterns to Avoid

- **Injecting org profile as a static string in the prompt:** The org profile can change (ADM-04 use case). Having the agent call `organizations_list` means it always reads fresh data, not a snapshot from when `main.py` booted.
- **Adding a separate `AnalysisRun` or `AdmissibilityAgent` model:** The `Grant` model already has all the admissibility fields. Adding `__agent__ = True` and one method is sufficient.
- **Using `result_type` for structured output on streaming calls:** `result_type` works for non-streaming `agentic()` but the integration with `run_stream()` is uncertain. Let the agent call `grants_update` as a tool call instead of returning structured output.
- **Separate streaming endpoint for batch analysis:** Batch analysis (post-scrape) should be non-streaming. Only per-grant re-run (ADM-04) needs streaming. Mixing them complicates the frontend.
- **Calling `Grant.agentic()` as a class method for instance analysis:** Always call on an instance (`grant_obj.agentic(...)`) so `ctx()` includes the current grant field values as LLM context via `_build_instance_text()`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Reading org profile in agent | String injection in prompt | `tools=['organizations']` + `organizations_list` tool call | Always reads fresh data; org can be updated before re-run (ADM-04) |
| Saving analysis result | Manual `Grant.update()` inside the method | Agent calls `grants_update` as tool | Consistent pattern; agent has full field context and can update correctly |
| Streaming analysis to frontend | Custom SSE loop | `@expose_route(stream=True)` + `agentic_stream()` | Same infrastructure as Run.execute() — proven pattern |
| Criteria matching logic | Hand-coded comparator | LLM reasoning in agent | The holistic LLM judgment (ADM-02) IS the matching (ADM-01) |
| Batch analysis orchestration | Separate scheduler or queue | Loop inside `Run.execute()` post-scraping | Simpler, no new infrastructure; batch size is small (one run's grants) |

**Key insight:** The agent calling `grants_update` to save its own results is idiomatic for this framework. The Run agent does the same with `grants_create`. Let the LLM handle output formatting and let the tool dispatch handle persistence.

---

## Common Pitfalls

### Pitfall 1: `__agent__` on Grant Before n3tx_agents Import

**What goes wrong:** `Grant.__agent__ = True` silently does nothing — no `agentic()` method.
**Why it happens:** `import n3tx_agents` must run BEFORE `from models import Grant`. `main.py` already has this in the correct order. Grant is imported after `import n3tx_agents`.
**How to avoid:** No change needed — existing import order in `main.py` is already correct.
**Warning signs:** `AttributeError: 'Grant' object has no attribute 'agentic'`.

### Pitfall 2: `status` Field Values — Enum vs Free String

**What goes wrong:** The agent produces `'admissible'` but the UI filters for `'Admissible'` (capital), or vice versa.
**Why it happens:** `status: str` has no enum constraint — the agent can write anything.
**How to avoid:** Be explicit in the agent task prompt: "Classify strictly as 'admissible', 'partially admissible', or 'non-admissible' (lowercase, exact spelling)." The justification in the system prompt enforces this. Add validation in the `analyze()` method as a post-processing step if needed.
**Warning signs:** Grants end up with `status='Admissible'` or `status='non_admissible'` that don't match UI filters.

### Pitfall 3: `Grant.get(id)` Returns Dict Not Instance

**What goes wrong:** `Grant.get(id)` returns a dict in some code paths; calling `.agentic()` on a dict raises `AttributeError`.
**Why it happens:** `StorableMixin.get()` may return the raw dict from SQLite depending on the actor handler path. Level 3 routing returns dicts from TX responses.
**How to avoid:** In the batch loop inside `Run.execute()`, call `Grant.get(grant_id)` and check: if it returns a dict, reconstruct the instance with `Grant(**data_dict)`. Or use `grant_instance = Grant(**Grant.get(grant_id))` if get always returns a dict at this layer.
**Warning signs:** `AttributeError: 'dict' object has no attribute 'agentic'`.

Verified workaround:
```python
raw = Grant.get(grant_id)
if isinstance(raw, dict):
    grant_instance = Grant(**{k: v for k, v in raw.items() if k != 'id'})
    grant_instance.id = grant_id
else:
    grant_instance = raw
```

### Pitfall 4: `organizations_list` Returns No Data

**What goes wrong:** Agent calls `organizations_list` and gets an empty list; analysis fails.
**Why it happens:** No organization profile configured. The app can start with zero organizations.
**How to avoid:** In `_build_analysis_task()`, pre-check that an org exists:
```python
from models.organization import Organization
orgs = Organization.list(limit=1)
data = orgs.get('data', orgs) if isinstance(orgs, dict) else orgs
if not data:
    return "No organization profile configured. Cannot analyze admissibility."
```
The agent task should short-circuit if no org profile exists. Alternatively, catch in the agent prompt: "If organizations_list returns an empty list, report that analysis cannot be performed and use grants_update to set status='new'."
**Warning signs:** Agent loops with "No organization found, cannot evaluate" and still tries to save.

### Pitfall 5: Streaming Analysis Events Inside Run.execute() Double-Yields

**What goes wrong:** If `Run.execute()` tries to `yield` analysis chunks while already streaming scraping chunks, the SSE stream may produce interleaved events that confuse the frontend.
**Why it happens:** `Run.execute()` is an async generator — you can add more `yield` statements after the scraping loop, but the frontend `NTXRunPanel` only knows about scraping events (tool calls for `web_tools_scrape`, `grants_create`). Analysis tool calls (`organizations_list`, `grants_update`) would appear as generic tool entries.
**How to avoid:** Run batch analysis non-streaming inside `Run.execute()` after the scraping generator completes. No additional yields from the analysis phase.
**Warning signs:** Run panel shows `organizations_list` and `grants_update` tool calls after the "Run complete" message.

### Pitfall 6: Scoring Values Outside 0-1 Range

**What goes wrong:** Agent returns `admissibility_score=85` (thinking it's a percentage) instead of `0.85`.
**Why it happens:** LLMs sometimes interpret "score" as a percentage.
**How to avoid:** Be explicit in task and prompt: "Score must be a float between 0.0 and 1.0, where 0.0 is completely inadmissible and 1.0 is fully admissible."
**Warning signs:** `admissibility_score = 75.0` in the database.

---

## Code Examples

### Grant Model with `__agent__` (verified pattern structure)

```python
# Source: pattern from apps/veille/models/run.py + packages/n3tx-agents/src/n3tx_agents/mixin.py
from n3tx_agents.actor import (
    TextChunk, ToolCallEvent, ToolResultEvent, ThinkingChunk, DoneChunk,
)
from n3tx_core.utils.decorators import expose_route
from n3tx_core.authorize import AUTHENTICATED

class Grant(ActorModel):
    __tablename__ = 'grants'
    __storable__ = True
    __agent__ = {
        'self_tools': True,         # grants_update saves analysis results
        'neighbors': False,
        'tools': ['organizations'], # organizations_list reads org profile
    }
    # ... existing fields unchanged ...

    @expose_route('/analyze', methods=['POST'], stream=True, access=AUTHENTICATED,
                  events={
                      'text': TextChunk,
                      'tool_call': ToolCallEvent,
                      'tool_result': ToolResultEvent,
                      'thinking': ThinkingChunk,
                      'done': DoneChunk,
                  })
    async def analyze(self):
        """Analyze this grant's admissibility. Streams progress.

        Route: POST /grants/{id}/analyze
        The agent reads the org profile, evaluates fit, and calls
        grants_update to save classification, score, and reasoning.
        """
        # Check org profile exists before starting agent
        from models.organization import Organization
        orgs = Organization.list(limit=1)
        data = orgs.get('data', orgs) if isinstance(orgs, dict) else orgs
        if not data:
            yield {
                'name': 'error',
                'data': {'message': 'No organization profile configured.'},
                'meta': {'error': True},
            }
            return

        task = self._build_analysis_task()
        prompt = self._build_analysis_prompt()

        Grant.update(self.id, {'status': 'analyzing'})

        try:
            async for chunk in self.agentic_stream(task=task, prompt=prompt):
                yield chunk
        except Exception as e:
            logger.error(f"Analysis failed for grant {self.id}: {e}")
            Grant.update(self.id, {'status': 'new'})
            raise
```

### Batch Analysis in Run.execute() (non-streaming)

```python
# Source: pattern verified from apps/veille/models/run.py
# Add this block inside Run.execute() after the scraping agentic_stream completes:

# Analyze all grants discovered in this run
from models.grant import Grant
try:
    all_grants = Grant.list(limit=1000)
    data = all_grants.get('data', all_grants) if isinstance(all_grants, dict) else all_grants
    new_grants = [g for g in data
                  if (g.get('run_id') if isinstance(g, dict)
                      else getattr(g, 'run_id', None)) == self.id]
    count = len(new_grants)

    for i, grant_record in enumerate(new_grants):
        grant_id = (grant_record.get('id') if isinstance(grant_record, dict)
                    else getattr(grant_record, 'id', None))
        if not grant_id:
            continue
        try:
            # Reconstruct instance (in Level 3, get() may return dict)
            raw = Grant.get(grant_id)
            if isinstance(raw, dict):
                grant_instance = Grant(**{k: v for k, v in raw.items()})
            else:
                grant_instance = raw

            await grant_instance.agentic(
                task=grant_instance._build_analysis_task(),
                prompt=grant_instance._build_analysis_prompt(),
            )
            logger.info(f"Analyzed grant {grant_id} ({i+1}/{count})")
        except Exception as e:
            logger.warning(f"Analysis failed for grant {grant_id}: {e}")
            # Continue with remaining grants
except Exception as e:
    logger.warning(f"Batch analysis failed: {e}")
```

### Frontend: ntx-grant-analyze Component

```javascript
// Source: pattern from apps/veille/static/components/ntx-run-panel.js
import { StreamActor } from './StreamActor.js';
import { config } from '../config.js';

class NTXGrantAnalyze extends StreamActor(HTMLElement) {
    #grantId = null;
    #els;

    static get observedAttributes() { return ['grant-id']; }

    attributeChangedCallback(name, _, newVal) {
        if (name === 'grant-id') {
            this.#grantId = parseInt(newVal, 10);
        }
    }

    connectedCallback() {
        this.attachShadow({ mode: 'open' });
        this.shadowRoot.innerHTML = `
            <style>${NTXGrantAnalyze.styles}</style>
            <div class="panel">
                <button id="analyze-btn" class="btn">Re-run Analysis</button>
                <div class="log" id="log"></div>
            </div>
        `;
        this.#els = {
            btn: this.shadowRoot.getElementById('analyze-btn'),
            log: this.shadowRoot.getElementById('log'),
        };
        this.#els.btn.addEventListener('click', () => this.#startAnalysis());
    }

    async #startAnalysis() {
        if (!this.#grantId) return;
        this.#els.log.innerHTML = '';
        this.#els.btn.disabled = true;

        const token = localStorage.getItem('jwtToken');
        const url = `${config.API_URL}/grants/${this.#grantId}/analyze`;
        this.stream(url, {}, { 'x-access-token': token });
    }

    // TX inbox handlers — MUST be UPPERCASE
    TEXT(data)        { this.#addEntry('text', data?.text || ''); }
    TOOL_CALL(data)   { this.#addEntry('tool', `Calling ${data?.tool}...`); }
    TOOL_RESULT(data) { /* tool completed */ }
    THINKING(data)    { this.#addEntry('thinking', data?.text || ''); }
    DONE(data)        { this.#addEntry('done', 'Analysis complete.'); }
    STREAM_END()      { this.#els.btn.disabled = false; }
    STREAM_ERROR(err) { this.#addEntry('error', err?.message || 'Error'); this.#els.btn.disabled = false; }

    #addEntry(type, text) {
        const el = document.createElement('div');
        el.className = `entry entry-${type}`;
        el.textContent = text;
        this.#els.log.appendChild(el);
    }
}

customElements.define('ntx-grant-analyze', NTXGrantAnalyze);
export { NTXGrantAnalyze };
```

### Analysis Task and Prompt Builder Methods

```python
# Source: pattern from apps/veille/models/run.py _build_task()/_build_prompt()
def _build_analysis_task(self) -> str:
    """Build the analysis task for the admissibility agent."""
    criteria_str = (
        '\n'.join(f'  - {c}' for c in self.eligibility_criteria)
        if self.eligibility_criteria else '  (none listed)'
    )
    return (
        f"Analyze admissibility of this grant for our organization.\n\n"
        f"GRANT DETAILS:\n"
        f"  Title: {self.title}\n"
        f"  Funder: {self.funder}\n"
        f"  Description: {(self.description or '')[:800]}\n"
        f"  Eligibility criteria:\n{criteria_str}\n"
        f"  Amount: {self.amount_min} to {self.amount_max}\n"
        f"  Deadline: {self.deadline}\n\n"
        f"STEPS:\n"
        f"1. Call organizations_list to read the organization profile.\n"
        f"2. For each eligibility criterion, check if the org meets it.\n"
        f"3. Determine the classification:\n"
        f"   - 'admissible': org meets all criteria\n"
        f"   - 'partially admissible': org meets some but not all\n"
        f"   - 'non-admissible': org does not meet key criteria\n"
        f"4. Write a Markdown justification referencing specific criteria.\n"
        f"5. Assign a score 0.0 (inadmissible) to 1.0 (fully admissible).\n"
        f"6. Call grants_update with: id={self.id}, status=<classification>, "
        f"admissibility_score=<float 0.0-1.0>, admissibility_reasoning=<markdown>.\n"
    )

def _build_analysis_prompt(self) -> str:
    """Build the system prompt for the admissibility agent."""
    return (
        "You are a grant admissibility analyst for a non-profit organization. "
        "Your job is to evaluate whether a grant matches the organization's eligibility profile.\n\n"
        "RULES:\n"
        "- Always call organizations_list FIRST to read the live organization profile.\n"
        "- Classification must be exactly one of: 'admissible', 'partially admissible', 'non-admissible'.\n"
        "- Score is a float from 0.0 to 1.0 (not a percentage).\n"
        "- Reasoning must be in Markdown format. Include a section per criterion.\n"
        "- Always call grants_update to save results before finishing.\n"
        "- Be specific: cite which profile fields match or fail which criteria.\n"
    )
```

---

## Integration Strategy: Answered Questions

### Q1: Auto after scraping vs separate trigger?

**Answer:** Both, implemented differently.

- **Automatic (Success Criterion 1):** Non-streaming `grant_instance.agentic()` loop runs inside `Run.execute()` after the scraping generator completes, before `Run.update(status='complete')`. The user sees the scraping stream end, then the run completes while analysis runs in background.
- **Manual re-run (ADM-04):** `POST /grants/{id}/analyze` streaming endpoint on Grant. User can trigger per-grant from the UI.

The two share the same `_build_analysis_task()` and `_build_analysis_prompt()` methods on Grant.

### Q2: What fields to add for admissibility results?

**Answer:** None. All three fields already exist from Phase 1:
- `status: str` (currently `'new'`) — will hold classification
- `admissibility_score: Optional[float]` — will hold 0.0-1.0 score
- `admissibility_reasoning: MarkdownField` — will hold justification

The `status` field already has `'new'` as default, which correctly represents "not yet analyzed." After analysis, it becomes `'admissible'`, `'partially admissible'`, or `'non-admissible'`.

### Q3: How does re-running work (ADM-04)?

**Answer:** `POST /grants/{id}/analyze` is a streaming instance method on Grant. N3TX auto-registers it at that URL because `analyze()` has `self` in its signature (verified: `network_api.py:_register_custom_routes` line 393 creates `{endpoint_base}/{id:int}{route}`). The user triggers it from `<ntx-grant-analyze grant-id="42">`.

### Q4: Does Grant need `__agent__`?

**Answer:** Yes. Grant needs `__agent__ = True` to get `agentic()` and `agentic_stream()` methods injected by `AgentMixin`. Without this, calling `grant_instance.agentic(...)` raises `AttributeError`.

### Q5: What tools does the admissibility agent need?

**Answer:** Exactly two tool groups:
- `'grants'` (via `self_tools=True`) — for `grants_update` to save results
- `'organizations'` (via `tools=['organizations']`) — for `organizations_list` to read the org profile

No web scraping tools needed (unlike the Run agent). No `'web_tools'` in the tool list.

### Q6: Streaming UI — extend ntx-run-panel or new component?

**Answer:** New component `<ntx-grant-analyze>`. The run panel is scoped to Run execution (scraping context, run creation, full/adhoc toggle). Grant analysis is per-entity, lives in the Grant view. A separate component avoids polluting the run panel with analysis context.

The component is simpler than `ntx-run-panel` — no run creation step, just a "Re-run Analysis" button that immediately calls `POST /grants/{id}/analyze`.

### Q7: Org model fields for matching?

**Answer:** All org fields are relevant to different grants:
- `mission`, `activities` — thematic fit (ADM-01/ADM-02)
- `legal_status`, `charitable_status` — eligibility gates (many grants require registered charity status)
- `province` — geographic eligibility (many grants are province-specific)
- `employee_count`, `annual_budget` — size criteria (some grants are for small orgs only)
- `focus_areas` — thematic match
- `custom_criteria` — user-defined extra matching criteria

The agent reads all of these via `organizations_list` tool call and reasons about them holistically.

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Separate analysis model/pipeline | `__agent__ = True` on Grant | No new models or DB tables |
| Manual criteria comparison code | LLM holistic reasoning (ADM-02) | More flexible, handles natural language criteria |
| Structured output from streaming | Agent saves via `grants_update` tool call | No streaming/structured-output conflict |

**Verified current status of Grant fields for admissibility:**
- `status = 'new'` — default, correct sentinel for "not yet analyzed"
- `admissibility_score = None` — default, correct (no score until analyzed)
- `admissibility_reasoning = ''` — default, correct (no reasoning until analyzed)
- These fields are already in the `__ui__` `Analysis` group on Grant

---

## Open Questions

1. **`Grant.get()` return type in Level 3 routing**
   - What we know: `StorableMixin.get()` returns a model instance in direct calls. But inside `Run.execute()`, the call goes through the actor system.
   - What's unclear: Whether `Grant.get(id)` called inside `Run.execute()` (itself running in an actor handler context) returns a dict or instance.
   - Recommendation: Defensively handle both: `if isinstance(raw, dict): grant_instance = Grant(**raw)`. Test in Phase 3 plan execution.

2. **`analyzing` status as intermediate state**
   - What we know: Setting `status='analyzing'` while the agent runs is safe — the field is a free string.
   - What's unclear: Whether the frontend Grant list should show an "analyzing" badge, or just show "new" until analysis completes.
   - Recommendation: Set `status='analyzing'` at start of `analyze()` so the Grant list shows progress. Reset to `'new'` on error. The planner can decide whether to add a frontend indicator for this state.

3. **Batch analysis order and duration**
   - What we know: A full run could discover 20-50 grants. Each analysis calls the LLM once (one `organizations_list` + one `grants_update`). At ~2-5 seconds per analysis, batch could take 60-250 seconds.
   - What's unclear: Whether the user expects the Run stream to keep the connection open during batch analysis, or whether analysis should run after the SSE stream closes.
   - Recommendation: Run batch analysis non-streaming after the scraping stream closes. The user's SSE connection to `/runs/{id}/execute` is done before batch analysis starts. This avoids long-running SSE connections and keeps concerns separate.

---

## Sources

### Primary (HIGH confidence — verified from source code)
- `apps/veille/models/grant.py` — existing Grant fields, all admissibility fields already present
- `apps/veille/models/run.py` — `execute()` streaming pattern, `_build_task()/_build_prompt()` methods, agentic_stream() usage
- `apps/veille/models/organization.py` — all org profile fields available to agent
- `apps/veille/models/web_tools.py` — non-storable ActorModel pattern (proof WebTools pattern works)
- `apps/veille/main.py` — import order (n3tx_agents before models), model registration list
- `packages/n3tx-agents/src/n3tx_agents/mixin.py` — AgentMixin `agentic()`, `agentic_stream()`, `tools()`, config cascade, `self_tools`/`neighbors`/`tools` config
- `packages/n3tx-agents/src/n3tx_agents/tools.py` — `discover_tools()` address resolution, CRUD tool generation, `self_tools` behavior
- `packages/n3tx-actors/src/n3tx_actors/api/network_api.py` — instance method routing (`/grants/{id}/analyze`), streaming route registration
- `packages/n3tx-agents/src/n3tx_agents/static/components/StreamActor.js` — UPPERCASE handler convention, STREAM envelope unwrapping
- `apps/veille/static/components/ntx-run-panel.js` — complete working StreamActor component to mirror for ntx-grant-analyze
- `packages/n3tx-core/src/n3tx_core/widgets/__init__.py` — MarkdownField is in n3tx-core (not n3tx-ui)

### Secondary (MEDIUM confidence)
- `apps/veille/.planning/phases/02-scraping-and-grant-extraction/02-RESEARCH.md` — Phase 2 research confirms streaming patterns, import ordering, WebTools registration
- `apps/veille/.planning/STATE.md` — current app state: 54 routes after Phase 2

---

## Metadata

**Confidence breakdown:**
- Existing Grant fields: HIGH — read directly from source file
- AgentMixin tool discovery: HIGH — traced through mixin.py tools() and tools.py discover_tools()
- Instance method routing: HIGH — verified in network_api.py _register_custom_routes()
- Batch analysis in Run.execute(): HIGH — pattern mirrors existing grant counting code
- Frontend component: HIGH — pattern is identical copy of ntx-run-panel.js minus the run creation logic
- `Grant.get()` return type in actor context: MEDIUM — needs runtime verification

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (N3TX 0.10 stable; no external library risk for this phase)
