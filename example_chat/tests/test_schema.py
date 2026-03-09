"""Tests for schema endpoints and HTML serving in the chat app."""
import pytest


class TestHTMLServing:
    def test_index_html_returns_200(self, client, seed_data):
        """GET / serves index.html (SSR or static) without errors.

        This catches SSR bundler failures (e.g. esbuild can't resolve
        imports) that only surface when the HTML is actually requested.
        """
        resp = client.get("/")
        assert resp.status_code == 200
        assert 'text/html' in resp.headers.get('content-type', '')
        body = resp.text
        assert 'ntx-chat-sidebar' in body
        assert 'ntx-chat-view' in body

    def test_index_html_imports_use_relative_paths(self, client, seed_data):
        """Module imports in index.html use ./ relative paths, not / absolute.

        Absolute paths break the SSR bundler (esbuild resolves from
        filesystem, not web server root).
        """
        resp = client.get("/")
        body = resp.text
        # If SSR bundled, module imports are replaced — check original only
        # if the inline script is still present
        if '<script type="module">' in body:
            # Extract inline module script
            import re
            scripts = re.findall(
                r'<script\s+type="module"\s*>(.*?)</script>',
                body, re.DOTALL,
            )
            for script in scripts:
                # No absolute imports like "from '/utils/..."
                assert "from '/" not in script, \
                    f"Found absolute import in inline script: {script[:200]}"
                assert "import '/" not in script, \
                    f"Found absolute import in inline script: {script[:200]}"


class TestSchemaEndpoints:
    def test_conversation_schema(self, client, seed_data):
        resp = client.get("/Conversation")
        assert resp.status_code == 200
        schema = resp.json()
        assert schema["__name__"] == "Conversation"
        assert schema["__tablename__"] == "conversations"
        props = schema["properties"]
        assert "name" in props
        assert "prompt" in props
        assert "llm" in props
        assert "messages" in props

    def test_conversation_has_agent_section(self, client, seed_data):
        resp = client.get("/Conversation")
        schema = resp.json()
        assert "agent" in schema
        assert schema["agent"]["enabled"] is True

    def test_conversation_has_chat_method(self, client, seed_data):
        """Chat method appears in schema with stream flag."""
        resp = client.get("/Conversation")
        schema = resp.json()
        methods = schema.get("methods", {})
        assert "chat" in methods, f"Expected 'chat' in methods, got: {list(methods.keys())}"
        chat_method = methods["chat"]
        assert chat_method.get("stream") is True

    def test_message_schema(self, client, seed_data):
        resp = client.get("/Message")
        assert resp.status_code == 200
        schema = resp.json()
        assert schema["__name__"] == "Message"
        props = schema["properties"]
        assert "kind" in props
        assert "parts" in props
        assert "content" in props
        assert "role" in props

    def test_user_schema(self, client, seed_data):
        resp = client.get("/User")
        assert resp.status_code == 200
        schema = resp.json()
        assert schema["__name__"] == "User"
