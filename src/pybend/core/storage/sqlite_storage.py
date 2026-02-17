# app/storage/sqlite_storage.py

import sqlite3
from typing import Any, Dict, List, Type

from pydantic import BaseModel

from utils.registrar import registered_models
from .abstract_storage import AbstractStorage
from .sqlite_helpers import get_list_fields
from .sqlite_migration import SQLiteMigration


class SQLiteStorage(AbstractStorage):
    """
    SQLite storage backend implementing the AbstractStorage.
    Delegates schema management to SQLiteMigration.
    """

    def __init__(self, database: str = 'database.db'):
        self.database = database
        self._migration = SQLiteMigration(database=database)

    # ──────────────────────────────────────────────
    # SCHEMA (delegated to SQLiteMigration)
    # ──────────────────────────────────────────────

    def create_table(self, model_class: Type[Any]):
        self._migration.create_table(model_class)

    def migrate_table(self, model_class: Type[Any]):
        self._migration.migrate_table(model_class)

    # ──────────────────────────────────────────────
    # CREATE
    # ──────────────────────────────────────────────

    def create(self, model_class: Type[Any], data: Dict[str, Any]) -> Any:
        print("Creating a new record in the database for model class:", model_class.__name__, flush=True)
        table_name = model_class.__tablename__

        # Identify List[BaseModel] fields — these are NOT columns on this table
        list_field_names = {name for name, _cls in get_list_fields(model_class)}

        fields = [f for f in model_class.model_fields.keys()
                  if f != 'id' and f not in list_field_names]
        print("Fields: ", fields)
        placeholders = ", ".join(['?'] * len(fields))
        columns = ", ".join(fields)
        # Extract values
        values = [data.get(field) for field in fields]
        # De-reference BaseModel instances to their IDs if they have an 'id' attribute
        values = [value.id
                  if isinstance(value, BaseModel) and hasattr(value, 'id') else value
                  for value in values]
        insert_sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
        conn = sqlite3.connect(self.database)
        cursor = conn.cursor()
        cursor.execute(insert_sql, values)
        conn.commit()
        data['id'] = cursor.lastrowid
        conn.close()
        print("Record created with ID:", data['id'], flush=True)
        return model_class(**data)

    # ──────────────────────────────────────────────
    # LIST
    # ──────────────────────────────────────────────

    def list(self, model_class: Type[Any]) -> List[Any]:
        table_name = model_class.__tablename__
        list_fields = get_list_fields(model_class)

        select_sql = f"SELECT * FROM {table_name}"
        conn = sqlite3.connect(self.database)
        cursor = conn.cursor()
        cursor.execute(select_sql)
        rows = cursor.fetchall()
        columns = [column[0] for column in cursor.description]

        results = []
        for row in rows:
            record = dict(zip(columns, row))

            # If no List[BaseModel] fields, fast path
            if not list_fields:
                results.append(model_class(**record))
                continue

            # Hydrate List[BaseModel] fields
            parent_id = record.get('id')
            for field_name, child_class in list_fields:
                fk_col = f"{model_class.__name__.lower()}_id"
                child_table = child_class.__tablename__
                try:
                    cursor.execute(
                        f"SELECT * FROM {child_table} WHERE {fk_col} = ?",
                        (parent_id,)
                    )
                    child_rows = cursor.fetchall()
                    if child_rows:
                        child_cols = [c[0] for c in cursor.description]
                        record[field_name] = [
                            child_class(**dict(zip(child_cols, r)))
                            for r in child_rows
                        ]
                    else:
                        record[field_name] = []
                except sqlite3.OperationalError:
                    record[field_name] = []

            results.append(model_class(**record))

        conn.close()
        return results

    # ──────────────────────────────────────────────
    # GET
    # ──────────────────────────────────────────────

    def get(self, model_class: Type[Any], id: int, as_dict: bool = False) -> Any:
        table_name = model_class.__tablename__
        select_sql = f"SELECT * FROM {table_name} WHERE id = ?"
        conn = sqlite3.connect(self.database)
        cursor = conn.cursor()
        cursor.execute(select_sql, (id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
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

        # ── Hydrate List[BaseModel] fields from child tables ──
        for field_name, child_class in get_list_fields(model_class):
            fk_col = f"{model_class.__name__.lower()}_id"
            child_table = child_class.__tablename__
            try:
                cursor.execute(
                    f"SELECT * FROM {child_table} WHERE {fk_col} = ?", (id,)
                )
                child_rows = cursor.fetchall()
                if child_rows:
                    child_cols = [c[0] for c in cursor.description]
                    data[field_name] = [
                        child_class(**dict(zip(child_cols, r)))
                        for r in child_rows
                    ]
                else:
                    data[field_name] = []
            except sqlite3.OperationalError:
                # Child table or FK column may not exist yet
                data[field_name] = []

        conn.close()

        if as_dict:
            return data
        return model_class(**data)

    # ──────────────────────────────────────────────
    # UPDATE
    # ──────────────────────────────────────────────

    def update(self, model_class: Type[Any], id: int, data: Dict[str, Any]):
        """
        Updates a record in the database for the given model class,
        using only the fields provided in the `data` dictionary.
        Prevents SQL injection by using parameterized queries.
        """
        table_name = model_class.__tablename__

        # Validate and filter the fields based on model annotations
        valid_fields = [f for f in model_class.__annotations__.keys() if f != 'id']
        fields_to_update = [field for field in data.keys() if field in valid_fields]

        if not fields_to_update:
            raise ValueError("No valid fields provided to update.")

        # Construct the SET clause dynamically
        set_clause = ", ".join([f"{field} = ?" for field in fields_to_update])
        values = [data[field] for field in fields_to_update]

        # Add the id to the values for the WHERE clause
        update_sql = f"UPDATE {table_name} SET {set_clause} WHERE id = ?"
        values.append(id)

        # Execute the update query
        conn = sqlite3.connect(self.database)
        cursor = conn.cursor()

        try:
            cursor.execute(update_sql, values)
            conn.commit()
        except sqlite3.Error as e:
            raise RuntimeError(f"Database update failed: {e}")
        finally:
            conn.close()

    # ──────────────────────────────────────────────
    # DELETE
    # ──────────────────────────────────────────────

    def delete(self, model_class: Type[Any], id: int):
        table_name = model_class.__tablename__
        delete_sql = f"DELETE FROM {table_name} WHERE id = ?"
        conn = sqlite3.connect(self.database)
        cursor = conn.cursor()
        cursor.execute(delete_sql, (id,))
        conn.commit()
        conn.close()