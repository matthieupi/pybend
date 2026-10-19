# Frontend Unit Test Plan — N3TX N3TX 0.6

> **Scope**: Every exported function, method, class, and behavior in the N3TX 0.6 frontend.
> **Framework**: Vitest + jsdom (or similar JS test runner)
> **Estimated test cases**: ~700+

---

## CORE LAYER

### N3TX.js (TT & N3TX Classes)

#### TT Class (Base Transfer Type)

**`constructor(addr, href)`**
- Happy path: valid address and href
- Edge case: empty string address
- Edge case: null/undefined address
- Edge case: null href (should default to `${config.API_URL}/${addr}`)

**`href` (getter/setter)**
- Happy path: get href after construction
- Happy path: set valid URL
- Edge case: set empty string

**`watch(addr, immediate=true)`**
- Happy path: watch valid address with immediate=true
- Happy path: watch valid address with immediate=false
- Edge case: watch with null/undefined addr
- Verify TX sent via matrix with correct event name (E.update)
- Verify watchers set is updated

**`notify(value)`**
- Happy path: notify with undefined value (extracts from this.value)
- Happy path: notify with array value
- Happy path: notify with single object value
- Edge case: notify when no watchers registered
- Verify each watcher receives TX

**`call(method, data={}, meta={})`**
- Happy path: call with method name and data
- Happy path: call with empty data
- Happy path: call with metadata
- Edge case: call with null method
- Verify TX sent through matrix with correct target

**`_error_(event)`**
- Happy path: error handler receives event with error data
- Verify logging called

#### N3TX Class (Named Transfer Type — Core Entity System)

**Static Methods:**

**`static has(addr)`**
- Happy path: addr exists in prototypes → true
- Happy path: addr does not exist → false
- Edge case: null/undefined addr
- Edge case: empty string addr

**`static get(addr)`**
- Happy path: get DynamicClass by model name (e.g., "Product")
- Happy path: get N3TX instance by entity ref (e.g., "Product/1")
- Happy path: addr not found → returns undefined
- Edge case: null/undefined addr → returns undefined
- Edge case: malformed address without slash
- Edge case: empty string

**`static attach(addr, callback)`**
- Happy path: attach when DynamicClass exists (fires immediately)
- Happy path: attach when schema in flight (queues callback)
- Happy path: attach to new model (queues, fetches schema)
- Edge case: null/undefined addr
- Edge case: null/undefined callback
- Edge case: attach same model multiple times (dedup)
- Edge case: pre-loaded schema consumed instead of network fetch
- Verify unsubscribe function returned
- Verify callback cleanup on multiple attaches

**`static ATTACH(data, tx)` — universal ATTACH router**
- Happy path: type-level ATTACH (model name only)
- Happy path: instance-level ATTACH (model/id)
- Edge case: schema not yet loaded (queued)
- Edge case: schema in flight

**`static SCHEMA(data, tx)` — bootstrap completion**
- Happy path: schema with properties, methods, access
- Happy path: schema with $defs (nested models)
- Happy path: replays queued TXs
- Edge case: schema with invalid $defs (skipped)
- Edge case: no __tablename__ (inferred from addr.toLowerCase() + 's')
- Edge case: pre-loaded data consumed instead of network fetch
- Edge case: DynamicClass created with all fields and methods
- Verify initial READ triggered with correct populate depth

**`static #replayWaiting(addr, DC)`**
- Happy path: replay attach callbacks
- Happy path: replay queued TXs
- Happy path: handle both _attachCallback and TX formats
- Edge case: no queue for addr
- Edge case: empty queue
- Verify queue cleared after replay

**`static UPDATE(data)` — handles batch entity updates**
- Happy path: update existing instances
- Happy path: create new instances if not found
- Edge case: malformed data

**Instance Methods:**

**`constructor(model, hash, data={}, meta={})`**
- Happy path: full constructor with all params
- Happy path: hash auto-generated if null
- Happy path: addr/href calculated correctly
- Edge case: null model
- Edge case: empty string model

**`ATTACH(data, event)`**
- Happy path: component attaches to entity
- Happy path: watches added
- Happy path: DESCRIBE TX sent
- Edge case: null data

**`value` (getter/setter)**
- Happy path: get value returns object
- Happy path: set value with object
- Edge case: set non-object value (should throw TypeError)
- Edge case: value includes $schema and $id on getter
- Verify signal fired on set

**`proto` (getter)**
- Happy path: returns proto
- Edge case: proto not defined (returns undefined)

**`schema` (getter)**
- Happy path: returns _schema from DynamicClass
- Edge case: no schema available

**`define(proto)`**
- Happy path: sets proto with schema
- Happy path: updates href if proto has href
- Edge case: proto is null
- Edge case: proto has no href

**`describe(proto, data)`**
- Happy path: sets proto and updates data
- Happy path: data defaults to current data if not provided
- Edge case: null proto (returns early)
- Edge case: non-object proto (returns early)

**`READ(data)`**
- Happy path: static method updates instance
- Edge case: null/undefined data

**`UPDATE(data, event)`**
- Happy path: updates value
- Happy path: calls remote UPDATE if source is not HTTP
- Edge case: data without $schema

**`update(data)`**
- Happy path: merges data with current value
- Happy path: detects error messages and logs warnings
- Edge case: null/undefined data

**`_read_(data)`**
- Happy path: updates with received data
- Edge case: null/undefined data

**`pull()`**
- Happy path: sends READ TX with populate depth
- Happy path: returns this for chaining
- Edge case: invalid href

**`toJSON()`**
- Happy path: returns serializable object
- Happy path: excludes non-serializable metadata

#### Helper Functions

**`prototype(addr, schema, href)` — DynamicClass factory**
- Happy path: creates class with properties and methods
- Happy path: creates properties with getters/setters
- Happy path: property type validation
- Happy path: read-only property enforcement
- Happy path: static signal/observe/call at class level
- Happy path: static ATTACH/READ/CREATE/UPDATE/DELETE handlers
- Happy path: instance _response_ handler calls pull()
- Edge case: schema with no properties
- Edge case: schema with no methods
- Edge case: class name normalization
- Verify instances tracked in DC.instances map
- Verify watchers notified on READ

**`normalizePopulated(entity, schema)` — populated data normalization**
- Happy path: converts {data: [...], meta} to href array
- Happy path: converts inline objects with $id to href strings
- Happy path: recursively registers child instances
- Edge case: no populated fields
- Edge case: malformed wrapper (missing data/meta)
- Edge case: null/undefined entity
- Edge case: null/undefined schema

**`registerInstance(DC, data)` — entity registration**
- Happy path: creates new instance
- Happy path: updates existing instance
- Edge case: data without id
- Verify DC.instances updated

**`resolveModelName(def)` — extracts model from schema def**
- Happy path: items.$ref
- Happy path: items.anyOf[...].$ref
- Edge case: no items
- Edge case: no $ref
- Edge case: null/undefined def

---

### Matrix.js (Message Bus)

**`constructor(addr, url="")`**
- Happy path: creates Matrix with addr
- Happy path: registers as ROOT_ACTOR if first instance
- Happy path: initializes NetworkAdapter
- Edge case: multiple Matrix instances (ROOT only set once)

**`has(addr)`**
- Happy path: check if child actor exists
- Happy path: parses compound address
- Edge case: null/undefined addr

**`inbox(event)`**
- Happy path: routes CONNECT event
- Happy path: throws error if target is self
- Happy path: forwards to local child actor
- Happy path: sends to NetworkAdapter if remote
- Edge case: null/undefined event
- Edge case: invalid TX format (auto-converted)

**`dispatch(event)`**
- Happy path: delegates to inbox
- Edge case: pre-dispatched TX

**`connect(source, target)`**
- Happy path: routes to local child actor
- Happy path: throws error if target class not registered
- Edge case: null source/target
- Edge case: malformed addresses

---

### Actor.js (Actor Model)

**Static Methods:**

**`static registerRoot(actor)`**
- Happy path: registers first actor as root
- Happy path: throws if already registered

**`static get root`**
- Happy path: returns registered root actor
- Edge case: no root registered (returns null)

**`static get addr`**
- Happy path: returns class name (default)

**`static _send(event)`**
- Happy path: routes to local child
- Happy path: routes to self if addr matches
- Happy path: bubbles to root Matrix if target unknown
- Edge case: no ROOT_ACTOR registered (throws)
- Edge case: null/undefined event
- Edge case: malformed target path

**`static _inbox(event)`**
- Happy path: calls method matching event.name
- Happy path: delegates to prototype method
- Happy path: throws if no handler found
- Edge case: null/undefined event

**`static _register(actor)`**
- Happy path: registers actor in children map
- Happy path: type check for instance match
- Edge case: null actor
- Edge case: actor of wrong type

**`static subclass(ChildClass, ...Mixins)`**
- Happy path: sets up static addr, children, send, inbox
- Happy path: applies mixins
- Happy path: idempotent (already augmented class)
- Happy path: registers with parent if ROOT exists
- Edge case: null/undefined ChildClass
- Edge case: ChildClass not a function
- Verify all properties added to prototype and static

**Instance Methods:**

**`constructor(addr="")`**
- Happy path: auto-generates addr if empty
- Happy path: registers in type-level children
- Happy path: binds inbox/send
- Edge case: null addr (generates)

**`get addr`**
- Happy path: returns private addr

**`get children`**
- Happy path: returns children map

**`inbox(event)`**
- Happy path: delegates to _inbox
- Edge case: null event

**`register(actor)`**
- Happy path: calls _register
- Edge case: null actor

**`static isActor(obj)`**
- Happy path: true for Actor instances
- Happy path: true for __TypeActor marked objects
- Happy path: false for non-actors

**`send(event)` (instance)**
- Throws: not implemented in base class

**`spawn(addr, ActorClass, ...args)`**
- Happy path: creates child actor
- Happy path: uses Actor as default class
- Edge case: duplicate addr (throws)
- Edge case: null addr
- Verify child registered in children map

---

### Router.js (Navigation State)

**`constructor(addr, {hash=false}={})`**
- Happy path: creates router with hash sync off
- Happy path: creates router with hash sync on
- Happy path: registers in global routers map
- Edge case: duplicate router names
- Verify hashchange listener attached if hash=true

**`current` (getter)**
- Happy path: returns current route (null or string/object)

**`canGoBack` (getter)**
- Happy path: true if stack has items
- Happy path: false if stack empty

**`NAVIGATE(data, tx)`**
- Happy path: pushes old route to stack
- Happy path: sets current to new data
- Happy path: updates hash if sync enabled
- Happy path: notifies observers
- Edge case: navigate to same route (returns early)
- Edge case: string route vs object route comparison

**`BACK(data, tx)`**
- Happy path: pops from stack
- Happy path: reverts to previous route
- Happy path: updates hash
- Happy path: notifies observers
- Edge case: back when no stack (returns early)
- Edge case: stack only one item (pops to null)

**`#toHash()` (private hash sync)**
- Happy path: sets location.hash for string routes
- Happy path: uses history.replaceState for null route
- Edge case: non-string route (skipped)

**`#fromHash()` (private hash read)**
- Happy path: reads hash on page load
- Happy path: pushes old route to stack
- Happy path: detects no-hash (clears route)
- Edge case: empty hash
- Edge case: hash same as current (no change)

**`getRouter(addr)` (module function)**
- Happy path: retrieves registered router
- Edge case: addr not found (returns undefined)

---

### Observable.js (Mixin)

**`static apply(Base)`**
- Happy path: augments class with signal, observe, notify
- Happy path: idempotent (already applied)
- Edge case: null/undefined Base (throws TypeError)
- Verify proto gets methods

**`signal(callback?, wait=false)` (instance)**
- Happy path: fires callback immediately if no callback provided
- Happy path: registers callback and returns unsubscribe
- Happy path: wait=true defers immediate callback
- Edge case: null/undefined callback (fires all listeners)
- Edge case: callback not a function (throws)
- Verify unsubscribe removes listener

**`observe(property, callback)` (instance)**
- Happy path: registers observer for property
- Happy path: returns unsubscribe function
- Edge case: null/undefined property
- Edge case: null/undefined callback
- Edge case: duplicate property observers
- Verify cleanup on unsubscribe

**`notify(property, newValue, oldValue)` (instance)**
- Happy path: calls all observers for property
- Happy path: passes newValue, oldValue, property, this
- Edge case: null/undefined property
- Edge case: property with no observers (no-op)
- Edge case: empty property

---

### TX.js (Transaction/Event)

**`constructor(event)`**
- Happy path: object with all fields
- Happy path: JSON string parsed
- Happy path: defaults: timestamp, data={}, meta={}
- Edge case: string that's not valid JSON (throws)
- Edge case: null/undefined event

**`hash` (getter, lazy)**
- Happy path: computes on first access
- Happy path: caches result
- Edge case: empty repr

**`repr()`**
- Happy path: returns object with all TX fields
- Happy path: includes computed hash

**`str()`**
- Happy path: JSON stringifies repr

**`static fromString(str)`**
- Happy path: parses JSON string to TX
- Edge case: invalid JSON (throws)

---

### Utils.js

**`deepEqual(obj1, obj2)`**
- Happy path: identical primitives → true
- Happy path: identical objects → true
- Happy path: different primitives → false
- Happy path: different object structures → false
- Happy path: deeply nested objects
- Edge case: null/undefined → false
- Edge case: arrays of different lengths
- Edge case: circular references (may stack overflow)

**`generateId()`**
- Happy path: generates unique string
- Happy path: each call different
- Verify format (random + timestamp)

**`createOperation(type, transformation, metadata={}, version=1)`**
- Happy path: creates operation record with all fields
- Happy path: defaults version=1
- Happy path: generates unique id
- Edge case: null type
- Edge case: null transformation

**`notifySubscribers(instance, oldData, newData)`**
- Happy path: calls all subscribers
- Happy path: calls property observers with delta
- Happy path: error handling on subscriber exceptions
- Edge case: no subscribers
- Edge case: no property observers

**`simpleHash(data)`**
- Happy path: hashes object consistently
- Happy path: same object same hash
- Happy path: different objects different hashes
- Edge case: empty object
- Edge case: nested object
- Edge case: null/undefined

**`isTypeCompatible(value, expectedType)`**
- Happy path: string type
- Happy path: number type
- Happy path: integer type (includes float checks)
- Happy path: boolean type
- Happy path: object type (excludes arrays)
- Happy path: array type
- Edge case: unknown expectedType (returns true)
- Edge case: null value
- Edge case: 0 as number
- Edge case: '' as string
- Edge case: false as boolean

**`isUrl(str)`**
- Happy path: valid HTTP URL → true
- Happy path: valid HTTPS URL → true
- Happy path: invalid URL string → false
- Edge case: null/undefined (throws TypeError)
- Edge case: relative path (throws)

**`isEmpty(obj)`**
- Happy path: empty object → true
- Happy path: non-empty object → false
- Happy path: empty array → true
- Happy path: non-empty array → false
- Edge case: null/undefined (returns !!obj)
- Edge case: non-object primitive (falsy check)

---

### Component.js (Base Web Component)

**`static normalizeDisplay(value)`**
- Happy path: 'xs', 'sm', 'md', 'lg', 'xl'
- Happy path: aliases 'pill' → 'xs', 'card' → 'md'
- Edge case: 'auto' or null (returns null)
- Edge case: unknown value (returns null)

**`constructor(defaultValue={})`**
- Happy path: creates shadow DOM
- Happy path: initializes actor identity
- Happy path: inits entity state
- Happy path: binds callbacks
- Happy path: loads stylesheet if defined
- Edge case: defaultValue type enforcement

**`get addr` / `set addr`**
- Happy path: getter returns addr
- Happy path: setter on first set
- Happy path: setter rejects change after set (throws)
- Edge case: null addr

**`static observedAttributes`**
- Happy path: returns ['model', 'addr', 'hash', 'ref', 'display']

**`attributeChangedCallback(name, oldVal, newVal)`**
- Happy path: skips if values identical
- Happy path: handles 'display' → displayModeChanged
- Happy path: handles 'model' → ATTACH TX
- Happy path: handles 'ref' → setter
- Edge case: oldVal === newVal (returns early)

**`model` (getter/setter)**
- Happy path: get/set model name
- Edge case: null model

**`proto` (getter)**
- Happy path: returns proto
- Edge case: proto not set (empty object)

**`schema` (getter/setter)**
- Happy path: infers from proto if available
- Happy path: setter overrides

**`define(ptt)`**
- Happy path: called with DynamicClass
- Happy path: sets proto, infers model
- Happy path: calls definedCallback
- Edge case: same schema called twice (skips)
- Edge case: null ptt

**`definedCallback()`**
- Happy path: hook called after define
- Verify subclasses can override

**`ref` (getter/setter)**
- Happy path: get/set href
- Happy path: URL ref with model → ATTACH
- Happy path: direct URL ref → READ
- Happy path: N3TX address → ATTACH
- Edge case: null ref

**`value` (getter/setter)**
- Happy path: get returns current data
- Happy path: set updates data
- Happy path: type mismatch logs warning (no-op)
- Edge case: identity check (no update if same)

**`displayBreakpoints` (getter)**
- Happy path: returns breakpoint map {xl: 800, ...}
- Verify override in subclasses

**`displayMode` (getter)**
- Happy path: returns current size
- Edge case: before connectedCallback

**`display` (getter/setter)**
- Happy path: getter returns attr or 'auto'
- Happy path: setter with size name
- Happy path: setter with 'auto' removes attribute

**`displayModeChanged(oldMode, newMode)`**
- Happy path: re-renders if schema available
- Verify subclasses can override

**`#startResizeObserver()`**
- Happy path: creates ResizeObserver
- Happy path: calculates displayMode from width
- Happy path: calls displayModeChanged
- Happy path: skips if display attribute forced
- Edge case: width === 0 (layout not complete yet)
- Verify breakpoint sorting (largest first)

**`#stopResizeObserver()`**
- Happy path: disconnects observer
- Happy path: nulls observer

**`subscribe(tt, attribute, callback)`**
- Happy path: cleans previous subscription
- Happy path: calls tt.observe
- Happy path: returns unsubscribe function
- Edge case: multiple subscriptions

**`attach(addr)`**
- Happy path: cleans previous attach
- Happy path: calls N3TX.attach
- Verify lazy import of N3TX

**`connectedCallback()`**
- Happy path: applies forced display mode
- Happy path: starts ResizeObserver

**`disconnectedCallback()`**
- Happy path: calls super
- Happy path: cleans subscriptions
- Happy path: cleans attachments

**`render()`**
- Throws: must be overridden in subclass

**`styles` (getter)**
- Happy path: returns null (override in subclass)

---

## COMPONENTS LAYER

### NTTElement.js (Single Entity Base)

**`value` (getter/setter)**
- Happy path: setter triggers update then render
- Happy path: surgical update optimization
- Edge case: render skipped if no schema
- Verify signal called

**`update(prev, next)`**
- Happy path: default returns false (full render)
- Verify override in subclasses

**`UPDATE(data)`**
- Happy path: receives entity data with $schema
- Happy path: updates value
- Happy path: sends CONNECT if schema changed
- Edge case: missing $schema

**`DESCRIBE(data)`**
- Happy path: receives proto + data
- Happy path: sets schema from proto
- Happy path: subscribes to entity signal
- Happy path: entity signal updates value
- Edge case: null proto (skips)

**`READ(data)`**
- Happy path: receives direct URL fetch
- Happy path: infers schema from model attr
- Edge case: no model attr

**`save()`**
- Happy path: sends UPDATE TX to ref
- Happy path: uses current value

**`disconnectedCallback()`**
- Happy path: cleans entity subscription

---

### ListElement.js (Collection Base)

**`SIZE_CASCADE`**
- Verify: xl→md, lg→sm, md→sm, sm→xs, xs→xs

**`constructor()`**
- Happy path: default value is []

**`selected` (getter)**
- Happy path: returns Set of selected addresses

**`select(addr)` / `deselect(addr)` / `toggle(addr)`**
- Happy path: add/remove/toggle address in selected set

**`clearSelection()`**
- Happy path: clears all selections

**`definedCallback()`**
- Happy path: subscribes to proto UPDATE
- Happy path: triggers initial READ with limit/offset
- Happy path: passes populate depth in params

**`loadMore()`**
- Happy path: increments offset
- Happy path: calls proto.READ again
- Happy path: appends results

**`UPDATE(data, tx)`**
- Happy path: receives array of addresses
- Happy path: updates value and renders
- Happy path: surgical update optimization
- Edge case: non-array data (logs warning)

**`SELECT(data, tx)`**
- Happy path: toggles selection
- Happy path: sends NAVIGATE to router if configured

**`append(data)`**
- Happy path: appends array to value
- Edge case: non-array data (logs warning)

**`childTag` (getter)**
- Happy path: item-tag attribute
- Happy path: schema.ui.renderer.item
- Happy path: defaults to 'ntx-item'

**`childDisplay` (getter)**
- Happy path: item-display attribute
- Happy path: SIZE_CASCADE from displayMode
- Edge case: explicit normalized

**`createChild(addr)`**
- Happy path: uses template if present
- Happy path: creates element with childTag
- Happy path: sets ref and attributes
- Verify select-target attribute set

**`update(prev, next)`**
- Happy path: surgical DOM patching (deletions + additions)
- Happy path: updates count element
- Happy path: returns false if no grid found (full render)
- Edge case: non-array prev/next
- Verify attribute-based element queries

**`render()`**
- Happy path: renders list header, grid, load-more button
- Happy path: stamps child elements with stagger animation
- Edge case: no schema or non-array value (no-op)

---

### ntx-item.js (Single Entity Default)

**`styles` (getter)**
- Happy path: returns CSS URL

**`mode`**
- Happy path: initialized to 'display'

**`connectedCallback()`**
- Happy path: shows skeleton if no schema yet
- Verify placeholder matches size

**`placeholder(size)`**
- Happy path: xs skeleton (pill shape)
- Happy path: sm skeleton (avatar + name)
- Happy path: md/lg/xl skeleton (text lines)

**`deleteItem()`**
- Happy path: permission check
- Happy path: asks confirmation
- Happy path: sends DELETE TX via DynamicClass
- Happy path: optimistic parent update
- Edge case: no permission (early return)
- Edge case: user cancels (no delete)

**`toggleMode()`**
- Happy path: permission check
- Happy path: saves if in edit mode
- Happy path: toggles mode and renders
- Edge case: no permission (early return)

**`handleInputChange(e)`**
- Happy path: handles text input
- Happy path: handles checkbox input
- Happy path: handles number input
- Happy path: updates nested array elements
- Edge case: creates array if missing

**`xs()` (size method)**
- Happy path: returns pill HTML with name
- Edge case: no name, no title (uses schema name)

**`sm()` (size method)**
- Happy path: renders compact row
- Happy path: shows action buttons
- Happy path: respects field_order
- Happy path: handles $ref fields (avatars)
- Happy path: renders name field
- Happy path: renders up to 3 inline fields
- Happy path: renders method buttons
- Happy path: reply button if method exists
- Edge case: no permission for edit/delete (no buttons)
- Edge case: image fallback
- Edge case: $ref as leading avatar
- Edge case: multiple fallbacks

**`md()` (size method — card)**
- Happy path: renders card with image
- Happy path: renders edit/delete buttons
- Happy path: renders form via Formidable
- Happy path: separates attached/standalone methods
- Edge case: no image
- Edge case: no permission for actions

**`lg()` / `xl()` (size methods)**
- Happy path: delegate to md()

**`update(prev, next)` — surgical**
- Happy path: patches individual field values
- Happy path: handles array field reconciliation
- Happy path: skips fields that didn't change
- Happy path: skips if not rendered yet
- Edge case: element not found for field
- Edge case: active input (don't overwrite during typing)

**`#updateListField(root, key, prevArr, nextArr)`**
- Happy path: removes deleted refs
- Happy path: adds new refs
- Happy path: handles populated wrappers
- Happy path: promotes collapsed items to visible
- Happy path: updates count badge
- Happy path: manages show-more button
- Edge case: container not found (returns false)
- Verify VISIBLE_COUNT=2

**`render()`**
- Happy path: dispatches to size method
- Happy path: wraps in card div
- Happy path: applies reply-indent class if selfref
- Happy path: binds events
- Edge case: no schema/value (no-op)

**`#bindEvents()`**
- Happy path: edit button → toggleMode
- Happy path: delete button → deleteItem
- Happy path: input changes → handleInputChange
- Happy path: show-more button → toggle collapsed
- Happy path: reply button → shows reply input box
- Happy path: reply submit → calls method
- Happy path: card click → SELECT TX
- Edge case: skips interactive elements on click

**`#smFields()` — field resolution**
- Happy path: respects field_order
- Happy path: skips id, hidden, array, selfref
- Happy path: permission checks
- Verify ordering

**`#resolveChildTag(refModel)`**
- Happy path: checks $defs first
- Happy path: falls back to N3TX registry
- Happy path: defaults to 'ntx-item'

**`#standaloneMethodsHtml(methods)`**
- Happy path: generates ntx-method elements
- Happy path: renders non-attached methods

---

### ntx-list.js (Collection Default)

**`styles` (getter)**
- Happy path: returns CSS URL
- Inherits all ListElement behavior

---

### ntx-router.js (Generic View Container)

**`styles` (getter)**
- Happy path: returns CSS URL

**`constructor()`**
- Happy path: default value {}

**`connectedCallback()`**
- Happy path: creates or gets Router actor
- Happy path: observes route changes
- Happy path: auto-configures child [model] elements
- Happy path: renders initial view

**`disconnectedCallback()`**
- Happy path: cleans router subscription

**`render()`**
- Happy path: mounts view if route exists
- Happy path: shows slot if no route

**`#showSlot()`**
- Happy path: removes current view
- Happy path: shows slot content

**`#mountView(routeData)`**
- Happy path: string @app routes (@profile -> ntx-profile)
- Happy path: string entity refs (Product/1)
- Happy path: object routes {tag, attrs, title}
- Happy path: back button if canGoBack
- Happy path: chrome rendered
- Edge case: unrecognized route (shows slot)

**`#resolveTag(model)`**
- Happy path: checks N3TX schema for renderer.detail
- Happy path: falls back to renderer.item
- Happy path: defaults to 'ntx-item'

---

### ntx-method.js (Method Call Component)

**`static get observedAttributes`**
- Happy path: returns attribute list

**`constructor()`**
- Happy path: creates shadow DOM
- Happy path: initializes state

**`connectedCallback()`**
- Happy path: calls load()

**`attributeChangedCallback()`**
- Happy path: calls load()

**`load()`**
- Happy path: reads all attributes
- Happy path: resolves model and method schemas
- Happy path: renders
- Edge case: model not found (logs error)
- Edge case: method not found (logs error)

**`handleInput(e)`**
- Happy path: updates value from input
- Happy path: handles nested params
- Happy path: auto-calls if mode='auto'

**`callMethod()`**
- Happy path: instance method via N3TX.call()
- Happy path: class method via proto.call()
- Happy path: routes to _response_ handler
- Edge case: no N3TX or proto (no-op)

**`#postCall()`**
- Happy path: clears inputs and response for inline layout
- Happy path: re-renders for other layouts

**`render()`**
- Happy path: dispatches to layout method

**`renderButton()`**
- Happy path: renders icon + count
- Happy path: handles count_field (array or wrapper)
- Happy path: uses ICONS or defaults

**`renderFieldset()`**
- Happy path: renders form with legend
- Happy path: handles selfref parameters
- Happy path: handles $ref parameters (nested fields)
- Happy path: renders output if response exists
- Happy path: renders submit button if manual mode

**`renderInline()`**
- Happy path: compact textarea/input + button
- Happy path: handles single required field
- Happy path: stacks multiple fields
- Happy path: detects widget='textarea'
- Happy path: single-line input/button row
- Edge case: multiple params
- Edge case: $ref with multiple required fields

**`#bindInputs()`**
- Happy path: binds input listeners
- Happy path: form onsubmit -> callMethod
- Edge case: no form

---

### ntx-topbar.js (Navigation Bar)

**`connectedCallback()`**
- Happy path: renders brand + nav
- Happy path: checks auth state
- Happy path: renders user pill or sign-in link

**`render()`**
- Happy path: full topbar with brand, nav, auth state

**Theme toggle**
- Happy path: dispatches 'theme-change' event
- Happy path: toggles dark/light

**User dropdown**
- Happy path: shows profile, theme toggle, logout
- Happy path: logout clears token

**Favorites link**
- Happy path: shows when authenticated
- Happy path: navigates to #@favorites

---

### ntx-logs.js (Logging Panel)

**`connectedCallback()`**
- Happy path: subscribes to Logging.addListener
- Happy path: renders initial log entries

**`render()`**
- Happy path: renders log entries list
- Happy path: level colors

**Filter by level**
- Happy path: filters entries by selected level
- Happy path: toggle filter off shows all

**Clear logs**
- Happy path: clears all entries
- Happy path: notifies listeners

**Expand/collapse entries**
- Happy path: JSON tree rendering
- Happy path: collapse long strings

---

## GENERATORS LAYER

### form.js (Formidable — Schema-Driven Form Generator)

**`getForm(ntt, mode="display", attachedMethods={})`**
- Happy path: renders form with header and fields
- Happy path: groups fields if schema.ui.groups defined
- Happy path: filters protected fields in edit mode
- Happy path: injects attached methods
- Happy path: respects field_order
- Edge case: no fields to render
- Edge case: missing schema
- Verify permissions applied

**`getHeader(ntt, mode)`**
- Happy path: display mode renders h2 + h4
- Happy path: edit mode renders input + textarea
- Edge case: no name, no description

**`getInput(ntt, key, mode)`**
- Happy path: renders different input types per schema type
- Happy path: handles $ref fields
- Happy path: handles arrays
- Happy path: respects widget hints (currency, textarea)
- Happy path: displays read-only in display mode
- Happy path: enforces validation on input
- Edge case: unknown type (defaults to text)

**`getListInput(ntt, key, mode)`**
- Happy path: shows first 2 items visible
- Happy path: rest collapsed under .nested-collapsed
- Happy path: counts refs from URLs or populated objects' $id
- Happy path: shows "Show N more" button
- Happy path: renders child items as `<ntx-item ref="..." display="sm">`

**`renderGroupedFields(ntt, renderableFields, groups, mode, attachedMethods)`**
- Happy path: renders fieldsets per group
- Happy path: injects attached methods
- Happy path: renders ungrouped fields at end

**`renderAttachedMethod(ntt, methodName, methodDef)`**
- Happy path: generates ntx-method HTML
- Happy path: passes all attributes

**`refInput(ref)`**
- Happy path: resolves ref and renders form
- Edge case: ref not found (returns error input)

**`formatDisplayValue(fieldDef, key, value)`**
- Happy path: formats currency as $X.XX
- Happy path: formats textarea as div
- Happy path: formats $ref as [Reference: name/id]
- Happy path: formats selfref as [Parent: #id] or (top-level)
- Edge case: null/undefined value

**`validationAttrs(def, isRequired)`**
- Happy path: builds required, minlength, maxlength, min, max, pattern
- Edge case: no constraints → empty string

---

## UTILS LAYER

### Permissions.js

**`constructor()`**
- Happy path: initializes empty user state

**`user` (getter)**
- Happy path: returns current user or null

**`authenticated` (getter)**
- Happy path: true if user exists → true
- Happy path: false if null → false

**`role` (getter)**
- Happy path: returns user role or 'anonymous'

**`init()`**
- Happy path: fetches /auth/me via JWT
- Happy path: caches result (deduplicates)
- Happy path: returns promise
- Edge case: no token in localStorage
- Edge case: fetch fails (returns null)

**`#fetchUser()`**
- Happy path: parses JWT from localStorage
- Happy path: sends to /auth/me
- Happy path: sets user on success
- Happy path: null on 401 or network error
- Happy path: sets ready flag

**`canView(fieldDef)`**
- Happy path: undefined → visible
- Happy path: 'anyone' → visible
- Happy path: 'authenticated' → checks user
- Happy path: 'owner' → checks ownership
- Happy path: role name → checks user.role

**`canEdit(fieldDef)`**
- Happy path: same semantics as canView but checks fieldDef.access.edit

**`canAction(accessDict, action, resource)`**
- Happy path: evaluates serialized rules
- Happy path: supports or/and/not composites
- Happy path: resource-aware OWNER checks
- Happy path: role-based rules
- Edge case: no accessDict (returns true)
- Edge case: no rule for action (returns true)

**`#evaluateRule(rule)` (private)**
- Happy path: 'anyone' → true
- Happy path: 'authenticated' → checks user
- Happy path: 'owner' → checks authenticated
- Happy path: role name → checks match

**`#evaluateCompositeRule(rule, resource)` (private)**
- Happy path: simple { rule: 'X' }
- Happy path: or/and/not compositions
- Happy path: recursive evaluation

**`#evaluateOwner(rule, resource)` (private)**
- Happy path: compares resource[owner_field] to user_id
- Happy path: handles href hydration (extracts ID from URL)
- Edge case: no resource (returns true if authenticated)
- Edge case: resource.user_owner is null

---

### Logging.js

**`static get size`** — returns entry count
**`static getEntries(filter)`** — returns all or filtered entries
**`static clear()`** — clears entries, notifies listeners
**`static addListener(fn)` / `removeListener(fn)`** — manage listener callbacks
**`static #push(level, message, detail)`** — creates entry, enforces MAX_ENTRIES (500), notifies listeners
**`static init/log/dev/event/debug/warn/error()`** — level-specific logging with config gating

---

### Assert.js

**`default assert(caller, condition, message, trigger='error')`**
- Happy path: throws AssertionError on false condition
- Happy path: formats message with caller name
- Happy path: trigger='warn' logs warning
- Happy path: trigger='info' logs debug
- Edge case: null caller (no name prefix)

**`caution(caller, condition, message)`**
- Happy path: calls assert with 'warn' if LOGGING >= 2

**`inform(caller, condition, message)`**
- Happy path: calls assert with 'info' if LOGGING >= 4

---

### DateFormat.js

**`Date.prototype.toStringDM`** — formats DD-MM
**`Date.prototype.toStringDMY`** — formats DD-MM-YYYY
**`getCurrentTime()`** — returns HH:MM, pads zeros, handles midnight and 23:59

---

### config.js

- LOGGING level (1-4)
- LOGEVENTS toggle
- DEBUG toggle
- API_URL, WS_URL
- E (event constants — all names defined)
- TIMEOUT, RETRY_LIMIT

---

## TRANSPORT LAYER

### NetworkAdapter.js

**`constructor(matrix, url="", mode='http')`**
- Happy path: HTTP mode (default)
- Happy path: WS mode (lazy-loads Socket)
- Happy path: uses config.API_URL if no url provided

**`httpCallback(event, response)`**
- Happy path: swaps source/target
- Happy path: updates event.name from meta.inbox
- Happy path: dispatches via matrix
- Edge case: event without target
- Edge case: unknown source

**`onError(event, response)`**
- Happy path: logs error
- Happy path: sends ERROR callback with swapped source/target

**`emit(event)`**
- Happy path: invokes callback
- Edge case: event without target

**`pull(target, callback=null)`**
- Happy path: sends event with remote meta
- Edge case: null target

**`send(event)`**
- Happy path: HTTP READ → HTTP.get with params
- Happy path: HTTP SCHEMA → HTTP.get
- Happy path: HTTP CREATE → HTTP.post
- Happy path: HTTP UPDATE → HTTP.put
- Happy path: HTTP DELETE → HTTP.remove
- Happy path: HTTP custom methods → HTTP.post to /{target}/{method}
- Happy path: WS mode → Socket.sendEvent
- Edge case: unknown event name (falls back to POST)

---

### HTTP.js

**`static get(url, onSuccess, onError)`**
- Happy path: sends GET with auth token, parses JSON, calls onSuccess
- Edge case: 401 → redirects to /login.html
- Edge case: 404 → onError
- Edge case: network error → onError

**`static post(url, data, onSuccess, onError)`**
- Happy path: stringifies data, sends POST, calls onSuccess
- Edge case: bad request → onError, 401 → redirects

**`static put(url, data, onSuccess, onError)`**
- Happy path: same as post but PUT method

**`static remove(url, onSuccess, onError)`**
- Happy path: sends DELETE with auth token

**`static checkIfUnauthorized(res)`**
- Happy path: 401 → clears token, returns true
- Happy path: other status → returns false

**`static checkValidCode(res)`**
- Happy path: 200, 201, 203, 2xx → true
- Happy path: other → false

**`static checkRessource(res)`**
- Happy path: 404, 301, 308, 400, 500 → false (with logging)
- Happy path: other → true

**`static rpc(method_name, args={}, kwargs={}, onSuccess=()=>{})`**
- Happy path: sends RPC POST
- Edge case: error → alerts "FAIL"

---

### Socket.js

**States:** DISCONNECTED, CONNECTED, CONNECTING, FAILED, PENDING, WAITING, RECONNECT

**`constructor(url, targets={}, ttl=1000)`** — initializes state, binds callbacks, connects
**`heartbeat(msg=true)`** — updates lrh, sends heartbeat message
**`watchdog()`** — state machine: CONNECTING→WAITING, FAILED→reconnect, CONNECTED+expired→heartbeat
**`disable()` / `enable()`** — calls target callbacks, updates isDisabled flag
**`connect(url, callback)`** — creates WebSocket, sets CONNECTING, binds events
**`reconnect()`** — increments retries, closes old, creates new, stops at MAX_TRIES
**`disconnect()`** — closes WebSocket, clears interval, sets DISCONNECTED
**`setTarget(target, callback)` / `removeTarget(id)`** — manages target callbacks
**`dispatchEvent(event)`** — calls target callback; Edge case: target not found
**`onMessage(msg)`** — parses JSON, sets CONNECTED, dispatches, sends queued, updates lrh
**`sendMessage(key, msg, plain=false)`** — queues if not connected, sends JSON or plaintext
**`sendEvent(event)`** — converts to string and sends
**`onOpen(event)`** — sets CONNECTING, clears interval, sets watchdog, sends allStatesRequest
**`onClose(event)`** — sets DISCONNECTED, calls disable(), logs code

---

## CROSS-CUTTING CONCERNS

### Error Handling
- Network failures (404, 401, 500)
- Timeout / connection refused
- Invalid JSON responses
- Missing $defs, invalid property definitions

### State Management
- Entity lifecycle: CREATE → instance added, UPDATE → merged + signaled, DELETE → removed
- Collection pagination: limit/offset, has_more, loadMore() appends
- Surgical DOM updates: field patches, array reconciliation

### Boundary Tests
- Large collections (1000s of items)
- Deep nesting (multi-level $ref hydration)
- Concurrent operations (multiple ATTACH calls racing, overlapping UPDATE/DELETE)
