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
        for field_name, field_type in model_class.__annotations__.items():
            if field_name == 'id':
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

    def get(self, model_class: Type[Any], id: int) -> Any:
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
