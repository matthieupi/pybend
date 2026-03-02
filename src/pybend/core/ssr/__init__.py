"""
SSR (Server-Side Rendering) module for PyBend.

Provides four modes controlled by ``config.SSR``:
- ``"off"``    — serve static HTML as-is (default)
- ``"schema"`` — inject inline ``<script data-ntt-schema>`` tags
- ``"bundle"`` — replace ES module waterfall with a single inlined JS bundle
- ``"full"``   — both schema injection and JS bundling

Bundling uses esbuild (installed in ``static/node_modules/``).
"""

from .html import build_schema_tags, inject_schemas, inject_bundle, inject_full, inject_css_preloads
from .bundler import build_bundle, discover_css_deps

__all__ = [
    'build_schema_tags',
    'inject_schemas',
    'inject_css_preloads',
    'inject_bundle',
    'inject_full',
    'build_bundle',
    'discover_css_deps',
]
