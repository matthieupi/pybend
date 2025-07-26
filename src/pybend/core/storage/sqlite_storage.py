# app/storage/sqlite_storage.py

import sqlite3
from typing import Any, Dict, List, Type
from .abstract_storage import AbstractStorage

class SQLiteStorage(AbstractStorage):
    """
    SQLite storage backend implementing the AbstractStorage.
    """

    def __init__(self, database: str = 'database.db'):
        self.database = database

    def create_table(self, model_class: Type[Any]):
        # Implementation similar to previous create_table method
        # Use model_class.__annotations__ to get fields
        # ...

        # (Include the same create_table logic as before, adjusted to fit this method)

        # Example:
        table_name = model_class.__tablename__
        columns = []
        for field_name, field_info in model_class.model_fields.items():
            field_type = field_info.annotation
            if field_name == 'id' or field_name.startswith('_') or field_name.startswith('__'):
                continue  # 'id' is added separately

            # Handle typing annotations like Optional[int]
            origin_type = getattr(field_type, '__origin__', None)
            if origin_type is not None:
                field_type = field_type.__args__[0]

            if field_type == int:
                sql_type = 'INTEGER'
            elif field_type == float:
                sql_type = 'REAL'
            elif field_type == str:
                sql_type = 'TEXT'
            else:
                sql_type = 'TEXT'  # Default to TEXT
            columns.append(f"{field_name} {sql_type}")

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
        conn.commit()
        conn.close()

    def migrate_table(self, model_class: Type[Any]):
        """
        Adds missing columns to existing tables based on the model definition.
        Automatically handles List[...] fields by storing them as TEXT and initializing to '[]'.
        """
        import json
        import sqlite3
        from typing import get_origin, get_args

        table_name = model_class.__tablename__
        existing_columns = set()

        conn = sqlite3.connect(self.database)
        cursor = conn.cursor()
        try:
            cursor.execute(f"PRAGMA table_info({table_name})")
            existing_columns = {row[1] for row in cursor.fetchall()}
        except sqlite3.OperationalError:
            existing_columns = set()

        for field_name, field_info in model_class.model_fields.items():
            field_type = field_info.annotation
            if field_name == 'id' or field_name in existing_columns:
                continue

            origin_type = getattr(field_type, '__origin__', None)
            base_type = field_type
            if origin_type is not None:
                base_type = field_type.__args__[0]

            if origin_type is list or origin_type is List:
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
                print(f"[MIGRATE] Added column '{field_name}' to '{table_name}' as {sql_type}")

            except sqlite3.OperationalError as e:
                print(f"[MIGRATE] Failed to add column {field_name} to {table_name}: {e}")

        # Remove the column from the table that are in existing_columns and not present anymore
        for col in existing_columns:
            if col not in model_class.model_fields or col.startswith('_') or col.startswith('__'):
                try:
                    cursor.execute(f"ALTER TABLE {table_name} DROP COLUMN {col}")
                    print(f"[MIGRATE] Removed column '{col}' from '{table_name}'")
                except sqlite3.OperationalError as e:
                    print(f"[MIGRATE] Failed to remove column {col} from {table_name}: {e}")

        conn.commit()
        conn.close()

    def create(self, model_class: Type[Any], data: Dict[str, Any]) -> Any:
        # Implementation similar to previous create method
        # ...

        print("Creating a new record in the database for model class:", model_class.__name__, flush=True)
        table_name = model_class.__tablename__
        fields = [f for f in model_class.model_fields.keys() if f != 'id']
        print("Fields: ", fields)
        placeholders = ", ".join(['?'] * len(fields))
        columns = ", ".join(fields)
        values = [data.get(field) for field in fields]
        insert_sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
        conn = sqlite3.connect(self.database)
        cursor = conn.cursor()
        cursor.execute(insert_sql, values)
        conn.commit()
        data['id'] = cursor.lastrowid
        conn.close()
        return model_class(**data)

    def list(self, model_class: Type[Any]) -> List[Any]:
        # Implementation similar to previous get_all method
        # ...

        table_name = model_class.__tablename__
        select_sql = f"SELECT * FROM {table_name}"
        conn = sqlite3.connect(self.database)
        cursor = conn.cursor()
        cursor.execute(select_sql)
        rows = cursor.fetchall()
        columns = [column[0] for column in cursor.description]
        conn.close()
        return [model_class(**dict(zip(columns, row))) for row in rows]

    def get(self, model_class: Type[Any], id: int, as_dict: bool = False) -> Any:
        # Implementation similar to previous get_by_id method
        # ...

        table_name = model_class.__tablename__
        select_sql = f"SELECT * FROM {table_name} WHERE id = ?"
        conn = sqlite3.connect(self.database)
        cursor = conn.cursor()
        cursor.execute(select_sql, (id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            columns = [column[0] for column in cursor.description]
            record = dict(zip(columns, row))
            object = {key: value for key, value in record.items() if key in model_class.model_fields}
            print(object)
            if as_dict:
                return object
            return model_class(**object)
        else:
            return None

    def update(self, model_class: Type[Any], id: int, data: Dict[str, Any]):
        """
        Updates a record in the database for the given model class, using only the fields provided in the `data` dictionary.
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
    """
        def update(self, model_class: Type[Any], id: int, data: Dict[str, Any]):
            # Implementation similar to previous update method
            # ...

            table_name = model_class.__tablename__
            fields = [f for f in model_class.__annotations__.keys() if f != 'id']
            set_clause = ", ".join([f"{field} = ?" for field in fields])
            values = [data.get(field) for field in data.keys() if field in fields]
            update_sql = f"UPDATE {table_name} SET {set_clause} WHERE id = ?"
            conn = sqlite3.connect(self.database)
            cursor = conn.cursor()
            cursor.execute(update_sql, values + [id])
            conn.commit()
            conn.close()
    """

    def delete(self, model_class: Type[Any], id: int):
        # Implementation similar to previous delete method
        # ...

        table_name = model_class.__tablename__
        delete_sql = f"DELETE FROM {table_name} WHERE id = ?"
        conn = sqlite3.connect(self.database)
        cursor = conn.cursor()
        cursor.execute(delete_sql, (id,))
        conn.commit()
        conn.close()
