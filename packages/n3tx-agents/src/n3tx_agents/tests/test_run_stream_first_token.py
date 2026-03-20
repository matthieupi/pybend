"""Tests for run_stream() first-token-missing bug.

Bug: When streaming with OpenAI/Ollama-compatible models, the first text
token arrives as PartStartEvent with TextPart(content=first_token).
run_stream() does not handle PartStartEvent for TextPart, so the first
token is silently dropped.

TestModel does NOT trigger this bug — it sends an empty PartStartEvent
then all words via PartDeltaEvent. Real OpenAI/Ollama models DO trigger it.

These tests use a FakeOpenAIModel that mimics OpenAI streaming behavior
to reproduce the bug reliably without a real API.
"""
import asyncio
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncIterator

import pytest
from pydantic import Field
from pydantic_ai.messages import (
    ModelMessage, ModelResponse, TextPart,
    ModelResponseStreamEvent,
)
from pydantic_ai.models import (
    Model, StreamedResponse, ModelRequestParameters,
    ModelSettings,
)

import n3tx_agents  # noqa — ensure AgentMixin registered
from n3tx_actors.models.actor_model import ActorModel

pytestmark = pytest.mark.unit


# ── Fake model that mimics OpenAI/Ollama streaming ────────────────────────────

@dataclass
class _OpenAIStyleStreamedResponse(StreamedResponse):
    """StreamedResponse that sends first token via PartStartEvent (OpenAI behavior).

    OpenAI streaming emits:
      1. PartStartEvent(part=TextPart(content='Hello'))   ← first token in START
      2. PartDeltaEvent(delta=TextPartDelta(' World'))     ← subsequent deltas

    TestModel emits:
      1. PartStartEvent(part=TextPart(content=''))         ← empty start
      2. PartDeltaEvent(delta=TextPartDelta('Hello '))     ← each word as delta
      3. PartDeltaEvent(delta=TextPartDelta('World'))
    """

    _tokens: list = field(default_factory=lambda: ['Hello', ' World', ' from', ' agent'])

    async def _get_event_iterator(self) -> AsyncIterator[ModelResponseStreamEvent]:
        # First token — no existing part → yields PartStartEvent with non-empty TextPart
        # This is the OpenAI/Ollama behavior that triggers the bug.
        for event in self._parts_manager.handle_text_delta(
            vendor_part_id=0, content=self._tokens[0]
        ):
            yield event

        # Subsequent tokens — existing part → yields PartDeltaEvent
        for token in self._tokens[1:]:
            for event in self._parts_manager.handle_text_delta(
                vendor_part_id=0, content=token
            ):
                yield event

    @property
    def model_name(self) -> str:
        return 'fake-openai'

    @property
    def provider_name(self) -> str:
        return 'fake-openai'

    @property
    def provider_url(self) -> str | None:
        return None

    @property
    def timestamp(self) -> datetime:
        return datetime.now(timezone.utc)


class FakeOpenAIModel(Model):
    """Model that mimics OpenAI streaming (first token in PartStartEvent).

    Produces: 'Hello World from agent'
    With OpenAI streaming, 'Hello' arrives in PartStartEvent.part.content,
    then ' World', ' from', ' agent' arrive in PartDeltaEvent.delta.content_delta.
    """

    async def request(self, messages, model_settings, model_request_parameters):
        return ModelResponse(
            parts=[TextPart(content='Hello World from agent')],
            model_name='fake-openai',
        )

    @asynccontextmanager
    async def request_stream(
        self, messages, model_settings, model_request_parameters, run_context=None
    ):
        yield _OpenAIStyleStreamedResponse(
            model_request_parameters=model_request_parameters,
        )

    @property
    def model_name(self) -> str:
        return 'fake-openai'

    @property
    def system(self) -> str:
        return 'fake-openai'


# ── Model fixture ─────────────────────────────────────────────────────────────


class StreamScanner(ActorModel):
    """Minimal agent model for streaming tests."""
    __tablename__ = 'stream_scanners'
    __storable__ = False
    __agent__ = True
    name: str = Field(default='scanner')


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestRunStreamFirstTokenHandling:
    """run_stream() must yield text from PartStartEvent, not just PartDeltaEvent."""

    @pytest.mark.asyncio
    async def test_text_in_part_start_event_is_yielded(self, fresh_matrix):
        """run_stream() must not drop text that arrives in PartStartEvent.

        OpenAI/Ollama-compatible models send the first text token as
        PartStartEvent(part=TextPart(content=first_token)), NOT as PartDeltaEvent.
        run_stream() must yield this content; currently it is silently dropped.
        """
        scanner = StreamScanner(addr='stream_scanners/1')
        chunks = []
        async for chunk in scanner.run_stream(
            task='Test task',
            prompt='Test prompt',
            tools=[],
            llm=FakeOpenAIModel(),
        ):
            chunks.append(chunk)

        text_chunks = [c for c in chunks if c['name'] == 'text']
        all_text = ''.join(c['data']['text'] for c in text_chunks)

        # The complete text must include 'Hello' (the first token from PartStartEvent)
        assert 'Hello' in all_text, (
            f"First token 'Hello' is missing from streamed text.\n"
            f"Received text: {all_text!r}\n"
            f"All chunks: {[(c['name'], c['data']) for c in chunks]}\n"
            f"Bug confirmed: PartStartEvent TextPart content is dropped by run_stream()."
        )

    @pytest.mark.asyncio
    async def test_first_text_chunk_is_from_part_start_event(self, fresh_matrix):
        """First TEXT event must contain content from PartStartEvent.part.content.

        When the model sends PartStartEvent(part=TextPart(content='Hello')),
        the first 'text' event from run_stream() must contain 'Hello'.
        Currently run_stream() skips this PartStartEvent and 'Hello' is never yielded.
        """
        scanner = StreamScanner(addr='stream_scanners/2')
        chunks = []
        async for chunk in scanner.run_stream(
            task='Test task',
            prompt='Test prompt',
            tools=[],
            llm=FakeOpenAIModel(),
        ):
            chunks.append(chunk)

        text_chunks = [c for c in chunks if c['name'] == 'text']

        assert len(text_chunks) >= 1, (
            f"No text events received at all.\n"
            f"All chunks: {chunks}"
        )

        first_text = text_chunks[0]['data']['text']
        assert first_text == 'Hello', (
            f"Expected first text chunk to be 'Hello' (from PartStartEvent.part.content).\n"
            f"Got: {first_text!r}\n"
            f"This means PartStartEvent.part.content was not yielded — first token dropped."
        )

    @pytest.mark.asyncio
    async def test_all_text_chunks_match_done_answer(self, fresh_matrix):
        """All text chunks joined must equal the answer in the done event.

        If the first token is dropped, the accumulated text won't match done.answer.
        done.answer = 'Hello World from agent' (the full response from the model).
        assembled text = ' World from agent' (missing 'Hello' because PartStartEvent dropped).
        """
        scanner = StreamScanner(addr='stream_scanners/3')
        chunks = []
        async for chunk in scanner.run_stream(
            task='Test task',
            prompt='Test prompt',
            tools=[],
            llm=FakeOpenAIModel(),
        ):
            chunks.append(chunk)

        text_chunks = [c for c in chunks if c['name'] == 'text']
        done_chunks = [c for c in chunks if c['name'] == 'done']

        assert done_chunks, f"No done event received. All chunks: {[c['name'] for c in chunks]}"

        assembled = ''.join(c['data']['text'] for c in text_chunks)
        done_answer = done_chunks[0]['data']['answer']

        assert assembled == done_answer, (
            f"Text assembled from chunks != done.answer.\n"
            f"Chunks assembled: {assembled!r}\n"
            f"Done answer:      {done_answer!r}\n"
            f"Missing prefix: {done_answer[:len(done_answer) - len(assembled)]!r}\n"
            f"This indicates the first token is dropped before accumulation in run_stream()."
        )
