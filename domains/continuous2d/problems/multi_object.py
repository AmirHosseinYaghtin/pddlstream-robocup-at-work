"""
domains/continuous2d/problems/multi_object.py

Three cubes from table1 to table2, with the two tables far enough apart that
crossing between them dominates the travel cost.  The tray has 3 slots, so the
cheap plan is to pick all three cubes (short hops along table1), cross once,
and place all three -- and the expensive plan with the same action count is one
round trip per cube.  Both are 12 actions, so this scenario isolates whether a
planner finds the cheaper *routing*, not the shorter plan.  That makes it the
scenario where the planner separates from a fixed-order state machine, which
cannot batch: see the measured separation trend on `regions` below.

A shelf is included as static furniture (blocks base motion only) but placed
off to the side so it doesn't force the RRT to detour.
"""

from ..primitives import *


def get_multi_object_problem():
    object_types = {'cube1': 'cube', 'cube2': 'cube', 'cube3': 'cube'}
    OBJECT_SIZES['cube'] = (0.05, 0.05)
    OBJECT_SIZES['shelf0'] = (0.30, 1.00)

    regions = {
        'table1': Region(lower=(0.70, -0.30), upper=(1.30, 0.30)),
        # The separation is load-bearing, so resist moving table2 closer to make
        # a run finish faster.  This scenario exists to test whether the planner
        # discovers tray batching -- pick all three cubes, cross once, place all
        # three -- and batching only pays through the COST_PER_BASE_DIST term.
        # Every plan here has 6 move_base actions whatever the routing, so the
        # flat MOVE_BASE_COST = 5 cancels out and the travel term is the entire
        # signal.
        #
        # `python -m evaluations.separation` sweeps this distance and writes
        # results/sweeps/separation_table.md.  Measured over 2/4/6/8/10/12 at
        # n=10, the planner reaches tray peak 3 at every separation and its cost
        # grows ~1.0 per unit; the scripted baseline is structurally tray peak 1
        # and grows ~5.1 per unit, because it pays one round trip per cube.  So
        # the gap is a slope (~4 cost units per unit of separation), and any
        # single separation is just a point on it:
        #
        #   sep 2.0   64 vs  68     6% -- inside trial noise
        #   sep 8.0   69 vs  97    29% -- shipped
        #   sep 12.0  75 vs 118    36%
        #
        # 8.0 puts the gap well clear of noise while two workstations 8 m apart
        # stays plausible for an @Work arena, and coverage is 10/10 for both
        # planner and script at every separation above, so widening costs no
        # solve rate.  compute_default_bounds() derives the RRT sampling bounds
        # from the regions, so the arena grows with the tables automatically.
        'table2': Region(lower=(-7.30, -0.30), upper=(-6.70, 0.30)),
        # 'table2': Region(lower=(-3.30, -0.30), upper=(-2.70, 0.30)),  # sep 4.0
        # 'table2': Region(lower=(-1.30, -0.30), upper=(-0.70, 0.30)),  # sep 2.0
    }

    table1_center, table1_size = region_as_furniture(regions['table1'])
    table2_center, table2_size = region_as_furniture(regions['table2'])
    OBJECT_SIZES['table1'] = table1_size
    OBJECT_SIZES['table2'] = table2_size

    furniture = [
        ('shelf0', (0.0, 1.4)),
        ('table1', table1_center),
        ('table2', table2_center),
    ]

    initial_object_poses = {
        'cube1': (0.75, 0.20), 'cube2': (0.75, 0.0), 'cube3': (0.75, -0.20),
    }

    initial = TAMPState(
        base_conf=BaseConf(0.0, -1.0, 0.0),
        arm_conf=ArmConf((0.0, 0.0, 0.0)),
        holding=None,
        tray={},
        object_poses=initial_object_poses,
    )

    goal_regions = {'cube1': 'table2', 'cube2': 'table2', 'cube3': 'table2'}

    return TAMPProblem(initial, regions, object_types, goal_regions, furniture)