"""Tests for storage/sqlite_migration.py — Migration base and SQLiteMigration."""

import os
import sqlite3
import pytest
from typing import ClassVar

from pydantic import Field

from pybend.core.storage.sqlite_migration import Migration, SQLiteMigration
from pybend.core.models.proto_model import ProtoModel

pytestmark = pytest.mark.unit



@pytest.fixture
def tmp_db(tmp_path):
    return str(tmp_path / 'migration_test.db')


@pytest.fixture
def migration(tmp_db, tmp_path):
    migrations_dir = str(tmp_path / 'migrations')
    return SQLiteMigration(database=tmp_db, migrations_dir=migrations_dir)


class TestMigrationBase:

    def test_abstract_up(self):
        with pytest.raises(TypeError):
            Migration()

    def test_concrete_migration(self):
        class TestMig(Migration):
            def up(self, cursor):
                pass
            def down(self, cursor):
                pass
        m = TestMig()
        assert callable(m.up)
        assert callable(m.down)


class TestSQLiteMigrationInit:

    def test_creates_migrations_table(self, tmp_db):
        m = SQLiteMigration(database=tmp_db)
        conn = sqlite3.connect(tmp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='_migrations'")
        result = cursor.fetchone()
        conn.close()
        assert result is not None

    def test_default_migrations_dir(self, tmp_db):
        m = SQLiteMigration(database=tmp_db)
        assert m.migrations_dir == 'migrations'

    def test_custom_migrations_dir(self, tmp_db, tmp_path):
        custom_dir = str(tmp_path / 'custom_migrations')
        m = SQLiteMigration(database=tmp_db, migrations_dir=custom_dir)
        assert m.migrations_dir == custom_dir


class TestGetAppliedMigrations:

    def test_empty_initially(self, migration):
        applied = migration._get_applied_migrations()
        assert applied == set()

    def test_after_recording(self, migration, tmp_db):
        conn = sqlite3.connect(tmp_db)
        cursor = conn.cursor()
        migration._record_migration('test_001', cursor)
        conn.commit()
        conn.close()
        applied = migration._get_applied_migrations()
        assert 'test_001' in applied


class TestRecordUnrecordMigration:

    def test_record(self, migration, tmp_db):
        conn = sqlite3.connect(tmp_db)
        cursor = conn.cursor()
        migration._record_migration('mig_001', cursor)
        conn.commit()
        conn.close()
        assert 'mig_001' in migration._get_applied_migrations()

    def test_unrecord(self, migration, tmp_db):
        conn = sqlite3.connect(tmp_db)
        cursor = conn.cursor()
        migration._record_migration('mig_002', cursor)
        conn.commit()
        migration._unrecord_migration('mig_002', cursor)
        conn.commit()
        conn.close()
        assert 'mig_002' not in migration._get_applied_migrations()


class TestCreateTable:

    def test_creates_table_for_model(self, migration, tmp_db):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'mig_ct1'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
            value: int = Field(default=0)
        migration.create_table(M)
        conn = sqlite3.connect(tmp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='mig_ct1'")
        assert cursor.fetchone() is not None
        conn.close()

    def test_has_correct_columns(self, migration, tmp_db):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'mig_ct2'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
            price: float = Field(default=0.0)
        migration.create_table(M)
        conn = sqlite3.connect(tmp_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(mig_ct2)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        conn.close()
        assert 'name' in columns
        assert 'price' in columns
        assert columns['name'] == 'TEXT'
        assert columns['price'] == 'REAL'

    def test_id_autoincrement(self, migration, tmp_db):
        class M(ProtoModel):
            __tablename__: ClassVar[str] = 'mig_ct3'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        migration.create_table(M)
        conn = sqlite3.connect(tmp_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(mig_ct3)")
        rows = cursor.fetchall()
        id_row = next(r for r in rows if r[1] == 'id')
        assert id_row[2] == 'INTEGER'
        assert id_row[5] == 1  # pk flag
        conn.close()


class TestMigrateTable:

    def test_adds_missing_column(self, migration, tmp_db):
        class M1(ProtoModel):
            __tablename__: ClassVar[str] = 'mig_mt1'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
        migration.create_table(M1)

        class M2(ProtoModel):
            __tablename__: ClassVar[str] = 'mig_mt1'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')
            extra: str = Field(default='')
        migration.migrate_table(M2)

        conn = sqlite3.connect(tmp_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(mig_mt1)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()
        assert 'extra' in columns


class TestDiscoverMigrations:

    def test_no_directory(self, tmp_db):
        m = SQLiteMigration(database=tmp_db, migrations_dir='/nonexistent_dir')
        assert m._discover_migrations() == []

    def test_empty_directory(self, migration, tmp_path):
        os.makedirs(str(tmp_path / 'migrations'), exist_ok=True)
        result = migration._discover_migrations()
        assert result == []

    def test_finds_py_files(self, migration, tmp_path):
        mig_dir = str(tmp_path / 'migrations')
        os.makedirs(mig_dir, exist_ok=True)
        with open(os.path.join(mig_dir, '001_test.py'), 'w') as f:
            f.write('pass')
        result = migration._discover_migrations()
        assert '001_test.py' in result

    def test_skips_underscore_files(self, migration, tmp_path):
        mig_dir = str(tmp_path / 'migrations')
        os.makedirs(mig_dir, exist_ok=True)
        with open(os.path.join(mig_dir, '__init__.py'), 'w') as f:
            f.write('pass')
        result = migration._discover_migrations()
        assert '__init__.py' not in result

    def test_sorted_order(self, migration, tmp_path):
        mig_dir = str(tmp_path / 'migrations')
        os.makedirs(mig_dir, exist_ok=True)
        for name in ['002_b.py', '001_a.py', '003_c.py']:
            with open(os.path.join(mig_dir, name), 'w') as f:
                f.write('pass')
        result = migration._discover_migrations()
        assert result == ['001_a.py', '002_b.py', '003_c.py']


class TestLoadMigrationClass:

    def test_loads_valid(self, migration, tmp_path):
        mig_dir = str(tmp_path / 'migrations')
        os.makedirs(mig_dir, exist_ok=True)
        code = '''
from pybend.core.storage.sqlite_migration import Migration

class AddColumn(Migration):
    def up(self, cursor):
        pass
    def down(self, cursor):
        pass
'''
        with open(os.path.join(mig_dir, '001_add.py'), 'w') as f:
            f.write(code)
        result = migration._load_migration_class('001_add.py')
        assert isinstance(result, Migration)

    def test_no_subclass_raises(self, migration, tmp_path):
        mig_dir = str(tmp_path / 'migrations')
        os.makedirs(mig_dir, exist_ok=True)
        with open(os.path.join(mig_dir, '001_bad.py'), 'w') as f:
            f.write('x = 1\n')
        with pytest.raises(ValueError, match="No Migration subclass found"):
            migration._load_migration_class('001_bad.py')


class TestRunMigrations:

    def test_runs_pending(self, migration, tmp_path):
        mig_dir = str(tmp_path / 'migrations')
        os.makedirs(mig_dir, exist_ok=True)
        code = '''
from pybend.core.storage.sqlite_migration import Migration

class CreateFoo(Migration):
    def up(self, cursor):
        cursor.execute("CREATE TABLE IF NOT EXISTS foo (id INTEGER PRIMARY KEY)")
    def down(self, cursor):
        cursor.execute("DROP TABLE IF EXISTS foo")
'''
        with open(os.path.join(mig_dir, '001_create_foo.py'), 'w') as f:
            f.write(code)
        applied = migration.run_migrations()
        assert '001_create_foo' in applied

    def test_skips_applied(self, migration, tmp_path):
        mig_dir = str(tmp_path / 'migrations')
        os.makedirs(mig_dir, exist_ok=True)
        code = '''
from pybend.core.storage.sqlite_migration import Migration

class CreateBar(Migration):
    def up(self, cursor):
        cursor.execute("CREATE TABLE IF NOT EXISTS bar (id INTEGER PRIMARY KEY)")
    def down(self, cursor):
        cursor.execute("DROP TABLE IF EXISTS bar")
'''
        with open(os.path.join(mig_dir, '001_create_bar.py'), 'w') as f:
            f.write(code)
        migration.run_migrations()
        # Run again — should not re-apply
        applied = migration.run_migrations()
        assert applied == []

    def test_no_pending(self, migration):
        applied = migration.run_migrations()
        assert applied == []


class TestRollback:

    def test_rollback_one(self, migration, tmp_path, tmp_db):
        mig_dir = str(tmp_path / 'migrations')
        os.makedirs(mig_dir, exist_ok=True)
        code = '''
from pybend.core.storage.sqlite_migration import Migration

class CreateBaz(Migration):
    def up(self, cursor):
        cursor.execute("CREATE TABLE IF NOT EXISTS baz (id INTEGER PRIMARY KEY)")
    def down(self, cursor):
        cursor.execute("DROP TABLE IF EXISTS baz")
'''
        with open(os.path.join(mig_dir, '001_create_baz.py'), 'w') as f:
            f.write(code)
        migration.run_migrations()
        rolled = migration.rollback(steps=1)
        assert '001_create_baz' in rolled

        # Verify table dropped
        conn = sqlite3.connect(tmp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='baz'")
        assert cursor.fetchone() is None
        conn.close()

    def test_rollback_file_not_found(self, migration, tmp_path, tmp_db):
        # Record a migration manually
        conn = sqlite3.connect(tmp_db)
        cursor = conn.cursor()
        migration._record_migration('nonexistent_mig', cursor)
        conn.commit()
        conn.close()
        with pytest.raises(FileNotFoundError):
            migration.rollback(steps=1)

    def test_nothing_to_rollback(self, migration):
        rolled = migration.rollback(steps=1)
        assert rolled == []


class TestMigrationStatus:

    def test_empty(self, migration):
        status = migration.migration_status()
        assert status['applied'] == []
        assert status['pending'] == []

    def test_with_applied(self, migration, tmp_path):
        mig_dir = str(tmp_path / 'migrations')
        os.makedirs(mig_dir, exist_ok=True)
        code = '''
from pybend.core.storage.sqlite_migration import Migration

class StatusTest(Migration):
    def up(self, cursor):
        pass
    def down(self, cursor):
        pass
'''
        with open(os.path.join(mig_dir, '001_status_test.py'), 'w') as f:
            f.write(code)
        migration.run_migrations()
        status = migration.migration_status()
        assert len(status['applied']) == 1
        assert status['pending'] == []

    def test_pending(self, migration, tmp_path):
        mig_dir = str(tmp_path / 'migrations')
        os.makedirs(mig_dir, exist_ok=True)
        code = '''
from pybend.core.storage.sqlite_migration import Migration

class PendingTest(Migration):
    def up(self, cursor):
        pass
    def down(self, cursor):
        pass
'''
        with open(os.path.join(mig_dir, '001_pending.py'), 'w') as f:
            f.write(code)
        status = migration.migration_status()
        assert '001_pending' in status['pending']
