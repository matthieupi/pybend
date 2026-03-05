"""
Tests for SSR (Server-Side Rendering) modes.

Modes:
- "off"    — serve static HTML as-is
- "schema" — inject inline <script data-ntx-schema> tags
- "bundle" — replace ES module waterfall with single JS bundle (esbuild)
- "full"   — both schema tags and JS bundle
"""

import json
import os
import re
import shutil
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from n3tx.core.app import create_app, _resolve_ssr
from n3tx.core.storage.sqlite_storage import SQLiteStorage
from n3tx.core import config
from n3tx.core.authorize import configure as auth_configure
from n3tx.core.utils.registrar import registered_models
from n3tx.core.ssr.bundler import (
    parse_html_modules,
    build_bundle,
    discover_css_deps,
    _find_esbuild_bin,
    _merge_static_dirs,
    _rewrite_import_meta_urls,
    _inline_css_imports,
)
from n3tx.core.ssr.html import (
    build_schema_tags,
    inject_schemas,
    inject_bundle,
    inject_full,
    inject_css_preloads,
)


# ---------------------------------------------------------------------------
# Minimal model for SSR tests (avoids importing example models)
# ---------------------------------------------------------------------------
from pydantic import Field
from n3tx.core.models.proto_model import ProtoModel


class SSRProduct(ProtoModel):
    __tablename__ = 'ssr_products'
    __storable__ = True
    name: str = Field(min_length=1, max_length=200)
    price: float = Field(gt=0)


# ---------------------------------------------------------------------------
# Sample HTML with module structure (for bundle/full mode tests)
# ---------------------------------------------------------------------------

SAMPLE_HTML_WITH_MODULES = textwrap.dedent("""\
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <title>Test</title>
        <link rel="modulepreload" href="./config.js">
        <link rel="modulepreload" href="./core/Actor.js">
        <link rel="modulepreload" href="./core/TX.js">
        <script type="module" src="./utils/theme.js"></script>
    </head>
    <body>
        <div id="app"></div>
        <script type="module">
            import { config } from './config.js';
            import Actor from './core/Actor.js';
            console.log('bootstrap');
        </script>
    </body>
    </html>
""")

# Minimal JS files to create a resolvable module graph
SAMPLE_JS_FILES = {
    'config.js': "export const config = { E: {} };\n",
    'core/Actor.js': textwrap.dedent("""\
        import {config} from '../config.js';
        import TX from './TX.js';
        export default class Actor {
            constructor() {}
        }
    """),
    'core/TX.js': textwrap.dedent("""\
        import {config} from '../config.js';
        export default class TX {
            constructor() {}
        }
        export { TX };
    """),
    'utils/theme.js': textwrap.dedent("""\
        export function getTheme() { return 'dark'; }
        const saved = getTheme();
    """),
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def _isolated_models():
    """Save and restore the global registered_models dict around this module."""
    saved = dict(registered_models)
    registered_models.clear()
    yield
    registered_models.clear()
    registered_models.update(saved)


@pytest.fixture(scope="module")
def static_dir(tmp_path_factory):
    """Create a temporary static directory with a minimal index.html."""
    d = tmp_path_factory.mktemp("static")
    html = d / "index.html"
    html.write_text(
        '<!DOCTYPE html>\n'
        '<html lang="en">\n'
        '<head><title>Test</title></head>\n'
        '<body>\n'
        '    <div id="app"></div>\n'
        '</body>\n'
        '</html>\n'
    )
    return str(d)


@pytest.fixture(scope="module")
def static_dir_with_modules(tmp_path_factory):
    """Create a temporary static directory with index.html + JS module files."""
    d = tmp_path_factory.mktemp("static_mods")
    html = d / "index.html"
    html.write_text(SAMPLE_HTML_WITH_MODULES)

    for rel_path, content in SAMPLE_JS_FILES.items():
        fp = d / rel_path
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)

    return str(d)


@pytest.fixture(scope="module")
def db_path(tmp_path_factory):
    d = tmp_path_factory.mktemp("db")
    return str(d / "test_ssr.db")


@pytest.fixture(scope="module")
def ssr_app(_isolated_models, static_dir, db_path):
    """Create a N3TX app with SSR schema mode (backward compat: ssr=True)."""
    auth_configure(jwt_secret=config.JWT_SECRET, jwt_expiry_hours=1)
    return create_app(
        models=[SSRProduct],
        storage=SQLiteStorage(db_path),
        static_dir=static_dir,
        jwt_secret=config.JWT_SECRET,
        ssr=True,
    )


@pytest.fixture(scope="module")
def no_ssr_app(_isolated_models, static_dir, db_path):
    """Create a N3TX app with SSR disabled (default)."""
    auth_configure(jwt_secret=config.JWT_SECRET, jwt_expiry_hours=1)
    db_path_no_ssr = db_path.replace('.db', '_nossr.db')
    return create_app(
        models=[SSRProduct],
        storage=SQLiteStorage(db_path_no_ssr),
        static_dir=static_dir,
        jwt_secret=config.JWT_SECRET,
        ssr=False,
    )


@pytest.fixture(scope="module")
def ssr_client(ssr_app):
    with TestClient(ssr_app) as c:
        yield c


@pytest.fixture(scope="module")
def no_ssr_client(no_ssr_app):
    with TestClient(no_ssr_app) as c:
        yield c


def _make_app(static_dir, db_suffix, ssr):
    """Helper to create an app with a given SSR mode and unique DB."""
    auth_configure(jwt_secret=config.JWT_SECRET, jwt_expiry_hours=1)
    return create_app(
        models=[SSRProduct],
        storage=SQLiteStorage(f"/tmp/test_ssr_{db_suffix}.db"),
        static_dir=static_dir,
        jwt_secret=config.JWT_SECRET,
        ssr=ssr,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_schema_tags(html: str) -> list[tuple[str, dict]]:
    """Extract (model_name, schema_dict) pairs from SSR script tags."""
    pattern = r'<script type="application/json" data-ntx-schema="([^"]+)">(.+?)</script>'
    results = []
    for match in re.finditer(pattern, html, re.DOTALL):
        model_name = match.group(1)
        schema_json = json.loads(match.group(2))
        results.append((model_name, schema_json))
    return results


# ---------------------------------------------------------------------------
# Tests — SSR Disabled (mode="off")
# ---------------------------------------------------------------------------

class TestSSRDisabled:
    """When ssr=False (default), index.html is served as-is."""

    def test_serves_static_html(self, no_ssr_client):
        resp = no_ssr_client.get("/index.html")
        assert resp.status_code == 200
        assert 'data-ntx-schema' not in resp.text

    def test_html_is_unchanged(self, no_ssr_client):
        resp = no_ssr_client.get("/index.html")
        assert '<div id="app"></div>' in resp.text
        assert '</body>' in resp.text

    def test_root_serves_index(self, no_ssr_client):
        """GET / serves the same content as /index.html."""
        resp = no_ssr_client.get("/")
        assert resp.status_code == 200
        assert '<div id="app"></div>' in resp.text


# ---------------------------------------------------------------------------
# Tests — SSR Schema Mode (ssr=True / "schema")
# ---------------------------------------------------------------------------

class TestSSREnabled:
    """When ssr=True, index.html includes inline schema script tags."""

    def test_injects_schema_tags(self, ssr_client):
        resp = ssr_client.get("/index.html")
        assert resp.status_code == 200
        assert 'data-ntx-schema' in resp.text

    def test_schema_json_is_valid(self, ssr_client):
        resp = ssr_client.get("/index.html")
        tags = _extract_schema_tags(resp.text)
        assert len(tags) > 0
        for model_name, schema in tags:
            assert isinstance(schema, dict)
            assert '__name__' in schema
            assert 'properties' in schema

    def test_ssr_product_schema_present(self, ssr_client):
        resp = ssr_client.get("/index.html")
        tags = _extract_schema_tags(resp.text)
        model_names = [name for name, _ in tags]
        assert 'SSRProduct' in model_names

    def test_schema_matches_model_schema(self, ssr_client):
        resp = ssr_client.get("/index.html")
        tags = _extract_schema_tags(resp.text)
        tag_dict = {name: schema for name, schema in tags}
        expected = SSRProduct.schema()
        assert tag_dict['SSRProduct']['__name__'] == expected['__name__']
        assert tag_dict['SSRProduct']['properties'] == expected['properties']

    def test_preserves_original_html(self, ssr_client):
        resp = ssr_client.get("/index.html")
        assert '<div id="app"></div>' in resp.text
        assert '<title>Test</title>' in resp.text
        assert '</body>' in resp.text

    def test_ssr_comment_marker(self, ssr_client):
        resp = ssr_client.get("/index.html")
        assert '<!-- SSR: Pre-loaded schemas -->' in resp.text

    def test_response_is_cached(self, ssr_client):
        resp1 = ssr_client.get("/index.html")
        resp2 = ssr_client.get("/index.html")
        assert resp1.text == resp2.text

    def test_content_type_is_html(self, ssr_client):
        resp = ssr_client.get("/index.html")
        assert 'text/html' in resp.headers['content-type']

    def test_root_serves_ssr_content(self, ssr_client):
        """GET / serves the same SSR content as /index.html."""
        resp = ssr_client.get("/")
        assert resp.status_code == 200
        assert 'data-ntx-schema' in resp.text


# ---------------------------------------------------------------------------
# Tests — SSR Bundle Mode (mocked build_bundle)
# ---------------------------------------------------------------------------

MOCK_BUNDLE_JS = "(function(){ var x = 1; })();"


class TestSSRBundleMode:
    """When ssr="bundle", modulepreloads are stripped and a JS bundle is injected.

    build_bundle is mocked since esbuild may not be available in the test
    static directory.
    """

    @pytest.fixture(scope="class")
    def bundle_app(self, _isolated_models, static_dir_with_modules):
        auth_configure(jwt_secret=config.JWT_SECRET, jwt_expiry_hours=1)
        with patch('n3tx.core.ssr.bundler.build_bundle', return_value=MOCK_BUNDLE_JS):
            return create_app(
                models=[SSRProduct],
                storage=SQLiteStorage("/tmp/test_ssr_bundle.db"),
                static_dir=static_dir_with_modules,
                jwt_secret=config.JWT_SECRET,
                ssr="bundle",
            )

    @pytest.fixture(scope="class")
    def bundle_client(self, bundle_app):
        with TestClient(bundle_app) as c:
            yield c

    def test_bundle_strips_modulepreload(self, bundle_client):
        resp = bundle_client.get("/index.html")
        assert resp.status_code == 200
        assert 'rel="modulepreload"' not in resp.text

    def test_bundle_strips_module_scripts(self, bundle_client):
        resp = bundle_client.get("/index.html")
        assert 'type="module"' not in resp.text

    def test_bundle_injects_script_tag(self, bundle_client):
        resp = bundle_client.get("/index.html")
        assert '<!-- SSR: Bundled JS -->' in resp.text
        assert '<script>' in resp.text

    def test_bundle_no_schema_tags(self, bundle_client):
        resp = bundle_client.get("/index.html")
        assert 'data-ntx-schema' not in resp.text

    def test_bundle_contains_mock_content(self, bundle_client):
        resp = bundle_client.get("/index.html")
        assert MOCK_BUNDLE_JS in resp.text


# ---------------------------------------------------------------------------
# Tests — SSR Full Mode (mocked build_bundle)
# ---------------------------------------------------------------------------

class TestSSRFullMode:
    """When ssr="full", both schemas and bundle are injected."""

    @pytest.fixture(scope="class")
    def full_app(self, _isolated_models, static_dir_with_modules):
        auth_configure(jwt_secret=config.JWT_SECRET, jwt_expiry_hours=1)
        with patch('n3tx.core.ssr.bundler.build_bundle', return_value=MOCK_BUNDLE_JS):
            return create_app(
                models=[SSRProduct],
                storage=SQLiteStorage("/tmp/test_ssr_full.db"),
                static_dir=static_dir_with_modules,
                jwt_secret=config.JWT_SECRET,
                ssr="full",
            )

    @pytest.fixture(scope="class")
    def full_client(self, full_app):
        with TestClient(full_app) as c:
            yield c

    def test_full_has_both_schemas_and_bundle(self, full_client):
        resp = full_client.get("/index.html")
        assert resp.status_code == 200
        assert 'data-ntx-schema' in resp.text
        assert '<!-- SSR: Bundled JS -->' in resp.text

    def test_full_strips_modulepreload(self, full_client):
        resp = full_client.get("/index.html")
        assert 'rel="modulepreload"' not in resp.text

    def test_full_strips_module_scripts(self, full_client):
        resp = full_client.get("/index.html")
        assert 'type="module"' not in resp.text

    def test_full_bundle_content(self, full_client):
        resp = full_client.get("/index.html")
        assert MOCK_BUNDLE_JS in resp.text


# ---------------------------------------------------------------------------
# Tests — HTML transforms (unit tests)
# ---------------------------------------------------------------------------

class TestHTMLTransforms:
    """Unit tests for the html.py injection functions."""

    def test_inject_schemas(self):
        html = '<html><body></body></html>'
        result = inject_schemas(html, {'SSRProduct': SSRProduct})
        assert 'data-ntx-schema="SSRProduct"' in result
        assert '<!-- SSR: Pre-loaded schemas -->' in result

    def test_inject_bundle(self):
        html = textwrap.dedent("""\
            <html>
            <head>
                <link rel="modulepreload" href="./config.js">
                <script type="module" src="./theme.js"></script>
            </head>
            <body>
                <script type="module">console.log('hi');</script>
            </body>
            </html>
        """)
        result = inject_bundle(html, 'var x = 1;')
        assert 'modulepreload' not in result
        assert 'type="module"' not in result
        assert '<!-- SSR: Bundled JS -->' in result
        assert '<script>var x = 1;</script>' in result

    def test_inject_full(self):
        html = textwrap.dedent("""\
            <html>
            <head>
                <link rel="modulepreload" href="./config.js">
            </head>
            <body>
                <script type="module">console.log('hi');</script>
            </body>
            </html>
        """)
        result = inject_full(html, {'SSRProduct': SSRProduct}, 'var x = 1;')
        assert 'modulepreload' not in result
        assert 'type="module"' not in result
        assert 'data-ntx-schema' in result
        assert '<script>var x = 1;</script>' in result

    def test_build_schema_tags(self):
        tags = build_schema_tags({'SSRProduct': SSRProduct})
        assert 'data-ntx-schema="SSRProduct"' in tags
        # Verify it's valid JSON inside
        match = re.search(r'data-ntx-schema="SSRProduct">(.+?)</script>', tags)
        assert match
        data = json.loads(match.group(1))
        assert data['__name__'] == 'SSRProduct'

    def test_inject_css_preloads(self):
        html = '<html><head><title>Test</title></head><body></body></html>'
        result = inject_css_preloads(html, [
            './components/ntx-item.css',
            './components/ntx-list.css',
        ])
        assert '<!-- SSR: CSS preloads -->' in result
        assert '<link rel="preload" href="./components/ntx-item.css" as="style" crossorigin>' in result
        assert '<link rel="preload" href="./components/ntx-list.css" as="style" crossorigin>' in result
        # Should be before </head>
        assert result.index('preload') < result.index('</head>')

    def test_inject_css_preloads_empty(self):
        html = '<html><head></head><body></body></html>'
        result = inject_css_preloads(html, [])
        assert result == html  # no change

    def test_inject_bundle_strips_css_preloads(self):
        """Bundle mode strips CSS preload links since CSS is inlined in the bundle."""
        html = textwrap.dedent("""\
            <html>
            <head>
                <link rel="preload" href="./components/ntx-item.css" as="style" crossorigin>
                <link rel="preload" href="./components/ntx-list.css" as="style" crossorigin>
                <link rel="modulepreload" href="./config.js">
                <script type="module" src="./theme.js"></script>
            </head>
            <body>
                <script type="module">console.log('hi');</script>
            </body>
            </html>
        """)
        result = inject_bundle(html, 'var x = 1;')
        assert 'rel="preload"' not in result
        assert 'modulepreload' not in result


# ---------------------------------------------------------------------------
# Tests — Bundler helpers (unit tests)
# ---------------------------------------------------------------------------

class TestBundlerHelpers:
    """Unit tests for bundler.py helper functions."""

    def test_parse_html_modules_script_srcs(self):
        info = parse_html_modules(SAMPLE_HTML_WITH_MODULES)
        assert './utils/theme.js' in info['script_srcs']

    def test_parse_html_modules_inline_scripts(self):
        info = parse_html_modules(SAMPLE_HTML_WITH_MODULES)
        assert len(info['inline_scripts']) == 1
        assert 'bootstrap' in info['inline_scripts'][0]

    def test_parse_html_modules_empty(self):
        info = parse_html_modules('<html><body></body></html>')
        assert info['script_srcs'] == []
        assert info['inline_scripts'] == []

    def test_find_esbuild_bin_found(self):
        """Finds esbuild in the framework static dir."""
        framework_static = str(Path(__file__).resolve().parent.parent.parent.parent / 'static')
        result = _find_esbuild_bin([framework_static])
        if result:
            assert 'esbuild' in result
            assert os.path.isfile(result)

    def test_find_esbuild_bin_not_found(self, tmp_path):
        """Returns None when esbuild is not installed."""
        result = _find_esbuild_bin([str(tmp_path)])
        assert result is None

    def test_merge_static_dirs(self, static_dir_with_modules):
        """Merges static dirs into a temp directory."""
        work_dir = _merge_static_dirs([static_dir_with_modules])
        try:
            # Files should be copied
            assert (Path(work_dir) / 'config.js').is_file()
            assert (Path(work_dir) / 'core' / 'Actor.js').is_file()
            assert (Path(work_dir) / 'core' / 'TX.js').is_file()
            assert (Path(work_dir) / 'utils' / 'theme.js').is_file()
            # node_modules should NOT be copied
            assert not (Path(work_dir) / 'node_modules').exists()
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    def test_merge_static_dirs_overlay(self, tmp_path):
        """App dir files overlay framework dir files."""
        fw_dir = tmp_path / 'framework'
        fw_dir.mkdir()
        (fw_dir / 'config.js').write_text('// framework')
        (fw_dir / 'utils').mkdir()
        (fw_dir / 'utils' / 'helper.js').write_text('// fw helper')

        app_dir = tmp_path / 'app'
        app_dir.mkdir()
        (app_dir / 'config.js').write_text('// app override')
        (app_dir / 'custom.js').write_text('// app custom')

        # App dir first, framework dir last (per convention)
        work_dir = _merge_static_dirs([str(app_dir), str(fw_dir)])
        try:
            # App override wins
            assert (Path(work_dir) / 'config.js').read_text() == '// app override'
            # Framework-only file preserved
            assert (Path(work_dir) / 'utils' / 'helper.js').read_text() == '// fw helper'
            # App-only file present
            assert (Path(work_dir) / 'custom.js').read_text() == '// app custom'
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    def test_merge_skips_broken_symlinks(self, tmp_path):
        """Broken symlinks in static dirs are silently skipped."""
        d = tmp_path / 'static'
        d.mkdir()
        (d / 'real.js').write_text('ok')
        (d / 'broken.js').symlink_to('/nonexistent/path/file.js')
        # Also test broken symlinks inside a subdirectory
        (d / 'components').mkdir()
        (d / 'components' / 'real.js').write_text('component')
        (d / 'components' / 'broken.js').symlink_to('/nonexistent/other.js')

        work_dir = _merge_static_dirs([str(d)])
        try:
            assert (Path(work_dir) / 'real.js').is_file()
            assert not (Path(work_dir) / 'broken.js').exists()
            assert (Path(work_dir) / 'components' / 'real.js').is_file()
            assert not (Path(work_dir) / 'components' / 'broken.js').exists()
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    def test_merge_skips_broken_symlinks_in_overlay(self, tmp_path):
        """Broken symlinks are skipped during overlay merge too."""
        fw_dir = tmp_path / 'fw'
        fw_dir.mkdir()
        (fw_dir / 'components').mkdir()
        (fw_dir / 'components' / 'base.js').write_text('base')

        app_dir = tmp_path / 'app'
        app_dir.mkdir()
        (app_dir / 'components').mkdir()
        (app_dir / 'components' / 'custom.js').write_text('custom')
        (app_dir / 'components' / 'broken.js').symlink_to('/nonexistent/x.js')

        # Framework first (reversed), then app overlay — components/ dir exists
        # in both, triggering _copy_tree_merge
        work_dir = _merge_static_dirs([str(app_dir), str(fw_dir)])
        try:
            assert (Path(work_dir) / 'components' / 'base.js').is_file()
            assert (Path(work_dir) / 'components' / 'custom.js').is_file()
            assert not (Path(work_dir) / 'components' / 'broken.js').exists()
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    def test_merge_skips_hidden_and_node_modules(self, tmp_path):
        """Hidden files and node_modules are skipped during merge."""
        d = tmp_path / 'static'
        d.mkdir()
        (d / '.hidden').write_text('hidden')
        (d / 'node_modules').mkdir()
        (d / 'node_modules' / 'pkg.js').write_text('pkg')
        (d / 'visible.js').write_text('ok')

        work_dir = _merge_static_dirs([str(d)])
        try:
            assert not (Path(work_dir) / '.hidden').exists()
            assert not (Path(work_dir) / 'node_modules').exists()
            assert (Path(work_dir) / 'visible.js').is_file()
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    def test_rewrite_import_meta_urls(self, tmp_path):
        """import.meta.url is replaced with per-file URL expressions."""
        d = tmp_path / 'work'
        d.mkdir()
        (d / 'components').mkdir()
        (d / 'components' / 'ntx-list.js').write_text(
            "get styles() { return new URL('./ntx-list.css', import.meta.url).href; }"
        )
        (d / 'config.js').write_text(
            "export const config = {};"  # no import.meta.url — should be untouched
        )

        _rewrite_import_meta_urls(str(d))

        rewritten = (d / 'components' / 'ntx-list.js').read_text()
        assert 'import.meta.url' not in rewritten
        assert "window.location.origin+'/components/ntx-list.js'" in rewritten
        # config.js should be unchanged
        assert (d / 'config.js').read_text() == "export const config = {};"

    def test_rewrite_preserves_correct_css_resolution(self, tmp_path):
        """The rewritten URL allows new URL('./file.css', ...) to resolve correctly."""
        d = tmp_path / 'work'
        d.mkdir()
        (d / 'components').mkdir()
        (d / 'components' / 'widget.js').write_text(
            "const css = new URL('./widget.css', import.meta.url).href;"
        )

        _rewrite_import_meta_urls(str(d))

        rewritten = (d / 'components' / 'widget.js').read_text()
        # Simulate browser resolution: new URL('./widget.css', origin+'/components/widget.js')
        # Should resolve to origin+'/components/widget.css'
        assert "window.location.origin+'/components/widget.js'" in rewritten

    def test_inline_css_imports(self, tmp_path):
        """CSS referenced via new URL('./x.css', import.meta.url).href is inlined as data URI."""
        import base64
        d = tmp_path / 'work'
        d.mkdir()
        (d / 'components').mkdir()
        css_content = ".ntx-list { display: block; }"
        (d / 'components' / 'ntx-list.css').write_text(css_content)
        (d / 'components' / 'ntx-list.js').write_text(
            "get styles() { return new URL('./ntx-list.css', import.meta.url).href; }"
        )

        _inline_css_imports(str(d))

        rewritten = (d / 'components' / 'ntx-list.js').read_text()
        # Should be a data URI now
        assert 'import.meta.url' not in rewritten
        assert 'data:text/css;base64,' in rewritten
        # Decode and verify content
        b64 = base64.b64encode(css_content.encode()).decode('ascii')
        assert f'"data:text/css;base64,{b64}"' in rewritten

    def test_inline_css_missing_file_falls_back(self, tmp_path):
        """If the CSS file doesn't exist, the original pattern is preserved."""
        d = tmp_path / 'work'
        d.mkdir()
        (d / 'components').mkdir()
        original = "get styles() { return new URL('./missing.css', import.meta.url).href; }"
        (d / 'components' / 'widget.js').write_text(original)

        _inline_css_imports(str(d))

        # Unchanged — CSS file not found
        assert (d / 'components' / 'widget.js').read_text() == original

    def test_inline_css_const_pattern(self, tmp_path):
        """const TOPBAR_CSS = new URL('./ntx-topbar.css', import.meta.url).href;"""
        import base64
        d = tmp_path / 'work'
        d.mkdir()
        css_content = ".topbar { height: 60px; }"
        (d / 'ntx-topbar.css').write_text(css_content)
        (d / 'ntx-topbar.js').write_text(
            "const TOPBAR_CSS = new URL('./ntx-topbar.css', import.meta.url).href;"
        )

        _inline_css_imports(str(d))

        rewritten = (d / 'ntx-topbar.js').read_text()
        b64 = base64.b64encode(css_content.encode()).decode('ascii')
        assert f'const TOPBAR_CSS = "data:text/css;base64,{b64}";' in rewritten

    def test_discover_css_deps(self, tmp_path):
        """discover_css_deps finds CSS files referenced by JS components."""
        d = tmp_path / 'static'
        d.mkdir()
        (d / 'components').mkdir()
        (d / 'components' / 'ntx-list.js').write_text(
            "get styles() { return new URL('./ntx-list.css', import.meta.url).href; }"
        )
        (d / 'components' / 'ntx-list.css').write_text('.ntx-list {}')
        (d / 'components' / 'ntx-item.js').write_text(
            "get styles() { return new URL('./ntx-item.css', import.meta.url).href; }"
        )
        (d / 'components' / 'ntx-item.css').write_text('.ntx-item {}')
        (d / 'config.js').write_text("export const config = {};")  # no CSS dep

        deps = discover_css_deps([str(d)])
        assert deps == ['./components/ntx-item.css', './components/ntx-list.css']

    def test_discover_css_deps_missing_css(self, tmp_path):
        """CSS files that don't exist are not included."""
        d = tmp_path / 'static'
        d.mkdir()
        (d / 'widget.js').write_text(
            "get styles() { return new URL('./missing.css', import.meta.url).href; }"
        )

        deps = discover_css_deps([str(d)])
        assert deps == []

    def test_discover_css_deps_multiple_dirs(self, tmp_path):
        """CSS deps from multiple static dirs are combined."""
        fw = tmp_path / 'fw'
        fw.mkdir()
        (fw / 'components').mkdir()
        (fw / 'components' / 'ntx-list.js').write_text(
            "get styles() { return new URL('./ntx-list.css', import.meta.url).href; }"
        )
        (fw / 'components' / 'ntx-list.css').write_text('.ntx-list {}')

        app = tmp_path / 'app'
        app.mkdir()
        (app / 'components').mkdir()
        (app / 'components' / 'ntx-user.js').write_text(
            "get styles() { return new URL('./ntx-user.css', import.meta.url).href; }"
        )
        (app / 'components' / 'ntx-user.css').write_text('.ntx-user {}')

        deps = discover_css_deps([str(app), str(fw)])
        assert './components/ntx-list.css' in deps
        assert './components/ntx-user.css' in deps


# ---------------------------------------------------------------------------
# Tests — esbuild integration (requires esbuild binary)
# ---------------------------------------------------------------------------

class TestEsbuildIntegration:
    """Integration tests that run esbuild against sample JS files.

    These tests are skipped if esbuild is not available.
    """

    @pytest.fixture(scope="class")
    def esbuild_static_dir(self, tmp_path_factory):
        """Create a static dir with JS files + symlinked node_modules for esbuild."""
        d = tmp_path_factory.mktemp("esbuild_static")

        # Write sample JS files
        (d / "index.html").write_text(SAMPLE_HTML_WITH_MODULES)
        for rel_path, content in SAMPLE_JS_FILES.items():
            fp = d / rel_path
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(content)

        # Symlink the real node_modules so esbuild is available
        framework_nm = Path(__file__).resolve().parent.parent.parent.parent / 'static' / 'node_modules'
        if framework_nm.is_dir():
            (d / 'node_modules').symlink_to(framework_nm)

        return str(d)

    @pytest.fixture(scope="class")
    def has_esbuild(self, esbuild_static_dir):
        """Check if esbuild is available."""
        return _find_esbuild_bin([esbuild_static_dir]) is not None

    def test_build_bundle_produces_output(self, esbuild_static_dir, has_esbuild):
        if not has_esbuild:
            pytest.skip("esbuild not available")
        bundle = build_bundle(
            os.path.join(esbuild_static_dir, 'index.html'),
            [esbuild_static_dir],
        )
        assert isinstance(bundle, str)
        assert len(bundle) > 0

    def test_build_bundle_is_minified(self, esbuild_static_dir, has_esbuild):
        if not has_esbuild:
            pytest.skip("esbuild not available")
        bundle = build_bundle(
            os.path.join(esbuild_static_dir, 'index.html'),
            [esbuild_static_dir],
        )
        # Minified output shouldn't have multi-line formatting
        # (esbuild minifies to mostly single line for small bundles)
        lines = bundle.strip().split('\n')
        assert len(lines) <= 3  # typically 1-2 lines for minified output

    def test_build_bundle_is_iife(self, esbuild_static_dir, has_esbuild):
        if not has_esbuild:
            pytest.skip("esbuild not available")
        bundle = build_bundle(
            os.path.join(esbuild_static_dir, 'index.html'),
            [esbuild_static_dir],
        )
        # esbuild IIFE format starts with (()=>{...})();
        assert bundle.strip().startswith('(()=>{')
        assert bundle.strip().endswith('})();')

    def test_build_bundle_contains_module_content(self, esbuild_static_dir, has_esbuild):
        if not has_esbuild:
            pytest.skip("esbuild not available")
        bundle = build_bundle(
            os.path.join(esbuild_static_dir, 'index.html'),
            [esbuild_static_dir],
        )
        # Should contain content from our sample modules (esbuild may tree-shake
        # unused exports, but side-effect code like getTheme() call and
        # console.log('bootstrap') should remain)
        assert 'bootstrap' in bundle
        assert 'dark' in bundle  # getTheme return value

    def test_build_bundle_inlines_css(self, esbuild_static_dir, has_esbuild):
        """CSS referenced via import.meta.url is inlined as data URI in the bundle."""
        if not has_esbuild:
            pytest.skip("esbuild not available")
        import base64

        # Add a component with a CSS dependency to the esbuild static dir
        d = Path(esbuild_static_dir)
        (d / 'components').mkdir(exist_ok=True)
        css_content = ".test-comp { color: red; }"
        (d / 'components' / 'test-comp.css').write_text(css_content)
        (d / 'components' / 'test-comp.js').write_text(textwrap.dedent("""\
            const CSS = new URL('./test-comp.css', import.meta.url).href;
            console.log('test-comp loaded', CSS);
        """))

        # Add import to the inline script in index.html
        html = (d / 'index.html').read_text()
        html = html.replace(
            "console.log('bootstrap');",
            "import './components/test-comp.js';\n            console.log('bootstrap');",
        )
        (d / 'index.html').write_text(html)

        try:
            bundle = build_bundle(str(d / 'index.html'), [esbuild_static_dir])
            b64 = base64.b64encode(css_content.encode()).decode('ascii')
            assert f'data:text/css;base64,{b64}' in bundle
        finally:
            # Restore original index.html
            (d / 'index.html').write_text(SAMPLE_HTML_WITH_MODULES)
            # Clean up test files
            (d / 'components' / 'test-comp.css').unlink(missing_ok=True)
            (d / 'components' / 'test-comp.js').unlink(missing_ok=True)

    def test_build_bundle_no_esbuild_raises(self, tmp_path):
        """build_bundle raises RuntimeError when esbuild is not found."""
        html = tmp_path / "index.html"
        html.write_text(SAMPLE_HTML_WITH_MODULES)
        for rel_path, content in SAMPLE_JS_FILES.items():
            fp = tmp_path / rel_path
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(content)

        with pytest.raises(RuntimeError, match="esbuild not found"):
            build_bundle(str(html), [str(tmp_path)])


# ---------------------------------------------------------------------------
# Tests — Config Integration
# ---------------------------------------------------------------------------

class TestConfigIntegration:
    """Tests for config-driven SSR mode resolution."""

    def test_resolve_ssr_none_reads_config(self):
        """None defaults to config.SSR."""
        original = config.SSR
        try:
            config.SSR = 'bundle'
            assert _resolve_ssr(None) == 'bundle'
        finally:
            config.SSR = original

    def test_resolve_ssr_true_is_schema(self):
        assert _resolve_ssr(True) == 'schema'

    def test_resolve_ssr_false_is_off(self):
        assert _resolve_ssr(False) == 'off'

    def test_resolve_ssr_string(self):
        assert _resolve_ssr('full') == 'full'
        assert _resolve_ssr('bundle') == 'bundle'
        assert _resolve_ssr('schema') == 'schema'
        assert _resolve_ssr('off') == 'off'

    def test_resolve_ssr_invalid_string(self):
        with pytest.raises(ValueError, match="Invalid SSR mode"):
            _resolve_ssr('invalid')

    def test_resolve_ssr_case_insensitive(self):
        assert _resolve_ssr('FULL') == 'full'
        assert _resolve_ssr('Schema') == 'schema'

    def test_config_ssr_off(self, _isolated_models, static_dir):
        """config.SSR="off" serves static HTML."""
        app = _make_app(static_dir, 'cfg_off', ssr=False)
        with TestClient(app) as client:
            resp = client.get("/index.html")
            assert resp.status_code == 200
            assert 'data-ntx-schema' not in resp.text

    def test_config_ssr_schema(self, _isolated_models, static_dir):
        """config.SSR="schema" injects schemas."""
        app = _make_app(static_dir, 'cfg_schema', ssr="schema")
        with TestClient(app) as client:
            resp = client.get("/index.html")
            assert resp.status_code == 200
            assert 'data-ntx-schema' in resp.text

    def test_ssr_flag_overrides_config(self, _isolated_models, static_dir):
        """Explicit ssr= param overrides config.SSR."""
        original = config.SSR
        try:
            config.SSR = 'off'
            app = _make_app(static_dir, 'cfg_override', ssr="schema")
            with TestClient(app) as client:
                resp = client.get("/index.html")
                assert 'data-ntx-schema' in resp.text
        finally:
            config.SSR = original

    def test_backward_compat_bool_true(self, _isolated_models, static_dir):
        """ssr=True still works (maps to 'schema')."""
        app = _make_app(static_dir, 'compat_true', ssr=True)
        with TestClient(app) as client:
            resp = client.get("/index.html")
            assert 'data-ntx-schema' in resp.text

    def test_backward_compat_bool_false(self, _isolated_models, static_dir):
        """ssr=False still works (maps to 'off')."""
        app = _make_app(static_dir, 'compat_false', ssr=False)
        with TestClient(app) as client:
            resp = client.get("/index.html")
            assert 'data-ntx-schema' not in resp.text
