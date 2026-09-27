"""Mutation-test the test suite: break the code on purpose, confirm the named tests fail.

Each mutation is an exact, single-occurrence text replacement. For each one the script
(1) runs the selected tests on clean code and requires them to pass, (2) applies the
mutation and requires them to FAIL, (3) restores the file byte-for-byte. It writes
MUTATION.md with the outcome. Run from the repo root:  python scripts/mutation_check.py
"""
import subprocess
import sys
import time
from pathlib import Path

import _path  # noqa: F401

ROOT = _path.ROOT

MUTATIONS = [
    ("M1", "simeval/kpi.py", "if v is not None and v < threshold:", "if v is not None and v <= threshold:",
     "SSM TTC count uses <= instead of strict <", "tests/test_kpi.py"),
    ("M2", "simeval/kpi.py", 'd = float(el.get("timeLoss", 0.0)) + float(el.get("departDelay", 0.0))',
     'd = float(el.get("timeLoss", 0.0))', "delay drops departDelay (insertion backlog)", "tests/test_kpi.py"),
    ("M3", "simeval/kpi.py", 'if el.get("id") not in MERGE_LOOPS or float(el.get("begin")) >= until:',
     'if el.get("id") not in MERGE_LOOPS:', "merge speed ignores the end of the demand window", "tests/test_kpi.py"),
    ("M4", "simeval/criteria.py", 'return value <= self.limit if self.op == "<=" else value >= self.limit',
     'return value < self.limit if self.op == "<=" else value >= self.limit', "upper limits become exclusive",
     "tests/test_criteria.py"),
    ("M5", "simeval/criteria.py", 'VALIDITY = (("teleports", 0), ("collisions", 0))', 'VALIDITY = (("teleports", 0),)',
     "collisions no longer invalidate a run", "tests/test_criteria.py"),
    ("M6", "simeval/runner.py", '"--seed", str(s.seed),', '"--seed", "1",', "every run uses SUMO seed 1 (seed dropped)",
     "tests/test_scenario.py tests/test_sumo_integration.py"),
    ("M7", "simeval/attribution.py", 'return [(s, moved[s]["eval"]["margin"] - nominal[s]["eval"]["margin"]) for s in seeds]',
     'return [(s, moved[s]["eval"]["margin"] - nominal[seeds[-1 - seeds.index(s)]]["eval"]["margin"]) for s in seeds]',
     "OAT pairs runs with the wrong seed", "tests/test_agent_mock.py"),
    ("M8", "simeval/attribution.py", "return 2 * bad > len(verdicts)", "return bad > 0",
     "majority rule becomes any-seed-fails", "tests/test_agent_mock.py"),
    ("M9", "simeval/boundary.py", "        if failed:\n            self.fail_value = value\n        else:\n            self.pass_value = value",
     "        if not failed:\n            self.fail_value = value\n        else:\n            self.pass_value = value",
     "bisection moves the wrong end", "tests/test_agent_mock.py"),
    ("M10", "simeval/controller.py", "r = self.rate + self.k_r * (self.target - m.occupancy_pct)",
     "r = self.rate + self.k_r * (m.occupancy_pct - self.target)", "ALINEA feedback sign flipped",
     "tests/test_controller.py"),
    ("M11", "simeval/network.py", 'return _HEADER_RE.sub("", text, count=1)', "return text",
     "timestamped netconvert header kept in the net file", "tests/test_sumo_integration.py"),
    ("M12", "simeval/scenario.py", "else round(float(d[name]), 4)", "else float(d[name])",
     "scenario id no longer canonicalises floats", "tests/test_scenario.py"),
    ("M13", "simeval/policy.py", "if action is not None and action not in allowed:", "if False:",
     "LLM policy accepts vocabulary items it is not allowed to pick", "tests/test_policy.py"),
    ("M14", "simeval/report.py", 'if fresh != rep["claims"]:', "if False:",
     "verify() stops comparing claims with runs.jsonl", "tests/test_results_consistency.py"),
    ("M15", "scripts/render_readme.py", "        if current != block:", "        if False:",
     "README --check never fails", "tests/test_results_consistency.py"),
    # ---- added in round 2 (INVALID fix, 20-seed refinement, Morris, LLM comparison)
    ("M16", "simeval/stats.py", "    den = 1 + z * z / n", "    den = 1",
     "Wilson interval loses its denominator (becomes a skewed Wald-like interval)", "tests/test_stats.py"),
    ("M17", "simeval/stats.py", "    start = 0 if last_pass_i is None else last_pass_i + 1", "    start = 0",
     "band end searched from the start of the axis, not after the last confident PASS", "tests/test_stats.py"),
    ("M18", "simeval/stats.py", "while len(blocks) > 1 and blocks[-2][0] < blocks[-1][0]:",
     "while len(blocks) > 1 and blocks[-2][0] > blocks[-1][0]:", "isotonic fit pools the wrong way", "tests/test_stats.py"),
    ("M19", "simeval/morris.py", "                ee = (y[(j, i + 1, s)] - y[(j, i, s)]) / step",
     "                ee = (y[(j, i + 1, s)] - y[(j, i, seeds[0])]) / step",
     "elementary effects no longer paired within a seed", "tests/test_morris.py"),
    ("M20", "simeval/morris.py", "if x[n] + delta <= 1.0 + 1e-9 else", "if True else",
     "trajectory steps can leave the unit cube", "tests/test_morris.py"),
    ("M21", "simeval/morris.py", "            d = min(abs(m - nom) for m in mids)", "            d = max(abs(m - nom) for m in mids)",
     "calibrated range uses the farthest boundary instead of the nearest", "tests/test_morris.py"),
    ("M22", "simeval/policy.py",
     'score = abs(r["levels"][lv]["mean_delta_margin"]) if "levels" in r else r["influence"]',
     'score = r["influence"]', "directions ranked by the parameter's overall influence, not their own effect",
     "tests/test_policy.py"),
    ("M23", "simeval/runner.py", "        if dist > 0 and dist >= speed * speed / (2.0 * decel) + margin:",
     "        if dist > 0:", "stall may pick a vehicle that cannot stop with ordinary braking", "tests/test_incident.py"),
    ("M24", "simeval/kpi.py",
     'trip = parse_tripinfo(d / "tripinfo.xml", frozenset({BLOCKER_ID} | ({inc_id} if inc_id else set())))',
     'trip = parse_tripinfo(d / "tripinfo.xml")', "the stalled incident vehicle is counted as a traveller",
     "tests/test_kpi.py"),
    ("M25", "simeval/diagnosis.py", 'if s["vehicle"] == c["victim"] and c["time"] - WINDOW_S <= s["time"] <= c["time"]]',
     'if s["vehicle"] == c["victim"] and s["time"] <= c["time"]]',
     "collision blamed on any earlier emergency stop of the victim, however old", "tests/test_diagnosis.py"),
    ("M26", "simeval/controller.py", "    return max(cycle - GREEN_S - amber_s, 0.5)", "    return max(cycle - GREEN_S, 0.5)",
     "amber added on top of the cycle (meter rate silently lowered)", "tests/test_controller.py"),
    ("M27", "simeval/agent.py", "                add.append(self._clip(p, pass_end + sgn * step))",
     "                add.append(self._clip(p, pass_end - sgn * step))",
     "refinement extends the grid towards the fail side", "tests/test_agent_mock.py"),
    ("M28", "simeval/report.py", '        if ranges != mo_res["ranges"]:', "        if False:",
     "verify() stops checking the Morris ranges against the boundaries", "tests/test_agent_mock.py"),
    ("M29", "simeval/report.py", '        if {k: v for k, v in stored.items() if k != "meta"} != fresh:', "        if False:",
     "verify_experiments() stops rebuilding the diagnosis summary", "tests/test_results_consistency.py"),
    ("M30", "simeval/llm_compare.py", '"agree_with_deterministic": sum(e["parsed"] == e["deterministic_choice"] for e in cl),',
     '"agree_with_deterministic": sum(e["used"] == e["deterministic_choice"] for e in cl),',
     "agreement counts the deterministic fallback as the LLM agreeing", "tests/test_llm_compare.py"),
]


HISTORY = """
## History

- 2026-09-26, first pass: 14/15 caught. **M12 survived**: `test_id_ignores_float_noise_but_not_real_changes`
  only built scenarios through `Scenario.with_()`, which already rounds floats, so removing the rounding in
  `canonical()` went unnoticed. Scenarios built with the constructor (as `Scenario.from_dict` does when
  reading results) would have got a different id for the same parameters. The test now also builds one through
  the constructor; second pass: 15/15 caught.
- 2026-09-26, round 2: M13's pattern was rewritten with the new policy code; M16-M30 cover the code added
  for the INVALID fix, the 20-seed refinement, Morris screening and the LLM comparison. See the table for
  the outcome of this pass.
"""


def pytest(selector: str) -> tuple[int, str]:
    p = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *selector.split()],
                       cwd=ROOT, capture_output=True, text=True)
    last = [ln for ln in p.stdout.strip().splitlines() if ln.strip()]
    return p.returncode, (last[-1] if last else p.stderr.strip()[-200:])


def main() -> int:
    rows, ok = [], True
    t0 = time.perf_counter()
    for mid, rel, old, new, what, sel in MUTATIONS:
        path = ROOT / rel
        original = path.read_bytes()
        text = original.decode("utf-8")
        n = text.count(old)
        if n != 1:
            rows.append((mid, rel, what, sel, "-", f"ERROR: pattern found {n} times", "no"))
            ok = False
            continue
        rc0, s0 = pytest(sel)
        if rc0 != 0:
            rows.append((mid, rel, what, sel, s0, "baseline failing", "no"))
            ok = False
            continue
        try:
            path.write_bytes(text.replace(old, new).encode("utf-8"))
            rc1, s1 = pytest(sel)
        finally:
            path.write_bytes(original)
        caught = rc1 != 0
        ok &= caught
        rows.append((mid, rel, what, sel, s0, s1, "yes" if caught else "NO"))
        print(f"{mid}: {'caught' if caught else 'SURVIVED'}  ({s1})")
    wall = round(time.perf_counter() - t0, 1)
    md = [
        "# Mutation check",
        "",
        "Generated by `python scripts/mutation_check.py`. Each row breaks the code on purpose with one exact text",
        "replacement (see `MUTATIONS` in the script), runs the listed tests, and restores the file.",
        "A mutation is *caught* when those tests pass on clean code and fail on the mutant.",
        "",
        f"{sum(r[-1] == 'yes' for r in rows)}/{len(rows)} caught; wall time {wall} s.",
        "",
        "| id | file | mutation | tests | clean run | mutant run | caught |",
        "|---|---|---|---|---|---|---|",
    ]
    md += [f"| {r[0]} | `{r[1]}` | {r[2]} | `{r[3]}` | {r[4]} | {r[5]} | {r[6]} |" for r in rows]
    md += HISTORY.splitlines()
    (ROOT / "MUTATION.md").write_text("\n".join(md) + "\n", encoding="utf-8", newline="\n")
    print(f"{sum(r[-1] == 'yes' for r in rows)}/{len(rows)} caught -> MUTATION.md")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
