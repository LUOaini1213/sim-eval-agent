"""Turn an agent result into report.json / REPORT.md / runs.jsonl.

Every claim carries the run ids it rests on, and its numbers are recomputed from those
runs by :func:`build_claims`. :func:`verify` re-derives verdicts and claims from a
``runs.jsonl`` alone, so a report that drifted from its evidence fails loudly.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from statistics import mean

from . import criteria
from .attribution import majority_fail
from .criteria import CRITERIA, INVALID, PASS
from .scenario import PARAMS, Scenario
from .stats import boundary_from_rates

KPI_COLS = ("mean_delay_s", "ramp_p95_delay_s", "merge_speed_kmh", "ttc_per_1000veh",
            "throughput_veh", "ramp_queue_max_veh", "teleports", "collisions")


def _match(runs: list[dict], base: dict, **kw) -> list[dict]:
    """Runs equal to ``base`` (canonical nominal) except for kw overrides, any seed."""
    want = {**base, **kw}
    out = [r for r in runs if all(r["scenario"][k] == v for k, v in want.items() if k != "seed")]
    return sorted(out, key=lambda r: r["scenario"]["seed"])


def _mean(rs: list[dict], k: str) -> float | None:
    vals = [r["kpis"][k] for r in rs if r["kpis"].get(k) is not None]
    return round(mean(vals), 2) if vals else None


def build_claims(result: dict) -> list[dict]:
    from .agent import morris_summary

    runs, nominal, seeds = result["runs"], result["nominal"], result["config"]["seeds"]
    claims: list[dict] = []

    def add(text: str, values: dict, evidence: list[str]) -> None:
        claims.append({"id": f"C{len(claims) + 1}", "text": text, "values": values, "evidence": sorted(evidence)})

    ctrls = list(result["config"]["controllers"])
    if result["config"].get("reference_controller"):
        ctrls.append(result["config"]["reference_controller"])
    for c in ctrls:
        rs = [r for r in _match(runs, nominal, controller=c) if r["scenario"]["seed"] in seeds]
        if not rs:
            continue
        vals = {k: _mean(rs, k) for k in KPI_COLS}
        vals["verdicts"] = [r["eval"]["verdict"] for r in rs]
        add(f"Nominal scenario, controller '{c}': mean over {len(rs)} seeds.", vals, [r["id"] for r in rs])

    for c in result["config"]["controllers"]:  # config order, not dict order (JSON is written sorted)
        rows = result["oat"].get(c)
        if not rows:
            continue
        top = rows[0]
        lv = max(top["levels"], key=lambda k: abs(top["levels"][k]["mean_delta_margin"]))
        L = top["levels"][lv]
        nom = [r for r in _match(runs, nominal, controller=c) if r["scenario"]["seed"] in seeds]
        add(
            f"One-at-a-time (paired seeds), controller '{c}': the most influential parameter is "
            f"'{top['param']}'; moving it to {lv}={L['value']} changes the run margin by "
            f"{L['mean_delta_margin']} on average (per-seed range {L['min_delta_margin']}..{L['max_delta_margin']}).",
            {"param": top["param"], "level": lv, "value": L["value"], "mean_delta_margin": L["mean_delta_margin"],
             "min_delta_margin": L["min_delta_margin"], "max_delta_margin": L["max_delta_margin"],
             "verdicts": L["verdicts"]},
            L["run_ids"] + [r["id"] for r in nom],
        )

    for b in result["boundaries"]:
        p = PARAMS[b["param"]]
        at_pass = [r for r in _match(runs, nominal, controller=b["controller"], **{b["param"]: b["last_pass"]})
                   if r["scenario"]["seed"] in seeds]
        at_fail = [r for r in _match(runs, nominal, controller=b["controller"], **{b["param"]: b["first_fail"]})
                   if r["scenario"]["seed"] in seeds]
        failed_crit = sorted({k for r in at_fail for k in r["eval"]["failed"] + r["eval"]["invalid"]})
        add(
            f"Boundary, controller '{b['controller']}' along '{b['param']}' ({p.unit}), other parameters nominal: "
            f"majority PASS at {b['last_pass']}, majority not-PASS at {b['first_fail']} "
            f"(bisection width {b['width']}, tolerance {b['tol']}, "
            f"{'monotone' if b['monotonicity']['monotone'] else 'NOT monotone'} over "
            f"{len(b['monotonicity']['points'])} evaluated points).",
            {"controller": b["controller"], "param": b["param"], "last_pass": b["last_pass"],
             "first_fail": b["first_fail"], "pass_verdicts": [r["eval"]["verdict"] for r in at_pass],
             "fail_verdicts": [r["eval"]["verdict"] for r in at_fail], "criteria_violated_at_fail": failed_crit},
            [r["id"] for r in at_pass + at_fail],
        )

    for c in result["config"]["controllers"]:
        strat = [s for s in result["screen"].get("stratified", []) if s["controller"] == c
                 and s["fail_rate_low"] is not None and s["fail_rate_high"] is not None]
        if not strat:
            continue
        def contrast(x: dict) -> float:
            return round(abs(x["fail_rate_high"] - x["fail_rate_low"]), 3)

        best = max(contrast(x) for x in strat)
        tied = sorted(x["param"] for x in strat if contrast(x) == best)
        ids = strat[0]["run_ids"]
        bad = sum(1 for r in runs if r["id"] in set(ids) and r["eval"]["verdict"] != PASS)
        add(
            f"Screening (Latin hypercube over the full ranges, seed {seeds[0]}), controller '{c}': "
            f"{bad} of {len(ids)} runs are not-PASS; the largest lower-half vs upper-half difference in "
            f"not-PASS rate is {best}, shared by {', '.join(tied)}.",
            {"not_pass": bad, "runs": len(ids), "largest_contrast": best, "params_with_largest_contrast": tied},
            ids,
        )

    by_id = {r["id"]: r for r in runs}
    for rf in result.get("refined") or []:
        counts = [(x, sum(by_id[i]["eval"]["verdict"] == PASS for i in rf["run_ids"][str(x)]), len(rf["run_ids"][str(x)]))
                  for x in rf["grid"]]
        res = boundary_from_rates(counts, rf["pass_side"])
        add(
            f"Refined boundary, controller '{rf['controller']}' along '{rf['param']}' ({PARAMS[rf['param']].unit}): "
            f"pass rate over {len(rf['seeds'])} paired seeds at {len(counts)} values; Wilson 95% band "
            f"{res['band']}, 50% crossing of the isotonic fit x50={res['x50']} "
            f"(5-seed bisection gave {rf['bisection']}).",
            {"controller": rf["controller"], "param": rf["param"], "bisection": rf["bisection"],
             "band": res["band"], "x50": res["x50"], "band_closed": res["band_closed"],
             "monotone_within_ci": res["monotone_within_ci"], "points": res["points"]},
            [i for x in rf["grid"] for i in rf["run_ids"][str(x)]],
        )

    mo_res = result.get("morris") or {}
    for c in result["config"]["controllers"]:
        if c not in mo_res.get("by_controller", {}):
            continue
        nom = Scenario.from_dict(nominal)
        summ = morris_summary(by_id, mo_res["trajectories"], mo_res["ranges"], c, mo_res["seeds"], nom)
        ids = sorted({nom.with_(controller=c, seed=s, **pt).id
                      for pts in mo_res["trajectories"] for pt in pts for s in mo_res["seeds"]})
        add(
            f"Morris screening (run margin; r={mo_res['r']} trajectories, {mo_res['levels']} levels, "
            f"paired seeds {mo_res['seeds']}, calibrated ranges), controller '{c}': "
            f"ranking by mu* {summ['ranking']}.",
            {"ranking": summ["ranking"], "stats": summ["stats"], "runs": summ["runs"],
             "not_pass_runs": summ["not_pass_runs"], "invalid_runs": summ["invalid_runs"]},
            ids,
        )

    by_crit = {c.kpi: [r["id"] for r in runs if c.kpi in r["eval"]["failed"]] for c in CRITERIA}
    add("Failure modes over all runs: number of runs violating each criterion.",
        {k: len(v) for k, v in by_crit.items()} | {"runs": len(runs)}, sorted({i for v in by_crit.values() for i in v}))
    inv = [r for r in runs if r["eval"]["verdict"] == INVALID]
    add("Validity: runs with teleports or collisions (excluded from PASS/FAIL, counted as not-PASS).",
        {"invalid_runs": len(inv), "runs": len(runs),
         "teleports": sum(r["kpis"]["teleports"] for r in runs),
         "collisions": sum(r["kpis"]["collisions"] for r in runs),
         "collision_lanes": dict(sorted(Counter(l for r in runs for l in r["kpis"].get("collision_lanes", [])).items())),
         "invalid_by_phase": dict(sorted(Counter(r["phase"] for r in inv).items())),
         "invalid_with_incident": sum(1 for r in inv if r["scenario"]["incident_duration"] > 0)},
        [r["id"] for r in inv])
    return claims


def build_report(result: dict, meta: dict) -> dict:
    rep = {k: v for k, v in result.items() if k != "runs"}
    rep["meta"] = meta
    rep["criteria"] = [{"kpi": c.kpi, "op": c.op, "limit": c.limit, "why": c.why} for c in CRITERIA]
    rep["verdict_counts"] = {v: sum(r["eval"]["verdict"] == v for r in result["runs"])
                             for v in (PASS, criteria.FAIL, INVALID)}
    rep["claims"] = build_claims(result)
    return rep


def write_all(result: dict, meta: dict, out_dir: Path) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "runs.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for r in result["runs"]:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    rep = build_report(result, meta)
    (out / "report.json").write_text(json.dumps(rep, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    (out / "REPORT.md").write_text(render_markdown(rep), encoding="utf-8", newline="\n")
    return rep


RESULT_KEYS = ("config", "nominal", "policy", "stop_reason", "runs_executed", "batches", "actions",
               "screen", "oat", "boundaries", "refined", "morris")


def rebuild(results_dir: Path) -> dict:
    """Re-render report.json / REPORT.md from runs.jsonl + the stored agent trace (no SUMO)."""
    d = Path(results_dir)
    rep = json.loads((d / "report.json").read_text(encoding="utf-8"))
    result = {k: rep[k] for k in RESULT_KEYS} | {"runs": load_runs(d / "runs.jsonl")}
    return write_all(result, rep["meta"], d)


def load_runs(path: Path) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def verify(results_dir: Path) -> list[str]:
    """Return a list of problems (empty = report consistent with runs.jsonl)."""
    d = Path(results_dir)
    runs = load_runs(d / "runs.jsonl")
    rep = json.loads((d / "report.json").read_text(encoding="utf-8"))
    problems = []
    ids = {r["id"] for r in runs}
    for r in runs:
        again = criteria.evaluate(r["kpis"])
        if again != r["eval"]:
            problems.append(f"run {r['id']}: stored eval differs from criteria applied to its KPIs")
    result = {k: rep.get(k) for k in ("config", "nominal", "oat", "boundaries", "screen", "refined", "morris")} | {"runs": runs}
    fresh = build_claims(result)
    if fresh != rep["claims"]:
        problems.append("claims in report.json differ from claims rebuilt from runs.jsonl")
    problems += verify_design(rep)
    for c in rep["claims"]:
        missing = [e for e in c["evidence"] if e not in ids]
        if missing:
            problems.append(f"{c['id']}: evidence ids not in runs.jsonl: {missing[:3]}")
    for b in rep["boundaries"]:
        for st in b["steps"]:
            vs = [next(r for r in runs if r["id"] == i)["eval"]["verdict"] for i in st["run_ids"]]
            if vs != st["verdicts"] or majority_fail(vs) != st["failed"]:
                problems.append(f"boundary {b['controller']}/{b['param']} step {st['value']}: verdicts mismatch")
    return problems


def verify_design(rep: dict) -> list[str]:
    """The stored refinement / Morris design must follow from the stored boundaries and config."""
    from .morris import calibrated_ranges, scale, trajectories

    problems = []
    for rf in rep.get("refined") or []:
        b = next((b for b in rep["boundaries"] if b["controller"] == rf["controller"] and b["param"] == rf["param"]), None)
        if b is None or [b["last_pass"], b["first_fail"]] != rf["bisection"]:
            problems.append(f"refined {rf['controller']}/{rf['param']}: no matching bisection boundary")
    mo_res = rep.get("morris") or {}
    if mo_res:
        cfg = rep["config"]
        ranges = calibrated_ranges(rep["nominal"], rep["boundaries"])
        traj = [[scale(u, ranges) for u in pts]
                for pts in trajectories(list(PARAMS), cfg["morris_r"], cfg["morris_levels"], seed=cfg["agent_seed"])]
        if ranges != mo_res["ranges"]:
            problems.append("Morris ranges differ from calibrated_ranges(nominal, boundaries)")
        if traj != mo_res["trajectories"]:
            problems.append("Morris trajectories differ from the design implied by the config")
    return problems


# ---------------------------------------------------------------------- markdown
def _fmt(v) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:g}"
    if isinstance(v, list):
        return "/".join(str(x) for x in v)
    return str(v)


def render_markdown(rep: dict) -> str:
    m = rep["meta"]
    L = [
        "# Simulation-evaluation report",
        "",
        f"SUMO {m['sumo_version']} | net sha256 `{m['net_sha256'][:16]}` | policy `{rep['policy']}` | "
        f"{rep['runs_executed']} runs, budget {rep['config']['budget']} | wall time {m['wall_time_s']} s "
        f"({m['jobs']} worker processes) | generated {m['date']}",
        "",
        f"Stop reason: {rep['stop_reason']}.",
        "",
        "Verdict counts: " + ", ".join(f"{k} {v}" for k, v in rep["verdict_counts"].items()) + ".",
        "",
        "## Pass/fail criteria (project-defined)",
        "",
        "| KPI | limit | meaning |",
        "|---|---|---|",
    ]
    L += [f"| `{c['kpi']}` | {c['op']} {c['limit']:g} | {c['why']} |" for c in rep["criteria"]]
    L += ["", "Validity: `teleports` = 0 and `collisions` = 0, otherwise the run is INVALID.", ""]

    L += ["## Boundaries found (bisection, other parameters nominal, majority of seeds)", "",
          "| controller | parameter | last PASS | first not-PASS | width | tol | converged | monotone | steps |",
          "|---|---|---|---|---|---|---|---|---|"]
    for b in rep["boundaries"]:
        L.append(f"| {b['controller']} | {b['param']} | {_fmt(b['last_pass'])} | {_fmt(b['first_fail'])} | "
                 f"{_fmt(b['width'])} | {_fmt(b['tol'])} | {b['converged']} | {b['monotonicity']['monotone']} | "
                 f"{len(b['steps'])} |")
    if not rep["boundaries"]:
        L.append("| - | - | - | - | - | - | - | - | - |")

    if rep.get("refined"):
        L += ["", "## Refined boundaries (pass rate over paired seeds, Wilson 95% interval)", "",
              "Rule: a value is confidently PASS if the interval's lower end > 0.5, confidently not-PASS if its "
              "upper end < 0.5. The band runs from the last confidently-PASS value to the first confidently-not-PASS "
              "value; x50 is where the isotonic fit of the pass rate crosses 0.5.", ""]
        for c in rep["claims"]:
            if not c["text"].startswith("Refined boundary"):
                continue
            v = c["values"]
            L += [f"### {v['controller']} / {v['param']}: band {v['band']}, x50 {v['x50']} (bisection {v['bisection']})", "",
                  "| value | passes / n | rate | Wilson 95% | class |", "|---|---|---|---|---|"]
            L += [f"| {_fmt(pt['x'])} | {pt['passes']}/{pt['n']} | {pt['rate']:.2f} | "
                  f"{pt['wilson95'][0]:.2f}-{pt['wilson95'][1]:.2f} | {pt['class']} |" for pt in v["points"]]
            L.append("")
    if rep.get("morris"):
        mo_res = rep["morris"]
        L += ["", "## Morris screening (elementary effects of the run margin, per unit of calibrated range)", "",
              "| parameter | range | rule |", "|---|---|---|"]
        L += [f"| {k} | {_fmt(v['lo'])}..{_fmt(v['hi'])} | {v['rule']} |" for k, v in mo_res["ranges"].items()]
        for c in rep["claims"]:
            if not c["text"].startswith("Morris screening"):
                continue
            v = c["values"]
            name = c["text"].split("'")[1]
            L += ["", f"### controller `{name}` ({v['runs']} runs, {v['not_pass_runs']} not-PASS, {v['invalid_runs']} INVALID)", "",
                  "| parameter | mu* | mu | sigma | sigma_seed | n |", "|---|---|---|---|---|---|"]
            L += [f"| {f} | {v['stats'][f]['mu_star']:.4f} | {v['stats'][f]['mu']:.4f} | {v['stats'][f]['sigma']:.4f} | "
                  f"{v['stats'][f]['sigma_seed']:.4f} | {v['stats'][f]['n']} |" for f in v["ranking"]]
        L.append("")

    L += ["", "## One-at-a-time sensitivity (paired seeds; delta of run margin vs nominal)", ""]
    for c in rep["config"]["controllers"]:
        rows = rep["oat"].get(c, [])
        L += [f"### controller `{c}`", "",
              "| parameter | lo value | mean delta (lo) | verdicts (lo) | hi value | mean delta (hi) | verdicts (hi) | influence | flip |",
              "|---|---|---|---|---|---|---|---|---|"]
        for r in rows:
            lo, hi = r["levels"].get("lo", {}), r["levels"].get("hi", {})
            L.append(f"| {r['param']} | {_fmt(lo.get('value'))} | {_fmt(lo.get('mean_delta_margin'))} | "
                     f"{_fmt(lo.get('verdicts'))} | {_fmt(hi.get('value'))} | {_fmt(hi.get('mean_delta_margin'))} | "
                     f"{_fmt(hi.get('verdicts'))} | {_fmt(r['influence'])} | {_fmt(r['flip_levels']) or '-'} |")
        L.append("")

    if rep["screen"]:
        L += ["## Screening: stratified not-PASS rate (lower vs upper half of each range)", "",
              "| controller | parameter | split | n low | rate low | n high | rate high |", "|---|---|---|---|---|---|---|"]
        for s in rep["screen"]["stratified"]:
            L.append(f"| {s['controller']} | {s['param']} | {_fmt(s['split_at'])} | {s['n_low']} | "
                     f"{_fmt(s['fail_rate_low'])} | {s['n_high']} | {_fmt(s['fail_rate_high'])} |")
        L.append("")

    L += ["## Agent decisions", "", "| # | action | policy | runs before | why |", "|---|---|---|---|---|"]
    for i, a in enumerate(rep["actions"], 1):
        L.append(f"| {i} | `{a['action']}` | {a['policy']} | {a['runs_so_far']} | {a['why']} |")

    L += ["", "## Claims and evidence", "",
          "Each claim's numbers are recomputed from the listed runs in `runs.jsonl` by "
          "`python scripts/verify_results.py`.", ""]
    for c in rep["claims"]:
        ev = ", ".join(f"`{e}`" for e in c["evidence"][:12])
        more = f" (+{len(c['evidence']) - 12} more)" if len(c["evidence"]) > 12 else ""
        L += [f"**{c['id']}.** {c['text']}", "",
              "values: `" + json.dumps(c["values"], sort_keys=True) + "`", "",
              f"evidence ({len(c['evidence'])} runs): {ev}{more}", ""]
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------- experiments
def verify_experiments(results_dir: Path) -> list[str]:
    """Recompute results/diagnosis and results/llm summaries from their run/log files."""
    from .diagnosis import build_summary
    from .llm_compare import summarize_campaigns

    d = Path(results_dir)
    problems = []
    diag = d / "diagnosis"
    if (diag / "summary.json").exists():
        stored = json.loads((diag / "summary.json").read_text(encoding="utf-8"))
        recs = load_runs(diag / "runs.jsonl")
        fresh = build_summary(recs, load_runs(d / "v1" / "runs.jsonl"), stored["compare_ids"], stored["invalid_ids"])
        if {k: v for k, v in stored.items() if k != "meta"} != fresh:
            problems.append("diagnosis/summary.json differs from the summary rebuilt from diagnosis/runs.jsonl")
        for r in recs:
            if r["kpis"]["collisions"] != len(r["log"]["collisions"]):
                problems.append(f"diagnosis run {r['config']}/{r['id']}: collision count differs from the SUMO log")
    llm = d / "llm"
    if (llm / "summary.json").exists():
        stored = json.loads((llm / "summary.json").read_text(encoding="utf-8"))
        logs = load_runs(llm / "llm_log.jsonl")
        fresh = summarize_campaigns(stored["campaigns"], logs)
        if fresh["per_campaign"] != stored["per_campaign"] or fresh["totals"] != stored["totals"]:
            problems.append("llm/summary.json differs from the summary rebuilt from llm/llm_log.jsonl")
        runs = {r["id"]: r for r in load_runs(d / "runs.jsonl")}
        runs |= {r["id"]: r for r in load_runs(llm / "runs_extra.jsonl")} if (llm / "runs_extra.jsonl").exists() else {}
        for c in stored["campaigns"]:
            for b in c["boundaries"]:
                for st in b["steps"]:
                    missing = [i for i in st["run_ids"] if i not in runs]
                    if missing:
                        problems.append(f"llm {c['name']} {b['controller']}/{b['param']}: runs {missing[:2]} not on record")
                        continue
                    vs = [criteria.evaluate(runs[i]["kpis"])["verdict"] for i in st["run_ids"]]
                    if vs != st["verdicts"] or majority_fail(vs) != st["failed"]:
                        problems.append(f"llm {c['name']} {b['controller']}/{b['param']} step {st['value']}: verdicts mismatch")
        for e in logs:
            if e["accepted"] != (e["rejection"] is None) or (e["accepted"] and e["used"] != e["parsed"]):
                problems.append(f"llm log {e['campaign']}#{e['step']}: accepted/used inconsistent")
    return problems
