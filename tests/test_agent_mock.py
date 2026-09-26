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


def run(cfg=None):
    ev = FunctionEvaluator(mock_kpis)
    return Agent(ev, cfg or AgentConfig(budget=400, screen_n=8)).run(), ev


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
    assert set(probed) <= {"probe:main_demand", "probe:ramp_demand", "stop"}


def test_budget_stops_the_loop():
    res, ev = run(AgentConfig(budget=90, screen_n=8))
    assert "budget" in res["stop_reason"]
    assert ev.runs_executed <= 90


def test_deterministic():
    a, _ = run()
    b, _ = run()
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
