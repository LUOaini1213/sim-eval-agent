"""Check results/ for internal consistency: the main report against runs.jsonl (claims, verdicts,
evidence, refinement and Morris design) and the diagnosis / LLM summaries against their logs."""
import argparse
import sys

import _path  # noqa: F401
from simeval.report import verify, verify_experiments

ap = argparse.ArgumentParser()
ap.add_argument("--dir", default=str(_path.ROOT / "results"))
d = ap.parse_args().dir
problems = verify(d) + verify_experiments(d)
for p in problems:
    print("PROBLEM:", p)
print("OK" if not problems else f"{len(problems)} problem(s)")
sys.exit(1 if problems else 0)
