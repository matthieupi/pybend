"""Native SQLite persistence, pooled connections and explicit row conversion.

API: SQLiteStorage provides model CRUD, ordering, hydration and population.
Boundary: StorableMixin validates model updates and caller conditions; storage
executes trusted SQL predicates and does not enforce route authorization.
Integration: inject a registered backend through model registration."""

import contextlib
import asyncio
import inspect
import json
import logging
import queue
import re
import sqlite3
from types import UnionType
from typing import Any, Dict, List, Type, get_args, get_origin, Union

from pydantic import BaseModel

from n3tx_core import config
from n3tx_core.utils.introspection import (
    get_json_fields,
    get_fk_list_fields,
    get_ref_fields,
    get_ref_list_fields,
)
from n3tx_core.utils.populate import PopulateSpec
from n3tx_core.utils.where import query_field
from n3tx_core.models.ref import Ref, is_ref_url, local_ref_id, public_id_url
from .abstract_storage import AbstractStorage
from .sqlite_migration import SQLiteMigration

logger = logging.getLogger('n3tx.storage')


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
    doesn't raise ``sqlite3.ProgrammingError``. """
    # 0. Preserve native scalars and SQLite datetime adapters.
    if isinstance(v, _SQLITE_NATIVE):
        return v
    # datetime objects have a built-in SQLite adapter — let them through
    import datetime
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v
    # 1. Encode containers and coerce remaining native extension values.
    if isinstance(v, (dict, list)):
        return json.dumps(v, default=str)
    return str(v)


def _is_bool_field(field_info) -> bool:
    """Return True when a model field accepts bool values.

    SQLite databases can contain legacy empty-string values for bool columns
    created by older migrations or hand-written schema changes. Detecting the
    field type lets the read path normalize only bool fields before Pydantic
    validation, without changing ordinary string data. """
    # 0. Recognize scalar and nullable boolean annotations.
    annotation = field_info.annotation
    if annotation is bool:
        return True

    origin = get_origin(annotation)
    if origin in (Union, UnionType):
        return bool in get_args(annotation)

    return False


def _is_nullable_numeric_field(field_info) -> bool:
    """Return True when a model field accepts None plus numeric values."""
    # 0. Distinguish nullable numeric unions from scalar annotations.
    annotation = field_info.annotation
    if annotation in (int, float):
        return False

    origin = get_origin(annotation)
    if origin not in (Union, UnionType):
        return False

    args = set(get_args(annotation))
    return type(None) in args and bool(args & {int, float})


def _normalize_storage_value(field_info, value):
    """Normalize legacy form/storage sentinels before SQLite bind/validation."""
    if _is_nullable_numeric_field(field_info) and value in ('', "''"):
        return None
    return value


def _deserialize_bool_fields(model_class, record):
    """Normalize legacy empty-string bool values before model validation."""
    # 0. Normalize only fields explicitly accepting boolean values.
    for field_name, field_info in model_class.model_fields.items():
        if not _is_bool_field(field_info):
            continue
        if record.get(field_name) in ('', "''"):
            record[field_name] = False


def _deserialize_nullable_numeric_fields(model_class, record):
    """Normalize legacy empty-string nullable numerics before validation."""
    # 0. Normalize present fields without introducing omitted values.
    for field_name, field_info in model_class.model_fields.items():
        if field_name not in record:
            continue
        record[field_name] = _normalize_storage_value(
            field_info, record.get(field_name),
        )


def _deserialize_json_fields(model_class, record):
    """Deserialize DB strings back into model-compatible Python values."""
    # 0. Normalize historical scalar sentinels before parsing JSON columns.
    _deserialize_bool_fields(model_class, record)
    _deserialize_nullable_numeric_fields(model_class, record)
    for field_name in get_json_fields(model_class):
        val = record.get(field_name)
        if isinstance(val, str):
            try:
                record[field_name] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                pass


def _normalize_ref_storage_values(model_class, data):
    """Validate Ref[T] URL values before SQLite writes."""
    # 0. Validate scalar references without hydration.
    for field_name, target_cls in get_ref_fields(model_class):
        if field_name in data and data[field_name] is not None:
            value = Ref.url(data[field_name])
            if Ref.schema(value) != target_cls.__name__:
                raise ValueError(f"Reference target mismatch for {field_name}")
            data[field_name] = value
    # 1. Preserve pointer-list ordering while validating each target type.
    for field_name, target_cls in get_ref_list_fields(model_class):
        if field_name not in data or data[field_name] is None:
            continue
        value = data[field_name]
        if isinstance(value, list):
            refs = []
            for item in value:
                ref = Ref.url(item)
                if Ref.schema(ref) != target_cls.__name__:
                    raise ValueError(
                        f"Reference target mismatch for {field_name}"
                    )
                refs.append(ref)
            data[field_name] = refs


def _normalize_fk_list_storage_values(model_class, data):
    """Convert list[T] runtime values to ordered local id lists for storage."""
    # 0. Resolve only local relationship IDs; remote pointers are not children.
    for field_name, target_cls in get_fk_list_fields(model_class):
        if field_name not in data or data[field_name] is None:
            continue
        value = data[field_name]
        if not isinstance(value, list):
            data[field_name] = []
            continue

        ids = []
        for item in value:
            local_id = local_ref_id(item, target_cls=target_cls)
            if local_id is not None:
                ids.append(local_id)
                continue
            if isinstance(item, dict):
                ref_value = item.get('$id') or item.get('id')
            else:
                ref_value = item
            if isinstance(ref_value, str) and (
                '://' in ref_value
                or ref_value.startswith('/')
            ):
                raise ValueError(
                    f"Invalid non-local relationship value for {field_name}: "
                    f"{ref_value}"
                )
        data[field_name] = ids


def _local_ref_href(value, target_cls):
    """Return the canonical flat class-name URL for a local ref."""
    return f"{config.API_URL}/{target_cls.__name__}/{value}"


def _public_storage_ref(value, target_cls):
    """Return a public URL, including support for legacy local IDs."""
    if value is None:
        return None
    if is_ref_url(value):
        return Ref.url(value)
    return public_id_url(value, target_cls=target_cls)


def _public_ref_list(value, target_cls):
    """Return API-facing refs for a JSON-backed list[Ref[T]] field."""
    # 0. Preserve non-lists and convert stored references in list order.
    if not isinstance(value, list):
        return value
    refs = []
    for item in value:
        if is_ref_url(item):
            refs.append(Ref.url(item))
            continue
        local_id = local_ref_id(item, target_cls=target_cls)
        refs.append(
            _local_ref_href(local_id, target_cls)
            if local_id is not None else item
        )
    return refs


class SQLiteStorage(AbstractStorage):
    """SQLite storage backend implementing AbstractStorage.
    Delegates schema management to SQLiteMigration.

    Uses a connection pool to avoid opening/closing a connection per operation,
    and enables WAL mode so concurrent readers don't block on a writer. """

    def __init__(
        self, database: str = 'database.db', pool_size: int = 4,
        reference_resolver=None,
    ):
        """Initialize the database adapter and reusable connection pool."""
        # 0. Retain schema and optional reference-resolution dependencies.
        self.database = database
        self.reference_resolver = reference_resolver
        self._migration = SQLiteMigration(database=database)
        # 1. Enable persistent WAL and set each connection's busy timeout.
        # check_same_thread=False is required because FastAPI/Starlette may
        # dispatch requests across threads; our pool handles thread safety.
        self._pool = queue.Queue(maxsize=pool_size)
        init_conn = sqlite3.connect(database, check_same_thread=False)
        init_conn.execute("PRAGMA journal_mode=WAL")
        init_conn.execute("PRAGMA busy_timeout=5000")
        self._pool.put(init_conn)

    def set_reference_resolver(self, reference_resolver):
        """Set the optional resolver used for non-local Ref populate.

        The default ``None`` preserves local-only Ref behavior. A resolver may
        expose ``resolve(ref, target_cls=None, user=None, context=None)`` or
        be a callable with the same signature. Storage stays independent from
        actors while actor-mode bootstrap injects a Matrix-backed resolver. """
        self.reference_resolver = reference_resolver

    def _resolve_reference(self, ref, *, target_cls=None, context=None):
        """Best-effort optional reference resolution for non-local refs."""
        # 0. Reject absent resolvers without attempting remote I/O.
        if self.reference_resolver is None:
            return None, {
                'ref': ref,
                'message': 'No reference resolver configured',
            }
        # 1. Resolve synchronously, refusing nested event-loop execution.
        resolver = self.reference_resolver
        resolve = getattr(resolver, 'resolve', resolver)
        try:
            result = resolve(ref, target_cls=target_cls, context=context)
            if inspect.isawaitable(result):
                try:
                    asyncio.get_running_loop()
                except RuntimeError:
                    result = asyncio.run(result)
                else:
                    return None, {
                        'ref': ref,
                        'message': (
                            'Async reference resolver cannot run from '
                            'synchronous storage context'
                        ),
                    }
            return result, None
        except Exception as exc:
            return None, {'ref': ref, 'message': str(exc)}

    def _populate_ref_list_field(self, field_name, target_cls, instances, conn):
        """Populate a JSON-backed list[Ref[T]] field best-effort."""
        # 0. Collect local IDs for a single batched lookup.
        refs_by_instance = []
        local_ids = set()

        for inst in instances:
            refs = getattr(inst, field_name, None) or []
            if not isinstance(refs, list):
                refs = []
            refs_by_instance.append((inst, refs))
            for ref in refs:
                local_id = local_ref_id(ref, target_cls=target_cls)
                if local_id is not None:
                    local_ids.add(local_id)
        # 1. Hydrate local rows through native JSON and response conversion.
        local_lookup = {}
        if local_ids:
            target_table = _validate_identifier(getattr(
                target_cls, '__tablename__', target_cls.__name__.lower(),
            ))
            placeholders = ','.join(['?'] * len(local_ids))
            cursor = conn.cursor()
            try:
                cursor.execute(
                    f"SELECT * FROM {target_table} "
                    f"WHERE id IN ({placeholders})",
                    list(local_ids),
                )
                rows = cursor.fetchall()
                columns = [col[0] for col in cursor.description]
                for row in rows:
                    record = dict(zip(columns, row))
                    _deserialize_json_fields(target_cls, record)
                    try:
                        ref_inst = target_cls(**record)
                        local_lookup[record['id']] = ref_inst.model_response()
                    except Exception:
                        pass
            except sqlite3.OperationalError:
                pass
        # 2. Resolve remaining pointers and attach per-reference errors.
        for inst, refs in refs_by_instance:
            data = []
            errors = []
            for ref in refs:
                local_id = local_ref_id(ref, target_cls=target_cls)
                if local_id is not None:
                    local_data = local_lookup.get(local_id)
                    if local_data is not None:
                        data.append(local_data)
                    else:
                        errors.append({
                            'ref': ref, 'message': 'Local reference not found',
                        })
                    continue

                resolved, error = self._resolve_reference(
                    ref,
                    target_cls=target_cls,
                    context={
                        'field': field_name, 'model': inst.__class__.__name__,
                    },
                )
                if error:
                    errors.append(error)
                elif resolved is not None:
                    if hasattr(resolved, 'model_response'):
                        resolved = resolved.model_response()
                    data.append(resolved)

            if not hasattr(inst, '_populated') or inst._populated is None:
                inst.__dict__['_populated'] = {}
            inst.__dict__['_populated'][field_name] = {
                'data': data,
                'refs': refs,
                'errors': errors,
            }

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
        """Borrow and return a pooled connection without transaction cleanup."""
        # 0. Acquire an exclusive pool lease for this operation.
        conn = self._get_conn()
        try:
            yield conn
        finally:
            self._put_conn(conn)

    # ----------------------------------------------
    # SCHEMA (delegated to SQLiteMigration)
    # ----------------------------------------------

    def create_table(self, model_class: Type[Any]):
        """Create a native model table through the migration backend."""
        _validate_identifier(model_class.__tablename__)
        self._migration.create_table(model_class)

    def migrate_table(self, model_class: Type[Any]):
        """Delegate explicit model schema reconciliation to migrations."""
        _validate_identifier(model_class.__tablename__)
        self._migration.migrate_table(model_class)

    # ----------------------------------------------
    # CREATE
    # ----------------------------------------------

    def create(self, model_class: Type[Any], data: Dict[str, Any]) -> Any:
        """Normalize and commit one native row, then construct its model."""
        # 0. Normalize references and select the native stored field set.
        logger.info("Creating new %s record", model_class.__name__)
        table_name = _validate_identifier(model_class.__tablename__)
        _normalize_ref_storage_values(model_class, data)
        _normalize_fk_list_storage_values(model_class, data)

        # list[T] fields are JSON-backed columns and remain in the field set.
        json_field_names = set(get_json_fields(model_class))
        collection_field_names = {
            name for name, _cls in get_fk_list_fields(model_class)
            if name not in json_field_names
        }

        fields = [f for f in model_class.model_fields.keys()
                  if f != 'id' and f not in collection_field_names]
        logger.debug("Fields: %s", fields)
        placeholders = ", ".join(['?'] * len(fields))
        columns = ", ".join(fields)
        # 1. Apply the same scalar/JSON conversion as ordinary native creation.
        values = [data.get(field) for field in fields]
        # De-reference model instances carrying local IDs.
        values = [
            value.id
            if isinstance(value, BaseModel) and hasattr(value, 'id') else value
            for value in values
        ]
        values = [
            _normalize_storage_value(model_class.model_fields[field], value)
            for field, value in zip(fields, values)
        ]
        # Coerce non-native types (e.g. AnyHttpUrl) to SQLite-compatible values
        values = [_coerce_value(v) for v in values]
        insert_sql = (
            f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
        )
        # 2. Commit before assigning the generated ID and constructing a model.
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(insert_sql, values)
            conn.commit()
            data['id'] = cursor.lastrowid
        logger.info("Record created with ID: %s", data['id'])
        return model_class(**data)

    # ----------------------------------------------
    # LIST
    # ----------------------------------------------

    def list(
        self, model_class: Type[Any], sql_filter: tuple = None,
        limit: int = None, offset: int = None, populate: PopulateSpec = None,
        ids: list = None, *, order_asc: str | None = None,
        order_desc: str | None = None,
    ) -> List[Any]:
        """Select rows with filtering, single-column ordering and pagination.

        Ordering accepts one declared, physically stored field. Invalid names
        or simultaneous directions raise ValueError. SQLite owns NULL and tie
        ordering; counts and hydration are independent of ordering. Pagination
        requires nonnegative signed-64-bit integers (or None); zero limits
        remain valid for trusted count-only probes."""
        # 0. Compose the trusted filter and optional selected-ID constraint.
        for name, value in (('limit', limit), ('offset', offset)):
            if value is not None and (
                type(value) is not int or not 0 <= value < 2**63
            ):
                raise ValueError(
                    f'{name} must be a nonnegative signed-64-bit integer',
                )
        if order_asc is not None and order_desc is not None:
            raise ValueError("order_asc and order_desc are mutually exclusive")
        order_field = order_asc if order_asc is not None else order_desc
        if order_field is not None:
            query_field(model_class, order_field)
        table_name = _validate_identifier(model_class.__tablename__)
        ref_fields = get_ref_fields(model_class)

        select_sql = f"SELECT * FROM {table_name}"
        filter_params = []

        # Optional ids filter: WHERE id IN (?, ?, ...)
        if ids is not None and ids:
            placeholders = ','.join('?' * len(ids))
            id_clause = f"id IN ({placeholders})"
            if sql_filter and sql_filter[0]:
                clause = f"({sql_filter[0]}) AND {id_clause}"
                filter_params = list(sql_filter[1] or []) + list(ids)
                sql_filter = (clause, filter_params)
            else:
                sql_filter = (id_clause, list(ids))

        if sql_filter is not None:
            clause, params = sql_filter
            if clause:
                select_sql += f" WHERE {clause}"
                filter_params = list(params) if params else []
        # 1. Count and select using one leased connection.
        with self._connection() as conn:
            cursor = conn.cursor()
            if order_field is not None:
                cursor.execute(f'PRAGMA table_info("{table_name}")')
                stored_columns = {column[1] for column in cursor.fetchall()}
                if order_field not in stored_columns:
                    raise ValueError("Ordering requires a stored model field")

            # Count total matching rows (before pagination)
            total = None
            if limit is not None:
                count_sql = select_sql.replace("SELECT *", "SELECT COUNT(*)", 1)
                cursor.execute(count_sql, filter_params[:])
                total = cursor.fetchone()[0]

            # Apply native ordering only to rows, before pagination.
            if order_field is not None:
                direction = 'ASC' if order_asc is not None else 'DESC'
                select_sql += f' ORDER BY "{order_field}" {direction}'

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
            # 2. Decode defaults, JSON and references before construction.
            records = []
            for row in rows:
                record = dict(zip(columns, row))

                # Coerce NULL values to field defaults
                for key, val in record.items():
                    if val is None and key in model_class.model_fields:
                        field = model_class.model_fields[key]
                        if field.default is not None:
                            record[key] = field.default

                # Deserialize JSON TEXT before model instantiation.
                _deserialize_json_fields(model_class, record)

                # Hydrate Ref[T] fields as href URLs
                for field_name, target_cls in ref_fields:
                    val = record.get(field_name)
                    if val is not None:
                        record[field_name] = _public_storage_ref(
                            val, target_cls,
                        )

                for field_name, target_cls in get_ref_list_fields(model_class):
                    if field_name in record:
                        record[field_name] = _public_ref_list(
                            record.get(field_name), target_cls,
                        )

                records.append(record)

            results = [model_class(**record) for record in records]

            if populate and not populate.is_empty:
                self._populate_fields(model_class, results, populate, conn)
        # 3. Preserve the native paginated or unpaginated response shape.
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

    # ----------------------------------------------
    # GET
    # ----------------------------------------------

    def get(
        self, model_class: Type[Any], id: int, as_dict: bool = False,
        populate: PopulateSpec = None,
    ) -> Any:
        """Read one row with optional dictionary output and population."""
        # 0. Select the exact local record through a leased connection.
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
            # 1. Restore scalar and local model fields, omitting SQL NULLs.
            data = {}
            for field_name, field_info in model_class.model_fields.items():
                value = record.get(field_name)
                if value is not None:
                    data[field_name] = value
                    continue

                field_type = field_info.annotation
                if (
                    isinstance(field_type, type)
                    and issubclass(field_type, BaseModel)
                ):
                    fk_field = f"{field_name}_id"
                    fk_value = record.get(fk_field)
                    if fk_value is not None:
                        try:
                            data[field_name] = field_type(id=fk_value)
                        except Exception:
                            pass
            # 2. Normalize URL references and JSON before native construction.
            for field_name, target_cls in get_ref_fields(model_class):
                val = data.get(field_name)
                if val is not None:
                    data[field_name] = _public_storage_ref(val, target_cls)

            _deserialize_json_fields(model_class, data)
            for field_name, target_cls in get_ref_list_fields(model_class):
                if field_name in data:
                    data[field_name] = _public_ref_list(
                        data.get(field_name), target_cls,
                    )

            instance = model_class(**data) if not as_dict else None

            if populate and not populate.is_empty and instance:
                self._populate_fields(model_class, [instance], populate, conn)

        if as_dict:
            return data
        return instance

    # ----------------------------------------------
    # POPULATE (eager loading)
    # ----------------------------------------------

    def _populate_fields(
        self, model_class, instances, populate, conn, _visited=None,
    ):
        """Batch-load related entities for a list of parent instances.

        Args:
            model_class: The parent model class
            instances: List of parent model instances
            populate: PopulateSpec controlling which fields to load
            conn: Open sqlite3 connection to reuse
            _visited: Model names already visited, preventing cycles. """
        # 0. Track each branch without sharing mutable visited state.
        if not instances:
            return

        if _visited is None:
            _visited = set()
        _visited = _visited | {model_class.__name__}

        ref_fields = get_ref_fields(model_class)
        ref_list_fields = get_ref_list_fields(model_class)
        cursor = conn.cursor()
        # 1. Populate requested pointer lists using their batched resolver.
        for field_name, target_cls in ref_list_fields:
            if not populate.should_populate(field_name):
                continue
            if target_cls.__name__ in _visited:
                continue
            self._populate_ref_list_field(
                field_name, target_cls, instances, conn,
            )
        # 2. Resolve scalar references locally or through the optional resolver.
        for field_name, target_cls in ref_fields:
            if not populate.should_populate(field_name):
                continue
            if target_cls.__name__ in _visited:
                continue

            target_table = _validate_identifier(getattr(
                target_cls, '__tablename__', target_cls.__name__.lower(),
            ))

            # Extract local IDs from stored href values.
            fk_ids = []
            for inst in instances:
                val = getattr(inst, field_name, None)
                fk_id = local_ref_id(val, target_cls=target_cls)
                if fk_id is not None:
                    fk_ids.append(fk_id)

            if not fk_ids:
                for inst in instances:
                    val = getattr(inst, field_name, None)
                    if val is None or self.reference_resolver is None:
                        continue
                    resolved, _error = self._resolve_reference(
                        val,
                        target_cls=target_cls,
                        context={
                            'field': field_name,
                            'model': inst.__class__.__name__,
                        },
                    )
                    if resolved is not None:
                        if hasattr(resolved, 'model_response'):
                            resolved = resolved.model_response()
                        if (
                            not hasattr(inst, '_populated')
                            or inst._populated is None
                        ):
                            inst.__dict__['_populated'] = {}
                        inst.__dict__['_populated'][field_name] = resolved
                continue

            unique_ids = list(set(fk_ids))
            placeholders = ",".join(["?"] * len(unique_ids))
            try:
                cursor.execute(
                    f"SELECT * FROM {target_table} "
                    f"WHERE id IN ({placeholders})",
                    unique_ids
                )
                rows = cursor.fetchall()
                columns = [col[0] for col in cursor.description]
            except sqlite3.OperationalError:
                continue

            lookup = {}
            for row in rows:
                record = dict(zip(columns, row))
                _deserialize_json_fields(target_cls, record)
                try:
                    ref_inst = target_cls(**record)
                    dumped = ref_inst.model_response()
                    lookup[record['id']] = dumped
                except Exception:
                    pass

            for inst in instances:
                val = getattr(inst, field_name, None)
                fk_id = local_ref_id(val, target_cls=target_cls)
                if fk_id is None:
                    if val is not None and self.reference_resolver is not None:
                        resolved, _error = self._resolve_reference(
                            val,
                            target_cls=target_cls,
                            context={
                                'field': field_name,
                                'model': inst.__class__.__name__,
                            },
                        )
                        if resolved is not None:
                            if hasattr(resolved, 'model_response'):
                                resolved = resolved.model_response()
                            if (
                                not hasattr(inst, '_populated')
                                or inst._populated is None
                            ):
                                inst.__dict__['_populated'] = {}
                            inst.__dict__['_populated'][field_name] = resolved
                    continue
                ref_data = lookup.get(fk_id)
                if ref_data:
                    if (
                        not hasattr(inst, '_populated')
                        or inst._populated is None
                    ):
                        inst.__dict__['_populated'] = {}
                    inst.__dict__['_populated'][field_name] = ref_data

    # ----------------------------------------------
    # UPDATE
    # ----------------------------------------------

    def update(self, model_class: Type[Any], id: int, data: Dict[str, Any]):
        """Update a record in the database for the given model class,
        using only the fields provided in the `data` dictionary.
        Prevents SQL injection by using parameterized queries. """
        # 0. Normalize the model's supplied storage values.
        table_name = _validate_identifier(model_class.__tablename__)
        _normalize_ref_storage_values(model_class, data)
        _normalize_fk_list_storage_values(model_class, data)
        # 1. Select supplied stored fields, preserving JSON-backed collections.
        json_field_names = set(get_json_fields(model_class))
        collection_field_names = {
            name for name, _cls in get_fk_list_fields(model_class)
            if name not in json_field_names
        }

        # Validate and filter the fields based on model annotations
        valid_fields = [f for f in model_class.model_fields.keys()
                        if f != 'id' and f not in collection_field_names]
        fields_to_update = [
            field for field in data.keys() if field in valid_fields
        ]

        if not fields_to_update:
            raise ValueError("No valid fields provided to update.")
        # 2. Convert patch values and bind the exact row ID.
        set_clause = ", ".join([f"{field} = ?" for field in fields_to_update])
        values = [
            _coerce_value(_normalize_storage_value(
                model_class.model_fields[field], data[field],
            ))
            for field in fields_to_update
        ]

        # Add the id to the values for the WHERE clause
        update_sql = f"UPDATE {table_name} SET {set_clause} WHERE id = ?"
        values.append(id)
        # 3. Commit the patch and report SQLite update failures.
        with self._connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(update_sql, values)
                conn.commit()
            except sqlite3.Error as e:
                raise RuntimeError(f"Database update failed: {e}")

    # ----------------------------------------------
    # DELETE
    # ----------------------------------------------

    def delete(self, model_class: Type[Any], id: int):
        """Delete one native row by its local ID."""
        # 0. Bind the requested ID and commit the deletion.
        table_name = _validate_identifier(model_class.__tablename__)
        delete_sql = f"DELETE FROM {table_name} WHERE id = ?"
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(delete_sql, (id,))
            conn.commit()


# Changelog
# - 2026-11-02: Reject invalid pagination values before leasing a connection.
# - 2026-10-31: Factor transaction-owned insertion and roll back failed leases;
#   reject generic TXRecord writes and document native storage operations.
#   Share native get row decoding with transaction-owned record readers.
# - 2026-10-31: Restore ordinary inline persistence and pool return behavior;
#   remove task-specific insertion/decoding helpers and table-name guards.
# - 2026-11-02: Validate single-field list ordering against declared and stored
#   columns; apply native ORDER BY before paging without changing counts.
# - 2026-11-02: Reject private, hidden and excluded ordering-field probes.
# - 2026-11-10: Restore native ordering and pagination guards from 123d825.
