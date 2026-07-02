"""Tests for models/ref.py — Ref helpers."""

import pytest
from pydantic import BaseModel

from n3tx_core.models.ref import (
    Ref,
    canonicalize_ref,
    flatten_refs,
    is_distributed_ref,
    is_external_link,
    local_ref_id,
    parse_ref_string,
    public_ref,
)
from n3tx_core.utils.typer import Ref as CompatRef

pytestmark = pytest.mark.unit


class File(BaseModel):
    id: int = 0


class TestRefStringHelpers:

    def test_distributed_ref_detection(self):
        assert is_distributed_ref('n3tx://storage/File/12') is True
        assert is_distributed_ref('/File/12') is False
        assert is_distributed_ref('https://example.com/File/12') is False

    def test_parse_distributed_ref_string(self):
        assert parse_ref_string('n3tx://storage/File/12') == ('storage', 'File', '12')

    def test_parse_local_class_path(self):
        assert parse_ref_string('/File/12') == (None, 'File', '12')

    @pytest.mark.parametrize('value', [
        '',
        'n3tx://storage/File',
        'n3tx:///File/12',
        '/File',
        '/File/12/extra',
        'File/12',
    ])
    def test_parse_rejects_invalid_reference_shapes(self, value):
        with pytest.raises(ValueError):
            parse_ref_string(value)

    def test_configured_remote_http_canonicalizes_to_n3tx(self):
        remotes = {'storage': {'url': 'http://storage:7100'}}
        assert canonicalize_ref(
            'http://storage:7100/File/12', target_cls=File, remotes=remotes,
        ) == 'n3tx://storage/File/12'

    def test_current_api_url_canonicalizes_to_local_id(self):
        assert canonicalize_ref(
            'http://api.local/File/12', target_cls=File, api_url='http://api.local',
        ) == 12

    def test_canonicalize_ref_rejects_target_mismatch(self):
        class Artifact(BaseModel):
            id: int = 0

        with pytest.raises(ValueError, match='Reference target mismatch'):
            canonicalize_ref('/Artifact/12', target_cls=File)

    def test_local_ref_id_accepts_int_path_and_current_api_url(self):
        assert local_ref_id(12, target_cls=File) == 12
        assert local_ref_id('/File/12', target_cls=File) == 12
        assert local_ref_id(
            'http://api.local/File/12', target_cls=File, api_url='http://api.local',
        ) == 12

    def test_public_ref_preserves_distributed_refs(self):
        assert public_ref('n3tx://storage/File/12', target_cls=File) == 'n3tx://storage/File/12'

    def test_public_ref_formats_local_refs_as_class_name_urls(self):
        assert public_ref(12, target_cls=File, api_url='http://api.local') == 'http://api.local/File/12'

    def test_external_link_classification(self):
        assert is_external_link('https://example.com/file.pdf') is True
        assert is_external_link('n3tx://storage/File/12') is False
        assert is_external_link('http://storage:7100/File/12', remotes={'storage': 'http://storage:7100'}) is False

    def test_malformed_configured_remote_http_ref_is_not_matrix_ref(self):
        assert is_external_link(
            'http://storage:7100/not-a-ref',
            remotes={'storage': 'http://storage:7100'},
        ) is True


class TestRefPromotion:

    def test_ref_accepts_distributed_string(self):
        ref = Ref('n3tx://storage/File/12')
        assert ref.id == 'n3tx://storage/File/12'
        assert ref.model_dump() == 'n3tx://storage/File/12'

    def test_distributed_ref_cannot_be_coerced_to_int(self):
        with pytest.raises(TypeError, match='Cannot coerce distributed Ref to int'):
            int(Ref('n3tx://storage/File/12'))

    def test_ref_rejects_unstructured_string(self):
        with pytest.raises(ValueError, match='Invalid FK assignment'):
            Ref('invalid_string')

    def test_flatten_refs_preserves_distributed_ref_values(self):
        class Document(BaseModel):
            file: object

        doc = Document(file=Ref('n3tx://storage/File/12'))
        assert flatten_refs(doc)['file'] == 'n3tx://storage/File/12'

    def test_utils_typer_compatibility_import(self):
        assert CompatRef is Ref
