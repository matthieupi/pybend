# Handoff — N3TX ERROR Terminal Semantics Follow-up

Generated: 2026-06-28 23:26:03 UTC
Session focus: Follow-up bug report for the N3TX team after validating that the current ERROR recursion fix is incomplete.

## ✅ Executive Snapshot

- The N3TX 0.11.3-side fix appears to only stop recursive forwarding when an `ERROR` handler **raises**.
- The production bug still reproduces when an `ERROR` handler **succeeds and returns a value**: the actor system sends `ERROR_RESPONSE` back to the original remote source.
- That `ERROR_RESPONSE` targets the id-less remote class actor `n3tx://compute/Process`, causing `RemoteMatrix` to fail with `Remote target requires an id for ERROR: n3tx://compute/Process` and recurse.
- Correct invariant: **incoming `tx.is_error` handlers are terminal catch handlers. Invoke them for side effects, then ignore the return value and never reply.**
- Required fix applies to both base `Actor.handler()` and `ActorModel.handler()`.

## 🎯 Requested Framework Fix

When any actor receives a TX where `tx.is_error` is true:

1. If the actor has a matching handler, including `ERROR`, invoke it so application actors can catch and record the failure.
2. If the handler raises, log and return. Do not generate another `ERROR`.
3. If the handler returns successfully, **ignore the return value and return**.
4. Never emit `tx.reply(...)`, `ERROR_RESPONSE`, `tx.exception(...)`, stream chunks, or any outbound TX in response to an incoming error envelope.

## 🔎 Validation Evidence From App Side

Runtime still shows repeated warnings after `GENERATE()` → `STOP()` → `STOP()` → `GENERATE()`:

```text
RemoteMatrix request failed for n3tx://compute/Process: Remote target requires an id for ERROR: n3tx://compute/Process
...
ERROR: n3tx.actors: [scenes_tasks] Error in ERROR: maximum recursion depth exceeded
```

Local semantic probe against the current checkout also confirms the gap:

```python
class Catcher(Actor, auto_register=False):
    __addr__ = 'catcher'

    @classmethod
    def ERROR(cls, data, tx):
        cls.caught = data
        return {'handled': True}
```

Observed result:

```text
sent_count=1
sent=ERROR_RESPONSE target=n3tx://compute/Process meta={'error': True, 'req': '...'}
```

Expected result:

```text
sent_count=0
```

## 💻 Implementation Sketch

### `n3tx_actors/actor.py`

After invoking the handler and before normal response dispatch:

```python
if asyncio.iscoroutine(result):
    result = await result

if tx.is_error:
    return

# normal reply/TX/dict/result dispatch continues for non-error TXs
```

Also preserve the exception-path guard:

```python
except Exception as exc:
    logger.error(...)
    if tx.is_error:
        return
    await target.send(tx.exception(exc))
    return
```

### `n3tx_actors/models/actor_model.py`

Apply the same terminal guard in the custom/exposed method path after coroutine resolution and before streaming/result dispatch:

```python
if asyncio.iscoroutine(result):
    result = await result

if tx.is_error:
    return

if inspect.isasyncgen(result):
    ...
```

For CRUD dispatch, a defensive `if tx.is_error: return` before dispatching CRUD results is acceptable, but ordinary CRUD names should not normally be error envelopes.

## 🧪 Required Tests

Add tests that cover successful `ERROR` handlers, not only failing handlers.

### Base Actor: successful ERROR handler is terminal

```python
async def test_actor_error_handler_return_value_is_not_replied():
    sent = []

    class Catcher(Actor, auto_register=False):
        __addr__ = 'catcher'

        @classmethod
        def ERROR(cls, data, tx):
            cls.caught = data
            return {'handled': True}

        @classmethod
        async def send(cls, tx):
            sent.append(tx)

    await Catcher.inbox(TX(
        name='ERROR',
        source='n3tx://compute/Process',
        target='catcher',
        data={'message': 'boom'},
        meta={'error': True},
    ))

    assert Catcher.caught['message'] == 'boom'
    assert sent == []
```

### ActorModel: successful exposed ERROR handler is terminal

```python
async def test_actormodel_error_handler_return_value_is_not_replied():
    sent = []

    class CatcherModel(ActorModel):
        __tablename__ = 'catcher_models'
        __storable__ = False

        @classmethod
        def ERROR(cls, data, tx):
            cls.caught = data
            return {'handled': True}

        @classmethod
        async def send(cls, tx):
            sent.append(tx)

    await CatcherModel.inbox(TX(
        name='ERROR',
        source='n3tx://compute/Process',
        target='catcher_models',
        data={'message': 'boom'},
        meta={'error': True},
    ))

    assert CatcherModel.caught['message'] == 'boom'
    assert sent == []
```

### Regression shape

Also add a test where `ERROR` handler returns a Pydantic model, `TX`, string, and `None` if practical. All should produce no outbound reply when `tx.is_error` is true.

## ✅ Definition of Done

- `ERROR` handlers remain catchable and can update actor/application state.
- Successful `ERROR` handlers emit no reply.
- Failing `ERROR` handlers emit no nested error.
- Normal non-error handler responses are unchanged.
- `RemoteMatrix` no longer logs repeated `Remote target requires an id for ERROR: n3tx://compute/Process` after the app's `GENERATE()`/`STOP()`/`STOP()`/`GENERATE()` path.

## 📚 Related Artifact

- `/workspace/.project/handoffs/handoff-20260628-213910.md` — original comprehensive handoff describing the production failure, actor catch intent, and first recommended fix.

## 🔐 Sensitive Content Handling

No secrets or credentials are included. Service names and local actor refs are non-secret runtime identifiers.
