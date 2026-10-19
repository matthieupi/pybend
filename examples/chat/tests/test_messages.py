"""Tests for Message model and pydantic-ai round-trip conversion."""
import json
import pytest
from examples.chat.models import Message


class TestMessageModel:
    def test_from_model_request(self):
        """Convert a pydantic-ai ModelRequest to our Message."""
        from pydantic_ai.messages import ModelRequest, UserPromptPart
        from datetime import datetime, timezone

        req = ModelRequest(
            parts=[UserPromptPart(content='Hello', timestamp=datetime.now(timezone.utc))],
        )
        msg = Message.from_model_message(req, user_owner=1)
        assert msg.kind == 'request'
        assert msg.content == 'Hello'
        assert msg.role == 'user'
        assert len(msg.parts) == 1
        assert msg.parts[0]['part_kind'] == 'user-prompt'

    def test_from_model_response(self):
        """Convert a pydantic-ai ModelResponse to our Message."""
        from pydantic_ai.messages import ModelResponse, TextPart, RequestUsage
        from datetime import datetime, timezone

        resp = ModelResponse(
            parts=[TextPart(content='Hi there!')],
            usage=RequestUsage(input_tokens=10, output_tokens=5, details={}),
            timestamp=datetime.now(timezone.utc),
            model_name='test-model',
        )
        msg = Message.from_model_message(resp, user_owner=1)
        assert msg.kind == 'response'
        assert msg.content == 'Hi there!'
        assert msg.role == 'assistant'
        assert msg.model_name == 'test-model'
        assert msg.usage['input_tokens'] == 10
        assert msg.usage['output_tokens'] == 5

    def test_round_trip_request(self):
        """Message -> pydantic-ai -> Message preserves content."""
        from pydantic_ai.messages import ModelRequest, UserPromptPart
        from datetime import datetime, timezone

        original = ModelRequest(
            parts=[UserPromptPart(content='Test question', timestamp=datetime.now(timezone.utc))],
            instructions='Be helpful',
        )
        msg = Message.from_model_message(original)
        restored = msg.to_model_message()

        assert restored.kind == 'request'
        assert len(restored.parts) == 1
        assert restored.parts[0].content == 'Test question'
        assert restored.instructions == 'Be helpful'

    def test_round_trip_response(self):
        """Response round-trip preserves text and usage."""
        from pydantic_ai.messages import ModelResponse, TextPart, RequestUsage
        from datetime import datetime, timezone

        original = ModelResponse(
            parts=[TextPart(content='The answer is 42')],
            usage=RequestUsage(input_tokens=15, output_tokens=8, details={}),
            timestamp=datetime.now(timezone.utc),
            model_name='test-model',
        )
        msg = Message.from_model_message(original)
        restored = msg.to_model_message()

        assert restored.kind == 'response'
        assert restored.parts[0].content == 'The answer is 42'
        assert restored.model_name == 'test-model'

    def test_tool_call_preserved(self):
        """Tool call parts survive the round-trip."""
        from pydantic_ai.messages import ModelResponse, ToolCallPart, RequestUsage
        from datetime import datetime, timezone

        original = ModelResponse(
            parts=[ToolCallPart(tool_name='search', args={'q': 'test'}, tool_call_id='tc_123')],
            usage=RequestUsage(input_tokens=5, output_tokens=3, details={}),
            timestamp=datetime.now(timezone.utc),
        )
        msg = Message.from_model_message(original)
        assert msg.content == '[tool: search]'
        assert msg.role == 'assistant'

        restored = msg.to_model_message()
        assert restored.parts[0].tool_name == 'search'
        assert restored.parts[0].tool_call_id == 'tc_123'

    def test_tool_return_preserved(self):
        """Tool return parts survive the round-trip."""
        from pydantic_ai.messages import ModelRequest, ToolReturnPart
        from datetime import datetime, timezone

        original = ModelRequest(
            parts=[ToolReturnPart(
                tool_name='search',
                content='Found 3 results',
                tool_call_id='tc_123',
                timestamp=datetime.now(timezone.utc),
            )],
        )
        msg = Message.from_model_message(original)
        assert msg.role == 'tool'
        assert msg.content == 'Found 3 results'

        restored = msg.to_model_message()
        assert restored.parts[0].tool_name == 'search'
        assert restored.parts[0].content == 'Found 3 results'

    def test_extract_display_thinking(self):
        """Thinking parts get extracted for display."""
        from pydantic_ai.messages import ModelResponse, ThinkingPart, RequestUsage
        from datetime import datetime, timezone

        resp = ModelResponse(
            parts=[ThinkingPart(content='Let me think...')],
            usage=RequestUsage(input_tokens=5, output_tokens=3, details={}),
            timestamp=datetime.now(timezone.utc),
        )
        msg = Message.from_model_message(resp)
        assert msg.content == 'Let me think...'
        assert msg.role == 'assistant'

    def test_json_serialization(self):
        """Parts and usage serialize to JSON for SQLite storage."""
        msg = Message(
            kind='response',
            parts=[{'part_kind': 'text', 'content': 'hello'}],
            content='hello',
            role='assistant',
            usage={'input_tokens': 5, 'output_tokens': 3},
        )
        d = msg._storage_dict(exclude_unset=False)
        assert isinstance(d['parts'], str)
        assert isinstance(d['usage'], str)

        # Verify round-trip through JSON
        parts = json.loads(d['parts'])
        assert parts[0]['content'] == 'hello'
