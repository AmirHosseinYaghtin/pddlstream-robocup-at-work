"""The scenario registry for the evaluation.

Two phases, each ordered least- to most-complex -- the plots put the scenarios
on the x axis in exactly this order, so the ordering is the experiment's
independent variable and is documented per scenario below.

Every scenario is solved through its domain's own `run.solve_tamp`, i.e. the
same code path as `python -m domains.<phase>.run ...`, so the numbers here
describe the planner as actually shipped and not a parallel re-implementation.
"""

from __future__ import print_function

from collections import namedtuple

from domains.continuous2d import run as continuous_run
from domains.discrete2d import run as discrete_run

# label:      x-axis / table label
# phase:      'discrete2d' | 'continuous2d'
# problem:    the problem function name accepted by -p
# complexity: one-line note on *why* it sits where it sits in the ordering
# solve:      () -> Solution; closes over the phase's solve_tamp
Scenario = namedtuple('Scenario', ['label', 'phase', 'problem', 'complexity', 'solve'])

DISCRETE = 'discrete2d'
CONTINUOUS = 'continuous2d'

# The user's evaluation fixes these two knobs across the whole sweep.
ALGORITHM = 'adaptive'
MERGE_ACTIONS = True  # every continuous scenario runs as if given -ma

# Cap per trial. The CLI default for continuous2d is 300s; a timed-out trial is
# recorded (timeout=True, cost=None) rather than aborting the sweep.
MAX_TIME = 300


def _discrete_solver(problem, algorithm=ALGORITHM, max_time=MAX_TIME, planner=None):
    problem_fn = discrete_run.get_problem_fn(problem)
    extra = {} if planner is None else {'planner': planner}

    def solve():
        # Rebuilt per trial: the TAMP problem objects are cheap and this keeps
        # trials independent (no state carried over from the previous solve).
        return discrete_run.solve_tamp(
            problem_fn(),
            algorithm=algorithm,
            max_time=max_time,
            verbose=False,
            **extra
        )
    return solve


def _continuous_solver(problem, algorithm=ALGORITHM, max_time=MAX_TIME,
                       merge_pick_and_stow=MERGE_ACTIONS, planner=None):
    problem_fn = continuous_run.get_problem_fn(problem)
    extra = {} if planner is None else {'planner': planner}

    def solve():
        return continuous_run.solve_tamp(
            problem_fn(),
            algorithm=algorithm,
            merge_pick_and_stow=merge_pick_and_stow,
            max_time=max_time,
            verbose=False,
            dump=False,
            **extra
        )
    return solve


def build_solver(scenario, algorithm=ALGORITHM, max_time=MAX_TIME, planner=None,
                 merge_pick_and_stow=MERGE_ACTIONS):
    """Rebuild a scenario's solver with the sweep knobs overridden.

    `Scenario.solve` is frozen at the headline configuration (adaptive, -ma,
    FD's default planner). The comparison sweeps need the same problem under a
    different algorithm or a different Fast Downward search configuration, so
    they go through here rather than through the baked-in closure.

    `planner=None` means "do not pass the keyword at all", so the default path
    is byte-identical to what the CLI does -- it does not hard-code FD's
    current DEFAULT_PLANNER and so cannot drift from it.
    """
    if scenario.phase == DISCRETE:
        return _discrete_solver(scenario.problem, algorithm=algorithm,
                                max_time=max_time, planner=planner)
    return _continuous_solver(scenario.problem, algorithm=algorithm,
                              max_time=max_time, planner=planner,
                              merge_pick_and_stow=merge_pick_and_stow)


def find_scenario(phase, label):
    for scenario in scenarios_for(phase):
        if scenario.label == label:
            return scenario
    raise ValueError('No scenario {!r} in phase {!r}'.format(label, phase))


# --------------------------------------------------------------------------
# Phase 1 -- discrete2d: symbolic poses, no geometry, no collisions.
# Ordering rationale: objects, then poses, then goal coupling.
# blocked_retrieval is deliberately omitted (per the evaluation spec).
# --------------------------------------------------------------------------

DISCRETE_SCENARIOS = [
    Scenario(
        label='pick_place',
        phase=DISCRETE,
        problem='get_pick_and_place_problem',
        complexity='1 object, 2 poses, 1 goal -- the minimal transfer',
        solve=_discrete_solver('get_pick_and_place_problem'),
    ),
    Scenario(
        label='object_transport',
        phase=DISCRETE,
        problem='get_object_transport_problem',
        complexity='1 object, 4 poses, 1 goal -- same plan shape, larger pose set',
        solve=_discrete_solver('get_object_transport_problem'),
    ),
    Scenario(
        label='rearrangement',
        phase=DISCRETE,
        problem='get_rearrangement_problem',
        complexity='2 objects, 5 poses, 2 goals -- a swap, needs a buffer pose',
        solve=_discrete_solver('get_rearrangement_problem'),
    ),
]

# --------------------------------------------------------------------------
# Phase 2 -- continuous2d: continuous poses, IK, base/arm motion, collisions.
# All four run with merged pick/stow actions (-ma).
# --------------------------------------------------------------------------

CONTINUOUS_SCENARIOS = [
    Scenario(
        label='pick_place',
        phase=CONTINUOUS,
        problem='get_pick_and_place_problem',
        complexity='1 cube, 2 tables, shelf as furniture -- minimal continuous transfer',
        solve=_continuous_solver('get_pick_and_place_problem'),
    ),
    Scenario(
        label='corridor',
        phase=CONTINUOUS,
        problem='get_corridor_problem',
        complexity='1 cube, but base motion must thread a narrow gap (RRT pressure)',
        solve=_continuous_solver('get_corridor_problem'),
    ),
    Scenario(
        label='multi_object',
        phase=CONTINUOUS,
        problem='get_multi_object_problem',
        complexity='3 cubes to a distant table -- rewards tray batching',
        solve=_continuous_solver('get_multi_object_problem'),
    ),
    Scenario(
        label='at_work',
        phase=CONTINUOUS,
        problem='get_at_work_problem',
        complexity='5 parts, 4 workstations + precision table -- full @Work task',
        solve=_continuous_solver('get_at_work_problem'),
    ),
]

PHASES = [
    (DISCRETE, DISCRETE_SCENARIOS),
    (CONTINUOUS, CONTINUOUS_SCENARIOS),
]

ALL_SCENARIOS = DISCRETE_SCENARIOS + CONTINUOUS_SCENARIOS


def scenarios_for(phase=None):
    if phase is None:
        return list(ALL_SCENARIOS)
    for name, scenarios in PHASES:
        if name == phase:
            return list(scenarios)
    raise ValueError('Unknown phase: {}. Options: {}'.format(
        phase, [name for name, _ in PHASES]))
