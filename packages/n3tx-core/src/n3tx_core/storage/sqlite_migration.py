"""Native SQLite model projection and explicit migration execution.

API: SQLiteMigration creates model tables and reconciles their columns, or
validates existing columns when auto_migrate=False. Migration supplies up/down
hooks for the separately invoked file-based runner and its migration ledger.
Boundary: model registration never runs migration files. Creation and validation
share one physical projection; opt-in constraints use static Field defaults.
Integration: SQLiteStorage delegates schema operations to this module."""

import importlib.util
import json
import logging
import os
import sqlite3
from abc import ABC, abstractmethod
from typing import Any, List, Type, Union, get_args

from pydantic import BaseModel

from n3tx_core.utils.introspection import _is_self_ref
from n3tx_core.models.ref import Ref

logger = logging.getLogger('n3tx.storage')


def _not_null_default(field_info) -> tuple[str, str] | None:
    """Return an opted-in SQL type/literal without evaluating default factories.

    Only static string and bool defaults are supported. Strings are quoted as
    data, never SQL expressions; invalid marked defaults raise ValueError."""
    # 0. Leave all unmarked fields on the native projection path.
    extra = field_info.json_schema_extra
    if not isinstance(extra, dict) or extra.get(
        'x-sqlite-not-null-default',
    ) is not True:
        return None
    # 1. Reject absent, nullable, factory and unsupported default values.
    default = field_info.default
    if field_info.default_factory is not None or type(default) not in (
        str, bool,
    ):
        raise ValueError(
            'x-sqlite-not-null-default requires a static string or bool default'
        )
    # 2. Bind Boolean storage to INTEGER and escape literal string contents.
    if type(default) is bool:
        return 'INTEGER', str(int(default))
    if '\x00' in default:
        raise ValueError('SQLite default string literals cannot contain NUL')
    return 'TEXT', "'" + default.replace("'", "''") + "'"


def _model_columns(
    model_class: Type[Any],
) -> dict[str, tuple[str, str | None]]:
    """Project native physical column names, SQL types and marked defaults.

    Unmarked types retain creation's existing mapping, including local nested
    models stored under an _id suffix and ordinary bools stored as TEXT."""
    # 0. Include native identity independently of the model's id annotation.
    columns: dict[str, tuple[str, str | None]] = {'id': ('INTEGER', None)}
    for field_name, field_info in model_class.model_fields.items():
        if field_name == 'id' or field_name.startswith('_'):
            continue
        default = None
        marked = _not_null_default(field_info)
        # 1. Preserve native self references and Optional[T] unwrapping.
        field_type = field_info.annotation
        origin_type = getattr(field_type, '__origin__', None)
        self_ref = _is_self_ref(field_type)
        if (
            not self_ref
            and origin_type is Union
            and type(None) in get_args(field_type)
        ):
            field_type = get_args(field_type)[0]
            origin_type = getattr(field_type, '__origin__', None)
        # 2. Project pointers/containers before local nested models and scalars.
        if marked is not None:
            sql_type, default = marked
        elif self_ref:
            sql_type = 'INTEGER'
        elif (
            origin_type in (Ref, list, dict)
            or field_type is dict
        ):
            sql_type = 'TEXT'
        elif isinstance(field_type, type) and issubclass(field_type, BaseModel):
            field_name = f'{field_name}_id'
            sql_type = 'INTEGER'
        elif field_type == int:
            sql_type = 'INTEGER'
        elif field_type == float:
            sql_type = 'REAL'
        else:
            sql_type = 'TEXT'
        if field_name in columns:
            raise sqlite3.OperationalError(
                f'duplicate column name: {field_name}'
            )
        columns[field_name] = (sql_type, default)
    return columns


class Migration(ABC):
    """Base hooks for user-written, explicitly executed migrations.

    API: implement up(cursor) and down(cursor) in each migration file.
    Integration: SQLiteMigration discovers files in its migrations directory
    and owns each hook's transaction and ledger update.

    Example (migrations/20250217_001_add_status_to_products.py):

        from n3tx_core.storage.sqlite_migration import Migration

        class AddStatusToProducts(Migration):
            def up(self, cursor):
                cursor.execute(
                    "ALTER TABLE products ADD COLUMN status "
                    "TEXT DEFAULT 'active'"
                )

            def down(self, cursor):
                cursor.execute(
                    "ALTER TABLE products DROP COLUMN status"
                )"""

    @abstractmethod
    def up(self, cursor: sqlite3.Cursor):
        """Apply the migration."""
        ...

    @abstractmethod
    def down(self, cursor: sqlite3.Cursor):
        """Reverse the migration."""
        ...


class SQLiteMigration:
    """Own model schema projection, validation and explicit manual migrations.

    API: create_table/migrate_table create model tables; default mode reconciles
    missing/orphaned columns. With auto_migrate=False, existing tables receive
    only column-name and marked-constraint validation, without DDL.
    Boundary: run_migrations/rollback explicitly execute files regardless of the
    flag. Manual ledger APIs initialize tracking on first use in false mode;
    ordinary model registration neither creates nor replays the ledger.
    Integration: SQLiteStorage passes its registration migration policy."""

    MIGRATIONS_TABLE = "_migrations"

    def __init__(
        self, database: str = 'database.db',
        migrations_dir: str = 'migrations', *,
        auto_migrate: bool = True,
    ):
        """Configure model policy and default-mode migration tracking."""
        # 0. Retain policy without opening the manual ledger in false mode.
        self.database = database
        self.migrations_dir = migrations_dir
        self.auto_migrate = auto_migrate
        if auto_migrate:
            self._ensure_migrations_table()

    def _create_relationship_indexes(
        self, cursor: sqlite3.Cursor, model_class: Type[Any],
    ):
        """Create indexes for generated relationship link models."""
        # 0. Resolve the generated link model's declared endpoints.
        relationship = getattr(model_class, '__relationship__', None)
        if (
            not relationship
            or getattr(relationship, 'kind', None) != 'many_to_many'
        ):
            return

        table_name = model_class.__tablename__
        owner_fk = relationship.owner_fk
        target_fk = relationship.target_fk
        if not owner_fk or not target_fk:
            return
        # 1. Create native endpoint lookup and pair uniqueness indexes.
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{table_name}_{owner_fk} "
            f"ON {table_name} ({owner_fk})"
        )
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{table_name}_{target_fk} "
            f"ON {table_name} ({target_fk})"
        )
        cursor.execute(
            f"CREATE UNIQUE INDEX IF NOT EXISTS "
            f"idx_{table_name}_{owner_fk}_{target_fk}_unique "
            f"ON {table_name} ({owner_fk}, {target_fk})"
        )

    # ══════════════════════════════════════════════
    # Internal: migrations tracking table
    # ══════════════════════════════════════════════

    def _ensure_migrations_table(self):
        """Create the _migrations tracking table if it doesn't exist."""
        # 0. Initialize tracking through default setup or manual ledger use.
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
        # 0. Explicit manual APIs retain ledger setup in non-migrating mode.
        if not self.auto_migrate:
            self._ensure_migrations_table()
        # 1. Read recorded names without executing migration files.
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

    def _validate_columns(
        self, cursor: sqlite3.Cursor, table_name: str,
        columns: dict[str, tuple[str, str | None]],
    ) -> bool:
        """Validate an existing projection or return False for an absent table.

        Only marked columns require exact SQL type, NOT NULL and literal default
        metadata. Missing/surplus columns or marked mismatches raise ValueError;
        unrelated tables and unmarked constraints are not inspected."""
        # 0. Compare native physical names, not logical model field names.
        cursor.execute(f'PRAGMA table_xinfo({table_name})')
        existing = {row[1]: row for row in cursor.fetchall()}
        if not existing:
            return False
        missing = columns.keys() - existing.keys()
        surplus = existing.keys() - columns.keys()
        if missing or surplus:
            raise ValueError(
                f'SQLite schema mismatch for {table_name}: '
                f'missing columns {sorted(missing)}, '
                f'surplus columns {sorted(surplus)}; auto_migrate=False'
            )
        # 1. Refuse marked constraint drift without executing or repairing DDL.
        for name, (sql_type, default) in columns.items():
            if default is None:
                continue
            row = existing[name]
            if (
                row[2].upper() != sql_type
                or row[3] != 1
                or row[4] != default
            ):
                raise ValueError(
                    f'SQLite constraint mismatch for {table_name}.{name}: '
                    f'expected {sql_type} NOT NULL DEFAULT {default}; '
                    'auto_migrate=False'
                )
        return True

    def create_table(self, model_class: Type[Any]):
        """Create native columns, or validate existing tables in false mode.

        Plain lists use JSON TEXT. Marked fields use their static literal SQL
        default and NOT NULL. Existing false-mode tables receive no DDL."""
        # 0. Resolve the same physical projection used by false-mode validation.
        table_name = model_class.__tablename__
        columns = _model_columns(model_class)
        definitions = ['id INTEGER PRIMARY KEY AUTOINCREMENT']
        for name, (sql_type, default) in columns.items():
            if name == 'id':
                continue
            definition = f'{name} {sql_type}'
            if default is not None:
                definition += f' NOT NULL DEFAULT {default}'
            definitions.append(definition)
        columns_sql = ', '.join(definitions)
        if_not_exists = 'IF NOT EXISTS ' if self.auto_migrate else ''
        create_table_sql = (
            f'CREATE TABLE {if_not_exists}{table_name} ({columns_sql})'
        )
        # 1. Refuse incompatible existing tables before any model DDL.
        conn = sqlite3.connect(self.database)
        try:
            cursor = conn.cursor()
            if not self.auto_migrate and self._validate_columns(
                cursor, table_name, columns,
            ):
                return
            # 2. Create the absent table and its native relationship indexes.
            cursor.execute(create_table_sql)
            for field_name, field_info in model_class.model_fields.items():
                if _is_self_ref(field_info.annotation):
                    cursor.execute(
                        f'CREATE INDEX IF NOT EXISTS '
                        f'idx_{table_name}_{field_name} '
                        f'ON {table_name} ({field_name})'
                    )
            self._create_relationship_indexes(cursor, model_class)
            conn.commit()
        finally:
            conn.close()

    # ══════════════════════════════════════════════
    # Auto-migration: migrate_table
    # ══════════════════════════════════════════════

    def migrate_table(self, model_class: Type[Any]):
        """Reconcile model columns, or create/validate without migration DDL.

        Default mode retains native ADD/DROP behavior for unmarked fields.
        False mode shares creation's projection and never repairs existing
        tables; incompatible names or marked constraints raise ValueError."""
        # 0. Use creation/validation rather than legacy ADD/DROP in false mode.
        if not self.auto_migrate:
            self.create_table(model_class)
            return
        # 1. Validate marked declarations before default-mode schema changes.
        projected_columns = _model_columns(model_class)
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
            # 2. Add missing marked columns with their declared constraints.
            marked_column = projected_columns.get(field_name)
            if marked_column is not None and marked_column[1] is not None:
                if field_name not in existing_columns:
                    sql_type, default = marked_column
                    try:
                        cursor.execute(
                            f'ALTER TABLE {table_name} ADD COLUMN '
                            f'{field_name} {sql_type} '
                            f'NOT NULL DEFAULT {default}'
                        )
                        logger.info(
                            "Added marked column '%s' to '%s' as %s",
                            field_name, table_name, sql_type,
                        )
                    except sqlite3.OperationalError as e:
                        logger.warning(
                            'Failed to add marked column %s to %s: %s',
                            field_name, table_name, e,
                        )
                continue
            # 3. Preserve native unmarked column types and type-based defaults.
            # Handle Ref['self'] fields — self-referential FK stored as INTEGER
            if _is_self_ref(field_type):
                if field_name == 'id' or field_name in existing_columns:
                    continue
                try:
                    alter_sql = (
                        f"ALTER TABLE {table_name} ADD COLUMN "
                        f"{field_name} INTEGER DEFAULT NULL"
                    )
                    cursor.execute(alter_sql)
                    logger.info(
                        "Added selfref column '%s' to '%s' as INTEGER",
                        field_name, table_name,
                    )
                except sqlite3.OperationalError as e:
                    logger.warning(
                        "Failed to add selfref column %s to %s: %s",
                        field_name, table_name, e,
                    )
                continue

            origin_type = getattr(field_type, '__origin__', None)
            base_type = field_type
            if origin_type is not None:
                base_type = field_type.__args__[0]

            # Handle Optional[T]
            if origin_type is Union and type(None) in get_args(field_type):
                field_type = get_args(field_type)[0]
                origin_type = getattr(field_type, '__origin__', None)

            # Ref[T] may store local ids or canonical distributed ref strings.
            if origin_type is Ref:
                if field_name != 'id' and field_name not in existing_columns:
                    try:
                        alter_sql = (
                            f"ALTER TABLE {table_name} ADD COLUMN "
                            f"{field_name} TEXT DEFAULT NULL"
                        )
                        cursor.execute(alter_sql)
                        logger.info(
                            "Added Ref column '%s' to '%s' as TEXT",
                            field_name, table_name,
                        )
                    except sqlite3.OperationalError as e:
                        logger.warning(
                            "Failed to add Ref column %s to %s: %s",
                            field_name, table_name, e,
                        )
                continue

            # dict fields → TEXT column (JSON serialized)
            if field_type is dict or origin_type is dict:
                if field_name != 'id' and field_name not in existing_columns:
                    try:
                        alter_sql = (
                            f"ALTER TABLE {table_name} ADD COLUMN "
                            f"{field_name} TEXT DEFAULT '{{}}'"
                        )
                        cursor.execute(alter_sql)
                        logger.info(
                            "Added JSON dict column '%s' to '%s' as TEXT",
                            field_name, table_name,
                        )
                    except sqlite3.OperationalError as e:
                        logger.warning(
                            "Failed to add dict column %s to %s: %s",
                            field_name, table_name, e,
                        )
                continue

            if (
                isinstance(field_type, type)
                and issubclass(field_type, BaseModel)
            ):
                model_columns[f"{field_name}_id"] = model_columns.pop(
                    field_name,
                )
                field_name = f"{field_name}_id"

            # Skip 'id' and fields that already exist in the table
            if field_name == 'id' or field_name in existing_columns:
                continue

            logger.debug(
                "Processing field '%s' of type '%s' in model '%s'",
                field_name, field_type, model_class.__name__,
            )

            if (
                isinstance(field_type, type)
                and issubclass(field_type, BaseModel)
            ):
                sql_type = 'INTEGER'
                default_value = 0
            elif origin_type is list or origin_type is List:
                sql_type = 'TEXT'
                default_value = json.dumps([])
            elif base_type == bool:
                sql_type = 'INTEGER'
                default_value = 0
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
                alter_sql = (
                    f"ALTER TABLE {table_name} ADD COLUMN "
                    f"{field_name} {sql_type} DEFAULT {repr(default_value)}"
                )
                cursor.execute(alter_sql)
                logger.info(
                    "Added column '%s' to '%s' as %s",
                    field_name, table_name, sql_type,
                )
            except sqlite3.OperationalError as e:
                logger.warning(
                    "Failed to add column %s to %s: %s",
                    field_name, table_name, e,
                )
        # 4. Retain default-mode removal of orphaned and private columns.
        for col in existing_columns:
            if col not in model_columns or col.startswith('_'):
                try:
                    cursor.execute(
                        f"ALTER TABLE {table_name} DROP COLUMN {col}"
                    )
                    logger.info(
                        "Removed column '%s' from '%s'", col, table_name,
                    )
                except sqlite3.OperationalError as e:
                    logger.warning(
                        "Failed to remove column %s from %s: %s",
                        col, table_name, e,
                    )
        # 5. Preserve native index reconciliation and commit in default mode.
        for field_name, field_info in model_class.model_fields.items():
            if _is_self_ref(field_info.annotation):
                try:
                    cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS "
                        f"idx_{table_name}_{field_name} "
                        f"ON {table_name} ({field_name})"
                    )
                except sqlite3.OperationalError:
                    pass
        try:
            self._create_relationship_indexes(cursor, model_class)
        except sqlite3.OperationalError:
            pass

        conn.commit()
        conn.close()

    # ══════════════════════════════════════════════
    # Manual migrations: Rails-style runner
    # ══════════════════════════════════════════════

    def _discover_migrations(self) -> list:
        """Return migration filenames sorted for the explicit manual runner.

        Use YYYYMMDD_NNN_description.py files defining a Migration subclass."""
        # 0. Discover non-private Python files without importing their contents.
        if not os.path.isdir(self.migrations_dir):
            return []

        files = sorted(
            f for f in os.listdir(self.migrations_dir)
            if f.endswith('.py') and not f.startswith('_')
        )
        return files

    def _load_migration_class(self, filename: str) -> Migration:
        """Import one migration file and instantiate its Migration subclass."""
        # 0. Execute the explicit migration module, not ordinary registration.
        filepath = os.path.join(self.migrations_dir, filename)
        module_name = filename[:-3]  # strip .py

        spec = importlib.util.spec_from_file_location(module_name, filepath)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # 1. Resolve the first concrete migration class or reject the file.
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
                "Each migration file must define a class "
                "inheriting from Migration."
            )

        return migration_cls()

    def run_migrations(self):
        """Apply pending manual migrations, each in its own transaction.

        Return applied names; auto_migrate does not gate this explicit API."""
        # 0. Initialize manual tracking and select unapplied files.
        applied = self._get_applied_migrations()
        files = self._discover_migrations()
        newly_applied = []
        # 1. Commit each up hook and ledger record, rolling back failed hooks.
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
        """Reverse the last N manual migrations and return rolled-back names.

        auto_migrate controls registration only; down hooks remain explicit."""
        # 0. Initialize manual tracking and select the most recently applied.
        if not self.auto_migrate:
            self._ensure_migrations_table()
        conn = sqlite3.connect(self.database)
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT name FROM {self.MIGRATIONS_TABLE} "
            "ORDER BY id DESC LIMIT ?",
            (steps,)
        )
        to_rollback = [row[0] for row in cursor.fetchall()]
        conn.close()
        # 1. Commit each down hook and ledger removal in its own transaction.
        rolled_back = []
        for name in to_rollback:
            filename = f"{name}.py"
            filepath = os.path.join(self.migrations_dir, filename)

            if not os.path.exists(filepath):
                raise FileNotFoundError(
                    f"Migration file '{filename}' not found in "
                    f"'{self.migrations_dir}'. "
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
        """Return applied name/timestamp pairs and pending migration names.

        Like other manual ledger APIs, first use initializes tracking even when
        ordinary model registration has auto_migrate=False."""
        # 0. Initialize manual tracking and compare recorded/discovered names.
        applied = self._get_applied_migrations()
        files = self._discover_migrations()

        all_names = [f[:-3] for f in files]
        pending = [n for n in all_names if n not in applied]
        # 1. Preserve application order and timestamps in the public status.
        conn = sqlite3.connect(self.database)
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT name, applied_at FROM {self.MIGRATIONS_TABLE} "
            "ORDER BY id ASC"
        )
        applied_list = [(row[0], row[1]) for row in cursor.fetchall()]
        conn.close()

        return {
            "applied": applied_list,
            "pending": pending,
        }


# Changelog
# - 2026-11-12:
#   - Share native physical projection between table creation and validation.
#   - Add non-migrating registration without existing-table or ledger DDL.
#   - Derive opt-in NOT NULL string/bool defaults as safe SQL literals.
