#!/usr/bin/env python
"""A scripted state machine, as the non-planner baseline.

The question this answers is the obvious one: *why use a task planner at all,
when the @Work task is "for each object, drive there, pick it up, drive to the
destination, put it down"?*  So we write exactly that, and measure it.

WHAT IS HELD CONSTANT.  Everything below the task layer is the same code the
planner uses -- the samplers, IK, the RRT, the collision tests, and the cost
functions, all imported from domains/continuous2d/primitives.py.  The emitted
actions are the merged domain's own (move_base / pick_and_stow /
unstow_and_place) with the same argument tuples, and the cost is accumulated by
calling MoveCost/ManipCost exactly as pddlstream does.  So a cost printed here
and a cost printed by the planner mean the same thing.

WHAT IS ABLATED.  The script commits.  It takes the objects in a fixed order,
and for each one it drives, picks, drives, and places.  It is allowed bounded
resampling at every step (a bad grasp, dock, IK solution or RRT failure is
retried) and it is allowed to abandon and restart an object -- being stingy here
would produce a strawman that fails for want of engineering rather than for want
of search.  What it does not get is the thing that makes a planner a planner:
it cannot reorder the objects, it cannot place an object anywhere except its
goal region, and it cannot undo a decision made for object i because of a
problem discovered at object j.

The discrete2d variant is the same idea with the geometry stripped out, and it
exists for one scenario in particular: `rearrangement` asks for a swap, so no
fixed order of "pick it up, put it in its goal slot" can work -- whichever
object goes first, its goal slot is occupied by the other one.  The planner
solves it by parking an object in a buffer slot.  The script cannot, and
reports the deadlock.

    python -m evaluations.baseline                        # every scenario
    python -m evaluations.baseline --scenario at_work -n 20
"""

from __future__ import print_function

import argparse
import json
import os
import time

import numpy as np

from pddlstream.language.constants import Action

from domains.continuous2d import primitives as cp
from domains.continuous2d.run import ROBOT, get_problem_fn as continuous_problem_fn
from domains.discrete2d import primitives as dp
from domains.discrete2d.run import get_problem_fn as discrete_problem_fn
from evaluations.run import RESULTS_DIR, aggregate
from evaluations.scenarios import (CONTINUOUS, CONTINUOUS_SCENARIOS, DISCRETE,
                                   DISCRETE_SCENARIOS, ALL_SCENARIOS)

# Bounded retries. The streams the planner uses are themselves bounded
# (get_dock_gen gives up after DOCK_MAX_ATTEMPTS, get_grasp_gen yields exactly
# four grasps), so these are the script's equivalent, not a handicap.
SAMPLE_ATTEMPTS = 10       # resamples of one (grasp, dock, IK, motion) chain
OBJECT_ATTEMPTS = 3        # restarts of a whole object
TRAY_SLOT = 'slot0'        # pick_and_stow frees the slot again at place time

DEFAULT_TRIALS = 20


class ScriptFailure(Exception):
    """Raised when the script commits itself into a corner it cannot leave."""

    def __init__(self, stage, obj, detail=''):
        super(ScriptFailure, self).__init__(
            '{} failed for {}{}'.format(stage, obj, ': ' + detail if detail else ''))
        self.stage = stage
        self.obj = obj
        self.detail = detail


# ==========================================================================
# continuous2d
# ==========================================================================

class ContinuousScript(object):
    """One run of the state machine over one TAMPProblem."""

    def __init__(self, tamp_problem, world_bound_margin=1.0):
        self.problem = tamp_problem
        self.object_types = tamp_problem.object_types
        self.regions = tamp_problem.regions

        obstacles = cp.compute_obstacle_boxes(tamp_problem.furniture)
        bounds = cp.compute_default_bounds(tamp_problem.regions,
                                           tamp_problem.furniture,
                                           world_bound_margin)

        # Identical wiring to pddlstream_from_tamp()'s stream_map, minus the
        # from_gen_fn/from_fn wrappers, which only adapt the calling convention.
        self.grasp_gen = cp.get_grasp_gen()
        self.region_gen = cp.get_region_gen(self.regions, self.object_types)
        self.region_test = cp.get_region_test(self.regions, self.object_types)
        self.dock_gen = cp.get_dock_gen(obstacles)
        self.ik_fn = cp.get_ik_fn()
        self.base_motion_fn = cp.get_base_motion_fn(obstacles, bounds, self.regions)
        self.arm_free_fn = cp.get_arm_motion_free_fn()
        self.arm_hold_fn = cp.get_arm_motion_holding_fn()
        self.base_cfree = cp.get_base_cfree_test(self.object_types)
        self.arm_cfree = cp.get_arm_cfree_test(self.object_types)
        self.move_cost = cp.get_move_base_cost_fn()
        self.manip_cost = cp.get_manip_cost_fn(include_stow=True)

        # Mutable world state, mirroring the PDDL fluents the merged domain
        # actually tracks: AtBaseConf, AtArmConf, AtPose, OnTray.
        self.base_conf = tamp_problem.initial.base_conf
        self.arm_home = tamp_problem.initial.arm_conf
        self.poses = dict(tamp_problem.initial.object_poses)
        self.furniture = list(tamp_problem.furniture)

        self.plan = []
        self.cost = 0.

    # -- collision checks, over exactly the facts the domain's foralls range over

    def _placed(self, exclude=None):
        """(object, pose) for everything with an AtPose fact right now."""
        entries = [(o, p) for o, p in self.poses.items() if o != exclude]
        return entries

    def _base_path_clear(self, traj):
        for obj, pose in self._placed():
            if not self.base_cfree(traj, obj, pose):
                return False
        for obj_type, pose in self.furniture:
            if not self.base_cfree(traj, obj_type, pose):
                return False
        return True

    def _arm_path_clear(self, bq, traj, moving_obj):
        # The domain's forall is over (Object ?o2), i.e. movable objects only.
        for obj, pose in self._placed(exclude=moving_obj):
            if not self.arm_cfree(bq, traj, obj, pose):
                return False
        return True

    # -- one manipulation, sampled with bounded retries

    def _reach(self, obj, pose, holding):
        """Sample (grasp, dock conf, arm conf, base traj, arm traj) for one
        manipulation at `pose`, or return None if the budget runs out."""
        grasps = [g for (g,) in self.grasp_gen(obj)]
        docks = self.dock_gen(obj, pose)
        for attempt in range(SAMPLE_ATTEMPTS):
            grasp = grasps[attempt % len(grasps)]
            try:
                (bq,) = next(docks)
            except StopIteration:
                return None
            ik = self.ik_fn(obj, pose, grasp, bq)
            if ik is None:
                continue
            (aq,) = ik

            motion = self.base_motion_fn(self.base_conf, bq)
            if motion is None:
                continue
            (base_traj,) = motion
            if not self._base_path_clear(base_traj):
                continue

            if holding:
                (arm_traj,) = self.arm_hold_fn(bq, self.arm_home, aq, obj, grasp)
            else:
                (arm_traj,) = self.arm_free_fn(bq, self.arm_home, aq)
            if not self._arm_path_clear(bq, arm_traj, obj):
                continue

            return grasp, bq, aq, base_traj, arm_traj
        return None

    def _do_move(self, bq, base_traj):
        self.plan.append(Action('move_base', (ROBOT, self.base_conf, base_traj, bq)))
        self.cost += self.move_cost(self.base_conf, bq)
        self.base_conf = bq

    def _pick(self, obj):
        pose = self.poses[obj]
        sampled = self._reach(obj, pose, holding=False)
        if sampled is None:
            raise ScriptFailure('pick', obj, 'no collision-free approach in {} tries'
                                .format(SAMPLE_ATTEMPTS))
        grasp, bq, aq, base_traj, arm_traj = sampled
        self._do_move(bq, base_traj)
        self.plan.append(Action('pick_and_stow', (ROBOT, obj, pose, grasp, bq,
                                                  self.arm_home, aq, arm_traj, TRAY_SLOT)))
        self.cost += self.manip_cost(self.arm_home, aq)
        del self.poses[obj]          # AtPose is deleted; the object rides the tray
        return grasp

    def _place(self, obj, grasp, region):
        # A placement pose is sampled the same way s-region does, and screened
        # by t-region -- the two streams the planner would use here.
        poses = self.region_gen(obj, region)
        for _ in range(SAMPLE_ATTEMPTS):
            try:
                (pose,) = next(poses)
            except StopIteration:
                break
            if not self.region_test(obj, pose, region):
                continue
            sampled = self._reach(obj, pose, holding=True)
            if sampled is None:
                continue
            _, bq, aq, base_traj, arm_traj = sampled
            self._do_move(bq, base_traj)
            self.plan.append(Action('unstow_and_place', (ROBOT, obj, pose, grasp, bq,
                                                         self.arm_home, aq, arm_traj,
                                                         TRAY_SLOT)))
            self.cost += self.manip_cost(self.arm_home, aq)
            self.poses[obj] = pose
            return
        raise ScriptFailure('place', obj, 'no reachable pose in {} of region {}'
                            .format(SAMPLE_ATTEMPTS, region))

    def run(self):
        """Fixed-order transfer. Returns the plan; raises ScriptFailure."""
        for obj, region in sorted(self.problem.goal_regions.items()):
            last_error = None
            for _ in range(OBJECT_ATTEMPTS):
                # Snapshot so an abandoned attempt does not leave a half-done
                # object in the state or a dangling prefix in the plan.
                saved = (self.base_conf, dict(self.poses), list(self.plan), self.cost)
                try:
                    grasp = self._pick(obj)
                    self._place(obj, grasp, region)
                    break
                except ScriptFailure as exc:
                    last_error = exc
                    self.base_conf, self.poses, self.plan, self.cost = saved
            else:
                raise last_error
        return self.plan


def run_continuous_trial(problem_fn):
    tamp_problem = problem_fn()
    script = ContinuousScript(tamp_problem)
    start = time.time()
    try:
        plan = script.run()
        failure = None
    except ScriptFailure as exc:
        plan, failure = None, exc
    elapsed = time.time() - start

    return {
        'solved': plan is not None,
        'timeout': False,
        'run_time': elapsed,
        'wall_time': elapsed,
        'cost': script.cost if plan is not None else None,
        'length': len(plan) if plan is not None else None,
        'has_plan': plan is not None,
        'failure_stage': failure.stage if failure else None,
        'failure_object': failure.obj if failure else None,
        'error': str(failure) if failure else None,
    }, plan


# ==========================================================================
# discrete2d
# ==========================================================================

def run_discrete_trial(problem_fn):
    """Same state machine with the geometry removed.

    move / pick / place from domains/discrete2d/domain.pddl. `place` requires
    (Clear ?p), which is the whole story on `rearrangement`: the script has no
    way to vacate a goal pose it has not reached yet.
    """
    problem = problem_fn()
    start = time.time()

    poses = dict(problem.initial.object_poses)
    conf = problem.initial.conf
    plan = []
    failure = None

    for obj in sorted(problem.goal_poses):
        target = problem.goal_poses[obj]
        current = poses[obj]
        if current == target:
            continue
        occupant = next((o for o, p in poses.items() if p == target and o != obj), None)
        if occupant is not None:
            # Escaping needs a buffer pose, i.e. a placement that serves no goal
            # -- exactly the step a fixed-order script has no reason to take.
            failure = ScriptFailure(
                'place', obj,
                'goal pose {} is occupied by {}; the script has no buffer step'
                .format(target, occupant))
            break

        pick_conf = dp.pose_to_conf(current)
        place_conf = dp.pose_to_conf(target)
        plan.append(Action('move', (conf, pick_conf)))
        plan.append(Action('pick', (obj, current, pick_conf)))
        plan.append(Action('move', (pick_conf, place_conf)))
        plan.append(Action('place', (obj, target, place_conf)))
        poses[obj] = target
        conf = place_conf

    elapsed = time.time() - start
    solved = failure is None
    return {
        'solved': solved,
        'timeout': False,
        'run_time': elapsed,
        'wall_time': elapsed,
        # discrete2d/domain.pddl carries no (increase (total-cost)) effects, so
        # the planner reports 0 here too -- not a missing measurement.
        'cost': 0. if solved else None,
        'length': len(plan) if solved else None,
        'has_plan': solved,
        'failure_stage': failure.stage if failure else None,
        'failure_object': failure.obj if failure else None,
        'error': str(failure) if failure else None,
    }, (plan if solved else None)


# ==========================================================================
# driver
# ==========================================================================

def run_scenario(scenario, trials):
    if scenario.phase == CONTINUOUS:
        problem_fn = continuous_problem_fn(scenario.problem)
        runner = run_continuous_trial
    else:
        problem_fn = discrete_problem_fn(scenario.problem)
        runner = run_discrete_trial

    print('  {:<18} {}'.format(scenario.label, scenario.complexity))
    records = []
    for trial in range(trials):
        record, _ = runner(problem_fn)
        record['trial'] = trial
        records.append(record)
    solved = sum(1 for r in records if r['solved'])
    reasons = sorted({r['error'] for r in records if r['error']})
    print('    solved {}/{}   mean run_time={:.4f}s'.format(
        solved, trials, sum(r['run_time'] for r in records) / float(trials)))
    for reason in reasons:
        print('    failure: {}'.format(reason))
    return records


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-n', '--trials', type=int, default=DEFAULT_TRIALS)
    parser.add_argument('--phase', default=None, choices=[DISCRETE, CONTINUOUS])
    parser.add_argument('--scenario', default=None,
                        help='Restrict to scenarios whose label contains this')
    parser.add_argument('-o', '--out-dir', default=os.path.join(RESULTS_DIR, 'sweeps'))
    args = parser.parse_args(argv)

    selected = list(ALL_SCENARIOS)
    if args.phase:
        selected = [s for s in selected if s.phase == args.phase]
    if args.scenario:
        selected = [s for s in selected if args.scenario in s.label]
    if not selected:
        parser.error('No scenario selected')

    cells = []
    for phase, scenarios in ((DISCRETE, DISCRETE_SCENARIOS),
                             (CONTINUOUS, CONTINUOUS_SCENARIOS)):
        chosen = [s for s in selected if s.phase == phase]
        if not chosen:
            continue
        print('\n=== scripted baseline: {} ({} trials each) ==='.format(phase, args.trials))
        for scenario in chosen:
            records = run_scenario(scenario, args.trials)
            cells.append({
                'axis': 'baseline',
                'key': 'script',
                'phase': scenario.phase,
                'scenario': scenario.label,
                'problem': scenario.problem,
                'complexity': scenario.complexity,
                'requested_trials': args.trials,
                'status': 'ok',
                'trials': records,
                'average': aggregate(records),
            })

    if not os.path.isdir(args.out_dir):
        os.makedirs(args.out_dir)
    path = os.path.join(args.out_dir, 'baseline.json')
    with open(path, 'w') as fh:
        json.dump({'sweep': 'baseline',
                   'config': {'trials': args.trials,
                              'sample_attempts': SAMPLE_ATTEMPTS,
                              'object_attempts': OBJECT_ATTEMPTS},
                   'cells': cells}, fh, indent=2, sort_keys=True)
    print('\nWrote', path)
    return path


if __name__ == '__main__':
    main()
