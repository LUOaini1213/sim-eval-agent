# Simulation-evaluation report

SUMO 1.24.0 | net sha256 `9b93309afcb0d3b5` | policy `deterministic` | 908 runs, budget 1300 | wall time 2533.5 s (7 worker processes) | generated 2026-09-26

Stop reason: max_probes=3 reached.

Verdict counts: PASS 495, FAIL 413, INVALID 0.

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
| fixed | incident_duration | 225 | 254 | 29 | 30 | True | True | 5 |
| alinea | incident_duration | 196 | 225 | 29 | 30 | True | True | 5 |
| fixed | main_demand | 4044 | 4075 | 31 | 50 | True | True | 5 |
| alinea | main_demand | 4044 | 4075 | 31 | 50 | True | True | 5 |

## Refined boundaries (pass rate over paired seeds, Wilson 95% interval)

Rule: a value is confidently PASS if the interval's lower end > 0.5, confidently not-PASS if its upper end < 0.5. The band runs from the last confidently-PASS value to the first confidently-not-PASS value; x50 is where the isotonic fit of the pass rate crosses 0.5.

### fixed / ramp_demand: band [697, 847], x50 772.0 (bisection [788, 806])

| value | passes / n | rate | Wilson 95% | class |
|---|---|---|---|---|
| 697 | 19/20 | 0.95 | 0.76-0.99 | pass |
| 747 | 13/20 | 0.65 | 0.43-0.82 | undecided |
| 797 | 7/20 | 0.35 | 0.18-0.57 | undecided |
| 847 | 0/20 | 0.00 | 0.00-0.16 | fail |
| 897 | 0/20 | 0.00 | 0.00-0.16 | fail |

### fixed / incident_duration: band [120, 300], x50 210.0 (bisection [225, 254])

| value | passes / n | rate | Wilson 95% | class |
|---|---|---|---|---|
| 120 | 18/20 | 0.90 | 0.70-0.97 | pass |
| 180 | 14/20 | 0.70 | 0.48-0.85 | undecided |
| 240 | 6/20 | 0.30 | 0.15-0.52 | undecided |
| 300 | 3/20 | 0.15 | 0.05-0.36 | fail |
| 360 | 0/20 | 0.00 | 0.00-0.16 | fail |

### alinea / incident_duration: band [150, 270], x50 198.0 (bisection [196, 225])

| value | passes / n | rate | Wilson 95% | class |
|---|---|---|---|---|
| 90 | 20/20 | 1.00 | 0.84-1.00 | pass |
| 150 | 18/20 | 0.90 | 0.70-0.97 | pass |
| 210 | 8/20 | 0.40 | 0.22-0.61 | undecided |
| 270 | 4/20 | 0.20 | 0.08-0.42 | fail |
| 330 | 1/20 | 0.05 | 0.01-0.24 | fail |

### fixed / main_demand: band [3860, None], x50 4085.0 (bisection [4044, 4075])

| value | passes / n | rate | Wilson 95% | class |
|---|---|---|---|---|
| 3860 | 19/20 | 0.95 | 0.76-0.99 | pass |
| 3960 | 14/20 | 0.70 | 0.48-0.85 | undecided |
| 4060 | 11/20 | 0.55 | 0.34-0.74 | undecided |
| 4160 | 7/20 | 0.35 | 0.18-0.57 | undecided |
| 4200 | 7/20 | 0.35 | 0.18-0.57 | undecided |

### alinea / main_demand: band [3960, None], x50 4096.36 (bisection [4044, 4075])

| value | passes / n | rate | Wilson 95% | class |
|---|---|---|---|---|
| 3860 | 18/20 | 0.90 | 0.70-0.97 | pass |
| 3960 | 15/20 | 0.75 | 0.53-0.89 | pass |
| 4060 | 12/20 | 0.60 | 0.39-0.78 | undecided |
| 4160 | 6/20 | 0.30 | 0.15-0.52 | undecided |
| 4200 | 7/20 | 0.35 | 0.18-0.57 | undecided |


## Morris screening (elementary effects of the run margin, per unit of calibrated range)

| parameter | range | rule |
|---|---|---|
| main_demand | 2400..4200 | nominal +- 1.25 x distance to nearest boundary (859.5) |
| ramp_demand | 354..846 | nominal +- 1.25 x distance to nearest boundary (197.0) |
| truck_share | 0..0.25 | full range (no verdict flip in one-at-a-time) |
| incident_start | 300..1200 | full range (no verdict flip in one-at-a-time) |
| incident_duration | 0..263 | nominal +- 1.25 x distance to nearest boundary (210.5) |
| sigma | 0..0.9 | full range (no verdict flip in one-at-a-time) |

### controller `fixed` (84 runs, 45 not-PASS, 0 INVALID)

| parameter | mu* | mu | sigma | sigma_seed | n |
|---|---|---|---|---|---|
| main_demand | 1.5857 | -1.5857 | 1.0729 | 0.3690 | 12 |
| sigma | 1.4887 | -1.3171 | 1.6589 | 0.3472 | 12 |
| ramp_demand | 1.0469 | -0.7021 | 1.0883 | 0.4832 | 12 |
| incident_duration | 0.5494 | -0.5494 | 0.5719 | 0.0434 | 12 |
| truck_share | 0.4646 | -0.4646 | 0.3309 | 0.0335 | 12 |
| incident_start | 0.2103 | -0.1681 | 0.2919 | 0.1475 | 12 |

### controller `alinea` (84 runs, 37 not-PASS, 0 INVALID)

| parameter | mu* | mu | sigma | sigma_seed | n |
|---|---|---|---|---|---|
| main_demand | 2.0358 | -2.0358 | 1.7523 | 0.8658 | 12 |
| sigma | 1.2300 | -0.9766 | 1.4923 | 0.3197 | 12 |
| incident_duration | 1.0507 | -1.0507 | 0.7986 | 0.2397 | 12 |
| truck_share | 0.9777 | -0.8236 | 1.3902 | 0.4893 | 12 |
| incident_start | 0.8292 | -0.7524 | 1.4319 | 0.5446 | 12 |
| ramp_demand | 0.7730 | -0.5873 | 1.1166 | 0.4629 | 12 |


## One-at-a-time sensitivity (paired seeds; delta of run margin vs nominal)

### controller `fixed`

| parameter | lo value | mean delta (lo) | verdicts (lo) | hi value | mean delta (hi) | verdicts (hi) | influence | flip |
|---|---|---|---|---|---|---|---|---|
| ramp_demand | 300 | 0.0255 | PASS/PASS/PASS/PASS/PASS | 1200 | -5.2563 | FAIL/FAIL/FAIL/FAIL/FAIL | 5.2563 | hi |
| incident_duration | 0 | 0 | PASS/PASS/PASS/PASS/PASS | 900 | -4.6377 | FAIL/FAIL/FAIL/FAIL/FAIL | 4.6377 | hi |
| main_demand | 2400 | 0.0743 | PASS/PASS/PASS/PASS/PASS | 4200 | -0.5604 | PASS/PASS/FAIL/FAIL/FAIL | 0.5604 | hi |
| truck_share | 0 | 0.125 | PASS/PASS/PASS/PASS/PASS | 0.25 | -0.1029 | PASS/PASS/PASS/PASS/PASS | 0.125 | - |
| sigma | 0 | 0.0198 | PASS/PASS/PASS/PASS/PASS | 0.9 | -0.0964 | PASS/PASS/PASS/FAIL/PASS | 0.0964 | - |
| incident_start | 300 | 0 | PASS/PASS/PASS/PASS/PASS | 1200 | 0 | PASS/PASS/PASS/PASS/PASS | 0 | - |

### controller `alinea`

| parameter | lo value | mean delta (lo) | verdicts (lo) | hi value | mean delta (hi) | verdicts (hi) | influence | flip |
|---|---|---|---|---|---|---|---|---|
| incident_duration | 0 | 0 | PASS/PASS/PASS/PASS/PASS | 900 | -4.2648 | FAIL/FAIL/FAIL/FAIL/FAIL | 4.2648 | hi |
| main_demand | 2400 | 0.0802 | PASS/PASS/PASS/PASS/PASS | 4200 | -0.5313 | PASS/PASS/FAIL/FAIL/FAIL | 0.5313 | hi |
| truck_share | 0 | 0.1278 | PASS/PASS/PASS/PASS/PASS | 0.25 | -0.1018 | PASS/PASS/PASS/PASS/PASS | 0.1278 | - |
| ramp_demand | 300 | 0.0307 | PASS/PASS/PASS/PASS/PASS | 1200 | -0.1181 | PASS/PASS/PASS/PASS/PASS | 0.1181 | - |
| sigma | 0 | 0.0232 | PASS/PASS/PASS/PASS/PASS | 0.9 | -0.0581 | PASS/PASS/PASS/PASS/PASS | 0.0581 | - |
| incident_start | 300 | 0 | PASS/PASS/PASS/PASS/PASS | 1200 | 0 | PASS/PASS/PASS/PASS/PASS | 0 | - |

## Agent decisions

| # | action | policy | runs before | why |
|---|---|---|---|---|
| 1 | `probe:ramp_demand:hi` | deterministic | 125 | largest paired |mean delta margin| among unprobed directions with a verdict flip (probe:ramp_demand:hi) |
| 2 | `probe:incident_duration:hi` | deterministic | 150 | largest paired |mean delta margin| among unprobed directions with a verdict flip (probe:incident_duration:hi) |
| 3 | `probe:main_demand:hi` | deterministic | 200 | largest paired |mean delta margin| among unprobed directions with a verdict flip (probe:main_demand:hi) |

## Claims and evidence

Each claim's numbers are recomputed from the listed runs in `runs.jsonl` by `python scripts/verify_results.py`.

**C1.** Nominal scenario, controller 'fixed': mean over 5 seeds.

values: `{"collisions": 0, "mean_delay_s": 14.8, "merge_speed_kmh": 97.16, "ramp_p95_delay_s": 46.91, "ramp_queue_max_veh": 11.8, "teleports": 0, "throughput_veh": 1695.8, "ttc_per_1000veh": 0.0, "verdicts": ["PASS", "PASS", "PASS", "PASS", "PASS"]}`

evidence (5 runs): `09de1b65ac99`, `4224d1e7fafd`, `6dccacdae032`, `8107cc25c975`, `dbec7f1de5b6`

**C2.** Nominal scenario, controller 'alinea': mean over 5 seeds.

values: `{"collisions": 0, "mean_delay_s": 13.65, "merge_speed_kmh": 96.67, "ramp_p95_delay_s": 25.65, "ramp_queue_max_veh": 8.8, "teleports": 0, "throughput_veh": 1695.8, "ttc_per_1000veh": 0.0, "verdicts": ["PASS", "PASS", "PASS", "PASS", "PASS"]}`

evidence (5 runs): `162fa6351870`, `1cab0918e077`, `51dd7aabb8cb`, `576fab337e71`, `5da8cb55bbb9`

**C3.** Nominal scenario, controller 'none': mean over 5 seeds.

values: `{"collisions": 0, "mean_delay_s": 13.54, "merge_speed_kmh": 96.79, "ramp_p95_delay_s": 25.47, "ramp_queue_max_veh": 8.8, "teleports": 0, "throughput_veh": 1695.8, "ttc_per_1000veh": 0.0, "verdicts": ["PASS", "PASS", "PASS", "PASS", "PASS"]}`

evidence (5 runs): `00e8f793a37e`, `49405911a80a`, `68f9ed45e187`, `80c052907d12`, `e75e7c8bac3f`

**C4.** One-at-a-time (paired seeds), controller 'fixed': the most influential parameter is 'ramp_demand'; moving it to hi=1200 changes the run margin by -5.2563 on average (per-seed range -5.5804..-4.8591).

values: `{"level": "hi", "max_delta_margin": -4.8591, "mean_delta_margin": -5.2563, "min_delta_margin": -5.5804, "param": "ramp_demand", "value": 1200, "verdicts": ["FAIL", "FAIL", "FAIL", "FAIL", "FAIL"]}`

evidence (10 runs): `09de1b65ac99`, `4224d1e7fafd`, `560af3bd5974`, `5b69e0a7a7c3`, `6dccacdae032`, `8107cc25c975`, `8f292be11ec7`, `c945aff5b69e`, `d02047fc7541`, `dbec7f1de5b6`

**C5.** One-at-a-time (paired seeds), controller 'alinea': the most influential parameter is 'incident_duration'; moving it to hi=900 changes the run margin by -4.2648 on average (per-seed range -5.2067..-3.4112).

values: `{"level": "hi", "max_delta_margin": -3.4112, "mean_delta_margin": -4.2648, "min_delta_margin": -5.2067, "param": "incident_duration", "value": 900, "verdicts": ["FAIL", "FAIL", "FAIL", "FAIL", "FAIL"]}`

evidence (10 runs): `162fa6351870`, `1cab0918e077`, `51dd7aabb8cb`, `5224ba9c9247`, `576fab337e71`, `5da8cb55bbb9`, `633dc142a9c6`, `7a2625efd310`, `8983b24c47f5`, `a9f8909b7436`

**C6.** Boundary, controller 'fixed' along 'ramp_demand' (veh/h), other parameters nominal: majority PASS at 788, majority not-PASS at 806 (bisection width 18, tolerance 25, monotone over 8 evaluated points).

values: `{"controller": "fixed", "criteria_violated_at_fail": ["ramp_p95_delay_s"], "fail_verdicts": ["FAIL", "PASS", "FAIL", "FAIL", "FAIL"], "first_fail": 806, "last_pass": 788, "param": "ramp_demand", "pass_verdicts": ["PASS", "PASS", "FAIL", "FAIL", "PASS"]}`

evidence (10 runs): `1fd401bcc3eb`, `26857bdc104e`, `26f74ebf780f`, `8f8c45969a37`, `999513ac4970`, `aa0a5b54f6b1`, `b6db6ce7dc87`, `c381a31dae9f`, `c863b6f279ca`, `e99d0e2eb872`

**C7.** Boundary, controller 'fixed' along 'incident_duration' (s), other parameters nominal: majority PASS at 225, majority not-PASS at 254 (bisection width 29, tolerance 30, monotone over 7 evaluated points).

values: `{"controller": "fixed", "criteria_violated_at_fail": ["ramp_p95_delay_s", "ttc_per_1000veh"], "fail_verdicts": ["PASS", "FAIL", "FAIL", "PASS", "FAIL"], "first_fail": 254, "last_pass": 225, "param": "incident_duration", "pass_verdicts": ["PASS", "PASS", "FAIL", "PASS", "FAIL"]}`

evidence (10 runs): `05da049a6203`, `1a9fe3581d59`, `200fa7eabea0`, `20bc5dfb77c5`, `3cd0c106d771`, `6ceb47f37d45`, `7a80b2c6e822`, `a56d08b00c29`, `b177c9de0bc6`, `e7332f22383d`

**C8.** Boundary, controller 'alinea' along 'incident_duration' (s), other parameters nominal: majority PASS at 196, majority not-PASS at 225 (bisection width 29, tolerance 30, monotone over 7 evaluated points).

values: `{"controller": "alinea", "criteria_violated_at_fail": ["ramp_p95_delay_s", "ttc_per_1000veh"], "fail_verdicts": ["PASS", "PASS", "FAIL", "FAIL", "FAIL"], "first_fail": 225, "last_pass": 196, "param": "incident_duration", "pass_verdicts": ["PASS", "PASS", "FAIL", "PASS", "FAIL"]}`

evidence (10 runs): `2f14207208c4`, `498a9c62e32b`, `672fd7385dfe`, `6898b7c9e721`, `6e35a6bf8b3a`, `796b15404388`, `8cf7269f2da4`, `983cc4ce5740`, `bee2fe6e2ac5`, `d7f3c185f20c`

**C9.** Boundary, controller 'fixed' along 'main_demand' (veh/h), other parameters nominal: majority PASS at 4044, majority not-PASS at 4075 (bisection width 31, tolerance 50, monotone over 8 evaluated points).

values: `{"controller": "fixed", "criteria_violated_at_fail": ["mean_delay_s"], "fail_verdicts": ["PASS", "PASS", "FAIL", "FAIL", "FAIL"], "first_fail": 4075, "last_pass": 4044, "param": "main_demand", "pass_verdicts": ["PASS", "PASS", "FAIL", "FAIL", "PASS"]}`

evidence (10 runs): `085fcd30041a`, `22c4c180b92a`, `35a427f672d3`, `4a6721522e6d`, `5727f57c6b03`, `5735e19acc46`, `720c8fd2cd5d`, `adaccb634de5`, `dee507fd2fb3`, `dfe0cac3d9fb`

**C10.** Boundary, controller 'alinea' along 'main_demand' (veh/h), other parameters nominal: majority PASS at 4044, majority not-PASS at 4075 (bisection width 31, tolerance 50, monotone over 8 evaluated points).

values: `{"controller": "alinea", "criteria_violated_at_fail": ["mean_delay_s"], "fail_verdicts": ["PASS", "PASS", "FAIL", "FAIL", "FAIL"], "first_fail": 4075, "last_pass": 4044, "param": "main_demand", "pass_verdicts": ["PASS", "PASS", "FAIL", "FAIL", "PASS"]}`

evidence (10 runs): `04498198b89b`, `0e90fa89f39c`, `0ffbe6a5278b`, `42156a89a688`, `4fb5d9502efe`, `62cd4a0567bc`, `684cf981d116`, `9015246c364c`, `ae7b578fad66`, `cd76d11cd57c`

**C11.** Refined boundary, controller 'fixed' along 'ramp_demand' (veh/h): pass rate over 20 paired seeds at 5 values; Wilson 95% band [697, 847], 50% crossing of the isotonic fit x50=772.0 (5-seed bisection gave [788, 806]).

values: `{"band": [697, 847], "band_closed": true, "bisection": [788, 806], "controller": "fixed", "monotone_within_ci": true, "param": "ramp_demand", "points": [{"class": "pass", "n": 20, "passes": 19, "rate": 0.95, "wilson95": [0.7639, 0.9911], "x": 697}, {"class": "undecided", "n": 20, "passes": 13, "rate": 0.65, "wilson95": [0.4329, 0.8188], "x": 747}, {"class": "undecided", "n": 20, "passes": 7, "rate": 0.35, "wilson95": [0.1812, 0.5671], "x": 797}, {"class": "fail", "n": 20, "passes": 0, "rate": 0.0, "wilson95": [0.0, 0.1611], "x": 847}, {"class": "fail", "n": 20, "passes": 0, "rate": 0.0, "wilson95": [0.0, 0.1611], "x": 897}], "x50": 772.0}`

evidence (100 runs): `0190e68f226b`, `020ea211e3a4`, `031387f2f8d9`, `03b290f8d5ab`, `0504866a07c2`, `0861ab65fdd7`, `0c8c9964c985`, `13a3a6b1029d`, `1ccb74a33053`, `22a698475d82`, `256501e718bc`, `2636d4833bc5` (+88 more)

**C12.** Refined boundary, controller 'fixed' along 'incident_duration' (s): pass rate over 20 paired seeds at 5 values; Wilson 95% band [120, 300], 50% crossing of the isotonic fit x50=210.0 (5-seed bisection gave [225, 254]).

values: `{"band": [120, 300], "band_closed": true, "bisection": [225, 254], "controller": "fixed", "monotone_within_ci": true, "param": "incident_duration", "points": [{"class": "pass", "n": 20, "passes": 18, "rate": 0.9, "wilson95": [0.699, 0.9721], "x": 120}, {"class": "undecided", "n": 20, "passes": 14, "rate": 0.7, "wilson95": [0.481, 0.8545], "x": 180}, {"class": "undecided", "n": 20, "passes": 6, "rate": 0.3, "wilson95": [0.1455, 0.519], "x": 240}, {"class": "fail", "n": 20, "passes": 3, "rate": 0.15, "wilson95": [0.0524, 0.3604], "x": 300}, {"class": "fail", "n": 20, "passes": 0, "rate": 0.0, "wilson95": [0.0, 0.1611], "x": 360}], "x50": 210.0}`

evidence (100 runs): `01a29a43155b`, `0206dd36cf13`, `05407e887f7b`, `05540a1408a0`, `0915594e5889`, `0a1bea2eb62f`, `0b2c5211b6b3`, `0b3fc4ea2681`, `148e62efa0f1`, `1b2e134518f0`, `1b6be5a2f657`, `21430c342f35` (+88 more)

**C13.** Refined boundary, controller 'alinea' along 'incident_duration' (s): pass rate over 20 paired seeds at 5 values; Wilson 95% band [150, 270], 50% crossing of the isotonic fit x50=198.0 (5-seed bisection gave [196, 225]).

values: `{"band": [150, 270], "band_closed": true, "bisection": [196, 225], "controller": "alinea", "monotone_within_ci": true, "param": "incident_duration", "points": [{"class": "pass", "n": 20, "passes": 20, "rate": 1.0, "wilson95": [0.8389, 1.0], "x": 90}, {"class": "pass", "n": 20, "passes": 18, "rate": 0.9, "wilson95": [0.699, 0.9721], "x": 150}, {"class": "undecided", "n": 20, "passes": 8, "rate": 0.4, "wilson95": [0.2188, 0.6134], "x": 210}, {"class": "fail", "n": 20, "passes": 4, "rate": 0.2, "wilson95": [0.0807, 0.416], "x": 270}, {"class": "fail", "n": 20, "passes": 1, "rate": 0.05, "wilson95": [0.0089, 0.2361], "x": 330}], "x50": 198.0}`

evidence (100 runs): `0161e55fbb63`, `02edcee68c00`, `0a4e6b055f47`, `0bd065e9fe88`, `10d870b4031b`, `126b5fc0eaa5`, `13b649bc3023`, `1a3aa2212ff2`, `1c03cd242693`, `1c2cf1eef43c`, `1f8ecf14ae7d`, `1fe4665c9b70` (+88 more)

**C14.** Refined boundary, controller 'fixed' along 'main_demand' (veh/h): pass rate over 20 paired seeds at 5 values; Wilson 95% band [3860, None], 50% crossing of the isotonic fit x50=4085.0 (5-seed bisection gave [4044, 4075]).

values: `{"band": [3860, null], "band_closed": false, "bisection": [4044, 4075], "controller": "fixed", "monotone_within_ci": true, "param": "main_demand", "points": [{"class": "pass", "n": 20, "passes": 19, "rate": 0.95, "wilson95": [0.7639, 0.9911], "x": 3860}, {"class": "undecided", "n": 20, "passes": 14, "rate": 0.7, "wilson95": [0.481, 0.8545], "x": 3960}, {"class": "undecided", "n": 20, "passes": 11, "rate": 0.55, "wilson95": [0.3421, 0.7418], "x": 4060}, {"class": "undecided", "n": 20, "passes": 7, "rate": 0.35, "wilson95": [0.1812, 0.5671], "x": 4160}, {"class": "undecided", "n": 20, "passes": 7, "rate": 0.35, "wilson95": [0.1812, 0.5671], "x": 4200}], "x50": 4085.0}`

evidence (100 runs): `024d3511b830`, `027f86bf8764`, `03d5a253c0e5`, `047b9507c72a`, `0610f9647832`, `07a7509679ca`, `0d1fdde655ac`, `0e2f8f06c51f`, `105fe350c59c`, `1112612065c9`, `11ee890705b8`, `12b44d208ccb` (+88 more)

**C15.** Refined boundary, controller 'alinea' along 'main_demand' (veh/h): pass rate over 20 paired seeds at 5 values; Wilson 95% band [3960, None], 50% crossing of the isotonic fit x50=4096.36 (5-seed bisection gave [4044, 4075]).

values: `{"band": [3960, null], "band_closed": false, "bisection": [4044, 4075], "controller": "alinea", "monotone_within_ci": true, "param": "main_demand", "points": [{"class": "pass", "n": 20, "passes": 18, "rate": 0.9, "wilson95": [0.699, 0.9721], "x": 3860}, {"class": "pass", "n": 20, "passes": 15, "rate": 0.75, "wilson95": [0.5313, 0.8881], "x": 3960}, {"class": "undecided", "n": 20, "passes": 12, "rate": 0.6, "wilson95": [0.3866, 0.7812], "x": 4060}, {"class": "undecided", "n": 20, "passes": 6, "rate": 0.3, "wilson95": [0.1455, 0.519], "x": 4160}, {"class": "undecided", "n": 20, "passes": 7, "rate": 0.35, "wilson95": [0.1812, 0.5671], "x": 4200}], "x50": 4096.36}`

evidence (100 runs): `001981e1261c`, `00c8e3a5a392`, `019198f104a1`, `0348c47243ce`, `049fccdc4c1d`, `09ec26ec1d6a`, `0c281ad8da4c`, `0dfad7e1aba4`, `0fe91baf4d1c`, `166d61ed5b39`, `16c5625e4aeb`, `1722163b12e4` (+88 more)

**C16.** Morris screening (run margin; r=6 trajectories, 4 levels, paired seeds [1, 2], calibrated ranges), controller 'fixed': ranking by mu* ['main_demand', 'sigma', 'ramp_demand', 'incident_duration', 'truck_share', 'incident_start'].

values: `{"invalid_runs": 0, "not_pass_runs": 45, "ranking": ["main_demand", "sigma", "ramp_demand", "incident_duration", "truck_share", "incident_start"], "runs": 84, "stats": {"incident_duration": {"mu": -0.5494, "mu_star": 0.5494, "n": 12, "sigma": 0.5719, "sigma_seed": 0.0434}, "incident_start": {"mu": -0.1681, "mu_star": 0.2103, "n": 12, "sigma": 0.2919, "sigma_seed": 0.1475}, "main_demand": {"mu": -1.5857, "mu_star": 1.5857, "n": 12, "sigma": 1.0729, "sigma_seed": 0.369}, "ramp_demand": {"mu": -0.7021, "mu_star": 1.0469, "n": 12, "sigma": 1.0883, "sigma_seed": 0.4832}, "sigma": {"mu": -1.3171, "mu_star": 1.4887, "n": 12, "sigma": 1.6589, "sigma_seed": 0.3472}, "truck_share": {"mu": -0.4646, "mu_star": 0.4646, "n": 12, "sigma": 0.3309, "sigma_seed": 0.0335}}}`

evidence (84 runs): `089736a629e7`, `0a5eb7998716`, `1037aef7fae6`, `1461e32945be`, `1603370359f5`, `1775eb6a7734`, `1a9fe31bef96`, `1c28a385a401`, `1cbcc89977e1`, `1e8079399c70`, `1e8ae87aade4`, `211946aa25ac` (+72 more)

**C17.** Morris screening (run margin; r=6 trajectories, 4 levels, paired seeds [1, 2], calibrated ranges), controller 'alinea': ranking by mu* ['main_demand', 'sigma', 'incident_duration', 'truck_share', 'incident_start', 'ramp_demand'].

values: `{"invalid_runs": 0, "not_pass_runs": 37, "ranking": ["main_demand", "sigma", "incident_duration", "truck_share", "incident_start", "ramp_demand"], "runs": 84, "stats": {"incident_duration": {"mu": -1.0507, "mu_star": 1.0507, "n": 12, "sigma": 0.7986, "sigma_seed": 0.2397}, "incident_start": {"mu": -0.7524, "mu_star": 0.8292, "n": 12, "sigma": 1.4319, "sigma_seed": 0.5446}, "main_demand": {"mu": -2.0358, "mu_star": 2.0358, "n": 12, "sigma": 1.7523, "sigma_seed": 0.8658}, "ramp_demand": {"mu": -0.5873, "mu_star": 0.773, "n": 12, "sigma": 1.1166, "sigma_seed": 0.4629}, "sigma": {"mu": -0.9766, "mu_star": 1.23, "n": 12, "sigma": 1.4923, "sigma_seed": 0.3197}, "truck_share": {"mu": -0.8236, "mu_star": 0.9777, "n": 12, "sigma": 1.3902, "sigma_seed": 0.4893}}}`

evidence (84 runs): `04c206a60f7e`, `05fe93de4ece`, `0a565488e769`, `0d5d45c68031`, `0e7e97aabd8e`, `0e7eb77928dc`, `197b013f54ce`, `1a629917ed00`, `1b6af9acdb39`, `1dc5e02d2aa9`, `22aacce1066c`, `22e939a95345` (+72 more)

**C18.** Failure modes over all runs: number of runs violating each criterion.

values: `{"mean_delay_s": 226, "merge_speed_kmh": 44, "ramp_p95_delay_s": 244, "runs": 908, "ttc_per_1000veh": 184}`

evidence (413 runs): `001981e1261c`, `00c8e3a5a392`, `0190e68f226b`, `01a29a43155b`, `0206dd36cf13`, `031387f2f8d9`, `0348c47243ce`, `03d5a253c0e5`, `0504866a07c2`, `05407e887f7b`, `05540a1408a0`, `05da049a6203` (+401 more)

**C19.** Validity: runs with teleports or collisions (excluded from PASS/FAIL, counted as not-PASS).

values: `{"collision_lanes": {}, "collisions": 0, "invalid_by_phase": {}, "invalid_runs": 0, "invalid_with_incident": 0, "runs": 908, "teleports": 0}`

evidence (0 runs): 

