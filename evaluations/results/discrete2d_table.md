# discrete2d -- adaptive, mean +/- population std over 20 trials

| metric | pick_place | object_transport | rearrangement |
|---|---|---|---|
| Total run time (s) | 0.021 ± 0.002 | 0.023 ± 0.002 | 0.044 ± 0.004 |
| Search time (s) | 0.021 ± 0.002 | 0.023 ± 0.002 | 0.044 ± 0.004 |
| Sample time (s) | 4.37e-05 ± 6.75e-06 | 4.08e-05 ± 2.80e-06 | 5.11e-05 ± 6.54e-06 |
| Evaluations | 14 | 18 | 23 |
| Iterations | 2.0 | 2.0 | 2.0 |
| Final complexity limit | 1.0 | 1.0 | 1.0 |
| Plan skeletons | 1.0 | 1.0 | 1.0 |
| Plan cost | 0.00 | 0.00 | 0.00 |
| Plan length (actions) | 4.0 | 4.0 | 12.0 |
| Success rate | 1.00 | 1.00 | 1.00 |

## Scenario complexity (x-axis order)

1. **pick_place** (`-p get_pick_and_place_problem`) -- 1 object, 2 poses, 1 goal -- the minimal transfer
2. **object_transport** (`-p get_object_transport_problem`) -- 1 object, 4 poses, 1 goal -- same plan shape, larger pose set
3. **rearrangement** (`-p get_rearrangement_problem`) -- 2 objects, 5 poses, 2 goals -- a swap, needs a buffer pose
