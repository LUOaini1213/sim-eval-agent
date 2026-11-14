"""The helper scripts' guards: command lines build without SUMO, and linux_check.sh sees exit codes."""
import shutil
import subprocess
from pathlib import Path

import pytest

from simeval import sumo_env
from simeval.runner import sumo_cmd
from simeval.scenario import NOMINAL

ROOT = Path(__file__).resolve().parents[1]


def test_sumo_cmd_builds_without_sumo_installed(monkeypatch):
    def missing(name):
        raise FileNotFoundError(name)

    monkeypatch.setattr(sumo_env, "binary", missing)
    cmd = sumo_cmd(NOMINAL)
    assert cmd[0] == "sumo"
    assert cmd[cmd.index("--seed") + 1] == str(NOMINAL.seed)


def _bash():
    """A real bash; on Windows never the System32 WSL launcher (CreateProcess would pick it first)."""
    b = shutil.which("bash")
    return None if b is None or "system32" in b.lower() else b


@pytest.mark.skipif(_bash() is None, reason="no bash")
def test_linux_check_set_line_propagates_a_failing_command_through_tail():
    """linux_check.sh records NET_RC=$? after `build_network.py --check | tail -n 1`; without
    pipefail that is tail's status (always 0) and a changed network is labelled byte-identical."""
    lines = (ROOT / "scripts" / "linux_check.sh").read_text(encoding="utf-8").splitlines()
    set_line = next(ln for ln in lines if ln.startswith("set "))
    assert any("| tail -n 1); NET_RC=$?" in ln for ln in lines)
    probe = set_line + '\nX=$({ echo DIFFERENT; false; } 2>&1 | tail -n 1); echo "rc=$? out=$X"\n'
    out = subprocess.run([_bash(), "-s"], input=probe, capture_output=True, text=True, timeout=60)
    assert out.stdout.strip() == "rc=1 out=DIFFERENT", out.stdout + out.stderr


def test_rerun_check_fails_when_no_runs_are_selected(tmp_path):
    """CI gates on rerun_check.py's exit code; an empty selection must not pass as "0/0 identical"."""
    import sys

    shutil.copy(ROOT / "results" / "report.json", tmp_path / "report.json")
    (tmp_path / "runs.jsonl").write_text("", encoding="utf-8")
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "rerun_check.py"), "--n", "3", "--dir", str(tmp_path)],
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 1 and "no runs selected" in out.stdout, out.stdout + out.stderr


def test_v1_invalid_selection_is_the_diagnosed_set():
    """--v1-invalid re-simulates exactly the v1 INVALID runs that results/diagnosis/ attributes."""
    import json
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    import rerun_check

    diag = json.loads((ROOT / "results" / "diagnosis" / "summary.json").read_text(encoding="utf-8"))
    assert sorted(r["id"] for r in rerun_check.v1_invalid_runs()) == sorted(diag["invalid_ids"])
    assert len(diag["invalid_ids"]) > 0
