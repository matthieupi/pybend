"""Schema stages for native agent capability and LLM context projection.

API: agent publishes enabled status, safe discovery settings and Python method
names; the llm base/clean stages remove presentation and protected schema data.
Importing n3tx_agents registers these stages before model schema generation.
Capability metadata grants no execution access and advertises no stock HTTP
agent endpoint. Instance-data redaction remains the caller's responsibility."""

from n3tx_core.models.proto_schema import schema_extension, register_stage


# ── Default pipeline: agent metadata stage ────────────────────────

@schema_extension(after='methods')
def agent(cls, schema: dict) -> dict:
    """Inject agent metadata into schema for __agent__ = True models."""
    # 0. Publish only explicit capability and safe model-owned settings.
    if not getattr(cls, '__agent__', False):
        return schema

    agent_flag = getattr(cls, '__agent__', False)
    agent_meta = {'enabled': True}

    # Expose safe config keys (no LLM credentials)
    if isinstance(agent_flag, dict):
        safe_keys = {'self_tools', 'neighbors', 'neighbor_depth'}
        agent_meta['config'] = {
            key: value for key, value in agent_flag.items() if key in safe_keys
        }

    agent_meta['methods'] = ['agentic', 'agentic_stream', 'ctx', 'tools']
    schema['agent'] = agent_meta
    return schema


# ── LLM pipeline: clean schema for LLM consumption ───────────────

# Keys that are frontend-only noise for the LLM
_LLM_STRIP_KEYS = {'ui', '$id', '$schema', 'additionalProperties'}
# Method keys that are routing/frontend concerns
_METHOD_STRIP_KEYS = {'route', 'methods', 'scope', 'ui', 'access'}


def _llm_base(cls):
    """Seed LLM pipeline from the cached default schema."""
    return cls.schema()  # returns a deep copy from cache — safe to mutate


def _llm_clean(cls, schema):
    """Strip frontend-only keys for LLM consumption.

    Removes UI hints, routing metadata, $defs, and hidden/protected
    properties. It does not authorize access or redact instance values."""

    def _strip(obj):
        """Remove presentation-only keys recursively without changing values."""
        if isinstance(obj, dict):
            return {
                key: _strip(value) for key, value in obj.items()
                if key not in _LLM_STRIP_KEYS
            }
        if isinstance(obj, list):
            return [_strip(item) for item in obj]
        return obj

    # 0. Project a detached schema and remove separately discovered definitions.
    cleaned = _strip(schema)
    cleaned.pop('$defs', None)
    # 1. Remove properties explicitly marked hidden or protected by the model.
    if 'properties' in cleaned:
        original_props = schema.get('properties', {})
        for name in list(cleaned['properties']):
            prop_ui = original_props.get(name, {}).get('ui', {})
            if prop_ui.get('display') is False or prop_ui.get('protected'):
                del cleaned['properties'][name]

    # 2. Keep method semantics while excluding transport/caller presentation.
    if 'methods' in cleaned:
        for minfo in cleaned['methods'].values():
            for k in _METHOD_STRIP_KEYS:
                minfo.pop(k, None)
            params = minfo.get('parameters', {})
            params.pop('user', None)

    return cleaned


register_stage('base', _llm_base, pipeline='llm')
register_stage('clean', _llm_clean, pipeline='llm')


# Changelog (Python has no block-comment syntax).
# - 2026-11-11: Stop advertising retired stock HTTP agent execution endpoints;
#   document capability and context-projection boundaries.
