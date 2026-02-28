# CLI & TUI x PyBend: Technical Propositions

> *How CLI/TUI principles can improve our architecture.*
> *Based on research in .traces/research/cli-tui/ and codebase analysis.*
> *Companion to the [whitepaper](12-02-cli-tui-whitepaper.md).*

---

## The Bridge

PyBend's central thesis is that **the model is the app**. A Python class definition is the single source of truth for the entire stack: data structure, validation, API endpoints, JSON Schema, access control, UI rendering. The frontend already proves this -- `form.js` reads `schema.properties` and produces the correct HTML input for each field type, with validation constraints, widget hints, and access-controlled visibility. The CLI/TUI domain arrives at the exact same conclusion from a different direction: the best framework CLIs are the ones that **derive their commands from the schema**, not from hand-coded templates.

This is not a coincidence. Django's `manage.py` succeeded because it was extensible by design. Rails' generators succeeded because the generated code followed the same conventions the framework enforces at runtime. Prisma's CLI succeeded because it generates a type-safe client from a single schema file. But none of these frameworks carry the *full behavioral specification* in their schema the way PyBend does. PyBend's JSON Schema includes validation constraints (`minLength`, `gt`, `pattern`), UI widget hints (`ui.widget: "currency"`), field grouping and ordering (`ui.groups`, `ui.field_order`), ABAC access rules (`access.update: OWNER | ROLE('admin')`), custom method signatures (`methods.comment.parameters`), and protected field markers. No other framework's schema is this rich.

The creative friction point is this: the web frontend consumes the schema at runtime through the browser's DOM. A CLI consumes it through the terminal's character grid. The schema itself does not care. It is a universal contract. The propositions below explore how to add a second consumer -- the terminal -- without duplicating the contract, without breaking the existing consumer, and without adding complexity that contradicts PyBend's "transparent, not magical" principle.

---

## Propositions

### Proposition 1: Extract `PyBendApp.setup()` to decouple model registration from HTTP

> **Proposition:** Split `PyBendApp.build()` into `setup()` (model registration, storage, auth) and `build()` (FastAPI app creation) so CLI commands can access registered models without starting an HTTP server.

**From the research:** Every successful framework CLI -- Django's `manage.py`, Rails' `console`, Laravel's `tinker` -- can bootstrap the framework without running a web server. The research (02, Section 8.2) identifies "model discovery without HTTP" as the single biggest technical gap blocking a PyBend CLI. Django solves this by separating `django.setup()` (which loads settings, apps, and models) from `runserver` (which starts the HTTP layer). Laravel's `tinker` bootstraps the full service container without starting Artisan's HTTP kernel.

**In our system:** `PyBendApp.build()` at `/workspace/src/pybend/core/app.py` line 128 does everything in sequence: configure auth (line 142), register models with storage (line 148), generate join models (line 157), create `FastAPIBackend` (line 162), register routes (line 170), and return the ASGI app (line 177). Steps 1-3 are the **setup** that any consumer needs. Steps 4-6 are HTTP-specific. Today, there is no way to execute steps 1-3 alone.

**The idea:** Extract lines 141-159 of `build()` into a new `setup()` method:

```
Before:
  PyBendApp.build()  ──>  auth + models + joins + FastAPI + routes + app
  (CLI has no entry point to models without HTTP)

After:
  PyBendApp.setup()  ──>  auth + models + joins
  PyBendApp.build()  ──>  setup() + FastAPI + routes + app
  (CLI calls setup(), gets registered_models, never touches HTTP)
```

The `registered_models` dict at `/workspace/src/pybend/core/utils/registrar.py` line 9 becomes populated after `setup()`. Any CLI command can then call `Product.list()`, `Product.schema()`, or `Product.create(data)` directly through `StorableMixin`. The web layer calls `build()` as before -- `build()` simply calls `setup()` first, then proceeds with FastAPI wiring. Zero breaking changes.

This is the **keystone** proposition. Every other proposition depends on it.

| Dimension | Assessment |
|-----------|------------|
| **Effort** | 2-4 hours (extract existing code, add one method) |
| **Impact** | Critical -- unblocks all CLI/TUI work |
| **Risk** | Very low -- `build()` still works identically |
| **Timeline** | Day 1 |

---

### Proposition 2: Add a `pybend` CLI entry point with Typer

> **Proposition:** Create a `pybend` console script backed by Typer that serves as the framework's developer-facing command interface, starting with `run`, `models`, `describe`, and `migrate:status`.

**From the research:** Typer has 19K GitHub stars and 66M monthly PyPI downloads (02, Section 2.1). It is built on Click (533M monthly downloads), uses Python type hints for CLI argument declaration (matching PyBend's Pydantic philosophy), includes built-in Rich integration for beautiful output, and is created by Sebastien Ramirez -- the same author as FastAPI, which PyBend already depends on. The research (03, Section 11.5) estimates a 7-command MVP CLI at ~104 hours and a Phase 1 foundation at 8 hours.

**In our system:** PyBend currently exposes `create_app()` and `PyBendApp` as Python APIs (`/workspace/src/pybend/__init__.py` line 16-17). There is no console script. Starting the example app requires `cd src/pybend/example && python3 main.py`. Running scaffolding requires `python -m utils.scaffold Product`. Running seed requires `python seed.py`. Each is a separate incantation that a developer must memorize.

**The idea:** Add a `pybend` entry point to `pyproject.toml`:

```
pybend/
  cli/
    __init__.py        # Typer app with lazy-loaded command groups
    commands/
      run.py           # pybend run (wraps uvicorn)
      models.py        # pybend models (list), pybend describe Product (schema)
      migrate.py       # pybend migrate:status
```

The CLI discovers the user's app via convention or `--app` flag (like Flask/FastAPI CLI patterns), calls `PyBendApp.setup()` from Proposition 1, and then has full access to `registered_models`. Phase 1 commands:

```
$ pybend models

  Registered Models
  +----------+----------+---------+---------+
  | Name     | Table    | Fields  | Methods |
  +----------+----------+---------+---------+
  | Product  | products | 6       | 2       |
  | User     | users    | 6       | 2       |
  | Comment  | comments | 5       | 2       |
  | Like     | likes    | 2       | 0       |
  +----------+----------+---------+---------+
  4 models, 2 join models

$ pybend describe Product
  [Rich tree: properties, methods, access rules, UI config]

$ pybend run
  INFO     Started server at http://0.0.0.0:5000
```

Lazy loading (Click's `LazyGroup` pattern, 02 Section 6.2) ensures `pybend --help` starts in <100ms even with many commands. Rich is a transitive dependency of Typer, so table rendering costs zero additional installation.

| Dimension | Assessment |
|-----------|------------|
| **Effort** | 8-16 hours (entry point, 4 commands, tests) |
| **Impact** | High -- first-contact developer experience |
| **Risk** | Low -- additive, optional dependency |
| **Timeline** | Week 1 |

---

### Proposition 3: Schema-driven `inspect` command -- the CLI's killer feature

> **Proposition:** Build a `pybend inspect <Model>` command that renders a complete, navigable view of a model's schema, routes, access rules, field validations, UI hints, and method signatures -- all derived from `ProtoModel.schema()`.

**From the research:** Prisma proved that a CLI can be a **product differentiator** (01, Section 1.4). The research (04, Section "The Schema-Driven Advantage") argues that PyBend's schema carries information no other framework's CLI can access: validation constraints, UI widget hints, field grouping, access control rules, and custom method signatures. The research (03, Section 2.3) identifies "the knowledge encoding principle" -- a CLI command is worth building when it encodes at least 3 pieces of knowledge a developer would otherwise need to remember.

**In our system:** `ProtoModel.schema()` at `/workspace/src/pybend/core/models/proto_model.py` lines 197-316 produces a JSON Schema document so rich that the entire web frontend derives from it. Currently, inspecting this schema requires either (a) starting the server and hitting `GET /Product`, or (b) writing a Python script that imports the model and calls `.schema()`. Neither is fast. Neither is formatted for human reading.

**The idea:** The `inspect` command renders the schema as a Rich tree with expandable sections:

```
$ pybend inspect Product

  Product (products)
  ==================

  Fields (6):
  +-------------+---------+----------+----------------------------+
  | Field       | Type    | Required | Constraints                |
  +-------------+---------+----------+----------------------------+
  | id          | integer | No       | (auto, hidden)             |
  | name        | string  | Yes      | min=1, max=200             |
  | price       | float   | Yes      | gt=0, widget=currency      |
  | description | string  | No       | default='', widget=textarea|
  | image       | string  | No       | (hidden)                   |
  | comments    | array   | No       | ListRef[Comment]           |
  +-------------+---------+----------+----------------------------+

  Access Rules:
    read:   ANYONE
    create: AUTHENTICATED
    update: OWNER | ROLE('admin')
    delete: ROLE('admin')

  Methods:
    POST /products/{id}/comment  (access: AUTHENTICATED)
      Parameters: comment: Comment, user: User
      Returns: str

  Routes (auto-generated):
    GET    /Product           (schema)
    POST   /products          (create)
    GET    /products          (list, paginated)
    GET    /products/{id}     (read)
    PUT    /products/{id}     (update)
    DELETE /products/{id}     (delete)

  UI Configuration:
    field_order: [name, price, description, comments]
    groups: {main: [name, description, price], Social: [comments]}
    renderer: {item: ntt-item, list: ntt-list}
```

This command encodes **6 pieces of knowledge**: field definitions, validation constraints, access rules, method signatures, auto-generated routes, and UI configuration. No `curl`. No server running. No documentation to read. One command surfaces the entire behavioral specification of a model.

The implementation reads from `ProtoModel.schema()` and `registered_models` (already populated by Proposition 1's `setup()`). The route information comes from walking `registered_models` and applying the same logic as `register_routes()` in `/workspace/src/pybend/core/api/routes_fastapi.py` line 387. This is roughly 80 lines of Rich rendering code.

| Dimension | Assessment |
|-----------|------------|
| **Effort** | 8-12 hours |
| **Impact** | Very high -- unique capability, no other framework has this |
| **Risk** | Low -- read-only, no side effects |
| **Timeline** | Week 1-2 |

---

### Proposition 4: Interactive REPL with pre-loaded models (`pybend shell`)

> **Proposition:** Build a `pybend shell` command that launches an enhanced Python REPL with all registered models, their schemas, and CRUD operations pre-imported and ready to use.

**From the research:** 80% of Rails developers use `rails console` for debugging and testing (01, Section 1.2). Laravel's `tinker` gives developers a fully loaded Laravel environment in the terminal -- you can dispatch jobs, fire events, and manipulate Eloquent models. The research (02, Section 8) compares IPython (~500ms startup, ~40MB) vs. ptpython (~200ms startup, ~20MB) and recommends ptpython for minimal footprint.

**In our system:** PyBend has no REPL. Debugging requires starting the server, crafting `curl` commands with JWT tokens, and parsing JSON responses. The `registered_models` dict, `StorableMixin` methods, and `ProtoModel.schema()` are all available as Python APIs -- they just have no interactive entry point.

**The idea:** After `setup()`, inject the following into the REPL namespace:

```python
# What pybend shell provides:
Product   = registered_models['products']  # The model class
User      = registered_models['users']
Comment   = registered_models['comments']

# CRUD operations work immediately:
>>> Product.list(limit=5)
[<Product id=1 name="Widget">, <Product id=2 name="Gadget">, ...]

>>> p = Product.get(1)
>>> p.name
'Widget'
>>> p.price = 29.99
>>> p.save()

>>> Product.schema()
{'$schema': '...', 'properties': {...}, 'methods': {...}, ...}
```

This is 15-20 lines of glue code that calls `setup()`, builds a namespace dict from `registered_models`, and launches ptpython (or IPython, or plain Python as fallback). The REPL inherits all `StorableMixin` methods: `create()`, `get()`, `list()`, `update()`, `delete()`, `save()` -- all working against the actual database, no HTTP server required.

| Dimension | Assessment |
|-----------|------------|
| **Effort** | 4-8 hours |
| **Impact** | High -- massive debugging productivity gain |
| **Risk** | Low -- ptpython is an optional dependency |
| **Timeline** | Week 2 |

---

### Proposition 5: Schema-driven terminal forms via Rich/Textual

> **Proposition:** Build a `tui_form.py` module that maps JSON Schema properties to terminal widgets, mirroring `form.js`'s logic, so that `pybend create Product` launches an interactive schema-driven form in the terminal.

**From the research:** Nobody has built a Python library that takes JSON Schema and generates Textual TUI forms (05, Section 2). The closest prior art is SchemaUI (Rust, 37 stars) and django-admin-tui (55 stars, v0.0.1). The research (05, Section 5) provides a side-by-side comparison of `form.js`'s `getInput()` (lines 173-236) and its theoretical Textual equivalent, showing the logic ports nearly 1:1. The mapping: `string` -> `Input(type="text")`, `number` -> `Input(type="number")`, `boolean` -> `Checkbox`, `ui.widget: "textarea"` -> `TextArea()`, `ui.widget: "currency"` -> `Horizontal(Label("$"), Input())`, `enum` -> `Select()`.

**In our system:** `form.js` at `/workspace/src/pybend/static/generators/form.js` is ~370 lines that convert schema properties to HTML. The `getInput()` function (line 173) switches on `type` and `ui.widget` to produce the right HTML element. `validationAttrs()` (line 159) maps `minLength`, `maximum`, `pattern` to HTML5 attributes. `renderGroupedFields()` (line 87) wraps fields in `<fieldset>` based on `ui.groups`. This is the exact logic that would drive a terminal form -- the only difference is the output target.

**The idea:** Create `pybend/cli/tui_form.py` (~400 lines) that:

1. Reads `schema.properties` and `schema.ui.field_order` -- same as `form.js` line 24
2. Filters by `ui.display`, `ui.protected`, permissions -- same as `form.js` line 35
3. Maps each field to a Textual widget via `get_widget()` -- analogous to `getInput()`
4. Builds validation from `minLength`, `minimum`, `pattern` -- analogous to `validationAttrs()`
5. Groups fields into `TabbedContent` / `TabPane` -- analogous to `renderGroupedFields()`

The `pybend create Product` command would launch:

```
  Create Product
  ==============

  Name:        [                    ]  (required, 1-200 chars)
  Price ($):   [        ]              (required, > 0)
  Description: [                    ]  (optional, multiline)
                [                    ]

  [Create]  [Cancel]
```

The form enforces the same validation as the web form -- because it reads the same schema. `id`, `image`, `created_at` are hidden (same `_AUTO_HIDE_FIELDS` logic from `proto_model.py` line 23). Comments (ListRef) are skipped in creation forms (same logic as `form.js`). This would make PyBend the **first framework where `pybend create Product` and `<ntt-list model="Product">` both derive from the same source of truth**.

| Dimension | Assessment |
|-----------|------------|
| **Effort** | 20-30 hours |
| **Impact** | Very high -- category-defining capability |
| **Risk** | Medium -- Textual is a non-trivial dependency |
| **Timeline** | Month 1-2 |

---

### Proposition 6: `pybend doctor` -- diagnostic command for environment health

> **Proposition:** Build a diagnostic command that verifies Python version, package versions, database connectivity, model registration, route generation, and auth configuration -- surfacing issues before they become runtime errors.

**From the research:** The research (02, Section 11.3) outlines a `pybend doctor` command that checks Python version, PyBend version, dependencies, database existence, tables, models, routes, auth, and static files. The Atlassian DX Report 2024 found that 69% of developers lose 8+ hours weekly to tooling friction (01, Section 5.3). A diagnostic command eliminates an entire category of "it doesn't work and I don't know why" moments.

**In our system:** Configuration lives in `/workspace/src/pybend/core/config.py`. Storage is set via `_resolve_storage()` in `app.py` line 32. Auth is configured via `authorize.configure()`. Models are tracked in `registered_models`. None of this is inspectable from the command line today.

**The idea:** `pybend doctor` runs after `setup()` and outputs:

```
$ pybend doctor

  PyBend v0.7.0 Diagnostics
  ==========================

  Python:    3.12.1          OK
  FastAPI:   0.115.4         OK
  Pydantic:  2.7.1           OK
  SQLite:    3.45.0          OK

  Database:  sqlite:///app.db
  - Exists:  Yes             OK
  - Tables:  5               OK

  Models:    4 registered
  - Product  (6 fields, 2 methods)  OK
  - User     (6 fields, 2 methods)  OK
  - Comment  (5 fields, 2 methods)  OK
  - Like     (2 fields, 0 methods)  OK

  Auth:      JWT configured  OK

  All checks passed.
```

This is approximately 60 lines of code that calls `importlib.metadata.version()` for package checks, `os.path.exists()` for the database, iterates `registered_models` for model checks, and verifies auth configuration. Low effort, high signal-to-noise ratio for debugging deployment issues.

| Dimension | Assessment |
|-----------|------------|
| **Effort** | 4-6 hours |
| **Impact** | Medium-high -- eliminates "it doesn't work" debugging |
| **Risk** | Very low |
| **Timeline** | Week 2 |

---

### Proposition 7: `pybend new` -- project scaffolding for zero-to-working in 30 seconds

> **Proposition:** Create a `pybend new myapp` command that generates a working project directory with `main.py`, an example model, seed data, and configuration -- matching the "zero to working, then customize" principle.

**From the research:** The "First 5 Minutes" test (03, Section 9.3) shows PyBend takes ~8-10 minutes to go from zero to running, vs. ~2-3 minutes for Django, Rails, and Laravel. The gap is not capability -- it is ceremony. A `pybend new` command would match the experience of `rails new` or `django-admin startproject`.

**In our system:** `create_app()` at `/workspace/src/pybend/core/app.py` line 180 already handles the full wiring -- but the developer must write the `main.py` file, import models, and call `create_app()` manually. The example app at `/workspace/src/pybend/example/` shows the pattern: `main.py`, `models/`, `seed.py`, `tests/`.

**The idea:**

```
$ pybend new myapp

  Creating project: myapp/
    myapp/
      main.py           # create_app() with example Product model
      models/
        __init__.py
        product.py      # Example model with fields, access rules, UI hints
      seed.py           # Seed data script
      tests/
        __init__.py
        test_product.py # Basic integration test
      pyproject.toml    # Project config with pybend dependency

  Done! Next steps:
    cd myapp
    pybend run
    Open http://localhost:5000/static/matrix.html
```

The generated code uses `create_app()` (not raw primitives) to demonstrate the recommended pattern. The example model includes at least one `ListRef` field, one `@expose_route` method, and `__access__` rules -- teaching the framework's patterns through generated code (the Rails insight from 01, Section 1.2: "generators are a teaching tool").

Templates can use Jinja2 (Cookiecutter pattern, 02 Section 7.2) or simple string formatting. The key constraint: generated code must always reflect the current version's best practices, because it reads from the framework's own template directory rather than static snapshots.

| Dimension | Assessment |
|-----------|------------|
| **Effort** | 16-24 hours |
| **Impact** | High -- first-contact experience defines adoption |
| **Risk** | Medium -- templates must stay in sync with framework |
| **Timeline** | Week 2-3 |

---

### Proposition 8: Isomorphic form architecture -- shared schema, multiple renderers

> **Proposition:** Formalize the pattern where JSON Schema is the abstraction layer between backend and *multiple* frontends, so that web (`form.js`), CLI (Rich tables), and TUI (Textual forms) all consume the same contract without any bridging layer.

**From the research:** The research (05, Section 8) identifies the "isomorphic form architecture" as the strategic endgame: one schema, multiple renderers. RJSF (React JSON Schema Form) solved this for the web with a separate `uiSchema`. PyBend solved it better by embedding UI hints directly in the JSON Schema via `json_schema_extra`. This means a TUI renderer reads the **exact same schema** -- no translation layer, no adapter, no separate configuration.

**In our system:** The schema flow today is:

```
ProtoModel.schema() -> JSON Schema -> form.js -> HTML
```

The proposed flow adds parallel consumers:

```
ProtoModel.schema() -> JSON Schema -> form.js    -> HTML (browser)
                                   -> tui_form.py -> Textual widgets (terminal)
                                   -> cli_render  -> Rich tables (CLI output)
```

**The idea:** This is not a single piece of code -- it is an architectural principle that Propositions 3, 5, and the eventual TUI dashboard all follow. The principle is: **the schema IS the abstraction layer**. No intermediate format. No adapter pattern. Each renderer independently interprets `properties`, `ui.widget`, `ui.field_order`, `ui.groups`, `access`, and `methods`.

The practical implementation is a shared `schema_reader.py` module (~100 lines) that provides:
- `get_renderable_fields(schema, mode)` -- same logic as `form.js` lines 24-42
- `get_field_constraints(definition)` -- extracts `minLength`, `minimum`, `pattern`
- `get_widget_hint(definition)` -- returns `ui.widget` value or infers from type
- `get_groups(schema)` -- returns `ui.groups` dict

This module is imported by both `tui_form.py` (Proposition 5) and CLI rendering commands (Proposition 3). The web frontend continues using `form.js` independently -- JavaScript does not import Python -- but the *logic* is identical, documented, and testable on both sides.

| Dimension | Assessment |
|-----------|------------|
| **Effort** | 8-12 hours (shared module + documentation) |
| **Impact** | High -- architectural foundation for multi-renderer |
| **Risk** | Low -- does not touch existing code |
| **Timeline** | Month 1 (alongside Proposition 5) |

---

### Proposition 9: Textual TUI admin dashboard (moonshot)

> **Proposition:** Build a `pybend admin` command that launches a full Textual-based terminal admin interface -- model browser, entity CRUD, migration status, live logs -- all driven by the schema, accessible via SSH without a browser.

**From the research:** TUI adoption in cloud-native environments has surged 65% (04, Section "TUI Dashboard Opportunity"). Textual achieves 120 FPS terminal rendering (02, Section 3.1). Bloomberg built Memray with Textual. GitHub, Nvidia, AWS, and Shopify build TUI tools with Bubble Tea. The research (05, Section 10) provides a complete CRUD flow architecture with screen definitions. django-admin-tui (55 stars) validates demand but is early-stage. Nobody has built a schema-driven TUI admin in Python.

**In our system:** The web frontend at `matrix.html` already serves as the data exploration layer. But it requires a browser. The TUI would serve the same purpose over SSH -- valuable for production server administration, container debugging, and environments without browser access.

**The idea:**

```
$ pybend admin

  +---------------------------------------------------------------+
  | PyBend Admin                                     localhost:5000 |
  +---------------+-----------------------------------------------+
  |               |                                               |
  | Models        |  Products (23 total)                          |
  |               |                                               |
  | > Product     |  ID | Name                | Price   | Desc    |
  |   User        |  1  | Wireless Headphones | $79.99  | Noise.. |
  |   Comment     |  2  | Mechanical Keyboard | $129.50 | Cherry. |
  |   Like        |  3  | USB-C Hub           | $45.00  | 7-in-1. |
  |               |                                               |
  | Migration     |  [Create] [Refresh]           Page 1 of 3     |
  | Status        |                                               |
  +---------------+-----------------------------------------------+
  | [n] New  [e] Edit  [d] Delete  [/] Search  [q] Quit          |
  +---------------------------------------------------------------+
```

The sidebar reads from `registered_models`. The main panel uses `StorableMixin.list()` with pagination. The create/edit screens are generated by `tui_form.py` (Proposition 5). The detail view maps to `ntt-item` size levels: `xs` -> `Label(name)`, `sm` -> `Horizontal(Label, Label, Label)`, `md/lg` -> full form. Method buttons come from `schema.methods`.

Textual apps can also be served to browsers via `textual serve`, giving three deployment modes from one codebase: terminal native, browser via WebSocket, and the existing `matrix.html` web frontend.

This is the moonshot. It is the highest-effort proposition but also the one that makes PyBend genuinely unique in the Python framework landscape.

| Dimension | Assessment |
|-----------|------------|
| **Effort** | 60-100 hours |
| **Impact** | Very high -- category-defining differentiator |
| **Risk** | Medium-high -- Textual dependency, maintenance surface |
| **Timeline** | Month 2-3 |

---

## Proposition Map

```
                        IMPACT
                 Low    Medium    High    Very High
              +--------+--------+--------+----------+
   Very High  |        |        |        |          |
              |        |        |        |          |
   High       |        |        |  P7    |  P9      |
              |        |        |  new   |  TUI     |
   Medium     |        |        |        |  P5      |
  EFFORT      |        |        |        |  forms   |
   Low-Med    |        |        |  P4    |  P3,P8   |
              |        |        |  shell |  inspect  |
   Low        |        |  P6    |  P2    |  P1      |
              |        | doctor |  CLI   |  setup() |
              +--------+--------+--------+----------+

  Quadrant Guide:
    Bottom-right = Quick wins (P1, P2, P3, P6)
    Middle-right = Strategic investments (P4, P5, P7, P8)
    Top-right    = Moonshots (P9)
```

**Proposition ranking by ROI (effort-adjusted impact):**

| Rank | Proposition | Effort | Impact | ROI |
|------|-------------|--------|--------|-----|
| 1 | P1: `setup()` extraction | 2-4 hrs | Critical | Infinite (blocker removal) |
| 2 | P2: CLI entry point | 8-16 hrs | High | Very high |
| 3 | P3: `inspect` command | 8-12 hrs | Very high | Very high |
| 4 | P6: `doctor` command | 4-6 hrs | Medium-high | High |
| 5 | P4: Interactive shell | 4-8 hrs | High | High |
| 6 | P8: Isomorphic arch | 8-12 hrs | High | High |
| 7 | P7: `pybend new` | 16-24 hrs | High | Medium-high |
| 8 | P5: Terminal forms | 20-30 hrs | Very high | Medium-high |
| 9 | P9: TUI dashboard | 60-100 hrs | Very high | Medium |

---

## What NOT to Do

### Anti-Pattern 1: Don't build a scaffolding-only CLI

The research documents the Create React App graveyard (01, Section 2.1): scaffolding CLIs that are used once and never maintained become actively harmful. A `pybend generate` command that creates boilerplate files from templates is the lowest-value, highest-maintenance CLI feature. PyBend already has `scaffold.py` for component generation -- it is schema-driven, not template-driven. Resist the urge to expand it into a "generate everything" system. The framework's value is that you do NOT need to generate code -- the schema derives it at runtime.

### Anti-Pattern 2: Don't add Textual as a hard dependency

Textual is ~3MB and pulls in significant transitive dependencies. For a framework that prides itself on minimal ceremony, making every `pip install pybend` include a TUI framework would violate the "zero to working" principle. Use optional dependency groups: `pip install pybend[cli]` for Typer/Rich, `pip install pybend[tui]` for Textual. The core framework stays lean.

### Anti-Pattern 3: Don't mirror the web UI in the terminal

The research (03, Section 10.1) identifies the "Mirror CLI" as an anti-pattern: a CLI that duplicates the web dashboard. The TUI admin (Proposition 9) is NOT a terminal clone of `matrix.html` -- it is a power-user tool for server-side administration. It does not need to render images, handle drag-and-drop, or replicate every web interaction. It needs to list entities, inspect schemas, create/edit records, and show migration status. The 80/20 rule applies: 85-90% of CRUD admin functionality maps cleanly to terminal widgets. The remaining 10-15% (images, rich media) degrades gracefully to text placeholders.

---

## Recommended Starting Point

**Start with P1 + P2 + P3, in that order, in a single sprint.**

1. **P1 (setup extraction, 2-4 hours):** This is the keystone. Without it, no CLI command can access registered models. It is a surgical refactor of `app.py` that extracts existing lines into a new method. Zero risk, zero breaking changes, infinite enabling value.

2. **P2 (CLI entry point, 8-16 hours):** This gives developers `pybend run`, `pybend models`, and the foundation for all future commands. It establishes the CLI package structure, Typer app, lazy loading, and the app-discovery mechanism. It is the scaffold that all subsequent propositions build on.

3. **P3 (inspect command, 8-12 hours):** This is the *signature* command -- the one that makes a developer say "wow, this framework understands itself." No other framework CLI can show you a model's fields, validation constraints, access rules, routes, methods, and UI configuration in one command. It is the CLI manifestation of PyBend's "the model is the app" philosophy.

Total: **18-32 hours of work** to deliver a CLI that matches Django's `manage.py` functionality and surpasses it with schema-aware inspection. This is achievable in a single focused week and immediately improves the developer experience for every PyBend user.
