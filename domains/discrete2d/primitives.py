from collections import namedtuple

# ---------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------

DiscreteTAMPState = namedtuple('DiscreteTAMPState', ['conf', 'holding', 'object_poses'])
DiscreteTAMPProblem = namedtuple('DiscreteTAMPProblem', ['initial', 'poses', 'goal_poses', 'objects'])


# ---------------------------------------------------------------------
# Symbol templates
# ---------------------------------------------------------------------

OBJECT_TEMPLATE = 'obj{}'
POSE_TEMPLATE = '{}_slot{}'
CONF_TEMPLATE = 'q_{}_slot{}'

INITIAL_CONF = 'q_home'


# ---------------------------------------------------------------------
# Pose / configuration constructors
# ---------------------------------------------------------------------

def make_pose(region, slot):
    """
    Creates a symbolic pose name.

    Example:
        make_pose('table1', 1) -> 'table1_slot1'
        make_pose('shelf1', 2) -> 'shelf1_slot2'
    """
    return POSE_TEMPLATE.format(region, slot)


def make_conf(region, slot):
    """
    Creates a symbolic configuration name associated with a pose.

    Example:
        make_conf('table1', 1) -> 'q_table1_slot1'
        make_conf('shelf1', 2) -> 'q_shelf1_slot2'
    """
    return CONF_TEMPLATE.format(region, slot)


def pose_to_conf(pose):
    """
    Deterministic symbolic inverse kinematics mapping.

    Example:
        'table1_slot1' -> 'q_table1_slot1'
    """
    return f'q_{pose}'


# ---------------------------------------------------------------------
# Streams support
# ---------------------------------------------------------------------

def get_pose_gen(problem):
    """
    Returns a generator function for all available poses in the problem.

    This is used by the sample-pose stream.
    """
    def gen():
        for pose in problem.poses:
            yield (pose,)
    return gen


def get_ik_fn(problem):
    """
    Returns a symbolic inverse kinematics function.

    In Phase 1 this is just a lookup:
        pose -> corresponding symbolic configuration

    In Phase 2 this can be replaced by a real IK / reachability sampler.
    """
    valid_poses = set(problem.poses)
    valid_poses.update(problem.initial.object_poses.values())
    valid_poses.update(problem.goal_poses.values())

    def fn(pose):
        if pose not in valid_poses:
            return
        yield (pose_to_conf(pose),)
    return fn

