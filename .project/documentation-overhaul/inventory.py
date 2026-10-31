"""Reproducible documentation discovery; never infer human review from a scan."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = Path(__file__).resolve().parent
EXTENSIONS = {'.md', '.mdx', '.rst', '.txt', '.adoc', '.org', '.jsonl', '.pdf'}
EXCLUDED = {
    '.project', '.git', 'node_modules', '.venv', 'venv', '.venv-agents', '.venv-e2e',
    '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache',
}
# These are observed reading windows, not automatic assessment claims.
WINDOWS = {
    'AGENTS.md': [[1, 713]],
    'README.md': [[1, 250]],
    'BACKEND.md': [[1, 180]],
    'FRONTEND.md': [[1, 150]],
    'docs/GETTING_STARTED.md': [[1, 100]],
    'docs/API_CUSTOM_ENDPOINTS.md': [[1, 115]],
    'docs/MODELS.md': [[1, 413]],
    'docs/AGENTS.md': [[1, 736]],
    'packages/n3tx-agents/README.md': [[1, 95]],
    'packages/n3tx-ui/README.md': [[1, 100]],
    'packages/n3tx-actors/README.md': [[1, 130]],
}
FINDINGS = {
    'docs/GETTING_STARTED.md': ['F01', 'F02'],
    'docs/API_CUSTOM_ENDPOINTS.md': ['F03', 'F04'],
    'README.md': ['F05', 'F10'],
    'AGENTS.md': ['F05', 'F08', 'F10'],
    'BACKEND.md': ['F08'],
    'FRONTEND.md': ['F08'],
    'packages/n3tx-agents/README.md': ['F06'],
    'packages/n3tx-ui/README.md': ['F07'],
    'docs/AGENTS.md': ['F09'],
}


def discover():
    writers = {}
    for report in ('core-report.md', 'frontend-report.md', 'capabilities-report.md'):
        for line in (OUTPUT / report).read_text().splitlines():
            cells = [cell.strip().strip('`') for cell in line.split('|')[1:-1]]
            if not cells or not cells[0].endswith('.md') or len(cells) < 5:
                continue
            name = cells[0]
            if not (ROOT / name).is_file():
                continue
            writers[name] = (report, cells)
    writers['docs/OPERATIONS.md'] = ('core-report.md', [
        'docs/OPERATIONS.md', 'Operational boundaries and deployment guidance',
        'New guide', 'Actual defaults and known limitations', 'New canonical guide'])
    local_path = OUTPUT / 'T02D-DECISIONS.json'
    local = json.loads(local_path.read_text()) if local_path.exists() else {}
    closing = json.loads((OUTPUT / 'CLOSING-ASSESSMENTS.json').read_text())
    current_path = OUTPUT / 'CURRENT-REVIEWS.json'
    current_reviews = json.loads(current_path.read_text()) if current_path.exists() else {}
    modified = set(subprocess.check_output(['git', 'diff', '--name-only'], cwd=ROOT).decode().splitlines())
    review_path = OUTPUT / 'REVIEWS.json'
    review = json.loads(review_path.read_text()) if review_path.exists() else {'batches': [], 'assessments': {}}
    history_path = OUTPUT / 'HISTORICAL-REVIEWS.json'
    history_review = json.loads(history_path.read_text()) if history_path.exists() else {'batches': [], 'assessments': {}}
    manifest_path = OUTPUT / 'BATCHES.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    observed = {}
    for batch in review['batches'] + history_review['batches']:
        for entry in manifest[batch]:
            observed.setdefault(entry['path'], set()).update(set(entry['lines']) - set(entry['truncated_lines']))
    tracked = set(subprocess.check_output(
        ['git', 'ls-files', '-z'], cwd=ROOT
    ).decode().split('\0')) - {''}
    paths = set()
    exclusions = []
    aliases = []
    for parent, directories, files in os.walk(ROOT, followlinks=False):
        for name in list(directories):
            path = Path(parent) / name
            relative = path.relative_to(ROOT).as_posix()
            if path.is_symlink():
                aliases.append({'path': relative, 'target': os.readlink(path)})
                directories.remove(name)
            elif name in EXCLUDED or path == OUTPUT:
                exclusions.append({'path': relative, 'reason': (
                    'User excludes all .project content from assessment; audit artifacts remain here'
                    if name == '.project' else 'Dependency, Git metadata, or runtime cache'
                )})
                directories.remove(name)
        for name in files:
            path = Path(parent) / name
            if path.suffix.lower() in EXTENSIONS or name in {'LICENSE', 'NOTICE'}:
                paths.add(path.relative_to(ROOT).as_posix())
    # Include missing tracked documentation rather than silently dropping it.
    for name in tracked:
        if Path(name).suffix.lower() in EXTENSIONS and not any(
            part in EXCLUDED for part in Path(name).parts
        ) and not name.startswith('.project/documentation-overhaul/'):
            paths.add(name)
    rows = []
    for name in sorted(paths):
        path = ROOT / name
        history = name.startswith(('.project/', 'apps/veille/.planning/', 'docs/changelogs/'))
        agent = name.startswith(('.agents/', '.opencode/', '.pi/', '.claude/'))
        generated = name.startswith('docs/generated/')
        metadata = Path(name).name.startswith('requirements') or name in {'LICENSE', 'NOTICE'}
        group = ('history-or-working-record' if history else 'agent-guidance' if agent
                 else 'generated-reference' if generated else 'metadata' if metadata
                 else 'current-or-unclassified-documentation')
        spans = WINDOWS.get(name, [])
        raw = path.read_bytes() if path.is_file() else b''
        lines = len(raw.splitlines())
        seen = observed.get(name, set()).copy()
        for first, last in spans:
            seen.update(range(first, last + 1))
        spans = []
        for line in sorted(seen):
            if spans and spans[-1][1] == line - 1:
                spans[-1][1] = line
            else:
                spans.append([line, line])
        complete = bool(spans and spans == [[1, lines]])
        rows.append({
            'path': name,
            'tracked': name in tracked,
            'exists': path.exists(),
            'sha256': hashlib.sha256(raw).hexdigest() if path.is_file() else None,
            'line_count': lines,
            'classification': group,
            'classification_basis': 'Path-based triage; not a content verdict',
            'read_status': 'prior-recorded-full-unverified' if complete else 'prior-recorded-partial' if spans else 'not-recorded',
            'read_windows': spans,
            'assessment_status': 'findings-recorded' if name in FINDINGS else 'pending',
            'audience': 'maintainers' if history else 'coding-agents' if agent else 'developers',
            'value': 'Historical decision/provenance evidence' if history else 'Pending content assessment',
            'presentation_issues': ['See AUDIT.md finding IDs'] if name in FINDINGS else ['Not assessed'],
            'correctness_issues': FINDINGS.get(name, []),
            'completeness_issues': [] if complete else ['Full content review not completed'],
            'disposition': 'rewrite' if name in FINDINGS else 'keep',
            'disposition_status': 'proposed' if name in FINDINGS else 'provisional-preserve-until-reviewed',
            'canonical_destination': name,
            'destination_status': 'Current location preserved; see rewrite plan for consolidation candidates',
            'symlink_target': os.readlink(path) if path.is_symlink() else None,
        })
        assessment = review['assessments'].get(name)
        if name in history_review['assessments']:
            purpose, provenance, issue = history_review['assessments'][name]
            assessment = {
                'classification': 'historical-or-planning-record',
                'audience': 'Maintainers researching provenance',
                'value': purpose,
                'assessment_evidence': provenance,
                'assessment_depth': 'Bounded purpose/status/provenance inspection; not full content verification',
                'presentation_issues': ['Keep clearly separate from current contract'],
                'correctness_issues': [issue],
                'completeness_issues': ['Historical implementation claims not revalidated'],
                'disposition': 'keep', 'canonical_destination': name,
                'destination_status': 'Preserve original historical record in place; label from canonical navigation',
            }
        if assessment:
            rows[-1].update(assessment)
            rows[-1]['assessment_status'] = 'assessed'
            rows[-1]['disposition_status'] = 'proposed-after-content-review'
            rows[-1]['classification_basis'] = 'Content reviewed; see assessment_evidence'
            rows[-1]['disposition'] = 'keep'
            rows[-1]['disposition_status'] = 'T02D-preserved-with-recorded-caveats'
            rows[-1]['canonical_destination'] = name
            rows[-1]['destination_status'] = 'Retained at existing path; prior move proposals not applied'
        if name in history_review['assessments'] and name.startswith('.project/orchestration/'):
            rows[-1]['classification'] = 'live-coordination-record'
            rows[-1]['destination_status'] = 'Live coordination ledger; outside audit edit ownership'
        if name in modified or name in writers:
            rows[-1]['read_status'] = 'not-recorded-for-current-revision'
            rows[-1]['read_windows'] = []
        if name in writers:
            report, cells = writers[name]
            rows[-1].update({
                'assessment_status': 'assessed',
                'assessment_evidence': f'Writer assessment: .project/documentation-overhaul/{report}',
                'assessment_depth': 'Attributed writer assessment; not a T02D independent full read',
                'value': cells[1], 'presentation_issues': [cells[2]],
                'correctness_issues': [cells[3]],
                'completeness_issues': [cells[4]] if len(cells) > 5 else ['See writer verification gaps'],
                'disposition': cells[-1], 'disposition_status': 'writer-applied',
                'canonical_destination': name,
                'destination_status': 'Current writer-owned path; preserved by T02D',
                'classification_basis': 'Writer per-path assessment; issue descriptions may concern pre-rewrite text',
                'writer_report_sha256': hashlib.sha256((OUTPUT / report).read_bytes()).hexdigest(),
            })
        if name in local or name in closing:
            value, issues, disposition, classification, evidence = closing.get(name, local.get(name))
            rows[-1].update({
                'value': value, 'presentation_issues': [issues],
                'correctness_issues': ['See assessment evidence and revision-specific caveats'],
                'completeness_issues': ['Runtime/browser execution is separate from content review'],
                'classification': classification, 'disposition': disposition,
                'canonical_destination': name, 'destination_status': 'Stable path retained',
                'assessment_evidence': evidence if name in closing else 'Prior-session claim, not recertified: ' + evidence,
                'assessment_depth': 'Content assessment; read coverage separately qualified',
                'read_status': 'closing-original-read; current-authored-or-preserved' if name in closing else 'prior-session-coverage-unverified',
                'read_windows': [],
            })
            rows[-1]['assessment_status'] = 'assessed'
            rows[-1]['classification_basis'] = 'T02D content assessment'
            rows[-1]['disposition_status'] = 'T02D-applied-or-preserved'
        if '.egg-info/' in name:
            rows[-1].update({
                'assessment_status': 'assessed', 'classification': 'generated-package-metadata',
                'classification_basis': 'Content inspected in batch-other-001.txt',
                'audience': 'Packaging tools and maintainers',
                'value': 'Generated source manifest, dependency requirements or import root',
                'assessment_evidence': 'Prior-session metadata classification cites batch-other-001.txt; full reading not recertified',
                'assessment_depth': 'Metadata classification; not a dependency compatibility certification',
                'presentation_issues': [], 'correctness_issues': ['Regenerate from package metadata, do not hand-edit'],
                'completeness_issues': ['Snapshot freshness not certified'],
                'disposition': 'keep-generated', 'disposition_status': 'preserve-no-manual-edit',
                'canonical_destination': name, 'destination_status': 'Packaging-owned artifact',
                'read_status': 'prior-session-coverage-unverified', 'read_windows': [],
            })
        row = rows[-1]
        row['owned_current_guide'] = False
        if '.egg-info/' in name:
            row['assessment_status'] = 'classified-generated-metadata'
            row['classification_basis'] = 'Packaging artifact path; no substantive review claimed'
        elif name in writers:
            row['assessment_status'] = 'writer-reported'
        elif history or row['classification'] in {
            'historical-record', 'historical-design', 'application-research',
            'historical-or-planning-record', 'stale-generated-reference',
            'historical-test-report', 'historical-changelog',
        }:
            row['assessment_status'] = 'classified-historical-or-generated'
            row['assessment_depth'] = 'Bounded classification; not a substantive full assessment'
        elif metadata or row['classification'] in {
            'application-domain-input', 'application-domain-source', 'application-domain-transcription',
        } or path.suffix == '.pdf':
            row['assessment_status'] = 'classified-non-guide'
        else:
            row['owned_current_guide'] = True
            row['assessment_status'] = 'current-review-pending'
        # Prior batch captures and original-read claims cannot certify this revision.
        if name in closing:
            row['read_status'] = 'prior-closing-claim-unverified'
            row['assessment_evidence'] = 'Prior closing claim, not recertified: ' + row['assessment_evidence']
        evidence = current_reviews.get(name)
        if evidence and row['owned_current_guide']:
            row['current_review'] = evidence
            if evidence['sha256'] == row['sha256'] and evidence['read_windows'] == [[1, lines]]:
                row['assessment_status'] = 'current-revision-reviewed'
                row['assessment_depth'] = 'Full current text review; not runtime correctness certification'
                row['classification_basis'] = 'Revision-pinned direct read; see current_review'
                row['read_status'] = 'full-current-revision-read'
                row['read_windows'] = evidence['read_windows']
                row['assessment_evidence'] = evidence['assessment']
                row['completeness_issues'] = ['Content review only; runtime execution is separate']
    return rows, sorted(exclusions, key=lambda x: x['path']), sorted(aliases, key=lambda x: x['path'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    rows, exclusions, aliases = discover()
    inventory = ''.join(json.dumps(row, ensure_ascii=True, sort_keys=True) + '\n' for row in rows)
    scope = json.dumps({'extensions': sorted(EXTENSIONS), 'exclusions': exclusions,
                        'user_exclusion': 'All .project content, including plans, research, history and orchestration; artifacts stored there are outputs only',
                         'directory_aliases': aliases}, indent=2, sort_keys=True) + '\n'
    remaining = ''.join(r['path'] + '\n' for r in rows if r['assessment_status'] == 'current-review-pending')
    if args.check:
        assert (OUTPUT / 'INVENTORY.jsonl').read_text() == inventory, 'Inventory drift'
        assert (OUTPUT / 'SCOPE.json').read_text() == scope, 'Scope drift'
        assert (OUTPUT / 'REMAINING.txt').read_text() == remaining, 'Remaining-list drift'
    else:
        (OUTPUT / 'INVENTORY.jsonl').write_text(inventory)
        (OUTPUT / 'SCOPE.json').write_text(scope)
        (OUTPUT / 'REMAINING.txt').write_text(remaining)
    print(json.dumps({
        'paths': len(rows), 'tracked': sum(r['tracked'] for r in rows),
        'closing_original_reads': sum(r['read_status'].startswith('closing-original-read') for r in rows),
        'coverage_note': 'Assessment counts are not full-current-revision read counts',
        'paths_with_findings': sum(r['assessment_status'] == 'findings-recorded' for r in rows),
        'assessment_categories': {status: sum(r['assessment_status'] == status for r in rows)
                                  for status in sorted({r['assessment_status'] for r in rows})},
        'owned_current_guides_remaining': sum(r['assessment_status'] == 'current-review-pending' for r in rows),
        'excluded_directories': len(exclusions), 'directory_aliases': len(aliases),
        'check': args.check,
    }, sort_keys=True))


if __name__ == '__main__':
    main()
