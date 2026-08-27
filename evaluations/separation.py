#!/usr/bin/env python
"""How does the planner-vs-state-machine cost gap scale with table separation?

    python -m evaluations.separation              # the shipped scan, n=10
    python -m evaluations.separation -n 20
    python -m evaluations.separation --separations 2 8 20

`multi_object` is the scenario that isolates *routing* rather than plan length:
every solution is 12 actions with 6 `move_base`, so the flat MOVE_BASE_COST and
PICK_PLACE_COST charges cancel and COST_PER_BASE_DIST -- how far the base
actually drives -- is the entire cost signal.  The planner may batch, because
`pick_and_stow` preserves (CanMoveArm ?r) and the tray has 3 slots; the scripted
state machine in baseline.py cannot, because it transfers objects in a fixed
order with one tray slot.  So the planner crosses between the tables once and
the state machine crosses once per object.

That predicts the gap grows linearly in the separation with a slope of roughly
(objects - 1) x 2 x COST_PER_BASE_DIST, and a single separation cannot
distinguish that prediction from a lucky constant.  This module measures the
whole curve, which is why it exists as a module and not as a number in a
comment: the claim in the report is about the *slope*, not about one cell.

It rebuilds the shipped problem and moves only table2, so every other property
of the scenario (cube poses, shelf, tray size, initial base pose) stays whatever
multi_object.py currently says.  Both sides run through the same code paths the
main evaluation uses -- domains.continuous2d.run.solve_tamp and
evaluations.baseline.ContinuousScript -- so the costs are priced by the same
functions and are directly comparable.

Caveats that belong with the numbers:
  * Trials are not independent.  `adaptive` loads and rewrites
    statistics/py3/robocup-continuous-tamp.pkl on every solve, keyed per domain,
    so a scan run after a full 7-scenario campaign starts from different sampler
    statistics than one run cold.  The curve's slope is stable; its absolute
    offset moves by a few cost units between campaigns.
  * `adaptive` splits its budget on wall-clock, and these solves take ~1s, so
    run this with nothing else planning or a contended run will report a worse
    skeleton than the planner would otherwise find.
"""

from __future__ import print_function

import argparse
import json
import os
import time

import numpy as np

from domains.continuous2d.primitives import OBJECT_SIZES, Region, region_as_furniture
from domains.continuous2d.problems.multi_object import get_multi_object_problem
from domains.continuous2d.run import solve_tamp
from evaluations.baseline import ContinuousScript, ScriptFailure
from evaluations.plan_shape import shape_of
from evaluations.run import RESULTS_DIR
from evaluations.scenarios import ALGORITHM, MAX_TIME, MERGE_ACTIONS

# Chosen to bracket the shipped value on both sides.  2.0 is included on purpose:
# it is what the scenario shipped before this scan, and it is the point where the
# gap disappears into trial noise -- the figure needs that end of the curve to
# explain why an earlier evaluation showed no cost advantage at all.
SEPARATIONS = (2.0, 4.0, 6.0, 8.0, 10.0, 12.0)
DEFAULT_TRIALS = 10

OUT_DIR = os.path.join(RESULTS_DIR, 'sweeps')


def shipped_separation(problem=None):
    """Centre-to-centre x distance between the two tables as shipped."""
    problem = problem or get_multi_object_problem()
    return abs(_centre_x(problem.regions['table1'])
               - _centre_x(problem.regions['table2']))


def _centre_x(region):
    return 0.5 * (region.lower[0] + region.upper[0])


def problem_fn_at(separation):
    """The shipped multi_object problem with table2 moved, nothing else touched."""
    def problem_fn():
        base = get_multi_object_problem()      # also (re)fills OBJECT_SIZES
        table1, table2 = base.regions['table1'], base.regions['table2']
        half_width = 0.5 * (table2.upper[0] - table2.lower[0])
        centre_x = _centre_x(table1) - separation
        moved = Region(lower=(centre_x - half_width, table2.lower[1]),
                       upper=(centre_x + half_width, table2.upper[1]))

        regions = dict(base.regions, table2=moved)
        centre, size = region_as_furniture(moved)
        OBJECT_SIZES['table2'] = size
        # The furniture list carries the collision footprint, so moving the region
        # without moving the furniture would leave the old table blocking the base.
        furniture = [(name, centre if name == 'table2' else position)
                     for name, position in base.furniture]
        return base._replace(regions=regions, furniture=furniture)
    return problem_fn


def _summary(costs, trials, **extra):
    """mean/std over the solved trials, plus whatever shape metrics came with them."""
    summary = {'trials': trials, 'solved_trials': len(costs),
               'success_rate': float(len(costs)) / trials if trials else None,
               'cost': None, 'cost_std': None}
    if costs:
        array = np.array(costs, dtype=float)
        summary['cost'] = float(array.mean())
        summary['cost_std'] = float(array.std())
    for key, values in extra.items():
        summary[key] = float(np.mean(values)) if values else None
    return summary


def measure_planner(problem_fn, trials, algorithm=ALGORITHM, max_time=MAX_TIME):
    costs, peaks, travels, run_times, lengths = [], [], [], [], []
    for _ in range(trials):
        start = time.time()
        plan, cost, _ = solve_tamp(problem_fn(), algorithm=algorithm,
                                   merge_pick_and_stow=MERGE_ACTIONS,
                                   max_time=max_time, dump=False, verbose=False)
        elapsed = time.time() - start
        if plan is None:
            continue
        shape = shape_of(plan)
        costs.append(cost)
        peaks.append(shape['peak'])
        travels.append(shape['travel'])
        lengths.append(len(plan))
        run_times.append(elapsed)
    return _summary(costs, trials, tray_peak=peaks, travel=travels,
                    run_time=run_times, length=lengths)


def measure_script(problem_fn, trials):
    costs, peaks, travels, run_times, lengths = [], [], [], [], []
    for _ in range(trials):
        script = ContinuousScript(problem_fn())
        start = time.time()
        try:
            plan = script.run()
        except ScriptFailure:
            continue
        elapsed = time.time() - start
        shape = shape_of(plan)
        costs.append(script.cost)
        peaks.append(shape['peak'])
        travels.append(shape['travel'])
        lengths.append(len(plan))
        run_times.append(elapsed)
    return _summary(costs, trials, tray_peak=peaks, travel=travels,
                    run_time=run_times, length=lengths)


def scan(separations=SEPARATIONS, trials=DEFAULT_TRIALS, verbose=True):
    shipped = shipped_separation()
    points = []
    for separation in separations:
        problem_fn = problem_fn_at(separation)
        planner = measure_planner(problem_fn, trials)
        script = measure_script(problem_fn, trials)
        gap = (script['cost'] - planner['cost']
               if planner['cost'] is not None and script['cost'] is not None else None)
        point = {
            'separation': float(separation),
            'shipped': abs(separation - shipped) < 1e-6,
            'planner': planner,
            'script': script,
            'gap': gap,
            'gap_fraction': gap / script['cost'] if gap is not None else None,
        }
        points.append(point)
        if verbose:
            _print_point(point, trials)
    return {
        'sweep': 'separation',
        'config': {'scenario': 'multi_object', 'phase': 'continuous2d',
                   'trials': trials, 'algorithm': ALGORITHM,
                   'merge_actions': MERGE_ACTIONS, 'max_time': MAX_TIME,
                   'shipped_separation': shipped,
                   'separations': [float(s) for s in separations]},
        'points': points,
    }


def _print_point(point, trials):
    for name in ('planner', 'script'):
        side = point[name]
        if side['cost'] is None:
            print('sep={:>5.1f}  {:<8} NO SOLUTION in {} trials'.format(
                point['separation'], name, trials))
            continue
        print('sep={:>5.1f}  {:<8} {:2d}/{:2d} solved  cost={:7.2f} +/- {:5.2f}  '
              'tray_peak={:.1f}  travel={:6.2f}  t={:5.2f}s'.format(
                  point['separation'], name, side['solved_trials'], trials,
                  side['cost'], side['cost_std'], side['tray_peak'],
                  side['travel'], side['run_time']))
    if point['gap'] is not None:
        print('sep={:>5.1f}  {:<8} script - planner = {:6.2f}   planner {:4.1f}% cheaper{}'
              .format(point['separation'], 'GAP', point['gap'],
                      100. * point['gap_fraction'],
                      '   <-- shipped' if point['shipped'] else ''))
    print()


def slope(result, side):
    """Least-squares cost-per-unit-separation, the number the claim rests on."""
    xs = [p['separation'] for p in result['points'] if p[side]['cost'] is not None]
    ys = [p[side]['cost'] for p in result['points'] if p[side]['cost'] is not None]
    if len(xs) < 2:
        return None
    return float(np.polyfit(xs, ys, 1)[0])


def write_result(result, out_dir=OUT_DIR):
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    result['config']['planner_cost_slope'] = slope(result, 'planner')
    result['config']['script_cost_slope'] = slope(result, 'script')
    path = os.path.join(out_dir, 'separation.json')
    with open(path, 'w') as fh:
        json.dump(result, fh, indent=2, sort_keys=True)
    print('Wrote', path)
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-n', '--trials', type=int, default=DEFAULT_TRIALS)
    parser.add_argument('--separations', type=float, nargs='+', default=list(SEPARATIONS),
                        help='centre-to-centre x distances to measure')
    parser.add_argument('-o', '--out-dir', default=OUT_DIR)
    args = parser.parse_args(argv)

    print('multi_object ships table2 at separation {:.1f}'.format(shipped_separation()))
    print('scanning {} at n={}\n'.format(
        ', '.join('{:.1f}'.format(s) for s in args.separations), args.trials))
    result = scan(separations=args.separations, trials=args.trials)
    print('cost per unit separation:  planner {:+.2f}   script {:+.2f}'.format(
        slope(result, 'planner') or float('nan'), slope(result, 'script') or float('nan')))
    write_result(result, args.out_dir)


if __name__ == '__main__':
    main()
