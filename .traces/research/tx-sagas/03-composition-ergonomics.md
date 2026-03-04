# Composition Patterns & Developer Ergonomics for Multi-Step TX Workflows

> How to design multi-step TX APIs that feel natural to developers: DSL approaches,
> fluent builders, decorator patterns, async pipelines, and lessons from real-world
> workflow libraries on what makes a great DX.

---

## Executive Summary

The difference between a workflow API developers **love** and one they **tolerate** usually comes down to three things: **how quickly they can write their first workflow**, **how intuitive error handling feels**, and **how easy it is to test individual steps in isolation**. This document surveys the composition patterns used by Temporal, Elixir's Sage, Prefect, Dagster, Cloudflare Workflows, dry-python's `returns`, and Akka/Pekko -- then synthesizes recommendations for a **Python actor system** that already has TX messaging, interceptors, and `@expose_route` decorators as building blocks.

> **Key Insight:** The highest-adoption workflow libraries all converge on the same principle: **workflows should look like regular code with superpowers**. Temporal, Prefect, and Cloudflare all let developers write `async def` functions with decorators -- no YAML, no JSON DSL, no separate configuration language. The data shows that code-first approaches reduce time-to-first-workflow from **weeks to hours** compared to DSL-driven systems like Netflix Conductor or AWS Step Functions.

**Bottom line for the CEO:** Building saga composition into an actor framework is a **competitive differentiator** when the API is right. Temporal raised **$246M** proving that durable workflows are a massive market. But Temporal's learning curve -- roughly **1 month to productivity** ([Procycons 2025 Guide](https://procycons.com/en/blogs/workflow-orchestration-platforms-comparison-2025/)) -- leaves a gap for lighter-weight alternatives that layer saga semantics onto existing actor messaging without requiring developers to learn a new mental model.

---

## Table of Contents

1. [Landscape: How the Industry Defines Multi-Step Workflows](#-landscape-how-the-industry-defines-multi-step-workflows)
2. [Pattern Deep-Dives](#-pattern-deep-dives)
   - [Temporal: Workflows as Async Classes](#temporal-workflows-as-async-classes)
   - [Sage: Pipe-Based Saga DSL](#sage-pipe-based-saga-dsl)
   - [Prefect / Dagster: Decorated Functions](#prefect--dagster-decorated-functions)
   - [Cloudflare Workflows: Step Decorators](#cloudflare-workflows-step-decorators)
   - [dry-python returns: Railway-Oriented Programming](#dry-python-returns-railway-oriented-programming)
   - [Akka/Pekko: Typed Actor Sagas](#akkapekko-typed-actor-sagas)
3. [Comparison Matrix](#-comparison-matrix)
4. [Error Handling Ergonomics](#-error-handling-ergonomics)
5. [Testability Patterns](#-testability-patterns)
6. [Synthesis: What Would Feel Natural in a Python Actor System](#-synthesis-what-would-feel-natural-in-a-python-actor-system)
7. [Proposed API Designs](#-proposed-api-designs)
8. [Risks and Gotchas](#-risks-and-gotchas)
9. [Recommendations](#-recommendations)
10. [Sources](#-sources)

---

## :mag: Landscape: How the Industry Defines Multi-Step Workflows

The workflow/saga composition space divides into **three camps**, each with distinct tradeoffs:

```
                        Composition Approaches
  ┌──────────────────┬────────────────────┬──────────────────────┐
  │   CODE-FIRST     │   DSL/CONFIG       │   FUNCTIONAL         │
  │                  │                    │   COMPOSITION        │
  ├──────────────────┼────────────────────┼──────────────────────┤
  │ Temporal         │ Netflix Conductor  │ dry-python returns   │
  │ Prefect          │ AWS Step Functions │ Elixir Sage          │
  │ Dagster          │ Kestra (YAML)      │ Railway-Oriented     │
  │ Cloudflare WF    │ Airflow (DAG cfg)  │ Rust Result<T,E>    │
  ├──────────────────┼────────────────────┼──────────────────────┤
  │ Learning curve:  │ Learning curve:    │ Learning curve:      │
  │ Low-Medium       │ Medium-High        │ High (concepts)      │
  │ Type safety: ++  │ Type safety: --    │ Type safety: +++     │
  │ Testability: +++ │ Testability: +     │ Testability: +++     │
  │ IDE support: +++ │ IDE support: +     │ IDE support: ++      │
  └──────────────────┴────────────────────┴──────────────────────┘
```

The **clear winner** for developer adoption is code-first. Prefect's learning curve is described as "basically zero for Python developers" ([Procycons](https://procycons.com/en/blogs/workflow-orchestration-platforms-comparison-2025/)). Conductor's JSON DSL, by contrast, is "cumbersome to design and tricky to debug" ([Instaclustr comparison](https://www.instaclustr.com/blog/workflow-comparison-uber-cadence-vs-netflix-conductor/)).

| Approach | Example | Time to First Workflow | Time to Production |
|----------|---------|----------------------|-------------------|
| **Code-first (decorators)** | Prefect, Cloudflare | Minutes to hours | Days |
| **Code-first (class-based)** | Temporal | Hours to days | ~1 month |
| **DSL/JSON** | Conductor, Step Functions | Hours | Weeks |
| **Functional composition** | dry-python returns | Hours (if FP background) | Days to weeks |
| **Pipe-based** | Sage (Elixir) | Minutes | Hours |

---

## :mag: Pattern Deep-Dives

### Temporal: Workflows as Async Classes

Temporal's Python SDK is the gold standard for **durable workflow execution**. Its core insight: workflows are **classes decorated with `@workflow.defn`**, and activities are **functions decorated with `@activity.defn`**. The workflow body is a regular `async def` method -- no special DSL ([Temporal Python docs](https://docs.temporal.io/develop/python/core-application)).

```python
from temporalio import workflow, activity
from dataclasses import dataclass
from datetime import timedelta

@dataclass
class BookVacationInput:
    user_id: str
    destination: str
    attempts: int = 3

@activity.defn
async def book_car(input: BookVacationInput) -> str:
    return f"Car booked for {input.user_id}"

@activity.defn
async def book_hotel(input: BookVacationInput) -> str:
    return f"Hotel booked at {input.destination}"

@activity.defn
async def book_flight(input: BookVacationInput) -> str:
    return f"Flight booked to {input.destination}"

@activity.defn
async def undo_book_car(input: BookVacationInput) -> str:
    return "Car booking cancelled"

@activity.defn
async def undo_book_hotel(input: BookVacationInput) -> str:
    return "Hotel booking cancelled"

@workflow.defn
class BookingWorkflow:
    @workflow.run
    async def run(self, input: BookVacationInput) -> dict:
        compensations = []
        try:
            compensations.append(undo_book_car)
            await workflow.execute_activity(
                book_car, input,
                start_to_close_timeout=timedelta(seconds=10),
            )
            compensations.append(undo_book_hotel)
            await workflow.execute_activity(
                book_hotel, input,
                start_to_close_timeout=timedelta(seconds=10),
            )
            await workflow.execute_activity(
                book_flight, input,
                start_to_close_timeout=timedelta(seconds=10),
            )
            return {"status": "success"}
        except Exception as ex:
            for comp in reversed(compensations):
                await workflow.execute_activity(
                    comp, input,
                    start_to_close_timeout=timedelta(seconds=10),
                )
            return {"status": "failure", "error": str(ex)}
```
*Source: [Temporal trip booking tutorial](https://learn.temporal.io/tutorials/python/trip-booking-app/)*

**What developers love:**
- Workflows look like **regular Python** -- `async/await`, `try/except`, `for` loops
- Full **type safety** with MyPy support; starting a workflow with wrong param types fails at lint time ([Temporal SDK GitHub](https://github.com/temporalio/sdk-python))
- **Replay semantics** give automatic retries and durability
- IDE autocomplete works naturally on typed dataclasses

**What developers hate:**
- The **replay model is conceptually difficult** -- you cannot use random numbers, current time, or non-deterministic operations inside a workflow ([Temporal DX tips](https://medium.com/symphonyis/tips-for-a-better-developer-experience-with-temporal-9b2205ee0563))
- **Worker versioning** has been a persistent pain point (public preview only as of 2025, [Temporal blog](https://temporal.io/blog/announcing-worker-versioning-public-preview-pin-workflows-to-a-single-code))
- The **compensation list pattern** is manual -- no built-in saga abstraction; developers hand-roll the `compensations = []` pattern
- Requires a **Temporal server** to be running

> **Key Insight:** Temporal proves that async class-based workflows with decorators achieve broad adoption. But its compensation handling is surprisingly **manual** -- there is no `@workflow.compensate` decorator. This is a design gap that a lighter framework could fill.

---

### Sage: Pipe-Based Saga DSL

Elixir's [Sage library](https://github.com/Nebo15/sage) (v0.6.3, ~700 GitHub stars) is the cleanest pure saga implementation in any ecosystem. Its pipe-based DSL makes multi-step transactions read like a recipe:

```elixir
# Sage — pipe-based saga composition
Sage.new()
|> Sage.run(:user, &create_user/2)
|> Sage.run(:plans, &fetch_plans/2, &plans_circuit_breaker/3)
|> Sage.run(:subscription, &create_subscription/2, &delete_subscription/3)
|> Sage.run_async(:delivery, &schedule_delivery/2, &delete_delivery/3)
|> Sage.run_async(:receipt, &send_receipt/2, &send_excuse/3)
|> Sage.run(:update_user, &set_plan_for_user/2)
|> Sage.finally(&acknowledge_job/2)
|> Sage.with_tracer(MyTracer)
|> Sage.execute(attrs)
```
*Source: [Sage README / hexdocs](https://hexdocs.pm/sage/Sage.html)*

The API surface is **tiny**: `new()`, `run()`, `run_async()`, `finally()`, `execute()`, `transaction()`, `with_tracer()`, `with_compensation_error_handler()`. That's the entire public API.

**Design brilliance:**

```
Transaction flow:    [T1] --> [T2] --> [T3] --> [T4]   Success!

Failure + rollback:  [T1] --> [T2] --> [T3 ERROR]
                      |                   |
                     [C1] <-- [C2] <-- [C3]           Compensated!

Circuit breaker:     [T1] --> [T2 ERROR]
                               |
                     [C2 {:continue, cached}] --> [T3]  Recovered!
```

**Key API decisions worth stealing:**

| Decision | Why It Works |
|----------|-------------|
| **Named steps** (`:user`, `:plans`) | Effects accumulate in a map -- each step can access previous results by name |
| **Compensation is adjacent to transaction** | `run(:step, &do_thing/2, &undo_thing/3)` -- the undo is declared right next to the do |
| **`:noop` default compensation** | Steps without side effects skip the `undo` function argument |
| **`run_async`** | Parallel execution with automatic sync barriers before the next sequential step |
| **`{:continue, effect}`** return | Circuit breaker pattern -- compensation returns a fallback value and continues forward |
| **`{:retry, opts}`** return | Compensations can retry with backoff: `{:retry, retry_limit: 5, base_backoff: 10}` |

**Limitations:**
- No process crash recovery (RFC exists but unimplemented)
- Elixir-only; the pattern hasn't been ported well to Python
- No visualization or debugging UI

> **Key Insight:** Sage's co-location of transaction + compensation in a single `run()` call is the **single best API decision** in the saga space. Temporal forces you to manually track compensations in a list. Sage makes it structurally impossible to forget a compensation.

---

### Prefect / Dagster: Decorated Functions

**Prefect 3** uses the simplest possible pattern -- decorated Python functions:

```python
from prefect import flow, task

@task(retries=3, retry_delay_seconds=10)
def extract_data(url: str) -> dict:
    return requests.get(url).json()

@task
def transform_data(raw: dict) -> dict:
    return {k: v.strip() for k, v in raw.items()}

@task
def load_data(data: dict) -> None:
    db.insert(data)

@flow(name="ETL Pipeline")
def etl_pipeline(url: str):
    raw = extract_data(url)
    clean = transform_data(raw)
    load_data(clean)
```
*Source: [Prefect quickstart](https://docs.prefect.io/v3/get-started/quickstart)*

**Dagster** uses a richer model with **ops** (operations) and **assets** (data products):

```python
import dagster as dg

@dg.op
def return_one() -> int:
    return 1

@dg.op
def add_one(number: int) -> int:
    return number + 1

@dg.graph
def linear():
    add_one(add_one(add_one(return_one())))

@dg.asset
def upstream_asset():
    return [1, 2, 3]

@dg.graph_asset
def derived_asset(upstream_asset):
    return multiply_by_two(add_one(upstream_asset))
```
*Source: [Dagster docs - graphs](https://docs.dagster.io/api/dagster/graphs)*

| Feature | Prefect | Dagster |
|---------|---------|--------|
| **Core abstraction** | `@flow` + `@task` | `@asset` + `@op` + `@graph` |
| **Composition** | Imperative (call tasks in flow) | Declarative (function args = dependencies) |
| **Type safety** | Moderate (runtime validation) | Strong (IO types, resource types) |
| **Saga/compensation** | Not built-in | Not built-in |
| **Learning curve** | ~Zero for Python devs | Moderate (asset model is opinionated) |
| **Concurrency** | `task.map()` for parallel | `@graph` with parallel ops |
| **Retries** | `@task(retries=3)` | `@op(retry_policy=...)` |

A [FreeAgent engineering blog comparison](https://engineering.freeagent.com/2025/05/29/decoding-data-orchestration-tools-comparing-prefect-dagster-airflow-and-mage/) notes that Dagster "forces every workflow into its Software-Defined Asset model" which can feel constraining for simple sequential pipelines but excels at data lineage tracking.

**What translates to actor TX composition:**
- `@task` is analogous to a **saga step** -- a unit of work with retries
- `@flow` is analogous to a **saga orchestrator** -- coordinates steps
- Prefect's **implicit data flow** (return values become inputs) is clean but lacks compensation semantics

---

### Cloudflare Workflows: Step Decorators

Cloudflare's [Python Workflows SDK](https://blog.cloudflare.com/python-workflows/) (beta, 2025) introduced a clever decorator-based step API that bridges Python's lack of anonymous callbacks:

```python
from workers import WorkflowEntrypoint

class MyWorkflow(WorkflowEntrypoint):
    async def run(self, event, step):
        @step.do("extract user email")
        async def extract():
            return {"email": event["payload"]["userEmail"]}

        result = await extract()

        @step.do("send welcome email")
        async def send_email():
            await email_service.send(result["email"])

        await send_email()

        # DAG-style dependency declaration
        @step.do("step A")
        async def step_a():
            return compute_a()

        @step.do("step B")
        async def step_b():
            return compute_b()

        @step.do("final", depends=[step_a, step_b], concurrent=True)
        async def final(res_a=None, res_b=None):
            return combine(res_a, res_b)

        await final()
```
*Source: [Cloudflare Python Workflows blog](https://blog.cloudflare.com/python-workflows/)*

This is notable because the **step decorator is provided as a parameter**, not imported globally. The `step` object carries the durable execution context. Testing becomes easier because you can mock `step` ([Cloudflare testing blog](https://blog.cloudflare.com/better-testing-for-workflows/)).

**Testing innovation** -- Cloudflare introduced step-level mocking:

```javascript
// Mock individual workflow steps
await instance.modify(async (m) => {
    await m.mockStepResult({ name: "AI content scan" }, { violationScore: 50 });
    await m.mockEvent({ type: "moderation-approval", payload: { action: "approved" } });
});
```

Before this, workflow testing was a "black box process with no visibility into intermediate steps" -- making debugging "really difficult" ([Cloudflare](https://blog.cloudflare.com/better-testing-for-workflows/)).

---

### dry-python returns: Railway-Oriented Programming

The [dry-python `returns` library](https://github.com/dry-python/returns) (**4.2k GitHub stars**) brings functional composition to Python with `Result`, `Maybe`, `IO`, and `FutureResult` containers:

```python
from returns.result import Result, Success, Failure
from returns.pipeline import flow
from returns.pointfree import bind_result

def validate_user(user_id: str) -> Result[str, str]:
    if not user_id:
        return Failure("Empty user ID")
    return Success(user_id)

def fetch_user(user_id: str) -> Result[dict, str]:
    user = db.get(user_id)
    if not user:
        return Failure(f"User {user_id} not found")
    return Success(user)

def create_order(user: dict) -> Result[dict, str]:
    if not user.get("verified"):
        return Failure("User not verified")
    return Success({"order_id": "123", "user": user["id"]})

# Compose with flow -- short-circuits on first Failure
result = flow(
    "user-42",
    validate_user,
    bind_result(fetch_user),
    bind_result(create_order),
)
# result is either Success({"order_id": "123", ...}) or Failure("...")
```
*Source: [returns Railway-Oriented Programming docs](https://returns.readthedocs.io/en/latest/pages/railway.html)*

The **railway metaphor** is powerful:

```
  Success track:  [validate] --> [fetch] --> [create] --> Success!
                       |             |            |
  Failure track:  [failure]    [failure]    [failure]   --> Failure
                  (short-circuits on first error)
```

**Error recovery** uses `lash()`:

```python
from returns.result import Result, Failure, Success

def recover_from_db_error(error: Exception) -> Result[dict, Exception]:
    if isinstance(error, ConnectionError):
        return Success({"from": "cache"})   # switch back to success track
    return Failure(error)                     # stay on failure track

result = Failure(ConnectionError()).lash(recover_from_db_error)
# result == Success({"from": "cache"})
```

**Relevance to actor sagas:** The `Result` type maps directly to TX's `reply()` / `error()` pattern. A saga step either produces a success TX or an error TX -- exactly two tracks. The `flow()` composition is analogous to piping TX messages through a sequence of handlers.

---

### Akka/Pekko: Typed Actor Sagas

The Akka ecosystem ([Akka saga patterns docs](https://doc.akka.io/concepts/saga-patterns.html)) distinguishes two saga approaches for actors:

**Orchestrator-based** -- a central workflow actor coordinates steps:
```
[Orchestrator] --book_car--> [CarService]
       |                          |
       | <---car_booked-----------+
       |
       | --book_hotel--> [HotelService]
       |                       |
       | <---hotel_booked------+
       |
       | --book_flight--> [FlightService]
```

**Choreography-based** -- services react to events:
```
[CarService] --car_booked--> [HotelService] --hotel_booked--> [FlightService]
                                                                    |
[CompensateAll] <----flight_failed--------------------------------+
```

Akka 3 recently simplified orchestrator sagas with a **Workflow component** that "handles all the technical challenges so developers can focus solely on business logic" ([Akka blog, April 2025](https://akka.io/blog/saga-patterns-in-akka-part-1-event-choreography)).

**Key lesson for N3TX:** The orchestrator pattern maps cleanly to an actor that manages a TX saga. The **choreography pattern** maps to N3TX's existing `_publish_lifecycle()` mechanism. Both are useful; the orchestrator is easier to reason about for developers.

---

## :bar_chart: Comparison Matrix

Rating scale: 1 = poor, 5 = excellent

| Approach | Learning Curve | Type Safety | Testability | Debuggability | Fit for Actor Systems | Compensation Built-in |
|----------|:---:|:---:|:---:|:---:|:---:|:---:|
| **Temporal** (class + decorator) | 3 | 5 | 4 | 3 | 4 | 2 (manual list) |
| **Sage** (pipe DSL) | 5 | 3 | 5 | 4 | 5 | 5 (co-located) |
| **Prefect** (decorator) | 5 | 3 | 4 | 4 | 3 | 1 (none) |
| **Cloudflare** (step decorator) | 4 | 3 | 5 | 4 | 3 | 1 (none) |
| **dry-python returns** (functional) | 2 | 5 | 5 | 3 | 4 | 3 (lash/recovery) |
| **Akka/Pekko** (typed actors) | 2 | 5 | 3 | 3 | 5 | 4 (workflow component) |
| **Dagster** (asset graph) | 3 | 4 | 4 | 4 | 2 | 1 (none) |

> **Key Insight:** The top-scoring combination for a Python actor system is **Sage's co-located compensation model** + **Prefect/Temporal's decorator ergonomics** + **dry-python's type-safe Result semantics**. No single existing library nails all three.

### Adoption Context

| Library | GitHub Stars | Language | Production Users | Funding |
|---------|:-----------:|----------|-----------------|---------|
| Temporal | ~12k | Multi-language | Netflix, Snap, Stripe | $246M Series C |
| Prefect | ~18k | Python | Thousands (OSS) | $70M Series B |
| Dagster | ~12k | Python | Thousands (OSS) | $70M Series C |
| Sage | ~700 | Elixir | Unknown | OSS, unfunded |
| dry-python returns | ~4.2k | Python | Unknown | OSS, unfunded |
| Cloudflare Workflows | N/A | JS/Python | Cloudflare customers | Internal |

---

## :warning: Error Handling Ergonomics

Error handling is where saga APIs **succeed or fail** in developer adoption. Here's how each approach handles a mid-workflow failure:

### The "Forgot to Compensate" Problem

Temporal's **manual compensation list** is the most common source of bugs:

```python
# Temporal -- easy to forget adding compensation
compensations = []
try:
    compensations.append(undo_book_car)    # <-- must remember this
    await workflow.execute_activity(book_car, ...)

    # BUG: forgot to add undo_book_hotel!
    await workflow.execute_activity(book_hotel, ...)

    await workflow.execute_activity(book_flight, ...)
except Exception:
    for comp in reversed(compensations):   # hotel is never undone
        await workflow.execute_activity(comp, ...)
```

Sage **eliminates this class of bug entirely** because compensation is co-located:

```elixir
# Sage -- compensation is structurally bound to the transaction
Sage.new()
|> Sage.run(:car, &book_car/2, &undo_car/3)      # can't forget
|> Sage.run(:hotel, &book_hotel/2, &undo_hotel/3) # compensation is right here
|> Sage.run(:flight, &book_flight/2)               # no compensation = :noop
```

### Error Channel Design

| Approach | Error Signaling | Recovery Path | Partial Failure Handling |
|----------|----------------|---------------|------------------------|
| **Temporal** | Python exceptions | `try/except` + compensation list | Manual tracking |
| **Sage** | `{:error, reason}` tuple | `{:retry, opts}` or `{:continue, effect}` | Automatic reverse-order compensation |
| **Prefect** | Python exceptions | `@task(retries=3)` | Task-level only, no saga |
| **dry-python** | `Failure(error)` container | `lash()` / `alt()` | Short-circuit + recovery functions |
| **TX (N3TX)** | `tx.error(msg, code)` | Interceptor chain | Not yet implemented |

The **best developer experience** for error handling follows a hierarchy:

1. **Make invalid states unrepresentable** (Sage's co-location)
2. **Make the error path explicit** (Result types, TX error method)
3. **Make recovery composable** (Sage's `{:retry}` / `{:continue}` / `lash()`)
4. **Make the default safe** (auto-compensation on failure)

---

## :zap: Testability Patterns

Testability is the **second most important factor** (after learning curve) in workflow library adoption. Cloudflare explicitly identified "poor testing experience" as a barrier that "discourages adoption of Workflows" ([Cloudflare testing blog](https://blog.cloudflare.com/better-testing-for-workflows/)).

### Testing Strategies by Approach

**Temporal** -- Test workflows using `WorkflowEnvironment`:
```python
async def test_booking_saga():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        result = await env.client.execute_workflow(
            BookingWorkflow.run,
            BookVacationInput(user_id="test", destination="Paris"),
            id="test-id",
            task_queue="test-queue",
        )
        assert result["status"] == "success"
```

**Sage** -- Pure functions, trivially testable:
```elixir
# Each transaction/compensation is a plain function
test "create_user succeeds" do
  assert {:ok, user} = create_user(%{}, %{"user" => valid_attrs()})
end

# The saga itself is testable as a whole
test "saga rolls back on subscription failure" do
  assert {:error, _reason} = create_and_subscribe_user(invalid_attrs())
end
```

**Prefect** -- Tasks are plain functions:
```python
# Without Prefect runtime -- just call the function
def test_transform():
    result = transform_data.fn({"key": " value "})
    assert result == {"key": "value"}
```

**dry-python returns** -- Pattern matching on Result:
```python
def test_create_order_pipeline():
    result = flow("user-42", validate_user, bind_result(fetch_user))
    assert isinstance(result, Success)
    assert result.unwrap()["id"] == "user-42"
```

### Testability Comparison

| Approach | Unit Test Steps | Integration Test Saga | Mock External Services | Time to Write Test |
|----------|:-:|:-:|:-:|:-:|
| **Sage** | Trivial (plain functions) | One-liner `execute()` | Standard mocking | Minutes |
| **Prefect** | Trivial (`.fn()` bypass) | Start flow in test | `@task` wrapping | Minutes |
| **dry-python** | Trivial (assert Result) | `flow()` call | Standard mocking | Minutes |
| **Temporal** | Moderate (need mock activities) | Need WorkflowEnvironment | Activity mocking API | 10-30 min setup |
| **Cloudflare** | Good (step mocking API) | `introspectWorkflow()` | Built-in mocking | Minutes (after setup) |
| **Akka/Pekko** | Complex (TestKit) | Complex (TestProbe) | ActorTestKit mocking | 30+ min setup |

> **Key Insight:** The best testability comes from **making steps plain functions** that can be called directly, and **making the saga runner a pure coordinator** that doesn't embed business logic. Sage and Prefect both nail this. Temporal adds friction because workflow code can't be run outside the Temporal runtime.

---

## :bulb: Synthesis: What Would Feel Natural in a Python Actor System

Given N3TX's existing primitives -- `TX` messages, `Actor` with `inbox`/`handler`/`send`, `@expose_route` decorators, and `use()` interceptors -- here are the design constraints and opportunities:

### Existing Primitives to Build On

```
┌─────────────────────────────────────────────────────────────────┐
│                    N3TX Actor System (v0.9)                   │
├─────────────────────────────────────────────────────────────────┤
│  TX          │ reply(), error(), is_error, meta, uuid           │
│  Actor       │ inbox(), handler(), send(), use(), register()    │
│  ActorModel  │ handler_crud(), _publish_lifecycle()             │
│  @expose_route│ Decorator marking methods as API endpoints      │
│  Interceptors│ async (TX) -> TX, chain on inbox/send/request    │
│  NetworkAPI  │ HTTP -> TX -> Matrix -> ActorModel bridge        │
└─────────────────────────────────────────────────────────────────┘
```

### Design Principles for TX Sagas

Drawing from the research, five principles should guide the API design:

1. **Co-locate compensation** (from Sage) -- Never let a developer define a forward step without seeing where the undo goes
2. **Use decorators, not DSLs** (from Prefect/Temporal) -- Python developers expect `@decorator` patterns
3. **Steps are plain functions** (from Sage/Prefect) -- Testable in isolation
4. **TX is the error channel** (from existing N3TX) -- `tx.reply()` = success track, `tx.error()` = failure track
5. **Interceptors participate in saga lifecycle** (from existing N3TX) -- `use()` on saga actors for cross-cutting concerns

---

## :bulb: Proposed API Designs

I present three candidate API designs, from simplest to most sophisticated. **They are not mutually exclusive** -- a layered approach can offer all three.

### Design A: Sage-Style Fluent Builder

The most direct translation of Sage's pipe pattern into Python. Uses method chaining (fluent interface) with co-located compensation.

```python
from n3tx.core.sagas import Saga

async def transfer_funds(data: dict, tx: TX):
    result = await (
        Saga("transfer_funds")
        .step("debit_source",
              action=lambda ctx: debit_account(ctx["source"], ctx["amount"]),
              compensate=lambda ctx, effect: credit_account(ctx["source"], ctx["amount"]))
        .step("credit_target",
              action=lambda ctx: credit_account(ctx["target"], ctx["amount"]),
              compensate=lambda ctx, effect: debit_account(ctx["target"], ctx["amount"]))
        .step("send_notification",
              action=lambda ctx: notify_user(ctx["source"], "Transfer complete"))
        # No compensate = noop (like Sage)
        .execute(data)
    )
    return tx.reply(result) if result.ok else tx.error(result.error)
```

**Pros:**
- Familiar to anyone who's used SQLAlchemy query builders or Pydantic model config
- **Co-located compensation** eliminates the "forgot to undo" class of bugs
- Each step gets accumulated context (like Sage's `effects_so_far`)
- Method chaining is **highly scannable** -- you can see the entire flow at a glance

**Cons:**
- Lambda-heavy for complex steps (Python lambdas are limited to expressions)
- Less IDE support for lambda signatures
- Hard to add type hints inside lambdas

### Design B: Decorator-Based Steps

More Pythonic -- uses decorators like `@expose_route` to mark functions as saga steps. This mirrors Temporal's activity pattern but adds co-located compensation.

```python
from n3tx.core.sagas import saga, step, compensates

@saga("order_fulfillment")
class OrderFulfillment:
    """Order processing saga with automatic compensation."""

    @step("validate_inventory")
    async def validate(self, ctx: SagaContext) -> dict:
        product = Product.get(ctx.data["product_id"])
        if product.stock < ctx.data["quantity"]:
            raise SagaError("Insufficient stock", code=409)
        return {"product": product, "quantity": ctx.data["quantity"]}

    @step("reserve_stock")
    async def reserve(self, ctx: SagaContext) -> dict:
        product = ctx.effects["validate_inventory"]["product"]
        product.stock -= ctx.data["quantity"]
        Product.update(product.id, {"stock": product.stock})
        return {"reserved": ctx.data["quantity"]}

    @compensates("reserve_stock")
    async def unreserve(self, ctx: SagaContext, effect: dict) -> None:
        product = ctx.effects["validate_inventory"]["product"]
        product.stock += effect["reserved"]
        Product.update(product.id, {"stock": product.stock})

    @step("charge_payment")
    async def charge(self, ctx: SagaContext) -> dict:
        charge = await PaymentService.charge(
            ctx.data["user_id"], ctx.data["amount"]
        )
        return {"charge_id": charge.id}

    @compensates("charge_payment")
    async def refund(self, ctx: SagaContext, effect: dict) -> None:
        await PaymentService.refund(effect["charge_id"])

    @step("create_shipment")
    async def ship(self, ctx: SagaContext) -> dict:
        return await ShippingService.create(ctx.data)

# Usage in an ActorModel:
class Order(ActorModel):
    __tablename__ = 'orders'

    @expose_route('/fulfill', methods=['POST'], access=AUTHENTICATED)
    async def fulfill(self, user: User = None) -> str:
        saga = OrderFulfillment()
        result = await saga.run({"product_id": self.product_id, ...})
        if result.ok:
            self.status = "fulfilled"
            Order.update(self.id, {"status": "fulfilled"})
            return json.dumps(result.effects)
        raise MethodError(result.error, status_code=result.code)
```

**Pros:**
- Steps are **real functions** with full type hints, docstrings, and IDE support
- `@compensates("step_name")` co-locates compensation with clear naming
- Each step is **independently testable**: `await saga.validate(mock_ctx)`
- Naturally extends N3TX's existing `@expose_route` decorator pattern
- Class-based organization groups related steps

**Cons:**
- More boilerplate than the fluent builder
- `@compensates` link is by string name (could use direct reference instead)
- Class instantiation overhead for simple sagas

### Design C: Context Manager + Pipeline

Uses Python's `async with` for saga lifecycle management, combined with functional composition for steps.

```python
from n3tx.core.sagas import TXSaga, SagaStep

async def process_order(data: dict, tx: TX):
    async with TXSaga("process_order", tx) as saga:
        # Each step auto-tracks in the saga context
        user = await saga.run(
            "validate_user",
            action=validate_user,
            compensate=None,  # validation has no side effects
            input=data["user_id"],
        )

        inventory = await saga.run(
            "reserve_inventory",
            action=reserve_stock,
            compensate=release_stock,
            input={"product": data["product_id"], "qty": data["qty"]},
        )

        payment = await saga.run(
            "charge_payment",
            action=charge_card,
            compensate=refund_card,
            input={"user": user, "amount": data["total"]},
        )

        # Parallel steps
        async with saga.parallel() as batch:
            batch.run("send_email", action=send_confirmation, input=user)
            batch.run("update_analytics", action=track_order, input=data)

    # saga.__aexit__ handles:
    #   - If all steps succeeded: returns accumulated effects
    #   - If any step failed: runs compensations in reverse, raises SagaFailed

    return saga.result  # SagaResult with .ok, .effects, .error
```

**Pros:**
- **Context manager guarantees cleanup** -- Python developers understand `async with` deeply
- `saga.parallel()` nested context for concurrent steps is elegant
- The saga lifetime is **visually bounded** by the `async with` block
- Natural integration with Python's structured concurrency (`TaskGroup` in 3.11+)

**Cons:**
- More imperative than the fluent builder
- Compensation functions are separate from action functions (less co-located)
- Harder to serialize/introspect the saga definition (it's code, not data)

### Design D: Pydantic Model-Based Workflow (Workflows as Data)

The most "N3TX-native" approach -- define sagas as Pydantic models, making them schema-derivable and inspectable:

```python
from n3tx.core.sagas import SagaModel, SagaStep

class OrderSaga(SagaModel):
    """Saga definition as data -- inspectable, serializable, schema-derivable."""
    __saga_name__ = "order_fulfillment"

    steps: list[SagaStep] = [
        SagaStep(
            name="validate",
            action="Order.validate_stock",
            compensate=None,
        ),
        SagaStep(
            name="reserve",
            action="Order.reserve_stock",
            compensate="Order.release_stock",
        ),
        SagaStep(
            name="charge",
            action="PaymentService.charge",
            compensate="PaymentService.refund",
        ),
        SagaStep(
            name="ship",
            action="ShippingService.create_shipment",
            compensate="ShippingService.cancel_shipment",
            async_step=True,
        ),
    ]

    timeout: float = 30.0  # saga-level timeout
    max_retries: int = 3

# The saga is data -- it can be:
# 1. Serialized to JSON Schema (exposed in /OrderSaga endpoint)
# 2. Visualized in the frontend as a step diagram
# 3. Version-controlled and diffed
# 4. Executed by a generic saga runner

runner = SagaRunner(matrix)
result = await runner.execute(OrderSaga, context={"order_id": 42})
```

**Pros:**
- **Aligns perfectly with N3TX's "model is the app" philosophy**
- Sagas become schema-derivable -- the frontend could render saga status/progress
- Version control of workflow definitions is trivial (it's just a model)
- Can be combined with the actor system -- the saga runner sends TX messages to steps

**Cons:**
- String references to actions (`"Order.validate_stock"`) lose type safety
- Less flexible than code-first for complex conditional logic
- Requires a separate runner/executor component

---

## :bar_chart: Design Comparison

| Criterion | A: Fluent Builder | B: Decorators | C: Context Mgr | D: Pydantic Model |
|-----------|:-:|:-:|:-:|:-:|
| **Learning curve** | 4 | 5 | 4 | 3 |
| **Type safety** | 2 | 4 | 3 | 2 |
| **Co-located compensation** | 5 | 4 | 3 | 4 |
| **Testability** | 3 | 5 | 4 | 3 |
| **IDE support** | 3 | 5 | 4 | 3 |
| **Fit with N3TX patterns** | 4 | 5 | 4 | 5 |
| **Debuggability** | 4 | 4 | 4 | 5 |
| **Introspectability** | 3 | 3 | 2 | 5 |

> **Key Insight:** **Design B (Decorators)** wins on developer ergonomics. **Design D (Pydantic Model)** wins on schema-driven architecture alignment. The optimal solution is **B for authoring, D for introspection** -- a decorator-defined saga that can export its step graph as a Pydantic model for schema/visualization purposes.

---

## :warning: Risks and Gotchas

### What Goes Wrong with Saga APIs

Based on community feedback and failure analysis across the libraries studied:

**1. Compensation ordering is subtle**

Compensations must run in **reverse order** of successful executions. If step 3 fails, you compensate step 2 then step 1 -- not step 1 then step 2. Sage handles this automatically. Temporal's manual list requires `reversed(compensations)` -- and developers forget.

**2. Idempotency is the developer's problem**

Every library studied **pushes idempotency onto the developer**. As [Sage's documentation](https://github.com/Nebo15/sage) warns: "Write compensations as idempotent operations since network failures may cause retries after successful external operations." This is consistently the hardest part for developers to get right.

**3. Partial compensation failures cascade**

If a compensation function itself fails, the system is in an inconsistent state. Approaches:
- Sage: "Let it fail" by default, register `with_compensation_error_handler/2` for custom handling
- Temporal: Compensation activities have their own retry policies
- Most frameworks: Log and continue (best-effort compensation)

**4. The async saga debugging problem**

Debugging a multi-step async workflow is significantly harder than debugging synchronous code. The [Cloudflare team](https://blog.cloudflare.com/better-testing-for-workflows/) found that without step-level introspection, debugging was a "black box process." Any saga API must provide:
- Step-level status tracking (`pending`, `running`, `completed`, `failed`, `compensated`)
- Causal links between steps (which step triggered which)
- Timing data (how long each step took)

**5. Transaction scope confusion**

Developers often confuse saga transactions with database transactions. A saga is **not ACID** -- it provides eventual consistency through compensations. This needs clear documentation and possibly a different name (`workflow`, `pipeline`, or `multi-step TX`) to avoid confusion.

### What NOT to Do

| Anti-Pattern | Why It Fails | Example |
|-------------|-------------|---------|
| **YAML/JSON workflow definitions** | Hard to test, no IDE support, no type checking | Netflix Conductor, early Airflow |
| **Implicit step ordering** | Developers can't reason about execution flow | Some DAG frameworks |
| **Hidden compensation** | Developers forget it exists until production fails | Frameworks with "auto-rollback" marketing |
| **Tight coupling to runtime** | Can't test without full infrastructure | Temporal (partial -- needs server) |
| **God-object orchestrators** | Violates single responsibility, hard to compose | Monolithic workflow classes |

---

## :bulb: Recommendations

### For N3TX: A Layered Approach

**Layer 1 -- TX Saga Primitives** (v1.0)

Extend the TX dataclass to support saga metadata:

```python
@dataclass
class TX:
    # ... existing fields ...
    # New: saga context in meta
    # meta = {
    #   'saga_id': 'order-fulfillment-abc123',
    #   'saga_step': 'reserve_stock',
    #   'saga_step_index': 2,
    #   'saga_effects': {'validate': {...}, 'reserve': {...}},
    #   'saga_compensations': ['release_stock', 'refund_payment'],
    # }
```

This requires **zero new classes** -- sagas are just TX messages with structured metadata. Interceptors can inspect `meta['saga_id']` for cross-cutting concerns (logging, tracing, timeout enforcement).

**Layer 2 -- Decorator API** (v1.1)

Implement Design B with a `@saga` class decorator and `@step`/`@compensates` method decorators:

```python
@saga("order_fulfillment")
class OrderSaga:
    @step("validate", order=1)
    async def validate(self, ctx): ...

    @step("reserve", order=2)
    async def reserve(self, ctx): ...

    @compensates("reserve")
    async def unreserve(self, ctx, effect): ...
```

The decorator-based approach:
- Matches `@expose_route` patterns developers already know
- Steps are testable as plain async methods
- The `@saga` class decorator registers the saga with the Matrix (like `ActorMeta` auto-registration)

**Layer 3 -- Schema Integration** (v1.2)

Generate JSON Schema for saga definitions, enabling:
- Frontend visualization of saga step progress
- API discovery of available sagas (like model schema endpoints)
- Runtime saga status tracking via schema-described state

### Priority Recommendation

> **Start with Layer 1 (TX meta conventions) and Layer 2 (decorator API)**. Layer 1 has zero architecture cost -- it's just a convention for what goes in `tx.meta`. Layer 2 gives developers the ergonomics they expect. Layer 3 can wait until there's a real frontend need for saga visualization.

### Concrete Implementation Sizing

| Component | Estimated LOC | Complexity | Dependencies |
|-----------|:---:|:---:|:---|
| `SagaContext` dataclass | ~50 | Low | TX, dataclasses |
| `@saga` / `@step` / `@compensates` decorators | ~150 | Medium | None (pure Python) |
| `SagaRunner` (executor) | ~200 | Medium | Actor, TX, asyncio |
| Saga interceptor (logging/tracing) | ~50 | Low | Actor.use() |
| SagaResult type | ~30 | Low | dataclasses |
| **Total** | **~480** | | |

This is a **small surface area** -- comparable to the existing interceptor system (~100 LOC) and `@expose_route` decorator (~20 LOC). The bulk of the complexity is in the `SagaRunner`, which manages step execution, compensation, and result accumulation.

---

## :link: Sources

1. [Temporal Python SDK developer guide](https://docs.temporal.io/develop/python) -- Official documentation for workflow and activity definitions
2. [Temporal Python SDK GitHub](https://github.com/temporalio/sdk-python) -- Source code, type safety details, MyPy integration
3. [Temporal trip booking tutorial](https://learn.temporal.io/tutorials/python/trip-booking-app/) -- Saga pattern implementation with compensating activities
4. [Temporal worker versioning announcement](https://temporal.io/blog/announcing-worker-versioning-public-preview-pin-workflows-to-a-single-code) -- Public preview of version pinning (2025)
5. [Sage GitHub (Nebo15/sage)](https://github.com/Nebo15/sage) -- Elixir saga library source code and README
6. [Sage API documentation (hexdocs)](https://hexdocs.pm/sage/Sage.html) -- Full API reference with callback signatures
7. [Sage introduction blog post](https://medium.com/nebo-15/introducing-sage-a-sagas-pattern-implementation-in-elixir-3ad499f236f6) -- Design rationale and composition patterns
8. [Prefect quickstart](https://docs.prefect.io/v3/get-started/quickstart) -- @flow/@task decorator patterns
9. [Prefect GitHub](https://github.com/PrefectHQ/prefect) -- 18k+ stars, Python workflow orchestration
10. [FreeAgent: Decoding Data Orchestration Tools](https://engineering.freeagent.com/2025/05/29/decoding-data-orchestration-tools-comparing-prefect-dagster-airflow-and-mage/) -- Comparative analysis of Prefect, Dagster, Airflow, Mage
11. [Dagster graphs documentation](https://docs.dagster.io/api/dagster/graphs) -- @op/@graph/@asset composition patterns
12. [Dagster asset definition docs](https://docs.dagster.io/guides/build/assets/defining-assets) -- Software-Defined Asset model
13. [dry-python returns GitHub](https://github.com/dry-python/returns) -- 4.2k stars, functional Python with Result/Maybe/IO
14. [returns Railway-Oriented Programming docs](https://returns.readthedocs.io/en/latest/pages/railway.html) -- flow(), bind(), lash() composition
15. [Cloudflare Python Workflows blog](https://blog.cloudflare.com/python-workflows/) -- Step decorator API, DAG dependencies
16. [Cloudflare Workflows testing blog](https://blog.cloudflare.com/better-testing-for-workflows/) -- Step-level mocking and introspection
17. [Akka saga patterns documentation](https://doc.akka.io/concepts/saga-patterns.html) -- Orchestrator vs choreography patterns
18. [Akka saga patterns blog (Part 1)](https://akka.io/blog/saga-patterns-in-akka-part-1-event-choreography) -- Event choreography implementation
19. [Workflow Orchestration Platforms comparison (2025)](https://procycons.com/en/blogs/workflow-orchestration-platforms-comparison-2025/) -- Kestra vs Temporal vs Prefect learning curves
20. [Instaclustr: Uber Cadence vs Netflix Conductor](https://www.instaclustr.com/blog/workflow-comparison-uber-cadence-vs-netflix-conductor/) -- Code-first vs JSON DSL comparison
21. [Pronovix: Eliminating API friction](https://pronovix.com/blog/eliminating-api-friction-along-downstream-developer-journey-1) -- Developer experience research on API adoption
22. [Temporal DX tips (Symphony.is)](https://medium.com/symphonyis/tips-for-a-better-developer-experience-with-temporal-9b2205ee0563) -- Practical Temporal developer experience advice
23. [AnyIO structured concurrency](https://mattwestcott.org/blog/structured-concurrency-in-python-with-anyio) -- TaskGroup patterns for async pipelines
24. [F# Railway-Oriented Programming](https://fsharpforfunandprofit.com/posts/recipe-part2/) -- Original ROP concept by Scott Wlaschin
