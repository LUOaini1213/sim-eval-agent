"""Attribute failures to parameters.

Two complementary views:

* ``stratified``: on the screening sample, compare the non-PASS rate of runs whose
  parameter value is in the lower half of its range vs the upper half.
* ``one_at_a_time``: around the nominal scenario, move one parameter to its low / high
  end and compare against nominal *on the same seed* (paired). Pairing removes the
  seed-to-seed noise that would otherwise swamp small effects.
"""
from __future__ import annotations

from statistics import mean

from .criteria import PASS
from .scenario import PARAMS


def majority_fail(verdicts: list[str]) -> bool:
    """A probe point fails if strictly more than half of its seeds are not PASS."""
    bad = sum(v != PASS for v in verdicts)
    return 2 * bad > len(verdicts)


def stratified(rows: list[dict]) -> list[dict]:
    """rows: run records with 'scenario' and 'eval'. Returns one row per (controller, param)."""
    out = []
    controllers = sorted({r["scenario"]["controller"] for r in rows})
    for c in controllers:
        sub = [r for r in rows if r["scenario"]["controller"] == c]
        for name, p in PARAMS.items():
            mid = (p.lo + p.hi) / 2.0
            lo = [r for r in sub if r["scenario"][name] < mid]
            hi = [r for r in sub if r["scenario"][name] >= mid]

            def rate(rs: list[dict]) -> float | None:
                return None if not rs else round(sum(r["eval"]["verdict"] != PASS for r in rs) / len(rs), 3)

            out.append({
                "controller": c, "param": name, "split_at": mid,
                "n_low": len(lo), "fail_rate_low": rate(lo),
                "n_high": len(hi), "fail_rate_high": rate(hi),
                "run_ids": sorted(r["id"] for r in lo + hi),
            })
    return out


def paired_deltas(nominal: dict[int, dict], moved: dict[int, dict]) -> list[tuple[int, float]]:
    """nominal/moved: seed -> run record. Returns (seed, margin_moved - margin_nominal)."""
    seeds = sorted(set(nominal) & set(moved))
    return [(s, moved[s]["eval"]["margin"] - nominal[s]["eval"]["margin"]) for s in seeds]


def one_at_a_time(nominal: dict[int, dict], moved: dict[str, dict[str, dict[int, dict]]]) -> list[dict]:
    """moved[param][level] = seed -> record, level in {'lo','hi'}. One row per param."""
    rows = []
    nom_fail = majority_fail([r["eval"]["verdict"] for r in nominal.values()])
    for name in sorted(moved):
        row = {"param": name, "nominal_fails": nom_fail, "levels": {}}
        influence = 0.0
        for level in ("lo", "hi"):
            recs = moved[name].get(level)
            if not recs:
                continue
            d = paired_deltas(nominal, recs)
            deltas = [x for _, x in d]
            fails = majority_fail([r["eval"]["verdict"] for r in recs.values()])
            row["levels"][level] = {
                "value": next(iter(recs.values()))["scenario"][name],
                "mean_delta_margin": round(mean(deltas), 4),
                "min_delta_margin": round(min(deltas), 4),
                "max_delta_margin": round(max(deltas), 4),
                "majority_fails": fails,
                "verdicts": [recs[s]["eval"]["verdict"] for s in sorted(recs)],
                "run_ids": [recs[s]["id"] for s in sorted(recs)],
            }
            influence = max(influence, abs(mean(deltas)))
        row["influence"] = round(influence, 4)
        # A flip means the majority verdict at that end differs from nominal: a boundary
        # must lie between nominal and that end (under a monotonicity assumption).
        row["flip_levels"] = [lv for lv, x in row["levels"].items() if x["majority_fails"] != nom_fail]
        rows.append(row)
    rows.sort(key=lambda r: (-r["influence"], r["param"]))
    return rows
