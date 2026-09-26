"""Explicit pass/fail criteria.

Thresholds are project-defined acceptance limits for this synthetic merge, not taken
from any standard. Each criterion yields a normalised *margin*: > 0 means slack,
< 0 means violated. The run margin is the minimum over criteria, so it is a single
continuous score the agent can compare across paired seeds.

Validity checks (teleports, collisions) are kept separate: a run that violates them
is INVALID -- the simulation itself is not trustworthy -- rather than a SUT failure.
"""
from __future__ import annotations

from dataclasses import dataclass

PASS, FAIL, INVALID = "PASS", "FAIL", "INVALID"


@dataclass(frozen=True)
class Criterion:
    kpi: str
    op: str        # "<=" (upper limit) or ">=" (lower limit)
    limit: float
    why: str

    def margin(self, value: float | None) -> float:
        if value is None:
            return -1.0
        if self.op == "<=":
            return (self.limit - value) / self.limit
        if self.op == ">=":
            return (value - self.limit) / self.limit
        raise ValueError(self.op)

    def ok(self, value: float | None) -> bool:
        if value is None:
            return False
        return value <= self.limit if self.op == "<=" else value >= self.limit


CRITERIA: tuple[Criterion, ...] = (
    Criterion("mean_delay_s", "<=", 60.0, "network-wide mean delay per vehicle (timeLoss + departDelay)"),
    Criterion("ramp_p95_delay_s", "<=", 120.0, "95th-percentile delay of ramp vehicles (queue / spillback)"),
    Criterion("merge_speed_kmh", ">=", 75.0, "flow-weighted mainline spot speed in the merge area"),
    Criterion("ttc_per_1000veh", "<=", 10.0, "SSM conflicts with min TTC < 1.5 s per 1000 vehicles"),
)

VALIDITY = (("teleports", 0), ("collisions", 0))


def evaluate(kpis: dict) -> dict:
    invalid = [k for k, mx in VALIDITY if kpis.get(k, 0) > mx]
    per = {c.kpi: round(c.margin(kpis.get(c.kpi)), 4) for c in CRITERIA}
    failed = [c.kpi for c in CRITERIA if not c.ok(kpis.get(c.kpi))]
    if invalid:
        verdict = INVALID
    elif failed:
        verdict = FAIL
    else:
        verdict = PASS
    return {
        "verdict": verdict,
        "margin": min(per.values()),
        "margins": per,
        "failed": failed,
        "invalid": invalid,
    }
