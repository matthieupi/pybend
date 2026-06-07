"""Pure helpers for agent policy and runtime code."""

from __future__ import annotations

import json

from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.ollama import OllamaProvider

from n3tx_core import config
from n3tx_core.models.proto_schema import run_pipeline


def _resolve_llm(llm):
    """Resolve an LLM string to a pydantic-ai model instance."""
    if not llm:
        raise ValueError(
            "No LLM provided. Pass an llm= argument "
            "(e.g., 'ollama:llama3.1', 'anthropic:claude-sonnet-4-5-20250929') "
            "or set it via __agent__['llm'] or config.AGENT_DEFAULTS['llm']."
        )
    if llm == 'test':
        from pydantic_ai.models.test import TestModel
        return TestModel(call_tools=[])
    if not isinstance(llm, str) or not llm.startswith('ollama:'):
        return llm

    model_name = llm.split(':', 1)[1]
    base_url = config.OLLAMA_BASE_URL.rstrip('/')
    if not base_url.endswith('/v1'):
        base_url += '/v1'
    return OpenAIChatModel(
        model_name,
        provider=OllamaProvider(base_url=base_url),
    )



def _build_instance_text(target) -> str:
    """Append current instance state to context."""
    try:
        data = target.model_dump()
    except Exception:
        return ''

    try:
        data_str = json.dumps(data, indent=2, default=str)
    except Exception:
        data_str = str(data)

    instance_id = getattr(target, 'id', '?')
    return f'\n\nCurrent instance (id={instance_id}):\n{data_str}'


def _agent_scope(agent_addr: str, cls=None) -> str:
    if isinstance(agent_addr, str) and agent_addr:
        return agent_addr.split('/', 1)[0]
    if cls is not None:
        return getattr(cls, '__tablename__', cls.__name__)
    return ''


def _agent_addr(target, cls) -> str:
    """Resolve a concrete string actor address for class or instance calls."""
    addr = getattr(target, '_addr', '')
    if isinstance(addr, str) and addr:
        return addr

    addr = getattr(target, '__addr__', '')
    if isinstance(addr, str) and addr:
        return addr

    return getattr(cls, '__tablename__', cls.__name__)


def _thread_matches_agent(thread_data: dict, agent_addr: str, cls=None) -> bool:
    thread_agent = (thread_data or {}).get('agent_addr', '')
    if not thread_agent:
        return True
    scope = _agent_scope(agent_addr, cls=cls)
    return thread_agent == agent_addr or thread_agent == scope


def _thread_user(user):
    """Normalize route-injected users for Thread CRUD authorization."""
    if user is None or isinstance(user, dict):
        return user
    user_id = getattr(user, 'id', None)
    if user_id is None:
        return user
    return {
        'user_id': user_id,
        'email': getattr(user, 'email', None),
        'role': getattr(user, 'role', 'user'),
    }
