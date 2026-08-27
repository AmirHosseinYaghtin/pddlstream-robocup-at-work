"""Systematic evaluation of the PDDLStream planner on this project's scenarios.

Two phases (`discrete2d`, `continuous2d`), each with scenarios ordered by
increasing complexity. Every scenario is solved N times, the planner's own
summary metrics are captured per trial, averaged per scenario, and plotted.

    python -m evaluations.run   --trials 20     # run + save results
    python -m evaluations.plot                  # plot the saved results

and the comparison sweeps, each writing into results/sweeps/:

    python -m evaluations.sweep --probe         # which algo/planner cells work
    python -m evaluations.sweep --algorithms    # 4-algorithm comparison
    python -m evaluations.sweep --planners      # FD search-config comparison
    python -m evaluations.baseline              # scripted state machine
    python -m evaluations.separation            # cost gap vs table separation
    python -m evaluations.plot_compare          # plot all of them

See scenarios.py for the scenario registry and metrics.py for the capture.
sweep.py runs each cell as a killable subprocess; worker.py is that subprocess.
plan_shape.py answers what the cost column cannot: whether a plan carries several
objects per trip.
"""
