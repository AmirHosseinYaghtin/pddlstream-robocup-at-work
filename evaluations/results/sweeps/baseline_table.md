# scripted state machine vs. planner -- mean +/- population std

Up to 20 trials per cell.

## Total run time (s)

| scenario | script | planner |
|---|---|---|
| discrete2d / pick_place | 0.000 ± 0.000 | 0.021 ± 0.002 |
| discrete2d / object_transport | 0.000 ± 0.000 | 0.023 ± 0.002 |
| discrete2d / rearrangement | _place failed for obj0_ | 0.044 ± 0.004 |
| continuous2d / pick_place | 0.011 ± 0.014 | 0.134 ± 0.020 |
| continuous2d / corridor | 0.183 ± 0.111 | 0.288 ± 0.084 |
| continuous2d / multi_object | 0.250 ± 0.163 | 1.121 ± 0.968 |
| continuous2d / at_work | 0.345 ± 0.151 | 4.446 ± 1.768 |

## Plan cost

discrete2d / pick_place, discrete2d / object_transport, discrete2d / rearrangement report 0 by construction: that domain's domain.pddl has no `increase (total-cost)` effects, so no action carries a cost.

| scenario | script | planner |
|---|---|---|
| discrete2d / pick_place | 0.00 | 0.00 |
| discrete2d / object_transport | 0.00 | 0.00 |
| discrete2d / rearrangement | _place failed for obj0_ | 0.00 |
| continuous2d / pick_place | 21.36 ± 0.86 | 21.83 ± 0.90 |
| continuous2d / corridor | 22.86 ± 0.98 | 22.82 ± 0.85 |
| continuous2d / multi_object | 97.98 ± 2.15 | 69.26 ± 2.14 |
| continuous2d / at_work | 116.44 ± 3.00 | 117.56 ± 2.59 |

## Plan length (actions)

| scenario | script | planner |
|---|---|---|
| discrete2d / pick_place | 4.0 | 4.0 |
| discrete2d / object_transport | 4.0 | 4.0 |
| discrete2d / rearrangement | _place failed for obj0_ | 12.0 |
| continuous2d / pick_place | 4.0 | 4.0 |
| continuous2d / corridor | 4.0 | 4.0 |
| continuous2d / multi_object | 12.0 | 12.0 |
| continuous2d / at_work | 20.0 | 20.0 |

## Evaluations

| scenario | script | planner |
|---|---|---|
| discrete2d / pick_place | _n/a_ | 14 |
| discrete2d / object_transport | _n/a_ | 18 |
| discrete2d / rearrangement | _place failed for obj0_ | 23 |
| continuous2d / pick_place | _n/a_ | 62 ± 1 |
| continuous2d / corridor | _n/a_ | 68 ± 2 |
| continuous2d / multi_object | _n/a_ | 158 ± 40 |
| continuous2d / at_work | _n/a_ | 385 ± 119 |

## Success rate

| scenario | script | planner |
|---|---|---|
| discrete2d / pick_place | 1.00 | 1.00 |
| discrete2d / object_transport | 1.00 | 1.00 |
| discrete2d / rearrangement | 0.00 | 1.00 |
| continuous2d / pick_place | 1.00 | 1.00 |
| continuous2d / corridor | 1.00 | 1.00 |
| continuous2d / multi_object | 1.00 | 1.00 |
| continuous2d / at_work | 1.00 | 1.00 |

## Trials actually run per cell

| scenario | script | planner |
|---|---|---|
| discrete2d / pick_place | 20 | 20 |
| discrete2d / object_transport | 20 | 20 |
| discrete2d / rearrangement | 20 | 20 |
| continuous2d / pick_place | 20 | 20 |
| continuous2d / corridor | 20 | 20 |
| continuous2d / multi_object | 20 | 20 |
| continuous2d / at_work | 20 | 20 |
