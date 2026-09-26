import pytest

from simeval import criteria
from simeval.criteria import FAIL, INVALID, PASS

GOOD = {"mean_delay_s": 20.0, "ramp_p95_delay_s": 40.0, "merge_speed_kmh": 95.0,
        "ttc_per_1000veh": 0.0, "teleports": 0, "collisions": 0}


def test_all_good_passes_with_positive_margin():
    e = criteria.evaluate(GOOD)
    assert e["verdict"] == PASS and e["failed"] == [] and e["margin"] > 0


@pytest.mark.parametrize("kpi,at_limit,beyond", [
    ("mean_delay_s", 60.0, 60.01),
    ("ramp_p95_delay_s", 120.0, 120.01),
    ("ttc_per_1000veh", 10.0, 10.001),
    ("merge_speed_kmh", 75.0, 74.99),
])
def test_limits_are_inclusive_and_violations_fail(kpi, at_limit, beyond):
    ok = criteria.evaluate({**GOOD, kpi: at_limit})
    assert ok["verdict"] == PASS
    assert ok["margins"][kpi] == pytest.approx(0.0)
    bad = criteria.evaluate({**GOOD, kpi: beyond})
    assert bad["verdict"] == FAIL and bad["failed"] == [kpi]
    assert bad["margin"] < 0


def test_margin_is_min_over_criteria_and_normalised():
    e = criteria.evaluate({**GOOD, "mean_delay_s": 90.0, "merge_speed_kmh": 60.0})
    assert e["margins"]["mean_delay_s"] == pytest.approx(-0.5)
    assert e["margins"]["merge_speed_kmh"] == pytest.approx(-0.2)
    assert e["margin"] == pytest.approx(-0.5)


def test_missing_kpi_is_a_failure_not_a_pass():
    e = criteria.evaluate({**GOOD, "merge_speed_kmh": None})
    assert e["verdict"] == FAIL and "merge_speed_kmh" in e["failed"]


@pytest.mark.parametrize("k", ["teleports", "collisions"])
def test_validity_violation_is_invalid_even_if_kpis_pass(k):
    e = criteria.evaluate({**GOOD, k: 1})
    assert e["verdict"] == INVALID and e["invalid"] == [k]
