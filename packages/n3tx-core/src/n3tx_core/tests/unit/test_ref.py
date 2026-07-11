"""Tests for the canonical HTTP(S) ``Ref[T]`` value."""

import pytest
from pydantic import BaseModel

from n3tx_core.models.ref import Ref, flatten_refs, local_ref_id
from n3tx_core.utils.typer import Ref as CompatRef

pytestmark = pytest.mark.unit


class File(BaseModel):
    id: int = 0


class TestRefUrl:
    REF = "https://storage.example.com/api/v1/File/file-12"

    def test_ref_is_a_validated_string_value(self):
        ref = Ref[File](self.REF)

        assert isinstance(ref, str)
        assert ref == self.REF
        assert str(ref) == self.REF

    def test_extracts_canonical_url_parts(self):
        assert Ref.base_url(self.REF) == "https://storage.example.com/api/v1"
        assert Ref.schema(self.REF) == "File"
        assert Ref.id(self.REF) == "file-12"

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "file-12",
            12,
            "/File/file-12",
            "n3tx://storage/File/file-12",
            "ftp://storage.example.com/File/file-12",
            "https://storage.example.com/File",
            "https://storage.example.com/File/file-12?download=1",
            "https://storage.example.com/File/file-12#fragment",
        ],
    )
    def test_rejects_non_entity_urls(self, value):
        with pytest.raises((TypeError, ValueError)):
            Ref[File](value)

    def test_rejects_target_schema_mismatch(self):
        with pytest.raises(ValueError, match="Reference target mismatch"):
            Ref[File]("https://storage.example.com/Artifact/artifact-1")

    def test_pydantic_serializes_ref_as_url_string(self):
        class Job(BaseModel):
            file: Ref[File]

        job = Job(file=self.REF)

        assert isinstance(job.file, Ref)
        assert job.file == self.REF
        assert job.model_dump() == {"file": self.REF}
        assert job.model_dump_json() == '{"file":"https://storage.example.com/api/v1/File/file-12"}'

    def test_pydantic_schema_declares_url_ref_target(self):
        class Job(BaseModel):
            file: Ref[File]
            files: list[Ref[File]] = []

        properties = Job.model_json_schema()["properties"]
        assert properties["file"] == {
            "format": "uri",
            "title": "File",
            "type": "string",
            "x-ref": "File",
        }
        assert properties["files"]["items"] == {
            "format": "uri",
            "type": "string",
            "x-ref": "File",
        }

    def test_flatten_refs_preserves_url_strings(self):
        class Document(BaseModel):
            file: Ref[File]

        document = Document(file=self.REF)
        assert flatten_refs(document) == {"file": self.REF}

    def test_local_ref_id_extracts_current_service_url_only(self):
        assert local_ref_id(
            "https://api.example.com/api/v1/File/12",
            target_cls=File,
            api_url="https://api.example.com/api/v1",
        ) == 12
        assert local_ref_id(
            self.REF,
            target_cls=File,
            api_url="https://api.example.com/api/v1",
        ) is None

    def test_hydrate_uses_explicit_context_without_mutating_ref(self):
        class Resolver:
            def __init__(self):
                self.calls = []

            def resolve(self, ref, target_cls=None, user=None, context=None):
                self.calls.append((ref, target_cls, user, context))
                return File(id=12)

        resolver = Resolver()
        ref = Ref[File](self.REF)

        hydrated = ref.hydrate(user={"id": 7}, context=resolver)

        assert hydrated == File(id=12)
        assert ref == self.REF
        assert resolver.calls == [(self.REF, File, {"id": 7}, resolver)]

    def test_hydrate_requires_a_resolver_context(self):
        with pytest.raises(RuntimeError, match="resolver"):
            Ref[File](self.REF).hydrate()

    def test_utils_typer_compatibility_import(self):
        assert CompatRef is Ref
