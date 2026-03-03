"""Schema pipeline extension for agent metadata.

Adds 'agent' section to JSON Schema for models with __agent__ = True.
Registered via @schema_extension so it plugs into the existing pipeline
without modifying proto_schema.py.

Output in schema:
    {
        "agent": {
            "enabled": true,
            "run_endpoint": "/agents/{id}/run"   # if AgentActor
        }
    }
"""

from pybend.core.models.proto_schema import schema_extension


@schema_extension(after='methods')
def agent(cls, schema: dict) -> dict:
    """Inject agent metadata into schema for __agent__ = True models."""
    if not getattr(cls, '__agent__', False):
        return schema

    agent_meta = {'enabled': True}

    # AgentActor instances have a /run endpoint — add the pattern
    from pybend.core.agents.actor import AgentActor
    if issubclass(cls, AgentActor):
        tablename = schema.get('__tablename__', cls.__tablename__)
        agent_meta['run_endpoint'] = f'/{tablename}/{{id}}/run'

    schema['agent'] = agent_meta
    return schema
