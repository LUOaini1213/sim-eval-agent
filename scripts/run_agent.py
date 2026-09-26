"""Run the simulation-evaluation agent against SUMO and write results/.

    python scripts/run_agent.py                 # the full run behind the README numbers
    python scripts/run_agent.py --smoke --out smoke_results   # tiny CI run
"""
import argparse
import datetime as dt
import platform
import sys
import time

import _path  # noqa: F401
from simeval.agent import Agent, AgentConfig
from simeval.evaluator import SumoEvaluator
from simeval.network import sha256
from simeval.policy import DeterministicPolicy, LLMPolicy, anthropic_chat
from simeval.report import write_all
from simeval.sumo_env import sumo_version

ROOT = _path.ROOT


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results")
    ap.add_argument("--work", default="work", help="scratch dir for raw SUMO outputs")
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--budget", type=int, default=240)
    ap.add_argument("--screen-n", type=int, default=16)
    ap.add_argument("--keep-raw", action="store_true")
    ap.add_argument("--smoke", action="store_true", help="tiny configuration for CI")
    ap.add_argument("--policy", choices=["deterministic", "llm"], default="deterministic")
    ap.add_argument("--llm-model", default="claude-opus-5")
    a = ap.parse_args()

    if a.smoke:
        cfg = AgentConfig(budget=40, seeds=(1,), controllers=("fixed",), reference_controller=None,
                          screen_n=2, max_probes=1)
    else:
        cfg = AgentConfig(budget=a.budget, screen_n=a.screen_n)
    policy = DeterministicPolicy() if a.policy == "deterministic" else LLMPolicy(anthropic_chat(a.llm_model))
    net = ROOT / "network" / "merge.net.xml"
    ev = SumoEvaluator(net, ROOT / a.work, jobs=a.jobs, keep_raw=a.keep_raw)
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
        "jobs": a.jobs,
        "python": platform.python_version(),
        "platform": platform.platform(terse=True),
        "cpu_count": __import__("os").cpu_count(),
        "sim_wall_s_sum": round(sum(r["wall_s"] for r in result["runs"]), 1),
    }
    if a.policy == "llm":
        meta["llm_model"] = a.llm_model
        meta["llm_log"] = policy.log
    rep = write_all(result, meta, ROOT / a.out)
    print(f"{rep['runs_executed']} runs in {wall} s; stop: {rep['stop_reason']}")
    for b in rep["boundaries"]:
        print(f"  {b['controller']:7} {b['param']:18} pass@{b['last_pass']}  fail@{b['first_fail']}  "
              f"monotone={b['monotonicity']['monotone']}")
    print(f"verdicts: {rep['verdict_counts']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
