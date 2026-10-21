import pytest

from testbudget.ranker import (
    get_linked_tests,
    rank_tests,
    rank_tests_coverage,
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
    selected_names = {test["test_name"] for test in result["selected"]}
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
    selected_names = [test["test_name"] for test in result["selected"]]
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


def _stat(name, duration=1.0, failures=0, last_failure=None):
    return {
        "test_name": name,
        "failure_count": failures,
        "avg_duration": duration,
        "last_failure": last_failure,
    }


def _names(ranked):
    return [test["test_name"] for test in ranked]


def test_test_covering_high_weight_file_ranks_first():
    stats = [_stat("t_low"), _stat("t_high")]
    links = {"low.py": ["t_low"], "high.py": ["t_high"]}
    ranked = rank_tests_coverage(stats, ["low.py", "high.py"], links, {"high.py": 0.9})
    assert _names(ranked) == ["t_high", "t_low"]
    assert ranked[0]["reason"] == "covers high.py"


def test_redundant_test_never_precedes_uncovered_file_of_equal_value():
    stats = [_stat("a_first"), _stat("b_same"), _stat("c_other")]
    links = {"x.py": ["a_first", "b_same"], "y.py": ["c_other"]}
    ranked = rank_tests_coverage(stats, ["x.py", "y.py"], links, {})
    assert _names(ranked) == ["a_first", "c_other", "b_same"]


def test_value_is_per_second():
    stats = [_stat("slow", duration=10.0), _stat("fast", duration=1.0)]
    links = {"a.py": ["slow", "fast"]}
    assert _names(rank_tests_coverage(stats, ["a.py"], links, {}))[0] == "fast"


def test_empty_links_fall_back_to_recent_failure_then_name():
    stats = [
        _stat("b_never"),
        _stat("old_fail", failures=1, last_failure="2026-10-01T00:00:00Z"),
        _stat("a_never"),
        _stat("new_fail", failures=2, last_failure="2026-10-05T00:00:00Z"),
    ]
    ranked = rank_tests_coverage(stats, ["a.py"], {}, {})
    assert _names(ranked) == ["new_fail", "old_fail", "a_never", "b_never"]
    assert ranked[0]["reason"] == "no changed file + 2 historical failures"


def test_result_has_rank_tests_shape():
    ranked = rank_tests_coverage([_stat("t")], ["a.py"], {"a.py": ["t"]}, {})
    assert set(ranked[0]) == {
        "test_name",
        "score",
        "duration",
        "failure_count",
        "linked_to_change",
        "reason",
    }
    assert ranked[0]["linked_to_change"] is True


def test_empty_stats_give_empty_ranking():
    assert rank_tests_coverage([], ["a.py"], {"a.py": ["t"]}, {}) == []
