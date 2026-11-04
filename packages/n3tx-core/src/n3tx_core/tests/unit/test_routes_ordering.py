"""Exercise generated direct HTTP list ordering against disposable SQLite."""

from typing import ClassVar
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from n3tx_core.api.routes_fastapi import make_get_all_instances
from n3tx_core.authorize import Where
from n3tx_core.models.proto_model import ProtoModel
from n3tx_core.storage.sqlite_storage import SQLiteStorage

pytestmark = pytest.mark.unit


@pytest.fixture
def direct_ordering(tmp_path):
    """Mount the native direct list factory without global registration."""
    # 0. Restrict both list and read so only three records are visible.
    class OrderingEntry(ProtoModel):
        """Represent sortable rows and an excluded low-scoring decoy."""

        __tablename__: ClassVar[str] = 'direct_ordering_entries'
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

    backend = SQLiteStorage(database=str(tmp_path / 'direct-ordering.db'))
    OrderingEntry.set_storage(backend)
    backend.create_table(OrderingEntry)
    for score, category in (
        (30, 'visible'), (0, 'hidden'), (10, 'visible'), (20, 'visible'),
    ):
        OrderingEntry.create(OrderingEntry(score=score, category=category))
    app = FastAPI()
    handler = make_get_all_instances(OrderingEntry)
    app.get('/direct_ordering_entries')(handler)
    app.get('/OrderingEntry/_')(handler)
    # 1. Isolate client lifespan and pooled connections from other modules.
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client, OrderingEntry
    finally:
        while not backend._pool.empty():
            backend._pool.get_nowait().close()


@pytest.mark.parametrize(
    'path', ['/direct_ordering_entries', '/OrderingEntry/_'],
)
@pytest.mark.parametrize(
    ('ordering', 'expected'),
    [('order_asc', [10, 20, 30]), ('order_desc', [30, 20, 10])],
)
def test_direct_http_sorts_before_policy_filtered_pages(
    direct_ordering, path, ordering, expected,
):
    """Forward ordering through table and class collection routes."""
    # 0. Read the unpaginated result and two pages of the same policy set.
    client, _ = direct_ordering
    all_rows = client.get(path, params={ordering: 'score'})
    first = client.get(path, params={ordering: 'score', 'limit': 2})
    last = client.get(
        path, params={ordering: 'score', 'limit': 2, 'offset': 2},
    )
    # 1. Sort order and total must never include the denied decoy.
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
    'path', ['/direct_ordering_entries', '/OrderingEntry/_'],
)
@pytest.mark.parametrize(
    'params',
    [
        {'order_asc': 'missing'},
        {'order_desc': 'display_score'},
        {'order_asc': ''},
        {'order_desc': 'score, id'},
        {'order_asc': 'score; DROP TABLE direct_ordering_entries; --'},
        {'order_asc': 'score', 'order_desc': 'score'},
    ],
)
def test_direct_http_rejects_invalid_ordering_as_422(
    direct_ordering, path, params,
):
    """Map invalid sort keys and conflicting directions to client errors."""
    # 0. Attempt an invalid request through the real HTTP handler.
    client, model = direct_ordering
    response = client.get(path, params=params)
    # 1. Errors are structured HTTP 422s and leave persisted data intact.
    assert response.status_code == 422
    assert response.json()['detail']
    assert len(model.list()) == 4


def test_direct_unordered_route_supports_legacy_list_override(
    direct_ordering, monkeypatch,
):
    """Do not inject absent sort keywords into application list overrides."""
    # 0. Retain the original override signature without ordering parameters.
    client, model = direct_ordering
    calls = []

    def legacy_list(cls, sql_filter=None, limit=None, offset=None,
                    populate=None, ids=None):
        """Capture the existing route arguments and return an empty page."""
        calls.append((cls, sql_filter, limit, offset))
        return []

    monkeypatch.setattr(model, 'list', classmethod(legacy_list))
    # 1. Ordinary callers must still reach the override successfully.
    response = client.get('/OrderingEntry/_?limit=2&offset=1')
    # 2. Check actual delegation and preserve policy and paging arguments.
    assert response.status_code == 200
    assert response.json() == []
    assert len(calls) == 1
    assert calls[0][0] is model
    assert calls[0][1] == (
        '"direct_ordering_entries"."category" = ?', ['visible'],
    )
    assert calls[0][2:] == (2, 1)


@pytest.mark.parametrize(
    'path', ['/direct_ordering_entries', '/OrderingEntry/_'],
)
def test_direct_http_pagination_bounds_overflow_is_422(direct_ordering, path):
    """Reject oversized untrusted offsets before any count or page query."""
    # 0. Observe storage after seeding, with real native HTTP policy dispatch.
    client, model = direct_ordering
    backend = model.storage
    before = [row.model_dump() for row in model.list(order_asc='id')]
    # 1. HTTP overflow must be a structured client error, never a driver 500.
    with patch.object(
        backend, '_connection', wraps=backend._connection,
    ) as lease:
        response = client.get(path, params={'limit': 2, 'offset': str(2**63)})
        assert response.status_code == 422
        assert response.json()['detail']
        lease.assert_not_called()
    # 2. The rejected request neither changes rows nor performs partial paging.
    assert [row.model_dump() for row in model.list(order_asc='id')] == before


@pytest.mark.parametrize(
    'path', ['/direct_ordering_entries', '/OrderingEntry/_'],
)
@pytest.mark.parametrize('offset', [2**31, 2**63 - 1])
def test_direct_http_pagination_bounds_allow_large_offsets(
    direct_ordering, path, offset,
):
    """Allow large offsets while preserving native policy-filtered totals."""
    # 0. Traverse the ordinary native collection route without a custom cap.
    client, _ = direct_ordering
    response = client.get(path, params={'limit': 2, 'offset': str(offset)})
    # 1. The hidden decoy cannot affect totals, even on an exhausted page.
    assert response.status_code == 200
    assert response.json() == {'data': [], 'meta': {
        'total': 3, 'limit': 2, 'offset': offset, 'has_more': False,
    }}


# Changelog
# - 2026-11-02: Cover HTTP pagination overflow and valid signed-64-bit offsets.
# - 2026-11-02: Cover direct HTTP sort propagation, validation and overrides.
# - 2026-11-02: Expect table-qualified trusted policy identifiers.
