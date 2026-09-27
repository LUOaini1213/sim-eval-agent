"""Morris design and elementary effects on functions with known answers."""
import pytest

from simeval import morris as mo
from simeval.scenario import NOMINAL, PARAMS

NAMES = list(PARAMS)
FULL = {n: {"lo": p.lo, "hi": p.hi, "rule": "test"} for n, p in PARAMS.items()}


def test_each_step_moves_exactly_one_factor_by_delta_and_each_factor_once():
    for pts in mo.trajectories(NAMES, r=10, levels=4, seed=3):
        assert len(pts) == len(NAMES) + 1
        moved = []
        for a, b in zip(pts, pts[1:]):
            diff = [n for n in NAMES if a[n] != b[n]]
            assert len(diff) == 1
            assert abs(b[diff[0]] - a[diff[0]]) == pytest.approx(2 / 3)
            assert 0.0 <= b[diff[0]] <= 1.0
            moved += diff
        assert sorted(moved) == sorted(NAMES)


def test_design_is_seeded():
    assert mo.trajectories(NAMES, 4, seed=1) == mo.trajectories(NAMES, 4, seed=1)
    assert mo.trajectories(NAMES, 4, seed=1) != mo.trajectories(NAMES, 4, seed=2)


def _run(fn, seeds=(1, 2)):
    traj = [[mo.scale(u, FULL) for u in pts] for pts in mo.trajectories(NAMES, r=8, seed=5)]
    y = {(j, i, s): fn(pt, s) for j, pts in enumerate(traj) for i, pt in enumerate(pts) for s in seeds}
    return mo.summarize(mo.elementary_effects(traj, FULL, y))


def test_linear_function_gives_exact_effects_and_zero_sigma():
    # y = 2 * u(main_demand) - 0.5 * u(sigma) + seed offset; u = position in the range
    def fn(pt, s):
        u = {n: (pt[n] - FULL[n]["lo"]) / (FULL[n]["hi"] - FULL[n]["lo"]) for n in NAMES}
        return 2.0 * u["main_demand"] - 0.5 * u["sigma"] + 10.0 * s   # seed shifts the level only

    st = _run(fn)
    assert st["main_demand"]["mu_star"] == pytest.approx(2.0, abs=1e-3)
    assert st["main_demand"]["mu"] == pytest.approx(2.0, abs=1e-3)
    assert st["sigma"]["mu"] == pytest.approx(-0.5, abs=1e-3)
    assert st["main_demand"]["sigma"] == pytest.approx(0.0, abs=1e-3)
    assert st["truck_share"]["mu_star"] == pytest.approx(0.0, abs=1e-9)
    # pairing within a seed removes the +10*s offset entirely
    assert st["main_demand"]["sigma_seed"] == pytest.approx(0.0, abs=1e-3)


def test_interaction_shows_up_as_sigma():
    def fn(pt, s):
        u = {n: (pt[n] - FULL[n]["lo"]) / (FULL[n]["hi"] - FULL[n]["lo"]) for n in NAMES}
        return u["incident_duration"] * u["incident_start"]

    st = _run(fn)
    assert st["incident_duration"]["sigma"] > 0.1 and st["incident_start"]["sigma"] > 0.1
    assert st["main_demand"]["mu_star"] == 0.0


def test_calibrated_ranges_rule():
    b = [{"param": "ramp_demand", "last_pass": 780, "first_fail": 800},
         {"param": "ramp_demand", "last_pass": 1000, "first_fail": 1050},
         {"param": "incident_duration", "last_pass": 240, "first_fail": 260}]
    r = mo.calibrated_ranges(NOMINAL.canonical(), b)
    assert (r["ramp_demand"]["lo"], r["ramp_demand"]["hi"]) == (362, 838)      # 600 +- 1.25*190
    assert (r["incident_duration"]["lo"], r["incident_duration"]["hi"]) == (0, 312)   # clipped at 0
    assert (r["sigma"]["lo"], r["sigma"]["hi"]) == (0.0, 0.9)
    assert r["sigma"]["rule"].startswith("full range")
