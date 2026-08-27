#!/usr/bin/env python
"""Comparison sweeps: PDDLStream algorithms, and Fast Downward search configs.

    python -m evaluations.sweep --probe        # 1 trial/cell, 60s cap: what works?
    python -m evaluations.sweep --algorithms   # incremental/focused/binding/adaptive
    python -m evaluations.sweep --planners     # FD search configurations
    python -m evaluations.sweep --all          # probe, then both sweeps

Each *cell* -- one (scenario, algorithm) or (scenario, planner) pair -- runs in
its own process group so it can be killed outright.  That is not defensive
programming: `--algorithm incremental` on continuous2d hangs inside Fast
Downward's translator, which never returns to the point where PDDLStream checks
`max_time`, so nothing short of an external kill stops it.

Results stream to JSONL per cell, so a killed or interrupted cell keeps the
trials it already finished and re-running resumes instead of restarting.

Cells that fail during the probe are re-run at a reduced trial count rather than
the full 20 -- a deterministic grounding blowup does not become more informative
when repeated twenty times.  The reduction is recorded per cell in the output
JSON (`requested_trials` vs the sweep's `trials`) and printed in the summary, so
it is never a silent hole in the data.
"""

from __future__ import print_function

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from collections import namedtuple

from evaluations.run import RESULTS_DIR, aggregate
from evaluations.scenarios import ALL_SCENARIOS, MAX_TIME, MERGE_ACTIONS

SWEEP_DIR = os.path.join(RESULTS_DIR, 'sweeps')

# --------------------------------------------------------------------------
# What gets compared
# --------------------------------------------------------------------------

# pddlstream/algorithms/meta.py: ALGORITHMS = ['incremental'] + FOCUSED_ALGORITHMS
ALGORITHM_KEYS = ['incremental', 'focused', 'binding', 'adaptive']

# Keys into pddlstream/algorithms/downward.py SEARCH_OPTIONS, chosen to span the
# heuristic families (blind / hmax / lmcut / ff / cea / add) and the
# eager-vs-lazy and greedy-vs-weighted axes.
#
# NOTE for the write-up: the three A* configs are *not* optimal with respect to
# the cost we report. Every template in SEARCH_OPTIONS wraps its heuristic in
# adapt_costs(cost_type=PLUSONE) and runs the search itself at cost_type=PLUSONE,
# so they minimise (cost + 1 per action), not cost. They are the cost-sensitive
# end of the spectrum, not a ground-truth optimum.
PLANNER_KEYS = [
    'ff-astar2',        # == downward.DEFAULT_PLANNER: the reference point
    'ff-astar',
    'ff-eager',
    'ff-lazy',
    'ff-wastar3',
    'cea-wastar3',
    'add-random-lazy',
    'max-astar',
    'lmcut-astar',
    'dijkstra',
]

REFERENCE_PLANNER = 'ff-astar2'
REFERENCE_ALGORITHM = 'adaptive'

# Why some cells return no plan.  Each of these was diagnosed by hand from the
# probe, because neither failure surfaces as a Python error the worker can label:
#
#   lmcut-astar   Fast Downward's LM-cut heuristic does not support axioms.
#                 continuous2d/domain_merged.pddl:232 declares
#                 `(:derived (In ?o ?reg) ...)`, which the translator emits as a
#                 SAS axiom rule, so FD prints "This configuration does not
#                 support axioms! ... Tried to use unsupported feature." and
#                 exits nonzero.  run_search() ignores the return code
#                 (downward.py:461, the check is commented out) and finds no plan
#                 file, so it returns (None, INF) -- a silent 0.00 in ~0.1s.
#                 Confirmed by running the search binary directly on the
#                 output.sas the failing run left in temp/.  discrete2d has no
#                 axioms, which is why the same config solves all three of its
#                 scenarios.
#
#   focused,      AssertionError: "Could not find instantiation for PNE:
#   binding       'PNE movecost(v2, v16)'".  Both raise this on continuous2d,
#                 i.e. an immediate error rather than a timeout: the optimistic
#                 objects these algorithms plan over have no MoveCost value to
#                 instantiate.  focused raises it on all four continuous
#                 scenarios; binding gets much further, because it binds more
#                 before planning -- at n=20 it solves pick_place 17/20 and
#                 corridor 18/20, and the two larger scenarios defeat it by
#                 *hanging* rather than by this assertion: on multi_object it
#                 returned one plan and was then killed sampling, and on at_work
#                 it was killed in stream planning.  (multi_object was 2/3 by the
#                 assertion while table2 sat 2.0 from table1.  The separation the
#                 scenario now uses gives binding far more base motion to bind up
#                 front, which moves its failure from the assertion to a hang.)
#                 So the note below applies to binding at the probe's n=1 but not
#                 to any zero-coverage cell in the final sweep; write_table only
#                 attaches it to non-hang failures for exactly that reason.
#
#   incremental   Hangs in the translator, not in search -- see the module
#                 docstring.  This one *is* labelled automatically, from the
#                 SIGUSR1 stack dump.
DIAGNOSED_FAILURES = {
    'lmcut-astar': 'FD\'s LM-cut heuristic does not support axioms, and '
                   'continuous2d derives (In ?o ?reg); FD exits with '
                   '"unsupported feature" and no plan file.',
    'focused': 'AssertionError: could not instantiate the MoveCost PNE for an '
               'optimistic object.',
    'binding': 'AssertionError: could not instantiate the MoveCost PNE for an '
               'optimistic object.',
}

# --------------------------------------------------------------------------
# Budgets
# --------------------------------------------------------------------------

TRIALS = 20             # for cells the probe says work
FAILED_TRIALS = 3       # for cells the probe says do not
PROBE_TRIALS = 1

PROBE_MAX_TIME = 60.    # planner's own budget during the probe
STALL_SLACK = 30.       # grace on top of max_time before we call it stalled

Cell = namedtuple('Cell', ['axis', 'key', 'phase', 'scenario', 'algorithm', 'planner'])


def cell_id(cell):
    return '{}__{}__{}'.format(cell.phase, cell.scenario, cell.key)


def build_cells(sweep):
    cells = []
    for scenario in ALL_SCENARIOS:
        if sweep == 'algorithms':
            for key in ALGORITHM_KEYS:
                cells.append(Cell('algorithm', key, scenario.phase, scenario.label,
                                  key, None))
        elif sweep == 'planners':
            for key in PLANNER_KEYS:
                cells.append(Cell('planner', key, scenario.phase, scenario.label,
                                  REFERENCE_ALGORITHM, key))
        else:
            raise ValueError('Unknown sweep: {}'.format(sweep))
    return cells


# --------------------------------------------------------------------------
# Running one cell
# --------------------------------------------------------------------------

# Ordered most- to least-specific: the first family whose marker appears in the
# stack dump wins, so a translator hang is not mislabelled as "search" just
# because run_search sits higher up the same stack.
HANG_SITES = [
    ('translation', ('build_model', 'instantiate', 'translate_and_write',
                     'pddl_to_sas', 'normalize', 'sas_from_pddl')),
    ('search', ('run_search', 'read_sas', 'parse_solution')),
    ('sampling', ('process_stream_queue', 'rrt_plan_base', 'skeleton_queue',
                  'get_next', 'process_instance')),
    # Stuck building the optimistic evaluation set before any of the above --
    # binding on at_work dies here, inside plan_streams' evaluation_from_fact,
    # with the GC running.  Checked last so that a translator or sampler blowup
    # reached *through* plan_streams still gets the more specific label.
    ('stream planning', ('plan_streams', 'evaluation_from_fact', 'head_from_fact',
                         'iterative_plan_streams', 'hierarchical_plan_streams',
                         'relaxed_stream_plan')),
]


def classify_hang(log_text):
    """Which phase of planning was the killed cell stuck in?

    Read out of the faulthandler stack dump the worker emits on SIGUSR1, so it
    is measured rather than assumed.
    """
    if not log_text:
        return None
    # Only look at the last stack dump -- earlier ones may be from a previous
    # trial in the same cell that completed fine.
    marker = 'Current thread'
    tail = log_text[log_text.rfind(marker):] if marker in log_text else log_text
    for site, needles in HANG_SITES:
        if any(needle in tail for needle in needles):
            return site
    return 'unknown'


def _count_lines(path):
    if not os.path.exists(path):
        return 0
    with open(path) as fh:
        return sum(1 for line in fh if line.strip())


def _read_trials(path):
    trials = []
    if not os.path.exists(path):
        return trials
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                trials.append(json.loads(line))
            except ValueError:
                # A kill mid-write can truncate the last line; drop it rather
                # than lose the whole cell.
                pass
    return trials


def _kill_group(proc, dump_stack=False):
    """SIGKILL the worker's whole process group.

    The group, not the process: FD's binary is a grandchild (run_search shells
    out), and start_new_session=True means it is not in our group, so killing
    only `proc` would leave the planner running.
    """
    if dump_stack:
        try:
            os.kill(proc.pid, signal.SIGUSR1)
            time.sleep(1.0)
        except OSError:
            pass
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except OSError:
        pass
    proc.wait()


def run_cell(cell, out_dir, trials, max_time, verbose=False):
    """Launch a worker for one cell, watchdog it, and return a status dict."""
    jsonl = os.path.join(out_dir, cell_id(cell) + '.jsonl')
    logpath = os.path.join(out_dir, cell_id(cell) + '.log')

    already = _count_lines(jsonl)
    if already >= trials:
        return {'status': 'cached', 'completed': already, 'hang_site': None}

    cmd = [sys.executable, '-m', 'evaluations.worker',
           '--phase', cell.phase,
           '--scenario', cell.scenario,
           '--algorithm', cell.algorithm,
           '--trials', str(trials),
           '--max-time', str(max_time),
           '--out', jsonl]
    if cell.planner is not None:
        cmd += ['--planner', cell.planner]

    # A stalled trial is one that has produced no new JSONL line for longer than
    # the planner's own budget plus slack. Watching the file rather than the
    # process gives per-trial granularity from a single process per cell.
    stall_limit = max_time + STALL_SLACK
    killed = 0
    hang_site = None

    with open(logpath, 'a') as log_fh:
        proc = subprocess.Popen(cmd, stdout=log_fh, stderr=subprocess.STDOUT,
                                start_new_session=True, cwd=os.getcwd())
        # Ctrl-C unwinds out of the sleep below, and the worker is in its own
        # session so it never sees the terminal's SIGINT. Without this the
        # interrupted cell leaks a worker and an FD binary that go on burning a
        # core -- which would then quietly skew the timings of the next sweep.
        try:
            last_size = -1
            last_change = time.time()
            while True:
                if proc.poll() is not None:
                    break
                time.sleep(0.5)
                size = os.path.getsize(jsonl) if os.path.exists(jsonl) else 0
                now = time.time()
                if size != last_size:
                    last_size, last_change = size, now
                elif now - last_change > stall_limit:
                    _kill_group(proc, dump_stack=True)
                    killed = 1
                    break
        except BaseException:
            if proc.poll() is None:
                print('\nInterrupted -- killing the {} worker; the {} trial(s) '
                      'already written are kept.'.format(
                          cell_id(cell), _count_lines(jsonl)))
                _kill_group(proc)
            raise

    log_text = ''
    if os.path.exists(logpath):
        with open(logpath) as fh:
            log_text = fh.read()
    if killed:
        hang_site = classify_hang(log_text)

    completed = _count_lines(jsonl)
    if killed:
        status = 'killed'
    elif proc.returncode != 0:
        status = 'crashed'
    elif completed >= trials:
        status = 'ok'
    else:
        status = 'partial'
    return {'status': status, 'completed': completed, 'hang_site': hang_site,
            'returncode': proc.returncode}


# --------------------------------------------------------------------------
# Sweep driver
# --------------------------------------------------------------------------

def _scenario_meta(phase, label):
    for scenario in ALL_SCENARIOS:
        if scenario.phase == phase and scenario.label == label:
            return scenario
    return None


def run_sweep(sweep, out_root=SWEEP_DIR, trials=TRIALS, failed_trials=FAILED_TRIALS,
              max_time=MAX_TIME, probe=False, viability=None, verbose=False):
    out_dir = os.path.join(out_root, 'probe' if probe else sweep)
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)

    cells = build_cells(sweep)
    viability = viability or {}
    records = []
    reductions = []

    print('\n=== sweep: {}{} ({} cells) ==='.format(
        sweep, ' [probe]' if probe else '', len(cells)))

    for index, cell in enumerate(cells, 1):
        if probe:
            cell_trials, cell_max_time = PROBE_TRIALS, PROBE_MAX_TIME
        elif viability.get(cell_id(cell), True):
            cell_trials, cell_max_time = trials, max_time
        else:
            # Probe said this cell does not produce a plan. Record the failure
            # a few times rather than twenty; see module docstring.
            cell_trials, cell_max_time = failed_trials, PROBE_MAX_TIME
            reductions.append(cell_id(cell))

        started = time.time()
        status = run_cell(cell, out_dir, cell_trials, cell_max_time, verbose=verbose)
        elapsed = time.time() - started

        cell_trials_data = _read_trials(os.path.join(out_dir, cell_id(cell) + '.jsonl'))
        scenario = _scenario_meta(cell.phase, cell.scenario)
        record = {
            'axis': cell.axis,
            'key': cell.key,
            'phase': cell.phase,
            'scenario': cell.scenario,
            'problem': scenario.problem if scenario else None,
            'complexity': scenario.complexity if scenario else None,
            'algorithm': cell.algorithm,
            'planner': cell.planner,
            'requested_trials': cell_trials,
            'max_time': cell_max_time,
            'status': status['status'],
            'hang_site': status['hang_site'],
            'wall_time': elapsed,
            'trials': cell_trials_data,
            'average': aggregate(cell_trials_data) if cell_trials_data else None,
        }
        records.append(record)

        avg = record['average'] or {}
        print('  [{:>3}/{}] {:<44} {:<8} n={:<3} success={:<5} {}'.format(
            index, len(cells), cell_id(cell), status['status'],
            len(cell_trials_data),
            '{:.2f}'.format(avg.get('success_rate', 0.)) if avg else 'n/a',
            'hang@{}'.format(status['hang_site']) if status['hang_site'] else
            ('{:.1f}s'.format(avg['run_time']) if avg.get('run_time') else '')))

    result = {
        'sweep': sweep,
        'probe': probe,
        'config': {
            'trials': PROBE_TRIALS if probe else trials,
            'failed_trials': failed_trials,
            'max_time': PROBE_MAX_TIME if probe else max_time,
            'merge_actions_continuous': MERGE_ACTIONS,
            'reference_algorithm': REFERENCE_ALGORITHM,
            'reference_planner': REFERENCE_PLANNER,
            'algorithm_keys': ALGORITHM_KEYS,
            'planner_keys': PLANNER_KEYS,
        },
        'reduced_cells': reductions,
        'cells': records,
    }

    path = os.path.join(out_root, '{}{}.json'.format('probe_' if probe else '', sweep))
    with open(path, 'w') as fh:
        json.dump(result, fh, indent=2, sort_keys=True)
    print('Wrote', path)
    if reductions:
        print('NOTE: {} cell(s) run at n={} instead of n={} because the probe '
              'found no plan:'.format(len(reductions), failed_trials, trials))
        for cid in reductions:
            print('        ', cid)
    return result


def viability_from(probe_results):
    """cell_id -> did the probe get a plan out of this cell?"""
    viable = {}
    for result in probe_results:
        for cell in result['cells']:
            avg = cell.get('average') or {}
            viable[cell_id(Cell(cell['axis'], cell['key'], cell['phase'],
                                cell['scenario'], cell['algorithm'],
                                cell['planner']))] = bool(avg.get('solved_trials'))
    return viable


def print_matrix(result):
    """Cross-tab of success rate: scenario rows, sweep-key columns."""
    keys = []
    for cell in result['cells']:
        if cell['key'] not in keys:
            keys.append(cell['key'])
    rows = []
    for cell in result['cells']:
        row = (cell['phase'], cell['scenario'])
        if row not in rows:
            rows.append(row)

    by = {(c['phase'], c['scenario'], c['key']): c for c in result['cells']}
    width = max(12, max(len(k) for k in keys) + 1)
    label_width = max(len('{}/{}'.format(*r)) for r in rows) + 2

    print('\n--- {} : success rate ---'.format(result['sweep']))
    print(' ' * label_width + ''.join(k.rjust(width) for k in keys))
    for row in rows:
        line = '{}/{}'.format(*row).ljust(label_width)
        for key in keys:
            cell = by.get((row[0], row[1], key))
            avg = (cell or {}).get('average') or {}
            if not cell:
                text = '-'
            elif cell.get('hang_site'):
                text = 'hang:' + cell['hang_site'][:4]
            elif not avg:
                text = 'n/a'
            else:
                text = '{:.2f}'.format(avg.get('success_rate', 0.))
            line += text.rjust(width)
        print(line)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--probe', action='store_true',
                        help='1 trial per cell at a 60s cap, to find viable cells')
    parser.add_argument('--algorithms', action='store_true',
                        help='Compare the four PDDLStream algorithms')
    parser.add_argument('--planners', action='store_true',
                        help='Compare Fast Downward search configurations')
    parser.add_argument('--all', action='store_true',
                        help='Probe, then run both sweeps')
    parser.add_argument('-n', '--trials', type=int, default=TRIALS)
    parser.add_argument('--failed-trials', type=int, default=FAILED_TRIALS)
    parser.add_argument('--max-time', type=float, default=MAX_TIME)
    parser.add_argument('-o', '--out-dir', default=SWEEP_DIR)
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args(argv)

    do_probe = args.probe or args.all
    sweeps = []
    if args.algorithms or args.all:
        sweeps.append('algorithms')
    if args.planners or args.all:
        sweeps.append('planners')
    if not do_probe and not sweeps:
        parser.error('Pick at least one of --probe / --algorithms / --planners / --all')

    probe_results = []
    if do_probe:
        for sweep in (sweeps or ['algorithms', 'planners']):
            result = run_sweep(sweep, out_root=args.out_dir, probe=True,
                               verbose=args.verbose)
            print_matrix(result)
            probe_results.append(result)

    if not sweeps:
        return

    viability = viability_from(probe_results) if probe_results else None
    if viability is None:
        # Reuse a previous probe if one is on disk.
        loaded = []
        for sweep in sweeps:
            path = os.path.join(args.out_dir, 'probe_{}.json'.format(sweep))
            if os.path.exists(path):
                with open(path) as fh:
                    loaded.append(json.load(fh))
        viability = viability_from(loaded) if loaded else {}
        if viability:
            print('Using viability from the probe results already on disk.')
        else:
            print('No probe found -- every cell gets the full trial count.')

    for sweep in sweeps:
        result = run_sweep(sweep, out_root=args.out_dir, trials=args.trials,
                           failed_trials=args.failed_trials,
                           max_time=args.max_time, viability=viability,
                           verbose=args.verbose)
        print_matrix(result)


if __name__ == '__main__':
    main()
