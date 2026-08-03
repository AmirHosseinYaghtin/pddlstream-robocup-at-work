"""
domains/continuous2d/problems/pick_place.py

Simplest benchmark: move one object from table1 to table2.
A shelf is included as static furniture (blocks base motion only)
but placed off to the side so it doesn't force the RRT to detour --
good first target to get a plan before adding harder obstacles.
"""

from ..primitives import *


def get_multi_object_problem():
    objects = ['cube1', 'cube2', 'cube3']
    object_types = {'cube1': 'cube', 'cube2': 'cube', 'cube3': 'cube'}
    OBJECT_SIZES['cube'] = (0.05, 0.05)
    OBJECT_SIZES['shelf0'] = (0.30, 1.00)

    regions = {
        'table1': Region(lower=(0.70, -0.30), upper=(1.30, 0.30)),
        'table2': Region(lower=(-1.30, -0.30), upper=(-0.70, 0.30)),
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