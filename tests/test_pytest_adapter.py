from pathlib import Path

import pytest

from testbudget.adapters.pytest_adapter import (
    PytestAdapterError,
    normalize_pytest_test_id,
    parse_pytest_junit,
)


FIXTURES = (
    Path(__file__).parent
    / "fixtures"
)


def test_normalize_pytest_test_id_from_file():
    test_id = normalize_pytest_test_id(
        "tests/test_checkout.py",
        "test_checkout_success",
    )

    assert (
        test_id
        == (
            "tests/test_checkout.py"
            "::test_checkout_success"
        )
    )


def test_normalize_windows_path():
    test_id = normalize_pytest_test_id(
        r"tests\test_checkout.py",
        "test_checkout_success",
    )

    assert (
        test_id
        == (
            "tests/test_checkout.py"
            "::test_checkout_success"
        )
    )


def test_normalize_test_id_from_classname():
    test_id = normalize_pytest_test_id(
        None,
        "test_payment_success",
        "tests.test_payment",
    )

    assert (
        test_id
        == (
            "tests/test_payment.py"
            "::test_payment_success"
        )
    )


def test_classname_with_test_class_uses_module_path():
    test_id = normalize_pytest_test_id(
        None,
        "test_payment_timeout",
        "tests.test_payment.TestPayment",
    )

    assert (
        test_id
        == (
            "tests/test_payment.py"
            "::test_payment_timeout"
        )
    )


def test_parse_xunit1():
    results = parse_pytest_junit(
        FIXTURES
        / "pytest_xunit1.xml"
    )

    assert len(results) == 4

    assert results[0] == {
        "test_id": (
            "tests/test_checkout.py"
            "::test_checkout_success"
        ),
        "status": "passed",
        "duration_s": 1.2,
        "attempt": 1,
    }


def test_xunit1_failure():
    results = parse_pytest_junit(
        FIXTURES
        / "pytest_xunit1.xml"
    )

    failed = next(
        item
        for item in results
        if item["test_id"].endswith(
            "::test_checkout_invalid_card"
        )
    )

    assert failed["status"] == "failed"


def test_xunit1_skipped():
    results = parse_pytest_junit(
        FIXTURES
        / "pytest_xunit1.xml"
    )

    skipped = next(
        item
        for item in results
        if item["test_id"].endswith(
            "::test_cart"
        )
    )

    assert skipped["status"] == "skipped"


def test_missing_time_becomes_zero():
    results = parse_pytest_junit(
        FIXTURES
        / "pytest_xunit1.xml"
    )

    login = next(
        item
        for item in results
        if item["test_id"].endswith(
            "::test_login"
        )
    )

    assert login["duration_s"] == 0.0


def test_parse_xunit2_without_file_attribute():
    results = parse_pytest_junit(
        FIXTURES
        / "pytest_xunit2.xml"
    )

    assert results[0]["test_id"] == (
        "tests/test_payment.py"
        "::test_payment_success"
    )


def test_xunit2_error_counts_as_failed():
    results = parse_pytest_junit(
        FIXTURES
        / "pytest_xunit2.xml"
    )

    timeout = next(
        item
        for item in results
        if item["test_id"].endswith(
            "::test_payment_timeout"
        )
    )

    assert timeout["status"] == "failed"


def test_missing_report_raises_error(
    tmp_path,
):
    missing = (
        tmp_path / "missing.xml"
    )

    with pytest.raises(
        PytestAdapterError,
        match="does not exist",
    ):
        parse_pytest_junit(
            missing
        )


def test_invalid_xml_raises_error(
    tmp_path,
):
    report = (
        tmp_path / "broken.xml"
    )

    report.write_text(
        "<testsuite>",
        encoding="utf-8",
    )

    with pytest.raises(
        PytestAdapterError,
        match="invalid JUnit XML",
    ):
        parse_pytest_junit(
            report
        )


def test_missing_identity_raises_error(
    tmp_path,
):
    report = (
        tmp_path / "missing-id.xml"
    )

    report.write_text(
        """
        <testsuite>
            <testcase
                name="test_example"
                time="1.0"
            />
        </testsuite>
        """,
        encoding="utf-8",
    )

    with pytest.raises(
        PytestAdapterError,
        match="neither a usable file nor classname",
    ):
        parse_pytest_junit(
            report
        )


def test_invalid_duration_raises_error(
    tmp_path,
):
    report = (
        tmp_path / "bad-time.xml"
    )

    report.write_text(
        """
        <testsuite>
            <testcase
                classname="tests.test_example"
                name="test_example"
                time="not-a-number"
            />
        </testsuite>
        """,
        encoding="utf-8",
    )

    with pytest.raises(
        PytestAdapterError,
        match="invalid JUnit time",
    ):
        parse_pytest_junit(
            report
        )


def test_repeated_testcases_increment_attempt(
    tmp_path,
):
    report = (
        tmp_path / "retry.xml"
    )

    report.write_text(
        """
        <testsuite>

            <testcase
                classname="tests.test_example"
                name="test_example"
                time="1.0"
            >
                <failure message="first failure" />
            </testcase>

            <testcase
                classname="tests.test_example"
                name="test_example"
                time="0.5"
            />

        </testsuite>
        """,
        encoding="utf-8",
    )

    results = parse_pytest_junit(
        report
    )

    assert len(results) == 2

    assert results[0]["attempt"] == 1
    assert results[1]["attempt"] == 2

    assert results[0]["status"] == "failed"
    assert results[1]["status"] == "passed"