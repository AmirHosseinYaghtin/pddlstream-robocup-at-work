#!/usr/bin/env python
"""Run every evaluation scenario N times and record the averaged metrics.

    python -m evaluations.run                     # 20 trials, both phases
    python -m evaluations.run --trials 10
    python -m evaluations.run --phase continuous2d
    python -m evaluations.run --scenario at_work --trials 3

Writes evaluations/results/results.json (per-trial + aggregate) and one
summary CSV per phase. Plot afterwards with `python -m evaluations.plot`.
"""

from __future__ import print_function

import argparse
import csv
import json
import math
import os
import platform
import sys

from evaluations.metrics import ALL_METRICS, run_trial
from evaluations.scenarios import ALGORITHM, MAX_TIME, MERGE_ACTIONS, PHASES, scenarios_for

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')
RESULTS_FILE = 'results.json'

# The eight metrics that describe planner behaviour per scenario, in the order
# they are reported. `solved`/`timeout`/`solutions`/`wall_time` are recorded too
# but are diagnostics rather than the headline comparison (see plot.py).
PRIMARY_METRICS = [
    'run_time',
    'search_time',
    'sample_time',
    'evaluations',
    'iterations',
    'complexity',
    'skeletons',
    'cost',
]

SECONDARY_METRICS = ['length', 'solutions', 'wall_time']

DEFAULT_TRIALS = 20


def _finite(value):
    """JSON-safe: INF cost (no solution) and None both become None."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def mean(values):
    values = [v for v in values if v is not None]
    if not values:
        return None
    return sum(values) / float(len(values))


def stdev(values):
    """Population standard deviation; None when fewer than two samples."""
    values = [v for v in values if v is not None]
    if len(values) < 2:
        return None
    mu = sum(values) / float(len(values))
    return math.sqrt(sum((v - mu) ** 2 for v in values) / float(len(values)))


def aggregate(trials):
    """Average each metric over the trials that produced a value for it.

    Cost/length are averaged over *solved* trials only -- averaging in a
    failed trial's missing cost would silently bias the mean downwards.
    """
    solved_trials = [t for t in trials if t.get('solved')]
    agg = {
        'trials': len(trials),
        'solved_trials': len(solved_trials),
        'success_rate': len(solved_trials) / float(len(trials)) if trials else 0.,
        'timeout_rate': (sum(1 for t in trials if t.get('timeout')) / float(len(trials))
                         if trials else 0.),
    }
    for metric in ALL_METRICS + ['wall_time']:
        if metric in ('solved', 'timeout'):
            continue
        source = solved_trials if metric in ('cost', 'length') else trials
        values = [t.get(metric) for t in source]
        if metric in ('cost', 'length'):
            values = [v for v in values if v is not None]
        agg[metric] = mean(values)
        agg[metric + '_std'] = stdev(values)
    return agg


def run_scenario(scenario, trials, quiet=True):
    print('  {:<18} {}'.format(scenario.label, scenario.complexity))
    records = []
    for trial in range(trials):
        metrics, solution = run_trial(scenario.solve, quiet=quiet)
        record = {key: _finite(value) for key, value in metrics.items()}
        record['trial'] = trial
        # `solved` is a bool from the store; keep it verbatim, and note whether
        # a plan came back at all even if the cost bound was not met.
        record['has_plan'] = solution[0] is not None
        records.append(record)
        print('    trial {}/{}  solved={!s:<5} run_time={:8.3f}s  cost={}  length={}'.format(
            trial + 1, trials, bool(record.get('solved')),
            record.get('run_time') or 0.,
            'n/a' if record.get('cost') is None else '{:.3f}'.format(record['cost']),
            record.get('length')))
    return records


def run_all(selected, trials, quiet=True):
    results = {
        'config': {
            'algorithm': ALGORITHM,
            'merge_actions_continuous': MERGE_ACTIONS,
            'max_time': MAX_TIME,
            'trials': trials,
            'python': platform.python_version(),
            'platform': platform.platform(),
        },
        'primary_metrics': PRIMARY_METRICS,
        'secondary_metrics': SECONDARY_METRICS,
        'phases': [],
    }

    by_phase = {}
    for scenario in selected:
        by_phase.setdefault(scenario.phase, []).append(scenario)

    for phase_name, _ in PHASES:
        if phase_name not in by_phase:
            continue
        print('\n=== phase: {} ({}, {} trials each) ==='.format(
            phase_name, ALGORITHM, trials))
        phase_record = {'phase': phase_name, 'scenarios': []}
        for scenario in by_phase[phase_name]:
            records = run_scenario(scenario, trials, quiet=quiet)
            phase_record['scenarios'].append({
                'label': scenario.label,
                'problem': scenario.problem,
                'complexity': scenario.complexity,
                'trials': records,
                'average': aggregate(records),
            })
        results['phases'].append(phase_record)
    return results


def write_results(results, out_dir=RESULTS_DIR):
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    json_path = os.path.join(out_dir, RESULTS_FILE)
    with open(json_path, 'w') as f:
        json.dump(results, f, indent=2, sort_keys=True)
    print('\nWrote', json_path)

    columns = ['scenario', 'problem', 'trials', 'solved_trials', 'success_rate',
               'timeout_rate'] + PRIMARY_METRICS + SECONDARY_METRICS
    for phase in results['phases']:
        csv_path = os.path.join(out_dir, '{}.csv'.format(phase['phase']))
        with open(csv_path, 'w') as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            for scenario in phase['scenarios']:
                avg = scenario['average']
                row = [scenario['label'], scenario['problem']]
                row += [avg.get(column) for column in columns[2:]]
                writer.writerow(row)
        print('Wrote', csv_path)
    return json_path


def print_table(results):
    for phase in results['phases']:
        print('\n--- {} (mean over {} trials) ---'.format(
            phase['phase'], results['config']['trials']))
        header = ['scenario'] + PRIMARY_METRICS
        widths = [max(len(header[0]), *[len(s['label']) for s in phase['scenarios']])]
        widths += [max(len(m), 10) for m in PRIMARY_METRICS]
        print('  '.join(h.rjust(w) if i else h.ljust(w)
                        for i, (h, w) in enumerate(zip(header, widths))))
        for scenario in phase['scenarios']:
            avg = scenario['average']
            cells = [scenario['label'].ljust(widths[0])]
            for metric, width in zip(PRIMARY_METRICS, widths[1:]):
                value = avg.get(metric)
                if value is None:
                    cells.append('n/a'.rjust(width))
                elif metric.endswith('_time') or metric == 'cost':
                    cells.append('{:.3f}'.format(value).rjust(width))
                else:
                    cells.append('{:.1f}'.format(value).rjust(width))
            print('  '.join(cells))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-n', '--trials', type=int, default=DEFAULT_TRIALS,
                        help='Number of times to solve each scenario (default: %(default)s)')
    parser.add_argument('--phase', default=None, choices=[name for name, _ in PHASES],
                        help='Restrict to one phase (default: both)')
    parser.add_argument('--scenario', default=None,
                        help='Restrict to scenarios whose label contains this substring')
    parser.add_argument('-o', '--out-dir', default=RESULTS_DIR,
                        help='Where to write results (default: %(default)s)')
    parser.add_argument('--verbose', action='store_true',
                        help="Let the planner's per-iteration output through")
    parser.add_argument('--no-plot', action='store_true',
                        help='Skip plotting after the run')
    args = parser.parse_args(argv)

    if args.trials < 1:
        parser.error('--trials must be >= 1')

    selected = scenarios_for(args.phase)
    if args.scenario:
        selected = [s for s in selected if args.scenario in s.label]
        if not selected:
            parser.error('No scenario label contains {!r}'.format(args.scenario))

    results = run_all(selected, args.trials, quiet=not args.verbose)
    print_table(results)
    json_path = write_results(results, out_dir=args.out_dir)

    if not args.no_plot:
        from evaluations.plot import plot_results
        plot_results(results, out_dir=args.out_dir)
    return json_path


if __name__ == '__main__':
    sys.exit(0 if main() else 0)
