# P5: Grant Lifecycle Workflow

## Summary

State machine for grants with 8 states, transition history via join model, workflow metadata in schema for frontend-driven conditional button visibility, and auto-expiration.

## State Machine

```
discovered -> reviewed -> shortlisted -> applied -> awarded
                 |            |            |
                 v            v            v
              dismissed    dismissed    rejected

         any non-terminal  -----------> expired
```

**Terminal states** (no outgoing transitions): `awarded`, `rejected`, `dismissed`, `expired`

**Transition table:**

| From | To | Method | Access |
|------|----|--------|--------|
| discovered | reviewed | `review()` | AUTHENTICATED |
| reviewed | shortlisted | `shortlist()` | OWNER \| ROLE('admin') |
| reviewed | dismissed | `dismiss()` | OWNER \| ROLE('admin') |
| shortlisted | applied | `apply_grant()` | OWNER \| ROLE('admin') |
| shortlisted | dismissed | `dismiss()` | OWNER \| ROLE('admin') |
| applied | awarded | `award()` | ROLE('admin') |
| applied | rejected | `reject()` | ROLE('admin') |
| any non-terminal | expired | `expire()` | ROLE('admin') |

## Implementation

### New: `example_grants/models/grant_transition.py`

```python
class GrantTransition(ActorModel):
    __tablename__ = 'grant_transitions'
    __storable__ = True

    from_status: str
    to_status: str
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    note: Optional[str] = None
    transitioned_at: Optional[str] = None  # ISO timestamp
```

### Modified: `example_grants/models/grant.py`

Add state machine logic:

```python
GRANT_STATES = {
    'discovered': ['reviewed'],
    'reviewed': ['shortlisted', 'dismissed'],
    'shortlisted': ['applied', 'dismissed'],
    'applied': ['awarded', 'rejected'],
    'awarded': [],      # terminal
    'rejected': [],     # terminal
    'dismissed': [],    # terminal
    'expired': [],      # terminal
}
TERMINAL_STATES = {'awarded', 'rejected', 'dismissed', 'expired'}

class Grant(ActorModel):
    transitions: Optional[ListRef[GrantTransition]] = Field(default=[])

    def _transition(self, to_status, user=None, note=None):
        """Validate and execute state transition."""
        allowed = GRANT_STATES.get(self.status, [])
        if to_status not in allowed and to_status != 'expired':
            raise MethodError(f"Cannot transition from '{self.status}' to '{to_status}'", 400)
        if to_status == 'expired' and self.status in TERMINAL_STATES:
            raise MethodError(f"Cannot expire: already in terminal state '{self.status}'", 400)

        old = self.status
        Grant.update(self.id, {'status': to_status})

        # Record transition
        GrantTransition.create(GrantTransition(
            from_status=old, to_status=to_status,
            user_id=user.id if user else None,
            user_name=user.name if user else None,
            note=note,
            transitioned_at=datetime.now(timezone.utc).isoformat(),
        ))
        return json.dumps({"action": to_status, "from": old, "to": to_status})

    @expose_route('/review', methods=['POST'], access=AUTHENTICATED,
                  workflow={'from': ['discovered'], 'to': 'reviewed'})
    def review(self, user: User = None, note: str = None) -> str:
        return self._transition('reviewed', user, note)

    # ... shortlist, dismiss, apply_grant, award, reject, expire methods ...

    @classmethod
    def expire_overdue(cls):
        """Expire all grants past their deadline."""
        today = date.today().isoformat()
        overdue = cls.list(sql_filter=(
            f"deadline < ? AND status NOT IN ('awarded','rejected','dismissed','expired')",
            [today]
        ))
        # ... update each to expired ...
```

### Modified: `example_grants/main.py`

```python
from models import User, Grant, GrantTransition, Source, WebTools
models=[..., GrantTransition, ...]
join_models=[..., (Grant, GrantTransition)]
```

### Framework Enhancement: `@expose_route(workflow=...)`

**`src/n3tx/core/utils/decorators.py`** — Add `workflow` parameter (3 lines):
```python
def expose_route(route, methods=["POST"], access=None, workflow=None):
    def decorator(func):
        func.__endpoint__ = {'route': route, 'methods': methods, 'access': access}
        if workflow:
            func.__endpoint__['workflow'] = workflow
        return func
    return decorator
```

**`src/n3tx/core/models/proto_model.py`** — Propagate into schema (2 lines):
```python
if endpoint_info.get('workflow'):
    method_entry['workflow'] = endpoint_info['workflow']
```

Schema output:
```json
{
  "methods": {
    "review": {
      "route": "/review",
      "methods": ["POST"],
      "access": {"rule": "authenticated"},
      "workflow": {"from": ["discovered"], "to": "reviewed"}
    }
  }
}
```

### Frontend: Conditional Method Buttons

**`src/n3tx/static/components/ntx-item.js`** — In `#standaloneMethodsHtml()` and `sm()`:
```javascript
const workflow = def.ui?.workflow || def.workflow;
if (workflow?.from && !workflow.from.includes(this.value.status)) {
    continue; // skip — not applicable to current status
}
```

Methods without `workflow` metadata render as before (backward compatible).

## Tests

### `example_grants/tests/test_grant_lifecycle.py`

**TestValidTransitions** (~8 tests):
- discovered → reviewed, reviewed → shortlisted, reviewed → dismissed
- shortlisted → applied, shortlisted → dismissed
- applied → awarded, applied → rejected
- any non-terminal → expired

**TestInvalidTransitions** (~6 tests):
- Cannot review already-reviewed grant
- Cannot shortlist from discovered (skips step)
- Cannot apply from discovered
- Cannot transition from terminal states
- Cannot award from shortlisted (skips applied)

**TestTransitionABAC** (~7 tests):
- Unauthenticated cannot review (401)
- Regular user cannot award/reject (requires admin)
- Admin can award, reject
- Non-owner cannot shortlist
- Owner can shortlist their own
- Admin can shortlist any

**TestTransitionHistory** (~4 tests):
- Transition creates GrantTransition record
- Records user who performed transition
- Optional note preserved
- Multiple transitions build history

**TestGrantStatusAfterTransition** (~1 test):
- GET /grants/{id} shows new status after transition

**TestSchemaWorkflowMetadata** (~3 tests):
- Schema methods include workflow hints
- Schema has transitions field
- $defs include GrantTransition

**TestAutoExpiration** (~1 test):
- Grant.expire_overdue() transitions past-deadline grants

## Execution Order

```
Phase 1: Backend model layer (Day 1)
  - grant_transition.py (new)
  - grant.py (state machine, transition methods)
  - main.py (register GrantTransition, join model)
  - __init__.py (export)

Phase 2: Framework enhancement (Day 1, 30 min)
  - decorators.py (workflow param)
  - proto_model.py (propagate workflow)

Phase 3: Tests (Day 2)
  - conftest.py (updated seeds)
  - test_grant_lifecycle.py (all test classes)
  - seed.py (diverse lifecycle data)

Phase 4: Frontend (Day 3)
  - ntx-item.js (conditional method buttons)
  - Status badge CSS for new states
```

## Files Summary

**New files (2):**
- `example_grants/models/grant_transition.py`
- `example_grants/tests/test_grant_lifecycle.py`

**Modified files (7):**
- `example_grants/models/grant.py`
- `example_grants/models/__init__.py`
- `example_grants/main.py`
- `example_grants/seed.py`
- `example_grants/tests/conftest.py`
- `src/n3tx/core/utils/decorators.py`
- `src/n3tx/core/models/proto_model.py`
- `src/n3tx/static/components/ntx-item.js`
