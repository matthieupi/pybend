"""Retain first-token streaming coverage with explicit authorized parent scope.

The synthetic model emits nonempty PartStart text like OpenAI-compatible
streams, without a provider request. The first token must not be discarded.
"""

from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import AsyncIterator

import pytest
from pydantic import Field
from pydantic_ai.messages import (
    ModelResponse, ModelResponseStreamEvent, TextPart,
)
from pydantic_ai.models import Model, StreamedResponse

import n3tx_agents  # noqa: F401
from n3tx_actors.models.actor_model import ActorModel


pytestmark = pytest.mark.unit


@dataclass
class _OpenAIStyleStreamedResponse(StreamedResponse):
    """Emit initial PartStart text followed by native text deltas."""

    _tokens: list = field(default_factory=lambda: [
        'Hello', ' World', ' from', ' agent',
    ])

    async def _get_event_iterator(
        self,
    ) -> AsyncIterator[ModelResponseStreamEvent]:
        """Use the native parts manager for start and delta event generation."""
        # 0. The first token creates a nonempty start, not an empty placeholder.
        for event in self._parts_manager.handle_text_delta(
            vendor_part_id=0, content=self._tokens[0],
        ):
            yield event
        # 1. Remaining tokens extend the same native response part.
        for token in self._tokens[1:]:
            for event in self._parts_manager.handle_text_delta(
                vendor_part_id=0, content=token,
            ):
                yield event

    @property
    def model_name(self) -> str:
        """Identify the synthetic model without a provider."""
        return 'fake-openai'

    @property
    def provider_name(self) -> str:
        """Identify the synthetic response source."""
        return 'fake-openai'

    @property
    def provider_url(self) -> str | None:
        """Expose no network provider endpoint."""
        return None

    @property
    def timestamp(self) -> datetime:
        """Supply the native response timestamp."""
        return datetime.now(timezone.utc)


class FakeOpenAIModel(Model):
    """Mimic nonempty initial streaming text without external inference."""

    async def request(self, messages, model_settings, model_request_parameters):
        """Return the exact synthetic completed response."""
        return ModelResponse(
            parts=[TextPart(content='Hello World from agent')],
            model_name='fake-openai',
        )

    @asynccontextmanager
    async def request_stream(
        self, messages, model_settings, model_request_parameters,
        run_context=None,
    ):
        """Yield the native synthetic stream without opening any transport."""
        yield _OpenAIStyleStreamedResponse(
            model_request_parameters=model_request_parameters,
        )

    @property
    def model_name(self) -> str:
        """Identify the synthetic model."""
        return 'fake-openai'

    @property
    def system(self) -> str:
        """Identify the synthetic provider family."""
        return 'fake-openai'


class StreamScanner(ActorModel):
    """Require explicit saved business scope for synthetic streaming."""

    __tablename__ = 'stream_scanners'
    __storable__ = False
    __agent__ = True
    name: str = Field(default='scanner')


async def _chunks(agent_context):
    """Collect the real native runtime stream under the synthetic parent ACL."""
    # 0. Execute the shared runtime with the provider-free model.
    scanner = StreamScanner(addr='stream_scanners/1')
    return [chunk async for chunk in scanner.run_stream(
        task='Test task', prompt='Test prompt', tools=[],
        llm=FakeOpenAIModel(), **agent_context,
    )]


class TestRunStreamFirstTokenHandling:
    """Retain complete start/delta text and terminal answer parity."""

    @pytest.mark.asyncio
    async def test_text_in_part_start_event_is_yielded(self, agent_context):
        """Do not discard nonempty text delivered through PartStart."""
        # 0. Collect text from actual runtime events.
        chunks = await _chunks(agent_context)
        text = ''.join(
            chunk['data']['text'] for chunk in chunks
            if chunk['name'] == 'text'
        )
        # 1. Preserve the initial token as well as the response suffix.
        assert 'Hello' in text, chunks

    @pytest.mark.asyncio
    async def test_first_text_chunk_is_from_part_start_event(
        self, agent_context,
    ):
        """The first native text event contains the exact initial token."""
        # 0. Observe actual native text event boundaries.
        chunks = await _chunks(agent_context)
        text = [chunk for chunk in chunks if chunk['name'] == 'text']
        # 1. Deltas cannot replace or conceal the original start token.
        assert text, chunks
        assert text[0]['data']['text'] == 'Hello'

    @pytest.mark.asyncio
    async def test_all_text_chunks_match_done_answer(self, agent_context):
        """Assembled streaming text equals the terminal native answer."""
        # 0. Collect both incremental and terminal events from one invocation.
        chunks = await _chunks(agent_context)
        text = ''.join(
            chunk['data']['text'] for chunk in chunks
            if chunk['name'] == 'text'
        )
        done = [chunk for chunk in chunks if chunk['name'] == 'done']
        # 1. Preserve exact response text and root identity through completion.
        assert len(done) == 1, chunks
        assert text == done[0]['data']['answer']
        assert text == 'Hello World from agent'
        assert done[0]['data']['thread_id'] > 0


# Changelog (Python has no block-comment syntax).
# - 2026-11-04: Supply real saved parent scope to first-token regressions;
#   retain synthetic PartStart generation and exact terminal text parity.
