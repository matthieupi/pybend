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

## 14. Test Plan

### 14.1 Frontend unit tests

Run:

```bash
cd /workspace/tests/frontend && npx vitest run
```

Add focused tests for:

- parsing `Model/@`
- parsing `Model/@table`
- parsing `Model/1/@`
- parsing `Model/1/@item`
- preserving `Model/1/run`
- preserving `@profile`
- resolving view routes through `schema.ui.renderer`
- preserving `?view=` compatibility

### 14.2 Backend direct route tests

Run:

```bash
cd /workspace && python3 -m pytest packages/n3tx-core/src/n3tx_core/tests/unit/
cd /workspace && python3 -m pytest examples/core/tests/
```

Add tests for:

- `GET /Product/{id}` mirrors `GET /products/{id}`
- `$id` remains `/products/{id}` initially
- `GET /Product/@` returns HTML
- `GET /Product/{id}/@` returns HTML
- `GET /Product/@table` resolves/embeds table view

### 14.3 Actor route tests

Run:

```bash
cd /workspace && python3 -m pytest packages/n3tx-actors/src/n3tx_actors/tests/
cd /workspace && python3 -m pytest examples/actors/tests/
```

Add equivalent class-name mirror tests for actor routing once implemented.

### 14.4 Veille/app smoke tests

Manual smoke routes:

```text
http://localhost:4000/#AgentActor/@
http://localhost:4000/#AgentActor/@table
http://localhost:4000/#AgentActor/1/@
http://localhost:4000/#AgentActor/1/@item
```

Expected:

- refresh preserves the hash route
- router remounts the correct component
- data fetches still succeed through current data paths

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
