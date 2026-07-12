"""
domains/continuous2d/problems/pick_place.py

Simplest benchmark: move one object from table1 to table2.
A shelf is included as static furniture (blocks base motion only)
but placed off to the side so it doesn't force the RRT to detour --
good first target to get a plan before adding harder obstacles.
"""

from ..primitives import *


def get_pick_and_place_problem():
    objects = ['cube1']
    object_types = {'cube1': 'cube1'}

    OBJECT_SIZES['cube1'] = (0.05, 0.05)
    OBJECT_SIZES['shelf0'] = (0.30, 1.00)

    regions = {
        'table1': Region(lower=(0.70, -0.30), upper=(1.30, 0.30)),
        'table2': Region(lower=(-1.30, -0.30), upper=(-0.70, 0.30)),
    }

    furniture = [
        ('shelf0', (0.0, 1.4)),
    ]

    initial_object_poses = {
        'cube1': (1.0, 0.0),  # inside table1
    }

    initial = TAMPState(
        base_conf=BaseConf(0.0, -1.0, 0.0),
        arm_conf=ArmConf((0.0, 0.0, 0.0)),
        holding=None,
        tray={},
        object_poses=initial_object_poses,
    )

    goal_regions = {
        'cube1': 'table2',
    }

    return TAMPProblem(initial, regions, object_types, goal_regions, furniture)