"""Exercise reserved caller injection through real local Matrix requests.

Synthetic actions cover metadata authority, detached identity dictionaries,
native SQLite caller lookup, descriptor scopes, and unchanged raw handlers.
These internal requests do not claim HTTP authentication or policy parity."""

from copy import deepcopy
from queue import Empty

import pytest
from pydantic import PrivateAttr

from n3tx_actors.actor import Actor
from n3tx_actors.matrix import Matrix
from n3tx_actors.models.actor_model import ActorModel
from n3tx_actors.tx import TX
from n3tx_core import config
from n3tx_core.authorize import ROLE
from n3tx_core.models import proto_dump
from n3tx_core.models.proto_model import ProtoModel
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_core.utils import materialize, registrar
from n3tx_core.utils.decorators import expose_route

pytestmark = pytest.mark.asyncio


class CallerIdentity(ProtoModel):
    """Synthetic concrete storable caller, with no authentication services."""

    __storable__ = True
    __tablename__ = 'caller_injection_identities'
    name: str
    role: str = 'staff'


class RecordingMatrix(Matrix, auto_register=False):
    """Observe correlated replies without replacing routing or request logic."""

    _replies: list = PrivateAttr(default_factory=list)

    async def inbox(self, tx):
        """Record replies before native correlation consumes them."""
        if tx.meta.get('req'):
            self._replies.append(tx)
        await super().inbox(tx)


@pytest.fixture
def caller_boundary(tmp_path, monkeypatch):
    """Isolate synthetic registration, caller storage, config, and routing."""
    # 0. Keep process-wide registries and configuration local to this test.
    monkeypatch.setattr(config, 'DEBUG', False)
    monkeypatch.setattr(registrar, 'registered_models', {})
    monkeypatch.setattr(ProtoModel, '_schema_cache', {})
    monkeypatch.setattr(proto_dump, '_schema_url_cache', {})
    monkeypatch.setattr(proto_dump, '_instance_url_cache', {})
    monkeypatch.setattr(materialize, '_materializers', [])
    monkeypatch.setattr(CallerIdentity, 'storage', None)
    root = RecordingMatrix(addr='caller_boundary')
    Actor.root(root)
    calls = []
    # 1. Declare only synthetic action targets against the isolated root.

    class CallerActions(ActorModel, auto_register=False):
        """Synthetic domain actions expose the caller actually received."""

        __storable__ = True
        __tablename__ = 'caller_injection_actions'
        name: str

        @staticmethod
        @expose_route('/dictionary')
        def dictionary(user: dict):
            """Mutate a nested caller to expose shallow-copy regressions."""
            calls.append(user)
            before = deepcopy(user)
            if user is not None:
                user['nested']['roles'].append('action-local')
            return {'caller': before}

        @classmethod
        @expose_route('/typed')
        def typed(cls, user: CallerIdentity):
            """Return the native caller row, not the supplied body identity."""
            calls.append(user)
            return {
                'id': user.id,
                'name': user.name,
                'role': user.role,
                'native': isinstance(user, CallerIdentity),
            }

        @expose_route('/instance')
        def instance(self, user: dict):
            """Report both the resolved target row and trusted caller."""
            calls.append(user)
            return {'id': self.id, 'caller': user}

        @staticmethod
        @expose_route('/asynchronous')
        async def asynchronous(user: dict):
            """Report caller identity from an awaited exposed action."""
            calls.append(user)
            return {'caller': user}

        @staticmethod
        @expose_route('/without_user')
        def without_user(value: str):
            """Accept ordinary arguments without a caller parameter."""
            calls.append(value)
            return {'value': value}

        @staticmethod
        @expose_route('/kwargs_only')
        def kwargs_only(**kwargs):
            """Expose unexpected identity injection into arbitrary kwargs."""
            calls.append(kwargs)
            return kwargs

        @classmethod
        @expose_route('/restricted', access=ROLE('admin'))
        def restricted(cls, user: CallerIdentity):
            """Record execution only after the existing method access gate."""
            calls.append(user)
            return {'id': user.id}

        @classmethod
        def RAW(cls, data, tx):
            """Preserve the ordinary unexposed data/envelope convention."""
            calls.append((data, tx))
            return {'body': data, 'metadata': tx.meta}
    # 2. Register native storage against one disposable file and seed callers.
    storage = SQLiteStorage(str(tmp_path / 'caller-boundary.sqlite'))
    try:
        registrar.register_model(CallerIdentity, storage)
        registrar.register_model(CallerActions, storage)
        root.register(CallerActions)
        caller = CallerIdentity.create(CallerIdentity(name='Metadata caller'))
        spoof = CallerIdentity.create(CallerIdentity(name='Body caller'))
        target = CallerActions.create(CallerActions(name='Target row'))
        yield root, CallerActions, caller, spoof, target, calls
    finally:
        # 3. Close only this fixture's pool; conftest restores Actor.root.
        while True:
            try:
                storage._pool.get_nowait().close()
            except Empty:
                break


async def request_once(boundary, name, data, meta):
    """Require exactly one correlated native response and no pending request."""
    # 0. Arrange a native envelope and a reply observation boundary.
    root, model, *_ = boundary
    tx = TX(
        name=name, source=root.addr, target=model.__tablename__,
        data=data, meta=meta,
    )
    before = len(root._replies)
    # 1. Use inherited request routing and correlation without mocks.
    response = await root.request(tx, timeout=1)
    # 2. Require one reply, not merely one resolved future.
    assert root._replies[before:] == [response]
    assert response.meta['req'] == tx.uuid
    assert tx.uuid not in root._pending
    return response


async def test_dictionary_caller_is_detached_and_body_is_ignored(
    caller_boundary,
):
    """Nested action mutations cannot alter trusted metadata or body data."""
    # 0. Arrange conflicting nested identities.
    identity = {
        'user_id': 41, 'role': 'staff', 'nested': {'roles': ['staff']},
    }
    body = {'user': {'user_id': 99, 'nested': {'roles': ['admin']}}}
    original_meta = deepcopy(identity)
    original_body = deepcopy(body)
    # 1. Exercise the real Matrix action path.
    response = await request_once(
        caller_boundary, 'dictionary', body, {'user': identity},
    )
    # 2. Assert metadata authority and deep detachment.
    assert not response.is_error, response.data
    assert response.data == {'caller': original_meta}
    assert identity == original_meta
    assert body == original_body
    received = caller_boundary[-1][0]
    assert received is not identity
    assert received['nested']['roles'] == ['staff', 'action-local']


async def test_storable_caller_loads_metadata_id_from_sqlite(caller_boundary):
    """Concrete caller annotations hydrate the metadata ID's saved row."""
    # 0. Arrange a conflicting saved body identity and stale JWT attributes.
    _, _, caller, spoof, _, calls = caller_boundary
    meta = {'user': {'user_id': caller.id, 'role': 'stale-token-role'}}
    # 1. Exercise native storable materialization through Matrix.
    response = await request_once(
        caller_boundary, 'typed', {'user': {'id': spoof.id}}, meta,
    )
    # 2. Assert the stored row, rather than body or token attributes, wins.
    assert not response.is_error, response.data
    assert response.data == {
        'id': caller.id, 'name': 'Metadata caller',
        'role': 'staff', 'native': True,
    }
    assert len(calls) == 1
    assert isinstance(calls[0], CallerIdentity)
    assert meta['user']['role'] == 'stale-token-role'


async def test_deleted_caller_returns_403_without_execution(caller_boundary):
    """A missing metadata caller cannot fall back to a valid body caller."""
    # 0. Delete the authenticated row but retain a valid spoof target.
    _, _, caller, spoof, _, calls = caller_boundary
    CallerIdentity.delete(caller.id)
    assert CallerIdentity.get(caller.id) is None
    # 1. Request the typed action with the now-stale metadata ID.
    response = await request_once(
        caller_boundary, 'typed', {'user': {'id': spoof.id}},
        {'user': {'user_id': caller.id}},
    )
    # 2. Assert a correlated forbidden error with no action side effect.
    assert response.is_error
    assert response.data['code'] == 403
    assert calls == []


@pytest.mark.parametrize('meta', [{}, {'user': None}, {'user': {}}])
async def test_missing_caller_injects_none(caller_boundary, meta):
    """Absent caller metadata never promotes a body identity."""
    # 0. Arrange a body that would be usable as a caller dictionary.
    body = {'user': {'user_id': 99, 'nested': {'roles': ['admin']}}}
    # 1. Invoke an action with a required named caller parameter.
    response = await request_once(caller_boundary, 'dictionary', body, meta)
    # 2. Assert None injection, not authentication or body fallback.
    assert not response.is_error, response.data
    assert response.data == {'caller': None}
    assert caller_boundary[-1] == [None]


@pytest.mark.parametrize('name', ['without_user', 'kwargs_only'])
async def test_no_named_user_drops_reserved_body_argument(
    caller_boundary, monkeypatch, name,
):
    """Neither explicit non-user parameters nor **kwargs receive identity."""
    # 0. Observe generic materialization without replacing native dispatch.
    materialized = []

    def observe(value, expected_type, *, user=None, context=None):
        """Record which ordinary typed parameters reach materializers."""
        materialized.append(context['param'])
        return False, value

    monkeypatch.setattr(materialize, '_materializers', [observe])
    body = {'value': 'kept', 'user': 'reserved-body-identity'}
    # 1. Exercise methods that never explicitly declare user.
    response = await request_once(
        caller_boundary, name, body, {'user': {'user_id': 41}},
    )
    # 2. Assert ordinary kwargs survive, reserved user is never materialized.
    assert not response.is_error, response.data
    assert response.data == {'value': 'kept'}
    assert 'user' not in materialized
    assert materialized == (['value'] if name == 'without_user' else [])
    assert body['user'] == 'reserved-body-identity'


@pytest.mark.parametrize('name', ['instance', 'asynchronous'])
async def test_instance_and_async_actions_receive_metadata(
    caller_boundary, name,
):
    """Instance resolution and awaited actions preserve caller injection."""
    # 0. Arrange a saved target row and a conflicting body caller.
    _, _, caller, spoof, target, calls = caller_boundary
    identity = {'user_id': caller.id, 'role': 'staff'}
    body = {'user': {'user_id': spoof.id}}
    if name == 'instance':
        body['id'] = target.id
    # 1. Exercise descriptor-aware action dispatch.
    response = await request_once(
        caller_boundary, name, body, {'user': identity},
    )
    # 2. Assert the same authoritative identity reaches either scope.
    assert not response.is_error, response.data
    assert response.data['caller'] == identity
    assert calls == [identity]
    assert calls[0] is not identity
    if name == 'instance':
        assert response.data['id'] == target.id


async def test_access_denial_precedes_caller_lookup(
    caller_boundary, monkeypatch,
):
    """Existing method access checks deny before lookup or action execution."""
    # 0. Arrange denied metadata and an admin body spoof.
    calls = caller_boundary[-1]
    lookups = []

    def record_lookup(cls, entity_id):
        """Expose any caller lookup occurring before access denial."""
        lookups.append(entity_id)
        return None

    monkeypatch.setattr(CallerIdentity, 'get', classmethod(record_lookup))
    # 1. Invoke the protected method with a non-admin metadata role.
    response = await request_once(
        caller_boundary, 'restricted',
        {'user': {'user_id': 99, 'role': 'admin'}},
        {'user': {'user_id': 41, 'role': 'staff'}},
    )
    # 2. Assert the existing gate remains metadata-based and runs first.
    assert response.is_error
    assert response.data['code'] == 403
    assert response.data['message'] == 'Access denied'
    assert lookups == []
    assert calls == []


async def test_nonexposed_handler_keeps_data_and_tx(caller_boundary):
    """Raw handlers retain body user as data, not as an injected argument."""
    # 0. Arrange distinct body and trusted metadata identities.
    body = {'user': {'user_id': 99}, 'value': 'raw'}
    meta = {'user': {'user_id': 41}}
    # 1. Exercise the unexposed (data, tx) dispatch branch.
    response = await request_once(caller_boundary, 'RAW', body, meta)
    # 2. Assert the original objects reach the ordinary handler unchanged.
    assert not response.is_error, response.data
    assert response.data == {'body': body, 'metadata': meta}
    data, tx = caller_boundary[-1][0]
    assert data is body
    assert tx.data is body
    assert tx.meta is meta


# Changelog
# - 2026-11-09: Cover Matrix caller injection and native SQLite lookup with
#   isolated synthetic models, reserved body inputs, and correlated replies.
