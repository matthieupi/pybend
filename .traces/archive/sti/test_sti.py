"""Tests for Single Table Inheritance (STI) — DiscriminatorMixin.

Tests cover:
1. __init_subclass__ detection (root, subtype, non-STI)
2. Storage CRUD (create, list, get, update) with real SQLite
3. Migration (discriminator column, orphan protection, index)
4. Edge cases (abstract base, non-STI unaffected, empty subtypes)
"""
import os
import sqlite3
import pytest
from typing import ClassVar
from unittest.mock import MagicMock

from pydantic import Field

from n3tx.core.models.proto_model import ProtoModel
from n3tx.core.models.discriminator_mixin import DiscriminatorMixin
from n3tx.core.storage.sqlite_storage import SQLiteStorage

pytestmark = pytest.mark.unit


# ── Helpers ────────────────────────────────────────────────────────

@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / 'test_sti.db')


@pytest.fixture
def storage(db_path):
    return SQLiteStorage(database=db_path)


def get_columns(db_path, table):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table})")
    cols = {row[1] for row in cursor.fetchall()}
    conn.close()
    return cols


def get_indexes(db_path, table):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA index_list({table})")
    indexes = {row[1] for row in cursor.fetchall()}
    conn.close()
    return indexes


# ══════════════════════════════════════════════════════════════════
# 1. __init_subclass__ Detection
# ══════════════════════════════════════════════════════════════════

class TestSTIDetection:
    """DiscriminatorMixin auto-injection and subtype registration."""

    def test_root_has_subtypes_dict(self):
        class Content(ProtoModel):
            __tablename__: ClassVar[str] = 'det_content'
            __storable__: ClassVar[bool] = True
            __discriminator__: ClassVar[str] = 'content_type'
            title: str = Field(default='')

        assert hasattr(Content, '__subtypes__')
        assert Content.__subtypes__ == {}
        assert Content.__sti_root__ is Content

    def test_root_has_discriminator_field(self):
        class Content(ProtoModel):
            __tablename__: ClassVar[str] = 'det_content2'
            __storable__: ClassVar[bool] = True
            __discriminator__: ClassVar[str] = 'content_type'
            title: str = Field(default='')

        assert 'content_type' in Content.model_fields
        assert Content.model_fields['content_type'].default == 'Content'

    def test_subtype_registered_in_root(self):
        class Content(ProtoModel):
            __tablename__: ClassVar[str] = 'det_content3'
            __storable__: ClassVar[bool] = True
            __discriminator__: ClassVar[str] = 'content_type'
            title: str = Field(default='')

        class Article(Content):
            body: str = Field(default='')

        assert 'Article' in Content.__subtypes__
        assert Content.__subtypes__['Article'] is Article

    def test_subtype_inherits_tablename(self):
        class Content(ProtoModel):
            __tablename__: ClassVar[str] = 'det_content4'
            __storable__: ClassVar[bool] = True
            __discriminator__: ClassVar[str] = 'content_type'
            title: str = Field(default='')

        class Video(Content):
            video_url: str = Field(default='')

        assert Video.__tablename__ == 'det_content4'

    def test_subtype_has_discriminator_field_with_own_default(self):
        class Content(ProtoModel):
            __tablename__: ClassVar[str] = 'det_content5'
            __storable__: ClassVar[bool] = True
            __discriminator__: ClassVar[str] = 'content_type'
            title: str = Field(default='')

        class Article(Content):
            body: str = Field(default='')

        assert 'content_type' in Article.model_fields
        assert Article.model_fields['content_type'].default == 'Article'

    def test_subtype_sti_root_points_to_root(self):
        class Content(ProtoModel):
            __tablename__: ClassVar[str] = 'det_content6'
            __storable__: ClassVar[bool] = True
            __discriminator__: ClassVar[str] = 'content_type'
            title: str = Field(default='')

        class Article(Content):
            body: str = Field(default='')

        assert Article.__sti_root__ is Content

    def test_mixin_injected(self):
        class Content(ProtoModel):
            __tablename__: ClassVar[str] = 'det_content7'
            __storable__: ClassVar[bool] = True
            __discriminator__: ClassVar[str] = 'content_type'
            title: str = Field(default='')

        assert issubclass(Content, DiscriminatorMixin)

    def test_mixin_inherited_by_subtype(self):
        class Content(ProtoModel):
            __tablename__: ClassVar[str] = 'det_content8'
            __storable__: ClassVar[bool] = True
            __discriminator__: ClassVar[str] = 'content_type'
            title: str = Field(default='')

        class Article(Content):
            body: str = Field(default='')

        assert issubclass(Article, DiscriminatorMixin)

    def test_multiple_subtypes(self):
        class Content(ProtoModel):
            __tablename__: ClassVar[str] = 'det_content9'
            __storable__: ClassVar[bool] = True
            __discriminator__: ClassVar[str] = 'content_type'
            title: str = Field(default='')

        class Article(Content):
            body: str = Field(default='')

        class Video(Content):
            video_url: str = Field(default='')
            duration: int = Field(default=0)

        assert len(Content.__subtypes__) == 2
        assert 'Article' in Content.__subtypes__
        assert 'Video' in Content.__subtypes__

    def test_non_sti_class_unaffected(self):
        class RegularModel(ProtoModel):
            __tablename__: ClassVar[str] = 'det_regular'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')

        assert not hasattr(RegularModel, '__subtypes__') or RegularModel.__subtypes__ == {}
        assert not issubclass(RegularModel, DiscriminatorMixin)

    def test_discriminator_default_value_on_instance(self):
        class Content(ProtoModel):
            __tablename__: ClassVar[str] = 'det_content10'
            __storable__: ClassVar[bool] = True
            __discriminator__: ClassVar[str] = 'content_type'
            title: str = Field(default='')

        class Article(Content):
            body: str = Field(default='')

        article = Article(title='Test', body='Hello')
        assert article.content_type == 'Article'

        content = Content(title='Generic')
        assert content.content_type == 'Content'


# ══════════════════════════════════════════════════════════════════
# 2. Storage CRUD with Real SQLite
# ══════════════════════════════════════════════════════════════════

class TestSTICrud:
    """CRUD operations through DiscriminatorMixin + real SQLite storage."""

    def _setup_models(self, storage):
        """Create STI models and register with storage."""
        class Content(ProtoModel):
            __tablename__: ClassVar[str] = 'crud_content'
            __storable__: ClassVar[bool] = True
            __discriminator__: ClassVar[str] = 'content_type'
            title: str = Field(default='')
            author: str = Field(default='')

        class Article(Content):
            body: str = Field(default='')

        class Video(Content):
            video_url: str = Field(default='')
            duration: int = Field(default=0)

        # Register root and subtypes with storage
        Content.set_storage(storage)
        Content.create_table()
        storage.migrate_table(Content)

        Article.set_storage(storage)
        storage.migrate_table(Article)

        Video.set_storage(storage)
        storage.migrate_table(Video)

        return Content, Article, Video

    def test_create_article(self, storage):
        Content, Article, Video = self._setup_models(storage)
        article = Article.create(Article(title='My Article', author='Alice', body='Hello world'))
        assert article.id > 0
        assert article.content_type == 'Article'
        assert article.title == 'My Article'
        assert article.body == 'Hello world'

    def test_create_video(self, storage):
        Content, Article, Video = self._setup_models(storage)
        video = Video.create(Video(title='My Video', author='Bob', video_url='https://example.com/v.mp4', duration=120))
        assert video.id > 0
        assert video.content_type == 'Video'
        assert video.video_url == 'https://example.com/v.mp4'

    def test_create_base_content(self, storage):
        Content, Article, Video = self._setup_models(storage)
        content = Content.create(Content(title='Generic', author='Charlie'))
        assert content.id > 0
        assert content.content_type == 'Content'

    def test_list_subtype_filters(self, storage):
        Content, Article, Video = self._setup_models(storage)
        Article.create(Article(title='A1', author='Alice', body='Body 1'))
        Article.create(Article(title='A2', author='Alice', body='Body 2'))
        Video.create(Video(title='V1', author='Bob', video_url='https://v1.mp4'))

        articles = Article.list()
        assert len(articles) == 2
        assert all(a.content_type == 'Article' for a in articles)

        videos = Video.list()
        assert len(videos) == 1
        assert videos[0].content_type == 'Video'

    def test_list_root_returns_all(self, storage):
        Content, Article, Video = self._setup_models(storage)
        Article.create(Article(title='A1', author='Alice', body='Body'))
        Video.create(Video(title='V1', author='Bob', video_url='https://v.mp4'))
        Content.create(Content(title='C1', author='Charlie'))

        all_content = Content.list()
        assert len(all_content) == 3

    def test_list_subtype_with_sql_filter(self, storage):
        Content, Article, Video = self._setup_models(storage)
        Article.create(Article(title='A1', author='Alice', body='Body 1'))
        Article.create(Article(title='A2', author='Bob', body='Body 2'))
        Video.create(Video(title='V1', author='Alice', video_url='https://v.mp4'))

        # Filter articles by author
        alice_articles = Article.list(sql_filter=("author = ?", ["Alice"]))
        assert len(alice_articles) == 1
        assert alice_articles[0].title == 'A1'

    def test_get_returns_correct_subtype(self, storage):
        Content, Article, Video = self._setup_models(storage)
        created = Article.create(Article(title='A1', author='Alice', body='Body'))

        # Get via Article class
        result = Article.get(created.id)
        assert isinstance(result, Article)
        assert result.body == 'Body'
        assert result.content_type == 'Article'

    def test_get_via_root_returns_subtype(self, storage):
        Content, Article, Video = self._setup_models(storage)
        created = Article.create(Article(title='A1', author='Alice', body='Body'))

        # Get via Content (root) class — should return Article instance
        result = Content.get(created.id)
        assert isinstance(result, Article)
        assert result.body == 'Body'
        assert result.content_type == 'Article'

    def test_get_base_content_via_root(self, storage):
        Content, Article, Video = self._setup_models(storage)
        created = Content.create(Content(title='Generic', author='Charlie'))

        result = Content.get(created.id)
        assert isinstance(result, Content)
        assert result.content_type == 'Content'

    def test_get_nonexistent(self, storage):
        Content, Article, Video = self._setup_models(storage)
        result = Content.get(9999)
        assert result is None

    def test_update_preserves_discriminator(self, storage):
        Content, Article, Video = self._setup_models(storage)
        created = Article.create(Article(title='A1', author='Alice', body='Old body'))

        Article.update(created.id, {'title': 'Updated Title', 'body': 'New body'})
        result = Article.get(created.id)
        assert result.title == 'Updated Title'
        assert result.body == 'New body'
        assert result.content_type == 'Article'  # discriminator preserved

    def test_update_strips_discriminator(self, storage):
        """Ensure discriminator is stripped from update data (can't change type)."""
        Content, Article, Video = self._setup_models(storage)
        created = Article.create(Article(title='A1', author='Alice', body='Body'))

        # Try to change discriminator — should be stripped
        Article.update(created.id, {'content_type': 'Video', 'title': 'Sneaky'})
        result = Article.get(created.id)
        assert result.content_type == 'Article'  # unchanged
        assert result.title == 'Sneaky'

    def test_delete(self, storage):
        Content, Article, Video = self._setup_models(storage)
        created = Article.create(Article(title='A1', author='Alice', body='Body'))
        Article.delete(created.id)
        assert Article.get(created.id) is None


# ══════════════════════════════════════════════════════════════════
# 3. Migration
# ══════════════════════════════════════════════════════════════════

class TestSTIMigration:
    """Discriminator column, orphan protection, and index creation."""

    def test_discriminator_column_created(self, storage, db_path):
        class Content(ProtoModel):
            __tablename__: ClassVar[str] = 'mig_content'
            __storable__: ClassVar[bool] = True
            __discriminator__: ClassVar[str] = 'content_type'
            title: str = Field(default='')

        Content.set_storage(storage)
        Content.create_table()

        cols = get_columns(db_path, 'mig_content')
        assert 'content_type' in cols

    def test_discriminator_index_created(self, storage, db_path):
        class Content(ProtoModel):
            __tablename__: ClassVar[str] = 'mig_content2'
            __storable__: ClassVar[bool] = True
            __discriminator__: ClassVar[str] = 'content_type'
            title: str = Field(default='')

        Content.set_storage(storage)
        Content.create_table()

        indexes = get_indexes(db_path, 'mig_content2')
        assert 'idx_mig_content2_content_type' in indexes

    def test_subtype_columns_added_by_migration(self, storage, db_path):
        class Content(ProtoModel):
            __tablename__: ClassVar[str] = 'mig_content3'
            __storable__: ClassVar[bool] = True
            __discriminator__: ClassVar[str] = 'content_type'
            title: str = Field(default='')

        class Article(Content):
            body: str = Field(default='')

        Content.set_storage(storage)
        Content.create_table()
        storage.migrate_table(Content)

        Article.set_storage(storage)
        storage.migrate_table(Article)

        cols = get_columns(db_path, 'mig_content3')
        assert 'body' in cols
        assert 'content_type' in cols
        assert 'title' in cols

    def test_orphan_protection_no_cross_subtype_drop(self, storage, db_path):
        """migrate_table(Video) must NOT drop Article's 'body' column."""
        class Content(ProtoModel):
            __tablename__: ClassVar[str] = 'mig_content4'
            __storable__: ClassVar[bool] = True
            __discriminator__: ClassVar[str] = 'content_type'
            title: str = Field(default='')

        class Article(Content):
            body: str = Field(default='')

        class Video(Content):
            video_url: str = Field(default='')

        Content.set_storage(storage)
        Content.create_table()
        storage.migrate_table(Content)

        Article.set_storage(storage)
        storage.migrate_table(Article)

        Video.set_storage(storage)
        storage.migrate_table(Video)

        cols = get_columns(db_path, 'mig_content4')
        # Both Article's 'body' and Video's 'video_url' should exist
        assert 'body' in cols
        assert 'video_url' in cols
        assert 'content_type' in cols


# ══════════════════════════════════════════════════════════════════
# 4. Edge Cases
# ══════════════════════════════════════════════════════════════════

class TestSTIEdgeCases:
    """Edge cases: abstract base, non-STI inheritance, empty subtypes."""

    def test_non_sti_inheritance_unaffected(self):
        """Regular inheritance without __discriminator__ works as before."""
        class Base(ProtoModel):
            __tablename__: ClassVar[str] = 'edge_base'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')

        class Child(Base):
            extra: str = Field(default='')

        assert not hasattr(Base, '__sti_root__') or Base.__sti_root__ is None
        assert not issubclass(Base, DiscriminatorMixin)

    def test_root_with_no_subtypes_crud(self, storage):
        """Root with no subtypes should work like a regular model."""
        class Standalone(ProtoModel):
            __tablename__: ClassVar[str] = 'edge_standalone'
            __storable__: ClassVar[bool] = True
            __discriminator__: ClassVar[str] = 'content_type'
            name: str = Field(default='')

        Standalone.set_storage(storage)
        Standalone.create_table()
        storage.migrate_table(Standalone)

        created = Standalone.create(Standalone(name='Test'))
        assert created.content_type == 'Standalone'

        result = Standalone.get(created.id)
        assert result.name == 'Test'
        assert result.content_type == 'Standalone'

    def test_list_empty_subtype(self, storage):
        """Listing a subtype with no records returns empty list."""
        class Content(ProtoModel):
            __tablename__: ClassVar[str] = 'edge_content'
            __storable__: ClassVar[bool] = True
            __discriminator__: ClassVar[str] = 'content_type'
            title: str = Field(default='')

        class Article(Content):
            body: str = Field(default='')

        Content.set_storage(storage)
        Content.create_table()
        storage.migrate_table(Content)
        Article.set_storage(storage)
        storage.migrate_table(Article)

        articles = Article.list()
        assert articles == []

    def test_custom_discriminator_name(self):
        """User can choose any non-underscore field name."""
        class Shape(ProtoModel):
            __tablename__: ClassVar[str] = 'edge_shapes'
            __storable__: ClassVar[bool] = True
            __discriminator__: ClassVar[str] = 'shape_kind'
            area: float = Field(default=0.0)

        class Circle(Shape):
            radius: float = Field(default=0.0)

        assert 'shape_kind' in Shape.model_fields
        assert Shape.model_fields['shape_kind'].default == 'Shape'
        assert Circle.model_fields['shape_kind'].default == 'Circle'
        assert Circle.__sti_root__ is Shape

    def test_discriminator_in_storage_dict(self):
        """Discriminator field appears in _storage_dict (used by create)."""
        class Content(ProtoModel):
            __tablename__: ClassVar[str] = 'edge_sdict'
            __storable__: ClassVar[bool] = True
            __discriminator__: ClassVar[str] = 'content_type'
            title: str = Field(default='')

        class Article(Content):
            body: str = Field(default='')

        article = Article(title='Test', body='Hello')
        d = article._storage_dict(exclude_unset=False)
        assert d['content_type'] == 'Article'

    def test_get_as_dict(self, storage):
        """get(as_dict=True) returns dict with discriminator value."""
        class Content(ProtoModel):
            __tablename__: ClassVar[str] = 'edge_asdict'
            __storable__: ClassVar[bool] = True
            __discriminator__: ClassVar[str] = 'content_type'
            title: str = Field(default='')

        class Article(Content):
            body: str = Field(default='')

        Content.set_storage(storage)
        Content.create_table()
        storage.migrate_table(Content)
        Article.set_storage(storage)
        storage.migrate_table(Article)

        created = Article.create(Article(title='Test', body='Body'))
        data = Article.get(created.id, as_dict=True)
        assert isinstance(data, dict)
        assert data['content_type'] == 'Article'
        assert data['title'] == 'Test'


# ══════════════════════════════════════════════════════════════════
# 5. Schema Extension
# ══════════════════════════════════════════════════════════════════

class TestSTISchema:
    """Polymorphic schema: oneOf, discriminator mapping, $defs per subtype."""

    def test_root_schema_has_one_of(self):
        class Content(ProtoModel):
            __tablename__: ClassVar[str] = 'sch_content'
            __storable__: ClassVar[bool] = True
            __discriminator__: ClassVar[str] = 'content_type'
            title: str = Field(default='')

        class Article(Content):
            body: str = Field(default='')

        class Video(Content):
            video_url: str = Field(default='')

        schema = Content.schema()
        assert 'oneOf' in schema
        assert 'discriminator' in schema

    def test_root_schema_discriminator_mapping(self):
        class Content(ProtoModel):
            __tablename__: ClassVar[str] = 'sch_content2'
            __storable__: ClassVar[bool] = True
            __discriminator__: ClassVar[str] = 'content_type'
            title: str = Field(default='')

        class Article(Content):
            body: str = Field(default='')

        schema = Content.schema()
        mapping = schema['discriminator']['mapping']
        assert schema['discriminator']['propertyName'] == 'content_type'
        assert 'Article' in mapping
        assert 'Content' in mapping  # root included (not abstract)

    def test_root_schema_defs_has_subtypes(self):
        class Content(ProtoModel):
            __tablename__: ClassVar[str] = 'sch_content3'
            __storable__: ClassVar[bool] = True
            __discriminator__: ClassVar[str] = 'content_type'
            title: str = Field(default='')

        class Article(Content):
            body: str = Field(default='')

        class Video(Content):
            video_url: str = Field(default='')

        schema = Content.schema()
        assert 'Article' in schema['$defs']
        assert 'Video' in schema['$defs']
        assert 'Content' in schema['$defs']

    def test_subtype_def_has_metadata(self):
        class Content(ProtoModel):
            __tablename__: ClassVar[str] = 'sch_content4'
            __storable__: ClassVar[bool] = True
            __discriminator__: ClassVar[str] = 'content_type'
            title: str = Field(default='')

        class Article(Content):
            body: str = Field(default='')

        schema = Content.schema()
        article_def = schema['$defs']['Article']
        assert article_def['__name__'] == 'Article'
        assert '$id' in article_def
        assert 'methods' in article_def
        assert 'access' in article_def

    def test_subtype_def_has_discriminator_const(self):
        class Content(ProtoModel):
            __tablename__: ClassVar[str] = 'sch_content5'
            __storable__: ClassVar[bool] = True
            __discriminator__: ClassVar[str] = 'content_type'
            title: str = Field(default='')

        class Article(Content):
            body: str = Field(default='')

        schema = Content.schema()
        article_def = schema['$defs']['Article']
        assert article_def['properties']['content_type']['const'] == 'Article'
        assert article_def['properties']['content_type']['ui']['display'] is False

    def test_subtype_schema_has_const_discriminator(self):
        class Content(ProtoModel):
            __tablename__: ClassVar[str] = 'sch_content6'
            __storable__: ClassVar[bool] = True
            __discriminator__: ClassVar[str] = 'content_type'
            title: str = Field(default='')

        class Article(Content):
            body: str = Field(default='')

        schema = Article.schema()
        assert 'properties' in schema
        assert schema['properties']['content_type']['const'] == 'Article'

    def test_non_sti_model_schema_unchanged(self):
        class Regular(ProtoModel):
            __tablename__: ClassVar[str] = 'sch_regular'
            __storable__: ClassVar[bool] = True
            name: str = Field(default='')

        schema = Regular.schema()
        assert 'oneOf' not in schema
        assert 'discriminator' not in schema

    def test_subtype_schema_has_all_fields(self):
        class Content(ProtoModel):
            __tablename__: ClassVar[str] = 'sch_content7'
            __storable__: ClassVar[bool] = True
            __discriminator__: ClassVar[str] = 'content_type'
            title: str = Field(default='')

        class Article(Content):
            body: str = Field(default='')

        schema = Article.schema()
        assert 'title' in schema['properties']
        assert 'body' in schema['properties']
        assert 'content_type' in schema['properties']


# ══════════════════════════════════════════════════════════════════
# 6. Dump / Model Response
# ══════════════════════════════════════════════════════════════════

class TestSTIDump:
    """Discriminator in model_response() output."""

    def test_discriminator_in_model_response(self, storage):
        class Content(ProtoModel):
            __tablename__: ClassVar[str] = 'dmp_content'
            __storable__: ClassVar[bool] = True
            __discriminator__: ClassVar[str] = 'content_type'
            title: str = Field(default='')

        class Article(Content):
            body: str = Field(default='')

        Content.set_storage(storage)
        Content.create_table()
        storage.migrate_table(Content)
        Article.set_storage(storage)
        storage.migrate_table(Article)

        created = Article.create(Article(title='Test', body='Body'))
        result = Article.get(created.id)
        response = result.model_response()
        assert response['content_type'] == 'Article'
        assert '$schema' in response
        assert '$id' in response
