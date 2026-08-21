"""Systematic evaluation of the PDDLStream planner on this project's scenarios.

Two phases (`discrete2d`, `continuous2d`), each with scenarios ordered by
increasing complexity. Every scenario is solved N times, the planner's own
summary metrics are captured per trial, averaged per scenario, and plotted.

    python -m evaluations.run   --trials 5      # run + save results
    python -m evaluations.plot                  # plot the saved results

See scenarios.py for the scenario registry and metrics.py for the capture.
"""
