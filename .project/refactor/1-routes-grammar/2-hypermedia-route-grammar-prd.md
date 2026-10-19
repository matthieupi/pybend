# PRD: Hypermedia Route Grammar

## Problem Statement

N3TX currently gives developers a working schema-driven application from model definitions, but its route grammar is split and increasingly overloaded. Schema endpoints use model class names, while data endpoints use table names, and frontend navigation encodes renderer selection through query parameters or positional route segments. This works for the existing CRUD and method flows, but it becomes fragile when N3TX needs richer model-centric hypermedia entrypoints that can render collection and member views directly.

The immediate user-facing problem is that developers cannot express “show this model/member using this semantic view” with a clear, stable, schema-driven route. A route such as a model plus a table view can be misread as a member ID; a member route plus a view name can be misread as a method/action; and direct browser refreshes of view-specific routes require a backend route that does not yet exist. This ambiguity makes the framework harder to teach, harder to test, and riskier to extend toward hypertext-oriented applications.

The product problem is therefore not just a missing route form. It is a missing grammar boundary between data, schema, action, and presentation. N3TX needs an additive route architecture that preserves every existing app contract while introducing an explicit view namespace for model-centric HTML and component routes.

## Solution

Introduce an incremental dual route grammar that keeps existing table-name API routes unchanged while adding class-name model routes and an explicit `@` view namespace.

From the user’s perspective, existing apps continue to work. Developers can still use table-name API routes for JSON data, class-name roots for schema, and existing hash routes for navigation. In addition, they gain clear routes for model views and member views: a collection can be opened with a default view or named view, and a member can be opened with a default detail view or named view. The `@` marker means view/HTML/component route only; it never means data and never means method invocation.

Frontend route resolution will use the model schema as the source of truth for semantic view names. A semantic view like `table`, `item`, `detail`, `chat`, or a custom view resolves through the schema’s renderer declaration first, then through framework fallbacks. Backend route handling will add class-name read mirrors and server-served HTML entrypoints that bootstrap the same frontend component system, rather than creating a separate server-side component framework.

The solution is intentionally phased:

- First, lock and implement frontend parsing, building, route resolution, hash sync, and DOM mounting for `@` view routes.
- Then add direct backend class-name read mirrors while preserving table-name identity in payloads.
- Then add backend HTML/view entrypoints that return full HTML shells and do not shadow schema or data routes.
- Then bring actor-routed APIs to parity with direct routes.
- Finally, migrate first-party app navigation where appropriate, backed by browser regression tests.

## User Stories

1. As an app developer, I want existing table-name JSON API routes to keep working, so that upgrading N3TX does not break my application.
2. As an app developer, I want existing class-name schema endpoints to keep working, so that runtime schema loading remains stable.
3. As an app developer, I want to navigate to a model collection’s default view with an explicit view route, so that collection pages are not confused with schema or data endpoints.
4. As an app developer, I want to navigate to a model collection’s named table view, so that I can expose tabular views without query-parameter conventions.
5. As an app developer, I want to navigate to a model collection’s named custom view, so that app-specific components can be addressed cleanly.
6. As an app developer, I want to navigate to a model member’s default detail view, so that member pages have a stable model-centric URL.
7. As an app developer, I want to navigate to a model member’s item view, so that compact and detailed renderers can be selected semantically.
8. As an app developer, I want to navigate to a model member’s chat or agent view, so that rich interactive projections can live behind model routes.
9. As an app developer, I want a view named like a method to remain a view when prefixed with `@`, so that route intent is unambiguous.
10. As an app developer, I want a method/action route without `@` to remain a method/action route, so that existing custom method behavior remains stable.
11. As an app developer, I want root app routes such as profile and settings to remain distinct from model view routes, so that shell navigation is not broken.
12. As an app developer, I want semantic view names to resolve through the model schema first, so that the backend remains the source of truth for presentation hints.
13. As an app developer, I want framework defaults when a schema does not declare a renderer, so that zero-configuration models still render.
14. As an app developer, I want custom semantic views to have a deterministic fallback, so that prototyping remains ergonomic.
15. As an app developer, I want query parameters on view routes to pass through to the mounted component, so that pagination, filters, tabs, and display options still work.
16. As an app developer, I want internal route parameters such as view selection to be filtered from component attributes when appropriate, so that components receive clean external inputs.
17. As an app developer, I want legacy query-based view selection to remain supported, so that old links and bookmarks continue to work during migration.
18. As an app developer, I want path-based view selection to take precedence over query-based view selection, so that explicit route grammar has predictable behavior.
19. As an app developer, I want leading and trailing slashes in hash routes to normalize safely, so that route handling is robust to minor URL variations.
20. As an app developer, I want malformed extra route segments to be handled deterministically, so that router bugs do not silently mount the wrong component.
21. As a frontend framework maintainer, I want route parsing to expose explicit view metadata, so that downstream routing code does not infer view intent from raw strings.
22. As a frontend framework maintainer, I want route building to round-trip parsed view routes, so that navigation helpers can generate canonical URLs.
23. As a frontend framework maintainer, I want route resolution to remain a pure function, so that parser and resolver behavior can be tested in isolation.
24. As a frontend framework maintainer, I want router state to treat view routes like normal routes, so that hash sync, history stack, back navigation, and reset behavior remain consistent.
25. As a frontend framework maintainer, I want the router DOM container to mount the resolved component tag for view routes, so that view selection flows through the same component system.
26. As a frontend framework maintainer, I want member view components to avoid accidental method attributes, so that a view route cannot trigger method behavior.
27. As a frontend framework maintainer, I want collection view components to receive router context when appropriate, so that nested navigation keeps working.
28. As a frontend framework maintainer, I want deep-linked view routes to hide navigation chrome when there is no back history, so that direct refresh behavior matches current deep-link behavior.
29. As a frontend framework maintainer, I want home navigation to clear view routes correctly, so that the application never gets stuck in a stale mounted view.
30. As an end user, I want refreshing a view-specific route to show the same view again, so that browser refresh does not blank the app.
31. As an end user, I want browser back from a model view to return to the previous route, so that navigation feels native.
32. As an end user, I want sidebar selection to reflect model view routes, so that navigation state remains understandable.
33. As an end user, I want dashboard/home links to remain home links, so that top-level app navigation is not confused with model views.
34. As an API consumer, I want existing table-name list, create, read, update, delete, and method routes to remain unchanged, so that existing integrations keep working.
35. As an API consumer, I want a class-name read mirror for model instances, so that model-centric route grammar can be introduced incrementally.
36. As an API consumer, I want class-name read mirrors to return the same entity data as table-name reads, so that the mirror is behaviorally trustworthy.
37. As an API consumer, I want class-name read mirrors to preserve query semantics such as population depth, so that data shape controls remain consistent.
38. As an API consumer, I want class-name read mirrors to enforce the same authorization behavior as table-name reads, so that the mirror does not bypass access control.
39. As an API consumer, I want missing records to return the same errors through class-name and table-name routes, so that error handling stays predictable.
40. As an API consumer, I want class-name write routes to stay unavailable until deliberately implemented, so that read mirrors do not imply full CRUD migration.
41. As a frontend runtime maintainer, I want payload instance identity to remain table-name based in this phase, so that caches and references do not break.
42. As a frontend runtime maintainer, I want schema identity to remain class-name based, so that schema lookup remains stable.
43. As a backend framework maintainer, I want class-name view routes to return HTML, so that direct browser requests can bootstrap the application at a model view.
44. As a backend framework maintainer, I want model HTML routes to use the existing frontend shell and component runtime, so that N3TX does not grow a disconnected server-side component system.
45. As a backend framework maintainer, I want collection HTML routes to mount collection renderers, so that model collection pages can load directly.
46. As a backend framework maintainer, I want member HTML routes to mount member renderers, so that entity detail pages can load directly.
47. As a backend framework maintainer, I want unknown view names to have documented behavior, so that apps and tests agree on fallback or rejection.
48. As a backend framework maintainer, I want unsafe view tokens to be rejected or sanitized, so that route grammar cannot become an injection or traversal vector.
49. As a backend framework maintainer, I want route order to prevent `@` segments from being captured as IDs, so that view routes cannot be shadowed by item routes.
50. As a backend framework maintainer, I want HTML routes hidden from generated API documentation if they are not part of the JSON API surface, so that OpenAPI remains clear.
51. As an actor-system maintainer, I want actor-routed HTTP APIs to mirror direct-route behavior, so that Level 3 apps do not diverge from Level 1/2 apps.
52. As an actor-system maintainer, I want class-name read mirrors in actor routing to dispatch to the same model actor target as table-name reads, so that behavior and authorization remain centralized.
53. As an actor-system maintainer, I want actor route metadata to preserve user and model context, so that two-tier authorization stays intact.
54. As an actor-system maintainer, I want actor route errors to map to the same HTTP responses as existing routes, so that clients do not need route-mode-specific error handling.
55. As a tester, I want parser, builder, resolver, state, DOM, backend, actor, and browser tests, so that regressions identify the exact failing boundary.
56. As a tester, I want tests proving legacy routes still work, so that additive grammar changes cannot accidentally become breaking changes.
57. As a tester, I want tests proving method routes and view routes are distinct, so that the most important grammar collision is locked down.
58. As a maintainer, I want this migration to happen in small phases, so that each layer can be reviewed and verified independently.
59. As a maintainer, I want future identity migration deferred, so that route grammar can improve without destabilizing references.
60. As a maintainer, I want future full class-name CRUD and method mirrors deferred, so that this release can focus on read mirrors and view entrypoints.

## Implementation Decisions

- Adopt an additive dual grammar: table-name routes remain the compatibility JSON API, class-name roots remain schema endpoints, class-name instance routes become read mirrors, and `@` segments represent view/HTML/component routes.
- Treat `@` as a reserved semantic marker inside model routes. It always means view route and never means ID, JSON data, or method invocation.
- Preserve root app routes that begin with `@` as shell/application routes, separate from model view routes.
- Keep exact model class names as the route model identifier in the first waves. Friendly aliases are deferred.
- Keep payload `$id` table-name based during this migration phase. Class-name instance routes are mirrors, not a new canonical identity system.
- Keep schema identity class-name based. The class-name root remains the schema/type endpoint and is not converted into a collection API endpoint.
- Add frontend route metadata for view routes, including explicit view name and view-route status, while preserving existing route type shapes for model, detail, action, app, and home routes.
- Normalize leading and trailing route slashes and empty internal path segments deterministically in the frontend router.
- Resolve semantic view names through schema renderer declarations first.
- For default collection views, prefer page renderer, then list renderer, then the framework list fallback.
- For default member views, prefer detail renderer, then item renderer, then the framework item fallback.
- For named known views, use schema renderer if declared, then framework known-view fallback.
- For custom named views, allow deterministic component fallback unless a later security decision restricts arbitrary component fallback to schema-declared renderers only.
- Preserve legacy query-based collection view selection during migration, but prefer the new path-based `@` grammar for new links.
- Filter internal routing controls from mounted component attributes, while passing through user-facing query parameters.
- Keep frontend route resolution as a deep module with a small interface: parse a string, build a string, resolve parsed route plus schema into a mount instruction.
- Keep router state management independent from DOM mounting. The state actor owns current route, stack, hash sync, back navigation, and reset behavior.
- Keep the router component as a thin mount container that consumes resolved mount instructions and does not know grammar details.
- Add class-name read mirrors only for storable models in the first backend phase.
- Do not add class-name create, update, delete, or method mirrors in the first backend phase unless explicitly planned later.
- Reuse existing read, authorization, population, and serialization behavior for class-name read mirrors rather than duplicating logic.
- Add server HTML/view entrypoints that return full HTML app shells and mount the same frontend component system.
- Do not build a separate server-side component rendering framework in this phase.
- Validate backend view names with a safe token contract before using them to generate mounted component markup.
- Ensure backend route registration orders specific view routes before generic instance and method-like routes where matching order matters.
- Use integer-constrained instance route parameters so `@view` cannot be parsed as an ID.
- Preserve join/static collection route precedence over generic instance routes.
- Bring actor-routed APIs to parity after direct-route behavior is implemented and tested.
- Preserve two-tier actor authorization by dispatching class-name read mirrors through the same actor targets and metadata as table-name reads.
- Treat sidebar and app link migration as a later phase after parser, resolver, backend, and actor route behavior are green.

## Testing Decisions

- Tests should validate external behavior and contracts, not private implementation details.
- The pure route grammar module should be tested exhaustively because it is a deep module: a small API encapsulates parsing, building, and resolution for many downstream consumers.
- Parser tests must cover all new collection and member view forms, root app routes, malformed inputs, normalization, query params, and method-versus-view collisions.
- Builder tests must prove every supported parsed route shape can produce the canonical route string.
- Round-trip tests must prove canonical routes can parse and rebuild without semantic loss.
- Resolver tests must prove schema renderer lookup, default fallback order, custom fallback behavior, query pass-through, and internal parameter filtering.
- Router state tests must prove hash sync, initial hash load, duplicate navigation no-ops, back stack behavior, reset behavior, and resolved route behavior for view routes.
- Router DOM tests must prove deep-linked and navigated view routes mount the expected component tag with the expected public attributes.
- Sidebar tests must prove selected-state compatibility for new `@` model routes before link generation is migrated.
- Direct backend tests must prove route generation, class-name read mirror behavior, identity preservation, auth parity, query forwarding, error parity, unsupported writes, and route conflict behavior.
- HTML route tests must prove view routes return HTML, do not shadow schema or instance routes, mount the intended component or boot metadata, and reject or sanitize unsafe views.
- Actor route tests must prove route generation, TX dispatch equivalence, query forwarding, metadata preservation, error mapping, and direct/actor parity.
- Identity regression tests must prove `$schema` remains class-name based and `$id` remains table-name based through class-name mirrors.
- Browser tests should be added after lower-level tests pass, covering direct navigation, refresh, back behavior, sidebar selection, and legacy route compatibility.
- Existing frontend route function tests, router state tests, router component tests, sidebar tests, direct route unit tests, SSR tests, actor API tests, and example application tests are the main prior art for this work.
- The acceptance bar is layered green coverage: parser, builder, resolver, router state, DOM mount, direct API, HTML routes, actor parity, identity, security boundaries, and browser refresh/back flows.

## Out of Scope

- Migrating `$id` from table-name URLs to class-name URLs.
- Making class-name instance routes the canonical API identity.
- Adding full class-name CRUD write mirrors.
- Adding class-name method/action mirrors unless a later phase explicitly decides to do so.
- Introducing friendly route aliases for model classes.
- Designing nested resource class-name grammar.
- Building a server-side component framework or full server-rendered component tree.
- Replacing the existing hash router with browser history path routing.
- Removing support for legacy table-name API routes.
- Removing support for legacy query-based view selection during the migration window.
- Migrating all first-party app links in the first implementation slice.
- Redesigning schema renderer shape beyond the existing flat renderer map.

## Further Notes

The central architectural choice is to separate grammar migration from identity migration. N3TX can introduce clearer model-centric routes and server-served view entrypoints without destabilizing frontend caching, references, nested resources, or existing API clients.

The most important regression surface is the method-versus-view collision. A route without `@` remains an action route; the same suffix with `@` is a view route. This distinction should be treated as a non-negotiable contract across frontend and backend tests.

The second most important regression surface is route shadowing. Backend route order and constrained instance parameters must make it impossible for a view route to be captured as an ID route.

The recommended build order is test-first by layer: add failing frontend grammar tests, implement frontend grammar, add failing backend direct route tests, implement direct routes, add failing actor parity tests, implement actor parity, then add browser-level refresh and navigation tests.
