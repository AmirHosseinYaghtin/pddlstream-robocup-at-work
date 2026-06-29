from ..primitives import *

def get_object_transport_problem():
    """
    Transport one object across multiple possible symbolic poses.
    """
    objects = ['obj0']

    table1_slot1 = make_pose('table1', 1)
    table2_slot1 = make_pose('table2', 1)
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
        table2_slot1,
        shelf1_slot1,
    ]

    return DiscreteTAMPProblem(initial, poses, goal_poses, objects)