"""
Compare two profiling runs and output a delta table.

Usage:
    python -m n3tx.core.tests.profiling.compare <file_a> <file_b>
    python -m n3tx.core.tests.profiling.compare .traces/.profiling/api_perf_baseline.json .traces/.profiling/api_perf_optimized.json
"""
import json
import sys
from pathlib import Path

from n3tx.core.tests.profiling.seed_perf import tier_record_count

PROFILING_DIR = Path('.traces/.profiling')


def load_results(path):
    """Load profiling results and index by (tier, name)."""
    with open(path) as f:
        data = json.load(f)
    index = {}
    for r in data['results']:
        key = (r['tier'], r['name'])
        index[key] = r['duration_ms']
    return data['label'], index


def compare(file_a, file_b):
    label_a, results_a = load_results(file_a)
    label_b, results_b = load_results(file_b)

    all_keys = list(dict.fromkeys(list(results_a.keys()) + list(results_b.keys())))

    lines = []
    lines.append(f'Performance Comparison: {label_a} vs {label_b}')
    lines.append(f'{"=" * 90}')
    lines.append('')

    current_tier = None
    tier_totals_a = {}
    tier_totals_b = {}

    header = f'{"Operation":<40} {label_a:>10} {label_b:>10} {"Delta":>10} {"Change":>10}'
    separator = '-' * 82

    for tier, name in all_keys:
        if tier != current_tier:
            if current_tier and current_tier in tier_totals_a:
                ta = tier_totals_a[current_tier]
                tb = tier_totals_b.get(current_tier, 0)
                delta = tb - ta
                pct = (delta / ta * 100) if ta > 0 else 0
                lines.append(separator)
                lines.append(f'{"TOTAL":<40} {ta:>10.2f} {tb:>10.2f} {delta:>+10.2f} {pct:>+9.1f}%')
                lines.append('')

            current_tier = tier
            lines.append(f'--- Tier: {tier} ---')
            lines.append(header)
            lines.append(separator)

        ms_a = results_a.get((tier, name), 0)
        ms_b = results_b.get((tier, name), 0)
        delta = ms_b - ms_a
        pct = (delta / ms_a * 100) if ms_a > 0 else 0

        tier_totals_a[tier] = tier_totals_a.get(tier, 0) + ms_a
        tier_totals_b[tier] = tier_totals_b.get(tier, 0) + ms_b

        marker = ''
        if pct < -10:
            marker = ' <<'
        elif pct > 10:
            marker = ' !!'

        lines.append(f'{name:<40} {ms_a:>10.2f} {ms_b:>10.2f} {delta:>+10.2f} {pct:>+9.1f}%{marker}')

    # Final tier total
    if current_tier and current_tier in tier_totals_a:
        ta = tier_totals_a[current_tier]
        tb = tier_totals_b.get(current_tier, 0)
        delta = tb - ta
        pct = (delta / ta * 100) if ta > 0 else 0
        lines.append(separator)
        lines.append(f'{"TOTAL":<40} {ta:>10.2f} {tb:>10.2f} {delta:>+10.2f} {pct:>+9.1f}%')

    # Grand totals
    lines.append('')
    lines.append('=' * 82)
    grand_a = sum(tier_totals_a.values())
    grand_b = sum(tier_totals_b.values())
    grand_delta = grand_b - grand_a
    grand_pct = (grand_delta / grand_a * 100) if grand_a > 0 else 0
    lines.append(f'{"GRAND TOTAL":<40} {grand_a:>10.2f} {grand_b:>10.2f} {grand_delta:>+10.2f} {grand_pct:>+9.1f}%')

    # Scaling analysis
    lines.append('')
    lines.append('Scaling Analysis (total ms per tier):')
    lines.append(f'{"Tier":<10} {"Records":>8} {label_a:>12} {label_b:>12} {"Delta":>12} {"Change":>10}')
    lines.append('-' * 66)
    for tier in ['empty', 'small', 'medium', 'large', 'full']:
        ta = tier_totals_a.get(tier, 0)
        tb = tier_totals_b.get(tier, 0)
        d = tb - ta
        p = (d / ta * 100) if ta > 0 else 0
        records = tier_record_count(tier)
        lines.append(f'{tier:<10} {records:>8} {ta:>12.1f} {tb:>12.1f} {d:>+12.1f} {p:>+9.1f}%')

    output = '\n'.join(lines)
    return output


def compare_json(file_a, file_b):
    """Compare two runs and return structured JSON for the dashboard."""
    label_a, results_a = load_results(file_a)
    label_b, results_b = load_results(file_b)
    all_keys = list(dict.fromkeys(list(results_a.keys()) + list(results_b.keys())))

    rows = []
    tier_totals = {}
    for tier, name in all_keys:
        ms_a = results_a.get((tier, name), 0)
        ms_b = results_b.get((tier, name), 0)
        delta = ms_b - ms_a
        pct = (delta / ms_a * 100) if ms_a > 0 else 0
        rows.append({'tier': tier, 'name': name, 'a': ms_a, 'b': ms_b, 'delta': round(delta, 2), 'pct': round(pct, 1)})
        if tier not in tier_totals:
            tier_totals[tier] = {'a': 0, 'b': 0}
        tier_totals[tier]['a'] += ms_a
        tier_totals[tier]['b'] += ms_b

    scaling = []
    for tier in ['empty', 'small', 'medium', 'large', 'full']:
        t = tier_totals.get(tier, {'a': 0, 'b': 0})
        d = t['b'] - t['a']
        p = (d / t['a'] * 100) if t['a'] > 0 else 0
        scaling.append({'tier': tier, 'db_records': tier_record_count(tier), 'a': round(t['a'], 1), 'b': round(t['b'], 1), 'delta': round(d, 1), 'pct': round(p, 1)})

    return {
        'label_a': label_a, 'label_b': label_b,
        'rows': rows, 'scaling': scaling,
    }


def main():
    if len(sys.argv) < 3:
        print('Usage: python -m n3tx.core.tests.profiling.compare <file_a> <file_b>')
        sys.exit(1)

    file_a, file_b = sys.argv[1], sys.argv[2]
    output = compare(file_a, file_b)
    print(output)

    PROFILING_DIR.mkdir(parents=True, exist_ok=True)
    comparison_path = PROFILING_DIR / 'comparison.txt'
    with open(comparison_path, 'w') as f:
        f.write(output)
    print(f'\nComparison written to {comparison_path}')


if __name__ == '__main__':
    main()
