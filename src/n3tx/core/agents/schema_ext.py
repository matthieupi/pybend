"""Schema pipeline extension for agent metadata.

Adds 'agent' section to JSON Schema for models with __agent__ = True.
Registered via @schema_extension so it plugs into the existing pipeline
without modifying proto_schema.py.

Output in schema:
    {
        "agent": {
            "enabled": true,
            "config": {"self_tools": true, "neighbors": true},  # safe keys only
            "methods": ["run", "run_stream", "ctx", "tools"],
            "run_endpoint": "/agents/{id}/run"   # if AgentActor
        }
    }
"""

from n3tx.core.models.proto_schema import schema_extension


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

    # AgentActor instances have a /run endpoint — add the pattern
    from n3tx.core.agents.actor import AgentActor
    if issubclass(cls, AgentActor):
        tablename = schema.get('__tablename__', cls.__tablename__)
        agent_meta['run_endpoint'] = f'/{tablename}/{{id}}/run'

    agent_meta['methods'] = ['run', 'run_stream', 'ctx', 'tools']
    schema['agent'] = agent_meta
    return schema
