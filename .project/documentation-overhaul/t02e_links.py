"""Repository-wide Markdown local link/anchor scan; no .project source reads."""
from pathlib import Path
import json
import re
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
SKIP = {'.git', '.project', 'node_modules', '.venv', '__pycache__'}
HISTORICAL = {'README_pre.md', 'CHANGELOG.md', 'RELEASE_NOTES.md', 'TODO.md',
              'Universal Context Protocol.md', '01_UI_SEPARATION_CONCERNS.md',
              '02_UI_PRIMITIVES_ENHANCEMENT.md', '03_SYSTEM_IMPROVEMENTS_REFACTOR.md',
              'PACKAGE_ARCHITECTURE.md'}

def historical(path):
    return path.name in HISTORICAL or any(p in {'changelogs', 'generated', 'proposals'} for p in path.parts)

def prose(text):
    return re.sub(r'^(```|~~~).*?^\1[^\n]*$', '', text, flags=re.M | re.S)

def anchors(path):
    text = prose(path.read_text())
    result, counts = set(), {}
    for heading in re.findall(r'^#{1,6}\s+(.+?)\s*#*$', text, re.M):
        heading = re.sub(r'\[([^]]+)\]\([^)]*\)', r'\1', heading)
        slug = re.sub(r'[^\w\- ]', '', heading.lower()).replace(' ', '-')
        count = counts.get(slug, 0)
        result.add(slug + (f'-{count}' if count else ''))
        counts[slug] = count + 1
    result.update(re.findall(r'(?:id|name)=["\']([^"\']+)', text))
    return result

def main():
    report = {'scope': 'All repository Markdown, excluding .project, dependencies and VCS. Historical bodies excluded from current results; separately scanned for provenance.',
              'files': 0, 'links': 0, 'current_errors': [], 'historical_errors': [],
              'agent_template_references': [], 'excluded_project_links': 0}
    for source in sorted(ROOT.rglob('*.md')):
        if any(p in SKIP for p in source.relative_to(ROOT).parts):
            continue
        report['files'] += 1
        text = prose(source.read_text())
        links = re.findall(r'\[[^\]]*\]\(([^\s)]+)(?:\s+"[^"]*")?\)', text)
        links += re.findall(r'^\s*\[[^]]+\]:\s*(\S+)', text, re.M)
        for link in links:
            url = urlsplit(link.strip('<>'))
            if url.scheme or url.netloc or link.startswith('/'):
                continue
            target = (source.parent / unquote(url.path)).resolve() if url.path else source
            if '.project' in target.parts:
                report['excluded_project_links'] += 1
                continue
            report['links'] += 1
            error = None
            if not target.exists():
                error = 'missing path'
            elif url.fragment and target.suffix == '.md' and unquote(url.fragment) not in anchors(target):
                error = 'missing anchor'
            if error:
                bucket = 'historical_errors' if historical(source) else 'current_errors'
                if source.name in {'ideation-agent.md', 'ideation-researcher.md', 'static-site-researcher.md'}:
                    bucket = 'agent_template_references'
                report[bucket].append({'source': str(source.relative_to(ROOT)), 'link': link, 'error': error})
    (OUT / 't02e-links.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
