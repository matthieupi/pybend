# Hypermedia Route Grammar Architecture Plan

## 0. Executive Summary

This plan defines N3TX's next route grammar for model-centric APIs and HTML/view entrypoints while preserving current table-name API routes.

The new design is an **incremental dual grammar**:

```text
/{tablename}/...       legacy/current data API, unchanged for compatibility
/{ClassName}/...       class-name schema + mirrored model API grammar
/{ClassName}/@...      server-served HTML/view entrypoints
#{ClassName}/@...      frontend hash-router view routes during migration
```

The key idea is that N3TX will keep current apps working while adding a clearer model-first route layer. The `@` segment is reserved to mean **view / HTML / component route**, never data.

### Core invariants

1. Existing table-name routes such as `/agents` and `/agents/1` remain working.
2. Existing schema routes such as `/AgentActor` remain schema/type endpoints.
3. New class-name instance routes such as `/AgentActor/1` mirror table-name instance routes.
4. `@` always marks an HTML/view route, e.g. `/AgentActor/@table`, `/AgentActor/1/@`.
5. Frontend hash navigation uses the same grammar first, e.g. `#AgentActor/@table`.
6. `@view` resolves through `schema.ui.renderer[view]` before any fallback.
7. In the first implementation waves, `$id` remains table-name based to avoid breaking current cache/ref behavior.

---

## 1. Why This Plan Changed

Earlier planning explored a pure HTTP representation-negotiation model:

```http
GET /agents/1
Accept: text/html
```

That remains philosophically sound, but it is too disruptive for the current codebase because N3TX already has a strong split:

```text
/{ClassName}   -> schema
/{tablename}   -> data/API
```

The engineering decision is to preserve this split and extend it into a clearer dual grammar:

```text
table-name URLs  = current API compatibility
class-name URLs  = model-centric schema/API/view grammar
@ URLs           = HTML/view entrypoints
```

This gives N3TX a lower-risk migration path toward model-centric hypertext without breaking current applications.

---

## 2. Current State

### Current backend route shape

For a model like `AgentActor` with `__tablename__ = 'agents'`:

```text
GET    /AgentActor          JSON Schema
GET    /agents              JSON list
POST   /agents              JSON create
GET    /agents/1            JSON read
PUT    /agents/1            JSON update
DELETE /agents/1            JSON delete
POST   /agents/1/run        custom method
```

### Current frontend route shape

The hash router currently understands:

```text
#AgentActor
#AgentActor/1
#AgentActor/1/run
#AgentActor?view=table
#@profile
```

### Current fragility

Current route strings overload multiple concerns:

```text
Route string       -> Model/id/action
Schema endpoint    -> /ClassName
Data endpoint      -> /tablename/id
Renderer override  -> ?view=table
```

This creates ambiguity when adding richer HTML/component routes. The `@` marker gives N3TX a reserved, explicit namespace for views.

---

## 3. Target Route Grammar

### 3.1 Backend route grammar

```text
/{ClassName}                       schema/type endpoint
/{ClassName}/{id:int}              class-name instance mirror
/{ClassName}/{id:int}/{method}     future class-name method mirror, optional

/{ClassName}/@                     collection default HTML page
/{ClassName}/@{view}               collection named HTML view
/{ClassName}/{id:int}/@            member default HTML page
/{ClassName}/{id:int}/@{view}      member named HTML view

/{tablename}                       existing collection API
/{tablename}/{id:int}              existing member API
/{tablename}/{id:int}/{method}     existing method API
```

### 3.2 Frontend hash route grammar

```text
#{ClassName}                       legacy/default collection route
#{ClassName}/{id}                  legacy/default detail route
#{ClassName}/{id}/{method}         method/action route

#{ClassName}/@                     collection default full/page view
#{ClassName}/@{view}               collection named view
#{ClassName}/{id}/@                member default full/detail view
#{ClassName}/{id}/@{view}          member named view

#@{appRoute}                       app-level route, existing behavior
```

### 3.3 Route diagram

```text
                         +----------------------------+
                         | Browser URL / Hash Route   |
                         +-------------+--------------+
                                       |
              +------------------------+-------------------------+
              |                                                  |
              v                                                  v
     +--------------------+                          +-----------------------+
     | /agents/1          |                          | #AgentActor/1/@item   |
     | table-name API     |                          | frontend view route   |
     +---------+----------+                          +----------+------------+
               |                                                |
               v                                                v
     +--------------------+                          +-----------------------+
     | JSON data response |                          | Router.parseRoute()   |
     +--------------------+                          +----------+------------+
                                                               |
                                                               v
                                                    +------------------------+
                                                    | schema.ui.renderer     |
                                                    | item -> ntx-agent      |
                                                    +----------+-------------+
                                                               |
                                                               v
                                                    +------------------------+
                                                    | mount component        |
                                                    | ref=AgentActor/1       |
                                                    +------------------------+

     +--------------------+
     | /AgentActor/1/@    |
     | server HTML route  |
     +---------+----------+
               |
               v
     +--------------------+
     | HTML shell/page    |
     | bootstraps same    |
     | component/view     |
     +--------------------+
```

---

## 4. Route Matrix

| Route | Layer | Meaning | Response |
|---|---|---|---|
| `/agents` | legacy/current API | collection list/create | JSON |
| `/agents/1` | legacy/current API | member CRUD | JSON |
| `/agents/1/run` | legacy/current API | method/action | JSON/SSE/etc |
| `/AgentActor` | schema/type | model schema | JSON Schema |
| `/AgentActor/1` | new class API mirror | same entity as `/agents/1` | JSON |
| `/AgentActor/@` | HTML/view | collection default full page | HTML |
| `/AgentActor/@table` | HTML/view | collection table view | HTML |
| `/AgentActor/1/@` | HTML/view | member default detail page | HTML |
| `/AgentActor/1/@item` | HTML/view | member item view | HTML |
| `#AgentActor/@` | frontend router | collection default view | mounted component |
| `#AgentActor/@table` | frontend router | collection table view | mounted component |
| `#AgentActor/1/@` | frontend router | member default view | mounted component |
| `#AgentActor/1/@item` | frontend router | member item view | mounted component |

---

## 5. Semantic Rules

### 5.1 `@` means view/html, never data

These routes are intentionally different:

```text
AgentActor/1/run    method/action route
AgentActor/1/@run   view named run
```

The first invokes a backend method. The second asks for a UI projection.

### 5.2 Class names are exact class names for now

Use actual schema names:

```text
AgentActor
Product
Grant
Source
```

Do not introduce friendly aliases like `Agent -> AgentActor` in the first waves. Aliases require a real schema/router alias layer and should be deferred.

### 5.3 `$id` remains table-name based initially

In early phases, keep responses like:

```json
{
  "$schema": "http://localhost:4000/AgentActor",
  "$id": "http://localhost:4000/agents/1"
}
```

Do not switch `$id` to `/AgentActor/1` until the runtime cache/ref model is ready.

### 5.4 Class-name mirrors are migration routes

`/AgentActor/1` mirrors `/agents/1` to introduce the new grammar, but `/agents/1` remains supported for legacy compatibility.

Eventually, apps may move to the new class-name API grammar, but that is a later phase.

---

## 6. Renderer Resolution Contract

`@view` is a semantic view key, not necessarily the component tag.

Resolution order:

1. `schema.ui.renderer[view]`
2. framework fallback for known views
3. optional `ntx-${view}` fallback for developer ergonomics

### 6.1 Recommended schema shape

Existing schema already supports flat renderer hints:

```json
{
  "ui": {
    "renderer": {
      "list": "ntx-agents",
      "table": "ntx-table",
      "item": "ntx-agent",
      "detail": "ntx-agent",
      "chat": "ntx-chat"
    }
  }
}
```

This plan uses the existing shape first. A richer nested shape can come later if needed.

### 6.2 Collection resolution examples

```text
AgentActor/@
  -> renderer.page
  -> renderer.list
  -> ntx-list

AgentActor/@list
  -> renderer.list
  -> ntx-list

AgentActor/@table
  -> renderer.table
  -> ntx-table
```

### 6.3 Member resolution examples

```text
AgentActor/1/@
  -> renderer.detail
  -> renderer.item
  -> ntx-item

AgentActor/1/@item
  -> renderer.item
  -> ntx-item

AgentActor/1/@chat
  -> renderer.chat
  -> ntx-chat
```

### 6.4 Code sketch: view tag resolver

```js
function resolveViewTag(schema, view, scope) {
  const renderer = schema?.ui?.renderer || {};

  if (view && renderer[view]) return renderer[view];

  if (!view && scope === 'collection') {
    return renderer.page || renderer.list || 'ntx-list';
  }

  if (!view && scope === 'member') {
    return renderer.detail || renderer.item || 'ntx-item';
  }

  const known = {
    list: 'ntx-list',
    table: 'ntx-table',
    item: 'ntx-item',
    detail: renderer.detail || renderer.item || 'ntx-item',
  };

  if (view && known[view]) return known[view];
  if (view) return view.startsWith('ntx-') ? view : `ntx-${view}`;

  return scope === 'collection' ? 'ntx-list' : 'ntx-item';
}
```

---

## 7. Frontend Router Changes

### 7.1 Current parser problem

Today, `Router.parseRoute()` treats:

```text
AgentActor/@table
```

as:

```js
{ type: 'detail', model: 'AgentActor', id: '@table' }
```

and:

```text
AgentActor/1/@
```

as:

```js
{ type: 'action', model: 'AgentActor', id: '1', action: '@' }
```

That must change.

### 7.2 Minimal parser extension

We do not need a large route model rewrite. Keep existing route types and add view metadata:

```js
{
  type: 'model' | 'detail' | 'action' | 'app' | 'home',
  model?: string,
  id?: string,
  action?: string,
  view?: string,
  isViewRoute?: boolean,
  params: object,
}
```

### 7.3 Parsing rules

```text
AgentActor              -> model
AgentActor/@            -> model + isViewRoute + view=null
AgentActor/@table       -> model + isViewRoute + view='table'

AgentActor/1            -> detail
AgentActor/1/@          -> detail + isViewRoute + view=null
AgentActor/1/@item      -> detail + isViewRoute + view='item'

AgentActor/1/run        -> action
AgentActor/1/@run       -> detail + isViewRoute + view='run'

@profile                -> app route, existing behavior
```

### 7.4 Code sketch: parseRoute

```js
export function parseRoute(route) {
  if (!route || typeof route !== 'string') return { type: 'home' };

  // App routes keep existing root @ behavior: @profile, @settings?tab=security
  if (route.startsWith('@')) {
    const [path, query] = route.slice(1).split('?');
    return {
      type: 'app',
      app: path,
      params: query ? Object.fromEntries(new URLSearchParams(query)) : {},
    };
  }

  const [path, query] = route.split('?');
  const params = query ? Object.fromEntries(new URLSearchParams(query)) : {};
  const parts = path.replace(/^\/+|\/+$/g, '').split('/').filter(Boolean);
  const [model, second, third] = parts;

  // Collection view: Model/@ or Model/@table
  if (second === '@' || second?.startsWith('@')) {
    return {
      type: 'model',
      model,
      view: second === '@' ? null : second.slice(1),
      isViewRoute: true,
      params,
    };
  }

  // Legacy model route: Model or Model?view=table
  if (!second) {
    return { type: 'model', model, params };
  }

  // Detail view: Model/id/@ or Model/id/@item
  if (third === '@' || third?.startsWith('@')) {
    return {
      type: 'detail',
      model,
      id: second,
      view: third === '@' ? null : third.slice(1),
      isViewRoute: true,
      params,
    };
  }

  // Legacy detail/action route
  if (third) {
    return { type: 'action', model, id: second, action: third, params };
  }

  return { type: 'detail', model, id: second, params };
}
```

### 7.5 Code sketch: buildRoute

```js
export function buildRoute(parts) {
  if (!parts || parts.type === 'home') return '';

  let route;
  if (parts.type === 'app') {
    route = '@' + parts.app;
  } else {
    route = parts.model || '';
    if (parts.id) route += '/' + parts.id;
    if (parts.isViewRoute) route += '/@' + (parts.view || '');
    else if (parts.action) route += '/' + parts.action;
  }

  if (parts.params && Object.keys(parts.params).length > 0) {
    route += '?' + new URLSearchParams(parts.params).toString();
  }
  return route;
}
```

### 7.6 Code sketch: resolveRoute additions

```js
if (parsed.type === 'model') {
  const view = parsed.isViewRoute ? parsed.view : parsed.params?.view;
  const tag = parsed.isViewRoute
    ? resolveViewTag(schema, view, 'collection')
    : view
      ? resolveViewTag(schema, view, 'collection')
      : renderer.list || 'ntx-list';

  return {
    tag,
    attrs: { model: parsed.model, ...passthroughParams(parsed.params) },
    title: schema?.title || schema?.__name__ || parsed.model,
  };
}

if (parsed.type === 'detail') {
  const view = parsed.isViewRoute ? parsed.view : null;
  const tag = parsed.isViewRoute
    ? resolveViewTag(schema, view, 'member')
    : renderer.detail || renderer.item || 'ntx-item';

  return {
    tag,
    attrs: { ref: parsed.model + '/' + parsed.id, display: 'lg', ...passthroughParams(parsed.params) },
    title: schema?.title || schema?.__name__ || parsed.model,
  };
}
```

---

## 8. Backend Route Changes

### 8.1 Direct FastAPI routes

Primary file:

```text
packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py
```

Add class-name instance mirror routes and HTML/view routes while preserving existing table-name routes.

### 8.2 Actor routing routes

Primary file:

```text
packages/n3tx-actors/src/n3tx_actors/api/network_api.py
```

The actor-routed API should eventually mirror the direct FastAPI route grammar so Level 1/2 and Level 3 apps behave consistently.

### 8.3 Backend route registration order

Route order matters. Register specific `@` routes before generic instance/action mirrors.

Recommended order per model:

```text
GET /{ClassName}                         schema
GET /{ClassName}/@                       collection default HTML
GET /{ClassName}/@{view}                 collection named HTML
GET /{ClassName}/{id:int}/@              member default HTML
GET /{ClassName}/{id:int}/@{view}        member named HTML
GET /{ClassName}/{id:int}                class-name read mirror
GET /{ClassName}/{id:int}/{method}       optional method mirror

existing /{tablename}/... routes remain registered as today
```

Using `{id:int}` is important so `@table` is never parsed as an ID.

### 8.4 Code sketch: class-name read mirror

```python
@router.get(f"/{model_class.__name__}/{{id:int}}")
async def read_instance_by_class(id: int, request: Request):
    # Delegate to the same logic used by /{tablename}/{id}
    return await read_instance(id=id, request=request)
```

Actual implementation should avoid duplicating authorization and serialization logic. Extract shared read logic if needed.

### 8.5 Code sketch: HTML view endpoint handler

```python
@router.get(f"/{model_class.__name__}/@{{view:path}}", include_in_schema=False)
async def collection_view(view: str = '', request: Request = None):
    return render_model_view(
        model_class=model_class,
        id=None,
        view=view or None,
        scope='collection',
        request=request,
    )

@router.get(f"/{model_class.__name__}/{{id:int}}/@{{view:path}}", include_in_schema=False)
async def member_view(id: int, view: str = '', request: Request = None):
    return render_model_view(
        model_class=model_class,
        id=id,
        view=view or None,
        scope='member',
        request=request,
    )
```

FastAPI may require separate routes for the empty default case:

```text
/{ClassName}/@
/{ClassName}/@{view}
/{ClassName}/{id:int}/@
/{ClassName}/{id:int}/@{view}
```

because optional path segments are awkward.

---

## 9. HTML/View Response Design

### 9.1 Short-term goal

`/{ClassName}/@...` routes return a full HTML app shell that mounts the requested component.

This is not a JSON API route.

### 9.2 Example server output

For:

```text
GET /AgentActor/1/@item
```

The server can return HTML equivalent to:

```html
<!doctype html>
<html>
  <head>
    <script type="module" src="/core/NTT.js"></script>
    <script type="module" src="/components/ntx-agent.js"></script>
  </head>
  <body>
    <ntx-agent ref="AgentActor/1" display="lg"></ntx-agent>
  </body>
</html>
```

For:

```text
GET /AgentActor/@table
```

Return:

```html
<ntx-table model="AgentActor"></ntx-table>
```

In practice, reuse the existing app shell and SSR schema preload helpers where possible.

### 9.3 Important constraint

Do not create a disconnected server-side component system in the first phase. The HTML route can bootstrap the normal frontend component system.

---

## 10. `$id`, `href`, and Identity Migration

### 10.1 First-wave rule

Keep payload identity as-is:

```json
{
  "$schema": "/AgentActor",
  "$id": "/agents/1"
}
```

### 10.2 Why

Current frontend caching and references are still table-name/`Model/id` oriented. Changing `$id` immediately would risk breaking:

- `NTT` instance hrefs
- relation refs
- nested resources
- stored links
- tests
- external API consumers

### 10.3 Later migration option

Eventually N3TX may move to:

```json
{
  "$schema": "/AgentActor",
  "$id": "/AgentActor/1",
  "links": {
    "legacy": "/agents/1"
  }
}
```

But only after identity handling is explicitly migrated.

---

## 11. Compatibility and Legacy Behavior

### Existing routes must continue working

```text
#AgentActor
#AgentActor/1
#AgentActor/1/run
#AgentActor?view=table

/agents
/agents/1
/agents/1/run
```

### New routes are additive

```text
#AgentActor/@
#AgentActor/@table
#AgentActor/1/@
#AgentActor/1/@item

/AgentActor/1
/AgentActor/@
/AgentActor/1/@
```

### Query compatibility

Legacy:

```text
#AgentActor?view=table
```

Should remain equivalent to:

```text
#AgentActor/@table
```

The new `@` grammar is preferred, but old `?view=` should not break.

---

## 12. Implementation Phases

### Phase 1 — Frontend `@` router grammar

Modify:

```text
packages/n3tx-core/src/n3tx_core/static/core/Router.js
```

Add support for:

```text
Model/@
Model/@view
Model/id/@
Model/id/@view
```

Keep support for:

```text
Model
Model/id
Model/id/action
Model?view=table
@profile
```

#### Tests to add/update

```text
tests/frontend/tests/core/Router.test.js
```

Test cases:

```js
parseRoute('AgentActor/@')
parseRoute('AgentActor/@table')
parseRoute('AgentActor/1/@')
parseRoute('AgentActor/1/@item')
parseRoute('AgentActor/1/run')
parseRoute('@profile')
buildRoute({ type: 'detail', model: 'AgentActor', id: '1', isViewRoute: true })
```

### Phase 2 — Schema-driven renderer resolution

Update `resolveRoute()` to resolve `@view` through `schema.ui.renderer` first.

Test cases:

```js
resolveRoute(parseRoute('AgentActor/@table'), getSchema)
  -> { tag: 'ntx-table', attrs: { model: 'AgentActor' } }

resolveRoute(parseRoute('AgentActor/1/@item'), getSchema)
  -> { tag: 'ntx-agent', attrs: { ref: 'AgentActor/1', display: 'lg' } }
```

### Phase 3 — Backend class-name read mirrors

Modify direct routes first:

```text
packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py
```

Add:

```text
GET /{ClassName}/{id:int}
```

mirroring:

```text
GET /{tablename}/{id:int}
```

Keep `$id` unchanged.

Then mirror in actor routing:

```text
packages/n3tx-actors/src/n3tx_actors/api/network_api.py
```

### Phase 4 — Backend HTML entrypoints

Add:

```text
GET /{ClassName}/@
GET /{ClassName}/@{view}
GET /{ClassName}/{id:int}/@
GET /{ClassName}/{id:int}/@{view}
```

These return HTML shell/page responses, not JSON.

Start with full-page shell output. Fragment support can be added later if needed.

### Phase 5 — App migration

Gradually migrate app shells/sidebar/topbar links from:

```text
#AgentActor
#AgentActor/1
```

to:

```text
#AgentActor/@
#AgentActor/1/@
```

### Phase 6 — Future class-name API grammar migration

Decide whether class-name routes become the preferred API grammar.

Questions for this phase:

- Should `$id` move to `/ClassName/id`?
- Should CRUD writes be mirrored under class-name paths?
- Should method routes mirror under class-name paths?
- How are nested resource URLs represented?

---

## 13. File-by-File Implementation Guide

### 13.1 Frontend core router

File:

```text
packages/n3tx-core/src/n3tx_core/static/core/Router.js
```

Tasks:

1. Normalize route paths by trimming leading/trailing slashes.
2. Extend `parseRoute()` for `@` view segments.
3. Extend `buildRoute()` for view routes.
4. Add `resolveViewTag()` helper.
5. Update `resolveRoute()` to use view-aware resolution.
6. Preserve current behavior for non-`@` routes.

### 13.2 Router component

File:

```text
packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js
```

Likely no major changes needed if `Router.resolved` continues returning `{ tag, attrs, title }`.

Verify that mounted components receive `router` attrs as today.

### 13.3 Sidebar links

Files:

```text
packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.js
packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar-link-item.js
```

Initial phase can keep old route generation.

Later app migration may update generated links to use explicit `@` defaults:

```text
Model/@
Model/id/@
```

### 13.4 Direct backend routes

File:

```text
packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py
```

Tasks:

1. Extract shared read-instance logic if necessary.
2. Register class-name read mirror route.
3. Register class-name HTML routes.
4. Ensure route order prevents `@` conflicts.
5. Preserve OpenAPI clarity; hide HTML routes from schema if noisy.

### 13.5 Actor backend routes

File:

```text
packages/n3tx-actors/src/n3tx_actors/api/network_api.py
```

Tasks:

1. Mirror direct-route behavior for Level 3 actor routing.
2. Preserve two-tier auth behavior.
3. Ensure class-name aliases dispatch to the same actor/model handlers as table-name routes.

### 13.6 SSR / HTML rendering helper

Potential files:

```text
packages/n3tx-core/src/n3tx_core/api/backend.py
packages/n3tx-core/src/n3tx_core/ssr/html.py
new: packages/n3tx-core/src/n3tx_core/ssr/views.py
```

Recommended helper signature:

```python
def render_model_view(
    *,
    model_class: type,
    id: int | None,
    view: str | None,
    scope: str,
    request=None,
) -> HTMLResponse:
    ...
```

---

## 14. Test Coverage Audit and Regression Test Plan

This refactor changes route grammar and route registration. The test suite must prove two things at the same time:

1. **new `@` grammar works exactly as designed**
2. **all legacy routes keep working exactly as before**

The goal is not merely “some tests pass.” The goal is to make regressions obvious at the exact boundary where they occur: parser, resolver, component mount, sidebar link, direct FastAPI route, actor route, SSR HTML entrypoint, or app-level navigation.

### 14.1 Current coverage audit

Current relevant coverage exists, but it is incomplete for this architecture.

| Area | Existing tests | What is covered now | Main gaps for this refactor |
|---|---|---|---|
| Pure route functions | `tests/frontend/tests/core/route-functions.test.js` | `parseRoute`, `buildRoute`, `resolveRoute` for `Model`, `Model/id`, `Model/id/action`, `@app`, `?view=` | no `@` path-segment routes, no trailing slash normalization, no explicit method-vs-view collision tests |
| Router actor state | `tests/frontend/tests/core/Router.test.js`, `tests/frontend/tests/integration/router-navigation.test.js` | navigation stack, hash sync, back behavior, resolved getter | no hash refresh tests for `#Model/@`, no back-stack tests for view routes, no same-route no-op tests for view routes |
| Router DOM mount | `tests/frontend/tests/components/ntx-router.test.js` | slot/home state, default hash sync, basic deep-link mount | no view-route mount assertions, no schema renderer mount assertions, no chrome behavior for deep-linked `@` routes |
| Sidebar | `tests/frontend/tests/components/ntx-sidebar.test.js` | model parsing, route templates, dropdown fallback, selected state for `#Product`, bare `#` home fix | no selected-state support for `#Product/@`, no generated `@` default routes after migration, no `@view` link dispatch |
| Sidebar record links | `tests/frontend/tests/components/ntx-sidebar-link-item.test.js` | record link currently renders `href="#Model/id"` | must update/add tests when record links migrate to `href="#Model/id/@"` |
| Direct FastAPI routes | `packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py`, `examples/core/tests/*` | helper functions and existing table-name API behavior | no class-name mirror route tests, no `/ClassName/@` HTML tests, no route-order conflict tests |
| Actor API routes | `packages/n3tx-actors/src/n3tx_actors/api/tests/test_network_api.py`, `examples/actors/tests/*` | schema route, table-name CRUD, method routes, parent-child routes | no class-name mirrors, no actor HTML route parity, no route-order conflict tests |
| SSR/static shell | `packages/n3tx-core/src/n3tx_core/tests/unit/test_ssr.py` | root/index SSR modes, schema injection, bundle/full modes | no per-model HTML view entrypoints, no mounted component injection assertions |
| Identity contracts | `test_proto_dump.py`, `test_populate.py`, frontend `NTT.test.js`, nested integration tests | `$schema`, `$id`, hrefs, nested refs in current API | no tests proving `/ClassName/id` mirror preserves `$id=/tablename/id` initially |
| App/E2E navigation | frontend Playwright + examples e2e | existing UI navigation and forms | no browser-level regression around `#Model/@`, refresh, dashboard/home, or direct `/ClassName/@` HTML entrypoints |

### 14.2 Required test commands by layer

Use narrow commands during implementation, then full commands at phase boundaries.

```bash
# Frontend unit/integration
cd /workspace/tests/frontend && npx vitest run tests/core/route-functions.test.js
cd /workspace/tests/frontend && npx vitest run tests/core/Router.test.js tests/integration/router-navigation.test.js
cd /workspace/tests/frontend && npx vitest run tests/components/ntx-router.test.js tests/components/ntx-sidebar.test.js tests/components/ntx-sidebar-link-item.test.js
cd /workspace/tests/frontend && npx vitest run

# Core backend
cd /workspace && python3 -m pytest packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py
cd /workspace && python3 -m pytest packages/n3tx-core/src/n3tx_core/tests/unit/test_ssr.py
cd /workspace && python3 -m pytest examples/core/tests/

# Actor backend
cd /workspace && python3 -m pytest packages/n3tx-actors/src/n3tx_actors/api/tests/test_network_api.py
cd /workspace && python3 -m pytest examples/actors/tests/

# Frontend browser smoke/E2E after route UI migration
cd /workspace/tests/frontend && npx playwright test --config=tests/e2e/playwright.config.js
cd /workspace/tests/frontend && npx playwright test --config=tests/e2e/veille.playwright.config.js
```

### 14.3 Phase 1 tests — pure frontend route grammar

Primary file:

```text
tests/frontend/tests/core/route-functions.test.js
```

#### `parseRoute(route)` must cover every new route form

Add these exact cases:

| Input | Expected important fields | Why it matters |
|---|---|---|
| `Product/@` | `{ type:'model', model:'Product', isViewRoute:true, view:null }` | collection default view |
| `Product/@list` | `view:'list'` | collection named list view |
| `Product/@table` | `view:'table'` | collection table view |
| `Product/@custom-card` | `view:'custom-card'` | hyphenated custom view names |
| `Product/@ntx-custom-card` | `view:'ntx-custom-card'` | explicit component-like view names |
| `Product/@table?limit=10&offset=20` | `params:{limit:'10', offset:'20'}` | query params survive view route parsing |
| `Product/3/@` | `{ type:'detail', model:'Product', id:'3', isViewRoute:true, view:null }` | member default view |
| `Product/3/@item` | `view:'item'` | member item/card view |
| `Product/3/@detail` | `view:'detail'` | member detail view |
| `Product/3/@chat?thread=abc` | `view:'chat', params:{thread:'abc'}` | custom member view with params |
| `Product/3/run` | `{ type:'action', action:'run', isViewRoute:undefined/false }` | method route remains method route |
| `Product/3/@run` | `{ type:'detail', view:'run', isViewRoute:true }` | view named same as method stays view |
| `@profile` | app route unchanged | root app route not confused with view marker |
| `@settings?tab=security` | params preserved | app params unchanged |
| `` | home unchanged | home route unchanged |
| `null`, `undefined`, `42`, `{}` | home unchanged | bad input unchanged |

#### Path normalization edge cases

If implementation trims leading/trailing slashes as planned, add:

| Input | Expected canonical parse |
|---|---|
| `/Product/@table` | same as `Product/@table` |
| `Product/@table/` | same as `Product/@table` |
| `/Product/3/@item/` | same as `Product/3/@item` |
| `Product//3//@item` | either normalized deterministically or rejected as current behavior; decide and lock it |

Recommendation: trim leading/trailing slashes and filter empty path segments; test that behavior explicitly.

#### `buildRoute(parts)` must round-trip new shape

Add exact cases:

```js
expect(buildRoute({ type: 'model', model: 'Product', isViewRoute: true })).toBe('Product/@');
expect(buildRoute({ type: 'model', model: 'Product', isViewRoute: true, view: 'table' })).toBe('Product/@table');
expect(buildRoute({ type: 'detail', model: 'Product', id: '3', isViewRoute: true })).toBe('Product/3/@');
expect(buildRoute({ type: 'detail', model: 'Product', id: '3', isViewRoute: true, view: 'item' })).toBe('Product/3/@item');
expect(buildRoute({ type: 'detail', model: 'Product', id: '3', action: 'run' })).toBe('Product/3/run');
expect(buildRoute({ type: 'detail', model: 'Product', id: '3', isViewRoute: true, view: 'chat', params: { thread: 'abc' } })).toBe('Product/3/@chat?thread=abc');
```

#### Round-trip tests

Every new route must satisfy:

```js
expect(buildRoute(parseRoute(route))).toBe(route);
```

Required route list:

```text
Product/@
Product/@list
Product/@table
Product/@table?limit=10&offset=20
Product/3/@
Product/3/@item
Product/3/@detail
Product/3/@chat?thread=abc
Product/3/run
Product/3/@run
@profile
@settings?tab=security
Product?view=table
```

### 14.4 Phase 1 tests — `resolveRoute(parsed, getSchema)`

Primary file:

```text
tests/frontend/tests/core/route-functions.test.js
```

Use representative schemas:

```js
const productSchema = {
  __name__: 'Product',
  title: 'Product',
  ui: {
    renderer: {
      list: 'ntx-products',
      table: 'ntx-product-table',
      item: 'ntx-product-card',
      detail: 'ntx-product-detail',
      chat: 'ntx-product-chat',
    }
  },
  methods: {
    run: { ui: { renderer: 'ntx-run-method' } }
  }
};
```

Required assertions:

| Route | Expected tag | Expected attrs | Notes |
|---|---|---|---|
| `Product/@` | `ntx-products` | `{ model:'Product' }` | default collection view uses `renderer.page || renderer.list` |
| `Product/@list` | `ntx-products` | `{ model:'Product' }` | semantic view maps through renderer |
| `Product/@table` | `ntx-product-table` | `{ model:'Product' }` | table view maps through renderer |
| `Product/@missing` | `ntx-missing` or rejected, per chosen fallback | document exact fallback |
| `Product/@table?limit=10` | `ntx-product-table` | includes `limit:'10'`, excludes `view` | params pass through |
| `Product/3/@` | `ntx-product-detail` | `{ ref:'Product/3', display:'lg' }` | default member view |
| `Product/3/@item` | `ntx-product-card` | `{ ref:'Product/3', display:'lg' }` | member item maps through renderer |
| `Product/3/@chat?thread=abc` | `ntx-product-chat` | includes `thread:'abc'` | custom member view |
| `Product/3/run` | `ntx-run-method` | `{ ref:'Product/3', method:'run', display:'lg' }` | method route unchanged |
| `Product/3/@run` | fallback or `renderer.run` | no `method` attr | view named `run` is not a method |
| `Product?view=table` | current `ntx-table` compatibility or schema-mapped `ntx-product-table` per implementation decision | `view` not passed through | legacy query compatibility |

Important regression assertions:

- `resolveRoute(parseRoute('Product/3/@run')).attrs.method` must be `undefined`.
- `resolveRoute(parseRoute('Product/3/run')).attrs.method` must be `'run'`.
- `resolveRoute(parseRoute('@profile')).tag` remains `'ntx-profile'`.
- unknown schema still produces stable fallbacks for all `@` routes.

### 14.5 Phase 1 tests — Router actor and hash sync

Primary files:

```text
tests/frontend/tests/core/Router.test.js
tests/frontend/tests/integration/router-navigation.test.js
```

Add tests proving the state actor treats new route strings exactly like old route strings.

Required tests:

1. `NAVIGATE('Product/@table')` sets `current` and updates hash to `#Product/@table`.
2. `NAVIGATE('Product/3/@item')` sets `current` and updates hash to `#Product/3/@item`.
3. Initial hash load from `#Product/@table` sets `current` without fake back history.
4. Initial hash load from `#Product/3/@item` sets `current` without fake back history.
5. Duplicate `NAVIGATE('Product/@table')` is a no-op.
6. `BACK()` from `Product/3/@item` returns to the previous route.
7. `BACK()` from a view route to root clears hash.
8. Reset navigation to home from a view route clears hash and stack.
9. `resolved` getter returns renderer-mapped tag for `Product/@table` when `getSchema` is provided.
10. Stack cap behavior still works when routes include `@` segments.

### 14.6 Phase 1 tests — `ntx-router` DOM mounting

Primary file:

```text
tests/frontend/tests/components/ntx-router.test.js
```

Existing tests only assert basic `#Product/9` deep-link mount. Add:

1. Deep-link `#Product/@table` mounts `<ntx-table model="Product">` or schema-selected table tag.
2. Deep-link `#Product/9/@item` mounts the schema-selected item tag with `ref="Product/9"` and `display="lg"`.
3. Deep-linked view route has router chrome hidden when no back history, matching current deep-link behavior.
4. Navigating from home slot to `Product/@table` removes the slot and mounts the view.
5. Navigating back to home from `Product/@table` restores the slot and removes the mounted view.
6. Mounted component gets `router="<router-name>"` when it has a `model` attribute and lacks a router attr.
7. Member view components without `model` attr do not receive unwanted router attr.

Test setup should mock `window.NTT.get('Product').schema` with `ui.renderer.table` and `ui.renderer.item` so the test proves schema-driven selection, not just fallback behavior.

### 14.7 Sidebar and navigation link tests

Primary files:

```text
tests/frontend/tests/components/ntx-sidebar.test.js
tests/frontend/tests/components/ntx-sidebar-link-item.test.js
```

#### Before sidebar migration

Add compatibility tests now:

1. A hash of `#Product/@` marks `Product` model section selected.
2. A hash of `#Product/@table` marks `Product` selected.
3. A hash of `#Product/3/@item` marks `Product` selected.
4. Existing `#Product` selected-state still works.
5. Existing app link selected-state `#@settings` still works.
6. Bare `href="#"` still dispatches home route `''`, not `'@'`.

#### When sidebar route generation migrates

Update/add tests:

1. Model header primary link/dispatch uses `Product/@` instead of `Product` when the migration flag/default changes.
2. Sidebar dropdown record link renders `href="#Product/5/@"` instead of `href="#Product/5"`.
3. Existing legacy record link behavior is either preserved behind compatibility mode or explicitly updated in one test.
4. `ntx-table` route-template dropdown fallback still mounts compact `ntx-list`, but its route target is `Product/@table` for main navigation.
5. Custom route-template renderer with `sidebar-label` keeps label behavior while using `@` route grammar.

### 14.8 Phase 3 tests — direct FastAPI class-name mirrors

Primary files:

```text
packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py
examples/core/tests/test_schema_endpoints.py
examples/core/tests/test_products_crud.py
```

Current direct-route unit coverage is weak for generated route tables. Add or create a dedicated direct-route test file if needed, e.g.:

```text
packages/n3tx-core/src/n3tx_core/tests/unit/test_classname_routes.py
```

Required route-generation tests:

1. `register_routes()` registers `/Product` schema route as before.
2. `register_routes()` registers `/Product/{id:int}` class-name read mirror for storable models.
3. `register_routes()` does not register duplicate class-name read mirrors for non-storable models.
4. `register_routes()` registers `/Product/@`, `/Product/@{view}` or equivalent concrete route shape.
5. `register_routes()` registers `/Product/{id:int}/@`, `/Product/{id:int}/@{view}`.
6. Existing table-name routes `/products`, `/products/{id:int}`, `/products/{id:int}/comment` are still present.
7. Route order places `@` routes before `/{id:int}` and method aliases when order matters.

Required behavior tests against a `TestClient`:

1. `GET /Product/1` returns status and JSON body identical to `GET /products/1`, except for allowed headers.
2. `GET /Product/1` preserves `$id` as `/products/1` in the first wave.
3. `GET /Product/1?populate=comments&depth=1` forwards query semantics exactly like `/products/1?populate=comments&depth=1`.
4. `GET /Product/999999` returns the same status/detail as `/products/999999`.
5. `GET /Product/not-an-int` does not match the `{id:int}` mirror and does not shadow `/Product/@...`.
6. `POST /Product/1` is not available unless/until full CRUD mirrors are explicitly implemented.
7. `PUT /Product/1` and `DELETE /Product/1` are not available unless/until full CRUD mirrors are explicitly implemented.
8. Schema endpoint `GET /Product` remains JSON Schema and is not confused with class-name list/data endpoint.

Required auth/access tests:

1. If `GET /products/1` requires/uses auth context, `GET /Product/1` must enforce the same auth behavior.
2. Owner-only protected resources return the same 403/404 behavior through both paths.
3. User injection behavior for methods is unaffected by adding class-name read mirrors.

### 14.9 Phase 4 tests — backend HTML/view entrypoints

Primary files:

```text
packages/n3tx-core/src/n3tx_core/tests/unit/test_ssr.py
new: packages/n3tx-core/src/n3tx_core/tests/unit/test_model_view_routes.py
examples/core/tests/test_static_pages.py or equivalent
```

Required HTML endpoint tests:

| Route | Expected |
|---|---|
| `GET /Product/@` | `200`, `Content-Type: text/html`, mounts collection default component |
| `GET /Product/@list` | `200`, HTML contains list renderer tag or boot metadata for list renderer |
| `GET /Product/@table` | `200`, HTML contains table renderer tag or boot metadata for table renderer |
| `GET /Product/1/@` | `200`, HTML contains detail/item renderer and `ref="Product/1"` or equivalent boot route |
| `GET /Product/1/@item` | `200`, HTML contains item renderer and member ref |
| `GET /Product/999999/@` | chosen behavior is explicit: either shell still loads and frontend handles 404, or backend returns 404; test whichever is chosen |
| `GET /Product/@unknown` | chosen fallback explicit: `ntx-unknown`, 404, or schema-error; test it |

Required invariants:

1. HTML routes never return JSON by accident.
2. HTML routes are `include_in_schema=False` if OpenAPI should not expose them.
3. HTML routes do not shadow `GET /Product` schema.
4. HTML routes do not shadow `GET /Product/{id:int}` mirror.
5. HTML routes preserve SSR schema injection if app SSR mode is enabled.
6. HTML routes include enough scripts/imports for custom elements used by the route.
7. Response should be deterministic for caching unless route-specific data is injected.

### 14.10 Phase 5 tests — actor route parity

Primary files:

```text
packages/n3tx-actors/src/n3tx_actors/api/tests/test_network_api.py
examples/actors/tests/test_schema_endpoints.py
examples/actors/tests/test_products_crud.py
```

Add route-generation tests:

1. `create_api_routes()` generates `/MockModel` schema as before.
2. `create_api_routes()` generates `/MockModel/{id:int}` class-name read mirror.
3. `create_api_routes()` generates `/MockModel/@` and member HTML routes if actor API owns HTML routes.
4. Existing `/mock_models`, `/mock_models/{id:int}`, `/mock_models/{id:int}/custom` remain present.
5. Parent-child routes remain present and unchanged.

Add behavior tests using mocked `NetworkAPI.request`:

1. `GET /MockModel/5` sends a TX equivalent to `GET /mock_models/5`: `name='get'`, `target='mock_models'`, `data.id=5`.
2. Query params `populate` and `depth` are forwarded.
3. `meta.user` and `meta.model_cls` are identical to table-name route behavior.
4. Error TX from class-name mirror maps to the same HTTP exception as table-name route.
5. Class-name mirror does not send `schema` TX; only `/MockModel` does.
6. `/MockModel/5/custom` is not added until method mirrors are intentionally implemented; if implemented, it must send the same method TX as `/mock_models/5/custom`.

### 14.11 Identity and `$id` regression tests

Primary files:

```text
packages/n3tx-core/src/n3tx_core/tests/unit/test_proto_dump.py
examples/core/tests/test_products_crud.py
examples/actors/tests/test_products_crud.py
tests/frontend/tests/core/NTT.test.js
tests/frontend/tests/integration/nested-entities.test.js
```

Required tests:

1. `GET /Product/1` response has `$schema` ending in `/Product`.
2. `GET /Product/1` response has `$id` ending in `/products/1`, not `/Product/1`, for the first wave.
3. `GET /products/1` and `GET /Product/1` return the same `id` and domain fields.
4. `NTT` still registers instances under `Product/1` when data arrives with `$id=/products/1`.
5. Existing nested hrefs such as `/products/1/comments/2` remain unchanged.
6. Populated nested child `$id` behavior remains unchanged.
7. Class-name mirror does not mutate stored hrefs or relation arrays.

### 14.12 Method/action collision tests

This is one of the most important regression surfaces.

Add tests covering a model with both:

```python
@expose_route('/run', methods=['POST'])
def run(self): ...
```

and schema renderer:

```json
ui.renderer.run = 'ntx-run-view'
```

Required frontend assertions:

```text
Product/1/run   -> action route, attrs.method='run'
Product/1/@run  -> view route, no attrs.method, tag='ntx-run-view'
```

Required backend assertions:

```text
POST /products/1/run      -> method handler
GET  /Product/1/@run      -> HTML/view route
GET  /Product/1/run       -> only exists if class-name method mirror is explicitly implemented
```

### 14.13 Route conflict and order tests

Route order bugs are likely. Add explicit tests that inspect route matching, not only route presence.

Required cases:

1. `/Product/@table` resolves to HTML route, not `/Product/{id:int}`.
2. `/Product/@` resolves to HTML route, not schema route.
3. `/Product/1/@item` resolves to member HTML route, not method route.
4. `/Product/1/run` remains a method/action route only where intentionally registered.
5. `/Product/abc` returns 404/422 and does not match `@` routes.
6. `/Product/@123` is treated as a view named `123` or rejected according to chosen validation; lock behavior.
7. `/Product/1/@123` same as above for member views.
8. Join/static routes like `/products/comments` still beat `/products/{id:int}`.
9. New class-name routes do not affect existing join routes.

### 14.14 Query parameter compatibility tests

Add tests at parser, resolver, backend mirror, and HTML-route layers.

Frontend:

1. `Product/@table?limit=10&offset=20` passes `limit` and `offset` to the mounted component.
2. `Product/1/@item?tab=history` passes `tab` to the mounted component.
3. `Product?view=table&limit=10` remains supported and does not pass `view` as attr.
4. `Product/@table?view=list` behavior is explicit; recommendation: `@table` wins and query `view` is filtered/ignored. Add a test.

Backend:

1. `/Product/1?populate=comments&depth=1` mirrors `/products/1?populate=comments&depth=1`.
2. `/Product/@table?limit=10` preserves query data in boot metadata or component attrs if server injects it.

### 14.15 Invalid and boundary input tests

Frontend route parser:

| Input | Expected |
|---|---|
| `Product/@/extra` | reject or deterministic parse; choose and test |
| `Product/1/@item/extra` | reject or deterministic parse; choose and test |
| `Product/` | same as `Product` if normalized |
| `/Product` | same as `Product` if normalized |
| `Product/@?x=1` | default collection view with params |
| `Product/1/@?x=1` | default member view with params |
| `Product/@%E2%9C%93` | decide whether decoded view names are allowed; test |
| `Product/@../../x` | must not generate dangerous component tag/path; reject or sanitize |

Backend view validation:

1. View names should be limited to a safe token pattern such as `[A-Za-z0-9_-]+`.
2. Invalid view names return 400, not a file/path traversal attempt.
3. HTML route rendering escapes attrs in injected HTML.

### 14.16 App/E2E tests

Add browser-level tests only after unit/integration coverage is green.

Core example E2E or frontend Playwright:

1. Navigate to `/#Product/@` and verify list surface renders.
2. Navigate to `/#Product/@table` and verify table surface renders.
3. Navigate to `/#Product/1/@` and verify detail item renders.
4. Refresh on `/#Product/1/@` and verify same route remounts.
5. Use browser back from `/#Product/1/@` to previous route.
6. Dashboard/home route still works after the recent bare `#` fix.

Veille E2E:

1. `/#AgentActor/@` renders agents collection/dashboard-equivalent surface if migrated.
2. `/#AgentActor/1/@` renders agent detail with `ntx-agent`.
3. `/#AgentActor/1/@chat` renders or mounts chat if schema renderer declares it.
4. Sidebar selection highlights the correct model for `#AgentActor/@...` routes.
5. Refresh preserves route and does not blank the main panel.

### 14.17 Coverage-gated acceptance checklist

Do not consider the refactor complete until all rows are checked.

| Layer | Required proof |
|---|---|
| Parser | every new route grammar branch has direct unit tests |
| Builder | every new parsed shape round-trips through `buildRoute` |
| Resolver | schema renderer lookup, fallback, params, and method-vs-view collision tested |
| Router state | hash sync, initial load, back stack, reset home tested for `@` routes |
| Router DOM | `ntx-router` mounts collection/member view routes correctly |
| Sidebar | selected-state and generated links support `@` routes when migration happens |
| Direct API | `/ClassName/id` mirrors `/tablename/id`; legacy API unchanged |
| Actor API | Level 3 actor routing has parity with direct API |
| HTML routes | `/ClassName/@...` returns HTML and cannot shadow schema/data routes |
| Identity | `$id` remains legacy table URL until explicit future migration |
| Security | invalid view tokens cannot inject tags/paths/scripts |
| E2E | refresh/back/navigation do not blank the app |

### 14.18 Suggested implementation order for tests

Follow this order to keep failures diagnostic:

1. Add failing parser tests.
2. Implement parser.
3. Add failing resolver tests.
4. Implement renderer resolution.
5. Add Router actor/hash tests.
6. Add `ntx-router` DOM tests.
7. Add direct backend route-generation and mirror behavior tests.
8. Implement direct backend mirrors.
9. Add HTML route tests.
10. Implement HTML routes.
11. Add actor route parity tests.
12. Implement actor route parity.
13. Add sidebar migration tests when changing sidebar generation.
14. Add E2E smoke tests last.

---

## 15. Risks and Mitigations

| Risk | Why it matters | Mitigation |
|---|---|---|
| Duplicate API identities | `/agents/1` and `/AgentActor/1` both identify same entity | Keep `$id` table-name based in first waves; document class routes as mirrors |
| Router misparses `@` | `@table` could be read as ID | Update parser before app migration; add tests |
| Custom components bypass schema | `@custom` could mount arbitrary frontend tags | Resolve through `schema.ui.renderer` first; optionally restrict fallback later |
| Backend route conflicts | `/ClassName/@table` could conflict with `{id}` | Use `{id:int}` and register `@` routes before generic aliases |
| Actor/direct route drift | Level 3 actor routing may differ from direct routes | Implement direct first, then mirror in `network_api.py` with tests |
| `$id` migration breaks refs | Current runtime expects table-name hrefs | Defer `$id` migration |
| Hash routes are not true path URLs | Direct `/ClassName/1/@` refresh requires backend HTML route | Add backend HTML entrypoints in later phase |

---

## 16. Open Questions

These do not block Phase 1, but should be decided before later phases.

1. When, if ever, should `$id` migrate from `/agents/1` to `/AgentActor/1`?
2. Should class-name mirrors support only GET initially, or full CRUD/methods?
3. Should `/ClassName/@view` return full documents only, or also fragments later?
4. Should arbitrary `ntx-${view}` fallback be allowed in production, or only schema-declared renderers?
5. Should friendly aliases such as `Agent -> AgentActor` be supported later?
6. How should nested resources map into class-name grammar?
7. Should class-name API routes be advertised in OpenAPI immediately or hidden during migration?

---

## 17. Recommended First Commit Sequence

### Commit 1: Router grammar

```text
feat(frontend): Add @ view route grammar [wave]
```

Changes:

- `Router.js` parse/build/resolve updates
- router unit tests

### Commit 2: Schema-driven view resolution

```text
feat(ui): Resolve @ routes through schema renderers [wave]
```

Changes:

- `resolveViewTag()` helper
- tests for renderer lookup/fallbacks

### Commit 3: Class-name read mirrors

```text
feat(core): Add class-name read route mirrors [wave]
```

Changes:

- direct FastAPI route mirror
- unit/example tests

### Commit 4: HTML view entrypoints

```text
feat(core): Add class-name HTML view entrypoints [wave]
```

Changes:

- HTML shell rendering helper
- `/ClassName/@...` routes
- tests/smoke docs

### Commit 5: Actor route parity

```text
feat(actors): Mirror class-name route grammar in actor API [wave]
```

Changes:

- `network_api.py` parity
- actor tests

---

## 18. Final Recommendation

Adopt this architecture as the next N3TX routing direction:

```text
/{tablename}/...       current/legacy data API
/{ClassName}/...       new class-name model API grammar
/{ClassName}/@...      HTML/view entrypoints
#{ClassName}/@...      frontend router view grammar during migration
```

Use these rules strictly:

1. `@` means view/html, never data.
2. `@view` resolves through `schema.ui.renderer` before fallback.
3. Existing table-name routes stay untouched.
4. `$id` stays table-name based until identity migration is explicitly planned.
5. Router grammar lands before backend HTML entrypoints.

This design is not the purest possible HTTP representation model, but it is the best practical fit for the current N3TX architecture. It gives the project a clear migration path toward model-centric hypertext while preserving existing apps and APIs.
