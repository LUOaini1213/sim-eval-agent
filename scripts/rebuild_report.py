"""Re-render results/report.json and REPORT.md from runs.jsonl and the stored agent trace.

No simulation is re-run; use this after changing report formatting or claim wording.
"""
import argparse

import _path  # noqa: F401
from simeval.report import rebuild

ap = argparse.ArgumentParser()
ap.add_argument("--dir", default=str(_path.ROOT / "results"))
rep = rebuild(ap.parse_args().dir)
print(f"rebuilt {len(rep['claims'])} claims")
