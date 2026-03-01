"""NetworkMCP — MCP (Model Context Protocol) adapter.

Translates MCP JSON-RPC 2.0 messages to/from TX messages, enabling
AI agents (Claude Desktop, Cursor, GPT, etc.) to discover and call
PyBend model methods.

MCP operations:
    tools/list  →  iterate registered ActorModels, convert schemas to MCP tools
    tools/call  →  parse tool name, create TX, route through Matrix, return result

MCP wire format (JSON-RPC 2.0):
    Request:  {"jsonrpc": "2.0", "method": "tools/list", "id": 1}
    Response: {"jsonrpc": "2.0", "result": {"tools": [...]}, "id": 1}

    Request:  {"jsonrpc": "2.0", "method": "tools/call",
               "params": {"name": "products_list", "arguments": {}}, "id": 2}
    Response: {"jsonrpc": "2.0", "result": {"content": [...]}, "id": 2}

Usage:
    mcp = NetworkMCP(addr='mcp')
    matrix.register(mcp)

    # In FastAPI:
    app.include_router(create_mcp_routes(mcp))
"""

import json
import logging
from typing import Any

from pydantic import PrivateAttr

from pybend.core.actors.tx import TX
from pybend.core.api.network_adapter import NetworkAdapter

logger = logging.getLogger('pybend.network.mcp')


class NetworkMCP(NetworkAdapter, auto_register=False):
    """MCP JSON-RPC 2.0 adapter.

    Registered as a Matrix child at addr='mcp'. All communication with
    ActorModels goes through request() — schemas, CRUD, custom methods.
    """

    _tools_cache: list | None = PrivateAttr(default=None)

    def __init__(self, **kwargs):
        kwargs.setdefault('addr', 'mcp')
        super().__init__(**kwargs)

    def invalidate_cache(self):
        """Clear cached tools list. Call when models are registered/removed."""
        self._tools_cache = None

    # ── MCP protocol handlers ──

    async def handle_tools_list(self) -> list[dict]:
        """MCP tools/list — discover all available tools.

        Iterates Matrix children, requests schema from each model,
        converts to MCP tool definitions. Results are cached.
        """
        if self._tools_cache is not None:
            return self._tools_cache

        tools = []
        for addr, child in self.parent.children.items():
            # Only process model classes (types with schema capability)
            if not isinstance(child, type):
                continue
            if not hasattr(child, 'schema'):
                continue

            try:
                response = await self.request(
                    TX(name='schema', source=self.addr, target=addr),
                    timeout=10.0,
                )
                if response.is_error:
                    logger.warning("Schema request failed for %s: %s", addr, response.data)
                    continue
                tools.extend(self._schema_to_mcp_tools(response.data))
            except Exception as e:
                logger.warning("Failed to get schema from %s: %s", addr, e)
                continue

        self._tools_cache = tools
        return tools

    async def handle_tools_call(self, tool_name: str, arguments: dict) -> dict:
        """MCP tools/call — execute a tool.

        Tool names follow the pattern: {tablename}_{action}
        e.g. products_list, products_create, products_favorite

        Args:
            tool_name: The MCP tool name (e.g. 'products_create')
            arguments: The tool arguments dict

        Returns:
            MCP result dict with 'content' array.
        """
        model_addr, action = self._parse_tool_name(tool_name)

        tx = TX(
            name=action,
            source=self.addr,
            target=model_addr,
            data=arguments,
        )
        response = await self.request(tx, timeout=30.0)

        if response.is_error:
            return {
                'content': [{
                    'type': 'text',
                    'text': json.dumps(response.data),
                }],
                'isError': True,
            }

        return {
            'content': [{
                'type': 'text',
                'text': json.dumps(response.data, default=str),
            }],
        }

    async def handle_jsonrpc(self, request_body: dict) -> dict:
        """Handle a raw MCP JSON-RPC 2.0 request.

        Args:
            request_body: Parsed JSON-RPC request dict.

        Returns:
            JSON-RPC response dict.
        """
        method = request_body.get('method', '')
        params = request_body.get('params', {})
        req_id = request_body.get('id')

        try:
            if method == 'tools/list':
                tools = await self.handle_tools_list()
                result = {'tools': tools}

            elif method == 'tools/call':
                name = params.get('name', '')
                arguments = params.get('arguments', {})
                result = await self.handle_tools_call(name, arguments)

            elif method == 'initialize':
                result = {
                    'protocolVersion': '2024-11-05',
                    'capabilities': {'tools': {'listChanged': True}},
                    'serverInfo': {
                        'name': 'pybend',
                        'version': '0.8.0',
                    },
                }

            elif method == 'ping':
                result = {}

            else:
                return {
                    'jsonrpc': '2.0',
                    'error': {
                        'code': -32601,
                        'message': f'Method not found: {method}',
                    },
                    'id': req_id,
                }

        except Exception as e:
            logger.error("MCP error handling %s: %s", method, e)
            return {
                'jsonrpc': '2.0',
                'error': {
                    'code': -32603,
                    'message': str(e),
                },
                'id': req_id,
            }

        return {
            'jsonrpc': '2.0',
            'result': result,
            'id': req_id,
        }

    # ── Schema → MCP tool conversion ──

    def _schema_to_mcp_tools(self, schema: dict) -> list[dict]:
        """Convert a model schema to a list of MCP tool definitions.

        Each model contributes:
        - CRUD tools: {tablename}_list, _get, _create, _update, _delete
        - Custom method tools: {tablename}_{method_name}
        """
        tablename = schema.get('__tablename__', '')
        model_name = schema.get('__name__', tablename)
        if not tablename:
            return []

        tools = []

        # CRUD tools
        for action, description, input_schema in self._crud_tool_specs(schema, tablename, model_name):
            tools.append({
                'name': f'{tablename}_{action}',
                'description': description,
                'inputSchema': input_schema,
            })

        # Custom method tools from schema.methods
        for method_name, method_info in schema.get('methods', {}).items():
            params = method_info.get('parameters', {})
            # Filter out 'user' parameter (injected server-side)
            filtered_params = {
                k: v for k, v in params.items()
                if k != 'user'
            }
            tools.append({
                'name': f'{tablename}_{method_name}',
                'description': method_info.get('description', f'{model_name}.{method_name}()'),
                'inputSchema': {
                    'type': 'object',
                    'properties': filtered_params,
                },
            })

        return tools

    def _crud_tool_specs(self, schema: dict, tablename: str, model_name: str) -> list[tuple]:
        """Generate (action, description, inputSchema) for CRUD operations."""
        properties = schema.get('properties', {})
        required = schema.get('required', [])

        # Filter properties for create/update — exclude read-only fields
        writable = {}
        for name, prop in properties.items():
            if name == 'id':
                continue
            ui = prop.get('ui', {})
            if ui.get('protected') or ui.get('display') is False:
                continue
            writable[name] = {k: v for k, v in prop.items() if k not in ('ui', 'access')}

        writable_required = [r for r in required if r in writable]

        return [
            ('list', f'List {model_name} records', {
                'type': 'object',
                'properties': {
                    'limit': {'type': 'integer', 'description': 'Max records to return'},
                    'offset': {'type': 'integer', 'description': 'Records to skip'},
                },
            }),
            ('get', f'Get a {model_name} by ID', {
                'type': 'object',
                'properties': {'id': {'type': 'integer', 'description': f'{model_name} ID'}},
                'required': ['id'],
            }),
            ('create', f'Create a new {model_name}', {
                'type': 'object',
                'properties': writable,
                'required': writable_required,
            }),
            ('update', f'Update an existing {model_name}', {
                'type': 'object',
                'properties': {'id': {'type': 'integer', 'description': f'{model_name} ID'}, **writable},
                'required': ['id'],
            }),
            ('delete', f'Delete a {model_name} by ID', {
                'type': 'object',
                'properties': {'id': {'type': 'integer', 'description': f'{model_name} ID'}},
                'required': ['id'],
            }),
        ]

    def _parse_tool_name(self, tool_name: str) -> tuple[str, str]:
        """Parse MCP tool name into (model_addr, action).

        Tool names: {tablename}_{action}
        e.g. 'products_create' → ('products', 'create')
             'products_favorite' → ('products', 'favorite')
        """
        parts = tool_name.rsplit('_', 1)
        if len(parts) == 2:
            return parts[0], parts[1]
        return tool_name, 'list'


def create_mcp_routes(mcp_adapter: NetworkMCP):
    """Create FastAPI routes for MCP JSON-RPC endpoint.

    Returns a FastAPI APIRouter with:
    - POST /mcp — JSON-RPC 2.0 endpoint for MCP clients
    - GET /mcp/tools — convenience endpoint to list available tools
    """
    from fastapi import APIRouter, Request
    from fastapi.responses import JSONResponse

    router = APIRouter(tags=['MCP'])

    @router.post('/mcp')
    async def mcp_jsonrpc(request: Request):
        """MCP JSON-RPC 2.0 endpoint."""
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({
                'jsonrpc': '2.0',
                'error': {'code': -32700, 'message': 'Parse error'},
                'id': None,
            }, status_code=400)

        response = await mcp_adapter.handle_jsonrpc(body)
        return JSONResponse(response)

    @router.get('/mcp/tools')
    async def list_tools():
        """Convenience endpoint to list available MCP tools."""
        tools = await mcp_adapter.handle_tools_list()
        return {'tools': tools, 'count': len(tools)}

    return router
