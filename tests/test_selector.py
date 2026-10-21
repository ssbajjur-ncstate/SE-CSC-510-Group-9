import pytest

from testbudget.rules import RuleContext
from testbudget.selector import select_with_budget, select_with_rules


def _test(name, duration, **extra):
    return {"test_name": name, "duration": duration, "score": 1.0, **extra}


def test_tests_that_fit_are_selected_in_ranked_order():
    plan = select_with_budget([_test("a", 1), _test("b", 5), _test("c", 1)], 2)
    assert [t["test_name"] for t in plan["selected"]] == ["a", "c"]
    assert plan["skipped"][0]["skip_reason"] == "budget exhausted"


def test_forced_test_survives_a_budget_smaller_than_its_duration():
    plan = select_with_budget([_test("a", 1), _test("big", 10, forced=True)], 2)
    assert [t["test_name"] for t in plan["selected"]] == ["big"]
    assert plan["estimated_runtime"] == 10


def test_negative_budget_is_rejected():
    with pytest.raises(ValueError):
        select_with_budget([_test("a", 1)], -1)


def test_pinned_test_survives_a_small_budget_through_the_rules():
    ranked = [_test("a", 1), _test("pinned", 5)]
    context = RuleContext(config={"pins": ["pinned"]})
    plan = select_with_rules(ranked, 1, context)
    names = [t["test_name"] for t in plan["selected"]]
    assert names[0] == "pinned"
    assert plan["run_all"] is False


def test_rotation_limit_forces_a_test_with_skip_debt():
    runs = [
        {"sha": f"s{i}", "timestamp": f"2026-10-0{i}", "branch": "main"}
        for i in range(1, 4)
    ]
    results = [{"sha": "s1", "test_id": "old", "status": "passed"}]
    ranked = [_test("old", 5), _test("new", 1)]
    context = RuleContext(config={"rotation_limit": 2}, runs=runs, results=results)
    plan = select_with_rules(ranked, 0, context)
    assert [t["test_name"] for t in plan["selected"]] == ["old"]


def test_full_suite_trigger_selects_everything_past_the_budget():
    ranked = [_test("a", 5), _test("b", 5)]
    context = RuleContext(changed_files=["poetry.lock"])
    plan = select_with_rules(ranked, 1, context)
    assert len(plan["selected"]) == 2
    assert plan["trigger"] == "lockfile changed: poetry.lock"


def test_bad_rule_config_is_rejected():
    with pytest.raises(ValueError):
        select_with_rules([_test("a", 1)], 1, RuleContext(config={"pins": 3}))
