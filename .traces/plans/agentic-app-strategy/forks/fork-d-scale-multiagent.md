# Fork D: Multi-Agent Coordination + Agent Specialization

**Prereqs:** Sprints 1-3 complete (observability, safety, StatusWidget, GrantsGovAPI, UserProfile, GrantMatch, MatcherTools)
**Duration:** ~4-6 weeks (3 phases)
**Branch:** `v0.10-fork-d-multiagent`

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Phase 1: Structured Output + Agent Memory (Week 1-2)](#2-phase-1-structured-output--agent-memory-week-1-2)
3. [Phase 2: Multi-Agent Pipeline (Week 3-4)](#3-phase-2-multi-agent-pipeline-week-3-4)
4. [Phase 3: Advanced Capabilities (Week 5-6)](#4-phase-3-advanced-capabilities-week-5-6)
5. [Test Strategy](#5-test-strategy)
6. [Risk Register](#6-risk-register)
7. [Framework vs Application Code Boundary](#7-framework-vs-application-code-boundary)

---

## 1. Architecture Overview

### Target State

```
                            Matrix (root)
                              |
    +--------+--------+-------+--------+--------+-----------+-----------+
    |        |        |       |        |        |           |           |
  grants  sources  web_tools  agents  agent_  grants_    sam_gov_    grant_
                                      tools   gov_api     api       analyzer
  (storable) (stor) (non-stor) (stor) (stor)  (non-stor) (non-stor) (non-stor)
    |
    | _subscribers = ['analyzer_monitor']
    |
    +--------> analyzer_monitor (Actor instance, registered on Matrix)
                    |
                    | On LIFECYCLE TX (event='after_create'):
                    |   1. Load Analyzer agent from DB
                    |   2. Call agent.run(task="Analyze grant {id}...")
                    |   3. Analyzer uses grant_analyzer tools
                    |   4. Grant.update() with score/status
                    v
              (triggers Analyzer AgentActor via agent_run())
```

### The Multi-Agent Pipeline (Event-Driven)

```
Scanner Agent                          Analyzer Agent                     Reporter Agent
(AgentActor #1)                       (AgentActor #2)                   (AgentActor #3)
tools: grants, sources,               tools: grants,                    tools: grants,
       web_tools, grants_gov_api             grant_analyzer                    notification_tools
                |                              ^                               ^
                | grants_create                |                               |
                v                              |                               |
           Grant.create()                      |                               |
                |                              |                               |
                | _publish_lifecycle           |                               |
                | ('after_create', data)       |                               |
                v                              |                               |
         AnalyzerMonitor.inbox()               |                               |
                |                              |                               |
                | loads AgentActor #2          |                               |
                | calls agent.run()  ----------+                               |
                |                                                              |
                | (future: on high score,      |                               |
                |  publish to reporter)  ------+-------------------------------+
```

### Key Design Decisions

1. **AnalyzerMonitor is a plain Actor instance** (not ActorModel, not ActorProxy). It has no storage, no schema, no routes. It is the thinnest possible glue between lifecycle events and agent invocations. Registered manually on Matrix via `matrix.register(monitor)`.

2. **Agent specialization is data, not code.** The Scanner, Analyzer, and Reporter are all `AgentActor` records in the DB with different `prompt` and `tools` fields. No new Python classes needed for new agent types.

3. **No external multi-agent frameworks.** CrewAI and LangGraph are not used. Coordination flows through PyBend's native `_publish_lifecycle()` -> `_subscribers` -> `TX` -> `Matrix` routing. Agent-to-agent delegation within a single run uses Pydantic AI's native delegation pattern (one agent calls another as a tool).

4. **Framework changes are minimal.** Two additions to `mixin.py`: `output_type` passthrough (1 line) and `message_history` support (~4 lines). Everything else is application code in `example_grants/`.

---

## 2. Phase 1: Structured Output + Agent Memory (Week 1-2)

### Task 1.1: Structured Output — `output_type` Passthrough (Day 1)

**Goal:** Allow agents to return typed Pydantic models instead of raw text.

**Framework change:** 1 line in `/workspace/src/pybend/core/agents/mixin.py`

**File:** `/workspace/src/pybend/core/agents/mixin.py`

```python
# Line 107-112, current:
ai_agent = Agent(
    llm,
    system_prompt=prompt,
    deps_type=AgentDeps,
    tools=ai_tools,
)

# Change to:
ai_agent = Agent(
    llm,
    system_prompt=prompt,
    deps_type=AgentDeps,
    tools=ai_tools,
    output_type=kwargs.get('output_type', str),
)
```

**How it works:**
- Pydantic AI's `Agent` accepts `output_type` parameter. When set to a BaseModel subclass, the LLM is instructed to return structured JSON matching that schema.
- `result.output` becomes an instance of the output type (e.g., `ScanResult`) instead of `str`.
- The existing `return {'answer': result.output, ...}` works unchanged because `json.dumps(result, default=str)` in `AgentActor.run()` serializes any type.
- Callers that do not pass `output_type` get the default `str` behavior -- fully backward compatible.

**Handling the result in the return dict:**
The current `agent_run()` return at line 132 assigns `result.output` to `answer`. When `output_type` is a BaseModel, `result.output` is a model instance. The `json.dumps(result, default=str)` call in `AgentActor.run()` (line 156 of actor.py) handles this. However, for richer serialization, also serialize the output model:

```python
# Line 132-140, enhance the return dict:
output = result.output
return {
    'answer': output.model_dump() if hasattr(output, 'model_dump') else output,
    'usage': {
        'input_tokens': usage.input_tokens,
        'output_tokens': usage.output_tokens,
        'requests': usage.requests,
    },
    'messages': len(result.all_messages()),
}
```

This is ~3 extra lines in `mixin.py`. The serialized output retains all structure, which downstream consumers (AnalyzerMonitor, AgentRun records) can parse.

**Dependencies:** None
**Estimate:** 0.5 day (change + tests)

---

### Task 1.2: Define Structured Output Types (Day 1)

**Goal:** Create Pydantic models for typed agent outputs.

**New file:** `/workspace/example_grants/agents/output_types.py`

```python
"""Structured output types for Grant Watcher agents.

These are Pydantic BaseModel subclasses passed as output_type to agent_run().
The LLM returns JSON conforming to these schemas instead of raw text.
"""
from pydantic import BaseModel, Field


class ScanResult(BaseModel):
    """Structured output from a grant scan run."""
    grants_found: int = Field(description="Total grants identified on source pages")
    grants_created: int = Field(description="New grant records created")
    duplicates_skipped: int = Field(description="Grants skipped due to duplication")
    errors: list[str] = Field(default=[], description="Any errors encountered during scanning")
    sources_scanned: list[str] = Field(default=[], description="Source URLs that were scanned")


class AnalysisResult(BaseModel):
    """Structured output from grant analysis."""
    grant_id: int = Field(description="ID of the analyzed grant")
    relevance_score: float = Field(ge=0, le=1, description="0-1 relevance score")
    is_duplicate: bool = Field(default=False, description="Whether this is a duplicate")
    duplicate_of: int | None = Field(default=None, description="ID of the original grant if duplicate")
    days_until_deadline: int | None = Field(default=None, description="Days remaining")
    reasoning: str = Field(description="Why this score was assigned")
    recommended_action: str = Field(description="apply | watch | skip | expired")


class DigestReport(BaseModel):
    """Structured output from digest/report generation."""
    grants_summarized: int = Field(description="Number of grants in the digest")
    high_priority: list[int] = Field(default=[], description="Grant IDs flagged as high priority")
    summary: str = Field(description="Natural language digest text")
```

**Dependencies:** None (pure Pydantic models)
**Estimate:** 0.25 day

---

### Task 1.3: Agent Memory via `message_history` (Days 2-3)

**Goal:** Agents remember what they have done in previous runs by passing conversation history from `AgentRun` records.

**Prereq:** Sprint 1 must have delivered the `AgentRun` model with a `messages` field storing serialized Pydantic AI message history.

**Framework change:** ~4 lines in `/workspace/src/pybend/core/agents/mixin.py`

```python
# After line 128 (usage_limits), before line 129 (result = await ai_agent.run(...)):

# ── Message history (agent memory) ──
message_history = kwargs.get('message_history')

# ── Run ──
result = await ai_agent.run(
    task,
    deps=deps,
    usage_limits=usage_limits,
    message_history=message_history,    # <-- new parameter
)
```

**How Pydantic AI's `message_history` works:**
- `Agent.run(message_history=[...])` prepends the history before the current task.
- The LLM sees previous turns as context, enabling it to avoid re-scanning sources it already checked.
- `result.all_messages()` returns the full conversation (history + new), which gets stored in the `AgentRun.messages` field for the next run.
- `result.new_messages()` returns only messages from the current run, useful if you want to store incrementally.

**Application-level loading** (in `example_grants/`, not in framework):

The actual history loading logic belongs in `AgentActor.run()` or the instrumented run wrapper (from Sprint 1). The framework just passes it through.

```python
# In AgentActor.run() or the instrumented_run wrapper:
# Load message_history from the most recent completed AgentRun for this agent

from models.agent_run import AgentRun
from pydantic_ai.messages import ModelMessage

def _load_message_history(agent_id: int, limit: int = 1) -> list[ModelMessage] | None:
    """Load serialized message history from the most recent AgentRun."""
    runs = AgentRun.list(
        sql_filter=f"agent_id = {agent_id} AND status = 'completed'",
        limit=limit,
    )
    data = runs.get('data', []) if isinstance(runs, dict) else runs
    if not data:
        return None
    # Get the most recent run's messages
    last_run = data[-1]
    messages_raw = last_run.messages if hasattr(last_run, 'messages') else []
    if not messages_raw:
        return None
    # Deserialize back to Pydantic AI message objects
    return _deserialize_messages(messages_raw)
```

**Message serialization/deserialization:**

Pydantic AI message objects (ModelRequest, ModelResponse) are Pydantic models themselves, so they support `.model_dump()` and `.model_validate()`. The serialization utility:

**New file:** `/workspace/example_grants/agents/memory.py`

```python
"""Agent memory — message history persistence for cross-run context.

Serializes Pydantic AI messages to JSON-safe dicts for storage in
AgentRun.messages, and deserializes them back for passing as
message_history to subsequent runs.
"""
import json
import logging

logger = logging.getLogger('grants.agents')


def serialize_messages(messages: list) -> list[dict]:
    """Serialize Pydantic AI message objects to JSON-safe dicts."""
    result = []
    for msg in messages:
        if hasattr(msg, 'model_dump'):
            result.append(msg.model_dump(mode='json'))
        elif isinstance(msg, dict):
            result.append(msg)
        else:
            result.append({'type': type(msg).__name__, 'data': str(msg)})
    return result


def deserialize_messages(raw: list) -> list | None:
    """Deserialize stored message dicts back to Pydantic AI messages.

    Uses Pydantic AI's ModelRequest/ModelResponse.model_validate() for
    proper reconstruction. Falls back to raw dicts if deserialization fails
    (Pydantic AI accepts both objects and dicts as message_history).
    """
    if not raw:
        return None
    try:
        from pydantic_ai.messages import ModelRequest, ModelResponse
        messages = []
        for item in raw:
            if isinstance(item, str):
                item = json.loads(item)
            kind = item.get('kind', '')
            if kind == 'request':
                messages.append(ModelRequest.model_validate(item))
            elif kind == 'response':
                messages.append(ModelResponse.model_validate(item))
            else:
                messages.append(item)  # Pass raw dict — Pydantic AI handles it
        return messages if messages else None
    except Exception as e:
        logger.warning("Failed to deserialize message history: %s", e)
        return None


def load_history(agent_id: int, limit: int = 1):
    """Load message history from the most recent completed AgentRun.

    Args:
        agent_id: The agent whose history to load.
        limit: Number of recent runs to consider (default: 1, most recent only).

    Returns:
        List of Pydantic AI message objects, or None if no history.
    """
    try:
        from models.agent_run import AgentRun
        runs = AgentRun.list(
            sql_filter=f"agent_id = {agent_id} AND status = 'completed'",
            limit=limit,
        )
        data = runs.get('data', []) if isinstance(runs, dict) else runs
        if not data:
            return None
        last_run = data[-1]
        messages_raw = last_run.messages if hasattr(last_run, 'messages') else []
        return deserialize_messages(messages_raw)
    except Exception as e:
        logger.warning("Failed to load agent history: %s", e)
        return None
```

**Wiring into `AgentActor.run()` or instrumented wrapper:**

```python
# In the run method, before calling agent_run():
from agents.memory import load_history

message_history = load_history(self.id) if kwargs.get('use_memory', True) else None

result = await self.agent_run(
    prompt=self.prompt,
    tools=tool_addrs,
    task=task,
    message_history=message_history,
    **kwargs,
)
```

**Dependencies:** Task 1.1 (output_type), Sprint 1 AgentRun model
**Estimate:** 1.5 days (framework change + memory module + serialization + tests)

---

### Task 1.4: SamGovAPI Tool Actor (Days 3-4)

**Goal:** A non-storable ActorModel that wraps the SAM.gov Opportunities API, following the exact WebTools pattern.

**New file:** `/workspace/example_grants/models/sam_gov_api.py`

```python
"""SamGovAPI tool actor — wraps the SAM.gov Opportunities API.

Follows the WebTools pattern: non-storable ActorModel with @expose_route
methods that become agent tools via discover_tools(). Requires SAM_GOV_API_KEY
environment variable.

API docs: https://open.gsa.gov/api/get-opportunities-public-api/
Rate limits: Vary by role. Max 1-year date range per query.
"""
from __future__ import annotations
import os
from typing import ClassVar

from pybend.core.models.actor_model import ActorModel
from pybend.core.utils.decorators import expose_route
from pybend.core.authorize import AUTHENTICATED


class SamGovAPI(ActorModel):
    """Tool actor wrapping the SAM.gov Opportunities API."""

    __tablename__: ClassVar[str] = 'sam_gov_api'
    __storable__: ClassVar[bool] = False

    @expose_route('/search', methods=['POST'], access=AUTHENTICATED)
    async def search(self, keyword: str = '', posted_from: str = '',
                     posted_to: str = '', limit: int = 100) -> dict:
        """Search SAM.gov for contract/grant opportunities.

        Args:
            keyword: Search term for opportunity titles.
            posted_from: Start date (MM/dd/yyyy format).
            posted_to: End date (MM/dd/yyyy format). Max 1-year span.
            limit: Max results (up to 1000).

        Returns:
            Dict with 'total' count and 'opportunities' list.
        """
        import httpx

        api_key = os.environ.get('SAM_GOV_API_KEY', '')
        if not api_key:
            from pybend.core.utils.erroring import MethodError
            raise MethodError("SAM_GOV_API_KEY environment variable not set", 503)

        params = {
            'api_key': api_key,
            'limit': min(limit, 1000),
            'offset': 0,
        }
        if keyword:
            params['title'] = keyword
        if posted_from:
            params['postedFrom'] = posted_from
        if posted_to:
            params['postedTo'] = posted_to

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                'https://api.sam.gov/opportunities/v2/search',
                params=params,
            )
        if resp.status_code != 200:
            from pybend.core.utils.erroring import MethodError
            raise MethodError(f"SAM.gov API error: {resp.status_code}", resp.status_code)

        data = resp.json()
        return {
            'total': data.get('totalRecords', 0),
            'opportunities': data.get('opportunitiesData', [])[:limit],
        }
```

**Registration in `main.py`:**
```python
from models.sam_gov_api import SamGovAPI
# Add to models list:
models=[..., SamGovAPI]
```

**Registration in `models/__init__.py`:**
```python
from .sam_gov_api import SamGovAPI
__all__ = [..., "SamGovAPI"]
```

**Tool discovery:** Any agent listing `"sam_gov_api"` in its tools gets `sam_gov_api_search` automatically via `discover_tools()`. Zero framework changes.

**Dependencies:** None (follows existing WebTools pattern exactly)
**Estimate:** 1 day (implementation + mock tests for API responses)

---

### Task 1.5: GrantAnalyzer Tool Actor (Days 4-5)

**Goal:** Non-storable ActorModel providing grant analysis tools: duplicate detection and deadline prioritization.

**New file:** `/workspace/example_grants/models/grant_analyzer.py`

```python
"""GrantAnalyzer tool actor — grant analysis utilities.

Non-storable ActorModel with @expose_route methods that become agent
tools. Provides duplicate detection (URL hash + Levenshtein title
similarity) and deadline prioritization.
"""
from __future__ import annotations
import hashlib
from datetime import date
from typing import ClassVar

from pybend.core.models.actor_model import ActorModel
from pybend.core.utils.decorators import expose_route
from pybend.core.authorize import AUTHENTICATED


def _normalize(text: str) -> str:
    """Normalize text for comparison: lowercase, strip, collapse whitespace."""
    import re
    return re.sub(r'\s+', ' ', text.lower().strip())


def _levenshtein_ratio(s1: str, s2: str) -> float:
    """Normalized Levenshtein similarity (0.0 to 1.0). No external deps."""
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0
    n, m = len(s1), len(s2)
    if n > m:
        s1, s2 = s2, s1
        n, m = m, n
    # Single-row DP
    prev = list(range(n + 1))
    for j in range(1, m + 1):
        curr = [j] + [0] * n
        for i in range(1, n + 1):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            curr[i] = min(curr[i - 1] + 1, prev[i] + 1, prev[i - 1] + cost)
        prev = curr
    distance = prev[n]
    max_len = max(n, m)
    return 1.0 - (distance / max_len) if max_len > 0 else 1.0


class GrantAnalyzer(ActorModel):
    """Tool actor providing grant analysis capabilities."""

    __tablename__: ClassVar[str] = 'grant_analyzer'
    __storable__: ClassVar[bool] = False

    @expose_route('/find_duplicates', methods=['POST'], access=AUTHENTICATED)
    def find_duplicates(self, title: str, url: str = '') -> dict:
        """Check if a grant with similar title or URL already exists.

        Uses URL hash for exact match and normalized Levenshtein for
        title similarity (threshold 0.85).

        Args:
            title: Grant title to check.
            url: Grant URL to check (optional).

        Returns:
            Dict with 'duplicates' list and 'is_duplicate' boolean.
        """
        from models.grant import Grant

        existing = Grant.list(limit=500)
        items = existing.get('data', []) if isinstance(existing, dict) else existing
        matches = []

        url_hash = hashlib.sha256(url.encode()).hexdigest()[:16] if url else ''
        norm_title = _normalize(title)

        for g in items:
            grant = g.model_response() if hasattr(g, 'model_response') else g

            # Exact URL match
            if url and grant.get('url', '').rstrip('/') == url.rstrip('/'):
                matches.append({
                    'id': grant.get('id'),
                    'title': grant.get('title', ''),
                    'match_type': 'url_exact',
                    'score': 1.0,
                })
                continue

            # Title similarity
            existing_title = _normalize(grant.get('title', ''))
            sim = _levenshtein_ratio(norm_title, existing_title)
            if sim > 0.85:
                matches.append({
                    'id': grant.get('id'),
                    'title': grant.get('title', ''),
                    'match_type': 'title_similarity',
                    'score': round(sim, 3),
                })

        return {'duplicates': matches, 'is_duplicate': len(matches) > 0}

    @expose_route('/prioritize_deadlines', methods=['POST'], access=AUTHENTICATED)
    def prioritize_deadlines(self, limit: int = 20) -> dict:
        """Rank discovered grants by deadline urgency.

        Returns grants sorted by days remaining, excluding expired ones.

        Args:
            limit: Max grants to return (default 20).

        Returns:
            Dict with 'ranked_grants' list sorted by days_until_deadline.
        """
        from models.grant import Grant

        grants = Grant.list(limit=200)
        items = grants.get('data', []) if isinstance(grants, dict) else grants
        today = date.today()
        ranked = []

        for g in items:
            grant = g.model_response() if hasattr(g, 'model_response') else g
            deadline = grant.get('deadline')
            if not deadline:
                continue
            try:
                days_left = (date.fromisoformat(str(deadline)) - today).days
                if days_left > 0:
                    ranked.append({
                        'id': grant.get('id'),
                        'title': grant.get('title', ''),
                        'agency': grant.get('agency', ''),
                        'deadline': str(deadline),
                        'days_until_deadline': days_left,
                        'status': grant.get('status', ''),
                    })
            except (ValueError, TypeError):
                continue

        ranked.sort(key=lambda x: x['days_until_deadline'])
        return {'ranked_grants': ranked[:limit]}

    @expose_route('/score_relevance', methods=['POST'], access=AUTHENTICATED)
    def score_relevance(self, grant_id: int) -> dict:
        """Basic relevance scoring for a grant based on completeness and deadline.

        This is a heuristic scorer, not an LLM-based scorer. The LLM-based
        scoring happens when the Analyzer agent uses this tool alongside its
        own reasoning.

        Args:
            grant_id: ID of the grant to score.

        Returns:
            Dict with 'score' (0-1), 'factors' dict, and 'recommendation'.
        """
        from models.grant import Grant

        grant = Grant.get(grant_id)
        if not grant:
            from pybend.core.utils.erroring import MethodError
            raise MethodError(f"Grant {grant_id} not found", 404)

        grant_data = grant.model_response() if hasattr(grant, 'model_response') else {}
        factors = {}
        score = 0.0

        # Factor 1: Completeness (0-0.3)
        fields_present = sum(1 for f in ['title', 'agency', 'deadline', 'url', 'description',
                                          'amount_min', 'amount_max']
                             if grant_data.get(f))
        completeness = fields_present / 7
        factors['completeness'] = round(completeness, 2)
        score += completeness * 0.3

        # Factor 2: Deadline proximity (0-0.4) — closer = more urgent = higher score
        deadline = grant_data.get('deadline')
        if deadline:
            try:
                days = (date.fromisoformat(str(deadline)) - date.today()).days
                if days <= 0:
                    factors['deadline'] = 0.0  # expired
                elif days <= 30:
                    factors['deadline'] = 1.0  # urgent
                    score += 0.4
                elif days <= 90:
                    factors['deadline'] = 0.6
                    score += 0.24
                else:
                    factors['deadline'] = 0.3
                    score += 0.12
            except (ValueError, TypeError):
                factors['deadline'] = 0.0
        else:
            factors['deadline'] = 0.0

        # Factor 3: Has funding amounts (0-0.3)
        has_amounts = bool(grant_data.get('amount_min') or grant_data.get('amount_max'))
        factors['funding_info'] = 1.0 if has_amounts else 0.0
        score += 0.3 if has_amounts else 0.0

        score = round(min(score, 1.0), 2)
        recommendation = 'apply' if score >= 0.7 else ('watch' if score >= 0.4 else 'skip')

        return {
            'grant_id': grant_id,
            'score': score,
            'factors': factors,
            'recommendation': recommendation,
        }
```

**Registration:** Same pattern as SamGovAPI -- add to `models/__init__.py`, `main.py` models list.

**Tool discovery:** Agents with `"grant_analyzer"` in tools get:
- `grant_analyzer_find_duplicates`
- `grant_analyzer_prioritize_deadlines`
- `grant_analyzer_score_relevance`

**Dependencies:** Task 1.1 (for structured output from Analyzer agent), Grant model
**Estimate:** 1.5 days (implementation + unit tests for scoring/dedup algorithms)

---

### Phase 1 Summary

| Task | Files Changed/Created | Framework Changes | Estimate |
|------|----------------------|-------------------|----------|
| 1.1 output_type | `mixin.py` (3-4 lines) | Yes (1 line + output serialization) | 0.5d |
| 1.2 Output types | `example_grants/agents/output_types.py` (new) | No | 0.25d |
| 1.3 message_history | `mixin.py` (4 lines), `example_grants/agents/memory.py` (new) | Yes (passthrough only) | 1.5d |
| 1.4 SamGovAPI | `example_grants/models/sam_gov_api.py` (new), `main.py`, `__init__.py` | No | 1d |
| 1.5 GrantAnalyzer | `example_grants/models/grant_analyzer.py` (new), `main.py`, `__init__.py` | No | 1.5d |
| **Total Phase 1** | | **~8 lines in framework** | **~5 days** |

---

## 3. Phase 2: Multi-Agent Pipeline (Week 3-4)

### Task 2.1: Agent Specialization via DB Records (Day 1)

**Goal:** Create 3-4 specialized agent instances as database records. No new Python classes. The agents differ only in their `prompt`, `llm`, and `tools` fields.

**This is the "agents are data, not code" payoff.** Each agent type is a `POST /agents` call (or a seed script entry), not a new Python class.

**File to modify:** `/workspace/example_grants/seed.py` (add agent records)

Agent definitions:

```python
# 1. Scanner Agent (already exists from Sprint 0)
# Just verify its tools include grants_gov_api and sam_gov_api

# 2. Analyzer Agent (NEW)
analyzer_agent = AgentActor(
    name="Grant Analyzer",
    prompt=(
        "You analyze newly discovered grants for relevance and quality. "
        "For each grant, check for duplicates using find_duplicates, "
        "score its relevance using score_relevance, and update the grant "
        "status based on your analysis. If a grant is a duplicate, update "
        "its status to 'duplicate'. If it scores above 0.7, update status "
        "to 'reviewed'. Use prioritize_deadlines to identify urgent grants."
    ),
    llm="anthropic:claude-sonnet-4-5-20250929",
    constraints={"max_iterations": 15},
)
# Tools: grants (CRUD), grant_analyzer (scoring/dedup)

# 3. Reporter Agent (NEW)
reporter_agent = AgentActor(
    name="Grant Reporter",
    prompt=(
        "You generate digest reports of recently discovered grants. "
        "List grants, identify high-priority ones (high relevance score, "
        "approaching deadlines), and produce a concise summary suitable "
        "for email notification."
    ),
    llm="anthropic:claude-sonnet-4-5-20250929",
    constraints={"max_iterations": 10},
)
# Tools: grants (CRUD), notification_tools (future Phase 3)

# 4. Matcher Agent (from Sprint 3, if not already present)
# Tools: grants, grant_match, matcher_tools
```

**Seed script additions:**

```python
def _seed_analyzer_agent():
    agent = AgentActor(
        name="Grant Analyzer",
        prompt="You analyze newly discovered grants...",  # full prompt above
        llm="anthropic:claude-sonnet-4-5-20250929",
        constraints={"max_iterations": 15},
    )
    created = AgentActor.create(agent)
    # Link tools via join table
    for target, desc in [
        ("grants", "Grant CRUD operations"),
        ("grant_analyzer", "Scoring, dedup, deadline tools"),
    ]:
        record = join_cls(**{"target": target, "description": desc,
                            "agentactor_id": created.id})
        join_cls.create(record)
    return created
```

**Dependencies:** Task 1.5 (GrantAnalyzer must exist for Analyzer agent's tools)
**Estimate:** 0.5 day

---

### Task 2.2: AnalyzerMonitor Actor (Days 2-4)

**Goal:** A lightweight Actor that subscribes to Grant lifecycle events and triggers the Analyzer agent when new grants are created.

#### Design Decision: Actor, ActorModel, or ActorProxy?

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| `Actor` instance | Simplest. No storage, no schema, no routes. Exactly what we need. | Must register manually. No CRUD. | **Use this.** |
| `ActorModel` | Gets schema/routes for free. | Overkill -- monitor has no data to store or expose. | No. |
| `ActorProxy` | Wraps a plain class. | More indirection than needed -- we want the Actor interface directly. | No. |

**The AnalyzerMonitor is a plain Actor instance** with a custom `handler()`. It has one job: receive LIFECYCLE TXs and invoke the Analyzer agent.

**New file:** `/workspace/example_grants/actors/analyzer_monitor.py`

```python
"""AnalyzerMonitor — event-driven bridge between Grant lifecycle and Analyzer agent.

A lightweight Actor (not ActorModel) that subscribes to Grant._subscribers.
When a Grant is created, it loads the Analyzer agent from the DB and triggers
an analysis run.

This is the thinnest possible glue between lifecycle events and agent runs.
No storage, no schema, no routes — just event handling.

Wiring (in main.py):
    from actors.analyzer_monitor import AnalyzerMonitor
    from pybend.core.actors.matrix import matrix

    monitor = AnalyzerMonitor(addr='analyzer_monitor')
    matrix.register(monitor)
    Grant._subscribers.append('analyzer_monitor')
"""
import asyncio
import logging

from pybend.core.actors.actor import Actor
from pybend.core.actors.tx import TX

logger = logging.getLogger('grants.monitor')

# Default: Analyzer agent is the second AgentActor created (id=2).
# Override via ANALYZER_AGENT_ID env var or by passing to constructor.
_DEFAULT_ANALYZER_ID = 2


class AnalyzerMonitor(Actor, auto_register=False):
    """Listens for Grant lifecycle events, triggers analysis pipeline.

    Handles:
        LIFECYCLE TX with event='after_create' -> triggers Analyzer agent
        LIFECYCLE TX with event='after_update' -> (future: re-score on significant changes)
    """

    def __init__(self, analyzer_agent_id: int = None, **kwargs):
        super().__init__(**kwargs)
        # Store as plain attribute (not Pydantic field — Actor is a PydanticBaseModel
        # but we use object.__setattr__ to avoid Pydantic field declaration)
        object.__setattr__(self, '_analyzer_agent_id',
                           analyzer_agent_id or _DEFAULT_ANALYZER_ID)

    async def handler(self, tx: TX) -> None:
        """Dispatch LIFECYCLE events to the appropriate handler."""
        if tx.name != 'LIFECYCLE':
            # Not our concern -- drop silently (don't error, don't bounce)
            logger.debug("[AnalyzerMonitor] Ignoring non-LIFECYCLE TX: %s", tx.name)
            return

        event = tx.data.get('event', '')
        entity = tx.data.get('entity', {})

        if event == 'after_create':
            await self._on_grant_created(entity, tx)
        elif event == 'after_update':
            # Future: re-analyze on significant field changes
            pass
        elif event == 'after_delete':
            # Nothing to analyze for deleted grants
            pass

    async def _on_grant_created(self, entity: dict, tx: TX) -> None:
        """A new Grant was created -- trigger the Analyzer agent.

        Loads the Analyzer agent from DB, constructs a task prompt with
        the new grant's details, and fires agent.run() as a background task.
        The analysis result (score, duplicate check, status update) is
        handled by the agent via its tools.

        Fire-and-forget: the Scanner does not wait for analysis to complete.
        """
        grant_id = entity.get('id')
        grant_title = entity.get('title', 'Unknown')

        if not grant_id:
            logger.warning("[AnalyzerMonitor] LIFECYCLE entity missing 'id'")
            return

        logger.info(
            "[AnalyzerMonitor] New grant created: #%s '%s' — triggering analysis",
            grant_id, grant_title,
        )

        try:
            from pybend.core.agents.actor import AgentActor

            analyzer_id = object.__getattribute__(self, '_analyzer_agent_id')
            analyzer = AgentActor.get(analyzer_id)

            if not analyzer:
                logger.error(
                    "[AnalyzerMonitor] Analyzer agent (id=%d) not found in DB. "
                    "Create it via POST /agents or seed.py.",
                    analyzer_id,
                )
                return

            # Build task prompt with grant context
            task = (
                f"Analyze the newly discovered grant:\n"
                f"- ID: {grant_id}\n"
                f"- Title: {grant_title}\n"
                f"- Agency: {entity.get('agency', 'Unknown')}\n"
                f"- Deadline: {entity.get('deadline', 'Not specified')}\n"
                f"- URL: {entity.get('url', 'N/A')}\n\n"
                f"Steps:\n"
                f"1. Check for duplicates using find_duplicates with the title and URL.\n"
                f"2. Score the grant's relevance using score_relevance.\n"
                f"3. If it is a duplicate, update the grant status to 'duplicate'.\n"
                f"4. If the relevance score is >= 0.7, update status to 'reviewed'.\n"
                f"5. Report your findings."
            )

            # Fire-and-forget: run analysis in background
            asyncio.create_task(
                self._run_analyzer(analyzer, task, grant_id)
            )

        except Exception as e:
            logger.error("[AnalyzerMonitor] Failed to trigger analysis: %s", e)

    async def _run_analyzer(self, analyzer, task: str, grant_id: int) -> None:
        """Execute the analyzer agent run with error handling."""
        try:
            result = await analyzer.run(task=task)
            logger.info(
                "[AnalyzerMonitor] Analysis complete for grant #%d: %s",
                grant_id, result[:200] if isinstance(result, str) else str(result)[:200],
            )
        except Exception as e:
            logger.error(
                "[AnalyzerMonitor] Analysis failed for grant #%d: %s",
                grant_id, e,
            )
```

**Key design choices:**

1. **`auto_register=False`** -- must be registered manually via `matrix.register()`. This prevents auto-registration at class definition time (before Matrix is ready).

2. **Fire-and-forget via `asyncio.create_task()`** -- the monitor does not block waiting for the Analyzer agent to complete. This matches `_publish_lifecycle()`'s own fire-and-forget pattern.

3. **`object.__setattr__`** for `_analyzer_agent_id` -- Actor extends PydanticBaseModel, which intercepts `__setattr__`. Using `object.__setattr__` bypasses Pydantic's field validation for this runtime-only attribute (same pattern as the mock_method utility in tests).

4. **No storage, no schema** -- the monitor is ephemeral. If the server restarts, it is re-created in `main.py`. There is nothing to persist.

5. **Agent ID from DB** -- the monitor does NOT hold a reference to the AgentActor instance. It loads it fresh from the DB on each event. This ensures it always gets the latest prompt/tools/constraints.

**Dependencies:** Task 2.1 (Analyzer agent must exist in DB)
**Estimate:** 1.5 days (implementation + integration tests)

---

### Task 2.3: Subscriber Wiring (Day 4)

**Goal:** Connect Grant lifecycle events to the AnalyzerMonitor.

**File to modify:** `/workspace/example_grants/main.py`

```python
# After create_app() and storage setup:

from pybend.core.actors.matrix import matrix
from actors.analyzer_monitor import AnalyzerMonitor
from models import Grant

# Register the analysis pipeline monitor
monitor = AnalyzerMonitor(addr='analyzer_monitor', analyzer_agent_id=2)
matrix.register(monitor)

# Subscribe Grant model to the monitor
# When Grant.create() runs in handler_crud(), _publish_lifecycle('after_create', ...)
# sends a LIFECYCLE TX to 'analyzer_monitor', which arrives at monitor.handler()
Grant._subscribers.append('analyzer_monitor')
```

**Full TX flow for a new grant:**

```
1. Scanner Agent calls grants_create via tool call
   -> _route_tool_call() creates TX(name='create', target='grants', data={title, agency, ...})
   -> adapter.request(tx) sends TX to Matrix

2. Matrix routes to Grant class (registered child at 'grants')
   -> Grant.inbox(tx) -> Grant.handler(tx)
   -> handler_crud() handles 'create': Grant.create(instance)
   -> SQLite INSERT

3. handler_crud() calls _publish_lifecycle('after_create', result.model_response())
   -> asyncio.create_task(cls.send(TX(
        name='LIFECYCLE',
        source='grants',
        target='analyzer_monitor',
        data={'event': 'after_create', 'entity': {id, title, agency, ...}}
      )))

4. Matrix routes LIFECYCLE TX to analyzer_monitor (registered child)
   -> AnalyzerMonitor.inbox(tx) -> AnalyzerMonitor.handler(tx)
   -> handler sees event='after_create'
   -> _on_grant_created() loads AgentActor.get(2) from DB
   -> asyncio.create_task(_run_analyzer(analyzer, task, grant_id))

5. Analyzer agent's run() calls agent_run() with its own tools
   -> discover_tools(['grants', 'grant_analyzer']) finds:
      grants_list, grants_get, grants_update, ...
      grant_analyzer_find_duplicates, grant_analyzer_score_relevance, ...
   -> LLM executes analysis loop:
      a. Calls grant_analyzer_find_duplicates({title, url})
         -> TX to grant_analyzer -> GrantAnalyzer.find_duplicates()
         -> Returns {duplicates: [...], is_duplicate: false}
      b. Calls grant_analyzer_score_relevance({grant_id})
         -> TX to grant_analyzer -> GrantAnalyzer.score_relevance()
         -> Returns {score: 0.72, recommendation: 'apply'}
      c. Calls grants_update({id, status: 'reviewed'})
         -> TX to grants -> Grant.handler_crud() update
         -> Grant record updated in SQLite

6. Analyzer agent returns AnalysisResult (if output_type is set)
   -> AnalyzerMonitor logs result
   -> (Future: if score > threshold, trigger Reporter agent)
```

**Dependencies:** Task 2.2 (AnalyzerMonitor), Grant model
**Estimate:** 0.5 day (wiring + integration test for full lifecycle chain)

---

### Task 2.4: Pydantic AI Agent Delegation (Days 5-6)

**Goal:** Enable one agent to delegate to another within a single run via tool calls. This complements the event-driven coordination (Task 2.2-2.3) with synchronous in-run delegation.

**Use case:** The Scanner agent, during a single scan run, wants to check if a grant is a duplicate BEFORE creating it. Instead of creating the grant and then having the AnalyzerMonitor trigger a separate analysis run, the Scanner calls the Analyzer as a tool within its own run.

**How Pydantic AI delegation works:**
Pydantic AI supports calling another agent as a tool within a parent agent's run. The child agent's run is fully nested -- it uses its own tools, prompt, and LLM, but its token usage is aggregated with the parent.

**Implementation approach:** Create a delegation tool that the Scanner can call. This tool internally loads and runs the Analyzer agent.

**New file:** `/workspace/example_grants/agents/delegation.py`

```python
"""Agent delegation — tools that allow one agent to invoke another.

These are standard Pydantic AI tool functions that internally load an
AgentActor from the DB and call agent_run(). The parent agent sees them
as regular tools; the child agent runs with its own prompt/tools/LLM.

Usage:
    # In the Scanner agent's tool set, add:
    from agents.delegation import create_delegation_tools
    delegation_tools = create_delegation_tools()
    # These get added to the Scanner's ai_tools list
"""
import json
import logging
from pydantic_ai.tools import Tool

logger = logging.getLogger('grants.delegation')


def create_analyze_grant_tool():
    """Create a tool that delegates grant analysis to the Analyzer agent.

    Returns a Pydantic AI Tool that the Scanner agent can call to analyze
    a grant inline (within the same run) rather than waiting for the
    event-driven pipeline.
    """
    async def analyze_grant(ctx, grant_id: int) -> str:
        """Delegate grant analysis to the Analyzer agent.

        Loads the Analyzer agent from DB and runs it with a focused task.
        Returns the analysis result as JSON.
        """
        from pybend.core.agents.actor import AgentActor

        analyzer = AgentActor.get(2)  # Analyzer agent ID
        if not analyzer:
            return json.dumps({"error": "Analyzer agent not found"})

        try:
            result_str = await analyzer.run(
                task=f"Analyze grant {grant_id}: check duplicates and score relevance.",
            )
            return result_str
        except Exception as e:
            logger.error("Delegation to Analyzer failed: %s", e)
            return json.dumps({"error": str(e)})

    return Tool(
        function=analyze_grant,
        takes_ctx=True,
        name='delegate_analyze',
        description='Delegate grant analysis to the Analyzer agent (checks duplicates, scores relevance)',
    )
```

**Wiring delegation tools into agent_run():**

Delegation tools are NOT wired at the framework level. They are additional tools that the application adds to specific agent runs. Two options:

**Option A: Add via the Scanner agent's tool list (simplest)**

The Scanner agent's tools in the DB include `grants`, `sources`, `web_tools`, `grants_gov_api`. Delegation tools are NOT Matrix-routed actors, so they cannot be discovered via `discover_tools()`. Instead, they are passed directly as additional `ai_tools`:

```python
# In AgentActor.run() or the app-level wrapper:
from agents.delegation import create_analyze_grant_tool

extra_tools = [create_analyze_grant_tool()]
# Pass as a kwarg that agent_run() forwards to ai_tools
```

This requires a small addition to `agent_run()` -- an `extra_tools` kwarg:

```python
# In mixin.py, after ai_tools = [make_tool(spec) for spec in tool_specs]:
extra_tools = kwargs.get('extra_tools', [])
ai_tools.extend(extra_tools)
```

This is 2 lines in the framework -- additive, backward compatible.

**Option B: Register delegation as a tool actor (no framework change)**

Create a non-storable `DelegationTools` ActorModel with `@expose_route` methods for each delegation. Then it works like any other tool actor. However, this adds indirection -- the delegation method would need to load the target agent and call `agent_run()` within an `@expose_route` method, which is awkward because `expose_route` methods are dispatched by the actor handler, not by the Pydantic AI agent.

**Recommendation: Option A.** The `extra_tools` kwarg is cleaner and the 2-line framework change is trivial.

**Dependencies:** Task 1.5 (GrantAnalyzer), Task 2.1 (Analyzer agent in DB)
**Estimate:** 1.5 days (delegation module + extra_tools kwarg + tests)

---

### Phase 2 Summary

| Task | Files Changed/Created | Framework Changes | Estimate |
|------|----------------------|-------------------|----------|
| 2.1 Agent records | `seed.py` | No | 0.5d |
| 2.2 AnalyzerMonitor | `example_grants/actors/analyzer_monitor.py` (new) | No | 1.5d |
| 2.3 Subscriber wiring | `main.py` (3 lines) | No | 0.5d |
| 2.4 Agent delegation | `example_grants/agents/delegation.py` (new), `mixin.py` (2 lines) | Yes (extra_tools kwarg) | 1.5d |
| **Total Phase 2** | | **2 lines in framework** | **~4 days** |

---

## 4. Phase 3: Advanced Capabilities (Week 5-6)

### Task 3.1: DocumentTools Actor (Days 1-3)

**Goal:** PDF parsing and HTML FOA extraction for grant documents.

**New file:** `/workspace/example_grants/models/document_tools.py`

```python
"""DocumentTools tool actor — PDF parsing and HTML extraction.

Non-storable ActorModel with @expose_route methods for document processing.
Uses pymupdf (fitz) for PDF parsing and BeautifulSoup for HTML extraction.

Dependencies: pip install pymupdf (or pdfplumber as fallback)
"""
from __future__ import annotations
from typing import ClassVar

from pybend.core.models.actor_model import ActorModel
from pybend.core.utils.decorators import expose_route
from pybend.core.authorize import AUTHENTICATED


class DocumentTools(ActorModel):
    """Tool actor providing document processing capabilities."""

    __tablename__: ClassVar[str] = 'document_tools'
    __storable__: ClassVar[bool] = False

    @expose_route('/parse_pdf', methods=['POST'], access=AUTHENTICATED)
    async def parse_pdf(self, url: str, max_pages: int = 20) -> dict:
        """Download a PDF from URL and extract its text content.

        Args:
            url: URL to the PDF document.
            max_pages: Maximum pages to extract (default 20).

        Returns:
            Dict with 'pages' count, 'text' content, and 'metadata'.
        """
        import httpx

        # Download PDF
        async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
            resp = await client.get(url)

        if resp.status_code != 200:
            from pybend.core.utils.erroring import MethodError
            raise MethodError(f"Failed to download PDF: HTTP {resp.status_code}", resp.status_code)

        content_type = resp.headers.get('content-type', '')
        if 'pdf' not in content_type and not url.lower().endswith('.pdf'):
            from pybend.core.utils.erroring import MethodError
            raise MethodError(f"URL does not appear to be a PDF: {content_type}", 400)

        try:
            import fitz  # pymupdf
            doc = fitz.open(stream=resp.content, filetype="pdf")
            pages_text = []
            for i, page in enumerate(doc):
                if i >= max_pages:
                    break
                pages_text.append(page.get_text())
            metadata = doc.metadata or {}
            doc.close()
            return {
                'pages': len(pages_text),
                'total_pages': doc.page_count if hasattr(doc, 'page_count') else len(pages_text),
                'text': '\n\n--- Page Break ---\n\n'.join(pages_text),
                'metadata': {
                    'title': metadata.get('title', ''),
                    'author': metadata.get('author', ''),
                    'subject': metadata.get('subject', ''),
                },
            }
        except ImportError:
            # Fallback: return raw bytes info
            return {
                'pages': 0,
                'text': f'[PDF parsing unavailable — install pymupdf. File size: {len(resp.content)} bytes]',
                'metadata': {},
            }

    @expose_route('/extract_foa', methods=['POST'], access=AUTHENTICATED)
    def extract_foa(self, html: str) -> dict:
        """Extract structured Funding Opportunity Announcement data from HTML.

        Looks for common FOA patterns: opportunity number, agency, dates,
        eligibility, funding amounts.

        Args:
            html: Raw HTML content of a grant listing page.

        Returns:
            Dict with extracted structured fields.
        """
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, 'html.parser')
        text = soup.get_text(separator='\n', strip=True)

        # Extract structured data via common patterns
        import re
        result = {
            'title': '',
            'opportunity_number': '',
            'agency': '',
            'posted_date': '',
            'close_date': '',
            'award_ceiling': '',
            'award_floor': '',
            'eligible_applicants': '',
            'description': '',
            'full_text_length': len(text),
        }

        # Title: usually the first h1 or h2
        title_el = soup.find(['h1', 'h2'])
        if title_el:
            result['title'] = title_el.get_text(strip=True)

        # Opportunity number patterns
        opp_match = re.search(r'(?:Opportunity|Funding)\s*(?:Number|#)[:\s]*([A-Z0-9-]+)', text, re.I)
        if opp_match:
            result['opportunity_number'] = opp_match.group(1)

        # Date patterns (MM/DD/YYYY or YYYY-MM-DD)
        dates = re.findall(r'\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2}', text)
        if len(dates) >= 2:
            result['posted_date'] = dates[0]
            result['close_date'] = dates[-1]
        elif len(dates) == 1:
            result['close_date'] = dates[0]

        # Truncate description to first 2000 chars of body text
        result['description'] = text[:2000]

        return result
```

**New dependency:** `pymupdf` (or `pdfplumber`). Add to `example_grants/requirements.txt`.

**Registration:** Add `DocumentTools` to models list in `main.py` and `models/__init__.py`.

**Dependencies:** None (independent tool actor)
**Estimate:** 2 days (implementation + PDF download mocking in tests)

---

### Task 3.2: Deduplication Memory — SeenGrant Model (Days 4-5)

**Goal:** A simple storable model that records URL hashes and title fingerprints. The Scanner agent checks `check_seen()` before creating grants, preventing duplicates at the source.

**Design:** This is a storable ActorModel (not a tool actor). It stores seen-grant fingerprints with hash-based lookup. The GrantAnalyzer's `find_duplicates()` provides post-hoc fuzzy matching; SeenGrant provides pre-creation exact matching.

**New file:** `/workspace/example_grants/models/seen_grant.py`

```python
"""SeenGrant — deduplication memory for the scanner pipeline.

Stores URL hashes and title fingerprints for grants the system has
already processed. The Scanner agent checks check_seen() before calling
grants_create, preventing duplicate grant records at the source.

This is a hash-based, not semantic, deduplication layer. It catches the
80% case: the same URL or very similar title appearing in subsequent scans.
For fuzzy matching, see GrantAnalyzer.find_duplicates().
"""
from __future__ import annotations
import hashlib
from typing import ClassVar, Optional
from pydantic import Field

from pybend.core.models.actor_model import ActorModel
from pybend.core.utils.decorators import expose_route
from pybend.core.authorize import AUTHENTICATED


class SeenGrant(ActorModel):
    """A fingerprint record for a previously seen grant."""

    __tablename__: ClassVar[str] = 'seen_grants'
    __storable__: ClassVar[bool] = True
    __access__: ClassVar[dict] = {
        'read': AUTHENTICATED,
        'create': AUTHENTICATED,
        'update': AUTHENTICATED,
        'delete': AUTHENTICATED,
    }

    url_hash: str = Field(max_length=64, description="SHA-256 hash of the normalized URL")
    title_fingerprint: str = Field(max_length=64, description="SHA-256 hash of the normalized title")
    original_url: str = Field(default='', description="Original URL for debugging")
    original_title: str = Field(default='', max_length=500, description="Original title for debugging")
    first_seen_at: str = Field(default='', description="ISO timestamp of first encounter")
    grant_id: Optional[int] = Field(default=None, description="FK to the created Grant record, if any")

    @expose_route('/check_seen', methods=['POST'], access=AUTHENTICATED)
    def check_seen(self, url: str = '', title: str = '') -> dict:
        """Check if a grant with this URL or title has been seen before.

        Args:
            url: Grant URL to check.
            title: Grant title to check.

        Returns:
            Dict with 'seen' boolean and 'matches' list.
        """
        matches = []

        if url:
            url_hash = _hash_url(url)
            existing = SeenGrant.list(sql_filter=f"url_hash = '{url_hash}'", limit=1)
            data = existing.get('data', []) if isinstance(existing, dict) else existing
            if data:
                matches.append({
                    'match_type': 'url',
                    'url_hash': url_hash,
                    'original_title': getattr(data[0], 'original_title', ''),
                    'grant_id': getattr(data[0], 'grant_id', None),
                })

        if title and not matches:  # Skip title check if URL already matched
            title_fp = _hash_title(title)
            existing = SeenGrant.list(sql_filter=f"title_fingerprint = '{title_fp}'", limit=1)
            data = existing.get('data', []) if isinstance(existing, dict) else existing
            if data:
                matches.append({
                    'match_type': 'title',
                    'title_fingerprint': title_fp,
                    'original_title': getattr(data[0], 'original_title', ''),
                    'grant_id': getattr(data[0], 'grant_id', None),
                })

        return {'seen': len(matches) > 0, 'matches': matches}

    @expose_route('/record_seen', methods=['POST'], access=AUTHENTICATED)
    def record_seen(self, url: str, title: str, grant_id: int = None) -> dict:
        """Record a grant as seen in the deduplication memory.

        Args:
            url: Grant URL.
            title: Grant title.
            grant_id: ID of the created Grant record (optional).

        Returns:
            Dict with the created SeenGrant record ID.
        """
        from datetime import datetime, timezone

        record = SeenGrant(
            url_hash=_hash_url(url),
            title_fingerprint=_hash_title(title),
            original_url=url,
            original_title=title[:500],
            first_seen_at=datetime.now(timezone.utc).isoformat(),
            grant_id=grant_id,
        )
        created = SeenGrant.create(record)
        return {'id': created.id, 'url_hash': record.url_hash}


def _hash_url(url: str) -> str:
    """Normalize and hash a URL."""
    normalized = url.lower().rstrip('/').strip()
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def _hash_title(title: str) -> str:
    """Normalize and hash a title."""
    import re
    normalized = re.sub(r'\s+', ' ', title.lower().strip())
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]
```

**Scanner agent prompt update:** Modify the Scanner agent's prompt in the seed script to include deduplication instructions:

```
"Before creating a grant, always call seen_grants_check_seen with the URL
and title. If it returns seen=true, skip creation. After creating a grant,
call seen_grants_record_seen to record it in the deduplication memory."
```

**Scanner agent tools update:** Add `seen_grants` to the Scanner agent's tool list.

**Registration:** Add `SeenGrant` to models list in `main.py` and `models/__init__.py`.

**Dependencies:** None
**Estimate:** 1.5 days (model + tools + Scanner prompt update + tests)

---

### Task 3.3: Agent Constraints Refinement (Day 6)

**Goal:** Extend the `constraints` field schema with retry/timeout/backoff settings that `agent_run()` reads and applies.

**Current state:** The `constraints` dict on `AgentActor` has one known key: `max_iterations` (mapped to `UsageLimits.request_limit`).

**New keys:**

| Key | Type | Default | Effect |
|-----|------|---------|--------|
| `max_iterations` | int | None | `UsageLimits(request_limit=N)` -- existing |
| `max_tokens` | int | None | `UsageLimits(response_tokens_limit=N)` -- Pydantic AI native |
| `tool_retries` | int | 3 | `Tool(retries=N)` -- per-tool retry on ModelRetry |
| `timeout` | float | 30.0 | `adapter.request(tx, timeout=N)` for tool calls |
| `run_timeout` | float | 300.0 | Overall `asyncio.wait_for(agent.run(), timeout=N)` |

**Framework change in `mixin.py`:**

```python
# After usage_limits setup (line ~127):

# ── Tool retries ──
tool_retries = constraints.get('tool_retries', 3)
# Apply to each tool
for tool in ai_tools:
    tool.max_retries = tool_retries

# ── Run timeout ──
run_timeout = constraints.get('run_timeout', 300.0)

# ── Usage limits (enhanced) ──
usage_limits = None
if constraints.get('max_iterations') or constraints.get('max_tokens'):
    usage_limits = UsageLimits(
        request_limit=constraints.get('max_iterations'),
        response_tokens_limit=constraints.get('max_tokens'),
    )

# ── Run with timeout ──
try:
    result = await asyncio.wait_for(
        ai_agent.run(task, deps=deps, usage_limits=usage_limits,
                     message_history=message_history),
        timeout=run_timeout,
    )
except asyncio.TimeoutError:
    return {
        'answer': f'Agent run timed out after {run_timeout}s',
        'usage': {'input_tokens': 0, 'output_tokens': 0, 'requests': 0},
        'messages': 0,
        'error': 'timeout',
    }
```

This is ~15 lines in `mixin.py`. The existing `max_iterations` behavior is unchanged. New keys are additive.

**Dependencies:** None
**Estimate:** 0.5 day (implementation + tests for timeout/retry behavior)

---

### Phase 3 Summary

| Task | Files Changed/Created | Framework Changes | Estimate |
|------|----------------------|-------------------|----------|
| 3.1 DocumentTools | `example_grants/models/document_tools.py` (new) | No | 2d |
| 3.2 SeenGrant | `example_grants/models/seen_grant.py` (new), `main.py`, seed.py | No | 1.5d |
| 3.3 Constraints | `mixin.py` (~15 lines) | Yes | 0.5d |
| **Total Phase 3** | | **~15 lines in framework** | **~4 days** |

---

## 5. Test Strategy

### 5.1. Unit Tests for Tool Actors

Each tool actor gets its own test file. Tests use real DB fixtures (same as existing `conftest.py` pattern) but mock external HTTP calls.

**File:** `/workspace/example_grants/tests/test_grant_analyzer.py`

```python
"""Tests for GrantAnalyzer tool actor methods."""
import pytest
from models.grant_analyzer import GrantAnalyzer, _levenshtein_ratio, _normalize


class TestLevenshteinRatio:
    def test_identical(self):
        assert _levenshtein_ratio("hello", "hello") == 1.0

    def test_completely_different(self):
        assert _levenshtein_ratio("abc", "xyz") < 0.5

    def test_similar_titles(self):
        s1 = _normalize("CISE Research Infrastructure: Discovery")
        s2 = _normalize("CISE Research Infrastructure: Discovery Program")
        assert _levenshtein_ratio(s1, s2) > 0.85

    def test_empty_strings(self):
        assert _levenshtein_ratio("", "") == 1.0
        assert _levenshtein_ratio("abc", "") == 0.0


class TestFindDuplicates:
    def test_no_duplicates(self, test_db, seed_data):
        result = GrantAnalyzer().find_duplicates(
            title="Completely Unique Grant Title XYZ123",
            url="https://example.com/unique-grant",
        )
        assert result['is_duplicate'] is False
        assert result['duplicates'] == []

    def test_exact_url_match(self, test_db, seed_data):
        result = GrantAnalyzer().find_duplicates(
            title="Different Title",
            url="https://nsf.gov/example-cise",  # matches seed grant
        )
        assert result['is_duplicate'] is True
        assert result['duplicates'][0]['match_type'] == 'url_exact'

    def test_similar_title_match(self, test_db, seed_data):
        result = GrantAnalyzer().find_duplicates(
            title="CISE Research Grant",  # very similar to seed grant
            url="https://example.com/different-url",
        )
        assert result['is_duplicate'] is True
        assert result['duplicates'][0]['match_type'] == 'title_similarity'


class TestScoreRelevance:
    def test_score_existing_grant(self, test_db, seed_data):
        grant_id = seed_data['grants'][0].id
        result = GrantAnalyzer().score_relevance(grant_id=grant_id)
        assert 'score' in result
        assert 0 <= result['score'] <= 1
        assert result['recommendation'] in ('apply', 'watch', 'skip')

    def test_score_nonexistent_grant(self, test_db, seed_data):
        with pytest.raises(Exception):  # MethodError
            GrantAnalyzer().score_relevance(grant_id=99999)


class TestPrioritizeDeadlines:
    def test_returns_ranked_grants(self, test_db, seed_data):
        result = GrantAnalyzer().prioritize_deadlines(limit=10)
        assert 'ranked_grants' in result
        # If there are grants with future deadlines, they should be sorted
        ranked = result['ranked_grants']
        if len(ranked) > 1:
            assert ranked[0]['days_until_deadline'] <= ranked[1]['days_until_deadline']
```

### 5.2. Integration Tests for Multi-Agent Pipeline

Test the full lifecycle chain: create grant -> LIFECYCLE TX -> AnalyzerMonitor -> Analyzer agent -> Grant updated.

**File:** `/workspace/example_grants/tests/test_multi_agent_pipeline.py`

```python
"""Integration tests for the multi-agent analysis pipeline.

Tests the full chain:
    Grant.create() -> LIFECYCLE TX -> AnalyzerMonitor -> Analyzer agent -> Grant.update()

Uses Pydantic AI TestModel to mock LLM responses.
"""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, patch

from pybend.core.actors.tx import TX
from pybend.core.agents.actor import AgentActor
from actors.analyzer_monitor import AnalyzerMonitor
from models import Grant


class TestAnalyzerMonitor:
    @pytest.mark.asyncio
    async def test_ignores_non_lifecycle_tx(self, test_db, seed_data):
        """Monitor silently drops non-LIFECYCLE messages."""
        monitor = AnalyzerMonitor(addr='test_monitor')
        tx = TX(name='UNKNOWN', source='test', target='test_monitor', data={})
        # Should not raise
        await monitor.handler(tx)

    @pytest.mark.asyncio
    async def test_handles_after_create(self, test_db, seed_data):
        """Monitor triggers analysis on after_create event."""
        monitor = AnalyzerMonitor(addr='test_monitor', analyzer_agent_id=seed_data['agent'].id)

        # Mock the analyzer agent's run method
        with patch.object(AgentActor, 'get') as mock_get:
            mock_agent = AsyncMock()
            mock_agent.run = AsyncMock(return_value='{"answer": "analyzed"}')
            mock_get.return_value = mock_agent

            tx = TX(
                name='LIFECYCLE',
                source='grants',
                target='test_monitor',
                data={
                    'event': 'after_create',
                    'entity': {'id': 1, 'title': 'Test Grant', 'agency': 'NSF'},
                },
            )
            await monitor.handler(tx)

            # Give the background task time to execute
            await asyncio.sleep(0.1)

            mock_get.assert_called_once()
            mock_agent.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_missing_analyzer(self, test_db, seed_data):
        """Monitor logs error when Analyzer agent not found."""
        monitor = AnalyzerMonitor(addr='test_monitor', analyzer_agent_id=99999)

        tx = TX(
            name='LIFECYCLE',
            source='grants',
            target='test_monitor',
            data={
                'event': 'after_create',
                'entity': {'id': 1, 'title': 'Test Grant'},
            },
        )
        # Should not raise -- logs error and returns
        await monitor.handler(tx)


class TestFullPipeline:
    @pytest.mark.asyncio
    async def test_grant_create_triggers_analysis(self, test_db, seed_data):
        """Creating a Grant via handler_crud publishes LIFECYCLE event.

        This test verifies the TX chain from create to LIFECYCLE publication.
        The actual analyzer invocation is tested separately in TestAnalyzerMonitor.
        """
        # Subscribe a test listener to Grant._subscribers
        received_events = []
        original_subscribers = Grant._subscribers[:]

        class TestListener:
            """Captures LIFECYCLE TXs for assertions."""
            _addr = 'test_listener'
            addr = 'test_listener'
            _children = {}
            children = {}
            _parent = None
            parent = None
            _interceptors = {}

            async def inbox(self, tx):
                received_events.append(tx)

        # Register test listener
        from pybend.core.actors.matrix import matrix
        listener = TestListener()
        matrix._children['test_listener'] = listener
        Grant._subscribers.append('test_listener')

        try:
            # Create a grant via handler_crud
            tx = TX(
                name='create',
                source='test',
                target='grants',
                data={
                    'title': 'Pipeline Test Grant',
                    'agency': 'DOE',
                    'url': 'https://example.com/pipeline-test',
                },
            )
            await Grant.inbox(tx)
            await asyncio.sleep(0.1)

            # Verify LIFECYCLE event was published
            lifecycle_txs = [e for e in received_events if e.name == 'LIFECYCLE']
            assert len(lifecycle_txs) >= 1
            event_data = lifecycle_txs[0].data
            assert event_data['event'] == 'after_create'
            assert event_data['entity']['title'] == 'Pipeline Test Grant'
        finally:
            # Cleanup
            Grant._subscribers = original_subscribers
            matrix._children.pop('test_listener', None)
```

### 5.3. Testing Structured Output

**File:** `/workspace/example_grants/tests/test_structured_output.py`

```python
"""Tests for structured output via output_type parameter."""
import json
import pytest
from pydantic_ai.models.test import TestModel
from pybend.core.agents.actor import AgentActor
from agents.output_types import ScanResult, AnalysisResult


class TestStructuredOutput:
    @pytest.mark.asyncio
    async def test_output_type_passthrough(self, test_db, seed_data):
        """agent_run() passes output_type to Pydantic AI Agent."""
        agent = AgentActor.get(seed_data['agent'].id)
        result_str = await agent.run(
            task="Scan for grants",
            llm=TestModel(call_tools=[]),
            output_type=ScanResult,
        )
        result = json.loads(result_str)
        # TestModel returns a default/mock structured output
        assert 'answer' in result

    @pytest.mark.asyncio
    async def test_default_str_output(self, test_db, seed_data):
        """Without output_type, agent returns plain string (backward compat)."""
        agent = AgentActor.get(seed_data['agent'].id)
        result_str = await agent.run(
            task="Hello",
            llm=TestModel(call_tools=[]),
        )
        result = json.loads(result_str)
        assert isinstance(result['answer'], str)
```

### 5.4. Testing Agent Memory

**File:** `/workspace/example_grants/tests/test_agent_memory.py`

```python
"""Tests for agent memory — message_history persistence and loading."""
import pytest
from agents.memory import serialize_messages, deserialize_messages, load_history


class TestMessageSerialization:
    def test_roundtrip_dicts(self):
        """Dicts survive serialize/deserialize roundtrip."""
        original = [{'kind': 'request', 'parts': [{'content': 'hello'}]}]
        serialized = serialize_messages(original)
        deserialized = deserialize_messages(serialized)
        assert deserialized is not None
        assert len(deserialized) == 1

    def test_empty_history(self):
        """Empty list returns None."""
        assert deserialize_messages([]) is None
        assert deserialize_messages(None) is None

    def test_load_history_no_runs(self, test_db, seed_data):
        """load_history returns None when no completed runs exist."""
        result = load_history(agent_id=99999)
        assert result is None
```

### 5.5. Testing SamGovAPI and DocumentTools (Mocked HTTP)

```python
"""Tests for SamGovAPI tool actor — mocked HTTP responses."""
import pytest
from unittest.mock import patch, AsyncMock
from models.sam_gov_api import SamGovAPI


class TestSamGovAPI:
    @pytest.mark.asyncio
    async def test_search_missing_api_key(self):
        """Raises MethodError when SAM_GOV_API_KEY not set."""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(Exception):  # MethodError
                await SamGovAPI().search(keyword='test')

    @pytest.mark.asyncio
    async def test_search_success(self):
        """Returns structured results on successful API call."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'totalRecords': 1,
            'opportunitiesData': [{'title': 'Test Opp'}],
        }

        with patch.dict('os.environ', {'SAM_GOV_API_KEY': 'test-key'}):
            with patch('httpx.AsyncClient') as mock_client:
                mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
                mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
                mock_client.return_value.get = AsyncMock(return_value=mock_response)

                result = await SamGovAPI().search(keyword='grants')
                assert result['total'] == 1
                assert len(result['opportunities']) == 1
```

### 5.6. Test File Organization

```
example_grants/tests/
    conftest.py                     # Existing — add SeenGrant, GrantAnalyzer to registration
    test_grant_analyzer.py          # Unit: dedup, scoring, deadline ranking (Task 1.5)
    test_sam_gov_api.py             # Unit: mocked HTTP (Task 1.4)
    test_document_tools.py          # Unit: mocked PDF/HTML (Task 3.1)
    test_seen_grant.py              # Unit: hash-based dedup (Task 3.2)
    test_structured_output.py       # Integration: output_type passthrough (Task 1.1)
    test_agent_memory.py            # Unit + Integration: serialization + load (Task 1.3)
    test_multi_agent_pipeline.py    # Integration: LIFECYCLE -> Monitor -> Agent (Task 2.2-2.3)
    test_delegation.py              # Integration: in-run agent delegation (Task 2.4)
    test_agent_run.py               # Existing — extend with new tests
```

**conftest.py updates:**
- Register new models: `SamGovAPI`, `GrantAnalyzer`, `DocumentTools`, `SeenGrant`
- Seed Analyzer agent record for multi-agent tests
- Add `analyzer_agent` fixture

---

## 6. Risk Register

| Risk | Likelihood | Impact | Mitigation | Phase |
|------|------------|--------|------------|-------|
| SAM.gov API key approval delay (5-30 days) | Medium | Low | Start with GrantsGovAPI (no auth). SamGovAPI is additive -- deploy without it. | P1 |
| Lifecycle event ordering non-deterministic | Low | Medium | `asyncio.create_task()` does not guarantee order. AnalyzerMonitor is idempotent -- duplicate analysis is harmless (updates same grant). | P2 |
| Analyzer agent run fails during lifecycle event | Medium | Low | `_run_analyzer()` catches all exceptions and logs. Grant remains in 'discovered' status -- no data corruption. | P2 |
| Message history deserialization breaks across Pydantic AI versions | Medium | Medium | Pin pydantic-ai version. Defensive `deserialize_messages()` catches errors and returns None (agent runs without memory, not crash). | P1 |
| PDF parsing fails on complex/scanned PDFs | High | Low | `parse_pdf()` returns error dict, not crash. Agent sees the error and can fall back to HTML scraping. | P3 |
| SeenGrant table grows unbounded | Low | Low | Hash-based, 16-char hashes. 100K records = ~10MB. Add periodic cleanup for grants older than 1 year if needed. | P3 |
| Delegation creates nested agent runs (token explosion) | Medium | Medium | Analyzer agent has `max_iterations: 15` constraint. Delegation tools document that they spawn a full agent run. Budget-aware users set constraints. | P2 |
| Multiple LIFECYCLE events for same grant (race condition) | Low | Low | AnalyzerMonitor's `_on_grant_created` is idempotent. Scoring the same grant twice produces the same result. | P2 |

---

## 7. Framework vs Application Code Boundary

This is critical for maintaining PyBend's architecture. The fork adds **~25 lines to the framework** and everything else is application code.

### Framework Changes (src/pybend/core/)

| File | Change | Lines | Backward Compatible |
|------|--------|-------|---------------------|
| `agents/mixin.py` | `output_type` passthrough | 1 | Yes (defaults to `str`) |
| `agents/mixin.py` | `model_dump()` on output | 3 | Yes (only if output has `model_dump`) |
| `agents/mixin.py` | `message_history` passthrough | 4 | Yes (defaults to `None`) |
| `agents/mixin.py` | `extra_tools` kwarg | 2 | Yes (defaults to `[]`) |
| `agents/mixin.py` | Constraints: `max_tokens`, `tool_retries`, `run_timeout` | ~15 | Yes (new keys only) |
| **Total** | | **~25** | **All backward compatible** |

### Application Code (example_grants/)

| Directory | New Files | Purpose |
|-----------|-----------|---------|
| `models/` | `sam_gov_api.py`, `grant_analyzer.py`, `document_tools.py`, `seen_grant.py` | Tool actors + dedup model |
| `actors/` | `analyzer_monitor.py` | Event-driven pipeline glue |
| `agents/` | `output_types.py`, `memory.py`, `delegation.py` | Agent capabilities |
| `tests/` | 6 new test files | Coverage for all new features |
| `main.py` | ~8 lines added | Registration + subscriber wiring |
| `seed.py` | ~30 lines added | Analyzer + Reporter agent records |
| `models/__init__.py` | 4 imports added | New model exports |

### No Changes Required

| Component | Why |
|-----------|-----|
| `actor_model.py` | `_publish_lifecycle()` and `_subscribers` already exist, work as-is |
| `matrix.py` | Routing works for all new actors without changes |
| `tx.py` | TX envelope handles all new message types |
| `tools.py` | `discover_tools()` automatically finds new tool actors |
| `network_adapter.py` | Used by `agent_run()` unchanged |
| `proto_model.py` | Schema pipeline unchanged |
| All frontend code | Schema-driven rendering adapts automatically |

---

## Appendix A: Complete Task Dependency Graph

```
Phase 1 (Week 1-2):
    Task 1.1 (output_type)  ──────────────────────────+
    Task 1.2 (output types) ──── depends on 1.1 ──────+──── Phase 2 can start
    Task 1.3 (message_history) ── depends on Sprint 1 |
    Task 1.4 (SamGovAPI) ── independent ───────────────+
    Task 1.5 (GrantAnalyzer) ── independent ───────────+

Phase 2 (Week 3-4):
    Task 2.1 (Agent records) ── depends on 1.5 (analyzer tools must exist)
    Task 2.2 (AnalyzerMonitor) ── depends on 2.1 (analyzer agent must exist)
    Task 2.3 (Subscriber wiring) ── depends on 2.2
    Task 2.4 (Delegation) ── depends on 1.5, 2.1

Phase 3 (Week 5-6):
    Task 3.1 (DocumentTools) ── independent
    Task 3.2 (SeenGrant) ── independent
    Task 3.3 (Constraints) ── independent
```

**Critical path:** 1.1 -> 1.5 -> 2.1 -> 2.2 -> 2.3

Tasks 1.3, 1.4, 2.4, 3.1, 3.2, 3.3 are all parallelizable off the critical path.

---

## Appendix B: Full `main.py` After Fork D

```python
"""Grant Watcher — main.py with multi-agent pipeline."""
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import config
from pybend.core.app import create_app
from pybend.core.storage.sqlite_storage import SQLiteStorage
from pybend.core.agents.actor import AgentActor
from pybend.core.agents.tool_model import AgentTool
from models import User, Grant, Source, WebTools, SamGovAPI, GrantAnalyzer, DocumentTools, SeenGrant

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')

_HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get('PYBEND_SQLITE_DB') or os.path.join(_HERE, 'grants.db')

storage = SQLiteStorage(DB_PATH)
app = create_app(
    models=[User, Grant, Source, WebTools, SamGovAPI, GrantAnalyzer, DocumentTools,
            SeenGrant, AgentTool, AgentActor],
    join_models=[(AgentActor, AgentTool)],
    storage=storage,
    routing='actor',
    static_dir=os.path.join(_HERE, 'static'),
    jwt_secret=config.JWT_SECRET,
    name="Grant Watcher",
    version="0.10.0",
    description="Agentic grant-watching application with multi-agent pipeline",
)

# Run manual migrations
storage._migration.migrations_dir = os.path.join(_HERE, 'migrations')
storage._migration.run_migrations()

# ── Multi-Agent Pipeline ──
from pybend.core.actors.matrix import matrix
from actors.analyzer_monitor import AnalyzerMonitor

monitor = AnalyzerMonitor(addr='analyzer_monitor', analyzer_agent_id=2)
matrix.register(monitor)
Grant._subscribers.append('analyzer_monitor')

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host=config.HOST, port=config.PORT)
```

---

## Appendix C: Structured Output Flow Detail

How `output_type` flows from the application through the framework to Pydantic AI and back:

```
1. Application calls AgentActor.run(task="Scan sources", output_type=ScanResult)

2. AgentActor.run() passes output_type as kwarg to self.agent_run()

3. agent_run() (in mixin.py) reads kwargs.get('output_type', str):
   ai_agent = Agent(
       llm,
       system_prompt=prompt,
       deps_type=AgentDeps,
       tools=ai_tools,
       output_type=ScanResult,    # <-- passed through
   )

4. Pydantic AI's Agent(output_type=ScanResult) injects the output schema
   into the system prompt as a JSON Schema constraint. The LLM is instructed
   to return JSON conforming to ScanResult's schema.

5. result = await ai_agent.run(task, deps=deps, usage_limits=usage_limits)
   result.output is now a ScanResult instance:
   ScanResult(grants_found=5, grants_created=3, duplicates_skipped=2, ...)

6. agent_run() returns:
   {
       'answer': result.output.model_dump(),  # dict, not str
       'usage': {...},
       'messages': N,
   }

7. AgentActor.run() serializes: json.dumps(result, default=str)
   Returns JSON string with structured answer.

8. HTTP response: {"answer": {"grants_found": 5, "grants_created": 3, ...}, "usage": {...}}
```

The AnalyzerMonitor, AgentRun records, and any other consumer can now parse the answer as a typed dict instead of trying to extract meaning from raw text.

---

## Appendix D: Agent-to-Agent Communication Patterns

This fork uses two complementary patterns for agent coordination:

### Pattern 1: Event-Driven (Cross-Run)

Used when one agent's output triggers another agent's execution asynchronously.

```
Scanner Agent          Grant Model         AnalyzerMonitor      Analyzer Agent
     |                     |                     |                    |
     | grants_create(...)  |                     |                    |
     |-------------------->|                     |                    |
     |                     | _publish_lifecycle  |                    |
     |                     | ('after_create')    |                    |
     |                     |-------------------->|                    |
     |                     |                     | AgentActor.get(2)  |
     |                     |                     |------------------->|
     |                     |                     | analyzer.run(task) |
     |                     |                     |------------------->|
     |                     |                     |                    | grant_analyzer_find_duplicates
     |                     |                     |                    | grant_analyzer_score_relevance
     |                     |                     |                    | grants_update(status='reviewed')
     |                     |<-----------------------------------------|
     |                     |                     |                    |
```

**Characteristics:**
- Asynchronous (fire-and-forget via `asyncio.create_task`)
- Scanner does not wait for analysis
- Separate agent runs (separate LLM sessions, separate token counts)
- Decoupled: Scanner does not know about Analyzer

### Pattern 2: Delegation (Within-Run)

Used when one agent needs another's analysis before making a decision.

```
Scanner Agent (single LLM run)
     |
     | LLM decides: "Before creating, let me check for duplicates"
     |
     | delegate_analyze(grant_id=5)    <-- tool call within Scanner's run
     |
     +---> Analyzer Agent (nested run)
     |         |
     |         | grant_analyzer_find_duplicates(...)
     |         | grant_analyzer_score_relevance(...)
     |         |
     |         | Returns: {"score": 0.8, "is_duplicate": false}
     |     <---+
     |
     | LLM sees: "Score is high, not a duplicate — creating grant"
     |
     | grants_create(...)
     |
```

**Characteristics:**
- Synchronous (parent waits for child)
- Single logical operation (Scanner decides inline)
- Token usage aggregated (parent sees total cost)
- Coupled: Scanner explicitly calls Analyzer as a tool

**When to use which:**
- **Event-driven** for post-creation analysis (the default). Every new grant gets analyzed regardless of how it was created.
- **Delegation** for pre-creation validation (optional). The Scanner can check before creating, avoiding unnecessary records. Both can be active simultaneously.
