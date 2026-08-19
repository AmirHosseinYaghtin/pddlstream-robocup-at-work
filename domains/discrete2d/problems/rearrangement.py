from ..primitives import *

def get_rearrangement_problem():
    """
    Two-object rearrangement benchmark.
    """
    objects = ['obj0', 'obj1']

    table1_slot1 = make_pose('table1', 1)
    table1_slot2 = make_pose('table1', 2)
    shelf1_slot1 = make_pose('shelf1', 1)
    shelf1_slot2 = make_pose('shelf1', 2)
    shelf2_slot1 = make_pose('shelf2', 1)

    initial_object_poses = {
        'obj0': table1_slot1,
        'obj1': shelf1_slot1,
    }

    initial = DiscreteTAMPState(
        conf=INITIAL_CONF,
        holding=None,
        object_poses=initial_object_poses
    )

    goal_poses = {
        'obj0': shelf1_slot1,
        'obj1': table1_slot1,
    }

    poses = [
        table1_slot1,
        table1_slot2,
        shelf1_slot1,
        shelf1_slot2,
        shelf2_slot1,
    ]

    return DiscreteTAMPProblem(initial, poses, goal_poses, objects)