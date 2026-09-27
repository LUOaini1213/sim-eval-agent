"""Re-simulate a deterministic sample of committed runs and compare KPIs + tripinfo hash.

    python scripts/rerun_check.py --n 6

Exact equality is expected on the same SUMO version and platform; other platforms may differ
(the script prints which KPIs changed). Uses the simulation options stored in report.json.
"""
import argparse
import sys
import tempfile

import _path  # noqa: F401
from simeval.evaluator import _run_one
from simeval.report import load_runs

ROOT = _path.ROOT


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--dir", default=str(ROOT / "results"))
    a = ap.parse_args()
    runs = load_runs(f"{a.dir}/runs.jsonl")
    import json

    opts = json.loads(open(f"{a.dir}/report.json", encoding="utf-8").read())["meta"].get("sim_options", {})
    opts = {**opts, "log_warnings": False}
    step = max(1, len(runs) // a.n)
    sample = runs[::step][: a.n]
    bad = 0
    with tempfile.TemporaryDirectory() as tmp:
        for r in sample:
            again = _run_one((r["scenario"], str(ROOT / "network" / "merge.net.xml"), tmp, False, opts))
            same = again["kpis"] == r["kpis"] and again["tripinfo_sha256"] == r["tripinfo_sha256"]
            bad += not same
            diff = "" if same else " " + ", ".join(
                f"{k} {r['kpis'].get(k)}->{again['kpis'].get(k)}" for k in sorted(r["kpis"])
                if again["kpis"].get(k) != r["kpis"].get(k))[:300]
            print(f"{r['id']} {r['phase']:<24} {r['eval']['verdict']:<8} {'identical' if same else 'DIFFERENT'}{diff}")
    print(f"{len(sample) - bad}/{len(sample)} identical")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
