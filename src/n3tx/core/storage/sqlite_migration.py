# app/storage/sqlite_migration.py

import importlib.util
import json
import logging
import os
import sqlite3
from abc import ABC, abstractmethod
from typing import Any, List, Type, Union, get_args, get_origin

from pydantic import BaseModel

from .sqlite_helpers import get_parent_fk_columns
from n3tx.core.utils.introspection import _is_self_ref

logger = logging.getLogger('n3tx.storage')


class Migration(ABC):
    """
    Base class for user-written migrations (Rails-style).

    Each migration file in the migrations/ folder should define a class
    that inherits from Migration and implements up() and down().

    Example (migrations/20250217_001_add_status_to_products.py):

        from storage.sqlite_migration import Migration

        class AddStatusToProducts(Migration):
            def up(self, cursor):
                cursor.execute(
                    "ALTER TABLE products ADD COLUMN status TEXT DEFAULT 'active'"
                )

            def down(self, cursor):
                cursor.execute(
                    "ALTER TABLE products DROP COLUMN status"
                )
    """

    @abstractmethod
    def up(self, cursor: sqlite3.Cursor):
        """Apply the migration."""
        ...

    @abstractmethod
    def down(self, cursor: sqlite3.Cursor):
        """Reverse the migration."""
        ...


class SQLiteMigration:
    """
    Handles all schema management for the SQLite backend:

    1. Auto-migrations — create_table / migrate_table based on Pydantic models
    2. Manual migrations — Rails-style timestamped migration files with up/down
    """

    MIGRATIONS_TABLE = "_migrations"

    def __init__(self, database: str = 'database.db', migrations_dir: str = 'migrations'):
        self.database = database
        self.migrations_dir = migrations_dir
        self._ensure_migrations_table()

    # ══════════════════════════════════════════════
    # Internal: migrations tracking table
    # ══════════════════════════════════════════════

    def _ensure_migrations_table(self):
        """Create the _migrations tracking table if it doesn't exist."""
        conn = sqlite3.connect(self.database)
        cursor = conn.cursor()
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.MIGRATIONS_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def _get_applied_migrations(self) -> set:
        """Return the set of migration names that have already been applied."""
        conn = sqlite3.connect(self.database)
        cursor = conn.cursor()
        cursor.execute(f"SELECT name FROM {self.MIGRATIONS_TABLE}")
        applied = {row[0] for row in cursor.fetchall()}
        conn.close()
        return applied

    def _record_migration(self, name: str, cursor: sqlite3.Cursor):
        """Mark a migration as applied."""
        cursor.execute(
            f"INSERT INTO {self.MIGRATIONS_TABLE} (name) VALUES (?)", (name,)
        )

    def _unrecord_migration(self, name: str, cursor: sqlite3.Cursor):
        """Remove a migration from the applied set (for rollback)."""
        cursor.execute(
            f"DELETE FROM {self.MIGRATIONS_TABLE} WHERE name = ?", (name,)
        )

    # ══════════════════════════════════════════════
    # Auto-migration: create_table
    # ══════════════════════════════════════════════

    def create_table(self, model_class: Type[Any]):
        """
        Creates a table for the given Pydantic model class.
        Automatically adds FK columns for parent List[BaseModel] relationships.
        Raises ValueError if an auto-generated FK column conflicts with a
        column already declared on the model.
        """
        table_name = model_class.__tablename__
        columns = []

        for field_name, field_info in model_class.model_fields.items():
            field_type = field_info.annotation
            if field_name == 'id' or field_name.startswith('_') or field_name.startswith('__'):
                continue

            origin_type = getattr(field_type, '__origin__', None)
            # Handle Ref['self'] fields — self-referential FK stored as INTEGER
            if _is_self_ref(field_type):
                columns.append(f"{field_name} INTEGER")
                continue

            # Handle Optional[T]
            if origin_type is Union and type(None) in get_args(field_type):
                field_type = get_args(field_type)[0]
                origin_type = getattr(field_type, '__origin__', None)

            # Skip List[BaseModel] fields — stored via FK on the child table
            if origin_type is list:
                continue

            # Handle nested Pydantic model
            if isinstance(field_type, type) and issubclass(field_type, BaseModel):
                sql_type = 'INTEGER'
                field_name = f"{field_name}_id"
            elif field_type == int:
                sql_type = 'INTEGER'
            elif field_type == float:
                sql_type = 'REAL'
            elif field_type == str:
                sql_type = 'TEXT'
            else:
                sql_type = 'TEXT'
            columns.append(f"{field_name} {sql_type}")

        # Auto-add FK columns for any parent that declares List[this_model]
        existing_col_names = {c.split()[0] for c in columns}
        for _parent_name, fk_col in get_parent_fk_columns(model_class):
            if fk_col in existing_col_names:
                raise ValueError(
                    f"Duplicate FK column '{fk_col}' on model '{model_class.__name__}': "
                    f"the column is both declared on the model and auto-generated from a "
                    f"List[{model_class.__name__}] relationship. Remove the explicit "
                    f"declaration or rename it to avoid conflicts."
                )
            columns.append(f"{fk_col} INTEGER")
            existing_col_names.add(fk_col)

        columns_sql = ", ".join(columns)
        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            {columns_sql}
        )
        """
        conn = sqlite3.connect(self.database)
        cursor = conn.cursor()
        cursor.execute(create_table_sql)

        # Create indexes on FK columns for efficient hydration queries
        for _parent_name, fk_col in get_parent_fk_columns(model_class):
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_{fk_col} ON {table_name} ({fk_col})")
        for field_name, field_info in model_class.model_fields.items():
            if _is_self_ref(field_info.annotation):
                cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_{field_name} ON {table_name} ({field_name})")

        conn.commit()
        conn.close()

    # ══════════════════════════════════════════════
    # Auto-migration: migrate_table
    # ══════════════════════════════════════════════

    def migrate_table(self, model_class: Type[Any]):
        """
        Adds missing columns to existing tables based on the model definition.
        Removes orphaned columns that no longer exist on the model.
        Automatically adds FK columns for parent List[BaseModel] relationships.
        Raises ValueError on FK column conflicts.
        """
        table_name = model_class.__tablename__
        existing_columns = set()
        model_columns = dict(model_class.model_fields)

        conn = sqlite3.connect(self.database)
        cursor = conn.cursor()
        try:
            cursor.execute(f"PRAGMA table_info({table_name})")
            existing_columns = {row[1] for row in cursor.fetchall()}
        except sqlite3.OperationalError:
            existing_columns = set()

        for field_name, field_info in list(model_columns.items()):
            field_type = field_info.annotation

            # Handle Ref['self'] fields — self-referential FK stored as INTEGER
            if _is_self_ref(field_type):
                if field_name == 'id' or field_name in existing_columns:
                    continue
                try:
                    alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {field_name} INTEGER DEFAULT NULL"
                    cursor.execute(alter_sql)
                    logger.info("Added selfref column '%s' to '%s' as INTEGER", field_name, table_name)
                except sqlite3.OperationalError as e:
                    logger.warning("Failed to add selfref column %s to %s: %s", field_name, table_name, e)
                continue

            origin_type = getattr(field_type, '__origin__', None)
            base_type = field_type
            if origin_type is not None:
                base_type = field_type.__args__[0]

            # Handle Optional[T]
            if origin_type is Union and type(None) in get_args(field_type):
                field_type = get_args(field_type)[0]
                origin_type = getattr(field_type, '__origin__', None)

            # Skip List[BaseModel] fields — stored via FK on the child table
            if origin_type is list:
                model_columns.pop(field_name, None)
                continue

            if isinstance(field_type, type) and issubclass(field_type, BaseModel):
                model_columns[f"{field_name}_id"] = model_columns.pop(field_name)
                field_name = f"{field_name}_id"

            # Skip 'id' and fields that already exist in the table
            if field_name == 'id' or field_name in existing_columns:
                continue

            logger.debug("Processing field '%s' of type '%s' in model '%s'", field_name, field_type, model_class.__name__)

            if isinstance(field_type, type) and issubclass(field_type, BaseModel):
                sql_type = 'INTEGER'
                default_value = 0
            elif origin_type is list or origin_type is List:
                sql_type = 'TEXT'
                default_value = json.dumps([])
            elif base_type == int:
                sql_type = 'INTEGER'
                default_value = '0'
            elif base_type == float:
                sql_type = 'REAL'
                default_value = '0.0'
            elif base_type == str:
                sql_type = 'TEXT'
                default_value = "''"
            else:
                sql_type = 'TEXT'
                default_value = "''"

            try:
                alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {field_name} {sql_type} DEFAULT {repr(default_value)}"
                cursor.execute(alter_sql)
                logger.info("Added column '%s' to '%s' as %s", field_name, table_name, sql_type)
            except sqlite3.OperationalError as e:
                logger.warning("Failed to add column %s to %s: %s", field_name, table_name, e)

        # Remove orphaned columns
        for col in existing_columns:
            if col not in model_columns or col.startswith('_') or col.startswith('__'):
                try:
                    cursor.execute(f"ALTER TABLE {table_name} DROP COLUMN {col}")
                    logger.info("Removed column '%s' from '%s'", col, table_name)
                except sqlite3.OperationalError as e:
                    logger.warning("Failed to remove column %s from %s: %s", col, table_name, e)

        # Auto-add FK columns for parent List[BaseModel] relationships
        model_col_names = set(model_columns.keys())
        for _parent_name, fk_col in get_parent_fk_columns(model_class):
            if fk_col in model_col_names:
                raise ValueError(
                    f"Duplicate FK column '{fk_col}' on model '{model_class.__name__}': "
                    f"the column is both declared on the model and auto-generated from a "
                    f"List[{model_class.__name__}] relationship. Remove the explicit "
                    f"declaration or rename it to avoid conflicts."
                )
            if fk_col not in existing_columns:
                try:
                    alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {fk_col} INTEGER DEFAULT 0"
                    cursor.execute(alter_sql)
                    logger.info("Added parent FK column '%s' to '%s' as INTEGER", fk_col, table_name)
                except sqlite3.OperationalError as e:
                    logger.warning("FK column %s already exists or error: %s", fk_col, e)

        # Ensure FK columns have indexes for efficient hydration queries
        for _parent_name, fk_col in get_parent_fk_columns(model_class):
            try:
                cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_{fk_col} ON {table_name} ({fk_col})")
            except sqlite3.OperationalError:
                pass
        for field_name, field_info in model_class.model_fields.items():
            if _is_self_ref(field_info.annotation):
                try:
                    cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_{field_name} ON {table_name} ({field_name})")
                except sqlite3.OperationalError:
                    pass

        conn.commit()
        conn.close()

    # ══════════════════════════════════════════════
    # Manual migrations: Rails-style runner
    # ══════════════════════════════════════════════

    def _discover_migrations(self) -> list:
        """
        Scans the migrations/ directory for Python files and returns them
        sorted by filename. Each file should contain exactly one class
        that inherits from Migration.

        Naming convention: YYYYMMDD_NNN_description.py
            e.g. 20250217_001_add_status_to_products.py
        """
        if not os.path.isdir(self.migrations_dir):
            return []

        files = sorted(
            f for f in os.listdir(self.migrations_dir)
            if f.endswith('.py') and not f.startswith('_')
        )
        return files

    def _load_migration_class(self, filename: str) -> Migration:
        """
        Dynamically imports a migration file and returns an instance
        of the Migration subclass defined in it.
        """
        filepath = os.path.join(self.migrations_dir, filename)
        module_name = filename[:-3]  # strip .py

        spec = importlib.util.spec_from_file_location(module_name, filepath)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Find the Migration subclass in the module
        migration_cls = None
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, Migration)
                and attr is not Migration
            ):
                migration_cls = attr
                break

        if migration_cls is None:
            raise ValueError(
                f"No Migration subclass found in '{filename}'. "
                f"Each migration file must define a class inheriting from Migration."
            )

        return migration_cls()

    def run_migrations(self):
        """
        Discovers and applies all pending migrations in order.
        Each migration runs inside its own transaction.

        Returns the list of migration names that were applied.
        """
        applied = self._get_applied_migrations()
        files = self._discover_migrations()
        newly_applied = []

        for filename in files:
            name = filename[:-3]  # strip .py
            if name in applied:
                continue

            logger.info("Applying migration: %s", name)
            migration = self._load_migration_class(filename)

            conn = sqlite3.connect(self.database)
            cursor = conn.cursor()
            try:
                migration.up(cursor)
                self._record_migration(name, cursor)
                conn.commit()
                newly_applied.append(name)
                logger.info("Applied migration: %s", name)
            except Exception as e:
                conn.rollback()
                raise RuntimeError(
                    f"Migration '{name}' failed during up(): {e}"
                ) from e
            finally:
                conn.close()

        if not newly_applied:
            logger.debug("No pending migrations.")

        return newly_applied

    def rollback(self, steps: int = 1):
        """
        Rolls back the last N applied migrations in reverse order.

        Returns the list of migration names that were rolled back.
        """
        conn = sqlite3.connect(self.database)
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT name FROM {self.MIGRATIONS_TABLE} ORDER BY id DESC LIMIT ?",
            (steps,)
        )
        to_rollback = [row[0] for row in cursor.fetchall()]
        conn.close()

        rolled_back = []
        for name in to_rollback:
            filename = f"{name}.py"
            filepath = os.path.join(self.migrations_dir, filename)

            if not os.path.exists(filepath):
                raise FileNotFoundError(
                    f"Migration file '{filename}' not found in '{self.migrations_dir}'. "
                    f"Cannot rollback '{name}'."
                )

            logger.info("Rolling back migration: %s", name)
            migration = self._load_migration_class(filename)

            conn = sqlite3.connect(self.database)
            cursor = conn.cursor()
            try:
                migration.down(cursor)
                self._unrecord_migration(name, cursor)
                conn.commit()
                rolled_back.append(name)
                logger.info("Rolled back migration: %s", name)
            except Exception as e:
                conn.rollback()
                raise RuntimeError(
                    f"Migration '{name}' failed during down(): {e}"
                ) from e
            finally:
                conn.close()

        if not rolled_back:
            logger.debug("Nothing to rollback.")

        return rolled_back

    def migration_status(self) -> dict:
        """
        Returns a dict with:
            - applied: list of applied migration names (in order)
            - pending: list of discovered but not-yet-applied migration names
        """
        applied = self._get_applied_migrations()
        files = self._discover_migrations()

        all_names = [f[:-3] for f in files]
        pending = [n for n in all_names if n not in applied]

        # Get applied in order
        conn = sqlite3.connect(self.database)
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT name, applied_at FROM {self.MIGRATIONS_TABLE} ORDER BY id ASC"
        )
        applied_list = [(row[0], row[1]) for row in cursor.fetchall()]
        conn.close()

        return {
            "applied": applied_list,
            "pending": pending,
        }