import pytest

from testbudget.adapters.pytest_adapter import PytestAdapterError
from testbudget.db import (
    get_all_results,
    get_test_stats,
    init_db,
    insert_test_results,
)
from testbudget.ingest import parse_junit

FIXTURE = "fixtures/sample_junit.xml"


def test_parser_reads_all_testcases():
    results = parse_junit(FIXTURE)

    assert len(results) == 5


def test_parser_detects_failures():
    results = parse_junit(FIXTURE)

    failed = [result for result in results if result["status"] == "failed"]

    assert len(failed) == 2

    failed_names = {result["test_name"] for result in failed}

    assert "tests/test_checkout.py::test_checkout_invalid_card" in failed_names
    assert "tests/test_payment.py::test_payment_timeout" in failed_names


def test_parser_extracts_duration():
    results = parse_junit(FIXTURE)

    checkout = next(
        result
        for result in results
        if result["test_name"] == "tests/test_checkout.py::test_checkout_success"
    )

    assert checkout["duration"] == 3.2


def test_database_stores_results(tmp_path):
    db_path = tmp_path / "testbudget.db"

    init_db(db_path)

    results = parse_junit(FIXTURE)

    inserted = insert_test_results(
        db_path,
        results,
        changed_file="src/checkout.py",
    )

    assert inserted == 5

    stored = get_all_results(db_path)

    assert len(stored) == 5

    assert stored[0]["changed_file"] == "src/checkout.py"


def test_stats_calculate_run_count(tmp_path):
    db_path = tmp_path / "testbudget.db"

    results = parse_junit(FIXTURE)

    insert_test_results(
        db_path,
        results,
        changed_file="src/checkout.py",
    )

    stats = get_test_stats(db_path)

    checkout = next(
        item
        for item in stats
        if item["test_name"] == "tests/test_checkout.py::test_checkout_invalid_card"
    )

    assert checkout["run_count"] == 1


def test_stats_calculate_failure_count(tmp_path):
    db_path = tmp_path / "testbudget.db"

    results = parse_junit(FIXTURE)

    # Pretend we ingested two historical CI runs.
    insert_test_results(
        db_path,
        results,
        changed_file="src/checkout.py",
    )

    insert_test_results(
        db_path,
        results,
        changed_file="src/payment.py",
    )

    stats = get_test_stats(db_path)

    checkout = next(
        item
        for item in stats
        if item["test_name"] == "tests/test_checkout.py::test_checkout_invalid_card"
    )

    assert checkout["run_count"] == 2
    assert checkout["failure_count"] == 2


def test_average_duration_is_calculated(tmp_path):
    db_path = tmp_path / "testbudget.db"

    results = [
        {
            "test_name": "test_example",
            "test_file": "tests.test_example",
            "status": "passed",
            "duration": 2.0,
        },
        {
            "test_name": "test_example",
            "test_file": "tests.test_example",
            "status": "failed",
            "duration": 4.0,
        },
    ]

    insert_test_results(
        db_path,
        results,
        changed_file="src/example.py",
    )

    stats = get_test_stats(db_path)

    example = stats[0]

    assert example["run_count"] == 2
    assert example["failure_count"] == 1
    assert example["avg_duration"] == 3.0


DOTTED = "fixtures/junit_dotted_classnames.xml"


def test_parser_builds_path_ids_from_dotted_classnames():
    ids = [result["test_name"] for result in parse_junit(DOTTED)]

    assert ids == [
        "tests/test_ranker.py::test_empty_input",
        "tests/test_selector.py::test_empty_input",
        "tests/test_rules.py::test_pin_first",
        "tests/test_cli.py::test_main",
    ]


def test_parser_sets_test_file_to_the_id_path():
    files = [result["test_file"] for result in parse_junit(DOTTED)]

    assert files[:2] == ["tests/test_ranker.py", "tests/test_selector.py"]


def test_same_name_in_two_files_stays_two_tests(tmp_path):
    db_path = tmp_path / "testbudget.db"

    insert_test_results(db_path, parse_junit(DOTTED), changed_file="x.py")

    stats = {item["test_name"]: item for item in get_test_stats(db_path)}

    assert len(stats) == 4
    assert stats["tests/test_ranker.py::test_empty_input"]["failure_count"] == 0
    assert stats["tests/test_selector.py::test_empty_input"]["failure_count"] == 1


def test_parser_rejects_testcase_without_path(tmp_path):
    xml_path = tmp_path / "bad.xml"
    xml_path.write_text(
        '<testsuite><testcase name="test_orphan" /></testsuite>',
        encoding="utf-8",
    )

    with pytest.raises(PytestAdapterError):
        parse_junit(xml_path)
