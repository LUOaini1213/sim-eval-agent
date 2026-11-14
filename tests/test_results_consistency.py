"""The committed results are internally consistent and the README table matches them."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from simeval.report import verify

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
pytestmark = pytest.mark.skipif(not (RESULTS / "report.json").exists(), reason="no committed results")


def test_committed_results_verify():
    assert verify(RESULTS) == []


def test_verify_catches_a_tampered_claim(tmp_path):
    d = tmp_path / "r"
    shutil.copytree(RESULTS, d)
    rep = json.loads((d / "report.json").read_text(encoding="utf-8"))
    c = next(c for c in rep["claims"] if "mean_delay_s" in c["values"])
    c["values"]["mean_delay_s"] = round(c["values"]["mean_delay_s"] - 5.0, 2)
    (d / "report.json").write_text(json.dumps(rep), encoding="utf-8")
    assert any("claims" in p for p in verify(d))


def test_verify_catches_a_tampered_kpi(tmp_path):
    d = tmp_path / "r"
    shutil.copytree(RESULTS, d)
    lines = (d / "runs.jsonl").read_text(encoding="utf-8").splitlines()
    r = json.loads(lines[0])
    r["kpis"]["mean_delay_s"] = 999.0
    lines[0] = json.dumps(r)
    (d / "runs.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert verify(d)


def test_readme_matches_results():
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "render_readme.py"), "--check"],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr


def test_readme_check_fails_on_drift(tmp_path):
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    start = readme.index("<!-- RESULTS:BEGIN -->")
    tampered = readme[:start] + readme[start:].replace("|", "| ", 1)
    p = tmp_path / "README.md"
    p.write_text(tampered, encoding="utf-8")
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "render_readme.py"), "--check", "--readme", str(p)],
                         capture_output=True, text=True)
    assert out.returncode == 1


def test_readme_check_fails_on_tldr_drift(tmp_path):
    """The TL;DR under the title is generated too: a hand-edited number there fails --check."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    i, j = readme.index("<!-- TLDR:BEGIN -->"), readme.index("<!-- TLDR:END -->")
    runs = str(json.loads((RESULTS / "report.json").read_text(encoding="utf-8"))["runs_executed"])
    assert f"{runs} SUMO runs" in readme[i:j]
    p = tmp_path / "README.md"
    p.write_text(readme[:i] + readme[i:j].replace(f"{runs} SUMO runs", f"{int(runs) + 1} SUMO runs") + readme[j:],
                 encoding="utf-8")
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "render_readme.py"), "--check", "--readme", str(p)],
                         capture_output=True, text=True)
    assert out.returncode == 1 and "TL;DR" in out.stdout


def test_diagnosis_sentence_names_the_platform_when_recorded():
    sys.path.insert(0, str(ROOT / "scripts"))
    import render_readme

    d = json.loads((RESULTS / "diagnosis" / "summary.json").read_text(encoding="utf-8"))
    without = " ".join(render_readme.render_diagnosis(d, "Windows-10"))
    assert "platform of this re-run not recorded" in without and "made on Windows-10" in without
    d["meta"].update(platform="Linux-6.8", git_commit="0123456789abcdef", git_dirty=False)
    with_ = " ".join(render_readme.render_diagnosis(d, "Windows-10"))
    assert "re-run on Linux-6.8, code commit `0123456`" in with_


@pytest.mark.skipif(not (RESULTS / "diagnosis" / "summary.json").exists(), reason="no diagnosis results")
def test_experiment_summaries_verify_and_tampering_is_caught(tmp_path):
    from simeval.report import verify_experiments

    assert verify_experiments(RESULTS) == []
    d = tmp_path / "r"
    shutil.copytree(RESULTS, d)
    s = json.loads((d / "diagnosis" / "summary.json").read_text(encoding="utf-8"))
    s["comparison"]["legacy"]["collisions"] -= 1
    (d / "diagnosis" / "summary.json").write_text(json.dumps(s), encoding="utf-8")
    assert any("diagnosis" in p for p in verify_experiments(d))
    if (d / "llm" / "summary.json").exists():
        s = json.loads((d / "llm" / "summary.json").read_text(encoding="utf-8"))
        s["totals"]["valid"] += 1
        (d / "llm" / "summary.json").write_text(json.dumps(s), encoding="utf-8")
        assert any("llm" in p for p in verify_experiments(d))
