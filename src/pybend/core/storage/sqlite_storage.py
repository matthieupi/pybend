# app/storage/sqlite_storage.py

import contextlib
import logging
import queue
import re
import sqlite3
from typing import Any, Dict, List, Type

from pydantic import BaseModel

from pybend.core import config
from pybend.core.utils.registrar import registered_models
from pybend.core.utils.introspection import get_list_fields, get_ref_fields
from pybend.core.utils.populate import PopulateSpec
from .abstract_storage import AbstractStorage
from .sqlite_migration import SQLiteMigration

logger = logging.getLogger('pybend.storage')


_SQLITE_NATIVE = (int, float, str, bytes, bool, type(None))


def _validate_identifier(name: str) -> str:
    """Validate and return a safe SQL identifier."""
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")
    return name


def _coerce_value(v):
    """Coerce a value to a type SQLite can bind.

    SQLite only accepts int, float, str, bytes, bool, None (and datetime via
    adapter).  Pydantic types like AnyHttpUrl survive model_dump() as objects,
    not plain strings.  Convert anything non-native to str so the binding
    doesn't raise ``sqlite3.ProgrammingError``.
    """
    if isinstance(v, _SQLITE_NATIVE):
        return v
    # datetime objects have a built-in SQLite adapter — let them through
    import datetime
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v
    return str(v)


class SQLiteStorage(AbstractStorage):
    """
    SQLite storage backend implementing the AbstractStorage.
    Delegates schema management to SQLiteMigration.

    Uses a connection pool to avoid opening/closing a connection per operation,
    and enables WAL mode so concurrent readers don't block on a writer.
    """

    def __init__(self, database: str = 'database.db', pool_size: int = 4):
        self.database = database
        self._migration = SQLiteMigration(database=database)

        # Connection pool: reuse connections instead of open/close per operation.
        # WAL mode is set on the first connection so it persists for the DB file.
        # check_same_thread=False is required because FastAPI/Starlette may
        # dispatch requests across threads; our pool handles thread safety.
        self._pool = queue.Queue(maxsize=pool_size)
        init_conn = sqlite3.connect(database, check_same_thread=False)
        init_conn.execute("PRAGMA journal_mode=WAL")
        init_conn.execute("PRAGMA busy_timeout=5000")
        self._pool.put(init_conn)

    def _get_conn(self):
        """Get a connection from the pool, or create a new one if empty."""
        try:
            return self._pool.get_nowait()
        except queue.Empty:
            conn = sqlite3.connect(self.database, check_same_thread=False)
            conn.execute("PRAGMA busy_timeout=5000")
            return conn

    def _put_conn(self, conn):
        """Return a connection to the pool, or close it if the pool is full."""
        try:
            self._pool.put_nowait(conn)
        except queue.Full:
            conn.close()

    @contextlib.contextmanager
    def _connection(self):
        """Context manager for pool-managed connections."""
        conn = self._get_conn()
        try:
            yield conn
        finally:
            self._put_conn(conn)

    # ──────────────────────────────────────────────
    # SCHEMA (delegated to SQLiteMigration)
    # ──────────────────────────────────────────────

    def create_table(self, model_class: Type[Any]):
        _validate_identifier(model_class.__tablename__)
        self._migration.create_table(model_class)

    def migrate_table(self, model_class: Type[Any]):
        _validate_identifier(model_class.__tablename__)
        self._migration.migrate_table(model_class)

    # ──────────────────────────────────────────────
    # CREATE
    # ──────────────────────────────────────────────

    def create(self, model_class: Type[Any], data: Dict[str, Any]) -> Any:
        logger.info("Creating new %s record", model_class.__name__)
        table_name = _validate_identifier(model_class.__tablename__)

        # Identify List[BaseModel] fields — these are NOT columns on this table
        collection_field_names = {name for name, _cls in get_list_fields(model_class)}

        fields = [f for f in model_class.model_fields.keys()
                  if f != 'id' and f not in collection_field_names]
        logger.debug("Fields: %s", fields)
        placeholders = ", ".join(['?'] * len(fields))
        columns = ", ".join(fields)
        # Extract values
        values = [data.get(field) for field in fields]
        # De-reference BaseModel instances to their IDs if they have an 'id' attribute
        values = [value.id
                  if isinstance(value, BaseModel) and hasattr(value, 'id') else value
                  for value in values]
        # Coerce non-native types (e.g. AnyHttpUrl) to SQLite-compatible values
        values = [_coerce_value(v) for v in values]
        insert_sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(insert_sql, values)
            conn.commit()
            data['id'] = cursor.lastrowid
        logger.info("Record created with ID: %s", data['id'])
        return model_class(**data)

    # ──────────────────────────────────────────────
    # LIST
    # ──────────────────────────────────────────────

    def list(self, model_class: Type[Any], sql_filter: tuple = None,
             limit: int = None, offset: int = None, populate: PopulateSpec = None) -> List[Any]:
        table_name = _validate_identifier(model_class.__tablename__)
        list_fields = get_list_fields(model_class)
        ref_fields = get_ref_fields(model_class)

        select_sql = f"SELECT * FROM {table_name}"
        filter_params = []
        if sql_filter is not None:
            clause, params = sql_filter
            if clause:
                select_sql += f" WHERE {clause}"
                filter_params = list(params) if params else []

        # Single pooled connection for count + query + hydration + populate
        with self._connection() as conn:
            cursor = conn.cursor()

            # Count total matching rows (before pagination)
            total = None
            if limit is not None:
                count_sql = select_sql.replace("SELECT *", "SELECT COUNT(*)", 1)
                cursor.execute(count_sql, filter_params[:])
                total = cursor.fetchone()[0]

            # Apply pagination
            paginated_params = filter_params[:]
            if limit is not None:
                select_sql += " LIMIT ?"
                paginated_params.append(limit)
                if offset is not None and offset > 0:
                    select_sql += " OFFSET ?"
                    paginated_params.append(offset)

            cursor.execute(select_sql, paginated_params)
            rows = cursor.fetchall()
            columns = [column[0] for column in cursor.description]

            # Build records from rows: coerce NULLs, hydrate Ref fields
            records = []
            for row in rows:
                record = dict(zip(columns, row))

                # Coerce NULL values to field defaults
                for key, val in record.items():
                    if val is None and key in model_class.model_fields:
                        field = model_class.model_fields[key]
                        if field.default is not None:
                            record[key] = field.default

                # Hydrate Ref[T] fields as href URLs
                for field_name, target_cls in ref_fields:
                    val = record.get(field_name)
                    if val is not None:
                        target_table = getattr(target_cls, '__tablename__', target_cls.__name__.lower())
                        record[field_name] = f"{config.API_URL}/{target_table}/{val}"

                records.append(record)

            # Batch-hydrate collection fields: one query per ListRef field
            # instead of one query per parent row per field (N×M → M queries).
            if list_fields:
                parent_ids = [r['id'] for r in records if r.get('id') is not None]
                for field_name, child_class in list_fields:
                    effective_cls = getattr(model_class, '__fk_models__', {}).get(field_name, child_class)
                    child_table = _validate_identifier(effective_cls.__tablename__)
                    if hasattr(effective_cls, '__owner__') and effective_cls.__owner__ is not None:
                        fk_col = _validate_identifier(f"{effective_cls.__owner__.__name__.lower()}_id")
                    else:
                        fk_col = _validate_identifier(f"{model_class.__name__.lower()}_id")

                    # Single batch query for all parents
                    grouped = {}
                    if parent_ids:
                        placeholders = ",".join(["?"] * len(parent_ids))
                        try:
                            cursor.execute(
                                f"SELECT id, {fk_col} FROM {child_table} WHERE {fk_col} IN ({placeholders})",
                                parent_ids
                            )
                            for child_id, parent_fk in cursor.fetchall():
                                grouped.setdefault(parent_fk, []).append(child_id)
                        except sqlite3.OperationalError:
                            pass

                    # Assign href arrays to each record
                    for record in records:
                        pid = record.get('id')
                        child_ids = grouped.get(pid, [])
                        record[field_name] = [
                            f"{config.API_URL}/{model_class.__tablename__}/{pid}/{field_name}/{cid}"
                            for cid in child_ids
                        ]

            results = [model_class(**record) for record in records]

            if populate and not populate.is_empty:
                self._populate_fields(model_class, results, populate, conn)

        if limit is not None:
            effective_offset = offset or 0
            return {
                'data': results,
                'meta': {
                    'total': total,
                    'limit': limit,
                    'offset': effective_offset,
                    'has_more': effective_offset + len(results) < total,
                }
            }
        return results

    # ──────────────────────────────────────────────
    # GET
    # ──────────────────────────────────────────────

    def get(self, model_class: Type[Any], id: int, as_dict: bool = False, populate: PopulateSpec = None) -> Any:
        table_name = _validate_identifier(model_class.__tablename__)
        select_sql = f"SELECT * FROM {table_name} WHERE id = ?"

        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(select_sql, (id,))
            row = cursor.fetchone()
            if not row:
                return None

            columns = [column[0] for column in cursor.description]
            record = dict(zip(columns, row))

            data = {}

            for field_name, field_info in model_class.model_fields.items():
                value = record.get(field_name)

                if value is not None:
                    data[field_name] = value
                    continue

                # If this is a nested Pydantic model (foreign key style)
                field_type = field_info.annotation
                if (
                        isinstance(field_type, type)
                        and issubclass(field_type, BaseModel)
                ):
                    fk_field = f"{field_name}_id"
                    fk_value = record.get(fk_field)

                    if fk_value is not None:
                        try:
                            fk_model = registered_models[field_type.__tablename__]
                            data[field_name] = fk_model(id=fk_value)
                        except Exception:
                            pass

            # ── Hydrate Ref[T] fields as href URLs ──
            for field_name, target_cls in get_ref_fields(model_class):
                val = data.get(field_name)
                if val is not None:
                    target_table = getattr(target_cls, '__tablename__', target_cls.__name__.lower())
                    data[field_name] = f"{config.API_URL}/{target_table}/{val}"

            # ── Hydrate collection fields as href arrays ──
            for field_name, child_class in get_list_fields(model_class):
                effective_cls = getattr(model_class, '__fk_models__', {}).get(field_name, child_class)
                child_table = _validate_identifier(effective_cls.__tablename__)
                if hasattr(effective_cls, '__owner__') and effective_cls.__owner__ is not None:
                    fk_col = _validate_identifier(f"{effective_cls.__owner__.__name__.lower()}_id")
                else:
                    fk_col = _validate_identifier(f"{model_class.__name__.lower()}_id")
                try:
                    cursor.execute(
                        f"SELECT id FROM {child_table} WHERE {fk_col} = ?", (id,)
                    )
                    child_rows = cursor.fetchall()
                    data[field_name] = [
                        f"{config.API_URL}/{model_class.__tablename__}/{id}/{field_name}/{row[0]}"
                        for row in child_rows
                    ]
                except sqlite3.OperationalError:
                    # Child table or FK column may not exist yet
                    data[field_name] = []

            instance = model_class(**data) if not as_dict else None

            if populate and not populate.is_empty and instance:
                self._populate_fields(model_class, [instance], populate, conn)

        if as_dict:
            return data
        return instance

    # ──────────────────────────────────────────────
    # POPULATE (eager loading)
    # ──────────────────────────────────────────────

    def _populate_fields(self, model_class, instances, populate, conn, _visited=None):
        """Batch-load related entities for a list of parent instances.

        Args:
            model_class: The parent model class
            instances: List of parent model instances
            populate: PopulateSpec controlling which fields to load
            conn: Open sqlite3 connection to reuse
            _visited: Set of model names already populated in this chain (cycle prevention)
        """
        if not instances:
            return

        if _visited is None:
            _visited = set()
        _visited = _visited | {model_class.__name__}  # immutable copy per branch

        list_fields = get_list_fields(model_class)
        ref_fields = get_ref_fields(model_class)
        cursor = conn.cursor()

        # ── Populate ListRef fields (collections) ──
        for field_name, child_class in list_fields:
            if not populate.should_populate(field_name):
                continue

            effective_cls = getattr(model_class, '__fk_models__', {}).get(field_name, child_class)
            actual_child_class = getattr(effective_cls, '__parent__', effective_cls)

            # Cycle check
            if actual_child_class.__name__ in _visited:
                continue

            child_table = _validate_identifier(effective_cls.__tablename__)
            if hasattr(effective_cls, '__owner__') and effective_cls.__owner__ is not None:
                fk_col = _validate_identifier(f"{effective_cls.__owner__.__name__.lower()}_id")
            else:
                fk_col = _validate_identifier(f"{model_class.__name__.lower()}_id")

            # Collect parent IDs
            parent_ids = [getattr(inst, 'id', None) for inst in instances]
            parent_ids = [pid for pid in parent_ids if pid is not None]
            if not parent_ids:
                continue

            # Batch query: SELECT * FROM child_table WHERE fk_col IN (?, ?, ...)
            placeholders = ",".join(["?"] * len(parent_ids))
            try:
                cursor.execute(
                    f"SELECT * FROM {child_table} WHERE {fk_col} IN ({placeholders})",
                    parent_ids
                )
                rows = cursor.fetchall()
                columns = [col[0] for col in cursor.description]
            except sqlite3.OperationalError:
                continue

            # Group by parent FK
            grouped = {}
            for row in rows:
                record = dict(zip(columns, row))
                parent_fk = record.get(fk_col)
                grouped.setdefault(parent_fk, []).append(record)

            child_spec = populate.child_spec(field_name)

            # Build child instances, apply per-parent limit, build {data, meta} wrapper
            for inst in instances:
                pid = getattr(inst, 'id', None)
                child_records = grouped.get(pid, [])
                total = len(child_records)
                capped = child_records[:child_spec.limit]

                # Coerce NULLs and hydrate Ref fields on all children first
                child_ref_fields = get_ref_fields(effective_cls)
                child_list_fields = get_list_fields(effective_cls)
                for rec in capped:
                    for key, val in rec.items():
                        if val is None and key in effective_cls.model_fields:
                            field_info = effective_cls.model_fields[key]
                            if field_info.default is not None:
                                rec[key] = field_info.default

                    for ref_name, target_cls in child_ref_fields:
                        val = rec.get(ref_name)
                        if val is not None:
                            target_table = getattr(target_cls, '__tablename__', target_cls.__name__.lower())
                            rec[ref_name] = f"{config.API_URL}/{target_table}/{val}"

                # Batch-hydrate child's own ListRef fields (one query per field,
                # not per child instance — same N+1 fix as in list()).
                if child_list_fields and capped:
                    child_ids = [r['id'] for r in capped if r.get('id') is not None]
                    for child_list_name, child_list_cls in child_list_fields:
                        child_effective = getattr(effective_cls, '__fk_models__', {}).get(child_list_name, child_list_cls)
                        child_list_table = _validate_identifier(child_effective.__tablename__)
                        if hasattr(child_effective, '__owner__') and child_effective.__owner__ is not None:
                            child_fk = _validate_identifier(f"{child_effective.__owner__.__name__.lower()}_id")
                        else:
                            child_fk = _validate_identifier(f"{effective_cls.__name__.lower()}_id")

                        sub_grouped = {}
                        if child_ids:
                            ph = ",".join(["?"] * len(child_ids))
                            try:
                                cursor.execute(
                                    f"SELECT id, {child_fk} FROM {child_list_table} WHERE {child_fk} IN ({ph})",
                                    child_ids
                                )
                                for sub_id, sub_fk in cursor.fetchall():
                                    sub_grouped.setdefault(sub_fk, []).append(sub_id)
                            except sqlite3.OperationalError:
                                pass

                        for rec in capped:
                            rid = rec.get('id')
                            sub_ids = sub_grouped.get(rid, [])
                            rec[child_list_name] = [
                                f"{config.API_URL}/{effective_cls.__tablename__}/{rid}/{child_list_name}/{sid}"
                                for sid in sub_ids
                            ]

                # Build child model instances and serialize
                child_dicts = []
                child_instances = []
                for rec in capped:
                    try:
                        child_inst = effective_cls(**rec)
                        child_instances.append(child_inst)
                        dumped = child_inst.model_response()
                        # Use parent-scoped URL for $id
                        dumped['$id'] = f"{config.API_URL}/{model_class.__tablename__}/{pid}/{field_name}/{rec.get('id')}"
                        child_dicts.append(dumped)
                    except Exception:
                        pass

                populated_wrapper = {
                    'data': child_dicts,
                    'meta': {
                        'total': total,
                        'limit': child_spec.limit,
                        'offset': 0,
                        'has_more': total > child_spec.limit,
                    }
                }

                if not hasattr(inst, '_populated') or inst._populated is None:
                    inst.__dict__['_populated'] = {}
                inst.__dict__['_populated'][field_name] = populated_wrapper

                # Recurse for nested populate
                if child_instances and not child_spec.is_empty:
                    self._populate_fields(effective_cls, child_instances, child_spec, conn, _visited)
                    # Overlay recursive population onto already-serialized dicts
                    for child_inst, child_dict in zip(child_instances, child_dicts):
                        nested_pop = getattr(child_inst, '_populated', None) or child_inst.__dict__.get('_populated')
                        if nested_pop:
                            child_dict.update(nested_pop)

        # ── Populate Ref fields (single FK) ──
        for field_name, target_cls in ref_fields:
            if not populate.should_populate(field_name):
                continue
            if target_cls.__name__ in _visited:
                continue

            target_table = _validate_identifier(getattr(target_cls, '__tablename__', target_cls.__name__.lower()))

            # Collect FK values (these are currently href strings — extract the ID)
            fk_ids = []
            for inst in instances:
                val = getattr(inst, field_name, None)
                if val is not None:
                    if isinstance(val, str) and '/' in val:
                        fk_id = val.rsplit('/', 1)[-1]
                    else:
                        fk_id = val
                    try:
                        fk_ids.append(int(fk_id))
                    except (ValueError, TypeError):
                        pass

            if not fk_ids:
                continue

            unique_ids = list(set(fk_ids))
            placeholders = ",".join(["?"] * len(unique_ids))
            try:
                cursor.execute(
                    f"SELECT * FROM {target_table} WHERE id IN ({placeholders})",
                    unique_ids
                )
                rows = cursor.fetchall()
                columns = [col[0] for col in cursor.description]
            except sqlite3.OperationalError:
                continue

            lookup = {}
            for row in rows:
                record = dict(zip(columns, row))
                try:
                    ref_inst = target_cls(**record)
                    dumped = ref_inst.model_response()
                    lookup[record['id']] = dumped
                except Exception:
                    pass

            for inst in instances:
                val = getattr(inst, field_name, None)
                if val is not None:
                    if isinstance(val, str) and '/' in val:
                        fk_id = int(val.rsplit('/', 1)[-1])
                    else:
                        fk_id = int(val)
                    ref_data = lookup.get(fk_id)
                    if ref_data:
                        if not hasattr(inst, '_populated') or inst._populated is None:
                            inst.__dict__['_populated'] = {}
                        inst.__dict__['_populated'][field_name] = ref_data

    # ──────────────────────────────────────────────
    # UPDATE
    # ──────────────────────────────────────────────

    def update(self, model_class: Type[Any], id: int, data: Dict[str, Any]):
        """
        Updates a record in the database for the given model class,
        using only the fields provided in the `data` dictionary.
        Prevents SQL injection by using parameterized queries.
        """
        table_name = _validate_identifier(model_class.__tablename__)

        # Identify List[BaseModel] fields — these are NOT columns on this table
        collection_field_names = {name for name, _cls in get_list_fields(model_class)}

        # Validate and filter the fields based on model annotations
        valid_fields = [f for f in model_class.model_fields.keys()
                        if f != 'id' and f not in collection_field_names]
        fields_to_update = [field for field in data.keys() if field in valid_fields]

        if not fields_to_update:
            raise ValueError("No valid fields provided to update.")

        # Construct the SET clause dynamically
        set_clause = ", ".join([f"{field} = ?" for field in fields_to_update])
        values = [_coerce_value(data[field]) for field in fields_to_update]

        # Add the id to the values for the WHERE clause
        update_sql = f"UPDATE {table_name} SET {set_clause} WHERE id = ?"
        values.append(id)

        # Execute the update query
        with self._connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(update_sql, values)
                conn.commit()
            except sqlite3.Error as e:
                raise RuntimeError(f"Database update failed: {e}")

    # ──────────────────────────────────────────────
    # DELETE
    # ──────────────────────────────────────────────

    def delete(self, model_class: Type[Any], id: int):
        table_name = _validate_identifier(model_class.__tablename__)
        delete_sql = f"DELETE FROM {table_name} WHERE id = ?"
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(delete_sql, (id,))
            conn.commit()