#!/usr/bin/env python

from __future__ import print_function

import os
import numpy as np

from pddlstream.algorithms.meta import solve, create_parser, DEFAULT_ALGORITHM

from .primitives import DiscreteTAMPState
from .primitives import get_pose_gen, get_ik_fn

from .problems.pick_place import get_pick_and_place_problem
from .problems.object_transport import get_object_transport_problem
from .problems.rearrangement import get_rearrangement_problem
from .problems.blocked_retrieval import get_blocked_retrieval_problem

from pddlstream.language.constants import And, Equal, TOTAL_COST, print_solution, PDDLProblem
from pddlstream.language.generator import from_gen_fn, from_fn, from_test
from pddlstream.utils import user_input, read, INF

# NOTE: .viewer is imported lazily inside main() -- it pulls in Tkinter, which
# is not available (or wanted) when this module is imported by a headless
# caller such as the evaluation harness.

# Ordered from least to most complex; the evaluation harness relies on this
# order, and -p accepts any of these function names.
PROBLEMS = [
    get_pick_and_place_problem,
    get_object_transport_problem,
    get_rearrangement_problem,
    get_blocked_retrieval_problem,
]

# Kept as the default so that the historical invocation
#   python -m domains.discrete2d.run --algorithm focused
# still solves exactly the problem it used to (it was hardcoded here).
DEFAULT_PROBLEM = 'get_rearrangement_problem'


def get_problem_fn(name):
    problem_from_name = {fn.__name__: fn for fn in PROBLEMS}
    if name not in problem_from_name:
        raise ValueError('Unknown problem: {}. Options: {}'.format(
            name, list(problem_from_name)))
    return problem_from_name[name]


def pddlstream_from_tamp(tamp_problem):
    initial = tamp_problem.initial
    assert(initial.holding is None)

    known_poses = tamp_problem.poses

    directory = os.path.dirname(os.path.abspath(__file__))
    domain_pddl = read(os.path.join(directory, 'domain.pddl'))
    stream_pddl = read(os.path.join(directory, 'stream.pddl'))


    constant_map = {}

    init = [
        #Type(q100, 'conf'),
        ('CanMove',),
        ('Conf', initial.conf),
        ('AtConf', initial.conf),
        ('HandEmpty',),
        Equal((TOTAL_COST,), 0)]

    init += [('Object', o) for o in tamp_problem.objects]

    for p in known_poses:
        if p not in initial.object_poses.values():
            init.append(('Clear', p))
        init.append(('Pose', p))

    # object placements
    init += [('AtPose', o, pos) for o, pos in initial.object_poses.items()]

    goal = And(*[
        ('AtPose', b, p) for b, p in tamp_problem.goal_poses.items()
    ])

    pose_gen = get_pose_gen(tamp_problem)
    ik_fn = get_ik_fn(tamp_problem)

    stream_map = {
        'sample-pose': from_gen_fn(pose_gen),
        'inverse-kinematics': from_fn(ik_fn),
    }

    return PDDLProblem(domain_pddl, constant_map, stream_pddl, stream_map, init, goal)

##################################################

def initialize(parser):
    parser.add_argument('-p', '--problem', default=DEFAULT_PROBLEM,
                        help='The name of the problem to solve')

    args = parser.parse_args()
    print('Arguments:', args)

    problem_fn = get_problem_fn(args.problem)
    print('Problem:', args.problem)
    tamp_problem = problem_fn()
    print(tamp_problem)
    return tamp_problem, args


def solve_tamp(tamp_problem, algorithm=DEFAULT_ALGORITHM, unit_costs=False,
               max_time=INF, verbose=True, debug=False, **kwargs):
    """Build the PDDLStream problem and solve it. No viewer, no I/O prompts.

    This is the whole of main() minus argument parsing and visualization, so
    the CLI and the evaluation harness go through byte-identical planning code.
    The defaults reproduce what the CLI used to pass (max_time and verbose were
    left at solve()'s own defaults of INF and True).
    """
    pddlstream_problem = pddlstream_from_tamp(tamp_problem)
    #solution = solve_serialized(pddlstream_problem, planner='max-astar', unit_costs=unit_costs)
    return solve(pddlstream_problem, algorithm=algorithm, unit_costs=unit_costs,
                 max_time=max_time, verbose=verbose, debug=debug,
                 #complexity_step=INF, max_complexity=0,
                 **kwargs)


def main():
    parser = create_parser()
    tamp_problem, args = initialize(parser)

    solution = solve_tamp(tamp_problem, algorithm=args.algorithm, unit_costs=args.unit)

    print_solution(solution)
    plan, cost, evaluations = solution
    if plan is None:
        return

    from .viewer import apply_plan
    apply_plan(tamp_problem, plan)

if __name__ == '__main__':
    main()
