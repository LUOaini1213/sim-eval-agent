"""Wilson intervals and the 50 %-crossing boundary rule."""
import pytest

from simeval.stats import boundary_from_rates, classify, isotonic_decreasing, wilson


def test_wilson_reference_values():
    # reference values of the Wilson score interval (z = 1.96)
    assert wilson(10, 20) == pytest.approx((0.2993, 0.7007), abs=1e-4)
    assert wilson(0, 20) == pytest.approx((0.0, 0.1611), abs=1e-4)
    assert wilson(20, 20) == pytest.approx((0.8389, 1.0), abs=1e-4)
    assert wilson(15, 20) == pytest.approx((0.5313, 0.8881), abs=1e-4)
    with pytest.raises(ValueError):
        wilson(3, 2)


def test_classification_thresholds_at_20_seeds():
    # with 20 seeds, 15 passes is the least that is confidently PASS, 5 the most confidently not-PASS
    assert [classify(k, 20) for k in (16, 15, 14, 6, 5, 4)] == \
        ["pass", "pass", "undecided", "undecided", "fail", "fail"]


def test_isotonic_pools_violators():
    assert isotonic_decreasing([1.0, 0.6, 0.8, 0.2], [1, 1, 1, 1]) == pytest.approx([1.0, 0.7, 0.7, 0.2])
    assert isotonic_decreasing([0.9, 0.5], [1, 1]) == [0.9, 0.5]


def test_band_and_crossing_pass_on_low_side():
    pts = [(100, 20, 20), (200, 17, 20), (300, 11, 20), (400, 7, 20), (500, 2, 20)]
    r = boundary_from_rates(pts)
    assert r["band"] == [200, 500]          # 300 and 400 are undecided
    assert r["band_closed"] and r["monotone_within_ci"]
    # fit equals the raw rates (already decreasing): 0.55 at 300, 0.35 at 400 -> 325
    assert r["x50"] == pytest.approx(325.0)


def test_pass_on_high_side_and_open_band():
    pts = [(0, 3, 20), (10, 9, 20), (20, 12, 20)]
    r = boundary_from_rates(pts, pass_side="high")
    assert [p["x"] for p in r["points"]] == [20, 10, 0]
    assert r["band"] == [None, 0]           # nothing confidently PASS on the grid
    assert not r["band_closed"]
    assert r["x50"] == pytest.approx(20 - 10 * 0.1 / 0.15, abs=0.01)  # 0.6 at 20, 0.45 at 10


def test_confident_fail_before_confident_pass_is_flagged():
    pts = [(1, 20, 20), (2, 2, 20), (3, 19, 20), (4, 0, 20)]
    r = boundary_from_rates(pts)
    assert not r["monotone_within_ci"]
    assert r["band"] == [3, 4]
