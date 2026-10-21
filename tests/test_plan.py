import json

import pytest

from testbudget.db import load_history_records
from testbudget.plan import build_plan, plan_risk_level, write_plan
from testbudget.rules import RuleContext
from testbudget.selector import select_with_rules

CONTRACT_KEYS = {
    "sha",
    "risk_level",
    "budget_s",
    "selected",
    "skipped",
    "catch_rate_estimate",
}


def _ranked():
    return [
        {"test_name": "a", "duration": 1.0, "failure_count": 2, "reason": "x"},
        {"test_name": "b", "duration": 5.0, "failure_count": 1, "reason": "y"},
        {"test_name": "pin", "duration": 3.0, "failure_count": 0, "reason": "z"},
    ]


def _plan(budget=1.0):
    selection = select_with_rules(
        _ranked(), budget, RuleContext(config={"pins": ["pin"]})
    )
    return build_plan("abc", selection, "low", budget)


def test_plan_has_every_contract_key():
    plan = _plan()
    assert set(plan) == CONTRACT_KEYS
    assert set(plan["selected"][0]) == {"test_id", "reason", "duration_s"}


def test_skipped_tests_carry_skip_reason_and_skip_debt():
    skipped = _plan(budget=4.0)["skipped"]
    assert skipped == [
        {"test_id": "b", "skip_reason": "budget exhausted", "skip_debt": 0}
    ]


def test_pinned_test_is_selected_with_its_rule_as_reason():
    selected = _plan()["selected"]
    assert selected[0] == {"test_id": "pin", "reason": "pinned", "duration_s": 3.0}


def test_catch_rate_estimate_counts_selected_failures():
    assert _plan(budget=100)["catch_rate_estimate"] == 1.0
    assert _plan()["catch_rate_estimate"] == 0.0


def test_negative_budget_is_rejected():
    with pytest.raises(ValueError):
        build_plan("abc", {"selected": [], "skipped": []}, "low", -1)


def test_risk_level_is_medium_with_empty_history():
    assert plan_risk_level(["src/pay.py"], [], []) == "medium"


def test_risk_level_comes_from_history():
    runs, results = load_history_records("fixtures/history_small")
    assert plan_risk_level(["src/pay.py"], runs, results) in {"low", "medium", "high"}


def test_write_plan_round_trips(tmp_path):
    out = write_plan(_plan(), tmp_path / "out" / "plan.json")
    assert json.loads(out.read_text(encoding="utf-8"))["sha"] == "abc"
