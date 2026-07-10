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

    _validate_app_agent_config(app_agent)
    _validate_tool_targets(app_agent, registered_models)

    existing = _find_existing_agent(agent_cls, app_agent)
    if existing is None:
        agent = _create_agent(agent_cls, app_agent)
    else:
        agent = _update_agent(agent_cls, existing, app_agent)

    _reconcile_agent_tools(agent_cls, tool_cls, agent.id, app_agent.get('tools', []))
    return agent_cls.get(agent.id)


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


def _reconcile_agent_tools(agent_cls, tool_cls, agent_id: int, tool_specs: list[dict[str, Any]]) -> None:
    """Create/update AgentTool rows and store their ordered ids on AgentActor.tools."""
    ordered_tools = []
    for spec in tool_specs:
        target = spec['target']
        description = spec.get('description', '')
        existing = tool_cls.list(sql_filter=("target = ?", [target]))
        rows = existing.get('data', existing) if isinstance(existing, dict) else existing
        rows = rows or []

        if rows:
            tool = rows[0]
            if getattr(tool, 'description', '') != description:
                tool = tool_cls.update(tool.id, {'description': description})
        else:
            tool = tool_cls.create(tool_cls(target=target, description=description))
        ordered_tools.append(tool)

    agent_cls.update(agent_id, {'tools': ordered_tools})
