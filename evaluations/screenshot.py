"""Render still frames of a solved plan, for the README and the write-up.

`domains/continuous2d/viewer.py` animates a plan interactively, which is the
right thing at a desk and useless in a document.  This module drives the same
viewer headlessly (Agg), snapshots it at chosen steps, and lays the snapshots
out side by side:

    python -m evaluations.screenshot                    # multi_object, 3 frames
    python -m evaluations.screenshot -p get_at_work_problem

Frames are chosen by what the state *is*, not by step index, so the montage
survives the planner returning a different-but-equivalent routing:

    initial state -> the fullest the tray ever gets -> goal reached

That middle frame is the point of the figure.  The scripted baseline in
`evaluations/baseline.py` is structurally tray-peak 1, so "three cubes on the
tray at once" is the plan shape behind the cost gap that
`evaluations/separation.py` measures.

The viewer calls plt.ion()/plt.pause(), which Agg warns about once per call and
otherwise ignores; the warning is filtered rather than worked around, so this
keeps going through the shipped animate_action instead of re-deriving the state
transitions here.
"""

from __future__ import print_function

import argparse
import os
import warnings

import matplotlib

matplotlib.use('Agg')  # before any pyplot import, including the viewer's

import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import numpy as np

from domains.continuous2d.run import get_problem_fn, solve_tamp
from domains.continuous2d.viewer import ContinuousTAMPViewer, animate_action

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'docs')
DEFAULT_PROBLEM = 'get_multi_object_problem'
SEEDS = (0, 1, 2, 3, 4)
# The tray the domain actually models: three slots, fixed in
# domains/continuous2d/run.py (`all_slots`).  Nothing can batch more than this,
# so it caps what counts as a well-batched plan for at_work's five parts.
TRAY_SLOTS = 3
PANEL_WIDTH = 9.0
DPI = 140

warnings.filterwarnings('ignore', message='FigureCanvasAgg is non-interactive')


def _capture(viewer, path):
    viewer.fig.savefig(path, dpi=DPI, bbox_inches='tight',
                       facecolor=viewer.fig.get_facecolor())


def _fit_figure(viewer, panel_width=PANEL_WIDTH):
    """Resize the viewer's figure to the arena's aspect ratio.

    The viewer's default 8x9 suits a roughly square scene.  multi_object's tables
    are 8 apart on x and the arena is ~4 tall, and the workspace axes is
    aspect-equal, so at 8x9 the scene collapses into a strip with two thirds of
    the panel empty.  Reading the limits back off the axes reuses the viewer's own
    bounds computation rather than re-deriving it from regions and furniture.
    """
    (x0, x1), (y0, y1) = viewer.ax.get_xlim(), viewer.ax.get_ylim()
    # The workspace axes holds 7 of the 8 gridspec rows; the tray strip and the
    # titles take the rest.
    workspace_height = panel_width * (y1 - y0) / float(x1 - x0)
    viewer.fig.set_size_inches(panel_width, workspace_height * 8. / 7. + 0.6)
    # The montage puts a caption over every panel, so the viewer's own
    # 'Workspace' title would be a second heading saying less.  The tray strip
    # keeps its title -- it is the one panel whose contents need naming.
    viewer.ax.set_title('')
    # Wider gap than the default: at this aspect the tray title lands on the
    # workspace's tick labels.
    viewer.fig.subplots_adjust(hspace=0.28)


def walk_plan(viewer, initial_state, plan):
    """State after each action, plus the state where the tray is fullest.

    `animate_action` is the shipped transition function, so it stays in the loop
    -- but it is written to animate, and animating is both wasteful and unsafe
    here.  Wasteful: it redraws the whole figure once per RRT waypoint, hundreds
    of times per plan, and a still needs three frames.  Unsafe: it calls
    `plt.pause(step_pause)`, and under Agg with a live figure manager
    `plt.pause(0.)` reaches `FigureCanvasBase.start_event_loop(0)`, which reads a
    non-positive timeout as "never time out" and spins forever -- so passing
    step_pause=0 to skip the animation hangs instead.

    Both are neutralised for the duration of the walk and restored afterwards;
    the three states we keep are drawn once each by the caller.

    The fullest-tray state is picked by what the state *is*, not by step index,
    so the montage survives the planner returning a different-but-equivalent
    routing.  Ties keep the earlier state: the first time the tray fills is the
    moment the batching decision has visibly been made.
    """
    real_draw, real_pause = viewer.draw_state, plt.pause
    viewer.draw_state = lambda *args, **kwargs: None
    plt.pause = lambda *args, **kwargs: None
    try:
        state, peak_state, peak = initial_state, None, 0
        for step_idx, action in enumerate(plan):
            state = animate_action(viewer, state, action, step_idx=step_idx,
                                   step_pause=0.)
            if len(state.tray) > peak:
                peak, peak_state = len(state.tray), state
    finally:
        viewer.draw_state, plt.pause = real_draw, real_pause
    return state, peak_state, peak


def solve_representative(problem_fn, algorithm='adaptive', max_time=300,
                         seeds=SEEDS):
    """Solve until the plan has the tray peak the sweeps report as typical.

    `evaluations/separation.py` measures a mean tray peak of exactly 3.0 over 10
    trials at every table separation, i.e. every trial batched all three cubes.
    A single run can still come back with a peak of 2 and a correspondingly worse
    cost, because `adaptive` reloads and rewrites its per-domain stream statistics
    on every solve, so consecutive runs are not independent draws.

    So this walks fixed seeds and stops at the first plan whose tray peak reaches
    the number of objects the goal moves, or the tray's capacity if the goal moves
    more than fit -- the shape the sweeps say is normal -- and otherwise returns
    the best it saw, printing which seed was used and what it settled for.  The
    figure is an illustration of the typical plan, and the numbers in the write-up
    come from the n=20 sweeps, not from this run.
    """
    target = min(len(problem_fn().goal_regions), TRAY_SLOTS)
    best = None
    for seed in seeds:
        np.random.seed(seed)
        tamp_problem = problem_fn()
        plan, cost, _ = solve_tamp(tamp_problem, algorithm=algorithm,
                                   merge_pick_and_stow=True, max_time=max_time,
                                   verbose=False, dump=False)
        if plan is None:
            print('seed {}: no plan'.format(seed))
            continue
        peak = max([0] + [len(shape) for shape in _tray_sizes(plan)])
        print('seed {}: {} actions, cost {:.2f}, tray peak {}'.format(
            seed, len(plan), cost, peak))
        if best is None or peak > best[0]:
            best = (peak, seed, tamp_problem, plan, cost)
        if peak >= target:
            break
    if best is None:
        raise RuntimeError('no plan found on any seed; nothing to screenshot')
    peak, seed, tamp_problem, plan, cost = best
    print('using seed {} (tray peak {} of {} objects)'.format(seed, peak, target))
    return tamp_problem, plan, cost


def _tray_sizes(plan):
    """Tray contents after each action, without needing the geometric state."""
    on_tray, sizes = set(), []
    for name, args in plan:
        if name in ('pick_and_stow', 'stow'):
            on_tray.add(args[1])
        elif name in ('unstow_and_place', 'unstow'):
            on_tray.discard(args[1])
        sizes.append(set(on_tray))
    return sizes


def frames_of(problem_fn, tmp_dir, algorithm='adaptive', max_time=300):
    """Solve once, then return [(png_path, caption), ...] for the montage."""
    tamp_problem, plan, cost = solve_representative(
        problem_fn, algorithm=algorithm, max_time=max_time)

    viewer = ContinuousTAMPViewer(tamp_problem)
    _fit_figure(viewer)
    final_state, peak_state, peak = walk_plan(viewer, tamp_problem.initial, plan)

    frames = []
    for name, state, caption in [
            ('initial', tamp_problem.initial, 'Initial state'),
            ('peak', peak_state, '{} objects carried at once'.format(peak)),
            ('final', final_state, 'Goal reached, {} actions'.format(len(plan)))]:
        if state is None or (name == 'peak' and peak < 2):
            continue
        # status=None: the montage caption above the panel already says this, and
        # the viewer's status box would repeat it inside the frame.
        viewer.draw_state(state, status=None)
        path = os.path.join(tmp_dir, '_frame_{}.png'.format(name))
        _capture(viewer, path)
        frames.append((path, caption))
    viewer.close()
    return frames


def montage(frames, out_path, heading, panel_width=PANEL_WIDTH):
    """Lay the frames out along whichever axis keeps each panel large.

    Stacking direction follows the frames' own shape rather than a fixed choice.
    A README renders an image scaled to the column width, so three wide-and-short
    panels in a row arrive at a third of that width each and stop being readable;
    stacked in a column they each get the full width.  A tall narrow scene is the
    other way round, hence the aspect test rather than a hard-coded orientation.
    """
    images = [mpimg.imread(path) for path, _ in frames]
    aspects = [img.shape[1] / float(img.shape[0]) for img in images]
    column = sum(aspects) / len(aspects) > 1.3

    if column:
        # Panels share a width; each keeps its own height, plus room for a caption.
        heights = [panel_width / aspect + 0.35 for aspect in aspects]
        fig, axes = plt.subplots(
            len(images), 1, figsize=(panel_width, sum(heights) + 0.4),
            gridspec_kw={'height_ratios': heights})
    else:
        # Panels share a height, so width follows each image's own aspect --
        # letting the grid pick equal widths would letterbox one and crop the
        # read of the scene, which is the whole content of the figure.
        height = 4.6
        fig, axes = plt.subplots(
            1, len(images), figsize=(height * sum(aspects), height + 0.5),
            gridspec_kw={'width_ratios': aspects})
    axes = np.atleast_1d(axes).ravel()

    for ax, img, (_path, caption) in zip(axes, images, frames):
        ax.imshow(img)
        ax.set_axis_off()
        ax.set_title(caption, fontsize=11, color='#333333')
    fig.suptitle(heading, fontsize=13, fontweight='bold', color='#111111')
    fig.tight_layout(rect=(0, 0, 1, 0.98 if column else 0.97))
    fig.savefig(out_path, dpi=DPI, facecolor='white')
    plt.close(fig)
    print('wrote {} ({} panels, {})'.format(
        out_path, len(images), 'stacked' if column else 'side by side'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--problem', default=DEFAULT_PROBLEM)
    parser.add_argument('-o', '--out-dir', default=OUT_DIR)
    parser.add_argument('--algorithm', default='adaptive')
    parser.add_argument('--max-time', type=float, default=300)
    parser.add_argument('--name', default=None,
                        help='output basename (default: derived from --problem)')
    args = parser.parse_args()

    out_dir = os.path.abspath(args.out_dir)
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    label = args.problem.replace('get_', '').replace('_problem', '')
    name = args.name or 'continuous2d_{}_plan.png'.format(label)
    out_path = os.path.join(out_dir, name)

    frames = frames_of(get_problem_fn(args.problem), out_dir,
                       algorithm=args.algorithm, max_time=args.max_time)
    montage(frames, out_path,
            'continuous2d / {} -- plan executed by the viewer'.format(label))
    for path, _caption in frames:
        os.remove(path)


if __name__ == '__main__':
    main()
