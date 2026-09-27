"""Compare LLM-policy campaigns with the deterministic campaign (pure functions, recomputable)."""
from __future__ import annotations

from collections import Counter


def _key(b: dict) -> str:
    return f"{b['controller']}/{b['param']}"


def summarize_campaigns(campaigns: list[dict], logs: list[dict]) -> dict:
    det = next(c for c in campaigns if c["policy"] == "deterministic")
    det_b = {_key(b): [b["last_pass"], b["first_fail"]] for b in det["boundaries"]}
    det_actions = [a["action"] for a in det["actions"]]
    per = []
    for c in campaigns:
        if c["policy"] == "deterministic":
            continue
        cl = [e for e in logs if e["campaign"] == c["name"]]
        mine = {_key(b): [b["last_pass"], b["first_fail"]] for b in c["boundaries"]}
        per.append({
            "name": c["name"],
            "calls": len(cl),
            "valid": sum(e["accepted"] for e in cl),
            "invalid": sum(not e["accepted"] for e in cl),
            "rejections": dict(sorted(Counter(e["rejection"] for e in cl if not e["accepted"]).items())),
            "agree_with_deterministic": sum(e["parsed"] == e["deterministic_choice"] for e in cl),
            "actions": [a["action"] for a in c["actions"]],
            "same_actions_as_deterministic": [a["action"] for a in c["actions"]] == det_actions,
            "runs_used": c["runs_used"],
            "boundaries_found": sorted(mine),
            "boundaries_missing_vs_deterministic": sorted(set(det_b) - set(mine)),
            "boundaries_extra_vs_deterministic": sorted(set(mine) - set(det_b)),
            "boundary_differences": {k: {"deterministic": det_b[k], "llm": mine[k]}
                                     for k in sorted(set(det_b) & set(mine)) if det_b[k] != mine[k]},
            "latency_s_total": round(sum(e["latency_s"] for e in cl), 1),
            "unconverged": sorted(_key(b) for b in c["boundaries"] if not b["converged"]),
        })
    totals = {
        "llm_campaigns": len(per),
        "calls": sum(p["calls"] for p in per),
        "valid": sum(p["valid"] for p in per),
        "invalid": sum(p["invalid"] for p in per),
        "rejections": dict(sorted(sum((Counter(p["rejections"]) for p in per), Counter()).items())),
        "agree_with_deterministic": sum(p["agree_with_deterministic"] for p in per),
        "campaigns_same_actions": sum(p["same_actions_as_deterministic"] for p in per),
        "campaigns_same_boundaries": sum(not p["boundaries_missing_vs_deterministic"]
                                         and not p["boundaries_extra_vs_deterministic"]
                                         and not p["boundary_differences"] for p in per),
        "deterministic_actions": det_actions,
        "deterministic_boundaries": det_b,
        "deterministic_runs_used": det["runs_used"],
        "deterministic_unconverged": sorted(_key(b) for b in det["boundaries"] if not b["converged"]),
    }
    return {"per_campaign": per, "totals": totals}
