from pddlstream.utils import user_input
from .primitives import DiscreteTAMPState

try:
    from Tkinter import Tk, Canvas, Toplevel
except ImportError:
    from tkinter import Tk, Canvas, Toplevel

# --------------------------------------------------
# Basic viewer config
# --------------------------------------------------

MAX_ROWS = 3
MAX_COLS = 10

COLORS = ['red', 'orange', 'yellow', 'green',
          'blue', 'violet', 'white', 'black']

# --------------------------------------------------
# Utility: symbolic pose -> (row, col)
# --------------------------------------------------

# Global coordinate cache populated dynamically before rendering
POSE_TO_GRID_MAP = {}


def pose_to_grid(pose):
    """
    Converts symbolic pose into grid coordinates (row, col)
    using a dynamically built mapping to prevent overlaps.
    """
    if pose in POSE_TO_GRID_MAP:
        return POSE_TO_GRID_MAP[pose]

    # Fallback to the original logic if not dynamically populated
    try:
        surface, slot = pose.split('_slot')
        col = int(slot) - 1
        row = 1 if surface.startswith('shelf') else 0
        return row, col
    except Exception:
        return 0, 0


def conf_to_pose(conf):
    """
    Converts configuration name to pose name.

    q_table1_slot1 -> table1_slot1
    q_home -> None
    """
    if conf == 'q_home':
        return None
    return conf[2:]  # remove "q_"


class DiscreteTAMPViewer(object):
    def __init__(self, rows, cols, width=600, height=350, side=25,
                 block_buffer=10, title='Discrete TAMP Environment', background='tan', draw_fingers=False):
        assert (rows <= MAX_ROWS)
        assert (cols <= MAX_COLS)

        self.tk = Tk()
        self.tk.withdraw()
        self.top = Toplevel(self.tk)
        self.top.wm_title(title)
        self.top.protocol('WM_DELETE_WINDOW', self.top.destroy)

        self.width = width
        self.height = height
        self.rows = rows
        self.cols = cols
        self.canvas = Canvas(self.top, width=self.width, height=self.height, background=background)
        self.canvas.pack()
        self.side = side
        self.block_buffer = block_buffer
        self.draw_fingers = draw_fingers
        self.cells = {}
        self.robot = []

        # Calculate base offsets
        table_width = self.cols * (self.side + 2 * self.block_buffer) + 2 * self.block_buffer
        table_height = self.rows * (self.side + 2 * self.block_buffer) + 2 * self.block_buffer
        border_buffer = 50

        self.table_x1 = self.width / 2 - table_width / 2
        self.table_y1 = self.height - table_height - border_buffer

        self.draw_environment()

    def update(self):
        self.tk.update_idletasks()
        self.tk.update()

    def transform_r(self, r):
        row_spacing = self.side + 2 * self.block_buffer + 60
        offset_y = 80
        return self.table_y1 + r * row_spacing + 2 * self.block_buffer + self.side / 2 - offset_y

    def transform_c(self, c):
        col_spacing = self.side + 2 * self.block_buffer + 10
        return self.table_x1 + c * col_spacing + 2 * self.block_buffer + self.side / 2

    def draw_environment(self):
        self.environment = []

        # Group columns by surface name
        surfaces = {}
        for pose, (r, c) in POSE_TO_GRID_MAP.items():
            try:
                surf_name = pose.split('_slot')[0]
            except:
                surf_name = "unknown"
            if surf_name not in surfaces:
                surfaces[surf_name] = {'row': r, 'cols': []}
            surfaces[surf_name]['cols'].append(c)

        cell_width = (self.side + 2 * self.block_buffer + 10)
        surface_height = cell_width + 10

        for surf_name, info in surfaces.items():
            r = info['row']
            cols = info['cols']

            min_c = min(cols)
            max_c = max(cols)

            y_center = self.transform_r(r)

            x_center_min = self.transform_c(min_c)
            x_center_max = self.transform_c(max_c)

            # Dimensions of the specific surface
            x_start = x_center_min - cell_width / 2
            x_end = x_center_max + cell_width / 2
            y_start = y_center - surface_height / 2
            y_end = y_center + surface_height / 2

            color = 'lightgrey' if r == 0 else 'saddlebrown'

            self.environment.append(
                self.canvas.create_rectangle(x_start, y_start, x_end, y_end,
                                             fill=color, outline='black', width=2)
            )

            self.environment.append(
                self.canvas.create_text((x_start + x_end) / 2, y_end + 10, text=surf_name,
                                        font=('Arial', 10, 'bold'), anchor='n')
            )

            # Draw slots
            pose_radius = 3
            for c in cols:
                x = self.transform_c(c)
                self.environment.append(
                    self.canvas.create_oval(x - pose_radius, y_center - pose_radius,
                                            x + pose_radius, y_center + pose_radius,
                                            fill='black')
                )
                self.environment.append(
                    self.canvas.create_text(x, y_center + 18, text=f"S{c - min_c + 1}",
                                            font=('Arial', 7), fill='black')
                )
    def draw_robot(self, r, c, color='yellow'):
        grasp_buffer = 3
        finger_length = self.side + grasp_buffer
        finger_width = 10
        gripper_length = 20
        if self.draw_fingers:
            gripper_width = self.side + 2 * self.block_buffer + finger_width
        else:
            gripper_width = self.side
        stem_length = 50
        stem_width = 20

        x = self.transform_c(c)
        y = self.transform_r(r) - self.side / 2 - gripper_length / 2 - grasp_buffer
        finger_x = gripper_width / 2 - finger_width / 2

        self.robot = [
            self.canvas.create_rectangle(x - stem_width / 2., y - stem_length,
                                         x + stem_width / 2., y,
                                         fill=color, outline='black', width=2),
            self.canvas.create_rectangle(x - gripper_width / 2., y - gripper_length / 2.,
                                         x + gripper_width / 2., y + gripper_length / 2.,
                                         fill=color, outline='black', width=2),
        ]
        if self.draw_fingers:
            self.robot += [
                self.canvas.create_rectangle(x + finger_x - finger_width / 2., y,
                                             x + finger_x + finger_width / 2., y + finger_length,
                                             fill=color, outline='black', width=2),
                self.canvas.create_rectangle(x - finger_x - finger_width / 2., y,
                                             x - finger_x + finger_width / 2., y + finger_length,
                                             fill=color, outline='black', width=2),
            ]

    def draw_block(self, r, c, name='', color='red'):
        x = self.transform_c(c)
        y = self.transform_r(r)
        self.cells[(x, y)] = [
            self.canvas.create_rectangle(x - self.side / 2., y - self.side / 2.,
                                         x + self.side / 2., y + self.side / 2.,
                                         fill=color, outline='black', width=2),
            self.canvas.create_text(x, y, text=name, font=('Arial', 8, 'bold')),
        ]

    def clear(self):
        self.canvas.delete('all')


def draw_state(viewer, state, colors):
    viewer.clear()
    viewer.draw_environment()

    # Robot pose from configuration
    robot_pose = conf_to_pose(state.conf)

    if robot_pose is not None:
        r, c = pose_to_grid(robot_pose)
        viewer.draw_robot(r, c)
    else:
        viewer.draw_robot(0, 0)

    # Draw objects on the table
    for obj, obj_pose in state.object_poses.items():
        r, c = pose_to_grid(obj_pose)
        viewer.draw_block(r, c, name=obj, color=colors[obj])

    # Draw held object at robot location
    if state.holding is not None and robot_pose is not None:
        r, c = pose_to_grid(robot_pose)
        viewer.draw_block(r, c, name=state.holding, color=colors[state.holding])

    viewer.update()


def apply_action(state, action):
    conf, holding, object_poses = state
    object_poses = dict(object_poses)

    name, args = action

    if name == 'move':
        _, new_conf = args
        conf = new_conf

    elif name == 'pick':
        obj, pose, _ = args
        holding = obj
        del object_poses[obj]

    elif name == 'place':
        obj, pose, _ = args
        holding = None
        object_poses[obj] = pose

    else:
        raise ValueError(name)

    return DiscreteTAMPState(conf, holding, object_poses)


def apply_plan(tamp_problem, plan):
    global POSE_TO_GRID_MAP

    # Dynamically layout table and shelf poses sequentially
    table_poses = sorted([p for p in tamp_problem.poses if 'table' in p])
    shelf_poses = sorted([p for p in tamp_problem.poses if 'shelf' in p])

    POSE_TO_GRID_MAP = {}
    for idx, p in enumerate(table_poses):
        POSE_TO_GRID_MAP[p] = (0, idx)
    for idx, p in enumerate(shelf_poses):
        POSE_TO_GRID_MAP[p] = (1, idx)

    colors = dict(zip(tamp_problem.objects, COLORS))

    max_cols = max(len(table_poses), len(shelf_poses), 1)

    viewer = DiscreteTAMPViewer(
        rows=2,
        cols=max_cols,
        title='Discrete TAMP Simulation'
    )

    state = tamp_problem.initial

    draw_state(viewer, state, colors)

    for action in plan:
        user_input('Next step?')
        state = apply_action(state, action)
        draw_state(viewer, state, colors)

    user_input('Finished.')
