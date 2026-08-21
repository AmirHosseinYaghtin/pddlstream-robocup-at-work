# continuous2d -- adaptive, mean +/- population std over 5 trials

| metric | pick_place | corridor | multi_object | at_work |
|---|---|---|---|---|
| Total run time (s) | 0.130 ± 0.014 | 0.282 ± 0.050 | 0.808 ± 0.126 | 6.990 ± 1.069 |
| Search time (s) | 0.112 ± 0.008 | 0.119 ± 0.012 | 0.770 ± 0.130 | 6.635 ± 0.927 |
| Sample time (s) | 0.018 ± 0.015 | 0.163 ± 0.045 | 0.038 ± 0.010 | 0.354 ± 0.187 |
| Evaluations | 63 ± 2 | 69 ± 3 | 145 ± 3 | 396 ± 109 |
| Iterations | 5.0 | 5.0 | 5.0 | 5.0 |
| Final complexity limit | 4.0 | 4.0 | 4.0 | 4.0 |
| Plan skeletons | 1.0 | 1.0 | 1.0 | 1.0 |
| Plan cost | 22.71 ± 0.29 | 24.10 ± 0.73 | 63.50 ± 2.77 | 115.98 ± 2.28 |
| Plan length (actions) | 4.0 | 4.0 | 12.0 | 20.0 |
| Success rate | 1.00 | 1.00 | 1.00 | 1.00 |

## Scenario complexity (x-axis order)

1. **pick_place** (`-p get_pick_and_place_problem`) -- 1 cube, 2 tables, shelf as furniture -- minimal continuous transfer
2. **corridor** (`-p get_corridor_problem`) -- 1 cube, but base motion must thread a narrow gap (RRT pressure)
3. **multi_object** (`-p get_multi_object_problem`) -- 3 cubes to one table -- tray slots and placement interaction
4. **at_work** (`-p get_at_work_problem`) -- 5 parts, 4 workstations + precision table -- full @Work task
