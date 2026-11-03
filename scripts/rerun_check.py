"""Re-simulate a deterministic sample of committed runs and compare KPIs + tripinfo hash.

    python scripts/rerun_check.py --n 6          # sample of results/runs.jsonl (v2 options)
    python scripts/rerun_check.py --v1-invalid   # the INVALID runs of results/v1, v1 options

Exact equality is expected on the same SUMO version and platform; other platforms may differ
(the script prints which KPIs changed). The default mode uses the simulation options stored in
report.json; ``--v1-invalid`` uses the v1 simulation (``LEGACY_OPTIONS``: TraCI lane closure,
meter without amber), which is what ``scripts/diagnose_invalid.py`` re-runs, and the same
comparison as the diagnosis (``simeval.diagnosis.same_run``). Exit 1 on any mismatch. The
platform is printed first, so a log says where the comparison was made.
"""
import argparse
import json
import platform
import sys
import tempfile

import _path  # noqa: F401
from simeval.diagnosis import same_run
from simeval.evaluator import _run_one
from simeval.report import load_runs

ROOT = _path.ROOT


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--dir", default=str(ROOT / "results"))
    ap.add_argument("--v1-invalid", action="store_true",
                    help="re-run every INVALID run of results/v1 with the v1 simulation options")
    a = ap.parse_args()
    if a.v1_invalid:
        from simeval.runner import LEGACY_OPTIONS

        runs = load_runs(ROOT / "results" / "v1" / "runs.jsonl")
        sample = [r for r in runs if r["eval"]["verdict"] == "INVALID"]
        opts = {**LEGACY_OPTIONS.as_dict(), "log_warnings": False}
    else:
        runs = load_runs(f"{a.dir}/runs.jsonl")
        opts = json.loads(open(f"{a.dir}/report.json", encoding="utf-8").read())["meta"].get("sim_options", {})
        opts = {**opts, "log_warnings": False}
        step = max(1, len(runs) // a.n)
        sample = runs[::step][: a.n]
    print(f"platform: {platform.platform(terse=True)}")
    bad = 0
    with tempfile.TemporaryDirectory() as tmp:
        for r in sample:
            again = _run_one((r["scenario"], str(ROOT / "network" / "merge.net.xml"), tmp, False, opts))
            if a.v1_invalid:
                same = same_run(again, r)
            else:
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
