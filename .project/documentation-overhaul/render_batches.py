"""Render bounded review packets. Rendering is NOT reading or assessment."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
rows = [json.loads(line) for line in (HERE / 'INVENTORY.jsonl').read_text().splitlines()]
groups = {'current': [], 'history': [], 'agent': [], 'other': []}
for row in rows:
    path = row['path']
    group = ('history' if row['classification'] == 'history-or-working-record'
             else 'agent' if row['classification'] == 'agent-guidance'
             else 'other' if Path(path).suffix == '.pdf' or '.egg-info/' in path
             else 'current')
    groups[group].append(row)
index = []
manifest = {}
for group, items in groups.items():
    packets = []
    content = ''
    entries = []
    for row in items:
        path = row['path']
        source = ROOT / path
        if source.suffix == '.pdf':
            index.append(f'PDF requires attachment Read: {path}')
            continue
        lines = source.read_text(errors='replace').splitlines()
        if group == 'history':
            # Short purpose/provenance inspection, explicitly not a full read.
            selected = sorted(set(range(min(10, len(lines)))) | set(range(max(0, len(lines)-3), len(lines))))
        else:
            selected = list(range(len(lines)))
        for start in range(0, len(selected), 130):
            chunk = selected[start:start+130]
            text = f'\n### {path} ({len(lines)} total lines)\n'
            text += ''.join(f'{i+1}: {lines[i][:1600]}\n' for i in chunk)
            entry = {'path': path, 'lines': [i+1 for i in chunk],
                     'truncated_lines': [i+1 for i in chunk if len(lines[i]) > 1600]}
            if content and len(content) + len(text) > 28000:
                packets.append((content, entries))
                content, entries = '', []
            content += text
            entries.append(entry)
    if content:
        packets.append((content, entries))
    for i, (text, entries) in enumerate(packets, 1):
        name = f'batch-{group}-{i:03d}.txt'
        (HERE / name).write_text(text)
        manifest[name] = entries
        index.append(f'{name}: {len(text)} chars; {len(entries)} chunks; ' + ', '.join(dict.fromkeys(e['path'] for e in entries)))
(HERE / 'BATCHES.json').write_text(json.dumps(manifest, indent=2) + '\n')
(HERE / 'BATCHES.txt').write_text('\n'.join(index) + '\n')
print(f'Rendered {len(manifest)} packets; none automatically marked read.')
