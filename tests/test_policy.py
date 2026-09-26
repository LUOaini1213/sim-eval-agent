from simeval.policy import VOCABULARY, DeterministicPolicy, LLMPolicy, parse_action

OAT = {"alinea": [
    {"param": "main_demand", "influence": 0.9, "flip_levels": ["hi"]},
    {"param": "sigma", "influence": 0.95, "flip_levels": []},
    {"param": "incident_duration", "influence": 0.5, "flip_levels": ["hi"]},
]}


def test_vocabulary_is_closed():
    assert "stop" in VOCABULARY and all(v == "stop" or v.startswith("probe:") for v in VOCABULARY)
    assert parse_action('{"action": "probe:main_demand"}') == "probe:main_demand"
    assert parse_action('{"action": "traci.vehicle.remove(x)"}') is None
    assert parse_action("no json here") is None


def test_deterministic_policy_skips_flipless_and_probed():
    p = DeterministicPolicy()
    assert p.choose(OAT, set())[0] == "probe:main_demand"      # sigma has no flip
    assert p.choose(OAT, {"main_demand"})[0] == "probe:incident_duration"
    assert p.choose(OAT, {"main_demand", "incident_duration"})[0] == "stop"


def test_llm_policy_rejects_out_of_vocabulary_and_invalid_choices():
    replies = iter(['{"action": "run_sumo --end 99"}', '{"action": "probe:sigma"}', '{"action": "probe:incident_duration"}'])
    p = LLMPolicy(lambda prompt: next(replies))
    a1, _ = p.choose(OAT, set())
    a2, _ = p.choose(OAT, set())
    a3, _ = p.choose(OAT, set())
    assert (a1, a2, a3) == ("probe:main_demand", "probe:main_demand", "probe:incident_duration")
    assert [e["accepted"] for e in p.log] == [False, False, True]
