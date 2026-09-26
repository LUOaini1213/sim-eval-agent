"""Incident methods: which TraCI actions happen when, and who may be told to stall."""
import pytest

from simeval.runner import (LEGACY_OPTIONS, STALL_MARGIN_M, SimOptions, incident_events, stall_candidates,
                            sumo_cmd)
from simeval.scenario import BLOCKER_ID, NOMINAL, incident_routes_xml, routes_xml

INC = NOMINAL.with_(incident_start=600, incident_duration=200)


def test_default_is_stall_with_amber_and_legacy_reproduces_v1():
    assert SimOptions().incident_method == "stall" and SimOptions().amber_s > 0
    assert LEGACY_OPTIONS.incident_method == "traci_disallow" and LEGACY_OPTIONS.amber_s == 0
    with pytest.raises(ValueError):
        SimOptions(incident_method="teleport")


def test_events_per_method():
    assert incident_events(INC, SimOptions("stall")) == {600.0: [("stall", 800.0)]}
    assert incident_events(INC, SimOptions("blocker")) == {}
    assert incident_events(INC, SimOptions("traci_disallow")) == {
        600.0: [("disallow", ["passenger", "truck"])], 800.0: [("disallow", [])]}
    vss = incident_events(INC, SimOptions("vss_disallow"))
    assert vss[540.0] == [("speed", 16.67)] and ("speed", None) in vss[800.0]
    assert incident_events(NOMINAL, SimOptions("stall")) == {}          # no incident, no events


def test_stall_only_picks_vehicles_that_can_stop_with_ordinary_braking():
    mid = 346.0
    vehs = [
        ("far", "main_mid_0", 0.0, 33.0, 4.5),           # 446 m away: fine
        ("near", "main_mid_0", 300.0, 33.0, 4.5),        # 146 m < 121 + 5? 146 >= 126 -> fine, nearest
        ("tooclose", "incident_0", 20.0, 30.0, 4.5),     # 80 m < 100 + 5 m needed
        ("slow", "incident_0", 90.0, 5.0, 4.5),          # 10 m >= 2.8 + 5: fine, nearest of all
        ("past", "incident_0", 150.0, 0.0, 4.5),         # already beyond the stop
        ("otherlane", "main_mid_1", 300.0, 10.0, 4.5),
    ]
    got = stall_candidates(vehs, mid)
    assert [v for _, v in got] == ["slow", "near", "far"]
    d, v = got[0]
    assert d == pytest.approx(10.0)
    # exactly at the limit is allowed, 1 cm short is not
    v2 = 20.0
    need = v2 * v2 / (2 * 4.5) + STALL_MARGIN_M
    assert stall_candidates([("a", "incident_0", 100.0 - need, v2, 4.5)], mid)
    assert not stall_candidates([("a", "incident_0", 100.0 - need + 0.01, v2, 4.5)], mid)


def test_blocker_goes_to_its_own_route_file():
    assert BLOCKER_ID not in routes_xml(INC)
    assert BLOCKER_ID in incident_routes_xml(INC, "blocker")
    assert BLOCKER_ID in incident_routes_xml(INC, "blocker_insert")
    assert BLOCKER_ID not in incident_routes_xml(INC, "stall")
    assert BLOCKER_ID not in incident_routes_xml(NOMINAL, "blocker")
    cmd = sumo_cmd(INC)
    assert cmd[cmd.index("--route-files") + 1] == "routes.rou.xml,incident.rou.xml"
    assert "--stop-output" in cmd
