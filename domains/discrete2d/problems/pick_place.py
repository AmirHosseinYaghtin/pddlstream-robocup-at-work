from ..primitives import *

def get_pick_and_place_problem():
    """
    Simplest benchmark:
    move one object from table to shelf
    """
    objects = ['obj0']

    table1_slot1 = make_pose('table1', 1)
    shelf1_slot1 = make_pose('shelf1', 1)

    initial_object_poses = {
        'obj0': table1_slot1,
    }

    initial = DiscreteTAMPState(
        conf=INITIAL_CONF,
        holding=None,
        object_poses=initial_object_poses
    )

    goal_poses = {
        'obj0': shelf1_slot1,
    }

    poses = [
        table1_slot1,
        shelf1_slot1,
    ]

    return DiscreteTAMPProblem(initial, poses, goal_poses, objects)
