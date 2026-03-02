"""
HTML transformation functions for SSR modes.

Three injection strategies:
- inject_schemas: add inline <script data-ntt-schema> tags (mode="schema")
- inject_bundle:  strip modulepreloads + module scripts, inject single bundle (mode="bundle")
- inject_full:    both schemas and bundle (mode="full")
"""

import json
import logging
import re

logger = logging.getLogger('pybend.ssr')


def build_schema_tags(models: dict) -> str:
    """Generate inline <script> tags containing JSON Schema for each model.

    Args:
        models: dict of {name: model_class} from registered_models.

    Returns:
        HTML string of <script type="application/json" data-ntt-schema="..."> tags.
    """
    tags = []
    for model_cls in models.values():
        try:
            schema = model_cls.schema()
            model_name = schema.get('__name__', model_cls.__name__)
            schema_json = json.dumps(schema, default=str)
            tags.append(
                f'    <script type="application/json" '
                f'data-ntt-schema="{model_name}">'
                f'{schema_json}</script>'
            )
        except Exception as e:
            logger.warning(f"SSR: Failed to generate schema for {model_cls.__name__}: {e}")
    return '\n'.join(tags)


def inject_css_preloads(html: str, css_paths: list) -> str:
    """Inject ``<link rel="preload" as="style">`` tags for component CSS.

    Args:
        html: original HTML string.
        css_paths: list of CSS paths relative to static root
            (e.g. ``['./components/ntt-list.css']``).

    Returns:
        HTML with preload links injected before ``</head>``.
    """
    if not css_paths:
        return html
    tags = []
    for path in css_paths:
        tags.append(f'    <link rel="preload" href="{path}" as="style" crossorigin>')
    preload_html = '\n'.join(tags)
    return html.replace(
        '</head>',
        f'    <!-- SSR: CSS preloads -->\n{preload_html}\n</head>'
    )


def inject_schemas(html: str, models: dict) -> str:
    """Inject schema <script> tags before </body>.

    Args:
        html: original HTML string.
        models: dict of registered models.

    Returns:
        HTML with schema tags injected.
    """
    tags_html = build_schema_tags(models)
    if not tags_html:
        return html
    return html.replace(
        '</body>',
        f'\n    <!-- SSR: Pre-loaded schemas -->\n{tags_html}\n</body>'
    )


def inject_bundle(html: str, bundle_js: str) -> str:
    """Strip modulepreload links and module scripts, inject a single bundle.

    Removes:
    - <link rel="modulepreload" ...>
    - <script type="module" src="...">
    - inline <script type="module">...</script>

    Injects:
    - <script> with the concatenated bundle before </body>

    Args:
        html: original HTML string.
        bundle_js: the bundled JavaScript string.

    Returns:
        Transformed HTML with bundle injected.
    """
    # Strip modulepreload links and CSS preload links (CSS is inlined in the bundle)
    html = re.sub(r'\s*<link\s+rel="modulepreload"[^>]*>\s*', '\n', html)
    html = re.sub(r'\s*<link\s+rel="preload"[^>]*as="style"[^>]*>\s*', '\n', html)

    # Strip <script type="module" src="..."> (external module scripts)
    html = re.sub(r'\s*<script\s+type="module"\s+src="[^"]*"\s*>\s*</script>\s*', '\n', html)

    # Strip inline <script type="module">...</script>
    html = re.sub(
        r'\s*<script\s+type="module"\s*>.*?</script>\s*',
        '\n',
        html,
        flags=re.DOTALL,
    )

    # Clean up excessive blank lines left by stripping
    html = re.sub(r'\n{3,}', '\n\n', html)

    # Inject the bundle before </body>
    html = html.replace(
        '</body>',
        f'    <!-- SSR: Bundled JS -->\n'
        f'    <script>{bundle_js}</script>\n</body>'
    )
    return html


def inject_full(html: str, models: dict, bundle_js: str) -> str:
    """Inject both schema tags and the JS bundle (mode="full").

    Schema tags are injected BEFORE the bundle so they are already in
    the DOM when the synchronous bundle script executes and calls
    ``#consumePreloadedSchema()``.

    Args:
        html: original HTML string.
        models: dict of registered models.
        bundle_js: the bundled JavaScript string.

    Returns:
        HTML with both schemas and bundle injected.
    """
    # Schemas first — must be in DOM before bundle executes
    html = inject_schemas(html, models)
    # Then bundle (strips modulepreload/module scripts, injects <script>)
    html = inject_bundle(html, bundle_js)
    return html
