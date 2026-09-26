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


def _run_one(args: tuple[dict, str, str, bool]) -> dict:
    from .kpi import compute_kpis
    from .runner import run_scenario

    sdict, net, work, keep = args
    s = Scenario.from_dict(sdict)
    run_dir = Path(work) / s.id
    meta = run_scenario(s, Path(net), run_dir)
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
    if not keep:
        shutil.rmtree(run_dir, ignore_errors=True)
    return rec


class SumoEvaluator:
    def __init__(self, net: Path, work_dir: Path, jobs: int = 4, keep_raw: bool = False):
        self.net, self.work_dir, self.jobs, self.keep_raw = Path(net), Path(work_dir), jobs, keep_raw
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
            args = [(s.canonical(), str(self.net), str(self.work_dir), self.keep_raw) for s in todo]
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
