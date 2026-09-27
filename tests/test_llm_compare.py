"""Campaign comparison arithmetic on hand-made campaigns."""
from simeval.llm_compare import summarize_campaigns


def camp(name, policy, actions, boundaries):
    return {"name": name, "policy": policy, "runs_used": 200, "actions": [{"action": a} for a in actions],
            "boundaries": [{"controller": c, "param": p, "last_pass": lp, "first_fail": ff, "converged": ff - lp <= 2}
                           for c, p, lp, ff in boundaries]}


def log(campaign, step, parsed, det, accepted, rejection=None):
    return {"campaign": campaign, "step": step, "parsed": parsed, "deterministic_choice": det, "accepted": accepted,
            "rejection": rejection, "used": parsed if accepted else det, "latency_s": 2.0}


def test_counts_agreement_and_boundary_differences():
    det = camp("det", "deterministic", ["probe:a:hi", "probe:b:hi"], [("x", "a", 1, 2), ("x", "b", 5, 6)])
    same = camp("l1", "llm", ["probe:a:hi", "probe:b:hi"], [("x", "a", 1, 2), ("x", "b", 5, 6)])
    other = camp("l2", "llm", ["probe:c:lo", "probe:a:hi"], [("x", "c", 9, 8), ("x", "a", 1, 3)])
    logs = [log("l1", 0, "probe:a:hi", "probe:a:hi", True), log("l1", 1, "probe:b:hi", "probe:b:hi", True),
            log("l2", 0, "probe:c:lo", "probe:a:hi", True),
            log("l2", 1, None, "probe:a:hi", False, "no_json"),
            log("l2", 2, "probe:z:hi", "probe:b:hi", False, "not_allowed_now")]
    s = summarize_campaigns([det, same, other], logs)
    t = s["totals"]
    assert (t["calls"], t["valid"], t["invalid"]) == (5, 3, 2)
    assert t["rejections"] == {"no_json": 1, "not_allowed_now": 1}
    assert t["agree_with_deterministic"] == 2          # an invalid reply never counts as agreement
    assert (t["campaigns_same_actions"], t["campaigns_same_boundaries"]) == (1, 1)
    p2 = s["per_campaign"][1]
    assert p2["boundaries_missing_vs_deterministic"] == ["x/b"]
    assert p2["boundaries_extra_vs_deterministic"] == ["x/c"]
    assert p2["boundary_differences"] == {"x/a": {"deterministic": [1, 2], "llm": [1, 3]}}
    assert p2["unconverged"] == [] and t["deterministic_unconverged"] == []
