"""KPI parsing on a hand-written fixture whose expected values are computed by hand."""
from pathlib import Path

import pytest

from simeval import kpi

FIX = Path(__file__).parent / "fixtures" / "run"


def test_tripinfo_counts_timeloss_plus_departdelay():
    t = kpi.parse_tripinfo(FIX / "tripinfo.xml")
    # delays: 2+8, 0+30, 50+10, 0+5  -> 10, 30, 60, 5
    assert t["vehicles"] == 4
    assert t["arrived"] == 3          # arrival="-1" is an unfinished trip
    assert t["total_delay_s"] == pytest.approx(105.0)
    assert t["ramp_vehicles"] == 2
    assert t["ramp_p95_delay_s"] == pytest.approx(60.0)  # nearest rank of [5, 60]


def test_p95_is_nearest_rank():
    assert kpi._p95(list(range(1, 21))) == 19   # ceil(0.95*20)=19th value
    assert kpi._p95(list(range(1, 101))) == 95
    assert kpi._p95([7.0]) == 7.0
    assert kpi._p95([]) == 0.0


def test_merge_speed_is_flow_weighted_and_stops_at_demand_end():
    # (10*20 + 30*30) / 40 = 27.5 m/s; the empty interval, loop_down and t>=1800 are ignored
    assert kpi.parse_merge_speed(FIX / "e1_merge.xml") == pytest.approx(27.5 * 3.6)


def test_ramp_queue_is_max_vehicle_number():
    assert kpi.parse_ramp_queue(FIX / "e2_ramp.xml") == 31


def test_ssm_threshold_is_strict_and_ignores_na():
    # values 1.49 (yes), 1.50 (no: not strictly below), NA (no), 0.20 (yes), 2.90 (no)
    assert kpi.parse_ssm(FIX / "ssm.xml") == 2
    assert kpi.parse_ssm(FIX / "ssm.xml", threshold=3.0) == 4


def test_stats_and_collisions():
    s = kpi.parse_stats(FIX / "stats.xml")
    assert (s["teleports"], s["collisions"], s["not_inserted"], s["emergency_braking"]) == (2, 1, 1, 3)
    assert kpi.parse_collisions(FIX / "collisions.xml") == ["ramp_in_0"]
    assert kpi.parse_collisions(FIX / "does_not_exist.xml") == []


def test_compute_kpis_end_to_end():
    k = kpi.compute_kpis(FIX)
    assert k == {
        "vehicles": 4,
        "throughput_veh": 3,
        "total_delay_veh_h": 0.029,
        "mean_delay_s": 26.25,
        "merge_speed_kmh": 99.0,
        "ramp_queue_max_veh": 31,
        "ramp_p95_delay_s": 60.0,
        "ttc_conflicts": 2,
        "ttc_per_1000veh": 500.0,
        "teleports": 2,
        "collisions": 1,
        "not_inserted": 1,
        "emergency_braking": 3,
        "collision_lanes": ["ramp_in_0"],
    }
