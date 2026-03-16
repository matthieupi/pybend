"""
JavaScript bundler for N3TX SSR.

Replaces the ES module import waterfall with a single self-contained
``<script>`` using esbuild (already installed in ``static/node_modules/``).

The bundler:
1. Parses index.html for ``<script type="module" src="...">`` and inline
   ``<script type="module">`` blocks
2. Merges framework + app static dirs into a temp directory so relative
   imports resolve
3. Shells out to esbuild with ``--bundle --format=iife``
4. Returns the bundled JS as a string
"""

import base64
import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger('n3tx.ssr.bundler')

# ---------------------------------------------------------------------------
# HTML parsing — extract entry points from index.html
# ---------------------------------------------------------------------------

_RE_MODULE_SCRIPT_SRC = re.compile(
    r'<script\s+type="module"\s+src="([^"]+)"\s*>\s*</script>', re.IGNORECASE
)
_RE_INLINE_MODULE = re.compile(
    r'<script\s+type="module"\s*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)


def parse_html_modules(html_text):
    """Extract module entry points from index.html.

    Returns:
        dict with keys:
        - ``script_srcs``: list of ``<script type="module" src="...">`` paths
        - ``inline_scripts``: list of inline ``<script type="module">`` bodies
    """
    return {
        'script_srcs': _RE_MODULE_SCRIPT_SRC.findall(html_text),
        'inline_scripts': _RE_INLINE_MODULE.findall(html_text),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_bundle(html_path, static_dirs):
    """Build a JS bundle from index.html's module graph using esbuild.

    Args:
        html_path: Path to index.html (str or Path).
        static_dirs: List of static directories to search (app dirs first,
            framework dir last).  Files are merged into a temp directory
            (framework first, then app overlays) so that relative imports
            resolve correctly.

    Returns:
        The bundled JavaScript as a string.
    """
    html_path = Path(html_path)
    with open(html_path) as f:
        html = f.read()

    info = parse_html_modules(html)

    # Find esbuild binary
    esbuild_bin = _find_esbuild_bin(static_dirs)
    if not esbuild_bin:
        raise RuntimeError(
            "esbuild not found in any static directory's node_modules/.bin/. "
            "Install it with: cd static && npm install esbuild"
        )

    # Create a merged temp directory so all relative imports resolve
    work_dir = _merge_static_dirs(static_dirs)

    try:
        # Inline CSS files referenced via new URL('./x.css', import.meta.url).href
        # as base64 data URIs.  Must run BEFORE _rewrite_import_meta_urls so the
        # pattern still contains the literal `import.meta.url` text.
        _inline_css_imports(work_dir)

        # Replace remaining import.meta.url per-file so non-CSS URL resolution
        # works.  In IIFE mode import.meta is unavailable, so we rewrite each
        # occurrence to (window.location.origin + '/path/to/file.js').
        _rewrite_import_meta_urls(work_dir)

        # Compose virtual entry from the script srcs + inline scripts
        entry_lines = []
        for src in info['script_srcs']:
            entry_lines.append(f"import '{src}';")
        for inline in info['inline_scripts']:
            entry_lines.append(inline)

        entry_path = os.path.join(work_dir, '_ssr_entry.js')
        with open(entry_path, 'w') as f:
            f.write('\n'.join(entry_lines))

        out_path = os.path.join(work_dir, '_ssr_bundle.js')

        result = subprocess.run(
            [
                esbuild_bin,
                '--bundle',
                '--format=iife',
                '--minify',
                '--keep-names',
                f'--outfile={out_path}',
                '--log-level=warning',
                entry_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            raise RuntimeError(f"esbuild failed:\n{result.stderr}")

        with open(out_path) as f:
            bundle = f.read()

        logger.info(f"Bundler: esbuild bundle — {len(bundle)} bytes")
        return bundle

    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _find_esbuild_bin(static_dirs):
    """Locate the esbuild binary in node_modules or on PATH."""
    for sd in static_dirs:
        candidate = Path(sd) / 'node_modules' / '.bin' / 'esbuild'
        if candidate.is_file():
            return str(candidate)
    # Fallback: check system PATH (e.g. globally installed esbuild)
    system_esbuild = shutil.which('esbuild')
    if system_esbuild:
        return system_esbuild
    return None


def _rewrite_import_meta_urls(work_dir):
    """Replace ``import.meta.url`` with a per-file URL expression.

    In ES modules, ``import.meta.url`` gives each module its own URL
    (e.g. ``http://host/components/ntx-list.js``).  In IIFE mode this
    is unavailable, so we rewrite each occurrence to an expression that
    reconstructs the correct URL at runtime::

        import.meta.url  →  (window.location.origin+'/components/ntx-list.js')

    This keeps ``new URL('./ntx-list.css', import.meta.url)`` resolving
    to the right path.  Only ``.js`` files in the work directory are
    touched; the original source files are never modified.
    """
    work_path = Path(work_dir)
    for js_file in work_path.rglob('*.js'):
        if js_file.name.startswith('_ssr_'):
            continue
        content = js_file.read_text()
        if 'import.meta.url' not in content:
            continue
        rel = js_file.relative_to(work_path)
        url_path = '/' + '/'.join(rel.parts)
        content = content.replace(
            'import.meta.url',
            f"(window.location.origin+'{url_path}')",
        )
        js_file.write_text(content)


def _merge_static_dirs(static_dirs):
    """Create a temp directory with files from all static dirs merged.

    Framework dir is copied first, then app dirs overlay on top so that
    app-specific files (components, overrides) take precedence.

    Dereferences symlinks so esbuild resolves relative imports against
    the temp directory.  Broken symlinks are silently skipped.
    """
    work_dir = tempfile.mkdtemp(prefix='ntx_ssr_')

    # Copy in order: framework (last in list) first, app dirs overlay
    for sd in reversed(static_dirs):
        sd_path = Path(sd)
        if not sd_path.is_dir():
            continue
        for item in sd_path.iterdir():
            # Skip node_modules, tests, and hidden files
            if item.name in ('node_modules', 'tests', 'test-results', '.git'):
                continue
            if item.name.startswith('.'):
                continue
            # Skip broken symlinks
            if item.is_symlink() and not item.exists():
                continue
            dest = Path(work_dir) / item.name
            if item.is_dir():
                if dest.is_dir():
                    _copy_tree_merge(item, dest)
                else:
                    shutil.copytree(
                        item, dest, symlinks=False,
                        ignore_dangling_symlinks=True,
                    )
            else:
                shutil.copy2(item, dest)

    return work_dir


def _copy_tree_merge(src_dir, dest_dir):
    """Recursively copy files from src_dir into dest_dir, merging contents."""
    for item in Path(src_dir).iterdir():
        # Skip broken symlinks
        if item.is_symlink() and not item.exists():
            continue
        dest = dest_dir / item.name
        if item.is_dir():
            if dest.is_dir():
                _copy_tree_merge(item, dest)
            else:
                shutil.copytree(
                    item, dest, symlinks=False,
                    ignore_dangling_symlinks=True,
                )
        else:
            shutil.copy2(item, dest)


# Regex: new URL('./file.css', import.meta.url).href
_RE_CSS_IMPORT_META = re.compile(
    r"""new\s+URL\(\s*['"](\./[^'"]+\.css)['"]\s*,\s*import\.meta\.url\s*\)\.href"""
)


def _inline_css_imports(work_dir):
    """Replace ``new URL('./x.css', import.meta.url).href`` with base64 data URIs.

    Components load Shadow DOM stylesheets via this pattern.  In the IIFE
    bundle we can inline the CSS content directly so the browser needs zero
    extra network requests for component styles.

    Must be called **before** ``_rewrite_import_meta_urls`` because it
    relies on the literal ``import.meta.url`` text to identify patterns.
    """
    work_path = Path(work_dir)
    for js_file in work_path.rglob('*.js'):
        if js_file.name.startswith('_ssr_'):
            continue
        content = js_file.read_text()
        if 'import.meta.url' not in content or '.css' not in content:
            continue

        def _replace_css(match, _js_file=js_file):
            css_rel = match.group(1)  # e.g. './ntx-list.css'
            css_file = (_js_file.parent / css_rel).resolve()
            if css_file.is_file():
                css_bytes = css_file.read_bytes()
                b64 = base64.b64encode(css_bytes).decode('ascii')
                return f'"data:text/css;base64,{b64}"'
            # CSS file not found — leave original for import.meta.url rewrite
            return match.group(0)

        new_content = _RE_CSS_IMPORT_META.sub(_replace_css, content)
        if new_content != content:
            js_file.write_text(new_content)
            logger.debug(f"Bundler: inlined CSS in {js_file.name}")


def discover_css_deps(static_dirs):
    """Scan JS files in static directories for CSS dependencies.

    Looks for ``new URL('./x.css', import.meta.url)`` patterns and resolves
    the CSS file paths relative to the static root.

    Args:
        static_dirs: list of static directory paths (app dirs first,
            framework dir last).

    Returns:
        Sorted list of CSS paths relative to the static root
        (e.g. ``['./components/ntx-item.css', './components/ntx-list.css']``).
    """
    css_paths = set()
    for sd in static_dirs:
        sd_path = Path(sd)
        if not sd_path.is_dir():
            continue
        for js_file in sd_path.rglob('*.js'):
            # Skip node_modules
            if 'node_modules' in js_file.parts:
                continue
            try:
                content = js_file.read_text()
            except (UnicodeDecodeError, OSError):
                continue
            for match in _RE_CSS_IMPORT_META.finditer(content):
                css_rel = match.group(1)  # e.g. './ntx-list.css'
                css_file = (js_file.parent / css_rel).resolve()
                if css_file.is_file():
                    try:
                        rel = css_file.relative_to(sd_path)
                        css_paths.add('./' + '/'.join(rel.parts))
                    except ValueError:
                        pass
    return sorted(css_paths)
