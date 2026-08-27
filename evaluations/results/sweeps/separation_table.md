# Cost against table separation -- mean +/- population std

Scenario continuous2d / multi_object, algorithm adaptive, 10 trials per side per separation. The scenario ships at separation 8.0.

| separation | planner cost | state machine cost | gap | planner cheaper by | planner tray peak | planner base travel | state machine base travel | solved (planner / script) |
|---|---|---|---|---|---|---|---|---|
| 2.0 | 63.58 ± 2.01 | 67.94 ± 2.14 | 4.36 | 6.4% | 3.0 | 4.90 | 10.07 | 10 / 10 |
| 4.0 | 66.22 ± 1.67 | 76.67 ± 2.27 | 10.45 | 13.6% | 3.0 | 7.01 | 19.05 | 10 / 10 |
| 6.0 | 66.65 ± 1.50 | 86.82 ± 2.34 | 20.17 | 23.2% | 3.0 | 8.75 | 29.16 | 10 / 10 |
| 8.0 **(shipped)** | 69.41 ± 2.26 | 97.47 ± 1.37 | 28.06 | 28.8% | 3.0 | 11.31 | 38.78 | 10 / 10 |
| 10.0 | 70.55 ± 2.54 | 108.43 ± 2.27 | 37.87 | 34.9% | 3.0 | 12.94 | 49.09 | 10 / 10 |
| 12.0 | 74.83 ± 1.81 | 117.58 ± 1.98 | 42.75 | 36.4% | 3.0 | 15.81 | 59.01 | 10 / 10 |

`tray peak` is the largest number of objects on the tray at once, so it is the mechanism behind the gap: the planner reaches 3, and the state machine is structurally 1 -- it transfers objects one at a time in a fixed order.

Cost per unit separation (least squares): planner +1.03, state machine +5.06.

Caveat, as recorded in separation.py: `adaptive` persists its stream statistics per domain, so absolute costs shift by a few units between campaigns. The slope is the reproducible quantity, not the offset.
