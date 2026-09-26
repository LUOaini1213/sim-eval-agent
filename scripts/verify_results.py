"""Check that results/report.json is consistent with results/runs.jsonl (claims, verdicts, evidence)."""
import argparse
import sys

import _path  # noqa: F401
from simeval.report import verify

ap = argparse.ArgumentParser()
ap.add_argument("--dir", default=str(_path.ROOT / "results"))
problems = verify(ap.parse_args().dir)
for p in problems:
    print("PROBLEM:", p)
print("OK" if not problems else f"{len(problems)} problem(s)")
sys.exit(1 if problems else 0)
