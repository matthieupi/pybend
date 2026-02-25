"""
scaffold.py — Generate starter web component files from a model's schema.

Usage:
    CLI:  python -m utils.scaffold Product
    API:  GET /Product?scaffold=item  (returns JS source as text/plain)

Reads the model's schema() output and generates:
    - {model}-card.js   — Item component extending NTTElement
    - {model}-grid.js   — List component extending ListElement
    - {model}-card.css  — Starter stylesheet

All generated code is immediately functional — override render() to customize.
"""
import logging
import re
import textwrap
from pathlib import Path
from typing import Optional

logger = logging.getLogger('pybend.utils')

# Where generated components go (relative to pybend root)
COMPONENTS_DIR = Path(__file__).parent.parent.parent / 'static' / 'components'


def _to_kebab(name: str) -> str:
    """CamelCase -> kebab-case  (e.g. ProductCard -> product-card)"""
    s = re.sub(r'([A-Z])', r'-\1', name).strip('-').lower()
    return s


def _to_pascal(name: str) -> str:
    """kebab-case or plain -> PascalCase"""
    return ''.join(w.capitalize() for w in re.split(r'[-_]', name))


def _js_default(field_def: dict) -> str:
    """Produce a sensible JS default expression for a field type."""
    t = field_def.get('type', 'string')
    if t == 'boolean':
        return 'false'
    if t == 'number' or t == 'integer':
        return '0'
    if t == 'array':
        return '[]'
    return "''"


def _field_html(key: str, field_def: dict, model_name: str, mode: str = 'display') -> str:
    """Generate the HTML snippet for one field in display mode."""
    t = field_def.get('type', 'string')
    widget = field_def.get('ui', {}).get('widget')

    # ListRef array fields
    if t == 'array' and field_def.get('items'):
        ref = field_def['items'].get('$ref', '')
        ref_model = ref.split('/')[-1] if ref else 'item'
        return (
            f'        <div class="{_to_kebab(model_name)}-{key}">\n'
            f'          ${{({key} ?? []).map(c =>\n'
            f'            `<ntt-item ref="${{c}}" data-model="{ref_model}"></ntt-item>`\n'
            f'          ).join(\'\')}}\n'
            f'        </div>'
        )

    # Currency widget
    if widget == 'currency':
        return (
            f'        <span class="{_to_kebab(model_name)}-{key}">'
            f'${{typeof {key} === \'number\' ? `$${{ {key}.toFixed(2) }}` : {key} ?? \'\'}}'
            f'</span>'
        )

    # Textarea / text blocks
    if widget == 'textarea' or t == 'text':
        return f'        <p class="{_to_kebab(model_name)}-{key}">${{{key} ?? \'\'}}</p>'

    # Boolean
    if t == 'boolean':
        return f'        <span class="{_to_kebab(model_name)}-{key}">${{{key} ? \'Yes\' : \'No\'}}</span>'

    # Default: string/number
    return f'        <span class="{_to_kebab(model_name)}-{key}">${{{key} ?? \'\'}}</span>'


def scaffold_item(schema: dict) -> str:
    """Generate a single-entity component from schema."""
    model_name = schema.get('__name__', 'Model')
    tag = _to_kebab(model_name) + '-card'
    cls_name = _to_pascal(model_name) + 'Card'
    fields = schema.get('properties', {})
    ui = schema.get('ui', {})
    methods = schema.get('methods', {})

    # Determine field rendering order
    field_order = ui.get('field_order', list(fields.keys()))
    # Add any fields not in order
    for k in fields:
        if k not in field_order:
            field_order.append(k)

    # Separate header fields from body fields
    header_fields = []
    body_fields = []
    for key in field_order:
        if key in ('id',):
            continue
        fd = fields.get(key)
        if not fd:
            continue
        # Skip hidden fields
        if fd.get('ui', {}).get('display') is False:
            continue
        if key == 'name':
            header_fields.insert(0, key)
        elif key == 'description':
            header_fields.append(key)
        else:
            body_fields.append(key)

    # Build destructure list
    all_visible = header_fields + body_fields
    destructure = ', '.join(all_visible) if all_visible else '...rest'

    # Build HTML lines
    html_lines = []
    for key in header_fields:
        fd = fields[key]
        if key == 'name':
            html_lines.append(f'        <h2 class="{_to_kebab(model_name)}-name">${{name ?? \'\'}}</h2>')
        elif key == 'description':
            html_lines.append(f'        <p class="{_to_kebab(model_name)}-description">${{description ?? \'\'}}</p>')

    for key in body_fields:
        fd = fields[key]
        label = fd.get('title', key)
        html_lines.append(f'        <label>{label}</label>')
        html_lines.append(_field_html(key, fd, model_name))

    # Method buttons
    method_lines = []
    for mname, mdef in methods.items():
        label = mdef.get('title', mname)
        method_lines.append(
            f'        <ntt-method model="{model_name}" '
            f'uuid="${{this.value?.id || \'\'}}" '
            f'method="{mname}" label="{label}"></ntt-method>'
        )

    fields_html = '\n'.join(html_lines)
    methods_html = '\n'.join(method_lines)

    return textwrap.dedent(f"""\
        /**
         * {cls_name} — Custom component for {model_name} entities.
         *
         * Generated by: python -m utils.scaffold {model_name}
         * Extend NTTElement for single entity lifecycle (UPDATE, DESCRIBE, save).
         * Override render() below to customize.
         */
        import {{ NTTElement }} from './NTTElement.js';
        import './ntt-method.js';

        export class {cls_name} extends NTTElement {{

          get styles() {{ return new URL('./{tag}.css', import.meta.url).href; }}

          render() {{
            if (!this.schema || !this.value) return;
            const {{ {destructure} }} = this.value || {{}};

            this.shadowRoot.innerHTML = `
              <div class="{tag}">
        {fields_html}
        {methods_html}
              </div>
            `;
            if (this.$styles) this.shadowRoot.appendChild(this.$styles);
          }}
        }}

        customElements.define('{tag}', {cls_name});
    """)


def scaffold_list(schema: dict) -> str:
    """Generate a collection component from schema."""
    model_name = schema.get('__name__', 'Model')
    item_tag = _to_kebab(model_name) + '-card'
    tag = _to_kebab(model_name) + '-grid'
    cls_name = _to_pascal(model_name) + 'Grid'

    return textwrap.dedent(f"""\
        /**
         * {cls_name} — Custom collection component for {model_name} entities.
         *
         * Generated by: python -m utils.scaffold {model_name}
         * Extend ListElement for collection lifecycle (UPDATE, childTag, createChild).
         * Override render() or get childTag() to customize.
         */
        import {{ ListElement }} from './ListElement.js';
        import './{item_tag}.js';

        export class {cls_name} extends ListElement {{

          get styles() {{ return new URL('./{tag}.css', import.meta.url).href; }}

          get childTag() {{ return '{item_tag}'; }}
        }}

        customElements.define('{tag}', {cls_name});
    """)


def scaffold_css(schema: dict) -> str:
    """Generate a starter CSS file for the item component."""
    model_name = schema.get('__name__', 'Model')
    tag = _to_kebab(model_name) + '-card'
    fields = schema.get('properties', {})
    ui = schema.get('ui', {})

    field_order = ui.get('field_order', list(fields.keys()))
    for k in fields:
        if k not in field_order:
            field_order.append(k)

    # Generate CSS selectors for each visible field
    field_rules = []
    for key in field_order:
        fd = fields.get(key, {})
        if key == 'id':
            continue
        if fd.get('ui', {}).get('display') is False:
            continue
        selector = f'.{_to_kebab(model_name)}-{key}'
        field_rules.append(f'{selector} {{\n  /* styles for {key} */\n}}')

    fields_css = '\n\n'.join(field_rules)

    return f"""\
/* {tag} — Generated starter styles */

:host {{
    display: block;
    animation: staggerIn 0.4s cubic-bezier(0.4, 0, 0.2, 1) both;
    animation-delay: var(--stagger-delay, 0ms);
}}

.{tag} {{
    position: relative;
    background: var(--glass-bg, rgba(14, 16, 24, 0.55));
    backdrop-filter: blur(var(--glass-blur, 16px));
    -webkit-backdrop-filter: blur(var(--glass-blur, 16px));
    border: 1px solid var(--glass-border, rgba(255,255,255,0.08));
    border-radius: var(--radius-lg, 16px);
    padding: 1.5rem 1.75rem 1.25rem;
    transition: border-color 0.3s, box-shadow 0.3s;
}}

.{tag}:hover {{
    border-color: var(--glass-border-hover, rgba(255,255,255,0.14));
    box-shadow: var(--shadow-md, 0 4px 16px rgba(0,0,0,.4));
}}

h2 {{
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--text-0, #f0f2f8);
    margin-bottom: 0.15rem;
}}

p {{
    font-size: 0.85rem;
    color: var(--text-2, #8891ab);
    line-height: 1.5;
}}

label {{
    display: block;
    margin: 0.9rem 0 0.3rem;
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-3, #555e78);
}}

label + span {{
    font-size: 0.9rem;
    color: var(--text-1, #c4c9da);
}}

{fields_css}

@keyframes staggerIn {{
    from {{ opacity: 0; transform: translateY(12px) scale(0.98); }}
    to   {{ opacity: 1; transform: translateY(0) scale(1); }}
}}
"""


def scaffold_list_css(schema: dict) -> str:
    """Generate a starter CSS file for the list component."""
    model_name = schema.get('__name__', 'Model')
    tag = _to_kebab(model_name) + '-grid'

    return f"""\
/* {tag} — Generated starter styles */

:host {{
    display: block;
    width: 100%;
}}

.list-header {{
    display: flex;
    align-items: baseline;
    gap: 0.75rem;
    margin-bottom: 1.5rem;
}}

.list-header h1 {{
    font-size: 1.4rem;
    font-weight: 700;
    color: var(--text-0, #f0f2f8);
}}

.list-count {{
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--accent, #22d3c5);
    background: var(--accent-dim, rgba(34,211,197,0.12));
    border-radius: 100px;
    padding: 0.15rem 0.6rem;
}}

.list-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 1rem;
}}
"""


def scaffold_model(model_name: str, schema: Optional[dict] = None, output_dir: Optional[Path] = None):
    """
    Generate all scaffold files for a model.

    Args:
        model_name: Model class name (e.g. "Product")
        schema: Pre-computed schema dict. If None, imports and calls model.schema().
        output_dir: Directory to write files. Defaults to COMPONENTS_DIR.
    """
    if schema is None:
        from pybend.core.utils.registrar import registered_models
        model_cls = registered_models.get(model_name)
        if not model_cls:
            raise ValueError(f"Model '{model_name}' not found in registered_models. "
                             f"Available: {list(registered_models.keys())}")
        schema = model_cls.schema()

    out = output_dir or COMPONENTS_DIR
    out.mkdir(parents=True, exist_ok=True)

    tag = _to_kebab(model_name)
    files = {
        f'{tag}-card.js': scaffold_item(schema),
        f'{tag}-card.css': scaffold_css(schema),
        f'{tag}-grid.js': scaffold_list(schema),
        f'{tag}-grid.css': scaffold_list_css(schema),
    }

    written = []
    for filename, content in files.items():
        path = out / filename
        if path.exists():
            logger.info("SKIP  %s (already exists)", path)
            continue
        path.write_text(content)
        written.append(str(path))
        logger.info("WRITE %s", path)

    return written


def scaffold_single(model_name: str, kind: str = 'item', schema: Optional[dict] = None) -> str:
    """
    Generate a single scaffold file's content (for API endpoint use).

    Args:
        model_name: Model class name
        kind: 'item', 'list', 'css', or 'list-css'
        schema: Pre-computed schema dict

    Returns:
        Generated source code as string
    """
    if schema is None:
        from pybend.core.utils.registrar import registered_models
        model_cls = registered_models.get(model_name)
        if not model_cls:
            raise ValueError(f"Model '{model_name}' not found")
        schema = model_cls.schema()

    generators = {
        'item': scaffold_item,
        'list': scaffold_list,
        'css': scaffold_css,
        'list-css': scaffold_list_css,
    }

    gen = generators.get(kind)
    if not gen:
        raise ValueError(f"Unknown scaffold kind '{kind}'. Use: {list(generators.keys())}")

    return gen(schema)


# ── CLI entry point ──

if __name__ == '__main__':
    import sys
    import os

    # Ensure we can import from the core directory
    core_dir = Path(__file__).parent.parent
    if str(core_dir) not in sys.path:
        sys.path.insert(0, str(core_dir))

    if len(sys.argv) < 2:
        print("Usage: python -m utils.scaffold <ModelName> [output_dir]")
        print("       python -m utils.scaffold Product")
        print("       python -m utils.scaffold Product ./my-components/")
        sys.exit(1)

    model_name = sys.argv[1]
    output = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    # Import and register models (requires main.py setup)
    try:
        from pybend.core.main import app  # noqa: triggers model registration
    except ImportError:
        print("Warning: Could not import main.py. Ensure you run from src/pybend/core/")
        print("  cd /workspace/src/pybend/core && python -m utils.scaffold " + model_name)
        sys.exit(1)

    written = scaffold_model(model_name, output_dir=output)
    if written:
        print(f"\nGenerated {len(written)} files for {model_name}.")
    else:
        print(f"\nAll files already exist for {model_name}. Delete to regenerate.")
