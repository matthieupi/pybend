# CLI/TUI Interfaces: Relevance to the N3TX Stack

> **Angle:** How N3TX's schema-driven architecture maps to CLI/TUI generation.
> What we already have, what gaps exist, and what unique advantages our architecture provides.

---

## Executive Summary

N3TX's "the model is the app" philosophy gives it an unfair advantage in CLI/TUI generation that **no comparable framework possesses today**. Django's `manage.py` has ~50 built-in commands but requires separate management command classes. Rails scaffold generates files but from templates, not a live schema. Prisma generates client code but only for database access. N3TX already has the three pillars needed for a world-class CLI: a **model registry** that knows every entity (`registered_models` in `registrar.py`, line 9), a **schema generator** that produces complete JSON Schema with field types, validation, UI hints, and access rules (`ProtoModel.schema()` in `proto_model.py`, lines 198-316), and a **CRUD layer** that works without HTTP (`StorableMixin` in `storable_mixin.py`). The frontend already proves the concept -- `form.js` generates HTML forms from the same schema. A CLI could generate **terminal forms** from that same schema, making N3TX the only framework where `n3tx create Product` and `<ntx-item model="Product">` both derive from the same source of truth.

> **Key Insight:** N3TX is roughly **70% of the way to a complete CLI** with zero new code. The model registry, schema generation, CRUD operations, migration system, scaffold generator, and seed infrastructure all exist. What's missing is a **CLI entry point** to wire them together and a **TUI layer** to render schema-driven forms in the terminal.

---

## Table of Contents

1. [What N3TX Already Has](#what-ntx-already-has)
2. [Inventory: Existing Capabilities Mapped to CLI Commands](#inventory)
3. [The Schema-Driven Advantage](#the-schema-driven-advantage)
4. [Comparison with Major Framework CLIs](#comparison-with-major-framework-clis)
5. [Gap Analysis: What's Missing](#gap-analysis)
6. [Architecture: How a N3TX CLI Would Work](#architecture)
7. [Implementation Roadmap](#implementation-roadmap)
8. [TUI Dashboard Opportunity](#tui-dashboard-opportunity)
9. [Risk Assessment](#risk-assessment)
10. [Sources](#sources)

---

## What N3TX Already Has

Before designing anything new, here is a precise inventory of **existing code** that maps directly to CLI concerns. Every item below is a real function in the codebase today, not a proposal.

### Model Registry (`registrar.py`)

The `registered_models` dict at `/workspace/src/n3tx/core/utils/registrar.py` line 9 is a global registry of every model in the application:

```python
registered_models: Dict[str, Type[Any]] = {}  # tablename -> model class
join_models: Dict[tuple[str, str], Type[Any]] = {}  # (Parent, Child) -> join class
```

The `register_model()` function (line 14) handles the full lifecycle: sets storage backend, creates tables, and runs auto-migration. **A CLI command like `n3tx models` would need exactly 3 lines** to list every registered model.

### Schema Generation (`proto_model.py`)

`ProtoModel.schema()` at `/workspace/src/n3tx/core/models/proto_model.py` lines 198-316 produces a **complete JSON Schema document** including:

| Schema Section | Line Range | What It Contains |
|---|---|---|
| `properties` | 209-210 (Pydantic) | Field names, types, validation rules |
| `methods` | 220 | Exposed endpoints with parameters, return types |
| `$defs` | 222-241 | Referenced/nested model schemas |
| `access` | 256 | ABAC authorization rules (serialized) |
| `ui` | 283-306 | Field order, groups, renderer hints, widget types |
| `__tablename__` | 358 | Database table name |
| `__name__` | 355 | Python class name |

This is **far richer** than what Django's `inspectdb` or Rails' schema introspection produces. The schema carries *behavior* (methods, access rules, UI configuration), not just structure.

### Blueprint Method (`proto_model.py`)

`ProtoModel.blueprint()` at line 371-380 returns the complete schema for **every registered model** in one call:

```python
@staticmethod
def blueprint():
    from n3tx.core.utils.registrar import registered_models
    blueprint = {}
    for model_name, model_cls in registered_models.items():
        blueprint[model_name] = model_cls.schema()
    return blueprint
```

This is the foundation for commands like `n3tx describe --all` or a TUI model explorer.

### CRUD Operations (`storable_mixin.py`)

`StorableMixin` at `/workspace/src/n3tx/core/models/storable_mixin.py` provides **HTTP-independent CRUD**:

| Method | Line | Signature | CLI Mapping |
|---|---|---|---|
| `create()` | 64 | `cls.create(data)` | `n3tx create Product --name "Widget" --price 9.99` |
| `list()` | 92 | `cls.list(sql_filter, limit, offset)` | `n3tx list products --limit 10` |
| `get()` | 103 | `cls.get(id)` | `n3tx get products 42` |
| `update()` | 111 | `cls.update(id, data)` | `n3tx update products 42 --price 12.99` |
| `delete()` | 126 | `cls.delete(id)` | `n3tx delete products 42` |
| `save()` | 36 | `instance.save()` | (used internally) |

These methods work directly against the storage backend -- **no HTTP server needed**. A CLI can call `Product.list()` and get back model instances immediately.

### Migration System (`sqlite_migration.py`)

`SQLiteMigration` at `/workspace/src/n3tx/core/storage/sqlite_migration.py` already has a complete Rails-style migration system:

| Method | Line | CLI Equivalent |
|---|---|---|
| `create_table()` | 111 | `n3tx migrate` (auto) |
| `migrate_table()` | 193 | `n3tx migrate` (column add/remove) |
| `run_migrations()` | 375 | `n3tx migrate:run` |
| `rollback(steps)` | 415 | `n3tx migrate:rollback --steps 2` |
| `migration_status()` | 465 | `n3tx migrate:status` |
| `_discover_migrations()` | 325 | (internal discovery) |

The `Migration` base class (line 19) supports user-written up/down migrations. The `_migrations` tracking table (line 61) records applied migrations with timestamps. **This is a fully operational migration CLI backend -- it just needs a front door.**

### Scaffold Generator (`scaffold.py`)

`/workspace/src/n3tx/core/utils/scaffold.py` is the most CLI-adjacent code that exists today. It already has:

- **CLI entry point** (line 422): `python -m utils.scaffold Product`
- **API endpoint** (integrated in `routes_fastapi.py` line 169): `GET /Product?scaffold=item`
- **Four generators**: `scaffold_item()`, `scaffold_list()`, `scaffold_css()`, `scaffold_list_css()`
- **File writing**: `scaffold_model()` (line 346) writes files to disk, skipping existing ones

The scaffold reads the schema and generates Web Components. The same pattern would generate Python model files from a CLI.

### Seed Data (`seed.py`)

`/workspace/src/n3tx/example/seed.py` shows an existing pattern for database population. It imports models, registers them with storage, and creates records programmatically. The `--reset` flag (line 162) already handles database cleanup. **A `n3tx seed` command would wrap this pattern.**

### Auth Configuration (`auth.py`)

`/workspace/src/n3tx/core/authorize/auth.py` has `configure()` (line 23), `create_token()` (line 46), and `hash_password()` (line 38). A CLI could offer `n3tx token --email alice@example.com` for development.

### App Bootstrap (`app.py`)

`create_app()` at `/workspace/src/n3tx/core/app.py` line 180 and `N3TXApp` (line 59) handle the complete application wiring. The three-level bootstrap pattern means a CLI could:
- **Level 1**: `n3tx run` (wraps `create_app()`)
- **Level 2**: `n3tx run --builder` (uses `N3TXApp`)
- **Level 3**: Let advanced users wire things manually

---

## Inventory

Here is a complete mapping of existing N3TX capabilities to potential CLI commands:

```
EXISTING CODE                          POTENTIAL CLI COMMAND
---------------------------------------------------------------------
registered_models                  --> n3tx models
ProtoModel.schema()                --> n3tx describe Product
ProtoModel.blueprint()             --> n3tx describe --all
StorableMixin.list()               --> n3tx list products
StorableMixin.get(id)              --> n3tx get products 42
StorableMixin.create(data)         --> n3tx create Product --name X
StorableMixin.update(id, data)     --> n3tx update products 42 --price 9
StorableMixin.delete(id)           --> n3tx delete products 42
SQLiteMigration.run_migrations()   --> n3tx migrate
SQLiteMigration.rollback(n)        --> n3tx migrate:rollback
SQLiteMigration.migration_status() --> n3tx migrate:status
scaffold_model()                   --> n3tx scaffold Product
scaffold_single(kind='item')       --> n3tx scaffold Product --kind item
seed.py                            --> n3tx seed [--reset]
create_app()                       --> n3tx run
config.configure()                 --> n3tx config:show
auth.create_token()                --> n3tx token --email X
generate_docs()                    --> n3tx docs

NOT YET EXISTING:
(none)                             --> n3tx new myapp
(none)                             --> n3tx model Product name:str price:float
(none)                             --> n3tx shell (interactive REPL)
(none)                             --> n3tx tui (Textual dashboard)
```

> **Key Insight:** Of the 18 commands listed above, **14 are direct wrappers** around existing functions. Only 4 require genuinely new functionality (project creation, model generation, interactive shell, TUI dashboard).

---

## The Schema-Driven Advantage

This is where N3TX has a **structural advantage** over every other framework.

### The Problem with Traditional CLI Scaffolding

Django, Rails, and Laravel generate code from **templates**. When you run `rails generate scaffold Post title:string body:text`, Rails doesn't know your model -- it interpolates strings into ERB templates. The generated code is a one-shot snapshot that immediately diverges from the model.

```
Traditional Framework CLI:
  [Template Files] --string interpolation--> [Generated Code]
       |                                          |
  (static, one-shot)                    (diverges immediately)
```

### N3TX's Schema-Driven Approach

N3TX generates **everything from a live schema**. The frontend already proves this works at scale -- `form.js` reads `schema.properties` and emits the correct HTML input for each field type, with validation constraints, widget hints, and access-controlled visibility.

```
N3TX Schema Flow:
  [Python Model] --ProtoModel.schema()--> [JSON Schema]
       |                                      |
  (single source of truth)                    |
       |                    +-----------------+-----------------+
       |                    |                 |                 |
       v                    v                 v                 v
  [API Routes]     [Web Forms (form.js)]  [CLI Forms]    [TUI Forms]
  (routes_fastapi)  (already works)       (proposed)     (proposed)
```

### What the Schema Carries (That Others Don't)

| Information | Django CLI Has It? | Rails CLI Has It? | N3TX Schema Has It? |
|---|---|---|---|
| Field names and types | Yes | Yes | Yes |
| Validation constraints | No (separate) | No (separate) | **Yes** (`minLength`, `gt`, `pattern`) |
| UI widget hints | No | No | **Yes** (`ui.widget: "currency"`) |
| Field display order | No | No | **Yes** (`ui.field_order`) |
| Field grouping | No | No | **Yes** (`ui.groups`) |
| Access control rules | No | No | **Yes** (`access.update: OWNER \| ROLE('admin')`) |
| Custom method signatures | No | No | **Yes** (`methods.comment.parameters`) |
| Related model schemas | Partial | Partial | **Yes** (`$defs` with full schemas) |
| Protected field marking | No | No | **Yes** (`ui.protected: true`) |
| Hidden field marking | No | No | **Yes** (`ui.display: false`) |

This means a N3TX CLI could:
1. **Generate interactive terminal forms** from the same schema that generates web forms
2. **Enforce validation** in the terminal using `minLength`, `gt`, `pattern` from the schema
3. **Hide protected fields** in creation forms (same as the web UI does)
4. **Show access-aware options** -- e.g., only show `delete` if the user's role permits it
5. **Render currency fields** with `$` prefix in terminal output, just like `form.js` does

### Concrete Example: Schema-to-Terminal-Form

The Product schema includes:

```python
# From /workspace/src/n3tx/example/models/product.py
name: str = Field(min_length=1, max_length=200, 
                  json_schema_extra={'ui': {'placeholder': 'Product name...'}})
price: float = Field(gt=0, json_schema_extra={'ui': {'widget': 'currency'}})
description: str = Field(default='', json_schema_extra={'ui': {'widget': 'textarea'}})
```

The resulting schema properties would drive a terminal form:

```
n3tx create Product

  Product name...: [                    ]  (required, 1-200 chars)
  Price ($):      [        ]               (required, > 0)
  Description:    [                    ]   (optional, multiline)
                  [                    ]

  [Create]  [Cancel]
```

The form knows:
- `name` is required (from `min_length=1`), has a placeholder, max 200 chars
- `price` is a currency widget, must be > 0
- `description` is a textarea widget, optional (has default)
- `image` is hidden (`_AUTO_HIDE_FIELDS` in `proto_model.py` line 23)
- `comments` and `favorites` are ListRef arrays -- skip in creation form

**No other framework CLI can do this from a single model definition.**

---

## Comparison with Major Framework CLIs

### Command Coverage Comparison

| Command Category | Django `manage.py` | Rails `bin/rails` | Laravel `artisan` | Prisma CLI | N3TX (today) | N3TX (proposed) |
|---|---|---|---|---|---|---|
| Run server | `runserver` | `server` | `serve` | -- | `python main.py` | `n3tx run` |
| Create project | `startproject` | `new` | `new` | `init` | -- | `n3tx new` |
| Create model | `startapp` + manual | `generate model` | `make:model` | `prisma migrate` | -- | `n3tx model` |
| Scaffold (full CRUD) | -- | `generate scaffold` | -- | -- | `scaffold.py` (JS only) | `n3tx scaffold` |
| List models | `showmigrations` (partial) | -- | -- | -- | `registered_models` dict | `n3tx models` |
| Describe model | `inspectdb` (reverse) | -- | -- | `prisma studio` | `ProtoModel.schema()` | `n3tx describe` |
| CRUD operations | `shell` (manual) | `console` (manual) | `tinker` (manual) | `prisma studio` (GUI) | `StorableMixin` methods | `n3tx crud` |
| Migrations: run | `migrate` | `db:migrate` | `migrate` | `prisma migrate` | `run_migrations()` | `n3tx migrate` |
| Migrations: status | `showmigrations` | `db:migrate:status` | `migrate:status` | `prisma migrate status` | `migration_status()` | `n3tx migrate:status` |
| Migrations: rollback | `migrate app 0001` | `db:rollback` | `migrate:rollback` | `prisma migrate reset` | `rollback(steps)` | `n3tx migrate:rollback` |
| Seed data | `loaddata` (fixtures) | `db:seed` | `db:seed` | `prisma db seed` | `seed.py` | `n3tx seed` |
| Interactive shell | `shell` | `console` | `tinker` | -- | -- | `n3tx shell` |
| Generate docs | `admindocs` | `doc:` namespace | -- | -- | `generate_docs()` | `n3tx docs` |
| Auth token | -- | -- | -- | -- | `create_token()` | `n3tx token` |
| **Total commands** | **~50** | **~30** | **~40** | **~12** | **0 (as CLI)** | **~18** |

### Architectural Depth Comparison

| Feature | Django | Rails | N3TX Proposed |
|---|---|---|---|
| CLI framework | Custom `BaseCommand` | Thor gem | Typer (recommended) |
| Schema source | ORM introspection | ActiveRecord schema.rb | `ProtoModel.schema()` JSON Schema |
| Carries validation? | No (separate validators) | No (separate validators) | **Yes** (in schema) |
| Carries UI hints? | No (Django admin is separate) | No | **Yes** (`ui.widget`, `ui.groups`) |
| Carries access rules? | No (permissions are separate) | No | **Yes** (`access` in schema) |
| Form generation? | Django admin (web only) | `form_for` (web only) | **Web + CLI + TUI from same schema** |
| Model discovery? | `INSTALLED_APPS` + import | Convention (`app/models/`) | `registered_models` dict (explicit) |
| Interactive REPL? | `python manage.py shell` | `rails console` | Proposed: `n3tx shell` |

> **Key Insight:** Django has the most commands (~50), but they evolved over 20 years of bolt-on additions. N3TX could ship 18 commands that are **schema-aware from day one** -- something Django can't retrofit because its models don't carry UI hints, access rules, or method signatures in a unified schema.

### Django's Custom Command Pattern vs N3TX

Django's management command system requires creating a file in `management/commands/` with a `Command` class extending `BaseCommand`:

```python
# Django: management/commands/list_products.py (14+ lines)
from django.core.management.base import BaseCommand
from myapp.models import Product

class Command(BaseCommand):
    help = 'List all products'
    
    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=10)
    
    def handle(self, *args, **options):
        products = Product.objects.all()[:options['limit']]
        for p in products:
            self.stdout.write(f"{p.id}: {p.name} - ${p.price}")
```

N3TX equivalent with schema-driven generation (hypothetical, ~3 lines of new code):

```python
# N3TX: auto-generated from registered_models + StorableMixin
# No per-model command file needed -- the registry + CRUD layer IS the command
products = Product.list(limit=10)
for p in products:
    print(f"{p.id}: {p.name} - ${p.price}")
```

The N3TX version doesn't need a command file per model because the **registry knows every model** and **StorableMixin provides uniform CRUD**.

---

## Gap Analysis

### What's Missing (Prioritized)

| # | Gap | Effort | Why It Matters | Depends On |
|---|---|---|---|---|
| 1 | **CLI entry point** (`__main__.py` or `console_scripts`) | ~2h | No way to invoke `n3tx` from terminal today | Nothing |
| 2 | **Command router** (Typer/Click app) | ~3h | Routes `n3tx <command>` to the right function | #1 |
| 3 | **Model discovery without HTTP** | ~2h | Need to import and register models without starting uvicorn | #1 |
| 4 | **Model file generator** | ~4h | `n3tx model Product name:str price:float` creates `.py` file | #2 |
| 5 | **Project scaffolding** | ~4h | `n3tx new myapp` creates directory structure | #2 |
| 6 | **Interactive shell** (IPython/PtPython REPL) | ~3h | `n3tx shell` with models pre-imported | #3 |
| 7 | **Schema-driven terminal forms** | ~6h | Interactive CRUD with validation from schema | #3, Textual or questionary |
| 8 | **TUI dashboard** | ~12h | Full Textual app for admin | #3, #7 |

### The Model Discovery Problem

The biggest technical gap is **#3: model discovery without HTTP**. Today, models get registered during `create_app()` which creates a FastAPI instance. A CLI needs to:

1. Import the user's model classes
2. Set up storage backends
3. Register models (which creates tables and runs migrations)
4. **NOT** start an HTTP server

The fix is straightforward. `N3TXApp.build()` (at `/workspace/src/n3tx/core/app.py` line 128) does steps 1-3 before step 4. A CLI would call a subset:

```python
# Proposed: N3TXApp.setup() -- does everything except HTTP
def setup(self):
    """Register models and configure storage without starting HTTP."""
    authorize.configure(jwt_secret=self._jwt_secret or config.JWT_SECRET)
    for model_class, per_model_storage in self._models:
        effective_storage = _resolve_storage(per_model_storage) if per_model_storage else self._storage
        register_model(model_class, storage=effective_storage)
    for parent, child in self._join_pairs:
        join_model = generate_join_model(parent, child)
        register_model(join_model, storage=self._storage)
```

This is literally the first 12 lines of `build()` (lines 141-159) extracted into their own method. **Zero new logic required.**

---

## Architecture

### Proposed CLI Structure

```
n3tx/
  __main__.py          <-- NEW: entry point for `python -m n3tx`
  cli/                 <-- NEW: CLI package
    __init__.py
    app.py             <-- Typer app definition, command router
    commands/
      run.py           <-- n3tx run (wraps uvicorn)
      models.py        <-- n3tx models, n3tx describe
      crud.py          <-- n3tx list/get/create/update/delete
      migrate.py       <-- n3tx migrate, migrate:status, migrate:rollback
      scaffold.py      <-- n3tx scaffold Product (wraps existing scaffold.py)
      seed.py          <-- n3tx seed [--reset]
      new.py           <-- n3tx new myapp (project scaffold)
      model.py         <-- n3tx model Product name:str price:float
      shell.py         <-- n3tx shell (REPL)
      docs.py          <-- n3tx docs (wraps generate_docs)
      token.py         <-- n3tx token --email X
    discovery.py       <-- Model discovery + registration without HTTP
    tui/               <-- FUTURE: Textual dashboard
      __init__.py
      dashboard.py
      forms.py         <-- Schema-driven terminal forms
```

### Data Flow: CLI Command Execution

```
User types: n3tx list products --limit 5

  [Typer CLI Router]
        |
        v
  [discovery.py] -- imports user's app config, calls N3TXApp.setup()
        |
        v
  [registered_models] -- now populated with Product, User, etc.
        |
        v
  [crud.py: list_command()] -- resolves "products" -> Product class
        |
        v
  [Product.list(limit=5)] -- StorableMixin.list() hits SQLite directly
        |
        v
  [Rich table output] -- renders results with field names from schema

Output:
  Products (5 of 23)
  +----+---------------------+--------+---------------------------------+
  | ID | Name                | Price  | Description                     |
  +----+---------------------+--------+---------------------------------+
  |  1 | Wireless Headphones | $79.99 | Noise-cancelling over-ear...    |
  |  2 | Mechanical Keyboard | $129.50| Cherry MX Brown switches...     |
  |  3 | USB-C Hub           | $45.00 | 7-in-1 hub: HDMI, USB-A x3...  |
  |  4 | Standing Desk Mat   | $39.99 | Anti-fatigue ergonomic mat...   |
  |  5 | Monitor Light Bar   | $54.95 | Asymmetric LED light bar...     |
  +----+---------------------+--------+---------------------------------+
```

### Recommended Technology Stack

| Component | Recommendation | Why |
|---|---|---|
| CLI framework | **Typer** | Same author as FastAPI (tiangolo), type-hint driven, auto-completion, Rich integration |
| Terminal output | **Rich** | Tables, syntax highlighting, progress bars, tree views. Already a Typer dependency |
| Terminal forms | **textual-forms** or **questionary** | Schema-driven form rendering in terminal |
| TUI framework | **Textual** | CSS-like layout, widget system, async, from Rich ecosystem |
| REPL | **IPython** or **ptpython** | Auto-import models, tab completion |

The **Typer + Rich** combination is ideal because:
1. Typer uses **Python type hints** (same philosophy as Pydantic/N3TX)
2. Rich produces **beautiful terminal output** (tables, trees, panels)
3. Both are maintained by Textualize (Will McGuigan)
4. Textual extends Rich for full TUI applications
5. Typer is from the FastAPI ecosystem (already a N3TX dependency author)

### Entry Point Configuration

In `pyproject.toml` (currently at `/workspace/pyproject.toml`):

```toml
[project.scripts]
n3tx = "n3tx.cli:app"

[project.optional-dependencies]
cli = ["typer>=0.12", "rich>=13.0"]
tui = ["textual>=0.80", "textual-forms>=0.5"]
```

This would allow:
- `pip install n3tx` -- framework only (current behavior)
- `pip install n3tx[cli]` -- framework + CLI tools
- `pip install n3tx[tui]` -- framework + CLI + TUI dashboard

---

## Implementation Roadmap

### Phase 1: Foundation (1-2 days, ~8 hours)

**Goal:** `n3tx run`, `n3tx models`, `n3tx describe`, `n3tx migrate:status`

| Task | Effort | Files | Description |
|---|---|---|---|
| Create `cli/` package + Typer app | 1h | `cli/__init__.py`, `cli/app.py` | Basic command routing |
| Add `__main__.py` | 0.5h | `n3tx/__main__.py` | `python -m n3tx` support |
| Model discovery | 2h | `cli/discovery.py` | Import user app, call `setup()` |
| `n3tx run` | 1h | `cli/commands/run.py` | Wrap uvicorn with config |
| `n3tx models` | 1h | `cli/commands/models.py` | Rich table of `registered_models` |
| `n3tx describe Product` | 1.5h | `cli/commands/models.py` | Schema tree view with Rich |
| `n3tx migrate:status` | 1h | `cli/commands/migrate.py` | Wrap `migration_status()` |

**Estimated output:**
```
$ n3tx models

  Registered Models
  +----------+------------+-----------+--------+---------+
  | Name     | Table      | Storable  | Fields | Methods |
  +----------+------------+-----------+--------+---------+
  | Product  | products   | Yes       | 6      | 2       |
  | User     | users      | Yes       | 6      | 2       |
  | Comment  | comments   | Yes       | 5      | 2       |
  | Like     | likes      | Yes       | 2      | 0       |
  +----------+------------+-----------+--------+---------+
  4 models, 2 join models
```

### Phase 2: CRUD + Migration (1-2 days, ~8 hours)

**Goal:** Full terminal CRUD and migration management

| Task | Effort | Files |
|---|---|---|
| `n3tx list <table>` | 1.5h | `cli/commands/crud.py` |
| `n3tx get <table> <id>` | 1h | `cli/commands/crud.py` |
| `n3tx create <Model>` (with schema-driven prompts) | 2h | `cli/commands/crud.py` |
| `n3tx update <table> <id>` | 1.5h | `cli/commands/crud.py` |
| `n3tx delete <table> <id>` | 0.5h | `cli/commands/crud.py` |
| `n3tx migrate` / `n3tx migrate:rollback` | 1h | `cli/commands/migrate.py` |
| `n3tx seed` | 0.5h | `cli/commands/seed.py` |

### Phase 3: Scaffolding + Shell (1 day, ~6 hours)

**Goal:** Code generation and interactive REPL

| Task | Effort | Files |
|---|---|---|
| `n3tx scaffold Product` (wrap existing) | 1h | `cli/commands/scaffold.py` |
| `n3tx model Product name:str price:float` | 3h | `cli/commands/model.py` |
| `n3tx shell` | 1.5h | `cli/commands/shell.py` |
| `n3tx docs` | 0.5h | `cli/commands/docs.py` |

### Phase 4: TUI Dashboard (3-5 days, ~20 hours)

**Goal:** Full Textual-based admin interface

This is the most ambitious phase but also the most differentiating. No framework offers a terminal-native admin dashboard that reads from the same schema as the web UI.

---

## TUI Dashboard Opportunity

### Why This Matters

According to a [2024 Gartner report cited by johal.in](https://johal.in/rich-tui-applications-terminal-user-interfaces-built-with-python-for-admin-tools/), TUI adoption in cloud-native environments has surged **65%**. Textual has reached **2.5M PyPI downloads** ([johal.in TUI analysis](https://johal.in/textual-tui-widgets-python-rich-terminal-user-interfaces-apps-2025/)). The reason: SSH sessions, containers, and CI/CD pipelines often have terminals but no browsers.

### Schema-Driven TUI Forms

The existing `form.js` at `/workspace/src/n3tx/static/generators/form.js` demonstrates the pattern for converting schema properties to form inputs (lines 173-236). The `getInput()` function maps schema types to HTML inputs:

| Schema Type/Widget | form.js Output | TUI Equivalent |
|---|---|---|
| `type: "string"` | `<input type="text">` | `textual.widgets.Input()` |
| `type: "number"` | `<input type="number">` | `textual.widgets.Input(type="number")` |
| `type: "boolean"` | `<input type="checkbox">` | `textual.widgets.Switch()` |
| `widget: "textarea"` | `<textarea>` | `textual.widgets.TextArea()` |
| `widget: "currency"` | `<div class="currency-input">` | Custom `CurrencyInput` widget |
| `type: "array"` | Nested `<ntx-item>` list | Nested `DataTable` |

The [textual-forms library](https://github.com/rhymiz/textual-forms) already provides dynamic form generation for Textual. Combined with N3TX's schema, a TUI form generator could be ~200 lines of code that maps JSON Schema properties to Textual widgets.

### Architecture: TUI Dashboard

```
n3tx tui

  +---------------------------------------------------------------+
  | N3TX Admin                                     localhost:5000 |
  +---------------+-----------------------------------------------+
  |               |                                               |
  | Models        |  Products (23 total)                          |
  |               |                                               |
  | > Product     |  ID | Name                | Price   | Desc    |
  |   User        |  1  | Wireless Headphones | $79.99  | Noise.. |
  |   Comment     |  2  | Mechanical Keyboard | $129.50 | Cherry. |
  |   Like        |  3  | USB-C Hub           | $45.00  | 7-in-1. |
  |               |  4  | Standing Desk Mat   | $39.99  | Anti-f. |
  |               |  5  | Monitor Light Bar   | $54.95  | Asymme. |
  | Migration     |                                               |
  | Status        |  [Create] [Refresh] [Export]    Page 1 of 3   |
  |               |                                               |
  +---------------+-----------------------------------------------+
  | Logs: INFO n3tx.api: GET /products 200 OK (12ms)            |
  +---------------------------------------------------------------+
```

The sidebar reads from `registered_models`, the main panel uses `StorableMixin.list()`, the create button generates a form from `ProtoModel.schema()`.

---

## Risk Assessment

### Risks of Adding a CLI

| Risk | Severity | Mitigation |
|---|---|---|
| **Dependency bloat** | Medium | Optional dependencies: `pip install n3tx[cli]` keeps core lean |
| **Model discovery complexity** | Medium | User must provide app module path; convention: `--app myapp.main:app` |
| **Maintenance surface** | Medium | CLI commands are thin wrappers -- if CRUD layer changes, CLI follows |
| **Scope creep** | High | Phase 1-2 are high-value/low-effort; Phase 4 TUI is optional |
| **Competing with Django admin** | Low | Different niche: terminal-native, schema-driven, no browser needed |

### Risks of NOT Adding a CLI

| Risk | Severity | Notes |
|---|---|---|
| **Developer experience gap** | High | Every modern framework has a CLI; lacking one signals immaturity |
| **Onboarding friction** | High | New users must read docs instead of running `n3tx new myapp` |
| **Wasted schema potential** | Medium | The schema carries everything a CLI needs but nobody consumes it |
| **Migration management** | Medium | `migration_status()` exists but is inaccessible without code |

### Advantages: What N3TX Brings That Others Cannot

- **Single schema generates web forms AND terminal forms** -- unique in the industry
- **Zero per-model CLI code** -- CRUD commands work for any registered model
- **Schema carries behavior** (methods, access, UI hints) -- CLI can be smart, not just structural
- **The registry is the CLI's menu** -- `registered_models` IS the command namespace
- **Validation built into schema** -- terminal forms enforce the same rules as web forms

> **Key Insight:** The strongest argument for a N3TX CLI is not "other frameworks have one" -- it is that **N3TX's architecture makes the CLI almost free**. The schema, registry, CRUD layer, migration system, scaffold generator, and seed infrastructure already exist. The CLI is a ~500-line entry point that exposes what's already there.

---

## Comparison: Lines of Code to Add a CLI

| Framework | Lines to Add a New CLI Command | Why |
|---|---|---|
| Django | ~25 lines (BaseCommand subclass per command) | Each command is an independent class with `add_arguments` + `handle` |
| Rails | ~15 lines (Thor task) | Convention-based, but still per-command |
| Laravel | ~20 lines (Artisan command class) | Signature string + `handle()` |
| **N3TX (proposed)** | **~5-10 lines per command** | Typer + existing functions = thin wrappers |

Example: The `n3tx models` command would be approximately:

```python
import typer
from rich.table import Table
from rich.console import Console

app = typer.Typer()
console = Console()

@app.command()
def models():
    """List all registered models."""
    from n3tx.core.utils.registrar import registered_models
    table = Table(title="Registered Models")
    table.add_column("Name")
    table.add_column("Table")
    table.add_column("Fields", justify="right")
    table.add_column("Methods", justify="right")
    for name, cls in registered_models.items():
        schema = cls.schema()
        fields = len(schema.get('properties', {}))
        methods = len(schema.get('methods', {}))
        table.add_row(cls.__name__, name, str(fields), str(methods))
    console.print(table)
```

That is **18 lines** for a fully functional, beautifully formatted model listing command. The equivalent Django command would be 25+ lines without the rich formatting.

---

## Summary: The Bottom Line

| Dimension | Status | Action |
|---|---|---|
| Schema carries enough info for CLI | **Yes** | No changes to schema needed |
| CRUD layer works without HTTP | **Yes** | StorableMixin calls storage directly |
| Migration system has CLI-ready API | **Yes** | `run_migrations()`, `rollback()`, `migration_status()` |
| Model registry supports introspection | **Yes** | `registered_models`, `ProtoModel.blueprint()` |
| Scaffold generator exists | **Yes** | `scaffold.py` generates JS components |
| CLI entry point exists | **No** | Need `__main__.py` + Typer app |
| Project scaffolding exists | **No** | Need `n3tx new myapp` template |
| Model file generator exists | **No** | Need `n3tx model Product name:str` |
| Interactive shell exists | **No** | Need REPL with pre-imported models |
| TUI dashboard exists | **No** | Need Textual app (optional, high-impact) |

**Effort estimate for a production-quality CLI (Phases 1-3):** ~22 hours of development
**Effort estimate including TUI dashboard (Phase 4):** ~42 hours total

The N3TX CLI would be the **first schema-driven framework CLI** that generates terminal forms, CRUD commands, and admin dashboards from the same schema that drives the web UI. This is not an incremental feature -- it is a **category-defining capability** that no other framework can match without a fundamental architecture change.

---

## Sources

- [Django admin and manage.py documentation](https://docs.djangoproject.com/en/5.2/ref/django-admin/) -- Complete reference for Django's ~50 built-in commands
- [Django custom management commands](https://docs.djangoproject.com/en/5.2/howto/custom-management-commands/) -- Architecture for extending Django CLI
- [Django migrations documentation](https://docs.djangoproject.com/en/5.2/topics/migrations/) -- Migration commands: showmigrations, makemigrations, sqlmigrate, migrate
- [Rails command line guide](https://guides.rubyonrails.org/command_line.html) -- Official Rails CLI reference
- [Rails scaffolding complete guide 2026](https://www.railscarma.com/blog/scaffolding-in-ruby-on-rails-complete-guide/) -- Scaffolding internals and file generation
- [Prisma CLI reference](https://www.prisma.io/docs/orm/reference/prisma-cli-reference) -- Schema-driven code generation commands
- [Prisma schema documentation](https://www.prisma.io/docs/orm/prisma-schema/overview) -- Single source of truth schema approach
- [Laravel Artisan documentation](https://laravel.com/docs/12.x/artisan) -- 40+ commands including tinker REPL
- [Typer -- CLI framework](https://github.com/fastapi/typer) -- Type-hint driven CLI from FastAPI author
- [Typer features and alternatives](https://typer.tiangolo.com/alternatives/) -- Comparison with Click, argparse
- [Textual TUI framework](https://textual.textualize.io/) -- Modern Python TUI with CSS layout, 2.5M PyPI downloads
- [textual-forms for dynamic forms](https://github.com/rhymiz/textual-forms) -- Dynamic form generation for Textual
- [Rich TUI applications for admin tools](https://johal.in/rich-tui-applications-terminal-user-interfaces-built-with-python-for-admin-tools/) -- TUI adoption surging 65% in cloud-native environments
- [Schema-driven development and single source of truth](https://godspeed.systems/blog/schema-driven-development-and-single-source-of-truth) -- Industry perspective on schema-first architecture
- [Schema-driven platforms: JSON Schema as underrated tool](https://peterhrynkow.com/ai/architecture/2025/02/01/schema-driven-platforms.html) -- JSON Schema as universal contract
- [FastAPI CLI tools](https://fastapi.tiangolo.com/fastapi-cli/) -- Official FastAPI CLI for development
- [MakeFast: FastAPI CLI manager](https://medium.com/@chethanaperera272/makefast-streamlining-fastapi-development-with-an-efficient-cli-manager-53de89371b33) -- Third-party FastAPI scaffolding tool
- [AT Protocol Lexicon schema system](https://deepwiki.com/bluesky-social/atproto/2.3-lexicon-schema-system) -- Schema-driven code generation from JSON Schema definitions (Bluesky)
- [Form.io: Schema-driven form architecture](https://form.io/features/form-from-json-schema/) -- JSON Schema to form generation patterns
- [Click vs Typer comparison](https://johal.in/click-vs-typer-comparison-choosing-cli-frameworks-for-python-application-distribution/) -- CLI framework selection guidance