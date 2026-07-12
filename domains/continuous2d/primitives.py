from collections import namedtuple
import itertools
import numpy as np

# =====================================================================
# Data structures
#
# Bound to the PDDL objects produced/consumed by streams in stream.pddl.
# PDDL only ever treats them as opaque symbols (checked for equality),
# so these can be arbitrarily rich namedtuples.
# =====================================================================

BaseConf = namedtuple('BaseConf', ['x', 'y', 'theta'])
ArmConf = namedtuple('ArmConf', ['joints'])  # pure joint angles, frame-agnostic

Grasp = namedtuple('Grasp', ['dx', 'dy', 'dtheta'])

BaseTraj = namedtuple('BaseTraj', ['waypoints'])                       # list[BaseConf]
ArmTraj = namedtuple('ArmTraj', ['waypoints', 'held_object', 'held_grasp'])  # list[ArmConf]

Region = namedtuple('Region', ['lower', 'upper'])  # 2D axis-aligned box, e.g. table/shelf/box footprint

TAMPState = namedtuple('TAMPState', ['base_conf', 'arm_conf', 'holding', 'tray', 'object_poses'])
TAMPProblem = namedtuple('TAMPProblem', ['initial', 'regions', 'object_types', 'goal_regions', 'furniture'])

# =====================================================================
# Geometry constants
# =====================================================================

BASE_RADIUS = 0.22            # circular footprint approximation of the Waffle base

LINK_1 = 0.13
LINK_2 = 0.12
ARM_REACH_MAX = LINK_1 + LINK_2
ARM_REACH_MIN = abs(LINK_1 - LINK_2)
DOCK_MARGIN = 0.02

JOINT1_RANGE = (-np.pi, np.pi)
JOINT2_RANGE = (-2.5, 2.5)
JOINT3_RANGE = (-2.5, 2.5)

GRIPPER_RADIUS = 0.04

DEFAULT_OBJECT_SIZE = np.array([0.05, 0.05])
OBJECT_SIZES = {}   # OBJECT_SIZES[obj_type] = (w, h) -- populate per object/furniture type

GRASP_ANGLES = [0., np.pi / 2, np.pi, -np.pi / 2]

# ---------------------------------------------------------------------
# Costs
# ---------------------------------------------------------------------

MOVE_BASE_COST = 5.
COST_PER_BASE_DIST = 1.
COST_PER_ARM_DIST = 1.
UNNECESSARY_BASE_DIST_THRESHOLD = 0.05
UNNECESSARY_BASE_PENALTY = 50.
PICK_PLACE_COST = 2.
STOW_UNSTOW_COST = 0.5

# ---------------------------------------------------------------------
# RRT tuning (base motion planner -- see s-base-motion below)
# ---------------------------------------------------------------------

RRT_STEP_SIZE = 0.15
RRT_GOAL_BIAS = 0.10
RRT_MAX_ITERS = 2000
RRT_GOAL_TOLERANCE = 0.10
RRT_EDGE_CHECK_STEP = 0.05

DOCK_MAX_ATTEMPTS = 1000   # bounded so a genuinely unreachable object ends
                            # the generator instead of hanging forever


# =====================================================================
# Object geometry helpers
# =====================================================================

def get_object_size(obj_type):
    return np.array(OBJECT_SIZES.get(obj_type, DEFAULT_OBJECT_SIZE))


def get_object_box(obj_type, pose):
    """Axis-aligned bounding box for an object at a 2D pose (x, y).
    Rotation is ignored -- matches the project's stated 'simple
    rectangular collision geometry' simplification."""
    w, h = get_object_size(obj_type)
    center = np.array([pose[0], pose[1]])
    half = np.array([w, h]) / 2.
    return center - half, center + half


def boxes_overlap(box1, box2):
    lower1, upper1 = box1
    lower2, upper2 = box2
    return np.less_equal(lower1, upper2).all() and np.less_equal(lower2, upper1).all()


def circle_box_overlap(center, radius, box):
    lower, upper = box
    closest = np.clip(center, lower, upper)
    return np.linalg.norm(center - closest) <= radius


def base_point(bq):
    return np.array([bq.x, bq.y])


def compute_obstacle_boxes(furniture):
    """return the object box of furniture: tables, shelves, boxes"""
    return [get_object_box(obj_type, pose) for obj_type, pose in furniture]


def compute_default_bounds(regions, margin=1.0):
    """Fallback world bounds for RRT random sampling, derived from the
    union of all placement regions plus a margin."""
    lowers = np.array([r.lower for r in regions.values()])
    uppers = np.array([r.upper for r in regions.values()])
    lower = lowers.min(axis=0) - margin
    upper = uppers.max(axis=0) + margin
    return tuple(lower), tuple(upper)


# =====================================================================
# s-grasp : sample-grasp(object_type)
# =====================================================================

def get_grasp_gen():
    def gen(obj):
        for angle in itertools.cycle(GRASP_ANGLES):
            yield (Grasp(0., 0., angle),)
    return gen


# =====================================================================
# s-region / t-region : placement sampling + containment test
# =====================================================================

def sample_region_pose(obj_type, region):
    w, h = get_object_size(obj_type)
    lo = np.array(region.lower) + np.array([w, h]) / 2.
    hi = np.array(region.upper) - np.array([w, h]) / 2.
    if np.any(hi < lo):
        return None
    return float(np.random.uniform(lo[0], hi[0])), float(np.random.uniform(lo[1], hi[1]))


def get_region_gen(regions):
    def gen(obj, reg):
        region = regions[reg]
        # Ignores other already-placed *movable* objects on purpose --
        # rejection happens later via t-arm-cfree/t-base-cfree during
        # search. Furniture obstacles aren't relevant here since this
        # samples INSIDE a region's own surface, not through free space.
        while True:
            p = sample_region_pose(obj, region)
            if p is None:
                return
            yield (p,)
    return gen


def get_region_test(regions):
    def test(obj, pose, reg):
        region = regions[reg]
        lower, upper = get_object_box(obj, pose)
        return np.less_equal(region.lower, lower).all() and np.less_equal(upper, region.upper).all()
    return test


# =====================================================================
# s-dock : sample-base-dock(object_pose)
#
# FIX (issue #2): now filters candidates against static furniture
# obstacles so it stops proposing docking poses that plant the robot
# base inside a table/shelf. This is a pre-filter for efficiency --
# the real safety net is still move_base's CFree forall in domain.pddl.
# =====================================================================

def get_dock_gen(static_obstacles=None):
    obstacles = static_obstacles or []

    def gen(obj, pose):
        ox, oy = pose
        for _ in range(DOCK_MAX_ATTEMPTS):
            standoff = np.random.uniform(ARM_REACH_MIN + DOCK_MARGIN, ARM_REACH_MAX - DOCK_MARGIN)
            phi = np.random.uniform(-np.pi, np.pi)
            bx = ox - standoff * np.cos(phi)
            by = oy - standoff * np.sin(phi)
            bq = BaseConf(bx, by, phi)  # base faces toward the object
            if not any(circle_box_overlap(base_point(bq), BASE_RADIUS, box) for box in obstacles):
                yield (bq,)
        # DOCK_MAX_ATTEMPTS exhausted without a free candidate this
        # round -- end the generator rather than looping forever on an
        # object that's genuinely boxed in by obstacles.
    return gen


# =====================================================================
# s-ik : solve-ik(base_pose, object_pose, grasp)
# =====================================================================

def solve_ik(obj, pose, grasp, bq):
    target_world = np.array([pose[0], pose[1]])
    c, s = np.cos(-bq.theta), np.sin(-bq.theta)
    rot_to_base = np.array([[c, -s], [s, c]])
    local = rot_to_base.dot(target_world - np.array([bq.x, bq.y]))

    r = np.linalg.norm(local)
    if not (ARM_REACH_MIN <= r <= ARM_REACH_MAX):
        return None

    cos_j2 = (r ** 2 - LINK_1 ** 2 - LINK_2 ** 2) / (2 * LINK_1 * LINK_2)
    cos_j2 = np.clip(cos_j2, -1., 1.)
    j2 = np.arccos(cos_j2)  # elbow-down branch
    j1 = np.arctan2(local[1], local[0]) - np.arctan2(LINK_2 * np.sin(j2), LINK_1 + LINK_2 * np.cos(j2))
    j3 = grasp.dtheta - bq.theta - j1 - j2

    if not (JOINT1_RANGE[0] <= j1 <= JOINT1_RANGE[1]):
        return None
    if not (JOINT2_RANGE[0] <= j2 <= JOINT2_RANGE[1]):
        return None
    if not (JOINT3_RANGE[0] <= j3 <= JOINT3_RANGE[1]):
        return None

    return ArmConf(joints=(j1, j2, j3))


def get_ik_fn():
    def fn(obj, pose, grasp, bq):
        result = solve_ik(obj, pose, grasp, bq)
        if result is None:
            return None
        return (result,)
    return fn


def forward_kinematics(aq, bq):
    """World-frame end-effector position given an arm conf AND the base
    pose it's being executed from -- both now passed explicitly rather
    than assumed/baked into aq."""
    j1, j2, _j3 = aq.joints
    x = LINK_1 * np.cos(j1) + LINK_2 * np.cos(j1 + j2)
    y = LINK_1 * np.sin(j1) + LINK_2 * np.sin(j1 + j2)
    local = np.array([x, y])
    c, s = np.cos(bq.theta), np.sin(bq.theta)
    rot_to_world = np.array([[c, -s], [s, c]])
    return rot_to_world.dot(local) + np.array([bq.x, bq.y])


# =====================================================================
# s-base-motion : plan-base-motion(q_start, q_goal)
#
# FIX (issue #3): real RRT over the known static obstacle set, replacing
# the old straight-line interpolation. Returns None (no output) if no
# collision-free path is found within the iteration budget, which
# PDDLStream reads as "infeasible for this (bq1, bq2) pair" and moves on.
# =====================================================================

def interpolate_base(bq1, bq2, step=RRT_EDGE_CHECK_STEP):
    p1, p2 = np.array([bq1.x, bq1.y]), np.array([bq2.x, bq2.y])
    dist = np.linalg.norm(p2 - p1)
    n = max(2, int(np.ceil(dist / step)) + 1)
    xs = np.linspace(p1[0], p2[0], n)
    ys = np.linspace(p1[1], p2[1], n)
    thetas = np.linspace(bq1.theta, bq2.theta, n)
    return [BaseConf(x, y, t) for x, y, t in zip(xs, ys, thetas)]


def rrt_plan_base(bq1, bq2, obstacles, bounds,
                   step_size=RRT_STEP_SIZE, goal_bias=RRT_GOAL_BIAS,
                   max_iters=RRT_MAX_ITERS, goal_tolerance=RRT_GOAL_TOLERANCE):

    def is_free(bq):
        pt = base_point(bq)
        return not any(circle_box_overlap(pt, BASE_RADIUS, box) for box in obstacles)

    def edge_free(bq_a, bq_b):
        return all(is_free(wp) for wp in interpolate_base(bq_a, bq_b))

    if not is_free(bq1) or not is_free(bq2):
        return None

    lower_bound, upper_bound = np.array(bounds[0]), np.array(bounds[1])

    def sample_random():
        x, y = np.random.uniform(lower_bound, upper_bound)
        theta = np.random.uniform(-np.pi, np.pi)
        return BaseConf(x, y, theta)

    nodes = [bq1]
    parents = [None]

    for _ in range(max_iters):
        sample = bq2 if np.random.random() < goal_bias else sample_random()

        dists = [np.hypot(n.x - sample.x, n.y - sample.y) for n in nodes]
        nearest_idx = int(np.argmin(dists))
        nearest = nodes[nearest_idx]

        direction = np.array([sample.x - nearest.x, sample.y - nearest.y])
        dist = np.linalg.norm(direction)
        if dist < 1e-6:
            continue
        direction = direction / dist
        travel = min(step_size, dist)
        new_xy = np.array([nearest.x, nearest.y]) + direction * travel
        new_theta = np.arctan2(direction[1], direction[0])
        new_node = BaseConf(new_xy[0], new_xy[1], new_theta)

        if not is_free(new_node) or not edge_free(nearest, new_node):
            continue

        nodes.append(new_node)
        parents.append(nearest_idx)

        if np.hypot(new_node.x - bq2.x, new_node.y - bq2.y) <= goal_tolerance:
            if edge_free(new_node, bq2):
                nodes.append(bq2)
                parents.append(len(nodes) - 2)
                path_idx = len(nodes) - 1
                path = []
                while path_idx is not None:
                    path.append(nodes[path_idx])
                    path_idx = parents[path_idx]
                path.reverse()
                return path

    return None  # no path found within max_iters


def get_base_motion_fn(static_obstacles=None, world_bounds=None, regions=None):
    """Either pass world_bounds directly, or pass regions and let
    compute_default_bounds derive it."""
    obstacles = static_obstacles or []
    bounds = world_bounds or (compute_default_bounds(regions) if regions else ((-5., -5.), (5., 5.)))

    def fn(bq1, bq2):
        path = rrt_plan_base(bq1, bq2, obstacles, bounds)
        if path is None:
            return None
        return (BaseTraj(path),)
    return fn


# =====================================================================
# s-arm-motion-free / s-arm-motion-holding : plan-arm-motion(..., holding)
#
# Kept as straight-line joint-space interpolation (no RRT) -- the arm's
# reachable workspace is small and, once IK succeeds, largely
# self-collision-free; obstacle-avoidance against *movable* objects is
# still correctly enforced afterwards by t-arm-cfree.
# If your scene later has furniture actually intruding into the arm's
# reach envelope, this can be swapped for an RRT the same way s-base-motion was,
# using `obstacles` in local/base frame.
# =====================================================================

def interpolate_arm(aq1, aq2, steps=10):
    j1, j2 = np.array(aq1.joints), np.array(aq2.joints)
    return [ArmConf(tuple(j1 + t * (j2 - j1))) for t in np.linspace(0., 1., steps)]


def get_arm_motion_free_fn():
    def fn(bq, aq1, aq2):
        waypoints = interpolate_arm(aq1, aq2)
        return (ArmTraj(waypoints=waypoints, held_object=None, held_grasp=None),)
    return fn


def get_arm_motion_holding_fn():
    def fn(bq, aq1, aq2, obj, grasp):
        waypoints = interpolate_arm(aq1, aq2)
        return (ArmTraj(waypoints=waypoints, held_object=obj, held_grasp=grasp),)
    return fn


# =====================================================================
# t-base-cfree / t-arm-cfree : collision-free(...) test streams
# =====================================================================

def get_base_cfree_test():
    def test(bt, obj2, pose2):
        box2 = get_object_box(obj2, pose2)
        return not any(circle_box_overlap(base_point(bq), BASE_RADIUS, box2) for bq in bt.waypoints)
    return test


def get_arm_cfree_test():
    def test(bq, at, obj2, pose2):
        box2 = get_object_box(obj2, pose2)
        for aq in at.waypoints:
            ee_world = forward_kinematics(aq, bq)
            if at.held_object is not None:
                held_box = get_object_box(at.held_object, ee_world)
                if boxes_overlap(held_box, box2):
                    return False
            elif circle_box_overlap(ee_world, GRIPPER_RADIUS, box2):
                return False
        return True
    return test


# =====================================================================
# Cost functions: Dist, ArmDist, ExtraBaseCost
# =====================================================================

def get_base_distance_fn():
    def fn(bq1, bq2):
        d = np.hypot(bq2.x - bq1.x, bq2.y - bq1.y)
        return MOVE_BASE_COST + COST_PER_BASE_DIST * d
    return fn


def get_arm_distance_fn():
    def fn(aq1, aq2):
        j1, j2 = np.array(aq1.joints), np.array(aq2.joints)
        return COST_PER_ARM_DIST * np.linalg.norm(j2 - j1, ord=1)
    return fn


def get_extra_base_cost_fn():
    def fn(bq1, bq2):
        d = np.hypot(bq2.x - bq1.x, bq2.y - bq1.y)
        return UNNECESSARY_BASE_PENALTY if d < UNNECESSARY_BASE_DIST_THRESHOLD else 0.
    return fn




# =====================================================================
# Wiring dict: maps stream.pddl :stream / :function names directly to
# the Python callables above.
#
# static_obstacles: list of (lower, upper) boxes, e.g. from
#     compute_obstacle_boxes(furniture_list)
# world_bounds: (lower, upper) for RRT random sampling; falls back to
#     compute_default_bounds(regions) if not given.
# =====================================================================

def get_stream_map(regions, static_obstacles=None, world_bounds=None):
    return {
        's-grasp': get_grasp_gen(),
        's-region': get_region_gen(regions),
        't-region': get_region_test(regions),
        's-dock': get_dock_gen(static_obstacles),
        's-ik': get_ik_fn(),
        's-base-motion': get_base_motion_fn(static_obstacles, world_bounds, regions),
        's-arm-motion-free': get_arm_motion_free_fn(),
        's-arm-motion-holding': get_arm_motion_holding_fn(),
        't-base-cfree': get_base_cfree_test(),
        't-arm-cfree': get_arm_cfree_test(),
    }


def get_function_map():
    return {
        'Dist': get_base_distance_fn(),
        'ArmDist': get_arm_distance_fn(),
        'ExtraBaseCost': get_extra_base_cost_fn(),
    }
