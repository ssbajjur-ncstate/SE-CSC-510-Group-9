from pathlib import Path

import pytest

from testbudget.adapters.playwright_adapter import (
    PlaywrightAdapterError,
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