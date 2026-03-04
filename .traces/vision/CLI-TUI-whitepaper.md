# CLI & TUI Applied: A Technical Whitepaper

> *How principles from CLI/TUI can reshape our architecture -- and where they cannot.*
> *Companion to the [propositions document](12-01-cli-tui-propositions.md).*

---

## Abstract

N3TX is a schema-driven framework where a Python model definition is the single source of truth for the entire stack: API, validation, storage, UI, permissions. The web frontend already proves this -- `form.js` reads JSON Schema and renders forms without knowing the model's implementation. This whitepaper examines what happens when we extend that schema contract to the terminal.

The CLI/TUI landscape has matured dramatically since 2020. Typer (66M monthly PyPI downloads) brings type-hint-driven commands. Rich (55.6K GitHub stars) brings beautiful terminal rendering. Textual (34.5K stars) brings CSS-like TUI development. Together, they form a cohesive ecosystem that maps cleanly to N3TX's architecture. More importantly, the 18 years of framework CLI history -- from Django's `manage.py` to Prisma's schema-first generation to Create React App's cautionary deprecation -- reveal a clear pattern: the CLIs that endure are the ones that **encode framework knowledge**, not just wrap shell commands.

N3TX's unique advantage is that its schema carries behavioral intent -- validation constraints, UI widget hints, access control rules, method signatures -- not just structural types. No other framework's CLI can derive terminal forms, inspect commands, and admin dashboards from the same source that drives the web UI. This paper explores how to exploit that advantage, what principles to import from the CLI/TUI world, where the boundaries are, and a phased path forward.

---

## 1. Introduction: Why This Matters Now

Three forces converge to make CLI/TUI investment timely for N3TX.

**Force 1: The developer experience gap.** The Atlassian State of Developer Experience Report 2024 surveyed 2,100+ developers and found that 97% are losing significant time to inefficiencies, 69% lose 8+ hours weekly to process friction, and 63% consider developer experience essential when deciding whether to stay at their job. For a framework, the CLI is the first touchpoint -- the "handshake" that sets expectations. N3TX currently requires ~8-10 minutes to go from zero to working app, vs. ~2-3 minutes for Django, Rails, and Laravel. That gap is not about capability. It is about ceremony.

**Force 2: The schema-driven CLI opportunity.** Prisma proved that a CLI can be a product differentiator by generating a type-safe client from a single schema file. But Prisma's schema carries only data structure and database relationships. N3TX's JSON Schema carries structure *plus behavior*: validation constraints in `properties`, UI rendering hints in `ui.widget`/`ui.groups`/`ui.field_order`, authorization rules in `access`, and callable method signatures in `methods`. If Prisma's limited schema powers a CLI with 5.49M weekly downloads, what can a richer schema power?

**Force 3: The TUI renaissance.** Charm raised $6M to commercialize terminal interfaces. Bloomberg built Memray with Textual. GitHub, AWS, Nvidia, and Shopify build TUI tools. Textual achieves 120 FPS rendering and supports CSS-like styling. The terminal is no longer a fallback interface -- it is a first-class development environment. For server administration via SSH, container debugging, and CI/CD pipelines, a terminal interface has zero deployment cost compared to a web dashboard.

The question is not whether N3TX should have a CLI. The question is what *kind* of CLI -- and the answer, as we will see, is fundamentally shaped by the framework's schema-driven architecture.

---

## 2. Principles Worth Importing

### 2.1 The Knowledge Encoding Principle

> A CLI command is worth building when it encodes at least three pieces of knowledge a developer would otherwise need to remember or configure manually.

This principle emerges from 18 years of framework CLI evolution. Django's `migrate` encodes schema diffing, SQL generation, dependency ordering, and rollback safety. Rails' `generate model` encodes naming conventions, file locations, boilerplate patterns, and test stubs. Laravel's `tinker` encodes model imports, DB connection, environment config, and helper methods.

The inverse is equally instructive. Create React App encoded *one* thing -- Webpack configuration -- and became obsolete the moment the ecosystem moved past Webpack. Yeoman encoded a *generic scaffolding mechanism* that carried no framework-specific knowledge, and died at 39 weekly downloads.

**Application to N3TX:** `ProtoModel.schema()` at `/workspace/src/n3tx/core/models/proto_model.py` lines 197-316 encodes an extraordinary density of knowledge per model. A `n3tx inspect Product` command that surfaces this knowledge in the terminal encodes at least six pieces: field definitions, validation constraints, access rules, method signatures, auto-generated routes, and UI configuration. That is twice the threshold.

### 2.2 Schema as Universal Contract

> The schema is not a description of the data. It is the specification of how the data behaves, renders, and is controlled. Multiple consumers can independently interpret the same schema.

This principle comes from observing how N3TX's web frontend already works. `N3TX.SCHEMA()` at `/workspace/src/n3tx/static/core/N3TX.js` line 390 receives the schema from the backend and creates DynamicClasses with typed properties, methods, and reactive getters. `form.js` at `/workspace/src/n3tx/static/generators/form.js` line 17 reads the same schema and generates HTML forms. `Permissions.js` reads the `access` section. `ntx-method.js` reads the `methods` section. Each consumer is independent. None knows about the others.

A CLI/TUI layer would be another independent consumer. No adapter pattern needed. No intermediate translation. The schema IS the abstraction layer. This is architecturally superior to RJSF's approach, which requires a separate `uiSchema` alongside the data schema -- N3TX embeds UI hints directly in `json_schema_extra`, so one schema serves all renderers.

### 2.3 Progressive Disclosure of Complexity

> Zero-config defaults for the common case. Flags and options for the advanced case. Full manual control for the expert case.

This principle maps directly to N3TX's existing three-level bootstrap:

```
Level 1 (one-liner):    create_app(models=[Product], storage="sqlite:///app.db")
Level 2 (builder):      N3TXApp(storage=...).model(Product).join(Product, Comment).build()
Level 3 (raw):          register_model(Product, storage=storage_backend); register_routes(...)
```

The CLI should mirror this pattern:

```
Level 1 (zero-config):  n3tx run              # finds main.py, starts server
Level 2 (flags):        n3tx run --port 8080 --host 0.0.0.0 --workers 4
Level 3 (explicit):     n3tx run --app myproject.main:app --storage sqlite:///custom.db
```

Every successful CLI follows this pattern. `rails server` works with zero flags. `django-admin runserver 0.0.0.0:8080` adds specificity. Flask's `--app` flag enables explicit module targeting. The research documents that adoption drops when configuration is required before first use.

### 2.4 The Maintenance Commitment is Forever

> Annual CLI maintenance runs 15-20% of initial development cost. Each command is a permanent contract.

This is the principle most teams ignore. A CLI with 15 commands costs approximately 60 hours/year in testing per release, plus 35 hours in base maintenance, plus incident response for breaking changes. Create React App's failure was not technical -- it was organizational. Nobody was committed to maintaining it.

**Application to N3TX:** Keep the command count low. The research recommends 7 core commands for a framework at N3TX's maturity. Each command must encode enough framework knowledge to justify its maintenance cost. Commands that merely wrap shell operations (`n3tx test` wrapping `pytest`) belong in a Makefile, not the CLI.

### 2.5 Operations Over Scaffolding

> The highest-ROI CLI commands are the ones used daily, not the flashy ones used once.

.NET SDK telemetry from 92 million users reveals the actual usage hierarchy: `build`, `run`, and `restore` dominate across all platforms. The top 5 most-used commands across Django, Rails, Laravel, and .NET are: dev server, migrations, code generation, REPL, and tests. These 5 capabilities account for ~80% of all CLI usage.

Scaffolding commands (`rails new`, `django-admin startproject`) are used once per project. Operational commands (`rails server`, `django migrate`, `artisan tinker`) are used dozens of times per day. Yet most framework CLIs invest 80% of effort in scaffolding and 20% in operations.

**Application to N3TX:** `n3tx run` and `n3tx inspect` will be used far more often than `n3tx new`. Invest accordingly.

---

## 3. Our Architecture Through This Lens

### 3.1 The Model Registry as CLI Menu

In Django, the list of available management commands is discovered by scanning `INSTALLED_APPS` for `management/commands/` directories. In Rails, commands are registered through Thor tasks. In Laravel, commands are PHP classes in `app/Console/Commands/`.

N3TX has something none of them do: `registered_models` at `/workspace/src/n3tx/core/utils/registrar.py` line 9 is a live dictionary of every entity in the application. Combined with `ProtoModel.schema()`, it provides a machine-readable manifest of every model's structure, behavior, and relationships. This is not a list of commands -- it is a **self-describing application**.

```
registered_models
  │
  ├── "products" -> Product class
  │     .schema()  -> JSON Schema (fields, types, validation, UI, access, methods)
  │     .list()    -> query all records
  │     .get(id)   -> fetch one record
  │     .create()  -> insert a record
  │     .update()  -> modify a record
  │     .delete()  -> remove a record
  │
  ├── "users" -> User class
  │     .schema()  -> JSON Schema (includes login/register methods)
  │     ...
  │
  └── "comments" -> Comment class
        .schema()  -> JSON Schema (includes parent_id selfref)
        ...
```

A CLI that reads this registry does not need per-model command classes. A single `n3tx list <table>` command works for any registered model. A single `n3tx inspect <Model>` command works for any model. The registry IS the command namespace.

### 3.2 `form.js` as the TUI Blueprint

The `Formidable` module at `/workspace/src/n3tx/static/generators/form.js` is the most direct analog to a TUI form renderer. Its `getForm()` function (line 17) performs a sequence of operations that any form renderer must perform:

1. **Read field order:** `ui.field_order` or `Object.keys(fields)` (line 24)
2. **Filter renderable fields:** exclude hidden, protected, access-denied (line 35)
3. **Select widget per field:** switch on `type` and `ui.widget` (line 173)
4. **Apply validation:** map constraints to attributes (line 159)
5. **Group fields:** render into `<fieldset>` groups (line 87)

A Python `tui_form.py` would follow the exact same 5-step sequence. Step 3 would map to Textual widgets instead of HTML elements: `string` -> `Input()`, `number` -> `Input(type="number")`, `boolean` -> `Checkbox()`, `textarea` -> `TextArea()`, `currency` -> `Horizontal(Label("$"), Input())`, `enum` -> `Select()`. Steps 1, 2, 4, and 5 would be identical logic in a different language.

This is not an accident. It is the architectural payoff of schema-driven design: the rendering logic is trivially portable because it does not depend on the renderer -- it depends on the schema.

### 3.3 The Actor Model and Message Passing

N3TX's frontend uses an Actor model (Matrix -> Actor -> N3TX -> DynamicClass) where entities communicate via TX messages. The `Matrix` at `/workspace/src/n3tx/static/core/Matrix.js` dispatches messages to local actors or remote endpoints. `N3TX.ATTACH` (line 357) handles entity bootstrapping -- a component sends ATTACH, receives schema, creates DynamicClass, triggers READ.

This architecture is relevant for the TUI because Textual's own architecture mirrors it. Textual uses a message-based event system where widgets communicate via messages (`on_*` handlers). A Textual app's `compose()` yields child widgets (like Actor.spawn). Widget state changes propagate via `reactive()` attributes (like N3TX's value setter triggering `signal()`). The mapping:

| N3TX Web | Textual TUI |
|-----------|-------------|
| `Matrix.dispatch(TX)` | `App.post_message(Message)` |
| `Actor.inbox(event)` | `Widget.on_event(event)` |
| `N3TX.signal(callback)` | `reactive()` + `watch_*()` |
| `DynamicClass.instances` | Widget query: `self.query(EntityRow)` |
| `form.js.getForm(schema)` | `tui_form.build_form(schema)` |

This architectural resonance means a TUI admin would not fight N3TX's patterns -- it would extend them into a different rendering target.

### 3.4 The `N3TXApp.build()` Bottleneck

The single biggest architectural obstacle is that model registration is coupled to HTTP server creation. `N3TXApp.build()` at `/workspace/src/n3tx/core/app.py` line 128 performs six steps in sequence:

```
1. authorize.configure(...)           -- auth setup
2. for model in models: register_model(...)  -- model registration
3. for parent, child: generate_join_model(...)  -- join model generation
4. backend = FastAPIBackend(...)      -- HTTP framework creation
5. backend.register_routes(...)       -- route generation
6. return backend.get_app(...)        -- ASGI app return
```

Steps 1-3 are **domain logic** that any consumer needs. Steps 4-6 are **HTTP plumbing** that only a web server needs. A CLI needs steps 1-3 but not 4-6. Today, there is no way to execute them independently.

The fix is surgical: extract steps 1-3 into a `setup()` method. `build()` calls `setup()` then proceeds to steps 4-6. CLI commands call `setup()` directly. This is approximately 15 lines of code moved from one method to another. It is the keystone change that makes everything else possible.

---

## 4. The Synthesis: Where Two Worlds Meet

### 4.1 Integration Point: Schema-Driven Inspection

**Before:**

```
Developer wants to know Product's access rules.

Option A: Start server. Open browser. Navigate to /Product. Read JSON.
          Time: 30-60 seconds. Requires running server.

Option B: Write Python script:
          from myapp.models import Product
          import json
          print(json.dumps(Product.schema(), indent=2))
          Time: 60-120 seconds. Requires file creation.

Option C: Read source code in proto_model.py and the model file.
          Time: 2-5 minutes. Requires architectural knowledge.
```

**After:**

```
$ n3tx inspect Product --section access

  Access Rules for Product
  ========================

  read:   ANYONE
  create: AUTHENTICATED
  update: OWNER | ROLE('admin')
  delete: ROLE('admin')

  Method Access:
    comment:  AUTHENTICATED
    favorite: AUTHENTICATED

  Owner Field: user_owner
```

Time: 2 seconds. No server required. No file creation. The schema carries the answer.

### 4.2 Integration Point: Terminal CRUD from Schema

**Before:**

```
Developer wants to create a test Product record.

Option A: Start server. Use curl:
          TOKEN=$(curl -s -X POST http://localhost:5000/users/login ...)
          curl -X POST http://localhost:5000/products \
            -H "x-access-token: $TOKEN" \
            -H "Content-Type: application/json" \
            -d '{"name":"Test","price":9.99,"description":"Test product"}'
          Time: 60-90 seconds. Error-prone JSON. Requires auth token.

Option B: Write seed script. Import model. Call StorableMixin.create().
          Time: 2-5 minutes.
```

**After:**

```
$ n3tx create Product

  Name:        [Test Widget          ]  (required, 1-200 chars)
  Price ($):   [9.99                 ]  (required, > 0)
  Description: [A test product       ]  (optional)

  Created Product #42: Test Widget ($9.99)
```

The form knows `name` is required (from `minLength=1`), `price` must be > 0 (from `exclusiveMinimum`), `description` is optional (has `default=''`), and `image`/`id`/`created_at` are hidden (from `_AUTO_HIDE_FIELDS` in `proto_model.py` line 23). The same validation logic that `form.js` enforces in the browser now runs in the terminal. The schema is the single source of truth for both.

### 4.3 Integration Point: The REPL as Schema Explorer

**Before:**

```
Developer wants to test a custom method (e.g., Product.comment()).

1. Start server
2. Seed database
3. Get auth token
4. POST /products/1/comment with JSON body
5. Parse response
6. Check database
Time: 3-5 minutes per iteration
```

**After:**

```
$ n3tx shell

>>> p = Product.get(1)
>>> p.name
'Wireless Headphones'
>>> p.schema()['methods']['comment']
{'route': '/comment', 'methods': ['POST'], 'parameters': {'comment': {...}}}
>>> from myapp.models import Comment
>>> c = Comment(body="Great product!", user_owner=1)
>>> p.comment(comment=c, user=User.get(1))
'Comment created'
>>> Product.get(1).comments
[3, 7, 12]  # ListRef IDs
```

Time: 30 seconds per iteration. No server. No HTTP. No token management. The REPL talks directly to `StorableMixin`, which talks to the storage backend. This is how `rails console` and `laravel tinker` work -- and 80% of Rails developers use it daily.

---

## 5. Boundaries: Where This Does Not Apply

### 5.1 A TUI Is Not a Web Replacement

The terminal cannot render images, video, rich text, color pickers, drag-and-drop, or complex CSS animations. N3TX's web frontend at `matrix.html` handles all of these. A TUI admin is a **complement** for power users, not a replacement for the web interface. The research estimates 85-90% of CRUD admin functionality maps cleanly to terminal widgets. The remaining 10-15% (media fields, rich interactions) degrades gracefully to text placeholders: `[Image: product_photo.jpg]`, `[Video: demo.mp4]`.

The TUI is valuable in specific contexts: SSH sessions on production servers, Docker container debugging, CI/CD pipelines, air-gapped environments, and developer workflows where context-switching to a browser costs 23 minutes of refocus time. It is not valuable as a general-purpose frontend.

### 5.2 Do Not Generate Application Code

The research is unambiguous on this point: scaffolding tools that generate application code create technical debt at scale. Create React App, Yeoman, and Rails' scaffold critics all point to the same failure mode -- generated code that diverges from best practices and teaches developers the wrong patterns.

N3TX's `scaffold.py` is schema-driven (reading from `ProtoModel.schema()`), not template-driven. This is architecturally sound. But a `n3tx generate model` command that writes Python model files from templates would be template-driven and subject to drift. The correct approach for model creation is either (a) interactive prompts that output a minimal model file, or (b) no generation at all -- let developers write models by hand, using the example app and `n3tx inspect` as references.

The exception is `n3tx new <project>`, which generates an initial project skeleton. This is acceptable because it is used once, the templates are maintained as part of the framework, and the generated code uses `create_app()` which is the framework's own API.

### 5.3 Do Not Build a Plugin System Prematurely

The research recommends against building a plugin system until at least 3 external teams request one. For a pre-1.0 framework with a small user base, a monolithic CLI with clear module boundaries is the correct architecture. Python's `entry_points` mechanism (via Click/Typer) provides a natural extensibility point when demand materializes. Building plugin infrastructure before there are plugins is wasted effort.

### 5.4 The Makefile Is Enough for Non-Schema Commands

Not every developer workflow needs a CLI command. `n3tx test` would be a thin wrapper around `pytest`. `n3tx deploy` would be a thin wrapper around deployment scripts. These commands carry no framework knowledge -- they are shell command wrappers. A Makefile or Justfile handles them with zero maintenance cost:

```makefile
test:
    cd src/n3tx/core && pytest tests/unit/

lint:
    ruff check src/

deploy:
    docker build -t myapp . && docker push myapp
```

The CLI should contain only commands that **require schema awareness or framework internals**. Everything else belongs in a task runner.

---

## 6. A Path Forward

### Phase 1: Foundation (Week 1, ~24 hours)

**Goal:** A working `n3tx` CLI with 4 schema-aware commands.

**Decision gate:** Can a developer go from `pip install n3tx` to inspecting a model schema in under 2 minutes?

| Deliverable | Effort | Depends On |
|-------------|--------|------------|
| `N3TXApp.setup()` extraction | 2-4 hrs | Nothing |
| `n3tx` entry point + Typer app | 4-6 hrs | setup() |
| `n3tx run` (uvicorn wrapper) | 2-3 hrs | Entry point |
| `n3tx models` (list registered models) | 2-3 hrs | Entry point + setup() |
| `n3tx inspect <Model>` (schema visualization) | 8-12 hrs | Entry point + setup() |
| CliRunner tests for all 4 commands | 4-6 hrs | Commands |

**Architectural decisions locked in Phase 1:**
- Typer as CLI framework (Click underneath, Rich for output)
- Lazy loading for <100ms `--help` startup
- `--app` flag for user project discovery
- Optional dependency: `pip install n3tx[cli]`

### Phase 2: Operations (Week 2-3, ~30 hours)

**Goal:** Daily-use operational commands that keep developers in the terminal.

**Decision gate:** Does the team use the CLI instead of curl/scripts for their daily workflow?

| Deliverable | Effort | Depends On |
|-------------|--------|------------|
| `n3tx shell` (REPL with models) | 4-8 hrs | Phase 1 |
| `n3tx doctor` (diagnostics) | 4-6 hrs | Phase 1 |
| `n3tx migrate:status` | 4-6 hrs | Phase 1 |
| `n3tx seed` (wraps seed.py) | 2-4 hrs | Phase 1 |
| `n3tx new <project>` (project scaffold) | 16-24 hrs | Phase 1 |

**Architectural decisions locked in Phase 2:**
- ptpython as optional REPL backend (fallback to IPython, then plain Python)
- Jinja2 templates for project scaffolding (maintained in framework repo)
- Seed command discovers `seed.py` by convention

### Phase 3: Schema-Driven Terminal Forms (Month 2, ~40 hours)

**Goal:** Interactive CRUD in the terminal, driven by the same schema as the web frontend.

**Decision gate:** Can a developer create a fully validated entity via terminal form without writing JSON?

| Deliverable | Effort | Depends On |
|-------------|--------|------------|
| `schema_reader.py` (shared field logic) | 8-12 hrs | Phase 1 |
| `tui_form.py` (schema-to-Textual widget mapping) | 20-30 hrs | schema_reader |
| `n3tx create <Model>` (interactive form) | 4-6 hrs | tui_form |
| `n3tx list <table>` (Rich table output) | 4-6 hrs | Phase 1 |

**Architectural decisions locked in Phase 3:**
- Textual as optional TUI dependency: `pip install n3tx[tui]`
- `schema_reader.py` as shared logic between CLI and TUI
- Graceful degradation: media fields -> text placeholders

### Phase 4: TUI Admin Dashboard (Month 3+, ~80 hours)

**Goal:** A full terminal admin interface accessible via SSH, comparable to Django Admin in functionality.

**Decision gate:** Is SSH-based administration a real use case for the user base?

This phase is contingent on Phase 3 success and demonstrated demand. It builds on `tui_form.py` to create `EntityListScreen`, `EntityFormScreen`, and `EntityDetailScreen` within a Textual app. The sidebar reads from `registered_models`. The main panel uses `StorableMixin.list()` with pagination. Method buttons come from `schema.methods`. The design mirrors the web frontend's architecture: schema consumed at runtime, rendering derived from metadata.

**Do not start Phase 4 until Phases 1-3 are stable and in use.** The TUI dashboard is a differentiator, not a necessity. Its value depends on N3TX's user base and their deployment patterns.

---

## 7. Conclusion

The CLI/TUI domain and N3TX's schema-driven architecture are not just compatible -- they are **mutually reinforcing**. The CLI world has spent 18 years converging on the insight that framework CLIs must encode domain knowledge, not just wrap shell commands. N3TX has spent its entire existence building a schema that encodes domain knowledge more richly than any comparable framework.

The schema carries field types, validation constraints, UI widget hints, field ordering, field grouping, ABAC access rules, custom method signatures, protected field markers, and relationship metadata. The web frontend already consumes this schema to generate forms, enforce permissions, render method buttons, and navigate entity hierarchies. Adding a terminal consumer requires no new abstraction layer -- the JSON Schema IS the abstraction.

The path is clear: extract `setup()` to decouple model registration from HTTP, add a Typer-based CLI entry point, build the `inspect` command as the signature schema-aware feature, then progressively add operations (shell, doctor, migrate), interactive forms (schema-to-widget mapping), and finally the TUI dashboard. Each phase delivers standalone value. Each phase builds on the one before. No phase requires burning the existing architecture.

The end state is a framework where `n3tx inspect Product` shows you the model's complete behavioral specification, `n3tx create Product` launches a validated terminal form, `n3tx shell` gives you a REPL with every model pre-loaded, and `n3tx admin` gives you a full admin interface over SSH -- all derived from the same Python class definition that drives the web UI. This is not incremental improvement. This is what "the model is the app" means when taken to its logical conclusion.

---

## References

### Industry Data
1. Atlassian State of Developer Experience Report 2024 -- 2,100+ developers surveyed; 97% report inefficiencies; 63% consider DX for retention
2. UC Irvine Context Switching Study -- 23 minutes 15 seconds to refocus after interruption
3. .NET SDK Telemetry -- 92M unique users; `build`, `run`, `restore` as top commands
4. Platform Engineering ROI Study -- 25-developer startup; onboarding reduced from 2 weeks to 2 hours; 185% ROI
5. Gartner TUI Adoption Report (2024) -- 65% surge in cloud-native TUI adoption

### Framework CLIs
6. Django Management Commands -- 50+ built-in commands; 32.9% web framework market share; 42,880+ companies
7. Rails CLI Scaffolding -- 40% productivity increase; 80% console usage; 65% team generator adoption
8. Laravel Artisan -- 743,470 active websites; 35.87% PHP framework market share; Tinker REPL
9. Prisma CLI -- $56.5M raised; 5.49M weekly npm downloads; schema-first generation
10. Create React App Deprecation (Feb 2025) -- Cautionary tale of unmaintained scaffolding

### Python Ecosystem
11. Typer -- 19K GitHub stars; 66M monthly PyPI downloads; type-hint-driven
12. Rich -- 55.6K GitHub stars; Console Protocol for custom renderables
13. Textual -- 34.5K GitHub stars; 120 FPS; CSS-like styling; web deployment via `textual serve`
14. Click -- 17K GitHub stars; 533M monthly PyPI downloads; LazyGroup, entry_points
15. ptpython -- Enhanced REPL; ~200ms startup; ~20MB memory

### Schema-Driven Architecture
16. react-jsonschema-form (RJSF) -- 14K+ stars; canonical web schema-to-form mapping; `uiSchema` separation
17. SchemaUI (Rust) -- 37 stars; JSON Schema to TUI forms; only terminal prior art
18. django-admin-tui -- 55 stars; v0.0.1; validates demand for model-driven TUI admin
19. Form.io -- JSON defines form + API in one spec; schema-driven dynamic forms

### Design Principles
20. clig.dev -- Command Line Interface Guidelines; flags over args; human-readable errors
21. Atlassian Forge CLI Principles -- 10 design principles; "create a reaction for every action"
22. Symfony Backward Compatibility Promise -- Deprecation windows; gold standard for CLI versioning
23. ScienceSoft Maintenance Analysis -- Annual maintenance: 15-20% of initial development cost

### N3TX Codebase (Referenced Files)
24. `/workspace/src/n3tx/core/models/proto_model.py` -- ProtoModel.schema(), _AUTO_HIDE_FIELDS, generate_join_model()
25. `/workspace/src/n3tx/core/app.py` -- N3TXApp.build(), create_app(), _resolve_storage()
26. `/workspace/src/n3tx/core/utils/registrar.py` -- registered_models, register_model()
27. `/workspace/src/n3tx/core/api/routes_fastapi.py` -- register_routes(), route factories
28. `/workspace/src/n3tx/static/generators/form.js` -- Formidable.getForm(), getInput(), validationAttrs()
29. `/workspace/src/n3tx/static/core/N3TX.js` -- N3TX.SCHEMA(), prototype(), DynamicClass creation
30. `/workspace/src/n3tx/static/core/Matrix.js` -- Message dispatch, NetworkAdapter bridge
31. `/workspace/src/n3tx/static/core/Actor.js` -- Actor model, subclass(), register()
32. `/workspace/src/n3tx/core/utils/decorators.py` -- @expose_route()
33. `/workspace/src/n3tx/__init__.py` -- Public API, __version__
