# scripts/generate_docs.py
import os
from models.proto_model import ProtoModel
from utils.registrar import registered_models
from pathlib import Path

DOCS_DIR = Path("docs")
DOCS_DIR.mkdir(exist_ok=True)

def generate_markdown_for_model(model_name, model_cls):
    schema = model_cls.schema()
    fields = schema.get('properties', {})
    methods = schema.get('methods', {})
    defs = schema.get('$defs', {})

    lines = []
    lines.append(f"# `{model_name}` Model")
    lines.append("")
    lines.append(f"**Endpoint**: `GET /{model_name}` (returns schema)")
    lines.append("")
    lines.append("## Fields")
    lines.append("")
    lines.append("| Name | Type | Required | Default |")
    lines.append("|------|------|----------|---------|")

    for field, meta in fields.items():
        ftype = meta.get('type', 'object')
        required = field in schema.get('required', [])
        default = meta.get('default', '—')
        lines.append(f"| {field} | {ftype} | {'Yes' if required else 'No'} | {default} |")

    lines.append("\n## Routes")
    for method_name, meta in methods.items():
        route = meta['route']
        http_methods = ", ".join(meta['methods'])
        scope = meta['scope']
        lines.append(f"### `{route}` [{http_methods}] ({scope})")
        lines.append(f"**Method**: `{method_name}`")
        lines.append("#### Parameters:")
        if meta['parameters']:
            for pname, pschema in meta['parameters'].items():
                ptype = pschema.get('type', 'object')
                lines.append(f"- `{pname}`: *{ptype}*")
        else:
            lines.append("- *(none)*")

        rtype = meta['returns'].get('type', 'None')
        lines.append(f"**Returns**: `{rtype}`\n")

    return "\n".join(lines)

def generate_docs():
    index_lines = ["# PyBend API Documentation", ""]
    for name, cls in registered_models.items():
        md = generate_markdown_for_model(name, cls)
        file_path = DOCS_DIR / f"{name}.md"
        with open(file_path, "w") as f:
            f.write(md)
        index_lines.append(f"- [{name}](./{name}.md)")

    with open(DOCS_DIR / "index.md", "w") as f:
        f.write("\n".join(index_lines))

if __name__ == "__main__":
    generate_docs()
    print("✅ Documentation generated in /docs/")
