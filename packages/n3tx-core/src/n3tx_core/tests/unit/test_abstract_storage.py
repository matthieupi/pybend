"""Tests for storage/abstract_storage.py — AbstractStorage interface."""

import pytest
from n3tx_core.storage.abstract_storage import AbstractStorage

pytestmark = pytest.mark.unit



class TestAbstractStorage:

    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            AbstractStorage()

    def test_abstract_methods(self):
        # Verify all abstract methods exist
        assert hasattr(AbstractStorage, 'create_table')
        assert hasattr(AbstractStorage, 'create')
        assert hasattr(AbstractStorage, 'list')
        assert hasattr(AbstractStorage, 'get')
        assert hasattr(AbstractStorage, 'update')
        assert hasattr(AbstractStorage, 'delete')

    def test_concrete_implementation(self):
        class ConcreteStorage(AbstractStorage):
            def create_table(self, model_class):
                pass
            def create(self, model_class, data):
                return None
            def list(self, model_class, sql_filter=None, limit=None, offset=None, populate=None, ids=None):
                return []
            def get(self, model_class, id_=None, as_dict=False, populate=None, **kwargs):
                return None
            def update(self, model_class, id_, data):
                pass
            def delete(self, model_class, id_):
                pass

        s = ConcreteStorage()
        assert isinstance(s, AbstractStorage)
