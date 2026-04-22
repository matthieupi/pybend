# Proposition 3: Mesh — The Wiring IS the Program

**Motto:** *The wiring IS the program.*
**Core metaphor:** Circuit board
**The program is:** The wiring graph
**Primary operator:** `flow()` / `wire()` (connect)

---

## The Core Insight

Look at how `ActorModel.handler()` works today -- 90 lines of imperative
dispatch in `actor_model.py`:

```python
async def handler(target, tx):
    # Try CRUD...
    result = cls.handler_crud(tx)
    if result is not _NOT_HANDLED:
        # dispatch CRUD result...
    else:
        # Get method...
        method = getattr(target, tx.name, None)
        if method:
            # Check if @expose_route...
            if is_exposed:
                # Tier 2 auth...
                # Unpack kwargs...
                # Resolve self for instance methods...
            else:
                # Original (data, tx) signature...
            # Check if streaming...
            if inspect.isasyncgen(result):
                # Stream loop...
            # Parse JSON strings...
            # Wrap in reply TX...
        else:
            # Error: unhandled...
```

This is a **router written as code**. It routes by message name to CRUD ops,
to exposed methods, to generic handlers. It handles auth, kwargs unpacking,
streaming detection, JSON parsing -- all woven into one giant method.

Now look at Matrix: it routes by **address**. ActorModel.handler routes by
**message name**. Interceptors route by **method target**. Three routing
mechanisms, three implicit topologies, none of them visible or composable.

**What if all routing was explicit topology -- a visible graph of nodes and
wires?**

Prop 1 said: compose actors linearly with `>>`.
Prop 2 said: the message carries its route.
Prop 3 says: **the connections between components ARE the program**. You don't
write handlers -- you place components on a graph and wire them together. The
graph is visible, inspectable, and modifiable at runtime.

```
Prop 1: The CHAIN is the program     A >> B >> C
Prop 2: The MESSAGE is the program   tx.through(A >> B >> C)
Prop 3: The GRAPH is the program     wire(A->B, A->C, B->D, C->D)
```

## Why a Graph, Not a Chain

Linear pipelines (`>>`) can't express:

**Fan-out:**
```
                    +-> Persist --+
Validate -> Authorize-+            +-> Respond
                    +-> Notify ---+
                    +-> AuditLog (fire & forget)
```

**Conditional branching:**
```
                       +-> FastTrack --> Respond
Classify -> -----------+
                       +-> Review -> Approve --> Persist --> Respond
```

**Feedback loops:**
```
Parse -> Validate --> Persist
            ^           |
            +-- Retry --+ (on transient failure)
```

**Shared components:**
```
create --> +                   +---> Persist --> Notify
           +--> Auth --> Rate --+
update --> +                   +---> Merge --> Persist --> Notify
read ----> Auth --> Rate --> Fetch --> Format
```

A mesh expresses ALL of these naturally. Chains are a special case of graphs
(a graph with one path).

## How It Works

```python
# -- Define components (reusable, standalone) -----------------------

class Validate(Node):
    """dict -> dict. Validates against schema, passes through or errors."""
    async def process(self, tx: TX) -> TX:
        errors = self.schema.validate(tx.data)
        if errors:
            return tx.error(f"Invalid: {errors}", 422)
        return tx

class Authorize(Node):
    """Gate node -- passes or blocks. Configurable policy."""
    def __init__(self, policy):
        self.policy = policy
    async def process(self, tx: TX) -> TX:
        if not self.policy.allows(tx.meta.get('user'), tx.name):
            return tx.error("Forbidden", 403)
        return tx

class Persist(Node):
    """dict -> dict. Writes to storage, returns entity with id."""
    async def process(self, tx: TX) -> TX:
        entity = await self.storage.create(tx.data)
        return tx.evolve(data=entity)

class Notify(Node):
    """Passthrough side-effect. Sends notification, passes TX unchanged."""
    async def process(self, tx: TX) -> TX:
        await self.bus.emit('entity.created', tx.data)
        return tx
```

```python
# -- Wire the mesh -- THIS IS THE APPLICATION ----------------------

products = Mesh('products')

# Place nodes (components exist independent of wiring)
products.node('validate',  Validate(schema=ProductSchema))
products.node('auth',      Authorize(policy=product_access))
products.node('persist',   Persist(storage=sqlite))
products.node('notify',    Notify(bus=event_bus))
products.node('format',    FormatResponse())

# Wire flows -- declare which nodes connect for each operation
products.flow('create', ['validate', 'auth', 'persist', 'notify', 'format'])
products.flow('read',   ['auth', 'persist:fetch', 'format'])
products.flow('update', ['validate', 'auth', 'persist:merge', 'notify', 'format'])
products.flow('delete', ['auth', 'persist:remove', 'notify', 'format'])

# Mount in the actor tree -- the Mesh IS an actor
matrix.register(products)
```

When a TX arrives at the mesh, the mesh looks up the flow by `tx.name`, then
routes the TX through the wired sequence of nodes. Each node is a functor.
The mesh is the router. The wiring is the program.

## The Three Systems Side by Side

**Same task: "Full CRUD for products"**

### Pyrofunc Alone

```python
validate = functor(validate_fn)
persist = functor(persist_fn)
pipeline = validate >> persist
result = Monad(data) | pipeline
# One pipeline. Can't reuse validate in a different context.
# No routing, no shared state, no graph.
```

### Actor Alone

```python
class Product(ActorModel):
    async def handler(target, tx):
        if tx.name == 'CREATE': ...
        elif tx.name == 'READ': ...
        elif tx.name == 'UPDATE': ...
        elif tx.name == 'DELETE': ...
# All operations in one monolithic handler.
# Validation is copy-pasted into each branch.
# Can't see the overall structure.
```

### Mesh

```python
products = Mesh('products')
products.node('auth',     Authorize(product_access))
products.node('validate', Validate(ProductSchema))
products.node('persist',  Persist(sqlite))
products.node('notify',   Notify(event_bus))
products.node('format',   FormatResponse())

products.flow('create', ['validate', 'auth', 'persist', 'notify', 'format'])
products.flow('read',   ['auth', 'persist:fetch', 'format'])
products.flow('update', ['validate', 'auth', 'persist:merge', 'notify', 'format'])
products.flow('delete', ['auth', 'persist:remove', 'notify', 'format'])

# You can SEE the entire application structure in these 10 lines.
# Change 'auth' policy -> affects ALL flows.
# Add a flow -> one line.
# Swap persist backend -> one node replacement.
```

## What Only the Mesh Has

### 1. The Application Is Visible

Today, to understand how N3TX processes a CREATE request, you trace through:
`routes_fastapi.py` -> `network_api.py` -> `auth_interceptor` -> `Matrix.inbox`
-> `ActorModel.handler` -> `handler_crud` -> `StorableMixin.create`. Six files,
hundreds of lines.

With a Mesh:

```python
products.describe()
# products/
#   create:  validate -> auth -> persist -> notify -> format
#   read:    auth -> persist:fetch -> format
#   update:  validate -> auth -> persist:merge -> notify -> format
#   delete:  auth -> persist:remove -> notify -> format
#
#   nodes:
#     validate  Validate(ProductSchema)     dict -> dict
#     auth      Authorize(product_access)   TX -> TX (gate)
#     persist   Persist(sqlite)             dict -> dict+id
#     notify    Notify(event_bus)           passthrough
#     format    FormatResponse()            dict -> response

products.diagram()  # generates visual graph (mermaid, graphviz, ASCII)
```

The CLAUDE.md philosophy says *"trace any behavior from HTML tag to network
request in under a minute."* With Mesh, the trace IS the topology. One glance.

### 2. Shared Components, Single Point of Change

In Prop 1 (pipelines), each pipeline owns its stages:

```python
create = Validate >> Auth >> Persist >> Notify     # Auth instance #1
read   = Auth >> Fetch >> Format                    # Auth instance #2
update = Validate >> Auth >> Merge >> Persist        # Auth instance #3
# Change auth policy -> must update 3 places (or share a variable, but the
# pipeline still holds a snapshot, not a live reference)
```

In Mesh, nodes are shared:

```python
products.node('auth', Authorize(product_access))    # ONE instance
products.flow('create', ['validate', 'auth', ...])  # references same node
products.flow('read',   ['auth', ...])               # references same node
products.flow('update', ['validate', 'auth', ...])  # references same node

# Change auth policy -> change ONE node -> affects ALL flows
products.replace('auth', Authorize(new_policy))
```

This is the difference between copying a function into every caller (Prop 1)
and calling a shared function (Prop 3). The mesh holds **live references**,
not snapshots.

### 3. Non-Linear Flow Patterns

**Fan-out (parallel execution):**

```python
products.flow('create', [
    'validate',
    'auth',
    'persist',
    {'parallel': ['notify', 'index', 'audit']},  # all three run concurrently
    'format',
])
```

**Conditional branching:**

```python
products.flow('process', [
    'classify',
    {'branch': {
        'simple':   ['persist', 'format'],
        'complex':  ['review', 'approve', 'persist', 'format'],
        'bulk':     ['batch', 'persist:bulk', 'format'],
    }},
])
```

**Error routing (not just short-circuit):**

```python
products.flow('create', ['validate', 'auth', 'persist', 'notify', 'format'])
products.on_error('create', ['log_error', 'alert_ops', 'format_error'])
# Errors don't just short-circuit -- they route to an explicit error flow
```

**Feedback / retry:**

```python
products.flow('sync', [
    'fetch_remote',
    'merge_local',
    {'retry': 'merge_local', 'on': 'conflict', 'max': 3},
    'persist',
])
```

None of these are expressible with linear `>>` composition alone.

### 4. Runtime Rewiring

The mesh is a living graph that can be modified while running:

```python
# Add a new flow at runtime (e.g., new API capability deployed)
products.flow('export', ['auth', 'persist:fetch_all', 'to_csv', 'stream'])

# Insert a stage into an existing flow (e.g., A/B test)
products.insert('create', after='validate', node='ab_test_pricing')

# Remove a stage (e.g., disable notifications during maintenance)
products.detach('create', node='notify')

# Replace a component (e.g., swap storage backend)
products.replace('persist', Persist(new_postgres_backend))
# Type-checks all affected flows: does new backend satisfy all uses?

# Merge two meshes (e.g., plugin system)
products.mount(premium_features_mesh, namespace='premium')
```

### 5. Graph-Level Intelligence

Because the mesh sees the full topology, it can reason about it:

```python
# Dependency analysis
products.depends_on('notify')    # ['create', 'update', 'delete'] -- which flows use it
products.critical_path('create') # ['validate', 'persist'] -- slowest chain

# Impact analysis (before making a change)
products.impact('persist')
# "persist" is used in 4 flows (create, read, update, delete)
# Replacing it affects 100% of operations.
# Current type: dict -> dict+id
# Replacement must satisfy: fetch, merge, remove, bulk_fetch variants

# Dead node detection
products.unused_nodes()  # nodes placed but not wired into any flow

# Cycle detection
products.cycles()  # finds feedback loops (intentional or accidental)

# Performance profiling at graph level
products.bottleneck()  # "persist averages 15ms, all other nodes < 2ms"
products.suggest()     # "Consider caching after persist:fetch in read flow"
```

### 6. Multi-Mesh Composition

Meshes compose into larger meshes -- the fractal property:

```python
# Each domain is its own mesh
products = Mesh('products')
users    = Mesh('users')
orders   = Mesh('orders')

# Cross-mesh wiring
app = Mesh('app')
app.mount(products)
app.mount(users)
app.mount(orders)

# Wire flows that span domains
app.flow('checkout', [
    'orders/validate',
    'users/auth',
    'products/check_stock',
    'orders/persist',
    'products/decrement_stock',
    'orders/notify',
])

# The full application topology is visible at any level:
# app level -> cross-domain flows
# domain level -> internal flows
# node level -> individual transformation
```

## The Unified Primitive: Mesh

```
Mesh = Actor + Graph[Node, Wire]

         Actor gives it:          Graph gives it:           Functor gives it:
         ---------------          ---------------           -----------------
         addr (identity)          nodes (components)        typed transforms
         inbox (receive)          wires (connections)       type validation
         children (sub-meshes)    flows (named paths)       error short-circuit
         Matrix routing           branching/merging         composable stages
         lifecycle                runtime rewiring
         interceptors             topology introspection
```

### Sketch: Mesh Class

```python
class Node:
    """Base class for mesh components. A typed TX transformer."""
    __name__: str

    async def process(self, tx: TX) -> TX:
        """Override this. The node's transformation logic."""
        raise NotImplementedError

    async def __call__(self, tx: TX) -> TX:
        """Execute with railway short-circuit."""
        if tx.is_error:
            return tx
        return await self.process(tx)


class FlowSpec:
    """A named path through the mesh -- sequence of node references."""
    def __init__(self, name: str, steps: list):
        self.name = name
        self.steps = steps       # list of node names, parallel/branch specs
        self.error_flow = None   # optional error handling path

    async def execute(self, tx: TX, nodes: dict) -> TX:
        """Run the TX through this flow's steps."""
        for step in self.steps:
            if isinstance(step, str):
                # Simple node reference: 'validate' or 'persist:fetch'
                node_name, _, method = step.partition(':')
                node = nodes[node_name]
                if method:
                    tx = await getattr(node, method)(tx)
                else:
                    tx = await node(tx)
                if tx.is_error:
                    if self.error_flow:
                        return await self.error_flow.execute(tx, nodes)
                    return tx

            elif isinstance(step, dict):
                if 'parallel' in step:
                    # Fan-out: run all concurrently, collect results
                    tasks = [nodes[n](tx) for n in step['parallel']]
                    results = await asyncio.gather(*tasks)
                    # Check for errors in any branch
                    errors = [r for r in results if r.is_error]
                    if errors:
                        tx = errors[0]  # surface first error
                    # Otherwise tx passes through unchanged (side-effect nodes)

                elif 'branch' in step:
                    # Conditional: route key comes from tx.meta['route']
                    route = tx.meta.get('route', 'default')
                    branch_steps = step['branch'].get(route, [])
                    for bstep in branch_steps:
                        node = nodes[bstep]
                        tx = await node(tx)
                        if tx.is_error:
                            break
        return tx


class Mesh(Actor):
    """A graph of nodes and flows. IS an actor -- routable, lifecycle, children.

    The wiring IS the program. Place nodes, connect them with flows,
    mount in the actor tree.
    """

    def __init__(self, name: str, **kwargs):
        super().__init__(addr=name, **kwargs)
        self._nodes: dict[str, Node] = {}
        self._flows: dict[str, FlowSpec] = {}

    def node(self, name: str, component: Node) -> 'Mesh':
        """Place a node in the mesh."""
        component.__name__ = name
        self._nodes[name] = component
        return self

    def flow(self, name: str, steps: list) -> 'Mesh':
        """Wire a named flow through existing nodes."""
        # Validate all referenced nodes exist
        for step in steps:
            if isinstance(step, str):
                node_name = step.partition(':')[0]
                assert node_name in self._nodes, (
                    f"Node '{node_name}' not found in mesh '{self.addr}'. "
                    f"Available: {list(self._nodes.keys())}"
                )
        self._flows[name] = FlowSpec(name, steps)
        return self

    def on_error(self, flow_name: str, steps: list) -> 'Mesh':
        """Wire an error handling flow for an existing flow."""
        self._flows[flow_name].error_flow = FlowSpec(f'{flow_name}_error', steps)
        return self

    async def inbox(self, tx: TX) -> None:
        """Route TX to the matching flow by tx.name."""
        flow_name = tx.name.lower()
        if flow_name in self._flows:
            result = await self._flows[flow_name].execute(tx, self._nodes)
            await self.send(result if result.is_error else tx.reply(data=result.data))
        else:
            await self.send(tx.error(f"No flow '{flow_name}' in mesh '{self.addr}'", 404))

    # -- Introspection --

    def describe(self) -> str:
        """Human-readable topology description."""
        lines = [f"{self.addr}/"]
        for name, flow in self._flows.items():
            step_names = []
            for s in flow.steps:
                if isinstance(s, str):
                    step_names.append(s)
                elif isinstance(s, dict):
                    step_names.append(str(s))
            lines.append(f"  {name}: {' -> '.join(step_names)}")

        lines.append(f"\n  nodes:")
        for name, node in self._nodes.items():
            lines.append(f"    {name:12s} {node.__class__.__name__}")
        return '\n'.join(lines)

    def depends_on(self, node_name: str) -> list[str]:
        """Which flows reference this node?"""
        result = []
        for fname, flow in self._flows.items():
            for step in flow.steps:
                ref = step if isinstance(step, str) else ''
                if ref.partition(':')[0] == node_name:
                    result.append(fname)
                    break
        return result

    def unused_nodes(self) -> list[str]:
        """Nodes placed but not wired into any flow."""
        used = set()
        for flow in self._flows.values():
            for step in flow.steps:
                if isinstance(step, str):
                    used.add(step.partition(':')[0])
        return [n for n in self._nodes if n not in used]

    # -- Runtime rewiring --

    def replace(self, node_name: str, new_component: Node) -> 'Mesh':
        """Replace a node. All flows referencing it get the new component."""
        assert node_name in self._nodes, f"Node '{node_name}' not found"
        new_component.__name__ = node_name
        self._nodes[node_name] = new_component
        return self

    def insert(self, flow_name: str, *, after: str, node: str) -> 'Mesh':
        """Insert a node into a flow after a specific step."""
        flow = self._flows[flow_name]
        for i, step in enumerate(flow.steps):
            if step == after:
                flow.steps.insert(i + 1, node)
                return self
        raise ValueError(f"Step '{after}' not found in flow '{flow_name}'")

    def detach(self, flow_name: str, *, node: str) -> 'Mesh':
        """Remove a node from a flow (node stays in mesh, just unwired)."""
        flow = self._flows[flow_name]
        flow.steps = [s for s in flow.steps if s != node]
        return self

    def mount(self, sub_mesh: 'Mesh', namespace: str = '') -> 'Mesh':
        """Mount a sub-mesh as a child. Cross-mesh wiring uses 'child/node'."""
        ns = namespace or sub_mesh.addr
        self.register(sub_mesh)
        # Import nodes with namespace prefix for cross-mesh wiring
        for name, node in sub_mesh._nodes.items():
            self._nodes[f'{ns}/{name}'] = node
        return self
```

## Limitations

- No message-level history -- the mesh doesn't journal individual TX processing
- No sender-defined processing -- the topology is fixed (defined by the mesh owner)
- No cross-system portability -- the mesh is a local graph, not a serializable plan
- More complex than linear pipelines for simple use cases
- Flow specifications are data, not compiled -- typos in node names are runtime errors
  (mitigated by validation in `flow()`, but not as strong as `>>` type checking)

These limitations are addressed by Propositions 1 (Reactive) and 2 (Journey).
