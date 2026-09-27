"""Run the probe phase with the LLM policy (qwen2.5:3b via Ollama, CPU only) and with the
deterministic policy under the same budget, and compare choices and boundaries.

    python scripts/compare_llm.py              # writes results/llm/

Both policies see the same one-at-a-time table (replayed from results/runs.jsonl) and get the
same run budget: the OAT runs plus ``--probe-budget`` runs for bisection. Runs already on
record are replayed; only scenarios nobody has simulated yet go to SUMO. Refinement and Morris
are off, so the only thing that differs between campaigns is which probe:<param>:<lo|hi> the
policy picks, in which order, and when it stops. Every prompt and reply is logged.
"""
import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

import _path  # noqa: F401
from simeval.agent import Agent, AgentConfig
from simeval.evaluator import ReplayEvaluator, SumoEvaluator
from simeval.llm_compare import summarize_campaigns
from simeval.policy import DeterministicPolicy, LLMPolicy, ollama_chat
from simeval.report import load_runs
from simeval.runner import SimOptions

ROOT = _path.ROOT
# (name, temperature, seed): one greedy campaign and four sampled ones for stability
LLM_RUNS = [("llm_t0", 0.0, 0), ("llm_t07_s1", 0.7, 1), ("llm_t07_s2", 0.7, 2), ("llm_t07_s3", 0.7, 3),
            ("llm_t07_s4", 0.7, 4)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "results" / "llm"))
    ap.add_argument("--model", default="qwen2.5:3b")
    ap.add_argument("--probe-budget", type=int, default=100)
    ap.add_argument("--max-probes", type=int, default=6)
    ap.add_argument("--jobs", type=int, default=7)
    a = ap.parse_args()
    base = load_runs(ROOT / "results" / "runs.jsonl")
    main_cfg = json.loads((ROOT / "results" / "report.json").read_text(encoding="utf-8"))["config"]
    oat_runs = sum(1 for r in base if r["phase"] == "oat")
    budget = oat_runs + a.probe_budget
    opts = SimOptions(log_warnings=True).as_dict()
    sumo = SumoEvaluator(ROOT / "network" / "merge.net.xml", ROOT / "work" / "llm", jobs=a.jobs, options=opts)
    known = list(base)
    campaigns, logs = [], []
    t_all = time.perf_counter()
    try:
        plan = [("deterministic", None, None)] + LLM_RUNS
        for name, temp, seed in plan:
            cfg = AgentConfig(budget=budget, seeds=tuple(main_cfg["seeds"]), controllers=tuple(main_cfg["controllers"]),
                              reference_controller=main_cfg["reference_controller"], max_probes=a.max_probes,
                              refine_seeds=(), morris_r=0)
            policy = DeterministicPolicy() if temp is None else LLMPolicy(ollama_chat(a.model, temperature=temp, seed=seed))
            ev = ReplayEvaluator(known, sumo)
            t0 = time.perf_counter()
            res = Agent(ev, cfg, policy=policy).run()
            wall = round(time.perf_counter() - t0, 1)
            known += ev.new_records
            campaigns.append({"name": name, "policy": policy.name, "temperature": temp, "seed": seed,
                              "budget": budget, "runs_used": res["runs_executed"], "simulated": ev.simulated,
                              "wall_s": wall, "stop_reason": res["stop_reason"], "actions": res["actions"],
                              "boundaries": [{k: b[k] for k in ("controller", "param", "last_pass", "first_fail",
                                                                "converged", "steps")} for b in res["boundaries"]]})
            for i, e in enumerate(getattr(policy, "log", [])):
                logs.append({"campaign": name, "step": i, **e})
            print(f"{name:14} {[x['action'] for x in res['actions']]} runs={res['runs_executed']} "
                  f"simulated={ev.simulated} wall={wall}s")
    finally:
        sumo.close()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    extra = [r for r in known[len(base):]]
    with open(out / "runs_extra.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for r in extra:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    with open(out / "llm_log.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for e in logs:
            f.write(json.dumps(e, sort_keys=True, ensure_ascii=False) + "\n")
    summary = summarize_campaigns(campaigns, logs)
    summary["meta"] = {"model": a.model, "ollama_options": {"num_gpu": 0}, "date": dt.date.today().isoformat(),
                       "budget": budget, "oat_runs": oat_runs, "probe_budget": a.probe_budget,
                       "max_probes": a.max_probes, "wall_time_s": round(time.perf_counter() - t_all, 1),
                       "sumo_runs_simulated": len(extra)}
    (out / "summary.json").write_text(json.dumps({"campaigns": campaigns, **summary}, indent=1, sort_keys=True) + "\n",
                                      encoding="utf-8", newline="\n")
    print(json.dumps(summary["totals"], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
