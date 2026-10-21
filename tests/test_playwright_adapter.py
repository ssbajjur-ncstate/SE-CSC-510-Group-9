import json
from pathlib import Path

import pytest

from testbudget.adapters.playwright_adapter import (
    PlaywrightAdapterError,
    build_playwright_invocations,
    load_playwright_test_ids,
    normalize_playwright_file,
    normalize_playwright_test_id,
    parse_playwright_junit,
    split_playwright_test_id,
)


FIXTURES = (
    Path(__file__).parent
    / "fixtures"
)


def test_normalize_playwright_test_id():
    test_id = (
        normalize_playwright_test_id(
            "tests/checkout.spec.ts",
            "checkout succeeds",
        )
    )

    assert test_id == (
        "tests/checkout.spec.ts "
        "› checkout succeeds"
    )


def test_windows_path_is_normalized():
    test_id = (
        normalize_playwright_test_id(
            r"tests\checkout.spec.ts",
            "checkout succeeds",
        )
    )

    assert test_id == (
        "tests/checkout.spec.ts "
        "› checkout succeeds"
    )


def test_old_line_column_suffix_is_removed():
    path = normalize_playwright_file(
        "tests/login.spec.ts:13:5"
    )

    assert path == (
        "tests/login.spec.ts"
    )


def test_parse_playwright_junit():
    results = parse_playwright_junit(
        FIXTURES
        / "playwright_junit.xml"
    )

    assert len(results) == 6


def test_playwright_pass():
    results = parse_playwright_junit(
        FIXTURES
        / "playwright_junit.xml"
    )

    result = next(
        item
        for item in results
        if item["test_id"].endswith(
            "› checkout succeeds"
        )
    )

    assert result == {
        "test_id": (
            "tests/checkout.spec.ts "
            "› checkout succeeds"
        ),
        "status": "passed",
        "duration_s": 1.2,
        "attempt": 1,
    }


def test_playwright_failure():
    results = parse_playwright_junit(
        FIXTURES
        / "playwright_junit.xml"
    )

    result = next(
        item
        for item in results
        if item["test_id"].endswith(
            "› invalid card is rejected"
        )
    )

    assert result["status"] == "failed"
    assert result["attempt"] == 1
    assert result["duration_s"] == 1.6


def test_playwright_skip():
    results = parse_playwright_junit(
        FIXTURES
        / "playwright_junit.xml"
    )

    result = next(
        item
        for item in results
        if item["test_id"].endswith(
            "› coupon is optional"
        )
    )

    assert result["status"] == "skipped"


def test_flaky_retry_counts_once():
    results = parse_playwright_junit(
        FIXTURES
        / "playwright_junit.xml"
    )

    matches = [
        item
        for item in results
        if item["test_id"].endswith(
            "› payment eventually succeeds"
        )
    ]

    assert len(matches) == 1

    result = matches[0]

    assert result["status"] == "passed"
    assert result["attempt"] == 2


def test_flaky_retry_uses_final_pass_duration():
    results = parse_playwright_junit(
        FIXTURES
        / "playwright_junit.xml"
    )

    result = next(
        item
        for item in results
        if item["test_id"].endswith(
            "› payment eventually succeeds"
        )
    )

    # The failed retry took 1.4 seconds.
    # The final passing attempt took 0.8 seconds.
    assert result["duration_s"] == 0.8


def test_failed_retry_counts_once():
    results = parse_playwright_junit(
        FIXTURES
        / "playwright_junit.xml"
    )

    matches = [
        item
        for item in results
        if item["test_id"].endswith(
            "› account remains unavailable"
        )
    ]

    assert len(matches) == 1

    result = matches[0]

    assert result["status"] == "failed"
    assert result["attempt"] == 2


def test_failed_retry_uses_final_retry_duration():
    results = parse_playwright_junit(
        FIXTURES
        / "playwright_junit.xml"
    )

    result = next(
        item
        for item in results
        if item["test_id"].endswith(
            "› account remains unavailable"
        )
    )

    assert result["duration_s"] == 0.7


def test_missing_time_becomes_zero():
    results = parse_playwright_junit(
        FIXTURES
        / "playwright_junit.xml"
    )

    result = next(
        item
        for item in results
        if item["test_id"].endswith(
            "› profile loads"
        )
    )

    assert result["duration_s"] == 0.0


def test_missing_report_raises_error(
    tmp_path,
):
    with pytest.raises(
        PlaywrightAdapterError,
        match="does not exist",
    ):
        parse_playwright_junit(
            tmp_path / "missing.xml"
        )


def test_malformed_xml_raises_error(
    tmp_path,
):
    report = (
        tmp_path / "broken.xml"
    )

    report.write_text(
        "<testsuites>",
        encoding="utf-8",
    )

    with pytest.raises(
        PlaywrightAdapterError,
        match="invalid Playwright JUnit XML",
    ):
        parse_playwright_junit(
            report
        )


def test_missing_file_raises_error(
    tmp_path,
):
    report = (
        tmp_path / "missing-file.xml"
    )

    report.write_text(
        """
        <testsuite>
            <testcase
                name="checkout works"
                time="1.0"
            />
        </testsuite>
        """,
        encoding="utf-8",
    )

    with pytest.raises(
        PlaywrightAdapterError,
        match="no usable file",
    ):
        parse_playwright_junit(
            report
        )


def test_invalid_time_raises_error(
    tmp_path,
):
    report = (
        tmp_path / "bad-time.xml"
    )

    report.write_text(
        """
        <testsuite>
            <testcase
                classname="tests/example.spec.ts"
                name="example works"
                time="slow"
            />
        </testsuite>
        """,
        encoding="utf-8",
    )

    with pytest.raises(
        PlaywrightAdapterError,
        match="invalid JUnit time",
    ):
        parse_playwright_junit(
            report
        )


def test_split_playwright_test_id():
    test_file, title = (
        split_playwright_test_id(
            (
                "tests/checkout.spec.ts "
                "› checkout succeeds"
            )
        )
    )

    assert test_file == (
        "tests/checkout.spec.ts"
    )

    assert title == (
        "checkout succeeds"
    )




def write_plan(
    path,
    test_ids,
):
    path.write_text(
        json.dumps(
            {
                "sha": "abc123",
                "risk_level": "medium",
                "budget_s": 20,
                "selected": [
                    {
                        "test_id": test_id,
                        "reason": "fixture",
                        "duration_s": 1.0,
                    }
                    for test_id
                    in test_ids
                ],
                "skipped": [],
                "catch_rate_estimate": 0.8,
            }
        ),
        encoding="utf-8",
    )


def test_load_playwright_ids_preserves_plan_order(
    tmp_path,
):
    plan = (
        tmp_path / "plan.json"
    )

    write_plan(
        plan,
        [
            (
                "tests/payment.spec.ts "
                "› payment succeeds"
            ),
            (
                "tests/checkout.spec.ts "
                "› checkout succeeds"
            ),
        ],
    )

    selected = (
        load_playwright_test_ids(
            plan
        )
    )

    assert selected == [
        (
            "tests/payment.spec.ts "
            "› payment succeeds"
        ),
        (
            "tests/checkout.spec.ts "
            "› checkout succeeds"
        ),
    ]


def test_pytest_ids_are_ignored(
    tmp_path,
):
    plan = (
        tmp_path / "plan.json"
    )

    write_plan(
        plan,
        [
            (
                "tests/test_cart.py"
                "::test_cart"
            ),
            (
                "tests/cart.spec.ts "
                "› cart works"
            ),
        ],
    )

    selected = (
        load_playwright_test_ids(
            plan
        )
    )

    assert selected == [
        (
            "tests/cart.spec.ts "
            "› cart works"
        )
    ]


def test_invocations_group_tests_by_file(
    tmp_path,
):
    plan = (
        tmp_path / "plan.json"
    )

    write_plan(
        plan,
        [
            (
                "tests/checkout.spec.ts "
                "› checkout succeeds"
            ),
            (
                "tests/payment.spec.ts "
                "› payment succeeds"
            ),
            (
                "tests/checkout.spec.ts "
                "› checkout rejects card"
            ),
        ],
    )

    invocations = (
        build_playwright_invocations(
            plan
        )
    )

    assert len(invocations) == 2

    assert invocations[0] == {
        "file": (
            "tests/checkout.spec.ts"
        ),
        "test_ids": [
            (
                "tests/checkout.spec.ts "
                "› checkout succeeds"
            ),
            (
                "tests/checkout.spec.ts "
                "› checkout rejects card"
            ),
        ],
        "titles": [
            "checkout succeeds",
            "checkout rejects card",
        ],
    }

    assert invocations[1][
        "file"
    ] == "tests/payment.spec.ts"


def test_invocation_file_order_uses_first_plan_occurrence(
    tmp_path,
):
    plan = (
        tmp_path / "plan.json"
    )

    write_plan(
        plan,
        [
            (
                "tests/z.spec.ts "
                "› z test"
            ),
            (
                "tests/a.spec.ts "
                "› a test"
            ),
        ],
    )

    invocations = (
        build_playwright_invocations(
            plan
        )
    )

    assert [
        item["file"]
        for item in invocations
    ] == [
        "tests/z.spec.ts",
        "tests/a.spec.ts",
    ]


def test_duplicate_playwright_id_is_removed(
    tmp_path,
):
    plan = (
        tmp_path / "plan.json"
    )

    test_id = (
        "tests/cart.spec.ts "
        "› cart works"
    )

    write_plan(
        plan,
        [
            test_id,
            test_id,
        ],
    )

    selected = (
        load_playwright_test_ids(
            plan
        )
    )

    assert selected == [
        test_id
    ]


def test_missing_plan_raises_error(
    tmp_path,
):
    with pytest.raises(
        PlaywrightAdapterError,
        match="does not exist",
    ):
        load_playwright_test_ids(
            tmp_path / "missing.json"
        )


def test_invalid_plan_json_raises_error(
    tmp_path,
):
    plan = (
        tmp_path / "plan.json"
    )

    plan.write_text(
        "{not json",
        encoding="utf-8",
    )

    with pytest.raises(
        PlaywrightAdapterError,
        match="invalid TestBudget plan JSON",
    ):
        load_playwright_test_ids(
            plan
        )


def test_plan_without_selected_raises_error(
    tmp_path,
):
    plan = (
        tmp_path / "plan.json"
    )

    plan.write_text(
        "{}",
        encoding="utf-8",
    )

    with pytest.raises(
        PlaywrightAdapterError,
        match="selected list",
    ):
        load_playwright_test_ids(
            plan
        )



def test_repeated_testcase_entries_are_deduplicated(
    tmp_path,
):
    report = (
        tmp_path / "repeated.xml"
    )

    report.write_text(
        """
        <testsuites>
            <testsuite name="tests/cart.spec.ts">

                <testcase
                    classname="tests/cart.spec.ts"
                    name="cart works"
                    time="1.5"
                >
                    <failure message="first failure" />
                </testcase>

                <testcase
                    classname="tests/cart.spec.ts"
                    name="cart works"
                    time="0.6"
                />

            </testsuite>
        </testsuites>
        """,
        encoding="utf-8",
    )

    results = parse_playwright_junit(
        report
    )

    assert len(results) == 1

    assert results[0] == {
        "test_id": (
            "tests/cart.spec.ts "
            "› cart works"
        ),
        "status": "passed",
        "duration_s": 0.6,
        "attempt": 2,
    }