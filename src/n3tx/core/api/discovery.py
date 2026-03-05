"""Discovery endpoints for agent and service discovery.

Provides:
    GET /_meta                  — Model registry, capabilities, health
    GET /.well-known/agent.json — A2A Agent Card (agent discovery)

Both endpoints are generated from the Matrix's actor registry — they
ask the Matrix for its registered actors and their capabilities.

Usage:
    from n3tx.core.api.discovery import create_discovery_routes

    app.include_router(create_discovery_routes(
        registered_models=registered_models,
        name='MyApp',
        version='1.0.0',
        base_url='http://localhost:5000',
    ))
"""

import logging
from typing import Optional

logger = logging.getLogger('n3tx.api.discovery')

from n3tx.core import config


def _build_meta(registered_models: dict, name: str, version: str,
                base_url: str, capabilities: Optional[dict] = None) -> dict:
    """Build the /_meta response from the model registry."""
    models = {}
    for tablename, model_cls in registered_models.items():
        model_info = {
            'name': model_cls.__name__,
            'tablename': tablename,
            'schema_url': f'{base_url}/{model_cls.__name__}',
            'collection_url': f'{base_url}/{tablename}',
        }

        if hasattr(model_cls, '__access__'):
            model_info['access'] = {
                action: rule.to_dict() if hasattr(rule, 'to_dict') else str(rule)
                for action, rule in model_cls.__access__.items()
            }

        if hasattr(model_cls, '__federated__') and model_cls.__federated__:
            model_info['federated'] = True

        methods = {}
        for attr_name in dir(model_cls):
            attr = getattr(model_cls, attr_name, None)
            if attr and hasattr(attr, '_route_path'):
                methods[attr_name] = {
                    'route': attr._route_path,
                    'methods': list(attr._route_methods),
                }
        if methods:
            model_info['methods'] = methods

        models[tablename] = model_info

    caps = {
        'crud': True,
        'schema': True,
        'authentication': True,
        'authorization': True,
    }
    if capabilities:
        caps.update(capabilities)

    return {
        'name': name,
        'version': version,
        'base_url': base_url,
        'models': models,
        'capabilities': caps,
        'debug': config.DEBUG,
    }


def _build_agent_card(registered_models: dict, name: str, version: str,
                      base_url: str, description: str = '') -> dict:
    """Build an A2A Agent Card from the model registry.

    Follows the Agent-to-Agent (A2A) protocol specification:
    https://google.github.io/A2A/
    """
    # Build skills from registered models
    skills = []
    for tablename, model_cls in registered_models.items():
        model_name = model_cls.__name__

        # CRUD skill per model
        skills.append({
            'id': f'{tablename}_crud',
            'name': f'{model_name} Management',
            'description': f'Create, read, update, and delete {model_name} records',
            'tags': [tablename, 'crud'],
            'examples': [
                f'List all {tablename}',
                f'Create a new {model_name}',
                f'Get {model_name} by ID',
            ],
        })

        # Custom method skills
        for attr_name in dir(model_cls):
            attr = getattr(model_cls, attr_name, None)
            if attr and hasattr(attr, '_route_path'):
                skills.append({
                    'id': f'{tablename}_{attr_name}',
                    'name': f'{model_name}.{attr_name}',
                    'description': f'Call {attr_name} on {model_name}',
                    'tags': [tablename, attr_name],
                })

    return {
        'name': name,
        'version': version,
        'description': description or f'{name} — a N3TX application',
        'url': base_url,
        'capabilities': {
            'streaming': False,
            'pushNotifications': False,
            'stateTransitionHistory': False,
        },
        'authentication': {
            'schemes': ['bearer'],
            'credentials': f'{base_url}/users/login',
        },
        'defaultInputModes': ['application/json'],
        'defaultOutputModes': ['application/json'],
        'skills': skills,
    }


def create_discovery_routes(
    registered_models: dict,
    name: str = 'N3TX',
    version: str = '0.8.0',
    base_url: str = '',
    description: str = '',
    capabilities: Optional[dict] = None,
):
    """Create FastAPI routes for service and agent discovery.

    Returns a FastAPI APIRouter with:
    - GET /_meta                  — model registry, capabilities, health
    - GET /.well-known/agent.json — A2A Agent Card for agent discovery
    """
    from fastapi import APIRouter
    from fastapi.responses import JSONResponse

    router = APIRouter(tags=['Discovery'])

    @router.get('/_meta')
    async def meta():
        """Service metadata — model registry, capabilities, health."""
        data = _build_meta(
            registered_models, name, version, base_url, capabilities,
        )
        return JSONResponse(data)

    @router.get('/.well-known/agent.json')
    async def agent_card():
        """A2A Agent Card — agent discovery endpoint."""
        data = _build_agent_card(
            registered_models, name, version, base_url, description,
        )
        return JSONResponse(data, headers={
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
        })

    return router
