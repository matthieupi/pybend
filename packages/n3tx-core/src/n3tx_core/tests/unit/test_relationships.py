"""Tests for model relationship primitives and generated relationship models."""

import sqlite3

from pydantic import Field

from n3tx_core.app import create_app
from n3tx_core.models.proto_model import ProtoModel
from n3tx_core.models.relationships import ManyToMany, generate_relationship_model
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_core.utils.registrar import registered_models, join_models


class TestGenerateRelationshipModel:

    def test_generates_many_to_many_link_model_and_metadata(self):
        class Tag(ProtoModel):
            __tablename__ = 'tags'

        class Product(ProtoModel):
            __tablename__ = 'products'
            tags: ManyToMany[Tag] = Field(default=[])

        link_model = generate_relationship_model(Product, 'tags', Tag)
        relationship = link_model.__relationship__

        assert link_model.__name__ == 'ProductTagsLink'
        assert link_model.__tablename__ == 'products_tags'
        assert relationship.kind == 'many_to_many'
        assert relationship.owner is Product
        assert relationship.field_name == 'tags'
        assert relationship.target is Tag
        assert relationship.through is link_model
        assert relationship.owner_fk == 'product_id'
        assert relationship.target_fk == 'tag_id'
        assert relationship.table_name == 'products_tags'
        assert Product.__relationships__['tags'] is relationship
        assert 'product_id' in link_model.model_fields
        assert 'tag_id' in link_model.model_fields

    def test_uses_explicit_through_model(self):
        class Tag(ProtoModel):
            __tablename__ = 'tags'

        class ProductTag(ProtoModel):
            __tablename__ = 'product_tags'
            product_id: int
            tag_id: int
            relevance: float = 1.0

        class Product(ProtoModel):
            __tablename__ = 'products'
            tags: ManyToMany[Tag, ProductTag] = Field(default=[])

        link_model = generate_relationship_model(Product, 'tags', Tag, ProductTag)
        relationship = link_model.__relationship__

        assert link_model is ProductTag
        assert relationship.through is ProductTag
        assert relationship.table_name == 'product_tags'
        assert Product.__relationships__['tags'] is relationship


class TestRelationshipAppBootstrap:

    def test_create_app_registers_many_to_many_link_model(self, tmp_path):
        saved_registered = dict(registered_models)
        saved_join_models = dict(join_models)
        registered_models.clear()
        join_models.clear()
        try:
            class Tag(ProtoModel):
                __tablename__ = 'tags'
                __storable__ = True
                name: str = ''

            class Product(ProtoModel):
                __tablename__ = 'products'
                __storable__ = True
                name: str = ''
                tags: ManyToMany[Tag] = Field(default=[])

            create_app(
                models=[Product, Tag],
                storage=SQLiteStorage(str(tmp_path / 'relationships.db')),
                static_dir=None,
            )

            assert 'products' in registered_models
            assert 'tags' in registered_models
            assert 'products_tags' in registered_models

            link_model = registered_models['products_tags']
            relationship = link_model.__relationship__
            assert relationship.owner is Product
            assert relationship.field_name == 'tags'
            assert relationship.target is Tag
            assert Product.__relationships__['tags'] is relationship
        finally:
            registered_models.clear()
            registered_models.update(saved_registered)
            join_models.clear()
            join_models.update(saved_join_models)

    def test_create_app_creates_many_to_many_link_table_indexes(self, tmp_path):
        saved_registered = dict(registered_models)
        saved_join_models = dict(join_models)
        registered_models.clear()
        join_models.clear()
        db_path = tmp_path / 'relationships_indexes.db'
        try:
            class Tag(ProtoModel):
                __tablename__ = 'tags'
                __storable__ = True
                name: str = ''

            class Product(ProtoModel):
                __tablename__ = 'products'
                __storable__ = True
                name: str = ''
                tags: ManyToMany[Tag] = Field(default=[])

            create_app(
                models=[Product, Tag],
                storage=SQLiteStorage(str(db_path)),
                static_dir=None,
            )

            with sqlite3.connect(db_path) as conn:
                table_columns = {
                    row[1]
                    for row in conn.execute('PRAGMA table_info(products_tags)').fetchall()
                }
                indexes = conn.execute('PRAGMA index_list(products_tags)').fetchall()
                index_names = {row[1] for row in indexes}
                unique_indexes = {row[1] for row in indexes if row[2]}

            assert {'id', 'product_id', 'tag_id'} <= table_columns
            assert 'idx_products_tags_product_id' in index_names
            assert 'idx_products_tags_tag_id' in index_names
            assert 'idx_products_tags_product_id_tag_id_unique' in unique_indexes
        finally:
            registered_models.clear()
            registered_models.update(saved_registered)
            join_models.clear()
            join_models.update(saved_join_models)
