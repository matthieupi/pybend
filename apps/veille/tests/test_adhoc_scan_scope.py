"""Tests for adhoc scan scope — single URL scan must not expand into a full scan.

Bug: When clicking "Scan URL" in the run page, the adhoc scan starts by
scanning the provided URL, but then goes on to process agent-discovered
sources, effectively becoming a full scan. The adhoc endpoint should only
scrape the one URL provided.

Root cause hypothesis: _process_queue() unconditionally enqueues
agent-discovered sources (via _get_discovered_sources()), even when
invoked from adhoc() which should process only the single provided URL.
"""

import sys
import os
import asyncio
import pytest
from collections import deque
from typing import ClassVar, Optional
from unittest.mock import AsyncMock, patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pydantic import Field

from n3tx_actors.actor import Actor
from n3tx_actors.matrix import Matrix
from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.authorize import AUTHENTICATED
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_core.utils.registrar import register_model, registered_models


@pytest.fixture(autouse=True)
def reset_state():
    saved_matrix = Actor.__matrix__
    saved_children = Actor.__children__.copy()
    saved_matrix_children = Matrix.__children__.copy()
    saved_models = dict(registered_models)

    Actor.__matrix__ = None
    Actor.__children__ = {}
    Matrix.__children__ = {}
    registered_models.clear()

    yield

    Actor.__matrix__ = saved_matrix
    Actor.__children__ = saved_children
    Matrix.__children__ = saved_matrix_children
    registered_models.clear()
    registered_models.update(saved_models)


@pytest.fixture
def fresh_matrix():
    return Matrix()


@pytest.fixture
def storage(tmp_path):
    return SQLiteStorage(str(tmp_path / 'test.db'))


class TestAdhocScanScope:
    """Adhoc scan should only process the single provided URL."""

    @pytest.mark.asyncio
    async def test_adhoc_does_not_enqueue_discovered_sources(self, fresh_matrix, storage):
        """When running an adhoc scan, _process_queue should NOT call
        _get_discovered_sources() or enqueue any additional sources.

        The bug: after scraping the adhoc URL, _process_queue calls
        _get_discovered_sources() which finds sources the agent created,
        adds them to the work queue, and the scan snowballs into a full run.
        """
        from models.run import Run, _get_discovered_sources
        register_model(Run, storage=storage)

        run = Run(id=1, status='pending', type='adhoc')

        # Track which sources get processed
        sources_processed = []

        async def mock_scrape(source, prompt, user_dict):
            sources_processed.append(source)
            # Simulate agent creating a discovered source
            yield {'name': 'text', 'data': {'text': 'found a link'}}

        # Mock _get_discovered_sources to return a "discovered" source
        # (simulates what happens when the agent calls sources_create)
        discovered = [
            {'id': 99, 'url': 'https://discovered.example.com',
             'name': 'Discovered Portal', 'agent_discovered': True,
             'language': 'en', 'scraping_notes': '', 'active': True}
        ]

        with patch.object(run, '_scrape_source', side_effect=mock_scrape), \
             patch.object(run, '_build_prompt', return_value='test prompt'), \
             patch('models.run._get_discovered_sources', return_value=discovered), \
             patch('models.run.Run.update'), \
             patch('models.run.Source'):

            # Adhoc: single synthetic source
            synthetic = {'id': None, 'url': 'https://target.example.com',
                         'name': 'https://target.example.com',
                         'language': 'en', 'scraping_notes': ''}
            work_queue = deque([synthetic])

            chunks = []
            async for chunk in run._process_queue(work_queue, None, adhoc=True):
                chunks.append(chunk)

        # BUG: with the current code, both the synthetic source AND the
        # discovered source get processed. Only the synthetic should be.
        assert len(sources_processed) == 1, (
            f"Adhoc scan processed {len(sources_processed)} sources, "
            f"expected exactly 1. Sources: {[s.get('url') for s in sources_processed]}"
        )
        assert sources_processed[0]['url'] == 'https://target.example.com'

    @pytest.mark.asyncio
    async def test_adhoc_yields_only_one_source_start(self, fresh_matrix, storage):
        """Adhoc scan should emit exactly one source_start event —
        the one for the provided URL. No more."""
        from models.run import Run
        register_model(Run, storage=storage)

        run = Run(id=1, status='pending', type='adhoc')

        async def mock_scrape(source, prompt, user_dict):
            yield {'name': 'text', 'data': {'text': 'scraped'}}

        discovered = [
            {'id': 50, 'url': 'https://extra1.example.com',
             'name': 'Extra 1', 'agent_discovered': True,
             'language': 'en', 'scraping_notes': '', 'active': True},
            {'id': 51, 'url': 'https://extra2.example.com',
             'name': 'Extra 2', 'agent_discovered': True,
             'language': 'en', 'scraping_notes': '', 'active': True},
        ]

        with patch.object(run, '_scrape_source', side_effect=mock_scrape), \
             patch.object(run, '_build_prompt', return_value='test prompt'), \
             patch('models.run._get_discovered_sources', return_value=discovered), \
             patch('models.run.Run.update'), \
             patch('models.run.Source'):

            synthetic = {'id': None, 'url': 'https://single-scan.example.com',
                         'name': 'https://single-scan.example.com',
                         'language': 'en', 'scraping_notes': ''}
            work_queue = deque([synthetic])

            source_starts = []
            async for chunk in run._process_queue(work_queue, None, adhoc=True):
                if chunk.get('name') == 'source_start':
                    source_starts.append(chunk)

        # BUG: current code emits 3 source_start events (1 adhoc + 2 discovered)
        assert len(source_starts) == 1, (
            f"Adhoc scan emitted {len(source_starts)} source_start events, "
            f"expected 1. URLs: {[s['data']['url'] for s in source_starts]}"
        )
        assert source_starts[0]['data']['url'] == 'https://single-scan.example.com'

    @pytest.mark.asyncio
    async def test_full_run_still_enqueues_discovered_sources(self, fresh_matrix, storage):
        """Full runs should still enqueue discovered sources — the fix must
        not break the full scan flow."""
        from models.run import Run
        register_model(Run, storage=storage)

        run = Run(id=1, status='pending', type='full')
        sources_processed = []
        call_count = [0]

        async def mock_scrape(source, prompt, user_dict):
            sources_processed.append(source)
            yield {'name': 'text', 'data': {'text': 'scraped'}}

        # First call returns discovered sources, second returns empty
        def mock_discovered(processed_ids, processed_urls):
            call_count[0] += 1
            if call_count[0] == 1:
                return [
                    {'id': 99, 'url': 'https://discovered.example.com',
                     'name': 'Discovered', 'agent_discovered': True,
                     'language': 'en', 'scraping_notes': '', 'active': True}
                ]
            return []

        with patch.object(run, '_scrape_source', side_effect=mock_scrape), \
             patch.object(run, '_build_prompt', return_value='test prompt'), \
             patch('models.run._get_discovered_sources', side_effect=mock_discovered), \
             patch('models.run.Run.update'), \
             patch('models.run.Source'):

            initial_source = {'id': 1, 'url': 'https://initial.example.com',
                              'name': 'Initial', 'language': 'en',
                              'scraping_notes': ''}
            work_queue = deque([initial_source])

            async for _ in run._process_queue(work_queue, None):
                pass

        # Full run: both initial + discovered should be processed
        assert len(sources_processed) == 2, (
            f"Full run processed {len(sources_processed)} sources, expected 2"
        )
        urls = [s.get('url') for s in sources_processed]
        assert 'https://initial.example.com' in urls
        assert 'https://discovered.example.com' in urls

    @pytest.mark.asyncio
    async def test_adhoc_sources_covered_is_one(self, fresh_matrix, storage):
        """After an adhoc scan completes, _mark_complete should be called
        with sources_covered=1, not N."""
        from models.run import Run
        register_model(Run, storage=storage)

        run = Run(id=1, status='pending', type='adhoc')
        mark_complete_args = []

        async def mock_scrape(source, prompt, user_dict):
            yield {'name': 'text', 'data': {'text': 'scraped'}}

        discovered = [
            {'id': 99, 'url': 'https://discovered.example.com',
             'name': 'Discovered', 'agent_discovered': True,
             'language': 'en', 'scraping_notes': '', 'active': True}
        ]

        original_mark_complete = run._mark_complete

        def capture_mark_complete(grants, sources):
            mark_complete_args.append((grants, sources))

        with patch.object(run, '_scrape_source', side_effect=mock_scrape), \
             patch.object(run, '_build_prompt', return_value='test prompt'), \
             patch('models.run._get_discovered_sources', return_value=discovered), \
             patch('models.run.Run.update'), \
             patch('models.run.Source'), \
             patch.object(run, '_mark_complete', side_effect=capture_mark_complete):

            synthetic = {'id': None, 'url': 'https://adhoc.example.com',
                         'name': 'https://adhoc.example.com',
                         'language': 'en', 'scraping_notes': ''}
            work_queue = deque([synthetic])

            async for _ in run._process_queue(work_queue, None, adhoc=True):
                pass

        assert len(mark_complete_args) == 1
        _, sources_covered = mark_complete_args[0]
        # BUG: sources_covered will be 2 (adhoc + discovered) instead of 1
        assert sources_covered == 1, (
            f"Adhoc scan reported sources_covered={sources_covered}, expected 1"
        )
