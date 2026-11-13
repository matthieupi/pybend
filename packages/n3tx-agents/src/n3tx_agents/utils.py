"""Native agent provider selection, context and caller helpers.

Internal API: resolve configured models, format current model context, derive
actual actor routing and normalize trusted native caller identities.
No helper grants permissions or derives ownership from actor routing."""

from __future__ import annotations

import json

from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.ollama import OllamaProvider

from n3tx_core import config


def _resolve_llm(llm):
    """Resolve an LLM string to a pydantic-ai model instance."""
    # 0. Preserve native provider selection and the explicit test-model path.
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
    # 1. Adapt Ollama configuration without changing other provider inputs.
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
    # 0. Read native model data, retaining the existing presentation fallback.
    try:
        data = target.model_dump()
    except Exception:
        return ''
    # 1. Format the instance context without affecting persistence encoding.
    try:
        data_str = json.dumps(data, indent=2, default=str)
    except Exception:
        data_str = str(data)

    instance_id = getattr(target, 'id', '?')
    return f'\n\nCurrent instance (id={instance_id}):\n{data_str}'


def _agent_addr(target, cls) -> str:
    """Resolve a concrete string actor address for class or instance calls."""
    # 0. Prefer concrete actor routing and otherwise use the model table.
    addr = getattr(target, '_addr', '')
    if isinstance(addr, str) and addr:
        return addr

    addr = getattr(target, '__addr__', '')
    if isinstance(addr, str) and addr:
        return addr

    return getattr(cls, '__tablename__', cls.__name__)


def _caller_user(user):
    """Normalize route-injected users for native agent authorization."""
    # 0. Retain dictionaries or translate native user-model identity fields.
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


# Changelog (Python has no block-comment syntax):
# - 2026-11-11: Name caller normalization independently of retired storage.
# - 2026-10-31: Replace legacy address matching with exact owner/scope binding.
#   Normalize documentation and source layout.
#   Replace binding grants with identity/scope checks under native source ACLs.
#   Remove task-added Thread context checks; retain native caller handling.
