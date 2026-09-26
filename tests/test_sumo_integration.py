"""Needs SUMO (skipped otherwise). Network reproducibility and run determinism."""
from pathlib import Path

import pytest

from simeval import sumo_env
from simeval.evaluator import _run_one
from simeval.network import build_network

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(not sumo_env.available(), reason="SUMO not installed")


def test_network_is_byte_reproducible(tmp_path):
    a = build_network(tmp_path / "a").read_bytes()
    b = build_network(tmp_path / "b").read_bytes()
    assert a == b
    assert b"generated on" not in a
    if sumo_env.sumo_version() == "1.24.0":  # the committed file was built with 1.24.0
        assert a == (ROOT / "network" / "merge.net.xml").read_bytes()


def test_same_seed_same_result_different_seed_different_result(tmp_path):
    from simeval.scenario import NOMINAL

    net = str(ROOT / "network" / "merge.net.xml")
    s1 = NOMINAL.with_(controller="alinea", seed=11)
    r1 = _run_one((s1.canonical(), net, str(tmp_path / "x"), False))
    r2 = _run_one((s1.canonical(), net, str(tmp_path / "y"), False))
    r3 = _run_one((NOMINAL.with_(controller="alinea", seed=12).canonical(), net, str(tmp_path / "z"), False))
    assert r1["kpis"] == r2["kpis"] and r1["tripinfo_sha256"] == r2["tripinfo_sha256"]
    assert r1["tripinfo_sha256"] != r3["tripinfo_sha256"]
    assert r1["kpis"]["vehicles"] > 1000 and r1["kpis"]["teleports"] == 0
