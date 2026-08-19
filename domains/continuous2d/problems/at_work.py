"""
domains/continuous2d/problems/robocup_at_work.py

Loosely modeled on the RoboCup@Work Basic Manipulation Test (BMT) /
Basic Transportation Test (BTT): a mobile manipulator drives between
several fixed workstations (WS) arranged around an arena, picks up
objects of different classes, and sorts them onto the correct
destination workstations. A precision placement table (PPT) stands
in for the cavity tray used in the real competition for high-accuracy
placement, and a barrier sits between the source and destination
clusters so the base can't take a straight-line shortcut -- forcing
the RRT to route around it, like the arena dividers/obstacles used
in the real BTT/BNT tests.
"""

from ..primitives import *


def get_at_work_problem():
    object_types = {
        'f20_20_1': 'small_part',
        'f20_20_2': 'small_part',
        's40_40_1': 'large_part',
        's40_40_2': 'large_part',
        'bearing1': 'precision_part',
    }
    OBJECT_SIZES['small_part'] = (0.04, 0.04)
    OBJECT_SIZES['large_part'] = (0.08, 0.08)
    OBJECT_SIZES['precision_part'] = (0.03, 0.03)
    # Narrowed from (0.10, 1.60): that only left a 0.1m gap to
    # ws1/ws2/ws3/ws4 (which start at y=+-0.9), too narrow for the
    # base to route around -- this leaves a ~0.4m corridor each side.
    OBJECT_SIZES['barrier0'] = (0.10, 1.00)
    OBJECT_SIZES['shelf0'] = (0.30, 0.60)

    # Arena layout: source workstations (WS1, WS2) on one side, sorted
    # destination workstations (WS3 for small parts, WS4 for large
    # parts) and a precision placement table (PPT) on the other side,
    # with a barrier splitting the arena down the middle -- the base
    # has to go around it to cross from source to destination side.
    regions = {
        'ws1': Region(lower=(0.70, 0.90), upper=(1.30, 1.50)),   # source
        'ws2': Region(lower=(0.70, -1.50), upper=(1.30, -0.90)),  # source
        'ws3': Region(lower=(-1.30, 0.90), upper=(-0.70, 1.50)),  # dest: small_part
        'ws4': Region(lower=(-1.30, -1.50), upper=(-0.70, -0.90)),  # dest: large_part
        'ppt': Region(lower=(-1.30, -0.30), upper=(-0.70, 0.30)),  # dest: precision_part
    }

    ws1_center, ws1_size = region_as_furniture(regions['ws1'])
    ws2_center, ws2_size = region_as_furniture(regions['ws2'])
    ws3_center, ws3_size = region_as_furniture(regions['ws3'])
    ws4_center, ws4_size = region_as_furniture(regions['ws4'])
    ppt_center, ppt_size = region_as_furniture(regions['ppt'])
    OBJECT_SIZES['ws1'] = ws1_size
    OBJECT_SIZES['ws2'] = ws2_size
    OBJECT_SIZES['ws3'] = ws3_size
    OBJECT_SIZES['ws4'] = ws4_size
    OBJECT_SIZES['ppt'] = ppt_size

    furniture = [
        ('ws1', ws1_center),
        ('ws2', ws2_center),
        ('ws3', ws3_center),
        ('ws4', ws4_center),
        ('ppt', ppt_center),
        # Barrier splitting the arena between source and destination
        # sides -- base motion only, tall enough that the arm can't
        # reach over it either.
        ('barrier0', (0.0, 0.0)),
        # Shelf tucked in the corner, out of the direct route, same
        # role as in pick_place.py: present but not forcing a detour.
        ('shelf0', (0.0, -2.2)),
    ]

    # Two objects per source WS, spread out within the region so they
    # don't overlap each other's footprints.
    initial_object_poses = {
        'f20_20_1': (0.85, 1.20), 'f20_20_2': (1.15, 1.20),
        's40_40_1': (0.85, -1.20), 's40_40_2': (1.15, -1.20),
        'bearing1': (0.90, 1.35),
    }

    initial = TAMPState(
        base_conf=BaseConf(0.0, 1.0, 0.0),
        arm_conf=ArmConf((0.0, 0.0, 0.0)),
        holding=None,
        tray={},
        object_poses=initial_object_poses,
    )

    goal_regions = {
        'f20_20_1': 'ws3', 'f20_20_2': 'ws3',
        's40_40_1': 'ws4', 's40_40_2': 'ws4',
        'bearing1': 'ppt',
    }

    return TAMPProblem(initial, regions, object_types, goal_regions, furniture)