from ..primitives import *

def get_corridor_problem():
    objects = ['cube']
    object_types = {'cube1': 'cube'}
    OBJECT_SIZES['cube'] = (0.05, 0.05)
    OBJECT_SIZES['wall_left'] = (0.10, 2.0)
    OBJECT_SIZES['wall_right'] = (0.10, 2.0)

    furniture = []
    regions = {
        'table1': Region(lower=(0.70, -0.30), upper=(1.30, 0.30)),
        'table2': Region(lower=(-1.30, -0.30), upper=(-0.70, 0.30)),
    }


    for region_name, region_object in regions.items():
        # print('region', region_name, region_object)
        region_center, region_size = region_as_furniture(regions[region_name])
        OBJECT_SIZES[region_name] = region_size
        furniture.append((region_name, region_center))

    furniture += [
        ('wall_left',  (-0.30, 0.0)),
        ('wall_right', ( 0.30, 0.0)),   # gap = 0.6m, base diameter = 0.44m
    ]

    initial_object_poses = {'cube1': (0.8, 0.0)}
    initial = TAMPState(BaseConf(0.0, -1.5, 0.0), ArmConf((0., 0., 0.)),
                         None, {}, initial_object_poses)
    goal_regions = {'cube1': 'table2'}
    return TAMPProblem(initial, regions, object_types, goal_regions, furniture)