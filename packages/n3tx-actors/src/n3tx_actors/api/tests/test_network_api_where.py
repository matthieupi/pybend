"""Exercise where through real actor HTTP, TX dispatch and SQLite."""

import json
from typing import ClassVar

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import Field, PrivateAttr, computed_field

from n3tx_actors.api.auth_interceptor import auth_interceptor
from n3tx_actors.api.network_api import NetworkAPI, create_api_routes
from n3tx_actors.matrix import Matrix
from n3tx_actors.models.actor_model import ActorModel
from n3tx_actors.tx import TX
from n3tx_core.authorize import Where
from n3tx_core.storage.sqlite_storage import SQLiteStorage

pytestmark = pytest.mark.unit


@pytest.fixture
def actor_where(tmp_path):
    """Wire the native actor boundary using only disposable synthetic rows."""
    # 0. The local autouse fixture restores global Actor and Matrix state.
    root = Matrix()

    class WhereActor(ActorModel, auto_register=False):
        """Declare searchable columns and a trusted collection restriction."""

        __tablename__: ClassVar[str] = 'actor_where_rows'
        __storable__: ClassVar[bool] = True
        __access__: ClassVar[dict] = {
            'list': Where(visible=True, excluded='secret'),
            'read': Where(visible=True, excluded='secret'),
        }
        __hidden_fields__: ClassVar[set] = {'hidden'}
        __protected_fields__: ClassVar[set] = {
            'protected', 'hidden', 'excluded',
        }
        name: str = ''
        score: int = 0
        visible: bool = True
        excluded: str = Field(default='secret', exclude=True)
        conditional: str = Field(default='secret', exclude_if=lambda v: True)
        hidden: str = 'secret'
        protected: str = 'secret'
        aliased: str = Field(default='text', alias='external_name')
        payload: list[str] = Field(default_factory=list)
        _private: str = PrivateAttr(default='secret')

        @computed_field
        @property
        def computed(self) -> str:
            """Expose a derived value that is not a stored query column."""
            return self.name

        def describe_secret(self) -> str:
            """Provide a method that public queries must not resolve."""
            return self.excluded

    backend = SQLiteStorage(database=str(tmp_path / 'actor-where.db'))
    WhereActor.set_storage(backend)
    backend.create_table(WhereActor)
    for name, score, visible in (
        ('A%_B', 30, True), ('A%_B', 10, True), ('A%_B', 20, True),
        ('a%_b', 40, True), ('AxxB', 50, True), ('A%_B', 0, False),
    ):
        WhereActor.create(WhereActor(
            name=name, score=score, visible=visible, protected=f'p{score}',
        ))
    root.register(WhereActor)
    adapter = NetworkAPI()
    root.register(adapter)
    adapter.use(auth_interceptor, on='request')
    app = FastAPI()
    app.include_router(create_api_routes(
        adapter, {'actor_where_rows': WhereActor},
    ))
    # 1. Use an in-process client, never a server or remote provider.
    try:
        with TestClient(app) as client:
            yield client, WhereActor
    finally:
        while not backend._pool.empty():
            backend._pool.get_nowait().close()


@pytest.mark.parametrize('path', ['/actor_where_rows', '/WhereActor/_'])
def test_actor_where_intersects_policy_before_order_and_pages(
    actor_where, path,
):
    """Preserve literal matching, AND conditions and policy-filtered totals."""
    # 0. Match exact case and literal wildcard characters with another bound.
    client, _ = actor_where
    params = {
        'where': json.dumps({'name__contains': 'A%_', 'score__gte': 10}),
        'order_asc': 'score', 'limit': 2,
    }
    # 1. Traverse HTTP decoding, Matrix, ActorModel and native storage.
    first = client.get(path, params=params)
    last = client.get(path, params={**params, 'offset': 2})
    denied = client.get(path, params={'where': '{"visible": false}'})
    # 2. Case/wildcard decoys and denied records cannot affect the page set.
    assert first.status_code == last.status_code == denied.status_code == 200
    assert [row['score'] for row in first.json()['data']] == [10, 20]
    assert [row['score'] for row in last.json()['data']] == [30]
    assert first.json()['meta'] == {
        'total': 3, 'limit': 2, 'offset': 0, 'has_more': True,
    }
    assert last.json()['meta'] == {
        'total': 3, 'limit': 2, 'offset': 2, 'has_more': False,
    }
    assert denied.json() == []


@pytest.mark.parametrize('path', ['/actor_where_rows', '/WhereActor/_'])
@pytest.mark.parametrize(
    'where',
    ['{', 'null', '[]', '"name"', '{"missing": 1}',
     '{"name__like": "x"}', '{"name__in": "abc"}',
     '{"name": ["x"]}', '{"name__contains": 1}',
     '{"score__contains": "1"}', '{"payload__contains": "x"}',
     '{"name__contains OR 1=1 --": "x"}',
     '{"name; DROP TABLE actor_where_rows": "x"}'],
)
def test_actor_http_invalid_where_returns_422(actor_where, path, where):
    """Reject decoder and compiler failures without changing stored rows."""
    # 0. Send malformed or unsupported filters through the real HTTP route.
    client, model = actor_where
    response = client.get(path, params={'where': where})
    # 1. Actor errors must translate to structured client errors, not 500s.
    assert response.status_code == 422
    assert response.json()['detail']
    assert len(model.list()) == 6


def test_actor_http_where_values_are_bound(actor_where):
    """SQL-looking user values cannot bypass the actor list policy."""
    # 0. Submit a value that would expose all rows if interpolated as SQL.
    client, model = actor_where
    response = client.get('/actor_where_rows', params={
        'where': json.dumps({'name': "' OR 1=1 --"}),
    })
    # 1. No value matches, and all data remains intact.
    assert response.status_code == 200
    assert response.json() == []
    assert len(model.list()) == 6


def test_actor_raw_list_forwards_decoded_where(actor_where):
    """Internal LIST accepts a dict while keeping trusted SQL restrictions."""
    # 0. Raw TX callers supply their own trusted authorization predicate.
    _, model = actor_where
    tx = TX(
        name='LIST', source='test', target=model.addr,
        data={'where': {'score__in': [0, 10, 20]}, 'order_desc': 'score'},
        meta={'sql_filter': ('visible = ?', [True])},
    )
    # 1. The CRUD adapter must forward the decoded dict to the native mixin.
    result = model.handler_crud(tx)
    # 2. Both predicates apply even without an HTTP request interceptor.
    assert [row['score'] for row in result] == [20, 10]


def test_actor_omitted_where_preserves_legacy_override(
    actor_where, monkeypatch,
):
    """Do not add absent where kwargs to historical application overrides."""
    # 0. Install the exact pre-where public list signature.
    client, model = actor_where
    calls = []

    def legacy_list(cls, sql_filter=None, limit=None, offset=None,
                    populate=None, ids=None):
        """Capture trusted SQL and pagination without new keyword support."""
        calls.append((cls, sql_filter, limit, offset))
        return []

    monkeypatch.setattr(model, 'list', classmethod(legacy_list))
    # 1. Exercise omission through both actor transport layers.
    response = client.get('/actor_where_rows?limit=2&offset=1')
    # 2. Preserve legacy behavior and the interceptor's trusted policy.
    assert response.status_code == 200
    assert calls == [(
        model,
        ('"actor_where_rows"."visible" = ? AND '
         '"actor_where_rows"."excluded" = ?', [True, 'secret']),
        2, 1,
    )]


@pytest.mark.parametrize('mode', ['where', 'order_asc', 'order_desc'])
@pytest.mark.parametrize(
    'field',
    ['excluded', 'conditional', 'hidden', '_private',
     '__dict__', 'name__class__', 'describe_secret', 'computed',
     'external_name', 'name" OR 1=1 --'],
)
def test_actor_public_queries_cannot_probe_secrets(actor_where, mode, field):
    """Reject public secret probes through both list query mechanisms."""
    # 0. Caller-supplied flags cannot select trusted policy compilation.
    client, model = actor_where
    value = json.dumps({field: 'secret'}) if mode == 'where' else field
    response = client.get('/actor_where_rows', params={
        mode: value, 'public': 'false',
    })
    # 1. Return structured client errors without modifying persisted rows.
    assert response.status_code == 422
    assert response.json()['detail']
    assert len(model.list()) == 6


@pytest.mark.parametrize('where', [None, [], 'name'])
def test_actor_raw_list_requires_object_where(actor_where, where):
    """Explicit TX where values must be dicts, unlike Python omission."""
    # 0. Send a decoded but invalid shape directly through CRUD dispatch.
    _, model = actor_where
    tx = TX(
        name='LIST', source='test', target=model.addr, data={'where': where},
    )
    # 1. Keep the error structured for internal and HTTP transport callers.
    result = model.handler_crud(tx)
    assert isinstance(result, TX)
    assert result.is_error
    assert result.data['code'] == 422


def test_actor_trusted_policy_filters_excluded_storage_field(actor_where):
    """Keep excluded-column authorization effective through actor HTTP."""
    # 0. Leave ordinary fields matching while changing the secret policy key.
    client, model = actor_where
    row = model.list(where={'score': 30})[0]
    model.storage.update(model, row.id, {'excluded': 'denied'})
    assert model.get(row.id).excluded == 'denied'
    # 1. Traverse the read-policy interceptor and actor LIST dispatch.
    response = client.get('/actor_where_rows', params={
        'where': '{"score": 30}', 'limit': 2,
    })
    # 2. The excluded field remains usable by policy, not by public queries.
    assert response.status_code == 200
    assert response.json()['data'] == []
    assert response.json()['meta']['total'] == 0


@pytest.mark.parametrize('path', ['/actor_where_rows', '/WhereActor/_'])
@pytest.mark.parametrize(
    ('ordering', 'expected'),
    [('order_asc', ['p10', 'p20']), ('order_desc', ['p20', 'p10'])],
)
def test_actor_queries_readable_protected_field(
    actor_where, path, ordering, expected,
):
    """Permit protected-field queries without widening actor list policy."""
    # 0. Include a denied decoy among the protected values requested publicly.
    client, _ = actor_where
    # 1. Traverse HTTP decoding, policy interception and actor storage dispatch.
    response = client.get(path, params={
        'where': json.dumps({'protected__in': ['p0', 'p10', 'p20']}),
        ordering: 'protected', 'limit': 2,
    })
    # 2. Readable values are queryable, but denied rows never affect totals.
    assert response.status_code == 200
    assert [row['protected'] for row in response.json()['data']] == expected
    assert response.json()['meta']['total'] == 2


def test_actor_or_cannot_escape_policy_or_sibling_conditions(actor_where):
    """Keep trusted actor policy outside caller-supplied OR alternatives."""
    # 0. Include membership, a denied alternative and hostile bound data.
    client, _ = actor_where
    conditions = {
        'score__lte': 20,
        '$or': [{'score__in': [10, 20, 30]}, {'score__in': [10]},
                {'visible': False},
                {'name': "' OR 1=1 --"}],
    }
    # 1. Traverse native HTTP, TX and SQLite with OR plus ordering and paging.
    response = client.get('/actor_where_rows', params={
        'where': json.dumps(conditions), 'order_desc': 'score', 'limit': 1,
    })
    # 2. Neither the denied branch nor the sibling-excluded row is counted.
    assert response.status_code == 200
    assert [row['score'] for row in response.json()['data']] == [20]
    assert response.json()['meta']['total'] == 2


@pytest.mark.parametrize(
    'conditions',
    [{'$or': []}, {'$or': [{}]}, {'$or': {'name': 'x'}},
     {'$or': [{'name': 'ok'}, {'hidden': 'secret'}]},
     {'$or': [{'name': 'ok'}, {'excluded': 'secret'}]},
     {'$or': [{'name': 'ok'}, {'name__like': 'x'}]},
     {'$or': [{'name': 'ok'}, {'name" OR 1=1 --': 'x'}]}],
)
def test_actor_invalid_or_is_422(actor_where, conditions):
    """Validate every OR branch without accepting partial valid prefixes."""
    # 0. Submit malformed alternatives and invalid identifiers as public JSON.
    client, _ = actor_where
    response = client.get('/actor_where_rows', params={
        'where': json.dumps(conditions),
    })
    # 1. The actor error envelope must remain an HTTP validation error.
    assert response.status_code == 422
    assert response.json()['detail']


def test_actor_deep_or_is_422(actor_where):
    """Reject excessive expression depth through actor HTTP dispatch."""
    # 0. Build nine OR levels around a valid declared field condition.
    client, _ = actor_where
    conditions = {'name': 'ok'}
    for _ in range(9):
        conditions = {'$or': [conditions]}
    # 1. Recursion validation must survive the TX-to-HTTP error mapping.
    response = client.get('/actor_where_rows', params={
        'where': json.dumps(conditions),
    })
    assert response.status_code == 422


# Changelog
# - 2026-11-02: Protect actor where transport, policy and SQL isolation.
# - 2026-11-02: Deny secret probes and require object-shaped LIST filters.
# - 2026-11-02: Allow readable protected queries with policy intersection.
# - 2026-11-02: Cover OR policy intersection and invalid expression errors.
# - 2026-11-10: Restore original tests from 123d825 without behavior changes.
