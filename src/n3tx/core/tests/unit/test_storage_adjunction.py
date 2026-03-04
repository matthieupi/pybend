"""Storage adjunction round-trip tests.

Verifies the fundamental property: get(create(m)).fields == m.fields
for all storable field types. This validates the storage layer as a
faithful store-retrieve adjunction.

Uses file-based SQLite (not :memory:) to avoid the separate-connection
gotcha where create_table opens a different DB than create/get.
"""

import pytest
from typing import ClassVar, Optional

from pydantic import Field

from n3tx.core.storage.sqlite_storage import SQLiteStorage
from n3tx.core.models.proto_model import ProtoModel

pytestmark = pytest.mark.unit


# ── Fixtures ───────────────────────────────────────────────────────

@pytest.fixture
def tmp_db(tmp_path):
    return str(tmp_path / 'adjunction.db')


@pytest.fixture
def storage(tmp_db):
    return SQLiteStorage(database=tmp_db)


def _make_model(tablename, storage_backend, **fields):
    """Create a storable model class with given fields, set up table."""
    annotation_dict = {}
    field_defs = {}
    for field_name, (field_type, default) in fields.items():
        annotation_dict[field_name] = field_type
        field_defs[field_name] = Field(default=default)

    M = type(tablename, (ProtoModel,), {
        '__annotations__': annotation_dict,
        '__tablename__': tablename,
        '__storable__': True,
        **field_defs,
    })
    M.__tablename__ = tablename
    M.__storable__ = True
    M.set_storage(storage_backend)
    storage_backend.create_table(M)
    return M


# ── Scalar Round-Trip ──────────────────────────────────────────────

class TestScalarRoundTrip:
    """get(create(m)) preserves scalar field values."""

    def test_string_roundtrip(self, storage):
        M = _make_model('adj_str', storage, name=(str, ''))
        created = storage.create(M, {'name': 'hello world'})
        fetched = storage.get(M, created.id)
        assert fetched.name == 'hello world'

    def test_int_roundtrip(self, storage):
        M = _make_model('adj_int', storage, count=(int, 0))
        created = storage.create(M, {'count': 42})
        fetched = storage.get(M, created.id)
        assert fetched.count == 42

    def test_float_roundtrip(self, storage):
        M = _make_model('adj_float', storage, price=(float, 0.0))
        created = storage.create(M, {'price': 19.99})
        fetched = storage.get(M, created.id)
        assert abs(fetched.price - 19.99) < 1e-9

    def test_bool_roundtrip(self, storage):
        M = _make_model('adj_bool', storage, active=(bool, False))
        created = storage.create(M, {'active': True})
        fetched = storage.get(M, created.id)
        assert fetched.active is True

    def test_empty_string_roundtrip(self, storage):
        M = _make_model('adj_empty', storage, name=(str, ''))
        created = storage.create(M, {'name': ''})
        fetched = storage.get(M, created.id)
        assert fetched.name == ''

    def test_zero_roundtrip(self, storage):
        M = _make_model('adj_zero', storage, count=(int, 0))
        created = storage.create(M, {'count': 0})
        fetched = storage.get(M, created.id)
        assert fetched.count == 0


# ── Optional Round-Trip ────────────────────────────────────────────

class TestOptionalRoundTrip:
    """get(create(m)) preserves Optional fields including None."""

    def test_optional_none(self, storage):
        M = _make_model('adj_opt_none', storage, label=(Optional[str], None))
        created = storage.create(M, {'label': None})
        fetched = storage.get(M, created.id)
        assert fetched.label is None

    def test_optional_with_value(self, storage):
        M = _make_model('adj_opt_val', storage, label=(Optional[str], None))
        created = storage.create(M, {'label': 'present'})
        fetched = storage.get(M, created.id)
        assert fetched.label == 'present'


# ── ID Round-Trip ──────────────────────────────────────────────────

class TestIdRoundTrip:
    """Auto-increment ID is assigned and preserved."""

    def test_id_assigned_on_create(self, storage):
        M = _make_model('adj_id', storage, name=(str, ''))
        created = storage.create(M, {'name': 'test'})
        assert created.id is not None
        assert created.id > 0

    def test_id_preserved_on_get(self, storage):
        M = _make_model('adj_id_get', storage, name=(str, ''))
        created = storage.create(M, {'name': 'test'})
        fetched = storage.get(M, created.id)
        assert fetched.id == created.id


# ── Multi-Field Round-Trip ─────────────────────────────────────────

class TestMultiFieldRoundTrip:
    """All scalar types together on one model."""

    def test_all_scalars_together(self, storage):
        M = _make_model('adj_multi', storage,
                         name=(str, ''),
                         count=(int, 0),
                         price=(float, 0.0),
                         active=(bool, False))
        data = {'name': 'widget', 'count': 7, 'price': 3.14, 'active': True}
        created = storage.create(M, data)
        fetched = storage.get(M, created.id)
        assert fetched.name == 'widget'
        assert fetched.count == 7
        assert abs(fetched.price - 3.14) < 1e-9
        assert fetched.active is True


# ── Update Partial Round-Trip ──────────────────────────────────────

class TestUpdatePartialRoundTrip:
    """Partial update preserves untouched fields."""

    def test_partial_update(self, storage):
        M = _make_model('adj_partial', storage,
                         name=(str, ''),
                         count=(int, 0))
        created = storage.create(M, {'name': 'original', 'count': 10})
        storage.update(M, created.id, {'name': 'updated'})
        fetched = storage.get(M, created.id)
        assert fetched.name == 'updated'
        assert fetched.count == 10  # untouched

    def test_update_to_zero(self, storage):
        M = _make_model('adj_zero_upd', storage,
                         name=(str, ''),
                         count=(int, 5))
        created = storage.create(M, {'name': 'test', 'count': 5})
        storage.update(M, created.id, {'count': 0})
        fetched = storage.get(M, created.id)
        assert fetched.count == 0  # zero is not "empty"
