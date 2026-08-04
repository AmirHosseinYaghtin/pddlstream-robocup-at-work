from ..primitives import *

def get_corridor_problem():
    object_types = {'cube1': 'cube'}
    OBJECT_SIZES['cube'] = (0.05, 0.05)

    # Walls extend past the RRT's sampling bounds (world bounds derived
    # from regions + margin=1.0 -> y in [-1.3, 1.3] here) so there is no
    # way to swing around the top/bottom -- passing through the gap is
    # the only route. Gap between inner edges stays 0.5m (>> base
    # diameter 0.44m) so it's passable, just mandatory.
    OBJECT_SIZES['wall_left'] = (0.10, 2.0)
    OBJECT_SIZES['wall_right'] = (0.10, 2.0)

    # Tables pushed further from the walls so the post-corridor dock
    # point isn't ALSO squeezed against a wall -- gives ~0.65m clearance,
    # comfortably more than base diameter + reach margin.
    regions = {
        'table1': Region(lower=(1.00, -0.30), upper=(1.60, 0.30)),
        'table2': Region(lower=(-1.60, -0.30), upper=(-1.00, 0.30)),
    }

    furniture = []
    for region_name, region in regions.items():
        center, size = region_as_furniture(region)
        OBJECT_SIZES[region_name] = size
        furniture.append((region_name, center))

    furniture += [
        ('wall_left',  (-0.30, 0.5)),
        ('wall_right', ( 0.30, -0.5)),
    ]

    # Object near table1's near (left) edge -- reachable from more than
    # one direction now, not pinned to a single sliver like before.
    initial_object_poses = {'cube1': (1.05, 0.0)}
    initial = TAMPState(BaseConf(0.0, -1.5, 0.0), ArmConf((0., 0., 0.)),
                         None, {}, initial_object_poses)
    goal_regions = {'cube1': 'table2'}
    return TAMPProblem(initial, regions, object_types, goal_regions, furniture)