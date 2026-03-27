"""Debug routes for the TX Inspector.

Endpoints:
    GET /debug/           — Inspector HTML page
    GET /debug/topology   — Actor tree as JSON {nodes, edges}
    GET /debug/snapshot   — Current trace buffer
    GET /debug/stream     — SSE live TX events
    GET /debug/static/*   — Debug UI static files
"""

import asyncio
import json
import os
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, StreamingResponse
from starlette.staticfiles import StaticFiles

from n3tx_trace.tracer import TraceCollector

STATIC_DIR = Path(__file__).parent / 'static'
GRAPH_FLOW_DIR = Path(__file__).parent.parent.parent.parent / 'graph-flow' / 'src'


def create_debug_routes(collector: TraceCollector, matrix) -> APIRouter:
    """Create FastAPI router for debug endpoints."""
    router = APIRouter(prefix='/debug', tags=['debug'])

    @router.get('/', response_class=HTMLResponse)
    @router.get('', response_class=HTMLResponse)
    async def debug_page():
        html_path = STATIC_DIR / 'debug.html'
        return HTMLResponse(html_path.read_text())

    @router.get('/topology')
    async def topology():
        """Walk the Matrix actor tree and return nodes + edges."""
        nodes = []
        edges = []

        def _classify(actor) -> str:
            """Classify an actor for node type coloring."""
            cls_name = type(actor).__name__ if not isinstance(actor, type) else actor.__name__
            if 'Network' in cls_name or 'Adapter' in cls_name:
                return 'adapter'
            if 'Agent' in cls_name or getattr(actor, '__agent__', False):
                return 'agent'
            return 'model'

        def _walk(actor, parent_id=None):
            is_class = isinstance(actor, type)
            actor_id = actor.__addr__ if is_class else actor._addr
            label = actor_id
            actor_type = _classify(actor)

            nodes.append({
                'id': actor_id,
                'label': label,
                'type': actor_type,
                'class': type(actor).__name__ if not is_class else actor.__name__,
            })

            if parent_id:
                edges.append({'from': parent_id, 'to': actor_id})

            # Walk children
            children = actor.__children__ if is_class else actor._children
            for child_addr, child in children.items():
                _walk(child, actor_id)

        # Walk adapters
        if hasattr(matrix, '_adapters'):
            for adapter in matrix._adapters:
                adapter_id = getattr(adapter, '_addr', None) or getattr(adapter, 'addr', type(adapter).__name__)
                nodes.append({
                    'id': adapter_id,
                    'label': adapter_id,
                    'type': 'adapter',
                    'class': type(adapter).__name__,
                })
                edges.append({'from': 'matrix', 'to': adapter_id})

        # Walk matrix children
        for child_addr, child in matrix._children.items():
            _walk(child, 'matrix')

        # Add matrix itself as root
        nodes.insert(0, {
            'id': 'matrix',
            'label': 'matrix',
            'type': 'matrix',
            'class': 'Matrix',
        })

        return {'nodes': nodes, 'edges': edges}

    @router.get('/snapshot')
    async def snapshot():
        """Return current trace buffer."""
        return {'entries': collector.snapshot()}

    @router.get('/stream')
    async def stream():
        """SSE endpoint for live TX events."""
        client_id = f'client-{id(asyncio.current_task())}'
        queue = collector.subscribe(client_id)

        async def event_generator():
            try:
                while True:
                    entry = await queue.get()
                    if entry is None:
                        return
                    yield f"data: {json.dumps(entry)}\n\n"
            except asyncio.CancelledError:
                raise
            finally:
                collector.unsubscribe(client_id)

        return StreamingResponse(
            event_generator(),
            media_type='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no',
            },
        )

    return router


def mount_debug_static(app, prefix: str = '/debug/static'):
    """Mount the debug static files directory and graph-flow sources."""
    if GRAPH_FLOW_DIR.exists():
        app.mount(f'{prefix}/graph-flow', StaticFiles(directory=str(GRAPH_FLOW_DIR)), name='graph-flow-static')
    if STATIC_DIR.exists():
        app.mount(prefix, StaticFiles(directory=str(STATIC_DIR)), name='debug-static')
