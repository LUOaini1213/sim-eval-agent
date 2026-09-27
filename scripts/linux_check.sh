#!/usr/bin/env bash
# Linux reproducibility check (run inside WSL / any Linux box):
#   bash scripts/linux_check.sh /path/to/sim-eval-agent  OUT.json
# Clones the committed HEAD into a scratch dir, installs SUMO 1.24.0 from pip into a venv
# (reused if present), runs the test suite, the byte-level network check and a sample
# re-simulation of committed runs, and writes a JSON summary to OUT.json.
set -u
REPO=$(cd "$1" && pwd)
OUT=$2
VENV=${VENV:-$HOME/sim-eval-venv}
WORK=${WORK:-$HOME/sim-eval-check}
COMMIT=$(git -c safe.directory='*' -C "$REPO" rev-parse --short HEAD)
rm -rf "$WORK"
git -c safe.directory='*' clone -q "$REPO" "$WORK"
cd "$WORK"
[ -x "$VENV/bin/python" ] || python3 -m venv "$VENV"
"$VENV/bin/pip" install -q -r requirements.txt
export SUMO_HOME=$("$VENV/bin/python" -c 'import sumo; print(sumo.SUMO_HOME)')
PY="$VENV/bin/python"
T0=$(date +%s)
PYTEST=$("$PY" -m pytest -q 2>&1 | tail -n 1)
T1=$(date +%s)
NET=$("$PY" scripts/build_network.py --check 2>&1 | tail -n 1); NET_RC=$?
RERUN=$("$PY" scripts/rerun_check.py --n 6 2>&1)
T2=$(date +%s)
export COMMIT PYTEST NET NET_RC RERUN T0 T1 T2
"$PY" - "$OUT" <<'EOF'
import json, os, platform, sys
from simeval.sumo_env import sumo_version
rerun = os.environ["RERUN"].strip().splitlines()
out = {
    "commit": os.environ["COMMIT"],
    "platform": f"{platform.system()} {platform.release()} ({platform.machine()})",
    "python": platform.python_version(),
    "sumo_version": sumo_version(),
    "pytest": os.environ["PYTEST"],
    "network_check_output": os.environ["NET"],
    "network_check": "byte-identical to the committed network/merge.net.xml" if os.environ["NET_RC"] == "0"
                     else "DIFFERENT from the committed network/merge.net.xml",
    "rerun_check_lines": rerun,
    "wall_s": {"pytest": int(os.environ["T1"]) - int(os.environ["T0"]), "network+rerun": int(os.environ["T2"]) - int(os.environ["T1"])},
}
json.dump(out, open(sys.argv[1], "w"), indent=1, sort_keys=True)
print(json.dumps(out, indent=1))
EOF
