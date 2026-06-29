#!/usr/bin/env python

from __future__ import print_function

import os
import numpy as np

from pddlstream.algorithms.meta import solve, create_parser

from primitives import DiscreteTAMPState
from primitives import get_pose_gen, get_ik_fn
from problems.pick_place import get_pick_and_place_problem

from pddlstream.language.constants import And, Equal, TOTAL_COST, print_solution, PDDLProblem
from pddlstream.language.generator import from_gen_fn, from_fn, from_test
from pddlstream.utils import user_input, read, INF


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

def main():
    parser = create_parser()
    #parser.add_argument('-p', '--problem', default='blocked', help='The name of the problem to solve')
    args = parser.parse_args()
    print('Arguments:', args)

    problem_fn = get_pick_and_place_problem
    tamp_problem = problem_fn()
    print(tamp_problem)

    pddlstream_problem = pddlstream_from_tamp(tamp_problem)
    #solution = solve_serialized(pddlstream_problem, planner='max-astar', unit_costs=args.unit)
    solution = solve(pddlstream_problem, algorithm=args.algorithm, unit_costs=args.unit, debug=False,
                     #complexity_step=INF, max_complexity=0,
                    )

    print_solution(solution)
    plan, cost, evaluations = solution
    if plan is None:
        return


if __name__ == '__main__':
    main()
