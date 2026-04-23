# Agent Chat + Veille Dashboard Refactor Plan

## Summary

This work splits into four independent but coordinated updates:

1. **Framework bootstrap addition** — provision a static app Assistant at startup as a pure addition
2. **Framework chat refactor** — make `ntx-chat` threaded, responsive, and based on shared stream rendering
3. **Veille dashboard rewrite** — replace the noisy default landing surface with `agents-dashboard`
4. **Veille agent interaction integration** — wire featured agent cards into detail + chat flows

Current agreed constraints:

- existing seed behavior stays in place
- Assistant is added at app bootstrap as a pure addition
- no `sessionStorage` or persisted frontend chat state for now
- `ntx-chat` is container-responsive
- `xs` uses button + panel launcher mode
- `sm` and above render as a plain in-flow component
- Veille default landing surface becomes `agents-dashboard`
- Veille sidebar label is `DASHBOARD`
- Veille dashboard shows **featured agents only**
- featured seeded agents are configured in **app config**

## Current State

### Already present

- `packages/n3tx-agents/src/n3tx_agents/thread.py`
- `packages/n3tx-agents/src/n3tx_agents/mixin.py`
- `packages/n3tx-agents/src/n3tx_agents/actor.py`
- `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js`
- `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js`
- `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js`
- thread persistence tests already exist in `packages/n3tx-agents/src/n3tx_agents/tests/test_thread.py`
- Veille already has seeded static agents in `apps/veille/seed.py`
- Veille already mounts `AgentActor` UI in the sidebar

### Main gaps

1. `ntx-chat` does not actually drive thread-backed history
   - no `thread_id`
   - no `create_thread`
   - no reuse of conversation state across turns inside the component

2. `ntx-chat` and `ntx-agent-live` duplicate stream rendering logic
   - they should be centered on `NTTStreamAgent`

3. There is no framework bootstrap contract for a static app Assistant
   - apps currently seed agents manually
   - there is no app-level Assistant provisioning hook in `create_app()` / `N3TXApp`

4. Veille HOME is still effectively `ntx-run-panel`
   - default landing UI mixes real data with hardcoded placeholder sections
   - the agent entrypoint is not the primary dashboard yet

## Goals

- Provide a reusable threaded chat component in `n3tx-agents`
- Reuse the existing backend `Thread` model rather than creating a new conversation model
- Reuse `NTTStreamAgent` instead of maintaining duplicated stream rendering logic
- Add framework-supported Assistant provisioning at app bootstrap as a pure addition
- Keep existing seeded Veille agents intact
- Replace Veille HOME with a featured-agent dashboard named `agents-dashboard`
- Show only featured agents on DASHBOARD
- Define featured seeded agents in Veille app config

## Non-Goals

- Replacing the app-specific `examples/chat` architecture
- Removing or migrating existing seeded agents out of `apps/veille/seed.py`
- Adding frontend chat state persistence beyond in-memory component state
- Making the Veille dashboard show all `AgentActor` rows by default

## High-Level Architecture

```text
Veille main.py
   |
   +-- create_app(..., app_agent={Assistant...})
   |
   +-- Veille config declares featured agent keys/names
            |
            v
     N3TXApp.build()
            |
            +-- register models + joins
            +-- provision Assistant if missing / update if present
            v
         app starts

Default Veille route ('')
   |
   v
agents-dashboard
   |
   +-- featured cards only
   |     1. Assistant
   |     2. Veille Scout
   |     3. other configured featured agents
   |
   +-- click card -> AgentActor/<id>
                     |
                     v
                  ntx-agent
                     |
                     +-- ntx-chat
                     +-- ntx-agent-live
```

## Files Likely To Change

### Framework backend

- `packages/n3tx-core/src/n3tx_core/app.py`
- `packages/n3tx-agents/src/n3tx_agents/actor.py`
- `packages/n3tx-agents/src/n3tx_agents/mixin.py`
- new helper module in `packages/n3tx-agents/src/n3tx_agents/`

### Framework frontend

- `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js`
- `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.css`
- `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js`
- `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js`
- possibly `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.js`

### Veille app

- `apps/veille/main.py`
- `apps/veille/config.py`
- `apps/veille/static/index.html`
- new `apps/veille/static/components/ntx-agents-dashboard.js`
- optional `apps/veille/static/components/ntx-agents-dashboard.css`
- possibly `apps/veille/static/veille.css`

### Tests

- `packages/n3tx-agents/src/n3tx_agents/tests/test_thread.py`
- new framework provisioning tests in `n3tx-agents` and/or `n3tx-core`
- Veille UI/integration tests for dashboard routing and featured agent rendering

### Docs

- `docs/AGENTS.md`
- `FRONTEND.md`
- `packages/n3tx-agents/docs/mixin.md`
- `packages/n3tx-agents/docs/agent-actor.md`

## Update 1 — Framework bootstrap addition: provision Assistant

### Goal

Add one framework-supported Assistant provisioning path that Veille can opt into via app bootstrap, without changing existing seed behavior.

### Scope

- `packages/n3tx-core/src/n3tx_core/app.py`
- `packages/n3tx-agents/src/n3tx_agents/actor.py`
- new helper module, preferably `packages/n3tx-agents/src/n3tx_agents/app_agent.py`
- `apps/veille/main.py`

### Implementation details

#### 1. Extend bootstrap API

Add optional `app_agent` argument to:

- `N3TXApp.__init__`
- `create_app()`

Store on builder state:

```python
self._app_agent = app_agent
```

#### 2. Add post-registration provisioning call

In `N3TXApp.build()`, immediately after all `apply_registration(...)` calls complete, add:

```python
if self._app_agent:
    from n3tx_agents.app_agent import provision_app_agent
    provision_app_agent(self._app_agent, registered_models)
```

This must happen:

- after `AgentActor`, `AgentTool`, and joins are registered
- before the app is returned

#### 3. Implement `provision_app_agent(...)`

Responsibilities:

1. resolve registered `AgentActor`
2. resolve registered `AgentTool`
3. resolve generated join model for `(AgentActor, AgentTool)`
4. find existing Assistant record
5. create or update Assistant record idempotently
6. create/update tool join rows idempotently

#### 4. Identity strategy

Preferred implementation:

Add a stable machine field to `AgentActor`:

```python
system_key: str = Field(default='', description='Stable bootstrap identity')
```

Provision lookup order:

1. `system_key`
2. fallback by `name` only if needed for compatibility

#### 5. Veille bootstrap usage

In `apps/veille/main.py`, pass:

```python
app_agent={
    "key": "assistant",
    "name": "Assistant",
    "prompt": "...",
    "llm": "...",
    "constraints": {...},
    "tools": [
        {"target": "grants", "description": "..."},
        {"target": "sources", "description": "..."},
        {"target": "web_tools", "description": "..."},
        {"target": "organizations", "description": "..."},
    ],
    "featured": True,
}
```

### Explicit non-goals

- do not remove or rewrite `apps/veille/seed.py`
- do not move `Veille Scout` out of seed

### Acceptance criteria

- app startup creates Assistant if missing
- repeated startup does not duplicate Assistant
- Assistant tool links are reconciled idempotently
- Veille Scout still comes from seed unchanged

### Tests

- create Assistant when absent
- no duplicate Assistant on repeated bootstrap
- tool join reconciliation is idempotent
- clear failure when `AgentActor`, `AgentTool`, or join model is missing

## Update 2 — Framework chat refactor: threaded responsive `ntx-chat`

### Goal

Make `ntx-chat` a real multi-turn agent chat component with in-memory thread tracking and container-responsive rendering.

### Scope

- `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js`
- `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.css`
- `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js`
- `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js`
- `packages/n3tx-agents/src/n3tx_agents/mixin.py`

### Interaction model

```text
<ntx-chat model="AgentActor" ref="agents/1"></ntx-chat>
           |
           +-- first turn  -> POST agentic_stream { task, create_thread: true }
           |                 <- done { thread_id }
           |
           +-- next turn   -> POST agentic_stream { task, thread_id }
                             <- done { thread_id }
```

### Implementation details

#### 1. Refactor reuse around `NTTStreamAgent`

Current problem:

- `ntx-chat` and `ntx-agent-live` duplicate rendering of thinking/tool/text/done states

Target structure:

- `NTTStream` stays the stream transport/dispatch base
- `NTTStreamAgent` stays the shared agent stream renderer
- `ntx-chat` becomes chat shell + transcript + thread state
- `ntx-agent-live` becomes a thinner layer over shared stream behavior

#### 2. Add in-memory thread state to `NTTChat`

Internal fields:

```js
#threadId = null;
#messages = [];
#size = 'sm';
#activeAssistant = null;
```

No `sessionStorage` and no URL persistence.

#### 3. Sending logic

First send:

```js
{ task: content, create_thread: true }
```

Subsequent sends:

```js
{ task: content, thread_id: this.#threadId }
```

#### 4. Completion logic

On `DONE`:

- read `data.thread_id`
- if present, set `#threadId`
- use it for later turns

#### 5. Transcript logic

- append user bubble immediately on send
- create one assistant bubble when stream begins
- append `TEXT` chunks into that bubble
- render tool/thinking events within or beneath the active assistant turn

#### 6. Responsive behavior

Use `ResizeObserver` on host/container.

Buckets:

- `xs` => floating launcher button + panel
- `sm`, `md`, `lg`, `xl` => plain in-flow component

Implementation detail:

- set host attribute or class such as `data-size="xs|sm|md|lg|xl"`
- CSS decides launcher vs inline layout

### Backend support cleanup

In `AgentMixin.run()` and `run_stream()`:

- support `create_thread=True`
- auto-create thread if requested and `thread_id` absent
- validate reused thread belongs to the current agent
- always include `thread_id` in final threaded result

### Acceptance criteria

- first turn creates a thread automatically
- second turn reuses returned `thread_id`
- `xs` renders launcher mode
- `sm+` renders inline mode
- no chat state survives page reload or component remount

### Tests

Backend:

- auto-create thread on first turn
- reuse thread on second turn
- reject invalid thread/agent pairing
- include `thread_id` in final payload

Frontend:

- first send uses `create_thread`
- second send uses returned `thread_id`
- `xs` uses launcher mode
- `sm+` uses inline mode

## Update 3 — Veille dashboard rewrite: `agents-dashboard`

### Goal

Replace the current default landing surface with a featured-agent dashboard and rename the primary sidebar entry to `DASHBOARD`.

### Scope

- `apps/veille/static/index.html`
- `apps/veille/config.py`
- new `apps/veille/static/components/ntx-agents-dashboard.js`
- optional CSS for the dashboard
- possibly `apps/veille/static/veille.css`

### App config requirement

Featured seeded agents must be configured in app config.

Add config entries such as:

```python
FEATURED_AGENT_KEYS = ['assistant']
FEATURED_AGENT_NAMES = ['Veille Scout']
```

Or equivalent single ordered structure:

```python
FEATURED_AGENTS = [
    {'system_key': 'assistant'},
    {'name': 'Veille Scout'},
]
```

Preferred implementation: one ordered config structure.

### Implementation details

#### 1. Replace default route content

In `apps/veille/static/index.html`, replace the current default landing element with:

```html
<ntx-agents-dashboard id="agents-dashboard"></ntx-agents-dashboard>
```

#### 2. Rename sidebar label

The first/default sidebar entry should render as:

```text
DASHBOARD
```

and route to the default `''` route.

#### 3. Keep runs separate

`ntx-run-panel` should remain accessible as its own route, not as the default landing surface.

#### 4. Build `ntx-agents-dashboard`

Responsibilities:

- load the configured featured agents in the configured order
- resolve the corresponding `AgentActor` records
- render agent cards using `ntx-agent` styling/shape
- navigate to `AgentActor/<id>` on click

#### 5. Featured-agent selection rule

Show **featured agents only**.

Initial Veille order:

1. Assistant
2. Veille Scout

The source of truth for this order is **app config**.

#### 6. Remove noisy landing-page filler

Do not show on default DASHBOARD:

- synthetic health score
- fake charts
- hardcoded strategic forecast copy
- decorative placeholder hero content from `ntx-run-panel`

### Acceptance criteria

- default Veille route shows `agents-dashboard`
- sidebar label is `DASHBOARD`
- only configured featured agents render
- Assistant appears first
- clicking a card opens the correct `AgentActor/<id>` route

### Tests

- default route renders dashboard
- DASHBOARD label appears in sidebar
- only configured featured agents render
- Assistant is first
- clicking a card routes correctly

## Update 4 — Veille agent interaction integration

### Goal

Make featured agent cards lead to actual conversational interaction.

### Scope

- `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.js`
- possibly Veille wrapper code if framework `ntx-agent` should stay lighter
- Veille route wiring in `apps/veille/static/index.html`

### Implementation details

#### 1. Card click flow

From `agents-dashboard`:

- click featured card
- navigate to `AgentActor/<id>`

#### 2. Detail view enhancement

When rendering a concrete `AgentActor` instance in `ntx-agent`, embed:

```html
<ntx-chat model="AgentActor" ref="agents/{id}"></ntx-chat>
```

Placement:

- below prompt/tool summary
- above or beside live activity depending on size mode

#### 3. Preserve existing activity view

Keep `ntx-agent-live` present as the structured/debug activity panel.
`ntx-chat` is the user-facing conversational surface.

#### 4. Responsive behavior inside detail

- `xs`: `ntx-chat` uses launcher mode
- `sm+`: `ntx-chat` renders inline

### Acceptance criteria

- clicking Assistant card opens detail view
- detail view includes `ntx-chat`
- detail view still includes summary/tool information
- threaded chat works from agent detail

### Tests

- clicking Assistant from dashboard opens detail
- detail includes chat component
- chat can start and continue a threaded conversation

## Risks And Mitigations

| Area | Risk | Mitigation |
|---|---|---|
| Bootstrap | no stable identity for Assistant | add `system_key` on `AgentActor` |
| Bootstrap | Assistant duplicates on reload/startup | provision by `system_key`, reconcile idempotently |
| History | wrong thread reused across agents | validate thread ownership/agent target |
| UI | duplicated stream logic diverges further | center chat/live rendering on `NTTStreamAgent` |
| UX | dashboard becomes another noisy list | show featured agents only, ordered from app config |
| State | user expects conversations after reload | explicitly keep thread state in memory only for now |

## Recommended Execution Order

1. Framework bootstrap addition: Assistant provisioning
2. Framework chat refactor: threaded responsive `ntx-chat`
3. Veille dashboard rewrite: `agents-dashboard` + `DASHBOARD`
4. Veille detail/chat integration
5. Tests and docs updates across all touched areas

## Verification Plan

- Run targeted framework tests for Assistant provisioning
- Run `n3tx-agents` thread-related tests
- Run frontend tests for `ntx-chat` responsive/threaded behavior where available
- Run Veille route/dashboard tests
- Manually verify:
  - Veille starts with Assistant provisioned
  - Veille Scout still comes from seed
  - default route shows `agents-dashboard`
  - DASHBOARD shows configured featured agents only
  - Assistant card opens detail
  - detail chat starts a new thread and continues it during the mounted session
