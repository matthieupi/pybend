# P6: Scanner + Reviewer Agent Pipeline

## Summary

Expand the agent system with 3 new tool actors, execution history tracking, a Reviewer agent, and a sequential pipeline endpoint.

## New Models

### `example_grants/models/grants_gov_tools.py` (New)
Non-storable ActorModel wrapping the Grants.gov REST API.

**Methods:**
- `search(keyword, agency=None, rows=25)`: Calls `https://www.grants.gov/grantsws/rest/opportunities/search/` with keyword + optional agency filter. Returns `{total, opportunities: [{title, agency, deadline, url, description}]}`
- `detail(opportunity_id)`: Fetches full opportunity details from Grants.gov API

Pattern: follows `WebTools` (non-storable ActorModel with `@expose_route` methods).

### `example_grants/models/dedup_tools.py` (New)
Non-storable ActorModel for deterministic duplicate checking.

**Method:**
- `check_duplicate(title, url=None)`:
  - Step 1: Exact URL match against existing grants
  - Step 2: Fuzzy title match using `difflib.SequenceMatcher` (threshold 0.85)
  - Returns `{is_duplicate, match_type, matched_id, similarity}`

### `example_grants/models/agent_run.py` (New)
Storable ActorModel for execution history.

```python
class AgentRun(ActorModel):
    __tablename__ = 'agent_runs'
    __storable__ = True

    agent_id: int
    agent_name: str = ''
    task: str = ''
    status: str = 'pending'  # pending | running | completed | failed
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    requests: int = 0
    token_usage: dict = Field(default_factory=dict)
    error: str = ''
```

## Core Framework Changes

### `src/pybend/core/agents/mixin.py`

**A. `output_type` parameter** — Passed through to pydantic-ai Agent for structured output.

**B. `_record_run()` method** — Best-effort recording of agent execution:
- Looks up `AgentRun` from `registered_models` by tablename (no hard import)
- Creates record with agent_id, task, status, token usage, timestamps
- Silently returns if AgentRun model is not registered (e.g., in tests)
- Called in `finally` block of `agent_run()` so cleanup happens even on failure

Design principle: Core agents mixin has zero imports from `example_grants`. The `AgentRun` class is discovered via `registered_models` lookup.

## Seed Data Updates

### `example_grants/seed.py`

**Updated Scanner prompt:**
- Add Grants.gov API search as primary discovery method
- Add dedup check before creating grants
- Add tool links for `grants_gov_tools` and `dedup_tools`

**New Reviewer agent:**
```python
AgentActor(
    name="Grant Reviewer",
    prompt="You are a grant quality reviewer. List grants with status='discovered'. "
           "Validate URL accessibility, data completeness. Update valid grants to 'reviewed'.",
    llm="anthropic:claude-sonnet-4-5-20250929",
    constraints={"max_iterations": 30},
)
```

**Reviewer tool links:** grants (CRUD), web_tools (URL validation), dedup_tools (duplicate checking)

## Pipeline Orchestration

### `example_grants/pipeline.py` (New)

Sequential pipeline: Scanner → Reviewer.

```python
async def run_scan_review_pipeline(scanner_id, reviewer_id, task, **kwargs) -> dict:
    # Phase 1: Run Scanner
    scanner = AgentActor.get(scanner_id)
    scanner_result = await scanner.run(task=task, **kwargs)

    # Phase 2: Run Reviewer
    reviewer = AgentActor.get(reviewer_id)
    reviewer_result = await reviewer.run(
        task="Review all grants with status='discovered'", **kwargs)

    return {scanner, reviewer, timing}
```

**Route:** `POST /pipeline/scan-review` in main.py.

**Why Option B (pipeline endpoint) over alternatives:**

| Approach | Pros | Cons |
|----------|------|------|
| A: Manual | Zero code | Two calls, no coordination |
| **B: Pipeline endpoint** | **Single call, combined results, easy cron** | Hardcoded two-agent sequence |
| C: TX-driven | Event-driven, scales to N | Complex, harder to debug |

## P5 Integration Notes

- If P5 adds `Grant.review()` method: Reviewer agent uses `grants_review` instead of `grants_update`
- If P5 adds validators (future deadlines, amounts): Pydantic auto-validates → TX.error() → ModelRetry → LLM corrects
- Current plan uses `grants_update` which works today; update prompt when P5 lands

## Cost Projections

**With Grants.gov API (structured JSON):**
- Scanner: ~5,000 tokens per source
- Reviewer: ~3,000 tokens per batch of 10 grants
- Total per pipeline run (4 sources): ~25,000 tokens
- At Claude Sonnet rates: ~$0.08-$0.15 per run

**Compared to current HTML scraping:** 50-70% fewer tokens.

**Monthly at 4 runs/day:** ~$10-18/month.

## Tests

### `example_grants/tests/test_grants_gov_tools.py`
- Schema has search and detail methods
- `@pytest.mark.integration`: search returns opportunities, agency filter works

### `example_grants/tests/test_dedup_tools.py`
- Schema has check_duplicate method
- Exact URL match detected
- Fuzzy title match detected (similarity > 0.85)
- No match returns `is_duplicate: false`

### `example_grants/tests/test_agent_run_model.py`
- CRUD operations on AgentRun
- List agent runs

### `example_grants/tests/test_pipeline.py`
- Pipeline runs both agents, returns combined results with timing
- Agent run creates AgentRun record

### Updated: `example_grants/tests/conftest.py`
- Register new models, seed Reviewer agent
- Add `reviewer` to seed_data fixture

### Updated: `example_grants/tests/test_schema_endpoints.py`
- Schema tests for GrantsGovTools, DeduplicationTools, AgentRun

## Execution Order

```
Day 1: Foundation models (parallel — no deps between them)
  [1a] GrantsGovTools model
  [1b] DeduplicationTools model
  [1c] AgentRun model
  [1d] models/__init__.py
  [1e] main.py registration

Day 2: Core mixin enhancement
  [2a] output_type in agent_run()
  [2b] _record_run in AgentMixin

Day 3: Seed data + agents
  [3a] Scanner prompt update
  [3b] Reviewer agent definition
  [3c] Tool links

Day 4: Pipeline
  [4a] pipeline.py
  [4b] Pipeline route in main.py

Day 5-6: Tests
  [5a-f] All test files

Day 7: Integration testing + docs
```

## What Goes in Core vs. example_grants

| Change | Location | Rationale |
|--------|----------|-----------|
| `output_type` param | `pybend.core.agents.mixin` | Generic framework capability |
| `_record_run` helper | `pybend.core.agents.mixin` | Optional, uses registered_models lookup |
| GrantsGovTools | `example_grants/models/` | Domain-specific |
| DeduplicationTools | `example_grants/models/` | Domain-specific, imports Grant |
| AgentRun | `example_grants/models/` | App-level (could promote to core later) |
| pipeline.py | `example_grants/` | App-level orchestration |

## Files Summary

**New files (6):**
- `example_grants/models/grants_gov_tools.py`
- `example_grants/models/dedup_tools.py`
- `example_grants/models/agent_run.py`
- `example_grants/pipeline.py`
- `example_grants/tests/test_grants_gov_tools.py`
- `example_grants/tests/test_dedup_tools.py`
- `example_grants/tests/test_agent_run_model.py`
- `example_grants/tests/test_pipeline.py`

**Modified files (5):**
- `src/pybend/core/agents/mixin.py`
- `example_grants/models/__init__.py`
- `example_grants/main.py`
- `example_grants/seed.py`
- `example_grants/tests/conftest.py`
- `example_grants/tests/test_schema_endpoints.py`

## Challenges

1. **Grants.gov API availability**: Free, unauthenticated, but may have rate limits. Tests marked `@pytest.mark.integration`.
2. **Dedup scaling**: Listing all grants for comparison works now; at 1000+, add SQL-based title search.
3. **Tool count**: Scanner at ~17 tools approaches the 15-20 confusion threshold. Monitor accuracy.
4. **Pipeline timeout**: Per-tool-call timeout via `asyncio.wait_for` (30s), total iterations capped by `UsageLimits.request_limit`.
