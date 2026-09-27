"""The simulation-evaluation agent loop.

    plan batch -> run (evaluator) -> evaluate (criteria) -> attribute (paired OAT)
    -> policy picks probe:<param>:<lo|hi> from a closed vocabulary -> bisection batches
    (5 seeds, majority) -> refine each boundary with 20 paired seeds (Wilson intervals)
    -> Morris screening over ranges calibrated from the boundaries -> stop -> report.

Everything here is deterministic given the config: design samples come from seeded RNGs,
SUMO seeds are explicit scenario fields, and the default policy is rule-based.
"""
from __future__ import annotations

import random
import time
from dataclasses import asdict, dataclass, field

from . import criteria
from . import morris as mo
from .attribution import majority_fail, one_at_a_time, stratified
from .boundary import Bisection
from .criteria import PASS
from .policy import DeterministicPolicy
from .scenario import NOMINAL, PARAMS, Scenario
from .stats import boundary_from_rates

DEFAULT_TOL = {
    "main_demand": 50,
    "ramp_demand": 25,
    "truck_share": 0.0125,
    "incident_start": 30,
    "incident_duration": 30,
    "sigma": 0.05,
}


@dataclass
class AgentConfig:
    budget: int = 1500                         # max number of simulation runs
    seeds: tuple[int, ...] = (1, 2, 3, 4, 5)   # paired SUMO seeds for OAT and probing
    controllers: tuple[str, ...] = ("fixed", "alinea")
    reference_controller: str | None = "none"  # evaluated at nominal only, for context
    screen_n: int = 0                          # Latin-hypercube points (x controllers, seed[0]); 0 = off
    agent_seed: int = 20260926                 # RNG seed for the screening / Morris designs
    max_probes: int = 3                        # max parameter directions to bisect
    tol: dict = field(default_factory=lambda: dict(DEFAULT_TOL))
    refine_seeds: tuple[int, ...] = tuple(range(1, 21))  # paired seeds per refinement point; () = off
    refine_points: int = 5                     # initial grid points around each boundary
    refine_step_tol: float = 2.0               # grid step in units of the bisection tolerance
    refine_extend: int = 1                     # max one-point extensions per side if the band is open
    morris_r: int = 6                          # Morris trajectories; 0 = off
    morris_levels: int = 4
    morris_seeds: tuple[int, ...] = (1, 2)


class BudgetExhausted(Exception):
    pass


class Agent:
    def __init__(self, evaluator, config: AgentConfig | None = None, policy=None, nominal: Scenario = NOMINAL):
        self.ev = evaluator
        self.cfg = config or AgentConfig()
        self.policy = policy or DeterministicPolicy()
        self.nominal = nominal
        self.records: dict[str, dict] = {}   # id -> record (first phase that requested it)
        self.order: list[str] = []
        self.actions: list[dict] = []
        self.batches: list[dict] = []
        self._open: list[Bisection] = []   # bisections of the probe in progress

    # ------------------------------------------------------------------ plumbing
    def _run_batch(self, phase: str, scenarios: list[Scenario]) -> list[dict]:
        new = {s.id for s in scenarios} - set(self.records)
        if self.ev.runs_executed + len(new) > self.cfg.budget:
            raise BudgetExhausted(phase)
        t0 = time.perf_counter()
        recs = self.ev.evaluate(scenarios)
        wall = round(time.perf_counter() - t0, 1)
        out = []
        for r in recs:
            if r["id"] not in self.records:
                rec = dict(r)
                rec["eval"] = criteria.evaluate(r["kpis"])
                rec["phase"] = phase
                rec["batch"] = len(self.batches)
                self.records[r["id"]] = rec
                self.order.append(r["id"])
            out.append(self.records[r["id"]])
        self.batches.append({"phase": phase, "size": len(scenarios), "new_runs": len(new), "wall_s": wall})
        return out

    def _at(self, controller: str, seed: int, **kw) -> Scenario:
        return self.nominal.with_(controller=controller, seed=seed, **kw)

    # ------------------------------------------------------------------ phases
    def screening_sample(self) -> list[dict]:
        """Latin-hypercube sample over PARAMS (deterministic for agent_seed)."""
        rng = random.Random(self.cfg.agent_seed)
        n = self.cfg.screen_n
        cols = {}
        for name, p in PARAMS.items():
            perm = list(range(n))
            rng.shuffle(perm)
            vals = [p.lo + (k + 0.5) / n * (p.hi - p.lo) for k in perm]
            cols[name] = [int(round(v)) if p.integer else round(v, 4) for v in vals]
        return [{name: cols[name][i] for name in PARAMS} for i in range(n)]

    def screen(self) -> list[dict]:
        if self.cfg.screen_n <= 0:
            return []
        pts = self.screening_sample()
        scen = [self._at(c, self.cfg.seeds[0], **pt) for pt in pts for c in self.cfg.controllers]
        return self._run_batch("screen", scen)

    def oat(self) -> tuple[dict, dict]:
        seeds = self.cfg.seeds
        nominal: dict[str, dict[int, dict]] = {}
        moved: dict[str, dict[str, dict[str, dict[int, dict]]]] = {}
        scen = []
        ctrls = list(self.cfg.controllers)
        for c in ctrls:
            scen += [self._at(c, s) for s in seeds]
            for name, p in PARAMS.items():
                for v in (p.lo, p.hi):
                    scen += [self._at(c, s, **{name: v}) for s in seeds]
        if self.cfg.reference_controller:
            scen += [self._at(self.cfg.reference_controller, s) for s in seeds]
        self._run_batch("oat", scen)
        for c in ctrls:
            nominal[c] = {s: self.records[self._at(c, s).id] for s in seeds}
            moved[c] = {}
            for name, p in PARAMS.items():
                moved[c][name] = {
                    lv: {s: self.records[self._at(c, s, **{name: v}).id] for s in seeds}
                    for lv, v in (("lo", p.lo), ("hi", p.hi))
                }
        oat_rows = {c: one_at_a_time(nominal[c], moved[c]) for c in ctrls}
        return oat_rows, nominal

    def probe(self, param: str, level: str, oat_rows: dict) -> list[Bisection]:
        """Bisect between nominal and the ``level`` end, for every controller that flips there."""
        p = PARAMS[param]
        nom_val = getattr(self.nominal, param)
        bis: list[Bisection] = []
        for c, rows in oat_rows.items():
            row = next(r for r in rows if r["param"] == param)
            if level not in row["flip_levels"]:
                continue
            end = p.lo if level == "lo" else p.hi
            if row["nominal_fails"]:
                b = Bisection(param, c, pass_value=end, fail_value=nom_val, tol=self.cfg.tol[param], integer=p.integer)
            else:
                b = Bisection(param, c, pass_value=nom_val, fail_value=end, tol=self.cfg.tol[param], integer=p.integer)
            bis.append(b)
        self._open = bis
        active = [b for b in bis if not b.done()]
        while active:
            plan = [(b, b.next_value()) for b in active]
            scen = [self._at(b.controller, s, **{param: v}) for b, v in plan for s in self.cfg.seeds]
            self._run_batch(f"probe:{param}:{level}", scen)
            for b, v in plan:
                recs = [self.records[self._at(b.controller, s, **{param: v}).id] for s in self.cfg.seeds]
                verdicts = [r["eval"]["verdict"] for r in recs]
                b.update(v, majority_fail(verdicts), [r["id"] for r in recs], verdicts)
            active = [b for b in bis if not b.done()]
        return bis

    def monotonicity(self, b: Bisection) -> dict:
        """Check every evaluated point on this axis (other params nominal) for a single switch."""
        pts = {}
        for rid in self.order:
            r = self.records[rid]
            s = r["scenario"]
            if s["controller"] != b.controller or s["seed"] not in self.cfg.seeds:
                continue
            others = {k: v for k, v in self.nominal.with_(controller=b.controller).canonical().items()
                      if k not in (b.param, "seed")}
            if any(s[k] != v for k, v in others.items()):
                continue
            pts.setdefault(s[b.param], []).append(r["eval"]["verdict"])
        seq = [(v, majority_fail(vs)) for v, vs in sorted(pts.items()) if len(vs) == len(self.cfg.seeds)]
        switches = sum(1 for (_, a), (_, c) in zip(seq, seq[1:]) if a != c)
        return {"points": [[v, f] for v, f in seq], "switches": switches, "monotone": switches <= 1}

    def _summarize(self, b: Bisection) -> dict:
        s = b.summary()
        s["monotonicity"] = self.monotonicity(b)
        return s

    # ------------------------------------------------------------------ refinement
    @staticmethod
    def _clip(p, x):
        x = min(max(x, p.lo), p.hi)
        return int(round(x)) if p.integer else round(x, 4)

    def refine_grid(self, b: dict) -> list:
        p = PARAMS[b["param"]]
        centre = (b["last_pass"] + b["first_fail"]) / 2.0
        step = self.cfg.refine_step_tol * self.cfg.tol[b["param"]]
        half = (self.cfg.refine_points - 1) / 2.0
        return sorted({self._clip(p, centre + (k - half) * step) for k in range(self.cfg.refine_points)})

    def _pass_counts(self, controller: str, param: str, xs: list) -> list[tuple]:
        out = []
        for x in xs:
            recs = [self.records[self._at(controller, s, **{param: x}).id] for s in self.cfg.refine_seeds]
            out.append((x, sum(r["eval"]["verdict"] == PASS for r in recs), len(recs)))
        return out

    def refine(self, b: dict) -> dict:
        """Pass rate over refine_seeds on a grid around a bisection boundary; Wilson band."""
        param, c = b["param"], b["controller"]
        p = PARAMS[param]
        side = "low" if b["last_pass"] < b["first_fail"] else "high"
        step = self.cfg.refine_step_tol * self.cfg.tol[param]
        xs = self.refine_grid(b)
        phase = f"refine:{c}:{param}"
        self._run_batch(phase, [self._at(c, s, **{param: x}) for x in xs for s in self.cfg.refine_seeds])
        res = boundary_from_rates(self._pass_counts(c, param, xs), side)
        for _ in range(self.cfg.refine_extend):
            sgn = -1 if side == "low" else 1          # direction from the fail side towards the pass side
            pass_end = min(xs) if side == "low" else max(xs)
            fail_end = max(xs) if side == "low" else min(xs)
            add = []
            if res["band"][0] is None:
                add.append(self._clip(p, pass_end + sgn * step))
            if res["band"][1] is None:
                add.append(self._clip(p, fail_end - sgn * step))
            add = [x for x in add if x not in xs]
            if not add:
                break
            xs = sorted(xs + add)
            self._run_batch(phase, [self._at(c, s, **{param: x}) for x in add for s in self.cfg.refine_seeds])
            res = boundary_from_rates(self._pass_counts(c, param, xs), side)
        ids = {str(x): [self._at(c, s, **{param: x}).id for s in self.cfg.refine_seeds] for x in xs}
        return {"controller": c, "param": param, "seeds": list(self.cfg.refine_seeds),
                "bisection": [b["last_pass"], b["first_fail"]], "grid": xs, "run_ids": ids, **res}

    # ------------------------------------------------------------------ Morris
    def morris(self, boundaries: list[dict]) -> dict:
        names = list(PARAMS)
        ranges = mo.calibrated_ranges(self.nominal.canonical(), boundaries)
        unit = mo.trajectories(names, self.cfg.morris_r, self.cfg.morris_levels, seed=self.cfg.agent_seed)
        traj = [[mo.scale(u, ranges) for u in pts] for pts in unit]
        scen = [self._at(c, s, **pt) for pts in traj for pt in pts
                for c in self.cfg.controllers for s in self.cfg.morris_seeds]
        self._run_batch("morris", scen)
        return {"ranges": ranges, "r": self.cfg.morris_r, "levels": self.cfg.morris_levels,
                "seeds": list(self.cfg.morris_seeds), "trajectories": traj,
                "by_controller": {c: morris_summary(self.records, traj, ranges, c, self.cfg.morris_seeds,
                                                    self.nominal) for c in self.cfg.controllers}}

    # ------------------------------------------------------------------ main loop
    def run(self) -> dict:
        stop_reason = "no unprobed parameter direction with a verdict flip"
        screen_rows, oat_rows, boundaries, refined, morris = [], {}, [], [], {}
        try:
            screen_rows = self.screen()
            oat_rows, _ = self.oat()
            probed: set[str] = set()
            while len(probed) < self.cfg.max_probes:
                ctx = {"runs_used": self.ev.runs_executed, "budget": self.cfg.budget,
                       "probe_cost": 5 * len(self.cfg.seeds) * len(self.cfg.controllers)}
                action, why = self.policy.choose(oat_rows, probed, ctx)
                self.actions.append({"action": action, "why": why, "policy": self.policy.name,
                                     "runs_so_far": self.ev.runs_executed})
                if action == "stop":
                    break
                _, param, level = action.split(":")
                probed.add(action)
                for b in self.probe(param, level, oat_rows):
                    boundaries.append(self._summarize(b))
                self._open = []
            else:
                stop_reason = f"max_probes={self.cfg.max_probes} reached"
            if self.cfg.refine_seeds:
                for b in boundaries:
                    refined.append(self.refine(b))
            if self.cfg.morris_r > 0:
                morris = self.morris(boundaries)
        except BudgetExhausted as e:
            stop_reason = f"budget of {self.cfg.budget} runs would be exceeded in phase {e.args[0]}"
            boundaries += [self._summarize(b) for b in self._open]  # partial, converged may be False
        return {
            "config": {**asdict(self.cfg), "seeds": list(self.cfg.seeds), "controllers": list(self.cfg.controllers),
                       "refine_seeds": list(self.cfg.refine_seeds), "morris_seeds": list(self.cfg.morris_seeds)},
            "nominal": self.nominal.canonical(),
            "policy": self.policy.name,
            "stop_reason": stop_reason,
            "runs_executed": self.ev.runs_executed,
            "batches": self.batches,
            "actions": self.actions,
            "screen": {"stratified": stratified(screen_rows)} if screen_rows else {},
            "oat": oat_rows,
            "boundaries": boundaries,
            "refined": refined,
            "morris": morris,
            "runs": [self.records[i] for i in self.order],
        }


def morris_summary(records: dict[str, dict], traj: list[list[dict]], ranges: dict, controller: str,
                   seeds, nominal: Scenario = NOMINAL) -> dict:
    """Morris statistics of the run margin for one controller, from run records keyed by id."""
    y, verdicts = {}, []
    for j, pts in enumerate(traj):
        for i, pt in enumerate(pts):
            for s in seeds:
                r = records[nominal.with_(controller=controller, seed=s, **pt).id]
                y[(j, i, s)] = r["eval"]["margin"]
                verdicts.append(r["eval"]["verdict"])
    stats = mo.summarize(mo.elementary_effects(traj, ranges, y))
    return {"stats": stats, "ranking": sorted(stats, key=lambda f: (-stats[f]["mu_star"], f)),
            "runs": len(verdicts), "not_pass_runs": sum(v != PASS for v in verdicts),
            "invalid_runs": sum(v == criteria.INVALID for v in verdicts)}
