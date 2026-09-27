"""Run the simulation-evaluation agent against SUMO and write results/.

    python scripts/run_agent.py                 # the full run behind the README numbers
    python scripts/run_agent.py --smoke --out smoke_results   # tiny CI run
"""
import argparse
import datetime as dt
import os
import platform
import sys
import time

import _path  # noqa: F401
from simeval.agent import Agent, AgentConfig
from simeval.evaluator import SumoEvaluator
from simeval.network import sha256
from simeval.policy import DeterministicPolicy, LLMPolicy, ollama_chat
from simeval.report import write_all
from simeval.runner import DEFAULT_OPTIONS, SimOptions
from simeval.sumo_env import sumo_version

ROOT = _path.ROOT


def phase_walls(batches: list[dict]) -> dict:
    out: dict[str, float] = {}
    for b in batches:
        k = b["phase"].split(":")[0]
        out[k] = round(out.get(k, 0.0) + b.get("wall_s", 0.0), 1)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results")
    ap.add_argument("--work", default="work", help="scratch dir for raw SUMO outputs")
    ap.add_argument("--jobs", type=int, default=7)
    ap.add_argument("--budget", type=int, default=AgentConfig.budget)
    ap.add_argument("--screen-n", type=int, default=AgentConfig.screen_n)
    ap.add_argument("--keep-raw", action="store_true")
    ap.add_argument("--smoke", action="store_true", help="tiny configuration for CI")
    ap.add_argument("--policy", choices=["deterministic", "llm"], default="deterministic")
    ap.add_argument("--llm-model", default="qwen2.5:3b", help="Ollama model (CPU only: num_gpu=0)")
    ap.add_argument("--incident-method", default=DEFAULT_OPTIONS.incident_method)
    a = ap.parse_args()

    if a.smoke:
        cfg = AgentConfig(budget=60, seeds=(1,), controllers=("fixed",), reference_controller=None,
                          screen_n=0, max_probes=1, refine_seeds=(1, 2), refine_points=3, refine_extend=0,
                          morris_r=1, morris_seeds=(1,))
    else:
        cfg = AgentConfig(budget=a.budget, screen_n=a.screen_n)
    policy = DeterministicPolicy() if a.policy == "deterministic" else LLMPolicy(ollama_chat(a.llm_model))
    opts = SimOptions(incident_method=a.incident_method, log_warnings=True)
    net = ROOT / "network" / "merge.net.xml"
    ev = SumoEvaluator(net, ROOT / a.work, jobs=a.jobs, keep_raw=a.keep_raw, options=opts.as_dict())
    t0 = time.perf_counter()
    try:
        result = Agent(ev, cfg, policy=policy).run()
    finally:
        ev.close()
    wall = round(time.perf_counter() - t0, 1)
    meta = {
        "sumo_version": sumo_version(),
        "net_sha256": sha256(net),
        "date": dt.date.today().isoformat(),
        "wall_time_s": wall,
        "phase_walls_s": phase_walls(result["batches"]),
        "jobs": a.jobs,
        "python": platform.python_version(),
        "platform": platform.platform(terse=True),
        "cpu_count": os.cpu_count(),
        "sim_wall_s_sum": round(sum(r["wall_s"] for r in result["runs"]), 1),
        "sim_options": opts.as_dict(),
    }
    if a.policy == "llm":
        meta["llm_model"] = a.llm_model
        meta["llm_log"] = policy.log
    rep = write_all(result, meta, ROOT / a.out)
    print(f"{rep['runs_executed']} runs in {wall} s; stop: {rep['stop_reason']}")
    for b in rep["boundaries"]:
        print(f"  {b['controller']:7} {b['param']:18} pass@{b['last_pass']}  fail@{b['first_fail']}  "
              f"monotone={b['monotonicity']['monotone']}")
    for r in rep.get("refined", []):
        print(f"  refined {r['controller']:7} {r['param']:18} band={r['band']} x50={r['x50']}")
    print(f"verdicts: {rep['verdict_counts']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
