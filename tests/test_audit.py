import copy

import pytest

from testbudget.audit import (
    AuditModeError,
    apply_reviewer_command,
    build_execution_policy,
)

from testbudget.reviewer import (
    parse_reviewer_command,
)

def make_plan():
    """
    Return a small TestBudget plan fixture.
    """

    return {
        "sha": "abc123",
        "risk_level": "medium",
        "budget_s": 10,
        "selected": [
            {
                "test_id": "test-a",
                "reason": "high risk",
                "duration_s": 1.0,
            },
            {
                "test_id": "test-b",
                "reason": "historical failure",
                "duration_s": 2.0,
            },
        ],
        "skipped": [
            {
                "test_id": "test-c",
                "skip_reason": "budget",
                "skip_debt": 1,
            },
            {
                "test_id": "test-d",
                "skip_reason": "budget",
                "skip_debt": 0,
            },
        ],
        "catch_rate_estimate": 0.85,
    }


ALL_TESTS = [
    "test-a",
    "test-b",
    "test-c",
    "test-d",
]


def test_normal_mode_executes_selected_only():
    policy = build_execution_policy(
        make_plan(),
        ALL_TESTS,
    )

    assert policy[
        "mode"
    ] == "normal"

    assert policy[
        "execute_test_ids"
    ] == [
        "test-a",
        "test-b",
    ]


def test_audit_mode_executes_full_suite():
    policy = build_execution_policy(
        make_plan(),
        ALL_TESTS,
        audit_mode=True,
    )

    assert policy[
        "mode"
    ] == "audit"

    assert policy[
        "execute_test_ids"
    ] == ALL_TESTS


def test_audit_mode_preserves_planned_selection():
    policy = build_execution_policy(
        make_plan(),
        ALL_TESTS,
        audit_mode=True,
    )

    assert policy[
        "planned_selected_test_ids"
    ] == [
        "test-a",
        "test-b",
    ]

    assert policy[
        "planned_skipped_test_ids"
    ] == [
        "test-c",
        "test-d",
    ]


def test_reviewer_full_executes_full_suite():
    policy = build_execution_policy(
        make_plan(),
        ALL_TESTS,
        force_full=True,
    )

    assert policy[
        "mode"
    ] == "reviewer_full"

    assert policy[
        "execute_test_ids"
    ] == ALL_TESTS


def test_reviewer_full_wins_when_audit_also_enabled():
    policy = build_execution_policy(
        make_plan(),
        ALL_TESTS,
        audit_mode=True,
        force_full=True,
    )

    assert policy[
        "mode"
    ] == "reviewer_full"

    assert policy[
        "execute_test_ids"
    ] == ALL_TESTS


def test_plan_is_not_mutated():
    plan = make_plan()

    original = copy.deepcopy(
        plan
    )

    build_execution_policy(
        plan,
        ALL_TESTS,
        audit_mode=True,
    )

    assert plan == original


def test_full_suite_order_is_preserved():
    all_tests = [
        "test-d",
        "test-a",
        "test-c",
        "test-b",
    ]

    policy = build_execution_policy(
        make_plan(),
        all_tests,
        audit_mode=True,
    )

    assert policy[
        "execute_test_ids"
    ] == all_tests


def test_duplicate_full_suite_ids_are_removed():
    policy = build_execution_policy(
        make_plan(),
        [
            "test-a",
            "test-b",
            "test-b",
            "test-c",
            "test-d",
        ],
        audit_mode=True,
    )

    assert policy[
        "execute_test_ids"
    ] == ALL_TESTS


def test_unknown_plan_test_is_rejected():
    plan = make_plan()

    plan[
        "selected"
    ].append(
        {
            "test_id": "unknown-test",
            "reason": "bad fixture",
            "duration_s": 1.0,
        }
    )

    with pytest.raises(
        AuditModeError,
        match="unknown test ID",
    ):
        build_execution_policy(
            plan,
            ALL_TESTS,
        )


def test_missing_selected_list_is_rejected():
    plan = make_plan()

    del plan[
        "selected"
    ]

    with pytest.raises(
        AuditModeError,
        match="selected list",
    ):
        build_execution_policy(
            plan,
            ALL_TESTS,
        )


def test_missing_skipped_list_is_rejected():
    plan = make_plan()

    del plan[
        "skipped"
    ]

    with pytest.raises(
        AuditModeError,
        match="skipped list",
    ):
        build_execution_policy(
            plan,
            ALL_TESTS,
        )


def test_apply_full_reviewer_command():
    policy = apply_reviewer_command(
        make_plan(),
        ALL_TESTS,
        {
            "action": "full",
        },
    )

    assert (
        policy["mode"]
        == "reviewer_full"
    )

    assert (
        policy["execute_test_ids"]
        == ALL_TESTS
    )


def test_apply_no_reviewer_command_uses_normal_mode():
    policy = apply_reviewer_command(
        make_plan(),
        ALL_TESTS,
        None,
    )

    assert policy[
        "mode"
    ] == "normal"

    assert policy[
        "execute_test_ids"
    ] == [
        "test-a",
        "test-b",
    ]


def test_unknown_reviewer_command_is_rejected():
    with pytest.raises(
        AuditModeError,
        match="unsupported reviewer command",
    ):
        apply_reviewer_command(
            make_plan(),
            ALL_TESTS,
            {
                "action": "destroy",
            },
        )


def test_writer_comment_forces_full_suite_end_to_end():
    command = parse_reviewer_command(
        "/testbudget full",
        "write",
    )

    policy = apply_reviewer_command(
        make_plan(),
        ALL_TESTS,
        command,
    )

    assert (
        policy["mode"]
        == "reviewer_full"
    )

    assert (
        policy["execute_test_ids"]
        == ALL_TESTS
    )


def test_audit_mode_without_comment_still_runs_full_suite():
    command = parse_reviewer_command(
        "ordinary review comment",
        "write",
    )

    assert command is None

    policy = apply_reviewer_command(
        make_plan(),
        ALL_TESTS,
        command,
        audit_mode=True,
    )

    assert (
        policy["mode"]
        == "audit"
    )

    assert (
        policy["execute_test_ids"]
        == ALL_TESTS
    )

    assert (
        policy[
            "planned_selected_test_ids"
        ]
        == [
            "test-a",
            "test-b",
        ]
    )