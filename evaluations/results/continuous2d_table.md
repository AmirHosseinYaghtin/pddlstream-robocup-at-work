# continuous2d -- adaptive, mean +/- population std over 20 trials

| metric | pick_place | corridor | multi_object | at_work |
|---|---|---|---|---|
| Total run time (s) | 0.134 ± 0.020 | 0.288 ± 0.084 | 1.121 ± 0.968 | 4.446 ± 1.768 |
| Search time (s) | 0.124 ± 0.020 | 0.146 ± 0.051 | 0.979 ± 0.844 | 4.056 ± 1.692 |
| Sample time (s) | 0.010 ± 0.005 | 0.142 ± 0.068 | 0.141 ± 0.156 | 0.390 ± 0.178 |
| Evaluations | 62 ± 1 | 68 ± 2 | 158 ± 40 | 385 ± 119 |
| Iterations | 5.0 | 5.0 | 5.0 ± 0.2 | 5.0 |
| Final complexity limit | 4.0 | 4.0 | 4.0 ± 0.2 | 4.0 |
| Plan skeletons | 1.0 | 1.0 | 1.0 | 1.0 |
| Plan cost | 21.83 ± 0.90 | 22.82 ± 0.85 | 69.26 ± 2.14 | 117.56 ± 2.59 |
| Plan length (actions) | 4.0 | 4.0 | 12.0 | 20.0 |
| Success rate | 1.00 | 1.00 | 1.00 | 1.00 |

## Scenario complexity (x-axis order)

1. **pick_place** (`-p get_pick_and_place_problem`) -- 1 cube, 2 tables, shelf as furniture -- minimal continuous transfer
2. **corridor** (`-p get_corridor_problem`) -- 1 cube, but base motion must thread a narrow gap (RRT pressure)
3. **multi_object** (`-p get_multi_object_problem`) -- 3 cubes to a distant table -- rewards tray batching
4. **at_work** (`-p get_at_work_problem`) -- 5 parts, 4 workstations + precision table -- full @Work task
