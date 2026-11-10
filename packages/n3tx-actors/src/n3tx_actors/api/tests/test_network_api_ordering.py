"""Exercise generated actor HTTP ordering through Matrix and SQLite."""

from typing import ClassVar
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from n3tx_actors.api.auth_interceptor import auth_interceptor
from n3tx_actors.api.network_api import NetworkAPI, create_api_routes
from n3tx_actors.matrix import Matrix
from n3tx_actors.models.actor_model import ActorModel
from n3tx_actors.tx import TX
from n3tx_core.authorize import Where
from n3tx_core.storage.sqlite_storage import SQLiteStorage

pytestmark = pytest.mark.unit


@pytest.fixture
def actor_ordering(tmp_path):
    """Wire real actor HTTP dispatch with isolated storage and actor state."""
    # 0. The local conftest restores process-wide Actor/Matrix registrations.
    root = Matrix()

    class OrderingActor(ActorModel, auto_register=False):
        """Provide sortable fields under a native SQL visibility policy."""

        __tablename__: ClassVar[str] = 'actor_ordering_entries'
        __storable__: ClassVar[bool] = True
        __access__: ClassVar[dict] = {
            'list': Where(category='visible'),
            'read': Where(category='visible'),
        }
        score: int = 0
        category: str = 'visible'

        @property
        def display_score(self):
            """Provide a non-persisted attribute for rejection coverage."""
            return str(self.score)

    backend = SQLiteStorage(database=str(tmp_path / 'actor-ordering.db'))
    OrderingActor.set_storage(backend)
    backend.create_table(OrderingActor)
    for score, category in (
        (30, 'visible'), (0, 'hidden'), (10, 'visible'), (20, 'visible'),
    ):
        OrderingActor.create(OrderingActor(score=score, category=category))
    root.register(OrderingActor)
    adapter = NetworkAPI()
    root.register(adapter)
    adapter.use(auth_interceptor, on='request')
    app = FastAPI()
    app.include_router(create_api_routes(
        adapter, {'actor_ordering_entries': OrderingActor},
    ))
    # 1. Never launch a server or contact a remote provider.
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client, OrderingActor
    finally:
        while not backend._pool.empty():
            backend._pool.get_nowait().close()


@pytest.mark.parametrize(
    'path', ['/actor_ordering_entries', '/OrderingActor/_'],
)
@pytest.mark.parametrize(
    ('ordering', 'expected'),
    [('order_asc', [10, 20, 30]), ('order_desc', [30, 20, 10])],
)
def test_actor_http_orders_policy_filtered_set_before_paging(
    actor_ordering, path, ordering, expected,
):
    """Propagate sort fields across HTTP, TX, ActorModel and storage."""
    # 0. Read one full collection and two pages through the actor boundary.
    client, _ = actor_ordering
    all_rows = client.get(path, params={ordering: 'score'})
    first = client.get(path, params={ordering: 'score', 'limit': 2})
    last = client.get(
        path, params={ordering: 'score', 'limit': 2, 'offset': 2},
    )
    # 1. Ordering must not bypass SQL policy or change filtered totals.
    assert all_rows.status_code == first.status_code == 200
    assert last.status_code == 200
    assert [row['score'] for row in all_rows.json()] == expected
    assert [row['score'] for row in first.json()['data']] == expected[:2]
    assert [row['score'] for row in last.json()['data']] == expected[2:]
    assert first.json()['meta'] == {
        'total': 3, 'limit': 2, 'offset': 0, 'has_more': True,
    }
    assert last.json()['meta'] == {
        'total': 3, 'limit': 2, 'offset': 2, 'has_more': False,
    }


@pytest.mark.parametrize(
    'path', ['/actor_ordering_entries', '/OrderingActor/_'],
)
@pytest.mark.parametrize(
    'params',
    [
        {'order_asc': 'missing'},
        {'order_desc': 'display_score'},
        {'order_asc': ''},
        {'order_desc': 'score, id'},
        {'order_asc': 'score; DROP TABLE actor_ordering_entries; --'},
        {'order_asc': 'score', 'order_desc': 'score'},
    ],
)
def test_actor_http_maps_invalid_ordering_to_422(
    actor_ordering, path, params,
):
    """Turn storage ValueErrors into error TXs and structured HTTP 422s."""
    # 0. Exercise invalid fields, properties, SQL fragments and conflicts.
    client, model = actor_ordering
    response = client.get(path, params=params)
    # 1. Validation errors must not become 500s or damage the database.
    assert response.status_code == 422
    assert response.json()['detail']
    assert len(model.list()) == 4


def test_actor_unordered_http_supports_legacy_list_override(
    actor_ordering, monkeypatch,
):
    """Omit absent ordering keywords when ActorModel invokes an override."""
    # 0. Install an application override accepting only historical arguments.
    client, model = actor_ordering
    calls = []

    def legacy_list(cls, sql_filter=None, limit=None, offset=None,
                    populate=None, ids=None):
        """Record the legacy call without accepting arbitrary keywords."""
        calls.append((cls, sql_filter, limit, offset))
        return []

    monkeypatch.setattr(model, 'list', classmethod(legacy_list))
    # 1. Traverse the real HTTP-to-Matrix-to-ActorModel list dispatch.
    response = client.get('/OrderingActor/_?limit=2&offset=1')
    # 2. Assert successful delegation with policy and paging preserved.
    assert response.status_code == 200
    assert response.json() == []
    assert len(calls) == 1
    assert calls[0][0] is model
    assert calls[0][1] == (
        '"actor_ordering_entries"."category" = ?', ['visible'],
    )
    assert calls[0][2:] == (2, 1)


@pytest.mark.parametrize(
    ('ordering', 'expected'),
    [('order_asc', [10, 20]), ('order_desc', [30, 20])],
)
def test_raw_actor_list_propagates_ordering(actor_ordering, ordering, expected):
    """Keep uppercase internal LIST dispatch compatible with ordering."""
    # 0. Internal TX callers supply their own trusted SQL filter metadata.
    _, model = actor_ordering
    tx = TX(
        name='LIST', source='test', target=model.addr,
        data={ordering: 'score', 'limit': 2},
        meta={'sql_filter': ('category = ?', ['visible'])},
    )
    # 1. Exercise the native CRUD adapter without an HTTP boundary.
    result = model.handler_crud(tx)
    # 2. Sort and count must survive TX argument adaptation and serialization.
    assert [row['score'] for row in result['data']] == expected
    assert result['meta']['total'] == 3
    assert result['meta']['has_more'] is True


@pytest.mark.parametrize(
    'data',
    [
        {'order_asc': 'display_score'},
        {'order_asc': 'score', 'order_desc': 'score'},
    ],
)
def test_raw_actor_list_returns_422_error_tx(actor_ordering, data):
    """Keep raw LIST validation errors structured instead of raising."""
    # 0. Send invalid ordering directly to the actor CRUD adapter.
    _, model = actor_ordering
    tx = TX(name='LIST', source='test', target=model.addr, data=data)
    # 1. Storage ValueError must be translated at the ActorModel boundary.
    result = model.handler_crud(tx)
    # 2. Preserve the error envelope consumed by actor HTTP and TX clients.
    assert isinstance(result, TX)
    assert result.is_error
    assert result.data['code'] == 422
    assert result.data['message']


@pytest.mark.parametrize(
    'path', ['/actor_ordering_entries', '/OrderingActor/_'],
)
def test_actor_http_pagination_bounds_overflow_is_422(actor_ordering, path):
    """Map invalid untrusted offsets through TX to HTTP before any SQL read."""
    # 0. Observe storage behind the existing real HTTP/Matrix/ActorModel path.
    client, model = actor_ordering
    backend = model.storage
    before = [row.model_dump() for row in model.list(order_asc='id')]
    # 1. Return a native client error, not a driver 500 after partial reads.
    with patch.object(
        backend, '_connection', wraps=backend._connection,
    ) as lease:
        response = client.get(path, params={'limit': 2, 'offset': str(2**63)})
        assert response.status_code == 422
        assert response.json()['detail']
        lease.assert_not_called()
    # 2. Failed requests do not alter rows or execute partial pagination work.
    assert [row.model_dump() for row in model.list(order_asc='id')] == before


@pytest.mark.parametrize(
    'path', ['/actor_ordering_entries', '/OrderingActor/_'],
)
@pytest.mark.parametrize('offset', [2**31, 2**63 - 1])
def test_actor_http_pagination_bounds_allow_large_offsets(
    actor_ordering, path, offset,
):
    """Preserve signed-64-bit offsets across actor HTTP and native storage."""
    # 0. Do not impose the removed application-specific 32-bit offset bound.
    client, _ = actor_ordering
    response = client.get(path, params={'limit': 2, 'offset': str(offset)})
    # 1. Page data is empty, but the trusted visibility filter still owns count.
    assert response.status_code == 200
    assert response.json() == {'data': [], 'meta': {
        'total': 3, 'limit': 2, 'offset': offset, 'has_more': False,
    }}


def test_raw_actor_pagination_bounds_overflow_is_422(actor_ordering):
    """Keep raw LIST overflow a structured 422 without count/selection reads."""
    # 0. Internal TX inputs bypass HTTP parsing but retain storage validation.
    _, model = actor_ordering
    tx = TX(
        name='LIST', source='test', target=model.addr,
        data={'limit': 2, 'offset': 2**63},
    )
    backend = model.storage
    # 1. ValueError must map to a client error before any connection is leased.
    with patch.object(
        backend, '_connection', wraps=backend._connection,
    ) as lease:
        result = model.handler_crud(tx)
        assert isinstance(result, TX)
        assert result.is_error
        assert result.data['code'] == 422
        lease.assert_not_called()


# Changelog
# - 2026-11-02: Cover native offset overflow through HTTP and raw LIST TX.
# - 2026-11-02: Cover actor HTTP ordered pages, errors and legacy overrides.
#   Include raw uppercase LIST propagation and structured error TXs.
# - 2026-11-02: Expect table-qualified trusted policy identifiers.
# - 2026-11-10: Restore original tests from 123d825 without behavior changes.
