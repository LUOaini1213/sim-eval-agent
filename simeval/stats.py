"""Pass-rate statistics near a boundary: Wilson intervals and a 50 %-crossing rule.

Rule used for the refined boundary (stated once here, reported with every estimate):

* at each grid value x the pass rate is k/n over n paired seeds, with a Wilson 95 % interval;
* x is *confidently PASS* if the interval's lower end is above 0.5, *confidently not-PASS*
  if its upper end is below 0.5, otherwise *undecided*;
* the boundary **band** runs from the last confidently-PASS value to the first
  confidently-not-PASS value beyond it: outside the band the pass rate is, at 95 %
  per point, on one side of 50 %;
* the **point estimate** x50 is where the isotonic (pool-adjacent-violators, non-increasing
  from the pass side) fit of the pass rate crosses 0.5, by linear interpolation.
"""
from __future__ import annotations

from math import sqrt

Z95 = 1.959963984540054


def wilson(k: int, n: int, z: float = Z95) -> tuple[float, float]:
    """Wilson score interval for k successes out of n."""
    if n <= 0:
        raise ValueError("n must be positive")
    if not 0 <= k <= n:
        raise ValueError("need 0 <= k <= n")
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, centre - half), min(1.0, centre + half)


def classify(k: int, n: int) -> str:
    lo, hi = wilson(k, n)
    if lo > 0.5:
        return "pass"
    if hi < 0.5:
        return "fail"
    return "undecided"


def isotonic_decreasing(y: list[float], w: list[float]) -> list[float]:
    """Weighted least-squares non-increasing fit (pool adjacent violators)."""
    blocks: list[list[float]] = []  # [value, weight, count]
    for yi, wi in zip(y, w):
        blocks.append([yi, wi, 1])
        while len(blocks) > 1 and blocks[-2][0] < blocks[-1][0]:
            v2, w2, c2 = blocks.pop()
            v1, w1, c1 = blocks.pop()
            blocks.append([(v1 * w1 + v2 * w2) / (w1 + w2), w1 + w2, c1 + c2])
    out: list[float] = []
    for v, _, c in blocks:
        out += [v] * c
    return out


def boundary_from_rates(points: list[tuple[float, int, int]], pass_side: str = "low") -> dict:
    """points: (x, passes, n). pass_side: which end of the axis passes ("low" or "high")."""
    if pass_side not in ("low", "high"):
        raise ValueError(pass_side)
    pts = sorted(points, key=lambda p: p[0], reverse=(pass_side == "high"))
    xs = [p[0] for p in pts]
    rates = [p[1] / p[2] for p in pts]
    cls = [classify(k, n) for _, k, n in pts]
    conf_pass = [i for i, c in enumerate(cls) if c == "pass"]
    last_pass_i = conf_pass[-1] if conf_pass else None
    start = 0 if last_pass_i is None else last_pass_i + 1
    first_fail_i = next((i for i in range(start, len(pts)) if cls[i] == "fail"), None)
    # a confidently-not-PASS value on the pass side of a confidently-PASS one breaks monotonicity
    fail_before_pass = any(cls[i] == "fail" for i in range(0, last_pass_i or 0))
    fit = isotonic_decreasing(rates, [float(p[2]) for p in pts])
    x50 = None
    for i in range(len(pts) - 1):
        if fit[i] >= 0.5 > fit[i + 1]:
            x50 = xs[i] + (fit[i] - 0.5) / (fit[i] - fit[i + 1]) * (xs[i + 1] - xs[i])
            break
    return {
        "pass_side": pass_side,
        "points": [{"x": x, "passes": k, "n": n, "rate": round(k / n, 4),
                    "wilson95": [round(v, 4) for v in wilson(k, n)], "class": c}
                   for (x, k, n), c in zip(pts, cls)],
        "band": [None if last_pass_i is None else xs[last_pass_i],
                 None if first_fail_i is None else xs[first_fail_i]],
        "x50": None if x50 is None else round(x50, 2),
        "band_closed": last_pass_i is not None and first_fail_i is not None,
        "monotone_within_ci": not fail_before_pass,
    }
