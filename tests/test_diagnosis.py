"""SUMO warning-log parsing and collision attribution (lines copied from real v1 re-runs)."""
from simeval.diagnosis import attribute, config_summary, parse_log, same_run, summarize

LOG = """\
Warning: Missing yellow phase in tlLogic 'r_meter', program 'meter' for tl-index 0 when switching to phase 1.
Warning: Vehicle 'ramp_1.40' performs emergency stop at the end of lane 'ramp_in_0' because of a red traffic light (decel=-14.36, offset=0.75), time=717.50.
Warning: Vehicle 'main_1.329' performs emergency braking on lane 'main_mid_0' with decel=9.00, wished=4.50, severity=1.00, time=806.00.
Warning: Vehicle 'main_1.329' performs emergency stop at the end of lane 'main_mid_0' because there is no connection to the next edge (decel=-29.99, offset=8.61), time=806.00.
Warning: Vehicle 'ramp_1.47'; collision with vehicle 'main_1.329', lane='main_mid_0', gap=-0.22, time=808.00, stage=move.
Warning: Vehicle 'ramp_1.132' performs emergency stop at the end of lane 'ramp_in_0' because of a red traffic light (decel=-19.36, offset=5.75), time=1137.00.
Warning: Vehicle 'ramp_1.133'; collision with vehicle 'ramp_1.132', lane='ramp_in_0', gap=-0.79, time=1139.00, stage=move.
Warning: Vehicle 'x'; collision with vehicle 'y', lane='merge_1', gap=-0.10, time=1500.00, stage=move.
Warning: Vehicle 'y' performs emergency stop at the end of lane 'merge_1' because of a red traffic light (decel=-9.00, offset=0.10), time=1400.00.
"""


def test_parse_counts_and_times():
    p = parse_log(LOG)
    assert len(p["collisions"]) == 3 and len(p["emergency_stops"]) == 4
    assert p["emergency_stops"][1] == {"vehicle": "main_1.329", "lane": "main_mid_0", "reason": "no_connection",
                                       "decel": -29.99, "time": 806.0}
    assert p["collisions"][0]["time"] == 808.0 and p["collisions"][0]["gap"] == -0.22


def test_each_collision_is_attributed_to_the_victims_recent_emergency_stop():
    rows = attribute(parse_log(LOG))
    assert [r["cause"] for r in rows] == ["no_connection", "red_light", "none"]  # y stopped 100 s earlier
    assert rows[0]["victim_stop_time"] == 806.0 and rows[0]["victim_stop_decel"] == -29.99


def test_summary_counts_by_reason():
    s = summarize(LOG)
    assert s["emergency_stops_by_reason"] == {"no_connection": 1, "red_light": 3}
    assert s["emergency_stop_times"]["red_light"] == [717.5, 1137.0, 1400.0]


def test_config_summary_and_same_run():
    recs = [{"scenario": {"incident_start": 600}, "kpis": {"collisions": 2, "teleports": 0, "mean_delay_s": 10.0,
                                                          "incident_onset_s": 607.0},
             "log": {"emergency_stops_by_reason": {"red_light": 3}}},
            {"scenario": {"incident_start": 600}, "kpis": {"collisions": 0, "teleports": 1, "mean_delay_s": 20.0,
                                                          "incident_onset_s": 630.0},
             "log": {"emergency_stops_by_reason": {"no_connection": 1}}}]
    s = config_summary(recs)
    assert (s["runs"], s["runs_with_collision"], s["collisions"], s["teleports"]) == (2, 1, 2, 1)
    assert s["emergency_stops"] == {"no_connection": 1, "red_light": 3}
    assert s["incident_onset_delay_s"] == {"n": 2, "median": 18.5, "max": 30.0, "min": 7.0}
    old = {"tripinfo_sha256": "a", "kpis": {"x": 1}}
    assert same_run({"tripinfo_sha256": "a", "kpis": {"x": 1, "new": 5}}, old)
    assert not same_run({"tripinfo_sha256": "a", "kpis": {"x": 2}}, old)
    assert not same_run({"tripinfo_sha256": "b", "kpis": {"x": 1}}, old)
