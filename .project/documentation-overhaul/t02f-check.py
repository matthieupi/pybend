"""Bounded syntax checks; never executes illustrative commands or certifies reads."""
import ast
import json
from pathlib import Path
import posixpath
import re
import subprocess
import textwrap

ROOT = Path(__file__).resolve().parents[2]
PATHS = [
    '.agents/agents/test-writer.md', '.agents/agents/ideation-agent.md',
    '.agents/agents/perf-audit-frontend.md', '.agents/prompts/git-smart.md',
    '.agents/prompts/bugfix.md', '.agents/prompts/build-feature.md',
    '.agents/prompts/fix-test.md', '.agents/skills/dev/fix-test/SKILL.md',
    '.agents/skills/research/ideation/SKILL.md',
    '.agents/skills/perf/perf-analysis/SKILL.md',
    '.opencode/commands/git-smart.md', '.opencode/skills/README.md',
] + [f'.opencode/skills/n3tx-{name}/SKILL.md' for name in (
    'widgets', 'authorization', 'ui-schema', 'skill-routing', 'principles',
    'actors', 'frontend', 'methods-routes', 'testing', 'ui-components')]

if __name__ == '__main__':
    counts = {'python': 0, 'javascript': 0, 'bash': 0, 'jsonl_rows': 0}
    for name in PATHS:
        text = (ROOT / name).read_text()
        for match in re.finditer(r'^([ ]*)```(python|javascript|bash|jsonl)\n(.*?)^\1```', text, re.M | re.S):
            lang, code = match[2], textwrap.dedent(match[3])
            if lang == 'python':
                if name.endswith('test-writer.md') and code.startswith('# Good:'):
                    print('SKIP signature-only naming illustration:', name)
                    continue
                ast.parse(code)
            elif lang == 'javascript':
                subprocess.run(['node', '--input-type=module', '--check'], input=code, text=True, check=True)
            elif lang == 'bash':
                if '<relevant_test_dirs>' in code:
                    print('SKIP explicitly placeholder shell selection:', name)
                    continue
                subprocess.run(['bash', '-n'], input=code, text=True, check=True)
            else:
                for row in code.splitlines():
                    json.loads(row)
                    counts['jsonl_rows'] += 1
                continue
            counts[lang] += 1
    print('Syntax only; no illustrative commands executed:', counts)
    for n in (2, 4, 6, 8):
        slug = 'webassembly-20261019T120000Z-a'
        parent = f'.project/research/{slug}'
        analysis = f'{parent}/{n+1:02d}-{slug}-analysis.md'
        summary = '.project/vision/Webassembly-20261019T120000Z-a-summary.md'
        assert posixpath.normpath(posixpath.join(posixpath.dirname(summary), f'../research/{slug}/{n+1:02d}-{slug}-analysis.md')) == analysis
        assert posixpath.normpath(posixpath.join(parent, '../../vision/' + posixpath.basename(summary))) == summary
        assert posixpath.normpath(posixpath.join(parent, '01-industry-and-decisions.md')) == parent + '/01-industry-and-decisions.md'
    print('Ideation relative-link model: N=2,4,6,8 passed; no research pipeline executed')
