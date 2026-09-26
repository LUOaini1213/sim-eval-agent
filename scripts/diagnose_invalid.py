"""Find out why v1 had INVALID runs, and compare incident simulation methods.

    python scripts/diagnose_invalid.py            # writes results/diagnosis/

1. Re-runs the 9 INVALID runs of results/v1 with the v1 simulation ('legacy': TraCI
   setDisallowed on incident_0, meter without amber) and SUMO warnings logged; checks the
   re-run is identical to the committed v1 run; attributes every collision to the victim's
   emergency stop just before it (simeval/diagnosis.py).
2. Runs the first 30 v1 runs that contain an incident under every incident method in
   ``CONFIGS`` (meter without amber, so only the incident method differs) plus the new
   default (stall + amber), and counts collisions, teleports and emergency stops by reason.
3. Re-runs the 9 INVALID scenarios with the new default.
"""
import argparse
import datetime as dt
import json
import sys
import time

import _path  # noqa: F401
from simeval.diagnosis import CONFIGS, build_summary
from simeval.evaluator import SumoEvaluator
from simeval.report import load_runs
from simeval.scenario import Scenario
from simeval.sumo_env import sumo_version

ROOT = _path.ROOT
N_COMPARE = 30


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "results" / "diagnosis"))
    ap.add_argument("--jobs", type=int, default=7)
    ap.add_argument("--work", default=str(ROOT / "work" / "diagnosis"))
    a = ap.parse_args()
    v1 = load_runs(ROOT / "results" / "v1" / "runs.jsonl")
    invalid_ids = [r["id"] for r in v1 if r["eval"]["verdict"] == "INVALID"]
    compare_ids = [r["id"] for r in v1 if r["scenario"]["incident_duration"] > 0][:N_COMPARE]
    by_id = {r["id"]: r for r in v1}
    plan = {name: (compare_ids + [i for i in invalid_ids if i not in compare_ids]
                   if name in ("legacy", "default") else compare_ids) for name in CONFIGS}
    records, walls = [], {}
    t_all = time.perf_counter()
    for name, (method, amber) in CONFIGS.items():
        ev = SumoEvaluator(ROOT / "network" / "merge.net.xml", f"{a.work}/{name}", jobs=a.jobs,
                           options={"incident_method": method, "amber_s": amber, "log_warnings": True})
        t0 = time.perf_counter()
        try:
            recs = ev.evaluate([Scenario.from_dict(by_id[i]["scenario"]) for i in plan[name]])
        finally:
            ev.close()
        walls[name] = round(time.perf_counter() - t0, 1)
        for r in recs:
            records.append({**r, "config": name, "incident_method": method, "amber_s": amber})
        print(f"{name:15} {len(recs)} runs in {walls[name]} s")
    summary = build_summary(records, v1, compare_ids, invalid_ids)
    summary["meta"] = {"sumo_version": sumo_version(), "date": dt.date.today().isoformat(), "jobs": a.jobs,
                       "wall_time_s": round(time.perf_counter() - t_all, 1), "wall_s_by_config": walls,
                       "runs": len(records), "configs": {k: list(v) for k, v in CONFIGS.items()}}
    from pathlib import Path
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "runs.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for r in records:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    (out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: summary[k] for k in ("invalid_cause_counts", "legacy_identical", "legacy_identical_all",
                                               "legacy_runs", "fixed_invalid")}, indent=1))
    for k, v in summary["comparison"].items():
        print(k, v)
    return 0


if __name__ == "__main__":
    sys.exit(main())
