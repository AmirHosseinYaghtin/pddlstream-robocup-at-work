# PDDLStream algorithm -- mean +/- population std

Up to 20 trials per cell. Cells the probe found unsolvable were re-run at n=3 instead; they are marked below.

## Total run time (s)

| scenario | incremental | focused | binding | adaptive |
|---|---|---|---|---|
| discrete2d / pick_place | 0.013 ± 0.003 | 0.019 ± 0.004 | 0.019 ± 0.004 | 0.019 ± 0.005 |
| discrete2d / object_transport | 0.014 ± 0.003 | 0.022 ± 0.004 | 0.021 ± 0.002 | 0.022 ± 0.002 |
| discrete2d / rearrangement | 0.017 ± 0.004 | 0.042 ± 0.010 | 0.044 ± 0.006 | 0.041 ± 0.006 |
| continuous2d / pick_place | _hang: translation_ | _AssertionError_ | 0.183 ± 0.130 | 0.137 ± 0.020 |
| continuous2d / corridor | _hang: translation_ | _AssertionError_ | 0.399 ± 0.236 | 0.253 ± 0.102 |
| continuous2d / multi_object | _hang: translation_ | _AssertionError_ | 0.496 | 0.855 ± 0.180 |
| continuous2d / at_work | _hang: unknown_ | _AssertionError_ | _hang: stream planning_ | 7.003 ± 1.294 |

## Plan cost

discrete2d / pick_place, discrete2d / object_transport, discrete2d / rearrangement report 0 by construction: that domain's domain.pddl has no `increase (total-cost)` effects, so no action carries a cost.

| scenario | incremental | focused | binding | adaptive |
|---|---|---|---|---|
| discrete2d / pick_place | 0.00 | 0.00 | 0.00 | 0.00 |
| discrete2d / object_transport | 0.00 | 0.00 | 0.00 | 0.00 |
| discrete2d / rearrangement | 0.00 | 0.00 | 0.00 | 0.00 |
| continuous2d / pick_place | _hang: translation_ | _AssertionError_ | 21.61 ± 0.71 | 21.81 ± 1.17 |
| continuous2d / corridor | _hang: translation_ | _AssertionError_ | 23.29 ± 1.14 | 23.44 ± 1.01 |
| continuous2d / multi_object | _hang: translation_ | _AssertionError_ | 66.14 | 68.33 ± 1.46 |
| continuous2d / at_work | _hang: unknown_ | _AssertionError_ | _hang: stream planning_ | 118.44 ± 2.76 |

## Plan length (actions)

| scenario | incremental | focused | binding | adaptive |
|---|---|---|---|---|
| discrete2d / pick_place | 4.0 | 4.0 | 4.0 | 4.0 |
| discrete2d / object_transport | 4.0 | 4.0 | 4.0 | 4.0 |
| discrete2d / rearrangement | 12.0 | 12.0 | 12.0 | 12.0 |
| continuous2d / pick_place | _hang: translation_ | _AssertionError_ | 4.0 | 4.0 |
| continuous2d / corridor | _hang: translation_ | _AssertionError_ | 4.0 | 4.0 |
| continuous2d / multi_object | _hang: translation_ | _AssertionError_ | 12.0 | 12.0 |
| continuous2d / at_work | _hang: unknown_ | _AssertionError_ | _hang: stream planning_ | 20.0 |

## Evaluations

| scenario | incremental | focused | binding | adaptive |
|---|---|---|---|---|
| discrete2d / pick_place | 14 | 14 | 14 | 14 |
| discrete2d / object_transport | 22 | 18 | 18 | 18 |
| discrete2d / rearrangement | 27 | 23 | 23 | 23 |
| continuous2d / pick_place | _hang: translation_ | _AssertionError_ | 65 ± 8 | 63 ± 2 |
| continuous2d / corridor | _hang: translation_ | _AssertionError_ | 76 ± 12 | 68 ± 2 |
| continuous2d / multi_object | _hang: translation_ | _AssertionError_ | 142 | 152 ± 13 |
| continuous2d / at_work | _hang: unknown_ | _AssertionError_ | _hang: stream planning_ | 331 ± 17 |

## Success rate

| scenario | incremental | focused | binding | adaptive |
|---|---|---|---|---|
| discrete2d / pick_place | 1.00 | 1.00 | 1.00 | 1.00 |
| discrete2d / object_transport | 1.00 | 1.00 | 1.00 | 1.00 |
| discrete2d / rearrangement | 1.00 | 1.00 | 1.00 | 1.00 |
| continuous2d / pick_place | _hang: translation_ | 0.00 | 0.85 | 1.00 |
| continuous2d / corridor | _hang: translation_ | 0.00 | 0.90 | 1.00 |
| continuous2d / multi_object | _hang: translation_ | 0.00 | 1.00 | 1.00 |
| continuous2d / at_work | 0.00 | 0.00 | 0.00 | 1.00 |

## Trials actually run per cell

| scenario | incremental | focused | binding | adaptive |
|---|---|---|---|---|
| discrete2d / pick_place | 20 | 20 | 20 | 20 |
| discrete2d / object_transport | 20 | 20 | 20 | 20 |
| discrete2d / rearrangement | 20 | 20 | 20 | 20 |
| continuous2d / pick_place | 0 (killed) | 3 | 20 | 20 |
| continuous2d / corridor | 0 (killed) | 3 | 20 | 20 |
| continuous2d / multi_object | 0 (killed) | 3 | 1 (killed) | 20 |
| continuous2d / at_work | 1 (killed) | 3 | 2 (killed) | 20 |

## Why these configurations found no plan

- **focused** -- AssertionError: could not instantiate the MoveCost PNE for an optimistic object.
