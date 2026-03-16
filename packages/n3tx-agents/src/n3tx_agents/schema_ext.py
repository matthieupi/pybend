"""Schema pipeline extensions for agent capabilities.

1. Default pipeline — 'agent' stage: adds agent metadata to JSON Schema
   for models with __agent__ = True.

2. LLM pipeline — 'base' + 'clean' stages: produces a clean JSON Schema
   stripped of frontend-only keys, suitable for LLM consumption.

Output in default schema:
    {
        "agent": {
            "enabled": true,
            "config": {"self_tools": true, "neighbors": true},  # safe keys only
            "methods": ["agentic", "agentic_stream", "ctx", "tools"],
            "agentic_endpoint": "/agents/{id}/agentic"   # if AgentActor
        }
    }
"""

from n3tx_core.models.proto_schema import schema_extension, register_stage


# ── Default pipeline: agent metadata stage ────────────────────────

@schema_extension(after='methods')
def agent(cls, schema: dict) -> dict:
    """Inject agent metadata into schema for __agent__ = True models."""
    if not getattr(cls, '__agent__', False):
        return schema

    agent_flag = getattr(cls, '__agent__', False)
    agent_meta = {'enabled': True}

    # Expose safe config keys (no LLM credentials)
    if isinstance(agent_flag, dict):
        safe_keys = {'self_tools', 'neighbors', 'neighbor_depth'}
        agent_meta['config'] = {k: v for k, v in agent_flag.items() if k in safe_keys}

    # AgentActor instances have an /agentic endpoint — add the pattern
    from n3tx_agents.actor import AgentActor
    if issubclass(cls, AgentActor):
        tablename = schema.get('__tablename__', cls.__tablename__)
        agent_meta['agentic_endpoint'] = f'/{tablename}/{{id}}/agentic'

    agent_meta['methods'] = ['agentic', 'agentic_stream', 'ctx', 'tools']
    schema['agent'] = agent_meta
    return schema


# ── LLM pipeline: clean schema for LLM consumption ───────────────

# Keys that are frontend-only noise for the LLM
_LLM_STRIP_KEYS = {'ui', '$id', '$schema', '__owner__', '__parent__', 'additionalProperties'}
# Method keys that are routing/frontend concerns
_METHOD_STRIP_KEYS = {'route', 'methods', 'scope', 'ui', 'access'}


def _llm_base(cls):
    """Seed LLM pipeline from the cached default schema."""
    return cls.schema()  # returns a deep copy from cache — safe to mutate


def _llm_clean(cls, schema):
    """Strip frontend-only keys for LLM consumption.

    Removes UI hints, routing metadata, $defs, and hidden/protected
    properties. Returns a clean JSON Schema that any LLM understands.
    """
    def _strip(obj):
        if isinstance(obj, dict):
            return {k: _strip(v) for k, v in obj.items() if k not in _LLM_STRIP_KEYS}
        if isinstance(obj, list):
            return [_strip(item) for item in obj]
        return obj

    cleaned = _strip(schema)

    # Remove $defs — tool discovery provides related model schemas separately
    cleaned.pop('$defs', None)

    # Filter hidden/protected properties (check original schema's ui values)
    if 'properties' in cleaned:
        original_props = schema.get('properties', {})
        for name in list(cleaned['properties']):
            prop_ui = original_props.get(name, {}).get('ui', {})
            if prop_ui.get('display') is False or prop_ui.get('protected'):
                del cleaned['properties'][name]

    # Strip routing/frontend keys from methods, remove 'user' param
    if 'methods' in cleaned:
        for minfo in cleaned['methods'].values():
            for k in _METHOD_STRIP_KEYS:
                minfo.pop(k, None)
            params = minfo.get('parameters', {})
            params.pop('user', None)

    return cleaned


register_stage('base', _llm_base, pipeline='llm')
register_stage('clean', _llm_clean, pipeline='llm')
