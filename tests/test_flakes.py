import pytest

from testbudget.flakes import (
    FlakeFilterError,
    filter_non_flaky_failures,
    mark_flaky_failures,
)


def make_result(
    *,
    sha="abc123",
    test_id=(
        "tests/test_cart.py"
        "::test_cart"
    ),
    status="failed",
    duration_s=1.0,
    attempt=1,
):
    """
    Build one result following TestBudget's shared history contract.
    """

    return {
        "sha": sha,
        "test_id": test_id,
        "status": status,
        "duration_s": duration_s,
        "attempt": attempt,
    }


def test_empty_history_returns_empty_list():
    assert (
        mark_flaky_failures([])
        == []
    )


def test_failure_that_passes_on_retry_is_flaky():
    results = [
        make_result(
            status="failed",
            attempt=1,
        ),
        make_result(
            status="passed",
            attempt=2,
        ),
    ]

    marked = mark_flaky_failures(
        results
    )

    assert marked[0]["flaky"] is True

    assert (
        marked[0]["flake_reason"]
        == "passed_on_retry"
    )

    assert marked[1]["flaky"] is False


def test_failure_that_passes_on_same_sha_is_flaky():
    results = [
        make_result(
            status="failed",
            attempt=1,
        ),
        make_result(
            status="passed",
            attempt=1,
        ),
    ]

    marked = mark_flaky_failures(
        results
    )

    assert marked[0]["flaky"] is True

    assert (
        marked[0]["flake_reason"]
        == "passed_on_same_sha"
    )


def test_pass_on_different_sha_does_not_make_failure_flaky():
    results = [
        make_result(
            sha="abc123",
            status="failed",
        ),
        make_result(
            sha="def456",
            status="passed",
        ),
    ]

    marked = mark_flaky_failures(
        results
    )

    assert marked[0]["flaky"] is False

    assert (
        marked[0]["flake_reason"]
        is None
    )


def test_pass_from_different_test_does_not_make_failure_flaky():
    results = [
        make_result(
            test_id=(
                "tests/test_cart.py"
                "::test_cart"
            ),
            status="failed",
        ),
        make_result(
            test_id=(
                "tests/test_login.py"
                "::test_login"
            ),
            status="passed",
        ),
    ]

    marked = mark_flaky_failures(
        results
    )

    assert marked[0]["flaky"] is False


def test_failure_without_pass_remains_non_flaky():
    results = [
        make_result(
            status="failed",
        )
    ]

    marked = mark_flaky_failures(
        results
    )

    assert marked[0]["flaky"] is False

    assert (
        marked[0]["flake_reason"]
        is None
    )


def test_skipped_test_is_not_marked_flaky():
    results = [
        make_result(
            status="skipped",
        ),
        make_result(
            status="passed",
            attempt=2,
        ),
    ]

    marked = mark_flaky_failures(
        results
    )

    assert marked[0]["flaky"] is False


def test_multiple_failures_become_flaky_when_same_sha_passes():
    results = [
        make_result(
            status="failed",
            attempt=1,
        ),
        make_result(
            status="failed",
            attempt=2,
        ),
        make_result(
            status="passed",
            attempt=3,
        ),
    ]

    marked = mark_flaky_failures(
        results
    )

    assert marked[0]["flaky"] is True
    assert marked[1]["flaky"] is True

    assert (
        marked[0]["flake_reason"]
        == "passed_on_retry"
    )

    assert (
        marked[1]["flake_reason"]
        == "passed_on_retry"
    )


def test_filter_non_flaky_failures_removes_flaky_failures():
    flaky_test = (
        "tests/test_cart.py"
        "::test_cart"
    )

    real_failure = (
        "tests/test_payment.py"
        "::test_payment"
    )

    results = [
        make_result(
            test_id=flaky_test,
            status="failed",
            attempt=1,
        ),
        make_result(
            test_id=flaky_test,
            status="passed",
            attempt=2,
        ),
        make_result(
            test_id=real_failure,
            status="failed",
            attempt=1,
        ),
    ]

    failures = (
        filter_non_flaky_failures(
            results
        )
    )

    assert len(failures) == 1

    assert (
        failures[0]["test_id"]
        == real_failure
    )

    assert failures[0]["flaky"] is False


def test_input_records_are_not_mutated():
    original = make_result(
        status="failed",
    )

    results = [
        original,
        make_result(
            status="passed",
            attempt=2,
        ),
    ]

    mark_flaky_failures(
        results
    )

    assert "flaky" not in original
    assert "flake_reason" not in original


def test_input_order_is_preserved():
    first = make_result(
        test_id=(
            "tests/test_first.py"
            "::test_first"
        ),
        status="failed",
    )

    second = make_result(
        test_id=(
            "tests/test_second.py"
            "::test_second"
        ),
        status="failed",
    )

    marked = mark_flaky_failures(
        [
            first,
            second,
        ]
    )

    assert [
        result["test_id"]
        for result in marked
    ] == [
        first["test_id"],
        second["test_id"],
    ]


def test_missing_required_field_raises_error():
    result = make_result()

    del result["sha"]

    with pytest.raises(
        FlakeFilterError,
        match="missing required fields",
    ):
        mark_flaky_failures(
            [result]
        )


def test_invalid_status_raises_error():
    result = make_result(
        status="broken"
    )

    with pytest.raises(
        FlakeFilterError,
        match="unsupported status",
    ):
        mark_flaky_failures(
            [result]
        )


def test_invalid_attempt_raises_error():
    result = make_result(
        attempt=0
    )

    with pytest.raises(
        FlakeFilterError,
        match="invalid attempt",
    ):
        mark_flaky_failures(
            [result]
        )


def test_negative_duration_raises_error():
    result = make_result(
        duration_s=-1.0
    )

    with pytest.raises(
        FlakeFilterError,
        match="invalid duration_s",
    ):
        mark_flaky_failures(
            [result]
        )