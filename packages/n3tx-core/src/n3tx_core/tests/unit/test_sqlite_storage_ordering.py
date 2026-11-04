"""Protect single-field SQLite ordering before filtered pagination."""

from typing import ClassVar
from unittest.mock import patch

import pytest
from pydantic import Field

from n3tx_core.models.proto_model import ProtoModel
from n3tx_core.storage.sqlite_storage import SQLiteStorage

pytestmark = pytest.mark.unit


@pytest.fixture
def ordered_storage(tmp_path):
    """Create synthetic rows in a disposable, file-backed SQLite database."""
    # 0. Declare persisted fields and a non-persisted property.
    class OrderingRow(ProtoModel):
        """Provide distinct sort keys and a nullable persisted column."""

        __tablename__: ClassVar[str] = 'ordering_rows'
        __storable__: ClassVar[bool] = True
        score: int | None = None
        category: str = 'included'

        @property
        def display_score(self):
            """Expose a property that must not become an SQL sort key."""
            return str(self.score)

    backend = SQLiteStorage(database=str(tmp_path / 'ordering.db'))
    OrderingRow.set_storage(backend)
    backend.create_table(OrderingRow)
    for score, category in (
        (30, 'included'), (0, 'excluded'), (10, 'included'),
        (40, 'included'), (20, 'included'), (None, 'included'),
    ):
        OrderingRow.create(OrderingRow(score=score, category=category))
    # 1. Keep every connection and record inside this fixture's database.
    try:
        yield backend, OrderingRow
    finally:
        while not backend._pool.empty():
            backend._pool.get_nowait().close()


@pytest.mark.parametrize(
    ('ordering', 'expected'),
    [('order_asc', [20, 30]), ('order_desc', [30, 20])],
)
def test_ordering_precedes_filtered_page_and_preserves_count(
    ordered_storage, ordering, expected,
):
    """Sort the complete filtered set, not the already-selected page."""
    # 0. Select four non-null matching rows, excluding a low-scoring decoy.
    backend, model = ordered_storage
    sql_filter = ('category = ? AND score IS NOT NULL', ['included'])
    # 1. Read a middle page through the storage contract.
    page = backend.list(
        model, sql_filter=sql_filter, limit=2, offset=1,
        **{ordering: 'score'},
    )
    unordered = backend.list(model, sql_filter=sql_filter, limit=2)
    # 2. Count remains independent of direction and page size.
    assert [row.score for row in page['data']] == expected
    assert page['meta'] == {
        'total': 4, 'limit': 2, 'offset': 1, 'has_more': True,
    }
    assert unordered['meta']['total'] == page['meta']['total']
    tail = backend.list(
        model, sql_filter=sql_filter, limit=2, offset=3,
        **{ordering: 'score'},
    )
    assert len(tail['data']) == 1
    assert tail['meta']['total'] == 4
    assert tail['meta']['has_more'] is False


@pytest.mark.parametrize(
    ('ordering', 'expected'),
    [
        ('order_asc', [None, 10, 20, 30, 40]),
        ('order_desc', [40, 30, 20, 10, None]),
    ],
)
def test_unpaginated_ordering_keeps_native_null_placement(
    ordered_storage, ordering, expected,
):
    """Preserve SQLite NULL-first ASC and NULL-last DESC semantics."""
    # 0. Exercise the public model-to-storage path without pagination.
    _, model = ordered_storage
    rows = model.list(
        sql_filter=('category = ?', ['included']),
        **{ordering: 'score'},
    )
    # 1. The unpaginated shape remains a plain list of hydrated models.
    assert isinstance(rows, list)
    assert [row.score for row in rows] == expected


@pytest.mark.parametrize('ordering', ['order_asc', 'order_desc'])
@pytest.mark.parametrize(
    'field',
    ['', 'missing', 'display_score', 'score DESC', 'score, id',
     'score; DROP TABLE ordering_rows; --', 'score\n', 1, ['score']],
)
def test_invalid_ordering_is_value_error_without_database_damage(
    ordered_storage, ordering, field,
):
    """Reject non-fields and SQL fragments before executing a query."""
    # 0. Attempt invalid ordering even when the selected IDs match no rows.
    backend, model = ordered_storage
    with pytest.raises(ValueError):
        backend.list(model, ids=[99999], **{ordering: field})
    # 1. Rejection must leave all persisted rows available.
    assert len(backend.list(model)) == 6


def test_conflicting_directions_fail_even_for_same_field(ordered_storage):
    """Do not silently prefer one direction when both are supplied."""
    # 0. Exercise conflicting directions against real storage.
    backend, model = ordered_storage
    with pytest.raises(ValueError):
        backend.list(model, order_asc='score', order_desc='score')
    # 1. An error must not mutate the table.
    assert len(model.list()) == 6


def test_ordered_ids_intersect_filter_before_count(ordered_storage):
    """Selected IDs and policy filters constrain both count and sort."""
    # 0. Include an excluded row in a nonempty selected-ID constraint.
    backend, model = ordered_storage
    rows = backend.list(model)
    selected = [row.id for row in rows if row.score in (0, 10, 30, 40)]
    # 1. Page only the intersection, in descending score order.
    page = model.list(
        ids=selected, sql_filter=('category = ?', ['included']),
        order_desc='score', limit=1, offset=1,
    )
    # 2. Count includes every matching selected row, not the decoy.
    assert [row.score for row in page['data']] == [30]
    assert page['meta']['total'] == 3
    assert page['meta']['has_more'] is True


@pytest.mark.parametrize('ordering', ['order_asc', 'order_desc'])
def test_declared_but_unmigrated_field_is_rejected(ordered_storage, ordering):
    """Require a physical column, not just a declared model field."""
    # 0. Extend the model without migrating the fixture's existing table.
    backend, model = ordered_storage

    class UnmigratedRow(model):
        """Represent a declaration ahead of its physical database schema."""

        pending_score: int = 0
    # 1. A quoted missing SQLite identifier must not become a constant sort.
    with pytest.raises(ValueError):
        backend.list(UnmigratedRow, **{ordering: 'pending_score'})
    # 2. The existing table remains readable without automatic migration.
    assert len(model.list()) == 6


def test_ordering_preserves_json_and_local_child_hydration(ordered_storage):
    """Sort parent rows without changing JSON decoding or child order."""
    # 0. Register related models only in the fixture's disposable database.
    backend, _ = ordered_storage

    class OrderingChild(ProtoModel):
        """Provide saved children whose association order is significant."""

        __tablename__: ClassVar[str] = 'ordering_children'
        __storable__: ClassVar[bool] = True
        name: str = ''

    class OrderingParent(ProtoModel):
        """Combine an SQL sort key with JSON and local relationship data."""

        __tablename__: ClassVar[str] = 'ordering_parents'
        __storable__: ClassVar[bool] = True
        score: int = 0
        payload: dict = Field(default_factory=dict)
        children: list[OrderingChild] = Field(default_factory=list)

    for model in (OrderingChild, OrderingParent):
        model.set_storage(backend)
        backend.create_table(model)
    first = OrderingChild.create(OrderingChild(name='first'))
    second = OrderingChild.create(OrderingChild(name='second'))
    for score in (30, 10):
        OrderingParent.create(OrderingParent(
            score=score, payload={'nested': [score, {'valid': True}]},
            children=[second, first],
        ))
    # 1. Hydrate the first page after ordering parents by their scalar key.
    page = OrderingParent.list(order_asc='score', limit=1)
    # 2. Parent ordering must not reorder or flatten embedded child data.
    parent = page['data'][0]
    assert parent.score == 10
    assert parent.payload == {'nested': [10, {'valid': True}]}
    assert [child.id for child in parent.children] == [second.id, first.id]
    assert [child.name for child in parent.children] == ['second', 'first']
    assert page['meta']['total'] == 2


@pytest.mark.parametrize('parameter', ['limit', 'offset'])
@pytest.mark.parametrize('value', [-1, True, False, 1.0, '1', 2**63])
def test_pagination_bounds_reject_invalid_values_before_connection(
    ordered_storage, parameter, value,
):
    """Reject invalid page bounds before count, selection or driver coercion."""
    # 0. Observe the connection seam only after disposable rows are persisted.
    backend, model = ordered_storage
    before = [row.model_dump() for row in model.list(order_asc='id')]
    options = {'limit': 2, 'offset': None, parameter: value}
    # 1. Invalid bounds must be ValueErrors without leasing a SQL connection.
    with patch.object(
        backend, '_connection', wraps=backend._connection,
    ) as lease:
        with pytest.raises(ValueError):
            backend.list(model, **options)
        lease.assert_not_called()
    # 2. Rejection preserves every stored row and its field values.
    assert [row.model_dump() for row in model.list(order_asc='id')] == before


def test_pagination_bounds_validate_offset_without_limit(ordered_storage):
    """Validate offsets even when unpaginated reads would ignore them."""
    # 0. Omitted limit must not bypass the storage parameter boundary.
    backend, model = ordered_storage
    # 1. An unbindable offset fails before any read/count connection is leased.
    with patch.object(
        backend, '_connection', wraps=backend._connection,
    ) as lease:
        with pytest.raises(ValueError):
            backend.list(model, offset=2**63)
        lease.assert_not_called()


@pytest.mark.parametrize('offset', [2**31, 2**63 - 1])
def test_pagination_bounds_allow_large_signed_offsets(ordered_storage, offset):
    """Retain native signed-64-bit offsets without restoring a 32-bit cap."""
    # 0. A real filter constrains the total independently of the empty page.
    backend, model = ordered_storage
    page = backend.list(
        model, sql_filter=('category = ?', ['included']),
        limit=2, offset=offset,
    )
    # 1. Large valid offsets return no rows but retain the filtered count.
    assert page == {'data': [], 'meta': {
        'total': 5, 'limit': 2, 'offset': offset, 'has_more': False,
    }}


def test_pagination_bounds_preserve_none_zero_and_max_limit(ordered_storage):
    """Keep unpaginated reads, count-only probes and valid large limits."""
    # 0. Explicit None retains the historical plain-list response shape.
    backend, model = ordered_storage
    assert len(backend.list(model, limit=None, offset=None)) == 6
    assert len(backend.list(model, offset=0)) == 6
    # 1. Zero is valid internally and counts without hydrating a page.
    assert backend.list(model, limit=0, offset=0) == {'data': [], 'meta': {
        'total': 6, 'limit': 0, 'offset': 0, 'has_more': True,
    }}
    # 2. Storage accepts signed-64-bit limits beyond HTTP's separate page cap.
    page = backend.list(model, limit=2**63 - 1)
    assert len(page['data']) == page['meta']['total'] == 6
    assert page['meta']['limit'] == 2**63 - 1
    assert page['meta']['has_more'] is False


# Changelog
# - 2026-11-02: Reject invalid page bounds before SQL; retain valid ranges.
# - 2026-11-02: Cover SQLite ordered pages, counts, NULLs and invalid keys.
#   Include physical-column validation and preserved JSON/child hydration.
