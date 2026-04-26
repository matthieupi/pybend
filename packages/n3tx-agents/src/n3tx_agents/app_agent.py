"""Framework bootstrap provisioning for a static app assistant."""

from __future__ import annotations

from typing import Any

from n3tx_agents.actor import AgentActor
from n3tx_agents.tool_model import AgentTool


def provision_app_agent(app_agent: dict[str, Any], registered_models: dict[str, Any]):
    """Create or update a framework-provisioned app agent idempotently."""
    agent_cls = registered_models.get(AgentActor.__tablename__)
    tool_cls = registered_models.get(AgentTool.__tablename__)
    if agent_cls is None:
        raise RuntimeError("app_agent provisioning requires registered AgentActor model")
    if tool_cls is None:
        raise RuntimeError("app_agent provisioning requires registered AgentTool model")

    join_cls = _resolve_agent_tool_join(agent_cls)
    if join_cls is None:
        raise RuntimeError(
            "app_agent provisioning requires the AgentActor -> AgentTool join model"
        )

    _validate_app_agent_config(app_agent)
    _validate_tool_targets(app_agent, registered_models)

    existing = _find_existing_agent(agent_cls, app_agent)
    if existing is None:
        agent = _create_agent(agent_cls, app_agent)
    else:
        agent = _update_agent(agent_cls, existing, app_agent)

    _reconcile_tool_links(join_cls, agent.id, app_agent.get('tools', []))
    return agent


def _resolve_agent_tool_join(agent_cls):
    fk_models = getattr(agent_cls, '__fk_models__', {}) or {}
    join_cls = fk_models.get('tools')
    if join_cls is not None:
        return join_cls

    for value in fk_models.values():
        if getattr(value, '__owner__', None) is agent_cls and AgentTool in value.__mro__[1:]:
            return value
    return None


def _validate_app_agent_config(app_agent: dict[str, Any]):
    if not isinstance(app_agent, dict):
        raise RuntimeError("app_agent must be a dict")
    if not app_agent.get('key'):
        raise RuntimeError("app_agent requires a non-empty 'key'")
    if not app_agent.get('name'):
        raise RuntimeError("app_agent requires a non-empty 'name'")
    if 'tools' in app_agent and not isinstance(app_agent.get('tools'), list):
        raise RuntimeError("app_agent 'tools' must be a list")


def _validate_tool_targets(app_agent: dict[str, Any], registered_models: dict[str, Any]):
    missing = []
    for spec in app_agent.get('tools', []):
        target = spec.get('target') if isinstance(spec, dict) else None
        if not target:
            raise RuntimeError("app_agent tool specs require non-empty 'target'")
        if target not in registered_models:
            missing.append(target)
    if missing:
        raise RuntimeError(
            f"app_agent references unknown tool targets: {', '.join(sorted(set(missing)))}"
        )


def _find_existing_agent(agent_cls, app_agent: dict[str, Any]):
    system_key = app_agent.get('key', '')
    if system_key:
        matches = agent_cls.list(sql_filter=("system_key = ?", [system_key]))
        rows = matches.get('data', matches) if isinstance(matches, dict) else matches
        if rows:
            return rows[0]

    name = app_agent.get('name', '')
    if name:
        matches = agent_cls.list(sql_filter=("name = ?", [name]))
        rows = matches.get('data', matches) if isinstance(matches, dict) else matches
        if rows:
            return rows[0]
    return None


def _agent_payload(app_agent: dict[str, Any]) -> dict[str, Any]:
    return {
        'system_key': app_agent.get('key', ''),
        'name': app_agent.get('name', ''),
        'prompt': app_agent.get('prompt', ''),
        'llm': app_agent.get('llm', ''),
        'constraints': dict(app_agent.get('constraints', {}) or {}),
    }


def _create_agent(agent_cls, app_agent: dict[str, Any]):
    return agent_cls.create(agent_cls(**_agent_payload(app_agent)))


def _update_agent(agent_cls, existing, app_agent: dict[str, Any]):
    return agent_cls.update(existing.id, _agent_payload(app_agent))


def _reconcile_tool_links(join_cls, agent_id: int, tool_specs: list[dict[str, Any]]):
    fk_field = f"{getattr(join_cls, '__owner__').__name__.lower()}_id"
    existing = join_cls.list(sql_filter=(f"{fk_field} = ?", [agent_id]))
    rows = existing.get('data', existing) if isinstance(existing, dict) else existing
    rows = rows or []

    desired = {
        spec['target']: spec.get('description', '')
        for spec in tool_specs
    }
    current = {row.target: row for row in rows}

    for target, description in desired.items():
        row = current.get(target)
        if row is None:
            join_cls.create(join_cls(**{fk_field: agent_id, 'target': target, 'description': description}))
            continue
        if row.description != description:
            join_cls.update(row.id, {'description': description})

    for target, row in current.items():
        if target not in desired:
            join_cls.delete(row.id)
