from simeval.policy import VOCABULARY, DeterministicPolicy, LLMPolicy, candidates, parse_action


def row(param, lo_delta, hi_delta, flips):
    return {"param": param, "nominal_fails": False, "flip_levels": flips,
            "influence": max(abs(lo_delta), abs(hi_delta)),
            "levels": {"lo": {"value": 0, "mean_delta_margin": lo_delta, "majority_fails": "lo" in flips},
                       "hi": {"value": 1, "mean_delta_margin": hi_delta, "majority_fails": "hi" in flips}}}


OAT = {"alinea": [
    row("main_demand", 0.2, -0.9, ["hi"]),
    row("sigma", -0.95, 0.1, []),                  # largest effect, but no verdict flip
    row("incident_duration", 0.0, -0.5, ["hi"]),
    row("ramp_demand", -0.6, -0.3, ["lo", "hi"]),  # both directions flip
]}


def test_vocabulary_is_closed_and_directional():
    assert "stop" in VOCABULARY and all(v == "stop" or v.count(":") == 2 for v in VOCABULARY)
    assert "probe:main_demand:hi" in VOCABULARY and "probe:main_demand" not in VOCABULARY
    assert parse_action('{"action": "probe:main_demand:hi"}') == ("probe:main_demand:hi", None)
    assert parse_action('{"action": "traci.vehicle.remove(x)"}') == (None, "not_in_vocabulary")
    assert parse_action("no json here") == (None, "no_json")
    assert parse_action('{"action": probe}') == (None, "bad_json")


def test_candidates_rank_directions_by_their_own_effect():
    assert candidates(OAT, set()) == ["probe:main_demand:hi", "probe:ramp_demand:lo",
                                      "probe:incident_duration:hi", "probe:ramp_demand:hi"]


def test_deterministic_policy_skips_flipless_and_probed():
    p = DeterministicPolicy()
    assert p.choose(OAT, set())[0] == "probe:main_demand:hi"      # sigma has no flip
    assert p.choose(OAT, {"probe:main_demand:hi"})[0] == "probe:ramp_demand:lo"
    assert p.choose(OAT, set(candidates(OAT, set())))[0] == "stop"


def test_llm_policy_rejects_and_logs_every_exchange():
    replies = iter(['{"action": "run_sumo --end 99"}', '{"action": "probe:sigma:lo"}', "sure!",
                    '{"action": "probe:incident_duration:hi"}', '{"action": "stop"}'])
    p = LLMPolicy(lambda prompt: next(replies))
    got = [p.choose(OAT, set())[0] for _ in range(5)]
    assert got == ["probe:main_demand:hi"] * 3 + ["probe:incident_duration:hi", "stop"]
    assert [e["accepted"] for e in p.log] == [False, False, False, True, True]
    assert [e["rejection"] for e in p.log] == ["not_in_vocabulary", "not_allowed_now", "no_json", None, None]
    assert all(e["prompt"] and "response" in e for e in p.log)
    assert all(e["deterministic_choice"] == "probe:main_demand:hi" for e in p.log)


def test_llm_failure_falls_back():
    def boom(prompt):
        raise TimeoutError("model too slow")

    p = LLMPolicy(boom)
    assert p.choose(OAT, set())[0] == "probe:main_demand:hi"
    assert p.log[0]["accepted"] is False and "TimeoutError" in p.log[0]["error"]
