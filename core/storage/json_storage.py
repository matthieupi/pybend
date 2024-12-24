# app/storage/json_storage.py

import json
import os
from typing import Any, Dict, List, Type
from .abstract_storage import AbstractStorage


class JSONStorage(AbstractStorage):
    """
    JSON file storage backend implementing the StorageInterface.
    """

    def __init__(self, directory: str = 'data'):
        self.directory = directory
        if not os.path.exists(directory):
            os.makedirs(directory)

    def _get_file_path(self, model_class: Type[Any]) -> str:
        return os.path.join(self.directory, f"{model_class.__tablename__}.json")

    def create_table(self, model_class: Type[Any]):
        # Ensure the data file exists
        file_path = self._get_file_path(model_class)
        if not os.path.exists(file_path):
            with open(file_path, 'w') as f:
                json.dump([], f)

    def create(self, model_class: Type[Any], data: Dict[str, Any]) -> Any:
        file_path = self._get_file_path(model_class)
        with open(file_path, 'r+') as f:
            records = json.load(f)
            data['id'] = max((record['id'] for record in records), default=0) + 1
            records.append(data)
            f.seek(0)
            json.dump(records, f, indent=4)
        return model_class(**data)

    def get_all(self, model_class: Type[Any]) -> List[Any]:
        file_path = self._get_file_path(model_class)
        with open(file_path, 'r') as f:
            records = json.load(f)
        return [model_class(**record) for record in records]

    def get_by_id(self, model_class: Type[Any], id: int) -> Any:
        file_path = self._get_file_path(model_class)
        with open(file_path, 'r') as f:
            records = json.load(f)
        for record in records:
            if record['id'] == id:
                return model_class(**record)
        return None

    def update(self, model_class: Type[Any], id: int, data: Dict[str, Any]):
        file_path = self._get_file_path(model_class)
        updated = False
        with open(file_path, 'r+') as f:
            records = json.load(f)
            for index, record in enumerate(records):
                if record['id'] == id:
                    records[index].update(data)
                    updated = True
                    break
            if updated:
                f.seek(0)
                f.truncate()
                json.dump(records, f, indent=4)

    def delete(self, model_class: Type[Any], id: int):
        file_path = self._get_file_path(model_class)
        with open(file_path, 'r+') as f:
            records = json.load(f)
            records = [record for record in records if record['id'] != id]
            f.seek(0)
            f.truncate()
            json.dump(records, f, indent=4)
