# Simulation-evaluation report

SUMO 1.24.0 | net sha256 `9b93309afcb0d3b5` | policy `deterministic` | 298 runs, budget 400 | wall time 482.2 s (7 worker processes) | generated 2026-09-26

Stop reason: max_probes=3 reached.

Verdict counts: PASS 171, FAIL 118, INVALID 9.

## Pass/fail criteria (project-defined)

| KPI | limit | meaning |
|---|---|---|
| `mean_delay_s` | <= 60 | network-wide mean delay per vehicle (timeLoss + departDelay) |
| `ramp_p95_delay_s` | <= 120 | 95th-percentile delay of ramp vehicles (queue / spillback) |
| `merge_speed_kmh` | >= 75 | flow-weighted mainline spot speed in the merge area |
| `ttc_per_1000veh` | <= 10 | SSM conflicts with min TTC < 1.5 s per 1000 vehicles |

Validity: `teleports` = 0 and `collisions` = 0, otherwise the run is INVALID.

## Boundaries found (bisection, other parameters nominal, majority of seeds)

| controller | parameter | last PASS | first not-PASS | width | tol | converged | monotone | steps |
|---|---|---|---|---|---|---|---|---|
| fixed | ramp_demand | 788 | 806 | 18 | 25 | True | True | 5 |
| fixed | incident_duration | 254 | 282 | 28 | 30 | True | True | 5 |
| alinea | incident_duration | 282 | 310 | 28 | 30 | True | True | 5 |
| fixed | main_demand | 4106 | 4138 | 32 | 50 | True | True | 5 |
| alinea | main_demand | 4044 | 4075 | 31 | 50 | True | True | 5 |

## One-at-a-time sensitivity (paired seeds; delta of run margin vs nominal)

### controller `fixed`

| parameter | lo value | mean delta (lo) | verdicts (lo) | hi value | mean delta (hi) | verdicts (hi) | influence | flip |
|---|---|---|---|---|---|---|---|---|
| ramp_demand | 300 | 0.0248 | PASS/PASS/PASS/PASS/PASS | 1200 | -5.3051 | FAIL/FAIL/FAIL/FAIL/FAIL | 5.3051 | hi |
| incident_duration | 0 | 0 | PASS/PASS/PASS/PASS/PASS | 900 | -2.3365 | FAIL/FAIL/FAIL/FAIL/FAIL | 2.3365 | hi |
| main_demand | 2400 | 0.0772 | PASS/PASS/PASS/PASS/PASS | 4200 | -0.6053 | PASS/PASS/FAIL/FAIL/FAIL | 0.6053 | hi |
| truck_share | 0 | 0.1281 | PASS/PASS/PASS/PASS/PASS | 0.25 | -0.1038 | INVALID/PASS/PASS/PASS/PASS | 0.1281 | - |
| sigma | 0 | 0.0224 | PASS/PASS/PASS/PASS/PASS | 0.9 | -0.1008 | PASS/PASS/PASS/FAIL/PASS | 0.1008 | - |
| incident_start | 300 | 0 | PASS/PASS/PASS/PASS/PASS | 1200 | 0 | PASS/PASS/PASS/PASS/PASS | 0 | - |

### controller `alinea`

| parameter | lo value | mean delta (lo) | verdicts (lo) | hi value | mean delta (hi) | verdicts (hi) | influence | flip |
|---|---|---|---|---|---|---|---|---|
| incident_duration | 0 | 0 | PASS/PASS/PASS/PASS/PASS | 900 | -2.3056 | FAIL/FAIL/FAIL/FAIL/FAIL | 2.3056 | hi |
| main_demand | 2400 | 0.081 | PASS/PASS/PASS/PASS/PASS | 4200 | -0.5364 | PASS/PASS/FAIL/FAIL/FAIL | 0.5364 | hi |
| truck_share | 0 | 0.1268 | PASS/PASS/PASS/PASS/PASS | 0.25 | -0.102 | PASS/PASS/PASS/PASS/PASS | 0.1268 | - |
| ramp_demand | 300 | 0.0319 | PASS/PASS/PASS/PASS/PASS | 1200 | -0.1183 | PASS/PASS/PASS/PASS/PASS | 0.1183 | - |
| sigma | 0 | 0.0231 | PASS/PASS/PASS/PASS/PASS | 0.9 | -0.0455 | PASS/PASS/PASS/PASS/PASS | 0.0455 | - |
| incident_start | 300 | 0 | PASS/PASS/PASS/PASS/PASS | 1200 | 0 | PASS/PASS/PASS/PASS/PASS | 0 | - |

## Screening: stratified not-PASS rate (lower vs upper half of each range)

| controller | parameter | split | n low | rate low | n high | rate high |
|---|---|---|---|---|---|---|
| alinea | main_demand | 3300 | 12 | 0.917 | 12 | 0.917 |
| alinea | ramp_demand | 750 | 12 | 0.917 | 12 | 0.917 |
| alinea | truck_share | 0.125 | 12 | 0.917 | 12 | 0.917 |
| alinea | incident_start | 750 | 12 | 0.833 | 12 | 1 |
| alinea | incident_duration | 450 | 12 | 0.833 | 12 | 1 |
| alinea | sigma | 0.45 | 12 | 0.833 | 12 | 1 |
| fixed | main_demand | 3300 | 12 | 0.833 | 12 | 1 |
| fixed | ramp_demand | 750 | 12 | 0.833 | 12 | 1 |
| fixed | truck_share | 0.125 | 12 | 0.917 | 12 | 0.917 |
| fixed | incident_start | 750 | 12 | 0.833 | 12 | 1 |
| fixed | incident_duration | 450 | 12 | 0.917 | 12 | 0.917 |
| fixed | sigma | 0.45 | 12 | 0.833 | 12 | 1 |

## Agent decisions

| # | action | policy | runs before | why |
|---|---|---|---|---|
| 1 | `probe:ramp_demand` | deterministic | 173 | largest paired mean-delta-margin magnitude among unprobed params with a verdict flip (ramp_demand) |
| 2 | `probe:incident_duration` | deterministic | 198 | largest paired mean-delta-margin magnitude among unprobed params with a verdict flip (incident_duration) |
| 3 | `probe:main_demand` | deterministic | 248 | largest paired mean-delta-margin magnitude among unprobed params with a verdict flip (main_demand) |

## Claims and evidence

Each claim's numbers are recomputed from the listed runs in `runs.jsonl` by `python scripts/verify_results.py`.

**C1.** Nominal scenario, controller 'fixed': mean over 5 seeds.

values: `{"collisions": 0, "mean_delay_s": 15.32, "merge_speed_kmh": 97.27, "ramp_p95_delay_s": 48.85, "ramp_queue_max_veh": 12.2, "teleports": 0, "throughput_veh": 1695.8, "ttc_per_1000veh": 0.0, "verdicts": ["PASS", "PASS", "PASS", "PASS", "PASS"]}`

evidence (5 runs): `09de1b65ac99`, `4224d1e7fafd`, `6dccacdae032`, `8107cc25c975`, `dbec7f1de5b6`

**C2.** Nominal scenario, controller 'alinea': mean over 5 seeds.

values: `{"collisions": 0, "mean_delay_s": 13.62, "merge_speed_kmh": 96.67, "ramp_p95_delay_s": 25.72, "ramp_queue_max_veh": 8.8, "teleports": 0, "throughput_veh": 1695.8, "ttc_per_1000veh": 0.0, "verdicts": ["PASS", "PASS", "PASS", "PASS", "PASS"]}`

evidence (5 runs): `162fa6351870`, `1cab0918e077`, `51dd7aabb8cb`, `576fab337e71`, `5da8cb55bbb9`

**C3.** Nominal scenario, controller 'none': mean over 5 seeds.

values: `{"collisions": 0, "mean_delay_s": 13.54, "merge_speed_kmh": 96.79, "ramp_p95_delay_s": 25.47, "ramp_queue_max_veh": 8.8, "teleports": 0, "throughput_veh": 1695.8, "ttc_per_1000veh": 0.0, "verdicts": ["PASS", "PASS", "PASS", "PASS", "PASS"]}`

evidence (5 runs): `00e8f793a37e`, `49405911a80a`, `68f9ed45e187`, `80c052907d12`, `e75e7c8bac3f`

**C4.** One-at-a-time (paired seeds), controller 'fixed': the most influential parameter is 'ramp_demand'; moving it to hi=1200 changes the run margin by -5.3051 on average (per-seed range -5.619..-4.8627).

values: `{"level": "hi", "max_delta_margin": -4.8627, "mean_delta_margin": -5.3051, "min_delta_margin": -5.619, "param": "ramp_demand", "value": 1200, "verdicts": ["FAIL", "FAIL", "FAIL", "FAIL", "FAIL"]}`

evidence (10 runs): `09de1b65ac99`, `4224d1e7fafd`, `560af3bd5974`, `5b69e0a7a7c3`, `6dccacdae032`, `8107cc25c975`, `8f292be11ec7`, `c945aff5b69e`, `d02047fc7541`, `dbec7f1de5b6`

**C5.** One-at-a-time (paired seeds), controller 'alinea': the most influential parameter is 'incident_duration'; moving it to hi=900 changes the run margin by -2.3056 on average (per-seed range -2.3958..-2.1959).

values: `{"level": "hi", "max_delta_margin": -2.1959, "mean_delta_margin": -2.3056, "min_delta_margin": -2.3958, "param": "incident_duration", "value": 900, "verdicts": ["FAIL", "FAIL", "FAIL", "FAIL", "FAIL"]}`

evidence (10 runs): `162fa6351870`, `1cab0918e077`, `51dd7aabb8cb`, `5224ba9c9247`, `576fab337e71`, `5da8cb55bbb9`, `633dc142a9c6`, `7a2625efd310`, `8983b24c47f5`, `a9f8909b7436`

**C6.** Boundary, controller 'fixed' along 'ramp_demand' (veh/h), other parameters nominal: majority PASS at 788, majority not-PASS at 806 (bisection width 18, tolerance 25, monotone over 8 evaluated points).

values: `{"controller": "fixed", "criteria_violated_at_fail": ["ramp_p95_delay_s"], "fail_verdicts": ["FAIL", "PASS", "FAIL", "FAIL", "FAIL"], "first_fail": 806, "last_pass": 788, "param": "ramp_demand", "pass_verdicts": ["PASS", "PASS", "FAIL", "FAIL", "PASS"]}`

evidence (10 runs): `1fd401bcc3eb`, `26857bdc104e`, `26f74ebf780f`, `8f8c45969a37`, `999513ac4970`, `aa0a5b54f6b1`, `b6db6ce7dc87`, `c381a31dae9f`, `c863b6f279ca`, `e99d0e2eb872`

**C7.** Boundary, controller 'fixed' along 'incident_duration' (s), other parameters nominal: majority PASS at 254, majority not-PASS at 282 (bisection width 28, tolerance 30, monotone over 7 evaluated points).

values: `{"controller": "fixed", "criteria_violated_at_fail": ["mean_delay_s"], "fail_verdicts": ["PASS", "FAIL", "FAIL", "FAIL", "PASS"], "first_fail": 282, "last_pass": 254, "param": "incident_duration", "pass_verdicts": ["PASS", "PASS", "PASS", "FAIL", "PASS"]}`

evidence (10 runs): `1a9fe3581d59`, `200fa7eabea0`, `3cd0c106d771`, `6ceb47f37d45`, `99f8e3c4260a`, `de325166dc1f`, `e7332f22383d`, `e81ec4374788`, `f2be735e0f3c`, `f391acfca4a6`

**C8.** Boundary, controller 'alinea' along 'incident_duration' (s), other parameters nominal: majority PASS at 282, majority not-PASS at 310 (bisection width 28, tolerance 30, monotone over 7 evaluated points).

values: `{"controller": "alinea", "criteria_violated_at_fail": ["mean_delay_s"], "fail_verdicts": ["PASS", "FAIL", "FAIL", "FAIL", "PASS"], "first_fail": 310, "last_pass": 282, "param": "incident_duration", "pass_verdicts": ["PASS", "PASS", "FAIL", "FAIL", "PASS"]}`

evidence (10 runs): `0629af1bc877`, `131d5b33c1b1`, `14c43b0a6902`, `22bdc8f3b129`, `25c9164520c9`, `44c5ddf879a6`, `471a72d7353d`, `68ceefb1a25b`, `85cb25cadb00`, `90733823a710`

**C9.** Boundary, controller 'fixed' along 'main_demand' (veh/h), other parameters nominal: majority PASS at 4106, majority not-PASS at 4138 (bisection width 32, tolerance 50, monotone over 8 evaluated points).

values: `{"controller": "fixed", "criteria_violated_at_fail": ["mean_delay_s"], "fail_verdicts": ["PASS", "PASS", "FAIL", "FAIL", "FAIL"], "first_fail": 4138, "last_pass": 4106, "param": "main_demand", "pass_verdicts": ["PASS", "PASS", "FAIL", "FAIL", "PASS"]}`

evidence (10 runs): `18f4b1f1807f`, `1f10b344dfc9`, `48ceb7093147`, `79066918bcaa`, `93b52022b45e`, `954df461b2a7`, `c3224d23d1d9`, `cb1b7ff578ea`, `f30140a3f7f5`, `f35f594c3880`

**C10.** Boundary, controller 'alinea' along 'main_demand' (veh/h), other parameters nominal: majority PASS at 4044, majority not-PASS at 4075 (bisection width 31, tolerance 50, monotone over 8 evaluated points).

values: `{"controller": "alinea", "criteria_violated_at_fail": ["mean_delay_s"], "fail_verdicts": ["PASS", "PASS", "FAIL", "FAIL", "FAIL"], "first_fail": 4075, "last_pass": 4044, "param": "main_demand", "pass_verdicts": ["PASS", "PASS", "FAIL", "FAIL", "PASS"]}`

evidence (10 runs): `04498198b89b`, `0e90fa89f39c`, `0ffbe6a5278b`, `42156a89a688`, `4fb5d9502efe`, `62cd4a0567bc`, `684cf981d116`, `9015246c364c`, `ae7b578fad66`, `cd76d11cd57c`

**C11.** Screening (Latin hypercube over the full ranges, seed 1), controller 'fixed': 22 of 24 runs are not-PASS; the largest lower-half vs upper-half difference in not-PASS rate is 0.167, shared by incident_start, main_demand, ramp_demand, sigma.

values: `{"largest_contrast": 0.167, "not_pass": 22, "params_with_largest_contrast": ["incident_start", "main_demand", "ramp_demand", "sigma"], "runs": 24}`

evidence (24 runs): `00a15a52e3cf`, `38a2a14fca29`, `405073b69216`, `4d60be8eebb1`, `4f79b434110a`, `5626225a7495`, `56cc2502d344`, `60235d869384`, `6d30a934cf4b`, `92aee55e52cc`, `9ea58b366b18`, `a1737a034381` (+12 more)

**C12.** Screening (Latin hypercube over the full ranges, seed 1), controller 'alinea': 22 of 24 runs are not-PASS; the largest lower-half vs upper-half difference in not-PASS rate is 0.167, shared by incident_duration, incident_start, sigma.

values: `{"largest_contrast": 0.167, "not_pass": 22, "params_with_largest_contrast": ["incident_duration", "incident_start", "sigma"], "runs": 24}`

evidence (24 runs): `024edca07011`, `15601102cdd3`, `1ca079456f75`, `296abcd640fe`, `2a68b5bb29d7`, `2ea744e6b9cd`, `33b6acc5dae6`, `3a8ee5ad6b4b`, `4e262c361f92`, `673627902069`, `6ca08c21d18d`, `7325d508ff17` (+12 more)

**C13.** Failure modes over all runs: number of runs violating each criterion.

values: `{"mean_delay_s": 102, "merge_speed_kmh": 14, "ramp_p95_delay_s": 35, "runs": 298, "ttc_per_1000veh": 15}`

evidence (122 runs): `00a15a52e3cf`, `0629af1bc877`, `063058d8c2b0`, `0e9ba335746d`, `0f6aa5f69187`, `0ffbe6a5278b`, `131d5b33c1b1`, `14c43b0a6902`, `16c5625e4aeb`, `192204924fec`, `1f10b344dfc9`, `230ddfaac8a6` (+110 more)

**C14.** Validity: runs with teleports or collisions (excluded from PASS/FAIL, counted as not-PASS).

values: `{"collision_lanes": {"incident_0": 1, "main_mid_0": 7, "ramp_in_0": 1}, "collisions": 9, "invalid_by_phase": {"oat": 1, "screen": 8}, "invalid_runs": 9, "invalid_with_incident": 8, "runs": 298, "teleports": 0}`

evidence (9 runs): `024edca07011`, `1ca079456f75`, `673627902069`, `6d30a934cf4b`, `ab75afb1c2c1`, `b80f7ca0ae7e`, `bce74dccebda`, `dfc3dc5c5a68`, `ecf9261e853c`

