"""Needs SUMO (skipped otherwise). Network reproducibility and run determinism."""
import sys
from pathlib import Path

import pytest

from simeval import sumo_env
from simeval.evaluator import _run_one
from simeval.network import build_network

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(not sumo_env.available(), reason="SUMO not installed")


def test_network_is_byte_reproducible(tmp_path):
    a = build_network(tmp_path / "a").read_bytes()
    b = build_network(tmp_path / "b").read_bytes()
    assert a == b
    assert b"generated on" not in a
    if sumo_env.sumo_version() == "1.24.0":  # the committed file was built with 1.24.0
        assert a == (ROOT / "network" / "merge.net.xml").read_bytes()


def test_same_seed_same_result_different_seed_different_result(tmp_path):
    from simeval.scenario import NOMINAL

    net = str(ROOT / "network" / "merge.net.xml")
    s1 = NOMINAL.with_(controller="alinea", seed=11)
    r1 = _run_one((s1.canonical(), net, str(tmp_path / "x"), False))
    r2 = _run_one((s1.canonical(), net, str(tmp_path / "y"), False))
    r3 = _run_one((NOMINAL.with_(controller="alinea", seed=12).canonical(), net, str(tmp_path / "z"), False))
    assert r1["kpis"] == r2["kpis"] and r1["tripinfo_sha256"] == r2["tripinfo_sha256"]
    assert r1["tripinfo_sha256"] != r3["tripinfo_sha256"]
    assert r1["kpis"]["vehicles"] > 1000 and r1["kpis"]["teleports"] == 0


def test_v1_invalid_run_reproduces_with_legacy_closure_and_is_clean_with_the_fix(tmp_path):
    """v1 run 6d30a934cf4b collided on main_mid_0 at the closure instant; the stall method does not."""
    from simeval.runner import DEFAULT_OPTIONS, LEGACY_OPTIONS
    from simeval.scenario import Scenario

    s = Scenario(main_demand=3038, ramp_demand=394, truck_share=0.099, incident_start=806, incident_duration=206,
                 sigma=0.4688, controller="fixed", seed=1)
    assert s.id == "6d30a934cf4b"
    net = str(ROOT / "network" / "merge.net.xml")
    legacy = _run_one((s.canonical(), net, str(tmp_path / "l"), False, {**LEGACY_OPTIONS.as_dict(), "log_warnings": True}))
    # the mechanism: disallowing the lane forces impossible stops at the closure instant
    assert 806.0 in legacy["log"]["emergency_stop_times"]["no_connection"]
    if sys.platform == "win32":  # v1 was produced on Windows; there the collision itself reproduces
        assert legacy["kpis"]["collision_lanes"] == ["main_mid_0"]
        assert legacy["log"]["collisions"][0]["cause"] == "no_connection"
        assert legacy["log"]["collisions"][0]["victim_stop_time"] == 806.0
    fixed = _run_one((s.canonical(), net, str(tmp_path / "f"), False, {**DEFAULT_OPTIONS.as_dict(), "log_warnings": True}))
    assert fixed["kpis"]["collisions"] == 0 and fixed["kpis"]["teleports"] == 0
    assert fixed["log"]["emergency_stops_by_reason"].get("no_connection", 0) == 0
    assert 806 <= fixed["kpis"]["incident_onset_s"] <= 806 + 60
