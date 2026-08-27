"""Does the planner batch objects onto the tray, and how far does the base travel?

Answers, per scenario, the question the cost column cannot: whether the plan
carries several objects per trip (tray peak > 1) or makes one round trip per
object (tray peak == 1).  The scripted baseline is structurally tray-peak 1, so
this is the shape difference the cost gap is supposed to reflect.

Reads the shipped problem definitions -- no monkeypatching -- so it measures the
scenarios the sweeps measure.

Run it when nothing else is planning, and treat a low tray peak from a contended
run as an artefact rather than a result.  `adaptive` splits its budget between
search and sampling on wall-clock, and multi_object solves in ~1s, so under load
it accepts a worse skeleton: measured against 24 busy loops on 24 cores (while
multi_object still had its tables 4 apart), one seed in five dropped from tray
peak 3 to peak 2 and paid one extra table crossing, +5 cost.  Idle, all five
seeds report peak 3, agreeing with the n=20 sweeps.  The sweeps themselves are
safe from this -- sweep.py runs one cell at a time (Popen then wait).

For multi_object specifically, `evaluations/separation.py` is the systematic
version of this measurement: it sweeps the table separation and reports tray peak
and base travel for the planner and the scripted baseline at each one.
"""

from __future__ import print_function

import sys
from collections import Counter

import numpy as np

from domains.continuous2d.primitives import base_distance
from domains.continuous2d.run import get_problem_fn, solve_tamp

SCENARIOS = [
    ('multi_object', 'get_multi_object_problem'),
    ('at_work', 'get_at_work_problem'),
]
SEEDS = (0, 1, 2, 3, 4)


def shape_of(plan):
    """Tray peak, the co-riding groups, base travel, and move count."""
    on_tray, peak, travel, moves = set(), 0, 0., 0
    groups = []
    for action in plan:
        name, args = action.name, action.args
        if name == 'pick_and_stow':
            on_tray.add(args[1])
            if len(on_tray) > peak:
                peak = len(on_tray)
        elif name == 'unstow_and_place':
            if len(on_tray) > 1:
                groups.append(tuple(sorted(on_tray)))
            on_tray.discard(args[1])
        elif name == 'move_base':
            travel += base_distance(args[1], args[3])
            moves += 1
    return dict(peak=peak, travel=travel, moves=moves, groups=groups)


def main():
    for label, fn_name in SCENARIOS:
        problem_fn = get_problem_fn(fn_name)
        peaks = Counter()
        rows = []
        for seed in SEEDS:
            np.random.seed(seed)
            plan, cost, _ = solve_tamp(
                problem_fn(), algorithm='adaptive', merge_pick_and_stow=True,
                max_time=300, dump=False, verbose=False)
            if plan is None:
                rows.append((seed, None, None, None, None))
                continue
            shape = shape_of(plan)
            peaks[shape['peak']] += 1
            rows.append((seed, cost, len(plan), shape['peak'], shape))
        print('### {}'.format(label))
        for seed, cost, length, peak, shape in rows:
            if cost is None:
                print('  seed={}  NO PLAN'.format(seed))
                continue
            print('  seed={}  cost={:8.3f}  len={:2d}  tray_peak={}  '
                  'moves={:2d}  travel={:7.3f}  co-riding={}'.format(
                      seed, cost, length, peak, shape['moves'],
                      shape['travel'], shape['groups'] or '-'))
        print('  tray peak distribution over {} seeds: {}'.format(
            len(SEEDS), dict(peaks)))
        print()
        sys.stdout.flush()


if __name__ == '__main__':
    main()
