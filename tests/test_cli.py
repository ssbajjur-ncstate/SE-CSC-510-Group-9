import json

from testbudget.cli import main
from testbudget.db import get_all_results

FIXTURE = "fixtures/sample_junit.xml"


def test_init_creates_database(tmp_path, capsys):
    db_path = tmp_path / "testbudget.db"

    exit_code = main(
        [
            "init",
            "--db",
            str(db_path),
        ]
    )

    assert exit_code == 0
    assert db_path.exists()

    output = capsys.readouterr().out

    assert "Initialized TestBudget" in output
    assert str(db_path) in output


def test_ingest_stores_junit_results(tmp_path, capsys):
    db_path = tmp_path / "testbudget.db"

    exit_code = main(
        [
            "ingest",
            FIXTURE,
            "--db",
            str(db_path),
            "--changed-file",
            "src/checkout.py",
        ]
    )

    assert exit_code == 0

    stored = get_all_results(db_path)

    assert len(stored) == 5
    assert stored[0]["changed_file"] == "src/checkout.py"

    output = capsys.readouterr().out

    assert "Imported CI history" in output
    assert "Results: 5" in output
    assert "Failed: 2" in output


def test_ingest_rejects_missing_file(tmp_path, capsys):
    db_path = tmp_path / "testbudget.db"

    exit_code = main(
        [
            "ingest",
            "fixtures/does_not_exist.xml",
            "--db",
            str(db_path),
        ]
    )

    assert exit_code == 1

    output = capsys.readouterr().out

    assert "JUnit file not found" in output


def test_plan_prints_selected_and_skipped_tests(tmp_path, capsys):
    db_path = tmp_path / "testbudget.db"
    links_path = tmp_path / "test_links.json"

    links_path.write_text(
        json.dumps(
            {
                "src/checkout.py": [
                    "test_checkout_success",
                    "test_checkout_invalid_card",
                    "test_payment_timeout",
                ]
            }
        ),
        encoding="utf-8",
    )

    ingest_exit = main(
        [
            "ingest",
            FIXTURE,
            "--db",
            str(db_path),
            "--changed-file",
            "src/checkout.py",
        ]
    )

    assert ingest_exit == 0

    # Clear ingest output so we only inspect plan output.
    capsys.readouterr()

    plan_exit = main(
        [
            "plan",
            "--changed",
            "src/checkout.py",
            "--budget",
            "10",
            "--db",
            str(db_path),
            "--links",
            str(links_path),
        ]
    )

    assert plan_exit == 0

    output = capsys.readouterr().out

    assert "TESTBUDGET PLAN" in output
    assert "RANKED TESTS" in output
    assert "SELECTED" in output
    assert "SKIPPED" in output
    assert "Estimated runtime" in output
    assert "test_checkout_invalid_card" in output


def test_plan_rejects_empty_history(tmp_path, capsys):
    db_path = tmp_path / "testbudget.db"
    links_path = tmp_path / "test_links.json"

    links_path.write_text(
        json.dumps({"src/checkout.py": ["test_checkout"]}),
        encoding="utf-8",
    )

    # init creates an empty database with no test history.
    assert (
        main(
            [
                "init",
                "--db",
                str(db_path),
            ]
        )
        == 0
    )

    capsys.readouterr()

    exit_code = main(
        [
            "plan",
            "--changed",
            "src/checkout.py",
            "--budget",
            "10",
            "--db",
            str(db_path),
            "--links",
            str(links_path),
        ]
    )

    assert exit_code == 1

    output = capsys.readouterr().out
    assert "No test history found" in output


def test_plan_rejects_negative_budget(tmp_path, capsys):
    db_path = tmp_path / "testbudget.db"
    links_path = tmp_path / "test_links.json"

    links_path.write_text(
        json.dumps({"src/checkout.py": ["test_checkout"]}),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "plan",
            "--changed",
            "src/checkout.py",
            "--budget",
            "-1",
            "--db",
            str(db_path),
            "--links",
            str(links_path),
        ]
    )

    assert exit_code == 1

    output = capsys.readouterr().out
    assert "Budget cannot be negative" in output


def test_links_report_missing_file(tmp_path, capsys):
    from testbudget.cli import main

    code = main(["links", "--report", "--links", str(tmp_path / "nope.json")])

    assert code == 1
    assert "not found" in capsys.readouterr().out


def test_links_report_prints_summary(tmp_path, capsys):
    import json

    from testbudget.cli import main

    links_file = tmp_path / "links.json"
    links_file.write_text(
        json.dumps(
            {
                "tests/t.py::test_a": [
                    {"file": "src/a.py", "source": "import", "weight": 1.0}
                ]
            }
        )
    )

    code = main(["links", "--report", "--links", str(links_file)])

    assert code == 0
    assert "import: 1" in capsys.readouterr().out


def test_links_without_report_flag_does_nothing(capsys):
    from testbudget.cli import main

    assert main(["links"]) == 1
    assert "Use --report" in capsys.readouterr().out
