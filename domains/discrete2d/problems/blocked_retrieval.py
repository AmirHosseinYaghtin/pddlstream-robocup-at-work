from ..primitives import *

def get_blocked_retrieval_problem():
    """
    Simplified blocked retrieval benchmark.

    Note:
    In the current minimal domain there is no explicit collision/blocking
    predicate, so "blocked retrieval" is represented as a rearrangement-style
    task that requires moving one object before another can reach its goal.
    A stronger blocked model can be added later with occupancy constraints.
    """
    objects = ['obj0', 'obj1']

    shelf1_slot1 = make_pose('shelf1', 1)
    shelf1_slot2 = make_pose('shelf1', 2)
    table1_slot1 = make_pose('table1', 1)
    table1_slot2 = make_pose('table1', 2)

    initial_object_poses = {
        'obj0': shelf1_slot1,
        'obj1': shelf1_slot2,
    }

    initial = DiscreteTAMPState(
        conf=INITIAL_CONF,
        holding=None,
        object_poses=initial_object_poses
    )

    goal_poses = {
        'obj0': table1_slot1,
        'obj1': table1_slot2,
    }

    poses = [
        shelf1_slot1,
        shelf1_slot2,
        table1_slot1,
        table1_slot2,
    ]

    return DiscreteTAMPProblem(initial, poses, goal_poses, objects)