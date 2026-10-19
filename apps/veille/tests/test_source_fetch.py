import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_core.utils.registrar import register_model

from models.source import Source
from models.web_tools import WebTools


@pytest.fixture
def storage(tmp_path):
    return SQLiteStorage(str(tmp_path / 'test.db'))


@pytest.mark.asyncio
async def test_source_fetch_persists_scrape_content_and_hash(storage, monkeypatch):
    register_model(Source, storage=storage)

    created = Source.create(Source(name='Test Source', url='https://example.com'))

    async def mock_fetch(url: str) -> dict:
        return {
            'url': url,
            'final_url': url,
            'status': 200,
            'text': 'Grant funding program now open',
            'truncated': False,
            'error': '',
            'method': 'scrape',
        }

    monkeypatch.setattr('models.source._fetch_http_content', mock_fetch)

    result = await created.fetch()
    refreshed = Source.get(created.id)

    assert result['id'] == created.id
    assert refreshed.scraped_content == 'Grant funding program now open'
    assert refreshed.scraped_content_hash.startswith('sha256:')
    assert refreshed.previous_content_hash is None
    assert refreshed.scrape_method == 'scrape'
    assert refreshed.scrape_status == 200
    assert refreshed.scrape_changed is False
    assert refreshed.content_updated_at is not None
    assert refreshed.last_scrape_error == ''


@pytest.mark.asyncio
async def test_webtools_scrape_with_source_id_returns_updated_source(storage, monkeypatch):
    register_model(Source, storage=storage)

    created = Source.create(Source(name='Tracked Source', url='https://tracked.example.com'))

    async def mock_fetch(url: str) -> dict:
        return {
            'url': url,
            'final_url': f'{url}/landing',
            'status': 200,
            'text': 'Updated content from source page',
            'truncated': False,
            'error': '',
            'method': 'scrape',
        }

    monkeypatch.setattr('models.web_tools._fetch_http_content', mock_fetch)

    result = await WebTools.scrape(created.url, created.id)

    assert result['id'] == created.id
    assert result['scraped_content'] == 'Updated content from source page'
    assert result['scraped_final_url'] == 'https://tracked.example.com/landing'


@pytest.mark.asyncio
async def test_source_fetch_marks_change_when_hash_differs(storage, monkeypatch):
    register_model(Source, storage=storage)

    created = Source.create(Source(
        name='Changed Source',
        url='https://changed.example.com',
        scraped_content='Old content',
        scraped_content_hash='sha256:oldhash',
        content_updated_at='2026-04-20T10:00:00+00:00',
    ))

    async def mock_fetch(url: str) -> dict:
        return {
            'url': url,
            'final_url': url,
            'status': 200,
            'text': 'New changed content',
            'truncated': False,
            'error': '',
            'method': 'scrape',
        }

    monkeypatch.setattr('models.source._fetch_http_content', mock_fetch)

    await created.fetch()
    refreshed = Source.get(created.id)

    assert refreshed.scrape_changed is True
    assert refreshed.previous_content_hash == 'sha256:oldhash'
    assert refreshed.scraped_content == 'New changed content'
    assert refreshed.scraped_content_hash != 'sha256:oldhash'
