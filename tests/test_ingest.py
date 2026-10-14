from testbudget.ingest import parse_junit
from testbudget.db import (
    init_db,
    insert_test_results,
    get_all_results,
    get_test_stats,
)


FIXTURE = "fixtures/sample_junit.xml"


def test_parser_reads_all_testcases():
    results = parse_junit(FIXTURE)

    assert len(results) == 5


def test_parser_detects_failures():
    results = parse_junit(FIXTURE)

    failed = [
        result
        for result in results
        if result["status"] == "failed"
    ]

    assert len(failed) == 2

    failed_names = {
        result["test_name"]
        for result in failed
    }

    assert "test_checkout_invalid_card" in failed_names
    assert "test_payment_timeout" in failed_names


def test_parser_extracts_duration():
    results = parse_junit(FIXTURE)

    checkout = next(
        result
        for result in results
        if result["test_name"] == "test_checkout_success"
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
        if item["test_name"] == "test_checkout_invalid_card"
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
        if item["test_name"] == "test_checkout_invalid_card"
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