"""Protect native SQLite projection, non-migrating reopen and static defaults.

Real disposable databases exercise storage directly with ordinary Pydantic
models, avoiding global registration and optional actor/model mixin injection.
False mode validates without reconciliation; default true mode stays compatible.
No application schema, index hook, migration files or live storage are used."""

from contextlib import closing
from queue import Empty
import sqlite3
from typing import ClassVar

import pytest
from pydantic import BaseModel, Field, create_model

from n3tx_core.storage.sqlite_storage import SQLiteStorage

HINT = {"x-sqlite-not-null-default": True}
LITERAL = "it's literal"


class MarkedFields(BaseModel):
    """Define static constrained fields without binding runtime storage."""

    __tablename__: ClassVar[str] = "constraint_rows"
    id: int = 0
    label: str = Field(default=LITERAL, json_schema_extra=HINT)
    enabled: bool = Field(default=False, json_schema_extra=HINT)


class Row(MarkedFields):
    """Retain an unmarked Boolean alongside the constrained projection."""

    plain: bool = False


@pytest.fixture
def open_storage(tmp_path):
    """Return native backends and close every owned pooled connection."""
    backends = []

    def open_backend(name="storage", **options):
        """Open a named database under the runner's temporary root."""
        backend = SQLiteStorage(
            str(tmp_path / f"{name}.sqlite3"), pool_size=1, **options,
        )
        backends.append(backend)
        return backend

    try:
        yield open_backend
    finally:
        # 0. Release only connections owned by this fixture's native backends.
        for backend in backends:
            while True:
                try:
                    connection = backend._pool.get_nowait()
                except Empty:
                    break
                connection.rollback()
                connection.close()


def _dump(database):
    """Snapshot native schema and rows, not WAL-dependent file bytes."""
    with closing(sqlite3.connect(database)) as connection:
        return tuple(connection.iterdump())


def test_fresh_projection_enforces_defaults_and_native_round_trips(
    open_storage,
):
    """Create absent tables and retain ordinary unmarked behavior."""
    # 0. Creation and validation use the same native physical projection.
    storage = open_storage(auto_migrate=False)
    storage.create_table(Row)
    storage.migrate_table(Row)
    with closing(sqlite3.connect(storage.database)) as connection:
        columns = {
            row[1]: row[2:5]
            for row in connection.execute("PRAGMA table_info(constraint_rows)")
        }
        assert columns["label"] == ("TEXT", 1, "'it''s literal'")
        assert columns["enabled"] == ("INTEGER", 1, "0")
        assert columns["plain"] == ("TEXT", 0, None)
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE name='_migrations'",
        ).fetchall() == []
        # 1. SQL itself enforces null refusal and supplies omitted defaults.
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO constraint_rows(label, enabled) VALUES(NULL, 0)",
            )
        connection.rollback()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO constraint_rows(label, enabled) VALUES('x', NULL)",
            )
        connection.rollback()
        default_id = connection.execute(
            "INSERT INTO constraint_rows DEFAULT VALUES",
        ).lastrowid
        connection.commit()
        assert connection.execute(
            "SELECT label, enabled, plain FROM constraint_rows WHERE id=?",
            (default_id,),
        ).fetchone() == (LITERAL, 0, None)
    # 2. Ordinary storage writes and hydration preserve Boolean/string values.
    created = storage.create(Row, {
        "label": "Created", "enabled": True, "plain": False,
    })
    assert storage.get(Row, created.id).enabled is True
    storage.update(Row, created.id, {
        "label": "Updated", "enabled": False, "plain": True,
    })
    assert storage.get(Row, created.id).model_dump() == {
        "id": created.id, "label": "Updated", "enabled": False, "plain": True,
    }
    page = storage.list(Row, limit=10, order_asc="id")
    assert page["meta"]["total"] == 2
    assert [row.label for row in page["data"]] == [LITERAL, "Updated"]
    assert page["data"][0].enabled is False


def test_existing_projection_refuses_drift_without_schema_rewrite(
    open_storage, monkeypatch,
):
    """Validate names and marked defaults without rewriting objects."""
    # 0. Native creation supplies a nested model's physical child_id column.
    class Child(BaseModel):
        """Represent a local nested model solely for physical projection."""

        id: int = 0

    class Envelope(BaseModel):
        """Project the local nested model under its native _id column."""

        __tablename__: ClassVar[str] = "nested_rows"
        id: int = 0
        child: Child

    storage = open_storage("existing", auto_migrate=False)
    storage.create_table(Row)
    storage.create_table(Envelope)
    storage.create(Row, {"label": "Retained", "enabled": True, "plain": True})
    with closing(sqlite3.connect(storage.database)) as connection:
        connection.executescript(
            "CREATE INDEX retained_index ON constraint_rows(label);"
            "CREATE TABLE extension_data(value TEXT);"
            "INSERT INTO extension_data VALUES('retained extension');"
            "CREATE TABLE _migrations(name TEXT PRIMARY KEY);"
            "INSERT INTO _migrations VALUES('synthetic ledger marker');"
        )
        assert {row[1] for row in connection.execute(
            "PRAGMA table_info(nested_rows)",
        )} == {"id", "child_id"}
    before = _dump(storage.database)
    reopened = open_storage("existing", auto_migrate=False)

    class MissingColumn(Row):
        """Demand a physical column absent from the existing table."""

        extra: str = ""

    class DifferentDefault(Row):
        """Demand a different marked Boolean default without changing names."""

        enabled: bool = Field(default=True, json_schema_extra=HINT)

    class LogicalNested(BaseModel):
        """Reject a logical child column where native storage has child_id."""

        __tablename__: ClassVar[str] = "nested_rows"
        id: int = 0
        child: int = 0

    native_connect = sqlite3.connect
    statements = []

    def traced_connect(*args, **kwargs):
        """Observe real connections without replacing SQLite execution."""
        connection = native_connect(*args, **kwargs)
        connection.set_trace_callback(statements.append)
        return connection

    # 1. Both public entrypoints validate compatible tables without any DDL.
    with monkeypatch.context() as patch:
        patch.setattr(sqlite3, "connect", traced_connect)
        for model in (Row, Envelope):
            reopened.create_table(model)
            reopened.migrate_table(model)
        # 2. Surplus, missing, nested-name and marked-default drift fail closed.
        for model in (
            MarkedFields, MissingColumn, LogicalNested, DifferentDefault,
        ):
            with pytest.raises(ValueError):
                reopened.create_table(model)
            with pytest.raises(ValueError):
                reopened.migrate_table(model)
    assert not any(statement.lstrip().upper().startswith(
        ("CREATE", "ALTER", "DROP"),
    ) for statement in statements)
    assert _dump(storage.database) == before
    assert reopened.get(Row, 1).label == "Retained"


def test_default_reconciliation_and_invalid_static_defaults(
    tmp_path, open_storage,
):
    """Keep default reconciliation and reject declarations without factories."""
    # 0. Omission of auto_migrate retains native ADD/DROP reconciliation.
    database = tmp_path / "default.sqlite3"
    with closing(sqlite3.connect(database)) as connection:
        connection.executescript(
            "CREATE TABLE constraint_rows "
            "(id INTEGER PRIMARY KEY, label TEXT, obsolete TEXT);"
            "INSERT INTO constraint_rows VALUES(1, 'Retained', 'old');"
        )
    storage = open_storage("default")
    storage.create_table(Row)
    storage.migrate_table(Row)
    with closing(sqlite3.connect(database)) as connection:
        columns = {row[1]: row for row in connection.execute(
            "PRAGMA table_info(constraint_rows)",
        )}
        assert set(columns) == {"id", "label", "enabled", "plain"}
        assert columns["enabled"][2:5] == ("INTEGER", 1, "0")
        assert columns["label"][3:5] == (0, None)
    assert storage.get(Row, 1).label == "Retained"
    assert storage.get(Row, 1).enabled is False
    before = _dump(database)
    calls = []

    def forbidden_factory():
        """Detect unsafe default-factory execution during SQL projection."""
        calls.append(True)
        raise AssertionError("Default factories must not execute")

    # 1. Validate declarations before DDL, including lazy and absent defaults.
    defaults = (
        Field(default_factory=forbidden_factory, json_schema_extra=HINT),
        Field(default=None, json_schema_extra=HINT),
        Field(json_schema_extra=HINT),
        Field(default=17, json_schema_extra=HINT),
    )
    for field in defaults:
        invalid = create_model(
            "InvalidDefault", __base__=Row, label=(str, field),
        )
        with pytest.raises(ValueError, match="static string or bool"):
            storage.create_table(invalid)
        with pytest.raises(ValueError, match="static string or bool"):
            storage.migrate_table(invalid)
    assert calls == [] and _dump(database) == before


# Changelog (Python has no native block-comment syntax).
# - 2026-11-12: Cover native constrained defaults, non-migrating projection
#   validation without rewrites, reconciliation and factory nonexecution.
