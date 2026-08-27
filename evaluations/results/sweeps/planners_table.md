# Fast Downward search configuration -- mean +/- population std

Up to 20 trials per cell. Cells the probe found unsolvable were re-run at n=3 instead; they are marked below.

## Total run time (s)

| scenario | ff-astar2 | ff-astar | ff-eager | ff-lazy | ff-wastar3 | cea-wastar3 | add-random-lazy | max-astar | lmcut-astar | dijkstra |
|---|---|---|---|---|---|---|---|---|---|---|
| discrete2d / pick_place | 0.019 ± 0.002 | 0.019 ± 0.005 | 0.018 ± 0.002 | 0.019 ± 0.004 | 0.019 ± 0.004 | 0.018 ± 0.004 | 0.021 ± 0.002 | 0.019 ± 0.004 | 0.020 ± 0.005 | 0.019 ± 0.004 |
| discrete2d / object_transport | 0.022 ± 0.005 | 0.021 ± 0.002 | 0.021 ± 0.002 | 0.021 ± 0.003 | 0.021 ± 0.002 | 0.020 ± 0.002 | 0.021 ± 0.005 | 0.021 ± 0.003 | 0.022 ± 0.004 | 0.022 ± 0.004 |
| discrete2d / rearrangement | 0.031 ± 0.009 | 0.030 ± 0.006 | 0.040 ± 0.006 | 0.040 ± 0.006 | 0.028 ± 0.008 | 0.054 ± 0.004 | 0.027 ± 0.006 | 0.041 ± 0.007 | 0.041 ± 0.007 | 0.028 ± 0.006 |
| continuous2d / pick_place | 0.141 ± 0.048 | 0.130 ± 0.019 | 0.126 ± 0.015 | 0.132 ± 0.021 | 0.130 ± 0.016 | 0.135 ± 0.019 | 0.127 ± 0.020 | 0.135 ± 0.028 | _no plan_ | 0.128 ± 0.015 |
| continuous2d / corridor | 0.322 ± 0.163 | 0.266 ± 0.096 | 0.274 ± 0.130 | 0.262 ± 0.108 | 0.281 ± 0.078 | 0.264 ± 0.083 | 0.264 ± 0.075 | 0.300 ± 0.153 | _no plan_ | 0.262 ± 0.130 |
| continuous2d / multi_object | 1.005 ± 0.239 | 1.081 ± 0.270 | 0.913 ± 0.209 | 1.015 ± 0.296 | 1.361 ± 2.051 | 0.877 ± 0.177 | 0.899 ± 0.199 | 0.856 ± 0.231 | _no plan_ | 0.885 ± 0.168 |
| continuous2d / at_work | 6.808 ± 0.916 | 7.294 ± 6.480 | 5.626 ± 1.171 | 7.991 ± 8.636 | 7.623 ± 1.256 | 6.341 ± 0.893 | 9.633 ± 4.640 | 23.332 ± 66.734 | _no plan_ | 6.762 ± 1.130 |

## Plan cost

discrete2d / pick_place, discrete2d / object_transport, discrete2d / rearrangement report 0 by construction: that domain's domain.pddl has no `increase (total-cost)` effects, so no action carries a cost.

| scenario | ff-astar2 | ff-astar | ff-eager | ff-lazy | ff-wastar3 | cea-wastar3 | add-random-lazy | max-astar | lmcut-astar | dijkstra |
|---|---|---|---|---|---|---|---|---|---|---|
| discrete2d / pick_place | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| discrete2d / object_transport | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| discrete2d / rearrangement | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| continuous2d / pick_place | 21.59 ± 0.88 | 22.17 ± 1.01 | 21.85 ± 0.62 | 21.57 ± 0.96 | 21.60 ± 0.83 | 21.70 ± 0.89 | 22.02 ± 0.96 | 21.76 ± 0.72 | _no plan_ | 21.33 ± 0.97 |
| continuous2d / corridor | 23.51 ± 0.78 | 23.28 ± 0.60 | 23.12 ± 0.78 | 23.40 ± 0.92 | 23.13 ± 0.78 | 22.78 ± 0.90 | 23.02 ± 0.99 | 23.30 ± 1.02 | _no plan_ | 23.11 ± 0.74 |
| continuous2d / multi_object | 69.83 ± 2.11 | 83.26 ± 2.02 | 69.84 ± 1.89 | 69.94 ± 4.10 | 72.11 ± 10.24 | 68.90 ± 2.08 | 69.60 ± 1.52 | 69.52 ± 1.54 | _no plan_ | 83.46 ± 2.73 |
| continuous2d / at_work | 118.69 ± 2.25 | 120.28 ± 3.17 | 119.39 ± 2.27 | 117.71 ± 3.53 | 118.82 ± 1.72 | 112.91 ± 2.26 | 140.14 ± 12.88 | 119.78 ± 2.78 | _no plan_ | 115.04 ± 2.45 |

## Plan length (actions)

| scenario | ff-astar2 | ff-astar | ff-eager | ff-lazy | ff-wastar3 | cea-wastar3 | add-random-lazy | max-astar | lmcut-astar | dijkstra |
|---|---|---|---|---|---|---|---|---|---|---|
| discrete2d / pick_place | 4.0 | 4.0 | 4.0 | 4.0 | 4.0 | 4.0 | 4.0 | 4.0 | 4.0 | 4.0 |
| discrete2d / object_transport | 4.0 | 4.0 | 4.0 | 4.0 | 4.0 | 4.0 | 4.0 | 4.0 | 4.0 | 4.0 |
| discrete2d / rearrangement | 12.0 | 12.0 | 12.0 | 12.0 | 12.0 | 12.0 | 12.0 | 12.0 | 12.0 | 12.0 |
| continuous2d / pick_place | 4.0 | 4.0 | 4.0 | 4.0 | 4.0 | 4.0 | 4.0 | 4.0 | _no plan_ | 4.0 |
| continuous2d / corridor | 4.0 | 4.0 | 4.0 | 4.0 | 4.0 | 4.0 | 4.0 | 4.0 | _no plan_ | 4.0 |
| continuous2d / multi_object | 12.0 | 12.0 | 12.0 | 12.0 | 12.2 ± 0.9 | 12.0 | 12.0 | 12.0 | _no plan_ | 12.0 |
| continuous2d / at_work | 20.0 | 20.0 | 20.0 | 20.0 | 20.0 | 20.0 | 25.2 ± 3.6 | 20.0 | _no plan_ | 20.0 |

## Evaluations

| scenario | ff-astar2 | ff-astar | ff-eager | ff-lazy | ff-wastar3 | cea-wastar3 | add-random-lazy | max-astar | lmcut-astar | dijkstra |
|---|---|---|---|---|---|---|---|---|---|---|
| discrete2d / pick_place | 14 | 14 | 14 | 14 | 14 | 14 | 14 | 14 | 14 | 14 |
| discrete2d / object_transport | 18 | 18 | 18 | 18 | 18 | 18 | 18 | 18 | 18 | 18 |
| discrete2d / rearrangement | 23 | 23 | 23 | 23 | 23 | 23 | 23 | 23 | 23 | 23 |
| continuous2d / pick_place | 64 ± 3 | 63 ± 2 | 63 ± 2 | 63 ± 2 | 62 ± 1 | 63 ± 2 | 63 ± 2 | 63 ± 2 | _no plan_ | 64 ± 3 |
| continuous2d / corridor | 68 ± 2 | 68 ± 2 | 68 ± 2 | 67 ± 1 | 68 ± 2 | 68 ± 2 | 68 ± 2 | 68 ± 2 | _no plan_ | 70 ± 3 |
| continuous2d / multi_object | 157 ± 18 | 168 ± 36 | 148 ± 7 | 151 ± 14 | 164 ± 73 | 154 ± 19 | 152 ± 17 | 158 ± 19 | _no plan_ | 153 ± 10 |
| continuous2d / at_work | 345 ± 53 | 398 ± 151 | 379 ± 103 | 363 ± 93 | 337 ± 13 | 386 ± 126 | 442 ± 116 | 344 ± 29 | _no plan_ | 340 ± 23 |

## Success rate

| scenario | ff-astar2 | ff-astar | ff-eager | ff-lazy | ff-wastar3 | cea-wastar3 | add-random-lazy | max-astar | lmcut-astar | dijkstra |
|---|---|---|---|---|---|---|---|---|---|---|
| discrete2d / pick_place | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| discrete2d / object_transport | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| discrete2d / rearrangement | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| continuous2d / pick_place | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.00 | 1.00 |
| continuous2d / corridor | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.00 | 1.00 |
| continuous2d / multi_object | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.00 | 1.00 |
| continuous2d / at_work | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.95 | 0.00 | 1.00 |

## Trials actually run per cell

| scenario | ff-astar2 | ff-astar | ff-eager | ff-lazy | ff-wastar3 | cea-wastar3 | add-random-lazy | max-astar | lmcut-astar | dijkstra |
|---|---|---|---|---|---|---|---|---|---|---|
| discrete2d / pick_place | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 20 |
| discrete2d / object_transport | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 20 |
| discrete2d / rearrangement | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 20 |
| continuous2d / pick_place | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 3 | 20 |
| continuous2d / corridor | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 3 | 20 |
| continuous2d / multi_object | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 3 | 20 |
| continuous2d / at_work | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 3 | 20 |

## Why these configurations found no plan

- **lmcut-astar** -- FD's LM-cut heuristic does not support axioms, and continuous2d derives (In ?o ?reg); FD exits with "unsupported feature" and no plan file.
