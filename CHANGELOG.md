# Pybend Change Log

# 0.7.0 (2026-02)

## Backend
- [x] **[ForeignKey Hydration](src/pybend/core/docs/features/01_ForeignKey_Hydration.md)**
  - Added SQLite migration system (`sqlite_migration.py`) with Rails-style run/rollback
  - Added `ListRef[T]` type (`models/ref.py`) for FK hydration — collection fields return href arrays instead of embedded objects
  - Added `__fk_models__` cache on parent models for join model resolution
  - Added `collection_field_names` filter in `update()` to skip List[BaseModel] fields
  - Moved type introspection utilities to `utils/introspection.py` (`get_list_fields`, `_unwrap_listref`)
  - Added nested routes for child entity access (`/tablename/:id/field/:child_id`)

## Frontend
- [x] **[Refactor PTT into NTT](src/pybend/static/NTT0.6/docs/PTT_NTT_MERGE.md)**
  - Merged PTT into NTT — NTT is now the universal type registry, schema proxy, and ATTACH router
  - Added null-pointer bootstrap pattern with TX message queueing for async schema loading
  - Added `NTT.SCHEMA` static handler for bootstrap completion and DynamicClass generation
  - Added `NTT.ATTACH` universal router handling both type-level and instance-level ATTACHes
  - Added optimistic update flow: `NTT.UPDATE` updates locally then forwards to backend
- Added `save()` method on `<ntt-item>` with NTT-mediated update path
- Added favicon (SVG)

## Documentation
- Created comprehensive README.md for NTT 0.6 (quickstart, architecture, dataflow, CRUD, components)
- Documented FK hydration across README.md, ARCHITECTURE.md, ACTORS.md, COMPONENTS.md, MESSAGE_PROTOCOL.md, TRANSPORT.md
- Added PTT/NTT merge report (`docs/PTT_NTT_MERGE.md`)
- Added FK hydration implementation report (`core/docs/features/FK_HYDRATION.md`)
- Created TODOs.md for project task tracking

# 0.6.0 (2025-12)

## Frontend — Actor Model Architecture (NTTTX v0.6)
- Rewrote entire frontend from event-bus architecture (NTT 0.5) to actor-based model
- Introduced `Actor` base class with hierarchical message routing (`_send` 3-case dispatch, `_inbox` dispatch-or-forward)
- Introduced `Matrix` as root actor and central message router
- Introduced `TX` (Transaction) as the universal message envelope (name, source, target, data, meta)
- Introduced `TT` (Transfer Type) as base entity class with watcher pattern and Observable mixin
- Introduced `PTT` (Proto Transfer Type) as schema proxy and dynamic class factory
- Introduced `NTT` (Named Transfer Type) as per-entity instance base class
- Introduced `DynamicClass` — runtime-generated NTT subclass per backend model with typed getters/setters
- Introduced `Component` base class extending `HTMLElement` with actor registration
- Added `Observable` mixin (`signal`, `observe`, `notify`) applied via `Actor.subclass()`
- Added `NetworkAdapter` for HTTP transport (GET/POST/PUT/DELETE) with TX-based request/response

## Infrastructure
- Added `matrix.html` — main application entry point
- Added `schema.html` — interactive schema explorer page
- Added `config.js` for frontend configuration (API_URL, debug flags)

# 0.5.0 (2025-07)

## Frontend — NTTTX v0.5
- Created NTT 0.5 frontend with event-based architecture (`Event.js`, `Remote.js`, `HTTP.js`)
- Created `<ntt-element>` web component — base component with data binding and render lifecycle
- Created `<ntt-list>` — renders a collection of `<ntt-item>` elements from a model type
- Created `<ntt-item>` — renders a single entity with auto-generated form fields from schema
- Created `<ntt-method>` — invokes backend RPC methods on entities
- Abstracted `<ntt-element>` base class, improved cross-system bindings
- Created `Formidable` form generator — auto-generates input fields from JSON schema (text, number, select, textarea, ref)
- Uncoupled form generation from `<ntt-item>` into standalone generator
- Added `dark-theme.css` with design tokens
- Removed legacy NTT 0.0–0.4 frontend versions (~10,000 lines deleted)

## Backend
- Added methods signature to JSON schema endpoint (`schema.methods`)
- Fixed routes registration closure bug — models were all binding to last registered model
- Added `ProtoModel.__init__` by id for direct entity lookup
- Added `List[RefProtoModel]` backend logic for one-to-many references
- Added nested routes for references (`POST /products/:id/comments`)
- Added join model architecture for managing entity relationships
- Started foreign key implementation with schema view support
- Added SQLite database file support

# 0.2.0 (2025-04)
- Added interface for multiple backend (added FastAPI)
- Updated README to reflect new features
- Created Universal Context Protocol (UCP) specification document for
  compute over meta models (COMM) first draft (very rough, WIP)

# 0.1.0 (2024-12)

## Initial release
- Created pybend module with flask and swagger support
- Support for multiple backend storages