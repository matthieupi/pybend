# Proposition 2: Journey — The Message Knows Its Own Destiny

**Motto:** *The message knows its own destiny.*
**Core metaphor:** Self-driving car with a GPS plan
**The program is:** The message's processing plan
**Primary operator:** `tx.through()` (plan)

---

## The Core Insight

Look at how TX.meta already works in N3TX:

```python
tx.meta['user']       # auth context -- injected by interceptor
tx.meta['req']        # request correlation -- injected by reply()
tx.meta['stream']     # stream state -- injected by stream_chunk()
tx.meta['seq']        # chunk sequence -- injected by stream_chunk()
tx.meta['sql_filter'] # query filter -- injected by tier 1 auth
tx.meta['error']      # error flag -- injected by error()
```

TX.meta **already IS** `MonadWithLogs`. It accumulates execution context as
the message flows through the system. But today, it's a passive bag -- actors
stuff things into it ad hoc. And routing is entirely actor-side: Matrix reads
the target address, finds the child, dispatches.

**What if the TX carries not just context, but its entire processing plan?**

Proposition 1 said: actors compose into pipelines, messages flow through them.
The **actor** knows the pipeline.

Proposition 2 inverts this: the **message** knows the pipeline. Actors provide
**capabilities**, the TX provides the **plan**. The message is a traveling
computation that executes itself as it moves through the system.

```
Prop 1: Actor defines pipeline, TX is passive payload
        Pipeline(Validate >> Persist >> Notify).inbox(tx)

Prop 2: TX defines journey, Actor is execution environment
        tx.through(Validate >> Persist >> Notify).depart(matrix)
```

This is the difference between a **train on fixed tracks** (Prop 1) and a
**self-driving car with a GPS plan** (Prop 2).

## How It Works

TX gains a `plan` -- an ordered sequence of functor stages. When an actor
receives a planned TX, it executes the current stage and advances the TX to
the next one. The TX drives its own processing.

```python
class TX:
    name: str
    source: str
    target: str
    data: dict
    meta: dict
    # New: the journey
    plan: list[Stage]       # ordered stages to execute
    cursor: int = 0         # current position in plan
    journal: list[Entry]    # execution history (MonadWithLogs)

    def advance(self, result_data) -> 'TX':
        """Move to next stage -- the monadic bind."""
        self.journal.append(Entry(
            stage=self.current_stage,
            input=self.data,
            output=result_data,
            timestamp=time.time(),
        ))
        return TX(
            **self.__dict__,
            data=result_data,
            cursor=self.cursor + 1,
        )

    @property
    def current_stage(self) -> Stage:
        return self.plan[self.cursor] if self.cursor < len(self.plan) else None

    @property
    def is_complete(self) -> bool:
        return self.cursor >= len(self.plan)
```

## The Three Systems Side by Side

**Same task: "Create a product with validation, persistence, and notification"**

### Pyrofunc Alone

```python
result = Monad(data) | Validate >> Persist(db) >> Notify
# The pipeline exists only in this line of code.
# No routing. No async. No history. Fire and forget.
```

### Actor Alone

```python
class ProductActor(ActorModel):
    async def handler(target, tx):
        if tx.name == 'CREATE':
            validated = validate(tx.data)
            stored = await db.create(validated)
            await notify(stored)
            await target.send(tx.reply(stored))
# The processing is buried in imperative code.
# Can't inspect, replay, or reuse the sequence.
```

### Journey

```python
# The SENDER defines the journey -- not the receiver
tx = TX.journey(
    data={'name': 'Widget', 'price': 9.99},
    through=Validate >> Persist >> Notify >> Respond,
)

# The system executes it -- any actor tree with the right capabilities
result = await matrix.dispatch(tx)

# The TX IS its own audit trail
result.journal
# [
#   Entry(stage=Validate, input={name,price}, output={name,price,valid:True}, 2ms),
#   Entry(stage=Persist,  input={..},         output={.., id:42},            15ms),
#   Entry(stage=Notify,   input={.., id:42},  output={.., id:42},            3ms),
#   Entry(stage=Respond,  input={.., id:42},  output={status:'ok', id:42},   1ms),
# ]
```

## What Only the Journey Has

### 1. Self-Documenting Messages

Every TX is a **complete audit record**. You don't instrument your actors with
logging -- the message logs itself.

```python
# Any TX can answer: what happened to you?
tx.journal           # full stage-by-stage history
tx.journal[1].input  # what Persist received
tx.journal[1].took   # how long Persist took
tx.plan              # what was supposed to happen
tx.cursor            # how far we got (3 of 4 = Notify finished, Respond pending)
```

Today, tracing a request through N3TX actors means correlating logs across
multiple actors using `meta['req']` UUIDs. With journaled TX, you hand
someone the TX object and they see **everything**.

### 2. Replay and Resume

Because the TX carries both its plan and its journal, you can replay from any
checkpoint:

```python
# Something failed at stage 3 (Notify). Fix the bug, then:
resumed = await matrix.replay(failed_tx, from_stage=2)
# Re-runs Persist -> Notify -> Respond with the original data

# Time-travel debugging: what if Persist got different data?
alt = await matrix.replay(failed_tx, from_stage=1, with_data={'price': 0})
# Runs Persist(modified) -> Notify -> Respond
```

This is impossible with Prop 1 (pipelines don't record history) and
impossible with standalone actors (handler state is ephemeral).

### 3. Sender-Defined Processing

Today, the sender says WHERE to go (target address). The receiver decides
WHAT to do. The sender has no control over processing.

With Journey, the sender says WHAT should happen:

```python
# Admin creates a product -- with extra validation
admin_create = TX.journey(
    data=product_data,
    through=Validate >> ComplianceCheck >> Persist >> Notify >> AuditLog,
    meta={'user': admin},
)

# Regular user creates a product -- standard flow
user_create = TX.journey(
    data=product_data,
    through=Validate >> Persist >> Notify,
    meta={'user': regular_user},
)

# Same target actor, different processing -- defined by the caller
await matrix.dispatch(admin_create)
await matrix.dispatch(user_create)
```

The caller composes the journey from available stages. The actor tree provides
the execution context. This is a **capability-based** model: the sender asks
for capabilities, not addresses.

### 4. Portable Computation

A TX with a plan is **serializable**. The journey can cross system boundaries:

```python
# System A: Create the journey
tx = TX.journey(
    data={'document': large_pdf},
    through=Parse >> OCR >> Classify >> Store >> Index,
)

# System A runs Parse and OCR (has GPU capabilities)
partial = await system_a.dispatch(tx, stop_after='OCR')
# partial.cursor == 2, journal has Parse + OCR entries

# Send partially-processed TX to System B (has storage + search)
await network.send(partial, to='system-b')

# System B resumes from where A left off
result = await system_b.dispatch(partial)
# Runs Classify -> Store -> Index
```

The TX carries its own continuation. It knows what's done, what's left, and
what the intermediate results were. This is distributed computing where the
**message orchestrates its own execution** across systems.

### 5. Dynamic Journey Modification

Because the plan is data (a list of stages), it can be modified in flight:

```python
class SmartRouter(Stage):
    """A stage that modifies the remaining journey based on data."""
    async def __exec__(self, tx: TX) -> TX:
        if tx.data.get('priority') == 'critical':
            # Insert extra stages into the remaining plan
            tx.plan.insert(tx.cursor + 1, ManagerApproval)
            tx.plan.insert(tx.cursor + 2, EscalationNotify)
        return tx

flow = Validate >> SmartRouter >> Persist >> Notify
# For critical items: Validate -> SmartRouter -> ManagerApproval -> EscalationNotify -> Persist -> Notify
# For normal items:   Validate -> SmartRouter -> Persist -> Notify
```

The journey adapts to its own content. A stage can rewrite the remaining plan
based on what it discovers in the data. This is **self-modifying computation**
-- like Lisp, where code is data.

### 6. Compensation (Saga Pattern)

Each stage can declare a **compensating action** -- what to undo if a later
stage fails:

```python
class Persist(Stage):
    async def __exec__(self, tx: TX) -> TX:
        entity = await db.create(tx.data)
        return tx.advance({**tx.data, 'id': entity.id})

    async def compensate(self, tx: TX) -> TX:
        await db.delete(tx.data['id'])
        return tx

# If Notify fails after Persist succeeded:
# The journey automatically runs Persist.compensate() to undo the write
flow = Validate >> Persist >> Notify  # saga-aware
```

This is the **Saga pattern** -- each step knows how to undo itself. The TX's
journal gives you the exact compensation sequence. Impossible with standalone
pyrofunc (no error handling) and hard to bolt onto actors (no structured undo).

## The Unified Primitive: Planned TX

```
TX = Monad + Plan + Journal

         Monad gives it:          Plan gives it:          Journal gives it:
         ---------------          --------------          -----------------
         data (wrapped value)     stages (what to do)     history (what happened)
         advance() (bind)         cursor (where we are)   replay (time travel)
         error (Left track)       dynamic modification    audit trail
         dtype (type tag)         compensation (undo)     timing/metrics
```

### Sketch: JourneyTX

```python
@dataclass
class JournalEntry:
    """One stage's execution record."""
    stage_name: str
    input_data: dict
    output_data: dict
    timestamp: float
    duration_ms: float
    error: str | None = None


class JourneyTX(TX):
    """A TX that carries its own processing plan and execution journal.

    The message IS the program. Actors provide capabilities,
    the JourneyTX provides the plan.
    """
    plan: list = field(default_factory=list)
    cursor: int = 0
    journal: list[JournalEntry] = field(default_factory=list)

    @classmethod
    def journey(cls, data: dict, through, **kwargs) -> 'JourneyTX':
        """Create a TX with a processing plan.

        through: a functor, composed pipeline, or list of stages.
        """
        if isinstance(through, Pipeline):
            stages = through.stages
        elif isinstance(through, list):
            stages = through
        else:
            stages = [through]

        return cls(
            name=kwargs.pop('name', 'JOURNEY'),
            source=kwargs.pop('source', 'client'),
            target=kwargs.pop('target', ''),
            data=data,
            plan=stages,
            **kwargs,
        )

    @property
    def current_stage(self):
        if self.cursor < len(self.plan):
            return self.plan[self.cursor]
        return None

    @property
    def is_complete(self) -> bool:
        return self.cursor >= len(self.plan)

    def advance(self, result_data: dict, stage_name: str, duration_ms: float) -> 'JourneyTX':
        """Record completed stage and move cursor forward."""
        self.journal.append(JournalEntry(
            stage_name=stage_name,
            input_data=self.data,
            output_data=result_data,
            timestamp=time.time(),
            duration_ms=duration_ms,
        ))
        # Return new TX at next cursor position
        return JourneyTX(
            name=self.name, source=self.source, target=self.target,
            data=result_data, meta=self.meta,
            plan=self.plan, cursor=self.cursor + 1, journal=self.journal,
        )

    async def dispatch(self, executor) -> 'JourneyTX':
        """Execute the remaining plan through an executor (Matrix, actor, etc.)."""
        tx = self
        while not tx.is_complete and not tx.is_error:
            stage = tx.current_stage
            start = time.time()
            tx = await stage(tx)
            duration = (time.time() - start) * 1000
            if not tx.is_error:
                tx = tx.advance(tx.data, stage.__name__, duration)
        return tx

    @classmethod
    async def replay(cls, completed_tx: 'JourneyTX', from_stage: int = 0,
                     with_data: dict = None) -> 'JourneyTX':
        """Replay a journey from a specific stage, optionally with modified data."""
        data = with_data or completed_tx.journal[from_stage].input_data
        replayed = cls.journey(
            data=data,
            through=completed_tx.plan[from_stage:],
            name=completed_tx.name,
            meta={**completed_tx.meta, 'replayed_from': from_stage},
        )
        return await replayed.dispatch(None)  # self-executing
```

## Limitations

- No topology-level reasoning -- can't see the full system graph
- No shared components -- each TX carries its own independent plan
- No visual introspection -- the plan is per-message, not per-system
- Serialization of stages requires stages to be name-resolvable (not just lambdas)
- Sender-defined processing requires trust -- the sender controls execution

These limitations are addressed by Propositions 1 (Reactive) and 3 (Mesh).
