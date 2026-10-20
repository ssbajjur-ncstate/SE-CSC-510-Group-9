import pytest

from testbudget.ranker import (
    get_linked_tests,
    rank_tests,
)
from testbudget.selector import select_with_budget


def test_get_linked_tests():
    links = {
        "src/checkout.py": [
            "test_checkout",
            "test_payment",
        ],
        "src/auth.py": [
            "test_login",
        ],
    }
    linked = get_linked_tests(
        ["src/checkout.py"],
        links,
    )
    assert linked == {
        "test_checkout",
        "test_payment",
    }

def test_changed_test_ranks_above_unrelated_test():
    stats = [
        {
            "test_name": "test_checkout",
            "run_count": 5,
            "failure_count": 0,
            "avg_duration": 2.0,
        },
        {
            "test_name": "test_login",
            "run_count": 5,
            "failure_count": 1,
            "avg_duration": 2.0,
        },
    ]
    links = {
        "src/checkout.py": [
            "test_checkout",
        ]
    }
    ranked = rank_tests(
        stats,
        ["src/checkout.py"],
        links,
    )
    assert ranked[0]["test_name"] == "test_checkout"
    assert ranked[0]["linked_to_change"] is True

def test_historical_failures_increase_score():
    stats = [
        {
            "test_name": "test_frequent_failure",
            "run_count": 10,
            "failure_count": 4,
            "avg_duration": 2.0,
        },
        {
            "test_name": "test_never_failed",
            "run_count": 10,
            "failure_count": 0,
            "avg_duration": 2.0,
        },
    ]
    ranked = rank_tests(
        stats,
        [],
        {},
    )
    assert ranked[0]["test_name"] == "test_frequent_failure"
    assert ranked[0]["score"] > ranked[1]["score"]

def test_selection_never_exceeds_budget():
    ranked = [
        {
            "test_name": "test_a",
            "score": 10,
            "duration": 4.0,
        },
        {
            "test_name": "test_b",
            "score": 8,
            "duration": 3.0,
        },
        {
            "test_name": "test_c",
            "score": 6,
            "duration": 8.0,
        },
    ]
    result = select_with_budget(
        ranked,
        budget=10,
    )
    assert result["estimated_runtime"] <= 10
    selected_names = {
        test["test_name"]
        for test in result["selected"]
    }
    assert selected_names == {
        "test_a",
        "test_b",
    }

def test_shorter_test_can_fit_after_large_test_is_skipped():
    ranked = [
        {
            "test_name": "test_a",
            "score": 10,
            "duration": 6.0,
        },
        {
            "test_name": "test_large",
            "score": 9,
            "duration": 8.0,
        },
        {
            "test_name": "test_small",
            "score": 8,
            "duration": 2.0,
        },
    ]
    result = select_with_budget(
        ranked,
        budget=10,
    )
    selected_names = [
        test["test_name"]
        for test in result["selected"]
    ]
    assert selected_names == [
        "test_a",
        "test_small",
    ]

def test_ranking_is_deterministic():
    stats = [
        {
            "test_name": "test_b",
            "run_count": 5,
            "failure_count": 1,
            "avg_duration": 2.0,
        },
        {
            "test_name": "test_a",
            "run_count": 5,
            "failure_count": 1,
            "avg_duration": 2.0,
        },
    ]
    first = rank_tests(
        stats,
        [],
        {},
    )
    second = rank_tests(
        stats,
        [],
        {},
    )
    assert first == second
    assert first[0]["test_name"] == "test_a"

def test_negative_budget_is_rejected():
    with pytest.raises(ValueError):
        select_with_budget(
            [],
            budget=-1,
        )