"""Morris elementary-effects screening (Morris 1991; mu* after Campolongo et al. 2007).

Design: ``r`` one-at-a-time trajectories on a ``levels``-level grid in the unit cube, step
Delta = levels / (2 (levels - 1)). Each trajectory moves every factor exactly once, in a
random order and direction. Every design point is run on the same SUMO seeds, and an
elementary effect is computed *within* a seed (paired), so seed-to-seed noise does not enter
an effect directly; its size is reported separately as ``sigma_seed``.

Ranges are "calibrated" by :func:`calibrated_ranges` (rule in its docstring) rather than the
full admissible ranges, where almost every run failed and effects saturated.
"""
from __future__ import annotations

import random
from statistics import mean, pstdev, stdev

from .scenario import PARAMS

RANGE_FACTOR = 1.25


def calibrated_ranges(nominal: dict, boundaries: list[dict], factor: float = RANGE_FACTOR) -> dict:
    """Per parameter: [lo, hi] plus the rule that produced it.

    * If the 5-seed bisection found a boundary along the parameter (any controller), let d be
      the distance from nominal to the nearest boundary midpoint; the range is
      nominal +- factor * d, clipped to the admissible range. It reaches just past the nearest
      failure boundary, so both outcomes occur without the far, saturated region.
    * Otherwise the full admissible range: the one-at-a-time screen showed no majority-verdict
      flip at either end, so the full range does not saturate.
    """
    out = {}
    for name, p in PARAMS.items():
        nom = nominal[name]
        mids = [(b["last_pass"] + b["first_fail"]) / 2.0 for b in boundaries if b["param"] == name]
        if mids:
            d = min(abs(m - nom) for m in mids)
            lo, hi = max(p.lo, nom - factor * d), min(p.hi, nom + factor * d)
            rule = f"nominal +- {factor} x distance to nearest boundary ({round(d, 4)})"
        else:
            lo, hi, rule = p.lo, p.hi, "full range (no verdict flip in one-at-a-time)"
        if p.integer:
            lo, hi = int(round(lo)), int(round(hi))
        else:
            lo, hi = round(lo, 4), round(hi, 4)
        out[name] = {"lo": lo, "hi": hi, "rule": rule}
    return out


def trajectories(names: list[str], r: int, levels: int = 4, seed: int = 0) -> list[list[dict]]:
    """r trajectories of len(names)+1 unit-cube points; each step moves one factor by +-Delta."""
    rng = random.Random(seed)
    delta = levels / (2.0 * (levels - 1))
    grid = [i / (levels - 1) for i in range(levels)]
    out = []
    for _ in range(r):
        x = {n: rng.choice(grid) for n in names}
        order = list(names)
        rng.shuffle(order)
        pts = [dict(x)]
        for n in order:
            x = dict(x)
            x[n] = round(x[n] + delta, 10) if x[n] + delta <= 1.0 + 1e-9 else round(x[n] - delta, 10)
            pts.append(x)
        out.append(pts)
    return out


def scale(unit: dict, ranges: dict) -> dict:
    vals = {}
    for n, u in unit.items():
        lo, hi = ranges[n]["lo"], ranges[n]["hi"]
        v = lo + u * (hi - lo)
        vals[n] = int(round(v)) if PARAMS[n].integer else round(v, 4)
    return vals


def changed_factor(a: dict, b: dict) -> str:
    diff = [n for n in a if a[n] != b[n]]
    if len(diff) != 1:
        raise ValueError(f"trajectory step changes {diff}")
    return diff[0]


def elementary_effects(traj_values: list[list[dict]], ranges: dict, y: dict) -> dict[str, list[dict]]:
    """traj_values: scaled trajectories; y[(j, i, seed)] = output at trajectory j, point i.

    Returns factor -> list of {"traj", "seed", "ee"}; effects are per unit of the (calibrated)
    range, using the realised (rounded) step, and paired within a seed.
    """
    seeds = sorted({k[2] for k in y})
    out: dict[str, list[dict]] = {n: [] for n in ranges}
    for j, pts in enumerate(traj_values):
        for i in range(len(pts) - 1):
            f = changed_factor(pts[i], pts[i + 1])
            step = (pts[i + 1][f] - pts[i][f]) / (ranges[f]["hi"] - ranges[f]["lo"])
            for s in seeds:
                ee = (y[(j, i + 1, s)] - y[(j, i, s)]) / step
                out[f].append({"traj": j, "seed": s, "ee": ee})
    return out


def summarize(ees: dict[str, list[dict]]) -> dict[str, dict]:
    """mu* (mean |EE|), mu, sigma (over trajectories x seeds) and sigma_seed per factor."""
    out = {}
    for f, rows in ees.items():
        e = [r["ee"] for r in rows]
        by_traj: dict[int, list[float]] = {}
        for r in rows:
            by_traj.setdefault(r["traj"], []).append(r["ee"])
        seed_sd = [pstdev(v) for v in by_traj.values() if len(v) > 1]
        out[f] = {
            "n": len(e),
            "mu_star": round(mean(abs(x) for x in e), 4),
            "mu": round(mean(e), 4),
            "sigma": round(stdev(e), 4) if len(e) > 1 else 0.0,
            "sigma_seed": round(mean(seed_sd), 4) if seed_sd else 0.0,
        }
    return out
