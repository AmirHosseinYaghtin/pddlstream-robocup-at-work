"""
domains/continuous2d/viewer.py

Matplotlib-based visualizer for the continuous 2D RoboCup@Work TAMP domain.

Phase 1's Tkinter grid viewer assumed discrete (row, col) poses snapped to
cells. This domain has continuous (x, y, theta) base poses, continuous arm
joint angles, and RRT trajectories as lists of waypoints -- so this viewer
draws real geometry (circles, rectangles, line-segment arm links) and
animates move_base/pick/place through their actual BaseTraj/ArmTraj
waypoints instead of just snapping between two states.

Data structures used here (BaseConf, ArmConf, TAMPState, ...) come straight
from primitives.py, and the action tuples come straight from domain.pddl's
:parameters lists -- see apply_action/animate_action below for the mapping.
"""

from __future__ import print_function

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches

from pddlstream.utils import user_input

from .primitives import (
    LINK_1, LINK_2, BASE_RADIUS, GRIPPER_RADIUS,
    get_object_size, forward_kinematics, resolve_type,
)

# ---------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------

REGION_COLOR    = '#dbe9f6'
REGION_EDGE     = '#6a8fb0'
FURNITURE_COLOR = '#8d8d8d'
FURNITURE_EDGE  = '#4a4a4a'
BASE_COLOR      = '#2f7bd1'
BASE_EDGE       = '#123a63'
ARM_COLOR       = '#1c1c1c'
GRIPPER_COLOR   = '#e8483a'
TRAY_SLOT_COLOR = '#f4f1e8'
TRAY_SLOT_EDGE  = '#a89f8a'
TRAJ_COLOR      = '#9bbfe0'

OBJECT_PALETTE = [
    '#e6194B', '#3cb44b', '#ffe119', '#4363d8', '#f58231',
    '#911eb4', '#42d4f4', '#f032e6', '#bfef45', '#fabed4',
]

# Fixed screen-space layout for the (up to 3) tray slots -- purely visual,
# unrelated to the actual TraySlot PDDL objects beyond sharing slot names.
TRAY_SLOT_OFFSETS = {
    'slot0': (-0.12, 0.0),
    'slot1': (0.0, 0.0),
    'slot2': (0.12, 0.0),
}


def _rot(theta):
    c, s = np.cos(theta), np.sin(theta)
    return np.array([[c, -s], [s, c]])


def _object_colors(object_types):
    names = sorted(object_types)
    return {name: OBJECT_PALETTE[i % len(OBJECT_PALETTE)] for i, name in enumerate(names)}


# ---------------------------------------------------------------------
# Viewer
# ---------------------------------------------------------------------

class ContinuousTAMPViewer(object):
    """Renders a TAMPState: static regions/furniture (drawn once) plus
    dynamic objects, robot base+arm, and tray contents (redrawn every
    frame)."""

    def __init__(self, tamp_problem, figsize=(8, 9), title='Continuous 2D TAMP'):
        self.problem = tamp_problem
        self.colors = _object_colors(tamp_problem.object_types)

        plt.ion()
        self.fig, (self.ax, self.tray_ax) = plt.subplots(
            2, 1, figsize=figsize, gridspec_kw={'height_ratios': [7, 1]})
        try:
            self.fig.canvas.manager.set_window_title(title)
        except Exception:
            pass

        self.dynamic_artists = []
        self.tray_artists = []
        self._draw_static()

    # -------------------------------------------------------------
    # Static scene -- regions + furniture, drawn once
    # -------------------------------------------------------------

    def _draw_static(self):
        ax = self.ax
        ax.set_aspect('equal')
        ax.set_title('Workspace')

        lowers, uppers = [], []
        for region in self.problem.regions.values():
            lowers.append(np.array(region.lower))
            uppers.append(np.array(region.upper))
        for obj_type, pose in self.problem.furniture:
            w, h = get_object_size(obj_type)
            lowers.append(np.array(pose) - np.array([w, h]) / 2. - 1.0)
            uppers.append(np.array(pose) + np.array([w, h]) / 2. + 1.0)

        lower = np.min(lowers, axis=0) - 0.5
        upper = np.max(uppers, axis=0) + 0.5
        ax.set_xlim(lower[0], upper[0])
        ax.set_ylim(lower[1], upper[1])
        ax.grid(True, linestyle=':', alpha=0.4)

        for name, region in self.problem.regions.items():
            w = region.upper[0] - region.lower[0]
            h = region.upper[1] - region.lower[1]
            ax.add_patch(patches.Rectangle(
                region.lower, w, h,
                facecolor=REGION_COLOR, edgecolor=REGION_EDGE, linewidth=1.5, zorder=0))
            cx = (region.lower[0] + region.upper[0]) / 2.
            cy = region.upper[1] + 0.05
            ax.text(cx, cy, name, ha='center', va='bottom', fontsize=9, color=REGION_EDGE)

        for obj_type, pose in self.problem.furniture:
            w, h = get_object_size(obj_type)
            lower_c = (pose[0] - w / 2., pose[1] - h / 2.)
            ax.add_patch(patches.Rectangle(
                lower_c, w, h,
                facecolor=FURNITURE_COLOR, edgecolor=FURNITURE_EDGE,
                linewidth=1.5, zorder=1, hatch='//'))
            ax.text(pose[0], pose[1], obj_type, ha='center', va='center',
                     fontsize=8, color='white')

        self.tray_ax.set_title('Tray', fontsize=9)
        self.tray_ax.set_xlim(-0.25, 0.25)
        self.tray_ax.set_ylim(-0.05, 0.05)
        self.tray_ax.set_xticks([])
        self.tray_ax.set_yticks([])
        for _slot, (sx, _sy) in TRAY_SLOT_OFFSETS.items():
            self.tray_ax.add_patch(patches.Rectangle(
                (sx - 0.05, -0.03), 0.10, 0.06,
                facecolor=TRAY_SLOT_COLOR, edgecolor=TRAY_SLOT_EDGE, linewidth=1.))

    # -------------------------------------------------------------
    # Dynamic scene -- objects, robot base+arm, tray contents
    # -------------------------------------------------------------

    def _clear_dynamic(self):
        for artist in self.dynamic_artists:
            artist.remove()
        self.dynamic_artists = []
        for artist in self.tray_artists:
            artist.remove()
        self.tray_artists = []

    def draw_state(self, state, base_traj_preview=None, status=None):
        self._clear_dynamic()
        ax = self.ax

        if base_traj_preview is not None:
            xs = [bq.x for bq in base_traj_preview]
            ys = [bq.y for bq in base_traj_preview]
            line, = ax.plot(xs, ys, color=TRAJ_COLOR, linewidth=2,
                             linestyle='--', zorder=2)
            self.dynamic_artists.append(line)

        for obj, pose in state.object_poses.items():
            self.dynamic_artists.extend(self._draw_object(obj, pose))

        held = self._held_world_pose(state)
        if held is not None:
            obj, pose = held
            self.dynamic_artists.extend(self._draw_object(obj, pose, held=True))

        self.dynamic_artists.extend(self._draw_robot(state.base_conf, state.arm_conf))

        if status:
            txt = ax.text(0.02, 0.98, status, transform=ax.transAxes,
                           ha='left', va='top', fontsize=10,
                           bbox=dict(boxstyle='round', facecolor='white', alpha=0.85))
            self.dynamic_artists.append(txt)

        for obj, slot in state.tray.items():
            self.tray_artists.extend(self._draw_tray_object(obj, slot))

        self.fig.canvas.draw()
        plt.pause(0.001)

    def _draw_object(self, obj, pose, held=False):
        w, h = get_object_size(resolve_type(self.problem.object_types, obj))
        color = self.colors.get(obj, '#777777')
        lower_c = (pose[0] - w / 2., pose[1] - h / 2.)
        rect = patches.Rectangle(
            lower_c, w, h, facecolor=color, edgecolor='black', linewidth=1.2,
            zorder=5 if held else 3)
        self.ax.add_patch(rect)
        label = self.ax.text(pose[0], pose[1], obj, ha='center', va='center',
                              fontsize=7, color='white', zorder=6)
        return [rect, label]

    def _draw_tray_object(self, obj, slot):
        color = self.colors.get(obj, '#777777')
        sx, sy = TRAY_SLOT_OFFSETS.get(slot, (0.0, 0.0))
        rect = patches.Rectangle((sx - 0.04, sy - 0.02), 0.08, 0.04,
                                  facecolor=color, edgecolor='black', linewidth=1.0)
        self.tray_ax.add_patch(rect)
        label = self.tray_ax.text(sx, sy, obj, ha='center', va='center',
                                   fontsize=6, color='white')
        return [rect, label]

    def _draw_robot(self, bq, aq):
        artists = []
        R = _rot(bq.theta)

        base_circle = patches.Circle((bq.x, bq.y), BASE_RADIUS,
                                      facecolor=BASE_COLOR, edgecolor=BASE_EDGE,
                                      linewidth=1.5, zorder=4, alpha=0.9)
        self.ax.add_patch(base_circle)
        artists.append(base_circle)

        heading = R.dot(np.array([BASE_RADIUS, 0.]))
        heading_line, = self.ax.plot(
            [bq.x, bq.x + heading[0]], [bq.y, bq.y + heading[1]],
            color=BASE_EDGE, linewidth=2, zorder=4)
        artists.append(heading_line)

        # Same 2-link geometry as primitives.forward_kinematics, but we also
        # need the elbow (link1 endpoint) for drawing, not just the tip.
        j1, j2, _j3 = aq.joints
        elbow_local = np.array([LINK_1 * np.cos(j1), LINK_1 * np.sin(j1)])
        ee_local = elbow_local + np.array([LINK_2 * np.cos(j1 + j2), LINK_2 * np.sin(j1 + j2)])
        elbow_world = R.dot(elbow_local) + np.array([bq.x, bq.y])
        ee_world = R.dot(ee_local) + np.array([bq.x, bq.y])

        link1, = self.ax.plot([bq.x, elbow_world[0]], [bq.y, elbow_world[1]],
                               color=ARM_COLOR, linewidth=3, zorder=5, solid_capstyle='round')
        link2, = self.ax.plot([elbow_world[0], ee_world[0]], [elbow_world[1], ee_world[1]],
                               color=ARM_COLOR, linewidth=3, zorder=5, solid_capstyle='round')
        gripper = patches.Circle(tuple(ee_world), GRIPPER_RADIUS,
                                  facecolor=GRIPPER_COLOR, edgecolor='black',
                                  linewidth=1., zorder=6)
        self.ax.add_patch(gripper)
        artists += [link1, link2, gripper]
        return artists

    def _held_world_pose(self, state):
        """If the robot is gripping (not stowed) an object, return
        (obj, world_xy) so it renders following the gripper. Grasp dx/dy is
        ignored on purpose -- s-grasp (primitives.get_grasp_gen) only ever
        emits dx=dy=0, so the held object's center coincides with the
        end-effector position."""
        if state.holding is None:
            return None
        obj, _grasp = state.holding
        ee_world = forward_kinematics(state.arm_conf, state.base_conf)
        return obj, tuple(ee_world)

    def close(self):
        plt.close(self.fig)


# ---------------------------------------------------------------------
# Plan execution / animation
# ---------------------------------------------------------------------
#
# Action tuples come straight from domain.pddl's :parameters order:
#   move_base : (?r ?bq1 ?bt ?bq2)
#   pick      : (?r ?o ?p ?g ?bq ?aq1 ?aq2 ?at)
#   place     : (?r ?o ?p ?g ?bq ?aq1 ?aq2 ?at)
#   stow      : (?r ?o ?g ?s)
#   unstow    : (?r ?o ?g ?s)
#
# Note pick/place never assert a new AtArmConf in their :effect -- the
# precondition's (AtArmConf ?r ?aq1) is left untouched, which is the
# "abstracted retract back to aq1" described in domain.pddl's comments.
# So the arm's *logical* resting config after pick/place is aq1, not aq2 --
# we animate the aq1->aq2 reach and the aq2->aq1 retract, but the returned
# state always ends with arm_conf == aq1.

def animate_action(viewer, state, action, step_idx=None, step_pause=0.03):
    name, args = action
    status = 'Step {}: {}'.format(step_idx, name) if step_idx is not None else name

    if name == 'move_base':
        _r, _bq1, bt, bq2 = args
        for wp in bt.waypoints:
            frame_state = state._replace(base_conf=wp)
            viewer.draw_state(frame_state, base_traj_preview=bt.waypoints, status=status)
            plt.pause(step_pause)
        return state._replace(base_conf=bq2)

    if name == 'pick':
        _r, o, p, g, bq, aq1, aq2, at = args
        # reach out to the grasp config (object still resting at p)
        for wp in at.waypoints:
            viewer.draw_state(state._replace(base_conf=bq, arm_conf=wp), status=status)
            plt.pause(step_pause)
        # grasp: object leaves object_poses, enters the gripper
        object_poses = dict(state.object_poses)
        del object_poses[o]
        grasped_state = state._replace(
            base_conf=bq, arm_conf=aq2, holding=(o, g), object_poses=object_poses)
        viewer.draw_state(grasped_state, status=status)
        plt.pause(step_pause)
        # retract back to aq1, carrying the object
        for wp in reversed(at.waypoints):
            viewer.draw_state(grasped_state._replace(arm_conf=wp), status=status)
            plt.pause(step_pause)
        return grasped_state._replace(arm_conf=aq1)

    if name == 'place':
        _r, o, p, g, bq, aq1, aq2, at = args
        # reach out to the place config, still holding
        for wp in at.waypoints:
            viewer.draw_state(state._replace(base_conf=bq, arm_conf=wp), status=status)
            plt.pause(step_pause)
        # release: object enters object_poses at p, gripper empties
        object_poses = dict(state.object_poses)
        object_poses[o] = p
        placed_state = state._replace(
            base_conf=bq, arm_conf=aq2, holding=None, object_poses=object_poses)
        viewer.draw_state(placed_state, status=status)
        plt.pause(step_pause)
        # retract back to aq1, empty-handed
        for wp in reversed(at.waypoints):
            viewer.draw_state(placed_state._replace(arm_conf=wp), status=status)
            plt.pause(step_pause)
        return placed_state._replace(arm_conf=aq1)

    if name == 'stow':
        _r, o, _g, s = args
        tray = dict(state.tray)
        tray[o] = s
        new_state = state._replace(holding=None, tray=tray)
        viewer.draw_state(new_state, status=status)
        return new_state

    if name == 'unstow':
        _r, o, g, s = args
        tray = dict(state.tray)
        del tray[o]
        new_state = state._replace(holding=(o, g), tray=tray)
        viewer.draw_state(new_state, status=status)
        return new_state

    raise ValueError('Unknown action: {}'.format(name))


def apply_plan(tamp_problem, plan, step_pause=0.03, interactive=True):
    """Entry point mirroring Phase 1's apply_plan(tamp_problem, plan)."""
    viewer = ContinuousTAMPViewer(tamp_problem)
    state = tamp_problem.initial
    viewer.draw_state(state, status='Initial state')

    if interactive:
        user_input('Start?')

    for step_idx, action in enumerate(plan):
        name, args = action
        print('{}) {} {}'.format(step_idx, name, args[1:]))
        state = animate_action(viewer, state, action, step_idx=step_idx, step_pause=step_pause)
        if interactive:
            user_input('Next step?')

    print('Finished.')
    if interactive:
        user_input('Close viewer?')
    viewer.close()
    return state