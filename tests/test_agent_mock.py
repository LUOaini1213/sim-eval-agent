"""The agent loop on a mocked evaluator with planted thresholds (no SUMO needed)."""
import pytest

from simeval.agent import Agent, AgentConfig
from simeval.attribution import majority_fail, one_at_a_time, paired_deltas
from simeval.criteria import FAIL, INVALID, PASS, evaluate
from simeval.evaluator import FunctionEvaluator

ALINEA_MAIN_THRESHOLD = 3517   # planted: alinea fails iff main_demand > 3517
FIXED_RAMP_THRESHOLD = 777     # planted: fixed fails iff ramp_demand > 777


def seed_noise(seed: int) -> float:
    return ((seed * 7919) % 11 - 5) * 0.8  # in [-4, 4], differs per seed


def mock_kpis(s):
    k = {"mean_delay_s": 20.0, "ramp_p95_delay_s": 40.0, "ttc_per_1000veh": 0.0,
         "teleports": 0, "collisions": 0,
         # never fails; carries seed noise and a weak sigma effect
         "merge_speed_kmh": 95.0 + seed_noise(s.seed) - 5.0 * s.sigma}
    if s.controller == "alinea":
        k["mean_delay_s"] = 20.0 + 40.0 * (s.main_demand - 2400) / (ALINEA_MAIN_THRESHOLD - 2400)
    if s.controller == "fixed":
        k["ramp_p95_delay_s"] = 120.0 * s.ramp_demand / FIXED_RAMP_THRESHOLD
    return k


def run(cfg=None, fn=None):
    ev = FunctionEvaluator(fn or mock_kpis)
    return Agent(ev, cfg or AgentConfig(budget=1000, screen_n=8)).run(), ev


def boundary(res, controller, param):
    return next(b for b in res["boundaries"] if b["controller"] == controller and b["param"] == param)


def test_finds_planted_thresholds_within_tolerance():
    res, _ = run()
    b = boundary(res, "alinea", "main_demand")
    assert b["last_pass"] <= ALINEA_MAIN_THRESHOLD < b["first_fail"]
    assert b["first_fail"] - b["last_pass"] <= 50 and b["converged"]
    b = boundary(res, "fixed", "ramp_demand")
    assert b["last_pass"] <= FIXED_RAMP_THRESHOLD < b["first_fail"]
    assert b["first_fail"] - b["last_pass"] <= 25 and b["converged"]
    assert all(x["monotonicity"]["monotone"] for x in res["boundaries"])


def test_attribution_ranks_the_planted_parameter_first():
    res, _ = run()
    assert res["oat"]["alinea"][0]["param"] == "main_demand"
    assert res["oat"]["fixed"][0]["param"] == "ramp_demand"
    # probe order follows influence; no flip-less parameter is probed
    probed = [a["action"] for a in res["actions"]]
    assert set(probed) <= {"probe:main_demand:hi", "probe:ramp_demand:hi", "stop"}


def test_budget_stops_the_loop():
    res, ev = run(AgentConfig(budget=150, screen_n=8))
    assert "budget" in res["stop_reason"]
    assert ev.runs_executed <= 150


def test_deterministic():
    a, _ = run()
    b, _ = run()
    for r in (a, b):  # batch wall times are measurements, not decisions
        for bt in r["batches"]:
            bt.pop("wall_s")
    assert a == b


def test_paired_deltas_cancel_seed_noise():
    """Seed noise (+-4 km/h) swamps a 0.05 sigma step unless runs are paired by seed."""
    def rec(sigma, seed):
        from simeval.scenario import NOMINAL
        s = NOMINAL.with_(controller="none", sigma=sigma, seed=seed)
        return {"id": s.id, "scenario": s.canonical(), "eval": evaluate(mock_kpis(s))}

    seeds = [1, 2, 3, 4, 5]
    nom = {s: rec(0.5, s) for s in seeds}
    hi = {s: rec(0.55, s) for s in seeds}
    d = [x for _, x in paired_deltas(nom, hi)]
    # exact paired effect: margin(speed) moves by -5*0.05/75 for every seed
    assert all(x == pytest.approx(-0.25 / 75, abs=1e-4) for x in d)
    rows = one_at_a_time(nom, {"sigma": {"hi": hi}})
    assert rows[0]["levels"]["hi"]["min_delta_margin"] == pytest.approx(rows[0]["levels"]["hi"]["max_delta_margin"], abs=2e-4)  # margins are stored to 4 dp


def test_majority_rule():
    assert majority_fail([FAIL, FAIL, PASS])
    assert not majority_fail([FAIL, PASS, PASS])
    assert majority_fail([INVALID, FAIL, PASS])
    assert not majority_fail([FAIL, PASS])  # a tie is not a majority


def noisy_kpis(s):
    """fixed fails iff ramp_demand + per-seed offset > 777; offsets spread seeds over ~+-60 veh/h."""
    k = mock_kpis(s)
    if s.controller == "fixed":
        offset = ((s.seed * 37) % 13 - 6) * 10.0
        k["ramp_p95_delay_s"] = 120.0 * (s.ramp_demand + offset) / FIXED_RAMP_THRESHOLD
    return k


def test_refinement_band_contains_the_planted_threshold_and_uses_20_paired_seeds():
    res, _ = run(fn=noisy_kpis)
    rf = next(r for r in res["refined"] if r["controller"] == "fixed" and r["param"] == "ramp_demand")
    assert rf["seeds"] == list(range(1, 21))
    assert all(p["n"] == 20 for p in rf["points"])
    lo, hi = rf["band"]
    assert rf["band_closed"] and lo < FIXED_RAMP_THRESHOLD < hi
    assert abs(rf["x50"] - FIXED_RAMP_THRESHOLD) <= 30
    # noisy seeds: some grid value is undecided, so the band is wider than one grid step
    assert any(p["class"] == "undecided" for p in rf["points"])


def test_morris_ranks_the_planted_parameter_first_on_calibrated_ranges():
    res, _ = run()
    m = res["morris"]
    assert m["by_controller"]["fixed"]["ranking"][0] == "ramp_demand"
    assert m["by_controller"]["alinea"]["ranking"][0] == "main_demand"
    # ranges reach just past the nearest boundary instead of the full range
    assert m["ranges"]["ramp_demand"]["hi"] < 1200 and m["ranges"]["main_demand"]["hi"] < 4200
    assert m["ranges"]["sigma"] == {"lo": 0.0, "hi": 0.9, "rule": "full range (no verdict flip in one-at-a-time)"}


def test_report_verifies_and_catches_tampered_refinement(tmp_path):
    import json

    from simeval.report import verify, write_all

    res, _ = run(fn=noisy_kpis)
    write_all(res, {"sumo_version": "-", "net_sha256": "0" * 64, "wall_time_s": 0, "jobs": 1, "date": "-"}, tmp_path)
    assert verify(tmp_path) == []
    rep = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    c = next(c for c in rep["claims"] if c["text"].startswith("Refined boundary"))
    c["values"]["points"][0]["passes"] -= 1
    (tmp_path / "report.json").write_text(json.dumps(rep), encoding="utf-8")
    assert any("claims" in p for p in verify(tmp_path))
    rep["claims"] = json.loads(json.dumps(rep["claims"]))
    rep["morris"]["ranges"]["sigma"]["hi"] = 0.8
    (tmp_path / "report.json").write_text(json.dumps(rep), encoding="utf-8")
    assert any("Morris ranges" in p for p in verify(tmp_path))


def test_replay_evaluator_counts_budget_as_if_fresh_and_simulates_only_misses():
    from simeval.evaluator import ReplayEvaluator
    from simeval.scenario import NOMINAL

    base = FunctionEvaluator(mock_kpis)
    known = base.evaluate([NOMINAL.with_(seed=s) for s in (1, 2)])
    fallback = FunctionEvaluator(mock_kpis)
    ev = ReplayEvaluator(known, fallback)
    out = ev.evaluate([NOMINAL.with_(seed=s) for s in (1, 2, 3, 3)])
    assert [r["scenario"]["seed"] for r in out] == [1, 2, 3, 3]
    assert (ev.runs_executed, ev.simulated, fallback.runs_executed) == (3, 1, 1)
    ev.evaluate([NOMINAL.with_(seed=3)])
    assert (ev.runs_executed, ev.simulated) == (3, 1)


def test_same_cache_same_campaign():
    """A campaign replayed from records equals the campaign that produced them."""
    from simeval.evaluator import ReplayEvaluator

    res, _ = run(AgentConfig(budget=1000, refine_seeds=(), morris_r=0))
    ev = ReplayEvaluator(res["runs"], FunctionEvaluator(lambda s: (_ for _ in ()).throw(AssertionError(s))))
    again = Agent(ev, AgentConfig(budget=1000, refine_seeds=(), morris_r=0)).run()
    assert again["boundaries"] == res["boundaries"] and ev.simulated == 0


def test_refinement_extends_the_grid_towards_the_pass_side_when_the_band_is_open():
    """Hand the refiner a boundary that is off by ~140 veh/h: the whole first grid fails, so it
    must add a value on the pass side (lower ramp demand) to close the band."""
    ev = FunctionEvaluator(mock_kpis)
    ag = Agent(ev, AgentConfig(refine_seeds=(1, 2, 3, 4, 5, 6)))
    rf = ag.refine({"param": "ramp_demand", "controller": "fixed", "last_pass": 900, "first_fail": 925})
    assert rf["grid"][0] < 812 and rf["band_closed"]
    assert rf["band"][0] < FIXED_RAMP_THRESHOLD < rf["band"][1]
