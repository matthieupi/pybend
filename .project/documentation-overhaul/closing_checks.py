"""Documentation-only closure checks; scans never certify human read coverage."""

import argparse
from collections import Counter
import difflib
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    rows = [json.loads(line) for line in (OUT / 'INVENTORY.jsonl').read_text().splitlines()]
    local = json.loads((OUT / 'T02D-DECISIONS.json').read_text())
    closing = json.loads((OUT / 'CLOSING-ASSESSMENTS.json').read_text())
    decisions = local | closing
    changed = set(subprocess.check_output(['git', 'diff', 'HEAD', '--name-only', '-z'], cwd=ROOT).decode().split('\0')) - {''}
    changed |= set(subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard', '-z'], cwd=ROOT).decode().split('\0')) - {''}
    changed = {name for name in changed if not name.startswith('.project/')}
    by_path = {row['path']: row for row in rows}
    assert not any('.project' in Path(row['path']).parts for row in rows)
    assert all(row['assessment_status'] == 'classified-generated-metadata'
               for row in rows if '.egg-info/' in row['path'])
    assert changed <= by_path.keys(), 'Out-of-inventory changes require review'
    manifest = []
    preservation = []
    frontmatter = []
    links_checked = 0
    link_issues = []
    for name in sorted(changed):
        row = by_path[name]
        current = (ROOT / name).read_bytes()
        assert hashlib.sha256(current).hexdigest() == row['sha256'], name
        owner = 'T02D' if name in decisions else row.get('assessment_evidence', 'unattributed')
        manifest.append({'path': name, 'owner': owner, 'sha256': row['sha256']})
        old_result = subprocess.run(['git', 'show', f'HEAD:{name}'], cwd=ROOT, capture_output=True)
        old = old_result.stdout.decode() if old_result.returncode == 0 else ''
        text = current.decode()
        if name.startswith(('.agents/', '.opencode/')) and old.startswith('---\n'):
            old_settings = re.sub(r'^description:.*$', '', old.split('---', 2)[1], flags=re.M)
            new_settings = re.sub(r'^description:.*$', '', text.split('---', 2)[1], flags=re.M)
            assert old_settings == new_settings, f'Non-description frontmatter changed: {name}'
            frontmatter.append(name)
        # Notices preserve original bodies, including obsolete links and claims.
        historical = (name in decisions and decisions[name][2] in {'historical-label', 'stale-label'}
                      and name != 'docs/generated/index.md') or name in {
                          'docs/frontend/PACKAGE_ARCHITECTURE.md',
                          'docs/frontend/01_UI_SEPARATION_CONCERNS.md',
                          'docs/frontend/02_UI_PRIMITIVES_ENHANCEMENT.md',
                          'docs/frontend/03_SYSTEM_IMPROVEMENTS_REFACTOR.md'}
        if historical:
            diff = list(difflib.SequenceMatcher(a=old.rstrip('\n').splitlines(), b=text.rstrip('\n').splitlines()).get_opcodes())
            assert all(tag in {'equal', 'insert'} for tag, *_ in diff), f'Original body altered: {name}'
            preservation.append(name)
            text = '\n'.join('\n'.join(text.splitlines()[j:k]) for tag, _, _, j, k in diff if tag == 'insert')
        if not name.endswith('.md'):
            continue
        # Templates are assessed as templates, not promoted to runnable guide links.
        if name.startswith('.agents/') or name.startswith('.opencode/commands/'):
            continue
        text = re.sub(r'```.*?```', '', text, flags=re.S)
        inline_code = [(match.start(), match.end()) for match in re.finditer(r'`[^`\n]*`', text)]
        for match in re.finditer(r'\[[^\]\n]+\]\(([^)\n]+)\)', text):
            if any(start <= match.start() < end for start, end in inline_code):
                continue
            target = match[1].strip().strip('<>')
            url = urlsplit(target)
            if url.scheme or url.netloc:
                continue
            path = (ROOT / name).parent / unquote(url.path) if url.path else ROOT / name
            links_checked += 1
            if not path.exists():
                link_issues.append({'path': name, 'target': target, 'issue': 'missing local target'})
            elif url.fragment and path.suffix == '.md':
                headings = []
                for heading in re.findall(r'^#{1,6}\s+(.+?)\s*#*$', path.read_text(), re.M):
                    slug = re.sub(r'[^\w\- ]', '', heading.lower()).replace(' ', '-')
                    headings.append(slug)
                if unquote(url.fragment) not in headings:
                    link_issues.append({'path': name, 'target': target, 'issue': 'fragment needs manual review'})
    result = {
        'baseline': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip(),
        'scope_paths': len(rows),
        'assessment_categories': dict(Counter(row['assessment_status'] for row in rows)),
        'owned_current_guides_remaining': sum(row['assessment_status'] == 'current-review-pending' for row in rows),
        'assessment_read_statuses': dict(Counter(row['read_status'] for row in rows)),
        'changed_documents': len(manifest),
        'T02D_changed_documents': sum(item['owner'] == 'T02D' for item in manifest),
        'writer_changed_documents': sum(item['owner'] != 'T02D' for item in manifest),
        'preserved_original_bodies_except_final_newlines': preservation,
        'unchanged_agent_settings_except_descriptions': frontmatter,
        'local_inline_links_checked': links_checked, 'link_issues': link_issues,
        'limits': ['No external requests', 'No rendered Markdown validation',
                   'Heading slugs are approximated; flagged fragments need manual review',
                   'Preserved historical bodies and generic workflow templates excluded from link checks',
                   'No read-coverage inference from hashes or scans'],
    }
    outputs = {'CHANGED-FILES.json': manifest, 'CLOSING-CHECKS.json': result}
    for filename, value in outputs.items():
        encoded = json.dumps(value, indent=2, ensure_ascii=True, sort_keys=True) + '\n'
        if args.check:
            assert (OUT / filename).read_text() == encoded, f'{filename} drift'
        else:
            (OUT / filename).write_text(encoded)
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == '__main__':
    main()
