"""
ASGI profiling middleware using pyinstrument.

Wraps each API request with a pyinstrument Profiler and writes
per-request flame-graph text to `.traces/.profiling/perf_run_{label}.log`.

Enable by setting N3TX_PROFILING=1 and N3TX_PROFILING_LABEL=<label>.
"""
import os
import time
from pathlib import Path

from starlette.types import ASGIApp, Receive, Scope, Send

try:
    from pyinstrument import Profiler
except ImportError:
    Profiler = None

_default_dir = str(Path(__file__).resolve().parents[5] / '.traces' / '.profiling')
PROFILING_DIR = Path(os.environ.get('N3TX_PROFILING_DIR', _default_dir))
SKIP_EXTENSIONS = ('.js', '.css', '.html', '.png', '.ico', '.svg',
                   '.woff', '.woff2', '.ttf', '.map')


class ProfilingMiddleware:
    """ASGI middleware that profiles each request with pyinstrument."""

    def __init__(self, app: ASGIApp):
        self.app = app
        PROFILING_DIR.mkdir(parents=True, exist_ok=True)
        label = os.environ.get('N3TX_PROFILING_LABEL', 'run')
        self.log_path = PROFILING_DIR / f'perf_run_{label}.log'

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        path = scope.get('path', '')
        if any(path.endswith(ext) for ext in SKIP_EXTENSIONS):
            await self.app(scope, receive, send)
            return

        method = scope.get('method', '?')
        status_code = 0

        async def send_wrapper(message):
            nonlocal status_code
            if message['type'] == 'http.response.start':
                status_code = message.get('status', 0)
            await send(message)

        profiler = Profiler() if Profiler else None
        start = time.perf_counter()
        if profiler:
            profiler.start()
        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            if profiler:
                profiler.stop()
            duration_ms = (time.perf_counter() - start) * 1000

            flame = profiler.output_text(unicode=True, color=False) if profiler else '(pyinstrument not installed)'
            entry = (
                f"\n{'=' * 72}\n"
                f"{method} {path}  ->  {status_code}  ({duration_ms:.1f}ms)\n"
                f"{'=' * 72}\n"
                f"{flame}\n"
            )
            with open(self.log_path, 'a') as f:
                f.write(entry)
