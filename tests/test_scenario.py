"""Scenario generation is deterministic and the seed reaches SUMO."""
import pytest

from simeval.agent import Agent, AgentConfig
from simeval.evaluator import FunctionEvaluator
from simeval.runner import sumo_cmd
from simeval.scenario import NOMINAL, Scenario, routes_xml, write_inputs

# Golden id of the nominal scenario. If this changes, every committed run id changes too.
NOMINAL_ID = "5da8cb55bbb9"


def test_nominal_id_is_stable():
    assert NOMINAL.id == NOMINAL_ID


def test_id_ignores_float_noise_but_not_real_changes():
    assert NOMINAL.with_(sigma=0.5000000001).id == NOMINAL.id
    # the constructor path does not go through with_(), so canonical() must do the rounding
    assert Scenario(sigma=0.5000000001, truck_share=0.1 + 1e-12).id == NOMINAL.id
    assert NOMINAL.with_(sigma=0.51).id != NOMINAL.id
    assert NOMINAL.with_(seed=2).id != NOMINAL.id


def test_route_file_is_byte_identical_across_calls_and_dirs(tmp_path):
    a, _ = write_inputs(NOMINAL, tmp_path / "a")
    b, _ = write_inputs(Scenario(), tmp_path / "b")
    assert a.read_bytes() == b.read_bytes()
    assert routes_xml(NOMINAL.with_(main_demand=3300)) != routes_xml(NOMINAL)


def test_seed_is_passed_to_sumo():
    cmd = sumo_cmd(NOMINAL.with_(seed=7))
    i = cmd.index("--seed")
    assert cmd[i + 1] == "7"
    assert sumo_cmd(NOMINAL.with_(seed=8))[i + 1] == "8"


def test_out_of_range_rejected():
    with pytest.raises(ValueError):
        NOMINAL.with_(main_demand=5000)
    with pytest.raises(ValueError):
        NOMINAL.with_(controller="magic")


def test_screening_sample_deterministic_and_seed_dependent():
    ev = FunctionEvaluator(lambda s: {})
    a = Agent(ev, AgentConfig(agent_seed=1)).screening_sample()
    b = Agent(ev, AgentConfig(agent_seed=1)).screening_sample()
    c = Agent(ev, AgentConfig(agent_seed=2)).screening_sample()
    assert a == b and a != c
    # Latin hypercube: each parameter hits each of the n strata exactly once
    n = len(a)
    vals = sorted(p["sigma"] for p in a)
    assert all(0.9 * k / n <= v <= 0.9 * (k + 1) / n for k, v in enumerate(vals))
