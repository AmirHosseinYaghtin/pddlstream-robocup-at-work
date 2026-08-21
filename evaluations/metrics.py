"""Capture the planner's own summary metrics out of a solve() call.

Both `solve_incremental` and `solve_abstract` end with

    summary = store.export_summary()
    summary.update({...})                       # algorithm-specific extras
    print('Summary: {}'.format(str_from_object(summary, ndigits=3)))

and then throw the dict away (there is even a `# TODO: return the summary` on
that line). Rather than scrape the printed line -- which is rounded to three
digits and would break the moment the format string changes -- we temporarily
wrap `SolutionStore.export_summary` and keep a reference to the dict it
returned. The algorithm's own `summary.update(...)` mutates *that same object*,
so by the time solve() returns we hold every key at full float precision,
including the algorithm-specific `iterations` / `complexity` / `skeletons`.

Nothing under pddlstream/ is modified; the patch is undone in a finally block.
"""

from __future__ import print_function

import contextlib
import os
import sys
import time

from pddlstream.algorithms.common import SolutionStore
from pddlstream.language.constants import FunctionAction, StreamAction, get_length, is_plan

# The metrics reported by every algorithm (SolutionStore.export_summary).
BASE_METRICS = [
    'solved',
    'solutions',
    'cost',
    'length',
    'evaluations',
    'search_time',
    'sample_time',
    'run_time',
    'timeout',
]

# Added by solve_incremental and solve_abstract (focused/binding/adaptive).
ALGORITHM_METRICS = ['iterations', 'complexity']

# Added by solve_abstract only.
FOCUSED_METRICS = ['skeletons']

ALL_METRICS = BASE_METRICS + ALGORITHM_METRICS + FOCUSED_METRICS


@contextlib.contextmanager
def capture_summary():
    """Yield a dict that is filled in with the planner's summary metrics.

    The yielded dict is empty until the wrapped solve() call returns.
    """
    captured = {}
    original = SolutionStore.export_summary

    def export_summary(self):
        summary = original(self)
        # Return `captured` itself, not a copy: the caller mutates the dict we
        # hand back to add 'iterations'/'complexity'/'skeletons', and we want
        # those updates to land where we can see them.
        captured.clear()
        captured.update(summary)
        return captured

    SolutionStore.export_summary = export_summary
    try:
        yield captured
    finally:
        SolutionStore.export_summary = original


@contextlib.contextmanager
def suppress_stdout(enabled=True):
    """Silence the planner's per-iteration chatter.

    Even with verbose=False the algorithms print an Iteration/Stream plan block
    per iteration. For a multi-trial sweep that is thousands of lines of noise,
    and the write syscalls themselves show up in run_time.
    """
    if not enabled:
        yield
        return
    saved = sys.stdout
    with open(os.devnull, 'w') as devnull:
        sys.stdout = devnull
        try:
            yield
        finally:
            sys.stdout = saved


def plan_length(solution):
    """The number of real actions in a solution, or None if unsolved.

    Deliberately NOT taken from the summary's 'length'. export_summary computes
    get_length(store.best_plan), and for the focused/adaptive algorithms
    best_plan is an OptPlan -- a two-field namedtuple ('action_plan',
    'preimage_facts') -- so len() of it is the field count, i.e. the literal
    constant 2, no matter how long the plan is. (Confirmed against
    print_solution, which reports 12 for a discrete2d rearrangement plan while
    the Summary line for the same run reports 2.)

    The solution returned by solve() has already been reverted to a flat action
    list, so we measure it there and discount the deferred stream/function
    actions exactly as print_solution does.
    """
    plan = solution[0]
    if not is_plan(plan) or plan is None:
        return None
    deferred = sum(1 for action in plan
                   if isinstance(action, (StreamAction, FunctionAction)))
    return get_length(plan) - deferred


def run_trial(solve_fn, quiet=True):
    """Call solve_fn() once and return (metrics_dict, solution).

    metrics_dict always contains every key in ALL_METRICS; keys the algorithm
    did not report are None. `wall_time` is measured out here as an independent
    check on the planner's self-reported `run_time`.
    """
    with capture_summary() as captured:
        start = time.time()
        with suppress_stdout(quiet):
            solution = solve_fn()
        wall_time = time.time() - start

    metrics = {key: captured.get(key) for key in ALL_METRICS}
    metrics['wall_time'] = wall_time
    # Overwrite the planner's broken 'length' -- see plan_length().
    metrics['length'] = plan_length(solution)
    return metrics, solution
