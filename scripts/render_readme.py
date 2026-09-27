"""Render the README results block from the committed results files.

    python scripts/render_readme.py          # rewrite the block between the markers
    python scripts/render_readme.py --check  # exit 1 if README and the results files disagree

Sources: results/report.json (main run), results/diagnosis/summary.json (INVALID diagnosis),
results/llm/summary.json (LLM vs deterministic), results/linux_check.json (WSL check).
A missing optional file just drops its section.
"""
import argparse
import json
import sys
from pathlib import Path

import _path  # noqa: F401

ROOT = _path.ROOT
BEGIN, END = "<!-- RESULTS:BEGIN -->", "<!-- RESULTS:END -->"


def _f(v, nd=1):
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.{nd}f}"
    return str(v)


def _seeds(verdicts: list[str]) -> str:
    return "".join({"PASS": "P", "FAIL": "F", "INVALID": "I"}[v] for v in verdicts)


def _band(b) -> str:
    return f"{_f(b[0])} .. {_f(b[1])}"


def render_main(rep: dict) -> list[str]:
    m = rep["meta"]
    claims = rep["claims"]
    vc = rep["verdict_counts"]
    so = m.get("sim_options", {})
    pw = ", ".join(f"{k} {v} s" for k, v in m.get("phase_walls_s", {}).items())
    L = [
        f"本机实跑 / measured run: SUMO {m['sumo_version']}, {rep['runs_executed']} runs "
        f"(budget {rep['config']['budget']}), wall time **{m['wall_time_s']} s** with {m['jobs']} worker processes "
        f"({m['platform']}, {m['cpu_count']} logical CPUs, shared with another job), date {m['date']}; by phase: {pw}. "
        f"Incident method `{so.get('incident_method')}`, meter amber {so.get('amber_s')} s. "
        f"Verdicts: PASS {vc['PASS']} / FAIL {vc['FAIL']} / INVALID {vc['INVALID']}. "
        f"Stop reason: {rep['stop_reason']}.",
        "",
        f"**名义场景 / nominal scenario** (mean over seeds {rep['config']['seeds']}):",
        "",
        "| controller | mean delay (s) | ramp p95 delay (s) | merge speed (km/h) | TTC<1.5 s per 1000 veh | throughput (veh) | verdicts | evidence |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for c in claims:
        if c["text"].startswith("Nominal scenario"):
            v = c["values"]
            name = c["text"].split("'")[1]
            L.append(f"| {name} | {_f(v['mean_delay_s'])} | {_f(v['ramp_p95_delay_s'])} | {_f(v['merge_speed_kmh'])} | "
                     f"{_f(v['ttc_per_1000veh'], 2)} | {_f(v['throughput_veh'])} | {'/'.join(v['verdicts'])} | {c['id']} |")
    L += ["", f"**5 种子二分边界 / bisection boundaries** (other parameters nominal, majority of seeds "
          f"{rep['config']['seeds']}; ramp/main demand in veh/h, incident duration in s):", "",
          "| controller | parameter | last PASS | seeds there | first not-PASS | seeds there | criteria violated | monotone on axis | evidence |",
          "|---|---|---|---|---|---|---|---|---|"]
    for c in claims:
        if c["text"].startswith("Boundary"):
            v = c["values"]
            mono = "yes" if "monotone over" in c["text"] and "NOT monotone" not in c["text"] else "no"
            L.append(f"| {v['controller']} | {v['param']} | {v['last_pass']} | {_seeds(v['pass_verdicts'])} | "
                     f"{v['first_fail']} | {_seeds(v['fail_verdicts'])} | "
                     f"{', '.join(v['criteria_violated_at_fail']) or '-'} | {mono} | {c['id']} |")
    refined = [c for c in claims if c["text"].startswith("Refined boundary")]
    if refined:
        n = len(rep["config"]["refine_seeds"])
        L += ["", f"**{n} 种子通过率边界 / pass rate over {n} paired seeds** (Wilson 95%; band = last confidently-PASS "
              "value .. first confidently-not-PASS value; x50 = 50% crossing of the isotonic fit):", "",
              f"| controller | parameter | 5-seed bisection | pass rate at grid values (passes/{n}) | Wilson band | x50 | band closed | monotone within CI | evidence |",
              "|---|---|---|---|---|---|---|---|---|"]
        for c in refined:
            v = c["values"]
            pts = sorted(v["points"], key=lambda p: p["x"])
            rates = ", ".join(f"{_f(p['x'])}: {p['passes']}" for p in pts)
            L.append(f"| {v['controller']} | {v['param']} | {v['bisection'][0]} .. {v['bisection'][1]} | {rates} | "
                     f"{_band(v['band'])} | {_f(v['x50'])} | {'yes' if v['band_closed'] else 'no'} | "
                     f"{'yes' if v['monotone_within_ci'] else 'no'} | {c['id']} |")
    if refined:
        outside = [c["id"] for c in refined if c["values"]["x50"] is not None
                   and not min(c["values"]["bisection"]) <= c["values"]["x50"] <= max(c["values"]["bisection"])]
        L += ["", f"x50 outside the 5-seed bisection interval: {len(outside)} of {len(refined)} boundaries "
                  f"({', '.join(outside) or 'none'})."]
    L += ["", "**最有影响的参数 / most influential parameter** (paired-seed one-at-a-time):", "",
          "| controller | parameter | moved to | mean delta of run margin | per-seed range | evidence |", "|---|---|---|---|---|---|"]
    for c in claims:
        if c["text"].startswith("One-at-a-time"):
            v = c["values"]
            name = c["text"].split("'")[1]
            L.append(f"| {name} | {v['param']} | {v['level']}={v['value']} | {v['mean_delta_margin']} | "
                     f"{v['min_delta_margin']} .. {v['max_delta_margin']} | {c['id']} |")
    morris = [c for c in claims if c["text"].startswith("Morris screening")]
    if morris:
        mo = rep["morris"]
        L += ["", f"**Morris 筛选 / Morris screening** (output = run margin; r={mo['r']} trajectories x "
              f"{len(PARAMS_ORDER(mo))} + 1 points, {mo['levels']} levels, paired seeds {mo['seeds']}; effects per unit "
              "of the calibrated range; sigma_seed = mean spread of an effect across seeds):", "",
              "| parameter | calibrated range | how the range was chosen |", "|---|---|---|"]
        L += [f"| {k} | {_f(v['lo'], 4) if isinstance(v['lo'], float) else v['lo']} .. "
              f"{_f(v['hi'], 4) if isinstance(v['hi'], float) else v['hi']} | {v['rule']} |" for k, v in mo["ranges"].items()]
        for c in morris:
            v = c["values"]
            name = c["text"].split("'")[1]
            L += ["", f"controller `{name}` ({c['id']}; {v['runs']} runs, {v['not_pass_runs']} not-PASS, "
                      f"{v['invalid_runs']} INVALID):", "",
                  "| rank | parameter | mu* | mu | sigma | sigma_seed |", "|---|---|---|---|---|---|"]
            L += [f"| {i} | {f} | {v['stats'][f]['mu_star']:.3f} | {v['stats'][f]['mu']:.3f} | "
                  f"{v['stats'][f]['sigma']:.3f} | {v['stats'][f]['sigma_seed']:.3f} |" for i, f in enumerate(v["ranking"], 1)]
    for c in claims:
        if c["text"].startswith("Failure modes"):
            v = c["values"]
            parts = ", ".join(f"`{k}` {n}" for k, n in v.items() if k != "runs")
            L += ["", f"Failure modes ({c['id']}), runs violating each criterion out of {v['runs']}: {parts}."]
        if c["text"].startswith("Validity"):
            v = c["values"]
            lanes = ", ".join(f"{k} x{n}" for k, n in v["collision_lanes"].items()) or "none"
            phases = ", ".join(f"{k} {n}" for k, n in v["invalid_by_phase"].items()) or "none"
            L += ["", f"Validity ({c['id']}): {v['invalid_runs']} of {v['runs']} runs INVALID "
                      f"({v['invalid_with_incident']} of them with an incident; by phase: {phases}); "
                      f"teleports {v['teleports']}, collisions {v['collisions']} (lanes: {lanes})."]
    L += ["", "Seeds column: one letter per seed in order, P = PASS, F = FAIL, I = INVALID."]
    return L


def PARAMS_ORDER(mo: dict) -> list[str]:
    return list(mo["ranges"])


def render_diagnosis(d: dict) -> list[str]:
    m = d["meta"]
    L = ["", f"**v1 INVALID 诊断 / diagnosis of the v1 INVALID runs** (`results/diagnosis/`, {m['runs']} runs, "
         f"wall {m['wall_time_s']} s): the v1 simulation re-run with SUMO warnings logged reproduces "
         f"{d['legacy_identical']} of {len(d['invalid_ids'])} INVALID runs exactly "
         f"({d['legacy_identical_all']} of {d['legacy_runs']} re-run v1 runs identical overall). "
         f"Cause of each collision = the victim's emergency stop just before it: "
         + ", ".join(f"`{k}` x{v}" for k, v in d["invalid_cause_counts"].items())
         + f". Re-run with the fixed simulation: {d['fixed_invalid']} of {len(d['invalid_ids'])} still INVALID.", "",
         "| v1 run | controller | incident start, duration (s) | collision lane | victim's emergency stop | at closure instant | fixed verdict |",
         "|---|---|---|---|---|---|---|"]
    for r in d["invalid_runs"]:
        for c in r["causes"]:
            L.append(f"| `{r['id']}` | {r['controller']} | {r['incident'][0]}, {r['incident'][1]} | {c['lane']} | "
                     f"{c['cause']} at {_f(c['victim_stop_time'])} s, decel {_f(c['victim_stop_decel'], 2)} m/s2 | "
                     f"{'yes' if c['stop_at_closure_instant'] else 'no'} | {r['fixed_verdict']} |")
    L += ["", f"Incident methods on the same {len(d['compare_ids'])} v1 incident scenarios (first {len(d['compare_ids'])} "
          "v1 runs with an incident; meter without amber except `default`):", "",
          "| config | method, amber (s) | runs with collision | collisions | teleports | emergency stops: no connection | emergency stops: red light | incident onset delay median / max (s) | mean delay avg (s) | wall (s) |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for name, s in d["comparison"].items():
        meth, amber = m["configs"][name]
        od = s["incident_onset_delay_s"]
        onset = "-" if od is None else f"{_f(od['median'])} / {_f(od['max'])}"
        L.append(f"| {name} | {meth}, {amber} | {s['runs_with_collision']}/{s['runs']} | {s['collisions']} | "
                 f"{s['teleports']} | {s['emergency_stops'].get('no_connection', 0)} | {s['emergency_stops'].get('red_light', 0)} | "
                 f"{onset} | {_f(s['mean_delay_s_avg'], 2)} | {m['wall_s_by_config'][name]} |")
    return L


def render_llm(s: dict) -> list[str]:
    t, m = s["totals"], s["meta"]
    L = ["", f"**LLM 策略对比 / LLM policy vs deterministic** (`results/llm/`; {m['model']} via Ollama on CPU "
         f"(num_gpu {m['ollama_options']['num_gpu']}); same budget for every campaign: {m['oat_runs']} OAT runs + "
         f"{m['probe_budget']} probe runs; wall {m['wall_time_s']} s, {m['sumo_runs_simulated']} new SUMO runs): "
         f"{t['calls']} LLM calls in {t['llm_campaigns']} campaigns, {t['valid']} valid / {t['invalid']} invalid "
         f"({', '.join(f'{k} {v}' for k, v in t['rejections'].items()) or 'none'}); the reply named the deterministic "
         f"choice in {t['agree_with_deterministic']} of {t['calls']} calls; {t['campaigns_same_actions']} of "
         f"{t['llm_campaigns']} campaigns took the same action sequence and {t['campaigns_same_boundaries']} of "
         f"{t['llm_campaigns']} found the same boundaries as the deterministic policy.", "",
         f"Deterministic: {' -> '.join(f'`{a}`' for a in t['deterministic_actions'])}, "
         f"{t['deterministic_runs_used']} runs, boundaries "
         + "; ".join(f"{k} {v[0]}..{v[1]}" + (" (cut by budget)" if k in t["deterministic_unconverged"] else "")
                     for k, v in t["deterministic_boundaries"].items()) + ".", "",
         "| campaign | temperature, seed | valid / calls | rejections | actions (after fallback) | runs used | boundaries missing / extra vs deterministic | differing boundaries (deterministic vs LLM campaign; * = cut by budget) |",
         "|---|---|---|---|---|---|---|---|"]
    camp = {c["name"]: c for c in s["campaigns"]}
    for p in s["per_campaign"]:
        c = camp[p["name"]]
        dmark = lambda k: "*" if k in t["deterministic_unconverged"] else ""  # noqa: E731
        lmark = lambda k: "*" if k in p["unconverged"] else ""  # noqa: E731
        diff = "; ".join(f"{k}: {v['deterministic']}{dmark(k)} vs {v['llm']}{lmark(k)}"
                         for k, v in p["boundary_differences"].items()) or "-"
        L.append(f"| {p['name']} | {c['temperature']}, {c['seed']} | {p['valid']}/{p['calls']} | "
                 f"{', '.join(f'{k} {v}' for k, v in p['rejections'].items()) or '-'} | "
                 f"{' -> '.join(a.replace('probe:', '') for a in p['actions'])} | {p['runs_used']} | "
                 f"{', '.join(p['boundaries_missing_vs_deterministic']) or '-'} / "
                 f"{', '.join(p['boundaries_extra_vs_deterministic']) or '-'} | {diff} |")
    return L


def render_linux(x: dict) -> list[str]:
    rr = [ln for ln in x["rerun_check_lines"] if ln.endswith("identical") and "/" in ln.split()[0]]
    return ["", f"**Linux 复现 / Linux check** (`results/linux_check.json`, {x['platform']}, Python {x['python']}, "
            f"pip `eclipse-sumo` {x['sumo_version']}, fresh clone of commit `{x['commit']}`, {x['date']}): tests "
            f"`{x['pytest']}`; `build_network.py --check`: {x['network_check']}; `rerun_check.py --n 6` "
            f"(re-simulating committed Windows runs on Linux, KPIs + tripinfo hash): "
            f"{rr[0] if rr else x['rerun_check_lines'][-1]}."]


def render(root: Path) -> str:
    rep = json.loads((root / "results" / "report.json").read_text(encoding="utf-8"))
    L = [BEGIN, "<!-- generated by scripts/render_readme.py from results/*.json; do not edit by hand -->", ""]
    L += render_main(rep)
    for rel, fn in (("diagnosis/summary.json", render_diagnosis), ("llm/summary.json", render_llm),
                    ("linux_check.json", render_linux)):
        p = root / "results" / rel
        if p.exists():
            L += fn(json.loads(p.read_text(encoding="utf-8")))
    L += ["", END]
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--readme", default=str(ROOT / "README.md"))
    ap.add_argument("--root", default=str(ROOT))
    a = ap.parse_args()
    block = render(Path(a.root))
    readme = Path(a.readme).read_text(encoding="utf-8")
    i, j = readme.find(BEGIN), readme.find(END)
    if i < 0 or j < 0:
        print("README has no results markers")
        return 1
    current = readme[i:j + len(END)]
    if a.check:
        if current != block:
            print("README results block differs from results/*.json; run scripts/render_readme.py")
            return 1
        print("README results block matches results/*.json")
        return 0
    Path(a.readme).write_text(readme[:i] + block + readme[j + len(END):], encoding="utf-8", newline="\n")
    print("README results block updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
