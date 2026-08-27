#!/usr/bin/env python
"""Run a single evaluation cell and append one JSON line per completed trial.

Launched by sweep.py as a subprocess -- not meant for direct use.

Two reasons this is a separate process rather than a loop inside sweep.py:

1. `--algorithm incremental` on continuous2d does not hang in PDDLStream's own
   loop, where `max_time` is checked, but inside Fast Downward's *translator*
   (`build_model.compute_model`, reached from `instantiate_task`). A run with
   max_time=90 was still going at 200s. The only way to bound it is externally,
   so the parent puts this process in its own process group and SIGKILLs the
   whole group -- FD's binary is a grandchild and has to die with it.
2. A killed cell must not lose the trials that already finished, so every
   result is written and flushed the moment it exists. The parent counts the
   lines to resume.

On SIGUSR1 this process dumps a stack trace to stderr (faulthandler). The
parent sends that immediately before killing a stalled cell, which is how the
sweep can say *where* a cell hung instead of only that it did.
"""

from __future__ import print_function

import argparse
import faulthandler
import json
import os
import signal
import sys

from evaluations.metrics import run_trial
from evaluations.run import _finite
from evaluations.scenarios import ALL_SCENARIOS, ALGORITHM, MAX_TIME, build_solver


def _find_scenario(phase, label):
    for scenario in ALL_SCENARIOS:
        if scenario.phase == phase and scenario.label == label:
            return scenario
    raise ValueError('No scenario {!r} in phase {!r}'.format(label, phase))


def _count_lines(path):
    if not os.path.exists(path):
        return 0
    with open(path) as fh:
        return sum(1 for line in fh if line.strip())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', required=True)
    parser.add_argument('--scenario', required=True)
    parser.add_argument('--algorithm', default=ALGORITHM)
    parser.add_argument('--planner', default=None,
                        help="FD search config key; omitted = the domain's own default")
    parser.add_argument('--trials', type=int, default=1)
    parser.add_argument('--max-time', type=float, default=MAX_TIME)
    parser.add_argument('--out', required=True,
                        help='JSONL path -- one line appended per completed trial')
    args = parser.parse_args()

    # Lets the parent ask "where are you stuck?" before it kills us.
    faulthandler.enable(file=sys.stderr)
    if hasattr(signal, 'SIGUSR1'):
        faulthandler.register(signal.SIGUSR1, file=sys.stderr, chain=False)

    scenario = _find_scenario(args.phase, args.scenario)
    solver = build_solver(scenario,
                          algorithm=args.algorithm,
                          max_time=args.max_time,
                          planner=args.planner)

    completed = _count_lines(args.out)
    if completed >= args.trials:
        print('SKIP have={} want={}'.format(completed, args.trials))
        return

    out_dir = os.path.dirname(os.path.abspath(args.out))
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir)

    with open(args.out, 'a') as out_fh:
        for trial_idx in range(completed, args.trials):
            try:
                metrics, solution = run_trial(solver, quiet=True)
                record = {key: _finite(value) for key, value in metrics.items()}
                record['has_plan'] = solution[0] is not None
                record['error'] = None
            except Exception as exc:  # noqa: BLE001 -- recorded, not swallowed
                # A Python-level failure is a different outcome from a hang
                # (which kills us before we get here) and from an honest
                # "no plan found", so it gets its own field.
                record = {
                    'solved': False,
                    'timeout': False,
                    'has_plan': False,
                    'error': '{}: {}'.format(type(exc).__name__, exc),
                }
            record['trial'] = trial_idx
            out_fh.write(json.dumps(record) + '\n')
            out_fh.flush()
            os.fsync(out_fh.fileno())
            print('TRIAL {} solved={} error={}'.format(
                trial_idx, record.get('solved'), record.get('error')))
            sys.stdout.flush()


if __name__ == '__main__':
    main()
