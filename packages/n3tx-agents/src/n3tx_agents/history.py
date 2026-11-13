"""Agent history policy and full SDK codec for canonical TTX storage.

API: create_history declares a protected agent root; get_history and
authorize_history reload it under native owner/admin policy; chat_history
decodes complete incoming SDK dictionaries in insertion order.

Boundary: scope is immutable nullable metadata, never a business permission
grant. Retained history does not depend on a surviving business record.
Execution adapters separately enforce callee and application permissions.
Register TTX only; generic TTX access policy remains unchanged."""

from pydantic_ai.messages import ModelMessagesTypeAdapter

from n3tx_actors.actor import Actor
from n3tx_actors.tx import TX
from n3tx_core.authorize import AccessContext, OWNER, ROLE
from n3tx_core.models.ref import Ref, local_ref_id, public_id_url
from n3tx_threads import TTX

from .utils import _agent_addr, _caller_user


HISTORY_CODEC = "pydantic-ai/v1"
_HISTORY_ACCESS = OWNER | ROLE("admin")


def _scope_ref(scope: Ref | None) -> Ref | None:
    """Validate nullable canonical local metadata without reading its target."""
    if scope is None:
        return None
    # 0. Reject remote, numeric and noncanonical identifiers without I/O.
    reference = Ref(scope)
    ident = local_ref_id(reference)
    if (
        type(ident) is not int or not 0 < ident <= 2**63 - 1
        or Ref.id(reference) != str(ident) or str(scope) != str(reference)
    ):
        raise ValueError("History scope must be a canonical local reference")
    return reference


def authorize_history(
    ttx: TTX, *, user, action: str = "read", scope: Ref | None = None,
) -> TTX:
    """Reload an agent root and apply private owner/admin history policy.

    A non-null supplied scope asserts equality, never rebinding. Callers needing
    an explicit null assertion compare the returned data.scope themselves.
    None callers retain trusted native semantics; DM roots never qualify."""
    # 0. Saved declaration and explicit scope presence distinguish agent roots.
    if not isinstance(ttx, TTX) or ttx.id <= 0:
        raise ValueError("History requires a saved TTX owner")
    owner = TTX.get(ttx.id, archived=True)
    if owner is None:
        raise ValueError("History owner is unavailable")
    if owner.meta.get("agent_history") is not True or "scope" not in owner.data:
        raise ValueError("TTX is not an agent history root")
    binding = _scope_ref(owner.data["scope"])
    if scope is not None and _scope_ref(scope) != binding:
        raise ValueError("History scope does not match")
    # 1. Use native rules without granting admins access to generic TTX/DMs.
    if action not in {"read", "update", "delete", "list"}:
        raise ValueError("Unsupported history action")
    caller = _caller_user(user)
    if caller is not None:
        if not isinstance(caller, dict):
            raise TypeError("Caller must be a native identity mapping")
        context = AccessContext(
            user=caller, action=action, model_class=TTX, resource=owner,
        )
        if not _HISTORY_ACCESS.evaluate(context):
            raise PermissionError("Access denied for agent history")
    return owner


def get_history(ttx_ref: str, *, user, action: str = "read") -> TTX:
    """Resolve one exact local /TTX/id URL and authorize its saved root."""
    # 0. A public handle is never an integer or an alias into another table.
    if not isinstance(ttx_ref, str) or not ttx_ref:
        raise ValueError("A canonical TTX reference is required")
    reference = Ref(ttx_ref)
    ident = local_ref_id(reference, target_cls=TTX)
    if (
        type(ident) is not int or not 0 < ident <= 2**63 - 1
        or ttx_ref != public_id_url(ident, target_cls=TTX)
    ):
        raise ValueError("A canonical local TTX reference is required")
    owner = TTX.get(ident, archived=True)
    if owner is None:
        raise ValueError("History owner is unavailable")
    return authorize_history(owner, user=user, action=action)


def create_history(target, *, user, scope: Ref | None = None) -> TTX:
    """Create one declared root with actual actor and caller attribution."""
    from .threaded_mixin import current_execution

    # 0. Validate metadata and identity before any storage write.
    binding = _scope_ref(scope)
    caller = _caller_user(user)
    if caller is not None and not isinstance(caller, dict):
        raise TypeError("Caller must be a native identity mapping")
    user_id = caller.get("user_id") if caller is not None else None
    if caller is not None and (type(user_id) is not int or user_id <= 0):
        raise PermissionError("An authenticated caller is required")
    router = Actor.root()
    if router is None:
        raise RuntimeError("No Matrix root is available")
    active = current_execution.get()
    source = (
        f"ttx/{active.id}" if active is not None
        else f"users/{user_id}" if user_id is not None else router.addr
    )
    cls = target if isinstance(target, type) else type(target)
    # 1. The declaration is written only by this trusted server creation path.
    return TTX.create(TTX.from_tx(TX(
        "AGENTIC", source, _agent_addr(target, cls),
        data={"scope": binding}, meta={"agent_history": True},
    ), user_owner=user_id))


def chat_history(ttx: TTX) -> list:
    """Decode full incoming codec messages; callers own access authorization."""
    # 0. Require a saved owner, but do not silently mutate or repair evidence.
    if not isinstance(ttx, TTX) or ttx.id <= 0:
        raise ValueError("History requires a saved TTX owner")
    if TTX.get(ttx.id, archived=True) is None:
        raise ValueError("History owner is unavailable")
    records = TTX.list(
        where={"target": f"ttx/{ttx.id}"}, order_asc="id", archived=True,
    )
    # 1. Insertion order preserves checkpoints independently of event clocks.
    return list(ModelMessagesTypeAdapter.validate_python([
        record.data for record in records
        if record.meta.get("codec") == HISTORY_CODEC
    ]))


# Changelog (Python has no block-comment syntax).
# - 2026-11-11: Centralize TTX-only agent root policy and full SDK decoding;
#   preserve nullable scope, owner/admin access and deleted-source audits.
