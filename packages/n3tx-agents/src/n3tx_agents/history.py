"""Open parent-authorized conversations and decode exact SDK message evidence.

Thread is the semantic Python shape of a TTX conversation root. Only TTX
identities are persisted. Parent policy grants access, never root attribution
or agent provenance. Provider-context repair belongs to execution, not reads."""

from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter

from n3tx_actors.tx import TX
from n3tx_core.authorize import AccessContext, DefaultResolver
from n3tx_core.models.proto_model import ProtoModel
from n3tx_core.models.ref import Ref, local_ref_id, public_id_url
from n3tx_core.utils.registrar import registered_models
from n3tx_threads import Thread, TTX

from .utils import _normalize_user


def _authorize_owner(
    scope: Ref, *, user: dict | None, actions: tuple[str, ...],
) -> ProtoModel:
    """Resolve a saved local owner and apply its current native action rules.

    Remote, ambiguous, unregistered and TTX owners are unsupported. References
    are canonicalized through native helpers; no graph traversal takes place.
    Invalid ownership raises ValueError; native access denials propagate."""
    # 0. Resolve one registered class without hydrating remote references.
    scope = Ref(scope)
    candidates = {
        model for model in registered_models.values()
        if model.__name__ == Ref.schema(scope)
    }
    if len(candidates) != 1:
        raise ValueError("Conversation scope must name one registered model")
    model = candidates.pop()
    if (
        not issubclass(model, ProtoModel)
        or issubclass(model, TTX)
        or not getattr(model, '__storable__', False)
        or getattr(model, 'storage', None) is None
    ):
        raise ValueError("Conversation scope needs a stored business owner")
    owner_id = local_ref_id(scope, target_cls=model)
    if type(owner_id) is not int or owner_id <= 0:
        raise ValueError("Conversation scope must identify a local saved row")
    owner = model.get(owner_id)
    if owner is None:
        raise ValueError("Conversation owner is unavailable")
    # 1. Recheck policy against persisted owner state, including anonymous use.
    caller = _normalize_user(user)
    resolver = DefaultResolver()
    for action in actions:
        resolver.authorize(AccessContext(
            user=caller, action=action, model_class=model, resource=owner,
        ))
    return owner


def _authorize_thread(
    thread: Thread, *, user: dict | None, action: str,
) -> Thread:
    """Reload the exact conversation and authorize its unchanged parent.

    The supplied root retains the expected target. Deleted, renamed or
    retargeted roots fail closed; attribution and source never grant access.
    Update checkpoints require both parent read and update permissions. Checks
    and subsequent storage operations are not an atomic transaction."""
    # 0. Bind the fresh root to the prepared conversation and expected owner.
    if type(thread.id) is not int or thread.id <= 0:
        raise ValueError("Conversation root must be saved")
    current = Thread.get(thread.id)
    if current is None or current.name != 'Conversation':
        raise ValueError("Conversation root is unavailable")
    if thread.name != 'Conversation' or current.target != thread.target:
        raise ValueError("Conversation owner changed")
    # 1. Resolve current parent policy without traversing another TTX root.
    actions = ('read', 'update') if action == 'update' else (action,)
    owner = _authorize_owner(current.target, user=user, actions=actions)
    if current.target != public_id_url(owner.id, target_cls=type(owner)):
        raise ValueError("Conversation owner must use its canonical reference")
    return current


def open_thread(
    *, scope: Ref, agent_addr: str, user: dict | None,
    thread_id: int | None = None,
) -> Thread:
    """Create a conversation or resume its exact ID under a saved owner.

    Read and update permission are required before creation or history access.
    An existing root must name the expected canonical owner; another agent may
    resume it explicitly. The source records creation provenance only."""
    # 0. Authorize the current business owner before any history access.
    caller = _normalize_user(user)
    owner = _authorize_owner(
        scope, user=caller, actions=('read', 'update'),
    )
    target = public_id_url(owner.id, target_cls=type(owner))
    # 1. Resume exactly the requested root, never silently create a replacement.
    if thread_id is not None:
        if type(thread_id) is not int or thread_id <= 0:
            raise ValueError("Conversation ID must be a positive integer")
        thread = Thread.get(thread_id)
        if thread is None or thread.name != 'Conversation':
            raise ValueError("Conversation root is unavailable")
        if thread.target != target:
            raise ValueError("Conversation belongs to a different owner")
        return thread
    # 2. Store only the semantic root and trusted appender attribution.
    return Thread.create(Thread(
        TX('Conversation', agent_addr, target, data=None),
        user_owner=caller.get('user_id'),
    ))


def read_history(
    thread: Thread, *, user: dict | None,
) -> list[ModelMessage]:
    """Decode direct Message children without repairing or mutating evidence.

    The single unbounded query orders only by timestamp, without an ID
    tie-breaker or snapshot guarantee. Denials and invalid payloads propagate.
    Unrelated entry names and grandchildren are not conversation history."""
    # 0. Authorize the current root and parent before selecting SDK evidence.
    current = _authorize_thread(thread, user=user, action='read')
    rows = TTX.list(
        where={
            'target': public_id_url(current.id, target_cls=TTX),
            'name': 'Message',
        },
        order_asc='timestamp',
    )
    # 1. Restore exact typed messages without provider-context repair.
    return list(ModelMessagesTypeAdapter.validate_python([
        row.value for row in rows
    ]))


# Changelog (Python has no block-comment syntax).
# - 2026-11-04: Replace codecs with parent-authorized TTX conversations and
#   direct timestamp-ordered Message history; recheck saved root ownership.
# - 2026-11-02: Separate agent history decoding from generic Thread storage.
