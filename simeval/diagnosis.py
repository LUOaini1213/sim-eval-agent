"""Read SUMO's warning log and attribute each collision to what the victim was doing.

SUMO writes one warning per emergency stop (with its reason) and per collision. A rear-end
collision in SUMO's collision-free car-following model needs a leader that stopped harder
than its follower can brake; SUMO calls that an *emergency stop* and states why. So the
cause of a collision is read off the victim's last emergency stop shortly before it.
"""
from __future__ import annotations

import re
from collections import Counter

_COLLISION = re.compile(
    r"Vehicle '([^']+)'; collision with vehicle '([^']+)', lane='([^']*)', gap=([-\d.]+), time=(\d+(?:\.\d+)?)")
_ESTOP = re.compile(
    r"Vehicle '([^']+)' performs emergency stop at the end of lane '([^']*)' because (.+?) "
    r"\(decel=([-\d.]+), offset=[-\d.]+\), time=(\d+(?:\.\d+)?)")

REASONS = {
    "there is no connection to the next edge": "no_connection",
    "of a red traffic light": "red_light",
}
WINDOW_S = 5.0  # a victim's emergency stop at most this long before the collision counts


def reason_class(text: str) -> str:
    return REASONS.get(text.strip(), "other")


def parse_log(text: str) -> dict:
    collisions = [{"collider": m[0], "victim": m[1], "lane": m[2], "gap": float(m[3]), "time": float(m[4])}
                  for m in _COLLISION.findall(text)]
    stops = [{"vehicle": m[0], "lane": m[1], "reason": reason_class(m[2]), "decel": float(m[3]), "time": float(m[4])}
             for m in _ESTOP.findall(text)]
    return {"collisions": collisions, "emergency_stops": stops}


def attribute(parsed: dict) -> list[dict]:
    """One row per collision: the victim's last emergency stop within WINDOW_S before it."""
    out = []
    for c in parsed["collisions"]:
        prior = [s for s in parsed["emergency_stops"]
                 if s["vehicle"] == c["victim"] and c["time"] - WINDOW_S <= s["time"] <= c["time"]]
        cause = prior[-1] if prior else None
        out.append({**c, "cause": cause["reason"] if cause else "none",
                    "victim_stop_time": cause["time"] if cause else None,
                    "victim_stop_decel": cause["decel"] if cause else None})
    return out


def summarize(text: str) -> dict:
    """Compact, JSON-able summary of a SUMO log for a run record."""
    p = parse_log(text)
    return {
        "collisions": attribute(p),
        "emergency_stops_by_reason": dict(sorted(Counter(s["reason"] for s in p["emergency_stops"]).items())),
        "emergency_stop_times": {r: sorted({s["time"] for s in p["emergency_stops"] if s["reason"] == r})
                                 for r in sorted({s["reason"] for s in p["emergency_stops"]})},
    }


# ---------------------------------------------------------------------------- experiment summary
CONFIGS = {
    # name: (incident_method, amber_s)
    "legacy": ("traci_disallow", 0.0),         # what produced results/v1
    "vss_disallow": ("vss_disallow", 0.0),     # SUMO docs' mitigation: slow traffic before closing
    "blocker_insert": ("blocker_insert", 0.0),
    "blocker": ("blocker", 0.0),
    "stall": ("stall", 0.0),
    "default": ("stall", 2.5),                 # what produced results/ (v2)
}


def _median(xs: list[float]) -> float | None:
    if not xs:
        return None
    xs = sorted(xs)
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def config_summary(recs: list[dict]) -> dict:
    """Totals over one configuration's runs (records carry 'kpis' and 'log')."""
    onset = [r["kpis"]["incident_onset_s"] - r["scenario"]["incident_start"] for r in recs
             if r["kpis"].get("incident_onset_s") is not None]
    by_reason = Counter()
    for r in recs:
        by_reason.update(r["log"]["emergency_stops_by_reason"])
    return {
        "runs": len(recs),
        "runs_with_collision": sum(r["kpis"]["collisions"] > 0 for r in recs),
        "collisions": sum(r["kpis"]["collisions"] for r in recs),
        "teleports": sum(r["kpis"]["teleports"] for r in recs),
        "emergency_stops": dict(sorted(by_reason.items())),
        "incident_onset_delay_s": None if not onset else {
            "n": len(onset), "median": _median(onset), "max": max(onset), "min": min(onset)},
        "mean_delay_s_avg": round(sum(r["kpis"]["mean_delay_s"] for r in recs) / len(recs), 2) if recs else None,
    }


def same_run(new: dict, old: dict) -> bool:
    """Same tripinfo hash and every KPI the old record has is equal (new KPIs may be extra)."""
    return (new["tripinfo_sha256"] == old["tripinfo_sha256"]
            and all(k in new["kpis"] and new["kpis"][k] == v for k, v in old["kpis"].items()))


def invalid_rows(v1: dict[str, dict], legacy: dict[str, dict], default: dict[str, dict], ids: list[str]) -> list[dict]:
    """Per v1-INVALID run: is the legacy re-run identical, what caused each collision, and the
    verdict with the fixed simulation."""
    from .criteria import evaluate

    rows = []
    for i in ids:
        old, leg, new = v1[i], legacy[i], default[i]
        s = old["scenario"]
        causes = []
        for c in leg["log"]["collisions"]:
            at_closure = (s["incident_duration"] > 0 and c["victim_stop_time"] is not None
                          and c["victim_stop_time"] == float(s["incident_start"]))
            causes.append({"lane": c["lane"], "time": c["time"], "cause": c["cause"],
                           "victim_stop_time": c["victim_stop_time"], "victim_stop_decel": c["victim_stop_decel"],
                           "stop_at_closure_instant": at_closure})
        rows.append({
            "id": i, "controller": s["controller"], "incident": [s["incident_start"], s["incident_duration"]],
            "v1_collision_lanes": old["kpis"]["collision_lanes"],
            "legacy_identical": same_run(leg, old),
            "causes": causes,
            "fixed_verdict": evaluate(new["kpis"])["verdict"],
            "fixed_collisions": new["kpis"]["collisions"],
        })
    return rows


def build_summary(records: list[dict], v1_runs: list[dict], compare_ids: list[str], invalid_ids: list[str]) -> dict:
    by_cfg: dict[str, dict[str, dict]] = {}
    for r in records:
        by_cfg.setdefault(r["config"], {})[r["id"]] = r
    v1 = {r["id"]: r for r in v1_runs}
    cmp_ = {name: config_summary([by_cfg[name][i] for i in compare_ids]) for name in CONFIGS if name in by_cfg}
    inv = invalid_rows(v1, by_cfg["legacy"], by_cfg["default"], invalid_ids)
    cause_counts = Counter(c["cause"] + (":at_closure" if c["stop_at_closure_instant"] else "")
                           for row in inv for c in row["causes"])
    return {
        "compare_ids": compare_ids,
        "invalid_ids": invalid_ids,
        "comparison": cmp_,
        "invalid_runs": inv,
        "invalid_cause_counts": dict(sorted(cause_counts.items())),
        "legacy_identical": sum(r["legacy_identical"] for r in inv),
        "legacy_identical_all": sum(same_run(r, v1[i]) for i, r in by_cfg["legacy"].items()),
        "legacy_runs": len(by_cfg["legacy"]),
        "fixed_invalid": sum(r["fixed_verdict"] == "INVALID" for r in inv),
    }
