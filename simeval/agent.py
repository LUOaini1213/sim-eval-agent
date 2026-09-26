"""The simulation-evaluation agent loop.

    plan batch -> run (evaluator) -> evaluate (criteria) -> attribute (stratified + paired OAT)
    -> policy picks a parameter from a closed vocabulary -> bisection batches probe the
    pass/fail boundary -> stop on budget / nothing left to probe -> report.

Everything here is deterministic given the config: the screening sample comes from a
seeded RNG, SUMO seeds are explicit scenario fields, and the default policy is rule-based.
"""
from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field

from . import criteria
from .attribution import majority_fail, one_at_a_time, stratified
from .boundary import Bisection
from .policy import DeterministicPolicy
from .scenario import NOMINAL, PARAMS, Scenario

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
    budget: int = 400                          # max number of simulation runs
    seeds: tuple[int, ...] = (1, 2, 3, 4, 5)   # paired SUMO seeds for OAT and probing
    controllers: tuple[str, ...] = ("fixed", "alinea")
    reference_controller: str | None = "none"  # evaluated at nominal only, for context
    screen_n: int = 24                         # Latin-hypercube points (x controllers, seed[0])
    agent_seed: int = 20260926                 # RNG seed for the screening sample
    max_probes: int = 3                        # max parameters to bisect
    tol: dict = field(default_factory=lambda: dict(DEFAULT_TOL))


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
        recs = self.ev.evaluate(scenarios)
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
        self.batches.append({"phase": phase, "size": len(scenarios), "new_runs": len(new)})
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

    def probe(self, param: str, oat_rows: dict) -> list[Bisection]:
        p = PARAMS[param]
        nom_val = getattr(self.nominal, param)
        bis: list[Bisection] = []
        for c, rows in oat_rows.items():
            row = next(r for r in rows if r["param"] == param)
            for lv in row["flip_levels"]:
                end = p.lo if lv == "lo" else p.hi
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
            self._run_batch(f"probe:{param}", scen)
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
            if s["controller"] != b.controller:
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

    # ------------------------------------------------------------------ main loop
    def run(self) -> dict:
        stop_reason = "no unprobed parameter with a verdict flip"
        screen_rows, oat_rows, boundaries = [], {}, []
        try:
            screen_rows = self.screen()
            oat_rows, _ = self.oat()
            probed: set[str] = set()
            while len(probed) < self.cfg.max_probes:
                action, why = self.policy.choose(oat_rows, probed)
                self.actions.append({"action": action, "why": why, "policy": self.policy.name,
                                     "runs_so_far": self.ev.runs_executed})
                if action == "stop":
                    break
                param = action.split(":", 1)[1]
                probed.add(param)
                for b in self.probe(param, oat_rows):
                    boundaries.append(self._summarize(b))
                self._open = []
            else:
                stop_reason = f"max_probes={self.cfg.max_probes} reached"
        except BudgetExhausted as e:
            stop_reason = f"budget of {self.cfg.budget} runs would be exceeded in phase {e.args[0]}"
            boundaries += [self._summarize(b) for b in self._open]  # partial, converged may be False
        return {
            "config": {**asdict(self.cfg), "seeds": list(self.cfg.seeds), "controllers": list(self.cfg.controllers)},
            "nominal": self.nominal.canonical(),
            "policy": self.policy.name,
            "stop_reason": stop_reason,
            "runs_executed": self.ev.runs_executed,
            "batches": self.batches,
            "actions": self.actions,
            "screen": {"stratified": stratified(screen_rows)} if screen_rows else {},
            "oat": oat_rows,
            "boundaries": boundaries,
            "runs": [self.records[i] for i in self.order],
        }
