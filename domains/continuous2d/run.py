#!/usr/bin/env python

from __future__ import print_function

import numpy as np

from pddlstream.algorithms.meta import solve, create_parser
from pddlstream.language.constants import And, Equal, TOTAL_COST, PDDLProblem, print_solution
from pddlstream.language.generator import from_gen_fn, from_fn, from_test
from pddlstream.language.stream import StreamInfo
from pddlstream.language.function import FunctionInfo
from pddlstream.language.external import defer_shared
from pddlstream.utils import read, get_file_path, INF


from pddlstream.algorithms.constraints import PlanConstraints, WILD


from .primitives import (
    compute_obstacle_boxes,
    compute_default_bounds,
    get_grasp_gen,
    get_region_gen,
    get_region_test,
    get_dock_gen,
    get_ik_fn,
    get_base_motion_fn,
    get_arm_motion_free_fn,
    get_arm_motion_holding_fn,
    get_base_cfree_test,
    get_arm_cfree_test,
    get_base_distance_fn,
    get_arm_distance_fn,
    get_extra_base_cost_fn,
    PICK_PLACE_COST,
    STOW_UNSTOW_COST,
)

from .problems.pick_place import get_pick_and_place_problem
from .problems.narrow_corridor import get_corridor_problem
from .problems.multi_object import get_multi_object_problem

PROBLEMS = [
    get_pick_and_place_problem,
    get_corridor_problem,
    get_multi_object_problem,
]

ROBOT = 'robot0'  # single-robot domain for now; matches problems/pick_place.py

##################################################

def create_problem(tamp_problem):
    initial = tamp_problem.initial
    assert initial.holding is None  # no problem file should start mid-grasp

    init = [
        Equal((TOTAL_COST,), 0),
        Equal(('Cost',), PICK_PLACE_COST),  # flat per-action cost; see stream.pddl note
        Equal(('StowCost',), STOW_UNSTOW_COST),
        ('Robot', ROBOT),
        ('BaseConf', initial.base_conf),
        ('ArmConf', initial.arm_conf),
        ('AtBaseConf', ROBOT, initial.base_conf),
        ('AtArmConf', ROBOT, initial.arm_conf),
        ('HandEmpty', ROBOT),
        ('CanMoveBase', ROBOT),
    ]

    init += [('Object', o) for o in tamp_problem.object_types]
    init += [('Region', r) for r in tamp_problem.regions]

    for o, p in initial.object_poses.items():
        init += [('Pose', o, p), ('AtPose', o, p)]

    for obj_type, pose in tamp_problem.furniture:
        init += [('Furniture', obj_type), ('Pose', obj_type, pose), ('AtPose', obj_type, pose)]

    # Tray: 3 fixed slots, occupied per initial.tray, free otherwise.
    all_slots = ('slot0', 'slot1', 'slot2')
    occupied = {}
    for o, s in initial.tray.items():
        occupied[s] = o
        init += [('TraySlot', s), ('OnTray', ROBOT, o, s)]
    for s in all_slots:
        if s not in occupied:
            init += [('TraySlot', s), ('TraySlotFree', ROBOT, s)]

    goal = And(*[
        ('In', o, r) for o, r in tamp_problem.goal_regions.items()
    ])

    return init, goal


def pddlstream_from_tamp(tamp_problem, collisions=True, default_world_bound_margin=1.0, merge_pick_and_stow=True):
    domain_pddl = read(get_file_path(__file__, 'domain_merged.pddl')) if merge_pick_and_stow else read(get_file_path(__file__, 'domain.pddl'))
    stream_pddl = read(get_file_path(__file__, 'stream.pddl'))
    constant_map = {}

    regions = tamp_problem.regions
    static_obstacles = compute_obstacle_boxes(tamp_problem.furniture)
    world_bounds = compute_default_bounds(regions, default_world_bound_margin)

    stream_map = {
        's-grasp': from_gen_fn(get_grasp_gen()),
        's-region': from_gen_fn(get_region_gen(regions, tamp_problem.object_types)),
        't-region': from_test(get_region_test(regions, tamp_problem.object_types)),
        's-dock': from_gen_fn(get_dock_gen(static_obstacles)),
        's-ik': from_fn(get_ik_fn()),
        's-base-motion': from_fn(get_base_motion_fn(static_obstacles, world_bounds, regions)),
        's-arm-motion-free': from_fn(get_arm_motion_free_fn()),
        's-arm-motion-holding': from_fn(get_arm_motion_holding_fn()),
        't-base-cfree': from_test(get_base_cfree_test(tamp_problem.object_types) if collisions else (lambda *args: True)),
        't-arm-cfree': from_test(get_arm_cfree_test(tamp_problem.object_types) if collisions else (lambda *args: True)),

        # :function entries are raw callables, not wrapped -- pddlstream
        # calls them directly to score a cost, same as official
        # continuous_tamp/run.py's 'dist': distance_fn.
        'Dist': get_base_distance_fn(),
        'ArmDist': get_arm_distance_fn(),
        'ExtraBaseCost': get_extra_base_cost_fn(),
    }

    init, goal = create_problem(tamp_problem)

    return PDDLProblem(domain_pddl, constant_map, stream_pddl, stream_map, init, goal)

##################################################

def initialize(parser):
    parser.add_argument('-c', '--cfree', action='store_true', help='Disables collision checking')
    parser.add_argument('-p', '--problem', default='get_pick_and_place_problem', help='The name of the problem to solve')
    parser.add_argument('-wm', '--worldmargin', default=1.0, type=float, help='Default world bound margin')

    parser.add_argument('-s', '--skeleton', action='store_true', help='Use hard skeleton')
    parser.add_argument('-ma', '--mergeactions', action='store_true', help='Merge pick and stow actions')

    args = parser.parse_args()
    print('Arguments:', args)

    problem_from_name = {fn.__name__: fn for fn in PROBLEMS}
    if args.problem not in problem_from_name:
        raise ValueError('Unknown problem: {}. Options: {}'.format(
            args.problem, list(problem_from_name)))
    print('Problem:', args.problem)
    problem_fn = problem_from_name[args.problem]
    tamp_problem = problem_fn()
    print(tamp_problem)
    return tamp_problem, args


def dump_pddlstream(pddlstream_problem):
    print('Init:', pddlstream_problem.init)
    print('Goal:', pddlstream_problem.goal)


WILD = '*'
TIGHT_SKELETON = [
    ('move_base', ['robot0', '?q0', WILD, '?q1']),
    ('pick', ['robot0', 'cube1', '?p1', '?g1', '?q1', '?aq_home', '?aq_grasp1', WILD]),
    ('stow', ['robot0', 'cube1', '?g1', 'slot1']),
    ('move_base', ['robot0', '?q1', WILD, '?q2']),
    ('pick', ['robot0', 'cube2', '?p2', '?g2', '?q2', '?aq_home', '?aq_grasp2', WILD]),
    ('stow', ['robot0', 'cube2', '?g2', 'slot2']),
    ('move_base', ['robot0', '?q2', WILD, '?q3']),
    ('pick', ['robot0', 'cube3', '?p3', '?g3', '?q3', '?aq_home', '?aq_grasp3', WILD]),

    ('move_base', ['robot0', '?q3', WILD, '?q4']),
    ('place', ['robot0', 'cube3', '?p_dest3', '?g3', '?q4', '?aq_home', '?aq_place3', WILD]),

    ('move_base', ['robot0', '?q4', WILD, '?q5']),
    ('unstow', ['robot0', 'cube2', '?g2', 'slot2']),
    ('place', ['robot0', 'cube2', '?p_dest2', '?g2', '?q5', '?aq_home', '?aq_place2', WILD]),

    ('move_base', ['robot0', '?q5', WILD, '?q6']),
    ('unstow', ['robot0', 'cube1', '?g1', 'slot1']),
    ('place', ['robot0', 'cube1', '?p_dest1', '?g1', '?q6', '?aq_home', '?aq_place1', WILD]),
]

def main():
    parser = create_parser()
    tamp_problem, args = initialize(parser)

    defer_fn = defer_shared
    stream_info = {
        's-region': StreamInfo(defer_fn=defer_fn),
        's-grasp': StreamInfo(defer_fn=defer_fn),
        's-dock': StreamInfo(defer_fn=defer_fn),
        's-ik': StreamInfo(defer_fn=defer_fn),
        's-base-motion': StreamInfo(defer_fn=defer_fn),
        's-arm-motion-free': StreamInfo(defer_fn=defer_fn),
        's-arm-motion-holding': StreamInfo(defer_fn=defer_fn),
        't-base-cfree': StreamInfo(eager=False, verbose=False),
        't-arm-cfree': StreamInfo(eager=False, verbose=False),
        't-region': StreamInfo(eager=True, p_success=0),
        'Dist': FunctionInfo(eager=False, defer_fn=defer_fn),
        'ArmDist': FunctionInfo(eager=False, defer_fn=defer_fn),
        'ExtraBaseCost': FunctionInfo(eager=False, defer_fn=defer_fn),
    }

    skeletons = [TIGHT_SKELETON] if args.skeleton else None
    constraints = PlanConstraints(skeletons=skeletons,
                                  # skeletons=[],
                                  # skeletons=[skeleton, []],
                                  exact=True,
                                  max_cost=INF)

    pddlstream_problem = pddlstream_from_tamp(tamp_problem, collisions=not args.cfree, default_world_bound_margin=args.worldmargin, merge_pick_and_stow=args.mergeactions)
    dump_pddlstream(pddlstream_problem)

    solution = solve(
        pddlstream_problem,
        algorithm=args.algorithm,
        constraints=constraints,
        # planner='max-astar',
        unit_costs=args.unit,
        max_time=150,
        success_cost=INF,
        debug=False,
        verbose=False,
    )

    print_solution(solution)
    plan, cost, evaluations = solution
    if plan is None:
        return



    from .viewer import apply_plan
    apply_plan(tamp_problem, plan)


if __name__ == '__main__':
    main()