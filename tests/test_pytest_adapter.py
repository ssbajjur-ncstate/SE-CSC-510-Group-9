from pathlib import Path

import pytest

from testbudget.adapters.pytest_adapter import (
    PytestAdapterError,
    item_to_test_id,
    load_selected_test_ids,
    normalize_pytest_test_id,
    parse_pytest_junit,
    pytest_collection_modifyitems,
)

pytest_plugins = ["pytester"]

FIXTURES = Path(__file__).parent / "fixtures"


def test_normalize_pytest_test_id_from_file():
    test_id = normalize_pytest_test_id(
        "tests/test_checkout.py",
        "test_checkout_success",
    )

    assert test_id == ("tests/test_checkout.py::test_checkout_success")


def test_normalize_windows_path():
    test_id = normalize_pytest_test_id(
        r"tests\test_checkout.py",
        "test_checkout_success",
    )

    assert test_id == ("tests/test_checkout.py::test_checkout_success")


def test_normalize_test_id_from_classname():
    test_id = normalize_pytest_test_id(
        None,
        "test_payment_success",
        "tests.test_payment",
    )

    assert test_id == ("tests/test_payment.py::test_payment_success")


def test_classname_with_test_class_uses_module_path():
    test_id = normalize_pytest_test_id(
        None,
        "test_payment_timeout",
        "tests.test_payment.TestPayment",
    )

    assert test_id == ("tests/test_payment.py::test_payment_timeout")


def test_parse_xunit1():
    results = parse_pytest_junit(FIXTURES / "pytest_xunit1.xml")

    assert len(results) == 4

    assert results[0] == {
        "test_id": ("tests/test_checkout.py::test_checkout_success"),
        "status": "passed",
        "duration_s": 1.2,
        "attempt": 1,
    }


def test_xunit1_failure():
    results = parse_pytest_junit(FIXTURES / "pytest_xunit1.xml")

    failed = next(
        item
        for item in results
        if item["test_id"].endswith("::test_checkout_invalid_card")
    )

    assert failed["status"] == "failed"


def test_xunit1_skipped():
    results = parse_pytest_junit(FIXTURES / "pytest_xunit1.xml")

    skipped = next(item for item in results if item["test_id"].endswith("::test_cart"))

    assert skipped["status"] == "skipped"


def test_missing_time_becomes_zero():
    results = parse_pytest_junit(FIXTURES / "pytest_xunit1.xml")

    login = next(item for item in results if item["test_id"].endswith("::test_login"))

    assert login["duration_s"] == 0.0


def test_parse_xunit2_without_file_attribute():
    results = parse_pytest_junit(FIXTURES / "pytest_xunit2.xml")

    assert results[0]["test_id"] == ("tests/test_payment.py::test_payment_success")


def test_xunit2_error_counts_as_failed():
    results = parse_pytest_junit(FIXTURES / "pytest_xunit2.xml")

    timeout = next(
        item for item in results if item["test_id"].endswith("::test_payment_timeout")
    )

    assert timeout["status"] == "failed"


def test_missing_report_raises_error(
    tmp_path,
):
    missing = tmp_path / "missing.xml"

    with pytest.raises(
        PytestAdapterError,
        match="does not exist",
    ):
        parse_pytest_junit(missing)


def test_invalid_xml_raises_error(
    tmp_path,
):
    report = tmp_path / "broken.xml"

    report.write_text(
        "<testsuite>",
        encoding="utf-8",
    )

    with pytest.raises(
        PytestAdapterError,
        match="invalid JUnit XML",
    ):
        parse_pytest_junit(report)


def test_missing_identity_raises_error(
    tmp_path,
):
    report = tmp_path / "missing-id.xml"

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
        parse_pytest_junit(report)


def test_invalid_duration_raises_error(
    tmp_path,
):
    report = tmp_path / "bad-time.xml"

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
        parse_pytest_junit(report)


def test_repeated_testcases_increment_attempt(
    tmp_path,
):
    report = tmp_path / "retry.xml"

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

    results = parse_pytest_junit(report)

    assert len(results) == 2

    assert results[0]["attempt"] == 1
    assert results[1]["attempt"] == 2

    assert results[0]["status"] == "failed"
    assert results[1]["status"] == "passed"


class FakeItem:
    """
    Minimal pytest item used to test collection ordering.
    """

    def __init__(
        self,
        nodeid,
    ):
        self.nodeid = nodeid


class FakeHook:
    """
    Capture items reported as deselected.
    """

    def __init__(self):
        self.deselected = []

    def pytest_deselected(
        self,
        items,
    ):
        self.deselected.extend(items)


class FakeConfig:
    """
    Minimal pytest config used by adapter unit tests.
    """

    def __init__(
        self,
        plan_path,
    ):
        self.plan_path = plan_path
        self.hook = FakeHook()

    def getoption(
        self,
        name,
    ):
        assert name == "--testbudget-plan"

        return self.plan_path


def write_plan(
    path,
    test_ids,
):
    path.write_text(
        __import__("json").dumps(
            {
                "sha": "abc123",
                "risk_level": "medium",
                "budget_s": 10,
                "selected": [
                    {
                        "test_id": test_id,
                        "reason": "fixture",
                        "duration_s": 1.0,
                    }
                    for test_id in test_ids
                ],
                "skipped": [],
                "catch_rate_estimate": 0.8,
            }
        ),
        encoding="utf-8",
    )


def test_load_selected_ids_preserves_plan_order(
    tmp_path,
):
    plan = tmp_path / "plan.json"

    write_plan(
        plan,
        [
            ("tests/test_payment.py::test_payment"),
            ("tests/test_checkout.py::test_checkout"),
        ],
    )

    selected = load_selected_test_ids(plan)

    assert selected == [
        ("tests/test_payment.py::test_payment"),
        ("tests/test_checkout.py::test_checkout"),
    ]


def test_plan_ignores_non_pytest_ids(
    tmp_path,
):
    plan = tmp_path / "plan.json"

    write_plan(
        plan,
        [
            "tests/test_checkout.py::test_checkout",
            "checkout.spec.ts › checkout works",
        ],
    )

    selected = load_selected_test_ids(plan)

    assert selected == [("tests/test_checkout.py::test_checkout")]


def test_missing_plan_raises_error(
    tmp_path,
):
    with pytest.raises(
        PytestAdapterError,
        match="does not exist",
    ):
        load_selected_test_ids(tmp_path / "missing.json")


def test_invalid_plan_json_raises_error(
    tmp_path,
):
    plan = tmp_path / "plan.json"

    plan.write_text(
        "{bad json",
        encoding="utf-8",
    )

    with pytest.raises(
        PytestAdapterError,
        match="invalid TestBudget plan JSON",
    ):
        load_selected_test_ids(plan)


def test_plan_without_selected_raises_error(
    tmp_path,
):
    plan = tmp_path / "plan.json"

    plan.write_text(
        "{}",
        encoding="utf-8",
    )

    with pytest.raises(
        PytestAdapterError,
        match="selected list",
    ):
        load_selected_test_ids(plan)


def test_pytest_item_to_test_id_removes_class_component():
    item = FakeItem("tests/test_cart.py::TestCart::test_add_item")

    assert item_to_test_id(item) == ("tests/test_cart.py::test_add_item")


def test_collection_is_reordered_to_plan(
    tmp_path,
):
    plan = tmp_path / "plan.json"

    write_plan(
        plan,
        [
            ("tests/test_payment.py::test_payment"),
            ("tests/test_checkout.py::test_checkout"),
        ],
    )

    checkout = FakeItem("tests/test_checkout.py::test_checkout")

    login = FakeItem("tests/test_login.py::test_login")

    payment = FakeItem("tests/test_payment.py::test_payment")

    items = [
        checkout,
        login,
        payment,
    ]

    config = FakeConfig(plan)

    pytest_collection_modifyitems(
        config,
        items,
    )

    assert items == [
        payment,
        checkout,
    ]


def test_tests_not_in_plan_are_deselected(
    tmp_path,
):
    plan = tmp_path / "plan.json"

    write_plan(
        plan,
        [("tests/test_checkout.py::test_checkout")],
    )

    checkout = FakeItem("tests/test_checkout.py::test_checkout")

    login = FakeItem("tests/test_login.py::test_login")

    items = [
        login,
        checkout,
    ]

    config = FakeConfig(plan)

    pytest_collection_modifyitems(
        config,
        items,
    )

    assert items == [checkout]

    assert config.hook.deselected == [login]


def test_collection_unchanged_without_plan():
    checkout = FakeItem("tests/test_checkout.py::test_checkout")

    login = FakeItem("tests/test_login.py::test_login")

    items = [
        checkout,
        login,
    ]

    config = FakeConfig(None)

    pytest_collection_modifyitems(
        config,
        items,
    )

    assert items == [
        checkout,
        login,
    ]


def test_real_pytest_plugin_reorders_and_cuts(
    pytester,
):
    pytester.makepyfile(
        test_example="""
def test_alpha():
    assert True

def test_beta():
    assert True

def test_gamma():
    assert True
"""
    )

    plan_path = pytester.path / "plan.json"

    write_plan(
        plan_path,
        [
            ("test_example.py::test_gamma"),
            ("test_example.py::test_alpha"),
        ],
    )

    result = pytester.runpytest(
        "-p",
        "testbudget.adapters.pytest_adapter",
        "--testbudget-plan",
        str(plan_path),
        "-v",
    )

    result.assert_outcomes(
        passed=2,
        deselected=1,
    )

    result.stdout.fnmatch_lines(
        [
            "*test_example.py::test_gamma*PASSED*",
            "*test_example.py::test_alpha*PASSED*",
        ]
    )
