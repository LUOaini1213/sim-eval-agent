"""Evaluators map scenarios to run records. The agent only sees this interface.

``SumoEvaluator`` runs SUMO headless in parallel worker processes and caches by
scenario id; ``FunctionEvaluator`` wraps a pure function (used by tests / mocks).
"""
from __future__ import annotations

import hashlib
import shutil
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Callable, Iterable

from .scenario import Scenario


def _body_sha256(path: Path) -> str:
    text = Path(path).read_text(encoding="utf-8")
    body = text.split("-->", 1)[1] if "-->" in text else text  # drop config/timestamp header
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


def _run_one(args: tuple) -> dict:
    """args = (scenario dict, net path, work dir, keep raw[, SimOptions dict])."""
    from .kpi import compute_kpis
    from .runner import DEFAULT_OPTIONS, SimOptions, run_scenario

    sdict, net, work, keep = args[:4]
    opts = SimOptions(**args[4]) if len(args) > 4 and args[4] else DEFAULT_OPTIONS
    s = Scenario.from_dict(sdict)
    run_dir = Path(work) / s.id
    meta = run_scenario(s, Path(net), run_dir, opts=opts)
    kpis = compute_kpis(run_dir)
    rates = [r for _, r in meta["rates"]]
    rec = {
        "id": s.id,
        "scenario": s.canonical(),
        "kpis": kpis,
        "meter_rate_mean_veh_h": round(sum(rates) / len(rates), 1),
        "tripinfo_sha256": _body_sha256(run_dir / "tripinfo.xml"),
        "wall_s": meta["wall_s"],
    }
    if opts.log_warnings:
        from .diagnosis import summarize

        rec["log"] = summarize((run_dir / "sumo_log.txt").read_text(encoding="utf-8", errors="replace"))
    if not keep:
        shutil.rmtree(run_dir, ignore_errors=True)
    return rec


class SumoEvaluator:
    def __init__(self, net: Path, work_dir: Path, jobs: int = 4, keep_raw: bool = False,
                 options: dict | None = None):
        self.net, self.work_dir, self.jobs, self.keep_raw = Path(net), Path(work_dir), jobs, keep_raw
        self.options = options or {}
        self.cache: dict[str, dict] = {}
        self.runs_executed = 0
        self._pool: ProcessPoolExecutor | None = None

    def close(self) -> None:
        if self._pool is not None:
            self._pool.shutdown()
            self._pool = None

    def evaluate(self, scenarios: Iterable[Scenario]) -> list[dict]:
        scenarios = list(scenarios)
        todo = []
        seen = set()
        for s in scenarios:
            if s.id not in self.cache and s.id not in seen:
                todo.append(s)
                seen.add(s.id)
        if todo:
            args = [(s.canonical(), str(self.net), str(self.work_dir), self.keep_raw, self.options) for s in todo]
            if self.jobs <= 1:
                recs = [_run_one(a) for a in args]
            else:
                if self._pool is None:
                    self._pool = ProcessPoolExecutor(max_workers=self.jobs)
                recs = list(self._pool.map(_run_one, args))
            for r in recs:
                self.cache[r["id"]] = r
            self.runs_executed += len(recs)
        return [self.cache[s.id] for s in scenarios]


class FunctionEvaluator:
    """Deterministic stand-in: ``fn(scenario) -> kpis``."""

    def __init__(self, fn: Callable[[Scenario], dict]):
        self.fn = fn
        self.cache: dict[str, dict] = {}
        self.runs_executed = 0

    def evaluate(self, scenarios: Iterable[Scenario]) -> list[dict]:
        out = []
        for s in scenarios:
            if s.id not in self.cache:
                self.cache[s.id] = {"id": s.id, "scenario": s.canonical(), "kpis": self.fn(s), "wall_s": 0.0}
                self.runs_executed += 1
            out.append(self.cache[s.id])
        return out


class ReplayEvaluator:
    """Serves runs already on record (e.g. results/runs.jsonl) and simulates only the rest.

    ``runs_executed`` counts every distinct scenario this campaign asked for, cached or not,
    so budgets mean the same thing as in a fresh campaign; ``simulated`` counts real SUMO runs.
    """

    def __init__(self, records: Iterable[dict], fallback):
        keep = ("id", "scenario", "kpis", "meter_rate_mean_veh_h", "tripinfo_sha256", "wall_s", "log")
        self.cache: dict[str, dict] = {r["id"]: {k: r[k] for k in keep if k in r} for r in records}
        self.fallback = fallback
        self.runs_executed = 0
        self.simulated = 0
        self.new_records: list[dict] = []
        self._seen: set[str] = set()

    def evaluate(self, scenarios: Iterable[Scenario]) -> list[dict]:
        scenarios = list(scenarios)
        missing, seen = [], set()
        for s in scenarios:
            if s.id not in self.cache and s.id not in seen:
                missing.append(s)
                seen.add(s.id)
        if missing:
            recs = self.fallback.evaluate(missing)
            for r in recs:
                self.cache[r["id"]] = r
                self.new_records.append(r)
            self.simulated += len(recs)
        for s in scenarios:
            if s.id not in self._seen:
                self._seen.add(s.id)
                self.runs_executed += 1
        return [self.cache[s.id] for s in scenarios]
